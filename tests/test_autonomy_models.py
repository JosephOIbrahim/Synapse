"""
Synapse Autonomy Pipeline — Model Tests

Tests for data classes in synapse.autonomy.models.
Run without Houdini:
    python -m pytest tests/test_autonomy_models.py -v
"""

import sys
import os
from datetime import datetime

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.autonomy.models import (
    GateLevel,
    StepStatus,
    CheckSeverity,
    RenderStep,
    PreFlightCheck,
    RenderPlan,
    FrameEvaluation,
    SequenceEvaluation,
    Decision,
    RenderReport,
)


# =============================================================================
# GATE LEVEL TESTS
# =============================================================================


class TestGateLevel:
    """Tests for GateLevel enum values."""

    def test_gate_level_values(self):
        assert GateLevel.INFORM.value == "inform"
        assert GateLevel.REVIEW.value == "review"
        assert GateLevel.CONFIRM.value == "confirm"

    def test_gate_level_count(self):
        assert len(GateLevel) == 3


# =============================================================================
# STEP STATUS TESTS
# =============================================================================


class TestStepStatus:
    """Tests for StepStatus enum transitions."""

    def test_step_status_values(self):
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_step_status_transitions(self):
        """Status field on RenderStep can change freely (no FSM enforcement)."""
        step = RenderStep(
            handler="render",
            params={"frame": 1},
            description="Render frame 1",
        )
        assert step.status == StepStatus.PENDING
        step.status = StepStatus.RUNNING
        assert step.status == StepStatus.RUNNING
        step.status = StepStatus.COMPLETED
        assert step.status == StepStatus.COMPLETED


# =============================================================================
# RENDER PLAN TESTS
# =============================================================================


class TestRenderPlan:
    """Tests for RenderPlan creation and defaults."""

    def test_render_plan_creation(self):
        plan = RenderPlan(intent="render frame 1")
        assert plan.intent == "render frame 1"
        assert plan.steps == []
        assert plan.validation_checks == []
        assert plan.estimated_frames == 0
        assert plan.gate_level == GateLevel.REVIEW
        assert isinstance(plan.created_at, datetime)

    def test_render_plan_with_steps(self):
        step = RenderStep(
            handler="render",
            params={"frame": 1},
            description="Render frame 1",
        )
        plan = RenderPlan(intent="render frame 1", steps=[step])
        assert len(plan.steps) == 1
        assert plan.steps[0].handler == "render"


# =============================================================================
# PREFLIGHT CHECK TESTS
# =============================================================================


class TestPreFlightCheck:
    """Tests for PreFlightCheck defaults."""

    def test_preflight_check_creation(self):
        check = PreFlightCheck(
            name="camera_exists",
            description="Verify camera exists in scene",
            severity=CheckSeverity.HARD_FAIL,
        )
        assert check.name == "camera_exists"
        assert check.passed is False
        assert check.message == ""
        assert check.severity == CheckSeverity.HARD_FAIL


# =============================================================================
# FRAME EVALUATION TESTS
# =============================================================================


class TestFrameEvaluation:
    """Tests for FrameEvaluation defaults."""

    def test_frame_evaluation_defaults(self):
        ev = FrameEvaluation(frame=1, output_path="/tmp/frame_0001.exr", passed=True)
        assert ev.frame == 1
        assert ev.issues == []
        assert ev.metrics == {}
        assert ev.passed is True

    def test_frame_evaluation_with_issues(self):
        ev = FrameEvaluation(
            frame=5,
            output_path="/tmp/frame_0005.exr",
            passed=False,
            issues=["black_frame", "nan_detected"],
            metrics={"mean_luminance": 0.0},
        )
        assert len(ev.issues) == 2
        assert ev.metrics["mean_luminance"] == 0.0


# =============================================================================
# RENDER REPORT TESTS
# =============================================================================


class TestRenderReport:
    """Tests for RenderReport aggregation."""

    def test_render_report_aggregation(self):
        plan = RenderPlan(intent="render turntable")
        decision = Decision(
            timestamp=datetime.now(),
            context="pre-flight",
            decision="proceed",
            reasoning="All checks passed",
            gate_level=GateLevel.INFORM,
        )
        report = RenderReport(
            plan=plan,
            decisions=[decision],
            iterations=1,
            total_time_seconds=12.5,
            success=True,
        )
        assert report.plan is plan
        assert len(report.decisions) == 1
        assert report.iterations == 1
        assert report.success is True
        assert report.evaluation is None

    def test_render_report_defaults(self):
        plan = RenderPlan(intent="test")
        report = RenderReport(plan=plan)
        assert report.evaluation is None
        assert report.decisions == []
        assert report.iterations == 0
        assert report.total_time_seconds == 0.0
        assert report.success is False
