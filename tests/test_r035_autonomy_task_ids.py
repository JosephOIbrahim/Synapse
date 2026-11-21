"""R-035 (CONDUCTOR-8) -- autonomous render returns a task id, joins a
duplicate start, and stops at a step boundary when its wall clock expires.

The audit's failure mode: ``synapse_autonomous_render`` ran the whole loop
inside the tool call, with a client budget (600 s) below the handler's own
worst case (the driver budget + 60 s), so the caller was told it timed out
while the render kept going -- and a retry started a SECOND loop over the
first.

These tests pin the repair:

* the handler returns a task id immediately (the run continues on a worker
  thread) and ``{"task_id": ...}`` exposes the terminal report;
* a second start for the same intent and plan is JOINED (same id,
  ``reused: true``) and only one driver is constructed;
* the driver checks its wall clock at every STEP boundary: once the deadline
  passes, no further step starts, the skipped steps say so, and the report
  carries ``stop_reason='wall_clock_exceeded'``.

Headless. Plant-or-enrich hou-fake convention (tests/test_m2_cook_verify.py
header); handler-module globals patched directly, never sys.modules residency.
No Houdini, no hython, no network.
"""

import asyncio
import sys
import threading
import time
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "text"):
    _h.text = MagicMock()
    _h.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    _hd.executeDeferred = lambda fn: fn()
    sys.modules["hdefereval"] = _hd

from synapse.autonomy.driver import AutonomousDriver, _register_live_driver  # noqa: E402
from synapse.autonomy.models import (  # noqa: E402
    GateLevel,
    RenderPlan,
    RenderStep,
    StepStatus,
)
from synapse.server.autonomy_tasks import (  # noqa: E402
    AutonomyTaskStore,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_RUNNING,
    fingerprint,
)
from synapse.server.handlers import SynapseHandler  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes and helpers
# ---------------------------------------------------------------------------

@dataclass
class _FakeReport:
    """Minimal RenderReport shape: the fields the handler serializes."""

    success: bool = True
    stop_reason: str = ""
    executed: object = None
    evaluation: object = None


def _fake_autonomy(driver_cls):
    """A ``synapse.autonomy`` stand-in with a real-shaped planner."""
    module = ModuleType("synapse.autonomy")
    module.AutonomousDriver = driver_cls
    module.RenderPlanner = lambda *a, **k: SimpleNamespace(
        plan=lambda intent, scene_context=None: RenderPlan(intent=str(intent)),
    )
    module.PreFlightValidator = lambda *a, **k: object()
    module.RenderEvaluator = lambda *a, **k: object()
    return module


def _new_handler():
    """A handler with the live registry seam and no heavy __init__."""
    handler = SynapseHandler.__new__(SynapseHandler)
    handler._registry = MagicMock()
    return handler


def _await(handler, task_id, timeout=10.0):
    """Poll an autonomy task to its terminal receipt (bounded)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        receipt = handler._handle_autonomous_render({"task_id": task_id})
        if receipt.get("status") != "running":
            return receipt
        time.sleep(0.01)
    raise AssertionError("autonomy task %s did not finish in %.1fs"
                         % (task_id, timeout))


class _BlockingDriver:
    """A driver whose execute() stays inside until the test releases it."""

    instances = []
    gate = threading.Event()

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        type(self).instances.append(self)

    async def execute(self, intent):
        while not type(self).gate.is_set():
            await asyncio.sleep(0.005)
        return _FakeReport(success=True, stop_reason="")


@pytest.fixture(autouse=True)
def _clean_live_registry():
    _register_live_driver(None)
    yield
    _register_live_driver(None)


@pytest.fixture
def blocking_driver():
    driver_cls = type("_BlockingDriverForTest", (_BlockingDriver,), {
        "instances": [],
        "gate": threading.Event(),
    })
    yield driver_cls
    driver_cls.gate.set()


# ---------------------------------------------------------------------------
# Task store: join identity, bounded memory, terminal receipts
# ---------------------------------------------------------------------------

class TestAutonomyTaskStore:
    def test_same_key_joins_the_running_task(self):
        store = AutonomyTaskStore()
        first, joined_first = store.start_or_join("k1", "render frames 1-2")
        second, joined_second = store.start_or_join("k1", "render frames 1-2")
        assert joined_first is False
        assert joined_second is True
        assert second["task_id"] == first["task_id"]
        assert second["joined_calls"] == 1

    def test_a_finished_task_is_not_joined_by_a_later_start(self):
        store = AutonomyTaskStore()
        first, _ = store.start_or_join("k1", "render frames 1-2")
        store.complete(first["task_id"], {"success": True}, success=True)
        second, joined = store.start_or_join("k1", "render frames 1-2")
        assert joined is False
        assert second["task_id"] != first["task_id"]

    def test_a_stale_running_task_is_not_joined(self):
        store = AutonomyTaskStore(stale_after_s=0.0)
        first, _ = store.start_or_join("k1", "render frames 1-2")
        time.sleep(0.01)
        second, joined = store.start_or_join("k1", "render frames 1-2")
        assert joined is False
        assert second["task_id"] != first["task_id"]

    def test_receipts_are_terminal_state_honest(self):
        store = AutonomyTaskStore()
        task, _ = store.start_or_join("k1", "render frames 1-2")
        running = store.public(task["task_id"])
        assert running["status"] == STATUS_RUNNING
        assert "result" not in running

        store.complete(task["task_id"], {"success": False}, success=False,
                       stop_reason="wall_clock_exceeded")
        done = store.public(task["task_id"])
        assert done["status"] == STATUS_DONE
        assert done["success"] is False
        assert done["stop_reason"] == "wall_clock_exceeded"
        assert done["result"] == {"success": False}

        failed, _ = store.start_or_join("k2", "other")
        store.fail(failed["task_id"], "boom", "RuntimeError")
        errored = store.public(failed["task_id"])
        assert errored["status"] == STATUS_ERROR
        assert errored["error"] == "boom"
        assert errored["error_type"] == "RuntimeError"

    def test_unknown_task_id_is_none(self):
        assert AutonomyTaskStore().public("nope") is None

    def test_finished_eviction_never_drops_a_running_task(self):
        store = AutonomyTaskStore(max_finished=2)
        running, _ = store.start_or_join("run", "render frames 1-2")
        for i in range(5):
            task, _ = store.start_or_join("k%d" % i, "intent %d" % i)
            store.complete(task["task_id"], {}, success=True)
        assert store.public(running["task_id"]) is not None
        # The running record survives; terminals are pruned at the next
        # start, so at most max_finished + the one that just finished remain.
        assert len(store) <= 2 + 2

    def test_fingerprint_distinguishes_plan_and_parameters(self):
        steps = [{"handler": "render_sequence", "params": {"start_frame": 1}}]
        base = fingerprint("render frame 1", steps, {"quality_threshold": 0.85})
        assert fingerprint("render frame 1", steps, {"quality_threshold": 0.85}) == base
        assert fingerprint("render frame 1", steps, {"quality_threshold": 0.9}) != base
        assert fingerprint("render frame 1", [], {"quality_threshold": 0.85}) != base
        assert fingerprint("render frame 2", steps, {"quality_threshold": 0.85}) != base


# ---------------------------------------------------------------------------
# Handler: immediate task id, join, poll
# ---------------------------------------------------------------------------

class TestHandlerTaskContract:
    def test_start_returns_a_task_id_without_waiting_for_the_loop(
            self, blocking_driver):
        handler = _new_handler()
        with patch.dict(sys.modules, {"synapse.autonomy": _fake_autonomy(blocking_driver)}), \
             patch.object(SynapseHandler, "_resolve_agent_usd",
                          staticmethod(lambda: None)):
            t0 = time.monotonic()
            started = handler._handle_autonomous_render(
                {"intent": "render frames 1-2"})
            elapsed = time.monotonic() - t0

            assert elapsed < 2.0, "the start call must not wait for the loop"
            assert started["task_id"].startswith("autorender-")
            assert started["status"] == STATUS_RUNNING
            assert started["reused"] is False
            assert started["note"]

            while_running = handler._handle_autonomous_render(
                {"task_id": started["task_id"]})
            assert while_running["status"] == STATUS_RUNNING
            assert while_running["task_id"] == started["task_id"]

            blocking_driver.gate.set()
            done = _await(handler, started["task_id"])

        assert done["status"] == STATUS_DONE
        assert done["success"] is True
        assert done["result"]["success"] is True

    def test_second_start_for_the_same_intent_and_plan_joins(
            self, blocking_driver):
        handler = _new_handler()
        with patch.dict(sys.modules, {"synapse.autonomy": _fake_autonomy(blocking_driver)}), \
             patch.object(SynapseHandler, "_resolve_agent_usd",
                          staticmethod(lambda: None)):
            first = handler._handle_autonomous_render({"intent": "render frames 1-2"})
            second = handler._handle_autonomous_render({"intent": "render frames 1-2"})

            assert second["task_id"] == first["task_id"]
            assert second["reused"] is True
            assert second["joined_calls"] == 1
            assert len(blocking_driver.instances) == 1, \
                "a duplicate start must not construct a second driver"

            blocking_driver.gate.set()
            _await(handler, first["task_id"])

    def test_a_different_intent_starts_a_separate_task(self, blocking_driver):
        handler = _new_handler()
        with patch.dict(sys.modules, {"synapse.autonomy": _fake_autonomy(blocking_driver)}), \
             patch.object(SynapseHandler, "_resolve_agent_usd",
                          staticmethod(lambda: None)):
            first = handler._handle_autonomous_render({"intent": "render frames 1-2"})
            second = handler._handle_autonomous_render({"intent": "render frames 3-4"})

            assert second["task_id"] != first["task_id"]
            assert second["reused"] is False
            assert len(blocking_driver.instances) == 2

            blocking_driver.gate.set()
            _await(handler, first["task_id"])
            _await(handler, second["task_id"])

    def test_polling_an_unknown_task_id_raises(self):
        handler = _new_handler()
        with pytest.raises(ValueError, match="autonomous render task"):
            handler._handle_autonomous_render({"task_id": "autorender-deadbeef"})

    def test_a_missing_intent_still_says_what_is_needed(self):
        handler = _new_handler()
        with pytest.raises(ValueError, match="intent"):
            handler._handle_autonomous_render({})

    def test_the_terminal_receipt_mirrors_the_wall_clock_stop(self):
        class _WallClockDriver:
            def __init__(self, **kwargs):
                pass

            async def execute(self, intent):
                return _FakeReport(success=False,
                                   stop_reason="wall_clock_exceeded")

        handler = _new_handler()
        with patch.dict(sys.modules, {"synapse.autonomy": _fake_autonomy(_WallClockDriver)}), \
             patch.object(SynapseHandler, "_resolve_agent_usd",
                          staticmethod(lambda: None)):
            started = handler._handle_autonomous_render(
                {"intent": "render frames 1-2"})
            done = _await(handler, started["task_id"])

        assert done["status"] == STATUS_DONE
        assert done["success"] is False
        assert done["stop_reason"] == "wall_clock_exceeded"
        assert done["result"]["stop_reason"] == "wall_clock_exceeded"


# ---------------------------------------------------------------------------
# Driver: the wall clock is checked at every STEP boundary
# ---------------------------------------------------------------------------

class _TwoStepPlanner:
    """A fixed two-step plan: settings, then the render."""

    def plan(self, intent, scene_context=None):
        return RenderPlan(
            intent=str(intent),
            gate_level=GateLevel.INFORM,
            steps=[
                RenderStep(handler="render_settings", params={},
                           description="apply settings"),
                RenderStep(handler="render_sequence",
                           params={"start_frame": 1, "end_frame": 2},
                           description="render frames 1-2"),
            ],
        )

    def replan(self, plan, evaluation):
        return plan


class _NoChecks:
    async def validate(self, plan):
        return []


def test_driver_stops_at_a_step_boundary_when_the_wall_clock_expires():
    """A step that finishes past the deadline must not start the next one.

    The settings step takes 50 ms against a 10 ms budget: the render step
    never dispatches, is reported SKIPPED, and the report says why.
    """
    calls = []

    class _SlowFirstStepHandler:
        async def call(self, name, params):
            calls.append(name)
            if name == "render_settings":
                await asyncio.sleep(0.05)
            return {"success": True}

    class _NeverGrade:
        def evaluate_sequence(self, results, **kw):
            raise AssertionError(
                "a wall-clock stop must not grade a partial sequence")

    driver = AutonomousDriver(
        planner=_TwoStepPlanner(),
        validator=_NoChecks(),
        evaluator=_NeverGrade(),
        handler_interface=_SlowFirstStepHandler(),
        max_iterations=3,
        max_wall_clock_seconds=0.01,
    )

    report = asyncio.run(driver.execute("render frame 1"))

    assert calls == ["render_settings"], "the render step must never start"
    assert report.stop_reason == "wall_clock_exceeded"
    assert report.success is False
    assert report.iterations == 1
    assert [step.status for step in report.executed.steps] == [
        StepStatus.COMPLETED, StepStatus.SKIPPED]
    assert any(d.context == "wall_clock_exceeded" for d in report.decisions)


def test_driver_never_starts_a_step_after_the_deadline():
    """A deadline crossed during validation stops before the first step.

    (The iteration-top check cannot catch this: validation runs after it.)
    """
    calls = []

    class _SlowChecks:
        async def validate(self, plan):
            await asyncio.sleep(0.05)
            return []

    class _CountingHandler:
        async def call(self, name, params):
            calls.append(name)
            return {"success": True}

    class _NeverGrade:
        def evaluate_sequence(self, results, **kw):
            raise AssertionError("nothing ran; nothing may be graded")

    driver = AutonomousDriver(
        planner=_TwoStepPlanner(),
        validator=_SlowChecks(),
        evaluator=_NeverGrade(),
        handler_interface=_CountingHandler(),
        max_iterations=3,
        max_wall_clock_seconds=0.01,
    )

    report = asyncio.run(driver.execute("render frame 1"))

    assert calls == [], "no step may dispatch once the deadline has passed"
    assert report.stop_reason == "wall_clock_exceeded"
    assert report.success is False
    assert [step.status for step in report.executed.steps] == [
        StepStatus.SKIPPED, StepStatus.SKIPPED]
