"""Render Preflight Checker for SYNAPSE.

Catches common render problems (missing cameras, empty output paths,
unbound materials, missing lights, etc.) BEFORE submitting to the farm.

Usage inside Houdini::

    from synapse.panel.render_preflight import run_preflight, format_preflight_html
    report = run_preflight()           # auto-detect render node
    html   = format_preflight_html(report)

Each check is self-contained: one check raising an exception never
prevents the others from running.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# ── Houdini import guard ────────────────────────────────────────────────
_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]

    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]

# ── OpenUSD import guard ────────────────────────────────────────────────
_PXR_AVAILABLE = False
try:
    from pxr import Sdf, Usd, UsdGeom, UsdLux, UsdShade  # type: ignore[import-untyped]

    _PXR_AVAILABLE = True
except ImportError:
    Usd = Sdf = UsdGeom = UsdLux = UsdShade = None  # type: ignore[assignment]

# ── Optional psutil for memory estimation ───────────────────────────────
_PSUTIL_AVAILABLE = False
try:
    import psutil  # type: ignore[import-untyped]

    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]


# =====================================================================
# Data classes
# =====================================================================


@dataclass
class PreflightCheck:
    """Single preflight check result."""

    name: str  # short identifier: "camera", "output_path", etc.
    status: str  # "pass", "fail", "warn"
    message: str  # human-readable result
    detail: str = ""  # additional info (empty if not needed)
    fix_available: bool = False
    fix_fn: Optional[Callable[[], None]] = None


@dataclass
class PreflightReport:
    """Aggregate report from all preflight checks."""

    checks: List[PreflightCheck] = field(default_factory=list)
    render_node: str = ""  # path to the ROP / Karma node being checked
    ready: bool = False  # True only if zero "fail" checks
    summary: str = ""  # "Preflight: 8/10 passed, 1 warning, 1 failure"

    def _build_summary(self) -> None:
        """Recompute *ready* and *summary* from current checks."""
        n_pass = sum(1 for c in self.checks if c.status == "pass")
        n_warn = sum(1 for c in self.checks if c.status == "warn")
        n_fail = sum(1 for c in self.checks if c.status == "fail")
        total = len(self.checks)
        self.ready = n_fail == 0
        parts = [f"{n_pass}/{total} passed"]
        if n_warn:
            parts.append(f"{n_warn} warning{'s' if n_warn != 1 else ''}")
        if n_fail:
            parts.append(f"{n_fail} failure{'s' if n_fail != 1 else ''}")
        self.summary = f"Preflight: {', '.join(parts)}"


# =====================================================================
# Helpers
# =====================================================================


def _parm_str(node: "hou.Node", names: List[str]) -> Optional[str]:
    """Return the evaluated string value of the first matching parm, or None."""
    for name in names:
        parm = node.parm(name)
        if parm is not None:
            val = parm.evalAsString()
            if val:
                return val
    return None


def _parm_int(node: "hou.Node", name: str) -> Optional[int]:
    parm = node.parm(name)
    if parm is not None:
        return parm.evalAsInt()
    return None


def _is_lop_node(node: "hou.Node") -> bool:
    """Return True if *node* lives inside a LOP network."""
    try:
        return isinstance(node, hou.LopNode)
    except Exception:
        return node.type().category().name() == "Lop"


# =====================================================================
# Auto-detection
# =====================================================================


def _detect_render_node() -> Optional["hou.Node"]:
    """Find a suitable render node automatically.

    Priority:
    1. Karma LOP inside ``/stage`` with the display flag set.
    2. First Karma LOP inside ``/stage``.
    3. First ROP in ``/out``.
    """
    # --- Karma in /stage ---
    stage_net = hou.node("/stage")
    if stage_net is not None:
        karma_nodes: list["hou.Node"] = []
        for child in stage_net.children():
            type_name = child.type().name()
            if type_name in ("karma", "karmarendersettings", "usdrender_rop"):
                karma_nodes.append(child)
        # Prefer the one with display flag
        for kn in karma_nodes:
            try:
                if kn.isDisplayFlagSet():
                    return kn
            except AttributeError:
                pass
        if karma_nodes:
            return karma_nodes[0]

    # --- ROP in /out ---
    out_net = hou.node("/out")
    if out_net is not None:
        for child in out_net.children():
            type_name = child.type().name()
            if type_name in ("usdrender", "usdrender_rop", "karma", "ifd", "ris"):
                return child
        # Fallback: first child of /out
        children = out_net.children()
        if children:
            return children[0]

    return None


# =====================================================================
# Individual checks
# =====================================================================


def check_camera(render_node: "hou.Node") -> PreflightCheck:
    """Is a camera assigned and does it resolve to a valid node/prim?"""
    try:
        cam_path = _parm_str(render_node, ["camera"])
        if not cam_path:
            return PreflightCheck(
                name="camera",
                status="fail",
                message="No camera assigned",
                detail="Set the 'camera' parameter on the render node.",
            )

        # For LOP nodes, camera is a USD prim path -- validate on stage
        if _is_lop_node(render_node) and _PXR_AVAILABLE:
            try:
                stage = render_node.stage()
                if stage:
                    prim = stage.GetPrimAtPath(cam_path)
                    if prim and prim.IsValid():
                        return PreflightCheck(
                            name="camera",
                            status="pass",
                            message=f"Camera: {cam_path}",
                        )
                    else:
                        return PreflightCheck(
                            name="camera",
                            status="fail",
                            message=f"Camera prim not found: {cam_path}",
                            detail="The camera path does not resolve to a valid USD prim.",
                        )
            except Exception:
                pass  # Fall through to node-based check

        # Node-based camera check (OBJ context / ROPs)
        cam_node = hou.node(cam_path)
        if cam_node is not None:
            return PreflightCheck(
                name="camera",
                status="pass",
                message=f"Camera: {cam_path}",
            )

        return PreflightCheck(
            name="camera",
            status="fail",
            message=f"Camera node not found: {cam_path}",
            detail="The camera path does not resolve to a valid node.",
        )
    except Exception as exc:
        return PreflightCheck(
            name="camera",
            status="fail",
            message=f"Camera check error: {exc}",
        )


def check_output_path(render_node: "hou.Node") -> PreflightCheck:
    """Is the output path set? Does the directory exist and is it writable?"""
    try:
        out_path = _parm_str(render_node, ["picture", "outputimage"])
        if not out_path:
            return PreflightCheck(
                name="output_path",
                status="fail",
                message="No output path set",
                detail="Set 'picture' or 'outputimage' on the render node.",
            )

        # Expand Houdini variables
        try:
            expanded = hou.text.expandString(out_path)
        except Exception:
            expanded = out_path

        out_dir = os.path.dirname(expanded)
        if not out_dir:
            return PreflightCheck(
                name="output_path",
                status="warn",
                message=f"Output path has no directory component: {out_path}",
                detail="File will be written to the current working directory.",
            )

        if not os.path.isdir(out_dir):
            def _make_dir(d: str = out_dir) -> None:
                os.makedirs(d, exist_ok=True)

            return PreflightCheck(
                name="output_path",
                status="warn",
                message=f"Output directory does not exist: {out_dir}",
                detail="Directory will be created if you apply the fix.",
                fix_available=True,
                fix_fn=_make_dir,
            )

        if not os.access(out_dir, os.W_OK):
            return PreflightCheck(
                name="output_path",
                status="fail",
                message=f"Output directory is not writable: {out_dir}",
            )

        return PreflightCheck(
            name="output_path",
            status="pass",
            message=f"Output: {out_path}",
            detail=f"Resolved: {expanded}" if expanded != out_path else "",
        )
    except Exception as exc:
        return PreflightCheck(
            name="output_path",
            status="fail",
            message=f"Output path check error: {exc}",
        )


def check_resolution(render_node: "hou.Node") -> PreflightCheck:
    """Is the resolution reasonable?"""
    try:
        res_x = _parm_int(render_node, "resolutionx")
        res_y = _parm_int(render_node, "resolutiony")

        # Some nodes use a single "res" parm (tuple)
        if res_x is None or res_y is None:
            res_parm = render_node.parmTuple("res")
            if res_parm is not None:
                vals = res_parm.eval()
                res_x, res_y = int(vals[0]), int(vals[1])

        if res_x is None or res_y is None:
            return PreflightCheck(
                name="resolution",
                status="warn",
                message="Could not determine resolution",
                detail="No 'resolutionx/y' or 'res' parameter found.",
            )

        if res_x < 100 or res_y < 100:
            return PreflightCheck(
                name="resolution",
                status="warn",
                message=f"Very low resolution: {res_x}x{res_y}",
                detail="Are you rendering a thumbnail on purpose?",
            )

        if res_x > 8192 or res_y > 8192:
            return PreflightCheck(
                name="resolution",
                status="warn",
                message=f"Very high resolution: {res_x}x{res_y}",
                detail="This will require significant memory and render time.",
            )

        return PreflightCheck(
            name="resolution",
            status="pass",
            message=f"Resolution: {res_x}x{res_y}",
        )
    except Exception as exc:
        return PreflightCheck(
            name="resolution",
            status="warn",
            message=f"Resolution check error: {exc}",
        )


def check_frame_range(render_node: "hou.Node") -> PreflightCheck:
    """Report the configured frame range and warn on mismatches."""
    try:
        f_start = _parm_int(render_node, "f1") or _parm_int(render_node, "framerangex")
        f_end = _parm_int(render_node, "f2") or _parm_int(render_node, "framerangey")

        # Playbar range
        try:
            pb_range = hou.playbar.frameRange()
            pb_start, pb_end = int(pb_range[0]), int(pb_range[1])
        except Exception:
            pb_start, pb_end = None, None

        if f_start is not None and f_end is not None:
            frame_count = f_end - f_start + 1
            msg = f"Frame range: {f_start}-{f_end} ({frame_count} frame{'s' if frame_count != 1 else ''})"

            if frame_count == 1 and pb_start is not None and pb_end is not None:
                if pb_end - pb_start > 1:
                    return PreflightCheck(
                        name="frame_range",
                        status="warn",
                        message=msg,
                        detail=(
                            f"Single frame render but playbar range is "
                            f"{pb_start}-{pb_end}. Intentional?"
                        ),
                    )

            return PreflightCheck(
                name="frame_range",
                status="pass",
                message=msg,
            )

        # Could not read range -- report playbar
        if pb_start is not None and pb_end is not None:
            return PreflightCheck(
                name="frame_range",
                status="pass",
                message=f"Frame range (playbar): {pb_start}-{pb_end}",
                detail="Render node does not specify its own range.",
            )

        return PreflightCheck(
            name="frame_range",
            status="pass",
            message="Frame range: could not determine (will use scene default)",
        )
    except Exception as exc:
        return PreflightCheck(
            name="frame_range",
            status="warn",
            message=f"Frame range check error: {exc}",
        )


def check_materials(render_node: "hou.Node") -> PreflightCheck:
    """Find geometry prims with no material binding (Solaris only)."""
    if not _PXR_AVAILABLE:
        return PreflightCheck(
            name="materials",
            status="warn",
            message="USD libraries not available -- skipping material check",
        )

    if not _is_lop_node(render_node):
        return PreflightCheck(
            name="materials",
            status="pass",
            message="Material check skipped (not a LOP render node)",
        )

    try:
        stage = render_node.stage()
        if not stage:
            return PreflightCheck(
                name="materials",
                status="warn",
                message="Could not access USD stage from render node",
            )

        unbound: list[str] = []
        checked = 0
        limit = 100

        for prim in stage.Traverse():
            if checked >= limit:
                break
            if not prim.IsA(UsdGeom.Mesh) and not prim.IsA(UsdGeom.BasisCurves):
                continue
            checked += 1
            binding_api = UsdShade.MaterialBindingAPI(prim)
            mat, _rel = binding_api.ComputeBoundMaterial()
            if not mat or not mat.GetPrim().IsValid():
                unbound.append(str(prim.GetPath()))

        if not unbound:
            return PreflightCheck(
                name="materials",
                status="pass",
                message=f"All geometry prims have materials ({checked} checked)",
            )

        detail_lines = unbound[:10]
        if len(unbound) > 10:
            detail_lines.append(f"... and {len(unbound) - 10} more")

        return PreflightCheck(
            name="materials",
            status="warn",
            message=f"{len(unbound)} geometry prim(s) missing material binding",
            detail="\n".join(detail_lines),
        )
    except Exception as exc:
        return PreflightCheck(
            name="materials",
            status="warn",
            message=f"Material check error: {exc}",
        )


def check_lights(render_node: "hou.Node") -> PreflightCheck:
    """Are there lights in the scene?"""
    try:
        # Solaris: look for UsdLux light prims on the stage
        if _is_lop_node(render_node) and _PXR_AVAILABLE:
            try:
                stage = render_node.stage()
                if stage:
                    light_count = 0
                    light_types: list[str] = []
                    for prim in stage.Traverse():
                        if prim.IsA(UsdLux.BoundableLightBase) or prim.IsA(UsdLux.NonboundableLightBase):
                            light_count += 1
                            light_types.append(prim.GetTypeName())
                            if light_count > 20:
                                break  # Enough to confirm presence

                    if light_count == 0:
                        return PreflightCheck(
                            name="lights",
                            status="fail",
                            message="No lights found in the USD stage",
                            detail="Add at least a key light and environment light.",
                        )

                    if light_count == 1:
                        return PreflightCheck(
                            name="lights",
                            status="warn",
                            message=f"Only 1 light found ({light_types[0]})",
                            detail="Consider adding fill/rim lights for better results.",
                        )

                    return PreflightCheck(
                        name="lights",
                        status="pass",
                        message=f"{light_count} light(s) in scene",
                        detail=", ".join(light_types[:10]),
                    )
            except Exception:
                pass  # Fall through to OBJ check

        # OBJ context: look for light objects
        obj_net = hou.node("/obj")
        if obj_net is not None:
            light_count = 0
            for child in obj_net.children():
                cat = child.type().category().name()
                type_name = child.type().name()
                if "light" in type_name.lower() or cat == "Light":
                    light_count += 1

            if light_count == 0:
                return PreflightCheck(
                    name="lights",
                    status="fail",
                    message="No lights found in /obj",
                )

            if light_count == 1:
                return PreflightCheck(
                    name="lights",
                    status="warn",
                    message="Only 1 light found in /obj",
                    detail="Consider adding fill/rim lights.",
                )

            return PreflightCheck(
                name="lights",
                status="pass",
                message=f"{light_count} light(s) in /obj",
            )

        return PreflightCheck(
            name="lights",
            status="warn",
            message="Could not check lights (no stage or /obj network)",
        )
    except Exception as exc:
        return PreflightCheck(
            name="lights",
            status="warn",
            message=f"Light check error: {exc}",
        )


def check_memory_estimate(render_node: "hou.Node") -> PreflightCheck:
    """Rough memory estimate based on geometry and textures."""
    try:
        total_points = 0
        texture_bytes = 0
        subd_multiplier = 1.0

        if _is_lop_node(render_node) and _PXR_AVAILABLE:
            try:
                stage = render_node.stage()
                if stage:
                    prim_count = 0
                    limit = 100
                    for prim in stage.Traverse():
                        if prim_count >= limit:
                            break
                        if prim.IsA(UsdGeom.Mesh):
                            prim_count += 1
                            pts_attr = prim.GetAttribute("points")
                            if pts_attr and pts_attr.HasValue():
                                pts = pts_attr.Get()
                                if pts is not None:
                                    total_points += len(pts)
                            # Check subdivision
                            subdiv_attr = prim.GetAttribute("subdivisionScheme")
                            if subdiv_attr and subdiv_attr.HasValue():
                                scheme = subdiv_attr.Get()
                                if scheme and scheme != "none":
                                    subd_multiplier = max(subd_multiplier, 4.0)

                    # Scan for texture file references (first 50)
                    tex_count = 0
                    tex_limit = 50
                    for prim in stage.Traverse():
                        if tex_count >= tex_limit:
                            break
                        if prim.IsA(UsdShade.Shader):
                            for attr in prim.GetAttributes():
                                val = attr.Get()
                                if isinstance(val, (str, Sdf.AssetPath)):
                                    path_str = str(val.path if isinstance(val, Sdf.AssetPath) else val)
                                    if path_str and any(
                                        path_str.lower().endswith(ext)
                                        for ext in (".exr", ".hdr", ".tx", ".png", ".jpg", ".tif", ".tiff")
                                    ):
                                        tex_count += 1
                                        try:
                                            expanded = hou.text.expandString(path_str)
                                            if os.path.isfile(expanded):
                                                texture_bytes += os.path.getsize(expanded)
                                        except Exception:
                                            pass
            except Exception:
                pass

        # Estimate: ~200 bytes per point (position + normals + UVs + overhead)
        # Subdivision multiplies by ~4x per level, we assume 1 level if detected
        geo_bytes = total_points * 200 * subd_multiplier
        est_bytes = geo_bytes + texture_bytes * 3  # textures expand ~3x in RAM
        est_gb = est_bytes / (1024**3)

        # System RAM
        if _PSUTIL_AVAILABLE:
            sys_ram_gb = psutil.virtual_memory().total / (1024**3)
        else:
            sys_ram_gb = 64.0

        if est_gb < 0.01 and total_points == 0:
            return PreflightCheck(
                name="memory_estimate",
                status="pass",
                message="Memory estimate: insufficient data to estimate",
                detail="Could not read geometry data from the stage.",
            )

        status = "pass"
        detail_parts = [
            f"{total_points:,} points",
            f"~{texture_bytes / (1024**2):.0f}MB textures on disk",
        ]
        if subd_multiplier > 1:
            detail_parts.append("subdivision detected")

        if est_gb > sys_ram_gb * 0.8:
            status = "warn"
            detail_parts.append(
                f"Exceeds 80% of system RAM ({sys_ram_gb:.0f}GB)"
            )

        return PreflightCheck(
            name="memory_estimate",
            status=status,
            message=f"Estimated ~{est_gb:.1f}GB memory usage",
            detail=", ".join(detail_parts),
        )
    except Exception as exc:
        return PreflightCheck(
            name="memory_estimate",
            status="warn",
            message=f"Memory estimate error: {exc}",
        )


def check_motion_blur(render_node: "hou.Node") -> PreflightCheck:
    """Check motion blur configuration vs scene animation."""
    try:
        # Check if motion blur is enabled on the render node
        mb_enabled = False
        mb_parm = render_node.parm("mblur") or render_node.parm("allowmotionblur")
        if mb_parm is not None:
            mb_enabled = bool(mb_parm.evalAsInt())

        # Check for animation in the scene (best-effort)
        has_animation = False
        try:
            pb_range = hou.playbar.frameRange()
            if pb_range[1] - pb_range[0] > 1:
                has_animation = True
        except Exception:
            pass

        # Check for xform animation on key prims
        has_xform_anim = False
        if _is_lop_node(render_node) and _PXR_AVAILABLE:
            try:
                stage = render_node.stage()
                if stage:
                    checked = 0
                    for prim in stage.Traverse():
                        if checked >= 20:
                            break
                        if prim.IsA(UsdGeom.Xformable):
                            xformable = UsdGeom.Xformable(prim)
                            if xformable.GetTimeSamples():
                                has_xform_anim = True
                                break
                            checked += 1
            except Exception:
                pass

        if mb_enabled:
            return PreflightCheck(
                name="motion_blur",
                status="pass",
                message="Motion blur: enabled",
                detail="Velocity attributes recommended on fast-moving geometry."
                if has_xform_anim
                else "",
            )

        if has_animation and has_xform_anim:
            return PreflightCheck(
                name="motion_blur",
                status="warn",
                message="Motion blur disabled but scene has animation",
                detail="Consider enabling motion blur for animated scenes.",
            )

        return PreflightCheck(
            name="motion_blur",
            status="pass",
            message="Motion blur: disabled" + (" (no animation detected)" if not has_animation else ""),
        )
    except Exception as exc:
        return PreflightCheck(
            name="motion_blur",
            status="warn",
            message=f"Motion blur check error: {exc}",
        )


def check_render_engine(render_node: "hou.Node") -> PreflightCheck:
    """Report which render engine is configured."""
    try:
        # Karma render engine: check "renderer" or "renderengine" parm
        engine_str = _parm_str(render_node, ["renderer", "renderengine"])
        if engine_str is None:
            # Infer from node type
            type_name = render_node.type().name()
            if "karma" in type_name.lower():
                engine_str = "karma (type inferred)"
            elif "ifd" in type_name.lower():
                engine_str = "mantra"
            elif "ris" in type_name.lower():
                engine_str = "RenderMan"

        if engine_str is None:
            return PreflightCheck(
                name="render_engine",
                status="pass",
                message="Render engine: could not determine",
            )

        engine_lower = engine_str.lower()
        is_cpu = "cpu" in engine_lower or engine_lower == "karma"

        if is_cpu:
            return PreflightCheck(
                name="render_engine",
                status="warn",
                message=f"Render engine: {engine_str} (CPU)",
                detail="XPU may offer faster renders if your scene is compatible.",
            )

        return PreflightCheck(
            name="render_engine",
            status="pass",
            message=f"Render engine: {engine_str}",
        )
    except Exception as exc:
        return PreflightCheck(
            name="render_engine",
            status="pass",
            message=f"Render engine check error: {exc}",
        )


# =====================================================================
# Main entry point
# =====================================================================


def run_preflight(render_node: str = "") -> PreflightReport:
    """Run all preflight checks against *render_node*.

    Parameters
    ----------
    render_node:
        Houdini node path (e.g. ``/stage/karmarendersettings1``).
        If empty, auto-detect the best candidate.

    Returns
    -------
    PreflightReport
        Aggregate report with all check results.
    """
    report = PreflightReport()

    if not _HOU_AVAILABLE:
        report.checks.append(
            PreflightCheck(
                name="houdini",
                status="fail",
                message="Houdini is not available (hou module not loaded)",
            )
        )
        report._build_summary()
        return report

    # Resolve render node
    node: Optional["hou.Node"] = None
    if render_node:
        node = hou.node(render_node)
        if node is None:
            report.checks.append(
                PreflightCheck(
                    name="render_node",
                    status="fail",
                    message=f"Render node not found: {render_node}",
                )
            )
            report._build_summary()
            return report
    else:
        node = _detect_render_node()
        if node is None:
            report.checks.append(
                PreflightCheck(
                    name="render_node",
                    status="fail",
                    message="No render node found",
                    detail="Create a Karma LOP in /stage or a ROP in /out.",
                )
            )
            report._build_summary()
            return report

    report.render_node = node.path()

    # Run all checks -- each is isolated
    check_fns = [
        check_camera,
        check_output_path,
        check_resolution,
        check_frame_range,
        check_materials,
        check_lights,
        check_memory_estimate,
        check_motion_blur,
        check_render_engine,
    ]

    for fn in check_fns:
        try:
            result = fn(node)
            report.checks.append(result)
        except Exception as exc:
            report.checks.append(
                PreflightCheck(
                    name=fn.__name__.replace("check_", ""),
                    status="warn",
                    message=f"Check failed unexpectedly: {exc}",
                )
            )

    report._build_summary()
    return report


# =====================================================================
# HTML formatter
# =====================================================================


_STATUS_ICONS = {
    "pass": ("&#10004;", "#4CAF50"),  # checkmark, green
    "fail": ("&#10008;", "#F44336"),  # cross, red
    "warn": ("&#9888;", "#FF9800"),   # warning triangle, orange
}


def format_preflight_html(report: PreflightReport) -> str:
    """Format a :class:`PreflightReport` as HTML for a QTextEdit widget.

    Groups checks by status: failures first, then warnings, then passes.
    """
    lines: list[str] = []
    lines.append("<div style='font-family: monospace; font-size: 13px;'>")

    # Header
    if report.render_node:
        lines.append(
            f"<p style='color: #AAA; margin: 4px 0;'>"
            f"Render node: <b>{report.render_node}</b></p>"
        )

    # Status banner
    if report.ready:
        lines.append(
            "<p style='color: #4CAF50; font-size: 16px; font-weight: bold; "
            "margin: 8px 0;'>&#10004; Ready to render</p>"
        )
    else:
        n_fail = sum(1 for c in report.checks if c.status == "fail")
        lines.append(
            f"<p style='color: #F44336; font-size: 16px; font-weight: bold; "
            f"margin: 8px 0;'>&#10008; {n_fail} issue{'s' if n_fail != 1 else ''} "
            f"to fix before rendering</p>"
        )

    lines.append(f"<p style='color: #888; margin: 2px 0;'>{report.summary}</p>")
    lines.append("<hr style='border-color: #555;'>")

    # Group by status
    ordered = sorted(report.checks, key=lambda c: {"fail": 0, "warn": 1, "pass": 2}.get(c.status, 3))

    for check in ordered:
        icon, color = _STATUS_ICONS.get(check.status, ("?", "#888"))
        lines.append(
            f"<p style='margin: 6px 0 2px 0;'>"
            f"<span style='color: {color}; font-size: 15px;'>{icon}</span> "
            f"<b>{check.name}</b>: {check.message}</p>"
        )
        if check.detail:
            # Escape HTML in detail and preserve newlines
            detail_escaped = (
                check.detail.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            lines.append(
                f"<p style='color: #999; margin: 0 0 4px 24px; font-size: 12px;'>"
                f"{detail_escaped}</p>"
            )
        if check.fix_available:
            lines.append(
                f"<p style='color: #00D4FF; margin: 0 0 4px 24px; font-size: 12px;'>"
                f"[Auto-fix available]</p>"
            )

    lines.append("</div>")
    return "\n".join(lines)
