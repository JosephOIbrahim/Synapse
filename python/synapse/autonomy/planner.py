"""
Synapse Autonomy Pipeline — Render Planner

Parses artist intent into a structured RenderPlan with handler steps,
validation checks, frame estimates, and gate levels.

Uses the existing routing cascade and recipe registry to resolve intent
into concrete handler sequences. stdlib-only.
"""

import re
from typing import Any, Dict, List, Optional, Protocol

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
        """Create a revised plan based on evaluation results.

        Only re-renders failed frames and adjusts quality settings if
        the evaluation flagged specific issues (fireflies, clipping, etc.).
        """
        failed_frames = [
            fe.frame
            for fe in evaluation.frame_evaluations
            if not fe.passed
        ]

        if not failed_frames:
            # Everything passed — nothing to replan
            return original_plan

        # Build re-render intent
        frames_str = ", ".join(str(f) for f in sorted(failed_frames))
        replan_intent = f"re-render frames {frames_str}"
        parsed = _parse_intent(replan_intent)

        # Collect issue-based parameter adjustments
        adjustments = self._adjustments_from_evaluation(evaluation)

        steps = self._build_render_steps(parsed, adjustments)

        return RenderPlan(
            intent=replan_intent,
            steps=steps,
            validation_checks=[
                PreFlightCheck(
                    name=c.name,
                    description=c.description,
                    severity=c.severity,
                )
                for c in _STANDARD_CHECKS
            ],
            estimated_frames=len(failed_frames),
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
            1. validate_frame (pre-check)
            2. render_settings (apply quality)
            3. render_sequence (actual render)
        """
        adj = adjustments or {}
        steps: List[RenderStep] = []

        # Step 1: Validate the stage before rendering
        steps.append(RenderStep(
            handler="validate_frame",
            params={"frame": parsed["start"]},
            description="Pre-render frame validation",
            gate=GateLevel.INFORM,
        ))

        # Step 2: Apply render settings if adjustments needed
        if adj:
            steps.append(RenderStep(
                handler="render_settings",
                params=adj,
                description="Apply adjusted render settings",
                gate=GateLevel.INFORM,
            ))

        # Step 3: Render
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
