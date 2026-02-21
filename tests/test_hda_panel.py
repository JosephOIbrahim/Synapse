"""Tests for the HDA panel: bridge routing, views, controller, and regression.

Mock-based -- no Houdini or Qt event loop required.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: minimal stubs for hou, hdefereval, PySide6/PySide2, websockets
# ---------------------------------------------------------------------------

# hou stub
if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.selectedNodes = MagicMock(return_value=[])
    _hou.undos = MagicMock()
    _hou.hda = MagicMock()
    _hou.exprLanguage = MagicMock()
    _hou.exprLanguage.Hscript = "Hscript"
    _hou.scriptLanguage = MagicMock()
    _hou.scriptLanguage.Python = "Python"
    _hou.FolderParmTemplate = MagicMock()
    _hou.Keyframe = MagicMock
    _hou.OperationFailed = type("OperationFailed", (Exception,), {})
    sys.modules["hou"] = _hou

if "hdefereval" not in sys.modules:
    _hde = types.ModuleType("hdefereval")
    _hde.executeDeferred = lambda fn: fn()
    _hde.executeInMainThreadWithResult = lambda fn: fn()
    sys.modules["hdefereval"] = _hde

# Qt stub -- provide just enough for Signal, QThread, QObject, QWidget, etc.
_qt_core_stub = None
_qt_widgets_stub = None
_qt_gui_stub = None

for qt_pkg in ("PySide6", "PySide2"):
    try:
        __import__(qt_pkg)
        break  # Real Qt available, no stub needed
    except ImportError:
        continue
else:
    # No Qt available -- provide stubs
    class _FakeSignal:
        def __init__(self, *args):
            self._slots = []
        def connect(self, slot):
            self._slots.append(slot)
        def emit(self, *args):
            for s in self._slots:
                s(*args)
        def disconnect(self, slot=None):
            if slot:
                self._slots.remove(slot)
            else:
                self._slots.clear()

    class _FakeQObject:
        def __init__(self, parent=None):
            pass

    class _FakeQThread(_FakeQObject):
        def isRunning(self):
            return False
        def start(self):
            pass
        def wait(self, timeout=0):
            pass
        def msleep(self, ms):
            pass

    class _FakeQWidget(_FakeQObject):
        def setObjectName(self, name):
            self._objectName = name
        def objectName(self):
            return getattr(self, "_objectName", "")
        def setStyleSheet(self, ss):
            pass
        def setMinimumHeight(self, h):
            pass
        def setMaximumHeight(self, h):
            pass
        def setMinimumWidth(self, w):
            pass
        def style(self):
            m = MagicMock()
            return m

    # Build PySide6 stub modules
    pyside6 = types.ModuleType("PySide6")
    pyside6_core = types.ModuleType("PySide6.QtCore")
    pyside6_core.Signal = _FakeSignal
    pyside6_core.Slot = lambda *a, **k: (lambda f: f)
    pyside6_core.QObject = _FakeQObject
    pyside6_core.QThread = _FakeQThread
    pyside6_core.QTimer = MagicMock
    pyside6_core.QMetaObject = MagicMock()
    pyside6_core.Qt = MagicMock()
    pyside6_core.Q_ARG = MagicMock()
    pyside6_core.QPropertyAnimation = MagicMock
    pyside6_core.QEasingCurve = MagicMock()

    pyside6_widgets = types.ModuleType("PySide6.QtWidgets")
    pyside6_widgets.QWidget = _FakeQWidget
    pyside6_widgets.QVBoxLayout = MagicMock
    pyside6_widgets.QHBoxLayout = MagicMock
    pyside6_widgets.QStackedWidget = MagicMock
    pyside6_widgets.QLabel = MagicMock
    pyside6_widgets.QTextEdit = MagicMock
    pyside6_widgets.QPushButton = MagicMock
    pyside6_widgets.QComboBox = MagicMock
    pyside6_widgets.QCheckBox = MagicMock
    pyside6_widgets.QProgressBar = MagicMock
    pyside6_widgets.QTableWidget = MagicMock
    pyside6_widgets.QTableWidgetItem = MagicMock
    pyside6_widgets.QGraphicsOpacityEffect = MagicMock
    pyside6_widgets.QAbstractItemView = MagicMock()
    pyside6_widgets.QFrame = MagicMock
    pyside6_widgets.QGridLayout = MagicMock
    pyside6_widgets.QLineEdit = MagicMock
    pyside6_widgets.QApplication = MagicMock

    pyside6_gui = types.ModuleType("PySide6.QtGui")
    pyside6_gui.QCursor = MagicMock
    pyside6_gui.QTextCursor = MagicMock()
    pyside6_gui.QGuiApplication = MagicMock

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = pyside6_core
    sys.modules["PySide6.QtWidgets"] = pyside6_widgets
    sys.modules["PySide6.QtGui"] = pyside6_gui


# ---------------------------------------------------------------------------
# Ensure synapse package modules exist for import
# ---------------------------------------------------------------------------

_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
    ("synapse.panel", _base / "panel"),
    ("synapse.routing", _base / "routing"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

# Pre-load core modules needed by panel imports
for mod_name, fpath in [
    ("synapse.core.protocol", _base / "core" / "protocol.py"),
    ("synapse.core.aliases", _base / "core" / "aliases.py"),
]:
    if mod_name not in sys.modules and fpath.exists():
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Import panel modules
# ---------------------------------------------------------------------------

from synapse.panel.ws_bridge import SynapseWSBridge, HDA_STAGES
from synapse.routing.hda_recipes import HDA_RECIPES, list_recipes
from synapse.panel import tokens as t


# ---------------------------------------------------------------------------
# X1: Test bridge message routing
# ---------------------------------------------------------------------------

class TestBridgeMessageRouting:
    """Verify _dispatch_message routes by msg_type."""

    def _make_bridge(self):
        bridge = SynapseWSBridge.__new__(SynapseWSBridge)
        # Manually init without QThread.__init__ (no Qt event loop)
        bridge._ws = None
        bridge._running = False
        bridge._send_queue = []
        import threading
        bridge._queue_lock = threading.Lock()
        return bridge

    def test_chat_message_routes_to_chat_signal(self):
        """Messages with msg_type='chat' emit response_received."""
        bridge = self._make_bridge()
        received = []
        bridge.response_received.connect(lambda d: received.append(d))

        data = {"msg_type": "chat", "text": "hello"}
        bridge._dispatch_message(data)

        assert len(received) == 1
        assert received[0]["text"] == "hello"

    def test_hda_progress_routes_to_hda_signal(self):
        """Messages with msg_type='hda_progress' emit hda_progress."""
        bridge = self._make_bridge()
        received = []
        bridge.hda_progress.connect(lambda d: received.append(d))

        data = {"msg_type": "hda_progress", "stage": "building_nodes", "progress_pct": 50}
        bridge._dispatch_message(data)

        assert len(received) == 1
        assert received[0]["stage"] == "building_nodes"

    def test_hda_result_routes_to_hda_signal(self):
        """Messages with msg_type='hda_result' emit hda_result."""
        bridge = self._make_bridge()
        received = []
        bridge.hda_result.connect(lambda d: received.append(d))

        data = {"msg_type": "hda_result", "success": True, "node_path": "/obj/my_hda"}
        bridge._dispatch_message(data)

        assert len(received) == 1
        assert received[0]["success"] is True

    def test_backward_compat_no_msg_type(self):
        """Messages without msg_type default to chat routing."""
        bridge = self._make_bridge()
        chat_received = []
        hda_received = []
        bridge.response_received.connect(lambda d: chat_received.append(d))
        bridge.hda_progress.connect(lambda d: hda_received.append(d))

        data = {"status": "ok", "result": "something"}
        bridge._dispatch_message(data)

        assert len(chat_received) == 1
        assert len(hda_received) == 0

    def test_hda_stages_constant(self):
        """HDA_STAGES has expected stages."""
        assert "parsing_prompt" in HDA_STAGES
        assert "complete" in HDA_STAGES
        assert "failed" in HDA_STAGES
        assert len(HDA_STAGES) == 9

    def test_send_method_queues_when_disconnected(self):
        """send() queues messages when WebSocket is not connected."""
        bridge = self._make_bridge()
        bridge._ws = None

        bridge.send({"command": "test"})
        assert len(bridge._send_queue) == 1
        queued = json.loads(bridge._send_queue[0])
        assert queued["command"] == "test"


# ---------------------------------------------------------------------------
# X2: Test tokens and styles
# ---------------------------------------------------------------------------

class TestTokensAndStyles:
    """Verify design tokens and stylesheet generation."""

    def test_hda_tokens_exist(self):
        assert hasattr(t, "STATE_DESCRIBE")
        assert hasattr(t, "STATE_BUILDING")
        assert hasattr(t, "STATE_RESULT")
        assert hasattr(t, "HDA_INPUT_BG")
        assert hasattr(t, "HDA_STAGE_ACTIVE")
        assert hasattr(t, "MODE_ACTIVE_BG")

    def test_signal_color_is_canonical(self):
        assert t.SIGNAL == "#00D4FF"

    def test_error_color_alias(self):
        assert t.ERROR_COLOR == t.ERROR

    def test_stylesheet_generates(self):
        from synapse.panel.styles import get_hda_stylesheet
        ss = get_hda_stylesheet()
        assert isinstance(ss, str)
        assert "HdaPromptInput" in ss
        assert "BuildingView" in ss
        assert "NodePathLabel" in ss
        assert "ModeToggleActive" in ss
        assert len(ss) > 500


# ---------------------------------------------------------------------------
# X3: Test HDA recipes
# ---------------------------------------------------------------------------

class TestHdaRecipes:
    """Verify recipe structure and content."""

    def test_lop_light_rig_recipe_valid(self):
        recipe = HDA_RECIPES["lop_light_rig"]
        assert recipe["context"] == "LOP"
        assert recipe["name"] == "three_point_light_rig"
        assert len(recipe["node_graph"]) >= 4
        # Has key, fill, rim, dome
        names = [n["name"] for n in recipe["node_graph"]]
        assert "key_light" in names
        assert "fill_light" in names
        assert "rim_light" in names
        assert "dome_light" in names

    def test_lop_karma_quality_recipe_valid(self):
        recipe = HDA_RECIPES["lop_karma_quality"]
        assert recipe["context"] == "LOP"
        assert "quality_presets" in recipe
        presets = recipe["quality_presets"]
        assert "draft" in presets
        assert "preview" in presets
        assert "production" in presets

    def test_all_recipes_have_required_fields(self):
        for key, recipe in HDA_RECIPES.items():
            assert "name" in recipe, "Recipe {} missing name".format(key)
            assert "context" in recipe, "Recipe {} missing context".format(key)
            assert "node_graph" in recipe, "Recipe {} missing node_graph".format(key)
            assert "promote_parameters" in recipe, (
                "Recipe {} missing promote_parameters".format(key)
            )

    def test_list_recipes_returns_summaries(self):
        summaries = list_recipes()
        assert len(summaries) == len(HDA_RECIPES)
        for s in summaries:
            assert "key" in s
            assert "name" in s
            assert "context" in s

    def test_sop_scatter_recipe_connections(self):
        recipe = HDA_RECIPES["sop_scatter"]
        assert len(recipe["connections"]) >= 2
        # __input0 -> scatter1
        assert recipe["connections"][0][0] == "__input0"

    def test_lighting_law_compliance(self):
        """Light rig recipe must use intensity=1.0 and exposure for brightness."""
        recipe = HDA_RECIPES["lop_light_rig"]
        for node in recipe["node_graph"]:
            parms = node.get("parms", {})
            if "xn__inputsintensity_i0a" in parms:
                assert parms["xn__inputsintensity_i0a"] == 1.0, (
                    "{} violates Lighting Law: intensity must be 1.0".format(
                        node["name"]
                    )
                )


# ---------------------------------------------------------------------------
# X4: Test HDA controller
# ---------------------------------------------------------------------------

class TestHdaController:
    """Test controller recipe selection and signal flow."""

    def _make_controller(self):
        from synapse.panel.hda_controller import HdaController
        mock_bridge = MagicMock()
        mock_bridge.hda_progress = MagicMock()
        mock_bridge.hda_progress.connect = MagicMock()
        mock_bridge.hda_result = MagicMock()
        mock_bridge.hda_result.connect = MagicMock()
        controller = HdaController(bridge=mock_bridge)
        return controller, mock_bridge

    def test_selects_scatter_recipe_for_sop(self):
        controller, bridge = self._make_controller()
        recipe = controller._select_recipe("scatter points on surface", "SOP")
        assert recipe is not None
        assert "scatter" in recipe["name"]

    def test_selects_light_rig_for_lop(self):
        controller, bridge = self._make_controller()
        recipe = controller._select_recipe(
            "set up a 3-point light rig", "LOP"
        )
        assert recipe is not None
        assert "light" in recipe["name"]

    def test_returns_none_for_no_match(self):
        controller, bridge = self._make_controller()
        recipe = controller._select_recipe(
            "quantum field simulation", "DOP"
        )
        assert recipe is None

    def test_execute_sends_to_bridge(self):
        controller, bridge = self._make_controller()
        results = []
        controller.result.connect(lambda d: results.append(d))

        controller.execute("scatter points on surface", "SOP", {})

        # Should have called bridge.send with hda_package payload
        bridge.send.assert_called_once()
        payload = bridge.send.call_args[0][0]
        assert payload["command"] == "hda_package"
        assert "scatter" in payload["payload"]["name"]

    def test_execute_emits_failure_on_no_match(self):
        controller, bridge = self._make_controller()
        results = []
        controller.result.connect(lambda d: results.append(d))

        controller.execute("quantum entanglement simulator", "DOP", {})

        assert len(results) == 1
        assert results[0]["success"] is False

    def test_execute_blocks_when_active(self):
        controller, bridge = self._make_controller()
        errors = []
        controller.error.connect(lambda msg: errors.append(msg))

        # First call succeeds
        controller.execute("scatter points", "SOP", {})
        assert controller.active is True

        # Second call should emit error
        controller.execute("another hda", "SOP", {})
        assert len(errors) == 1
        assert "already in progress" in errors[0]

    def test_cancel_resets_active(self):
        controller, bridge = self._make_controller()
        controller.execute("scatter points", "SOP", {})
        assert controller.active is True

        controller.cancel()
        assert controller.active is False


# ---------------------------------------------------------------------------
# X5: E2E flow test
# ---------------------------------------------------------------------------

class TestE2EFlow:
    """Full flow: prompt -> controller -> recipe -> (mocked) build -> result."""

    def test_full_prompt_to_result(self):
        from synapse.panel.hda_controller import HdaController

        mock_bridge = MagicMock()
        mock_bridge.hda_progress = MagicMock()
        mock_bridge.hda_progress.connect = MagicMock()
        mock_bridge.hda_result = MagicMock()
        mock_bridge.hda_result.connect = MagicMock()

        controller = HdaController(bridge=mock_bridge)

        # Track signals
        progress_updates = []
        results = []
        controller.progress.connect(
            lambda s, p, d: progress_updates.append((s, p, d))
        )
        controller.result.connect(lambda d: results.append(d))

        # Execute
        controller.execute(
            "Create a scatter tool for distributing points",
            "SOP",
            {"include_help": True},
        )

        # Verify progress was emitted
        assert len(progress_updates) >= 2
        assert progress_updates[0][0] == "parsing_prompt"
        assert progress_updates[1][0] == "selecting_recipe"

        # Verify bridge.send was called with correct payload
        bridge_call = mock_bridge.send.call_args[0][0]
        assert bridge_call["command"] == "hda_package"
        assert bridge_call["payload"]["category"] == "Sop"
        assert len(bridge_call["payload"]["nodes"]) >= 2

        # Simulate Houdini result coming back
        controller._on_bridge_result({
            "success": True,
            "node_path": "/obj/geo1/scatter_points",
            "parameters": [
                {"name": "npts", "type": "int", "default": 10000},
            ],
            "validation": {
                "cook_success": True,
                "internal_nodes": 2,
                "connections_valid": True,
            },
        })

        assert len(results) == 1
        assert results[0]["success"] is True
        assert controller.active is False


# ---------------------------------------------------------------------------
# X6: Regression — existing tests still pass
# ---------------------------------------------------------------------------

class TestRegression:
    """Verify no regression in existing infrastructure."""

    def test_bridge_has_original_signals(self):
        """Original signals still exist on SynapseWSBridge."""
        assert hasattr(SynapseWSBridge, "response_received")
        assert hasattr(SynapseWSBridge, "status_changed")
        assert hasattr(SynapseWSBridge, "context_updated")

    def test_bridge_has_new_signals(self):
        """New HDA signals added to SynapseWSBridge."""
        assert hasattr(SynapseWSBridge, "hda_progress")
        assert hasattr(SynapseWSBridge, "hda_result")

    def test_bridge_send_command_still_works(self):
        """send_command() is backward compatible."""
        bridge = SynapseWSBridge.__new__(SynapseWSBridge)
        bridge._ws = None
        bridge._running = False
        bridge._send_queue = []
        import threading
        bridge._queue_lock = threading.Lock()

        bridge.send_command("ping", {"msg": "hello"})
        assert len(bridge._send_queue) == 1
        msg = json.loads(bridge._send_queue[0])
        assert msg["command"] == "ping"
        assert msg["payload"]["msg"] == "hello"

    def test_recipes_import_cleanly(self):
        """Recipes module imports without errors."""
        from synapse.routing.hda_recipes import HDA_RECIPES, get_recipe
        assert len(HDA_RECIPES) >= 5
        assert get_recipe("sop_scatter") is not None
        assert get_recipe("nonexistent") is None

    def test_tokens_import_cleanly(self):
        """Panel tokens import without errors."""
        from synapse.panel.tokens import (
            SIGNAL, VOID, CARBON, GRAPHITE,
            STATE_DESCRIBE, STATE_BUILDING, STATE_RESULT,
            HDA_INPUT_BG, ERROR_COLOR,
        )
        assert SIGNAL == "#00D4FF"
        assert ERROR_COLOR == "#FF3D71"
