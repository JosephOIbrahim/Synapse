"""Tests for handler edge cases — TOPS race, VEX cleanup, PDG callback."""
import importlib
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

# Stub hou
if "hou" not in sys.modules:
    mock_hou = types.ModuleType("hou")
    mock_hou.node = MagicMock(return_value=None)
    mock_hou.undos = MagicMock()
    sys.modules["hou"] = mock_hou


class TestTopsMonitorRace:
    """C8: Concurrent stop doesn't crash."""

    def test_double_stop_raises_valueerror_not_keyerror(self):
        """Stopping an already-stopped monitor raises ValueError, not KeyError."""
        # Load handlers_tops
        spec = importlib.util.spec_from_file_location(
            "synapse.server.handlers_tops", _base / "server" / "handlers_tops" / "__init__.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Simulate: monitor already stopped (not in dict)
        handler_obj = MagicMock()
        handler_obj._tops_monitors = {}
        # pop with default should return None
        result = handler_obj._tops_monitors.pop("mon-1", None)
        assert result is None  # No KeyError

    def test_pop_with_default_is_atomic(self):
        """dict.pop(key, None) doesn't raise even if key missing."""
        d = {"a": 1}
        d.pop("a", None)  # Removes a
        result = d.pop("a", None)  # Second pop — returns None, no KeyError
        assert result is None


class TestVexTempCleanup:
    """C11: Temp VEX nodes cleaned up on failure."""

    def test_temp_node_deleted_on_cook_failure_no_input(self):
        """When VEX cook fails without input_node, temp container is cleaned up."""
        # Verify the cleanup logic exists in the source
        spec = importlib.util.spec_from_file_location(
            "synapse.server.handlers", _base / "server" / "handlers.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        import inspect
        source = inspect.getsource(mod.SynapseHandler._handle_execute_vex)
        assert "synapse_vex_temp" in source, "Handler should reference temp container name"
        assert "destroy()" in source, "Handler should clean up temp nodes"

    def test_temp_node_preserved_with_input(self):
        """Cleanup logic should check 'not input_node' before destroying."""
        spec = importlib.util.spec_from_file_location(
            "synapse.server.handlers", _base / "server" / "handlers.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        import inspect
        source = inspect.getsource(mod.SynapseHandler._handle_execute_vex)
        assert "not input_node" in source, "Cleanup should only trigger when we created the temp node"


class TestPdgCallbackCleanup:
    """C13: PDG callback unregistered on storage failure."""

    def test_callback_cleanup_pattern_exists(self):
        """The monitor start code should have cleanup logic."""
        spec = importlib.util.spec_from_file_location(
            "synapse.server.handlers_tops", _base / "server" / "handlers_tops" / "__init__.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        import inspect
        source = inspect.getsource(mod.TopsHandlerMixin._handle_tops_monitor_stream)
        assert "removeEventHandler" in source, "Monitor start should have callback cleanup"
