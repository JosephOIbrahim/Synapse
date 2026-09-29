"""MCP polish (BP12 item 12): 202 for notifications, and an opt-in read-only mode.

``POST /mcp`` answered a notification with 204 No Content, which hwebserver frames
with ``Transfer-Encoding: chunked`` and no chunk; Python's http.client then waited
for the chunk and hung the kept-alive connection (reproduced on the live server and
on a private hwebserver under hython, where 202 works). It now answers 202 Accepted
with no body, as the MCP Streamable HTTP transport specifies.

``SYNAPSE_MCP_READ_ONLY`` fences external clients to the tools that are read-only
under both gating sets, on ``/mcp`` and on the WebSocket that ``mcp_server.py``
uses. Protocol commands pass, and the panel's own agent is never gated.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from synapse.mcp import read_only_mode as RO
from synapse.mcp import server as S
from synapse.mcp._tool_registry import TOOL_DEFS, TOOL_JSON
from synapse.mcp.protocol import JsonRpcError, READ_ONLY_REFUSED

_CMD = {entry[0]: entry[1] for entry in TOOL_DEFS}
BOTH_SETS = sorted(name for name in _CMD if S.is_transport_fast_path(name))[0]
TRANSPORT_ONLY = sorted(S.read_only_set_divergence())
MUTATING = sorted(name for name in _CMD if name not in S._READ_ONLY_TOOLS)[0]


# ── 202 for a notification ──────────────────────────────────────────────────

def test_a_notification_gets_202_with_no_body():
    assert S._post_response(None, {"Content-Type": "application/json"}) == ("", 202, "text/plain", {})


def test_a_request_gets_200_with_its_body_and_headers():
    body, status, content_type, extra = S._post_response(
        b'{"jsonrpc": "2.0", "id": 1, "result": {}}',
        {"Content-Type": "application/json", "Mcp-Session-Id": "abc"})
    assert (status, content_type, extra) == (200, "application/json", {"Mcp-Session-Id": "abc"})
    assert json.loads(body)["id"] == 1


# ── the read-only gate ──────────────────────────────────────────────────────

def test_mode_is_off_by_default(monkeypatch):
    monkeypatch.delenv(RO.ENV, raising=False)
    for name in (BOTH_SETS, MUTATING, *TRANSPORT_ONLY):
        assert RO.refusal_for_tool(name) is None


def test_mode_allows_only_tools_read_only_under_both_sets(monkeypatch):
    """A tool read-only to the transport but mutating to the bridge is refused too.

    Checking the transport annotation alone would let those through."""
    monkeypatch.setenv(RO.ENV, "1")
    assert RO.refusal_for_tool(BOTH_SETS) is None
    refusal = RO.refusal_for_tool(MUTATING)
    assert refusal and MUTATING in refusal and RO.ENV in refusal
    assert TRANSPORT_ONLY, "expected the transport/bridge divergence to be non-empty"
    for name in TRANSPORT_ONLY:
        assert RO.refusal_for_tool(name), name


def test_protocol_commands_are_never_refused(monkeypatch):
    monkeypatch.setenv(RO.ENV, "1")
    for command_type in ("authenticate", "heartbeat", "ping", "get_health", "context"):
        assert RO.refusal_for_command(command_type) is None
    assert RO.refusal_for_command(_CMD[MUTATING])
    assert RO.refusal_for_command(_CMD[BOTH_SETS]) is None


def test_mcp_tools_call_is_refused_before_dispatch(monkeypatch):
    monkeypatch.setenv(RO.ENV, "1")
    monkeypatch.setattr(S, "dispatch_tool", Mock(side_effect=AssertionError("dispatched")))
    server = object.__new__(S.MCPServer)
    server._get_handler = lambda: None
    with pytest.raises(JsonRpcError) as caught:
        server._handle_tools_call({"name": MUTATING, "arguments": {}})
    assert caught.value.code == READ_ONLY_REFUSED
    assert MUTATING in str(caught.value) and RO.ENV in str(caught.value)


def test_websocket_command_is_refused_before_the_handler(monkeypatch):
    from synapse.core.protocol import SynapseResponse
    from synapse.server import websocket as transport

    handler = SimpleNamespace(handle=Mock(return_value=SynapseResponse(id="r", success=True, data={})))
    server = object.__new__(transport.SynapseServer)
    server._handler, server._session_manager = handler, None
    server._enable_resilience = False
    server._circuit_breaker = None
    server._avg_latency, server._latency_alpha = 0.0, 0.2

    def send(command_type):
        sent = []
        server._handle_message(SimpleNamespace(send=lambda value: sent.append(json.loads(value))),
                               json.dumps({"type": command_type, "id": "r", "payload": {}}), "local")
        return sent[0]

    monkeypatch.setenv(RO.ENV, "1")
    refused = send(_CMD[MUTATING])
    assert refused["success"] is False and RO.ENV in refused["error"]
    assert handler.handle.call_count == 0
    monkeypatch.delenv(RO.ENV)
    assert send(_CMD[MUTATING])["success"] is True
    assert handler.handle.call_count == 1


def test_the_hwebserver_websocket_route_runs_the_same_gate():
    """The in-Houdini WebSocket route cannot run here (it needs hwebserver), so its
    source is pinned: the gate runs before the handler is reached."""
    from pathlib import Path

    text = (Path(S.__file__).resolve().parents[1] / "server" / "hwebserver_adapter.py").read_text(
        encoding="utf-8")
    gate = text.index("refusal = _read_only_refusal_for_command(command.type)")
    assert gate < text.index("# Lazy session creation") < text.index("response = handler.handle(command)", gate)
