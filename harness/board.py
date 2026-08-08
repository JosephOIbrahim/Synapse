"""board.html - the finish board in a browser. No terminal needed.

    python harness/board.py            # write harness/notes/board.html once
    python harness/board.py --watch    # regenerate every 5s; page self-refreshes

Reads harness/legs.json states + receipt presence. Renders observed
states and counts only. UNKNOWN renders as UNKNOWN - never a number.
Open harness/notes/board.html in any browser (second monitor, kiosk tab).
"""
import json, re, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGS = ROOT / "harness" / "legs.json"
OUT = ROOT / "harness" / "notes" / "board.html"
RECEIPTS = ROOT / "harness" / "notes" / "receipts"

COLORS = {"done": "#1D9E75", "running": "#378ADD", "launched": "#378ADD",
          "ready": "#8A8A8A", "held": "#5A5A5A"}
ORDER = {"running": 0, "launched": 0, "ready": 1, "held": 2}
NOTES = ROOT / "harness" / "notes"

def live_states() -> dict:
    """Latest orchestrator board line -> {leg_id: state}. Empty if the
    newest log is older than 10 min (no run in flight = nothing live)."""
    logs = sorted(NOTES.glob("orchestrator_*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs or time.time() - logs[0].stat().st_mtime > 600:
        return {}
    board = None
    for line in logs[0].read_text(encoding="utf-8", errors="replace").splitlines():
        if "  board  " in line:
            board = line
    if not board:
        return {}
    return dict(re.findall(r"([\w-]+):(\w+)", board.split("  board  ", 1)[1]))

def render() -> str:
    data = json.loads(LEGS.read_text(encoding="utf-8"))
    legs = data.get("legs", [])
    live = live_states()

    def eff(l):
        if (RECEIPTS / l.get("receipt", "_")).exists():
            return "done"
        return live.get(l.get("id", ""), l.get("state", "UNKNOWN"))

    states = {l["id"]: eff(l) for l in legs}
    counts = {}
    for s in states.values():
        counts[s] = counts.get(s, 0) + 1
    active = [l for l in legs if states[l["id"]] != "done"]
    active.sort(key=lambda l: ORDER.get(states[l["id"]], 3))
    rows = []
    for l in active:
        st = states[l["id"]]
        c = COLORS.get(st, "#B45309")
        rows.append(
            f"<tr><td class='id'>{l['id']}</td><td class='nm'>{l.get('name','')}</td>"
            f"<td class='st' style='color:{c}'>{st}</td></tr>"
        )
    stamp = datetime.now().strftime("%H:%M:%S")
    src = "manifest + orchestrator + receipts" if live else "manifest + receipts (no live run)"
    return HEAD + (
        f"<p class='meta'>observed {stamp} &middot; {counts.get('done',0)} done &middot; "
        f"{counts.get('running',0)+counts.get('launched',0)} running &middot; "
        f"{counts.get('ready',0)} ready &middot; {counts.get('held',0)} held "
        f"&middot; {src} &middot; counts only, nothing estimated</p>"
        f"<table>{''.join(rows)}</table></body></html>"
    )

HEAD = """<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>SYNAPSE board</title><style>
body{background:#111;color:#ddd;font-family:Segoe UI,system-ui,sans-serif;
     max-width:640px;margin:2rem auto;padding:0 1rem}
h1{font-size:16px;font-weight:500;letter-spacing:.04em;margin:0}
.meta{font-size:12px;color:#888;margin:.4rem 0 1.2rem}
table{width:100%;border-collapse:collapse;font-size:14px}
td{padding:8px 4px;border-top:1px solid #2a2a2a}
.id{font-family:Consolas,monospace;font-weight:600;width:74px}
.nm{color:#aaa}
.st{text-align:right;font-size:12px;letter-spacing:.05em;white-space:nowrap}
</style></head><body><h1>SYNAPSE &middot; finish board</h1>"""

def main() -> None:
    watch = "--watch" in sys.argv
    while True:
        OUT.write_text(render(), encoding="utf-8")
        print(f"wrote {OUT}")
        if not watch:
            break
        time.sleep(5)

if __name__ == "__main__":
    main()
