"""
Synapse Autonomy Pipeline — Planner Tests

Tests for synapse.autonomy.planner.RenderPlanner.
Run without Houdini:
    python -m pytest tests/test_autonomy_planner.py -v
"""

import sys
import os
from unittest.mock import MagicMock

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.autonomy.models import (
    GateLevel,
    StepStatus,
    RenderPlan,
    RenderStep,
    FrameEvaluation,
    SequenceEvaluation,
)
from synapse.autonomy.planner import RenderPlanner


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_routing():
    """Mock routing cascade that returns recipe-style results."""
    routing = MagicMock()
    routing.route = MagicMock(return_value=MagicMock(steps=None))
    # Make hasattr(result, "steps") True but result.steps falsy so it falls through
    routing.route.return_value.steps = None
    return routing


@pytest.fixture
def mock_recipe_registry():
    """Mock recipe registry with known recipes."""
    registry = MagicMock()
    registry.match = MagicMock(return_value=None)
    return registry


@pytest.fixture
def planner(mock_routing, mock_recipe_registry):
    return RenderPlanner(mock_routing, mock_recipe_registry)


# =============================================================================
# PLAN CREATION TESTS
# =============================================================================


class TestPlanCreation:
    """Tests for RenderPlanner.plan()."""

    def test_simple_render_plan(self, planner):
        """'render frame 1' produces a plan with at least one step."""
        plan = planner.plan("render frame 1")
        assert isinstance(plan, RenderPlan)
        assert plan.intent == "render frame 1"
        assert len(plan.steps) >= 1
        assert plan.estimated_frames == 1

    def test_sequence_render_plan(self, planner):
        """'render frames 1-48' produces a plan with frame range."""
        plan = planner.plan("render frames 1-48")
        assert plan.estimated_frames == 48
        assert len(plan.steps) >= 1

    def test_turntable_plan(self, planner):
        """'render turntable' produces a 48-frame plan."""
        plan = planner.plan("render turntable")
        assert plan.intent == "render turntable"
        assert plan.estimated_frames == 48
        assert len(plan.steps) >= 1

    def test_invalid_intent(self, planner):
        """Empty intent returns a plan with 'unknown' kind and 0 estimated frames."""
        plan = planner.plan("")
        assert isinstance(plan, RenderPlan)
        assert plan.estimated_frames == 0

    def test_plan_gate_levels(self, planner):
        """First plan defaults to REVIEW gate level for single frame."""
        plan = planner.plan("render frame 1")
        assert plan.gate_level == GateLevel.REVIEW

    def test_plan_step_ordering(self, planner):
        """Default steps follow validate -> render_sequence ordering."""
        plan = planner.plan("render frame 1")
        handler_names = [s.handler for s in plan.steps]
        # validate_frame should come before render_sequence
        if "validate_frame" in handler_names and "render_sequence" in handler_names:
            assert handler_names.index("validate_frame") < handler_names.index("render_sequence")

    def test_plan_with_scene_context(self, planner):
        """Scene context is accepted and passed to routing."""
        context = {"camera": "/cameras/cam1", "frame_range": "1-24"}
        plan = planner.plan("render frame 1", scene_context=context)
        assert isinstance(plan, RenderPlan)

    def test_plan_estimated_frames(self, planner):
        """Frame count matches intent for range."""
        plan = planner.plan("render frames 10-20")
        assert plan.estimated_frames == 11

    def test_plan_has_validation_checks(self, planner):
        """Plan should include standard validation checks."""
        plan = planner.plan("render frame 1")
        assert len(plan.validation_checks) == 8
        check_names = {c.name for c in plan.validation_checks}
        assert "camera" in check_names
        assert "renderable_prims" in check_names

    def test_turntable_gate_review(self, planner):
        """Turntable render uses REVIEW gate."""
        plan = planner.plan("render turntable")
        assert plan.gate_level == GateLevel.REVIEW


# =============================================================================
# REPLAN TESTS
# =============================================================================


class TestReplan:
    """Tests for RenderPlanner.replan()."""

    def test_rerender_plan(self, planner):
        """Evaluation with bad frames produces a targeted replan."""
        original = RenderPlan(
            intent="render frames 1-10",
            steps=[
                RenderStep(handler="render_sequence", params={"start_frame": 1, "end_frame": 10},
                           description="Render all"),
            ],
            estimated_frames=10,
        )
        bad_evals = [
            FrameEvaluation(frame=3, output_path="/tmp/3.exr", passed=False, issues=["fireflies"]),
            FrameEvaluation(frame=7, output_path="/tmp/7.exr", passed=False, issues=["black_frame"]),
            FrameEvaluation(frame=9, output_path="/tmp/9.exr", passed=False, issues=["nan_detected"]),
        ]
        good_evals = [
            FrameEvaluation(frame=i, output_path=f"/tmp/{i}.exr", passed=True)
            for i in range(1, 11) if i not in (3, 7, 9)
        ]
        seq_eval = SequenceEvaluation(
            frame_evaluations=bad_evals + good_evals,
            overall_score=0.7,
            passed=False,
        )
        replan = planner.replan(original, seq_eval)
        assert isinstance(replan, RenderPlan)
        assert replan.estimated_frames == 3  # Only the 3 failed frames
        assert len(replan.steps) >= 1

    def test_replan_gate_level(self, planner):
        """Replan should use INFORM gate (not REVIEW) since artist already approved."""
        original = RenderPlan(intent="render frame 1", estimated_frames=1)
        seq_eval = SequenceEvaluation(
            frame_evaluations=[
                FrameEvaluation(frame=1, output_path="/tmp/1.exr", passed=False,
                                issues=["noise"]),
            ],
            overall_score=0.5,
            passed=False,
        )
        replan = planner.replan(original, seq_eval)
        assert replan.gate_level == GateLevel.INFORM

    def test_replan_increases_samples_on_fireflies(self, planner):
        """Firefly issues in evaluation lead to higher sample counts in adjustments."""
        original = RenderPlan(
            intent="render frame 1",
            steps=[
                RenderStep(handler="render_settings", params={"samples": 32},
                           description="Set render settings"),
                RenderStep(handler="render_sequence", params={"start_frame": 1, "end_frame": 1},
                           description="Render"),
            ],
            estimated_frames=1,
        )
        seq_eval = SequenceEvaluation(
            frame_evaluations=[
                FrameEvaluation(
                    frame=1, output_path="/tmp/1.exr", passed=False,
                    issues=["Detected 5 firefly pixel(s)"],
                ),
            ],
            overall_score=0.4,
            passed=False,
        )
        replan = planner.replan(original, seq_eval)
        assert isinstance(replan, RenderPlan)
        # Should have a render_settings step with increased samples
        settings_steps = [s for s in replan.steps if s.handler == "render_settings"]
        assert len(settings_steps) >= 1
        assert settings_steps[0].params.get("pixel_samples", 0) >= 64

    def test_replan_all_passed_returns_original(self, planner):
        """If all frames passed, replan returns the original plan."""
        original = RenderPlan(intent="render frame 1", estimated_frames=1)
        seq_eval = SequenceEvaluation(
            frame_evaluations=[
                FrameEvaluation(frame=1, output_path="/tmp/1.exr", passed=True),
            ],
            overall_score=0.95,
            passed=True,
        )
        replan = planner.replan(original, seq_eval)
        assert replan is original
