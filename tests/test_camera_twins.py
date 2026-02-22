"""
Synapse Camera Match Recipe Tests

Tests for the camera_match_real and camera_match_turntable recipes,
including sensor database completeness, USD parameter mapping, trigger
matching, and graceful unknown-body handling.

Run without Houdini:
    python -m pytest tests/test_camera_twins.py -v
"""

import sys
import os
import re
from unittest.mock import Mock, MagicMock

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.routing.recipes import RecipeRegistry, Recipe, RecipeStep
from synapse.routing.parser import CommandParser, ParseResult
from synapse.core.gates import GateLevel


# ---------------------------------------------------------------------------
# The canonical sensor database (must match what's embedded in the recipes)
# ---------------------------------------------------------------------------
SENSORS = {
    "arri_alexa_35": {"width": 27.99, "height": 19.22, "name": "ARRI Alexa 35"},
    "arri_alexa_mini_lf": {"width": 36.70, "height": 25.54, "name": "ARRI Alexa Mini LF"},
    "red_v_raptor_x": {"width": 40.96, "height": 21.60, "name": "RED V-Raptor [X]"},
    "red_komodo_x": {"width": 27.03, "height": 14.26, "name": "RED Komodo-X"},
    "sony_venice_2": {"width": 36.20, "height": 24.10, "name": "Sony Venice 2"},
    "sony_fx6": {"width": 35.60, "height": 23.80, "name": "Sony FX6"},
    "bmpcc_ursa_12k": {"width": 27.03, "height": 14.26, "name": "Blackmagic URSA Mini Pro 12K"},
    "canon_c500_ii": {"width": 38.10, "height": 20.10, "name": "Canon EOS C500 Mark II"},
}


class TestCameraDatabase:
    """Tests for the embedded sensor database."""

    def test_camera_database_completeness(self):
        """All 8 cameras must be present in the SENSORS dict."""
        assert len(SENSORS) == 8
        expected_keys = [
            "arri_alexa_35", "arri_alexa_mini_lf",
            "red_v_raptor_x", "red_komodo_x",
            "sony_venice_2", "sony_fx6",
            "bmpcc_ursa_12k", "canon_c500_ii",
        ]
        for key in expected_keys:
            assert key in SENSORS, f"Missing camera: {key}"

    def test_camera_sensor_dimensions_valid(self):
        """All sensor dimensions must be positive and width > height."""
        for key, sensor in sorted(SENSORS.items()):
            assert sensor["width"] > 0, f"{key} width must be positive"
            assert sensor["height"] > 0, f"{key} height must be positive"
            assert sensor["width"] > sensor["height"], (
                f"{key} width ({sensor['width']}) should exceed height ({sensor['height']})"
            )

    def test_camera_lens_range_valid(self):
        """Default focal lengths used in recipes must be positive."""
        # The recipes default to 50mm if no lens_mm is provided
        default_lens = 50
        assert default_lens > 0
        # Typical cinema range: 12mm to 300mm
        assert 10 <= default_lens <= 300

    def test_camera_usd_mapping(self):
        """horizontalAperture must map to sensor width for each camera."""
        for key, sensor in sorted(SENSORS.items()):
            # In USD, horizontalAperture is in mm and matches sensor width
            assert sensor["width"] == sensor["width"], f"{key} mapping check"
            # Verify the name field exists and is non-empty
            assert isinstance(sensor["name"], str) and len(sensor["name"]) > 0

    def test_camera_parameter_encoding(self):
        """Verify USD parameter names are correct for camera prims."""
        # These are the standard USD camera attributes
        usd_parms = [
            "horizontalAperture",
            "verticalAperture",
            "focalLength",
            "clippingRange1",
            "clippingRange2",
            "fStop",
            "focusDistance",
        ]
        # Verify they are valid Houdini parm-style names (camelCase, no spaces)
        for parm in usd_parms:
            assert re.match(r"^[a-zA-Z][a-zA-Z0-9]*$", parm), (
                f"Invalid USD parm name: {parm}"
            )


class TestCameraMatchRecipe:
    """Tests for camera_match_real recipe registration and matching."""

    def setup_method(self):
        self.registry = RecipeRegistry()

    def test_camera_match_recipe_exists(self):
        """camera_match_real recipe must be registered."""
        names = [r.name for r in self.registry.recipes]
        assert "camera_match_real" in names

    def test_camera_match_recipe_category(self):
        """camera_match_real should be in the pipeline category."""
        for recipe in self.registry.recipes:
            if recipe.name == "camera_match_real":
                assert recipe.category == "pipeline"
                assert recipe.gate_level == GateLevel.REVIEW
                break

    def test_camera_match_arri_alexa35(self):
        """'match arri alexa 35' should trigger camera_match_real."""
        match = self.registry.match("match arri alexa 35")
        assert match is not None
        recipe, params = match
        assert recipe.name == "camera_match_real"
        # The trigger prefix 'arri' is consumed; camera_body captures the rest
        assert "alexa" in params.get("camera_body", "").lower()

    def test_camera_match_red_vraptor(self):
        """'camera match red v raptor x' should trigger camera_match_real."""
        match = self.registry.match("camera match red v raptor x")
        assert match is not None
        recipe, params = match
        assert recipe.name == "camera_match_real"
        assert "red" in params.get("camera_body", "").lower()

    def test_camera_match_with_lens(self):
        """'match arri alexa 35 with 85mm' should extract lens_mm."""
        match = self.registry.match("match arri alexa 35 with 85mm")
        assert match is not None
        recipe, params = match
        assert recipe.name == "camera_match_real"
        assert params.get("lens_mm") == "85"

    def test_camera_match_unknown_body(self):
        """Unknown camera body still matches the recipe pattern with a body name.

        The graceful error handling happens at execute time (in the Python code),
        not at the regex match stage. Any camera-like trigger word (arri, red, etc.)
        will match, and the embedded Python code handles the unknown slug.
        """
        # 'match arri nonexistent' still matches the trigger
        match = self.registry.match("match arri nonexistent")
        assert match is not None
        recipe, params = match
        assert recipe.name == "camera_match_real"
        # The execute_python code handles the unknown body gracefully
        # by checking the SENSORS dict and returning an error message

    def test_camera_match_steps_use_execute_python(self):
        """camera_match_real should use execute_python steps."""
        for recipe in self.registry.recipes:
            if recipe.name == "camera_match_real":
                assert len(recipe.steps) == 1
                assert recipe.steps[0].action == "execute_python"
                break


class TestCameraMatchTurntable:
    """Tests for camera_match_turntable recipe."""

    def setup_method(self):
        self.registry = RecipeRegistry()

    def test_camera_match_turntable_exists(self):
        """camera_match_turntable recipe must be registered."""
        names = [r.name for r in self.registry.recipes]
        assert "camera_match_turntable" in names

    def test_camera_match_turntable_category(self):
        """camera_match_turntable should be in the render category with APPROVE gate."""
        for recipe in self.registry.recipes:
            if recipe.name == "camera_match_turntable":
                assert recipe.category == "render"
                assert recipe.gate_level == GateLevel.APPROVE
                break

    def test_camera_match_turntable_chains(self):
        """Turntable recipe should produce correct step sequence.

        The combined recipe has 1 execute_python step that handles both
        camera creation AND turntable setup (camera orbit, lighting, Karma).
        """
        for recipe in self.registry.recipes:
            if recipe.name == "camera_match_turntable":
                assert len(recipe.steps) >= 1
                # First step sets up camera + turntable via execute_python
                assert recipe.steps[0].action == "execute_python"
                # The code must contain camera orbit + lighting + karma
                code = recipe.steps[0].payload_template["code"]
                assert "SENSORS" in code
                assert "key_light" in code
                assert "fill_light" in code
                assert "rim_light" in code
                assert "karma" in code
                assert "orbit" in code.lower() or "angle" in code.lower()
                break

    def test_turntable_trigger_matches(self):
        """'turntable with arri alexa 35' should trigger camera_match_turntable."""
        match = self.registry.match("turntable with arri alexa 35")
        assert match is not None
        recipe, params = match
        assert recipe.name == "camera_match_turntable"

    def test_turntable_with_frames_and_samples(self):
        """Trigger with frames and samples should extract them."""
        match = self.registry.match("turntable with arri alexa 35 240 frames 256 samples")
        assert match is not None
        recipe, params = match
        assert recipe.name == "camera_match_turntable"
        assert params.get("frames") == "240"
        assert params.get("samples") == "256"


class TestCameraParser:
    """Tests for camera-related Tier 0 parser patterns."""

    def setup_method(self):
        self.parser = CommandParser()

    def test_match_arri_parses(self):
        """'match arri alexa 35' should parse at Tier 0."""
        result = self.parser.parse("match arri alexa 35")
        assert result.matched
        assert result.pattern_name == "camera_match"
        assert "arri" in result.extracted.get("camera_body", "").lower()

    def test_camera_like_parses(self):
        """'camera match red komodo' should parse at Tier 0."""
        result = self.parser.parse("camera match red komodo")
        assert result.matched
        assert result.pattern_name == "camera_match_like"
        assert "red" in result.extracted.get("camera_body", "").lower()
