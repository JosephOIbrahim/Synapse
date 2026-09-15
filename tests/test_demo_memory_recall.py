"""Reproduce the capture's ordinary-recall misses using real persisted records."""
import pytest

from synapse.memory import store as memory_store
from synapse.memory.models import Memory, MemoryType


@pytest.fixture
def memory(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_store, "HOU_AVAILABLE", False)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    instance = memory_store.SynapseMemory(str(tmp_path))
    yield instance
    instance.save()


@pytest.mark.parametrize("query", [
    "look decision",
    "look decision product display demo",
    "What was the look decision for our product display demo?",
    "CORAL, copper charcoal",
])
def test_demo_question_recalls_canonical_id_after_reopen(memory, query):
    decision = memory.decision(
        "Hero product display look: warm coral sphere, copper torus, charcoal plinth.",
        "This is the approved look for the demo display.",
    )
    memory.save()
    reopened = memory_store.SynapseMemory(str(memory.project_path))
    assert [row.id for row in reopened.recall(query)] == [decision.id]
    assert reopened.recall(query)[0].content == decision.content


def test_recall_does_not_widen_to_one_shared_word_or_another_kind(memory):
    memory.decision("Coral hero display", "Approved product look.")
    memory.add("Coral submarine display", memory_type=MemoryType.NOTE)
    assert memory.recall("coral submarine") == []
    assert memory.recall("oral") == []
    assert memory.recall("submarine", kinds=[MemoryType.NOTE])


def test_keyword_recall_keeps_deterministic_order_and_limit(memory):
    for record_id, date in [("old", "2026-01-01"), ("b", "2026-09-09"), ("a", "2026-09-09")]:
        memory.store.add(Memory(
            id=record_id, created_at=date, updated_at=date,
            content="**Decision:** Warm coral product display look.",
            memory_type=MemoryType.DECISION,
        ))
    assert [row.id for row in memory.recall("look decision", limit=2)] == ["a", "b"]
    assert [row.id for row in memory.recall("", limit=2)] == ["a", "b"]
