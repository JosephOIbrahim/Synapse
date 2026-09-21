"""Tests for the shared panel components that outlived the legacy chat panel.

Tests cover message formatting, the WebSocket bridge context gather, the
context bar and the chat display. Qt widget tests are skipped when no display
is available.

BP9-RETIRE (ruling 3): chat_panel.py / quick_actions.py are deleted; the
SynapseChatPanel, QuickActionPills and route_chat protocol tests that lived
here went with them. What remains tests modules the shipped panel still uses.
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
if "hou" not in sys.modules:  # defer to conftest's canonical hou resident
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
    # Stub PySide6 so the panel modules can be imported without Qt.
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

    def test_usd_prim_path_becomes_chip(self):
        # Mile 3 — the comp's Direct artifact is a USD prim path, not a /obj
        # node path. It must still resolve to a clickable node: chip.
        result = format_response("rebound at /materials/AMD/Dark_Glass")
        assert 'href="node:/materials/AMD/Dark_Glass"' in result

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
    """Mile 3 — the human voice: a signal hairline + brighter text, no bubble."""

    def test_user_message_has_signal_rule(self):
        # The single hairline rule on the human voice uses the canonical
        # signal blue (#8FB3D9), not the legacy cyan, not a bubble.
        result = format_user_message("Hello")
        assert "#8FB3D9" in result

    def test_user_message_has_no_bubble(self):
        # Bubbles are dead: no CARBON fill, no rounded container.
        result = format_user_message("Hello")
        assert "#333333" not in result
        assert "border-radius" not in result

    def test_user_message_escapes_html(self):
        result = format_user_message("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestSynapseMessageFormat:
    """Mile 3 — the agent voice: plain body copy, no label, no bubble."""

    def test_synapse_no_bubble(self):
        result = format_synapse_message("Hello")
        assert "Hello" in result
        assert "border-radius" not in result
        assert "#333333" not in result

    def test_synapse_uses_canonical_signal(self):
        # Node refs surface as artifact chips in the canonical signal blue
        # (#8FB3D9) — the de-cyaned single chromatic event, not #00D4FF.
        result = format_synapse_message("rebound at /obj/geo1/mat")
        assert "#8FB3D9" in result
        assert "#00D4FF" not in result


class TestStylesDecyaned:
    """Mile 7 — styles.py renders the signature blue (#8FB3D9), not legacy cyan."""

    def _all_styles(self):
        from synapse.panel import styles
        return "".join([
            styles.get_chat_display_stylesheet(),
            styles.get_send_button_stylesheet(),
            styles.get_growing_input_stylesheet(),
            styles.get_quick_action_button_stylesheet(),
            styles.get_connect_button_stylesheet(),
            styles.get_ws_url_button_stylesheet(),
            styles.get_context_bar_path_stylesheet(),
            styles.get_quick_action_pill_stylesheet(),
            styles.get_font_size_button_stylesheet(),
            styles.get_hda_stylesheet(),
        ])

    def test_no_legacy_cyan(self):
        out = self._all_styles().upper()
        assert "00D4FF" not in out
        assert "0, 212, 255" not in out and "0,212,255" not in out

    def test_signature_blue_present(self):
        assert "8FB3D9" in self._all_styles().upper()


class TestSystemMessageFormat:
    """Test system message formatting."""

    def test_system_message_centered(self):
        result = format_system_message("Connected")
        assert "text-align:center" in result

    def test_system_message_italic(self):
        result = format_system_message("Reconnecting")
        assert "italic" in result


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


@pytest.mark.skipif(not _QT_AVAILABLE, reason="Qt not available")
class TestContextBarProjectContext:
    """Test context bar project memory display."""

    def test_set_project_context_flat(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_project_context("my_project", "flat")
        assert bar._project_name == "my_project"
        assert bar._evolution_stage == "flat"

    def test_set_project_context_structured(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_project_context("my_project", "structured")
        assert bar._evolution_stage == "structured"

    def test_set_project_context_composed(self):
        from synapse.panel.context_bar import ContextBar

        bar = ContextBar()
        bar.set_project_context("big_project", "composed")
        assert bar._evolution_stage == "composed"
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
    # Absence is `= None`, never a pop — a genuine eviction lets a later lazy
    # `import hou` re-execute hou.py under hython and half-build the SWIG `Parm`
    # class for the rest of the process. See HOU_REIMPORT_GUARD in
    # tests/conftest.py. Dormant here (under hython `_orig_hou` is real hou), and
    # converted anyway: the guard rescues the idiom, it does not make it correct.
    sys.modules["hou"] = _orig_hou
    # Do NOT pop hdefereval — other test files depend on the stub persisting.
    # The stub is harmless (just calls fn() directly) and removing it causes
    # cross-test ModuleNotFoundError for any test importing handlers_tops.py.
