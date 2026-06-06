"""FloorGate — Tier-0 provenance hook (the 0a-prime emit-time hook).

Both command registries — ``synapse.server.handlers.CommandHandlerRegistry`` and
``synapse.cognitive.dispatcher.Dispatcher`` — funnel their handler/tool calls
through a single :class:`FloorGate` so that *every mutating operation* leaves a
durable provenance record at the moment it executes.

Design constraints (CTO decisions, baked in):

* **Neutral module, no cycles.** Lives in ``synapse.core`` (alongside
  ``synapse.core.gates``) so both the server and cognitive registries can import
  it WITHOUT a ``cognitive -> server`` import cycle. The read-only taxonomy is
  imported *lazily* (inside :meth:`wrap`) for the same reason.
* **Zero ``hou``.** Pure Python. Provenance is plain file I/O, written through the
  durable, atomic ``write_report`` primitive (tmp + fsync + os.replace).
* **Additive only.** The gate wraps ``fn(payload)`` — it never alters the result,
  never swallows an exception (it re-raises after recording), and writes NOTHING
  for read-only ops.
* **Tier-0 only.** This is provenance, not admission control. No halting, no
  consent gating — that is Tier-1, out of scope here.
"""

from __future__ import annotations

import collections
import contextvars
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, Optional

# The op-id of the operation currently executing on this thread/context. Set by
# ``FloorGate.wrap`` around ``fn()`` so a nested op can discover its parent. Read
# explicitly (``current_op_id``) by ``_handle_batch_commands`` BEFORE it marshals
# sub-ops to the main thread — a contextvar does not survive that thread hop, so
# the batch threads its parent explicitly; the contextvar covers same-thread
# nesting (the general case).
_current_op: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "synapse_floor_current_op", default=None
)


@dataclass(frozen=True)
class FloorContext:
    """Call-site context threaded into a provenance record.

    Attributes:
        session: Session id of the originating client, if any.
        origin: Where the call entered — ``'handler'`` (default WS handle path),
            ``'batch'`` (a batch sub-op), or ``'autonomy'`` (the autonomy adapter).
        parent: Parent op-id this record nests under (e.g. the batch envelope's
            op-id, so the N sub-ops nest under the 1 envelope record).
    """

    session: Optional[str] = None
    origin: Optional[str] = None
    parent: Optional[str] = None


def _canonical_digest(obj: Any) -> str:
    """sha256 of a canonical JSON serialization of ``obj``.

    ``sort_keys`` makes the digest order-independent; ``default=str`` keeps it
    total over non-JSON-native values (datetimes, hou stand-ins in tests, etc.)
    instead of raising. Deterministic for equal inputs.
    """
    try:
        serialized = json.dumps(obj, sort_keys=True, default=str)
    except Exception:
        serialized = repr(obj)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def resolve_provenance_dir() -> str:
    """Resolve the provenance root WITHOUT importing ``hou``.

    ``$SYNAPSE_PROVENANCE_DIR`` if set, else ``<repo-root>/.synapse/provenance``.
    Mirrors how ``_handle_write_report`` resolves its reports base dir — the repo
    root is three directories up from this file (``core`` -> ``synapse`` ->
    ``python`` -> repo-root).
    """
    base_dir = os.environ.get("SYNAPSE_PROVENANCE_DIR")
    if base_dir:
        return base_dir
    here = os.path.dirname(os.path.abspath(__file__))  # .../python/synapse/core
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    return os.path.join(repo_root, ".synapse", "provenance")


# Default FIFO cap on provenance files retained in the provenance dir.
DEFAULT_PROVENANCE_MAX_RECORDS = 5000


def resolve_provenance_max_records() -> int:
    """Resolve the FIFO retention cap from ``$SYNAPSE_PROVENANCE_MAX_RECORDS``.

    Returns the configured int, else :data:`DEFAULT_PROVENANCE_MAX_RECORDS`. A
    value ``<= 0`` (or unparseable) DISABLES rotation (unbounded — an explicit
    opt-out), signalled by returning the raw value (``<= 0``).
    """
    raw = os.environ.get("SYNAPSE_PROVENANCE_MAX_RECORDS")
    if raw is None:
        return DEFAULT_PROVENANCE_MAX_RECORDS
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0  # unparseable => rotation disabled


class FloorGate:
    """Records one provenance file per mutating op, around ``fn(payload)``.

    A single instance is shared by a registry (constructed once on the registry /
    handler / dispatcher). It carries no per-call state beyond a counter used to
    mint unique op-ids; it is thread-safe.
    """

    def __init__(self, *, provenance_dir: Optional[str] = None) -> None:
        self._provenance_dir = provenance_dir
        self._seq = 0
        self._lock = threading.Lock()
        # FIFO rotation state (all guarded by ``self._lock``):
        #   _max_records   — cap, resolved lazily at first use (None = unread)
        #   _record_paths  — known record file paths, oldest-first
        #   _reconciled    — has the one-time on-disk startup sweep run yet?
        self._max_records: Optional[int] = None
        self._record_paths: Deque[str] = collections.deque()
        self._reconciled = False

    @property
    def provenance_dir(self) -> str:
        if self._provenance_dir is None:
            self._provenance_dir = resolve_provenance_dir()
        return self._provenance_dir

    @property
    def max_records(self) -> int:
        """FIFO retention cap, resolved lazily from the environment once."""
        if self._max_records is None:
            self._max_records = resolve_provenance_max_records()
        return self._max_records

    def new_op_id(self) -> str:
        """Mint a unique op-id (used to thread a batch parent down to sub-ops)."""
        with self._lock:
            self._seq += 1
            seq = self._seq
        return f"op-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{seq:06d}"

    @staticmethod
    def current_op_id() -> Optional[str]:
        """The op-id of the op currently executing on this thread, or None.

        ``wrap`` sets this around ``fn()``, so a handler running *inside* a
        wrapped op (e.g. ``_handle_batch_commands`` inside the 'batch_commands'
        envelope's wrap) reads its own envelope's REAL op-id here and threads it
        to its sub-ops — making the nesting linkage reference an actual record
        rather than a freshly-minted phantom.
        """
        return _current_op.get()

    @staticmethod
    def _is_read_only(cmd_type: str) -> bool:
        """Reuse the handler-layer taxonomy — do NOT duplicate it.

        Imported lazily so this module stays free of a ``core -> server`` import
        cycle and imports clean headless. If handlers can't be imported for any
        reason, treat the op as mutating (fail toward recording, never toward a
        silent provenance gap).
        """
        try:
            from synapse.server.handlers import _READ_ONLY_COMMANDS
        except Exception:
            return False
        return cmd_type in _READ_ONLY_COMMANDS

    def wrap(
        self,
        cmd_type: str,
        payload: Any,
        fn: Callable[[Any], Any],
        ctx: Optional[FloorContext] = None,
    ) -> Any:
        """Run ``fn(payload)`` and, for mutating ops, emit one provenance record.

        Read-only ops (per ``_READ_ONLY_COMMANDS``) execute with zero provenance.
        On a handler exception, a record with ``outcome='error'`` is written
        FIRST (so provenance survives failures), then the exception re-raises
        unchanged.
        """
        read_only = self._is_read_only(cmd_type)
        op_id = None if read_only else self.new_op_id()

        # Parent linkage: an explicit ``ctx.parent`` wins (the batch envelope
        # threads its real op-id to sub-ops, surviving the run_on_main thread
        # hop); otherwise nest under the enclosing op on this thread's stack.
        explicit_parent = ctx.parent if (ctx and ctx.parent) else None
        parent = explicit_parent if explicit_parent is not None else _current_op.get()

        token = _current_op.set(op_id) if op_id is not None else None
        try:
            result = fn(payload)
        except Exception as exc:
            if not read_only:
                self._record(
                    op_id, cmd_type, payload, result=None,
                    outcome="error", ctx=ctx, parent=parent,
                    error_type=type(exc).__name__,
                )
            raise
        finally:
            if token is not None:
                _current_op.reset(token)

        if not read_only:
            self._record(
                op_id, cmd_type, payload, result=result,
                outcome="ok", ctx=ctx, parent=parent, error_type=None,
            )
        return result

    def _record(
        self,
        op_id: Optional[str],
        cmd_type: str,
        payload: Any,
        *,
        result: Any,
        outcome: str,
        ctx: Optional[FloorContext],
        parent: Optional[str],
        error_type: Optional[str],
    ) -> None:
        """Write a single provenance record through the durable write-path.

        Best-effort: a failure to record never masks the operation's own result
        or exception (recording is observability, not the operation).

        ``parent`` is the resolved linkage (explicit ctx.parent, else the
        enclosing op), computed by :meth:`wrap` — NOT re-read from ``ctx`` here.
        """
        record: Dict[str, Any] = {
            "op_id": op_id,
            "op": cmd_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": ctx.session if ctx else None,
            "payload_digest": _canonical_digest(payload),
            "result_digest": _canonical_digest(result),
            "outcome": outcome,
            "origin": ctx.origin if ctx else None,
            "parent": parent,
        }
        if error_type is not None:
            record["error_type"] = error_type

        try:
            from synapse.cognitive.tools.write_report import write_report
            write_report(
                f"{op_id}.json",
                json.dumps(record, sort_keys=True, default=str),
                overwrite=True,
                base_dir=self.provenance_dir,
            )
        except Exception:
            # Never let a provenance write failure break the live op.
            return

        # Housekeeping AFTER the record is durably on disk. Wrapped so a rotation
        # failure can never propagate — provenance + its trimming are
        # observability, not the operation.
        try:
            self._rotate(os.path.join(self.provenance_dir, f"{op_id}.json"))
        except Exception:
            pass

    def _rotate(self, record_path: str) -> None:
        """FIFO-trim the provenance dir to :attr:`max_records` after a write.

        Appends the just-written ``record_path`` to the in-memory deque, then,
        while the deque exceeds the cap, ``popleft`` the OLDEST path and unlink
        it. A cap ``<= 0`` disables rotation entirely (unbounded). The first call
        also performs a one-time on-disk reconcile sweep so the cap survives
        process restarts. All deque/cap state is guarded by ``self._lock``;
        unlinks happen outside the lock and tolerate a concurrently-removed file.
        """
        cap = self.max_records
        if cap <= 0:
            return  # rotation disabled — unbounded retention

        to_unlink = []
        with self._lock:
            if not self._reconciled:
                self._reconcile_locked(skip=record_path)
                self._reconciled = True
            self._record_paths.append(record_path)
            while len(self._record_paths) > cap:
                to_unlink.append(self._record_paths.popleft())

        for path in to_unlink:
            self._unlink_quiet(path)

    def _reconcile_locked(self, *, skip: str) -> None:
        """One-time startup sweep: seed the deque from the on-disk provenance dir.

        Lists existing ``*.json`` records, sorts by name (op-ids are
        UTC-microsecond timestamped, so name order == chronological order) and
        seeds the deque oldest-first. ``skip`` is the just-written record path —
        it is excluded here because the caller appends it immediately after, so
        it is never double-counted. Trimming to ``cap`` is left to the single
        loop in :meth:`_rotate`. Best-effort: if the dir can't be listed
        (missing/permission), seed nothing. Caller holds ``self._lock``.
        """
        try:
            existing = sorted(
                name for name in os.listdir(self.provenance_dir)
                if name.endswith(".json")
                and os.path.join(self.provenance_dir, name) != skip
            )
        except OSError:
            return
        self._record_paths.extend(
            os.path.join(self.provenance_dir, name) for name in existing
        )

    @staticmethod
    def _unlink_quiet(path: str) -> None:
        """Unlink ``path``, ignoring a concurrently-removed/locked file."""
        try:
            os.unlink(path)
        except (FileNotFoundError, OSError):
            pass
