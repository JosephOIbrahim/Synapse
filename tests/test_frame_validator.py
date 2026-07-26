"""Tests for the synapse_validate_frame handler (Frame Validator).

Mock-based -- no Houdini or OpenImageIO required.
Covers all 6 validation checks, integration scenarios, aliases,
threshold overrides, and OIIO graceful degradation.
"""

import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load handlers without Houdini
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    sys.modules["hdefereval"] = types.ModuleType("hdefereval")

_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _base / "core" / "protocol.py"),
    ("synapse.core.aliases", _base / "core" / "aliases.py"),
    ("synapse.server.handlers", _base / "server" / "handlers.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]


# ---------------------------------------------------------------------------
# OIIO mock helper
# ---------------------------------------------------------------------------

def _make_oiio_mock(
    width=1920, height=1080, channels=3, format_str="float",
    avg=None, nancount=None, infcount=None, pixels=None,
):
    """Create a mock OpenImageIO module with configurable stats and pixels.

    Args:
        avg: Per-channel average values (list of floats). Default: [0.5] * channels.
        nancount: Per-channel NaN counts. Default: [0] * channels.
        infcount: Per-channel Inf counts. Default: [0] * channels.
        pixels: numpy array for get_pixels(). If None, creates uniform array from avg.
    """
    import numpy as np

    if avg is None:
        avg = [0.5] * channels
    if nancount is None:
        nancount = [0] * channels
    if infcount is None:
        infcount = [0] * channels

    oiio = types.ModuleType("OpenImageIO")

    # FLOAT type constant
    oiio.FLOAT = "float"

    # geterror
    oiio.geterror = MagicMock(return_value="")

    # ImageInput
    mock_spec = MagicMock()
    mock_spec.width = width
    mock_spec.height = height
    mock_spec.nchannels = channels
    mock_spec.format = format_str

    mock_input = MagicMock()
    mock_input.spec.return_value = mock_spec

    oiio.ImageInput = MagicMock()
    oiio.ImageInput.open = MagicMock(return_value=mock_input)

    # ImageBuf
    mock_buf = MagicMock()
    if pixels is None:
        # Create uniform pixel array from avg values
        pixels = np.full((height, width, channels), 0.0, dtype=np.float32)
        for c in range(channels):
            pixels[:, :, c] = avg[c]
    mock_buf.get_pixels = MagicMock(return_value=pixels)

    oiio.ImageBuf = MagicMock(return_value=mock_buf)

    # ImageBufAlgo.computePixelStats
    mock_stats = MagicMock()
    mock_stats.avg = avg
    mock_stats.nancount = nancount
    mock_stats.infcount = infcount

    oiio.ImageBufAlgo = MagicMock()
    oiio.ImageBufAlgo.computePixelStats = MagicMock(return_value=mock_stats)

    return oiio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    return h


@pytest.fixture
def valid_image(tmp_path):
    """Create a non-empty temp file to pass file_integrity checks."""
    img = tmp_path / "test_render.exr"
    img.write_bytes(b"\x00" * 1024)
    return str(img)


@pytest.fixture
def empty_image(tmp_path):
    """Create a 0-byte temp file."""
    img = tmp_path / "empty_render.exr"
    img.write_bytes(b"")
    return str(img)


# ---------------------------------------------------------------------------
# Tests: File Integrity
# ---------------------------------------------------------------------------

class TestFileIntegrity:
    def test_missing_file(self, handler):
        result = handler._handle_validate_frame({
            "image_path": "/nonexistent/path/render.exr",
        })
        assert result["valid"] is False
        assert result["checks"]["file_integrity"]["passed"] is False
        assert "not found" in result["checks"]["file_integrity"]["detail"].lower()

    def test_empty_file(self, handler, empty_image):
        result = handler._handle_validate_frame({
            "image_path": empty_image,
        })
        assert result["valid"] is False
        assert result["checks"]["file_integrity"]["passed"] is False
        assert "empty" in result["checks"]["file_integrity"]["detail"].lower()

    def test_oiio_unavailable_graceful_degradation(self, handler, valid_image):
        """When OIIO is not installed, return file-integrity-only results."""
        with patch.dict(sys.modules, {"OpenImageIO": None, "oiio": None}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
            })
        assert result["oiio_available"] is False
        assert result["checks"]["file_integrity"]["passed"] is True
        # No pixel-based checks should appear
        assert "black_frame" not in result["checks"]

    def test_valid_file_passes_integrity(self, handler, valid_image):
        """A non-empty file should pass the integrity check."""
        oiio_mock = _make_oiio_mock()
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["file_integrity"],
            })
        assert result["checks"]["file_integrity"]["passed"] is True


# ---------------------------------------------------------------------------
# Tests: Black Frame
# ---------------------------------------------------------------------------

class TestBlackFrame:
    def test_all_black_detected(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(avg=[0.0, 0.0, 0.0])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["black_frame"],
            })
        assert result["checks"]["black_frame"]["passed"] is False
        assert "black" in result["checks"]["black_frame"]["detail"].lower()

    def test_normal_frame_passes(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(avg=[0.3, 0.25, 0.2])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["black_frame"],
            })
        assert result["checks"]["black_frame"]["passed"] is True

    def test_near_black_uses_threshold(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(avg=[0.0005, 0.0005, 0.0005])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["black_frame"],
            })
        assert result["checks"]["black_frame"]["passed"] is False


# ---------------------------------------------------------------------------
# Tests: NaN Check
# ---------------------------------------------------------------------------

class TestNaN:
    def test_nan_detected(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(nancount=[100, 0, 0], infcount=[0, 0, 0])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["nan_check"],
            })
        assert result["checks"]["nan_check"]["passed"] is False
        assert "NaN" in result["checks"]["nan_check"]["detail"]

    def test_inf_detected(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(nancount=[0, 0, 0], infcount=[0, 50, 0])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["nan_check"],
            })
        assert result["checks"]["nan_check"]["passed"] is False
        assert "Inf" in result["checks"]["nan_check"]["detail"]

    def test_clean_float_passes(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(nancount=[0, 0, 0], infcount=[0, 0, 0])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["nan_check"],
            })
        assert result["checks"]["nan_check"]["passed"] is True

    def test_combined_nan_and_inf(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(nancount=[10, 0, 0], infcount=[0, 5, 0])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["nan_check"],
            })
        assert result["checks"]["nan_check"]["passed"] is False
        assert result["checks"]["nan_check"]["value"] == 15


# ---------------------------------------------------------------------------
# Tests: Clipping
# ---------------------------------------------------------------------------

class TestClipping:
    def test_overexposure_detected(self, handler, valid_image):
        import numpy as np
        # 5% of pixels at 1.0 (clipped)
        pixels = np.full((100, 100, 3), 0.5, dtype=np.float32)
        pixels[:5, :, :] = 1.0  # 5% clipped
        oiio_mock = _make_oiio_mock(
            width=100, height=100, avg=[0.5, 0.5, 0.5], pixels=pixels,
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["clipping"],
            })
        assert result["checks"]["clipping"]["passed"] is False
        assert result["checks"]["clipping"]["value"] > 0.5

    def test_normal_range_passes(self, handler, valid_image):
        import numpy as np
        pixels = np.full((100, 100, 3), 0.5, dtype=np.float32)
        oiio_mock = _make_oiio_mock(
            width=100, height=100, avg=[0.5, 0.5, 0.5], pixels=pixels,
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["clipping"],
            })
        assert result["checks"]["clipping"]["passed"] is True


# ---------------------------------------------------------------------------
# Tests: Underexposure
# ---------------------------------------------------------------------------

class TestUnderexposure:
    def test_too_dark_detected(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(avg=[0.01, 0.01, 0.01])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["underexposure"],
            })
        assert result["checks"]["underexposure"]["passed"] is False
        assert "underexposed" in result["checks"]["underexposure"]["detail"].lower()

    def test_adequate_exposure_passes(self, handler, valid_image):
        oiio_mock = _make_oiio_mock(avg=[0.3, 0.25, 0.2])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["underexposure"],
            })
        assert result["checks"]["underexposure"]["passed"] is True


# ---------------------------------------------------------------------------
# Tests: Saturation (Fireflies)
# ---------------------------------------------------------------------------

class TestSaturation:
    def test_fireflies_detected(self, handler, valid_image):
        import numpy as np
        # Mean ~0.3, but 2% of pixels at 50.0 (>> 10x mean)
        pixels = np.full((100, 100, 3), 0.3, dtype=np.float32)
        pixels[:2, :, :] = 50.0  # 2% fireflies
        oiio_mock = _make_oiio_mock(
            width=100, height=100, avg=[0.3, 0.3, 0.3], pixels=pixels,
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["saturation"],
            })
        assert result["checks"]["saturation"]["passed"] is False

    def test_smooth_image_passes(self, handler, valid_image):
        import numpy as np
        pixels = np.full((100, 100, 3), 0.3, dtype=np.float32)
        oiio_mock = _make_oiio_mock(
            width=100, height=100, avg=[0.3, 0.3, 0.3], pixels=pixels,
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["saturation"],
            })
        assert result["checks"]["saturation"]["passed"] is True


# ---------------------------------------------------------------------------
# Tests: Integration
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_all_pass_valid_true(self, handler, valid_image):
        import numpy as np
        pixels = np.full((100, 100, 3), 0.3, dtype=np.float32)
        oiio_mock = _make_oiio_mock(
            width=100, height=100, avg=[0.3, 0.3, 0.3], pixels=pixels,
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
            })
        assert result["valid"] is True
        assert result["summary"] == "Frame looks good"
        assert result["oiio_available"] is True

    def test_multiple_failures(self, handler, valid_image):
        import numpy as np
        # Black frame + NaN
        pixels = np.full((100, 100, 3), 0.0, dtype=np.float32)
        oiio_mock = _make_oiio_mock(
            width=100, height=100, avg=[0.0, 0.0, 0.0],
            nancount=[10, 0, 0], infcount=[0, 0, 0],
            pixels=pixels,
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
            })
        assert result["valid"] is False
        assert "black_frame" in result["summary"]
        assert "nan_check" in result["summary"]

    def test_selective_checks(self, handler, valid_image):
        """Only run requested checks."""
        oiio_mock = _make_oiio_mock(avg=[0.3, 0.3, 0.3])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["black_frame", "nan_check"],
            })
        assert "black_frame" in result["checks"]
        assert "nan_check" in result["checks"]
        assert "clipping" not in result["checks"]
        assert "saturation" not in result["checks"]
        assert "underexposure" not in result["checks"]

    def test_invalid_check_name_raises(self, handler, valid_image):
        with pytest.raises(ValueError, match="Unknown check"):
            handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["black_frame", "fake_check"],
            })

    def test_threshold_overrides(self, handler, valid_image):
        """Custom threshold should change pass/fail boundary."""
        # Mean is 0.03 -- default underexposure threshold is 0.05 (would fail)
        oiio_mock = _make_oiio_mock(avg=[0.03, 0.03, 0.03])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            # With lowered threshold, it should pass
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["underexposure"],
                "thresholds": {"underexposure_mean": 0.01},
            })
        assert result["checks"]["underexposure"]["passed"] is True

    def test_output_keys_present(self, handler, valid_image):
        import numpy as np
        pixels = np.full((100, 100, 3), 0.3, dtype=np.float32)
        oiio_mock = _make_oiio_mock(
            width=100, height=100, channels=3, format_str="float",
            avg=[0.3, 0.3, 0.3], pixels=pixels,
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
            })
        expected_keys = {"valid", "image_path", "resolution", "channels",
                         "format", "checks", "summary", "oiio_available"}
        assert set(result.keys()) == expected_keys

    def test_sorted_check_keys_he2025(self, handler, valid_image):
        """Checks dict keys must be sorted (He2025 determinism)."""
        import numpy as np
        pixels = np.full((100, 100, 3), 0.3, dtype=np.float32)
        oiio_mock = _make_oiio_mock(
            width=100, height=100, avg=[0.3, 0.3, 0.3], pixels=pixels,
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
            })
        check_keys = list(result["checks"].keys())
        assert check_keys == sorted(check_keys)

    def test_resolution_and_format_returned(self, handler, valid_image):
        import numpy as np
        pixels = np.full((100, 100, 3), 0.3, dtype=np.float32)
        oiio_mock = _make_oiio_mock(
            width=1920, height=1080, channels=4, format_str="half",
            avg=[0.3, 0.3, 0.3, 1.0], pixels=np.full((1080, 1920, 4), 0.3, dtype=np.float32),
        )
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "checks": ["black_frame"],
            })
        assert result["resolution"] == [1920, 1080]
        assert result["channels"] == 4
        assert result["format"] == "half"

    def test_oiio_open_failure(self, handler, valid_image):
        """If OIIO can't open the file, return file_integrity failure."""
        oiio_mock = _make_oiio_mock()
        oiio_mock.ImageInput.open = MagicMock(return_value=None)
        oiio_mock.geterror = MagicMock(return_value="Unsupported format")
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
            })
        assert result["valid"] is False
        assert "file_integrity" in result["checks"]
        assert result["checks"]["file_integrity"]["passed"] is False


# ---------------------------------------------------------------------------
# Tests: Aliases
# ---------------------------------------------------------------------------

class TestAliases:
    def test_image_alias_resolves(self, handler, valid_image):
        """'image' should resolve to 'image_path'."""
        oiio_mock = _make_oiio_mock(avg=[0.3, 0.3, 0.3])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image": valid_image,
                "checks": ["black_frame"],
            })
        assert result["checks"]["black_frame"]["passed"] is True

    def test_validations_alias_resolves(self, handler, valid_image):
        """'validations' should resolve to 'checks'."""
        oiio_mock = _make_oiio_mock(avg=[0.3, 0.3, 0.3])
        with patch.dict(sys.modules, {"OpenImageIO": oiio_mock}):
            result = handler._handle_validate_frame({
                "image_path": valid_image,
                "validations": ["black_frame"],
            })
        assert "black_frame" in result["checks"]
        assert "nan_check" not in result["checks"]

    def test_missing_image_path_raises(self, handler):
        """Missing required image_path should raise ValueError."""
        with pytest.raises(ValueError, match="Missing required parameter"):
            handler._handle_validate_frame({})
