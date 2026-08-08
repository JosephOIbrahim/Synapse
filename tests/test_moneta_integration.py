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


def test_vector_recall_through_facade(tmp_path, monkeypatch):
    """Vector recall works through the SynapseMemory facade with Moneta backend.

    The facade's ``search()`` method triggers vector recall when ``text`` is
    set (embedding + Moneta vector query). This verifies the integration path
    callers actually use — not just the adapter in isolation.
    """
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    from synapse.memory.store import SynapseMemory
    from synapse.memory.moneta_store import MonetaBackedStore

    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    try:
        assert isinstance(sm.store, MonetaBackedStore)

        # Add diverse memories — some karma-related, some not.
        sm.add(content="render the karma beauty pass tonight",
               memory_type=MemoryType.ACTION)
        sm.add(content="solaris stage assembly with karma render settings",
               memory_type=MemoryType.ACTION)
        sm.add(content="material binding failed on the hero asset",
               memory_type=MemoryType.ERROR)
        sm.add(content="note about denoiser settings for the render",
               memory_type=MemoryType.NOTE)

        # Vector recall via text search — should find karma-related memories.
        hits = sm.search("karma", limit=5)
        assert len(hits) >= 2, (
            "Vector recall through facade returned %d results, expected >= 2"
            % len(hits)
        )
        karma_hits = [h for h in hits if "karma" in h.memory.content]
        assert len(karma_hits) >= 2, (
            "Vector recall through facade found %d karma-related memories, "
            "expected >= 2" % len(karma_hits)
        )
    finally:
        sm.store.close()


# The subprocess body for the atexit durability tests. Deposits N memories and
# leaves -- deliberately WITHOUT calling save() or close(), exactly as the
# production SynapseMemory path does. How it exits is the variable.
#
# CI0 -- WHY N IS 3 AND NOT 1. These two tests deposited ONE memory, and the
# negative control asserted a hard exit persisted NOTHING. That assertion was
# false about the system, and CI was reporting it as a failure honestly:
# MonetaBackedStore.__init__ sets `_last_save = 0.0`, so add()'s periodic-save
# check (`now - _last_save >= _save_interval`) is ALWAYS true on the first
# deposit -- the very first add() force-saves, synchronously, every time.
#
# Measured (moneta v1.2.0-rc3, deposits -> rows in .moneta/snapshot.json):
#
#     deposits   clean sys.exit(0)   hard os._exit(0)
#     --------   -----------------   ----------------
#            1                   1                  1     <- negative control could not fail
#            2                   2                  1
#            3                   3                  1
#
# So at N=1 the positive test passed for the WRONG REASON: persistence came
# from that first-add save, not from the atexit hook it claimed to prove --
# Law 1, a check that could not fail. At N>=2 the split is real and both
# controls become load-bearing: deposit #1 is covered by the first-add save,
# deposits #2..N ONLY by atexit. N=3 leaves margin (3 vs 1) so a single
# off-by-one in either mechanism is visible in the numbers.
#
# The first-add save is therefore PINNED here as observed behaviour, not
# endorsed as design -- moneta_store's own docstring says "there is no
# per-deposit fsync", which is untrue of the first deposit. Whether to keep it
# or initialise `_last_save = time.monotonic()` is a durability-posture call
# and is raised in the CI0 receipt's for_ruling[], not decided here.
_DEPOSITS = 3

_DEPOSIT_THEN_EXIT = """
import sys
sys.path.insert(0, {root!r})
from synapse.memory.moneta_store import MonetaBackedStore
from synapse.memory.models import Memory, MemoryType
s = MonetaBackedStore.from_storage_dir({proj!r})
for _i in range({n}):
    s.add(Memory(content="deposit %d, never explicitly saved" % _i,
                 memory_type=MemoryType.DECISION))
{exit_call}
"""


def _run_deposit_subprocess(tmp_path, exit_call, n=_DEPOSITS):
    import subprocess
    proj = str(tmp_path / "proj")
    code = _DEPOSIT_THEN_EXIT.format(
        root=str(_ROOT / "python"), proj=proj, exit_call=exit_call, n=n)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return proj


def test_atexit_snapshots_deposits_on_clean_exit(tmp_path):
    """The reachable Moneta bug: deposit() writes only the in-memory ECS, and
    the production path never calls save(). A clean interpreter exit must still
    persist the deposits -- via the atexit hook registered in from_storage_dir.

    Unlike test_durable_reload_across_owners above, this NEVER calls save() or
    close() in the writer: `sys.exit(0)` runs interpreter shutdown, which fires
    atexit. That is the exact production condition (a normal shutdown), and it
    failed before the hook existed.

    Deposits #2 and #3 are the load-bearing ones -- #1 is force-saved by the
    first-add timer regardless of how the process ends (see _DEPOSITS above).
    """
    from synapse.memory.moneta_store import MonetaBackedStore
    proj = _run_deposit_subprocess(tmp_path, "sys.exit(0)")

    s = MonetaBackedStore.from_storage_dir(proj)
    try:
        assert s.count() == _DEPOSITS, (
            "clean-exit deposits were lost -- atexit did not fire (deposit #1 "
            "survives the first-add save on its own, so anything less than "
            f"{_DEPOSITS} means the hook is not persisting #2..#{_DEPOSITS})")
        contents = {m.content for m in s.get_by_type(MemoryType.DECISION)}
        assert contents == {
            "deposit %d, never explicitly saved" % i for i in range(_DEPOSITS)}
    finally:
        s.close()


def test_hard_exit_loses_the_unsnapshotted_deposits(tmp_path):
    """FIX_IS_REAL companion: os._exit(0) bypasses atexit, so every deposit
    after the first-add save is lost. This proves the test above is not vacuous
    -- persistence of #2..#N there comes from the hook, not from an incidental
    save -- and documents the bound the atexit fix does NOT close (kill -9 /
    native crash, the crash-harness class).

    Renamed from test_hard_exit_loses_the_deposit (singular): the old name
    asserted a total loss that never happens, because deposit #1 is always
    snapshotted synchronously.
    """
    from synapse.memory.moneta_store import MonetaBackedStore
    proj = _run_deposit_subprocess(tmp_path, "import os; os._exit(0)")

    s = MonetaBackedStore.from_storage_dir(proj)
    try:
        assert s.count() == 1, (
            "hard exit persisted %d of %d deposits, expected exactly 1 (the "
            "first-add save). More means some incidental save is covering "
            "#2..#%d, so the clean-exit test's durability cannot be attributed "
            "to atexit; fewer means the first-add save stopped firing and the "
            "clean-exit test's baseline moved." % (s.count(), _DEPOSITS, _DEPOSITS))
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


def test_save_timer_persists_across_interval(tmp_path):
    """The periodic save in add() fires when the interval elapses.

    Mechanism: add() checks ``now - _last_save >= _save_interval`` and calls
    save() when true.  We reset _last_save to the current monotonic clock so
    the first add does NOT trigger a save, then wait past the short interval
    so the second add DOES trigger one.  Reopening the store should see both
    memories.
    """
    import time as _time
    from synapse.memory.moneta_store import MonetaBackedStore
    from synapse.memory.models import Memory, MemoryType

    s1 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        # Reset the timer reference so the first add does not trigger a save.
        s1._last_save = _time.monotonic()
        s1._save_interval = 0.1  # 100 ms

        s1.add(Memory(content="first", memory_type=MemoryType.NOTE))
        assert s1.count() == 1, "first add should succeed"

        # Wait past the interval so the second add triggers a periodic save.
        _time.sleep(0.2)
        s1.add(Memory(content="second", memory_type=MemoryType.NOTE))
        assert s1.count() == 2, "second add should succeed"
    finally:
        s1.close()

    # Reopen and verify both memories survived the periodic save.
    s2 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        assert s2.count() == 2, (
            "periodic save did not persist -- expected 2 memories, got %d"
            % s2.count()
        )
        contents = {m.content for m in s2._iter_memories()}
        assert "first" in contents
        assert "second" in contents
    finally:
        s2.close()


def test_save_timer_does_not_fire_with_long_interval(tmp_path):
    """Negative control: with a long interval the periodic save never fires,
    so memories are lost on close.  Proves the positive test above is not
    vacuous -- persistence there comes from the interval-triggered save, not
    from incidental persistence.

    NOTE: close() calls save() unconditionally (line 449), so we must
    prevent save() from running to isolate the timer path.  We set _closed
    before close() so it returns immediately, then close the handle manually
    to release the URI lock for the reopen.
    """
    import time as _time
    from synapse.memory.moneta_store import MonetaBackedStore
    from synapse.memory.models import Memory, MemoryType

    s1 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        s1._last_save = _time.monotonic()
        s1._save_interval = 9999.0  # effectively never

        s1.add(Memory(content="orphan", memory_type=MemoryType.NOTE))
        assert s1.count() == 1
    finally:
        # Prevent close() from calling save() so the timer path is isolated.
        s1._closed = True
        s1.close()  # returns immediately, no save
        # Release the URI lock so s2 can open the same storage dir.
        close_fn = getattr(s1._handle, "close", None)
        if callable(close_fn):
            close_fn()

    s2 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        assert s2.count() == 0, (
            "expected 0 memories (save timer never fired), got %d"
            % s2.count()
        )
    finally:
        s2.close()
