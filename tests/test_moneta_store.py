"""Mile 4 — MonetaBackedStore contract + parity (L1).

Runs wherever Moneta is importable; skips cleanly otherwise. Pins:
  * the five-op contract (add/count/search/get_recent/get_by_type) round-trips,
  * search ranking is identical to the JSONL MemoryStore on the same inputs
    (parity preview of AP5 — fix-forward if it diverges, never weaken),
  * importance -> protected_floor mapping,
  * append/consolidate ops (update/delete/clear) raise loudly, not silently.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import (  # noqa: E402
    Memory, MemoryQuery, MemoryType, MemoryTier,
)
from synapse.memory.store import MemoryStore  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)

DIM = 256


def _store():
    from synapse.memory.moneta_store import MonetaBackedStore
    handle = mr.make_ephemeral(embedding_dim=DIM)
    return MonetaBackedStore(handle, HashEmbedder(dim=DIM))


def _corpus():
    """A small fixed corpus exercising types, tags, keywords, recency."""
    return [
        Memory(content="render the karma beauty pass tonight",
               memory_type=MemoryType.ACTION, tags=["render", "karma"],
               keywords=["karma", "beauty"], created_at="2026-01-01T00:00:00Z"),
        Memory(content="Decision: use assemble_chain to wire the Solaris graph",
               memory_type=MemoryType.DECISION, tags=["ai_decision"],
               keywords=["assemble_chain", "solaris"], created_at="2026-01-02T00:00:00Z"),
        Memory(content="material binding failed on the hero asset",
               memory_type=MemoryType.ERROR, tags=["error", "material"],
               keywords=["material", "binding"], created_at="2026-01-03T00:00:00Z"),
        Memory(content="note about karma denoiser settings for the render",
               memory_type=MemoryType.NOTE, tags=["render"],
               keywords=["karma", "denoiser"], created_at="2026-01-04T00:00:00Z"),
    ]


def test_add_and_count():
    s = _store()
    for m in _corpus():
        assert s.add(m) == m.id
    assert s.count() == 4


def test_payload_round_trips_full_memory():
    s = _store()
    original = _corpus()[1]  # the decision, with tags + keywords
    s.add(original)
    got = s.get(original.id)
    assert got is not None
    assert got.content == original.content
    assert got.memory_type == MemoryType.DECISION
    assert got.tags == original.tags
    assert got.keywords == original.keywords


def test_get_recent_orders_by_created_at_desc():
    s = _store()
    for m in _corpus():
        s.add(m)
    recent = s.get_recent(limit=2)
    assert [m.created_at for m in recent] == ["2026-01-04T00:00:00Z", "2026-01-03T00:00:00Z"]


def test_get_by_type_is_the_decisions_path():
    s = _store()
    for m in _corpus():
        s.add(m)
    decisions = s.get_by_type(MemoryType.DECISION)
    assert len(decisions) == 1
    assert decisions[0].memory_type == MemoryType.DECISION


@pytest.mark.parametrize("query", [
    MemoryQuery(text="karma"),
    MemoryQuery(text="render", limit=2),
    MemoryQuery(tags=["render"]),
    MemoryQuery(keywords=["karma"]),
    MemoryQuery(memory_types=[MemoryType.DECISION]),
    MemoryQuery(text="material", tags=["error"]),
    MemoryQuery(text="nothing matches this string xyzzy"),
])
def test_search_ranking_parity_with_jsonl_store(tmp_path, query):
    corpus = _corpus()
    moneta = _store()
    jsonl = MemoryStore(tmp_path / ".synapse")
    for m in corpus:
        moneta.add(m)
        jsonl.add(m)

    def rank(results):
        return [(r.memory.id, round(r.score, 9)) for r in results]

    assert rank(moneta.search(query)) == rank(jsonl.search(query))


def test_protected_floor_mapping():
    from synapse.memory.moneta_store import MonetaBackedStore
    handle = mr.make_ephemeral(embedding_dim=DIM)
    s = MonetaBackedStore(handle, HashEmbedder(dim=DIM))
    note = Memory(content="routine note", memory_type=MemoryType.NOTE)
    decision = Memory(content="big call", memory_type=MemoryType.DECISION)
    s.add(note)
    s.add(decision)
    floors = {Memory.from_json(r.payload).memory_type: r.protected_floor
              for r in handle.ecs.iter_rows()}
    assert floors[MemoryType.NOTE] == 0.0
    assert floors[MemoryType.DECISION] > 0.0


def test_show_tier_and_gate_source_are_protected():
    from synapse.memory.moneta_store import MonetaBackedStore
    handle = mr.make_ephemeral(embedding_dim=DIM)
    s = MonetaBackedStore(handle, HashEmbedder(dim=DIM))
    s.add(Memory(content="show-wide convention", memory_type=MemoryType.NOTE,
                 tier=MemoryTier.SHOW))
    s.add(Memory(content="human-approved", memory_type=MemoryType.NOTE, source="gate"))
    assert all(r.protected_floor > 0.0 for r in handle.ecs.iter_rows())


def test_mutation_ops_raise_loudly():
    from synapse.memory.moneta_store import MonetaUpdateNotSupported
    s = _store()
    m = _corpus()[0]
    s.add(m)
    with pytest.raises(MonetaUpdateNotSupported):
        s.update(m)
    with pytest.raises(MonetaUpdateNotSupported):
        s.delete(m.id)
    with pytest.raises(MonetaUpdateNotSupported):
        s.clear()


def test_flag_wires_synapse_memory_to_moneta(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    from synapse.memory.store import SynapseMemory
    from synapse.memory.moneta_store import MonetaBackedStore

    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    try:
        assert isinstance(sm.store, MonetaBackedStore)
        # Facade methods must work unchanged through the new backend.
        sm.add(content="a decision", memory_type=MemoryType.DECISION, tags=["x"])
        sm.add(content="a note", memory_type=MemoryType.NOTE)
        assert sm.store.count() == 2
        assert len(sm.get_decisions()) == 1
        assert len(sm.get_recent(10)) == 2
    finally:
        sm.store.close()


def test_flag_falls_back_to_jsonl_when_backend_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNAPSE_MEMORY_BACKEND", raising=False)
    from synapse.memory.store import SynapseMemory
    sm = SynapseMemory(project_path=str(tmp_path / "proj2"))
    assert isinstance(sm.store, MemoryStore)
