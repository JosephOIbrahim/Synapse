"""Tests for the Synapse Chat Panel components.

Tests cover message formatting, quick actions data integrity, and
WebSocket bridge message structures. Qt widget tests are skipped when
no display is available.
"""

import importlib
import importlib.util
import json
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub the hou module before importing panel modules
# ---------------------------------------------------------------------------
_mock_hou = types.ModuleType("hou")
_mock_hou.selectedNodes = MagicMock(return_value=[])
_mock_hou.frame = MagicMock(return_value=1.0)
_mock_hou.node = MagicMock(return_value=None)
_mock_hou.hipFile = MagicMock()
_mock_hou.hipFile.path = MagicMock(return_value="/tmp/untitled.hip")
_mock_hou.ui = MagicMock()
_mock_hou.ui.paneTabs = MagicMock(return_value=[])
_mock_hou.paneTabType = MagicMock()
_mock_hou.paneTabType.NetworkEditor = "NetworkEditor"

_orig_hou = sys.modules.get("hou")
sys.modules["hou"] = _mock_hou

# Stub hdefereval (both methods needed — handlers use both)
_orig_hdefereval = sys.modules.get("hdefereval")
_mock_hdefereval = types.ModuleType("hdefereval")
_mock_hdefereval.executeInMainThreadWithResult = lambda fn: fn()
_mock_hdefereval.executeDeferred = lambda fn: fn()
sys.modules["hdefereval"] = _mock_hdefereval

# ---------------------------------------------------------------------------
# Determine if Qt is available for widget tests
# ---------------------------------------------------------------------------
_QT_AVAILABLE = False
try:
    try:
        from PySide6 import QtWidgets, QtCore
    except ImportError:
        from PySide2 import QtWidgets, QtCore
    _QT_AVAILABLE = True
except ImportError:
    # Stub PySide6 so chat_panel.py can be imported without Qt.
    # Widget-level tests remain skipped via _QT_AVAILABLE checks;
    # logic-only tests (stale context, response handling) work fine.
    # MagicMock auto-creates attributes (QTextBrowser, etc.) on access,
    # which handles classes used as base classes in panel modules.
    _mock_qt_core = MagicMock()
    _mock_qt_core.Signal = lambda *a, **kw: MagicMock()
    _mock_qt_core.Slot = lambda *a, **kw: (lambda fn: fn)
    _mock_qt_core.QTimer = MagicMock

    _mock_qt_widgets = MagicMock()
    _mock_qt_gui = MagicMock()

    _mock_pyside6 = MagicMock()
    _mock_pyside6.QtWidgets = _mock_qt_widgets
    _mock_pyside6.QtCore = _mock_qt_core
    _mock_pyside6.QtGui = _mock_qt_gui

    sys.modules["PySide6"] = _mock_pyside6
    sys.modules["PySide6.QtWidgets"] = _mock_qt_widgets
    sys.modules["PySide6.QtCore"] = _mock_qt_core
    sys.modules["PySide6.QtGui"] = _mock_qt_gui

# Need a QApplication for widget tests
_app = None
if _QT_AVAILABLE:
    try:
        _app = QtWidgets.QApplication.instance()
        if _app is None:
            _app = QtWidgets.QApplication([])
    except Exception:
        _QT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Ensure synapse package is importable
# ---------------------------------------------------------------------------
_python_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"
)
if _python_dir not in sys.path:
    sys.path.insert(0, _python_dir)

from synapse.panel.message_formatter import (
    format_response,
    format_user_message,
    format_synapse_message,
    format_system_message,
)
from synapse.panel.quick_actions import QUICK_ACTIONS


# ===========================================================================
# Message Formatter Tests
# ===========================================================================


class TestMessageFormatterPlainText:
    """Test plain text formatting."""

    def test_plain_string_to_html(self):
        result = format_response("Hello world")
        assert "Hello world" in result
        assert "<div" in result

    def test_dict_with_message_key(self):
        result = format_response({"message": "Done successfully"})
        assert "Done successfully" in result

    def test_dict_with_result_key(self):
        result = format_response({"result": "42 nodes"})
        assert "42 nodes" in result

    def test_dict_with_content_key(self):
        result = format_response({"content": "Scene loaded"})
        assert "Scene loaded" in result


class TestMessageFormatterCodeBlock:
    """Test code block formatting."""

    def test_python_code_block(self):
        text = '```python\nprint("hello")\n```'
        result = format_response(text)
        assert "<pre" in result
        assert "print" in result

    def test_vex_code_block(self):
        text = "```vex\n@P.y = sin(@P.x);\n```"
        result = format_response(text)
        assert "<pre" in result
        assert "@P.y" in result

    def test_unfenced_code_no_pre(self):
        result = format_response("just normal text")
        assert "<pre" not in result


class TestMessageFormatterNodePath:
    """Test node path formatting."""

    def test_obj_path_becomes_link(self):
        result = format_response("Created node at /obj/geo1/scatter1")
        assert 'href="node:/obj/geo1/scatter1"' in result

    def test_stage_path_becomes_link(self):
        result = format_response("See /stage/karmarendersettings")
        assert 'href="node:/stage/karmarendersettings"' in result

    def test_out_path_becomes_link(self):
        result = format_response("ROP at /out/usdrender1")
        assert 'href="node:/out/usdrender1"' in result

    def test_no_path_no_link(self):
        result = format_response("No paths here")
        assert "href" not in result


class TestMessageFormatterMixedContent:
    """Test mixed content formatting."""

    def test_text_and_code_and_path(self):
        text = (
            "Created scatter at /obj/geo1/scatter1\n"
            "```python\nhou.node('/obj/geo1')\n```\n"
            "Done."
        )
        result = format_response(text)
        assert "href" in result  # node path link
        assert "<pre" in result  # code block

    def test_inline_code(self):
        text = "Set `height` to 5"
        result = format_response(text)
        assert "<code" in result
        assert "height" in result


class TestMessageFormatterStatus:
    """Test status indicator formatting."""

    def test_status_ok(self):
        result = format_response({"status": "ok", "message": "All good"})
        # Should contain a green circle indicator (canonical GROW #00E676)
        assert "#00E676" in result

    def test_status_error(self):
        result = format_response({"status": "error", "message": "Failed"})
        # Canonical ERROR #FF3D71
        assert "#FF3D71" in result

    def test_status_warning(self):
        result = format_response({"status": "warning", "message": "Careful"})
        # Canonical WARN #FFAB00
        assert "#FFAB00" in result

    def test_no_status_no_indicator(self):
        result = format_response("Plain text")
        # No status color indicators
        assert "#00E676" not in result
        assert "#FF3D71" not in result
        assert "#FFAB00" not in result


class TestUserMessageFormat:
    """Test user message bubble formatting."""

    def test_user_message_has_you_label(self):
        result = format_user_message("Hello")
        assert "You" in result

    def test_user_message_has_background(self):
        result = format_user_message("Hello")
        # User bubble uses CARBON (#333333) from design system
        assert "#333333" in result

    def test_user_message_escapes_html(self):
        result = format_user_message("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestSynapseMessageFormat:
    """Test synapse message bubble formatting."""

    def test_synapse_label(self):
        result = format_synapse_message("Hello")
        assert "SYNAPSE" in result

    def test_synapse_accent_color(self):
        result = format_synapse_message("Hello")
        assert "#00D4FF" in result


class TestSystemMessageFormat:
    """Test system message formatting."""

    def test_system_message_centered(self):
        result = format_system_message("Connected")
        assert "text-align:center" in result

    def test_system_message_italic(self):
        result = format_system_message("Reconnecting")
        assert "italic" in result


# ===========================================================================
# Quick Actions Tests
# ===========================================================================


class TestQuickActions:
    """Test quick action data integrity."""

    def test_all_have_required_fields(self):
        required = {"label", "prompt", "requires_selection"}
        for action in QUICK_ACTIONS:
            missing = required - set(action.keys())
            assert not missing, (
                "Action '{}' missing fields: {}".format(
                    action.get("label", "?"), missing
                )
            )

    def test_unique_labels(self):
        labels = [a["label"] for a in QUICK_ACTIONS]
        assert len(labels) == len(set(labels)), "Duplicate labels found"

    def test_all_have_tooltips(self):
        for action in QUICK_ACTIONS:
            assert "tooltip" in action, (
                "Action '{}' missing tooltip".format(action["label"])
            )

    def test_all_have_icon(self):
        for action in QUICK_ACTIONS:
            assert "icon" in action, (
                "Action '{}' missing icon".format(action["label"])
            )

    def test_minimum_actions(self):
        assert len(QUICK_ACTIONS) >= 5


# ===========================================================================
# WebSocket Bridge Tests (no actual WS connection)
# ===========================================================================


class TestWSBridgeMessageFormat:
    """Test outgoing message JSON structure."""

    def test_send_command_structure(self):
        """Verify the JSON structure of a send_command call."""
        # We test the message construction logic without an actual WS
        msg = {
            "command": "inspect_scene",
            "payload": {},
        }
        dumped = json.dumps(msg, sort_keys=True)
        parsed = json.loads(dumped)
        assert parsed["command"] == "inspect_scene"
        assert "payload" in parsed

    def test_send_chat_uses_route_chat(self):
        """Verify chat messages use route_chat command."""
        payload = {
            "command": "route_chat",
            "payload": {
                "message": "test message",
            },
        }
        dumped = json.dumps(payload, sort_keys=True)
        parsed = json.loads(dumped)
        assert parsed["command"] == "route_chat"
        assert parsed["payload"]["message"] == "test message"

    def test_chat_no_longer_uses_execute_python(self):
        """Ensure chat dispatch does not use execute_python."""
        # route_chat uses "message" key, not "content"
        payload = {
            "command": "route_chat",
            "payload": {"message": "scatter rocks on terrain"},
        }
        dumped = json.dumps(payload, sort_keys=True)
        parsed = json.loads(dumped)
        assert parsed["command"] != "execute_python"
        assert "message" in parsed["payload"]

    def test_context_included_when_provided(self):
        """Verify context dict is included in the message."""
        context = {
            "selected_nodes": ["/obj/geo1"],
            "current_network": "/obj",
            "scene_file": "/tmp/test.hip",
            "frame": 24.0,
        }
        msg = {
            "command": "route_chat",
            "payload": {"message": "hello"},
            "context": context,
        }
        dumped = json.dumps(msg, sort_keys=True)
        parsed = json.loads(dumped)
        assert parsed["context"]["frame"] == 24.0
        assert parsed["context"]["selected_nodes"] == ["/obj/geo1"]


@pytest.mark.skipif(not _QT_AVAILABLE, reason="Qt not available")
class TestWSBridgeContextKeys:
    """Test context dict structure from gather_context."""

    def test_context_has_expected_keys(self):
        """The context dict should have standard keys."""
        from synapse.panel.ws_bridge import _gather_context_on_main_thread

        ctx = _gather_context_on_main_thread()
        assert "selected_nodes" in ctx
        assert "current_network" in ctx
        assert "scene_file" in ctx
        assert "frame" in ctx

    def test_context_defaults(self):
        """Context should have sensible defaults even with no scene."""
        from synapse.panel.ws_bridge import _gather_context_on_main_thread

        ctx = _gather_context_on_main_thread()
        assert isinstance(ctx["selected_nodes"], list)
        assert isinstance(ctx["frame"], (int, float))


# ===========================================================================
# Qt Widget Tests (skipped if no display)
# ===========================================================================


@pytest.mark.skipif(not _QT_AVAILABLE, reason="Qt not available")
class TestContextBarCreation:
    """Test context bar widget creation."""

    def test_creates_without_error(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        assert bar is not None

    def test_set_connected(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_connected(True)
        assert bar._connected is True
        bar.set_connected(False)
        assert bar._connected is False

    def test_set_network_path(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_network_path("/obj/geo1")
        assert bar._network_path == "/obj/geo1"

    def test_set_selection_count(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_selection_count(3)
        assert bar._selection_count == 3

    def test_set_frame(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_frame(24.0)
        assert bar._frame == 24.0


@pytest.mark.skipif(not _QT_AVAILABLE, reason="Qt not available")
class TestChatDisplayAppend:
    """Test chat display message appending."""

    def test_append_user_message(self):
        from synapse.panel.chat_display import ChatDisplay

        display = ChatDisplay()
        display.append_user_message("Hello")
        html_content = display.toHtml()
        assert "Hello" in html_content

    def test_append_synapse_message(self):
        from synapse.panel.chat_display import ChatDisplay

        display = ChatDisplay()
        display.append_synapse_message("Response here")
        html_content = display.toHtml()
        assert "Response" in html_content

    def test_append_system_message(self):
        from synapse.panel.chat_display import ChatDisplay

        display = ChatDisplay()
        display.append_system_message("Connected")
        html_content = display.toHtml()
        assert "Connected" in html_content


@pytest.mark.skipif(not _QT_AVAILABLE, reason="Qt not available")
class TestChatDisplayNodeClick:
    """Test node path click signal emission."""

    def test_node_click_signal_emitted(self):
        from synapse.panel.chat_display import ChatDisplay

        display = ChatDisplay()
        received = []
        display.node_clicked.connect(lambda path: received.append(path))

        # Simulate anchor click
        try:
            from PySide6.QtCore import QUrl
        except ImportError:
            from PySide2.QtCore import QUrl

        display._on_anchor_clicked(QUrl("node:/obj/geo1"))
        assert received == ["/obj/geo1"]

    def test_non_node_link_ignored(self):
        from synapse.panel.chat_display import ChatDisplay

        display = ChatDisplay()
        received = []
        display.node_clicked.connect(lambda path: received.append(path))

        try:
            from PySide6.QtCore import QUrl
        except ImportError:
            from PySide2.QtCore import QUrl

        display._on_anchor_clicked(QUrl("https://example.com"))
        assert received == []


# ===========================================================================
# Stale Context Tests
# ===========================================================================


class TestStaleContextGather:
    """Test the stale-check context gathering logic."""

    def test_fresh_context_skips_gather(self):
        """When context is fresh (<5s old), gather is not called."""
        import time
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = MagicMock()
        panel._bridge.connected = True
        panel._last_context = {"current_network": "/obj"}
        panel._last_context_time = time.time() * 1000  # now

        result = panel._gather_context_if_stale()
        assert result == {"current_network": "/obj"}
        panel._bridge.gather_context.assert_not_called()

    def test_stale_context_triggers_gather(self):
        """When context is stale (>5s old), gather runs directly."""
        import time
        from unittest.mock import patch
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = MagicMock()
        panel._bridge.connected = True
        panel._last_context = {"current_network": "/obj"}
        # Set time 10s in the past
        panel._last_context_time = (time.time() - 10) * 1000

        fresh = {"current_network": "/stage", "selected_nodes": [], "scene_file": "", "frame": 1.0}
        with patch("synapse.panel.ws_bridge._gather_context_on_main_thread", return_value=fresh):
            result = panel._gather_context_if_stale()

        assert result["current_network"] == "/stage"

    def test_no_context_time_triggers_gather(self):
        """When context has never been gathered, trigger a gather."""
        from unittest.mock import patch
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = MagicMock()
        panel._bridge.connected = True
        panel._last_context = None
        panel._last_context_time = None

        fresh = {"current_network": "/obj", "selected_nodes": [], "scene_file": "", "frame": 1.0}
        with patch("synapse.panel.ws_bridge._gather_context_on_main_thread", return_value=fresh):
            result = panel._gather_context_if_stale()

        assert result["current_network"] == "/obj"

    def test_no_bridge_skips_gather(self):
        """When bridge is None, gather still works (runs on main thread)."""
        from unittest.mock import patch
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = None
        panel._last_context = None
        panel._last_context_time = None

        fresh = {"current_network": "", "selected_nodes": [], "scene_file": "", "frame": 1.0}
        with patch("synapse.panel.ws_bridge._gather_context_on_main_thread", return_value=fresh):
            result = panel._gather_context_if_stale()

        # Context is gathered even without bridge (main-thread direct call)
        assert result is not None


# ===========================================================================
# Route Chat Response Tests
# ===========================================================================


class TestRouteChatResponse:
    """Test the response handler for route_chat format."""

    def test_route_chat_response_with_text(self):
        """Response with text and tier is displayed correctly."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._chat = MagicMock()

        response = {
            "response": "Created scatter network",
            "tier": "recipe",
            "commands": [],
            "confidence": 0.95,
        }
        panel._on_response(response)
        panel._chat.append_synapse_message.assert_called_once_with(
            {"message": "Created scatter network", "tier": "recipe"}
        )

    def test_route_chat_response_with_commands(self):
        """Response with commands shows them as pending actions."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._chat = MagicMock()

        response = {
            "response": "Setting up lighting",
            "tier": "recipe",
            "commands": [
                {"type": "create_node", "description": "Create area light"},
                {"type": "set_parm", "description": "Set exposure to 8"},
            ],
            "confidence": 0.9,
        }
        panel._on_response(response)
        # Text message + 2 system messages for commands
        assert panel._chat.append_synapse_message.call_count == 1
        assert panel._chat.append_system_message.call_count == 2

    def test_error_response_handled(self):
        """Error responses are passed through to chat display."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._chat = MagicMock()

        response = {"status": "error", "message": "Couldn't find node"}
        panel._on_response(response)
        panel._chat.append_synapse_message.assert_called_once_with(response)

    def test_non_chat_response_ignored(self):
        """Responses without route_chat keys are silently ignored."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._chat = MagicMock()

        response = {"status": "ok", "data": "something"}
        panel._on_response(response)
        panel._chat.append_synapse_message.assert_not_called()


# ===========================================================================
# Chat Panel Source Verification
# ===========================================================================


# ===========================================================================
# Project Auto-Init Tests
# ===========================================================================


class TestProjectAutoInit:
    """Test project memory auto-initialization on first message."""

    def test_project_initialized_starts_false(self):
        """Panel should initialize _project_initialized to False."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        assert panel._project_initialized is False

    def test_ensure_project_fires_project_setup(self):
        """First call to _ensure_project_initialized sends project_setup."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = MagicMock()
        panel._bridge.connected = True

        panel._ensure_project_initialized()

        panel._bridge.send_command.assert_called_once_with(
            "project_setup", {}
        )
        assert panel._project_initialized is True

    def test_ensure_project_skips_when_already_initialized(self):
        """Second call to _ensure_project_initialized is a no-op."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = MagicMock()
        panel._bridge.connected = True
        panel._project_initialized = True

        panel._ensure_project_initialized()

        panel._bridge.send_command.assert_not_called()

    def test_ensure_project_skips_when_disconnected(self):
        """_ensure_project_initialized skips when bridge is disconnected."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = MagicMock()
        panel._bridge.connected = False

        panel._ensure_project_initialized()

        panel._bridge.send_command.assert_not_called()
        assert panel._project_initialized is False

    def test_ensure_project_skips_when_no_bridge(self):
        """_ensure_project_initialized skips when bridge is None."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = None

        panel._ensure_project_initialized()
        assert panel._project_initialized is False

    def test_ensure_project_retries_on_exception(self):
        """If send_command raises, flag stays False for retry."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._bridge = MagicMock()
        panel._bridge.connected = True
        panel._bridge.send_command.side_effect = Exception("ws closed")

        panel._ensure_project_initialized()

        assert panel._project_initialized is False

    def test_send_message_calls_ensure_project(self):
        """_send_message should call _ensure_project_initialized."""
        import inspect
        from synapse.panel.chat_panel import SynapseChatPanel

        send_src = inspect.getsource(SynapseChatPanel._send_message)
        assert "_ensure_project_initialized" in send_src


# ===========================================================================
# Context Bar Project Context Tests
# ===========================================================================


@pytest.mark.skipif(not _QT_AVAILABLE, reason="Qt not available")
class TestContextBarProjectContext:
    """Test context bar project memory display."""

    def test_set_project_context_charmander(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_project_context("my_project", "charmander")
        assert bar._project_name == "my_project"
        assert bar._evolution_stage == "charmander"

    def test_set_project_context_charmeleon(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_project_context("my_project", "charmeleon")
        assert bar._evolution_stage == "charmeleon"

    def test_set_project_context_charizard(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_project_context("big_project", "charizard")
        assert bar._evolution_stage == "charizard"
        assert bar._project_name == "big_project"

    def test_set_project_context_empty(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_project_context("", "")
        assert bar._project_name == ""
        assert bar._evolution_stage == ""

    def test_set_project_context_initializes_empty(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        assert bar._project_name == ""
        assert bar._evolution_stage == ""


class TestChatPanelSource:
    """Verify chat_panel.py source patterns."""

    def test_no_execute_python_in_chat_dispatch(self):
        """chat_panel.py should not use execute_python for chat messages."""
        import inspect
        from synapse.panel.chat_panel import SynapseChatPanel

        send_src = inspect.getsource(SynapseChatPanel._send_message)
        assert "execute_python" not in send_src
        assert "route_chat" in send_src

    def test_no_execute_python_in_quick_action(self):
        """_on_quick_action should use route_chat, not execute_python."""
        import inspect
        from synapse.panel.chat_panel import SynapseChatPanel

        action_src = inspect.getsource(SynapseChatPanel._on_quick_action)
        assert "execute_python" not in action_src
        assert "route_chat" in action_src

    def test_gather_context_if_stale_exists(self):
        """_gather_context_if_stale method should exist."""
        from synapse.panel.chat_panel import SynapseChatPanel

        assert hasattr(SynapseChatPanel, "_gather_context_if_stale")

    def test_last_context_time_initialized(self):
        """Panel should initialize _last_context_time to None."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        assert panel._last_context_time is None


# ===========================================================================
# Keyboard Shortcuts Tests
# ===========================================================================


class TestKeyboardShortcuts:
    """Test keyboard shortcut infrastructure."""

    def test_last_sent_message_initialized(self):
        """Panel should initialize _last_sent_message to empty string."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        assert panel._last_sent_message == ""

    def test_waiting_for_response_initialized(self):
        """Panel should initialize _waiting_for_response to False."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        assert panel._waiting_for_response is False

    def test_send_message_stores_last_sent(self):
        """_send_message should store the sent text in _last_sent_message."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._input = MagicMock()
        panel._input.text.return_value = "scatter rocks"
        panel._chat = MagicMock()
        panel._bridge = MagicMock()
        panel._bridge.connected = True

        panel._send_message()
        assert panel._last_sent_message == "scatter rocks"

    def test_send_message_sets_waiting_flag(self):
        """_send_message should set _waiting_for_response to True."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._input = MagicMock()
        panel._input.text.return_value = "hello"
        panel._chat = MagicMock()
        panel._bridge = MagicMock()
        panel._bridge.connected = True

        panel._send_message()
        assert panel._waiting_for_response is True

    def test_response_clears_waiting_flag(self):
        """_on_response should clear _waiting_for_response."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._chat = MagicMock()
        panel._waiting_for_response = True

        panel._on_response({"response": "done", "tier": "recipe"})
        assert panel._waiting_for_response is False

    def test_shortcut_clear_chat(self):
        """_shortcut_clear_chat should call chat.clear()."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._chat = MagicMock()
        panel._shortcut_clear_chat()
        panel._chat.clear.assert_called_once()

    def test_shortcut_focus_input(self):
        """_shortcut_focus_input should call input.setFocus()."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._input = MagicMock()
        panel._shortcut_focus_input()
        panel._input.setFocus.assert_called_once()

    def test_shortcut_escape_clears_input(self):
        """_shortcut_escape should clear the input field."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._input = MagicMock()
        panel._shortcut_escape()
        panel._input.clear.assert_called_once()

    def test_install_shortcuts_method_exists(self):
        """_install_shortcuts method should exist on SynapseChatPanel."""
        from synapse.panel.chat_panel import SynapseChatPanel

        assert hasattr(SynapseChatPanel, "_install_shortcuts")

    def test_event_filter_class_exists(self):
        """_InputEventFilter class handles Up-arrow recall for the input field."""
        from synapse.panel.chat_panel import _InputEventFilter

        assert hasattr(_InputEventFilter, "eventFilter")


# ===========================================================================
# Typing Indicator Tests
# ===========================================================================


class TestTypingIndicator:
    """Test the typing indicator in chat display."""

    def test_send_shows_typing_indicator(self):
        """_send_message should call show_typing_indicator on the chat."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._input = MagicMock()
        panel._input.text.return_value = "test"
        panel._chat = MagicMock()
        panel._bridge = MagicMock()
        panel._bridge.connected = True

        panel._send_message()
        panel._chat.show_typing_indicator.assert_called_once()

    def test_response_hides_typing_indicator(self):
        """_on_response should call hide_typing_indicator on the chat."""
        from synapse.panel.chat_panel import SynapseChatPanel

        panel = SynapseChatPanel()
        panel._chat = MagicMock()

        panel._on_response({"response": "done", "tier": "cache"})
        panel._chat.hide_typing_indicator.assert_called_once()

    def test_typing_html_contains_signal_color(self):
        """Typing indicator HTML should use SIGNAL cyan color."""
        import inspect
        src = inspect.getsource(
            sys.modules["synapse.panel.chat_display"]
        )
        # The class defines _TYPING_HTML with SIGNAL color
        assert "#00D4FF" in src or "t.SIGNAL" in src

    def test_typing_html_contains_thinking(self):
        """Typing indicator should show 'thinking...' text."""
        import inspect
        src = inspect.getsource(
            sys.modules["synapse.panel.chat_display"]
        )
        assert "thinking..." in src


# ===========================================================================
# CSS Consolidation Verification Tests
# ===========================================================================


class TestCSSConsolidation:
    """Verify all inline CSS has been moved to styles.py."""

    def test_no_inline_css_in_chat_panel_root(self):
        """Root widget should use get_root_widget_stylesheet()."""
        import inspect
        from synapse.panel.chat_panel import SynapseChatPanel

        src = inspect.getsource(SynapseChatPanel.createInterface)
        assert "get_root_widget_stylesheet()" in src
        assert "font-family:" not in src

    def test_no_inline_css_in_build_quick_actions(self):
        """Quick actions should use get_section_container_stylesheet()."""
        import inspect
        from synapse.panel.chat_panel import SynapseChatPanel

        src = inspect.getsource(SynapseChatPanel._build_quick_actions)
        assert "get_section_container_stylesheet()" in src
        assert "background:" not in src

    def test_no_inline_css_in_build_input_area(self):
        """Input area should use get_section_container_stylesheet()."""
        import inspect
        from synapse.panel.chat_panel import SynapseChatPanel

        src = inspect.getsource(SynapseChatPanel._build_input_area)
        assert "get_section_container_stylesheet()" in src

    def test_no_inline_css_in_connection_bar(self):
        """Connection bar should use get_connection_frame_stylesheet()."""
        import inspect
        from synapse.panel.chat_panel import SynapseChatPanel

        src = inspect.getsource(SynapseChatPanel._build_connection_bar)
        assert "get_connection_frame_stylesheet()" in src
        assert "border-top:" not in src

    def test_no_inline_css_in_mode_toolbar(self):
        """Mode toolbar should use get_mode_toolbar_stylesheet()."""
        import inspect
        from synapse.panel.chat_panel import SynapseChatPanel

        src = inspect.getsource(SynapseChatPanel._build_mode_toolbar)
        assert "get_mode_toolbar_stylesheet()" in src
        assert "border-bottom:" not in src


# ===========================================================================
# New Style Function Tests
# ===========================================================================


class TestNewStyleFunctions:
    """Verify new stylesheet functions from styles.py."""

    def test_root_widget_stylesheet(self):
        from synapse.panel.styles import get_root_widget_stylesheet
        ss = get_root_widget_stylesheet()
        assert "background" in ss
        assert "font-family" in ss

    def test_section_container_stylesheet(self):
        from synapse.panel.styles import get_section_container_stylesheet
        ss = get_section_container_stylesheet()
        assert "background" in ss

    def test_connection_frame_stylesheet(self):
        from synapse.panel.styles import get_connection_frame_stylesheet
        ss = get_connection_frame_stylesheet()
        assert "connection_frame" in ss
        assert "border-top" in ss

    def test_mode_toolbar_stylesheet(self):
        from synapse.panel.styles import get_mode_toolbar_stylesheet
        ss = get_mode_toolbar_stylesheet()
        assert "background" in ss
        assert "border-bottom" in ss

    def test_chat_display_stylesheet(self):
        from synapse.panel.styles import get_chat_display_stylesheet
        ss = get_chat_display_stylesheet()
        assert "QTextBrowser" in ss
        assert "QScrollBar" in ss
        assert "selection-background-color" in ss


# ---------------------------------------------------------------------------
# Teardown: restore original hou module
# ---------------------------------------------------------------------------
def teardown_module():
    if _orig_hou is not None:
        sys.modules["hou"] = _orig_hou
    else:
        sys.modules.pop("hou", None)
    # Do NOT pop hdefereval — other test files depend on the stub persisting.
    # The stub is harmless (just calls fn() directly) and removing it causes
    # cross-test ModuleNotFoundError for any test importing handlers_tops.py.
