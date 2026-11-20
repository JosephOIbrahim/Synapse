"""
Synapse TOPS/PDG Handler Mixin -- Cook

Auto-extracted from the monolith handlers_tops.py.
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ...core.aliases import resolve_param, resolve_param_with_default
from ...core.determinism import round_float, kahan_sum, deterministic_uuid
from ..handler_helpers import _HOUDINI_UNAVAILABLE
from ._common import logger, _run_in_main_thread_pdg, _ensure_tops_warm_standby, _MAX_MONITOR_EVENTS


# =========================================================================
# CONDUCTOR-1 / CONDUCTOR-6 — non-blocking cook tasks
# =========================================================================
#
# The pre-repair handler called cookWorkItems(block=True) INSIDE the
# run_on_main payload. That parked Houdini's main thread for the whole cook,
# so the 60s PDG marshal budget expired on any real cook, the caller got a
# FALSE failure (the payload had already started and could not be abandoned),
# and tops_cancel_cook — itself a main-thread marshal — could not reach the
# blocked thread. A late cancel then dirtied a finished node.
#
# The repair is deliberately minimal and honest:
#   * the cook is kicked with cookWorkItems(block=False); the payload returns
#     a task id in milliseconds,
#   * a pdg.Node event handler records the terminal CookComplete / CookError
#     state (events fire on a PDG worker thread — threading.Event, never
#     asyncio.Event),
#   * polling re-reads hou.TopNode.getCookState() + pdg work-item states, so a
#     missed event still resolves,
#   * blocking=True waits OFF the main thread, bounded; expiry returns the
#     still-cooking receipt instead of a failure.
#
# A full async job daemon (separate process, durable queue) is out of scope
# for this node; this in-process task registry is the smallest model that
# keeps the predicate true across the WS command boundary.

# Default bound for an explicit blocking=True wait (seconds). Under the old
# 60s PDG marshal budget that used to false-fail, and well under the 120s
# transport budget (core/timeouts.py: tops_cook_node). Expiry is NOT a
# failure — the cook keeps running and the task id stays pollable.
_DEFAULT_BLOCKING_WAIT_S = 45.0

# How long the cancel branch waits for Houdini's main thread before falling
# back to the pdg-only handle captured at cook start (CONDUCTOR-6: a legacy
# blocking cook must not make cancel unreachable).
_CANCEL_MARSHAL_TIMEOUT_S = 10.0

_ACTIVE_TASK_STATES = ("started", "cooking", "cancelling")

# Work-item states a cancel can still act on (Cooking is the documented
# pdg.WorkItem.cancel target; Scheduled/Waiting are pending and node-level
# cancel can stop them before they start).
_ACTIVE_WORK_ITEM_STATES = ("Cooking", "Scheduled", "Waiting")

# hou.topCookState member -> terminal task status. Warning counts as cooked
# (the items finished; warnings are not cook failures).
_TERMINAL_COOK_STATES = {
    "Cooked": "cooked",
    "Warning": "cooked",
    "Failed": "failed",
}

_tops_cook_tasks_lock = threading.Lock()


def _on_main_thread() -> bool:
    """True when the caller is Houdini's main thread (same check run_on_main uses)."""
    return threading.current_thread().ident == threading.main_thread().ident


def _state_name(state) -> Optional[str]:
    """Read an enum-member name from a pdg / hou state value, defensively.

    H22 pybind enums and hou.topCookState both expose ``.name``. A plain
    string (the fake graphs in tests use one) passes through unchanged.
    """
    if state is None:
        return None
    name = getattr(state, "name", None)
    if isinstance(name, str):
        return name
    text = str(state)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    # A non-enum object (e.g. a MagicMock in a fake scene) must not be
    # reported as a cook state.
    if not text or text.startswith("<"):
        return None
    return text


def _cook_state_name(node) -> Optional[str]:
    """node.getCookState() as a member name; None when unreadable/absent."""
    get_state = getattr(node, "getCookState", None)
    if not callable(get_state):
        return None
    # H22 TopNode.getCookState() requires a force argument (live receipt,
    # 2026-11-20); older hosts and the fake nodes in tests take none. Try
    # the documented signature first, fall back rather than losing the
    # readback silently.
    try:
        try:
            return _state_name(get_state(True))
        except TypeError:
            return _state_name(get_state())
    except Exception as exc:
        logger.debug("could not read TOP cook state: %r", exc)
        return None


def _work_item_state_counts(pdg_node) -> Dict[str, int]:
    """Count work items by state name. Reads pdg.* only — safe off the main thread."""
    counts: Dict[str, int] = {}
    try:
        items = list(getattr(pdg_node, "workItems", []) or [])
    except Exception as exc:
        logger.debug("could not read PDG work items: %r", exc)
        return counts
    for wi in items:
        try:
            name = _state_name(wi.state) or "unknown"
        except Exception as exc:
            logger.debug("could not read a PDG work-item state: %r", exc)
            name = "unknown"
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _task_receipt(record: Optional[Dict]) -> Optional[Dict]:
    """Public, JSON-safe view of one task record (private keys never leave)."""
    if record is None:
        return None
    status = record["status"]
    if status == "started":
        status = "cooking"
    elif status == "cancelling":
        status = "cancel_requested"
    return {
        "node": record["node"],
        "status": status,
        "task_id": record["task_id"],
        "work_items": record["work_items"],
        "cook_state": record["cook_state"],
        "event": record["event"],
        "error": record["error"],
        "event_bridge": record["event_bridge"],
        "cancel_requested": record["cancel_requested"],
        "cancel_api": record["cancel_api"],
        "readback": record["readback"],
        "started_at": record["started_at"],
        "finished_at": record["finished_at"],
    }


class _CookTaskRegistry:
    """Bounded, thread-safe task records for in-flight PDG cooks.

    One registry lives on the SynapseHandler for the life of the server, so a
    task id returned by tops_cook_node can be polled and cancelled by later
    commands. Completion is written by the PDG event callback (worker thread)
    and by state readback on poll/cancel — every mutation is under ``_lock``.
    """

    _MAX_FINISHED = 64
    _STALE_AFTER_S = 6 * 3600.0

    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: "OrderedDict[str, Dict]" = OrderedDict()

    def create(self, node_path: str) -> Dict:
        task_id = "cook-" + deterministic_uuid(
            f"cook_task:{node_path}:{time.time_ns()}"
        )[:12]
        record = {
            "task_id": task_id,
            "node": node_path,
            "status": "started",
            "event": None,
            "error": None,
            "cook_state": None,
            "work_items": None,
            "readback": None,
            "event_bridge": False,
            "cancel_requested": False,
            "cancel_api": None,
            "started_at": time.time(),
            "finished_at": None,
            "completion": threading.Event(),
            "_handlers": [],
            "_callback": None,
            "_pdg_node": None,
        }
        with self._lock:
            self._tasks[task_id] = record
            self._prune_locked()
        return record

    def get(self, task_id: str) -> Optional[Dict]:
        """The LIVE record (internal callers may wait on ``completion``)."""
        with self._lock:
            return self._tasks.get(task_id)

    def active_for_node(self, node_path: str) -> Optional[Dict]:
        now = time.time()
        with self._lock:
            for record in self._tasks.values():
                if record["node"] != node_path:
                    continue
                if record["status"] not in _ACTIVE_TASK_STATES:
                    continue
                if now - record["started_at"] > self._STALE_AFTER_S:
                    continue
                return record
            return None

    def update(self, task_id: str, **fields) -> Optional[Dict]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            record.update(fields)
            return record

    def finish(self, task_id: str, status: str, *, event=None, error=None,
               cook_state=None, work_items=None, force: bool = False) -> Optional[Dict]:
        """Record a terminal state and wake any blocking waiter.

        A cancel outcome owns the status (``cancel_requested``) unless
        ``force`` is set — a late cook event must not relabel a cancel that
        was already confirmed by readback.
        """
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            if event:
                record["event"] = event
            if error is not None:
                record["error"] = error
            if cook_state is not None:
                record["cook_state"] = cook_state
            if work_items is not None:
                record["work_items"] = work_items
            if force or not record["cancel_requested"]:
                record["status"] = status
                record["finished_at"] = time.time()
            record["completion"].set()
            return record

    def mark_cancel(self, task_id: str, status: str, *, cancel_api=None,
                    readback=None) -> Optional[Dict]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return None
            record["cancel_requested"] = True
            if cancel_api is not None:
                record["cancel_api"] = cancel_api
            if readback is not None:
                record["readback"] = readback
            record["status"] = status
            if status == "cancelled":
                record["finished_at"] = time.time()
            record["completion"].set()
            return record

    def attach_handlers(self, task_id: str, registrations, callback) -> bool:
        """Record (emitter, wrapper) pairs and keep the callback alive."""
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return False
            record["_handlers"] = list(registrations)
            record["_callback"] = callback  # strong ref: PDG holds only the wrapper
            record["event_bridge"] = True
            return True

    def take_handlers(self, task_id: str):
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return []
            handlers = list(record["_handlers"])
            record["_handlers"] = []
            return handlers

    def public(self, task_id: str) -> Optional[Dict]:
        with self._lock:
            record = self._tasks.get(task_id)
            return _task_receipt(record) if record is not None else None

    def _prune_locked(self) -> None:
        finished = [tid for tid, rec in self._tasks.items()
                    if rec["status"] not in _ACTIVE_TASK_STATES]
        excess = len(finished) - self._MAX_FINISHED
        for tid in finished[:max(0, excess)]:
            self._tasks.pop(tid, None)

    def reset(self) -> None:
        """Drop every record. Tests only — the server never calls this."""
        with self._lock:
            self._tasks.clear()


def _detach_task_handlers(registry: "_CookTaskRegistry", task_id: str) -> None:
    """Remove the task's PDG event handlers (idempotent; safe off the main thread)."""
    registrations = registry.take_handlers(task_id)
    for emitter, wrapper in registrations:
        remove = getattr(emitter, "removeEventHandler", None)
        if not callable(remove):
            continue
        try:
            remove(wrapper)
        except Exception as exc:
            logger.info("cook task %s: event-handler teardown failed: %r", task_id, exc)


def _register_cook_events(registry: "_CookTaskRegistry", task: Dict,
                          pdg_node, graph_context) -> bool:
    """Register CookComplete/CookError handlers for one cook task.

    Two scopes are registered when available:
      * the node's own EventEmitter (pdg.Node.addEventHandler) — precise, no
        sibling cook can trip it;
      * the graph context (the R8 pattern) — the proven backstop if a build
        does not emit cook events at node scope.
    The callback ignores a cook-level event while THIS node still has active
    work items, so a sibling node's CookComplete/CookError cannot finish (or
    fail) our task. Polling re-reads hou.TopNode.getCookState(), so a missed
    event still resolves.
    """
    task_id = task["task_id"]
    try:
        import pdg as _pdg
    except ImportError:
        logger.info(
            "pdg module unavailable — cook task %s will finish by state readback",
            task_id,
        )
        return False

    event_type = getattr(_pdg, "EventType", None)
    complete = getattr(event_type, "CookComplete", None)
    error = getattr(event_type, "CookError", None)
    if complete is None or error is None:
        logger.info(
            "pdg.EventType lacks cook events — cook task %s will finish by "
            "state readback", task_id,
        )
        return False

    def _node_still_active() -> bool:
        # pdg.* reads only — safe on the worker thread that fires the event.
        counts = _work_item_state_counts(pdg_node)
        return any(counts.get(state, 0) for state in _ACTIVE_WORK_ITEM_STATES)

    def on_cook_event(event) -> None:
        # PDG fires events on a worker thread. pdg.* reads only; the registry
        # is lock-guarded. threading.Event (never asyncio.Event) wakes waiters.
        try:
            etype = getattr(event, "type", None)
        except Exception as exc:
            logger.debug("cook task %s: unreadable event type: %r", task_id, exc)
            return
        if etype == complete:
            if _node_still_active():
                return  # a sibling cook completed; this node is still working
            registry.finish(task_id, "cooked", event="CookComplete")
        elif etype == error:
            if _node_still_active():
                return  # a sibling node failed; this cook has not finished
            message = getattr(event, "message", None)
            registry.finish(task_id, "failed", event="CookError",
                            error=str(message) if message else "")
        else:
            return
        _detach_task_handlers(registry, task_id)

    registrations = []
    seen = []
    for emitter in (pdg_node, graph_context):
        if emitter is None or any(emitter is prior for prior in seen):
            continue
        seen.append(emitter)
        add = getattr(emitter, "addEventHandler", None)
        if not callable(add):
            continue
        try:
            registrations.append((emitter, add(on_cook_event, complete)))
            registrations.append((emitter, add(on_cook_event, error)))
        except Exception as exc:
            logger.warning(
                "PDG event registration failed on %s for task %s: %r",
                task["node"], task_id, exc,
            )
            # Roll back only what this emitter accepted.
            remove = getattr(emitter, "removeEventHandler", None)
            for prior_emitter, wrapper in registrations:
                if prior_emitter is not emitter:
                    continue
                try:
                    if callable(remove):
                        remove(wrapper)
                except Exception as teardown_exc:
                    logger.info(
                        "cook task %s: partial handler rollback failed: %r",
                        task_id, teardown_exc,
                    )
            registrations = [reg for reg in registrations if reg[0] is not emitter]

    if not registrations:
        return False
    return registry.attach_handlers(task_id, registrations, on_cook_event)


def _read_node_cook_state(node_path: str) -> Dict:
    """Read a TOP node's cook state/readback ON the main thread."""
    node = hou.node(node_path)
    if node is None:
        return {"found": False}
    pdg_node = node.getPDGNode()
    work_items = None
    readback: Dict[str, int] = {}
    if pdg_node is not None:
        try:
            work_items = len(pdg_node.workItems)
        except Exception as exc:
            logger.debug("could not count work items on %s: %r", node_path, exc)
        readback = _work_item_state_counts(pdg_node)
    return {
        "found": True,
        "cook_state": _cook_state_name(node),
        "work_items": work_items,
        "readback": readback,
    }


def _reconcile_task(registry: "_CookTaskRegistry", record: Dict, fresh: Dict) -> None:
    """Promote a non-terminal task to its read-back terminal state."""
    if not fresh.get("found"):
        return
    state = fresh.get("cook_state")
    mapped = _TERMINAL_COOK_STATES.get(state)
    if mapped is None:
        return
    status = record["status"]
    if status in ("started", "cooking"):
        registry.finish(record["task_id"], mapped, event="state_readback",
                        cook_state=state, work_items=fresh.get("work_items"))
        _detach_task_handlers(registry, record["task_id"])
    elif status == "cancelling":
        # The cook ended after a cancel request: record what actually ended.
        registry.finish(record["task_id"], mapped, event="state_readback",
                        cook_state=state, work_items=fresh.get("work_items"),
                        force=True)
        _detach_task_handlers(registry, record["task_id"])
    elif record.get("cook_state") is None:
        registry.update(record["task_id"], cook_state=state,
                        work_items=fresh.get("work_items"))


def _await_tops_cook_task(registry: "_CookTaskRegistry", task_id: str,
                          timeout) -> Dict:
    """Wait OFF the main thread for a task's completion event, bounded.

    Expiry returns the still-cooking receipt with ``wait_timed_out: true`` —
    never a failure. The cook keeps running and the task id remains pollable.
    """
    record = registry.get(task_id)
    if record is None:
        return {"task_id": task_id, "status": "unknown_task"}
    try:
        wait_s = max(0.0, float(timeout))
    except (TypeError, ValueError):
        wait_s = _DEFAULT_BLOCKING_WAIT_S
    finished = record["completion"].wait(timeout=wait_s)
    receipt = registry.public(task_id) or {"task_id": task_id, "status": "unknown_task"}
    receipt["wait_timed_out"] = not finished
    if not finished:
        receipt["note"] = (
            f"Cook is still running after {wait_s:.1f}s — this is not a failure. "
            f"Poll tops_cook_node with task_id '{task_id}' for the final state, "
            "or tops_cancel_cook to stop it."
        )
    return receipt


def _start_tops_cook(registry: "_CookTaskRegistry", node_path: str,
                     generate_only: bool) -> Dict:
    """Kick a non-blocking cook and return its task receipt (main thread)."""
    node = hou.node(node_path)
    if node is None:
        raise ValueError(
            f"Couldn't find a node at {node_path} -- "
            "double-check the path exists"
        )

    # Verify it has a PDG node
    pdg_node = node.getPDGNode()
    if pdg_node is None:
        raise ValueError(
            f"The node at {node_path} isn't a TOP node or hasn't been "
            "set up for PDG yet -- make sure it's inside a TOP network"
        )

    if generate_only:
        node.generateStaticItems()
        item_count = len(pdg_node.workItems)
        return {
            "node": node_path,
            "status": "generated",
            "work_items": item_count,
        }

    # One in-flight cook per node: a second kick would either be refused by
    # PDG or start a duplicate cook. Reconcile first — an event can be missed,
    # and a finished node must not keep a task marked in-flight.
    existing = registry.active_for_node(node_path)
    if existing is not None:
        fresh_state = _cook_state_name(node)
        mapped = _TERMINAL_COOK_STATES.get(fresh_state)
        if mapped is not None:
            try:
                item_count = len(pdg_node.workItems)
            except Exception as exc:
                logger.debug("could not count work items on %s: %r", node_path, exc)
                item_count = None
            registry.finish(existing["task_id"], mapped, event="state_readback",
                            cook_state=fresh_state, work_items=item_count)
            _detach_task_handlers(registry, existing["task_id"])
            existing = None
    if existing is not None:
        receipt = _task_receipt(existing) or {"node": node_path}
        receipt["reused"] = True
        receipt["note"] = (
            "A cook for this node is already in flight — returning its task id "
            "instead of starting a second cook."
        )
        return receipt

    task = registry.create(node_path)
    task_id = task["task_id"]
    registry.update(task_id, _pdg_node=pdg_node)

    graph_context = None
    get_context = getattr(node, "getPDGGraphContext", None)
    if callable(get_context):
        try:
            graph_context = get_context()
        except Exception as exc:
            logger.debug("could not read PDG graph context on %s: %r", node_path, exc)
    _register_cook_events(registry, task, pdg_node, graph_context)

    try:
        # Non-blocking by contract: cookWorkItems' documented default is
        # block=False; the cook runs on PDG's scheduler and returns at once.
        # (executeGraph() would do the same kick but is documented-deprecated
        # on 22.0.368 in favour of cookWorkItems — H5-F7.)
        node.cookWorkItems(block=False)
    except Exception as e:
        logger.error("PDG cook kick failed for %s: %s", node_path, e)
        item_count = len(pdg_node.workItems) if pdg_node else 0
        state = _cook_state_name(node)
        registry.finish(task_id, "failed", event="kick_error", error=str(e),
                        cook_state=state, work_items=item_count)
        _detach_task_handlers(registry, task_id)
        return {
            "node": node_path,
            "status": "error",
            "task_id": task_id,
            "work_items": item_count,
            "error": str(e),
        }

    if not task["event_bridge"] and graph_context is None:
        # getPDGGraphContext() can be None before the first cook. Try once more
        # now that the graph exists; a fast completion is covered by the
        # readback below and by polling.
        late_context = None
        if callable(get_context):
            try:
                late_context = get_context()
            except Exception as exc:
                logger.debug(
                    "could not re-read PDG graph context on %s: %r", node_path, exc)
        if late_context is not None:
            _register_cook_events(registry, task, pdg_node, late_context)

    state = _cook_state_name(node)
    try:
        item_count = len(pdg_node.workItems)
    except Exception as exc:
        logger.debug("could not count work items on %s: %r", node_path, exc)
        item_count = None
    registry.update(task_id, cook_state=state, work_items=item_count,
                    readback=_work_item_state_counts(pdg_node))

    mapped = _TERMINAL_COOK_STATES.get(state)
    if mapped is not None:
        # The cook already finished (tiny graph / everything cached): report
        # the read-back terminal state instead of a stale "cooking".
        registry.finish(task_id, mapped, event="state_readback",
                        cook_state=state, work_items=item_count)
        _detach_task_handlers(registry, task_id)

    receipt = registry.public(task_id) or {"node": node_path, "task_id": task_id}
    receipt["reused"] = False
    if receipt.get("status") == "cooking":
        receipt["note"] = (
            "Cook started non-blocking — Houdini's main thread is free. "
            f"Poll tops_cook_node with task_id '{task_id}' for the final state, "
            "or tops_cancel_cook to stop it."
        )
    return receipt


def _cancel_pdg_node(pdg_node, node_path: str) -> Dict:
    """Cancel a single TOP node through the PDG cancel path (CONDUCTOR-6).

    NEVER dirties: dirty() deletes a node's work items, which destroys a
    finished node's results and does not stop a running cook. The reply says
    "cancelled" only after reading the work-item states back; when no cancel
    API reaches the node it is an explicit cannot-cancel receipt.
    """
    try:
        items = list(getattr(pdg_node, "workItems", []) or [])
    except Exception as exc:
        logger.warning("could not list work items on %s: %s", node_path, exc)
        items = []
    before = _work_item_state_counts(pdg_node)

    active = []
    for wi in items:
        try:
            if _state_name(wi.state) in _ACTIVE_WORK_ITEM_STATES:
                active.append(wi)
        except Exception as exc:
            logger.debug("could not read a work-item state on %s: %r", node_path, exc)

    if not items:
        return {
            "node": node_path,
            "status": "cannot_cancel",
            "reason": "the node has no work items — there is nothing to cancel",
            "readback": before,
        }
    if not active:
        return {
            "node": node_path,
            "status": "not_cooking",
            "reason": (
                "no work items are cooking, scheduled or waiting — nothing was "
                "changed (a finished node is never dirtied by a cancel)"
            ),
            "readback": before,
        }

    errors: List[str] = []
    cancel_api = None

    # pdg.Node.cancel exists in the H22 symbol table; its exact arity is not
    # probed, so a call failure falls through to the per-item verb below.
    node_cancel = getattr(pdg_node, "cancel", None)
    if callable(node_cancel):
        try:
            node_cancel()
            cancel_api = "pdg.Node.cancel"
        except Exception as exc:
            errors.append(f"pdg.Node.cancel: {exc}")
            logger.warning("pdg.Node.cancel failed on %s: %s", node_path, exc)

    if cancel_api is None:
        for wi in active:
            # pdg.WorkItem.cancel's documented scope is "if it is cooking".
            try:
                if _state_name(wi.state) != "Cooking":
                    continue
            except Exception as exc:
                logger.debug("could not re-read a work-item state on %s: %r",
                             node_path, exc)
                continue
            item_cancel = getattr(wi, "cancel", None)
            if not callable(item_cancel):
                continue
            try:
                item_cancel()
                cancel_api = "pdg.WorkItem.cancel"
            except Exception as exc:
                errors.append(f"pdg.WorkItem.cancel: {exc}")
                logger.warning("pdg.WorkItem.cancel failed on %s: %s", node_path, exc)
    if cancel_api is None:
        return {
            "node": node_path,
            "status": "cannot_cancel",
            "reason": (
                "no PDG cancel API could reach this node — nothing was changed"
            ),
            "errors": errors,
            "readback": before,
        }

    # READBACK — status "cancelled" is only claimed after the second read.
    after = _work_item_state_counts(pdg_node)
    still_cooking = int(after.get("Cooking", 0))
    still_active = sum(int(after.get(state, 0)) for state in _ACTIVE_WORK_ITEM_STATES)
    status = "cancelled" if still_active == 0 else "cancel_requested"
    note = (
        "Cancel confirmed by readback — no work items remain cooking, "
        "scheduled or waiting."
        if status == "cancelled" else
        f"{still_active} work item(s) are still active after the cancel "
        f"signal ({still_cooking} cooking) — they may stop shortly. "
        "This is not a failure."
    )
    return {
        "node": node_path,
        "status": status,
        "cancel_api": cancel_api,
        "readback": after,
        "cooking_remaining": still_cooking,
        "active_remaining": still_active,
        "note": note,
    }


def _cancel_tops_cook(node_path: str) -> Dict:
    """Cancel a cook on the main thread. TopNet uses the graph-context verb."""
    node = hou.node(node_path)
    if node is None:
        raise ValueError(
            f"Couldn't find a node at {node_path} -- "
            "double-check the path exists"
        )

    cat = node.type().category().name()
    if cat == "TopNet":
        ctx = node.getPDGGraphContext()
        if ctx is None:
            return {
                "node": node_path,
                "status": "cannot_cancel",
                "reason": "no PDG graph context on this TOP network — nothing to cancel",
            }
        cancel = getattr(ctx, "cancelCook", None)
        if not callable(cancel):
            return {
                "node": node_path,
                "status": "cannot_cancel",
                "reason": "this graph context has no cancelCook() — nothing was changed",
            }
        try:
            cancel()
        except Exception as exc:
            logger.warning("TopNet cancelCook failed on %s: %s", node_path, exc)
            return {
                "node": node_path,
                "status": "cannot_cancel",
                "cancel_api": "pdg.GraphContext.cancelCook",
                "reason": str(exc),
            }
        return {
            "node": node_path,
            "status": "cancelled",
            "cancel_api": "pdg.GraphContext.cancelCook",
            "cook_state": _cook_state_name(node),
            "note": (
                "We've sent the cancel signal -- items already in progress "
                "may finish up before stopping completely."
            ),
        }

    pdg_node = node.getPDGNode()
    if pdg_node is None:
        raise ValueError(
            f"The node at {node_path} isn't a TOP node or hasn't been "
            "set up for PDG yet -- make sure it's inside a TOP network"
        )
    result = _cancel_pdg_node(pdg_node, node_path)
    # CONDUCTOR-6: the node-level cook state is read back after the cancel too,
    # beside the per-work-item readback the status decision is based on.
    state = _cook_state_name(node)
    if state is not None:
        result["cook_state"] = state
    return result


def _cancel_without_marshal(record: Optional[Dict], node_path: str) -> Dict:
    """Cancel from the pdg-only handle when the main thread cannot be reached."""
    pdg_node = record.get("_pdg_node") if record else None
    if pdg_node is None:
        return {
            "node": node_path,
            "status": "cannot_cancel",
            "reason": (
                "Houdini's main thread is busy and no PDG handle was registered "
                "for this cook — cancel could not reach the node."
            ),
        }
    return _cancel_pdg_node(pdg_node, node_path)


def _apply_cancel_outcome(registry: "_CookTaskRegistry", record: Dict,
                          result: Dict) -> None:
    """Fold a cancel receipt back into the task record."""
    task_id = record["task_id"]
    status = result.get("status")
    if status == "cancelled":
        registry.mark_cancel(task_id, "cancelled",
                             cancel_api=result.get("cancel_api"),
                             readback=result.get("readback"))
        _detach_task_handlers(registry, task_id)
    elif status == "cancel_requested":
        registry.mark_cancel(task_id, "cancelling",
                             cancel_api=result.get("cancel_api"),
                             readback=result.get("readback"))
    else:
        registry.update(task_id, readback=result.get("readback"),
                        cancel_api=result.get("cancel_api"))


class TopsCookMixin:
    """Mixin providing TOPS/PDG cook handlers."""

    def _cook_task_registry(self) -> "_CookTaskRegistry":
        """The server's cook-task registry (lazy, thread-safe)."""
        registry = getattr(self, "_tops_cook_tasks", None)
        if registry is None:
            with _tops_cook_tasks_lock:
                registry = getattr(self, "_tops_cook_tasks", None)
                if registry is None:
                    registry = _CookTaskRegistry()
                    self._tops_cook_tasks = registry
        return registry

    def _poll_tops_cook_task(self, task_id: str) -> Dict:
        """Poll one cook task; a fresh readback can finish it when events miss."""
        registry = self._cook_task_registry()
        record = registry.get(task_id)
        if record is None:
            raise ValueError(
                f"No cook task '{task_id}' is on record — it may have been "
                "pruned. Use tops_get_cook_stats on the node for its current state."
            )
        if record["status"] in _ACTIVE_TASK_STATES and HOU_AVAILABLE:
            fresh = None
            try:
                fresh = _run_in_main_thread_pdg(
                    lambda: _read_node_cook_state(record["node"]), timeout=10.0)
            except Exception as exc:
                logger.info(
                    "cook task %s: state poll could not reach the main thread: %r",
                    task_id, exc,
                )
            if fresh:
                _reconcile_task(registry, record, fresh)
        return registry.public(task_id) or {"task_id": task_id, "status": "unknown_task"}

    def _handle_tops_cook_node(self, payload: Dict) -> Dict:
        """Cook a TOP node, optionally generating work items only.

        CONDUCTOR-1: non-blocking by default. The cook is kicked with
        cookWorkItems(block=False), a PDG completion handler is registered on
        the node, and a task id is returned immediately — Houdini's main
        thread (and the UI) stays free while the cook runs.

        Poll with {"task_id": ...}. blocking=True waits for completion OFF the
        main thread, bounded by blocking_timeout; if the bound expires the
        reply is a still-cooking receipt, never a false failure.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval  # noqa: F401  (dual-mode guard kept for parity)

        task_id = resolve_param(payload, "task_id", required=False)
        node_path = resolve_param(payload, "node", required=False)

        if node_path is None and task_id is not None:
            return self._poll_tops_cook_task(str(task_id))
        if node_path is None:
            raise ValueError(
                "Missing required parameter. Expected 'node' (or 'task_id' to "
                "poll a cook started earlier).\n"
                "HINT: Common names are 'node' or 'node_path'"
            )

        generate_only = resolve_param_with_default(payload, "generate_only", False)
        blocking = resolve_param_with_default(payload, "blocking", False)
        blocking_timeout = resolve_param_with_default(
            payload, "blocking_timeout", _DEFAULT_BLOCKING_WAIT_S)
        top_down = resolve_param_with_default(payload, "top_down", True)  # noqa: F841

        registry = self._cook_task_registry()
        result = _run_in_main_thread_pdg(
            lambda: _start_tops_cook(registry, node_path, bool(generate_only))
        )

        if (
            blocking
            and result.get("task_id")
            and result.get("status") in ("cooking", "started")
        ):
            if _on_main_thread():
                # Waiting here would park the Qt event loop — the exact defect
                # this node repairs. Leave the cook running; the task id poll
                # is the honest way to follow it.
                result["wait_skipped"] = "main_thread"
                result["note"] = (
                    "blocking=True was requested from Houdini's main thread — "
                    "waiting here would freeze the UI, so the cook was left "
                    f"running. Poll tops_cook_node with task_id '{result['task_id']}'."
                )
            else:
                result = _await_tops_cook_task(
                    registry, result["task_id"], blocking_timeout)
        return result


    def _handle_tops_generate_items(self, payload: Dict) -> Dict:
        """Generate work items for a TOP node without cooking.

        Creates static work items based on the node's configuration.
        Useful for previewing what a node will produce before cooking.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            node.generateStaticItems()
            item_count = len(pdg_node.workItems)
            return {
                "node": node_path,
                "status": "generated",
                "item_count": item_count,
            }

        return _run_in_main_thread_pdg(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 2: Scheduler & Control
    # =========================================================================



    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 2: Scheduler & Control
    # =========================================================================

    def _handle_tops_configure_scheduler(self, payload: Dict) -> Dict:
        """Configure the scheduler for a TOP network.

        Sets scheduler type, max concurrent processes, and working directory
        on the topnet's scheduler child node.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        scheduler_type = resolve_param_with_default(payload, "scheduler_type", "local")
        max_concurrent = resolve_param(payload, "max_concurrent", required=False)
        working_dir = resolve_param(payload, "working_dir", required=False)

        # PDG integration is localscheduler-only -- fail loudly on anything else
        # rather than echoing back an unconfigured scheduler type (truth contract).
        if str(scheduler_type).strip().lower() not in ("local", "localscheduler"):
            raise ValueError(
                f"Scheduler type '{scheduler_type}' isn't supported -- SYNAPSE's PDG "
                "integration is localscheduler-only (Deadline/Tractor/HQueue farm "
                "submission isn't wired up). Use scheduler_type='local' or omit it."
            )

        def _run():
            node = hou.node(topnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {topnet_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()
            if cat not in ("TopNet",):
                raise ValueError(
                    f"The node at {topnet_path} is a {cat} node, not a TOP network -- "
                    "point to a topnet node (e.g. '/obj/topnet1')"
                )

            # Find scheduler child node
            scheduler_node = None
            for child in node.children():
                child_type = child.type().name().lower()
                if "scheduler" in child_type or child_type == "localscheduler":
                    scheduler_node = child
                    break

            if scheduler_node is None:
                raise ValueError(
                    f"Couldn't find a scheduler node inside {topnet_path} -- "
                    "make sure the TOP network has a scheduler (e.g. localscheduler)"
                )

            # Configure max concurrent processes
            if max_concurrent is not None:
                menu_parm = scheduler_node.parm("maxprocsmenu")
                if menu_parm:
                    menu_parm.set("custom")
                procs_parm = scheduler_node.parm("maxprocs")
                if procs_parm:
                    procs_parm.set(int(max_concurrent))

            # Configure working directory
            if working_dir is not None:
                wd_parm = scheduler_node.parm("pdg_workingdir")
                if wd_parm:
                    wd_parm.set(str(working_dir))

            result = {
                "topnet": topnet_path,
                "scheduler_node": scheduler_node.path(),
                "scheduler_type": scheduler_type,
                "status": "configured",
            }
            if max_concurrent is not None:
                result["max_concurrent"] = int(max_concurrent)
            if working_dir is not None:
                result["working_dir"] = str(working_dir)
            return result

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_cancel_cook(self, payload: Dict) -> Dict:
        """Cancel an active cook on a TOP node or network.

        CONDUCTOR-6: the single-node branch calls the PDG cancel path
        (pdg.Node.cancel, falling back to pdg.WorkItem.cancel) and reports
        "cancelled" ONLY after reading the work-item states back. It never
        dirties the node: dirty() deletes work items, which destroys a
        finished node's results and does not stop a running cook. When no
        cancel API can reach the node the reply is an explicit cannot-cancel
        receipt, not a false success.

        Reachable while a cook runs: cooks started by tops_cook_node are
        non-blocking, so the main-thread marshal below is free. If a legacy
        blocking cook is somehow parked on the main thread, the marshal times
        out and the cancel falls back to the pdg-only handle captured at cook
        start (no hou.* call, no blocked marshal).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval  # noqa: F401  (dual-mode guard kept for parity)

        registry = self._cook_task_registry()
        node_path = resolve_param(payload, "node", required=False)
        task_id = resolve_param(payload, "task_id", required=False)

        record = registry.get(str(task_id)) if task_id is not None else None
        if record is None and node_path is not None:
            record = registry.active_for_node(node_path)
        if node_path is None:
            if record is None:
                raise ValueError(
                    "Cancel needs 'node' or a known 'task_id' — no cook is on record."
                )
            node_path = record["node"]
        elif record is not None and record["node"] != node_path:
            # A task id for a different node never cancels this one.
            record = registry.active_for_node(node_path)

        try:
            result = _run_in_main_thread_pdg(
                lambda: _cancel_tops_cook(node_path),
                timeout=_CANCEL_MARSHAL_TIMEOUT_S,
            )
        except Exception as exc:
            from ..main_thread import MainThreadTimeout
            if not isinstance(exc, MainThreadTimeout):
                raise
            result = _cancel_without_marshal(record, node_path)
            result["marshal_timed_out"] = True

        if record is not None:
            _apply_cancel_outcome(registry, record, result)
            result["task_id"] = record["task_id"]
        return result


    def _handle_tops_pause_cook(self, payload: Dict) -> Dict:
        """Pause an active cook on a TOP network.

        Pauses PDG cooking so the artist can inspect intermediate results.
        Work items currently in progress will finish, but no new items start.
        Use tops_resume_cook to continue.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()
            if cat != "TopNet":
                raise ValueError(
                    f"Pause requires a TOP network, but {node_path} is a {cat} -- "
                    "pass the topnet path instead of a single TOP node"
                )

            ctx = node.getPDGGraphContext()
            if ctx is None:
                raise ValueError(
                    f"No PDG context found on {node_path} -- "
                    "it may not have been cooked yet"
                )

            ctx.pauseCook()
            return {
                "node": node_path,
                "status": "paused",
                "note": (
                    "Cook is paused -- items already in progress will finish up. "
                    "Use tops_resume_cook when you're ready to continue."
                ),
            }

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_resume_cook(self, payload: Dict) -> Dict:
        """Resume a paused cook on a TOP network."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()
            if cat != "TopNet":
                raise ValueError(
                    f"Resume requires a TOP network, but {node_path} is a {cat} -- "
                    "pass the topnet path instead of a single TOP node"
                )

            ctx = node.getPDGGraphContext()
            if ctx is None:
                raise ValueError(
                    f"No PDG context found on {node_path} -- "
                    "it may not have been cooked yet"
                )

            ctx.resumeCook()
            return {
                "node": node_path,
                "status": "resumed",
                "note": "Cook resumed -- pending work items are being scheduled.",
            }

        return _run_in_main_thread_pdg(_run)


    def _handle_tops_dirty_node(self, payload: Dict) -> Dict:
        """Dirty a TOP node, optionally including upstream nodes.

        Dirtying removes cached work item results, forcing a re-cook.
        Use dirty_upstream=True to also dirty all upstream dependencies.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        dirty_upstream = resolve_param_with_default(payload, "dirty_upstream", False)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is not None:
                pdg_node.dirty(bool(dirty_upstream))
            else:
                # Fallback for nodes without PDG node
                try:
                    node.dirtyAllTasks(False)
                except AttributeError:
                    raise ValueError(
                        f"The node at {node_path} isn't a TOP node -- "
                        "make sure it's inside a TOP network"
                    )

            return {
                "node": node_path,
                "status": "dirtied",
                "dirty_upstream": bool(dirty_upstream),
            }

        return _run_in_main_thread_pdg(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS -- Phase 3: Advanced
    # =========================================================================


    def _handle_tops_batch_cook(self, payload: Dict) -> Dict:
        """Cook multiple TOP nodes in sequence, collecting results.

        Cooks each node in order and collects per-node results including
        status, work item counts, and cook times. Uses kahan_sum for
        stable total cook time aggregation (He2025).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_paths = resolve_param(payload, "node_paths")
        blocking = resolve_param_with_default(payload, "blocking", True)
        stop_on_error = resolve_param_with_default(payload, "stop_on_error", True)

        if not isinstance(node_paths, list) or len(node_paths) == 0:
            raise ValueError(
                "The 'node_paths' parameter should be a list of TOP node paths"
            )

        def _run():
            results = []
            cook_times = []
            by_state = {}
            errors = []

            for node_path in node_paths:
                node = hou.node(node_path)
                if node is None:
                    err = f"Couldn't find a node at {node_path}"
                    if stop_on_error:
                        raise ValueError(err)
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": 0.0,
                    })
                    errors.append(node_path)
                    continue

                pdg_node = node.getPDGNode()
                if pdg_node is None:
                    err = f"The node at {node_path} isn't a TOP node"
                    if stop_on_error:
                        raise ValueError(err)
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": 0.0,
                    })
                    errors.append(node_path)
                    continue

                t0 = time.monotonic()
                try:
                    node.cookWorkItems(block=bool(blocking))
                    elapsed = time.monotonic() - t0
                    item_count = len(pdg_node.workItems)

                    # Collect per-node state counts
                    node_states = {}
                    for wi in pdg_node.workItems:
                        sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                        node_states[sname] = node_states.get(sname, 0) + 1

                    for sname, count in sorted(node_states.items()):
                        by_state[sname] = by_state.get(sname, 0) + count

                    results.append({
                        "node": node_path,
                        "status": "cooked" if blocking else "cooking",
                        "work_items": item_count,
                        "cook_time": round_float(elapsed),
                    })
                    cook_times.append(elapsed)
                except Exception as e:
                    elapsed = time.monotonic() - t0
                    err = str(e)
                    if stop_on_error:
                        raise
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": round_float(elapsed),
                    })
                    cook_times.append(elapsed)
                    errors.append(node_path)

            total = kahan_sum(cook_times)
            cooked = sum(1 for r in results if r["status"] in ("cooked", "cooking"))
            summary = f"Cooked {cooked}/{len(node_paths)} nodes"
            if errors:
                summary += f", {len(errors)} error(s)"

            return {
                "nodes": results,
                "total_cook_time": round_float(total),
                "by_state": dict(sorted(by_state.items())),
                "summary": summary,
            }

        return _run_in_main_thread_pdg(_run)


