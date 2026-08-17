"""W5-MEASURES cook-verify contracts — acceptance goldens.

Pins the three leg acceptance predicates:
  1. the measures module covers all five output kinds, each with an UNKNOWN condition
  2. the explosion detector fires on the broken golden, silent on the healthy one
  3. a measurement projects to an EXISTING synapse.science.exposure rung/tier
     (extends, never forks — the exposure contract tests stay green untouched)

FP2 throughout: an unmeasured output is UNKNOWN, never a fabricated pass.
Pure Python — no hou, no hython. The live cook that produces observations is the
seat gate (rulebook/goldens/README.md); here we judge the observations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.validation.measures import (  # noqa: E402
    CONTRACTS, OUTPUT_KINDS, UNKNOWN_CONDITIONS, MeasureResult,
    measure, measure_image, measure_sim, measure_geometry,
    measure_channels, measure_graph, exposure_rung, exposure_tier,
    MEASURED, UNKNOWN, FAIL, EXPLODING,
)
from synapse.validation.explosion import (  # noqa: E402
    detect_explosion, STABLE, EXPLODING as EXPL_EXPLODING, UNKNOWN as EXPL_UNKNOWN,
)

_GOLDENS = _ROOT / "rulebook" / "goldens"


def _golden(domain, name):
    return json.loads((_GOLDENS / domain / f"{name}.json").read_text(encoding="utf-8"))


# ── Acceptance 1: all five output kinds covered, each with an UNKNOWN condition ─

def test_all_five_output_kinds_have_a_contract():
    assert set(OUTPUT_KINDS) == {"image", "sim", "geometry", "channels", "graph"}
    assert set(CONTRACTS) == set(OUTPUT_KINDS)
    # every kind has a stated UNKNOWN condition — the honesty guard can't be dropped
    for kind in OUTPUT_KINDS:
        assert kind in UNKNOWN_CONDITIONS and UNKNOWN_CONDITIONS[kind]


@pytest.mark.parametrize("kind,empty_obs", [
    ("image", {}),
    ("sim", {}),
    ("geometry", {}),
    ("channels", {}),
    ("graph", {}),
])
def test_missing_observation_renders_unknown_not_pass(kind, empty_obs):
    # FP2: no observation -> UNKNOWN with the exact reason, never MEASURED.
    r = measure(kind, empty_obs)
    assert r.verdict == UNKNOWN
    assert r.unknown_reason == UNKNOWN_CONDITIONS[kind]
    assert r.signals == {}


def test_unknown_kind_is_unknown_never_fabricated():
    r = measure("pointcloud", {"anything": 1})
    assert r.verdict == UNKNOWN
    assert "no measurement contract" in r.unknown_reason


def test_image_measured_and_fail():
    ok = measure_image({"resolution": [1920, 1080], "channels": ["R", "G", "B"],
                        "stats": {"R": {"min": 0.0, "max": 1.0, "mean": 0.4}}, "hash": "abc"})
    assert ok.verdict == MEASURED and ok.signals["resolution"] == (1920, 1080)
    bad_res = measure_image({"resolution": [0, 0], "stats": {}})
    assert bad_res.verdict == FAIL
    nan_stats = measure_image({"resolution": [8, 8], "stats": {"R": {"mean": float("nan")}}})
    assert nan_stats.verdict == FAIL


def test_geometry_measured_fail_unknown():
    assert measure_geometry({"point_count": None, "prim_count": None}).verdict == UNKNOWN
    ok = measure_geometry({"point_count": 100, "prim_count": 40, "bbox": [0, 0, 0, 1, 1, 1], "weight_sum": 1.0})
    assert ok.verdict == MEASURED
    assert measure_geometry({"point_count": 5, "prim_count": 2, "weight_sum": 0.7}).verdict == FAIL
    assert measure_geometry({"point_count": 5, "prim_count": 2, "has_nan_positions": True}).verdict == FAIL


def test_channels_measured_fail_unknown():
    assert measure_channels({"samples": 0}).verdict == UNKNOWN
    assert measure_channels({"samples": 240, "range": [-1.0, 1.0], "variance": 0.2}).verdict == MEASURED
    assert measure_channels({"samples": 10, "range": [5.0, -5.0]}).verdict == FAIL  # inverted range


def test_graph_measured_fail_unknown():
    assert measure_graph({}).verdict == UNKNOWN                       # compiles absent
    assert measure_graph({"compiles": True, "errors": [], "invokes": True}).verdict == MEASURED
    assert measure_graph({"compiles": False}).verdict == FAIL
    assert measure_graph({"compiles": True, "errors": ["boom"]}).verdict == FAIL
    assert measure_graph({"compiles": True, "invokes": False}).verdict == FAIL


# ── Acceptance 2: explosion detector — fires on broken, silent on healthy ──────

def test_healthy_golden_reads_stable():
    g = _golden("sim", "healthy_sim")
    r = measure_sim(g["obs"])
    assert r.verdict == MEASURED
    ev = detect_explosion(g["obs"]["frames"])
    assert ev.verdict == STABLE
    assert g["expect"]["explosion"] == STABLE


def test_exploding_golden_reads_exploding_with_anchor():
    g = _golden("sim", "exploding_sim")
    r = measure_sim(g["obs"])
    assert r.verdict == EXPLODING
    ev = detect_explosion(g["obs"]["frames"])
    assert ev.verdict == EXPL_EXPLODING
    # anchored, not a vibe: the exact signal + offending frame the golden pins
    assert ev.signal == g["expect"]["signal"] == "ke_growth"
    assert ev.offending_frame == g["expect"]["offending_frame"] == 5


def test_detector_nan_and_strain_and_empty():
    nan = detect_explosion([{"frame": 1, "kinetic_energy": 1.0}, {"frame": 2, "kinetic_energy": float("nan")}])
    assert nan.verdict == EXPL_EXPLODING and nan.signal == "nan" and nan.offending_frame == 2
    strain = detect_explosion([{"frame": 1, "max_strain": 3.0}, {"frame": 2, "max_strain": 42.0}])
    assert strain.verdict == EXPL_EXPLODING and strain.signal == "strain" and strain.offending_frame == 2
    assert detect_explosion([]).verdict == EXPL_UNKNOWN                       # nothing measured
    assert detect_explosion([{"frame": 1, "max_strain": 0.1}]).verdict == EXPL_UNKNOWN  # no KE anywhere


def test_ke_growth_needs_full_window_and_ratio():
    # doubles but only across 3 frames with window=5 -> not enough frames -> STABLE
    frames = [{"frame": i, "kinetic_energy": ke} for i, ke in enumerate([1.0, 2.1, 4.4], 1)]
    assert detect_explosion(frames, ke_window=5).verdict == STABLE
    # rises but ratio under threshold -> STABLE
    slow = [{"frame": i, "kinetic_energy": ke} for i, ke in enumerate([10, 11, 12, 13, 14], 1)]
    assert detect_explosion(slow, ke_window=5, ke_ratio_threshold=2.0).verdict == STABLE


# ── Acceptance 3 (extends, never forks): measurement -> existing exposure rung ──

def test_exposure_rung_mapping_is_honest():
    assert exposure_rung(MeasureResult("sim", MEASURED)) == "V1_output"
    assert exposure_rung(MeasureResult("sim", UNKNOWN)) == "V0_membership"
    assert exposure_rung(MeasureResult("sim", FAIL)) == "V1-degraded"
    assert exposure_rung(MeasureResult("sim", EXPLODING)) == "V1-degraded"


def test_exposure_tier_projects_through_existing_system():
    # Proves the ladder EXTENDS synapse.science.exposure: our rungs feed ITS
    # highest_tier and land on ITS tiers. If exposure.py drifts these rungs, this
    # fails loud — the extension stays honest to the contract.
    exposure = pytest.importorskip("synapse.science.exposure")
    assert exposure.highest_tier(["V1_output"]) == "foreground"
    assert exposure_tier(MeasureResult("image", MEASURED)) == "foreground"
    assert exposure_tier(MeasureResult("image", UNKNOWN)) == "surfaced_unverified"
    assert exposure_tier(MeasureResult("image", FAIL)) == "surfaced_caveat"
