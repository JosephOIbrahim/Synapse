#!/usr/bin/env python
"""Merge harness/rope/PENDING_TASKS.json into STATE.json.

Exists because a running runner holds STATE.json in memory and overwrites it at
every task boundary -- editing STATE.json mid-pass silently loses the edit.
Staging + an explicit merge between passes is the only safe seam.

Refuses to run while a runner holds the lock. Skips ids already present.
"""
import json, os, sys

ROPE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROPE, "STATE.json")
PEND = os.path.join(ROPE, "PENDING_TASKS.json")

if os.path.exists(os.path.join(ROPE, ".runner.lock")):
    sys.exit("a runner is looping; wait for the pass to end, then re-run")
if not os.path.exists(PEND):
    sys.exit("nothing staged")

st = json.load(open(STATE, encoding="utf-8"))
have = {t["id"] for t in st["tasks"]}
added = [t for t in json.load(open(PEND, encoding="utf-8")) if t["id"] not in have]
st["tasks"].extend(added)
json.dump(st, open(STATE, "w", encoding="utf-8"), indent=1)
print("merged:", ", ".join(t["id"] for t in added) or "(none new)")
