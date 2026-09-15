"""FR-1 send guard: a chat message typed while the bridge is down is never
queued silently. Stock pytest -- no Qt, no ``hou``.

Pins ``synapse.panel.send_guard.decide_send`` (the decision the chat panel
makes before it hands a message to the WebSocket bridge) and the module's
Qt-free import surface. The panel-level wiring is pinned in
``tests/test_chat_panel.py``; the bridge's no-replay send in
``tests/test_hda_panel.py``.
"""
import ast
from pathlib import Path

import pytest

from synapse.panel import send_guard
from synapse.panel.send_guard import (
    ACTION_EMPTY,
    ACTION_REFUSE_BRIDGE_DOWN,
    ACTION_REFUSE_NO_BRIDGE,
    ACTION_SEND,
    BRIDGE_DOWN_LINE,
    NO_BRIDGE_LINE,
    QUICK_ACTION_DOWN_LINE,
    QUICK_ACTION_FAILED_LINE,
    SEND_FAILED_LINE,
    decide_send,
)


def test_bridge_down_is_refused_text_kept_and_said():
    """The reported case: bridge object alive, socket down."""
    d = decide_send("make a box", bridge_present=True, bridge_connected=False)
    assert d.action == ACTION_REFUSE_BRIDGE_DOWN
    assert d.sends is False
    assert d.keep_text is True
    assert d.status_line == BRIDGE_DOWN_LINE


def test_no_bridge_is_refused_text_kept_and_said():
    d = decide_send("make a box", bridge_present=False, bridge_connected=False)
    assert d.action == ACTION_REFUSE_NO_BRIDGE
    assert d.sends is False
    assert d.keep_text is True
    assert d.status_line == NO_BRIDGE_LINE


def test_connected_sends():
    d = decide_send("make a box", bridge_present=True, bridge_connected=True)
    assert d.action == ACTION_SEND
    assert d.sends is True
    assert d.keep_text is False
    assert d.status_line == ""


@pytest.mark.parametrize("text", ["", "   ", "\n\t", None])
def test_blank_text_is_a_no_op(text):
    d = decide_send(text, bridge_present=True, bridge_connected=True)
    assert d.action == ACTION_EMPTY
    assert d.sends is False
    assert d.status_line == ""


@pytest.mark.parametrize("text", ["make a box", "x", "  spaced  ", "multi\nline"])
@pytest.mark.parametrize("bridge_present", [True, False])
def test_never_sends_while_down(text, bridge_present):
    """The invariant: bridge down + text -> stays in the box, never queued-silent."""
    d = decide_send(text, bridge_present=bridge_present, bridge_connected=False)
    assert d.sends is False
    assert d.keep_text is True
    assert d.status_line, "a refusal must say so on the surface"


def test_status_lines_name_the_release():
    """Every refusal tells the artist the text is still there and how to release it."""
    for line in (BRIDGE_DOWN_LINE, SEND_FAILED_LINE):
        assert "wasn't sent" in line
        assert "Connect" in line
        assert "Send again" in line
    assert "wasn't sent" in NO_BRIDGE_LINE
    assert "still in the box" in NO_BRIDGE_LINE
    # Pills have no input box: the release is the pill itself.
    for line in (QUICK_ACTION_DOWN_LINE, QUICK_ACTION_FAILED_LINE):
        assert "wasn't sent" in line
        assert "Connect" in line
        assert "pill again" in line
        assert "box" not in line


def test_send_guard_imports_no_qt_no_hou():
    """The decision must stay importable under stock CPython."""
    src = Path(send_guard.__file__).read_text(encoding="utf-8")
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
    for name in names:
        assert not name.startswith(("PySide", "hou", "hdefereval", "synapse.")), name
