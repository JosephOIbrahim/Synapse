"""Tests for the main_thread.run_on_main utility.

Verifies:
1. Results are returned correctly through the main-thread wrapper
2. Exceptions are propagated to the calling thread
3. Timeout raises RuntimeError when Houdini's main thread is busy
4. Reentrant calls (nested run_on_main) work without deadlock
"""

import importlib.util
import sys
import threading
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: stub hdefereval so main_thread.py can import it
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    sys.modules["hou"] = _hou

# Create hdefereval stub that executes the deferred fn immediately on a
# simulated "main thread" (actually a new thread, to match the real pattern
# where executeDeferred queues the fn for later execution on a different thread).
_hdefereval = types.ModuleType("hdefereval")


def _mock_executeDeferred(fn):
    """Simulate hdefereval.executeDeferred by running fn in a thread."""
    t = threading.Thread(target=fn, daemon=True)
    t.start()


_hdefereval.executeDeferred = _mock_executeDeferred
sys.modules["hdefereval"] = _hdefereval

# Ensure package modules exist for relative imports
for mod_name, mod_path in [
    ("synapse", Path(__file__).resolve().parent.parent / "python" / "synapse"),
    ("synapse.core", Path(__file__).resolve().parent.parent / "python" / "synapse" / "core"),
    ("synapse.server", Path(__file__).resolve().parent.parent / "python" / "synapse" / "server"),
    ("synapse.session", Path(__file__).resolve().parent.parent / "python" / "synapse" / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

# Import the module under test
_mt_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "server" / "main_thread.py"
spec = importlib.util.spec_from_file_location("synapse.server.main_thread", _mt_path)
mt_mod = importlib.util.module_from_spec(spec)
sys.modules["synapse.server.main_thread"] = mt_mod
spec.loader.exec_module(mt_mod)

run_on_main = mt_mod.run_on_main
_tls = mt_mod._tls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunOnMain:
    """Core run_on_main tests."""

    def test_returns_result(self):
        """fn returns a value -- verify it's passed through."""
        result = run_on_main(lambda: {"hip_file": "test.hip", "frame": 1})
        assert result == {"hip_file": "test.hip", "frame": 1}

    def test_returns_none(self):
        """fn returns None -- verify it's not confused with error."""
        result = run_on_main(lambda: None)
        assert result is None

    def test_propagates_exception(self):
        """fn raises -- verify it's re-raised on the calling thread."""
        def _boom():
            raise ValueError("Couldn't find a node at /obj/missing")

        with pytest.raises(ValueError, match="Couldn't find"):
            run_on_main(_boom)

    def test_propagates_runtime_error(self):
        """fn raises RuntimeError -- verify it's re-raised (not confused with timeout)."""
        def _boom():
            raise RuntimeError("hou.OperationFailed")

        with pytest.raises(RuntimeError, match="hou.OperationFailed"):
            run_on_main(_boom)

    def test_timeout_raises_runtime_error(self):
        """fn never completes -- verify RuntimeError after timeout.

        Must run from a non-main thread so run_on_main actually defers
        through hdefereval instead of taking the main-thread fast path.
        """
        original = _hdefereval.executeDeferred
        _hdefereval.executeDeferred = lambda fn: None  # swallow the fn

        result_holder = [None]

        def _call_from_thread():
            try:
                run_on_main(lambda: 42, timeout=0.1)
            except RuntimeError as e:
                result_holder[0] = e

        try:
            t = threading.Thread(target=_call_from_thread)
            t.start()
            t.join(timeout=5.0)
            assert result_holder[0] is not None
            assert "main thread didn't respond" in str(result_holder[0])
        finally:
            _hdefereval.executeDeferred = original

    def test_reentrant_direct_execution(self):
        """Nested run_on_main calls execute directly (no deadlock)."""
        call_order = []

        def _outer():
            call_order.append("outer_start")
            # This nested call should detect _tls.on_main and run directly
            inner_result = run_on_main(lambda: "inner_value")
            call_order.append("outer_end")
            return inner_result

        result = run_on_main(_outer)
        assert result == "inner_value"
        assert call_order == ["outer_start", "outer_end"]

    def test_tls_flag_cleared_after_normal_execution(self):
        """_tls.on_main is False after run_on_main completes."""
        run_on_main(lambda: 42)
        assert not getattr(_tls, "on_main", False)

    def test_tls_flag_cleared_after_exception(self):
        """_tls.on_main is False even if fn raises."""
        with pytest.raises(ValueError):
            run_on_main(lambda: (_ for _ in ()).throw(ValueError("test")))
        assert not getattr(_tls, "on_main", False)

    def test_custom_timeout(self):
        """Custom timeout is respected.

        Must run from a non-main thread so run_on_main actually defers
        through hdefereval instead of taking the main-thread fast path.
        """
        import time

        original = _hdefereval.executeDeferred

        def _delayed_exec(fn):
            def _delayed():
                time.sleep(0.3)
                fn()
            t = threading.Thread(target=_delayed, daemon=True)
            t.start()

        _hdefereval.executeDeferred = _delayed_exec

        result_holder = [None]

        def _call_from_thread():
            try:
                run_on_main(lambda: 42, timeout=0.05)
            except RuntimeError as e:
                result_holder[0] = e

        try:
            t = threading.Thread(target=_call_from_thread)
            t.start()
            t.join(timeout=5.0)
            assert result_holder[0] is not None
            assert "main thread didn't respond" in str(result_holder[0])
        finally:
            _hdefereval.executeDeferred = original

    def test_main_thread_direct_execution(self):
        """When called from the main thread (e.g. Qt slot), fn runs directly
        without deferring through hdefereval -- avoids deadlock."""
        # We ARE on the main thread in tests, so this should take the fast path
        original = _hdefereval.executeDeferred
        defer_called = [False]

        def _track_defer(fn):
            defer_called[0] = True
            fn()

        _hdefereval.executeDeferred = _track_defer

        try:
            result = run_on_main(lambda: "direct")
            assert result == "direct"
            # executeDeferred should NOT have been called -- fast path 2
            assert not defer_called[0], "Should not defer when already on main thread"
        finally:
            _hdefereval.executeDeferred = original
