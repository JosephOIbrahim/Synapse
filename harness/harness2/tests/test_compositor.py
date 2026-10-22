"""Tests for the HARNESS2 compose guard.

Article III, Law 1: every check must be able to fail. Prove it can. Each test below
names the condition under which the guard changes its answer, and a test that cannot
fail is deleted rather than kept green.

Run:  python -m pytest harness/harness2/tests/test_compositor.py -q
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))

import compositor as C  # noqa: E402


# --------------------------------------------------------------- scrubbing

def test_scrub_removes_absolute_path_hash_and_pid():
    s = ("read C:\\Users\\User\\SYNAPSE\\python\\synapse\\core\\protocol.py and "
         "/home/someone/secret.txt sha=deadbeefdeadbeefdeadbeefdeadbeefdeadbeef pid 32832")
    out = C.scrub_text(s)
    assert "C:\\Users\\User" not in out
    assert "/home/someone" not in out
    assert "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" not in out
    assert "32832" not in out
    # the repo-relative part stays readable, because a path is evidence
    assert "python/synapse/core/protocol.py" in out


def test_scrub_keeps_repo_relative_path_readable():
    out = C.scrub_text("python/synapse/core/preflight.py:202")
    assert out == "python/synapse/core/preflight.py:202"


def test_scrub_is_recursive():
    out = C.scrub({"a": ["C:\\Users\\User\\x.py"], "b": {"c": "pid 99"}})
    assert "C:\\Users\\User" not in json.dumps(out)
    assert "99" not in json.dumps(out)


# --------------------------------------------------------------- compose

def _cand(cid, files, probe="PROBED: before fails, after passes", strength=3, probe_n=0.9, comp=0.9):
    return {
        "id": cid,
        "claim": "close the " + cid + " gap",
        "change": "add a check",
        "files": files,
        "probe": probe,
        "exclusion": "not for other gaps",
    }


def _answers(choice="A", conf=0.9, strength=3, probe=0.9, comp=0.9):
    return {
        "choices": {"adopt": {"choice": choice, "confidence": conf, "probabilities": {choice: conf}}},
        "scores": {"strength_A": {"score": strength, "confidence": 1.0},
                   "strength_B": {"score": strength, "confidence": 1.0}},
        "nouls": {"probe_A": {"noul": probe}, "probe_B": {"noul": probe},
                  "composable_A": {"noul": comp}, "composable_B": {"noul": comp}},
    }


def test_compose_adopts_the_chosen_candidate_when_everything_holds():
    cands = [_cand("A", ["a.py"]), _cand("B", ["b.py"])]
    d = C.decide_compose(_answers(), cands, C.load_questions()["guards"]["compose"]["policy"])
    assert d["primary"] == "A"
    assert {c["id"] for c in d["adopted"]} == {"A", "B"}
    assert d["reason"].startswith("jev:")


def test_compose_refuses_when_jev_is_unavailable():
    """The fail-closed path. No Jev answer means NO adoption, never a default."""
    cands = [_cand("A", ["a.py"])]
    d = C.decide_compose(None, cands, C.load_questions()["guards"]["compose"]["policy"])
    assert d["adopted"] == []
    assert d["needs_joe"] == ["A"]
    assert "no Jev answer" in d["reason"]


def test_compose_refuses_a_choice_that_is_not_a_candidate():
    cands = [_cand("A", ["a.py"])]
    d = C.decide_compose(_answers(choice="C2-identity"), cands,
                          C.load_questions()["guards"]["compose"]["policy"])
    assert d["adopted"] == []
    assert "not a candidate id" in d["reason"]


def test_compose_refuses_a_low_confidence_choice():
    cands = [_cand("A", ["a.py"])]
    d = C.decide_compose(_answers(conf=0.2), cands,
                          C.load_questions()["guards"]["compose"]["policy"])
    assert d["adopted"] == []
    assert "confidence" in d["reason"]


def test_compose_refuses_a_weak_candidate():
    cands = [_cand("A", ["a.py"])]
    d = C.decide_compose(_answers(strength=1), cands,
                          C.load_questions()["guards"]["compose"]["policy"])
    assert d["adopted"] == []
    assert "strength" in d["reason"]


def test_compose_refuses_a_candidate_whose_probe_does_not_support_it():
    cands = [_cand("A", ["a.py"])]
    d = C.decide_compose(_answers(probe=0.1), cands,
                          C.load_questions()["guards"]["compose"]["policy"])
    assert d["adopted"] == []
    assert "probe support" in d["reason"]


def test_compose_never_co_adopts_two_candidates_claiming_one_file():
    """The single-writer rule, enforced in CODE. Jev's opinion does not override it."""
    cands = [_cand("A", ["shared.py"]), _cand("B", ["shared.py"])]
    d = C.decide_compose(_answers(), cands, C.load_questions()["guards"]["compose"]["policy"])
    assert {c["id"] for c in d["adopted"]} == {"A"}
    assert d["conflicts"] and d["conflicts"][0]["candidate"] == "B"


def test_compose_spec_builds_one_criterion_per_candidate():
    guard = C.load_questions()["guards"]["compose"]
    cands = [_cand("A", ["a.py"]), _cand("B", ["b.py"])]
    spec = C.compose_spec(cands, guard)
    assert set(spec["adopt"]["criteria"]) == {"A", "B"}
    assert "strength_A" in spec and "probe_A" in spec and "composable_A" in spec
    # a candidate's own claim reaches the criterion, not a generic description
    assert "close the A gap" in spec["adopt"]["criteria"]["A"]["what"]


# --------------------------------------------------------------- binding
#
# A JEV question id is NOT sent to the model. An instruction that says "this
# candidate" names nothing, and the state carries EVERY candidate - so the model
# averages over the whole set. These tests are the guard against that regression.

def test_per_candidate_questions_carry_their_own_candidate_text():
    """strength_A must talk about A. If it names B, the question is not per-candidate."""
    guard = C.load_questions()["guards"]["compose"]
    cands = [_cand("A", ["a.py"]), _cand("B", ["b.py"])]
    spec = C.compose_spec(cands, guard)
    a = spec["strength_A"]["instructions"]
    b = spec["strength_B"]["instructions"]
    assert "close the A gap" in a
    assert "close the B gap" not in a
    assert "close the B gap" in b
    assert "close the A gap" not in b
    assert a != b


def test_probe_question_carries_the_candidate_own_probe_text():
    """A candidate whose probe reads NOT PROBED must say so in the instruction.

    This is the exact failure the smoke run exposed: probe_B scored 0.73 against a
    candidate whose probe literally read NOT PROBED, because the instruction never
    named a candidate and the model averaged over both.
    """
    guard = C.load_questions()["guards"]["compose"]
    cands = [_cand("A", ["a.py"]),
             dict(_cand("B", ["b.py"]), probe="NOT PROBED")]
    spec = C.compose_spec(cands, guard)
    # the SUBJECT block is what binds the question to one candidate
    subj_b = spec["probe_B"]["instructions"].split("CANDIDATE UNDER JUDGMENT:", 1)[1]
    subj_a = spec["probe_A"]["instructions"].split("CANDIDATE UNDER JUDGMENT:", 1)[1]
    assert "NOT PROBED" in subj_b
    assert "NOT PROBED" not in subj_a
    assert "PROBED: before fails" in subj_a


def test_composable_question_lists_the_OTHER_candidates_files():
    """Composability is relative. The instruction must carry the other candidates'
    file sets, and the candidate's OWN file set must not appear in that block."""
    guard = C.load_questions()["guards"]["compose"]
    cands = [_cand("A", ["a.py"]), _cand("B", ["b.py"])]
    spec = C.compose_spec(cands, guard)
    marker = "OTHER ITEMS IN THIS WAVE:"
    others_a = spec["composable_A"]["instructions"].split(marker, 1)[1]
    others_b = spec["composable_B"]["instructions"].split(marker, 1)[1]
    assert "b.py" in others_a
    assert "a.py" not in others_a
    assert "a.py" in others_b
    assert "b.py" not in others_b


def test_composable_of_a_lone_candidate_says_so_explicitly():
    """One candidate: the 'others' block must not be silently empty."""
    guard = C.load_questions()["guards"]["compose"]
    spec = C.compose_spec([_cand("A", ["a.py"])], guard)
    inst = spec["composable_A"]["instructions"]
    assert "OTHER ITEMS IN THIS WAVE:" in inst
    assert "only item" in inst


def test_graph_per_node_questions_carry_their_own_node_text():
    guard = C.load_questions()["guards"]["graph"]
    nodes = [_node("A", ["a.py"]), _node("B", ["b.py"], ["A"])]
    spec = C.graph_spec(nodes, guard)
    a = spec["value_A"]["instructions"]
    b = spec["value_B"]["instructions"]
    assert "node A" in a and "node B" not in a
    assert "node B" in b and "node A" not in b
    assert "DEPENDS ON: none" in a
    assert "DEPENDS ON: A" in b


def test_no_shipped_instruction_refers_to_an_unbound_item():
    """The lint. 'this candidate' / 'this node' in a shipped instruction is a
    reference the model cannot resolve, because the question id never reaches it."""
    q = C.load_questions()
    banned = ("this candidate", "this node", "the candidate above", "the node above")
    for gname, guard in q["guards"].items():
        for qid, spec in guard["questions"].items():
            text = spec.get("instructions")
            if isinstance(text, dict):
                text = " ".join(str(v) for v in text.values())
            if not isinstance(text, str):
                continue
            low = text.lower()
            for phrase in banned:
                assert phrase not in low, "%s.%s says %r - an unbound reference" % (
                    gname, qid, phrase)


def test_every_per_item_question_declares_what_it_binds():
    """A per-item question that binds nothing is the bug this whole block fixes."""
    q = C.load_questions()
    for gname, guard in q["guards"].items():
        assert "subject_shape" in guard, "%s has no subject_shape" % gname
        per_item = [qid for qid, s in guard["questions"].items()
                    if s.get("type") != "choice"]
        for qid in per_item:
            bind = guard["questions"][qid].get("bind")
            assert bind, "%s.%s binds nothing" % (gname, qid)
            assert "subject" in bind, "%s.%s does not bind a subject" % (gname, qid)


# --------------------------------------------------------------- calibration

def test_every_score_threshold_has_a_calibration_record_with_a_producer():
    """Law 2: a number with no producer path is a number nobody can re-derive."""
    q = C.load_questions()
    for gname, guard in q["guards"].items():
        policy = guard.get("policy") or {}
        rec = guard.get("calibration") or {}
        for qid, spec in guard["questions"].items():
            if spec.get("type") != "score":
                continue
            key = "min_strength" if "strength" in qid else "min_value"
            if key not in policy:
                continue
            assert key in rec, "%s.%s threshold %s has no calibration record" % (
                gname, qid, policy[key])
            entry = rec[key]
            assert entry.get("producer"), "%s.calibration.%s has no producer path" % (gname, key)
            assert entry.get("verdict") in ("LIVE", "DORMANT"), \
                "%s.calibration.%s verdict is %r" % (gname, key, entry.get("verdict"))
            assert abs(float(entry["value"]) - float(policy[key])) < 1e-9


def test_recorded_calibration_matches_a_fresh_measurement():
    """The producer must reproduce the recorded verdict. If the model drifts, this
    is where the threshold gets re-examined - not by guessing."""
    import calibrate
    rep = calibrate.build_report()
    assert calibrate.check_recorded(rep) == []
    for t in rep["thresholds"]:
        assert t["verdict"] == "LIVE", "%s.%s is %s: %s" % (
            t["guard"], t["policy_key"], t["verdict"], t["why"])


def test_the_shipped_strength_threshold_can_actually_fire():
    """min_strength: 2 on a 4-criteria rubric is two thirds of the range. A dead
    gate is worse than no gate: it prints PASS forever."""
    import calibrate
    rep = calibrate.build_report()
    t = next(x for x in rep["thresholds"] if x["policy_key"] == "min_strength")
    assert t["verdict"] == "LIVE"
    assert t["reachable_fraction"] and t["reachable_fraction"] > 0.0
    assert t["fraction_of_range"] == round(2 / 3, 4)


def test_the_invariant_does_not_claim_a_score_is_a_row_index():
    """The old text said a threshold of 2 'means the third rubric row'. It does not.
    A Score returns a probability-weighted POSITION, and the same raw value is a
    different thing on a different-sized rubric."""
    q = C.load_questions()
    text = " ".join(q["_invariants"])
    assert "rubric row" not in text
    assert "fraction of range" in text.lower() or "FRACTION OF RANGE" in text
    assert "position" in text.lower()


# --------------------------------------------------------------- graph

def _node(nid, files, depends=None):
    return {"id": nid, "title": "node " + nid, "owner_files": files, "depends_on": depends or [],
            "why": "it is the " + nid + " problem"}


def _ganswers(choice="A", conf=0.9, lands=0.9, value=3, joe=0.1):
    return {
        "choices": {"first_landing": {"choice": choice, "confidence": conf, "probabilities": {choice: conf}}},
        "scores": {"value_A": {"score": value, "confidence": 1.0}, "value_B": {"score": value, "confidence": 1.0}},
        "nouls": {"lands_A": {"noul": lands}, "lands_B": {"noul": lands},
                  "joe_decides_A": {"noul": joe}, "joe_decides_B": {"noul": joe}},
    }


def test_graph_picks_the_first_landing_and_splits_land_park():
    nodes = [_node("A", ["a.py"]), _node("B", ["b.py"], ["A"])]
    pol = C.load_questions()["guards"]["graph"]["policy"]
    d = C.decide_graph(_ganswers(), nodes, pol)
    assert d["first_landing"] == "A"
    assert set(d["land_now"]) == {"A", "B"}
    assert d["park"] == []


def test_graph_escalates_a_node_that_needs_joe_out_of_land_now():
    nodes = [_node("A", ["a.py"]), _node("B", ["b.py"])]
    pol = C.load_questions()["guards"]["graph"]["policy"]
    d = C.decide_graph(_ganswers(joe=0.9), nodes, pol)
    assert set(d["needs_joe"]) == {"A", "B"}
    assert d["land_now"] == []


def test_graph_falls_back_when_the_chosen_node_is_blocked():
    nodes = [_node("A", ["a.py"]), _node("B", ["b.py"])]
    pol = C.load_questions()["guards"]["graph"]["policy"]
    d = C.decide_graph(_ganswers(choice="A", lands=0.1), nodes, pol)
    assert d["first_landing"] is None
    assert "not landable" in d["reason"]


def test_graph_fails_closed_without_jev():
    nodes = [_node("A", ["a.py"])]
    pol = C.load_questions()["guards"]["graph"]["policy"]
    d = C.decide_graph(None, nodes, pol)
    assert d["first_landing"] is None
    assert d["park"] == ["A"]


# --------------------------------------------------------------- dead gates

def test_dead_gate_is_refused_at_load_time():
    """A threshold above the maximum score can never fire. That is a dead gate, and a
    dead gate is worse than no gate: it prints PASS forever."""
    guard = C.load_questions()["guards"]["compose"]
    bad = dict(guard["policy"])
    bad["min_strength"] = 99
    spec = C.compose_spec([_cand("A", ["a.py"])], guard)
    problems = C.check_policy("compose", {**guard, "policy": bad}, spec)
    assert problems and "DEAD GATE" in problems[0]


def test_shipped_policy_has_no_dead_gate():
    q = C.load_questions()
    for name in ("compose", "graph"):
        guard = q["guards"][name]
        spec = (C.compose_spec([_cand("A", ["a.py"])], guard) if name == "compose"
                else C.graph_spec([_node("A", ["a.py"])], guard))
        assert C.check_policy(name, guard, spec) == []


def test_every_shipped_question_is_in_a_documented_primitive():
    """A Score takes a SEQUENCE of criteria; a Choice takes a MAPPING. Getting this
    backwards is a TypeError at call time, in production."""
    q = C.load_questions()
    for name in ("compose", "graph"):
        for qid, spec in q["guards"][name]["questions"].items():
            if spec["type"] == "score":
                assert isinstance(spec["criteria"], list), f"{name}.{qid} score criteria must be a list"
            elif spec["type"] == "choice":
                assert "criteria_shape" in q["guards"][name], f"{name}.{qid} needs a runtime criteria shape"
            elif spec["type"] == "noul":
                assert "instructions" in spec, f"{name}.{qid} needs instructions"


def test_scrubbed_state_is_what_reaches_the_api(monkeypatch):
    """The scrubber is not decoration: the state handed to jc.ask carries no path."""
    seen = {}

    def fake_ask(state, spec, **kw):
        seen["state"] = state
        seen["spec"] = spec
        return None

    monkeypatch.setattr(C.jc, "ask", fake_ask)
    C.compose([_cand("A", ["a.py"])], "test", {"harness": "at C:\\Users\\User\\SYNAPSE"},
              ["no absolute paths"], ["wrote C:\\Users\\User\\SYNAPSE\\x.py"])
    blob = json.dumps(seen["state"])
    assert "C:\\Users\\User" not in blob
    assert "SYNAPSE" not in blob
