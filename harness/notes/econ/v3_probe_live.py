#!/usr/bin/env python
"""V3 producer — run the live capability probe against every CONFIGURED provider.

    python harness/notes/econ/v3_probe_live.py [--label NAME] [--env-from PATH]

Emits ``harness/notes/econ/V3_probe_live[.LABEL].json``.

**Zero completion spend.** Every call this makes is a free list/metadata
endpoint (see ``probe.FREE_ENDPOINTS``). No completion is requested, here or in
the module under it. Any probe declined on cost grounds is recorded in
``declined`` with what it would have measured and why it was not run.

``--env-from`` names a directory whose ``.env`` is loaded with **assignment,
not setdefault**. That is not a convenience: ``synapse.host.auth._load_dotenv``
uses ``os.environ.setdefault``, so an ``ANTHROPIC_API_KEY`` that exists in the
environment as an EMPTY STRING permanently shadows the repo ``.env`` and the
product reports itself unconfigured while holding a valid key. This producer
can therefore measure both realities and label which one it measured.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "python"))


def load_env_from(directory: pathlib.Path) -> dict:
    """Load ``<directory>/.env`` into os.environ by ASSIGNMENT.

    Returns a provenance record (names only — never a value, never a prefix).
    """
    rec = {"path": str(directory / ".env"), "exists": False, "assigned": []}
    path = directory / ".env"
    if not path.is_file():
        return rec
    rec["exists"] = True
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        value = value.strip().strip('"').strip("'")
        if name and value:
            os.environ[name] = value          # assignment, NOT setdefault
            rec["assigned"].append(name)
    return rec


def env_shadow_check() -> dict:
    """Is any provider key present-but-EMPTY in the environment?

    An empty env var defeats ``setdefault``-based dotenv loading. This is the
    condition, stated before it is measured, under which the product reports a
    configured provider as unconfigured.
    """
    out = {}
    for name in ("ANTHROPIC_API_KEY", "NVIDIA_API_KEY", "GEMINI_API_KEY",
                 "GOOGLE_API_KEY", "OLLAMA_API_KEY"):
        if name in os.environ:
            out[name] = {"present": True, "empty": os.environ[name].strip() == ""}
        else:
            out[name] = {"present": False, "empty": None}
    return out


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO),
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="", help="suffix for the output artifact")
    ap.add_argument("--env-from", default="",
                    help="directory whose .env is loaded by assignment")
    args = ap.parse_args()

    env_record = {"loaded": False}
    if args.env_from:
        env_record = load_env_from(pathlib.Path(args.env_from).resolve())
        env_record["loaded"] = True

    shadow = env_shadow_check()

    from synapse.panel.providers import probe as P
    from synapse.panel.providers import registry as R

    t0 = time.time()
    configured = P.configured_providers()
    rows = P.probe_all(now=None)
    wall_ms = (time.time() - t0) * 1000.0
    now = time.time()

    declared = {pid: [m for m, _ in R.models_for(pid)] for pid in P._PROBES}

    per_provider = {}
    for pid in P._PROBES:
        prows = [r for r in rows if r.provider == pid]
        per_provider[pid] = {
            "configured": configured.get(pid),
            "declared_count": len(declared[pid]),
            "declared": declared[pid],
            "live_count": sum(1 for r in prows if r.live),
            "rows": len(prows),
            "method": prows[0].method if prows else None,
            "reason": prows[0].reason if prows else None,
            "latency_ms": prows[0].latency_ms if prows else None,
            "quota_source": prows[0].quota_source if prows else None,
            "declared_but_absent": [r.model for r in prows
                                    if r.reason == "declared_but_absent"],
            "live_not_declared": [r.model for r in prows
                                  if r.live and not r.declared],
            "colours": _colour_counts(P, prows, now),
        }

    out = {
        "schema": "v3_probe_live/v1",
        "producer": "harness/notes/econ/v3_probe_live.py",
        "label": args.label or "default",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "commit": git_commit(),
        "host": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
        "env": {
            "explicit_env_load": env_record,
            "empty_string_shadow_check": shadow,
            "auth_repo_root": _auth_repo_root(),
        },
        "spend": {
            "completions_issued": 0,
            "endpoints_called": sorted({r.method for r in rows}),
            "allowlist": sorted(P.FREE_ENDPOINTS),
            "all_calls_in_allowlist": all(r.method in P.FREE_ENDPOINTS for r in rows),
            "declined": _declined(),
        },
        "policy": {
            "refresh_interval_s": P.REFRESH_INTERVAL_S,
            "probe_ttl_s": P.PROBE_TTL_S,
            "requests_per_hour_per_provider_worst_case":
                3600.0 / P.REFRESH_INTERVAL_S,
        },
        "wall_ms": round(wall_ms, 1),
        "configured": configured,
        "per_provider": per_provider,
        "summary": P.summarize(rows, now=now),
        "rows": [r.to_dict() for r in rows],
    }
    name = "V3_probe_live%s.json" % (("." + args.label) if args.label else "")
    dest = HERE.parent / name
    dest.write_text(json.dumps(out, indent=1, sort_keys=False), encoding="utf-8")

    print("wrote %s" % dest)
    print("configured: %s" % {k: v for k, v in configured.items() if v})
    for pid, info in per_provider.items():
        print("  %-9s configured=%-5s declared=%-2d live=%-3d %s"
              % (pid, info["configured"], info["declared_count"],
                 info["live_count"], info["colours"]))
    print("completions issued: 0")
    return 0


def _colour_counts(P, rows, now):
    counts = {c: 0 for c in P.COLOURS}
    for r in rows:
        counts[P.colour_for(r, now=now)] += 1
    return counts


def _auth_repo_root() -> str:
    """Where ``synapse.host.auth`` looks for ``.env`` — checkout-dependent, and
    therefore part of the answer, not background."""
    try:
        from synapse.host import auth
        return str(auth._repo_root())
    except Exception as exc:
        return "unresolved: %s" % exc


def _declined() -> list:
    """Probes NOT run on cost grounds, with what each would have measured."""
    return [
        {
            "probe": "POST /v1/messages (Anthropic completions, 1 token)",
            "would_have_measured":
                "quota headroom — anthropic-ratelimit-{requests,input-tokens,"
                "output-tokens}-{limit,remaining,reset} — which is published ONLY "
                "by the billed completions endpoint",
            "declined_because":
                "it bills. The economist axis cannot credibly measure cost while "
                "being careless with it, and a liveness check that consumes the "
                "quota it reports on is self-defeating.",
            "consequence_recorded":
                "quota_remaining/quota_total are None for every metered provider, "
                "with quota_source='unavailable_at_zero_cost'. Rate-limiting is "
                "still caught reactively on a 429; headroom is not reported.",
        },
        {
            "probe": "POST /v1/chat/completions (NVIDIA NIM, Ollama :cloud)",
            "would_have_measured":
                "end-to-end generation latency and any x-ratelimit-* headers on "
                "the completions bucket",
            "declined_because":
                "NIM and Ollama :cloud tags are metered by their host. "
                "GET /v1/models and GET /api/tags answer availability for free.",
            "consequence_recorded":
                "latency_ms is METADATA-endpoint latency, not generation latency. "
                "It is a liveness number, and must not be read as time-to-first-token.",
        },
    ]


if __name__ == "__main__":
    raise SystemExit(main())
