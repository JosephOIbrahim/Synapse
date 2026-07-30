"""Off-main Qt-fallback tool dispatch — the bridge-DOWN freeze fix.

When the local MCP endpoint is unreachable (the user's current bridge-DOWN
state), ``ClaudeWorker._execute_tool_block`` used to emit a Qt signal delivered
via AutoConnection to ``ToolExecutor.execute_tool`` on Houdini's MAIN thread.
That ran the WHOLE handler inline on the GUI thread: every internal
``run_on_main`` call hit Fast path 2 (``main_thread.py:240`` — "caller IS main
thread → fn() inline, NO timeout possible"), freezing node selection / viewport
/ the 1s FreezeChain heartbeat for the handler's full duration.

The fix dispatches the SAME handler on a daemon thread the worker spawns.
Because the daemon thread is OFF main, ``run_on_main`` calls inside the handler
take the DEFERRED path (``hdefereval.executeDeferred`` + per-tool timeout,
interleaved with UI events) — identical to the MCP path. The main thread is
freed. No handler / undo / consent / integrity logic is touched; only the
threading context of the dispatch changes.

These tests pin that:

  * the handler now runs on a NON-main thread (so run_on_main resolves to the
    DEFERRED path, not Fast path 2),
  * the ``request.done`` + per-tool budget contract still holds (success →
    result; raise → error; slow → the existing "did not finish" error with no
    double-dispatch),
  * the off-main dispatch still routes read-only tools through
    ``handler.handle`` and mutating tools through
    ``bridge_adapter.execute_through_bridge`` exactly as the inline slot did.

Pure logic + a lightweight Qt stub — runs under stock pytest (no live
Houdini). Mirrors the established ``test_worker_tool_policy.py`` fixture
convention (PySide stub with sys.modules restore on teardown).
"""

import importlib
import os
import sys
import threading
import time
import types
from unittest.mock import MagicMock

import pytest

# Ensure THIS worktree's synapse.panel submodules win (same rationale as
# test_worker_tool_policy.py).
_PYTHON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"
)
if sys.path and sys.path[0] != _PYTHON_DIR:
    sys.path.insert(0, _PYTHON_DIR)
_WORKTREE_PANEL_DIR = os.path.join(_PYTHON_DIR, "synapse", "panel")

if "synapse.panel.worker_policy" not in sys.modules:
    import synapse.panel as _panel_pkg  # noqa: E402
    _ppath = getattr(_panel_pkg, "__path__", None)
    if _ppath is not None and _WORKTREE_PANEL_DIR not in list(_ppath):
        _ppath.insert(0, _WORKTREE_PANEL_DIR)


# ---------------------------------------------------------------------------
# PySide stub fixture (sys.modules-restoring, no leak into sibling tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def claude_worker_module():
    """Import claude_worker headlessly, restoring sys.modules afterward.

    If genuine PySide6/PySide2 (a REAL QThread class) is present we use it;
    otherwise we install minimal stubs (QThread/QObject as plain base classes,
    Signal as a no-op factory, Slot as a passthrough) only for this test, then
    restore every key we touched.
    """
    touched = [
        "PySide6", "PySide6.QtCore",
        "PySide2", "PySide2.QtCore",
        "synapse.panel.claude_worker",
        "synapse.panel.tool_executor",
    ]
    saved = {k: sys.modules.get(k) for k in touched}

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

    if not real_qt:
        sys.modules.pop("synapse.panel.tool_executor", None)
    sys.modules.pop("synapse.panel.claude_worker", None)
    import synapse.panel.claude_worker as cw

    try:
        yield cw
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------
class _Resp:
    def __init__(self, data, success=True, error=None):
        self.success = success
        self.data = data
        self.error = error


class _RecordingHandler:
    """Fake handler whose handle() records the caller thread ident — the proof
    that the handler runs off-main (and so run_on_main would take the DEFERRED
    path, not Fast path 2)."""
    def __init__(self, data=None, exc=None, sleep_s=None, call_run_on_main=None):
        self._data = data
        self._exc = exc
        self._sleep_s = sleep_s
        self._call_run_on_main = call_run_on_main
        self.calls = []
        self.thread_idents = []

    def handle(self, command):
        self.calls.append(command)
        self.thread_idents.append(threading.current_thread().ident)
        if self._sleep_s is not None:
            time.sleep(self._sleep_s)
        if self._call_run_on_main is not None:
            self._call_run_on_main()
        if self._exc is not None:
            raise self._exc
        return _Resp(self._data)


def _make_worker(cw_module, **kwargs):
    worker = cw_module.ClaudeWorker(messages=[], **kwargs)
    worker.tool_status = MagicMock()
    return worker


def _wire(worker_module, monkeypatch, handler, *, read_only=True,
          mutate_bridge=None, tool_name="houdini_get_parm"):
    """Wire a freshly-built executor's dispatch so the fake handler is reached.

    Returns the executor the worker's off-main path will use (built lazily).
    Patches the tool_executor + bridge_adapter namespaces the reloaded
    claude_worker actually imports.
    """
    te = sys.modules["synapse.panel.tool_executor"]
    ba = importlib.import_module("synapse.panel.bridge_adapter")

    monkeypatch.setattr(
        te, "get_tool_dispatch",
        lambda name: ("read", lambda inp: dict(inp)),
    )
    monkeypatch.setattr(ba, "is_read_only", lambda name: read_only)
    if mutate_bridge is not None:
        monkeypatch.setattr(ba, "execute_through_bridge", mutate_bridge)

    worker = _make_worker(worker_module, enforce_worker_policy=False)
    executor = worker._get_offmain_executor()
    monkeypatch.setattr(executor, "_get_handler", lambda: handler)
    return worker, executor


def _block(tool_name="houdini_get_parm"):
    return {"id": "tu_x", "name": tool_name, "input": {"node": "/obj"}}


# ===========================================================================
# 1. The handler runs on a NON-main thread (deferred path, not Fast path 2)
# ===========================================================================

def test_offmain_fallback_runs_handler_off_main(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    # MCP unavailable — forces the Qt-fallback path.
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)

    handler = _RecordingHandler(data={"ok": 1})
    worker, executor = _wire(cw, monkeypatch, handler, read_only=True)

    main_ident = threading.main_thread().ident
    result = worker._execute_tool_block(_block())

    assert handler.calls, "handler.handle was invoked"
    assert len(handler.thread_idents) == 1
    assert handler.thread_idents[0] != main_ident, (
        "handler must run OFF the main thread so run_on_main resolves to the "
        "DEFERRED path (hdefereval.executeDeferred + per-tool timeout), not "
        "Fast path 2 inline"
    )
    assert result["is_error"] is False
    assert '"ok"' in result["content"]


def test_offmain_fallback_run_on_main_called_off_main(claude_worker_module, monkeypatch):
    """Directly assert run_on_main would take the deferred path: a handler
    that calls run_on_main does so from a non-main thread."""
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)

    main_thread = importlib.import_module("synapse.server.main_thread")
    captured = {}

    def _fake_run_on_main(fn, *a, **kw):
        captured["caller_ident"] = threading.current_thread().ident
        return fn()

    monkeypatch.setattr(main_thread, "run_on_main", _fake_run_on_main)

    handler = _RecordingHandler(
        data={"ok": 1},
        call_run_on_main=lambda: main_thread.run_on_main(lambda: None),
    )
    worker, executor = _wire(cw, monkeypatch, handler, read_only=True)

    worker._execute_tool_block(_block())

    assert "caller_ident" in captured, "handler called run_on_main"
    assert captured["caller_ident"] != threading.main_thread().ident


# ===========================================================================
# 2. request.done + per-tool budget contract (C7)
# ===========================================================================

def test_offmain_success_sets_result_and_done(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)
    handler = _RecordingHandler(data={"made": "box"})
    worker, executor = _wire(cw, monkeypatch, handler, read_only=True)

    result = worker._execute_tool_block(_block())

    assert result["is_error"] is False
    assert '"made"' in result["content"]
    assert len(handler.calls) == 1


def test_offmain_handler_raise_sets_error(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)
    handler = _RecordingHandler(exc=RuntimeError("boom"))
    worker, executor = _wire(cw, monkeypatch, handler, read_only=True)

    result = worker._execute_tool_block(_block())

    assert result["is_error"] is True
    assert "boom" in result["content"]


def test_offmain_slow_handler_times_out_no_double_dispatch(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)
    # Shrink the wait budget so the test does not sleep the real 30s floor.
    monkeypatch.setattr(cw, "_wait_budget", lambda name: 0.5)
    # Handler slower than the budget.
    handler = _RecordingHandler(data={"ok": 1}, sleep_s=2.0)
    worker, executor = _wire(cw, monkeypatch, handler, read_only=True)

    t0 = time.perf_counter()
    result = worker._execute_tool_block(_block("houdini_render"))
    elapsed = time.perf_counter() - t0

    assert result["is_error"] is True
    assert "did not finish" in result["content"]
    assert elapsed < 1.5, "the worker must report the timeout promptly, not block on the handler"
    # No double-dispatch: the handler was started exactly once (the abandoned
    # daemon thread may still be sleeping, but it is not re-dispatched).
    assert len(handler.calls) == 1


# ===========================================================================
# 3. Routing: read-only vs mutating selects the same code path as the slot
# ===========================================================================

def test_offmain_read_only_calls_handler_handle_directly(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)

    te = sys.modules["synapse.panel.tool_executor"]
    ba = importlib.import_module("synapse.panel.bridge_adapter")

    bridge_called = {"n": 0}

    def _bridge(*a, **kw):
        bridge_called["n"] += 1
        return _Resp({"via": "bridge"})

    handler = _RecordingHandler(data={"via": "handle"})
    worker, executor = _wire(
        cw, monkeypatch, handler, read_only=True, mutate_bridge=_bridge,
    )

    worker._execute_tool_block(_block("synapse_ping"))  # synapse_ping is read-only

    assert len(handler.calls) == 1, "read-only tool routes through handler.handle"
    assert bridge_called["n"] == 0, "read-only tool must NOT route through the bridge"


def test_offmain_mutating_routes_through_bridge(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: None)

    ba = importlib.import_module("synapse.panel.bridge_adapter")

    bridge_called = {"n": 0}

    def _bridge(tool_name, handler, command):
        bridge_called["n"] += 1
        return _Resp({"via": "bridge"})

    handler = _RecordingHandler(data={"via": "handle"})  # should NOT be called directly
    worker, executor = _wire(
        cw, monkeypatch, handler, read_only=False, mutate_bridge=_bridge,
    )

    worker._execute_tool_block(_block("houdini_create_node"))

    assert bridge_called["n"] == 1, "mutating tool routes through execute_through_bridge"
    assert handler.calls == [], "mutating tool must NOT call handler.handle directly"


# ===========================================================================
# 4. The synchronous execute_tool slot contract is preserved (tests stay green)
# ===========================================================================

def test_execute_tool_slot_still_synchronous_and_sets_done(claude_worker_module, monkeypatch):
    """A direct/test caller of the @Slot still gets result set before return —
    the refactor must not have made execute_tool asynchronous."""
    te = sys.modules["synapse.panel.tool_executor"]
    ba = importlib.import_module("synapse.panel.bridge_adapter")

    monkeypatch.setattr(
        te, "get_tool_dispatch",
        lambda name: ("read", lambda inp: dict(inp)),
    )
    monkeypatch.setattr(ba, "is_read_only", lambda name: True)
    te.reset_panel_inline_stats()
    handler = _RecordingHandler(data={"slot": "ok"})
    executor = te.ToolExecutor()
    monkeypatch.setattr(executor, "_get_handler", lambda: handler)

    req = te.ToolRequest("tu_s", "houdini_get_parm", {"node": "/obj"})

    executor.execute_tool(req)

    assert req.done.is_set()
    assert req.error is None
    assert req.result == {"slot": "ok"}
    assert len(handler.calls) == 1