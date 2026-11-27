"""The APEX graph reader: points are nodes, wires are primitives, controls are tagged.

Before this, the trace read every primitive of a rig's packed folders as a
graph node. On a production rig that reported 830,152 "nodes" after about
five minutes (the mesh's polygons) where the graph has 205, and it never
answered at all on a Scene Invoke node. Nothing counted the rig's controls.

The fakes below copy the geometry layout measured on Houdini 22.0.466
(``python/synapse/server/apex_graph.py`` docstring): one point per graph
node, one two-vertex primitive per wire, ``portname`` on each vertex, a
string-array ``tags`` with no bulk reader, a character as packed folders,
and a scene one folder deeper.

Pure Python -- no hou, no hython. ``tests/test_apex_graph_read_hython.py``
reads a graph built by the real ``apex`` module.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from synapse.server import apex_graph, introspection


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _MeshWalked(AssertionError):
    """A mesh's elements were iterated. Distinct type so the failure can
    never be confused with an unrelated assertion."""


class _Named:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _Point:
    def __init__(self, number, attribs):
        self._number = number
        self._attribs = attribs

    def number(self):
        return self._number

    def attribValue(self, name):
        return self._attribs[name]


class _Vertex:
    def __init__(self, point, portname):
        self._point = point
        self._portname = portname

    def point(self):
        return self._point

    def attribValue(self, name):
        assert name == "portname"
        return self._portname


class _Wire:
    def __init__(self, ends):
        self._ends = ends

    def type(self):
        return _Named("Polygon")

    def vertices(self):
        # A generator, as hou.Prim.vertices() is on 22.0.466. A reader that
        # demands a tuple here reads no wires at all on a real rig.
        return (end for end in self._ends)


class _Folder:
    """A packed primitive holding embedded geometry."""

    def __init__(self, embedded):
        self._embedded = embedded

    def type(self):
        return _Named(apex_graph.PACKED_TYPE)

    def getEmbeddedGeometry(self):
        return self._embedded


class _Geo:
    """Just enough of hou.Geometry for the reader, with honest counts."""

    def __init__(self, points=(), prims=(), prim_names=None, point_attribs=(),
                 vertex_attribs=(), point_count=None, prim_count=None,
                 walkable=True):
        self._points = list(points)
        self._prims = list(prims)
        self._prim_names = prim_names
        self._point_attribs = set(point_attribs)
        self._vertex_attribs = set(vertex_attribs)
        self._point_count = len(self._points) if point_count is None else point_count
        self._prim_count = len(self._prims) if prim_count is None else prim_count
        self._walkable = walkable

    # O(1) reads
    def intrinsicValue(self, name):
        return {"pointcount": self._point_count,
                "primitivecount": self._prim_count}[name]

    def countPrimType(self, type_name):
        return sum(1 for p in self._prims if p.type().name() == type_name)

    def findPointAttrib(self, name):
        return _Named(name) if name in self._point_attribs else None

    def findPrimAttrib(self, name):
        return _Named(name) if name == "name" and self._prim_names is not None else None

    def findVertexAttrib(self, name):
        return _Named(name) if name in self._vertex_attribs else None

    # bulk string columns
    def pointStringAttribValues(self, name):
        if name == "tags":
            # Measured: a string array has no bulk reader on 22.0.466.
            raise RuntimeError("OperationFailed")
        return tuple(p.attribValue(name) for p in self._points)

    def primStringAttribValues(self, name):
        assert name == "name"
        return tuple(self._prim_names)

    # element walks: a mesh must never be walked
    def _walk(self, items):
        if not self._walkable:
            raise _MeshWalked("the reader iterated a mesh's elements")
        return tuple(items)

    def points(self):
        return self._walk(self._points)

    def iterPoints(self):
        return iter(self._walk(self._points))

    def prims(self):
        return self._walk(self._prims)

    def iterPrims(self):
        return iter(self._walk(self._prims))


def _graph_geo(nodes, wires):
    """nodes: [(name, callback, tags)], wires: [(src, src_port, dst, dst_port)]."""
    points = [
        _Point(i, {"name": name, "callback": callback, "tags": tuple(tags)})
        for i, (name, callback, tags) in enumerate(nodes)
    ]
    by_name = {p.attribValue("name"): p for p in points}
    prims = [
        _Wire([_Vertex(by_name[src], sp), _Vertex(by_name[dst], dp)])
        for src, sp, dst, dp in wires
    ]
    return _Geo(points=points, prims=prims,
                point_attribs=("name", "callback", "tags", "parms", "properties"),
                vertex_attribs=("portname", "portindex", "portalias"))


# A six-node rig in the measured shape: two tagged controls, one untagged
# TransformObject (OVOID has nine of those), one math node.
RIG_NODES = [
    ("parms", "__parms__", ()),
    ("output", "__output__", ()),
    ("placement", "TransformObject", ("control",)),
    ("body_cog", "TransformObject", ("control",)),
    ("iris_leaf_00", "TransformObject", ()),
    ("body_bind", "Multiply<Matrix4>", ()),
]
RIG_WIRES = [
    ("parms", "placement_t", "placement", "t"),
    ("parms", "placement_r", "placement", "r"),
    ("placement", "xform", "output", "placement"),
    ("placement", "xform", "body_cog", "parent"),
    ("parms", "body_t", "body_cog", "t"),
    ("body_cog", "xform", "iris_leaf_00", "parent"),
    ("body_cog", "xform", "body_bind", "b"),
    ("body_bind", "result", "output", "body"),
]


def _rig():
    return _graph_geo(RIG_NODES, RIG_WIRES)


def _mesh(points=792_113, prims=829_618):
    """A mesh that raises if any element is iterated."""
    return _Geo(point_count=points, prim_count=prims, walkable=False,
                point_attribs=("P", "N", "rest"))


def _skeleton():
    return _Geo(points=[_Point(i, {"name": "j%d" % i}) for i in range(44)],
                point_attribs=("P", "name", "transform"))


def _character():
    return _Geo(prims=[_Folder(_rig()), _Folder(_mesh()), _Folder(_skeleton())],
                prim_names=("Base.rig", "Base.shp", "Base.skel"),
                point_count=3, point_attribs=("P",))


def _scene():
    return _Geo(prims=[_Folder(_character())], prim_names=("ovoid.char",),
                point_count=1, point_attribs=("P",))


class _Node:
    def __init__(self, path, type_name="null", geo=None, inputs=(), dirty=False):
        self._path = path
        self._type_name = type_name
        self._geo = geo
        self._inputs = tuple(inputs)
        self._dirty = dirty
        self.geometry_call_count = 0

    def path(self):
        return self._path

    def type(self):
        return _Named(self._type_name)

    def inputs(self):
        return self._inputs

    def needsToCook(self):
        return self._dirty

    def geometry(self):
        self.geometry_call_count += 1
        if self._dirty:
            raise AssertionError("geometry() on a dirty node forces the cook")
        return self._geo


# ---------------------------------------------------------------------------
# One graph
# ---------------------------------------------------------------------------

def test_points_are_nodes_and_prims_are_wires():
    graph = apex_graph.read_graph(_rig())
    assert graph["read"] is True
    assert graph["node_count"] == len(RIG_NODES) == 6
    assert graph["wire_count"] == len(RIG_WIRES) == 8
    assert graph["wires_status"] == "read"
    assert "omitted" not in graph


def test_controls_are_the_tagged_nodes_not_every_transform():
    graph = apex_graph.read_graph(_rig())
    # Three TransformObject nodes, two of them tagged. Counting the callback
    # would report 3; OVOID's real numbers are 58 transforms and 49 controls.
    assert graph["callbacks"]["TransformObject"] == 3
    assert graph["control_count"] == 2
    assert graph["controls"] == ["placement", "body_cog"]


def test_graph_inputs_and_outputs_come_from_the_boundary_nodes():
    graph = apex_graph.read_graph(_rig())
    assert graph["graph_inputs"] == ["placement_t", "placement_r", "body_t"]
    assert graph["graph_outputs"] == ["placement", "body"]
    assert graph["graph_input_count"] == 3
    assert graph["graph_output_count"] == 2


def test_wire_direction_is_source_then_destination():
    graph = apex_graph.read_graph(_rig(), include_nodes=True, include_wires=True)
    assert [n["name"] for n in graph["nodes"]] == [n[0] for n in RIG_NODES]
    assert graph["nodes"][2] == {
        "name": "placement", "callback": "TransformObject", "tags": ["control"]}
    wires = graph["wires"]
    assert wires[0] == {"source": "parms", "source_port": "placement_t",
                        "destination": "placement", "destination_port": "t"}
    # Nothing enters the graph's inputs and nothing leaves its outputs.
    assert not [w for w in wires if w["destination"] == "parms"]
    assert not [w for w in wires if w["source"] == "output"]


def test_summary_is_small_by_default():
    graph = apex_graph.read_graph(_rig())
    assert "nodes" not in graph and "wires" not in graph


def test_a_wire_that_is_not_two_vertices_is_counted_unread_not_guessed():
    geo = _rig()
    geo._prims.append(_Wire([_Vertex(geo._points[0], "x")]))
    geo._prim_count += 1
    graph = apex_graph.read_graph(geo, include_wires=True)
    assert len(graph["wires"]) == 8
    assert graph["wires_status"] == "partly read"
    assert graph["omitted"]["wires_unread"] == 1


def test_a_graph_past_the_node_ceiling_is_stamped_not_read(monkeypatch):
    monkeypatch.setattr(apex_graph, "GRAPH_NODE_CAP", 4)
    graph = apex_graph.read_graph(_rig())
    assert graph["read"] is False
    assert graph["node_count"] == 6
    assert "ceiling" in graph["reason"]


def test_long_name_lists_are_capped_and_the_omission_is_stamped(monkeypatch):
    monkeypatch.setattr(apex_graph, "NAME_LIST_CAP", 1)
    graph = apex_graph.read_graph(_rig())
    assert graph["controls"] == ["placement"]
    assert graph["control_count"] == 2          # the count stays true
    assert graph["omitted"]["controls"] == 1
    assert graph["omitted"]["graph_inputs"] == 2


# ---------------------------------------------------------------------------
# What is not a graph
# ---------------------------------------------------------------------------

def test_a_mesh_is_not_a_graph_and_is_never_walked():
    mesh = _mesh()
    assert apex_graph.is_graph_geometry(mesh) is False
    assert apex_graph.read_graph(mesh) is None
    assert apex_graph.summarize(mesh) is None    # _MeshWalked would raise here


def test_a_skeleton_is_not_a_graph():
    assert apex_graph.read_graph(_skeleton()) is None


def test_ordinary_packed_geometry_gets_no_block():
    rocks = _Geo(prims=[_Folder(_mesh(100, 80)) for _ in range(5)],
                 prim_names=tuple("rock%d" % i for i in range(5)), point_count=5)
    assert apex_graph.summarize(rocks) is None


def test_a_mock_never_reads_as_a_graph():
    # A MagicMock answers every call with a truthy non-value. The reader must
    # demand real ints and real str, or every mocked node in the suite would
    # grow an ``apex`` block.
    mock = MagicMock()
    assert apex_graph.is_graph_geometry(mock) is False
    assert apex_graph.read_graph(mock) is None
    assert apex_graph.summarize(mock) is None
    assert list(apex_graph.iter_folders(mock)) == []
    assert apex_graph.summarize(None) is None


def test_a_callback_attribute_that_is_not_strings_is_not_a_graph():
    geo = _Geo(points=[_Point(0, {"callback": 7})], point_attribs=("callback",))
    assert apex_graph.read_graph(geo) is None


# ---------------------------------------------------------------------------
# Characters and scenes
# ---------------------------------------------------------------------------

def test_a_character_holds_its_graph_in_a_folder():
    summary = apex_graph.summarize(_character())
    assert [g["folder"] for g in summary["graphs"]] == ["Base.rig"]
    assert summary["graphs"][0]["control_count"] == 2
    kinds = {f["name"]: f["kind"] for f in summary["folders"]}
    assert kinds == {"Base.rig": "graph", "Base.shp": "geometry",
                     "Base.skel": "skeleton"}
    shape = next(f for f in summary["folders"] if f["name"] == "Base.shp")
    assert shape["points"] == 792_113            # counted, never walked


def test_a_scene_nests_the_character_one_folder_deeper():
    summary = apex_graph.summarize(_scene())
    assert [g["folder"] for g in summary["graphs"]] == ["ovoid.char/Base.rig"]
    assert summary["graphs"][0]["node_count"] == 6
    names = [f["name"] for f in summary["folders"]]
    assert names == ["ovoid.char", "ovoid.char/Base.rig",
                     "ovoid.char/Base.shp", "ovoid.char/Base.skel"]


def test_a_graph_handed_in_directly_is_read():
    summary = apex_graph.summarize(_rig())
    assert summary["graphs"][0]["folder"] == ""
    assert summary["graphs"][0]["node_count"] == 6


def test_folder_depth_is_capped(monkeypatch):
    monkeypatch.setattr(apex_graph, "FOLDER_DEPTH_CAP", 0)
    # The scene's graph is at depth 1; with the walk held to depth 0 it is not found.
    assert apex_graph.summarize(_scene()) is None


def test_a_geometry_with_too_many_prims_is_not_walked_for_folders(monkeypatch):
    monkeypatch.setattr(apex_graph, "FOLDER_SCAN_CAP", 2)
    assert apex_graph.summarize(_character()) is None   # 3 prims, ceiling 2


# ---------------------------------------------------------------------------
# Node-level search
# ---------------------------------------------------------------------------

def _plain_reader(node):
    return node.geometry()


def test_a_node_with_no_graph_is_answered_from_upstream():
    scene = _Node("/obj/rig/scene_animate", "apex::sceneanimate", _scene())
    invoke = _Node("/obj/rig/scene_invoke", "apex::sceneinvoke::2.0", _mesh(),
                   inputs=[scene])
    found = apex_graph.find_graphs(invoke, _plain_reader)
    assert found["source"] == "/obj/rig/scene_animate"
    assert found["distance"] == 1
    assert found["summary"]["graphs"][0]["folder"] == "ovoid.char/Base.rig"


def test_a_node_that_carries_the_graph_answers_for_itself():
    pose = _Node("/obj/rig/rigpose", "apex::rigpose", _character())
    found = apex_graph.find_graphs(pose, _plain_reader)
    assert (found["source"], found["distance"]) == ("/obj/rig/rigpose", 0)
    assert found["examined"] == 0


def test_the_search_reads_only_through_the_callers_reader():
    dirty = _Node("/obj/rig/upstream", "apex::sceneanimate", _scene(), dirty=True)
    invoke = _Node("/obj/rig/scene_invoke", "apex::sceneinvoke::2.0", _mesh(),
                   inputs=[dirty])
    gated = lambda n: introspection._clean_geometry(n)[0]   # noqa: E731
    found = apex_graph.find_graphs(invoke, gated)
    assert found["summary"] is None
    assert found["unread"] == ["/obj/rig/upstream"]
    assert dirty.geometry_call_count == 0


def test_the_upstream_search_is_bounded(monkeypatch):
    monkeypatch.setattr(apex_graph, "UPSTREAM_NODE_CAP", 3)
    chain = _Node("/obj/n0", geo=_mesh())
    for i in range(1, 10):
        chain = _Node("/obj/n%d" % i, geo=_mesh(), inputs=[chain])
    found = apex_graph.find_graphs(chain, _plain_reader)
    assert found["summary"] is None
    assert found["examined"] == 3


# ---------------------------------------------------------------------------
# The inspect_node block
# ---------------------------------------------------------------------------

def test_inspect_block_reads_a_rig_node():
    pose = _Node("/obj/rig/rigpose", "apex::rigpose", _character())
    block = introspection._apex_block(pose)
    assert block["graph_read"] is True
    assert block["graph_source"] == "/obj/rig/rigpose"
    assert block["graph_distance"] == 0
    assert block["graphs"][0]["controls"] == ["placement", "body_cog"]
    assert "note" not in block


def test_inspect_block_answers_scene_invoke_from_upstream():
    scene = _Node("/obj/rig/scene_animate", "apex::sceneanimate", _scene())
    invoke = _Node("/obj/rig/scene_invoke", "apex::sceneinvoke::2.0", _mesh(),
                   inputs=[scene])
    block = introspection._apex_block(invoke)
    assert block["graph_source"] == "/obj/rig/scene_animate"
    assert block["graph_distance"] == 1
    assert "/obj/rig/scene_animate" in block["note"]


def test_every_block_is_plain_json():
    # The /mcp path serialises a result with orjson, which takes no stand-in
    # values and no non-str keys. A ``default=str`` fallback would hide one.
    import json
    scene = _Node("/obj/rig/scene_animate", "apex::sceneanimate", _scene())
    nodes = [
        _Node("/obj/rig/rigpose", "apex::rigpose", _character()),
        _Node("/obj/rig/scene_invoke", "apex::sceneinvoke::2.0", _mesh(), inputs=[scene]),
        _Node("/obj/rig/rigpose", "apex::rigpose", _character(), dirty=True),
        _Node("/obj/rig/scene_invoke", "apex::sceneinvoke::2.0", _mesh()),
    ]
    for node in nodes:
        block = introspection._apex_block(node)
        assert json.loads(json.dumps(block)) == block
    full = apex_graph.read_graph(_rig(), include_nodes=True, include_wires=True)
    assert json.loads(json.dumps(full)) == full


def test_inspect_block_never_cooks_a_dirty_apex_node():
    dirty = _Node("/obj/rig/rigpose", "apex::rigpose", _character(), dirty=True)
    block = introspection._apex_block(dirty)
    assert block["graph_read"] is False
    assert block["observation_status"] == "dirty_not_forced"
    assert dirty.geometry_call_count == 0


def test_inspect_block_lists_a_dirty_input_instead_of_cooking_it():
    dirty = _Node("/obj/rig/upstream", "apex::sceneanimate", _scene(), dirty=True)
    invoke = _Node("/obj/rig/scene_invoke", "apex::sceneinvoke::2.0", _mesh(),
                   inputs=[dirty])
    block = introspection._apex_block(invoke)
    assert block["graph_read"] is False
    assert block["upstream_not_cooked"] == ["/obj/rig/upstream"]
    assert dirty.geometry_call_count == 0


def test_inspect_block_is_absent_for_ordinary_nodes():
    assert introspection._apex_block(_Node("/obj/geo1/box1", "box", _mesh())) is None
    # A dirty ordinary node is silent too: the block is optional, never noise.
    assert introspection._apex_block(
        _Node("/obj/geo1/box1", "box", _mesh(), dirty=True)) is None
    # A non-APEX node does not search upstream.
    scene = _Node("/obj/rig/scene_animate", "apex::sceneanimate", _scene())
    downstream = _Node("/obj/rig/null1", "null", _mesh(), inputs=[scene])
    assert introspection._apex_block(downstream) is None


def test_inspect_block_reads_a_character_on_any_node_type():
    # OVOID's character is assembled by a Python SOP, not an ``apex::`` node.
    data = _Node("/obj/rig/character_data", "python", _character())
    assert introspection._apex_block(data)["graphs"][0]["node_count"] == 6


def test_inspect_block_ignores_a_mocked_node():
    node = MagicMock()
    node.needsToCook.return_value = False
    assert introspection._apex_block(node) is None


def test_inspect_node_attaches_the_block_without_the_geometry_flag(monkeypatch):
    pose = _Node("/obj/rig/rigpose", "apex::rigpose", _character())
    pose.name = lambda: "rigpose"
    pose.parms = lambda: []
    pose.warnings = lambda: []
    pose.errors = lambda: []
    pose.parm = lambda name: None
    pose.inputConnections = lambda: []
    pose.outputConnections = lambda: []
    monkeypatch.setattr(introspection, "hou", SimpleNamespace(node=lambda path: pose))
    monkeypatch.setattr(introspection, "_node_basic", lambda n: {"path": n.path()})
    monkeypatch.setattr(introspection, "_connections", lambda n: {})
    info = introspection.inspect_node_detail("/obj/rig/rigpose", include_geometry=False)
    assert "geometry" not in info
    assert info["apex"]["graphs"][0]["control_count"] == 2


# ---------------------------------------------------------------------------
# The panel modules read through the same reader
# ---------------------------------------------------------------------------

# The fourteen callbacks OVOID's rig uses, measured on 22.0.466.
REAL_CALLBACKS = {
    "Multiply<Matrix4>": "math",
    "TransformObject": "transform",
    "geo::Transform": "deform",
    "TwoWaySwitch<Matrix4>": "logic",
    "LookAt": "transform",
    "rig::TwoBoneIK": "solver",
    "Value<Geometry>": "other",
    "Clamp<Float>": "math",
    "SetComponent<Vector3>": "math",
    "Multiply<Float>": "math",
    "__parms__": "io",
    "__output__": "io",
    "skel::SetPointTransforms": "deform",
    "sop::bonedeform": "deform",
}


@pytest.mark.parametrize("callback,category", sorted(REAL_CALLBACKS.items()))
def test_real_callbacks_get_a_true_category(callback, category):
    from synapse.panel import apex_trace
    assert apex_trace.categorize_apex_operation(callback) == category


def test_no_category_is_named_control():
    # "control" means a rig control here. A flow-control category of the same
    # name would print "60 control" beside "49 controls".
    from synapse.panel import apex_trace
    assert "control" not in apex_trace._CATEGORY_MAP
    assert {apex_trace.categorize_apex_operation(c) for c in REAL_CALLBACKS} <= {
        "transform", "math", "logic", "solver", "deform", "io", "other"}


def _trace(monkeypatch, node):
    from synapse.panel import apex_trace
    node.name = lambda: node.path().rsplit("/", 1)[-1]
    node.parm = lambda name: None
    monkeypatch.setattr(apex_trace, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(apex_trace, "hou", SimpleNamespace(node=lambda path: node))
    return apex_trace, apex_trace.trace_apex_graph(node.path())


def test_trace_reports_nodes_wires_and_controls(monkeypatch):
    pose = _Node("/obj/rig/rigpose", "apex::rigpose", _character())
    apex_trace, trace = _trace(monkeypatch, pose)
    assert trace.graph_name == "Base.rig"
    assert (trace.node_count, trace.wire_count) == (6, 8)
    assert trace.controls == ["placement", "body_cog"]
    assert "6 nodes, 8 wires, 2 controls" in trace.summary
    order = [n.name for n in trace.nodes]
    assert order.index("parms") < order.index("placement") < order.index("body_cog")
    assert order.index("body_bind") < order.index("output")
    assert ("placement", "body_cog", "xform -> parent") in trace.data_flow
    text = apex_trace.format_apex_trace_text(trace)
    assert "Controls: 2" in text and "placement, body_cog" in text


def test_trace_of_scene_invoke_reads_the_rig_upstream(monkeypatch):
    scene = _Node("/obj/rig/scene_animate", "apex::sceneanimate", _scene())
    invoke = _Node("/obj/rig/scene_invoke", "apex::sceneinvoke::2.0", _mesh(),
                   inputs=[scene])
    _, trace = _trace(monkeypatch, invoke)
    assert trace.node_count == 6
    assert trace.graph_source == "/obj/rig/scene_animate"
    assert "1 input(s) upstream" in trace.summary


def test_trace_of_a_mesh_with_no_rig_says_so_without_walking_it(monkeypatch):
    _, trace = _trace(monkeypatch, _Node("/obj/geo1/mesh", "null", _mesh()))
    assert trace.node_count == 0
    assert "no APEX graph" in trace.summary


@pytest.mark.parametrize("type_name,expected", [
    ("apex::rigpose", "apex_network"),        # was "kinefx"
    ("kinefx::rigpose", "kinefx"),
    ("apex::sceneinvoke::2.0", "invoke"),
    ("apex::sceneanimate", "apex_network"),
])
def test_an_apex_node_is_never_explained_as_kinefx(type_name, expected):
    from synapse.panel import apex_explainer
    assert apex_explainer._classify_apex_type(type_name) == expected


def test_explain_context_carries_the_rig(monkeypatch):
    from synapse.panel import apex_explainer
    pose = _Node("/obj/rig/rigpose", "apex::rigpose", _character())
    pose.parms = lambda: []
    pose.errors = lambda: []
    pose.warnings = lambda: []
    monkeypatch.setattr(apex_explainer, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(apex_explainer, "hou", SimpleNamespace(node=lambda path: pose))
    context = apex_explainer.gather_apex_context("/obj/rig/rigpose")
    assert context["apex_type"] == "apex_network"
    assert context["rig_info"]["graphs"][0]["control_count"] == 2
    assert context["packed_info"]["folder_names"] == ["Base.rig", "Base.shp", "Base.skel"]
    assert context["skeleton_info"]["has_skeleton"] is False
    message = apex_explainer.build_apex_messages(context)[0]["content"]
    assert "6 nodes, 8 wires, 2 controls" in message
    assert "placement, body_cog" in message
