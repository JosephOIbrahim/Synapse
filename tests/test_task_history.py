"""Terminal transcript correctness using actual worker/panel method bodies.

The only replaced worker substrate is QThread/Signal; no thread, model, bridge
or Houdini executes here. A separate native Qt probe checks queued delivery.
Each next-request assertion passes through the real Ollama message converter.
"""
import ast
import copy
import logging
from pathlib import Path
import threading
from types import SimpleNamespace, MethodType
from unittest.mock import Mock

import pytest

from test_first_session_panel import fixture_panel, panel_methods
from synapse.panel.providers.nemotron_provider import _to_openai_messages


class Signal:
    def __init__(self, *args):
        self.name = None

    def __set_name__(self, owner, name):
        self.name = '_signal_' + name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.name not in instance.__dict__:
            slots = []
            instance.__dict__[self.name] = SimpleNamespace(
                connect=slots.append, emit=lambda *args: [slot(*args) for slot in list(slots)])
        return instance.__dict__[self.name]


class Thread:
    def __init__(self, parent=None):
        pass

    def isRunning(self):
        return False


@pytest.fixture
def worker_class():
    source = Path(__file__).parents[1] / 'python/synapse/panel/claude_worker.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    # Keep the entire production class, including run/finalization/abort. Only
    # the Qt base and signal descriptors are substituted in this pure check.
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ClaudeWorker')
    ns = dict(QThread=Thread, Signal=Signal, copy=copy, threading=threading,
              logger=Mock(spec=logging.Logger), USAGE_SINK=None, _MAX_TOOL_ITERATIONS=3)
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, cls], type_ignores=[]))
    exec(compile(module, str(source), 'exec'), ns)
    return ns['ClaudeWorker']


def provider(script):
    requests = []
    def stream(**kwargs):
        requests.append(_to_openai_messages(copy.deepcopy(kwargs['messages']), '', directive=None))
        return script(kwargs)
    return SimpleNamespace(stream=stream, resolve_key=lambda: 'fake-no-network-key',
                           key_error_message=lambda: 'Key unavailable', _model_scope=SimpleNamespace(active=True),
                           requests=requests)


def call(identifier):
    return {'type': 'tool_use', 'id': identifier, 'name': 'fixture_tool', 'input': {'id': identifier}}


def result(identifier, text):
    return {'type': 'tool_result', 'tool_use_id': identifier, 'content': text}


def results(messages):
    return [block for message in messages if isinstance(message.get('content'), list)
            for block in message['content'] if block.get('type') == 'tool_result']


def markers(messages):
    return [m for m in messages if isinstance(m.get('content'), str)
            and m['content'].startswith('[SYNAPSE task status]')]


def panel_for(worker, monkeypatch):
    from synapse.server import session_store
    saved = []
    monkeypatch.setattr(session_store, 'save_conversation', lambda msgs: saved.append(copy.deepcopy(msgs)))
    panel, connection, _ = fixture_panel()
    panel._messages = [{'role': 'user', 'content': 'Build the previous fixture.'}]
    panel._worker = worker
    panel._task_connection = connection
    panel._stream_buf = []
    panel._streaming_started = False
    panel._set_thinking = Mock()
    panel._set_busy = Mock()
    panel._turn_evidence = lambda: ([], [], [])
    panel._author_token = lambda: 'fixture/model'
    for name, fn in panel_methods('_on_done', '_on_error', '_on_worker_finished').items():
        setattr(panel, name, MethodType(fn, panel))
    return panel, connection, saved


def run_to_panel(worker, panel, connection):
    worker.stream_done.connect(panel._on_done)
    worker.stream_error.connect(panel._on_error)
    worker.run()
    if panel._worker is worker:
        panel._on_worker_finished(worker, connection)


def send_next(panel, worker_class):
    fresh = provider(lambda _: ('end_turn', [{'type': 'text', 'text': 'Recovery observed.'}]))
    panel._pending_context = []
    panel._allow_connection.return_value = True
    panel._prepare_connection.return_value.provider = fresh
    def start():
        worker = worker_class(panel._messages, tools=[], provider=fresh)
        panel._worker = worker
        run_to_panel(worker, panel, panel._task_connection)
    panel._start_worker = start
    prompt = 'Recovery only: inspect once. Do not create or change anything.'
    assert panel._send(prompt) is True
    assert len(fresh.requests) == 1
    payload = fresh.requests[0]
    assert payload[-1] == {'role': 'user', 'content': prompt}
    assert sum(m.get('content') == prompt for m in payload) == 1
    return payload


def test_only_tool_stop_retains_actual_result_and_boundary_in_next_request(worker_class, monkeypatch):
    first = provider(lambda _: ('tool_use', [call('a')]))
    worker = worker_class([{'role': 'user', 'content': 'Build the previous fixture.'}], tools=[], provider=first)
    def execute(_):
        worker.abort()
        return result('a', 'Created /stage/owned_fixture')
    worker._execute_tool_block = execute
    panel, connection, saved = panel_for(worker, monkeypatch)
    run_to_panel(worker, panel, connection)
    payload = send_next(panel, worker_class)
    assert len(first.requests) == 1
    assert [m for m in payload if m['role'] == 'tool'] == [
        {'role': 'tool', 'tool_call_id': 'a', 'content': 'Created /stage/owned_fixture'}]
    boundary = markers(payload)
    assert len(boundary) == 1, 'The next request must record that the artist stopped the old task'
    assert 'stopped' in boundary[0]['content'].lower()
    assert payload.index(boundary[0]) > next(i for i,m in enumerate(payload) if m['role'] == 'tool')
    assert markers(saved[0]) == boundary


@pytest.mark.parametrize('error_kind', ['provider', 'permission'])
def test_later_error_preserves_tool_facts_in_panel_disk_and_next_request(worker_class, monkeypatch, error_kind):
    from synapse.model_access import ModelAccessDenied
    count = 0
    def response(_):
        nonlocal count
        count += 1
        if count == 1:
            return 'tool_use', [call('a')]
        raise (ModelAccessDenied('Project permission changed') if error_kind == 'permission' else RuntimeError('Provider failed'))
    first = provider(response)
    worker = worker_class([{'role': 'user', 'content': 'Build the previous fixture.'}], tools=[], provider=first)
    worker._execute_tool_block = lambda _: result('a', 'The real operation already finished')
    panel, connection, saved = panel_for(worker, monkeypatch)
    run_to_panel(worker, panel, connection)
    payload = send_next(panel, worker_class)
    assert [m.get('content') for m in payload if m['role'] == 'tool'] == ['The real operation already finished'], 'Completed tool facts were discarded on error'
    assert results(saved[0]) == [result('a', 'The real operation already finished')]
    assert len(markers(payload)) == 1 and 'error' in markers(payload)[0]['content'].lower()
    assert len(first.requests) == 2


def test_executor_exception_preserves_pairs_and_distinguishes_unknown_from_not_executed(worker_class, monkeypatch):
    first = provider(lambda _: ('tool_use', [call('a'), call('b'), call('c')]))
    worker = worker_class([{'role': 'user', 'content': 'Build the previous fixture.'}], tools=[], provider=first)
    executed = []
    def execute(block):
        executed.append(block['id'])
        if block['id'] == 'b':
            raise RuntimeError('dispatch failed after possibly starting')
        return result('a', 'First operation finished')
    worker._execute_tool_block = execute
    panel, connection, saved = panel_for(worker, monkeypatch)
    run_to_panel(worker, panel, connection)
    retained = results(worker.get_messages())
    assert [r['tool_use_id'] for r in retained] == ['a', 'b', 'c'], 'An interrupted batch lost results or left unpaired calls'
    assert retained[0] == result('a', 'First operation finished')
    assert retained[1]['is_error'] and 'unknown' in retained[1]['content'].lower()
    assert retained[2]['is_error'] and 'not executed' in retained[2]['content'].lower()
    assert executed == ['a', 'b']
    payload = send_next(panel, worker_class)
    assert [m['tool_call_id'] for m in payload if m['role'] == 'tool'] == ['a', 'b', 'c']
    assert len(first.requests) == 1


@pytest.mark.parametrize('phase', ['before_response', 'during_next_response', 'before_sibling', 'permission_race'])
def test_stop_boundaries_do_not_replay_partial_or_unexecuted_calls(worker_class, phase):
    attempts = 0
    worker = None
    def response(_):
        nonlocal attempts
        attempts += 1
        if phase == 'permission_race':
            from synapse.model_access import ModelAccessDenied
            worker.abort()
            raise ModelAccessDenied('Task stopped before sending')
        if attempts == 1:
            return 'tool_use', [call('a')] + ([call('b')] if phase == 'before_sibling' else [])
        worker.abort()
        return 'tool_use', [call('incomplete')]
    first = provider(response)
    worker = worker_class([{'role': 'user', 'content': 'Prior task'}], tools=[], provider=first)
    executed = []
    def execute(block):
        executed.append(block['id'])
        if phase == 'before_sibling':
            worker.abort()
        return result(block['id'], 'Actual result')
    worker._execute_tool_block = execute
    if phase == 'before_response':
        worker.abort()
    worker.run()
    history = worker.get_messages()
    assert len(markers(history)) == 1 and 'stopped' in markers(history)[0]['content'].lower()
    assert 'incomplete' not in str(history)
    if phase == 'before_sibling':
        assert executed == ['a'] and results(history)[1]['is_error']
    elif phase in ('before_response', 'permission_race'):
        assert executed == []
    else:
        assert executed == ['a'] and results(history) == [result('a', 'Actual result')]


@pytest.mark.parametrize('outcome', ['complete', 'error', 'stop'])
def test_terminal_snapshot_is_published_before_signals_and_copies_are_isolated(worker_class, outcome):
    worker = None
    before = []
    def response(_):
        before.append(getattr(worker, 'get_terminal_messages', lambda: None)())
        if outcome == 'error':
            raise RuntimeError('Stream failed')
        if outcome == 'stop':
            worker.abort()
        return 'end_turn', [{'type': 'text', 'text': 'Actual answer'}]
    worker = worker_class([{'role': 'user', 'content': 'Prior task'}], tools=[], provider=provider(response))
    observed = []
    worker.stream_done.connect(lambda: observed.append(getattr(worker, 'get_terminal_messages', lambda: None)()))
    worker.stream_error.connect(lambda _: observed.append(getattr(worker, 'get_terminal_messages', lambda: None)()))
    worker.run()
    snapshot = getattr(worker, 'get_terminal_messages', lambda: None)()
    assert before == [None]
    assert snapshot is not None, 'Terminal worker history must be published independently of mutable loop history'
    assert observed == ([] if outcome == 'stop' else [snapshot])
    pristine = copy.deepcopy(snapshot)
    snapshot.append({'role': 'user', 'content': 'Caller mutation'})
    worker._messages.append({'role': 'user', 'content': 'Late live-list mutation'})
    assert worker.get_terminal_messages() == pristine


def test_normal_answer_followup_has_no_status_marker(worker_class, monkeypatch):
    first = provider(lambda _: ('end_turn', [{'type': 'text', 'text': 'Completed answer'}]))
    worker = worker_class([{'role': 'user', 'content': 'Build the previous fixture.'}], tools=[], provider=first)
    panel, connection, _ = panel_for(worker, monkeypatch)
    run_to_panel(worker, panel, connection)
    payload = send_next(panel, worker_class)
    assert sum(m.get('content') == 'Completed answer' for m in payload) == 1
    assert not markers(payload)


def test_error_handler_never_reads_unpublished_mutable_history(worker_class, monkeypatch):
    worker = worker_class([{'role': 'user', 'content': 'Prior task'}], tools=[], provider=provider(lambda _: None))
    worker.get_messages = Mock(side_effect=AssertionError('Read live mutable history'))
    panel, _, saved = panel_for(worker, monkeypatch)
    previous = copy.deepcopy(panel._messages)
    panel._on_error('Startup failed')
    assert panel._messages == previous and saved == []
    worker.get_messages.assert_not_called()


def test_failed_start_keeps_draft_context_and_removes_only_failed_prompt(monkeypatch):
    panel, _, methods = fixture_panel()
    panel._allow_connection.return_value = True
    panel._set_busy = Mock()
    panel._set_thinking = Mock()
    panel._on_error = MethodType(panel_methods('_on_error')['_on_error'], panel)
    panel._start_worker.side_effect = RuntimeError('Thread start failed')
    before = copy.deepcopy(panel._messages)
    methods['_on_submit'](panel)
    assert panel._messages == before
    assert panel._pending_context == ['/stage/light']
    panel._input.clear.assert_not_called()


@pytest.mark.parametrize('signal', ['_on_error', '_on_done'])
def test_old_worker_terminal_signal_cannot_finish_a_new_task(worker_class, monkeypatch, signal):
    old = worker_class([{'role': 'user', 'content': 'Old task'}], tools=[], provider=provider(lambda _: None))
    current = worker_class([{'role': 'user', 'content': 'New task'}], tools=[], provider=provider(lambda _: None))
    panel, connection, saved = panel_for(current, monkeypatch)
    panel.sender = lambda: old
    before = copy.deepcopy(panel._messages)
    getattr(panel, signal)(*(['Late error'] if signal == '_on_error' else []))
    assert panel._worker is current and panel._task_connection is connection
    assert panel._messages == before and not saved
    connection.revoke.assert_not_called()
    panel._set_busy.assert_not_called()


def test_late_finished_helper_cannot_complete_another_worker(worker_class, monkeypatch):
    old = worker_class([], tools=[], provider=provider(lambda _: None))
    current = worker_class([], tools=[], provider=provider(lambda _: None))
    panel, connection, saved = panel_for(current, monkeypatch)
    old.abort()
    panel._on_worker_finished(old, connection)
    assert panel._worker is current and panel._task_connection is connection and not saved
    connection.revoke.assert_not_called()
