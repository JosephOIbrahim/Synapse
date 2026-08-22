"""M1 — the handle law: one handle per storage URI, one owner.

Evidence this pins: ``harness/memory/notes/AUDIT_2026-08-21.md`` §C.

``get_synapse_memory()`` was an unlocked check-then-create. N threads entering
together each saw ``_global_synapse is None``, each constructed a
``SynapseMemory``, and N-1 of them were orphaned **while still holding a Moneta
handle on the same storage URI** — and, because
``MonetaBackedStore.from_storage_dir`` registers ``atexit.register(store.close)``
(``moneta_store.py:377-378``), the orphan is pinned alive for the rest of the
process. Moneta enforces single-owner URI locking, so the winner of the module
global is frequently the loser of the lock.

The second half of the same defect is ``reset_synapse_memory()``: it called
``save()`` and dropped the reference without ``close()``, so the URI lock was
never released and the very next accessor call fell back to JSONL with
``_BACKEND_FALLBACK`` reason ``init failed: MonetaResourceLockedError``. That is
the composed regression — it bites on the SECOND action, not the first.

Every test here is hermetic: the project path is pinned at a ``tmp_path`` so
nothing resolves a real ``hou`` scene or writes into the repo.
"""

import threading
import time
from pathlib import Path

import pytest

from synapse.memory import store as store_mod
from synapse.memory import moneta_runtime as mr


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_global():
    """Never let a test inherit or leak the process-global handle."""
    prior = store_mod._global_synapse
    store_mod._global_synapse = None
    store_mod._BACKEND_FALLBACK = None
    yield
    leaked = store_mod._global_synapse
    if leaked is not None:
        closer = getattr(getattr(leaked, "store", None), "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:  # noqa: BLE001 -- teardown must not mask a verdict
                pass
    store_mod._global_synapse = prior
    store_mod._BACKEND_FALLBACK = None


def _pin_project(monkeypatch, tmp_path, delay=0.0, built=None, hook=None):
    """Force every ``SynapseMemory()`` to build at *tmp_path*.

    ``delay`` amplifies a window that genuinely exists — the real ``__init__``
    resolves a project path, may migrate a legacy directory (``shutil.copytree``,
    ``store.py:1156``) and constructs a backend store. The race is not created by
    the sleep; the sleep only makes an existing race observable on every run
    instead of most runs. ``test_concurrent_accessors_build_one_object`` runs the
    same shape with NO delay to show that.
    """
    real_init = store_mod.SynapseMemory.__init__

    def patched(self, project_path=None):
        if delay:
            time.sleep(delay)
        if hook is not None:
            hook()
        real_init(self, project_path=str(tmp_path))
        if built is not None:
            built.append(self)

    monkeypatch.setattr(store_mod.SynapseMemory, "__init__", patched)
    return real_init


def _run_threads(n, fn, timeout=30.0):
    """Fire *n* barrier-synchronised threads at *fn*; return their results."""
    barrier = threading.Barrier(n)
    results = [None] * n
    errors = []

    def worker(i):
        try:
            barrier.wait(timeout=timeout)
            results[i] = fn()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True)
               for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout)
    assert not [t for t in threads if t.is_alive()], "worker thread hung"
    assert not errors, f"worker raised: {errors!r}"
    return results


# ---------------------------------------------------------------------------
# 1 · the race itself
# ---------------------------------------------------------------------------

def test_concurrent_accessors_build_one_object_amplified(monkeypatch, tmp_path):
    """Deterministic form: with a 50ms constructor, 8 threads must still get one
    object and must construct exactly once."""
    built = []
    _pin_project(monkeypatch, tmp_path, delay=0.05, built=built)

    handles = _run_threads(8, store_mod.get_synapse_memory)

    assert len({id(h) for h in handles}) == 1, (
        f"{len({id(h) for h in handles})} distinct SynapseMemory objects handed "
        "to 8 callers — each orphan holds a Moneta handle on the same URI"
    )
    assert len(built) == 1, (
        f"{len(built)} SynapseMemory objects constructed; the handle law allows 1"
    )
    assert handles[0] is store_mod._global_synapse


def test_concurrent_accessors_build_one_object(monkeypatch, tmp_path):
    """Unamplified form — no injected sleep, 16 threads. The cartographer leg
    measured 8/8 distinct objects 3/3 runs on HEAD with no amplification
    (``harness/memory/bus/memory_m1_cartographer.json``); after the fix the lock
    makes single-identity unconditional, so this cannot flake green-to-red."""
    built = []
    _pin_project(monkeypatch, tmp_path, built=built)

    handles = _run_threads(16, store_mod.get_synapse_memory)

    assert len({id(h) for h in handles}) == 1
    assert len(built) == 1


def test_backwards_compat_aliases_share_the_one_handle(monkeypatch, tmp_path):
    """``get_nexus_memory`` / ``get_engram`` are the same authority, not two."""
    built = []
    _pin_project(monkeypatch, tmp_path, delay=0.02, built=built)

    fns = [store_mod.get_synapse_memory, store_mod.get_nexus_memory,
           store_mod.get_engram, store_mod.get_synapse_memory]
    handles = _run_threads(4, lambda: fns.pop()())

    assert len({id(h) for h in handles}) == 1
    assert len(built) == 1


# ---------------------------------------------------------------------------
# 2 · never orphan a handle (re-entrancy)
# ---------------------------------------------------------------------------

def test_reentrant_construction_does_not_deadlock_or_orphan(monkeypatch, tmp_path):
    """A construction path that re-enters the accessor must neither self-deadlock
    (a plain ``Lock`` would) nor leave two live handles on one URI.

    Runs on a daemon thread with a bounded join so a regression fails the test
    instead of hanging the suite.
    """
    built = []
    depth = {"n": 0}

    def reenter():
        depth["n"] += 1
        if depth["n"] == 1:
            store_mod.get_synapse_memory()  # re-enter from inside construction

    _pin_project(monkeypatch, tmp_path, built=built, hook=reenter)

    closed = []
    monkeypatch.setattr(store_mod, "_close_memory_quietly",
                        lambda mem, why: closed.append(mem), raising=False)

    out = []
    t = threading.Thread(target=lambda: out.append(store_mod.get_synapse_memory()),
                         daemon=True)
    t.start()
    t.join(timeout=15.0)

    assert not t.is_alive(), "get_synapse_memory() self-deadlocked on re-entry"
    assert out and out[0] is store_mod._global_synapse
    # Re-entrancy legitimately builds two objects; only one may survive as an
    # owner, and the loser must be CLOSED, never silently dropped.
    assert len(built) - len(closed) == 1, (
        f"built={len(built)} closed={len(closed)} — a live handle was orphaned"
    )


# ---------------------------------------------------------------------------
# 3 · reset releases the handle (the second-action defect)
# ---------------------------------------------------------------------------

class _RecordingStore:
    """Stands in for a store that owns an external lock (Moneta does)."""

    def __init__(self):
        self.saved = 0
        self.closed = 0

    def save(self):
        self.saved += 1

    def close(self):
        self.closed += 1


def test_reset_closes_the_store_handle(monkeypatch, tmp_path):
    _pin_project(monkeypatch, tmp_path)
    mem = store_mod.get_synapse_memory()
    recorder = _RecordingStore()
    mem.store = recorder

    store_mod.reset_synapse_memory()

    assert store_mod._global_synapse is None
    assert recorder.closed == 1, (
        "reset dropped the reference without close() — the storage URI stays "
        "locked by an unreachable object for the life of the process"
    )


def test_reset_survives_a_store_whose_close_raises(monkeypatch, tmp_path):
    """Reset must clear the global even when teardown fails; a store that
    refuses to close must not wedge the accessor forever."""
    _pin_project(monkeypatch, tmp_path)
    mem = store_mod.get_synapse_memory()

    class _Angry(_RecordingStore):
        def close(self):
            super().close()
            raise RuntimeError("boom")

    angry = _Angry()
    mem.store = angry

    store_mod.reset_synapse_memory()

    assert angry.closed == 1
    assert store_mod._global_synapse is None
    assert store_mod.get_synapse_memory() is not mem


# ---------------------------------------------------------------------------
# 4 · the composed regression, on the real substrate
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not mr.moneta_available(),
                    reason=f"Moneta not importable: {mr.import_error()}")
def test_reset_then_reopen_keeps_the_moneta_backend(monkeypatch, tmp_path):
    """Second-action test. get -> reset -> get must still be Moneta-backed.

    On HEAD the first handle keeps the ``moneta-file://`` URI lock after reset,
    so the second construction raises ``MonetaResourceLockedError`` and is
    silently downgraded to JSONL.
    """
    from synapse.memory.moneta_store import MonetaBackedStore

    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    _pin_project(monkeypatch, tmp_path)

    first = store_mod.get_synapse_memory()
    if not isinstance(first.store, MonetaBackedStore):
        pytest.skip(f"moneta backend did not serve: {store_mod.backend_fallback()}")

    store_mod.reset_synapse_memory()
    second = store_mod.get_synapse_memory()

    assert second is not first
    assert isinstance(second.store, MonetaBackedStore), (
        "backend downgraded to JSONL after reset: "
        f"{store_mod.backend_fallback()}"
    )
    assert store_mod.backend_fallback() is None


@pytest.mark.skipif(not mr.moneta_available(),
                    reason=f"Moneta not importable: {mr.import_error()}")
def test_reset_then_reopen_keeps_the_shadow_backend(monkeypatch, tmp_path):
    """The shadow arrangement owns a Moneta handle behind a JSONL primary.

    ``ShadowMemoryStore`` exposed no ``close()``, so releasing it fell through
    to ``save()`` and the ``moneta-file://`` URI stayed held — the same
    second-action downgrade as the moneta backend, one layer down.
    """
    from synapse.memory.moneta_store import MonetaBackedStore
    from synapse.memory.shadow_store import ShadowMemoryStore

    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "shadow")
    _pin_project(monkeypatch, tmp_path)

    first = store_mod.get_synapse_memory()
    if not isinstance(first.store, ShadowMemoryStore):
        pytest.skip(f"shadow backend did not serve: {store_mod.backend_fallback()}")

    store_mod.reset_synapse_memory()
    second = store_mod.get_synapse_memory()

    assert isinstance(second.store, ShadowMemoryStore), (
        f"shadow downgraded to JSONL after reset: {store_mod.backend_fallback()}"
    )
    assert isinstance(second.store.shadow, MonetaBackedStore)
    assert store_mod.backend_fallback() is None


# ---------------------------------------------------------------------------
# 5 · guards on what the fix must NOT break
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not mr.moneta_available(),
                    reason=f"Moneta not importable: {mr.import_error()}")
def test_ephemeral_multi_store_still_works():
    """Adjudication D7: ``MonetaConfig.ephemeral()`` auto-generates a UNIQUE
    storage_uri (``moneta_runtime.py:686-704``) so tests can hold several stores
    at once. A process-scalar handle authority would break that; the M1 fix must
    not."""
    h1 = mr.make_ephemeral(embedding_dim=8)
    try:
        h2 = mr.make_ephemeral(embedding_dim=8)
        try:
            assert h1 is not h2
        finally:
            h2.close()
    finally:
        h1.close()


def test_census_names_both_authorities_and_constructs_nothing(monkeypatch, tmp_path):
    """One place names both real authorities. It is an OBSERVER, not a third
    authority: calling it while no handle exists must leave none behind."""
    _pin_project(monkeypatch, tmp_path)
    assert store_mod._global_synapse is None

    census = store_mod.memory_handle_census()

    assert set(census) == {"project_memory", "ledger_findings"}
    assert store_mod._global_synapse is None, "the census CONSTRUCTED a handle"
    assert census["project_memory"]["live"] is False
    assert census["project_memory"]["storage_uri"] is None

    mem = store_mod.get_synapse_memory()
    census = store_mod.memory_handle_census()
    assert census["project_memory"]["live"] is True
    assert census["project_memory"]["storage_uri"] == str(mem.storage_dir)
    # Every entry names the module:symbol it is reporting on, so the census is
    # traceable back to the code it describes rather than being folklore.
    for entry in census.values():
        assert Path(entry["authority"].split(":")[0]).name.endswith(".py")
