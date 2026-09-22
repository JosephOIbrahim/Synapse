"""Native Connections controls keep ranking, measurement and permission distinct."""
from types import SimpleNamespace

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore

if not isinstance(QtWidgets.QApplication, type):
    pytest.skip("Native Qt required", allow_module_level=True)


class Discovery(QtCore.QObject):
    changed = QtCore.Signal()

    def names(self):
        return None

    def message(self):
        return ""

    def refresh(self):
        pass


@pytest.fixture
def dialog(monkeypatch, tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("SYNAPSE_MODEL_POLICY", str(tmp_path / "policy.json"))
    monkeypatch.setenv("SYNAPSE_JEV", "off")
    from synapse.panel import settings
    from synapse.panel.connection_dialog import ConnectionDialog
    from synapse.jev import adapter
    monkeypatch.setattr(adapter, "_post", lambda *a, **k: pytest.fail("No live JEV calls"))
    settings.save_settings({**settings.default_settings(), "provider_id": "ollama",
                           "model_choice": {"mode": "exact", "value": "artist-picked"}})
    widget = ConnectionDialog(provider_id="claude", discovery=Discovery())
    widget.show()
    app.processEvents()
    yield widget, tmp_path
    widget.reject()
    widget.deleteLater()
    app.processEvents()


def test_save_ranking_without_checking_provider_does_not_grant_permission(dialog):
    from synapse.panel import settings
    widget, path = dialog
    assert not widget.jev_suggestions.isChecked()
    assert not widget.use.isEnabled()
    widget.jev_suggestions.setChecked(True)
    widget.jev_save.click()
    loaded = settings.load_settings()
    assert loaded["jev_suggestions_enabled"] is True
    assert loaded["jev_routing_mode"] == "off"
    assert loaded["provider_id"] == "ollama"
    assert loaded["model_choice"] == {"mode": "exact", "value": "artist-picked"}
    assert not (path / "policy.json").exists()
    assert "disabled by SYNAPSE_JEV" in widget.jev_status.text()
    assert widget.selection is None


def test_second_save_can_disable_ranking_without_disabling_measurement(dialog):
    from synapse.panel import settings
    widget, _ = dialog
    widget.jev_suggestions.setChecked(True)
    widget.jev_routing.setCurrentIndex(widget.jev_routing.findData("shadow"))
    widget.jev_save.click()
    widget.jev_suggestions.setChecked(False)
    widget.jev_save.click()
    loaded = settings.load_settings()
    assert loaded["jev_suggestions_enabled"] is False
    assert loaded["jev_routing_mode"] == "shadow"


def test_ranking_ready_status_does_not_claim_shadow_measurement(dialog, monkeypatch):
    from synapse import model_access as access
    from synapse.jev import adapter
    widget, _ = dialog
    monkeypatch.delenv("SYNAPSE_JEV")
    monkeypatch.setattr(adapter, "resolve_key", lambda: "synthetic")
    monkeypatch.setattr(access, "require_access", lambda *a, **k: None)
    widget.jev_suggestions.setChecked(True)
    widget.jev_save.click()
    assert "rank actions when you ask" in widget.jev_status.text()
    assert "measure future tasks" not in widget.jev_status.text()


def test_saving_failure_retains_previous_preference(dialog, monkeypatch):
    from synapse.panel import settings
    widget, _ = dialog
    monkeypatch.setattr(settings, "save_settings", lambda *a, **k: False)
    widget.jev_suggestions.setChecked(True)
    widget.jev_save.click()
    assert settings.load_settings()["jev_suggestions_enabled"] is False
    assert "could not be saved" in widget.jev_status.text()


def test_use_model_persists_ranking_choice_too(dialog, monkeypatch):
    from synapse.panel import settings
    widget, _ = dialog
    widget.jev_suggestions.setChecked(True)
    widget._request_inputs = widget._inputs()
    widget._checked = SimpleNamespace(spec="checked", facts="checked",
        provider=SimpleNamespace(resolve_key=lambda: "synthetic"), release=lambda: None)
    monkeypatch.setattr(widget, "accept", lambda: None)
    widget._use()
    assert settings.load_settings()["jev_suggestions_enabled"] is True
    assert widget.selection[:3] == ("checked", "checked", "synthetic")
