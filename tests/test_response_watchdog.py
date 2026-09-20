"""Panel response watchdog (BP8-WATCHDOG).

A hung turn -- the artist sends, the server never replies -- used to spin the
typing indicator forever with no way back: ``_waiting_for_response`` was armed
in ``_send_message`` and cleared only by a reply or a failed send. A dropped
socket or a silent server hang left it stuck.

These tests pin the fix: a single-shot ``QTimer`` armed on send, stopped the
moment the wait ends through the one shared ``_clear_waiting_state`` teardown,
and on fire it clears the waiting state and appends ONE "send again" line.

TWO LAYERS
----------
* Layer 1 (always runs, even under stock CPython): the panel's control flow is
  driven against a hand-injected mock timer -- arm on send, stop on reply /
  disconnect / connection-error / failed-send, and on fire clear + one line.
  The timer is a ``MagicMock`` so ``start``/``stop`` are assertable; firing is
  the test driving the slot the timeout is wired to (a fake clock).
* Layer 2 (runs only under a real PySide, i.e. hython): a REAL single-shot
  ``QTimer`` is built, wired, and actually fired by spinning the event loop --
  runtime truth that the wiring fires and that a real ``stop()`` prevents it.
  It ``skip``s under the MagicMock stub (skip != pass).
"""

import sys
import time
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Headless harness: stub hou + hdefereval, and make sure SOME PySide (real or a
# MagicMock stub) is resident so ``chat_panel`` imports without a display.
# Mirrors tests/test_chat_panel.py so this file also runs standalone.
# ---------------------------------------------------------------------------
if "hou" not in sys.modules:
    _mock_hou = types.ModuleType("hou")
    _mock_hou.selectedNodes = MagicMock(return_value=[])
    _mock_hou.node = MagicMock(return_value=None)
    _mock_hou.hipFile = MagicMock()
    _mock_hou.hipFile.path = MagicMock(return_value="/tmp/untitled.hip")
    _mock_hou.ui = MagicMock()
    sys.modules["hou"] = _mock_hou

if "hdefereval" not in sys.modules:
    _mock_hdefereval = types.ModuleType("hdefereval")
    _mock_hdefereval.executeInMainThreadWithResult = lambda fn: fn()
    _mock_hdefereval.executeDeferred = lambda fn: fn()
    sys.modules["hdefereval"] = _mock_hdefereval

try:
    from PySide6 import QtWidgets, QtCore  # noqa: F401
except Exception:  # noqa: BLE001 - any import failure means "no real Qt here"
    try:
        from PySide2 import QtWidgets, QtCore  # noqa: F401
    except Exception:  # noqa: BLE001
        # Minimal MagicMock PySide6 so chat_panel imports; QTimer is the class
        # MagicMock so ``QTimer(parent)`` yields a recordable mock instance.
        _m_core = MagicMock()
        _m_core.Signal = lambda *a, **k: MagicMock()
        _m_core.Slot = lambda *a, **k: (lambda fn: fn)
        _m_core.QTimer = MagicMock
        _m_ps = MagicMock()
        _m_ps.QtWidgets = MagicMock()
        _m_ps.QtCore = _m_core
        _m_ps.QtGui = MagicMock()
        sys.modules["PySide6"] = _m_ps
        sys.modules["PySide6.QtWidgets"] = _m_ps.QtWidgets
        sys.modules["PySide6.QtCore"] = _m_core
        sys.modules["PySide6.QtGui"] = _m_ps.QtGui

import os
_python_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"
)
if _python_dir not in sys.path:
    sys.path.insert(0, _python_dir)

from synapse.panel.chat_panel import (  # noqa: E402
    NO_RESPONSE_LINE,
    WATCHDOG_TIMEOUT_MS,
    SynapseChatPanel,
)


# ---------------------------------------------------------------------------
# Layer 1 helpers
# ---------------------------------------------------------------------------
def _panel_with_mocks():
    """A panel wired for the send path with a mock watchdog and mock widgets.

    No ``createInterface`` -- init only, then hand-set the collaborators the
    send / teardown paths touch, exactly like tests/test_chat_panel.py does.
    """
    p = SynapseChatPanel()
    p._chat = MagicMock()
    p._input = MagicMock()
    p._input.toPlainText.return_value = "scatter rocks on terrain"
    p._bridge = MagicMock()
    p._bridge.connected = True
    p._bridge.send_command.return_value = True  # a normal, accepted send
    p._response_watchdog = MagicMock()          # the fake clock
    # Connection-bar widgets, so _on_status_changed can run:
    p._context_chips = MagicMock()
    p._conn_btn = MagicMock()
    p._conn_dot = MagicMock()
    p._conn_label = MagicMock()
    # Pretend context is fresh, so the send path never fires an off-main gather.
    p._last_context = {}
    p._last_context_time = time.time() * 1000
    return p


def test_budget_is_slow_op_plus_margin_named_not_literal():
    """The watchdog budget is the 30 s server slow-op budget plus a margin,
    named -- never a call-site literal (BP8-WATCHDOG T1).

    proved_it_bites: change ``WATCHDOG_TIMEOUT_MS`` to <= 30000 (drop the
    margin) and this reddens.
    """
    assert WATCHDOG_TIMEOUT_MS > 30000
    assert WATCHDOG_TIMEOUT_MS == 35000


def test_watchdog_hang_clears_state_and_shows_one_line():
    """Send, never respond, fire the watchdog: waiting clears, typing hides,
    exactly one system line appears (BP8-WATCHDOG T1 / acceptance 1).

    proved_it_bites: delete ``append_system_message(NO_RESPONSE_LINE)`` from
    ``_on_response_timeout`` and the single-line assertion reddens (0 calls);
    delete the ``start()`` arm in ``_send_message`` and the arm assertion
    reddens.
    """
    p = _panel_with_mocks()

    p._send_message()
    assert p._waiting_for_response is True
    p._response_watchdog.start.assert_called_once()   # armed on send

    # Ignore any lines the send path itself produced; isolate the watchdog's.
    p._chat.append_system_message.reset_mock()
    p._chat.hide_typing_indicator.reset_mock()

    # Drive the fake clock: fire the slot the timeout is wired to.
    p._on_response_timeout()

    assert p._waiting_for_response is False
    p._chat.hide_typing_indicator.assert_called_once()
    p._chat.append_system_message.assert_called_once_with(NO_RESPONSE_LINE)


def test_delivered_response_stops_watchdog_and_no_late_line():
    """A delivered reply stops the watchdog, so no late 'no response' line can
    ever appear (BP8-WATCHDOG T1 / acceptance 2).

    proved_it_bites: delete the timer stop on the reply path (remove
    ``self._response_watchdog.stop()`` from ``_clear_waiting_state`` or stop
    ``_on_response`` calling it) and ``stop.assert_called_once`` reddens --
    the exact mutation the crucible authors.
    """
    p = _panel_with_mocks()

    p._send_message()
    p._response_watchdog.start.assert_called_once()
    p._chat.append_system_message.reset_mock()

    p._on_response({"response": "done", "tier": "recipe", "commands": []})

    p._response_watchdog.stop.assert_called_once()    # reply stopped it
    assert p._waiting_for_response is False
    # The watchdog line must never appear on a turn that got a reply.
    for call in p._chat.append_system_message.call_args_list:
        assert not (call.args and call.args[0] == NO_RESPONSE_LINE)


def test_connection_error_clears_waiting_via_shared_helper():
    """A connection error clears the waiting state through the one shared
    helper (BP8-WATCHDOG T2 / acceptance 3).

    proved_it_bites: remove ``self._clear_waiting_state()`` from
    ``_on_connection_error`` and the waiting/stop assertions redden.
    """
    p = _panel_with_mocks()
    p._send_message()
    p._response_watchdog.stop.reset_mock()

    p._on_connection_error("SYNAPSE connection lost.")

    assert p._waiting_for_response is False
    p._response_watchdog.stop.assert_called_once()    # via the shared teardown
    p._chat.hide_typing_indicator.assert_called()
    p._chat.append_system_message.assert_any_call("SYNAPSE connection lost.")


def test_disconnect_status_clears_waiting_via_shared_helper():
    """status_changed(False) clears the waiting state through the same shared
    helper (BP8-WATCHDOG T2 / acceptance 3).

    proved_it_bites: remove ``self._clear_waiting_state()`` from the
    ``_on_status_changed`` disconnect branch and the waiting/stop assertions
    redden.
    """
    p = _panel_with_mocks()
    p._send_message()
    p._response_watchdog.stop.reset_mock()

    with patch("synapse.panel.chat_panel.qss.sweep_a_style"):
        p._on_status_changed(False)

    assert p._waiting_for_response is False
    p._response_watchdog.stop.assert_called_once()
    p._chat.hide_typing_indicator.assert_called()


def test_failed_send_stops_watchdog_no_zombie_timer():
    """A send that fails mid-flight also tears down through the shared helper,
    so an armed watchdog is never left behind (BP8-WATCHDOG T1: stopped in the
    send-failure path).

    proved_it_bites: make the failure branch skip ``_clear_waiting_state()``
    and either the stop assertion or the waiting assertion reddens.
    """
    p = _panel_with_mocks()
    p._bridge.send_command.return_value = False  # socket died between check+send

    p._send_message()

    assert p._waiting_for_response is False
    p._response_watchdog.start.assert_called_once()   # it was armed...
    p._response_watchdog.stop.assert_called_once()    # ...then stopped
    # No stray watchdog line on a failed send (the text is handed back instead).
    for call in p._chat.append_system_message.call_args_list:
        assert not (call.args and call.args[0] == NO_RESPONSE_LINE)


# ---------------------------------------------------------------------------
# Layer 2: real QTimer (runtime truth). Runs only under a genuine PySide.
# ---------------------------------------------------------------------------
def _real_qt():
    """(ok, QtCore, QtWidgets) -- ok True only under a genuine PySide.

    Immune to the MagicMock-stub-in-sys.modules trap: a mock QTimer's
    ``isActive()`` returns a MagicMock, a real one returns a ``bool``.
    """
    try:
        from PySide6 import QtCore as C, QtWidgets as W
    except Exception:  # noqa: BLE001
        try:
            from PySide2 import QtCore as C, QtWidgets as W
        except Exception:  # noqa: BLE001
            return False, None, None
    try:
        _ = W.QApplication.instance() or W.QApplication([])
        return isinstance(C.QTimer().isActive(), bool), C, W
    except Exception:  # noqa: BLE001
        return False, None, None


def _wire_real_watchdog(panel, QtCore, interval_ms):
    """Mirror createInterface's four watchdog lines with a tiny interval."""
    panel._response_watchdog = QtCore.QTimer()
    panel._response_watchdog.setSingleShot(True)
    panel._response_watchdog.setInterval(interval_ms)
    panel._response_watchdog.timeout.connect(panel._on_response_timeout)


def _pump(QtWidgets, predicate, timeout_s=2.0):
    app = QtWidgets.QApplication.instance()
    deadline = time.time() + timeout_s
    while predicate() and time.time() < deadline:
        app.processEvents()


def test_real_qtimer_fires_and_stop_prevents_it():
    """Runtime truth under hython: a real single-shot QTimer actually fires
    the teardown+line, and a real stop() prevents any fire.
    """
    ok, QtCore, QtWidgets = _real_qt()
    if not ok:
        pytest.skip("needs a real PySide (run under hython); Layer 1 covers "
                    "the logic against a mock timer")

    # --- it fires ---
    p = SynapseChatPanel()
    p._chat = MagicMock()
    p._waiting_for_response = True
    _wire_real_watchdog(p, QtCore, 1)
    p._response_watchdog.start()
    assert p._response_watchdog.isActive() is True
    _pump(QtWidgets, lambda: p._response_watchdog.isActive())
    assert p._response_watchdog.isActive() is False        # single-shot fired
    assert p._waiting_for_response is False                 # cleared on fire
    p._chat.append_system_message.assert_called_once_with(NO_RESPONSE_LINE)

    # --- a real stop() prevents the fire ---
    q = SynapseChatPanel()
    q._chat = MagicMock()
    q._waiting_for_response = True
    _wire_real_watchdog(q, QtCore, 1)
    q._response_watchdog.start()
    q._on_response({"response": "done", "commands": []})    # stops via helper
    assert q._response_watchdog.isActive() is False
    _pump(QtWidgets, lambda: True, timeout_s=0.15)           # give it a chance
    for call in q._chat.append_system_message.call_args_list:
        assert not (call.args and call.args[0] == NO_RESPONSE_LINE)
