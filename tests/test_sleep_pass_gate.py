"""FU-2 — AP6: the destructive Moneta op (run_sleep_pass) is APPROVE-gated.

`add` stays INFORM (unchanged); only `run_sleep_pass` — which permanently
prunes unprotected memories — is classified APPROVE, like `prune_memory`. The
classification still applies in execute_through_bridge (tool -> op mapping)
before the handler runs. Standalone auto-approves so CI stays green.

PIN MOVED (D4, 2026-10-18). This file used to rely on the handler wrapping
the prune in an APPROVE `sleep_pass` Operation and running it through
`bridge.execute()`. That pin is retargeted, not dropped, for two reasons:

1. The APPROVE class never blocked in production. The process bridge is built
   auto-approve with its gate nulled (CLAUDE.md 1.2.1), so the class alone
   gated nothing. The handler now carries the gate that holds: it refuses
   unless SYNAPSE_ALLOW_SLEEP_PASS is exactly "1" in the process environment.
2. FM11. Inside `bridge.execute()` the scene-free pass ran in an undo group
   whose rollback could `performUndo` the artist's last edit, and an off-main
   pass that had already pruned scored fidelity 0 and was answered ran=False.

So the handler tests below opt in explicitly, and
`test_handler_gate_holds_and_the_prune_runs_outside_bridge_execute` pins the
new shape: refused by default, and once opted in the prune runs directly,
never inside `bridge.execute()`. The bridge-level APPROVE tests stay as they
were: the class and its consent mechanics are unchanged.
tests/test_sleep_pass_consent.py holds the full D4 contract.
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


def test_handler_gate_holds_and_the_prune_runs_outside_bridge_execute(monkeypatch):
    """The retargeted pin (see the module docstring for why it moved)."""
    import shared.bridge as bridge_mod
    from synapse.server import integrity_envelope

    entered = []

    def _execute_must_not_run(self, operation):
        entered.append(operation.operation_type)
        raise AssertionError("the sleep pass went through bridge.execute()")

    monkeypatch.setattr(bridge_mod.LosslessExecutionBridge, "execute", _execute_must_not_run)
    recorded = []
    monkeypatch.setattr(
        integrity_envelope, "get_process_bridge",
        lambda: SimpleNamespace(record_external_block=recorded.append),
    )
    calls = {"n": 0}

    def _prune():
        calls["n"] += 1
        return SimpleNamespace(pruned=0, pruned_ids=[], staged=0)

    fake_store = SimpleNamespace(count=lambda: 2, run_sleep_pass=_prune)
    h = _handler()
    monkeypatch.setattr(h, "_get_bridge", lambda: SimpleNamespace(_synapse=SimpleNamespace(store=fake_store)))

    # Not opted in: refused, nothing pruned.
    monkeypatch.delenv("SYNAPSE_ALLOW_SLEEP_PASS", raising=False)
    out = h._handle_sleep_pass({})
    assert out["ran"] is False and out["refused"] is True
    assert calls["n"] == 0

    # Opted in: the prune runs once, directly, and leaves an observe-only block.
    monkeypatch.setenv("SYNAPSE_ALLOW_SLEEP_PASS", "1")
    out = h._handle_sleep_pass({})
    assert out["ran"] is True
    assert calls["n"] == 1
    assert entered == []
    assert [b.operation_type for b in recorded] == ["sleep_pass"]
    assert recorded[0].execution_path == "live"
    assert recorded[0].undo_applicable is False and recorded[0].consent_applicable is False


def test_handler_noop_when_not_moneta_backed(monkeypatch):
    # Opt in: the D4 environment check runs first, so without it this test
    # would only see the refusal and stop pinning the backend no-op behind it.
    monkeypatch.setenv("SYNAPSE_ALLOW_SLEEP_PASS", "1")
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

    # Opt in explicitly: since D4 the handler refuses unless the process
    # environment holds exactly "1", and this test pins the audit of a pass
    # that ran, not the refusal.
    monkeypatch.setenv("SYNAPSE_ALLOW_SLEEP_PASS", "1")
    # Keep the observe-only block out of the process-wide bridge trail.
    from synapse.server import integrity_envelope
    monkeypatch.setattr(
        integrity_envelope, "get_process_bridge",
        lambda: SimpleNamespace(record_external_block=lambda block: None),
    )
    h = _handler()
    monkeypatch.setattr(h, "_get_bridge", lambda: SimpleNamespace(_synapse=SimpleNamespace(store=store)))
    out = h._handle_sleep_pass({})
    assert out["ran"] is True
    assert out["pruned"] == 0           # protected decision survives
    assert out["before"] == out["after"] == 1
    assert out["pruned_ids"] == []
