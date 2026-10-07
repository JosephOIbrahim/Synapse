"""The demo deposit -> reopen -> recall round trip, on BOTH memory backends.

tests/test_demo_memory_recall.py and test_demo_memory_scope.py pin the demo on
jsonl only, but the seat runs SYNAPSE_MEMORY_BACKEND=moneta (packages/
synapse.json). This file runs the same artist path -- the real decide and recall
handlers, a release, a fresh store on the same directory -- on each backend.

Moneta skips with the import error when it is not importable. When it IS
importable the store must really be Moneta: a silent jsonl fallback would make
the moneta case a second jsonl run that reads green (store.py _make_store).
"""
import pytest

from synapse.memory import moneta_runtime as mr
from synapse.memory import store
from synapse.session import tracker

DEPOSITS = {
    "look": ("Hero product display look: warm coral sphere, copper torus, charcoal plinth.",
             "project"),
    "camera": ("Camera locked at 50mm, eye level, slow push in on the plinth.", "project"),
    "key": ("Key light stays warm from frame left; rim is a cool kicker.", "scene"),
}


def _backend_params():
    yield pytest.param("jsonl", id="jsonl")
    yield pytest.param("moneta", id="moneta", marks=pytest.mark.skipif(
        not mr.moneta_available(),
        reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
    ))


def _open(path):
    memory = store.SynapseMemory(str(path))
    bridge = tracker.SynapseBridge.__new__(tracker.SynapseBridge)
    bridge._synapse, bridge._markdown_sync, bridge._context_cache = memory, None, None
    return memory, bridge


def _release(memory):
    # save() is not a release: Moneta holds a per-URI lock until close(), and a
    # second open while it is held falls back to jsonl.
    closer = getattr(memory.store, "close", None)
    closer() if callable(closer) else memory.save()


@pytest.fixture(params=list(_backend_params()))
def backend(request, monkeypatch):
    monkeypatch.setattr(store, "HOU_AVAILABLE", False)
    monkeypatch.setattr(tracker, "HOU_AVAILABLE", False)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", request.param)
    return request.param


def _assert_serving(memory, backend):
    if backend == "moneta":
        from synapse.memory.moneta_store import MonetaBackedStore
        assert isinstance(memory.store, MonetaBackedStore), store.backend_fallback()
    else:
        assert isinstance(memory.store, store.MemoryStore)


@pytest.fixture
def reopened(backend, tmp_path):
    memory, bridge = _open(tmp_path)
    _assert_serving(memory, backend)
    ids = {}
    for key, (decision, scope) in DEPOSITS.items():
        result = bridge.handle_memory_decide({"decision": decision, "scope": scope})
        assert result.get("recorded", True) and result["scope"] == scope, result
        ids[key] = result["id"]
    _release(memory)
    memory, bridge = _open(tmp_path)
    _assert_serving(memory, backend)
    yield bridge, ids
    _release(memory)


@pytest.mark.parametrize("key, query, scope", [
    ("look", "Hero product display look", "project"),
    ("look", "What was the look decision for our product display?", "project"),
    ("look", "coral sphere copper torus", "all"),
    ("camera", "camera 50mm push", "project"),
    ("key", "key light rim", "scene"),
    ("key", "key light rim", "all"),
])
def test_deposit_survives_reopen_and_recalls_first(reopened, key, query, scope):
    bridge, ids = reopened
    result = bridge.handle_memory_recall({"query": query, "scope": scope})
    assert result["found"] is True, result
    assert result["matches"][0]["id"] == ids[key]
    assert not any(m.get("source") == "knowledge" for m in result["matches"])


def test_project_scope_never_returns_the_scene_decision(reopened):
    bridge, ids = reopened
    result = bridge.handle_memory_recall({"query": "key light rim", "scope": "project"})
    assert result["found"] is False and result["matches"] == []


@pytest.mark.parametrize("query", ["submarine periscope", "oral", "rim light blue"])
def test_unrelated_recall_is_not_found(reopened, query):
    bridge, _ = reopened
    result = bridge.handle_memory_recall({"query": query, "scope": "project"})
    assert result["found"] is False and result["matches"] == []
