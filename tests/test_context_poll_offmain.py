"""Off-main scene-context gather — the panel poll/send freeze-hardening.

Companion to ``test_offmain_fallback.py`` (the tool-call fallback fix,
6f354ae). That fix closed the inline-hou-on-main-thread freeze on the
tool-dispatch path; this pins the SAME fix class on the panel's own
context-gather path (the 10 s ``_poll_context`` QTimer + the send-time
``_gather_context_if_stale``).

Before: both call sites ran ``_gather_context_on_main_thread()`` directly
from the main thread (a Qt slot). ``run_on_main``'s Fast path 2
(``main_thread.py:240`` — "caller IS main thread → fn() inline, NO timeout
possible") applied, so every ``hou.selectedNodes()`` / ``hou.ui.paneTabs()``
read froze the GUI for its duration.

After: ``ws_bridge.gather_context_off_main`` spawns a daemon thread that
calls ``run_on_main(_gather_context_on_main_thread, ...)`` from OFF main,
so the read takes the DEFERRED path (``hdefereval.executeDeferred`` + bounded
timeout, interleaved with UI events). On a busy main thread it sheds and
keeps the stale cache; the chips are advisory.

These tests pin (without a live Houdini):

  * the gather runs on a NON-main thread (so run_on_main would resolve to
    the DEFERRED path, not Fast path 2),
  * ``run_on_main`` is called with ``record_stall=False`` and
    ``record_wait=False`` (observe-only — must not pollute the stall
    detector or the C6 dispatch-wait histogram),
  * the fn handed to ``run_on_main`` IS ``_gather_context_on_main_thread``
    (the real gather, not an inline lambda that would re-introduce the bug),
  * on success ``on_ready`` is invoked with the context,
  * on a run_on_main timeout/raise, ``on_ready`` is NOT called (shed → keep
    stale cache, no exception escapes).

Pure logic + a lightweight PySide6.QtCore stub — runs under stock pytest.
Patching mirrors ``test_live_metrics_threadsafe.py``: a string-path
``unittest.mock.patch("synapse.server.main_thread.run_on_main", ...)``, which
resolves the module fresh and is robust to import-order pollution across the
full suite (the same pattern the live-metrics tests use for this seam).
"""

import importlib
import os
import sys
import threading
import time
import types
from unittest.mock import MagicMock, patch

import pytest

import pkgbootstrap

# Ensure THIS worktree's synapse.panel.ws_bridge wins.
_PYTHON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"
)
if sys.path and sys.path[0] != _PYTHON_DIR:
    sys.path.insert(0, _PYTHON_DIR)
_WORKTREE_PANEL_DIR = os.path.join(_PYTHON_DIR, "synapse", "panel")


# ---------------------------------------------------------------------------
# PySide6.QtCore stub fixture (sys.modules-restoring, no leak)
# ---------------------------------------------------------------------------
@pytest.fixture
def ws_bridge_module():
    """Import ws_bridge headlessly, restoring sys.modules afterward.

    ws_bridge only needs QtCore (QThread/Signal/Slot/QMetaObject/Qt/Q_ARG).
    If genuine PySide6/PySide2 is present we use it; otherwise we install a
    minimal QtCore stub whose QThread is a plain base class, Signal is a
    no-op factory, and everything else is a MagicMock. Then we import
    synapse.panel.ws_bridge and yield it.
    """
    touched = [
        "PySide6", "PySide6.QtCore",
        "PySide2", "PySide2.QtCore",
        "synapse.panel.ws_bridge",
    ]
    # R310: snapshot through pkgbootstrap so the teardown restores BOTH halves.
    # The `import synapse.panel.ws_bridge` below is a real import and binds its
    # fresh module on synapse.panel; putting the original back in sys.modules
    # alone leaves that binding on the throwaway — resolution that succeeds and
    # returns the wrong module. snapshot_modules also keeps ABSENT distinct
    # from a stored None, which the old `sys.modules.get(k)` dict conflated.
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

            def __getattr__(self, name):  # QMetaObject / Qt / Q_ARG / etc.
                return MagicMock()

        qtcore = _QtCoreStub("PySide6.QtCore")
        pyside = types.ModuleType("PySide6")
        pyside.QtCore = qtcore
        sys.modules["PySide6"] = pyside
        sys.modules["PySide6.QtCore"] = qtcore

    if "synapse.panel" not in sys.modules:
        import synapse.panel as _panel_pkg  # noqa: E402
        _ppath = getattr(_panel_pkg, "__path__", None)
        if _ppath is not None and _WORKTREE_PANEL_DIR not in list(_ppath):
            _ppath.insert(0, _WORKTREE_PANEL_DIR)

    sys.modules.pop("synapse.panel.ws_bridge", None)
    import synapse.panel.ws_bridge as wsb

    try:
        yield wsb
    finally:
        pkgbootstrap.restore_modules(saved)


# ---------------------------------------------------------------------------
# A fake run_on_main that records how it was called + which thread asked.
# ---------------------------------------------------------------------------
class _FakeRunOnMain:
    """Replaces synapse.server.main_thread.run_on_main for the test.

    Records the fn, the record_stall / record_wait flags, and the caller
    thread ident. Returns ``self.retval`` by default, or raises ``self.exc``
    if set (simulating a main-thread timeout). NEVER calls fn — the gather
    fn is the production ``_gather_context_on_main_thread`` which touches
    hou; the point is to assert what run_on_main is called WITH, not to
    execute it.
    """
    def __init__(self, retval=None, exc=None):
        self.retval = retval
        self.exc = exc
        self.calls = []

    def __call__(self, fn, timeout=10.0, record_stall=True, record_wait=True):
        self.calls.append({
            "fn": fn,
            "timeout": timeout,
            "record_stall": record_stall,
            "record_wait": record_wait,
            "caller_ident": threading.current_thread().ident,
        })
        if self.exc is not None:
            raise self.exc
        return self.retval


def _wait_for_calls(fake, n=1, timeout_s=2.0):
    """Spin until the daemon thread has hit run_on_main n times."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if len(fake.calls) >= n:
            return True
        time.sleep(0.01)
    return len(fake.calls) >= n


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_gather_runs_off_main_thread(ws_bridge_module):
    """The on_ready callback (and thus the run_on_main call) happens on a
    NON-main thread — the precondition for run_on_main's DEFERRED path."""
    wsb = ws_bridge_module
    main_ident = threading.main_thread().ident

    fake = _FakeRunOnMain(retval={"selected_nodes": [], "current_network": "/obj"})
    done = threading.Event()
    seen_thread = []

    def on_ready(ctx):
        seen_thread.append(threading.current_thread().ident)
        done.set()

    with patch("synapse.server.main_thread.run_on_main", fake):
        wsb.gather_context_off_main(on_ready)

    assert done.wait(2.0), "on_ready was never called"
    assert fake.calls, "run_on_main was never invoked"
    assert seen_thread[0] != main_ident, (
        "gather ran on the main thread — run_on_main would hit Fast path 2 "
        "(inline, no timeout) and the freeze fix is void"
    )


def test_run_on_main_called_observe_only(ws_bridge_module):
    """record_stall=False AND record_wait=False — an advisory read must not
    trip the 2-strike stall detector nor pollute the C6 dispatch-wait
    histogram (see run_on_main docstring)."""
    wsb = ws_bridge_module
    fake = _FakeRunOnMain(retval={"selected_nodes": []})
    with patch("synapse.server.main_thread.run_on_main", fake):
        wsb.gather_context_off_main(lambda ctx: None)
        assert _wait_for_calls(fake), "run_on_main was never invoked"
    call = fake.calls[0]
    assert call["record_stall"] is False, (
        "advisory context gather must opt out of the stall detector — two "
        "back-to-back timeouts would otherwise fast-fail REAL commands"
    )
    assert call["record_wait"] is False, (
        "advisory context gather must opt out of the C6 dispatch-wait "
        "histogram — it must stay a measure of REAL command waits"
    )


def test_real_gather_fn_passed_to_run_on_main(ws_bridge_module):
    """The fn handed to run_on_main IS ``_gather_context_on_main_thread`` —
    the real gather, not an inline lambda wrapping it (which would defeat
    the seam and could re-introduce an inline hou call)."""
    wsb = ws_bridge_module
    fake = _FakeRunOnMain(retval={"selected_nodes": []})
    with patch("synapse.server.main_thread.run_on_main", fake):
        wsb.gather_context_off_main(lambda ctx: None)
        assert _wait_for_calls(fake), "run_on_main was never invoked"
    assert fake.calls[0]["fn"] is wsb._gather_context_on_main_thread, (
        "run_on_main must marshal the real gather fn, not a wrapper"
    )


def test_on_ready_receives_context_on_success(ws_bridge_module):
    """Success path: on_ready is called with the ctx returned by run_on_main."""
    wsb = ws_bridge_module
    ctx = {"selected_nodes": ["/obj/geo1"], "current_network": "/obj",
           "scene_file": "/tmp/hip.hip", "frame": 24}
    received = []
    done = threading.Event()

    def on_ready(c):
        received.append(c)
        done.set()

    fake = _FakeRunOnMain(retval=ctx)
    with patch("synapse.server.main_thread.run_on_main", fake):
        wsb.gather_context_off_main(on_ready)
        assert done.wait(2.0), "on_ready was never called on success"
    assert received[0] is ctx


def test_sheds_on_timeout_without_calling_on_ready(ws_bridge_module):
    """Timeout/busy path: run_on_main raises, on_ready is NOT called, and no
    exception escapes the daemon thread (shed → caller keeps stale cache)."""
    wsb = ws_bridge_module
    called = []
    fake = _FakeRunOnMain(exc=RuntimeError("main thread didn't respond in time"))

    def on_ready(c):
        called.append(c)

    with patch("synapse.server.main_thread.run_on_main", fake):
        wsb.gather_context_off_main(on_ready)
        assert _wait_for_calls(fake), "run_on_main was never invoked"
    # The daemon thread hit the exception + shed; on_ready must not fire.
    time.sleep(0.2)
    assert called == [], (
        "on_ready fired after a timeout — a busy main thread would still "
        "drive the chip update; the shed contract is broken"
    )


def test_on_ready_exception_does_not_escape(ws_bridge_module):
    """A buggy on_ready callback must not crash the daemon thread (it would
    otherwise surface as a noisy traceback for an advisory path). The helper
    swallows it; the thread simply exits."""
    wsb = ws_bridge_module

    def bad_on_ready(ctx):
        raise ValueError("buggy chip update")

    fake = _FakeRunOnMain(retval={"x": 1})
    # Should not raise from gather_context_off_main itself.
    with patch("synapse.server.main_thread.run_on_main", fake):
        wsb.gather_context_off_main(bad_on_ready)
        assert _wait_for_calls(fake), "run_on_main was never invoked"
    time.sleep(0.2)  # daemon thread runs, exception is swallowed
    # No assertion possible on absence of a traceback here; reaching this
    # line (the call returning + the fake being hit) is the pass condition.