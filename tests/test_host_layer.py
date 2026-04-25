"""Host-layer tests (Sprint 3 Spike 2 Phase 1).

Covers the pieces of ``synapse.host.*`` that can be exercised without
an actual Houdini process. Tests that genuinely need ``hou`` /
``hdefereval`` at runtime go in the Crucible protocol in Phase 2.
"""

from __future__ import annotations

import os
import sys
import threading
import time
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
    """Daemon.submit_turn queues a request, returns a TurnHandle
    immediately, and the daemon thread posts the AgentTurnResult onto
    the handle when the agent loop completes. All tests inject a mock
    Anthropic client — no real API calls.

    Spike 2.4 migration: ``submit_turn`` no longer blocks on a result
    queue and no longer accepts ``wait_timeout``. The legacy synchronous
    shape is now ``submit_turn_blocking``, retained for tests and
    headless callers but forbidden on the Houdini main thread in GUI
    mode (it raises ``RuntimeError``).
    """

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

    # -- Migrated: §5.2 ------------------------------------------------

    def test_submit_turn_handle_completes_for_simple_end_turn(self):
        """Replaces the prior ``test_submit_turn_end_to_end``. Mock
        client emits ``end_turn`` immediately; ``handle.result(timeout=2)``
        returns ``AgentTurnResult`` with ``STATUS_COMPLETE`` and
        ``iterations == 1``."""
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE
        from synapse.host.turn_handle import TurnHandle

        d = self._make_daemon([
            _MockResponse(
                [{"type": "text", "text": "ok"}], stop_reason="end_turn"
            )
        ])
        d.start()
        try:
            handle = d.submit_turn("hi")
            assert isinstance(handle, TurnHandle)
            # submit_turn must NOT block — the handle is returned
            # before the daemon picks up the request. We don't pin
            # the timing here (already covered in
            # test_submit_turn_does_not_block_caller_thread); we pin
            # the shape and the eventual completion.
            result = handle.result(timeout=2)
            assert result.status == STATUS_COMPLETE
            assert result.iterations == 1
            assert handle.done() is True
            assert handle.cancelled() is False
        finally:
            d.stop(timeout=2)

    def test_submit_turn_handle_completes_for_max_iterations(self):
        """Mock client never emits ``end_turn``; the handle eventually
        completes with ``STATUS_MAX_ITERATIONS``. The agent loop only
        re-iterates on ``tool_use``, so we script tool_use responses
        that target a registered tool."""
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_MAX_ITERATIONS

        looping = [
            _MockResponse(
                [{
                    "type": "tool_use",
                    "id": f"tu-{i}",
                    "name": "echo",
                    "input": {"msg": "x"},
                }],
                stop_reason="tool_use",
            )
            for i in range(20)
        ]
        d = self._make_daemon(looping)
        d.start()
        try:
            d.dispatcher.register(
                "echo",
                lambda **kw: {"echoed": kw},
                schema={
                    "description": "echo",
                    "input_schema": {
                        "type": "object",
                        "properties": {"msg": {"type": "string"}},
                        "required": [],
                    },
                },
            )
            d.dispatcher.is_testing = True
            handle = d.submit_turn("hi", max_iterations=3)
            result = handle.result(timeout=3)
            assert result.status == STATUS_MAX_ITERATIONS
            assert result.iterations == 3
        finally:
            d.stop(timeout=2)

    def test_submit_turn_blocking_convenience_returns_result(self):
        """Legacy synchronous shape via ``submit_turn_blocking(prompt,
        wait_timeout=5)`` returns the same ``AgentTurnResult`` the
        handle would. Run from a helper thread to avoid the main-
        thread guard (we're in stock Python so the guard is a no-op,
        but emulating real usage is good hygiene)."""
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE

        d = self._make_daemon([
            _MockResponse(
                [{"type": "text", "text": "ok"}], stop_reason="end_turn"
            )
        ])
        d.start()
        try:
            result = d.submit_turn_blocking("hi", wait_timeout=5)
            assert result.status == STATUS_COMPLETE
            assert result.iterations == 1
        finally:
            d.stop(timeout=2)

    def test_submit_turn_blocking_timeout_surfaces_distinctly(self):
        """A hanging mock client causes ``submit_turn_blocking(
        wait_timeout=0.5)`` to raise ``TurnNotComplete`` (which IS-A
        ``TimeoutError``, so legacy ``except TimeoutError`` paths
        still catch it — pinned by both isinstance checks below)."""
        from synapse.host.daemon import SynapseDaemon
        from synapse.host.turn_handle import TurnNotComplete

        blocked = threading.Event()
        release = threading.Event()

        class _HangingClient:
            def __init__(self, *a, **kw):
                self.messages = self

            def create(self, **kwargs):
                blocked.set()
                release.wait(timeout=5)
                raise RuntimeError("should not reach")

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _HangingClient(),
        )
        d.start()
        try:
            with pytest.raises(TurnNotComplete) as exc_info:
                d.submit_turn_blocking("hi", wait_timeout=0.5)
            # Pin Q1 lock: TurnNotComplete IS-A TimeoutError.
            assert isinstance(exc_info.value, TimeoutError)
            # Ensure the daemon thread did pick up the request so we
            # actually exercised the blocking path.
            assert blocked.wait(timeout=1)
        finally:
            release.set()
            d.cancel()
            d.stop(timeout=2)

    def test_submit_turn_raises_when_daemon_not_running(self):
        """Pre-condition check on the new submit_turn signature: no
        ``wait_timeout`` parameter — the daemon-not-running guard
        fires before the request is queued."""
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            anthropic_client_factory=lambda k: MagicMock(),
        )
        with pytest.raises(DaemonBootError, match="running daemon"):
            d.submit_turn("hi")

    def test_submit_turn_blocking_raises_when_daemon_not_running(self):
        """Same pre-condition check on the blocking convenience."""
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            anthropic_client_factory=lambda k: MagicMock(),
        )
        with pytest.raises(DaemonBootError, match="running daemon"):
            d.submit_turn_blocking("hi", wait_timeout=0.1)


# ---------------------------------------------------------------------------
# Spike 2.4 §5.1 — Deadlock regression suite
# ---------------------------------------------------------------------------


class TestDaemonSubmitTurnDeadlockRegression:
    """The Spike 2.4 regression family — the deadlock that surfaced
    on 4/20 against graphical Houdini.

    The pre-2.4 ``submit_turn`` blocked the caller thread on a
    ``result_queue.get(timeout=...)``. In GUI Houdini the caller is
    the main thread, which is the same thread ``hdefereval`` needs
    free to run dispatched lambdas. Two-party reverse-wait: the main
    thread waited for a result the daemon thread couldn't produce
    (because the daemon was waiting for a tool dispatch the main
    thread couldn't pump).

    These tests close that surface in a CI-runnable shape: stock
    Python plus mock executors that simulate GUI semantics. The live
    graphical-Houdini repro is documented in the runbook (and marked
    ``live`` below)."""

    def _make_daemon_with_executor(self, executor, responses):
        """Build a daemon with a custom main_thread_executor and a
        scripted Anthropic mock."""
        from synapse.host.daemon import SynapseDaemon
        from test_agent_loop import _MockClient  # type: ignore

        def _factory(_api_key):
            return _MockClient(responses)

        return SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=executor,
            anthropic_client_factory=_factory,
        )

    def test_submit_turn_does_not_block_caller_thread(self):
        """§5.1 — After ``daemon.submit_turn(prompt)``, the calling
        thread returns immediately (well under 1s) with a TurnHandle,
        even with a mock executor that simulates ``hdefereval`` taking
        a long time on tool dispatch.

        Pre-2.4 this test deadlocks because the main thread was
        parked in result_queue.get(...). Post-2.4 the caller never
        blocks and the executor's slow path is irrelevant to
        submit_turn's return latency."""
        import time as _time
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host.turn_handle import TurnHandle

        slow_executor_called = threading.Event()

        def _slow_executor(fn, kwargs):
            slow_executor_called.set()
            _time.sleep(5.0)  # simulate hdefereval-stuck-behind-main-thread
            return fn(**kwargs)

        d = self._make_daemon_with_executor(
            _slow_executor,
            [_MockResponse(
                [{"type": "text", "text": "ok"}], stop_reason="end_turn"
            )],
        )
        d.start()
        try:
            t0 = _time.monotonic()
            handle = d.submit_turn("hi")
            elapsed = _time.monotonic() - t0
            # The CRITICAL assertion: submit_turn returned without
            # blocking on the slow executor.
            assert elapsed < 1.0, (
                f"submit_turn blocked for {elapsed:.2f}s — "
                "Spike 2.4 regression"
            )
            assert isinstance(handle, TurnHandle)
            assert handle.done() is False  # daemon hasn't completed yet
        finally:
            # Don't wait for the slow executor; cancel cuts the daemon.
            d.cancel()
            d.stop(timeout=8)

    def test_main_thread_can_pump_while_daemon_dispatches(self):
        """§5.1 — Caller thread is the one that "pumps" tool dispatches
        when the test's mock executor signals. Without 2.4's fix this
        test deadlocks: the main thread is parked in submit_turn and
        cannot service the pump.

        With 2.4's fix, submit_turn returns immediately, the caller
        thread is free to service the pump signal, and the handle
        completes once the dispatched lambda runs.
        """
        from test_agent_loop import _MockResponse  # type: ignore

        # The pump is a single-slot mailbox. The daemon-side executor
        # drops the (fn, kwargs) request into it; the main-thread
        # service loop picks it up, runs the lambda, and posts the
        # result back. Mimics hdefereval's submit-and-wait shape.
        pump_request: "list" = []
        pump_result: "list" = []
        pump_request_ready = threading.Event()
        pump_result_ready = threading.Event()

        def _gui_like_executor(fn, kwargs):
            """Daemon-thread side: enqueue work, wait for main thread."""
            pump_request.append((fn, kwargs))
            pump_request_ready.set()
            assert pump_result_ready.wait(timeout=5), "pump never serviced"
            return pump_result.pop(0)

        # Mock client: emits a single tool_use, then end_turn.
        responses = [
            _MockResponse(
                [
                    {
                        "type": "tool_use",
                        "id": "use-1",
                        "name": "synapse_inspect_stage",
                        "input": {"target_path": "/stage"},
                    }
                ],
                stop_reason="tool_use",
            ),
            _MockResponse(
                [{"type": "text", "text": "done"}], stop_reason="end_turn"
            ),
        ]
        d = self._make_daemon_with_executor(_gui_like_executor, responses)
        d.start()
        try:
            handle = d.submit_turn("inspect")
            # The main thread is FREE to pump — pre-2.4 it was parked
            # in submit_turn, and this assertion would never run.
            assert pump_request_ready.wait(timeout=5), (
                "daemon never asked for a pump dispatch"
            )
            fn, kwargs = pump_request[0]
            # Run the dispatched callable on the "main" (caller) thread,
            # then signal completion. This is the path that pre-2.4
            # was deadlocked.
            try:
                pump_result.append(fn(**kwargs))
            except Exception as exc:  # noqa: BLE001
                # Inspector might raise — but the test should still
                # complete. Re-raise as the dispatched return so the
                # daemon sees the failure.
                pump_result.append({"error": str(exc)})
            pump_result_ready.set()

            from synapse.host import STATUS_COMPLETE
            result = handle.result(timeout=5)
            # The handle completes; whether the inspector mock-tool
            # call succeeded or raised, the agent loop runs to
            # end_turn on the second response.
            assert result.status == STATUS_COMPLETE
        finally:
            d.cancel()
            d.stop(timeout=3)

    def test_crucible_full_turn_with_inspect_stage(self):
        """§5.1 — The 4/20 hostile turn that didn't run: full
        ``run_turn`` against a mock Anthropic client that emits a
        ``synapse_inspect_stage`` tool_use block, dispatcher routes
        through a mock main_thread_executor, handle completes within
        5s with ``STATUS_COMPLETE`` and ``len(tool_errors) == 0``."""
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE

        # Mock the inspector tool's underlying transport. The dispatcher
        # registered ``synapse_inspect_stage`` on daemon boot; when
        # called it imports synapse.inspector. Stub the whole import
        # chain so the dispatched lambda returns a sensible payload
        # without touching real Houdini.

        def _inspect_stage_stub(fn, kwargs):
            # The dispatcher passes `inspect_stage` (the cognitive
            # tool) as fn and the input as kwargs. We invoke the
            # tool directly but with a transport-level fake: the
            # tool calls synapse.inspector.synapse_inspect_stage,
            # which itself calls the registered transport. To keep
            # this test from importing the inspector module at all,
            # we short-circuit here and return a pre-baked payload
            # that satisfies the inspect_stage tool's contract.
            return {
                "schema_version": "1.0.0",
                "target_path": kwargs.get("target_path", "/stage"),
                "nodes": [],
            }

        # Two-step agent script: tool_use → tool_result → end_turn.
        responses = [
            _MockResponse(
                [
                    {
                        "type": "tool_use",
                        "id": "use-crucible-1",
                        "name": "synapse_inspect_stage",
                        "input": {"target_path": "/stage"},
                    }
                ],
                stop_reason="tool_use",
            ),
            _MockResponse(
                [{"type": "text", "text": "stage is empty"}],
                stop_reason="end_turn",
            ),
        ]
        d = self._make_daemon_with_executor(_inspect_stage_stub, responses)
        d.start()
        try:
            handle = d.submit_turn("inspect the stage please")
            result = handle.result(timeout=5)
            assert result.status == STATUS_COMPLETE
            assert len(result.tool_errors) == 0, (
                f"unexpected tool errors: {result.tool_errors!r}"
            )
            assert result.tool_calls_made == 1
            # 2 iterations: the tool_use round + the end_turn round.
            assert result.iterations == 2
        finally:
            d.stop(timeout=3)

    @pytest.mark.live
    def test_crucible_turn_runs_against_graphical_houdini(self):
        """§5.1 live — graphical-Houdini repro of the 4/20 hostile
        turn. Skipped in CI (requires Houdini 21.0.671 + Synapse
        WebSocket server). Run via the runbook step:

            export ANTHROPIC_API_KEY=sk-ant-...
            houdini21  # graphical session, not hython
            # in the Python shell:
            from synapse.host.daemon import SynapseDaemon
            d = SynapseDaemon()
            d.start()
            handle = d.submit_turn("inspect the stage please")
            # Poll from the panel UI's tick callback (NOT
            # handle.result(timeout=None) on the main thread).
            assert handle.done(), "deadlock — see Spike 2.4 design"

        This pytest body is intentionally a no-op: pytest collects
        the test, the ``live`` marker keeps it out of CI, and Joe's
        runbook step provides the actual verification."""
        pytest.skip("live: requires graphical Houdini 21.0.671")


# ---------------------------------------------------------------------------
# Spike 2.4 §5.3 — Concurrent submissions
# ---------------------------------------------------------------------------


class TestDaemonSubmitTurnConcurrent:
    """Submitting multiple turns rapidly: the daemon's single-thread
    agent loop processes them in order, but the caller is never
    blocked on the previous handle's completion."""

    def _make_daemon_with_responses(self, responses):
        from synapse.host.daemon import SynapseDaemon
        from test_agent_loop import _MockClient  # type: ignore

        def _factory(_key):
            return _MockClient(responses)

        return SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=_factory,
        )

    def test_two_handles_in_flight_no_head_of_line_blocking(self):
        """§5.3 — Submit turn A then turn B before A completes. The
        daemon processes them in order (single-thread agent loop
        semantics preserved), but the caller's submission of B does
        NOT block on A's completion."""
        import time as _time
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE

        # Two scripted responses, both end_turn. The first uses a
        # custom client that delays so we can observe overlap.
        from test_agent_loop import _MockMessagesAPI  # type: ignore

        a_started = threading.Event()
        a_release = threading.Event()

        class _DelayingMessagesAPI(_MockMessagesAPI):
            def __init__(self, script):
                super().__init__(script)
                self._call_count = 0

            def create(self, **kwargs):
                self._call_count += 1
                if self._call_count == 1:
                    a_started.set()
                    a_release.wait(timeout=3)
                return super().create(**kwargs)

        class _Client:
            def __init__(self):
                self.messages = _DelayingMessagesAPI([
                    _MockResponse(
                        [{"type": "text", "text": "A"}],
                        stop_reason="end_turn",
                    ),
                    _MockResponse(
                        [{"type": "text", "text": "B"}],
                        stop_reason="end_turn",
                    ),
                ])

        from synapse.host.daemon import SynapseDaemon
        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _Client(),
        )
        d.start()
        try:
            handle_a = d.submit_turn("A")
            # A is mid-flight; the caller submits B WITHOUT blocking.
            assert a_started.wait(timeout=2), "daemon never picked up A"
            t0 = _time.monotonic()
            handle_b = d.submit_turn("B")
            elapsed = _time.monotonic() - t0
            assert elapsed < 0.5, (
                f"submit_turn(B) blocked for {elapsed:.2f}s while A "
                "was in flight — Spike 2.4 head-of-line regression"
            )
            assert handle_a.done() is False
            assert handle_b.done() is False

            # Now release A; both should complete in submission order.
            a_release.set()
            ra = handle_a.result(timeout=3)
            rb = handle_b.result(timeout=3)
            assert ra.status == STATUS_COMPLETE
            assert rb.status == STATUS_COMPLETE
        finally:
            d.cancel()
            d.stop(timeout=2)

    def test_handle_done_polling_safe_under_concurrency(self):
        """§5.3 — Caller thread polls ``handle.done()`` 1000× from a
        tight loop while the daemon is processing the turn. No race
        on the underlying Event; final value is True and the polling
        completes cleanly."""
        from test_agent_loop import _MockResponse  # type: ignore

        d = self._make_daemon_with_responses([
            _MockResponse(
                [{"type": "text", "text": "ok"}], stop_reason="end_turn"
            )
        ])
        d.start()
        try:
            handle = d.submit_turn("poll-stress")
            # Tight poll — no sleep. If done() races, we'd see
            # observed True followed by False. The Event-based
            # implementation guarantees monotonic transition.
            observed: list = []
            for _ in range(1000):
                observed.append(handle.done())
                if observed[-1]:
                    break
            # If we exited early on True, the rest is implicit. If
            # we never saw True, the daemon is too slow — wait it
            # out and verify done() now flips.
            if observed[-1] is False:
                handle.result(timeout=3)  # block until done
                observed.append(handle.done())

            assert observed[-1] is True
            # Monotonicity: once True, stays True.
            first_true_idx = next(
                i for i, v in enumerate(observed) if v is True
            )
            assert all(v is True for v in observed[first_true_idx:])
        finally:
            d.stop(timeout=2)


# ---------------------------------------------------------------------------
# Spike 2.4 §5.4 — Tool error envelope preservation
# ---------------------------------------------------------------------------


class TestDaemonSubmitTurnToolErrors:
    """``AgentToolError`` envelope shape is byte-identical pre- and
    post-2.4. The handle is a transport for the result, not a
    transformer of its content."""

    def test_tool_error_envelope_preserved_through_handle(self):
        """§5.4 — A tool raises a Houdini-style exception; the
        Dispatcher wraps it as ``AgentToolError``; the agent loop
        records it in ``result.tool_errors``; the handle delivers it
        unchanged."""
        from synapse.cognitive.dispatcher import AgentToolError, Dispatcher
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE
        from synapse.host.daemon import SynapseDaemon
        from test_agent_loop import _MockClient  # type: ignore

        # Build a custom dispatcher with our hostile tool.
        class _FakeObjectWasDeleted(Exception):
            pass

        def _broken_tool(**_kwargs):
            raise _FakeObjectWasDeleted("/obj/geo1 has been removed")

        responses = [
            _MockResponse(
                [
                    {
                        "type": "tool_use",
                        "id": "use-broken-1",
                        "name": "broken_tool",
                        "input": {},
                    }
                ],
                stop_reason="tool_use",
            ),
            _MockResponse(
                [{"type": "text", "text": "noted"}],
                stop_reason="end_turn",
            ),
        ]

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _MockClient(responses),
        )
        d.start()
        try:
            # Inject the broken tool AFTER start so the dispatcher
            # exists. is_testing=True bypasses main_thread_executor.
            d.dispatcher.register(
                "broken_tool",
                _broken_tool,
                schema={
                    "description": "raises a hou-style ObjectWasDeleted",
                    "input_schema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            )
            d.dispatcher.is_testing = True

            handle = d.submit_turn("trigger broken tool")
            result = handle.result(timeout=3)
            assert result.status == STATUS_COMPLETE
            assert len(result.tool_errors) == 1
            err = result.tool_errors[0]
            # Envelope shape — byte-identical to pre-2.4.
            assert isinstance(err, AgentToolError)
            assert err.tool_name == "broken_tool"
            assert err.error_type == "_FakeObjectWasDeleted"
            assert "/obj/geo1 has been removed" in err.error_message
            assert err.traceback_str  # non-empty
            # to_dict() is the JSON-RPC marshalling shape.
            payload = err.to_dict()
            assert payload["agent_tool_error"] is True
            assert payload["tool_name"] == "broken_tool"
            assert payload["error_type"] == "_FakeObjectWasDeleted"
        finally:
            d.stop(timeout=2)

    def test_unknown_tool_via_handle_returns_agent_tool_error(self):
        """§5.4 — Agent emits ``tool_use`` for a tool not registered.
        Same ``AgentToolError(error_type="ToolNotRegistered")`` arrives
        in ``result.tool_errors``."""
        from synapse.cognitive.dispatcher import AgentToolError
        from test_agent_loop import _MockResponse, _MockClient  # type: ignore
        from synapse.host import STATUS_COMPLETE
        from synapse.host.daemon import SynapseDaemon

        responses = [
            _MockResponse(
                [
                    {
                        "type": "tool_use",
                        "id": "use-unknown-1",
                        "name": "tool_that_does_not_exist",
                        "input": {},
                    }
                ],
                stop_reason="tool_use",
            ),
            _MockResponse(
                [{"type": "text", "text": "ack"}],
                stop_reason="end_turn",
            ),
        ]
        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _MockClient(responses),
        )
        d.start()
        try:
            handle = d.submit_turn("call ghost tool")
            result = handle.result(timeout=3)
            assert result.status == STATUS_COMPLETE
            assert len(result.tool_errors) == 1
            err = result.tool_errors[0]
            assert isinstance(err, AgentToolError)
            assert err.error_type == "ToolNotRegistered"
            assert err.tool_name == "tool_that_does_not_exist"
            # ToolNotRegistered carries no upstream traceback.
            assert err.traceback_str == ""
        finally:
            d.stop(timeout=2)


# ---------------------------------------------------------------------------
# Spike 2.4 §5.5 — Daemon shutdown mid-flight
# ---------------------------------------------------------------------------


class TestDaemonStopMidFlight:
    """Stop semantics: in-flight turns get cancelled cleanly; queued
    requests have their handles cancelled so callers don't hang
    forever; no orphaned threads."""

    def test_stop_during_in_flight_turn_cancels_handle(self):
        """§5.5 — Submit a turn whose mock client blocks on a Event
        the test owns. Call ``daemon.stop(timeout=2)`` while the
        dispatch is mid-flight. The cancel_event propagates into
        run_turn (cancel check #2 / #3); the handle observes
        ``STATUS_CANCELLED`` via ``result()``."""
        import threading as _t
        from test_agent_loop import (  # type: ignore
            _MockMessagesAPI,
            _MockResponse,
        )
        from synapse.host import STATUS_CANCELLED
        from synapse.host.daemon import SynapseDaemon

        released = _t.Event()

        class _WaitingMessagesAPI(_MockMessagesAPI):
            def create(self, **kwargs):
                released.wait(timeout=3)
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
        baseline_threads = set(t.ident for t in threading.enumerate())
        d.start()
        try:
            handle = d.submit_turn("hi")
            # Give the daemon thread a moment to enter create().
            time.sleep(0.1)
            d.cancel()
            released.set()
            result = handle.result(timeout=3)
            assert result.status == STATUS_CANCELLED
        finally:
            d.stop(timeout=2)

        # No orphaned threads after stop. Allow a brief settle window
        # — the daemon thread is daemon=True and exits when its run
        # method returns.
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            current = set(t.ident for t in threading.enumerate())
            leaked = current - baseline_threads
            if not leaked:
                return
            time.sleep(0.05)
        # Final check — fail loudly with diagnostic.
        current = set(t.ident for t in threading.enumerate())
        leaked = current - baseline_threads
        leaked_names = [
            t.name for t in threading.enumerate() if t.ident in leaked
        ]
        assert not leaked, (
            f"orphaned threads after stop: {leaked_names!r}"
        )

    def test_stop_drains_pending_handles_as_cancelled(self):
        """§5.5 — Submit two turns rapidly; daemon picks up the first,
        the second sits in queue. Call ``stop()`` before the first
        completes. Both handles transition: first to STATUS_CANCELLED
        via in-flight cancel, second to ``cancelled() == True`` via
        queue drain. Neither handle is left dangling.

        Implementation contract: ``SynapseDaemon._drain_request_queue``
        is documented to be called "on ``stop()`` so callers blocked
        in ``handle.result(...)`` see ``TurnCancelled`` instead of
        hanging forever". This test pins that contract.

        Note on race tolerance: the first request may already have
        been popped off the queue by the time stop() fires (the
        daemon's poll loop runs every 250ms). We assert the
        invariant — both handles reach a terminal state — without
        pinning which path each took."""
        from test_agent_loop import (  # type: ignore
            _MockMessagesAPI,
            _MockResponse,
        )
        from synapse.host import STATUS_CANCELLED
        from synapse.host.daemon import SynapseDaemon
        from synapse.host.turn_handle import TurnCancelled

        released = threading.Event()

        class _WaitingMessagesAPI(_MockMessagesAPI):
            def create(self, **kwargs):
                released.wait(timeout=3)
                return super().create(**kwargs)

        class _Client:
            def __init__(self):
                self.messages = _WaitingMessagesAPI([
                    _MockResponse(
                        [{"type": "text", "text": "first"}],
                        stop_reason="end_turn",
                    ),
                    _MockResponse(
                        [{"type": "text", "text": "second"}],
                        stop_reason="end_turn",
                    ),
                ])

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _Client(),
        )
        d.start()
        try:
            h1 = d.submit_turn("one")
            h2 = d.submit_turn("two")
            # Give the daemon a moment to pop h1.
            time.sleep(0.1)
            # stop() drains anything still queued (h2 in this case)
            # and cancels in-flight (h1).
            d.cancel()
            released.set()
            d.stop(timeout=3)

            # Both handles must reach a terminal state — neither
            # hangs on result().
            assert h1.done() is True, (
                "h1 (in-flight at stop) is still pending — "
                "daemon cancel didn't propagate to handle"
            )
            assert h2.done() is True, (
                "h2 (queued behind h1 at stop) is still pending — "
                "stop() must drain pending handles. See "
                "_drain_request_queue docstring: 'Called on start() "
                "before the thread takes over... and on stop() so "
                "callers blocked in handle.result(...) see "
                "TurnCancelled instead of hanging forever.'"
            )

            # h1 either completed normally (raced past the cancel)
            # or was cancelled. We accept both. h2 must have been
            # drained (cancelled) since the daemon never reached it.
            try:
                r1 = h1.result(timeout=0.5)
                assert r1.status in (STATUS_CANCELLED, "complete")
            except TurnCancelled:
                pass  # also acceptable

            # h2 is the deterministic case: it was queued behind the
            # blocking h1 and never had a chance to run before stop.
            assert h2.cancelled() is True
            with pytest.raises(TurnCancelled):
                h2.result(timeout=0.5)
        finally:
            # idempotent stop()
            d.stop(timeout=1)

    def test_drained_handle_raises_turn_cancelled_on_result(self):
        """§5.5 — After ``stop()`` drains an unprocessed request,
        calling ``handle.result(timeout=2)`` raises ``TurnCancelled``.
        Replaces the prior dangling-queue silent-loss behavior.

        We exercise this directly through ``_drain_request_queue``
        rather than racing the daemon: the contract is that the
        drain method cancels each handle, regardless of why it's
        being called."""
        from synapse.cognitive.agent_loop import AgentTurnConfig
        from synapse.host.daemon import SynapseDaemon, _AgentRequest
        from synapse.host.turn_handle import TurnCancelled, TurnHandle

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: MagicMock(),
        )
        # Stuff a handle into the queue without starting the daemon.
        handle = TurnHandle()
        d._request_queue.put(_AgentRequest(
            user_prompt="orphan",
            config=AgentTurnConfig(),
            handle=handle,
        ))
        # Drain — handle should be cancelled.
        d._drain_request_queue()
        assert handle.cancelled() is True
        with pytest.raises(TurnCancelled):
            handle.result(timeout=2)

    def test_stop_drains_unprocessed_requests_across_restart(self):
        """Restart cycle: a stale request in the queue from a prior
        run must not fire into the new agent loop, and its handle
        must be cancelled (no silent loss).

        Migrated from the pre-2.4 ``test_stop_drains_unprocessed_requests``
        which relied on result_queue.get(timeout=0.5) to assert
        non-firing. Post-2.4 we assert via the handle's cancelled
        state, which is the structural guarantee."""
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.cognitive.agent_loop import AgentTurnConfig
        from synapse.host import STATUS_COMPLETE
        from synapse.host.daemon import SynapseDaemon, _AgentRequest
        from synapse.host.turn_handle import TurnCancelled, TurnHandle

        class _Client:
            def __init__(self):
                self.messages = self

            def create(self, **kwargs):
                return _MockResponse(
                    [{"type": "text", "text": "fresh"}],
                    stop_reason="end_turn",
                )

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _Client(),
        )
        d.start()
        try:
            h1 = d.submit_turn("first")
            r1 = h1.result(timeout=3)
            assert r1.status == STATUS_COMPLETE
        finally:
            d.stop(timeout=2)

        # Enqueue a request between runs (direct internal access —
        # testing the drain path is the point).
        stale_handle = TurnHandle()
        d._request_queue.put(_AgentRequest(
            user_prompt="stale",
            config=AgentTurnConfig(),
            handle=stale_handle,
        ))
        assert stale_handle.cancelled() is False  # still pending

        d.start()
        try:
            # The stale request must NOT have fired. Its handle was
            # cancelled by start()'s drain.
            assert stale_handle.cancelled() is True
            with pytest.raises(TurnCancelled):
                stale_handle.result(timeout=0.5)

            # Fresh turn still works.
            h2 = d.submit_turn("second")
            r2 = h2.result(timeout=3)
            assert r2.status == STATUS_COMPLETE
        finally:
            d.stop(timeout=2)

    def test_no_orphaned_main_thread_executor_workers(self):
        """§5.5 — After 10 submit→complete cycles, ``threading.enumerate()``
        shows no leaked worker threads. Pins the executor's
        cleanup contract."""
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE
        from synapse.host.daemon import SynapseDaemon

        # Build a fresh client per turn so the script never runs out.
        responses_list = [
            [_MockResponse(
                [{"type": "text", "text": f"r{i}"}],
                stop_reason="end_turn",
            )]
            for i in range(15)
        ]

        from test_agent_loop import _MockClient  # type: ignore
        consumed = [0]

        def _factory(_key):
            i = consumed[0]
            consumed[0] += 1
            return _MockClient(responses_list[i])

        baseline = set(t.ident for t in threading.enumerate())

        for _ in range(10):
            d = SynapseDaemon(
                api_key="test",
                boot_gate=False,
                main_thread_executor=lambda fn, kwargs: fn(**kwargs),
                anthropic_client_factory=_factory,
            )
            d.start()
            try:
                handle = d.submit_turn("ping")
                result = handle.result(timeout=3)
                assert result.status == STATUS_COMPLETE
            finally:
                d.stop(timeout=2)

        # Settle window for daemon=True threads to wind down.
        deadline = time.monotonic() + 2.0
        leaked: set = set()
        while time.monotonic() < deadline:
            current = set(t.ident for t in threading.enumerate())
            leaked = current - baseline
            if not leaked:
                break
            time.sleep(0.05)

        leaked_names = [
            t.name for t in threading.enumerate() if t.ident in leaked
        ]
        assert not leaked, (
            f"orphaned threads after 10 cycles: {leaked_names!r}"
        )


# ---------------------------------------------------------------------------
# Spike 2.4 §5.7 — Cancel semantics
# ---------------------------------------------------------------------------


class TestDaemonCancelSemantics:
    """``daemon.cancel()`` and ``handle.cancel()`` are intentionally
    distinct. ``daemon.cancel()`` stops the daemon (all in-flight
    handles cascade via the agent loop's cooperative cancel checks).
    ``handle.cancel()`` is local to one waiter — surfaces
    TurnCancelled to anyone calling ``result()`` on that handle but
    does NOT signal the daemon."""

    def test_daemon_cancel_propagates_to_in_flight_handle(self):
        """§5.7 — daemon.cancel() mid-turn → handle completes with
        STATUS_CANCELLED via the agent loop's cancel checks. Confirms
        2.4 didn't break the cooperative-cancel contract from
        Spike 2.2."""
        from test_agent_loop import (  # type: ignore
            _MockMessagesAPI,
            _MockResponse,
        )
        from synapse.host import STATUS_CANCELLED
        from synapse.host.daemon import SynapseDaemon

        released = threading.Event()

        class _WaitingMessagesAPI(_MockMessagesAPI):
            def create(self, **kwargs):
                released.wait(timeout=3)
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
            handle = d.submit_turn("hi")
            time.sleep(0.1)  # let daemon enter create()
            d.cancel()
            released.set()
            result = handle.result(timeout=3)
            assert result.status == STATUS_CANCELLED
            # handle.cancelled() is False — daemon.cancel() doesn't
            # mark the handle as cancelled; it makes the agent loop
            # return STATUS_CANCELLED, which is posted via
            # _set_result. Two distinct signals.
            assert handle.cancelled() is False
        finally:
            d.stop(timeout=2)

    def test_handle_cancel_does_not_stop_daemon(self):
        """§5.7 — ``handle.cancel()`` only affects waiters on that one
        handle. The daemon thread continues processing the request to
        completion, then drops the result on the cancelled handle.
        Other handles remain healthy."""
        from test_agent_loop import (  # type: ignore
            _MockMessagesAPI,
            _MockResponse,
        )
        from synapse.host import STATUS_COMPLETE
        from synapse.host.daemon import SynapseDaemon
        from synapse.host.turn_handle import TurnCancelled

        a_in_flight = threading.Event()
        a_release = threading.Event()

        class _DelayingMessagesAPI(_MockMessagesAPI):
            def __init__(self, script):
                super().__init__(script)
                self._call_count = 0

            def create(self, **kwargs):
                self._call_count += 1
                if self._call_count == 1:
                    a_in_flight.set()
                    a_release.wait(timeout=3)
                return super().create(**kwargs)

        class _Client:
            def __init__(self):
                self.messages = _DelayingMessagesAPI([
                    _MockResponse(
                        [{"type": "text", "text": "A"}],
                        stop_reason="end_turn",
                    ),
                    _MockResponse(
                        [{"type": "text", "text": "B"}],
                        stop_reason="end_turn",
                    ),
                ])

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=lambda fn, kwargs: fn(**kwargs),
            anthropic_client_factory=lambda k: _Client(),
        )
        d.start()
        try:
            handle_a = d.submit_turn("A")
            assert a_in_flight.wait(timeout=2)
            # Cancel handle_a — but daemon is still happily working
            # on it (daemon.cancel was NOT called).
            assert handle_a.cancel() is True
            assert handle_a.cancelled() is True
            # Waiters on handle_a unblock with TurnCancelled.
            with pytest.raises(TurnCancelled):
                handle_a.result(timeout=0.5)

            # Daemon hasn't been stopped — it's still processing A.
            assert d.is_running

            # Submit handle_b; it must work normally.
            handle_b = d.submit_turn("B")
            # Now release A. Daemon completes A (the result is
            # silently dropped on the cancelled handle), then picks
            # up B and runs it to completion.
            a_release.set()
            r_b = handle_b.result(timeout=3)
            assert r_b.status == STATUS_COMPLETE
            # Handle A stays cancelled — the daemon's late post is
            # dropped, not registered.
            assert handle_a.cancelled() is True
        finally:
            d.cancel()
            d.stop(timeout=2)


# ---------------------------------------------------------------------------
# Spike 2.4 §5.8 — Hostile Crucible (executor shim)
# ---------------------------------------------------------------------------


class TestDaemonHostileCrucible:
    """The 4/20 hostile turn re-run: full multi-iteration ``run_turn``
    with a tool_use → tool_result → end_turn script, against a
    main_thread_executor shim that simulates GUI Houdini's hdefereval
    semantics (caller-thread serviced pump). Handle completes within
    10s, no MainThreadTimeoutError, no 30s hang."""

    def test_hostile_crucible_turn_passes_against_live_executor_shim(self):
        """§5.8 — The headless analog of the Crucible turn that didn't
        run end-of-day 4/20. Multi-iteration: the agent emits two
        tool_use blocks (different inputs) before finishing.

        The executor shim simulates ``hdefereval`` semantics: the
        daemon thread queues work onto an inbox queue and waits on a
        per-dispatch result queue (mirroring the request/response
        pair ``hdefereval.executeInMainThreadWithResult`` produces).
        The test thread services the inbox (just like the main
        thread services Qt events in graphical Houdini).

        Pre-2.4, the test thread would be parked in submit_turn and
        could not service the inbox → 30s MainThreadTimeoutError per
        dispatch. Post-2.4, submit_turn returns immediately, the test
        thread is free to service the inbox, the dispatched lambdas
        run, the agent loop completes."""
        import queue as _q
        import time as _time
        from test_agent_loop import _MockResponse  # type: ignore
        from synapse.host import STATUS_COMPLETE

        # Each dispatch is its own (request, reply) pair. The reply
        # queue is per-dispatch so two concurrent dispatches don't
        # collide (the agent loop is sequential, but this shape is
        # closer to what hdefereval actually does).
        inbox: "_q.Queue" = _q.Queue()

        def _gui_executor(fn, kwargs):
            """Daemon-side: enqueue (fn, kwargs, reply_q), wait reply."""
            reply: "_q.Queue" = _q.Queue(maxsize=1)
            inbox.put((fn, kwargs, reply))
            try:
                outcome = reply.get(timeout=10)
            except _q.Empty:  # pragma: no cover — fail loudly
                raise AssertionError(
                    "executor shim never serviced — 4/20 deadlock surface"
                )
            kind, payload = outcome
            if kind == "ok":
                return payload
            raise payload  # propagate exception

        responses = [
            _MockResponse(
                [
                    {
                        "type": "tool_use",
                        "id": "use-h-1",
                        "name": "synapse_inspect_stage",
                        "input": {"target_path": "/stage"},
                    }
                ],
                stop_reason="tool_use",
            ),
            _MockResponse(
                [
                    {
                        "type": "tool_use",
                        "id": "use-h-2",
                        "name": "synapse_inspect_stage",
                        "input": {"target_path": "/obj"},
                    }
                ],
                stop_reason="tool_use",
            ),
            _MockResponse(
                [{"type": "text", "text": "scene mapped"}],
                stop_reason="end_turn",
            ),
        ]

        from synapse.host.daemon import SynapseDaemon
        from test_agent_loop import _MockClient  # type: ignore

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            main_thread_executor=_gui_executor,
            anthropic_client_factory=lambda k: _MockClient(responses),
        )
        d.start()

        # Pump service runs on this (the test) thread. Pre-2.4 this
        # thread would be blocked in submit_turn → no pump → deadlock.
        try:
            handle = d.submit_turn("inspect everywhere")
            t0 = _time.monotonic()
            while not handle.done():
                try:
                    fn, kwargs, reply = inbox.get(timeout=0.1)
                except _q.Empty:
                    if _time.monotonic() - t0 > 10:
                        pytest.fail(
                            "hostile turn took >10s — deadlock surface"
                        )
                    continue
                # Dispatch on the test thread (the "main" thread in
                # this simulation). For the inspect_stage tool, return
                # a synthetic payload — the cognitive tool would
                # otherwise call into the real inspector, which
                # requires a transport.
                try:
                    payload = {
                        "schema_version": "1.0.0",
                        "target_path": kwargs.get(
                            "target_path", "/stage"
                        ),
                        "nodes": [],
                    }
                    reply.put(("ok", payload))
                except BaseException as exc:  # noqa: BLE001
                    reply.put(("err", exc))

            elapsed = _time.monotonic() - t0
            result = handle.result(timeout=1)
            assert result.status == STATUS_COMPLETE, (
                f"hostile turn failed: {result.status} / {result.error!r}"
            )
            assert result.tool_errors == []
            assert result.tool_calls_made == 2
            assert result.iterations == 3
            # 4/20 symptom: ANY 30s hang. Our budget here is 10s;
            # in practice this runs in well under 1s.
            assert elapsed < 10, (
                f"hostile turn took {elapsed:.1f}s — 4/20 regression"
            )
        finally:
            d.cancel()
            d.stop(timeout=3)


# ---------------------------------------------------------------------------
# Spike 2.4 — submit_turn_blocking main-thread guard
# ---------------------------------------------------------------------------


class TestDaemonSubmitTurnBlockingGuard:
    """``submit_turn_blocking`` raises ``RuntimeError`` when called
    from the Houdini main thread in GUI mode (Q2 lock per
    orchestrator). Stock Python: guard is a no-op (no ``hou``).
    Headless: guard is a no-op (single-threaded by design).
    GUI: hard fail (would deadlock)."""

    def test_blocking_guard_noop_in_stock_python(self, monkeypatch):
        """No ``hou`` import → guard short-circuits; the real call
        proceeds. We test via daemon-not-running so the call still
        raises (DaemonBootError) but for the right reason."""
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        monkeypatch.setitem(sys.modules, "hou", None)
        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            anthropic_client_factory=lambda k: MagicMock(),
        )
        # Daemon not started — should raise DaemonBootError, NOT
        # RuntimeError from the guard.
        with pytest.raises(DaemonBootError):
            d.submit_turn_blocking("hi", wait_timeout=0.1)

    def test_blocking_guard_noop_in_headless_houdini(self, monkeypatch):
        """``hou.isUIAvailable() == False`` → guard short-circuits;
        single-threaded by design, blocking is safe."""
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: False  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            anthropic_client_factory=lambda k: MagicMock(),
        )
        # Should fall through to DaemonBootError, NOT raise
        # RuntimeError from the guard.
        with pytest.raises(DaemonBootError):
            d.submit_turn_blocking("hi", wait_timeout=0.1)

    def test_blocking_guard_raises_in_gui_main_thread(self, monkeypatch):
        """``hou.isUIAvailable() == True`` AND on the main thread →
        RuntimeError BEFORE submit_turn fires. This is the structural
        steering wheel that prevents accidental re-introduction of
        the Spike 2.4 deadlock."""
        from synapse.host.daemon import SynapseDaemon

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: True  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            anthropic_client_factory=lambda k: MagicMock(),
        )
        # We're on the test main thread; the guard fires.
        with pytest.raises(RuntimeError, match="main thread"):
            d.submit_turn_blocking("hi", wait_timeout=0.1)

    def test_blocking_guard_allows_non_main_thread_in_gui(self, monkeypatch):
        """``hou.isUIAvailable() == True`` but caller is on a worker
        thread → guard short-circuits; blocking is safe because the
        main thread is free to service hdefereval."""
        from synapse.host.daemon import DaemonBootError, SynapseDaemon

        fake_hou = types.ModuleType("hou")
        fake_hou.isUIAvailable = lambda: True  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "hou", fake_hou)

        d = SynapseDaemon(
            api_key="test",
            boot_gate=False,
            anthropic_client_factory=lambda k: MagicMock(),
        )
        observed: list = []

        def _runner():
            try:
                d.submit_turn_blocking("hi", wait_timeout=0.1)
            except BaseException as exc:  # noqa: BLE001
                observed.append(exc)

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join(timeout=2)
        assert observed, "worker thread never returned"
        # Guard short-circuits; we get DaemonBootError because the
        # daemon isn't started, NOT RuntimeError from the guard.
        assert isinstance(observed[0], DaemonBootError)
