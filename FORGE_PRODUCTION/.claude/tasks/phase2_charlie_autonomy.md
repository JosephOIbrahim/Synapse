# TEAM CHARLIE — Phase 2: Autonomy Layer

> **File ownership:** `synapse/agent/`, `synapse/render_farm.py`, `synapse/autonomy/` (new)
> **Do NOT modify:** handlers_*.py, mcp/, rag/, routing/, tests/

## Context

Read these first:
- `CLAUDE.md` (project conventions, safety middleware, gate levels)
- `docs/forge/FORGE_PRODUCTION.md` (your deliverables)
- `.claude/agent.md` (conventions for autonomy package)
- `synapse/agent/synapse_agent.py` (existing agent architecture)
- `synapse/agent/synapse_hooks.py` (safety hooks pattern)
- `synapse/agent/synapse_tools.py` (tool registration pattern)
- `synapse/core/guards.py` (gate levels: INFORM, REVIEW, CONFIRM)
- `synapse/memory/` (scene memory system for decision logging)

## Create: `synapse/autonomy/`

```
synapse/autonomy/
├── __init__.py        # Package init, exports public API
├── planner.py         # RenderPlanner
├── validator.py       # PreFlightValidator
├── evaluator.py       # RenderEvaluator
├── driver.py          # AutonomousDriver
└── models.py          # Shared dataclasses
```

---

## Module 1: `models.py` — Shared Data Structures

```python
"""Data models for the autonomy pipeline."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime

class GateLevel(Enum):
    """Gate levels mirror existing guards.py."""
    INFORM = "inform"      # Log, don't ask
    REVIEW = "review"      # Show plan, wait for approval
    CONFIRM = "confirm"    # Require explicit approval per step

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class CheckSeverity(Enum):
    HARD_FAIL = "hard_fail"   # Blocks render
    SOFT_WARN = "soft_warn"   # Warning, artist can override
    INFO = "info"              # Informational only

@dataclass
class RenderStep:
    handler: str              # MCP tool name to call
    params: Dict[str, Any]    # Handler parameters
    description: str          # Human-readable description
    gate: GateLevel = GateLevel.INFORM
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict] = None
    error: Optional[str] = None

@dataclass
class PreFlightCheck:
    name: str
    description: str
    severity: CheckSeverity
    passed: bool = False
    message: str = ""

@dataclass
class RenderPlan:
    intent: str                          # Original artist intent
    steps: List[RenderStep] = field(default_factory=list)
    validation_checks: List[PreFlightCheck] = field(default_factory=list)
    estimated_frames: int = 0
    gate_level: GateLevel = GateLevel.REVIEW
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class FrameEvaluation:
    frame: int
    output_path: str
    passed: bool
    issues: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

@dataclass
class SequenceEvaluation:
    frame_evaluations: List[FrameEvaluation] = field(default_factory=list)
    temporal_issues: List[str] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False

@dataclass
class Decision:
    timestamp: datetime
    context: str
    decision: str
    reasoning: str
    gate_level: GateLevel

@dataclass
class RenderReport:
    plan: RenderPlan
    evaluation: Optional[SequenceEvaluation] = None
    decisions: List[Decision] = field(default_factory=list)
    iterations: int = 0
    total_time_seconds: float = 0.0
    success: bool = False
```

---

## Module 2: `planner.py` — RenderPlanner

### Responsibilities
- Parse artist intent (natural language or structured)
- Decompose into concrete RenderPlan with ordered steps
- Map intent → recipe → handler sequence via routing cascade
- Assign gate levels based on operation risk

### Key methods

```python
class RenderPlanner:
    def __init__(self, routing_cascade, recipe_registry):
        """Takes existing routing and recipe systems."""

    def plan(self, intent: str, scene_context: Optional[dict] = None) -> RenderPlan:
        """Decompose intent into a RenderPlan.

        1. Route intent through routing cascade to find matching recipe
        2. Expand recipe into handler sequence
        3. Add validation checks based on recipe requirements
        4. Estimate frame count from intent or scene context
        5. Assign gate level (REVIEW for first render, INFORM for re-renders)
        """

    def replan(self, original_plan: RenderPlan, evaluation: SequenceEvaluation) -> RenderPlan:
        """Create a revised plan based on evaluation results.

        Used in the feedback loop — evaluator found issues, planner adjusts.
        Only re-render failed frames. Adjust settings based on issues
        (e.g., increase samples if noise detected).
        """
```

### Intent patterns to handle
- "render frame 1" → single frame render
- "render frames 1-48" → sequence render
- "render turntable" → turntable recipe
- "render with ARRI Alexa at 50mm" → camera match + render (Phase 4)
- "re-render frames 12, 17, 23" → partial re-render

### Gate level assignment
- First render of session → REVIEW
- Re-render (same scene, adjusted params) → INFORM
- Destructive operation (delete existing renders) → CONFIRM
- Recipe with many steps → REVIEW

---

## Module 3: `validator.py` — PreFlightValidator

### Responsibilities
- Run BEFORE any render executes
- Check scene readiness via existing handlers
- Return ValidationReport with pass/fail per check

### Checks to implement

```python
class PreFlightValidator:
    def __init__(self, handler_interface):
        """Takes the MCP handler call interface."""

    async def validate(self, plan: RenderPlan) -> List[PreFlightCheck]:
        """Run all pre-flight checks. Returns updated check list."""

    async def _check_camera(self, plan: RenderPlan) -> PreFlightCheck:
        """HARD_FAIL if no camera exists or camera path is invalid."""

    async def _check_renderable_prims(self, plan: RenderPlan) -> PreFlightCheck:
        """HARD_FAIL if stage has no renderable geometry."""

    async def _check_materials(self, plan: RenderPlan) -> PreFlightCheck:
        """SOFT_WARN if any renderable prims have no material assignment."""

    async def _check_render_settings(self, plan: RenderPlan) -> PreFlightCheck:
        """SOFT_WARN if resolution too low, samples too low, etc."""

    async def _check_frame_range(self, plan: RenderPlan) -> PreFlightCheck:
        """HARD_FAIL if frame range invalid (start > end, negative)."""

    async def _check_output_path(self, plan: RenderPlan) -> PreFlightCheck:
        """SOFT_WARN if output directory doesn't exist or no write permission."""

    async def _check_solaris_ordering(self, plan: RenderPlan) -> PreFlightCheck:
        """SOFT_WARN if ambiguous LOP merge points detected.
        (Phase 3 will add the actual handler — stub this for now.)"""

    async def _check_missing_assets(self, plan: RenderPlan) -> PreFlightCheck:
        """SOFT_WARN if USD composition has unresolved references."""
```

### Failure handling
- Any HARD_FAIL → render blocked, report to artist
- SOFT_WARN → report warning, artist can override, render proceeds
- INFO → logged only

---

## Module 4: `evaluator.py` — RenderEvaluator

### Responsibilities
- Run AFTER render completes
- Evaluate per-frame quality + sequence coherence
- Return SequenceEvaluation

### Per-frame checks

```python
class RenderEvaluator:
    def __init__(self, quality_threshold: float = 0.85):
        """Quality threshold: 0.0-1.0, frames below this are flagged."""

    def evaluate_frame(self, frame: int, output_path: str) -> FrameEvaluation:
        """Evaluate a single rendered frame."""

    def _check_black_frame(self, pixels) -> Optional[str]:
        """Flag if >95% of pixels are near-black (< 0.001)."""

    def _check_nan_inf(self, pixels) -> Optional[str]:
        """Flag if any pixels contain NaN or Inf values."""

    def _check_fireflies(self, pixels) -> Optional[str]:
        """Flag statistical outlier pixels (>10 std devs from mean)."""

    def _check_clipping(self, pixels) -> Optional[str]:
        """Flag if >5% of pixels are pure white (overexposure)
        or pure black (underexposure)."""

    def evaluate_sequence(self, frame_evaluations: List[FrameEvaluation]) -> SequenceEvaluation:
        """Evaluate temporal coherence across the sequence."""

    def _check_flickering(self, evaluations: List[FrameEvaluation]) -> List[str]:
        """Detect high-frequency luminance changes between consecutive frames.
        Use frame-to-frame mean luminance delta. Flag if delta > threshold."""

    def _check_motion_continuity(self, evaluations: List[FrameEvaluation]) -> List[str]:
        """Detect large unexpected jumps in frame content.
        Use frame-to-frame SSIM or pixel difference. Flag discontinuities."""

    def _check_missing_frames(self, evaluations: List[FrameEvaluation]) -> List[str]:
        """Detect gaps in the sequence (missing frame numbers)."""
```

### Image loading
- Use OpenEXR (pyexr or OpenImageIO) for EXR files
- Fall back to PIL/Pillow for PNG/JPEG
- If neither available, skip pixel-level checks and report "evaluation skipped — no image library"

### Quality score
```
frame_score = 1.0 - (0.25 * per_issue)  # Each issue reduces score by 0.25
sequence_score = mean(frame_scores) * temporal_coherence_factor
```

---

## Module 5: `driver.py` — AutonomousDriver

### Responsibilities
- Orchestrate the full loop: Plan → Validate → Execute → Evaluate → Report
- Gate system integration
- Checkpoint/resume
- Decision logging
- Max iteration limit

### Main loop

```python
class AutonomousDriver:
    def __init__(self, planner, validator, evaluator, handler_interface,
                 memory_system, max_iterations: int = 3):
        self.decisions: List[Decision] = []

    async def execute(self, intent: str) -> RenderReport:
        """Main autonomous render loop.

        1. Plan: planner.plan(intent)
        2. Gate check: if plan.gate_level >= REVIEW, present to artist
        3. Validate: validator.validate(plan)
           - HARD_FAIL → stop, report
           - SOFT_WARN → log, continue (unless artist overrides)
        4. Execute: call tops_render_sequence via handler interface
        5. Monitor: subscribe to tops_monitor_stream events
        6. Evaluate: evaluator.evaluate_sequence(results)
        7. If evaluation fails and iterations < max:
           a. replan = planner.replan(plan, evaluation)
           b. Log decision: "Re-rendering because {reason}"
           c. Go to step 3 with replan
        8. Report: compile RenderReport with all decisions
        """

    def _checkpoint(self, step: str, state: dict):
        """Save checkpoint for resume capability.
        Store in scene memory via existing memory system."""

    def _resume(self, checkpoint_id: str) -> Optional[dict]:
        """Resume from a checkpoint."""

    def _log_decision(self, context: str, decision: str, reasoning: str,
                      gate: GateLevel = GateLevel.INFORM):
        """Log every non-trivial decision."""
        self.decisions.append(Decision(
            timestamp=datetime.now(),
            context=context, decision=decision,
            reasoning=reasoning, gate_level=gate
        ))

    async def _present_for_approval(self, plan: RenderPlan) -> bool:
        """Present plan to artist for REVIEW/CONFIRM gates.
        Uses existing gate system from guards.py."""

    async def emergency_stop(self):
        """Cancel all work items immediately.
        Calls existing tops_cancel handler."""
```

### Gate behavior
| Gate Level | First Render | Re-render | Destructive |
|-----------|-------------|-----------|-------------|
| INFORM | ❌ | ✅ | ❌ |
| REVIEW | ✅ | ❌ | ❌ |
| CONFIRM | ❌ | ❌ | ✅ |

### Decision log example
```json
{
    "timestamp": "2026-02-18T15:30:00",
    "context": "Frame evaluation: 3 of 48 frames flagged (frames 12, 17, 23)",
    "decision": "Re-render flagged frames with 2x samples",
    "reasoning": "Firefly detection triggered on frames 12, 17, 23. Increasing samples from 128 to 256 should resolve. Other 45 frames passed quality threshold.",
    "gate_level": "inform"
}
```

---

## `__init__.py`

```python
"""SYNAPSE Autonomy Pipeline — autonomous render loop."""
from .models import (
    GateLevel, StepStatus, CheckSeverity,
    RenderStep, PreFlightCheck, RenderPlan,
    FrameEvaluation, SequenceEvaluation, Decision, RenderReport
)
from .planner import RenderPlanner
from .validator import PreFlightValidator
from .evaluator import RenderEvaluator
from .driver import AutonomousDriver

__all__ = [
    "GateLevel", "StepStatus", "CheckSeverity",
    "RenderStep", "PreFlightCheck", "RenderPlan",
    "FrameEvaluation", "SequenceEvaluation", "Decision", "RenderReport",
    "RenderPlanner", "PreFlightValidator", "RenderEvaluator", "AutonomousDriver",
]
```

---

## Integration Points

| This module | Calls | Via |
|-------------|-------|-----|
| Planner | `routing/recipes.py` | Import recipe registry |
| Planner | routing cascade | Import from `routing/` |
| Validator | MCP handlers (`get_stage_info`, etc.) | Handler interface (passed to constructor) |
| Evaluator | File system (rendered frames) | Direct file read |
| Driver | `tops_render_sequence` | Handler interface |
| Driver | `tops_monitor_stream` | Handler interface |
| Driver | Scene memory | Import from `memory/` |
| Driver | Gate system | Import from `core/guards.py` |

**Handler interface pattern:** Don't call handlers directly. Use the same interface the MCP server uses — this keeps autonomy testable with mocks.

---

## Done Criteria

- [ ] `synapse/autonomy/` package created with all 6 files
- [ ] All classes have type hints and docstrings
- [ ] Dataclass-based interfaces (no raw dicts in public API)
- [ ] Integration with existing routing, guards, memory systems
- [ ] Decision logging on every non-trivial choice
- [ ] Checkpoint/resume capability in driver
- [ ] Max iteration limit respected
- [ ] Emergency stop wired to existing TOPS cancel
- [ ] Existing tests still pass
- [ ] Report: public API summary, integration points, any architectural questions
