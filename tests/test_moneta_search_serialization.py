"""Text recall must obey the adapter's existing engine ownership boundary.

These tests exercise the real adapter with inert handles. They do not reproduce
or establish the cause of the recorded native Houdini exit.
"""
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.memory.embedding import HashEmbedder
from synapse.memory.models import Memory, MemoryQuery
from synapse.memory.moneta_store import MonetaBackedStore


def _fixture():
    memory = Memory(content="Warm coral hero sphere", summary="Coral look")
    row = SimpleNamespace(payload=memory.to_json(), entity_id=UUID(int=1))
    calls = []
    handle = SimpleNamespace(
        query=lambda embedding, limit: calls.append("query") or [row],
        signal_attention=lambda weights: calls.append("attention"),
        ecs=SimpleNamespace(iter_rows=lambda: calls.append("iterate") or [row]),
        durability=None,
        close=lambda: calls.append("close"),
    )
    return MonetaBackedStore(handle, HashEmbedder(dim=8)), memory, calls


def _start(fn):
    started, finished = threading.Event(), threading.Event()
    errors, results = [], []

    def run():
        started.set()
        try:
            results.append(fn())
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert started.wait(2), "fixture worker did not start"
    return thread, finished, errors, results


def _join(worker):
    thread, finished, errors, results = worker
    thread.join(2)
    assert not thread.is_alive(), "adapter operation did not finish after lock release"
    assert finished.is_set()
    assert not errors, repr(errors)
    return results


def test_text_search_waits_for_existing_engine_owner():
    store, memory, calls = _fixture()
    with store._lock:
        worker = _start(lambda: store.search(MemoryQuery(text="coral")))
        worker[1].wait(0.2)
        during = list(calls)
    results = _join(worker)[0]
    assert during == [], f"engine touched while another owner held the lock: {during}"
    assert calls == ["query", "attention"]
    assert [hit.memory.id for hit in results] == [memory.id]


def test_close_waits_until_query_and_attention_finish():
    store, memory, calls = _fixture()
    entered, release_query = threading.Event(), threading.Event()
    original_query = store._handle.query

    def query(embedding, limit):
        result = original_query(embedding, limit)
        entered.set()
        assert release_query.wait(2), "test did not release the query"
        return result

    store._handle.query = query
    searching = _start(lambda: store.search(MemoryQuery(text="coral")))
    closing = None
    try:
        assert entered.wait(2), "search did not reach its handle"
        closing = _start(store.close)
        close_finished_during_query = closing[1].wait(0.2)
    finally:
        release_query.set()
    results = _join(searching)[0]
    if closing is not None:
        _join(closing)
    assert not close_finished_during_query, "close overlapped an active engine query"
    assert calls == ["query", "attention", "close"]
    assert [hit.memory.id for hit in results] == [memory.id]


@pytest.mark.parametrize("text", ["", "coral"])
def test_search_rejects_closed_owner_before_engine_access(text):
    store, _, calls = _fixture()
    store.close()
    calls.clear()
    with pytest.raises(RuntimeError, match="Memory store is closed"):
        store.search(MemoryQuery(text=text))
    assert calls == []


def test_closed_search_rejects_before_invoking_the_embedder():
    store, _, calls = _fixture()

    def embed(text):
        calls.append("embed")
        raise AssertionError("a closed store must not invoke embedding")

    store._embedder = SimpleNamespace(embed=embed)
    store.close()
    calls.clear()
    with pytest.raises(RuntimeError, match="Memory store is closed"):
        store.search(MemoryQuery(text="coral"))
    assert calls == []


@pytest.mark.parametrize("require_durable", [False, True])
def test_closed_add_rejects_before_embedding_or_deposit(require_durable):
    store, memory, calls = _fixture()
    store._handle.deposit = lambda *args, **kwargs: calls.append("deposit")
    store._handle.durability = SimpleNamespace(
        snapshot_ecs=lambda ecs: calls.append("snapshot")
    )

    def embed(text):
        calls.append("embed")
        return [0.0] * 8

    store._embedder = SimpleNamespace(embed=embed)
    store.close()
    calls.clear()
    with pytest.raises(RuntimeError, match="Memory store is closed"):
        store.add(memory, require_durable=require_durable)
    assert calls == []


@pytest.mark.parametrize("require_durable", [False, True])
def test_close_during_add_embedding_prevents_deposit(require_durable):
    store, memory, calls = _fixture()
    store._handle.deposit = lambda *args, **kwargs: calls.append("deposit")
    store._handle.durability = SimpleNamespace(
        snapshot_ecs=lambda ecs: calls.append("snapshot")
    )

    def embed(text):
        calls.append("embed")
        store.close()
        return [0.0] * 8

    store._embedder = SimpleNamespace(embed=embed)
    with pytest.raises(RuntimeError, match="Memory store is closed"):
        store.add(memory, require_durable=require_durable)
    assert calls == ["embed", "snapshot", "close"]


def test_vector_failure_falls_back_without_reentrant_deadlock():
    store, memory, calls = _fixture()

    def query(embedding, limit):
        calls.append("query")
        raise RuntimeError("fixture vector lookup unavailable")

    store._handle.query = query
    results = _join(_start(lambda: store.search(MemoryQuery(text="coral"))))[0]
    assert [hit.memory.id for hit in results] == [memory.id]
    assert calls == ["query", "iterate"]


def test_attention_failure_preserves_search_result_and_releases_owner():
    store, memory, calls = _fixture()

    def signal(weights):
        calls.append("attention")
        raise RuntimeError("fixture attention update unavailable")

    store._handle.signal_attention = signal
    results = _join(_start(lambda: store.search(MemoryQuery(text="coral"))))[0]
    _join(_start(store.close))
    assert [hit.memory.id for hit in results] == [memory.id]
    assert calls == ["query", "attention", "close"]


def test_strict_add_rechecks_failed_state_after_concurrent_embedding():
    store, _, calls = _fixture()
    paused = Memory(id="strict_paused", content="paused")
    failing = Memory(id="strict_failing", content="failing")
    entered, release = threading.Event(), threading.Event()
    attempts, snapshots, embeds, errors = [], [], [], []
    failure = RuntimeError("fixture partial backend deposit")

    def embed(text):
        embeds.append(text)
        if text == "paused":
            entered.set()
            assert release.wait(2), "challenge did not release paused embedding"
        return [0.0] * 8

    def deposit(payload, embedding, *, protected_floor):
        memory = Memory.from_json(payload)
        attempts.append(memory.id)
        if memory.id == failing.id:
            raise failure

    store._embedder = SimpleNamespace(embed=embed)
    store._handle.deposit = deposit
    store._handle.durability = SimpleNamespace(
        snapshot_ecs=lambda ecs: snapshots.append("snapshot")
    )

    def add_paused():
        try:
            store.add(paused, require_durable=True)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=add_paused, daemon=True)
    worker.start()
    try:
        assert entered.wait(2), "strict add did not reach embedding"
        with pytest.raises(RuntimeError) as caught:
            store.add(failing, require_durable=True)
        assert caught.value is failure
        assert attempts == [failing.id]
        assert store._strict_deposit_failed is True
        release.set()
        worker.join(2)
        assert not worker.is_alive(), "paused strict add did not finish"
        assert len(errors) == 1 and isinstance(errors[0], RuntimeError)
        assert str(errors[0]) == (
            "A partial backend deposit requires restart before checked memory can continue"
        )
        assert attempts == [failing.id], "another deposit occurred after strict failure"
        assert snapshots == [], "a failed strict add must not checkpoint or acknowledge"
        with pytest.raises(RuntimeError, match="partial backend deposit requires restart"):
            store.add(Memory(id="strict_retry", content="retry"), require_durable=True)
        assert embeds == ["paused", "failing"]
        assert attempts == [failing.id]
        assert store._strict_deposit_failed is True
    finally:
        release.set()
        worker.join(2)
        assert not worker.is_alive()
        store.close()
