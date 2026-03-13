"""Tests for R10 Solaris viewport sync in LosslessEvolution.

After memory evolution, LOP nodes referencing the evolved USD should
be force-cooked. In standalone mode (no hou), this is a no-op.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from shared.evolution import LosslessEvolution, _HOU_AVAILABLE


class TestViewportSyncStandalone:
    """Standalone mode -- no hou available."""

    def test_standalone_noop_no_error(self):
        """Without Houdini, _sync_solaris_viewport should silently no-op."""
        evo = LosslessEvolution()
        if not _HOU_AVAILABLE:
            # Should not raise any exception
            evo._sync_solaris_viewport("/tmp/memory.usd")

    def test_standalone_empty_path(self):
        """Empty path should not cause errors."""
        evo = LosslessEvolution()
        if not _HOU_AVAILABLE:
            evo._sync_solaris_viewport("")

    def test_standalone_arbitrary_path(self):
        """Any path is fine in standalone mode."""
        evo = LosslessEvolution()
        if not _HOU_AVAILABLE:
            evo._sync_solaris_viewport("/nonexistent/memory.usd")


class TestViewportSyncInterface:
    """Method existence and signature."""

    def test_method_exists(self):
        evo = LosslessEvolution()
        assert hasattr(evo, "_sync_solaris_viewport")

    def test_method_is_callable(self):
        evo = LosslessEvolution()
        assert callable(evo._sync_solaris_viewport)

    def test_returns_none(self):
        """The method should return None (void)."""
        evo = LosslessEvolution()
        result = evo._sync_solaris_viewport("/tmp/test.usd")
        assert result is None


class TestViewportSyncPatched:
    """Patched hou scenarios."""

    def test_exception_in_hou_node_is_caught(self):
        """Exceptions in hou.node('/') should be caught gracefully."""
        mock_hou = MagicMock()
        mock_hou.node.side_effect = RuntimeError("hou broken")
        mock_hou.LopNetwork = type("LopNetwork", (), {})

        with patch("shared.evolution._HOU_AVAILABLE", True), \
             patch("shared.evolution.hou", mock_hou):
            evo = LosslessEvolution()
            # Should not raise
            evo._sync_solaris_viewport("/tmp/memory.usd")

    def test_no_lop_networks_no_error(self):
        """Scene with no LOP networks -- nothing to sync."""
        mock_hou = MagicMock()
        mock_hou.LopNetwork = type("LopNetwork", (), {})
        root = MagicMock()
        root.children.return_value = []
        mock_hou.node.return_value = root

        with patch("shared.evolution._HOU_AVAILABLE", True), \
             patch("shared.evolution.hou", mock_hou):
            evo = LosslessEvolution()
            evo._sync_solaris_viewport("/tmp/memory.usd")
            # No crash = success
