#!/usr/bin/env python3
"""W5-WCRUX probe 6 - pin the composed regression the ratchet found.

Runs tests/test_m3_env_conformance.py::test_every_source_env_read_is_documented
in BOTH base (must pass) and scratch/combined (fails), capturing the assertion
detail so the undocumented env read + its owning leg file is anchored, not vibed.
"""
import subprocess, sys, os, json

WT = "C:/Users/User/SYNAPSE/.claude/worktrees"
TARGETS = {"base": f"{WT}/wcrux-base", "scratch": f"{WT}/wcrux-scratch"}
TEST = "tests/test_m3_env_conformance.py::test_every_source_env_read_is_documented"

rep = {"probe": "regression", "test": TEST, "runs": {}}
for name, cwd in TARGETS.items():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(cwd, "python") + os.pathsep + env.get("PYTHONPATH", "")
    p = subprocess.run([sys.executable, "-m", "pytest", TEST, "-q", "-p",
                        "no:cacheprovider", "--no-header", "-rA"],
                       cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    out = (p.stdout or "") + (p.stderr or "")
    # keep the assertion region + summary
    rep["runs"][name] = {
        "rc": p.returncode,
        "passed": ("1 passed" in out and "failed" not in out.split("passed")[0][-30:]),
        "detail": out[-2500:],
    }
print(json.dumps(rep, indent=2))
