"""A2: a turn is bounded by time and input tokens, not only by rounds.

The round cap was the only ceiling on a turn. On 2026-10-04 one turn ran 15
minutes and read 5.77 million input tokens before round 25 stopped it. A turn
now also ends on a wall-clock budget (SYNAPSE_TURN_BUDGET_S, default 600) and
an input-token budget (SYNAPSE_TURN_BUDGET_TOKENS, default 3,000,000), the same
way the round cap ends it: one last model round with the wrap-up directive, no
tool run, a closing line in words, and ``cap`` in the ledger row.

Headless: the AST exec of ``_conversation_loop`` used by test_worker_round_cap.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

_SOURCE = Path(__file__).parents[1] / "python/synapse/panel/claude_worker.py"
_CAP = 25


class _Clock:
    def __init__(self):
        self.now = 0.0

    def perf_counter(self):
        return self.now

    def time(self):
        return self.now


class _Sink:
    def __init__(self):
        self.input_tokens = 0

    def begin_task(self, *a, **kw):
        self.input_tokens = 0

    def add(self, usage):
        if usage:
            self.input_tokens += usage.get("input_tokens", 0)

    def set_reported_model(self, model):
        pass

    def set_context_window(self, *a):
        pass

    def snapshot(self):
        return {"input_tokens": self.input_tokens}


def _loop(clock=None, sink=None, with_os=True):
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    method = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_conversation_loop")
    ns = {"USAGE_SINK": sink, "_MAX_TOOL_ITERATIONS": _CAP, "logger": Mock()}
    if clock is not None:
        ns["time"] = clock
    if with_os:
        ns["os"] = os
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(_SOURCE), "exec"), ns)
    return ns["_conversation_loop"]


def _call(i):
    return {"type": "tool_use", "id": "call-%d" % i, "name": "houdini_set_parm", "input": {}}


class _Script:
    """One step per round: (stop_reason, blocks, seconds this round takes, input tokens)."""

    def __init__(self, steps, clock=None):
        self.steps = list(steps)
        self.clock = clock
        self.systems = []
        self.last_usage = None

    def stream(self, **kw):
        self.systems.append(kw["system"])
        stop_reason, blocks, seconds, tokens = self.steps.pop(0)
        if self.clock is not None:
            self.clock.now += seconds
        self.last_usage = {"input_tokens": tokens}
        return stop_reason, blocks


def _worker(script):
    executed = []

    def execute(block):
        executed.append(block["id"])
        return {"type": "tool_result", "tool_use_id": block["id"], "content": "ok"}

    worker = SimpleNamespace(_abort=False, _messages=[{"role": "user", "content": "build it"}],
                             _tools=[], _system="BASE", activity_changed=Mock(),
                             token_received=Mock(), _execute_tool_block=execute,
                             _provider=script)
    return worker, executed


@pytest.fixture(autouse=True)
def _no_budget_env(monkeypatch):
    monkeypatch.delenv("SYNAPSE_TURN_BUDGET_S", raising=False)
    monkeypatch.delenv("SYNAPSE_TURN_BUDGET_TOKENS", raising=False)
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", os.devnull)


def test_the_time_budget_ends_the_turn_in_words_and_runs_no_more_tools():
    clock = _Clock()
    # 4 rounds of 200 s: the budget (600 s) is spent when round 4 begins.
    script = _Script([("tool_use", [_call(i)], 200.0, 10) for i in range(4)], clock)
    worker, executed = _worker(script)
    _loop(clock)(worker, "key")
    assert executed == ["call-0", "call-1", "call-2"]
    assert script.systems[:3] == ["BASE"] * 3
    assert "Do not call a tool" in script.systems[3]
    closing = worker._messages[-1]["content"][-1]["text"]
    assert "reached its time budget of 600 seconds before I could answer" in closing
    assert "Nothing changed after the last tool result" in closing
    assert not script.steps  # no fifth round was asked for


def test_the_token_budget_ends_the_turn():
    sink = _Sink()
    script = _Script([("tool_use", [_call(i)], 1.0, 1_200_000) for i in range(4)])
    worker, executed = _worker(script)
    _loop(sink=sink)(worker, "key")
    # 3.6M after three rounds: the fourth round is the last, and its call is not run.
    assert executed == ["call-0", "call-1", "call-2"]
    closing = worker._messages[-1]["content"][-1]["text"]
    assert "reached its budget of 3,000,000 input tokens" in closing


def test_a_model_that_answers_on_the_budget_round_is_not_cut_off():
    clock = _Clock()
    script = _Script([("tool_use", [_call(0)], 700.0, 10),
                      ("end_turn", [{"type": "text", "text": "Built the key."}], 5.0, 10)], clock)
    worker, executed = _worker(script)
    _loop(clock)(worker, "key")
    assert executed == ["call-0"]
    assert worker._messages[-1] == {"role": "assistant",
                                    "content": [{"type": "text", "text": "Built the key."}]}


def test_an_ordinary_turn_never_sees_the_directive():
    clock = _Clock()
    script = _Script([("tool_use", [_call(0)], 20.0, 150_000),
                      ("end_turn", [{"type": "text", "text": "Done."}], 5.0, 150_000)], clock)
    worker, executed = _worker(script)
    _loop(clock, _Sink())(worker, "key")
    assert script.systems == ["BASE", "BASE"]
    assert executed == ["call-0"]


def test_unknown_usage_is_not_read_as_zero_or_as_over_budget():
    sink = _Sink()
    sink.snapshot = lambda: {"input_tokens": None}
    script = _Script([("tool_use", [_call(0)], 1.0, 0),
                      ("end_turn", [{"type": "text", "text": "Done."}], 1.0, 0)])
    worker, executed = _worker(script)
    _loop(sink=sink)(worker, "key")
    assert script.systems == ["BASE", "BASE"]


def test_the_budgets_can_be_changed_and_switched_off(monkeypatch):
    clock = _Clock()
    monkeypatch.setenv("SYNAPSE_TURN_BUDGET_S", "30")
    script = _Script([("tool_use", [_call(0)], 40.0, 10), ("tool_use", [_call(1)], 1.0, 10)], clock)
    worker, executed = _worker(script)
    _loop(clock)(worker, "key")
    assert executed == ["call-0"]
    assert "time budget of 30 seconds" in worker._messages[-1]["content"][-1]["text"]

    clock = _Clock()
    monkeypatch.setenv("SYNAPSE_TURN_BUDGET_S", "0")
    script = _Script([("tool_use", [_call(0)], 5000.0, 10),
                      ("end_turn", [{"type": "text", "text": "Done."}], 1.0, 10)], clock)
    worker, executed = _worker(script)
    _loop(clock)(worker, "key")
    assert script.systems == ["BASE", "BASE"]


def test_the_round_cap_still_says_rounds():
    script = _Script([("tool_use", [_call(i)], 1.0, 10) for i in range(_CAP)])
    worker, executed = _worker(script)
    _loop()(worker, "key")
    assert len(executed) == _CAP - 1
    assert ("used all %d of its tool rounds" % _CAP) in worker._messages[-1]["content"][-1]["text"]
