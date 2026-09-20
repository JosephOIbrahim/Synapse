# test_jev_drift.py - biting tests for the JEV-DRIFT guard (helm mile 4). Shadow only: the tests
# also pin that this guard has NO way to post to the bus.
from __future__ import annotations

import json
import sys
from pathlib import Path

JEV_DIR = Path(__file__).resolve().parents[1]
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))

import jev_client as jc  # noqa: E402
import jev_drift as jd  # noqa: E402

POLICY = jc.load_questions()["guards"]["drift"]["policy"]


def _a(adv, loop, scope=0.0):
    return {"choices": {}, "scores": {}, "nouls": {"advancing": {"noul": adv}, "looping": {"noul": loop},
                                                    "out_of_scope": {"noul": scope}}}


def test_none_answer_never_warns():
    """Mutation: warn on answers=None -> a network blip reads as a looping leg."""
    d = jd.decide(None, {"looks_looping": True}, POLICY)
    assert d["would_warn"] is False and d["looks_looping"] is False


def test_one_looping_judgment_is_not_enough():
    """Mutation: drop the consecutive rule -> one slow stretch earns a warning."""
    d = jd.decide(_a(0.1, 0.9), None, POLICY)
    assert d["looks_looping"] is True and d["would_warn"] is False
    assert jd.decide(_a(0.1, 0.9), {"looks_looping": False}, POLICY)["would_warn"] is False


def test_two_in_a_row_would_warn():
    """Mutation: never read `previous` -> the guard can never warn at all."""
    assert jd.decide(_a(0.1, 0.9), {"looks_looping": True}, POLICY)["would_warn"] is True


def test_advancing_leg_is_never_a_loop_and_unknown_is_not_zero():
    """Mutation: test looping alone -> a leg re-running a probe while landing evidence gets warned;
    or treat a missing Noul as 0.0 -> UNKNOWN advancing reads as 'not advancing'."""
    assert jd.decide(_a(0.7, 0.95), {"looks_looping": True}, POLICY)["would_warn"] is False
    a = _a(0.1, 0.9)
    a["nouls"]["advancing"] = {"noul": None}
    assert jd.decide(a, {"looks_looping": True}, POLICY)["would_warn"] is False


def _msgs(n, leg="BP9-X", closer=None):
    out = [{"ts": f"2026-09-20T10:{i:02d}:00", "frm": leg, "to": "*", "type": "progress", "body": {"target": "T1"}} for i in range(n)]
    if closer:
        out.append(closer)
    return out


def test_closed_legs_are_never_judged(tmp_path):
    """Mutation: drop any closed-leg guard -> a finished session gets 'drift' judgments forever."""
    assert jd.is_closed(_msgs(3), "BP9-X", tmp_path) is False
    assert jd.is_closed(_msgs(3, closer={"frm": "BP9-X", "type": "progress", "body": {"target": "done"}}), "BP9-X", tmp_path)
    assert jd.is_closed(_msgs(3, closer={"frm": "BP9-X", "type": "status", "body": {"release": True}}), "BP9-X", tmp_path)
    assert jd.is_closed(_msgs(3, closer={"frm": "orchestrator", "to": "BP9-X", "type": "halt", "body": {}}), "BP9-X", tmp_path)
    (tmp_path / "BP9-X.json").write_text("{}", encoding="utf-8")
    assert jd.is_closed(_msgs(3), "BP9-X", tmp_path)


def test_cadence_bounds_calls_and_state_stays_small(tmp_path, monkeypatch):
    """Mutation: judge on every poll -> calls scale with poll frequency, not bus traffic."""
    calls = []
    monkeypatch.setattr(jd.jc, "LEDGER_DIR", tmp_path / "ledger")
    monkeypatch.setattr(jd.jc, "ask", lambda state, spec, **kw: calls.append(state) or _a(0.9, 0.1))
    monkeypatch.setattr(jd, "MISSIONS", tmp_path)
    (tmp_path / "BP9-X.json").write_text(json.dumps({"id": "BP9-X", "targets": ["T1"], "touches": []}), encoding="utf-8")
    assert jd.check("bp9", _msgs(2), tmp_path / "none") == []              # < MIN_NEW events: no call
    assert len(jd.check("bp9", _msgs(4), tmp_path / "none")) == 1          # enough events: one call
    assert jd.check("bp9", _msgs(5), tmp_path / "none") == []              # only 1 new since: no call
    assert len(jd.check("bp9", _msgs(7), tmp_path / "none")) == 1
    assert len(calls) == 2
    big = _msgs(40)
    big[-1]["body"] = {"target": "T1", "blob": "x" * 5000}
    st = jd.drift_state({"id": "BP9-X", "targets": ["T1"], "touches": []}, big)
    assert len(st["events"]) == jd.WINDOW and all(len(e["body"]) <= jd.BODY_MAX for e in st["events"])


def test_shadow_only_no_bus_writer_exists():
    """Mutation: add a bus.post call -> this guard gains authority the card says it does not have."""
    src = (JEV_DIR / "jev_drift.py").read_text(encoding="utf-8")
    assert "bus.post" not in src and ".post(" not in src
