"""
Synapse Agent Layer Tests

Tests for the protocol models — the surviving half of `synapse/agent/`.

The executor tests were removed on 2026-08-01 with the mechanism they
covered: `AgentExecutor` (`synapse/agent/executor.py`) was deleted when the
`RL-3` escalation from RSI loop `A2`'s retirement was ruled — it had zero
production constructions. The four v8-DSA modules and their dedicated test
files went in the same cut. `TestDeletedAgentSubsystemStaysDeleted` below
pins the subtraction, so a revival has to be deliberate rather than
accidental (and per the `A2` tombstone: a production construction site
comes first).

Run without Houdini:
    python -m pytest tests/test_agent.py -v
"""

import sys
import os
import importlib

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.protocol import SynapseCommand
from synapse.core.gates import GateLevel
from synapse.core.audit import AuditCategory

from synapse.agent.protocol import (
    AgentStep,
    AgentTask,
    AgentPlan,
    StepStatus,
    PlanStatus,
    DEFAULT_GATE_LEVELS,
    classify_gate_level,
)


# =============================================================================
# HELPERS
# =============================================================================

def _make_step(action="create_node", description="Create a node", **kwargs):
    """Helper to create a basic AgentStep."""
    defaults = {
        "step_id": "",
        "action": action,
        "description": description,
        "payload": {"type": "hlight", "path": "/obj/key"},
        "gate_level": None,
        "reasoning": "Test step",
    }
    defaults.update(kwargs)
    return AgentStep(**defaults)


def _make_task(goal="Set up lighting", **kwargs):
    """Helper to create a basic AgentTask."""
    defaults = {
        "task_id": "",
        "goal": goal,
        "sequence_id": "shot_010",
        "category": AuditCategory.LIGHTING,
    }
    defaults.update(kwargs)
    return AgentTask(**defaults)


# =============================================================================
# PROTOCOL TESTS — AgentStep
# =============================================================================

class TestAgentStep:
    """Tests for AgentStep data model."""

    def test_creation_generates_id(self):
        step = _make_step()
        assert step.step_id != ""
        assert len(step.step_id) == 16  # deterministic_uuid output

    def test_creation_with_explicit_id(self):
        step = _make_step(step_id="my_step_id")
        assert step.step_id == "my_step_id"

    def test_default_status_is_pending(self):
        step = _make_step()
        assert step.status == StepStatus.PENDING

    def test_to_command_produces_synapse_command(self):
        step = _make_step(action="set_parm", payload={"node": "/obj/key", "parm": "intensity", "value": 1.0})
        cmd = step.to_command()
        assert isinstance(cmd, SynapseCommand)
        assert cmd.type == "set_parm"
        assert cmd.payload["node"] == "/obj/key"
        assert cmd.payload["parm"] == "intensity"
        assert cmd.payload["value"] == 1.0

    def test_to_command_has_deterministic_id(self):
        step = _make_step(step_id="fixed_id")
        cmd1 = step.to_command()
        cmd2 = step.to_command()
        assert cmd1.id == cmd2.id

    def test_to_dict_from_dict_roundtrip(self):
        step = _make_step(
            confidence=0.85,
            gate_level=GateLevel.REVIEW,
        )
        step.status = StepStatus.COMPLETED
        step.observation = {"result": "ok"}
        step.duration_ms = 42.5

        data = step.to_dict()
        restored = AgentStep.from_dict(data)

        assert restored.step_id == step.step_id
        assert restored.action == step.action
        assert restored.description == step.description
        assert restored.payload == step.payload
        assert restored.gate_level == GateLevel.REVIEW
        assert restored.confidence == 0.85
        assert restored.status == StepStatus.COMPLETED
        assert restored.observation == {"result": "ok"}
        assert restored.duration_ms == 42.5

    def test_from_dict_with_null_gate_level(self):
        data = {
            "step_id": "test",
            "action": "ping",
            "description": "Ping",
            "payload": {},
            "gate_level": None,
            "reasoning": "Check connectivity",
        }
        step = AgentStep.from_dict(data)
        assert step.gate_level is None


# =============================================================================
# PROTOCOL TESTS — AgentTask
# =============================================================================

class TestAgentTask:
    """Tests for AgentTask data model."""

    def test_creation_generates_id(self):
        task = _make_task()
        assert task.task_id != ""

    def test_creation_sets_timestamp(self):
        task = _make_task()
        assert task.created_at != ""
        assert "T" in task.created_at  # ISO format

    def test_creation_with_context(self):
        task = _make_task(
            relevant_memories=["mem_abc", "mem_def"],
            constraints=["Do not use area lights"],
            context_summary="## Past Outcomes\n- Used spot lights",
        )
        assert len(task.relevant_memories) == 2
        assert "Do not use area lights" in task.constraints
        assert "Past Outcomes" in task.context_summary

    def test_to_dict_from_dict_roundtrip(self):
        task = _make_task(
            agent_id="agent_001",
            relevant_memories=["mem_abc"],
            constraints=["No area lights"],
            context_summary="Summary",
        )
        data = task.to_dict()
        restored = AgentTask.from_dict(data)

        assert restored.task_id == task.task_id
        assert restored.goal == task.goal
        assert restored.sequence_id == task.sequence_id
        assert restored.category == AuditCategory.LIGHTING
        assert restored.agent_id == "agent_001"
        assert restored.relevant_memories == ["mem_abc"]
        assert restored.constraints == ["No area lights"]


# =============================================================================
# PROTOCOL TESTS — AgentPlan
# =============================================================================

class TestAgentPlan:
    """Tests for AgentPlan data model."""

    def test_creation_generates_id(self):
        task = _make_task()
        plan = AgentPlan(plan_id="", task=task, steps=[], reasoning="Test")
        assert plan.plan_id != ""

    def test_default_status_is_draft(self):
        task = _make_task()
        plan = AgentPlan(plan_id="", task=task, steps=[], reasoning="Test")
        assert plan.status == PlanStatus.DRAFT

    def test_progress_empty_plan(self):
        task = _make_task()
        plan = AgentPlan(plan_id="", task=task, steps=[], reasoning="Test")
        assert plan.progress() == 0.0

    def test_progress_partial(self):
        task = _make_task()
        steps = [_make_step(), _make_step(), _make_step(), _make_step()]
        steps[0].status = StepStatus.COMPLETED
        steps[1].status = StepStatus.COMPLETED
        plan = AgentPlan(plan_id="", task=task, steps=steps, reasoning="Test")
        assert plan.progress() == 0.5

    def test_progress_all_complete(self):
        task = _make_task()
        steps = [_make_step(), _make_step()]
        steps[0].status = StepStatus.COMPLETED
        steps[1].status = StepStatus.COMPLETED
        plan = AgentPlan(plan_id="", task=task, steps=steps, reasoning="Test")
        assert plan.progress() == 1.0

    def test_progress_skipped_counts_as_done(self):
        task = _make_task()
        steps = [_make_step(), _make_step()]
        steps[0].status = StepStatus.COMPLETED
        steps[1].status = StepStatus.SKIPPED
        plan = AgentPlan(plan_id="", task=task, steps=steps, reasoning="Test")
        assert plan.progress() == 1.0

    def test_pending_steps(self):
        task = _make_task()
        steps = [_make_step(), _make_step(), _make_step()]
        steps[0].status = StepStatus.COMPLETED
        plan = AgentPlan(plan_id="", task=task, steps=steps, reasoning="Test")
        assert len(plan.pending_steps()) == 2

    def test_completed_steps(self):
        task = _make_task()
        steps = [_make_step(), _make_step(), _make_step()]
        steps[0].status = StepStatus.COMPLETED
        steps[2].status = StepStatus.COMPLETED
        plan = AgentPlan(plan_id="", task=task, steps=steps, reasoning="Test")
        assert len(plan.completed_steps()) == 2

    def test_failed_steps(self):
        task = _make_task()
        steps = [_make_step(), _make_step()]
        steps[1].status = StepStatus.FAILED
        plan = AgentPlan(plan_id="", task=task, steps=steps, reasoning="Test")
        assert len(plan.failed_steps()) == 1

    def test_to_summary_contains_goal(self):
        task = _make_task(goal="Create key light")
        steps = [_make_step(description="Make light")]
        plan = AgentPlan(plan_id="", task=task, steps=steps, reasoning="Lighting setup")
        summary = plan.to_summary()
        assert "Create key light" in summary
        assert "Lighting setup" in summary
        assert "Make light" in summary

    def test_to_dict_from_dict_roundtrip(self):
        task = _make_task()
        steps = [
            _make_step(action="create_node", description="Step 1"),
            _make_step(action="set_parm", description="Step 2"),
        ]
        plan = AgentPlan(
            plan_id="", task=task, steps=steps, reasoning="Test plan",
            status=PlanStatus.COMPLETED, success=True, outcome="All done",
        )
        data = plan.to_dict()
        restored = AgentPlan.from_dict(data)

        assert restored.plan_id == plan.plan_id
        assert restored.task.goal == task.goal
        assert len(restored.steps) == 2
        assert restored.reasoning == "Test plan"
        assert restored.status == PlanStatus.COMPLETED
        assert restored.success is True
        assert restored.outcome == "All done"


# =============================================================================
# PROTOCOL TESTS — Gate Classification
# =============================================================================

class TestClassifyGateLevel:
    """Tests for gate-level auto-classification."""

    def test_reads_are_inform(self):
        for action in ["get_parm", "get_scene_info", "get_selection", "ping",
                       "get_health", "get_node_types", "get_stage_info",
                       "get_usd_attribute", "context", "search", "recall"]:
            assert classify_gate_level(action) == GateLevel.INFORM, f"{action} should be INFORM"

    def test_creates_are_review(self):
        for action in ["create_node", "modify_node", "connect_nodes", "set_parm",
                       "set_selection", "create_usd_prim", "modify_usd_prim",
                       "set_usd_attribute", "add_memory", "decide"]:
            assert classify_gate_level(action) == GateLevel.REVIEW, f"{action} should be REVIEW"

    def test_deletes_are_approve(self):
        assert classify_gate_level("delete_node") == GateLevel.APPROVE

    def test_execute_is_critical(self):
        assert classify_gate_level("execute_python") == GateLevel.CRITICAL
        assert classify_gate_level("execute_vex") == GateLevel.CRITICAL

    def test_unknown_defaults_to_review(self):
        assert classify_gate_level("some_unknown_action") == GateLevel.REVIEW
        assert classify_gate_level("") == GateLevel.REVIEW

    def test_default_gate_levels_dict_is_complete(self):
        assert len(DEFAULT_GATE_LEVELS) > 20  # Sanity check


# =============================================================================
# THE DELETED SUBSYSTEM STAYS DELETED
#
# 2026-08-01, two cuts the same day. First `A2` retired `OutcomeTracker`
# (`learning.py`). Then the `RL-3` escalation it raised was ruled: the
# executor and the four v8-DSA modules had no production consumer at all —
# only their own dedicated tests and the package re-exports — and were
# deleted. `protocol.py` survived because a live tool suite imports it
# (`tests/test_set_usd_primvar.py::test_gate_level_is_review`).
#
# These pins make silent regrowth fail the suite. Reviving any of it
# requires a production construction site first (see the `A2` tombstone in
# `harness/rsi/REGISTRY.json`: executor first, reward signal second).
# =============================================================================

class TestDeletedAgentSubsystemStaysDeleted:
    """None of the deleted agent modules may quietly return."""

    DELETED_MODULES = [
        "synapse.agent.learning",          # A2 retirement
        "synapse.agent.executor",          # RL-3 cut
        "synapse.agent.sparse_router",     # RL-3 cut (v8-DSA)
        "synapse.agent.reasoning_context", # RL-3 cut (v8-DSA)
        "synapse.agent.specialist_modes",  # RL-3 cut (v8-DSA)
        "synapse.agent.task_synthesizer",  # RL-3 cut (v8-DSA)
    ]

    def test_deleted_modules_are_gone(self):
        for mod in self.DELETED_MODULES:
            with pytest.raises(ImportError):
                importlib.import_module(mod)

    def test_deleted_names_not_exported_from_agent_package(self):
        with pytest.raises(ImportError):
            from synapse.agent import AgentExecutor  # noqa: F401
        with pytest.raises(ImportError):
            from synapse.agent import OutcomeTracker  # noqa: F401
        with pytest.raises(ImportError):
            from synapse.agent import TaskSynthesizer  # noqa: F401

    def test_deleted_names_not_exported_from_synapse_root(self):
        with pytest.raises(ImportError):
            from synapse import AgentExecutor  # noqa: F401
        with pytest.raises(ImportError):
            from synapse import OutcomeTracker  # noqa: F401
        with pytest.raises(ImportError):
            from synapse import SparseToolIndexer  # noqa: F401
        with pytest.raises(ImportError):
            from synapse import TaskSynthesizer  # noqa: F401

    def test_agent_package_all_is_protocol_only(self):
        import synapse.agent as agent_pkg
        assert set(agent_pkg.__all__) == {
            "AgentTask", "AgentPlan", "AgentStep",
            "StepStatus", "PlanStatus",
            "DEFAULT_GATE_LEVELS", "classify_gate_level",
        }


# =============================================================================
# PACKAGE IMPORT TESTS
# =============================================================================

class TestPackageImports:
    """Verify public API is accessible."""

    def test_import_from_agent_package(self):
        from synapse.agent import (
            AgentTask, AgentPlan, AgentStep,
            StepStatus, PlanStatus,
            DEFAULT_GATE_LEVELS, classify_gate_level,
        )
        assert AgentTask is not None
        assert classify_gate_level is not None

    def test_import_from_synapse_root(self):
        from synapse import (
            AgentTask, AgentPlan, AgentStep,
        )
        assert AgentTask is not None
