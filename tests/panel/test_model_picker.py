"""Native acceptance for model browsing, identity and popup lifetime.

The catalog and discovery replies are synthetic. No provider, saved model,
Houdini state or network is used. These assertions exercise real Qt widgets.
"""
from copy import deepcopy
import os
from pathlib import Path
import socket
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
    pytest.skip("Real Qt required, not a mocked QApplication", allow_module_level=True)

from shiboken6 import isValid
from synapse.panel.model_picker import ModelPicker

Qt = QtCore.Qt
_APP = None


class Discovery(QtCore.QObject):
    changed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.loading = False
        self.text = "Synthetic discovery result"
        self.refreshes = 0

    def message(self):
        return self.text

    def refresh(self):
        self.refreshes += 1
        self.loading = True
        self.text = "Refreshing synthetic catalog"
        self.changed.emit()


def pump(delete=False):
    for _ in range(4):
        _APP.processEvents()
    if delete:
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        _APP.processEvents()


def catalog():
    return [
        ("claude", "Claude", [("claude-reference-20260922", "Claude reference", False)]),
        ("gemini", "Gemini", [("models/gemini-reference:preview", "Gemini reference", False)]),
        ("nemotron", "Nemotron", [("nvidia/nemotron-reference:70b", "Nemotron reference", False)]),
        ("ollama", "Ollama", [
            ("studio/echo:Q4_K_M", "Echo", True),
            ("another/echo:Q8_0", "Echo", False),
            ("cloud/reference:cloud", "Cloud relay reference", False),
        ]),
        ("custom", "Custom endpoint", [("vendor-a/endpoint:fp16", "Endpoint reference", False)]),
    ]


def rows(widget, kind=None):
    result = [widget.list.item(i) for i in range(widget.list.count())]
    return result if kind is None else [item for item in result if item.data(Qt.UserRole)["kind"] == kind]


def identity(item):
    value = item.data(Qt.UserRole)
    return value.get("provider"), value.get("model")


def model_item(widget, provider, model):
    return next(item for item in rows(widget, "model") if identity(item) == (provider, model))


@pytest.fixture
def make_picker(monkeypatch, tmp_path):
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    original_font = QtGui.QFont(_APP.font())
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "panel.json"))
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "policy.json"))
    monkeypatch.setenv("SYNAPSE_JEV_LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setenv("SYNAPSE_FILE_LOG", "0")
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Model picker acceptance cannot call any network")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    owned = []

    def build(data=None, scale=1.0, bottom_right=False):
        values = deepcopy(catalog() if data is None else data)
        reads = []

        def read_rows():
            reads.append(True)
            return deepcopy(values)

        parent = QtWidgets.QWidget()
        parent.resize(320, 100)
        anchor = QtWidgets.QPushButton("Choose generation model", parent)
        anchor.setGeometry(16, 24, 280, 40)
        available = parent.screen().availableGeometry()
        parent.move(available.left() + 20, available.top() + 20)
        if bottom_right:
            parent.move(available.right() - parent.width(), available.bottom() - parent.height())
        parent.show()
        pump()
        discovery = Discovery()
        picker = ModelPicker(parent, read_rows, discovery, scale)
        chosen, connections, configurations = [], [], []
        picker.model_chosen.connect(lambda provider, model: chosen.append((provider, model)))
        picker.connect_requested.connect(lambda: connections.append(True))
        picker.configure_requested.connect(lambda: configurations.append(True))
        owned.append((parent, picker, discovery))
        picker.popup(anchor)
        pump()
        return SimpleNamespace(parent=parent, anchor=anchor, picker=picker, discovery=discovery,
                               data=values, reads=reads, chosen=chosen,
                               connections=connections, configurations=configurations)

    yield build
    for parent, picker, discovery in reversed(owned):
        if isValid(picker):
            picker.close()
        if isValid(parent):
            parent.close()
            parent.deleteLater()
        if isValid(discovery):
            discovery.deleteLater()
    pump(delete=True)
    _APP.setFont(original_font)
    assert not attempts


def test_provider_groups_are_labeled_and_not_selectable(make_picker):
    case = make_picker()
    headings = rows(case.picker, "provider")
    assert [item.text() for item in headings] == ["Anthropic", "Google", "NVIDIA", "Ollama", "Custom"]
    provider = None
    for item in rows(case.picker):
        value = item.data(Qt.UserRole)
        if value["kind"] == "provider":
            provider = value["provider"]
            assert not item.flags() & (Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        else:
            assert value["provider"] == provider
            assert item.flags() & Qt.ItemIsSelectable
    case.picker.list.scrollToItem(headings[0])
    QtTest.QTest.mouseClick(case.picker.list.viewport(), Qt.LeftButton,
                           pos=case.picker.list.visualItemRect(headings[0]).center())
    assert case.chosen == []


def test_exact_model_namespace_and_tag_survive_duplicate_labels(make_picker):
    case = make_picker()
    expected = [(pid, mid) for pid, _, group in case.data for mid, _, _ in group]
    assert [identity(item) for item in rows(case.picker, "model")] == expected
    for item in rows(case.picker, "model"):
        value = item.data(Qt.UserRole)
        assert value["model"] == value["detail"]
        assert value["model"] in item.toolTip()
        assert value["model"] in item.data(Qt.AccessibleTextRole)
    echo = [item for item in rows(case.picker, "model") if item.text() == "Echo"]
    assert len(echo) == 2 and identity(echo[0]) != identity(echo[1])
    assert [item.data(Qt.UserRole)["active"] for item in echo] == [True, False]
    assert "studio/echo:Q4_K_M" in case.picker.current.accessibleName()
    assert "studio/echo:Q4_K_M" in case.picker.current.toolTip()


@pytest.mark.parametrize("query,provider", [
    ("Anthropic", "claude"), ("cLaUdE", "claude"), ("Google", "gemini"),
    ("gemini", "gemini"), ("NVIDIA", "nemotron"), ("nemotron", "nemotron"),
    ("Ollama", "ollama"), ("custom", "custom"),
])
def test_search_accepts_provider_names_aliases_and_ids(make_picker, query, provider):
    case = make_picker()
    before = deepcopy(case.data)
    case.picker.search.setText(query)
    pump()
    matches = rows(case.picker, "model")
    assert matches and {identity(item)[0] for item in matches} == {provider}
    assert not case.chosen and case.data == before


def test_search_uses_full_model_id_and_multiple_terms_without_committing(make_picker):
    case = make_picker()
    current = case.picker.current.text()
    current_accessible = case.picker.current.accessibleName()
    case.picker.search.setText("Ollama ANOTHER/echo Q8_0")
    pump()
    assert [identity(item) for item in rows(case.picker, "model")] == [("ollama", "another/echo:Q8_0")]
    assert case.picker.current.text() == current
    assert case.picker.current.accessibleName() == current_accessible
    assert not any(item.data(Qt.UserRole)["active"] for item in rows(case.picker, "model"))
    case.picker.list.setCurrentItem(rows(case.picker, "model")[0])
    QtTest.QTest.keyClick(case.picker.search, Qt.Key_Down)
    assert case.chosen == []
    case.picker.search.setText("a-model-that-is-not-present")
    pump()
    assert rows(case.picker) == [] and case.picker.empty.isVisible()
    assert case.picker.current.text() == current
    QtTest.QTest.keyClick(case.picker.search, Qt.Key_Return)
    assert case.chosen == [] and case.picker.isVisible()


@pytest.mark.parametrize("action", ["mouse", "keyboard"])
def test_activation_emits_exact_identity_once_even_if_qt_repeats_activation(make_picker, action):
    case = make_picker()
    target = model_item(case.picker, "ollama", "another/echo:Q8_0")
    case.picker.list.setCurrentItem(target)
    case.picker.list.scrollToItem(target)
    pump()
    assert case.chosen == []
    if action == "mouse":
        QtTest.QTest.mouseClick(case.picker.list.viewport(), Qt.LeftButton,
                               pos=case.picker.list.visualItemRect(target).center())
    else:
        QtTest.QTest.keyClick(case.picker.list, Qt.Key_Return)
    # Mouse/keyboard activation can converge on both connected Qt signals.
    # Repeat the signal before DeferredDelete to exercise the one-shot latch.
    case.picker.list.itemActivated.emit(target)
    assert case.chosen == [("ollama", "another/echo:Q8_0")]
    assert not case.connections and not case.configurations
    assert not case.picker.isVisible()


@pytest.mark.parametrize("focused", ["search", "list"])
def test_escape_dismisses_without_changing_selection(make_picker, focused):
    case = make_picker()
    case.picker.search.setText("Ollama")
    widget = getattr(case.picker, focused)
    widget.setFocus()
    QtTest.QTest.keyClick(widget, Qt.Key_Escape)
    assert not case.picker.isVisible()
    assert case.chosen == [] and case.connections == [] and case.configurations == []


@pytest.mark.parametrize("scale", [1.0, 1.25, 2.25])
def test_eighty_models_last_row_is_keyboard_reachable_and_popup_stays_on_screen(make_picker, scale):
    models = [("studio/model-%02d:Q4_K_M" % i, "Model %02d" % i, i == 0) for i in range(80)]
    case = make_picker([("ollama", "Ollama", models)], scale, bottom_right=True)
    available = case.anchor.screen().availableGeometry()
    assert available.contains(case.picker.frameGeometry())
    assert len(rows(case.picker, "model")) == 80
    assert case.picker.list.verticalScrollBar().maximum() > 0
    QtTest.QTest.keyClick(case.picker.search, Qt.Key_Down)
    QtTest.QTest.keyClick(case.picker.list, Qt.Key_End)
    pump()
    last = case.picker.list.currentItem()
    assert identity(last) == ("ollama", "studio/model-79:Q4_K_M")
    assert case.picker.list.viewport().rect().contains(case.picker.list.visualItemRect(last))
    assert case.picker.list.visualItemRect(last).height() >= 2 * case.picker.list.fontMetrics().height()
    assert not case.chosen
    QtTest.QTest.keyClick(case.picker.list, Qt.Key_Return)
    assert case.chosen == [("ollama", "studio/model-79:Q4_K_M")]


def test_discovery_refresh_preserves_query_highlight_scroll_and_filtered_current(make_picker):
    data = catalog()
    data[3][2].extend(("studio/model-%02d:Q4_K_M" % i, "Model %02d" % i, False) for i in range(80))
    case = make_picker(data)
    current = case.picker.current.text()
    current_accessible = case.picker.current.accessibleName()
    assert "studio/echo:Q4_K_M" in current_accessible
    # "model" alone also matches Ollama's provider alias, "Installed models".
    # This namespace prefix excludes the saved Echo ID independently of label.
    case.picker.search.setText("Ollama studio/model-")
    pump()
    highlighted = model_item(case.picker, "ollama", "studio/model-60:Q4_K_M")
    case.picker.list.setCurrentItem(highlighted)
    case.picker.list.scrollToItem(highlighted, QtWidgets.QAbstractItemView.PositionAtCenter)
    pump()
    old_scroll = case.picker.list.verticalScrollBar().value()
    assert old_scroll > 0
    expected = identity(highlighted)
    case.data[3][2].append(("new/model-81:Q8_0", "Model 81", False))
    case.discovery.loading = True
    case.discovery.text = "Refreshing synthetic models"
    case.discovery.changed.emit()
    pump()
    assert case.picker.search.text() == "Ollama studio/model-"
    assert identity(case.picker.list.currentItem()) == expected
    assert case.picker.list.verticalScrollBar().value() == old_scroll
    assert case.picker.current.text() == current
    assert case.picker.current.accessibleName() == current_accessible
    assert not any(item.data(Qt.UserRole)["active"] for item in rows(case.picker, "model"))
    assert case.picker.status.text() == case.discovery.text and not case.picker.refresh_button.isEnabled()
    case.discovery.loading = False
    case.discovery.text = "Synthetic refresh finished"
    case.discovery.changed.emit()
    pump()
    assert identity(case.picker.list.currentItem()) == expected
    assert case.picker.list.verticalScrollBar().value() == old_scroll
    assert case.picker.current.text() == current and case.picker.refresh_button.isEnabled()
    assert case.picker.current.accessibleName() == current_accessible
    assert not case.chosen


def test_refresh_button_requests_discovery_without_model_activation(make_picker):
    case = make_picker()
    case.picker.search.setText("echo")
    case.picker.refresh_button.click()
    pump()
    assert case.discovery.refreshes == 1
    assert case.picker.search.text() == "echo" and not case.chosen
    assert not case.picker.refresh_button.isEnabled()


def test_discovery_insertions_above_focused_model_keep_identity_visible_and_in_place(make_picker):
    models = [("studio/model-%02d:Q4_K_M" % i, "Model %02d" % i, i == 0) for i in range(80)]
    case = make_picker([("ollama", "Ollama", models)], scale=1.25)
    target = model_item(case.picker, "ollama", "studio/model-60:Q4_K_M")
    case.picker.list.setCurrentItem(target)
    case.picker.list.setFocus()
    case.picker.list.scrollToItem(target, QtWidgets.QAbstractItemView.PositionAtCenter)
    pump()
    before = case.picker.list.visualItemRect(target)
    assert case.picker.list.hasFocus()
    assert case.picker.list.viewport().rect().contains(before)
    old_current = case.picker.current.accessibleName()
    case.data[0][2][:0] = [("new/model-%02d:Q8_0" % i, "New model %02d" % i, False) for i in range(12)]
    case.discovery.changed.emit()
    pump()
    current = case.picker.list.currentItem()
    after = case.picker.list.visualItemRect(current)
    assert identity(current) == ("ollama", "studio/model-60:Q4_K_M")
    assert case.picker.list.hasFocus()
    assert case.picker.list.viewport().rect().contains(after)
    assert after.top() == before.top()
    assert case.picker.current.accessibleName() == old_current and not case.chosen


@pytest.mark.parametrize("close_parent", [False, True])
def test_deleted_popup_ignores_late_discovery_and_fresh_popup_still_refreshes(make_picker, close_parent):
    case = make_picker()
    destroyed = QtTest.QSignalSpy(case.picker.destroyed)
    before = len(case.reads)
    if close_parent:
        case.parent.deleteLater()
    else:
        case.picker.close()
    pump(delete=True)
    assert destroyed.count() == 1 and not isValid(case.picker)
    QtCore.QTimer.singleShot(0, case.discovery.changed.emit)
    pump()
    assert len(case.reads) == before and not case.chosen
    fresh = make_picker()
    reads_before = len(fresh.reads)
    fresh.discovery.text = "Fresh popup gets its own discovery"
    fresh.discovery.changed.emit()
    pump()
    assert len(fresh.reads) == reads_before + 1
    assert fresh.picker.status.text() == fresh.discovery.text


def test_connection_request_does_not_pick_a_model(make_picker):
    case = make_picker()
    case.picker.connect_button.click()
    assert case.connections == [True] and not case.chosen and not case.configurations
    assert not case.picker.isVisible()
