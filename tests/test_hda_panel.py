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

# Qt stub -- ALWAYS use fakes. These tests run without a Qt event loop.
# Real PySide6/PySide2 may be installed but unusable in headless/WSL
# environments, so we force stubs regardless.


class _AutoMockModule(types.ModuleType):
    """Module stub that auto-provides MagicMock for missing attributes.

    Explicit attributes (Signal, QObject, etc.) take priority. Anything
    else returns a fresh MagicMock so ``from PySide6.QtFoo import Bar``
    always succeeds regardless of which Qt class ``Bar`` is.
    """

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        mock = MagicMock()
        object.__setattr__(self, name, mock)
        return mock


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

# Build PySide6 stub modules using _AutoMockModule so missing Qt classes
# auto-resolve to MagicMock (prevents ImportError for any Qt class).
pyside6 = _AutoMockModule("PySide6")
pyside6.__path__ = []  # Makes it a package
pyside6_core = _AutoMockModule("PySide6.QtCore")
pyside6_core.Signal = _FakeSignal
pyside6_core.Slot = lambda *a, **k: (lambda f: f)
pyside6_core.QObject = _FakeQObject
pyside6_core.QThread = _FakeQThread
pyside6_core.QTimer = MagicMock
pyside6_core.QMetaObject = MagicMock()
pyside6_core.Qt = MagicMock()
pyside6_core.Q_ARG = MagicMock()
pyside6_core.QUrl = MagicMock
pyside6_core.QPropertyAnimation = MagicMock
pyside6_core.QEasingCurve = MagicMock()

pyside6_widgets = _AutoMockModule("PySide6.QtWidgets")
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

pyside6_gui = _AutoMockModule("PySide6.QtGui")
pyside6_gui.QCursor = MagicMock
pyside6_gui.QTextCursor = MagicMock()
pyside6_gui.QGuiApplication = MagicMock

# Wire submodules as attributes so `from PySide6 import QtCore` works
pyside6.QtCore = pyside6_core
pyside6.QtWidgets = pyside6_widgets
pyside6.QtGui = pyside6_gui

# Evict any real PySide6/PySide2 so panel modules pick up our stubs.
# Only evict the specific panel modules THIS file reimports — leave
# other panel modules (chat_panel, message_formatter, etc.) untouched
# so sibling test files aren't affected.
#
# CRITICAL (Q1): capture the ORIGINAL module OBJECTS before eviction and put
# those exact objects back once our imports are done (see _restore_real_qt
# below). Shiboken cannot re-initialise in one process: once real PySide6 is
# deleted from sys.modules, a later ``import PySide6`` yields a NEW but
# half-initialised module (PySide6.QtWidgets loses QApplication) while the C++
# QApplication singleton stays alive — any sibling test that then calls
# app.font() dereferences dead wrapper state and the interpreter takes an
# access violation. Restore-by-object is the only correct teardown;
# restore-by-reimport looks identical and is not.
# Only *file-backed* Qt modules count as real. Sibling test files
# (test_chat_panel.py, test_panel_preflight.py, …) plant their own in-memory
# PySide6 stubs and may run before this one; those carry no ``__file__``, are
# not Shiboken-backed, and must NOT be handed back here — restoring a foreign
# stub would deprive the tests that rely on this file's richer stub.
#
# The ``__file__`` filter is load-bearing, so it lives in exactly ONE place —
# ``qt_stub_window.capture_real_qt`` — imported here and used by the stub window
# too, so the two consumers cannot drift. It is unit-pinned below by
# ``test_capture_real_qt_rejects_file_less_stubs`` and in
# ``tests/test_qt_stub_window.py``. Inlining it back into the comprehension
# would put it beyond the reach of those pins.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from qt_stub_window import capture_real_qt as _capture_real_qt  # noqa: E402

_REAL_QT_MODULES = _capture_real_qt(sys.modules)
for _key in list(sys.modules):
    if _key.startswith(("PySide6", "PySide2")):
        del sys.modules[_key]
for _key in ("synapse.panel.ws_bridge", "synapse.panel.hda_controller"):
    sys.modules.pop(_key, None)

# Evict any leaked bare ``tokens`` so synapse.panel.tokens (imported below)
# resolves its SIGNAL from the deployed/fallback source (#00D4FF), not from a
# repo-tokens pin (#8FB3D9) that test_design_system may have left in
# sys.modules. We pop only bare ``tokens`` (not synapse.panel.tokens itself) so
# this file's captured panel-tokens module stays stable for the whole session.
_REAL_BARE_TOKENS = sys.modules.pop("tokens", None)

_QT_STUB_KEYS = ("PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui")
sys.modules["PySide6"] = pyside6
sys.modules["PySide6.QtCore"] = pyside6_core
sys.modules["PySide6.QtWidgets"] = pyside6_widgets
sys.modules["PySide6.QtGui"] = pyside6_gui

# Status written by _restore_real_qt() below. Read by the regression pins.
#
# Law 3: these report what HAPPENED, not that a function was entered.
#   _QT_RESTORE_STATUS  : None (never called) | "noop-nothing-captured" | "restored"
#   _TOKENS_RESTORE_STATUS : None (branch not reached)
#                          | "noop-nothing-captured"
#                          | "noop-foreign-tokens-present"  (someone else owns it)
#                          | "restored"
_QT_RESTORE_STATUS = None
_TOKENS_RESTORE_STATUS = None
_QT_RESTORE_STATUSES = (None, "noop-nothing-captured", "restored")
_TOKENS_RESTORE_STATUSES = (
    None,
    "noop-nothing-captured",
    "noop-foreign-tokens-present",
    "restored",
)


def _restore_real_qt():
    """Put the ORIGINAL Qt module objects back into ``sys.modules``.

    Runs immediately after this file's own imports complete, so the stubs are
    live only for the duration of those imports and never leak into sibling
    test modules or into the run phase. Removes only the keys this file
    planted; restores only objects it captured. Never re-imports.

    Scoped deliberately: the crash comes from *evicting* real Qt, so the swap
    happens only when real Qt was actually captured. On an interpreter with no
    PySide6 installed there is nothing to evict and nothing to corrupt — the
    stubs stay planted, which is this file's long-standing behaviour that
    several sibling panel tests import against.
    """
    global _QT_RESTORE_STATUS, _TOKENS_RESTORE_STATUS
    if not _REAL_QT_MODULES:
        # Nothing was evicted, so nothing is restored. Law 3: say so.
        _QT_RESTORE_STATUS = "noop-nothing-captured"
        return
    for _k in _QT_STUB_KEYS:
        if sys.modules.get(_k) in (pyside6, pyside6_core, pyside6_widgets, pyside6_gui):
            del sys.modules[_k]
    sys.modules.update(_REAL_QT_MODULES)
    _QT_RESTORE_STATUS = "restored"

    # Bare ``tokens``: report the outcome instead of letting setdefault hide it.
    if _REAL_BARE_TOKENS is None:
        _TOKENS_RESTORE_STATUS = "noop-nothing-captured"
    elif "tokens" in sys.modules:
        # Someone else planted a ``tokens`` while our imports ran; theirs wins
        # and ours is NOT installed. That is a noop, not a restore.
        _TOKENS_RESTORE_STATUS = "noop-foreign-tokens-present"
    else:
        sys.modules["tokens"] = _REAL_BARE_TOKENS
        _TOKENS_RESTORE_STATUS = "restored"


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

# Modules imported lazily *inside* tests below — bind them here, while the Qt
# stubs are still live, so those in-test imports hit the sys.modules cache
# instead of re-importing against restored real Qt.
import synapse.panel.styles  # noqa: F401,E402
import synapse.panel.hda_controller  # noqa: F401,E402

# Stubs have served their only purpose. Hand the real Qt modules back.
_restore_real_qt()


# ---------------------------------------------------------------------------
# Q1 regression pin
# ---------------------------------------------------------------------------

def test_capture_real_qt_rejects_file_less_stubs():
    """D2 — pins the load-bearing ``__file__`` filter in ``_capture_real_qt``.

    FAILS IF the filter is broken (dropped or inverted), because a Qt-named
    module with no ``__file__`` would then be captured as "real" and later
    handed back by ``_restore_real_qt`` as the authoritative Qt — depriving
    every sibling test that relies on this file's richer stub. Crucible's
    mutation 3d did exactly that and slipped past the old pins, which only
    observe the *result* of a capture that is empty on stock CI.

    This pin is interpreter-independent: it drives the filter with a synthetic
    module map, so it fails under the mutation on BOTH interpreters.
    """
    real = types.ModuleType("PySide6.QtCore")
    real.__file__ = r"C:\fake\PySide6\QtCore.pyd"
    foreign_stub = types.ModuleType("PySide6.QtWidgets")  # in-memory: no __file__
    bare_stub = types.ModuleType("PySide6")
    unrelated = types.ModuleType("json")
    unrelated.__file__ = "json.py"

    captured = _capture_real_qt(
        {
            "PySide6.QtCore": real,
            "PySide6.QtWidgets": foreign_stub,
            "PySide6": bare_stub,
            "json": unrelated,
        }
    )

    assert captured == {"PySide6.QtCore": real}, (
        "the __file__ filter is broken: file-less in-memory Qt stubs were "
        f"captured as real Qt -> {sorted(captured)}"
    )


def test_restore_status_reports_what_happened_not_what_was_attempted():
    """D4 — the restore bookkeeping must describe an EFFECT, not an attempt.

    FAILS IF ``_restore_real_qt()`` was never called (status still ``None``),
    or if it reports a status outside the declared vocabulary, or if it claims
    ``"restored"`` on an interpreter where nothing was ever captured (the exact
    Law-3 defect: flag set before the ``if not _REAL_QT_MODULES: return``).
    """
    assert _QT_RESTORE_STATUS is not None, "_restore_real_qt() never ran"
    assert _QT_RESTORE_STATUS in _QT_RESTORE_STATUSES, _QT_RESTORE_STATUS
    assert _TOKENS_RESTORE_STATUS in _TOKENS_RESTORE_STATUSES, _TOKENS_RESTORE_STATUS

    if _REAL_QT_MODULES:
        assert _QT_RESTORE_STATUS == "restored"
        # The tokens branch is only reachable on the restore path.
        assert _TOKENS_RESTORE_STATUS is not None
        if _TOKENS_RESTORE_STATUS == "restored":
            assert sys.modules.get("tokens") is _REAL_BARE_TOKENS
        elif _TOKENS_RESTORE_STATUS == "noop-foreign-tokens-present":
            assert sys.modules.get("tokens") is not _REAL_BARE_TOKENS
    else:
        assert _QT_RESTORE_STATUS == "noop-nothing-captured", (
            "claimed a restore on an interpreter where no real Qt was captured"
        )
        assert _TOKENS_RESTORE_STATUS is None, (
            "tokens branch reported an outcome it never reached"
        )


def test_qt_stubs_do_not_leak_past_module_import():
    """FAILS IF this module's Qt stubs are still installed in ``sys.modules``
    at run time — i.e. the module-scope plant was left un-restored, which is
    the exact condition that crashes sibling panel tests with an access
    violation.

    D3 — on an interpreter with no real PySide6 nothing is ever evicted, so
    there is no restore to observe and this check has no way to fail. A
    vacuous pass would be a lie (AGENT_CONSTITUTION Law 1), so it SKIPS with a
    reason instead. The mutation-detecting halves of this file's coverage on
    such an interpreter are the two pins above, which are interpreter-
    independent by construction.
    """
    if not _REAL_QT_MODULES:
        pytest.skip(
            "no file-backed PySide6/PySide2 on this interpreter: nothing was "
            "evicted, so the restore assertions cannot fail here (D3 — honest "
            "skip, not a vacuous pass). Covered instead by "
            "test_capture_real_qt_rejects_file_less_stubs and "
            "test_restore_status_reports_what_happened_not_what_was_attempted."
        )
    for _k in _QT_STUB_KEYS:
        assert sys.modules.get(_k) not in (
            pyside6,
            pyside6_core,
            pyside6_widgets,
            pyside6_gui,
        ), f"test stub still installed at sys.modules[{_k!r}]"
    for _k, _real in _REAL_QT_MODULES.items():
        assert sys.modules.get(_k) is _real, (
            f"sys.modules[{_k!r}] is not the ORIGINAL module object "
            "(restored by re-import instead of by reference?)"
        )


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
        """Route_chat responses (with 'response' key in data) emit response_received."""
        bridge = self._make_bridge()
        received = []
        bridge.response_received.connect(lambda d: received.append(d))

        data = {"data": {"response": "hello", "tier": "recipe"}, "success": True}
        bridge._dispatch_message(data)

        assert len(received) == 1
        assert received[0]["response"] == "hello"

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

    def test_non_chat_response_silently_dropped(self):
        """Non-chat responses (no 'response'/'tier' in data) are silently dropped."""
        bridge = self._make_bridge()
        chat_received = []
        hda_received = []
        bridge.response_received.connect(lambda d: chat_received.append(d))
        bridge.hda_progress.connect(lambda d: hda_received.append(d))

        # project_setup-style response — should NOT reach chat
        data = {"data": {"agent_state": {}, "paths": {}}, "success": True}
        bridge._dispatch_message(data)

        assert len(chat_received) == 0
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
        assert payload["type"] == "hda_package"
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
        assert bridge_call["type"] == "hda_package"
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
        assert msg["type"] == "ping"
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
