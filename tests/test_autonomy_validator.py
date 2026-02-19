"""
Synapse Autonomy Pipeline — Validator Tests

Tests for synapse.autonomy.validator.PreFlightValidator.
Run without Houdini:
    python -m pytest tests/test_autonomy_validator.py -v
"""

import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.autonomy.models import (
    CheckSeverity,
    GateLevel,
    RenderPlan,
    RenderStep,
    PreFlightCheck,
)
from synapse.autonomy.validator import PreFlightValidator


# =============================================================================
# HELPERS
# =============================================================================


def _make_handler(**overrides):
    """Create a mock handler interface.

    The validator calls get_stage_info, get_scene_info, and render_settings.
    Default responses represent a fully valid scene.
    """
    defaults = {
        "get_stage_info": {
            "status": "ok",
            "cameras": ["/cameras/cam1"],
            "prim_count": 50,
            "renderable_prims": 50,
            "materials": ["/materials/mat1"],
            "unassigned_material_prims": [],
            "unresolved_references": [],
        },
        "get_scene_info": {
            "status": "ok",
            "frame_start": 1,
            "frame_end": 48,
            "fps": 24,
        },
        "render_settings": {
            "status": "ok",
            "pixel_samples": 64,
            "resolution_x": 1920,
            "output_path": "/tmp/render/output.$F4.exr",
        },
    }
    defaults.update(overrides)

    handler = AsyncMock()

    async def _call(tool_name, params=None):
        return defaults.get(tool_name, {"status": "ok"})

    handler.call = _call
    return handler


def _make_plan(**overrides):
    """Create a minimal RenderPlan for validation."""
    plan_defaults = {
        "intent": "render frame 1",
        "steps": [
            RenderStep(handler="render_settings", params={"samples": 64}, description="Settings"),
            RenderStep(handler="render_sequence", params={"start_frame": 1, "end_frame": 1},
                       description="Render"),
        ],
        "estimated_frames": 1,
    }
    plan_defaults.update(overrides)
    return RenderPlan(**plan_defaults)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def valid_handler():
    return _make_handler()


@pytest.fixture
def validator(valid_handler):
    return PreFlightValidator(valid_handler)


@pytest.fixture
def plan():
    return _make_plan()


# =============================================================================
# VALIDATION TESTS
# =============================================================================


class TestPreFlightValidation:
    """Tests for PreFlightValidator.validate()."""

    @pytest.mark.asyncio
    async def test_valid_scene_passes(self, validator, plan):
        """A fully valid scene should pass all checks."""
        checks = await validator.validate(plan)
        assert isinstance(checks, list)
        assert len(checks) > 0
        hard_fails = [c for c in checks if c.severity == CheckSeverity.HARD_FAIL and not c.passed]
        assert len(hard_fails) == 0, f"Unexpected hard fails: {[c.name + ': ' + c.message for c in hard_fails]}"

    @pytest.mark.asyncio
    async def test_missing_camera_hard_fails(self, plan):
        """Missing camera triggers a hard fail."""
        handler = _make_handler(**{
            "get_stage_info": {
                "cameras": [],
                "prim_count": 10,
                "renderable_prims": 10,
                "unassigned_material_prims": [],
                "unresolved_references": [],
            },
        })
        validator = PreFlightValidator(handler)
        checks = await validator.validate(plan)
        camera_checks = [c for c in checks if c.name == "camera"]
        assert len(camera_checks) == 1
        assert camera_checks[0].passed is False
        assert camera_checks[0].severity == CheckSeverity.HARD_FAIL

    @pytest.mark.asyncio
    async def test_missing_renderable_prims_hard_fails(self, plan):
        """No renderable prims triggers a hard fail."""
        handler = _make_handler(**{
            "get_stage_info": {
                "cameras": ["/cam/cam1"],
                "prim_count": 0,
                "renderable_prims": 0,
                "unassigned_material_prims": [],
                "unresolved_references": [],
            },
        })
        validator = PreFlightValidator(handler)
        checks = await validator.validate(plan)
        prim_checks = [c for c in checks if c.name == "renderable_prims"]
        assert len(prim_checks) == 1
        assert prim_checks[0].passed is False
        assert prim_checks[0].severity == CheckSeverity.HARD_FAIL

    @pytest.mark.asyncio
    async def test_missing_materials_soft_warns(self, plan):
        """Unassigned materials triggers a soft warning, not a hard fail."""
        handler = _make_handler(**{
            "get_stage_info": {
                "cameras": ["/cam/cam1"],
                "prim_count": 10,
                "renderable_prims": 10,
                "unassigned_material_prims": ["/geo/shape1", "/geo/shape2"],
                "unresolved_references": [],
            },
        })
        validator = PreFlightValidator(handler)
        checks = await validator.validate(plan)
        mat_checks = [c for c in checks if c.name == "materials"]
        assert len(mat_checks) == 1
        assert mat_checks[0].passed is False
        assert mat_checks[0].severity == CheckSeverity.SOFT_WARN

    @pytest.mark.asyncio
    async def test_low_samples_soft_warns(self, plan):
        """Low pixel samples triggers a soft warning."""
        handler = _make_handler(**{
            "render_settings": {
                "pixel_samples": 2,
                "resolution_x": 1920,
                "output_path": "/tmp/out.$F4.exr",
            },
        })
        validator = PreFlightValidator(handler)
        checks = await validator.validate(plan)
        settings_checks = [c for c in checks if c.name == "render_settings"]
        assert len(settings_checks) == 1
        assert settings_checks[0].passed is False
        assert settings_checks[0].severity == CheckSeverity.SOFT_WARN

    @pytest.mark.asyncio
    async def test_invalid_frame_range_hard_fails(self, plan):
        """Frame range start > end triggers hard fail via planner params."""
        bad_plan = _make_plan(
            steps=[
                RenderStep(
                    handler="render_sequence",
                    params={"start_frame": 100, "end_frame": 1},
                    description="Bad range",
                ),
            ],
        )
        handler = _make_handler(**{
            "get_scene_info": {
                "frame_start": 1,
                "frame_end": 48,
            },
        })
        validator = PreFlightValidator(handler)
        checks = await validator.validate(bad_plan)
        range_checks = [c for c in checks if c.name == "frame_range"]
        assert len(range_checks) == 1
        assert range_checks[0].passed is False

    @pytest.mark.asyncio
    async def test_zero_frames_hard_fails(self):
        """Estimated frames = 0 triggers hard fail."""
        plan = _make_plan(estimated_frames=0)
        handler = _make_handler()
        validator = PreFlightValidator(handler)
        checks = await validator.validate(plan)
        range_checks = [c for c in checks if c.name == "frame_range"]
        assert len(range_checks) == 1
        assert range_checks[0].passed is False
        assert range_checks[0].severity == CheckSeverity.HARD_FAIL

    @pytest.mark.asyncio
    async def test_output_path_missing_warns(self, plan):
        """Missing output path triggers a warning."""
        handler = _make_handler(**{
            "render_settings": {
                "pixel_samples": 64,
                "resolution_x": 1920,
                "output_path": "",
                "picture": "",
            },
        })
        validator = PreFlightValidator(handler)
        checks = await validator.validate(plan)
        path_checks = [c for c in checks if c.name == "output_path"]
        assert len(path_checks) == 1
        assert path_checks[0].passed is False
        assert path_checks[0].severity == CheckSeverity.SOFT_WARN

    @pytest.mark.asyncio
    async def test_solaris_ordering_clean(self, validator, plan):
        """Solaris ordering check passes as INFO when no ambiguities detected."""
        checks = await validator.validate(plan)
        ordering_checks = [c for c in checks if c.name == "solaris_ordering"]
        assert len(ordering_checks) == 1
        assert ordering_checks[0].severity == CheckSeverity.INFO
        assert ordering_checks[0].passed is True

    @pytest.mark.asyncio
    async def test_missing_assets_warns(self, plan):
        """Unresolved asset references triggers a warning."""
        handler = _make_handler(**{
            "get_stage_info": {
                "cameras": ["/cam/cam1"],
                "prim_count": 10,
                "renderable_prims": 10,
                "unassigned_material_prims": [],
                "unresolved_references": ["/textures/missing.exr"],
            },
        })
        validator = PreFlightValidator(handler)
        checks = await validator.validate(plan)
        asset_checks = [c for c in checks if c.name == "missing_assets"]
        assert len(asset_checks) == 1
        assert asset_checks[0].passed is False
        assert asset_checks[0].severity == CheckSeverity.SOFT_WARN

    @pytest.mark.asyncio
    async def test_multiple_hard_fails(self, plan):
        """Multiple hard failures are all reported (no short-circuit)."""
        handler = _make_handler(**{
            "get_stage_info": {
                "cameras": [],
                "prim_count": 0,
                "renderable_prims": 0,
                "unassigned_material_prims": [],
                "unresolved_references": [],
            },
        })
        zero_plan = _make_plan(estimated_frames=0)
        validator = PreFlightValidator(handler)
        checks = await validator.validate(zero_plan)
        hard_fails = [c for c in checks if c.severity == CheckSeverity.HARD_FAIL and not c.passed]
        assert len(hard_fails) >= 2, f"Expected at least 2 hard fails, got {len(hard_fails)}: {[c.name for c in hard_fails]}"

    @pytest.mark.asyncio
    async def test_all_checks_run(self, validator, plan):
        """All 8 check categories are executed (no short-circuiting)."""
        checks = await validator.validate(plan)
        assert len(checks) == 8, f"Expected 8 checks, got {len(checks)}: {[c.name for c in checks]}"
        expected_names = {
            "camera", "renderable_prims", "materials", "render_settings",
            "frame_range", "output_path", "solaris_ordering", "missing_assets",
        }
        actual_names = {c.name for c in checks}
        assert actual_names == expected_names
