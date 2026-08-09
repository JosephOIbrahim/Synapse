"""Mile 2 (resource-aware-cache Phase 0, R-CACHE-1) — the MANDATORY negative control.

Blueprint §8.2: "Given a fake node whose ``needsToCook()`` returns true and whose
``geometry()`` raises if called, the passive-assessment function must complete without
calling ``geometry()`` and return ``measure_first`` or a decision based on valid historical
evidence." Binding constraint #5: "geometry() is NEVER called when needsToCook() is True.
The negative control above is mandatory and must pass."

Pure Python. No ``hou`` import anywhere in this file or in the module under test's
critical path — ``host/cache_host_probe.py`` guards its own ``hou`` import and every
function exercised here is duck-typed against the fake node below. This file is runnable
with zero Houdini present:

    python -m pytest tests/test_cache_no_forced_cook.py -v

Every test states the condition under which it fails.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HOST_DIR = _REPO_ROOT / "host"
if str(_HOST_DIR) not in sys.path:
    sys.path.insert(0, str(_HOST_DIR))

import cache_host_probe as chp  # noqa: E402


class _GeometryTripwire(AssertionError):
    """Distinct exception type so a test can assert on *this* failure specifically,
    never confusing it with an unrelated AssertionError from elsewhere in the call."""


class FakeDirtyNode:
    """needsToCook() is True; geometry() raises if called at all — the tripwire."""

    def __init__(self, path="/obj/geo1/expensive_solver1"):
        self._path = path
        self.geometry_call_count = 0

    def needsToCook(self):
        return True

    def isTimeDependent(self, for_last_cook=False):
        return True

    def lastCookTime(self):
        return 6180.0  # milliseconds — must NOT be read as seconds anywhere downstream

    def cookCount(self):
        return 42

    def geometry(self):
        self.geometry_call_count += 1
        raise _GeometryTripwire(
            "node.geometry() was called on a dirty node — this forces the exact cook "
            "passive assessment exists to avoid triggering"
        )

    def path(self):
        return self._path


class FakeCleanNode:
    """Contrast case: needsToCook() is False, so geometry() reading IS expected and safe."""

    def __init__(self, path="/obj/geo1/static_box1", memoryusage=1048576):
        self._path = path
        self.geometry_call_count = 0
        self._memoryusage = memoryusage

    def needsToCook(self):
        return False

    def isTimeDependent(self, for_last_cook=False):
        return False

    def lastCookTime(self):
        return 12.5

    def cookCount(self):
        return 3

    def geometry(self):
        self.geometry_call_count += 1
        return _FakeGeometry(self._memoryusage)

    def path(self):
        return self._path


class _FakeGeometry:
    def __init__(self, memoryusage):
        self._memoryusage = memoryusage

    def intrinsicValue(self, name):
        assert name == "memoryusage"
        return self._memoryusage


class FakeUnknownDirtyNode:
    """needsToCook() itself fails (returns None via safe_call) — neither branch is a green
    light to guess. geometry() still must never be called."""

    def __init__(self, path="/obj/geo1/broken_query1"):
        self._path = path
        self.geometry_call_count = 0

    def needsToCook(self):
        raise RuntimeError("simulated hou query failure")

    def isTimeDependent(self, for_last_cook=False):
        return None

    def lastCookTime(self):
        return None

    def cookCount(self):
        return None

    def geometry(self):
        self.geometry_call_count += 1
        raise _GeometryTripwire("geometry() called despite unknown dirty state")

    def path(self):
        return self._path


# --------------------------------------------------------------------------- the mandatory control

def test_dirty_node_never_calls_geometry_and_completes():
    """Fails if observe_node_passively ever invokes node.geometry() while needsToCook() is
    True — the tripwire in FakeDirtyNode.geometry() would raise and the call above would
    propagate instead of the function completing normally.
    """
    node = FakeDirtyNode()
    result = chp.observe_node_passively(node)

    assert node.geometry_call_count == 0, (
        "geometry() was called on a dirty node — the mandatory negative control failed"
    )
    assert result["observation_status"] == "dirty_not_forced", (
        f"expected the dirty-not-forced status, got {result['observation_status']!r}"
    )


def test_dirty_node_result_is_measure_first_shaped():
    """Fails if the dirty branch fabricates a geometry_memory_bytes value instead of
    reporting unknown provenance when there is no historical observation to fall back on.
    """
    node = FakeDirtyNode()
    result = chp.observe_node_passively(node)

    geo = result["geometry_memory_bytes"]
    assert geo["value"] is None, "no historical evidence existed — value must stay None"
    assert geo["source"] == "unknown", "unmeasured must report source=unknown, never a guess"
    assert geo["confidence"] == "unknown"


def test_dirty_node_falls_back_to_historical_evidence_without_calling_geometry():
    """Fails if a valid prior observation in last_observation_store is ignored, or if
    geometry() gets called anyway while consulting history.
    """
    store = chp.LastObservationStore()
    node = FakeDirtyNode()
    store.record(node.path(), {
        "geometry_memory_bytes": {"value": 2048, "unit": "bytes", "source": "hou.Geometry.intrinsicValue",
                                   "observed_at": "2026-08-09T00:00:00+00:00",
                                   "scope": f"node:{node.path()}", "confidence": "high"},
    })

    result = chp.observe_node_passively(node, last_observation_store=store)

    assert node.geometry_call_count == 0
    geo = result["geometry_memory_bytes"]
    assert geo["value"] == 2048
    assert geo["source"] == "measured_historical"
    assert geo["confidence"] == "medium", "historical evidence is not the same confidence as a live read"


def test_unknown_dirty_state_never_calls_geometry_either():
    """Fails if a failed needsToCook() query (safe_call returns None) is treated as
    "clean" and geometry() gets read anyway — unknown must never default to the
    permissive branch.
    """
    node = FakeUnknownDirtyNode()
    result = chp.observe_node_passively(node)

    assert node.geometry_call_count == 0
    assert result["observation_status"] == "dirty_unknown"
    assert result["needs_to_cook"]["value"] is None
    assert result["needs_to_cook"]["source"] == "unknown"


def test_unknown_dirty_state_records_typed_warning_not_fake_zero():
    """Fails if the needsToCook() exception is swallowed silently instead of producing a
    typed warning — §17.2: exceptions must produce typed warnings, not zero-valued fake
    evidence.
    """
    node = FakeUnknownDirtyNode()
    result = chp.observe_node_passively(node)

    assert any("needsToCook" in w for w in result["warnings"]), (
        f"expected a typed warning naming needsToCook, got {result['warnings']!r}"
    )


# --------------------------------------------------------------------------- contrast case

def test_clean_node_does_read_geometry():
    """Fails if the clean branch ALSO refuses to read geometry — this proves the dirty-node
    behavior above is a real conditional branch, not geometry() being globally disabled.
    """
    node = FakeCleanNode(memoryusage=4096)
    result = chp.observe_node_passively(node)

    assert node.geometry_call_count == 1
    assert result["observation_status"] == "clean_snapshot"
    geo = result["geometry_memory_bytes"]
    assert geo["value"] == 4096
    assert geo["unit"] == "bytes"
    assert geo["source"] == "hou.Geometry.intrinsicValue"
    assert geo["confidence"] == "high"


def test_clean_snapshot_is_recorded_into_the_observation_store():
    """Fails if a clean observation is not written back to last_observation_store — without
    this, the historical fallback in the dirty branch would never have anything to use.
    """
    store = chp.LastObservationStore()
    node = FakeCleanNode(memoryusage=8192)
    chp.observe_node_passively(node, last_observation_store=store)

    stored = store.lookup(node.path())
    assert stored is not None
    assert stored["geometry_memory_bytes"]["value"] == 8192
