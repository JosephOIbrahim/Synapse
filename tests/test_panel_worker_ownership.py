"""Exercise shipped panel reloads and actual admission/start/completion bodies.

The transport, model and widget boundaries are synthetic. Optional Qt controls
use a standalone QCoreApplication and a waiting QThread, never Houdini or a model.
"""
import ast
from contextlib import contextmanager
import gc
from pathlib import Path
import sys
import threading
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock
import weakref
import xml.etree.ElementTree as ET

import pytest

from qt_stub_window import capture_real_qt

SOURCE = Path(__file__).parents[1]
PANEL = SOURCE / "python/synapse/panel/synapse_panel.py"
LOADER = SOURCE / "houdini/python_panels/synapse_panel.pypanel"


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback, *args):
        self.callbacks.append(callback)

    def emit(self):
        for callback in tuple(self.callbacks):
            callback()


class Worker:
    created = weakref.WeakSet()
    mode = "normal"

    def __init__(self, *args, **kwargs):
        assert kwargs["parent"] is None
        assert kwargs["enforce_worker_policy"] is True
        self.running = False
        self.deleted = 0
        self.mode = type(self).mode
        for name in ("token_received", "stream_done", "stream_error", "tool_requested",
                     "tool_status", "render_receipt", "integrity_updated",
                     "activity_changed", "finished"):
            setattr(self, name, Signal())
        self.created.add(self)

    def isRunning(self):
        return self.running

    def start(self):
        if self.mode == "fail_before_start":
            raise RuntimeError("Synthetic start failure")
        self.running = True
        if self.mode == "fail_after_start":
            raise RuntimeError("Synthetic exception after thread started")
        if self.mode == "finish_inline":
            self.finish()

    def finish(self):
        self.running = False
        self.finished.emit()

    def deleteLater(self):
        self.deleted += 1


class Connection:
    def __init__(self):
        self.provider = SimpleNamespace(resolve_key=lambda: "synthetic-key")
        self.facts = SimpleNamespace(description="Synthetic approved binding")
        self.released = 0

    def release(self):
        self.released += 1


@contextmanager
def timed_phase(*args, **kwargs):
    yield SimpleNamespace(set_sizes=lambda **sizes: None)


def load_generation():
    tree = ast.parse(PANEL.read_text(encoding="utf-8"), str(PANEL))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "SynapsePanel")
    # Compile the real registry binding, whether the regression's local set or
    # the repaired import. Never inject a shared registry into the method test.
    registry = [node for node in tree.body if
                (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                  and target.id == "_ACTIVE_PANEL_WORKERS" for target in node.targets))
                or (isinstance(node, ast.ImportFrom) and any(alias.asname == "_ACTIVE_PANEL_WORKERS"
                                                            for alias in node.names))]
    assert len(registry) == 1
    release = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == "_release_panel_worker")
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in {"_send", "_start_worker"}]
    module = ModuleType("synapse.panel.synapse_panel")
    module.__dict__.update({"ClaudeWorker": Worker, "get_anthropic_tools": lambda: [],
                            "_timed_phase": timed_phase, "logger": Mock(),
                            "Qt": SimpleNamespace(QueuedConnection=object())})
    exec(compile(ast.Module(body=[*registry, release, *methods], type_ignores=[]), str(PANEL), "exec"), module.__dict__)
    sys.modules[module.__name__] = module
    sys.modules["synapse.panel"].synapse_panel = module
    return module


def reload_ui():
    script = ET.parse(LOADER).find("./interface/script").text
    exec(compile(script, str(LOADER), "exec"), {})
    assert "synapse.panel.synapse_panel" not in sys.modules
    assert not hasattr(sys.modules["synapse.panel"], "synapse_panel")
    return load_generation()


def make_panel(module):
    panel = SimpleNamespace(_worker=None, _messages=[{"role": "assistant", "content": "Previous result"}],
                            _pending_context=["/stage/artist_selection"], _permission_connections=[],
                            _tool_executor=None, _input=Mock(), _chat=Mock(),
                            _prepare_connection=Mock(side_effect=Connection),
                            _route_connection=lambda connection, text: connection,
                            _allow_connection=Mock(return_value=True),
                            _build_system_prompt=Mock(return_value="Synthetic prompt; never sent"))
    panel._send = module._send.__get__(panel)
    panel._start_worker = module._start_worker.__get__(panel)
    for name in ("_hide_turn_receipt", "_refresh_engine_selector", "_set_thinking", "_set_busy",
                 "_on_token", "_on_done", "_on_error", "_on_tool_status", "_on_render_receipt",
                 "_on_integrity", "_on_activity", "_on_worker_thread_finished"):
        setattr(panel, name, Mock())
    return panel


@pytest.fixture
def generation():
    previous = {key: value for key, value in sys.modules.items()
                if key == "synapse" or key.startswith("synapse.")}
    try:
        for key in previous:
            sys.modules.pop(key)
        for name, relative in (("synapse", "python/synapse"),
                               ("synapse.panel", "python/synapse/panel"),
                               ("synapse.host", "python/synapse/host")):
            package = ModuleType(name)
            package.__path__ = [str(SOURCE / relative)]
            sys.modules[name] = package
        model_access = ModuleType("synapse.model_access")
        model_access.capture_scope = lambda: SimpleNamespace(active=True)
        sys.modules[model_access.__name__] = model_access
        Worker.created, Worker.mode = weakref.WeakSet(), "normal"
        yield load_generation()
    finally:
        for worker in tuple(Worker.created):
            if worker.isRunning():
                worker.finish()
        for key in tuple(sys.modules):
            if key == "synapse" or key.startswith("synapse."):
                sys.modules.pop(key)
        sys.modules.update(previous)


def assert_draft_untouched(panel):
    assert panel._messages == [{"role": "assistant", "content": "Previous result"}]
    assert panel._pending_context == ["/stage/artist_selection"]
    panel._hide_turn_receipt.assert_not_called()
    panel._input.clearFocus.assert_not_called()
    panel._chat.append_user_message.assert_not_called()
    panel._set_busy.assert_not_called()


def test_shipped_reload_keeps_busy_authority_and_releases_only_completing_worker(generation):
    first = make_panel(generation)
    assert first._send("First task")
    original = first._worker
    same = make_panel(generation)
    assert not same._send("Overlapping task")
    assert_draft_untouched(same)
    newer = reload_ui()
    second = make_panel(newer)
    assert not second._send("Overlapping task after reopen")
    assert newer._ACTIVE_PANEL_WORKERS is generation._ACTIVE_PANEL_WORKERS
    assert original.isRunning() and original in newer._ACTIVE_PANEL_WORKERS
    assert_draft_untouched(second)
    original.finish()
    assert original.deleted == 1
    assert second._send("Task after completion")
    current = second._worker
    original.finish()  # delayed/duplicate notification from the old generation
    assert original.deleted == 1
    assert current.isRunning() and current in newer._ACTIVE_PANEL_WORKERS


def test_reentrant_approval_refuses_before_changing_the_previous_result(generation):
    first = make_panel(generation)
    second = make_panel(generation)
    def approve(connection):
        assert second._send("Accepted during approval callback")
        return True
    first._allow_connection.side_effect = approve
    assert not first._send("Refused after the callback")
    assert_draft_untouched(first)
    assert second._worker in generation._ACTIVE_PANEL_WORKERS


def test_reservation_blocks_reentrant_worker_setup(generation):
    first = make_panel(generation)
    second = make_panel(generation)
    def build_prompt():
        assert not second._send("Callback while first task is setting up")
        assert_draft_untouched(second)
        return "Synthetic prompt"
    first._build_system_prompt.side_effect = build_prompt
    assert first._send("First task")
    assert first._worker in generation._ACTIVE_PANEL_WORKERS


@pytest.mark.parametrize("mode", ["fail_before_start", "fail_after_start"])
def test_start_exception_never_orphans_a_running_worker(generation, mode):
    Worker.mode = mode
    first = make_panel(generation)
    assert not first._send("Synthetic failed start")
    Worker.mode = "normal"
    second = make_panel(reload_ui())
    if mode == "fail_after_start":
        original = first._worker
        assert original.isRunning() and original.deleted == 0
        assert original in generation._ACTIVE_PANEL_WORKERS
        assert not second._send("Must wait for original completion")
        assert_draft_untouched(second)
        original.finish()
    else:
        assert first._worker is None
        assert not generation._ACTIVE_PANEL_WORKERS
    assert second._send("Safe subsequent task")


def test_same_thread_completion_does_not_leave_a_stale_reservation(generation):
    Worker.mode = "finish_inline"
    first = make_panel(generation)
    assert first._send("Completes inside start")
    assert not generation._ACTIVE_PANEL_WORKERS
    assert first._worker.deleted == 1
    Worker.mode = "normal"
    second = make_panel(reload_ui())
    assert second._send("Next task")
    assert second._worker in generation._ACTIVE_PANEL_WORKERS


def test_destroyed_panel_and_module_do_not_orphan_worker(generation):
    panel = make_panel(generation)
    assert panel._send("Retained task")
    reference = weakref.ref(panel._worker)
    registry = generation._ACTIVE_PANEL_WORKERS
    newer = reload_ui()
    del panel
    gc.collect()
    assert reference() is not None and reference().isRunning()
    assert reference() in newer._ACTIVE_PANEL_WORKERS
    reference().finish()
    assert not registry
    gc.collect()
    assert reference() is None


def test_registry_reservation_is_atomic_and_identity_scoped(generation):
    registry = generation._ACTIVE_PANEL_WORKERS
    start = threading.Barrier(2)
    outcomes = []
    def reserve():
        start.wait(timeout=2)
        outcomes.append(registry.reserve())
    threads = [threading.Thread(target=reserve) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
        assert not thread.is_alive()
    owners = [item for item in outcomes if item is not None]
    assert len(owners) == 1
    registry.release_reservation(object())
    assert registry
    worker = object()
    registry.bind(owners[0], worker)
    registry.release_reservation(owners[0])
    assert worker in registry
    assert not registry.release(object())
    assert registry.release(worker)
    assert not registry


def test_native_qthread_is_retained_through_reload_and_completion(generation):
    QtCore = pytest.importorskip("PySide6.QtCore")
    if not capture_real_qt({"PySide6.QtCore": QtCore}):
        pytest.skip("Native PySide6.QtCore unavailable: resident module is a file-less test stub")
    existing = QtCore.QCoreApplication.instance()
    app = existing or QtCore.QCoreApplication([])
    release = threading.Event()
    class NativeWorker(QtCore.QThread):
        def run(self):
            release.wait(timeout=3)
    worker = NativeWorker()
    registry = generation._ACTIVE_PANEL_WORKERS
    registry.bind(registry.reserve(), worker)
    from functools import partial
    worker.finished.connect(partial(generation._release_panel_worker, worker))
    worker.start()
    reference = weakref.ref(worker)
    newer = reload_ui()
    try:
        del worker
        gc.collect()
        assert reference() is not None and reference().isRunning()
        assert reference() in newer._ACTIVE_PANEL_WORKERS
        panel = make_panel(newer)
        assert not panel._send("Cannot overlap real QThread")
        assert_draft_untouched(panel)
    finally:
        release.set()
        current = reference()
        if current is not None:
            assert current.wait(3000)
        deadline = time.monotonic() + 3
        while registry and time.monotonic() < deadline:
            app.processEvents()
        assert not registry
        if existing is None:
            # Leave later QWidget tests free to create their QApplication.
            QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
            import shiboken6
            shiboken6.delete(app)
