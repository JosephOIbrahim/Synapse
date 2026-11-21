"""R-015 (BRAINSTEM-7) — a service failure opens the transports' breakers.

``core/errors.py`` promises "SynapseServiceError -> success=False + trip CB",
and that only SynapseServiceError trips it. Before this repair neither live
dispatcher could honor that promise:

  * the hwebserver WS adapter recorded only SUCCESSES on its transport breaker
    — handler failures were deliberately NOT recorded — so five service-error
    responses left it closed and the sixth command was dispatched again;
  * /mcp classified failures by matching words in the error TEXT ("timeout",
    "main thread", "crashed", "unresponsive"), so a service error that did not
    happen to use one of those words was never counted, and a user error that
    did was.

The repair classifies by the outcome code the handler attached to the failed
response — the exception TYPE's classification (SynapseServiceError ->
tool.failed, a mutating main-thread timeout -> transport.timeout) — never by
the text. These tests drive a DEFAULT-constructed handler through each
dispatcher with a test breaker, so the gate and the counting are the shipped
ones.

Standalone: no hou, no hdefereval, no network. The "service" command is
``set_parm``, which raises HoudiniUnavailableError through a default handler
when hou is absent; the "user error" command is ``propose_graph`` with no
proposal, which raises SynapseUserError before any hou call.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from synapse.core.outcomes import is_service_failure
from synapse.core.protocol import SynapseCommand, SynapseResponse
from synapse.server.handlers import SynapseHandler
from synapse.server.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)

ROOT = Path(__file__).resolve().parents[1]

#: -> "set_parm": registered, mutating, and raises HoudiniUnavailableError
#: through a default handler in this process (no hou).
_SERVICE_COMMAND = {"type": "set_parm", "payload": {
    "node": "/obj/geo1", "parm": "tx", "value": 1.0}}
_SERVICE_TOOL = "houdini_set_parm"

#: -> raises SynapseUserError ("needs a 'proposal' object") before hou.
_USER_ERROR_COMMAND = {"type": "propose_graph", "payload": {}}
_USER_ERROR_TOOL = "synapse_propose_graph"


# ---------------------------------------------------------------------------
# A default handler, with side effects that are not the subject turned off
# ---------------------------------------------------------------------------

@pytest.fixture
def handler(monkeypatch):
    """The shipped, default-constructed handler — nothing stubbed in its registry."""
    from synapse.server import handlers as handlers_module

    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
    monkeypatch.delenv("SYNAPSE_COOK_SANDWICH", raising=False)
    # This process has no Houdini; say so explicitly so the test never depends on
    # whatever another test file may have put in sys.modules["hou"].
    monkeypatch.setattr(handlers_module, "HOU_AVAILABLE", False)
    # The observe-only envelope is not the subject; its scene hashes would only
    # add a hou fallback path to the call count.
    monkeypatch.setattr(handlers_module._envelope, "envelope_active",
                        lambda _cmd_type: False)
    h = SynapseHandler()
    # Audit/session logging is not the subject and would open a real bridge.
    monkeypatch.setattr(h, "_submit_logs", lambda *args, **kwargs: None)
    return h


def _count_dispatches(handler):
    """Every command that actually reaches the handler, in order."""
    calls = []
    real = handler.handle

    def counted(command):
        calls.append(command.type)
        return real(command)

    handler.handle = counted
    return calls


def _breaker(name):
    """A test breaker with the shipped threshold (5 failures -> open)."""
    return CircuitBreaker(name=name,
                          config=CircuitBreakerConfig(failure_threshold=5,
                                                      timeout_seconds=30.0))


# ---------------------------------------------------------------------------
# The classification itself: outcome code, never text
# ---------------------------------------------------------------------------

def test_the_classification_reads_the_outcome_code_and_never_the_text():
    assert is_service_failure({"code": "tool.failed", "outcome": "failed"})
    assert is_service_failure({"code": "tool.internal", "outcome": "unknown_outcome"})
    assert is_service_failure({"code": "execution.deadline_exceeded",
                               "outcome": "unknown_outcome"})
    assert is_service_failure({"code": "transport.timeout", "outcome": "unknown_outcome"})

    # A refused/user failure is not a service failure, however alarming the words.
    assert not is_service_failure({"code": "policy.safety_guard", "outcome": "refused"})
    # A READ that timed out changes nothing: a retry, not a service fault.
    assert not is_service_failure({"code": "transport.read_retry", "outcome": "retryable"})
    # No attached outcome = unclassified. The words never decide it.
    assert not is_service_failure(None)
    assert not is_service_failure({"outcome": "failed",
                                   "message": "Houdini crashed: main thread timeout"})


def test_a_service_error_carries_its_outcome_on_the_response(handler):
    response = handler.handle(SynapseCommand(
        type=_SERVICE_COMMAND["type"], id="r015-svc",
        payload=dict(_SERVICE_COMMAND["payload"])))
    assert response.success is False
    assert response.data["outcome"]["code"] == "tool.failed"
    assert response.data["outcome"]["outcome"] == "failed"


def test_a_user_error_carries_no_service_outcome(handler):
    response = handler.handle(SynapseCommand(
        type=_USER_ERROR_COMMAND["type"], id="r015-user",
        payload=dict(_USER_ERROR_COMMAND["payload"])))
    assert response.success is False
    assert "proposal" in (response.error or "")
    # Nothing for a breaker to classify — and it is NOT the error text's job.
    assert response.data is None


def test_the_ws_helper_reads_the_response_outcome():
    from synapse.core.outcomes import info
    from synapse.server.hwebserver_adapter import _service_failure

    timeout = SynapseResponse(id="t", success=False, error="main thread timed out",
                              data={"outcome": info("transport.timeout", "x").to_dict()})
    user = SynapseResponse(id="u", success=False,
                           error="Houdini crashed: main thread timeout", data=None)
    assert _service_failure(timeout) is True
    assert _service_failure(user) is False  # the words never decide it


# ---------------------------------------------------------------------------
# WS dispatcher (the live hwebserver transport)
# ---------------------------------------------------------------------------

def _hwebserver_receive(handler, breaker):
    """The shipped ``receive`` coroutine, AST-extracted (hwebserver is absent here)."""
    from synapse.core.farm_contract import FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
    from synapse.server import hwebserver_adapter as adapter
    from synapse.server.handlers import _READ_ONLY_COMMANDS

    path = ROOT / "python/synapse/server/hwebserver_adapter.py"
    node = next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "receive")
    ns = {
        "__name__": "synapse.server.hwebserver_adapter",
        "__package__": "synapse.server",
        "json": json,
        "_dumps": json.dumps,
        "logger": logging.getLogger("r015-test"),
        "SynapseCommand": SynapseCommand,
        "SynapseResponse": SynapseResponse,
        "PROTOCOL_VERSION": "1.0.0",
        "_READ_ONLY_COMMANDS": _READ_ONLY_COMMANDS,
        "_read_only_refusal_for_command": lambda _command_type: None,
        "FARM_CONTROL_COMMANDS": FARM_CONTROL_COMMANDS,
        "FARM_READ_COMMANDS": FARM_READ_COMMANDS,
        "_get_handler": lambda: handler,
        "get_bridge": lambda: SimpleNamespace(
            start_session=lambda _client: "session-r015",
            end_session=lambda _session: None),
        "_client_sessions": {},
        "_rate_limiter": None,
        "_circuit_breaker": breaker,
        "_preflight_refusal_for": lambda *args: None,
        "_preflight_note_for": lambda *args: None,
        "_service_failure": adapter._service_failure,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return ns["receive"]


def _connection(sent):
    async def send(text, **kwargs):
        sent.append(json.loads(text))

    return SimpleNamespace(_authenticated=True, _client_id="r015",
                           _session_id=None, _ws_id=1, send=send)


def _ws_send(receive, connection, command_type, request_id, payload=None):
    asyncio.run(receive(connection, json.dumps({
        "type": command_type, "id": request_id, "payload": payload or {}})))
    return connection


def test_five_service_errors_open_the_ws_breaker_and_the_sixth_is_not_dispatched(handler):
    breaker = _breaker("r015-ws")
    calls = _count_dispatches(handler)
    receive = _hwebserver_receive(handler, breaker)
    sent: list = []
    connection = _connection(sent)

    for i in range(5):
        _ws_send(receive, connection, _SERVICE_COMMAND["type"], "svc-%d" % i,
                 dict(_SERVICE_COMMAND["payload"]))

    assert [wire["success"] for wire in sent] == [False] * 5
    assert {wire["data"]["outcome"]["code"] for wire in sent} == {"tool.failed"}
    assert breaker.state is CircuitState.OPEN
    assert calls == ["set_parm"] * 5

    _ws_send(receive, connection, _SERVICE_COMMAND["type"], "sixth",
             dict(_SERVICE_COMMAND["payload"]))

    sixth = sent[-1]
    assert sixth["id"] == "sixth"
    assert sixth["success"] is False
    assert sixth["data"]["outcome"]["code"] == "server.busy"
    assert sixth["data"]["outcome"]["outcome"] == "retryable"
    assert sixth["data"]["state"] == "open"
    assert calls == ["set_parm"] * 5, "the sixth command must not be dispatched"


def test_ws_user_errors_never_open_the_breaker(handler):
    breaker = _breaker("r015-ws-user")
    calls = _count_dispatches(handler)
    receive = _hwebserver_receive(handler, breaker)
    sent: list = []
    connection = _connection(sent)

    for i in range(6):
        _ws_send(receive, connection, _USER_ERROR_COMMAND["type"], "user-%d" % i,
                 dict(_USER_ERROR_COMMAND["payload"]))

    assert [wire["success"] for wire in sent] == [False] * 6
    assert breaker.state is CircuitState.CLOSED
    assert calls == ["propose_graph"] * 6


# ---------------------------------------------------------------------------
# /mcp dispatcher — the same predicate, same threshold, same sixth answer
# ---------------------------------------------------------------------------

def _standalone_mcp(monkeypatch):
    """Route /mcp dispatch straight to the handler (no bridge, no marshal, no loop)."""
    from synapse.mcp import server as server_module
    from synapse.panel import bridge_adapter
    import synapse.server.main_thread as main_thread

    monkeypatch.delenv("SYNAPSE_MCP_READ_ONLY", raising=False)
    monkeypatch.setenv("SYNAPSE_LOOP_ENABLED", "0")
    monkeypatch.setattr(server_module, "_STALL_DETECT_AVAILABLE", False, raising=False)
    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: None)
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kwargs: fn())


def _mcp_server(handler):
    from synapse.mcp import server as server_module

    server = server_module.MCPServer(handler=handler)
    assert server._enable_resilience is True, "resilience must be on for this test"
    server._rate_limiter = None  # token buckets are not the subject
    return server


def test_five_service_errors_open_the_mcp_breaker_and_the_sixth_is_not_dispatched(
        handler, monkeypatch):
    _standalone_mcp(monkeypatch)
    server = _mcp_server(handler)
    calls = _count_dispatches(handler)

    for i in range(5):
        result = server._handle_tools_call({
            "name": _SERVICE_TOOL, "arguments": dict(_SERVICE_COMMAND["payload"])})
        assert result["isError"] is True
        assert result["_meta"]["synapse/outcome"]["code"] == "tool.failed"

    assert server._circuit_breaker.state is CircuitState.OPEN
    assert calls == ["set_parm"] * 5

    sixth = server._handle_tools_call({
        "name": _SERVICE_TOOL, "arguments": dict(_SERVICE_COMMAND["payload"])})
    outcome = sixth["_meta"]["synapse/outcome"]
    assert sixth["isError"] is True
    assert (outcome["code"], outcome["outcome"]) == ("server.busy", "retryable")
    assert calls == ["set_parm"] * 5, "the sixth call must not be dispatched"


def test_mcp_user_errors_never_open_the_breaker(handler, monkeypatch):
    _standalone_mcp(monkeypatch)
    server = _mcp_server(handler)
    calls = _count_dispatches(handler)

    for _ in range(6):
        result = server._handle_tools_call({"name": _USER_ERROR_TOOL, "arguments": {}})
        assert result["isError"] is True

    assert server._circuit_breaker.state is CircuitState.CLOSED
    assert calls == ["propose_graph"] * 6


def test_mcp_counts_a_timeout_by_its_outcome_code(handler, monkeypatch):
    """An attached transport.timeout is a breaker failure — one is enough here."""
    from synapse.core.outcomes import info
    from synapse.mcp import server as server_module

    _standalone_mcp(monkeypatch)
    server = _mcp_server(handler)
    server._circuit_breaker = CircuitBreaker(
        name="r015-mcp-timeout",
        config=CircuitBreakerConfig(failure_threshold=1))
    attached = {"content": [{"type": "text", "text": "timed out"}], "isError": True,
                "structuredContent": {"outcome": info("transport.timeout", "timed out").to_dict()}}
    monkeypatch.setattr(server_module, "dispatch_tool",
                        lambda _handler, _name, _arguments: attached)

    result = server._handle_tools_call({"name": _SERVICE_TOOL, "arguments": {}})
    assert result["_meta"]["synapse/outcome"]["code"] == "transport.timeout"
    assert server._circuit_breaker.state is CircuitState.OPEN


def test_mcp_never_counts_a_failure_by_the_text_it_carries(handler, monkeypatch):
    """The old heuristic counted these words; the repair counts only the code."""
    from synapse.mcp import server as server_module

    _standalone_mcp(monkeypatch)
    server = _mcp_server(handler)
    server._circuit_breaker = CircuitBreaker(
        name="r015-mcp-text",
        config=CircuitBreakerConfig(failure_threshold=1))
    words_only = {"content": [
        {"type": "text", "text": "The main thread timeout was reached: crashed, unresponsive"}],
        "isError": True}
    monkeypatch.setattr(server_module, "dispatch_tool",
                        lambda _handler, _name, _arguments: words_only)

    result = server._handle_tools_call({"name": _SERVICE_TOOL, "arguments": {}})
    # The wire still answers transport.timeout for an unattached failure (the
    # Level 1 R-6 pin), but the breaker is untouched: words are not a code.
    assert result["_meta"]["synapse/outcome"]["code"] == "transport.timeout"
    assert server._circuit_breaker.state is CircuitState.CLOSED
