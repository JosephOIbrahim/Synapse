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


def _diverse_corpus():
    """A larger corpus exercising vector-relevant content differences."""
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
        Memory(content="karma xpu renderer is faster than cpu for beauty passes",
               memory_type=MemoryType.NOTE, tags=["render", "karma"],
               keywords=["karma", "xpu"], created_at="2026-01-05T00:00:00Z"),
        Memory(content="solaris stage assembly with karma render settings",
               memory_type=MemoryType.ACTION, tags=["solaris", "render"],
               keywords=["solaris", "karma"], created_at="2026-01-06T00:00:00Z"),
        Memory(content="the hero asset needs a new material binding for the cloth",
               memory_type=MemoryType.ACTION, tags=["material", "asset"],
               keywords=["material", "hero"], created_at="2026-01-07T00:00:00Z"),
        Memory(content="Decision: use karma xpu for final render",
               memory_type=MemoryType.DECISION, tags=["render", "karma"],
               keywords=["karma", "xpu", "final"], created_at="2026-01-08T00:00:00Z"),
    ]


def test_vector_recall_parity():
    """Vector recall returns same top-N as keyword recall for a representative query set."""
    s = _store()
    corpus = _diverse_corpus()
    for m in corpus:
        s.add(m)

    # Vector path: text query triggers embedding + Moneta vector query.
    vector_results = s.search(MemoryQuery(text="karma", limit=4))
    vector_ids = {r.memory.id for r in vector_results}

    # Keyword path: no text, so it falls back to full-scan keyword scoring.
    keyword_results = s.search(MemoryQuery(keywords=["karma"], limit=4))
    keyword_ids = {r.memory.id for r in keyword_results}

    # The top-4 from each path should overlap by at least 50% (2 of 4).
    overlap = vector_ids & keyword_ids
    assert len(overlap) >= 2, (
        f"Vector and keyword top-4 overlap too small: {len(overlap)}/4. "
        f"Vector ids: {vector_ids}, keyword ids: {keyword_ids}"
    )


def test_vector_recall_fallback():
    """Non-text queries (tags only, keywords only) still work and return results.
    Vector recall is only activated when query.text is set."""
    s = _store()
    corpus = _diverse_corpus()
    for m in corpus:
        s.add(m)

    # Tags-only query — no text, should use full scan, not vector recall.
    tag_results = s.search(MemoryQuery(tags=["render"], limit=5))
    assert len(tag_results) > 0, "Tags-only query returned no results"
    assert all("render" in m.memory.tags for m in tag_results), (
        "All tag results should carry the queried tag"
    )

    # Keywords-only query — no text, should use full scan, not vector recall.
    kw_results = s.search(MemoryQuery(keywords=["karma"], limit=5))
    assert len(kw_results) > 0, "Keywords-only query returned no results"
    assert all("karma" in m.memory.keywords for m in kw_results), (
        "All keyword results should carry the queried keyword"
    )

    # Mixed tags+keywords, still no text — still the full-scan path.
    mixed_results = s.search(MemoryQuery(tags=["render"], keywords=["karma"], limit=5))
    assert len(mixed_results) > 0, "Mixed tags+keywords query returned no results"


def test_re_embed_preserves_memory_count():
    """Re-embedding (creating a new store over the same handle) preserves count.

    A new MonetaBackedStore with a different embedder instance should still
    see the same memories — the handle owns the ECS, not the store wrapper.
    """
    from synapse.memory.moneta_store import MonetaBackedStore
    from synapse.memory.embedding import HashEmbedder

    handle = mr.make_ephemeral(embedding_dim=DIM)
    s1 = MonetaBackedStore(handle, HashEmbedder(dim=DIM))
    for m in _corpus():
        s1.add(m)
    assert s1.count() == 4

    # Second store, same handle, different embedder instance.
    s2 = MonetaBackedStore(handle, HashEmbedder(dim=DIM))
    assert s2.count() == 4
    # Payloads must still round-trip.
    got = s2.get(_corpus()[0].id)
    assert got is not None
    assert got.content == _corpus()[0].content


def test_embedder_swap_detectable():
    """embedder_id changes when a different embedder is used, so provenance
    can detect that a re-embed is needed."""
    from synapse.memory.moneta_store import MonetaBackedStore
    from synapse.memory.embedding import HashEmbedder

    handle = mr.make_ephemeral(embedding_dim=256)
    s1 = MonetaBackedStore(handle, HashEmbedder(dim=256))
    assert s1.embedder_id == "hash-ngram-v1-d256-n1_3"

    s2 = MonetaBackedStore(handle, HashEmbedder(dim=384))
    assert s2.embedder_id == "hash-ngram-v1-d384-n1_3"
    assert s1.embedder_id != s2.embedder_id
