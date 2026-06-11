"""
Synapse Autonomy Pipeline -- Evaluator Truth Tests (WP5)

A tool result may not claim an outcome the handler did not observe: a frame
whose pixels were never analyzed must NOT report passed. These tests pin the
truth contract end to end:

  - unloadable frames -> passed=False, verified=False, metrics={"unverified": 1.0}
  - directory paths take the missing-file FAIL branch (isfile, not exists)
  - unverified frames poison the sequence gate (unverified_count > 0 -> fail)
  - missing frames score 0.0 (not the old phantom 1.0)
  - pass_threshold is constructor-injectable and gates the sequence
  - handlers.py threads payload quality_threshold -> RenderEvaluator gate
    (orchestrator-reserved edit -- that one test fails until it lands)

Run without Houdini:
    python -m pytest tests/test_wp5_evaluator_truth.py -v
"""

import os
import sys
import tempfile
import types
from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock, patch

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

import synapse.autonomy.evaluator as evaluator_module
from synapse.autonomy.evaluator import RenderEvaluator
from synapse.autonomy.models import FrameEvaluation, SequenceEvaluation


def _SH():
    """Lazily import ``SynapseHandler`` INSIDE a test, never at collection time.

    Mirrors tests/test_autonomy_task_provenance.py:34-45 -- importing
    ``synapse.server.handlers`` at module/collection time would race the
    sibling hou-stub bootstraps and leave ``handlers.hou`` undefined for the
    whole session."""
    from synapse.server.handlers import SynapseHandler
    return SynapseHandler


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


@pytest.fixture
def no_decoders(monkeypatch):
    """Force the no-image-library path regardless of what's installed."""
    monkeypatch.setattr(evaluator_module, "_OIIO_AVAILABLE", False)
    monkeypatch.setattr(evaluator_module, "_PYEXR_AVAILABLE", False)
    monkeypatch.setattr(evaluator_module, "_PIL_AVAILABLE", False)


# =============================================================================
# HELPERS
# =============================================================================


def _write_junk_exr(dir_, name):
    """Write a file that no image library could ever decode."""
    path = os.path.join(dir_, name)
    with open(path, "wb") as f:
        f.write(b"\x00\x01junk-bytes-not-an-exr" * 4)
    return path


# =============================================================================
# UNVERIFIED FRAMES MUST FAIL
# =============================================================================


class TestUnverifiedFramesFail:
    """An unanalyzed frame must never report as passed."""

    def test_junk_exr_decoders_off_is_unverified_failure(
        self, evaluator, tmp_dir, no_decoders
    ):
        """Undecodable frame on disk -> honest unverified FAIL, no score."""
        path = _write_junk_exr(tmp_dir, "frame.0001.exr")

        ev = evaluator.evaluate_frame(frame=1, output_path=path)
        assert isinstance(ev, FrameEvaluation)
        assert ev.passed is False
        assert ev.verified is False
        assert ev.metrics == {"unverified": 1.0}
        assert "quality_score" not in ev.metrics
        assert any("unverified" in issue.lower() for issue in ev.issues)

    def test_directory_path_takes_missing_file_branch(
        self, evaluator, tmp_dir, no_decoders
    ):
        """A directory is not a rendered frame -- isfile sends it to FAIL."""
        ev = evaluator.evaluate_frame(frame=1, output_path=tmp_dir)
        assert isinstance(ev, FrameEvaluation)
        assert ev.passed is False
        assert ev.issues[0].startswith("Couldn't find")

    def test_sequence_of_junk_frames_scores_zero(
        self, evaluator, tmp_dir, no_decoders
    ):
        """5 unloadable frames -> 5 unverified, overall 0.0, sequence fails."""
        frame_paths = {
            i: _write_junk_exr(tmp_dir, f"frame.{i:04d}.exr") for i in range(1, 6)
        }

        seq = evaluator.evaluate_sequence_from_disk(frame_paths)
        assert isinstance(seq, SequenceEvaluation)
        assert seq.passed is False
        assert seq.unverified_count == 5
        assert seq.overall_score == 0.0


# =============================================================================
# VERIFIED SCORING + THRESHOLD GATE
# =============================================================================


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy not installed")
class TestVerifiedScoringAndThreshold:
    """Missing frames score 0.0; pass_threshold gates the sequence."""

    def test_missing_frames_drag_score_below_all_clean(self, evaluator, tmp_dir):
        """2 clean pixel frames + 2 nonexistent paths -> missing score as 0.0."""
        clean = np.full((32, 32, 3), 0.5, dtype=np.float32)
        mixed = [
            {"frame": 1, "output_path": "/x/f1.exr", "image_data": clean},
            {"frame": 2, "output_path": "/x/f2.exr", "image_data": clean},
            {"frame": 3, "output_path": os.path.join(tmp_dir, "missing.0003.exr"),
             "image_data": None},
            {"frame": 4, "output_path": os.path.join(tmp_dir, "missing.0004.exr"),
             "image_data": None},
        ]
        all_clean = [
            {"frame": i, "output_path": f"/x/f{i}.exr", "image_data": clean}
            for i in range(1, 5)
        ]

        seq_mixed = evaluator.evaluate_sequence(mixed)
        seq_clean = evaluator.evaluate_sequence(all_clean)

        # Missing frames are VERIFIED failures (quality_score 0.0), not skips
        assert seq_mixed.unverified_count == 0
        assert seq_mixed.overall_score == pytest.approx(0.5)
        assert seq_mixed.overall_score < seq_clean.overall_score

    def test_pass_threshold_gates_sequence(self):
        """Mean 0.875: fails at threshold 0.95, passes at 0.7."""
        clean = np.full((20, 20, 3), 0.5, dtype=np.float32)
        clipped = np.full((20, 20, 3), 0.5, dtype=np.float32)
        clipped[:2, :, :] = 1.0  # 10% pure white -> exactly one clipping issue

        results = [
            {"frame": 1, "output_path": "/x/f1.exr", "image_data": clean},
            {"frame": 2, "output_path": "/x/f2.exr", "image_data": clipped},
        ]

        strict = RenderEvaluator(pass_threshold=0.95).evaluate_sequence(results)
        assert strict.overall_score == pytest.approx(0.875)
        assert strict.passed is False
        assert strict.pass_threshold == 0.95

        lenient = RenderEvaluator(pass_threshold=0.7).evaluate_sequence(results)
        assert lenient.passed is True
        assert lenient.pass_threshold == 0.7


# =============================================================================
# HANDLER -> GATE THRESHOLD THREADING (orchestrator-reserved handlers.py edit)
# =============================================================================


class TestHandlerThreadsThreshold:
    """Pins handlers.py threading payload quality_threshold into the
    RenderEvaluator pass_threshold gate (with clamping into [0, 1]).

    EXPECTED TO FAIL until the orchestrator lands the reserved handlers.py
    edit this wave -- do not weaken."""

    def test_handler_threads_quality_threshold_to_evaluator(self, monkeypatch):
        SynapseHandler = _SH()
        import synapse.server.handlers as H
        import synapse.memory.store as mem_store

        captured: List[float] = []

        class _RecordingEvaluator(RenderEvaluator):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                captured.append(self._pass_threshold)

        @dataclass
        class _FakePlan:
            validation_checks: list = field(default_factory=list)

        @dataclass
        class _FakeReport:
            success: bool = True
            plan: _FakePlan = field(default_factory=_FakePlan)
            evaluation: Optional[object] = None
            verification: Optional[object] = None

        class _FakeDriver:
            def __init__(self, **kw):
                pass

            async def execute(self, intent):
                return _FakeReport()

        fake_autonomy = types.ModuleType("synapse.autonomy")
        fake_autonomy.AutonomousDriver = _FakeDriver
        fake_autonomy.RenderPlanner = lambda *a, **k: object()
        fake_autonomy.PreFlightValidator = lambda *a, **k: object()
        fake_autonomy.RenderEvaluator = _RecordingEvaluator

        def _no_memory():
            raise RuntimeError("memory store disabled for this test")

        monkeypatch.setattr(mem_store, "get_synapse_memory", _no_memory)

        handler = SynapseHandler.__new__(SynapseHandler)  # no heavy __init__
        handler._registry = MagicMock()

        with patch.dict(sys.modules, {"synapse.autonomy": fake_autonomy}), \
             patch.object(H.SynapseHandler, "_resolve_agent_usd",
                          staticmethod(lambda: None)):
            handler._handle_autonomous_render(
                {"intent": "render frames 1-2", "quality_threshold": 0.95}
            )
            assert captured, "RenderEvaluator was never constructed"
            assert captured[-1] == 0.95

            # Out-of-range payload must clamp into [0, 1], not pass through
            handler._handle_autonomous_render(
                {"intent": "render frames 1-2", "quality_threshold": 1.5}
            )
            assert captured[-1] == 1.0
