"""Tests for render farm handler integration — verifies the MCP handler
layer wires correctly to RenderFarmOrchestrator.

Mock-based — no Houdini required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: ensure synapse package structure is importable
# ---------------------------------------------------------------------------

_root = Path(__file__).resolve().parent.parent / "python"

for mod_name, mod_path in [
    ("synapse", _root / "synapse"),
    ("synapse.core", _root / "synapse" / "core"),
    ("synapse.server", _root / "synapse" / "server"),
    ("synapse.memory", _root / "synapse" / "memory"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.determinism", _root / "synapse" / "core" / "determinism.py"),
    ("synapse.core.aliases", _root / "synapse" / "core" / "aliases.py"),
    ("synapse.memory.models", _root / "synapse" / "memory" / "models.py"),
    ("synapse.server.render_diagnostics", _root / "synapse" / "server" / "render_diagnostics.py"),
    ("synapse.server.render_notify", _root / "synapse" / "server" / "render_notify.py"),
    ("synapse.server.render_farm", _root / "synapse" / "server" / "render_farm.py"),
    ("synapse.server.handlers_usd", _root / "synapse" / "server" / "handlers_usd.py"),
    ("synapse.server.handlers_render", _root / "synapse" / "server" / "handlers_render.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

render_handlers_mod = sys.modules["synapse.server.handlers_render"]
farm_mod = sys.modules["synapse.server.render_farm"]

RenderHandlerMixin = render_handlers_mod.RenderHandlerMixin
RenderFarmOrchestrator = farm_mod.RenderFarmOrchestrator
RenderCallbacks = farm_mod.RenderCallbacks
BatchReport = sys.modules["synapse.server.render_notify"].BatchReport


# ---------------------------------------------------------------------------
# Helper: create a minimal handler instance with the mixin
# ---------------------------------------------------------------------------

def _make_handler():
    """Create a RenderHandlerMixin instance with mocked dependencies."""
    handler = RenderHandlerMixin()
    # Mock the existing handlers that the render farm callbacks wire to
    handler._handle_render = MagicMock(return_value={
        "image_path": "/tmp/frame.0001.exr", "rop": "/stage/karma1",
    })
    handler._handle_validate_frame = MagicMock(return_value={
        "valid": True, "checks": {},
    })
    handler._handle_render_settings = MagicMock(return_value={
        "settings": {"pathtracedsamples": 64},
    })
    handler._handle_get_stage_info = MagicMock(return_value={"prims": []})
    handler._broadcast = MagicMock()
    handler._memory = None
    return handler


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHandleRenderSequence:
    """Test _handle_render_sequence handler method."""

    def test_basic_sequence(self):
        """Verify orchestrator receives correct params and returns report dict."""
        handler = _make_handler()

        mock_report = BatchReport(
            start_frame=1, end_frame=3, total_frames=3, rop_path="/stage/karma1",
        )
        mock_report.completed_frames = 3
        mock_report.failed_frames = 0

        with patch.object(
            RenderFarmOrchestrator, "render_sequence", return_value=mock_report
        ) as mock_seq:
            result = handler._handle_render_sequence({
                "start_frame": 1,
                "end_frame": 3,
                "rop": "/stage/karma1",
            })

        # Orchestrator was called with correct frame range
        mock_seq.assert_called_once()
        call_kwargs = mock_seq.call_args
        assert call_kwargs[1]["frame_range"] == (1, 3)
        assert call_kwargs[1]["step"] == 1

        # Result is a dict (from to_dict())
        assert isinstance(result, dict)
        assert result["start_frame"] == 1
        assert result["end_frame"] == 3

    def test_default_parameters(self):
        """Verify defaults for step, auto_fix, max_retries."""
        handler = _make_handler()

        mock_report = BatchReport(
            start_frame=1, end_frame=5, total_frames=5, rop_path="",
        )

        with patch.object(
            RenderFarmOrchestrator, "render_sequence", return_value=mock_report
        ):
            result = handler._handle_render_sequence({
                "start_frame": 1,
                "end_frame": 5,
            })

        # Singleton orchestrator was created
        assert hasattr(handler, '_render_farm')
        assert handler._render_farm is not None
        # Defaults applied
        assert handler._render_farm._max_retries == 3
        assert handler._render_farm._auto_fix is True

    def test_custom_parameters(self):
        """Verify custom step/auto_fix/max_retries pass through."""
        handler = _make_handler()

        mock_report = BatchReport(
            start_frame=1, end_frame=10, total_frames=5, rop_path="/stage/karma1",
        )

        with patch.object(
            RenderFarmOrchestrator, "render_sequence", return_value=mock_report
        ) as mock_seq:
            result = handler._handle_render_sequence({
                "start_frame": 1,
                "end_frame": 10,
                "step": 2,
                "auto_fix": False,
                "max_retries": 5,
            })

        call_kwargs = mock_seq.call_args
        assert call_kwargs[1]["step"] == 2

    def test_singleton_reuse(self):
        """Verify orchestrator is reused across calls."""
        handler = _make_handler()

        mock_report = BatchReport(
            start_frame=1, end_frame=2, total_frames=2, rop_path="",
        )

        with patch.object(
            RenderFarmOrchestrator, "render_sequence", return_value=mock_report
        ):
            handler._handle_render_sequence({"start_frame": 1, "end_frame": 2})
            farm1 = handler._render_farm
            handler._handle_render_sequence({"start_frame": 3, "end_frame": 4})
            farm2 = handler._render_farm

        assert farm1 is farm2


class TestHandleRenderFarmStatus:
    """Test _handle_render_farm_status handler method."""

    def test_idle_status(self):
        """No running job returns idle status."""
        handler = _make_handler()
        result = handler._handle_render_farm_status({})
        assert result == {"running": False, "cancelled": False, "scene_tags": []}

    def test_running_status(self):
        """Mock running job returns status from orchestrator."""
        handler = _make_handler()
        mock_farm = MagicMock()
        mock_farm.get_status.return_value = {
            "running": True, "cancelled": False, "scene_tags": ["has_volumes"],
        }
        handler._render_farm = mock_farm

        result = handler._handle_render_farm_status({})
        assert result["running"] is True
        assert "has_volumes" in result["scene_tags"]


class TestHandlerRegistration:
    """Test that both commands are registered in handlers.py."""

    def test_handlers_registered(self):
        """Verify render_sequence and render_farm_status are in the registry."""
        # Load handlers.py to check registration
        handlers_path = _root / "synapse" / "server" / "handlers.py"

        with open(handlers_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert 'reg.register("render_sequence"' in source
        assert 'reg.register("render_farm_status"' in source
