# test_jev_sweep.py - biting tests for the JEV-SWEEP guard (rope graph: scout candidate -> fix item).
# Same contract as the other guard tests: exact decisions, the reddening mutation named in each
# docstring, hermetic (no network, no key).
from __future__ import annotations

import sys
from pathlib import Path

JEV_DIR = Path(__file__).resolve().parents[1]
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))

import jev_client as jc  # noqa: E402
import jev_sweep as js  # noqa: E402

POLICY = jc.load_questions()["guards"]["sweep"]["policy"]
CAND = {"id": "S01-1", "file": "python/synapse/core/x.py", "blast": 0}


def _a(route="fix_now", conf=0.9, p_houdini=0.02, value=1.6, binary=0.9, tier="mechanical", tconf=0.9):
    return {"choices": {"route": {"choice": route, "confidence": conf,
                                  "probabilities": {route: conf, "needs_houdini": p_houdini}},
                        "tier": {"choice": tier, "confidence": tconf, "probabilities": {}}},
            "scores": {"value": {"score": value, "confidence": 0.9, "probabilities": {}}},
            "nouls": {"binary": {"noul": binary}}}


def test_a_clean_fix_now_is_routed_to_a_fixer_with_a_priority():
    """Mutation: return propose_only for everything -> the graph never fixes anything."""
    d = js.decide(CAND, _a(), POLICY)
    assert d["route"] == "fix_now" and d["tier"] == "mechanical"
    assert d["priority"] == round(1.6 * 0.9 * 0.9, 3)


def test_no_answer_falls_back_to_propose_only_never_to_a_fix():
    """Mutation: make the fallback fix_now -> a Jev outage starts editing code with no judgment."""
    d = js.decide(CAND, None, POLICY)
    assert d["route"] == POLICY["fallback_route"] == "propose_only"
    assert d["priority"] == 0.0


def test_a_code_veto_wins_before_jev_is_read():
    """Mutation: check answers before the veto -> a fenced file reaches a fixer on Jev's say-so."""
    d = js.decide({**CAND, "veto": "fenced"}, _a(), POLICY)
    assert d["route"] == "vetoed" and d["jev"] is None


def test_any_real_chance_of_houdini_rounds_down():
    """Mutation: drop houdini_wins_at -> a fix nobody can verify outside Houdini is made anyway."""
    assert js.decide(CAND, _a(p_houdini=0.40), POLICY)["route"] == "needs_houdini"
    assert js.decide(CAND, _a(p_houdini=0.10), POLICY)["route"] == "fix_now"
    assert js.decide({**CAND, "needs_houdini": True}, _a(), POLICY)["route"] == "needs_houdini"
    assert js.decide(CAND, _a(route="needs_houdini", conf=0.7), POLICY)["route"] == "needs_houdini"


def test_fix_now_that_misses_one_bar_becomes_propose_only():
    """Mutation: delete any one of the three bars -> an unjudgeable, worthless or doubtful fix is made."""
    assert js.decide(CAND, _a(conf=0.4), POLICY)["route"] == "propose_only"
    assert js.decide(CAND, _a(binary=0.3), POLICY)["route"] == "propose_only"
    assert js.decide(CAND, _a(value=0.2), POLICY)["route"] == "propose_only"
    assert js.decide(CAND, _a(binary=None), POLICY)["route"] == "propose_only"
    assert "binary" in js.decide(CAND, _a(binary=0.3), POLICY)["reason"]


def test_other_routes_pass_through_and_never_get_a_fixer():
    """Mutation: treat not_a_defect as fix_now -> the scout's misreading becomes a code change."""
    for r in ("propose_only", "not_a_defect"):
        d = js.decide(CAND, _a(route=r, conf=0.8), POLICY)
        assert d["route"] == r and d["tier"] is None and d["priority"] == 0.0
    assert js.decide(CAND, _a(route="delete_it"), POLICY)["route"] == "propose_only"


def test_tier_rounds_up_on_doubt_and_on_reach():
    """Mutation: round DOWN on tier doubt -> a change that needs judgment runs on the cheapest tier."""
    assert js.decide(CAND, _a(tier="mechanical", tconf=0.4), POLICY)["tier"] == "reasoning"
    assert js.decide(CAND, _a(tier="referee"), POLICY)["tier"] == "reasoning"   # not a fixer tier
    far = {**CAND, "blast": POLICY["mechanical_max_blast"] + 1}
    assert js.decide(far, _a(tier="mechanical"), POLICY)["tier"] == "reasoning"
    assert js.decide(CAND, _a(tier="reasoning"), POLICY)["tier"] == "reasoning"


def test_fixer_tier_names_come_from_rails_not_from_this_guard():
    """Mutation: hardcode the tier list -> a tier renamed in rails_exec.json is still offered to Jev."""
    assert set(js.fixer_tiers()) <= set(jc.rails_tiers())
    assert "referee" not in js.fixer_tiers()
    spec = js.sweep_spec()
    assert set(spec) == {"route", "value", "binary", "tier"}
    assert set(spec["route"]["criteria"]) == set(js.ROUTES)


def test_state_carries_only_the_listed_fields():
    """Mutation: send the whole candidate -> the veto and the decision leak into the question."""
    st = js.sweep_state({**CAND, "claim": "x", "veto": "", "decision": {"route": "fix_now"}})
    assert set(st["candidate"]) == {"id", "file", "blast", "claim"}
