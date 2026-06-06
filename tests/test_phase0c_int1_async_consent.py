"""Phase 0c / INT-1: the consent wait on the FastMCP path must not block the loop.

execute_async() previously called the SYNC _check_consent, whose _wait_for_decision
busy-polls with blocking time.sleep -- a pending APPROVE/CRITICAL decision stalled the
whole event loop for up to the timeout (the S4 defect). INT-1 adds async mirrors
(_check_consent_async / _check_consent_gate_async / _wait_for_decision_async) that poll
with `await asyncio.sleep`, wired into execute_async. The sync execute() path is
unchanged.

Verified in stock CI: the async wait returns on approval, times out cleanly, and --
critically -- YIELDS the event loop while pending (a concurrent task keeps ticking).
The gate -> async-wait wiring is exercised via a fake proposal so no real 120s wait runs.
"""
import asyncio
import time

import pytest

import shared.bridge as b
from shared.bridge import LosslessExecutionBridge, Operation
from shared.types import AgentID


class _GD:  # stand-in for GateDecision
    PENDING = "pending"
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


def _op(op_type, agent=AgentID.SUBSTRATE):
    return Operation(agent_id=agent, operation_type=op_type, summary="t", fn=lambda: None)


@pytest.mark.asyncio
async def test_wait_async_returns_true_on_approval(monkeypatch):
    monkeypatch.setattr(b, "GateDecision", _GD)
    bridge = LosslessExecutionBridge()

    class P:
        decision = _GD.APPROVED

    assert await bridge._wait_for_decision_async(P(), timeout=5.0) is True


@pytest.mark.asyncio
async def test_wait_async_times_out_without_blocking_the_loop(monkeypatch):
    monkeypatch.setattr(b, "GateDecision", _GD)
    bridge = LosslessExecutionBridge()

    class P:
        decision = _GD.PENDING  # never decided -> must time out

    ticks = {"n": 0}

    async def ticker():
        for _ in range(40):
            await asyncio.sleep(0.02)
            ticks["n"] += 1

    t0 = time.monotonic()
    result, _ = await asyncio.gather(
        bridge._wait_for_decision_async(P(), timeout=0.6),
        ticker(),
    )
    assert result is False                  # PENDING + timeout -> reject (safe default)
    assert ticks["n"] >= 5, "concurrent task starved -> the wait BLOCKED the loop (S4)"
    assert time.monotonic() - t0 < 3.0      # returned near the timeout, no hang


@pytest.mark.asyncio
async def test_check_consent_async_inform_short_circuits():
    # INFORM never reaches the gate/wait -> True immediately (no _gate dependency).
    bridge = LosslessExecutionBridge()
    assert await bridge._check_consent_async(_op("read_network", AgentID.OBSERVER)) is True


@pytest.mark.asyncio
async def test_check_consent_gate_async_uses_async_wait(monkeypatch):
    # Exercise the gate -> async-wait path without a real HumanGate (which would
    # block the full 120s). A fake proposal returns APPROVED immediately.
    monkeypatch.setattr(b, "GateDecision", _GD)
    bridge = LosslessExecutionBridge()

    class P:
        decision = _GD.APPROVED

    monkeypatch.setattr(bridge, "_propose_gate", lambda op: P())
    assert await bridge._check_consent_gate_async(_op("execute_python")) is True  # CRITICAL
