"""WA1-WIRE (C2) — plain-Python tests: mission schema for the two new probe kinds,
the UNKNOWN discipline of the probes when apex/hou are absent, and hash determinism.

The LIVE wire-typing semantics (connect/coerce/reject) and the @/$ resolution table
are hython-only; they are exercised by tests/test_apex_wire_hython.py (via the
.synapse/hytest.py shim) and by the mission run itself. Under plain Python these
probes must degrade to UNKNOWN — never crash, never silently pass (skip != pass).
"""
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_AR = _REPO / "harness" / "autoresearch"
for _p in (str(_AR), str(_REPO / "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mission_schema as ms  # noqa: E402
import probes  # noqa: E402

MISSION = _AR / "missions" / "apex_wire.json"


def _apex_available() -> bool:
    try:
        import apex  # noqa: F401
        return True
    except Exception:
        return False


def _hou_available() -> bool:
    try:
        import hou  # noqa: F401
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- mission schema

def test_apex_wire_mission_validates():
    m = ms.load_mission(MISSION)
    assert m.name == "apex_wire"
    assert m.artifact_prefix == "apex_wire_matrix"
    kinds = [p.kind for p in m.phases]
    assert "apex_wire_matrix" in kinds
    assert "apex_token_resolution" in kinds


def test_apex_wire_mission_type_set_is_declared_and_nonempty():
    m = ms.load_mission(MISSION)
    q = m.phases[0].questions[0]
    assert isinstance(q["type_set"], list) and len(q["type_set"]) >= 2
    # the axis names the type CLASSES the blueprint calls out
    for t in ("Matrix4", "Float", "Geometry", "Dict", "String", "FloatRamp"):
        assert t in q["type_set"], t
    assert any(t.endswith("Array") for t in q["type_set"])  # arrays in scope


def test_wire_matrix_kind_requires_type_set():
    data = {"mission": "m", "version": "1", "target_build": "22.0.400",
            "phases": [{"id": "p", "kind": "apex_wire_matrix", "questions": [{}]}]}
    with pytest.raises(ms.MissionError):
        ms.validate_mission(data)


def test_wire_matrix_defaults_normalized():
    data = {"mission": "m", "version": "1", "target_build": "22.0.400",
            "phases": [{"id": "p", "kind": "apex_wire_matrix",
                        "questions": [{"type_set": ["Float", "Int"]}]}]}
    m = ms.validate_mission(data)
    q = m.phases[0].questions[0]
    assert q["repeat"] == 2
    assert q["sample"] is None


def test_wire_matrix_bad_sample_shape_rejected():
    data = {"mission": "m", "version": "1", "target_build": "22.0.400",
            "phases": [{"id": "p", "kind": "apex_wire_matrix",
                        "questions": [{"type_set": ["Float"], "sample": [["Float"]]}]}]}
    with pytest.raises(ms.MissionError):
        ms.validate_mission(data)


def test_token_kind_requires_tokens():
    data = {"mission": "m", "version": "1", "target_build": "22.0.400",
            "phases": [{"id": "p", "kind": "apex_token_resolution", "questions": [{}]}]}
    with pytest.raises(ms.MissionError):
        ms.validate_mission(data)


def test_token_contexts_default_none():
    data = {"mission": "m", "version": "1", "target_build": "22.0.400",
            "phases": [{"id": "p", "kind": "apex_token_resolution",
                        "questions": [{"tokens": ["$HIP"]}]}]}
    m = ms.validate_mission(data)
    assert m.phases[0].questions[0]["contexts"] is None


# ---------------------------------------------------------------- UNKNOWN discipline
# When apex/hou are absent (plain CPython), the probes render UNKNOWN with a reason —
# never a crash, never a fabricated verdict. (Skipped only in the irrelevant case
# where apex/hou happen to be present, e.g. the suite run under hython.)

@pytest.mark.skipif(_apex_available(), reason="apex present: UNKNOWN-without-apex path is a plain-Python guarantee")
def test_wire_matrix_unknown_without_apex():
    r = probes.probe_apex_wire_matrix(["Float", "Int"])
    assert r.get("value") == "UNKNOWN"
    assert "apex" in (r.get("reason") or "").lower()
    assert r["type_set"] == ["Float", "Int"]


@pytest.mark.skipif(_hou_available(), reason="hou present: UNKNOWN-without-hou path is a plain-Python guarantee")
def test_token_resolution_unknown_without_hou():
    r = probes.probe_apex_token_resolution(["$HIP", "@P"], None)
    assert r["row_count"] == len(r["rows"]) == 2 * 4
    # every cell UNKNOWN when the surfaces are absent — and the reason is recorded
    assert all(row["resolved_to"] == "UNKNOWN" for row in r["rows"])
    assert all("reason" in row for row in r["rows"])
    # form + session-dependence are still classified without a runtime
    forms = {row["token"]: row["form"] for row in r["rows"]}
    assert forms["$HIP"] == "$" and forms["@P"] == "@"


# ---------------------------------------------------------------- pure-function determinism

def test_matrix_hash_order_independent_and_exception_sensitive():
    cells = [{"out": "A", "in": "B", "verdict": "connect"},
             {"out": "B", "in": "A", "verdict": "reject", "exception": "x"}]
    h1 = probes._wm_matrix_hash(cells)
    h2 = probes._wm_matrix_hash(list(reversed(cells)))
    assert h1 == h2  # order-independent
    # a reject whose exception text silently changed must break the hash (idempotence guard)
    cells2 = [dict(cells[0]), dict(cells[1], exception="y")]
    assert probes._wm_matrix_hash(cells2) != h1


def test_tok_form_classifier():
    assert probes._tok_form("$HIP") == "$"
    assert probes._tok_form("@P") == "@"
    assert probes._tok_form("plain") == "other"
