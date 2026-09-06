"""Offscreen interaction checks using real Qt; no live Houdini or network.

Run with Houdini's plain python313/python.exe (not hython). Optional first
argument names a directory for screenshots. No product settings are written.
"""
from pathlib import Path
import os
import sys
import tempfile
import threading
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
# Explicit absence in this new standalone process; never unload a real hou.
assert "hou" not in sys.modules
sys.modules["hou"] = None

import http.client


def no_network(*args, **kwargs):
    raise AssertionError("Offscreen checks may not contact any service")


http.client.HTTPConnection = no_network
http.client.HTTPSConnection = no_network

from PySide6 import QtWidgets, QtGui, QtCore
evidence_dir = (Path(sys.argv[1]).resolve() if len(sys.argv) > 1
                else Path(tempfile.mkdtemp(prefix="synapse-first-session-qt-")))
evidence_dir.mkdir(parents=True, exist_ok=True)


def qt_message(_kind, _context, message):
    with (evidence_dir / "qt-messages.txt").open("a", encoding="utf-8") as log:
        log.write(message + "\n")
QtCore.qInstallMessageHandler(qt_message)
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
# The plain Houdini interpreter does not load the host's system font setup.
# Supply the actual Windows font for this offscreen process only.
for font_file in ("segoeui.ttf", "seguisb.ttf", "consola.ttf"):
    path = Path("C:/Windows/Fonts") / font_file
    if path.is_file():
        QtGui.QFontDatabase.addApplicationFont(str(path))
app.setFont(QtGui.QFont("Segoe UI", 10))
from synapse.panel import connections as cn
from synapse.panel.connection_dialog import ConnectionDialog
from synapse.panel.message_formatter import format_response
from synapse.panel.synapse_panel import SynapsePanel
from synapse.panel.chat_display import ChatDisplay
from synapse.panel.designsystem import qss



def pump_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while not predicate():
        app.processEvents()
        if time.monotonic() > end:
            raise AssertionError("Qt condition timed out")
        time.sleep(.005)
    app.processEvents()


def fake_check(spec, key):
    return cn.ConnectionCheck(True, "Service reached · model listed · generation untested. Local",
                              (spec.model,), cn.ConnectionFacts(spec,
                              {"size": 100, "details": {"format": "gguf"}}, time.time()))


def check_dialog():
    # A deliberately delayed result must not freeze Qt or apply to a new choice.
    release = threading.Event()
    started = threading.Event()

    def delayed(spec, key):
        started.set()
        release.wait(2)
        return fake_check(spec, key)

    cn.check_connection = delayed
    host = QtWidgets.QWidget()
    host.setStyleSheet(qss.stylesheet(1.0))
    dialog = ConnectionDialog(host, provider_id="ollama", models={"ollama": "local:latest"})
    dialog.key.setText("session-only-test-key")
    dialog.show()
    dialog._check()
    pump_until(started.is_set)
    beats = []
    QtCore.QTimer.singleShot(0, lambda: beats.append(True))
    pump_until(lambda: bool(beats))
    assert dialog._future is not None and not dialog._future.done()
    dialog.model.setCurrentText("changed:latest")
    release.set()
    pump_until(lambda: dialog._future is None)
    assert not dialog.use.isEnabled() and dialog._checked is None
    assert "Selection changed" in dialog.status.text()

    cn.check_connection = fake_check
    dialog._check()
    pump_until(lambda: dialog._future is None)
    assert dialog.use.isEnabled()
    assert dialog._checked.facts.location == "Local"
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
        directory.mkdir(parents=True, exist_ok=True)
        dialog.resize(550, 580)
        app.processEvents()
        dialog.grab().save(str(directory / "connection-setup.png"))
    bound = dialog._checked
    dialog._use()
    assert dialog.selection[0].model == "changed:latest"
    assert dialog.selection[2] == "session-only-test-key"
    assert not dialog.key.text() and not dialog._keys
    assert bound.provider.resolve_key() is None
    dialog.selection = None
    dialog.deleteLater()
    app.processEvents()

    cancelled = ConnectionDialog(provider_id="ollama", models={"ollama": "local:latest"})
    cancelled.key.setText("discard-this-key")
    cancelled.reject()
    assert cancelled.selection is None and not cancelled.key.text()
    cancelled.deleteLater()
    app.processEvents()


def check_rendering():
    document = QtGui.QTextDocument()
    document.setHtml(format_response("## Light setup\n\n**Key light** and *fill*.\n\n1. Select /stage/light\n2. Set intensity\n\n```python\nnode = '/stage/light'\n```"))
    text = document.toPlainText()
    assert "##" not in text and "**" not in text
    assert "Light setup" in text and "node = '/stage/light'" in text
    block = document.begin()
    found_bold = found_list = False
    while block.isValid():
        found_list = found_list or block.textList() is not None
        it = block.begin()
        while not it.atEnd():
            fragment = it.fragment()
            if fragment.isValid() and "Key light" in fragment.text():
                found_bold = fragment.charFormat().fontWeight() >= QtGui.QFont.Bold
            it += 1
        block = block.next()
    assert found_bold and found_list
    chat = ChatDisplay()
    chat.append_synapse_message("[Docs](https://example.invalid/docs)")
    assert not chat.openLinks()
    before = chat.toPlainText()
    opened = []
    original = QtGui.QDesktopServices.openUrl
    QtGui.QDesktopServices.openUrl = lambda url: opened.append(url.toString())
    try:
        chat._on_anchor_clicked(QtCore.QUrl("https://example.invalid/docs"))
        chat._on_anchor_clicked(QtCore.QUrl("file:///private/file"))
        assert opened == ["https://example.invalid/docs"]
        assert chat.toPlainText() == before
    finally:
        QtGui.QDesktopServices.openUrl = original


def check_composer():
    # Use real panel methods and widgets without its live observation startup.
    panel = SynapsePanel.__new__(SynapsePanel)
    QtWidgets.QWidget.__init__(panel)
    panel.setObjectName("DsRoot")
    panel.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    panel.setWindowTitle("SYNAPSE · first-session preview")
    panel._font_scale = panel._chrome_scale = 1.0
    panel._region_cache = {}
    panel._messages = []
    panel._worker = panel._task_connection = None
    panel._pending_context = ["/stage/light"]
    panel._provider_id = "ollama"
    panel._model_by_provider = {"ollama": "local:latest"}
    panel._session_keys = {}
    panel._connection_facts = {}
    panel._render_token_state = lambda: None
    panel._persist_composer_height = lambda *_: None
    panel._hide_turn_receipt = lambda: None
    panel._settle_composer_height = lambda: None
    panel.setStyleSheet(qss.stylesheet(1.0))
    layout = QtWidgets.QVBoxLayout(panel)
    panel._chat = ChatDisplay(panel)
    layout.addWidget(panel._chat, 1)
    layout.addWidget(panel._build_input())
    panel._chat.append_user_message("Help me make this light softer.")
    panel._chat.append_synapse_message("## A softer key light\n\nIncrease the **light size** first.\n\n1. Select /stage/key_light\n2. Increase its width and height\n3. Compare the shadow edge\n\n`/stage/key_light` remains literal in code.", signed="ollama/local:latest")
    panel._input.setPlainText("Keep my draft when I open commands.")
    panel._input.set_user_height(130)
    panel.resize(480, 740)
    panel.show()
    app.processEvents()
    draft = panel._input.toPlainText()
    panel._commands_btn.click()
    app.processEvents()
    assert getattr(panel, "_palette", None) is not None
    panel._palette.close()
    app.processEvents()
    assert panel._input.toPlainText() == draft
    panel._allow_connection = lambda _: False
    panel._on_submit()
    assert panel._input.toPlainText() == draft
    assert panel._pending_context == ["/stage/light"] and panel._messages == []
    for width in (360, 480, 720):
        panel.resize(width, 740)
        app.processEvents()
        assert panel._commands_btn.width() >= panel._commands_btn.minimumSizeHint().width()
        assert panel._connection_status.geometry().right() <= panel.width()
    if len(sys.argv) > 1:
        panel.resize(480, 740)
        app.processEvents()
        panel.grab().save(str(Path(sys.argv[1]) / "first-session-panel.png"))
    panel._location_timer.stop()
    panel.hide()
    return panel  # retain until QApplication teardown; do not call live closeEvent


def check_parent_destruction():
    from functools import partial
    from synapse.panel import synapse_panel as sp
    from synapse.panel.providers.custom_provider import CustomProvider
    import shiboken6

    release = threading.Event()
    class WaitingWorker(QtCore.QThread):
        def run(self):
            release.wait(2)

    parent = QtWidgets.QWidget()
    keys = {"test": "session-key"}
    parent.destroyed.connect(keys.clear)
    worker = WaitingWorker(parent=None)
    bound = cn.bind_provider(CustomProvider(base_url="https://example.invalid/v1", model="a"), key="session-key")
    worker.finished.connect(bound.release)
    worker.finished.connect(partial(sp._release_panel_worker, worker))
    sp._ACTIVE_PANEL_WORKERS.add(worker)
    worker.start()
    pump_until(worker.isRunning)
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not shiboken6.isValid(parent) and not keys
    assert worker.isRunning() and bound.provider.resolve_key() == "session-key"
    release.set()
    pump_until(lambda: not sp._ACTIVE_PANEL_WORKERS)
    assert bound.provider.resolve_key() is None


def check_worker_wiring(panel):
    """Exercise the real panel start/completion slots and QThread signals."""
    from synapse.panel import synapse_panel as sp
    from synapse.panel.providers.custom_provider import CustomProvider
    from synapse.server import session_store

    release = threading.Event()
    original_worker = sp.ClaudeWorker
    original_tools = sp.get_anthropic_tools
    original_save = session_store.save_conversation
    saved = []
    class PreviewWorker(original_worker):
        def _conversation_loop(self, api_key):
            release.wait(2)
            if not self._abort:
                self.token_received.emit("Finished the test task.")

    sp.ClaudeWorker = PreviewWorker
    sp.get_anthropic_tools = lambda: []
    session_store.save_conversation = lambda messages: saved.append(list(messages))
    panel._build_system_prompt = lambda: "Test context"
    panel._set_thinking = lambda _: None
    panel._set_busy = lambda value: setattr(panel, "_was_busy", value)
    panel._turn_evidence = lambda: ([], [], [])
    panel._refresh_token_surfaces = lambda: None
    panel._refresh_engine_selector = lambda: None
    panel._tool_executor = None
    try:
        for cancel in (False, True):
            release.clear()
            bound = cn.bind_provider(CustomProvider(base_url="https://example.invalid/v1", model="model-a"), key="ephemeral-key")
            panel._prepare_connection = lambda: bound
            panel._allow_connection = lambda _: True
            assert panel._send("Run the test task")
            worker = panel._worker
            assert worker.parent() is None and worker in sp._ACTIVE_PANEL_WORKERS
            if cancel:
                worker.abort()
            panel._provider_id = "gemini"  # next selection cannot rewrite credit
            release.set()
            pump_until(lambda: panel._task_connection is None and not sp._ACTIVE_PANEL_WORKERS)
            assert panel._worker is None and not panel._was_busy
            assert bound.provider.resolve_key() is None
            if not cancel:
                assert "signed custom/model-a" in panel._chat.toPlainText()
        assert len(saved) == 2
    finally:
        release.set()
        sp.ClaudeWorker = original_worker
        sp.get_anthropic_tools = original_tools
        session_store.save_conversation = original_save


if __name__ == "__main__":
    print("Checking connection dialog…", flush=True)
    check_dialog()
    print("Checking text rendering…", flush=True)
    check_rendering()
    check_parent_destruction()
    print("Checking composer and palette…", flush=True)
    try:
        preview = check_composer()
        check_worker_wiring(preview)
    except BaseException:
        import traceback
        error = traceback.format_exc()
        (evidence_dir / "qt-exception.txt").write_text(error, encoding="utf-8")
        print(error, flush=True)
        raise
    print("PASS: real Qt async/stale-result/key-lifetime checks, Markdown rendering, draft preservation, palette, and 360/480/720px composer.")
