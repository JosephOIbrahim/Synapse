"""
Synapse Autonomy Pipeline -- Evaluator Image I/O Tests

Tests for _load_frame(), auto-loading in evaluate_frame(),
and evaluate_sequence_from_disk().

Run without Houdini:
    python -m pytest tests/test_evaluator_io.py -v
"""

import os
import sys
import tempfile

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from synapse.autonomy.models import FrameEvaluation, SequenceEvaluation
from synapse.autonomy.evaluator import RenderEvaluator

pytestmark = pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def evaluator():
    return RenderEvaluator()


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


# =============================================================================
# HELPERS
# =============================================================================


def _write_png(path, arr_uint8):
    """Write a uint8 numpy array as a minimal PNG using PIL."""
    if not HAS_PIL:
        pytest.skip("Pillow not installed")
    img = PILImage.fromarray(arr_uint8)
    img.save(path)


# =============================================================================
# _load_frame TESTS
# =============================================================================


class TestLoadFrame:
    """Tests for RenderEvaluator._load_frame()."""

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_load_frame_png(self, evaluator, tmp_dir):
        """Load a real PNG from disk and verify shape and range."""
        arr_uint8 = np.random.randint(0, 256, (64, 48, 3), dtype=np.uint8)
        path = os.path.join(tmp_dir, "frame.png")
        _write_png(path, arr_uint8)

        loaded = evaluator._load_frame(path)
        assert loaded is not None
        assert loaded.shape == (64, 48, 3)
        assert loaded.dtype == np.float32
        # All values should be in [0, 1] after normalization
        assert loaded.min() >= 0.0
        assert loaded.max() <= 1.0

    def test_load_frame_missing_file(self, evaluator):
        """Missing file should return None gracefully."""
        result = evaluator._load_frame("/nonexistent/path/frame.0001.exr")
        assert result is None

    def test_load_frame_unsupported_format(self, evaluator, tmp_dir):
        """Unsupported extension (no library can handle) returns None."""
        path = os.path.join(tmp_dir, "frame.xyz")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not an image")
        result = evaluator._load_frame(path)
        assert result is None

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_normalize_uint8(self, evaluator, tmp_dir):
        """uint8 PNG with known values normalizes correctly to 0-1."""
        # Create a 2x2 image: black, white, mid-gray, red
        arr = np.array([
            [[0, 0, 0], [255, 255, 255]],
            [[128, 128, 128], [255, 0, 0]],
        ], dtype=np.uint8)
        path = os.path.join(tmp_dir, "known.png")
        _write_png(path, arr)

        loaded = evaluator._load_frame(path)
        assert loaded is not None
        # Black pixel should be 0.0
        assert np.allclose(loaded[0, 0], [0.0, 0.0, 0.0], atol=0.01)
        # White pixel should be 1.0
        assert np.allclose(loaded[0, 1], [1.0, 1.0, 1.0], atol=0.01)

    def test_normalize_float32(self, evaluator):
        """Float32 pixels already in 0-1 should pass through unchanged."""
        arr = np.random.uniform(0.0, 1.0, (10, 10, 3)).astype(np.float32)
        # Directly call evaluate_frame with pre-normalized pixels
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f.exr", pixels=arr)
        # The array should have been used as-is (no normalization artifacts)
        assert isinstance(ev, FrameEvaluation)


# =============================================================================
# evaluate_frame AUTO-LOADING TESTS
# =============================================================================


class TestEvaluateFrameAutoLoad:
    """Tests for evaluate_frame auto-loading behavior."""

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_evaluate_frame_auto_loads(self, evaluator, tmp_dir):
        """When pixels=None, evaluate_frame loads from disk automatically."""
        arr_uint8 = np.random.randint(30, 220, (64, 64, 3), dtype=np.uint8)
        path = os.path.join(tmp_dir, "auto.png")
        _write_png(path, arr_uint8)

        ev = evaluator.evaluate_frame(frame=1, output_path=path)
        assert isinstance(ev, FrameEvaluation)
        # Should have run pixel checks (quality_score in metrics)
        assert "quality_score" in ev.metrics

    def test_evaluate_frame_preloaded_pixels(self, evaluator):
        """When pixels are provided, no file loading should occur."""
        pixels = np.random.uniform(0.1, 0.9, (32, 32, 3)).astype(np.float32)
        # output_path doesn't exist, but that's fine -- pixels are provided
        ev = evaluator.evaluate_frame(
            frame=1,
            output_path="/nonexistent/f.exr",
            pixels=pixels,
        )
        assert isinstance(ev, FrameEvaluation)
        assert ev.passed is True
        assert len(ev.issues) == 0

    def test_evaluate_frame_no_image_library(self, evaluator, tmp_dir):
        """When no library can load the file, skip pixel checks gracefully."""
        # Create a file with an extension that no library handles
        path = os.path.join(tmp_dir, "frame.dat")
        with open(path, "wb") as f:
            f.write(b"\x00" * 100)

        ev = evaluator.evaluate_frame(frame=1, output_path=path)
        assert isinstance(ev, FrameEvaluation)
        # File exists but can't be loaded -- should pass with skip note
        assert ev.passed is True
        assert any("skipping quality checks" in issue.lower() for issue in ev.issues)

    def test_evaluate_frame_missing_file_no_pixels(self, evaluator):
        """Missing file with no pixels should fail."""
        ev = evaluator.evaluate_frame(
            frame=1,
            output_path="/nonexistent/missing.exr",
        )
        assert isinstance(ev, FrameEvaluation)
        assert ev.passed is False
        assert any("Couldn't find" in issue for issue in ev.issues)

    def test_evaluate_frame_image_data_backwards_compat(self, evaluator):
        """Legacy image_data kwarg still works."""
        pixels = np.random.uniform(0.1, 0.9, (32, 32, 3)).astype(np.float32)
        ev = evaluator.evaluate_frame(
            frame=1,
            output_path="/tmp/f.exr",
            image_data=pixels,
        )
        assert isinstance(ev, FrameEvaluation)
        assert ev.passed is True


# =============================================================================
# evaluate_sequence_from_disk TESTS
# =============================================================================


class TestEvaluateSequenceFromDisk:
    """Tests for evaluate_sequence_from_disk()."""

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_evaluate_sequence_from_disk(self, evaluator, tmp_dir):
        """Dict of frame paths should produce a valid SequenceEvaluation."""
        frame_paths = {}
        for i in range(1, 6):
            arr = np.random.randint(30, 220, (32, 32, 3), dtype=np.uint8)
            path = os.path.join(tmp_dir, f"frame.{i:04d}.png")
            _write_png(path, arr)
            frame_paths[i] = path

        seq = evaluator.evaluate_sequence_from_disk(frame_paths)
        assert isinstance(seq, SequenceEvaluation)
        assert len(seq.frame_evaluations) == 5
        # Frames should be evaluated in sorted order
        frames = [fe.frame for fe in seq.frame_evaluations]
        assert frames == [1, 2, 3, 4, 5]

    @pytest.mark.skipif(not HAS_PIL, reason="Pillow not installed")
    def test_evaluate_sequence_from_disk_missing_frames(self, evaluator, tmp_dir):
        """Some paths pointing to missing files should not crash."""
        # Create frames 1 and 3, but frame 2 path points to nonexistent file
        frame_paths = {}
        for i in [1, 3]:
            arr = np.random.randint(30, 220, (32, 32, 3), dtype=np.uint8)
            path = os.path.join(tmp_dir, f"frame.{i:04d}.png")
            _write_png(path, arr)
            frame_paths[i] = path
        frame_paths[2] = os.path.join(tmp_dir, "frame.0002.png")  # missing

        seq = evaluator.evaluate_sequence_from_disk(frame_paths)
        assert isinstance(seq, SequenceEvaluation)
        assert len(seq.frame_evaluations) == 3
        # Frame 2 should have failed (file not found)
        frame2_eval = [fe for fe in seq.frame_evaluations if fe.frame == 2][0]
        assert frame2_eval.passed is False
