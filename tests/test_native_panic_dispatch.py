"""L-PANIC-WS.1: a native panic during a command is answered at the dispatch seam.

PyO3 turns a Rust panic into ``pyo3_runtime.PanicException``, which derives
from ``BaseException``. Every arm in ``SynapseHandler.handle()``, and in the
transports around it, catches ``Exception`` or narrower, so the panic passed
all of them. On both WebSocket transports no reply was sent. On the bridge
routes (the in-Houdini ``/mcp`` endpoint and the panel's tool route) the panic
escaped the tool call.

The fix is one arm after the last arm in ``handle()``. It answers a native
panic with a failed reply under the request's own id, and re-raises everything
``synapse.memory.native_panic.is_native_panic`` rejects.

Fakes only: no hython, no Houdini, no real Rust module. The panic is a
stand-in shaped like PyO3's (a ``BaseException`` subclass whose ``__module__``
is ``pyo3_runtime``), as in tests/test_native_panic_construction.py. The
handler is a real ``SynapseHandler`` whose registry is swapped for a scripted
fake. The command is ``ping``, which is read-only, so the C5 lock, the live
integrity envelope and ``_submit_logs`` stay out of the way.

Bite. Against the unguarded handlers.py the five answer cases fail, each
because the ``PanicException`` escapes. The six re-raise cases are pins: they
pass on both sides, because what is not a native panic must still propagate.
"""

import ast
import asyncio
import importlib
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from synapse.core.protocol import SynapseCommand, SynapseResponse

#: Shaped like PyO3's panic: a BaseException subclass from ``pyo3_runtime``.
PanicException = type("PanicException", (BaseException,), {"__module__": "pyo3_runtime"})

#: Named like PyO3's panic but defined by some other module: not ours to answer.
ForeignPanicException = type(
    "PanicException", (BaseException,), {"__module__": "not_pyo3_runtime"})

#: A BaseException subclass with another name, from PyO3's own module.
UnrelatedBaseException = type(
    "UnrelatedBaseException", (BaseException,), {"__module__": "pyo3_runtime"})

#: Any non-None handler, so handle() never takes the alias fallback.
_FOUND = object()


def _handlers():
    return importlib.import_module("synapse.server.handlers")


class _ScriptedRegistry:
    """get() finds every command; invoke() raises or returns the next outcome."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)

    def get(self, command_type):
        return _FOUND

    def invoke(self, command_type, payload, ctx=None):
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _real_handler(*outcomes):
    """A real SynapseHandler whose registry answers each ``ping`` in turn."""
    handlers = _handlers()
    # ping is read-only: no C5 lock, no live envelope, no _submit_logs.
    assert "ping" in handlers._READ_ONLY_COMMANDS
    handler = handlers.SynapseHandler()
    handler._registry = _ScriptedRegistry(outcomes)
    return handler


def _ping(request_id):
    return SynapseCommand(type="ping", id=request_id, payload={})


def _panic():
    return PanicException("rust panicked")


# ---------------------------------------------------------------------------
# the seam itself
# ---------------------------------------------------------------------------

def test_handle_answers_a_native_panic_under_the_request_id(caplog):
    handler = _real_handler(_panic())
    caplog.set_level(logging.ERROR, logger="synapse.server.handlers")

    response = handler.handle(_ping("req-1"))

    assert response.success is False
    assert response.id == "req-1"
    assert "PanicException" in response.error and "native" in response.error
    errors = [r for r in caplog.records
              if r.name == "synapse.server.handlers" and r.levelno == logging.ERROR]
    assert len(errors) == 1


# ---------------------------------------------------------------------------
# the routes that dispatch through handle()
# ---------------------------------------------------------------------------

def _standalone_server(handler):
    # The helper from tests/test_harden_h3_error_reply_id.py.
    from synapse.server import websocket as transport
    server = object.__new__(transport.SynapseServer)
    server._handler, server._session_manager = handler, None
    server._enable_resilience = False
    server._circuit_breaker = None
    server._avg_latency, server._latency_alpha = 0.0, 0.2
    return server


def test_standalone_ws_answers_a_panic_then_the_next_request():
    server = _standalone_server(_real_handler(_panic(), {"pong": True}))
    sent = []
    websocket = SimpleNamespace(send=lambda value: sent.append(json.loads(value)))

    server._handle_message(
        websocket, json.dumps({"type": "ping", "id": "req-1", "payload": {}}), "local")
    server._handle_message(
        websocket, json.dumps({"type": "ping", "id": "req-2", "payload": {}}), "local")

    assert [reply["id"] for reply in sent] == ["req-1", "req-2"]
    assert sent[0]["success"] is False and "PanicException" in sent[0]["error"]
    assert sent[1]["success"] is True


def test_hwebserver_receive_answers_a_panic_under_the_request_id():
    # The receive harness from tests/test_harden_h3_error_reply_id.py, with
    # _get_handler returning the real handler. A Mock(side_effect=...) handler
    # would raise past handle() and never reach the arm under test.
    from synapse.core.farm_contract import FARM_CONTROL_COMMANDS, FARM_READ_COMMANDS
    path = Path(__file__).parents[1] / "python/synapse/server/hwebserver_adapter.py"
    node = next(n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "receive")
    sent = []

    async def send(text, **kwargs):
        sent.append(json.loads(text))

    handler = _real_handler(_panic())
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
    assert sent[-1]["success"] is False and "PanicException" in sent[-1]["error"]


def test_bridge_route_direct_dispatch_answers_a_panic(monkeypatch):
    bridge_adapter = importlib.import_module("synapse.panel.bridge_adapter")
    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: None)

    response = bridge_adapter.execute_through_bridge(
        "synapse_add_memory", _real_handler(_panic()),
        SynapseCommand(type="ping", id="req-b", payload={}))

    assert response.success is False
    assert response.id == "req-b"
    assert "PanicException" in response.error


def test_bridge_route_through_a_bridge_answers_a_panic(monkeypatch):
    bridge_adapter = importlib.import_module("synapse.panel.bridge_adapter")

    class _Bridge:
        """Runs the operation and reports success, as the real bridge does
        when the wrapped call returns: the four fields execute_through_bridge
        reads afterwards."""

        def execute(self, op):
            return SimpleNamespace(success=True, result=op.fn(), integrity=None, error=None)

    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: _Bridge())

    response = bridge_adapter.execute_through_bridge(
        "synapse_add_memory", _real_handler(_panic()),
        SynapseCommand(type="ping", id="req-b", payload={}))

    # The arm's own reply, not the bridge's "Bridge: ..." failure.
    assert response.success is False
    assert response.id == "req-b"
    assert "native" in response.error and "PanicException" in response.error


# ---------------------------------------------------------------------------
# pins: what is not a native panic still propagates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exc", [
    KeyboardInterrupt(),
    SystemExit(3),
    GeneratorExit(),
    asyncio.CancelledError(),
    ForeignPanicException("not pyo3's"),
    UnrelatedBaseException("not a panic"),
], ids=[
    "KeyboardInterrupt",
    "SystemExit",
    "GeneratorExit",
    "CancelledError",
    "foreign-PanicException",
    "unrelated-BaseException",
])
def test_handle_reraises_what_is_not_a_native_panic(exc):
    handler = _real_handler(exc)

    with pytest.raises(type(exc)) as caught:
        handler.handle(_ping("req-p"))

    assert caught.value is exc
