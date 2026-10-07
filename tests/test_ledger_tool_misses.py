"""TT-8: the usage ledger counts the misses a successful tool call reported.

TT-1 made a miss-carrying result (``cook_error``, ``parms_missed``, ...) reach
the panel as 'warn' while its tool_result stays ``is_error`` False, because the
work it did exists and the model must still read the payload. The on-disk
usage ledger (``turns.jsonl``) recorded only ``is_error``, so every warn result
looked identical to a clean one there.

Every ``row["tools"]`` entry now carries ``misses``:

* an ``int`` -- ``len(result_misses(payload))`` for a result the worker read
  (0 means clean);
* ``None`` -- never measured: an error result, a call cancelled by the artist,
  or a dispatch that raised. None is UNKNOWN, never 0.

``is_error`` semantics are unchanged: a warn result stays ``is_error`` False.

Headless: reuses the PySide-stubbing fixture from test_worker_tool_policy.
"""
from __future__ import annotations

import json
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

TOOL = "houdini_set_usd_attribute"


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


def _envelope(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def _use(tid, name=TOOL, inp=None):
    return {"type": "tool_use", "id": tid, "name": name,
            "input": inp if inp is not None else {"prim_path": "/a", "attr": tid}}


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "usage" / "turns.jsonl"
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", str(path))
    return path


def _row(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 1
    return rows[0]


# ---------------------------------------------------------------------------
# MCP branch, end to end through the conversation loop
# ---------------------------------------------------------------------------

def test_mcp_warn_results_carry_their_miss_count(claude_worker_module, ledger_path, monkeypatch):
    cw = claude_worker_module
    payloads = {
        "one": {"created_node": "/stage/x", "cook_error": "No prim at /a"},
        "two": {"node": "/mat/m", "parms_missed": ["a.x"], "inputs_missed": ["input2"]},
        "clean": {"created_node": "/stage/y"},
    }
    monkeypatch.setattr(cw, "try_mcp_tool_call",
                        lambda name, inp: _envelope(payloads[inp["attr"]]))
    blocks = [_use("one"), _use("two"), _use("clean")]
    w = _worker(cw, _Provider([("tool_use", blocks), ("end_turn", [])]),
                enforce_worker_policy=False)
    w._conversation_loop("key")
    tools = _row(ledger_path)["tools"]
    assert [t["misses"] for t in tools] == [1, 2, 0]
    # is_error semantics are unchanged: a warn result is not an error.
    assert [t["is_error"] for t in tools] == [False, False, False]


def test_error_results_have_no_measured_misses(claude_worker_module, ledger_path, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call",
                        lambda name, inp: _envelope({"cook_error": "boom"}))
    # Denied by the worker policy -> is_error True, the payload is never read.
    blocks = [_use("t1"), _use("t2", name="houdini_execute_python", inp={"code": "1"})]
    w = _worker(cw, _Provider([("tool_use", blocks), ("end_turn", [])]),
                enforce_worker_policy=True)
    w._conversation_loop("key")
    tools = _row(ledger_path)["tools"]
    assert [t["is_error"] for t in tools] == [False, True]
    assert tools[0]["misses"] == 1
    assert tools[1]["misses"] is None


def test_mcp_envelope_error_has_no_measured_misses(claude_worker_module, ledger_path, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: {
        "isError": True,
        "content": [{"type": "text", "text": json.dumps({"cook_error": "x"})}]})
    w = _worker(cw, _Provider([("tool_use", [_use("t1")]), ("end_turn", [])]),
                enforce_worker_policy=False)
    w._conversation_loop("key")
    (entry,) = _row(ledger_path)["tools"]
    assert entry["is_error"] is True
    assert entry["misses"] is None


def test_cancelled_call_has_no_measured_misses(claude_worker_module, ledger_path, monkeypatch):
    cw = claude_worker_module
    calls = []

    def _mcp(name, inp):
        calls.append(inp["attr"])
        w._abort = True   # the artist stops after the first call lands
        return _envelope({"cook_error": "x"})

    monkeypatch.setattr(cw, "try_mcp_tool_call", _mcp)
    w = _worker(cw, _Provider([("tool_use", [_use("t1"), _use("t2")])]),
                enforce_worker_policy=False)
    w._conversation_loop("key")
    tools = _row(ledger_path)["tools"]
    assert calls == ["t1"]
    assert [t["misses"] for t in tools] == [1, None]
    assert [t["is_error"] for t in tools] == [False, True]


def test_raised_dispatch_has_no_measured_misses(claude_worker_module, ledger_path, monkeypatch):
    cw = claude_worker_module
    w = _worker(cw, _Provider([("tool_use", [_use("t1")])]), enforce_worker_policy=False)
    # A stale count from an earlier call must not leak onto a raised entry.
    w._last_tool_misses = 7

    def _boom(block):
        raise RuntimeError("dispatch died")

    monkeypatch.setattr(w, "_execute_tool_block", _boom)
    with pytest.raises(RuntimeError):
        w._conversation_loop("key")
    (entry,) = _row(ledger_path)["tools"]
    assert entry["is_error"] is True
    assert entry["misses"] is None


def test_stubbed_dispatch_does_not_inherit_a_stale_count(claude_worker_module, ledger_path,
                                                        monkeypatch):
    cw = claude_worker_module
    w = _worker(cw, _Provider([("tool_use", [_use("t1")]), ("end_turn", [])]),
                enforce_worker_policy=False)
    w._last_tool_misses = 3

    def _ok(block):
        return {"type": "tool_result", "tool_use_id": block["id"],
                "content": "OK", "is_error": False}

    monkeypatch.setattr(w, "_execute_tool_block", _ok)
    w._conversation_loop("key")
    (entry,) = _row(ledger_path)["tools"]
    assert entry["is_error"] is False
    assert entry["misses"] is None   # this dispatch measured nothing


# ---------------------------------------------------------------------------
# Off-main fallback branch: the same count, recorded on the worker
# ---------------------------------------------------------------------------

def _fallback(cw, monkeypatch, result_value):
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)

    def _dispatch(request):
        request.result = result_value
        request.done.set()

    w = _worker(cw, provider=None, enforce_worker_policy=False)
    monkeypatch.setattr(w, "_dispatch_off_main", _dispatch)
    result = w._execute_tool_block({"id": "tu_1", "name": TOOL,
                                    "input": {"prim_path": "/a", "attr": "x"}})
    return w, result


def test_fallback_branch_records_the_miss_count(claude_worker_module, monkeypatch):
    w, result = _fallback(claude_worker_module, monkeypatch,
                          {"node": "/mat/m", "parms_missed": ["a.x"], "cook_error": "e"})
    assert result["is_error"] is False
    assert w._last_tool_misses == 2


def test_fallback_branch_clean_result_records_zero(claude_worker_module, monkeypatch):
    w, result = _fallback(claude_worker_module, monkeypatch, {"node": "/mat/m"})
    assert result["is_error"] is False
    assert w._last_tool_misses == 0


def test_tool_result_sent_to_the_model_gains_no_key(claude_worker_module, monkeypatch):
    """The count rides a side channel; the tool_result block is unchanged."""
    w, result = _fallback(claude_worker_module, monkeypatch, {"cook_error": "e"})
    assert set(result) == {"type", "tool_use_id", "content", "is_error"}
