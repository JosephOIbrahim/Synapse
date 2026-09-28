"""BP11-SALIENCE T4 (harness): the JEV-SALIENCE shadow grader.

Hermetic: no network. ``jc.ask`` is monkeypatched, the ledger points at tmp_path.
Coverage:
  * code-order top-2 is the two lowest template-order parameters,
  * only groups with more than two survivors are graded,
  * with Jev access the grader ranks by Noul and can beat code order,
  * fail closed - no key or SYNAPSE_JEV=off -> the Jev side is UNKNOWN, never 0,
  * the grader asks the PRODUCT-OWNED question text (one question, one file),
  * the committed answer key clears the >=40 cases / >=10 types floor.
Every behavioural test names the mutation that reddens it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

JEV_DIR = Path(__file__).resolve().parents[1]  # harness/jev
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))

import jev_salience as js  # noqa: E402


def _case(ctx, tname, parm, order, matters, typ="Float"):
    return {"context": ctx, "node_type": tname, "node_category": ctx, "parm": parm,
            "parm_label": parm.upper(), "parm_type": typ, "parm_help": "",
            "template_order": order,
            "hash_changed": "b" if matters else "a", "hash_default": "a",
            "matters": matters}


def _group3():
    # order 0 = A (bookkeeping, matters False), 1 = B (matters), 2 = C (matters)
    return [_case("Sop", "demo", "a", 0, False),
            _case("Sop", "demo", "b", 1, True),
            _case("Sop", "demo", "c", 2, True)]


def _scorer(by_label):
    def ask(state, spec, **kw):
        return {"choices": {}, "scores": {},
                "nouls": {js.psal.QID: {"noul": by_label.get(state["parameter_label"], 0.0)}}}
    return ask


def _last_ledger(tmp_path):
    rows = [json.loads(x) for x in
            (tmp_path / "bp11.salience.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows[-1]


# ------------------------------------------------------------------- unit: code order
def test_code_top2_is_lowest_template_order():
    """Mutation: sort _code_top2 by -template_order -> the bubble's real first-two flips
    -> RED."""
    assert js._code_top2(_group3()) == ["a", "b"]


# -------------------------------------------------------------- only >2 survivors grade
def test_two_param_group_is_not_graded(tmp_path, monkeypatch):
    """Mutation: change MIN_GROUP to 2 -> a group with no top-2 choice is 'graded' -> RED
    (a row appears for it)."""
    monkeypatch.setattr(js.jc, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(js, "load_key", lambda: {"build": "t", "summary": {"n_cases": 2},
                        "cases": [_case("Sop", "two", "a", 0, True), _case("Sop", "two", "b", 1, False)]})
    monkeypatch.setattr(js.jc, "enabled", lambda: False)
    assert js.grade(shadow=True) == 0
    assert _last_ledger(tmp_path)["gradeable_groups"] == 0


# ----------------------------------------------------------- jev access: can beat code
def test_jev_ranks_by_noul_and_beats_code(tmp_path, monkeypatch):
    """With access, Jev's top-2 are the two highest Nouls. Mutation: rank Jev by +noul
    ascending -> Jev picks the bookkeeping parm -> loses -> RED."""
    monkeypatch.setattr(js.jc, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(js, "load_key", lambda: {"build": "t", "summary": {"n_cases": 3}, "cases": _group3()})
    monkeypatch.setattr(js.psal.adapter, "resolve_key", lambda: "test-key")
    monkeypatch.setattr(js.jc, "enabled", lambda: True)
    # A low, B and C high -> jev picks B,C (both matter); code picks A,B (one matters).
    monkeypatch.setattr(js.jc, "ask", _scorer({"A": 0.1, "B": 0.9, "C": 0.8}))
    assert js.grade(shadow=True) == 0
    row = _last_ledger(tmp_path)
    assert row["code_agree"] == "1/2"
    assert row["jev_agree"] == "2/2"
    assert row["jev_wins"] == 1


# --------------------------------------------------------------- fail closed => UNKNOWN
def test_no_access_is_unknown_never_zero(tmp_path, monkeypatch):
    """SYNAPSE_JEV=off / no key -> Jev side UNKNOWN, never 0. Mutation: make the grader
    write jev_agree='0/0' when access is absent -> RED."""
    monkeypatch.setattr(js.jc, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(js, "load_key", lambda: {"build": "t", "summary": {"n_cases": 3}, "cases": _group3()})
    monkeypatch.setattr(js.jc, "enabled", lambda: False)  # Jev disabled

    def _boom(*a, **k):
        raise AssertionError("ask() must not be called when Jev has no access")

    monkeypatch.setattr(js.jc, "ask", _boom)
    assert js.grade(shadow=True) == 0
    row = _last_ledger(tmp_path)
    assert row["jev_agree"] == "UNKNOWN"
    assert row["jev_wins"] is None
    assert row["code_agree"] == "1/2"  # code order is deterministic from the key


def test_missing_key_file_is_unknown_not_a_crash(tmp_path, monkeypatch):
    """Mutation: let load_key raise instead of returning None -> the grader crashes
    instead of reporting UNKNOWN -> RED."""
    monkeypatch.setattr(js.jc, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(js, "load_key", lambda: None)
    assert js.grade(shadow=True) == 0
    assert _last_ledger(tmp_path)["reason"] == "no_key_file"


# -------------------------------------------------- one question text in one file
def test_grader_uses_the_product_owned_question_text():
    """The grader asks exactly the product's Noul, read from the product file - not a
    harness copy. Mutation: duplicate the instructions into guards.salience and read
    those -> two sources of truth -> this test (text equality) still holds but the
    _comment/text_source contract below breaks -> RED."""
    product = json.loads((JEV_DIR.parents[1] / "python" / "synapse" / "identify"
                          / "salience_questions.json").read_text(encoding="utf-8"))
    batch = js.psal.question_batch()
    assert batch[js.psal.QID]["instructions"] == product["question"]["instructions"]
    guards = js.jc.load_questions()["guards"]["salience"]["questions"]["salient"]
    assert guards["type"] == "noul"
    assert "instructions" not in guards  # text lives only in the product file
    assert guards["text_source"].endswith("salience_questions.json")


# --------------------------------------------------------------- committed key floor
def test_committed_key_clears_the_floor():
    """The real answer key holds >=40 cases across >=10 node types. Mutation: shrink the
    fixture -> RED (and the check-evidence in the receipt would be false)."""
    key = js.load_key()
    assert key is not None
    cases = key["cases"]
    assert len(cases) >= 40
    assert len({(c["context"], c["node_type"]) for c in cases}) >= 10
    assert key["producer"].startswith("hython ")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
