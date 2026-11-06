"""
Synapse Autonomy Pipeline — Render Evaluator

Per-frame and sequence-level quality checks on rendered output.
Detects black frames, NaN/Inf values, fireflies, clipping,
flickering, motion discontinuities, and missing frames.

numpy is optional — gracefully degrades if unavailable.
Image loading uses OIIO > pyexr > PIL with graceful fallback.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Union

from .models import FrameEvaluation, SequenceEvaluation

logger = logging.getLogger("synapse.autonomy.evaluator")

# Optional numpy import
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False

# Optional image library imports — tried in order of preference
_OIIO_AVAILABLE = False
_PYEXR_AVAILABLE = False
_PIL_AVAILABLE = False

try:
    import OpenImageIO as oiio  # type: ignore[import-untyped]
    _OIIO_AVAILABLE = True
except ImportError:
    oiio = None  # type: ignore[assignment]

if not _OIIO_AVAILABLE:
    try:
        import pyexr  # type: ignore[import-untyped]
        _PYEXR_AVAILABLE = True
    except ImportError:
        pyexr = None  # type: ignore[assignment]

try:
    from PIL import Image as _PILImage  # type: ignore[import-untyped]
    _PIL_AVAILABLE = True
except ImportError:
    _PILImage = None  # type: ignore[assignment]


class RenderEvaluator:
    """Evaluates rendered frames and sequences for quality issues.

    Per-frame checks:
        - Black frame detection (>95% near-black pixels)
        - NaN/Inf detection
        - Firefly detection (outlier pixels >10 std devs from mean)
        - Clipping detection (>5% pure white or pure black)

    Sequence checks:
        - Flickering (high-frequency luminance changes)
        - Motion continuity (large frame-to-frame jumps)
        - Missing frames (gaps in frame numbers)

    Args:
        black_threshold: Pixel intensity below this is considered near-black.
        black_ratio: Fraction of near-black pixels to flag as black frame.
        firefly_std_devs: Outlier threshold in standard deviations.
        clipping_ratio: Fraction of clipped pixels to flag.
        flicker_threshold: Luminance delta threshold for flickering.
        continuity_threshold: Frame-to-frame difference threshold.
        pass_threshold: Minimum overall score for a sequence to pass.
    """

    def __init__(
        self,
        black_threshold: float = 0.001,
        black_ratio: float = 0.95,
        firefly_std_devs: float = 10.0,
        clipping_ratio: float = 0.05,
        flicker_threshold: float = 0.15,
        continuity_threshold: float = 0.5,
        pass_threshold: float = 0.7,
    ) -> None:
        self._black_threshold = black_threshold
        self._black_ratio = black_ratio
        self._firefly_std_devs = firefly_std_devs
        self._clipping_ratio = clipping_ratio
        self._flicker_threshold = flicker_threshold
        self._continuity_threshold = continuity_threshold
        self._pass_threshold = pass_threshold

    # ------------------------------------------------------------------
    # Image loading
    # ------------------------------------------------------------------

    def _load_frame(self, output_path: str) -> Optional[Any]:
        """Load a rendered frame from disk as a float32 numpy array.

        Tries image libraries in order: OIIO > pyexr > PIL.
        Returns numpy array (H, W, C) in [0, 1] float32 range,
        or None if loading failed or no library is available.
        """
        if not NUMPY_AVAILABLE:
            logger.debug("numpy not available — can't load frame pixels")
            return None

        if not os.path.exists(output_path):
            logger.debug("Frame file does not exist: %s", output_path)
            return None

        ext = os.path.splitext(output_path)[1].lower()

        # --- OIIO path (handles EXR, PNG, JPEG, TIFF, and more) ---
        if _OIIO_AVAILABLE:
            try:
                inp = oiio.ImageInput.open(output_path)
                if inp is None:
                    logger.warning(
                        "OIIO couldn't open %s: %s",
                        output_path,
                        oiio.geterror(),
                    )
                    return None
                spec = inp.spec()
                try:
                    # Probed against the binding hython 22.0.368 actually ships
                    # (OpenImageIO 2.5.18.0): read_image has three overloads and
                    # every one of them RETURNS the pixels. The out-parameter form
                    # read_image(x, y, format, buf) is the C++ API transliterated
                    # into Python. It raises TypeError on every call, so this branch
                    # had never once succeeded on a shipping interpreter -- and the
                    # np.empty() preallocation it fed was dead code.
                    buf = inp.read_image(0, 0, 0, spec.nchannels, oiio.FLOAT)
                finally:
                    # close() belongs in finally, not after the read. Previously a
                    # failed read left via the except below WITHOUT closing, so every
                    # failure leaked a file handle; on Windows that also makes the
                    # containing directory undeletable (WinError 32). A verification
                    # loop over a frame sequence leaked one handle per bad frame.
                    inp.close()
                if buf is None:
                    logger.warning("OIIO read returned no pixels: %s", output_path)
                    return None
                return np.asarray(buf, dtype=np.float32)
            except Exception as exc:
                logger.warning("OIIO failed to read %s: %s", output_path, exc)
                return None

        # --- pyexr path (EXR only) ---
        if _PYEXR_AVAILABLE and ext == ".exr":
            try:
                data = pyexr.open(output_path).get()
                return np.asarray(data, dtype=np.float32)
            except Exception as exc:
                logger.warning("pyexr failed to read %s: %s", output_path, exc)
                return None

        # --- PIL path (PNG, JPEG, TIFF, BMP — not EXR) ---
        if _PIL_AVAILABLE and ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
            try:
                img = _PILImage.open(output_path)
                arr = np.asarray(img, dtype=np.float32)
                # Normalize based on original bit depth
                if arr.max() > 1.0:
                    if img.mode in ("I;16", "I;16B", "I;16L"):
                        arr = arr / 65535.0
                    elif arr.max() > 255.0:
                        arr = arr / 65535.0
                    else:
                        arr = arr / 255.0
                # Ensure 3D shape (H, W, C)
                if arr.ndim == 2:
                    arr = arr[:, :, np.newaxis]
                return arr
            except Exception as exc:
                logger.warning("PIL failed to read %s: %s", output_path, exc)
                return None

        # No library could handle this format
        logger.debug(
            "No image library available for %s (ext=%s). "
            "Install OpenImageIO, pyexr, or Pillow.",
            output_path,
            ext,
        )
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_frame(
        self,
        frame: int,
        output_path: str,
        pixels: Optional[Any] = None,
        image_data: Optional[Any] = None,
        load_if_missing: bool = True,
    ) -> FrameEvaluation:
        """Evaluate a single rendered frame.

        Args:
            frame: Frame number.
            output_path: Path to the rendered image file.
            pixels: Optional numpy array (H, W, C) with pixel values
                    in [0, 1] range. If not provided, attempts to load
                    from output_path automatically.
            image_data: Legacy alias for pixels (backwards compatibility).
            load_if_missing: Load from disk when no pixels were handed in.
                    evaluate_sequence resolves pixels once for both the
                    per-frame and the temporal checks, so it passes False: a
                    second read here could succeed after the first failed,
                    and the frame would be judged on pixels the motion check
                    never saw.

        Returns:
            FrameEvaluation with issues list and per-check metrics.
        """
        # Resolve pixel data: pixels takes priority over image_data
        resolved_pixels = pixels if pixels is not None else image_data

        issues: List[str] = []
        metrics: Dict[str, float] = {}

        # Auto-load from disk if no pixel data provided
        if resolved_pixels is None and load_if_missing:
            resolved_pixels = self._load_frame(output_path)

        if resolved_pixels is None:
            # Couldn't load — check if the file exists at all
            # (isfile so a directory path counts as a missing frame)
            if not os.path.isfile(output_path):
                return FrameEvaluation(
                    frame=frame,
                    output_path=output_path,
                    passed=False,
                    issues=[f"Couldn't find rendered output at {output_path}"],
                    metrics={"quality_score": 0.0},
                )
            # File exists but couldn't load pixels — quality is UNKNOWN.
            # An unanalyzed frame must never report as passed.
            return FrameEvaluation(
                frame=frame,
                output_path=output_path,
                passed=False,
                verified=False,
                issues=["Couldn't load frame for pixel analysis — quality unverified "
                        "(install OpenImageIO, pyexr, or Pillow)"],
                metrics={"unverified": 1.0},
            )

        if resolved_pixels is not None and NUMPY_AVAILABLE:
            arr = np.asarray(resolved_pixels, dtype=np.float64)

            # Run all per-frame checks
            black_result = self._check_black_frame(arr)
            if black_result:
                issues.append(black_result)
            metrics["black_ratio"] = self._compute_black_ratio(arr)

            nan_inf_result = self._check_nan_inf(arr)
            if nan_inf_result:
                issues.append(nan_inf_result)
            metrics["nan_count"] = float(np.isnan(arr).sum())
            metrics["inf_count"] = float(np.isinf(arr).sum())

            firefly_result = self._check_fireflies(arr)
            if firefly_result:
                issues.append(firefly_result)

            clipping_result = self._check_clipping(arr)
            if clipping_result:
                issues.append(clipping_result)

            # Per-frame mean luminance, so the temporal checks can run on the
            # driver path where full frames are never held in memory.
            metrics["mean_luminance"] = self._mean_luminance(arr)

        elif resolved_pixels is not None and not NUMPY_AVAILABLE:
            logger.warning(
                "numpy not available — can't run pixel-level quality checks for frame %d",
                frame,
            )
            # Pixels were handed to us but can't be analyzed — quality is UNKNOWN.
            return FrameEvaluation(
                frame=frame,
                output_path=output_path,
                passed=False,
                verified=False,
                issues=["Couldn't analyze frame pixels — quality unverified "
                        "(install numpy)"],
                metrics={"unverified": 1.0},
            )

        # Score: 1.0 minus 0.25 per issue, floored at 0.0
        score = max(0.0, 1.0 - 0.25 * len(issues))
        metrics["quality_score"] = score

        return FrameEvaluation(
            frame=frame,
            output_path=output_path,
            passed=len(issues) == 0,
            issues=issues,
            metrics=metrics,
        )

    def evaluate_sequence(
        self,
        frame_results: List[Dict[str, Any]],
        planned_frames: Optional[Any] = None,
        farm_failed_frames: int = 0,
    ) -> SequenceEvaluation:
        """Evaluate an entire rendered sequence.

        Args:
            frame_results: List of dicts with keys:
                - frame (int): frame number
                - output_path (str): path to rendered file
                - image_data (optional): numpy array or None
                - error (optional): the farm's per-frame error, "" for a good frame
                - failed (optional): True when the farm marked the frame failed
            planned_frames: Optional iterable of frame numbers the plan asked
                for. When given, a sequence that evaluated different frames
                fails, whatever its mean score.
            farm_failed_frames: The farm's own failure count for this render.
                Above zero fails the sequence, whatever its mean score.

        Returns:
            SequenceEvaluation with per-frame and temporal analysis. A missing
            output, a failed frame or a plan mismatch fails the sequence; the
            mean score governs soft issues only.
        """
        frame_evals: List[FrameEvaluation] = []

        # Load each frame once, and keep only the previous one, so the motion
        # check can compare real pixels on the driver path, which never hands
        # frames over in memory. One frame of storage, whatever the range.
        prev_pixels: Optional[Any] = None
        jump_frames: List[int] = []

        for fr in frame_results:
            pixels = fr.get("image_data")
            if pixels is None and NUMPY_AVAILABLE:
                pixels = self._load_frame(fr.get("output_path") or "")
            fe = self.evaluate_frame(
                frame=fr["frame"],
                output_path=fr["output_path"],
                pixels=pixels,
                # Resolved once here, for both the per-frame checks and the
                # motion comparison. A second read inside evaluate_frame could
                # succeed after this one failed, and the frame would be judged
                # on pixels the motion check never saw.
                load_if_missing=False,
            )
            frame_evals.append(fe)

            if NUMPY_AVAILABLE and pixels is not None:
                arr = np.asarray(pixels, dtype=np.float64)
                if (
                    prev_pixels is not None
                    and arr.shape == prev_pixels.shape
                    and float(np.mean(np.abs(arr - prev_pixels))) > self._continuity_threshold
                ):
                    jump_frames.append(fr["frame"])
                prev_pixels = arr
            else:
                prev_pixels = None

        # Temporal / sequence-level checks
        temporal_issues: List[str] = []
        hard_failures: List[str] = []

        missing = self._check_missing_frames(frame_evals)
        if missing:
            temporal_issues.append(missing)

        if NUMPY_AVAILABLE and len(frame_evals) >= 2:
            flicker = self._check_flickering_from_evals(frame_evals, frame_results)
            if flicker:
                temporal_issues.append(flicker)

            continuity = self._motion_issue(jump_frames)
            if continuity:
                temporal_issues.append(continuity)

        # Hard failures: a frame that never produced an output, a frame the
        # farm reported as failed, or a sequence that does not match the plan.
        # None of these may be averaged away.
        missing_output = [
            fe.frame for fe in frame_evals
            if any("couldn't find rendered output" in i.lower() for i in fe.issues)
        ]
        if missing_output:
            hard_failures.append(
                f"Missing rendered output for {len(missing_output)} frame(s): "
                + ", ".join(str(f) for f in sorted(missing_output)[:20])
            )

        farm_failed = sorted({
            int(fr.get("frame", 0))
            for fr in frame_results
            if fr.get("error") or fr.get("failed")
        })
        if farm_failed:
            hard_failures.append(
                f"The farm reported {len(farm_failed)} failed frame(s): "
                + ", ".join(str(f) for f in farm_failed[:20])
            )
        try:
            failed_count = int(farm_failed_frames or 0)
        except (TypeError, ValueError):
            failed_count = 0
        if failed_count > len(farm_failed):
            hard_failures.append(
                f"The farm reported {failed_count} failed frame(s) "
                f"for this render."
            )

        if planned_frames is not None:
            planned = sorted({int(f) for f in planned_frames})
            evaluated = sorted({fe.frame for fe in frame_evals})
            missing_planned = sorted(set(planned) - set(evaluated))
            unplanned = sorted(set(evaluated) - set(planned))
            if missing_planned:
                hard_failures.append(
                    f"Missing planned frame(s): "
                    + ", ".join(str(f) for f in missing_planned[:20])
                )
            if unplanned:
                hard_failures.append(
                    f"Evaluated frame(s) the plan did not ask for: "
                    + ", ".join(str(f) for f in unplanned[:20])
                )

        temporal_issues.extend(hard_failures)

        # Overall score — only verified frames can vouch for quality
        verified_evals = [fe for fe in frame_evals if fe.verified]
        unverified_count = len(frame_evals) - len(verified_evals)
        if verified_evals:
            frame_scores = [
                fe.metrics.get("quality_score", 0.0) for fe in verified_evals
            ]
            mean_score = sum(frame_scores) / len(frame_scores)
        else:
            mean_score = 0.0

        temporal_factor = max(0.5, 1.0 - 0.1 * len(temporal_issues))
        overall_score = mean_score * temporal_factor

        passed = (
            unverified_count == 0
            and not hard_failures
            and overall_score >= self._pass_threshold
            and not any(
                not fe.passed for fe in frame_evals
                if any("black frame" in i.lower() or "nan" in i.lower() for i in fe.issues)
            )
        )

        return SequenceEvaluation(
            frame_evaluations=frame_evals,
            temporal_issues=temporal_issues,
            overall_score=overall_score,
            passed=passed,
            unverified_count=unverified_count,
            pass_threshold=self._pass_threshold,
        )

    def evaluate_sequence_from_disk(
        self,
        frame_paths: Dict[int, str],
    ) -> SequenceEvaluation:
        """Evaluate a sequence of rendered frames from disk.

        Loads each frame automatically using _load_frame(). This is a
        convenience wrapper around evaluate_frame + evaluate_sequence
        for the common case where frames are already on disk.

        Args:
            frame_paths: Dict mapping frame number to file path,
                         e.g., {1: "/tmp/frame.0001.exr", 2: "/tmp/frame.0002.exr"}

        Returns:
            SequenceEvaluation with per-frame and temporal analysis.
        """
        frame_results: List[Dict[str, Any]] = []
        for frame_num in sorted(frame_paths.keys()):
            path = frame_paths[frame_num]
            loaded = self._load_frame(path)
            frame_results.append({
                "frame": frame_num,
                "output_path": path,
                "image_data": loaded,
            })
        return self.evaluate_sequence(frame_results)

    # ------------------------------------------------------------------
    # Per-frame checks
    # ------------------------------------------------------------------

    def _check_black_frame(self, arr: Any) -> Optional[str]:
        """Detect if >95% of pixels are near-black (<threshold)."""
        ratio = self._compute_black_ratio(arr)
        if ratio > self._black_ratio:
            return (
                f"Black frame detected: {ratio:.1%} of pixels are near-black "
                f"(threshold {self._black_ratio:.0%}). This usually means the "
                f"camera, lights, or materials aren't set up correctly."
            )
        return None

    def _mean_luminance(self, arr: Any) -> float:
        """Mean pixel value of a frame, ignoring NaN. 0.0 when unmeasurable."""
        if not NUMPY_AVAILABLE:
            return 0.0
        with np.errstate(invalid="ignore"):
            value = float(np.nanmean(arr))
        return value if np.isfinite(value) else 0.0

    def _compute_black_ratio(self, arr: Any) -> float:
        """Compute fraction of near-black pixels."""
        if arr.ndim == 3:
            luminance = np.mean(arr, axis=-1)
        else:
            luminance = arr
        return float(np.mean(luminance < self._black_threshold))

    def _check_nan_inf(self, arr: Any) -> Optional[str]:
        """Detect NaN or Inf values in pixel data."""
        nan_count = int(np.isnan(arr).sum())
        inf_count = int(np.isinf(arr).sum())
        if nan_count > 0 or inf_count > 0:
            parts = []
            if nan_count > 0:
                parts.append(f"{nan_count} NaN")
            if inf_count > 0:
                parts.append(f"{inf_count} Inf")
            return (
                f"Found {' and '.join(parts)} pixel value(s). "
                f"This typically indicates a shader or lighting issue."
            )
        return None

    def _check_fireflies(self, arr: Any) -> Optional[str]:
        """Detect outlier pixels >10 std devs from mean (fireflies)."""
        if arr.ndim == 3:
            luminance = np.mean(arr, axis=-1)
        else:
            luminance = arr

        mean_val = np.mean(luminance)
        std_val = np.std(luminance)

        if std_val < 1e-10:
            return None  # Flat image, no fireflies possible

        outlier_mask = np.abs(luminance - mean_val) > (self._firefly_std_devs * std_val)
        outlier_count = int(outlier_mask.sum())
        total_pixels = luminance.size

        if outlier_count > 0:
            ratio = outlier_count / total_pixels
            return (
                f"Detected {outlier_count} firefly pixel(s) ({ratio:.4%} of image) "
                f"exceeding {self._firefly_std_devs} standard deviations from mean. "
                f"Consider increasing pixel samples or enabling the denoiser."
            )
        return None

    def _check_clipping(self, arr: Any) -> Optional[str]:
        """Detect if >5% of pixels are pure white or pure black."""
        if arr.ndim == 3:
            luminance = np.mean(arr, axis=-1)
        else:
            luminance = arr

        total = luminance.size
        pure_black = float(np.sum(luminance <= 0.0)) / total
        pure_white = float(np.sum(luminance >= 1.0)) / total

        issues = []
        if pure_black > self._clipping_ratio:
            issues.append(f"{pure_black:.1%} pure black")
        if pure_white > self._clipping_ratio:
            issues.append(f"{pure_white:.1%} pure white")

        if issues:
            return (
                f"Clipping detected: {' and '.join(issues)} pixels "
                f"(threshold {self._clipping_ratio:.0%}). "
                f"Adjust exposure to recover detail in clipped areas."
            )
        return None

    # ------------------------------------------------------------------
    # Sequence-level checks
    # ------------------------------------------------------------------

    def _check_flickering_from_evals(
        self,
        frame_evals: List[FrameEvaluation],
        frame_results: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Detect flicker from the per-frame mean luminance evaluate_frame measured.

        This is the path the driver takes: it never holds full frames in memory,
        so before this existed the temporal checks saw nothing.
        """
        luminances = [fe.metrics.get("mean_luminance") for fe in frame_evals]
        # Every frame must have been measured. Compressing the list past an
        # unverified frame would compare frames that are not adjacent.
        if len(luminances) >= 3 and all(v is not None for v in luminances):
            return self._flicker_from_luminances(luminances)  # type: ignore[arg-type]
        # No measured luminance (unverified frames, or an old caller) — fall
        # back to whatever pixel data the results carry.
        return self._check_flickering(frame_results)

    def _check_flickering(
        self,
        frame_results: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Detect high-frequency luminance changes between consecutive frames."""
        luminances: List[float] = []
        for fr in frame_results:
            data = fr.get("image_data")
            if data is not None and NUMPY_AVAILABLE:
                arr = np.asarray(data, dtype=np.float64)
                luminances.append(self._mean_luminance(arr))
            else:
                luminances.append(0.0)

        return self._flicker_from_luminances(luminances)

    def _flicker_from_luminances(
        self,
        luminances: List[float],
    ) -> Optional[str]:
        """Detect high-frequency luminance changes between consecutive frames."""
        if len(luminances) < 3:
            return None

        # High-frequency = sign changes in luminance delta
        deltas = [luminances[i + 1] - luminances[i] for i in range(len(luminances) - 1)]
        sign_changes = sum(
            1
            for i in range(len(deltas) - 1)
            if (deltas[i] > self._flicker_threshold and deltas[i + 1] < -self._flicker_threshold)
            or (deltas[i] < -self._flicker_threshold and deltas[i + 1] > self._flicker_threshold)
        )

        if sign_changes > len(deltas) * 0.3:
            return (
                f"Flickering detected: {sign_changes} high-frequency luminance reversals "
                f"across {len(deltas)} frame transitions. Consider increasing pixel samples "
                f"for more stable convergence."
            )
        return None

    def _check_motion_continuity(
        self,
        frame_results: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Detect large frame-to-frame jumps suggesting temporal discontinuity."""
        if len(frame_results) < 2:
            return None

        jump_frames: List[int] = []
        prev_arr = None

        for fr in frame_results:
            data = fr.get("image_data")
            if data is None or not NUMPY_AVAILABLE:
                prev_arr = None
                continue

            arr = np.asarray(data, dtype=np.float64)
            if prev_arr is not None:
                diff = float(np.mean(np.abs(arr - prev_arr)))
                if diff > self._continuity_threshold:
                    jump_frames.append(fr["frame"])
            prev_arr = arr

        return self._motion_issue(jump_frames)

    def _motion_issue(self, jump_frames: List[int]) -> Optional[str]:
        """Describe the motion-discontinuity issue, if any frames jumped."""
        if jump_frames:
            frames_str = ", ".join(str(f) for f in jump_frames[:10])
            return (
                f"Motion discontinuity detected at frame(s): {frames_str}. "
                f"Large frame-to-frame pixel differences suggest a temporal "
                f"coherence issue (e.g., popping lights, unstable sampling)."
            )
        return None

    def _check_missing_frames(
        self,
        frame_evals: List[FrameEvaluation],
    ) -> Optional[str]:
        """Detect gaps in the frame number sequence."""
        if len(frame_evals) < 2:
            return None

        frames = sorted(fe.frame for fe in frame_evals)
        expected = set(range(frames[0], frames[-1] + 1))
        actual = set(frames)
        missing = sorted(expected - actual)

        if missing:
            frames_str = ", ".join(str(f) for f in missing[:20])
            suffix = f" (and {len(missing) - 20} more)" if len(missing) > 20 else ""
            return (
                f"Missing {len(missing)} frame(s) in sequence: {frames_str}{suffix}. "
                f"These frames may have failed to render."
            )
        return None
