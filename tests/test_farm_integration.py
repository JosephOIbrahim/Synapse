"""Production routing regressions: admission, responsiveness and local access."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock
import threading

import pytest


def test_canonical_tools_have_real_dispatch_and_correct_annotations():
    from synapse.mcp._tool_registry import TOOL_DEFS
    from synapse.core.farm_contract import FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
    from synapse.server.handlers import SynapseHandler
    from synapse.server.rbac import Role, check_permission
    handler = SynapseHandler()
    definitions = {row[0]: row for row in TOOL_DEFS}
    for command in FARM_CONTROL_COMMANDS | FARM_READ_COMMANDS:
        row = definitions["synapse_" + command]
        assert handler._registry.get(row[1]) is not None
        assert row[2]({"request_id": "same-intent"}) == {"request_id": "same-intent"}
        assert row[5] is (command in FARM_READ_COMMANDS)
        assert check_permission(Role.ARTIST, command)
        assert check_permission(Role.VIEWER, command) is (command in FARM_READ_COMMANDS)
    assert definitions["synapse_farm_cancel"][6] is True


@pytest.mark.parametrize("allowed", [False, True])
def test_control_keeps_consent_without_scene_bridge(monkeypatch, allowed):
    from synapse.panel import bridge_adapter as adapter
    from synapse.core.protocol import SynapseCommand, SynapseResponse
    bridge = SimpleNamespace(authorize_external_operation=Mock(return_value=allowed),
                             execute=Mock(side_effect=AssertionError("Scene bridge invoked")))
    monkeypatch.setattr(adapter, "get_bridge", lambda: bridge)
    handler = SimpleNamespace(handle=Mock(return_value=SynapseResponse(
        id="call", success=True, data={"state": "rendering"})))
    command = SynapseCommand(type="farm_submit", id="call", payload={"request_id": "intent", "digest": "frozen"})
    response = adapter.execute_farm_control("synapse_farm_submit", handler, command)
    assert response.success is allowed
    assert handler.handle.call_count == int(allowed)
    assert bridge.authorize_external_operation.call_args.args[0].kwargs["touches_disk"]
    bridge.execute.assert_not_called()
    if allowed:
        assert "_integrity" not in response.data
        assert response.data["_execution"]["scene_undo_applicable"] is False


def test_absent_admission_fails_closed(monkeypatch):
    from synapse.panel import bridge_adapter as adapter
    from synapse.core.protocol import SynapseCommand
    monkeypatch.setattr(adapter, "get_bridge", lambda: None)
    handler = SimpleNamespace(handle=Mock())
    result = adapter.execute_farm_control("synapse_farm_cancel", handler,
        SynapseCommand(type="farm_cancel", id="call", payload={"request_id": "intent"}))
    assert not result.success
    handler.handle.assert_not_called()


@pytest.mark.parametrize("tool", ["synapse_farm_submit", "synapse_farm_cancel"])
def test_http_control_remains_off_main_when_houdini_is_stalled(monkeypatch, tool):
    from synapse.mcp import server as server_module
    from synapse.panel import bridge_adapter as adapter
    from synapse.server import main_thread
    from synapse.core.protocol import SynapseResponse
    monkeypatch.setattr(server_module, "is_main_thread_stalled", lambda: True)
    monkeypatch.setattr(server_module, "probe_main_thread", Mock(side_effect=AssertionError("Waited for GUI")))
    monkeypatch.setattr(main_thread, "run_on_main", Mock(side_effect=AssertionError("Marshalled whole control")))
    monkeypatch.setattr(adapter, "get_bridge", lambda: SimpleNamespace(authorize_external_operation=lambda op: True))
    called = []
    handler = SimpleNamespace(handle=lambda cmd: (called.append(threading.get_ident()) or
        SynapseResponse(id=cmd.id, success=True, data={"state": "rendering"})))
    server = server_module.MCPServer(handler=handler)
    server._enable_resilience = False
    result = server._handle_tools_call({"name": tool, "arguments": {"request_id": "intent", "digest": "frozen"}}, None)
    assert not result.get("isError")
    assert called == [threading.get_ident()]


def test_http_controls_still_obey_rate_admission(monkeypatch):
    from synapse.mcp import server as server_module
    handler = SimpleNamespace(handle=Mock())
    server = server_module.MCPServer(handler=handler)
    server._enable_resilience = True
    server._rate_limiter = SimpleNamespace(acquire=lambda _: (False, {"reason": "capacity"}))
    with pytest.raises(server_module.JsonRpcError):
        server._handle_tools_call({"name": "synapse_farm_submit", "arguments": {}}, None)
    handler.handle.assert_not_called()


def test_job_controls_bypass_scene_lock_and_memory_but_keep_provenance(monkeypatch, tmp_path):
    from synapse.server import handlers
    from synapse.core.protocol import SynapseCommand
    monkeypatch.setenv("SYNAPSE_PROVENANCE_DIR", str(tmp_path / "provenance"))
    monkeypatch.setenv("SYNAPSE_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(handlers, "_MUTATION_LOCK", Mock(__enter__=Mock(side_effect=AssertionError("Scene lock"))))
    monkeypatch.setattr(handlers._envelope, "capture_scene_hash", Mock(side_effect=AssertionError("Scene hash")))
    handler = handlers.SynapseHandler()
    handler._get_bridge = Mock(side_effect=AssertionError("Constructed memory store"))
    handler._registry.register("farm_submit", lambda _: {"state": "rendering"})
    results = []
    worker = threading.Thread(target=lambda: results.append(handler.handle(
        SynapseCommand(type="farm_submit", id="call", payload={"request_id": "intent"}))))
    worker.start()
    worker.join(5)
    assert not worker.is_alive()
    assert results[0].success, results[0].error
    assert list((tmp_path / "provenance").glob("*.json"))
    handler._get_bridge.assert_not_called()


def test_opening_empty_history_never_constructs_service(monkeypatch, tmp_path):
    from synapse.server import handlers_farm as farm
    monkeypatch.setenv("SYNAPSE_RENDER_HOME", str(tmp_path / "unused"))
    monkeypatch.setattr(farm, "_services", {})
    monkeypatch.setattr(farm, "_backend", Mock(side_effect=AssertionError("Constructed backend")))
    assert farm.FarmHandlerMixin()._handle_farm_jobs({}) == {"jobs": []}
    assert not (tmp_path / "unused").exists()


def test_scene_batch_cannot_run_detached_job_control():
    from synapse.server.handlers import SynapseHandler
    handler = SynapseHandler()
    with pytest.raises(ValueError, match="separate requests"):
        handler._handle_batch_commands({"commands": [{"type": "farm_submit", "payload": {}}]})


def test_scene_batch_cannot_hash_render_outputs_on_main():
    from synapse.server.handlers import SynapseHandler
    with pytest.raises(ValueError, match="separate requests"):
        SynapseHandler()._handle_batch_commands({"commands": [{"type": "farm_job", "payload": {}}]})


def test_real_bridge_without_policy_denies_external_admission():
    from shared.bridge import LosslessExecutionBridge
    bridge = object.__new__(LosslessExecutionBridge)
    bridge._gate = None
    bridge._consent_callback = None
    bridge._check_consent = Mock(side_effect=AssertionError("Reached legacy default allow"))
    assert bridge.authorize_external_operation(object()) is False
    bridge._check_consent.assert_not_called()


@pytest.mark.parametrize("command", ["prepare", "submit", "cancel", "job", "jobs"])
def test_unqualified_studio_deployment_cannot_access_job_authority(monkeypatch, command):
    from synapse.server import handlers_farm as farm
    monkeypatch.setenv("SYNAPSE_DEPLOY_MODE", "studio")
    service = Mock(side_effect=AssertionError("Opened job authority without studio identity"))
    monkeypatch.setattr(farm, "_service", service)
    with pytest.raises(ValueError, match="local deployment only"):
        getattr(farm.FarmHandlerMixin(), "_handle_farm_" + command)({})
    service.assert_not_called()


def test_dirty_source_file_alias_is_refused(monkeypatch, tmp_path):
    from synapse.server import handlers_farm as farm
    source = tmp_path / "artist.hip"
    source.write_bytes(b"saved")
    monkeypatch.setattr(farm, "_inspect_saved_source", lambda: {"source_hip": str(source), "unsaved": True})
    monkeypatch.setattr(farm.os.path, "samefile", lambda a, b: True)
    service = Mock()
    monkeypatch.setattr(farm, "_service", lambda: service)
    with pytest.raises(ValueError, match="Save the scene"):
        farm.FarmHandlerMixin()._handle_farm_prepare({"source_hip": str(tmp_path / "alias.hip")})
    service.prepare.assert_not_called()


def _local_client_class():
    # Run the actual stdlib-only class without importing Qt into stock Python.
    import http.client
    import time
    from typing import Optional
    path = Path(__file__).parents[1] / "python/synapse/panel/tool_executor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_MCPLocalClient")
    ns = {"Optional": Optional, "threading": threading, "json": json, "http": http, "time": time}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return ns["_MCPLocalClient"]


def test_local_client_authenticates_to_loopback(monkeypatch):
    import http.client
    from synapse.server import auth
    monkeypatch.setattr(auth, "get_auth_key", lambda: "test-only-key")
    response = SimpleNamespace(read=lambda: b'{"result": {}}', getheader=lambda _: None)
    connection = SimpleNamespace(request=Mock(), getresponse=lambda: response, close=Mock())
    constructor = Mock(return_value=connection)
    monkeypatch.setattr(http.client, "HTTPConnection", constructor)
    client = _local_client_class()()
    client._port = 12345
    client._post({"method": "initialize"})
    assert constructor.call_args.args == ("localhost", 12345)
    assert connection.request.call_args.kwargs["headers"]["Authorization"] == "Bearer test-only-key"


def test_local_client_reconnects_only_on_a_later_request(monkeypatch):
    import http.client
    from synapse.server import auth
    monkeypatch.setattr(auth, "get_auth_key", lambda: None)
    request = Mock(side_effect=ConnectionError("connection lost"))
    monkeypatch.setattr(http.client, "HTTPConnection", lambda *a, **k: SimpleNamespace(request=request, close=lambda: None))
    client = _local_client_class()()
    client._port, client._session_id = 12345, "old-session"
    with pytest.raises(ConnectionError):
        client._post({"method": "tools/call", "params": {"name": "synapse_farm_submit"}})
    assert request.call_count == 1
    assert client._port is None and client._session_id is None


def test_current_host_endpoint_and_cached_port_need_no_hom(monkeypatch, tmp_path):
    import os
    from synapse.server import bridge_endpoint, main_thread
    path = tmp_path / "endpoint.json"
    path.write_text(json.dumps({"pid": os.getpid(), "port": 12345}), encoding="utf-8")
    monkeypatch.setattr(bridge_endpoint, "bridge_file", lambda: str(path))
    monkeypatch.setattr(main_thread, "run_on_main", Mock(side_effect=AssertionError("Needed GUI for cached endpoint")))
    client = _local_client_class()()
    assert client.available and client._port == 12345
    path.unlink()
    assert client.available


@pytest.mark.parametrize("gate", ["rate", "breaker", "fresh_session"])
@pytest.mark.parametrize("allowed", [True, False])
def test_primary_hweb_cancel_survives_gates_without_memory(monkeypatch, gate, allowed):
    import asyncio
    import logging
    from synapse.core.protocol import SynapseCommand, SynapseResponse
    from synapse.core.farm_contract import FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
    from synapse.panel import bridge_adapter as adapter
    policy = Mock(return_value=allowed)
    monkeypatch.setattr(adapter, "get_bridge", lambda: SimpleNamespace(authorize_external_operation=policy))
    path = Path(__file__).parents[1] / "python/synapse/server/hwebserver_adapter.py"
    node = next(node for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "receive")
    sent = []
    async def send(text, **kwargs):
        sent.append(json.loads(text))
    handler = SimpleNamespace(handle=Mock(return_value=SynapseResponse(id="stop", success=True, data={})))
    ns = {"json": json, "_dumps": json.dumps, "logger": logging.getLogger("farm-test"),
          "SynapseCommand": SynapseCommand, "SynapseResponse": SynapseResponse,
          "_READ_ONLY_COMMANDS": FARM_READ_COMMANDS, "FARM_CONTROL_COMMANDS": FARM_CONTROL_COMMANDS,
          "FARM_READ_COMMANDS": FARM_READ_COMMANDS, "_get_handler": lambda: handler,
          "get_bridge": Mock(side_effect=AssertionError("Constructed artist memory")),
          "_client_sessions": {},
          "_rate_limiter": SimpleNamespace(acquire=lambda _: (False, {"reason": "full"})) if gate == "rate" else None,
          "_circuit_breaker": SimpleNamespace(can_execute=lambda: (False, {}), record_success=lambda: None) if gate == "breaker" else None}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    connection = SimpleNamespace(_authenticated=True, _client_id="local", _session_id=None, send=send)
    asyncio.run(ns["receive"](connection, json.dumps({"type": "farm_cancel", "id": "stop", "payload": {"request_id": "job"}})))
    assert sent[0]["success"] is allowed
    assert handler.handle.call_count == int(allowed)
    policy.assert_called_once()
    ns["get_bridge"].assert_not_called()


@pytest.mark.parametrize("command_type", ["farm_prepare", "farm_submit"])
@pytest.mark.parametrize("allowed", [True, False])
def test_primary_hweb_launch_obeys_external_policy(monkeypatch, command_type, allowed):
    import asyncio
    import logging
    from synapse.core.protocol import SynapseCommand, SynapseResponse
    from synapse.core.farm_contract import FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
    from synapse.panel import bridge_adapter as adapter
    policy = Mock(return_value=allowed)
    monkeypatch.setattr(adapter, "get_bridge", lambda: SimpleNamespace(authorize_external_operation=policy))
    path = Path(__file__).parents[1] / "python/synapse/server/hwebserver_adapter.py"
    node = next(node for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(node, ast.AsyncFunctionDef) and node.name == "receive")
    sent = []
    async def send(text, **kwargs):
        sent.append(json.loads(text))
    handler = SimpleNamespace(handle=Mock(return_value=SynapseResponse(id="request", success=True, data={})))
    ns = {"json": json, "_dumps": json.dumps, "logger": logging.getLogger("farm-test"),
          "SynapseCommand": SynapseCommand, "SynapseResponse": SynapseResponse,
          "_READ_ONLY_COMMANDS": FARM_READ_COMMANDS, "FARM_CONTROL_COMMANDS": FARM_CONTROL_COMMANDS,
          "FARM_READ_COMMANDS": FARM_READ_COMMANDS, "_get_handler": lambda: handler,
          "get_bridge": Mock(side_effect=AssertionError("Constructed artist memory")),
          "_client_sessions": {}, "_rate_limiter": None, "_circuit_breaker": None}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    connection = SimpleNamespace(_authenticated=True, _client_id="local", _session_id=None, send=send)
    asyncio.run(ns["receive"](connection, json.dumps({"type": command_type, "id": "request", "payload": {}})))
    assert sent[0]["success"] is allowed
    assert handler.handle.call_count == int(allowed)
    policy.assert_called_once()
    ns["get_bridge"].assert_not_called()


@pytest.mark.parametrize("command_type", ["farm_prepare", "farm_submit", "farm_cancel"])
@pytest.mark.parametrize("allowed", [True, False])
def test_standalone_ws_controls_obey_policy_without_main_thread_probe(monkeypatch, command_type, allowed):
    from synapse.server import websocket as transport, main_thread
    from synapse.panel import bridge_adapter as adapter
    from synapse.core.protocol import SynapseResponse
    policy = Mock(return_value=allowed)
    monkeypatch.setattr(adapter, "get_bridge", lambda: SimpleNamespace(authorize_external_operation=policy))
    monkeypatch.setattr(main_thread, "is_main_thread_stalled", lambda: True)
    monkeypatch.setattr(main_thread, "probe_main_thread", Mock(side_effect=AssertionError("Probed artist GUI")))
    handler = SimpleNamespace(handle=Mock(return_value=SynapseResponse(id="request", success=True, data={})))
    server = object.__new__(transport.SynapseServer)
    server._handler, server._session_manager = handler, None
    server._enable_resilience = False
    server._circuit_breaker = None
    server._avg_latency, server._latency_alpha = 0.0, 0.2
    sent = []
    server._handle_message(SimpleNamespace(send=lambda value: sent.append(json.loads(value))),
        json.dumps({"type": command_type, "id": "request", "payload": {}}), "local")
    assert sent[0]["success"] is allowed, sent
    assert handler.handle.call_count == int(allowed)
    policy.assert_called_once()


def test_standalone_farm_connection_never_initializes_scene_memory(monkeypatch):
    from synapse.server import websocket as transport
    from synapse.panel import bridge_adapter as adapter
    from synapse.core.protocol import SynapseResponse
    monkeypatch.setattr(adapter, "get_bridge", lambda: SimpleNamespace(authorize_external_operation=lambda op: True))
    monkeypatch.setattr(transport, "get_auth_key", lambda: None)
    monkeypatch.setattr(transport, "validate_origin", lambda *a, **k: True)
    memory = Mock(side_effect=AssertionError("Initialized scene memory on render-only connection"))
    monkeypatch.setattr(transport, "get_bridge", memory)
    messages = [json.dumps({"type": command, "id": command, "payload": {}})
                for command in ("farm_jobs", "farm_cancel")]
    monkeypatch.setattr(transport, "iter_messages", lambda *args: iter(messages))
    handler = SimpleNamespace(handle=Mock(side_effect=lambda command: SynapseResponse(id=command.id, success=True, data={})),
                              set_session_id=Mock())
    server = object.__new__(transport.SynapseServer)
    server._handler = handler
    server._clients_lock, server._client_counter = threading.Lock(), 0
    server._clients, server._client_ids, server._client_cancels, server._client_sessions = set(), {}, {}, {}
    server._on_client_connect = server._on_client_disconnect = None
    server._deploy_config = server._session_manager = server._user_directory = None
    server._rate_limiter = server._circuit_breaker = None
    server._enable_resilience = False
    server._avg_latency, server._latency_alpha = 0.0, 0.2
    socket = Mock()
    socket.request.headers = {}
    server._handle_client(socket)
    assert handler.handle.call_count == 2
    assert socket.send.call_count == 2
    memory.assert_not_called()
    handler.set_session_id.assert_not_called()
    assert not server._clients and not server._client_sessions


def test_unsaved_active_scene_is_refused_before_package_admission(monkeypatch, tmp_path):
    from synapse.server import handlers_farm as farm
    source = str(tmp_path / "artist.hip")
    monkeypatch.setattr(farm, "_inspect_saved_source", lambda: {"source_hip": source, "unsaved": True})
    service = Mock()
    monkeypatch.setattr(farm, "_service", lambda: service)
    with pytest.raises(ValueError, match="Save the scene"):
        farm.FarmHandlerMixin()._handle_farm_prepare({"source_hip": source})
    service.prepare.assert_not_called()


@pytest.mark.parametrize("busy", [False, True])
def test_render_command_opens_without_a_model_or_draft_change(busy):
    panel_file = Path(__file__).parents[1] / "python/synapse/panel/synapse_panel.py"
    tree = ast.parse(panel_file.read_text(encoding="utf-8"))
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
             and node.name in ("_send", "_on_tool_picked")]
    ns = {"_ACTIVE_PANEL_WORKERS": {object()} if busy else set(), "ClaudeWorker": None}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(panel_file), "exec"), ns)
    panel = SimpleNamespace(_open_render_workspace=Mock(), _prepare_connection=Mock(),
                            _input=Mock(), _worker=None, _chat=Mock())
    panel._send = MethodType(ns["_send"], panel)
    ns["_on_tool_picked"](panel, "/render")
    panel._open_render_workspace.assert_called_once_with()
    panel._prepare_connection.assert_not_called()
    panel._input.clear.assert_not_called()
    panel._input.setPlainText.assert_not_called()
