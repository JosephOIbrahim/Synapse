"""R-2 (ratified 2026-09-30): the named 'workstation' render profile - Karma XPU with the local profile's limits."""
import pytest

from synapse.farm import package
from synapse.farm.backend import NativeTopsBackend


def _plan(profile="workstation", frames=(1,), width=256, height=256, samples=8):
    plan = {"profile_id": profile, "frames": list(frames), "width": width, "height": height, "samples": samples}
    plan["digest"] = package.digest(dict(plan))
    return plan


def test_profile_table_keeps_local_and_adds_workstation():
    assert package.profile_settings("local") == {"label": "local", "renderer": "BRAY_HdKarma",
                                                 "renderer_name": "Karma CPU", "threads": 2}
    ws = package.profile_settings("workstation")
    assert ws["renderer"] == "BRAY_HdKarmaXPU" and ws["threads"] == 0
    with pytest.raises(ValueError, match="HQueue is not configured"):
        package.profile_settings("hqueue")


def test_capabilities_list_workstation_last_with_local_limits(tmp_path):
    profiles = NativeTopsBackend(tmp_path).capabilities()["profiles"]
    assert [p["id"] for p in profiles] == ["local", "hqueue", "workstation"]
    local, ws = profiles[0], profiles[2]
    assert ws["label"] == "This workstation (GPU)" and ws["qualification"] == "workstation"
    assert ws["limits"]["renderer"] == "Karma XPU" and ws["limits"]["threads"] == "all"
    for key in ("max_frames", "max_width", "max_height", "max_samples", "frame_timeout_seconds", "concurrent_tasks"):
        assert ws["limits"][key] == local["limits"][key]
    assert ws["available"] is False  # no qualified Houdini under tmp_path


def test_validate_accepts_workstation_and_names_the_profile_in_errors():
    package.validate_local_plan(_plan())
    with pytest.raises(ValueError, match="The workstation profile accepts 1.120 distinct"):
        package.validate_local_plan(_plan(frames=range(1, 122)))
    with pytest.raises(ValueError, match="The local profile is limited to 2048 by 2048 pixels."):
        package.validate_local_plan(_plan(profile="local", width=4096))
    with pytest.raises(ValueError, match="HQueue is not configured"):
        package.validate_local_plan(_plan(profile="hqueue"))


def test_environment_caps_threads_only_for_local(tmp_path):
    assert package.isolated_environment(tmp_path, tmp_path / "rt")["HOUDINI_MAXTHREADS"] == "2"
    assert "HOUDINI_MAXTHREADS" not in package.isolated_environment(tmp_path, tmp_path / "rt2", threads=0)


def test_launch_refuses_an_unavailable_workstation_with_its_reason(tmp_path, monkeypatch):
    backend = NativeTopsBackend(tmp_path)
    monkeypatch.setattr(backend, "capabilities", lambda: {"profiles": [
        {"id": "local", "available": True},
        {"id": "workstation", "available": False, "reason": "no qualified Houdini"}]})
    result = backend.prepare(_plan(), tmp_path / "job")
    assert result["state"] == "failed" and result["note"] == "no qualified Houdini"
