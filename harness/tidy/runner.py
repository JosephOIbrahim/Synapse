#!/usr/bin/env python3
"""TIDY Mode-1 runner: cheap daily sweep, no subagents.

Heuristic classification of the working tree. The agent team (Mode 2,
harness/tidy/workflow.js) is the deep review; this is the quick check.

Usage: python harness/tidy/runner.py
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
STATE = HERE / "STATE.json"

# name heuristics -> disposition (first match wins)
RULES = [
    (re.compile(r"\.bak$"), "DROP"),
    (re.compile(r"^\$null$"), "DROP"),
    (re.compile(r"\.log$"), "DROP"),
    (re.compile(r"^_commit_msg\d*\.txt$"), "DROP"),
    (re.compile(r"^_probe_.*\.py$"), "PARK"),
    (re.compile(r"^_why\.py$"), "PARK"),
    (re.compile(r"^_diff_runs\.py$"), "PARK"),
    (re.compile(r"^_extract_reasons\.py$"), "PARK"),
    (re.compile(r"^_route_dispatch\.py$"), "PARK"),
    (re.compile(r"^watch_.*\.ps1$"), "PARK"),
    (re.compile(r"^MONETA_WATCH\.txt$"), "PARK"),
    (re.compile(r"^pkg_info\.json$"), "MOVE"),
    (re.compile(r"^project\.md$"), "MOVE"),
    (re.compile(r"^models/$"), "GITIGNORE"),
    (re.compile(r"^shot_layers/$"), "GITIGNORE"),
]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def classify(path: str) -> str:
    for pattern, disp in RULES:
        if pattern.search(path):
            return disp
    return "REVIEW"  # needs the agent team


def main() -> int:
    status = git("status", "--porcelain=v1")
    items = []
    for line in status.splitlines():
        code, path = line[:2].strip(), line[3:]
        kind = "untracked" if code == "??" else ("modified" if code in ("M", "MM") else "other")
        items.append({"path": path, "kind": kind, "disposition": classify(path)})

    counts = {}
    for item in items:
        counts[item["disposition"]] = counts.get(item["disposition"], 0) + 1

    report = {
        "run_at": datetime.now().isoformat(),
        "items": items,
        "summary": f"{len(items)} items: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
    }

    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"schema_version": 1, "name": "tidy", "runs": []}
    state["last_run"] = report["run_at"]
    state["runs"].append(report)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2))
    review = [i["path"] for i in items if i["disposition"] == "REVIEW"]
    if review:
        print(f"\nREVIEW items need the agent team: {review}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
