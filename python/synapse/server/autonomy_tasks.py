"""In-flight autonomous-render task registry (R-035 / CONDUCTOR-8).

Why this exists
---------------
``synapse_autonomous_render`` used to run the whole Plan -> Validate -> Execute
-> Evaluate -> Report loop INSIDE the tool call. The canonical client budget for
that command is 600 s (``core/timeouts.py``), but the handler could hold the
caller for that budget PLUS an extra 60 s waiting on an event-loop future --
so the client reported a timeout while the render kept running, and a retry
with the same intent started a SECOND loop beside the first.

The repair mirrors the live TOP-cook task pattern
(``server/handlers_tops/cook.py``): the tool call returns a task id
immediately, the loop runs on a worker thread, and later calls poll
``{"task_id": ...}`` for the terminal state. A second start whose intent
resolves to the same plan (and the same run parameters) is JOINED to the
in-flight task instead of starting a duplicate.

This module is pure Python -- no ``hou``, no autonomy import -- so it is
importable standalone (and by the handler tests) with Houdini absent.
Every mutation is lock-guarded: the start/poll calls arrive on the handler
thread while completion is written by the render worker.

Bounded: finished tasks beyond ``max_finished`` are evicted oldest-first;
a running task is never evicted (its poll id must stay valid until it
finishes). A task that has been "running" past ``stale_after_s`` is not
joinable -- a dead worker must not capture every later start for this plan.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"

_ACTIVE = frozenset({STATUS_RUNNING})

#: Terminal tasks kept for later polls. A lost receipt degrades to "unknown
#: task id", never to a wrong answer.
DEFAULT_MAX_FINISHED = 16

#: A running record older than this is treated as abandoned for JOIN purposes
#: (a new start proceeds). The record itself is kept so a later poll still
#: answers honestly.
DEFAULT_STALE_AFTER_S = 6 * 3600.0


def fingerprint(intent: str, steps: Optional[List[Any]] = None,
                params: Optional[Dict[str, Any]] = None) -> str:
    """Stable identity of one autonomous run: intent + plan + run parameters.

    The plan is a pure function of the intent in the live wiring, but it is
    included explicitly because the predicate is "same intent and plan": a
    future planner that consults scene context must not let two different
    plans share a task. Run parameters are included because joining a run
    configured with a different quality threshold or wall-clock budget would
    silently ignore the caller's settings.

    Payloads arrive from JSON; ``default=str`` is a belt for exotic test input.
    """
    material = json.dumps(
        {"intent": intent, "steps": steps or [], "params": params or {}},
        sort_keys=True, default=str, separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8", "replace")).hexdigest()[:32]


class AutonomyTaskStore:
    """Bounded, thread-safe map of task id -> autonomous-render task record."""

    def __init__(self, max_finished: int = DEFAULT_MAX_FINISHED,
                 stale_after_s: float = DEFAULT_STALE_AFTER_S):
        self._max_finished = max(1, int(max_finished))
        self._stale_after_s = float(stale_after_s)
        self._lock = threading.Lock()
        self._tasks: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_or_join(self, key: str, intent: str,
                      meta: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], bool]:
        """Create a task for ``key`` or join the live one.

        Returns ``(record, joined)``. ``record`` is the LIVE dict (internal
        callers may read ``completion``); ``joined`` is True when an existing
        in-flight task for the same key was returned and no new run started.
        The join check and the create happen under one lock, so two callers
        cannot both miss each other and start duplicates.
        """
        now = time.time()
        with self._lock:
            existing = self._active_for_key_locked(key, now)
            if existing is not None:
                existing["joined_calls"] += 1
                return existing, True
            task_id = "autorender-" + uuid.uuid4().hex[:12]
            record: Dict[str, Any] = {
                "task_id": task_id,
                "key": key,
                "intent": intent,
                "status": STATUS_RUNNING,
                "meta": dict(meta or {}),
                "started_at": now,
                "finished_at": None,
                "result": None,
                "success": None,
                "stop_reason": "",
                "error": None,
                "error_type": None,
                "joined_calls": 0,
                "completion": threading.Event(),
            }
            self._tasks[task_id] = record
            self._prune_locked()
            return record, False

    def complete(self, task_id: str, result: Any, *, success: bool,
                 stop_reason: str = "") -> Optional[Dict[str, Any]]:
        """Record a finished run and wake every waiter."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            record["status"] = STATUS_DONE
            record["result"] = result
            record["success"] = bool(success)
            record["stop_reason"] = str(stop_reason or "")
            record["finished_at"] = time.time()
            record["completion"].set()
            return record

    def fail(self, task_id: str, error: str,
             error_type: str = "Exception") -> Optional[Dict[str, Any]]:
        """Record a crashed run. Only the message and type NAME are kept --
        the exception object would pin its traceback in the registry until
        eviction."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            record["status"] = STATUS_ERROR
            record["error"] = str(error)
            record["error_type"] = str(error_type)
            record["finished_at"] = time.time()
            record["completion"].set()
            return record

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """The LIVE record (internal callers may wait on ``completion``)."""
        with self._lock:
            return self._tasks.get(task_id)

    def wait(self, task_id: str, timeout: Optional[float] = None) -> bool:
        """Wait for a task to finish. Returns True when it is terminal.

        ``timeout=None`` waits forever; expiry returns False without changing
        the record. Used by tests and available to any future bounded caller.
        """
        record = self.get(task_id)
        if record is None:
            return False
        return bool(record["completion"].wait(timeout))

    def public(self, task_id: str) -> Optional[Dict[str, Any]]:
        """JSON-safe, point-in-time receipt for a poll response."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            return self._receipt_locked(record)

    def __len__(self) -> int:
        with self._lock:
            return len(self._tasks)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _receipt_locked(self, record: Dict[str, Any]) -> Dict[str, Any]:
        ended = record["finished_at"] or time.time()
        receipt: Dict[str, Any] = {
            "task_id": record["task_id"],
            "status": record["status"],
            "intent": record["intent"],
            "started_at": record["started_at"],
            "finished_at": record["finished_at"],
            "elapsed_s": round(ended - record["started_at"], 2),
            "joined_calls": record["joined_calls"],
            "meta": dict(record["meta"]),
        }
        if record["status"] == STATUS_DONE:
            receipt["success"] = record["success"]
            receipt["stop_reason"] = record["stop_reason"]
            receipt["result"] = record["result"]
        elif record["status"] == STATUS_ERROR:
            receipt["error"] = record["error"]
            receipt["error_type"] = record["error_type"]
        else:
            receipt["note"] = (
                "Autonomous render still running on its worker thread -- this "
                "is not a failure. Poll synapse_autonomous_render with "
                '{"task_id": "%s"} for the final report.' % record["task_id"]
            )
        return receipt

    def _active_for_key_locked(self, key: str, now: float) -> Optional[Dict[str, Any]]:
        for record in self._tasks.values():
            if record["key"] != key:
                continue
            if record["status"] not in _ACTIVE:
                continue
            if now - record["started_at"] > self._stale_after_s:
                continue  # abandoned worker: let a fresh start proceed
            return record
        return None

    def _prune_locked(self) -> None:
        finished = [tid for tid, rec in self._tasks.items()
                    if rec["status"] not in _ACTIVE]
        excess = len(finished) - self._max_finished
        for tid in finished[:max(0, excess)]:
            self._tasks.pop(tid, None)

    def reset(self) -> None:
        """Drop every record. Tests only -- the server never calls this."""
        with self._lock:
            self._tasks.clear()
