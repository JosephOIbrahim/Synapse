"""Graph-synthesis production wiring — propose (cognitive) + instantiate (host).

Pins the three things the wiring must guarantee:

  (a) propose + build share ONE ProposalStore — a VALID proposal parked via the
      cognitive ``synapse_propose_graph`` tool is retrievable by the build path by
      id (if the stores differed, instantiate would REJECT the unknown id).
  (b) the build tool (``instantiate_graph`` handler) routes to
      ``GraphBuilder.instantiate`` and serializes the result to a dict.
  (c) the daemon still builds its Dispatcher, now with ``synapse_propose_graph``
      registered alongside ``synapse_inspect_stage``.

TEST TRAP (repo-specific): a module-level ``sys.modules['hou']=fake`` LEAKS across
the whole suite (alphabetically-first planter wins — broken CI before). So we
NEVER plant a module-level fake. Each test installs the fake via function-scoped
monkeypatch (setattr on the builder module's hou global + setitem on sys.modules),
both auto-reverted at test end. The runtime singletons are reset per test.
"""
from __future__ import annotations

import sys
import types

import pytest

from synapse.cognitive.graph_proposal import (
    ValidationReport,
    ValidationStatus,
)
from synapse.host.graph_builder import InstantiationResult, InstantiationStatus


# --------------------------------------------------------------------------- #
# Minimal fake hou — enough for a single createNode build (no edges/parms).    #
# --------------------------------------------------------------------------- #
class _FakeNode:
    def __init__(self, path, type_name, scene):
        self._path, self._type_name, self._scene = path, type_name, scene

    def path(self):
        return self._path

    def createNode(self, type_name, name=None):
        nm = name or f"{type_name}1"
        child = _FakeNode(f"{self._path}/{nm}", type_name, self._scene)
        self._scene.registry[child.path()] = child
        self._scene.created.append((type_name, child.path()))
        return child

    def inputConnections(self):
        return []


class _UndosGroup:
    def __init__(self, scene, label):
        self._scene, self._label = scene, label

    def __enter__(self):
        self._scene.undo_enters.append(self._label)
        return self

    def __exit__(self, *exc):
        return False


class _Undos:
    def __init__(self, scene):
        self._scene = scene

    def group(self, label):
        return _UndosGroup(self._scene, label)


class _Scene:
    def __init__(self):
        self.registry: dict = {}
        self.created: list = []
        self.undo_enters: list = []

    def node(self, path):
        return self.registry.get(path)

    def add(self, path, type_name="geo"):
        n = _FakeNode(path, type_name, self)
        self.registry[path] = n
        return n


def _install_fake_hou(monkeypatch, scene):
    fake = types.SimpleNamespace(node=scene.node, undos=_Undos(scene))
    import synapse.host.graph_builder as gb
    monkeypatch.setattr(gb, "hou", fake)
    monkeypatch.setitem(sys.modules, "hou", fake)
    return fake


class _AlwaysValid:
    """A validator that passes anything — used so propose parks and the build's
    TOCTOU re-validation succeeds, all without touching hou-backed oracles."""

    def validate(self, p):
        return ValidationReport(status=ValidationStatus.VALID, proposal_id=p.proposal_id)


def _valid_proposal_dict(pid="p-share"):
    return {
        "proposal_id": pid,
        "network_type": "SOP",
        "parent_path": "/obj/geo1",
        "nodes": [
            {"node_id": "a", "kind": "new", "node_category": "Sop",
             "node_type": "box", "friendly_name": "box1"},
        ],
        "edges": [],
        "natural_language_intent": "a single box",
        "model_id": "glm-5.2",
        "houdini_version_stamp": "21.0.671",
    }


@pytest.fixture
def rt(monkeypatch):
    """Fresh runtime singletons + a fake (always-VALID) validator so neither the
    propose nor the build path constructs the hou-backed oracles."""
    import synapse.host.graph_synth_runtime as runtime
    runtime.reset()
    monkeypatch.setattr(runtime, "_build_validator", lambda: _AlwaysValid())
    yield runtime
    runtime.reset()


# --------------------------------------------------------------------------- #
# (a) propose + build share ONE ProposalStore.                                #
# --------------------------------------------------------------------------- #
def test_propose_and_build_share_one_store(rt, monkeypatch):
    from synapse.cognitive.tools import propose_graph

    scene = _Scene()
    scene.add("/obj/geo1", "geo")
    _install_fake_hou(monkeypatch, scene)

    rt.wire_propose()

    # Direct proof: the propose tool was configured with the runtime's ONE store,
    # and the build's GraphBuilder is bound to that SAME object.
    shared = rt._get_store()
    assert propose_graph._STORE is shared
    assert rt._get_builder()._store is shared

    # Behavioral proof: park a VALID proposal through the cognitive tool...
    out = propose_graph.synapse_propose_graph(_valid_proposal_dict("p-share"))
    assert out["status"] == "valid"
    assert shared.get("p-share") is not None

    # ...and the build path retrieves it BY ID and builds (REJECTED would mean the
    # stores diverged — the exact failure the shared-store invariant guards).
    result = rt.instantiate("p-share")
    assert result.status is InstantiationStatus.BUILT
    assert result.proposal_id == "p-share"
    assert ("box", "/obj/geo1/box1") in scene.created
    assert len(scene.undo_enters) == 1  # one undo group


def test_unknown_id_rejects_without_mutation(rt, monkeypatch):
    scene = _Scene()
    scene.add("/obj/geo1", "geo")
    _install_fake_hou(monkeypatch, scene)
    rt.wire_propose()

    result = rt.instantiate("never-proposed")
    assert result.status is InstantiationStatus.REJECTED
    assert scene.created == []
    assert scene.undo_enters == []


# --------------------------------------------------------------------------- #
# (b) the build tool routes to GraphBuilder.instantiate.                      #
# --------------------------------------------------------------------------- #
class _SpyBuilder:
    def __init__(self):
        self.calls: list = []

    def instantiate(self, proposal_id):
        self.calls.append(proposal_id)
        return InstantiationResult(
            status=InstantiationStatus.BUILT,
            proposal_id=proposal_id,
            message="spy build",
            created_paths=["/obj/geo1/box1"],
        )


def test_instantiate_handler_routes_to_graphbuilder(rt, monkeypatch):
    from synapse.core.protocol import SynapseCommand
    from synapse.server.handlers import SynapseHandler

    spy = _SpyBuilder()
    monkeypatch.setattr(rt, "_builder", spy)   # _get_builder() returns the spy

    h = SynapseHandler()
    resp = h.handle(SynapseCommand(
        type="instantiate_graph",
        id="ig-001",
        payload={"proposal_id": "p-route"},
        sequence=0,
    ))

    assert resp.success is True
    assert spy.calls == ["p-route"]                  # routed to GraphBuilder.instantiate
    assert resp.data["status"] == "built"            # serialized to a dict
    assert resp.data["proposal_id"] == "p-route"
    assert resp.data["created_paths"] == ["/obj/geo1/box1"]
    assert resp.data["ok"] is True


def test_instantiate_handler_rejects_missing_proposal_id(rt):
    from synapse.core.protocol import SynapseCommand
    from synapse.server.handlers import SynapseHandler

    h = SynapseHandler()
    resp = h.handle(SynapseCommand(
        type="instantiate_graph", id="ig-002", payload={}, sequence=0,
    ))
    assert resp.success is False
    assert "proposal_id" in resp.error


# --------------------------------------------------------------------------- #
# (b2) the HOST propose handler shares ONE store with the build handler.       #
#                                                                              #
# This is the real cross-process invariant under test: propose and instantiate #
# are BOTH host command handlers that run IN the Houdini process, so they share #
# THAT process's single ProposalStore. The /mcp transport (separate, hou-less   #
# mcp_server process) forwards BOTH over WebSocket to this same handler layer — #
# it never validates locally — so an id parked by the propose handler is found  #
# by the instantiate handler by id. We drive the ACTUAL handler entrypoints     #
# (SynapseHandler.handle), not a one-process cognitive-tool stub.               #
# --------------------------------------------------------------------------- #
def test_propose_then_build_share_store_through_handlers(rt, monkeypatch):
    from synapse.core.protocol import SynapseCommand
    from synapse.server.handlers import SynapseHandler

    scene = _Scene()
    scene.add("/obj/geo1", "geo")
    _install_fake_hou(monkeypatch, scene)

    h = SynapseHandler()

    # 1) PROPOSE via the host handler. wire_propose() runs lazily INSIDE the
    #    handler (not at boot) and configures the propose tool with the runtime's
    #    ONE shared store; the VALID proposal is parked by id.
    propose_resp = h.handle(SynapseCommand(
        type="propose_graph", id="pg-001",
        payload={"proposal": _valid_proposal_dict("p-host")},
        sequence=0,
    ))
    assert propose_resp.success is True
    assert propose_resp.data["status"] == "valid"
    assert propose_resp.data["proposal_id"] == "p-host"

    # The parked id lives in the runtime's single store — the SAME object the
    # propose tool was configured with and the build path resolves against.
    from synapse.cognitive.tools import propose_graph
    shared = rt._get_store()
    assert propose_graph._STORE is shared
    assert shared.get("p-host") is not None

    # 2) BUILD via the host handler resolves that SAME id from that SAME store
    #    (a divergent store would REJECT the unknown id — the invariant's failure).
    build_resp = h.handle(SynapseCommand(
        type="instantiate_graph", id="ig-host",
        payload={"proposal_id": "p-host"}, sequence=1,
    ))
    assert build_resp.success is True
    assert build_resp.data["status"] == "built"
    assert build_resp.data["proposal_id"] == "p-host"
    assert ("box", "/obj/geo1/box1") in scene.created


def test_propose_handler_rejects_missing_proposal(rt):
    from synapse.core.protocol import SynapseCommand
    from synapse.server.handlers import SynapseHandler

    h = SynapseHandler()
    resp = h.handle(SynapseCommand(
        type="propose_graph", id="pg-002", payload={}, sequence=0,
    ))
    assert resp.success is False
    assert "proposal" in resp.error


# --------------------------------------------------------------------------- #
# (c) the daemon still BOOTS its Dispatcher, and boot does NOT depend on        #
#     wiring the hou-backed propose validator.                                  #
#                                                                               #
# propose is now a HOST command handler (symmetric to instantiate), reached via #
# the host-tool path — NOT registered as an in-process cognitive tool. So boot  #
# must build the Dispatcher WITHOUT touching graph_synth_runtime.wire_propose   #
# (which constructs hou-backed oracles); that wiring is lazy-in-handler.        #
# --------------------------------------------------------------------------- #
def test_daemon_dispatcher_boots_without_propose_wiring(rt, monkeypatch):
    import synapse.host.graph_synth_runtime as runtime
    from synapse.host.daemon import SynapseDaemon

    # Boot MUST NOT call wire_propose — guard by exploding if it does.
    def _boom():
        raise AssertionError("daemon boot must not call wire_propose()")

    monkeypatch.setattr(runtime, "wire_propose", _boom)

    daemon = SynapseDaemon(api_key="test", boot_gate=False)
    dispatcher = daemon._build_dispatcher()

    # The pre-existing cognitive tool still registers...
    assert dispatcher.is_registered("synapse_inspect_stage")
    # ...and propose is NOT a daemon cognitive tool (it's a host handler now).
    assert not dispatcher.is_registered("synapse_propose_graph")


def test_instantiate_graph_in_registry_surface():
    """The mutating build tool is a registry tool -> appears on the MCP surface
    with the right destructive/idempotent metadata."""
    from synapse.mcp._tool_registry import TOOL_DISPATCH, TOOL_JSON

    assert "synapse_instantiate_graph" in TOOL_DISPATCH
    cmd_type, _builder = TOOL_DISPATCH["synapse_instantiate_graph"]
    assert cmd_type == "instantiate_graph"
    ann = TOOL_JSON["synapse_instantiate_graph"]["annotations"]
    assert ann["readOnlyHint"] is False
    assert ann["destructiveHint"] is True
    assert ann["idempotentHint"] is False


def test_propose_graph_in_registry_surface():
    """propose is a HOST registry tool too (not an in-process cognitive special
    case) -> it reaches BOTH transports via TOOL_DISPATCH -> WS, exactly like the
    build half, and carries read-only/non-destructive/idempotent metadata."""
    from synapse.mcp._tool_registry import TOOL_DISPATCH, TOOL_JSON

    assert "synapse_propose_graph" in TOOL_DISPATCH
    cmd_type, _builder = TOOL_DISPATCH["synapse_propose_graph"]
    assert cmd_type == "propose_graph"
    ann = TOOL_JSON["synapse_propose_graph"]["annotations"]
    assert ann["readOnlyHint"] is True
    assert ann["destructiveHint"] is False
    assert ann["idempotentHint"] is True
