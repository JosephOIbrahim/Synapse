"""Track C · Phase 1 — the rung-scale migration (v5 §2 / §4a.2). Logic/CI tier.

Pins, all pxr-independent / bridgeless:
  · the five rungs are single-sourced (DOC-1 conformance — bound to the v5 spec)
  · the legacy read shim is conservative (V1 → V1_cook, NEVER V1_output)
  · ledger.deposit validates the five-token set, fail-closed (empty AND unknown)
  · the VerifiedClaim Floor hook: doc_only / V0_membership may NOT back "verified"

The LIVE rung-ASSIGNMENT tests (probe→V0_membership, createNode+cook→V1_cook,
intended-output→V1_output) are bridge-gated and DEFERRED (this run is bridgeless);
they sit behind SYNAPSE_INTEGRATION and are recorded as owed in the Ledger.
"""

import os
from pathlib import Path

import pytest

from synapse.science import rungs
from synapse.science.rungs import (
    RUNGS, VERIFYING_RUNGS, LAYERS, migrate_verified_by, is_verifying,
)
from synapse.science.verified_claim import (
    VerifiedClaim, assert_verified_claim, FloorViolation,
)
from synapse.memory import ledger

_ROOT = Path(__file__).resolve().parent.parent


# ── the five-rung scale, single-sourced ──────────────────────────────────────

def test_five_rungs_canonical():
    assert RUNGS == ("doc_only", "V0_membership", "V1_cook", "V1_output", "V1-degraded")
    assert VERIFYING_RUNGS == ("V1_cook", "V1_output", "V1-degraded")
    assert LAYERS == ("L0", "L1", "L2")


def test_rungs_single_sourced_doc_conformance():
    """DOC-1: the five tokens live in ONE place (science.rungs) and BOTH the v5
    spec and the ratified RFC name them — bind doc↔code so the scale can't drift
    silently. (test_five_rungs_canonical already pins the exact 5-tuple, so a
    sneaked-in 6th rung fails there.)"""
    assert ledger.RUNGS is RUNGS          # one object — no shadow copy in ledger
    for doc in ("SYNAPSE_SCIENCE_HARNESS_v5.md", "RFC_allocation_exposure_schema.md"):
        text = (_ROOT / "docs" / doc).read_text(encoding="utf-8")
        for token in RUNGS:
            assert token in text, f"docs/{doc} no longer names rung {token!r} (doc/code drift)"


def test_shim_recovers_annotated_legacy_tokens():
    """BLOCKER-1 fix: annotated legacy tokens must NOT silently drop on backfill
    (D-2 lossless). The leading token is recovered, conservatively."""
    assert migrate_verified_by("V1 (deterministic pin, build-agnostic)") == "V1_cook"
    assert migrate_verified_by("V0 (citation self-check + live grep)") == "V0_membership"
    assert migrate_verified_by("V1-degraded (live unavailable)") == "V1-degraded"
    assert migrate_verified_by("V1 (foo)") != "V1_output"   # never auto-promotes
    assert migrate_verified_by("bogus (note)") == ""        # still rejects unknown


# ── the legacy read shim — conservative ──────────────────────────────────────

def test_shim_maps_legacy_conservatively():
    assert migrate_verified_by("V0") == "V0_membership"
    assert migrate_verified_by("V1") == "V1_cook"          # conservative
    assert migrate_verified_by("V1") != "V1_output"        # NEVER auto-promoted
    assert migrate_verified_by("V1-degraded") == "V1-degraded"


def test_shim_passes_through_v5_and_rejects_unknown():
    for tok in RUNGS:
        assert migrate_verified_by(tok) == tok
    assert migrate_verified_by("bogus") == ""
    assert migrate_verified_by("") == ""
    assert migrate_verified_by("  V1_cook  ") == "V1_cook"  # whitespace-tolerant


# ── deposit validates the five-token set, fail-closed ────────────────────────

def _rec(verified_by="V1_cook"):
    return ledger.LedgerRecord(
        kind="Confirmation", verified_by=verified_by, against_build="21.0.631",
        question="q", timestamp="2026-06-08T00:00:00Z",
    )


def test_deposit_accepts_each_v5_rung(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LEDGER_DIR", str(tmp_path))
    for tok in RUNGS:
        res = ledger.deposit(_rec(tok))
        assert res["ok"] is True


def test_deposit_rejects_unknown_token(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LEDGER_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        ledger.deposit(_rec("V1"))        # legacy must be migrated first
    with pytest.raises(ValueError):
        ledger.deposit(_rec("bogus"))     # unknown
    assert list(tmp_path.glob("*.json")) == []  # fail-closed: nothing written


# ── the VerifiedClaim Floor hook — "verified" is reserved ────────────────────

def _claim(**kw):
    base = dict(eval_signal_fired=True, eval_signal="cook ok", verified_by="V1_cook",
                verified_layer="L1", artifact_path="shared/bridge.py",
                against_build="21.0.631")
    base.update(kw)
    return VerifiedClaim(**base)


def test_verifying_rungs_back_verified():
    for tok in VERIFYING_RUNGS:
        assert _claim(verified_by=tok).is_valid()
        assert is_verifying(tok)


def test_doc_only_and_membership_cannot_back_verified():
    for tok in ("doc_only", "V0_membership"):
        with pytest.raises(FloorViolation):
            assert_verified_claim(_claim(verified_by=tok))
        assert not is_verifying(tok)


def test_verified_claim_requires_layer_build_signal_and_inrepo_artifact():
    with pytest.raises(FloorViolation):
        assert_verified_claim(_claim(verified_layer="L3"))          # not an L0-L2 layer
    with pytest.raises(FloorViolation):
        assert_verified_claim(_claim(against_build=""))             # Task B
    with pytest.raises(FloorViolation):
        assert_verified_claim(_claim(eval_signal_fired=False))      # no signal
    with pytest.raises(FloorViolation):
        assert_verified_claim(_claim(artifact_path="/abs/outside")) # POSIX absolute
    with pytest.raises(FloorViolation):
        assert_verified_claim(_claim(artifact_path="..\\..\\..\\etc\\passwd"))  # win32 traversal (BLOCKER-2)
    with pytest.raises(FloorViolation):
        assert_verified_claim(_claim(artifact_path="../../etc/passwd"))         # POSIX traversal
    with pytest.raises(FloorViolation):
        assert_verified_claim(_claim(artifact_path="C:\\Windows\\System32"))    # drive-absolute
    with pytest.raises(FloorViolation):
        assert_verified_claim(_claim(artifact_path=""))             # no provenance


def test_inrepo_relative_artifact_accepted():
    """The in-repo guard must not over-reject legitimate relative repo paths."""
    for ok in ("shared/bridge.py", "python/synapse/science/rungs.py", "tests/x.py"):
        assert _claim(artifact_path=ok).is_valid(), f"{ok} wrongly rejected"


# ── LIVE rung-assignment — DEFERRED (bridgeless this run) ─────────────────────

@pytest.mark.skipif(
    not os.environ.get("SYNAPSE_INTEGRATION"),
    reason="live rung assignment (V0_membership/V1_cook/V1_output) needs the bridge "
           "— deferred bridgeless; owed on bridge restore (Ledger)",
)
def test_live_rung_assignment_placeholder():  # pragma: no cover - integration only
    # When wired: probe membership → V0_membership; createNode + cook(force=True) +
    # no errors → V1_cook; flipbook pixel sample / reproduced-then-resolved bug →
    # V1_output. Bridge-gated; not run in CI.
    raise AssertionError("integration harness not wired this bridgeless run")
