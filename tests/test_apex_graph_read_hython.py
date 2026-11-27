"""hython: the APEX graph reader against a graph the real ``apex`` module built.

``tests/test_apex_graph_read.py`` pins the reader against fakes that copy the
measured geometry layout. This module closes the loop on the layout itself: it
builds a small rig with ``apex.Graph``, saves it to real ``hou.Geometry``,
packs a character and a scene, and reads them back. If a Houdini build ever
stores a graph differently, this is the test that goes red.

Runs only under hython (apex/hou). The module-level importorskip self-gates
it: plain pytest skips the module at collection and prints the reason. That
skip is not a pass. Run it for real via:

    python .synapse/hytest.py tests/test_apex_graph_read_hython.py

Every ``apex`` call here is one the OVOID rig source already makes on
22.0.466: ``addNode``, ``getPort``, ``addWire``, ``promoteInput``,
``promoteOutput``, ``setNodeTag``, ``saveToGeometry`` and
``apex.packToFolders``.
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

from synapse.server import apex_graph  # noqa: E402


def _rig_geometry():
    """Five nodes, seven wires, two tagged controls."""
    g = apex.Graph()
    parms = g.addNode("parms", "__parms__")
    out = g.addNode("output", "__output__")
    placement = g.addNode("placement", "TransformObject")
    body = g.addNode("body_cog", "TransformObject")
    leaf = g.addNode("iris_leaf_00", "TransformObject")

    g.promoteInput(g.getPort(placement, "t[in]"), parms, "placement_t")
    g.promoteInput(g.getPort(placement, "r[in]"), parms, "placement_r")
    g.promoteOutput(g.getPort(placement, "xform[out]"), out, "placement")
    g.addWire(g.getPort(placement, "xform[out]"), g.getPort(body, "parent[in]"))
    g.promoteInput(g.getPort(body, "t[in]"), parms, "body_t")
    g.addWire(g.getPort(body, "xform[out]"), g.getPort(leaf, "parent[in]"))
    g.promoteOutput(g.getPort(leaf, "xform[out]"), out, "leaf")

    g.setNodeTag(placement, "control")
    g.setNodeTag(body, "control")

    geo = hou.Geometry()
    g.saveToGeometry(geo)
    return geo


def _triangle():
    geo = hou.Geometry()
    poly = geo.createPolygon()
    for position in ((0, 0, 0), (1, 0, 0), (0, 1, 0)):
        point = geo.createPoint()
        point.setPosition(hou.Vector3(position))
        poly.addVertex(point)
    return geo


def _character_geometry():
    geo = hou.Geometry()
    apex.packToFolders(geo, apex.Dict({
        "Base.shp": _triangle(),
        "Base.rig": _rig_geometry(),
    }))
    return geo


def test_a_saved_graph_reads_back_as_nodes_wires_and_controls():
    graph = apex_graph.read_graph(_rig_geometry(), include_nodes=True, include_wires=True)
    assert graph is not None and graph["read"] is True
    assert graph["node_count"] == 5
    assert graph["wire_count"] == 7
    assert graph["wires_status"] == "read"
    assert sorted(graph["controls"]) == ["body_cog", "placement"]
    assert graph["control_count"] == 2
    assert graph["callbacks"]["TransformObject"] == 3
    assert sorted(graph["graph_inputs"]) == ["body_t", "placement_r", "placement_t"]
    assert sorted(graph["graph_outputs"]) == ["leaf", "placement"]


def test_wire_direction_matches_what_was_wired():
    graph = apex_graph.read_graph(_rig_geometry(), include_wires=True)
    wires = {(w["source"], w["source_port"], w["destination"], w["destination_port"])
             for w in graph["wires"]}
    assert ("placement", "xform", "body_cog", "parent") in wires
    assert ("body_cog", "xform", "iris_leaf_00", "parent") in wires
    assert ("parms", "placement_t", "placement", "t") in wires
    assert ("iris_leaf_00", "xform", "output", "leaf") in wires
    assert not [w for w in wires if w[2] == "parms"]
    assert not [w for w in wires if w[0] == "output"]


def test_a_mesh_is_not_a_graph():
    assert apex_graph.is_graph_geometry(_triangle()) is False
    assert apex_graph.summarize(_triangle()) is None


def test_a_packed_character_gives_up_its_graph():
    summary = apex_graph.summarize(_character_geometry())
    assert summary is not None
    assert [g["folder"] for g in summary["graphs"]] == ["Base.rig"]
    assert summary["graphs"][0]["node_count"] == 5
    kinds = {f["name"]: f["kind"] for f in summary["folders"]}
    assert kinds == {"Base.rig": "graph", "Base.shp": "geometry"}


def test_a_scene_folder_is_opened_one_level_deeper():
    scene = hou.Geometry()
    apex.packToFolders(scene, apex.Dict({"ovoid.char": _character_geometry()}))
    summary = apex_graph.summarize(scene)
    assert summary is not None
    assert [g["folder"] for g in summary["graphs"]] == ["ovoid.char/Base.rig"]
    assert summary["graphs"][0]["control_count"] == 2
