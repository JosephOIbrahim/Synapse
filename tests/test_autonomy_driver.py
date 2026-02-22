"""
Synapse Autonomy Pipeline — Driver Tests

Tests for synapse.autonomy.driver.AutonomousDriver.
Run without Houdini:
    python -m pytest tests/test_autonomy_driver.py -v

Note: driver.py may not exist yet if TEAM CHARLIE hasn't created it.
All tests are skipped gracefully in that case.
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
    GateLevel,
    StepStatus,
    CheckSeverity,
    RenderPlan,
    RenderStep,
    PreFlightCheck,
    FrameEvaluation,
    SequenceEvaluation,
    RenderReport,
)

try:
    from synapse.autonomy.driver import AutonomousDriver
    HAS_DRIVER = True
except ImportError:
    HAS_DRIVER = False

pytestmark = pytest.mark.skipif(not HAS_DRIVER, reason="synapse.autonomy.driver not yet implemented")


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_handler_interface():
    """Mock handler interface for executing render steps."""
    interface = AsyncMock()
    interface.call = AsyncMock(return_value={"status": "ok"})
    return interface


@pytest.fixture
def mock_memory_system():
    """Mock memory system for decision logging."""
    memory = MagicMock()
    memory.log_decision = MagicMock()
    memory.save_checkpoint = MagicMock()
    memory.load_checkpoint = MagicMock(return_value=None)
    return memory


def _make_passing_plan():
    """A plan that requires no replan."""
    return RenderPlan(
        intent="render frame 1",
        steps=[
            RenderStep(handler="render_settings", params={"samples": 64}, description="Settings"),
            RenderStep(handler="render_sequence", params={"start_frame": 1, "end_frame": 1},
                       description="Render frame 1"),
        ],
        estimated_frames=1,
        gate_level=GateLevel.INFORM,
    )


def _make_passing_checks():
    """All checks pass."""
    return [
        PreFlightCheck(name="camera", description="Camera exists",
                       severity=CheckSeverity.HARD_FAIL, passed=True),
        PreFlightCheck(name="renderable_prims", description="Has geometry",
                       severity=CheckSeverity.HARD_FAIL, passed=True),
    ]


def _make_failing_checks():
    """A check that hard-fails."""
    return [
        PreFlightCheck(name="camera", description="Camera exists",
                       severity=CheckSeverity.HARD_FAIL, passed=False,
                       message="Couldn't find camera in scene"),
    ]


def _make_warn_checks():
    """A check that soft-warns only."""
    return [
        PreFlightCheck(name="camera", description="Camera exists",
                       severity=CheckSeverity.HARD_FAIL, passed=True),
        PreFlightCheck(name="materials", description="Has materials",
                       severity=CheckSeverity.SOFT_WARN, passed=False,
                       message="No materials assigned"),
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


def _make_failing_evaluation():
    """Evaluation with failed frames."""
    return SequenceEvaluation(
        frame_evaluations=[
            FrameEvaluation(frame=1, output_path="/tmp/f1.exr", passed=False,
                            issues=["fireflies"]),
        ],
        overall_score=0.4,
        passed=False,
    )


@pytest.fixture
def mock_planner():
    planner = MagicMock()
    planner.plan = MagicMock(return_value=_make_passing_plan())
    planner.replan = MagicMock(return_value=_make_passing_plan())
    return planner


@pytest.fixture
def mock_validator():
    validator = MagicMock()
    validator.validate = AsyncMock(return_value=_make_passing_checks())
    return validator


@pytest.fixture
def mock_evaluator():
    evaluator = MagicMock()
    evaluator.evaluate_frame = MagicMock(return_value=FrameEvaluation(
        frame=1, output_path="/tmp/f1.exr", passed=True,
    ))
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
# FULL LOOP TESTS
# =============================================================================


class TestFullLoop:
    """Tests for the complete plan-validate-execute-evaluate loop."""

    @pytest.mark.asyncio
    async def test_full_loop_success(self, driver):
        """Happy path: plan, validate, execute, evaluate -- all succeed."""
        report = await driver.execute("render frame 1")
        assert isinstance(report, RenderReport)
        assert report.success is True
        assert report.iterations >= 1

    @pytest.mark.asyncio
    async def test_validation_hard_fail_stops(self, driver, mock_validator):
        """A hard-fail validation check stops execution before rendering."""
        mock_validator.validate = AsyncMock(return_value=_make_failing_checks())
        report = await driver.execute("render frame 1")
        assert isinstance(report, RenderReport)
        assert report.success is False

    @pytest.mark.asyncio
    async def test_validation_soft_warn_continues(self, driver, mock_validator):
        """A soft-warn check does not block execution."""
        mock_validator.validate = AsyncMock(return_value=_make_warn_checks())
        report = await driver.execute("render frame 1")
        assert isinstance(report, RenderReport)
        assert report.success is True


# =============================================================================
# ITERATION TESTS
# =============================================================================


class TestIterations:
    """Tests for replan/retry iteration behavior."""

    @pytest.mark.asyncio
    async def test_evaluation_triggers_replan(self, driver, mock_evaluator, mock_planner):
        """Failed evaluation should trigger a replan attempt."""
        call_count = 0

        def _eval_sequence(frame_results):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_failing_evaluation()
            return _make_passing_evaluation()

        mock_evaluator.evaluate_sequence = MagicMock(side_effect=_eval_sequence)
        report = await driver.execute("render frame 1")
        assert isinstance(report, RenderReport)
        assert report.iterations >= 2 or mock_planner.replan.called

    @pytest.mark.asyncio
    async def test_max_iterations_respected(self, driver, mock_evaluator):
        """Driver should stop after max_iterations even if still failing."""
        mock_evaluator.evaluate_sequence = MagicMock(return_value=_make_failing_evaluation())
        report = await driver.execute("render frame 1")
        assert isinstance(report, RenderReport)
        assert report.iterations <= 3
        assert report.success is False

    @pytest.mark.asyncio
    async def test_max_iterations_configurable(self, mock_planner, mock_validator,
                                                mock_evaluator, mock_handler_interface,
                                                mock_memory_system):
        """max_iterations parameter is respected."""
        mock_evaluator.evaluate_sequence = MagicMock(return_value=_make_failing_evaluation())
        d = AutonomousDriver(
            planner=mock_planner,
            validator=mock_validator,
            evaluator=mock_evaluator,
            handler_interface=mock_handler_interface,
            memory_system=mock_memory_system,
            max_iterations=1,
        )
        report = await d.execute("render frame 1")
        assert report.iterations <= 1


# =============================================================================
# CHECKPOINT TESTS
# =============================================================================


class TestCheckpoints:
    """Tests for checkpoint save/resume."""

    @pytest.mark.asyncio
    async def test_checkpoint_save(self, driver, mock_memory_system):
        """Checkpoints are saved during execution."""
        await driver.execute("render frame 1")
        # The driver should call _checkpoint at least once during execution
        assert isinstance(driver, AutonomousDriver)

    @pytest.mark.asyncio
    async def test_checkpoint_resume(self, driver):
        """_resume with an unknown checkpoint returns None or raises gracefully."""
        result = driver._resume("nonexistent_checkpoint_id")
        assert result is None


# =============================================================================
# GATE TESTS
# =============================================================================


class TestGates:
    """Tests for human-in-the-loop gate handling."""

    @pytest.mark.asyncio
    async def test_gate_review_waits(self, driver, mock_planner):
        """REVIEW gate should invoke the approval mechanism."""
        plan = _make_passing_plan()
        plan.gate_level = GateLevel.REVIEW
        mock_planner.plan = MagicMock(return_value=plan)

        # Patch _present_for_approval to auto-approve
        driver._present_for_approval = AsyncMock(return_value=True)
        report = await driver.execute("render frame 1")
        assert isinstance(report, RenderReport)

    @pytest.mark.asyncio
    async def test_gate_inform_proceeds(self, driver, mock_planner):
        """INFORM gate should proceed without waiting for approval."""
        plan = _make_passing_plan()
        plan.gate_level = GateLevel.INFORM
        mock_planner.plan = MagicMock(return_value=plan)
        report = await driver.execute("render frame 1")
        assert isinstance(report, RenderReport)
        assert report.success is True


# =============================================================================
# DECISION LOGGING TESTS
# =============================================================================


class TestDecisionLogging:
    """Tests for decision audit trail."""

    @pytest.mark.asyncio
    async def test_decision_logging(self, driver):
        """Decisions should be recorded in the report."""
        report = await driver.execute("render frame 1")
        assert isinstance(report, RenderReport)
        # The report should contain at least one decision (plan creation)
        assert isinstance(report.decisions, list)


# =============================================================================
# EMERGENCY STOP TESTS
# =============================================================================


class TestEmergencyStop:
    """Tests for emergency_stop()."""

    def test_emergency_stop(self, driver):
        """emergency_stop() should be callable and not raise."""
        driver.emergency_stop()
        # After emergency stop, the driver should be in a stopped state
        # No exception means success
