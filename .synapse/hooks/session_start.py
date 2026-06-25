#!/usr/bin/env python3
"""SYNAPSE harness SessionStart hook — inject orientation (cross-session memory),
backend-agnostic. Reads the orientation string the orchestrator wrote into state.json,
so it needs no knowledge of whether memory is flat files or a USD stage, and no deps."""
import json
import os
import sys


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    cwd = data.get("cwd") or os.getcwd()
    try:
        state = json.load(open(os.path.join(cwd, ".synapse", "state.json"), encoding="utf-8"))
    except Exception:
        sys.exit(0)
    c = state.get("contract") or {}
    if not c:
        sys.exit(0)
    tests = "tests are protected" + ("" if c.get("allow_test_edits") else " (allow_test_edits is off)")
    lines = [
        "## SYNAPSE harness — active task",
        f"- goal: {c.get('goal','')}",
        f"- session: {state.get('session','?')}   model: {state.get('model','')}",
        f"- you may edit ONLY: {c.get('owns', [])}",
        f"- do NOT touch: {c.get('do_not_touch', [])}; {tests}",
        "- PHANTOM-API: any unverified hou.*/pdg.* call will be DENIED by the fence; "
        "feature-detect via hou.ui/hou.qt instead of assuming an API exists.",
        "",
        "## Orientation — your cross-session memory",
        state.get("orient", "(none)"),
        "",
        "Confirm a green baseline, work ONE not-passing feature, keep the tree green, summarize "
        "what you did, then stop. You cannot mark a feature done — only a passing test does.",
    ]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": "\n".join(lines)}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
