"""
Synapse Autonomy Pipeline

Autonomous render loop: Plan -> Validate -> Execute -> Evaluate -> Report.

Usage:
    from synapse.autonomy import (
        AutonomousDriver,
        RenderPlanner,
        PreFlightValidator,
        RenderEvaluator,
    )

    driver = AutonomousDriver(
        planner=RenderPlanner(),
        validator=PreFlightValidator(handler_interface),
        evaluator=RenderEvaluator(),
        handler_interface=handler_interface,
    )

    report = await driver.execute("render frames 1-48")
"""

from .models import (
    CheckSeverity,
    Decision,
    FrameEvaluation,
    GateLevel,
    PreFlightCheck,
    RenderPlan,
    RenderPrediction,
    RenderReport,
    RenderStep,
    SequenceEvaluation,
    StepStatus,
    VerificationResult,
)
from .planner import RenderPlanner
from .validator import PreFlightValidator
from .evaluator import RenderEvaluator
from .predictor import RenderPredictor
from .driver import AutonomousDriver

__all__ = [
    # Models
    "CheckSeverity",
    "Decision",
    "FrameEvaluation",
    "GateLevel",
    "PreFlightCheck",
    "RenderPlan",
    "RenderPrediction",
    "RenderReport",
    "RenderStep",
    "SequenceEvaluation",
    "StepStatus",
    "VerificationResult",
    # Core classes
    "AutonomousDriver",
    "RenderEvaluator",
    "RenderPlanner",
    "RenderPredictor",
    "PreFlightValidator",
]
