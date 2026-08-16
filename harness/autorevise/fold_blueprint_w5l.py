import json
from pathlib import Path

AV = Path(r"C:\Users\User\SYNAPSE\harness\autorevise")
NEW_IDS = ["W5-CATALOG", "W5-PARMGATE", "W5-MEASURES", "W5-WCRUX"]

rows = json.loads((AV / "waves" / "wave5.rows.json").read_text(encoding="utf-8"))
man_path = AV / "waves" / "wave5l.live.json"
man = json.loads(man_path.read_text(encoding="utf-8"))

existing = {leg["id"] for leg in man["legs"]}
added = []
for row in rows:
    if row["id"] in NEW_IDS and row["id"] not in existing:
        man["legs"].append(row)
        added.append(row["id"])

man["_comment"] += (" | FOLDED 2026-08-16 on Joe word 'fold this blueprint into the currently "
                    "running harness': substrate legs W5-CATALOG, W5-PARMGATE (dep CATALOG), "
                    "W5-MEASURES + crucible W5-WCRUX from docs/BLUEPRINT_WEAK_DOMAINS.md M1-M3. "
                    "Domain waves A-E gated behind substrate merge.")

man_path.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"appended {added} -> manifest now {len(man['legs'])} legs")
