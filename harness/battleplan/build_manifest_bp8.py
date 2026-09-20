# build_manifest_bp8.py - BP8 rows -> waves/bp8.live.json (legs/v1) for orchestrate.ps1.
# Clone of build_manifest_bp7.py (wave id swap). BP8 = the first wave shaped by JEV-SHAPE
# (build-screen-crux @ 0.99, harness/jev/ledger/bp8.shape.jsonl): WATCHDOG + TIMEOUTS builders on
# literal tier `reasoning` (Joe's word 2026-09-20: Opus 4.8 for execution), CRUX referee, TIDY
# mechanical. The memory-store leg was deliberately NOT authored (pending Joe's GUI repro), so
# nothing is held. ARMED only on Joe's word (2026-09-20 13:12 "3. Arm BP8").
import json
import subprocess
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
HELD = {}

rows = json.loads((AF / "waves" / "bp8.rows.json").read_text(encoding="utf-8"))
for r in rows:
    if r["id"] in HELD:
        r["state"] = "held"
        r["note"] = f"HELD - {HELD[r['id']]}. " + r.get("note", "")
base = subprocess.run(
    ["git", "-C", r"C:\Users\User\SYNAPSE", "rev-parse", "--short=8", "master"],
    capture_output=True, text=True).stdout.strip() or "master"
man = {
    "_comment": ('BP8 wave - act on harness/battleplan/notes/BP7_VERDICT.md (chat stalls after turn 1): panel watchdog + '
                 f'router tier timeouts, then CRUX, then TIDY. Shape chosen by JEV-SHAPE. Base=master {base}. ARMED only on '
                 'Joe word, WITH -Budget (rails turn = leg dispatch). Merge/push remain Joe words per act. '
                 'Own bus (battleplan/bus/bp8), own worktree prefix (bp8-*). JEV-EDGE and JEV-DRIFT run in SHADOW.'),
    "_schema": "legs/v1",
    "repo": "C:\\Users\\User\\SYNAPSE",
    "settings": "C:\\Users\\User\\SYNAPSE\\harness\\relay-settings.json",
    "effort": "max",
    "base": "master",
    "model": "claude-opus-4-8",
    "wave": "bp8",
    "legs": rows,
}
out = AF / "waves" / "bp8.live.json"
out.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
held = [r["id"] for r in rows if r["state"] == "held"]
print(f"manifest written: {out} ({len(rows)} legs, held={held}, base master@{base})")
