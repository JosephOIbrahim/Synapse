"""Tests for AgentHandoff.verify() — cross-agent context transfer validation.

Covers:
- Fidelity < 1.0 rejection
- Failed source output rejection
- Missing required context keys per agent type
- Provenance chain extension
- Successful handoff for each agent
"""

import os
import sys

# Path setup
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)

from shared.types import AgentID, ExecutionResult
from shared.bridge import AgentHandoff, AGENT_CONTEXT_REQUIREMENTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_result(data="ok"):
    return ExecutionResult.ok(result=data, agent_id=AgentID.OBSERVER)


def _failed_result():
    return ExecutionResult.fail(error="boom", agent_id=AgentID.OBSERVER)


def _make_handoff(
    from_agent=AgentID.OBSERVER,
    to_agent=AgentID.HANDS,
    fidelity=1.0,
    source_output=None,
    context=None,
):
    if source_output is None:
        source_output = _ok_result()
    if context is None:
        # Default: satisfy HANDS requirement
        context = {"domain": "usd"}
    return AgentHandoff(
        from_agent=from_agent,
        to_agent=to_agent,
        task_id="test_task",
        source_output=source_output,
        source_fidelity=fidelity,
        context=context,
    )


# ---------------------------------------------------------------------------
# Fidelity gating
# ---------------------------------------------------------------------------

def test_verify_passes_at_fidelity_1():
    h = _make_handoff(fidelity=1.0)
    assert h.verify() is True


def test_verify_rejects_fidelity_below_1():
    h = _make_handoff(fidelity=0.99)
    assert h.verify() is False


def test_verify_rejects_fidelity_zero():
    h = _make_handoff(fidelity=0.0)
    assert h.verify() is False


def test_verify_rejects_fidelity_half():
    h = _make_handoff(fidelity=0.5)
    assert h.verify() is False


# ---------------------------------------------------------------------------
# Source output success gating
# ---------------------------------------------------------------------------

def test_verify_rejects_failed_source_output():
    h = _make_handoff(source_output=_failed_result())
    assert h.verify() is False


def test_verify_rejects_failed_even_with_fidelity_1():
    h = _make_handoff(source_output=_failed_result(), fidelity=1.0)
    assert h.verify() is False


# ---------------------------------------------------------------------------
# Context requirements per agent
# ---------------------------------------------------------------------------

def test_handoff_to_substrate_needs_operation_type():
    h = _make_handoff(to_agent=AgentID.SUBSTRATE, context={})
    assert h.verify() is False

    h2 = _make_handoff(
        to_agent=AgentID.SUBSTRATE,
        context={"operation_type": "create_node"},
    )
    assert h2.verify() is True


def test_handoff_to_brainstem_needs_node_path():
    h = _make_handoff(to_agent=AgentID.BRAINSTEM, context={})
    assert h.verify() is False

    h2 = _make_handoff(
        to_agent=AgentID.BRAINSTEM,
        context={"node_path": "/obj/geo1"},
    )
    assert h2.verify() is True


def test_handoff_to_observer_needs_network_path():
    h = _make_handoff(to_agent=AgentID.OBSERVER, context={})
    assert h.verify() is False

    h2 = _make_handoff(
        to_agent=AgentID.OBSERVER,
        context={"network_path": "/obj"},
    )
    assert h2.verify() is True


def test_handoff_to_hands_needs_domain():
    h = _make_handoff(to_agent=AgentID.HANDS, context={})
    assert h.verify() is False

    h2 = _make_handoff(
        to_agent=AgentID.HANDS,
        context={"domain": "materialx"},
    )
    assert h2.verify() is True


def test_handoff_to_conductor_needs_nothing():
    """CONDUCTOR has no required context keys."""
    h = _make_handoff(to_agent=AgentID.CONDUCTOR, context={})
    assert h.verify() is True


def test_handoff_to_integrator_needs_files_touched():
    h = _make_handoff(to_agent=AgentID.INTEGRATOR, context={})
    assert h.verify() is False

    h2 = _make_handoff(
        to_agent=AgentID.INTEGRATOR,
        context={"files_touched": ["shared/types.py"]},
    )
    assert h2.verify() is True


# ---------------------------------------------------------------------------
# Extra context keys are fine
# ---------------------------------------------------------------------------

def test_extra_context_keys_do_not_break_verify():
    h = _make_handoff(
        to_agent=AgentID.HANDS,
        context={"domain": "usd", "extra": "data", "more": 42},
    )
    assert h.verify() is True


# ---------------------------------------------------------------------------
# Provenance chain
# ---------------------------------------------------------------------------

def test_provenance_starts_empty():
    h = _make_handoff()
    assert h.provenance == []


def test_extend_provenance_appends():
    h = _make_handoff()
    h.extend_provenance(AgentID.OBSERVER, "scanned /obj")
    assert len(h.provenance) == 1
    assert h.provenance[0] == ("OBSERVER", "scanned /obj")


def test_extend_provenance_chains():
    h = _make_handoff()
    h.extend_provenance(AgentID.OBSERVER, "step 1")
    h.extend_provenance(AgentID.HANDS, "step 2")
    h.extend_provenance(AgentID.INTEGRATOR, "step 3")
    assert len(h.provenance) == 3
    assert h.provenance[0][0] == "OBSERVER"
    assert h.provenance[1][0] == "HANDS"
    assert h.provenance[2][0] == "INTEGRATOR"


def test_provenance_preserves_order():
    h = _make_handoff()
    agents = [AgentID.SUBSTRATE, AgentID.BRAINSTEM, AgentID.OBSERVER,
              AgentID.HANDS, AgentID.CONDUCTOR, AgentID.INTEGRATOR]
    for i, a in enumerate(agents):
        h.extend_provenance(a, f"step_{i}")
    assert [p[0] for p in h.provenance] == [a.value for a in agents]


# ---------------------------------------------------------------------------
# Context requirements registry completeness
# ---------------------------------------------------------------------------

def test_all_agents_have_context_requirements():
    """Every AgentID must have an entry in AGENT_CONTEXT_REQUIREMENTS."""
    for agent in AgentID:
        assert agent in AGENT_CONTEXT_REQUIREMENTS, (
            f"{agent.value} missing from AGENT_CONTEXT_REQUIREMENTS"
        )
