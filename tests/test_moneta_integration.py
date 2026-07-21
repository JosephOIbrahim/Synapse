"""Mile 6 — system-level integration of the Moneta backend.

Verifies the composed system through the real SynapseMemory facade (the API
callers use), not the adapter in isolation:

  * AP3 — facade methods (add/decision/note/action/get_decisions/get_recent/
    search) work unchanged through the Moneta backend.
  * AP4 — the gauge invariant: the metrics gauge reads ``store.count()``
    (handlers.py:1166), which under Moneta is ``ecs.n`` — so gauge == count by
    construction, for any backend.
  * AP7 — replay determinism: identical inputs + the pinned HashEmbedder ->
    identical engine state.
  * FC4 seam — single-owner URI lock: a second handle on the same storage dir
    is refused. (The async-server deadlock check is live-gated; see the ship
    report — it needs the running FastMCP server and is not simulated here.)
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import Memory, MemoryQuery, MemoryType  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)

DIM = 256


def test_facade_e2e_through_moneta_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    from synapse.memory.store import SynapseMemory
    from synapse.memory.moneta_store import MonetaBackedStore

    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    try:
        assert isinstance(sm.store, MonetaBackedStore)
        sm.decision(decision="use Moneta as the backend", reasoning="kills divergence")
        sm.note("a routine note")
        sm.action(action="created /obj/geo1")

        assert sm.store.count() == 3
        assert len(sm.get_decisions()) == 1
        assert sm.get_decisions()[0].memory_type == MemoryType.DECISION
        assert len(sm.get_recent(10)) == 3
        hits = sm.search("Moneta", limit=5)
        assert any("Moneta" in h.memory.content for h in hits)
    finally:
        sm.store.close()


def test_gauge_invariant_holds_under_moneta(tmp_path, monkeypatch):
    # AP4: the gauge IS store.count(); under Moneta that is ecs.n. They cannot
    # diverge the way the old JSONL gauge did (it read a dead accessor).
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    from synapse.memory.store import SynapseMemory

    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    try:
        for i in range(7):
            sm.add(content=f"memory {i}", memory_type=MemoryType.NOTE)
        gauge = sm.store.count()          # what handlers.py:1166 emits
        truth = len(sm.store.all())       # actual stored entities
        assert gauge == truth == 7
    finally:
        sm.store.close()


def test_replay_determinism_same_inputs_same_state():
    # AP7: same memories + same pinned embedder -> identical engine state.
    from synapse.memory.moneta_store import MonetaBackedStore

    corpus = [
        Memory(content="alpha", memory_type=MemoryType.NOTE, tags=["a"],
               created_at="2026-01-01T00:00:00Z"),
        Memory(content="beta decision", memory_type=MemoryType.DECISION,
               created_at="2026-01-02T00:00:00Z"),
        Memory(content="gamma", memory_type=MemoryType.ACTION, keywords=["g"],
               created_at="2026-01-03T00:00:00Z"),
    ]

    def build_state():
        s = MonetaBackedStore(mr.make_ephemeral(embedding_dim=DIM), HashEmbedder(dim=DIM))
        for m in corpus:
            s.add(m)
        return sorted(
            ((row.payload, tuple(row.semantic_vector)) for row in s._handle.ecs.iter_rows()),
            key=lambda t: t[0],
        )

    assert build_state() == build_state()


def test_single_owner_uri_lock_is_enforced(tmp_path):
    # FC4 seam: one durable store per project dir. A second handle on the same
    # dir must be refused so two owners can never race the single-writer ECS.
    from synapse.memory.moneta_store import MonetaBackedStore

    s1 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        with pytest.raises(Exception) as ei:
            MonetaBackedStore.from_storage_dir(tmp_path / "proj")
        assert "lock" in str(ei.value).lower() or "locked" in type(ei.value).__name__.lower()
    finally:
        s1.close()
    # After release, a fresh owner acquires cleanly and reloads prior state.
    s2 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        assert isinstance(s2.count(), int)
    finally:
        s2.close()


def test_durable_reload_across_owners(tmp_path):
    # The persistent path survives close/reopen (snapshot + WAL).
    from synapse.memory.moneta_store import MonetaBackedStore

    s1 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    s1.add(Memory(content="persist across restart", memory_type=MemoryType.DECISION))
    s1.save()
    s1.close()

    s2 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        assert s2.count() == 1
        assert s2.get_by_type(MemoryType.DECISION)[0].content == "persist across restart"
    finally:
        s2.close()


# The subprocess body for the atexit durability tests. Deposits ONE memory and
# leaves -- deliberately WITHOUT calling save() or close(), exactly as the
# production SynapseMemory path does. How it exits is the variable.
_DEPOSIT_THEN_EXIT = """
import sys
sys.path.insert(0, {root!r})
from synapse.memory.moneta_store import MonetaBackedStore
from synapse.memory.models import Memory, MemoryType
s = MonetaBackedStore.from_storage_dir({proj!r})
s.add(Memory(content="deposited, never explicitly saved", memory_type=MemoryType.DECISION))
{exit_call}
"""


def _run_deposit_subprocess(tmp_path, exit_call):
    import subprocess
    proj = str(tmp_path / "proj")
    code = _DEPOSIT_THEN_EXIT.format(
        root=str(_ROOT / "python"), proj=proj, exit_call=exit_call)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return proj


def test_atexit_snapshots_deposits_on_clean_exit(tmp_path):
    """The reachable Moneta bug: deposit() writes only the in-memory ECS, and
    the production path never calls save(). A clean interpreter exit must still
    persist the deposit -- via the atexit hook registered in from_storage_dir.

    Unlike test_durable_reload_across_owners above, this NEVER calls save() or
    close() in the writer: `sys.exit(0)` runs interpreter shutdown, which fires
    atexit. That is the exact production condition (a normal shutdown), and it
    failed before the hook existed.
    """
    from synapse.memory.moneta_store import MonetaBackedStore
    proj = _run_deposit_subprocess(tmp_path, "sys.exit(0)")

    s = MonetaBackedStore.from_storage_dir(proj)
    try:
        assert s.count() == 1, "clean-exit deposit was lost -- atexit did not fire"
        assert s.get_by_type(MemoryType.DECISION)[0].content == (
            "deposited, never explicitly saved")
    finally:
        s.close()


def test_hard_exit_loses_the_deposit(tmp_path):
    """FIX_IS_REAL companion: os._exit(0) bypasses atexit, so the deposit is
    lost. This proves the test above is not vacuous -- persistence there comes
    from the hook, not from some incidental save -- and documents the bound the
    atexit fix does NOT close (kill -9 / native crash, the crash-harness class).
    """
    from synapse.memory.moneta_store import MonetaBackedStore
    proj = _run_deposit_subprocess(tmp_path, "import os; os._exit(0)")

    s = MonetaBackedStore.from_storage_dir(proj)
    try:
        assert s.count() == 0, (
            "hard exit unexpectedly persisted -- the durability of the clean-exit "
            "test cannot be attributed to atexit")
    finally:
        s.close()


def test_protected_floor_thresholds_pin_consolidation_coupling():
    """P0-6 / C1 pin. Resolved against the installed consolidation.py: classify()
    is the ONLY staging path (should_run at :89 is a trigger, not a classifier),
    so the audit's "second staging path" does not exist -- the contested probe
    differed only in attended_count.

    What genuinely matters is the coupling between SYNAPSE's protected_floor and
    Moneta's thresholds, which live in a SEPARATE repo on a SEPARATE release
    train. This asserts the two invariants SYNAPSE relies on, so a moneta upgrade
    that moves either threshold fails loud instead of silently changing whether
    a "protected" memory can be evicted:

      * floor > PRUNE_UTILITY_THRESHOLD  -> protected memories are never pruned
        (the dangerous one: if a future threshold rose above 0.9, pinned
        memories would become deletable).
      * floor >= STAGE_UTILITY_THRESHOLD -> protected memories never stage to the
        cold tier. For SYNAPSE that is intended, not a bug: it never reads the
        cold USD tier (MockUsdTarget), and keeping pinned memories hot is the
        goal. The "stall" is real as a mechanism and inert as an impact.
    """
    from synapse.memory.moneta_store import _DEFAULT_PROTECTED_FLOOR
    from moneta.consolidation import (
        PRUNE_UTILITY_THRESHOLD, STAGE_UTILITY_THRESHOLD,
    )
    assert _DEFAULT_PROTECTED_FLOOR > PRUNE_UTILITY_THRESHOLD, (
        "protected memories must never fall in the prunable band -- a moneta "
        "upgrade moved PRUNE_UTILITY_THRESHOLD above %.3f"
        % _DEFAULT_PROTECTED_FLOOR)
    assert _DEFAULT_PROTECTED_FLOOR >= STAGE_UTILITY_THRESHOLD, (
        "protected-floor/stage-threshold coupling changed upstream -- re-verify "
        "the consolidation posture")
