"""
Synapse Render Handler Mixin

Extracted from handlers.py -- contains viewport capture, render, keyframe,
render settings, wedge, and material handlers for the SynapseHandler class.
"""

import logging
import os
import time
from typing import Dict

logger = logging.getLogger(__name__)

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default, USD_PARM_ALIASES
from ..core.determinism import round_float, kahan_sum
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


_VALIDATE_CHECKS = ("file_integrity", "black_frame", "nan_check",
                     "clipping", "underexposure", "saturation")

_VALIDATE_DEFAULTS = {
    "black_frame_mean": 0.001,
    "clipping_pct": 0.5,
    "underexposure_mean": 0.05,
    "saturation_pct": 0.1,
    "saturation_multiplier": 10.0,
}


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
            used_flipbook = False
            render_ok = False
            for _ in range(60):
                if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
                    render_ok = True
                    break
                time.sleep(0.25)

            # -- Flipbook fallback for usdrender ROPs (husk may fail on Indie) --
            if not render_ok and node_type in ("usdrender", "usdrender_rop"):
                logger.warning(
                    "Render output not found after node.render() -- "
                    "attempting viewport flipbook fallback (husk may not "
                    "support this license type)"
                )
                try:
                    desktop = hou.ui.curDesktop()
                    sv = desktop.paneTabOfType(hou.paneTabType.SceneViewer)
                    if sv is not None:
                        hou.setFrame(cur)
                        vp = sv.curViewport()
                        fb_settings = sv.flipbookSettings()
                        ext = "jpg"
                        fb_pattern = out_path.replace(
                            f".{ext}", f".$F4.{ext}"
                        )
                        fb_settings.frameRange((cur, cur))
                        fb_settings.output(fb_pattern)
                        fb_settings.useResolution(True)
                        w_fb = int(width) if width else 640
                        h_fb = int(height) if height else 480
                        fb_settings.resolution((w_fb, h_fb))
                        sv.flipbook(
                            viewport=vp,
                            settings=fb_settings,
                            open_dialog=False,
                        )
                        fb_actual = fb_pattern.replace(
                            "$F4", f"{cur:04d}"
                        )
                        if (
                            Path(fb_actual).exists()
                            and Path(fb_actual).stat().st_size > 0
                        ):
                            used_flipbook = True
                            out_path = fb_actual
                            render_ok = True
                except Exception as fb_err:
                    logger.warning(
                        "Flipbook fallback also failed: %s", fb_err
                    )

            if not render_ok:
                raise RuntimeError(
                    f"The render finished but the output wasn't created at {out_path} -- "
                    "check if the output directory is writable and the renderer didn't error"
                )
            return out_path, node.path(), node_type, engine, used_flipbook

        import hdefereval
        result_path, used_rop, used_type, engine, used_flipbook = (
            hdefereval.executeInMainThreadWithResult(_render_on_main)
        )
        result = {
            "image_path": result_path,
            "rop": used_rop,
            "rop_type": used_type,
            "engine": engine,
            "width": int(width) if width else None,
            "height": int(height) if height else None,
            "format": "jpeg",
        }
        if used_flipbook:
            result["flipbook_fallback"] = True
        return result

    def _handle_set_keyframe(self, payload: Dict) -> Dict:
        """Set a keyframe on a node parameter at a specific frame."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")
        value = resolve_param(payload, "value")
        frame = resolve_param_with_default(payload, "frame", None)

        from .main_thread import run_on_main

        def _on_main():
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

        return run_on_main(_on_main)

    def _handle_render_settings(self, payload: Dict) -> Dict:
        """Read and optionally modify render settings on a ROP or Karma node."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        node_path = resolve_param(payload, "node")
        overrides = resolve_param_with_default(payload, "settings", {})

        from .main_thread import run_on_main

        def _on_main():
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
            if isinstance(overrides, dict):
                for k, v in sorted(overrides.items()):
                    p = node.parm(k)
                    if p:
                        p.set(v)
                        settings[k] = v

            return {"node": node_path, "settings": settings}

        return run_on_main(_on_main)

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

    # =========================================================================
    # TOPS / PDG HANDLERS
    # =========================================================================

    def _handle_tops_get_work_items(self, payload: Dict) -> Dict:
        """Get work items from a TOP node with optional state filtering.

        Returns work item details including id, index, name, state, cook time,
        and optionally attributes. Useful for inspecting what a TOP node produced.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        state_filter = resolve_param_with_default(payload, "state_filter", "all")
        include_attrs = resolve_param_with_default(payload, "include_attributes", True)
        limit = resolve_param_with_default(payload, "limit", 100)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            # Map state names to pdg.workItemState values
            import pdg as _pdg
            state_map = {
                "cooked": _pdg.workItemState.CookedSuccess,
                "failed": _pdg.workItemState.CookedFail,
                "cooking": _pdg.workItemState.Cooking,
                "scheduled": _pdg.workItemState.Scheduled,
                "uncooked": _pdg.workItemState.Uncooked,
                "cancelled": _pdg.workItemState.CookedCancel,
            }

            all_items = pdg_node.workItems
            items = []
            for wi in all_items:
                # Apply state filter
                if state_filter != "all":
                    expected_state = state_map.get(state_filter.lower())
                    if expected_state is not None and wi.state != expected_state:
                        continue

                item = {
                    "id": wi.id,
                    "index": wi.index,
                    "name": wi.name,
                    "state": wi.state.name if hasattr(wi.state, 'name') else str(wi.state),
                    "cook_time": round_float(getattr(wi, 'cookTime', 0.0)),
                }

                if include_attrs:
                    attrs = {}
                    try:
                        for attr in wi.attribs:
                            try:
                                attrs[attr.name] = attr.values()
                            except Exception:
                                attrs[attr.name] = str(attr)
                    except Exception:
                        pass
                    item["attributes"] = attrs

                items.append(item)
                if len(items) >= int(limit):
                    break

            return {
                "node": node_path,
                "total_items": len(all_items),
                "returned": len(items),
                "filter": state_filter,
                "items": items,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_get_dependency_graph(self, payload: Dict) -> Dict:
        """Get the dependency graph for a TOP network.

        Returns nodes with their types, work item counts by state, and
        edges representing connections between TOP nodes.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        depth = resolve_param_with_default(payload, "depth", -1)

        def _run():
            node = hou.node(topnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {topnet_path} -- "
                    "double-check the path exists"
                )

            # Verify it's a TOP network
            cat = node.type().category().name()
            if cat not in ("TopNet", "Top"):
                raise ValueError(
                    f"The node at {topnet_path} is a {cat} node, not a TOP network -- "
                    "point to a topnet node (e.g. '/obj/topnet1')"
                )

            children = node.children()
            nodes = []
            edges = []

            for child in children:
                node_info = {
                    "name": child.name(),
                    "path": child.path(),
                    "type": child.type().name(),
                }

                # Get work item counts by state if PDG node exists
                pdg_node = child.getPDGNode()
                if pdg_node is not None:
                    by_state = {}
                    for wi in pdg_node.workItems:
                        state_name = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                        by_state[state_name] = by_state.get(state_name, 0) + 1
                    node_info["work_items"] = dict(sorted(by_state.items()))
                    node_info["total_items"] = sum(by_state.values())
                else:
                    node_info["work_items"] = {}
                    node_info["total_items"] = 0

                nodes.append(node_info)

                # Build edges from input connections
                for conn in child.inputConnections():
                    edges.append({
                        "from": conn.inputNode().path(),
                        "to": child.path(),
                        "input_index": conn.inputIndex(),
                        "output_index": conn.outputIndex(),
                    })

            return {
                "topnet": topnet_path,
                "node_count": len(nodes),
                "nodes": nodes,
                "edges": edges,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_get_cook_stats(self, payload: Dict) -> Dict:
        """Get cook statistics for a TOP node or network.

        For a single TOP node: work item counts by state and total cook time.
        For a TOP network: aggregate stats across all child nodes.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()

            def _node_stats(n):
                """Get stats for a single TOP node."""
                pdg_node = n.getPDGNode()
                if pdg_node is None:
                    return {"name": n.name(), "path": n.path(), "by_state": {}, "total_items": 0, "cook_time": 0.0}
                by_state = {}
                cook_times = []
                for wi in pdg_node.workItems:
                    state_name = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                    by_state[state_name] = by_state.get(state_name, 0) + 1
                    cook_times.append(getattr(wi, 'cookTime', 0.0))
                return {
                    "name": n.name(),
                    "path": n.path(),
                    "by_state": dict(sorted(by_state.items())),
                    "total_items": sum(by_state.values()),
                    "cook_time": kahan_sum(cook_times),
                }

            if cat == "TopNet":
                # Aggregate over children
                node_stats = []
                agg_by_state = {}
                cook_times = []
                total_items = 0
                for child in node.children():
                    s = _node_stats(child)
                    node_stats.append(s)
                    cook_times.append(s["cook_time"])
                    total_items += s["total_items"]
                    for state, count in sorted(s["by_state"].items()):
                        agg_by_state[state] = agg_by_state.get(state, 0) + count
                return {
                    "node": node_path,
                    "is_network": True,
                    "total_items": total_items,
                    "by_state": dict(sorted(agg_by_state.items())),
                    "total_cook_time": kahan_sum(cook_times),
                    "nodes": node_stats,
                }
            else:
                s = _node_stats(node)
                return {
                    "node": node_path,
                    "is_network": False,
                    "total_items": s["total_items"],
                    "by_state": s["by_state"],  # already sorted by _node_stats
                    "total_cook_time": s["cook_time"],
                    "nodes": [s],
                }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_cook_node(self, payload: Dict) -> Dict:
        """Cook a TOP node, optionally generating work items only.

        Supports blocking (wait for cook) and non-blocking (fire-and-forget)
        modes. Use generate_only=True to create work items without cooking.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        generate_only = resolve_param_with_default(payload, "generate_only", False)
        blocking = resolve_param_with_default(payload, "blocking", True)
        top_down = resolve_param_with_default(payload, "top_down", True)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            # Verify it has a PDG node
            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            if generate_only:
                node.generateStaticItems()
                item_count = len(pdg_node.workItems)
                return {
                    "node": node_path,
                    "status": "generated",
                    "work_items": item_count,
                }

            node.cook(block=bool(blocking))
            item_count = len(pdg_node.workItems)
            return {
                "node": node_path,
                "status": "cooked" if blocking else "cooking",
                "work_items": item_count,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_generate_items(self, payload: Dict) -> Dict:
        """Generate work items for a TOP node without cooking.

        Creates static work items based on the node's configuration.
        Useful for previewing what a node will produce before cooking.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            node.generateStaticItems()
            item_count = len(pdg_node.workItems)
            return {
                "node": node_path,
                "status": "generated",
                "item_count": item_count,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS — Phase 2: Scheduler & Control
    # =========================================================================

    def _handle_tops_configure_scheduler(self, payload: Dict) -> Dict:
        """Configure the scheduler for a TOP network.

        Sets scheduler type, max concurrent processes, and working directory
        on the topnet's scheduler child node.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        scheduler_type = resolve_param_with_default(payload, "scheduler_type", "local")
        max_concurrent = resolve_param(payload, "max_concurrent", required=False)
        working_dir = resolve_param(payload, "working_dir", required=False)

        def _run():
            node = hou.node(topnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {topnet_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()
            if cat not in ("TopNet",):
                raise ValueError(
                    f"The node at {topnet_path} is a {cat} node, not a TOP network -- "
                    "point to a topnet node (e.g. '/obj/topnet1')"
                )

            # Find scheduler child node
            scheduler_node = None
            for child in node.children():
                child_type = child.type().name().lower()
                if "scheduler" in child_type or child_type == "localscheduler":
                    scheduler_node = child
                    break

            if scheduler_node is None:
                raise ValueError(
                    f"Couldn't find a scheduler node inside {topnet_path} -- "
                    "make sure the TOP network has a scheduler (e.g. localscheduler)"
                )

            # Configure max concurrent processes
            if max_concurrent is not None:
                menu_parm = scheduler_node.parm("maxprocsmenu")
                if menu_parm:
                    menu_parm.set("custom")
                procs_parm = scheduler_node.parm("maxprocs")
                if procs_parm:
                    procs_parm.set(int(max_concurrent))

            # Configure working directory
            if working_dir is not None:
                wd_parm = scheduler_node.parm("pdg_workingdir")
                if wd_parm:
                    wd_parm.set(str(working_dir))

            result = {
                "topnet": topnet_path,
                "scheduler_node": scheduler_node.path(),
                "scheduler_type": scheduler_type,
                "status": "configured",
            }
            if max_concurrent is not None:
                result["max_concurrent"] = int(max_concurrent)
            if working_dir is not None:
                result["working_dir"] = str(working_dir)
            return result

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_cancel_cook(self, payload: Dict) -> Dict:
        """Cancel an active cook on a TOP node or network.

        For TOP networks: cancels the entire PDG graph context cook.
        For single TOP nodes: dirties the node to stop its cook.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()

            if cat == "TopNet":
                # Cancel the entire PDG graph context
                try:
                    ctx = node.getPDGGraphContext()
                    if ctx is not None:
                        ctx.cancelCook()
                except Exception:
                    # Fallback: dirty all children
                    for child in node.children():
                        pdg_node = child.getPDGNode()
                        if pdg_node is not None:
                            pdg_node.dirty(False)
            else:
                # Single TOP node — dirty it to stop cooking
                pdg_node = node.getPDGNode()
                if pdg_node is not None:
                    pdg_node.dirty(False)

            return {
                "node": node_path,
                "status": "cancelled",
                "note": "Currently cooking items may finish before cancellation takes effect",
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_dirty_node(self, payload: Dict) -> Dict:
        """Dirty a TOP node, optionally including upstream nodes.

        Dirtying removes cached work item results, forcing a re-cook.
        Use dirty_upstream=True to also dirty all upstream dependencies.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        dirty_upstream = resolve_param_with_default(payload, "dirty_upstream", False)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is not None:
                pdg_node.dirty(bool(dirty_upstream))
            else:
                # Fallback for nodes without PDG node
                try:
                    node.dirtyAllTasks(False)
                except AttributeError:
                    raise ValueError(
                        f"The node at {node_path} isn't a TOP node -- "
                        "make sure it's inside a TOP network"
                    )

            return {
                "node": node_path,
                "status": "dirtied",
                "dirty_upstream": bool(dirty_upstream),
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS — Phase 3: Advanced
    # =========================================================================

    def _handle_tops_setup_wedge(self, payload: Dict) -> Dict:
        """Set up a Wedge TOP node for parameter variation exploration.

        Creates a wedge node inside a TOP network and configures its
        attributes (multiparm) for systematic parameter sweeps.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        wedge_name = resolve_param_with_default(payload, "wedge_name", "wedge1")
        attributes = resolve_param(payload, "attributes")

        if not isinstance(attributes, list) or len(attributes) == 0:
            raise ValueError(
                "The 'attributes' parameter should be a list of attribute definitions "
                "(each with name, type, start, end, steps)"
            )

        def _run():
            node = hou.node(topnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {topnet_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()
            if cat not in ("TopNet",):
                raise ValueError(
                    f"The node at {topnet_path} is a {cat} node, not a TOP network -- "
                    "point to a topnet node (e.g. '/obj/topnet1')"
                )

            wedge_node = node.createNode("wedge", wedge_name)
            wedge_node.moveToGoodPosition()

            # Configure wedge attributes via multiparm
            sorted_attrs = sorted(attributes, key=lambda a: a.get("name", ""))
            num_attrs = len(sorted_attrs)
            multiparm = wedge_node.parm("wedgeattributes")
            if multiparm:
                multiparm.set(num_attrs)

            total_variations = 1
            attr_results = []
            for i, attr in enumerate(sorted_attrs):
                idx = i + 1  # 1-indexed multiparm
                attr_name = attr.get("name", f"attr_{i}")
                attr_type = attr.get("type", "float")
                start = attr.get("start", 0)
                end = attr.get("end", 1)
                steps = attr.get("steps", 5)

                # Set wedge attribute parameters
                name_parm = wedge_node.parm(f"name{idx}")
                if name_parm:
                    name_parm.set(attr_name)

                type_parm = wedge_node.parm(f"type{idx}")
                if type_parm:
                    type_map = {"float": 0, "int": 1, "string": 2}
                    type_parm.set(type_map.get(attr_type, 0))

                start_parm = wedge_node.parm(f"range{idx}x")
                if start_parm:
                    start_parm.set(float(start))

                end_parm = wedge_node.parm(f"range{idx}y")
                if end_parm:
                    end_parm.set(float(end))

                steps_parm = wedge_node.parm(f"steps{idx}")
                if steps_parm:
                    steps_parm.set(int(steps))

                total_variations *= int(steps)
                attr_results.append({
                    "name": attr_name,
                    "type": attr_type,
                    "start": round_float(float(start)),
                    "end": round_float(float(end)),
                    "steps": int(steps),
                })

            return {
                "topnet": topnet_path,
                "wedge_node": wedge_node.path(),
                "attributes": attr_results,
                "total_variations": total_variations,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_batch_cook(self, payload: Dict) -> Dict:
        """Cook multiple TOP nodes in sequence, collecting results.

        Cooks each node in order and collects per-node results including
        status, work item counts, and cook times. Uses kahan_sum for
        stable total cook time aggregation (He2025).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_paths = resolve_param(payload, "node_paths")
        blocking = resolve_param_with_default(payload, "blocking", True)
        stop_on_error = resolve_param_with_default(payload, "stop_on_error", True)

        if not isinstance(node_paths, list) or len(node_paths) == 0:
            raise ValueError(
                "The 'node_paths' parameter should be a list of TOP node paths"
            )

        def _run():
            results = []
            cook_times = []
            by_state = {}
            errors = []

            for node_path in node_paths:
                node = hou.node(node_path)
                if node is None:
                    err = f"Couldn't find a node at {node_path}"
                    if stop_on_error:
                        raise ValueError(err)
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": 0.0,
                    })
                    errors.append(node_path)
                    continue

                pdg_node = node.getPDGNode()
                if pdg_node is None:
                    err = f"The node at {node_path} isn't a TOP node"
                    if stop_on_error:
                        raise ValueError(err)
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": 0.0,
                    })
                    errors.append(node_path)
                    continue

                t0 = time.monotonic()
                try:
                    node.cook(block=bool(blocking))
                    elapsed = time.monotonic() - t0
                    item_count = len(pdg_node.workItems)

                    # Collect per-node state counts
                    node_states = {}
                    for wi in pdg_node.workItems:
                        sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                        node_states[sname] = node_states.get(sname, 0) + 1

                    for sname, count in sorted(node_states.items()):
                        by_state[sname] = by_state.get(sname, 0) + count

                    results.append({
                        "node": node_path,
                        "status": "cooked" if blocking else "cooking",
                        "work_items": item_count,
                        "cook_time": round_float(elapsed),
                    })
                    cook_times.append(elapsed)
                except Exception as e:
                    elapsed = time.monotonic() - t0
                    err = str(e)
                    if stop_on_error:
                        raise
                    results.append({
                        "node": node_path,
                        "status": "error",
                        "error": err,
                        "cook_time": round_float(elapsed),
                    })
                    cook_times.append(elapsed)
                    errors.append(node_path)

            total = kahan_sum(cook_times)
            cooked = sum(1 for r in results if r["status"] in ("cooked", "cooking"))
            summary = f"Cooked {cooked}/{len(node_paths)} nodes"
            if errors:
                summary += f", {len(errors)} error(s)"

            return {
                "nodes": results,
                "total_cook_time": round_float(total),
                "by_state": dict(sorted(by_state.items())),
                "summary": summary,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_query_items(self, payload: Dict) -> Dict:
        """Query work items by attribute value with filter operators.

        Searches work items on a TOP node for those matching a condition
        on a specific attribute. Supports eq, gt, lt, gte, lte, contains,
        and regex operators.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval
        import re

        node_path = resolve_param(payload, "node")
        attr_name = resolve_param(payload, "query_attribute")
        filter_op = resolve_param_with_default(payload, "filter_op", "eq")
        filter_value = resolve_param(payload, "filter_value")

        valid_ops = ("eq", "gt", "lt", "gte", "lte", "contains", "regex")
        if filter_op not in valid_ops:
            raise ValueError(
                f"Unknown filter operator '{filter_op}'. "
                f"Available: {', '.join(valid_ops)}"
            )

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet"
                )

            all_items = pdg_node.workItems
            matched = []

            for wi in all_items:
                # Find the attribute
                attr_val = None
                for attr in getattr(wi, 'attribs', []):
                    if attr.name == attr_name:
                        vals = attr.values()
                        attr_val = vals[0] if len(vals) == 1 else vals
                        break

                if attr_val is None:
                    continue

                # Apply filter
                try:
                    if filter_op == "eq" and attr_val == filter_value:
                        pass
                    elif filter_op == "gt" and float(attr_val) > float(filter_value):
                        pass
                    elif filter_op == "lt" and float(attr_val) < float(filter_value):
                        pass
                    elif filter_op == "gte" and float(attr_val) >= float(filter_value):
                        pass
                    elif filter_op == "lte" and float(attr_val) <= float(filter_value):
                        pass
                    elif filter_op == "contains" and str(filter_value) in str(attr_val):
                        pass
                    elif filter_op == "regex" and re.search(str(filter_value), str(attr_val)):
                        pass
                    else:
                        continue
                except (TypeError, ValueError):
                    continue

                # Round float values in output (He2025)
                display_val = round_float(attr_val) if isinstance(attr_val, float) else attr_val

                matched.append({
                    "id": wi.id,
                    "name": wi.name,
                    "state": wi.state.name if hasattr(wi.state, 'name') else str(wi.state),
                    "attribute_value": display_val,
                })

            return {
                "node": node_path,
                "attribute": attr_name,
                "operator": filter_op,
                "value": filter_value,
                "matched_count": len(matched),
                "total_count": len(all_items),
                "items": matched,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    # =========================================================================
    # TOPS / PDG HANDLERS — Phase 4: Autonomous Operations
    # =========================================================================

    def _handle_tops_cook_and_validate(self, payload: Dict) -> Dict:
        """Cook a TOP node with optional retry on failure (Item 15: self-healing).

        Blocking cook -> collect work item states -> if failures AND retries
        remaining -> dirty -> re-cook -> repeat. Returns per-attempt details
        and aggregate stats.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        max_retries = resolve_param_with_default(payload, "max_retries", 0)
        validate_states = resolve_param_with_default(payload, "validate_states", True)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            attempts = []
            total_elapsed_start = time.monotonic()

            for attempt_num in range(1, int(max_retries) + 2):
                t0 = time.monotonic()
                node.cook(block=True)
                cook_time = time.monotonic() - t0

                # Collect state counts
                by_state = {}
                failed_count = 0
                for wi in pdg_node.workItems:
                    sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                    by_state[sname] = by_state.get(sname, 0) + 1
                    if sname == "CookedFail":
                        failed_count += 1

                total_items = sum(by_state.values())
                attempt_info = {
                    "attempt": attempt_num,
                    "cook_time": round_float(cook_time),
                    "work_items": total_items,
                    "by_state": dict(sorted(by_state.items())),
                    "failed_items": failed_count,
                }

                if validate_states and failed_count > 0 and attempt_num <= int(max_retries):
                    attempt_info["status"] = "retry"
                    attempts.append(attempt_info)
                    # Dirty and retry
                    pdg_node.dirty(False)
                    continue
                else:
                    status = "success" if failed_count == 0 else "failed"
                    attempt_info["status"] = status
                    attempts.append(attempt_info)
                    break

            total_elapsed = time.monotonic() - total_elapsed_start
            all_cook_times = [a["cook_time"] for a in attempts]
            final_by_state = attempts[-1]["by_state"]

            return {
                "node": node_path,
                "status": attempts[-1]["status"],
                "attempts": attempts,
                "total_attempts": len(attempts),
                "total_cook_time": kahan_sum(all_cook_times),
                "total_elapsed": round_float(total_elapsed),
                "final_by_state": final_by_state,
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_diagnose(self, payload: Dict) -> Dict:
        """Diagnose failures on a TOP node -- inspect work items, scheduler,
        upstream dependencies, and generate actionable suggestions.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        node_path = resolve_param(payload, "node")
        include_scheduler = resolve_param_with_default(payload, "include_scheduler", True)
        include_dependencies = resolve_param_with_default(payload, "include_dependencies", True)

        def _run():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} -- "
                    "double-check the path exists"
                )

            pdg_node = node.getPDGNode()
            if pdg_node is None:
                raise ValueError(
                    f"The node at {node_path} isn't a TOP node or hasn't been "
                    "set up for PDG yet -- make sure it's inside a TOP network"
                )

            node_type = node.type().name()

            # Collect work item states and details
            by_state = {}
            failed_details = []
            cook_times = []
            for wi in pdg_node.workItems:
                sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                by_state[sname] = by_state.get(sname, 0) + 1
                cook_times.append(getattr(wi, 'cookTime', 0.0))
                if sname == "CookedFail":
                    failed_details.append({
                        "id": wi.id,
                        "name": wi.name,
                        "state": sname,
                    })

            total_items = sum(by_state.values())
            total_cook_time = kahan_sum(cook_times)

            result = {
                "node": node_path,
                "node_type": node_type,
                "total_items": total_items,
                "by_state": dict(sorted(by_state.items())),
                "failed_items": len(failed_details),
                "failed_details": sorted(failed_details, key=lambda d: d["id"]),
                "total_cook_time": round_float(total_cook_time),
            }

            # Scheduler info
            if include_scheduler:
                scheduler_info = None
                parent = node.parent()
                if parent is not None:
                    for child in parent.children():
                        child_type = child.type().name().lower()
                        if "scheduler" in child_type or child_type == "localscheduler":
                            sched_info = {
                                "path": child.path(),
                                "type": child.type().name(),
                            }
                            procs_parm = child.parm("maxprocs")
                            if procs_parm is not None:
                                sched_info["max_procs"] = procs_parm.eval()
                            scheduler_info = sched_info
                            break
                result["scheduler"] = scheduler_info

            # Upstream dependency check
            if include_dependencies:
                upstream = []
                for conn in node.inputConnections():
                    inp_node = conn.inputNode()
                    inp_pdg = inp_node.getPDGNode()
                    inp_by_state = {}
                    has_failures = False
                    if inp_pdg is not None:
                        for wi in inp_pdg.workItems:
                            sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                            inp_by_state[sname] = inp_by_state.get(sname, 0) + 1
                            if sname == "CookedFail":
                                has_failures = True
                    upstream.append({
                        "path": inp_node.path(),
                        "type": inp_node.type().name(),
                        "by_state": dict(sorted(inp_by_state.items())),
                        "has_failures": has_failures,
                    })
                result["upstream"] = sorted(upstream, key=lambda u: u["path"])

            # Generate suggestions
            suggestions = []
            if len(failed_details) > 0:
                suggestions.append(
                    f"{len(failed_details)} work item(s) failed -- "
                    "check error messages in failed_details"
                )
            if total_items == 0:
                suggestions.append(
                    "No work items found -- the node may need to generate items first"
                )
            if include_dependencies:
                for u in result.get("upstream", []):
                    if u["has_failures"]:
                        suggestions.append(
                            f"Upstream node {u['path']} has failures -- fix upstream first"
                        )
            result["suggestions"] = sorted(suggestions)

            return result

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_tops_pipeline_status(self, payload: Dict) -> Dict:
        """Full health check for a TOP network -- walk all child nodes,
        aggregate work item counts, detect issues, generate suggestions.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        topnet_path = resolve_param(payload, "topnet_path")
        include_items = resolve_param_with_default(payload, "include_items", False)

        def _run():
            node = hou.node(topnet_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {topnet_path} -- "
                    "double-check the path exists"
                )

            cat = node.type().category().name()
            if cat not in ("TopNet",):
                raise ValueError(
                    f"The node at {topnet_path} is a {cat} node, not a TOP network -- "
                    "point to a topnet node (e.g. '/obj/topnet1')"
                )

            nodes_info = []
            agg_by_state = {}
            all_cook_times = []
            total_items = 0
            issues = []

            for child in node.children():
                # Skip scheduler nodes
                child_type = child.type().name().lower()
                if "scheduler" in child_type or child_type == "localscheduler":
                    continue

                pdg_child = child.getPDGNode()
                child_by_state = {}
                child_cook_times = []
                child_total = 0
                child_items = []

                if pdg_child is not None:
                    for wi in pdg_child.workItems:
                        sname = wi.state.name if hasattr(wi.state, 'name') else str(wi.state)
                        child_by_state[sname] = child_by_state.get(sname, 0) + 1
                        child_cook_times.append(getattr(wi, 'cookTime', 0.0))
                        if include_items:
                            child_items.append({
                                "id": wi.id,
                                "name": wi.name,
                                "state": sname,
                            })

                child_total = sum(child_by_state.values())
                child_cook_time = kahan_sum(child_cook_times)

                # Determine per-node health
                failed_count = child_by_state.get("CookedFail", 0)
                if failed_count > 0:
                    health = "error"
                    issues.append(f"{child.path()}: {failed_count} failed work item(s)")
                elif child_total == 0:
                    health = "empty"
                else:
                    health = "healthy"

                node_info = {
                    "path": child.path(),
                    "name": child.name(),
                    "type": child.type().name(),
                    "health": health,
                    "by_state": dict(sorted(child_by_state.items())),
                    "total_items": child_total,
                    "cook_time": round_float(child_cook_time),
                }
                if include_items and child_items:
                    node_info["items"] = child_items

                nodes_info.append(node_info)

                # Aggregate
                total_items += child_total
                all_cook_times.append(child_cook_time)
                for sname, count in sorted(child_by_state.items()):
                    agg_by_state[sname] = agg_by_state.get(sname, 0) + count

            # Overall health
            total_failed = agg_by_state.get("CookedFail", 0)
            if total_failed > 0:
                overall_health = "error"
            elif total_items == 0:
                overall_health = "empty"
            else:
                overall_health = "healthy"

            # Suggestions
            suggestions = []
            if total_failed > 0:
                suggestions.append(
                    f"{total_failed} total failed work item(s) -- "
                    "use tops_diagnose for details"
                )
            if total_items == 0:
                suggestions.append(
                    "No work items in the network -- "
                    "nodes may need to generate or cook first"
                )

            return {
                "topnet": topnet_path,
                "overall_health": overall_health,
                "node_count": len(nodes_info),
                "total_items": total_items,
                "by_state": dict(sorted(agg_by_state.items())),
                "total_cook_time": kahan_sum(all_cook_times),
                "nodes": sorted(nodes_info, key=lambda n: n["path"]),
                "issues": sorted(issues),
                "suggestions": sorted(suggestions),
            }

        return hdefereval.executeInMainThreadWithResult(_run)

    def _handle_create_material(self, payload: Dict) -> Dict:
        """Create a materiallibrary LOP with a MaterialX shader inside it.

        Uses native Houdini nodes (materiallibrary + shader child) so the
        material is visible and editable in the artist's network.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        name = resolve_param_with_default(payload, "name", "material")
        shader_type = resolve_param_with_default(
            payload, "shader_type", "mtlxstandard_surface"
        )
        base_color = resolve_param(payload, "base_color", required=False)
        metalness = resolve_param(payload, "metalness", required=False)
        roughness = resolve_param(payload, "roughness", required=False)

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

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

        return run_on_main(_on_main)

    def _handle_assign_material(self, payload: Dict) -> Dict:
        """Create an assignmaterial LOP to bind a material to geometry prims."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        prim_pattern = resolve_param(payload, "prim_pattern")
        material_path = resolve_param(payload, "material_path")

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

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

        return run_on_main(_on_main)

    def _handle_read_material(self, payload: Dict) -> Dict:
        """Read material binding and shader parameters from a USD prim.

        Pure stage query -- no node creation. Uses UsdShade API to inspect
        material bindings and shader inputs.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path_arg = resolve_param(payload, "node", required=False)
        prim_path = resolve_param(payload, "prim_path")

        from .main_thread import run_on_main

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]

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

        return run_on_main(_on_main)

    def _handle_validate_frame(self, payload: Dict) -> Dict:
        """Validate a rendered frame for common quality issues.

        Checks for black frames, NaN/Inf pixels, clipping, underexposure,
        and firefly (saturation) artifacts. Uses OpenImageIO for fast C++-level
        pixel analysis. Gracefully degrades to file-integrity-only if OIIO
        is unavailable.
        """
        image_path = resolve_param(payload, "image_path")
        requested_checks = resolve_param_with_default(payload, "checks", None)
        threshold_overrides = resolve_param_with_default(payload, "thresholds", None) or {}

        # Determine which checks to run
        if requested_checks is not None:
            if not isinstance(requested_checks, list):
                requested_checks = [requested_checks]
            invalid = [c for c in requested_checks if c not in _VALIDATE_CHECKS]
            if invalid:
                raise ValueError(
                    f"Unknown check(s): {', '.join(invalid)}. "
                    f"Available checks: {', '.join(_VALIDATE_CHECKS)}"
                )
            check_set = set(requested_checks)
        else:
            check_set = set(_VALIDATE_CHECKS)

        # Merge thresholds
        thresholds = dict(_VALIDATE_DEFAULTS)
        for k, v in sorted(threshold_overrides.items()):
            if k in thresholds:
                thresholds[k] = float(v)

        checks_result = {}
        issues = []

        # --- File integrity (always runs, no OIIO needed) ---
        if "file_integrity" in check_set:
            fi = self._validate_file_integrity(image_path)
            checks_result["file_integrity"] = fi
            if not fi["passed"]:
                issues.append("file_integrity")
                # Can't continue without a valid file
                return {
                    "valid": False,
                    "image_path": image_path,
                    "resolution": None,
                    "channels": None,
                    "format": None,
                    "checks": dict(sorted(checks_result.items())),
                    "summary": f"Frame has 1 issue(s): file_integrity",
                    "oiio_available": False,
                }

        # --- Try to load OIIO ---
        oiio = None
        try:
            import OpenImageIO as oiio
        except ImportError:
            try:
                import oiio as oiio
            except ImportError:
                pass

        if oiio is None:
            # No OIIO -- return file-integrity-only result
            return {
                "valid": len(issues) == 0,
                "image_path": image_path,
                "resolution": None,
                "channels": None,
                "format": None,
                "checks": dict(sorted(checks_result.items())),
                "summary": "OIIO unavailable -- only file integrity checked",
                "oiio_available": False,
            }

        # --- Open image with OIIO ---
        inp = oiio.ImageInput.open(image_path)
        if inp is None:
            checks_result["file_integrity"] = {
                "passed": False,
                "value": 0,
                "threshold": 0,
                "detail": f"OIIO couldn't open the file: {oiio.geterror()}",
            }
            return {
                "valid": False,
                "image_path": image_path,
                "resolution": None,
                "channels": None,
                "format": None,
                "checks": dict(sorted(checks_result.items())),
                "summary": "Frame has 1 issue(s): file_integrity",
                "oiio_available": True,
            }

        spec = inp.spec()
        width, height, channels = spec.width, spec.height, spec.nchannels
        fmt_str = str(spec.format)
        inp.close()

        # --- Compute pixel stats via ImageBuf ---
        buf = oiio.ImageBuf(image_path)
        stats = oiio.ImageBufAlgo.computePixelStats(buf)

        # --- Per-pixel data (only if needed) ---
        need_pixels = bool(check_set & {"clipping", "saturation"})
        pixels = None
        pixel_count = 0

        if need_pixels:
            import numpy as np
            pixels = buf.get_pixels(oiio.FLOAT)
            # Downsample if > 8MP
            total_pixels = width * height
            if total_pixels > 8_000_000:
                pixels = pixels[::2, ::2, :]
                pixel_count = pixels.shape[0] * pixels.shape[1]
            else:
                pixel_count = total_pixels

        # --- Mean luminance (used by multiple checks) ---
        # Average across RGB channels (first 3); ignore alpha
        rgb_channels = min(channels, 3)
        mean_lum = sum(stats.avg[i] for i in range(rgb_channels)) / rgb_channels

        # --- Run requested checks ---
        if "black_frame" in check_set:
            thresh = thresholds["black_frame_mean"]
            passed = mean_lum >= thresh
            checks_result["black_frame"] = {
                "passed": passed,
                "value": round(mean_lum, 6),
                "threshold": thresh,
                "detail": "Mean luminance is adequate" if passed else "Frame appears black or near-black",
            }
            if not passed:
                issues.append("black_frame")

        if "nan_check" in check_set:
            nan_count = sum(stats.nancount[i] for i in range(channels))
            inf_count = sum(stats.infcount[i] for i in range(channels))
            total_bad = nan_count + inf_count
            passed = total_bad == 0
            checks_result["nan_check"] = {
                "passed": passed,
                "value": int(total_bad),
                "threshold": 0,
                "detail": "No NaN/Inf pixels" if passed else f"Found {int(nan_count)} NaN and {int(inf_count)} Inf values",
            }
            if not passed:
                issues.append("nan_check")

        if "clipping" in check_set and pixels is not None:
            import numpy as np
            thresh_pct = thresholds["clipping_pct"]
            rgb = pixels[:, :, :rgb_channels]
            clipped = int(np.sum(rgb >= 1.0))
            total_vals = rgb.size
            clip_pct = (clipped / total_vals) * 100.0 if total_vals > 0 else 0.0
            passed = bool(clip_pct <= thresh_pct)
            checks_result["clipping"] = {
                "passed": passed,
                "value": round(clip_pct, 4),
                "threshold": thresh_pct,
                "detail": "Highlights within range" if passed else f"{clip_pct:.2f}% of values are clipped at 1.0+",
            }
            if not passed:
                issues.append("clipping")

        if "underexposure" in check_set:
            thresh = thresholds["underexposure_mean"]
            passed = mean_lum >= thresh
            checks_result["underexposure"] = {
                "passed": passed,
                "value": round(mean_lum, 6),
                "threshold": thresh,
                "detail": "Exposure looks adequate" if passed else "Frame appears underexposed",
            }
            if not passed:
                issues.append("underexposure")

        if "saturation" in check_set and pixels is not None:
            import numpy as np
            thresh_pct = thresholds["saturation_pct"]
            multiplier = thresholds["saturation_multiplier"]
            rgb = pixels[:, :, :rgb_channels]
            firefly_threshold = mean_lum * multiplier
            if firefly_threshold > 0:
                hot_pixels = int(np.sum(rgb > firefly_threshold))
                total_vals = rgb.size
                sat_pct = (hot_pixels / total_vals) * 100.0 if total_vals > 0 else 0.0
            else:
                sat_pct = 0.0
            passed = bool(sat_pct <= thresh_pct)
            checks_result["saturation"] = {
                "passed": passed,
                "value": round(sat_pct, 4),
                "threshold": thresh_pct,
                "detail": "No firefly artifacts detected" if passed else f"{sat_pct:.2f}% of values exceed {multiplier}x mean",
            }
            if not passed:
                issues.append("saturation")

        # --- Build result ---
        all_passed = len(issues) == 0
        if all_passed:
            summary = "Frame looks good"
        else:
            summary = f"Frame has {len(issues)} issue(s): {', '.join(sorted(issues))}"

        return {
            "valid": all_passed,
            "image_path": image_path,
            "resolution": [width, height],
            "channels": channels,
            "format": fmt_str,
            "checks": dict(sorted(checks_result.items())),
            "summary": summary,
            "oiio_available": True,
        }

    # =========================================================================
    # RENDER FARM HANDLERS
    # =========================================================================

    def _handle_render_sequence(self, payload: Dict) -> Dict:
        """Render a frame sequence with per-frame validation and auto-fix.

        Orchestrates multi-frame renders through the RenderFarmOrchestrator,
        which handles validation, diagnostics, and automatic re-renders.

        Auto-fix remedies target the Karma Render Properties LOP (where the
        real quality parms live), not the usdrender ROP itself. Discovery:
        ROP.loppath -> walk LOP children for 'karmarenderproperties' type.
        """
        from .render_farm import RenderFarmOrchestrator, RenderCallbacks

        start_frame = resolve_param(payload, "start_frame")
        end_frame = resolve_param(payload, "end_frame")
        rop = resolve_param(payload, "rop", required=False)
        step = int(resolve_param_with_default(payload, "step", 1))
        auto_fix = resolve_param_with_default(payload, "auto_fix", True)
        max_retries = int(resolve_param_with_default(payload, "max_retries", 3))

        # Discover the Karma Render Properties LOP where quality parms live.
        # The ROP's loppath parm points to the LOP network; we walk its
        # children looking for a karmarenderproperties node.
        karma_lop_path = None
        if HOU_AVAILABLE and rop:
            try:
                rop_node = hou.node(rop)
                if rop_node is not None:
                    lp = rop_node.parm("loppath")
                    if lp:
                        lop_target = lp.eval()  # noqa: S307
                        if lop_target:
                            lop_node = hou.node(lop_target)
                            if lop_node is not None:
                                # Walk up to the parent LOP network
                                lop_net = lop_node.parent() if lop_node.parent() else lop_node
                                for child in lop_net.children():
                                    if child.type().name() == "karmarenderproperties":
                                        karma_lop_path = child.path()
                                        break
            except Exception:
                pass  # Fall back to ROP path for settings

        # Wrap get/set_render_settings to target the Karma LOP if discovered.
        # The orchestrator always passes the ROP path, but the quality parms
        # (pathtracedsamples, colorlimit, diffuselimit) live on the Karma LOP.
        # When we've found it, always redirect there.
        settings_target = karma_lop_path or rop

        def _get_settings(p):
            return self._handle_render_settings({"node": settings_target})

        def _set_settings(p):
            settings = p.get("settings", {})
            return self._handle_render_settings({"node": settings_target, "settings": settings})

        # Build callbacks wiring to existing handlers
        callbacks = RenderCallbacks(
            render_frame=self._handle_render,
            validate_frame=self._handle_validate_frame,
            get_render_settings=_get_settings,
            set_render_settings=_set_settings,
            get_stage_info=getattr(self, '_handle_get_stage_info', None),
            broadcast=getattr(self, '_broadcast', None),
        )

        # Resolve report directory
        report_dir = None
        if HOU_AVAILABLE:
            try:
                hip = hou.text.expandString("$HIP")
                if hip and hip != "$HIP":
                    report_dir = os.path.join(hip, ".synapse", "render_reports")
            except Exception:
                pass
        if not report_dir:
            report_dir = os.path.join(
                os.path.expanduser("~"), ".synapse", "render_reports"
            )

        # Get or create singleton orchestrator
        if not hasattr(self, '_render_farm') or self._render_farm is None:
            self._render_farm = RenderFarmOrchestrator(
                callbacks=callbacks,
                max_retries=max_retries,
                auto_fix=bool(auto_fix),
                report_dir=report_dir,
            )
        else:
            # Update settings for this run
            self._render_farm._cb = callbacks
            self._render_farm._max_retries = max_retries
            self._render_farm._auto_fix = bool(auto_fix)
            self._render_farm._report_dir = report_dir

        # Inject memory if available
        if hasattr(self, '_memory') and self._memory is not None:
            self._render_farm._memory = self._memory

        # Run the sequence (blocks until complete)
        report = self._render_farm.render_sequence(
            rop=rop or "",
            frame_range=(int(start_frame), int(end_frame)),
            step=step,
        )

        return report.to_dict()

    def _handle_render_farm_status(self, payload: Dict) -> Dict:
        """Get the current render farm status."""
        if hasattr(self, '_render_farm') and self._render_farm is not None:
            return self._render_farm.get_status()
        return {"running": False, "cancelled": False, "scene_tags": []}

    @staticmethod
    def _validate_file_integrity(image_path: str) -> Dict:
        """Check file exists and has non-zero size."""
        if not os.path.isfile(image_path):
            return {
                "passed": False,
                "value": 0,
                "threshold": 0,
                "detail": f"File not found: {image_path}",
            }
        size = os.path.getsize(image_path)
        if size == 0:
            return {
                "passed": False,
                "value": 0,
                "threshold": 0,
                "detail": "File is empty (0 bytes)",
            }
        return {
            "passed": True,
            "value": size,
            "threshold": 0,
            "detail": f"File exists ({size} bytes)",
        }
