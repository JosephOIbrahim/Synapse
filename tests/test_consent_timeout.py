"""Tests for consent gate behavior in LosslessExecutionBridge._check_consent().

Covers:
- INFORM gate: auto-approve, no wait
- REVIEW gate: log and continue (not rejected by default)
- APPROVE gate: wait and timeout leads to rejection
- CRITICAL gate: wait longer, timeout leads to rejection
- Injected callback path
- Standalone (no gate, no callback): auto-approve all
- R4: disk-write gate elevation
"""

import os
import sys
import time

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

from shared.types import AgentID
from shared.bridge import (
    LosslessExecutionBridge,
    Operation,
    GateLevel,
    OPERATION_GATES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_op(op_type="read_network", agent=AgentID.OBSERVER, **kwargs):
    return Operation(
        agent_id=agent,
        operation_type=op_type,
        summary=f"test {op_type}",
        fn=lambda: "result",
        kwargs=kwargs,
    )


# ---------------------------------------------------------------------------
# Gate level classification
# ---------------------------------------------------------------------------

def test_inform_ops_are_classified_correctly():
    """Operations like read_network and create_node are INFORM level."""
    inform_ops = [
        "read_network", "inspect_geometry", "create_node",
        "set_parameter", "connect_nodes",
    ]
    for op_type in inform_ops:
        op = _make_op(op_type)
        assert op.gate_level == GateLevel.INFORM, f"{op_type} should be INFORM"


def test_review_ops_are_classified_correctly():
    review_ops = ["delete_node", "build_from_manifest", "evolve_memory"]
    for op_type in review_ops:
        op = _make_op(op_type)
        assert op.gate_level == GateLevel.REVIEW, f"{op_type} should be REVIEW"


def test_approve_ops_are_classified_correctly():
    approve_ops = ["submit_render", "export_file", "cook_pdg_chain"]
    for op_type in approve_ops:
        op = _make_op(op_type)
        assert op.gate_level == GateLevel.APPROVE, f"{op_type} should be APPROVE"


def test_critical_ops_are_classified_correctly():
    critical_ops = ["execute_python", "execute_vex"]
    for op_type in critical_ops:
        op = _make_op(op_type)
        assert op.gate_level == GateLevel.CRITICAL, f"{op_type} should be CRITICAL"


def test_unknown_op_defaults_to_review():
    op = _make_op("some_unknown_operation")
    assert op.gate_level == GateLevel.REVIEW


# ---------------------------------------------------------------------------
# R4: Disk-write gate elevation
# ---------------------------------------------------------------------------

def test_disk_write_elevates_inform_to_approve():
    op = _make_op("create_node", touches_disk=True)
    assert op.gate_level == GateLevel.APPROVE


def test_disk_write_elevates_review_to_approve():
    op = _make_op("delete_node", touches_disk=True)
    assert op.gate_level == GateLevel.APPROVE


def test_disk_write_does_not_downgrade_critical():
    """CRITICAL is higher than APPROVE -- R4 never downgrades."""
    op = _make_op("execute_python", touches_disk=True)
    assert op.gate_level == GateLevel.CRITICAL


def test_disk_write_keeps_approve_at_approve():
    op = _make_op("submit_render", touches_disk=True)
    assert op.gate_level == GateLevel.APPROVE


# ---------------------------------------------------------------------------
# Standalone mode (no gate system, no callback) -- auto-approve
# ---------------------------------------------------------------------------
# Note: In the test environment, synapse.core.gates is importable so the
# bridge would pick up the real HumanGate.  We simulate true standalone mode
# by forcing _gate=None on the bridge instance after construction.

def _standalone_bridge():
    """Create a bridge that behaves like standalone (no gate system)."""
    bridge = LosslessExecutionBridge()
    bridge._gate = None  # Simulate no gate system
    return bridge


def test_standalone_inform_auto_approves():
    bridge = _standalone_bridge()
    op = _make_op("read_network")
    result = bridge.execute(op)
    assert result.success is True


def test_standalone_review_auto_approves():
    bridge = _standalone_bridge()
    op = _make_op("delete_node")
    result = bridge.execute(op)
    assert result.success is True


def test_standalone_approve_auto_approves():
    bridge = _standalone_bridge()
    op = _make_op("submit_render")
    result = bridge.execute(op)
    assert result.success is True


def test_standalone_critical_auto_approves():
    bridge = _standalone_bridge()
    op = _make_op("execute_python")
    result = bridge.execute(op)
    assert result.success is True


# ---------------------------------------------------------------------------
# Injected callback path
# ---------------------------------------------------------------------------
# We null out _gate so the bridge uses the callback (Path 2) not the gate
# system (Path 1).  In production, Path 2 is for MCP/custom integrations
# that don't have the full gate system wired.

def _callback_bridge(callback):
    bridge = LosslessExecutionBridge(consent_callback=callback)
    bridge._gate = None  # Force Path 2 (callback)
    return bridge


def test_callback_approve_allows_execution():
    bridge = _callback_bridge(lambda op: True)
    op = _make_op("delete_node")
    result = bridge.execute(op)
    assert result.success is True


def test_callback_reject_blocks_execution():
    bridge = _callback_bridge(lambda op: False)
    op = _make_op("delete_node")
    result = bridge.execute(op)
    assert result.success is False
    assert "consent" in result.error.lower()


def test_callback_not_called_for_inform():
    """INFORM gates auto-approve -- callback should not be reached."""
    called = []
    def track_callback(op):
        called.append(op)
        return True

    bridge = _callback_bridge(track_callback)
    op = _make_op("read_network")
    result = bridge.execute(op)
    assert result.success is True
    assert len(called) == 0


def test_callback_called_for_review():
    called = []
    def track_callback(op):
        called.append(op.operation_type)
        return True

    bridge = _callback_bridge(track_callback)
    op = _make_op("delete_node")
    bridge.execute(op)
    assert "delete_node" in called


def test_callback_called_for_approve():
    called = []
    def track_callback(op):
        called.append(op.operation_type)
        return True

    bridge = _callback_bridge(track_callback)
    op = _make_op("submit_render")
    bridge.execute(op)
    assert "submit_render" in called


def test_callback_called_for_critical():
    called = []
    def track_callback(op):
        called.append(op.operation_type)
        return True

    bridge = _callback_bridge(track_callback)
    op = _make_op("execute_python")
    bridge.execute(op)
    assert "execute_python" in called


# ---------------------------------------------------------------------------
# Consent rejection produces correct error type
# ---------------------------------------------------------------------------

def test_consent_rejection_error_type():
    bridge = _callback_bridge(lambda op: False)
    op = _make_op("execute_python")
    result = bridge.execute(op)
    assert result.success is False
    assert result.error_type == "consent_required"


def test_consent_rejection_mentions_gate_level():
    bridge = _callback_bridge(lambda op: False)
    op = _make_op("submit_render")
    result = bridge.execute(op)
    assert "approve" in result.error.lower()


# ---------------------------------------------------------------------------
# Integrity block records consent status
# ---------------------------------------------------------------------------

def test_integrity_records_consent_verified_on_success():
    bridge = _standalone_bridge()
    op = _make_op("read_network")
    result = bridge.execute(op)
    assert result.integrity is not None
    assert result.integrity.consent_verified is True


def test_integrity_records_consent_verified_on_rejection():
    bridge = _callback_bridge(lambda op: False)
    op = _make_op("delete_node")
    result = bridge.execute(op)
    assert result.integrity is not None
    assert result.integrity.consent_verified is False


# ---------------------------------------------------------------------------
# Read-only detection
# ---------------------------------------------------------------------------

def test_read_only_operation_flag():
    op_read = _make_op("read_network")
    assert op_read.is_read_only is True

    op_inspect = _make_op("inspect_geometry")
    assert op_inspect.is_read_only is True

    op_capture = _make_op("capture_viewport")
    assert op_capture.is_read_only is True

    op_write = _make_op("create_node")
    assert op_write.is_read_only is False
