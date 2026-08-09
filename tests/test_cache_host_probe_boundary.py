"""Mile 2 (resource-aware-cache Phase 0, R-CACHE-1) — boundary tests for
``host/cache_host_probe.py``.

Binding constraint #4: "lastCookTime ms->s conversion happens EXACTLY ONCE, in your host
adapter. This is pinned by a boundary test — write one that asserts the conversion happens
and is not repeated/doubled elsewhere." Also covers the broader §17.2 boundary-test set
this module is responsible for: never a fake fallback number, typed warnings on exception,
and the read-only (never-guessed) machine-profile fields.

Pure Python. No ``hou`` import anywhere in this file's critical path.

Every test states the condition under which it fails.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HOST_DIR = _REPO_ROOT / "host"
if str(_HOST_DIR) not in sys.path:
    sys.path.insert(0, str(_HOST_DIR))

import cache_host_probe as chp  # noqa: E402


class _CleanNodeWithCookTime:
    def __init__(self, last_cook_ms):
        self._last_cook_ms = last_cook_ms

    def needsToCook(self):
        return False

    def isTimeDependent(self, for_last_cook=False):
        return False

    def lastCookTime(self):
        return self._last_cook_ms

    def cookCount(self):
        return 1

    def geometry(self):
        class _G:
            def intrinsicValue(self, name):
                return 0

        return _G()

    def path(self):
        return "/obj/geo1/timed1"


class _NodeWithFailingLastCookTime:
    def needsToCook(self):
        return False

    def isTimeDependent(self, for_last_cook=False):
        return False

    def lastCookTime(self):
        raise RuntimeError("simulated failure reading lastCookTime")

    def cookCount(self):
        return 0

    def geometry(self):
        class _G:
            def intrinsicValue(self, name):
                return 0

        return _G()

    def path(self):
        return "/obj/geo1/broken_timed1"


# --------------------------------------------------------------------------- ms -> s, exactly once

def test_ms_to_seconds_conversion_is_correct_and_applied_exactly_once():
    """Fails if the division by 1000 is missing, applied twice (a 1000x or 1,000,000x
    error), or applied to the wrong field. 6180 ms must become exactly 6.18 s — not 6180,
    not 0.00618, not 0.618.
    """
    node = _CleanNodeWithCookTime(last_cook_ms=6180.0)
    result = chp.observe_node_passively(node)

    seconds = result["last_cook_seconds"]["value"]
    assert seconds == 6.18, f"expected 6.18 seconds from 6180 ms, got {seconds!r}"
    assert result["last_cook_seconds"]["unit"] == "seconds"


def test_workload_snapshot_mapping_does_not_reconvert_the_value():
    """Fails if to_workload_snapshot_kwargs (or any later consumer of the observation dict)
    re-applies a unit conversion instead of passing the already-converted evidence through
    unchanged — this is the "not repeated/doubled elsewhere" half of the constraint.
    """
    node = _CleanNodeWithCookTime(last_cook_ms=6180.0)
    observation = chp.observe_node_passively(node)
    mapped = chp.to_workload_snapshot_kwargs(observation)

    assert mapped["last_cook_seconds"]["value"] == observation["last_cook_seconds"]["value"] == 6.18


def test_zero_ms_converts_to_zero_seconds_not_none():
    """Fails if a legitimately-zero cook time (e.g. an instant no-op node) is confused with
    an unmeasured value — 0 ms is a real measurement, not "unknown". Guards against a
    ``if last_cook_ms:`` truthiness bug that would treat 0 the same as None.
    """
    node = _CleanNodeWithCookTime(last_cook_ms=0.0)
    result = chp.observe_node_passively(node)

    assert result["last_cook_seconds"]["value"] == 0.0
    assert result["last_cook_seconds"]["confidence"] == "high"


def test_failed_last_cook_time_read_never_fabricates_a_number():
    """Fails if a lastCookTime() exception produces a fake 0.0 instead of an honest
    unknown evidence wrapper — this is the exact defect class named in adjudication a4/a5
    ("never a guessed fallback"), applied to the cook-time field specifically.
    """
    node = _NodeWithFailingLastCookTime()
    result = chp.observe_node_passively(node)

    seconds = result["last_cook_seconds"]
    assert seconds["value"] is None
    assert seconds["source"] == "unknown"
    assert seconds["confidence"] == "unknown"
    assert any("lastCookTime" in w for w in result["warnings"])


# --------------------------------------------------------------------------- safe_call

def test_safe_call_returns_default_and_records_typed_warning_on_exception():
    """Fails if safe_call swallows the exception without a warning, or if it lets the
    exception propagate instead of degrading to None.
    """
    warnings = []

    def _boom():
        raise ValueError("simulated")

    result = chp.safe_call(_boom, warnings=warnings, label="boom")

    assert result is None
    assert len(warnings) == 1
    assert "boom" in warnings[0]
    assert "ValueError" in warnings[0]


def test_safe_call_passes_through_a_real_zero_unmodified():
    """Fails if safe_call's exception handling ever coerces a legitimate falsy return
    value (0, False, "") into something else — only actual exceptions become None.
    """
    assert chp.safe_call(lambda: 0) == 0
    assert chp.safe_call(lambda: False) is False
    assert chp.safe_call(lambda: "") == ""


# --------------------------------------------------------------------------- machine profile: unmeasured = unknown

def test_machine_profile_never_fabricates_ram_when_probes_fail(monkeypatch):
    """Fails if any RAM/CPU/disk field falls back to a guessed constant (e.g. the
    adjudication a5 defect: ``else: sys_ram_gb = 64.0``) instead of the literal string
    "unknown" when every probing tier is unavailable.
    """
    monkeypatch.setattr(chp, "PSUTIL_AVAILABLE", False)
    monkeypatch.setattr(chp, "_detect_os_family", lambda: "unknown")

    profile = chp.detect_machine_profile()

    assert profile["ram_total_bytes"] == "unknown"
    assert profile["ram_available_bytes"] == "unknown"
    assert profile["os_family"] == "unknown"


def test_machine_profile_reports_unknown_houdini_version_without_hou(monkeypatch):
    """Fails if houdini_version is guessed (e.g. hardcoded to the pinned build) instead of
    reporting "unknown" when hou is unavailable — the build must be a real read, never an
    assumption baked into the probe.
    """
    monkeypatch.setattr(chp, "HOU_AVAILABLE", False)

    profile = chp.detect_machine_profile()

    assert profile["houdini_version"] == "unknown"


def test_cache_volume_free_space_is_real_measurement_or_unknown_never_guessed(tmp_path):
    """Fails if free/total disk bytes are fabricated instead of read via shutil.disk_usage,
    or if a real, existing path fails to produce real numbers.
    """
    profile = chp.detect_machine_profile(cache_root=str(tmp_path))

    volume = profile["cache_volume"]
    assert isinstance(volume["free_bytes"], int), "a real path must yield a real measurement"
    assert isinstance(volume["total_bytes"], int)
    assert volume["free_bytes"] >= 0


def test_cache_volume_unknown_path_never_guesses_free_space(monkeypatch):
    """Fails if a nonexistent/unset cache root silently reports some default free-space
    number instead of "unknown".
    """
    monkeypatch.delenv("HIP", raising=False)

    profile = chp.detect_machine_profile(cache_root=None)

    volume = profile["cache_volume"]
    assert volume["path"] == "unknown"
    assert volume["free_bytes"] == "unknown"
    assert volume["total_bytes"] == "unknown"
