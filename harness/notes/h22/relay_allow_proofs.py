import json
from pathlib import Path
p = Path(r"C:\Users\User\SYNAPSE\harness\relay-settings.json")
d = json.loads(p.read_text(encoding="utf-8"))
rule = "Bash(powershell -File harness/battleplan/runs/*:*)"
allow = d["permissions"]["allow"]
if rule not in allow:
    allow.append(rule)
d["_comment"] = d["_comment"] + (" 2026-09-01 (Joe word): one narrow allow for proof scripts under harness/battleplan/runs/ "
                                 "(BP2-NITS stalled on a .ps1 re-run prompt). Not powershell:* - arbitrary code stays a prompt.")
p.write_text(json.dumps(d, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
json.loads(p.read_text(encoding="utf-8"))
print("relay-settings.json valid;", len(allow), "allow rules;", len(d["permissions"]["deny"]), "deny rules; rule present:", rule in allow)
