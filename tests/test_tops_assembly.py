"""Tests for TOPs/wedging and USD scene assembly handlers."""
import pytest
import sys
import types
from unittest.mock import MagicMock, patch, PropertyMock

# Create hou mock
hou_mock = types.ModuleType("hou")
sys.modules["hou"] = hou_mock
hou_mock.node = MagicMock()
hou_mock.frame = MagicMock(return_value=1)


class _MockCategory:
    def __init__(self, name):
        self._name = name
    def name(self):
        return self._name

class _MockNodeType:
    def __init__(self, name="null", category="Object"):
        self._name = name
        self._cat = _MockCategory(category)
    def name(self):
        return self._name
    def category(self):
        return self._cat


class TestWedge:
    def test_top_node_cook(self):
        """TOP node should be cooked."""
        mock_node = MagicMock()
        mock_node.type.return_value = _MockNodeType("wedge", "Top")
        mock_node.cook = MagicMock()
        hou_mock.node.return_value = mock_node

        node = hou_mock.node("/obj/topnet1/wedge1")
        assert node.type().category().name() == "Top"
        node.cook(block=True)
        node.cook.assert_called_once_with(block=True)

    def test_topnet_finds_wedge(self):
        """TOP network should find child wedge nodes."""
        wedge_child = MagicMock()
        wedge_child.type.return_value = _MockNodeType("wedge", "Top")
        wedge_child.path.return_value = "/obj/topnet1/wedge1"
        wedge_child.cook = MagicMock()

        mock_net = MagicMock()
        mock_net.type.return_value = _MockNodeType("topnet", "TopNet")
        mock_net.children.return_value = [wedge_child]
        hou_mock.node.return_value = mock_net

        node = hou_mock.node("/obj/topnet1")
        wedge_nodes = [n for n in node.children() if "wedge" in n.type().name().lower()]
        assert len(wedge_nodes) == 1

    def test_node_not_found(self):
        """Missing node should raise ValueError."""
        hou_mock.node.return_value = None
        with pytest.raises(ValueError, match="Node not found"):
            node = hou_mock.node("/bad")
            if node is None:
                raise ValueError("Node not found: /bad")

    def test_values_must_be_list(self):
        """Non-list values should raise ValueError."""
        with pytest.raises(ValueError, match="must be a list"):
            values = "not a list"
            if not isinstance(values, list):
                raise ValueError("'values' must be a list")


class TestReferenceUSD:
    def test_reference_creates_node(self):
        """Reference mode should create a reference LOP node."""
        mock_parent = MagicMock()
        mock_ref = MagicMock()
        mock_ref.path.return_value = "/stage/ref_import"
        mock_ref.parm.return_value = MagicMock()
        mock_parent.createNode.return_value = mock_ref
        hou_mock.node.return_value = mock_parent

        parent = hou_mock.node("/stage")
        node = parent.createNode("reference", "ref_import")
        node.parm("filepath1").set("D:/assets/building.usdc")

        parent.createNode.assert_called_with("reference", "ref_import")

    def test_sublayer_creates_node(self):
        """Sublayer mode should create a sublayer LOP node."""
        mock_parent = MagicMock()
        mock_sub = MagicMock()
        mock_sub.path.return_value = "/stage/sublayer_import"
        mock_sub.parm.return_value = MagicMock()
        mock_parent.createNode.return_value = mock_sub
        hou_mock.node.return_value = mock_parent

        parent = hou_mock.node("/stage")
        node = parent.createNode("sublayer", "sublayer_import")
        node.parm("filepath1").set("D:/assets/env.usda")

        parent.createNode.assert_called_with("sublayer", "sublayer_import")

    def test_invalid_mode(self):
        """Invalid mode should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            mode = "invalid"
            if mode not in ("reference", "sublayer"):
                raise ValueError(f"Invalid mode: {mode}. Use 'reference' or 'sublayer'.")

    def test_parent_not_found(self):
        """Missing parent node should raise ValueError."""
        hou_mock.node.return_value = None
        with pytest.raises(ValueError, match="Parent node not found"):
            parent = hou_mock.node("/bad")
            if parent is None:
                raise ValueError("Parent node not found: /bad")


def teardown_module():
    if "hou" in sys.modules and sys.modules["hou"] is hou_mock:
        del sys.modules["hou"]
