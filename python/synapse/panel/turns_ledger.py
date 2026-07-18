"""Turns-per-send JSONL ledger — the U2 instrument (scene-model Mile 0).

``claude_worker._conversation_loop`` already *logs* "Conversation complete:
N turns, M tool calls" (L9). This module promotes that log-only line to a
persisted record so the turns-per-send distribution — the dominant latency
term, imperative build (many turns) vs one-shot declarative call (1 turn) —
is measurable on disk across sessions.

Record shape (one JSON object per line)::

    {"ts": iso8601-utc, "provider_id": str, "model": str | null,
     "turns": int, "tool_calls": int, "hit_25_cap": bool,
     "outcome": "completed" | "cap" | "aborted" | "error"}

Fix pass 2026-07-18:

* ``model`` — the provider MODEL id (``StreamProvider.model_identity``),
  the CTO-gate 6b confound control: a mid-soak-window model update must be
  visible in the baseline data.
* ``outcome`` — kills the survivorship bias: aborted sends (the Stop
  button exists precisely to kill runaway imperative loops — the many-turn
  tail this instrument measures) and provider-error sends now land rows
  with the turns reached, instead of vanishing.
* ``SYNAPSE_TURNS_LEDGER=0`` kill switch (call-time, mirroring
  ``read_ledger_enabled`` — the read ledger must not be the only default-on
  disk writer a support desk can reach).

Same disciplines as ``server.read_ledger`` — mechanics shared via
``core.jsonl_ledger.BoundedJsonlLedger``: pure stdlib, zero ``hou``, zero
Qt; never fails the caller (ONE-TIME warning); same logs-dir resolution;
FloorGate cap idiom via ``SYNAPSE_TURNS_LEDGER_MAX_RECORDS`` (default 5000,
``<= 0`` / unparseable disables rotation) with trim hysteresis; thread-safe
(called from the worker QThread).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from ..core.jsonl_ledger import BoundedJsonlLedger

_log = logging.getLogger(__name__)

LEDGER_FILENAME = "turns.jsonl"
DEFAULT_MAX_RECORDS = 5000

_ENV_ENABLE = "SYNAPSE_TURNS_LEDGER"
_ENV_MAX_RECORDS = "SYNAPSE_TURNS_LEDGER_MAX_RECORDS"

#: The closed outcome vocabulary. Unknown values are coerced to "error"
#: (never dropped — a row with a weird outcome is still a send).
OUTCOMES = frozenset({"completed", "cap", "aborted", "error"})


def turns_ledger_enabled() -> bool:
    """Env kill switch: ``SYNAPSE_TURNS_LEDGER=0`` disables the ledger.
    Default ON, read at call time (the ``read_ledger_enabled`` idiom)."""
    return os.environ.get(_ENV_ENABLE, "1").strip().lower() not in (
        "0", "false", "off",
    )


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


_LEDGER = BoundedJsonlLedger(
    LEDGER_FILENAME, resolve_max_records,
    logger=_log, warn_label="turns ledger",
)


def ledger_path() -> str:
    """``<logs dir>/turns.jsonl`` via ``core.logfile.log_dir()`` — resolved
    at call time so env changes take effect without re-import."""
    return _LEDGER.path()


def append_turn_record(
    provider_id: str,
    turns: int,
    tool_calls: int,
    hit_cap: bool,
    outcome: str = "completed",
    model: Optional[str] = None,
) -> bool:
    """Append one turns-per-send record. NEVER raises.

    Returns True when a row was written, False when disabled or on any
    (once-warned) failure — the caller's behavior must be identical
    either way.
    """
    try:
        if not turns_ledger_enabled():
            return False
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider_id": provider_id,
            "model": str(model) if model else None,
            "turns": int(turns),
            "tool_calls": int(tool_calls),
            "hit_25_cap": bool(hit_cap),
            "outcome": outcome if outcome in OUTCOMES else "error",
        }
        return _LEDGER.append(record)
    except Exception:
        _LEDGER.warn_once(
            "record failed -- turns-per-send records will be missing "
            "until this is fixed")
        return False


def reset_ledger_state() -> None:
    """Test/diagnostic helper: drop the count cache, re-arm the warning."""
    _LEDGER.reset_state()
