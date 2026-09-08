"""Explicit diagnostics: truthful reports, real worker dispatch and repeat use."""
import json
import threading
import time

import pytest

from synapse.panel import doctor_dialog


def report():
    return {"checks": [
        {"name": "version", "status": "ok", "detail": "Running build matches"},
        {"name": "log_file", "status": "fail", "detail": "Log is missing"},
        {"name": "vector_recall", "status": "skipped", "detail": "No index exists"},
    ], "summary": {"ok": 99, "fail": 0, "skipped": 0}, "bundle": None}


def envelope(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}]}


@pytest.mark.parametrize("wrap", [lambda x: x, envelope, lambda x: {"structuredContent": x}])
def test_report_counts_actual_checks_and_keeps_absence_distinct(wrap):
    text = doctor_dialog.format_report(wrap(report()))
    assert text.startswith("1 passed · 1 need attention · 1 not checked")
    assert "NEEDS ATTENTION — log file\nLog is missing" in text
    assert "NOT CHECKED — vector recall\nNo index exists" in text
    assert "99 passed" not in text


@pytest.mark.parametrize("value", [None, {}, {"checks": []}, envelope({"status": "done"}),
    {"content": [{"type": "text", "text": "not a report"}]},
    {"checks": [{"name": "unknown", "status": "unknown", "detail": "Not measured"}]}])
def test_missing_or_unreadable_report_is_never_success(value):
    with pytest.raises(ValueError):
        doctor_dialog.format_report(value)


def test_mcp_tool_error_cannot_be_hidden_by_a_report():
    value = envelope(report())
    value["isError"] = True
    with pytest.raises(ValueError):
        doctor_dialog.format_report(value)


@pytest.fixture
def qt(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SYNAPSE_PANEL_SETTINGS", str(tmp_path / "settings.json"))
    monkeypatch.setenv("SYNAPSE_REDUCED_MOTION", "1")
    QtWidgets = doctor_dialog.QtWidgets
    if QtWidgets is None or not isinstance(getattr(QtWidgets, "QApplication", None), type):
        pytest.skip("Requires real PySide; run with Houdini's Python")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def wait_until(app, predicate):
    deadline = time.monotonic() + 4
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert predicate(), "Qt worker did not settle within four seconds"
    app.processEvents()


def test_button_runs_off_thread_once_then_runs_again_without_a_model(qt, monkeypatch):
    from synapse.panel import tool_executor
    from synapse.panel.synapse_panel import SynapsePanel
    calls, entered, release = [], threading.Event(), threading.Event()

    def invoke(name, args):
        calls.append((name, args, threading.current_thread()))
        entered.set()
        assert release.wait(3)
        return envelope(report())

    monkeypatch.setattr(tool_executor, "try_mcp_tool_call", invoke)
    monkeypatch.setattr(SynapsePanel, "_send", lambda *a, **k: pytest.fail("No model turn"))
    p = SynapsePanel()
    p.resize(340, 760)
    p.show()
    qt.processEvents()
    try:
        assert not calls  # construction/polling must never launch the doctor
        assert p._doctor_btn.isVisible()
        assert p._doctor_btn.width() >= p._doctor_btn.sizeHint().width()
        p._doctor_btn.click()
        d = p._doctor_dialog
        wait_until(qt, entered.is_set)
        assert not d.run_button.isEnabled()
        assert d.run_button.text() == "Checking…"
        p._doctor_btn.click()
        d.run_check()
        assert len(calls) == 1
        # Closing/reopening during the same request must not launch another.
        d.close()
        p._doctor_btn.click()
        assert len(calls) == 1
        release.set()
        wait_until(qt, lambda: d._worker is None)
        assert d.report.toPlainText().startswith("1 passed · 1 need attention")
        d.run_button.click()
        wait_until(qt, lambda: d._worker is None)
        assert len(calls) == 2
        assert all(name == "synapse_doctor" and args == {"bundle": False}
                   and thread is not threading.main_thread() for name, args, thread in calls)
        assert d.copy_button.isEnabled()
    finally:
        release.set()
        if hasattr(p, "_doctor_dialog"):
            wait_until(qt, lambda: p._doctor_dialog._worker is None)
            p._doctor_dialog.close()
        p.close()


@pytest.mark.parametrize("response", [None, RuntimeError("Timed out; check still running"),
    {"isError": True, "content": [{"type": "text", "text": "Tool refused"}]}])
def test_offline_timeout_and_tool_error_are_visible_and_can_recover(qt, monkeypatch, response):
    from synapse.panel import tool_executor
    def invoke(*_):
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(tool_executor, "try_mcp_tool_call", invoke)
    d = doctor_dialog.DoctorDialog()
    try:
        d.run_check()
        wait_until(qt, lambda: d._worker is None)
        assert "check unavailable" in d.report.toPlainText()
        assert "passed" not in d.report.toPlainText()
        monkeypatch.setattr(tool_executor, "try_mcp_tool_call", lambda *_: envelope(report()))
        d.run_button.click()
        wait_until(qt, lambda: d._worker is None)
        assert d.report.toPlainText().startswith("1 passed")
    finally:
        d.close()


def test_deleted_panel_does_not_destroy_running_diagnostic(qt, monkeypatch):
    from synapse.panel import tool_executor
    entered, release = threading.Event(), threading.Event()
    def invoke(*_):
        entered.set()
        assert release.wait(3)
        return envelope(report())
    monkeypatch.setattr(tool_executor, "try_mcp_tool_call", invoke)
    parent = doctor_dialog.QtWidgets.QWidget()
    d = doctor_dialog.DoctorDialog(parent)
    d.run_check()
    worker = d._worker
    wait_until(qt, entered.is_set)
    try:
        parent.deleteLater()
        doctor_dialog.QtCore.QCoreApplication.sendPostedEvents(
            None, doctor_dialog.QtCore.QEvent.DeferredDelete)
        assert worker in doctor_dialog._CALLS and worker.isRunning()
    finally:
        release.set()
        wait_until(qt, lambda: worker not in doctor_dialog._CALLS)


def test_transport_discovers_only_the_running_owner_and_tracks_reconnection(qt, monkeypatch):
    import sys
    import types
    from synapse.panel.tool_executor import _MCPLocalClient

    # The worker must never query a HOM API or construct a new server owner.
    monkeypatch.setitem(sys.modules, "hou", object())
    monkeypatch.delitem(sys.modules, "synapse.server.hwebserver_adapter", raising=False)
    client = _MCPLocalClient()
    assert client.available is False
    owner = types.SimpleNamespace(_running=False, _port=9234)
    monkeypatch.setitem(sys.modules, "synapse.server.hwebserver_adapter", owner)
    assert client.available is False
    owner._running = True
    assert client.available is True and client._port == 9234
    client._session_id = "old-session"
    owner._port = 9235
    assert client.available is True and client._port == 9235
    assert client._session_id is None
    client._session_id = "new-session"
    assert client.available is True and client._session_id == "new-session"
    for invalid in (None, 0, 65536, True, "9235"):
        owner._port = invalid
        assert client.available is False and client._session_id is None


def test_old_endpoint_response_cannot_replace_reconnected_session(qt, monkeypatch):
    from synapse.panel import tool_executor
    entered, release = threading.Event(), threading.Event()
    class Reply:
        def read(self):
            return b'{"result": {}}'
        def getheader(self, name):
            return "stale-session"
    class Connection:
        def __init__(self, host, port, **kwargs):
            assert port == 9234
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            entered.set()
            assert release.wait(3)
            return Reply()
        def close(self):
            pass
    monkeypatch.setattr(tool_executor.http.client, "HTTPConnection", Connection)
    client = tool_executor._MCPLocalClient()
    client._port = 9234
    results = []
    thread = threading.Thread(target=lambda: results.append(client._post({})))
    thread.start()
    try:
        assert entered.wait(3)
        monkeypatch.setattr(client, "_detect_port", lambda: 9235)
        assert client.available
        client._session_id = "reconnected-session"
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive() and results == [{"result": {}}]
    assert client._session_id == "reconnected-session"
