"""Regression tests for the Sprint 3 Spike 1 Dispatcher port.

The ``synapse_inspect_stage`` tool was ported out of the Sprint-2
WebSocket handler path and into the cognitive Dispatcher. These tests
pin the port so the next migration (Spike 2, Spike 3) doesn't silently
drift:

  - Happy path through the Dispatcher produces the same payload
    shape the Inspector produces directly.
  - Inspector exceptions do not propagate out of ``Dispatcher.execute``;
    they come back as ``AgentToolError`` values with preserved
    ``error_type`` and ``error_message``.
  - Unknown-tool and wrong-return-type error routes also work.

No Houdini required. Runs against the Inspector mock transport.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synapse.cognitive.dispatcher import AgentToolError, Dispatcher
from synapse.cognitive.tools.inspect_stage import inspect_stage
from synapse.inspector import SCHEMA_VERSION, configure_transport, reset_transport

from conftest import make_mock_transport


_GOLDEN = Path(__file__).parent / "fixtures" / "inspector_week1_flat.golden.json"


@pytest.fixture
def golden_text() -> str:
    return _GOLDEN.read_text(encoding="utf-8")


@pytest.fixture
def configured_mock(golden_text: str):
    """Configure Inspector transport with the golden JSON; auto-reset."""
    reset_transport()
    configure_transport(make_mock_transport(golden_text))
    yield
    reset_transport()


@pytest.fixture
def port_dispatcher() -> Dispatcher:
    """Test-mode Dispatcher with only the ported Inspector tool registered."""
    return Dispatcher(
        is_testing=True,
        tools={"synapse_inspect_stage": inspect_stage},
    )


class TestPortHappyPath:
    def test_returns_dict_payload(self, port_dispatcher, configured_mock):
        result = port_dispatcher.execute(
            "synapse_inspect_stage", {"target_path": "/stage"}
        )
        assert isinstance(result, dict)

    def test_schema_version_preserved(self, port_dispatcher, configured_mock):
        result = port_dispatcher.execute("synapse_inspect_stage", {})
        assert result["schema_version"] == SCHEMA_VERSION

    def test_default_target_path(self, port_dispatcher, configured_mock):
        result = port_dispatcher.execute("synapse_inspect_stage", {})
        assert result["target_path"] == "/stage"

    def test_node_count_matches_golden(self, port_dispatcher, configured_mock, golden_text):
        golden_payload = json.loads(golden_text)
        result = port_dispatcher.execute("synapse_inspect_stage", {})
        assert len(result["nodes"]) == len(golden_payload["nodes"])

    def test_node_names_match_golden(self, port_dispatcher, configured_mock, golden_text):
        golden_payload = json.loads(golden_text)
        golden_names = sorted(n["node_name"] for n in golden_payload["nodes"])
        result = port_dispatcher.execute("synapse_inspect_stage", {})
        result_names = sorted(n["node_name"] for n in result["nodes"])
        assert result_names == golden_names


class TestPortExceptionBoundary:
    """Inspector exceptions must come back as AgentToolError, not raise."""

    def test_invalid_target_path_routes_as_error(self, port_dispatcher, configured_mock):
        err = port_dispatcher.execute(
            "synapse_inspect_stage", {"target_path": "../escape_attempt"}
        )
        assert isinstance(err, AgentToolError)
        assert err.error_type == "InvalidTargetPathError"
        assert err.tool_name == "synapse_inspect_stage"

    def test_stage_not_found_routes_as_error(self, port_dispatcher):
        # Transport returns a stage_not_found envelope — Inspector raises
        # StageNotFoundError, Dispatcher wraps as AgentToolError.
        reset_transport()
        configure_transport(make_mock_transport(
            json.dumps({
                "synapse_error": "stage_not_found",
                "target_path": "/stage",
            })
        ))
        try:
            err = port_dispatcher.execute(
                "synapse_inspect_stage", {"target_path": "/stage"}
            )
        finally:
            reset_transport()
        assert isinstance(err, AgentToolError)
        assert err.error_type == "StageNotFoundError"

    def test_schema_version_mismatch_routes_as_error(self, port_dispatcher):
        reset_transport()
        configure_transport(make_mock_transport(
            json.dumps({
                "schema_version": "999.0.0",
                "target_path": "/stage",
                "nodes": [],
            }, sort_keys=True)
        ))
        try:
            err = port_dispatcher.execute("synapse_inspect_stage", {})
        finally:
            reset_transport()
        assert isinstance(err, AgentToolError)
        assert err.error_type == "SchemaVersionMismatchError"

    def test_traceback_populated_on_exception(self, port_dispatcher, configured_mock):
        err = port_dispatcher.execute(
            "synapse_inspect_stage", {"target_path": "not/absolute"}
        )
        assert isinstance(err, AgentToolError)
        # Traceback should capture at least the synapse.inspector frame
        assert "synapse" in err.traceback_str.lower()


class TestDispatcherContracts:
    """Generic Dispatcher contracts exercised through the ported tool."""

    def test_unknown_tool_routes_as_error(self, port_dispatcher):
        err = port_dispatcher.execute("no_such_tool", {})
        assert isinstance(err, AgentToolError)
        assert err.error_type == "ToolNotRegistered"

    def test_execute_never_raises_on_exception(self, port_dispatcher):
        # A tool whose body deliberately raises — Dispatcher must catch.
        def detonate(**kwargs):
            raise RuntimeError("boom")

        port_dispatcher.register("detonate", detonate)
        err = port_dispatcher.execute("detonate", {"any": 1})
        assert isinstance(err, AgentToolError)
        assert err.error_type == "RuntimeError"
        assert "boom" in err.error_message
