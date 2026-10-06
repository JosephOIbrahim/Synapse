# jev_sweep.py - JEV-SWEEP guard: what happens to ONE candidate a scout brought back?
# Called by harness/rope/graph.py (route), between the scout wave and the fix wave of a graph run.
# Jev answers three things about a candidate: where it goes next (route), how much fixing it is
# worth (value), and whether a program could tell a right fix from a wrong one without Houdini
# (binary). It also picks the fixer's tier among the rails_exec.json tier NAMES.
# decide() is plain code, and Jev's answer is never the last word:
#   - a deterministic veto (fenced path, the exam, no evidence) is applied by the caller BEFORE Jev;
#   - DOUBT ROUNDS DOWN on the route: a real chance it needs Houdini means it is not fixed here,
#     and a fix_now that misses one bar becomes propose_only;
#   - DOUBT ROUNDS UP on the tier, as in jev_route: low confidence means the reasoning tier;
#   - no Jev answer means policy.fallback_route (propose_only), ledgered as a fallback.
# Jev routes and ranks. It never keeps a change: keep or discard belongs to the gate, by tests.
from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

ROUTES = ("fix_now", "needs_houdini", "propose_only", "not_a_defect")
GUARD = None  # a run may hand the guard in, for a tree whose questions.json predates this guard


def guard() -> dict:
    return GUARD or jc.load_questions()["guards"]["sweep"]


def fixer_tiers() -> dict:
    """rails tier NAMES a fixer may run on, with this guard's descriptions. Names come from rails."""
    desc = guard()["questions"]["tier"]["criteria_by_tier"]
    return {name: desc[name] for name in jc.rails_tiers() if name in desc}


def sweep_state(c: dict) -> dict:
    return {"candidate": {k: c[k] for k in guard()["state_fields"] if k in c}}


def sweep_spec() -> dict:
    q = guard()["questions"]
    return {
        "route": {"type": "choice", "instructions": q["route"]["instructions"], "criteria": q["route"]["criteria"]},
        "value": {"type": "score", "instructions": q["value"]["instructions"], "criteria": q["value"]["criteria"]},
        "binary": {"type": "noul", "instructions": q["binary"]["instructions"]},
        "tier": {"type": "choice", "instructions": q["tier"]["instructions"], "criteria": fixer_tiers()},
    }


def decide(c: dict, answers: dict | None, policy: dict) -> dict:
    """Plain code. Returns {route, tier, priority, reason, jev}."""
    fb_tier = policy["fallback_tier"]
    if c.get("veto"):
        return {"route": "vetoed", "tier": None, "priority": 0.0, "reason": "rule: " + str(c["veto"]), "jev": None}
    if answers is None:
        return {"route": policy["fallback_route"], "tier": fb_tier, "priority": 0.0,
                "reason": "fallback: no Jev answer (see ledger)", "jev": None}
    r = answers["choices"].get("route") or {}
    choice, conf, probs = r.get("choice"), r.get("confidence"), r.get("probabilities") or {}
    value = (answers["scores"].get("value") or {}).get("score")
    binary = (answers["nouls"].get("binary") or {}).get("noul")
    t = answers["choices"].get("tier") or {}
    jev = {"route": choice, "confidence": conf, "needs_houdini_p": probs.get("needs_houdini"),
           "value": value, "binary": binary, "tier": t.get("choice"), "tier_confidence": t.get("confidence")}
    if choice not in ROUTES:
        return {"route": policy["fallback_route"], "tier": fb_tier, "priority": 0.0,
                "reason": f"fallback: Jev chose unknown route {choice!r}", "jev": jev}
    p_h = probs.get("needs_houdini") or 0.0
    if c.get("needs_houdini") or choice == "needs_houdini" or p_h >= policy["houdini_wins_at"]:
        why = "the scout flagged it" if c.get("needs_houdini") else f"needs_houdini p={p_h:.2f}"
        return {"route": "needs_houdini", "tier": None, "priority": 0.0,
                "reason": f"round-down: {why}; not judged outside Houdini", "jev": jev}
    if choice != "fix_now":
        return {"route": choice, "tier": None, "priority": 0.0,
                "reason": f"jev: {choice} @ {conf if conf is None else round(conf, 2)}", "jev": jev}
    misses = []
    if conf is None or conf < policy["fix_min_confidence"]:
        misses.append(f"confidence {conf} < {policy['fix_min_confidence']}")
    if binary is None or binary < policy["fix_min_binary"]:
        misses.append(f"binary {binary} < {policy['fix_min_binary']}")
    if value is None or value < policy["fix_min_value"]:
        misses.append(f"value {value} < {policy['fix_min_value']}")
    if misses:
        return {"route": "propose_only", "tier": None, "priority": 0.0,
                "reason": "round-down: " + "; ".join(misses), "jev": jev}
    tier, tconf = t.get("choice"), t.get("confidence")
    if tier not in fixer_tiers() or tconf is None or tconf < policy["min_tier_confidence"]:
        tier, twhy = fb_tier, "tier round-up on doubt"
    elif tier != fb_tier and (c.get("blast") or 0) > policy["mechanical_max_blast"]:
        tier, twhy = fb_tier, f"tier round-up: {c.get('blast')} areas import this one"
    else:
        twhy = f"tier {tier} @ {tconf:.2f}"
    return {"route": "fix_now", "tier": tier, "priority": round(value * binary * conf, 3),
            "reason": f"jev: fix_now @ {conf:.2f}; {twhy}", "jev": jev}


def resolve(c: dict, wave: str, spec: dict | None = None) -> dict:
    """One candidate in, its decision out (also left on c['decision']). Never raises."""
    answers = None
    if not c.get("veto"):
        answers = jc.ask(sweep_state(c), spec or sweep_spec(), wave=wave, guard="sweep", leg=c["id"])
    d = decide(c, answers, guard()["policy"])
    jc.ledger(wave, "sweep", {"leg": c["id"], "result": "decision", "decision": d})
    c["decision"] = d
    return d


def resolve_many(cands: list, wave: str, workers: int = 4) -> list:
    """Route a wave of candidates. A few at a time; the ledger is written one row at a time."""
    if not cands:
        return []
    lock, plain = threading.Lock(), jc.ledger

    def locked(*a, **k):
        with lock:
            return plain(*a, **k)

    jc.ledger = locked
    try:
        spec = sweep_spec()
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            return list(ex.map(lambda c: resolve(c, wave, spec), cands))
    finally:
        jc.ledger = plain
