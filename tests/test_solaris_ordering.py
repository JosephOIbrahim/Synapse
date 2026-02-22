"""
Synapse — Solaris Ordering Validation Tests

Tests the solaris_validate_ordering pre-flight check that detects ambiguous
merge points in the LOP network. All mocked — no Houdini required.

Run:
    python -m pytest tests/test_solaris_ordering.py -v
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
    PreFlightCheck,
    RenderPlan,
    RenderStep,
)
from synapse.autonomy.validator import PreFlightValidator


# =============================================================================
# HELPERS — Mock handler_interface responses for solaris_validate_ordering
# =============================================================================


def _make_handler_interface(**overrides):
    """Build a mock handler_interface that returns canned data.

    By default every scene query returns a healthy scene, but individual
    tool responses can be overridden via keyword arguments:
        _make_handler_interface(
            solaris_validate_ordering={"clean": False, "issues": [...]},
        )
    """
    # Defaults for every tool the validator calls
    defaults = {
        "get_stage_info": {
            "cameras": ["/cameras/camera1"],
            "prim_count": 10,
            "renderable_prims": 5,
            "unassigned_material_prims": [],
            "unresolved_references": [],
        },
        "get_scene_info": {
            "frame_start": 1,
            "frame_end": 100,
        },
        "render_settings": {
            "pixel_samples": 64,
            "resolution_x": 1920,
            "output_path": "/tmp/renders/out.exr",
        },
        "solaris_validate_ordering": {
            "clean": True,
            "issues": [],
        },
    }
    defaults.update(overrides)

    async def _call(tool_name, params=None):
        if tool_name in defaults:
            return defaults[tool_name]
        return {"status": "ok"}

    interface = AsyncMock()
    interface.call = AsyncMock(side_effect=_call)
    return interface


def _make_plan(render_node=""):
    """Build a minimal RenderPlan used by the validator."""
    return RenderPlan(
        intent="render frame 1",
        steps=[
            RenderStep(
                handler="render_sequence",
                params={"start_frame": 1, "end_frame": 1, "render_node": render_node},
                description="Render frame 1",
            ),
        ],
        estimated_frames=1,
        gate_level=GateLevel.INFORM,
    )


# =============================================================================
# TESTS
# =============================================================================


class TestSolarisOrdering:
    """Tests for the _check_solaris_ordering pre-flight check."""

    @pytest.mark.asyncio
    async def test_clean_network(self):
        """Linear LOP chain with no multi-input nodes reports clean."""
        handler = _make_handler_interface(
            solaris_validate_ordering={"clean": True, "issues": []},
        )
        validator = PreFlightValidator(handler_interface=handler)
        plan = _make_plan()

        checks = await validator.validate(plan)
        ordering_check = [c for c in checks if c.name == "solaris_ordering"]

        assert len(ordering_check) == 1
        check = ordering_check[0]
        assert check.passed is True
        assert "No ordering ambiguities" in check.message

    @pytest.mark.asyncio
    async def test_ambiguous_merge(self):
        """Merge LOP with 3 unsorted inputs is flagged with issue details."""
        handler = _make_handler_interface(
            solaris_validate_ordering={
                "clean": False,
                "issues": [
                    {
                        "node": "/stage/merge1",
                        "type": "ambiguous_merge",
                        "input_count": 3,
                        "current_order": ["/stage/lighting", "/stage/materials", "/stage/geo"],
                        "suggested_fix": "Verify merge order matches intended layer strength",
                    },
                ],
            },
        )
        validator = PreFlightValidator(handler_interface=handler)
        plan = _make_plan()

        checks = await validator.validate(plan)
        ordering_check = [c for c in checks if c.name == "solaris_ordering"]

        assert len(ordering_check) == 1
        check = ordering_check[0]
        assert check.passed is False
        assert check.severity == CheckSeverity.SOFT_WARN
        assert "/stage/merge1" in check.message
        assert "ambiguous_merge" in check.message
        assert "Review merge order" in check.message

    @pytest.mark.asyncio
    async def test_explicit_order(self):
        """Merge with explicit ordering set is not flagged."""
        # When every merge node has explicit ordering, the handler returns clean
        handler = _make_handler_interface(
            solaris_validate_ordering={"clean": True, "issues": []},
        )
        validator = PreFlightValidator(handler_interface=handler)
        plan = _make_plan()

        checks = await validator.validate(plan)
        ordering_check = [c for c in checks if c.name == "solaris_ordering"]

        assert len(ordering_check) == 1
        check = ordering_check[0]
        assert check.passed is True

    @pytest.mark.asyncio
    async def test_no_render_node(self):
        """No render ROP found results in a graceful informational message."""
        # When the handler raises (e.g., can't find render node), the validator
        # catches the exception and returns a passing INFO check.
        async def _failing_call(tool_name, params=None):
            if tool_name == "solaris_validate_ordering":
                raise RuntimeError("Couldn't find a render node in the scene")
            # Other tools return healthy defaults
            defaults = {
                "get_stage_info": {
                    "cameras": ["/cameras/camera1"],
                    "prim_count": 10,
                    "renderable_prims": 5,
                    "unassigned_material_prims": [],
                    "unresolved_references": [],
                },
                "get_scene_info": {"frame_start": 1, "frame_end": 100},
                "render_settings": {
                    "pixel_samples": 64,
                    "resolution_x": 1920,
                    "output_path": "/tmp/renders/out.exr",
                },
            }
            return defaults.get(tool_name, {"status": "ok"})

        handler = AsyncMock()
        handler.call = AsyncMock(side_effect=_failing_call)
        validator = PreFlightValidator(handler_interface=handler)
        plan = _make_plan()

        checks = await validator.validate(plan)
        ordering_check = [c for c in checks if c.name == "solaris_ordering"]

        assert len(ordering_check) == 1
        check = ordering_check[0]
        # Exception path returns INFO severity and passed=True (graceful degradation)
        assert check.passed is True
        assert check.severity == CheckSeverity.INFO
        assert "Couldn't run ordering check" in check.message

    @pytest.mark.asyncio
    async def test_complex_network(self):
        """Branching and merging network reports all merge points."""
        handler = _make_handler_interface(
            solaris_validate_ordering={
                "clean": False,
                "issues": [
                    {
                        "node": "/stage/merge1",
                        "type": "ambiguous_merge",
                        "input_count": 2,
                        "current_order": ["/stage/geo_a", "/stage/geo_b"],
                        "suggested_fix": "Verify merge order matches intended layer strength",
                    },
                    {
                        "node": "/stage/sublayer1",
                        "type": "ambiguous_sublayer",
                        "input_count": 3,
                        "current_order": ["/stage/base", "/stage/override_a", "/stage/override_b"],
                        "suggested_fix": "Check sublayer opinion strength ordering",
                    },
                ],
            },
        )
        validator = PreFlightValidator(handler_interface=handler)
        plan = _make_plan()

        checks = await validator.validate(plan)
        ordering_check = [c for c in checks if c.name == "solaris_ordering"]

        assert len(ordering_check) == 1
        check = ordering_check[0]
        assert check.passed is False
        # Both merge points should be mentioned
        assert "/stage/merge1" in check.message
        assert "/stage/sublayer1" in check.message
        assert "ambiguous_merge" in check.message
        assert "ambiguous_sublayer" in check.message
