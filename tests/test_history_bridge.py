"""History is a native stack operation; opening another group prevents it."""
import asyncio
from contextlib import contextmanager
import queue
import threading
from types import SimpleNamespace

import pytest

from qt_stub_window import capture_real_qt

import shared.bridge as b
from shared.types import AgentID
from synapse.core.protocol import SynapseCommand
from synapse.panel import bridge_adapter as adapter
from synapse.server import handlers


class History:
    def __init__(self):
        self.depth = 0
        self.groups = 0
        # Top-first, as hou.undos.undoLabels() reports it: element 0 is the
        # entry performUndo() would step over next.
        self.undo = ['SYNAPSE: build', 'Artist edit']
        self.redo = []
        self.calls = []
        self.fail = False

    @contextmanager
    def group(self, label):
        self.groups += 1
        self.depth += 1
        try:
            yield
        finally:
            self.depth -= 1

    def step(self, direction):
        self.calls.append((direction, threading.get_ident()))
        if self.depth:
            raise RuntimeError('Cannot undo within an undo group')
        if self.fail:
            raise RuntimeError('History unavailable')
        source, target = (self.undo, self.redo) if direction == 'undo' else (self.redo, self.undo)
        if not source:
            raise RuntimeError('No history entry')
        target.insert(0, source.pop(0))

    def performUndo(self):
        self.step('undo')

    def performRedo(self):
        self.step('redo')

    def areEnabled(self):
        return True

    def undoLabels(self):
        return tuple(self.undo)

    def redoLabels(self):
        return tuple(self.redo)


@pytest.fixture
def env(monkeypatch):
    history = History()
    fake_hou = SimpleNamespace(undos=history, node=lambda _: None)
    monkeypatch.setattr(b, '_HOU_AVAILABLE', True)
    monkeypatch.setattr(b, '_GATES_AVAILABLE', False)
    monkeypatch.setattr(b, 'hou', fake_hou)
    monkeypatch.setattr(handlers, 'HOU_AVAILABLE', True)
    monkeypatch.setattr(handlers, 'hou', fake_hou)
    bridge = b.LosslessExecutionBridge()
    # Scene probe stands in for two actual contexts; stack behavior is real here.
    def scene_hash(path, **kwargs):
        return str(history.undo) if path == '/stage' else 'artist-obj-state'
    monkeypatch.setattr(bridge, '_compute_scene_hash', scene_hash)
    monkeypatch.setattr(adapter, 'get_bridge', lambda: bridge)
    handler = handlers.SynapseHandler()
    monkeypatch.setattr(handler._registry._floor_gate, 'wrap', lambda kind, payload, fn, **kw: fn(payload))
    monkeypatch.setattr(handler, '_submit_logs', lambda *a, **kw: None)
    from synapse.host import memory_loop
    monkeypatch.setattr(memory_loop, 'observe_operation', lambda kind, payload, fn, **kw: fn())
    return history, bridge, handler


def _session_started_before_the_build(handler):
    """Make 'SYNAPSE: build' this session's step: the baseline predates it.

    Under the R-012 session rule a SYNAPSE step that was already on the stack
    before this handler's session is refused; these tests are about the
    bridge's history path, so they record the session start explicitly.
    """
    start = History()
    start.undo, start.redo = ['Artist edit'], []
    assert handler._undo_scope.note_session_start(start)


def dispatch(handler, direction):
    return adapter.execute_through_bridge('houdini_' + direction, handler,
        SynapseCommand(id='history-test', type=direction, payload={}))


def test_real_adapter_handler_undo_redo_keeps_artist_entry(env):
    history, bridge, handler = env
    _session_started_before_the_build(handler)
    undo = dispatch(handler, 'undo')
    assert undo.success, undo.error
    assert history.undo == ['Artist edit'] and history.redo == ['SYNAPSE: build']
    assert history.groups == 0
    assert undo.data['_integrity']['undo_applicable'] is False
    assert undo.data['_integrity']['undo'] is False
    assert undo.data['_integrity']['thread'] is True
    assert undo.data['_integrity']['consent'] is True
    assert undo.data['_integrity']['composition_applicable'] is False
    assert undo.data['_integrity']['delta_hash'] != 'no_change'
    assert undo.data['_integrity']['hash_target'] == '/obj,/stage'
    redo = dispatch(handler, 'redo')
    assert redo.success, redo.error
    assert history.undo == ['SYNAPSE: build', 'Artist edit'] and not history.redo
    assert [c[0] for c in history.calls] == ['undo', 'redo']
    assert bridge.operation_stats()['operations_verified'] == 2


def test_real_adapter_handler_undo_refuses_an_artist_edit_on_top(env):
    """R-012: the agent's undo must refuse the artist's own step and name it."""
    history, bridge, handler = env
    history.undo = ['Artist edit', 'SYNAPSE: build']
    response = dispatch(handler, 'undo')
    assert not response.success
    assert 'Artist edit' in response.error
    assert 'did not record' in response.error
    assert history.calls == [] and history.groups == 0


@pytest.mark.parametrize('failure', ['exception', 'handler_error', 'empty'])
def test_history_failure_never_undoes_an_extra_artist_entry(env, failure):
    history, bridge, handler = env
    history.fail = failure != 'empty'
    if failure == 'empty':
        history.undo.clear()
    before = list(history.undo)
    if failure == 'exception':
        op = b.Operation(AgentID.BRAINSTEM, 'history_undo', 'undo', history.performUndo)
        response = bridge.execute(op)
    else:
        _session_started_before_the_build(handler)
        response = dispatch(handler, 'undo')
    assert not response.success
    expected = 'History unavailable' if history.fail else 'nothing to undo'
    assert expected in response.error
    assert history.undo == before and not history.redo
    # An empty stack is refused before the native call; a failing history is
    # attempted exactly once. Neither may touch a second entry.
    expected_calls = 0 if failure == 'empty' else 1
    assert len(history.calls) == expected_calls and history.groups == 0
    assert bridge.operation_stats()['operations_verified'] == 0


def test_ordinary_mutation_still_opens_group(env):
    history, bridge, _ = env
    seen = []
    result = bridge.execute(b.Operation(AgentID.HANDS, 'create_node', 'ordinary', lambda: seen.append(history.depth)))
    assert result.success and seen == [1] and history.groups == 1
    assert result.integrity.undo_applicable


def test_history_stays_mutating_and_respects_worker_mode(monkeypatch):
    from synapse.panel import worker_policy
    monkeypatch.delenv('SYNAPSE_WORKER_TOOL_PROFILE', raising=False)
    for direction in ('undo', 'redo'):
        name = 'houdini_' + direction
        assert not adapter.is_read_only(name)
        # R-012: history is review-gated, so the autonomous worker may no
        # longer step the undo stack in the default (standard) mode.
        monkeypatch.setenv('SYNAPSE_WORKER_TOOL_MODE', 'standard')
        allowed, reason = worker_policy.is_tool_allowed_for_worker(name)
        assert not allowed and 'review' in reason
        monkeypatch.setenv('SYNAPSE_WORKER_TOOL_MODE', 'unrestricted')
        assert worker_policy.is_tool_allowed_for_worker(name)[0]
        monkeypatch.setenv('SYNAPSE_WORKER_TOOL_MODE', 'strict')
        assert not worker_policy.is_tool_allowed_for_worker(name)[0]


def test_history_without_main_thread_refuses_before_native_call(env):
    history, bridge, handler = env
    result = []
    thread = threading.Thread(target=lambda: result.append(dispatch(handler, 'undo')))
    thread.start()
    thread.join(3)
    assert not thread.is_alive()
    assert not result[0].success and 'main thread' in result[0].error
    assert history.calls == [] and history.groups == 0


def pump_main_thread(run_worker):
    work = queue.Queue()
    result = []
    def marshal(fn, **kw):
        # Like run_on_main: a caller already on the main thread runs inline.
        if threading.current_thread() is threading.main_thread():
            return fn()
        done = threading.Event()
        value = []
        work.put((fn, done, value))
        assert done.wait(3), 'main-thread test pump timed out'
        return value[0]
    thread = threading.Thread(target=lambda: result.append(run_worker(marshal)))
    thread.start()
    fn, done, value = work.get(timeout=3)
    try:
        value.append(fn())
    finally:
        done.set()
    thread.join(3)
    assert not thread.is_alive()
    return result[0]


def test_async_bridge_history_runs_on_real_main_thread(env, monkeypatch):
    history, bridge, _ = env
    def worker(marshal):
        monkeypatch.setattr(b, '_resolve_marshal', lambda: marshal)
        return asyncio.run(bridge.execute_async(b.Operation(
            AgentID.BRAINSTEM, 'history_undo', 'undo', history.performUndo)))
    response = pump_main_thread(worker)
    assert response.success, response.error
    assert history.calls == [('undo', threading.main_thread().ident)]
    assert history.undo == ['Artist edit'] and history.groups == 0


def test_tool_executor_off_main_keeps_native_history_on_main(env, monkeypatch):
    QtWidgets = pytest.importorskip('PySide6.QtWidgets')
    if not capture_real_qt({'PySide6.QtWidgets': QtWidgets}):
        pytest.skip('Native PySide6.QtWidgets unavailable: resident module is a file-less test stub')
    from synapse.panel.tool_executor import ToolExecutor, ToolRequest
    from synapse.server import main_thread
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    history, _, handler = env
    _session_started_before_the_build(handler)
    executor = ToolExecutor()
    monkeypatch.setattr(executor, '_get_handler', lambda: handler)
    request = ToolRequest('history-test', 'houdini_undo', {})
    def worker(marshal):
        monkeypatch.setattr(main_thread, 'run_on_main', marshal)
        executor.execute_tool_off_main(request)
        return request
    response = pump_main_thread(worker)
    assert response.done.is_set() and not response.error, response.error
    assert history.calls == [('undo', threading.main_thread().ident)]
    assert history.undo == ['Artist edit'] and history.groups == 0
    executor.deleteLater()
    app.processEvents()


def test_the_bridge_captures_the_baseline_outside_its_own_group(env, monkeypatch):
    """Live check 2026-11-21: Houdini 22.0.400 lists an open group in undoLabels(),
    so a capture inside the bridge's own group made the session's first step look
    pre-session. The adapter now captures before the bridge opens its group."""
    history, bridge, handler = env
    depths = []
    real = handler._undo_scope.note_session_start

    def spy(undos):
        depths.append(history.depth)
        return real(undos)

    monkeypatch.setattr(handler._undo_scope, 'note_session_start', spy)
    adapter.execute_through_bridge('houdini_set_parm', handler, SynapseCommand(
        id='p1', type='set_parm', payload={'node': '/obj/x', 'parm': 'tx', 'value': 1}))
    assert depths and depths[0] == 0, depths
    assert handler._undo_scope.needs_baseline is False
