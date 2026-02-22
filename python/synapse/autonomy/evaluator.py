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
    """

    def __init__(
        self,
        black_threshold: float = 0.001,
        black_ratio: float = 0.95,
        firefly_std_devs: float = 10.0,
        clipping_ratio: float = 0.05,
        flicker_threshold: float = 0.15,
        continuity_threshold: float = 0.5,
    ) -> None:
        self._black_threshold = black_threshold
        self._black_ratio = black_ratio
        self._firefly_std_devs = firefly_std_devs
        self._clipping_ratio = clipping_ratio
        self._flicker_threshold = flicker_threshold
        self._continuity_threshold = continuity_threshold

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
                buf = np.empty(
                    (spec.height, spec.width, spec.nchannels),
                    dtype=np.float32,
                )
                inp.read_image(0, 0, oiio.FLOAT, buf)
                inp.close()
                return buf
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
    ) -> FrameEvaluation:
        """Evaluate a single rendered frame.

        Args:
            frame: Frame number.
            output_path: Path to the rendered image file.
            pixels: Optional numpy array (H, W, C) with pixel values
                    in [0, 1] range. If not provided, attempts to load
                    from output_path automatically.
            image_data: Legacy alias for pixels (backwards compatibility).

        Returns:
            FrameEvaluation with issues list and per-check metrics.
        """
        # Resolve pixel data: pixels takes priority over image_data
        resolved_pixels = pixels if pixels is not None else image_data

        issues: List[str] = []
        metrics: Dict[str, float] = {}

        # Auto-load from disk if no pixel data provided
        if resolved_pixels is None:
            resolved_pixels = self._load_frame(output_path)
            if resolved_pixels is None:
                # Couldn't load — check if file exists at all
                if not os.path.exists(output_path):
                    return FrameEvaluation(
                        frame=frame,
                        output_path=output_path,
                        passed=False,
                        issues=[f"Couldn't find rendered output at {output_path}"],
                        metrics={},
                    )
                # File exists but couldn't load pixels — skip quality checks
                return FrameEvaluation(
                    frame=frame,
                    output_path=output_path,
                    passed=True,
                    issues=["Couldn't load frame for pixel analysis — skipping quality checks"],
                    metrics={"quality_score": 1.0},
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

        elif resolved_pixels is not None and not NUMPY_AVAILABLE:
            logger.warning(
                "numpy not available — skipping pixel-level quality checks for frame %d",
                frame,
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
    ) -> SequenceEvaluation:
        """Evaluate an entire rendered sequence.

        Args:
            frame_results: List of dicts with keys:
                - frame (int): frame number
                - output_path (str): path to rendered file
                - image_data (optional): numpy array or None

        Returns:
            SequenceEvaluation with per-frame and temporal analysis.
        """
        frame_evals: List[FrameEvaluation] = []

        for fr in frame_results:
            fe = self.evaluate_frame(
                frame=fr["frame"],
                output_path=fr["output_path"],
                image_data=fr.get("image_data"),
            )
            frame_evals.append(fe)

        # Temporal / sequence-level checks
        temporal_issues: List[str] = []

        missing = self._check_missing_frames(frame_evals)
        if missing:
            temporal_issues.append(missing)

        if NUMPY_AVAILABLE and len(frame_evals) >= 2:
            flicker = self._check_flickering(frame_results)
            if flicker:
                temporal_issues.append(flicker)

            continuity = self._check_motion_continuity(frame_results)
            if continuity:
                temporal_issues.append(continuity)

        # Overall score
        if frame_evals:
            frame_scores = [
                fe.metrics.get("quality_score", 1.0) for fe in frame_evals
            ]
            mean_score = sum(frame_scores) / len(frame_scores)
        else:
            mean_score = 0.0

        temporal_factor = max(0.5, 1.0 - 0.1 * len(temporal_issues))
        overall_score = mean_score * temporal_factor

        passed = overall_score >= 0.7 and not any(
            not fe.passed for fe in frame_evals
            if any("black frame" in i.lower() or "nan" in i.lower() for i in fe.issues)
        )

        return SequenceEvaluation(
            frame_evaluations=frame_evals,
            temporal_issues=temporal_issues,
            overall_score=overall_score,
            passed=passed,
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
                luminances.append(float(np.mean(arr)))
            else:
                luminances.append(0.0)

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
        prev_frame = None

        for fr in frame_results:
            data = fr.get("image_data")
            if data is None or not NUMPY_AVAILABLE:
                prev_arr = None
                prev_frame = fr["frame"]
                continue

            arr = np.asarray(data, dtype=np.float64)
            if prev_arr is not None:
                diff = float(np.mean(np.abs(arr - prev_arr)))
                if diff > self._continuity_threshold:
                    jump_frames.append(fr["frame"])
            prev_arr = arr
            prev_frame = fr["frame"]

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
