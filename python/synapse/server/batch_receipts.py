"""Per-step receipts and the applied-step guard for ``synapse_batch`` (R-034).

Why this exists
---------------
A batch is N registry invocations run in declared order. Its caller waits on
Houdini's main thread with a budget; when that budget expires the caller is
told the call timed out, but the payload may already be *inside* the loop and
keep issuing steps. The 2026-11-20 audit found two consequences:

* the scene keeps mutating after the caller was told the batch timed out;
* a retry re-sends the same command list, so every step that already ran is
  applied a second time.

The fixes are structural and live here:

* every step gets a receipt BEFORE it runs (``in_progress``) and again when it
  finishes (``ok`` / ``error``), written on the executing thread under a lock;
* a caller that stopped waiting reads a point-in-time snapshot: finished steps
  are named, and a step that was mid-flight is reported ``unknown`` -- never
  ``error``, because nothing says it failed;
* a retry that carries the same ``batch_id`` consults the receipts and SKIPS
  every step recorded ``ok`` (the applied-step guard), so a timed-out batch is
  never replayed;
* a step left mid-flight (the payload died inside it) is NOT re-executed on
  retry -- it may have mutated. The retry reports it ``unknown`` and stops
  there; the caller checks the scene. A fresh batch id is the explicit escape
  hatch.

Memory is bounded: the store keeps at most ``DEFAULT_CAPACITY`` batches and
evicts settled ones first, so a lost receipt degrades to "unknown, starts
over" rather than growing without limit. Pure Python -- no ``hou``, no Qt, no
transport imports, so it is importable standalone.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any, Dict, List

STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_IN_PROGRESS = "in_progress"   # live, only ever seen by the executing thread
STATUS_UNKNOWN = "unknown"           # rendered state: in flight when the caller gave up
STATUS_NOT_RUN = "not_run"           # never began (deadline, or a retry that stopped early)

_TERMINAL = frozenset({STATUS_OK, STATUS_ERROR})

#: Receipts hold recorded step results so a retry can return them verbatim;
#: the cap keeps that memory small (a lost receipt degrades to "unknown, start
#: over", never to a wrong answer).
DEFAULT_CAPACITY = 8

#: Rendered labels for a timeout message. One word per receipt state.
_STEP_WORDS = {
    STATUS_OK: "ok",
    STATUS_ERROR: "error",
    STATUS_UNKNOWN: "unknown",
    STATUS_NOT_RUN: "not run",
}


class BatchIdConflict(ValueError):
    """The same ``batch_id`` was presented for a different command list."""


def new_batch_id() -> str:
    """A collision-resistant default id for a caller that did not choose one."""
    return "batch-" + uuid.uuid4().hex[:16]


def fingerprint_steps(commands: List[Any]) -> str:
    """Stable identity of a batch's command list (types and payloads).

    The id alone is not enough to resume a batch: a caller that reuses an id
    for a different command list would have unrelated steps skipped. Payloads
    arrive from JSON, so ``default=str`` is only a belt for exotic test input.
    """
    try:
        material = json.dumps(commands, sort_keys=True, default=str,
                              separators=(",", ":"))
    except (TypeError, ValueError):  # pragma: no cover - JSON payloads always encode
        material = repr(commands)
    return hashlib.sha256(material.encode("utf-8", "replace")).hexdigest()[:32]


class BatchReceipts:
    """One batch's per-step receipts. Every read and write is lock-guarded.

    Written by the payload on Houdini's main thread, read by the caller that
    timed out on its own thread -- or by a later retry, which the single main
    thread serializes behind the first payload, so it observes settled
    receipts rather than a half-written loop.
    """

    def __init__(self, batch_id: str, step_count: int, fingerprint: str):
        self.batch_id = batch_id
        self.step_count = int(step_count)
        self.fingerprint = fingerprint
        self.created = time.time()
        self._lock = threading.Lock()
        self._status: List[Any] = [None] * self.step_count
        self._results: List[Any] = [None] * self.step_count
        self._errors: List[Any] = [None] * self.step_count

    def status(self, index: int) -> str:
        with self._lock:
            return self._status[index] or STATUS_NOT_RUN

    def result(self, index: int) -> Any:
        with self._lock:
            return self._results[index]

    def error(self, index: int) -> Any:
        with self._lock:
            return self._errors[index]

    def begin(self, index: int) -> None:
        """The step is about to run. Anything not terminal from here on is unknown."""
        with self._lock:
            self._status[index] = STATUS_IN_PROGRESS

    def finish_ok(self, index: int, result: Any) -> None:
        with self._lock:
            self._status[index] = STATUS_OK
            self._results[index] = result

    def finish_error(self, index: int, message: str) -> None:
        with self._lock:
            self._status[index] = STATUS_ERROR
            self._errors[index] = message

    def finish_unknown(self, index: int, detail: str) -> None:
        """Settle a step whose outcome cannot be known (do not re-run it)."""
        with self._lock:
            self._status[index] = STATUS_UNKNOWN
            self._errors[index] = detail

    def settled(self) -> bool:
        """True when no step can still change state (eviction prefers these)."""
        with self._lock:
            return all(state is None or state in _TERMINAL or state == STATUS_UNKNOWN
                       for state in self._status)

    def snapshot(self) -> Dict[str, Any]:
        """Point-in-time receipt for a caller that stopped waiting.

        A step mid-flight is rendered ``unknown``: nothing says it failed and
        nothing says it finished. The live registry is left untouched -- the
        payload may still complete that step.
        """
        with self._lock:
            states = [state or STATUS_NOT_RUN for state in self._status]
        rendered = [STATUS_UNKNOWN if state == STATUS_IN_PROGRESS else state
                    for state in states]
        completed = [i for i, state in enumerate(rendered) if state == STATUS_OK]
        failed = [i for i, state in enumerate(rendered) if state == STATUS_ERROR]
        unknown = [i for i, state in enumerate(rendered) if state == STATUS_UNKNOWN]
        not_run = [i for i, state in enumerate(rendered) if state == STATUS_NOT_RUN]
        if unknown or not_run:
            overall = ("not_started" if not (completed or failed or unknown)
                       else "in_progress")
        else:
            overall = "complete"
        return {
            "batch_id": self.batch_id,
            "status": overall,
            "step_count": self.step_count,
            "steps": [{"index": i, "status": state}
                      for i, state in enumerate(rendered)],
            "completed_steps": completed,
            "failed_steps": failed,
            "unknown_steps": unknown,
            "not_run_steps": not_run,
        }


def step_summary(receipt: Dict[str, Any], max_steps: int = 12) -> str:
    """One-line ``0=ok, 1=unknown, 2=not run`` rendering of a snapshot."""
    steps = receipt.get("steps") if isinstance(receipt, dict) else None
    if not isinstance(steps, list) or not steps:
        return "(no steps)"
    parts = ["%d=%s" % (step.get("index"), _STEP_WORDS.get(step.get("status"),
                                                          step.get("status")))
             for step in steps[:max_steps]]
    if len(steps) > max_steps:
        parts.append("... %d more" % (len(steps) - max_steps))
    return ", ".join(parts)


class BatchReceiptStore:
    """Bounded, thread-safe map of batch id -> :class:`BatchReceipts`."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        self._capacity = max(1, int(capacity))
        self._lock = threading.Lock()
        self._batches: "OrderedDict[str, BatchReceipts]" = OrderedDict()

    def get_or_create(self, batch_id: str, commands: List[Any]) -> BatchReceipts:
        """Receipts for this id, creating them on the first attempt.

        Reusing an id with a different command list is refused rather than
        silently resuming: skipping a step from an unrelated batch would be a
        correctness bug wearing a convenience's clothes.
        """
        step_count = len(commands)
        fingerprint = fingerprint_steps(commands)
        with self._lock:
            existing = self._batches.get(batch_id)
            if existing is not None:
                if existing.step_count != step_count:
                    raise BatchIdConflict(
                        "batch_id %r was used for a batch of %d step(s); this "
                        "batch has %d. Use a new batch_id for a new batch."
                        % (batch_id, existing.step_count, step_count))
                if existing.fingerprint != fingerprint:
                    raise BatchIdConflict(
                        "batch_id %r was used for a different command list. "
                        "Use a new batch_id for a new batch." % (batch_id,))
                self._batches.move_to_end(batch_id)
                return existing
            receipts = BatchReceipts(batch_id, step_count, fingerprint)
            self._batches[batch_id] = receipts
            self._evict_locked()
            return receipts

    def get(self, batch_id: str) -> BatchReceipts | None:
        with self._lock:
            return self._batches.get(batch_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._batches)

    def _evict_locked(self) -> None:
        # Lock order is store -> receipts everywhere; the receipts never call
        # back into the store, so there is no inversion.
        while len(self._batches) > self._capacity:
            victim = next((batch_id for batch_id, receipts in self._batches.items()
                           if receipts.settled()), None)
            if victim is None:
                victim = next(iter(self._batches))
            del self._batches[victim]
