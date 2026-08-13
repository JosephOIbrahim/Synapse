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
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .models import Memory, MemoryQuery, MemorySearchResult, MemoryTier, MemoryType

logger = logging.getLogger(__name__)

# Importance -> protected_floor. Pinned memories resist Moneta's decay.
_DEFAULT_PROTECTED_FLOOR = 0.9


@dataclass(frozen=True)
class PruneAudit:
    """What a sleep pass actually removed — the lossless prune record.

    ``run_sleep_pass`` is the one destructive memory op (it permanently prunes
    unprotected memories). Moneta's ``ConsolidationResult`` reports only counts;
    this captures the ids + payloads + types of what was removed, so data loss
    is never silent. Back-compatible: ``.pruned``/``.staged``/``.attention_updated``
    mirror the old return shape.
    """

    pruned_ids: List[str] = field(default_factory=list)          # SYNAPSE Memory.id
    pruned_entity_ids: List[str] = field(default_factory=list)   # Moneta UUID (str)
    pruned_payloads: Dict[str, str] = field(default_factory=dict)
    pruned_types: Dict[str, str] = field(default_factory=dict)
    count_before: int = 0
    count_after: int = 0
    attention_updated: int = 0
    staged: int = 0

    @property
    def pruned(self) -> int:
        return len(self.pruned_entity_ids)


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

    # Recency-aware ranking, IDENTICAL to MemoryStore/SqliteStore so recall parity holds
    # (test_moneta_store ranking parity): score desc, then fresher-first (created_at is an
    # ISO-8601 string, lexical desc == chronological desc), then id asc. Layered stable sorts.
    results.sort(key=lambda r: r.memory.id)
    results.sort(key=lambda r: r.memory.created_at, reverse=True)
    results.sort(key=lambda r: r.score, reverse=True)
    if query.limit > 0:
        results = results[: query.limit]
    return results


class MonetaUpdateNotSupported(NotImplementedError):
    """Moneta is append/consolidate; in-place update/delete/clear is not clean."""


class MonetaBackedStore:
    """``MemoryStore``-compatible facade over a single Moneta handle.

    Durability
    ----------
    ``deposit()`` writes to the in-memory ECS and returns immediately.
    There is no per-deposit fsync. Persistence is via ``save()``, which
    snapshots the ECS to ``snapshot.json`` under ``.moneta/``.

    The periodic save timer (``_save_interval``, 30 s) bounds the loss
    window: at most 30 seconds of deposits are at risk between snapshots.
    The ``atexit`` handler (registered in ``from_storage_dir``) covers
    **clean exit only** — ``sys.exit()``, normal shutdown, Ctrl+C. A
    ``kill -9``, native crash, or power loss loses at most 30 s of
    deposits (the timer's window). This bound is recorded, not silently
    assumed closed — the repo keeps a crash harness precisely because
    hard crashes happen.

    The WAL (``wal.log``) is **inert**: SYNAPSE never calls
    ``signal_attention``, which is Moneta's only WAL writer. The WAL path
    is configured so an upstream deposit-WAL can light it up without a
    config change, but it must not be read as "deposits are journalled
    today," because they are not.

    The per-record JSON file (``snapshot.json``) is the durable source of
    truth. A corrupt snapshot is quarantined (renamed with a ``.corrupt-``
    suffix) and the store starts fresh, rather than crashing startup or
    silently abandoning the file. The background snapshot daemon is
    deliberately NOT started — under the async server it races the ECS
    single-writer (FC4).
    """

    def __init__(self, handle, embedder, *, protected_floor: float = _DEFAULT_PROTECTED_FLOOR,
                 cortex=None, jsonl_net=None):
        self._handle = handle
        self._embedder = embedder
        self._protected_floor = protected_floor
        # W3-STORE secondary sinks (both optional; None preserves the pure
        # engine-only adapter that tests inject). ``_cortex`` is a
        # UsdCortexStore that materializes cortex_root.usda so the doctor sees a
        # typed substrate; ``_jsonl_net`` is a JSONL MemoryStore safety net so a
        # memory never lands ONLY in moneta (dual-write, the wave non-negotiable).
        # Neither is authoritative for reads -- moneta stays the substrate.
        self._cortex = cortex
        self._jsonl_net = jsonl_net
        self._sidecar_ensured = False
        # Stamp the embedder id onto the store so a future embedder swap can
        # detect entries that need re-embedding (handoff capsule PARKED note).
        self.embedder_id = getattr(embedder, "id", "unknown")
        # FC4: serialize ALL engine access. Moneta's ECS is single-writer —
        # concurrent deposit/iterate/prune corrupts its swap-and-pop index. This
        # RLock makes the adapter thread-safe by construction. It guards ONLY
        # in-process Python state and is never held across an hdefereval
        # main-thread hop (this adapter makes zero hou.* calls — see the
        # no-hou-import guard test), so it cannot deadlock the async server.
        # RLock (not Lock) because close() -> save() is a guarded-calls-guarded edge.
        self._lock = threading.RLock()
        self._last_save: float = 0.0
        self._save_interval: float = 30.0
        self._add_count: int = 0

    # Protected memories (decisions / show-tier / gate) are exactly the
    # keep-forever set, so the per-handle protected quota is set high: Moneta's
    # default 100 is a backstop that would silently demote the 101st pin to
    # prunable (CRUCIBLE finding). We never want that for SYNAPSE.
    _PROTECTED_QUOTA = 100_000

    @classmethod
    def from_storage_dir(
        cls,
        storage_dir,
        embedder=None,
        *,
        protected_floor: float = _DEFAULT_PROTECTED_FLOOR,
        protected_quota: int = _PROTECTED_QUOTA,
        dual_write_jsonl: Optional[bool] = None,
    ) -> "MonetaBackedStore":
        """Build a durable, project-scoped Moneta-backed store.

        Snapshot + WAL live under ``<storage_dir>/.moneta/``; the ``storage_uri``
        is stable per project dir so the URI lock and snapshot reload key are
        consistent across restarts. The background snapshot daemon is NOT
        started here — under the async server it races the ECS single-writer
        (FC4). Persistence is via :meth:`save` (synchronous snapshot).

        A corrupt snapshot is quarantined (renamed, preserved) and the store
        starts fresh, rather than crashing startup or silently abandoning the
        file — Moneta's ``hydrate()`` does a bare ``json.load`` (CRUCIBLE finding).
        """
        from .embedding import HashEmbedder, SemanticEmbedder
        from . import moneta_runtime as mr

        if not mr.moneta_available():
            raise RuntimeError(
                f"Moneta backend requested but not importable: {mr.import_error()}"
            )
        if embedder is None:
            try:
                embedder = SemanticEmbedder()
                logger.info(
                    "Using SemanticEmbedder (%s) as default embedder",
                    embedder.id,
                )
            except Exception as exc:
                logger.warning(
                    "SemanticEmbedder init failed (%s: %s); falling back to HashEmbedder",
                    type(exc).__name__, exc,
                )
                embedder = HashEmbedder()
        base = Path(storage_dir) / ".moneta"
        base.mkdir(parents=True, exist_ok=True)
        snapshot_path = base / "snapshot.json"
        cls._quarantine_if_corrupt(snapshot_path)
        cls._quarantine_wal_if_unreplayable(base / "wal.log")
        cfg = mr.MonetaConfig(
            storage_uri=f"moneta-file://{Path(storage_dir).resolve().as_posix()}",
            embedding_dim=embedder.dim,
            quota_override=protected_quota,
            snapshot_path=snapshot_path,
            # wal_path is configured but INERT under SYNAPSE: Moneta's only WAL
            # writer is signal_attention, which SYNAPSE never calls. Durability
            # therefore rests entirely on snapshots (save() + the atexit hook in
            # from_storage_dir), NOT on this log. Kept so an upstream deposit-WAL
            # can light it up without a config change -- do not read it as
            # "deposits are journalled today," because they are not.
            wal_path=base / "wal.log",
            # Phase 4: author typed MonetaMemory prims to USD sublayers.
            # Requires the MonetaMemory schema to be registered
            # (PXR_PLUGINPATH_NAME in the package env) -- without it, USD
            # writes are schema-blind and produce dead bytes.
            use_real_usd=True,
            usd_target_path=base / "usd",  # USD sublayers live under .moneta/usd/
        )
        try:
            handle = mr.Moneta(cfg)
        except Exception as exc:
            logger.warning(
                "Moneta init with use_real_usd=True failed (%s: %s); "
                "retrying without USD sublayers",
                type(exc).__name__, exc,
            )
            cfg_no_usd = mr.MonetaConfig(
                storage_uri=cfg.storage_uri,
                embedding_dim=cfg.embedding_dim,
                quota_override=cfg.quota_override,
                snapshot_path=cfg.snapshot_path,
                wal_path=cfg.wal_path,
                use_real_usd=False,
                usd_target_path=cfg.usd_target_path,
            )
            handle = mr.Moneta(cfg_no_usd)

        # W3-STORE: the handle is now built -- i.e. the W3-DIM dim check has
        # passed (handle construction is exactly what the dim gate protects).
        # Materialize the SYNAPSE-authored cortex at the resolved usd_root:
        # base/cortex_root.usda, the EXACT file server/doctor.py inspects (it
        # hints <store_dir>/.moneta and _resolve_usd_root appends
        # cortex_root.usda). Isolated -- an authoring failure never breaks store
        # construction; the JSONL safety net still carries every memory.
        cortex = None
        try:
            cortex = mr.UsdCortexStore(base)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cortex_root.usda materialization failed (%s: %s); continuing "
                "without a typed USD substrate (JSONL dual-write unaffected)",
                type(exc).__name__, exc,
            )

        # W3-STORE dual-write: when THIS store is the PRIMARY moneta backend,
        # mirror every add to a JSONL MemoryStore so a memory never lands ONLY
        # in moneta. In shadow mode the ShadowMemoryStore ALREADY wraps a JSONL
        # primary, so dual-writing here would double-write memory.jsonl -- gate
        # it on the selected backend, read from the SAME env store.py::
        # _make_store reads (no store.py edit needed). Callers/tests may force it.
        if dual_write_jsonl is None:
            import os
            dual_write_jsonl = (
                os.environ.get("SYNAPSE_MEMORY_BACKEND", "").strip().lower() == "moneta"
            )
        jsonl_net = None
        if dual_write_jsonl:
            try:
                from .store import MemoryStore
                jsonl_net = MemoryStore(storage_dir)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "JSONL safety-net init failed (%s: %s); dual-write disabled "
                    "for this store", type(exc).__name__, exc,
                )

        store = cls(handle, embedder, protected_floor=protected_floor,
                    cortex=cortex, jsonl_net=jsonl_net)
        # Durability (Moneta audit, reachable-bug #1): deposit() writes to the
        # in-memory ECS and returns. There is no per-deposit save, the snapshot
        # daemon is deliberately NOT started (it races the single-writer ECS,
        # see the from_storage_dir docstring), and the WAL is inert because
        # SYNAPSE never calls signal_attention. So without this, a clean process
        # exit dropped every deposit since the last manual sleep pass. Mirror
        # MemoryStore's own atexit flush (store.py) so a normal shutdown snapshots.
        # NOTE: this covers clean exit only -- not kill -9 or a native crash
        # (this repo keeps a crash harness precisely because those happen). Full
        # coverage would need a per-deposit save or an upstream deposit-WAL;
        # that bound is recorded, not silently assumed closed.
        import atexit
        atexit.register(store.close)
        return store

    _SNAPSHOT_REQUIRED_KEYS = (
        "entity_id", "payload", "semantic_vector", "utility",
        "attended_count", "protected_floor", "last_evaluated", "state",
    )

    @classmethod
    def _quarantine_if_corrupt(cls, snapshot_path: Path) -> None:
        """Rename a corrupt snapshot aside so startup neither crashes nor
        silently discards it. Best-effort; a valid/absent snapshot is untouched."""
        if not snapshot_path.exists():
            return
        import json
        import time as _time
        try:
            with open(snapshot_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if not isinstance(data, dict) or not isinstance(data.get("rows", []), list):
                raise ValueError("snapshot missing a 'rows' list")
            for row in data.get("rows", []):
                if not all(k in row for k in cls._SNAPSHOT_REQUIRED_KEYS):
                    raise ValueError("snapshot row missing required keys")
        except Exception as exc:
            bad = snapshot_path.with_name(f"{snapshot_path.name}.corrupt-{int(_time.time())}")
            try:
                snapshot_path.replace(bad)
                logger.error(
                    "Quarantined corrupt Moneta snapshot %s -> %s (%s); starting fresh",
                    snapshot_path, bad, exc,
                )
            except Exception as move_err:  # last resort: remove so startup proceeds
                logger.error(
                    "Corrupt snapshot %s unrecoverable (%s); removing", snapshot_path, move_err
                )
                try:
                    snapshot_path.unlink()
                except OSError:
                    pass

    @classmethod
    def _quarantine_wal_if_unreplayable(cls, wal_path) -> None:
        """Rename aside a WAL Moneta cannot replay, so reopen neither crashes
        nor silently downgrades to jsonl (PRST SEAM, defense-in-depth).

        Moneta's ``durability.wal_read`` parses each entry's ``entity_id`` as a
        UUID with NO guard (only ``json.JSONDecodeError`` is caught upstream).
        A SYNAPSE string id ('mem_...') written there by an EARLIER
        ``signal_attention`` -- now fixed to signal on entity UUIDs, but already
        on disk in stores that ran the old code -- makes cold-start ``hydrate``
        raise, which ``store._make_store`` swallows into a silent empty-jsonl
        fallback. The WAL holds attention SIGNALS only (deposits live in the
        snapshot), so quarantining it loses no memory content: deposits are
        recalled from the snapshot and only a utility nudge is dropped.

        Best-effort; a clean or absent WAL is untouched. A malformed-JSON line
        is left alone -- Moneta itself skips those.
        """
        import json
        import time as _time
        import uuid as _uuid
        wal_path = Path(wal_path)
        if not wal_path.exists():
            return
        poisoned = False
        try:
            with open(wal_path, "r", encoding="utf-8") as fp:
                for raw in fp:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # Moneta itself skips malformed JSON lines
                    try:
                        _uuid.UUID(str(d.get("entity_id", "")))
                    except (ValueError, AttributeError, TypeError):
                        poisoned = True
                        break
        except OSError as exc:
            logger.warning(
                "Could not read Moneta WAL %s (%s); leaving as-is", wal_path, exc
            )
            return
        if not poisoned:
            return
        bad = wal_path.with_name(f"{wal_path.name}.unreplayable-{int(_time.time())}")
        try:
            wal_path.replace(bad)
            logger.error(
                "Quarantined unreplayable Moneta WAL %s -> %s (a non-UUID "
                "entity_id would crash cold-start replay); deposits are recovered "
                "from the snapshot, only attention signals are dropped",
                wal_path, bad,
            )
        except OSError as move_err:  # last resort: remove so reopen proceeds
            logger.error(
                "Unreplayable WAL %s could not be quarantined (%s); removing",
                wal_path, move_err,
            )
            try:
                wal_path.unlink()
            except OSError:
                pass

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
        with self._lock:
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
            # Durability (PRST SEAM A): persist EVERY deposit synchronously
            # before add() returns. The previous 30s throttle
            # (now - _last_save >= _save_interval) acknowledged a NON-FIRST
            # deposit to the caller that never reached disk when the process
            # died via os._exit (no atexit, the crash class) -- the exact repro
            # in test_second_deposit_of_a_session_survives_abrupt_restart. save()
            # is a full atomic snapshot taken under self._lock, so it does not
            # race the single-writer ECS and can neither lose nor duplicate a
            # deposit. Cost is O(n) per deposit; the from_storage_dir docstring
            # already named a per-deposit save as the durability fix, and for
            # USER MEMORY correctness outranks the write cost.
            self.save()  # sets self._last_save
            # Opportunistic consolidation: every 100 adds, if the engine has
            # more than 1000 entities, run a sleep pass to keep memory bounded.
            self._add_count += 1
            if self._add_count % 100 == 0 and self._handle.ecs.n > 1000:
                try:
                    audit = self.run_sleep_pass()
                    if audit.pruned > 0:
                        logger.info(
                            "Consolidation pruned %d memories (before=%d, after=%d)",
                            audit.pruned, audit.count_before, audit.count_after,
                        )
                except Exception as exc:
                    logger.warning(
                        "Periodic consolidation failed (%s: %s); continuing",
                        type(exc).__name__, exc,
                    )

            # W3-STORE secondary sinks (still under the lock so the cortex stage
            # mutation is serialized against reads). The moneta deposit +
            # snapshot above are the PRIMARY substrate; these MIRROR it. Both are
            # isolated -- a sink failure is logged and never breaks the caller or
            # the moneta write. Order: moneta (durable) -> cortex (typed USD) ->
            # JSONL safety net.
            self._write_cortex(memory, payload)
            self._dual_write_jsonl(memory)
        return memory.id

    # -- W3-STORE secondary sinks (isolated; never break the primary write) --

    def _write_cortex(self, memory: Memory, payload: str) -> None:
        """Mirror the memory into cortex_root.usda as a typed prim keyed by
        (kind, id). ``kind`` is the memory type value, ``id`` the SYNAPSE id,
        ``payload`` the same ``Memory.to_json()`` deposited into moneta."""
        cortex = self._cortex
        if cortex is None:
            return
        try:
            cortex.write(memory.memory_type.value, memory.id, payload)
        except Exception as exc:  # noqa: BLE001 -- typed-USD authoring is best-effort
            logger.warning("cortex write failed (isolated): %s", exc)

    def _dual_write_jsonl(self, memory: Memory) -> None:
        """Land the memory in the JSONL MemoryStore safety net via its own,
        unchanged write path (add -> buffered append -> flush). On first use,
        ensure the key.fingerprint sidecar exists (W3-STORE target 4)."""
        net = self._jsonl_net
        if net is None:
            return
        try:
            net.add(memory)
            net.flush()  # synchronous append; drains the buffer to memory.jsonl
            if not self._sidecar_ensured:
                self._ensure_keyfp_sidecar()
                self._sidecar_ensured = True
        except Exception as exc:  # noqa: BLE001 -- the safety net must never break the caller
            logger.warning("JSONL dual-write failed (isolated): %s", exc)

    def _ensure_keyfp_sidecar(self) -> None:
        """Write ``<storage_dir>/key.fingerprint`` on first use so the doctor's
        ``memory_key_fingerprint`` check moves ``no_sidecar`` -> ``match``.

        Mirrors ``MemoryStore.save()``'s C3 stamp EXACTLY -- same file, same
        content (``crypto.fingerprint()``) -- but WITHOUT a full JSONL rewrite,
        so the safety net's write path is untouched. Uses the SAME cached
        CryptoEngine the net's ``add()`` used to encrypt its lines, so the
        fingerprint describes the key that actually wrote memory.jsonl (and the
        one the doctor resolves from ~/.synapse/encryption.key). No crypto (no
        ``cryptography`` / no key) -> no meaningful sidecar to write."""
        net = self._jsonl_net
        if net is None:
            return
        try:
            from . import store as _store_mod
            crypto = _store_mod._get_crypto()
            if crypto is None:
                return
            sidecar = net.storage_dir / "key.fingerprint"
            if not sidecar.exists():
                sidecar.write_text(crypto.fingerprint(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 -- non-critical
            logger.debug("key.fingerprint sidecar ensure failed (non-critical): %s", exc)

    # -- enumerate (the one coupling to Moneta internals, centralized) ------

    def _iter_memories(self) -> List[Memory]:
        # Snapshot the engine under the lock and return a list — NOT a generator.
        # A lazy generator would hold the lock across caller work (or until GC if
        # abandoned). Materializing the rows under the lock gives every read an
        # atomic point-in-time view; the expensive JSON deserialization runs
        # lock-free. All read methods inherit safety from this single snapshot.
        #
        # Corrupt payloads are skipped with a warning rather than failing the
        # entire read — one bad entry must never hide every other memory.
        with self._lock:
            rows = list(self._handle.ecs.iter_rows())
        result: List[Memory] = []
        for row in rows:
            try:
                result.append(Memory.from_json(row.payload))
            except Exception as exc:
                logger.warning(
                    "Skipping corrupt Moneta row %s: %s",
                    getattr(row, "entity_id", "<unknown>"), exc,
                )
        return result

    # -- read ---------------------------------------------------------------

    def count(self) -> int:
        with self._lock:
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
        # Raw, case-sensitive — matches search() tag semantics across stores.
        return [m for m in self._iter_memories() if tag in m.tags]

    def get_linked(self, memory_id: str) -> List[Memory]:
        all_mems = list(self._iter_memories())
        src = next((m for m in all_mems if m.id == memory_id), None)
        if src is None:
            return []
        targets = {link.target_id for link in src.links}
        return [m for m in all_mems if m.id in targets]

    def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        # Hybrid: vector recall as candidate pre-filter, keyword scoring for ranking.
        # When query.text is present, we embed it and use Moneta's vector query to
        # retrieve a candidate pool (over-fetched 3x, minimum 50). The keyword
        # scoring in score_memories then reranks these candidates — it needs room
        # to differentiate memories that are all vector-nearby but differ in
        # keyword/tag/text-match relevance. Over-fetching ensures the reranker has
        # enough candidates to produce a meaningful ordering, not just the top-N
        # that happened to be closest in embedding space.
        # For non-text queries (tags/keywords only), fall back to the full scan.
        if query.text:
            embedding = self._embedder.embed(query.text)
            # Map SYNAPSE memory id -> Moneta entity_id (UUID). Only the vector
            # path yields entity ids; the keyword fallback below does not, so it
            # will not signal attention (correct -- there is nothing to key on).
            entity_by_syn_id: Dict[str, object] = {}
            try:
                vector_results = self._handle.query(
                    embedding, limit=max(query.limit * 3, 50)
                )
                memories = []
                for r in vector_results:
                    syn = Memory.from_json(r.payload)
                    memories.append(syn)
                    entity_by_syn_id[str(syn.id)] = r.entity_id
                logger.info(
                    "Vector recall: %d candidates from query (limit=%d, overfetch=%d)",
                    len(vector_results), query.limit, max(query.limit * 3, 50),
                )
            except Exception as exc:
                logger.warning(
                    "Vector query failed (%s: %s); falling back to keyword scan",
                    type(exc).__name__, exc,
                )
                memories = self._iter_memories()
            results = score_memories(memories, query)
            # Attention signaling: boost utility of frequently-accessed memories.
            # Signal on Moneta ENTITY ids (UUIDs), never SYNAPSE string ids
            # ('mem_...'). Two reasons: (1) those strings are not entities Moneta
            # indexes, so the old signal was a no-op; (2) PRST SEAM -- Moneta
            # journals every signal to its WAL, whose cold-start replay parses
            # entity_id as a UUID with NO guard (durability.wal_read), so a
            # non-UUID key there crashes the very NEXT reopen, which _make_store
            # then swallows into a silent empty-jsonl downgrade. Best-effort and
            # non-critical: failure never breaks search().
            if results and entity_by_syn_id:
                try:
                    weights = {}
                    for r in results[:5]:
                        eid = entity_by_syn_id.get(str(r.memory.id))
                        if eid is not None:
                            weights[eid] = float(r.score)
                    if weights:
                        self._handle.signal_attention(weights)
                        logger.debug(
                            "Attention signaled on %d entities", len(weights),
                        )
                except Exception as exc:
                    logger.debug("Attention signaling failed (non-critical): %s", exc)
            return results
        return score_memories(self._iter_memories(), query)

    # -- lifecycle ----------------------------------------------------------

    def save(self) -> None:
        """Durably snapshot the engine. No-op when durability is disabled (ephemeral)."""
        with self._lock:
            dur = getattr(self._handle, "durability", None)
            if dur is not None:
                try:
                    dur.snapshot_ecs(self._handle.ecs)
                    self._last_save = time.monotonic()
                except Exception as exc:
                    logger.warning("Moneta snapshot on save() failed: %s", exc)

    def run_sleep_pass(self) -> PruneAudit:
        """Trigger Moneta consolidation/decay — AUDITABLE and serialized.

        This is the one destructive memory op: it permanently prunes unprotected
        memories. We enumerate the live id-set + payloads BEFORE the pass, run it,
        then diff the survivors to recover exactly which entities were pruned —
        so data loss is logged, never silent. Held under the lock (the prune
        mutates the ECS and must not interleave with deposit/iterate).
        """
        with self._lock:
            ecs = self._handle.ecs
            before_payload: Dict[str, str] = {}
            before_mem: Dict[str, Optional[Memory]] = {}
            for row in ecs.iter_rows():
                eid = str(row.entity_id)
                before_payload[eid] = row.payload
                try:
                    before_mem[eid] = Memory.from_json(row.payload)
                except Exception:
                    before_mem[eid] = None  # keep the raw payload for forensics
            count_before = ecs.n

            result = self._handle.run_sleep_pass()

            survivors = {str(row.entity_id) for row in ecs.iter_rows()}
            count_after = ecs.n

        pruned_eids = [eid for eid in before_payload if eid not in survivors]
        pruned_ids: List[str] = []
        pruned_types: Dict[str, str] = {}
        for eid in pruned_eids:
            mem = before_mem.get(eid)
            if mem is not None:
                pruned_ids.append(mem.id)
                pruned_types[mem.id] = getattr(mem.memory_type, "value", str(mem.memory_type))

        audit = PruneAudit(
            pruned_ids=pruned_ids,
            pruned_entity_ids=pruned_eids,
            pruned_payloads={eid: before_payload[eid] for eid in pruned_eids},
            pruned_types=pruned_types,
            count_before=count_before,
            count_after=count_after,
            attention_updated=getattr(result, "attention_updated", 0),
            staged=getattr(result, "staged", 0),
        )
        if audit.pruned:
            logger.warning(
                "moneta.prune lossless-audit pruned=%d staged=%d before=%d after=%d ids=%s",
                audit.pruned, audit.staged, count_before, count_after, pruned_ids,
            )
        else:
            logger.info(
                "moneta.sleep_pass pruned=0 staged=%d attended=%d n=%d",
                audit.staged, audit.attention_updated, count_after,
            )
        return audit

    def close(self) -> None:
        # Idempotent: registered with atexit AND callable explicitly, so a
        # normal `close()` followed by interpreter shutdown must not double-close
        # the handle (Moneta's URI lock release is not re-entrant).
        with self._lock:
            if getattr(self, "_closed", False):
                return
            self._closed = True
            self.save()
            # W3-STORE: drain the JSONL safety net and persist the cortex before
            # releasing the handle. Both isolated -- a sink close must not stop
            # the handle's URI-lock release.
            if self._jsonl_net is not None:
                try:
                    self._jsonl_net.flush()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("JSONL safety-net flush on close failed: %s", exc)
            if self._cortex is not None:
                try:
                    self._cortex.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("cortex close failed: %s", exc)
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
