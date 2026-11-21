"""R-016 (BRAINSTEM-8) — behavioural coverage for execute_python's rollback and
the WS transports' main-thread-timeout outcomes.

The 2026-11-20 audit found these surfaces pinned by SOURCE TEXT or not pinned
at all:

* ``tests/test_handler_edge.py`` asserted the strings ``"destroy()"`` and
  ``"not input_node"`` appear in ``inspect.getsource(_handle_execute_vex)`` —
  a pin a comment satisfies. Those are now behavioural (same file).
* execute_python's rollback (``handlers.py:1684``) had no test that a NameError
  reaches ``performUndo`` exactly once, that the undo happens only AFTER the
  group closes, or that an operational error keeps the partial work the
  docstring promises.
* a main-thread timeout was only exercised with a fake handler that RAISES;
  nothing drove a real handler's timeout RESPONSE through the WS dispatcher,
  or proved that response trips the live transport's breaker.

These tests call the public handler entry points against a local fake hou. The
fake models the two rules the real undo system enforces and that the shipped
code is written around: ``performUndo()`` inside an open group raises
``Cannot undo within an undo group``, and a group that changed nothing leaves
the artist's stack untouched.

No Houdini, no hython, no network.
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from synapse.core.protocol import SynapseCommand, SynapseResponse
from synapse.server.resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fake hou for the execute_python rollback: an undo stack that enforces the
# real rule the implementation is written around.
# ---------------------------------------------------------------------------

class _UndoGroup:
    def __init__(self, undos, name):
        self._undos = undos
        self._name = name

    def __enter__(self):
        self._undos.open_groups += 1
        return self

    def __exit__(self, *exc_info):
        self._undos.open_groups -= 1
        if self._undos.records_an_entry:
            self._undos.labels.insert(0, self._name)
        return False  # never suppress — the exception under test must propagate


class _Undos:
    """The two documented rules: no undo inside a group; empty groups are no-ops."""

    def __init__(self, records_an_entry=True):
        self.labels = ["artist edit"]
        self.records_an_entry = records_an_entry
        self.open_groups = 0
        self.perform_undo_calls = 0

    def group(self, name=""):
        return _UndoGroup(self, name)

    def undoLabels(self):
        return list(self.labels)

    def performUndo(self):
        if self.open_groups:
            raise RuntimeError("Cannot undo within an undo group")
        self.perform_undo_calls += 1
        if self.labels:
            self.labels.pop(0)


def _handler_with_undos(monkeypatch, undos):
    """The shipped handler, with its hou global swapped for the undo fake."""
    from synapse.server import handlers as handlers_module

    monkeypatch.setattr(handlers_module, "hou", SimpleNamespace(undos=undos),
                        raising=False)
    monkeypatch.setattr(handlers_module, "HOU_AVAILABLE", True)
    monkeypatch.delenv("SYNAPSE_COOK_SANDWICH", raising=False)
    monkeypatch.delenv("SYNAPSE_EXEC_DEADLINE", raising=False)
    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
    monkeypatch.setattr(handlers_module.SynapseHandler, "_submit_logs",
                        lambda self, *a, **k: None)
    return handlers_module.SynapseHandler()


# ---------------------------------------------------------------------------
# Rollback integration — coding error vs operational error
# ---------------------------------------------------------------------------

def test_a_name_error_rolls_back_exactly_once(monkeypatch):
    """NameError -> performUndo exactly once, after the undo group has closed.

    If the rollback were moved inside the group, the fake raises the same
    "Cannot undo within an undo group" Houdini raises, and this test goes red
    on the wrong exception. If the rollback call were deleted, the count is 0
    and it goes red on the count.
    """
    undos = _Undos(records_an_entry=True)
    handler = _handler_with_undos(monkeypatch, undos)

    with pytest.raises(NameError) as caught:
        handler._handle_execute_python({"content": "raise NameError('typo')"})

    assert "typo" in str(caught.value), "the coding error propagates unchanged"
    assert undos.perform_undo_calls == 1
    assert undos.labels == ["artist edit"], "the rollback consumed its own entry only"


def test_an_empty_group_never_takes_the_artists_last_action(monkeypatch):
    """No entry recorded -> no performUndo: the artist's own edit is untouched."""
    undos = _Undos(records_an_entry=False)
    handler = _handler_with_undos(monkeypatch, undos)

    with pytest.raises(NameError):
        handler._handle_execute_python({"content": "raise NameError('typo')"})

    assert undos.perform_undo_calls == 0
    assert undos.labels == ["artist edit"]


def test_an_operational_error_keeps_the_partial_work(monkeypatch):
    """RuntimeError is not a coding error: no rollback, work stays undoable.

    This is the retention the docstring promises ("operational errors keep
    partial work for the artist to undo") — pinned here as behaviour, beside
    the docstring conformance pin in tests/test_graph_run_seed_11.py.
    """
    undos = _Undos(records_an_entry=True)
    handler = _handler_with_undos(monkeypatch, undos)

    with pytest.raises(RuntimeError) as caught:
        handler._handle_execute_python({"content": "raise RuntimeError('render failed')"})

    assert "render failed" in str(caught.value)
    assert undos.perform_undo_calls == 0, "operational errors never roll back"
    assert undos.labels[0] == "synapse_execute", (
        "the partial work stays on the undo stack for the artist")


# ---------------------------------------------------------------------------
# A real handler whose dispatch times out on the main thread
# ---------------------------------------------------------------------------

_FOUND = object()

_TIMEOUT_TEXT = (
    "Houdini's main thread didn't respond in time -- it may be busy cooking "
    "or rendering. The call may still be running; check the scene before "
    "trying again."
)


class _TimeoutRegistry:
    """get() finds every command; invoke() raises the live MainThreadTimeout."""

    def get(self, command_type):
        return _FOUND

    def invoke(self, command_type, payload, ctx=None):
        from synapse.server.main_thread import MainThreadTimeout
        raise MainThreadTimeout(_TIMEOUT_TEXT)


def _timeout_handler(monkeypatch):
    """The shipped handler; only its registry is swapped for the timeout raiser."""
    from synapse.server import handlers as handlers_module

    monkeypatch.delenv("SYNAPSE_COOK_SANDWICH", raising=False)
    monkeypatch.setenv("SYNAPSE_LIVE_ENVELOPE", "0")
    monkeypatch.setattr(handlers_module.SynapseHandler, "_submit_logs",
                        lambda self, *a, **k: None)
    h = handlers_module.SynapseHandler()
    h._registry = _TimeoutRegistry()
    return h


def _count_dispatches(handler):
    calls = []
    real = handler.handle

    def counted(command):
        calls.append(command.type)
        return real(command)

    handler.handle = counted
    return calls


# ---------------------------------------------------------------------------
# WS dispatch (the standalone websockets transport): the wire outcome
# ---------------------------------------------------------------------------

def _standalone_server(handler):
    from synapse.server import websocket as transport

    server = object.__new__(transport.SynapseServer)
    server._handler = handler
    server._session_manager = None
    server._enable_resilience = False
    server._circuit_breaker = None
    server._avg_latency = 0.0
    server._latency_alpha = 0.2
    return server


def _ws_send(server, command_type, request_id, payload=None):
    sent = []
    websocket = SimpleNamespace(send=lambda value: sent.append(json.loads(value)))
    server._handle_message(
        websocket,
        json.dumps({"type": command_type, "id": request_id, "payload": payload or {}}),
        "local",
    )
    assert sent, "the dispatcher must answer every request"
    return sent[-1]


def test_a_mutating_timeout_on_the_ws_dispatch_is_an_unknown_outcome(monkeypatch):
    handler = _timeout_handler(monkeypatch)
    server = _standalone_server(handler)

    wire = _ws_send(server, "execute_python", "r016-ws-1", {"content": "x = 1"})

    outcome = wire["data"]["outcome"]
    assert wire["id"] == "r016-ws-1"
    assert wire["success"] is False
    assert (outcome["code"], outcome["outcome"], outcome["dispatched"]) == (
        "transport.timeout", "unknown_outcome", "maybe")
    assert "check the scene" in outcome["next"].lower()


def test_a_read_timeout_on_the_ws_dispatch_stays_retryable(monkeypatch):
    handler = _timeout_handler(monkeypatch)
    server = _standalone_server(handler)

    wire = _ws_send(server, "get_scene_info", "r016-ws-2")

    outcome = wire["data"]["outcome"]
    assert (outcome["code"], outcome["outcome"]) == (
        "transport.read_retry", "retryable")


# ---------------------------------------------------------------------------
# WS dispatch (the live hwebserver transport): timeout outcome + breaker
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
        "logger": logging.getLogger("r016-test"),
        "SynapseCommand": SynapseCommand,
        "SynapseResponse": SynapseResponse,
        "PROTOCOL_VERSION": "1.0.0",
        "_READ_ONLY_COMMANDS": _READ_ONLY_COMMANDS,
        "_read_only_refusal_for_command": lambda _command_type: None,
        "FARM_CONTROL_COMMANDS": FARM_CONTROL_COMMANDS,
        "FARM_READ_COMMANDS": FARM_READ_COMMANDS,
        "_get_handler": lambda: handler,
        "get_bridge": lambda: SimpleNamespace(
            start_session=lambda _client: "session-r016",
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

    return SimpleNamespace(_authenticated=True, _client_id="r016",
                           _session_id=None, _ws_id=1, send=send)


def _receive_one(receive, connection, command_type, request_id, payload=None):
    asyncio.run(receive(connection, json.dumps({
        "type": command_type, "id": request_id, "payload": payload or {}})))


def _breaker(name):
    return CircuitBreaker(
        name=name,
        config=CircuitBreakerConfig(failure_threshold=5, timeout_seconds=30.0))


def test_a_mutating_timeout_on_the_live_ws_dispatch_is_an_unknown_outcome(monkeypatch):
    """The live transport answers a real handler's timeout response, not a snag."""
    handler = _timeout_handler(monkeypatch)
    receive = _hwebserver_receive(handler, breaker=None)
    sent = []
    connection = _connection(sent)

    _receive_one(receive, connection, "execute_python", "r016-h-1", {"content": "x = 1"})

    outcome = sent[-1]["data"]["outcome"]
    assert sent[-1]["id"] == "r016-h-1"
    assert (outcome["code"], outcome["outcome"], outcome["dispatched"]) == (
        "transport.timeout", "unknown_outcome", "maybe")


def test_five_mutating_timeouts_open_the_ws_breaker_and_the_sixth_is_not_dispatched(
        monkeypatch):
    """Breaker failures counted THROUGH the handler's response, not an exception."""
    handler = _timeout_handler(monkeypatch)
    calls = _count_dispatches(handler)
    breaker = _breaker("r016-ws-timeout")
    receive = _hwebserver_receive(handler, breaker)
    sent = []
    connection = _connection(sent)

    for i in range(5):
        _receive_one(receive, connection, "execute_python", "t-%d" % i,
                     {"content": "x = 1"})

    assert [wire["success"] for wire in sent] == [False] * 5
    assert {wire["data"]["outcome"]["code"] for wire in sent} == {"transport.timeout"}
    assert breaker.state is CircuitState.OPEN
    assert calls == ["execute_python"] * 5

    _receive_one(receive, connection, "execute_python", "sixth", {"content": "x = 1"})

    sixth = sent[-1]
    assert sixth["id"] == "sixth"
    assert sixth["success"] is False
    outcome = sixth["data"]["outcome"]
    assert (outcome["code"], outcome["outcome"]) == ("server.busy", "retryable")
    assert calls == ["execute_python"] * 5, "the sixth command must not be dispatched"


def test_read_timeouts_never_open_the_ws_breaker(monkeypatch):
    """A read that timed out changed nothing — retryable, never a service fault."""
    handler = _timeout_handler(monkeypatch)
    calls = _count_dispatches(handler)
    breaker = _breaker("r016-ws-read-timeout")
    receive = _hwebserver_receive(handler, breaker)
    sent = []
    connection = _connection(sent)

    for i in range(6):
        _receive_one(receive, connection, "get_scene_info", "read-%d" % i)

    assert {wire["data"]["outcome"]["code"] for wire in sent} == {"transport.read_retry"}
    assert breaker.state is CircuitState.CLOSED
    assert calls == ["get_scene_info"] * 6, "reads are never fast-failed"
