"""
Synapse Agent Layer

Agentic execution protocol that transforms Synapse from a dumb pipe
into a smart runtime. Agents propose plans, plans route through gates,
steps execute and observe, outcomes feed back into memory for learning.

Usage:
    from synapse.agent import AgentExecutor, AgentStep

    # Dry-run mode (no Houdini needed)
    ex = AgentExecutor()
    task = ex.prepare("Set up key light", "shot_010", "lighting")
    plan = ex.propose(task, [
        AgentStep(step_id="", action="create_node",
                  description="Create key light",
                  payload={"type": "hlight", "path": "/obj/key"},
                  gate_level=None, reasoning="Need key light")
    ], reasoning="Basic lighting setup")
    result = ex.execute(plan)
"""

from .protocol import (
    AgentTask,
    AgentPlan,
    AgentStep,
    StepStatus,
    PlanStatus,
    DEFAULT_GATE_LEVELS,
    classify_gate_level,
)
from .executor import AgentExecutor
from .learning import OutcomeTracker

# v8-DSA: DeepSeek-V3.2 research graft (Phase 1)
from .sparse_router import (
    SparseToolIndexer,
    SparseRouterConfig,
    ToolSignature,
    RouteCandidate,
    Domain,
    CostTier,
    build_signatures_from_registry,
)
from .reasoning_context import (
    ReasoningContext,
    ReasoningContextManager,
    ReasoningEntry,
    EntryCategory,
    PROTECTED_CATEGORIES,
)
from .specialist_modes import (
    SpecialistMode,
    SpecialistDomain,
    QualitySignal,
    SPECIALIST_REGISTRY,
    get_specialist,
    get_specialist_by_name,
    build_enhanced_prompt,
    list_specialists,
)
from .task_synthesizer import (
    TaskSynthesizer,
    TaskEnvironment,
    TaskConstraint,
    SuccessCriterion,
    Complexity,
    ConstraintType,
    FailureMode,
)

__all__ = [
    "AgentTask",
    "AgentPlan",
    "AgentStep",
    "StepStatus",
    "PlanStatus",
    "DEFAULT_GATE_LEVELS",
    "classify_gate_level",
    "AgentExecutor",
    "OutcomeTracker",
    # v8-DSA: Sparse Router
    "SparseToolIndexer",
    "SparseRouterConfig",
    "ToolSignature",
    "RouteCandidate",
    "Domain",
    "CostTier",
    "build_signatures_from_registry",
    # v8-DSA: Reasoning Context
    "ReasoningContext",
    "ReasoningContextManager",
    "ReasoningEntry",
    "EntryCategory",
    "PROTECTED_CATEGORIES",
    # v8-DSA: Specialist Modes
    "SpecialistMode",
    "SpecialistDomain",
    "QualitySignal",
    "SPECIALIST_REGISTRY",
    "get_specialist",
    "get_specialist_by_name",
    "build_enhanced_prompt",
    "list_specialists",
    # v8-DSA: Task Synthesizer
    "TaskSynthesizer",
    "TaskEnvironment",
    "TaskConstraint",
    "SuccessCriterion",
    "Complexity",
    "ConstraintType",
    "FailureMode",
]
