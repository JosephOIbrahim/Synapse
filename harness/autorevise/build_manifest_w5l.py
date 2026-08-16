import json
from pathlib import Path

AV = Path(r"C:\Users\User\SYNAPSE\harness\autorevise")
rows = json.loads((AV / "waves" / "wave5.rows.json").read_text(encoding="utf-8"))
man = {
    "_comment": ('W5L lifecycle wave - compiled from Joe live-seat findings 2026-08-16 '
                 '(g5 fail + panel observations 1-7). Base=master df8c9ef3. ARMED on Joe word: '
                 '"fold these as changes into the harness and execute the harness". '
                 'Merge/flip/gui-receipt remain Joe words per act. Ritual halted at g5; '
                 'resumes on the fixed build.'),
    "_schema": "legs/v1",
    "repo": "C:\\Users\\User\\SYNAPSE",
    "settings": "C:\\Users\\User\\SYNAPSE\\harness\\relay-settings.json",
    "effort": "ultracode",
    "base": "master",
    "model": "claude-opus-4-8",
    "wave": "wave5l",
    "legs": rows,
}
out = AV / "waves" / "wave5l.live.json"
out.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"manifest written: {out} ({len(rows)} legs, legs is a JSON array: {isinstance(rows, list)})")
