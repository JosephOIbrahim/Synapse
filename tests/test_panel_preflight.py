"""Pre-flight + inline-duration instrumentation for the panel main-thread path.

A tool dispatched inline by the panel (``ToolExecutor.execute_tool``) runs on
Houdini's MAIN thread — the thread that pumps the Qt event loop. A heavy op
freezes the GUI for its whole duration; confirmed live (2026-06-27) a 127KB-dump
execute_python ran inline >5000ms → heartbeat 10.19s, freeze_count=1, silently.

hou MUST run on the main thread, so we cannot move it off. Instead:
  TASK 1 — pre-flight: a cheap, non-blocking heads-up (log + advisory signal)
           when an inline op is likely to briefly freeze the loop.
  TASK 2 — instrument: record every inline tool duration and log when a single
           op exceeds the slow threshold, so the freeze contributor is named.

These tests pin that the pre-flight is advisory ONLY (never blocks, never alters
the tool result) and that the instrumentation records + flags slow ops.

Pure logic + a lightweight Qt stub — runs under stock pytest.
"""

import sys
import types
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Qt stub (the established sibling convention, e.g. test_timeouts_c7.py):
# tool_executor imports PySide6.QtCore at top. setdefault → real PySide6/hython
# wins when present; in bare stock python the stub makes these tests
# deterministic instead of order-dependent on other tests' stubs.
# ---------------------------------------------------------------------------
if "PySide6" not in sys.modules:
    # Mirror the canonical sibling stub (test_timeouts_c7.py) EXACTLY: this test
    # sorts before others, so if it plants first its stub is the one siblings
    # (claude_worker → QThread/Signal) inherit. A partial stub here would break
    # them ("alphabetically-first planter wins" trap). No QtWidgets/QApplication
    # — that would trip the panel suite's genuine-PySide guard.
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

from synapse.panel import bridge_adapter as ba
from synapse.panel import tool_executor as te


# ===========================================================================
# TASK 1 heuristic — estimate_inline_cost (pure, no Qt, no hou)
# ===========================================================================

def test_heavy_inline_code_is_flagged():
    code = "x = 0\n" * 1000  # ~6000 chars, well over PREFLIGHT_HEAVY_CODE_CHARS
    heavy, msg = ba.estimate_inline_cost("houdini_execute_python", {"code": code})
    assert heavy is True
    assert "main thread" in msg
    assert "houdini_execute_python" in msg


def test_content_field_also_counts_as_code():
    # The execute_python payload builder produces {"content": code}; the inline
    # path may see either the raw API field ("code") or the built payload.
    big = "print(1)\n" * 500
    heavy, _ = ba.estimate_inline_cost("houdini_execute_python", {"content": big})
    assert heavy is True


def test_trivial_make_a_box_is_not_flagged():
    # The canonical light case — must NOT raise a noisy advisory.
    heavy, msg = ba.estimate_inline_cost(
        "houdini_execute_python",
        {"code": "hou.node('/obj').createNode('geo')"},
    )
    assert heavy is False
    assert msg == ""


def test_known_slow_tool_flagged_even_with_tiny_payload():
    heavy, msg = ba.estimate_inline_cost("houdini_render", {"node": "/stage/rop"})
    assert heavy is True
    assert "houdini_render" in msg


def test_oversized_payload_is_flagged():
    blob = {"data": ["item" * 50] * 400}  # large overall payload, no code field
    heavy, msg = ba.estimate_inline_cost("houdini_set_parm", blob)
    assert heavy is True
    assert "payload" in msg


def test_estimate_tolerates_non_dict_input():
    heavy, msg = ba.estimate_inline_cost("houdini_set_parm", None)
    assert heavy is False
    assert msg == ""


# ===========================================================================
# Fakes for exercising ToolExecutor.execute_tool without hou
# ===========================================================================

class _Resp:
    def __init__(self, data):
        self.success = True
        self.data = data
        self.error = None


class _Handler:
    def __init__(self, data):
        self._data = data
        self.calls = []

    def handle(self, command):
        self.calls.append(command)
        return _Resp(self._data)


def _wire_executor(monkeypatch, handler, cmd_type="execute_python"):
    """Build a ToolExecutor with the dispatch + handler stubbed, and force the
    direct (non-bridge) path so the handler result passes through unmodified —
    isolating what the pre-flight/instrumentation does to the result (nothing).
    """
    executor = te.ToolExecutor()
    monkeypatch.setattr(
        te, "get_tool_dispatch",
        lambda name: (cmd_type, lambda inp: dict(inp)),
    )
    monkeypatch.setattr(ba, "is_read_only", lambda name: True)  # skip bridge
    monkeypatch.setattr(executor, "_get_handler", lambda: handler)
    return executor


# ===========================================================================
# TASK 1 — pre-flight surfaces an advisory, but never changes the result
# ===========================================================================

def test_heavy_execute_python_logs_advisory_and_returns_result(monkeypatch, caplog):
    te.reset_panel_inline_stats()
    data = {"made": "box"}
    handler = _Handler(data)
    executor = _wire_executor(monkeypatch, handler)

    req = te.ToolRequest(
        tool_use_id="tu_1",
        tool_name="houdini_execute_python",
        tool_input={"code": "y = 1\n" * 1000},
    )

    with caplog.at_level("WARNING"):
        executor.execute_tool(req)

    # Advisory surfaced (attributable, not silent)...
    assert any("Pre-flight advisory" in r.message for r in caplog.records)
    assert executor._last_preflight is not None
    # ...but the result is exactly what the handler returned — unchanged.
    assert req.error is None
    assert req.result == data
    assert req.done.is_set()
    assert len(handler.calls) == 1


def test_light_tool_emits_no_advisory_but_still_records(monkeypatch, caplog):
    te.reset_panel_inline_stats()
    data = {"ok": True}
    handler = _Handler(data)
    executor = _wire_executor(monkeypatch, handler)

    req = te.ToolRequest(
        tool_use_id="tu_2",
        tool_name="houdini_execute_python",
        tool_input={"code": "hou.node('/obj').createNode('geo')"},
    )

    with caplog.at_level("WARNING"):
        executor.execute_tool(req)

    # No noisy advisory for the trivial case...
    assert not any("Pre-flight advisory" in r.message for r in caplog.records)
    assert executor._last_preflight is None
    # ...result unchanged, and instrumentation still records the inline op.
    assert req.error is None
    assert req.result == data
    assert te.panel_inline_stats()["count"] == 1


def test_preflight_does_not_change_result_heavy_vs_light(monkeypatch):
    """The pre-flight verdict must not influence the delivered result."""
    data = {"value": 42}

    heavy_handler = _Handler(data)
    heavy_exec = _wire_executor(monkeypatch, heavy_handler)
    heavy_req = te.ToolRequest("tu_h", "houdini_execute_python",
                               {"code": "z = 1\n" * 1000})
    heavy_exec.execute_tool(heavy_req)

    light_handler = _Handler(data)
    light_exec = _wire_executor(monkeypatch, light_handler)
    light_req = te.ToolRequest("tu_l", "houdini_execute_python", {"code": "z = 1"})
    light_exec.execute_tool(light_req)

    assert heavy_req.result == light_req.result == data
    assert heavy_req.error is None and light_req.error is None


# ===========================================================================
# TASK 2 — inline-duration instrumentation
# ===========================================================================

def test_record_panel_inline_counts_and_flags_slow():
    te.reset_panel_inline_stats()
    te._record_panel_inline("houdini_set_parm", 12.0)        # fast
    te._record_panel_inline("houdini_execute_python", 5000.0)  # slow

    stats = te.panel_inline_stats()
    assert stats["count"] == 2
    assert stats["slow_count"] == 1
    assert stats["max_ms"] == 5000.0
    assert stats["slowest_tool"] == "houdini_execute_python"
    # snapshot is a copy — mutating it must not corrupt the live counters
    stats["count"] = 999
    assert te.panel_inline_stats()["count"] == 2


def test_execute_tool_records_one_inline_sample(monkeypatch):
    te.reset_panel_inline_stats()
    handler = _Handler({"ok": 1})
    executor = _wire_executor(monkeypatch, handler)
    req = te.ToolRequest("tu_3", "houdini_set_parm", {"node": "/obj", "value": 1})

    executor.execute_tool(req)

    assert te.panel_inline_stats()["count"] == 1


def test_slow_inline_op_names_itself_in_the_log(monkeypatch, caplog):
    te.reset_panel_inline_stats()
    # Force every op to count as slow without sleeping a real second.
    monkeypatch.setattr(te, "PANEL_INLINE_SLOW_MS", 0.0)
    handler = _Handler({"ok": 1})
    executor = _wire_executor(monkeypatch, handler)
    req = te.ToolRequest("tu_4", "houdini_execute_python", {"code": "1"})

    with caplog.at_level("WARNING"):
        executor.execute_tool(req)

    slow_logs = [r for r in caplog.records if "ran" in r.message and "main thread" in r.message]
    assert slow_logs, "a slow inline op must name itself in the log"
    assert any("houdini_execute_python" in r.getMessage() for r in slow_logs)


def test_unknown_tool_records_no_inline_sample(monkeypatch):
    """Early-return paths (unknown tool) must not record a spurious duration."""
    te.reset_panel_inline_stats()
    monkeypatch.setattr(te, "get_tool_dispatch", lambda name: None)
    executor = te.ToolExecutor()
    req = te.ToolRequest("tu_5", "nonexistent_tool", {})

    executor.execute_tool(req)

    assert req.error is not None
    assert te.panel_inline_stats()["count"] == 0
