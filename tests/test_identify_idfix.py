"""BP11-IDFIX: the save callbacks are installed by ``show`` on the product path.

G6 failed because ``install_save_callbacks`` was only ever called by a probe and
a test, never by ``show``/``toggle``/``/identify`` — so a GUI save with bubbles
shown kept every sentinel on disk. These tests pin the fix at the unit level:
``show`` registers the hipFile callback exactly once (idempotently), and the
BeforeSave/AfterSave pair strips *every* shown block and restores every one.

Fake ``hou`` only — no Houdini. The live disk round trip is proved headless by
``.scratch/g6_roundtrip.py`` under hython (recorded in the receipt).
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

from synapse.identify import apply as A


# ── fakes ────────────────────────────────────────────────────────────────────

class _NodeFlag:
    DisplayComment = "DisplayComment"


class _Undos:
    @contextmanager
    def group(self, label):
        yield

    @contextmanager
    def disabler(self):
        yield


class _HipFile:
    def __init__(self):
        self.callbacks = []

    def addEventCallback(self, cb):
        self.callbacks.append(cb)

    def removeEventCallback(self, cb):
        if cb in self.callbacks:
            self.callbacks.remove(cb)

    def eventCallbacks(self):
        return list(self.callbacks)


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


@pytest.fixture
def hou(monkeypatch):
    fake = FakeHou()
    monkeypatch.setattr(A, "hou", fake)
    A._reset_state()
    yield fake
    A._reset_state()


# ── T1: show installs the save callback (the G6 fix) ─────────────────────────

def test_show_installs_exactly_one_save_callback(hou):
    """The product write path arms save safety; the probe never had to."""
    n = FakeNode(hou, "/obj/geo/box1", 11)
    A.show([(n, ["PolyBevel", "Offset 0.07"])])
    assert len(hou.hipFile.callbacks) == 1
    assert A._SAVE_CALLBACK is not None


def test_reshow_does_not_re_register_the_callback(hou):
    n = FakeNode(hou, "/obj/geo/box1", 12)
    A.show([(n, ["A"])])
    A.show([(n, ["A"])])
    A.show([(n, ["A"])])
    assert len(hou.hipFile.callbacks) == 1


def test_toggle_and_clear_paths_also_arm_save_safety(hou):
    """``/identify`` reaches ``show`` through ``toggle``; that path arms too."""
    n = FakeNode(hou, "/obj/geo/box1", 13, comment="note")
    r = A.toggle([(n, ["A"])])            # no block yet -> shows
    assert r["action"] == "show"
    assert len(hou.hipFile.callbacks) == 1


def test_before_save_strips_every_block_and_after_save_restores(hou):
    nodes = [FakeNode(hou, f"/obj/n{i}", 20 + i, comment=f"artist {i}", flag=(i % 2 == 0))
             for i in range(4)]
    A.show([(n, ["Type", f"Offset {i}"]) for i, n in enumerate(nodes)])
    shown = [n.comment() for n in nodes]
    for c in shown:
        assert A.SENTINEL in c

    A.before_save()
    for i, n in enumerate(nodes):
        assert A.SENTINEL not in n.comment()          # nothing on disk
        assert n.comment() == f"artist {i}"           # artist text intact

    A.after_save()
    for n, before in zip(nodes, shown):
        assert n.comment() == before                  # every block restored
