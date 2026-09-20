# build_manifest_bp7.py - BP6 rows -> waves/bp7.live.json (legs/v1) for orchestrate.ps1.
# Clone of build_manifest_bp4.py (wave id swap). BP6 = one leg, scouts + SYNTH, every leg
# routed by JEV-ROUTE (tier:auto -> resolved at compile; see harness/jev/ledger/bp7.route.jsonl).
# Nothing held. ARMED only on Joe's word (2026-09-19 "run it now").
import json
import subprocess
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
HELD = {}

rows = json.loads((AF / "waves" / "bp7.rows.json").read_text(encoding="utf-8"))
for r in rows:
    if r["id"] in HELD:
        r["state"] = "held"
        r["note"] = f"HELD - {HELD[r['id']]}. " + r.get("note", "")
base = subprocess.run(
    ["git", "-C", r"C:\Users\User\SYNAPSE", "rev-parse", "--short=8", "master"],
    capture_output=True, text=True).stdout.strip() or "master"
man = {
    "_comment": ('BP7 SCOUT wave - four read-only scouts + SYNTH compiled from harness/battleplan/notes/SCOUT_CHAT_STALL.md. '
                 f'Tier resolved by JEV-ROUTE at compile (ledger bp7.route.jsonl). Base=master {base}. ARMED only on '
                 'Joe word, WITH -Budget (rails turn = leg dispatch). Merge/push remain Joe words per act. '
                 'Own bus (battleplan/bus/bp7), own worktree prefix (bp7-*).'),
    "_schema": "legs/v1",
    "repo": "C:\\Users\\User\\SYNAPSE",
    "settings": "C:\\Users\\User\\SYNAPSE\\harness\\relay-settings.json",
    "effort": "max",
    "base": "master",
    "model": "claude-opus-4-8",
    "wave": "bp7",
    "legs": rows,
}
out = AF / "waves" / "bp7.live.json"
out.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
held = [r["id"] for r in rows if r["state"] == "held"]
print(f"manifest written: {out} ({len(rows)} legs, held={held}, base master@{base})")
