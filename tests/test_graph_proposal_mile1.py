"""Mile 1 definition of done (spec §12). Cognitive-only, mocked, ZERO mutation.

Proposal: 5 nodes — 2 hallucinated types + 1 existing-node edge endpoint.
Assert: structured errors name both bad types, carry the version stamp, the
existing-node edge is routed to P5 (NOT symbol-checked), and nothing mutates.

The mock oracles live here (module-local) rather than in the shared
tests/conftest.py so Mile 1 cannot perturb the existing suite. Promote them to
conftest once Mile 2 collision-checks the existence/connectivity fixture names.

Zero mutation is structural: this module imports only cognitive.* (+ the pure
host store) and never touches hou — the test passing is itself the proof of the
no-Houdini guarantee.
"""
from __future__ import annotations

import pytest

from synapse.cognitive.graph_proposal import (
    GraphProposal,
    NodeKind,
    ProposedEdge,
    ProposedNode,
    ValidationStatus,
)
from synapse.cognitive.graph_validator import GraphValidator


class MockExistenceOracle:  # IExistenceOracle
    def __init__(self, known_types, known_parms=None):
        self._types = known_types
        self._parms = known_parms or {}

    def node_type_exists(self, node_type, category):
        return node_type in self._types

    def parameter_exists(self, node_type, category, parm):
        return parm in self._parms.get((node_type, category), set())


class MockConnectivityOracle:  # IConnectivityOracle — Mile 1 asserts it is NOT called for symbols
    def __init__(self, existing=None):
        self._existing = existing or {}

    def resolve_node_type(self, scene_path):
        return self._existing[scene_path]

    def __getattr__(self, name):
        # Let dunders fall through so test-framework introspection doesn't trip
        # the trap; any real connectivity method touched at Mile 1 is a bug.
        if name.startswith("__"):
            raise AttributeError(name)
        raise AssertionError(f"connectivity.{name} called at Mile 1 — should be mocked/deferred")


@pytest.fixture
def existence():
    return MockExistenceOracle(known_types={"box", "xform", "mountain"})


@pytest.fixture
def connectivity():
    return MockConnectivityOracle(existing={"/obj/geo1/copy1": ("copy", "Sop")})


def _mile1_proposal() -> GraphProposal:
    nodes = [
        ProposedNode(node_id="n1", kind=NodeKind.NEW, node_category="Sop", node_type="box", friendly_name="box1"),
        ProposedNode(node_id="n2", kind=NodeKind.NEW, node_category="Sop", node_type="frobnicate", friendly_name="f1"),   # hallucinated
        ProposedNode(node_id="n3", kind=NodeKind.NEW, node_category="Sop", node_type="xform", friendly_name="x1"),
        ProposedNode(node_id="n4", kind=NodeKind.NEW, node_category="Sop", node_type="quux", friendly_name="q1"),         # hallucinated
        ProposedNode(node_id="e1", kind=NodeKind.EXISTING, node_category="Sop", scene_path="/obj/geo1/copy1"),            # existing endpoint
    ]
    edges = [ProposedEdge("e1", 0, "n1", 0)]   # existing copy1 -> new box1
    return GraphProposal(
        proposal_id="p-001",
        network_type="SOP",
        parent_path="/obj/geo1",
        nodes=nodes,
        edges=edges,
        natural_language_intent="add a box off copy1",
        model_id="glm-5.2",
        houdini_version_stamp="21.0.671",
    )


def test_mile1_hallucinated_types_and_existing_edge(existence, connectivity):
    # Mile-1 scope: P1/P2 symbol path only. The connectivity mock refuses any
    # connectivity call, so opt out of the now-default-on Mile-2 live phases.
    report = GraphValidator(existence, connectivity,
                            live_phases_enabled=False).validate(_mile1_proposal())

    assert report.status == ValidationStatus.INVALID
    bad = {i.where for i in report.errors}
    assert {"n2", "n4"} <= bad                      # both hallucinated types named
    assert "n1" not in bad and "n3" not in bad      # valid new types pass
    assert "e1" not in bad                          # existing node NOT symbol-checked (routed to P5)
    assert all("21.0.671" in i.message for i in report.errors)   # version stamp on every issue


def test_mile1_propose_graph_tool_and_store_roundtrip(existence, connectivity):
    """A VALID proposal persists in the store; an INVALID one does not. Tool stays hou-free."""
    from synapse.cognitive.tools.propose_graph import configure, synapse_propose_graph
    from synapse.host.proposal_store import ProposalStore

    store = ProposalStore()
    # Mile-1 tool/store roundtrip exercises the P1/P2 path with the refusing
    # connectivity mock; opt out of the now-default-on Mile-2 live phases.
    configure(GraphValidator(existence, connectivity, live_phases_enabled=False), store)

    valid = {
        "proposal_id": "p-ok",
        "network_type": "SOP",
        "parent_path": "/obj/geo1",
        "nodes": [
            {"node_id": "a", "kind": "new", "node_category": "Sop", "node_type": "box", "friendly_name": "box1"},
            {"node_id": "b", "kind": "new", "node_category": "Sop", "node_type": "xform", "friendly_name": "x1"},
        ],
        "edges": [{"source_node_id": "a", "source_output_index": 0, "target_node_id": "b", "target_input_index": 0}],
        "natural_language_intent": "box into xform",
        "model_id": "glm-5.2",
        "houdini_version_stamp": "21.0.671",
    }
    out = synapse_propose_graph(valid)
    assert out["status"] == "valid"
    assert store.get("p-ok") is not None            # persisted on VALID

    invalid = dict(valid, proposal_id="p-bad",
                   nodes=[{"node_id": "z", "kind": "new", "node_category": "Sop", "node_type": "frobnicate"}],
                   edges=[])
    out2 = synapse_propose_graph(invalid)
    assert out2["status"] == "invalid"
    assert any(e["where"] == "z" for e in out2["errors"])
    assert store.get("p-bad") is None               # NOT persisted on INVALID
