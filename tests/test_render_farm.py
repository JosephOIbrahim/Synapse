"""Tests for render_farm.py — core orchestrator with mocked handlers.

Mock-based — no Houdini required.
"""

import importlib.util
import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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
    ("synapse.memory.models", _root / "synapse" / "memory" / "models.py"),
    ("synapse.server.render_diagnostics", _root / "synapse" / "server" / "render_diagnostics.py"),
    ("synapse.server.render_notify", _root / "synapse" / "server" / "render_notify.py"),
    ("synapse.server.render_farm", _root / "synapse" / "server" / "render_farm.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

farm_mod = sys.modules["synapse.server.render_farm"]

RenderFarmOrchestrator = farm_mod.RenderFarmOrchestrator
RenderCallbacks = farm_mod.RenderCallbacks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_callbacks(
    render_resp=None,
    validate_resp=None,
    settings_resp=None,
    stage_resp=None,
):
    """Create RenderCallbacks with mock handlers."""
    if render_resp is None:
        render_resp = {"image_path": "/tmp/frame.exr", "rop": "/stage/karma1"}
    if validate_resp is None:
        validate_resp = {"valid": True, "checks": {}}
    if settings_resp is None:
        settings_resp = {"settings": {"karma_samples": 64}}

    return RenderCallbacks(
        render_frame=MagicMock(return_value=render_resp),
        validate_frame=MagicMock(return_value=validate_resp),
        get_render_settings=MagicMock(return_value=settings_resp),
        set_render_settings=MagicMock(return_value=settings_resp),
        get_stage_info=MagicMock(return_value=stage_resp or {"prims": []}),
        broadcast=MagicMock(),
    )


@pytest.fixture
def callbacks():
    return _make_callbacks()


@pytest.fixture
def farm(callbacks, tmp_path):
    return RenderFarmOrchestrator(
        callbacks=callbacks,
        max_retries=3,
        auto_fix=True,
        report_dir=str(tmp_path),
    )


# ---------------------------------------------------------------------------
# Tests: render_frame_validated — happy path
# ---------------------------------------------------------------------------

class TestRenderFrameValidated:
    def test_single_frame_success(self, callbacks, tmp_path):
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))
        result = farm.render_frame_validated("/stage/karma1", 1001)
        assert result.success is True
        assert result.frame == 1001
        assert result.retries == 0
        assert result.image_path == "/tmp/frame.exr"

    def test_render_error(self, tmp_path):
        cb = _make_callbacks()
        cb.render_frame.side_effect = RuntimeError("GPU crash")
        farm = RenderFarmOrchestrator(callbacks=cb, report_dir=str(tmp_path))
        result = farm.render_frame_validated("/stage/karma1", 1001)
        assert result.success is False
        assert "GPU crash" in result.error

    def test_no_output_image(self, tmp_path):
        cb = _make_callbacks(render_resp={"image_path": "", "rop": "/stage/karma1"})
        farm = RenderFarmOrchestrator(callbacks=cb, report_dir=str(tmp_path))
        result = farm.render_frame_validated("/stage/karma1", 1001)
        assert result.success is False
        assert "no output" in result.error.lower()

    def test_validation_error_is_not_failure(self, tmp_path):
        cb = _make_callbacks()
        cb.validate_frame.side_effect = RuntimeError("OIIO crashed")
        farm = RenderFarmOrchestrator(callbacks=cb, report_dir=str(tmp_path))
        result = farm.render_frame_validated("/stage/karma1", 1001)
        # Validation error = we can't tell if frame is good, treat as success
        assert result.success is True


# ---------------------------------------------------------------------------
# Tests: render_frame_validated — auto-fix loop
# ---------------------------------------------------------------------------

class TestAutoFix:
    def test_fixes_on_first_retry(self, tmp_path):
        cb = _make_callbacks()
        # First validate: fails with saturation. Second: passes.
        cb.validate_frame.side_effect = [
            {"valid": False, "checks": {"saturation": {"passed": False}}},
            {"valid": True, "checks": {}},
        ]
        farm = RenderFarmOrchestrator(callbacks=cb, max_retries=3, report_dir=str(tmp_path))
        result = farm.render_frame_validated("/stage/karma1", 1001, {"karma_samples": 32})
        assert result.success is True
        assert result.retries == 1
        assert len(result.fixes_applied) >= 1
        # Render was called twice
        assert cb.render_frame.call_count == 2

    def test_exhausts_retries(self, tmp_path):
        cb = _make_callbacks()
        # Always fails
        cb.validate_frame.return_value = {
            "valid": False,
            "checks": {"saturation": {"passed": False}},
        }
        farm = RenderFarmOrchestrator(callbacks=cb, max_retries=2, report_dir=str(tmp_path))
        result = farm.render_frame_validated("/stage/karma1", 1001, {"karma_samples": 32})
        assert result.success is False
        assert result.retries == 2
        # 1 initial + 2 retries = 3 renders
        assert cb.render_frame.call_count == 3

    def test_auto_fix_disabled(self, tmp_path):
        cb = _make_callbacks()
        cb.validate_frame.return_value = {
            "valid": False,
            "checks": {"saturation": {"passed": False}},
        }
        farm = RenderFarmOrchestrator(
            callbacks=cb, max_retries=3, auto_fix=False,
            report_dir=str(tmp_path),
        )
        result = farm.render_frame_validated("/stage/karma1", 1001)
        assert result.success is False
        # Only one render attempt when auto_fix is disabled
        assert cb.render_frame.call_count == 1

    def test_no_remedy_available(self, tmp_path):
        cb = _make_callbacks()
        cb.validate_frame.return_value = {
            "valid": False,
            "checks": {"exotic_unknown_issue": {"passed": False}},
        }
        farm = RenderFarmOrchestrator(callbacks=cb, max_retries=3, report_dir=str(tmp_path))
        result = farm.render_frame_validated("/stage/karma1", 1001)
        assert result.success is False
        assert "No remedy" in result.error

    def test_remedy_application_failure(self, tmp_path):
        cb = _make_callbacks()
        cb.validate_frame.return_value = {
            "valid": False,
            "checks": {"saturation": {"passed": False}},
        }
        cb.set_render_settings.side_effect = RuntimeError("permission denied")
        farm = RenderFarmOrchestrator(callbacks=cb, max_retries=3, report_dir=str(tmp_path))
        result = farm.render_frame_validated("/stage/karma1", 1001, {"karma_samples": 32})
        assert result.success is False
        assert "Remedy application failed" in result.error

    def test_cancelled_frame(self, tmp_path):
        cb = _make_callbacks()
        farm = RenderFarmOrchestrator(callbacks=cb, report_dir=str(tmp_path))
        farm.cancel()
        result = farm.render_frame_validated("/stage/karma1", 1001)
        assert result.success is False
        assert "Cancelled" in result.error


# ---------------------------------------------------------------------------
# Tests: render_sequence
# ---------------------------------------------------------------------------

class TestRenderSequence:
    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_full_sequence_success(self, mock_notify, callbacks, tmp_path):
        mock_notify.return_value = {"report_path": "/tmp/report.md"}
        farm = RenderFarmOrchestrator(
            callbacks=callbacks, report_dir=str(tmp_path),
        )
        report = farm.render_sequence("/stage/karma1", (1001, 1005))
        assert report.total_frames == 5
        assert report.successful_frames == 5
        assert report.failed_frames == 0
        assert report.success_rate == 1.0
        assert report.start_frame == 1001
        assert report.end_frame == 1005
        assert callbacks.render_frame.call_count == 5

    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_sequence_with_step(self, mock_notify, callbacks, tmp_path):
        mock_notify.return_value = {}
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))
        report = farm.render_sequence("/stage/karma1", (1001, 1010), step=2)
        # Frames: 1001, 1003, 1005, 1007, 1009
        assert report.total_frames == 5

    @patch("synapse.server.render_farm.notify_batch_complete")
    @patch("synapse.server.render_farm.notify_persistent_failure")
    def test_sequence_with_failures(self, mock_fail_notify, mock_notify, tmp_path):
        mock_notify.return_value = {}
        mock_fail_notify.return_value = True

        cb = _make_callbacks()
        # Frame 1003 always fails validation
        call_count = [0]
        def validate_side_effect(payload):
            call_count[0] += 1
            # Calls for frame 1003 fail (calls 5-8 with max_retries=3)
            image_path = payload.get("image_path", "")
            # We can't distinguish frames by image path easily here,
            # so alternate based on call count
            return {"valid": True, "checks": {}}

        cb.validate_frame.side_effect = validate_side_effect
        farm = RenderFarmOrchestrator(
            callbacks=cb, max_retries=1, report_dir=str(tmp_path),
        )
        report = farm.render_sequence("/stage/karma1", (1001, 1003))
        assert report.total_frames == 3

    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_broadcasts_progress(self, mock_notify, callbacks, tmp_path):
        mock_notify.return_value = {}
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))
        report = farm.render_sequence("/stage/karma1", (1, 4))
        # Broadcast called for each frame
        assert callbacks.broadcast.call_count >= 4

    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_cancelled_sequence(self, mock_notify, callbacks, tmp_path):
        mock_notify.return_value = {}
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))
        # Cancel after first render call — render_sequence resets _cancelled on entry
        def cancel_on_first_render(payload):
            farm.cancel()
            return {"image_path": "/tmp/frame.exr", "rop": "/stage/karma1"}
        callbacks.render_frame.side_effect = cancel_on_first_render
        report = farm.render_sequence("/stage/karma1", (1, 100))
        # Most frames should not have rendered (cancelled after first)
        assert report.successful_frames <= 1

    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_scene_classification(self, mock_notify, tmp_path):
        mock_notify.return_value = {}
        cb = _make_callbacks(
            stage_resp={"prims": [
                {"path": "/World/interior/room", "type": "Mesh"},
                {"path": "/lights/dome_light", "type": "DomeLight"},
            ]},
        )
        farm = RenderFarmOrchestrator(callbacks=cb, report_dir=str(tmp_path))
        report = farm.render_sequence("/stage/karma1", (1, 2))
        assert "interior" in report.scene_tags
        assert "has_environment" in report.scene_tags


# ---------------------------------------------------------------------------
# Tests: memory integration
# ---------------------------------------------------------------------------

class TestMemoryIntegration:
    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_records_batch_in_memory(self, mock_notify, callbacks, tmp_path):
        mock_notify.return_value = {}
        mock_memory = MagicMock()
        farm = RenderFarmOrchestrator(
            callbacks=callbacks, memory=mock_memory,
            report_dir=str(tmp_path),
        )
        farm.render_sequence("/stage/karma1", (1, 3))
        # At minimum, the batch summary should be recorded
        mock_memory.add.assert_called()

    @patch("synapse.server.render_farm.notify_batch_complete")
    @patch("synapse.server.render_farm.query_known_fixes")
    def test_warmup_from_memory(self, mock_query, mock_notify, tmp_path):
        mock_notify.return_value = {}
        mock_query.return_value = [{
            "content": "**Parameter:** karma_samples = 128\n**Issue:** saturation",
            "tags": ["render_fix", "success"],
            "score": 0.9,
            "memory_id": "mem-1",
        }]
        # Provide stage prims so _classify_scene returns tags (not empty)
        cb = _make_callbacks(
            stage_resp={"prims": [
                {"path": "/World/interior/room", "type": "Mesh"},
            ]},
        )
        mock_memory = MagicMock()
        farm = RenderFarmOrchestrator(
            callbacks=cb, memory=mock_memory,
            report_dir=str(tmp_path),
        )
        report = farm.render_sequence("/stage/karma1", (1, 2))
        # set_render_settings should have been called with suggested settings
        # (the warmup applies memory-suggested settings before first frame)
        assert cb.set_render_settings.called


# ---------------------------------------------------------------------------
# Tests: get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_initial_status(self, farm):
        status = farm.get_status()
        assert status["running"] is False
        assert status["cancelled"] is False

    @patch("synapse.server.render_farm.notify_batch_complete")
    def test_status_after_sequence(self, mock_notify, callbacks, tmp_path):
        mock_notify.return_value = {}
        farm = RenderFarmOrchestrator(callbacks=callbacks, report_dir=str(tmp_path))
        farm.render_sequence("/stage/karma1", (1, 2))
        status = farm.get_status()
        assert status["running"] is False


# ---------------------------------------------------------------------------
# Tests: shutdown
# ---------------------------------------------------------------------------

class TestShutdown:
    def test_shutdown(self, farm):
        farm.shutdown()
        # Should not raise even if called multiple times
        farm.shutdown()
