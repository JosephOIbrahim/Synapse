"""
Synapse Introspection Tests

Tests for server/introspection.py and the execute_python dry_run/atomic
enhancements. Runs without Houdini by mocking the hou module.

    python -m pytest tests/test_introspection.py -v
"""

import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Mock hou before importing introspection
# ---------------------------------------------------------------------------

_mock_hou = ModuleType("hou")
_mock_hou.selectedNodes = MagicMock(return_value=[])
_mock_hou.node = MagicMock(return_value=None)
_mock_hou.undos = MagicMock()
sys.modules["hou"] = _mock_hou

import importlib.util

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
introspection_path = os.path.join(
    package_root, "python", "synapse", "server", "introspection.py"
)

spec = importlib.util.spec_from_file_location("introspection", introspection_path)
introspection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(introspection)


# ---------------------------------------------------------------------------
# Helpers to build mock nodes
# ---------------------------------------------------------------------------

def _make_type(name="null", category="Sop"):
    """Build a mock hou.NodeType."""
    t = MagicMock()
    t.name.return_value = name
    cat = MagicMock()
    cat.name.return_value = category
    t.category.return_value = cat
    t.definition.return_value = None
    return t


def _make_parm(name, value, default=None, label=None, folders=(), expression=None, keyframes=None, spare=False):
    """Build a mock hou.Parm."""
    p = MagicMock()
    p.name.return_value = name
    p.eval.return_value = value  # noqa: S307

    # containingFolders and isSpare live on the parm, not the template
    p.containingFolders.return_value = folders
    p.isSpare.return_value = spare

    tmpl = MagicMock()
    tmpl.label.return_value = label or name
    tmpl.defaultValue.return_value = (default,) if default is not None else (value,)
    p.parmTemplate.return_value = tmpl

    if expression:
        p.expression.return_value = expression
        p.expressionLanguage.return_value = "Hscript"
    else:
        p.expression.side_effect = Exception("no expression")

    if keyframes:
        p.keyframes.return_value = keyframes
    else:
        p.keyframes.return_value = []

    return p


def _make_conn(out_node_path, input_idx=0, output_idx=0):
    """Build a mock hou.NodeConnection (output connection)."""
    conn = MagicMock()
    out_node = MagicMock()
    out_node.path.return_value = out_node_path
    conn.outputNode.return_value = out_node
    conn.inputIndex.return_value = input_idx
    conn.outputIndex.return_value = output_idx
    return conn


def _make_node(path, node_type="null", category="Sop", parms=None, inputs=None,
               output_conns=None, warnings=None, errors=None, children=None,
               geometry=None, code_parm=None, sticky_notes=None):
    """Build a fully-configured mock hou.Node."""
    node = MagicMock()
    node.path.return_value = path
    node.name.return_value = path.rsplit("/", 1)[-1]
    node.type.return_value = _make_type(node_type, category)
    node.parms.return_value = parms or []
    node.inputs.return_value = inputs or []
    node.outputConnections.return_value = output_conns or []
    node.warnings.return_value = warnings or []
    node.errors.return_value = errors or []
    node.children.return_value = children or []
    node.stickyNotes.return_value = sticky_notes or []

    # Parm lookup for code extraction
    def _parm_lookup(name):
        if code_parm and name == code_parm[0]:
            cp = MagicMock()
            cp.eval.return_value = code_parm[1]  # noqa: S307
            return cp
        for p in (parms or []):
            if p.name() == name:
                return p
        return None
    node.parm = _parm_lookup

    if geometry is not None:
        node.geometry.return_value = geometry
    else:
        node.geometry.side_effect = Exception("no geometry")

    return node


def _make_geometry(points=10, prims=5, vertices=20):
    """Build a mock hou.Geometry."""
    geo = MagicMock()
    geo.points.return_value = [None] * points
    geo.prims.return_value = [None] * prims
    geo.vertices.return_value = [None] * vertices
    geo.pointAttribs.return_value = []
    geo.primAttribs.return_value = []
    geo.globalAttribs.return_value = []
    return geo


# ===========================================================================
# Tests: _node_basic
# ===========================================================================

class TestNodeBasic:
    def test_returns_path_type_name_category(self):
        node = _make_node("/obj/geo1/mountain1", "mountain", "Sop")
        result = introspection._node_basic(node)
        assert result == {
            "path": "/obj/geo1/mountain1",
            "name": "mountain1",
            "type": "mountain",
            "category": "Sop",
        }


# ===========================================================================
# Tests: _modified_parms
# ===========================================================================

class TestModifiedParms:
    def test_detects_changed_parm(self):
        node = _make_node("/obj/geo1/grid1", parms=[
            _make_parm("height", 0.5, default=0.0),
            _make_parm("rows", 10, default=10),  # unchanged
        ])
        result = introspection._modified_parms(node)
        assert "height" in result
        assert result["height"] == 0.5
        assert "rows" not in result

    def test_empty_when_all_defaults(self):
        node = _make_node("/obj/n", parms=[
            _make_parm("tx", 0.0, default=0.0),
        ])
        result = introspection._modified_parms(node)
        assert result == {}


# ===========================================================================
# Tests: _connections
# ===========================================================================

class TestConnections:
    def test_inputs_and_outputs(self):
        inp_node = _make_node("/obj/geo1/grid1")
        conn = _make_conn("/obj/geo1/merge1", input_idx=0, output_idx=0)
        node = _make_node("/obj/geo1/mountain1", inputs=[inp_node], output_conns=[conn])
        result = introspection._connections(node)
        assert result["inputs"] == [{"path": "/obj/geo1/grid1", "index": 0}]
        assert result["outputs"] == [{"path": "/obj/geo1/merge1", "input_index": 0, "output_index": 0}]

    def test_no_connections(self):
        node = _make_node("/obj/geo1/null1")
        result = introspection._connections(node)
        assert result == {"inputs": [], "outputs": []}

    def test_none_inputs_skipped(self):
        node = _make_node("/obj/geo1/merge1", inputs=[None, _make_node("/obj/geo1/grid1")])
        result = introspection._connections(node)
        assert len(result["inputs"]) == 1
        assert result["inputs"][0]["index"] == 1


# ===========================================================================
# Tests: _geometry_summary
# ===========================================================================

class TestGeometrySummary:
    def test_basic_counts(self):
        geo = _make_geometry(points=100, prims=50, vertices=200)
        node = _make_node("/obj/geo1/grid1", geometry=geo)
        result = introspection._geometry_summary(node)
        assert result is not None
        assert result["points"] == 100
        assert result["prims"] == 50
        assert result["vertices"] == 200

    def test_returns_none_when_no_geometry(self):
        node = _make_node("/obj/geo1", category="Object")
        result = introspection._geometry_summary(node)
        assert result is None

    def test_returns_none_when_geometry_is_none(self):
        node = MagicMock()
        node.geometry.return_value = None
        result = introspection._geometry_summary(node)
        assert result is None


# ===========================================================================
# Tests: _node_issues
# ===========================================================================

class TestNodeIssues:
    def test_warnings_and_errors(self):
        node = _make_node("/n", warnings=["slow cook"], errors=["missing input"])
        result = introspection._node_issues(node)
        assert result["warnings"] == ["slow cook"]
        assert result["errors"] == ["missing input"]

    def test_clean_node(self):
        node = _make_node("/n")
        result = introspection._node_issues(node)
        assert result == {"warnings": [], "errors": []}


# ===========================================================================
# Tests: _node_code
# ===========================================================================

class TestNodeCode:
    def test_wrangle_snippet(self):
        node = _make_node("/n", code_parm=("snippet", "@P.y += 1;"))
        result = introspection._node_code(node)
        assert result == "@P.y += 1;"

    def test_python_code(self):
        node = _make_node("/n", code_parm=("python", "print('hi')"))
        result = introspection._node_code(node)
        assert result == "print('hi')"

    def test_non_wrangle_returns_none(self):
        node = _make_node("/n")
        result = introspection._node_code(node)
        assert result is None

    def test_empty_code_returns_none(self):
        node = _make_node("/n", code_parm=("snippet", ""))
        result = introspection._node_code(node)
        assert result is None


# ===========================================================================
# Tests: _recurse_inputs
# ===========================================================================

class TestRecurseInputs:
    def test_depth_zero_returns_empty(self):
        node = _make_node("/n", inputs=[_make_node("/n/inp")])
        result = introspection._recurse_inputs(node, depth=0)
        assert result == []

    def test_depth_one(self):
        inp = _make_node("/obj/geo1/grid1", "grid", "Sop")
        node = _make_node("/obj/geo1/mountain1", inputs=[inp])
        result = introspection._recurse_inputs(node, depth=1)
        assert len(result) == 1
        assert result[0]["path"] == "/obj/geo1/grid1"
        assert result[0]["type"] == "grid"

    def test_depth_two(self):
        inp2 = _make_node("/obj/geo1/line1", "line", "Sop")
        inp1 = _make_node("/obj/geo1/grid1", "grid", "Sop", inputs=[inp2])
        node = _make_node("/obj/geo1/mountain1", inputs=[inp1])
        result = introspection._recurse_inputs(node, depth=2)
        assert len(result) == 1
        assert "inputs" in result[0]
        assert len(result[0]["inputs"]) == 1
        assert result[0]["inputs"][0]["path"] == "/obj/geo1/line1"


# ===========================================================================
# Tests: inspect_selection
# ===========================================================================

class TestInspectSelection:
    def test_empty_selection(self):
        _mock_hou.selectedNodes.return_value = []
        result = introspection.inspect_selection()
        assert result["count"] == 0
        assert result["nodes"] == []

    def test_single_node(self):
        node = _make_node("/obj/geo1/mountain1", "mountain", "Sop", geometry=_make_geometry())
        _mock_hou.selectedNodes.return_value = [node]
        result = introspection.inspect_selection(depth=0)
        assert result["count"] == 1
        assert result["nodes"][0]["path"] == "/obj/geo1/mountain1"
        assert "input_graph" not in result["nodes"][0]  # depth=0

    def test_with_depth(self):
        inp = _make_node("/obj/geo1/grid1", "grid", "Sop")
        node = _make_node("/obj/geo1/mountain1", "mountain", "Sop", inputs=[inp], geometry=_make_geometry())
        _mock_hou.selectedNodes.return_value = [node]
        result = introspection.inspect_selection(depth=1)
        assert "input_graph" in result["nodes"][0]
        assert len(result["nodes"][0]["input_graph"]) == 1

    def test_topology_edges(self):
        inp = _make_node("/obj/geo1/grid1", "grid", "Sop")
        node = _make_node("/obj/geo1/mountain1", "mountain", "Sop", inputs=[inp], geometry=_make_geometry())
        _mock_hou.selectedNodes.return_value = [node]
        result = introspection.inspect_selection()
        assert ["grid1", "mountain1", 0] in result["topology"]


# ===========================================================================
# Tests: inspect_scene
# ===========================================================================

class TestInspectScene:
    def test_root_not_found(self):
        _mock_hou.node.return_value = None
        with pytest.raises(ValueError, match="Couldn't find"):
            introspection.inspect_scene(root="/nonexistent")

    def test_basic_tree(self):
        child = _make_node("/obj/geo1", "geo", "Object")
        root = _make_node("/obj", "obj", "Manager", children=[child])
        _mock_hou.node.return_value = root
        result = introspection.inspect_scene(root="/obj", max_depth=2)
        assert result["overview"]["node_count"] >= 1
        assert len(result["network_tree"]) == 1

    def test_max_depth_limit(self):
        deep_child = _make_node("/obj/geo1/sub/deep", "null", "Sop")
        sub = _make_node("/obj/geo1/sub", "subnet", "Sop", children=[deep_child])
        geo = _make_node("/obj/geo1", "geo", "Object", children=[sub])
        root = _make_node("/obj", "obj", "Manager", children=[geo])
        _mock_hou.node.return_value = root
        # depth=1: root + direct children only
        result = introspection.inspect_scene(root="/obj", max_depth=1)
        tree = result["network_tree"][0]
        # Children of /obj should exist
        assert "children" in tree
        # But grandchildren should not exist (depth exceeded)
        for child in tree.get("children", []):
            assert "children" not in child or child["children"] == []

    def test_context_filter(self):
        sop_child = _make_node("/obj/geo1", "geo", "Sop")
        lop_child = _make_node("/stage/dome", "domlight", "Lop")
        root = _make_node("/", "root", "Manager", children=[sop_child, lop_child])
        _mock_hou.node.return_value = root
        result = introspection.inspect_scene(root="/", max_depth=2, context_filter="Sop")
        # Only Sop nodes counted
        assert result["overview"]["contexts"].get("Lop", 0) == 0

    def test_issues_collected(self):
        broken = _make_node("/obj/broken", "null", "Sop", errors=["Cook error"])
        root = _make_node("/obj", "obj", "Manager", children=[broken])
        _mock_hou.node.return_value = root
        result = introspection.inspect_scene(root="/obj", max_depth=2)
        assert len(result["issues"]) == 1
        assert result["issues"][0]["path"] == "/obj/broken"

    def test_sticky_notes(self):
        sticky = MagicMock()
        sticky.text.return_value = "Main character geo"
        child = _make_node("/obj/geo1", "geo", "Object", sticky_notes=[sticky])
        root = _make_node("/obj", "obj", "Manager", children=[child])
        _mock_hou.node.return_value = root
        result = introspection.inspect_scene(root="/obj", max_depth=2)
        assert len(result["artist_notes"]) == 1
        assert "Main character" in result["artist_notes"][0]["text"]


# ===========================================================================
# Tests: inspect_node_detail
# ===========================================================================

class TestInspectNodeDetail:
    def _setup_node(self, **kwargs):
        node = _make_node("/obj/geo1/wrangle1", "attribwrangle", "Sop", **kwargs)
        _mock_hou.node.return_value = node
        return node

    def test_node_not_found(self):
        _mock_hou.node.return_value = None
        with pytest.raises(ValueError, match="Couldn't find"):
            introspection.inspect_node_detail("/nonexistent")

    def test_full_dump(self):
        parms = [
            _make_parm("snippet", "@P.y += 1;", default="", label="VEXpression", folders=("Code",)),
            _make_parm("class", 1, default=0, label="Run Over"),
        ]
        self._setup_node(parms=parms, code_parm=("snippet", "@P.y += 1;"), geometry=_make_geometry())
        result = introspection.inspect_node_detail("/obj/geo1/wrangle1")
        assert result["type"] == "attribwrangle"
        assert "Code" in result["parameters"]
        assert result["code"] == "@P.y += 1;"
        assert result["geometry"] is not None

    def test_include_code_false(self):
        self._setup_node(code_parm=("snippet", "@P.y += 1;"))
        result = introspection.inspect_node_detail("/obj/geo1/wrangle1", include_code=False)
        assert "code" not in result

    def test_include_geometry_false(self):
        self._setup_node(geometry=_make_geometry())
        result = introspection.inspect_node_detail("/obj/geo1/wrangle1", include_geometry=False)
        assert "geometry" not in result

    def test_expressions_detected(self):
        parms = [
            _make_parm("tx", 5.0, default=0.0, expression="$F * 0.1"),
        ]
        self._setup_node(parms=parms)
        result = introspection.inspect_node_detail("/obj/geo1/wrangle1")
        assert len(result["expressions"]) == 1
        assert result["expressions"][0]["expression"] == "$F * 0.1"

    def test_include_expressions_false(self):
        parms = [
            _make_parm("tx", 5.0, default=0.0, expression="$F * 0.1"),
        ]
        self._setup_node(parms=parms)
        result = introspection.inspect_node_detail("/obj/geo1/wrangle1", include_expressions=False)
        # Expression info should not be collected
        assert len(result["expressions"]) == 0

    def test_keyframes_detected(self):
        kf = MagicMock()
        parms = [
            _make_parm("ty", 3.0, default=0.0, keyframes=[kf, kf]),
        ]
        self._setup_node(parms=parms)
        result = introspection.inspect_node_detail("/obj/geo1/wrangle1")
        assert len(result["keyframed_parms"]) == 1
        assert result["keyframed_parms"][0]["count"] == 2

    def test_spare_parms_detected(self):
        parms = [
            _make_parm("custom_attr", "test", default="", spare=True),
        ]
        self._setup_node(parms=parms)
        result = introspection.inspect_node_detail("/obj/geo1/wrangle1")
        assert "custom_attr" in result["spare_parms"]

    def test_hda_info(self):
        node = self._setup_node()
        defn = MagicMock()
        defn.libraryFilePath.return_value = "/opt/hfs/hda/SideFX.hda"
        defn.description.return_value = "Attribute Wrangle"
        defn.sections.return_value = {"Help": None, "DialogScript": None}
        node.type().definition.return_value = defn
        result = introspection.inspect_node_detail("/obj/geo1/wrangle1")
        assert result["hda"]["label"] == "Attribute Wrangle"
        assert "Help" in result["hda"]["sections"]


# ===========================================================================
# Tests: execute_python dry_run / atomic
# ===========================================================================

class TestExecutePythonEnhancements:
    """Test dry_run and atomic parameters on _handle_execute_python."""

    @pytest.fixture(autouse=True)
    def handler(self):
        import synapse.server.handlers as handlers_mod
        # Patch the hou reference that the handler module actually uses
        # (may differ from sys.modules["hou"] if other tests replaced it)
        self._handlers_hou = handlers_mod.hou
        # Ensure undos mock exists on the actual hou reference
        if not hasattr(self._handlers_hou, "undos") or not hasattr(self._handlers_hou.undos, "group"):
            self._handlers_hou.undos = MagicMock()
        self.h = handlers_mod.SynapseHandler()

    def test_dry_run_valid_code(self):
        result = self.h._handle_execute_python({
            "content": "x = 1 + 2",
            "dry_run": True,
        })
        assert result["valid"] is True
        assert result["dry_run"] is True

    def test_dry_run_invalid_syntax(self):
        result = self.h._handle_execute_python({
            "content": "def f(:",
            "dry_run": True,
        })
        assert result["valid"] is False
        assert result["dry_run"] is True
        assert "error" in result

    def test_dry_run_does_not_execute(self):
        """Verify that dry_run=True doesn't actually run the code."""
        result = self.h._handle_execute_python({
            "content": "result = 'should not run'",
            "dry_run": True,
        })
        # Should not have 'executed' key — just valid/dry_run
        assert "executed" not in result

    def test_atomic_false_skips_undo(self):
        """With atomic=False, hou.undos.group should not be called."""
        self._handlers_hou.undos.group.reset_mock()
        result = self.h._handle_execute_python({
            "content": "result = 42",
            "atomic": False,
        })
        assert result["executed"] is True
        self._handlers_hou.undos.group.assert_not_called()

    def test_atomic_true_uses_undo(self):
        """With atomic=True (default), hou.undos.group should be called."""
        self._handlers_hou.undos.group.reset_mock()
        result = self.h._handle_execute_python({
            "content": "result = 42",
            "atomic": True,
        })
        assert result["executed"] is True
        self._handlers_hou.undos.group.assert_called_once_with("synapse_execute")

    def test_default_is_atomic(self):
        """When atomic is not specified, it defaults to True."""
        self._handlers_hou.undos.group.reset_mock()
        result = self.h._handle_execute_python({
            "content": "result = 42",
        })
        assert result["executed"] is True
        self._handlers_hou.undos.group.assert_called_once()
