"""TT-1 / PUX-05: the worker's verdict on what a tool call actually did.

TT-1. A handler dict with ``cook_error`` or a non-empty ``parms_missed`` came
back without an envelope ``isError``, so both branches of
``ClaudeWorker._execute_tool_block`` emitted a clean 'done'. Now they emit
'warn' naming the misses. ``is_error`` stays False (the node exists and the
model must read the payload), and the tool_result leads with one line naming
the misses.

PUX-05. A response cut off at the token cap after some visible text dropped
its half-written tool call and ended 'completed'; nothing ran in Houdini and
nothing said so. It now says so and ends 'truncated'.
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


def _worker(cw):
    w = cw.ClaudeWorker([{"role": "user", "content": "hi"}], tools=[],
                        enforce_worker_policy=False, provider=None)
    w.tool_status = MagicMock()
    return w


def _block():
    return {"id": "tu_1", "name": TOOL, "input": {"prim_path": "/a", "attr": "x"}}


def _envelope(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def _terminal(worker):
    """(phase, detail) of every non-running emit for TOOL."""
    return [(c.args[1], c.args[2]) for c in worker.tool_status.emit.call_args_list
            if c.args[0] == TOOL and c.args[1] != "running"]


# ---------------------------------------------------------------------------
# MCP branch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload, expected", [
    ({"created_node": "/stage/x", "cook_error": "No prim at /a"}, "No prim at /a"),
    ({"node": "/mat/m", "parms_missed": ["karmamaterial.resx"]},
     "parms missed: karmamaterial.resx"),
    ({"path": "/img/s", "parms_missed": [], "inputs_missed": ["input2"]},
     "inputs missed: input2"),
])
def test_mcp_branch_marks_a_miss_warn(claude_worker_module, monkeypatch, payload, expected):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: _envelope(payload))
    w = _worker(cw)
    result = w._execute_tool_block(_block())
    assert _terminal(w) == [("warn", expected)]
    assert result["is_error"] is False
    _assert_noted(result["content"], payload, expected)


def _assert_noted(content, payload, expected):
    """The tool_result is still ONE JSON object (history readers such as
    recall_card parse it back), led by the key naming the misses."""
    assert isinstance(content, str)
    parsed = json.loads(content)
    keys = list(parsed)
    assert keys[0] == "synapse_reported_misses"
    note = parsed.pop("synapse_reported_misses")
    assert "Name each one to the artist" in note["note"]
    assert expected in note["misses"]
    assert parsed == payload                  # the payload itself is intact


def test_mcp_branch_clean_result_stays_done(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    payload = {"node": "/mat/m", "parms_missed": []}
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: _envelope(payload))
    w = _worker(cw)
    result = w._execute_tool_block(_block())
    assert [p for p, _d in _terminal(w)] == ["done"]
    assert result["is_error"] is False
    assert json.loads(result["content"]) == payload   # no miss note on a clean result


def test_warn_detail_is_capped_at_120(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    payload = {"parms_missed": ["node.parm%03d" % i for i in range(40)]}
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: _envelope(payload))
    w = _worker(cw)
    w._execute_tool_block(_block())
    (phase, detail), = _terminal(w)
    assert phase == "warn" and len(detail) == 120


# ---------------------------------------------------------------------------
# Off-main fallback branch
# ---------------------------------------------------------------------------

def _fallback(cw, monkeypatch, result_value):
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)

    def _dispatch(request):
        request.result = result_value
        request.done.set()

    w = _worker(cw)
    monkeypatch.setattr(w, "_dispatch_off_main", _dispatch)
    return w, w._execute_tool_block(_block())


def test_fallback_branch_marks_a_miss_warn(claude_worker_module, monkeypatch):
    payload = {"created_node": "/stage/x", "cook_error": "No prim at /a"}
    w, result = _fallback(claude_worker_module, monkeypatch, payload)
    assert _terminal(w) == [("warn", "No prim at /a")]
    assert result["is_error"] is False
    _assert_noted(result["content"], payload, "No prim at /a")


def test_noted_recall_result_still_reads_on_the_recall_card(claude_worker_module, monkeypatch):
    """recall_card parses synapse_recall's tool_result text back out of history;
    a miss note must not make an errored recall read UNKNOWN."""
    from synapse.panel.recall_card import latest_recall_result
    cw = claude_worker_module
    payload = {"error": "memory store offline"}
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: _envelope(payload))
    w = _worker(cw)
    result = w._execute_tool_block({"id": "tu_r", "name": "synapse_recall",
                                    "input": {"query": "x"}})
    messages = [{"role": "assistant", "content": [
                    {"type": "tool_use", "id": "tu_r", "name": "synapse_recall", "input": {}}]},
                {"role": "user", "content": [result]}]
    latest = latest_recall_result(messages)
    assert isinstance(latest, dict) and latest.get("error") == "memory store offline"


def test_fallback_branch_clean_result_stays_done(claude_worker_module, monkeypatch):
    payload = {"node": "/stage/x", "parms_missed": []}
    w, result = _fallback(claude_worker_module, monkeypatch, payload)
    assert [p for p, _d in _terminal(w)] == ["done"]
    assert json.loads(result["content"]) == payload


# ---------------------------------------------------------------------------
# PUX-05: a tool call cut off at the token cap after visible text
# ---------------------------------------------------------------------------

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
        return self._script.pop(0)


def _loop_worker(cw, provider):
    w = cw.ClaudeWorker([{"role": "user", "content": "hi"}], tools=[], provider=provider)
    for sig in ("tool_status", "activity_changed", "token_received", "stream_done", "stream_error"):
        setattr(w, sig, MagicMock())
    return w


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "usage" / "turns.jsonl"
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", str(path))
    return path


def _last_row(path):
    return json.loads(path.read_text(encoding="utf-8").splitlines()[-1])


@pytest.mark.parametrize("stop", ["length", "max_tokens"])
def test_tool_call_cut_off_after_text_is_said(claude_worker_module, ledger_path, stop):
    blocks = [{"type": "text", "text": "Building the network now..."},
              {"type": "tool_use", "id": "t1", "name": "synapse_solaris_build_graph",
               "input": {}}]
    w = _loop_worker(claude_worker_module, _Provider([(stop, blocks)]))
    w._conversation_loop("key")
    said = " ".join(str(c.args[0]) for c in w.token_received.emit.call_args_list)
    assert "synapse_solaris_build_graph" in said
    assert "nothing changed in Houdini" in said
    assert _last_row(ledger_path)["outcome"] == "truncated"
    # The unexecuted call is not replayed; the text the artist saw is kept.
    last = w._messages[-1]
    assert last["role"] == "assistant"
    assert all(b.get("type") != "tool_use" for b in last["content"])


def test_text_only_token_cap_stays_completed(claude_worker_module, ledger_path):
    w = _loop_worker(claude_worker_module,
                     _Provider([("max_tokens", [{"type": "text", "text": "Done."}])]))
    w._conversation_loop("key")
    assert not w.token_received.emit.called
    assert _last_row(ledger_path)["outcome"] == "completed"
