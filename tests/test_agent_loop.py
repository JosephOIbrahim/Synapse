"""Agent-loop tests (Sprint 3 Spike 2 Phase 2).

Covers ``synapse.cognitive.agent_loop.run_turn`` with a mocked
Anthropic client. No real API calls, no Houdini required.

The Crucible pass rubric:

  - Baseline: no segfault, process stays alive.
  - Full: agent catches ``hou.ObjectWasDeleted``, routes as
          recoverable tool error, LLM rewrites approach next turn.
  - Partial: catches but can't articulate — needs Spike 2.5.
  - FAIL: silent retry on stale pointer, or segfault.

These tests drive the "Full" pass by constructing scripted agent
scripts: the mocked client emits tool_use → we inject a tool that
raises ``hou.ObjectWasDeleted`` → Dispatcher wraps it as
``AgentToolError`` → agent_loop serializes that back into the next
turn's ``tool_result`` content → we confirm the error envelope is
present in the conversation history (i.e. the LLM sees it).
"""

from __future__ import annotations

import threading
import types
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from synapse.cognitive.agent_loop import (
    AgentTurnConfig,
    AgentTurnResult,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    STATUS_API_ERROR,
    STATUS_CANCELLED,
    STATUS_COMPLETE,
    STATUS_MAX_ITERATIONS,
    STATUS_UNKNOWN_STOP,
    run_turn,
)
from synapse.cognitive.dispatcher import AgentToolError, Dispatcher


# ---------------------------------------------------------------------------
# Scripted mock Anthropic client
# ---------------------------------------------------------------------------


class _MockResponse:
    """Minimal stand-in for ``anthropic.types.Message``."""

    def __init__(self, content: List[Dict[str, Any]], stop_reason: str):
        # agent_loop calls model_dump on each block; provide a
        # matching interface.
        self.content = [_MockBlock(b) for b in content]
        self.stop_reason = stop_reason


class _MockBlock:
    """Response content block with ``model_dump``."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def model_dump(self) -> Dict[str, Any]:
        return dict(self._data)


class _MockMessagesAPI:
    """Scripted responses in FIFO order; raises if script exhausted."""

    def __init__(self, script: List[_MockResponse]):
        self._script = list(script)
        self.create_calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _MockResponse:
        self.create_calls.append(kwargs)
        if not self._script:
            raise AssertionError("Mock Anthropic script exhausted")
        return self._script.pop(0)


class _MockClient:
    def __init__(self, script: List[_MockResponse]):
        self.messages = _MockMessagesAPI(script)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dispatcher_only() -> Dispatcher:
    """Dispatcher with no tools registered — bare infrastructure."""
    return Dispatcher(is_testing=True)


@pytest.fixture
def dispatcher_with_echo() -> Dispatcher:
    """Dispatcher with a trivial ``echo`` tool registered and schema."""
    d = Dispatcher(is_testing=True)
    d.register(
        "echo",
        lambda **kw: {"echoed": kw},
        schema={
            "description": "Echoes kwargs back as a dict.",
            "input_schema": {
                "type": "object",
                "properties": {"msg": {"type": "string"}},
                "required": [],
            },
        },
    )
    return d


# ---------------------------------------------------------------------------
# Simple flows
# ---------------------------------------------------------------------------


class TestRunTurnSimple:
    def test_end_turn_exits_cleanly(self, dispatcher_only):
        client = _MockClient([
            _MockResponse(
                [{"type": "text", "text": "hello"}], stop_reason="end_turn"
            )
        ])
        result = run_turn(client, dispatcher_only, "hi")
        assert result.status == STATUS_COMPLETE
        assert result.iterations == 1
        assert len(result.messages) == 2  # user + assistant

    def test_stop_sequence_also_exits_cleanly(self, dispatcher_only):
        client = _MockClient([
            _MockResponse(
                [{"type": "text", "text": "done."}], stop_reason="stop_sequence"
            )
        ])
        result = run_turn(client, dispatcher_only, "hi")
        assert result.status == STATUS_COMPLETE
        assert result.iterations == 1

    def test_unknown_stop_reason_returns_error_status(self, dispatcher_only):
        client = _MockClient([
            _MockResponse([{"type": "text", "text": "?"}], stop_reason="max_tokens")
        ])
        result = run_turn(client, dispatcher_only, "hi")
        assert result.status == STATUS_UNKNOWN_STOP
        assert "max_tokens" in result.error

    def test_api_error_caught(self, dispatcher_only):
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("rate limited")
        result = run_turn(client, dispatcher_only, "hi")
        assert result.status == STATUS_API_ERROR
        assert "rate limited" in result.error
        assert result.iterations == 0

    def test_max_iterations_cap_hit(self, dispatcher_with_echo):
        # Every response demands a tool call — will loop forever without cap.
        looping = [
            _MockResponse([
                {"type": "tool_use", "id": f"tu-{i}",
                 "name": "echo", "input": {"msg": "x"}},
            ], stop_reason="tool_use")
            for i in range(20)
        ]
        client = _MockClient(looping)
        cfg = AgentTurnConfig(max_iterations=3)
        result = run_turn(client, dispatcher_with_echo, "loop forever",
                          config=cfg)
        assert result.status == STATUS_MAX_ITERATIONS
        assert result.iterations == 3
        assert result.tool_calls_made == 3


# ---------------------------------------------------------------------------
# Tool dispatch happy path
# ---------------------------------------------------------------------------


class TestRunTurnToolUse:
    def test_tool_use_then_end_turn(self, dispatcher_with_echo):
        """Classic flow: model uses a tool, receives result, wraps up."""
        client = _MockClient([
            _MockResponse([
                {"type": "tool_use", "id": "tu-1",
                 "name": "echo", "input": {"msg": "hi"}},
            ], stop_reason="tool_use"),
            _MockResponse(
                [{"type": "text", "text": "thanks"}], stop_reason="end_turn"
            ),
        ])
        result = run_turn(client, dispatcher_with_echo, "use echo")
        assert result.status == STATUS_COMPLETE
        assert result.tool_calls_made == 1
        assert result.iterations == 2
        # Messages: user, assistant(tool_use), user(tool_result), assistant(end)
        assert len(result.messages) == 4
        tool_result_msg = result.messages[2]
        assert tool_result_msg["role"] == "user"
        assert tool_result_msg["content"][0]["type"] == "tool_result"
        assert tool_result_msg["content"][0]["tool_use_id"] == "tu-1"
        # Tool output serialized as JSON into the content field
        content_str = tool_result_msg["content"][0]["content"]
        assert "echoed" in content_str

    def test_multiple_tool_blocks_dispatched_in_order(self, dispatcher_with_echo):
        """One response with two tool_use blocks → both dispatched."""
        client = _MockClient([
            _MockResponse([
                {"type": "tool_use", "id": "tu-a", "name": "echo", "input": {"msg": "a"}},
                {"type": "tool_use", "id": "tu-b", "name": "echo", "input": {"msg": "b"}},
            ], stop_reason="tool_use"),
            _MockResponse(
                [{"type": "text", "text": "done"}], stop_reason="end_turn"
            ),
        ])
        result = run_turn(client, dispatcher_with_echo, "use echo twice")
        assert result.status == STATUS_COMPLETE
        assert result.tool_calls_made == 2
        tool_results = result.messages[2]["content"]
        assert len(tool_results) == 2
        assert tool_results[0]["tool_use_id"] == "tu-a"
        assert tool_results[1]["tool_use_id"] == "tu-b"

    def test_dispatcher_schemas_passed_to_client(self, dispatcher_with_echo):
        """Schema from register() should surface in the Anthropic tools= param."""
        client = _MockClient([
            _MockResponse(
                [{"type": "text", "text": "ok"}], stop_reason="end_turn"
            )
        ])
        run_turn(client, dispatcher_with_echo, "hi")
        call_kwargs = client.messages.create_calls[0]
        assert "tools" in call_kwargs
        names = [t["name"] for t in call_kwargs["tools"]]
        assert "echo" in names


# ---------------------------------------------------------------------------
# ``hou.ObjectWasDeleted`` routing — the Crucible "Full" pass criterion
# ---------------------------------------------------------------------------


class TestObjectWasDeletedRouting:
    """The core Crucible resilience claim: a tool raising
    ``hou.ObjectWasDeleted`` must come back to the LLM as data, not
    as a silent retry or a crash.

    We stand in a fake ``hou.ObjectWasDeleted`` exception class so
    the test runs outside Houdini."""

    class _FakeObjectWasDeleted(Exception):
        """Stand-in for the real hou.ObjectWasDeleted exception."""

    def test_tool_exception_routes_as_agent_tool_error(self):
        dispatcher = Dispatcher(is_testing=True)

        def _dead_node_tool(**kwargs: Any) -> Dict[str, Any]:
            raise self._FakeObjectWasDeleted(
                "Node /stage/dead was deleted while tool was reasoning"
            )

        dispatcher.register(
            "touch_dead_node",
            _dead_node_tool,
            schema={
                "description": "Demo tool that simulates stale-pointer failure.",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        )

        client = _MockClient([
            _MockResponse([
                {"type": "tool_use", "id": "tu-1",
                 "name": "touch_dead_node",
                 "input": {"path": "/stage/dead"}},
            ], stop_reason="tool_use"),
            _MockResponse(
                [{"type": "text", "text": "Understood, that node is gone."}],
                stop_reason="end_turn",
            ),
        ])

        result = run_turn(client, dispatcher, "touch /stage/dead")
        assert result.status == STATUS_COMPLETE
        # Exactly one AgentToolError surfaced for the dead-node touch.
        assert len(result.tool_errors) == 1
        err = result.tool_errors[0]
        assert err.error_type == "_FakeObjectWasDeleted"
        assert "deleted while tool was reasoning" in err.error_message
        # Error is ALSO serialized into the tool_result content the LLM sees.
        tool_result_content = result.messages[2]["content"][0]["content"]
        assert "agent_tool_error" in tool_result_content
        assert "_FakeObjectWasDeleted" in tool_result_content

    def test_no_silent_retry_on_dead_node(self):
        """Guard rail: if a tool raises, the loop must NOT retry it
        with the same input on the same iteration.

        In-loop: each tool_use block is dispatched exactly once.
        Cross-iteration: whether to retry is the LLM's decision
        based on seeing the error in the tool_result content.
        """
        dispatch_count = 0

        def _counting_dead_tool(**kwargs: Any) -> Dict[str, Any]:
            nonlocal dispatch_count
            dispatch_count += 1
            raise self._FakeObjectWasDeleted("dead")

        dispatcher = Dispatcher(is_testing=True)
        dispatcher.register(
            "dead",
            _counting_dead_tool,
            schema={
                "description": "Always raises _FakeObjectWasDeleted.",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
        )
        client = _MockClient([
            _MockResponse([
                {"type": "tool_use", "id": "tu-1",
                 "name": "dead", "input": {}},
            ], stop_reason="tool_use"),
            _MockResponse(
                [{"type": "text", "text": "OK, stopping."}],
                stop_reason="end_turn",
            ),
        ])
        run_turn(client, dispatcher, "poke dead")
        assert dispatch_count == 1  # not 2, not 3 — exactly 1


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestRunTurnCancellation:
    def test_cancel_before_first_api_call(self, dispatcher_only):
        client = _MockClient([
            _MockResponse(
                [{"type": "text", "text": "should never send"}],
                stop_reason="end_turn",
            ),
        ])
        event = threading.Event()
        event.set()

        result = run_turn(
            client, dispatcher_only, "prompt",
            cancel_event=event,
        )
        assert result.status == STATUS_CANCELLED
        assert result.iterations == 0
        # Client was NOT called — cancel cut before the API yield.
        assert client.messages.create_calls == []

    def test_cancel_after_first_response(self, dispatcher_with_echo):
        """Cancel between network return and tool dispatch."""
        event = threading.Event()

        # Real _MockMessagesAPI but set the cancel event from inside
        # the first create() call to simulate cancel arriving during
        # network I/O.
        class _CancelOnCreate(_MockMessagesAPI):
            def create(self, **kwargs):
                resp = super().create(**kwargs)
                event.set()
                return resp

        client = _MockClient([])
        client.messages = _CancelOnCreate([
            _MockResponse([
                {"type": "tool_use", "id": "tu-1",
                 "name": "echo", "input": {"msg": "hi"}},
            ], stop_reason="tool_use"),
        ])

        result = run_turn(client, dispatcher_with_echo, "x", cancel_event=event)
        assert result.status == STATUS_CANCELLED
        assert result.iterations == 1
        # Tool was NOT dispatched — cancelled before tool phase.
        assert result.tool_calls_made == 0

    def test_cancel_between_tool_blocks(self, dispatcher_with_echo):
        """Cancel mid-batch: response has 2 tool_use blocks, cancel
        fires after the first dispatch."""
        event = threading.Event()
        call_count = 0

        def _echo_with_trip(**kw: Any) -> Dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                event.set()  # trip cancel after first call
            return {"echoed": kw}

        dispatcher = Dispatcher(is_testing=True)
        dispatcher.register(
            "echo",
            _echo_with_trip,
            schema={"description": "x", "input_schema": {"type": "object"}},
        )

        client = _MockClient([
            _MockResponse([
                {"type": "tool_use", "id": "tu-a", "name": "echo", "input": {}},
                {"type": "tool_use", "id": "tu-b", "name": "echo", "input": {}},
            ], stop_reason="tool_use"),
        ])
        result = run_turn(client, dispatcher, "x", cancel_event=event)
        assert result.status == STATUS_CANCELLED
        # First tool ran; second was skipped.
        assert call_count == 1
        assert result.tool_calls_made == 1

    def test_cancel_event_none_disables_cancellation(self, dispatcher_only):
        """Passing cancel_event=None should never treat the agent as cancelled."""
        client = _MockClient([
            _MockResponse(
                [{"type": "text", "text": "ok"}], stop_reason="end_turn"
            )
        ])
        result = run_turn(client, dispatcher_only, "x", cancel_event=None)
        assert result.status == STATUS_COMPLETE


# ---------------------------------------------------------------------------
# Config + surface
# ---------------------------------------------------------------------------


class TestConfigAndSurface:
    def test_default_model_is_set(self):
        assert DEFAULT_MODEL.startswith("claude-")

    def test_config_defaults_match_module_constants(self):
        cfg = AgentTurnConfig()
        assert cfg.model == DEFAULT_MODEL
        assert cfg.max_tokens == DEFAULT_MAX_TOKENS
        assert cfg.max_iterations == DEFAULT_MAX_ITERATIONS

    def test_system_prompt_included_when_set(self, dispatcher_only):
        client = _MockClient([
            _MockResponse([{"type": "text", "text": "ok"}], stop_reason="end_turn")
        ])
        cfg = AgentTurnConfig(system="You are a test.")
        run_turn(client, dispatcher_only, "hi", config=cfg)
        assert client.messages.create_calls[0]["system"] == "You are a test."

    def test_system_prompt_omitted_when_empty(self, dispatcher_only):
        client = _MockClient([
            _MockResponse([{"type": "text", "text": "ok"}], stop_reason="end_turn")
        ])
        run_turn(client, dispatcher_only, "hi")
        assert "system" not in client.messages.create_calls[0]
