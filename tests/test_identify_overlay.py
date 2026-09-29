"""overlay: the paint layer's pure parts, its controller, and its contract.

No Qt and no Houdini here. ``read_state`` runs against a fake editor and a fake
``hou``; the controller runs against a fake overlay window. The Qt painting is
checked live by ``scripts/probe_identify_overlay.py``.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from synapse.identify import bubble as B
from synapse.identify import layout as L
from synapse.identify import overlay as O

IDENTIFY = Path(__file__).resolve().parents[1] / "python" / "synapse" / "identify"


# ── read_state: editor pixels to window pixels ───────────────────────────────

class _Rect:
    def __init__(self, x, y, w, h):
        self._v = (x, y, w, h)

    def x(self):
        return self._v[0]

    def y(self):
        return self._v[1]

    def width(self):
        return self._v[2]

    def height(self):
        return self._v[3]


class _Bounds:
    def __init__(self, w, h):
        self._size = (w, h)

    def size(self):
        return self._size


class _Node:
    def __init__(self, sid, name, pos, parent, size=(1.13, 0.282)):
        self.sid, self._name, self._pos, self._parent, self._size = sid, name, pos, parent, size

    def sessionId(self):
        return self.sid

    def name(self):
        return self._name

    def position(self):
        return self._pos

    def size(self):
        return self._size

    def parent(self):
        return self._parent


class _Editor:
    """Pane at (100, 50), 800 wide, 600 tall with a 100 px toolbar on top."""

    def __init__(self, network, current=True, unit=100.0):
        self._network, self._current, self._unit = network, current, unit

    def isCurrentTab(self):
        return self._current

    def qtScreenGeometry(self):
        return _Rect(100, 50, 800, 600)

    def screenBounds(self):
        return _Bounds(800.0, 500.0)

    def pwd(self):
        return self._network

    def lengthToScreen(self, length):
        return self._unit * length

    def posToScreen(self, vec):
        return (vec[0] * self._unit, vec[1] * self._unit)


@pytest.fixture
def world(monkeypatch):
    net = SimpleNamespace(sessionId=lambda: 1)
    other = SimpleNamespace(sessionId=lambda: 2)
    nodes = {
        10: _Node(10, "box1", (1.0, 2.0), net),
        11: _Node(11, "far", (0.0, 0.0), other),
    }
    fake = SimpleNamespace(nodeBySessionId=nodes.get, Vector2=lambda x, y: (x, y))
    monkeypatch.setattr(O, "hou", fake)
    return SimpleNamespace(net=net, nodes=nodes)


def test_area_is_the_pane_minus_the_toolbar_above_it(world):
    area, _anchors, _alive = O.read_state(_Editor(world.net), [10])
    assert area == (100, 150, 800, 500)


def test_anchor_is_the_node_right_edge_mid_height_with_y_flipped(world):
    _area, anchors, alive = O.read_state(_Editor(world.net), [10])
    (a,) = anchors
    assert (a.x, a.y) == (213.0, 285.9)
    assert a.node_h == 28.2
    assert a.name_w == round(O.NAME_UNITS_PER_CHAR * 4 * 100, 1)
    assert a.node_w == 113.0
    assert alive == 1


def test_nodes_in_another_network_count_as_alive_but_are_not_drawn(world):
    _area, anchors, alive = O.read_state(_Editor(world.net), [10, 11, 99])
    assert [a.key for a in anchors] == [10]
    assert alive == 2


def test_a_hidden_editor_tab_reads_as_nothing_to_draw(world):
    assert O.read_state(_Editor(world.net, current=False), [10]) is None


# ── chip text and rows ───────────────────────────────────────────────────────

def test_chip_text():
    assert O.chip_text(5, 5) == "5 of 5 nodes"
    assert O.chip_text(60, 214, zoomed_out=True) == "60 of 214 nodes · zoom in to read"
    assert O.chip_text(3, 3, cleaned=1).endswith("1 old note removed")
    assert O.chip_text(3, 3, cleaned=2).endswith("2 old notes removed")


def test_rows_say_not_in_library_instead_of_guessing():
    model = B.bubble_model({"type_label": "Mystery", "category": "Sop",
                            "summary": None, "summary_source": "unknown"})
    assert O.rows(model)[0] == ("text", O.NOT_IN_LIBRARY, "body", "quiet")


def test_rows_order_and_inks():
    model = {"summary": "Does a thing.", "writes": {"path": "/ball", "more": 2},
             "changes": "Offset 0.07", "state": "warning: Slow"}
    assert O.rows(model) == [
        ("text", "Does a thing.", "body", "body"),
        ("writes", "/ball", 2),
        ("text", "Offset 0.07", "body", "detail"),
        ("text", "warning: Slow", "body", "warning"),
    ]
    assert O.rows({"summary": "x", "state": "error: Bad"})[-1][3] == "error"
    assert O.rows({"summary": "x", "state": "bypassed"})[-1][3] == "quiet"


# ── controller: show, clear, toggle ──────────────────────────────────────────

class _Timer:
    def __init__(self):
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


class _FakeOverlay:
    made = []

    def __init__(self, editor):
        self.editor, self.timer, self.order = editor, _Timer(), []
        self.visible, self.deleted, self.ticks = False, False, 0
        _FakeOverlay.made.append(self)

    def set_entries(self, entries, total, cleaned):
        self.order = [key for key, _model in entries]
        self.total, self.cleaned = total, cleaned

    def tick(self):
        self.ticks += 1
        self.visible = True

    def hide(self):
        self.visible = False

    def deleteLater(self):
        self.deleted = True


@pytest.fixture
def ctl(monkeypatch):
    _FakeOverlay.made = []
    monkeypatch.setattr(O, "hou", SimpleNamespace())
    monkeypatch.setattr(O, "QtWidgets", SimpleNamespace())
    monkeypatch.setattr(O, "_overlay_class", lambda: _FakeOverlay)
    monkeypatch.setattr(O, "_load_fonts", lambda: None)
    monkeypatch.setattr(O, "_OVERLAY", None)
    yield SimpleNamespace(editor=SimpleNamespace(name=lambda: "panetab1"))
    O._OVERLAY = None


def _entries(*keys):
    return [(k, {"title": str(k)}) for k in keys]


def test_show_draws_and_starts_following_the_editor(ctl):
    result = O.show(_entries(1, 2), total=5, editor=ctl.editor)
    assert result == {"action": "show", "shown": 2, "total": 5, "cleaned": 0}
    (overlay,) = _FakeOverlay.made
    assert overlay.timer.running and overlay.visible and O.is_active()


def test_show_caps_the_bubbles_but_keeps_the_full_total(ctl):
    result = O.show(_entries(*range(B.CAP + 10)), total=B.CAP + 10, editor=ctl.editor)
    assert result["shown"] == B.CAP and result["total"] == B.CAP + 10


def test_show_without_an_editor_draws_nothing_and_says_why(ctl):
    result = O.show(_entries(1), editor=None)
    assert result["shown"] == 0 and result["reason"] == O.NO_EDITOR
    assert _FakeOverlay.made == [] and not O.is_active()


def test_toggle_on_the_same_nodes_clears_without_running_the_cleanup(ctl):
    O.show(_entries(1, 2), editor=ctl.editor)
    calls = []
    result = O.toggle(_entries(2, 1), editor=ctl.editor, cleanup=lambda: calls.append(1) or 0)
    assert result == {"action": "clear", "removed": 2}
    assert calls == [] and not O.is_active()
    (overlay,) = _FakeOverlay.made
    assert not overlay.timer.running and overlay.deleted and not overlay.visible


def test_toggle_on_new_nodes_replaces_the_bubbles_and_runs_the_cleanup_first(ctl):
    O.show(_entries(1), editor=ctl.editor)
    result = O.toggle(_entries(3, 4), total=2, editor=ctl.editor, cleanup=lambda: 1)
    assert result == {"action": "show", "shown": 2, "total": 2, "cleaned": 1}
    assert O._OVERLAY.order == [3, 4] and len(_FakeOverlay.made) == 1


def test_a_different_editor_gets_a_fresh_overlay(ctl):
    O.show(_entries(1), editor=ctl.editor)
    O.show(_entries(1), editor=SimpleNamespace(name=lambda: "panetab2"))
    first, second = _FakeOverlay.made
    assert first.deleted and not second.deleted


def test_clear_with_nothing_shown_is_a_no_op(ctl):
    assert O.clear() == {"action": "clear", "removed": 0}


# ── contract: the overlay reads; only apply writes; tokens, not hex ─────────

_WRITERS = ("setComment", "setGenericFlag", ".undos", "addEventCallback", "setUserData")


@pytest.mark.parametrize("module", ["overlay.py", "bubble.py", "layout.py", "compose.py"])
def test_display_modules_never_write_to_the_scene(module):
    src = (IDENTIFY / module).read_text(encoding="utf-8")
    for token in _WRITERS:
        assert token not in src, (module, token)


def test_no_identify_module_hooks_the_save_any_more():
    for path in IDENTIFY.glob("*.py"):
        assert "addEventCallback" not in path.read_text(encoding="utf-8"), path.name


def test_the_overlay_declares_no_colour_of_its_own():
    src = (IDENTIFY / "overlay.py").read_text(encoding="utf-8")
    assert re.findall(r"[\"']#[0-9A-Fa-f]{3,8}[\"']", src) == []
    assert "designsystem import tokens" in src


def test_the_overlay_window_is_click_through_and_never_takes_focus():
    src = (IDENTIFY / "overlay.py").read_text(encoding="utf-8")
    for flag in ("WindowTransparentForInput", "WA_TransparentForMouseEvents",
                 "WindowDoesNotAcceptFocus", "WA_ShowWithoutActivating"):
        assert flag in src, flag
