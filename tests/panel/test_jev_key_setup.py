"""Native key-entry sequences must not alter models, permissions, or send data."""
import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

if not isinstance(QtWidgets.QApplication, type):
    pytest.skip("Native Qt required", allow_module_level=True)

from PySide6 import QtCore, QtTest


class Discovery(QtCore.QObject):
    changed = QtCore.Signal()

    def names(self):
        return None

    def message(self):
        return ""

    def refresh(self):
        pass


@pytest.fixture
def setup(monkeypatch, tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "panel.json"))
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "policy.json"))
    monkeypatch.setenv("SYNAPSE_JEV", "off")
    from synapse.jev import adapter, credentials
    from synapse.panel import connections, settings
    from synapse.panel.connection_dialog import ConnectionDialog
    credentials.clear_session_key()
    monkeypatch.setattr(credentials, "_configured_key", lambda: None)
    monkeypatch.setattr(adapter, "_post", lambda *a, **k: pytest.fail("Key setup sent to TypeSafe"))
    monkeypatch.setattr(connections, "check_connection", lambda *a, **k: pytest.fail("Key setup checked a generation model"))
    settings.save_settings({**settings.default_settings(), "provider_id": "ollama"})
    widgets = []

    def make():
        widget = ConnectionDialog(provider_id="claude", discovery=Discovery())
        widgets.append(widget)
        widget.show()
        app.processEvents()
        return widget

    yield make, tmp_path, app
    for widget in widgets:
        widget.reject()
        widget.deleteLater()
    app.processEvents()
    credentials.clear_session_key()


def test_masked_save_is_local_and_does_not_enable_jev_or_change_provider(setup):
    from synapse.jev import adapter
    make, path, app = setup
    widget = make()
    before = (path / "panel.json").read_bytes()
    assert widget.jev_key.echoMode() == QtWidgets.QLineEdit.Password
    assert widget.jev_key.text() == ""
    assert not widget.jev_key_save.isEnabled()
    assert "No TypeSafe key" in widget.jev_key_status.text()
    widget.jev_key.setText("synthetic-ui-key")
    widget.jev_key_save.click()
    assert adapter.resolve_key() == "synthetic-ui-key"
    assert widget.jev_key.text() == ""
    assert "Session key saved" in widget.jev_key_status.text()
    assert "not been checked" in widget.jev_key_status.text()
    assert widget.jev_status.text().startswith("Off.")
    assert widget.selection is None
    assert (path / "panel.json").read_bytes() == before
    assert not (path / "policy.json").exists()
    assert all("synthetic-ui-key" not in label.text() for label in widget.findChildren(QtWidgets.QLabel))


def test_cancel_drops_unsaved_entry_and_reopen_retains_explicitly_saved_key(setup):
    from synapse.jev import adapter
    make, _, _ = setup
    first = make()
    first.jev_key.setText("unsaved-test-key")
    first.reject()
    assert first.jev_key.text() == ""
    assert adapter.resolve_key() is None
    second = make()
    second.jev_key.setText("saved-test-key")
    second.jev_key_save.click()
    second.reject()
    third = make()
    assert third.jev_key.text() == ""
    assert "Session key saved" in third.jev_key_status.text()
    assert adapter.resolve_key() == "saved-test-key"


def test_clear_reports_environment_fallback_without_revealing_it(setup, monkeypatch):
    from synapse.jev import adapter, credentials
    make, _, _ = setup
    monkeypatch.setattr(credentials, "_configured_key", lambda: "fallback-test-key")
    widget = make()
    assert "TYPESAFE_API_KEY" in widget.jev_key_status.text()
    widget.jev_key.setText("override-test-key")
    widget.jev_key_save.click()
    widget.jev_key_clear.click()
    assert adapter.resolve_key() == "fallback-test-key"
    assert "TYPESAFE_API_KEY" in widget.jev_key_status.text()
    assert not widget.jev_key_clear.isEnabled()
    assert "fallback-test-key" not in widget.jev_key_status.text()


def test_invalid_key_does_not_replace_saved_key(setup):
    from synapse.jev import adapter
    make, _, _ = setup
    widget = make()
    widget.jev_key.setText("saved-test-key")
    widget.jev_key_save.click()
    widget.jev_key.setText("invalid key secret")
    widget.jev_key_save.click()
    assert adapter.resolve_key() == "saved-test-key"
    assert "invalid characters" in widget.jev_key_status.text()
    assert "invalid key secret" not in widget.jev_key_status.text()


def test_top_setup_action_reveals_and_focuses_key_field(setup):
    make, _, app = setup
    widget = make()
    widget.resize(600, 450)
    app.processEvents()
    widget.jev_key_setup.click()
    app.processEvents()
    point = widget.jev_key.mapTo(widget._content_scroll.viewport(), QtCore.QPoint(0, 0))
    assert widget._content_scroll.viewport().rect().intersects(QtCore.QRect(point, widget.jev_key.size()))
    assert widget.jev_key.hasFocus()


@pytest.mark.parametrize("key", [QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter])
def test_enter_saves_only_jev_key_without_accepting_dialog(setup, monkeypatch, key):
    from synapse.jev import adapter
    make, path, app = setup
    widget = make()
    monkeypatch.setattr(widget, "accept", lambda: pytest.fail("Enter accepted connection"))
    widget.jev_key.setFocus()
    widget.jev_key.setText("enter-test-key")
    QtTest.QTest.keyClick(widget.jev_key, key)
    app.processEvents()
    assert adapter.resolve_key() == "enter-test-key"
    assert widget.isVisible()
    assert widget.selection is None
    assert widget._future is None
    assert not (path / "policy.json").exists()
