"""Model metadata reaches the artist's selectors without switching or sending."""
import threading
import time

import pytest

from synapse.panel import connections as cn

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    QtCore = QtWidgets = None

pytestmark = pytest.mark.skipif(
    QtWidgets is None or not isinstance(getattr(QtWidgets, "QApplication", None), type),
    reason="Requires native Qt",
)


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    monkeypatch.setattr(cn, "check_connection", lambda *a, **k: pytest.fail("Discovery is not a connection grant"))
    from synapse.server import session_store, freeze_chain
    monkeypatch.setattr(session_store, "_resolve_store_dir", lambda: str(tmp_path / "conversation"))
    yield QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    freeze_chain.shutdown_freeze_chain()


def settle(app, predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert predicate(), "Discovery did not settle"
    app.processEvents()


def test_discovery_reaches_picker_and_dialog_without_switching(app, monkeypatch):
    from synapse.panel.synapse_panel import SynapsePanel
    from synapse.panel.connection_dialog import ConnectionDialog
    names = ("artist-model:small", "artist-model:large", "relay-model:cloud")
    calls = []
    def fetch(endpoint):
        calls.append(threading.current_thread())
        return names
    monkeypatch.setattr(cn, "list_ollama_models", fetch, raising=False)
    p = SynapsePanel()
    d = None
    try:
        before = (p._provider_id, p._active_model(), list(p._messages), dict(p._connection_facts))
        discovery = p._get_ollama_discovery()
        discovery.refresh()
        settle(app, lambda: discovery.names() == names)
        assert [mid for mid, _ in p._provider_model_rows("ollama")] == list(names)
        d = ConnectionDialog(p, provider_id="ollama", models={"ollama": "artist-model:small"},
                             discovery=discovery)
        settle(app, lambda: all(d.model.findText(name) >= 0 for name in names))
        assert d.model.currentText() == "artist-model:small"
        assert not d.use.isEnabled()
        assert (p._provider_id, p._active_model(), p._messages, p._connection_facts) == before
        assert calls and all(thread is not threading.main_thread() for thread in calls)
        menu = QtWidgets.QMenu()
        p._fill_author_submenu(menu, "ollama")
        assert [a.text() for a in menu.actions() if a.isCheckable()] == list(names)
    finally:
        if d is not None:
            d.reject()
        p.close()


def test_refresh_replaces_removed_models_and_empty_is_success(app, monkeypatch):
    from synapse.panel.model_discovery import OllamaDiscovery
    replies = iter([("a", "b"), ("b", "c"), (), RuntimeError("private service details")])
    def fetch(endpoint):
        result = next(replies)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(cn, "list_ollama_models", fetch)
    discovery = OllamaDiscovery()
    try:
        for expected in (("a", "b"), ("b", "c"), ()):
            discovery.refresh()
            settle(app, lambda: not discovery.loading)
            assert discovery.names() == expected
        assert "No models" in discovery.message()
        discovery.refresh()
        settle(app, lambda: not discovery.loading)
        assert discovery.names() == ()
        assert "unavailable" in discovery.message().lower()
        assert "private" not in discovery.message()
    finally:
        discovery.close()


@pytest.mark.parametrize("return_to_first", [False, True])
def test_endpoint_switch_discards_inflight_results_and_coalesces(app, monkeypatch, return_to_first):
    from synapse.panel.model_discovery import OllamaDiscovery
    entered, release = threading.Event(), threading.Event()
    calls = []
    def fetch(endpoint):
        calls.append(endpoint)
        if len(calls) == 1:
            entered.set()
            assert release.wait(2)
            return ("old-server-model",)
        return ("new-server-model",)
    monkeypatch.setattr(cn, "list_ollama_models", fetch)
    discovery = OllamaDiscovery()
    try:
        discovery.refresh()
        settle(app, entered.is_set)
        for _ in range(3):
            discovery.refresh()
        assert len(calls) == 1
        monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11435")
        discovery.refresh()
        assert discovery.names() is None
        if return_to_first:
            monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
            discovery.refresh()
        release.set()
        settle(app, lambda: discovery.names() == ("new-server-model",))
        assert len(calls) == 2
        assert (calls[0] == calls[1]) is return_to_first
    finally:
        release.set()
        discovery.close()


def test_closing_parent_during_discovery_never_calls_deleted_qt(app, monkeypatch):
    from synapse.panel.model_discovery import OllamaDiscovery
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    def fetch(endpoint):
        entered.set()
        assert release.wait(2)
        completed.set()
        return ("late",)
    monkeypatch.setattr(cn, "list_ollama_models", fetch)
    parent = QtWidgets.QWidget()
    discovery = OllamaDiscovery(parent)
    deliveries = []
    discovery.changed.connect(lambda: deliveries.append(1))
    try:
        discovery.refresh()
        settle(app, entered.is_set)
        deliveries.clear()
        parent.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        release.set()
        settle(app, completed.is_set)
        assert not deliveries
    finally:
        release.set()


def test_setup_publishes_full_list_even_when_selected_model_is_missing(app, monkeypatch):
    from synapse.panel.synapse_panel import SynapsePanel
    from synapse.panel.connection_dialog import ConnectionDialog
    names = ("available-one", "available-two")
    monkeypatch.setattr(cn, "list_ollama_models", lambda endpoint: names)
    monkeypatch.setattr(cn, "check_connection", lambda *a: cn.ConnectionCheck(False, "Model not listed", names))
    p = SynapsePanel()
    discovery = p._get_ollama_discovery()
    d = ConnectionDialog(p, provider_id="ollama", models={"ollama": "missing"}, discovery=discovery)
    try:
        d._check()
        settle(app, lambda: d._future is None)
        assert d.model.currentText() == "missing"
        assert not d.use.isEnabled()
        assert [mid for mid, _ in p._provider_model_rows("ollama")] == list(names)
        assert not p._connection_facts
        d.reject()
        d = ConnectionDialog(p, provider_id="ollama", models={"ollama": "missing"}, discovery=discovery)
        assert all(d.model.findText(name) >= 0 for name in names)
        assert not d.use.isEnabled()
    finally:
        d.reject()
        p.close()


def test_checked_rows_do_not_leak_between_ollama_endpoints(app):
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    try:
        here = cn.ConnectionSpec("ollama", "here", "http://127.0.0.1:11434/v1/chat/completions")
        elsewhere = cn.ConnectionSpec("ollama", "elsewhere", "http://127.0.0.1:11435/v1/chat/completions")
        p._connection_facts = {here: cn.ConnectionFacts(here), elsewhere: cn.ConnectionFacts(elsewhere)}
        ids = [mid for mid, _ in p._provider_model_rows("ollama")]
        assert "here" in ids and "elsewhere" not in ids
        p._provider_id = "ollama"
        p._model_by_provider["ollama"] = "artist-saved-choice"
        p._get_ollama_discovery().remember(here.endpoint, ())
        assert p._model_menu_items() == [("artist-saved-choice", "Artist Saved Choice", True)]
    finally:
        p.close()


@pytest.mark.parametrize("menu_method", ["_open_model_menu", "_open_author_menu"])
def test_menu_cleanup_survives_parent_deletion(app, monkeypatch, menu_method):
    from synapse.panel.synapse_panel import SynapsePanel
    entered, release = threading.Event(), threading.Event()
    def fetch(endpoint):
        entered.set()
        assert release.wait(2)
        return ("late",)
    monkeypatch.setattr(cn, "list_ollama_models", fetch)
    p = SynapsePanel()
    p._provider_id = "ollama"
    discovery = p._get_ollama_discovery()
    discovery.refresh()
    settle(app, entered.is_set)
    def delete_parent():
        p.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    QtCore.QTimer.singleShot(10, delete_parent)
    try:
        getattr(p, menu_method)()
    finally:
        release.set()
