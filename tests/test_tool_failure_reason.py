"""BP9-WORKER: a tool failure reaches the artist as a REASON, not an input echo.

Before: the four error branches of ``ClaudeWorker._execute_tool_block``
emitted ``tool_status(tool, "error", json.dumps(tool_input)[:120])`` -- the
request the model made, truncated, with no word about why it failed. Now they
emit ``translate_tool_error(tool, err_text)[:120]``; ``activity.tool_status``
renders it as ``Failed: <label> - <detail>``; the face tooltip carries the full
detail on the error phase. The two policy branches (allowlist denial, retry
breaker) already carried a reason and are unchanged.

Pins:
  * error detail never equals ``json.dumps(tool_input)[:120]``
  * running-phase detail is unchanged (test_h3b_panel_cancel depends on it)
  * receipts on the done phase are unchanged
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
from synapse.panel.activity import tool_status, tool_label, with_undo_receipt  # noqa: E402
from synapse.panel.error_translator import translate_tool_error  # noqa: E402

TOOL = "houdini_set_parm"
INPUT = {"node": "/obj/geo1/box1", "parm": "sizex", "value": 2.0,
         "note": "make the box wider than it is tall for the hero shot"}
INPUT_ECHO = json.dumps(INPUT, default=str)[:120]


def _worker(cw, **kw):
    w = cw.ClaudeWorker([{"role": "user", "content": "hi"}], tools=[],
                        enforce_worker_policy=False, provider=None, **kw)
    w.tool_status = MagicMock()
    return w


def _block():
    return {"id": "tu_1", "name": TOOL, "input": dict(INPUT)}


def _error_emits(worker):
    return [c.args for c in worker.tool_status.emit.call_args_list
            if len(c.args) >= 2 and c.args[1] == "error" and c.args[0] == TOOL]


def _running_emits(worker):
    return [c.args for c in worker.tool_status.emit.call_args_list
            if len(c.args) >= 2 and c.args[1] == "running"]


def _assert_reason(worker, expected_err_text):
    errs = _error_emits(worker)
    assert len(errs) == 1, errs
    _tool, _phase, detail = errs[0]
    assert detail != INPUT_ECHO
    assert not detail.startswith("{")
    assert detail == translate_tool_error(TOOL, expected_err_text)[:120]
    assert len(detail) <= 120
    # The running phase still carries the input echo (h3b pins that shape).
    runs = _running_emits(worker)
    assert runs and runs[0][2] == INPUT_ECHO


# ---------------------------------------------------------------------------
# Branch 1: MCP returned a tool-level is_error result
# ---------------------------------------------------------------------------

def test_mcp_is_error_branch_emits_reason(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    err_text = "Parameter 'sizex' not found on node /obj/geo1/box1"
    monkeypatch.setattr(cw, "try_mcp_tool_call",
                        lambda name, inp: {"content": [{"type": "text", "text": err_text}],
                                           "isError": True})
    monkeypatch.setattr(cw, "unpack_tool_result", lambda r: (err_text, True))
    w = _worker(cw)
    result = w._execute_tool_block(_block())
    assert result["is_error"] is True
    _assert_reason(w, err_text)


# ---------------------------------------------------------------------------
# Branch 2: MCP raised RuntimeError (JSON-RPC error)
# ---------------------------------------------------------------------------

def test_runtime_error_branch_emits_reason(claude_worker_module, monkeypatch):
    cw = claude_worker_module

    def _raise(name, inp):
        raise RuntimeError("Invalid node path: /obj/geo1/box1 does not exist")

    monkeypatch.setattr(cw, "try_mcp_tool_call", _raise)
    w = _worker(cw)
    result = w._execute_tool_block(_block())
    assert result["is_error"] is True
    _assert_reason(w, "Invalid node path: /obj/geo1/box1 does not exist")


# ---------------------------------------------------------------------------
# Branch 3: result decoding raised (outcome unreadable)
# ---------------------------------------------------------------------------

def test_unreadable_outcome_branch_emits_reason(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: {"weird": object()})

    def _boom(r):
        raise ValueError("cannot decode")

    monkeypatch.setattr(cw, "unpack_tool_result", _boom)
    w = _worker(cw)
    result = w._execute_tool_block(_block())
    assert result["is_error"] is True
    _assert_reason(w, "The tool outcome could not be read. Do not retry; "
                      "check the scene/cook state first.")


# ---------------------------------------------------------------------------
# Branch 4: off-main fallback reported request.error (incl. the C7 timeout)
# ---------------------------------------------------------------------------

def test_fallback_request_error_branch_emits_reason(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)
    err_text = "Cook error: Warning: Errors or warnings encountered during VEX compile"

    def _dispatch(request):
        request.error = err_text
        request.done.set()

    w = _worker(cw)
    monkeypatch.setattr(w, "_dispatch_off_main", _dispatch)
    result = w._execute_tool_block(_block())
    assert result["is_error"] is True
    assert result["content"] == err_text        # tool_result text unchanged
    _assert_reason(w, err_text)


def test_fallback_timeout_branch_emits_reason(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)
    monkeypatch.setattr(cw, "_wait_budget", lambda name: 0.01)
    w = _worker(cw)
    monkeypatch.setattr(w, "_dispatch_off_main", lambda request: None)   # never done
    result = w._execute_tool_block(_block())
    assert result["is_error"] is True
    assert "STILL be running inside Houdini" in result["content"]
    errs = _error_emits(w)
    assert len(errs) == 1
    assert errs[0][2] != INPUT_ECHO
    assert errs[0][2] == translate_tool_error(TOOL, result["content"])[:120]


# ---------------------------------------------------------------------------
# Untouched: policy denial and retry breaker keep their own reasons
# ---------------------------------------------------------------------------

def test_policy_denial_still_carries_its_reason(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    sentinel = MagicMock(side_effect=AssertionError("must not dispatch"))
    monkeypatch.setattr(cw, "try_mcp_tool_call", sentinel)
    w = _worker(cw)
    w._enforce_worker_policy = True
    block = {"id": "tu_2", "name": "houdini_execute_python", "input": {"code": "x=1"}}
    result = w._execute_tool_block(block)
    assert result["is_error"] is True
    args = w.tool_status.emit.call_args.args
    assert args[1] == "error"
    assert args[2] != json.dumps(block["input"], default=str)[:120]
    assert args[2]     # a non-empty reason


# ---------------------------------------------------------------------------
# activity.tool_status render
# ---------------------------------------------------------------------------

def test_tool_status_renders_failure_reason():
    detail = translate_tool_error(TOOL, "Invalid node path: /obj/nope")[:120]
    line = tool_status(TOOL, "error", detail)
    assert line.startswith("Failed: %s - " % tool_label(TOOL))
    assert detail in line
    assert tool_status(TOOL, "failed", detail) == line


def test_tool_status_error_without_detail_is_bare():
    assert tool_status(TOOL, "error", None) == "Failed: %s" % tool_label(TOOL)
    assert tool_status(TOOL, "error", "") == "Failed: %s" % tool_label(TOOL)


def test_tool_status_running_and_done_unchanged():
    assert tool_status(TOOL, "running", INPUT_ECHO) == "Running: %s" % tool_label(TOOL)
    receipted = with_undo_receipt(INPUT_ECHO, {"undo_label": "Set Parameter"})
    line = tool_status(TOOL, "done", receipted)
    assert line.startswith("Finished: %s" % tool_label(TOOL))
    assert INPUT_ECHO not in line          # receipts unchanged: detail body not shown


# ---------------------------------------------------------------------------
# Source pins
# ---------------------------------------------------------------------------

def test_translate_tool_error_has_four_worker_callers():
    src = open(os.path.join(_ROOT, "python", "synapse", "panel", "claude_worker.py"),
               encoding="utf-8").read()
    assert src.count("translate_tool_error(") >= 4
    # No error emit still hands the input summary to the artist.
    assert 'self.tool_status.emit(tool_name, "error", summary)' not in src


# ---------------------------------------------------------------------------
# Face tooltip (Qt-gated: real PySide6 + offscreen)
# ---------------------------------------------------------------------------

def _have_real_qt():
    """Decided at CALL time: another test may have installed a MagicMock PySide6 stub."""
    try:
        from unittest import mock
        from PySide6 import QtWidgets
        if isinstance(QtWidgets, mock.NonCallableMock) or isinstance(getattr(QtWidgets, "QApplication", None), mock.NonCallableMock):
            return False
        app = getattr(QtWidgets, "QApplication", None)
        return isinstance(getattr(QtWidgets, "QWidget", None), type) and isinstance(app, type) and callable(getattr(app, "instance", None))
    except Exception:
        return False


def test_face_work_tooltip_carries_reason_on_error():
    if not _have_real_qt():
        pytest.skip("real PySide6 unavailable in this process (stub or absent); run via hython")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from synapse.panel.face_work import FaceWork
    face = FaceWork()
    detail = translate_tool_error(TOOL, "Invalid node path: /obj/nope")[:120]
    face.set_tool_status(TOOL, "error", detail)
    assert detail in face._status.toolTip()
    assert TOOL in face._status.toolTip()
    face.set_tool_status(TOOL, "running", INPUT_ECHO)
    assert face._status.toolTip() == TOOL
    del app
