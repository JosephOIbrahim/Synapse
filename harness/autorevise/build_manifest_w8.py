import json
from pathlib import Path

AV = Path(r"C:\Users\User\SYNAPSE\harness\autorevise")
allrows = json.loads((AV / "waves" / "wave5.rows.json").read_text(encoding="utf-8"))
rows = [r for r in allrows if r["id"].startswith("W8-")]
assert len(rows) == 9, f"expected 9 W8 legs, got {len(rows)}: {[r['id'] for r in rows]}"

# wave8.rows.json so make_control.py can build the dry-run control for this wave
(AV / "waves" / "wave8.rows.json").write_text(
    json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

man = {
    "_comment": ('W8 BASTION wave-0 (7 scouts + librarian + smith) - compiled from '
                 'harness/bastion/PROGRAM.md, ratified 2026-08-17 ("go"). Filtered to W8-* '
                 'from the shared rows file. ARMED on Joe word: "approved and go" (2026-08-17). '
                 'Merge/flip/push remain Joe words per act. '
                 'W8-LIBR gates on all seven scouts; W8-SMITH independent, touches '
                 'harness/bastion/** only.'),
    "_schema": "legs/v1",
    "repo": "C:\\Users\\User\\SYNAPSE",
    "settings": "C:\\Users\\User\\SYNAPSE\\harness\\relay-settings.json",
    "effort": "ultracode",
    "base": "master",
    "model": "claude-opus-4-8",
    "wave": "wave8",
    "legs": rows,
}
out = AV / "waves" / "wave8.live.json"
out.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"manifest written: {out} ({len(rows)} legs, legs is a JSON array: {isinstance(rows, list)})")
