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

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional


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

    @property
    def provenance_dir(self) -> str:
        if self._provenance_dir is None:
            self._provenance_dir = resolve_provenance_dir()
        return self._provenance_dir

    def new_op_id(self) -> str:
        """Mint a unique op-id (used to thread a batch parent down to sub-ops)."""
        with self._lock:
            self._seq += 1
            seq = self._seq
        return f"op-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{seq:06d}"

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

        try:
            result = fn(payload)
        except Exception as exc:
            if not read_only:
                self._record(
                    op_id, cmd_type, payload, result=None,
                    outcome="error", ctx=ctx, error_type=type(exc).__name__,
                )
            raise

        if not read_only:
            self._record(
                op_id, cmd_type, payload, result=result,
                outcome="ok", ctx=ctx, error_type=None,
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
        error_type: Optional[str],
    ) -> None:
        """Write a single provenance record through the durable write-path.

        Best-effort: a failure to record never masks the operation's own result
        or exception (recording is observability, not the operation).
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
            "parent": ctx.parent if ctx else None,
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
            pass
