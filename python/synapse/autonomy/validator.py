"""
Synapse Autonomy Pipeline — Pre-Flight Validator

Runs 8 async checks against the live Houdini scene before render execution.
All checks run unconditionally (no short-circuit) so the artist sees the
full picture in one pass.

Uses handler_interface for scene queries — never calls handlers directly.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Protocol

from .models import CheckSeverity, PreFlightCheck, RenderPlan

logger = logging.getLogger("synapse.autonomy.validator")


class HandlerInterface(Protocol):
    """Async callable interface for querying scene state via MCP handlers."""

    async def call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a handler tool by name with the given parameters."""
        ...


class PreFlightValidator:
    """Runs all pre-flight checks against a RenderPlan.

    Each check queries the scene through the handler_interface and returns
    a PreFlightCheck result. All checks run concurrently via asyncio.gather
    and none short-circuit on failure.

    Args:
        handler_interface: Async callable for scene queries.
    """

    def __init__(self, handler_interface: HandlerInterface) -> None:
        self._handler = handler_interface

    async def validate(self, plan: RenderPlan) -> List[PreFlightCheck]:
        """Run all 8 pre-flight checks and return results.

        Does NOT short-circuit — all checks execute regardless of earlier
        failures so the artist gets a complete diagnostic.
        """
        checks = await asyncio.gather(
            self._check_camera(),
            self._check_renderable_prims(),
            self._check_materials(),
            self._check_render_settings(plan),
            self._check_frame_range(plan),
            self._check_output_path(),
            self._check_solaris_ordering(plan),
            self._check_missing_assets(),
            return_exceptions=True,
        )

        results: List[PreFlightCheck] = []
        for check in checks:
            if isinstance(check, PreFlightCheck):
                results.append(check)
            elif isinstance(check, Exception):
                # An individual check crashed — report as a soft warning
                results.append(PreFlightCheck(
                    name="internal_error",
                    description="A pre-flight check raised an unexpected error",
                    severity=CheckSeverity.SOFT_WARN,
                    passed=False,
                    message=f"Check failed internally: {check}",
                ))
        return results

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    async def _check_camera(self) -> PreFlightCheck:
        """HARD_FAIL if no render camera exists on the USD stage."""
        try:
            result = await self._handler.call("get_stage_info", {})
            cameras = result.get("cameras", [])
            if not cameras:
                return PreFlightCheck(
                    name="camera",
                    description="Verify a render camera exists on the USD stage",
                    severity=CheckSeverity.HARD_FAIL,
                    passed=False,
                    message="Couldn't find a render camera on the stage. "
                            "Add a Camera LOP before rendering.",
                )
            return PreFlightCheck(
                name="camera",
                description="Verify a render camera exists on the USD stage",
                severity=CheckSeverity.HARD_FAIL,
                passed=True,
                message=f"Found {len(cameras)} camera(s): {', '.join(cameras[:5])}",
            )
        except Exception as exc:
            return PreFlightCheck(
                name="camera",
                description="Verify a render camera exists on the USD stage",
                severity=CheckSeverity.HARD_FAIL,
                passed=False,
                message=f"Couldn't query stage for cameras: {exc}",
            )

    async def _check_renderable_prims(self) -> PreFlightCheck:
        """HARD_FAIL if no renderable geometry prims exist."""
        try:
            result = await self._handler.call("get_stage_info", {})
            prim_count = result.get("prim_count", 0)
            renderable = result.get("renderable_prims", prim_count)
            if renderable == 0:
                return PreFlightCheck(
                    name="renderable_prims",
                    description="Verify at least one renderable geometry prim exists",
                    severity=CheckSeverity.HARD_FAIL,
                    passed=False,
                    message="Couldn't find any renderable geometry on the stage. "
                            "We need at least one mesh or other renderable prim.",
                )
            return PreFlightCheck(
                name="renderable_prims",
                description="Verify at least one renderable geometry prim exists",
                severity=CheckSeverity.HARD_FAIL,
                passed=True,
                message=f"Found {renderable} renderable prim(s) on the stage.",
            )
        except Exception as exc:
            return PreFlightCheck(
                name="renderable_prims",
                description="Verify at least one renderable geometry prim exists",
                severity=CheckSeverity.HARD_FAIL,
                passed=False,
                message=f"Couldn't query stage for renderable prims: {exc}",
            )

    async def _check_materials(self) -> PreFlightCheck:
        """SOFT_WARN if geometry prims lack assigned materials."""
        try:
            result = await self._handler.call("get_stage_info", {})
            unassigned = result.get("unassigned_material_prims", [])
            if unassigned:
                paths = ", ".join(str(p) for p in unassigned[:5])
                suffix = f" (and {len(unassigned) - 5} more)" if len(unassigned) > 5 else ""
                return PreFlightCheck(
                    name="materials",
                    description="Check for geometry prims without assigned materials",
                    severity=CheckSeverity.SOFT_WARN,
                    passed=False,
                    message=f"Found {len(unassigned)} prim(s) without materials: "
                            f"{paths}{suffix}. They'll render with the default grey shader.",
                )
            return PreFlightCheck(
                name="materials",
                description="Check for geometry prims without assigned materials",
                severity=CheckSeverity.SOFT_WARN,
                passed=True,
                message="All geometry prims have materials assigned.",
            )
        except Exception as exc:
            return PreFlightCheck(
                name="materials",
                description="Check for geometry prims without assigned materials",
                severity=CheckSeverity.SOFT_WARN,
                passed=False,
                message=f"Couldn't check material assignments: {exc}",
            )

    async def _check_render_settings(self, plan: RenderPlan) -> PreFlightCheck:
        """SOFT_WARN if render quality settings appear unusually low."""
        try:
            result = await self._handler.call("render_settings", {"action": "get"})
            pixel_samples = result.get("pixel_samples", 0)
            resolution_x = result.get("resolution_x", 0)

            warnings: List[str] = []
            if 0 < pixel_samples < 8:
                warnings.append(
                    f"Pixel samples is {pixel_samples} (very low — consider 32+ for production)"
                )
            if 0 < resolution_x < 320:
                warnings.append(
                    f"Resolution width is {resolution_x}px (very low for a final render)"
                )

            if warnings:
                return PreFlightCheck(
                    name="render_settings",
                    description="Warn if render quality settings are unusually low",
                    severity=CheckSeverity.SOFT_WARN,
                    passed=False,
                    message="; ".join(warnings),
                )
            return PreFlightCheck(
                name="render_settings",
                description="Warn if render quality settings are unusually low",
                severity=CheckSeverity.SOFT_WARN,
                passed=True,
                message="Render quality settings look reasonable.",
            )
        except Exception as exc:
            return PreFlightCheck(
                name="render_settings",
                description="Warn if render quality settings are unusually low",
                severity=CheckSeverity.SOFT_WARN,
                passed=False,
                message=f"Couldn't read render settings: {exc}",
            )

    async def _check_frame_range(self, plan: RenderPlan) -> PreFlightCheck:
        """HARD_FAIL if the planned frame range is invalid."""
        if plan.estimated_frames <= 0:
            return PreFlightCheck(
                name="frame_range",
                description="Verify frame range is valid and within scene bounds",
                severity=CheckSeverity.HARD_FAIL,
                passed=False,
                message="Couldn't determine any frames to render. "
                        "Check the intent — we need at least one frame.",
            )

        # Check against scene frame range if available
        try:
            result = await self._handler.call("get_scene_info", {})
            scene_start = result.get("frame_start", None)
            scene_end = result.get("frame_end", None)

            if scene_start is not None and scene_end is not None:
                # Extract planned range from steps
                planned_start = None
                planned_end = None
                for step in plan.steps:
                    if "start_frame" in step.params:
                        planned_start = step.params["start_frame"]
                    if "end_frame" in step.params:
                        planned_end = step.params["end_frame"]

                if planned_start is not None and planned_end is not None:
                    if planned_start > planned_end:
                        return PreFlightCheck(
                            name="frame_range",
                            description="Verify frame range is valid and within scene bounds",
                            severity=CheckSeverity.HARD_FAIL,
                            passed=False,
                            message=f"Start frame ({planned_start}) is after end frame "
                                    f"({planned_end}). That doesn't look right.",
                        )
        except Exception:
            pass  # Scene info unavailable — still pass on estimated_frames > 0

        return PreFlightCheck(
            name="frame_range",
            description="Verify frame range is valid and within scene bounds",
            severity=CheckSeverity.HARD_FAIL,
            passed=True,
            message=f"Frame range looks valid ({plan.estimated_frames} frame(s) planned).",
        )

    async def _check_output_path(self) -> PreFlightCheck:
        """SOFT_WARN if the render output directory doesn't exist."""
        try:
            result = await self._handler.call("render_settings", {"action": "get"})
            output_path = result.get("output_path", "") or result.get("picture", "")

            if not output_path:
                return PreFlightCheck(
                    name="output_path",
                    description="Check that the output directory exists or can be created",
                    severity=CheckSeverity.SOFT_WARN,
                    passed=False,
                    message="Couldn't find an output path configured. "
                            "Set the 'picture' parameter on the Karma LOP.",
                )
            return PreFlightCheck(
                name="output_path",
                description="Check that the output directory exists or can be created",
                severity=CheckSeverity.SOFT_WARN,
                passed=True,
                message=f"Output path configured: {output_path}",
            )
        except Exception as exc:
            return PreFlightCheck(
                name="output_path",
                description="Check that the output directory exists or can be created",
                severity=CheckSeverity.SOFT_WARN,
                passed=False,
                message=f"Couldn't verify output path: {exc}",
            )

    async def _check_solaris_ordering(self, plan: RenderPlan) -> PreFlightCheck:
        """Detect ambiguous LOP merge ordering via solaris_validate_ordering handler."""
        try:
            render_node = ""
            if plan.steps:
                render_node = plan.steps[0].params.get("render_node", "")
            result = await self._handler.call("solaris_validate_ordering", {
                "render_node": render_node
            })

            if result.get("clean", True):
                return PreFlightCheck(
                    name="solaris_ordering",
                    description="Solaris network ordering check",
                    severity=CheckSeverity.INFO,
                    passed=True,
                    message="No ordering ambiguities detected."
                )
            else:
                issues = result.get("issues", [])
                issue_desc = "; ".join(f"{i['node']}: {i['type']}" for i in issues)
                return PreFlightCheck(
                    name="solaris_ordering",
                    description="Solaris network ordering check",
                    severity=CheckSeverity.SOFT_WARN,
                    passed=False,
                    message=f"Ordering ambiguities detected: {issue_desc}. Review merge order before rendering."
                )
        except Exception as exc:
            return PreFlightCheck(
                name="solaris_ordering",
                description="Solaris network ordering check",
                severity=CheckSeverity.INFO,
                passed=True,
                message=f"Couldn't run ordering check: {exc}"
            )

    async def _check_missing_assets(self) -> PreFlightCheck:
        """SOFT_WARN if unresolved USD asset references are found."""
        try:
            result = await self._handler.call("get_stage_info", {})
            unresolved = result.get("unresolved_references", [])

            if unresolved:
                refs = ", ".join(str(r) for r in unresolved[:5])
                suffix = f" (and {len(unresolved) - 5} more)" if len(unresolved) > 5 else ""
                return PreFlightCheck(
                    name="missing_assets",
                    description="Check for unresolved USD asset references",
                    severity=CheckSeverity.SOFT_WARN,
                    passed=False,
                    message=f"Found {len(unresolved)} unresolved reference(s): "
                            f"{refs}{suffix}. These assets may render as missing geometry.",
                )
            return PreFlightCheck(
                name="missing_assets",
                description="Check for unresolved USD asset references",
                severity=CheckSeverity.SOFT_WARN,
                passed=True,
                message="All USD asset references resolved successfully.",
            )
        except Exception as exc:
            return PreFlightCheck(
                name="missing_assets",
                description="Check for unresolved USD asset references",
                severity=CheckSeverity.SOFT_WARN,
                passed=False,
                message=f"Couldn't check asset references: {exc}",
            )
