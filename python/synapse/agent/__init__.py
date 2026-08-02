"""
Synapse Agent Layer — protocol only.

This package once carried a full agentic execution subsystem. It was deleted
on 2026-08-01 when the escalation from RSI loop `A2`'s retirement (`RL-3`,
`harness/rsi/LOG.md`) was ruled: none of it had a production consumer.
Deleted (last live at fc38cc4 — find the code in git history):

- ``executor.py`` (`AgentExecutor`) — the prepare -> propose -> execute loop.
  Zero non-test constructions anywhere in the tree; the only non-test
  ``AgentExecutor(`` was an illustrative example in this very docstring.
- ``sparse_router.py``, ``reasoning_context.py``, ``specialist_modes.py``,
  ``task_synthesizer.py`` (the v8-DSA research graft) — each consumed only
  by its own dedicated test file and the package re-exports.
- ``learning.py`` (`OutcomeTracker`) went earlier the same day, in the `A2`
  retirement itself — see ``harness/rsi/REGISTRY.json`` -> loop `A2`.

What remains, and why: ``protocol.py``. Its gate map is imported by a live
tool's suite (``tests/test_set_usd_primvar.py::test_gate_level_is_review``,
"Wiring site 1: gate map (protocol.py)"), and its dataclasses pin the plan
serialization contract in ``tests/test_agent.py``. A live import keeps a
module; a docstring example never did.

Reviving the agent loop means building a production construction site first —
a handler, panel loop, or MCP tool that drives it on real artist traffic.
Resurrecting the deleted files without that caller only re-creates code that
runs zero times. Ordering per the `A2` tombstone: the executor comes first,
everything downstream of it second.
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

__all__ = [
    "AgentTask",
    "AgentPlan",
    "AgentStep",
    "StepStatus",
    "PlanStatus",
    "DEFAULT_GATE_LEVELS",
    "classify_gate_level",
]
