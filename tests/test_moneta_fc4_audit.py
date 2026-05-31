"""FC4 thread-safety + prune auditability for MonetaBackedStore.

Closes the one staged gap: the Moneta backend is now thread-safe BY
CONSTRUCTION (a serialization RLock), and the one destructive op
(run_sleep_pass) is auditable (returns/logs what it pruned). Proven standalone
— no live Houdini needed. Skips cleanly where Moneta is absent.
"""

import logging
import sys
import threading
import time
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

DIM = 64


def _store(**cfg):
    from synapse.memory.moneta_store import MonetaBackedStore
    return MonetaBackedStore(mr.make_ephemeral(embedding_dim=DIM, **cfg), HashEmbedder(dim=DIM))


def _backdate(store, seconds_ago=100_000):
    ecs = store._handle.ecs
    past = time.time() - seconds_ago
    for i in range(len(ecs._last_evaluated)):
        ecs._last_evaluated[i] = past


def _assert_ecs_consistent(store):
    """The single invariant that distinguishes a locked store from a corrupt one."""
    ecs = store._handle.ecs
    n = len(ecs._ids)
    for col in (ecs._payloads, ecs._embeddings, ecs._utility, ecs._attended,
                ecs._protected_floor, ecs._last_evaluated, ecs._state, ecs._usd_link):
        assert len(col) == n, "ECS column length desync"
    assert len(ecs._id_to_row) == n, "_id_to_row desync"
    assert all(0 <= r < n for r in ecs._id_to_row.values()), "_id_to_row out of range"
    assert all(ecs._ids[r] == eid for eid, r in ecs._id_to_row.items()), "_id_to_row mismapped"


# --------------------------------------------------------------------------- #
# FC4 — concurrency must not corrupt the single-writer ECS
# --------------------------------------------------------------------------- #

def test_concurrent_add_and_prune_no_corruption():
    s = _store(half_life_seconds=60.0)
    for i in range(200):  # seed unprotected, then backdate so prune is eligible
        s.add(Memory(content=f"seed {i}", memory_type=MemoryType.NOTE))
    _backdate(s)

    errors = []
    barrier = threading.Barrier(10)

    def adder(t):
        barrier.wait()
        try:
            for i in range(200):
                s.add(Memory(content=f"t{t}-i{i}", memory_type=MemoryType.NOTE))
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    def pruner():
        barrier.wait()
        try:
            for _ in range(50):
                s.run_sleep_pass()
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    threads = [threading.Thread(target=adder, args=(t,)) for t in range(8)]
    threads += [threading.Thread(target=pruner) for _ in range(2)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert errors == [], f"concurrent add/prune raised: {errors[:5]}"
    _assert_ecs_consistent(s)


def test_concurrent_iterate_during_prune():
    s = _store(half_life_seconds=60.0)
    for i in range(200):
        s.add(Memory(content=f"seed {i}", memory_type=MemoryType.NOTE))
    _backdate(s)

    errors = []
    stop = threading.Event()

    def reader():
        try:
            while not stop.is_set():
                for r in s.search(MemoryQuery()):
                    assert isinstance(r.memory, Memory)  # no torn payload
                s.all()
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    def pruner():
        try:
            for _ in range(30):
                s.run_sleep_pass()
        finally:
            stop.set()

    readers = [threading.Thread(target=reader) for _ in range(8)]
    p = threading.Thread(target=pruner)
    for th in readers:
        th.start()
    p.start()
    p.join()
    for th in readers:
        th.join()

    assert errors == [], f"iterate-during-prune raised: {errors[:5]}"
    _assert_ecs_consistent(s)


def test_concurrent_add_is_lossless():
    s = _store()
    barrier = threading.Barrier(8)

    def adder(t):
        barrier.wait()
        for i in range(300):
            s.add(Memory(content=f"t{t}-i{i}", memory_type=MemoryType.NOTE))

    threads = [threading.Thread(target=adder, args=(t,)) for t in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert s.count() == 8 * 300
    _assert_ecs_consistent(s)


def test_count_under_churn_never_raises():
    s = _store(half_life_seconds=60.0)
    for i in range(100):
        s.add(Memory(content=f"seed {i}", memory_type=MemoryType.NOTE))
    _backdate(s)
    seen, errors, stop = [], [], threading.Event()

    def counter():
        try:
            while not stop.is_set():
                seen.append(s.count())
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    def churn():
        try:
            for i in range(100):
                s.add(Memory(content=f"c{i}", memory_type=MemoryType.NOTE))
            for _ in range(20):
                s.run_sleep_pass()
        finally:
            stop.set()

    c = threading.Thread(target=counter)
    ch = threading.Thread(target=churn)
    c.start(); ch.start(); ch.join(); c.join()
    assert errors == []
    assert all(isinstance(x, int) and x >= 0 for x in seen)


def test_adapter_imports_no_hou():
    # Pins the deadlock-freedom argument: the adapter holds its lock only over
    # pure-Python engine state and never across an hdefereval main-thread hop.
    # AST-based so it checks real imports, not mentions in comments/docstrings.
    import ast
    from synapse.memory import moneta_store
    tree = ast.parse(Path(moneta_store.__file__).read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad += [n.name for n in node.names if n.name.split(".")[0] in ("hou", "hdefereval")]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in ("hou", "hdefereval"):
                bad.append(node.module)
    assert not bad, f"adapter must not import hou/hdefereval (deadlock-freedom): {bad}"
    # And no hou binding leaked into the module namespace at import time.
    assert not hasattr(moneta_store, "hou")
    assert not hasattr(moneta_store, "hdefereval")


# --------------------------------------------------------------------------- #
# prune auditability — data loss is never silent
# --------------------------------------------------------------------------- #

def test_prune_audit_returns_pruned_ids():
    s = _store(half_life_seconds=60.0)
    doomed = Memory(content="ephemeral scratch note", memory_type=MemoryType.NOTE)
    kept = Memory(content="Decision: lock the wiring", memory_type=MemoryType.DECISION)
    s.add(doomed)
    s.add(kept)
    _backdate(s)
    audit = s.run_sleep_pass()

    assert doomed.id in audit.pruned_ids
    assert kept.id not in audit.pruned_ids
    assert audit.pruned == 1
    assert audit.count_before == 2
    assert audit.count_after == 1
    assert audit.pruned_types[doomed.id] == MemoryType.NOTE.value
    assert any("ephemeral scratch note" in p for p in audit.pruned_payloads.values())
    assert s.get(kept.id) is not None
    assert s.get(doomed.id) is None


def test_prune_audit_logs_at_warning(caplog):
    s = _store(half_life_seconds=60.0)
    doomed = Memory(content="another throwaway", memory_type=MemoryType.NOTE)
    s.add(doomed)
    _backdate(s)
    with caplog.at_level(logging.WARNING, logger="synapse.memory.moneta_store"):
        audit = s.run_sleep_pass()
    assert audit.pruned == 1
    blob = " ".join(r.message for r in caplog.records)
    assert "lossless-audit" in blob
    assert doomed.id in blob


def test_no_prune_is_quiet_and_consistent():
    s = _store()  # default long half-life: nothing decays enough to prune
    s.add(Memory(content="Decision: keep me", memory_type=MemoryType.DECISION))
    audit = s.run_sleep_pass()
    assert audit.pruned == 0
    assert audit.pruned_ids == []
    assert audit.count_before == audit.count_after == s.count()
