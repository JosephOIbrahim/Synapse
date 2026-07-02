"""Mile 2 DoD SCAFFOLD — validator phases P3-P5, exercised off-Houdini.

These encode the Mile-2 *behaviors* named in the build blueprint (P3a arity,
P3b typed type-compat, P3d occupied-input guard, P4 structural, P5 context).
RECONCILE the fixtures + assertions against ARCHITECT spec §12 before the bench
fill — §12 is authoritative on the exact DoD; this file is the starting target.

State now: RED by design. validate() runs P3 first, which raises
NotImplementedError until FORGE fills it — so every test here errors on the same
surface. They go green together when P3/P4/P5 are implemented AND
live_phases_enabled defaults True (one Mile, WIP=1).

The mock connectivity oracle below lets the cognitive validation logic be built
and tested with no Houdini; the REAL hou-backed ConnectivityOracle
(host/graph_oracle.py) is tested separately at the bench (§2.5).
"""
from __future__ import annotations

import pytest

from conftest import HOUDINI_BUILD
from synapse.cognitive.graph_proposal import (
    GraphProposal,
    NodeKind,
    ProposedEdge,
    ProposedNode,
    ValidationStatus,
)
from synapse.cognitive.graph_validator import GraphValidator


class _AllExist:  # IExistenceOracle — symbols are not the focus at Mile 2
    def __init__(self, known):
        self._known = known

    def node_type_exists(self, node_type, category):
        return node_type in self._known

    def parameter_exists(self, node_type, category, parm):
        return True


class MockConnectivityOracle:
    """Configurable IConnectivityOracle for exercising P3-P5 without Houdini.

    Every surface is data-driven so a test states exactly the runtime shape it
    needs. Sensible defaults (1 input, 1 output, untyped, compatible, unoccupied)
    keep fixtures small.
    """

    def __init__(self, *, arity=None, labels=None, outputs=None, typed=None,
                 compat=None, occupied=None, existing=None):
        self._arity = arity or {}          # (type, cat) -> (min, max)
        self._labels = labels or {}        # (type, cat) -> [labels]
        self._outputs = outputs or {}      # (type, cat) -> int
        self._typed = set(typed or ())     # categories that carry wire types
        self._compat = compat or {}        # (src_t, src_o, tgt_t, tgt_i, cat) -> bool
        self._occupied = set(occupied or ())   # {(scene_path, input_index)}
        self._existing = existing or {}    # scene_path -> (type, cat)

    def input_arity(self, node_type, category):
        return self._arity.get((node_type, category), (0, 1))

    def input_labels(self, node_type, category):
        return self._labels.get((node_type, category), [])

    def output_count(self, node_type, category):
        return self._outputs.get((node_type, category), 1)

    def is_typed_category(self, category):
        return category in self._typed

    def types_compatible(self, src_type, src_out, tgt_type, tgt_in, category):
        return self._compat.get((src_type, src_out, tgt_type, tgt_in, category), True)

    def input_is_occupied(self, scene_path, input_index):
        return (scene_path, input_index) in self._occupied

    def resolve_node_type(self, scene_path):
        return self._existing[scene_path]   # KeyError == "does not resolve" (P5 must handle)


def _proposal(network_type, parent_path, nodes, edges) -> GraphProposal:
    return GraphProposal(
        proposal_id="p-m2",
        network_type=network_type,
        parent_path=parent_path,
        nodes=nodes,
        edges=edges,
        natural_language_intent="mile 2 fixture",
        model_id="glm-5.2",
        houdini_version_stamp=HOUDINI_BUILD,
    )


def _validate(p, *, known, conn):
    return GraphValidator(_AllExist(known), conn, live_phases_enabled=True).validate(p)


# Assertions stay behavioral and loose (status + an id/keyword touch) so FORGE
# keeps implementation latitude. Tighten only where §12 demands a specific shape.

def test_mile2_p3a_arity_overflow_is_rejected():
    """An edge into an input the node does not have is an arity violation."""
    nodes = [
        ProposedNode("n1", NodeKind.NEW, "Sop", node_type="box", friendly_name="box1"),     # mock posits box=0 inputs to force the overflow (real H21 box=1)
        ProposedNode("n2", NodeKind.NEW, "Sop", node_type="xform", friendly_name="x1"),
    ]
    edges = [ProposedEdge("n2", 0, "n1", 0)]   # xform -> box.input0, but box takes no inputs
    p = _proposal("SOP", "/obj/geo1", nodes, edges)
    conn = MockConnectivityOracle(arity={("box", "Sop"): (0, 0), ("xform", "Sop"): (1, 1)})

    report = _validate(p, known={"box", "xform"}, conn=conn)
    assert report.status == ValidationStatus.INVALID
    assert any(("n1" in i.where) or ("input" in i.message.lower()) or ("arity" in i.message.lower())
               for i in report.errors)
    assert all(HOUDINI_BUILD in i.message for i in report.errors)


def test_mile2_p3b_type_incompat_flagged_in_typed_category():
    """In a typed network (VOP/MAT) incompatible wire types are rejected."""
    nodes = [
        ProposedNode("a", NodeKind.NEW, "Vop", node_type="constant", friendly_name="c1"),
        ProposedNode("b", NodeKind.NEW, "Vop", node_type="add", friendly_name="add1"),
    ]
    edges = [ProposedEdge("a", 0, "b", 0)]
    p = _proposal("VOP", "/mat/vex1", nodes, edges)
    conn = MockConnectivityOracle(
        typed={"Vop"},
        arity={("add", "Vop"): (1, 2), ("constant", "Vop"): (0, 0)},
        compat={("constant", 0, "add", 0, "Vop"): False},   # the one incompatible pair
    )

    report = _validate(p, known={"constant", "add"}, conn=conn)
    assert report.status == ValidationStatus.INVALID


def test_mile2_p3d_occupied_input_on_existing_node_halts():
    """Wiring into an EXISTING node's already-occupied input is rejected — and
    this guard HALTS rather than degrading to a pass (it severs live wiring)."""
    nodes = [
        ProposedNode("new1", NodeKind.NEW, "Sop", node_type="box", friendly_name="box1"),
        ProposedNode("ex", NodeKind.EXISTING, "Sop", scene_path="/obj/geo1/merge1"),
    ]
    edges = [ProposedEdge("new1", 0, "ex", 0)]   # new box -> existing merge1.input0 (occupied)
    p = _proposal("SOP", "/obj/geo1", nodes, edges)
    conn = MockConnectivityOracle(
        existing={"/obj/geo1/merge1": ("merge", "Sop")},
        arity={("merge", "Sop"): (1, -1), ("box", "Sop"): (0, 0)},
        occupied={("/obj/geo1/merge1", 0)},
    )

    report = _validate(p, known={"box", "merge"}, conn=conn)
    assert report.status == ValidationStatus.INVALID
    # HALT must be the occupied/sever guard specifically — pin it so a future
    # phase erroring on this fixture can't silently turn this into a vacuous pass.
    assert any("occupied" in i.message.lower() or "sever" in i.message.lower()
               or i.where == "ex" for i in report.errors)


def test_mile2_p4_cycle_and_name_collision_rejected():
    """P4 pure logic: a cycle violates the DAG rule; two NEW nodes sharing a
    friendly_name collide."""
    nodes = [
        ProposedNode("n1", NodeKind.NEW, "Sop", node_type="xform", friendly_name="dup"),
        ProposedNode("n2", NodeKind.NEW, "Sop", node_type="xform", friendly_name="dup"),   # name collision
    ]
    edges = [ProposedEdge("n1", 0, "n2", 0), ProposedEdge("n2", 0, "n1", 0)]               # cycle
    p = _proposal("SOP", "/obj/geo1", nodes, edges)
    conn = MockConnectivityOracle(arity={("xform", "Sop"): (1, 1)})

    report = _validate(p, known={"xform"}, conn=conn)
    assert report.status == ValidationStatus.INVALID
    # Pin BOTH P4 sub-checks independently (the fixture trips a cycle AND a name
    # collision) so a regression in either is not masked by the other.
    _msgs = " ".join(i.message.lower() for i in report.errors)
    assert "cycle" in _msgs
    assert "friendly_name" in _msgs or "duplicate" in _msgs


def test_mile2_p5_unresolvable_existing_path_is_context_error():
    """P5 context: an EXISTING scene_path that does not resolve is a clean error,
    not a crash — resolve failure must be caught and reported."""
    nodes = [
        ProposedNode("ex", NodeKind.EXISTING, "Sop", scene_path="/obj/geo1/ghost"),   # not in runtime
        ProposedNode("n1", NodeKind.NEW, "Sop", node_type="box", friendly_name="box1"),
    ]
    edges = [ProposedEdge("ex", 0, "n1", 0)]
    p = _proposal("SOP", "/obj/geo1", nodes, edges)
    conn = MockConnectivityOracle(existing={})   # "/obj/geo1/ghost" absent -> resolve raises

    report = _validate(p, known={"box"}, conn=conn)
    assert report.status == ValidationStatus.INVALID
