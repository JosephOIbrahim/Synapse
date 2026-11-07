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
