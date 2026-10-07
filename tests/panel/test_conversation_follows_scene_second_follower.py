"""PUX-01b re-review: the second follower when the destination previous slot is taken.

Two panels pinned to scene A both follow a Save As into B. When A has a chat
AND a parked previous and B already holds something (its own chat, or only its
own previous), the first panel parks B's chat into B's previous slot (or finds
that slot already full) and so leaves A's previous where it is. The old guard
then let the second panel through - A's previous still existed - and it parked
the first panel's chat over B's previous, destroying B's chat (r2) or B's
previous (r3). A follower whose store was already carried here now changes
nothing; A's uncarried previous stays at A.

Every test asserts that every chat and every previous survives somewhere.
The panel helpers are imported from the hardening module (same fake panel,
real method source, no SynapsePanel built).
"""
from __future__ import annotations

from synapse.server import session_store

from .test_conversation_follows_scene_hardening import (  # noqa: F401 -- fixtures
    CHAT_A, CHAT_B, EVENTS, PARKED, _all_chats, _fresh_carry_record, _panel,
    _prev, _read, _seed, scenes)

B_PREVIOUS = [{"role": "user", "content": "B's own previous boot"}]


def _everything(scenes):
    return _all_chats(scenes.store("A").parent, scenes.store("B").parent)


def _two_panels_follow(scenes):
    p1, p2 = _panel(CHAT_A), _panel(CHAT_A)
    scenes.open("B")
    p1._on_hip_event(EVENTS.AfterSave)
    p2._on_hip_event(EVENTS.AfterSave)


def test_r2_second_follower_keeps_b_own_chat(scenes):
    """A: chat + previous. B: its own chat. B's chat must survive."""
    _seed(scenes.store("A"), CHAT_A)
    _seed(_prev(scenes.store("A")), PARKED)
    _seed(scenes.store("B"), CHAT_B)

    _two_panels_follow(scenes)

    found = _everything(scenes)
    assert CHAT_B in found, "B's own chat destroyed by the second follower"
    assert PARKED in found
    assert CHAT_A in found
    assert _read(scenes.store("B")) == CHAT_A
    assert _read(_prev(scenes.store("B"))) == CHAT_B
    assert _read(_prev(scenes.store("A"))) == PARKED   # never carried, left in place


def test_r3_second_follower_keeps_b_own_previous(scenes):
    """A: chat + previous. B: only a previous. B's previous must survive."""
    _seed(scenes.store("A"), CHAT_A)
    _seed(_prev(scenes.store("A")), PARKED)
    _seed(_prev(scenes.store("B")), B_PREVIOUS)

    _two_panels_follow(scenes)

    found = _everything(scenes)
    assert B_PREVIOUS in found, "B's previous destroyed by the second follower"
    assert PARKED in found
    assert CHAT_A in found
    assert _read(scenes.store("B")) == CHAT_A
    assert _read(_prev(scenes.store("B"))) == B_PREVIOUS
    assert _read(_prev(scenes.store("A"))) == PARKED


def test_r2_shape_three_followers_keep_everything(scenes):
    """A third panel on the same Save As changes nothing more."""
    _seed(scenes.store("A"), CHAT_A)
    _seed(_prev(scenes.store("A")), PARKED)
    _seed(scenes.store("B"), CHAT_B)
    panels = [_panel(CHAT_A) for _ in range(3)]
    scenes.open("B")
    for panel in panels:
        panel._on_hip_event(EVENTS.AfterSave)

    found = _everything(scenes)
    assert CHAT_B in found and PARKED in found and CHAT_A in found


def test_single_panel_r2_shape_keeps_everything(scenes):
    """Baseline: one follower in the r2 shape (B has its own chat)."""
    _seed(scenes.store("A"), CHAT_A)
    _seed(_prev(scenes.store("A")), PARKED)
    _seed(scenes.store("B"), CHAT_B)
    panel = _panel(CHAT_A)
    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterSave)

    found = _everything(scenes)
    assert CHAT_B in found and PARKED in found and CHAT_A in found


def test_single_panel_r3_shape_keeps_everything(scenes):
    """Baseline: one follower in the r3 shape (B has only a previous)."""
    _seed(scenes.store("A"), CHAT_A)
    _seed(_prev(scenes.store("A")), PARKED)
    _seed(_prev(scenes.store("B")), B_PREVIOUS)
    panel = _panel(CHAT_A)
    scenes.open("B")
    panel._on_hip_event(EVENTS.AfterSave)

    found = _everything(scenes)
    assert B_PREVIOUS in found and PARKED in found and CHAT_A in found


def test_move_conversation_second_follower_with_taken_slot_changes_nothing(tmp_path):
    """Store level: the source previous was NOT carried (slot taken), so it
    still exists at the source; the second call must still change nothing."""
    src = tmp_path / "a" / "claude" / "conversation.json"
    dst = tmp_path / "b" / "claude" / "conversation.json"
    _seed(src, CHAT_A)
    _seed(_prev(src), PARKED)
    _seed(_prev(dst), B_PREVIOUS)

    assert session_store.move_conversation(str(src), str(dst)) is True
    assert _read(_prev(src)) == PARKED                  # slot was taken: stays
    _seed(dst, CHAT_A)                                  # panel 1's save
    assert session_store.move_conversation(str(src), str(dst)) is False

    assert _read(_prev(dst)) == B_PREVIOUS
    assert _read(_prev(src)) == PARKED
    assert _read(dst) == CHAT_A
