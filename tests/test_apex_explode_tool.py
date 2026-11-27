"""synapse_add_explode_control: the plan, the node's code, the build, the tables.

The tool adds one control, ``explode``, to an existing APEX rig, carried by
one Python SOP whose code SYNAPSE generates. Nothing here needs Houdini.

The stand-ins copy what was measured on Houdini 22.0.466:

  * a graph is geometry: one point per node, one two-vertex primitive per
    wire, ``portname`` on each vertex, tags with no bulk reader;
  * a character is three packed folders (``Base.rig``, ``Base.shp``,
    ``Base.skel``), and a Python SOP's geometry starts as a copy of its input;
  * the ``apex.Graph`` calls the edit makes, with the port names each
    callback really has.

The build tests run the GENERATED CODE, not a copy of its logic: the stand-in
node executes the text the core wrote into its ``python`` parameter against a
stand-in ``apex``, and the result is read back with the real
``apex_graph`` reader. ``tests/test_apex_explode_tool_hython.py`` runs the
same build against the real ``apex`` module.

Every test says what would make it fail.
"""
from __future__ import annotations

import array
import contextlib
import inspect
import json
import sys
import types

import pytest

from synapse.core.errors import SynapseUserError
from synapse.server import apex_explode as plan
from synapse.server import apex_explode_edit as edit
from synapse.server import apex_graph
from synapse.server import handlers_apex


# ---------------------------------------------------------------------------
# Graph geometry, as apex_graph reads it
# ---------------------------------------------------------------------------

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
        return (end for end in self._ends)   # a generator, as on 22.0.466


class _GraphGeo:
    """Graph geometry. ``hou.Geometry()`` in the stand-in ``hou`` makes an
    empty one, and ``saveToGeometry`` fills it."""

    def __init__(self, nodes=(), wires=()):
        self.load(nodes, wires)

    def load(self, nodes, wires):
        """nodes: [(name, callback, tags)], wires: [(src, src_port, dst, dst_port)]."""
        self.nodes = [(n, c, tuple(t)) for n, c, t in nodes]
        self.wires = [tuple(w) for w in wires]
        self._points = [_Point(i, {"name": n, "callback": c, "tags": t})
                        for i, (n, c, t) in enumerate(self.nodes)]
        by_name = {p.attribValue("name"): p for p in self._points}
        self._prims = [_Wire([_Vertex(by_name[s], sp), _Vertex(by_name[d], dp)])
                       for s, sp, d, dp in self.wires]

    def intrinsicValue(self, name):
        return {"pointcount": len(self._points), "primitivecount": len(self._prims)}[name]

    def countPrimType(self, type_name):
        return 0

    def findPointAttrib(self, name):
        if not self._points:
            return None
        return _Named(name) if name in ("name", "callback", "tags") else None

    def findPrimAttrib(self, name):
        return None

    def findVertexAttrib(self, name):
        return _Named(name) if name == "portname" else None

    def pointStringAttribValues(self, name):
        if name == "tags":
            raise RuntimeError("OperationFailed")   # measured: no bulk reader
        return tuple(p.attribValue(name) for p in self._points)

    def points(self):
        return tuple(self._points)

    def iterPoints(self):
        return iter(self._points)

    def prims(self):
        return tuple(self._prims)

    def iterPrims(self):
        return iter(self._prims)


# ---------------------------------------------------------------------------
# The rest shape, and the packed character
# ---------------------------------------------------------------------------

class _Attrib:
    def __init__(self, kind="Float", size=3):
        self._kind, self._size = kind, size

    def dataType(self):
        return _Named(self._kind)

    def size(self):
        return self._size


class _Box:
    def __init__(self, low, high):
        self._low, self._high = low, high

    def minvec(self):
        return self._low

    def maxvec(self):
        return self._high


class _Shape:
    """A mesh. It has no ``points()`` and no ``prims()``: reading one element
    of it would raise AttributeError, so no test passes by walking a mesh."""

    def __init__(self, offsets=((0.0, 0.0, 0.0), (0.2, 0.08, 0.0), (0.0, 0.0, 0.16),
                                (0.0, 0.0, 0.0)),
                 low=(-0.632, 0.0, -0.563), high=(0.632, 1.2, 0.563),
                 attribute="explode_offset", kind="Float", size=3):
        self.offsets = [tuple(o) for o in offsets]
        self._low, self._high = low, high
        self._attribute, self._kind, self._size = attribute, kind, size

    def intrinsicValue(self, name):
        return {"pointcount": len(self.offsets), "primitivecount": 7}[name]

    def countPrimType(self, type_name):
        return 0

    def findPointAttrib(self, name):
        if name == self._attribute:
            return _Attrib(self._kind, self._size)
        return _Named(name) if name in ("P", "N") else None

    def findPrimAttrib(self, name):
        return None

    def boundingBox(self):
        return _Box(self._low, self._high)

    def pointFloatAttribValuesAsString(self, name):
        assert name == self._attribute
        flat = [c for o in self.offsets for c in o]
        return array.array("f", flat).tobytes()


class _Folder:
    """A packed primitive holding embedded geometry."""

    def __init__(self, name, embedded):
        self._name = name
        self._embedded = embedded

    def type(self):
        return _Named(apex_graph.PACKED_TYPE)

    def attribValue(self, name):
        assert name == "name"
        return self._name

    def getEmbeddedGeometry(self):
        return self._embedded

    def setEmbeddedGeometry(self, geo):
        self._embedded = geo


class _Packed:
    """A packed character or scene: folders named by the ``name`` attribute."""

    def __init__(self, folders):
        self._folders = [_Folder(name, geo) for name, geo in folders]

    def copy(self):
        """A Python SOP's own geometry: new folders around the same embedded
        geometry, so replacing one folder here leaves the input as it was."""
        return _Packed([(f.attribValue("name"), f.getEmbeddedGeometry())
                        for f in self._folders])

    def folder(self, name):
        return next(f for f in self._folders if f.attribValue("name") == name)

    def intrinsicValue(self, name):
        return {"pointcount": len(self._folders),
                "primitivecount": len(self._folders)}[name]

    def countPrimType(self, type_name):
        return len(self._folders) if type_name == apex_graph.PACKED_TYPE else 0

    def findPointAttrib(self, name):
        return _Named(name) if name == "P" else None

    def findPrimAttrib(self, name):
        return _Named(name) if name == "name" else None

    def primStringAttribValues(self, name):
        assert name == "name"
        return tuple(f.attribValue("name") for f in self._folders)

    def prims(self):
        return tuple(self._folders)


# A small rig in the measured shape. The shape arrives on a graph input named
# after its folder, and one node reads it, as on the production rig.
RIG_NODES = [
    ("parms", "__parms__", ()),
    ("output", "__output__", ()),
    ("placement", "TransformObject", ("control",)),
    ("body_cog", "TransformObject", ("control",)),
    ("iris_leaf_00", "TransformObject", ()),
    ("rest_manufacture", "Value<Geometry>", ()),
    ("body_rigid_deform", "geo::Transform", ()),
]
RIG_WIRES = [
    ("parms", "placement_t", "placement", "t"),
    ("placement", "xform", "output", "placement"),
    ("placement", "xform", "body_cog", "parent"),
    ("parms", "body_t", "body_cog", "t"),
    ("body_cog", "xform", "iris_leaf_00", "parent"),
    ("parms", "Base.shp", "rest_manufacture", "parm"),
    ("rest_manufacture", "value", "body_rigid_deform", "geo"),
    ("body_cog", "xform", "body_rigid_deform", "xform"),
    ("body_rigid_deform", "geo", "output", "Base.shp"),
]


def _rig(nodes=RIG_NODES, wires=RIG_WIRES):
    return _GraphGeo(nodes, wires)


def _skeleton():
    return _Shape(attribute="transform", kind="Float", size=16)


def _character(rig=None, shape=None):
    return _Packed([("Base.rig", rig if rig is not None else _rig()),
                    ("Base.shp", shape if shape is not None else _Shape()),
                    ("Base.skel", _skeleton())])


def _read(geo):
    return apex_graph.read_graph(geo, include_nodes=True, include_wires=True)


# ---------------------------------------------------------------------------
# Stand-ins for the apex and hou modules the node's code imports
# ---------------------------------------------------------------------------

# Port names per callback, as probed on 22.0.466 (apex_explode_edit docstring).
PORTS = {
    "TransformObject": (("parent", "parentlocal", "scaleinheritance", "xform", "t", "r", "s",
                         "local", "restlocal", "xord", "rord", "xformmask", "p", "pr"),
                        ("xform", "localxform", "restlocal", "t", "r", "s")),
    "Vector3ToFloat": (("vector",), ("x", "y", "z")),
    "Multiply<Float>": (("a", "b"), ("result",)),
    "Clamp<Float>": (("val", "min", "max"), ("result",)),
    "sop::peak": (("geo0", "group", "grouptype", "mask", "enablemaskattrib", "maskattrib",
                   "usecustomattrib", "customattrib", "normalizeattrib", "dist", "updatenmls"),
                  ("geo0",)),
    "Value<Geometry>": (("parm",), ("value",)),
    "geo::Transform": (("geo", "xform", "group", "grouptype"), ("geo",)),
}


class _FakeGraph:
    """The part of ``apex.Graph`` the edit uses. Strict: an unknown callback,
    a wire into a port that already has one, or a wire between two ports of
    the wrong kind raises, so a wrong edit cannot pass quietly."""

    callbacks_missing = ()      # a test sets this to make a callback unknown

    def __init__(self, geo=None):
        self._nodes = []        # [name, callback, set(tags), parms]
        self._ports = []        # (node, name, kind)
        self._wires = {}        # wire id -> (source port, destination port)
        self._next_wire = 0
        self.defaults = {}
        if geo is not None:
            for name, callback, tags in geo.nodes:
                self._nodes.append([name, callback, set(tags), {}])
            index = {n[0]: i for i, n in enumerate(self._nodes)}
            for source, sp, dest, dp in geo.wires:
                self._wire(self._port(index[source], sp, "out", make=True),
                           self._port(index[dest], dp, "in", make=True))

    def _port(self, node, name, kind, make=False):
        key = (node, name, kind)
        if key in self._ports:
            return self._ports.index(key)
        callback = self._nodes[node][1]
        fixed = PORTS.get(callback)
        known = fixed is not None and name in fixed[0 if kind == "in" else 1]
        if known or make:
            self._ports.append(key)
            return len(self._ports) - 1
        return -1

    def _wire(self, source, dest):
        assert self._ports[source][2] == "out" and self._ports[dest][2] == "in", \
            "a wire runs from an output port to an input port"
        assert all(d != dest for _, d in self._wires.values()), \
            "that input port already has a wire"
        self._wires[self._next_wire] = (source, dest)
        self._next_wire += 1

    # --- reads
    def matchNodes(self, pattern):
        assert pattern == "*"
        return list(range(len(self._nodes)))

    def nodeName(self, node):
        return self._nodes[node][0]

    def callbackName(self, node):
        return self._nodes[node][1]

    def getPort(self, node, spec):
        name, kind = spec[:-1].rsplit("[", 1)
        return self._port(node, name, kind)

    def connectedPorts(self, port):
        return [d for s, d in self._wires.values() if s == port]

    def portWires(self, port):
        return [w for w, (s, d) in self._wires.items() if port in (s, d)]

    # --- edits
    def addNode(self, name, callback):
        assert all(n[0] != name for n in self._nodes), "node names are unique"
        if callback not in PORTS or callback in self.callbacks_missing:
            raise RuntimeError("unknown callback %s" % callback)
        self._nodes.append([name, callback, set(), {}])
        return len(self._nodes) - 1

    def setNodeParms(self, node, values):
        self._nodes[node][3].update(values)

    def setNodeTag(self, node, tag):
        self._nodes[node][2].add(tag)

    def addWire(self, source, dest):
        self._wire(source, dest)

    def removeWires(self, wires, _flag):
        for wire in list(wires):
            del self._wires[wire]

    def addSubPort(self, port, label):
        node, name, kind = self._ports[port]
        self._ports.append((node, "%s:%s" % (name, label), kind))
        return len(self._ports) - 1

    def promoteInput(self, port, parms_node, name):
        assert self._nodes[parms_node][1] == "__parms__"
        self._wire(self._port(parms_node, name, "out", make=True), port)

    def promoteOutput(self, port, output_node, name):
        assert self._nodes[output_node][1] == "__output__"
        self._wire(port, self._port(output_node, name, "in", make=True))

    def setDefaultParms(self, values, _flag):
        self.defaults.update(values)

    def saveToGeometry(self, geo):
        nodes = [(n[0], n[1], sorted(n[2])) for n in self._nodes]
        wires = []
        for source, dest in self._wires.values():
            s_node, s_name, _ = self._ports[source]
            d_node, d_name, _ = self._ports[dest]
            wires.append((self._nodes[s_node][0], s_name.split(":")[0],
                          self._nodes[d_node][0], d_name.split(":")[0]))
        geo.load(nodes, wires)

    # --- for the tests
    def parms_of(self, name):
        return next(n[3] for n in self._nodes if n[0] == name)


class _NodeError(Exception):
    pass


def _fake_modules(current_node=None, graph_class=_FakeGraph):
    apex = types.ModuleType("apex")
    apex.Graph = graph_class
    apex.Dict = dict
    hou = types.ModuleType("hou")
    hou.Vector3 = lambda *xyz: tuple(float(v) for v in xyz)
    hou.hmath = types.SimpleNamespace(buildTranslate=lambda t: ("translate", tuple(t)))
    hou.Geometry = _GraphGeo
    hou.NodeError = _NodeError
    hou.pwd = lambda: current_node
    return apex, hou


@contextlib.contextmanager
def _modules_installed(apex, hou):
    saved = {name: sys.modules.get(name) for name in ("apex", "hou")}
    sys.modules["apex"], sys.modules["hou"] = apex, hou
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


EDIT = dict(shape_port="Base.shp", parent="placement", travel=0.3,
            handle=(0.0, 1.35, 0.0), attribute="explode_offset", rest_value=0.0)


def _edited(rig=None, **overrides):
    apex, hou = _fake_modules()
    graph = _FakeGraph(rig if rig is not None else _rig())
    added = edit.add_explode_control(graph, apex, hou, **dict(EDIT, **overrides))
    geo = _GraphGeo()
    graph.saveToGeometry(geo)
    return graph, geo, added


# ===========================================================================
# 1. The edit: what one call adds to a graph
# ===========================================================================

def test_the_edit_adds_one_control_and_four_working_nodes():
    """Fails if the edit adds a different set of nodes, or forgets the tag
    that makes ``explode`` a control."""
    _, geo, added = _edited()
    after, before = _read(geo), _read(_rig())
    assert added == list(plan.ADDED_NODES)
    assert after["node_count"] == before["node_count"] + 5
    assert after["control_count"] == before["control_count"] + 1
    assert "explode" in after["controls"]
    assert {n["name"]: n["callback"] for n in after["nodes"] if n["name"] in added} == {
        "explode": "TransformObject", "EXPLODE_height": "Vector3ToFloat",
        "EXPLODE_travel": "Multiply<Float>", "EXPLODE_limits": "Clamp<Float>",
        "EXPLODE_move": "sop::peak"}


def test_the_shape_is_moved_where_it_enters_the_graph():
    """Fails if the move step is not between the shape input and the node
    that read it, or if the old direct wire is left in."""
    _, geo, _ = _edited()
    wires = {(w["source"], w["source_port"], w["destination"], w["destination_port"])
             for w in _read(geo)["wires"]}
    assert ("parms", "Base.shp", "EXPLODE_move", "geo0") in wires
    assert ("EXPLODE_move", "geo0", "rest_manufacture", "parm") in wires
    assert ("parms", "Base.shp", "rest_manufacture", "parm") not in wires
    assert ("EXPLODE_limits", "result", "EXPLODE_move", "dist") in wires


def test_the_control_drives_the_amount_and_is_published():
    """Fails if the handle's height stops reaching the move, or if the rig no
    longer publishes the control's input and its two outputs."""
    _, geo, _ = _edited()
    after = _read(geo)
    wires = {(w["source"], w["source_port"], w["destination"], w["destination_port"])
             for w in after["wires"]}
    assert ("parms", "explode_t", "explode", "t") in wires
    assert ("parms", "explode_t", "EXPLODE_height", "vector") in wires
    assert ("EXPLODE_height", "y", "EXPLODE_travel", "b") in wires
    assert ("EXPLODE_travel", "result", "EXPLODE_limits", "val") in wires
    assert ("placement", "xform", "explode", "parent") in wires
    assert "explode_t" in after["graph_inputs"]
    assert {"explode", "explode_amount"} <= set(after["graph_outputs"])


def test_the_edit_sets_the_numbers_it_was_given():
    """Fails if travel, the clamp, the attribute name or the rest value are
    not the ones passed in. ``normalizeattrib`` 0 is what makes the move
    exactly offset times amount (probe, 22.0.466)."""
    graph, _, _ = _edited(travel=0.25, rest_value=0.5, handle=(0.1, 2.0, -0.2))
    assert graph.parms_of("EXPLODE_travel") == {"a": 4.0}
    assert graph.parms_of("EXPLODE_limits") == {"min": 0.0, "max": 1.0}
    assert graph.parms_of("EXPLODE_move") == {
        "usecustomattrib": 1, "customattrib": "explode_offset",
        "normalizeattrib": 0, "updatenmls": 0}
    assert graph.parms_of("explode")["restlocal"] == ("translate", (0.1, 2.0, -0.2))
    assert graph.defaults == {"explode_t": (0.0, 0.125, 0.0)}


@pytest.mark.parametrize("rest_value, height", [(-3.0, 0.0), (7.0, 0.3)])
def test_the_rest_value_is_held_between_closed_and_open(rest_value, height):
    """Fails if a rest value outside 0 to 1 reaches the rig unclamped."""
    graph, _, _ = _edited(rest_value=rest_value)
    assert graph.defaults == {"explode_t": (0.0, height, 0.0)}


def test_no_parent_leaves_the_handle_unparented():
    """Fails if a rig with no root control gets a parent wire anyway."""
    _, geo, _ = _edited(parent=None)
    assert not [w for w in _read(geo)["wires"]
                if w["destination"] == "explode" and w["destination_port"] == "parent"]


@pytest.mark.parametrize("overrides, says", [
    (dict(shape_port="Other.shp"), "no output port named Other.shp"),
    (dict(parent="nobody"), "no node named nobody"),
    (dict(travel=0.0), "travel must be above zero"),
])
def test_a_graph_it_cannot_edit_is_refused_before_anything_is_added(overrides, says):
    """Fails if a refused edit leaves a node or a wire behind."""
    apex, hou = _fake_modules()
    graph = _FakeGraph(_rig())
    with pytest.raises(ValueError) as caught:
        edit.add_explode_control(graph, apex, hou, **dict(EDIT, **overrides))
    assert says in str(caught.value)
    geo = _GraphGeo()
    graph.saveToGeometry(geo)
    assert _read(geo)["node_count"] == len(RIG_NODES)
    assert _read(geo)["wire_count"] == len(RIG_WIRES)


def test_a_rig_that_has_the_control_is_refused():
    """Fails if a second edit of the same graph is allowed to pile on."""
    _, geo, _ = _edited()
    apex, hou = _fake_modules()
    with pytest.raises(ValueError, match="already has a node named explode"):
        edit.add_explode_control(_FakeGraph(geo), apex, hou, **EDIT)


def test_a_shape_input_nobody_reads_is_refused():
    """Fails if the edit goes ahead when there is nowhere to put the move."""
    apex, hou = _fake_modules()
    graph = _FakeGraph(_GraphGeo(RIG_NODES, [w for w in RIG_WIRES if w[1] != "Base.shp"]))
    graph._port(0, "Base.shp", "out", make=True)    # the input exists; nothing reads it
    with pytest.raises(ValueError, match="nothing in the rig reads the shape input"):
        edit.add_explode_control(graph, apex, hou, **EDIT)


def test_only_the_rig_folder_is_replaced():
    """Fails if carrying the control touches the shape or the skeleton, or
    edits the rig it was handed in place."""
    apex, hou = _fake_modules()
    source = _character()
    original_rig = source.folder("Base.rig").getEmbeddedGeometry()
    own = source.copy()
    edit.carry_explode_control(own, apex, hou, rig_folder="Base.rig", **EDIT)
    assert own.folder("Base.shp").getEmbeddedGeometry() is source.folder(
        "Base.shp").getEmbeddedGeometry()
    assert own.folder("Base.skel").getEmbeddedGeometry() is source.folder(
        "Base.skel").getEmbeddedGeometry()
    assert own.folder("Base.rig").getEmbeddedGeometry() is not original_rig
    assert _read(original_rig)["node_count"] == len(RIG_NODES)
    assert "explode" in _read(own.folder("Base.rig").getEmbeddedGeometry())["controls"]


def test_a_missing_rig_folder_is_named():
    apex, hou = _fake_modules()
    with pytest.raises(ValueError, match="no folder named Other.rig"):
        edit.carry_explode_control(_character(), apex, hou, rig_folder="Other.rig", **EDIT)


# ===========================================================================
# 2. The node's code: one source, and nothing Houdini would expand
# ===========================================================================

def _code(**overrides):
    values = dict(rig_folder="Base.rig", shape_port="Base.shp", parent="placement",
                  travel=0.3, handle=(0.0, 1.35, 0.0))
    values.update(overrides)
    return plan.node_code(**values)


def test_the_node_carries_the_source_of_the_tested_functions():
    """One source. Fails if the code in the node is anything but the text of
    the two functions this file tests."""
    code = _code()
    for function in (edit.add_explode_control, edit.carry_explode_control):
        assert inspect.getsource(function).rstrip() in code


def test_every_line_of_the_node_code_is_ours():
    """The code is a fixed program over the rig's own names and measured
    numbers. Fails if it grows an import, or a call that reaches outside the
    geometry it is handed."""
    code = _code()
    lines = code.splitlines()
    assert lines[0].startswith("# SYNAPSE: explode control. Written by SYNAPSE")
    assert [ln for ln in lines if ln.startswith(("import ", "from "))] == [
        "import apex", "import hou"]
    for banned in ("open(", "exec(", "eval(", "__import__", "os.", "subprocess",
                   "hou.node(", "setFrame", "hou.hipFile", "hou.session"):
        assert banned not in code


def test_the_code_holds_nothing_houdini_would_expand():
    """Houdini expands a Python SOP's code as a string parameter before Python
    runs it: a doubled backslash arrived single on 22.0.466, and a dollar sign
    or a backtick starts a variable or an expression. Fails if either file
    that ends up in the node gains one of the three."""
    source = inspect.getsource(edit)
    for mark in plan.EXPANDED_BY_HOUDINI:
        assert mark not in source, "apex_explode_edit.py holds %r" % mark
        assert mark not in _code()


@pytest.mark.parametrize("field", ["rig_folder", "shape_port", "parent"])
@pytest.mark.parametrize("bad", ["a\\b", "a$b", "a`b", "", "x" * 201, "two\nlines", 7])
def test_a_name_that_is_not_plain_is_refused(field, bad):
    """Names reach the code as Python literals. Fails if one that Houdini
    would expand, or that is not a short printable string, gets in."""
    with pytest.raises(ValueError):
        _code(**{field: bad})


@pytest.mark.parametrize("overrides", [
    dict(travel=0.0), dict(travel=float("nan")), dict(travel=float("inf")),
    dict(handle=(0.0, float("nan"), 0.0)), dict(handle=(0.0, 1.0)),
])
def test_a_number_that_is_not_usable_is_refused(overrides):
    with pytest.raises(ValueError):
        _code(**overrides)


def test_the_code_reads_its_values_as_written():
    """Fails if a value is written into the code in a form that does not read
    back as the value."""
    namespace = {}
    head = _code(parent=None, travel=0.25, handle=(0.5, 2.0, -1.0)).split("\n\n\ndef ")[0]
    exec(compile(head.replace("import apex\nimport hou\n", ""), "<head>", "exec"), namespace)
    assert namespace["RIG_FOLDER"] == "Base.rig"
    assert namespace["SHAPE_PORT"] == "Base.shp"
    assert namespace["PARENT"] is None
    assert namespace["TRAVEL"] == 0.25
    assert namespace["HANDLE"] == (0.5, 2.0, -1.0)
    assert namespace["ATTRIBUTE"] == plan.OFFSET_ATTRIBUTE
    assert namespace["SLIDER"] == plan.SLIDER


# ===========================================================================
# 3. The plan: which node, which rig, what it stops for
# ===========================================================================

def test_a_character_is_a_rig_folder_with_a_shape_beside_it():
    found = plan.characters_in(_character())
    assert [(c["name"], c["rig_folder"], c["shape_folder"]) for c in found] == [
        ("Base", "Base.rig", "Base.shp")]


def test_a_scene_does_not_count_as_a_character():
    """A scene holds its character one folder down. Fails if the tool would
    edit the rig inside a scene instead of where the character is packed."""
    scene = _Packed([("ovoid", _character())])
    assert plan.characters_in(scene) == []


def test_a_rig_folder_without_a_graph_or_a_shape_is_not_a_character():
    assert plan.characters_in(_Packed([("Base.rig", _Shape()), ("Base.shp", _Shape())])) == []
    assert plan.characters_in(_Packed([("Base.rig", _rig())])) == []
    assert plan.characters_in(_Shape()) == []


def test_the_plan_follows_the_rigs_one_root_control():
    """Fails if the handle's parent is not the control with nothing wired to
    its own parent. On the production rig that is ``placement`` (probe)."""
    chosen = plan.plan_edit(_read(_rig()), "Base.shp")
    assert chosen["parent"] == "placement"
    assert chosen["shape_readers"] == 1
    assert chosen["before"]["node_count"] == len(RIG_NODES)


def test_two_root_controls_leave_the_handle_unparented_and_say_so():
    nodes = RIG_NODES + [("second_root", "TransformObject", ("control",))]
    chosen = plan.plan_edit(_read(_rig(nodes)), "Base.shp")
    assert chosen["parent"] is None
    assert "2 root controls" in chosen["parent_note"]
    assert "world space" in chosen["parent_note"]


def test_no_root_control_leaves_the_handle_unparented_and_says_so():
    nodes = [(n, c, ()) for n, c, _ in RIG_NODES]
    chosen = plan.plan_edit(_read(_rig(nodes)), "Base.shp")
    assert chosen["parent"] is None
    assert "no root control" in chosen["parent_note"]


@pytest.mark.parametrize("graph, says", [
    (None, "could not be read"),
    ({"read": False, "reason": "graph has 30000 nodes"}, "30000 nodes"),
])
def test_an_unreadable_rig_is_refused(graph, says):
    with pytest.raises(SynapseUserError) as caught:
        plan.plan_edit(graph, "Base.shp")
    assert says in str(caught.value)


def test_a_rig_whose_wires_were_not_all_read_is_refused():
    """The edit places wires by name. Fails if it plans on a partial read."""
    graph = _read(_rig())
    graph["wires_status"] = "partly read"
    with pytest.raises(SynapseUserError, match="needs all of them"):
        plan.plan_edit(graph, "Base.shp")


def test_a_rig_with_the_control_is_refused_with_a_way_to_check():
    _, geo, _ = _edited()
    with pytest.raises(SynapseUserError) as caught:
        plan.plan_edit(_read(geo), "Base.shp")
    assert "already has" in str(caught.value)
    assert "synapse_inspect_node" in caught.value.suggestion


def test_a_published_name_is_found_past_the_summarys_cap():
    """The reader's input and output lists stop at NAME_LIST_CAP names. Fails
    if a rig with more inputs than that hides an ``explode_t`` it already has."""
    extra = ["in_%03d" % i for i in range(apex_graph.NAME_LIST_CAP + 5)]
    nodes = RIG_NODES + [("sink", "TransformObject", ())]
    wires = RIG_WIRES + [("parms", name, "sink", "t") for name in extra[:1]]
    graph = _read(_rig(nodes, wires))
    graph["wires"] = graph["wires"] + [
        {"source": "parms", "source_port": name, "destination": "sink",
         "destination_port": "r"} for name in extra[1:]] + [
        {"source": "parms", "source_port": "explode_t", "destination": "sink",
         "destination_port": "s"}]
    graph["graph_inputs"] = graph["graph_inputs"][:apex_graph.NAME_LIST_CAP]
    assert "explode_t" not in graph["graph_inputs"]
    with pytest.raises(SynapseUserError, match="already has explode_t"):
        plan.plan_edit(graph, "Base.shp")


def test_a_rig_that_takes_its_shape_another_way_is_refused():
    with pytest.raises(SynapseUserError, match="graph input named Other.shp"):
        plan.plan_edit(_read(_rig()), "Other.shp")


def test_two_nodes_sharing_a_name_are_refused():
    nodes = RIG_NODES + [("placement2", "TransformObject", ())]
    graph = _read(_rig(nodes))
    graph["nodes"][-1]["name"] = "placement"
    with pytest.raises(SynapseUserError, match="share a name"):
        plan.plan_edit(graph, "Base.shp")


def test_the_shape_facts_count_what_moves():
    """Fails if the count of moving points, the largest move or the bounds
    are not read from the shape itself."""
    facts = plan.shape_facts(_Shape())
    assert facts["points"] == 4
    assert facts["points_that_move"] == 2
    assert facts["largest_move"] == pytest.approx(0.215407, abs=1e-5)
    assert facts["height"] == 1.2 and facts["top"] == 1.2
    assert facts["centre"] == [0.0, 0.0]


def test_an_asset_without_offsets_is_refused_and_told_what_it_needs():
    """The directions are the asset's. Fails if the tool would invent them
    for an asset that carries none."""
    with pytest.raises(SynapseUserError) as caught:
        plan.shape_facts(_Shape(attribute="something_else"))
    assert "no point attribute named explode_offset" in str(caught.value)
    assert "come from the asset" in caught.value.suggestion


@pytest.mark.parametrize("shape, says", [
    (_Shape(kind="Int"), "float attribute three wide"),
    (_Shape(size=4, offsets=[(0.0, 0.0, 0.0, 0.0)]), "float attribute three wide"),
    (_Shape(offsets=[(0.0, 0.0, 0.0)] * 3), "is zero"),
    (_Shape(offsets=[(0.0, float("nan"), 0.0)]), "not a finite number"),
    (_Shape(low=(0.0, 1.0, 0.0), high=(1.0, 1.0, 1.0)), "no height"),
])
def test_offsets_that_cannot_drive_an_explode_are_refused(shape, says):
    with pytest.raises(SynapseUserError) as caught:
        plan.shape_facts(shape)
    assert says in str(caught.value)


def test_the_control_is_sized_from_the_asset():
    """A quarter of the height to travel, an eighth of it above the top. On
    the production asset (1.2 tall) that is 0.3 and 1.35, the hand test's."""
    travel, handle = plan.sizes(plan.shape_facts(_Shape()))
    assert travel == 0.3
    assert handle == (0.0, 1.35, 0.0)


def test_a_given_travel_is_used_and_a_bad_one_refused():
    facts = plan.shape_facts(_Shape())
    assert plan.sizes(facts, 0.5)[0] == 0.5
    for bad in (0, -1.0, float("nan"), "far", True):
        with pytest.raises(SynapseUserError):
            plan.sizes(facts, bad)


# ===========================================================================
# 4. The build, on a stand-in network that runs the generated code
# ===========================================================================

class _Parm:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class _Connection:
    def __init__(self, consumer, input_index, output_index=0):
        self._consumer, self._input, self._output = consumer, input_index, output_index

    def outputNode(self):
        return self._consumer

    def inputIndex(self):
        return self._input

    def outputIndex(self):
        return self._output


class _Node:
    """A SOP node. A plain class with no ``__getattr__``: anything the core
    touches that is not modelled raises AttributeError and fails the test."""

    def __init__(self, network, name, geo=None, dirty=False, type_name="null"):
        self.network = network
        self._name = name
        self._geo = geo
        self._dirty = dirty
        self._type = type_name
        self._inputs = {}           # input index -> (source node, output index)
        self._user_data = {}
        self._parms = {}
        self._errors = []
        self.comment = None
        self.moved = 0
        self.geometry_reads = 0
        self.destroyed = False

    def name(self):
        return self._name

    def path(self):
        return "%s/%s" % (self.network.path(), self._name)

    def parent(self):
        return self.network

    def type(self):
        return _Named(self._type)

    def inputs(self):
        if not self._inputs:
            return ()
        return tuple(self._inputs.get(i, (None, 0))[0] for i in range(max(self._inputs) + 1))

    def setInput(self, index, source, output_index=0):
        if source is None:
            self._inputs.pop(index, None)
        else:
            self._inputs[index] = (source, output_index)

    def outputConnections(self):
        found = []
        for other in self.network.nodes:
            for index, (source, output_index) in sorted(other._inputs.items()):
                if source is self:
                    found.append(_Connection(other, index, output_index))
        return found

    def needsToCook(self):
        return self._dirty

    def geometry(self):
        self.geometry_reads += 1
        return self._geo

    def errors(self):
        return tuple(self._errors)

    def userData(self, key):
        return self._user_data.get(key)

    def setUserData(self, key, value):
        self._user_data[key] = value

    def parm(self, name):
        return self._parms.get(name)

    def evalParm(self, name):
        return self._parms[name].value

    def setComment(self, text):
        self.comment = text

    def moveToGoodPosition(self):
        self.moved += 1

    def destroy(self):
        self.destroyed = True
        self.network.nodes.remove(self)


class _PythonSop(_Node):
    """A Python SOP: its geometry is its input's, copied, after its own code
    has run on the copy. The code is the text in its ``python`` parameter."""

    def __init__(self, network, name):
        super().__init__(network, name, type_name="python")
        self._parms["python"] = _Parm()

    def needsToCook(self):
        return False

    def geometry(self):
        self.geometry_reads += 1
        self._errors = []
        source = self._inputs[0][0].geometry()
        own = source.copy()
        apex, hou = _fake_modules(current_node=_Cooking(self, own),
                                  graph_class=self.network.graph_class)
        try:
            with _modules_installed(apex, hou):
                exec(compile(self._parms["python"].value, self.path(), "exec"),
                     {"__name__": "__node__"})
        except _NodeError as problem:
            self._errors = [str(problem)]
            return None
        except Exception as problem:   # what Houdini reports as a Python error
            self._errors = ["Python error: %r" % (problem,)]
            return None
        return own


class _Cooking:
    """``hou.pwd()`` while a Python SOP cooks: the node, and its own geometry."""

    def __init__(self, node, geo):
        self._node, self._geo = node, geo

    def geometry(self):
        return self._geo

    def evalParm(self, name):
        return self._node.evalParm(name)


class _Network:
    def __init__(self, path="/obj/OVOID_HERO_MODEL"):
        self._path = path
        self.nodes = []
        self.graph_class = _FakeGraph
        self.created = []

    def path(self):
        return self._path

    def node(self, name):
        return next((n for n in self.nodes if n.name() == name), None)

    def add(self, name, geo=None, dirty=False, inputs=(), type_name="null"):
        node = _Node(self, name, geo=geo, dirty=dirty, type_name=type_name)
        for index, source in enumerate(inputs):
            if source is not None:
                node.setInput(index, source)
        self.nodes.append(node)
        return node

    def createNode(self, type_name, name):
        assert type_name == "python", "the tool creates one Python SOP and nothing else"
        node = _PythonSop(self, name)
        self.nodes.append(node)
        self.created.append(node)
        return node


class _Undo:
    """Counts undo groups, and holds the label the handler would pass."""

    def __init__(self):
        self.opened = 0
        self.closed = 0

    @contextlib.contextmanager
    def group(self):
        self.opened += 1
        try:
            yield
        finally:
            self.closed += 1


def _scene(shape=None, rig=None):
    """The production network's shape: a shape cache, a rig build and a
    skeleton feed the node that packs the character; a Rig Pose and a scene
    chain both read it; the scene chain ends in a posed mesh."""
    net = _Network()
    character = _character(rig=rig, shape=shape)
    cache = net.add("LIFT_07_REST_CACHE", geo=_Shape())
    build = net.add("APEX_BUILD_MECHANICAL_RIG", geo=_rig())
    skel = net.add("APEX_REST_SKELETON", geo=_skeleton())
    packer = net.add("APEX_CHARACTER_DATA", geo=character, inputs=(cache, build, skel))
    pose = net.add("ANIMATE_OVOID_APEX", geo=character, inputs=(packer,))
    scene = net.add("APEX_PERFORMANCE_SCENE", geo=_Packed([("ovoid", character)]),
                    inputs=(None, packer))
    animate = net.add("ANIMATE_OVOID_SCENE", geo=_Packed([("ovoid", character)]),
                      inputs=(scene,))
    invoke = net.add("APEX_INVOKE_PERFORMANCE", geo=_Shape(), inputs=(animate,))
    return net, dict(packer=packer, pose=pose, scene=scene, animate=animate, invoke=invoke,
                     cache=cache)


def _clean(node):
    """The handler's reader: a node that would have to cook is not read."""
    return None if node.needsToCook() else node.geometry()


def _slider(node):
    node._parms[plan.SLIDER] = _Parm()
    node._parms[plan.SLIDER].value = 0.0


def _run(node, undo=None, **kwargs):
    undo = undo or _Undo()
    result = handlers_apex.add_explode_control_core(
        node, read_geometry=_clean, add_slider=_slider,
        undo_context_factory=undo.group, **kwargs)
    return result, undo


@pytest.mark.parametrize("asked_at", ["packer", "pose", "animate", "invoke"])
def test_the_control_goes_in_after_the_node_that_packs_the_character(asked_at):
    """Whichever node is passed, the control goes in once, after the packer,
    and every node that read the packer reads the new node instead. Fails if
    asking at the Rig Pose leaves the scene chain without the control."""
    net, nodes = _scene()
    result, undo = _run(nodes[asked_at])
    assert result["status"] == "created"
    assert result["character_node"] == nodes["packer"].path()
    assert len(net.created) == 1
    carrier = net.created[0]
    assert carrier.name() == plan.CARRIER_NAME
    assert result["node"] == carrier.path()
    assert carrier.inputs() == (nodes["packer"],)
    assert nodes["pose"].inputs()[0] is carrier
    assert nodes["scene"].inputs() == (None, carrier)
    assert result["rewired"] == [
        {"node": nodes["pose"].path(), "input": 0},
        {"node": nodes["scene"].path(), "input": 1}]
    assert (undo.opened, undo.closed) == (1, 1)


def test_the_build_is_read_back_from_the_new_node():
    """Fails if the result reports counts it did not read out of the new
    node's own output, or if the packed rig upstream was edited in place."""
    net, nodes = _scene()
    result, _ = _run(nodes["animate"])
    assert result["before"]["node_count"] == len(RIG_NODES)
    assert result["after"]["node_count"] == len(RIG_NODES) + 5
    assert result["after"]["control_count"] == result["before"]["control_count"] + 1
    assert result["control_follows"] == "placement"
    upstream = nodes["packer"].geometry().folder("Base.rig").getEmbeddedGeometry()
    assert _read(upstream)["node_count"] == len(RIG_NODES)
    handed_on = net.created[0].geometry().folder("Base.rig").getEmbeddedGeometry()
    assert "explode" in _read(handed_on)["controls"]


def test_the_new_node_is_marked_and_carries_the_slider_and_generated_code():
    net, nodes = _scene()
    result, _ = _run(nodes["packer"])
    carrier = net.created[0]
    assert carrier.userData(plan.MARKER_KEY) == plan.MARKER_VALUE
    assert carrier.parm(plan.SLIDER) is not None
    assert result["slider"] == carrier.path() + "/explode"
    assert carrier.parm("python").value == plan.node_code(
        rig_folder="Base.rig", shape_port="Base.shp", parent="placement",
        travel=0.3, handle=(0.0, 1.35, 0.0))
    assert carrier.comment == "SYNAPSE: explode control"
    assert carrier.moved == 1


def test_the_slider_sets_where_the_control_rests():
    """Fails if the slider's value does not reach the rig the node hands on."""
    net, nodes = _scene()
    _run(nodes["packer"])
    carrier = net.created[0]
    seen = {}

    class _Recording(_FakeGraph):
        def setDefaultParms(self, values, flag):
            seen.update(values)
            super().setDefaultParms(values, flag)

    net.graph_class = _Recording
    carrier.parm(plan.SLIDER).value = 0.5
    carrier.geometry()
    assert seen == {"explode_t": (0.0, 0.15, 0.0)}


def test_the_result_says_what_was_done_and_how_to_undo_it():
    net, nodes = _scene()
    result, _ = _run(nodes["packer"])
    assert result["points"] == 4 and result["points_that_move"] == 2
    assert result["travel"] == 0.3 and result["handle"] == [0.0, 1.35, 0.0]
    assert result["offset_attribute"] == "explode_offset"
    assert "Added the explode control to Base.rig in one new node" in result["outcome"]
    assert "2 of the shape's 4 points move" in result["outcome"]
    assert "the asset's own explode_offset" in result["outcome"]
    assert "not from SYNAPSE" in result["reasoning"]
    assert result["undo"]["label"] == "SYNAPSE: Add explode control"
    assert result["undo"]["rolls_back_on_failure"] is True


def test_the_result_is_plain_json():
    """The result goes to the model as one JSON text block with sorted keys.
    Fails if it holds a tuple key, a node object or anything json cannot
    write without help."""
    net, nodes = _scene()
    result, _ = _run(nodes["invoke"])
    again = json.loads(json.dumps(result, sort_keys=True))
    assert again == result


def test_a_given_travel_reaches_the_node():
    net, nodes = _scene()
    result, _ = _run(nodes["packer"], travel=0.6)
    assert result["travel"] == 0.6
    assert "TRAVEL = 0.6" in net.created[0].parm("python").value


@pytest.mark.parametrize("asked_at", ["packer", "pose", "invoke", "carrier"])
def test_a_second_call_finds_its_own_node_and_changes_nothing(asked_at):
    """Fails if a second call adds a second node, opens an undo group, or
    cannot find the first call's node when asked at that node itself."""
    net, nodes = _scene()
    first, _ = _run(nodes["packer"])
    nodes["carrier"] = net.created[0]
    again, undo = _run(nodes[asked_at])
    assert again["status"] == "unchanged"
    assert again["node"] == first["node"]
    assert again["control_listed"] is True
    assert len(net.created) == 1
    assert undo.opened == 0
    assert "undo" not in again
    assert "nothing was changed" in again["outcome"]
    assert json.loads(json.dumps(again, sort_keys=True)) == again


def test_a_second_node_name_is_found_when_the_first_is_taken():
    """An artist's own node may already hold the name. Fails if the tool
    overwrites it or stops."""
    net, nodes = _scene()
    net.add(plan.CARRIER_NAME, geo=_Shape())
    result, _ = _run(nodes["packer"])
    assert result["node"].endswith("/%s2" % plan.CARRIER_NAME)


def _unchanged(net, nodes, undo):
    assert net.created == []
    assert undo.opened == 0
    assert nodes["pose"].inputs()[0] is nodes["packer"]
    assert nodes["scene"].inputs() == (None, nodes["packer"])


def test_no_character_at_or_above_the_node_is_refused():
    net, nodes = _scene()
    undo = _Undo()
    with pytest.raises(SynapseUserError, match="no APEX character at or above"):
        _run(nodes["cache"], undo)
    _unchanged(net, nodes, undo)


def test_a_rig_that_is_not_cooked_is_never_cooked_to_find_it():
    """No forced cook. Fails if a dirty node's geometry is read, or if the
    refusal does not say how to get the rig cooked."""
    net, nodes = _scene()
    for name in ("packer", "pose", "scene", "animate"):
        nodes[name]._dirty = True
    undo = _Undo()
    with pytest.raises(SynapseUserError) as caught:
        _run(nodes["invoke"], undo)
    assert "not cooked" in str(caught.value)
    assert "does not force a cook" in str(caught.value)
    assert "Display the rig's node" in caught.value.suggestion
    assert nodes["packer"].geometry_reads == 0
    assert nodes["animate"].geometry_reads == 0
    _unchanged(net, nodes, undo)


def test_an_asset_without_offsets_changes_nothing():
    net, nodes = _scene(shape=_Shape(attribute="something_else"))
    undo = _Undo()
    with pytest.raises(SynapseUserError, match="no point attribute named explode_offset"):
        _run(nodes["animate"], undo)
    _unchanged(net, nodes, undo)


def test_two_characters_in_one_node_are_refused():
    net, nodes = _scene()
    nodes["packer"]._geo = _Packed([
        ("Base.rig", _rig()), ("Base.shp", _Shape()),
        ("Other.rig", _rig()), ("Other.shp", _Shape())])
    undo = _Undo()
    with pytest.raises(SynapseUserError, match="packs 2 characters"):
        _run(nodes["packer"], undo)
    _unchanged(net, nodes, undo)


def test_a_build_that_does_not_cook_is_taken_back_out():
    """The node's code fails on this build (a callback is missing). Fails if
    the half-built node or its wires are left in the network, or if the error
    does not say the network was left as it was."""
    net, nodes = _scene()

    class _NoPeak(_FakeGraph):
        callbacks_missing = ("sop::peak",)

    net.graph_class = _NoPeak
    undo = _Undo()
    with pytest.raises(SynapseUserError) as caught:
        _run(nodes["animate"], undo)
    assert "The control was not added" in str(caught.value)
    assert "left as it was" in caught.value.suggestion
    assert len(net.created) == 1 and net.created[0].destroyed
    assert net.node(plan.CARRIER_NAME) is None
    assert nodes["pose"].inputs()[0] is nodes["packer"]
    assert nodes["scene"].inputs() == (None, nodes["packer"])
    assert (undo.opened, undo.closed) == (1, 1)


def test_a_build_whose_rig_lacks_the_control_is_taken_back_out():
    """The node cooks but hands on a rig without the control. Fails if the
    core reports success without having seen the control in the output."""
    net, nodes = _scene()

    class _SavesNothingNew(_FakeGraph):
        def saveToGeometry(self, geo):
            geo.load(RIG_NODES, RIG_WIRES)

    net.graph_class = _SavesNothingNew
    with pytest.raises(SynapseUserError, match="explode control is not in the rig"):
        _run(nodes["packer"])
    assert net.node(plan.CARRIER_NAME) is None
    assert nodes["pose"].inputs()[0] is nodes["packer"]


# ===========================================================================
# 5. The tables: one build tool, review-gated, with no code in its schema
# ===========================================================================

TOOL = "synapse_add_explode_control"
COMMAND = "add_explode_control"


def test_the_tool_is_registered_as_a_build_with_no_code_in_its_schema():
    """Fails if the schema grows a field that could carry code, a node name
    or a direction, or if the tool is marked read-only or destructive."""
    import synapse.mcp._tool_registry as tr

    assert tr.TOOL_DISPATCH[TOOL][0] == COMMAND
    schema = tr.TOOL_JSON[TOOL]["inputSchema"]
    assert set(schema["properties"]) == {"node", "travel"}
    assert schema["required"] == ["node"]
    assert schema["properties"]["node"]["type"] == "string"
    assert schema["properties"]["travel"]["type"] == "number"
    hints = tr.TOOL_JSON[TOOL]["annotations"]
    assert hints["readOnlyHint"] is False
    assert hints["destructiveHint"] is False
    assert hints["idempotentHint"] is True, "a second call changes nothing"


def test_the_payload_drops_anything_but_the_node_and_the_travel():
    import synapse.mcp._tool_registry as tr

    builder = tr.TOOL_DISPATCH[TOOL][1]
    assert builder({"node": "/obj/a/b", "travel": 0.4, "code": "import os", "name": "x"}) == {
        "node": "/obj/a/b", "travel": 0.4}


def test_the_description_says_where_the_directions_come_from():
    """The model reads this to decide what to promise. Fails if it stops
    saying the directions are the asset's, or that nothing is force-cooked."""
    import synapse.mcp._tool_registry as tr

    text = tr.TOOL_JSON[TOOL]["description"]
    assert "explode_offset" in text
    assert "the asset's own" in text
    assert "refuses an asset that has none" in text
    assert "one undo step" in text
    assert "nothing is force-cooked" in text


def test_the_command_is_registered_and_is_a_mutation():
    import synapse.server.handlers as h

    assert hasattr(h.SynapseHandler, "_handle_add_explode_control")
    assert COMMAND not in h._READ_ONLY_COMMANDS
    assert h.SynapseHandler()._registry.get(COMMAND) is not None


def test_the_tool_is_review_gated_and_never_read_only():
    import synapse.panel.bridge_adapter as ba
    from shared.constants import OPERATION_GATES

    assert ba._TOOL_TO_OPERATION[TOOL] == "build_rig_logic"
    assert OPERATION_GATES["build_rig_logic"] == "review"
    assert ba.is_read_only(TOOL) is False
    assert TOOL not in ba._READ_ONLY_TOOLS
    assert TOOL not in ba._DISK_WRITING_TOOLS


def test_an_artist_may_run_it_and_a_viewer_may_not():
    import synapse.server.rbac as rbac

    assert COMMAND in rbac._ARTIST_COMMANDS
    assert COMMAND not in rbac._VIEWER_COMMANDS
    assert rbac.check_permission(rbac.Role.VIEWER, COMMAND) is False
    assert rbac.check_permission(rbac.Role.ARTIST, COMMAND) is True


def test_the_build_has_the_build_time_budget():
    """Fails if a client would give the build the 10 s default, by command
    name or by tool name."""
    from synapse.core import timeouts

    assert timeouts.timeout_for(COMMAND) == 30.0
    assert timeouts.timeout_for(TOOL) == 30.0


def test_the_one_rig_tool_is_the_one_the_boundary_names():
    """Rule D-H22-3 keeps SYNAPSE off rig authoring, with one recorded
    exception. Fails if a second tool is mapped to the rig-logic gate, or if
    the boundary document stops naming this one."""
    from pathlib import Path

    import synapse.panel.bridge_adapter as ba

    rig_tools = sorted(t for t, op in ba._TOOL_TO_OPERATION.items() if op == "build_rig_logic")
    assert rig_tools == [TOOL]
    boundary = (Path(__file__).resolve().parents[1] / "docs"
                / "SYNAPSE_H22_BOUNDARY.md").read_text(encoding="utf-8")
    section = boundary.split("## 6 ·", 1)[1].split("\n## ", 1)[0]
    assert "Exception" in section and TOOL in section


def _through_the_bridge(monkeypatch, tool, command_type, payload):
    """What the panel's bridge is handed for one tool call: the Operation."""
    from types import SimpleNamespace

    from synapse.core.protocol import SynapseCommand, SynapseResponse
    from synapse.panel import bridge_adapter

    operations = []
    command = SynapseCommand(type=command_type, id="label-test", payload=payload)
    response = SynapseResponse(id=command.id, success=True, data={"status": "SUCCESS"})

    class Bridge:
        def execute(self, operation):
            operations.append(operation)
            return SimpleNamespace(success=True, result=operation.fn(), integrity=None)

    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: Bridge())
    handler = SimpleNamespace(handle=lambda received: response if received is command else None)
    assert bridge_adapter.execute_through_bridge(tool, handler, command) is response
    assert len(operations) == 1
    return operations[0]


def test_the_undo_step_is_named_in_words(monkeypatch):
    """Houdini's Edit menu shows the bridge's group, which is named from the
    Operation's summary. Fails if the step would read as a tool name and its
    arguments, or under another name than the tool's own result reports."""
    from synapse.panel import turn_revert
    from synapse.server.handler_helpers import undo_receipt

    operation = _through_the_bridge(monkeypatch, TOOL, COMMAND, {"node": "/obj/rig/pack"})
    shown = "SYNAPSE: " + operation.summary     # shared/bridge.py opens the group under this
    assert shown == "SYNAPSE: Add explode control"
    assert shown == plan.UNDO_LABEL == handlers_apex.UNDO_LABEL
    assert "synapse_add" not in shown and "{" not in shown
    assert turn_revert.is_synapse_label(shown)  # REVERT still knows the step as SYNAPSE's
    assert operation.operation_type == "build_rig_logic"
    assert operation.kwargs["node_path"] == "/obj/rig/pack"     # the target reaches integrity
    with_travel = _through_the_bridge(monkeypatch, TOOL, COMMAND,
                                      {"node": "/obj/rig/pack", "travel": 0.5})
    assert with_travel.summary == operation.summary             # one step, one name
    receipt = undo_receipt(plan.UNDO_LABEL, rolls_back_on_failure=True)["undo"]
    assert receipt["artist"] == "One Ctrl+Z reverses: Add explode control"
