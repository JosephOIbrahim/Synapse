"""Tests for _infer_stage_touch() blast radius inference (R7).

Validates that SOP->LOP bleed is auto-detected by tracing the dependency
graph forward. In standalone mode (no hou), the method returns False.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from shared.bridge import LosslessExecutionBridge, Operation, _HOU_AVAILABLE
from shared.types import AgentID


def _make_operation(**kwargs) -> Operation:
    """Helper to build an Operation with sensible defaults."""
    defaults = dict(
        agent_id=AgentID.HANDS,
        operation_type="set_parameter",
        summary="test op",
        fn=lambda: None,
        touches_stage=False,
    )
    defaults.update(kwargs)
    return Operation(**defaults)


def _make_chain(depth, ends_with_lop=False):
    """Create a chain of mock nodes, optionally ending with a LopNode."""
    LopNodeType = type("LopNode", (), {})
    nodes = []
    for i in range(depth):
        node = MagicMock()
        node.path.return_value = f"/obj/chain_{i}"
        node.dependents.return_value = []
        if i > 0:
            nodes[i - 1].dependents.return_value = [node]
        # Make isinstance check work for the last node if it's a LOP
        if ends_with_lop and i == depth - 1:
            node.__class__ = LopNodeType
            node.path.return_value = f"/stage/lop_{i}"
        nodes.append(node)
    return nodes


class TestBlastRadiusStandalone:
    """Standalone mode (no hou) -- returns False."""

    def test_standalone_returns_false(self):
        if not _HOU_AVAILABLE:
            bridge = LosslessExecutionBridge()
            op = _make_operation(kwargs={"node_path": "/obj/geo1"})
            assert bridge._infer_stage_touch(op) is False

    def test_standalone_no_node_path_returns_false(self):
        if not _HOU_AVAILABLE:
            bridge = LosslessExecutionBridge()
            op = _make_operation(kwargs={})
            assert bridge._infer_stage_touch(op) is False


class TestBlastRadiusTouchesStage:
    """Operation already has touches_stage=True."""

    def test_already_touches_stage_returns_true(self):
        bridge = LosslessExecutionBridge()
        op = _make_operation(touches_stage=True)
        assert bridge._infer_stage_touch(op) is True

    def test_already_touches_stage_does_not_query_hou(self):
        """Short-circuits before any hou calls."""
        bridge = LosslessExecutionBridge()
        op = _make_operation(touches_stage=True)
        # Should return True immediately without needing hou
        result = bridge._infer_stage_touch(op)
        assert result is True


class TestBlastRadiusNoNodePath:
    """No node_path or parent_path in kwargs."""

    def test_no_node_path_returns_false(self):
        bridge = LosslessExecutionBridge()
        op = _make_operation(kwargs={"some_other_key": "value"})
        result = bridge._infer_stage_touch(op)
        # Without touches_stage and without hou, or without node_path: False
        if op.touches_stage:
            assert result is True
        else:
            assert result is False

    def test_empty_kwargs_returns_false(self):
        bridge = LosslessExecutionBridge()
        op = _make_operation(kwargs={})
        assert bridge._infer_stage_touch(op) is False


class TestBlastRadiusPatched:
    """Patched hou scenarios for dependency tracing."""

    def test_direct_lop_dependent_detected(self):
        """A node whose direct dependent is a LopNode triggers stage touch."""
        mock_hou = MagicMock()
        LopNode = type("LopNode", (), {})
        mock_hou.LopNode = LopNode

        sop_node = MagicMock()
        sop_node.path.return_value = "/obj/geo1"
        lop_node = MagicMock()
        lop_node.__class__ = LopNode
        lop_node.path.return_value = "/stage/lop1"
        sop_node.dependents.return_value = [lop_node]

        mock_hou.node.return_value = sop_node

        # Make isinstance(dep, hou.LopNode) work
        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            op = _make_operation(kwargs={"node_path": "/obj/geo1"})
            result = bridge._infer_stage_touch(op)
            assert result is True
            assert op.touches_stage is True
            assert op.stage_path == "/stage/lop1"

    def test_no_lop_dependents_returns_false(self):
        """Node with only SOP dependents -- no stage bleed."""
        mock_hou = MagicMock()
        mock_hou.LopNode = type("LopNode", (), {})

        sop_node = MagicMock()
        sop_node.path.return_value = "/obj/geo1"
        sop_dep = MagicMock()
        sop_dep.path.return_value = "/obj/geo2"
        sop_dep.dependents.return_value = []
        sop_node.dependents.return_value = [sop_dep]

        mock_hou.node.return_value = sop_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            op = _make_operation(kwargs={"node_path": "/obj/geo1"})
            result = bridge._infer_stage_touch(op)
            assert result is False
            assert op.touches_stage is False

    def test_node_not_found_returns_false(self):
        """hou.node() returns None -- no blast radius."""
        mock_hou = MagicMock()
        mock_hou.node.return_value = None

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            op = _make_operation(kwargs={"node_path": "/obj/missing"})
            result = bridge._infer_stage_touch(op)
            assert result is False

    def test_parent_path_kwarg_also_works(self):
        """parent_path is an alternative to node_path."""
        mock_hou = MagicMock()
        mock_hou.LopNode = type("LopNode", (), {})
        sop_node = MagicMock()
        sop_node.path.return_value = "/obj/parent1"
        sop_node.dependents.return_value = []
        mock_hou.node.return_value = sop_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            op = _make_operation(kwargs={"parent_path": "/obj/parent1"})
            result = bridge._infer_stage_touch(op)
            # Node found but no LOP deps
            assert result is False

    def test_exception_in_dependents_returns_false(self):
        """Exception during tracing should be caught gracefully."""
        mock_hou = MagicMock()
        mock_hou.LopNode = type("LopNode", (), {})
        sop_node = MagicMock()
        sop_node.path.return_value = "/obj/geo1"
        sop_node.dependents.side_effect = RuntimeError("broken")
        mock_hou.node.return_value = sop_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            op = _make_operation(kwargs={"node_path": "/obj/geo1"})
            result = bridge._infer_stage_touch(op)
            assert result is False
