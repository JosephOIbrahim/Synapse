"""
Synapse Outcome Tracker

Wires audit + memory for feedback learning.
Records action-outcome pairs as FEEDBACK memories,
enabling the agent to learn from past successes and failures.

Key insight: This doesn't introduce a new storage system.
It uses existing SynapseMemory with MemoryType.FEEDBACK,
specific tags, and Zettelkasten links. The intelligence is
in the query patterns, not new infrastructure.
"""

from typing import List, Optional, TYPE_CHECKING

from ..memory.store import SynapseMemory
from ..memory.models import (
    Memory,
    MemoryType,
    MemoryQuery,
    MemorySearchResult,
    LinkType,
)
from ..core.audit import AuditCategory
from ..core.determinism import round_float

if TYPE_CHECKING:
    from .protocol import AgentPlan


class OutcomeTracker:
    """
    Records plan outcomes as FEEDBACK memories and queries
    past outcomes to inform future planning.
    """

    def __init__(self, memory: SynapseMemory):
        self._memory = memory

    def record(
        self,
        plan: "AgentPlan",
        success: bool,
        feedback: str = "",
    ) -> Memory:
        """
        Record plan outcome as a FEEDBACK memory.

        Content: structured summary of goal, steps taken, result.
        Tags: [category, "success"/"failure", sequence_id]
        Keywords: extracted from goal + step descriptions

        Returns:
            The created Memory.
        """
        # Build structured content
        step_summaries = []
        for step in plan.steps:
            status_str = step.status.value
            step_summaries.append(f"- [{status_str}] {step.description}")
            if step.error:
                step_summaries.append(f"  Error: {step.error}")

        content_parts = [
            f"**Goal:** {plan.task.goal}",
            f"**Result:** {'Success' if success else 'Failure'}",
            f"**Reasoning:** {plan.reasoning}",
            "",
            "**Steps:**",
            *step_summaries,
        ]
        if feedback:
            content_parts.extend(["", f"**Feedback:** {feedback}"])

        content = "\n".join(content_parts)

        # Build tags
        tags = [
            plan.task.category.value,
            "success" if success else "failure",
            plan.task.sequence_id,
            "outcome",
        ]

        # Extract keywords from goal and step descriptions
        words = plan.task.goal.lower().split()
        for step in plan.steps:
            words.extend(step.description.lower().split())
        # Simple dedup + filter short words
        seen = set()
        keywords = []
        for w in words:
            w = w.strip(".,!?;:()[]{}\"'-")
            if w and len(w) > 2 and w not in seen:
                seen.add(w)
                keywords.append(w)
                if len(keywords) >= 10:
                    break

        # Build links to decision memories from task context
        links = []
        for mem_id in plan.task.relevant_memories:
            links.append({
                "target_id": mem_id,
                "type": LinkType.CAUSED_BY.value,
                "reason": "Context for this plan",
            })

        memory = self._memory.add(
            content=content,
            memory_type=MemoryType.FEEDBACK,
            tags=tags,
            keywords=keywords,
            source="agent",
            links=links if links else None,
        )

        return memory

    def get_relevant(
        self,
        goal: str,
        category: AuditCategory,
        limit: int = 5,
    ) -> List[MemorySearchResult]:
        """
        Find past outcomes similar to current goal.

        Uses memory.store.search() with text=goal, tags=[category],
        memory_types=[FEEDBACK].
        """
        query = MemoryQuery(
            text=goal,
            memory_types=[MemoryType.FEEDBACK],
            tags=[category.value],
            limit=limit,
        )
        return self._memory.store.search(query)

    def get_rejections(
        self,
        sequence_id: str,
        category: Optional[AuditCategory] = None,
    ) -> List[Memory]:
        """
        Find past rejected/failed plans for constraint extraction.

        Queries memories tagged "failure" + sequence_id.
        """
        query = MemoryQuery(
            memory_types=[MemoryType.FEEDBACK],
            tags=["failure", sequence_id],
            limit=20,
        )
        results = self._memory.store.search(query)

        # Post-filter: require both "failure" and sequence_id tags
        # (MemoryStore.search scores by tag overlap, not strict AND)
        memories = [
            r.memory for r in results
            if "failure" in r.memory.tags and sequence_id in r.memory.tags
        ]

        # Optionally filter by category
        if category:
            memories = [m for m in memories if category.value in m.tags]

        return memories

    def success_rate(
        self,
        category: Optional[AuditCategory] = None,
    ) -> float:
        """
        Calculate success rate from stored outcomes.

        Returns 0.0 if no outcomes recorded.
        """
        tags = ["outcome"]
        if category:
            tags.append(category.value)

        query = MemoryQuery(
            memory_types=[MemoryType.FEEDBACK],
            tags=tags,
            limit=1000,
        )
        results = self._memory.store.search(query)

        if not results:
            return 0.0

        successes = sum(1 for r in results if "success" in r.memory.tags)
        return round_float(successes / len(results))
