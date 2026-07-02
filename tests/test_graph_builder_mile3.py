"""Mile 3 DoD — host/graph_builder.GraphBuilder.instantiate.

Four scenarios, all driven by a FAKE hou that records every call so the build is
asserted off-Houdini:

  1. novel-topology extend-existing build -> NEW nodes createNode'd in TOPOLOGICAL
     order, parms set NEW-only, edges setInput'd with correct indices, EXISTING
     never recreated.
  2. the whole build is wrapped in EXACTLY ONE undos.group (single Ctrl+Z).
  3. delete-between-propose-and-instantiate -> re-validate INVALID -> ZERO
     createNode/setInput and the undo group is NEVER entered.
  4. reject unknown proposal_id -> clean rejection, ZERO mutation, undo never
     entered, re-validation never even reached.

TEST TRAP (repo-specific): a module-level sys.modules['hou']=fake LEAKS across the
whole suite (alphabetically-first planter wins — this has broken CI before). So we
NEVER plant a module-level fake. Each test installs the fake via function-scoped
monkeypatch (setattr on the builder module's hou global + setitem on sys.modules),
both auto-reverted at test end.
"""
from __future__ import annotations

import sys
import types

import pytest

from conftest import HOUDINI_BUILD
from synapse.cognitive.graph_proposal import (
    GraphProposal,
    NodeKind,
    ProposedEdge,
    ProposedNode,
    ValidationIssue,
    ValidationReport,
    ValidationStatus,
)
from synapse.host.graph_builder import GraphBuilder, InstantiationStatus
from synapse.host.proposal_store import ProposalStore


# --------------------------------------------------------------------------- #
# Fake hou — records every call; zero Houdini.                                 #
# --------------------------------------------------------------------------- #
class _FakeParm:
    def __init__(self, node, name):
        self._node, self._name, self._val = node, name, None

    def set(self, value):
        self._val = value
        self._node._scene.parm_sets.append((self._node.path(), self._name, value))

    def eval(self):
        return self._val


class _FakeConnection:
    def __init__(self, input_index, source_node, output_index):
        self._ii, self._src, self._oi = input_index, source_node, output_index

    def inputIndex(self):
        return self._ii

    def outputIndex(self):
        return self._oi

    def inputNode(self):
        return self._src


class _FakeNode:
    def __init__(self, path, type_name, scene):
        self._path, self._type_name, self._scene = path, type_name, scene
        self._inputs: dict[int, tuple] = {}     # input_index -> (source_node, output_index)
        self._parms: dict[str, _FakeParm] = {}

    def path(self):
        return self._path

    def createNode(self, type_name, name=None):
        if type_name == self._scene.fail_create_for:
            raise RuntimeError(f"forced createNode failure: {type_name}")
        nm = name or f"{type_name}{self._scene.next_auto(type_name)}"
        child = _FakeNode(f"{self._path}/{nm}", type_name, self._scene)
        self._scene.register(child.path(), child)
        self._scene.created_order.append((type_name, child.path()))
        return child

    def parm(self, name):
        p = self._parms.get(name)
        if p is None:
            p = _FakeParm(self, name)
            self._parms[name] = p
        return p

    def parmTuple(self, name):
        return None   # this fixture exercises the scalar-parm path only

    def setInput(self, input_index, source, output_index=0):
        self._scene.setinput_calls.append(
            (self._path, input_index, source.path(), output_index)
        )
        self._inputs[input_index] = (source, output_index)

    def inputConnections(self):
        return [_FakeConnection(i, s, o) for i, (s, o) in sorted(self._inputs.items())]

    def destroy(self):
        self._scene.destroyed.append(self._path)
        self._scene.registry.pop(self._path, None)


class _FakeUndosGroup:
    def __init__(self, scene, label):
        self._scene, self._label = scene, label

    def __enter__(self):
        self._scene.undo_enters.append(self._label)
        return self

    def __exit__(self, *exc):
        self._scene.undo_exits.append(self._label)
        return False


class _FakeUndos:
    def __init__(self, scene):
        self._scene = scene

    def group(self, label):
        self._scene.undo_group_calls.append(label)
        return _FakeUndosGroup(self._scene, label)


class _Scene:
    def __init__(self):
        self.registry: dict[str, _FakeNode] = {}
        self.created_order: list[tuple] = []     # (type_name, path) per createNode
        self.setinput_calls: list[tuple] = []    # (target_path, input_index, source_path, output_index)
        self.parm_sets: list[tuple] = []         # (node_path, parm_name, value)
        self.undo_group_calls: list[str] = []
        self.undo_enters: list[str] = []
        self.undo_exits: list[str] = []
        self.destroyed: list[str] = []           # paths passed to node.destroy() (rollback)
        self.fail_create_for: str | None = None  # type_name whose createNode raises (failure injection)
        self._auto: dict[str, int] = {}

    def register(self, path, node):
        self.registry[path] = node

    def node(self, path):
        return self.registry.get(path)

    def next_auto(self, type_name):
        self._auto[type_name] = self._auto.get(type_name, 0) + 1
        return self._auto[type_name]

    def add_node(self, path, type_name="merge"):
        node = _FakeNode(path, type_name, self)
        self.register(path, node)
        return node


def _make_fake_hou(scene):
    m = types.SimpleNamespace()
    m.node = scene.node
    m.undos = _FakeUndos(scene)
    return m


def _install_fake_hou(monkeypatch, scene):
    fake = _make_fake_hou(scene)
    import synapse.host.graph_builder as gb
    monkeypatch.setattr(gb, "hou", fake)                 # what the builder actually reads
    monkeypatch.setitem(sys.modules, "hou", fake)        # any fresh `import hou` resolves here
    return fake


# --------------------------------------------------------------------------- #
# Fake validator + spy factory — drive the TOCTOU re-validate verdict.         #
# --------------------------------------------------------------------------- #
class _FakeValidator:
    def __init__(self, report):
        self._report = report

    def validate(self, p):
        return self._report


class _FactorySpy:
    def __init__(self, validator):
        self._validator = validator
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self._validator


def _valid_report(pid):
    return ValidationReport(status=ValidationStatus.VALID, proposal_id=pid)


def _invalid_report(pid, where, msg):
    return ValidationReport(
        status=ValidationStatus.INVALID,
        proposal_id=pid,
        errors=[ValidationIssue(where=where, message=msg)],
    )


# --------------------------------------------------------------------------- #
# Fixtures: a parent + one EXISTING child already in the scene.                #
# --------------------------------------------------------------------------- #
@pytest.fixture
def scene():
    s = _Scene()
    s.add_node("/obj/geo1", type_name="geo")          # parent container
    s.add_node("/obj/geo1/merge1", type_name="merge")  # an EXISTING node to extend
    return s


def _extend_proposal():
    # Declaration order [xf, box] is the REVERSE of the topological order: the edge
    # box -> xf forces box to be created FIRST. EXISTING merge1 is extended (a new
    # wire into its input 1) but never recreated.
    nodes = [
        ProposedNode("n_xf", NodeKind.NEW, "Sop", node_type="xform", friendly_name="xf1"),
        ProposedNode("n_box", NodeKind.NEW, "Sop", node_type="box", friendly_name="box1",
                     parameter_overrides={"scale": 2.0}),
        ProposedNode("n_merge", NodeKind.EXISTING, "Sop", scene_path="/obj/geo1/merge1"),
    ]
    edges = [
        ProposedEdge("n_box", 0, "n_xf", 0),       # NEW -> NEW (drives topo order)
        ProposedEdge("n_xf", 0, "n_merge", 1),     # NEW -> EXISTING (extend, input 1)
    ]
    return GraphProposal(
        proposal_id="p-mile3",
        network_type="SOP",
        parent_path="/obj/geo1",
        nodes=nodes,
        edges=edges,
        natural_language_intent="extend the existing merge with a transformed box",
        model_id="glm-5.2",
        houdini_version_stamp=HOUDINI_BUILD,
    )


# --------------------------------------------------------------------------- #
# Scenario 1 — novel-topology extend-existing build.                          #
# --------------------------------------------------------------------------- #
def test_mile3_extend_existing_build_topological(monkeypatch, scene):
    _install_fake_hou(monkeypatch, scene)
    store = ProposalStore()
    p = _extend_proposal()
    store.put(p)
    factory = _FactorySpy(_FakeValidator(_valid_report(p.proposal_id)))
    builder = GraphBuilder(store, validator_factory=factory)

    result = builder.instantiate("p-mile3")

    assert result.status is InstantiationStatus.BUILT
    assert factory.calls == 1   # re-validated exactly once before mutating

    # --- NEW nodes createNode'd in TOPOLOGICAL order (box before xform), and the
    #     EXISTING merge1 NEVER recreated ---
    created_types = [t for t, _ in scene.created_order]
    created_paths = [path for _, path in scene.created_order]
    assert created_types == ["box", "xform"]   # topo, NOT declaration order [xf, box]
    assert "/obj/geo1/merge1" not in created_paths
    assert len(scene.created_order) == 2

    # --- parms set on NEW nodes ONLY ---
    assert scene.parm_sets == [("/obj/geo1/box1", "scale", 2.0)]
    assert all(path != "/obj/geo1/merge1" for path, *_ in scene.parm_sets)

    # --- edges setInput'd with correct indices (source_output -> target_input) ---
    assert ("/obj/geo1/xf1", 0, "/obj/geo1/box1", 0) in scene.setinput_calls
    assert ("/obj/geo1/merge1", 1, "/obj/geo1/xf1", 0) in scene.setinput_calls
    assert len(scene.setinput_calls) == 2

    # --- truth contract: observed readback, not unobserved claims ---
    assert result.created_paths == ["/obj/geo1/box1", "/obj/geo1/xf1"]
    assert any(r["parm"] == "scale" and r["observed"] == 2.0 for r in result.parameters_set)
    wired = {(c["target"], c["input_index"]): c for c in result.connections}
    assert wired[("/obj/geo1/xf1", 0)]["source"] == "/obj/geo1/box1"
    assert wired[("/obj/geo1/merge1", 1)]["source"] == "/obj/geo1/xf1"
    assert all(c["wired"] for c in result.connections)


# --------------------------------------------------------------------------- #
# Scenario 2 — the whole build is wrapped in EXACTLY ONE undos.group.          #
# --------------------------------------------------------------------------- #
def test_mile3_single_undo_group(monkeypatch, scene):
    _install_fake_hou(monkeypatch, scene)
    store = ProposalStore()
    p = _extend_proposal()
    store.put(p)
    builder = GraphBuilder(store, validator_factory=_FactorySpy(_FakeValidator(_valid_report(p.proposal_id))))

    result = builder.instantiate("p-mile3")

    assert result.status is InstantiationStatus.BUILT
    assert len(scene.undo_group_calls) == 1   # exactly one group opened
    assert len(scene.undo_enters) == 1        # entered exactly once (single Ctrl+Z)
    assert len(scene.undo_exits) == 1
    assert scene.undo_group_calls[0] == scene.undo_enters[0] == scene.undo_exits[0]


# --------------------------------------------------------------------------- #
# Scenario 5 — build raises mid-way -> rolled back, structured FAILED, no orphan.#
# --------------------------------------------------------------------------- #
def test_mile3_build_failure_rolls_back(monkeypatch, scene):
    _install_fake_hou(monkeypatch, scene)
    scene.fail_create_for = "xform"   # box creates OK; the 2nd createNode (xform) raises
    store = ProposalStore()
    p = _extend_proposal()
    store.put(p)
    builder = GraphBuilder(
        store, validator_factory=_FactorySpy(_FakeValidator(_valid_report(p.proposal_id)))
    )

    result = builder.instantiate("p-mile3")

    # structured FAILED, NOT an uncaught exception
    assert result.status is InstantiationStatus.FAILED
    assert result.created_paths == []
    # the partial node (box, created before xform raised) was rolled back
    assert "/obj/geo1/box1" in scene.destroyed
    # rollback ran INSIDE the one undo group -> single Ctrl+Z, net zero mutation
    assert len(scene.undo_enters) == 1 and len(scene.undo_exits) == 1
    # the EXISTING node is never destroyed
    assert "/obj/geo1/merge1" not in scene.destroyed


# --------------------------------------------------------------------------- #
# Scenario 3 — delete-between-propose-and-instantiate -> INVALID -> zero mutate.#
# --------------------------------------------------------------------------- #
def test_mile3_toctou_revalidate_invalid_halts_zero_mutation(monkeypatch, scene):
    _install_fake_hou(monkeypatch, scene)
    store = ProposalStore()
    p = _extend_proposal()
    store.put(p)
    # The merge1 was deleted after propose: live re-validation now fails P5.
    bad = _invalid_report(p.proposal_id, "/obj/geo1/merge1",
                          "existing node path '/obj/geo1/merge1' does not resolve [houdini 21.0.671]")
    factory = _FactorySpy(_FakeValidator(bad))
    builder = GraphBuilder(store, validator_factory=factory)

    result = builder.instantiate("p-mile3")

    assert result.status is InstantiationStatus.HALTED
    assert factory.calls == 1            # re-validated unconditionally
    assert result.errors                 # carries the re-validation issue
    # ZERO mutation, undo group NEVER entered.
    assert scene.created_order == []
    assert scene.setinput_calls == []
    assert scene.parm_sets == []
    assert scene.undo_group_calls == []
    assert scene.undo_enters == []


# --------------------------------------------------------------------------- #
# Scenario 4 — reject unknown proposal_id -> clean, zero mutation.            #
# --------------------------------------------------------------------------- #
def test_mile3_reject_unknown_proposal_id(monkeypatch, scene):
    _install_fake_hou(monkeypatch, scene)
    store = ProposalStore()   # empty — nothing parked
    factory = _FactorySpy(_FakeValidator(_valid_report("unused")))
    builder = GraphBuilder(store, validator_factory=factory)

    result = builder.instantiate("does-not-exist")

    assert result.status is InstantiationStatus.REJECTED
    assert factory.calls == 0            # re-validation never even reached
    # ZERO mutation, undo group NEVER entered.
    assert scene.created_order == []
    assert scene.setinput_calls == []
    assert scene.parm_sets == []
    assert scene.undo_group_calls == []
    assert scene.undo_enters == []
