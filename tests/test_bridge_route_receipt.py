"""The write receipt survives the execution bridge on the in-Houdini /mcp route.

A mutating tool such as ``houdini_set_parm`` reaches its handler through
``panel.bridge_adapter.execute_through_bridge``. When the handler reports a
refusal or a failure, ``LosslessExecutionBridge.execute`` (shared/bridge.py,
the ``getattr(result, "success", None) is False`` arm) turns it into
``_fail_with_integrity(...)``, which returns ``ExecutionResult.fail(...)``
with an integrity block and DROPS the handler's response. The adapter then
rebuilt the reply as ``data={"_integrity": ...}`` only, so the structured
write receipt the handler attached never reached the caller - on /mcp, and
so on the panel, whose executor calls /mcp.

The receipt tests in tests/test_parm_write_receipt.py patch ``is_read_only``
to True, which skips the bridge, so they could not see this.

The fake bridge here does what the real one does on that arm, in the same
order: it calls the operation's function, sees ``success is False``, and
returns ``ExecutionResult.fail(error, "execution_error").with_integrity(block)``
- the exact value ``_fail_with_integrity`` builds (minus its log append).
"""
from __future__ import annotations

import pytest

pytest.importorskip("shared.bridge")

from shared.bridge import IntegrityBlock  # noqa: E402
from shared.types import ExecutionResult  # noqa: E402

from synapse.core.protocol import SynapseCommand, SynapseResponse  # noqa: E402
from synapse.core.tool_results import failure_receipt  # noqa: E402
from synapse.panel import bridge_adapter  # noqa: E402

_RECEIPT = {
    "write": "not_attempted",
    "code": "parm.precondition_invalid",
    "node": "/obj/geo1",
    "parm": "tx",
    "request_id": "req-bridge-1",
}


class _FailingHandler:
    """A handler whose failure arm carries a receipt, as handlers.py does."""

    def __init__(self, data):
        self.calls = 0
        self._data = data

    def handle(self, command):
        self.calls += 1
        return SynapseResponse(id=command.id, success=False,
                               error="parm.precondition_invalid: cannot check",
                               data=self._data)


class _BridgeFailsLikeTheRealOne:
    """Mirror of LosslessExecutionBridge.execute on a handler-reported failure."""

    def __init__(self, call_fn=True):
        self.call_fn = call_fn

    def execute(self, op):
        if not self.call_fn:
            # A failure the bridge raises itself, before the handler runs
            # (consent, an anchor, the marshal): there is no handler response.
            return ExecutionResult.fail(
                error="consent denied", error_type="consent_denied",
            ).with_integrity(IntegrityBlock())
        result = op.fn(*op.args, **op.kwargs)
        if getattr(result, "success", None) is False:
            return ExecutionResult.fail(
                error=getattr(result, "error", None) or "The handler reported failure",
                error_type="execution_error",
            ).with_integrity(IntegrityBlock())
        return ExecutionResult.ok(result=result).with_integrity(IntegrityBlock())


def _command():
    return SynapseCommand(type="set_parm", id="c1",
                          payload={"node": "/obj/geo1", "parm": "tx", "value": 5.0})


def test_a_refused_write_keeps_its_receipt_through_the_bridge(monkeypatch):
    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: _BridgeFailsLikeTheRealOne())
    handler = _FailingHandler({"receipt": dict(_RECEIPT)})

    response = bridge_adapter.execute_through_bridge("houdini_set_parm", handler, _command())

    assert handler.calls == 1
    assert response.success is False
    assert response.data["receipt"] == _RECEIPT
    assert "_integrity" in response.data
    assert failure_receipt(response.data) == _RECEIPT


def test_the_mcp_dispatch_carries_the_receipt_through_the_bridge(monkeypatch):
    from synapse.mcp import tools

    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: _BridgeFailsLikeTheRealOne())
    assert bridge_adapter.is_read_only("houdini_set_parm") is False
    handler = _FailingHandler({"receipt": dict(_RECEIPT)})

    result = tools.dispatch_tool(handler, "houdini_set_parm",
                                 {"node": "/obj/geo1", "parm": "tx", "value": 5.0})

    assert handler.calls == 1
    assert result["isError"] is True
    assert result["structuredContent"]["receipt"] == _RECEIPT
    assert failure_receipt(result) == _RECEIPT


def test_a_failure_without_a_receipt_keeps_the_old_shape(monkeypatch):
    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: _BridgeFailsLikeTheRealOne())
    handler = _FailingHandler(None)

    response = bridge_adapter.execute_through_bridge("houdini_set_parm", handler, _command())

    assert response.success is False
    assert set(response.data) == {"_integrity"}


def test_a_non_dict_receipt_is_not_carried(monkeypatch):
    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: _BridgeFailsLikeTheRealOne())
    handler = _FailingHandler({"receipt": "not a receipt"})

    response = bridge_adapter.execute_through_bridge("houdini_set_parm", handler, _command())

    assert set(response.data) == {"_integrity"}


def test_a_bridge_failure_before_the_handler_invents_no_receipt(monkeypatch):
    monkeypatch.setattr(bridge_adapter, "get_bridge",
                        lambda: _BridgeFailsLikeTheRealOne(call_fn=False))
    handler = _FailingHandler({"receipt": dict(_RECEIPT)})

    response = bridge_adapter.execute_through_bridge("houdini_set_parm", handler, _command())

    assert handler.calls == 0
    assert response.success is False
    assert set(response.data) == {"_integrity"}
    assert response.error.startswith("Bridge: ")


class _SucceedingHandler:
    """A handler whose write landed: its receipt says write=applied."""

    def __init__(self):
        self.calls = 0

    def handle(self, command):
        self.calls += 1
        return SynapseResponse(id=command.id, success=True,
                               data={"receipt": {"write": "applied",
                                                 "readback": "match"}})


class _BridgeFailsAfterTheHandler:
    """The bridge fails an op the handler completed (a composition violation
    that rolls the write back, or a fidelity failure): shared/bridge.py's
    except arm and _finalize both return ExecutionResult.fail after fn ran."""

    def execute(self, op):
        op.fn(*op.args, **op.kwargs)
        return ExecutionResult.fail(
            error="composition violation; rolled back",
            error_type="composition_invalid",
        ).with_integrity(IntegrityBlock())


def test_a_completed_write_the_bridge_failed_carries_no_applied_receipt(monkeypatch):
    monkeypatch.setattr(bridge_adapter, "get_bridge", lambda: _BridgeFailsAfterTheHandler())
    handler = _SucceedingHandler()

    response = bridge_adapter.execute_through_bridge("houdini_set_parm", handler, _command())

    assert handler.calls == 1
    assert response.success is False
    # The handler's receipt says the write landed; the bridge failed (and may
    # have undone) it. Repeating "applied" on a failure reply would be false.
    assert "receipt" not in response.data
    assert set(response.data) == {"_integrity"}
