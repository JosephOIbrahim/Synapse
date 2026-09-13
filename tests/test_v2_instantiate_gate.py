"""G1: model proposals and reviewed host application have separate authority."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from shared.constants import OPERATION_GATES
from synapse.mcp._tool_registry import TOOL_DEFS
from synapse.panel import bridge_adapter, tool_bridge, worker_policy as policy
from synapse.recipes.contracts import RUN_RECIPE_TOOL_NAME
from test_worker_tool_policy import claude_worker_module, _make_worker


@pytest.fixture(autouse=True)
def proposal_environment(monkeypatch):
    monkeypatch.delenv("SYNAPSE_WORKER_TOOL_PROFILE", raising=False)
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_MODE", "proposal")


def test_uses_this_checkout():
    root = Path(__file__).resolve().parents[1]
    for module in (policy, bridge_adapter, tool_bridge):
        assert Path(module.__file__).resolve().is_relative_to(root)


def test_proposal_mode_is_recognized():
    assert policy.resolve_mode() == "proposal"


@pytest.mark.parametrize("setting", ["proposal", " PROPOSAL "])
def test_proposal_mode_normalizes(setting, monkeypatch):
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_MODE", setting)
    assert policy.resolve_mode() == "proposal"


@pytest.mark.parametrize("entry", TOOL_DEFS, ids=lambda entry: entry[0])
def test_registry_effects_define_the_proposal_boundary(entry):
    name, _, _, _, _, read_only, _, _ = entry
    expected = bool(read_only) or name == RUN_RECIPE_TOOL_NAME
    allowed, reason = policy.is_tool_allowed_for_worker(name)
    assert allowed is expected, (name, reason)
    assert reason


def test_real_knowledge_tools_remain_available():
    names = {name for name, _ in tool_bridge._GROUP_TOOLS}
    assert names == {
        "synapse_group_scene", "synapse_group_render", "synapse_group_usd",
        "synapse_group_tops", "synapse_group_memory", "synapse_group_cops",
    }
    assert all(policy.is_tool_allowed_for_worker(name)[0] for name in names)


@pytest.mark.parametrize("name", [
    "unknown_tool", "synapse_group_unknown", "execute_python", "execute_vex",
])
def test_unknown_names_are_not_authority(name):
    assert policy.is_tool_allowed_for_worker(name)[0] is False


def test_instantiate_has_review_classification():
    operation = bridge_adapter._TOOL_TO_OPERATION.get("synapse_instantiate_graph")
    assert operation is not None
    assert OPERATION_GATES[operation] == "review"


def test_advertisement_matches_effects_and_declared_proposals():
    expected = {entry[0] for entry in TOOL_DEFS if entry[5]}
    expected.add(RUN_RECIPE_TOOL_NAME)
    expected.update(name for name, _ in tool_bridge._GROUP_TOOLS)
    # G1 filters the existing surface; registering the separate recipe interface
    # is an integrator task. Permission for that interface is tested at dispatch.
    expected &= {tool["name"] for tool in tool_bridge.get_anthropic_tools()}
    tools = tool_bridge.get_anthropic_tools_for_worker()
    assert {tool["name"] for tool in tools} == expected
    assert len(tools) == len(expected)
    assert "synapse_propose_graph" in expected


def test_tool_cache_cannot_keep_standard_mutations_in_proposal_mode(monkeypatch):
    def advertised():
        return {tool["name"] for tool in tool_bridge.get_anthropic_tools_for_worker()}

    proposal_names = advertised()
    assert "houdini_create_node" not in proposal_names
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_MODE", "standard")
    assert "houdini_create_node" in advertised()
    assert "synapse_solaris_build_graph" in advertised()
    assert "synapse_instantiate_graph" not in advertised()
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_MODE", "proposal")
    assert advertised() == proposal_names


@pytest.mark.parametrize("other", ["standard", "unrestricted", "", "unknown"])
def test_conflicting_host_profile_fails_closed(other, monkeypatch):
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_MODE", other)
    assert policy.resolve_mode(profile="proposal") == "strict"
    assert policy.is_tool_allowed_for_worker(
        "synapse_instantiate_graph", profile="proposal"
    )[0] is False
    assert policy.is_tool_allowed_for_worker(
        "houdini_create_node", profile="proposal"
    )[0] is False


def test_profile_only_can_select_proposal(monkeypatch):
    monkeypatch.delenv("SYNAPSE_WORKER_TOOL_MODE")
    assert policy.resolve_mode(profile="proposal") == "proposal"
    monkeypatch.setenv("SYNAPSE_WORKER_TOOL_PROFILE", "proposal")
    assert policy.resolve_mode() == "proposal"


def test_absent_mode_preserves_standard_default(monkeypatch):
    monkeypatch.delenv("SYNAPSE_WORKER_TOOL_MODE")
    assert policy.resolve_mode() == "standard"
    assert policy.is_tool_allowed_for_worker("houdini_create_node")[0] is True


@pytest.mark.parametrize("name", [
    "synapse_instantiate_graph", "synapse_batch",
    "houdini_create_node", "houdini_set_parm", "houdini_set_keyframe",
    "houdini_connect_nodes", "houdini_set_usd_attribute",
    "synapse_solaris_build_graph", "synapse_solaris_assemble_chain",
    "houdini_execute_python", "houdini_execute_vex",
    "houdini_delete_node", "houdini_render", "synapse_group_unknown",
])
def test_forged_mutation_is_rejected_before_either_transport(
    name, claude_worker_module, monkeypatch,
):
    cw = claude_worker_module
    transport = MagicMock()
    monkeypatch.setattr(cw, "try_mcp_tool_call", transport)
    provider = SimpleNamespace(_model_scope=None)
    worker = _make_worker(cw, tools=[], provider=provider, enforce_worker_policy=True)
    worker.tool_requested = MagicMock()

    result = worker._execute_tool_block({
        "id": "g1-forged", "name": name,
        "input": {"proposal_id": "p-test", "approved": True},
    })

    assert result["is_error"] is True
    assert result["tool_use_id"] == "g1-forged"
    transport.assert_not_called()
    worker.tool_requested.emit.assert_not_called()
    assert worker._offmain_executor is None


@pytest.mark.parametrize("name", ["synapse_ping", "synapse_propose_graph", RUN_RECIPE_TOOL_NAME])
def test_worker_can_dispatch_read_and_declared_proposals(
    name, claude_worker_module, monkeypatch,
):
    cw = claude_worker_module
    transport = MagicMock(return_value={"ok": True})
    monkeypatch.setattr(cw, "try_mcp_tool_call", transport)
    worker = _make_worker(
        cw, tools=[], provider=SimpleNamespace(_model_scope=None),
        enforce_worker_policy=True,
    )
    result = worker._execute_tool_block({
        "id": "g1-propose", "name": name, "input": {},
    })
    assert result["is_error"] is False
    transport.assert_called_once_with(name, {})


@pytest.mark.parametrize("approved", [False, True])
def test_host_dispatch_obeys_review_decision(approved, monkeypatch):
    # This fake observes the REAL Operation's gate level. It supplies the
    # review decision; it does not claim to exercise live CARD/scope UI.
    operations = []
    response = SimpleNamespace(success=True, data={"status": "built"})
    handler = SimpleNamespace(handle=MagicMock(return_value=response))

    class ReviewBridge:
        def execute(self, operation):
            operations.append(operation)
            assert operation.gate_level == bridge_adapter.GateLevel.REVIEW
            if not approved:
                return SimpleNamespace(
                    success=False, result=None, error="review declined", integrity=None,
                )
            return SimpleNamespace(
                success=True, result=operation.fn(), error=None, integrity=None,
            )

    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: ReviewBridge())
    command = SimpleNamespace(
        id="g1-host", type="instantiate_graph", payload={"proposal_id": "p-reviewed"},
    )
    result = bridge_adapter.execute_through_bridge(
        "synapse_instantiate_graph", handler, command,
    )
    assert len(operations) == 1
    assert result.success is approved
    if approved:
        assert result is response
        handler.handle.assert_called_once_with(command)
    else:
        handler.handle.assert_not_called()
        assert "review declined" in result.error
