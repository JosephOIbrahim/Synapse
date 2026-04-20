"""Host-layer tests (Sprint 3 Spike 2 Phase 1).

Covers the pieces of ``synapse.host.*`` that can be exercised without
an actual Houdini process. Tests that genuinely need ``hou`` /
``hdefereval`` at runtime go in the Crucible protocol in Phase 2.
"""

from __future__ import annotations

import os
import sys
import threading
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# synapse.host.auth
# ---------------------------------------------------------------------------


class TestAuth:
    """API-key resolution: hou.secure → env var → None."""

    def test_env_var_fallback(self, monkeypatch):
        from synapse.host.auth import get_anthropic_api_key

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
        # Make sure hou import fails so we fall through
        monkeypatch.setitem(sys.modules, "hou", None)
        assert get_anthropic_api_key() == "sk-ant-test-123"

    def test_env_var_whitespace_treated_as_missing(self, monkeypatch):
        from synapse.host.auth import get_anthropic_api_key

        monkeypatch.setenv("ANTHROPIC_API_KEY", "   \n\t  ")
        monkeypatch.setitem(sys.modules, "hou", None)
        assert get_anthropic_api_key() is None

    def test_no_source_returns_none(self, monkeypatch):
        from synapse.host.auth import get_anthropic_api_key

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setitem(sys.modules, "hou", None)
        assert get_anthropic_api_key() is None

    def test_hou_secure_preferred_over_env_var(self, monkeypatch):
        from synapse.host.auth import get_anthropic_api_key

        fake_hou = types.ModuleType("hou")
        fake_hou.secure = types.SimpleNamespace(  # type: ignore[attr-defined]
            password=lambda label: "sk-from-hou-secure" if label == "synapse_anthropic" else None
        )
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")

        assert get_anthropic_api_key() == "sk-from-hou-secure"

    def test_hou_secure_empty_falls_back_to_env(self, monkeypatch):
        from synapse.host.auth import get_anthropic_api_key

        fake_hou = types.ModuleType("hou")
        fake_hou.secure = types.SimpleNamespace(password=lambda _: "")  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-used")

        assert get_anthropic_api_key() == "sk-env-used"

    def test_hou_secure_exception_falls_back_to_env(self, monkeypatch):
        from synapse.host.auth import get_anthropic_api_key

        def _boom(_label):
            raise RuntimeError("credential store offline")

        fake_hou = types.ModuleType("hou")
        fake_hou.secure = types.SimpleNamespace(password=_boom)  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-recovered")

        assert get_anthropic_api_key() == "sk-recovered"


# ---------------------------------------------------------------------------
# synapse.host.dialog_suppression
# ---------------------------------------------------------------------------


class TestDialogSuppression:
    """Context manager patches + restores hou.ui.* blocking methods."""

    def test_noop_outside_houdini(self, monkeypatch):
        from synapse.host.dialog_suppression import suppress_modal_dialogs

        monkeypatch.setitem(sys.modules, "hou", None)
        with suppress_modal_dialogs():
            pass  # must not raise

    def test_noop_when_hou_ui_missing(self, monkeypatch):
        from synapse.host.dialog_suppression import suppress_modal_dialogs

        fake_hou = types.ModuleType("hou")
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        with suppress_modal_dialogs():
            pass

    def test_patches_block_methods_and_restores(self, monkeypatch):
        from synapse.host.dialog_suppression import (
            ModalDialogSuppressedError,
            suppress_modal_dialogs,
        )

        original_display = MagicMock(return_value="artist-said-yes")
        original_select = MagicMock(return_value=(0, "item"))

        fake_ui = types.SimpleNamespace(
            displayMessage=original_display,
            selectFromList=original_select,
        )
        fake_hou = types.ModuleType("hou")
        fake_hou.ui = fake_ui  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        with suppress_modal_dialogs():
            with pytest.raises(ModalDialogSuppressedError) as exc_info:
                fake_ui.displayMessage("hello")
            assert exc_info.value.method_name == "displayMessage"
            assert exc_info.value.args == ("hello",)

        # Restored after context exit
        assert fake_ui.displayMessage is original_display
        assert fake_ui.selectFromList is original_select

    def test_restores_even_if_body_raises(self, monkeypatch):
        from synapse.host.dialog_suppression import suppress_modal_dialogs

        original = MagicMock()
        fake_ui = types.SimpleNamespace(displayMessage=original)
        fake_hou = types.ModuleType("hou")
        fake_hou.ui = fake_ui  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        with pytest.raises(ValueError):
            with suppress_modal_dialogs():
                raise ValueError("body failure")

        assert fake_ui.displayMessage is original

    def test_error_captures_args_and_kwargs(self, monkeypatch):
        from synapse.host.dialog_suppression import (
            ModalDialogSuppressedError,
            suppress_modal_dialogs,
        )

        fake_ui = types.SimpleNamespace(displayMessage=lambda *a, **k: None)
        fake_hou = types.ModuleType("hou")
        fake_hou.ui = fake_ui  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        with suppress_modal_dialogs():
            with pytest.raises(ModalDialogSuppressedError) as exc_info:
                fake_ui.displayMessage("title", severity=1, buttons=("OK",))

        assert exc_info.value.method_name == "displayMessage"
        assert exc_info.value.args == ("title",)
        assert exc_info.value.kwargs == {"severity": 1, "buttons": ("OK",)}


# ---------------------------------------------------------------------------
# synapse.host.main_thread_executor
# ---------------------------------------------------------------------------


class TestMainThreadExecutor:
    """Three-state runtime detection + executor behaviour per mode.

    Spike 2.1 replaced the binary stock-vs-Houdini check with a
    stock / gui / headless tri-state. These tests pin each branch.
    """

    # -- Runtime mode detection -----------------------------------------

    def test_detects_stock_when_no_hou(self, monkeypatch):
        from synapse.host.main_thread_executor import (
            RUNTIME_STOCK,
            detect_runtime_mode,
        )

        monkeypatch.setitem(sys.modules, "hou", None)
        assert detect_runtime_mode() == RUNTIME_STOCK

    def test_detects_gui_when_is_ui_available_true(self, monkeypatch):
        from synapse.host.main_thread_executor import (
            RUNTIME_GUI,
            detect_runtime_mode,
        )

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: True  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        assert detect_runtime_mode() == RUNTIME_GUI

    def test_detects_headless_when_is_ui_available_false(self, monkeypatch):
        from synapse.host.main_thread_executor import (
            RUNTIME_HEADLESS,
            detect_runtime_mode,
        )

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: False  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        assert detect_runtime_mode() == RUNTIME_HEADLESS

    def test_detection_raises_when_isuiavailable_missing(self, monkeypatch):
        from synapse.host.main_thread_executor import detect_runtime_mode

        fake_hou = types.ModuleType("hou")
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        with pytest.raises(RuntimeError, match="isUIAvailable is missing"):
            detect_runtime_mode()

    # -- Execution per mode ---------------------------------------------

    def test_stock_mode_raises_with_testing_advice(self, monkeypatch):
        from synapse.host import main_thread_executor as mte

        monkeypatch.setitem(sys.modules, "hou", None)
        with pytest.raises(RuntimeError, match="is_testing=True"):
            mte.main_thread_exec(lambda: {"x": 1}, {})

    def test_headless_mode_runs_directly_on_calling_thread(self, monkeypatch):
        """Spike 2.1 bug fix — headless must NOT hit hdefereval."""
        from synapse.host import main_thread_executor as mte

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: False  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        caller_thread = threading.current_thread().ident
        seen_threads: list = []

        def _probe(value):
            seen_threads.append(threading.current_thread().ident)
            return {"got": value, "thread": threading.current_thread().ident}

        result = mte.main_thread_exec(_probe, {"value": "hi"})
        assert result == {"got": "hi", "thread": caller_thread}
        # Confirm we ran on the caller's thread, not a worker.
        assert seen_threads == [caller_thread]

    def test_headless_mode_propagates_exceptions(self, monkeypatch):
        from synapse.host import main_thread_executor as mte

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: False  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        def _boom():
            raise ValueError("headless explosion")

        with pytest.raises(ValueError, match="headless explosion"):
            mte.main_thread_exec(_boom, {})

    def test_headless_mode_does_not_touch_hdefereval(self, monkeypatch):
        """Regression guard — if this ever hits hdefereval, headless is broken."""
        from synapse.host import main_thread_executor as mte

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: False  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        sentinel = MagicMock()
        sentinel.executeInMainThreadWithResult.side_effect = AssertionError(
            "headless mode must not call hdefereval"
        )
        monkeypatch.setattr(mte, "hdefereval", sentinel)
        monkeypatch.setattr(mte, "_HDEFEREVAL_AVAILABLE", True)

        mte.main_thread_exec(lambda: {"ok": True}, {})
        sentinel.executeInMainThreadWithResult.assert_not_called()

    def test_gui_mode_routes_through_hdefereval(self, monkeypatch):
        from synapse.host import main_thread_executor as mte

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: True  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        captured: list = []

        def _fake_execute(callable_arg):
            captured.append("called")
            return callable_arg()

        fake_hdefereval = types.SimpleNamespace(
            executeInMainThreadWithResult=_fake_execute
        )
        monkeypatch.setattr(mte, "hdefereval", fake_hdefereval)
        monkeypatch.setattr(mte, "_HDEFEREVAL_AVAILABLE", True)

        result = mte.main_thread_exec(lambda: {"via": "hdefereval"}, {})
        assert result == {"via": "hdefereval"}
        assert captured == ["called"]

    def test_gui_mode_raises_if_hdefereval_missing(self, monkeypatch):
        """Defensive: UI=True + hdefereval unavailable is inconsistent."""
        from synapse.host import main_thread_executor as mte

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: True  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        monkeypatch.setattr(mte, "_HDEFEREVAL_AVAILABLE", False)

        with pytest.raises(RuntimeError, match="hdefereval is not"):
            mte.main_thread_exec(lambda: {"x": 1}, {})

    # -- Timeout + contract constants -----------------------------------

    def test_timeout_error_is_timeout_error(self):
        from synapse.host.main_thread_executor import MainThreadTimeoutError

        assert issubclass(MainThreadTimeoutError, TimeoutError)

    def test_default_timeout_constant(self):
        from synapse.host.main_thread_executor import (
            DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS,
        )

        # Spike 2 lock: must be 30s.
        assert DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS == 30.0


# ---------------------------------------------------------------------------
# synapse.host.transport
# ---------------------------------------------------------------------------


class TestTransport:
    """The in-process execute_python adapter."""

    def test_stdout_capture_under_patched_executor(self, monkeypatch):
        from synapse.host import transport as transport_mod

        def _fake_executor(fn, kwargs, *, timeout=None):
            # Simulates main_thread_exec synchronously on caller thread
            return fn(**kwargs)

        monkeypatch.setattr(transport_mod, "main_thread_exec", _fake_executor)

        out = transport_mod.execute_python("print('hello from code')")
        assert out == "hello from code\n"

    def test_empty_output_returns_empty_string(self, monkeypatch):
        from synapse.host import transport as transport_mod

        monkeypatch.setattr(
            transport_mod,
            "main_thread_exec",
            lambda fn, kw, *, timeout=None: fn(**kw),
        )
        assert transport_mod.execute_python("pass") == ""

    def test_exception_in_code_propagates(self, monkeypatch):
        from synapse.host import transport as transport_mod

        monkeypatch.setattr(
            transport_mod,
            "main_thread_exec",
            lambda fn, kw, *, timeout=None: fn(**kw),
        )
        with pytest.raises(ValueError, match="boom"):
            transport_mod.execute_python("raise ValueError('boom')")


# ---------------------------------------------------------------------------
# synapse.host.daemon
# ---------------------------------------------------------------------------


class TestDaemonBootGate:
    """Boot refuses unless hou.isUIAvailable() returns True."""

    def test_boot_refuses_without_hou(self, monkeypatch):
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        monkeypatch.setitem(sys.modules, "hou", None)
        d = SynapseDaemon(api_key="test", boot_gate=True)
        with pytest.raises(DaemonBootError, match="requires a running Houdini"):
            d.start()

    def test_boot_refuses_when_ui_unavailable(self, monkeypatch):
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: False  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        d = SynapseDaemon(api_key="test", boot_gate=True)
        with pytest.raises(DaemonBootError, match="isUIAvailable"):
            d.start()

    def test_boot_refuses_when_isuiavailable_missing(self, monkeypatch):
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        fake_hou = types.ModuleType("hou")
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        d = SynapseDaemon(api_key="test", boot_gate=True)
        with pytest.raises(DaemonBootError, match="isUIAvailable is missing"):
            d.start()

    def test_boot_gate_bypass_allowed_for_tests(self):
        from synapse.host.daemon import SynapseDaemon

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
        )
        try:
            d.start()
            assert d.is_running
        finally:
            d.stop(timeout=2)


class TestDaemonLifecycle:
    """start → cancel → stop cycle with the boot gate bypassed."""

    def _make(self) -> "SynapseDaemon":
        from synapse.host.daemon import SynapseDaemon

        return SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
        )

    def test_start_signals_started_event(self):
        d = self._make()
        try:
            d.start()
            assert d.started_event.is_set()
        finally:
            d.stop(timeout=2)

    def test_cancel_unblocks_thread(self):
        d = self._make()
        d.start()
        assert not d.exit_event.is_set()
        d.cancel()
        d.exit_event.wait(timeout=3)
        assert d.exit_event.is_set()
        d.stop(timeout=1)

    def test_stop_idempotent(self):
        d = self._make()
        d.start()
        d.stop(timeout=2)
        d.stop(timeout=2)  # second call must not raise

    def test_start_restart_cycle(self):
        d = self._make()
        d.start()
        d.stop(timeout=2)
        d.start()  # restart
        assert d.is_running
        d.stop(timeout=2)

    def test_start_while_running_raises(self):
        from synapse.host.daemon import DaemonBootError

        d = self._make()
        d.start()
        try:
            with pytest.raises(DaemonBootError, match="already running"):
                d.start()
        finally:
            d.stop(timeout=2)

    def test_dispatcher_accessible_after_start(self):
        from synapse.cognitive.dispatcher import Dispatcher

        d = self._make()
        d.start()
        try:
            assert isinstance(d.dispatcher, Dispatcher)
            assert d.dispatcher.is_registered("synapse_inspect_stage")
        finally:
            d.stop(timeout=2)

    def test_dispatcher_unavailable_before_start(self):
        from synapse.host.daemon import DaemonBootError

        d = self._make()
        with pytest.raises(DaemonBootError, match="not been started"):
            _ = d.dispatcher

    def test_cancel_event_survives_restart(self):
        d = self._make()
        d.start()
        d.cancel()
        d.stop(timeout=2)
        assert d.cancel_event.is_set()  # set from previous run

        d.start()  # restart clears it
        assert not d.cancel_event.is_set()
        d.stop(timeout=2)


class TestDaemonAuthResolution:
    """Daemon boot pulls API key from override / hou.secure / env, in order."""

    def test_explicit_override_wins(self, monkeypatch):
        from synapse.host.daemon import SynapseDaemon

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-loses")

        d = SynapseDaemon(
            api_key="sk-override-wins",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
        )
        d.start()
        try:
            assert d._resolved_api_key == "sk-override-wins"
        finally:
            d.stop(timeout=2)

    def test_empty_override_rejected(self):
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        d = SynapseDaemon(api_key="   ", boot_gate=False)
        with pytest.raises(DaemonBootError, match="empty"):
            d.start()

    def test_boot_halts_on_no_key_found(self, monkeypatch):
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setitem(sys.modules, "hou", None)

        d = SynapseDaemon(api_key=None, boot_gate=False)
        with pytest.raises(DaemonBootError, match="No Anthropic API key"):
            d.start()

    def test_env_var_resolves_at_boot(self, monkeypatch):
        from synapse.host.daemon import SynapseDaemon

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-resolved")

        d = SynapseDaemon(
            api_key=None,
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
        )
        d.start()
        try:
            assert d._resolved_api_key == "sk-env-resolved"
        finally:
            d.stop(timeout=2)


class TestDaemonExecutorComposition:
    """Default executor composes suppression + main_thread_exec; custom
    executors are respected."""

    def test_custom_executor_receives_tool_call(self):
        from synapse.host.daemon import SynapseDaemon

        seen = []

        def _capture(fn, kwargs):
            seen.append((fn.__name__, kwargs))
            return fn(**kwargs)

        d = SynapseDaemon(
            api_key="test", boot_gate=False, main_thread_executor=_capture,
        )
        d.start()
        try:
            # Invoke via dispatcher — executor should be called
            d.dispatcher.register("echo", lambda **kw: {"echo": kw})
            d.dispatcher.is_testing = False  # force main-thread path
            result = d.dispatcher.execute("echo", {"value": 42})
            assert result == {"echo": {"value": 42}}
            assert len(seen) == 1
            assert seen[0][1] == {"value": 42}
        finally:
            d.stop(timeout=2)
