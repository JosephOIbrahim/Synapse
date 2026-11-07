"""
Synapse Autonomy Pipeline — Render Plan Truth Tests

The plan's product set must be the artist's request, exactly: no invented
intermediate frames, no silently dropped frames, and no retry graded against
a rewritten plan.

Run without Houdini:
    python -m pytest tests/test_render_plan_truth.py -v
"""

import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add package to path (same idiom as the neighbouring autonomy tests)
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.autonomy.models import (
    RenderPlan,
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


def _make_driver(handler, planner=None, evaluator=None, max_iterations=3):
    from synapse.autonomy.validator import PreFlightValidator

    return AutonomousDriver(
        planner=planner or RenderPlanner(),
        validator=PreFlightValidator(handler),
        evaluator=evaluator or _stub_evaluator(),
        handler_interface=handler,
        max_iterations=max_iterations,
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
