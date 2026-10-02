"""The round cap ends a turn in words, never mid-thought (10/2).

Before: after ``_MAX_TOOL_ITERATIONS`` rounds the worker loop simply stopped,
so the artist's reply ended on the model's narration of a tool call that never
ran ("Let me check the collider..."). bench3 saw it twice on 10/1.

Now the last round carries a wrap-up directive in the system prompt, a tool
call requested on that round is never executed, and when one comes anyway the
turn closes with a line that says so. The history always ends on an assistant
message with no unpaired tool call, so the next request is well formed.

Two harnesses, both headless: the AST exec of ``_conversation_loop`` used by
test_first_session_panel (no Qt), and the PySide-stubbed worker used by
test_turn_usage_ledger for the ledger row.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_worker_tool_policy import claude_worker_module  # noqa: E402,F401

_SOURCE = Path(__file__).parents[1] / "python/synapse/panel/claude_worker.py"
_CAP = 3


def _loop():
    tree = ast.parse(_SOURCE.read_text(encoding="utf-8"))
    method = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_conversation_loop")
    ns = {"USAGE_SINK": None, "_MAX_TOOL_ITERATIONS": _CAP, "logger": Mock()}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(_SOURCE), "exec"), ns)
    return ns["_conversation_loop"]


def _call(i):
    return {"type": "tool_use", "id": "call-%d" % i, "name": "houdini_stage_info", "input": {}}


class _Script:
    """A fake provider: one step per round. A step is (stop_reason, blocks, narration)."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.systems = []
        self.requests = []

    def stream(self, **kw):
        self.systems.append(kw["system"])
        self.requests.append([dict(m) for m in kw["messages"]])
        stop_reason, blocks, narration = self.steps.pop(0)
        if narration:
            kw["emit_token"](narration)
        return stop_reason, blocks


def _worker(script, system="BASE"):
    executed = []

    def execute(block):
        executed.append(block["id"])
        return {"type": "tool_result", "tool_use_id": block["id"], "content": "ok"}

    worker = SimpleNamespace(_abort=False, _messages=[{"role": "user", "content": "build it"}],
                             _tools=[], _system=system, activity_changed=Mock(),
                             token_received=Mock(), _execute_tool_block=execute,
                             _provider=script)
    return worker, executed


def _emitted(worker):
    return "".join(c.args[0] for c in worker.token_received.emit.call_args_list)


def test_only_the_last_round_carries_the_wrap_up_directive():
    script = _Script([("tool_use", [_call(0)], None),
                      ("tool_use", [_call(1)], None),
                      ("end_turn", [{"type": "text", "text": "Built the key. The rim is not verified."}], None)])
    worker, executed = _worker(script)
    _loop()(worker, "key")
    assert script.systems[0] == script.systems[1] == "BASE"
    assert script.systems[2].startswith("BASE\n\n")
    assert "Do not call a tool" in script.systems[2]
    assert executed == ["call-0", "call-1"]
    assert worker._messages[-1] == {"role": "assistant", "content": [
        {"type": "text", "text": "Built the key. The rim is not verified."}]}
    # The directive lives in the request's system field only, never in the history.
    assert "Do not call a tool" not in json.dumps(worker._messages)


def test_a_tool_call_on_the_last_round_is_not_run_and_the_turn_closes_in_words():
    narration = "Let me check the collider's visibility."
    last = [{"type": "text", "text": narration}, _call(2)]
    script = _Script([("tool_use", [_call(0)], None),
                      ("tool_use", [_call(1)], None),
                      ("tool_use", last, narration)])
    worker, executed = _worker(script)
    _loop()(worker, "key")
    assert executed == ["call-0", "call-1"]
    final = worker._messages[-1]
    assert final["role"] == "assistant"
    assert [b["type"] for b in final["content"]] == ["text", "text"]
    assert final["content"][0]["text"] == narration
    closing = final["content"][1]["text"]
    assert "used all %d of its tool rounds, so that last step did not run" % _CAP in closing
    assert "Nothing changed after the last tool result" in closing
    # On the panel the closing line is its own paragraph after the narration.
    assert _emitted(worker).endswith(narration + "\n\n" + closing)


def test_a_silent_last_round_closes_with_before_i_could_answer():
    script = _Script([("tool_use", [_call(0)], None),
                      ("tool_use", [_call(1)], None),
                      ("tool_use", [_call(2)], None)])
    worker, executed = _worker(script)
    _loop()(worker, "key")
    assert executed == ["call-0", "call-1"]
    final = worker._messages[-1]
    assert [b["type"] for b in final["content"]] == ["text"]
    assert "before I could answer" in final["content"][0]["text"]


def test_after_a_closed_cap_the_next_request_has_no_unpaired_tool_call():
    script = _Script([("tool_use", [_call(0)], None),
                      ("tool_use", [_call(1)], None),
                      ("tool_use", [_call(2)], None),
                      ("end_turn", [{"type": "text", "text": "Continuing."}], None)])
    worker, _ = _worker(script)
    loop = _loop()
    loop(worker, "key")
    worker._messages.append({"role": "user", "content": "continue"})
    loop(worker, "key")
    sent = script.requests[-1]
    assert [m["role"] for m in sent][-2:] == ["assistant", "user"]
    calls = {b["id"] for m in sent if m["role"] == "assistant" and isinstance(m["content"], list)
             for b in m["content"] if b.get("type") == "tool_use"}
    results = {b["tool_use_id"] for m in sent if m["role"] == "user" and isinstance(m["content"], list)
               for b in m["content"] if b.get("type") == "tool_result"}
    assert calls == results == {"call-0", "call-1"}


def test_an_answer_before_the_last_round_is_untouched():
    script = _Script([("tool_use", [_call(0)], None),
                      ("end_turn", [{"type": "text", "text": "Done."}], None)])
    worker, _ = _worker(script)
    _loop()(worker, "key")
    assert script.systems == ["BASE", "BASE"]
    assert worker._messages[-1]["content"] == [{"type": "text", "text": "Done."}]


# --------------------------------------------------------------------------- #
#  The ledger row (PySide-stubbed worker)                                      #
# --------------------------------------------------------------------------- #
class _Provider:
    id = "fake"
    model_identity = "fake-model-1"

    def __init__(self, script):
        self._script = list(script)
        self.last_usage = None

    def resolve_key(self):
        return "key"

    def key_error_message(self):
        return "no key"

    def stream(self, **_kw):
        self.last_usage = {"input_tokens": 10, "output_tokens": 5}
        return self._script.pop(0)


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "usage" / "turns.jsonl"
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", str(path))
    return path


def _row(cw, steps, ledger_path):
    w = cw.ClaudeWorker([{"role": "user", "content": "hi"}], tools=[],
                        provider=_Provider(steps))
    for sig in ("tool_status", "activity_changed", "token_received",
                "stream_done", "stream_error"):
        setattr(w, sig, MagicMock())
    w._conversation_loop("key")
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 1
    return rows[0]


def test_ledger_records_a_closed_cap(claude_worker_module, ledger_path):
    cw = claude_worker_module
    n = cw._MAX_TOOL_ITERATIONS
    row = _row(cw, [("tool_use", [])] * n, ledger_path)
    assert row["outcome"] == "cap_hit"
    assert row["wrap_up"] == "closed"
    assert row["turns"] == n


def test_ledger_records_an_answered_cap(claude_worker_module, ledger_path):
    cw = claude_worker_module
    n = cw._MAX_TOOL_ITERATIONS
    steps = [("tool_use", [])] * (n - 1) + [("end_turn", [{"type": "text", "text": "Done."}])]
    row = _row(cw, steps, ledger_path)
    assert row["outcome"] == "cap_hit"
    assert row["wrap_up"] == "answered"


def test_ledger_leaves_wrap_up_empty_on_an_ordinary_turn(claude_worker_module, ledger_path):
    cw = claude_worker_module
    row = _row(cw, [("end_turn", [{"type": "text", "text": "Hi."}])], ledger_path)
    assert row["outcome"] == "completed"
    assert row["wrap_up"] is None
