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


# ---------------------------------------------------------------------------
# hou stub
# ---------------------------------------------------------------------------

def _make_hou_stub():
    """Create a minimal hou stub with undos support."""
    hou = types.ModuleType("hou")
    hou.node = MagicMock()
    hou.hipFile = MagicMock()
    hou.applicationVersion = MagicMock(return_value=(21, 0, 596))
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
    """Import handlers module via importlib (bypasses hou dependency)."""
    import importlib
    # Ensure fresh import picks up our hou stub
    for mod_name in list(sys.modules):
        if "synapse" in mod_name:
            del sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(
        "synapse.server.handlers",
        r"C:\Users\User\SYNAPSE\python\synapse\server\handlers.py",
        submodule_search_locations=[],
    )
    # We need the package hierarchy for relative imports
    import synapse  # noqa: F811
    return importlib.import_module("synapse.server.handlers")


def _get_handler_instance():
    """Return a SynapseHandler instance."""
    handlers_mod = _load_handlers()
    return handlers_mod.SynapseHandler()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUndoHandler:
    """Tests for the undo handler."""

    def test_undo_handler_calls_performUndo(self, _hou_stub):
        """_handle_undo should call hou.undos.performUndo()."""
        handler = _get_handler_instance()
        handlers_mod = sys.modules["synapse.server.handlers"]
        _handlers_hou = handlers_mod.hou
        with patch.object(_handlers_hou.undos, "performUndo") as mock_undo:
            result = handler._handle_undo({})
            mock_undo.assert_called_once()

    def test_undo_returns_status(self, _hou_stub):
        """_handle_undo should return a dict with status and message."""
        handler = _get_handler_instance()
        result = handler._handle_undo({})
        assert result["status"] == "ok"
        assert "Undid" in result["message"]

    def test_undo_registered_in_handlers(self, _hou_stub):
        """undo should be registered in the handler registry."""
        handler = _get_handler_instance()
        assert "undo" in handler._registry.registered_types


class TestRedoHandler:
    """Tests for the redo handler."""

    def test_redo_handler_calls_performRedo(self, _hou_stub):
        """_handle_redo should call hou.undos.performRedo()."""
        handler = _get_handler_instance()
        handlers_mod = sys.modules["synapse.server.handlers"]
        _handlers_hou = handlers_mod.hou
        with patch.object(_handlers_hou.undos, "performRedo") as mock_redo:
            result = handler._handle_redo({})
            mock_redo.assert_called_once()

    def test_redo_returns_status(self, _hou_stub):
        """_handle_redo should return a dict with status and message."""
        handler = _get_handler_instance()
        result = handler._handle_redo({})
        assert result["status"] == "ok"
        assert "Redid" in result["message"]

    def test_redo_registered_in_handlers(self, _hou_stub):
        """redo should be registered in the handler registry."""
        handler = _get_handler_instance()
        assert "redo" in handler._registry.registered_types
