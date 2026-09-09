"""Actual MCP dispatch/handler/observer sequence across real Python threads.

Scene, bridge authority and substrates are recording doubles. This exercises
the shipped serializers and caller order, not native Houdini or real stores.
"""
import ast
import contextlib
import json
import logging
import os
from pathlib import Path
import queue
import sys
import threading
import time
from types import MethodType, SimpleNamespace
from typing import Optional

import pytest

from synapse.core.protocol import SynapseCommand, SynapseResponse
from synapse.host import memory_loop as host
from synapse.loop.ports import PortResult
from synapse.mcp.protocol import JsonRpcError, JsonRpcInvalidParams, INTERNAL_ERROR
from synapse.mcp.tools import dispatch_tool


def source_method(path, class_name, method_name, globals_map):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), method], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), globals_map)
    return globals_map[method_name]


@pytest.fixture
def rig(monkeypatch):
    repo = Path(__file__).parents[1]
    callbacks, events, values = queue.Queue(), [], []
    result_data = [{"success": True, "created": "/stage/synthetic"}]

    def marshal(callback, **kwargs):
        if threading.current_thread() is threading.main_thread():
            return callback()
        done, result = threading.Event(), {}
        callbacks.put((callback, done, result))
        assert done.wait(2)
        if "error" in result:
            raise result["error"]
        return result["value"]

    import synapse.server.main_thread as mt
    monkeypatch.setattr(mt, "run_on_main", marshal)
    monkeypatch.setenv("SYNAPSE_LOOP_ENABLED", "1")
    class RecordingLoop:
        def begin(self, *args):
            assert threading.current_thread() is not threading.main_thread()
            events.append("forecast")
            return {"recording_double": True}
        def finish(self, record, value, result_digest):
            assert threading.current_thread() is not threading.main_thread()
            events.append("observed")
            values.append(value)
            return PortResult.ok({"recording_double": True})
    def snapshot(query):
        assert threading.current_thread() is threading.main_thread()
        events.append("snapshot")
        return {"storage_dir": "unused", "context": {}, "relation_keys": []}
    monkeypatch.setattr(host, "_snapshot", snapshot)
    monkeypatch.setattr(host, "coordinator", lambda root: RecordingLoop())
    class Registry:
        def get(self, command):
            return self.invoke
        def invoke(self, command, payload, **kwargs):
            assert threading.current_thread() is threading.main_thread()
            events.append("operation")
            return result_data[0]
    handler_globals = {"__package__": "synapse.server", "SynapseCommand": SynapseCommand,
        "SynapseResponse": SynapseResponse, "time": time, "threading": threading,
        "contextlib": contextlib, "_READ_ONLY_COMMANDS": set(), "_MUTATION_LOCK": threading.RLock(),
        "_envelope": SimpleNamespace(envelope_active=lambda _: False),
        "FloorContext": lambda **kwargs: kwargs, "normalize_command_type": lambda value: value,
        "SynapseUserError": type("SynapseUserError", (Exception,), {}), "logger": logging.getLogger("probe")}
    handler = SimpleNamespace(_registry=Registry(), _session_id="synthetic",
        _record_tool_duration=lambda *a, **k: None, _submit_logs=lambda *a, **k: None)
    handler.handle = MethodType(source_method(repo / "python/synapse/server/handlers.py", "SynapseHandler", "handle", handler_globals), handler)
    def bridge(tool_name, handler, command):
        assert threading.current_thread() is threading.main_thread()
        events.append("existing_bridge")
        return handler.handle(command)
    monkeypatch.setitem(sys.modules, "synapse.panel.bridge_adapter", SimpleNamespace(execute_through_bridge=bridge, is_read_only=lambda _: False))
    monkeypatch.setitem(sys.modules, "synapse.panel.session_journal", SimpleNamespace(get_journal=lambda: SimpleNamespace(log_tool=lambda *a, **k: None)))
    server_globals = {"__package__": "synapse.mcp", "time": time, "Optional": Optional,
        "is_transport_fast_path": lambda _: False, "_STALL_DETECT_AVAILABLE": False,
        "dispatch_tool": dispatch_tool, "logger": logging.getLogger("probe"),
        "JsonRpcInvalidParams": JsonRpcInvalidParams, "JsonRpcError": JsonRpcError, "INTERNAL_ERROR": INTERNAL_ERROR,
        "_note_marshal_bypass": lambda *args: None,
        "_isError_text": lambda result: result["content"][0]["text"]}
    server = SimpleNamespace(_get_handler=lambda: handler, _circuit_breaker=None,
        _enable_resilience=False, _rate_limiter=None, _latency_alpha=.2, _avg_latency=0)
    source = Path(os.environ.get("SYNAPSE_TEST_MCP_OBSERVATION_SOURCE", repo / "python/synapse/mcp/server.py"))
    server.call = MethodType(source_method(source, "MCPServer", "_handle_tools_call", server_globals), server)
    def run(tool="houdini_create_node"):
        result = {}
        def worker():
            try:
                result["value"] = server.call({"name": tool, "arguments": {"parent_path": "/stage", "node_type": "null"}})
            except BaseException as exc:
                result["error"] = exc
        thread = threading.Thread(target=worker)
        thread.start()
        deadline = time.monotonic() + 3
        while thread.is_alive() and time.monotonic() < deadline:
            try:
                callback, done, response = callbacks.get(timeout=.01)
            except queue.Empty:
                continue
            try:
                response["value"] = callback()
            except BaseException as exc:
                response["error"] = exc
            finally:
                done.set()
        thread.join(.1)
        assert not thread.is_alive()
        return result
    return SimpleNamespace(run=run, server=server, globals=server_globals,
        events=events, values=values, data=result_data)


@pytest.mark.parametrize("data, expected", [({"success": True}, True),
    ({"success": False}, False), ({"status": "pending"}, None)])
def test_preferred_mcp_records_once_and_delivers_receipt_in_actual_payload(rig, data, expected):
    rig.data[0] = data
    result = rig.run()
    assert "error" not in result, result
    decoded = json.loads(result["value"]["content"][0]["text"])
    assert rig.events == ["snapshot", "forecast", "existing_bridge", "operation", "observed"]
    assert rig.values == [expected]
    assert decoded["memory_loop"]["status"] == "SUCCESS"
    assert data == {key: value for key, value in decoded.items() if key != "memory_loop"}


def test_disabled_loop_dispatches_without_substrate(rig, monkeypatch):
    monkeypatch.setenv("SYNAPSE_LOOP_ENABLED", "0")
    assert "error" not in rig.run()
    assert rig.events == ["existing_bridge", "operation"] and not rig.values


def test_resilience_refusal_precedes_forecast_and_dispatch(rig):
    rig.server._enable_resilience = True
    rig.server._rate_limiter = SimpleNamespace(acquire=lambda _: (False, {"reason": "busy"}))
    assert isinstance(rig.run()["error"], JsonRpcError)
    assert not rig.events and not rig.values


def test_unobserved_command_keeps_existing_dispatch_without_forecast(rig):
    assert "error" not in rig.run("houdini_undo")
    assert rig.events == ["existing_bridge", "operation"] and not rig.values


def test_second_mcp_action_gets_its_own_observation(rig):
    assert "error" not in rig.run()
    assert "error" not in rig.run()
    assert rig.values == [True, True]
    assert rig.events == ["snapshot", "forecast", "existing_bridge", "operation", "observed"] * 2


def test_missing_dispatch_import_keeps_definitely_unsent_fallback(rig, monkeypatch):
    import builtins
    original_import = builtins.__import__
    def unavailable(name, globals=None, locals=None, fromlist=(), level=0):
        if name.endswith("server.main_thread") and "run_on_main" in fromlist:
            raise ImportError("dispatcher is unavailable before entry")
        return original_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", unavailable)
    def fallback(*args):
        rig.events.append("fallback")
        return {"content": [{"type": "text", "text": "{}"}]}
    rig.globals["dispatch_tool"] = fallback
    result = rig.run()
    assert "error" not in result, result
    assert rig.events == ["fallback"] and not rig.values


def test_import_failure_after_operation_entry_never_replays(rig):
    def broken_dispatch(*args):
        rig.events.append("entered")
        raise ImportError("simulated import during an operation")
    rig.globals["dispatch_tool"] = broken_dispatch
    assert isinstance(rig.run()["error"], ImportError)
    assert rig.events.count("entered") == 1


@pytest.mark.parametrize("result", [{"content": []}, {"content": [{"type": "image", "data": "x"}]},
    {"content": [{"type": "text", "text": "not JSON"}]},
    {"content": [{"type": "text", "text": "{}"}], "isError": "false"},
    {"content": [{"type": "text", "text": '{"success":false}'}], "isError": True}])
def test_untyped_mcp_results_are_unknown(result):
    assert host._mcp_payload(result) is None or not isinstance(host._mcp_payload(result), dict)
