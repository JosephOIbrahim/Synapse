"""One-shot: drop the harness `permissions` block from THIS repo's .claude/settings.json
so the human's interactive session is no longer denied `git push`. The autonomous harness
agents keep that never-push deny via harness/agent-settings.json (run.ts loads it with
--settings), so the safety stays scoped to the agents.

Run once, from ANY directory (path is computed from this file, not your cwd):

    python C:/Users/User/SYNAPSE/harness/rescope_settings.py

Then commit it:

    git -C C:/Users/User/SYNAPSE add .claude/settings.json
    git -C C:/Users/User/SYNAPSE commit -m "chore: scope harness never-push deny to agents"

(Delete this file afterward if you like — it's a one-shot.)
"""
import json
import os

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # harness/.. == repo root
p = os.path.join(repo, ".claude", "settings.json")

with open(p, encoding="utf-8") as f:
    d = json.load(f)

removed = [k for k in ("permissions", "_comment") if k in d]
for k in removed:
    d.pop(k, None)

with open(p, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2)

print("file:", p)
print("removed keys:", removed)
print("permissions present now:", "permissions" in d)
print("hooks intact:", list(d.get("hooks", {}).keys()))
