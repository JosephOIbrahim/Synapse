"""Wave 0 BRAINSTEM repairs — execute hardening (BRAINSTEM-3, -4, -5).

Predicates from REPAIR_SCAFFOLD_2026-11-20 (audit commit 4aab502a):

* BRAINSTEM-3 — dispatching ``{"content": "raise SystemExit(1)"}`` through
  ``_handle_execute_python`` over BOTH transports returns ``success=False``
  with outcome ``tool.internal``, and the next command still runs.
* BRAINSTEM-4 — ``execute_python("while True: pass")`` stops at the deadline
  (driven here with a short budget), and a synthetic loop drives the
  settrace deadline directly; ``execute_vex`` refuses to START a cook whose
  budget is spent and reports an overrun honestly.
* BRAINSTEM-5 — a WS-dispatched mutating command whose ``run_on_main`` times
  out comes back to the stdio client as ``transport.timeout``, and the
  model-facing first line tells it to check the scene, not retry.

No Houdini, no hython: the canonical fake ``hou`` from conftest is swapped for
a small local double whose undo group PROPAGATES exceptions — a MagicMock's
``__exit__`` returns a truthy mock and would silently swallow the very escapes
under test.
"""

import ast
import asyncio
import importlib
import json
import logging
import sys
import threading
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import pkgbootstrap
from synapse.core.protocol import SynapseCommand, SynapseResponse


def _handlers():
    return importlib.import_module("synapse.server.handlers")


def _main_thread():
    return importlib.import_module("synapse.server.main_thread")


# ---------------------------------------------------------------------------
# Local Houdini doubles (exception-propagating undo group)
# ---------------------------------------------------------------------------

class _UndoGroup:
    def __init__(self, name=""):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False  # never suppress — the escape under test must propagate


class _Undos:
    def __init__(self):
        self.labels = ["base"]
        self.undone = 0

    def group(self, name=""):
        return _UndoGroup(name)

    def undoLabels(self):
        return list(self.labels)

    def performUndo(self):
        self.undone += 1


class _FakeParm:
    def __init__(self):
        self.set_values = []

    def set(self, value):
        self.set_values.append(value)


class _FakeGeo:
    def __init__(self, wrangle):
        self._wrangle = wrangle

    def createNode(self, node_type, name):
        return self._wrangle

    def name(self):
        return "synapse_vex_temp"

    def destroy(self):
        pass


class _FakeWrangle:
    def __init__(self, cook_s=0.0):
        self._cook_s = cook_s
        self.cook_calls = []
        self._parms = {}

    def parm(self, name):
        return self._parms.setdefault(name, _FakeParm())

    def setInput(self, index, node):
        self.input = (index, node)

    def setDisplayFlag(self, flag):
        self.display = flag

    def setRenderFlag(self, flag):
        self.render = flag

    def cook(self, force=False):
        self.cook_calls.append(force)
        if self._cook_s:
            time.sleep(self._cook_s)

    def errors(self):
        return []

    def path(self):
        return "/obj/synapse_vex_temp/synapse_vex"

    def parent(self):
        return _FakeGeo(self)


class _FakeObj:
    def __init__(self, geo):
        self._geo = geo

    def createNode(self, node_type, name):
        return self._geo


def _install_hou(monkeypatch, fake):
    mod = _handlers()
    monkeypatch.setattr(mod, "hou", fake, raising=False)
    monkeypatch.setattr(mod, "HOU_AVAILABLE", True)


@pytest.fixture
def handler(monkeypatch):
    """A real SynapseHandler against the local fake, with logging side-effects off."""
    _install_hou(monkeypatch, SimpleNamespace(undos=_Undos()))
    monkeypatch.delenv("SYNAPSE_COOK_SANDWICH", raising=False)
    monkeypatch.delenv("SYNAPSE_EXEC_DEADLINE", raising=False)
    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
    mod = _handlers()
    monkeypatch.setattr(mod.SynapseHandler, "_submit_logs", lambda self, *a, **k: None)
    h = mod.SynapseHandler()
    # The Mile-6 VEX memory capture must never open the real bridge here.
    monkeypatch.setattr(h, "_get_bridge", lambda: None)
    return h


# ---------------------------------------------------------------------------
# Transport harnesses
# ---------------------------------------------------------------------------

def _standalone_server(handler):
    from synapse.server import websocket as transport
    server = object.__new__(transport.SynapseServer)
    server._handler, server._session_manager = handler, None
    server._enable_resilience = False
    server._circuit_breaker = None
    server._avg_latency, server._latency_alpha = 0.0, 0.2
    return server


def _send(server, websocket, sent, command_type, request_id, payload=None):
    server._handle_message(
        websocket,
        json.dumps({"type": command_type, "id": request_id, "payload": payload or {}}),
        "local",
    )
    return sent[-1]


def _hwebserver_receive(handler):
    """The receive() coroutine, AST-extracted (hwebserver does not exist here)."""
    from synapse.core.farm_contract import FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
    path = Path(__file__).parents[1] / "python/synapse/server/hwebserver_adapter.py"
    node = next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "receive")
    ns = {
        "__name__": "synapse.server.hwebserver_adapter",
        "__package__": "synapse.server",
        "json": json,
        "_dumps": json.dumps,
        "logger": logging.getLogger("wave0-test"),
        "SynapseCommand": SynapseCommand,
        "SynapseResponse": SynapseResponse,
        "_READ_ONLY_COMMANDS": FARM_READ_COMMANDS | {"ping", "get_scene_info"},
        "_read_only_refusal_for_command": lambda _command_type: None,
        "FARM_CONTROL_COMMANDS": FARM_CONTROL_COMMANDS,
        "FARM_READ_COMMANDS": FARM_READ_COMMANDS,
        "_get_handler": lambda: handler,
        "get_bridge": MagicMock(),
        "_client_sessions": {},
        "_rate_limiter": None,
        "_circuit_breaker": None,
        "_preflight_refusal_for": lambda *args: None,
        "_preflight_note_for": lambda *args: None,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return ns["receive"]


def _connection(sent):
    async def send(text, **kwargs):
        sent.append(json.loads(text))

    return SimpleNamespace(_authenticated=True, _client_id="local",
                           _session_id="sess", send=send)


# ---------------------------------------------------------------------------
# BRAINSTEM-3 — SystemExit inside the exec frame is that call's failure
# ---------------------------------------------------------------------------

def test_exec_python_system_exit_is_a_typed_failure_direct(handler):
    from synapse.core.errors import ExecutionAborted

    with pytest.raises(ExecutionAborted) as caught:
        handler._handle_execute_python({"content": "raise SystemExit(1)"})
    assert caught.value.outcome_code == "tool.internal"
    assert "SystemExit" in str(caught.value)


def test_websocket_answers_system_exit_then_serves_the_next_command(handler):
    server = _standalone_server(handler)
    sent = []
    websocket = SimpleNamespace(send=lambda value: sent.append(json.loads(value)))

    failed = _send(server, websocket, sent, "execute_python", "req-1",
                   {"content": "raise SystemExit(1)"})
    assert failed["id"] == "req-1"
    assert failed["success"] is False
    assert failed["data"]["outcome"]["code"] == "tool.internal"
    assert failed["data"]["outcome"]["outcome"] == "unknown_outcome"

    served = _send(server, websocket, sent, "ping", "req-2")
    assert served["id"] == "req-2"
    assert served["success"] is True


def test_hwebserver_answers_system_exit_then_serves_the_next_command(handler):
    receive = _hwebserver_receive(handler)
    sent = []
    connection = _connection(sent)

    asyncio.run(receive(connection, json.dumps(
        {"type": "execute_python", "id": "req-9",
         "payload": {"content": "raise SystemExit(1)"}})))
    assert sent[-1]["id"] == "req-9"
    assert sent[-1]["success"] is False
    assert sent[-1]["data"]["outcome"]["code"] == "tool.internal"

    asyncio.run(receive(connection, json.dumps({"type": "ping", "id": "req-10", "payload": {}})))
    assert sent[-1]["id"] == "req-10"
    assert sent[-1]["success"] is True


# ---------------------------------------------------------------------------
# BRAINSTEM-4 — the main-thread deadline
# ---------------------------------------------------------------------------

def _spin():
    while True:
        pass


def test_settrace_deadline_interrupts_a_synthetic_loop():
    from synapse.server.deadline import DeadlineExceeded, run_under_deadline

    started = time.monotonic()
    with pytest.raises(DeadlineExceeded):
        run_under_deadline(_spin, 0.05, label="synthetic-loop")
    assert time.monotonic() - started < 10.0


def test_the_deadline_restores_the_previous_trace_function():
    from synapse.server.deadline import run_under_deadline

    previous = sys.gettrace()
    assert run_under_deadline(lambda: 7, 1.0) == 7
    assert sys.gettrace() is previous


def test_the_deadline_can_be_disarmed(monkeypatch):
    from synapse.server import deadline as deadline_mod

    monkeypatch.setenv("SYNAPSE_EXEC_DEADLINE", "0")
    assert deadline_mod.deadlines_enabled() is False
    assert deadline_mod.run_under_deadline(lambda: 11, 0.0) == 11


def test_execute_python_infinite_loop_stops_at_the_deadline(handler, monkeypatch):
    from synapse.core.errors import ExecutionDeadlineExceeded

    monkeypatch.setattr(_main_thread(), "_SLOW_TIMEOUT", 0.05)
    started = time.monotonic()
    with pytest.raises(ExecutionDeadlineExceeded) as caught:
        handler._handle_execute_python({"content": "while True: pass"})
    assert time.monotonic() - started < 10.0
    assert "deadline" in str(caught.value).lower()
    assert "partial" in str(caught.value).lower()


def test_execute_python_deadline_is_an_explicit_outcome_on_the_wire(handler, monkeypatch):
    monkeypatch.setattr(_main_thread(), "_SLOW_TIMEOUT", 0.05)

    response = handler.handle(SynapseCommand(
        type="execute_python", id="dl-1",
        payload={"content": "while True: pass"},
    ))

    assert response.success is False
    wire = json.loads(response.to_json())
    outcome = wire["data"]["outcome"]
    assert outcome["code"] == "execution.deadline_exceeded"
    assert outcome["outcome"] == "unknown_outcome"
    assert outcome["dispatched"] == "maybe"
    assert "check the scene" in outcome["next"].lower()
    assert "partial" in (outcome["message"] + outcome["next"]).lower()


def test_execute_vex_will_not_start_a_cook_whose_budget_is_spent(handler, monkeypatch):
    from synapse.core.errors import ExecutionDeadlineExceeded

    wrangle = _FakeWrangle()
    _install_hou(monkeypatch, SimpleNamespace(
        undos=_Undos(), node=lambda path: _FakeObj(_FakeGeo(wrangle))))
    monkeypatch.setattr(_main_thread(), "_SLOW_TIMEOUT", 0.0)

    with pytest.raises(ExecutionDeadlineExceeded):
        handler._handle_execute_vex({"snippet": "int x = 1;"})
    assert wrangle.cook_calls == [], "no cook may start on a spent budget"


def test_execute_vex_reports_a_cook_overrun_after_it_returns(handler, monkeypatch):
    wrangle = _FakeWrangle(cook_s=0.1)
    _install_hou(monkeypatch, SimpleNamespace(
        undos=_Undos(), node=lambda path: _FakeObj(_FakeGeo(wrangle))))
    monkeypatch.setattr(_main_thread(), "_SLOW_TIMEOUT", 0.05)

    result = handler._handle_execute_vex({"snippet": "int x = 1;"})

    assert wrangle.cook_calls == [True], "the started cook was allowed to finish"
    assert result["deadline_exceeded"]["cook_s"] >= 0.09
    assert "cannot be interrupted" in result["deadline_exceeded"]["detail"]
    assert result["node"] == "/obj/synapse_vex_temp/synapse_vex"


# ---------------------------------------------------------------------------
# BRAINSTEM-5 — a main-thread timeout is an unknown outcome, not a failure
# ---------------------------------------------------------------------------

_FOUND = object()

_TIMEOUT_TEXT = (
    "Houdini's main thread didn't respond in time -- it may be busy cooking "
    "or rendering. The call may still be running; check the scene before "
    "trying again."
)


class _TimeoutRegistry:
    """get() finds every command; invoke() raises the timeout."""

    def __init__(self, exc):
        self._exc = exc

    def get(self, command_type):
        return _FOUND

    def invoke(self, command_type, payload, ctx=None):
        raise self._exc


class _TimeoutHandler:
    """A handler whose handle() raises a main-thread timeout (adapter-arm test)."""

    def __init__(self, exc):
        self._exc = exc

    def handle(self, command):
        raise self._exc


def _timeout():
    return _main_thread().MainThreadTimeout(_TIMEOUT_TEXT)


def test_handle_a_mutating_timeout_is_transport_timeout(monkeypatch):
    h = _handlers().SynapseHandler()
    h._registry = _TimeoutRegistry(_timeout())
    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")

    wire = json.loads(h.handle(SynapseCommand(
        type="execute_python", id="t-1", payload={"content": "x = 1"})).to_json())

    outcome = wire["data"]["outcome"]
    assert wire["success"] is False
    assert (outcome["code"], outcome["outcome"], outcome["dispatched"]) == (
        "transport.timeout", "unknown_outcome", "maybe")
    assert "check the scene" in outcome["next"].lower()
    assert "try again in a moment" not in (wire["error"] or "").lower()


def test_handle_a_read_timeout_stays_retryable():
    h = _handlers().SynapseHandler()
    h._registry = _TimeoutRegistry(_timeout())

    wire = json.loads(h.handle(SynapseCommand(
        type="get_scene_info", id="t-2", payload={})).to_json())

    outcome = wire["data"]["outcome"]
    assert (outcome["code"], outcome["outcome"]) == ("transport.read_retry", "retryable")


def test_standalone_ws_adapter_answers_a_timeout_as_unknown(monkeypatch):
    server = _standalone_server(_TimeoutHandler(_timeout()))
    sent = []
    websocket = SimpleNamespace(send=lambda value: sent.append(json.loads(value)))

    _send(server, websocket, sent, "execute_python", "req-t", {"content": "x = 1"})

    outcome = sent[-1]["data"]["outcome"]
    assert sent[-1]["id"] == "req-t"
    assert (outcome["code"], outcome["outcome"]) == ("transport.timeout", "unknown_outcome")
    assert "check the scene" in outcome["next"].lower()


def test_hwebserver_adapter_answers_a_timeout_as_unknown():
    receive = _hwebserver_receive(_TimeoutHandler(_timeout()))
    sent = []

    asyncio.run(receive(_connection(sent), json.dumps(
        {"type": "execute_python", "id": "req-h", "payload": {"content": "x = 1"}})))

    outcome = sent[-1]["data"]["outcome"]
    assert sent[-1]["id"] == "req-h"
    assert (outcome["code"], outcome["outcome"]) == ("transport.timeout", "unknown_outcome")


def test_the_run_on_main_timeout_message_does_not_invite_a_blind_retry(monkeypatch):
    mt = _main_thread()
    held = []
    fake = types.ModuleType("hdefereval")
    fake.executeDeferred = held.append  # accept the wake, never run it
    monkeypatch.setitem(sys.modules, "hdefereval", fake)

    box = {}

    def _call():
        try:
            mt.run_on_main(lambda: 42, timeout=0.05)
        except mt.MainThreadTimeout as exc:
            box["err"] = exc

    thread = threading.Thread(target=_call)
    thread.start()
    thread.join(timeout=5.0)
    try:
        message = str(box["err"])
        assert "main thread didn't respond" in message
        assert "may still be running" in message
        assert "check the scene" in message
        assert "Try again in a moment" not in message
    finally:
        # Drain the accepted wakes so the module-wide deferred dispatcher is
        # not left stranded for later tests (same cleanup as test_main_thread).
        for callback in held:
            callback()


# ---------------------------------------------------------------------------
# BRAINSTEM-5 — the stdio client gets the typed outcome, not the prose
# ---------------------------------------------------------------------------

def _stdio():
    pytest.importorskip("mcp")
    pytest.importorskip("websockets")
    return importlib.import_module("mcp_server")


def test_ws_timeout_reaches_the_stdio_client_as_transport_timeout(monkeypatch):
    # The WS reply the handler produces for a timed-out mutating command.
    h = _handlers().SynapseHandler()
    h._registry = _TimeoutRegistry(_timeout())
    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
    failure = json.loads(h.handle(SynapseCommand(
        type="execute_python", id="t-9", payload={"content": "x = 1"})).to_json())
    assert failure["data"]["outcome"]["code"] == "transport.timeout"

    ms = _stdio()

    class _Socket:
        async def send(self, text):
            command = json.loads(text)
            ms._pending[command["id"]].set_result(failure)

        async def close(self):
            pass

    async def connection():
        return _Socket()

    monkeypatch.setattr(ms, "_get_connection", connection)

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(ms.send_command("execute_python", {}))

    assert caught.value.outcome["code"] == "transport.timeout"
    first_line = str(caught.value).splitlines()[0]
    assert first_line.startswith("unknown_outcome: "), first_line
    assert "check the scene" in first_line.lower(), first_line
    assert "try again in a moment" not in first_line.lower(), first_line


def test_the_panel_client_keeps_the_server_attached_outcome(monkeypatch):
    """The F2 breaker reads a typed outcome, not the prose (tool_executor)."""
    from typing import Optional

    path = Path(__file__).parents[1] / "python/synapse/panel/tool_executor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    wanted = {"MCPUnavailable", "MCPOutcomeUnknown", "_MCPLocalClient"}
    nodes = [n for n in tree.body
             if isinstance(n, ast.ClassDef) and n.name in wanted]
    ns = {"Optional": Optional, "threading": threading, "json": json,
          "http": __import__("http.client", fromlist=["client"]),
          "time": time, "sys": sys}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    client = ns["_MCPLocalClient"]()
    monkeypatch.setattr(client, "_ensure_session", lambda: "s1")
    payload = {
        "content": [{"type": "text", "text": "unknown_outcome: x Next: y"}],
        "isError": True,
        "_meta": {"synapse/outcome": {
            "outcome": "unknown_outcome", "code": "transport.timeout",
            "message": "x", "next": "y", "dispatched": "maybe"}},
    }
    monkeypatch.setattr(client, "_post",
                        lambda body, headers=None, timeout=35.0: {
                            "jsonrpc": "2.0", "id": 1, "result": payload})

    with pytest.raises(RuntimeError) as caught:
        client.call_tool("houdini_execute_python", {})
    assert caught.value.outcome["code"] == "transport.timeout"


# ---------------------------------------------------------------------------
# BRAINSTEM-5 — the F2 retry breaker counts unknown outcomes for mutations
# ---------------------------------------------------------------------------

@pytest.fixture
def claude_worker_module():
    """Import claude_worker headlessly (same PySide-stub convention as test_retry_breaker)."""
    touched = [
        "PySide6", "PySide6.QtCore",
        "PySide2", "PySide2.QtCore",
        "synapse.panel.claude_worker",
        "synapse.panel.tool_executor",
        "synapse.server.main_thread",
    ]
    saved = pkgbootstrap.snapshot_modules(touched)

    def _is_genuine_qt(modname):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            return False
        return isinstance(getattr(mod, "QThread", None), type)

    real_qt = _is_genuine_qt("PySide6.QtCore") or _is_genuine_qt("PySide2.QtCore")

    if not real_qt:
        class _StubBase:
            def __init__(self, *a, **kw):
                pass

        class _QtCoreStub(types.ModuleType):
            QThread = _StubBase
            QObject = _StubBase

            @staticmethod
            def Signal(*a, **kw):
                return MagicMock()

            @staticmethod
            def Slot(*a, **kw):
                return lambda fn: fn

            def __getattr__(self, name):  # pragma: no cover - defensive
                return MagicMock()

        qtcore = _QtCoreStub("PySide6.QtCore")
        pyside = types.ModuleType("PySide6")
        pyside.QtCore = qtcore
        sys.modules["PySide6"] = pyside
        sys.modules["PySide6.QtCore"] = qtcore
        sys.modules.pop("synapse.panel.tool_executor", None)
    sys.modules.pop("synapse.panel.claude_worker", None)
    import synapse.panel.claude_worker as cw

    try:
        yield cw
    finally:
        pkgbootstrap.restore_modules(saved)


def _worker(cw_module):
    worker = cw_module.ClaudeWorker(messages=[], enforce_worker_policy=False)
    worker.tool_status = MagicMock()
    return worker


def _unknown_outcome_error(name, inp):
    exc = RuntimeError("unknown_outcome: Houdini may still be working on it. "
                       "Check the scene before trying again.")
    exc.outcome = {"outcome": "unknown_outcome", "code": "transport.timeout",
                   "message": "m", "next": "n", "dispatched": "maybe"}
    raise exc


def test_unknown_outcome_on_a_mutation_counts_toward_the_f2_breaker(
        claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", _unknown_outcome_error)
    worker = _worker(cw)
    block = {"id": "tu-1", "name": "execute_python", "input": {"content": "x = 1"}}

    result = worker._execute_tool_block(block)

    key = ("execute_python", json.dumps(block["input"], sort_keys=True))
    assert result["is_error"] is True
    assert worker._retry_abandons[key] == 1


def test_unknown_outcome_on_a_read_does_not_count(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", _unknown_outcome_error)
    worker = _worker(cw)
    block = {"id": "tu-2", "name": "houdini_scene_info", "input": {}}

    worker._execute_tool_block(block)

    assert worker._retry_abandons == {}


def test_mcp_server_prefers_the_handler_attached_outcome(monkeypatch):
    from synapse.core import outcomes as O
    import synapse.mcp.server as S

    attached = O.info("transport.timeout", "the call may still be running").to_dict()
    monkeypatch.setattr(S, "dispatch_tool", lambda handler, name, arguments: {
        "content": [{"type": "text", "text": "Houdini's main thread didn't respond"}],
        "isError": True,
        "structuredContent": {"outcome": attached},
    })
    monkeypatch.setattr(S, "_STALL_DETECT_AVAILABLE", False, raising=False)
    server = object.__new__(S.MCPServer)
    server._get_handler = lambda: None
    server._enable_resilience = False
    server._rate_limiter = None
    server._circuit_breaker = None
    server._latency_alpha, server._avg_latency = 0.2, 0.0
    server.broadcast_event = lambda *a, **k: None

    result = server._handle_tools_call({"name": "houdini_execute_python", "arguments": {}})

    assert result["isError"] is True
    assert result["_meta"]["synapse/outcome"]["code"] == "transport.timeout"
