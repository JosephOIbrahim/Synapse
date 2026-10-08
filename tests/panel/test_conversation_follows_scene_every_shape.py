"""PUX-01c: every Save As shape, followed by one, two or three panels.

Scene A (or an untitled scene) and the destination B each start in one of four
states: no files, a chat, only a parked previous, or both. One to three panels
pinned to the source follow the same Save As into B. The first panel defines
the outcome (the single-panel park design: B's chat is parked into B's one
previous slot, replacing an older previous, and A's previous travels only into
an empty slot). Every later panel is a follower and must change nothing.

On 74b0e52d a first panel that found nothing to carry or park (no chat at the
source, no chat at B) left no carry record, so the second panel parked the
first one's freshly saved chat into B's previous slot: B's own previous was
destroyed when B held only a previous, and a stray copy of the live chat was
parked when B was empty. Each row asserts the exact files left behind.

Helpers come from the hardening module (same fake panel, real method source,
no SynapsePanel built).
"""
from __future__ import annotations

import itertools

import pytest

from .test_conversation_follows_scene_hardening import (  # noqa: F401 -- fixtures
    CHAT_A, CHAT_B, EVENTS, PARKED, _fresh_carry_record, _panel, _prev,
    _read, _seed, scenes)

B_PREVIOUS = [{"role": "user", "content": "B's own previous boot"}]
STATES = ("none", "chat", "prev", "both")
CASES = list(itertools.product(("A", "untitled"), STATES, STATES, (1, 2, 3)))


def _seed_state(store, state, chat, previous):
    if state in ("chat", "both"):
        _seed(store, chat)
    if state in ("prev", "both"):
        _seed(_prev(store), previous)


def _files(store):
    """Conversation files in one store folder, by name (owner sidecars aside)."""
    folder = store.parent
    if not folder.exists():
        return {}
    return {p.name: _read(p) for p in folder.iterdir()
            if p.name.startswith("conversation") and p.name.endswith(".json")
            and not p.name.endswith(".owner.json")}


def _expected(src_state, dst_state):
    """What one panel's Save As leaves at the source and at B."""
    dst = {"conversation.json": CHAT_A}
    src = {}
    if dst_state in ("chat", "both"):
        dst["conversation.previous.json"] = CHAT_B      # B's chat is parked
    elif dst_state == "prev":
        dst["conversation.previous.json"] = B_PREVIOUS  # B's slot is kept
    if src_state in ("prev", "both"):
        if dst_state == "none":
            dst["conversation.previous.json"] = PARKED  # carried into the free slot
        else:
            src["conversation.previous.json"] = PARKED  # slot taken: stays at A
    return src, dst


@pytest.mark.parametrize("source,src_state,dst_state,panels", CASES,
                         ids=["%s-%s-%s-%d" % case for case in CASES])
def test_every_follower_count_leaves_the_single_panel_outcome(
        scenes, source, src_state, dst_state, panels):
    scenes.open(source)
    _seed_state(scenes.store(source), src_state, CHAT_A, PARKED)
    _seed_state(scenes.store("B"), dst_state, CHAT_B, B_PREVIOUS)
    followers = [_panel(CHAT_A) for _ in range(panels)]

    scenes.open("B")
    for panel in followers:
        panel._on_hip_event(EVENTS.AfterSave)

    want_src, want_dst = _expected(src_state, dst_state)
    assert _files(scenes.store(source)) == want_src
    assert _files(scenes.store("B")) == want_dst
    for panel in followers:
        assert panel._conversation_path == str(scenes.store("B"))
