"""
Reasoning Context Persistence (v8-DSA)

Maintains persistent reasoning traces across multi-tool agent chains,
adapted from DeepSeek-V3.2's Thinking Context Preservation pattern
(arxiv:2512.02556).

The core problem: every tool call or context switch resets momentum
to cold_start, forcing the agent to re-derive decisions it already
made. This module preserves 5 categories of state that must survive
any context boundary:

1. Active decisions made this session
2. Unresolved questions under investigation
3. Planned next steps (queued thoughts)
4. Current momentum phase
5. Burst phase and exchange count

Protected categories (DECISION, QUESTION, PLAN) survive compression.
Observations and analysis can be summarized to save space.

Phase 1: Standalone module, no integration with executor.py.
"""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..core.determinism import deterministic_uuid


# =============================================================================
# ENTRY CATEGORIES
# =============================================================================

class EntryCategory(Enum):
    """Classification of reasoning trace entries."""
    DECISION = "decision"         # Active decisions (PROTECTED)
    QUESTION = "question"         # Unresolved questions (PROTECTED)
    PLAN = "plan"                 # Planned next steps (PROTECTED)
    OBSERVATION = "observation"   # Tool call results (compressible)
    ANALYSIS = "analysis"         # Reasoning about observations (compressible)
    CONTEXT = "context"           # Background context (compressible)


# Categories that must survive compression
PROTECTED_CATEGORIES = frozenset({
    EntryCategory.DECISION,
    EntryCategory.QUESTION,
    EntryCategory.PLAN,
})


# =============================================================================
# REASONING ENTRY
# =============================================================================

@dataclass
class ReasoningEntry:
    """A single entry in the reasoning trace."""
    category: EntryCategory
    content: str
    timestamp: str = ""
    tool_call: Optional[str] = None    # Tool that produced this entry
    confidence: float = 1.0            # 0.0-1.0 how certain
    compressed: bool = False           # True if this is a summary

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )

    @property
    def is_protected(self) -> bool:
        """Whether this entry survives compression."""
        return self.category in PROTECTED_CATEGORIES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "tool_call": self.tool_call,
            "confidence": self.confidence,
            "compressed": self.compressed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningEntry":
        return cls(
            category=EntryCategory(data["category"]),
            content=data["content"],
            timestamp=data.get("timestamp", ""),
            tool_call=data.get("tool_call"),
            confidence=data.get("confidence", 1.0),
            compressed=data.get("compressed", False),
        )


# =============================================================================
# REASONING CONTEXT
# =============================================================================

@dataclass
class ReasoningContext:
    """Persistent reasoning state for a single agent chain.

    Tracks the agent's reasoning across tool calls, preserving
    decisions, questions, and plans while compressing observations.
    """
    chain_id: str
    intent: str                            # What the chain is trying to do
    entries: List[ReasoningEntry] = field(default_factory=list)
    tool_chain: List[str] = field(default_factory=list)  # Ordered tool calls
    created_at: str = ""
    archived: bool = False

    # Compression config
    max_uncompressed: int = 50             # Trigger compression above this
    target_after_compression: int = 25     # Target entry count after compression

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )

    def add(
        self,
        category: EntryCategory,
        content: str,
        tool_call: Optional[str] = None,
        confidence: float = 1.0,
    ) -> ReasoningEntry:
        """Add an entry to the reasoning trace."""
        entry = ReasoningEntry(
            category=category,
            content=content,
            tool_call=tool_call,
            confidence=confidence,
        )
        self.entries.append(entry)
        if tool_call and tool_call not in self.tool_chain:
            self.tool_chain.append(tool_call)

        # Auto-compress if over threshold
        if len(self.entries) > self.max_uncompressed:
            self.compress_if_needed()

        return entry

    def decisions(self) -> List[ReasoningEntry]:
        """Get all active decisions."""
        return [e for e in self.entries if e.category == EntryCategory.DECISION]

    def questions(self) -> List[ReasoningEntry]:
        """Get all unresolved questions."""
        return [e for e in self.entries if e.category == EntryCategory.QUESTION]

    def plans(self) -> List[ReasoningEntry]:
        """Get all planned next steps."""
        return [e for e in self.entries if e.category == EntryCategory.PLAN]

    def compress_if_needed(self) -> bool:
        """Compress compressible entries if over threshold.

        Protected entries (DECISION, QUESTION, PLAN) are never compressed.
        Compressible entries are grouped and summarized.

        Returns:
            True if compression occurred.
        """
        if len(self.entries) <= self.max_uncompressed:
            return False

        protected = [e for e in self.entries if e.is_protected]
        compressible = [
            e for e in self.entries
            if not e.is_protected and not e.compressed
        ]
        already_compressed = [e for e in self.entries if e.compressed]

        if not compressible:
            return False

        # Group compressible by category and summarize
        by_category: Dict[EntryCategory, List[str]] = {}
        for e in compressible:
            by_category.setdefault(e.category, []).append(e.content)

        summaries: List[ReasoningEntry] = []
        for cat in sorted(by_category.keys(), key=lambda c: c.value):
            contents = by_category[cat]
            # Keep the WHAT, drop the HOW
            summary_text = f"[{len(contents)} {cat.value}s] " + "; ".join(
                c[:80] for c in contents[:5]
            )
            if len(contents) > 5:
                summary_text += f"; ... and {len(contents) - 5} more"

            summaries.append(ReasoningEntry(
                category=cat,
                content=summary_text,
                compressed=True,
            ))

        # Rebuild entries: protected first, then compressed summaries
        self.entries = protected + already_compressed + summaries
        return True

    def summarize(self) -> str:
        """Generate a human-readable summary of the reasoning state.

        Includes all protected entries and compressed summaries.
        """
        lines = [f"Chain: {self.chain_id}", f"Intent: {self.intent}"]

        if self.tool_chain:
            lines.append(f"Tools: {' -> '.join(self.tool_chain)}")

        for cat in (EntryCategory.DECISION, EntryCategory.QUESTION, EntryCategory.PLAN):
            cat_entries = [e for e in self.entries if e.category == cat]
            if cat_entries:
                lines.append(f"\n{cat.value.upper()}S:")
                for e in cat_entries:
                    prefix = "[compressed] " if e.compressed else ""
                    lines.append(f"  - {prefix}{e.content}")

        # Compressed observation/analysis counts
        compressed = [e for e in self.entries if e.compressed]
        if compressed:
            lines.append(f"\n({len(compressed)} compressed entries)")

        return "\n".join(lines)

    def to_memory_record(self) -> Dict[str, Any]:
        """Export as a memory record for Synapse memory storage.

        Preserves all protected entries and the tool chain.
        Suitable for writing to the JSONL memory store.
        """
        return {
            "type": "reasoning_context",
            "chain_id": self.chain_id,
            "intent": self.intent,
            "created_at": self.created_at,
            "tool_chain": list(self.tool_chain),
            "decisions": [e.to_dict() for e in self.decisions()],
            "questions": [e.to_dict() for e in self.questions()],
            "plans": [e.to_dict() for e in self.plans()],
            "entry_count": len(self.entries),
            "protected_count": sum(1 for e in self.entries if e.is_protected),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "intent": self.intent,
            "entries": [e.to_dict() for e in self.entries],
            "tool_chain": list(self.tool_chain),
            "created_at": self.created_at,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningContext":
        ctx = cls(
            chain_id=data["chain_id"],
            intent=data["intent"],
            tool_chain=data.get("tool_chain", []),
            created_at=data.get("created_at", ""),
            archived=data.get("archived", False),
        )
        ctx.entries = [
            ReasoningEntry.from_dict(e) for e in data.get("entries", [])
        ]
        return ctx


# =============================================================================
# CONTEXT MANAGER
# =============================================================================

class ReasoningContextManager:
    """Manages multiple reasoning contexts across agent chains.

    Each chain_id gets its own context. Archived contexts are
    retained for memory export but not actively updated.
    """

    def __init__(self):
        self._contexts: Dict[str, ReasoningContext] = {}

    @property
    def active_count(self) -> int:
        return sum(
            1 for ctx in self._contexts.values() if not ctx.archived
        )

    @property
    def total_count(self) -> int:
        return len(self._contexts)

    def create(self, intent: str, chain_id: Optional[str] = None) -> ReasoningContext:
        """Create a new reasoning context for an agent chain."""
        if chain_id is None:
            chain_id = deterministic_uuid(
                f"{intent}:{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
                "chain",
            )
        ctx = ReasoningContext(chain_id=chain_id, intent=intent)
        self._contexts[chain_id] = ctx
        return ctx

    def get(self, chain_id: str) -> Optional[ReasoningContext]:
        """Get a context by chain ID."""
        return self._contexts.get(chain_id)

    def archive(self, chain_id: str) -> Optional[ReasoningContext]:
        """Archive a context (mark as no longer active)."""
        ctx = self._contexts.get(chain_id)
        if ctx:
            ctx.archived = True
        return ctx

    def active_contexts(self) -> List[ReasoningContext]:
        """Get all non-archived contexts."""
        return [
            ctx for ctx in self._contexts.values()
            if not ctx.archived
        ]

    def export_all(self) -> List[Dict[str, Any]]:
        """Export all contexts as memory records."""
        return [
            ctx.to_memory_record()
            for ctx in sorted(
                self._contexts.values(),
                key=lambda c: c.created_at,
            )
        ]
