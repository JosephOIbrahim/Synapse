"""R-2 (ratified 2026-09-30): the named 'workstation' render profile - Karma XPU with the local profile's limits."""
from pathlib import Path

import pytest

from synapse.farm import backend as backend_module
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


# XPUCACHE (2026-09-30): a fresh per-job XPU cache left every RC-2c frame to the CPU device. The workstation
# worker reuses this machine's OptiX cache and houdini_temp; everything else stays isolated.

def test_workstation_shares_the_machine_xpu_caches_and_local_does_not():
    assert package.profile_settings("workstation")["shared_xpu_cache"] is True
    assert "shared_xpu_cache" not in package.profile_settings("local")


def test_shared_xpu_cache_points_at_the_hosts_caches_and_keeps_the_rest_isolated(tmp_path):
    host = {"LOCALAPPDATA": str(tmp_path / "la"), "TEMP": str(tmp_path / "t"), "OPENAI_API_KEY": "unit-test-sentinel"}
    env = package.isolated_environment(tmp_path, tmp_path / "rt", threads=0, shared_xpu_cache=True, environ=host)
    assert env["OPTIX_CACHE_PATH"] == str(tmp_path / "la" / "NVIDIA" / "OptixCache")
    assert env["HOUDINI_TEMP_DIR"] == str(tmp_path / "t" / "houdini_temp")
    assert env["TEMP"] == env["TMP"] == str(tmp_path / "rt" / "temp")
    assert env["LOCALAPPDATA"] == str(tmp_path / "rt" / "localappdata")
    assert env["APPDATA"] == str(tmp_path / "rt" / "appdata")
    assert env["PYTHONNOUSERSITE"] == "1" and "OPENAI_API_KEY" not in env
    plain = package.isolated_environment(tmp_path, tmp_path / "rt2", threads=0, environ=host)
    assert "OPTIX_CACHE_PATH" not in plain and "HOUDINI_TEMP_DIR" not in plain


def test_machine_caches_prefer_the_hosts_settings_and_skip_unexpanded_or_missing_values():
    assert package.machine_xpu_caches({"OPTIX_CACHE_PATH": "D:/optix", "HOUDINI_TEMP_DIR": "E:/ht",
                                       "LOCALAPPDATA": "C:/la", "TEMP": "C:/t"}) == {
        "OPTIX_CACHE_PATH": "D:/optix", "HOUDINI_TEMP_DIR": "E:/ht"}
    unexpanded = package.machine_xpu_caches({"HOUDINI_TEMP_DIR": "$HOME/houdini_temp", "TMP": "C:/tmp"})
    assert unexpanded == {"HOUDINI_TEMP_DIR": str(Path("C:/tmp") / "houdini_temp")}
    assert package.machine_xpu_caches({}) == {}


def test_workstation_launch_asks_for_the_shared_xpu_cache(tmp_path, monkeypatch):
    seen = {}

    def environment(hfs, runtime_dir, threads=2, shared_xpu_cache=False, environ=None):
        seen.update(threads=threads, shared_xpu_cache=shared_xpu_cache)
        raise RuntimeError("stop before launch")

    monkeypatch.setattr(backend_module, "isolated_environment", environment)
    backend = NativeTopsBackend(tmp_path)
    monkeypatch.setattr(backend, "capabilities", lambda: {"profiles": [
        {"id": "local", "available": True}, {"id": "workstation", "available": True}]})
    with pytest.raises(RuntimeError, match="stop before launch"):
        backend.prepare(_plan(), tmp_path / "job")
    assert seen == {"threads": 0, "shared_xpu_cache": True}
