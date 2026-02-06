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
]
