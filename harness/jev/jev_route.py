# jev_route.py - JEV-ROUTE guard: mission -> tier, on the compile edge.
# Called by compile_wave.py when a mission carries "tier": "auto". A literal tier never
# reaches this file. Jev chooses among the tier NAMES in rails_exec.json; the policy in
# decide() turns three judgments into one tier and rounds up on doubt. Any failure ->
# policy.fallback_tier (reasoning), ledgered. Shadow CLI compares Jev to the author's tier.
# Source: harness/battleplan/notes/JEV_BLUEPRINT.md sec.3.1.
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402

REPO = jc.REPO
MISSIONS = REPO / "harness" / "battleplan" / "missions"


def route_state(m: dict, fields: list[str]) -> dict:
    return {"mission": {k: m[k] for k in fields if k in m}, "tiers": _tier_descriptions()}


def routable_tiers() -> dict:
    """rails tiers Jev may CHOOSE. BP9-NONETIER: a rails entry with "routable": false (the
    'none' probe tier, which launches no model) is literal-only - it never enters the Choice
    criteria, and a Jev answer naming it is treated as out-of-table by decide()."""
    return {name: e for name, e in jc.rails_tiers().items()
            if not (isinstance(e, dict) and e.get("routable") is False)}


def _tier_descriptions() -> dict:
    """routable rails names x questions.json descriptions. A tier without a description falls
    back to its rails `why`; a description without a tier is dropped. Names come from rails."""
    q = jc.load_questions()["guards"]["route"]["questions"]["tier"]["criteria_by_tier"]
    out = {}
    for name, entry in routable_tiers().items():
        out[name] = q.get(name) or {"what": entry.get("why", name)}
    return out


def route_spec(criteria: dict) -> dict:
    g = jc.load_questions()["guards"]["route"]["questions"]
    return {
        "tier": {"type": "choice", "instructions": g["tier"]["instructions"], "criteria": criteria},
        "novelty": {"type": "score", "instructions": g["novelty"]["instructions"], "criteria": g["novelty"]["criteria"]},
        "blast_radius": {"type": "score", "instructions": g["blast_radius"]["instructions"], "criteria": g["blast_radius"]["criteria"]},
    }


def decide(m: dict, answers: dict | None, policy: dict) -> dict:
    """Plain code. Returns {tier, reason, jev: {...}|None}."""
    fb = policy["fallback_tier"]
    if policy.get("crucible_is_referee") and m.get("band") == "TRUST" and m.get("class") == "crucible":
        return {"tier": "referee", "reason": "rule: TRUST/crucible is the referee seat", "jev": None}
    if answers is None:
        return {"tier": fb, "reason": "fallback: no Jev answer (see ledger)", "jev": None}
    t = answers["choices"].get("tier", {})
    choice, conf = t.get("choice"), t.get("confidence")
    nov = (answers["scores"].get("novelty") or {}).get("score")
    br = (answers["scores"].get("blast_radius") or {}).get("score")
    jev = {"tier": choice, "confidence": conf, "probabilities": t.get("probabilities"), "novelty": nov, "blast_radius": br}
    if choice not in routable_tiers():  # BP9-NONETIER: 'none' is in rails but never routable
        return {"tier": fb, "reason": f"fallback: Jev chose unknown tier {choice!r}", "jev": jev}
    if conf is None or conf < policy["min_tier_confidence"]:
        return {"tier": fb, "reason": f"round-up: tier confidence {conf} < {policy['min_tier_confidence']}", "jev": jev}
    if choice == "mechanical":
        if nov is not None and nov >= policy["mechanical_max_novelty"]:
            return {"tier": fb, "reason": f"round-up: novelty {nov:.2f} >= {policy['mechanical_max_novelty']}", "jev": jev}
        if br is not None and br >= policy["mechanical_max_blast_radius"]:
            return {"tier": fb, "reason": f"round-up: blast_radius {br:.2f} >= {policy['mechanical_max_blast_radius']}", "jev": jev}
    return {"tier": choice, "reason": f"jev: {choice} @ {conf:.2f}", "jev": jev}


def route_mission(m: dict, wave: str) -> dict:
    g = jc.load_questions()["guards"]["route"]
    policy = g["policy"]
    if policy.get("crucible_is_referee") and m.get("band") == "TRUST" and m.get("class") == "crucible":
        d = decide(m, None, policy)
        jc.ledger(wave, "route", {"leg": m["id"], "result": "rule", "decision": d})
        return d
    state = route_state(m, g["state_fields"])
    answers = jc.ask(state, route_spec(state["tiers"]), wave=wave, guard="route", leg=m["id"])
    d = decide(m, answers, policy)
    jc.ledger(wave, "route", {"leg": m["id"], "result": "decision", "author_tier": m.get("tier"), "decision": d})
    return d


def resolve_tier(m: dict, wave: str) -> str:
    """Entry point for compile_wave.py. Only ever called for tier == 'auto'."""
    return route_mission(m, wave)["tier"]


def _wave_of(mid: str) -> str:
    return mid.split("-", 1)[0].lower()


def shadow(wave: str) -> int:
    """Route every mission of a wave WITHOUT writing rows; print Jev vs author."""
    files = sorted(p for p in MISSIONS.glob("*.json") if p.stem.lower().startswith(wave.lower() + "-"))
    if not files:
        print(f"no missions for wave {wave} in {MISSIONS}")
        return 1
    rows, agree, n = [], 0, 0
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        d = route_mission(m, f"{wave}.shadow")
        author = m.get("tier", "-")
        same = (author == d["tier"])
        if author != "-":
            n += 1
            agree += int(same)
        j = d.get("jev") or {}
        rows.append((m["id"], author, d["tier"], "=" if same else "≠",
                     f"{j.get('confidence'):.2f}" if j.get("confidence") is not None else "-",
                     f"{j.get('novelty'):.2f}" if j.get("novelty") is not None else "-",
                     f"{j.get('blast_radius'):.2f}" if j.get("blast_radius") is not None else "-",
                     d["reason"]))
    w = max(len(r[0]) for r in rows)
    print(f"{'leg':{w}}  {'author':10} {'jev':10} {'':2} {'conf':5} {'nov':5} {'blast':5}  reason")
    for r in rows:
        print(f"{r[0]:{w}}  {r[1]:10} {r[2]:10} {r[3]:2} {r[4]:5} {r[5]:5} {r[6]:5}  {r[7]}")
    print(f"-- agreement {agree}/{n} on authored tiers; ledger: harness/jev/ledger/{wave}.shadow.route.jsonl")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", required=True, help="e.g. bp4")
    ap.add_argument("--shadow", action="store_true", help="route without writing rows (the only mode this CLI has)")
    a = ap.parse_args()
    sys.exit(shadow(a.wave))
