# build_manifest_bp11.py - BP11 rows -> waves/bp11.live.json (legs/v1) for orchestrate.ps1.
# Clone of build_manifest_bp10.py plus CHAINED BASES: IDSURF is cut from IDCORE's branch, SALIENCE from
# IDSURF's, HARDEN from SALIENCE's (orchestrate.ps1:559-566 honours a leg-declared base), so each Identify
# leg builds on the code of the one before and only one Opus-class leg is live at a time. FIXFWD, IDCORE,
# CRUX and TIDY keep the default base. Tiers for `tier: auto` legs were chosen by JEV-ROUTE at compile
# (harness/jev/ledger/bp11.route.jsonl); `team: auto` by JEV-TEAM (bp11.team.jsonl). ARMED only on Joe's word.
import json
import subprocess
from pathlib import Path

AF = Path(r"C:\Users\User\SYNAPSE\harness\battleplan")
HELD = {}
CHAIN = {"BP11-IDSURF": "BP11-IDCORE", "BP11-SALIENCE": "BP11-IDSURF", "BP11-HARDEN": "BP11-SALIENCE",
         "BP11-FIXFWD2": "BP11-FIXFWD"}  # FIXFWD2 added mid-wave 2026-09-28: repairs FIXFWD's CRLF hashes

rows = json.loads((AF / "waves" / "bp11.rows.json").read_text(encoding="utf-8"))
branch = {r["id"]: r.get("branch") for r in rows}
for r in rows:
    if r["id"] in CHAIN:
        parent = branch.get(CHAIN[r["id"]])
        if not parent:
            raise SystemExit(f"no branch recorded for {CHAIN[r['id']]}; cannot chain {r['id']}")
        r["base"] = parent
    if r["id"] in HELD:
        r["state"] = "held"
        r["note"] = f"HELD - {HELD[r['id']]}. " + r.get("note", "")
base = subprocess.run(
    ["git", "-C", r"C:\Users\User\SYNAPSE", "rev-parse", "--short=8", "master"],
    capture_output=True, text=True).stdout.strip() or "master"
man = {
    "_comment": ("BP11 wave - IDENTIFY + HARDENING: notes/IDENTIFY_BLUEPRINT.md (zero-token node bubbles, Jev "
                 "salience in shadow) and notes/BP11_CTO_PLAN.md (Windows CI, broad-except ratchet, BP10 fix-forward). "
                 "Shape build-screen-crux from JEV-SHAPE; Identify legs chained by base. "
                 f"Base=master {base}. ARMED only on Joe word, WITH -Budget (rails turn = leg dispatch). Merge/push "
                 "remain Joe words per act. Own bus (battleplan/bus/bp11), own worktree prefix (bp11-*). JEV-EDGE and "
                 "JEV-DRIFT run in SHADOW."),
    "_schema": "legs/v1",
    "repo": "C:\\Users\\User\\SYNAPSE",
    "settings": "C:\\Users\\User\\SYNAPSE\\harness\\relay-settings.json",
    "effort": "xhigh",  # R-7 trial on Joe's word 2026-09-28: BP10 ran max; compare per-leg output in the ledgers
    "base": "master",
    "model": "claude-opus-4-8",
    "wave": "bp11",
    "legs": rows,
}
out = AF / "waves" / "bp11.live.json"
out.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
held = [r["id"] for r in rows if r.get("state") == "held"]
print(f"manifest written: {out} ({len(rows)} legs, held={held}, base master@{base})")
for r in rows:
    print(f"  {r['id']:<14} tier={r.get('tier')!s:<11} team={r.get('team')!s:<40} "
          f"branch={r.get('branch')} base={r.get('base', '(default)')} deps={r.get('deps')}")
