"""The "what I remember" card shows memory, never a knowledge-corpus article.

Seen in Houdini on 2026-10-03: synapse_recall found no memory for the query and
fell back to one knowledge article about heightfield terrain. The card showed
that article as a HIT under "what I remember", under every reply that followed.
"""
from synapse.panel.recall_card import recall_view

KNOWLEDGE = {"content": "Terrain creation with heightfields", "id": "knowledge_2712", "source": "knowledge"}
MEMORY = {"content": "scale 2.1362 from two doorways taken as 2.10 m", "id": "ddd-rc4-9e121f"}


def test_a_knowledge_only_recall_is_not_a_hit():
    view = recall_view({"count": 1, "found": True, "matches": [KNOWLEDGE]})
    assert view == {"status": "KNOWLEDGE", "deposit": "UNKNOWN"}


def test_a_memory_match_is_still_a_hit():
    view = recall_view({"count": 1, "found": True, "matches": [MEMORY]})
    assert view == {"status": "HIT", "deposit": MEMORY["content"]}


def test_a_mixed_recall_shows_only_the_memory():
    view = recall_view({"count": 2, "found": True, "matches": [KNOWLEDGE, MEMORY]})
    assert view == {"status": "HIT", "deposit": MEMORY["content"]}
