"""
Tests for houdini_undo and houdini_redo MCP tools.

Validates handler registration, hou.undos dispatch, and return shape.
"""

import importlib
import importlib.util
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from conftest import HOUDINI_BUILD_TUPLE


# ---------------------------------------------------------------------------
# hou stub
# ---------------------------------------------------------------------------

def _make_hou_stub():
    """Create a minimal hou stub with undos support."""
    hou = types.ModuleType("hou")
    hou.node = MagicMock()
    hou.hipFile = MagicMock()
    hou.applicationVersion = MagicMock(return_value=HOUDINI_BUILD_TUPLE)
    hou.fps = MagicMock(return_value=24.0)
    hou.playbar = MagicMock()
    hou.selectedNodes = MagicMock(return_value=[])
    hou.hscript = MagicMock(return_value=("", ""))
    hou.NodeTypeCategory = MagicMock()
    hou.nodeTypeCategories = MagicMock(return_value={})
    hou.OperationFailed = type("OperationFailed", (Exception,), {})
    hou.NodeError = type("NodeError", (Exception,), {})
    hou.Error = type("Error", (Exception,), {})
    hou.parm = MagicMock
    hou.Parm = MagicMock
    hou.session = types.ModuleType("hou.session")
    hou.ui = MagicMock()
    # Undo support
    undos = MagicMock()
    undos.performUndo = MagicMock()
    undos.performRedo = MagicMock()
    hou.undos = undos
    return hou


@pytest.fixture(autouse=True)
def _hou_stub():
    """Install hou stub before importing handlers, restore after."""
    original = sys.modules.get("hou")
    stub = _make_hou_stub()
    sys.modules["hou"] = stub
    yield stub
    if original is not None:
        sys.modules["hou"] = original
    else:
        sys.modules.pop("hou", None)


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

def _load_handlers():
    """Import a FRESH handlers module under the resident hou stub, then restore
    the session's synapse module graph.

    The fresh import is needed so handlers binds our stub (a cached module
    would keep whatever hou it saw first). But leaving the swap in place
    bifurcates module identities for every later test file (the repo's
    fake-residency trap: a test module's collection-time class references
    point at the OLD modules while monkeypatches land on the NEW ones) — so
    save and restore, same pattern as test_routing's handler test.
    """
    import importlib
    saved = {m: sys.modules.pop(m) for m in list(sys.modules) if "synapse" in m}
    try:
        # We need the package hierarchy for relative imports
        import synapse  # noqa: F811
        return importlib.import_module("synapse.server.handlers")
    finally:
        for mod_name in [m for m in list(sys.modules) if "synapse" in m]:
            del sys.modules[mod_name]
        sys.modules.update(saved)


def _get_handler_instance():
    """Return (SynapseHandler instance, the fresh handlers module).

    The module comes back explicitly because sys.modules is restored by
    _load_handlers — the fresh module is NOT resident there.
    """
    handlers_mod = _load_handlers()
    return handlers_mod.SynapseHandler(), handlers_mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUndoHandler:
    """Tests for the undo handler."""

    def test_undo_handler_calls_performUndo(self, _hou_stub):
        """_handle_undo should call hou.undos.performUndo()."""
        handler, handlers_mod = _get_handler_instance()
        _handlers_hou = handlers_mod.hou
        with patch.object(_handlers_hou.undos, "performUndo") as mock_undo:
            result = handler._handle_undo({})
            mock_undo.assert_called_once()

    def test_undo_returns_status(self, _hou_stub):
        """_handle_undo should return a dict with status and message."""
        handler, _ = _get_handler_instance()
        result = handler._handle_undo({})
        assert result["status"] == "ok"
        assert "Undid" in result["message"]

    def test_undo_registered_in_handlers(self, _hou_stub):
        """undo should be registered in the handler registry."""
        handler, _ = _get_handler_instance()
        assert "undo" in handler._registry.registered_types


class TestRedoHandler:
    """Tests for the redo handler."""

    def test_redo_handler_calls_performRedo(self, _hou_stub):
        """_handle_redo should call hou.undos.performRedo()."""
        handler, handlers_mod = _get_handler_instance()
        _handlers_hou = handlers_mod.hou
        with patch.object(_handlers_hou.undos, "performRedo") as mock_redo:
            result = handler._handle_redo({})
            mock_redo.assert_called_once()

    def test_redo_returns_status(self, _hou_stub):
        """_handle_redo should return a dict with status and message."""
        handler, _ = _get_handler_instance()
        result = handler._handle_redo({})
        assert result["status"] == "ok"
        assert "Redid" in result["message"]

    def test_redo_registered_in_handlers(self, _hou_stub):
        """redo should be registered in the handler registry."""
        handler, _ = _get_handler_instance()
        assert "redo" in handler._registry.registered_types
