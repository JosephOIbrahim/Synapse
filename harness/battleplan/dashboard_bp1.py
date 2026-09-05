# dashboard_bp1.py - BP1 live board. Observed states only: leg phase from branch +
# worktree + receipt presence, bus tail, orchestrator liveness + log tail, ledgers.
# Writes harness/battleplan/board.html (auto-refresh 10s) and prints the same board.
# UNKNOWN renders as UNKNOWN - never zero, never an estimate. Reads only; never dispatches.
# Run: python harness/battleplan/dashboard_bp1.py [--once]   (watch_bp1.ps1 opens the html)
import json, subprocess, sys, time, html
from pathlib import Path

REPO = Path(r"C:\Users\User\SYNAPSE")
BP = REPO / "harness" / "battleplan"
ROWS = BP / "waves" / "bp1.rows.json"
BUS = BP / "bus" / "bp1" / "bus.jsonl"
LOG = REPO / "harness" / "notes" / "h22" / "orchestrator-bp1.log"
PID = REPO / "harness" / "notes" / "h22" / "orchestrator-bp1.pid"
RECEIPTS = REPO / "harness" / "notes" / "receipts"
OUT = BP / "board.html"

def git(*a):
    r = subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True)
    return r.stdout.strip()

def leg_state(r):
    wt = REPO / r["worktree"]
    branch_exists = git("rev-parse", "--verify", "--quiet", r["branch"]) != ""
    ahead = git("rev-list", "--count", f"master..{r['branch']}") if branch_exists else "UNKNOWN"
    rec = next((p for p in (RECEIPTS / r["receipt"], wt / "harness" / "notes" / "receipts" / r["receipt"]) if p.exists()), None)
    if rec:
        try:
            status = json.loads(rec.read_text(encoding="utf-8")).get("status", "UNKNOWN")
        except Exception:
            status = "UNKNOWN(unparsed)"
        phase = f"RECEIPT {status}"
    elif branch_exists and wt.exists():
        phase = "RUNNING"
    elif branch_exists:
        phase = "branch, no worktree"
    elif r["deps"]:
        phase = "blocked on " + ", ".join(d.split("-", 1)[1] for d in r["deps"])
    else:
        phase = "ready"
    return {"id": r["id"], "phase": phase, "ahead": ahead, "worktree": "yes" if wt.exists() else "no",
            "readonly": "ro" if r.get("readonly") else "rw"}

def bus_tail(n=8):
    if not BUS.exists():
        return 0, ["(bus: 0 lines yet)"]
    lines = [l for l in BUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for l in lines[-n:]:
        try:
            m = json.loads(l)
            body = m.get("body")
            body = json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body
            out.append(f"{m.get('ts','')[11:16]}  {m.get('frm','?'):<12} {m.get('type','?'):<8} -> {m.get('to','*'):<12} {body[:96]}")
        except Exception:
            out.append(l[:120])
    return len(lines), out

def orchestrator():
    alive = "not armed"
    if PID.exists():
        pid = PID.read_text().strip()
        found = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
        alive = f"live pid {pid}" if pid in found else f"DEAD (pid {pid} gone)"
    tail = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-8:] if LOG.exists() else ["(no orchestrator log yet)"]
    return alive, tail

def ledgers():
    runs = BP / "runs"
    found = sorted(runs.glob("*/ledger_*.json")) if runs.exists() else []
    return [str(p.relative_to(REPO)) for p in found[-3:]] or ["(no ledger yet - RAILS not landed)"]

def render():
    rows = json.loads(ROWS.read_text(encoding="utf-8"))
    legs = [leg_state(r) for r in rows]
    n_bus, bus = bus_tail()
    alive, olog = orchestrator()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    master = git("rev-parse", "--short=8", "master")
    return legs, n_bus, bus, alive, olog, ledgers(), stamp, master

CSS = ("body{background:#F7F4EE;color:#111;font:15px/1.5 'Archivo','Helvetica Neue',Arial,sans-serif;margin:0;padding:40px 56px}"
       "h1{font:600 26px/1.2 'Fraunces',Georgia,serif;margin:0 0 4px}.sub{color:#666;margin:0 0 32px;font-size:13px}"
       "table{border-collapse:collapse;width:100%;margin:0 0 36px}th{text-align:left;font-size:11px;letter-spacing:.12em;"
       "text-transform:uppercase;color:#666;padding:0 12px 10px 0;border-bottom:1px solid #111}td{padding:12px 12px 12px 0;"
       "border-bottom:1px solid #ddd;font-family:'JetBrains Mono',Consolas,monospace;font-size:14px}"
       ".hot{color:#F15A24;font-weight:600}.dim{color:#888}h2{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#666;margin:0 0 10px}"
       "pre{background:#fff;border:1px solid #ddd;padding:14px 16px;font:13px/1.55 'JetBrains Mono',Consolas,monospace;white-space:pre-wrap;margin:0 0 32px}")

def to_html(legs, n_bus, bus, alive, olog, leds, stamp, master):
    hot = ("RUNNING", "RECEIPT")
    tr = "".join(f"<tr><td>{l['id']}</td><td class='{'hot' if l['phase'].startswith(hot) else ('dim' if l['phase'].startswith('blocked') else '')}'>"
                 f"{html.escape(l['phase'])}</td><td>{l['ahead']}</td><td>{l['worktree']}</td><td class='dim'>{l['readonly']}</td></tr>" for l in legs)
    esc = lambda xs: html.escape("\n".join(xs))
    return (f"<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='10'><title>BP1 board</title>"
            f"<style>{CSS}</style></head><body><h1>SYNAPSE &middot; BP1 battle plan</h1>"
            f"<p class='sub'>observed {stamp} &middot; master {master} &middot; orchestrator {html.escape(alive)} &middot; bus {n_bus} lines &middot; UNKNOWN renders as UNKNOWN</p>"
            f"<table><tr><th>leg</th><th>phase</th><th>ahead</th><th>worktree</th><th></th></tr>{tr}</table>"
            f"<h2>bus tail</h2><pre>{esc(bus)}</pre><h2>orchestrator</h2><pre>{esc(olog)}</pre>"
            f"<h2>ledgers</h2><pre>{esc(leds)}</pre></body></html>")

def print_board(legs, n_bus, bus, alive, olog, leds, stamp, master):
    print(f"== BP1 board  {stamp}  master {master}  orchestrator {alive}  bus {n_bus} ==")
    for l in legs:
        print(f"  {l['id']:<13} {l['phase']:<28} ahead {l['ahead']:<8} wt {l['worktree']:<4} {l['readonly']}")
    print("  -- bus --");  [print("  " + b) for b in bus]
    print("  -- orchestrator --");  [print("  " + o) for o in olog[-4:]]
    print("  -- ledgers --");  [print("  " + x) for x in leds]

def main():
    once = "--once" in sys.argv
    while True:
        data = render()
        OUT.write_text(to_html(*data), encoding="utf-8")
        print_board(*data)
        if once:
            return 0
        time.sleep(10)
        print()

if __name__ == "__main__":
    sys.exit(main())
