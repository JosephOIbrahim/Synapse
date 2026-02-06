"""
Synapse Agent Executor

The core prepare → propose → execute → learn loop.
Orchestrates tasks through gate approval and step-by-step execution.

Key design: command_fn is optional. Without it, the executor works in
"planning mode" — plans are created, gated, and audited, but not sent
to Houdini. This enables testing without Houdini and separation of
planning from execution.
"""

import time
from typing import Any, Callable, Optional, List

from ..core.protocol import SynapseCommand, SynapseResponse
from ..core.gates import GateLevel, GateDecision, HumanGate
from ..core.audit import audit_log, AuditLevel, AuditCategory
from ..core.determinism import deterministic_uuid
from ..memory.store import SynapseMemory
from ..memory.models import MemoryType, MemoryQuery

from .protocol import (
    AgentTask,
    AgentPlan,
    AgentStep,
    StepStatus,
    PlanStatus,
    classify_gate_level,
)
from .learning import OutcomeTracker


class AgentExecutor:
    """
    Core agent execution loop.

    Manages the lifecycle: prepare → propose → execute → learn.
    Works in dry-run mode when command_fn is None.
    """

    def __init__(
        self,
        command_fn: Optional[Callable[[SynapseCommand], SynapseResponse]] = None,
        memory: Optional[SynapseMemory] = None,
        gate: Optional[HumanGate] = None,
        router: Optional[Any] = None,
    ):
        """
        Args:
            command_fn: Callback to execute commands (None = dry-run/planning mode).
            memory: For context retrieval and outcome storage.
            gate: For human approval routing.
            router: Optional TieredRouter for introspection (set by router externally).
        """
        self._command_fn = command_fn
        self._memory = memory
        self._gate = gate
        self._router = router
        self._tracker = OutcomeTracker(memory) if memory else None

    def prepare(
        self,
        goal: str,
        sequence_id: str,
        category: str,
        agent_id: str = "",
    ) -> AgentTask:
        """
        Create a task with memory context.

        1. Search memory for relevant past decisions/outcomes
        2. Search memory for past rejections → extract constraints
        3. Build context summary for AI prompt

        Returns:
            AgentTask ready for plan creation.
        """
        cat = AuditCategory(category) if isinstance(category, str) else category

        task = AgentTask(
            task_id="",
            goal=goal,
            sequence_id=sequence_id,
            category=cat,
            agent_id=agent_id,
        )

        # Populate context from memory if available
        if self._memory and self._tracker:
            # Search for relevant past outcomes
            relevant = self._tracker.get_relevant(goal, cat, limit=5)
            task.relevant_memories = [r.memory.id for r in relevant]

            # Search for past rejections to build constraints
            rejections = self._tracker.get_rejections(sequence_id, cat)
            task.constraints = [
                m.content for m in rejections
            ]

            # Build context summary
            parts = []
            if relevant:
                parts.append("## Relevant Past Outcomes")
                for r in relevant:
                    parts.append(f"- [{r.score:.0%}] {r.memory.summary}")
            if task.constraints:
                parts.append("\n## Constraints (from past rejections)")
                for c in task.constraints:
                    parts.append(f"- {c}")
            task.context_summary = "\n".join(parts)

        audit_log().log(
            operation="agent_prepare",
            message=f"Prepared task: {goal}",
            level=AuditLevel.INFO,
            category=cat,
            agent_id=agent_id,
            sequence_id=sequence_id,
            input_data={"task_id": task.task_id, "goal": goal},
        )

        return task

    def propose(
        self,
        task: AgentTask,
        steps: List[AgentStep],
        reasoning: str,
    ) -> AgentPlan:
        """
        Submit a plan for approval.

        1. Create AgentPlan
        2. For each step, auto-assign gate_level via classify_gate_level() if not set
        3. Route through HumanGate
        4. Audit log the proposal
        5. Return plan with appropriate status

        Returns:
            AgentPlan (status=PROPOSED, or APPROVED if all auto-approved).
        """
        # Auto-assign gate levels for steps that don't have one
        for step in steps:
            if step.gate_level is None:
                step.gate_level = classify_gate_level(step.action)

        plan = AgentPlan(
            plan_id="",
            task=task,
            steps=steps,
            reasoning=reasoning,
            status=PlanStatus.PROPOSED,
        )

        # Route through gate if available
        all_auto_approved = True
        if self._gate:
            for step in steps:
                proposal = self._gate.propose(
                    operation=step.action,
                    description=step.description,
                    sequence_id=task.sequence_id,
                    category=task.category,
                    level=step.gate_level,
                    proposed_changes=step.payload,
                    agent_id=task.agent_id,
                    reasoning=step.reasoning,
                    confidence=step.confidence,
                )
                if proposal.decision != GateDecision.APPROVED:
                    all_auto_approved = False
        else:
            # No gate — check if all steps would be auto-approved
            all_auto_approved = all(
                s.gate_level == GateLevel.INFORM for s in steps
            )

        if all_auto_approved:
            plan.status = PlanStatus.APPROVED
            plan.approved_by = "system:auto"
            plan.approved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        audit_log().log(
            operation="agent_propose",
            message=f"Proposed plan ({len(steps)} steps): {reasoning}",
            level=AuditLevel.AGENT_ACTION,
            category=task.category,
            agent_id=task.agent_id,
            sequence_id=task.sequence_id,
            input_data={
                "plan_id": plan.plan_id,
                "task_id": task.task_id,
                "step_count": len(steps),
                "status": plan.status.value,
            },
        )

        return plan

    def execute(self, plan: AgentPlan) -> AgentPlan:
        """
        Execute an approved plan step by step.

        1. Verify plan.status == APPROVED
        2. For each step: execute via command_fn or mark completed (dry run)
        3. Record outcome

        Returns:
            Completed (or failed) plan.
        """
        if plan.status != PlanStatus.APPROVED:
            raise ValueError(
                f"Cannot execute plan in status '{plan.status.value}'. "
                f"Plan must be APPROVED."
            )

        plan.status = PlanStatus.EXECUTING

        for i, step in enumerate(plan.steps):
            plan.current_step = i
            step.status = StepStatus.EXECUTING
            step.executed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            audit_log().log(
                operation="agent_step_start",
                message=f"Executing step {i+1}/{len(plan.steps)}: {step.description}",
                level=AuditLevel.INFO,
                category=plan.task.category,
                agent_id=plan.task.agent_id,
                sequence_id=plan.task.sequence_id,
                input_data={
                    "plan_id": plan.plan_id,
                    "step_id": step.step_id,
                    "action": step.action,
                },
            )

            start_time = time.monotonic()

            if self._command_fn:
                # Live execution
                try:
                    cmd = step.to_command()
                    response = self._command_fn(cmd)
                    step.duration_ms = (time.monotonic() - start_time) * 1000

                    if response.success:
                        step.status = StepStatus.COMPLETED
                        step.observation = response.data if isinstance(response.data, dict) else {"result": response.data}
                    else:
                        step.status = StepStatus.FAILED
                        step.error = response.error or "Command returned failure"
                        step.observation = response.data if isinstance(response.data, dict) else {}
                except Exception as e:
                    step.duration_ms = (time.monotonic() - start_time) * 1000
                    step.status = StepStatus.FAILED
                    step.error = str(e)
            else:
                # Dry run — mark completed with empty observation
                step.duration_ms = (time.monotonic() - start_time) * 1000
                step.status = StepStatus.COMPLETED
                step.observation = {}

            audit_log().log(
                operation="agent_step_end",
                message=f"Step {i+1} {step.status.value}: {step.description}",
                level=AuditLevel.INFO if step.status == StepStatus.COMPLETED else AuditLevel.WARNING,
                category=plan.task.category,
                agent_id=plan.task.agent_id,
                sequence_id=plan.task.sequence_id,
                output_data={
                    "plan_id": plan.plan_id,
                    "step_id": step.step_id,
                    "status": step.status.value,
                    "duration_ms": step.duration_ms,
                    "error": step.error,
                },
            )

            if step.status == StepStatus.FAILED:
                plan.status = PlanStatus.FAILED
                plan.outcome = f"Failed at step {i+1}: {step.error}"
                plan.success = False
                plan.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.record_outcome(plan, success=False)
                return plan

        # All steps completed
        plan.status = PlanStatus.COMPLETED
        plan.outcome = f"All {len(plan.steps)} steps completed successfully"
        plan.success = True
        plan.completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.record_outcome(plan, success=True)
        return plan

    def record_outcome(
        self,
        plan: AgentPlan,
        success: bool,
        feedback: str = "",
    ) -> None:
        """
        Store outcome in memory via OutcomeTracker.

        Called automatically at end of execute(), or manually for external feedback.
        """
        if self._tracker:
            self._tracker.record(plan, success, feedback)
