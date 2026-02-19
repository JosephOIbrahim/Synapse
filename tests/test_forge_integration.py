"""
Synapse FORGE — Full Pipeline Integration Tests

End-to-end integration tests for the autonomy driver with all subsystems
mocked. Tests the complete lifecycle: intent -> plan -> validate -> execute ->
evaluate -> report, including feedback loops, checkpoints, and decision logging.

Run without Houdini:
    python -m pytest tests/test_forge_integration.py -v
"""

import sys
import os
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.autonomy.models import (
    RenderPlan,
    RenderStep,
    PreFlightCheck,
    RenderReport,
    FrameEvaluation,
    SequenceEvaluation,
    Decision,
    GateLevel,
    StepStatus,
    CheckSeverity,
)
from synapse.autonomy.planner import RenderPlanner
from synapse.autonomy.validator import PreFlightValidator
from synapse.autonomy.evaluator import RenderEvaluator
from synapse.autonomy.driver import AutonomousDriver


# =============================================================================
# HELPERS
# =============================================================================


def _make_plan(intent="render frame 1", gate=GateLevel.INFORM):
    """Build a standard single-frame render plan."""
    return RenderPlan(
        intent=intent,
        steps=[
            RenderStep(
                handler="render_settings",
                params={"samples": 64},
                description="Apply render settings",
            ),
            RenderStep(
                handler="render_sequence",
                params={"start_frame": 1, "end_frame": 1},
                description="Render frame 1",
            ),
        ],
        estimated_frames=1,
        gate_level=gate,
    )


def _make_passing_checks():
    """All pre-flight checks pass, including solaris ordering."""
    return [
        PreFlightCheck(
            name="camera",
            description="Camera exists",
            severity=CheckSeverity.HARD_FAIL,
            passed=True,
            message="Found 1 camera(s): /cameras/camera1",
        ),
        PreFlightCheck(
            name="renderable_prims",
            description="Has geometry",
            severity=CheckSeverity.HARD_FAIL,
            passed=True,
            message="Found 5 renderable prim(s) on the stage.",
        ),
        PreFlightCheck(
            name="solaris_ordering",
            description="Solaris network ordering check",
            severity=CheckSeverity.INFO,
            passed=True,
            message="No ordering ambiguities detected.",
        ),
    ]


def _make_ordering_warn_checks():
    """Checks pass but with a solaris ordering warning."""
    return [
        PreFlightCheck(
            name="camera",
            description="Camera exists",
            severity=CheckSeverity.HARD_FAIL,
            passed=True,
            message="Found 1 camera(s): /cameras/camera1",
        ),
        PreFlightCheck(
            name="renderable_prims",
            description="Has geometry",
            severity=CheckSeverity.HARD_FAIL,
            passed=True,
        ),
        PreFlightCheck(
            name="solaris_ordering",
            description="Solaris network ordering check",
            severity=CheckSeverity.SOFT_WARN,
            passed=False,
            message="Ordering ambiguities detected: /stage/merge1: ambiguous_merge. "
                    "Review merge order before rendering.",
        ),
    ]


def _make_camera_fail_checks():
    """Camera check hard-fails."""
    return [
        PreFlightCheck(
            name="camera",
            description="Camera exists",
            severity=CheckSeverity.HARD_FAIL,
            passed=False,
            message="Couldn't find a render camera on the stage. "
                    "Add a Camera LOP before rendering.",
        ),
        PreFlightCheck(
            name="renderable_prims",
            description="Has geometry",
            severity=CheckSeverity.HARD_FAIL,
            passed=True,
        ),
    ]


def _make_passing_evaluation():
    """Evaluation where everything passes."""
    return SequenceEvaluation(
        frame_evaluations=[
            FrameEvaluation(frame=1, output_path="/tmp/f1.exr", passed=True),
        ],
        overall_score=0.95,
        passed=True,
    )


def _make_failing_evaluation(issues=None):
    """Evaluation with failed frames."""
    return SequenceEvaluation(
        frame_evaluations=[
            FrameEvaluation(
                frame=1,
                output_path="/tmp/f1.exr",
                passed=False,
                issues=issues or ["fireflies"],
            ),
        ],
        overall_score=0.4,
        passed=False,
    )


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_handler_interface():
    """Mock handler interface for executing render steps."""
    interface = AsyncMock()
    interface.call = AsyncMock(return_value={
        "status": "ok",
        "frames": [{"frame": 1, "output_path": "/tmp/f1.exr"}],
    })
    return interface


@pytest.fixture
def mock_memory_system():
    """Mock memory system for decision logging."""
    memory = MagicMock()
    memory.add = MagicMock()
    memory.log_decision = MagicMock()
    memory.save_checkpoint = MagicMock()
    memory.load_checkpoint = MagicMock(return_value=None)
    return memory


@pytest.fixture
def mock_planner():
    planner = MagicMock(spec=RenderPlanner)
    planner.plan = MagicMock(return_value=_make_plan())
    planner.replan = MagicMock(return_value=_make_plan())
    return planner


@pytest.fixture
def mock_validator():
    validator = MagicMock(spec=PreFlightValidator)
    validator.validate = AsyncMock(return_value=_make_passing_checks())
    return validator


@pytest.fixture
def mock_evaluator():
    evaluator = MagicMock(spec=RenderEvaluator)
    evaluator.evaluate_frame = MagicMock(
        return_value=FrameEvaluation(frame=1, output_path="/tmp/f1.exr", passed=True)
    )
    evaluator.evaluate_sequence = MagicMock(return_value=_make_passing_evaluation())
    return evaluator


@pytest.fixture
def driver(mock_planner, mock_validator, mock_evaluator, mock_handler_interface, mock_memory_system):
    return AutonomousDriver(
        planner=mock_planner,
        validator=mock_validator,
        evaluator=mock_evaluator,
        handler_interface=mock_handler_interface,
        memory_system=mock_memory_system,
        max_iterations=3,
    )


# =============================================================================
# TESTS
# =============================================================================


class TestFullPipelineMock:
    """End-to-end pipeline tests with all subsystems mocked."""

    @pytest.mark.asyncio
    async def test_full_pipeline_mock(self, driver, mock_planner, mock_validator, mock_evaluator):
        """Intent -> plan -> validate -> execute -> evaluate -> report, all pass."""
        report = await driver.execute("render frame 1")

        assert isinstance(report, RenderReport)
        assert report.success is True
        assert report.iterations >= 1

        # Verify each subsystem was called
        mock_planner.plan.assert_called_once_with("render frame 1")
        mock_validator.validate.assert_called()
        mock_evaluator.evaluate_sequence.assert_called()

    @pytest.mark.asyncio
    async def test_pipeline_with_ordering_warning(
        self, mock_planner, mock_evaluator, mock_handler_interface, mock_memory_system
    ):
        """Ambiguous merge detected and reported in validation warnings, pipeline continues."""
        validator = MagicMock(spec=PreFlightValidator)
        validator.validate = AsyncMock(return_value=_make_ordering_warn_checks())

        d = AutonomousDriver(
            planner=mock_planner,
            validator=validator,
            evaluator=mock_evaluator,
            handler_interface=mock_handler_interface,
            memory_system=mock_memory_system,
            max_iterations=3,
        )

        report = await d.execute("render frame 1")

        assert isinstance(report, RenderReport)
        # Soft warnings don't block — pipeline should still succeed
        assert report.success is True
        assert report.iterations >= 1

        # Verify the ordering warning was logged as a decision
        warn_decisions = [
            dec for dec in report.decisions if "warning" in dec.context.lower()
        ]
        assert len(warn_decisions) >= 1
        # The warning decision should mention the ordering issue
        warn_text = " ".join(dec.decision + dec.reasoning for dec in warn_decisions)
        assert "solaris_ordering" in warn_text or "warning" in warn_text.lower()

    @pytest.mark.asyncio
    async def test_pipeline_with_hard_failure(
        self, mock_planner, mock_evaluator, mock_handler_interface, mock_memory_system
    ):
        """Missing camera causes a hard failure — pipeline stops before render."""
        validator = MagicMock(spec=PreFlightValidator)
        validator.validate = AsyncMock(return_value=_make_camera_fail_checks())

        d = AutonomousDriver(
            planner=mock_planner,
            validator=validator,
            evaluator=mock_evaluator,
            handler_interface=mock_handler_interface,
            memory_system=mock_memory_system,
            max_iterations=3,
        )

        report = await d.execute("render frame 1")

        assert isinstance(report, RenderReport)
        assert report.success is False

        # The handler should NOT have been called — pipeline stopped at validation
        # (evaluator also should not be called)
        mock_evaluator.evaluate_sequence.assert_not_called()

        # Decision log should mention the hard failure
        fail_decisions = [
            dec for dec in report.decisions if "validation_failed" in dec.context
        ]
        assert len(fail_decisions) >= 1
        assert "camera" in fail_decisions[0].decision.lower() or "camera" in fail_decisions[0].reasoning.lower()

    @pytest.mark.asyncio
    async def test_pipeline_feedback_loop(
        self, mock_planner, mock_validator, mock_handler_interface, mock_memory_system
    ):
        """Bad frames on first render -> replan -> re-render -> passes on second try."""
        call_count = 0

        def _eval_sequence(frame_results):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_failing_evaluation(issues=["fireflies"])
            return _make_passing_evaluation()

        evaluator = MagicMock(spec=RenderEvaluator)
        evaluator.evaluate_sequence = MagicMock(side_effect=_eval_sequence)

        d = AutonomousDriver(
            planner=mock_planner,
            validator=mock_validator,
            evaluator=evaluator,
            handler_interface=mock_handler_interface,
            memory_system=mock_memory_system,
            max_iterations=3,
        )

        report = await d.execute("render frame 1")

        assert isinstance(report, RenderReport)
        assert report.success is True
        # Should have taken at least 2 iterations (fail + succeed)
        assert report.iterations >= 2
        # Planner should have been asked to replan after first failure
        assert mock_planner.replan.called

    @pytest.mark.asyncio
    async def test_pipeline_decision_log_complete(self, driver):
        """Every step produces at least one Decision entry in the report."""
        report = await driver.execute("render frame 1")

        assert isinstance(report, RenderReport)
        assert isinstance(report.decisions, list)
        assert len(report.decisions) >= 1

        # Should have at least: initial_plan + evaluation_complete/render_success
        contexts = [d.context for d in report.decisions]
        assert "initial_plan" in contexts

        # Every decision must be a valid Decision dataclass
        for dec in report.decisions:
            assert isinstance(dec, Decision)
            assert isinstance(dec.timestamp, datetime)
            assert isinstance(dec.context, str)
            assert isinstance(dec.decision, str)
            assert isinstance(dec.reasoning, str)
            assert isinstance(dec.gate_level, GateLevel)

    @pytest.mark.asyncio
    async def test_pipeline_checkpoint_resume(
        self, mock_planner, mock_validator, mock_evaluator,
        mock_handler_interface, mock_memory_system
    ):
        """Driver saves checkpoints during execution and can query them."""
        d = AutonomousDriver(
            planner=mock_planner,
            validator=mock_validator,
            evaluator=mock_evaluator,
            handler_interface=mock_handler_interface,
            memory_system=mock_memory_system,
            max_iterations=3,
        )

        # Run a full pipeline to generate checkpoints
        report = await d.execute("render frame 1")
        assert report.success is True

        # Verify checkpoints were saved internally
        assert "plan_created" in d._checkpoints
        assert "iteration_1" in d._checkpoints

        # _resume returns state for existing checkpoints
        state = d._resume("plan_created")
        assert state is not None
        assert "plan_intent" in state

        # _resume returns None for nonexistent checkpoints
        assert d._resume("nonexistent_checkpoint_id") is None

    @pytest.mark.asyncio
    async def test_pipeline_max_iterations(
        self, mock_planner, mock_validator, mock_handler_interface, mock_memory_system
    ):
        """3 bad evaluations in a row causes the driver to stop and report all attempts."""
        evaluator = MagicMock(spec=RenderEvaluator)
        evaluator.evaluate_sequence = MagicMock(
            return_value=_make_failing_evaluation(issues=["persistent fireflies"])
        )

        d = AutonomousDriver(
            planner=mock_planner,
            validator=mock_validator,
            evaluator=evaluator,
            handler_interface=mock_handler_interface,
            memory_system=mock_memory_system,
            max_iterations=3,
        )

        report = await d.execute("render frame 1")

        assert isinstance(report, RenderReport)
        assert report.success is False
        assert report.iterations == 3

        # Planner should have been asked to replan after each failure (except last)
        assert mock_planner.replan.call_count >= 2

        # Decision log should include max_iterations context
        contexts = [dec.context for dec in report.decisions]
        assert "max_iterations" in contexts or "replan" in contexts

        # Final evaluation should be present and failing
        assert report.evaluation is not None
        assert report.evaluation.passed is False
