"""Tests for render_notify.py — notifications and report generation.

Mock-based — no Houdini required.
"""

import importlib.util
import json
import os
import sys
import tempfile
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
    ("synapse.memory.models", _root / "synapse" / "memory" / "models.py"),
    ("synapse.server.render_notify", _root / "synapse" / "server" / "render_notify.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

notify_mod = sys.modules["synapse.server.render_notify"]

FrameResult = notify_mod.FrameResult
BatchReport = notify_mod.BatchReport
send_toast = notify_mod.send_toast
write_report = notify_mod.write_report
build_progress_event = notify_mod.build_progress_event
notify_batch_complete = notify_mod.notify_batch_complete
notify_persistent_failure = notify_mod.notify_persistent_failure


# ---------------------------------------------------------------------------
# Tests: FrameResult
# ---------------------------------------------------------------------------

class TestFrameResult:
    def test_defaults(self):
        fr = FrameResult(frame=1001, success=True)
        assert fr.frame == 1001
        assert fr.success is True
        assert fr.retries == 0
        assert fr.issues == []
        assert fr.fixes_applied == []

    def test_with_issues(self):
        fr = FrameResult(
            frame=1002, success=False, retries=3,
            issues=["saturation", "clipping"],
            fixes_applied=["pathtracedsamples=128"],
            error="Validation failed",
        )
        assert fr.retries == 3
        assert len(fr.issues) == 2


# ---------------------------------------------------------------------------
# Tests: BatchReport
# ---------------------------------------------------------------------------

class TestBatchReport:
    def test_success_rate_all_pass(self):
        report = BatchReport(
            start_frame=1001, end_frame=1010,
            total_frames=10, successful_frames=10,
        )
        assert report.success_rate == 1.0

    def test_success_rate_mixed(self):
        report = BatchReport(
            start_frame=1001, end_frame=1010,
            total_frames=10, successful_frames=7, failed_frames=3,
        )
        assert report.success_rate == 0.7

    def test_success_rate_empty(self):
        report = BatchReport(start_frame=1, end_frame=1, total_frames=0)
        assert report.success_rate == 0.0

    def test_to_dict(self):
        report = BatchReport(
            start_frame=1001, end_frame=1005,
            total_frames=5, successful_frames=4, failed_frames=1,
            total_render_time=120.567, total_wall_time=130.123,
            rop_path="/stage/karma1",
            scene_tags=["interior"],
            settings_used={"pathtracedsamples": 64},
            frame_results=[
                FrameResult(frame=1001, success=True, render_time=25.1),
                FrameResult(frame=1002, success=False, render_time=30.2, error="black frame"),
            ],
        )
        d = report.to_dict()
        assert d["total_frames"] == 5
        assert d["success_rate"] == 0.8
        assert d["rop_path"] == "/stage/karma1"
        assert len(d["frame_results"]) == 2
        assert d["frame_results"][0]["frame"] == 1001
        assert d["frame_results"][1]["success"] is False


# ---------------------------------------------------------------------------
# Tests: write_report
# ---------------------------------------------------------------------------

class TestWriteReport:
    def test_creates_markdown(self, tmp_path):
        report = BatchReport(
            start_frame=1001, end_frame=1005,
            total_frames=5, successful_frames=4, failed_frames=1,
            total_render_time=100.0, total_wall_time=110.0,
            rop_path="/stage/karma1",
            scene_tags=["interior", "has_environment"],
            settings_used={"pathtracedsamples": 64},
            frame_results=[
                FrameResult(frame=1001, success=True, render_time=20.0),
                FrameResult(
                    frame=1002, success=False, render_time=25.0,
                    retries=3, issues=["saturation"],
                    fixes_applied=["pathtracedsamples=128"],
                    error="Validation failed after max retries",
                ),
            ],
        )
        filepath = write_report(report, str(tmp_path))
        assert os.path.exists(filepath)
        assert filepath.endswith(".md")

        content = Path(filepath).read_text(encoding="utf-8")
        assert "Frames 1001-1005" in content
        assert "4/5 successful" in content
        assert "/stage/karma1" in content
        assert "interior" in content
        assert "saturation" in content
        assert "Failed Frames" in content

    def test_creates_directory(self, tmp_path):
        out_dir = str(tmp_path / "new_subdir" / "reports")
        report = BatchReport(
            start_frame=1, end_frame=1,
            total_frames=1, successful_frames=1,
            frame_results=[FrameResult(frame=1, success=True)],
        )
        filepath = write_report(report, out_dir)
        assert os.path.exists(filepath)

    def test_no_failed_frames_section(self, tmp_path):
        report = BatchReport(
            start_frame=1, end_frame=2,
            total_frames=2, successful_frames=2,
            frame_results=[
                FrameResult(frame=1, success=True),
                FrameResult(frame=2, success=True),
            ],
        )
        filepath = write_report(report, str(tmp_path))
        content = Path(filepath).read_text(encoding="utf-8")
        assert "Failed Frames" not in content


# ---------------------------------------------------------------------------
# Tests: build_progress_event
# ---------------------------------------------------------------------------

class TestBuildProgressEvent:
    def test_basic_event(self):
        event = build_progress_event(5, 100, "rendering")
        assert event["type"] == "render_farm_progress"
        assert event["frame"] == 5
        assert event["total_frames"] == 100
        assert event["progress"] == 0.05
        assert event["status"] == "rendering"
        assert "timestamp" in event

    def test_with_details(self):
        event = build_progress_event(50, 100, "complete", details={"fps": 2.5})
        assert event["details"]["fps"] == 2.5

    def test_zero_total(self):
        event = build_progress_event(0, 0, "idle")
        assert event["progress"] == 0.0


# ---------------------------------------------------------------------------
# Tests: send_toast
# ---------------------------------------------------------------------------

class TestSendToast:
    @patch("synapse.server.render_notify.subprocess.run")
    @patch("synapse.server.render_notify.os.name", "nt")
    def test_sends_on_windows(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = send_toast("Title", "Body text")
        assert result is True
        mock_run.assert_called_once()

    @patch("synapse.server.render_notify.os.name", "posix")
    def test_skips_on_non_windows(self):
        result = send_toast("Title", "Body")
        assert result is False

    @patch("synapse.server.render_notify.subprocess.run")
    @patch("synapse.server.render_notify.os.name", "nt")
    def test_handles_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = send_toast("Title", "Body")
        assert result is False

    @patch("synapse.server.render_notify.subprocess.run")
    @patch("synapse.server.render_notify.os.name", "nt")
    def test_handles_exception(self, mock_run):
        mock_run.side_effect = OSError("no powershell")
        result = send_toast("Title", "Body")
        assert result is False

    @patch("synapse.server.render_notify.subprocess.run")
    @patch("synapse.server.render_notify.os.name", "nt")
    def test_sanitizes_xml_chars(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        send_toast('Title with "quotes"', "Body with <tags>")
        call_args = mock_run.call_args[0][0]
        # The PowerShell command is passed as a list
        ps_cmd = call_args[-1]
        assert "&lt;" in ps_cmd
        assert "&gt;" in ps_cmd


# ---------------------------------------------------------------------------
# Tests: notify_batch_complete
# ---------------------------------------------------------------------------

class TestNotifyBatchComplete:
    @patch("synapse.server.render_notify.send_toast", return_value=True)
    def test_writes_report_and_toasts(self, mock_toast, tmp_path):
        report = BatchReport(
            start_frame=1, end_frame=5,
            total_frames=5, successful_frames=5,
            total_wall_time=60.0,
            frame_results=[FrameResult(frame=i, success=True) for i in range(1, 6)],
        )
        result = notify_batch_complete(report, str(tmp_path))
        assert "report_path" in result
        assert result["toast_sent"] is True
        mock_toast.assert_called_once()
        assert "All 5 frames" in mock_toast.call_args[0][1]

    @patch("synapse.server.render_notify.send_toast", return_value=True)
    def test_failure_message(self, mock_toast, tmp_path):
        report = BatchReport(
            start_frame=1, end_frame=5,
            total_frames=5, successful_frames=3, failed_frames=2,
            frame_results=[
                FrameResult(frame=1, success=True),
                FrameResult(frame=2, success=False),
            ],
        )
        notify_batch_complete(report, str(tmp_path))
        assert "2 failed" in mock_toast.call_args[0][1]


# ---------------------------------------------------------------------------
# Tests: notify_persistent_failure
# ---------------------------------------------------------------------------

class TestNotifyPersistentFailure:
    @patch("synapse.server.render_notify.send_toast", return_value=True)
    def test_sends_toast(self, mock_toast):
        result = notify_persistent_failure(42, "saturation", 3)
        assert result is True
        assert "Frame 42" in mock_toast.call_args[0][1]
        assert "3 retries" in mock_toast.call_args[0][1]
