# probe_rulings.py - one-off calibration probe: screen the BP4-RULINGS receipt (the leg
# CRUX called BROKEN) from its branch, since it never reached master. Prints the screen
# verdict beside the per-row probabilities. Safe to delete after BP6-JEV lands.
import json, subprocess, sys
from pathlib import Path

REPO = Path(r"C:\Users\User\SYNAPSE")
sys.path.insert(0, str(REPO / "harness" / "jev"))
import jev_screen as js  # noqa: E402

branches = subprocess.run(["git", "branch", "-a", "--list", "*bp4/rulings*"], cwd=REPO,
                          capture_output=True, text=True).stdout.split()
branches = [b.replace("remotes/", "") for b in branches if b != "*"]
print("branches:", branches or "none")
receipt = None
for b in branches:
    out = subprocess.run(["git", "show", f"{b}:harness/notes/receipts/BP4-RULINGS.json"], cwd=REPO,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode == 0 and out.stdout.strip():
        receipt = json.loads(out.stdout)
        print("receipt from", b)
        break
if receipt is None:
    print("no BP4-RULINGS receipt on any bp4/rulings* branch")
    sys.exit(2)

m = json.loads((REPO / "harness/battleplan/missions/BP4-RULINGS.json").read_text(encoding="utf-8"))
print("receipt status:", receipt.get("status"))
for i, a in enumerate(receipt.get("acceptance", [])):
    print(f"  acc[{i}] verdict={a.get('verdict')} evidence={str(a.get('evidence'))[:200]}")
d = js.screen_leg(m, receipt, "bp4.shadow")
print("SCREEN:", d["verdict"], "|", d["reason"])
for row in (d.get("jev") or {}).get("rows", []):
    p = {k: round(v, 2) for k, v in (row.get("p") or {}).items()}
    print(f"  row {row['i']}: {row['choice']} conf={row['confidence']} p={p}")
j = d.get("jev") or {}
print("  self_contradiction:", j.get("self_contradiction"), " crux_need:", j.get("crux_need"))
print("BRIEF LINE:", d["brief_line"])
