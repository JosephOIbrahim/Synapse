"""Derived vector recall over a SYNAPSE memory store (S5 Phase 3 — W3-VEC).

A rebuildable nearest-neighbour index built OVER the store's source memories.
It is DERIVED DATA and is never treated as the source of truth: it holds only
``(memory, vector)`` pairs re-derived from each memory's *source content* by the
active embedder. A lost index costs a rebuild and nothing else —
:meth:`DerivedVectorIndex.build_from_store` reconstructs it bit-for-bit from the
source memories, because the :class:`~synapse.memory.embedding.Embedder`
contract is a pure, deterministic function of text.

Scores are real model outputs. The confidence returned for each hit is the
**cosine similarity** between the query's embedding and the memory's embedding
(``[-1, 1]``; higher is more similar). Both SYNAPSE embedders L2-normalize, so
cosine is the dot product for the common case; the value is a genuine model
output, never a fabricated or constant number.

Dim discipline (W3-DIM regression guard). The embedding dimension is READ FROM
THE ACTIVE PROVIDER (``embedder.dim``) at build time — there is no pinned
dimension anywhere in this module. An embedder swap therefore changes the
vector space cleanly, and a query vector whose length does not match an entry's
is *skipped*, never silently compared across spaces.

Seam. This module reads the store's PUBLIC surface only (``store.all()`` and the
stamped ``_embedder``). It does not edit or depend on store internals, so it
composes cleanly with the store/kind/dim legs that own ``moneta_store.py``.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

from .models import Memory, MemorySearchResult

logger = logging.getLogger(__name__)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors.

    The embedders L2-normalize every non-empty vector, so this is a plain dot
    product for the common case; we divide by the norms anyway so an
    un-normalized or zero vector can never yield a misleading score or a NaN.
    A zero vector (the documented empty-string embedding) scores 0.0 against
    anything — no similarity, which is the honest answer.
    """
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


class DerivedVectorIndex:
    """A rebuildable nearest-neighbour index over source memories.

    DERIVED, never the source of truth. Each entry is ``(memory, vector)`` where
    ``vector`` is re-derived from the memory's source content by ``embedder``.
    ``dim`` is read from the provider at build time; there is no pinned
    dimension. Deleting the index and rebuilding it from the same source
    memories reproduces every vector exactly (the embedder is deterministic),
    so recall over a rebuilt index is bit-for-bit identical.
    """

    def __init__(self, dim: int, embedder_id: str = "unknown") -> None:
        self.dim = int(dim)
        self.embedder_id = embedder_id
        self._entries: List[Tuple[Memory, List[float]]] = []

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def _text_of(memory: Memory) -> str:
        # Mirror MonetaBackedStore.add() exactly (``content or summary or ""``)
        # so a rebuilt index reproduces the deposited vectors, not a variant.
        return memory.content or memory.summary or ""

    @classmethod
    def build_from_memories(cls, memories, embedder) -> "DerivedVectorIndex":
        """Build the index by embedding each memory's source content.

        A pure function of ``(memories, embedder)``: the deterministic embedder
        means this reproduces the same vectors on every rebuild. ``embedder.dim``
        is the sole dimension authority (W3-DIM guard) — no literal dim here.
        """
        idx = cls(dim=embedder.dim, embedder_id=getattr(embedder, "id", "unknown"))
        for memory in memories:
            vector = embedder.embed(idx._text_of(memory))
            idx._entries.append((memory, list(vector)))
        return idx

    @classmethod
    def build_from_store(cls, store) -> "DerivedVectorIndex":
        """Build the index over a store's SOURCE memories via its public surface.

        Reads ``store.all()`` (the source memories) and the store's stamped
        ``_embedder``. Nothing store-internal is touched, and nothing here is
        the source of truth — this is a derived view that can be discarded and
        rebuilt at will.
        """
        embedder = getattr(store, "_embedder", None)
        if embedder is None:
            raise ValueError("store has no embedder; vector recall is inactive")
        return cls.build_from_memories(store.all(), embedder)

    def query(self, query_vec: Sequence[float], limit: int = 5) -> List[MemorySearchResult]:
        """Rank entries by cosine similarity to ``query_vec`` (descending).

        Returns :class:`MemorySearchResult` hits carrying the REAL cosine score
        — not a raw dump. A dim-mismatched entry is skipped (never compared
        across embedding spaces). Ties break deterministically: fresher first,
        then id ascending — the same total order the keyword store uses, so
        recall is reproducible across restarts and index rebuilds.
        """
        scored: List[MemorySearchResult] = []
        qlen = len(query_vec)
        for memory, vector in self._entries:
            if len(vector) != qlen:
                # Cross-space comparison is meaningless; a swapped embedder or a
                # stale entry is dropped rather than scored against a wrong dim.
                continue
            score = _cosine(vector, query_vec)
            scored.append(MemorySearchResult(
                memory=memory,
                score=float(score),
                match_reasons=[f"vector cosine {score:.4f} (embedder {self.embedder_id})"],
            ))
        # Layered stable sorts, least-significant first — mirrors score_memories
        # so the two recall paths share one deterministic total order.
        scored.sort(key=lambda r: r.memory.id)
        scored.sort(key=lambda r: r.memory.created_at, reverse=True)
        scored.sort(key=lambda r: r.score, reverse=True)
        if limit and limit > 0:
            scored = scored[:limit]
        return scored


def recall_from_store(
    store,
    query_text: str,
    limit: int = 5,
    index: Optional[DerivedVectorIndex] = None,
) -> List[MemorySearchResult]:
    """Nearest-neighbour recall over a store's memories, ranked by real cosine.

    Not a raw dump: returns ranked :class:`MemorySearchResult` hits, each with a
    confidence (cosine) score. Supply ``index`` to reuse a prebuilt derived
    index; when omitted a fresh one is built from the store's source memories —
    that build IS the full cost of a lost index. The query is embedded with the
    store's OWN embedder so the query and memory vectors share one space.
    """
    embedder = getattr(store, "_embedder", None)
    if embedder is None:
        raise ValueError("store has no embedder; vector recall is inactive")
    if index is None:
        index = DerivedVectorIndex.build_from_store(store)
    query_vec = embedder.embed(query_text or "")
    return index.query(query_vec, limit)
