"""H-3 (2026-10-04): an error reply carries the id of the request that failed.

Clients match replies by id (mcp_server.py discards a reply whose id has no
pending future). Both transports answered a handler exception with
id="unknown", so the caller never saw the error and waited out its whole
command timeout instead.
"""
import ast
import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from synapse.core.protocol import SynapseCommand, SynapseResponse


def _standalone_server(handler):
    from synapse.server import websocket as transport
    server = object.__new__(transport.SynapseServer)
    server._handler, server._session_manager = handler, None
    server._enable_resilience = False
    server._circuit_breaker = None
    server._avg_latency, server._latency_alpha = 0.0, 0.2
    return server


def test_standalone_ws_error_reply_keeps_the_request_id():
    handler = SimpleNamespace(handle=Mock(side_effect=RuntimeError("boom")))
    sent = []
    _standalone_server(handler)._handle_message(
        SimpleNamespace(send=lambda value: sent.append(json.loads(value))),
        json.dumps({"type": "ping", "id": "req-7", "payload": {}}), "local")
    assert sent[0]["id"] == "req-7"
    assert sent[0]["success"] is False and "boom" in sent[0]["error"]


def test_standalone_ws_unparseable_message_still_says_unknown():
    handler = SimpleNamespace(handle=Mock())
    sent = []
    _standalone_server(handler)._handle_message(
        SimpleNamespace(send=lambda value: sent.append(json.loads(value))),
        "{not json", "local")
    assert sent[0]["id"] == "unknown" and sent[0]["success"] is False
    handler.handle.assert_not_called()


def test_hwebserver_error_reply_keeps_the_request_id():
    from synapse.core.farm_contract import FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
    path = Path(__file__).parents[1] / "python/synapse/server/hwebserver_adapter.py"
    node = next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "receive")
    sent = []

    async def send(text, **kwargs):
        sent.append(json.loads(text))

    handler = SimpleNamespace(handle=Mock(side_effect=RuntimeError("boom")))
    ns = {"__name__": "synapse.server.hwebserver_adapter", "__package__": "synapse.server",
          "json": json, "_dumps": json.dumps, "logger": logging.getLogger("h3-test"),
          "SynapseCommand": SynapseCommand, "SynapseResponse": SynapseResponse,
          "_READ_ONLY_COMMANDS": FARM_READ_COMMANDS | {"ping"},
          "_read_only_refusal_for_command": lambda _command_type: None,
          "FARM_CONTROL_COMMANDS": FARM_CONTROL_COMMANDS, "FARM_READ_COMMANDS": FARM_READ_COMMANDS,
          "_get_handler": lambda: handler, "get_bridge": Mock(),
          "_client_sessions": {}, "_rate_limiter": None, "_circuit_breaker": None,
          "_preflight_refusal_for": lambda *args: None, "_preflight_note_for": lambda *args: None}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    connection = SimpleNamespace(_authenticated=True, _client_id="local", _session_id=None, send=send)
    asyncio.run(ns["receive"](connection, json.dumps({"type": "ping", "id": "req-9", "payload": {}})))
    assert sent[-1]["id"] == "req-9"
    assert sent[-1]["success"] is False and "boom" in sent[-1]["error"]
