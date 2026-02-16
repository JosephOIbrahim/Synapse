"""
Synapse Render Handler Mixin

Extracted from handlers.py -- contains viewport capture, render, keyframe,
render settings, frame validation, and render farm handlers for the
SynapseHandler class.
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

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.determinism import round_float, kahan_sum
from .handler_helpers import _suggest_parms, _HOUDINI_UNAVAILABLE


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
    frame validation, and render farm handlers."""

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
