"""F2 retry cascade circuit-breaker — standalone tests.

Pins three things:

  * the pure decision half (``:func:`retry_breaker.breaker_message``):
    threshold, register-driven block, and the elapsed computation riding the
    register's ``start_ts`` (NOT stall_state's historical ``slowest_label``),
  * the worker wiring (``ClaudeWorker._execute_tool_block``): consecutive
    main-thread abandons of the SAME command + a live register holder → stop
    re-issuing and surface one honest sentence; holder cleared → retry safe,
    history resets; success clears the counter,
  * the breaker reads ``current_main_thread_holder()`` (the F4 register), not
    ``stall_state()`` — the instrument blind to the inline fast-path-2 class.

Runs under stock pytest (no live Houdini, no real Qt — same PySide stub
convention as test_offmain_fallback.py / test_worker_tool_policy.py).
"""

import importlib
import json
import os
import sys
import time
import types
from unittest.mock import MagicMock

import pytest

import pkgbootstrap

_PYTHON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"
)
if sys.path and sys.path[0] != _PYTHON_DIR:
    sys.path.insert(0, _PYTHON_DIR)
_WORKTREE_PANEL_DIR = os.path.join(_PYTHON_DIR, "synapse", "panel")

if "synapse.panel.retry_breaker" not in sys.modules:
    import synapse.panel as _panel_pkg  # noqa: E402
    _ppath = getattr(_panel_pkg, "__path__", None)
    if _ppath is not None and _WORKTREE_PANEL_DIR not in list(_ppath):
        _ppath.insert(0, _WORKTREE_PANEL_DIR)

from synapse.panel.retry_breaker import ABANDON_THRESHOLD, breaker_message


# ---------------------------------------------------------------------------
# 1. Pure decision half — no worker, no Qt
# ---------------------------------------------------------------------------

def test_breaker_silent_below_threshold():
    assert breaker_message(("render", 100.0), 0, now=160.0) is None
    assert breaker_message(("render", 100.0), ABANDON_THRESHOLD - 1, now=160.0) is None


def test_breaker_silent_when_register_idle():
    """No live holder => the hold cleared between iterations => allow retry."""
    assert breaker_message(None, ABANDON_THRESHOLD + 3, now=160.0) is None


def test_breaker_fires_with_label_and_elapsed():
    msg = breaker_message(("execute_python", 100.0), ABANDON_THRESHOLD, now=145.0)
    assert msg == (
        "Houdini is busy — a execute_python operation has held the UI for "
        "45s. Try again when it finishes."
    )


def test_breaker_elapsed_uses_real_clock_when_now_omitted():
    start = time.time() - 12
    msg = breaker_message(("render", start), ABANDON_THRESHOLD)
    assert msg.startswith("Houdini is busy — a render operation")
    # elapsed parses and meets the injected age (never zero, never negative)
    secs = int(msg.split("for ", 1)[1].split("s. ", 1)[0])
    assert secs >= 12


# ---------------------------------------------------------------------------
# 2. Worker wiring — PySide-stubbed ClaudeWorker
# ---------------------------------------------------------------------------

@pytest.fixture
def claude_worker_module():
    """Import claude_worker headlessly, restoring sys.modules afterward
    (mirrors test_offmain_fallback.py's fixture convention)."""
    touched = [
        "PySide6", "PySide6.QtCore",
        "PySide2", "PySide2.QtCore",
        "synapse.panel.claude_worker",
        "synapse.panel.tool_executor",
        "synapse.server.main_thread",
    ]
    saved = pkgbootstrap.snapshot_modules(touched)

    def _is_genuine_qt(modname):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            return False
        return isinstance(getattr(mod, "QThread", None), type)

    real_qt = _is_genuine_qt("PySide6.QtCore") or _is_genuine_qt("PySide2.QtCore")

    if not real_qt:
        class _StubBase:
            def __init__(self, *a, **kw):
                pass

        class _QtCoreStub(types.ModuleType):
            QThread = _StubBase
            QObject = _StubBase

            @staticmethod
            def Signal(*a, **kw):
                return MagicMock()

            @staticmethod
            def Slot(*a, **kw):
                return lambda fn: fn

            def __getattr__(self, name):  # pragma: no cover - defensive
                return MagicMock()

        qtcore = _QtCoreStub("PySide6.QtCore")
        pyside = types.ModuleType("PySide6")
        pyside.QtCore = qtcore
        sys.modules["PySide6"] = pyside
        sys.modules["PySide6.QtCore"] = qtcore
        sys.modules.pop("synapse.panel.tool_executor", None)
    sys.modules.pop("synapse.panel.claude_worker", None)
    import synapse.panel.claude_worker as cw

    try:
        yield cw
    finally:
        pkgbootstrap.restore_modules(saved)


_TIMEOUT_MESSAGE = (
    "Tool 'execute_python' timed out client-side but may STILL be running "
    "inside Houdini — do not retry; check the scene/cook state first. "
    "(socket timeout)"
)


def _make_worker(cw_module):
    worker = cw_module.ClaudeWorker(messages=[], enforce_worker_policy=False)
    worker.tool_status = MagicMock()
    return worker


def _block():
    return {"id": "tu_x", "name": "execute_python", "input": {"code": "print(1)"}}


def _abandoning_mcp(name, inp):
    raise RuntimeError(_TIMEOUT_MESSAGE)


def _set_holder(monkeypatch, cw_module, holder):
    """Plant a fake F4 register state: current_main_thread_holder -> holder."""
    mt = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt, "current_main_thread_holder", lambda: holder)


def test_two_abandons_then_holder_blocks_and_surfaces(claude_worker_module, monkeypatch):
    """2 consecutive abandons of the SAME command + live holder -> stop."""
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", _abandoning_mcp)
    worker = _make_worker(cw)

    r1 = worker._execute_tool_block(_block())
    r2 = worker._execute_tool_block(_block())
    assert r1["is_error"] is True and r2["is_error"] is True
    key = ("execute_python", json.dumps(_block()["input"], sort_keys=True))
    assert worker._retry_abandons[key] == 2

    # The main thread is now reported held (e.g. by the same zombie op).
    captured_calls = {"n": 0}

    def _should_never_dispatch(name, inp):
        captured_calls["n"] += 1
        return {"should": "not be reached"}

    monkeypatch.setattr(cw, "try_mcp_tool_call", _should_never_dispatch)
    _set_holder(monkeypatch, cw, ("execute_python", time.time() - 30.0))

    r3 = worker._execute_tool_block(_block())
    assert captured_calls["n"] == 0, "breaker opened — no re-issue dispatched"
    assert r3["is_error"] is True
    assert r3["content"].startswith(
        "Houdini is busy — a execute_python operation has held the UI for ")
    assert r3["content"].endswith("s. Try again when it finishes.")
    secs = int(r3["content"].split("for ", 1)[1].split("s. ", 1)[0])
    assert secs >= 30
    # Artist sees it on the tool-status rail, not only in the model's log.
    assert any(
        c.args[1] == "error" and c.args[2].startswith("Houdini is busy")
        for c in worker.tool_status.emit.call_args_list
    )


def test_idle_register_lets_retry_through_and_resets(claude_worker_module, monkeypatch):
    """Same 2 abandons, but register idle => the hold finished; allow + reset."""
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", _abandoning_mcp)
    worker = _make_worker(cw)
    worker._execute_tool_block(_block())
    worker._execute_tool_block(_block())

    _set_holder(monkeypatch, cw, None)
    seen = {}

    def _ok(name, inp):
        seen["called"] = True
        return {"ok": True}

    monkeypatch.setattr(cw, "try_mcp_tool_call", _ok)
    r3 = worker._execute_tool_block(_block())
    assert seen.get("called") is True, "idle register => retry dispatches"
    assert r3["is_error"] is False
    key = ("execute_python", json.dumps(_block()["input"], sort_keys=True))
    assert key not in worker._retry_abandons, "success clears the counter"


def test_holder_without_history_does_not_block(claude_worker_module, monkeypatch):
    """A live holder alone never blocks: the breaker is fed by abandons of
    THIS command, not by ambient busyness."""
    cw = claude_worker_module
    seen = {}

    def _ok(name, inp):
        seen["called"] = True
        return {"ok": 1}

    monkeypatch.setattr(cw, "try_mcp_tool_call", _ok)
    _set_holder(monkeypatch, cw, ("render", time.time() - 100.0))
    worker = _make_worker(cw)
    worker._execute_tool_block(_block())
    assert seen.get("called") is True


def test_abandon_counter_scoped_per_command(claude_worker_module, monkeypatch):
    """Two abandons of command A do not charge command B's breaker."""
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", _abandoning_mcp)
    worker = _make_worker(cw)
    worker._execute_tool_block(_block())
    worker._execute_tool_block(_block())

    _set_holder(monkeypatch, cw, ("execute_python", time.time() - 30.0))
    other = {"id": "tu_y", "name": "execute_python", "input": {"code": "print(2)"}}
    dispatched = {}

    def _ok(name, inp):
        dispatched[name] = dispatched.get(name, 0) + 1
        return {"ok": 1}

    monkeypatch.setattr(cw, "try_mcp_tool_call", _ok)
    r = worker._execute_tool_block(other)
    assert "execute_python" in dispatched, "different input = different command"
    assert r["is_error"] is False
