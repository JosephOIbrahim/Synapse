"""Disposable native Qt checks. Run with Houdini's plain Python, never hython.

Uses real Qt widgets, QThread and shipped panel methods; only the farm transport
is injected. The panel's live observation startup is deliberately not run.
No Houdini import, model, network, settings save or render is permitted.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import http.client
import json
import os
import sys
import threading
import time
import traceback
import faulthandler

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
NATIVE_HOST = os.environ.get("SYNAPSE_NATIVE_QT_HOST") == "hython"
if not NATIVE_HOST:
    assert "hou" not in sys.modules
    sys.modules["hou"] = None


def forbidden(*args, **kwargs):
    raise AssertionError("Native Render QA may not contact a service or model")


http.client.HTTPConnection = forbidden
http.client.HTTPSConnection = forbidden

from PySide6 import QtCore, QtGui, QtWidgets, QtTest
import shiboken6
from synapse.panel import render_workspace as rw
from synapse.panel import synapse_panel as sp
from synapse.panel.chat_display import ChatDisplay
from synapse.panel.designsystem import qss

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
MESSAGES = []
CHECKS = []
LAYOUTS = []


def qt_message(kind, context, message):
    MESSAGES.append(message)


QtCore.qInstallMessageHandler(qt_message)
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
app.setQuitOnLastWindowClosed(False)
for filename in ("segoeui.ttf", "seguisb.ttf", "consola.ttf"):
    font = Path("C:/Windows/Fonts") / filename
    if font.is_file():
        QtGui.QFontDatabase.addApplicationFont(str(font))
app.setFont(QtGui.QFont("Segoe UI", 10))


def pump_until(predicate, timeout=4):
    end = time.monotonic() + timeout
    while not predicate():
        app.processEvents()
        if time.monotonic() > end:
            raise AssertionError("Qt condition timed out")
        time.sleep(.005)
    app.processEvents()


def settle():
    for _ in range(4):
        app.processEvents()
        time.sleep(.01)


class FakeFarm:
    """In-memory, deterministic tool replies; no service execution."""

    def __init__(self):
        self.calls = []
        self.jobs = {}
        self.lose_submit = False
        self.fail_read = False
        self.gui_thread = threading.get_ident()

    def transport(self, tool, arguments):
        assert threading.get_ident() != self.gui_thread, "Farm transport ran on the GUI thread"
        self.calls.append((tool, deepcopy(arguments)))
        if tool == "synapse_farm_inspect":
            return {"status": "ready", "source_hip": "C:/shots/coffee/lighting.hip",
                    "source_node": "/stage/render_source", "unsaved": False,
                    "source_nodes": [{"path": "/stage/render_source", "label": "/stage/render_source"}],
                    "frames": [1001, 1003, 1], "note": "Saved scene ready."}
        if tool == "synapse_farm_capabilities":
            return {"profiles": [{"id": "local", "label": "This computer", "available": True},
                                 {"id": "hqueue", "label": "HQueue", "available": False,
                                  "reason": "HQueue is not configured. Open Settings for setup details."}]}
        if tool == "synapse_farm_jobs":
            return {"jobs": list(deepcopy(self.jobs).values())}
        if tool == "synapse_farm_prepare":
            from synapse.farm.models import parse_frames
            plan = deepcopy(arguments)
            plan["frames"] = parse_frames(plan["frames"])
            job = {"request_id": plan.pop("request_id"), "state": "prepared", "plan": plan,
                   "digest": "d" * 64, "verified_frames": [], "outputs": [],
                   "total_frames": len(plan["frames"]), "revision": 1,
                   "job_dir": "C:/shots/coffee/renders/synapse/synapse_renders/native-qa",
                   "note": "Prepared saved scene and render package.", "updated_at": "2026-09-07T12:00:00Z"}
            self.jobs[job["request_id"]] = job
            return deepcopy(job)
        if tool == "synapse_farm_submit":
            job = self.jobs[arguments["request_id"]]
            assert arguments["digest"] == job["digest"]
            job.update(state="rendering", revision=job["revision"] + 1,
                       backend_id="native-qa-driver", note="Rendering the requested frames.")
            if self.lose_submit:
                return None  # The accepted job exists, but its reply is lost.
            return deepcopy(job)
        if tool == "synapse_farm_job":
            if self.fail_read:
                return "this is not a readable job record"
            return deepcopy(self.jobs[arguments["request_id"]])
        if tool == "synapse_farm_cancel":
            job = self.jobs[arguments["request_id"]]
            job.update(state="cancel_requested", revision=job["revision"] + 1,
                       note="Cancellation requested; stop has not been confirmed.")
            return deepcopy(job)
        raise AssertionError("Unexpected tool: " + tool)

    def factory(self, tool, arguments):
        return rw.FarmToolCall(tool, arguments, transport=self.transport)


def idle(dialog):
    pump_until(lambda: not dialog._inflight and not rw._ACTIVE_FARM_CALLS)


def capture(dialog, name, *, expanded=False):
    dialog.settings_toggle.setChecked(expanded)
    dialog._toggle_settings()
    dialog._scroll.verticalScrollBar().setValue(0)
    settle()
    assert dialog.width() == 320, (name, "dialog expanded horizontally", dialog.width())
    assert dialog._scroll.horizontalScrollBar().maximum() == 0
    page_width = dialog._page.width()
    for widget in (dialog.source, dialog.frames, dialog.destination, dialog.profile,
                   dialog.primary, dialog.recent, dialog.image_width, dialog.image_height, dialog.samples, dialog.zoom):
        if not widget.isVisible():
            continue
        position = widget.mapTo(dialog._page, QtCore.QPoint(0, 0))
        assert position.x() >= 0 and position.x() + widget.width() <= page_width, (name, widget.objectName())
        assert widget.height() >= QtGui.QFontMetrics(widget.font()).height(), (name, "font clipped", widget.accessibleName())
    for label in dialog.findChildren(QtWidgets.QLabel):
        if label.isVisible() and label.text():
            assert label.height() >= label.heightForWidth(label.width()), (name, "label clipped", label.text())
            position = label.mapTo(dialog._page, QtCore.QPoint(0, 0))
            assert position.x() >= 0 and position.x() + label.width() <= page_width, (name, "label extends sideways", label.text())
    for button in dialog.findChildren(rw._RenderButton):
        if button.isVisible():
            metrics = QtGui.QFontMetrics(button.font())
            needed = max(metrics.horizontalAdvance(line) for line in button.text().splitlines())
            assert button.width() >= needed + 2 * rw.t.SPACE_MD, (name, "action clipped", button.accessibleName(), button.width(), needed)
            assert button.height() >= metrics.height() * len(button.text().splitlines()), (name, "action height clipped", button.accessibleName())
    captures = []
    scrollbar = dialog._scroll.verticalScrollBar()
    positions = list(range(0, scrollbar.maximum() + 1, max(1, dialog._scroll.viewport().height() - 80)))
    if not positions or positions[-1] != scrollbar.maximum():
        positions.append(scrollbar.maximum())
    for index, position in enumerate(positions):
        scrollbar.setValue(position)
        settle()
        path = OUT / (name + "-%02d.png" % index)
        assert dialog.grab().save(str(path))
        captures.append(str(path))
    LAYOUTS.append({"name": name, "width": dialog.width(), "height": dialog.height(),
                    "scale": dialog._scale, "page_width": page_width, "scroll_max": scrollbar.maximum(),
                    "field_font_px": QtGui.QFontInfo(dialog.frames.font()).pixelSize(), "screenshots": captures})


def check_workflow():
    farm = FakeFarm()
    dialog = rw.RenderWorkspaceDialog(transport_factory=farm.factory)
    dialog.resize(320, 680)
    dialog.show()
    idle(dialog)
    assert dialog.frames.text() == "1001-1003" and dialog.source.currentData() == "/stage/render_source"
    assert dialog.primary.isEnabled() and dialog.primary.text() == "Prepare render"
    assert not dialog.open_output.isVisible() and not dialog.settings_page.isVisible()
    capture(dialog, "draft-standard")
    calls = len(farm.calls)
    dialog.frames.setFocus()
    QtTest.QTest.keyClick(dialog.frames, QtCore.Qt.Key_Return)
    settle()
    assert len(farm.calls) == calls, "Enter in a field prepared or submitted unexpectedly"
    assert dialog.isVisible(), "Enter in an editable field closed the dialog"
    dialog.profile.setCurrentIndex(dialog.profile.findData("hqueue"))
    assert not dialog.primary.isEnabled() and "not configured" in dialog.profile_note.text()
    dialog.profile.setCurrentIndex(dialog.profile.findData("local"))
    dialog.primary.click()
    idle(dialog)
    assert dialog.primary.text() == "Render 3 frames" and dialog.primary.isEnabled()
    prepared_id = dialog._model.job["request_id"]
    assert "1001-1003" in dialog.summary.text() and "256" in dialog.summary.text()
    capture(dialog, "prepared-standard")
    dialog.frames.setText("1001, 1003")
    assert dialog.primary.text() == "Prepare render" and not dialog._model.can_submit
    farm.fail_read = True
    dialog.refresh()
    idle(dialog)
    assert not dialog.primary.isEnabled(), "Unreadable retained preparation enabled a replacement prepare"
    dialog.recent.setCurrentIndex(0)
    dialog.recent.setCurrentIndex(dialog.recent.findData(prepared_id))
    idle(dialog)
    assert not dialog.primary.isEnabled(), "Reselecting cached prepared history cleared status uncertainty"
    farm.fail_read = False
    dialog.refresh()
    idle(dialog)
    dialog.frames.setText("1001, 1003")
    dialog.primary.click()
    idle(dialog)
    assert dialog._model.job["request_id"] != prepared_id
    assert dialog.primary.text() == "Render 2 frames"
    farm.lose_submit = True
    dialog.primary.click()
    idle(dialog)
    request_id = dialog._model.job["request_id"]
    assert dialog._model.job["state"] == "submission_uncertain"
    assert not dialog.primary.isEnabled() and "may have started" in dialog.status.text()
    dialog.zoom.setCurrentIndex(2)
    capture(dialog, "lost-reply-largest", expanded=True)
    dialog.refresh()
    idle(dialog)
    assert dialog._model.job["state"] == "rendering"
    assert sum(tool == "synapse_farm_submit" for tool, _ in farm.calls) == 1
    assert dialog.progress_label.text() == "0 of 2 frames verified"
    farm.fail_read = True
    dialog.refresh()
    idle(dialog)
    assert "Status unavailable" in dialog.status.text() and dialog.cancel.isEnabled()
    dialog.cancel.click()
    idle(dialog)
    farm.fail_read = False
    assert dialog._model.job["state"] == "cancel_requested"
    assert "Waiting" in dialog.status.text() and "Render cancelled." != dialog.status.text()
    capture(dialog, "cancel-requested-largest")
    farm.jobs[request_id].update(state="cancelled", revision=5, note="The detached worker confirmed it stopped.")
    dialog.refresh()
    idle(dialog)
    assert dialog.status.text() == "Render cancelled."
    farm.fail_read = True
    dialog.refresh()
    idle(dialog)
    assert "Status unavailable" in dialog.status.text() and not dialog.open_output.isVisible()
    farm.fail_read = False
    dialog.close()
    assert not dialog.isVisible() and not dialog._poll_timer.isActive()
    assert sum(tool == "synapse_farm_cancel" for tool, _ in farm.calls) == 1
    dialog.show()
    idle(dialog)
    assert dialog._model.job["request_id"] == request_id and dialog.status.text() == "Render cancelled."
    # Persisted recent records are selected by identity, never by menu position.
    dialog.recent.setCurrentIndex(dialog.recent.findData(prepared_id))
    idle(dialog)
    assert dialog._model.job["request_id"] == prepared_id and dialog.primary.text() == "Render 3 frames"
    dialog.close()
    dialog.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    CHECKS.append("prepare, exact review, edit, lost acknowledgement, refresh only, cancellation, status failure, reopen and persisted selection")


def check_output():
    farm = FakeFarm()
    dialog = rw.RenderWorkspaceDialog(transport_factory=farm.factory)
    dialog.show()
    idle(dialog)
    dialog.frames.setText("1001")
    dialog.primary.click()
    idle(dialog)
    request_id = dialog._model.job["request_id"]
    job = farm.jobs[request_id]
    job.update(state="complete", revision=4, verified=True,
               verification={"verified": True, "frames": [1001]}, verified_frames=[1001],
               outputs=[{"frame": 1001, "path": "C:/shots/coffee/renders/1001.exr", "sha256": "a" * 64,
                         "size": 8192, "width": 256, "height": 256, "verified": True}])
    dialog.refresh()
    idle(dialog)
    assert dialog.open_output.isVisible() and dialog.open_output.isEnabled()
    opened = []
    original = QtGui.QDesktopServices.openUrl
    QtGui.QDesktopServices.openUrl = lambda url: opened.append(url.toLocalFile()) or True
    try:
        # Open first re-queries that exact saved request before using its evidence.
        dialog.open_output.click()
        idle(dialog)
        assert opened == ["C:/shots/coffee/renders/1001.exr"]
        started, release = threading.Event(), threading.Event()

        def held_read(tool, arguments):
            if tool == "synapse_farm_job":
                started.set()
                release.wait(3)
            return farm.transport(tool, arguments)

        dialog._transport_factory = lambda tool, arguments: rw.FarmToolCall(tool, arguments, transport=held_read)
        dialog.open_output.click()
        pump_until(started.is_set)
        dialog.new_render.click()
        release.set()
        idle(dialog)
        assert dialog._model.job is None and len(opened) == 1, "Late Open response opened a previous selection"
        dialog._transport_factory = farm.factory
        dialog.recent.setCurrentIndex(dialog.recent.findData(request_id))
        idle(dialog)
        job["outputs"][0]["verified"] = False
        job["revision"] = 5
        dialog.open_output.click()
        idle(dialog)
        assert len(opened) == 1 and not dialog.open_output.isEnabled()
        job.update(state="failed", error_code="output_changed", revision=6,
                   verified=False, outputs=[], verified_frames=[], verification=None)
        dialog.refresh()
        idle(dialog)
        assert dialog._model.job["state"] == "failed" and not dialog.open_output.isVisible()
        dialog.new_render.click()
        idle(dialog)
        dialog.recent.setCurrentIndex(dialog.recent.findData(request_id))
        idle(dialog)
        assert dialog._model.job["state"] == "failed" and not dialog.open_output.isVisible()
        assert len(opened) == 1
    finally:
        QtGui.QDesktopServices.openUrl = original
        dialog.close()
        dialog.deleteLater()
    CHECKS.append("Open output refreshes evidence; changed selection and corrupt output evidence both refuse opening")


def check_lifetime():
    started, release, ended = threading.Event(), threading.Event(), threading.Event()

    def delayed(tool, arguments):
        started.set()
        release.wait(3)
        ended.set()
        return {"profiles": []}

    dialog = rw.RenderWorkspaceDialog(transport_factory=lambda tool, arguments: rw.FarmToolCall(tool, arguments, transport=delayed))
    dialog._call("capabilities", "synapse_farm_capabilities", {})
    pump_until(started.is_set)
    worker = next(iter(rw._ACTIVE_FARM_CALLS))
    assert worker.parent() is None and worker.isRunning()
    beats = []
    QtCore.QTimer.singleShot(0, lambda: beats.append(True))
    pump_until(lambda: bool(beats))
    dialog.close()
    dialog.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not shiboken6.isValid(dialog) and worker.isRunning()
    release.set()
    pump_until(lambda: ended.is_set() and not rw._ACTIVE_FARM_CALLS)
    CHECKS.append("actual QThread survives close and Qt destruction, GUI remains responsive, no cancel or destroyed-running thread")


def check_read_during_submission():
    farm = FakeFarm()
    dialog = rw.RenderWorkspaceDialog(transport_factory=farm.factory)
    dialog.show()
    idle(dialog)
    dialog.primary.click()
    idle(dialog)
    read_started, read_release = threading.Event(), threading.Event()
    submit_started, submit_release = threading.Event(), threading.Event()

    def held(tool, arguments):
        if tool == "synapse_farm_job":
            old = farm.transport(tool, arguments)
            read_started.set()
            read_release.wait(3)
            return old
        if tool == "synapse_farm_submit":
            submit_started.set()
            submit_release.wait(3)
        return farm.transport(tool, arguments)

    dialog._transport_factory = lambda tool, args: rw.FarmToolCall(tool, args, transport=held)
    dialog._call("job", "synapse_farm_job", {"request_id": dialog._model.job["request_id"]})
    pump_until(read_started.is_set)
    dialog.primary.click()
    pump_until(submit_started.is_set)
    read_release.set()
    pump_until(lambda: "job" not in dialog._inflight)
    assert dialog._model.pending == "submit" and dialog._model.job["state"] == "submitting"
    assert not dialog.primary.isEnabled()
    submit_release.set()
    idle(dialog)
    assert dialog._model.job["state"] == "rendering"
    dialog.close()
    dialog.deleteLater()
    CHECKS.append("a stale read cannot acknowledge a pending submission or re-enable Render")


def check_large_host():
    farm = FakeFarm()
    parent = QtWidgets.QWidget()
    parent._chrome_scale = 2.25
    dialog = rw.RenderWorkspaceDialog(parent, transport_factory=farm.factory)
    dialog.resize(320, 680)
    dialog.show()
    idle(dialog)
    dialog.zoom.setCurrentIndex(2)
    capture(dialog, "host-large-largest", expanded=True)
    dialog.close()
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    CHECKS.append("320px at largest text on a host whose base text scale is2.25")


def check_panel_routes():
    # Use the actual class, input builder, buttons, palette and _send method;
    # skip only unrelated live observers and provider startup.
    panel = sp.SynapsePanel.__new__(sp.SynapsePanel)
    QtWidgets.QWidget.__init__(panel)
    panel.setObjectName("DsRoot")
    panel.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    panel._font_scale = panel._chrome_scale = 1.0
    panel._region_cache = {}
    panel._messages = []
    panel._pending_context = []
    panel._provider_id = "ollama"
    panel._model_by_provider = {"ollama": "local:latest"}
    panel._session_keys = {}
    panel._connection_facts = {}
    panel._task_connection = None
    panel._render_token_state = lambda: None
    panel._persist_composer_height = lambda *_: None
    panel._hide_turn_receipt = lambda: None
    panel._settle_composer_height = lambda: None
    panel._prepare_connection = forbidden
    panel.setStyleSheet(qss.stylesheet(1.0))
    layout = QtWidgets.QVBoxLayout(panel)
    panel._chat = ChatDisplay(panel)
    layout.addWidget(panel._chat, 1)
    layout.addWidget(panel._build_input())
    panel._input.setPlainText("Preserve this lighting draft when I open Render.")
    panel.resize(320, 680)
    panel.show()
    settle()
    farm = FakeFarm()
    original_dialog = rw.RenderWorkspaceDialog
    rw.RenderWorkspaceDialog = lambda parent=None: original_dialog(parent, transport_factory=farm.factory)

    class BusyModel:
        def isRunning(self):
            return True

    panel._worker = BusyModel()
    marker = object()
    sp._ACTIVE_PANEL_WORKERS.add(marker)
    try:
        draft = panel._input.toPlainText()
        assert panel._send(" /RENDER ") is True
        dialog = panel._render_workspace_dialog
        idle(dialog)
        assert dialog.isVisible() and panel._input.toPlainText() == draft
        dialog.close()
        panel._render_btn.click()
        idle(dialog)
        assert dialog.isVisible() and panel._input.toPlainText() == draft
        dialog.close()
        panel._commands_btn.click()
        settle()
        palette = panel._palette
        palette._search.setText("/render")
        settle()
        entry = next(palette._list.item(index) for index in range(palette._list.count())
                     if palette._list.item(index).data(QtCore.Qt.UserRole) == "/render")
        palette._list.itemActivated.emit(entry)
        idle(dialog)
        assert dialog.isVisible() and panel._input.toPlainText() == draft
        assert not panel._messages and not panel._task_connection
        assert all(tool in {"synapse_farm_inspect", "synapse_farm_capabilities", "synapse_farm_jobs"}
                   for tool, _ in farm.calls)
        dialog.close()
        settle()
        assert panel.width() == 320
        assert panel._render_btn.isVisible()
        for button in (panel._render_btn, panel._commands_btn, panel._recipes_btn, panel._events_btn):
            assert button.width() >= button.minimumSizeHint().width()
        assert panel.grab().save(str(OUT / "panel-render-entry-320.png"))
    finally:
        sp._ACTIVE_PANEL_WORKERS.discard(marker)
        rw.RenderWorkspaceDialog = original_dialog
        panel._worker = None
        panel._location_timer.stop()
        panel.hide()  # Do not run the skipped live startup's close handler.
    CHECKS.append("actual panel /render, visible Render, Commands route while model busy; draft preserved; zero admission/model calls")
    return panel


if __name__ == "__main__":
    faulthandler.enable()
    faulthandler.dump_traceback_later(30)
    failed = None
    keep_panel = None
    try:
        check_workflow()
        check_output()
        check_lifetime()
        check_read_during_submission()
        check_large_host()
        keep_panel = check_panel_routes()
        assert not rw._ACTIVE_FARM_CALLS
        assert not any("QThread: Destroyed" in message or "Traceback" in message for message in MESSAGES)
    except BaseException:
        failed = traceback.format_exc()
        print(failed, flush=True)
    finally:
        for widget in app.topLevelWidgets():
            widget.hide()
            widget.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()
        (OUT / "qt-messages.txt").write_text("\n".join(MESSAGES), encoding="utf-8")
        receipt = {"passed": failed is None, "python": sys.version, "qt": QtCore.qVersion(),
                   "executable": sys.executable, "host": "hython" if NATIVE_HOST else "ordinary-python",
                   "native_modules": {name: str(getattr(sys.modules.get(name), "__file__", None)) for name in ("hou", "_hou", "_pdg")},
                   "platform": app.platformName(), "checks": CHECKS, "layouts": LAYOUTS,
                   "error": failed, "limitations": ["Injected farm transport; no real render or scheduler",
                   "Actual panel methods and widgets; unrelated live observation startup deliberately skipped",
                   "Offscreen Qt; no live artist Houdini session"]}
        (OUT / "native-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps({"passed": failed is None, "checks": len(CHECKS), "layouts": len(LAYOUTS)}), flush=True)
    print("Native Qt assertions and widget cleanup finished.", flush=True)
    app.quit()
    shiboken6.delete(app)
    print("QApplication deleted.", flush=True)
    QtCore.qInstallMessageHandler(None)
    print("Remaining Python threads: " + repr([(thread.name, thread.daemon) for thread in threading.enumerate()]), flush=True)
    sys.exit(1 if failed else 0)
