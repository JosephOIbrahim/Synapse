"""C7 (CTO Remediation Mile 3.4) — per-tool timeout discipline + double-dispatch kill.

Before C7: the panel hardcoded 30/35s for every tool while the server budgets
120-600s; a >35s tool hit socket.timeout, try_mcp_tool_call returned None
("MCP unavailable"), and the worker FELL THROUGH to the Qt path — re-dispatching
the same mutation while the first still executed inside Houdini. Now:
(a) the timeout table is single-sourced (synapse.core.timeouts) and both clients
budget from it; (b) a client-side timeout RAISES ("still running — do not
retry") instead of returning None, so the worker emits an is_error tool_result
and never re-dispatches; (c) connection-refused still returns None (the genuine
fall-back case is preserved).
"""

import socket
import sys
import types
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Qt stub (the established sibling convention, e.g. test_chat_panel.py): the
# panel modules import PySide6 at top. setdefault → real PySide6/hython wins
# when present; in bare stock python the stub makes these tests deterministic
# instead of order-dependent on other tests' stubs (the documented flake genus).
# Import-only shapes: QObject usable as a base class, Slot a decorator factory,
# QThread/Signal for claude_worker. No QtWidgets/QApplication — cannot trip the
# panel suite's genuine-PySide guard.
# ---------------------------------------------------------------------------
if "PySide6" not in sys.modules:
    class _QObject:
        def __init__(self, *a, **k):
            pass

    class _QThread:
        def __init__(self, *a, **k):
            pass

    _qtcore = types.ModuleType("PySide6.QtCore")
    _qtcore.QObject = _QObject
    _qtcore.QThread = _QThread
    _qtcore.Slot = lambda *a, **k: (lambda f: f)
    _qtcore.Signal = lambda *a, **k: MagicMock()
    _pyside6 = types.ModuleType("PySide6")
    _pyside6.QtCore = _qtcore
    sys.modules["PySide6"] = _pyside6
    sys.modules["PySide6.QtCore"] = _qtcore

from synapse.core import timeouts


# ── the canonical table ──────────────────────────────────────────────────────

def test_command_types_resolve():
    assert timeouts.timeout_for("render") == 120.0
    assert timeouts.timeout_for("tops_cook_node") == 120.0
    assert timeouts.timeout_for("tops_render_sequence") == 600.0
    assert timeouts.timeout_for("unknown_fast_thing") == timeouts.COMMAND_TIMEOUT


def test_mcp_tool_names_resolve_via_prefix_and_alias():
    assert timeouts.timeout_for("houdini_render") == 120.0           # prefix-stripped
    assert timeouts.timeout_for("houdini_execute_python") == 30.0
    assert timeouts.timeout_for("synapse_render_sequence") == 600.0
    assert timeouts.timeout_for("synapse_autonomous_render") == 600.0
    assert timeouts.timeout_for("synapse_safe_render") == 120.0
    assert timeouts.timeout_for("synapse_batch") == 60.0             # alias → batch_commands


def test_stdio_client_uses_the_shared_table():
    import mcp_server
    assert mcp_server._SLOW_COMMANDS is timeouts.SLOW_COMMANDS       # one table, not a copy
    assert mcp_server.COMMAND_TIMEOUT == timeouts.COMMAND_TIMEOUT


# ── the double-dispatch kill ─────────────────────────────────────────────────

def _wired_executor(monkeypatch, exc=None, result=None):
    from synapse.panel import tool_executor as te
    client = MagicMock()
    client.available = True
    if exc is not None:
        client.call_tool.side_effect = exc
    else:
        client.call_tool.return_value = result
    monkeypatch.setattr(te, "_mcp_client", client)
    return te


def test_timeout_raises_do_not_retry(monkeypatch):
    te = _wired_executor(monkeypatch, exc=socket.timeout("timed out"))
    with pytest.raises(RuntimeError) as ei:
        te.try_mcp_tool_call("houdini_render", {})
    msg = str(ei.value)
    assert "STILL be running" in msg and "do not retry" in msg.lower()


def test_connection_refused_still_returns_none(monkeypatch):
    te = _wired_executor(monkeypatch, exc=ConnectionRefusedError("refused"))
    assert te.try_mcp_tool_call("houdini_render", {}) is None        # genuine fall-back preserved


def test_success_passes_through(monkeypatch):
    te = _wired_executor(monkeypatch, result={"ok": True})
    assert te.try_mcp_tool_call("houdini_render", {}) == {"ok": True}


# ── the Qt-fallback budget ───────────────────────────────────────────────────

def test_worker_wait_budget_scales_per_tool():
    from synapse.panel import claude_worker as cw
    assert cw._wait_budget("synapse_render_sequence") == 605.0       # 600 + 5 margin
    assert cw._wait_budget("houdini_render") == 125.0
    assert cw._wait_budget("houdini_set_parm") == cw._TOOL_WAIT_TIMEOUT  # floor holds for fast tools
