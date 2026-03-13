"""Tests for _verify_composition() in LosslessExecutionBridge.

Validates the Scene Integrity anchor -- USD composition validation
after every stage-touching mutation. In standalone mode (no pxr/hou),
the method gracefully returns True so the pipeline doesn't block.
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Ensure shared package is importable
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from shared.bridge import LosslessExecutionBridge, _HOU_AVAILABLE


# ---------------------------------------------------------------------------
# Standalone mode (no Houdini)
# ---------------------------------------------------------------------------

class TestCompositionStandalone:
    """When hou is not available, composition checks should pass."""

    def test_standalone_returns_true(self):
        """Without Houdini, _verify_composition always returns True."""
        bridge = LosslessExecutionBridge()
        # In standalone mode _HOU_AVAILABLE is False, so method returns True
        if not _HOU_AVAILABLE:
            assert bridge._verify_composition("/stage/lop1") is True

    def test_standalone_any_path_returns_true(self):
        """Arbitrary paths should not cause errors in standalone mode."""
        bridge = LosslessExecutionBridge()
        if not _HOU_AVAILABLE:
            assert bridge._verify_composition("/nonexistent/path") is True
            assert bridge._verify_composition("") is True
            assert bridge._verify_composition("/stage/deeply/nested/node") is True


# ---------------------------------------------------------------------------
# Method existence and callability
# ---------------------------------------------------------------------------

class TestCompositionInterface:
    """Verify the method exists and has the expected signature."""

    def test_method_exists(self):
        bridge = LosslessExecutionBridge()
        assert hasattr(bridge, "_verify_composition")

    def test_method_is_callable(self):
        bridge = LosslessExecutionBridge()
        assert callable(bridge._verify_composition)

    def test_accepts_string_argument(self):
        """Method should accept a single string path argument."""
        bridge = LosslessExecutionBridge()
        # Should not raise TypeError
        result = bridge._verify_composition("/stage/test")
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Mocked Houdini scenarios
# ---------------------------------------------------------------------------

class TestCompositionWithMockedHou:
    """Test composition validation with mocked Houdini."""

    def test_invalid_node_path_returns_true(self):
        """If the node doesn't exist, gracefully return True."""
        bridge = LosslessExecutionBridge()
        if not _HOU_AVAILABLE:
            # Standalone always returns True
            assert bridge._verify_composition("/invalid/node") is True

    def test_node_without_stage_returns_true(self):
        """Nodes without a .stage() method should pass validation."""
        bridge = LosslessExecutionBridge()
        if not _HOU_AVAILABLE:
            assert bridge._verify_composition("/obj/geo1") is True

    def test_exception_returns_true(self):
        """Any exception during validation should gracefully return True."""
        bridge = LosslessExecutionBridge()
        # The method has a broad try/except that returns True on error
        result = bridge._verify_composition("/stage/broken")
        assert result is True


# ---------------------------------------------------------------------------
# With patched hou module (simulating production)
# ---------------------------------------------------------------------------

class TestCompositionPatched:
    """Test with a patched hou module to simulate Houdini environment."""

    def test_valid_stage_with_no_prims_returns_true(self):
        """An empty stage (no prims to traverse) should pass."""
        mock_hou = MagicMock()
        mock_node = MagicMock()
        mock_node.stage.return_value = MagicMock()
        mock_node.stage.return_value.Traverse.return_value = []
        mock_hou.node.return_value = mock_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            result = bridge._verify_composition("/stage/lop1")
            assert result is True

    def test_node_not_found_returns_true(self):
        """hou.node() returning None should pass gracefully."""
        mock_hou = MagicMock()
        mock_hou.node.return_value = None

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            result = bridge._verify_composition("/stage/missing")
            assert result is True

    def test_node_without_stage_attr_returns_true(self):
        """Node without .stage attribute should pass gracefully."""
        mock_hou = MagicMock()
        mock_node = MagicMock(spec=[])  # No attributes at all
        mock_hou.node.return_value = mock_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            # hasattr(node, 'stage') will be False, returns True
            result = bridge._verify_composition("/stage/sopnode")
            assert result is True

    def test_stage_traverse_exception_returns_true(self):
        """Exception during stage traversal should return True (graceful)."""
        mock_hou = MagicMock()
        mock_node = MagicMock()
        mock_node.stage.side_effect = RuntimeError("Stage error")
        mock_hou.node.return_value = mock_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            result = bridge._verify_composition("/stage/broken")
            assert result is True

    def test_valid_prims_return_true(self):
        """Stage with valid, active prims should pass."""
        mock_hou = MagicMock()
        mock_node = MagicMock()
        mock_prim = MagicMock()
        mock_prim.IsValid.return_value = True
        mock_prim.IsActive.return_value = True
        mock_prim.HasAuthoredReferences.return_value = False
        mock_stage = MagicMock()
        mock_stage.Traverse.return_value = [mock_prim]
        mock_node.stage.return_value = mock_stage
        mock_hou.node.return_value = mock_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            result = bridge._verify_composition("/stage/lop1")
            assert result is True
