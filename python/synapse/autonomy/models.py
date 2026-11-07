"""
Synapse Autonomy Pipeline — Data Models

Shared data structures for the autonomous render loop:
Plan -> Validate -> Execute -> Evaluate -> Report.

All models are stdlib-only dataclasses with full type hints.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class GateLevel(Enum):
    """Approval requirement for an autonomous step.

    Mirrors core.gates.GateLevel but scoped to the autonomy pipeline
    to avoid tight coupling. Maps 1:1 when bridging to the gate system.
    """
    INFORM = "inform"
    REVIEW = "review"
    CONFIRM = "confirm"


class StepStatus(Enum):
    """Execution status of a single render step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CheckSeverity(Enum):
    """How severely a pre-flight check failure affects the pipeline."""
    HARD_FAIL = "hard_fail"   # Blocks execution entirely
    SOFT_WARN = "soft_warn"   # Logs warning, continues
    INFO = "info"             # Informational only


@dataclass
class RenderStep:
    """A single step in a render plan, mapped to a handler call."""
    handler: str
    params: Dict[str, Any]
    description: str
    gate: GateLevel = GateLevel.INFORM
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class PreFlightCheck:
    """Result of a single pre-flight validation check."""
    name: str
    description: str
    severity: CheckSeverity
    passed: bool = False
    message: str = ""


@dataclass
class RenderPlan:
    """A complete render plan with steps and validation metadata."""
    intent: str
    steps: List[RenderStep] = field(default_factory=list)
    validation_checks: List[PreFlightCheck] = field(default_factory=list)
    estimated_frames: int = 0
    gate_level: GateLevel = GateLevel.REVIEW
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class FrameEvaluation:
    """Quality evaluation for a single rendered frame."""
    frame: int
    output_path: str
    passed: bool
    issues: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    verified: bool = True  # False = pixels never analyzed; quality is unknown


@dataclass
class SequenceEvaluation:
    """Quality evaluation for an entire rendered sequence."""
    frame_evaluations: List[FrameEvaluation] = field(default_factory=list)
    temporal_issues: List[str] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False
    unverified_count: int = 0
    pass_threshold: float = 0.7
    # A missing output, a farm-failed frame or a plan mismatch. These fail the
    # sequence outright and are kept apart from temporal_issues so they do not
    # also move the soft score through the temporal factor.
    hard_failures: List[str] = field(default_factory=list)


@dataclass
class Decision:
    """A recorded decision made during the autonomous loop."""
    timestamp: datetime
    context: str
    decision: str
    reasoning: str
    gate_level: GateLevel


@dataclass
class RenderPrediction:
    """Pre-render prediction for verify-after-render comparison.

    Based on 'Predict Before Executing' (2601.05930): predict scene
    structure and expected outputs before rendering, then compare
    actual results to catch discrepancies early.

    Fields split into two groups:
        - Scene structure predictions (filled pre-render)
        - Verification results (filled post-render)
    """
    # Scene structure predictions
    render_product_path: str = ""
    output_file_pattern: str = ""
    expected_frame_range: tuple = (1, 1)
    camera_prim: str = ""
    material_count: int = 0
    light_count: int = 0
    geo_prim_count: int = 0

    # Quality predictions
    expected_resolution: tuple = (1920, 1080)
    has_motion_blur: bool = False
    has_displacement: bool = False
    estimated_render_time_seconds: float = 0.0

    # Pre-render issues found during prediction
    pre_render_issues: List[str] = field(default_factory=list)

    # Verification results (filled post-render)
    actual_output_files: List[str] = field(default_factory=list)
    render_succeeded: bool = False
    discrepancies: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Result of comparing pre-render prediction to post-render reality.

    A high discrepancy count triggers re-evaluation before proceeding
    to the next frame or sequence.
    """
    prediction: RenderPrediction
    evaluation: Optional[SequenceEvaluation] = None
    discrepancies: List[str] = field(default_factory=list)
    score: float = 1.0  # 1.0 = perfect match, 0.0 = total mismatch
    should_rerender: bool = False
    reasoning: str = ""


@dataclass
class RenderReport:
    """Final report from an autonomous render execution.

    ``plan`` is the artist's request exactly as the planner declared it and is
    never rewritten by execution. ``executed`` is the execution copy of the
    **last attempt** -- the most recent copy the driver validated or
    dispatched -- carrying that attempt's validation results and each step's
    status/result. It is not an attempt history: after a two-attempt success
    only the retry's step and checks are here, and the first attempt's result
    is gone.

    A run that stopped before any attempt did anything (gate rejected,
    unsupported shape, or a cancel or wall-clock stop before the first
    validate) carries an **empty** ``validation_checks`` list and leaves
    every step ``PENDING``. The planner's declared checks are a to-do list
    and are never presented as results, so an empty list means "no check
    ran", never "every check passed". A stop that lands between attempts
    keeps the attempt that ran. Ask ``plan`` what was requested; ask
    ``executed`` what last happened.
    """
    plan: RenderPlan
    executed: Optional[RenderPlan] = None
    evaluation: Optional[SequenceEvaluation] = None
    prediction: Optional[RenderPrediction] = None
    verification: Optional[VerificationResult] = None
    decisions: List[Decision] = field(default_factory=list)
    iterations: int = 0
    total_time_seconds: float = 0.0
    success: bool = False
    # M3-E: why the loop ended -- "" (passed), "max_iterations", "cancelled",
    # "wall_clock_exceeded", "gate_rejected", "validation_failed",
    # "unsupported_plan_shape" (more than one render step: no single product
    # set to grade)
    stop_reason: str = ""
