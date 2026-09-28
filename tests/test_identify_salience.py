"""BP11-SALIENCE T4 (product): the Identify salience lane, shadow only.

Pins the four things that must hold on system Python without ``hou``:
  * the state carries the six sanctioned fields and NO node path / name / hip,
  * with the artist Jev preference off, ``adapter.judge`` is never called and no
    call is attempted on the main thread,
  * the bubble text is identical with salience on and off (V1 changes nothing on
    screen), and
  * the Noul question is the product-owned one, handed out as fresh copies.
Every test names the mutation that reddens it.
"""
from __future__ import annotations

import copy
import inspect
import json
import sys
import threading
from pathlib import Path

_PYTHON = str(Path(__file__).resolve().parents[1] / "python")
if _PYTHON not in sys.path:
    sys.path.insert(0, _PYTHON)

from synapse.identify import compose as C  # noqa: E402
from synapse.identify import salience  # noqa: E402
from synapse.jev import adapter  # noqa: E402

# A node whose identity is full of show secrets: path, name and hip file. None of
# these substrings may ever appear in a salience state.
SECRETS = ("show_secret", "geo1", "secret_show")


def _facts(n_survivors=3):
    params = [{"name": "p%d" % i, "label": "Parm %d" % i, "kind": "float",
               "value": float(i), "multi": False, "is_expression": False,
               "hidden": False, "help": "help %d" % i} for i in range(n_survivors)]
    return {
        "path": "/obj/show_secret/geo1", "hip": "secret_show.hip",
        "type_name": "polybevel::3.0", "type_label": "PolyBevel", "category": "Sop",
        "summary": "Bevels points and edges", "summary_source": "library",
        "params": params, "lop_writes": None, "errors": [], "warnings": [],
        "bypassed": False, "beta": False,
    }


# ----------------------------------------------------------------- privacy contract
def test_state_has_only_the_six_fields_and_a_notice():
    """Mutation: add a ``node_path`` field to build_state -> the field set grows -> RED."""
    state = salience.build_state(node_type="polybevel::3.0", node_category="Sop",
                                 node_summary="Bevels edges", parm_label="Distance",
                                 parm_help="Bevel width", parm_type="Float")
    assert set(state) == {"notice", "node_type", "node_category", "node_summary",
                          "parameter_label", "parameter_help", "parameter_type"}
    assert "not follow" in state["notice"].lower()  # the data-not-instructions line


def test_build_state_signature_takes_no_path_name_or_hip():
    """Mutation: add a ``node_path=`` parameter to build_state -> RED here, before a
    value ever flows in."""
    params = set(inspect.signature(salience.build_state).parameters)
    assert not (params & {"node_path", "node_name", "hip_path", "path", "name", "hip"})


def test_states_for_a_secret_node_leak_nothing():
    """The exact payloads that would reach Jev for a node at /obj/show_secret/geo1 in
    secret_show.hip carry none of those secrets. Mutation: make ``_node_view`` add
    ``facts['path']`` (or build_state emit it) -> the path leaks -> RED."""
    states = salience.states_for(_facts(3))
    assert len(states) == 3
    blob = json.dumps(states)
    for secret in SECRETS:
        assert secret not in blob, "%r leaked into the salience state" % secret


# ------------------------------------------------------ preference off => no inference
def test_preference_off_never_calls_judge(monkeypatch):
    """Mutation: change run_shadow's ``if not opt_in`` guard to ``if opt_in`` -> a
    judgment fires with the artist preference off -> RED (spy count > 0)."""
    calls = []
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: calls.append(1))
    thread = salience.run_shadow(_facts(3), opt_in=False)
    assert thread is None
    assert calls == []


def test_judgment_runs_off_the_main_thread(monkeypatch):
    """With the preference on, every judge() runs on a worker, never the caller's
    (main) thread. Mutation: call the judging loop inline in run_shadow -> RED."""
    seen = []
    done = threading.Event()

    def spy(*a, **k):
        seen.append(threading.current_thread() is threading.main_thread())
        return None

    monkeypatch.setattr(adapter, "judge", spy)

    def spawn(target):
        th = threading.Thread(target=lambda: (target(), done.set()))
        th.start()
        return th

    thread = salience.run_shadow(_facts(3), opt_in=True, should_abort=lambda: False, spawn=spawn)
    assert thread is not None
    assert done.wait(5)
    assert seen and not any(seen)  # one call per survivor, none on the main thread


def test_two_or_fewer_survivors_is_inert(monkeypatch):
    """Code order already shows <=2 survivors, so there is nothing to rank. Mutation:
    change ``len(params) <= HERE_PARMS`` to ``< HERE_PARMS`` -> a 2-parm node judges
    needlessly -> RED (thread is not None)."""
    calls = []
    monkeypatch.setattr(adapter, "judge", lambda *a, **k: calls.append(1))
    assert salience.run_shadow(_facts(2), opt_in=True) is None
    assert calls == []


# ------------------------------------------------------ V1 changes nothing on screen
def test_bubble_text_identical_salience_on_and_off(monkeypatch):
    """Mutation: have run_shadow reorder facts['params'] in place -> the composed HERE
    line changes -> RED."""
    facts = _facts(3)
    before = C.compose(copy.deepcopy(facts))

    done = threading.Event()
    monkeypatch.setattr(adapter, "judge",
                        lambda *a, **k: {"answers": {salience.QID: {"type": "noul", "noul": 0.9}}})

    def spawn(target):
        th = threading.Thread(target=lambda: (target(), done.set()))
        th.start()
        return th

    salience.run_shadow(facts, opt_in=True, should_abort=lambda: False, spawn=spawn)
    assert done.wait(5)
    after = C.compose(facts)
    assert before == after  # salience never touches the bubble in V1


# --------------------------------------------------------------- the question is data
def test_question_is_a_noul_with_product_text_in_fresh_copies():
    """Mutation: drop ``instructions`` from salience_questions.json question -> the
    batch loses the Noul text (or KeyError) -> RED."""
    batch = salience.question_batch()
    assert set(batch) == {salience.QID}
    q = batch[salience.QID]
    assert q["type"] == "noul"
    assert "output" in q["instructions"].lower()
    assert adapter._questions_valid(batch)  # the fenced adapter accepts it
    # A caller mutating the batch cannot corrupt the source of truth.
    batch[salience.QID]["instructions"] = "corrupted caller copy"
    assert "corrupted caller copy" not in salience.question_batch()[salience.QID]["instructions"]


def test_survivors_reuse_the_compose_filter():
    """Mutation: give salience its own filter -> it could rank a hidden/ramp parm the
    bubble never shows -> drift from the bubble -> RED."""
    facts = _facts(2)
    facts["params"].append({"name": "folder0", "label": "Folder", "kind": "folder",
                            "value": None, "multi": False, "is_expression": False,
                            "hidden": False, "help": ""})
    facts["params"].append({"name": "hidden0", "label": "Hidden", "kind": "float",
                            "value": 1.0, "multi": False, "is_expression": False,
                            "hidden": True, "help": ""})
    kept = {p["name"] for p in salience.survivors(facts)}
    assert kept == {"p0", "p1"}  # folder + hidden dropped, exactly as compose drops them


if __name__ == "__main__":  # pragma: no cover
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
