"""
Agent capabilities -- render pipeline wrappers.

Exposes the autonomy pipeline (RenderPlanner, RenderEvaluator, RenderPredictor,
AutonomousDriver) as simple async functions for the agent tool-use loop.

Each function instantiates the relevant autonomy class, calls the appropriate
method, and returns the result. This keeps the agent layer thin -- all logic
lives in the autonomy module.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add the python/ directory to sys.path so we can import synapse.autonomy
_PYTHON_DIR = str(Path(__file__).resolve().parents[2] / "python")
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

from synapse.autonomy.models import (
    RenderPlan,
    RenderPrediction,
    RenderReport,
    SequenceEvaluation,
)
from synapse.autonomy.planner import RenderPlanner
from synapse.autonomy.evaluator import RenderEvaluator
from synapse.autonomy.predictor import RenderPredictor
from synapse.autonomy.validator import PreFlightValidator
from synapse.autonomy.driver import AutonomousDriver


def plan_render(
    intent: str,
    scene_context: Optional[Dict[str, Any]] = None,
) -> RenderPlan:
    """Build a render plan from a natural-language intent.

    Parses the intent into structured render parameters and produces a
    step-by-step RenderPlan with validation checks and gate levels.

    Let me know if the intent doesn't parse cleanly -- we'll figure it out.

    Args:
        intent: Natural-language description of what to render,
            e.g. "render frames 1-48" or "render turntable".
        scene_context: Optional dict with extra scene state for the planner.

    Returns:
        A RenderPlan with steps, validation checks, and gate level.
    """
    planner = RenderPlanner(routing_cascade=None, recipe_registry=None)
    return planner.plan(intent, scene_context=scene_context)


def evaluate_render(
    frame_paths: Dict[int, str],
) -> SequenceEvaluation:
    """Evaluate a rendered sequence from disk.

    Loads each frame, runs per-frame quality checks (black frames, NaN/Inf,
    fireflies, clipping) and sequence-level checks (flickering, motion
    continuity, missing frames).

    Args:
        frame_paths: Dict mapping frame number to file path,
            e.g. {1: "/tmp/frame.0001.exr", 2: "/tmp/frame.0002.exr"}.

    Returns:
        A SequenceEvaluation with per-frame results, temporal issues,
        overall score, and pass/fail status.
    """
    evaluator = RenderEvaluator()
    return evaluator.evaluate_sequence_from_disk(frame_paths)


async def predict_render(
    plan: RenderPlan,
    handler_interface: Any,
) -> RenderPrediction:
    """Predict render outcomes before executing.

    Introspects the USD stage via handler calls to build a prediction of
    expected outputs (camera, lights, materials, resolution, etc.).
    After rendering, use the AutonomousDriver's verify step to compare
    prediction to reality.

    Args:
        plan: The render plan about to be executed.
        handler_interface: Async handler with a
            ``call(tool_name, params) -> dict`` method.

    Returns:
        A RenderPrediction with scene structure predictions and any
        pre-render issues found.
    """
    predictor = RenderPredictor(handler_interface)
    return await predictor.predict(plan)


async def run_autonomous_render(
    intent: str,
    handler_interface: Any,
    memory_system: Any = None,
    max_iterations: int = 3,
) -> RenderReport:
    """Run the full autonomous render loop: plan, validate, execute, evaluate.

    Builds the complete pipeline (planner, validator, evaluator, predictor,
    driver) and executes it end-to-end. The driver handles re-planning on
    evaluation failure up to max_iterations.

    This is the high-level entry point -- for finer control, use the
    individual functions (plan_render, validate_scene, evaluate_render).

    Args:
        intent: Natural-language render intent from the artist.
        handler_interface: Async handler with a
            ``call(tool_name, params) -> dict`` method.
        memory_system: Optional memory system for persisting decisions.
        max_iterations: Maximum re-plan attempts before giving up.

    Returns:
        A RenderReport with plan, evaluation, prediction, verification,
        decisions, iteration count, timing, and success flag.
    """
    planner = RenderPlanner(routing_cascade=None, recipe_registry=None)
    validator = PreFlightValidator(handler_interface)
    evaluator = RenderEvaluator()
    predictor = RenderPredictor(handler_interface)

    driver = AutonomousDriver(
        planner=planner,
        validator=validator,
        evaluator=evaluator,
        handler_interface=handler_interface,
        memory_system=memory_system,
        predictor=predictor,
        max_iterations=max_iterations,
    )

    return await driver.execute(intent)
