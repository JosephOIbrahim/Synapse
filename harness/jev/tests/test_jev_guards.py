# test_jev_guards.py - the tests that make the JEV guard seam unbreakable-silently.
# Every test here BITES: it asserts an exact decision (tier / verdict / fail-closed
# behaviour), so a broken guard reddens it. The mutation that reddens each test is named
# in its docstring and copied into the receipt (BP6-JEV T1). Coverage:
#   (a) jev_route.decide + jev_screen.decide, one test per policy branch in questions.json
#   (b) a recorded fixture (a real ledger row) drives jev_client._answers_to_dict
#   (c) a raising TypeSafeClient -> ask() returns None AND writes a fallback ledger row
#   (d) SYNAPSE_JEV=off -> ask() returns None without importing the SDK
# Pure + hermetic: decide() tests make no call; ask() tests monkeypatch the SDK and point
# the ledger at tmp_path, so nothing here touches the network or the real ledger.
# Source: harness/battleplan/notes/JEV_BLUEPRINT.md sec.3-4.
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

JEV_DIR = Path(__file__).resolve().parents[1]  # harness/jev
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))

import jev_client as jc  # noqa: E402
import jev_route  # noqa: E402
import jev_screen  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

_Q = jc.load_questions()
ROUTE_POLICY = _Q["guards"]["route"]["policy"]
SCREEN_POLICY = _Q["guards"]["screen"]["policy"]

BUILD_M = {"band": "BUILD", "class": "build"}  # a non-crucible mission stub


# --------------------------------------------------------------------------- helpers
def _route_answers(choice, conf, novelty=0.0, blast=0.0):
    return {
        "choices": {"tier": {"choice": choice, "confidence": conf, "probabilities": {}}},
        "scores": {
            "novelty": {"score": novelty, "confidence": 0.9, "probabilities": {}},
            "blast_radius": {"score": blast, "confidence": 0.9, "probabilities": {}},
        },
        "nouls": {},
    }


def _screen_answers(rows, self_contra=0.10, crux_need=0.30):
    """rows: list of (choice, confidence, does_not_support_prob)."""
    choices = {}
    for i, (ch, cf, dns) in enumerate(rows):
        choices[f"acc_{i}"] = {
            "choice": ch,
            "confidence": cf,
            "probabilities": {"supports": max(0.0, 1.0 - dns), "does_not_support": dns,
                              "partial": 0.0, "claims_unknown": 0.0},
        }
    return {
        "choices": choices,
        "scores": {"crux_need": {"score": crux_need, "confidence": 0.5, "probabilities": {}}},
        "nouls": {"self_contradiction": {"noul": self_contra}},
    }


# --------------------------------------------------------------- (a) route.decide branches
def test_route_crucible_rule():
    """Mutation: in jev_route.decide change `m.get("class") == "crucible"` to `== "cricket"`
    (or delete `crucible_is_referee` from questions.json) -> returns the fallback tier, not
    'referee' -> RED."""
    d = jev_route.decide({"band": "TRUST", "class": "crucible"}, None, ROUTE_POLICY)
    assert d["tier"] == "referee"
    assert d["jev"] is None
    assert "referee seat" in d["reason"]


def test_route_none_answer_falls_back():
    """None->fallback. Mutation: change `if answers is None:` to `if answers is not None:`
    -> the guard no longer rounds up when Jev could not answer -> RED."""
    d = jev_route.decide(BUILD_M, None, ROUTE_POLICY)
    assert d["tier"] == ROUTE_POLICY["fallback_tier"] == "reasoning"
    assert d["jev"] is None
    assert "no Jev answer" in d["reason"]


def test_route_unknown_tier_falls_back():
    """Mutation: delete the `if choice not in jc.rails_tiers(): return fallback` block
    (or add 'quantum' to rails_exec.json) -> Jev's out-of-table tier is honoured -> RED."""
    d = jev_route.decide(BUILD_M, _route_answers("quantum", 0.99), ROUTE_POLICY)
    assert d["tier"] == "reasoning"
    assert "unknown tier" in d["reason"]
    assert d["jev"]["tier"] == "quantum"  # the raw judgment is still recorded, never trusted


def test_route_low_confidence_rounds_up():
    """round-up on low confidence. Mutation: delete `min_tier_confidence` from questions.json
    route.policy (KeyError) or change `conf < policy[...]` to `conf < 0` -> a low-confidence
    cheap route is accepted -> RED."""
    d = jev_route.decide(BUILD_M, _route_answers("mechanical", 0.50), ROUTE_POLICY)
    assert d["tier"] == "reasoning"
    assert "tier confidence" in d["reason"]


def test_route_high_novelty_rounds_up():
    """round-up on novelty. Mutation: change `nov >= policy["mechanical_max_novelty"]` to
    `nov >= 99` -> a novel leg is routed to Haiku -> RED."""
    d = jev_route.decide(BUILD_M, _route_answers("mechanical", 0.95, novelty=2.0, blast=0.0), ROUTE_POLICY)
    assert d["tier"] == "reasoning"
    assert "novelty" in d["reason"]


def test_route_high_blast_radius_rounds_up():
    """round-up on blast_radius. Mutation: change `br >= policy["mechanical_max_blast_radius"]`
    to `br >= 99` -> a product-touching leg is routed to Haiku -> RED."""
    d = jev_route.decide(BUILD_M, _route_answers("mechanical", 0.95, novelty=0.0, blast=2.0), ROUTE_POLICY)
    assert d["tier"] == "reasoning"
    assert "blast_radius" in d["reason"]


def test_route_honours_confident_low_risk_choice():
    """The positive path: Jev's choice IS honoured when confident and low-risk, so the guard
    is not vacuously always-fallback. Mutation: change the final `return {"tier": choice ...}`
    to `return {"tier": fb ...}` -> mechanical is never chosen -> RED."""
    d = jev_route.decide(BUILD_M, _route_answers("mechanical", 0.95, novelty=0.5, blast=0.5), ROUTE_POLICY)
    assert d["tier"] == "mechanical"
    assert d["reason"].startswith("jev:")
    assert d["jev"]["confidence"] == 0.95


# -------------------------------------------------------------- (a) screen.decide branches
def test_screen_flag_on_does_not_support():
    """FLAG. Mutation: change the `p.get("does_not_support",0) >= policy["flag_does_not_support_min"]`
    threshold to `>= 2.0` (or delete the key) -> a contradicted row is not flagged -> RED."""
    d = jev_screen.decide(1, _screen_answers([("does_not_support", 0.70, 0.70)]), SCREEN_POLICY)
    assert d["verdict"] == "FLAG"
    assert d["rows"] == [0]


def test_screen_clear_when_all_supported():
    """CLEAR. Mutation: raise `clear_min_support_confidence` to 0.99 (or delete
    `clear_max_crux_need`) in questions.json -> a clean receipt no longer clears -> RED."""
    d = jev_screen.decide(2, _screen_answers([("supports", 0.90, 0.03), ("supports", 0.88, 0.03)],
                                             self_contra=0.10, crux_need=0.30), SCREEN_POLICY)
    assert d["verdict"] == "CLEAR"
    assert d["rows"] == []


def test_screen_referee_on_weak_row():
    """REFEREE. Mutation: lower `clear_min_support_confidence` to 0.0 -> a thin-evidence row
    silently clears instead of going to the referee -> RED."""
    d = jev_screen.decide(1, _screen_answers([("supports", 0.55, 0.05)]), SCREEN_POLICY)
    assert d["verdict"] == "REFEREE"
    assert d["rows"] == [0]


def test_screen_none_answer_falls_back_to_referee():
    """None->fallback. Mutation: change `if answers is None:` to `is not None` -> a screen
    that could not run defaults to less-than-full referee attention -> RED."""
    d = jev_screen.decide(3, None, SCREEN_POLICY)
    assert d["verdict"] == SCREEN_POLICY["fallback_verdict"] == "REFEREE"
    assert d["jev"] is None
    assert "no Jev answer" in d["reason"]


# ------------------------------------------------- (b) recorded fixture drives _answers_to_dict
def test_recorded_fixture_drives_answers_to_dict():
    """The SDK response contract, pinned by a real ledger row (bp4.shadow.route.jsonl,
    BP4-B7FIX). Mutation: in jev_client._answers_to_dict read `_get(a,"value")` instead of
    `_get(a,"choice")` (or rename any flattened field) -> the round-trip drops the tier and
    decide() falls back -> RED."""
    fx = json.loads((FIXTURES / "route_answer.json").read_text(encoding="utf-8"))
    flat = jc._answers_to_dict(fx)  # a recorded SDK shape, re-flattened
    assert flat["choices"]["tier"]["choice"] == "reasoning"
    assert flat["choices"]["tier"]["confidence"] == 0.99
    assert flat["scores"]["novelty"]["score"] == 0.93
    assert flat["scores"]["blast_radius"]["score"] == 1.02
    assert flat["request_id"] == "req_01a0bc716e3d7dba9423fdccde3d5bf1"
    # and the flattened answer must still drive decide() to honour the recorded tier
    d = jev_route.decide(BUILD_M, flat, ROUTE_POLICY)
    assert d["tier"] == "reasoning"
    assert d["reason"].startswith("jev:")


# ----------------------------------------------------------- (c) fail-closed: SDK raises
class _RaisingClient:
    def __init__(self, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def system_one(self, **kw):
        raise RuntimeError("simulated SDK failure")


def test_ask_sdk_raises_returns_none_and_ledgers_fallback(tmp_path, monkeypatch):
    """Fail closed on an SDK error. Mutation: remove the `try/except Exception` around the
    SDK call in ask() (let it raise) OR make the except `return answers` without ledgering
    -> ask() raises / writes no fallback row -> RED."""
    monkeypatch.setattr(jc, "LEDGER_DIR", tmp_path)
    monkeypatch.setenv("SYNAPSE_JEV", "on")
    monkeypatch.setattr(jc, "api_key", lambda: "test-key")
    _mk = lambda **kw: dict(kw)  # noqa: E731 - stand-in Choice/Score/Noul
    monkeypatch.setattr(jc, "_sdk", lambda: (_RaisingClient, _mk, _mk, _mk))

    res = jc.ask({"x": 1}, {"q": {"type": "noul", "instructions": "?"}},
                 wave="t", guard="route", leg="T")

    assert res is None
    rows = [json.loads(x) for x in (tmp_path / "t.route.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert rows, "ask() must write a ledger row even on failure"
    assert rows[-1]["result"] == "fallback"
    assert "RuntimeError" in rows[-1]["reason"]


# ------------------------------------------------------ (d) fail-closed: SYNAPSE_JEV=off
def test_ask_disabled_returns_none_without_importing_sdk(tmp_path, monkeypatch):
    """SYNAPSE_JEV=off short-circuits before the SDK is ever imported. Mutation: change
    `if not enabled():` to `if enabled():` (or make enabled() always True) -> ask() reaches
    _sdk(), which raises AssertionError here -> RED."""
    monkeypatch.setattr(jc, "LEDGER_DIR", tmp_path)
    monkeypatch.setenv("SYNAPSE_JEV", "off")

    def _boom():
        raise AssertionError("the SDK must not be imported when SYNAPSE_JEV=off")

    monkeypatch.setattr(jc, "_sdk", _boom)

    res = jc.ask({"x": 1}, {"q": {"type": "noul", "instructions": "?"}},
                 wave="t", guard="route", leg="T")

    assert res is None
    rows = [json.loads(x) for x in (tmp_path / "t.route.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert rows and rows[-1]["result"] == "disabled"
    assert rows[-1]["reason"] == "SYNAPSE_JEV=off"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
