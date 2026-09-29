"""apply: the legacy cleaner, Identify's only scene writer (CRUX F4 closed here).

Older versions appended their bubble below a ``~ identify ~`` line in the node
comment. The overlay writes nothing, and this cleaner removes an old block only
when it has the exact shape Identify wrote. Fake ``hou`` objects only.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

from synapse.identify import apply as A
from synapse.identify import compose as C

WHAT = "Bevels points and edges."
WHATS = frozenset({WHAT, "PolyBevel - not in library"})


class _NodeFlag:
    DisplayComment = "DisplayComment"


class _Undos:
    def __init__(self):
        self.groups = []

    @contextmanager
    def group(self, label):
        self.groups.append(label)
        yield


class FakeHou:
    def __init__(self):
        self.nodeFlag = _NodeFlag()
        self.undos = _Undos()


class FakeNode:
    def __init__(self, comment="", flag=False):
        self._comment, self._flag = comment, flag
        self.writes = 0

    def comment(self):
        return self._comment

    def setComment(self, text):
        self.writes += 1
        self._comment = text

    def isGenericFlagSet(self, flag):
        return self._flag

    def setGenericFlag(self, flag, on):
        self._flag = bool(on)


@pytest.fixture
def hou(monkeypatch):
    fake = FakeHou()
    monkeypatch.setattr(A, "hou", fake)
    return fake


def _block(*lines):
    return "\n".join((A.SENTINEL,) + lines)


def test_an_old_block_is_removed_and_the_artist_text_stays_byte_identical(hou):
    artist = "keep this\n  indented line\n"
    node = FakeNode(artist + "\n" + _block(WHAT, "Offset 0.07"), flag=True)
    assert A.clean_legacy([(node, WHATS)]) == 1
    assert node.comment() == artist
    assert node._flag is True
    assert hou.undos.groups == [A.UNDO_LABEL]


def test_a_block_alone_leaves_an_empty_comment_with_the_display_off(hou):
    node = FakeNode(_block(WHAT), flag=True)
    A.clean_legacy([(node, WHATS)])
    assert node.comment() == ""
    assert node._flag is False


def test_the_not_in_library_form_counts_too(hou):
    node = FakeNode(_block("PolyBevel - not in library", "bypassed"))
    assert A.clean_legacy([(node, WHATS)]) == 1


def test_f4_an_artist_sentinel_line_with_their_own_text_survives(hou):
    comment = "notes\n~ identify ~\nmy own line about this node"
    node = FakeNode(comment, flag=True)
    assert A.clean_legacy([(node, WHATS)]) == 0
    assert node.comment() == comment and node.writes == 0
    assert hou.undos.groups == []


def test_f4_a_sentinel_followed_by_too_many_lines_is_artist_text(hou):
    comment = _block(WHAT, "a", "b", "c")
    node = FakeNode(comment)
    assert A.clean_legacy([(node, WHATS)]) == 0
    assert node.comment() == comment


def test_f4_a_line_longer_than_identify_ever_wrote_is_artist_text(hou):
    comment = _block(WHAT, "x" * (C.WIDTH + 1))
    assert A.clean_legacy([(FakeNode(comment), WHATS)]) == 0


def test_a_sentinel_quoted_inside_prose_is_never_a_block(hou):
    comment = f"see the {A.SENTINEL} marker\n{WHAT}"
    assert A.legacy_block_start(comment, WHATS) == -1


def test_a_trailing_sentinel_with_nothing_after_it_is_left_alone(hou):
    assert A.legacy_block_start("text\n" + A.SENTINEL, WHATS) == -1


def test_nothing_to_clean_writes_nothing_and_opens_no_undo_group(hou):
    nodes = [FakeNode("plain"), FakeNode("")]
    assert A.clean_legacy([(n, WHATS) for n in nodes]) == 0
    assert all(n.writes == 0 for n in nodes)
    assert hou.undos.groups == []


def test_one_undo_group_covers_every_node_in_a_cleanup(hou):
    nodes = [FakeNode(_block(WHAT)) for _ in range(3)]
    assert A.clean_legacy([(n, WHATS) for n in nodes]) == 3
    assert hou.undos.groups == [A.UNDO_LABEL]


def test_strip_legacy_is_a_no_op_without_a_block():
    assert A.strip_legacy("artist only", WHATS) == "artist only"
    assert A.strip_legacy(None, WHATS) == ""
