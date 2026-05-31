"""MonetaBackedStore — SYNAPSE MemoryStore backed by the Moneta engine (Mile 4).

Replaces the JSONL ``MemoryStore`` so the two-store divergence, the dead gauge,
and the empty stubs become *structurally* impossible: there is one store, and
``count()`` reads the engine's live entity count directly.

Mapping:
  * Each SYNAPSE ``Memory`` is serialized whole (``Memory.to_json()``) into a
    Moneta deposit's ``payload`` — it round-trips byte-for-byte.
  * ``content`` is embedded (pinned ``Embedder``) for vector recall.
  * Importance signals (decision / SHOW tier / gate source) map to a
    ``protected_floor`` so pinned memories resist Moneta's time-decay.
  * Reads enumerate the engine (``ecs.iter_rows``), deserialize payloads back
    to ``Memory``, and apply SYNAPSE's filtering/scoring here. Keyword recall is
    preserved exactly (see :func:`score_memories`); vector recall is a
    deliberate later upgrade, measured against keyword recall in shadow first.

This class is pure logic over an injected, caller-owned Moneta handle (Moneta
enforces single-owner URI locking). The factory :meth:`from_storage_dir` builds
a durable handle; tests inject an ephemeral one.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from .models import Memory, MemoryQuery, MemorySearchResult, MemoryTier, MemoryType

logger = logging.getLogger(__name__)

# Importance -> protected_floor. Pinned memories resist Moneta's decay.
_DEFAULT_PROTECTED_FLOOR = 0.9


def score_memories(
    memories: Iterable[Memory], query: MemoryQuery
) -> List[MemorySearchResult]:
    """Faithful re-implementation of ``MemoryStore.search`` scoring (parity target).

    The narrowing predicates mirror the by_type / by_tag / by_keyword index
    narrowing (raw, case-sensitive tag match — matching ``search``, not
    ``get_by_tag``); the scoring mirrors the tag/keyword/text weights and the
    ``(-score, id)`` deterministic sort. Kept standalone so the JSONL store is
    untouched; Mile 5's shadow harness measures any divergence empirically.
    """
    pool = list(memories)
    if query.memory_types:
        types = set(query.memory_types)
        pool = [m for m in pool if m.memory_type in types]
    if query.tags:
        qtags = set(query.tags)
        pool = [m for m in pool if qtags & set(m.tags)]
    if query.keywords:
        qkw = set(query.keywords)
        pool = [m for m in pool if qkw & set(m.keywords)]

    results: List[MemorySearchResult] = []
    for memory in pool:
        if memory.is_consolidated and not query.include_consolidated:
            continue
        if query.tier and memory.tier != query.tier:
            continue
        if query.source and memory.source != query.source:
            continue
        if query.since and memory.created_at < query.since:
            continue
        if query.until and memory.created_at > query.until:
            continue

        score = 0.0
        match_reasons: List[str] = []

        if query.tags:
            matching_tags = set(query.tags) & set(memory.tags)
            if matching_tags:
                score += len(matching_tags) * 0.2
                match_reasons.append(f"tags: {', '.join(matching_tags)}")
        if query.keywords:
            matching_keywords = set(query.keywords) & set(memory.keywords)
            if matching_keywords:
                score += len(matching_keywords) * 0.2
                match_reasons.append(f"keywords: {', '.join(matching_keywords)}")
        if query.text:
            text_lower = query.text.lower()
            content_lower = memory.content.lower()
            summary_lower = memory.summary.lower()
            if text_lower in content_lower:
                score += 0.5
                match_reasons.append("content match")
            if text_lower in summary_lower:
                score += 0.3
                match_reasons.append("summary match")
            words = text_lower.split()
            word_matches = sum(
                1 for w in words if w in content_lower or w in summary_lower
            )
            if word_matches > 0:
                score += word_matches * 0.1
                match_reasons.append(f"{word_matches} word matches")

        if not query.text and not query.tags and not query.keywords:
            score = 0.5

        if score > 0:
            results.append(
                MemorySearchResult(
                    memory=memory,
                    score=min(1.0, score),
                    match_reasons=match_reasons,
                )
            )

    results.sort(key=lambda r: (-r.score, r.memory.id))
    if query.limit > 0:
        results = results[: query.limit]
    return results


class MonetaUpdateNotSupported(NotImplementedError):
    """Moneta is append/consolidate; in-place update/delete/clear is not clean."""


class MonetaBackedStore:
    """``MemoryStore``-compatible facade over a single Moneta handle."""

    def __init__(self, handle, embedder, *, protected_floor: float = _DEFAULT_PROTECTED_FLOOR):
        self._handle = handle
        self._embedder = embedder
        self._protected_floor = protected_floor
        # Stamp the embedder id onto the store so a future embedder swap can
        # detect entries that need re-embedding (handoff capsule PARKED note).
        self.embedder_id = getattr(embedder, "id", "unknown")

    @classmethod
    def from_storage_dir(
        cls, storage_dir, embedder=None, *, protected_floor: float = _DEFAULT_PROTECTED_FLOOR
    ) -> "MonetaBackedStore":
        """Build a durable, project-scoped Moneta-backed store.

        Snapshot + WAL live under ``<storage_dir>/.moneta/``; the ``storage_uri``
        is stable per project dir so the URI lock and snapshot reload key are
        consistent across restarts. The background snapshot daemon is NOT
        started here — under the async server that races the ECS single-writer
        (FC4). Persistence is via :meth:`save` (synchronous snapshot); the
        production auto-snapshot cadence is wired in Mile 6.
        """
        from .embedding import HashEmbedder
        from . import moneta_runtime as mr

        if not mr.moneta_available():
            raise RuntimeError(
                f"Moneta backend requested but not importable: {mr.import_error()}"
            )
        embedder = embedder or HashEmbedder()
        base = Path(storage_dir) / ".moneta"
        base.mkdir(parents=True, exist_ok=True)
        cfg = mr.MonetaConfig(
            storage_uri=f"moneta-file://{Path(storage_dir).resolve().as_posix()}",
            embedding_dim=embedder.dim,
            snapshot_path=base / "snapshot.json",
            wal_path=base / "wal.log",
        )
        handle = mr.Moneta(cfg)
        return cls(handle, embedder, protected_floor=protected_floor)

    # -- write --------------------------------------------------------------

    def _is_protected(self, memory: Memory) -> bool:
        return (
            memory.memory_type == MemoryType.DECISION
            or memory.tier == MemoryTier.SHOW
            or memory.source == "gate"
        )

    def add(self, memory: Memory) -> str:
        text = memory.content or memory.summary or ""
        embedding = self._embedder.embed(text)
        payload = memory.to_json()
        floor = self._protected_floor if self._is_protected(memory) else 0.0
        try:
            self._handle.deposit(payload, embedding, protected_floor=floor)
        except Exception as exc:  # ProtectedQuotaExceededError, etc.
            if floor > 0.0:
                # Never drop a memory because the protected quota is full.
                logger.warning(
                    "Protected deposit failed (%s); storing unprotected: %s",
                    type(exc).__name__, exc,
                )
                self._handle.deposit(payload, embedding, protected_floor=0.0)
            else:
                raise
        return memory.id

    # -- enumerate (the one coupling to Moneta internals, centralized) ------

    def _iter_memories(self) -> Iterator[Memory]:
        for row in self._handle.ecs.iter_rows():
            yield Memory.from_json(row.payload)

    # -- read ---------------------------------------------------------------

    def count(self) -> int:
        return self._handle.ecs.n

    def all(self) -> List[Memory]:
        return list(self._iter_memories())

    def get(self, memory_id: str) -> Optional[Memory]:
        for m in self._iter_memories():
            if m.id == memory_id:
                return m
        return None

    def get_recent(self, limit: int = 10) -> List[Memory]:
        return sorted(
            self._iter_memories(), key=lambda m: m.created_at, reverse=True
        )[:limit]

    def get_by_type(self, memory_type: MemoryType) -> List[Memory]:
        return [m for m in self._iter_memories() if m.memory_type == memory_type]

    def get_by_tag(self, tag: str) -> List[Memory]:
        return [m for m in self._iter_memories() if tag in m.tags]

    def get_linked(self, memory_id: str) -> List[Memory]:
        all_mems = list(self._iter_memories())
        src = next((m for m in all_mems if m.id == memory_id), None)
        if src is None:
            return []
        targets = {link.target_id for link in src.links}
        return [m for m in all_mems if m.id in targets]

    def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        return score_memories(self._iter_memories(), query)

    # -- lifecycle ----------------------------------------------------------

    def save(self) -> None:
        """Durably snapshot the engine. No-op when durability is disabled (ephemeral)."""
        dur = getattr(self._handle, "durability", None)
        if dur is not None:
            try:
                dur.snapshot_ecs(self._handle.ecs)
            except Exception as exc:
                logger.warning("Moneta snapshot on save() failed: %s", exc)

    def run_sleep_pass(self):
        """Trigger Moneta consolidation/decay explicitly (snapshots when durable)."""
        return self._handle.run_sleep_pass()

    def close(self) -> None:
        self.save()
        close = getattr(self._handle, "close", None)
        if callable(close):
            close()

    # -- unsupported (append/consolidate engine) ----------------------------

    def update(self, memory: Memory):
        raise MonetaUpdateNotSupported(
            "MonetaBackedStore is append/consolidate; in-place update is not "
            "supported. Re-add as a new memory or trigger consolidation."
        )

    def delete(self, memory_id: str) -> bool:
        raise MonetaUpdateNotSupported(
            "MonetaBackedStore does not support targeted delete; pruning is "
            "handled by run_sleep_pass() decay/consolidation."
        )

    def clear(self):
        raise MonetaUpdateNotSupported(
            "MonetaBackedStore.clear() is unsupported on a live handle; "
            "construct a fresh handle for a clean store."
        )
