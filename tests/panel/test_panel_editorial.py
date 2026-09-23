"""Native Qt acceptance for the approved September panel refinement.

These are geometry/interaction checks, not source-text pins. All settings,
history and runtime hooks are isolated; no model or Houdini request is made.
"""
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "python"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui, QtTest

if not isinstance(QtWidgets.QApplication, type):
    pytest.skip("Real Qt required, not a mock QApplication", allow_module_level=True)

_APP = None


def settle():
    for _ in range(3):
        _APP.processEvents()


@pytest.fixture
def make_panel(monkeypatch, tmp_path):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    original_font = QtGui.QFont(_APP.font())
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "panel.json"))
    monkeypatch.setenv("SYNAPSE_REDUCED_MOTION", "1")
    from synapse.server import session_store, telemetry_dump, runtime_beat
    from synapse.core import logfile
    from synapse.panel.synapse_panel import SynapsePanel
    monkeypatch.setattr(session_store, "load_conversation_scoped", lambda: ([], "current"))
    monkeypatch.setattr(session_store, "save_conversation", lambda *a, **k: None)
    monkeypatch.setattr(telemetry_dump, "start_periodic_flush", lambda *a, **k: None)
    monkeypatch.setattr(runtime_beat, "ensure_beat_started", lambda *a, **k: None)
    monkeypatch.setattr(runtime_beat, "detach_panel", lambda *a, **k: None)
    monkeypatch.setattr(logfile, "ensure_file_logging", lambda *a, **k: None)
    for name in ("_update_context", "_update_health", "_register_selection_cb"):
        monkeypatch.setattr(SynapsePanel, name, lambda self: None)
    panels = []

    def build(scale=1.0, width=380, height=900):
        font = QtGui.QFont(original_font)
        font.setPixelSize(round(12 * scale))
        _APP.setFont(font)
        panel = SynapsePanel()
        panels.append(panel)
        panel._ctx_timer.stop()
        panel._health_timer.stop()
        if panel._notification_controller:
            panel._notification_controller._timer.stop()
        panel.resize(width, height)
        panel.show()
        settle()
        return panel

    yield build
    for panel in panels:
        panel._worker = None
        panel._chat.shutdown()
        panel.close()
        panel.deleteLater()
    settle()
    _APP.setFont(original_font)


def right(widget, root):
    return widget.mapTo(root, QtCore.QPoint(widget.width(), 0)).x()


def box(widget, root):
    return QtCore.QRect(widget.mapTo(root, QtCore.QPoint()), widget.size())


@pytest.mark.parametrize("scale,width", [(1.0, 380), (1.25, 480), (2.25, 720)])
def test_stop_stays_on_right_and_tells_the_truth_through_second_task(make_panel, scale, width):
    panel = make_panel(scale, width)
    aborts = []
    panel._worker = SimpleNamespace(abort=lambda: aborts.append(True))
    panel._set_busy(True)
    settle()
    assert panel._stop_btn.isVisible()
    assert panel._stop_btn.parentWidget() is panel._input
    assert right(panel._stop_btn, panel) == right(panel._send_btn, panel)
    assert panel._stop_btn.width() == panel._send_btn.width()
    assert panel._stop_btn.geometry().top() > panel._send_btn.geometry().bottom()
    assert panel._input.viewport().geometry().bottom() < panel._send_btn.geometry().top()
    assert panel._stop_btn.font() == panel._send_btn.font()
    assert panel._stop_btn.text() == "STOP"
    assert panel._stop_btn.width() >= panel._stop_btn.sizeHint().width()
    assert panel._stop_btn.accessibleName() == "Stop current task"
    panel._stop_btn.click()
    assert aborts == [True]
    assert panel._was_busy and panel._header_status.text() == "Stopping…"
    assert not panel._stop_btn.isEnabled()
    panel._worker = None
    panel._set_busy(False)
    panel._set_busy(True)
    panel._regate_stop()
    settle()
    assert panel._stop_btn.isVisible() and panel._stop_btn.isEnabled()
    assert right(panel._stop_btn, panel) == right(panel._send_btn, panel)
    assert panel._stop_btn.geometry().top() > panel._send_btn.geometry().bottom()
    panel._input.setPlainText("Keep this draft")
    for profile in ("curious", "ml", "expert"):
        panel._recompose(profile)
        panel._input.set_user_height(64)
        panel.resize(width, 760)
        settle()
        assert panel._stop_btn.isVisible() and panel._stop_btn.isEnabled()
        assert panel._input.rect().contains(panel._stop_btn.geometry())
        assert panel._input.viewport().geometry().bottom() < panel._send_btn.geometry().top()
        assert panel._input.viewport().height() >= panel._input.fontMetrics().height()
        assert right(panel._stop_btn, panel) == right(panel._send_btn, panel)
        assert panel._stop_btn.geometry().top() > panel._send_btn.geometry().bottom()
        assert panel._input.toPlainText() == "Keep this draft"
    panel._set_busy(False)
    settle()
    assert not panel._stop_btn.isVisible() and panel._send_btn.isEnabled()
    # Internal consent/work views hide the composer. The persistent mark
    # must still stop the same worker, including on the following task.
    for _ in range(2):
        panel._set_busy(True)
        panel._set_face("work")
        panel._worker = SimpleNamespace(abort=lambda: aborts.append(True))
        settle()
        assert not panel._stop_btn.isVisible() and panel._mark.isVisible()
        assert panel._mark.halt_available()
        before = len(aborts)
        QtTest.QTest.mouseClick(panel._mark, QtCore.Qt.LeftButton)
        assert len(aborts) == before + 1
        assert panel._was_busy and panel._header_status.text() == "Stopping…"
        assert not panel._stop_btn.isEnabled() and not panel._mark.halt_available()
        QtTest.QTest.mouseClick(panel._mark, QtCore.Qt.LeftButton)
        assert len(aborts) == before + 1
        panel._worker = None
        panel._set_busy(False)


@pytest.mark.parametrize("scale,width,min_height", [(1.0, 380, 40), (1.25, 480, 50), (2.25, 720, 90)])
def test_actual_model_rows_have_scaled_air_in_both_picker_paths(make_panel, scale, width, min_height):
    panel = make_panel(scale, width)
    from synapse.panel.model_picker import ModelPicker, ROW
    for entry in (panel._open_author_menu, panel._open_model_menu):
        entry()
        settle()
        picker = panel._model_picker
        assert isinstance(picker, ModelPicker)
        rows = [picker.list.item(i) for i in range(picker.list.count())]
        models = [item for item in rows if item.data(ROW)["kind"] == "model"]
        boxes = [picker.list.visualItemRect(item) for item in models]
        assert boxes and min(box.height() for box in boxes) >= min_height
        assert all(a.bottom() < b.top() for a, b in zip(boxes, boxes[1:]))
        assert sum(item.data(ROW).get("active", False) for item in models) == 1
        assert [item.text() for item in rows if item.data(ROW)["kind"] == "provider"] == [
            "Anthropic", "Google", "NVIDIA", "Ollama", "Custom"]
        picker.close()
        settle()


def test_long_model_menu_is_one_scrollable_column_and_last_choice_works(make_panel):
    panel = make_panel(2.25, 720)
    from synapse.panel.designsystem.components import ModelMenu
    menu = ModelMenu(panel, scale=2.25)
    chosen = []
    for index in range(80):
        action = menu.addAction("Local model %02d" % index)
        action.triggered.connect(lambda checked=False, i=index: chosen.append(i))
    menu.popup(panel.mapToGlobal(QtCore.QPoint(30, 60)))
    settle()
    try:
        screen = menu.screen().availableGeometry()
        assert menu.height() <= screen.height()
        assert menu.width() <= screen.width()
        assert len({menu.actionGeometry(a).x() for a in menu.actions()}) == 1
        QtTest.QTest.keyClick(menu, QtCore.Qt.Key_End)
        settle()
        assert menu.activeAction() is menu.actions()[-1]
        box = menu.actionGeometry(menu.activeAction())
        assert box.top() >= 0 and box.bottom() < menu.height()
        QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Return)
        assert chosen == [79]
    finally:
        menu.close()
        menu.deleteLater()


def test_menu_selection_keeps_exact_saved_identity_and_other_provider_picks(make_panel):
    panel = make_panel()
    before = dict(panel._model_by_provider)
    panel._model_by_provider["claude"] = "artist-retained-model"
    from synapse.panel.model_picker import ROW
    picker = panel._build_model_picker()
    picker.popup(panel._author_lbl)
    settle()
    active = [picker.list.item(i) for i in range(picker.list.count())
              if picker.list.item(i).data(ROW).get("active")]
    assert len(active) == 1 and active[0].data(ROW)["model"] == "artist-retained-model"
    picker.search.setText("Opus 5")
    settle()
    assert panel._active_model() == "artist-retained-model"
    QtTest.QTest.keyClick(picker.search, QtCore.Qt.Key_Return)
    settle()
    assert panel._active_model() == "claude-opus-5"
    assert all(panel._model_by_provider[key] == value for key, value in before.items() if key != "claude")


def test_custom_setup_cancellation_or_redirect_never_commits_an_old_row(make_panel, monkeypatch):
    panel = make_panel()
    before = (panel._provider_id, dict(panel._model_by_provider))
    monkeypatch.setattr(panel, "_custom_configured", lambda: False)
    calls = []
    monkeypatch.setattr(panel, "_configure_custom", lambda: calls.append("setup"))
    panel._pick_engine_model("custom", "obsolete-custom-id")
    assert calls == ["setup"]
    assert (panel._provider_id, panel._model_by_provider) == before
    def redirected_setup():
        panel._provider_id = "gemini"
        panel._model_by_provider["gemini"] = "accepted-google-id"
    monkeypatch.setattr(panel, "_configure_custom", redirected_setup)
    panel._pick_engine_model("custom", "obsolete-custom-id")
    assert panel._provider_id == "gemini"
    assert panel._model_by_provider["gemini"] == "accepted-google-id"
    assert panel._model_by_provider.get("custom") == before[1].get("custom")


def test_configure_opens_custom_without_changing_next_model(make_panel, monkeypatch):
    panel = make_panel()
    before = (panel._provider_id, dict(panel._model_by_provider))
    calls = []
    monkeypatch.setattr(panel, "_open_connections", lambda **kw: calls.append(kw))
    panel._configure_custom()
    assert calls == [{"provider_id": "custom"}]
    assert (panel._provider_id, panel._model_by_provider) == before


def test_empty_state_has_hierarchy_then_yields_to_real_content(make_panel):
    panel = make_panel()
    chat = panel._chat
    invitation = chat._empty_state
    assert invitation.isVisible() and chat.toPlainText() == ""
    assert invitation.title.text() == "What are we building?"
    assert invitation.title.alignment() & QtCore.Qt.AlignLeft
    assert not invitation.title.font().italic()
    assert invitation.title.font().pixelSize() > invitation.body.font().pixelSize()
    author_font = panel._author_lbl.font().pixelSize()
    initial_title = invitation.title.font().pixelSize()
    panel._cycle_font_scale()
    settle()
    assert invitation.title.font().pixelSize() > initial_title
    assert panel._author_lbl.font().pixelSize() == author_font
    chat.append_user_message("Inspect the selected network.")
    settle()
    assert not invitation.isVisible()
    assert "Inspect the selected network." in chat.toPlainText()
    assert "What are we building?" not in chat.toPlainText()


@pytest.mark.parametrize("scale,width", [(1.0, 380), (1.25, 480), (2.25, 720)])
def test_composer_actions_share_field_edge_without_stealing_text_or_draft(make_panel, scale, width):
    panel = make_panel(scale, width)
    field, send, attach = panel._input, panel._send_btn, panel._attach_btn
    assert attach.parentWidget() is field and send.parentWidget() is field
    assert right(field, panel) == right(panel._author_lbl, panel)
    assert attach.geometry().bottom() == send.geometry().bottom()
    assert field.viewport().geometry().bottom() < send.geometry().top()
    assert attach.geometry().right() < send.geometry().left()
    assert panel._khint.alignment() & QtCore.Qt.AlignLeft
    field.set_user_height(220)
    field.setPlainText("Keep this draft")
    preferred = field._user_h
    panel.resize(width + 80, 1000)
    settle()
    assert field._user_h == preferred and field.toPlainText() == "Keep this draft"
    field.submitted.disconnect()
    sends = []
    field.submitted.connect(lambda: sends.append(field.toPlainText()))
    field.setFocus()
    field.moveCursor(QtGui.QTextCursor.End)
    QtTest.QTest.keyClick(field, QtCore.Qt.Key_Return, QtCore.Qt.ShiftModifier)
    QtTest.QTest.keyClicks(field, "second line")
    QtTest.QTest.keyClick(field, QtCore.Qt.Key_Return)
    assert sends == ["Keep this draft\nsecond line"]
    assert panel._current_face == "direct"


def test_narrow_enlarged_panel_reflows_without_overlap_and_restores_draft_height(make_panel):
    panel = make_panel(2.25, 340, 900)
    panel._input.set_user_height(260)
    panel._input.setPlainText("Keep the lighting draft")
    panel.resize(341, 900)
    settle()
    for first, second in ((panel._wordmark, panel._author_lbl),
                          (panel._header_status, panel._connect_btn),
                          (panel._header_status, panel._overflow_btn),
                          (panel._input, panel._khint)):
        assert not box(first, panel).intersects(box(second, panel))
    for widget in (panel._author_lbl, panel._connect_btn, panel._overflow_btn,
                   panel._input, panel._khint, panel._connection_status):
        assert panel.rect().contains(box(widget, panel)), widget.objectName()
    assert panel._khint.height() >= panel._khint.heightForWidth(panel._khint.width())
    assert panel._connection_status.width() >= panel._connection_status.sizeHint().width()
    panel.resize(900, 1100)
    settle()
    assert panel._input._user_h == 260
    assert panel._input.height() == 260
    assert panel._input.toPlainText() == "Keep the lighting draft"
    # Soft Editorial displays the registry label; exact identity stays available.
    from synapse.panel.providers.registry import model_label
    assert panel._author_lbl.text() == model_label(panel._provider_id, panel._active_model())
    assert panel._active_model() in panel._author_lbl.accessibleName()
    assert panel._recipes_btn.isVisible() and panel._events_btn.isVisible()
    assert abs(box(panel._wordmark, panel).center().y() - box(panel._author_lbl, panel).center().y()) < 3


def test_long_model_identity_fits_narrow_header_but_keeps_exact_pick(make_panel):
    panel = make_panel(2.25, 340, 900)
    chosen = "an-artist-retained-model-with-an-extraordinarily-long-name-2026:cloud"
    panel._model_by_provider["claude"] = chosen
    panel._refresh_engine_selector()
    settle()
    assert panel._active_model() == chosen
    assert panel._author_lbl.text() != panel._author_token()
    assert chosen in panel._author_lbl.toolTip()
    assert panel._author_lbl.accessibleName() == "Generation model: claude/" + chosen
    assert panel.rect().contains(box(panel._author_lbl, panel))
    assert not box(panel._wordmark, panel).intersects(box(panel._author_lbl, panel))


def test_narrow_empty_invitation_and_busy_actions_never_paint_clipped(make_panel):
    panel = make_panel(2.25, 340, 900)
    panel._input.set_user_height(260)
    panel.resize(341, 900)
    settle()
    invite = panel._chat._empty_state
    assert invite.isVisible()
    assert invite.title.height() >= invite.title.heightForWidth(invite.title.width())
    assert invite.rect().contains(invite.title.geometry())
    if invite.body.isVisible():
        assert invite.body.height() >= invite.body.heightForWidth(invite.body.width())
        assert invite.rect().contains(invite.body.geometry())
    panel._set_busy(True)
    settle()
    for widget in (panel._stop_btn, panel._input, panel._khint, panel._connection_status):
        assert panel.rect().contains(box(widget, panel))
    assert not box(panel._input, panel).intersects(box(panel._khint, panel))
    if invite.isVisible():
        assert invite.title.height() >= invite.title.heightForWidth(invite.title.width())


def text_box(widget, root):
    """Native font/style text bounds, not just the widget's outer rectangle."""
    if isinstance(widget, QtWidgets.QAbstractButton):
        option = QtWidgets.QStyleOptionButton()
        widget.initStyleOption(option)
        content = widget.style().subElementRect(QtWidgets.QStyle.SE_PushButtonContents, option, widget)
        bounds = widget.style().itemTextRect(widget.fontMetrics(), content,
                                            QtCore.Qt.AlignCenter, widget.isEnabled(), widget.text())
    else:
        bounds = widget.fontMetrics().boundingRect(widget.contentsRect(),
                    int(widget.alignment() | QtCore.Qt.TextWordWrap), widget.text())
    bounds.translate(widget.mapTo(root, QtCore.QPoint()))
    return bounds


@pytest.mark.parametrize("scale,width", [(1.0, 340), (1.0, 640), (1.25, 340),
                                        (1.25, 640), (2.25, 340), (2.25, 900)])
def test_composer_footer_text_anchors_to_both_field_edges(make_panel, scale, width):
    panel = make_panel(scale, width, 1100)
    panel._input.set_user_height(220)
    settle()
    field = box(panel._input, panel)
    links = [button for button in (panel._commands_btn, panel._render_btn,
                                  panel._recipes_btn, panel._events_btn) if button.isVisible()]
    painted = [text_box(button, panel) for button in links]
    assert abs(painted[0].left() - field.left()) <= 2
    assert abs(painted[-1].right() - field.right()) <= 2
    newline = getattr(panel, "_newline_hint", None)
    assert newline is not None, "The two instructions need independent left/right anchors"
    left, right_hint = text_box(panel._khint, panel), text_box(newline, panel)
    assert abs(left.left() - field.left()) <= 2
    assert abs(right_hint.right() - field.right()) <= 2
    assert left.top() > field.bottom() and right_hint.top() > field.bottom()
    assert not left.intersects(right_hint)
    assert all(bounds.top() > max(left.bottom(), right_hint.bottom()) for bounds in painted)
    assert all(not a.intersects(b) for i, a in enumerate(painted) for b in painted[i + 1:])
    assert all(panel.rect().contains(bounds) for bounds in [left, right_hint] + painted)


@pytest.mark.parametrize("scale,width", [(1.0, 340), (1.25, 480), (2.25, 720)])
def test_stop_uses_requested_compact_height_without_changing_other_targets(make_panel, scale, width):
    panel = make_panel(scale, width)
    panel._set_busy(True)
    settle()
    assert panel._stop_btn.height() == round(20 * scale)
    assert panel._stop_btn.fontMetrics().height() <= panel._stop_btn.height()
    assert box(panel._stop_btn, panel).contains(text_box(panel._stop_btn, panel))
    assert right(panel._stop_btn, panel) == right(panel._send_btn, panel)
    assert panel._send_btn.height() >= 26 and panel._attach_btn.height() >= 26


@pytest.mark.parametrize("scale,width", [(1.0, 340), (1.0, 640), (1.25, 340),
                                        (1.25, 640), (2.25, 340), (2.25, 900)])
def test_connection_row_text_uses_the_prompt_edges_and_retains_evidence(make_panel, monkeypatch, scale, width):
    from synapse.panel.synapse_panel import SynapsePanel
    openings = []
    monkeypatch.setattr(SynapsePanel, "_open_connections", lambda self: openings.append(True))
    panel = make_panel(scale, width, 1100)
    # Deliberately do not derive location from the model's name. The prepared
    # connection owns it, including while the selected next model differs.
    evidence = "Current task: ollama/cloud-sounding-name\nLocal: runtime evidence"
    facts = SimpleNamespace(location="Local", description=evidence)
    connection = SimpleNamespace(facts=facts, provider=SimpleNamespace(resolve_key=lambda: "test"),
                                 release=lambda: None)
    monkeypatch.setattr(panel, "_prepare_connection", lambda: connection)
    monkeypatch.setattr(panel, "_refresh_session_permission", lambda _: None)
    panel._refresh_engine_selector()
    settle()
    location = getattr(panel, "_connection_location", None)
    assert location is not None, "Location and connection action need separate edge anchors"
    assert location.text() == "Local"
    assert location.toolTip() == evidence
    assert location.accessibleDescription() == evidence
    assert panel._connection_status.text() == "Connect models"
    assert panel._connection_status.toolTip() == evidence
    panel._connection_status.click()
    assert openings == [True]
    field = box(panel._input, panel)
    first, last = text_box(location, panel), text_box(panel._connection_status, panel)
    assert abs(first.left() - field.left()) <= 2
    assert abs(last.right() - field.right()) <= 2
    assert not first.intersects(last)
    assert all(panel.rect().contains(bounds) for bounds in (first, last))
    assert first.top() > field.bottom() and last.top() > field.bottom()
    # A failed next selection clears stale locality, including accessibility.
    monkeypatch.setattr(panel, "_prepare_connection", lambda: (_ for _ in ()).throw(ValueError("unavailable")))
    panel._refresh_engine_selector()
    settle()
    assert location.text() == "Unverified"
    assert "Location unverified" in location.toolTip()
    assert location.accessibleDescription() == location.toolTip()
    assert not text_box(location, panel).intersects(text_box(panel._connection_status, panel))


@pytest.mark.parametrize("profile", ["expert", "curious", "ml"])
def test_chat_is_the_only_home_without_token_construction_or_navigation(make_panel, monkeypatch, profile):
    from synapse.panel.synapse_panel import SynapsePanel
    built = []
    original = SynapsePanel._build_token_face
    def record_build(self):
        built.append(True)
        return original(self)
    monkeypatch.setattr(SynapsePanel, "_build_token_face", record_build)
    panel = make_panel()
    panel._recompose(profile)
    settle()
    assert built == [], "An inaccessible diagnostic face must not be constructed or probed"
    assert panel._faces.count() == 2  # conversation and retained internal work/consent state
    assert panel._current_face == "direct" and panel._input.isVisible()
    assert panel._face_pills == {}
    assert not [b.text() for b in panel.findChildren(QtWidgets.QAbstractButton)
                if b.text() in ("CHAT", "TOKEN")]
    menu = panel._build_overflow_menu()
    try:
        actions = menu.actions() + [a for child in menu.findChildren(QtWidgets.QMenu)
                                     for a in child.actions()]
        assert not [a.text() for a in actions if "TOKEN" in a.text().upper()]
    finally:
        menu.deleteLater()
    panel._input.setPlainText("Keep the draft")
    panel._set_face("token")  # any legacy restoration request lands on the composer
    probed = []
    panel._token_face = SimpleNamespace(refresh_from_probe=lambda: probed.append(True))
    panel._show_token_face()
    assert probed == [], "Legacy navigation must not refresh an inaccessible face"
    panel._token_face = None
    assert panel._current_face == "direct" and panel._faces.currentIndex() == 0
    assert panel._input.toPlainText() == "Keep the draft"


def test_completion_keeps_real_usage_without_a_token_tab(make_panel):
    from synapse.panel.usage_sink import USAGE_SINK
    panel = make_panel()
    USAGE_SINK.clear()
    try:
        USAGE_SINK.begin_task("kept-model:cloud", provider="ollama")
        USAGE_SINK.add({"input_tokens": 11, "output_tokens": 4})
        before = USAGE_SINK.snapshot()
        panel._set_busy(True)
        panel._stream_buf = ["The selected network was inspected."]
        panel._on_done()
        settle()
        assert USAGE_SINK.snapshot() == before
        assert panel._meter_lbl.text() == "15"
        assert "selected network was inspected" in panel._chat.toPlainText()
        assert panel._current_face == "direct" and panel._input.isVisible()
        assert panel._send_btn.isEnabled() and not panel._stop_btn.isVisible()
        assert getattr(panel, "_token_face", None) is None
    finally:
        USAGE_SINK.clear()


def test_first_run_leaves_reading_room_and_retains_artist_height(make_panel):
    panel = make_panel(1.25, 720, 1080)
    assert panel._input.height() < panel._chat.height() * 0.6
    # A fresh composer must actually expose its two-line draft area above Send.
    assert panel._input.viewport().height() >= 2 * panel._input.fontMetrics().height()
    panel._input.set_user_height(240)
    panel._input.setPlainText("Keep the lighting draft")
    panel.resize(620, 1000)
    settle()
    assert panel._input.height() == 240
    assert panel._input.toPlainText() == "Keep the lighting draft"
