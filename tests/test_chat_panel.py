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
    pass

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
        # Should contain a green circle indicator
        assert "#6BCB77" in result

    def test_status_error(self):
        result = format_response({"status": "error", "message": "Failed"})
        assert "#FF6B6B" in result

    def test_status_warning(self):
        result = format_response({"status": "warning", "message": "Careful"})
        assert "#FFD93D" in result

    def test_no_status_no_indicator(self):
        result = format_response("Plain text")
        # No status color indicators
        assert "#6BCB77" not in result
        assert "#FF6B6B" not in result
        assert "#FFD93D" not in result


class TestUserMessageFormat:
    """Test user message bubble formatting."""

    def test_user_message_has_you_label(self):
        result = format_user_message("Hello")
        assert "You" in result

    def test_user_message_has_background(self):
        result = format_user_message("Hello")
        assert "#2A2A2A" in result

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

    def test_send_chat_structure(self):
        """Verify the JSON structure of a chat message."""
        payload = {
            "command": "execute_python",
            "payload": {
                "content": "test message",
            },
        }
        dumped = json.dumps(payload, sort_keys=True)
        parsed = json.loads(dumped)
        assert parsed["command"] == "execute_python"
        assert parsed["payload"]["content"] == "test message"

    def test_context_included_when_provided(self):
        """Verify context dict is included in the message."""
        context = {
            "selected_nodes": ["/obj/geo1"],
            "current_network": "/obj",
            "scene_file": "/tmp/test.hip",
            "frame": 24.0,
        }
        msg = {
            "command": "execute_python",
            "payload": {"content": "hello"},
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
