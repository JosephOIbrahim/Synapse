"""BP9-WORKER: the per-turn usage ledger (``~/.synapse/usage/turns.jsonl``).

``ClaudeWorker._conversation_loop`` appends exactly ONE JSON row per loop from
its ``finally`` -- so every one of the loop's exits leaves a row: the abort
returns, end_turn, the cap-hit fallthrough, and a raise. The append is fenced
by ``try/except: pass`` so a disk error can never reach the artist as
``stream_error``. It is written on the worker thread (the caller's thread
here) and never via synapse.log.

Headless: reuses the PySide-stubbing fixture from test_worker_tool_policy.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from unittest.mock import MagicMock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_worker_tool_policy import claude_worker_module  # noqa: E402,F401


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
        step = self._script.pop(0)
        if isinstance(step, BaseException):
            raise step
        self.last_usage = {"input_tokens": 10, "output_tokens": 5}
        return step


def _worker(cw, provider, **kw):
    w = cw.ClaudeWorker([{"role": "user", "content": "hi"}], tools=[],
                        provider=provider, **kw)
    for sig in ("tool_status", "activity_changed", "token_received",
                "stream_done", "stream_error"):
        setattr(w, sig, MagicMock())
    return w


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "usage" / "turns.jsonl"
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", str(path))
    return path


def _rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_default_path_is_under_home_synapse_usage(claude_worker_module, monkeypatch):
    monkeypatch.delenv("SYNAPSE_USAGE_LEDGER", raising=False)
    p = claude_worker_module._usage_ledger_path()
    assert p.endswith(os.path.join(".synapse", "usage", "turns.jsonl"))
    assert p.startswith(os.path.expanduser("~"))


def test_end_turn_writes_one_completed_row(claude_worker_module, ledger_path):
    cw = claude_worker_module
    w = _worker(cw, _Provider([("end_turn", [{"type": "text", "text": "hi"}])]))
    w._conversation_loop("key")
    rows = _rows(ledger_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["outcome"] == "completed"
    assert row["stop_reason"] == "end_turn"
    assert row["turns"] == 1
    assert row["tool_calls_total"] == 0
    assert row["tools"] == []
    assert row["provider"] == "fake"
    assert row["model"] == "fake-model-1"
    assert len(row["stream_ms"]) == 1 and row["stream_ms"][0] >= 0
    assert "ts" in row
    # UsageSink task fields ride along (None stays None; never invented).
    assert "usage" in row


def test_tool_calls_are_recorded_with_is_error(claude_worker_module, ledger_path, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call",
                        lambda name, inp: {"ok": True, "echo": inp})
    blocks = [{"type": "tool_use", "id": "t1", "name": "synapse_ping", "input": {}},
              {"type": "tool_use", "id": "t2", "name": "houdini_execute_python",
               "input": {"code": "1"}}]   # denied by policy -> is_error
    w = _worker(cw, _Provider([("tool_use", blocks), ("end_turn", [])]),
                enforce_worker_policy=True)
    w._conversation_loop("key")
    rows = _rows(ledger_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["turns"] == 2
    assert row["tool_calls_total"] == 2
    assert [t["name"] for t in row["tools"]] == ["synapse_ping", "houdini_execute_python"]
    assert [t["is_error"] for t in row["tools"]] == [False, True]
    assert len(row["stream_ms"]) == 2


def test_abort_before_stream_writes_stopped_row(claude_worker_module, ledger_path):
    cw = claude_worker_module
    w = _worker(cw, _Provider([]))
    w._abort = True
    w._conversation_loop("key")
    rows = _rows(ledger_path)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "stopped"
    assert rows[0]["stream_ms"] == []


def test_abort_after_stream_writes_stopped_row(claude_worker_module, ledger_path):
    cw = claude_worker_module
    w = _worker(cw, _Provider([("tool_use", [])]))

    class _P(_Provider):
        def stream(self_, **kw):
            w._abort = True
            return super().stream(**kw)

    w._provider = _P([("tool_use", [])])
    w._conversation_loop("key")
    rows = _rows(ledger_path)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "stopped"
    assert rows[0]["stop_reason"] == "tool_use"
    assert len(rows[0]["stream_ms"]) == 1


def test_cap_hit_writes_cap_hit_row(claude_worker_module, ledger_path):
    cw = claude_worker_module
    n = cw._MAX_TOOL_ITERATIONS
    w = _worker(cw, _Provider([("tool_use", [])] * n))
    w._conversation_loop("key")
    rows = _rows(ledger_path)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "cap_hit"
    assert rows[0]["turns"] == n
    assert len(rows[0]["stream_ms"]) == n


def test_raise_writes_error_row_and_still_raises(claude_worker_module, ledger_path):
    cw = claude_worker_module
    w = _worker(cw, _Provider([RuntimeError("boom")]))
    with pytest.raises(RuntimeError):
        w._conversation_loop("key")
    rows = _rows(ledger_path)
    assert len(rows) == 1
    assert rows[0]["outcome"] == "error"
    assert rows[0]["turns"] == 1
    assert len(rows[0]["stream_ms"]) == 1   # measured even when stream raised


def test_disk_error_never_reaches_the_artist(claude_worker_module, monkeypatch, caplog):
    """The ledger append sits inside try/except inside the finally: a broken
    path must not turn a completed turn into stream_error, and must not log."""
    cw = claude_worker_module
    monkeypatch.setattr(cw, "_usage_ledger_path", lambda: os.devnull + "/x/turns.jsonl")
    w = _worker(cw, _Provider([("end_turn", [])]))
    with caplog.at_level(logging.DEBUG):
        w._conversation_loop("key")       # no raise
    # run() would classify this as completed, never error.
    w._provider = _Provider([("end_turn", [])])
    w._publish_terminal_messages = MagicMock()
    w.run()
    assert w.stream_done.emit.called
    assert not w.stream_error.emit.called
    assert not any("turns.jsonl" in r.getMessage() for r in caplog.records)


def test_ledger_never_goes_through_synapse_log(claude_worker_module, ledger_path, caplog):
    cw = claude_worker_module
    w = _worker(cw, _Provider([("end_turn", [])]))
    with caplog.at_level(logging.DEBUG):
        w._conversation_loop("key")
    assert len(_rows(ledger_path)) == 1
    assert not any("turns.jsonl" in r.getMessage() or "ledger" in r.getMessage().lower()
                   for r in caplog.records)


def test_append_is_in_a_try_except_inside_the_finally():
    """Structural pin: the write to turns.jsonl is fenced try/except inside finally."""
    import ast
    src_path = os.path.join(_ROOT, "python", "synapse", "panel", "claude_worker.py")
    tree = ast.parse(open(src_path, encoding="utf-8").read())
    loop = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_conversation_loop")
    outer = next(n for n in loop.body if isinstance(n, ast.Try) and n.finalbody)
    inner = [n for n in outer.finalbody if isinstance(n, ast.Try) and n.handlers]
    assert inner, "finally must contain a try/except"
    assert any(isinstance(h.body[0], ast.Pass) for t in inner for h in t.handlers)
    assert "_usage_ledger_path" in ast.dump(inner[0])
