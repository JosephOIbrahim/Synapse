"""
Synapse Agent Layer Tests

Tests for protocol models and the executor (dry-run and with mock command_fn).

The outcome-tracking/learning tests were removed on 2026-08-01 with the
mechanism they covered: `OutcomeTracker` (`synapse/agent/learning.py`), RSI
loop `A2`, RETIRED for dormancy. What replaces them is smaller and points the
other way — `TestExecutorMemoryIsInert` pins that the executor no longer reads
or writes memory, so a future revival has to be deliberate rather than
accidental.

Run without Houdini:
    python -m pytest tests/test_agent.py -v
"""

import sys
import os
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.core.protocol import SynapseCommand, SynapseResponse
from synapse.core.gates import GateLevel, GateDecision, HumanGate
from synapse.core.audit import AuditLog, AuditCategory
from synapse.core.determinism import deterministic_uuid
from synapse.memory.store import SynapseMemory
from synapse.memory.models import MemoryType, MemoryQuery

from synapse.agent.protocol import (
    AgentStep,
    AgentTask,
    AgentPlan,
    StepStatus,
    PlanStatus,
    DEFAULT_GATE_LEVELS,
    classify_gate_level,
)
from synapse.agent.executor import AgentExecutor


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
# EXECUTOR TESTS — Without Houdini (dry-run)
# =============================================================================

class TestExecutorDryRun:
    """Tests for AgentExecutor without command_fn (planning/dry-run mode)."""

    def setup_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.audit_dir = self.tmp_dir / "audit"
        self.gate_dir = self.tmp_dir / "gates"
        AuditLog.get_instance(log_dir=self.audit_dir)
        self.executor = AgentExecutor()

    def teardown_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_prepare_creates_task(self):
        task = self.executor.prepare("Set up three-point lighting", "shot_010", "lighting")
        assert isinstance(task, AgentTask)
        assert task.goal == "Set up three-point lighting"
        assert task.sequence_id == "shot_010"
        assert task.category == AuditCategory.LIGHTING
        assert task.task_id != ""
        assert task.created_at != ""

    def test_prepare_accepts_category_enum(self):
        task = self.executor.prepare("Test", "shot_010", AuditCategory.MATERIAL)
        assert task.category == AuditCategory.MATERIAL

    def test_prepare_with_agent_id(self):
        task = self.executor.prepare("Test", "shot_010", "lighting", agent_id="agent_001")
        assert task.agent_id == "agent_001"

    def test_propose_creates_plan(self):
        task = self.executor.prepare("Test lighting", "shot_010", "lighting")
        steps = [_make_step(action="create_node", description="Create light")]
        plan = self.executor.propose(task, steps, reasoning="Basic setup")

        assert isinstance(plan, AgentPlan)
        assert plan.task is task
        assert len(plan.steps) == 1
        assert plan.reasoning == "Basic setup"
        assert plan.plan_id != ""

    def test_propose_auto_assigns_gate_levels(self):
        task = self.executor.prepare("Test", "shot_010", "lighting")
        steps = [
            _make_step(action="get_parm", gate_level=None),
            _make_step(action="create_node", gate_level=None),
            _make_step(action="delete_node", gate_level=None),
        ]
        plan = self.executor.propose(task, steps, reasoning="Mixed actions")

        assert plan.steps[0].gate_level == GateLevel.INFORM
        assert plan.steps[1].gate_level == GateLevel.REVIEW
        assert plan.steps[2].gate_level == GateLevel.APPROVE

    def test_propose_preserves_explicit_gate_level(self):
        task = self.executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="get_parm", gate_level=GateLevel.CRITICAL)]
        plan = self.executor.propose(task, steps, reasoning="Overridden")

        assert plan.steps[0].gate_level == GateLevel.CRITICAL

    def test_propose_auto_approves_all_inform(self):
        task = self.executor.prepare("Test", "shot_010", "lighting")
        steps = [
            _make_step(action="get_parm"),
            _make_step(action="ping"),
        ]
        plan = self.executor.propose(task, steps, reasoning="Read-only")

        assert plan.status == PlanStatus.APPROVED

    def test_propose_stays_proposed_for_review_steps(self):
        task = self.executor.prepare("Test", "shot_010", "lighting")
        steps = [
            _make_step(action="create_node"),
        ]
        plan = self.executor.propose(task, steps, reasoning="Creating stuff")

        # Without a gate, non-INFORM steps stay PROPOSED
        assert plan.status == PlanStatus.PROPOSED

    def test_execute_dry_run_completes_all_steps(self):
        task = self.executor.prepare("Test", "shot_010", "lighting")
        steps = [
            _make_step(action="get_parm", description="Read param"),
            _make_step(action="get_parm", description="Read another"),
        ]
        plan = self.executor.propose(task, steps, reasoning="Read-only")
        assert plan.status == PlanStatus.APPROVED

        result = self.executor.execute(plan)

        assert result.status == PlanStatus.COMPLETED
        assert result.success is True
        assert len(result.completed_steps()) == 2
        assert all(s.status == StepStatus.COMPLETED for s in result.steps)
        assert all(s.executed_at is not None for s in result.steps)
        assert result.completed_at is not None

    def test_execute_raises_on_non_approved(self):
        task = self.executor.prepare("Test", "shot_010", "lighting")
        plan = AgentPlan(
            plan_id="", task=task, steps=[], reasoning="Test",
            status=PlanStatus.DRAFT,
        )
        try:
            self.executor.execute(plan)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "APPROVED" in str(e)

    def test_execute_records_audit(self):
        task = self.executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="ping")]
        plan = self.executor.propose(task, steps, reasoning="Check")
        assert plan.status == PlanStatus.APPROVED

        self.executor.execute(plan)

        # Verify audit entries were created
        entries = AuditLog.get_instance().get_entries()
        operations = [e.operation for e in entries]
        assert "agent_prepare" in operations
        assert "agent_propose" in operations
        assert "agent_step_start" in operations
        assert "agent_step_end" in operations


# =============================================================================
# EXECUTOR TESTS — With mock command_fn
# =============================================================================

class TestExecutorWithHandler:
    """Tests for AgentExecutor with a mock command_fn."""

    def setup_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        self.tmp_dir = Path(tempfile.mkdtemp())
        AuditLog.get_instance(log_dir=self.tmp_dir / "audit")

    def teardown_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_execute_calls_command_fn(self):
        mock_fn = Mock(return_value=SynapseResponse(
            id="resp_1", success=True, data={"result": "light_created"}
        ))
        executor = AgentExecutor(command_fn=mock_fn)

        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="ping")]
        plan = executor.propose(task, steps, reasoning="Test")
        assert plan.status == PlanStatus.APPROVED

        result = executor.execute(plan)

        assert mock_fn.call_count == 1
        cmd_arg = mock_fn.call_args[0][0]
        assert isinstance(cmd_arg, SynapseCommand)
        assert cmd_arg.type == "ping"

    def test_execute_captures_response_data(self):
        mock_fn = Mock(return_value=SynapseResponse(
            id="resp_1", success=True, data={"path": "/obj/key", "created": True}
        ))
        executor = AgentExecutor(command_fn=mock_fn)

        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="ping")]
        plan = executor.propose(task, steps, reasoning="Test")
        result = executor.execute(plan)

        assert result.steps[0].observation == {"path": "/obj/key", "created": True}
        assert result.steps[0].status == StepStatus.COMPLETED
        assert result.status == PlanStatus.COMPLETED

    def test_execute_handles_non_dict_response_data(self):
        mock_fn = Mock(return_value=SynapseResponse(
            id="resp_1", success=True, data="pong"
        ))
        executor = AgentExecutor(command_fn=mock_fn)

        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="ping")]
        plan = executor.propose(task, steps, reasoning="Test")
        result = executor.execute(plan)

        assert result.steps[0].observation == {"result": "pong"}

    def test_execute_handles_error_response(self):
        mock_fn = Mock(return_value=SynapseResponse(
            id="resp_1", success=False, error="Node not found"
        ))
        executor = AgentExecutor(command_fn=mock_fn)

        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [
            _make_step(action="ping", description="Step 1"),
            _make_step(action="ping", description="Step 2"),
        ]
        plan = executor.propose(task, steps, reasoning="Test")
        result = executor.execute(plan)

        assert result.steps[0].status == StepStatus.FAILED
        assert result.steps[0].error == "Node not found"
        assert result.status == PlanStatus.FAILED
        assert result.success is False
        # Step 2 should still be PENDING (never executed)
        assert result.steps[1].status == StepStatus.PENDING

    def test_execute_stops_on_failure(self):
        call_count = 0

        def failing_fn(cmd):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return SynapseResponse(id="r", success=False, error="Boom")
            return SynapseResponse(id="r", success=True, data={})

        executor = AgentExecutor(command_fn=failing_fn)

        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [
            _make_step(action="ping", description="Step 1"),
            _make_step(action="ping", description="Step 2"),
            _make_step(action="ping", description="Step 3"),
        ]
        plan = executor.propose(task, steps, reasoning="Test")
        result = executor.execute(plan)

        assert call_count == 2  # Third step never reached
        assert result.steps[0].status == StepStatus.COMPLETED
        assert result.steps[1].status == StepStatus.FAILED
        assert result.steps[2].status == StepStatus.PENDING
        assert result.status == PlanStatus.FAILED

    def test_execute_handles_exception_in_command_fn(self):
        def exploding_fn(cmd):
            raise ConnectionError("Houdini disconnected")

        executor = AgentExecutor(command_fn=exploding_fn)

        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="ping")]
        plan = executor.propose(task, steps, reasoning="Test")
        result = executor.execute(plan)

        assert result.steps[0].status == StepStatus.FAILED
        assert "Houdini disconnected" in result.steps[0].error
        assert result.status == PlanStatus.FAILED

    def test_execute_records_duration(self):
        def slow_fn(cmd):
            time.sleep(0.01)
            return SynapseResponse(id="r", success=True, data={})

        executor = AgentExecutor(command_fn=slow_fn)

        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="ping")]
        plan = executor.propose(task, steps, reasoning="Test")
        result = executor.execute(plan)

        assert result.steps[0].duration_ms > 0


# =============================================================================
# EXECUTOR TESTS — With Gate
# =============================================================================

class TestExecutorWithGate:
    """Tests for AgentExecutor with HumanGate integration."""

    def setup_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.gate = HumanGate(storage_dir=self.tmp_dir / "gates")
        AuditLog.get_instance(log_dir=self.tmp_dir / "audit")

    def teardown_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_propose_routes_inform_through_gate(self):
        executor = AgentExecutor(gate=self.gate)
        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="ping")]  # INFORM level
        plan = executor.propose(task, steps, reasoning="Read")

        # INFORM is auto-approved by gate
        assert plan.status == PlanStatus.APPROVED

    def test_propose_routes_review_through_gate(self):
        executor = AgentExecutor(gate=self.gate)
        task = executor.prepare("Test", "shot_010", "lighting")
        steps = [_make_step(action="create_node")]  # REVIEW level
        plan = executor.propose(task, steps, reasoning="Create")

        # REVIEW goes to batch, not auto-approved
        assert plan.status == PlanStatus.PROPOSED

        # Gate should have a batch for this sequence
        batch = self.gate.get_batch("shot_010")
        assert batch is not None
        assert len(batch.proposals) >= 1


# =============================================================================
# EXECUTOR + MEMORY: THE RETIRED REWARD SIGNAL
#
# RSI loop `A2` (`OutcomeTracker`, `synapse/agent/learning.py`) was RETIRED on
# 2026-08-01 for dormancy — it never recorded an outcome in production because
# `AgentExecutor` has no production construction site at all. The tests that
# covered it went with it. These pin the ABSENCE, so nothing silently grows
# back: passing `memory=` must not make the executor read or write memory.
# =============================================================================

class TestExecutorMemoryIsInert:
    """The executor accepts a memory handle and does nothing with it."""

    def setup_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        self.tmp_dir = Path(tempfile.mkdtemp())
        AuditLog.get_instance(log_dir=self.tmp_dir / "audit")
        self.memory = SynapseMemory(project_path=str(self.tmp_dir / "project"))

    def teardown_method(self):
        HumanGate.reset_instance()
        AuditLog.reset_instance()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_executor_has_no_outcome_tracker(self):
        """The wiring at the old executor.py:60 is gone, not merely disabled."""
        executor = AgentExecutor(memory=self.memory)
        assert not hasattr(executor, "_tracker")

    def test_executor_has_no_record_outcome_method(self):
        """The public reward-signal entry point is gone."""
        assert not hasattr(AgentExecutor(memory=self.memory), "record_outcome")

    def test_learning_module_is_gone(self):
        """`synapse.agent.learning` must not be importable, from anywhere."""
        import pytest
        with pytest.raises(ImportError):
            import synapse.agent.learning  # noqa: F401
        with pytest.raises(ImportError):
            from synapse.agent import OutcomeTracker  # noqa: F401
        with pytest.raises(ImportError):
            from synapse import OutcomeTracker  # noqa: F401

    def test_prepare_no_longer_reads_memory(self):
        """The read half is retired: prior FEEDBACK memories do not seed context."""
        self.memory.add(
            content="Previous lighting setup worked well",
            memory_type=MemoryType.FEEDBACK,
            tags=["lighting", "success", "shot_010", "outcome"],
            keywords=["lighting", "setup"],
        )

        executor = AgentExecutor(memory=self.memory)
        task = executor.prepare("Set up lighting", "shot_010", "lighting")

        assert task.relevant_memories == []
        assert task.constraints == []
        assert task.context_summary == ""

    def test_execute_writes_no_outcome_memory(self):
        """The write half is retired: a completed plan records nothing."""
        executor = AgentExecutor(memory=self.memory)
        task = executor.prepare("Test", "shot_010", "lighting")
        plan = executor.propose(task, [_make_step(action="ping")], reasoning="Test")
        assert plan.status == PlanStatus.APPROVED

        result = executor.execute(plan)
        assert result.success is True

        assert self.memory.store.get_by_type(MemoryType.FEEDBACK) == []

    def test_execute_writes_no_outcome_memory_on_failure(self):
        """The failure path recorded too. It also records nothing now."""
        def failing_fn(cmd):
            return SynapseResponse(success=False, error="nope")

        executor = AgentExecutor(command_fn=failing_fn, memory=self.memory)
        task = executor.prepare("Test", "shot_010", "lighting")
        plan = executor.propose(task, [_make_step(action="ping")], reasoning="Test")
        assert plan.status == PlanStatus.APPROVED

        result = executor.execute(plan)
        assert result.success is False

        assert self.memory.store.get_by_type(MemoryType.FEEDBACK) == []

    def test_full_loop_prepare_propose_execute(self):
        """End-to-end: prepare -> propose -> execute. No learn stage."""
        executor = AgentExecutor(memory=self.memory)

        task = executor.prepare(
            "Set up three-point lighting for shot_010",
            "shot_010",
            "lighting",
            agent_id="test_agent",
        )
        assert isinstance(task, AgentTask)

        steps = [
            _make_step(action="get_scene_info", description="Check current scene"),
            _make_step(action="get_parm", description="Check existing lights"),
        ]
        plan = executor.propose(task, steps, reasoning="Gather info first")
        assert plan.status == PlanStatus.APPROVED

        result = executor.execute(plan)
        assert result.status == PlanStatus.COMPLETED
        assert result.success is True
        assert result.progress() == 1.0


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
            AgentExecutor,
        )
        assert AgentTask is not None
        assert AgentExecutor is not None

    def test_import_from_synapse_root(self):
        from synapse import (
            AgentTask, AgentPlan, AgentStep,
            AgentExecutor,
        )
        assert AgentTask is not None
        assert AgentExecutor is not None
