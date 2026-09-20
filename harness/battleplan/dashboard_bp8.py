# dashboard_bp8.py - BP8 progress board (2026-09-20). Same contract as dashboard_bp4.py:
# OBSERVED STATES ONLY. Leg state comes from the orchestrator's own last `board` line; commits from
# git; receipts from the leg worktrees; spend from the rails ledger (integers or the literal UNKNOWN);
# Jev guard activity from harness/jev/ledger/bp8.*.jsonl. Reads only; never dispatches, never flips
# anything. UNKNOWN renders as UNKNOWN - never a guess, never a 0.
# Writes harness/battleplan/board_bp8.html (auto-refresh 30 s) and prints a one-line text board.
# Run: python harness/battleplan/dashboard_bp8.py            (once)
#      python harness/battleplan/dashboard_bp8.py --watch    (every 30 s)
#      python harness/battleplan/dashboard_bp8.py --open     (once, then opens the html)
import html, json, os, re, statistics, subprocess, sys, time
from datetime import datetime
from pathlib import Path

REPO = Path(r"C:\Users\User\SYNAPSE")
BP = REPO / "harness" / "battleplan"
WAVE = "bp8"
OUT = BP / f"board_{WAVE}.html"
LOG = REPO / "harness" / "notes" / "h22" / f"orchestrator-{WAVE}.log"
PID = REPO / "harness" / "notes" / "h22" / f"orchestrator-{WAVE}.pid"
LEDGERS = REPO / "harness" / "jev" / "ledger"
UNKNOWN = "UNKNOWN"
sys.path.insert(0, str(BP))


def git(*a, cwd=REPO):
    try:
        return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return ""


def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def pid_alive():
    try:
        pid = int(PID.read_text().strip())
    except Exception:
        return None, False
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return pid, str(pid) in out


def log_lines():
    try:
        return LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []


def board_states(lines):
    for ln in reversed(lines):
        if "  board  " in ln:
            return dict(re.findall(r"(BP\d+-[A-Z0-9]+):(\w+)", ln)), ln[:8]
    return {}, UNKNOWN


def bus_messages():
    try:
        import bus
        return bus.read(WAVE)
    except Exception:
        return []


def age(ts):
    try:
        m = int((datetime.now() - datetime.fromisoformat(ts)).total_seconds() // 60)
        return f"{m} min ago" if m < 120 else f"{m // 60} h ago"
    except Exception:
        return UNKNOWN


def leg_rows(manifest, states, msgs):
    rows = []
    for leg in (manifest or {}).get("legs", []):
        wt = REPO / leg["worktree"]
        ahead = git("rev-list", "--count", f"master..{leg['branch']}") if git("rev-parse", "--verify", "-q", leg["branch"]) else ""
        rc = load_json(wt / "harness" / "notes" / "receipts" / leg["receipt"]) or load_json(REPO / "harness" / "notes" / "receipts" / leg["receipt"])
        mine = [m for m in msgs if m.get("frm") == leg["id"]]
        last = mine[-1] if mine else None
        body = last.get("body") if last and isinstance(last.get("body"), dict) else {}
        rows.append({
            "id": leg["id"], "tier": leg.get("tier", "-"), "state": states.get(leg["id"], leg.get("state", UNKNOWN)),
            "deps": ", ".join(d.split("-", 1)[1] for d in leg.get("deps", [])) or "none",
            "commits": ahead if ahead != "" else ("-" if not wt.exists() else UNKNOWN),
            "receipt": (rc or {}).get("status", "none yet") if rc is not None else "none yet",
            "bus": f"{last.get('type')}: {str(body.get('target') or body.get('claim') or json.dumps(last.get('body'), ensure_ascii=False))[:60]} ({age(last.get('ts', ''))})" if last else "no events yet",
            "inserted": leg.get("inserted_by") == "jev-edge"})
    return rows


def rails():
    """The live run's ledger = the rails run id the orchestrator log announced ('rails open orch_...')."""
    run = None
    for ln in log_lines():
        m = re.search(r"rails open (orch_[\d-]+)", ln)
        if m:
            run = m.group(1)
    if not run:
        return None, UNKNOWN
    for p in (BP / "runs").glob(f"*/ledger_{run}.json"):
        return load_json(p), p.name
    return None, UNKNOWN


def guard_rows():
    out = []
    for p in sorted(LEDGERS.glob(f"{WAVE}.*.jsonl")):
        rows = [r for r in (load_line(l) for l in p.read_text(encoding="utf-8", errors="replace").splitlines()) if r]
        calls = [r for r in rows if r.get("result") == "ok"]
        lat = [r["latency_ms"] for r in calls if isinstance(r.get("latency_ms"), (int, float))]
        dec = [r for r in rows if r.get("result") == "decision"]
        last = dec[-1] if dec else None
        d = (last or {}).get("decision") or {}
        summary = d.get("reason") or d.get("brief_line") or d.get("shape") or d.get("tier") or "-"
        out.append({"guard": p.name[len(WAVE) + 1:-6], "calls": len(calls),
                    "fallbacks": sum(1 for r in rows if r.get("result") == "fallback"),
                    "median_ms": int(statistics.median(lat)) if lat else UNKNOWN,
                    "last": f"{(last or {}).get('leg', '-')}: {str(summary)[:90]}" if last else "no decision yet"})
    return out


def load_line(l):
    try:
        return json.loads(l)
    except Exception:
        return None


def words(states, alive):
    ahead = git("rev-list", "--count", "origin/master..master") or UNKNOWN
    done = [k for k, v in states.items() if v == "done"]
    return [
        ("GUI repro: send two messages in the panel, watch the spinner 35 s (BP7_VERDICT.md)", "yours - decides the held memory-store leg"),
        ("BP7-PANEL stuck at closing; two BP7 leg sessions still alive", "yours - pin done in bp7.live.json, or leave"),
        (f"master is {ahead} commit(s) ahead of origin", "push is your word"),
        (f"merge of bp8 leg branches ({len(done)}/{len(states) or 4} legs done)", "after CRUX verdicts - your word"),
        ("orchestrator " + ("alive" if alive else "NOT running"), "observed"),
    ]


E = html.escape
STATE_CLASS = {"done": "ok", "launched": "run", "running": "run", "closing": "warn", "blocked": "wait", "ready": "wait", "held": "wait"}


def render():
    manifest = load_json(BP / "waves" / f"{WAVE}.live.json")
    lines = log_lines()
    states, board_ts = board_states(lines)
    msgs = bus_messages()
    legs = leg_rows(manifest, states, msgs)
    pid, alive = pid_alive()
    led, led_name = rails()
    guards = guard_rows()
    n = len(legs) or 4
    done = sum(1 for l in legs if l["state"] == "done")
    running = sum(1 for l in legs if l["state"] in ("launched", "running", "closing"))
    cap = (led or {}).get("cap", {})
    tot = (led or {}).get("totals", {})
    turns = f"{tot.get('turns', UNKNOWN)} / {cap.get('turns', UNKNOWN)}"
    tin, tout = tot.get("tokens_in", UNKNOWN), tot.get("tokens_out", UNKNOWN)
    # The rails total stays UNKNOWN while ANY dispatched leg is unmeasured (correct: no estimates).
    # The per-leg numbers that ARE measured can still be summed, as long as it is labelled partial.
    rl = (led or {}).get("legs", [])
    settled = [l for l in rl if isinstance(l.get("tokens_in"), int) and isinstance(l.get("tokens_out"), int)]
    measured = sum(l["tokens_in"] + l["tokens_out"] for l in settled)
    if UNKNOWN not in (tin, tout):
        tok, measured = f"{(tin + tout) / 1e6:.1f}M", tin + tout
    elif settled:
        tok = f"{measured / 1e6:.1f}M so far ({len(settled)} of {len(rl)} dispatched legs measured)"
    else:
        tok = UNKNOWN
    tok_pct = 0 if not measured or not cap.get("tokens") else min(100, round(measured / cap["tokens"] * 100))
    headline = f"{done} of {n} legs done, {running} running. Budget: {turns} dispatches, {tok} of {cap.get('tokens', 0) / 1e6:.0f}M tokens measured."
    text = f"[{datetime.now():%H:%M:%S}] BP8  " + "  ".join(f"{l['id'].split('-')[1]}:{l['state']}" for l in legs) + f"  | turns {turns} | tokens {tok} | orch {'alive' if alive else 'DOWN'}"

    def table(head, rows):
        return "<table><thead><tr>" + "".join(f"<th>{E(h)}</th>" for h in head) + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"

    leg_html = table(["Leg", "State", "Tier", "Waits on", "Commits", "Receipt", "Last bus event"], [
        f"<tr><td class='mono'>{E(l['id'])}{' <span class=tag>inserted</span>' if l['inserted'] else ''}</td>"
        f"<td><span class='pill {STATE_CLASS.get(l['state'], 'wait')}'>{E(l['state'])}</span></td><td>{E(l['tier'])}</td>"
        f"<td>{E(l['deps'])}</td><td class='num'>{E(str(l['commits']))}</td><td>{E(str(l['receipt']))}</td><td class='dim'>{E(l['bus'])}</td></tr>"
        for l in legs]) if legs else "<p class='dim'>No live manifest found.</p>"
    guard_html = table(["Guard", "Jev calls", "Fallbacks", "Median latency", "Last decision"], [
        f"<tr><td class='mono'>{E(g['guard'])}</td><td class='num'>{g['calls']}</td><td class='num'>{g['fallbacks']}</td>"
        f"<td class='num'>{E(str(g['median_ms']))}{' ms' if g['median_ms'] != UNKNOWN else ''}</td><td class='dim'>{E(g['last'])}</td></tr>"
        for g in guards]) if guards else "<p class='dim'>No bp8 guard ledgers yet.</p>"
    miles = [("1", "SHAPE", "live"), ("2", "TEAM", "live"), ("3", "EDGE", "shadow"), ("4", "DRIFT", "shadow"),
             ("5", "BP8 wave", "done" if done == n else "running" if alive else "stopped")]
    mile_html = "".join(f"<div class='mile {E(s)}'><b>{E(k)}</b><span>{E(name)}</span><i>{E(s)}</i></div>" for k, name, s in miles)
    bus_html = "".join(f"<li><span class='dim'>{E(str(m.get('ts', ''))[11:19])}</span> <b>{E(str(m.get('frm')))}</b> {E(str(m.get('type')))} "
                       f"<span class='dim'>{E(json.dumps(m.get('body'), ensure_ascii=False)[:120])}</span></li>" for m in msgs[-8:]) or "<li class='dim'>No bus events yet.</li>"
    word_html = "".join(f"<li><span>{E(a)}</span><em>{E(b)}</em></li>" for a, b in words(states, alive))
    log_html = E("\n".join(lines[-8:])) or "no log yet"

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="30">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>BP8 Board</title><style>
:root{{--bg:#0f1214;--panel:#171c20;--line:#262e35;--text:#e6eaed;--dim:#8a97a3;--ok:#5fcf9a;--run:#6cb6ff;--warn:#f0b35a;--wait:#5d6b78;--accent:#c9a7ff}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{--bg:#f6f7f8;--panel:#fff;--line:#dfe4e8;--text:#182026;--dim:#5f6d7a;--ok:#1d8a57;--run:#1c6fd1;--warn:#a96a08;--wait:#8794a0;--accent:#6b3fc4}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 "Segoe UI",system-ui,sans-serif;padding:24px 16px}}
main{{max-width:1080px;margin:0 auto;display:grid;gap:16px}}h1{{font-size:20px;margin:0;letter-spacing:.02em}}h2{{font-size:12px;margin:0 0 10px;color:var(--dim);text-transform:uppercase;letter-spacing:.09em;font-weight:600}}
.top{{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}}.dim{{color:var(--dim)}}.mono,pre{{font-family:"Cascadia Mono",Consolas,monospace;font-size:13px}}
.headline{{font-size:18px;line-height:1.45}}section{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse;min-width:640px}}th{{text-align:left;font-size:12px;color:var(--dim);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--line)}}
td{{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}}tr:last-child td{{border-bottom:0}}.num{{text-align:right;font-variant-numeric:tabular-nums}}
.pill{{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;border:1px solid currentColor}}.ok{{color:var(--ok)}}.run{{color:var(--run)}}.warn{{color:var(--warn)}}.wait{{color:var(--wait)}}
.tag{{font-size:11px;color:var(--accent);border:1px solid var(--accent);border-radius:4px;padding:0 5px;margin-left:6px}}
.miles{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}}.mile{{border:1px solid var(--line);border-radius:8px;padding:10px;display:grid;gap:2px}}.mile b{{font-size:12px;color:var(--dim)}}.mile i{{font-style:normal;font-size:12px}}
.mile.live i,.mile.done i{{color:var(--ok)}}.mile.shadow i{{color:var(--accent)}}.mile.running i{{color:var(--run)}}.mile.stopped i{{color:var(--warn)}}
.bar{{height:8px;background:var(--line);border-radius:99px;overflow:hidden;margin-top:8px}}.bar>div{{height:100%;background:var(--run);width:{tok_pct}%}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}@media (max-width:760px){{.two,.miles{{grid-template-columns:1fr}}}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:8px}}.words li{{display:grid;gap:2px}}.words em{{font-style:normal;color:var(--dim);font-size:13px}}pre{{margin:0;white-space:pre-wrap;color:var(--dim)}}
</style></head><body><main>
<div class="top"><h1>BP8 &middot; act on the BP7 verdict</h1><span class="dim mono">{datetime.now():%Y-%m-%d %H:%M:%S} &middot; refreshes every 30 s &middot; orchestrator pid {pid or UNKNOWN} {'alive' if alive else 'NOT RUNNING'} &middot; master {E(git('rev-parse', '--short=8', 'HEAD') or UNKNOWN)}</span></div>
<section><h2>You are here</h2><div class="headline">{E(headline)}</div><div class="bar"><div></div></div>
<p class="dim" style="margin:8px 0 0">Tokens are measured from leg transcripts when a leg closes. Until then they read UNKNOWN, never an estimate. Board line read at {E(board_ts)}. Ledger: {E(led_name)}.</p></section>
<section><h2>Helm miles</h2><div class="miles">{mile_html}</div></section>
<section><h2>Legs</h2>{leg_html}</section>
<section><h2>Jev guards on this wave</h2>{guard_html}<p class="dim" style="margin:10px 0 0">EDGE and DRIFT run in shadow: they record what they would have done and change nothing. Compare them with CRUX's verdicts after the wave.</p></section>
<div class="two"><section><h2>Waiting on your word</h2><ul class="words">{word_html}</ul></section>
<section><h2>Bus, last 8</h2><ul class="mono">{bus_html}</ul></section></div>
<section><h2>Orchestrator log, last 8 lines</h2><pre>{log_html}</pre></section>
</main></body></html>"""
    OUT.write_text(page, encoding="utf-8")
    return text


if __name__ == "__main__":
    if "--watch" in sys.argv:
        while True:
            print(render(), flush=True)
            time.sleep(30)
    print(render())
    print(f"board: {OUT}")
    if "--open" in sys.argv:
        os.startfile(OUT)  # noqa: S606 - local file, Windows
