"""Tests for the network_explain handler.

Mock-based -- no Houdini required.
Verifies network traversal, topological sort, pattern detection,
output formats, and handler registration.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load handlers without Houdini
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    _hdefereval = types.ModuleType("hdefereval")
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]

if not hasattr(_hdefereval, "executeDeferred"):
    _hdefereval.executeDeferred = lambda fn: fn()
if not hasattr(_hdefereval, "executeInMainThreadWithResult"):
    _hdefereval.executeInMainThreadWithResult = lambda fn: fn()

# Import handlers via importlib to bypass package __init__
_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _base / "core" / "protocol.py"),
    ("synapse.core.aliases", _base / "core" / "aliases.py"),
    ("synapse.server.handlers", _base / "server" / "handlers.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]
handlers_node_mod = sys.modules.get("synapse.server.handlers_node")
if handlers_node_mod is None:
    spec = importlib.util.spec_from_file_location(
        "synapse.server.handlers_node",
        _base / "server" / "handlers_node.py",
    )
    handlers_node_mod = importlib.util.module_from_spec(spec)
    sys.modules["synapse.server.handlers_node"] = handlers_node_mod
    spec.loader.exec_module(handlers_node_mod)

_handlers_hou = handlers_mod.hou


# ---------------------------------------------------------------------------
# Mock node builder helpers
# ---------------------------------------------------------------------------

def _make_mock_node(name, type_name, type_label=None, inputs=None, outputs=None,
                    children=None, parms=None, path_prefix="/obj/geo1"):
    """Create a mock Houdini node for testing."""
    node = MagicMock()
    node.name.return_value = name
    node.path.return_value = f"{path_prefix}/{name}"

    node_type = MagicMock()
    node_type.name.return_value = type_name
    node_type.description.return_value = type_label or type_name.title()
    node.type.return_value = node_type

    node.inputs.return_value = inputs or []
    node.outputs.return_value = outputs or []
    node.children.return_value = children or []
    node.parms.return_value = parms or []

    return node


def _make_mock_parm(name, current_value, default_value, expression=None):
    """Create a mock parameter with non-default detection support."""
    parm = MagicMock()
    parm.name.return_value = name
    parm.eval.return_value = current_value

    template = MagicMock()
    template.defaultValue.return_value = (default_value,)
    parm_type = MagicMock()
    parm_type.name.return_value = "Float"
    template.type.return_value = parm_type
    parm.parmTemplate.return_value = template

    if expression:
        parm.expression.return_value = expression
    else:
        parm.expression.side_effect = Exception("No expression")

    return parm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._session_id = "test"
    h._bridge = MagicMock()
    return h


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExplainSimpleChain:
    """test_explain_simple_chain -- 3 nodes in sequence, verify flow order and connections."""

    def test_explain_simple_chain(self, handler):
        node_a = _make_mock_node("grid1", "grid", "Grid")
        node_b = _make_mock_node("mountain1", "mountain", "Mountain", inputs=[node_a])
        node_c = _make_mock_node("null1", "null", "Null", inputs=[node_b])

        node_a.outputs.return_value = [node_b]
        node_b.outputs.return_value = [node_c]

        root = MagicMock()
        root.children.return_value = [node_a, node_b, node_c]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})

        assert result["status"] == "ok"
        assert result["node_count"] == 3
        # Grid has no inputs so should appear first in topo sort
        assert result["data_flow"][0]["node"] == "grid1"
        assert "mountain1" in result["data_flow"][0]["outputs_to"]


class TestExplainBranchingNetwork:
    """test_explain_branching_network -- node with 2 outputs, verify both branches captured."""

    def test_explain_branching_network(self, handler):
        node_a = _make_mock_node("grid1", "grid", "Grid")
        node_b = _make_mock_node("scatter1", "scatter", "Scatter", inputs=[node_a])
        node_c = _make_mock_node("mountain1", "mountain", "Mountain", inputs=[node_a])

        node_a.outputs.return_value = [node_b, node_c]

        root = MagicMock()
        root.children.return_value = [node_a, node_b, node_c]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})

        assert result["node_count"] == 3
        # Grid should be first (no inputs)
        assert result["data_flow"][0]["node"] == "grid1"
        assert len(result["data_flow"][0]["outputs_to"]) == 2


class TestExplainNestedSubnets:
    """test_explain_nested_subnets -- subnet with children, verify depth traversal."""

    def test_explain_nested_subnets(self, handler):
        inner_a = _make_mock_node("inner_null", "null", "Null",
                                  path_prefix="/obj/geo1/subnet1")
        subnet = _make_mock_node("subnet1", "subnet", "Subnetwork",
                                 children=[inner_a])
        node_a = _make_mock_node("grid1", "grid", "Grid")

        root = MagicMock()
        root.children.return_value = [node_a, subnet]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain(
                {"node": "/obj/geo1", "depth": 2}
            )

        # Should find grid1, subnet1, and inner_null (depth=2)
        assert result["node_count"] == 3
        node_names = [e["node"] for e in result["data_flow"]]
        assert "inner_null" in node_names


class TestExplainEmptyNetwork:
    """test_explain_empty_network -- no children, verify graceful handling."""

    def test_explain_empty_network(self, handler):
        root = MagicMock()
        root.children.return_value = []

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})

        assert result["status"] == "ok"
        assert result["node_count"] == 0
        assert result["data_flow"] == []
        assert result["complexity"] == "simple"


class TestExplainPatternDetectionScatter:
    """test_explain_pattern_detection_scatter -- scatter+copytopoints detected."""

    def test_pattern_scatter(self, handler):
        node_a = _make_mock_node("scatter1", "scatter", "Scatter")
        node_b = _make_mock_node("copy1", "copytopoints", "Copy to Points",
                                 inputs=[node_a])
        node_a.outputs.return_value = [node_b]

        root = MagicMock()
        root.children.return_value = [node_a, node_b]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})

        assert "scatter_workflow" in result["patterns_detected"]


class TestExplainPatternDetectionTerrain:
    """test_explain_pattern_detection_terrain -- heightfield nodes detected."""

    def test_pattern_terrain(self, handler):
        node_a = _make_mock_node("hf_noise", "heightfield_noise", "HeightField Noise")
        node_b = _make_mock_node("hf_erode", "heightfield_erode", "HeightField Erode",
                                 inputs=[node_a])
        node_a.outputs.return_value = [node_b]

        root = MagicMock()
        root.children.return_value = [node_a, node_b]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})

        assert "terrain_generation" in result["patterns_detected"]


class TestExplainNonDefaultParamsOnly:
    """test_explain_non_default_params_only -- verify default params excluded."""

    def test_non_default_params(self, handler):
        parm_changed = _make_mock_parm("rows", 50, 10)
        parm_default = _make_mock_parm("cols", 10, 10)

        node_a = _make_mock_node("grid1", "grid", "Grid",
                                 parms=[parm_changed, parm_default])

        root = MagicMock()
        root.children.return_value = [node_a]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain(
                {"node": "/obj/geo1", "include_parameters": True}
            )

        key_params = result["data_flow"][0]["key_params"]
        assert "rows" in key_params
        assert key_params["rows"] == 50
        assert "cols" not in key_params


class TestExplainSuggestedHdaInterface:
    """test_explain_suggested_hda_interface -- verify suggestions generated for non-default parms."""

    def test_suggested_hda_interface(self, handler):
        parm_changed = _make_mock_parm("npts", 1000, 100)
        node_a = _make_mock_node("scatter1", "scatter", "Scatter",
                                 parms=[parm_changed])

        root = MagicMock()
        root.children.return_value = [node_a]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})

        suggestions = result["suggested_hda_interface"]
        assert len(suggestions) >= 1
        assert suggestions[0]["node"] == "scatter1"
        assert suggestions[0]["parm"] == "npts"


class TestExplainFormatProse:
    """test_explain_format_prose -- verify string output for prose format."""

    def test_format_prose(self, handler):
        node_a = _make_mock_node("grid1", "grid", "Grid")

        root = MagicMock()
        root.children.return_value = [node_a]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain(
                {"node": "/obj/geo1", "format": "prose"}
            )

        assert result["format"] == "prose"
        assert isinstance(result["text"], str)
        assert "grid1" in result["text"].lower() or "Grid" in result["text"]


class TestExplainFormatHelpCard:
    """test_explain_format_help_card -- verify wiki markup output."""

    def test_format_help_card(self, handler):
        node_a = _make_mock_node("grid1", "grid", "Grid")

        root = MagicMock()
        root.children.return_value = [node_a]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain(
                {"node": "/obj/geo1", "format": "help_card"}
            )

        assert result["format"] == "help_card"
        assert "= Network Overview =" in result["text"]
        assert "== Data Flow ==" in result["text"]


class TestExplainDepthLimit:
    """test_explain_depth_limit -- depth=1 doesn't recurse into subnets."""

    def test_depth_limit(self, handler):
        inner = _make_mock_node("inner_null", "null", "Null",
                                path_prefix="/obj/geo1/subnet1")
        subnet = _make_mock_node("subnet1", "subnet", "Subnetwork",
                                 children=[inner])
        node_a = _make_mock_node("grid1", "grid", "Grid")

        root = MagicMock()
        root.children.return_value = [node_a, subnet]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain(
                {"node": "/obj/geo1", "depth": 1}
            )

        # depth=1 means only direct children, no recurse into subnet
        assert result["node_count"] == 2
        node_names = [e["node"] for e in result["data_flow"]]
        assert "inner_null" not in node_names


class TestExplainDetailLevelSummary:
    """test_explain_detail_level_summary -- summary mode returns fewer details."""

    def test_detail_summary(self, handler):
        parm = _make_mock_parm("rows", 50, 10)
        node_a = _make_mock_node("grid1", "grid", "Grid", parms=[parm])

        root = MagicMock()
        root.children.return_value = [node_a]

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain(
                {"node": "/obj/geo1", "detail_level": "summary"}
            )

        # Summary mode should NOT include key_params
        assert "key_params" not in result["data_flow"][0]


class TestExplainRegisteredInHandlers:
    """test_explain_registered_in_handlers -- handler exists in registry."""

    def test_registered(self, handler):
        assert handler._registry.has("network_explain")


class TestExplainComplexityRating:
    """test_explain_complexity_rating -- verify simple/moderate/complex thresholds."""

    def test_complexity_simple(self, handler):
        nodes = [_make_mock_node(f"n{i}", "null", "Null") for i in range(3)]
        root = MagicMock()
        root.children.return_value = nodes

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})
        assert result["complexity"] == "simple"

    def test_complexity_moderate(self, handler):
        nodes = [_make_mock_node(f"n{i}", "null", "Null") for i in range(10)]
        root = MagicMock()
        root.children.return_value = nodes

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})
        assert result["complexity"] == "moderate"

    def test_complexity_complex(self, handler):
        nodes = [_make_mock_node(f"n{i}", "null", "Null") for i in range(20)]
        root = MagicMock()
        root.children.return_value = nodes

        with patch.object(_handlers_hou, "node", return_value=root):
            result = handler._handle_network_explain({"node": "/obj/geo1"})
        assert result["complexity"] == "complex"
