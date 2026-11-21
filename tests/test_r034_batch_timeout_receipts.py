"""R-034 (CONDUCTOR-7) — a timed-out batch stops, reports, and resumes without replay.

The audit's failure mode: ``batch_commands`` marshalled with a 30 s budget while
every client waited 60 s, so a caller told "timed out" left a payload that kept
issuing steps -- and a retry re-sent the same command list and applied every
step that had already run a second time.

These tests drive the shipped handler against:

* a registry double that counts executions per step and can block inside a
  step (a slow mutation);
* a marshal double that implements ``run_on_main``'s DOCUMENTED contract: the
  payload runs on its own thread and may outlive the caller's wait.

What is asserted: no step starts after the caller stopped waiting, a step that
was in flight is reported ``unknown`` (never ``failed``), a retry with the same
``batch_id`` never executes a completed step twice, an in-flight step left with
no outcome is never re-executed, and the marshal budget is the client budget.

No Houdini, no hython, no network.
"""
from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest

from synapse.core.errors import SynapseUserError
from synapse.core.protocol import SynapseCommand

_FOUND = object()


def _live_main_thread():
    """The LIVE main_thread module, resolved at call time.

    ``tests/test_main_thread.py`` replaces ``sys.modules['synapse.server.main_thread']``
    with a freshly loaded module object at import, so a ``MainThreadTimeout``
    imported at collection time can split identity from the class the handler
    and ``run_on_main`` resolve at call time. Production resolves it live, and
    so must a test that asserts on it.
    """
    from synapse.server import main_thread
    return main_thread


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------

class _Registry:
    """Registry double: one behaviour per command type, executions recorded."""

    def __init__(self, behaviours):
        self._behaviours = behaviours
        self.executions = []
        self._lock = threading.Lock()
        self._floor_gate = SimpleNamespace(current_op_id=lambda: None)

    def get(self, command_type):
        return _FOUND if command_type in self._behaviours else None

    def invoke(self, command_type, payload, ctx=None):
        with self._lock:
            # Every step in these tests carries its index; the batch envelope
            # itself (a wire-level test) carries none and is not a step.
            if isinstance(payload, dict) and "index" in payload:
                self.executions.append(payload["index"])
        return self._behaviours[command_type](payload)


class _Marshal:
    """run_on_main's contract: the payload may still be running when the wait ends."""

    def __init__(self, wait):
        self.wait = wait
        self.timeouts = []
        self.threads = []

    def __call__(self, fn, timeout=None, label=None):
        self.timeouts.append((timeout, label))
        box = {}

        def run():
            try:
                box["value"] = fn()
            except BaseException as error:  # the payload's own death reaches the caller
                box["error"] = error

        thread = threading.Thread(target=run, daemon=True)
        self.threads.append(thread)
        thread.start()
        thread.join(self.wait)
        if thread.is_alive():
            exc = _live_main_thread().MainThreadTimeout(
                "Houdini's main thread didn't respond in time -- it may be "
                "busy cooking or rendering. The call may still be running; "
                "check the scene before trying again.")
            exc.started = True  # the payload had begun
            raise exc
        if "error" in box:
            raise box["error"]
        return box["value"]

    def join(self):
        for thread in self.threads:
            thread.join(10)


def _never_starts(fn, timeout=None, label=None):
    exc = _live_main_thread().MainThreadTimeout(
        "Houdini's main thread didn't respond in time")
    exc.started = False  # C4 abandoned before fn() ran
    raise exc


def _make(monkeypatch, behaviours):
    from synapse.server import handlers as handlers_module

    handler = handlers_module.SynapseHandler()
    registry = _Registry(behaviours)
    handler._registry = registry
    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
    monkeypatch.setattr(handler, "_submit_logs", lambda *a, **k: None)
    return handlers_module, handler, registry


def _set_batch_budget(monkeypatch, seconds):
    """Patch the ONE canonical table entry the handler, marshal and client read."""
    from synapse.core import timeouts

    monkeypatch.setitem(timeouts.SLOW_COMMANDS, "batch_commands", seconds)


def _indices(registry):
    return [index for index in registry.executions]


# ---------------------------------------------------------------------------
# A timed-out batch stops issuing steps and reports which ones ran
# ---------------------------------------------------------------------------

def test_a_slow_step_stops_the_batch_and_reports_states(monkeypatch):
    gate = threading.Event()

    def slow(payload):
        gate.wait(5.0)
        return {"index": payload["index"]}

    handlers_module, handler, registry = _make(monkeypatch, {
        "fast": lambda p: {"index": p["index"]},
        "slow": slow,
        "never": lambda p: {"index": p["index"]},
    })
    monkeypatch.setattr(handlers_module, "_would_run_inline_on_main", lambda: False)
    _set_batch_budget(monkeypatch, 1.5)
    marshal = _Marshal(wait=1.7)
    monkeypatch.setattr(handlers_module, "run_on_main_observed", marshal)

    commands = [
        {"type": "fast", "payload": {"index": 0}},
        {"type": "slow", "payload": {"index": 1}},
        {"type": "never", "payload": {"index": 2}},
    ]
    with pytest.raises(_live_main_thread().MainThreadTimeout) as caught:
        handler._handle_batch_commands({"commands": commands, "batch_id": "b-slow"})

    receipt = caught.value.receipt
    assert receipt["batch_id"] == "b-slow"
    assert [step["status"] for step in receipt["steps"]] == [
        "ok", "unknown", "not_run"]
    assert receipt["unknown_steps"] == [1]
    assert receipt["status"] == "in_progress"
    assert caught.value.started is True
    assert caught.value.batch_id == "b-slow"

    message = str(caught.value)
    assert "b-slow" in message
    assert "1=unknown" in message
    assert "batch_id=b-slow" in message
    assert "unknown" in message and "check" in message.lower()

    gate.set()
    marshal.join()

    assert _indices(registry) == [0, 1], (
        "no step may start after the caller stopped waiting")


def test_a_timeout_before_dispatch_reports_nothing_applied(monkeypatch):
    handlers_module, handler, registry = _make(monkeypatch, {
        "fast": lambda p: {"index": p["index"]},
    })
    monkeypatch.setattr(handlers_module, "_would_run_inline_on_main", lambda: False)
    monkeypatch.setattr(handlers_module, "run_on_main_observed", _never_starts)

    with pytest.raises(_live_main_thread().MainThreadTimeout) as caught:
        handler._handle_batch_commands({
            "commands": [{"type": "fast", "payload": {"index": 0}}],
            "batch_id": "b-never",
        })

    receipt = caught.value.receipt
    assert receipt["status"] == "not_started"
    assert receipt["not_run_steps"] == [0]
    assert "never began" in str(caught.value)
    assert "nothing was applied" in str(caught.value)
    assert _indices(registry) == []


# ---------------------------------------------------------------------------
# The applied-step guard: a retry never replays a completed step
# ---------------------------------------------------------------------------

def test_a_retry_with_the_same_batch_id_skips_completed_steps(monkeypatch):
    gate = threading.Event()

    def slow(payload):
        gate.wait(5.0)
        return {"index": payload["index"]}

    handlers_module, handler, registry = _make(monkeypatch, {
        "fast": lambda p: {"index": p["index"]},
        "slow": slow,
    })
    monkeypatch.setattr(handlers_module, "_would_run_inline_on_main", lambda: False)
    _set_batch_budget(monkeypatch, 1.5)
    marshal = _Marshal(wait=1.7)
    monkeypatch.setattr(handlers_module, "run_on_main_observed", marshal)

    commands = [
        {"type": "fast", "payload": {"index": 0}},
        {"type": "slow", "payload": {"index": 1}},
        {"type": "fast", "payload": {"index": 2}},
        {"type": "fast", "payload": {"index": 3}},
    ]
    with pytest.raises(_live_main_thread().MainThreadTimeout):
        handler._handle_batch_commands({"commands": commands, "batch_id": "b-retry"})

    gate.set()
    marshal.join()
    # Step 1 finished; step 2 never started (the deadline stopped the loop).
    assert _indices(registry) == [0, 1]

    # A retry: normal budget, same id. Completed steps must not run again.
    _set_batch_budget(monkeypatch, 30.0)
    marshal.wait = 10.0
    result = handler._handle_batch_commands(
        {"commands": commands, "batch_id": "b-retry"})

    assert _indices(registry) == [0, 1, 2, 3], "no step executes twice"
    assert result["resumed"] == [0, 1]
    assert result["statuses"] == ["ok", "ok", "ok", "ok"]
    assert result["batch_status"] == "complete"
    assert result["results"] == [
        {"index": 0}, {"index": 1}, {"index": 2}, {"index": 3}]


def test_a_fresh_batch_id_starts_a_fresh_batch(monkeypatch):
    """The guard is id-scoped: a new id is the explicit way to run everything again."""
    handlers_module, handler, registry = _make(monkeypatch, {
        "fast": lambda p: {"index": p["index"]},
    })

    commands = [{"type": "fast", "payload": {"index": 0}},
                {"type": "fast", "payload": {"index": 1}}]
    handler._handle_batch_commands({"commands": commands, "batch_id": "b-one"})
    result = handler._handle_batch_commands({"commands": commands, "batch_id": "b-two"})

    assert _indices(registry) == [0, 1, 0, 1]
    assert result["resumed"] == []


def test_a_step_left_in_flight_is_reported_unknown_and_never_replayed(monkeypatch):
    class _PayloadDied(BaseException):
        """The payload died inside a step, so its receipt stayed in flight."""

    def dies(payload):
        raise _PayloadDied("payload died mid-step")

    handlers_module, handler, registry = _make(monkeypatch, {
        "dies": dies,
        "never": lambda p: {"index": p["index"]},
    })

    commands = [{"type": "dies", "payload": {"index": 0}},
                {"type": "never", "payload": {"index": 1}}]
    with pytest.raises(_PayloadDied):
        handler._handle_batch_commands({"commands": commands, "batch_id": "b-died"})

    result = handler._handle_batch_commands(
        {"commands": commands, "batch_id": "b-died"})

    assert _indices(registry) == [0], "an unknown step is never re-executed"
    assert result["statuses"] == ["unknown", "not_run"]
    assert result["batch_status"] == "in_progress"
    assert "not re-run" in result["errors"][0].lower()


def test_reusing_a_batch_id_for_a_different_command_list_is_refused(monkeypatch):
    handlers_module, handler, registry = _make(monkeypatch, {
        "fast": lambda p: {"index": p["index"]},
    })

    handler._handle_batch_commands({
        "commands": [{"type": "fast", "payload": {"index": 0}}],
        "batch_id": "b-conflict",
    })
    with pytest.raises(SynapseUserError, match="batch_id"):
        handler._handle_batch_commands({
            "commands": [{"type": "fast", "payload": {"index": 1}}],
            "batch_id": "b-conflict",
        })
    assert _indices(registry) == [0]


# ---------------------------------------------------------------------------
# Budgets: the marshal is the client's budget (C7's one canonical table)
# ---------------------------------------------------------------------------

def test_the_marshal_budget_is_the_client_budget(monkeypatch):
    from synapse.core import timeouts

    handlers_module, handler, registry = _make(monkeypatch, {
        "fast": lambda p: {"index": p["index"]},
    })
    captured = {}

    def marshal(fn, timeout=None, label=None):
        captured["timeout"] = timeout
        captured["label"] = label
        return fn()

    monkeypatch.setattr(handlers_module, "run_on_main_observed", marshal)
    handler._handle_batch_commands(
        {"commands": [{"type": "fast", "payload": {"index": 0}}]})

    assert captured["label"] == "batch_commands"
    assert captured["timeout"] == timeouts.SLOW_COMMANDS["batch_commands"]
    assert captured["timeout"] == timeouts.timeout_for("batch_commands")
    # The MCP tool name the stdio client budgets on resolves to the same value.
    assert captured["timeout"] == timeouts.timeout_for("synapse_batch")


# ---------------------------------------------------------------------------
# The wire: a timed-out batch is an unknown outcome AND it carries its receipt
# ---------------------------------------------------------------------------

def test_the_wire_reports_unknown_outcome_with_the_batch_receipt(monkeypatch):
    gate = threading.Event()

    def slow(payload):
        gate.wait(5.0)
        return {"index": payload["index"]}

    handlers_module, handler, registry = _make(monkeypatch, {
        "fast": lambda p: {"index": p["index"]},
        "slow": slow,
    })
    # The wire path resolves via handle(), so the envelope command itself must
    # dispatch to the shipped batch handler.
    registry._behaviours["batch_commands"] = handler._handle_batch_commands
    monkeypatch.setattr(handlers_module, "_would_run_inline_on_main", lambda: False)
    _set_batch_budget(monkeypatch, 1.5)
    marshal = _Marshal(wait=1.7)
    monkeypatch.setattr(handlers_module, "run_on_main_observed", marshal)

    response = handler.handle(SynapseCommand(
        id="r034-1",
        type="batch_commands",
        payload={
            "commands": [
                {"type": "fast", "payload": {"index": 0}},
                {"type": "slow", "payload": {"index": 1}},
                {"type": "fast", "payload": {"index": 2}},
            ],
            "batch_id": "b-wire",
        },
        sequence=1,
    ))

    wire = json.loads(response.to_json())
    assert wire["success"] is False
    outcome = wire["data"]["outcome"]
    assert (outcome["code"], outcome["outcome"], outcome["dispatched"]) == (
        "transport.timeout", "unknown_outcome", "maybe")
    receipt = wire["data"]["receipt"]
    assert receipt["batch_id"] == "b-wire"
    assert [step["status"] for step in receipt["steps"]] == [
        "ok", "unknown", "not_run"]

    gate.set()
    marshal.join()
    assert _indices(registry) == [0, 1], "the wire reply did not let step 2 start"


# ---------------------------------------------------------------------------
# The receipt store's own contract (bounded, snapshot is non-destructive)
# ---------------------------------------------------------------------------

def test_snapshot_renders_in_flight_as_unknown_without_mutating_it():
    from synapse.server.batch_receipts import BatchReceipts

    receipts = BatchReceipts("b-unit", 2, "fp")
    receipts.begin(0)
    snapshot = receipts.snapshot()

    assert snapshot["steps"] == [
        {"index": 0, "status": "unknown"},
        {"index": 1, "status": "not_run"},
    ]
    assert snapshot["status"] == "in_progress"
    # The live receipt is untouched: the payload may still complete step 0.
    assert receipts.status(0) == "in_progress"
    receipts.finish_ok(0, {"done": True})
    assert receipts.status(0) == "ok"


def test_the_store_is_bounded_and_evicts_settled_batches_first():
    from synapse.server.batch_receipts import BatchReceiptStore

    store = BatchReceiptStore(capacity=2)
    settled = store.get_or_create("settled", [{"type": "a"}])
    settled.begin(0)
    settled.finish_ok(0, {})
    running = store.get_or_create("running", [{"type": "b"}])
    running.begin(0)

    store.get_or_create("newest", [{"type": "c"}])

    assert len(store) == 2
    assert store.get("settled") is None, "a settled batch is evicted first"
    assert store.get("running") is running, "an in-flight batch is kept"
    assert store.get("newest") is not None
