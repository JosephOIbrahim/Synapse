#!/usr/bin/env python3
"""mcp_surface_probe — D-H22-4: pinned prose is not ground truth.

Enumerate the CONFIGURED APEX MCP provider's live tool list and diff it
against the recorded surface (``apex_mcp_surface.json``). On H21 the provider
resolves the in-process mock — an empty diff there proves the probe machinery
before the drop makes it real. On drop day the same probe runs against the
shipped MCP; ``absent`` and ``renamed`` must both be 0 before tasks 2.7/2.8
proceed (confirmed-absent endpoints auto-quarantine without re-litigation).

Usage (from the repo root):
    python python/synapse/science/mcp_surface_probe.py --diff --out .claude/mcp_surface_delta.json
    python python/synapse/science/mcp_surface_probe.py --record   # HUMAN-GATED (task 1.7)

Exit codes: 0 = probe ran and reported facts; 1 = operational failure. The
gate (``absent==0 and renamed==0``) is the CALLER's judgment (harness check /
tests) — this tool returns facts, mirroring the harness philosophy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

if __package__ in (None, ""):              # CLI invocation — make synapse importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SURFACE_PATH = Path(__file__).resolve().parent / "apex_mcp_surface.json"
SURFACE_SCHEMA = "apex_mcp_surface/v1"


def schema_digest(schema) -> str:
    """sha256 of the canonical (sorted-key, compact) JSON of an input schema."""
    canon = json.dumps(schema or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _default_provider():
    from synapse import providers
    return providers.get("apex_mcp")


def live_surface(provider=None) -> dict:
    """``name -> schema_digest`` from the configured provider's LIVE tool list."""
    provider = provider or _default_provider()
    return {t["name"]: schema_digest(t.get("input_schema", {}))
            for t in provider.list_tools()}


def recorded_surface(path: Path = SURFACE_PATH) -> dict:
    """``name -> schema_digest`` from the recorded-surface file."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {t["name"]: t["schema_digest"] for t in raw["tools"]}


def diff_surface(live: dict, recorded: dict) -> dict:
    """``{live, recorded, absent, added, renamed}``.

    ``renamed`` is kept honest: ONLY an exact schema-digest match under exactly
    one different name counts. Every other mismatch stays absent+added, which
    fails the wiring gate and forces a human re-record (``--record``).
    """
    absent = sorted(set(recorded) - set(live))
    added = sorted(set(live) - set(recorded))
    renamed = []
    claimed: set = set()
    for old in list(absent):
        candidates = [n for n in added
                      if n not in claimed and live[n] == recorded[old]]
        if len(candidates) == 1:
            claimed.add(candidates[0])
            renamed.append({"from": old, "to": candidates[0],
                            "schema_digest": recorded[old]})
    for r in renamed:
        absent.remove(r["from"])
        added.remove(r["to"])
    return {"live": sorted(live), "recorded": sorted(recorded),
            "absent": absent, "added": added, "renamed": renamed}


def record(provider=None, path: Path = SURFACE_PATH) -> dict:
    """HUMAN-GATED: rewrite the recorded surface from the live provider (1.7)."""
    from synapse.providers.apex_mcp import DEFAULT_ENDPOINT, ENDPOINT_ENV
    provider = provider or _default_provider()
    tools = sorted(provider.list_tools(), key=lambda t: t["name"])
    doc = {
        "schema": SURFACE_SCHEMA,
        "recorded_at": time.strftime("%Y-%m-%d"),
        "endpoint": os.environ.get(ENDPOINT_ENV) or DEFAULT_ENDPOINT,
        "note": ("Recorded APEX MCP tool surface (names + input-schema digests). "
                 "Mode A: authored against science/mcp_mock.py. Re-record from "
                 "the shipped H22 MCP is HUMAN-GATED (task 1.7)."),
        "tools": [{"name": t["name"],
                   "input_schema": t.get("input_schema", {}),
                   "schema_digest": schema_digest(t.get("input_schema", {}))}
                  for t in tools],
    }
    Path(path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--diff", action="store_true",
                    help="diff the live tool surface vs the recorded one (default action)")
    ap.add_argument("--record", action="store_true",
                    help="HUMAN-GATED: rewrite the recorded surface from the live provider")
    ap.add_argument("--out", default=None,
                    help="also write the diff JSON to this path")
    ap.add_argument("--surface", default=str(SURFACE_PATH),
                    help="recorded-surface file (default: alongside this script)")
    args = ap.parse_args(argv)
    try:
        if args.record:
            doc = record(path=Path(args.surface))
            sys.stdout.write(f"recorded {len(doc['tools'])} tool(s) -> {args.surface}\n")
            return 0
        delta = diff_surface(live_surface(), recorded_surface(Path(args.surface)))
    except Exception as e:
        sys.stderr.write(f"mcp_surface_probe failed: {type(e).__name__}: {e}\n")
        return 1
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(delta, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(delta) + "\n")
    return 0


if __name__ == "__main__":                  # pragma: no cover
    sys.exit(main())
