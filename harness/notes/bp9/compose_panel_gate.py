"""Composed gate for the panel spec legs (PNL-L1..L7).

Isolated green hides composed regressions (memory: solaris-harden). Every leg verified
alone, in its own worktree, against the files IT named. This script does the other half:
merge the leaf branches into one tree and run the gates nothing per-leg can run.

    python harness/notes/bp9/compose_panel_gate.py --plan          # print the merge plan, touch nothing
    python harness/notes/bp9/compose_panel_gate.py --merge         # build the integration worktree
    python harness/notes/bp9/compose_panel_gate.py --gate          # run the three gates on it
    python harness/notes/bp9/compose_panel_gate.py --merge --gate  # both

Merging is local only: it creates a worktree and a branch, never touches master, never pushes.
The gates are run ONE AT A TIME (the stock suite and the seat suite both attach a rotating
handler to the same log file; running them together fakes a failure -- see docs/RELEASE_CARD.md
"Traps"). SYNAPSE_LOG_DIR is pointed at the integration worktree for the same reason.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INT_DIR = ROOT.parent / "pnl-integration"
INT_BRANCH = "pnl/integration"
HYTHON = r"C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"
RESULTS = Path(__file__).resolve().parent / "panel_results.json"
LOGDIR = Path(__file__).resolve().parent / "gate-logs"

# Leaves of the dependency graph. Each already contains its upstream chain:
#   L3b -> L3a -> L1 ;  L5/L6/L7 -> L4 -> L2 -> L1
# Deepest chain first: the type ramp lands before the palette rows that sit on it.
LEAF_ORDER = ["PNL-L5", "PNL-L6", "PNL-L7", "PNL-L3B"]


def sh(cmd: list[str] | str, cwd: Path = ROOT, env: dict | None = None, timeout: int = 1800):
    e = {**os.environ, **(env or {})}
    return subprocess.run(cmd, cwd=str(cwd), env=e, shell=isinstance(cmd, str),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def load_results() -> dict:
    if not RESULTS.exists():
        sys.exit(f"no {RESULTS}: write the workflow result there first")
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def plan(res: dict) -> list[tuple[str, str, str]]:
    """[(leg, branch, verdict)] for the leaves, in merge order. Refuses a leaf that is not merge-ready."""
    out, refused = [], []
    for leg in LEAF_ORDER:
        r = res.get(leg) or {}
        v = r.get("verdict") or {}
        rc = r.get("receipt") or {}
        if not v.get("merge_ready") or not rc.get("branch"):
            refused.append(f"{leg}: verdict={v.get('verdict')} merge_ready={v.get('merge_ready')} branch={rc.get('branch')}")
            continue
        out.append((leg, rc["branch"], v.get("verdict", "?")))
    if refused:
        print("REFUSED (not merge-ready, excluded from the integration):")
        for r in refused:
            print("   ", r)
    return out


def merge(leaves) -> int:
    if INT_DIR.exists():
        sh(["git", "worktree", "remove", "--force", str(INT_DIR)])
    sh(["git", "branch", "-D", INT_BRANCH])
    r = sh(["git", "worktree", "add", "-b", INT_BRANCH, str(INT_DIR), "master"])
    if r.returncode:
        print(r.stdout, r.stderr)
        return 1
    for leg, branch, verdict in leaves:
        m = sh(["git", "merge", "--no-edit", "--no-ff", branch, "-m", f"merge(pnl): {leg} {branch} [{verdict}]"], cwd=INT_DIR)
        if m.returncode:
            conflicts = sh(["git", "diff", "--name-only", "--diff-filter=U"], cwd=INT_DIR).stdout.strip()
            print(f"CONFLICT merging {leg} ({branch}):\n{conflicts}")
            print("left in place for a human; resolve in", INT_DIR, "or run --merge again after a fix")
            return 2
        print(f"merged {leg:9} {branch}")
    n = sh(["git", "rev-list", "--count", f"master..{INT_BRANCH}"]).stdout.strip()
    print(f"{INT_BRANCH} is {n} commits over master at {INT_DIR}")
    return 0


_SUMMARY = re.compile(r"(\d+) (passed|failed|error)", re.I)


def _verdict(out: str) -> tuple[bool, str]:
    """A pytest run is green only if a summary line exists AND names no failure.
    A run that is entirely skipped is NOT green (hytest skips when PySide is absent)."""
    line = ""
    for ln in out.splitlines():
        if ("passed" in ln or "failed" in ln or "error" in ln) and ("=" in ln or " in " in ln):
            line = ln.strip()
    if not line:
        return False, "no pytest summary line (did it run?)"
    if re.search(r"\d+ (failed|error)", line):
        return False, line
    if not re.search(r"[1-9]\d* passed", line):
        return False, line + "  (no test actually passed)"
    return True, line


def gate() -> int:
    if not INT_DIR.exists():
        sys.exit(f"{INT_DIR} does not exist: run --merge first")
    LOGDIR.mkdir(parents=True, exist_ok=True)
    env = {"SYNAPSE_HYTHON": HYTHON, "QT_QPA_PLATFORM": "offscreen",
           "SYNAPSE_LOG_DIR": str(INT_DIR / ".scratch" / "logs")}
    (INT_DIR / ".scratch" / "logs").mkdir(parents=True, exist_ok=True)

    gates = [
        ("no test deleted", ["git", "diff", "--diff-filter=D", "--name-only", "master", "--", "tests/"], "empty"),
        ("stock suite (alone)", [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider",
                                 "-m", "not needs_houdini", "--deselect", "tests/test_phase0c_doc1_toolcount.py"], "pytest"),
        ("panel seat suite (alone, hython)", [sys.executable, ".synapse/hytest.py", "tests/panel", "-q"], "pytest"),
        ("strict panel audit", [HYTHON, "audit_panel.py", "--strict"], "exit0"),
        ("first-click probe", [HYTHON, "python/synapse/panel/scripts/probe_first_click.py"], "exit0"),
        ("measure probe", [HYTHON, "python/synapse/panel/scripts/probe_measure.py"], "exit0"),
        ("host-floor probe", [HYTHON, "python/synapse/panel/scripts/probe_ui_font.py"], "exit0"),
    ]
    rows, bad = [], 0
    for name, cmd, kind in gates:
        print(f"-- {name} ...", flush=True)
        r = sh(cmd, cwd=INT_DIR, env=env, timeout=3600)
        out = (r.stdout or "") + (r.stderr or "")
        (LOGDIR / (re.sub(r"[^a-z0-9]+", "-", name.lower()) + ".log")).write_text(out, encoding="utf-8")
        if kind == "empty":
            ok, ev = (not out.strip()), (out.strip() or "no test file deleted")
        elif kind == "pytest":
            ok, ev = _verdict(out)
        else:
            ok = r.returncode == 0
            ev = (out.strip().splitlines() or ["(no output)"])[-1][:160]
        rows.append((name, ok, ev))
        bad += 0 if ok else 1
        print(f"   {'PASS' if ok else 'FAIL'}  {ev}")

    print("\n== composed gate ==")
    for name, ok, ev in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name:34} {ev[:110]}")
    print(f"\n{len(rows) - bad}/{len(rows)} gates green; logs in {LOGDIR}")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args()
    if not (a.plan or a.merge or a.gate):
        ap.error("pick --plan, --merge and/or --gate")
    rc = 0
    if a.plan or a.merge:
        leaves = plan(load_results())
        print("merge plan:", " -> ".join(f"{l}({b})" for l, b, _ in leaves) or "(nothing merge-ready)")
        if a.merge:
            if not leaves:
                sys.exit("nothing merge-ready; refusing to build an empty integration")
            rc = merge(leaves)
    if a.gate and rc == 0:
        rc = gate()
    sys.exit(rc)
