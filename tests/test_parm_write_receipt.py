"""NR-WRITE-RECEIPT: an authored write's receipt survives success and failure.

G25 returned ``observed``, ``mismatch`` and a refusal, but:

- an uninspectable parm read exactly like a plain, unanimated one (the count
  collapsed to 0 and the source to None);
- a ``$HIP`` string was compared against its ``eval()`` expansion, so every
  correct authored write reported a mismatch;
- a failure produced no receipt at all, and a lost transport discarded what
  little there was;
- ``key_at_frame`` used whatever the playhead said instead of the declared
  frame.

These pins are pure Python. The parms follow Houdini 22.0.400 where it matters
(``unexpandedString`` raising for non-strings and keyed parms, a distinct-but-
equal reference wrapper) and raise the same ``_OPERATION_FAILED`` class the
module catches.
"""
import asyncio
import importlib
import json
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

# Qt stub -- the established sibling convention (tests/test_timeouts_c7.py).
# The panel's tool_executor imports PySide6.QtCore at module top; in bare stock
# python this import-only stub keeps the route pin deterministic. Real PySide6
# (hython) wins when it is already loaded.
if "PySide6" not in sys.modules:
    class _QObject:
        def __init__(self, *a, **k):
            pass

    class _QThread:
        def __init__(self, *a, **k):
            pass

    _qtcore = types.ModuleType("PySide6.QtCore")
    _qtcore.QObject = _QObject
    _qtcore.QThread = _QThread
    _qtcore.Slot = lambda *a, **k: (lambda f: f)
    _qtcore.Signal = lambda *a, **k: MagicMock()
    _pyside6 = types.ModuleType("PySide6")
    _pyside6.QtCore = _qtcore
    sys.modules["PySide6"] = _pyside6
    sys.modules["PySide6.QtCore"] = _qtcore

from synapse.core.tool_results import (  # noqa: E402
    failure_receipt,
    result_misses,
    unpack_tool_result,
)
from synapse.server import parm_authored  # noqa: E402
from synapse.server.parm_authored import (  # noqa: E402
    ParmWriteRefused,
    author_parm_write,
    authored_fields,
)

_FAILED = parm_authored._OPERATION_FAILED
AUTHORED = "$HIP/render/$F4.exr"
EXPANDED = "/proj/render/0001.exr"


# ---------------------------------------------------------------------------
# Stand-ins
# ---------------------------------------------------------------------------

class _Key:
    def __init__(self, frame=1.0, value=0.0):
        self._frame = frame
        self._value = value

    def setFrame(self, frame):
        self._frame = frame

    def setValue(self, value):
        self._value = value

    def frame(self):
        return self._frame

    def value(self):
        return self._value


class _Parm:
    """A numeric parm that behaves the way the H22 probe showed."""

    def __init__(self, value=0.0, keys=(), name="tx", frame=1.0,
                 rejects=None):
        self._value = value
        self._keys = [_Key(f, v) for f, v in keys]
        self._name = name
        self._frame = frame
        self._rejects = rejects
        self._extrap = ("extend", "extend")
        self.writes = []

    def name(self):
        return self._name

    def node(self):
        return SimpleNamespace(path=lambda: "/obj/geo1")

    def keyframes(self):
        return tuple(self._keys)

    def getReferencedParm(self):
        # Equal, not identical: the same trap the H22 probe recorded.
        return self

    def eval(self):
        if not self._keys:
            return self._value
        for key in self._keys:
            if key.frame() == self._frame:
                return key.value()
        return self._keys[0].value()

    def evalAtFrame(self, frame):
        if not self._keys:
            return self._value
        for key in self._keys:
            if key.frame() == frame:
                return key.value()
        return self._keys[0].value()

    def unexpandedString(self):
        raise _FAILED("Only string parms have unexpanded strings")

    def keyframeExtrapolation(self, before):
        if not self._keys:
            raise _FAILED("no animation channel")
        return self._extrap[0 if before else 1]

    def setKeyframeExtrapolation(self, before, value):
        if not self._keys:
            raise _FAILED("no animation channel")
        if before:
            self._extrap = (value, self._extrap[1])
        else:
            self._extrap = (self._extrap[0], value)

    def set(self, value, follow_parm_reference=True):
        if self._rejects is not None and self._rejects(value):
            raise TypeError("not a number")
        self.writes.append(value)
        if self._keys:
            if follow_parm_reference:
                self._store_key(_Key(self._frame, value))
            else:
                self._keys = []
                self._value = value
        else:
            self._value = value

    def setKeyframe(self, key):
        self._store_key(key)
        self._extrap = ("extend", "extend")  # probed on 22.0.400

    def deleteAllKeyframes(self):
        self._keys = []

    def _store_key(self, key):
        self._keys = [k for k in self._keys if k.frame() != key.frame()]
        self._keys.append(key)
        self._keys.sort(key=lambda k: k.frame())


class _UninspectableParm(_Parm):
    """Neither the animation nor the reference state can be read."""

    def keyframes(self):
        raise _FAILED("cannot inspect keyframes")

    def getReferencedParm(self):
        raise _FAILED("cannot inspect the reference source")


class _StringParm:
    """A string parm: stores the authored text, evaluates to the expansion."""

    def __init__(self, name="picture", store=True):
        self._name = name
        self._raw = "$HIP/render/$HIPNAME.$OS.$F4.exr"
        self._value = "/proj/render/untitled.geo.0001.exr"
        self._store = store
        self.writes = []

    def name(self):
        return self._name

    def node(self):
        return SimpleNamespace(path=lambda: "/stage/lookdev/preview_settings")

    def keyframes(self):
        return ()

    def getReferencedParm(self):
        return self

    def eval(self):
        return self._value

    def unexpandedString(self):
        return self._raw

    def keyframeExtrapolation(self, before):
        raise _FAILED("no animation channel")

    def set(self, value, follow_parm_reference=True):
        self.writes.append(value)
        if self._store:
            self._raw = value
            self._value = (value.replace("$HIP", "/proj")
                           .replace("$F4", "0001"))


@contextmanager
def _group(_name):
    yield


def _install_fake_hou(monkeypatch, parm, frame=1.0):
    """Patch the handler's hou and, for key writes, the module's hou too."""
    from synapse.server import handlers

    node = SimpleNamespace(parm=lambda name: parm,
                           parmTuple=lambda name: None)
    fake = SimpleNamespace(node=lambda path: node,
                           undos=SimpleNamespace(group=_group),
                           frame=lambda: frame)
    monkeypatch.setattr(handlers, "HOU_AVAILABLE", True, raising=False)
    monkeypatch.setattr(handlers, "hou", fake, raising=False)
    return fake


# ---------------------------------------------------------------------------
# 1. The uninspectable parm
# ---------------------------------------------------------------------------

def test_uninspectable_parm_refuses_before_any_setter(monkeypatch):
    parm = _UninspectableParm()

    with pytest.raises(ParmWriteRefused) as caught:
        author_parm_write([parm], [1.0])

    assert caught.value.receipt["write"] == "not_attempted"
    assert caught.value.receipt["error"]["code"] == "parm.inspection_unknown"
    assert parm.writes == []

    # A read must not report a count of zero or "no reference" either.
    assert authored_fields(parm, 1.0) == {"inspection": "unknown"}

    # The handler reaches the same refusal and writes nothing.
    _install_fake_hou(monkeypatch, parm)
    from synapse.server import handlers

    with pytest.raises(ParmWriteRefused) as handler_refusal:
        handlers.SynapseHandler._handle_set_parm(
            None, {"node": "/obj/geo1", "parm": "tx", "value": 1.0})

    assert handler_refusal.value.receipt["write"] == "not_attempted"
    assert parm.writes == []


# ---------------------------------------------------------------------------
# 2. The authored comparison domain
# ---------------------------------------------------------------------------

def test_raw_hip_string_compares_as_authored_text():
    parm = _StringParm()

    out = author_parm_write([parm], [AUTHORED])

    assert out["mismatch"] is False
    assert out["observed"] == EXPANDED          # legacy: still eval()
    readback = out["receipt"]["readback"]
    assert readback["domain"] == "authored-text"
    assert readback["raw_authored"] == AUTHORED
    assert readback["observed"] == EXPANDED
    # The old comparison is still reported, separately, and it is False.
    assert readback["evaluated_equal"] is False
    assert readback["state"] == "match"

    # A parm that does not take the authored text is a real mismatch.
    stuck = _StringParm(store=False)
    out = author_parm_write([stuck], [AUTHORED])

    assert out["mismatch"] is True
    assert out["receipt"]["readback"]["state"] == "mismatch"
    assert out["observed"] == "/proj/render/untitled.geo.0001.exr"


# ---------------------------------------------------------------------------
# 3. The lost transport
# ---------------------------------------------------------------------------

_RECEIPT = {
    "schema": "synapse.parm-write/1",
    "write": "not_attempted",
    "readback": {"state": "not_attempted"},
    "error": {"code": "parm.inspection_unknown", "message": "cannot inspect"},
}


def test_lost_transport_still_returns_the_structured_receipt(monkeypatch):
    structured = {
        "content": [{"type": "text", "text": "failed: cannot inspect"}],
        "isError": True,
        "structuredContent": {"receipt": _RECEIPT},
    }
    assert failure_receipt(structured) == _RECEIPT
    assert unpack_tool_result(structured) == ({"receipt": _RECEIPT}, True)

    meta = {
        "content": [{"type": "text", "text": "failed: cannot inspect"}],
        "isError": True,
        "_meta": {"synapse/outcome": {"evidence": {"receipt": _RECEIPT}}},
    }
    assert failure_receipt(meta) == _RECEIPT
    assert unpack_tool_result(meta) == ({"receipt": _RECEIPT}, True)

    raised = RuntimeError("boom")
    raised.outcome = {"evidence": {"receipt": _RECEIPT}}
    assert failure_receipt(raised) == _RECEIPT

    # The /mcp producer keeps the handler payload on failure.
    from synapse.core.protocol import SynapseResponse
    from synapse.mcp import tools
    from synapse.panel import bridge_adapter

    class _Handler:
        def handle(self, command):
            return SynapseResponse(id=command.id, success=False,
                                   error="cannot inspect",
                                   data={"receipt": _RECEIPT})

    monkeypatch.setattr(bridge_adapter, "is_read_only", lambda name: True)
    monkeypatch.setattr(tools, "_TOOL_DISPATCH",
                        {"fake_parm_tool": ("set_parm", lambda args: args)})

    result = tools.dispatch_tool(_Handler(), "fake_parm_tool",
                                 {"node": "/obj/geo1"})

    assert result["isError"] is True
    assert result["structuredContent"] == {"receipt": _RECEIPT}
    assert failure_receipt(result) == _RECEIPT


# ---------------------------------------------------------------------------
# 4. The handler's failure arm
# ---------------------------------------------------------------------------

def test_handler_failure_carries_the_receipt(monkeypatch):
    from synapse.core.protocol import SynapseCommand
    from synapse.server import handlers

    parm = _UninspectableParm()
    _install_fake_hou(monkeypatch, parm)
    monkeypatch.setattr(handlers._envelope, "envelope_active",
                        lambda _cmd_type: False)

    handler = handlers.SynapseHandler()
    # Exercise handle()'s failure arm without FloorGate provenance writes.
    monkeypatch.setattr(handler._registry, "invoke",
                        lambda cmd_type, payload, ctx=None:
                        handler._handle_set_parm(payload))

    response = handler.handle(SynapseCommand(
        type="set_parm", id="req-1",
        payload={"node": "/obj/geo1", "parm": "tx", "value": 1.0}))

    assert response.success is False
    assert response.data["receipt"]["write"] == "not_attempted"
    assert response.data["receipt"]["error"]["code"] == "parm.inspection_unknown"
    assert "inspect" in response.error
    assert parm.writes == []


# ---------------------------------------------------------------------------
# 5. The declared frame
# ---------------------------------------------------------------------------

def test_queued_write_refuses_without_precondition(monkeypatch):
    from synapse.server import handlers

    parm = _Parm(0.0)
    _install_fake_hou(monkeypatch, parm)

    with pytest.raises(ParmWriteRefused) as caught:
        handlers.SynapseHandler._handle_set_parm(
            None, {"node": "/obj/geo1", "parm": "tx", "value": 1.0,
                   "queued": True})

    assert caught.value.receipt["error"]["code"] == "parm.precondition_missing"
    assert caught.value.receipt["write"] == "not_attempted"
    assert parm.writes == []

    # An immediate legacy key write keeps current-frame behaviour and reports
    # the frame it actually used.
    legacy = _Parm(0.0, keys=[(1.0, 0.0)], frame=5.0)
    _install_fake_hou(monkeypatch, legacy, frame=5.0)
    monkeypatch.setattr(parm_authored, "hou",
                        SimpleNamespace(Keyframe=_Key, frame=lambda: 5.0))

    out = handlers.SynapseHandler._handle_set_parm(
        None, {"node": "/obj/geo1", "parm": "tx", "value": 7.0,
               "mode": "key_at_frame"})

    assert out["receipt"]["request"]["frame"] == 5.0
    assert out["observed"] == 7.0

    # A declared frame is the frame. The playhead is never consulted.
    declared = _Parm(0.0, keys=[(1.0, 0.0)], frame=12.0)
    _install_fake_hou(monkeypatch, declared, frame=5.0)

    def _no_frame():
        raise AssertionError("hou.frame() must not be called when a frame is declared")

    monkeypatch.setattr(parm_authored, "hou",
                        SimpleNamespace(Keyframe=_Key, frame=_no_frame))

    out = handlers.SynapseHandler._handle_set_parm(
        None, {"node": "/obj/geo1", "parm": "tx", "value": 7.0,
               "mode": "key_at_frame", "frame": 12})

    assert out["receipt"]["request"]["frame"] == 12
    assert out["authored"]["frame"] == 12
    assert any(key.frame() == 12 for key in declared.keyframes())


# ---------------------------------------------------------------------------
# 6. The partial tuple write
# ---------------------------------------------------------------------------

def test_partial_tuple_write_reports_partial_and_preserves_the_original_error():
    good = _Parm(1.0, name="tx")
    bad = _Parm(2.0, name="ty", rejects=lambda _value: True)

    with pytest.raises(TypeError) as caught:
        author_parm_write([good, bad], [5.0, 6.0])

    receipt = caught.value.receipt
    assert receipt["write"] == "partial"
    assert receipt["readback"]["state"] == "not_attempted"
    # Recovery names what _restore actually did, component by component.
    assert receipt["recovery"]["actions"] == ["set"]
    states = [entry["state"] for entry in receipt["recovery"]["evidence"]["targets"]]
    assert states == ["verified", "failed"]

    # The original failure survives; the restore attempt does not replace it.
    assert isinstance(caught.value, TypeError)
    assert str(caught.value) == "not a number"
    assert good.eval() == 1.0     # the applied component was put back
    assert bad.eval() == 2.0      # the refused component never changed


def test_partial_write_is_a_miss_for_the_warning_policy():
    """A partial/unknown write must not render as a clean panel 'done'."""
    assert result_misses({"receipt": {"write": "partial", "readback": {"state": "not_attempted"}}})
    assert result_misses({"receipt": {"write": "unknown", "readback": {"state": "not_attempted"}}})
    assert result_misses({"receipt": {"write": "applied", "readback": {"state": "unknown"}}})
    # A true mismatch is a miss too: the scene holds a different value.
    assert result_misses({"receipt": {"write": "applied", "readback": {"state": "mismatch"}}})
    assert result_misses({"receipt": {"write": "applied", "readback": {"state": "match"}}}) == []


# ---------------------------------------------------------------------------
# 7. The receipt across every installed route (round two, item 1)
# ---------------------------------------------------------------------------

def _failed_result():
    return {
        "content": [{"type": "text", "text": "failed: cannot inspect"}],
        "isError": True,
        "structuredContent": {"receipt": _RECEIPT},
    }


def test_outcomes_rewrap_carries_structured_content(monkeypatch):
    """Both /mcp rewraps keep the handler payload, not only its text."""
    from synapse.mcp import server as server_mod

    server = server_mod.MCPServer(handler=SimpleNamespace())
    server._enable_resilience = False
    server._rate_limiter = None
    server._circuit_breaker = None
    monkeypatch.setattr(server_mod.read_only_mode, "refusal_for_tool",
                        lambda name: None)
    monkeypatch.setattr(server_mod, "dispatch_tool",
                        lambda handler, name, args: _failed_result())

    # The read-only fast path (server.py:715 class of site).
    monkeypatch.setattr(server_mod, "is_transport_fast_path", lambda name: True)
    fast = server._handle_tools_call(
        {"name": "houdini_get_parm", "arguments": {}})
    assert fast["isError"] is True
    assert fast["structuredContent"] == {"receipt": _RECEIPT}
    assert failure_receipt(fast) == _RECEIPT

    # The marshalled path (server.py:888 class of site).
    monkeypatch.setattr(server_mod, "is_transport_fast_path", lambda name: False)
    monkeypatch.setattr(server_mod, "_preflight_refusal", lambda *a, **k: None)
    import synapse.server.main_thread as main_thread
    import synapse.host.memory_loop as memory_loop

    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kw: fn())
    monkeypatch.setattr(memory_loop, "observe_operation",
                        lambda op, args, fn, **kw: fn())
    marshalled = server._handle_tools_call(
        {"name": "houdini_get_parm", "arguments": {}})
    assert marshalled["isError"] is True
    assert marshalled["structuredContent"] == {"receipt": _RECEIPT}
    assert failure_receipt(marshalled) == _RECEIPT


def test_stdio_failure_paths_carry_the_receipt(monkeypatch):
    """mcp_server.send_command keeps a failed response's receipt."""
    import mcp_server as stdio

    async def drive():
        response = {"success": False, "error": "cannot inspect",
                    "data": {"receipt": _RECEIPT}}

        class _WS:
            async def send(self, _text):
                loop = asyncio.get_running_loop()
                for future in list(stdio._pending.values()):
                    if not future.done():
                        loop.call_soon(future.set_result, response)

            async def close(self):
                return None

        async def _connection():
            return _WS()

        monkeypatch.setattr(stdio, "_get_connection", _connection)
        try:
            await stdio.send_command("set_parm", {"node": "/obj/geo1"})
        except RuntimeError as exc:
            return exc
        return None

    stdio._pending.clear()
    exc = asyncio.run(drive())
    assert exc is not None
    # A setter failure is not a ValueError; the receipt must not depend on it.
    assert not isinstance(exc, ValueError)
    assert failure_receipt(exc) == _RECEIPT
    assert stdio._exc_outcome(exc)["evidence"]["receipt"] == _RECEIPT


def test_panel_mcp_client_failure_carries_the_receipt(monkeypatch):
    """The panel's local MCP client keeps the receipt when it raises."""
    from synapse.panel.tool_executor import _MCPLocalClient

    client = _MCPLocalClient()
    monkeypatch.setattr(client, "_call_once",
                        lambda name, args: {"result": _failed_result()})

    with pytest.raises(RuntimeError) as caught:
        client.call_tool("houdini_set_parm", {})

    assert failure_receipt(caught.value) == _RECEIPT


# ---------------------------------------------------------------------------
# 8. A non-ValueError setter failure (round two, item 2)
# ---------------------------------------------------------------------------

class _OperationFailed(RuntimeError):
    """Stands in for hou.OperationFailed, which is not a ValueError."""

    def __init__(self, message="cannot set this parm"):
        super().__init__(message)


class _FailingSetterParm(_Parm):
    """A numeric parm whose setter raises a non-ValueError."""

    def set(self, value, follow_parm_reference=True):
        raise _OperationFailed()


def test_non_valueerror_setter_failure_keeps_the_receipt(monkeypatch):
    from synapse.core.protocol import SynapseCommand
    from synapse.server import handlers

    parm = _FailingSetterParm(0.0)
    _install_fake_hou(monkeypatch, parm)
    monkeypatch.setattr(handlers._envelope, "envelope_active",
                        lambda _cmd_type: False)

    assert not issubclass(_OperationFailed, ValueError)

    handler = handlers.SynapseHandler()
    monkeypatch.setattr(handler._registry, "invoke",
                        lambda cmd_type, payload, ctx=None:
                        handler._handle_set_parm(payload))

    response = handler.handle(SynapseCommand(
        type="set_parm", id="req-2",
        payload={"node": "/obj/geo1", "parm": "tx", "value": 1.0}))

    assert response.success is False
    assert response.data["receipt"]["write"] == "unknown"
    assert response.data["receipt"]["error"]["code"] == "parm.write_failed"
    # The original message still reaches the caller.
    assert "cannot set this parm" in response.error


# ---------------------------------------------------------------------------
# 9. The canonical payload and schema (round two, item 3)
# ---------------------------------------------------------------------------

def test_set_parm_payload_and_schema_carry_write_context():
    """A queued write's frame, precondition and id must reach the handler."""
    from synapse.mcp._tool_registry import TOOL_DISPATCH, TOOL_JSON

    cmd_type, builder = TOOL_DISPATCH["houdini_set_parm"]
    assert cmd_type == "set_parm"
    arguments = {
        "node": "/obj/geo1",
        "parm": "tx",
        "value": 1.0,
        "mode": "key_at_frame",
        "frame": 120,
        "queued": True,
        "expect": {"value": 0.0},
        "request_id": "req-9",
        "not_a_parm_field": "dropped",
    }
    payload = builder(arguments)
    assert payload == {key: value for key, value in arguments.items()
                      if key != "not_a_parm_field"}

    properties = TOOL_JSON["houdini_set_parm"]["inputSchema"]["properties"]
    for key in ("frame", "queued", "expect", "request_id"):
        assert key in properties


# ---------------------------------------------------------------------------
# 10. The request block's session and observed state (round two, item 5)
# ---------------------------------------------------------------------------

def test_request_block_carries_session_and_observed_fields(monkeypatch):
    from synapse.server import handlers

    parm = _Parm(0.0, frame=5.0)
    _install_fake_hou(monkeypatch, parm, frame=5.0)
    handler = handlers.SynapseHandler()
    handler.set_session_id("sess-live")

    out = handler._handle_set_parm({
        "node": "/obj/geo1", "parm": "tx", "value": 1.0,
        "request_id": "req-10",
    })

    request = out["receipt"]["request"]
    assert request["request_id"] == "req-10"
    assert request["expected_session"] == "sess-live"
    assert request["observed_session"] == "sess-live"
    # The frame the write actually ran under, beside the declared one.
    assert request["observed_frame"] == 5.0
    assert request["observed_target"] == "/obj/geo1/tx"


def test_queued_write_with_frame_but_no_expect_refuses(monkeypatch):
    """A declared frame is not proof the scene is the planned one."""
    from synapse.server import handlers

    parm = _Parm(0.0)
    _install_fake_hou(monkeypatch, parm)

    with pytest.raises(ParmWriteRefused) as caught:
        handlers.SynapseHandler._handle_set_parm(
            None, {"node": "/obj/geo1", "parm": "tx", "value": 1.0,
                   "queued": True, "frame": 1})

    assert caught.value.receipt["error"]["code"] == "parm.precondition_missing"
    assert caught.value.receipt["write"] == "not_attempted"
    assert parm.writes == []


# ---------------------------------------------------------------------------
# 11. key_at_frame's domain and readback (round two, item 4)
# ---------------------------------------------------------------------------

class _KeyableStringParm(_StringParm):
    """A text parm with a key setter, so a stray key write is observable."""

    def __init__(self, name="picture"):
        super().__init__(name=name)
        self.key_writes = []

    def setKeyframe(self, key):
        self.key_writes.append(key)

    def evalAtFrame(self, frame):
        return self._value


def test_key_at_frame_refuses_a_text_parameter(monkeypatch):
    """A numeric key domain is refused before the first setter."""
    from synapse.server import handlers

    parm = _KeyableStringParm()
    _install_fake_hou(monkeypatch, parm)
    monkeypatch.setattr(parm_authored, "hou",
                        SimpleNamespace(Keyframe=_Key, frame=lambda: 1.0))

    with pytest.raises(ParmWriteRefused) as caught:
        handlers.SynapseHandler._handle_set_parm(
            None, {"node": "/stage/lookdev/preview_settings",
                   "parm": "picture", "value": 1.0,
                   "mode": "key_at_frame", "frame": 1})

    assert caught.value.receipt["error"]["code"] == "parm.key_domain"
    assert caught.value.receipt["write"] == "not_attempted"
    assert caught.value.receipt["readback"]["state"] == "not_attempted"
    assert parm.key_writes == []
    assert parm.writes == []


def test_key_at_frame_reads_back_at_the_declared_frame(monkeypatch):
    """The receipt proves the key at the declared frame, not the playhead."""
    from synapse.server import handlers

    parm = _Parm(0.0, keys=[(1.0, 0.0)], frame=1.0)
    _install_fake_hou(monkeypatch, parm, frame=5.0)
    monkeypatch.setattr(parm_authored, "hou",
                        SimpleNamespace(Keyframe=_Key, frame=lambda: 5.0))

    out = handlers.SynapseHandler._handle_set_parm(
        None, {"node": "/obj/geo1", "parm": "tx", "value": 7.0,
               "mode": "key_at_frame", "frame": 12})

    readback = out["receipt"]["readback"]
    assert readback["frame"] == 12
    assert readback["domain"] == "numeric-at-frame"
    assert readback["key_present"] is True
    # The at-frame value is its own field; the legacy `observed` is eval().
    assert readback["observed_at_frame"] == 7.0
    assert readback["state"] == "match"


# ---------------------------------------------------------------------------
# 12. Refusals carry a receipt (round two, item 5)
# ---------------------------------------------------------------------------

def test_mode_and_arity_refusals_carry_a_receipt():
    parm = _Parm(0.0)

    with pytest.raises(ParmWriteRefused) as mode_exc:
        author_parm_write([parm], [1.0], mode="bogus", request={"request_id": "r"})
    assert mode_exc.value.receipt["error"]["code"] == "parm.mode_invalid"
    assert mode_exc.value.receipt["write"] == "not_attempted"
    assert parm.writes == []

    with pytest.raises(ParmWriteRefused) as arity_exc:
        author_parm_write([parm], [1.0, 2.0])
    assert arity_exc.value.receipt["error"]["code"] == "parm.arity_mismatch"
    assert arity_exc.value.receipt["write"] == "not_attempted"
    assert parm.writes == []


def test_handler_mode_refusal_carries_a_receipt(monkeypatch):
    from synapse.core.protocol import SynapseCommand
    from synapse.server import handlers

    parm = _Parm(0.0)
    _install_fake_hou(monkeypatch, parm)
    monkeypatch.setattr(handlers._envelope, "envelope_active",
                        lambda _cmd_type: False)

    handler = handlers.SynapseHandler()
    monkeypatch.setattr(handler._registry, "invoke",
                        lambda cmd_type, payload, ctx=None:
                        handler._handle_set_parm(payload))

    response = handler.handle(SynapseCommand(
        type="set_parm", id="req-12",
        payload={"node": "/obj/geo1", "parm": "tx", "value": 1.0,
                 "mode": "bogus"}))

    assert response.success is False
    assert response.data["receipt"]["error"]["code"] == "parm.mode_invalid"
    assert response.data["receipt"]["write"] == "not_attempted"
    assert parm.writes == []


# ---------------------------------------------------------------------------
# 13. The precondition is evaluated, not merely present (round 2.5, blocker 1)
# ---------------------------------------------------------------------------

def test_queued_expect_with_an_unknown_key_refuses_before_the_hop(monkeypatch):
    """Probe: expect={"value_typo": 0.0} wrote 1.0 and reported applied.

    The handler tested truthiness only, so a misspelled key was a precondition
    nobody checked. It must refuse with zero setters instead.
    """
    from synapse.server import handlers

    parm = _Parm(1.0)
    _install_fake_hou(monkeypatch, parm)

    with pytest.raises(ParmWriteRefused) as caught:
        handlers.SynapseHandler._handle_set_parm(
            None, {"node": "/obj/geo1", "parm": "tx", "value": 1.0,
                   "queued": True, "expect": {"value_typo": 0.0}})

    assert caught.value.receipt["error"]["code"] == "parm.precondition_invalid"
    assert caught.value.receipt["write"] == "not_attempted"
    assert parm.writes == []


def test_author_write_refuses_an_expect_that_names_no_state():
    """The module refuses the same shapes with no handler in the way."""
    parm = _Parm(0.0)

    with pytest.raises(ParmWriteRefused) as unknown:
        author_parm_write([parm], [1.0], queued=True,
                          expect={"value_typo": 0.0})
    assert unknown.value.receipt["error"]["code"] == "parm.precondition_invalid"
    assert unknown.value.receipt["write"] == "not_attempted"
    assert parm.writes == []

    # At least one of {"value", "raw_authored"} is required.
    with pytest.raises(ParmWriteRefused) as empty:
        author_parm_write([parm], [1.0], queued=True, expect={})
    assert empty.value.receipt["error"]["code"] == "parm.precondition_invalid"
    assert parm.writes == []


def test_expect_that_names_an_uncheckable_state_refuses():
    """Probe: expect={"raw_authored": None} wrote 5.0 and reported applied.

    ``raw_authored()`` returns None for a numeric or keyframed parm, so the
    comparison was None == None: a schema-legal precondition that checked
    nothing. A key is not a check; the VALUE has to name something comparable.
    """
    parm = _Parm(0.0)

    with pytest.raises(ParmWriteRefused) as null_expect:
        author_parm_write([parm], [5.0], queued=True,
                          expect={"raw_authored": None})
    assert null_expect.value.receipt["error"]["code"] == "parm.precondition_invalid"
    assert null_expect.value.receipt["write"] == "not_attempted"
    assert parm.writes == []

    # A string expectation on a parm that cannot report authored text is
    # equally unverifiable. It used to refuse as "did not hold", which reads as
    # a scene mismatch rather than a precondition nobody could check.
    with pytest.raises(ParmWriteRefused) as unverifiable:
        author_parm_write([parm], [5.0], queued=True,
                          expect={"raw_authored": AUTHORED})
    assert unverifiable.value.receipt["error"]["code"] == "parm.precondition_invalid"
    assert parm.writes == []


def test_expect_value_must_be_a_scalar():
    """A null or a collection names no value a parameter can hold."""
    parm = _Parm(0.0)

    for bad in (None, {"a": 1}, [1.0], (1.0,)):
        with pytest.raises(ParmWriteRefused) as caught:
            author_parm_write([parm], [5.0], queued=True,
                              expect={"value": bad})
        assert caught.value.receipt["error"]["code"] == "parm.precondition_invalid"
    assert parm.writes == []

    # A JSON scalar is comparable, and still compared.
    out = author_parm_write([_Parm(0.0)], [5.0], queued=True,
                            expect={"value": 0})
    assert out["receipt"]["write"] == "applied"


def test_handler_route_refuses_a_null_authored_precondition(monkeypatch):
    """The probe's pure-Python route: handle() reported success true, applied."""
    from synapse.core.protocol import SynapseCommand
    from synapse.server import handlers

    parm = _Parm(1.0)
    _install_fake_hou(monkeypatch, parm)
    monkeypatch.setattr(handlers._envelope, "envelope_active",
                        lambda _cmd_type: False)

    handler = handlers.SynapseHandler()
    monkeypatch.setattr(handler._registry, "invoke",
                        lambda cmd_type, payload, ctx=None:
                        handler._handle_set_parm(payload))

    response = handler.handle(SynapseCommand(
        type="set_parm", id="req-25c",
        payload={"node": "/obj/geo1", "parm": "tx", "value": 1.0,
                 "queued": True, "expect": {"raw_authored": None}}))

    assert response.success is False
    assert response.data["receipt"]["error"]["code"] == "parm.precondition_invalid"
    assert response.data["receipt"]["write"] == "not_attempted"
    assert parm.writes == []


def test_queued_expect_that_holds_proceeds_and_is_recorded(monkeypatch):
    from synapse.server import handlers

    parm = _Parm(0.0)
    _install_fake_hou(monkeypatch, parm)

    out = handlers.SynapseHandler._handle_set_parm(
        None, {"node": "/obj/geo1", "parm": "tx", "value": 1.0,
               "queued": True, "expect": {"value": 0.0},
               "request_id": "req-13"})

    assert out["receipt"]["write"] == "applied"
    assert out["receipt"]["readback"]["state"] == "match"
    # The expectation that was actually checked rides in the receipt.
    assert out["receipt"]["request"]["expect"] == {"value": 0.0}
    assert parm.writes == [1.0]


def test_queued_expect_that_is_stale_refuses_on_main(monkeypatch):
    from synapse.server import handlers

    parm = _Parm(3.0)  # the scene moved since the write was planned
    _install_fake_hou(monkeypatch, parm)

    with pytest.raises(ParmWriteRefused) as caught:
        handlers.SynapseHandler._handle_set_parm(
            None, {"node": "/obj/geo1", "parm": "tx", "value": 1.0,
                   "queued": True, "expect": {"value": 0.0}})

    assert caught.value.receipt["error"]["code"] == "parm.precondition_failed"
    assert caught.value.receipt["write"] == "not_attempted"
    assert caught.value.receipt["request"]["expect"] == {"value": 0.0}
    assert parm.writes == []


def test_queued_raw_authored_expect_is_honoured():
    parm = _StringParm()
    held = parm.unexpandedString()

    out = author_parm_write([parm], [AUTHORED], queued=True,
                            expect={"raw_authored": held})
    assert out["receipt"]["write"] == "applied"
    assert out["receipt"]["request"]["expect"] == {"raw_authored": held}

    stuck = _StringParm()
    with pytest.raises(ParmWriteRefused) as caught:
        author_parm_write([stuck], [AUTHORED], queued=True,
                          expect={"raw_authored": "$HIP/other.exr"})
    assert caught.value.receipt["error"]["code"] == "parm.precondition_failed"
    assert stuck.writes == []


# ---------------------------------------------------------------------------
# 14. A queued key write never lands at the playhead (round 2.5, blocker 2)
# ---------------------------------------------------------------------------

def _no_playhead():
    raise AssertionError(
        "hou.frame() must not stand in for a queued write's declared frame")


def test_queued_key_write_without_a_declared_frame_refuses(monkeypatch):
    """Probe: queued=True, mode=key_at_frame, no frame, playhead 5 -> keys [1,5]."""
    from synapse.server import handlers

    parm = _Parm(0.0, keys=[(1.0, 0.0)], frame=5.0)
    _install_fake_hou(monkeypatch, parm, frame=5.0)
    monkeypatch.setattr(parm_authored, "hou",
                        SimpleNamespace(Keyframe=_Key, frame=_no_playhead))

    with pytest.raises(ParmWriteRefused) as caught:
        handlers.SynapseHandler._handle_set_parm(
            None, {"node": "/obj/geo1", "parm": "tx", "value": 7.0,
                   "mode": "key_at_frame", "queued": True,
                   "expect": {"value": 0.0}})

    assert caught.value.receipt["error"]["code"] == "parm.frame_unknown"
    assert caught.value.receipt["write"] == "not_attempted"
    assert [key.frame() for key in parm.keyframes()] == [1.0]
    assert parm.writes == []


def test_queued_key_write_with_a_declared_frame_lands_there(monkeypatch):
    from synapse.server import handlers

    parm = _Parm(0.0, keys=[(1.0, 0.0)], frame=5.0)
    _install_fake_hou(monkeypatch, parm, frame=5.0)
    monkeypatch.setattr(parm_authored, "hou",
                        SimpleNamespace(Keyframe=_Key, frame=_no_playhead))

    out = handlers.SynapseHandler._handle_set_parm(
        None, {"node": "/obj/geo1", "parm": "tx", "value": 7.0,
               "mode": "key_at_frame", "frame": 12, "queued": True,
               "expect": {"value": 0.0}})

    assert [key.frame() for key in parm.keyframes()] == [1.0, 12.0]
    assert out["receipt"]["request"]["frame"] == 12
    assert out["receipt"]["readback"]["state"] == "match"


# ---------------------------------------------------------------------------
# 15. The legacy observed keeps its published domain (round 2.5, blocker 3)
# ---------------------------------------------------------------------------

def test_key_at_frame_keeps_the_legacy_observed_at_the_playhead(monkeypatch):
    """Probe: frame=12 on a playhead of 5 reported observed 7.0 while eval() 0.0.

    ``observed`` is the legacy field every read returns, and the node's why
    promises it stays ``eval()``. The at-frame value belongs in its own field.
    """
    from synapse.server import handlers

    parm = _Parm(0.0, keys=[(1.0, 0.0)], frame=5.0)  # playhead 5
    _install_fake_hou(monkeypatch, parm, frame=5.0)
    monkeypatch.setattr(parm_authored, "hou",
                        SimpleNamespace(Keyframe=_Key, frame=lambda: 5.0))

    out = handlers.SynapseHandler._handle_set_parm(
        None, {"node": "/obj/geo1", "parm": "tx", "value": 7.0,
               "mode": "key_at_frame", "frame": 12})

    readback = out["receipt"]["readback"]
    assert parm.eval() == 0.0
    assert out["observed"] == 0.0                 # legacy: eval() at the playhead
    assert readback["observed"] == 0.0
    assert readback["observed_at_frame"] == 7.0   # what the write landed
    assert readback["evaluated_equal"] is False   # the old comparison, from eval()
    assert readback["state"] == "match"


# ---------------------------------------------------------------------------
# 16. The consumer keeps the receipt (round 2.5, blocker 4 / R3b)
# ---------------------------------------------------------------------------

def test_failure_detail_adds_a_receipt_only_when_there_is_one():
    """The shared consumer helper: no receipt, no invented JSON."""
    from synapse.core.tool_results import failure_detail

    plain = RuntimeError("cannot inspect")
    assert failure_detail(plain) == "cannot inspect"

    carried = RuntimeError("cannot inspect")
    carried.receipt = _RECEIPT
    payload = json.loads(failure_detail(carried))
    assert payload["error"] == "cannot inspect"
    assert payload["receipt"] == _RECEIPT

    # A payload-shaped failure (the fallback dispatch) works the same way.
    payload = json.loads(failure_detail({"receipt": _RECEIPT}, "refused"))
    assert payload == {"error": "refused", "receipt": _RECEIPT}
    # No receipt, no envelope: the message stays the message.
    assert failure_detail({"error": "refused"}, "refused") == "refused"


def test_panel_agent_route_keeps_the_receipt_on_a_refused_write(monkeypatch):
    """Probe: claude_worker stringified the exception and dropped exc.receipt."""
    import synapse.panel.claude_worker as cw

    refused = RuntimeError("The precondition on /obj/geo1/tx did not hold")
    refused.receipt = _RECEIPT
    monkeypatch.setattr(cw, "try_mcp_tool_call",
                        lambda name, args: (_ for _ in ()).throw(refused))

    worker = cw.ClaudeWorker(messages=[], enforce_worker_policy=False)
    worker.tool_status = MagicMock()
    result = worker._execute_tool_block({
        "id": "tu_16", "name": "houdini_set_parm",
        "input": {"node": "/obj/geo1", "parm": "tx", "value": 1.0}})

    assert result["is_error"] is True
    payload = json.loads(result["content"])
    assert payload["error"] == str(refused)
    assert failure_receipt(payload) == _RECEIPT


def test_direct_tool_failure_carries_the_receipt(monkeypatch):
    from synapse.panel import direct_tool
    from synapse.panel import tool_executor

    refused = RuntimeError("the write was refused")
    refused.receipt = _RECEIPT
    monkeypatch.setattr(tool_executor, "try_mcp_tool_call",
                        lambda name, args: (_ for _ in ()).throw(refused))

    call = direct_tool.DirectToolCall("houdini_set_parm", {"node": "/obj/geo1"})
    emitted = []
    call.failed = SimpleNamespace(emit=emitted.append)
    call.run()

    assert len(emitted) == 1
    payload = json.loads(emitted[0])
    assert payload["error"] == str(refused)
    assert payload["receipt"] == _RECEIPT


def test_render_workspace_failure_carries_the_receipt():
    from qt_stub_window import qt_stub_window

    with qt_stub_window():
        sys.modules.pop("synapse.panel.render_workspace", None)
        import synapse.panel.render_workspace as rw

        refused = RuntimeError("the farm refused the job")
        refused.receipt = _RECEIPT

        def _transport(name, args):
            raise refused

        call = rw.FarmToolCall("synapse_farm_job", {}, transport=_transport)
        emitted = []
        call.failed = SimpleNamespace(emit=emitted.append)
        call.run()

    assert len(emitted) == 1
    payload = json.loads(emitted[0])
    assert payload["error"] == "the farm refused the job"
    assert payload["receipt"] == _RECEIPT


# ---------------------------------------------------------------------------
# 17. The fallback dispatch keeps the receipt (round 2.5, blocker 5)
# ---------------------------------------------------------------------------

class _FailingHandler:
    """A handler whose tool failed but whose payload carries the receipt."""

    def __init__(self, data=None, error="the write was refused"):
        self._data = data
        self._error = error
        self.calls = 0

    def handle(self, command):
        self.calls += 1
        return SimpleNamespace(success=False, data=self._data, error=self._error)


def _bridge_down_worker(monkeypatch, handler):
    """Wire the worker's off-main fallback so the fake handler is reached."""
    import synapse.panel.bridge_adapter as ba
    import synapse.panel.claude_worker as cw

    te = importlib.import_module("synapse.panel.tool_executor")
    monkeypatch.setattr(te, "get_tool_dispatch",
                        lambda name: ("set_parm", lambda inp: dict(inp)))
    monkeypatch.setattr(ba, "is_read_only", lambda name: True)
    # MCP unavailable -> the Qt/daemon-thread fallback dispatches the tool.
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)

    worker = cw.ClaudeWorker(messages=[], enforce_worker_policy=False)
    worker.tool_status = MagicMock()
    executor = worker._get_offmain_executor()
    monkeypatch.setattr(executor, "_get_handler", lambda: handler)
    return worker, executor, te


def test_fallback_dispatch_keeps_the_receipt_on_the_request(monkeypatch):
    handler = _FailingHandler(data={"receipt": _RECEIPT})
    worker, executor, te = _bridge_down_worker(monkeypatch, handler)

    request = te.ToolRequest(
        tool_use_id="tu_17", tool_name="houdini_set_parm",
        tool_input={"node": "/obj/geo1", "parm": "tx", "value": 1.0})
    executor._dispatch(request)

    assert request.error == "the write was refused"
    assert failure_receipt(request.failure) == _RECEIPT


def test_bridge_down_fallback_tool_result_carries_the_receipt(monkeypatch):
    """Probe: the failure branch returned only request.error."""
    handler = _FailingHandler(data={"receipt": _RECEIPT})
    worker, executor, te = _bridge_down_worker(monkeypatch, handler)

    result = worker._execute_tool_block({
        "id": "tu_18", "name": "houdini_set_parm",
        "input": {"node": "/obj/geo1", "parm": "tx", "value": 1.0}})

    assert handler.calls == 1
    assert result["is_error"] is True
    payload = json.loads(result["content"])
    assert payload["error"] == "the write was refused"
    assert failure_receipt(payload) == _RECEIPT


# ---------------------------------------------------------------------------
# 18. The autonomy receipt reads what executed (round 2.5, R2b)
# ---------------------------------------------------------------------------

def _check(name, passed, severity="hard_fail"):
    return SimpleNamespace(name=name, passed=passed,
                           severity=SimpleNamespace(value=severity))


def _capture_verification(monkeypatch):
    from synapse.memory import agent_state

    written = {}
    monkeypatch.setattr(agent_state, "update_task_status",
                        lambda usd, task, status: written.setdefault("status", status))
    monkeypatch.setattr(
        agent_state, "write_verification",
        lambda usd, task, before, after, checks, result: written.update(
            before_state=before, after_state=after, checks=checks,
            result=result))
    return written


def test_record_autonomy_task_reads_the_executed_checks(monkeypatch):
    """The declared checks never ran; the executed copy is the evidence."""
    from synapse.server import handlers

    written = _capture_verification(monkeypatch)
    declared = SimpleNamespace(validation_checks=[_check("camera", False),
                                                  _check("output", False)])
    executed = SimpleNamespace(validation_checks=[_check("camera", True)])
    report = SimpleNamespace(success=True, plan=declared, executed=executed,
                             evaluation=None)

    handlers.SynapseHandler._record_autonomy_task(
        "/tmp/agent.usd", "task-18", report)

    assert written["before_state"] == "checks=1 hard_fail=0"
    assert written["checks"] == ["camera:pass"]
    assert written["result"] == "pass"
    assert written["status"] == "completed"


def test_record_autonomy_task_falls_back_to_plan(monkeypatch):
    """A report shape that predates ``executed`` still records its checks."""
    from synapse.server import handlers

    written = _capture_verification(monkeypatch)
    declared = SimpleNamespace(validation_checks=[_check("camera", False),
                                                  _check("output", False)])
    report = SimpleNamespace(success=False, plan=declared, evaluation=None)

    handlers.SynapseHandler._record_autonomy_task(
        "/tmp/agent.usd", "task-18b", report)

    assert written["before_state"] == "checks=2 hard_fail=2"
    assert written["checks"] == ["camera:fail", "output:fail"]
    assert written["result"] == "fail"
    assert written["status"] == "failed"
