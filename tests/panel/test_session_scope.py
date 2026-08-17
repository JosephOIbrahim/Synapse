# W7-SESSCOPE pins (Joe word 2026-08-16): the disk store survives everything;
# the boot scope decides what auto-attaches. Same boot -> reattach (P0.3 stays
# dead). New boot -> park, start clean, restore on command. Nothing is ever
# silently destroyed.
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from synapse.server import session_store as ss  # noqa: E402

MSGS_A = [{"role": "user", "content": "boot A work"}]
MSGS_B = [{"role": "user", "content": "boot B work"}]


def _paths(tmp_path):
    return str(tmp_path / "conversation.json")


def test_same_boot_reattaches(tmp_path):
    p = _paths(tmp_path)
    assert ss.save_conversation(MSGS_A, path=p, token="bootA")
    msgs, scope = ss.load_conversation_scoped(path=p, token="bootA")
    assert scope == "same_boot" and msgs == MSGS_A


def test_new_boot_parks_and_starts_clean(tmp_path):
    p = _paths(tmp_path)
    ss.save_conversation(MSGS_A, path=p, token="bootA")
    msgs, scope = ss.load_conversation_scoped(path=p, token="bootB")
    assert scope == "previous_parked" and msgs == []
    assert not os.path.exists(p)
    assert ss.has_previous_conversation(path=p)


def test_restore_brings_work_back_under_new_boot(tmp_path):
    p = _paths(tmp_path)
    ss.save_conversation(MSGS_A, path=p, token="bootA")
    ss.load_conversation_scoped(path=p, token="bootB")
    restored = ss.restore_previous_conversation(path=p, token="bootB")
    assert restored == MSGS_A
    msgs, scope = ss.load_conversation_scoped(path=p, token="bootB")
    assert scope == "same_boot" and msgs == MSGS_A
    assert not ss.has_previous_conversation(path=p)


def test_restore_with_nothing_parked_is_empty(tmp_path):
    p = _paths(tmp_path)
    assert ss.restore_previous_conversation(path=p, token="bootB") == []


def test_park_replaces_older_previous(tmp_path):
    p = _paths(tmp_path)
    ss.save_conversation(MSGS_A, path=p, token="bootA")
    ss.load_conversation_scoped(path=p, token="bootB")        # parks A
    ss.save_conversation(MSGS_B, path=p, token="bootB")
    msgs, scope = ss.load_conversation_scoped(path=p, token="bootC")  # parks B over A
    assert scope == "previous_parked" and msgs == []
    assert ss.restore_previous_conversation(path=p, token="bootC") == MSGS_B


def test_legacy_unstamped_conversation_parks_safely(tmp_path):
    # Pre-SESSCOPE stores have no owner sidecar: treated as an earlier boot -
    # parked (recoverable), never auto-attached, never destroyed.
    p = _paths(tmp_path)
    import json
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(MSGS_A, fh)
    msgs, scope = ss.load_conversation_scoped(path=p, token="bootB")
    assert scope == "previous_parked" and msgs == []
    assert ss.restore_previous_conversation(path=p, token="bootB") == MSGS_A


def test_empty_store_is_empty_scope(tmp_path):
    msgs, scope = ss.load_conversation_scoped(path=_paths(tmp_path), token="bootA")
    assert msgs == [] and scope == "empty"
