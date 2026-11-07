# build_manifest_bp10.py - BP10 rows -> waves/bp10.live.json (legs/v1) for orchestrate.ps1.
# Clone of build_manifest_bp8.py (wave id swap). BP10 = HARVEST: execute notes/HARVEST_SPEC.md +
# notes/JEV_HARVEST_BLUEPRINT.md as a SERIAL chain SCAFFOLD -> CORPUS -> GUIDES -> BENCH -> CRUX -> TIDY.
# Builders CORPUS/GUIDES/BENCH are `tier: auto` (JEV-ROUTE resolved them at compile time; see
# harness/jev/ledger/bp10.route.jsonl) and `team: auto` (JEV-TEAM, bp10.team.jsonl). SCAFFOLD/TIDY
# are literal mechanical (Haiku 4.5); CRUX literal referee (Fable 5.1). Manifest model is the reasoning
# tier default (Opus 4.8, rails_exec.json); effort `max` because `ultracode` is not a level Claude Code
# 2.1.278 lists (low|medium|high|xhigh|max) - same call BP4 made 2026-09-03. ARMED only on Joe's word.
import json
import subprocess
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
HELD = {}

rows = json.loads((AF / "waves" / "bp10.rows.json").read_text(encoding="utf-8"))
for r in rows:
    if r["id"] in HELD:
        r["state"] = "held"
        r["note"] = f"HELD - {HELD[r['id']]}. " + r.get("note", "")
base = subprocess.run(
    ["git", "-C", r"C:\Users\User\SYNAPSE", "rev-parse", "--short=8", "master"],
    capture_output=True, text=True).stdout.strip() or "master"
man = {
    "_comment": ('BP10 wave - HARVEST: fxhoudinimcp help-archive loader pattern -> H22 prose corpus, 31 workflow guides '
                 'gated into retrieval with provenance, outside-in benchmark harness, plus three Jev shadow guards '
                 '(rerank / harvest / bench). Serial chain by design (one Opus leg live at a time). Tiers for the three '
                 f'builders were chosen by JEV-ROUTE at compile. Base=master {base}. ARMED only on Joe word, WITH -Budget '
                 '(rails turn = leg dispatch). Merge/push remain Joe words per act. Own bus (battleplan/bus/bp10), own '
                 'worktree prefix (bp10-*). JEV-EDGE and JEV-DRIFT run in SHADOW.'),
    "_schema": "legs/v1",
    "repo": "C:\\Users\\User\\SYNAPSE",
    "settings": "C:\\Users\\User\\SYNAPSE\\harness\\relay-settings.json",
    "effort": "max",
    "base": "master",
    "model": "claude-opus-4-8",
    "wave": "bp10",
    "legs": rows,
}
out = AF / "waves" / "bp10.live.json"
out.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
held = [r["id"] for r in rows if r["state"] == "held"]
tiers = {r["id"]: r.get("tier") for r in rows}
print(f"manifest written: {out} ({len(rows)} legs, held={held}, base master@{base})")
print(f"tiers: {tiers}")
