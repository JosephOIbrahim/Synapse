"""Tests for vertical layout helpers and materiallibrary auto-populate.

Covers:
- _layout_vertical_chain: linear node positioning
- _layout_dag_vertical: DAG layered node positioning
- materiallibrary auto-populate in _handle_create_node
"""

import sys
import types
from unittest.mock import MagicMock, patch, call

import pytest


# ── Bootstrap hou stub ──────────────────────────────────────────────
# Must run before importing handler_helpers which checks _HOU_AVAILABLE.

if "hou" not in sys.modules:
    _mock_hou = types.ModuleType("hou")
    sys.modules["hou"] = _mock_hou
else:
    _mock_hou = sys.modules["hou"]


class _MockVector2:
    """Minimal hou.Vector2 stand-in that records (x, y)."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def __eq__(self, other):
        if isinstance(other, _MockVector2):
            return abs(self.x - other.x) < 1e-6 and abs(self.y - other.y) < 1e-6
        return NotImplemented

    def __repr__(self):
        return f"Vector2({self.x:.3f}, {self.y:.3f})"


_mock_hou.Vector2 = _MockVector2

# Ensure handler_helpers sees _HOU_AVAILABLE = True
import importlib
from synapse.server import handler_helpers

handler_helpers._HOU_AVAILABLE = True
handler_helpers.hou = _mock_hou

from synapse.server.handler_helpers import (
    _layout_vertical_chain,
    _layout_dag_vertical,
    VERTICAL_SPACING,
    HORIZONTAL_SPACING,
)


# ── Layout Helper Fixtures ─────────────────────────────────────────


def _make_mock_node(name: str):
    """Create a mock hou.Node with setPosition tracking."""
    node = MagicMock()
    node.name.return_value = name
    node._pos = None

    def _set_pos(vec):
        node._pos = vec

    node.setPosition = MagicMock(side_effect=_set_pos)
    return node


# ── Vertical Chain Tests ───────────────────────────────────────────


class TestLayoutVerticalChain:
    """Test _layout_vertical_chain positions nodes in a single column."""

    def test_empty_list(self):
        """Empty list should not raise."""
        _layout_vertical_chain([])

    def test_single_node(self):
        """Single node placed at start position."""
        n = _make_mock_node("A")
        _layout_vertical_chain([n], start_x=5.0, start_y=10.0)
        n.setPosition.assert_called_once()
        pos = n.setPosition.call_args[0][0]
        assert abs(pos.x - 5.0) < 1e-6
        assert abs(pos.y - 10.0) < 1e-6

    def test_three_nodes_default_spacing(self):
        """Three nodes spaced at VERTICAL_SPACING intervals."""
        nodes = [_make_mock_node(c) for c in "ABC"]
        _layout_vertical_chain(nodes)
        for i, n in enumerate(nodes):
            pos = n.setPosition.call_args[0][0]
            assert abs(pos.x - 0.0) < 1e-6, f"Node {i} X should be 0"
            expected_y = -i * VERTICAL_SPACING
            assert abs(pos.y - expected_y) < 1e-6, f"Node {i} Y expected {expected_y}"

    def test_custom_start_and_spacing(self):
        """Custom start position and spacing."""
        nodes = [_make_mock_node(c) for c in "AB"]
        _layout_vertical_chain(nodes, start_x=3.0, start_y=5.0, spacing=2.0)
        # First node at (3, 5)
        pos0 = nodes[0].setPosition.call_args[0][0]
        assert abs(pos0.x - 3.0) < 1e-6
        assert abs(pos0.y - 5.0) < 1e-6
        # Second node at (3, 3)
        pos1 = nodes[1].setPosition.call_args[0][0]
        assert abs(pos1.x - 3.0) < 1e-6
        assert abs(pos1.y - 3.0) < 1e-6

    def test_solaris_chain_order(self):
        """Simulates the reference image: componentgeometry → ... → usd_rop."""
        names = [
            "componentgeometry1", "materiallibrary1", "componentoutput1",
            "camera1", "domelight1", "rendersettings1", "usd_rop1",
        ]
        nodes = [_make_mock_node(n) for n in names]
        _layout_vertical_chain(nodes)

        # All on same X column
        xs = [n.setPosition.call_args[0][0].x for n in nodes]
        assert all(abs(x - 0.0) < 1e-6 for x in xs)

        # Y decreasing top to bottom
        ys = [n.setPosition.call_args[0][0].y for n in nodes]
        for i in range(len(ys) - 1):
            assert ys[i] > ys[i + 1], f"Node {i} should be above node {i+1}"


# ── DAG Layout Tests ──────────────────────────────────────────────


class TestLayoutDagVertical:
    """Test _layout_dag_vertical positions DAG nodes in depth layers."""

    def test_empty(self):
        """Empty DAG should not raise."""
        _layout_dag_vertical([], [], {})

    def test_linear_chain_as_dag(self):
        """A linear chain should produce single-column layout."""
        ids = ["A", "B", "C"]
        conns = [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}]
        nodes = {nid: _make_mock_node(nid) for nid in ids}
        _layout_dag_vertical(ids, conns, nodes)

        # All on same X
        xs = [nodes[nid].setPosition.call_args[0][0].x for nid in ids]
        assert all(abs(x - 0.0) < 1e-6 for x in xs)

        # Y decreasing
        ys = [nodes[nid].setPosition.call_args[0][0].y for nid in ids]
        assert ys[0] > ys[1] > ys[2]

    def test_merge_topology(self):
        """Two roots merging into one node — roots should be on same layer."""
        ids = ["A", "B", "merge"]
        conns = [
            {"from": "A", "to": "merge", "input": 0},
            {"from": "B", "to": "merge", "input": 1},
        ]
        nodes = {nid: _make_mock_node(nid) for nid in ids}
        _layout_dag_vertical(ids, conns, nodes)

        # A and B should be at same Y (depth 0)
        ya = nodes["A"].setPosition.call_args[0][0].y
        yb = nodes["B"].setPosition.call_args[0][0].y
        assert abs(ya - yb) < 1e-6, "Roots should be at same depth"

        # merge should be below
        ym = nodes["merge"].setPosition.call_args[0][0].y
        assert ym < ya, "Merge node should be below roots"

        # A and B should be horizontally spread
        xa = nodes["A"].setPosition.call_args[0][0].x
        xb = nodes["B"].setPosition.call_args[0][0].x
        assert abs(xa - xb) > 1.0, "Roots should be horizontally spread"

    def test_multi_asset_merge_to_render(self):
        """Simulates multi_asset_merge template: 3 assets → merge → render tail."""
        ids = ["asset_A", "asset_B", "asset_C", "merge", "matlib", "karma", "rop"]
        conns = [
            {"from": "asset_A", "to": "merge", "input": 0},
            {"from": "asset_B", "to": "merge", "input": 1},
            {"from": "asset_C", "to": "merge", "input": 2},
            {"from": "merge", "to": "matlib"},
            {"from": "matlib", "to": "karma"},
            {"from": "karma", "to": "rop"},
        ]
        nodes = {nid: _make_mock_node(nid) for nid in ids}
        _layout_dag_vertical(ids, conns, nodes)

        # Assets at depth 0 (same Y, horizontally spread)
        asset_ys = [nodes[n].setPosition.call_args[0][0].y for n in ["asset_A", "asset_B", "asset_C"]]
        assert abs(asset_ys[0] - asset_ys[1]) < 1e-6
        assert abs(asset_ys[1] - asset_ys[2]) < 1e-6

        # merge at depth 1
        y_merge = nodes["merge"].setPosition.call_args[0][0].y
        assert y_merge < asset_ys[0]

        # Render tail below merge, each deeper
        y_matlib = nodes["matlib"].setPosition.call_args[0][0].y
        y_karma = nodes["karma"].setPosition.call_args[0][0].y
        y_rop = nodes["rop"].setPosition.call_args[0][0].y
        assert y_matlib < y_merge
        assert y_karma < y_matlib
        assert y_rop < y_karma

        # Render tail nodes centered (single per layer)
        x_merge = nodes["merge"].setPosition.call_args[0][0].x
        x_matlib = nodes["matlib"].setPosition.call_args[0][0].x
        assert abs(x_merge - 0.0) < 1e-6, "Single nodes should center on X=0"
        assert abs(x_matlib - 0.0) < 1e-6

    def test_diamond_topology(self):
        """A → B,C → D — diamond should not cross connections."""
        ids = ["A", "B", "C", "D"]
        conns = [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "C"},
            {"from": "B", "to": "D"},
            {"from": "C", "to": "D"},
        ]
        nodes = {nid: _make_mock_node(nid) for nid in ids}
        _layout_dag_vertical(ids, conns, nodes)

        ya = nodes["A"].setPosition.call_args[0][0].y
        yb = nodes["B"].setPosition.call_args[0][0].y
        yc = nodes["C"].setPosition.call_args[0][0].y
        yd = nodes["D"].setPosition.call_args[0][0].y

        # A at top, B/C at middle, D at bottom
        assert abs(yb - yc) < 1e-6, "B and C should be at same depth"
        assert ya > yb, "A should be above B"
        assert yb > yd, "B should be above D"


# ── MaterialLibrary Auto-Populate Tests ────────────────────────────


class TestMaterialLibraryAutoPopulate:
    """Test that create_node('materiallibrary') auto-scaffolds MaterialX."""

    @pytest.fixture
    def mock_env(self):
        """Set up mock hou environment for handler testing."""
        # Stub hdefereval for synchronous execution
        if "hdefereval" not in sys.modules:
            hde = types.ModuleType("hdefereval")
            hde.executeInMainThreadWithResult = lambda fn: fn()
            hde.executeDeferred = lambda fn: fn()
            sys.modules["hdefereval"] = hde

        # Ensure run_on_main is synchronous
        from synapse.server import main_thread
        main_thread._HOU_AVAILABLE = True
        main_thread._USE_DEFERRED = False
        return _mock_hou

    def _make_parent_node(self):
        """Create a mock parent node that returns mock children."""
        parent = MagicMock()
        shader_node = MagicMock()
        shader_node.path.return_value = "/stage/matlib1/matlib1_shader"
        uv_node = MagicMock()
        uv_node.path.return_value = "/stage/matlib1/uv_reader"
        uv_node.parm.return_value = MagicMock()

        new_node = MagicMock()
        new_node.name.return_value = "matlib1"
        new_node.path.return_value = "/stage/matlib1"
        new_node.type.return_value.name.return_value = "materiallibrary"

        def _create_child(node_type, name=None):
            if "mtlxstandard" in node_type:
                return shader_node
            if "mtlxgeompropvalue" in node_type:
                return uv_node
            return MagicMock()

        new_node.createNode = MagicMock(side_effect=_create_child)
        new_node.layoutChildren = MagicMock()
        new_node.cook = MagicMock()

        parent.createNode.return_value = new_node
        return parent, new_node, shader_node, uv_node

    def test_materiallibrary_creates_shader(self, mock_env):
        """Creating a materiallibrary should auto-create mtlxstandard_surface."""
        from synapse.server.handlers_node import NodeHandlerMixin

        parent, matlib, shader, uv = self._make_parent_node()

        with patch.object(_mock_hou, "node", create=True, return_value=parent):
            handler = type("H", (NodeHandlerMixin,), {
                "_get_bridge": lambda self: MagicMock(get_session=lambda sid: None),
                "_session_id": None,
            })()
            result = handler._handle_create_node({
                "parent": "/stage",
                "type": "materiallibrary",
                "name": "matlib1",
            })

        assert result["materialx_ready"] is True
        assert result["shader_path"] == "/stage/matlib1/matlib1_shader"
        assert result["shader_type"] == "mtlxstandard_surface"
        assert result["uv_reader_path"] == "/stage/matlib1/uv_reader"

        # Verify the shader was created inside the matlib
        matlib.createNode.assert_any_call("mtlxstandard_surface", "matlib1_shader")
        matlib.createNode.assert_any_call("mtlxgeompropvalue", "uv_reader")

    def test_non_materiallibrary_no_auto_populate(self, mock_env):
        """Creating a non-materiallibrary node should NOT auto-populate."""
        from synapse.server.handlers_node import NodeHandlerMixin

        new_node = MagicMock()
        new_node.name.return_value = "cam1"
        new_node.path.return_value = "/stage/cam1"

        parent = MagicMock()
        parent.createNode.return_value = new_node

        with patch.object(_mock_hou, "node", create=True, return_value=parent):
            handler = type("H", (NodeHandlerMixin,), {
                "_get_bridge": lambda self: MagicMock(get_session=lambda sid: None),
                "_session_id": None,
            })()
            result = handler._handle_create_node({
                "parent": "/stage",
                "type": "camera",
                "name": "cam1",
            })

        assert "materialx_ready" not in result
        assert "shader_path" not in result
        # No createNode calls on the child node itself
        new_node.createNode.assert_not_called()

    def test_materiallibrary_uv_reader_configured(self, mock_env):
        """UV reader should be set to vector2 signature and 'st' geomprop."""
        from synapse.server.handlers_node import NodeHandlerMixin

        parent, matlib, shader, uv = self._make_parent_node()

        with patch.object(_mock_hou, "node", create=True, return_value=parent):
            handler = type("H", (NodeHandlerMixin,), {
                "_get_bridge": lambda self: MagicMock(get_session=lambda sid: None),
                "_session_id": None,
            })()
            handler._handle_create_node({
                "parent": "/stage",
                "type": "materiallibrary",
            })

        # Check UV reader parm calls
        uv.parm.assert_any_call("signature")
        uv.parm.assert_any_call("geomprop")
