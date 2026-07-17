"""RETINA T1 — real pixel-metric tests (need OpenCV + numpy).

These run in the RETINA worker venv (retina/requirements.txt) and on any dev
interpreter that already has cv2 + numpy; they SKIP cleanly in stock CI
(ubuntu/macos, no cv2), so the full ``pytest tests/`` stays green everywhere. The
cv2-free contract (event shape, roll-up, honesty, qc_profiles) is pinned
separately in ``test_retina_t1_schema.py`` — so CI still verifies the T1 contract
even with cv2 absent.

Availability is detected WITHOUT importing the native module at collection time
(``importlib.util.find_spec``); cv2/numpy are imported only inside the guarded
block below, exactly like the repo's other optional-native tests
(test_evaluator_io.py HAS_NUMPY, test_chat_panel.py _QT_AVAILABLE).
"""

from __future__ import annotations

import importlib.util

import pytest

_HAS_CV2 = importlib.util.find_spec("cv2") is not None
_HAS_NUMPY = importlib.util.find_spec("numpy") is not None

pytestmark = pytest.mark.skipif(
    not (_HAS_CV2 and _HAS_NUMPY),
    reason="opencv-python-headless + numpy not installed (RETINA worker venv only)",
)

if _HAS_CV2 and _HAS_NUMPY:  # imported only when present — never crashes collection
    import numpy as np

    from retina import qc_profiles
    from retina import t1
    from retina.tests.fixtures import img_synth

    PROFILE = qc_profiles.resolve_profile(qc_profiles.load_profiles())

NOW = "2026-07-17T00:00:00+00:00"


def _named(event, name):
    for c in event["checks"]:
        if c["name"] == name:
            return c
    return None


# --- the seven-metric kit --------------------------------------------------

def test_nan_inf_census_clean_passes():
    plane = img_synth.gradient_plane()
    check = t1.nan_inf_census(plane)
    assert check["pass"] is True
    assert check["nan_count"] == 0 and check["inf_count"] == 0


def test_nan_inf_census_catches_nan():
    plane = img_synth.inject_nan(img_synth.gradient_plane())
    check = t1.nan_inf_census(plane)
    assert check["pass"] is False
    assert check["nan_count"] >= 1


def test_black_blown_detects_black_frame():
    black = img_synth.flat_plane(value=0.0)
    check = t1.black_blown_frame(
        black,
        black_threshold=PROFILE["black_threshold"],
        blown_threshold=PROFILE["blown_threshold"],
        ratio=PROFILE["black_ratio"],
    )
    assert check["pass"] is False
    assert check["near_black_ratio"] == 1.0


def test_black_blown_detects_blown_frame():
    blown = img_synth.flat_plane(value=1.0)
    check = t1.black_blown_frame(
        blown,
        black_threshold=PROFILE["black_threshold"],
        blown_threshold=PROFILE["blown_threshold"],
        ratio=PROFILE["black_ratio"],
    )
    assert check["pass"] is False
    assert check["blown_ratio"] == 1.0


def test_black_blown_passes_normal_frame():
    plane = img_synth.gradient_plane()
    check = t1.black_blown_frame(
        plane,
        black_threshold=PROFILE["black_threshold"],
        blown_threshold=PROFILE["blown_threshold"],
        ratio=PROFILE["black_ratio"],
    )
    assert check["pass"] is True


def test_clip_percent_flags_clipped_frame():
    blown = img_synth.flat_plane(value=1.0)
    check = t1.clip_percent(
        blown, low=PROFILE["black_threshold"], high=PROFILE["blown_threshold"],
        clip_ratio=PROFILE["clip_ratio"],
    )
    assert check["pass"] is False
    assert check["clip_fraction"] > PROFILE["clip_ratio"]


def test_firefly_count_catches_injected_outliers():
    plane = img_synth.inject_fireflies(img_synth.flat_plane(value=0.2), count=8, value=50.0)
    check = t1.firefly_count(plane, std_devs=PROFILE["firefly_std_devs"])
    assert check["firefly_count"] >= 1


def test_ssim_identical_is_one():
    plane = img_synth.gradient_plane()
    val = t1.ssim(plane, plane, data_range=PROFILE["ssim_data_range"])
    assert val == pytest.approx(1.0, abs=1e-6)


def test_ssim_changed_is_below_one():
    before, after = img_synth.before_after_pair()
    val = t1.ssim(before, after, data_range=PROFILE["ssim_data_range"])
    assert val < 1.0


# --- scoped-delta primitives (§5) -----------------------------------------

def test_change_mask_localizes_the_change():
    before, after = img_synth.before_after_pair(region=(16, 32, 16, 32))
    mask = t1.change_mask(
        before, after,
        diff_threshold=PROFILE["diff_threshold"], morph_radius=PROFILE["morph_radius"],
    )
    assert mask.dtype == np.uint8
    # the change lives inside the region and (mostly) nowhere else
    assert mask[20, 20] == 1
    assert mask[2, 2] == 0


def test_id_matte_extracts_target_region():
    ids = img_synth.id_plane(regions=[(7, (16, 32, 16, 32))])
    matte = t1.id_matte(ids, 7, dilation=0)
    assert matte[20, 20] == 1
    assert matte[2, 2] == 0


def test_containment_pass_when_change_inside_matte():
    region = (16, 32, 16, 32)
    before, after = img_synth.before_after_pair(region=region)
    ids = img_synth.id_plane(regions=[(7, region)])
    mask = t1.change_mask(before, after, diff_threshold=PROFILE["diff_threshold"],
                          morph_radius=PROFILE["morph_radius"])
    matte = t1.id_matte(ids, 7, dilation=PROFILE["matte_dilation"])
    check = t1.containment(mask, matte, leak_eps=PROFILE["leak_eps"])
    assert check["pass"] is True
    assert check["leak_px"] <= PROFILE["leak_eps"]


def test_containment_fails_when_change_leaks_outside_matte():
    # change region and matte region do NOT overlap -> every changed pixel leaks
    before, after = img_synth.before_after_pair(region=(4, 12, 4, 12))
    ids = img_synth.id_plane(regions=[(7, (40, 56, 40, 56))])
    mask = t1.change_mask(before, after, diff_threshold=PROFILE["diff_threshold"],
                          morph_radius=PROFILE["morph_radius"])
    matte = t1.id_matte(ids, 7, dilation=PROFILE["matte_dilation"])
    check = t1.containment(mask, matte, leak_eps=PROFILE["leak_eps"])
    assert check["pass"] is False
    assert check["leak_px"] > PROFILE["leak_eps"]


def test_ssim_outside_high_when_change_confined_to_matte():
    region = (16, 32, 16, 32)
    before, after = img_synth.before_after_pair(region=region)
    ids = img_synth.id_plane(regions=[(7, region)])
    matte = t1.id_matte(ids, 7, dilation=PROFILE["matte_dilation"])
    check = t1.ssim_outside(before, after, matte, ssim_min=PROFILE["ssim_min"],
                            data_range=PROFILE["ssim_data_range"])
    assert check["pass"] is True
    assert check["val"] >= PROFILE["ssim_min"]


# --- the assembled event M3 drives ----------------------------------------

def test_assess_scoped_delta_passes_contained_change():
    region = (16, 32, 16, 32)
    before, after = img_synth.before_after_pair(region=region)
    ids = img_synth.id_plane(regions=[(7, region)])
    ev = t1.assess_scoped_delta(
        before, after, ids, 7, PROFILE, claim="material_swap:/geo/x", now=NOW,
    )
    assert ev["tier"] == 1
    assert ev["verdict"] == "pass"
    assert _named(ev, "delta_containment")["pass"] is True
    assert _named(ev, "ssim_outside")["pass"] is True


def test_assess_scoped_delta_fails_leaked_change():
    before, after = img_synth.before_after_pair(region=(4, 12, 4, 12))
    ids = img_synth.id_plane(regions=[(7, (40, 56, 40, 56))])
    ev = t1.assess_scoped_delta(
        before, after, ids, 7, PROFILE, claim="material_swap:/geo/x", now=NOW,
    )
    assert ev["verdict"] == "fail"
    assert _named(ev, "delta_containment")["pass"] is False


def test_assess_scoped_delta_honest_without_baseline():
    """No baseline (before=None) -> containment + ssim_outside inconclusive, never
    a silent pass (§7)."""
    _, after = img_synth.before_after_pair()
    ev = t1.assess_scoped_delta(
        None, after, None, None, PROFILE, claim="c", now=NOW,
    )
    assert ev["verdict"] == "inconclusive"
    assert _named(ev, "delta_containment")["pass"] is None
    assert _named(ev, "ssim_outside")["pass"] is None


def test_assess_scoped_delta_honest_without_id_aov():
    """A baseline but no ID AOV -> containment inconclusive (absent AOV), never a
    silent pass (§7)."""
    before, after = img_synth.before_after_pair()
    ev = t1.assess_scoped_delta(
        before, after, None, None, PROFILE, claim="c", now=NOW,
    )
    assert _named(ev, "delta_containment")["pass"] is None
    assert ev["verdict"] == "inconclusive"


def test_assess_frame_honest_without_baseline():
    plane = img_synth.gradient_plane()
    ev = t1.assess_frame(plane, PROFILE, claim="render:health", now=NOW)
    assert ev["tier"] == 1
    assert _named(ev, "ssim")["pass"] is None  # no baseline -> inconclusive


def test_assess_frame_clean_with_baseline_passes():
    plane = img_synth.gradient_plane()
    ev = t1.assess_frame(plane, PROFILE, claim="render:health", now=NOW, baseline=plane)
    assert ev["verdict"] == "pass"
    assert _named(ev, "ssim")["pass"] is True


# --- projection primitive --------------------------------------------------

def test_project_bbox_maps_world_to_pixels():
    # An identity world_to_ndc maps a world AABB spanning NDC [-1,1] to the full
    # frame; a small box near NDC origin lands near frame centre.
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    bbox = t1.project_bbox(identity, [-0.1, -0.1, 0.5, 0.1, 0.1, 0.5], 100, 100)
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert 0 <= x0 <= x1 <= 99
    assert 0 <= y0 <= y1 <= 99
    # centred box -> straddles the middle
    assert x0 < 50 < x1


# --- honesty of the raw metric surface ------------------------------------

def test_metrics_raise_without_pixels_is_not_reachable_here():
    """Sanity: within this guarded module pixels ARE available, so pixels_available
    is True — the T1Unavailable honest-raise path is exercised implicitly by the
    cv2-free schema tests importing t1 without calling the metrics."""
    assert t1.pixels_available() is True
