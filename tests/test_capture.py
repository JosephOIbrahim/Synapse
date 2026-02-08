"""Unit tests for _handle_capture_viewport without Houdini."""

import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock hou + hdefereval before importing handlers
# ---------------------------------------------------------------------------

_mock_hou = ModuleType("hou")
_mock_hou.ui = MagicMock()
_mock_hou.paneTabType = SimpleNamespace(SceneViewer="SceneViewer")
_mock_hou.text = MagicMock()
_mock_hou.frame = MagicMock(return_value=1)

_mock_hdefereval = ModuleType("hdefereval")
_mock_hdefereval.executeInMainThreadWithResult = staticmethod(lambda fn: fn())

sys.modules["hou"] = _mock_hou
sys.modules["hdefereval"] = _mock_hdefereval

from synapse.server.handlers import SynapseHandler  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def handler():
    return SynapseHandler()


@pytest.fixture()
def _setup_hou(tmp_path):
    """Configure hou mocks so flipbook produces a real temp file."""
    _mock_hou.text.expandString.return_value = str(tmp_path)

    mock_vp = MagicMock(name="viewport")
    mock_settings = MagicMock(name="flipbookSettings")
    mock_sv = MagicMock(name="SceneViewer")
    mock_sv.curViewport.return_value = mock_vp
    mock_sv.flipbookSettings.return_value = mock_settings

    def _write_file(*args, **kwargs):
        pattern = mock_settings.output.call_args[0][0]
        actual = pattern.replace("$F4", f"{int(_mock_hou.frame()):04d}")
        with open(actual, "wb") as f:
            f.write(b"\xff\xd8fake")

    mock_sv.flipbook.side_effect = _write_file

    desktop = MagicMock()
    desktop.paneTabOfType.return_value = mock_sv
    _mock_hou.ui.curDesktop.return_value = desktop

    return mock_sv, mock_settings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCaptureViewport:

    def test_default_jpeg(self, handler, _setup_hou):
        result = handler._handle_capture_viewport({})
        assert result["format"] == "jpeg"
        assert result["width"] == 800
        assert result["height"] == 600
        assert result["image_path"].endswith(".jpg")
        assert os.path.exists(result["image_path"])

    def test_png_format(self, handler, _setup_hou):
        result = handler._handle_capture_viewport({"format": "png", "width": 1920, "height": 1080})
        assert result["format"] == "png"
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["image_path"].endswith(".png")

    def test_dict_structure(self, handler, _setup_hou):
        result = handler._handle_capture_viewport({})
        assert set(result.keys()) == {"image_path", "width", "height", "format"}
        assert isinstance(result["image_path"], str)
        assert isinstance(result["width"], int)
        assert isinstance(result["height"], int)
        assert isinstance(result["format"], str)

    def test_missing_scene_viewer_raises(self, handler, tmp_path):
        _mock_hou.text.expandString.return_value = str(tmp_path)
        desktop = MagicMock()
        desktop.paneTabOfType.return_value = None
        _mock_hou.ui.curDesktop.return_value = desktop

        with pytest.raises(ValueError, match="No SceneViewer"):
            handler._handle_capture_viewport({})

    def test_param_alias_fmt(self, handler, _setup_hou):
        """'fmt' should resolve to 'format'."""
        result = handler._handle_capture_viewport({"fmt": "png"})
        assert result["format"] == "png"
        assert result["image_path"].endswith(".png")

    def test_flipbook_settings_called(self, handler, _setup_hou):
        mock_sv, mock_settings = _setup_hou
        handler._handle_capture_viewport({"width": 1280, "height": 720})

        mock_settings.useResolution.assert_called_once_with(True)
        mock_settings.resolution.assert_called_once_with((1280, 720))
        mock_sv.flipbook.assert_called_once()

    def test_file_not_created_raises(self, handler, tmp_path):
        """If flipbook doesn't produce a file, RuntimeError is raised."""
        _mock_hou.text.expandString.return_value = str(tmp_path)

        mock_sv = MagicMock()
        mock_sv.curViewport.return_value = MagicMock()
        mock_sv.flipbookSettings.return_value = MagicMock()
        mock_sv.flipbook.side_effect = lambda **kw: None

        desktop = MagicMock()
        desktop.paneTabOfType.return_value = mock_sv
        _mock_hou.ui.curDesktop.return_value = desktop

        with pytest.raises(RuntimeError, match="file not found"):
            handler._handle_capture_viewport({})
