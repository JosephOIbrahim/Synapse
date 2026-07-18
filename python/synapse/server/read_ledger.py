"""Bounded JSONL append ledger for READ-class command executions (Mile 0).

The scene-model measurement slice: before any composition/graft code lands,
instrument what the live path actually *reads*. Every successful read-only
command through ``SynapseHandler.handle()`` appends one record here so the
re-read rate (same command + same args re-observed within a session) becomes
a number instead of a hunch.

Record shape (one JSON object per line)::

    {"ts": iso8601-utc, "session_id": str, "cmd_type": str,
     "args_hash": sha256(canonical-sorted-JSON payload)[:16],
     "result_bytes": int}

Disciplines (all inherited from existing repo idioms):

* **Zero ``hou``.** Pure stdlib + intra-package imports only.
* **Never fails a command.** Every exception is swallowed after a ONE-TIME
  warning (the ``integrity_envelope._infra_warned`` idiom) — a broken disk
  must not make reads observably slower or louder than once.
* **Kill switch read at CALL TIME** (``SYNAPSE_READ_LEDGER=0`` — the
  ``integrity_envelope._envelope_enabled`` idiom): a toggle takes effect
  without re-import.
* **Bounded on disk** (the FloorGate max-records idiom): cap resolved
  lazily from ``SYNAPSE_READ_LEDGER_MAX_RECORDS`` (default 5000, ``<= 0``
  or unparseable disables rotation — an explicit opt-out), reconciled from
  disk once per path per process, oldest lines FIFO-evicted via atomic
  ``.tmp + os.replace`` rewrite.
* **Thread-safe append** — called from the handlers ``_log_executor``
  worker threads; a module lock serializes append + rotation.
* **Session identity is REUSED, not invented**: the same
  ``AuditLog._current_session`` the audit trail stamps on every entry.

Multi-process caveat (same class as ``logfile.py``'s RotatingFileHandler
note): two processes appending to the same file may lose lines across a
concurrent rotation rewrite. Acceptable for a measurement instrument.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict

_log = logging.getLogger(__name__)

LEDGER_FILENAME = "read_ledger.jsonl"
DEFAULT_MAX_RECORDS = 5000

_ENV_ENABLE = "SYNAPSE_READ_LEDGER"
_ENV_MAX_RECORDS = "SYNAPSE_READ_LEDGER_MAX_RECORDS"

# One lock guards append + rotation + the per-path count cache.
_lock = threading.Lock()
# path -> known line count. Reconciled from disk ONCE per path per process
# (the FloorGate ``_reconciled`` idiom), incremented per append after that.
_counts: Dict[str, int] = {}
_write_warned = False


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


def ledger_path() -> str:
    """Resolve the ledger file path under the shared logs dir.

    Reuses ``core.logfile.log_dir()`` (``$SYNAPSE_LOG_DIR`` else
    ``~/.synapse/logs``) — called at append time so an env change (tests,
    operator) takes effect without re-import.
    """
    from ..core.logfile import log_dir
    return os.path.join(log_dir(), LEDGER_FILENAME)


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


def _session_id() -> str:
    """The audit trail's session identity — REUSED, never a second scheme.

    ``AuditLog._current_session`` is the id stamped on every audit entry
    (core/audit.py). Falls back to ``"unknown"`` only if the audit
    singleton itself is broken — a fallback constant, not a new mechanism.
    """
    try:
        from ..core.audit import audit_log
        return audit_log()._current_session
    except Exception:
        return "unknown"


def _result_bytes(result: Any) -> int:
    """Size of the canonical serialization of the result, in bytes."""
    return len(json.dumps(
        result, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8"))


def record_read(cmd_type: str, payload: Any, result: Any) -> bool:
    """Append one READ observation. NEVER raises.

    Returns True when a row was written (test/diagnostic convenience),
    False when disabled or on any (once-warned) failure. Runs on the
    handlers ``_log_executor`` worker threads — thread-safe by module lock.
    """
    global _write_warned
    try:
        if not read_ledger_enabled():
            return False
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": _session_id(),
            "cmd_type": cmd_type,
            "args_hash": args_hash(payload),
            "result_bytes": _result_bytes(result),
        }
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        path = ledger_path()
        with _lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(line + "\n")
            _bump_and_rotate_locked(path)
        return True
    except Exception:
        if not _write_warned:
            _write_warned = True
            _log.warning(
                "read ledger: append failed -- read observations will be "
                "missing until this is fixed",
                exc_info=True,
            )
        return False


def _bump_and_rotate_locked(path: str) -> None:
    """Track the line count for *path* and FIFO-trim past the cap.

    Caller holds ``_lock``. First touch of a path reconciles the count
    from disk (cap survives process restarts — FloorGate idiom); later
    appends increment. Over-cap: rewrite keeping the NEWEST ``cap`` lines
    via atomic ``.tmp + os.replace`` (the RecommendationHistory idiom).
    """
    if path in _counts:
        _counts[path] += 1
    else:
        with open(path, "r", encoding="utf-8") as fh:
            _counts[path] = sum(1 for _ in fh)

    cap = resolve_max_records()
    if cap <= 0 or _counts[path] <= cap:
        return

    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    keep = lines[-cap:]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(keep)
    os.replace(tmp, path)
    _counts[path] = len(keep)


def reset_ledger_state() -> None:
    """Test/diagnostic helper (the ``logfile.reset_file_logging`` idiom):
    drop the per-path count cache and re-arm the one-time warning."""
    global _write_warned
    with _lock:
        _counts.clear()
        _write_warned = False
