"""Tests for FloorGate provenance-dir FIFO ROTATION (the bounded count cap).

Pins the rotation contract added on top of the Tier-0 provenance hook:

* ``$SYNAPSE_PROVENANCE_MAX_RECORDS`` caps the number of retained record files;
  default 5000, ``<= 0`` (or unparseable) DISABLES rotation (unbounded opt-out).
* After a successful record write the gate FIFO-trims the dir to the cap,
  deleting the OLDEST excess and NEVER the newest.
* RECONCILE-ON-STARTUP: a fresh gate sweeps an over-full dir on the first
  rotation so the cap survives process restarts.
* Rotation is best-effort: an ``os.unlink`` failure during trimming never
  breaks the live op or masks its result, and the record still lands.
* A read-only op triggers NO rotation/deletion (it writes no record).

Rotation lives ENTIRELY in ``floor_gate.py`` — these tests touch only the
public ``FloorGate.wrap`` surface plus the two env vars.
"""

from __future__ import annotations

import os

import pytest

from synapse.core.floor_gate import FloorGate


def _json_files(d):
    """Sorted (== chronological) list of provenance record filenames in ``d``."""
    if not os.path.isdir(d):
        return []
    return sorted(name for name in os.listdir(d) if name.endswith(".json"))


@pytest.fixture
def prov_dir(tmp_path, monkeypatch):
    """Point the FloorGate's provenance root at a tmp dir for the test."""
    d = tmp_path / "provenance"
    monkeypatch.setenv("SYNAPSE_PROVENANCE_DIR", str(d))
    return str(d)


# ---------------------------------------------------------------------------
# FIFO cap: cap+K writes leave exactly cap, and they are the NEWEST cap
# ---------------------------------------------------------------------------

def test_cap_keeps_exactly_newest_cap_files(prov_dir, monkeypatch):
    cap = 5
    extra = 7
    monkeypatch.setenv("SYNAPSE_PROVENANCE_MAX_RECORDS", str(cap))

    gate = FloorGate()
    op_ids = []
    for i in range(cap + extra):
        # mint a record per mutating op; capture the op_id that names its file
        gate.wrap("set_parm", {"i": i}, lambda p: {"ok": True})
        # op_ids in mint order == chronological == filename sort order
    files = _json_files(prov_dir)

    # Exactly `cap` files remain.
    assert len(files) == cap, files

    # They are the NEWEST cap: every surviving file's op-id sequence is among
    # the last `cap` minted. Op-ids end in a zero-padded monotonic seq, so the
    # newest survivors carry the highest sequence numbers.
    surviving_seqs = sorted(int(name.rsplit("-", 1)[1].split(".")[0]) for name in files)
    assert surviving_seqs == list(range(extra + 1, cap + extra + 1)), surviving_seqs
    # The oldest K op-ids (seq 1..extra) are gone.
    assert all(seq > extra for seq in surviving_seqs)


# ---------------------------------------------------------------------------
# RECONCILE-ON-STARTUP: a fresh gate trims an over-full dir on first write
# ---------------------------------------------------------------------------

def test_reconcile_on_startup_trims_overfull_dir(prov_dir, monkeypatch):
    cap = 4
    monkeypatch.setenv("SYNAPSE_PROVENANCE_MAX_RECORDS", str(cap))
    os.makedirs(prov_dir, exist_ok=True)

    # Pre-populate > cap fake records with SORTABLE names (< any real op-id,
    # since real ids start with 'op-2026...'). Name order == chronological.
    pre = [f"aold-{i:04d}.json" for i in range(10)]  # 10 > cap
    for name in pre:
        with open(os.path.join(prov_dir, name), "w", encoding="utf-8") as fh:
            fh.write("{}")
    assert len(_json_files(prov_dir)) == 10

    # Fresh gate (cold deque), write ONE op -> first rotation reconciles + trims.
    gate = FloorGate()
    gate.wrap("set_parm", {"k": 1}, lambda p: {"ok": True})

    files = _json_files(prov_dir)
    assert len(files) == cap, files

    # The one real record survives (newest), plus the NEWEST cap-1 fakes.
    real = [n for n in files if n.startswith("op-")]
    fakes = [n for n in files if n.startswith("aold-")]
    assert len(real) == 1, files
    assert fakes == pre[-(cap - 1):], fakes  # the cap-1 newest fakes retained
    # The oldest fakes were deleted.
    for name in pre[: 10 - (cap - 1)]:
        assert name not in files


def test_reconcile_runs_at_most_once(prov_dir, monkeypatch):
    """The startup sweep seeds the deque only once; later writes don't re-sweep
    (so files written by THIS gate aren't re-counted from disk)."""
    cap = 3
    monkeypatch.setenv("SYNAPSE_PROVENANCE_MAX_RECORDS", str(cap))

    gate = FloorGate()
    for i in range(cap + 4):
        gate.wrap("set_parm", {"i": i}, lambda p: {"ok": True})

    # Steady-state cap holds across many writes (no drift from a re-sweep).
    assert len(_json_files(prov_dir)) == cap


# ---------------------------------------------------------------------------
# Disable: cap <= 0 (and unparseable) => unbounded
# ---------------------------------------------------------------------------

def test_cap_zero_disables_rotation(prov_dir, monkeypatch):
    cap = 5
    monkeypatch.setenv("SYNAPSE_PROVENANCE_MAX_RECORDS", "0")

    gate = FloorGate()
    for i in range(cap + 10):
        gate.wrap("set_parm", {"i": i}, lambda p: {"ok": True})

    assert len(_json_files(prov_dir)) == cap + 10  # nothing deleted


def test_negative_cap_disables_rotation(prov_dir, monkeypatch):
    monkeypatch.setenv("SYNAPSE_PROVENANCE_MAX_RECORDS", "-1")
    gate = FloorGate()
    for i in range(20):
        gate.wrap("set_parm", {"i": i}, lambda p: {"ok": True})
    assert len(_json_files(prov_dir)) == 20


def test_unparseable_cap_disables_rotation(prov_dir, monkeypatch):
    monkeypatch.setenv("SYNAPSE_PROVENANCE_MAX_RECORDS", "not-a-number")
    gate = FloorGate()
    for i in range(15):
        gate.wrap("set_parm", {"i": i}, lambda p: {"ok": True})
    assert len(_json_files(prov_dir)) == 15


def test_unset_cap_uses_default(monkeypatch):
    """With the env unset, the resolved cap is the 5000 default (not disabled)."""
    monkeypatch.delenv("SYNAPSE_PROVENANCE_MAX_RECORDS", raising=False)
    from synapse.core.floor_gate import (
        DEFAULT_PROVENANCE_MAX_RECORDS,
        resolve_provenance_max_records,
    )
    assert resolve_provenance_max_records() == DEFAULT_PROVENANCE_MAX_RECORDS == 5000


# ---------------------------------------------------------------------------
# Best-effort: an unlink failure during rotation never breaks the op
# ---------------------------------------------------------------------------

def test_unlink_failure_during_rotation_does_not_break_op(prov_dir, monkeypatch):
    cap = 2
    monkeypatch.setenv("SYNAPSE_PROVENANCE_MAX_RECORDS", str(cap))

    gate = FloorGate()
    # Fill to the cap cleanly first.
    gate.wrap("set_parm", {"i": 0}, lambda p: {"ok": True})
    gate.wrap("set_parm", {"i": 1}, lambda p: {"ok": True})
    assert len(_json_files(prov_dir)) == cap

    # Now make every unlink raise — the NEXT write would normally evict one.
    def boom_unlink(_path):
        raise OSError("unlink denied")

    monkeypatch.setattr(os, "unlink", boom_unlink)

    sentinel = {"result": "live-op-value"}
    out = gate.wrap("set_parm", {"i": 2}, lambda p: sentinel)

    # The live op still returns its real result (rotation failure swallowed).
    assert out is sentinel
    # The new record still landed on disk (rotation runs AFTER the write).
    files = _json_files(prov_dir)
    assert len(files) == cap + 1, files  # eviction failed but op + record intact


# ---------------------------------------------------------------------------
# Read-only ops trigger NO rotation / deletion
# ---------------------------------------------------------------------------

def test_read_only_op_triggers_no_rotation(prov_dir, monkeypatch):
    cap = 2
    monkeypatch.setenv("SYNAPSE_PROVENANCE_MAX_RECORDS", str(cap))

    gate = FloorGate()
    gate.wrap("set_parm", {"i": 0}, lambda p: {"ok": True})
    gate.wrap("set_parm", {"i": 1}, lambda p: {"ok": True})
    before = _json_files(prov_dir)
    assert len(before) == cap

    # A read-only op writes no record; it must not unlink anything either.
    unlink_calls = []
    real_unlink = os.unlink
    monkeypatch.setattr(os, "unlink", lambda p: unlink_calls.append(p) or real_unlink(p))

    result = gate.wrap("ping", {}, lambda p: {"pong": True})

    assert result == {"pong": True}
    assert _json_files(prov_dir) == before  # untouched
    assert unlink_calls == []  # no rotation fired
