"""JEV-BENCH policy tests (BP10-BENCH T3). Pure Python: no key, no hou. The policy is code,
so it is tested with synthetic Jev answers -- including the crucible's planted false success."""
from __future__ import annotations

import json
import sys
from pathlib import Path

JEV = Path(__file__).resolve().parents[1]  # harness/jev
sys.path.insert(0, str(JEV))
import jev_bench as jb  # noqa: E402

POLICY = {"refused_unsupported_min": 0.7, "confidence_floor": 0.6,
          "unknown_verdict": "UNKNOWN", "other_verdict": "FAIL"}


def _ans(choice, probs, conf, named=None):
    return {"choices": {"failure_kind": {"choice": choice, "probabilities": probs, "confidence": conf}},
            "nouls": {"named_a_limitation": {"noul": named}}, "scores": {}}


def test_no_answer_is_unjudged_fail_not_unknown():
    d = jb.decide(None, POLICY)
    assert d["verdict"] == "FAIL" and d["kind"] == "unjudged"  # absence never fabricates UNKNOWN


def test_low_confidence_is_cannot_tell_never_unknown():
    # refused prob is high, but confidence is below the floor -> must NOT be promoted to UNKNOWN
    d = jb.decide(_ans("refused_unsupported", {"refused_unsupported": 0.95}, 0.40), POLICY)
    assert d["verdict"] == "FAIL" and d["kind"] == "cannot_tell"


def test_refused_high_confidence_is_unknown():
    d = jb.decide(_ans("refused_unsupported", {"refused_unsupported": 0.85}, 0.85, named=0.8), POLICY)
    assert d["verdict"] == "UNKNOWN" and d["kind"] == "refused_unsupported"


def test_attempted_failure_is_fail_with_kind():
    d = jb.decide(_ans("attempted_and_failed", {"attempted_and_failed": 0.82, "refused_unsupported": 0.03}, 0.82), POLICY)
    assert d["verdict"] == "FAIL" and d["kind"] == "attempted_and_failed"


def test_planted_false_success_is_flagged_claimed_success():
    # crucible: an arm that SAYS "done" on a failing scene is labelled claimed_success and stays a FAIL
    d = jb.decide(_ans("claimed_success", {"claimed_success": 0.9, "refused_unsupported": 0.02}, 0.9), POLICY)
    assert d["verdict"] == "FAIL" and d["kind"] == "claimed_success"


def test_refused_just_below_threshold_is_fail():
    d = jb.decide(_ans("refused_unsupported", {"refused_unsupported": 0.69}, 0.75), POLICY)
    assert d["verdict"] == "FAIL"  # 0.69 < 0.70 -> not an unsupported-context UNKNOWN


def test_leak_threshold(monkeypatch, tmp_path):
    seq = iter([
        {"nouls": {"hints_a_tool_or_arm": {"noul": 0.9}}},   # a: leaks
        {"nouls": {"hints_a_tool_or_arm": {"noul": 0.1}}},   # b: clean
        None,                                                 # c: fallback (no key)
    ])
    monkeypatch.setattr(jb.jc, "ask", lambda *a, **k: next(seq))
    monkeypatch.setattr(jb.jc, "ledger", lambda *a, **k: None)
    p = tmp_path / "p.jsonl"
    p.write_text("\n".join(json.dumps({"id": x, "prompt": "plain creative intent"}) for x in ["a", "b", "c"]),
                 encoding="utf-8")
    s = jb.leak_check(p, wave="test", threshold=0.5)
    assert s["leaked"] == ["a"]
    assert s["fallbacks"] == 1
    assert s["measured"] == 2


def test_bench_spec_reads_questions_json():
    # the classifier questions are DATA in questions.json guards.bench (scaffolded)
    spec = jb.bench_spec()
    assert set(spec) == {"failure_kind", "named_a_limitation"}
    assert spec["failure_kind"]["type"] == "choice"
    assert "refused_unsupported" in spec["failure_kind"]["criteria"]
