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

from shared.constants import (
    RENDER_VALIDATE_CHECKS as _VALIDATE_CHECKS,
    RENDER_VALIDATE_DEFAULTS as _VALIDATE_DEFAULTS,
)
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
            if vp is None:
                raise ValueError(
                    "The viewport is in an invalid state (minimized, hidden, "
                    "or GPU context lost) -- make sure the Scene Viewer pane "
                    "is visible and active"
                )
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
        must run on Houdini's main thread. Writes render output to disk (EXR or
        artist-configured format) AND generates a JPEG preview for AI consumption.

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
            lop_target_node = None
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
                        lop_target_node = target
                        break
            elif lp:
                lop_target_path = lp.eval()  # noqa: S307
                if lop_target_path:
                    lop_target_node = hou.node(lop_target_path)

            # Preserve artist's configured output path for EXR persistence
            temp_dir = Path(hou.text.expandString("$HOUDINI_TEMP_DIR"))
            timestamp = int(time.time() * 1000)
            preview_path = str(temp_dir / f"synapse_render_{timestamp}.jpg")

            # Read the artist's original output path — check ROP first, then
            # walk upstream to find Karma LOP's picture parm (BL-007 fix)
            artist_output = ""
            output_parm = None
            for parm_name in ("outputimage", "picture"):
                p = node.parm(parm_name)
                if p:
                    artist_output = p.eval() or ""  # noqa: S307
                    output_parm = p
                    if artist_output.strip():
                        break

            # If ROP has no output path, check the upstream Karma LOP
            if not artist_output.strip() and lop_target_node is not None:
                try:
                    # Walk from the LOP target up to find a karma node with picture
                    _walk = lop_target_node
                    for _ in range(20):  # bounded walk
                        kp = _walk.parm("picture")
                        if kp:
                            _val = kp.eval() or ""  # noqa: S307
                            if _val.strip():
                                artist_output = _val
                                break
                        # Try parent's children (sibling karma nodes)
                        inputs = _walk.inputs()
                        if inputs:
                            _walk = inputs[0]
                        else:
                            break
                except Exception:
                    pass  # best-effort upstream discovery

            # Determine render output: use artist path if set, else default EXR
            if artist_output and artist_output.strip():
                render_path = artist_output
            else:
                # Default to EXR in $HIP/.synapse/renders/ so renders persist
                try:
                    hip = hou.text.expandString("$HIP")
                    if hip and hip != "$HIP":
                        render_dir = Path(hip) / ".synapse" / "renders"
                    else:
                        render_dir = temp_dir / "synapse_renders"
                except Exception:
                    render_dir = temp_dir / "synapse_renders"
                render_path = str(render_dir / f"render_{timestamp}.$F4.exr")

            # Pre-render validation: ensure output directory exists
            render_dir_path = Path(render_path).parent
            # Expand $F4 frame tokens for directory check
            dir_str = str(render_dir_path)
            if "$" not in dir_str:
                try:
                    render_dir_path.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    raise RuntimeError(
                        f"Couldn't create output directory {render_dir_path} -- {e}. "
                        "Check the path is writable or set a different output path "
                        "on the render node's 'picture' or 'outputimage' parameter."
                    ) from e

            cur = int(hou.frame()) if frame is None else int(frame)

            # Resolve $F4 frame token in render path for file polling
            render_path_resolved = render_path.replace("$F4", f"{cur:04d}")

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

            # Set output path on the ROP parm (output_file kwarg doesn't
            # work reliably for usdrender/karma ROPs)
            if output_parm:
                output_parm.set(render_path)
            elif node.parm("outputimage"):
                node.parm("outputimage").set(render_path)
            elif node.parm("picture"):
                node.parm("picture").set(render_path)

            node.render(
                frame_range=(cur, cur),
                verbose=False,
            )

            # Karma XPU has a delayed file flush -- poll up to ~15s
            used_flipbook = False
            render_ok = False
            out_path = render_path_resolved
            for _ in range(60):
                if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
                    render_ok = True
                    break
                time.sleep(0.25)

            # If render wrote to artist's EXR/non-JPEG, convert to JPEG for preview
            artist_file_written = False
            if render_ok and out_path != preview_path:
                artist_file_written = True
                # Try to convert to JPEG preview using iconvert or PIL
                try:
                    hfs = hou.text.expandString("$HFS")
                    iconvert = Path(hfs) / "bin" / "iconvert.exe"
                    if not iconvert.exists():
                        iconvert = Path(hfs) / "bin" / "iconvert"
                    if iconvert.exists():
                        import subprocess
                        subprocess.run(
                            [str(iconvert), out_path, preview_path],
                            timeout=15,
                            capture_output=True,
                        )
                except Exception:
                    pass  # Preview conversion is best-effort
                # If iconvert worked, use preview; otherwise serve the render file
                if Path(preview_path).exists() and Path(preview_path).stat().st_size > 0:
                    out_path = preview_path
                # else: out_path stays as the artist's render file

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
            return out_path, node.path(), node_type, engine, used_flipbook, artist_file_written, render_path_resolved

        import hdefereval
        result_path, used_rop, used_type, engine, used_flipbook, artist_file_written, render_file = (
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
        # Always report the disk-written file path (EXR or artist format)
        if artist_file_written or render_file != result_path:
            result["output_file"] = render_file
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
        advanced_karma = resolve_param_with_default(payload, "advanced_karma", None)

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

            # Apply Karma advanced settings if provided in payload
            if isinstance(advanced_karma, dict) and advanced_karma:
                applied = RenderHandlerMixin._apply_karma_advanced_settings(
                    node, advanced_karma
                )
                if applied:
                    settings["_karma_advanced_applied"] = applied

            # Detect render engine variant for context
            node_type = node.type().name()
            engine = _detect_karma_engine(node, node_type)

            return {
                "node": node_path,
                "render_engine": engine,
                "settings": settings,
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

    def _handle_configure_render_passes(self, payload: Dict) -> Dict:
        """Configure render passes (AOVs) for Karma via Python LOP.

        Creates USD RenderVar prims for each requested pass. Supported presets:
        - beauty: RGBA combined output
        - diffuse: direct_diffuse + indirect_diffuse
        - specular: direct_specular + indirect_specular
        - emission: direct_emission
        - normal: world-space normals (N)
        - depth: camera depth (Z)
        - position: world-space position (P)
        - crypto_material: Cryptomatte by material
        - crypto_object: Cryptomatte by object
        - motion: 2D motion vectors
        - sss: subsurface scattering
        - albedo: surface albedo

        Can also accept custom pass names with explicit source_name and data_type.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        from ..core.aliases import resolve_param, resolve_param_with_default

        node_path_arg = resolve_param(payload, "node", required=False)
        passes = resolve_param(payload, "passes")
        clear_existing = resolve_param_with_default(payload, "clear_existing", False)

        # Preset definitions: name -> (source_name, data_type, source_type)
        _PRESETS = {
            "beauty":          ("C",                "color4f", "raw"),
            "direct_diffuse":  ("direct_diffuse",   "color3f", "raw"),
            "indirect_diffuse":("indirect_diffuse",  "color3f", "raw"),
            "diffuse":         ("direct_diffuse",    "color3f", "raw"),  # alias
            "direct_specular": ("direct_specular",   "color3f", "raw"),
            "indirect_specular":("indirect_specular", "color3f", "raw"),
            "specular":        ("direct_specular",   "color3f", "raw"),  # alias
            "emission":        ("direct_emission",   "color3f", "raw"),
            "sss":             ("sss",               "color3f", "raw"),
            "normal":          ("N",                 "normal3f","raw"),
            "depth":           ("Z",                 "float",   "raw"),
            "position":        ("P",                 "point3f", "raw"),
            "albedo":          ("albedo",            "color3f", "raw"),
            "motion":          ("motionvector",      "float2",  "raw"),
            "crypto_material": ("crypto_material",   "color4f", "raw"),
            "crypto_object":   ("crypto_object",     "color4f", "raw"),
            "crypto_asset":    ("crypto_asset",      "color4f", "raw"),
        }

        from .main_thread import run_on_main, _SLOW_TIMEOUT

        def _on_main():
            node = self._resolve_lop_node(node_path_arg)  # type: ignore[attr-defined]
            parent = node.parent()

            # Build the Python code to create RenderVar prims
            lines = [
                "import hou",
                "from pxr import UsdRender, Sdf, Gf",
                "",
                "node = hou.pwd()",
                "stage = node.editableStage()",
                "",
            ]

            if clear_existing:
                lines.append("# Clear existing render vars")
                lines.append("render_settings = stage.GetPrimAtPath('/Render/rendersettings')")
                lines.append("if render_settings and render_settings.IsValid():")
                lines.append("    for child in render_settings.GetChildren():")
                lines.append("        if child.GetTypeName() == 'RenderVar':")
                lines.append("            stage.RemovePrim(child.GetPath())")
                lines.append("")

            created_passes = []

            if isinstance(passes, list):
                pass_list = passes
            elif isinstance(passes, str):
                # Comma-separated string
                pass_list = [p.strip() for p in passes.split(",")]
            else:
                raise ValueError(
                    "passes should be a list of pass names or a comma-separated string "
                    f"(e.g. ['beauty', 'diffuse', 'normal'] or 'beauty,diffuse,normal')"
                )

            for pass_spec in pass_list:
                if isinstance(pass_spec, dict):
                    # Custom pass with explicit params
                    pass_name = pass_spec.get("name", "custom")
                    source_name = pass_spec.get("source_name", pass_name)
                    data_type = pass_spec.get("data_type", "color3f")
                    source_type = pass_spec.get("source_type", "raw")
                elif isinstance(pass_spec, str):
                    pass_name = pass_spec.lower().strip()
                    if pass_name in _PRESETS:
                        source_name, data_type, source_type = _PRESETS[pass_name]
                    else:
                        # Treat as custom pass name
                        source_name = pass_name
                        data_type = "color3f"
                        source_type = "raw"
                else:
                    continue

                safe_name = pass_name.replace("/", "_").replace(" ", "_")
                prim_path = f"/Render/rendersettings/{safe_name}"

                lines.append(f"# Render var: {pass_name}")
                lines.append(f"rv = UsdRender.Var.Define(stage, '{prim_path}')")
                lines.append(f"rv.GetSourceNameAttr().Set('{source_name}')")
                lines.append(f"rv.GetDataTypeAttr().Set('{data_type}')")
                lines.append(f"rv.GetSourceTypeAttr().Set('{source_type}')")
                lines.append("")

                created_passes.append({
                    "name": pass_name,
                    "prim_path": prim_path,
                    "source_name": source_name,
                    "data_type": data_type,
                })

            code = "\n".join(lines)

            # Create Python LOP then set code and force-cook inside undo
            # group so the pxr imports are validated before the undo exits.
            # Without the cook, Houdini defers validation to undo
            # serialization time, which can corrupt the undo stack if the
            # pythonscript code has import errors.
            try:
                with hou.undos.group("SYNAPSE: configure_render_passes"):
                    py_lop = parent.createNode("pythonscript", "render_passes")
                    py_lop.setInput(0, node)
                    py_lop.moveToGoodPosition()
                    py_lop.parm("python").set(code)
                    # Force cook validates the python code NOW, not at undo
                    # serialization time — catches pxr import errors early.
                    py_lop.cook(force=True)
            except Exception:
                try:
                    hou.undos.performUndo()
                except Exception:
                    pass
                raise

            return {
                "node": py_lop.path(),
                "passes": created_passes,
                "pass_count": len(created_passes),
                "clear_existing": bool(clear_existing),
            }

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT)

    # =========================================================================
    # SAFE RENDER (pre-flight + auto-background for large renders)
    # =========================================================================

    def _handle_safe_render(self, payload: Dict) -> Dict:
        """Render with automatic pre-flight validation and safety guards.

        Runs lightweight pre-flight checks (camera, materials, output path)
        before rendering. If resolution exceeds 512 on either axis and the
        caller hasn't explicitly set soho_foreground, forces background
        rendering to prevent Houdini lockup.

        Payload:
            rop_path (str, optional): Path to the render ROP node.
            soho_foreground (int, optional): 0=background, 1=foreground.
                If omitted and resolution > 512, defaults to 0 (background).
            width (int, optional): Resolution width override.
            height (int, optional): Resolution height override.
            Any additional keys are passed through to the render handler.

        Returns:
            dict with 'preflight' summary and 'render' result (or diagnostic
            if pre-flight failed).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        rop_path = resolve_param_with_default(payload, "rop_path", None)
        user_foreground = payload.get("soho_foreground", None)
        width = resolve_param_with_default(payload, "width", None)
        height = resolve_param_with_default(payload, "height", None)

        # ----- Pre-flight checks (synchronous, lightweight) -----
        checks = []

        # Check 1: Camera exists on the stage
        try:
            stage_info = self._handle_get_stage_info({})
            cameras = stage_info.get("cameras", [])
            if not cameras:
                checks.append({
                    "name": "camera",
                    "passed": False,
                    "severity": "hard_fail",
                    "message": (
                        "Couldn't find a render camera on the stage -- "
                        "add a Camera LOP before rendering"
                    ),
                })
            else:
                checks.append({
                    "name": "camera",
                    "passed": True,
                    "severity": "hard_fail",
                    "message": f"Found {len(cameras)} camera(s)",
                })
        except Exception as exc:
            checks.append({
                "name": "camera",
                "passed": False,
                "severity": "hard_fail",
                "message": f"Couldn't query stage for cameras: {exc}",
            })

        # Check 2: Materials bound (soft warning only)
        try:
            unassigned = stage_info.get("unassigned_material_prims", [])
            if unassigned:
                paths = ", ".join(str(p) for p in unassigned[:5])
                suffix = f" (and {len(unassigned) - 5} more)" if len(unassigned) > 5 else ""
                checks.append({
                    "name": "materials",
                    "passed": False,
                    "severity": "soft_warn",
                    "message": (
                        f"Found {len(unassigned)} prim(s) without materials: "
                        f"{paths}{suffix}. They'll render with the default grey shader."
                    ),
                })
            else:
                checks.append({
                    "name": "materials",
                    "passed": True,
                    "severity": "soft_warn",
                    "message": "All geometry prims have materials assigned.",
                })
        except Exception:
            # stage_info may not have this field -- soft warning
            checks.append({
                "name": "materials",
                "passed": True,
                "severity": "soft_warn",
                "message": "Couldn't verify material assignments (non-blocking).",
            })

        # Check 3: Output path is valid
        if rop_path:
            try:
                settings = self._handle_render_settings({"node": rop_path})
                current_settings = settings.get("settings", {})
                output = current_settings.get("outputimage", "") or current_settings.get("picture", "")
                if output:
                    output_dir = os.path.dirname(output)
                    # Expand Houdini variables for directory check
                    if "$" not in output_dir and output_dir:
                        if not os.path.isdir(output_dir):
                            checks.append({
                                "name": "output_path",
                                "passed": False,
                                "severity": "soft_warn",
                                "message": (
                                    f"Output directory doesn't exist: {output_dir} -- "
                                    "we'll try to create it during render"
                                ),
                            })
                        else:
                            checks.append({
                                "name": "output_path",
                                "passed": True,
                                "severity": "soft_warn",
                                "message": f"Output path configured: {output}",
                            })
                    else:
                        checks.append({
                            "name": "output_path",
                            "passed": True,
                            "severity": "soft_warn",
                            "message": f"Output path configured (contains variables): {output}",
                        })
                else:
                    checks.append({
                        "name": "output_path",
                        "passed": False,
                        "severity": "soft_warn",
                        "message": (
                            "Couldn't find an output path configured -- "
                            "the render handler will assign a default path"
                        ),
                    })
            except Exception as exc:
                checks.append({
                    "name": "output_path",
                    "passed": False,
                    "severity": "soft_warn",
                    "message": f"Couldn't verify output path: {exc}",
                })

        # ----- Evaluate pre-flight result -----
        hard_failures = [c for c in checks if not c["passed"] and c["severity"] == "hard_fail"]
        all_passed = len(hard_failures) == 0

        if not all_passed:
            suggestions = []
            for fail in hard_failures:
                suggestions.append(fail["message"])
            return {
                "passed": False,
                "checks": sorted(checks, key=lambda c: c["name"]),
                "suggestion": "; ".join(suggestions),
            }

        # ----- Safety: force background render for large resolutions -----
        render_payload = dict(payload)
        # Remove safe_render-specific keys before passing to _handle_render
        render_payload.pop("rop_path", None)
        render_payload.pop("soho_foreground", None)
        if rop_path:
            render_payload["node"] = rop_path

        effective_w = int(width) if width else 0
        effective_h = int(height) if height else 0
        forced_background = False

        if (effective_w > 512 or effective_h > 512) and user_foreground is None:
            # Force background render to prevent Houdini lockup
            forced_background = True
            logger.info(
                "safe_render: resolution %dx%d exceeds 512 -- "
                "forcing background render (soho_foreground=0)",
                effective_w, effective_h,
            )
            # Set soho_foreground=0 on the ROP node before rendering
            if rop_path:
                try:
                    self._handle_render_settings({
                        "node": rop_path,
                        "settings": {"soho_foreground": 0},
                    })
                except Exception:
                    pass  # Best effort -- render handler handles this too
        elif user_foreground is not None:
            # Respect explicit user setting
            if rop_path:
                try:
                    self._handle_render_settings({
                        "node": rop_path,
                        "settings": {"soho_foreground": int(user_foreground)},
                    })
                except Exception:
                    pass

        # ----- Delegate to existing render handler -----
        render_result = self._handle_render(render_payload)

        # ----- Build enriched response -----
        return {
            "passed": True,
            "checks": sorted(checks, key=lambda c: c["name"]),
            "render": render_result,
            "forced_background": forced_background,
        }

    # =========================================================================
    # PROGRESSIVE RENDER (test -> preview -> production)
    # =========================================================================

    def _handle_render_progressively(self, payload: Dict) -> Dict:
        """Render in 3 progressive passes with validation between each.

        Implements a test-preview-production pipeline that catches issues
        early at low cost before committing to expensive production renders.

        Pass 1 (test):       256x256, 4 samples, soho_foreground=1 (fast, blocks)
        Pass 2 (preview):    1280x720, 16 samples, soho_foreground=0 (background)
        Pass 3 (production): user resolution & samples, soho_foreground=0

        After each pass, validates the rendered frame for black frames, NaN,
        clipping, and underexposure. Stops on first validation failure.

        Payload:
            rop_path (str, optional): Path to the render ROP node.
            resolution (list[int,int], optional): Production resolution [w, h].
                Defaults to [1920, 1080].
            samples (int, optional): Production pixel samples. Defaults to 64.

        Returns:
            dict with 'passes' list and 'final_image' path (or None if failed).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        rop_path = resolve_param_with_default(payload, "rop_path", None)
        prod_resolution = resolve_param_with_default(payload, "resolution", [1920, 1080])
        prod_samples = int(resolve_param_with_default(payload, "samples", 64))

        if isinstance(prod_resolution, list) and len(prod_resolution) == 2:
            prod_w, prod_h = int(prod_resolution[0]), int(prod_resolution[1])
        else:
            prod_w, prod_h = 1920, 1080

        # Define the 3 passes
        pass_configs = [
            {
                "name": "test",
                "width": 256,
                "height": 256,
                "samples": 4,
                "soho_foreground": 1,
            },
            {
                "name": "preview",
                "width": 1280,
                "height": 720,
                "samples": 16,
                "soho_foreground": 0,
            },
            {
                "name": "production",
                "width": prod_w,
                "height": prod_h,
                "samples": prod_samples,
                "soho_foreground": 0,
            },
        ]

        passes = []
        final_image = None

        for config in pass_configs:
            pass_name = config["name"]
            w, h = config["width"], config["height"]
            samples = config["samples"]
            foreground = config["soho_foreground"]

            # Apply render settings (samples + foreground mode) on the ROP
            if rop_path:
                settings_overrides = {"soho_foreground": foreground}
                # Try common sample parm names
                for sample_parm in ("pathtracedsamples", "pixelsamples", "vm_samplesx"):
                    settings_overrides[sample_parm] = samples
                try:
                    self._handle_render_settings({
                        "node": rop_path,
                        "settings": settings_overrides,
                    })
                except Exception:
                    pass  # Best effort -- some parms may not exist

            # Build render payload
            render_payload = {
                "width": w,
                "height": h,
            }
            if rop_path:
                render_payload["node"] = rop_path

            # Execute the render
            pass_result = {
                "name": pass_name,
                "resolution": f"{w}x{h}",
                "samples": samples,
                "quality": pass_name,
                "status": "pending",
                "validation": None,
            }

            try:
                render_result = self._handle_render(render_payload)
                image_path = render_result.get("image_path") or render_result.get("output_file")

                if not image_path:
                    pass_result["status"] = "failed"
                    pass_result["validation"] = {
                        "valid": False,
                        "summary": "Render produced no output image",
                    }
                    passes.append(pass_result)
                    break

                # Validate the rendered frame
                try:
                    validation = self._handle_validate_frame({
                        "image_path": image_path,
                    })
                    pass_result["validation"] = validation

                    if validation.get("valid", False):
                        pass_result["status"] = "passed"
                        final_image = image_path
                    else:
                        pass_result["status"] = "failed"
                        passes.append(pass_result)
                        logger.warning(
                            "render_progressively: %s pass failed validation -- %s",
                            pass_name, validation.get("summary", "unknown issue"),
                        )
                        break
                except Exception as val_exc:
                    # Validation itself failed (e.g. OIIO unavailable)
                    # Treat as passed with warning -- don't block render pipeline
                    pass_result["status"] = "passed"
                    pass_result["validation"] = {
                        "valid": True,
                        "summary": f"Couldn't run full validation: {val_exc}",
                        "oiio_available": False,
                    }
                    final_image = image_path

            except Exception as render_exc:
                pass_result["status"] = "failed"
                pass_result["validation"] = {
                    "valid": False,
                    "summary": f"Render failed: {render_exc}",
                }
                passes.append(pass_result)
                break

            passes.append(pass_result)

        return {
            "passes": passes,
            "final_image": final_image,
            "completed_passes": len(passes),
            "total_passes": len(pass_configs),
            "success": final_image is not None and len(passes) == len(pass_configs),
        }

    # =========================================================================
    # KARMA ADVANCED SETTINGS
    # =========================================================================

    @staticmethod
    def _apply_karma_advanced_settings(rop_node, settings: dict) -> dict:
        """Apply advanced Karma-specific render settings to a ROP node.

        Accepts and applies the following settings (all optional -- pass None
        or omit to leave unchanged):

            path_samples (int): Number of path-traced samples per path vertex.
            pixel_samples (int): Alias for samplesPerPixel (primary ray samples).
            roughness_clamp (float): Clamp roughness to suppress fireflies (0.0-1.0).
            enable_caustics (bool): Enable/disable caustic light paths.
            volume_samples (int): Sample count for volumetric scattering.
            sample_distribution (str): "uniform" or "stratified" distribution.
            max_ray_depth (int): Maximum total ray depth.
            diffuse_limit (int): Max diffuse GI bounce depth.
            specular_limit (int): Max specular (reflection) bounce depth.
            sss_limit (int): Max subsurface scattering depth.
            color_limit (float): Clamp per-sample color contribution (firefly reduction).
            indirect_clamp (float): Clamp indirect light contributions specifically.
            enable_denoiser (bool): Enable OIDN/OptiX denoiser.
            adaptive_threshold (float): Noise threshold for adaptive sampling (0=disabled).
            min_samples (int): Minimum samples per pixel for adaptive sampling.
            bucket_size (int): Tile size in pixels (GPU memory vs speed tradeoff for XPU).
            motion_blur (bool): Enable/disable motion blur.

        Each setting checks if the parameter exists on the node before applying.
        Missing parameters are silently skipped (not all Karma versions have all
        params). Returns a dict of actually-applied settings.

        This function must be called on the main thread (inside a run_on_main
        closure or hdefereval context).
        """
        # Map of setting name -> list of candidate Karma ROP parm names
        _KARMA_PARM_MAP = {
            "path_samples": ["pathtracedsamples"],
            "pixel_samples": ["samplesperpixel"],
            "roughness_clamp": ["roughnessclamp", "karma:global:roughnessclamp"],
            "enable_caustics": ["enablecaustics", "karma:global:enablecaustics"],
            "volume_samples": ["volumesamples", "karma:global:volumesamples"],
            "sample_distribution": ["sampledistribution"],
            "max_ray_depth": ["maxraydepth", "karma:global:maxraydepth"],
            # Bounce depth limits
            "diffuse_limit": ["diffuselimit", "karma:global:diffuselimit"],
            "specular_limit": ["specularlimit", "karma:global:specularlimit"],
            "sss_limit": ["ssslimit", "karma:global:ssslimit"],
            # Clamping
            "color_limit": ["colorlimit", "karma:global:colorlimit"],
            "indirect_clamp": ["indirectclamp", "karma:global:indirectclamp"],
            # Denoiser
            "enable_denoiser": ["denoise_enable", "karma:global:denoiseenable",
                                "enabledenoiser"],
            # Adaptive sampling
            "adaptive_threshold": ["adaptivethreshold",
                                   "karma:global:adaptivethreshold"],
            "min_samples": ["minsamples", "karma:global:minsamples"],
            # XPU bucket size
            "bucket_size": ["bucketsize"],
            # Motion blur
            "motion_blur": ["enablemotionblur", "domotionblur"],
        }

        # Settings that accept bool values (toggled as 0/1 on the parm)
        _BOOL_SETTINGS = frozenset({
            "enable_caustics", "enable_denoiser", "motion_blur",
        })
        # Settings that accept float values with clamp ranges
        _FLOAT_CLAMP_SETTINGS = {
            "roughness_clamp": (0.0, 1.0),
            "color_limit": (0.0, None),
            "indirect_clamp": (0.0, None),
            "adaptive_threshold": (0.0, 1.0),
        }
        # Settings that accept int values
        _INT_SETTINGS = frozenset({
            "path_samples", "pixel_samples", "volume_samples", "max_ray_depth",
            "diffuse_limit", "specular_limit", "sss_limit", "min_samples",
            "bucket_size",
        })

        applied = {}

        for setting_name, parm_candidates in _KARMA_PARM_MAP.items():
            value = settings.get(setting_name)
            if value is None:
                continue

            # Type coercion and validation
            if setting_name in _BOOL_SETTINGS:
                value = bool(value)
            elif setting_name in _FLOAT_CLAMP_SETTINGS:
                lo, hi = _FLOAT_CLAMP_SETTINGS[setting_name]
                value = float(value)
                if lo is not None:
                    value = max(lo, value)
                if hi is not None:
                    value = min(hi, value)
            elif setting_name == "sample_distribution":
                value = str(value).lower()
                if value not in ("uniform", "stratified"):
                    continue  # Invalid value -- skip silently
            elif setting_name in _INT_SETTINGS:
                value = int(value)

            # Try each candidate parm name until one is found and set
            for parm_name in parm_candidates:
                try:
                    parm = rop_node.parm(parm_name)
                    if parm is not None:
                        if isinstance(value, bool):
                            parm.set(1 if value else 0)
                        else:
                            parm.set(value)
                        applied[setting_name] = value
                        break  # Applied successfully -- move to next setting
                except Exception:
                    pass  # Parm exists but set failed -- try next candidate

        return applied

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
