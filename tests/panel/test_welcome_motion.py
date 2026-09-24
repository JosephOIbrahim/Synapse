"""Native Qt welcome motion: interaction sequences, geometry, and teardown."""
import os
from pathlib import Path
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "python"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtTest

if not isinstance(QtWidgets.QApplication, type):
    pytest.skip("Real Qt required, not a mock QApplication", allow_module_level=True)

from synapse.panel.chat_display import ChatDisplay
from synapse.panel.designsystem import tokens as t

_APP = None


@pytest.fixture
def make_chat():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    original_motion = t._REDUCED_MOTION
    t.set_reduced_motion(False)
    chats = []

    def build(show=True, width=520, height=540):
        chat = ChatDisplay()
        chats.append(chat)
        chat.resize(width, height)
        chat.show_invitation()
        if show:
            chat.show()
        return chat

    yield build
    for chat in chats:
        chat.shutdown()
        chat.close()
        chat.deleteLater()
    _APP.processEvents()
    t.set_reduced_motion(original_motion)


def finish(chat):
    animation = chat._invitation_motion._animation
    animation.setCurrentTime(animation.duration())


def running(chat):
    return chat._invitation_motion._animation.state() == QtCore.QAbstractAnimation.Running


def centered(chat):
    center = chat._empty_state.geometry().center()
    target = chat.viewport().rect().center()
    assert abs(center.x() - target.x()) <= 1
    assert abs(center.y() - target.y()) <= 1


def test_entrance_waits_for_show_then_drops_without_changing_transcript(make_chat):
    chat = make_chat(show=False)
    assert not running(chat)
    assert chat._empty_state.isHidden()
    chat.show()
    invitation = chat._empty_state
    initial = QtCore.QRect(invitation.geometry())
    viewport = QtCore.QRect(chat.viewport().geometry())
    assert running(chat)
    assert initial.center().y() < chat.viewport().rect().center().y()
    assert invitation.graphicsEffect().opacity() < 1.0
    chat._invitation_motion._animation.setCurrentTime(160)
    assert invitation.y() > initial.y()
    assert invitation.size() == initial.size()
    assert 0 < invitation.graphicsEffect().opacity() < 1
    finish(chat)
    centered(chat)
    assert chat.viewport().geometry() == viewport
    assert chat.toPlainText() == "" and chat.document().isEmpty()
    assert not running(chat)
    assert not invitation.graphicsEffect().isEnabled()


def test_resize_focus_and_reshow_never_replay_a_completed_entrance(make_chat):
    chat = make_chat()
    finish(chat)
    for width, height in ((700, 700), (340, 450), (520, 12), (520, 540)):
        chat.resize(width, height)
        _APP.processEvents()
        assert not running(chat)
    centered(chat)
    chat.hide()
    chat.show()
    chat.setFocus()
    chat.show_invitation()
    assert not running(chat)
    centered(chat)
    assert chat._empty_state.isVisible()


def test_dismissal_interrupts_entrance_and_survives_resize_and_repeated_calls(make_chat):
    chat = make_chat()
    animation = chat._invitation_motion._animation
    animation.setCurrentTime(160)
    y_before = chat._empty_state.y()
    opacity_before = chat._empty_state.graphicsEffect().opacity()
    chat.dismiss_invitation()
    assert chat._empty_state.y() == y_before
    assert chat._empty_state.graphicsEffect().opacity() == opacity_before
    animation.setCurrentTime(100)
    assert chat._empty_state.y() < y_before
    assert chat._empty_state.graphicsEffect().opacity() < opacity_before
    time_before = animation.currentTime()
    chat.dismiss_invitation()
    assert animation.currentTime() == time_before
    finish(chat)
    for width, height in ((340, 450), (700, 700)):
        chat.resize(width, height)
        chat.show_invitation()
        _APP.processEvents()
        assert not running(chat)
        assert chat._empty_state.isHidden()
    assert chat.document().isEmpty()


def test_resize_during_motion_keeps_its_clock_and_lands_at_new_center(make_chat):
    chat = make_chat()
    animation = chat._invitation_motion._animation
    for exiting in (False, True):
        if exiting:
            chat.dismiss_invitation()
        animation.setCurrentTime(animation.duration() // 2)
        elapsed = animation.currentTime()
        delta = chat._empty_state.geometry().center().y() - chat.viewport().rect().center().y()
        chat.resize(400 if not exiting else 620, 650 if not exiting else 440)
        assert animation.currentTime() == elapsed
        assert running(chat)
        new_delta = chat._empty_state.geometry().center().y() - chat.viewport().rect().center().y()
        assert abs(new_delta - delta) <= 1
        finish(chat)
        if not exiting:
            centered(chat)
    assert chat._empty_state.isHidden()


def test_clicking_the_welcome_yields_to_transcript_interaction(make_chat):
    chat = make_chat()
    finish(chat)
    body = chat._empty_state.body
    QtTest.QTest.mouseClick(body, QtCore.Qt.LeftButton, pos=body.rect().center())
    assert running(chat)
    finish(chat)
    assert chat._empty_state.isHidden()


@pytest.mark.parametrize("during_exit", [False, True])
def test_real_message_cancels_motion_and_clear_starts_one_new_welcome(make_chat, during_exit):
    chat = make_chat()
    if during_exit:
        finish(chat)
        chat.dismiss_invitation()
    chat.append_user_message("Inspect the selected network.")
    assert not running(chat)
    assert chat._empty_state.isHidden()
    assert "Inspect the selected network." in chat.toPlainText()
    chat.clear()
    assert running(chat)
    assert chat._empty_state.isVisible()
    finish(chat)
    centered(chat)
    chat.dismiss_invitation()
    finish(chat)
    assert chat._empty_state.isHidden()


def test_reduced_motion_is_instant_and_can_settle_an_animation_in_flight(make_chat):
    t.set_reduced_motion(True)
    chat = make_chat()
    centered(chat)
    assert not running(chat)
    chat.dismiss_invitation()
    assert not running(chat) and chat._empty_state.isHidden()
    chat.append_user_message("Start another conversation.")
    t.set_reduced_motion(False)
    chat.clear()
    assert running(chat)
    t.set_reduced_motion(True)
    chat._invitation_motion._animation.setCurrentTime(50)
    assert not running(chat)
    centered(chat)
    t.set_reduced_motion(False)
    chat.dismiss_invitation()
    assert running(chat)
    t.set_reduced_motion(True)
    chat._invitation_motion._animation.setCurrentTime(50)
    assert not running(chat) and chat._empty_state.isHidden()


def test_hidden_dismissal_and_close_leave_no_animation_to_replay(make_chat):
    chat = make_chat(show=False)
    chat.dismiss_invitation()
    chat.show()
    assert not running(chat) and chat._empty_state.isHidden()
    chat.append_user_message("A message.")
    chat.clear()
    assert running(chat)
    chat.close()
    assert not running(chat)
    chat.show()
    assert not running(chat)
    centered(chat)
    chat.dismiss_invitation()
    chat.shutdown()
    assert not running(chat) and chat._empty_state.isHidden()


def test_event_loop_remains_responsive_during_motion(make_chat):
    chat = make_chat()
    events = []
    animation = chat._invitation_motion._animation
    assert running(chat)
    QtCore.QTimer.singleShot(0, lambda: events.append("processed"))
    # Qt's shared animation driver may still be waking after another widget's
    # teardown. Wait for observed frame progress, with a bounded failure path.
    deadline = QtCore.QElapsedTimer()
    deadline.start()
    while deadline.elapsed() < 1000 and (not events or animation.currentTime() == 0):
        QtTest.QTest.qWait(10)
    assert events == ["processed"]
    assert animation.currentTime() > 0
