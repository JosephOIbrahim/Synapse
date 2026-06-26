"""
Synapse Solaris Compose Handler Mixin.

Exposes the compose tier (PRD 7.1 / 7.2 / 7.3) as commands:
  solaris_shotsetup_karma_xpu, matlib_bind, assess_render_ready.

Thin wrappers -- the logic lives in solaris_compose_tools, built on the
solaris_compose primitive. Live truth: each handler marshals its hou work to
Houdini's main thread itself (run_on_main) and each MUTATING handler owns its
undo group (hou.undos.group + performUndo rollback -- the build_graph idiom).
The panel bridge adds audit (integrity) on top; it is not the safety mechanism.
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
from ..core.show_config import get_show_config
from . import solaris_compose as _sc
from . import solaris_compose_tools as _tools

_log = logging.getLogger(__name__)


class SolarisComposeMixin:
    """Compose-tier handlers: shotsetup_karma_xpu, matlib_bind, assess_render_ready."""

    def _handle_solaris_shotsetup_karma_xpu(self, payload: Dict) -> Dict:
        """Scaffold a render-ready Karma XPU shot (PRD 7.1 / GAP-1)."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        # Parse the payload HERE, on the handler thread, BEFORE run_on_main
        # marshals the work away (the batch_commands idiom).
        stage_path = resolve_param_with_default(payload, "stage", "/stage")
        # M2-I: a provided resolution is coerced HERE (handler thread); the
        # show-config default is consulted inside _on_main (the $HIP/$JOB
        # read must happen on the main thread).
        res = payload.get("resolution")
        resolution = (int(res[0]), int(res[1])) if res is not None else None
        shot = resolve_param_with_default(payload, "shot", "shot")
        engine = resolve_param_with_default(payload, "engine", "xpu")
        layer_dir = payload.get("layer_dir")
        reason = payload.get("reason")
        # verify=False skips the cold-cook stage readback (L8 §4) — used by the
        # shot_render_ready scaffold build so it can't freeze the GUI.
        verify = payload.get("verify", True)

        from .main_thread import run_on_main, _SLOW_TIMEOUT

        def _on_main():
            res_used = resolution
            advisory = None
            if res_used is None:
                cfg = get_show_config()
                _r, _src = cfg.lookup("resolution.render")
                res_used = (int(_r[0]), int(_r[1]))
                advisory = {
                    "default_used": (
                        ["resolution.render"] if _src == "default" else []
                    ),
                }
            stage = _sc.resolve_stage(stage_path)
            try:
                with hou.undos.group("SYNAPSE: solaris_shotsetup_karma_xpu"):
                    result = _tools.build_karma_xpu_shot(
                        stage,
                        shot=shot,
                        resolution=res_used,
                        engine=engine,
                        layer_dir=layer_dir,
                        reason=reason,
                        verify=verify,
                    )
                    if advisory is not None:
                        result.setdefault("show_config", advisory)
                    return result
            except Exception:
                # Safe undo fallback -- the C++ undo layer for LOP nodes can
                # throw during __exit__; explicitly undo to prevent undo
                # stack corruption (build_graph idiom).
                try:
                    hou.undos.performUndo()
                except Exception as undo_exc:
                    _log.warning(
                        "solaris_shotsetup_karma_xpu: undo rollback also failed: %s",
                        undo_exc,
                    )
                raise

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT)

    def _handle_matlib_bind(self, payload: Dict) -> Dict:
        """Bind a material to a prim set (PRD 7.2 / GAP-2 / BL-008)."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        material = payload.get("material")
        targets = payload.get("targets", payload.get("pattern"))
        if not material or not targets:
            raise SynapseUserError(
                "matlib_bind needs 'material' (prim path) and 'targets' (pattern or list)",
                suggestion="e.g. material='/materials/red', targets='//Mesh'",
            )
        stage_path = resolve_param_with_default(payload, "stage", "/stage")
        input_path = payload.get("input_node")
        strength = payload.get("strength")

        from .main_thread import run_on_main, _SLOW_TIMEOUT

        def _on_main():
            stage = _sc.resolve_stage(stage_path)
            input_node = hou.node(input_path) if input_path else None
            try:
                with hou.undos.group("SYNAPSE: matlib_bind"):
                    return _tools.bind_material(
                        stage, material, targets,
                        input_node=input_node, strength=strength,
                    )
            except Exception:
                try:
                    hou.undos.performUndo()
                except Exception as undo_exc:
                    _log.warning(
                        "matlib_bind: undo rollback also failed: %s", undo_exc,
                    )
                raise

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT)

    def _handle_assess_render_ready(self, payload: Dict) -> Dict:
        """Render-readiness report over E3 (PRD 7.3 / GAP-3). Read-only.

        Named 'assess_render_ready' (NOT 'shot_render_ready') to avoid colliding
        with the existing UsdHandlerMixin orchestrator of that name (which builds
        + renders); this is the read-only assessment counterpart.
        """
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        stage_path = resolve_param_with_default(payload, "stage", "/stage")
        engine = payload.get("engine")

        from .main_thread import run_on_main

        # Read-only -- no undo group, but resolve_stage/read_stage cook LOPs,
        # which must happen on the main thread. Default timeout.
        return run_on_main(
            lambda: _tools.assess_render_ready(
                _sc.resolve_stage(stage_path), engine_hint=engine,
            )
        )
