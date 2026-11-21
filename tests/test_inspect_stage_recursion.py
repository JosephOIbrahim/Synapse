"""R-018 — ``synapse_inspect_stage`` recursive walk and honesty stamps.

Executes the REAL extraction script the way the bridge does — split
globals/locals ``exec(code, G, L)`` with a fake ``hou`` module — against a
faithful fake node tree. No Houdini session is needed for these checks.

What is pinned here:

  - a /stage containing a subnet returns the subnet's inner nodes
    (recursive descent, not one network level)
  - a walk stopped by the depth cap says ``truncated: true`` and names the
    level reached (``max_depth`` / ``depth_reached`` / ``truncated_paths``)
  - a walk stopped by the node ceiling says so too
  - ``children`` / ``key_parms`` / ``provenance`` are populated from real
    reads, not hardcoded empty placeholders
  - the tool description matches what the walk does, in all three places
    it is declared (Inspector constants, cognitive schema, mcp_server)
  - the Python-side walk-limit constants match the limits compiled into
    the extraction script
"""

from __future__ import annotations

import ast
import io
import json
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

from synapse.inspector import (
    INSPECT_STAGE_TOOL_DESCRIPTION,
    MAX_KEY_PARMS,
    MAX_WALK_DEPTH,
    MAX_WALK_NODES,
    synapse_inspect_stage,
)
from synapse.inspector import tool_inspect_stage as inspector_tool
from synapse.inspector.models import SCHEMA_VERSION

from conftest import make_mock_transport


# -----------------------------------------------------------------------------
# A faithful-enough fake of the hou node API the extraction script reads.
# -----------------------------------------------------------------------------


class _ParmType:
    Int = "Int"
    Float = "Float"
    String = "String"
    Toggle = "Toggle"
    Menu = "Menu"
    Button = "Button"
    Folder = "Folder"
    Data = "Data"


class _ParmTemplate:
    def __init__(self, ptype):
        self._ptype = ptype

    def type(self):
        return self._ptype


class _Parm:
    def __init__(self, name, value, ptype=_ParmType.Float, at_default=False):
        self._name = name
        self._value = value
        self._ptype = ptype
        self._at_default = at_default

    def name(self):
        return self._name

    def eval(self):
        return self._value

    def isAtDefault(self):
        return self._at_default

    def parmTemplate(self):
        return _ParmTemplate(self._ptype)


class _NodeType:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _Attr:
    def __init__(self, name, value):
        self._name = name
        self._value = value

    def GetName(self):
        return self._name

    def Get(self):
        return self._value


class _Prim:
    def __init__(self, attrs=()):
        self._attrs = list(attrs)

    def IsValid(self):
        return True

    def GetAttributes(self):
        return tuple(self._attrs)


class _Stage:
    def __init__(self, prims=None):
        self._prims = dict(prims or {})

    def GetPrimAtPath(self, path):
        return self._prims.get(str(path))


class FakeNode:
    def __init__(
        self,
        path,
        node_type="sublayer",
        children=(),
        parms=(),
        errors=(),
        warnings=(),
        display=False,
        bypassed=False,
        prims=(),
        user_data=None,
        creator=None,
        stage=None,
    ):
        self._path = path
        self._node_type = node_type
        self._children = list(children)
        self._parms = list(parms)
        self._errors = list(errors)
        self._warnings = list(warnings)
        self._display = display
        self._bypassed = bypassed
        self._prims = list(prims)
        self._user_data = dict(user_data or {})
        self._creator = creator
        self._stage = stage
        self._inputs = []
        self._outputs = []

    def name(self):
        return self._path.rsplit("/", 1)[-1]

    def type(self):
        return _NodeType(self._node_type)

    def path(self):
        return self._path

    def children(self):
        return tuple(self._children)

    def errors(self):
        return list(self._errors)

    def warnings(self):
        return list(self._warnings)

    def isDisplayFlagSet(self):
        return self._display

    def isBypassed(self):
        return self._bypassed

    def lastModifiedPrims(self):
        return list(self._prims)

    def inputs(self):
        return tuple(self._inputs)

    def outputs(self):
        return tuple(self._outputs)

    def parms(self):
        return tuple(self._parms)

    def userDataDict(self):
        return dict(self._user_data)

    def creator(self):
        return self._creator

    def stage(self):
        return self._stage


def _fake_hou(root):
    module = types.ModuleType("hou")
    module.node = lambda path: root if path == root.path() else None
    module.parmTemplateType = _ParmType
    return module


def _run_extraction(root, target_path=None):
    """Exec the real template like the bridge: split globals/locals, fake hou."""
    script = inspector_tool._EXTRACTION_SCRIPT_TEMPLATE % {
        "schema_version": SCHEMA_VERSION,
        "target_path_literal": repr(target_path or root.path()),
    }
    saved = sys.modules.get("hou")
    sys.modules["hou"] = _fake_hou(root)
    try:
        g = {"__builtins__": __builtins__}  # hou NOT injected into globals
        l = {}
        buf = io.StringIO()
        with redirect_stdout(buf):
            exec(compile(script, "<inspect_recursion>", "exec"), g, l)
    finally:
        # `= None`, never a pop — an eviction window lets a lazy
        # `import hou` re-execute hou.py under hython.
        sys.modules["hou"] = saved
    return json.loads(buf.getvalue().strip())


def _chain(levels, prefix="/stage/n"):
    """A single-child chain of ``levels`` nodes (root excluded)."""
    node = FakeNode(prefix + str(levels))
    for i in range(levels - 1, 0, -1):
        node = FakeNode(prefix + str(i), children=[node])
    return node


# -----------------------------------------------------------------------------
# Recursive descent — the predicate's headline clause
# -----------------------------------------------------------------------------


class TestRecursiveWalk:
    def test_subnet_inner_nodes_are_returned(self):
        deep = FakeNode("/stage/sub/inner_a/deep")
        inner_a = FakeNode("/stage/sub/inner_a", children=[deep])
        inner_b = FakeNode("/stage/sub/inner_b")
        subnet = FakeNode(
            "/stage/sub", node_type="subnet", children=[inner_b, inner_a]
        )

        data = _run_extraction(FakeNode("/stage", children=[subnet]))

        assert data.get("synapse_error") is None, data
        assert data["truncated"] is False
        assert data["depth_reached"] == 3
        assert data["node_count"] == 4
        subnet_data = data["nodes"][0]
        assert subnet_data["node_name"] == "sub"
        # Deterministic order at every level.
        assert [c["node_name"] for c in subnet_data["children"]] == [
            "inner_a",
            "inner_b",
        ]
        assert [
            c["node_name"] for c in subnet_data["children"][0]["children"]
        ] == ["deep"]

    def test_flat_stage_still_reports_depth_one(self):
        root = FakeNode(
            "/stage", children=[FakeNode("/stage/a"), FakeNode("/stage/b")]
        )
        data = _run_extraction(root)
        assert data["truncated"] is False
        assert data["depth_reached"] == 1
        assert all(n["children"] == [] for n in data["nodes"])


# -----------------------------------------------------------------------------
# Bounded walk honesty — truncated:true names the level reached
# -----------------------------------------------------------------------------


class TestTruncation:
    def test_depth_cap_truncates_and_names_level(self):
        root = FakeNode("/stage", children=[_chain(MAX_WALK_DEPTH + 3)])

        data = _run_extraction(root)

        assert data["max_depth"] == MAX_WALK_DEPTH
        assert data["truncated"] is True
        assert "depth_cap" in data["truncation_reasons"]
        assert data["depth_reached"] == MAX_WALK_DEPTH
        assert data["truncated_paths"] == [
            "/stage/n" + str(MAX_WALK_DEPTH)
        ]

    def test_node_ceiling_truncates(self):
        children = [
            FakeNode("/stage/n%04d" % i) for i in range(MAX_WALK_NODES + 5)
        ]

        data = _run_extraction(FakeNode("/stage", children=children))

        assert data["node_count"] == MAX_WALK_NODES
        assert data["truncated"] is True
        assert "node_ceiling" in data["truncation_reasons"]


# -----------------------------------------------------------------------------
# No permanent empty placeholders
# -----------------------------------------------------------------------------


class TestPopulatedFields:
    def test_key_parms_capture_non_default_scalars(self):
        parms = [
            _Parm("filepath", "/assets/hero.usd", _ParmType.String),
            _Parm("scale", 2.5, _ParmType.Float),
            _Parm("defaulted", 1, _ParmType.Int, at_default=True),
            _Parm("button", 1, _ParmType.Button),
            _Parm("notes", "x" * 300, _ParmType.String),
        ]
        node = FakeNode("/stage/ref", parms=parms)

        data = _run_extraction(FakeNode("/stage", children=[node]))

        assert data["nodes"][0]["key_parms"] == {
            "filepath": "/assets/hero.usd",
            "scale": 2.5,
            "notes": "x" * 200,
        }

    def test_key_parms_are_bounded(self):
        parms = [
            _Parm("p%02d" % i, float(i), _ParmType.Float)
            for i in range(MAX_KEY_PARMS + 8)
        ]
        node = FakeNode("/stage/many", parms=parms)

        data = _run_extraction(FakeNode("/stage", children=[node]))

        assert len(data["nodes"][0]["key_parms"]) == MAX_KEY_PARMS

    def test_provenance_reads_creator_user_data_and_synapse_attrs(self):
        stage = _Stage({
            "/geo": _Prim([
                _Attr("synapse:agent", "observer"),
                _Attr("userPurpose", "render"),  # non-synapse: ignored
            ])
        })
        node = FakeNode(
            "/stage/geo",
            prims=["/geo"],
            stage=stage,
            user_data={"synapse:session": "s1"},
            creator=FakeNode("/stage/parent"),
        )

        data = _run_extraction(FakeNode("/stage", children=[node]))

        provenance = data["nodes"][0]["provenance"]
        assert provenance["creator"] == "/stage/parent"
        assert provenance["user_data"] == {"synapse:session": "s1"}
        assert provenance["usd_attributes"] == {"synapse:agent": "observer"}

    def test_provenance_none_when_no_source_has_data(self):
        node = FakeNode("/stage/plain")

        data = _run_extraction(FakeNode("/stage", children=[node]))

        assert data["nodes"][0]["provenance"] is None


# -----------------------------------------------------------------------------
# The parsed StageAST carries nested children and the walk envelope
# -----------------------------------------------------------------------------


class TestParsedStageAST:
    def test_nested_children_and_walk_meta_survive_parsing(self):
        subnet = FakeNode(
            "/stage/sub",
            node_type="subnet",
            children=[FakeNode("/stage/sub/inner")],
        )
        raw = _run_extraction(FakeNode("/stage", children=[subnet]))

        ast_obj = synapse_inspect_stage(
            execute_python_fn=make_mock_transport(json.dumps(raw))
        )

        assert ast_obj.truncated is False
        assert ast_obj.max_depth == MAX_WALK_DEPTH
        assert ast_obj.depth_reached == 2
        assert [c.node_name for c in ast_obj["sub"].children] == ["inner"]
        payload = ast_obj.to_payload()
        assert payload["truncated"] is False
        assert payload["node_count"] == 2
        assert payload["truncation_reasons"] == []

    def test_payload_without_walk_fields_is_byte_compatible(self):
        payload = {
            "schema_version": SCHEMA_VERSION,
            "target_path": "/stage",
            "nodes": [],
        }
        ast_obj = synapse_inspect_stage(
            execute_python_fn=make_mock_transport(json.dumps(payload))
        )
        assert ast_obj.truncated is False
        assert ast_obj.to_payload() == payload


# -----------------------------------------------------------------------------
# The description matches the walk — in all three declarations
# -----------------------------------------------------------------------------


def _mcp_server_inspector_desc():
    src = (
        Path(__file__).resolve().parent.parent / "mcp_server.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "_INSPECTOR_TOOL_DESC":
                return ast.literal_eval(node.value)
    raise AssertionError("_INSPECTOR_TOOL_DESC not found in mcp_server.py")


class TestDescriptions:
    def test_description_matches_the_walk(self):
        desc = INSPECT_STAGE_TOOL_DESCRIPTION
        assert "recursiv" in desc
        assert "depth cap" in desc
        assert "truncated:true" in desc
        assert "depth_reached" in desc

    def test_all_three_declarations_are_identical(self):
        from synapse.cognitive.tools.inspect_stage import INSPECT_STAGE_SCHEMA

        assert (
            INSPECT_STAGE_SCHEMA["description"]
            == INSPECT_STAGE_TOOL_DESCRIPTION
        )
        assert (
            _mcp_server_inspector_desc()
            == INSPECT_STAGE_TOOL_DESCRIPTION
        )

    def test_template_limits_match_module_constants(self):
        template = inspector_tool._EXTRACTION_SCRIPT_TEMPLATE
        assert "_MAX_DEPTH = %d" % MAX_WALK_DEPTH in template
        assert "_MAX_NODES = %d" % MAX_WALK_NODES in template
        assert "_MAX_KEY_PARMS = %d" % MAX_KEY_PARMS in template
