"""FU-2 — AP6: the destructive Moneta op (run_sleep_pass) is APPROVE-gated.

`add` stays INFORM (unchanged); only `run_sleep_pass` — which permanently
prunes unprotected memories — routes through the bridge at APPROVE, like
`prune_memory`. The gate fires in execute_through_bridge (tool -> op mapping)
before the handler runs. Standalone auto-approves so CI stays green.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))
sys.path.insert(0, str(_ROOT))

from shared.bridge import GateLevel, LosslessExecutionBridge, Operation  # noqa: E402
from shared.constants import OPERATION_GATES  # noqa: E402
from shared.types import AgentID  # noqa: E402


def _sleep_op(fn):
    return Operation(
        agent_id=AgentID.CONDUCTOR,
        operation_type="sleep_pass",
        summary="Moneta run_sleep_pass (prune unprotected)",
        fn=fn,
    )


# --- the wiring that makes the gate fire -----------------------------------

def test_sleep_pass_constant_is_approve():
    assert OPERATION_GATES["sleep_pass"] == "approve"


def test_sleep_pass_operation_gate_level_is_approve():
    assert _sleep_op(lambda: None).gate_level == GateLevel.APPROVE


def test_tool_maps_to_sleep_pass_operation():
    from synapse.panel.bridge_adapter import _TOOL_TO_OPERATION
    assert _TOOL_TO_OPERATION["synapse_sleep_pass"] == "sleep_pass"
    # And it must NOT be treated as read-only (else it skips the gate).
    from synapse.panel.bridge_adapter import is_read_only
    assert is_read_only("synapse_sleep_pass") is False


# --- the gate actually blocks / auto-approves ------------------------------

def test_rejecting_gate_blocks_the_prune():
    ran = {"n": 0}
    bridge = LosslessExecutionBridge(consent_callback=lambda op: False)
    bridge._gate = None  # force the injected callback (Path 2), not a real gate
    result = bridge.execute(_sleep_op(lambda: ran.__setitem__("n", ran["n"] + 1)))
    assert ran["n"] == 0          # destructive op never executed
    assert not result.success


def test_standalone_auto_approves():
    ran = {"n": 0}
    bridge = LosslessExecutionBridge()  # no callback
    bridge._gate = None                 # no real gate -> Path 3 auto-approve
    result = bridge.execute(_sleep_op(lambda: ran.__setitem__("n", ran["n"] + 1) or {"ok": True}))
    assert ran["n"] == 1
    assert result.success


# --- the handler behavior --------------------------------------------------

def _handler():
    from synapse.server import handlers as handlers_mod
    return handlers_mod.SynapseHandler()


def test_handler_noop_when_not_moneta_backed(monkeypatch):
    h = _handler()
    # A non-Moneta store has no run_sleep_pass -> handler is a safe no-op.
    fake_store = SimpleNamespace(count=lambda: 5)
    monkeypatch.setattr(h, "_get_bridge", lambda: SimpleNamespace(_synapse=SimpleNamespace(store=fake_store)))
    out = h._handle_sleep_pass({})
    assert out["ran"] is False
    assert "not Moneta-backed" in out["reason"]


def test_handler_returns_audit_when_moneta_backed(monkeypatch):
    from synapse.memory import moneta_runtime as mr
    if not mr.moneta_available():
        pytest.skip("Moneta not importable")
    from synapse.memory.moneta_store import MonetaBackedStore
    from synapse.memory.embedding import HashEmbedder
    from synapse.memory.models import Memory, MemoryType

    store = MonetaBackedStore(mr.make_ephemeral(embedding_dim=64), HashEmbedder(dim=64))
    store.add(Memory(content="Decision: keep me", memory_type=MemoryType.DECISION))

    h = _handler()
    monkeypatch.setattr(h, "_get_bridge", lambda: SimpleNamespace(_synapse=SimpleNamespace(store=store)))
    out = h._handle_sleep_pass({})
    assert out["ran"] is True
    assert out["pruned"] == 0           # protected decision survives
    assert out["before"] == out["after"] == 1
    assert out["pruned_ids"] == []
