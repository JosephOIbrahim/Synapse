# build_manifest_bp2.py - BP2 rows -> waves/bp2.live.json (legs/v1) for orchestrate.ps1.
# Clone of build_manifest_bp1.py (wave id swap) + one BP2 rule: HELD legs.
# docs/BATTLEPLAN.md 2026-09-01 sec.12 R-6: the orchestrator flips a leg
# blocked -> ready the moment its deps' RECEIPTS exist, not when they are merged.
# BP2-PANELDESIGN must wait for PANELTRUTH to be MERGED (Joe's word), so it is
# armed 'held' here; a leg in state 'held' is never dispatched (orchestrate.ps1:260).
# Flipping held -> ready is a manifest edit on Joe's Wed word, then re-arm.
import json
import subprocess
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
# 2026-09-01 14:5x - Joe's word ("spin up more agents to close the loop"): PANELDESIGN off hold.
# Its dep (PANELTRUTH receipt) is satisfied on master once the merge lands; branch base = master.
HELD = {}

rows = json.loads((AF / "waves" / "bp2.rows.json").read_text(encoding="utf-8"))
for r in rows:
    if r["id"] in HELD:
        r["state"] = "held"
        r["note"] = f"HELD - {HELD[r['id']]}. " + r.get("note", "")
base = subprocess.run(
    ["git", "-C", r"C:\Users\User\SYNAPSE", "rev-parse", "--short=8", "master"],
    capture_output=True, text=True).stdout.strip() or "master"
man = {
    "_comment": ('BP2 BATTLEPLAN wave - compiled from docs/BATTLEPLAN.md 2026-09-01 '
                 '(pairs 1+2: METER || PANELTRUTH, LATENCY || STORE; PANELDESIGN held; '
                 f'CRUX blocked on the four pair builders). Base=master {base}. ARMED only on '
                 'Joe word, WITH -Budget (rails turn = leg dispatch, sec.12 R-3). '
                 'Merge/push/flip remain Joe words per act. Own bus (battleplan/bus/bp2), '
                 'own worktree prefix (bp2-*) - zero claim overlap with any live wave.'),
    "_schema": "legs/v1",
    "repo": "C:\\Users\\User\\SYNAPSE",
    "settings": "C:\\Users\\User\\SYNAPSE\\harness\\relay-settings.json",
    "effort": "ultracode",
    "base": "master",
    "model": "claude-opus-4-8",
    "wave": "bp2",
    "legs": rows,
}
out = AF / "waves" / "bp2.live.json"
out.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
held = [r["id"] for r in rows if r["state"] == "held"]
print(f"manifest written: {out} ({len(rows)} legs, held={held}, base master@{base})")
