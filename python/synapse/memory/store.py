"""
Synapse Memory Store

Persistent storage for project memories.
Stores data in $HIP/.synapse/ alongside the Houdini project file.

Storage format:
- memory.jsonl: Append-only memory log (one JSON per line)
- index.json: Search index and metadata
- context.md: Human-readable project context
- decisions.md: Human-readable decision log
- tasks.md: Human-readable task history

Migration: Automatically migrates .nexus/ or .engram/ to .synapse/ if needed.
"""

import atexit
import logging
import os
import json
import hashlib
import re
import time
import shutil
import tempfile
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from functools import wraps

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

try:
    from ..core.crypto import CryptoEngine, ENCRYPTION_AVAILABLE, MAGIC_PREFIX
except ImportError:
    ENCRYPTION_AVAILABLE = False
    MAGIC_PREFIX = "SYNAPSE_ENC_V1:"

logger = logging.getLogger("synapse.memory")

# Cached CryptoEngine instance — avoids repeated get_instance() calls.
# _CRYPTO_NOT_CHECKED sentinel distinguishes "not checked yet" from "checked and None".
_CRYPTO_NOT_CHECKED = object()
_crypto_instance = _CRYPTO_NOT_CHECKED


def _get_crypto():
    """Return cached CryptoEngine instance, or None if unavailable."""
    global _crypto_instance
    if _crypto_instance is _CRYPTO_NOT_CHECKED:
        _crypto_instance = CryptoEngine.get_instance() if ENCRYPTION_AVAILABLE else None
    return _crypto_instance


# =============================================================================
# READ-WRITE LOCK
# =============================================================================

class ReadWriteLock:
    """Writer-priority read-write lock.

    Multiple readers can hold the lock simultaneously, but a writer gets
    exclusive access.  Writer-priority: when a writer is waiting, new
    readers queue behind it to prevent writer starvation.
    """

    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers: int = 0
        self._writer: bool = False
        self._writer_waiting: int = 0

    # -- context managers ---------------------------------------------------

    class _ReadCtx:
        __slots__ = ("_rwl",)

        def __init__(self, rwl: "ReadWriteLock"):
            self._rwl = rwl

        def __enter__(self):
            self._rwl._acquire_read()
            return self

        def __exit__(self, *exc):
            self._rwl._release_read()

    class _WriteCtx:
        __slots__ = ("_rwl",)

        def __init__(self, rwl: "ReadWriteLock"):
            self._rwl = rwl

        def __enter__(self):
            self._rwl._acquire_write()
            return self

        def __exit__(self, *exc):
            self._rwl._release_write()

    def read_lock(self):
        """Return a context manager for shared (read) access."""
        return self._ReadCtx(self)

    def write_lock(self):
        """Return a context manager for exclusive (write) access."""
        return self._WriteCtx(self)

    # -- primitives ---------------------------------------------------------

    def _acquire_read(self):
        with self._cond:
            # Wait if a writer is active OR a writer is waiting (priority)
            while self._writer or self._writer_waiting > 0:
                self._cond.wait()
            self._readers += 1

    def _release_read(self):
        with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def _acquire_write(self):
        with self._cond:
            self._writer_waiting += 1
            while self._writer or self._readers > 0:
                self._cond.wait()
            self._writer_waiting -= 1
            self._writer = True

    def _release_write(self):
        with self._cond:
            self._writer = False
            self._cond.notify_all()


from .models import (
    Memory,
    MemoryType,
    MemoryTier,
    MemoryLink,
    LinkType,
    MemoryQuery,
    MemorySearchResult
)


# =============================================================================
# MEMORY STORE
# =============================================================================

def _metadata_richness(memory) -> tuple:
    """How much artist metadata a record carries, as a sortable tuple.

    Used by :meth:`MemoryStore.add` to decide which of two colliding records
    survives. NOT a quality judgement about content -- the colliding pair always
    share identical ``content``; only the metadata around it differs.

    The ordering is the one the manual repair of the 2026-09-15 corruption used,
    kept identical on purpose so the automatic path and the recovery tool can
    never disagree about which twin is authoritative:

        (tag count, hip_file present, source is not 'auto', frame set, hip_version)

    ``source='auto'`` ranks LAST deliberately: it is the signature of the lossy
    deposit at ``scene_memory.py:729``, which constructs its Memory with tags,
    hip_file, hip_version and frame left at dataclass defaults. Every one of the
    five records that degraded the store carried it.

    Total and never raises -- a record missing an attribute simply scores lower,
    because a health-critical write path must not fail on an unexpected shape.
    """
    g = lambda name, default=None: getattr(memory, name, default)
    try:
        tags = g("tags") or ()
        tag_count = len(tags)
    except TypeError:
        tag_count = 0
    return (
        tag_count,
        1 if (g("hip_file") or "") else 0,
        0 if (g("source") or "") == "auto" else 1,
        1 if g("frame") is not None else 0,
        1 if (g("hip_version") or 0) else 0,
    )


class MemoryStore:
    """
    Low-level memory storage and retrieval.

    Handles:
    - Persisting memories to disk
    - Loading memories on startup
    - Basic search and filtering
    """

    # Throttle evolution checks: at most once per N add() calls

    def __init__(self, storage_dir: Path, background_load: bool = True):
        self.storage_dir = Path(storage_dir)
        self.memory_file = self.storage_dir / "memory.jsonl"
        self.index_file = self.storage_dir / "index.json"

        self._memories: Dict[str, Memory] = {}
        self._add_count = 0  # Counter for evolution throttle
        self._index: Dict[str, Any] = {
            "by_type": {},
            "by_tag": {},
            "by_keyword": {},
            "links": {},
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "updated": "",
            "version": 1
        }
        self._lock = ReadWriteLock()
        self._dirty = False
        self._needs_rewrite = False  # Set by update/delete to trigger full save
        # Any incomplete load refuses writes so a checkpoint cannot destroy
        # recoverable plaintext, ciphertext, or conflicting identities.
        self._degraded_load = False
        self._degraded_reason = ""
        # B6: every refused or downgraded write is COUNTED, not merely raised.
        # The 2026-09-15 15:09 -> 2026-09-17 15:53 outage (this store DEGRADED,
        # refusing every write for ~2 days) was invisible because the only
        # evidence was one ERROR line at load time. A raise is not evidence
        # either: the JSONL safety net (moneta_store._dual_write_jsonl) wraps
        # its call to this store in a bare `except Exception` so the net can
        # never break its caller, which swallows anything we throw. The counter
        # is what survives that swallow and reaches health().
        self._rejected_writes = 0
        # Counted SEPARATELY from _rejected_writes. That counter also rises on
        # add_durable_if_absent's CORRECT idempotency refusal, so it cannot be
        # promoted to a health signal without false-positiving every deposit.
        # This one rises only where prior data was actually overwritten.
        self._overwrote_prior = 0
        self._rejection_lock = threading.Lock()
        self._loaded = threading.Event()

        # Write buffer — defers disk I/O to background thread (saves 1-5ms per add)
        self._write_buffer: list = []
        self._write_lock = threading.Lock()
        self._flush_interval = 2.0  # seconds
        self._flush_max = 50  # items
        self._flush_event = threading.Event()  # Wakes flusher immediately on buffer full
        self._flusher = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="Synapse-MemoryFlush",
        )
        self._flusher_running = True
        self._flusher.start()

        # Ensure buffered writes survive interpreter shutdown
        atexit.register(self._shutdown_flush)

        self._ensure_storage_dir()

        if background_load:
            loader = threading.Thread(
                target=self._load,
                daemon=True,
                name="Synapse-MemoryLoad",
            )
            loader.start()
        else:
            self._load()

    def _flush_loop(self):
        """Background thread: flush buffered writes to disk.

        Wakes on either the flush interval (2s) OR immediately when
        the buffer hits capacity (via _flush_event). This eliminates
        the worst-case 4s latency under low write frequency.
        """
        while self._flusher_running:
            # Clear before wait to prevent eating a set() signal from another thread
            self._flush_event.clear()
            self._flush_event.wait(timeout=self._flush_interval)
            self._flush_writes()

    def _flush_writes(self):
        """Flush buffered memory lines to disk.

        If _needs_rewrite is set (from update/delete), does a full rewrite
        via save() since JSONL append-only format can't express mutations.
        Otherwise, appends buffered add() lines.
        """
        # A loader can still be checking the source. Never append to a source
        # whose integrity is unknown or was found incomplete.
        self._wait_loaded()
        if not self._loaded.is_set() or self._degraded_load:
            return
        # Check if a full rewrite is needed (update/delete happened)
        if self._needs_rewrite:
            # Drain the append buffer (those adds are already in _memories)
            with self._write_lock:
                self._write_buffer.clear()
            self._needs_rewrite = False
            try:
                self.save()
            except Exception as e:
                logger.error("Full rewrite flush error: %s", e)
            return

        with self._write_lock:
            if not self._write_buffer:
                return
            lines = self._write_buffer[:]
            self._write_buffer.clear()

        try:
            with open(self.memory_file, 'a', encoding='utf-8') as f:
                f.write("".join(lines))
        except Exception as e:
            logger.error("Write flush error, restoring %d lines to buffer: %s", len(lines), e)
            with self._write_lock:
                # Prepend failed lines back (they're older than anything new)
                self._write_buffer[0:0] = lines

    def flush(self):
        """Force-flush any buffered writes (call on shutdown)."""
        self._flush_writes()

    def _shutdown_flush(self):
        """atexit handler: stop flusher thread and drain buffer."""
        self._flusher_running = False
        self._flush_writes()

    def _ensure_storage_dir(self):
        """Create storage directory if it doesn't exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _keyfp_file(self) -> Path:
        return self.storage_dir / "key.fingerprint"

    def _key_fingerprint_mismatch(self, crypto) -> Optional[str]:
        """C3: compare the active key's fingerprint to the plaintext sidecar written on
        the last save. Mismatch ⇒ the key changed ⇒ refuse rewrite (prevents a mixed-key
        file). No sidecar / no crypto / empty sidecar ⇒ no opinion (fail-safe)."""
        if not crypto or not self._keyfp_file.exists():
            return None
        try:
            stored = self._keyfp_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        try:
            active = crypto.fingerprint()
        except Exception:
            return None
        if stored and active and stored != active:
            return f"encryption-key fingerprint changed ({stored} -> {active})"
        return None

    def _quarantine_store(self, reason: str = "degraded") -> Optional[Path]:
        """COPY the on-disk store aside as a timestamped recovery point. We copy,
        never move/delete — the unreadable ciphertext is exactly the recoverable
        asset. Best-effort; never raises (a failed copy still leaves the original)."""
        if not self.memory_file.exists():
            return None
        aside = self.memory_file.with_name(
            f"{self.memory_file.name}.{reason}-{int(time.time())}"
        )
        try:
            shutil.copy2(str(self.memory_file), str(aside))
            logger.error("Quarantined a copy of the store for recovery: %s", aside)
            return aside
        except OSError as e:
            logger.error("Could not quarantine the store (%s); original untouched", e)
            return None

    def _load(self):
        """Load memories from disk."""
        if not self.memory_file.exists():
            self._loaded.set()
            return

        crypto = _get_crypto()
        unreadable = []
        seen = {}

        with self._lock.write_lock():
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            if crypto:
                                line = crypto.decrypt_line(line)
                            data = json.loads(line)
                            required = ("id", "created_at", "content", "memory_type")
                            if (not isinstance(data, dict)
                                    or any(not isinstance(data.get(key), str) for key in required)
                                    or not data["id"] or not data["created_at"]):
                                raise ValueError("incomplete record identity or content")
                            memory = Memory.from_dict(data)
                            canonical = json.dumps(data, sort_keys=True)
                            prior = seen.get(memory.id)
                            if prior is not None:
                                if prior != canonical:
                                    raise ValueError("conflicting duplicate memory identity")
                                continue
                            seen[memory.id] = canonical
                            self._memories[memory.id] = memory
                            self._index_memory(memory)
                        except Exception as e:
                            unreadable.append(f"line {line_num}: {e}")
                            logger.warning("Failed to load memory on line %d: %s", line_num, e)
            except (OSError, UnicodeError) as e:
                unreadable.append(f"source read failed: {e}")

            # Load index if exists
            if self.index_file.exists():
                try:
                    with open(self.index_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if crypto:
                        content = crypto.decrypt_file_content(content)
                    loaded = json.loads(content)
                    # Convert lists to sets for by_type/by_tag/by_keyword
                    for section in ("by_type", "by_tag", "by_keyword"):
                        if section in loaded:
                            loaded[section] = {
                                k: set(v) if isinstance(v, list) else v
                                for k, v in loaded[section].items()
                            }
                    # Live index built from JSONL is authoritative — don't overwrite
                    logger.debug(
                        "Saved index loaded (%d types, %d tags) but live index from JSONL is authoritative",
                        len(loaded.get("by_type", {})),
                        len(loaded.get("by_tag", {})),
                    )
                except Exception as e:
                    logger.warning("Failed to load index: %s", e)

        # Plaintext corruption and identity conflicts are as recoverable as a
        # wrong encryption key. A partial read cannot authorize a rewrite.
        degraded_reason = (
            f"{len(unreadable)} incomplete source record/read(s): {unreadable[0]}"
            if unreadable else self._key_fingerprint_mismatch(crypto)
        )
        if degraded_reason:
            self._degraded_load = True
            self._degraded_reason = degraded_reason
            logger.error(
                "DEGRADED LOAD: %s in %s. Refusing writes; recover the source or "
                "encryption key, then reopen. Original bytes are preserved.",
                degraded_reason, self.memory_file,
            )
            self._quarantine_store(reason="degraded-load")

        logger.info("Loaded %d memories from %s", len(self._memories), self.storage_dir)
        self._loaded.set()
        # After load completes, replace _wait_loaded with a no-op to skip
        # the Event.is_set() check on every subsequent read call
        self._wait_loaded = lambda timeout=2.0: None

    def _index_memory(self, memory: Memory):
        """Add memory to in-memory indices (sets for O(1) membership)."""
        # Index by type
        type_key = memory.memory_type.value
        if type_key not in self._index["by_type"]:
            self._index["by_type"][type_key] = set()
        self._index["by_type"][type_key].add(memory.id)

        # Index by tags
        for tag in memory.tags:
            if tag not in self._index["by_tag"]:
                self._index["by_tag"][tag] = set()
            self._index["by_tag"][tag].add(memory.id)

        # Index by keywords
        for keyword in memory.keywords:
            if keyword not in self._index["by_keyword"]:
                self._index["by_keyword"][keyword] = set()
            self._index["by_keyword"][keyword].add(memory.id)

        # Index links
        for link in memory.links:
            if memory.id not in self._index["links"]:
                self._index["links"][memory.id] = []
            link_entry = {"target": link.target_id, "type": link.link_type.value}
            if link_entry not in self._index["links"][memory.id]:
                self._index["links"][memory.id].append(link_entry)

    def _wait_loaded(self, timeout: float = 2.0):
        """Block until background load completes (max timeout seconds)."""
        if self._loaded.is_set():
            return  # Fast path — already loaded
        self._loaded.wait(timeout=timeout)

    def _write_refusal_reason(self) -> str:
        """The ONE predicate behind both ``_require_writable_load()`` and
        ``health()["writable"]`` — they cannot disagree, because they read it here.

        Returns ``""`` when a write would be accepted right now, otherwise the
        operator-readable reason it would be refused. Deliberately does NOT wait
        on the loader: ``health()`` may be polled by the panel and must never
        block behind a 2s load. ``_require_writable_load()`` does the waiting
        itself, then asks this.
        """
        if not self._loaded.is_set():
            return "memory source is still loading"
        if self._degraded_load:
            return (
                "the store loaded in DEGRADED mode. "
                "Original bytes are preserved; recover the source or encryption "
                f"key, then reopen. {self._degraded_reason}"
            )
        return ""

    def _note_rejected_write(self, reason: str):
        """Record a refused or downgraded write in durable, readable state.

        Correct behaviour here has to be OBSERVABLE, not thrown. The JSONL
        safety net (``moneta_store._dual_write_jsonl``, ``except Exception``
        by design so the net never breaks its caller) swallows anything this
        store raises, so a raise alone leaves no trace anyone can find two days
        later. This counter does — ``health()["rejected_writes"]`` reads it, and
        the WARNING gives the log reader the specific reason.
        """
        with self._rejection_lock:
            self._rejected_writes += 1
            total = self._rejected_writes
        logger.warning(
            "Memory write refused or downgraded (%d so far in this store): %s",
            total, reason,
        )

    def _require_writable_load(self):
        """No write may acknowledge or replace an incomplete source read."""
        self._wait_loaded()
        reason = self._write_refusal_reason()
        if reason:
            self._note_rejected_write(reason)
            raise RuntimeError(f"Refusing to write: {reason}")

    # -- health surface (B6) --------------------------------------------------
    # ``_degraded_load`` used to be read at exactly three internal sites and by
    # NO health, doctor, panel or MCP surface. That is precisely why a two-day
    # write outage was visible only as a log line nobody reads. These three
    # members are the missing surface. Keep them cheap — a panel may poll them.

    @property
    def is_degraded(self) -> bool:
        """True when the store failed its load integrity check and is refusing writes."""
        return bool(self._degraded_load)

    @property
    def degraded_reason(self) -> str:
        """Why the load was degraded. ``""`` when healthy — never None, so a
        caller can print it unconditionally."""
        return self._degraded_reason or ""

    def health(self) -> Dict[str, Any]:
        """Operator-readable verdict on this store. ALWAYS five keys, NEVER raises.

        ``{"degraded": bool, "reason": str, "writable": bool,
           "records": int, "rejected_writes": int,
           "overwrote_prior": int}``

        - ``writable`` is derived from ``_write_refusal_reason()`` — the same
          predicate ``_require_writable_load()`` enforces — so "health says
          writable" and "a write is actually accepted" can never drift apart.
        - ``rejected_writes`` is monotonic for the life of the store object and
          counts every write this store refused or downgraded, including
          collision downgrades in ``add()`` that never reached the caller
          because the dual-write net swallowed them.
        - ``overwrote_prior`` counts ONLY writes that replaced data already in the
          store -- the add() collision downgrade. It is deliberately separate from
          ``rejected_writes``, which also rises on ``add_durable_if_absent``'s
          CORRECT idempotency refusal and so cannot be read as a fault on its own.
          A non-zero value here means metadata was lost and nothing raised.
        - A health check that throws is not a health check: any failure returns
          the fail-closed defaults below (degraded, unwritable) rather than a
          green answer or an exception.
        """
        report: Dict[str, Any] = {
            # Fail-closed defaults. If the probe cannot complete, the honest
            # answer is "sick and unwritable", never a reassuring blank.
            "degraded": True,
            "reason": "health probe did not complete",
            "writable": False,
            "records": -1,
            "rejected_writes": -1,
            "overwrote_prior": -1,
        }
        try:
            degraded = bool(self._degraded_load)
            reason = self._degraded_reason or ""
            writable = not self._write_refusal_reason()
            # Read the dict length WITHOUT the read lock on purpose: a health
            # probe that queues behind a writer is a health probe that freezes
            # the panel. A count one record stale is still an honest count.
            records = len(self._memories)
            with self._rejection_lock:
                rejected = self._rejected_writes
                overwrote = self._overwrote_prior
        except Exception as exc:  # noqa: BLE001 -- a health check that throws is not a health check
            report["reason"] = f"health probe failed: {exc}"
            logger.warning("MemoryStore.health() probe failed: %s", exc)
            return report

        report.update(
            degraded=degraded,
            reason=reason,
            writable=writable,
            records=records,
            rejected_writes=rejected,
            overwrote_prior=overwrote,
        )
        return report

    def save(self):
        """Persist all memories to disk."""
        self._require_writable_load()
        crypto = _get_crypto()
        # C2: atomic, backed-up writes. Lazy import keeps store.py's import order
        # unchanged (this module loads very early; write_report is zero-`hou`, and
        # ledger.py already depends on it, so the memory→cognitive.tools edge is safe).
        from ..cognitive.tools.write_report import write_report

        with self._lock.write_lock():
            # Build memory.jsonl content (per-line encrypted when crypto is present).
            mem_lines = []
            for memory in self._memories.values():
                line = memory.to_json()
                if crypto:
                    line = crypto.encrypt_line(line)
                mem_lines.append(line)
            mem_content = "".join(line + "\n" for line in mem_lines)

            # Build index content — sets → sorted lists for JSON serialization.
            serializable_index = dict(self._index)
            for section in ("by_type", "by_tag", "by_keyword"):
                serializable_index[section] = {
                    k: sorted(v) if isinstance(v, set) else v
                    for k, v in self._index[section].items()
                }
            serializable_index["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            index_content = json.dumps(serializable_index, indent=2, sort_keys=True)
            if crypto:
                index_content = crypto.encrypt_file_content(index_content)

            # Atomic (tmp + fsync + os.replace) with one generational .bak — a crash
            # mid-save leaves the prior file intact instead of truncated.
            write_report(self.memory_file.name, mem_content,
                         base_dir=str(self.storage_dir), backups=1)
            write_report(self.index_file.name, index_content,
                         base_dir=str(self.storage_dir), backups=1)

            # C3: stamp the active key's (non-secret) fingerprint so the next load can
            # detect a key change before rewriting. Plaintext on purpose — it must be
            # readable even when the key is wrong. Best-effort; a torn sidecar is empty
            # → no opinion (fail-safe).
            if crypto:
                try:
                    self._keyfp_file.write_text(crypto.fingerprint(), encoding="utf-8")
                except OSError:
                    pass

            self._dirty = False

    def add_durable_if_absent(self, memory: Memory) -> bool:
        """Checked immutable insertion; a collision never evicts prior data."""
        self._require_writable_load()
        with self._lock.write_lock():
            previous = self._memories.get(memory.id)
            if previous is not None and previous.to_json() != memory.to_json():
                # A refused write, same class of event as the add() collision —
                # count it so health() reflects every rejection, not just the
                # ones that happen to reach a caller who checks.
                self._note_rejected_write(
                    f"add_durable_if_absent() refused id {memory.id!r}: the "
                    "identity already holds different data"
                )
                raise ValueError("Memory identity already contains different data")
            inserted = previous is None
            if inserted:
                self._memories[memory.id] = memory
                self._index_memory(memory)
                self._dirty = True
        # Save outside the non-reentrant writer lock. Like Moneta, a failed
        # checkpoint leaves an unsettled insertion, never a durable success.
        self.save()
        return inserted

    def add(self, memory: Memory) -> str:
        """Add a memory to the store.

        Buffers disk write for background flush (saves 1-5ms per call).
        In-memory state is updated immediately for read consistency.

        B3 — the id-collision guard. Without it, ``add()`` replaced the record
        in ``_memories`` and ALSO appended a fresh line, so an id that already
        existed with different content left the file holding two differing
        lines for one identity. The next process to open it hits ``_load``'s
        "conflicting duplicate memory identity", which degrades the WHOLE store
        and refuses EVERY write until a human intervenes. One bad line is
        enough; two ``add()`` calls and one restart reproduce the full two-day
        outage of 2026-09-15 -> 2026-09-17. So this method must never be able to
        plant that line:

        - **new id** — the original fast path, untouched. This is hot: no extra
          file read, no second lock round-trip for the normal case.
        - **same id, byte-identical payload** — a harmless re-add. No-op; the
          append would be legal but pointless.
        - **same id, different payload** — this was never an add, it is an
          UPDATE. Append-only JSONL cannot express a mutation, and the class
          already knows that: ``update()`` sets ``_needs_rewrite`` so the next
          flush does a full ``save()``. Routed there rather than duplicated.

        The divergent case deliberately does NOT raise. Its only production
        caller is ``moneta_store._dual_write_jsonl``, whose bare
        ``except Exception`` exists so the safety net can never break the
        caller — a raise here would be swallowed, trading a loud-but-late
        outage for a silent permanent divergence between Moneta (the primary)
        and the JSONL mirror. It is recorded instead: counted into
        ``health()["rejected_writes"]`` and logged at WARNING.
        """
        self._require_writable_load()
        with self._lock.write_lock():
            existing = self._memories.get(memory.id)
            if existing is None:
                self._memories[memory.id] = memory
                self._index_memory(memory)
                self._dirty = True
                diverged = False
            else:
                # Compare the exact bytes that would hit the file. ``to_json()``
                # is sort_keys=True — the same canonical form ``_load`` computes
                # per line — so "differs here" is precisely "conflicts there".
                diverged = existing.to_json() != memory.to_json()

        if existing is not None:
            if not diverged:
                return memory.id  # byte-identical re-add: nothing to write
            # WHY THIS ROUTES AND NEVER DROPS.
            #
            # An intermediate version of this guard kept whichever record carried
            # more metadata and DISCARDED the other, while still returning
            # memory.id. An adversarial review measured the consequence: a caller
            # cannot tell. ledger.py:486 sets status["deposited"]=True off this
            # return, seed_corpus.py:179 counts it as written, vex_capture.py:112
            # hands it back as the id -- all three would report success over a
            # write that never landed. That is the SAME silent-failure class this
            # whole incident is about, so it was removed. The WRITE is always
            # routed -- never discarded while reporting success.
            #
            # BUT BE PRECISE ABOUT WHAT IS LOST. update() makes the INCOMING record
            # win, and in the incident's own shape the incoming record is the
            # metadata-stripped twin. So the prior record's tags, hip_file and frame
            # ARE replaced, and add() returns success. Pre-fix that was loud, late
            # and recoverable (the line stayed on disk and the next load screamed);
            # here it is quiet and immediate. Bounded, not absent -- content
            # participates in the id, so a collision is metadata-only and never a
            # lost edit. It is counted into health()["overwrote_prior"], which the
            # health surfaces read as NOT-green precisely so it cannot pass as fine.
            #
            # Losing metadata is not the risk it looks like, because CONTENT
            # PARTICIPATES IN THE ID (models.py:157-162 hashes
            # content:created_at:memory_type). Two records sharing an id
            # therefore share their content: a collision is always a
            # METADATA-only difference, never a lost edit. And the producer that
            # generated those differing-metadata pairs is fixed at source --
            # scene_memory.py's deposit is now suppressed for callers that
            # already deposited (see tracker.py:507). This guard is the backstop
            # behind that fix, not the fix itself.
            with self._write_lock:
                self._overwrote_prior += 1
            self._note_rejected_write(
                f"add() for existing id {memory.id!r} carries different content; "
                "appending it would plant a conflicting duplicate identity and "
                "degrade the whole store on next load; routed to update() "
                "(full rewrite) instead"
            )
            # Outside the writer lock: ReadWriteLock is NOT reentrant and
            # update() takes it again.
            self.update(memory)
            return memory.id

        # Buffer the disk write — flushed by background thread
        crypto = _get_crypto()
        line = memory.to_json()
        if crypto:
            line = crypto.encrypt_line(line)

        with self._write_lock:
            self._write_buffer.append(line + "\n")
            # Signal flusher to wake immediately when buffer hits capacity
            if len(self._write_buffer) >= self._flush_max:
                self._flush_event.set()

        return memory.id

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        self._wait_loaded()
        with self._lock.read_lock():
            return self._memories.get(memory_id)

    def update(self, memory: Memory):
        """Update an existing memory.

        Schedules a full JSONL rewrite on next flush cycle since
        append-only format can't express inline mutations.
        """
        self._require_writable_load()
        with self._lock.write_lock():
            if memory.id in self._memories:
                memory.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._memories[memory.id] = memory
                self._index_memory(memory)
                self._dirty = True
                self._needs_rewrite = True
        # Wake flusher to persist the change
        self._flush_event.set()

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Schedules a full JSONL rewrite on next flush cycle since
        append-only format can't express deletions.
        """
        self._require_writable_load()
        with self._lock.write_lock():
            if memory_id in self._memories:
                del self._memories[memory_id]
                self._dirty = True
                self._needs_rewrite = True
                # Wake flusher to persist the change
                self._flush_event.set()
                return True
            return False

    def all(self) -> List[Memory]:
        """Get all memories."""
        self._wait_loaded()
        with self._lock.read_lock():
            return list(self._memories.values())

    def count(self) -> int:
        """Get total memory count."""
        self._wait_loaded()
        with self._lock.read_lock():
            return len(self._memories)

    def clear(self):
        """Clear all memories."""
        self._require_writable_load()
        with self._lock.write_lock():
            self._memories.clear()
            self._index = {
                "by_type": {},
                "by_tag": {},
                "by_keyword": {},
                "links": {},
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "updated": "",
                "version": 1
            }
            self._dirty = True
            self.save()

    def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
        """Search memories based on query parameters.

        Uses the in-memory index to narrow candidates before scoring,
        avoiding a full scan when type/tag/keyword filters are provided.
        Falls back to full scan only for pure text queries.
        """
        self._wait_loaded()
        with self._lock.read_lock():
            # --- Candidate narrowing via index ---
            candidates = None  # None = "all", set() = "none matched yet"

            if query.memory_types:
                type_ids: set = set()
                for mt in query.memory_types:
                    type_ids.update(self._index["by_type"].get(mt.value, []))
                candidates = type_ids

            if query.tags:
                tag_ids: set = set()
                for tag in query.tags:
                    tag_ids.update(self._index["by_tag"].get(tag, []))
                candidates = tag_ids if candidates is None else candidates & tag_ids

            if query.keywords:
                kw_ids: set = set()
                for kw in query.keywords:
                    kw_ids.update(self._index["by_keyword"].get(kw, []))
                candidates = kw_ids if candidates is None else candidates & kw_ids

            # Resolve candidate IDs to Memory objects
            if candidates is not None:
                pool = [self._memories[mid] for mid in candidates if mid in self._memories]
            else:
                pool = list(self._memories.values())

            # --- Score candidates ---
            results = []

            for memory in pool:
                if memory.is_consolidated and not query.include_consolidated:
                    continue

                # Post-filter: tier, source, time range
                if query.tier and memory.tier != query.tier:
                    continue
                if query.source and memory.source != query.source:
                    continue
                if query.since and memory.created_at < query.since:
                    continue
                if query.until and memory.created_at > query.until:
                    continue

                score = 0.0
                match_reasons = []

                # Tag scoring (index already filtered, but score the overlap)
                if query.tags:
                    matching_tags = set(query.tags) & set(memory.tags)
                    if matching_tags:
                        score += len(matching_tags) * 0.2
                        match_reasons.append(f"tags: {', '.join(matching_tags)}")

                # Keyword scoring
                if query.keywords:
                    matching_keywords = set(query.keywords) & set(memory.keywords)
                    if matching_keywords:
                        score += len(matching_keywords) * 0.2
                        match_reasons.append(f"keywords: {', '.join(matching_keywords)}")

                # Text search (still linear over candidates, but candidate set is smaller)
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
                    word_matches = sum(1 for w in words if w in content_lower or w in summary_lower)
                    if word_matches > 0:
                        score += word_matches * 0.1
                        match_reasons.append(f"{word_matches} word matches")

                # No criteria = return all with base score
                if not query.text and not query.tags and not query.keywords:
                    score = 0.5

                if score > 0:
                    results.append(MemorySearchResult(
                        memory=memory,
                        score=min(1.0, score),
                        match_reasons=match_reasons
                    ))

            # He2025 + recency: score desc, then fresher-first (created_at is an ISO-8601
            # string so lexical desc == chronological desc), then id asc for determinism.
            # Layered stable sorts (least-significant first) — a string field can't be negated
            # in one tuple key. Identical across ALL backends so recall ranking stays
            # parity-consistent (test_moneta_store ranking parity).
            results.sort(key=lambda r: r.memory.id)
            results.sort(key=lambda r: r.memory.created_at, reverse=True)
            results.sort(key=lambda r: r.score, reverse=True)

            if query.limit > 0:
                results = results[:query.limit]

            return results

    def get_by_type(self, memory_type: MemoryType) -> List[Memory]:
        """Get all memories of a specific type."""
        self._wait_loaded()
        with self._lock.read_lock():
            ids = self._index["by_type"].get(memory_type.value, [])
            return [self._memories[id] for id in ids if id in self._memories]

    def get_by_tag(self, tag: str) -> List[Memory]:
        """Get all memories with a specific tag."""
        self._wait_loaded()
        with self._lock.read_lock():
            ids = self._index["by_tag"].get(tag.lower(), [])
            return [self._memories[id] for id in ids if id in self._memories]

    def get_linked(self, memory_id: str) -> List[Memory]:
        """Get all memories linked to a specific memory."""
        self._wait_loaded()
        with self._lock.read_lock():
            links = self._index["links"].get(memory_id, [])
            return [
                self._memories[link["target"]]
                for link in links
                if link["target"] in self._memories
            ]

    def get_recent(self, limit: int = 10) -> List[Memory]:
        """Get most recent memories."""
        self._wait_loaded()
        with self._lock.read_lock():
            sorted_memories = sorted(
                self._memories.values(),
                key=lambda m: m.created_at,
                reverse=True
            )
            return sorted_memories[:limit]


# =============================================================================
# BACKEND FALLBACK TELEMETRY (C-0 loudness)
# =============================================================================
# When $SYNAPSE_MEMORY_BACKEND selects moneta/shadow but this process ends up
# serving jsonl, the swap must be observable after the fact — twice in
# production (2026-07-31, 2026-08-01) the store landed on an unwritable
# address, raised PermissionError, and the only trace was one log line while
# the operator believed moneta was active. ``_make_store()`` records the
# event here; ``synapse.server.doctor._check_moneta_substrate()`` reads it
# via ``backend_fallback()``. Process-local by design: the doctor diagnoses
# THIS seat. The flag reflects the most recent ``_make_store()`` call.

_BACKEND_FALLBACK: Optional[Dict[str, Any]] = None


def _record_backend_fallback(requested: str, storage_dir: Any, reason: str) -> None:
    global _BACKEND_FALLBACK
    _BACKEND_FALLBACK = {
        "requested": requested,
        "served": "jsonl",
        "storage_dir": str(storage_dir),
        "reason": reason,
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def backend_fallback() -> Optional[Dict[str, Any]]:
    """Details of the backend fallback recorded by the most recent
    ``_make_store()`` in this process, or None when the selected backend is
    the one actually serving."""
    return None if _BACKEND_FALLBACK is None else dict(_BACKEND_FALLBACK)


# --------------------------------------------------------------------------- #
# Honest backend health (BP2-STORE / M-5, T2+T3).
#
# ``backend_fallback()`` above records the requested-vs-served GAP; this is its
# operator-facing twin: a single non-mutating verdict on the memory backend that
# speaks the ratified ``loop/ports.py`` status vocabulary
# (SUCCESS | UNAVAILABLE | BLOCKED) and carries the five W1 operator-acceptance
# fields (requested backend, active backend, embedder id, embedding dim, row
# count). The M-5 rule: SYNAPSE_MEMORY_BACKEND=moneta served by a jsonl store is
# NEVER reported SUCCESS -- a healthy jsonl must not masquerade as Moneta.
#
# OBSERVER, not an authority: it never constructs a store (returns None when
# none is live) and adds no key to ``memory_handle_census()``. The store handle
# authorities remain exactly two (this module's ``get_synapse_memory`` and
# ``ledger.py``'s ``ledger_moneta_store``).
# --------------------------------------------------------------------------- #

#: The three status strings this accessor may emit. Held as literals so the
#: memory layer stays import-decoupled from ``synapse.loop``; conformance to the
#: ratified ``ports.STATUS`` frozenset is pinned by
#: tests/test_store_backend_health.py::test_backend_health_status_in_ratified_vocabulary.
_BACKEND_STATUS = frozenset({"SUCCESS", "UNAVAILABLE", "BLOCKED"})


def _classify_backend(store: Any) -> str:
    """Name the backend actually serving, read from the live object's class."""
    if store is None:
        return "none"
    if isinstance(store, MemoryStore):
        return "jsonl"
    lowered = type(store).__name__.lower()
    if "moneta" in lowered:
        return "moneta"
    if "shadow" in lowered:
        return "shadow"
    if "sqlite" in lowered:
        return "sqlite"
    return type(store).__name__


def backend_health(store: Any = None) -> Optional[Dict[str, Any]]:
    """Honest, non-mutating health of the memory backend (BP2-STORE / M-5, T3).

    Pass a store, or omit it to read the process-global ``SynapseMemory``'s
    store. Returns ``None`` when no store is live (it NEVER constructs one --
    observer, not an authority). The dict carries the five operator-acceptance
    fields plus a ``status`` in SUCCESS | UNAVAILABLE | BLOCKED and a human
    ``reason``:

    - ``requested_backend`` -- ``$SYNAPSE_MEMORY_BACKEND`` (default ``jsonl``).
    - ``active_backend``     -- what the live store class actually is.
    - ``embedder_id`` / ``embedding_dim`` -- the active embedder identity + vector
      dimension (``None`` on jsonl, which has no embedder -- honest, not faked).
    - ``row_count``          -- ``store.count()`` (``None`` if it raises).
    - ``status``             -- SUCCESS when the served backend satisfies the
      request; UNAVAILABLE when a requested substrate is absent (e.g. Moneta not
      importable -> jsonl fallback); BLOCKED when it is present but a fault
      prevents it (init failed / durability). A ``moneta``/``shadow`` request
      served by a jsonl store is NEVER SUCCESS -- the M-5 anti-masquerade rule.
    """
    if store is None:
        mem = _global_synapse
        if mem is None:
            return None
        store = getattr(mem, "store", None)
        if store is None:
            return None

    requested = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl").strip().lower() or "jsonl"
    active = _classify_backend(store)
    served_jsonl = isinstance(store, MemoryStore)

    embedder_id = getattr(store, "embedder_id", None)
    _emb = getattr(store, "_embedder", None) or getattr(store, "embedder", None)
    embedding_dim = getattr(_emb, "dim", None) if _emb is not None else None

    try:
        row_count: Optional[int] = int(store.count())
    except Exception:  # noqa: BLE001 -- a health read must never raise
        row_count = None

    if requested in ("moneta", "shadow") and served_jsonl:
        fb = backend_fallback()
        reason = fb.get("reason") if fb and fb.get("requested") == requested else None
        if not reason:
            reason = (
                f"{requested!r} selected but a jsonl {type(store).__name__} is the "
                f"live store -- the selected substrate is not serving"
            )
        status = "BLOCKED" if "init failed" in reason.lower() else "UNAVAILABLE"
    else:
        status, reason = "SUCCESS", None

    return {
        "requested_backend": requested,
        "active_backend": active,
        "embedder_id": embedder_id,
        "embedding_dim": embedding_dim,
        "row_count": row_count,
        "status": status,
        "reason": reason,
    }


def hip_is_unsaved(hip_path: Optional[str], hou_mod: Any = None) -> bool:
    """True when *hip_path* is Houdini's placeholder for a never-saved scene.

    ``hou.hipFile.path()`` returns a FULL path ending in ``untitled.hip`` for
    an unsaved scene — wherever the process was launched from, e.g.
    ``C:/Program Files/.../bin/untitled.hip`` (VERIFIED in production logs
    2026-07-31 14:42:14 and 2026-08-01 10:25:01) — so equality against the
    bare string ``"untitled.hip"`` never matches. Detection is by BASENAME.

    A scene can legitimately be SAVED as ``untitled.hip`` inside a real
    project directory. When the running hou exposes
    ``hou.hipFile.isNewFile()`` (the canonical never-saved probe) it decides
    that case. The call is getattr-guarded rather than emitted directly
    because the committed h22 symbol table is depth-limited (hou depth 2) and
    cannot verdict ``hou.hipFile`` members either way — even
    ``hou.hipFile.path``, in production use for years, is absent from it. If
    ``isNewFile`` is unavailable, basename wins: a scene genuinely saved as
    ``untitled.hip`` is then treated as unsaved and its store lives under
    $HOUDINI_TEMP_DIR. Documented limitation, chosen deliberately — the
    wrong-but-writable temp address beats risking the launch-directory
    address that put the store inside Program Files.
    """
    if not hip_path:
        return True
    if os.path.basename(str(hip_path)) != "untitled.hip":
        return False
    if hou_mod is not None:
        hip_file = getattr(hou_mod, "hipFile", None)
        is_new = getattr(hip_file, "isNewFile", None) if hip_file is not None else None
        if callable(is_new):
            try:
                return bool(is_new())
            except Exception:
                pass
    return True


#: Migration honesty (C-0): the unsaved-scene address changed on 2026-08-01.
#: Announce once per process where the store lives now; never relocate data
#: silently.
_UNSAVED_RELOCATION_ANNOUNCED = False


def _announce_unsaved_relocation(temp_root: Any) -> None:
    global _UNSAVED_RELOCATION_ANNOUNCED
    if _UNSAVED_RELOCATION_ANNOUNCED:
        return
    _UNSAVED_RELOCATION_ANNOUNCED = True
    logger.info(
        "Unsaved scene: the memory store lives under $HOUDINI_TEMP_DIR (%s). "
        "Stores previously written next to the process working directory "
        "(e.g. <cwd>/untitled.hip/.synapse) are NOT carried over.",
        temp_root,
    )


def _read_on_main(fn, label="synapse_store_resolve"):
    """Run *fn* -- which reads ``hou.*`` -- on Houdini's main thread when the
    caller is OFF it.

    ``hou.*`` is not thread-safe: a bare call from a worker thread (e.g. a cold
    store construct reached by an off-main ``run_doctor`` dispatch on the
    hwebserver transport) can fault the process natively -- a crash no
    ``try/except`` can catch (W1-MTFIX finding F1). This marshals the read
    through ``server.main_thread.run_on_main``, which is a DIRECT passthrough
    when the caller is ALREADY on the main thread (the headless/hython and
    GUI-main cases), so store SEMANTICS are unchanged on every path that reaches
    ``hou`` today -- only the thread the read runs on changes, and only when off
    main.

    If marshalling is unavailable, a Houdini worker fails closed. Python
    exceptions cannot recover a native crash caused by an off-main hou call.
    """
    try:
        from ..server.main_thread import run_on_main
    except Exception as exc:
        if HOU_AVAILABLE and threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Houdini memory access requires main-thread dispatch") from exc
        return fn()
    return run_on_main(fn, label=label)


# =============================================================================
# STORE-PATH SAFETY (W1): never join an UNEXPANDED env token as a path segment
# =============================================================================
#
# The literal ``C:/Users/User/Synapse/$HOUDINI_TEMP_DIR/untitled/.synapse`` store
# found on disk was born here: ``_resolve_project_path`` joined the raw
# ``$HOUDINI_TEMP_DIR`` token -- returned UNCHANGED by ``expandString`` when the
# variable is undefined -- as a RELATIVE segment, so it landed under the process
# CWD. ``scene_memory.unsaved_memory_base`` already refuses that; these helpers
# mirror the discipline on every store path store.py builds. A path COMPONENT
# that still matches ``$VAR`` / ``${VAR}`` / ``%VAR%`` after expansion must NEVER
# be joined to disk.

#: A path COMPONENT that is still an unexpanded environment reference.
_LITERAL_ENV_SEG = re.compile(r"^(?:\$\w+|\$\{[^}]+\}|%[^%]+%)$")


def _has_literal_env_segment(path: Any) -> bool:
    """True when any component of *path* is still a literal env-var token."""
    try:
        parts = Path(str(path)).parts
    except Exception:  # noqa: BLE001 -- a path we cannot even split is not ours
        return False
    return any(_LITERAL_ENV_SEG.match(seg) for seg in parts)


def _expand_and_validate(raw: Any) -> Optional[Path]:
    """Expand ``$VAR`` / ``${VAR}`` / ``%VAR%`` / ``~`` in *raw*; reject a residual token.

    Returns the expanded ``Path``, or ``None`` when a component is STILL an
    unexpanded env token after expansion -- the caller then falls back to a
    resolved, writable base rather than create a literal ``$VAR`` directory.
    A plain, token-free path is returned unchanged (expansion is a no-op).
    """
    if raw is None:
        return None
    expanded = os.path.expanduser(os.path.expandvars(str(raw)))
    if _has_literal_env_segment(expanded):
        return None
    return Path(expanded)


def _safe_unsaved_base() -> Path:
    """Canonical unsaved-scene base, guaranteed free of literal env tokens.

    Mirrors ``scene_memory.unsaved_memory_base`` (C-0: both subsystems must
    address the SAME place -- in production they share the one ``hou`` module,
    so they land identically), but resolves through store's OWN ``hou`` and
    RE-VALIDATES. Order: expand ``$HOUDINI_TEMP_DIR`` via ``hou`` -> the
    ``HOUDINI_TEMP_DIR`` environment variable -> the platform temp dir. A result
    that still carries a literal ``$VAR`` / ``%VAR%`` segment (the undefined-var
    case, where ``expandString`` hands the token back) is refused before it can
    be joined to disk -- fall back to the platform temp dir loudly.
    """
    _TOKEN = "$HOUDINI_TEMP_DIR"
    base: Optional[str] = None
    if HOU_AVAILABLE:
        try:
            expanded = hou.text.expandString(_TOKEN)
            if expanded and expanded.strip() != _TOKEN:
                base = os.path.join(expanded, "untitled")
        except Exception:  # noqa: BLE001 -- a broken hou is not a crash here
            pass
    if base is None:
        env = os.environ.get("HOUDINI_TEMP_DIR")
        if env:
            base = os.path.join(env, "untitled")
    if not base or _has_literal_env_segment(base):
        fallback = os.path.join(tempfile.gettempdir(), "synapse", "untitled")
        if base and _has_literal_env_segment(base):
            logger.warning(
                "Unsaved-scene base held a literal env token (%r); falling back "
                "to %s", base, fallback,
            )
        base = fallback
    return Path(os.path.normpath(base))


# =============================================================================
# SYNAPSE MEMORY - HIGH-LEVEL API
# =============================================================================

def _on_memory_main(method):
    """Keep host backend work on main, including automatic action logging."""
    @wraps(method)
    def call(self, *args, **kwargs):
        if not HOU_AVAILABLE:
            return method(self, *args, **kwargs)
        expected = getattr(self, "_memory_binding", None)
        def execute():
            if expected is not None and (
                _global_synapse is not self
                or getattr(self, "_memory_binding", None) != expected
            ):
                raise RuntimeError("Memory scene changed before the request ran; original owner was not modified")
            return method(self, *args, **kwargs)
        return _read_on_main(execute, label="memory:" + method.__name__)
    return call


class SynapseMemory:
    """
    High-level API for Synapse memory system.

    Automatically detects current Houdini project and manages memory storage.
    Provides convenient methods for common operations.

    Migration: Automatically migrates .nexus/ or .engram/ to .synapse/ if needed.
    """

    def __init__(self, project_path: Optional[str] = None):
        """
        Initialize Synapse for a project.

        Args:
            project_path: Optional path to .hip file or project directory.
                         If None, uses current Houdini project.
        """
        self.project_path = self._resolve_project_path(project_path)
        self.storage_dir = self._get_storage_dir()
        self.store = self._make_store(self.storage_dir)

        # Callbacks
        self._on_memory_added: List[Callable[[Memory], None]] = []
        self._on_memory_updated: List[Callable[[Memory], None]] = []

        logger.info("Initialized for project: %s", self.project_path)
        logger.info("Storage: %s", self.storage_dir)

    def _make_store(self, storage_dir):
        """Select the memory backend via $SYNAPSE_MEMORY_BACKEND.

        Default ``jsonl`` is the unchanged behavior. ``moneta`` routes through
        the Moneta engine (Mile 4); it falls back to JSONL with a warning if
        Moneta can't be imported, so setting the flag can never break startup.
        Any other value (including ``sqlite``, which is NOT wired to this
        selector) falls back to JSONL with a warning.
        """
        global _BACKEND_FALLBACK
        _BACKEND_FALLBACK = None  # reflects the most recent construction
        backend = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl").strip().lower()
        if backend == "moneta":
            # H6 / Law 3: ask whether Moneta is importable rather than inferring
            # it from an exception type. The previous `except ImportError` arm
            # was UNREACHABLE (VERIFIED-RUNTIME 2026-07-26): moneta_store
            # imports nothing from moneta at module scope, so
            # `from .moneta_store import ...` always succeeds, and
            # from_storage_dir raises RuntimeError -- not ImportError -- when
            # the package is absent. Every not-installed seat therefore fell
            # through to the handler below and was told the backend "is
            # installed but failed to initialize ... not a missing dependency",
            # the exact inverse of the truth, at ERROR. A status must describe
            # what happened, and the distinction this branch exists to draw was
            # the one thing it got backwards.
            try:
                from . import moneta_runtime as _mr
                available, why = _mr.moneta_available(), _mr.import_error()
            except Exception as exc:  # noqa: BLE001 -- startup must not break
                available, why = False, f"{type(exc).__name__}: {exc}"
            if not available:
                # Intended path: moneta not installed -> quiet jsonl fallback.
                logger.warning(
                    "SYNAPSE_MEMORY_BACKEND=moneta but Moneta is not importable "
                    "(%s); falling back to jsonl. Install the moneta package or "
                    "set $MONETA_SRC.", why,
                )
                _record_backend_fallback(
                    "moneta", storage_dir, f"Moneta not importable: {why}",
                )
                return MemoryStore(storage_dir)
            try:
                from .moneta_store import MonetaBackedStore
                store = MonetaBackedStore.from_storage_dir(storage_dir)
                logger.info("Memory backend: moneta (%s)", store.embedder_id)
                return store
            except Exception as exc:
                # NOT the intended path: moneta IS installed but constructing
                # the store failed -- an API drift (unpinned, undeclared dep) or
                # a real defect. A blanket warning here read identically to
                # "not installed" and silently served jsonl while the operator
                # believed moneta was active. Name the resolved copy and raise
                # the level so an upgrade that breaks the adapter is loud.
                # H6: the provenance lookup is itself fenced. This log line is
                # the LAST thing standing between a broken adapter and a jsonl
                # fallback, and it runs inside an except handler -- a raise
                # here escapes _make_store and stops Houdini's panel loading,
                # which is precisely the failure the docstring contract above
                # promises can never happen. moneta_provenance() is written to
                # never raise; this fence means the contract does not depend on
                # that promise holding.
                try:
                    from . import moneta_runtime as _mr
                    provenance = _mr.moneta_provenance()
                except Exception as prov_exc:  # noqa: BLE001
                    provenance = (
                        f"<unavailable: {type(prov_exc).__name__}: {prov_exc}>"
                    )
                logger.error(
                    "SYNAPSE_MEMORY_BACKEND=moneta is installed but failed to "
                    "initialize (%s: %s); provenance=%s; attempted storage: %s. "
                    "The memory backend FELL BACK to jsonl — the selected "
                    "backend is NOT serving. This is an API-drift or defect, "
                    "not a missing dependency.",
                    type(exc).__name__, exc, provenance, storage_dir,
                )
                _record_backend_fallback(
                    "moneta", storage_dir,
                    f"init failed: {type(exc).__name__}: {exc}",
                )
        elif backend == "shadow":
            try:
                from .moneta_store import MonetaBackedStore
                from .shadow_store import ShadowMemoryStore
                primary = MemoryStore(storage_dir)
                shadow = MonetaBackedStore.from_storage_dir(storage_dir)
                logger.info("Memory backend: shadow (jsonl primary + moneta shadow)")
                return ShadowMemoryStore(primary, shadow)
            except Exception as exc:
                logger.warning(
                    "SYNAPSE_MEMORY_BACKEND=shadow unavailable (%s); attempted "
                    "storage: %s. The memory backend fell back to jsonl.",
                    exc, storage_dir,
                )
                _record_backend_fallback(
                    "shadow", storage_dir, f"shadow unavailable: {exc}",
                )
        if backend not in ("jsonl", "moneta", "shadow", ""):
            logger.warning(
                "SYNAPSE_MEMORY_BACKEND=%s is not a live backend "
                "(valid: jsonl | moneta | shadow); using jsonl.", backend,
            )
        return MemoryStore(storage_dir)

    def _resolve_project_path(self, path: Optional[str]) -> Path:
        """Resolve the project path."""
        if path:
            resolved = _expand_and_validate(path)
            if resolved is not None:
                return resolved
            # An explicit path that STILL holds a literal env token after
            # expansion must not be mkdir'd verbatim -- that is the literal
            # "$HOUDINI_TEMP_DIR" directory bug in path form. Fall back to the
            # writable unsaved-scene base instead of creating a "$VAR" dir.
            logger.warning(
                "project_path %r still contained an unexpanded env token after "
                "expansion; using the unsaved-scene base instead", path,
            )
            return _safe_unsaved_base()

        if HOU_AVAILABLE:
            from ..host.memory_lifecycle import current_binding
            binding = _read_on_main(lambda: current_binding(hou), label="synapse_store_resolve_binding")
            self._memory_binding = binding
            if binding.unsaved:
                _announce_unsaved_relocation(binding.project_dir)
            elif binding.project_source == "hip_directory":
                # Keep the historical explicit HIP-path representation when
                # there is no separate containing project; storage is its parent.
                return Path(binding.hip_path)
            return binding.project_dir

        # Fallback
        return Path.cwd() / "untitled.hip"

    def _get_storage_dir(self) -> Path:
        """
        Get the storage directory for this project.

        3-tier migration logic:
        1. If .synapse/ exists -> use it
        2. If .nexus/ exists -> copy to .synapse/, leave marker
        3. If .engram/ exists -> copy to .synapse/, leave marker
        4. Otherwise -> create .synapse/
        """
        if (self.project_path.is_file()
                or self.project_path.suffix.lower() in {".hip", ".hiplc", ".hipnc"}):
            base_dir = self.project_path.parent
        else:
            base_dir = self.project_path

        synapse_dir = base_dir / ".synapse"
        nexus_dir = base_dir / ".nexus"
        engram_dir = base_dir / ".engram"

        # Priority 1: Use existing .synapse/
        if synapse_dir.exists():
            return synapse_dir

        # Priority 2: Migrate from .nexus/
        if nexus_dir.exists():
            try:
                logger.info("Migrating from .nexus/ to .synapse/")
                shutil.copytree(nexus_dir, synapse_dir)
                migration_marker = nexus_dir / ".migrated_to_synapse"
                migration_marker.write_text(
                    f"Migrated to .synapse/ on {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"This directory is kept for backwards compatibility.\n"
                    f"You can safely delete it."
                )
                logger.info("Migration complete: %s -> %s", nexus_dir, synapse_dir)
                return synapse_dir
            except Exception as e:
                logger.warning("Migration failed: %s. Using .nexus/ directly.", e)
                return nexus_dir

        # Priority 3: Migrate from .engram/
        if engram_dir.exists():
            try:
                logger.info("Migrating from .engram/ to .synapse/")
                shutil.copytree(engram_dir, synapse_dir)
                migration_marker = engram_dir / ".migrated_to_synapse"
                migration_marker.write_text(
                    f"Migrated to .synapse/ on {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"This directory is kept for backwards compatibility.\n"
                    f"You can safely delete it."
                )
                logger.info("Migration complete: %s -> %s", engram_dir, synapse_dir)
                return synapse_dir
            except Exception as e:
                logger.warning("Migration failed: %s. Using .engram/ directly.", e)
                return engram_dir

        # Priority 4: Create new .synapse/
        return synapse_dir

    @_on_memory_main
    def add(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.NOTE,
        tags: List[str] = None,
        keywords: List[str] = None,
        source: str = "user",
        node_paths: List[str] = None,
        links: List[Dict] = None,
        summary: str = "",
        reasoning: str = "",
        alternatives: List[str] = None,
        status: str = "",
        ref_uri: str = "",
        tier: MemoryTier = MemoryTier.SHOT,
        require_durable: bool = False,
    ) -> Memory:
        """
        Add a new memory.

        Args:
            content: The memory content
            memory_type: Type of memory
            tags: Categorical tags
            keywords: Key concepts
            source: Who created this ("user", "ai", "auto")
            node_paths: Related Houdini node paths
            links: Links to other memories [{"target_id": "...", "type": "...", "reason": "..."}]
            summary: Explicit one-line summary. If empty (default), it is
                auto-derived from the first content line — which produces
                duplicate headings for templated content like session summaries
                (H-4). Pass an explicit summary for such writes.
            reasoning, alternatives, status, ref_uri: Typed per-kind fields
                (W3-KIND). Optional and additive -- a decision sets
                reasoning+alternatives, a task sets status, a reference sets
                ref_uri; every other kind leaves them at their defaults. See
                kind_schema.KIND_FIELDS.

        Returns:
            The created Memory object
        """
        tier = tier if isinstance(tier, MemoryTier) else MemoryTier(tier)
        # Get Houdini context if available
        hip_file = ""
        hip_version = 0
        frame = None

        if HOU_AVAILABLE:
            hip_file, frame = _read_on_main(
                lambda: (hou.hipFile.name(), int(hou.frame())),
                label="memory:add_context",
            )
            # Try to extract version from filename
            try:
                import re
                version_match = re.search(r'_v(\d+)', hip_file)
                if version_match:
                    hip_version = int(version_match.group(1))
            except Exception:
                pass

        # Create memory
        memory = Memory(
            content=content,
            memory_type=memory_type,
            tier=tier,
            tags=tags or [],
            keywords=keywords or [],
            source=source,
            hip_file=hip_file,
            hip_version=hip_version,
            frame=frame,
            node_paths=node_paths or [],
            summary=summary,
            reasoning=reasoning,
            alternatives=alternatives or [],
            status=status,
            ref_uri=ref_uri,
        )

        # Add links
        if links:
            for link_data in links:
                memory.add_link(
                    target_id=link_data["target_id"],
                    link_type=LinkType(link_data.get("type", "related")),
                    reason=link_data.get("reason", "")
                )

        # Store
        if require_durable:
            # The legacy Memory ID hashes prose + whole-second timestamp +
            # kind. Identical prose recorded at two scopes in one second must
            # not overwrite the first decision. Keep old/deserialized IDs
            # intact; checked new records include all canonical provenance.
            identity = memory.to_dict()
            identity.pop("id", None)
            memory.id = "mem_" + hashlib.sha256(json.dumps(
                identity, sort_keys=True, allow_nan=False,
            ).encode("utf-8")).hexdigest()[:12]
        durable_add = getattr(self.store, "add_durable_if_absent", None)
        if require_durable and callable(durable_add):
            durable_add(memory)
        else:
            self.store.add(memory)
            if require_durable:
                self.store.save()

        # Notify callbacks
        for callback in self._on_memory_added:
            try:
                callback(memory)
            except Exception as e:
                logger.error("Callback error: %s", e)

        return memory

    def decision(
        self,
        decision: str,
        reasoning: str,
        alternatives: List[str] = None,
        tags: List[str] = None,
        tier: MemoryTier = MemoryTier.SHOT,
    ) -> Memory:
        """
        Record a decision with reasoning.

        Args:
            decision: What was decided
            reasoning: Why this was chosen
            alternatives: Other options considered
            tags: Categorical tags
        """
        content_lines = [
            f"**Decision:** {decision}",
            f"**Reasoning:** {reasoning}"
        ]
        if alternatives:
            content_lines.append("**Alternatives Considered:**")
            for alt in alternatives:
                content_lines.append(f"- {alt}")

        return self.add(
            content="\n".join(content_lines),
            memory_type=MemoryType.DECISION,
            tags=tags or ["decision"],
            keywords=self._extract_keywords(decision + " " + reasoning),
            # Provenance: a decision recorded through this API is the AI/agent's
            # reasoning, not something the user typed. Stamp the real author so a
            # memory's source reflects who authored it (was mislabeled "user").
            source="ai",
            # W3-KIND: ALSO store reasoning+alternatives as typed per-kind fields
            # (in addition to the content baking above, which is kept for
            # back-compat with markdown sync + keyword recall). This is what
            # makes a decision a typed prim, not just prose.
            reasoning=reasoning,
            alternatives=alternatives or [],
            tier=tier,
            require_durable=True,
        )

    def action(
        self,
        action: str,
        node_paths: List[str] = None,
        tags: List[str] = None
    ) -> Memory:
        """
        Record an action taken.

        Args:
            action: What was done
            node_paths: Affected node paths
            tags: Categorical tags
        """
        return self.add(
            content=action,
            memory_type=MemoryType.ACTION,
            tags=tags or ["action"],
            node_paths=node_paths,
            source="auto"
        )

    def note(self, content: str, tags: List[str] = None) -> Memory:
        """Add a simple note."""
        return self.add(content, MemoryType.NOTE, tags=tags)

    @_on_memory_main
    def search(
        self,
        query: str,
        limit: int = 20,
        memory_types: Optional[List[MemoryType]] = None,
        tier: Optional[MemoryTier] = None,
    ) -> List[MemorySearchResult]:
        """Search memories by text, optionally filtered to specific kind(s).

        W3-KIND: when ``memory_types`` is given, the filter routes on the store's
        typed ``by_type`` index (store.search narrows candidates by type BEFORE
        scoring -- store.py:606), so a kind-filtered query touches only that
        kind's typed prims, not the whole store. ``memory_types=None`` (default)
        is the unchanged full-text behavior.
        """
        request = MemoryQuery(
            text=query,
            memory_types=list(memory_types) if memory_types else [],
            limit=limit,
            tier=tier,
        )
        if tier == MemoryTier.SHOT:
            # Narrow BEFORE ranking/limiting. Filtering a vector top-N after
            # the fact can discard a scene's only hit behind sibling scenes.
            from .moneta_store import score_memories
            sources = self._scene_sources()
            pool = (m for kind in (memory_types or list(MemoryType))
                    for m in self.store.get_by_type(kind)
                    if self._belongs_to_scene(m, sources))
            return score_memories(pool, request)
        return self.store.search(request)

    def _scene_sources(self):
        from ..host.memory_lifecycle import scene_hip_paths
        return scene_hip_paths(self)

    @staticmethod
    def _belongs_to_scene(memory, sources):
        # Standalone stores have no host scene binding. Bound scenes include
        # their durable Save As lineage, while retaining original provenance.
        if not sources:
            return True
        return bool(memory.hip_file) and os.path.normcase(
            str(Path(memory.hip_file).resolve())
        ) in sources

    @_on_memory_main
    def recall(
        self,
        query: str = "",
        kinds: Optional[List[MemoryType]] = None,
        limit: int = 5,
        tier: Optional[MemoryTier] = None,
    ) -> List[Memory]:
        """Recall memories of specific kind(s) that match a query, routed on type.

        W3-KIND: candidates come from ``store.get_by_type(kind)`` -- the by_type
        index, which resolves only that kind's typed prims (store.py:708), never
        a full-store scan. Defaults to DECISION (the historical recall surface)
        when no kind is given. Determinism mirrors the recall handler: id asc,
        then fresher-first. Query words match whole words in content/summary,
        independent of their order; ordinary question words are ignored.

        ``kinds`` accepts MemoryType members or their ``.value`` strings; an
        unknown kind raises ValueError (loud) rather than silently widening the
        scan -- callers that want a soft negative control should pre-resolve via
        kind_schema.resolve_kinds.
        """
        if kinds:
            types = [k if isinstance(k, MemoryType) else MemoryType(str(k)) for k in kinds]
        else:
            types = [MemoryType.DECISION]

        sources = self._scene_sources() if tier == MemoryTier.SHOT else None
        pool: List[Memory] = []
        seen = set()
        for t in types:
            for m in self.store.get_by_type(t):
                if (m.id not in seen and (tier is None or m.tier == tier)
                        and (sources is None or self._belongs_to_scene(m, sources))):
                    seen.add(m.id)
                    pool.append(m)

        # Deterministic order (matches handle_memory_recall): least-significant
        # sort first -- id asc, then fresher-first (ISO ts, lexical desc ==
        # chronological desc).
        pool.sort(key=lambda m: m.id)
        pool.sort(key=lambda m: m.created_at or "", reverse=True)

        q = (query or "").strip().casefold()
        # A question is not an exact quotation. The demo's "look decision"
        # failed against "**Decision:** ... display look" despite both words
        # being present. Require EVERY meaningful word, not just one shared
        # word, and never match "oral" inside "coral". This remains a bounded
        # typed-record lookup; it neither needs vectors nor invents record IDs.
        question_words = {
            "a", "an", "the", "what", "which", "was", "were", "is", "are",
            "did", "do", "does", "we", "you", "i", "our", "my", "for", "of",
            "on", "in", "to", "and", "about", "have", "has", "had", "please",
            "remember", "recall",
        }
        terms = set(re.findall(r"\w+", q)) - question_words
        matches = [
            m for m in pool
            if not q or (terms and terms <= set(re.findall(
                r"\w+", (m.content + " " + m.summary).casefold(),
            )))
        ]
        return matches[:limit] if limit and limit > 0 else matches

    @_on_memory_main
    def get_decisions(self) -> List[Memory]:
        """Get all decision memories."""
        return self.store.get_by_type(MemoryType.DECISION)

    @_on_memory_main
    def get_recent(self, limit: int = 10) -> List[Memory]:
        """Get most recent memories."""
        return self.store.get_recent(limit)

    def get_context_summary(self) -> str:
        """
        Generate a context summary for AI consumption.

        Returns a markdown-formatted summary of key project memories.
        """
        lines = ["# Project Memory Context", ""]

        # Recent decisions
        decisions = self.get_decisions()
        if decisions:
            lines.append("## Key Decisions")
            for d in decisions[-5:]:  # Last 5 decisions
                lines.append(f"- {d.summary}")
            lines.append("")

        # Recent activity
        recent = self.get_recent(5)
        if recent:
            lines.append("## Recent Activity")
            for m in recent:
                type_name = m.memory_type.value
                lines.append(f"- [{type_name}] {m.summary}")
            lines.append("")

        # Common tags
        all_tags = set()
        for m in self.store.all():
            all_tags.update(m.tags)
        if all_tags:
            lines.append(f"## Tags: {', '.join(sorted(all_tags)[:10])}")
            lines.append("")

        return "\n".join(lines)

    def save(self):
        """Persist all changes to disk."""
        self.store.save()

    def on_memory_added(self, callback: Callable[[Memory], None]):
        """Register callback for when memories are added."""
        self._on_memory_added.append(callback)

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> List[str]:
        """Simple keyword extraction from text."""
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'and', 'but', 'or', 'nor', 'so', 'yet', 'both', 'either',
            'neither', 'not', 'only', 'same', 'than', 'too', 'very',
            'just', 'also', 'now', 'here', 'there', 'when', 'where',
            'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'any', 'this', 'that',
            'these', 'those', 'what', 'which', 'who', 'whom', 'whose'
        }

        # Tokenize and filter
        words = text.lower().split()
        words = [w.strip('.,!?;:()[]{}"\'-') for w in words]
        words = [w for w in words if w and len(w) > 2 and w not in stop_words]

        # Count frequencies
        freq: Dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1

        # Return top keywords
        sorted_words = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
        return [w for w, _ in sorted_words[:max_keywords]]


# =============================================================================
# BACKWARDS COMPATIBILITY ALIASES
# =============================================================================

NexusMemory = SynapseMemory
EngramMemory = SynapseMemory


# =============================================================================
# GLOBAL INSTANCE  --  the handle law
# =============================================================================
#
# ONE handle per storage URI, ONE owner per handle (AGENTS.md §3.1).
#
# This process holds exactly TWO store authorities, and that split is
# DELIBERATE -- they are rooted at different URIs and serve different readers:
#
#   1. PROJECT MEMORY   `_global_synapse` (here)        -> <project>/.synapse
#   2. LEDGER FINDINGS  `ledger._MONETA_STORE`          -> $SYNAPSE_LEDGER_DIR
#                       (`ledger.ledger_moneta_store`)     default <repo>/.synapse/ledger
#
# Under the default roots those are distinct `moneta-file://` URIs, so the two
# do not contend for Moneta's single-owner lock. That is a property of the
# PATHS, not a guarantee: point $SYNAPSE_LEDGER_DIR at the project storage dir
# and the second handle raises MonetaResourceLockedError (stated at
# `ledger.ledger_moneta_store`, and it is honest about it). `memory_handle_census()`
# below reports both in one place; it CONSTRUCTS NOTHING, so reading the census
# can never become a third way to open a store.
#
# Why this one is a scalar and the ledger's is a URI-keyed registry: the ledger's
# key is a cheap env-var read (`ledger_dir()`), so re-keying on every access is
# free. This accessor's URI is not knowable without `SynapseMemory.__init__`
# work -- `_resolve_project_path` marshals `hou.hipFile.path()` to Houdini's main
# thread (store.py:1099-1105) and `_get_storage_dir` may `shutil.copytree` a
# legacy `.nexus/` tree (store.py:1156). Re-deriving the key per call would put a
# blocking main-thread hop and a migration probe on every reader. Project changes
# route through `reset_synapse_memory()` instead, which now RELEASES the handle.

_global_synapse: Optional[SynapseMemory] = None

# Re-entrant on purpose: `SynapseMemory.__init__` runs INSIDE this lock, and a
# plain Lock would deadlock the whole process if any construction path ever
# reached back into the accessor. Re-entry is still not allowed to orphan a
# handle -- see the post-construction re-check in get_synapse_memory().
_GLOBAL_LOCK = threading.RLock()


def _close_memory_quietly(mem: "SynapseMemory", why: str) -> None:
    """Persist and RELEASE a SynapseMemory's backend handle. Never raises.

    `save()` alone is not a release. `MonetaBackedStore.close()` is what drops
    the `moneta-file://` URI lock (moneta_store.py:934-958); without it the
    object stays reachable from the atexit hook registered in
    `from_storage_dir` (moneta_store.py:377-378) and keeps the URI locked for
    the rest of the process, so the NEXT construction fails with
    MonetaResourceLockedError and is silently downgraded to jsonl.
    """
    store = getattr(mem, "store", None)
    closer = getattr(store, "close", None)
    if callable(closer):
        try:
            closer()
            return
        except Exception as exc:  # noqa: BLE001 -- teardown must not propagate
            # ERROR, not warning: this is the precursor to the silent downgrade.
            # A handle that would not close may still hold the moneta-file://
            # URI, and the NEXT construction then falls back to jsonl.
            logger.error(
                "Closing the %s memory handle FAILED (%s: %s); the storage URI "
                "may stay locked for this process and the next store "
                "construction may silently fall back to jsonl",
                why, type(exc).__name__, exc,
            )
            return
    # No close() on this backend (MemoryStore holds no external lock): a save is
    # the whole of its teardown.
    try:
        mem.save()
    except Exception as exc:  # noqa: BLE001
        logger.error("Saving the %s memory handle FAILED (%s: %s); buffered "
                     "memories may not have reached disk",
                     why, type(exc).__name__, exc)


def get_synapse_memory() -> SynapseMemory:
    """Get or create the process-global SynapseMemory instance.

    Double-checked locking. The unlocked read is the fast path (attribute loads
    and reference assignment are atomic under the GIL, and the global is only
    ever published fully constructed); the lock covers the construct-and-publish
    window that used to let N concurrent callers build N stores and orphan N-1
    of them on the same storage URI.
    """
    def obtain():
        global _global_synapse
        existing = _global_synapse
        if existing is None:
            with _GLOBAL_LOCK:
                if _global_synapse is None:
                    built = SynapseMemory()
                    if _global_synapse is None:
                        _global_synapse = built
                    else:
                        # Re-entrant construction published a handle underneath us.
                        _close_memory_quietly(built, "superseded")
                existing = _global_synapse
        if getattr(existing, "_memory_binding", None) is not None:
            from ..host.memory_lifecycle import register_owner
            register_owner(existing)
        return existing
    # Marshal the whole constructor BEFORE taking the authority lock. Merely
    # marshaling hou path reads leaves native Moneta construction on a worker,
    # and waiting for main while holding this lock can deadlock the owner.
    if HOU_AVAILABLE:
        return _read_on_main(obtain, label="synapse_memory_owner")
    return obtain()


def reset_synapse_memory():
    """Release the global SynapseMemory instance (e.g., when opening a new project).

    Closes the backend handle, not just `save()` -- see `_close_memory_quietly`.
    The global is cleared even when teardown raises, so a store that refuses to
    close cannot wedge the accessor for the life of the process.
    """
    global _global_synapse
    with _GLOBAL_LOCK:
        stale, _global_synapse = _global_synapse, None
    if stale is not None:
        _close_memory_quietly(stale, "reset")


def memory_handle_census() -> Dict[str, Any]:
    """Report BOTH store authorities in one place, without constructing either.

    An observer, never an authority: it peeks module globals exactly the way
    `panel/health_strip.py:311` does (the reference-clean disciplined read) and
    reports `live: False` rather than opening anything. Unreadable state is
    reported as an explicit error string -- never as an absent handle.
    """
    # Snapshot once: a concurrent reset_synapse_memory() between two reads of
    # the global would otherwise let the census report a live handle with a
    # None URI -- an observer must never invent a state that never existed.
    held_project = _global_synapse
    project: Dict[str, Any] = {
        "authority": "python/synapse/memory/store.py:_global_synapse",
        "accessor": "synapse.memory.store.get_synapse_memory",
        "live": held_project is not None,
        "storage_uri": (str(held_project.storage_dir)
                        if held_project is not None else None),
        "backend": (type(held_project.store).__name__
                    if held_project is not None else None),
    }
    ledger_entry: Dict[str, Any] = {
        "authority": "python/synapse/memory/ledger.py:_MONETA_STORE",
        "accessor": "synapse.memory.ledger.ledger_moneta_store",
        "live": None,
        "storage_uri": None,
        "backend": None,
    }
    try:
        from . import ledger as _ledger
        held = getattr(_ledger, "_MONETA_STORE", None)
        ledger_entry["live"] = held is not None
        ledger_entry["storage_uri"] = getattr(_ledger, "_MONETA_STORE_KEY", None)
        ledger_entry["backend"] = type(held).__name__ if held is not None else None
    except Exception as exc:  # noqa: BLE001
        ledger_entry["error"] = f"{type(exc).__name__}: {exc}"
    return {"project_memory": project, "ledger_findings": ledger_entry}


# Backwards compatibility aliases
def get_nexus_memory() -> SynapseMemory:
    """Get or create the global memory instance (backwards compatible)."""
    return get_synapse_memory()


def get_engram() -> SynapseMemory:
    """Get or create the global memory instance (backwards compatible)."""
    return get_synapse_memory()


def reset_nexus_memory():
    """Reset the global memory instance (backwards compatible)."""
    reset_synapse_memory()


def reset_engram():
    """Reset the global memory instance (backwards compatible)."""
    reset_synapse_memory()
