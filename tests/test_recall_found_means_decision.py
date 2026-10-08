"""Recall plan Phase 4: at scope=all, ``found`` means a remembered decision.

The recall handler appends a reference-docs (knowledge) row to ``matches``
when scope is ``all``. That row is context, not memory, so it must never turn
``found`` true on its own. An empty store asked at scope=all answers
found=false and still carries the knowledge row.

No sys.path insert here on purpose: the module is resolved through
PYTHONPATH, so a fail-on-base run against an archived tree tests that tree.
"""

from types import SimpleNamespace

import pytest

from synapse.server.handlers_memory import MemoryHandlerMixin


class _FakeKnowledge:
    """Deterministic stand-in for KnowledgeIndex (always finds one article)."""

    def lookup(self, query):
        return SimpleNamespace(
            found=True,
            answer="VEX: use attribpromote to move attributes between classes.",
            summary="attribpromote reference",
            confidence=0.9,
            topic="vex_attributes",
            sources=["vex/attribpromote.md"],
            reference_file="vex/attribpromote.md",
        )


class _FakeBridge:
    """Returns a fresh Moneta-shaped recall dict on every call."""

    def __init__(self, matches=()):
        self._matches = [dict(m) for m in matches]

    def handle_memory_recall(self, payload):
        matches = [dict(m) for m in self._matches]
        return {
            "query": payload.get("query", ""),
            "found": bool(matches),
            "count": len(matches),
            "matches": matches,
        }


class _Handler(MemoryHandlerMixin):
    def __init__(self, bridge, ki=None):
        self._bridge = bridge
        self._ki = _FakeKnowledge() if ki is None else ki

    def _get_knowledge_index(self):
        return self._ki

    def _get_bridge(self):
        return self._bridge


_DECISION = {
    "id": "dec_coral", "summary": "Warm coral look",
    "content": "Use warm coral for the product look", "date": "2026-10-07",
}


@pytest.mark.parametrize("payload", [
    {"query": "vex attribute promote", "scope": "all"},
    {"query": "vex attribute promote"},  # recall's default scope is all
], ids=["explicit-all", "default-scope"])
def test_empty_store_scope_all_is_not_found_but_keeps_knowledge(payload):
    out = _Handler(_FakeBridge())._handle_memory_recall(payload)
    assert out["found"] is False
    assert [m["source"] for m in out["matches"]] == ["knowledge"]
    assert out["count"] == 1
    assert out["knowledge_found"] is True
    assert out["knowledge"]["topic"] == "vex_attributes"


def test_decision_match_stays_found_with_knowledge_appended():
    out = _Handler(_FakeBridge([_DECISION]))._handle_memory_recall(
        {"query": "coral look", "scope": "all"})
    assert out["found"] is True
    assert out["matches"][0]["id"] == "dec_coral"
    assert out["matches"][1]["source"] == "knowledge"
    assert out["count"] == 2


@pytest.mark.parametrize("matches,found", [((), False), ((_DECISION,), True)])
def test_scope_project_has_no_knowledge_row(matches, found):
    out = _Handler(_FakeBridge(matches))._handle_memory_recall(
        {"query": "coral look", "scope": "project"})
    assert out["found"] is found
    assert all(m.get("source") != "knowledge" for m in out["matches"])
    assert "knowledge" not in out
