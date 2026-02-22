"""
Agent capabilities -- scene validation wrappers.

Wraps PreFlightValidator and quick readiness checks as async functions
the agent can call before launching a render.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

# Add the python/ directory to sys.path so we can import synapse.autonomy
_PYTHON_DIR = str(Path(__file__).resolve().parents[2] / "python")
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

from synapse.autonomy.models import PreFlightCheck, RenderPlan
from synapse.autonomy.validator import PreFlightValidator


async def validate_scene(
    plan: RenderPlan,
    handler_interface: Any,
) -> List[PreFlightCheck]:
    """Run all pre-flight validation checks against a render plan.

    Executes 8 concurrent checks (camera, renderable prims, materials,
    render settings, frame range, output path, Solaris ordering, missing
    assets) and returns all results -- no short-circuiting.

    Args:
        plan: The render plan to validate against.
        handler_interface: Async handler with a
            ``call(tool_name, params) -> dict`` method.

    Returns:
        List of PreFlightCheck results. Check ``severity`` and ``passed``
        to determine if the scene is ready to render.
    """
    validator = PreFlightValidator(handler_interface)
    return await validator.validate(plan)


async def check_render_readiness(
    handler_interface: Any,
) -> Dict[str, Any]:
    """Quick readiness check -- is the scene render-ready?

    Queries scene info and render settings to verify the basics:
    camera exists, geometry exists, and an output path is configured.
    Lighter than a full validate_scene call.

    Args:
        handler_interface: Async handler with a
            ``call(tool_name, params) -> dict`` method.

    Returns:
        Dict with ``ready`` (bool) and ``issues`` (list of strings).
        If ready is True, the scene passes basic render requirements.
    """
    issues: List[str] = []

    # Check scene info for camera and geometry
    try:
        scene_info = await handler_interface.call("get_scene_info", {})
    except Exception as exc:
        return {
            "ready": False,
            "issues": [f"Couldn't query scene info: {exc}"],
        }

    # Camera check
    cameras = scene_info.get("cameras", [])
    if not cameras:
        camera = scene_info.get("camera", "")
        if not camera:
            issues.append(
                "Couldn't find a render camera. Add a Camera LOP before rendering."
            )

    # Geometry check
    prim_count = scene_info.get("prim_count", 0)
    renderable = scene_info.get("renderable_prims", prim_count)
    if renderable == 0 and prim_count == 0:
        issues.append(
            "Couldn't find any geometry on the stage. We need something to render."
        )

    # Render settings / output path check
    try:
        render_info = await handler_interface.call("render_settings", {"action": "get"})
        output_path = (
            render_info.get("output_path", "")
            or render_info.get("picture", "")
        )
        if not output_path:
            issues.append(
                "No output path configured. Set the 'picture' parameter on the Karma LOP."
            )
    except Exception:
        # render_settings not available -- not a hard blocker
        pass

    return {
        "ready": len(issues) == 0,
        "issues": issues,
    }
