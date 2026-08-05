#!/usr/bin/env python
"""Merge harness/rope/PENDING_TASKS.json into STATE.json.

Exists because a running runner holds STATE.json in memory and overwrites it at
every task boundary -- editing STATE.json mid-pass silently loses the edit.
Staging + an explicit merge between passes is the only safe seam.

Refuses to run while a runner holds the lock. Skips ids already present.
"""
import json, os, subprocess, sys

ROPE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROPE, "STATE.json")
PEND = os.path.join(ROPE, "PENDING_TASKS.json")

LOCK = os.path.join(ROPE, ".runner.lock")
if os.path.exists(LOCK):
    # Existence is not liveness. A killed runner leaves this file behind and
    # blocked staging forever, silently -- while runner.py::preflight happily
    # overwrote the same stale lock. Two readers of one lock disagreeing is the
    # bug; mirror preflight exactly. tasklist, never os.kill(pid, 0), which on
    # Windows routes through TerminateProcess.
    try:
        opid = open(LOCK).read().strip()
    except OSError:
        opid = ""
    if os.name == "nt":
        alive = bool(opid) and "python" in subprocess.run(
            ["tasklist", "/FI", "PID eq %s" % opid],
            capture_output=True, text=True).stdout.lower()
    else:
        try:
            os.kill(int(opid), 0)
            alive = True
        except (OSError, ValueError):
            alive = False
    if alive:
        sys.exit("a runner is looping (pid %s); wait for the pass to end, then re-run" % opid)
    print("stale lock (pid %s not alive) -- clearing" % (opid or "?"))
    os.remove(LOCK)
if not os.path.exists(PEND):
    sys.exit("nothing staged")

st = json.load(open(STATE, encoding="utf-8"))
have = {t["id"] for t in st["tasks"]}
added = [t for t in json.load(open(PEND, encoding="utf-8")) if t["id"] not in have]
st["tasks"].extend(added)
json.dump(st, open(STATE, "w", encoding="utf-8"), indent=1)
print("merged:", ", ".join(t["id"] for t in added) or "(none new)")
