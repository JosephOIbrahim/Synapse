import json
import subprocess
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\apexforge")
rows = json.loads((AF / "waves" / "wavea1.rows.json").read_text(encoding="utf-8"))
base = subprocess.run(
    ["git", "-C", r"C:\Users\User\SYNAPSE", "rev-parse", "--short=8", "master"],
    capture_output=True, text=True).stdout.strip() or "master"
man = {
    "_comment": ('WA1 APEXFORGE wave - compiled from docs/APEX_H22_BLUEPRINT.md '
                 '(phases 0-4: G1/G4+C1 truth, C3 xref, C2 wire matrix, G2 recipe '
                 f'migration, ACRUX crucible). Base=master {base}. ARMED only on '
                 'Joe word. Merge/push/flip remain Joe words per act. Own bus '
                 '(apexforge/bus), own worktree prefix (wa1-*) - zero claim '
                 'overlap with any live autorevise wave.'),
    "_schema": "legs/v1",
    "repo": "C:\\Users\\User\\SYNAPSE",
    "settings": "C:\\Users\\User\\SYNAPSE\\harness\\relay-settings.json",
    "effort": "ultracode",
    "base": "master",
    "model": "claude-opus-4-8",
    "wave": "wavea1",
    "legs": rows,
}
out = AF / "waves" / "wavea1.live.json"
out.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"manifest written: {out} ({len(rows)} legs, legs is a JSON array: {isinstance(rows, list)}, base master@{base})")
