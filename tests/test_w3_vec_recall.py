"""W3-VEC — derived vector recall over the store, ranked with real scores.

Pins the S5 Phase 3 contract:
  * recall returns RANKED nearest neighbours with confidence scores, not a dump;
  * scores are REAL model outputs (cosine of the embedder's own vectors), never
    constant or fabricated (crucible criterion #3);
  * the index is DERIVED data — delete it, rebuild from source memories, and
    recall reproduces bit-for-bit (crucible criterion #2: a lost index costs
    nothing but a rebuild);
  * index construction reads embedding_dim from the ACTIVE PROVIDER — no pin
    (the W3-DIM regression guard, target #3).

The core contract is proven WITHOUT Moneta (the index takes a plain memory list
+ an embedder), so those tests always run. One store-integration test exercises
the real ``MonetaBackedStore`` public surface and skips cleanly when Moneta is
not importable.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import Memory, MemoryType, MemorySearchResult  # noqa: E402
from synapse.memory.vector_recall import (  # noqa: E402
    DerivedVectorIndex,
    recall_from_store,
    _cosine,
)
from synapse.memory import moneta_runtime as mr  # noqa: E402

DIM = 256

# Index positions in _corpus(): the two rim-light memories (0, 3) are the
# lexical matches for the probe query; the pdg/usd memories (1, 2) are not.
_RIM = (0, 3)
_OTHER = (1, 2)
_EXACT = "rim light color decision: push it warmer"  # verbatim content of mem 3
_PROBE = "rim light color"


def _corpus():
    return [
        Memory(content="rim light warm color grading on the hero shot",
               memory_type=MemoryType.NOTE, created_at="2026-01-01T00:00:00Z"),
        Memory(content="pdg farm cook error on the karma render node",
               memory_type=MemoryType.ERROR, created_at="2026-01-02T00:00:00Z"),
        Memory(content="usd stage composition arcs for the layout layer",
               memory_type=MemoryType.NOTE, created_at="2026-01-03T00:00:00Z"),
        Memory(content=_EXACT,
               memory_type=MemoryType.DECISION, created_at="2026-01-04T00:00:00Z"),
    ]


# ---------------------------------------------------------------------------
# Core contract — no Moneta required
# ---------------------------------------------------------------------------

def test_recall_ranks_by_similarity_with_scores():
    """Ranked nearest neighbours with scores — not a raw dump."""
    emb = HashEmbedder(dim=DIM)
    idx = DerivedVectorIndex.build_from_memories(_corpus(), emb)
    results = idx.query(emb.embed(_PROBE), limit=3)

    assert results, "recall returned nothing for a seeded query"
    assert len(results) == 3, "limit was not honoured (would be a raw dump)"
    assert all(isinstance(r, MemorySearchResult) for r in results)
    assert all(isinstance(r.score, float) for r in results)
    assert all(r.match_reasons for r in results)

    # RANKED: scores are non-increasing.
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)

    # The lexical match is on top and carries the highest score.
    assert "rim light" in results[0].memory.content.lower()


def test_rim_memories_outrank_unrelated_ones():
    """Similarity ordering is real: both rim-light memories beat both others."""
    emb = HashEmbedder(dim=DIM)
    corpus = _corpus()
    idx = DerivedVectorIndex.build_from_memories(corpus, emb)
    results = idx.query(emb.embed(_PROBE), limit=4)  # full ranking

    by_id = {r.memory.id: r.score for r in results}
    rim_scores = [by_id[corpus[i].id] for i in _RIM]
    other_scores = [by_id[corpus[i].id] for i in _OTHER]
    assert min(rim_scores) > max(other_scores)


def test_scores_are_real_cosine_not_constant():
    """Crucible #3: scores are the embedder's own cosine, not a constant."""
    emb = HashEmbedder(dim=DIM)
    corpus = _corpus()
    idx = DerivedVectorIndex.build_from_memories(corpus, emb)
    qv = emb.embed(_PROBE)
    results = idx.query(qv, limit=4)

    # Not all equal — a fabricated/constant score would collapse to one value.
    distinct = {round(r.score, 6) for r in results}
    assert len(distinct) > 1, f"scores are suspiciously constant: {distinct}"

    # Independently recompute the cosine from the embedder's own vectors and
    # assert the returned score IS that value — proof it is a real model output.
    for r in results:
        text = r.memory.content or r.memory.summary or ""
        expected = _cosine(emb.embed(text), qv)
        assert r.score == pytest.approx(expected, abs=1e-12)

    # An exact-content query scores 1.0 against its own memory (identical
    # vectors) — the score tracks true similarity, it is not invented.
    exact = idx.query(emb.embed(_EXACT), limit=1)
    assert exact[0].memory.content == _EXACT
    assert exact[0].score == pytest.approx(1.0, abs=1e-9)


def test_index_is_derived_delete_rebuild_reproduces():
    """Crucible #2 / target #1: a lost index costs only a rebuild from source."""
    emb = HashEmbedder(dim=DIM)
    corpus = _corpus()
    qv = emb.embed(_PROBE)

    idx = DerivedVectorIndex.build_from_memories(corpus, emb)
    r1 = [(r.memory.id, round(r.score, 12)) for r in idx.query(qv, limit=5)]

    # Delete the index entirely.
    del idx

    # Rebuild from the SAME source memories alone.
    idx2 = DerivedVectorIndex.build_from_memories(corpus, emb)
    r2 = [(r.memory.id, round(r.score, 12)) for r in idx2.query(qv, limit=5)]

    assert r1 == r2, "rebuilt-from-source index did not reproduce recall"


def test_dim_is_read_from_provider_no_pin():
    """Target #3: dim comes from the active provider, with no hardcoded pin."""
    for dim in (256, 384):
        emb = HashEmbedder(dim=dim)
        idx = DerivedVectorIndex.build_from_memories(_corpus(), emb)
        assert idx.dim == dim == emb.dim
        # Recall works inside the provider-sized space.
        assert idx.query(emb.embed(_PROBE), limit=1)


def test_dim_mismatch_entries_are_skipped_never_cross_space():
    """A query vector of the wrong dim scores nothing — no cross-space compare."""
    emb256 = HashEmbedder(dim=256)
    idx = DerivedVectorIndex.build_from_memories(_corpus(), emb256)
    wrong_space = HashEmbedder(dim=384).embed(_PROBE)
    assert idx.query(wrong_space, limit=5) == []


def test_empty_index_returns_empty():
    emb = HashEmbedder(dim=DIM)
    idx = DerivedVectorIndex.build_from_memories([], emb)
    assert len(idx) == 0
    assert idx.query(emb.embed("anything"), limit=5) == []


# ---------------------------------------------------------------------------
# Store integration — real MonetaBackedStore public surface (Moneta-gated)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable. Last error: {mr.import_error()}",
)
def test_recall_over_real_store_public_surface():
    """Index builds over the store's PUBLIC surface; derived-rebuild reproduces."""
    from synapse.memory.moneta_store import MonetaBackedStore

    handle = mr.make_ephemeral(embedding_dim=DIM)
    store = MonetaBackedStore(handle, HashEmbedder(dim=DIM))
    for m in _corpus():
        store.add(m)

    # Recall with no prior index — built from source on the spot.
    r1 = recall_from_store(store, _PROBE, limit=4)
    assert r1, "store-backed recall returned nothing"
    assert [round(x.score, 4) for x in r1] == sorted(
        (round(x.score, 4) for x in r1), reverse=True)
    assert "rim light" in r1[0].memory.content.lower()

    # Build an explicit derived index, delete it, rebuild from the store's
    # source memories — recall reproduces the same ids and scores.
    idx = DerivedVectorIndex.build_from_store(store)
    a = [(x.memory.id, round(x.score, 12)) for x in
         idx.query(store._embedder.embed(_PROBE), limit=4)]
    del idx
    idx2 = DerivedVectorIndex.build_from_store(store)
    b = [(x.memory.id, round(x.score, 12)) for x in
         idx2.query(store._embedder.embed(_PROBE), limit=4)]
    assert a == b
    # And the store-backed ranking matches the no-index recall.
    assert [x[0] for x in b] == [x.memory.id for x in r1]
