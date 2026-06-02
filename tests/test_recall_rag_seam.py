"""Pins the recall->RAG seam (Mile 3 of the VEX-corpus goal).

The VEX corpus lives in the RAG ``KnowledgeIndex`` (reached via
``synapse_knowledge_lookup``), while ``synapse_recall`` / ``synapse_search``
historically saw only Moneta -- so a mid-session "vex @attrib promote" query
returned nothing. These tests pin that the memory handlers now *additively*
surface RAG hits under a ``knowledge`` key, without disturbing any existing
memory result keys, and that the bridge is a strict no-op when the index is
absent or the query is empty (never raises, never invents).
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "python"))

from synapse.server.handlers_memory import MemoryHandlerMixin  # noqa: E402
from synapse.routing.knowledge import KnowledgeIndex  # noqa: E402

_RAG_ROOT = _ROOT / "rag"


@pytest.fixture
def real_ki():
    """KnowledgeIndex over the repo's real rag/ corpus (skip if absent)."""
    index = _RAG_ROOT / "documentation" / "_metadata" / "semantic_index.json"
    if not index.exists():
        pytest.skip("repo rag/ corpus not present")
    return KnowledgeIndex(rag_root=str(_RAG_ROOT))


class _FakeBridge:
    """Stands in for the SynapseBridge -- returns Moneta-shaped result dicts."""

    def __init__(self, recall_result=None, search_result=None):
        self._recall = recall_result or {
            "query": "", "found": False, "count": 0, "matches": [],
        }
        self._search = search_result or {"query": "", "count": 0, "results": []}

    def handle_memory_recall(self, payload):
        return dict(self._recall)

    def handle_memory_search(self, payload):
        return dict(self._search)


class _Handler(MemoryHandlerMixin):
    """Minimal host for the mixin: stubs the two collaborators it needs."""

    def __init__(self, ki, bridge):
        self._ki = ki
        self._bridge = bridge

    def _get_knowledge_index(self):
        return self._ki

    def _get_bridge(self):
        return self._bridge


# --- RAG reachability: the corpus is actually queryable --------------------

def test_rag_corpus_reachable_for_vex(real_ki):
    """The VEX corpus must be reachable via the index (what recall lacked)."""
    hit = real_ki.lookup("vex attribute promote point")
    assert hit.found
    blob = (hit.answer + hit.topic + hit.reference_file).lower()
    assert any(tok in blob for tok in ("attrib", "vex", "point", "promote"))


# --- Seam: recall/search additively surface RAG ----------------------------

def test_recall_augments_with_knowledge(real_ki):
    h = _Handler(real_ki, _FakeBridge())
    out = h._handle_memory_recall({"query": "vex attribute promote"})
    # existing bridge keys preserved (no regression)
    assert out["found"] is False
    assert out["count"] == 0
    assert "matches" in out
    # additive knowledge block present
    assert out.get("knowledge_found") is True
    assert out["knowledge"]["answer"]


def test_search_augments_with_knowledge(real_ki):
    h = _Handler(real_ki, _FakeBridge())
    out = h._handle_memory_search({"query": "vex noise pattern"})
    assert "results" in out  # bridge key intact
    assert out.get("knowledge_found") is True
    assert out["knowledge"]["topic"]


def test_existing_moneta_results_are_untouched(real_ki):
    """Augmentation must not mutate the bridge's own result payload."""
    bridge = _FakeBridge(search_result={
        "query": "vex", "count": 1,
        "results": [{"id": "m1", "content": "user wrangle", "score": 0.9}],
    })
    h = _Handler(real_ki, bridge)
    out = h._handle_memory_search({"query": "vex"})
    assert out["count"] == 1
    assert out["results"][0]["id"] == "m1"


# --- No-op safety ----------------------------------------------------------

def test_no_knowledge_index_is_noop():
    h = _Handler(None, _FakeBridge())
    out = h._handle_memory_recall({"query": "vex attribute promote"})
    assert out["found"] is False
    assert "knowledge" not in out  # nothing attached when index unavailable


def test_empty_query_is_noop(real_ki):
    h = _Handler(real_ki, _FakeBridge())
    out = h._handle_memory_recall({"query": ""})
    assert "knowledge" not in out
