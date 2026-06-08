"""Track C · Phase 2 — the allocation pre-gate (v5 §3). Logic/CI tier, pure.

Pins the runbook verify list: admit proceeds; downstream-without-override HALTS;
downstream-with-override proceeds + records; defer bars decomposition; a target
with NO Allocation is barred (violation #6); a redundant second pass is tripped.
Plus the §7 substrate-adjacent default (conservative operator-override) and the
Allocation→Ledger projection (RFC Option C, kind="Allocation").
"""

import json

import pytest

from synapse.science.allocation import (
    Allocation, allocate, is_barred, detect_redundant_pass, to_ledger_record,
    AllocationHalt,
)
from synapse.memory import ledger

AB = "21.0.631"


# ── the gate's verdicts ──────────────────────────────────────────────────────

def test_substrate_loci_admit():
    for locus in ("authoring", "composition", "proof"):
        a = allocate("t", locus, "serves the substrate", against_build=AB)
        assert a.verdict == "admit" and a.decided_by == "gate"
        assert a.admits() and not is_barred(a)


def test_out_of_scope_defers_and_bars_decompose():
    a = allocate("t", "out-of-scope", "unrelated", against_build=AB)
    assert a.verdict == "defer" and not a.admits()
    assert is_barred(a)   # do NOT decompose (a Deferred entry is the caller's pair)


def test_downstream_without_override_halts():
    with pytest.raises(AllocationHalt):
        allocate("pixel_sort", "downstream", "post-proof polish", against_build=AB)


def test_downstream_with_override_proceeds_and_records():
    a = allocate("pixel_sort", "downstream", "post-proof polish",
                 against_build=AB, operator_override=True)
    assert a.verdict == "downstream" and a.decided_by == "operator-override"
    assert a.admits() and not is_barred(a)


def test_downstream_gate_verdict_never_auto_admits():
    # A 'downstream' verdict decided by the gate (not an override) can NEVER admit.
    a = Allocation("t", "downstream", "downstream", "x", "gate", against_build=AB)
    assert not a.admits() and is_barred(a)


# ── §7: substrate-adjacent (one hop downstream) — conservative default ───────

def test_adjacent_defaults_to_override_flips_with_flag():
    with pytest.raises(AllocationHalt):  # default: requires an override
        allocate("procedural_texture", "adjacent", "feeds material→render", against_build=AB)
    a = allocate("procedural_texture", "adjacent", "feeds material→render",
                 against_build=AB, adjacent_admits=True)
    assert a.verdict == "admit" and not is_barred(a)
    b = allocate("procedural_texture", "adjacent", "feeds material→render",
                 against_build=AB, operator_override=True)
    assert b.decided_by == "operator-override" and b.admits()


# ── violation #6 + self-policing ─────────────────────────────────────────────

def test_no_allocation_is_barred():
    assert is_barred(None)   # a target with no Allocation entry can't enter the graph


def test_redundant_pass_is_tripped():
    a = allocate("t", "composition", "x", against_build=AB)
    assert detect_redundant_pass("t", [a], new_evidence=False) is True   # surface, don't run
    assert detect_redundant_pass("t", [a], new_evidence=True) is False   # new evidence → ok
    assert detect_redundant_pass("other", [a]) is False                  # different target
    assert detect_redundant_pass("t", []) is False                       # never allocated


def test_unknown_thesis_locus_raises():
    with pytest.raises(ValueError):
        allocate("t", "vibes", "x", against_build=AB)


def test_empty_target_rejected():
    # crucible strengthening: a gate must not admit an unnamed target.
    with pytest.raises(ValueError):
        allocate("", "composition", "x", against_build=AB)
    with pytest.raises(ValueError):
        allocate("   ", "composition", "x", against_build=AB)


# ── Allocation → Ledger projection (RFC Option C) ────────────────────────────

def test_allocation_projects_and_deposits(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LEDGER_DIR", str(tmp_path))
    a = allocate("cops_opencl_fix", "composition", "COP texture → material → render",
                 against_build=AB)
    rec = to_ledger_record(a, timestamp="2026-06-08T00:00:00Z")
    assert rec.kind == "Allocation" and rec.verdict == "admit"
    assert rec.target == "cops_opencl_fix" and rec.decided_by == "gate"
    assert rec.thesis_locus == "composition" and rec.verified_by == "V0_membership"
    res = ledger.deposit(rec)   # V0_membership + against_build → deposits clean
    assert res["ok"] is True
    loaded = json.loads(open(res["path"], encoding="utf-8").read())
    assert loaded["kind"] == "Allocation"
    assert loaded["verdict"] == "admit" and loaded["target"] == "cops_opencl_fix"
