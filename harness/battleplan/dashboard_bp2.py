# dashboard_bp2.py - BP2 progress board for docs/BATTLEPLAN.md (2026-09-01).
# OBSERVED STATES ONLY: leg phase from manifest state + worktree + branch ahead-count +
# receipt presence + bus activity; rails ledger (integers or the literal UNKNOWN);
# bus tail; orchestrator liveness; git position; the sec.1 demo-readiness ledger
# (authored rows stay authored until an artifact upgrades them); the WORD checklist.
# Writes harness/battleplan/board_bp2.html (auto-refresh 30 s) and prints a text board.
# Reads only; never dispatches, never flips anything. UNKNOWN renders as UNKNOWN.
# Run: python harness/battleplan/dashboard_bp2.py            (once)
#      python harness/battleplan/dashboard_bp2.py --watch    (every 30 s)
#      python harness/battleplan/dashboard_bp2.py --open     (once, then opens the html)
import json, subprocess, sys, time, html, re, os
from datetime import datetime, date
from pathlib import Path

REPO = Path(r"C:\Users\User\SYNAPSE")
BP = REPO / "harness" / "battleplan"
WAVE = "bp2"
ROWS = BP / "waves" / f"{WAVE}.rows.json"
LIVE = BP / "waves" / f"{WAVE}.live.json"
BUS = BP / "bus" / WAVE / "bus.jsonl"
LOG = REPO / "harness" / "notes" / "h22" / f"orchestrator-{WAVE}.log"
PID = REPO / "harness" / "notes" / "h22" / f"orchestrator-{WAVE}.pid"
FLAG = REPO / "harness" / "notes" / "h22" / "BP2_CRUX_LANDED.flag"
RECEIPTS = REPO / "harness" / "notes" / "receipts"
VERDICTS = BP / "notes" / "BP2-CRUX_verdicts.md"
OUT = BP / f"board_{WAVE}.html"
UNKNOWN = "UNKNOWN"

PAIRS = {"BP2-METER": "pair 1", "BP2-PANELTRUTH": "pair 1", "BP2-LATENCY": "pair 2",
         "BP2-STORE": "pair 2", "BP2-PANELDESIGN": "solo (Wed word)", "BP2-CRUX": "solo (referee)"}

def git(*a):
    r = subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True)
    return r.stdout.strip()

def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default

def pid_alive():
    if not PID.exists():
        return None, False
    pid = PID.read_text().strip()
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"if (Get-CimInstance Win32_Process -Filter 'ProcessId={pid}') {{'1'}} else {{'0'}}"],
                       capture_output=True, text=True).stdout.strip()
    return pid, r == "1"

def bus_messages():
    if not BUS.exists():
        return []
    out = []
    for ln in BUS.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out

def leg_rows():
    rows = load_json(ROWS, []) or []
    live = {l["id"]: l for l in (load_json(LIVE, {}) or {}).get("legs", [])}
    msgs = bus_messages()
    verdicts = VERDICTS.read_text(encoding="utf-8") if VERDICTS.exists() else ""
    pid, alive = pid_alive()
    receipts_present = set()
    out = []
    for r in rows:
        lid = r["id"]
        tag = lid.split("-", 1)[1].lower()
        wt = REPO / ".claude" / "worktrees" / lid.lower()
        rec = (RECEIPTS / f"{lid}.json").exists() or (wt / "harness" / "notes" / "receipts" / f"{lid}.json").exists()
        if rec:
            receipts_present.add(lid)
        ahead = git("rev-list", "--count", f"master..{WAVE}/{tag}") if git("rev-parse", "--verify", "-q", f"{WAVE}/{tag}") else ""
        mine = [m for m in msgs if m.get("frm") == lid]
        prog = [m for m in mine if m.get("type") == "progress"]
        last_prog = prog[-1] if prog else None
        blocks = sum(1 for m in mine if m.get("type") == "block")
        findings = sum(1 for m in mine if m.get("type") == "finding")
        refocus = sum(1 for m in msgs if m.get("to") == lid and m.get("type") == "refocus")
        mstate = live.get(lid, {}).get("state", r.get("state", "ready")) if live else "unarmed"
        v = ""
        if verdicts:
            mv = re.search(rf"{re.escape(lid)}[^\n]*?\b(SOUND-WITH-NITS|SOUND|BROKEN)\b", verdicts)
            v = mv.group(1) if mv else ""
        out.append({"id": lid, "pair": PAIRS.get(lid, ""), "mstate": mstate, "deps": r.get("deps", []),
                    "worktree": wt.exists(), "ahead": ahead, "receipt": rec, "verdict": v,
                    "progress": last_prog, "n_progress": len(prog), "blocks": blocks,
                    "findings": findings, "refocus": refocus, "readonly": r.get("readonly", False)})
    for o in out:
        deps_missing = [d for d in o["deps"] if d not in receipts_present]
        if o["mstate"] == "unarmed":
            phase = "unarmed"
        elif o["mstate"] == "held":
            phase = "held"
        elif o["receipt"]:
            phase = "receipted" if not o["verdict"] else f"receipted · {o['verdict']}"
        elif o["worktree"] or (o["ahead"] not in ("", "0")) or o["n_progress"]:
            phase = "working"
        elif deps_missing:
            phase = "blocked"
        else:
            phase = "ready"
        o["phase"] = phase
        o["deps_missing"] = deps_missing
    return out, (pid, alive)

def rails_ledger():
    # live orchestrator ledgers only: rails run ids are orch_<yyyymmdd-hhmmss>; BP1's proof
    # copies (ledger_orch_budget_halt.json) and the dry-run copy do not match, and the
    # wave started 2026-09-01 so older run dirs are BP1's.
    leds = [p for p in sorted((BP / "runs").glob("*/ledger_orch_*.json"))
            if re.fullmatch(r"ledger_orch_\d{8}-\d{6}\.json", p.name) and p.parent.name >= "2026-09-01"]
    if not leds:
        return None
    led = load_json(leds[-1], {}) or {}
    led["_path"] = str(leds[-1].relative_to(REPO))
    return led

def latency_artifact():
    hits = sorted((BP / "runs").glob("*/memory_latency_*.json"))
    return [str(h.relative_to(REPO)) for h in hits]

# sec.1 demo-readiness ledger. Authored status (2026-09-01) unless an artifact upgrades it.
DEMO = [
    (1, "Build .400 pinned; launch-path env bucket closed", "GREEN", "receipt 08-31"),
    (2, "v5.58.0 published, CI green", "GREEN", "release 08-31"),
    (3, "In-session deposit + recall in GUI", "GREEN", "silent_recall_gui.json"),
    (4, "Cross-session round-trip on camera x2", "UNMEASURED", "your hands - 18:00 predicate"),
    (5, "Recall never silent (honesty contract)", "AMBER", "flips ride your word"),
    (6, "Memory latency inside a stated camera budget", "UNKNOWN", "BP2-LATENCY"),
    (7, "Repeat deposits don't corrupt the store (FU-1)", "RED", "BP2-STORE"),
    (8, "Panel opens docked; no float hijack", "RED", "BP2-PANELTRUTH T3 + your eyes"),
    (9, "Profiles visibly differ; switch persists", "UNKNOWN", "BP2-PANELTRUTH T1"),
    (10, "TOKEN readout updates per task", "RED", "BP2-PANELTRUTH T2"),
    (11, "Panel spacing at the Cohere rhythm (camera regions)", "RED", "BP2-PANELDESIGN (held)"),
    (12, "Harness spend measured in tokens, caps enforceable", "RED", "BP2-METER"),
    (13, "60-second narrative + rough cut", "RED", "Thu"),
    (14, "Full dry run", "RED", "Sun"),
]

def demo_rows(legs, led):
    by = {l["id"]: l for l in legs}
    rows = []
    for n, item, status, ev in DEMO:
        s, e = status, ev
        if n == 6 and latency_artifact():
            s, e = "MEASURED", ", ".join(latency_artifact())
        if n == 12 and led and any(isinstance(l.get("tokens_in"), int) for l in led.get("legs", [])):
            s, e = "MEASURED", led["_path"]
        for k, leg in ((7, "BP2-STORE"), (9, "BP2-PANELTRUTH"), (10, "BP2-PANELTRUTH")):
            if n == k and by.get(leg, {}).get("verdict", "").startswith("SOUND"):
                s, e = "RECEIPTED · merge word pending", f"{leg} {by[leg]['verdict']}"
        rows.append((n, item, s, e))
    return rows

def words(legs, pid_alive_):
    ahead_origin = git("rev-list", "--count", "origin/master..master") or UNKNOWN
    head = git("rev-parse", "--short=8", "HEAD")
    pid, alive = pid_alive_
    receipted = [l["id"] for l in legs if l["receipt"]]
    return [
        ("push", f"master {head} is {ahead_origin} ahead of origin/master" if ahead_origin != "0" else "nothing to push", ahead_origin != "0"),
        ("arm BP2 pairs 1+2", f"orchestrator pid {pid} ALIVE" if alive else ("pid file present, process DEAD" if pid else "not armed - `powershell -File harness\\battleplan\\arm_bp2.ps1`"), not alive),
        ("ratify sec.2 calls 7 (Curious on camera) + 8 (latency budgets)", "pending - override by number", True),
        ("read CRUX verdicts -> merge words", ("flag LANDED - " + FLAG.read_text().strip()) if FLAG.exists() else f"CRUX not landed; receipts present: {', '.join(receipted) or 'none'}", not FLAG.exists()),
        ("ratify memory-recall-honesty flips", "after reading BP1-HONESTY receipts", True),
        ("v5.57.0 draft - publish or delete", "your call", True),
        ("Wed: flip BP2-PANELDESIGN held -> ready (build_manifest_bp2.py HELD) and re-arm", "after PANELTRUTH is merged", True),
    ]

def miles():
    today = date.today()
    wk = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 8}
    mile = wk.get(today.weekday(), UNKNOWN)
    return mile, today.strftime("%a %Y-%m-%d")

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,500&family=Archivo:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--paper:#F4F1EA;--ink:#1A1917;--muted:#6F6A60;--hair:#D9D3C6;--card:#FBF9F4;--acc:#D6462B;--ok:#3F5F45}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Archivo,system-ui,sans-serif;padding:40px 48px 64px}
h1{font:300 40px/1.05 Fraunces,Georgia,serif;margin:0 0 4px;letter-spacing:-.01em}h1 em{font-style:normal;color:var(--acc)}
.pos{font:500 12px/1 'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:10px 0 28px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:36px}
.kpi{background:var(--card);border:1px solid var(--hair);border-radius:10px;padding:16px}
.kpi .l{font:500 11px/1 'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.kpi .v{font:300 34px/1.1 Fraunces,serif;margin-top:10px}.kpi .s{font:12px/1.4 'JetBrains Mono',monospace;color:var(--muted);margin-top:6px}
h2{font:500 11px/1 'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:32px 0 12px;padding-bottom:12px;border-bottom:1px solid var(--hair)}
table{width:100%;border-collapse:collapse}td,th{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--hair)}
th{font:500 11px/1 'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:500}
td.m{font:13px/1.4 'JetBrains Mono',monospace}td.mu{color:var(--muted)}
.pill{display:inline-block;font:500 11px/1 'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.06em;padding:6px 10px;border-radius:999px;border:1px solid var(--hair);background:var(--card);white-space:nowrap}
.pill.hot{border-color:var(--acc);color:var(--acc)}.pill.ok{border-color:var(--ok);color:var(--ok)}.pill.dim{color:var(--muted)}
.mile{display:flex;gap:6px;margin:6px 0 0}.mile i{display:block;width:34px;height:6px;border-radius:3px;background:var(--hair)}.mile i.done{background:var(--ink)}.mile i.now{background:var(--acc)}
.log{font:12px/1.6 'JetBrains Mono',monospace;background:var(--card);border:1px solid var(--hair);border-radius:10px;padding:14px 16px;white-space:pre-wrap;color:var(--muted)}
.foot{margin-top:40px;font:12px/1.5 'JetBrains Mono',monospace;color:var(--muted)}
"""

def pill(text):
    t = str(text)
    cls = "pill"
    if any(k in t for k in ("RED", "BROKEN", "blocked", "DEAD", "halt", "UNMEASURED")):
        cls += " hot"
    elif any(k in t for k in ("GREEN", "SOUND", "receipted", "MEASURED", "ALIVE", "done", "RECEIPTED")):
        cls += " ok"
    elif any(k in t for k in ("UNKNOWN", "held", "unarmed", "pending", "AMBER")):
        cls += " dim"
    return f'<span class="{cls}">{html.escape(t)}</span>'

def render_html(legs, pidinfo, led, bus_tail, demo, wds, mile, today):
    e = html.escape
    pid, alive = pidinfo
    receipted = sum(1 for l in legs if l["receipt"])
    green = sum(1 for _, _, s, _ in demo if s.startswith(("GREEN", "MEASURED", "RECEIPTED")))
    turns = f"{led['totals']['turns']} / {led['cap']['turns']}" if led else "not armed"
    tokens = (f"in {led['totals']['tokens_in']} · out {led['totals']['tokens_out']}") if led else UNKNOWN
    unit = led.get("enforced_unit", UNKNOWN) if led else "turns (dispatches)"
    dots = "".join(f'<i class="{"now" if i == mile else ("done" if isinstance(mile, int) and i < mile else "")}"></i>' for i in range(1, 9))
    h = [f"<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='30'><title>BP2 board</title><style>{CSS}</style></head><body>"]
    h.append(f"<h1>SYNAPSE · Battle Plan <em>BP2</em></h1>")
    h.append(f"<div class='pos'>demo week · mile {mile} of 8 · {e(today)} · generated {datetime.now().strftime('%H:%M:%S')} · observed states only · UNKNOWN is a measurement</div>")
    h.append(f"<div class='mile'>{dots}</div>")
    h.append("<div class='kpis' style='margin-top:28px'>")
    h.append(f"<div class='kpi'><div class='l'>legs receipted</div><div class='v'>{receipted} <span style='color:var(--muted)'>/ {len(legs)}</span></div><div class='s'>{e(', '.join(l['id'][4:] for l in legs if l['receipt']) or 'none yet')}</div></div>")
    h.append(f"<div class='kpi'><div class='l'>rails · {e(unit)}</div><div class='v'>{e(turns)}</div><div class='s'>a rails turn = one leg dispatch (sec.12 R-3)</div></div>")
    h.append(f"<div class='kpi'><div class='l'>tokens</div><div class='v' style='font-size:22px;margin-top:16px'>{e(tokens)}</div><div class='s'>integers only after METER's settle lands</div></div>")
    h.append(f"<div class='kpi'><div class='l'>demo-ready</div><div class='v'>{green} <span style='color:var(--muted)'>/ 14</span></div><div class='s'>sec.1 ledger · count, don't feel</div></div>")
    h.append("</div>")
    h.append("<h2>Legs</h2><table><tr><th>leg</th><th>lane</th><th>phase</th><th>manifest</th><th>deps</th><th>branch ahead</th><th>bus</th><th>last progress</th></tr>")
    for l in legs:
        lp = l["progress"]
        lp_txt = f"{lp['ts'][11:16]} {json.dumps(lp.get('body'))[:60]}" if lp else "-"
        deps = ", ".join(d[4:] + ("" if d not in l["deps_missing"] else " ✕") for d in l["deps"]) or "-"
        bus_txt = f"{l['findings']} findings · {l['blocks']} blocks · {l['refocus']} refocus"
        h.append(f"<tr><td class='m'>{e(l['id'])}</td><td class='mu'>{e(l['pair'])}</td><td>{pill(l['phase'])}</td><td class='m mu'>{e(l['mstate'])}</td><td class='m mu'>{e(deps)}</td><td class='m'>{e(l['ahead'] or '-')}</td><td class='m mu'>{e(bus_txt)}</td><td class='m mu'>{e(lp_txt)}</td></tr>")
    h.append("</table>")
    if led:
        h.append(f"<h2>Rails ledger · {e(led['_path'])}</h2><table><tr><th>leg</th><th>model</th><th>tokens in</th><th>tokens out</th><th>wall ms</th><th>admitted</th></tr>")
        for r in led.get("legs", []):
            h.append(f"<tr><td class='m'>{e(r.get('leg',''))}</td><td class='m mu'>{e(r.get('model',''))}</td><td class='m'>{e(str(r.get('tokens_in',UNKNOWN)))}</td><td class='m'>{e(str(r.get('tokens_out',UNKNOWN)))}</td><td class='m'>{e(str(r.get('wall_ms',UNKNOWN)))}</td><td>{pill('admitted' if r.get('admitted') else 'REFUSED')}</td></tr>")
        h.append(f"</table><div class='foot'>status {e(str(led.get('status')))} · reason {e(str(led.get('reason','-')))} · remaining turns {e(str(led.get('remaining',{}).get('turns')))} · remaining tokens {e(str(led.get('remaining',{}).get('tokens')))}</div>")
    h.append("<h2>Bus · last 12 (finding / block / refocus / halt / spawn / progress)</h2>")
    if bus_tail:
        h.append("<table><tr><th>ts</th><th>from</th><th>to</th><th>type</th><th>body</th></tr>")
        for m in bus_tail:
            h.append(f"<tr><td class='m mu'>{e(m['ts'][5:16])}</td><td class='m'>{e(m['frm'])}</td><td class='m mu'>{e(m.get('to','*'))}</td><td>{pill(m['type'])}</td><td class='m mu'>{e(json.dumps(m.get('body'), ensure_ascii=False)[:160])}</td></tr>")
        h.append("</table>")
    else:
        h.append("<div class='log'>bus empty - wave not started</div>")
    h.append("<h2>Demo-readiness · sec.1 ledger</h2><table><tr><th>#</th><th>item</th><th>status</th><th>evidence / owner</th></tr>")
    for n, item, s, ev in demo:
        h.append(f"<tr><td class='m mu'>{n}</td><td>{e(item)}</td><td>{pill(s)}</td><td class='m mu'>{e(ev)}</td></tr>")
    h.append("</table><h2>Words · yours, per act</h2><table><tr><th>word</th><th>observed</th><th></th></tr>")
    for w, obs, open_ in wds:
        h.append(f"<tr><td>{e(w)}</td><td class='m mu'>{e(obs)}</td><td>{pill('open' if open_ else 'done')}</td></tr>")
    h.append("</table><h2>Orchestrator</h2>")
    tail = "\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]) if LOG.exists() else "no orchestrator-bp2.log yet"
    h.append(f"<div class='log'>pid {e(str(pid))} {'ALIVE' if alive else ('DEAD' if pid else 'not armed')}\n{e(tail)}</div>")
    h.append(f"<div class='foot'>docs/BATTLEPLAN.md 2026-09-01 · harness/battleplan/dashboard_bp2.py · reads only · refresh 30 s</div></body></html>")
    return "\n".join(h)

def render_text(legs, pidinfo, led, bus_tail, demo, wds, mile, today):
    pid, alive = pidinfo
    lines = [f"== BP2 board - demo week mile {mile} of 8 - {today} - {datetime.now().strftime('%H:%M:%S')} ==",
             f"orchestrator: pid {pid} {'ALIVE' if alive else ('DEAD' if pid else 'not armed')}"]
    for l in legs:
        deps = ",".join(d[4:] + ("" if d not in l["deps_missing"] else "!") for d in l["deps"]) or "-"
        lines.append(f"  {l['id']:16s} {l['phase']:26s} manifest={l['mstate']:8s} deps={deps:24s} ahead={l['ahead'] or '-':>3s} "
                     f"bus f{l['findings']}/b{l['blocks']}/r{l['refocus']} progress={l['n_progress']}")
    if led:
        lines.append(f"rails: {led['_path']} status={led.get('status')} unit={led.get('enforced_unit')} "
                     f"turns={led['totals']['turns']}/{led['cap']['turns']} tokens_in={led['totals']['tokens_in']} tokens_out={led['totals']['tokens_out']}")
    else:
        lines.append("rails: no live ledger (not armed)")
    lines.append(f"bus: {len(bus_tail)} recent")
    for m in bus_tail[-6:]:
        lines.append(f"  {m['ts'][11:16]} {m['frm']:>16s} -> {m.get('to','*'):16s} {m['type']:9s} {json.dumps(m.get('body'), ensure_ascii=False)[:90]}")
    green = sum(1 for _, _, s, _ in demo if s.startswith(("GREEN", "MEASURED", "RECEIPTED")))
    lines.append(f"demo-ready: {green}/14 - " + " ".join(f"#{n}:{s.split()[0]}" for n, _, s, _ in demo))
    lines.append("words open: " + " | ".join(w for w, _, o in wds if o))
    return "\n".join(lines)

def once():
    legs, pidinfo = leg_rows()
    led = rails_ledger()
    msgs = [m for m in bus_messages() if m.get("type") in ("finding", "block", "refocus", "halt", "spawn", "progress", "status")]
    bus_tail = msgs[-12:]
    demo = demo_rows(legs, led)
    wds = words(legs, pidinfo)
    mile, today = miles()
    OUT.write_text(render_html(legs, pidinfo, led, bus_tail, demo, wds, mile, today), encoding="utf-8")
    txt = render_text(legs, pidinfo, led, bus_tail, demo, wds, mile, today)
    print(txt)
    print(f"html: {OUT}")
    return txt

if __name__ == "__main__":
    if "--watch" in sys.argv:
        while True:
            once()
            time.sleep(30)
    else:
        once()
        if "--open" in sys.argv:
            os.startfile(str(OUT))
