"""CRUCIBLE — pins harness/verify/mode_gate.py, the read-only MODE A/B guard.

The module mirrors run.ts:62-63 (MODE = existsSync(drop.json) ? "B" : "A"). These tests
prove:
  (a) assert_mode_b RAISES when drop.json is absent (MODE A holds);
  (b) RAISES when the file exists but carries drop.json.example placeholders;
  (c) RETURNS the parsed dict when the file carries real H22 numbers;
  (d) current_mode returns 'A' (absent) / 'B' (present).

Loaded by path — harness/verify is NOT a package, so the module is exec'd under its own
alias (mirrors tests/test_r_track.py:22-26). Every fixture is hermetic under tmp_path; the
real harness/state/drop.json is NEVER created, and the absent-case tests assert the guard
leaves no file behind (the module's no-write guarantee).
"""
import importlib.util
import json
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_MODULE = _REPO / "harness" / "verify" / "mode_gate.py"
_spec = importlib.util.spec_from_file_location("harness_mode_gate", _MODULE)
mode_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mode_gate)


# The verbatim drop.json.example placeholder payload — the shape the gate must reject.
_PLACEHOLDER = {
    "houdini_build": "22.0.XXX",
    "python": "3.XX.X",
    "usd": "0.XX.XX",
    "pyside": "6.X.X",
    "dropped_at": "2026-07-15T00:00:00Z",
    "written_by": "human",
}

# A fully-populated drop.json with real numbers (post-drop shape).
_REAL = {
    "houdini_build": "22.0.631",
    "python": "3.12.4",
    "usd": "0.25.05",
    "pyside": "6.7.2",
    "dropped_at": "2026-07-15T00:00:00Z",
    "written_by": "human",
}


# ---- (a) absent → RAISES, and writes nothing ---------------------------------------
def test_assert_mode_b_raises_when_absent(tmp_path):
    missing = tmp_path / "drop.json"
    assert not missing.exists()
    with pytest.raises(RuntimeError, match="MODE A holds"):
        mode_gate.assert_mode_b(str(missing))
    # No-write guarantee: the guard must not have created the file as a side effect.
    assert not missing.exists()


def test_mode_a_message_is_verbatim(tmp_path):
    missing = tmp_path / "drop.json"
    with pytest.raises(RuntimeError) as excinfo:
        mode_gate.assert_mode_b(str(missing))
    assert str(excinfo.value) == "MODE A holds - drop.json not present. Phase 0 only."


# ---- (b) present-but-placeholder → RAISES ------------------------------------------
def test_assert_mode_b_raises_on_placeholder(tmp_path):
    drop = tmp_path / "drop.json"
    drop.write_text(json.dumps(_PLACEHOLDER), encoding="utf-8")
    with pytest.raises(RuntimeError, match="placeholder"):
        mode_gate.assert_mode_b(str(drop))


def test_assert_mode_b_raises_on_partial_placeholder(tmp_path):
    # ANY unset field fires — three real, one still placeholder.
    partial = dict(_REAL, usd="0.XX.XX")
    drop = tmp_path / "drop.json"
    drop.write_text(json.dumps(partial), encoding="utf-8")
    with pytest.raises(RuntimeError, match="usd"):
        mode_gate.assert_mode_b(str(drop))


def test_assert_mode_b_raises_on_missing_field(tmp_path):
    incomplete = {k: v for k, v in _REAL.items() if k != "pyside"}
    drop = tmp_path / "drop.json"
    drop.write_text(json.dumps(incomplete), encoding="utf-8")
    with pytest.raises(RuntimeError, match="pyside"):
        mode_gate.assert_mode_b(str(drop))


def test_assert_mode_b_raises_on_null_field(tmp_path):
    nulled = dict(_REAL, python=None)
    drop = tmp_path / "drop.json"
    drop.write_text(json.dumps(nulled), encoding="utf-8")
    with pytest.raises(RuntimeError, match="python"):
        mode_gate.assert_mode_b(str(drop))


# ---- (c) present-with-real-numbers → RETURNS the dict -------------------------------
def test_assert_mode_b_returns_on_real(tmp_path):
    drop = tmp_path / "drop.json"
    drop.write_text(json.dumps(_REAL), encoding="utf-8")
    result = mode_gate.assert_mode_b(str(drop))
    assert result == _REAL
    assert result["houdini_build"] == "22.0.631"
    # Reading must not have mutated the file.
    assert json.loads(drop.read_text(encoding="utf-8")) == _REAL


# ---- (d) current_mode: A when absent, B when present -------------------------------
def test_current_mode_absent_returns_A(tmp_path):
    missing = tmp_path / "drop.json"
    assert mode_gate.current_mode(str(missing)) == "A"
    # Existence check must not create the file.
    assert not missing.exists()


def test_current_mode_present_returns_B(tmp_path):
    drop = tmp_path / "drop.json"
    drop.write_text("{}", encoding="utf-8")
    assert mode_gate.current_mode(str(drop)) == "B"


# ---- no-hou / import-hygiene guard -------------------------------------------------
def test_module_imports_no_hou():
    import sys
    # The guard must be pure-Python — never drag hou / pxr into the interpreter.
    assert "hou" not in sys.modules or sys.modules["hou"] is not None
    src = _MODULE.read_text(encoding="utf-8")
    assert "import hou" not in src
    assert "from pxr" not in src
