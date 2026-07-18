"""Turns-per-send JSONL ledger — the U2 instrument (scene-model Mile 0).

``claude_worker._conversation_loop`` already *logs* "Conversation complete:
N turns, M tool calls" (L9). This module promotes that log-only line to a
persisted record so the turns-per-send distribution — the dominant latency
term, imperative build (many turns) vs one-shot declarative call (1 turn) —
is measurable on disk across sessions.

Record shape (one JSON object per line)::

    {"ts": iso8601-utc, "provider_id": str, "turns": int,
     "tool_calls": int, "hit_25_cap": bool}

Same disciplines as ``server.read_ledger`` (the FILE-1 sibling):

* Pure stdlib. Zero ``hou``, zero Qt.
* Never fails the caller — every exception swallowed after a ONE-TIME
  warning.
* Same logs-dir resolution (``core.logfile.log_dir()``:
  ``$SYNAPSE_LOG_DIR`` else ``~/.synapse/logs``), read at append time.
* Same FloorGate cap idiom: ``SYNAPSE_TURNS_LEDGER_MAX_RECORDS``
  (default 5000, ``<= 0`` / unparseable disables rotation), count
  reconciled from disk once per path per process, FIFO trim via atomic
  ``.tmp + os.replace``.
* Thread-safe (called from the worker QThread) via a module lock.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Dict

_log = logging.getLogger(__name__)

LEDGER_FILENAME = "turns.jsonl"
DEFAULT_MAX_RECORDS = 5000

_ENV_MAX_RECORDS = "SYNAPSE_TURNS_LEDGER_MAX_RECORDS"

_lock = threading.Lock()
# path -> known line count (reconciled from disk once per path per process).
_counts: Dict[str, int] = {}
_write_warned = False


def resolve_max_records() -> int:
    """FIFO cap from ``$SYNAPSE_TURNS_LEDGER_MAX_RECORDS`` (FloorGate
    idiom): default 5000; ``<= 0`` or unparseable disables rotation."""
    raw = os.environ.get(_ENV_MAX_RECORDS)
    if raw is None:
        return DEFAULT_MAX_RECORDS
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0  # unparseable => rotation disabled


def ledger_path() -> str:
    """``<logs dir>/turns.jsonl`` via ``core.logfile.log_dir()`` — resolved
    at append time so env changes take effect without re-import."""
    from ..core.logfile import log_dir
    return os.path.join(log_dir(), LEDGER_FILENAME)


def append_turn_record(
    provider_id: str, turns: int, tool_calls: int, hit_cap: bool,
) -> bool:
    """Append one turns-per-send record. NEVER raises.

    Returns True when a row was written, False on any (once-warned)
    failure — the caller's behavior must be identical either way.
    """
    global _write_warned
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider_id": provider_id,
            "turns": int(turns),
            "tool_calls": int(tool_calls),
            "hit_25_cap": bool(hit_cap),
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
                "turns ledger: append failed -- turns-per-send records will "
                "be missing until this is fixed",
                exc_info=True,
            )
        return False


def _bump_and_rotate_locked(path: str) -> None:
    """Caller holds ``_lock``. Same mechanics as read_ledger: reconcile the
    count from disk on first touch, increment after, FIFO-trim to the cap
    keeping the NEWEST lines via atomic ``.tmp + os.replace``."""
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
    """Test/diagnostic helper: drop the count cache, re-arm the warning."""
    global _write_warned
    with _lock:
        _counts.clear()
        _write_warned = False
