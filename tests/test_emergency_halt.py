"""Tests for EmergencyProtocol.trigger_emergency_halt().

Covers:
- Report structure and required fields
- Emergency reason propagation
- Session report inclusion
- Behavior without Houdini (standalone/test mode)
- Bridge state after halt
"""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

from shared.types import AgentID, ExecutionResult
from shared.bridge import (
    EmergencyProtocol,
    LosslessExecutionBridge,
    Operation,
    GateLevel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bridge(**kwargs):
    bridge = LosslessExecutionBridge(**kwargs)
    bridge._gate = None  # Force standalone mode (no real gate polling)
    return bridge


def _noop_op(agent=AgentID.OBSERVER, op_type="read_network"):
    return Operation(
        agent_id=agent,
        operation_type=op_type,
        summary="test op",
        fn=lambda: "ok",
    )


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------

def test_halt_returns_dict():
    bridge = _make_bridge()
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "test reason")
    assert isinstance(report, dict)


def test_halt_includes_emergency_reason():
    bridge = _make_bridge()
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "fidelity dropped to 0")
    assert report["emergency_reason"] == "fidelity dropped to 0"


def test_halt_includes_timestamp():
    bridge = _make_bridge()
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "crash")
    assert "emergency_timestamp" in report
    # ISO format contains 'T' separator
    assert "T" in report["emergency_timestamp"]


def test_halt_includes_action():
    bridge = _make_bridge()
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "test")
    assert report["action"] == "ALL_OPERATIONS_HALTED"


def test_halt_includes_session_report_fields():
    bridge = _make_bridge()
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "test")
    # Should include all session_report() keys
    assert "operations_total" in report
    assert "operations_verified" in report
    assert "anchor_violations" in report
    assert "session_fidelity" in report


# ---------------------------------------------------------------------------
# Session state in report
# ---------------------------------------------------------------------------

def test_halt_reflects_operations_count():
    bridge = _make_bridge()
    # Run a couple of operations first
    bridge.execute(_noop_op())
    bridge.execute(_noop_op())
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "test")
    assert report["operations_total"] == 2


def test_halt_on_fresh_bridge():
    bridge = _make_bridge()
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "preemptive")
    assert report["operations_total"] == 0
    assert report["session_fidelity"] == 1.0


# ---------------------------------------------------------------------------
# Multiple halts
# ---------------------------------------------------------------------------

def test_halt_can_be_called_multiple_times():
    """Emergency halt is idempotent -- calling it twice doesn't crash."""
    bridge = _make_bridge()
    r1 = EmergencyProtocol.trigger_emergency_halt(bridge, "first")
    r2 = EmergencyProtocol.trigger_emergency_halt(bridge, "second")
    assert r1["emergency_reason"] == "first"
    assert r2["emergency_reason"] == "second"


# ---------------------------------------------------------------------------
# Different reason strings
# ---------------------------------------------------------------------------

def test_halt_with_empty_reason():
    bridge = _make_bridge()
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "")
    assert report["emergency_reason"] == ""


def test_halt_with_long_reason():
    bridge = _make_bridge()
    reason = "x" * 5000
    report = EmergencyProtocol.trigger_emergency_halt(bridge, reason)
    assert report["emergency_reason"] == reason


# ---------------------------------------------------------------------------
# Houdini-unavailable path (standalone/test)
# ---------------------------------------------------------------------------

def test_halt_without_houdini_succeeds():
    """In test mode (no hou), halt still produces a valid report."""
    bridge = _make_bridge()
    report = EmergencyProtocol.trigger_emergency_halt(bridge, "no hou")
    assert report["houdini_available"] is False
    assert report["action"] == "ALL_OPERATIONS_HALTED"


# ---------------------------------------------------------------------------
# Bridge operations after halt
# ---------------------------------------------------------------------------

def test_bridge_still_usable_after_halt():
    """Emergency halt doesn't corrupt the bridge -- you can still run ops.

    In a real system, dispatches would be cancelled externally.
    The bridge itself remains structurally sound.
    """
    bridge = _make_bridge()
    EmergencyProtocol.trigger_emergency_halt(bridge, "test")
    # Bridge should still function
    result = bridge.execute(_noop_op())
    assert result.success is True
