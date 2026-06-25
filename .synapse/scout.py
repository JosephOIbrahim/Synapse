#!/usr/bin/env python3
"""
SYNAPSE harness SCOUT — the leadoff leg.

A READ-ONLY reconnaissance pass that runs before any build worker and grounds the plan
against the ACTUAL repo, so the harness never builds against assumed reality (the
"phantom-hardening trap"). It cannot edit anything; it only reads, runs checks, and writes
.synapse/scout_report.json — which the run loop then uses to GATE which contracts may run.

Five recon checks (all deterministic, run from PowerShell; no LLM needed for these):
  1. path resolution   — do each contract's owns / do_not_touch globs resolve to real files?
                         (catches inferred paths like daemon/**, host/freeze_chain*)
  2. verify targets    — do the files/tests each feature's `verify` references actually exist?
                         (tells you which goalpost tests must be written before a real run)
  3. dead-tree         — are the modules a quarantine contract expects to be dead actually
                         orphaned (zero importers)?
  4. baseline          — is the test suite green right now? (one global "get up to speed")
  5. runtime symbols   — dir(hou)/dir(pdg) via hython if available -> regenerate the phantom
                         manifest with LIVE data; else keep the seed and flag the live audit
                         as pending.

An optional Opus synthesis pass (harness.py `scout --synthesize`) reads this report + the
review docs and recommends contract adjustments — that is where "dynamic" planning starts.
"""
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SYN = os.path.join(ROOT, ".synapse")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_yaml(path):
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception:
        return {}


def _glob_count(pattern):
    """Count repo files matching a contract glob (** aware). 0 == unconfirmed path."""
    pat = pattern.replace("\\", "/").rstrip("/")
    # translate trailing '/**' to recursive file match
    full = os.path.join(ROOT, pat)
    hits = [p for p in glob.glob(full, recursive=True) if os.path.isfile(p)]
    if not hits and pat.endswith("/**"):
        hits = [p for p in glob.glob(os.path.join(ROOT, pat[:-3], "**"), recursive=True)
                if os.path.isfile(p)]
    return len(hits)


_PY_TEST = re.compile(r"(tests?/[\w/]+\.py)")
_VERIFY_PATH = re.compile(r"verify\.py\s+(\S+)\s+(\S+)")


def _verify_targets(feature_verify):
    """Best-effort: pull file/test paths a `verify` command depends on."""
    targets = []
    if not feature_verify:
        return targets
    for m in _PY_TEST.finditer(feature_verify):
        targets.append(m.group(1).split("::")[0])
    m = _VERIFY_PATH.search(feature_verify)
    if m and not m.group(2).startswith("-"):
        check, arg = m.group(1), m.group(2)
        # Some verify.py checks don't take a must-exist path, so os.path.exists
        # on their argument gives a false 'missing goalpost':
        #   importable  -> a dotted MODULE name (validated by import, not a path;
        #                  e.g. synapse.panel.designsystem)
        #   absent-file -> a path that SHOULD NOT exist (absence is the goal,
        #                  e.g. scene_doctor.py after quarantine)
        if check not in ("importable", "absent-file"):
            targets.append(arg)
    return targets


def _has_importers(stem, search_root):
    root = os.path.join(ROOT, search_root)
    if not os.path.isdir(root):
        return None  # can't tell
    pat = re.compile(r"(?m)^\s*(?:from\s+[\w.]*\b" + re.escape(stem) +
                     r"\b[\w.]*\s+import\b|import\s+[\w.]*\b" + re.escape(stem) + r"\b)")
    for dp, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".py") or fn[:-3] == stem:
                continue
            try:
                if pat.search(open(os.path.join(dp, fn), encoding="utf-8", errors="ignore").read()):
                    return True
            except OSError:
                continue
    return False


def scout_contract(cid):
    c = _load_yaml(os.path.join(SYN, "contracts", cid + ".yaml"))
    owns = c.get("owns", []) or []
    dnt = c.get("do_not_touch", []) or []
    owns_res = [{"glob": g, "matches": _glob_count(g)} for g in owns]
    dnt_res = [{"glob": g, "matches": _glob_count(g)} for g in dnt]
    unconfirmed = [r["glob"] for r in owns_res if r["matches"] == 0]
    missing_targets = []
    for f in (c.get("features") or []):
        for t in _verify_targets(f.get("verify")):
            if not os.path.exists(os.path.join(ROOT, t)) and t not in missing_targets:
                missing_targets.append(t)
    status = "ready"
    if unconfirmed:
        status = "needs-attention: unconfirmed owns path(s)"
    elif missing_targets:
        status = "needs-attention: goalpost target(s) missing"
    return {
        "autonomy": c.get("autonomy", "amber"),
        "model": c.get("model", "(default)"),
        "owns_resolved": owns_res,
        "do_not_touch_resolved": dnt_res,
        "unconfirmed_paths": unconfirmed,
        "verify_targets_missing": missing_targets,
        "status": status,
    }


def scout_dead_tree(orphans):
    confirmed, not_found, has_importers = [], [], []
    for stem in orphans:
        found = bool(glob.glob(os.path.join(ROOT, "**", stem + ".py"), recursive=True))
        if not found:
            not_found.append(stem)
            continue
        imp = _has_importers(stem, "python")
        (has_importers if imp else confirmed).append(stem)
    return {"orphans_confirmed_dead": confirmed, "orphans_not_found": not_found,
            "orphans_with_importers": has_importers}


def scout_baseline(gate_cmd):
    if not gate_cmd:
        return {"gate_cmd": "", "green": None}
    proc = subprocess.run(gate_cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
    return {"gate_cmd": gate_cmd, "green": proc.returncode == 0}


def scout_runtime_symbols(cfg, phantom):
    """Run dir(hou)/dir(pdg) under hython if available; else keep the seed + flag pending."""
    manifest_rel = phantom.get("runtime_manifest", ".synapse/runtime_symbols.H21_0_671.json")
    manifest_path = os.path.join(ROOT, manifest_rel)
    hython = cfg.get("hython_bin", "hython")
    audit = (
        "import hou, json\n"
        "syms = ['hou.'+s for s in dir(hou) if not s.startswith('_')]\n"
        "try:\n import pdg\n syms += ['pdg.'+s for s in dir(pdg) if not s.startswith('_')]\n"
        "except Exception: pass\n"
        "print('SYN_SYMS:' + json.dumps(syms))\n"
    )
    try:
        proc = subprocess.run([hython, "-c", audit], cwd=ROOT,
                              capture_output=True, text=True, timeout=120)
        line = next((l for l in proc.stdout.splitlines() if l.startswith("SYN_SYMS:")), None)
        if line:
            syms = json.loads(line[len("SYN_SYMS:"):])
            man = {}
            if os.path.exists(manifest_path):
                try:
                    man = json.loads(open(manifest_path, encoding="utf-8").read())
                except Exception:
                    man = {}
            man["build"] = man.get("build", "live")
            man["generated"] = f"LIVE dir() audit via hython @ {_now()}"
            man["allowed_symbols"] = sorted(set(syms))
            man.setdefault("known_phantoms", phantom.get("known_phantoms", []))
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=2)
            return {"source": "hython", "count": len(syms), "manifest": manifest_rel,
                    "live_audit_pending": False}
    except (OSError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    seed = {}
    if os.path.exists(manifest_path):
        try:
            seed = json.loads(open(manifest_path, encoding="utf-8").read())
        except Exception:
            seed = {}
    return {"source": "seed", "count": len(seed.get("allowed_symbols", []) or []),
            "manifest": manifest_rel, "live_audit_pending": True,
            "note": "hython not reached — run scout on a box with Houdini to arm allowlist mode"}


# orphan stems named in the codebase review §1.2 (the quarantine targets)
KNOWN_ORPHANS = [
    "scene_doctor", "network_trace", "dependency_map", "performance_profiler", "explain_mode",
    "apex_explainer", "apex_trace", "save_shot", "cross_scene", "shot_login", "bookmarks",
    "prompt_to_hda", "image_prep", "error_translator", "exposure_seam", "agent_prompts",
    "chat_panel",
]


def run_scout(queue_ids, write=True):
    cfg = _load_yaml(os.path.join(SYN, "config.yaml"))
    phantom = _load_yaml(os.path.join(SYN, "phantom_fence.yaml"))
    report = {
        "generated": _now(),
        "repo_root": ROOT,
        "baseline": scout_baseline(cfg.get("gate_cmd", "pytest -q")),
        "contracts": {cid: scout_contract(cid) for cid in queue_ids},
        "dead_tree": scout_dead_tree(KNOWN_ORPHANS),
        "runtime_symbols": scout_runtime_symbols(cfg, phantom),
    }
    if write:
        with open(os.path.join(SYN, "scout_report.json"), "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    return report


def print_summary(report):
    print(f"SCOUT report . {report['generated']}")
    b = report["baseline"]
    print(f"  baseline   : {b['gate_cmd']!r} -> {'GREEN' if b['green'] else 'RED' if b['green'] is False else 'n/a'}")
    rs = report["runtime_symbols"]
    print(f"  runtime    : {rs['source']} manifest, {rs['count']} symbols"
          + (" . LIVE AUDIT PENDING" if rs.get("live_audit_pending") else " . armed from live dir()"))
    dt = report["dead_tree"]
    print(f"  dead-tree  : {len(dt['orphans_confirmed_dead'])} confirmed dead, "
          f"{len(dt['orphans_with_importers'])} still imported, {len(dt['orphans_not_found'])} not found")
    print("  contracts  :")
    for cid, r in report["contracts"].items():
        flag = "ok " if r["status"] == "ready" else "!! "
        print(f"    {flag}[{r['autonomy']:5}] {cid:24} {r['status']}")
        if r["unconfirmed_paths"]:
            print(f"         unconfirmed owns: {r['unconfirmed_paths']}")
        if r["verify_targets_missing"]:
            print(f"         missing goalposts: {r['verify_targets_missing']}")


if __name__ == "__main__":
    ids = sys.argv[1:]
    rep = run_scout(ids, write=True)
    print_summary(rep)
