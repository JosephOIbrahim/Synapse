"""
Tests for reasoning_context.py (v8-DSA)

Covers: protected categories survive compression, summarize includes
all protected, tool chain ordering, memory record export, concurrent
contexts via manager.
"""

import sys
import os

_SYNAPSE_ROOT = os.path.join(os.path.dirname(__file__), "..", "python")
if _SYNAPSE_ROOT not in sys.path:
    sys.path.insert(0, _SYNAPSE_ROOT)

import pytest

from synapse.agent.reasoning_context import (
    EntryCategory,
    PROTECTED_CATEGORIES,
    ReasoningContext,
    ReasoningContextManager,
    ReasoningEntry,
)


# ---------------------------------------------------------------------------
# Tests: ReasoningEntry
# ---------------------------------------------------------------------------

class TestReasoningEntry:
    def test_protected_decision(self):
        e = ReasoningEntry(category=EntryCategory.DECISION, content="Use Karma XPU")
        assert e.is_protected is True

    def test_protected_question(self):
        e = ReasoningEntry(category=EntryCategory.QUESTION, content="Which camera?")
        assert e.is_protected is True

    def test_protected_plan(self):
        e = ReasoningEntry(category=EntryCategory.PLAN, content="Create light next")
        assert e.is_protected is True

    def test_not_protected_observation(self):
        e = ReasoningEntry(category=EntryCategory.OBSERVATION, content="Node created")
        assert e.is_protected is False

    def test_not_protected_analysis(self):
        e = ReasoningEntry(category=EntryCategory.ANALYSIS, content="Looks good")
        assert e.is_protected is False

    def test_not_protected_context(self):
        e = ReasoningEntry(category=EntryCategory.CONTEXT, content="Background")
        assert e.is_protected is False

    def test_to_dict_roundtrip(self):
        e = ReasoningEntry(
            category=EntryCategory.DECISION,
            content="Use exposure for brightness",
            tool_call="set_usd_attribute",
            confidence=0.95,
        )
        d = e.to_dict()
        e2 = ReasoningEntry.from_dict(d)
        assert e2.category == e.category
        assert e2.content == e.content
        assert e2.tool_call == e.tool_call
        assert e2.confidence == e.confidence

    def test_timestamp_auto_generated(self):
        e = ReasoningEntry(category=EntryCategory.CONTEXT, content="test")
        assert e.timestamp != ""
        assert "T" in e.timestamp


# ---------------------------------------------------------------------------
# Tests: ReasoningContext
# ---------------------------------------------------------------------------

class TestReasoningContext:
    def test_add_entries(self):
        ctx = ReasoningContext(chain_id="test", intent="Set up lighting")
        ctx.add(EntryCategory.DECISION, "Use 3-point rig")
        ctx.add(EntryCategory.OBSERVATION, "Key light created", tool_call="create_usd_prim")
        assert len(ctx.entries) == 2

    def test_tool_chain_ordering(self):
        ctx = ReasoningContext(chain_id="test", intent="Build scene")
        ctx.add(EntryCategory.OBSERVATION, "geo", tool_call="create_node")
        ctx.add(EntryCategory.OBSERVATION, "light", tool_call="create_usd_prim")
        ctx.add(EntryCategory.OBSERVATION, "render", tool_call="render")
        assert ctx.tool_chain == ["create_node", "create_usd_prim", "render"]

    def test_tool_chain_dedup(self):
        ctx = ReasoningContext(chain_id="test", intent="test")
        ctx.add(EntryCategory.OBSERVATION, "a", tool_call="set_parm")
        ctx.add(EntryCategory.OBSERVATION, "b", tool_call="set_parm")
        assert ctx.tool_chain == ["set_parm"]

    def test_decisions_filter(self):
        ctx = ReasoningContext(chain_id="test", intent="test")
        ctx.add(EntryCategory.DECISION, "d1")
        ctx.add(EntryCategory.OBSERVATION, "o1")
        ctx.add(EntryCategory.DECISION, "d2")
        assert len(ctx.decisions()) == 2

    def test_questions_filter(self):
        ctx = ReasoningContext(chain_id="test", intent="test")
        ctx.add(EntryCategory.QUESTION, "q1")
        ctx.add(EntryCategory.OBSERVATION, "o1")
        assert len(ctx.questions()) == 1

    def test_plans_filter(self):
        ctx = ReasoningContext(chain_id="test", intent="test")
        ctx.add(EntryCategory.PLAN, "p1")
        ctx.add(EntryCategory.PLAN, "p2")
        assert len(ctx.plans()) == 2

    def test_compression_preserves_protected(self):
        ctx = ReasoningContext(
            chain_id="test", intent="test",
            max_uncompressed=10, target_after_compression=5,
        )
        # Add 3 protected entries
        ctx.add(EntryCategory.DECISION, "decision 1")
        ctx.add(EntryCategory.QUESTION, "question 1")
        ctx.add(EntryCategory.PLAN, "plan 1")

        # Add 15 compressible entries to trigger compression
        for i in range(15):
            ctx.add(EntryCategory.OBSERVATION, f"observation {i}")

        # Compression should have been triggered
        assert len(ctx.entries) < 18  # 3 protected + 15 obs

        # All protected entries must survive
        assert len(ctx.decisions()) == 1
        assert len(ctx.questions()) == 1
        assert len(ctx.plans()) == 1

    def test_compression_creates_summaries(self):
        ctx = ReasoningContext(
            chain_id="test", intent="test",
            max_uncompressed=5, target_after_compression=3,
        )
        for i in range(10):
            ctx.add(EntryCategory.OBSERVATION, f"obs {i}")

        compressed = [e for e in ctx.entries if e.compressed]
        assert len(compressed) > 0

    def test_no_compression_under_threshold(self):
        ctx = ReasoningContext(
            chain_id="test", intent="test",
            max_uncompressed=100,
        )
        for i in range(5):
            ctx.add(EntryCategory.OBSERVATION, f"obs {i}")

        result = ctx.compress_if_needed()
        assert result is False
        assert len(ctx.entries) == 5

    def test_summarize_includes_protected(self):
        ctx = ReasoningContext(chain_id="c1", intent="Build lighting rig")
        ctx.add(EntryCategory.DECISION, "Use Karma XPU")
        ctx.add(EntryCategory.QUESTION, "Which HDRI?")
        ctx.add(EntryCategory.PLAN, "Add fill light next")
        ctx.add(EntryCategory.OBSERVATION, "Key light created")

        summary = ctx.summarize()
        assert "Use Karma XPU" in summary
        assert "Which HDRI?" in summary
        assert "Add fill light next" in summary
        assert "Build lighting rig" in summary

    def test_summarize_includes_tool_chain(self):
        ctx = ReasoningContext(chain_id="c1", intent="test")
        ctx.add(EntryCategory.OBSERVATION, "a", tool_call="create_node")
        ctx.add(EntryCategory.OBSERVATION, "b", tool_call="render")

        summary = ctx.summarize()
        assert "create_node" in summary
        assert "render" in summary

    def test_to_memory_record(self):
        ctx = ReasoningContext(chain_id="c1", intent="Lighting setup")
        ctx.add(EntryCategory.DECISION, "3-point rig")
        ctx.add(EntryCategory.OBSERVATION, "key created", tool_call="create_usd_prim")
        ctx.add(EntryCategory.QUESTION, "HDRI choice?")

        record = ctx.to_memory_record()
        assert record["type"] == "reasoning_context"
        assert record["chain_id"] == "c1"
        assert record["intent"] == "Lighting setup"
        assert len(record["decisions"]) == 1
        assert len(record["questions"]) == 1
        assert "create_usd_prim" in record["tool_chain"]
        assert record["entry_count"] == 3
        assert record["protected_count"] == 2

    def test_to_dict_roundtrip(self):
        ctx = ReasoningContext(chain_id="c1", intent="test")
        ctx.add(EntryCategory.DECISION, "d1")
        ctx.add(EntryCategory.OBSERVATION, "o1", tool_call="ping")

        d = ctx.to_dict()
        ctx2 = ReasoningContext.from_dict(d)
        assert ctx2.chain_id == "c1"
        assert ctx2.intent == "test"
        assert len(ctx2.entries) == 2
        assert ctx2.tool_chain == ["ping"]


# ---------------------------------------------------------------------------
# Tests: ReasoningContextManager
# ---------------------------------------------------------------------------

class TestReasoningContextManager:
    def test_create_and_get(self):
        mgr = ReasoningContextManager()
        ctx = mgr.create("Build scene", chain_id="chain1")
        assert ctx.chain_id == "chain1"

        retrieved = mgr.get("chain1")
        assert retrieved is ctx

    def test_auto_generate_chain_id(self):
        mgr = ReasoningContextManager()
        ctx = mgr.create("Auto ID test")
        assert ctx.chain_id != ""
        assert mgr.get(ctx.chain_id) is ctx

    def test_active_count(self):
        mgr = ReasoningContextManager()
        mgr.create("a", chain_id="c1")
        mgr.create("b", chain_id="c2")
        assert mgr.active_count == 2

    def test_archive(self):
        mgr = ReasoningContextManager()
        mgr.create("a", chain_id="c1")
        mgr.archive("c1")
        assert mgr.active_count == 0
        assert mgr.total_count == 1

    def test_active_contexts_excludes_archived(self):
        mgr = ReasoningContextManager()
        mgr.create("a", chain_id="c1")
        mgr.create("b", chain_id="c2")
        mgr.archive("c1")
        active = mgr.active_contexts()
        assert len(active) == 1
        assert active[0].chain_id == "c2"

    def test_export_all(self):
        mgr = ReasoningContextManager()
        ctx1 = mgr.create("a", chain_id="c1")
        ctx1.add(EntryCategory.DECISION, "d1")
        ctx2 = mgr.create("b", chain_id="c2")
        ctx2.add(EntryCategory.PLAN, "p1")

        records = mgr.export_all()
        assert len(records) == 2
        assert all(r["type"] == "reasoning_context" for r in records)

    def test_get_nonexistent_returns_none(self):
        mgr = ReasoningContextManager()
        assert mgr.get("nonexistent") is None

    def test_concurrent_contexts(self):
        """Multiple active contexts don't interfere with each other."""
        mgr = ReasoningContextManager()
        ctx1 = mgr.create("Lighting", chain_id="c1")
        ctx2 = mgr.create("Materials", chain_id="c2")

        ctx1.add(EntryCategory.DECISION, "Karma XPU")
        ctx2.add(EntryCategory.DECISION, "MaterialX")
        ctx1.add(EntryCategory.OBSERVATION, "key light", tool_call="create_usd_prim")
        ctx2.add(EntryCategory.OBSERVATION, "shader", tool_call="create_material")

        assert len(ctx1.decisions()) == 1
        assert ctx1.decisions()[0].content == "Karma XPU"
        assert len(ctx2.decisions()) == 1
        assert ctx2.decisions()[0].content == "MaterialX"
        assert ctx1.tool_chain == ["create_usd_prim"]
        assert ctx2.tool_chain == ["create_material"]
