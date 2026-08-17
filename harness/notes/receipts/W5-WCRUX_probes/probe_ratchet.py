#!/usr/bin/env python3
"""W5-WCRUX probe 5 - combined-state SUITE RATCHET (predicate 3).

Runs the FULL test suite at one target and reports the counts. Called twice:
  TARGET='base'    -> wcrux-base    (df8c9ef3, clean fork point)
  TARGET='scratch' -> wcrux-scratch (df8c9ef3 + the 3 legs staged = combined)

Both run on the SAME interpreter, so any environment-driven skip/error is
identical on both sides and cancels in the delta (base vs combined). The ratchet
holds iff the combined tree introduces NO new failure/error vs base and does not
lose passes (new leg tests only ADD passes).

pytest is a subprocess (fresh interpreter, cwd+PYTHONPATH set) with
--continue-on-collection-errors so one bad import cannot abort the count.
"""
import subprocess, sys, os, json, re, time

WT = "C:/Users/User/SYNAPSE/.claude/worktrees"
TARGETS = {"base": f"{WT}/wcrux-base", "scratch": f"{WT}/wcrux-scratch"}

TARGET = globals().get("TARGET", "base")
cwd = TARGETS[TARGET]

env = dict(os.environ)
env["PYTHONPATH"] = os.path.join(cwd, "python") + os.pathsep + env.get("PYTHONPATH", "")
cmd = [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider",
       "--continue-on-collection-errors", "--no-header"]

t0 = time.time()
try:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=560)
    rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
    timed_out = False
except subprocess.TimeoutExpired as e:
    rc, out, timed_out = -9, (e.stdout or "") + (e.stderr or ""), True
dur = round(time.time() - t0, 1)

lines = [l for l in out.splitlines() if l.strip()]
resline = ""
for l in reversed(lines):
    if any(k in l for k in ("passed", "failed", "error", "no tests ran")):
        resline = l
        break
counts = {}
for kw in ("passed", "failed", "skipped", "error", "errors", "xfailed", "xpassed", "warning", "warnings", "deselected"):
    m = re.search(rf"(\d+) {kw}\b", resline)
    if m:
        counts[kw.rstrip("s")] = int(m.group(1))

print(json.dumps({
    "target": TARGET, "cwd": cwd, "rc": rc, "timed_out": timed_out,
    "duration_s": dur, "counts": counts, "result_line": resline.strip()[:200],
    "tail": "\n".join(lines[-6:])[:900],
}, indent=2))
