"""
Synapse Render Handler Mixin

Extracted from handlers.py -- contains viewport capture, render, keyframe,
render settings, wedge, and material handlers for the SynapseHandler class.
"""

import os
import time
from typing import Dict

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default, USD_PARM_ALIASES
from .handlers_usd import _usd_to_json


_HOUDINI_UNAVAILABLE = (
    "Houdini isn't reachable right now -- make sure it's running "
    "and Synapse is started from the Python Panel"
)


def _suggest_parms(node, invalid_name: str, limit: int = 8) -> str:
    """Find similar parameter names on a node for error enrichment."""
    try:
        all_names = [p.name() for p in node.parms()]
    except Exception:
        return ""
    needle = invalid_name.lower()
    matches = [n for n in all_names if needle in n.lower() or n.lower() in needle]
    if not matches:
        # Fallback: common prefix match
        matches = [n for n in all_names if n.lower().startswith(needle[:3])]
    # Check USD alias -- if the invalid name maps to an encoded USD parm, include hint
    usd_hint = ""
    usd_encoded = USD_PARM_ALIASES.get(invalid_name.lower())
    if usd_encoded and usd_encoded in all_names:
        usd_hint = f" Try '{usd_encoded}' (the encoded USD name for '{invalid_name}')."
    if not matches and not usd_hint:
        return ""
    parts = []
    if usd_hint:
        parts.append(usd_hint)
    if matches:
        parts.append(" Similar parameters: " + ", ".join(matches[:limit]))
    return "".join(parts)


def _find_render_rop():
    """Auto-discover a render ROP node. Searches /stage then /out."""
    _RENDER_TYPES = {
        "karma", "karmarendersettings",
        "usdrender", "usdrender_rop",
        "ifd",
        "opengl",
    }
    for parent_path in ["/stage", "/out"]:
        parent = hou.node(parent_path)
        if parent is None:
            continue
        for child in parent.children():
            if child.type().name() in _RENDER_TYPES:
                return child
    raise ValueError(
        "Couldn't auto-find a render ROP -- specify the 'node' parameter "
        "with the path to your ROP (e.g. '/stage/karma1' or '/out/mantra1')"
    )


def _detect_karma_engine(node, node_type: str) -> str:
    """Detect Karma XPU vs CPU vs Mantra vs other renderer.

    Karma XPU is the GPU+CPU hybrid renderer; Karma CPU is pure CPU.
    The engine is selected by a parm on the ROP or Karma Render Settings LOP.
    """
    if node_type == "ifd":
        return "mantra"
    if node_type == "opengl":
        return "opengl"
    if node_type not in ("karma", "karmarendersettings", "usdrender", "usdrender_rop"):
        return node_type

    # Check common parm names for Karma engine variant
    for parm_name in ("renderer", "karmarenderertype", "renderengine"):
        parm = node.parm(parm_name)
        if parm is not None:
            # hou.Parm.eval() reads the parameter value -- not Python eval()
            val = str(parm.eval()).lower()  # noqa: S307
            if "xpu" in val:
                return "karma_xpu"
            if "cpu" in val:
                return "karma_cpu"
            return f"karma_{val}" if val else "karma"

    return "karma"


class RenderHandlerMixin:
    """Mixin providing viewport capture, render, keyframe, render settings,
    wedge, and material handlers."""

    def _handle_capture_viewport(self, payload: Dict) -> Dict:
        """Capture the Houdini viewport as an image file.

        Uses Houdini's flipbook API for a single-frame capture. This correctly
        reads the OpenGL framebuffer (QWidget.grab() returns black for GL surfaces).
        Must run on the main thread via hdefereval.executeInMainThreadWithResult().
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        from pathlib import Path

        fmt = resolve_param_with_default(payload, "format", "jpeg")
        width = resolve_param_with_default(payload, "width", 800)
        height = resolve_param_with_default(payload, "height", 600)

        temp_dir = Path(hou.text.expandString("$HOUDINI_TEMP_DIR"))
        ext = "jpg" if fmt == "jpeg" else "png"
        timestamp = int(time.time() * 1000)
        # Flipbook requires $F4 frame pattern in output path
        out_pattern = str(temp_dir / f"synapse_cap_{timestamp}.$F4.{ext}")

        def _flipbook_on_main_thread():
            """Runs on Houdini's main thread."""
            desktop = hou.ui.curDesktop()
            sv = desktop.paneTabOfType(hou.paneTabType.SceneViewer)
            if sv is None:
                raise ValueError(
                    "Couldn't find a viewport -- make sure a Scene Viewer pane "
                    "is open in your current desktop layout"
                )

            vp = sv.curViewport()
            settings = sv.flipbookSettings()
            cur = int(hou.frame())
            settings.frameRange((cur, cur))
            settings.output(out_pattern)
            settings.useResolution(True)
            settings.resolution((int(width), int(height)))
            sv.flipbook(viewport=vp, settings=settings, open_dialog=False)

            # Resolve the actual output filename (replaces $F4 with frame number)
            actual = out_pattern.replace("$F4", f"{cur:04d}")
            return actual

        import hdefereval
        actual_path = hdefereval.executeInMainThreadWithResult(
            _flipbook_on_main_thread
        )

        if not Path(actual_path).exists():
            raise RuntimeError(
                f"The viewport capture ran but the image wasn't created at {actual_path} -- "
                "this can happen if the viewport is minimized or occluded"
            )

        return {
            "image_path": actual_path,
            "width": int(width),
            "height": int(height),
            "format": fmt,
        }

    def _handle_render(self, payload: Dict) -> Dict:
        """Render a frame via Karma, Mantra, or any ROP node.

        Uses hdefereval.executeInMainThreadWithResult() since hou.RopNode.render()
        must run on Houdini's main thread. Outputs to a temp JPEG for AI preview.

        Supports Karma XPU (GPU+CPU hybrid), Karma CPU, and Mantra ROPs.
        For Karma nodes, detects and reports the rendering engine variant.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from pathlib import Path

        rop_path = resolve_param(payload, "node", required=False)
        frame = resolve_param_with_default(payload, "frame", None)
        width = resolve_param_with_default(payload, "width", None)
        height = resolve_param_with_default(payload, "height", None)

        def _render_on_main():
            if rop_path:
                node = hou.node(rop_path)
                if node is None:
                    raise ValueError(
                        f"Couldn't find a render ROP at {rop_path} -- "
                        "double-check the path to your ROP node"
                    )
            else:
                node = _find_render_rop()

            # Detect Karma engine variant for metadata
            node_type = node.type().name()
            engine = _detect_karma_engine(node, node_type)

            # For usdrender ROPs in /out, ensure loppath is set
            lp = node.parm("loppath")
            # hou.Parm.eval() reads parameter value -- not Python eval()
            if lp and not lp.eval():  # noqa: S307
                # Auto-find a LOP node with a stage
                for lop_path in ["/stage"]:
                    lop = hou.node(lop_path)
                    if lop and lop.children():
                        # Find last display node or last child
                        display = [c for c in lop.children() if hasattr(c, 'isDisplayFlagSet') and c.isDisplayFlagSet()]
                        target = display[0] if display else lop.children()[-1]
                        lp.set(target.path())
                        break

            # Output to temp JPEG (AI preview, not final EXR)
            temp_dir = Path(hou.text.expandString("$HOUDINI_TEMP_DIR"))
            timestamp = int(time.time() * 1000)
            out_path = str(temp_dir / f"synapse_render_{timestamp}.jpg")

            cur = int(hou.frame()) if frame is None else int(frame)

            # Resolution override -- res= is a scale factor, so set parms directly
            if width and height:
                w, h = int(width), int(height)
                for rx, ry in [("resolutionx", "resolutiony"), ("res_user1", "res_user2")]:
                    if node.parm(rx):
                        node.parm(rx).set(w)
                        node.parm(ry).set(h)
                        break
                # Enable override if available (usdrender string menu)
                ov = node.parm("override_res")
                # hou.Parm.eval() reads parameter value -- not Python eval()
                if ov and ov.eval() != "specific":  # noqa: S307
                    ov.set("specific")

            # Set output path on the node parm (output_file kwarg doesn't
            # work reliably for usdrender/karma ROPs)
            for parm_name in ("outputimage", "picture"):
                p = node.parm(parm_name)
                if p:
                    p.set(out_path)
                    break

            node.render(
                frame_range=(cur, cur),
                verbose=False,
            )

            # Karma XPU has a delayed file flush -- poll up to ~15s
            for _ in range(60):
                if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(
                    f"The render finished but the output wasn't created at {out_path} -- "
                    "check if the output directory is writable and the renderer didn't error"
                )
            return out_path, node.path(), node_type, engine

        import hdefereval
        result_path, used_rop, used_type, engine = (
            hdefereval.executeInMainThreadWithResult(_render_on_main)
        )
        return {
            "image_path": result_path,
            "rop": used_rop,
            "rop_type": used_type,
            "engine": engine,
            "width": int(width) if width else None,
            "height": int(height) if height else None,
            "format": "jpeg",
        }

    def _handle_set_keyframe(self, payload: Dict) -> Dict:
        """Set a keyframe on a node parameter at a specific frame."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")
        value = resolve_param(payload, "value")
        frame = resolve_param_with_default(payload, "frame", None)

        node = hou.node(node_path)
        if node is None:
            raise ValueError(
                f"Couldn't find a node at {node_path} -- "
                "double-check the path exists"
            )
        parm = node.parm(parm_name)
        if parm is None:
            hint = _suggest_parms(node, parm_name)
            raise ValueError(
                f"Couldn't find parameter '{parm_name}' on {node_path}.{hint}"
            )

        if frame is not None:
            key = hou.Keyframe()
            key.setFrame(float(frame))
            key.setValue(float(value))
            parm.setKeyframe(key)
        else:
            key = hou.Keyframe()
            key.setFrame(float(hou.frame()))
            key.setValue(float(value))
            parm.setKeyframe(key)

        return {
            "node": node_path,
            "parm": parm_name,
            "value": float(value),
            "frame": float(frame) if frame is not None else float(hou.frame()),
        }

    def _handle_render_settings(self, payload: Dict) -> Dict:
        """Read and optionally modify render settings on a ROP or Karma node."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        node_path = resolve_param(payload, "node")

        node = hou.node(node_path)
        if node is None:
            raise ValueError(
                f"Couldn't find a node at {node_path} -- "
                "double-check the path to your render settings node"
            )

        settings = {}
        # Read current render settings
        for parm in node.parms():
            try:
                # hou.Parm.eval() reads parameter value -- not Python eval()
                val = parm.eval()  # noqa: S307
                if isinstance(val, (int, float, str)):
                    settings[parm.name()] = val
            except Exception:
                pass

        # Apply overrides if provided
        overrides = resolve_param_with_default(payload, "settings", {})
        if isinstance(overrides, dict):
            for k, v in sorted(overrides.items()):
                p = node.parm(k)
                if p:
                    p.set(v)
                    settings[k] = v

        return {"node": node_path, "settings": settings}

    def _handle_wedge(self, payload: Dict) -> Dict:
        """Run a TOPs/PDG wedge to explore parameter variations."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        top_path = resolve_param(payload, "node")  # TOP network or wedge node
        wedge_parm = resolve_param(payload, "parm", required=False)
        values = resolve_param(payload, "values", required=False)

        if values is not None and not isinstance(values, list):
            raise ValueError(
                "'values' should be a list (e.g. [0.5, 1.0, 2.0]) -- "
                "wrap your values in square brackets"
            )

        def _run_wedge():
            node = hou.node(top_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {top_path} -- "
                    "double-check the path to your TOP network or wedge node"
                )

            # If it's a TOP network, find or create wedge node
            if node.type().category().name() == "Top":
                # It's already a TOP node -- cook it
                node.cook(block=True)
                return {"node": top_path, "status": "cooked"}
            elif node.type().category().name() == "TopNet":
                # It's a TOP network -- find wedge nodes and cook
                wedge_nodes = [n for n in node.children() if "wedge" in n.type().name().lower()]
                if wedge_nodes:
                    wedge_nodes[0].cook(block=True)
                    return {"node": wedge_nodes[0].path(), "status": "cooked"}
                else:
                    raise ValueError(
                        f"Couldn't find a wedge node inside {top_path} -- "
                        "create a wedge TOP or point to one directly"
                    )
            else:
                raise ValueError(
                    f"The node at {top_path} isn't a TOP network -- "
                    "point to a TOP network or a specific wedge/TOP node"
                )

        result = hdefereval.executeInMainThreadWithResult(_run_wedge)
        return result

    def _handle_create_material(self, payload: Dict) -> Dict:
        """Create a materiallibrary LOP with a MaterialX shader inside it.

        Uses native Houdini nodes (materiallibrary + shader child) so the
        material is visible and editable in the artist's network.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node = self._resolve_lop_node(  # type: ignore[attr-defined]
            resolve_param(payload, "node", required=False)
        )
        name = resolve_param_with_default(payload, "name", "material")
        shader_type = resolve_param_with_default(
            payload, "shader_type", "mtlxstandard_surface"
        )
        base_color = resolve_param(payload, "base_color", required=False)
        metalness = resolve_param(payload, "metalness", required=False)
        roughness = resolve_param(payload, "roughness", required=False)

        parent = node.parent()

        # Create materiallibrary node and wire it after the resolved LOP node
        matlib = parent.createNode("materiallibrary", name)
        matlib.setInput(0, node)
        matlib.moveToGoodPosition()

        # Cook the matlib so its internal network is ready for child creation
        matlib.cook(force=True)

        # Create shader node inside the materiallibrary
        shader = matlib.createNode(shader_type, name + "_shader")
        if shader is None:
            raise RuntimeError(
                f"Couldn't create a '{shader_type}' shader inside the material library "
                "-- check that this shader type is available in your Houdini build"
            )

        # Set optional shader parameters
        if base_color is not None:
            if isinstance(base_color, (list, tuple)) and len(base_color) >= 3:
                for i, ch in enumerate(("r", "g", "b")):
                    p = shader.parm(f"base_color{ch}")
                    if p:
                        p.set(float(base_color[i]))
        if metalness is not None:
            p = shader.parm("metalness")
            if p:
                p.set(float(metalness))
        if roughness is not None:
            p = shader.parm("specular_roughness")
            if p:
                p.set(float(roughness))

        # Read the USD material path that the matlib auto-generates
        material_usd_path = f"/materials/{name}"

        return {
            "matlib_path": matlib.path(),
            "shader_path": shader.path(),
            "material_usd_path": material_usd_path,
            "shader_type": shader_type,
            "name": name,
        }

    def _handle_assign_material(self, payload: Dict) -> Dict:
        """Create an assignmaterial LOP to bind a material to geometry prims."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node = self._resolve_lop_node(  # type: ignore[attr-defined]
            resolve_param(payload, "node", required=False)
        )
        prim_pattern = resolve_param(payload, "prim_pattern")
        material_path = resolve_param(payload, "material_path")

        parent = node.parent()
        # Safe node name from the material path
        safe_name = material_path.rstrip("/").rsplit("/", 1)[-1] or "mat"
        assign_node = parent.createNode("assignmaterial", f"assign_{safe_name}")
        assign_node.setInput(0, node)
        assign_node.moveToGoodPosition()

        # Set the prim pattern and material spec path
        assign_node.parm("primpattern1").set(prim_pattern)
        assign_node.parm("matspecpath1").set(material_path)

        return {
            "node_path": assign_node.path(),
            "prim_pattern": prim_pattern,
            "material_path": material_path,
        }

    def _handle_read_material(self, payload: Dict) -> Dict:
        """Read material binding and shader parameters from a USD prim.

        Pure stage query -- no node creation. Uses UsdShade API to inspect
        material bindings and shader inputs.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node = self._resolve_lop_node(  # type: ignore[attr-defined]
            resolve_param(payload, "node", required=False)
        )
        prim_path = resolve_param(payload, "prim_path")

        stage = node.stage()
        if stage is None:
            raise ValueError(
                "That node doesn't have an active USD stage yet -- "
                "it may need to cook first, or check the LOP network is set up"
            )

        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise ValueError(
                f"Couldn't find a prim at {prim_path} -- "
                "double-check the path on the USD stage"
            )

        from pxr import UsdShade

        binding_api = UsdShade.MaterialBindingAPI(prim)
        bound = binding_api.GetDirectBinding()
        mat_path_str = str(bound.GetMaterialPath()) if bound.GetMaterial() else ""

        if not mat_path_str:
            return {
                "prim_path": prim_path,
                "has_material": False,
                "material_path": "",
                "shader_type": "",
                "shader_params": {},
            }

        material = bound.GetMaterial()
        shader_type = ""
        shader_params = {}

        # Get the surface shader output
        surface_output = material.GetSurfaceOutput()
        if surface_output:
            source = surface_output.GetConnectedSources()
            if source and source[0]:
                shader_prim = UsdShade.Shader(source[0][0].source.GetPrim())
                shader_type = str(shader_prim.GetIdAttr().Get() or "")

                for shader_input in shader_prim.GetInputs():
                    input_name = shader_input.GetBaseName()
                    val = shader_input.Get()
                    if val is not None:
                        shader_params[input_name] = _usd_to_json(val)

        return {
            "prim_path": prim_path,
            "has_material": True,
            "material_path": mat_path_str,
            "shader_type": shader_type,
            "shader_params": shader_params,
        }
