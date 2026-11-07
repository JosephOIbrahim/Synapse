# watch_approvals_bp11.py - read-only: which BP11 legs may be waiting on a permission prompt?
# A leg reads PENDING? when its newest Claude Code transcript ends on an assistant tool_use with no tool_result
# and nothing has been written for IDLE_S seconds. A long test run looks the same, hence the question mark: the
# seat confirms on screen before acting. It prints the tool and its input so the request can be judged against
# the leg's fence first. This script sends no keys, clicks nothing and changes nothing.
import json
import sys
import time
from pathlib import Path

PROJ = Path.home() / ".claude" / "projects"
IDLE_S = int(sys.argv[1]) if len(sys.argv) > 1 else 90
LEGS = ["fixfwd", "fixfwd2", "idcore", "idsurf", "salience", "harden", "crux", "tidy", "hardfix", "idfix", "crux2"]


def last_record(f):
    last = None
    with f.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                last = line
    try:
        return json.loads(last) if last else {}
    except ValueError:
        return {}


for leg in LEGS:
    dirs = [d for d in PROJ.iterdir() if d.is_dir() and d.name.lower().endswith(f"worktrees-bp11-{leg}")]
    files = sorted((f for d in dirs for f in d.glob("*.jsonl")), key=lambda f: f.stat().st_mtime)
    if not files:
        continue
    f = files[-1]
    age = int(time.time() - f.stat().st_mtime)
    rec = last_record(f)
    msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
    tool = None
    if rec.get("type") == "assistant" and isinstance(msg.get("content"), list):
        tool = next((c for c in reversed(msg["content"]) if isinstance(c, dict) and c.get("type") == "tool_use"), None)
    state = "PENDING?" if tool and age > IDLE_S else ("working" if age <= IDLE_S else "quiet")
    desc = ""
    if tool:
        inp = tool.get("input") or {}
        desc = f"{tool.get('name')}: " + str(inp.get("command") or inp.get("file_path") or json.dumps(inp))[:200]
    print(f"{leg:<9} {state:<9} last write {age:>5}s  {desc}")
