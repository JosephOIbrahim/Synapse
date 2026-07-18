"""Tests for synapse.server.foreground_guard — the refusal half of the
Indie render fix. Pure Python, no Houdini required."""

import pytest

from synapse.server import foreground_guard as fg


# ---------------------------------------------------------------------------
# optix_cache_state
# ---------------------------------------------------------------------------

class TestOptixCacheState:
    def test_missing_dir_is_cold(self, tmp_path, monkeypatch):
        monkeypatch.setenv(fg.OPTIX_CACHE_ENV, str(tmp_path / "nope"))
        state = fg.optix_cache_state()
        assert state["exists"] is False
        assert state["warm"] is False

    def test_empty_dir_is_cold(self, tmp_path, monkeypatch):
        monkeypatch.setenv(fg.OPTIX_CACHE_ENV, str(tmp_path))
        state = fg.optix_cache_state()
        assert state["exists"] is True
        assert state["warm"] is False

    def test_dir_with_file_is_warm(self, tmp_path, monkeypatch):
        (tmp_path / "kernel.bin").write_bytes(b"x")
        monkeypatch.setenv(fg.OPTIX_CACHE_ENV, str(tmp_path))
        assert fg.optix_cache_state()["warm"] is True

    def test_nested_file_is_warm(self, tmp_path, monkeypatch):
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        (sub / "cache.dat").write_bytes(b"x")
        monkeypatch.setenv(fg.OPTIX_CACHE_ENV, str(tmp_path))
        assert fg.optix_cache_state()["warm"] is True


# ---------------------------------------------------------------------------
# assess_foreground_render — XPU cold-cache gate
# ---------------------------------------------------------------------------

_COLD = {"path": "/x", "exists": False, "warm": False}
_WARM = {"path": "/x", "exists": True, "warm": True}


class TestXpuColdGate:
    def test_cold_cache_denies_regardless_of_size(self):
        v = fg.assess_foreground_render(
            "karma_xpu", width=64, height=64, cache_state=_COLD)
        assert v["allow"] is False
        assert v["level"] == "deny"
        assert "COLD" in v["reason"]

    def test_cold_cache_denies_even_with_unknown_resolution(self):
        v = fg.assess_foreground_render("karma_xpu", cache_state=_COLD)
        assert v["allow"] is False

    def test_force_downgrades_cold_deny_to_forced(self):
        v = fg.assess_foreground_render(
            "karma_xpu", width=64, height=64, force=True, cache_state=_COLD)
        assert v["allow"] is True
        assert v["level"] == "forced"
        assert v["forced"] is True

    def test_warm_small_xpu_allows(self):
        v = fg.assess_foreground_render(
            "karma_xpu", width=256, height=256, cache_state=_WARM)
        assert v["allow"] is True
        assert v["level"] == "allow"

    def test_warm_huge_xpu_denies(self):
        v = fg.assess_foreground_render(
            "karma_xpu", width=2048, height=2048, cache_state=_WARM)
        assert v["allow"] is False

    def test_verdict_carries_cache_info(self):
        v = fg.assess_foreground_render(
            "karma_xpu", width=64, height=64, cache_state=_WARM)
        assert v["optix_cache"]["warm"] is True


# ---------------------------------------------------------------------------
# assess_foreground_render — pixel/sample budgets
# ---------------------------------------------------------------------------

class TestBudgets:
    def test_cpu_within_budget_allows(self):
        v = fg.assess_foreground_render(
            "karma_cpu", width=256, height=256, samples=16)
        assert v["allow"] is True
        assert v["level"] == "allow"

    def test_cpu_mid_range_warns(self):
        v = fg.assess_foreground_render("karma_cpu", width=512, height=512)
        assert v["allow"] is True
        assert v["level"] == "warn"

    def test_cpu_over_samples_warns(self):
        v = fg.assess_foreground_render(
            "karma_cpu", width=128, height=128, samples=256)
        assert v["allow"] is True
        assert v["level"] == "warn"

    def test_cpu_huge_denies(self):
        v = fg.assess_foreground_render("karma_cpu", width=1920, height=1080)
        assert v["allow"] is False

    def test_cpu_huge_force_allows_with_forced_level(self):
        v = fg.assess_foreground_render(
            "karma_cpu", width=1920, height=1080, force=True)
        assert v["allow"] is True
        assert v["level"] == "forced"

    def test_mantra_tiny_sample_budget(self):
        v = fg.assess_foreground_render(
            "mantra", width=128, height=128, samples=8)
        assert v["level"] == "warn"

    def test_opengl_generous(self):
        v = fg.assess_foreground_render("opengl", width=1024, height=1024)
        assert v["allow"] is True
        assert v["level"] == "allow"


# ---------------------------------------------------------------------------
# assess_foreground_render — blind spots stay silent
# ---------------------------------------------------------------------------

class TestBlindSpots:
    def test_unknown_engine_allows_silently(self):
        v = fg.assess_foreground_render("renderman", width=4096, height=4096)
        assert v["allow"] is True
        assert v["level"] == "allow"

    def test_none_engine_allows(self):
        assert fg.assess_foreground_render(None)["allow"] is True

    def test_unknown_resolution_allows_silently_for_cpu(self):
        v = fg.assess_foreground_render("karma_cpu")
        assert v["allow"] is True
        assert v["level"] == "allow"

    def test_generic_karma_uses_cpu_budget_no_cache_gate(self):
        # Generic 'karma' (variant unresolved) must NOT probe the OptiX
        # cache — only an explicit karma_xpu does.
        v = fg.assess_foreground_render("karma", width=64, height=64)
        assert v["allow"] is True
        assert "optix_cache" not in v

    def test_delegate_flavored_karma_takes_generic_budget(self):
        # F1: "karma_bray_hdkarma" (a usdrender ROP's renderer parm evals to
        # the Hydra delegate id) must hit the conservative generic-karma
        # budget row — NOT fall through every row unbudgeted.
        v = fg.assess_foreground_render(
            "karma_bray_hdkarma", width=1920, height=1080)
        assert v["allow"] is False

    def test_delegate_flavored_karma_small_still_allows(self):
        v = fg.assess_foreground_render(
            "karma_bray_hdkarma", width=64, height=64)
        assert v["allow"] is True
        assert "optix_cache" not in v  # unknown variant never cache-gates
