"""
Synapse Autonomy Pipeline — Evaluator Tests

Tests for synapse.autonomy.evaluator.RenderEvaluator.
Run without Houdini:
    python -m pytest tests/test_autonomy_evaluator.py -v
"""

import sys
import os

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

from synapse.autonomy.models import FrameEvaluation, SequenceEvaluation
from synapse.autonomy.evaluator import RenderEvaluator


# =============================================================================
# HELPERS
# =============================================================================

def _make_clean_frame(height=100, width=100):
    """Uniform random pixel data in [0.1, 0.9] -- no issues."""
    assert HAS_NUMPY, "numpy required for evaluator tests"
    return np.random.uniform(0.1, 0.9, (height, width, 3)).astype(np.float32)


def _make_black_frame(height=100, width=100):
    """All-zero frame -- should trigger black_frame detection."""
    assert HAS_NUMPY
    return np.zeros((height, width, 3), dtype=np.float32)


def _make_firefly_frame(height=100, width=100):
    """One extreme outlier pixel -- should trigger firefly detection."""
    assert HAS_NUMPY
    frame = np.random.uniform(0.1, 0.5, (height, width, 3)).astype(np.float32)
    frame[50, 50] = [100.0, 100.0, 100.0]
    return frame


def _make_nan_frame(height=100, width=100):
    """Frame with NaN values."""
    assert HAS_NUMPY
    frame = np.random.uniform(0.1, 0.9, (height, width, 3)).astype(np.float32)
    frame[25, 25] = [float("nan"), float("nan"), float("nan")]
    return frame


def _make_inf_frame(height=100, width=100):
    """Frame with Inf values."""
    assert HAS_NUMPY
    frame = np.random.uniform(0.1, 0.9, (height, width, 3)).astype(np.float32)
    frame[25, 25] = [float("inf"), float("inf"), float("inf")]
    return frame


def _make_overexposed_frame(height=100, width=100):
    """Frame with large clipped-white regions (all pixels >= 1.0)."""
    assert HAS_NUMPY
    return np.ones((height, width, 3), dtype=np.float32)


def _make_underexposed_frame(height=100, width=100):
    """Frame that is nearly black (all pixels near zero)."""
    assert HAS_NUMPY
    return np.full((height, width, 3), 0.0, dtype=np.float32)


def _frame_result(frame, output_path, image_data=None):
    """Helper to build a frame_results dict for evaluate_sequence."""
    return {"frame": frame, "output_path": output_path, "image_data": image_data}


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def evaluator():
    return RenderEvaluator()


# =============================================================================
# PER-FRAME EVALUATION TESTS
# =============================================================================

pytestmark = pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")


class TestPerFrameEvaluation:
    """Tests for RenderEvaluator.evaluate_frame()."""

    def test_clean_frame_passes(self, evaluator):
        """A clean frame with normal pixel values should pass."""
        pixels = _make_clean_frame()
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=pixels)
        assert isinstance(ev, FrameEvaluation)
        assert ev.passed is True
        assert len(ev.issues) == 0

    def test_black_frame_detection(self, evaluator):
        """An all-black frame should be flagged."""
        pixels = _make_black_frame()
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=pixels)
        assert ev.passed is False
        assert any("black" in issue.lower() for issue in ev.issues)

    def test_nan_detection(self, evaluator):
        """NaN pixels should be detected."""
        pixels = _make_nan_frame()
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=pixels)
        assert ev.passed is False
        assert any("nan" in issue.lower() for issue in ev.issues)

    def test_inf_detection(self, evaluator):
        """Inf pixels should be detected."""
        pixels = _make_inf_frame()
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=pixels)
        assert ev.passed is False
        assert any("inf" in issue.lower() for issue in ev.issues)

    def test_firefly_detection(self, evaluator):
        """Extreme outlier pixels (fireflies) should be detected."""
        pixels = _make_firefly_frame()
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=pixels)
        assert ev.passed is False
        assert any("firefl" in issue.lower() for issue in ev.issues)

    def test_overexposure_clipping(self, evaluator):
        """All-white frame should be flagged as clipped/overexposed."""
        pixels = _make_overexposed_frame()
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=pixels)
        assert ev.passed is False
        assert any("clip" in issue.lower() for issue in ev.issues)

    def test_underexposure_clipping(self, evaluator):
        """All-black (zero) frame triggers black frame and/or clipping."""
        pixels = _make_underexposed_frame()
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=pixels)
        assert ev.passed is False
        assert len(ev.issues) >= 1

    def test_multiple_issues(self, evaluator):
        """A frame that is all-black AND has Inf values should report both issues."""
        assert HAS_NUMPY
        # All-black triggers black_frame, Inf triggers nan_inf check
        pixels = np.zeros((100, 100, 3), dtype=np.float32)
        pixels[10, 10] = [float("inf"), float("inf"), float("inf")]
        ev = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=pixels)
        assert ev.passed is False
        assert len(ev.issues) >= 2

    def test_quality_score_metric(self, evaluator):
        """Quality score should be 1.0 for clean frame, lower for issues."""
        clean = _make_clean_frame()
        ev_clean = evaluator.evaluate_frame(frame=1, output_path="/tmp/f1.exr", image_data=clean)
        assert ev_clean.metrics["quality_score"] == 1.0

        black = _make_black_frame()
        ev_bad = evaluator.evaluate_frame(frame=2, output_path="/tmp/f2.exr", image_data=black)
        assert ev_bad.metrics["quality_score"] < 1.0


# =============================================================================
# SEQUENCE EVALUATION TESTS
# =============================================================================


class TestSequenceEvaluation:
    """Tests for RenderEvaluator.evaluate_sequence().

    evaluate_sequence takes List[Dict] with keys: frame, output_path, image_data.
    """

    def test_stable_sequence_passes(self, evaluator):
        """A sequence of clean frames should pass."""
        frames = [
            _frame_result(i, f"/tmp/f{i}.exr", _make_clean_frame())
            for i in range(1, 13)
        ]
        seq = evaluator.evaluate_sequence(frames)
        assert isinstance(seq, SequenceEvaluation)
        assert seq.passed is True
        assert seq.overall_score > 0.7

    def test_flickering_detection(self, evaluator):
        """Alternating bright/dark frames should flag flickering."""
        assert HAS_NUMPY
        frames = []
        for i in range(1, 25):
            if i % 2 == 0:
                data = np.full((50, 50, 3), 0.9, dtype=np.float32)
            else:
                data = np.full((50, 50, 3), 0.1, dtype=np.float32)
            frames.append(_frame_result(i, f"/tmp/f{i}.exr", data))
        seq = evaluator.evaluate_sequence(frames)
        assert isinstance(seq, SequenceEvaluation)
        # Flickering should be detected as a temporal issue
        if seq.temporal_issues:
            assert any("flicker" in issue.lower() for issue in seq.temporal_issues)

    def test_motion_discontinuity(self, evaluator):
        """A sudden jump in frame content should flag motion discontinuity."""
        assert HAS_NUMPY
        frames = []
        for i in range(1, 13):
            if i == 6:
                # Sudden jump at frame 6
                data = np.full((50, 50, 3), 0.9, dtype=np.float32)
            else:
                data = np.full((50, 50, 3), 0.2, dtype=np.float32)
            frames.append(_frame_result(i, f"/tmp/f{i}.exr", data))
        seq = evaluator.evaluate_sequence(frames)
        assert isinstance(seq, SequenceEvaluation)
        # Should detect temporal discontinuity
        if seq.temporal_issues:
            assert any("discontinuity" in issue.lower() or "motion" in issue.lower()
                        for issue in seq.temporal_issues)

    def test_missing_frame_detection(self, evaluator):
        """Non-contiguous frame numbers should flag missing frames."""
        frames = [
            _frame_result(1, "/tmp/f1.exr", _make_clean_frame()),
            _frame_result(2, "/tmp/f2.exr", _make_clean_frame()),
            # Frame 3 missing
            _frame_result(4, "/tmp/f4.exr", _make_clean_frame()),
            _frame_result(5, "/tmp/f5.exr", _make_clean_frame()),
        ]
        seq = evaluator.evaluate_sequence(frames)
        assert isinstance(seq, SequenceEvaluation)
        assert any("missing" in issue.lower() for issue in seq.temporal_issues)

    def test_sequence_score_calculation(self, evaluator):
        """Score should decrease with more failed frames."""
        all_clean = [
            _frame_result(i, f"/tmp/f{i}.exr", _make_clean_frame())
            for i in range(1, 11)
        ]
        half_black = []
        for i in range(1, 11):
            if i <= 5:
                half_black.append(_frame_result(i, f"/tmp/f{i}.exr", _make_clean_frame()))
            else:
                half_black.append(_frame_result(i, f"/tmp/f{i}.exr", _make_black_frame()))

        score_good = evaluator.evaluate_sequence(all_clean).overall_score
        score_bad = evaluator.evaluate_sequence(half_black).overall_score
        assert score_good > score_bad

    def test_empty_sequence(self, evaluator):
        """Empty frame list should not crash."""
        seq = evaluator.evaluate_sequence([])
        assert isinstance(seq, SequenceEvaluation)
        assert seq.overall_score == 0.0

    def test_single_frame_sequence(self, evaluator):
        """Single-frame sequence should work correctly."""
        frames = [_frame_result(1, "/tmp/f1.exr", _make_clean_frame())]
        seq = evaluator.evaluate_sequence(frames)
        assert isinstance(seq, SequenceEvaluation)
        assert seq.overall_score > 0
        assert len(seq.frame_evaluations) == 1
