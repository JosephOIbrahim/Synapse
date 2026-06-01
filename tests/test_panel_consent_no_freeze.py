"""Regression guard for the "Houdini (Not Responding)" freeze.

Confirmed live (2026-06-01): "make a box" routed through houdini_execute_python
(a CRITICAL gate). My PYTHONPATH fix had just activated the LosslessExecution
bridge, so consent ran HumanGate's _wait_for_decision — a time.sleep poll — on
the GUI/main thread, waiting for an approval card that only the GUI thread can
draw. Deadlock. Houdini froze.

The panel bridge now resolves consent through a non-blocking callback
(bridge_adapter._panel_consent): artist-initiated panel ops are pre-consented
and NEVER enter the blocking poll. These tests fail loud if that ever regresses
(e.g. the bridge starts using HumanGate on the panel singleton again).

Pure logic — no Qt, no hou; runs under stock pytest.
"""

import pytest

from synapse.panel import bridge_adapter as ba
from shared.bridge import Operation, GateLevel
from shared.types import AgentID


@pytest.fixture(autouse=True)
def _fresh_bridge():
    ba._bridge = None
    yield
    ba._bridge = None


def test_panel_bridge_uses_nonblocking_consent():
    bridge = ba.get_bridge()
    assert bridge is not None
    # The blocking HumanGate must be OFF on the panel's bridge...
    assert bridge._gate is None, "panel bridge must not use the GUI-freezing HumanGate"
    # ...and the non-blocking artist-consent callback must be wired.
    assert bridge._consent_callback is ba._panel_consent


def test_critical_op_never_enters_the_blocking_poll(monkeypatch):
    bridge = ba.get_bridge()

    # If consent EVER reaches _wait_for_decision, it would time.sleep-poll the
    # calling thread (the GUI thread in production) -> the freeze. Make that loud.
    def _boom(*a, **k):
        raise AssertionError(
            "_wait_for_decision reached — this is the GUI-freezing poll"
        )
    monkeypatch.setattr(type(bridge), "_wait_for_decision", _boom)

    ran = {}
    op = Operation(
        agent_id=AgentID.BRAINSTEM,
        operation_type="execute_python",   # the exact CRITICAL op that froze us
        summary="make a box",
        fn=lambda **k: (ran.update(ok=True) or {"ok": True}),
        kwargs={},
    )
    # Confirm we're testing the genuinely dangerous gate, not a soft one.
    assert op.gate_level == GateLevel.CRITICAL

    result = bridge.execute(op)

    assert result.success, "CRITICAL op should be allowed via the panel callback"
    assert ran.get("ok") is True, "the operation body must actually run"
