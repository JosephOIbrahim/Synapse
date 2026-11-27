"""hython: synapse_add_explode_control against the real ``apex`` and ``hou``.

``tests/test_apex_explode_tool.py`` runs the generated code against stand-ins.
This module closes the loop on Houdini itself. It builds a small character in
a scratch network (a shape that carries ``explode_offset``, a rig built with
``apex.Graph``, and a node that packs them), calls the handler the MCP tool
calls, and checks what only a real session can show:

  * the code SYNAPSE wrote is what the Python SOP runs (the parameter does
    not change it), and the node cooks;
  * the rig it hands on moves each point by its own offset times the amount,
    clamps at closed and open, and leaves the packed rig upstream as it was;
  * the slider sets where the control rests;
  * one undo takes the node and the wires back, and one redo returns them;
  * a rig that is not cooked is refused without being cooked.

Runs only under hython (apex/hou). The module-level importorskip self-gates
it: plain pytest skips the module at collection and prints the reason. That
skip is not a pass. Run it for real via:

    python .synapse/hytest.py tests/test_apex_explode_tool_hython.py

Every test builds its own network under /obj and removes it afterwards. The
code written into the scratch Python SOPs holds no backslash, dollar sign or
backtick, for the reason apex_explode.EXPANDED_BY_HOUDINI gives.
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("hou")
pytest.importorskip("apex")

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "python") not in sys.path:
    sys.path.insert(0, str(_REPO / "python"))

import apex  # noqa: E402
import hou  # noqa: E402

from synapse.core.errors import SynapseUserError  # noqa: E402
from synapse.server import apex_explode as plan  # noqa: E402
from synapse.server import apex_graph  # noqa: E402
from synapse.server import handlers_apex  # noqa: E402

# Two quads. The first does not move; the second moves by OFFSET at full explode.
OFFSET = (0.5, 0.25, 0.0)

SHAPE_CODE = """
node = hou.pwd()
geo = node.geometry()
WITH_OFFSETS = %(with_offsets)r
if WITH_OFFSETS:
    geo.addAttrib(hou.attribType.Point, 'explode_offset', (0.0, 0.0, 0.0))
for x, offset in ((0.0, (0.0, 0.0, 0.0)), (2.0, %(offset)r)):
    poly = geo.createPolygon()
    for dx, dy in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)):
        point = geo.createPoint()
        point.setPosition((x + dx, dy, 0.0))
        if WITH_OFFSETS:
            point.setAttribValue('explode_offset', offset)
        poly.addVertex(point)
"""

RIG_CODE = """
import apex
node = hou.pwd()
geo = node.geometry()
g = apex.Graph()
parms = g.addNode('parms', '__parms__')
out = g.addNode('output', '__output__')
placement = g.addNode('placement', 'TransformObject')
rest = g.addNode('rest_shape', 'Value<Geometry>')
pose = g.addNode('body_deform', 'geo::Transform')
g.promoteInput(g.getPort(placement, 't[in]'), parms, 'placement_t')
g.promoteOutput(g.getPort(placement, 'xform[out]'), out, 'placement')
g.promoteInput(g.getPort(rest, 'parm[in]'), parms, 'Base.shp')
g.addWire(g.getPort(rest, 'value[out]'), g.getPort(pose, 'geo[in]'))
g.addWire(g.getPort(placement, 'xform[out]'), g.getPort(pose, 'xform[in]'))
g.promoteOutput(g.getPort(pose, 'geo[out]'), out, 'Base.shp')
g.setNodeTag(placement, 'control')
g.saveToGeometry(geo)
"""

PACK_CODE = """
import apex
node = hou.pwd()
geo = node.geometry()
geo.clear()
apex.packToFolders(geo, apex.Dict({
    'Base.shp': node.inputs()[0].geometry(),
    'Base.rig': node.inputs()[1].geometry(),
}))
"""


class _Scratch:
    """A character in its own network: shape and rig feed a packer, and two
    nodes read the packer. Removed on exit."""

    def __init__(self, with_offsets=True, cook=True):
        self.with_offsets = with_offsets
        self.cook = cook

    def __enter__(self):
        self.net = hou.node("/obj").createNode("geo", "synapse_explode_test")
        self.shape = self._python("shape", SHAPE_CODE % {
            "with_offsets": self.with_offsets, "offset": OFFSET})
        self.rig = self._python("rig", RIG_CODE)
        self.packer = self._python("pack_character", PACK_CODE)
        self.packer.setInput(0, self.shape)
        self.packer.setInput(1, self.rig)
        self.reader_a = self.net.createNode("null", "reader_a")
        self.reader_a.setInput(0, self.packer)
        self.reader_b = self.net.createNode("null", "reader_b")
        self.reader_b.setInput(0, self.packer)
        if self.cook:
            for node in (self.packer, self.reader_a, self.reader_b):
                node.geometry()
                assert not node.errors(), node.errors()
        return self

    def _python(self, name, code):
        node = self.net.createNode("python", name)
        node.parm("python").set(code)
        return node

    def __exit__(self, *exc):
        self.net.destroy()
        return False


def _call(node, **payload):
    """The handler the MCP tool dispatches to, with the tool's own payload."""
    return handlers_apex.ApexHandlerMixin()._handle_add_explode_control(
        dict(payload, node=node.path()))


def _folder(node, name):
    for prim in node.geometry().prims():
        if prim.attribValue("name") == name:
            return prim.getEmbeddedGeometry()
    raise AssertionError("no folder named %s in %s" % (name, node.path()))


def _posed(node, explode_t=None):
    """The shape the rig *node* hands on poses, as point positions."""
    graph = apex.Graph(_folder(node, "Base.rig"))
    data = {"Base.shp": _folder(node, "Base.shp")}
    if explode_t is not None:
        data["explode_t"] = hou.Vector3(*explode_t)
    graph.setParms(data)
    posed = graph.evaluateOutput("output:Base.shp")
    assert not graph.executionErrors(), graph.executionErrors()
    return [tuple(round(c, 5) for c in p.position()) for p in posed.points()]


def _moved(rest, now):
    return [tuple(round(n - r, 5) for n, r in zip(b, a)) for a, b in zip(rest, now)]


def test_the_handler_adds_one_node_after_the_packer_and_rewires_its_readers():
    with _Scratch() as s:
        result = _call(s.reader_a)
        carrier = hou.node(result["node"])
        assert result["status"] == "created"
        assert result["character_node"] == s.packer.path()
        assert carrier is not None and carrier.name() == plan.CARRIER_NAME
        assert carrier.type().name() == "python"
        assert carrier.inputs() == (s.packer,)
        assert s.reader_a.inputs() == (carrier,)
        assert s.reader_b.inputs() == (carrier,)
        assert carrier.userData(plan.MARKER_KEY) == plan.MARKER_VALUE
        assert not carrier.errors()
        assert result["control_follows"] == "placement"
        assert result["points"] == 8 and result["points_that_move"] == 4
        assert result["travel"] == 0.25          # a quarter of a shape 1.0 tall
        assert result["handle"] == [1.5, 1.125, 0.0]


def test_the_code_that_was_written_is_the_code_that_runs():
    """Houdini expands the code as a string parameter. If the expanded text
    differs from what SYNAPSE wrote, the node is not running SYNAPSE's code."""
    with _Scratch() as s:
        result = _call(s.packer)
        parm = hou.node(result["node"]).parm("python")
        written = plan.node_code(rig_folder="Base.rig", shape_port="Base.shp",
                                 parent="placement", travel=0.25,
                                 handle=(1.5, 1.125, 0.0))
        assert parm.unexpandedString() == written
        assert parm.eval() == written


def test_the_rig_it_hands_on_has_the_control_and_the_packed_rig_is_untouched():
    with _Scratch() as s:
        before = apex_graph.read_graph(_folder(s.packer, "Base.rig"))
        result = _call(s.packer)
        carrier = hou.node(result["node"])
        after = apex_graph.read_graph(_folder(carrier, "Base.rig"),
                                      include_nodes=True, include_wires=True)
        upstream = apex_graph.read_graph(_folder(s.packer, "Base.rig"))
        assert "explode" in after["controls"] and "explode" not in upstream["controls"]
        assert after["node_count"] == before["node_count"] + 5
        assert upstream["node_count"] == before["node_count"]
        assert result["after"]["node_count"] == after["node_count"]
        assert after["wires_status"] == "read"
        wires = {(w["source"], w["source_port"], w["destination"], w["destination_port"])
                 for w in after["wires"]}
        assert ("parms", "Base.shp", "EXPLODE_move", "geo0") in wires
        assert ("EXPLODE_move", "geo0", "rest_shape", "parm") in wires
        assert ("placement", "xform", "explode", "parent") in wires
        assert "explode_t" in after["graph_inputs"]
        assert {"explode", "explode_amount"} <= set(after["graph_outputs"])
        # the other folder passes through, attribute and all
        assert _folder(carrier, "Base.shp").findPointAttrib("explode_offset") is not None
        assert [p.attribValue("name") for p in carrier.geometry().prims()] == [
            p.attribValue("name") for p in s.packer.geometry().prims()]


def test_raising_the_control_moves_each_point_by_its_own_offset():
    with _Scratch() as s:
        rest = _posed(s.packer)
        carrier = hou.node(_call(s.packer)["node"])
        travel = 0.25
        still = [(0.0, 0.0, 0.0)] * 4
        assert _posed(carrier, (0.0, 0.0, 0.0)) == rest
        assert _moved(rest, _posed(carrier, (0.0, travel, 0.0))) == still + [OFFSET] * 4
        half = tuple(c / 2 for c in OFFSET)
        assert _moved(rest, _posed(carrier, (0.0, travel / 2, 0.0))) == still + [half] * 4
        # clamped: past the top is open, below the rest is closed
        assert _moved(rest, _posed(carrier, (0.0, travel * 4, 0.0))) == still + [OFFSET] * 4
        assert _posed(carrier, (0.0, -travel, 0.0)) == rest
        # only the height counts
        assert _posed(carrier, (3.0, 0.0, -2.0)) == rest


def test_the_slider_sets_where_the_control_rests():
    with _Scratch() as s:
        rest = _posed(s.packer)
        result = _call(s.packer)
        carrier = hou.node(result["node"])
        slider = carrier.parm(plan.SLIDER)
        assert slider is not None and result["slider"] == slider.path()
        assert slider.eval() == 0.0
        assert _posed(carrier) == rest
        slider.set(1.0)
        assert not carrier.errors()
        assert _moved(rest, _posed(carrier)) == [(0.0, 0.0, 0.0)] * 4 + [OFFSET] * 4
        slider.set(0.5)
        half = tuple(c / 2 for c in OFFSET)
        assert _moved(rest, _posed(carrier)) == [(0.0, 0.0, 0.0)] * 4 + [half] * 4
        slider.set(0.0)
        assert _posed(carrier) == rest
        # the slider cannot be pushed past its ends
        slider.set(5.0)
        assert slider.eval() == 1.0


def test_one_undo_takes_it_back_and_one_redo_returns_it():
    with _Scratch() as s:
        assert hou.undos.areEnabled()
        result = _call(s.reader_b)
        path = result["node"]
        assert hou.undos.undoLabels()[0] == plan.UNDO_LABEL == result["undo"]["label"]
        hou.undos.performUndo()
        assert hou.node(path) is None
        assert s.reader_a.inputs() == (s.packer,)
        assert s.reader_b.inputs() == (s.packer,)
        hou.undos.performRedo()
        carrier = hou.node(path)
        assert carrier is not None
        assert s.reader_a.inputs() == (carrier,) and s.reader_b.inputs() == (carrier,)
        assert carrier.parm(plan.SLIDER) is not None
        assert "explode" in apex_graph.read_graph(_folder(carrier, "Base.rig"))["controls"]


def test_a_second_call_changes_nothing():
    with _Scratch() as s:
        first = _call(s.packer)
        labels = hou.undos.undoLabels()
        for asked_at in (s.packer, s.reader_a, hou.node(first["node"])):
            again = _call(asked_at)
            assert again["status"] == "unchanged"
            assert again["node"] == first["node"]
            assert again["control_listed"] is True
        assert hou.undos.undoLabels() == labels
        assert len([n for n in s.net.children() if n.type().name() == "python"]) == 4


def test_an_asset_without_offsets_is_refused_and_nothing_is_built():
    with _Scratch(with_offsets=False) as s:
        children = len(s.net.children())
        try:
            _call(s.reader_a)
        except SynapseUserError as refusal:
            assert "no point attribute named explode_offset" in str(refusal)
        else:
            raise AssertionError("an asset with no explode_offset was not refused")
        assert len(s.net.children()) == children
        assert s.reader_a.inputs() == (s.packer,)


def test_a_rig_that_is_not_cooked_is_refused_and_not_cooked():
    with _Scratch(cook=False) as s:
        assert s.packer.needsToCook()
        try:
            _call(s.reader_a)
        except SynapseUserError as refusal:
            assert "not cooked" in str(refusal)
            assert "Display the rig's node" in refusal.suggestion
        else:
            raise AssertionError("a rig that was not cooked was read anyway")
        assert s.packer.needsToCook(), "the refusal cooked the packer"
        assert len(s.net.children()) == 5
