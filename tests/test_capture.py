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
_mock_hdefereval.executeInMainThreadWithResult = staticmethod(lambda fn, *args, **kwargs: fn(*args, **kwargs))

if "hou" not in sys.modules:  # defer to conftest's canonical hou resident
    sys.modules["hou"] = _mock_hou
if "hdefereval" not in sys.modules:
    sys.modules["hdefereval"] = _mock_hdefereval

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_render as _hr  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _wire_handler_module(monkeypatch):
    """Point the handler module at THIS file's fakes. In a full-suite run the
    resident sys.modules['hou'] is whichever test file planted first (and its
    skeleton may lack .ui/.paneTabType), so residency alone is order-fragile."""
    monkeypatch.setattr(_hr, "hou", _mock_hou)
    monkeypatch.setattr(_hr, "HOU_AVAILABLE", True)
    monkeypatch.setitem(sys.modules, "hdefereval", _mock_hdefereval)


@pytest.fixture()
def handler():
    return SynapseHandler()


@pytest.fixture()
def _setup_hou(tmp_path):
    """Configure hou mocks so flipbook produces a real temp file."""
    _mock_hou.text.expandString.return_value = str(tmp_path)
    _mock_hou.frame.return_value = 1001

    mock_vp = MagicMock(name="viewport")
    mock_vp.cameraPath.return_value = "/obj/cam1"
    mock_vp.name.return_value = "persp1"
    mock_settings = MagicMock(name="flipbookSettings")
    mock_sv = MagicMock(name="SceneViewer")
    mock_sv.name.return_value = "sceneviewer1"
    mock_sv.curViewport.return_value = mock_vp
    mock_sv.flipbookSettings.return_value = mock_settings

    def _write_file(*args, **kwargs):
        pattern = mock_settings.output.call_args[0][0]
        actual = pattern.replace("$F4", f"{int(_mock_hou.frame()):04d}")
        with open(actual, "wb") as f:
            f.write(b"\xff\xd8fake")

    mock_sv.flipbook.side_effect = _write_file

    desktop = MagicMock()
    desktop.name.return_value = "desktop1"
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
        assert set(result.keys()) == {
            "image_path", "width", "height", "format",
            "frame", "camera", "viewport", "pixel_check",
        }
        assert isinstance(result["image_path"], str)
        assert isinstance(result["width"], int)
        assert isinstance(result["height"], int)
        assert isinstance(result["format"], str)
        assert isinstance(result["frame"], int)

    def test_missing_scene_viewer_raises(self, handler, tmp_path):
        _mock_hou.text.expandString.return_value = str(tmp_path)
        desktop = MagicMock()
        desktop.paneTabOfType.return_value = None
        _mock_hou.ui.curDesktop.return_value = desktop

        with pytest.raises(ValueError, match="Couldn't find a viewport"):
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

        with pytest.raises(RuntimeError, match="image wasn't created"):
            handler._handle_capture_viewport({})


# ---------------------------------------------------------------------------
# R-021: the capture proves what it saw -- identity, pixel verdict, max size
# ---------------------------------------------------------------------------

class TestCaptureProvenance:

    def test_reports_camera_frame_and_viewport(self, handler, _setup_hou):
        result = handler._handle_capture_viewport({})
        assert result["frame"] == 1001
        assert result["camera"] == "/obj/cam1"
        assert result["viewport"] == {
            "desktop": "desktop1",
            "pane": "sceneviewer1",
            "viewport": "persp1",
        }

    def test_pixel_check_ok(self, handler, _setup_hou, monkeypatch):
        monkeypatch.setattr(
            _hr, "_capture_channel_means", lambda path: [0.4, 0.4, 0.4]
        )
        result = handler._handle_capture_viewport({})
        check = result["pixel_check"]
        assert check["checked"] is True
        assert check["verdict"] == "ok"
        assert check["mean_luminance"] == pytest.approx(0.4, abs=1e-6)
        assert check["file_size_bytes"] > 0

    def test_black_capture_returns_possible_black_frame(
        self, handler, _setup_hou, monkeypatch
    ):
        monkeypatch.setattr(
            _hr, "_capture_channel_means", lambda path: [0.0, 0.0, 0.0]
        )
        result = handler._handle_capture_viewport({})
        check = result["pixel_check"]
        assert check["checked"] is True
        assert check["verdict"] == "possible_black_frame"
        assert check["mean_luminance"] == 0.0
        assert "reason" in check

    def test_threshold_boundary_counts_as_black(
        self, handler, _setup_hou, monkeypatch
    ):
        monkeypatch.setattr(
            _hr, "_capture_channel_means",
            lambda path: [0.01, 0.01, 0.01],
        )
        result = handler._handle_capture_viewport({})
        assert result["pixel_check"]["verdict"] == "possible_black_frame"

    def test_pixel_check_unchecked_without_reader(
        self, handler, _setup_hou, monkeypatch
    ):
        monkeypatch.setattr(_hr, "_capture_channel_means", lambda path: None)
        result = handler._handle_capture_viewport({})
        check = result["pixel_check"]
        assert check["checked"] is False
        assert check["verdict"] == "unchecked"
        assert "reason" in check

    def test_resolution_above_max_refused_before_flipbook(
        self, handler, _setup_hou
    ):
        mock_sv, _settings = _setup_hou
        with pytest.raises(ValueError, match="exceeds the 8192px maximum"):
            handler._handle_capture_viewport({
                "width": _hr._CAPTURE_MAX_DIMENSION + 1,
                "height": 600,
            })
        mock_sv.flipbook.assert_not_called()

    def test_nonpositive_resolution_refused(self, handler, _setup_hou):
        with pytest.raises(ValueError, match="at least 1 pixel"):
            handler._handle_capture_viewport({"width": 0, "height": 600})
