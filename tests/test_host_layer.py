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
    """API-key resolution: hou.secure (forward-compat) → env var → None.

    Spike 2.3 field finding: ``hou.secure`` is absent in Houdini
    21.0.671 (only ``secureSelectionOption`` matches ``secure`` in
    ``dir(hou)``). The module keeps the ``hou.secure`` probe as a
    forward-compat path — these tests pin the probe's behaviour so
    it works cleanly if SideFX ships the API in a future release.
    """

    def test_env_var_fallback(self, monkeypatch):
        from synapse.host.auth import get_anthropic_api_key

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
        # Make sure hou import fails so we fall through
        monkeypatch.setitem(sys.modules, "hou", None)
        assert get_anthropic_api_key() == "sk-ant-test-123"

    def test_hou_without_secure_falls_back_to_env(self, monkeypatch):
        """Spike 2.3 production path: hou present, hou.secure absent."""
        from synapse.host.auth import get_anthropic_api_key

        # Real Houdini 21.0.671 state — hou exists, no ``secure`` attr
        fake_hou = types.ModuleType("hou")
        fake_hou.secureSelectionOption = MagicMock()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-wins")
        assert get_anthropic_api_key() == "sk-env-wins"

    def test_hou_secure_without_password_falls_back_to_env(self, monkeypatch):
        """Partial API: ``hou.secure`` present but missing ``.password``."""
        from synapse.host.auth import get_anthropic_api_key

        fake_hou = types.ModuleType("hou")
        fake_hou.secure = types.SimpleNamespace()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-wins")
        assert get_anthropic_api_key() == "sk-env-wins"

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


class TestDaemonInspectorTransportWiring:
    """Spike 2.3: daemon.start() must register the Inspector transport.

    Baseline Crucible hit ``TransportNotConfiguredError`` on first
    tool call because the daemon never called
    ``synapse.inspector.configure_transport``. These tests pin the
    fix: transport is wired during start(), idempotently, and a
    pre-registered transport survives a restart.
    """

    def _make_daemon(self, **overrides):
        from synapse.host.daemon import SynapseDaemon
        defaults = dict(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: MagicMock(),
        )
        defaults.update(overrides)
        return SynapseDaemon(**defaults)

    def test_start_configures_inspector_transport(self):
        from synapse.inspector import (
            is_transport_configured,
            reset_transport,
        )
        reset_transport()
        assert not is_transport_configured()

        d = self._make_daemon()
        d.start()
        try:
            assert is_transport_configured(), (
                "daemon.start() should have called configure_transport"
            )
        finally:
            d.stop(timeout=2)

    def test_start_does_not_override_existing_transport(self):
        """If a transport is already configured (e.g. test fixture),
        daemon must leave it intact — the caller had a reason."""
        from synapse.inspector import (
            configure_transport,
            get_transport,
            reset_transport,
        )
        reset_transport()

        def _sentinel_transport(code, *, timeout=None):
            return '{"schema_version": "1.0.0", "target_path": "/stage", "nodes": []}'

        configure_transport(_sentinel_transport)
        assert get_transport() is _sentinel_transport

        d = self._make_daemon()
        d.start()
        try:
            assert get_transport() is _sentinel_transport, (
                "daemon.start() overwrote pre-registered transport — "
                "idempotency is broken"
            )
        finally:
            d.stop(timeout=2)
            reset_transport()

    def test_start_seeds_env_var_if_unset(self, monkeypatch):
        monkeypatch.delenv(
            "SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE", raising=False
        )
        d = self._make_daemon()
        d.start()
        try:
            assert os.environ.get(
                "SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE"
            ) == "synapse.host.transport"
        finally:
            d.stop(timeout=2)

    def test_start_preserves_existing_env_var(self, monkeypatch):
        """If the operator already pointed the env var somewhere,
        daemon must not stomp on it."""
        monkeypatch.setenv(
            "SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE",
            "custom.transport.module",
        )
        d = self._make_daemon()
        d.start()
        try:
            assert os.environ[
                "SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE"
            ] == "custom.transport.module", (
                "daemon.start() overwrote operator-set env var"
            )
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
            api_key="test",
            boot_gate=False,
            main_thread_executor=_capture,
            anthropic_client_factory=lambda key: MagicMock(),
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


class TestDaemonSubmitTurn:
    """Daemon.submit_turn queues a request, runs the agent loop on the
    daemon thread, returns the AgentTurnResult. All tests inject a
    mock Anthropic client — no real API calls."""

    def _make_daemon(self, responses: list):
        """Build a daemon whose agent loop will consume ``responses``
        in FIFO order when submit_turn is called."""
        from synapse.host.daemon import SynapseDaemon

        # Reuse the agent-loop mock harness from test_agent_loop.
        from test_agent_loop import _MockClient  # type: ignore

        def _factory(_api_key):
            return _MockClient(responses)

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=_factory,
        )
        return d

    def test_submit_turn_end_to_end(self):
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE

        d = self._make_daemon([
            _MockResponse(
                [{"type": "text", "text": "ok"}], stop_reason="end_turn"
            )
        ])
        d.start()
        try:
            result = d.submit_turn("hi", wait_timeout=5)
            assert result.status == STATUS_COMPLETE
            assert result.iterations == 1
        finally:
            d.stop(timeout=2)

    def test_submit_turn_raises_when_daemon_not_running(self):
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            anthropic_client_factory=lambda k: MagicMock(),
        )
        with pytest.raises(DaemonBootError, match="running daemon"):
            d.submit_turn("hi", wait_timeout=1)

    def test_submit_turn_timeout_raises_timeouterror(self):
        """If the agent loop hangs (simulated via a blocking mock),
        submit_turn must surface as TimeoutError, not silently wait."""
        from synapse.host.daemon import SynapseDaemon

        blocked = threading.Event()
        release = threading.Event()

        class _HangingClient:
            def __init__(self, *a, **kw):
                self.messages = self

            def create(self, **kwargs):
                blocked.set()
                release.wait(timeout=2)
                raise RuntimeError("should not reach")

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _HangingClient(),
        )
        d.start()
        try:
            with pytest.raises(TimeoutError):
                d.submit_turn("hi", wait_timeout=0.5)
            # Ensure the daemon thread did pick up the request so we
            # actually exercised the blocking path.
            assert blocked.wait(timeout=1)
        finally:
            release.set()
            d.cancel()
            d.stop(timeout=2)

    def test_cancel_cuts_in_flight_turn(self):
        """Cancel the daemon while the agent loop is mid-yield."""
        from test_agent_loop import _MockMessagesAPI, _MockResponse  # type: ignore
        from synapse.host import STATUS_CANCELLED
        from synapse.host.daemon import SynapseDaemon

        released = threading.Event()

        class _WaitingMessagesAPI(_MockMessagesAPI):
            def create(self, **kwargs):
                released.wait(timeout=2)
                return super().create(**kwargs)

        class _Client:
            def __init__(self):
                self.messages = _WaitingMessagesAPI([
                    _MockResponse(
                        [{"type": "text", "text": "ok"}],
                        stop_reason="end_turn",
                    )
                ])

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _Client(),
        )
        d.start()
        try:
            # Submit a turn from a helper thread so we can observe it cancel.
            result_holder: list = []

            def _runner():
                result_holder.append(d.submit_turn("hi", wait_timeout=5))

            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            # Give the daemon thread a moment to start processing.
            threading.Event().wait(0.1)
            d.cancel()
            released.set()  # let the mock create finally return
            t.join(timeout=3)
            assert result_holder, "submit_turn never returned"
            assert result_holder[0].status == STATUS_CANCELLED
        finally:
            d.stop(timeout=2)

    def test_stop_drains_unprocessed_requests(self):
        """Restart cycle: a stale request in the queue from a prior
        run must not fire into the new agent loop."""
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE
        from synapse.host.daemon import SynapseDaemon

        class _Client:
            def __init__(self):
                self.messages = self

            def create(self, **kwargs):
                return _MockResponse(
                    [{"type": "text", "text": "fresh"}], stop_reason="end_turn"
                )

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _Client(),
        )
        d.start()
        try:
            r1 = d.submit_turn("first", wait_timeout=5)
            assert r1.status == STATUS_COMPLETE
        finally:
            d.stop(timeout=2)

        # Enqueue a request AFTER stop(). Next start() must drain it.
        # (Direct internal access — testing the drain path is the point.)
        import queue as _q
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.cognitive.agent_loop import AgentTurnConfig
        from synapse.host.daemon import _AgentRequest
        reply_q: "_q.Queue[Any]" = _q.Queue(maxsize=1)
        d._request_queue.put(_AgentRequest(
            user_prompt="stale",
            config=AgentTurnConfig(),
            result_queue=reply_q,
        ))

        d.start()
        try:
            # The stale request must NOT have fired. Reply queue stays empty.
            with pytest.raises(_q.Empty):
                reply_q.get(timeout=0.5)
            # Fresh turn still works.
            r2 = d.submit_turn("second", wait_timeout=5)
            assert r2.status == STATUS_COMPLETE
        finally:
            d.stop(timeout=2)
