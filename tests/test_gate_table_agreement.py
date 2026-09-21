"""CRUCIBLE -- pins harness/verify/gate_table_agreement.py, the deterministic
gate-table drift lint (advise-only, ratcheted, no key, no network).

Proves:
  (a) the lint PASSES at the committed ratchet baseline (today's 16 known-missing);
  (b) the live missing set equals the baseline names exactly (no silent drift in
      either direction -- a fixed row OR a new gap both break this);
  (c) the op-gate check is clean today (only the declared `insert_cache` op is
      absent from OPERATION_GATES);
  (d) THE BITE -- removing a non-read-only tool from _TOOL_TO_OPERATION reddens
      the lint (the tool becomes a NEW missing row, 16 -> 17);
  (e) main() returns 0 against the live tables at the baseline.

The module is loaded by path -- harness/verify is NOT a package (mirrors
tests/test_mode_gate.py:22-26). Every check is a pure cross-reference of the
shipped tables; nothing here mutates a real table on disk.
"""
import importlib.util
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]
_MODULE = _REPO / "harness" / "verify" / "gate_table_agreement.py"
_spec = importlib.util.spec_from_file_location("harness_gate_table_agreement", _MODULE)
gta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gta)


def _live():
    tool_defs, tool_to_op, operation_gates, _disk = gta.load_tables()
    return tool_defs, tool_to_op, operation_gates


def test_passes_at_ratchet_baseline():
    tool_defs, tool_to_op, operation_gates = _live()
    baseline = gta.load_baseline()
    result = gta.compute(tool_defs, tool_to_op, operation_gates)
    verdict = gta.evaluate(result, baseline)
    assert verdict["ok"], verdict
    assert verdict["new_missing"] == []
    assert result["missing_count"] == baseline["missing_count"]


def test_live_missing_set_matches_baseline_names():
    tool_defs, tool_to_op, operation_gates = _live()
    baseline = gta.load_baseline()
    result = gta.compute(tool_defs, tool_to_op, operation_gates)
    # Exact-set equality catches drift in BOTH directions: a fixed row (baseline
    # should tighten) and a new gap (lint should have reddened) each break it.
    assert set(result["missing"]) == set(baseline["missing_names"]), {
        "new_gap": sorted(set(result["missing"]) - set(baseline["missing_names"])),
        "now_fixed": sorted(set(baseline["missing_names"]) - set(result["missing"])),
    }


def test_op_gate_check_clean_today():
    # Every op a tool maps to is in OPERATION_GATES or the DECLARED_OPS set.
    tool_defs, tool_to_op, operation_gates = _live()
    result = gta.compute(tool_defs, tool_to_op, operation_gates)
    assert result["ungated_ops"] == [], result["ungated_ops"]


def test_reddens_when_mapped_tool_unmapped():
    """THE BITE. Remove a currently-mapped non-read-only tool -> lint FAILS.

    Mutation: delete "houdini_create_node" (non-read-only, mapped to
    "create_node") from a COPY of _TOOL_TO_OPERATION. It then has no row, so it
    becomes a NEW missing tool (16 -> 17) and evaluate() must reject.
    """
    tool_defs, tool_to_op, operation_gates = _live()
    baseline = gta.load_baseline()

    victim = "houdini_create_node"
    # Preconditions: the victim really is a non-read-only tool, currently mapped,
    # and NOT already an accepted-missing row -- so removing it is a true regression.
    assert victim in tool_to_op
    assert any(d[0] == victim and not d[5] for d in tool_defs)
    assert victim not in baseline["missing_names"]

    mutated = dict(tool_to_op)
    del mutated[victim]

    result = gta.compute(tool_defs, mutated, operation_gates)
    verdict = gta.evaluate(result, baseline)

    assert verdict["ok"] is False
    assert victim in verdict["new_missing"]
    assert result["missing_count"] == baseline["missing_count"] + 1


def test_main_exits_zero_at_baseline():
    """End-to-end: the script's main() returns 0 against the live tables."""
    assert gta.main() == 0
