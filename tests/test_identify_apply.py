"""apply: the only writer. Reversible, never on disk, artist text preserved.

Fake hou objects only — no Houdini. The live path is exercised by
scripts/probe_identify.py under hython.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

from synapse.identify import apply as A


# ── fakes ────────────────────────────────────────────────────────────────────

class _NodeFlag:
    DisplayComment = "DisplayComment"


class _Undos:
    def __init__(self):
        self.group_count = 0
        self.disabler_count = 0
        self.last_label = None

    @contextmanager
    def group(self, label):
        self.group_count += 1
        self.last_label = label
        yield

    @contextmanager
    def disabler(self):
        self.disabler_count += 1
        yield


class _HipFile:
    def __init__(self):
        self.callbacks = []

    def addEventCallback(self, cb):
        self.callbacks.append(cb)

    def removeEventCallback(self, cb):
        if cb in self.callbacks:
            self.callbacks.remove(cb)


class FakeHou:
    def __init__(self):
        self.nodeFlag = _NodeFlag()
        self.undos = _Undos()
        self.hipFile = _HipFile()
        self._nodes = {}

    def node(self, path):
        return self._nodes.get(path)


class FakeNode:
    def __init__(self, hou, path, sid, comment="", flag=False):
        self._path, self._sid = path, sid
        self._comment, self._flag = comment, flag
        hou._nodes[path] = self

    def path(self):
        return self._path

    def sessionId(self):
        return self._sid

    def comment(self):
        return self._comment

    def setComment(self, c):
        self._comment = c

    def isGenericFlagSet(self, flag):
        return self._flag

    def setGenericFlag(self, flag, on):
        self._flag = bool(on)


class FakeEditor:
    def __init__(self):
        self.messages = []

    def flashMessage(self, image, text, seconds):
        self.messages.append(text)


@pytest.fixture
def hou(monkeypatch):
    fake = FakeHou()
    monkeypatch.setattr(A, "hou", fake)
    A._reset_state()
    yield fake
    A._reset_state()


# ── the three byte-identical acceptances ─────────────────────────────────────

def test_show_then_clear_is_byte_identical(hou):
    n = FakeNode(hou, "/obj/geo/box1", 11, comment="artist note", flag=False)
    A.show([(n, ["PolyBevel", "Offset 0.07"])])
    assert A.SENTINEL in n.comment()
    assert n._flag is True
    A.clear([n])
    assert n.comment() == "artist note"
    assert n._flag is False            # prior flag restored


def test_save_strip_reapply_then_clear_byte_identical(hou):
    n = FakeNode(hou, "/obj/geo/box1", 12, comment="artist note", flag=True)
    A.show([(n, ["PolyBevel", "Offset 0.07"])])
    shown = n.comment()

    A.before_save()
    assert A.SENTINEL not in n.comment()          # nothing on disk
    assert n.comment() == "artist note"
    assert hou.undos.disabler_count >= 1          # save edits are undo-disabled

    A.after_save()
    assert n.comment() == shown                   # screen restored

    A.clear([n])
    assert n.comment() == "artist note"


def test_artist_comment_that_quotes_sentinel_in_prose_survives(hou):
    prose = f"see the {A.SENTINEL} block below for details"
    n = FakeNode(hou, "/obj/geo/box1", 13, comment=prose, flag=False)
    A.show([(n, ["PolyBevel", "Offset 0.07"])])
    assert n.comment() != prose                   # our block was appended
    A.clear([n])
    assert n.comment() == prose                   # inline mention untouched


# ── undo, cap, flash ─────────────────────────────────────────────────────────

def test_one_undo_group_per_show_and_per_clear(hou):
    n = FakeNode(hou, "/obj/geo/box1", 21)
    A.show([(n, ["A"])])
    assert hou.undos.group_count == 1
    assert hou.undos.last_label == A.UNDO_LABEL
    A.clear([n])
    assert hou.undos.group_count == 2


def test_cap_and_flash_line(hou):
    items = [(FakeNode(hou, f"/obj/n{i}", 100 + i), ["X"]) for i in range(62)]
    editor = FakeEditor()
    result = A.show(items, editor=editor)
    assert result == {"shown": A.CAP, "total": 62}
    assert editor.messages == [f"Identify: {A.CAP} of 62 nodes"]
    # nodes beyond the cap were never written
    assert items[A.CAP][0].comment() == ""


def test_flag_restored_for_multiple_priors(hou):
    on = FakeNode(hou, "/obj/on", 31, flag=True)
    off = FakeNode(hou, "/obj/off", 32, flag=False)
    A.show([(on, ["A"]), (off, ["B"])])
    A.clear([on, off])
    assert on._flag is True
    assert off._flag is False


# ── toggle, orphans, idempotence ─────────────────────────────────────────────

def test_toggle_is_idempotent(hou):
    n = FakeNode(hou, "/obj/geo/box1", 41, comment="note")
    r1 = A.toggle([(n, ["A"])])
    assert r1["action"] == "show" and A.SENTINEL in n.comment()
    r2 = A.toggle([(n, ["A"])])
    assert r2["action"] == "clear" and n.comment() == "note"


def test_orphan_block_removed_on_clear(hou):
    # A block with no registry entry (e.g. a prior session left it).
    orphan = A._compose_comment("keep me", "PolyBevel\nOffset 0.07")
    n = FakeNode(hou, "/obj/geo/box1", 51, comment=orphan, flag=True)
    A.clear([n])
    assert n.comment() == "keep me"
    assert n._flag is True             # artist text remains -> flag stays on


def test_orphan_with_no_artist_text_clears_flag(hou):
    orphan = A._compose_comment("", "PolyBevel")
    n = FakeNode(hou, "/obj/geo/box1", 52, comment=orphan, flag=True)
    A.clear([n])
    assert n.comment() == ""
    assert n._flag is False


def test_reshow_does_not_stack_blocks(hou):
    n = FakeNode(hou, "/obj/geo/box1", 61, comment="note")
    A.show([(n, ["PolyBevel", "Offset 0.07"])])
    A.show([(n, ["PolyBevel", "Offset 0.09"])])
    assert n.comment().count(A.SENTINEL) == 1
    assert n.comment().startswith("note\n")
    assert "0.09" in n.comment() and "0.07" not in n.comment()


def test_clear_untouched_node_is_noop(hou):
    n = FakeNode(hou, "/obj/geo/box1", 71, comment="plain note", flag=True)
    result = A.clear([n])
    assert result["removed"] == 0
    assert n.comment() == "plain note"


def test_install_and_remove_save_callbacks_idempotent(hou):
    A.install_save_callbacks()
    A.install_save_callbacks()
    assert len(hou.hipFile.callbacks) == 1
    A.remove_save_callbacks()
    assert hou.hipFile.callbacks == []
