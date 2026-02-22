"""
Synapse Agent Protocol

Data models for the agentic execution layer:
- AgentTask: what the agent wants to accomplish
- AgentPlan: ordered sequence of steps
- AgentStep: a single action in a plan
- Gate-level classification for automatic risk assignment
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

from ..core.determinism import deterministic_uuid
from ..core.protocol import SynapseCommand
from ..core.gates import GateLevel
from ..core.audit import AuditCategory


# =============================================================================
# STATUS ENUMS
# =============================================================================

class StepStatus(Enum):
    """Execution status of a single step."""
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(Enum):
    """Lifecycle status of an agent plan."""
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


# =============================================================================
# GATE-LEVEL CLASSIFICATION
# =============================================================================

DEFAULT_GATE_LEVELS: Dict[str, GateLevel] = {
    # Reads → auto-approve (INFORM)
    "get_parm": GateLevel.INFORM,
    "get_scene_info": GateLevel.INFORM,
    "get_selection": GateLevel.INFORM,
    "ping": GateLevel.INFORM,
    "get_health": GateLevel.INFORM,
    "get_node_types": GateLevel.INFORM,
    "get_stage_info": GateLevel.INFORM,
    "get_usd_attribute": GateLevel.INFORM,
    "context": GateLevel.INFORM,
    "search": GateLevel.INFORM,
    "recall": GateLevel.INFORM,

    # Creates/Modifies → batch review (REVIEW)
    "create_node": GateLevel.REVIEW,
    "modify_node": GateLevel.REVIEW,
    "connect_nodes": GateLevel.REVIEW,
    "set_parm": GateLevel.REVIEW,
    "set_selection": GateLevel.REVIEW,
    "create_usd_prim": GateLevel.REVIEW,
    "modify_usd_prim": GateLevel.REVIEW,
    "set_usd_attribute": GateLevel.REVIEW,
    "add_memory": GateLevel.REVIEW,
    "decide": GateLevel.REVIEW,

    # Destructive → explicit approval (APPROVE)
    "delete_node": GateLevel.APPROVE,

    # Arbitrary code execution → full stop (CRITICAL)
    "execute_python": GateLevel.CRITICAL,
    "execute_vex": GateLevel.CRITICAL,
}


def classify_gate_level(action: str) -> GateLevel:
    """
    Auto-classify risk level for an action type.

    Returns the default gate level for known actions,
    or REVIEW for unknown actions (safe default).
    """
    return DEFAULT_GATE_LEVELS.get(action, GateLevel.REVIEW)


# =============================================================================
# AGENT STEP
# =============================================================================

@dataclass
class AgentStep:
    """A single action in an agent plan."""

    # Identity
    step_id: str
    action: str                     # CommandType value ("create_node", "set_parm", etc.)
    description: str                # Human-readable
    payload: Dict[str, Any]         # SynapseCommand payload
    gate_level: Optional[GateLevel] # Auto-assigned or explicit (None = auto)
    reasoning: str                  # Why this step

    # Agent confidence
    confidence: float = 0.5

    # Filled during execution
    status: StepStatus = StepStatus.PENDING
    observation: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    executed_at: Optional[str] = None

    def __post_init__(self):
        if not self.step_id:
            content = f"{self.action}:{self.description}:{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
            self.step_id = deterministic_uuid(content, "step")

    def to_command(self) -> SynapseCommand:
        """Convert this step to a wire-format SynapseCommand."""
        return SynapseCommand(
            type=self.action,
            id=deterministic_uuid(f"cmd:{self.step_id}", "command"),
            payload=dict(self.payload),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "step_id": self.step_id,
            "action": self.action,
            "description": self.description,
            "payload": self.payload,
            "gate_level": self.gate_level.value if self.gate_level else None,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "status": self.status.value,
            "observation": self.observation,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "executed_at": self.executed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentStep":
        """Deserialize from dictionary."""
        gate_level = GateLevel(data["gate_level"]) if data.get("gate_level") else None
        return cls(
            step_id=data.get("step_id", ""),
            action=data["action"],
            description=data["description"],
            payload=data.get("payload", {}),
            gate_level=gate_level,
            reasoning=data.get("reasoning", ""),
            confidence=data.get("confidence", 0.5),
            status=StepStatus(data.get("status", "pending")),
            observation=data.get("observation", {}),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0.0),
            executed_at=data.get("executed_at"),
        )


# =============================================================================
# AGENT TASK
# =============================================================================

@dataclass
class AgentTask:
    """What the agent wants to accomplish."""

    # Identity
    task_id: str
    goal: str                       # "Set up three-point lighting for shot_010"
    sequence_id: str                # Shot/sequence context
    category: AuditCategory         # LIGHTING, MATERIAL, etc.
    agent_id: str = ""

    # Context (populated by executor.prepare())
    relevant_memories: List[str] = field(default_factory=list)   # Memory IDs
    constraints: List[str] = field(default_factory=list)         # From past rejections
    context_summary: str = ""                                     # Formatted for AI prompt

    created_at: str = ""

    def __post_init__(self):
        if not self.task_id:
            content = f"{self.goal}:{self.sequence_id}:{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
            self.task_id = deterministic_uuid(content, "task")
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "sequence_id": self.sequence_id,
            "category": self.category.value,
            "agent_id": self.agent_id,
            "relevant_memories": self.relevant_memories,
            "constraints": self.constraints,
            "context_summary": self.context_summary,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTask":
        """Deserialize from dictionary."""
        return cls(
            task_id=data.get("task_id", ""),
            goal=data["goal"],
            sequence_id=data["sequence_id"],
            category=AuditCategory(data["category"]),
            agent_id=data.get("agent_id", ""),
            relevant_memories=data.get("relevant_memories", []),
            constraints=data.get("constraints", []),
            context_summary=data.get("context_summary", ""),
            created_at=data.get("created_at", ""),
        )


# =============================================================================
# AGENT PLAN
# =============================================================================

@dataclass
class AgentPlan:
    """An ordered sequence of steps to accomplish a task."""

    # Identity
    plan_id: str
    task: AgentTask
    steps: List[AgentStep]
    reasoning: str                  # Overall approach explanation

    # State
    status: PlanStatus = PlanStatus.DRAFT
    current_step: int = 0           # Index of next step to execute
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

    # Results (filled after execution)
    outcome: Optional[str] = None
    success: Optional[bool] = None
    completed_at: Optional[str] = None

    def __post_init__(self):
        if not self.plan_id:
            content = f"{self.task.task_id}:{self.reasoning}:{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"
            self.plan_id = deterministic_uuid(content, "plan")

    def pending_steps(self) -> List[AgentStep]:
        """Get steps not yet executed."""
        return [s for s in self.steps if s.status == StepStatus.PENDING]

    def completed_steps(self) -> List[AgentStep]:
        """Get successfully completed steps."""
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    def failed_steps(self) -> List[AgentStep]:
        """Get failed steps."""
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    def progress(self) -> float:
        """Calculate completion progress (0.0 to 1.0)."""
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED))
        return done / len(self.steps)

    def to_summary(self) -> str:
        """Human-readable plan summary."""
        lines = [
            f"Plan: {self.plan_id}",
            f"Goal: {self.task.goal}",
            f"Status: {self.status.value}",
            f"Progress: {self.progress():.0%} ({len(self.completed_steps())}/{len(self.steps)} steps)",
            f"Reasoning: {self.reasoning}",
            "",
            "Steps:",
        ]
        for i, step in enumerate(self.steps):
            marker = ">" if i == self.current_step and self.status == PlanStatus.EXECUTING else " "
            lines.append(f"  {marker} {i+1}. [{step.status.value}] {step.description}")
            if step.error:
                lines.append(f"       Error: {step.error}")
        if self.outcome:
            lines.append(f"\nOutcome: {self.outcome}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "plan_id": self.plan_id,
            "task": self.task.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "reasoning": self.reasoning,
            "status": self.status.value,
            "current_step": self.current_step,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "outcome": self.outcome,
            "success": self.success,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentPlan":
        """Deserialize from dictionary."""
        return cls(
            plan_id=data.get("plan_id", ""),
            task=AgentTask.from_dict(data["task"]),
            steps=[AgentStep.from_dict(s) for s in data.get("steps", [])],
            reasoning=data.get("reasoning", ""),
            status=PlanStatus(data.get("status", "draft")),
            current_step=data.get("current_step", 0),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            outcome=data.get("outcome"),
            success=data.get("success"),
            completed_at=data.get("completed_at"),
        )
