"""WA1-WIRE (C2) — hython test: the LIVE wire-typing verdicts + @/$ resolution table.

Runs only under hython (apex/hou). The module-level importorskip self-gates it, so
tests/conftest.py auto-marks it `needs_houdini` and DESELECTS it under plain pytest —
loudly, never a silent skip-as-pass (skip != pass). Run it for real via:

    python .synapse/hytest.py tests/test_apex_wire_hython.py

These assertions pin the runtime semantics discovered live on H22.0.400: exact-match
diagonal connects; any mismatch rejects with anchored exception text; the matrix is
idempotent across repeats; the resolution table classifies $ (expands) vs @ (literal)
and marks the invoke-binding context UNKNOWN headless.
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("hou")
pytest.importorskip("apex")

_REPO = Path(__file__).resolve().parents[1]
_AR = _REPO / "harness" / "autoresearch"
for _p in (str(_AR), str(_REPO / "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import probes  # noqa: E402


def test_wire_matrix_diagonal_connects_offdiagonal_rejects():
    r = probes.probe_apex_wire_matrix(["Float", "Int", "Geometry"], repeat=2)
    assert r["type_set_source"] == "declared_fixture"
    cells = {(c["out"], c["in"]): c for c in r["cells"]}
    # exact-match diagonal -> connect
    assert cells[("Float", "Float")]["verdict"] == "connect"
    assert cells[("Geometry", "Geometry")]["verdict"] == "connect"
    # mismatch -> reject, carrying exception text (a reject without one is unanchored)
    rej = cells[("Int", "Float")]
    assert rej["verdict"] == "reject"
    assert rej.get("exception")
    assert "Mismatched type" in rej["exception"] or rej.get("reject_mode") == "structural"


def test_wire_matrix_idempotent():
    r = probes.probe_apex_wire_matrix(["Float", "Int", "Vector3"], repeat=2)
    assert r["repeat"]["idempotent"] is True
    assert len(set(r["repeat"]["pass_hashes"])) == 1
    assert r["repeat"]["drift"] == []


def test_every_cell_has_a_verdict():
    r = probes.probe_apex_wire_matrix(["Float", "Int", "Geometry", "Dict"], repeat=1)
    allowed = {"connect", "coerce", "reject", "UNKNOWN"}
    assert all(c["verdict"] in allowed for c in r["cells"])
    assert r["pair_count"] == 16  # 4 x 4 full ordered product


def test_absent_type_renders_unknown_not_omitted():
    # A bogus type has no Value<T> constructor -> the cell is UNKNOWN, never dropped.
    r = probes.probe_apex_wire_matrix(["Float", "NotAType"], repeat=1)
    cells = {(c["out"], c["in"]): c for c in r["cells"]}
    assert r["pair_count"] == 4  # full 2x2 product, nothing omitted
    assert cells[("NotAType", "Float")]["verdict"] == "UNKNOWN"
    assert cells[("NotAType", "Float")].get("reason")


def test_token_resolution_table_shape():
    r = probes.probe_apex_token_resolution(
        ["$HIP", "@P"], ["hscript_global", "apex_invoke_binding"])
    assert r["row_count"] == 4  # 2 tokens x 2 contexts, one row each
    rows = {(x["token"], x["context"]): x for x in r["rows"]}
    # @ is literal in hscript_global; the invoke binding is UNKNOWN headless by design
    assert rows[("@P", "hscript_global")]["resolved_to"] == "@P"
    assert rows[("$HIP", "apex_invoke_binding")]["resolved_to"] == "UNKNOWN"
    assert rows[("@P", "apex_invoke_binding")]["resolved_to"] == "UNKNOWN"
    assert rows[("$HIP", "apex_invoke_binding")].get("reason")
