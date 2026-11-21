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

It also pins the live follow-up defect (found on 22.0.400): Houdini's patched
asyncio ("haio") refuses ``create_task`` off the main thread, so the worker's
``asyncio.run`` died before its first task and the receipt read ``error`` in
0.07 s. The worker now builds a plain ``asyncio.SelectorEventLoop`` (no
policy); if even that construction is refused, the driver runs its
synchronous step loop, labeled ``execution_mode='sync_steps'``, and no step
is ever dispatched twice.

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


# ---------------------------------------------------------------------------
# R-035 live defect: Houdini 22's patched asyncio (haio) refuses the loop
# ---------------------------------------------------------------------------
#
# Measured live on 22.0.400: the worker thread's ``asyncio.run`` died in
# ``haio.py create_task`` with "Current thread is not the main thread", so the
# task never validated or rendered. The repair builds a plain
# asyncio.SelectorEventLoop (no policy, no haio loop) and falls back to a
# synchronous step loop if even that construction is refused.

def _raise_main_thread_guard(*args, **kwargs):
    """Exactly the refusal haio raises off Houdini's main thread."""
    raise RuntimeError("Current thread is not the main thread")


class _HaioGuardedLoop(asyncio.SelectorEventLoop):
    """The haio shape from the live traceback: a loop that refuses a task.

    The loop itself is constructible off the main thread (measured on
    hython 22.0.400); the first ``create_task`` is what raises the guard, and
    that is exactly where ``asyncio.run`` died. Later task creations are
    allowed so ``Runner`` can tear the loop down after the refusal.
    """

    def __init__(self):
        super().__init__()
        self.refusals_left = 1

    def create_task(self, coro, **kwargs):
        if self.refusals_left:
            self.refusals_left -= 1
            raise RuntimeError("Current thread is not the main thread")
        return super().create_task(coro, **kwargs)


def _guard_the_default_loop(monkeypatch):
    """Simulate haio at both loop-acquisition seams.

    ``asyncio.new_event_loop()`` raises the guard outright, and the policy
    still hands back a loop whose ``create_task`` raises it -- the measured
    live traceback (haio.py:2217 -> check_thread). ``asyncio.run``, the
    pre-fix worker's call, dies on that first task.
    """
    monkeypatch.setattr(asyncio, "new_event_loop", _raise_main_thread_guard)
    policy = asyncio.get_event_loop_policy()
    monkeypatch.setattr(policy, "new_event_loop", lambda: _HaioGuardedLoop())


def _guard_the_plain_loop(monkeypatch):
    """Even asyncio.SelectorEventLoop itself refuses (the fallback's trigger)."""
    _guard_the_default_loop(monkeypatch)
    monkeypatch.setattr(asyncio, "SelectorEventLoop", _raise_main_thread_guard)


class _RecordingRegistry:
    """Registry seam: get() answers existence, invoke() records and answers."""

    def __init__(self, results=None):
        self.calls = []
        self._results = dict(results or {})

    def get(self, tool_name):
        return lambda payload=None: self._results.get(tool_name, {"success": True})

    def invoke(self, tool_name, payload, ctx=None):
        self.calls.append(tool_name)
        return self._results.get(tool_name, {"success": True})


def _sync_autonomy(planner, driver_cls=AutonomousDriver):
    """A ``synapse.autonomy`` stand-in with the REAL driver under test.

    Only the planner and the unused collaborators are faked; the driver is
    the production class, so the handler exercises ``execute_sync`` itself
    rather than a test double that could agree with the test.
    """
    module = ModuleType("synapse.autonomy")
    module.AutonomousDriver = driver_cls
    module.RenderPlanner = lambda *a, **k: planner
    module.PreFlightValidator = lambda *a, **k: object()
    module.RenderEvaluator = lambda *a, **k: object()
    return module


def _no_memory_store():
    """Keep the handler's optional decision-memory out of the test."""
    return patch("synapse.memory.store.get_synapse_memory",
                 side_effect=RuntimeError("memory disabled for test"))


class TestHoudiniAsyncioGuard:
    def test_a_haio_guarded_default_policy_does_not_kill_the_task(
            self, monkeypatch):
        """haio's off-main create_task refusal must not end the run.

        Pre-fix, the worker called ``asyncio.run``, which asks the policy for
        its loop and then refuses the very first ``create_task`` -- the live
        failure. The simulation is asserted live below, then the repaired
        worker builds a plain loop and the task reaches ``done``.
        """
        observed = {}

        async def _value(v):
            return v

        class _PlainLoopDriver:
            def __init__(self, **kwargs):
                pass

            async def execute(self, intent):
                observed["loop"] = asyncio.get_running_loop()
                observed["gathered"] = await asyncio.gather(_value(1), _value(2))
                await asyncio.sleep(0)
                return _FakeReport(success=True, stop_reason="")

        _guard_the_default_loop(monkeypatch)
        # The simulation is live at both seams: the constructor refuses, and
        # asyncio.run dies on the policy loop's first create_task.
        with pytest.raises(RuntimeError, match="main thread"):
            asyncio.new_event_loop()
        coro = _value(None)
        with pytest.raises(RuntimeError, match="main thread"):
            asyncio.run(coro)
        coro.close()  # the runner never got to schedule it

        handler = _new_handler()
        with patch.dict(sys.modules, {"synapse.autonomy": _fake_autonomy(_PlainLoopDriver)}), \
             patch.object(SynapseHandler, "_resolve_agent_usd",
                          staticmethod(lambda: None)), \
             _no_memory_store():
            started = handler._handle_autonomous_render(
                {"intent": "render frames 1-2"})
            done = _await(handler, started["task_id"])

        assert done["status"] == STATUS_DONE, \
            "a guarded default policy must not fail the task: %r" % (done,)
        assert done["success"] is True
        assert isinstance(observed["loop"], asyncio.SelectorEventLoop), \
            "the driver must run on the plain loop, not the policy's loop"
        assert not isinstance(observed["loop"], _HaioGuardedLoop), \
            "the driver must not run on haio's guarded loop"
        assert observed["gathered"] == [1, 2], \
            "asyncio.gather must work on the plain loop off the main thread"

    def test_a_plain_loop_refusal_runs_the_synchronous_fallback(
            self, monkeypatch):
        """If the plain loop class is guarded too, steps run synchronously.

        The receipt must be terminal and honest: execution_mode says
        'sync_steps', validation is reported as not run, evaluation and
        prediction are None, and the stop reason says the output went
        ungraded instead of claiming a pass.
        """
        registry = _RecordingRegistry({
            "render_sequence": {"success": True,
                                "image_path": "/tmp/frame_0001.exr"},
        })
        handler = _new_handler()
        handler._registry = registry

        _guard_the_plain_loop(monkeypatch)

        with patch.dict(sys.modules, {
                "synapse.autonomy": _sync_autonomy(_TwoStepPlanner())}), \
             patch.object(SynapseHandler, "_resolve_agent_usd",
                          staticmethod(lambda: None)), \
             _no_memory_store():
            started = handler._handle_autonomous_render(
                {"intent": "render frames 1-2"})
            done = _await(handler, started["task_id"])

        assert done["status"] == STATUS_DONE, \
            "the fallback must end in a terminal receipt: %r" % (done,)
        result = done["result"]
        assert result["execution_mode"] == "sync_steps"
        assert result["success"] is False
        assert result["stop_reason"] == "sync_steps_ungraded"
        assert result["evaluation"] is None, "nothing was graded"
        assert result["prediction"] is None, "nothing was predicted"
        assert result["verification"] is None, "nothing was verified"
        assert result["executed"]["validation_checks"] == [], \
            "an empty check list means no check ran"
        assert [step["status"] for step in result["executed"]["steps"]] == [
            "completed", "completed"]
        contexts = [d["context"] for d in result["decisions"]]
        assert "sync_fallback" in contexts
        assert "validation_skipped" in contexts
        assert registry.calls == ["render_settings", "render_sequence"]

    def test_the_fallback_never_dispatches_a_step_twice(self, monkeypatch):
        """A refused loop is chosen before dispatch: no step is replayed.

        The primary ``execute`` coroutine is never created (the loop is built
        first), and the synchronous pass dispatches each planned step exactly
        once -- proving the fallback is a first attempt, not a retry.
        """
        registry = _RecordingRegistry()
        handler = _new_handler()
        handler._registry = registry

        class _CountingDriver(AutonomousDriver):
            async_entries = []

            async def execute(self, intent):
                type(self).async_entries.append(intent)
                return await super().execute(intent)

        _guard_the_plain_loop(monkeypatch)

        with patch.dict(sys.modules, {
                "synapse.autonomy": _sync_autonomy(
                    _TwoStepPlanner(), driver_cls=_CountingDriver)}), \
             patch.object(SynapseHandler, "_resolve_agent_usd",
                          staticmethod(lambda: None)), \
             _no_memory_store():
            started = handler._handle_autonomous_render(
                {"intent": "render frames 1-2"})
            done = _await(handler, started["task_id"])

        assert done["status"] == STATUS_DONE
        assert _CountingDriver.async_entries == [], \
            "the async loop must never be entered once its construction fails"
        assert registry.calls == ["render_settings", "render_sequence"], \
            "each planned step dispatches exactly once across both paths"
        assert [step["status"] for step in done["result"]["executed"]["steps"]] == [
            "completed", "completed"]


def test_a_guard_raised_mid_run_is_reported_not_retried():
    """Only loop CONSTRUCTION may select the fallback.

    A RuntimeError carrying the guard's message, raised from inside the
    running driver, is a real failure: the task goes terminal ``error`` and
    the synchronous fallback is never entered -- re-running there would
    replay steps the async attempt may already have started.
    """
    fallback_entries = []

    class _MidRunGuardDriver:
        def __init__(self, **kwargs):
            pass

        async def execute(self, intent):
            await asyncio.sleep(0)
            raise RuntimeError("Current thread is not the main thread")

        def execute_sync(self, intent, reason=""):
            fallback_entries.append(intent)
            return _FakeReport(success=True, stop_reason="")

    handler = _new_handler()
    with patch.dict(sys.modules, {"synapse.autonomy": _fake_autonomy(_MidRunGuardDriver)}), \
         patch.object(SynapseHandler, "_resolve_agent_usd",
                      staticmethod(lambda: None)), \
         _no_memory_store():
        started = handler._handle_autonomous_render(
            {"intent": "render frames 1-2"})
        done = _await(handler, started["task_id"])

    assert done["status"] == STATUS_ERROR
    assert done["error_type"] == "RuntimeError"
    assert "main thread" in done["error"]
    assert fallback_entries == [], \
        "a guard raised mid-run must be reported, never replayed synchronously"


def test_the_sync_fallback_reports_a_failed_step_without_grading():
    """A failed sync step stops the pass; nothing is evaluated or claimed."""
    calls = []

    class _FailingSyncHandler:
        def call_sync(self, name, params):
            calls.append(name)
            raise RuntimeError("scene is not renderable")

    class _NeverGrade:
        def evaluate_sequence(self, results, **kw):
            raise AssertionError("a failed execution must not be graded")

    driver = AutonomousDriver(
        planner=_TwoStepPlanner(),
        validator=_NoChecks(),
        evaluator=_NeverGrade(),
        handler_interface=_FailingSyncHandler(),
    )

    report = driver.execute_sync("render frames 1-2", reason="guarded")

    assert calls == ["render_settings"], "the loop stops at the failed step"
    assert report.stop_reason == "execution_failed"
    assert report.success is False
    assert report.execution_mode == "sync_steps"
    assert report.evaluation is None
    assert report.executed.validation_checks == [], "no check ran"
    assert [step.status for step in report.executed.steps] == [
        StepStatus.FAILED, StepStatus.PENDING]
    assert any(d.context == "validation_skipped" for d in report.decisions)
