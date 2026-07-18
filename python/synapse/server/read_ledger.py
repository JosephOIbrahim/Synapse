"""Bounded JSONL append ledger for READ-class command executions (Mile 0).

The scene-model measurement slice: before any composition/graft code lands,
instrument what the live path actually *reads*. Every successful read-only
command through ``SynapseHandler.handle()`` appends one record here so the
re-read rate (same command + same args re-observed within a session) becomes
a number instead of a hunch.

Record shape (one JSON object per line)::

    {"ts": iso8601-utc, "session_id": str,
     "session_scope": "connection" | "process",
     "cmd_type": str,
     "args_hash": sha256(canonical-sorted-JSON payload)[:16],
     "result_bytes": int}

Session identity (fix pass 2026-07-18): the PRIMARY id is the handler's
per-connection ``_session_id`` (set via ``set_session_id`` by the WS/
hwebserver adapters) — the same identity FloorGate provenance uses, and the
one the Mile-1 transcript-mine baseline is priced in (one transcript ≈ one
connection). Only when the handler has none does the record fall back to the
audit trail's process-lifetime id. ``session_scope`` records which was used,
honestly — the two have different re-read semantics (a days-open Houdini
process spans many conversations; merging them inflates the re-read rate).

What is deliberately NOT recorded (fix pass 2026-07-18):

* **Liveness/control-plane traffic** (:data:`INFRA_READ_COMMANDS`): ping,
  heartbeats, health/metrics/status polls, static catalog reads. Their
  payloads are empty-or-identical by design, so every one after the first
  would masquerade as a "re-read" while saying nothing about scene state —
  and they'd flood the FIFO cap, evicting genuine observations.
* **Render polls** (``render`` + ``{"poll": token}``): the handlers hook
  gates on ``_READ_ONLY_COMMANDS`` membership, which ``render`` fails — the
  crucible-F3 poll override never reaches this ledger.
* **``batch_commands`` sub-reads**: sub-ops dispatch through
  ``registry.invoke()`` and bypass ``handle()`` where the hook lives — the
  same documented seam as the integrity envelope's one-block-per-batch.
  The baseline therefore UNDERCOUNTS reads issued inside batches; the
  report script states this exclusion.

Disciplines (mechanics shared with ``panel/turns_ledger.py`` via
``core.jsonl_ledger.BoundedJsonlLedger``):

* **Zero ``hou``.** Pure stdlib + intra-package imports only.
* **Never fails a command.** Every exception swallowed after a ONE-TIME
  warning; a successful append returns True even if the post-append
  rotation failed.
* **Kill switch read at CALL TIME** (``SYNAPSE_READ_LEDGER=0`` — the
  ``integrity_envelope._envelope_enabled`` idiom).
* **Bounded on disk** (FloorGate max-records idiom + trim hysteresis):
  ``SYNAPSE_READ_LEDGER_MAX_RECORDS`` (default 5000, ``<= 0`` or
  unparseable disables rotation).
* **Thread-safe append** — called from the handlers ``_log_executor``
  worker threads.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from ..core.jsonl_ledger import BoundedJsonlLedger

_log = logging.getLogger(__name__)

LEDGER_FILENAME = "read_ledger.jsonl"
DEFAULT_MAX_RECORDS = 5000

_ENV_ENABLE = "SYNAPSE_READ_LEDGER"
_ENV_MAX_RECORDS = "SYNAPSE_READ_LEDGER_MAX_RECORDS"

#: Liveness/control-plane commands NEVER recorded (see module docstring).
#: Every member must also be in ``handlers._READ_ONLY_COMMANDS`` (pinned by
#: test_read_ledger) and the report script carries a conformance-pinned copy.
INFRA_READ_COMMANDS = frozenset({
    "ping", "heartbeat", "get_health", "get_help",
    "get_metrics", "get_live_metrics", "router_stats", "list_recipes",
    "render_farm_status", "render_farm_cancel",
})


def read_ledger_enabled() -> bool:
    """Env kill switch: ``SYNAPSE_READ_LEDGER=0`` disables the ledger.

    Default ON. Read at call time (cheap dict lookup — the
    ``integrity_envelope._envelope_enabled`` idiom) so a toggle takes
    effect without re-import.
    """
    return os.environ.get(_ENV_ENABLE, "1").strip().lower() not in (
        "0", "false", "off",
    )


def resolve_max_records() -> int:
    """Resolve the FIFO cap from ``$SYNAPSE_READ_LEDGER_MAX_RECORDS``.

    Returns the configured int, else :data:`DEFAULT_MAX_RECORDS`. A value
    ``<= 0`` (or unparseable) DISABLES rotation — the FloorGate
    ``resolve_provenance_max_records`` idiom.
    """
    raw = os.environ.get(_ENV_MAX_RECORDS)
    if raw is None:
        return DEFAULT_MAX_RECORDS
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0  # unparseable => rotation disabled


_LEDGER = BoundedJsonlLedger(
    LEDGER_FILENAME, resolve_max_records,
    logger=_log, warn_label="read ledger",
)


def ledger_path() -> str:
    """Resolve the ledger file path under the shared logs dir
    (``core.logfile.log_dir()``, resolved at call time)."""
    return _LEDGER.path()


def args_hash(payload: Any) -> str:
    """Deterministic 16-hex digest of the command payload.

    Canonicalization: ``json.dumps(payload, sort_keys=True,
    separators=(',', ':'), default=str)`` — two dicts with different key
    insertion orders hash identically.
    """
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _resolve_session(session_id: Optional[str]) -> Tuple[str, str]:
    """(id, scope): the caller's per-connection id when given, else the
    audit trail's process-lifetime id (public accessor — never a second
    identity scheme). ``"unknown"``/``"process"`` only if audit is broken."""
    if session_id:
        return str(session_id), "connection"
    try:
        from ..core.audit import audit_log
        return audit_log().current_session_id(), "process"
    except Exception:
        return "unknown", "process"


def _result_bytes(result: Any) -> int:
    """Size of the canonical serialization of the result, in bytes."""
    return len(json.dumps(
        result, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8"))


def record_read(
    cmd_type: str, payload: Any, result: Any,
    session_id: Optional[str] = None,
) -> bool:
    """Append one READ observation. NEVER raises.

    ``session_id`` is the handler's per-connection identity (PASS IT —
    the process-lifetime audit id is only a fallback; see docstring).
    Returns True when a row was written, False when disabled, when
    *cmd_type* is infra traffic (:data:`INFRA_READ_COMMANDS`), or on any
    (once-warned) failure. Runs on the handlers ``_log_executor`` worker
    threads — thread-safe via the shared ledger lock.
    """
    try:
        if not read_ledger_enabled():
            return False
        if cmd_type in INFRA_READ_COMMANDS:
            return False
        sid, scope = _resolve_session(session_id)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": sid,
            "session_scope": scope,
            "cmd_type": cmd_type,
            "args_hash": args_hash(payload),
            "result_bytes": _result_bytes(result),
        }
        return _LEDGER.append(record)
    except Exception:
        _LEDGER.warn_once(
            "record failed -- read observations will be missing until "
            "this is fixed")
        return False


def reset_ledger_state() -> None:
    """Test/diagnostic helper (the ``logfile.reset_file_logging`` idiom):
    drop the per-path count cache and re-arm the one-time warning."""
    _LEDGER.reset_state()
