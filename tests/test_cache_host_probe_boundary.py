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


class _NeverCookedNode:
    """cookCount()==0: no cook evidence at all. Used to distinguish "genuinely never
    cooked" (ordinary unknown, no special warning) from "headless didn't report it"
    (UNKNOWN + lastCookTime_unreported)."""

    def __init__(self, last_cook_ms):
        self._last_cook_ms = last_cook_ms

    def needsToCook(self):
        return True

    def isTimeDependent(self, for_last_cook=False):
        return False

    def lastCookTime(self):
        return self._last_cook_ms

    def cookCount(self):
        return 0

    def geometry(self):
        class _G:
            def intrinsicValue(self, name):
                return 0

        return _G()

    def path(self):
        return "/obj/geo1/never_cooked1"


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


class _NodeWithFailingCookCountRealCookTime:
    """Reviewer finding F2: cookCount() raises (safe_call -> None) while lastCookTime()
    itself returns a real, non-positive value (0.0). `cook_count` is None here, NOT 0 --
    None must be treated the same as "no cook evidence" (does not fire
    lastCookTime_unreported), same as a genuine 0, never mistaken for cook evidence."""

    def needsToCook(self):
        return False

    def isTimeDependent(self, for_last_cook=False):
        return False

    def lastCookTime(self):
        return 0.0

    def cookCount(self):
        raise RuntimeError("simulated failure reading cookCount")

    def geometry(self):
        class _G:
            def intrinsicValue(self, name):
                return 0

        return _G()

    def path(self):
        return "/obj/geo1/cookcount_raises1"


class _NodeWithFailingLastCookTimeRealCookCount:
    """Reviewer finding F3: lastCookTime() raises AND cookCount() returns a real positive
    count (5) -- the "double warning" case: safe_call's own generic exception warning AND
    the lastCookTime_unreported guard warning must BOTH be present, since cook evidence
    genuinely exists here."""

    def needsToCook(self):
        return False

    def isTimeDependent(self, for_last_cook=False):
        return False

    def lastCookTime(self):
        raise RuntimeError("simulated failure reading lastCookTime")

    def cookCount(self):
        return 5

    def geometry(self):
        class _G:
            def intrinsicValue(self, name):
                return 0

        return _G()

    def path(self):
        return "/obj/geo1/broken_timed_but_cooked1"


class _NodeWithBoolLastCookTime:
    """Reviewer finding F4a: lastCookTime() returns the Python bool `True` (an int
    subclass -- `True > 0` is `True`, `True / 1000.0` is `0.001`). Must be rejected as a
    measurement, not silently divided into a fabricated 0.001-second cook."""

    def needsToCook(self):
        return False

    def isTimeDependent(self, for_last_cook=False):
        return False

    def lastCookTime(self):
        return True

    def cookCount(self):
        return 5

    def geometry(self):
        class _G:
            def intrinsicValue(self, name):
                return 0

        return _G()

    def path(self):
        return "/obj/geo1/bool_last_cook_time1"


class _NodeWithNonNumericLastCookTime:
    """Reviewer finding F4b: lastCookTime() returns a non-numeric type (a string). Must
    degrade to UNKNOWN, never raise TypeError out of observe_node_passively (a numeric
    comparison against a string would raise if the guard is not type-checked)."""

    def needsToCook(self):
        return False

    def isTimeDependent(self, for_last_cook=False):
        return False

    def lastCookTime(self):
        return "0.0"

    def cookCount(self):
        return 5

    def geometry(self):
        class _G:
            def intrinsicValue(self, name):
                return 0

        return _G()

    def path(self):
        return "/obj/geo1/non_numeric_last_cook_time1"


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


def test_zero_ms_with_cook_evidence_is_unknown_not_fabricated_zero():
    """H22.0.400 headless contract (Mile 3b, harness/notes/cache_h22_contract_assay_
    22.0.400.json item 3): lastCookTime() returns 0.0 UNCONDITIONALLY for real cooks
    headless. Once cookCount() > 0 (real cook evidence), a 0.0/None/negative reading is
    INDISTINGUISHABLE from that unreported case and must never be reported as a measured
    0.0-second cook (CLAUDE.md binding constraint #3: "Unmeasured values are UNKNOWN. Never
    zero, never a default"). Supersedes the old
    ``test_zero_ms_converts_to_zero_seconds_not_none`` — that assertion (0.0 ms -> 0.0 s,
    confidence="high") directly contradicts this contract and has been replaced, not kept
    alongside it.

    Fails if a 0.0 ms reading with cookCount()=1 is still reported as a measured 0.0-second,
    high-confidence value instead of degrading to UNKNOWN with a warning.
    """
    node = _CleanNodeWithCookTime(last_cook_ms=0.0)
    result = chp.observe_node_passively(node)

    assert result["last_cook_seconds"]["value"] is None
    assert result["last_cook_seconds"]["confidence"] == "unknown"
    assert result["last_cook_seconds"]["source"] == "unknown"
    assert any("lastCookTime_unreported" in w for w in result["warnings"])


def test_none_last_cook_time_with_cook_evidence_is_unknown_with_warning():
    """Fails if a None lastCookTime() reading alongside cookCount()>0 (real cook evidence)
    is treated as ordinary unknown WITHOUT the lastCookTime_unreported warning, or if it is
    ever fabricated into a numeric value.
    """
    node = _CleanNodeWithCookTime(last_cook_ms=None)
    result = chp.observe_node_passively(node)

    assert result["last_cook_seconds"]["value"] is None
    assert result["last_cook_seconds"]["confidence"] == "unknown"
    assert any("lastCookTime_unreported" in w for w in result["warnings"])


def test_negative_last_cook_time_with_cook_evidence_is_unknown_with_warning():
    """Fails if a negative lastCookTime() reading (however unlikely) alongside real cook
    evidence is treated as a measured value instead of degrading to UNKNOWN + warning —
    the guard must not special-case 0.0 while missing other non-positive readings.
    """
    node = _CleanNodeWithCookTime(last_cook_ms=-1.0)
    result = chp.observe_node_passively(node)

    assert result["last_cook_seconds"]["value"] is None
    assert result["last_cook_seconds"]["confidence"] == "unknown"
    assert any("lastCookTime_unreported" in w for w in result["warnings"])


def test_zero_ms_without_cook_evidence_is_ordinary_unknown_no_special_warning():
    """A node that has genuinely never cooked (cookCount()==0) reading 0.0/None is NOT a
    contract violation — it's ordinary "not measured yet", same as any other unmeasured
    field. Fails if the lastCookTime_unreported warning fires here (it must only fire when
    cook evidence — cookCount()>0 — actually exists), or if the value is fabricated.
    """
    node = _NeverCookedNode(last_cook_ms=0.0)
    result = chp.observe_node_passively(node)

    assert result["last_cook_seconds"]["value"] is None
    assert result["last_cook_seconds"]["confidence"] == "unknown"
    assert not any("lastCookTime_unreported" in w for w in result["warnings"])


def test_none_ms_without_cook_evidence_is_ordinary_unknown_no_special_warning():
    """Same as above with a None reading instead of 0.0 — cookCount()==0 means no cook
    evidence exists, so no lastCookTime_unreported warning should fire.
    """
    node = _NeverCookedNode(last_cook_ms=None)
    result = chp.observe_node_passively(node)

    assert result["last_cook_seconds"]["value"] is None
    assert not any("lastCookTime_unreported" in w for w in result["warnings"])


def test_positive_ms_still_converts_normally_regardless_of_guard():
    """Fails if the Mile 3b guard changes behavior for a genuine positive lastCookTime()
    reading in any way — same ms->s divide, same confidence="high", same source, as before
    this guard existed. Positive readings are real measured evidence and bypass the guard
    entirely.
    """
    node = _CleanNodeWithCookTime(last_cook_ms=6180.0)
    result = chp.observe_node_passively(node)

    assert result["last_cook_seconds"]["value"] == 6.18
    assert result["last_cook_seconds"]["confidence"] == "high"
    assert result["last_cook_seconds"]["source"] == "hou.OpNode.lastCookTime"
    assert not any("lastCookTime_unreported" in w for w in result["warnings"])


def test_failed_last_cook_time_read_never_fabricates_a_number():
    """Fails if a lastCookTime() exception produces a fake 0.0 instead of an honest
    unknown evidence wrapper — this is the exact defect class named in adjudication a4/a5
    ("never a guessed fallback"), applied to the cook-time field specifically.

    Discriminating negative assertion: this fixture's cookCount() is 0 (no cook evidence),
    so the Mile 3b `lastCookTime_unreported` guard must NOT fire — only safe_call's own
    generic "lastCookTime raised ..." warning should be present. (A bare
    `any("lastCookTime" in w ...)` cannot tell these apart, since
    "lastCookTime_unreported" contains "lastCookTime" as a substring — this asserts the
    stronger, discriminating condition.)
    """
    node = _NodeWithFailingLastCookTime()
    result = chp.observe_node_passively(node)

    seconds = result["last_cook_seconds"]
    assert seconds["value"] is None
    assert seconds["source"] == "unknown"
    assert seconds["confidence"] == "unknown"
    assert any("lastCookTime" in w for w in result["warnings"])
    assert not any("lastCookTime_unreported" in w for w in result["warnings"])


def test_failed_cook_count_read_is_treated_as_no_cook_evidence():
    """Reviewer finding F2 (BLOCKED review, Mile 3b). ``cookCount()`` raising degrades to
    ``None`` via safe_call -- ``None`` must be treated exactly like a genuine 0 (no cook
    evidence), so a non-positive lastCookTime() reading here is ordinary unknown, WITHOUT
    the lastCookTime_unreported warning. Fails if a failed cookCount() read is ever
    mistaken for cook evidence (which would wrongly fire the warning) or if the value is
    ever fabricated into a number.
    """
    node = _NodeWithFailingCookCountRealCookTime()
    result = chp.observe_node_passively(node)

    seconds = result["last_cook_seconds"]
    assert seconds["value"] is None
    assert seconds["confidence"] == "unknown"
    assert not any("lastCookTime_unreported" in w for w in result["warnings"])
    assert any("cookCount" in w for w in result["warnings"])


def test_failed_last_cook_time_with_real_cook_count_carries_both_warnings():
    """Reviewer finding F3 (BLOCKED review, Mile 3b) -- the "double warning" case:
    lastCookTime() raises (safe_call's own generic exception warning) AND cookCount()
    genuinely returns a positive count (real cook evidence), so the
    lastCookTime_unreported guard must ALSO fire -- both warnings must be present
    simultaneously, and the value must never be fabricated either way.
    """
    node = _NodeWithFailingLastCookTimeRealCookCount()
    result = chp.observe_node_passively(node)

    seconds = result["last_cook_seconds"]
    assert seconds["value"] is None
    assert seconds["confidence"] == "unknown"
    assert any("lastCookTime raised" in w for w in result["warnings"]), (
        "safe_call's own generic exception warning must still be present"
    )
    assert any("lastCookTime_unreported" in w for w in result["warnings"]), (
        "cookCount()=5 is real cook evidence -- the guard must ALSO fire"
    )


def test_bool_last_cook_time_with_cook_evidence_is_unknown_not_fabricated():
    """Reviewer finding F4a (BLOCKED review, Mile 3b) -- ``bool`` is an ``int`` subclass
    in Python (``True > 0`` is ``True``); a naive numeric-positive check would divide
    ``True`` by 1000 into a fabricated 0.001-second cook. Fails if the guard's predicate
    ever accepts a bool as a genuine millisecond measurement.
    """
    node = _NodeWithBoolLastCookTime()
    result = chp.observe_node_passively(node)

    seconds = result["last_cook_seconds"]
    assert seconds["value"] is None, (
        f"bool True must never convert to a fabricated seconds value, got {seconds['value']!r}"
    )
    assert seconds["confidence"] == "unknown"
    assert any("lastCookTime_unreported" in w for w in result["warnings"])


def test_non_numeric_last_cook_time_degrades_to_unknown_never_raises():
    """Reviewer finding F4b (BLOCKED review, Mile 3b) -- a non-numeric lastCookTime()
    return value (e.g. a string) must degrade to UNKNOWN, never raise TypeError out of
    observe_node_passively (a bare ``last_cook_ms > 0`` comparison against a string would
    raise; the guard must type-check before comparing).
    """
    node = _NodeWithNonNumericLastCookTime()
    result = chp.observe_node_passively(node)  # must not raise

    seconds = result["last_cook_seconds"]
    assert seconds["value"] is None
    assert seconds["confidence"] == "unknown"
    assert any("lastCookTime_unreported" in w for w in result["warnings"])


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
