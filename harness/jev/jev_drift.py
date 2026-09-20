# jev_drift.py - JEV-DRIFT guard: is a running leg advancing, looping, or out of scope? (helm mile 4)
# SHADOW ONLY. This file never posts to the bus and never stops a leg: harness/battleplan/drift.py
# (regex, zero model calls) keeps the refocus/halt authority and the budget rails keep the hard stop.
# JEV-DRIFT only answers the semantic questions a regex cannot - "is it retrying the same step",
# "is it claiming files outside its touches" - and ledgers what it WOULD have warned, so the wave
# can grade it afterwards. Questions and thresholds: questions.json guards.drift (JEV_BLUEPRINT 3.3).
# Cadence (code, not judgment): a leg is judged only when it has >= MIN_NEW events since it was last
# judged, and never once it is closed - so calls scale with bus traffic, not with poll frequency.
# Source: harness/battleplan/notes/JEV_HELM.md (mile 4).
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "battleplan"))
import jev_client as jc  # noqa: E402

REPO = jc.REPO
MISSIONS = REPO / "harness" / "battleplan" / "missions"
RECEIPTS = REPO / "harness" / "notes" / "receipts"
WINDOW = 12     # bus events sent as state (questions.json: "last 12 bus events from this leg")
MIN_NEW = 3     # new events required before a leg is judged again
BODY_MAX = 400  # chars of each event body sent; a drift call must stay small


def drift_spec() -> dict:
    g = jc.load_questions()["guards"]["drift"]["questions"]
    return {k: {"type": "noul", "instructions": g[k]["instructions"]} for k in ("advancing", "looping", "out_of_scope")}


def leg_events(msgs: list, leg: str) -> list:
    return [m for m in msgs if m.get("frm") == leg or m.get("to") == leg]


def is_closed(msgs: list, leg: str, receipts: Path = RECEIPTS) -> bool:
    """Same closed-leg guards as drift.py: a finished session cannot be drifting."""
    if (receipts / f"{leg}.json").exists():
        return True
    for m in msgs:
        b = m.get("body") if isinstance(m.get("body"), dict) else {}
        if m.get("frm") == leg and (str(b.get("target", "")).upper() == "DONE" or (m.get("type") == "status" and b.get("release"))):
            return True
        if m.get("type") == "halt" and m.get("to") == leg:
            return True
    return False


def _closer(m: dict) -> bool:
    b = m.get("body") if isinstance(m.get("body"), dict) else {}
    return (m.get("type") == "halt" or str(b.get("target", "")).upper() == "DONE"
            or (m.get("type") == "status" and bool(b.get("release"))))


def strip_closers(msgs: list) -> list:
    """For replaying a FINISHED wave: without its closing markers, its legs read as open."""
    return [m for m in msgs if not _closer(m)]


def drift_state(m: dict, events: list) -> dict:
    ev = [{"ts": e.get("ts"), "type": e.get("type"), "from": e.get("frm"),
           "body": json.dumps(e.get("body"), ensure_ascii=False)[:BODY_MAX]} for e in events[-WINDOW:]]
    st = {"mission": {k: m.get(k) for k in ("id", "targets", "touches")}, "events": ev}
    try:
        t0, t1 = (datetime.fromisoformat(events[i]["ts"]) for i in (0, -1))
        st["elapsed_minutes"] = round((t1 - t0).total_seconds() / 60, 1)
    except Exception:  # noqa: BLE001 - an unparseable timestamp is UNKNOWN, not zero
        pass
    return st


def decide(answers: dict | None, previous: dict | None, policy: dict) -> dict:
    """Plain code. `previous` is the prior judgment's jev block for the same leg (or None).
    would_warn needs `consecutive_polls` (2) judgments in a row that both look like a loop."""
    if answers is None:
        return {"would_warn": False, "looks_looping": False, "reason": "fallback: no Jev answer (see ledger)", "jev": None}
    n = answers.get("nouls", {})
    adv, loop, scope = ((n.get(k) or {}).get("noul") for k in ("advancing", "looping", "out_of_scope"))
    jev = {"advancing": adv, "looping": loop, "out_of_scope": scope}
    looks = (loop is not None and adv is not None
             and loop >= policy["warn_looping_min"] and adv <= policy["warn_advancing_max"])
    jev["looks_looping"] = looks
    prev_looks = bool((previous or {}).get("looks_looping"))
    need = int(policy.get("consecutive_polls", 2))
    warn = looks and (need <= 1 or prev_looks)
    f = lambda v: "-" if v is None else f"{v:.2f}"  # noqa: E731
    why = f"advancing {f(adv)} looping {f(loop)} out_of_scope {f(scope)}"
    if looks and not warn:
        why += " - looks like a loop, waiting for a second judgment"
    return {"would_warn": warn, "looks_looping": looks, "reason": why, "jev": jev}


def _last_judgment(wave: str, leg: str) -> tuple[int, dict | None]:
    p = jc.LEDGER_DIR / f"{wave}.drift.jsonl"
    if not p.exists():
        return 0, None
    last = None
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("leg") == leg and r.get("result") == "decision":
            last = r
    return (last.get("n_events", 0), (last.get("decision") or {}).get("jev")) if last else (0, None)


def check(wave: str, msgs: list | None = None, receipts: Path = RECEIPTS) -> list:
    if msgs is None:
        import bus
        msgs = bus.read(wave)
    policy = jc.load_questions()["guards"]["drift"]["policy"]
    out = []
    for leg in sorted({m.get("frm") for m in msgs if str(m.get("frm", "")).upper().startswith(wave.upper() + "-")}):
        ev = leg_events(msgs, leg)
        seen, prev = _last_judgment(wave, leg)
        if is_closed(msgs, leg, receipts) or len(ev) - seen < MIN_NEW:
            continue
        mp = MISSIONS / f"{leg}.json"
        if not mp.exists():
            continue
        m = json.loads(mp.read_text(encoding="utf-8"))
        answers = jc.ask(drift_state(m, ev), drift_spec(), wave=wave, guard="drift", leg=leg)
        d = decide(answers, prev, policy)
        jc.ledger(wave, "drift", {"leg": leg, "result": "decision", "mode": "shadow", "n_events": len(ev), "decision": d})
        out.append({"leg": leg, **d})
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True)
    ap.add_argument("--bus-root", help="read a bus somewhere else (e.g. the main checkout) - read only")
    ap.add_argument("--ignore-closed", action="store_true", help="grade a FINISHED wave: judge legs even though they closed")
    a = ap.parse_args()
    try:
        import bus
        if a.bus_root:
            bus.BUS_ROOT = Path(a.bus_root)
        msgs = bus.read(a.wave)
        receipts = RECEIPTS
        if a.ignore_closed:  # replaying a finished wave: drop the closing markers so its legs get judged
            msgs, receipts = strip_closers(msgs), Path("__no_receipts__")
        res = check(a.wave, msgs, receipts)
        for r in res:
            print(f"{r['leg']:14} {'WOULD-WARN' if r['would_warn'] else 'ok':10} {r['reason']}")
        if not res:
            print("nothing to judge (no open leg with enough new events)")
    except Exception as e:  # noqa: BLE001 - a drift failure must never stop the orchestrator
        print(f"skipped: {type(e).__name__}: {e}"[:200])
    sys.exit(0)
