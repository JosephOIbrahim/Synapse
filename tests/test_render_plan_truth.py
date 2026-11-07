"""
Synapse Autonomy Pipeline — Render Plan Truth Tests

The plan's product set must be the artist's request, exactly: no invented
intermediate frames, no silently dropped frames, and no retry graded against
a rewritten plan.

Run without Houdini:
    python -m pytest tests/test_render_plan_truth.py -v
"""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add package to path (same idiom as the neighbouring autonomy tests)
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.autonomy.models import (
    RenderStep,
    StepStatus,
)
from synapse.autonomy.planner import RenderPlanner, requested_frames, retry_targets
from synapse.autonomy.driver import AutonomousDriver


# =============================================================================
# HELPERS
# =============================================================================


class _ScriptedRenderHandler:
    """Fake handler that honours an explicit ``params['frames']`` list.

    ``failures`` maps attempt number -> frames to return as failed (empty
    image_path + per-frame error). ``omit`` maps attempt number -> frames to
    leave out of ``frame_results`` entirely, which is what the real farm does
    for a frame it never produced.
    """

    def __init__(self, failures=None, omit=None):
        self.calls = []
        self._attempt = 0
        self._failures = failures or {}
        self._omit = omit or {}

    async def call(self, name, params):
        if name == "get_stage_info":
            return {"cameras": ["/c"], "renderable_prims": 1}
        if name != "render_sequence":
            return {}

        self.calls.append(dict(params))
        self._attempt += 1
        attempt = self._attempt

        frames = params.get("frames")
        if frames:
            frame_list = sorted({int(f) for f in frames})
        else:
            start = int(params.get("start_frame", 1))
            end = int(params.get("end_frame", start))
            frame_list = list(range(start, end + 1))

        omit = set(self._omit.get(attempt, ()))
        bad = set(self._failures.get(attempt, ()))

        results = []
        for frame in frame_list:
            if frame in omit:
                continue
            failed = frame in bad
            results.append({
                "frame": frame,
                "image_path": "" if failed else f"/tmp/f{frame}.exr",
                "error": "boom" if failed else "",
            })

        ok = sum(1 for row in results if not row["error"])
        return {
            "total_frames": len(frame_list),
            "successful_frames": ok,
            "failed_frames": len(frame_list) - ok,
            "frame_results": results,
        }


def _stub_evaluator():
    """Real evaluator with pixel loading stubbed to a clean mid-grey frame."""
    numpy = pytest.importorskip("numpy")
    from synapse.autonomy.evaluator import RenderEvaluator

    class _StubEvaluator(RenderEvaluator):
        def _load_frame(self, path):
            if not path:
                return None
            return numpy.full((8, 8, 3), 0.5, dtype=numpy.float32)

    return _StubEvaluator()


def _make_driver(
    handler,
    planner=None,
    evaluator=None,
    max_iterations=3,
    max_wall_clock_seconds=None,
):
    from synapse.autonomy.validator import PreFlightValidator

    return AutonomousDriver(
        planner=planner or RenderPlanner(),
        validator=PreFlightValidator(handler),
        evaluator=evaluator or _stub_evaluator(),
        handler_interface=handler,
        max_iterations=max_iterations,
        max_wall_clock_seconds=max_wall_clock_seconds,
    )


def _mock_driver():
    return AutonomousDriver(
        planner=MagicMock(),
        validator=MagicMock(),
        evaluator=MagicMock(),
        handler_interface=MagicMock(),
    )


# =============================================================================
# FAILING-FIRST CASES
# =============================================================================


def test_sparse_plan_never_invents_intermediate_frames():
    """'re-render frames 1, 3' must mean exactly frames 1 and 3.

    Fails today: ``requested_frames`` does not exist, and the driver's
    ``_planned_frames`` expands start=1/end=3 to [1, 2, 3], inventing a
    product the artist never asked for.
    """
    plan = RenderPlanner().plan("re-render frames 1, 3")

    assert requested_frames(plan) == (1, 3)
    assert _mock_driver()._planned_frames(plan) == [1, 3]


@pytest.mark.asyncio
async def test_sparse_retry_of_3_keeps_accepted_1():
    """Retrying frame 3 must re-render only frame 3 and keep frame 1.

    Fails today: the report carries the retry plan, so a consumer recomputing
    the product set from ``report.plan`` sees only [3] and loses frame 1.
    """
    handler = _ScriptedRenderHandler(failures={1: {3}})
    driver = _make_driver(handler)

    report = await driver.execute("re-render frames 1, 3")

    assert len(handler.calls) >= 2, "the first attempt must fail and be retried"
    assert handler.calls[1] == {
        "start_frame": 3,
        "end_frame": 3,
        "frames": [3],
    }
    assert [fe.frame for fe in report.evaluation.frame_evaluations] == [1, 3]
    assert report.success is True
    assert report.stop_reason == ""
    assert report.plan.intent == "re-render frames 1, 3"


@pytest.mark.asyncio
async def test_missing_terminal_product_without_evaluation_row_is_a_retry_target():
    """A planned frame with no evaluation row at all is still a retry target.

    Fails today: retry targets come only from rows that exist, so frame 3 is
    invisible to the replan and the whole 1-3 range is re-run.
    """
    handler = _ScriptedRenderHandler(omit={1: {3}})
    driver = _make_driver(handler)

    report = await driver.execute("render frames 1-3")

    assert len(handler.calls) >= 2, "the first attempt must fail and be retried"
    assert handler.calls[1].get("frames") == [3]
    assert handler.calls[1].get("start_frame") == 3
    assert any(
        "OUTPUT_MISSING" in d.reasoning for d in report.decisions
    ), "the retry reason must be observable in the decision trail"
    assert 3 in [fe.frame for fe in report.evaluation.frame_evaluations]
    assert report.success is True


@pytest.mark.asyncio
async def test_two_render_steps_refused_before_dispatch():
    """A plan with two render steps is refused, not silently truncated.

    Fails today: both steps execute and only the first is graded.
    """

    class _TwoRenderStepPlanner(RenderPlanner):
        def _resolve_steps(self, intent, parsed, scene_context):
            return [
                RenderStep(
                    handler="render_sequence",
                    params={"start_frame": 1, "end_frame": 1},
                    description="First render",
                ),
                RenderStep(
                    handler="render_sequence",
                    params={"start_frame": 2, "end_frame": 2},
                    description="Second render",
                ),
            ]

    handler = AsyncMock()
    handler.call = AsyncMock(return_value={"frame_results": []})
    validator = MagicMock()
    validator.validate = AsyncMock(return_value=[])

    driver = AutonomousDriver(
        planner=_TwoRenderStepPlanner(),
        validator=validator,
        evaluator=_stub_evaluator(),
        handler_interface=handler,
        max_iterations=3,
    )

    report = await driver.execute("render frames 1-2")

    handler.call.assert_not_awaited()
    validator.validate.assert_not_awaited()
    assert report.iterations == 0
    assert report.success is False
    assert report.stop_reason == "unsupported_plan_shape"
    # R4b: nothing was dispatched, so the executed state carries no check
    # results -- the planner's declarations are not evidence of a run.
    assert report.executed is not None
    assert report.executed is not report.plan
    assert report.executed.validation_checks == []
    assert all(step.status == StepStatus.PENDING for step in report.executed.steps)
    assert len(report.plan.validation_checks) == 8


@pytest.mark.asyncio
async def test_original_plan_is_not_mutated():
    """The artist's plan survives execution intact and is what the report carries.

    Fails today: validation_checks, step status/result are written onto the
    plan, and ``report.plan`` is the rebound retry plan.
    """

    class _RecordingPlanner(RenderPlanner):
        def __init__(self):
            super().__init__()
            self.captured = None

        def plan(self, intent, scene_context=None):
            self.captured = super().plan(intent, scene_context)
            return self.captured

    planner = _RecordingPlanner()
    handler = _ScriptedRenderHandler(failures={1: {3}})
    driver = _make_driver(handler, planner=planner)

    report = await driver.execute("re-render frames 1, 3")

    original = planner.captured
    assert report.plan is original

    render_step = original.steps[0]
    assert render_step.params["start_frame"] == 1
    assert render_step.params["end_frame"] == 3
    assert render_step.params["frames"] == [1, 3]
    assert all(step.status == StepStatus.PENDING for step in original.steps)
    assert len(original.validation_checks) == 8, (
        "the run must not overwrite the plan's declared checks"
    )


@pytest.mark.asyncio
async def test_report_carries_the_declared_plan_and_the_executed_state():
    """The report must separate what was asked for from what actually ran.

    Fails today: ``report.plan`` is the artist's unexecuted plan, and the
    validation results and step status/result that execution wrote live only
    on the discarded execution copy. A consumer reading ``report.plan`` sees
    the planner's declared checks (``passed=False``) and no proof a step ran.
    """
    handler = _ScriptedRenderHandler(failures={1: {3}})
    driver = _make_driver(handler)

    report = await driver.execute("re-render frames 1, 3")

    # The artist's plan keeps the planner's declarations, untouched.
    declared = {c.name: c for c in report.plan.validation_checks}
    assert len(declared) == 8
    assert all(c.passed is False for c in report.plan.validation_checks)

    # The executed state carries the results of the checks that actually ran.
    executed = {c.name: c for c in report.executed.validation_checks}
    assert set(executed) == set(declared)
    assert executed["camera"].passed is True
    assert executed["camera"].message, "an executed check carries the run's message"
    assert executed["output_path"].passed is False  # no output path in the fake scene

    assert report.executed is not report.plan


@pytest.mark.asyncio
async def test_executed_state_reports_the_step_statuses_that_ran():
    """The executed copy must show completed steps, not the planner's pending ones.

    Fails today: there is no executed state on the report, so a consumer reads
    the artist's plan -- every step still ``PENDING`` as if nothing had run.
    """
    handler = _ScriptedRenderHandler(failures={1: {3}})
    driver = _make_driver(handler)

    report = await driver.execute("re-render frames 1, 3")

    assert report.executed.steps
    assert all(
        step.status != StepStatus.PENDING for step in report.executed.steps
    ), "executed steps must report what happened, not what was planned"

    render_step = report.executed.steps[0]
    assert render_step.status == StepStatus.COMPLETED
    assert render_step.result is not None
    assert render_step.result["frame_results"], "the step result carries the render"

    # The artist's plan still shows nothing ran.
    assert all(step.status == StepStatus.PENDING for step in report.plan.steps)


@pytest.mark.asyncio
async def test_executed_state_reports_a_skipped_step_after_cancel():
    """A cancelled run leaves completed/skipped steps in the executed copy.

    Fails today: with no executed state, a cancelled report shows every step
    pending, so a consumer cannot tell a cancelled render from an unstarted one.
    """

    class _TwoStepPlanner(RenderPlanner):
        def _resolve_steps(self, intent, parsed, scene_context):
            return [
                RenderStep(
                    handler="set_render_settings",
                    params={"action": "get"},
                    description="Read settings",
                ),
                RenderStep(
                    handler="render_sequence",
                    params={"start_frame": 1, "end_frame": 1, "frames": [1]},
                    description="Render frame 1",
                ),
            ]

    class _CancellingHandler:
        def __init__(self):
            self.driver = None

        async def call(self, name, params):
            if name == "get_stage_info":
                return {"cameras": ["/c"], "renderable_prims": 1}
            if name == "set_render_settings":
                self.driver.emergency_stop()
            return {}

    from synapse.autonomy.validator import PreFlightValidator

    handler = _CancellingHandler()
    driver = AutonomousDriver(
        planner=_TwoStepPlanner(),
        validator=PreFlightValidator(handler),
        evaluator=_stub_evaluator(),
        handler_interface=handler,
        max_iterations=3,
    )
    handler.driver = driver

    report = await driver.execute("render frame 1")

    assert report.stop_reason == "cancelled"
    statuses = [step.status for step in report.executed.steps]
    assert statuses == [StepStatus.COMPLETED, StepStatus.SKIPPED]


@pytest.mark.asyncio
async def test_wall_clock_stop_after_a_dispatch_reports_that_attempt():
    """A stop between attempts reports the attempt that ran, not a fresh copy.

    Fails today: a replan rebinds ``plan`` to a new, unrun execution copy, so
    the wall-clock break at the top of the next iteration reports pending
    steps and no checks -- while one render was dispatched and failed. The
    report then contradicts itself: nothing ran, says the executed state.
    """

    class _SlowFailingHandler:
        def __init__(self):
            self.calls = []

        async def call(self, name, params):
            if name == "get_stage_info":
                return {"cameras": ["/c"], "renderable_prims": 1}
            if name != "render_sequence":
                return {}
            self.calls.append(dict(params))
            await asyncio.sleep(0.8)
            raise RuntimeError("farm went away")

    handler = _SlowFailingHandler()
    driver = _make_driver(handler, max_wall_clock_seconds=0.5)

    report = await driver.execute("render frames 1-3")

    assert len(handler.calls) == 1, "exactly one render must have been dispatched"
    assert report.iterations == 1
    assert report.stop_reason == "wall_clock_exceeded"
    assert report.success is False

    # The dispatched attempt ran its pre-flight checks and its step failed.
    assert report.executed.validation_checks, (
        "the attempt that ran was validated; the report must not fall back to "
        "the unrun copy a replan left behind"
    )
    assert [step.status for step in report.executed.steps] == [StepStatus.FAILED]
    assert report.executed.steps[0].error == "farm went away"


@pytest.mark.asyncio
async def test_original_plan_is_unchanged_after_two_attempts():
    """Two attempts must leave the artist's plan byte-for-byte as it was planned.

    Stronger than the identity check above: it snapshots every step's params,
    status and result plus every check's verdict at plan time, then proves a
    full retry cycle wrote none of it.
    """

    class _SnapshottingPlanner(RenderPlanner):
        def __init__(self):
            super().__init__()
            self.captured = None
            self.snapshot = None

        def plan(self, intent, scene_context=None):
            self.captured = super().plan(intent, scene_context)
            self.snapshot = self._snapshot(self.captured)
            return self.captured

        @staticmethod
        def _snapshot(plan):
            return (
                [
                    (dict(step.params), step.status, step.result, step.error)
                    for step in plan.steps
                ],
                [
                    (check.name, check.passed, check.message)
                    for check in plan.validation_checks
                ],
                plan.estimated_frames,
                plan.intent,
            )

    planner = _SnapshottingPlanner()
    handler = _ScriptedRenderHandler(failures={1: {3}})
    driver = _make_driver(handler, planner=planner)

    report = await driver.execute("re-render frames 1, 3")

    assert report.iterations == 2, "the first attempt must fail and the second pass"
    assert report.plan is planner.captured
    assert _SnapshottingPlanner._snapshot(planner.captured) == planner.snapshot


@pytest.mark.asyncio
async def test_handler_params_mutation_cannot_reach_the_artists_plan():
    """The execution copy must own its step params, not share the plan's dicts.

    Fails today: ``_execution_copy`` rebuilds each RenderStep with
    ``replace(step)``, which copies the dataclass and leaves ``params``
    pointing at the plan's own dict. A handler that writes into the params it
    was handed therefore rewrites the artist's plan.
    """

    class _ParamMutatingHandler:
        """Writes into the dict it is given, then renders normally."""

        def __init__(self):
            self.seen = []

        async def call(self, name, params):
            if name == "get_stage_info":
                return {"cameras": ["/c"], "renderable_prims": 1}
            if name != "render_sequence":
                return {}

            self.seen.append(dict(params))
            frames = sorted({int(f) for f in (params.get("frames") or [])})
            # A handler is entitled to mutate the dict it was handed. The
            # artist's plan must not be downstream of that dict.
            params["x"] = "mutated"
            params["start_frame"] = 999
            if isinstance(params.get("frames"), list):
                params["frames"].append(99)

            return {
                "total_frames": len(frames),
                "successful_frames": len(frames),
                "failed_frames": 0,
                "frame_results": [
                    {"frame": f, "image_path": f"/tmp/f{f}.exr", "error": ""}
                    for f in frames
                ],
            }

    handler = _ParamMutatingHandler()
    driver = _make_driver(handler)

    report = await driver.execute("re-render frames 1, 3")

    assert handler.seen, "the render step must have been dispatched"
    # The mutation really happened, and it landed on the copy ...
    assert report.executed.steps[0].params["x"] == "mutated"
    # ... never on the artist's plan.
    assert report.plan.steps[0].params == {
        "start_frame": 1,
        "end_frame": 3,
        "frames": [1, 3],
    }


@pytest.mark.asyncio
async def test_gate_rejected_reports_no_executed_checks():
    """A declined plan ran nothing; the report must not claim checks ran.

    Fails today: the pre-dispatch return hands back ``_execution_copy``, which
    carries the planner's 8 declared checks with ``passed=False``. The
    receipt reader counts them as hard failures even though no check ran.

    'render frames 1-200' is a >100-frame range, which the planner raises to
    CONFIRM; with no approval callback the driver auto-rejects.
    """
    handler = _ScriptedRenderHandler()
    driver = _make_driver(handler)

    report = await driver.execute("render frames 1-200")

    assert report.stop_reason == "gate_rejected"
    assert report.success is False
    assert handler.calls == [], "a rejected plan must not dispatch a render"

    # The artist's plan keeps the planner's declarations, untouched.
    assert len(report.plan.validation_checks) == 8
    assert all(c.passed is False for c in report.plan.validation_checks)

    # R4b: no check ran, so there is nothing to report as run.
    assert report.executed is not None
    assert report.executed is not report.plan
    assert report.executed.validation_checks == []
    assert all(step.status == StepStatus.PENDING for step in report.executed.steps)


@pytest.mark.asyncio
async def test_validation_failed_reports_the_validator_check_not_the_declaration():
    """A validation stop reports the check that actually failed.

    This path is the negative control for R4b: it is the one return that
    stops before dispatch *and* really ran the checks, so its executed state
    must carry the validator's verdicts. The planner declares ``passed=False``
    on all 8 checks, so ``renderable_prims`` passing is what proves the
    executed list is the validator's, not the declaration.

    It passes on the parent commit: the pre-dispatch fix must leave it alone.
    """

    class _NoCameraHandler(_ScriptedRenderHandler):
        async def call(self, name, params):
            if name == "get_stage_info":
                return {"cameras": [], "renderable_prims": 1}
            return await super().call(name, params)

    handler = _NoCameraHandler()
    driver = _make_driver(handler)

    report = await driver.execute("render frames 1-2")

    assert report.stop_reason == "validation_failed"
    assert report.iterations == 1
    assert report.success is False
    assert handler.calls == [], "a failed pre-flight must not dispatch a render"

    # The artist's plan still shows the planner's unrun declarations.
    assert len(report.plan.validation_checks) == 8
    assert all(c.passed is False for c in report.plan.validation_checks)

    # The executed state carries the validator's results.
    executed = {c.name: c for c in report.executed.validation_checks}
    assert len(executed) == 8
    assert executed["camera"].passed is False
    assert executed["camera"].message, "an executed check carries the run's message"
    assert executed["renderable_prims"].passed is True, (
        "the executed check is the validator's verdict, not the planner's "
        "declaration (which is passed=False for every check)"
    )


def test_failed_retry_does_not_replace_known_good():
    """A failed retry row must not overwrite an accepted product.

    Defensive unit: ``_accumulate`` is the only writer of the cross-attempt
    accumulator.
    """
    driver = _mock_driver()
    accepted = {
        "frame": 1,
        "output_path": "/tmp/f1.exr",
        "image_data": None,
        "error": "",
    }
    accumulated = {1: accepted}

    driver._accumulate(
        accumulated,
        [{
            "frame": 1,
            "output_path": "",
            "image_data": None,
            "error": "boom",
        }],
    )

    assert accumulated[1]["output_path"] == "/tmp/f1.exr"
    assert any(
        d.context == "accumulated_product_preserved" and "1" in d.decision
        for d in driver._decisions
    )
