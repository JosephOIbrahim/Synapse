"""
Synapse Autonomy Pipeline -- Predictor Tests

Tests for synapse.autonomy.predictor.RenderPredictor.
Run without Houdini:
    python -m pytest tests/test_autonomy_predictor.py -v
"""

import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.autonomy.models import (
    CheckSeverity,
    FrameEvaluation,
    GateLevel,
    PreFlightCheck,
    RenderPlan,
    RenderPrediction,
    RenderStep,
    SequenceEvaluation,
    VerificationResult,
)

try:
    from synapse.autonomy.predictor import RenderPredictor
    HAS_PREDICTOR = True
except ImportError:
    HAS_PREDICTOR = False

pytestmark = pytest.mark.skipif(
    not HAS_PREDICTOR, reason="synapse.autonomy.predictor not yet implemented"
)


# =============================================================================
# FIXTURES
# =============================================================================


def _make_handler(**overrides):
    """Create a mock handler interface with sensible defaults."""
    handler = AsyncMock()

    stage_info = {"prim_count": 42, "status": "ok"}
    scene_info = {"camera": "/cameras/render_cam", "fps": 24}

    # Default introspection result (returned by execute_python)
    render_setup = json.dumps({
        "render_product_path": "/Render/Products/renderproduct1",
        "output_file_pattern": "$HIP/render/shot.$F4.exr",
        "camera_prim": "/cameras/render_cam",
        "material_count": 3,
        "light_count": 2,
        "geo_prim_count": 15,
        "resolution": [1920, 1080],
        "has_motion_blur": False,
        "has_displacement": False,
    }, sort_keys=True)

    async def mock_call(tool_name, params):
        if tool_name == "get_stage_info":
            return overrides.get("stage_info", stage_info)
        elif tool_name == "get_scene_info":
            return overrides.get("scene_info", scene_info)
        elif tool_name == "execute_python":
            return {"output": overrides.get("render_setup_json", render_setup)}
        return {"status": "ok"}

    handler.call = AsyncMock(side_effect=mock_call)
    return handler


def _make_plan(start=1, end=10):
    """Create a minimal render plan."""
    return RenderPlan(
        intent=f"render frames {start}-{end}",
        steps=[
            RenderStep(
                handler="render_sequence",
                params={"start_frame": start, "end_frame": end},
                description=f"Render frames {start}-{end}",
            ),
        ],
        estimated_frames=end - start + 1,
    )


def _make_evaluation(passed=True, score=0.85, num_frames=10, failed_frames=None):
    """Create a mock SequenceEvaluation."""
    frame_evals = []
    failed_frames = failed_frames or []
    for i in range(1, num_frames + 1):
        frame_passed = i not in failed_frames
        issues = []
        if not frame_passed:
            issues = ["Black frame detected"]
        frame_evals.append(
            FrameEvaluation(
                frame=i,
                output_path=f"/tmp/frame.{i:04d}.exr",
                passed=frame_passed,
                issues=issues,
                metrics={"quality_score": 1.0 if frame_passed else 0.25},
            )
        )
    return SequenceEvaluation(
        frame_evaluations=frame_evals,
        temporal_issues=[],
        overall_score=score,
        passed=passed,
    )


# =============================================================================
# PREDICT TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_predict_basic():
    """Predict should populate scene structure fields from handler calls."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)
    plan = _make_plan()

    prediction = await predictor.predict(plan)

    assert isinstance(prediction, RenderPrediction)
    assert prediction.camera_prim == "/cameras/render_cam"
    assert prediction.material_count == 3
    assert prediction.light_count == 2
    assert prediction.geo_prim_count == 15
    assert prediction.render_product_path == "/Render/Products/renderproduct1"
    assert prediction.output_file_pattern == "$HIP/render/shot.$F4.exr"
    assert prediction.expected_resolution == (1920, 1080)
    assert prediction.expected_frame_range == (1, 10)
    assert len(prediction.pre_render_issues) == 0


@pytest.mark.asyncio
async def test_predict_no_camera():
    """Predict should flag missing camera as a pre-render issue."""
    render_setup = json.dumps({
        "render_product_path": "/Render/Products/renderproduct1",
        "output_file_pattern": "$HIP/render/shot.$F4.exr",
        "camera_prim": "",
        "material_count": 3,
        "light_count": 2,
        "geo_prim_count": 15,
        "resolution": [1920, 1080],
        "has_motion_blur": False,
        "has_displacement": False,
    }, sort_keys=True)

    handler = _make_handler(
        render_setup_json=render_setup,
        scene_info={"camera": "", "fps": 24},
    )
    predictor = RenderPredictor(handler)
    plan = _make_plan()

    prediction = await predictor.predict(plan)
    assert any("camera" in issue.lower() for issue in prediction.pre_render_issues)


@pytest.mark.asyncio
async def test_predict_no_lights():
    """Predict should flag missing lights as a pre-render issue."""
    render_setup = json.dumps({
        "render_product_path": "/Render/Products/rp1",
        "output_file_pattern": "$HIP/render/shot.$F4.exr",
        "camera_prim": "/cameras/cam1",
        "material_count": 3,
        "light_count": 0,
        "geo_prim_count": 15,
        "resolution": [1920, 1080],
        "has_motion_blur": False,
        "has_displacement": False,
    }, sort_keys=True)

    handler = _make_handler(render_setup_json=render_setup)
    predictor = RenderPredictor(handler)
    plan = _make_plan()

    prediction = await predictor.predict(plan)
    assert any("light" in issue.lower() for issue in prediction.pre_render_issues)


@pytest.mark.asyncio
async def test_predict_no_geometry():
    """Predict should flag missing geometry."""
    render_setup = json.dumps({
        "render_product_path": "/Render/Products/rp1",
        "output_file_pattern": "$HIP/render/shot.$F4.exr",
        "camera_prim": "/cameras/cam1",
        "material_count": 3,
        "light_count": 2,
        "geo_prim_count": 0,
        "resolution": [1920, 1080],
        "has_motion_blur": False,
        "has_displacement": False,
    }, sort_keys=True)

    handler = _make_handler(
        render_setup_json=render_setup,
        stage_info={"prim_count": 0, "status": "ok"},
    )
    predictor = RenderPredictor(handler)
    plan = _make_plan()

    prediction = await predictor.predict(plan)
    assert any("geometry" in issue.lower() for issue in prediction.pre_render_issues)


@pytest.mark.asyncio
async def test_predict_handler_failure_non_blocking():
    """Predict should not crash if handler calls fail."""
    handler = AsyncMock()
    handler.call = AsyncMock(side_effect=RuntimeError("connection lost"))

    predictor = RenderPredictor(handler)
    plan = _make_plan()

    # Should not raise
    prediction = await predictor.predict(plan)
    assert isinstance(prediction, RenderPrediction)
    assert len(prediction.pre_render_issues) > 0


@pytest.mark.asyncio
async def test_predict_with_validator_results():
    """Predict should incorporate pre-flight check failures."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)
    plan = _make_plan()

    validator_results = [
        PreFlightCheck(
            name="materials",
            description="Check material bindings",
            severity=CheckSeverity.SOFT_WARN,
            passed=False,
            message="2 geometry prims have no material binding",
        ),
    ]

    prediction = await predictor.predict(plan, validator_results)
    assert any("material" in issue.lower() for issue in prediction.pre_render_issues)


@pytest.mark.asyncio
async def test_predict_render_time_estimate():
    """Render time estimate should scale with scene complexity."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    plan_short = _make_plan(start=1, end=1)
    plan_long = _make_plan(start=1, end=48)

    pred_short = await predictor.predict(plan_short)
    pred_long = await predictor.predict(plan_long)

    # Longer sequence should have higher estimated time
    assert pred_long.estimated_render_time_seconds > pred_short.estimated_render_time_seconds


@pytest.mark.asyncio
async def test_predict_resolution():
    """Predict should capture render resolution from stage."""
    render_setup = json.dumps({
        "render_product_path": "/Render/Products/rp1",
        "output_file_pattern": "$HIP/render/shot.$F4.exr",
        "camera_prim": "/cameras/cam1",
        "material_count": 1,
        "light_count": 1,
        "geo_prim_count": 5,
        "resolution": [3840, 2160],
        "has_motion_blur": True,
        "has_displacement": True,
    }, sort_keys=True)

    handler = _make_handler(render_setup_json=render_setup)
    predictor = RenderPredictor(handler)
    plan = _make_plan()

    prediction = await predictor.predict(plan)
    assert prediction.expected_resolution == (3840, 2160)
    assert prediction.has_motion_blur is True
    assert prediction.has_displacement is True


# =============================================================================
# VERIFY TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_verify_success():
    """Verify should pass when prediction matches reality."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    prediction = RenderPrediction(
        render_product_path="/Render/Products/rp1",
        output_file_pattern="$HIP/render/shot.$F4.exr",
        expected_frame_range=(1, 3),
        camera_prim="/cameras/cam1",
        material_count=3,
        light_count=2,
        geo_prim_count=15,
        render_succeeded=True,
    )

    # Create temp files to simulate render output
    with tempfile.TemporaryDirectory() as tmpdir:
        files = []
        for i in range(1, 4):
            fpath = os.path.join(tmpdir, f"frame.{i:04d}.exr")
            with open(fpath, "wb") as f:
                f.write(b"x" * 2048)  # Above threshold
            files.append(fpath)
        prediction.actual_output_files = files

        evaluation = _make_evaluation(passed=True, score=0.9, num_frames=3)
        result = await predictor.verify(prediction, evaluation)

    assert isinstance(result, VerificationResult)
    assert result.score > 0.7
    assert not result.should_rerender
    assert len(result.discrepancies) == 0


@pytest.mark.asyncio
async def test_verify_missing_files():
    """Verify should flag missing output files."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    prediction = RenderPrediction(
        expected_frame_range=(1, 5),
        render_succeeded=True,
        actual_output_files=["/nonexistent/frame.0001.exr", "/nonexistent/frame.0002.exr"],
    )

    result = await predictor.verify(prediction, None)
    assert any("missing" in d.lower() for d in result.discrepancies)


@pytest.mark.asyncio
async def test_verify_small_files():
    """Verify should flag suspiciously small output files."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    with tempfile.TemporaryDirectory() as tmpdir:
        fpath = os.path.join(tmpdir, "frame.0001.exr")
        with open(fpath, "wb") as f:
            f.write(b"x" * 10)  # Very small

        prediction = RenderPrediction(
            expected_frame_range=(1, 1),
            render_succeeded=True,
            actual_output_files=[fpath],
        )

        result = await predictor.verify(prediction, None)
        assert any("small" in d.lower() for d in result.discrepancies)


@pytest.mark.asyncio
async def test_verify_frame_count_mismatch():
    """Verify should flag when fewer files than expected frames."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    with tempfile.TemporaryDirectory() as tmpdir:
        files = []
        for i in range(1, 4):
            fpath = os.path.join(tmpdir, f"frame.{i:04d}.exr")
            with open(fpath, "wb") as f:
                f.write(b"x" * 2048)
            files.append(fpath)

        prediction = RenderPrediction(
            expected_frame_range=(1, 10),  # Expected 10
            render_succeeded=True,
            actual_output_files=files,  # Only got 3
        )

        result = await predictor.verify(prediction, None)
        assert any("expected" in d.lower() and "10" in d for d in result.discrepancies)


@pytest.mark.asyncio
async def test_verify_failed_render():
    """Verify should flag render failure."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    prediction = RenderPrediction(
        expected_frame_range=(1, 5),
        render_succeeded=False,
        actual_output_files=[],
    )

    result = await predictor.verify(prediction, None)
    assert any("not succeed" in d.lower() for d in result.discrepancies)
    assert result.score < 0.5


@pytest.mark.asyncio
async def test_verify_evaluation_failure():
    """Verify should flag evaluation quality failure."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    prediction = RenderPrediction(
        expected_frame_range=(1, 5),
        render_succeeded=True,
        actual_output_files=[],
    )

    evaluation = _make_evaluation(passed=False, score=0.3, num_frames=5, failed_frames=[2, 4])
    result = await predictor.verify(prediction, evaluation)
    assert any("quality" in d.lower() for d in result.discrepancies)


@pytest.mark.asyncio
async def test_verify_critical_frames():
    """Verify should flag frames with critical issues (black, NaN)."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    prediction = RenderPrediction(
        expected_frame_range=(1, 3),
        render_succeeded=True,
    )

    # Create evaluation with a NaN frame
    frame_evals = [
        FrameEvaluation(frame=1, output_path="/tmp/f1.exr", passed=True),
        FrameEvaluation(
            frame=2, output_path="/tmp/f2.exr", passed=False,
            issues=["Found 500 NaN pixel value(s). Shader issue."],
        ),
        FrameEvaluation(frame=3, output_path="/tmp/f3.exr", passed=True),
    ]
    evaluation = SequenceEvaluation(
        frame_evaluations=frame_evals,
        overall_score=0.5,
        passed=False,
    )

    result = await predictor.verify(prediction, evaluation)
    assert any("critical" in d.lower() for d in result.discrepancies)


@pytest.mark.asyncio
async def test_verify_pre_render_issues_materialized():
    """Pre-render warnings should become discrepancies if render failed."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    prediction = RenderPrediction(
        expected_frame_range=(1, 1),
        render_succeeded=False,
        pre_render_issues=["No lights found -- render may produce a black frame"],
    )

    result = await predictor.verify(prediction, None)
    assert any("pre-render" in d.lower() for d in result.discrepancies)


@pytest.mark.asyncio
async def test_verify_score_threshold():
    """Should_rerender should be True when score < threshold."""
    handler = _make_handler()
    predictor = RenderPredictor(handler, discrepancy_rerender_threshold=0.8)

    prediction = RenderPrediction(
        expected_frame_range=(1, 5),
        render_succeeded=False,
    )

    result = await predictor.verify(prediction, None)
    assert result.should_rerender is True
    assert result.score < 0.8


# =============================================================================
# REPLAN BENEFIT TESTS
# =============================================================================


def test_replan_benefit_already_passing():
    """Replan benefit should be 0 for already-passing evaluation."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    evaluation = _make_evaluation(passed=True, score=0.9)
    benefit = predictor.predict_replan_benefit(evaluation, {"pixel_samples": 128})
    assert benefit == 0.0


def test_replan_benefit_fireflies():
    """Increasing pixel samples should help with fireflies."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    frame_evals = [
        FrameEvaluation(
            frame=1, output_path="/tmp/f1.exr", passed=False,
            issues=["Detected 50 firefly pixel(s)"],
        ),
    ]
    evaluation = SequenceEvaluation(
        frame_evaluations=frame_evals,
        overall_score=0.5,
        passed=False,
    )

    benefit = predictor.predict_replan_benefit(evaluation, {"pixel_samples": 128})
    assert benefit > 0.2


def test_replan_benefit_black_frame_not_fixable():
    """Black frames are setup issues, rerender should not help much."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    frame_evals = [
        FrameEvaluation(
            frame=1, output_path="/tmp/f1.exr", passed=False,
            issues=["Black frame detected: 98% near-black pixels"],
        ),
    ]
    evaluation = SequenceEvaluation(
        frame_evaluations=frame_evals,
        overall_score=0.2,
        passed=False,
    )

    benefit = predictor.predict_replan_benefit(evaluation, {"pixel_samples": 128})
    assert benefit == 0.0  # Negative clamped to 0


def test_replan_benefit_clipping():
    """Exposure compensation should help with clipping."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    frame_evals = [
        FrameEvaluation(
            frame=1, output_path="/tmp/f1.exr", passed=False,
            issues=["Clipping detected: 10% pure white pixels"],
        ),
    ]
    evaluation = SequenceEvaluation(
        frame_evaluations=frame_evals,
        overall_score=0.5,
        passed=False,
    )

    benefit = predictor.predict_replan_benefit(
        evaluation, {"exposure_compensation": -0.5}
    )
    assert benefit > 0.2


def test_replan_benefit_no_relevant_adjustments():
    """No benefit if adjustments don't address the actual issues."""
    handler = _make_handler()
    predictor = RenderPredictor(handler)

    frame_evals = [
        FrameEvaluation(
            frame=1, output_path="/tmp/f1.exr", passed=False,
            issues=["Detected 50 firefly pixel(s)"],
        ),
    ]
    evaluation = SequenceEvaluation(
        frame_evaluations=frame_evals,
        overall_score=0.5,
        passed=False,
    )

    # exposure_compensation doesn't help fireflies
    benefit = predictor.predict_replan_benefit(
        evaluation, {"exposure_compensation": -0.5}
    )
    assert benefit == 0.0


# =============================================================================
# DRIVER INTEGRATION TESTS (predictor wired into driver)
# =============================================================================


@pytest.mark.asyncio
async def test_driver_with_predictor():
    """AutonomousDriver should use predictor when provided."""
    from synapse.autonomy.planner import RenderPlanner
    from synapse.autonomy.validator import PreFlightValidator
    from synapse.autonomy.evaluator import RenderEvaluator
    from synapse.autonomy.driver import AutonomousDriver

    # Build handler that satisfies both predictor AND validator
    render_setup = json.dumps({
        "render_product_path": "/Render/Products/rp1",
        "output_file_pattern": "$HIP/render/shot.$F4.exr",
        "camera_prim": "/cameras/render_cam",
        "material_count": 3,
        "light_count": 2,
        "geo_prim_count": 15,
        "resolution": [1920, 1080],
        "has_motion_blur": False,
        "has_displacement": False,
    }, sort_keys=True)

    async def enhanced_call(tool_name, params):
        if tool_name == "get_stage_info":
            return {
                "prim_count": 42,
                "cameras": ["/cameras/render_cam"],
                "renderable_prims": 15,
                "materials": 3,
                "status": "ok",
            }
        if tool_name == "get_scene_info":
            return {"camera": "/cameras/render_cam", "fps": 24}
        if tool_name == "execute_python":
            return {"output": render_setup}
        if tool_name == "render_sequence":
            return {
                "status": "ok",
                "frames": [{"frame": 1, "output_path": "/tmp/f1.exr"}],
            }
        if tool_name == "validate_frame":
            return {"status": "ok", "valid": True}
        if tool_name == "render_settings":
            return {"status": "ok"}
        return {"status": "ok"}

    handler = AsyncMock()
    handler.call = AsyncMock(side_effect=enhanced_call)

    planner = RenderPlanner()
    validator = PreFlightValidator(handler)
    evaluator = RenderEvaluator()
    predictor = RenderPredictor(handler)

    driver = AutonomousDriver(
        planner=planner,
        validator=validator,
        evaluator=evaluator,
        handler_interface=handler,
        predictor=predictor,
        max_iterations=1,
    )

    report = await driver.execute("render frame 1")

    # Report should include prediction
    assert report.prediction is not None
    assert report.prediction.camera_prim == "/cameras/render_cam"

    # Decision log should include prediction and verification entries
    contexts = [d.context for d in report.decisions]
    assert "prediction" in contexts


@pytest.mark.asyncio
async def test_driver_without_predictor():
    """AutonomousDriver should work fine without a predictor (backwards compat)."""
    from synapse.autonomy.planner import RenderPlanner
    from synapse.autonomy.validator import PreFlightValidator
    from synapse.autonomy.evaluator import RenderEvaluator
    from synapse.autonomy.driver import AutonomousDriver

    handler = _make_handler()

    async def simple_call(tool_name, params):
        if tool_name == "render_sequence":
            return {"status": "ok", "frames": []}
        if tool_name == "validate_frame":
            return {"status": "ok"}
        return {"status": "ok"}

    handler.call = AsyncMock(side_effect=simple_call)

    planner = RenderPlanner()
    validator = PreFlightValidator(handler)
    evaluator = RenderEvaluator()

    driver = AutonomousDriver(
        planner=planner,
        validator=validator,
        evaluator=evaluator,
        handler_interface=handler,
        max_iterations=1,
    )

    report = await driver.execute("render frame 1")

    # No prediction or verification
    assert report.prediction is None
    assert report.verification is None
