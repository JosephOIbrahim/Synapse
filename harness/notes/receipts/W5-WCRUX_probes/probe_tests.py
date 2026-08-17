#!/usr/bin/env python3
"""W5-WCRUX probe 2 - independent per-leg test re-execution (predicate 1).

Runs each leg's OWN test slice, both ISOLATED (in that leg's own worktree, only
its changes present) and COMPOSED (in the harness-staged combined scratch tree,
all three legs present - the seam-hunter lesson: isolated-green can hide a
composed regression). Nothing is inherited from the builders' receipts; every
count here is observed live by this crucible.

pytest is spawned as a SUBPROCESS (fresh interpreter per run, cwd+PYTHONPATH set
like harness/verify/checks.py) so each run is clean and the top-level
`python -m pytest` permission gate is not in the path.
"""
import subprocess, sys, json, re, os

WT = "C:/Users/User/SYNAPSE/.claude/worktrees"
SCRATCH = f"{WT}/wcrux-scratch"
RUNS = [
    ("CATALOG.isolated", f"{WT}/w5-catalog", ["tests/test_node_catalog.py"]),
    ("PARMGATE.isolated", f"{WT}/w5-parmgate",
     ["tests/test_parm_gate.py", "tests/test_cops_parmgate_routing.py"]),
    ("MEASURES.isolated", f"{WT}/w5-measures", ["tests/test_measures_contracts.py"]),
    ("COMPOSED.scratch", SCRATCH,
     ["tests/test_node_catalog.py", "tests/test_parm_gate.py",
      "tests/test_cops_parmgate_routing.py", "tests/test_measures_contracts.py"]),
]

SUMMARY_RE = re.compile(
    r"(?:(\d+) failed)?[,\s]*(?:(\d+) passed)?[,\s]*(?:(\d+) skipped)?"
    r"[,\s]*(?:(\d+) error(?:s)?)?[,\s]*(?:(\d+) warning)?")


def run_pytest(cwd, testfiles):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(cwd, "python") + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "--no-header"] + testfiles
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    out = (p.stdout or "") + (p.stderr or "")
    lines = [l for l in out.splitlines() if l.strip()]
    # find the pytest result line (last line with 'passed'/'failed'/'error'/'no tests')
    resline = ""
    for l in reversed(lines):
        if any(k in l for k in ("passed", "failed", "error", "no tests ran")):
            resline = l
            break
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for key in counts:
        m = re.search(rf"(\d+) {key[:-1] if key=='errors' else key}", resline)
        if m:
            counts[key] = int(m.group(1))
    # explicit error count uses 'error'
    m = re.search(r"(\d+) error", resline)
    if m:
        counts["errors"] = int(m.group(1))
    return {
        "rc": p.returncode,
        "counts": counts,
        "result_line": resline.strip()[:200],
        "tail": "\n".join(lines[-8:])[:1200],
    }


report = {"probe": "per_leg_tests", "runs": {}}
for label, cwd, files in RUNS:
    try:
        report["runs"][label] = run_pytest(cwd, files)
    except Exception as e:
        report["runs"][label] = {"rc": -1, "error": f"{type(e).__name__}: {e}"}

print(json.dumps(report, indent=2))
