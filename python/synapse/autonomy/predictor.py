"""
Synapse Autonomy Pipeline -- Render Predictor

Predict-then-Verify pattern based on 'Predict Before Executing' (2601.05930).
Introspects the USD stage before render launch to build a prediction of
expected outputs, then compares actual results post-render to catch
discrepancies early.

Two-phase workflow:
    1. predict() -- pre-render: introspect stage, build RenderPrediction
    2. verify()  -- post-render: compare prediction to actual results

stdlib-only (no USD imports at module level -- injected via handler calls).
"""

import logging
import os
from typing import Any, Dict, List, Optional, Protocol

from .models import (
    RenderPlan,
    RenderPrediction,
    SequenceEvaluation,
    VerificationResult,
)

logger = logging.getLogger("synapse.autonomy.predictor")


class HandlerInterface(Protocol):
    """Async callable interface for executing MCP handler tools."""

    async def call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        ...


class RenderPredictor:
    """Predicts render outcomes and verifies them post-render.

    Uses MCP handler calls to introspect the scene without importing
    USD libraries directly. This keeps the module testable without
    Houdini and consistent with the rest of the autonomy pipeline.

    Args:
        handler_interface: Async callable for MCP handler tools.
        output_size_threshold: Minimum expected file size in bytes
            for a rendered frame. Files smaller than this are flagged
            as potentially corrupt.
        discrepancy_rerender_threshold: If the verification score
            drops below this value, should_rerender is set to True.
    """

    def __init__(
        self,
        handler_interface: HandlerInterface,
        output_size_threshold: int = 1024,
        discrepancy_rerender_threshold: float = 0.7,
    ) -> None:
        self._handler = handler_interface
        self._output_size_threshold = output_size_threshold
        self._rerender_threshold = discrepancy_rerender_threshold

    # ------------------------------------------------------------------
    # Phase 1: Pre-render prediction
    # ------------------------------------------------------------------

    async def predict(
        self,
        plan: RenderPlan,
        validator_results: Optional[List[Any]] = None,
    ) -> RenderPrediction:
        """Build a prediction of expected render outputs.

        Introspects the USD stage via handler calls to gather:
            - RenderProduct prim and output path pattern
            - Camera prim path
            - Geometry, material, and light counts
            - Resolution from render settings
            - Motion blur and displacement presence

        Args:
            plan: The render plan about to be executed.
            validator_results: Optional pre-flight check results
                (from PreFlightValidator) for cross-referencing.

        Returns:
            RenderPrediction with scene structure predictions filled in.
        """
        prediction = RenderPrediction()
        issues: List[str] = []

        # Extract frame range from plan
        prediction.expected_frame_range = (
            plan.steps[-1].params.get("start_frame", 1) if plan.steps else 1,
            plan.steps[-1].params.get("end_frame", 1) if plan.steps else 1,
        )

        # Introspect stage info
        try:
            stage_info = await self._handler.call("get_stage_info", {})
            prediction.geo_prim_count = stage_info.get("prim_count", 0)
        except Exception as exc:
            issues.append(f"Couldn't query stage info: {exc}")
            stage_info = {}

        # Find render settings and camera
        try:
            scene_info = await self._handler.call("get_scene_info", {})
            prediction.camera_prim = scene_info.get("camera", "")
        except Exception as exc:
            issues.append(f"Couldn't query scene info: {exc}")

        # Introspect render settings via execute_python
        render_data = await self._introspect_render_setup()
        prediction.render_product_path = render_data.get("render_product_path", "")
        prediction.output_file_pattern = render_data.get("output_file_pattern", "")
        prediction.camera_prim = render_data.get("camera_prim", "") or prediction.camera_prim
        prediction.material_count = render_data.get("material_count", 0)
        prediction.light_count = render_data.get("light_count", 0)
        prediction.geo_prim_count = render_data.get("geo_prim_count", 0) or prediction.geo_prim_count

        res = render_data.get("resolution", (1920, 1080))
        if isinstance(res, (list, tuple)) and len(res) >= 2:
            prediction.expected_resolution = (int(res[0]), int(res[1]))

        prediction.has_motion_blur = render_data.get("has_motion_blur", False)
        prediction.has_displacement = render_data.get("has_displacement", False)

        # Estimate render time based on scene complexity
        prediction.estimated_render_time_seconds = self._estimate_render_time(
            prediction
        )

        # Validate critical requirements
        if not prediction.camera_prim:
            issues.append("No camera prim found -- render will likely fail")
        if prediction.light_count == 0:
            issues.append("No lights found -- render may produce a black frame")
        if prediction.geo_prim_count == 0:
            issues.append("No geometry prims found -- nothing to render")
        if not prediction.output_file_pattern:
            issues.append("No output file pattern found -- render output path may be missing")

        # Cross-reference with validator results
        if validator_results:
            for check in validator_results:
                if hasattr(check, "passed") and not check.passed:
                    if hasattr(check, "message") and check.message:
                        issues.append(f"Pre-flight: {check.message}")

        prediction.pre_render_issues = issues
        if issues:
            logger.warning(
                "Pre-render prediction found %d issue(s): %s",
                len(issues),
                "; ".join(issues),
            )

        return prediction

    async def _introspect_render_setup(self) -> Dict[str, Any]:
        """Query the USD stage for render setup details via execute_python.

        Returns a dict with render_product_path, output_file_pattern,
        camera_prim, material_count, light_count, geo_prim_count,
        resolution, has_motion_blur, has_displacement.
        """
        code = """
import hou, json

result = {
    "render_product_path": "",
    "output_file_pattern": "",
    "camera_prim": "",
    "material_count": 0,
    "light_count": 0,
    "geo_prim_count": 0,
    "resolution": [1920, 1080],
    "has_motion_blur": False,
    "has_displacement": False,
}

try:
    from pxr import UsdRender, UsdGeom, UsdLux, UsdShade

    # Find the display LOP node to get the stage
    stage_node = None
    stage_net = hou.node("/stage")
    if stage_net:
        stage_node = stage_net.displayNode()

    if stage_node:
        stage = stage_node.stage()
        if stage:
            mat_count = 0
            light_count = 0
            geo_count = 0
            cam_path = ""
            render_product = ""
            output_pattern = ""
            res_x, res_y = 1920, 1080
            motion_blur = False
            displacement = False

            for prim in stage.Traverse():
                if prim.IsA(UsdShade.Material):
                    mat_count += 1
                elif prim.IsA(UsdLux.BoundableLightBase) or prim.IsA(UsdLux.NonboundableLightBase):
                    light_count += 1
                elif prim.IsA(UsdGeom.Gprim):
                    geo_count += 1
                elif prim.IsA(UsdGeom.Camera) and not cam_path:
                    cam_path = str(prim.GetPath())
                elif prim.IsA(UsdRender.Product):
                    render_product = str(prim.GetPath())
                    pn = prim.GetAttribute("productName")
                    if pn and pn.Get():
                        output_pattern = str(pn.Get())
                elif prim.IsA(UsdRender.Settings):
                    rx = prim.GetAttribute("resolution")
                    if rx and rx.Get():
                        r = rx.Get()
                        res_x, res_y = int(r[0]), int(r[1])

            result["material_count"] = mat_count
            result["light_count"] = light_count
            result["geo_prim_count"] = geo_count
            result["camera_prim"] = cam_path
            result["render_product_path"] = render_product
            result["output_file_pattern"] = output_pattern
            result["resolution"] = [res_x, res_y]
            result["has_motion_blur"] = motion_blur
            result["has_displacement"] = displacement
except Exception:
    pass

print(json.dumps(result, sort_keys=True))
"""
        try:
            resp = await self._handler.call("execute_python", {"content": code})
            output = resp.get("output", "").strip()
            # Parse the last line as JSON (print output)
            lines = output.strip().split("\n")
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("{"):
                    import json
                    return json.loads(line)
            return {}
        except Exception as exc:
            logger.warning("Couldn't introspect render setup: %s", exc)
            return {}

    def _estimate_render_time(self, prediction: RenderPrediction) -> float:
        """Rough render time estimate based on scene complexity.

        This is intentionally conservative -- used for timeout safety,
        not for accurate time prediction.
        """
        base_seconds = 10.0  # minimum per frame
        geo_factor = min(prediction.geo_prim_count * 0.5, 120.0)
        mat_factor = prediction.material_count * 1.0
        res_factor = (
            prediction.expected_resolution[0]
            * prediction.expected_resolution[1]
            / (1920 * 1080)
        )
        displacement_factor = 2.0 if prediction.has_displacement else 1.0
        motion_blur_factor = 1.5 if prediction.has_motion_blur else 1.0

        frame_count = max(
            1,
            prediction.expected_frame_range[1] - prediction.expected_frame_range[0] + 1,
        )

        per_frame = (
            (base_seconds + geo_factor + mat_factor)
            * res_factor
            * displacement_factor
            * motion_blur_factor
        )
        return per_frame * frame_count

    # ------------------------------------------------------------------
    # Phase 2: Post-render verification
    # ------------------------------------------------------------------

    async def verify(
        self,
        prediction: RenderPrediction,
        evaluation: Optional[SequenceEvaluation] = None,
    ) -> VerificationResult:
        """Compare pre-render prediction to post-render reality.

        Checks:
            - Expected output files exist on disk
            - File sizes are reasonable (not empty/corrupt)
            - Frame count matches expected range
            - Evaluation quality score (if provided) is acceptable
            - Pre-render issues that materialized

        Args:
            prediction: The prediction built before rendering.
            evaluation: Optional quality evaluation from RenderEvaluator.

        Returns:
            VerificationResult with discrepancies and rerender recommendation.
        """
        discrepancies: List[str] = []

        # Check output files
        if prediction.actual_output_files:
            expected_count = (
                prediction.expected_frame_range[1]
                - prediction.expected_frame_range[0]
                + 1
            )
            actual_count = len(prediction.actual_output_files)

            if actual_count < expected_count:
                discrepancies.append(
                    f"Expected {expected_count} output file(s), got {actual_count}"
                )

            # Check file sizes
            for fpath in prediction.actual_output_files:
                if os.path.exists(fpath):
                    size = os.path.getsize(fpath)
                    if size < self._output_size_threshold:
                        discrepancies.append(
                            f"Output file suspiciously small ({size} bytes): {fpath}"
                        )
                else:
                    discrepancies.append(f"Expected output file missing: {fpath}")
        elif not prediction.render_succeeded:
            discrepancies.append("Render did not succeed -- no output files")

        # Check evaluation quality
        if evaluation is not None:
            if not evaluation.passed:
                discrepancies.append(
                    f"Quality evaluation failed (score: {evaluation.overall_score:.2f})"
                )

            # Check for critical frame issues
            critical_frames = [
                fe.frame
                for fe in evaluation.frame_evaluations
                if not fe.passed
                and any(
                    kw in issue.lower()
                    for issue in fe.issues
                    for kw in ("black frame", "nan", "inf")
                )
            ]
            if critical_frames:
                frames_str = ", ".join(str(f) for f in critical_frames[:10])
                discrepancies.append(
                    f"Critical issues on frame(s): {frames_str}"
                )

        # Check pre-render issues that weren't resolved
        if prediction.pre_render_issues:
            # Pre-render issues are warnings -- if render failed, they become discrepancies
            if not prediction.render_succeeded:
                for issue in prediction.pre_render_issues:
                    discrepancies.append(f"Pre-render warning materialized: {issue}")

        # Compute verification score
        score = self._compute_verification_score(prediction, evaluation, discrepancies)

        should_rerender = score < self._rerender_threshold

        reasoning_parts = []
        if discrepancies:
            reasoning_parts.append(
                f"{len(discrepancies)} discrepancy(ies) found"
            )
        if should_rerender:
            reasoning_parts.append(
                f"score {score:.2f} < threshold {self._rerender_threshold}"
            )
        else:
            reasoning_parts.append(
                f"score {score:.2f} meets threshold"
            )
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Verification passed"

        return VerificationResult(
            prediction=prediction,
            evaluation=evaluation,
            discrepancies=discrepancies,
            score=score,
            should_rerender=should_rerender,
            reasoning=reasoning,
        )

    def _compute_verification_score(
        self,
        prediction: RenderPrediction,
        evaluation: Optional[SequenceEvaluation],
        discrepancies: List[str],
    ) -> float:
        """Compute a verification score between 0.0 and 1.0.

        Factors:
            - Render success: 0.4 weight
            - Output file presence: 0.2 weight
            - Quality evaluation score: 0.3 weight
            - No discrepancies bonus: 0.1 weight
        """
        score = 0.0

        # Render succeeded
        if prediction.render_succeeded:
            score += 0.4

        # Output files present
        if prediction.actual_output_files:
            expected = max(
                1,
                prediction.expected_frame_range[1]
                - prediction.expected_frame_range[0]
                + 1,
            )
            actual = len(prediction.actual_output_files)
            file_ratio = min(1.0, actual / expected)
            score += 0.2 * file_ratio

        # Quality evaluation
        if evaluation is not None:
            score += 0.3 * evaluation.overall_score
        else:
            # No evaluation available -- assume neutral
            score += 0.15

        # No discrepancies bonus
        if not discrepancies:
            score += 0.1

        return min(1.0, score)

    # ------------------------------------------------------------------
    # Utility: replan benefit prediction
    # ------------------------------------------------------------------

    def predict_replan_benefit(
        self,
        evaluation: SequenceEvaluation,
        adjustments: Dict[str, Any],
    ) -> float:
        """Estimate how much a re-render with adjustments would improve quality.

        Returns a value between 0.0 (no benefit) and 1.0 (maximum benefit).
        Used to decide whether re-rendering is worth the compute cost.

        Args:
            evaluation: Current evaluation results.
            adjustments: Proposed render setting changes.

        Returns:
            Estimated benefit score.
        """
        if evaluation.passed:
            return 0.0  # Already passing

        benefit = 0.0
        all_issues: List[str] = []
        for fe in evaluation.frame_evaluations:
            all_issues.extend(fe.issues)
        all_issues.extend(evaluation.temporal_issues)

        # Fireflies are very fixable with more samples
        if any("firefly" in i.lower() or "fireflies" in i.lower() for i in all_issues):
            if "pixel_samples" in adjustments:
                benefit += 0.3

        # Clipping is fixable with exposure adjustment
        if any("clipping" in i.lower() for i in all_issues):
            if "exposure_compensation" in adjustments:
                benefit += 0.25

        # Flickering is somewhat fixable with more samples
        if any("flicker" in i.lower() for i in all_issues):
            if "pixel_samples" in adjustments:
                benefit += 0.2

        # Black frames are usually a setup issue, not fixable by rerender
        if any("black frame" in i.lower() for i in all_issues):
            benefit -= 0.1  # Rerender won't help

        # NaN/Inf is a shader issue, not fixable by rerender
        if any("nan" in i.lower() or "inf" in i.lower() for i in all_issues):
            benefit -= 0.1  # Rerender won't help

        return max(0.0, min(1.0, benefit))
