"""
Synapse Solaris Compose Handler Mixin.

Exposes the compose tier (PRD 7.1 / 7.2 / 7.3) as commands:
  solaris_shotsetup_karma_xpu, matlib_bind, assess_render_ready.

Thin wrappers -- the logic lives in solaris_compose_tools, built on the
solaris_compose primitive. Dispatched through the bridge (undo / integrity /
consent / blast-radius) via panel.bridge_adapter.execute_through_bridge.
"""

from typing import Dict
import logging

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param_with_default
from ..core.errors import HoudiniUnavailableError, SynapseUserError
from . import solaris_compose as _sc
from . import solaris_compose_tools as _tools

_log = logging.getLogger(__name__)


class SolarisComposeMixin:
    """Compose-tier handlers: shotsetup_karma_xpu, matlib_bind, assess_render_ready."""

    def _handle_solaris_shotsetup_karma_xpu(self, payload: Dict) -> Dict:
        """Scaffold a render-ready Karma XPU shot (PRD 7.1 / GAP-1)."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        stage = _sc.resolve_stage(resolve_param_with_default(payload, "stage", "/stage"))
        res = payload.get("resolution", [1920, 1080])
        return _tools.build_karma_xpu_shot(
            stage,
            shot=resolve_param_with_default(payload, "shot", "shot"),
            resolution=(int(res[0]), int(res[1])),
            engine=resolve_param_with_default(payload, "engine", "xpu"),
            layer_dir=payload.get("layer_dir"),
            reason=payload.get("reason"),
        )

    def _handle_matlib_bind(self, payload: Dict) -> Dict:
        """Bind a material to a prim set (PRD 7.2 / GAP-2 / BL-008)."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        stage = _sc.resolve_stage(resolve_param_with_default(payload, "stage", "/stage"))
        material = payload.get("material")
        targets = payload.get("targets", payload.get("pattern"))
        if not material or not targets:
            raise SynapseUserError(
                "matlib_bind needs 'material' (prim path) and 'targets' (pattern or list)",
                suggestion="e.g. material='/materials/red', targets='//Mesh'",
            )
        input_node = hou.node(payload["input_node"]) if payload.get("input_node") else None
        return _tools.bind_material(
            stage, material, targets,
            input_node=input_node, strength=payload.get("strength"),
        )

    def _handle_assess_render_ready(self, payload: Dict) -> Dict:
        """Render-readiness report over E3 (PRD 7.3 / GAP-3). Read-only.

        Named 'assess_render_ready' (NOT 'shot_render_ready') to avoid colliding
        with the existing UsdHandlerMixin orchestrator of that name (which builds
        + renders); this is the read-only assessment counterpart.
        """
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        stage = _sc.resolve_stage(resolve_param_with_default(payload, "stage", "/stage"))
        return _tools.assess_render_ready(stage, engine_hint=payload.get("engine"))
