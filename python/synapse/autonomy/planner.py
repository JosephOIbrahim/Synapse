"""
Synapse Autonomy Pipeline — Render Planner

Parses artist intent into a structured RenderPlan with handler steps,
validation checks, frame estimates, and gate levels.

Uses the existing routing cascade and recipe registry to resolve intent
into concrete handler sequences. stdlib-only.
"""

import re
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .models import (
    CheckSeverity,
    GateLevel,
    PreFlightCheck,
    RenderPlan,
    RenderStep,
    SequenceEvaluation,
)


# ---------------------------------------------------------------------------
# Protocols for dependency injection (no concrete imports)
# ---------------------------------------------------------------------------

class RoutingCascade(Protocol):
    """Minimal interface for the existing routing cascade."""

    def route(self, query: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Route a query through the tiered cascade."""
        ...


class RecipeRegistry(Protocol):
    """Minimal interface for the existing recipe registry."""

    def match(self, query: str) -> Optional[Any]:
        """Match query against registered recipes."""
        ...


# ---------------------------------------------------------------------------
# Intent patterns
# ---------------------------------------------------------------------------

_SINGLE_FRAME_RE = re.compile(
    r"render\s+frame\s+(\d+)", re.IGNORECASE
)
_FRAME_RANGE_RE = re.compile(
    r"render\s+frames?\s+(\d+)\s*[-–]\s*(\d+)", re.IGNORECASE
)
_RERENDER_RE = re.compile(
    r"re-?render\s+frames?\s+([\d,\s]+)", re.IGNORECASE
)
_TURNTABLE_RE = re.compile(
    r"render\s+turntable", re.IGNORECASE
)


def _parse_intent(intent: str) -> Dict[str, Any]:
    """Extract structured render parameters from a natural-language intent.

    Returns a dict with keys:
        kind: "single" | "range" | "rerender" | "turntable" | "unknown"
        frames: list[int]  (explicit frame numbers)
        start / end: int   (for ranges)
    """
    m = _SINGLE_FRAME_RE.search(intent)
    if m:
        frame = int(m.group(1))
        return {"kind": "single", "frames": [frame], "start": frame, "end": frame}

    m = _FRAME_RANGE_RE.search(intent)
    if m:
        start, end = int(m.group(1)), int(m.group(2))
        return {
            "kind": "range",
            "frames": list(range(start, end + 1)),
            "start": start,
            "end": end,
        }

    m = _RERENDER_RE.search(intent)
    if m:
        frames = [int(f.strip()) for f in m.group(1).split(",") if f.strip().isdigit()]
        return {
            "kind": "rerender",
            "frames": frames,
            "start": min(frames) if frames else 1,
            "end": max(frames) if frames else 1,
        }

    if _TURNTABLE_RE.search(intent):
        # Default turntable: 48 frames, full 360-degree rotation
        return {
            "kind": "turntable",
            "frames": list(range(1, 49)),
            "start": 1,
            "end": 48,
        }

    return {"kind": "unknown", "frames": [], "start": 1, "end": 1}


# ---------------------------------------------------------------------------
# The plan's product set
# ---------------------------------------------------------------------------

# Handlers that actually render a product. Everything else in a plan (render
# settings, bookkeeping) says nothing about which frames were asked for.
RENDER_HANDLERS = ("render_sequence", "render")

# Retry reason codes. They ride alongside the readable decision text so a
# runtime observer can tell OUTPUT_MISSING (the product never existed) from
# PRODUCT_UNREADABLE (a file exists but pixels were never analyzed) from
# QUALITY_FAILED (pixels were analyzed and failed).
OUTPUT_MISSING = "OUTPUT_MISSING"
PRODUCT_UNREADABLE = "PRODUCT_UNREADABLE"
QUALITY_FAILED = "QUALITY_FAILED"

_MISSING_OUTPUT_MARKER = "couldn't find rendered output"


def requested_frames(plan: RenderPlan) -> Optional[Tuple[int, ...]]:
    """The exact frames a plan asks for, or None when the plan does not say.

    A plan is unambiguous only when it carries exactly one render-handler
    step. An explicit ``params["frames"]`` list wins over
    ``start_frame``/``end_frame``: a sparse request ("frames 1, 3") carries
    start=1 and end=3, and expanding that range would invent frame 2.

    ``params["step"]`` is honoured, because the render handler and the farm
    both honour it: start=1, end=10, step=2 is five frames (1, 3, 5, 7, 9),
    not ten. A step the farm cannot act on (zero, negative, non-integer)
    makes the product set unknowable, which is None -- never a guessed range.

    Returns a de-duplicated, sorted tuple, or None when the product set is
    absent, ambiguous, or unparseable. None means "no denominator", never
    "guess one".
    """
    renders = [step for step in plan.steps if step.handler in RENDER_HANDLERS]
    if len(renders) != 1:
        return None

    params = renders[0].params or {}

    explicit = params.get("frames")
    if explicit is not None:
        try:
            frames = {int(f) for f in explicit}
        except (TypeError, ValueError):
            return None
        if not frames:
            return None
        return tuple(sorted(frames))

    try:
        if "start_frame" in params and "end_frame" in params:
            start, end = int(params["start_frame"]), int(params["end_frame"])
        elif "frame" in params:
            start = end = int(params["frame"])
        else:
            return None
        step = int(params.get("step", 1))
    except (TypeError, ValueError):
        return None

    if end < start or step < 1:
        return None
    return tuple(range(start, end + 1, step))


def retry_targets(
    plan: RenderPlan,
    evaluation: SequenceEvaluation,
) -> Dict[int, str]:
    """Frames that still need a product, mapped to the reason code.

    The target set is every frame the evaluation failed plus every frame the
    original plan asked for that never produced an accepted product. A frame
    with no ``FrameEvaluation`` row at all is a target: the terminal product
    is missing, and an absent row is exactly what "missing" looks like when
    the farm never reported it.

    Frames the plan never asked for are never targets, whatever the farm
    reported. A stray failure row (a frame outside the requested set) would
    otherwise become the whole retry plan and re-render a product the artist
    never asked for. When the plan has no product set (``requested_frames``
    is None) there is nothing to intersect against, so the evaluation's own
    failures stand.

    A row is accepted only when it passed, was verified, and has an output
    path. Returns an empty dict when the plan and the evaluation agree.
    """
    rows = {fe.frame: fe for fe in evaluation.frame_evaluations}

    accepted = {
        fe.frame
        for fe in evaluation.frame_evaluations
        if fe.passed and fe.verified and fe.output_path
    }
    failed = {
        fe.frame for fe in evaluation.frame_evaluations if not fe.passed
    }

    frames = requested_frames(plan)
    requested = set(frames or ())
    if frames is not None:
        failed &= requested

    targets = failed | (requested - accepted)

    reasons: Dict[int, str] = {}
    for frame in sorted(targets):
        fe = rows.get(frame)
        if fe is None:
            reasons[frame] = OUTPUT_MISSING
        elif any(_MISSING_OUTPUT_MARKER in issue.lower() for issue in fe.issues):
            reasons[frame] = OUTPUT_MISSING
        elif not fe.output_path:
            reasons[frame] = OUTPUT_MISSING
        elif not fe.verified:
            reasons[frame] = PRODUCT_UNREADABLE
        else:
            reasons[frame] = QUALITY_FAILED

    return reasons


# ---------------------------------------------------------------------------
# Standard pre-flight checks (metadata only — validator runs them)
# ---------------------------------------------------------------------------

_STANDARD_CHECKS: List[PreFlightCheck] = [
    PreFlightCheck(
        name="camera",
        description="Verify a render camera exists on the USD stage",
        severity=CheckSeverity.HARD_FAIL,
    ),
    PreFlightCheck(
        name="renderable_prims",
        description="Verify at least one renderable geometry prim exists",
        severity=CheckSeverity.HARD_FAIL,
    ),
    PreFlightCheck(
        name="materials",
        description="Check for geometry prims without assigned materials",
        severity=CheckSeverity.SOFT_WARN,
    ),
    PreFlightCheck(
        name="render_settings",
        description="Warn if render quality settings are unusually low",
        severity=CheckSeverity.SOFT_WARN,
    ),
    PreFlightCheck(
        name="frame_range",
        description="Verify frame range is valid and within scene bounds",
        severity=CheckSeverity.HARD_FAIL,
    ),
    PreFlightCheck(
        name="output_path",
        description="Check that the output directory exists or can be created",
        severity=CheckSeverity.SOFT_WARN,
    ),
    PreFlightCheck(
        name="solaris_ordering",
        description="Check Solaris LOP network ordering (Phase 3 stub)",
        severity=CheckSeverity.SOFT_WARN,
    ),
    PreFlightCheck(
        name="missing_assets",
        description="Check for unresolved USD asset references",
        severity=CheckSeverity.SOFT_WARN,
    ),
]


class RenderPlanner:
    """Builds a RenderPlan from artist intent.

    Uses the routing cascade to resolve complex intents and the recipe
    registry for known patterns. Falls back to a default render handler
    sequence when neither matches.

    Args:
        routing_cascade: Existing tiered routing system.
        recipe_registry: Existing recipe registry for pattern matching.
    """

    def __init__(
        self,
        routing_cascade: Optional[RoutingCascade] = None,
        recipe_registry: Optional[RecipeRegistry] = None,
    ) -> None:
        self._routing = routing_cascade
        self._recipes = recipe_registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(
        self,
        intent: str,
        scene_context: Optional[Dict[str, Any]] = None,
    ) -> RenderPlan:
        """Parse intent into a full RenderPlan.

        Steps:
            1. Parse intent into structured parameters.
            2. Try recipe registry for a known pattern.
            3. Fall back to routing cascade or default sequence.
            4. Attach standard validation checks.
            5. Assign gate level based on intent kind.
        """
        parsed = _parse_intent(intent)
        steps = self._resolve_steps(intent, parsed, scene_context)
        gate = self._assign_gate(parsed)

        return RenderPlan(
            intent=intent,
            steps=steps,
            validation_checks=[
                PreFlightCheck(
                    name=c.name,
                    description=c.description,
                    severity=c.severity,
                )
                for c in _STANDARD_CHECKS
            ],
            estimated_frames=len(parsed["frames"]),
            gate_level=gate,
        )

    def replan(
        self,
        original_plan: RenderPlan,
        evaluation: SequenceEvaluation,
    ) -> RenderPlan:
        """Create a revised plan from what the evaluation proves is missing.

        Targets are the frames the evaluation failed plus every frame the
        original plan asked for that never produced an accepted product. A
        frame with no evaluation row at all is a target, not an absence.

        The revised plan carries the exact frame set. The parameters are
        derived directly rather than formatted into an intent string and
        re-parsed: ``_RERENDER_RE`` reconstructs start=min/end=max, which
        re-expands a sparse set into a contiguous range and re-asks for
        frames that already succeeded.
        """
        targets = retry_targets(original_plan, evaluation)

        if not targets:
            # Everything the plan asked for was accepted — nothing to replan.
            return original_plan

        retry_frames = sorted(targets)
        parsed: Dict[str, Any] = {
            "kind": "rerender",
            "frames": retry_frames,
            "start": retry_frames[0],
            "end": retry_frames[-1],
        }

        # Collect issue-based parameter adjustments
        adjustments = self._adjustments_from_evaluation(evaluation)

        steps = self._build_render_steps(parsed, adjustments)

        # Carry the reason codes alongside the readable description so the
        # retry plan and the decision trail agree about why each frame is
        # being retried.
        reason_codes = ", ".join(sorted({targets[f] for f in retry_frames}))
        for step in steps:
            if step.handler in RENDER_HANDLERS:
                step.description = f"{step.description} [{reason_codes}]"

        frames_str = ", ".join(str(f) for f in retry_frames)

        return RenderPlan(
            intent=f"re-render frames {frames_str}",
            steps=steps,
            validation_checks=[
                PreFlightCheck(
                    name=c.name,
                    description=c.description,
                    severity=c.severity,
                )
                for c in _STANDARD_CHECKS
            ],
            estimated_frames=len(retry_frames),
            gate_level=GateLevel.INFORM,  # Re-renders are lower gate
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_steps(
        self,
        intent: str,
        parsed: Dict[str, Any],
        scene_context: Optional[Dict[str, Any]],
    ) -> List[RenderStep]:
        """Try recipe -> routing -> default fallback."""
        # 1. Try recipe registry
        if self._recipes is not None:
            recipe = self._recipes.match(intent)
            if recipe is not None:
                return self._steps_from_recipe(recipe, parsed)

        # 2. Try routing cascade
        if self._routing is not None:
            try:
                result = self._routing.route(intent, scene_context)
                if result and hasattr(result, "steps"):
                    return self._steps_from_routing(result, parsed)
            except Exception:
                pass  # Fall through to default

        # 3. Default render sequence
        return self._build_render_steps(parsed)

    def _steps_from_recipe(
        self,
        recipe: Any,
        parsed: Dict[str, Any],
    ) -> List[RenderStep]:
        """Convert a matched recipe into RenderSteps."""
        steps: List[RenderStep] = []
        if hasattr(recipe, "steps"):
            for rs in recipe.steps:
                action = rs.action if hasattr(rs, "action") else str(rs)
                payload = rs.payload_template if hasattr(rs, "payload_template") else {}
                gate = GateLevel.INFORM
                if hasattr(rs, "gate_level"):
                    gate = GateLevel(rs.gate_level.value)
                steps.append(RenderStep(
                    handler=action,
                    params={**payload, "start": parsed["start"], "end": parsed["end"]},
                    description=f"Recipe step: {action}",
                    gate=gate,
                ))
        return steps or self._build_render_steps(parsed)

    def _steps_from_routing(
        self,
        result: Any,
        parsed: Dict[str, Any],
    ) -> List[RenderStep]:
        """Convert routing cascade result into RenderSteps."""
        steps: List[RenderStep] = []
        if hasattr(result, "steps"):
            for step in result.steps:
                handler = step.action if hasattr(step, "action") else str(step)
                params = step.payload if hasattr(step, "payload") else {}
                steps.append(RenderStep(
                    handler=handler,
                    params={**params, "start": parsed["start"], "end": parsed["end"]},
                    description=f"Routed step: {handler}",
                    gate=GateLevel.INFORM,
                ))
        return steps or self._build_render_steps(parsed)

    def _build_render_steps(
        self,
        parsed: Dict[str, Any],
        adjustments: Optional[Dict[str, Any]] = None,
    ) -> List[RenderStep]:
        """Build the default render handler sequence.

        Default pipeline:
            1. render_settings (apply quality, only when adjustments exist)
            2. render_sequence (actual render)

        Pre-render validation is PreFlightValidator.validate(plan);
        post-render per-frame validation happens inside render_sequence
        (validate_frame needs an image_path, which only exists post-render).
        """
        adj = adjustments or {}
        steps: List[RenderStep] = []

        # Step 1: Apply render settings if adjustments needed
        if adj:
            steps.append(RenderStep(
                handler="render_settings",
                params={"node": "", "settings": adj},
                description="Apply adjusted render settings",
                gate=GateLevel.INFORM,
            ))

        # Step 2: Render
        render_params: Dict[str, Any] = {
            "start_frame": parsed["start"],
            "end_frame": parsed["end"],
        }
        if parsed["kind"] == "rerender":
            render_params["frames"] = parsed["frames"]
        if parsed["kind"] == "turntable":
            render_params["turntable"] = True

        steps.append(RenderStep(
            handler="render_sequence",
            params=render_params,
            description=f"Render frames {parsed['start']}-{parsed['end']}",
            gate=GateLevel.REVIEW,
        ))

        return steps

    def _assign_gate(self, parsed: Dict[str, Any]) -> GateLevel:
        """Assign overall gate level based on intent kind."""
        if parsed["kind"] == "rerender":
            return GateLevel.INFORM
        if parsed["kind"] == "turntable":
            return GateLevel.REVIEW
        if len(parsed["frames"]) > 100:
            return GateLevel.CONFIRM
        return GateLevel.REVIEW

    def _adjustments_from_evaluation(
        self,
        evaluation: SequenceEvaluation,
    ) -> Dict[str, Any]:
        """Derive render setting adjustments from evaluation issues."""
        adjustments: Dict[str, Any] = {}

        all_issues: List[str] = []
        for fe in evaluation.frame_evaluations:
            all_issues.extend(fe.issues)
        all_issues.extend(evaluation.temporal_issues)
        all_issues.extend(evaluation.hard_failures)

        if any("firefly" in i.lower() or "fireflies" in i.lower() for i in all_issues):
            adjustments["pixel_samples"] = 128
            adjustments["clamp_indirect"] = 10.0

        if any("clipping" in i.lower() for i in all_issues):
            adjustments["exposure_compensation"] = -0.5

        if any("flicker" in i.lower() for i in all_issues):
            adjustments["pixel_samples"] = max(
                adjustments.get("pixel_samples", 64), 96
            )

        return adjustments
