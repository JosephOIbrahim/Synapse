"""HD1 floor fit, levelling and ground (SPEC 5.1, 5.2; design 8.3). Pure numpy: no hou, no pxr, no network.

The chain under test is the one the probe will run: condition the depth, unproject
the kept pixels in raw units (``cloud.unproject_raw``), then fit the floor. Truth
comes from the analytic fixture's truth record or from a closed form, never from
the code under test. The design's measured figures ([M]) are printed beside the
measured values on ``HD1-METRIC`` lines (run with -rP) and never asserted.
Tolerances such as 1e-9 are implementation-correctness pins on exact data, not the
SPEC 9 acceptance tolerances, which belong to D-1.
"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import sys

import pytest

np = pytest.importorskip("numpy")

from synapse.worldlabs.atlas_contracts import ContractError  # noqa: E402
from synapse.worldlabs.importer import ground_transform  # noqa: E402
from synapse.worldlabs.physical import level as hd1_level  # noqa: E402
from synapse.worldlabs.physical.cloud import floor_of, unproject_raw  # noqa: E402
from synapse.worldlabs.physical.depth import condition_depth  # noqa: E402
from synapse.worldlabs.physical.level import (  # noqa: E402
    FLOOR_INLIER_REL,
    FLOOR_MAX_TILT_DEG,
    FLOOR_MIN_INLIER_FRACTION,
    FLOOR_ROWS_FRACTION,
    FLOOR_SEED,
    FloorFit,
    PhysicalBlocked,
    fit_floor,
    ground_offset,
    normal_angle_deg,
    quaternion_angle_deg,
    rotation_matrix,
    smallest_rotation_to_up,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hd1_scene.py"


def _load_fixture():
    """Load tests/fixtures/hd1_scene.py by path (design 2.9); a failed load is unregistered again."""
    mod = sys.modules.get("hd1_scene")
    if mod is None:
        spec = importlib.util.spec_from_file_location("hd1_scene", _FIXTURE)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["hd1_scene"] = mod
        loaded = False
        try:
            spec.loader.exec_module(mod)
            loaded = True
        finally:
            if not loaded:
                sys.modules.pop("hd1_scene", None)
    return mod


hd1_scene = _load_fixture()

_GRIDS = [pytest.param((1280, 720), id="1280x720"), pytest.param((160, 90), id="160x90")]
_PIN = 1e-9          # implementation-correctness pin on exact data, not a SPEC 9 tolerance

# design.md [M] figures (in-memory re-derivation, 2026-11-14). Printed beside the
# measured value, never asserted: a difference is a finding, not an edit.
_DESIGN_FITS_1280 = {
    "A": {"candidates": 230400, "inlier_fraction": 1.0, "tilt_deg": 0.0, "camera_height": 1.5,
          "floor_height": -5.4e-17},
    "B": {"candidates": 230400, "inlier_fraction": 1.0, "tilt_deg": 5.828991157609,
          "normal_error_deg": 2.0e-14, "q_error_deg": 2.0e-14, "camera_height": 1.5,
          "floor_height": -7.756e-03},
    "C": {"candidates": 230400, "inlier_fraction": 1.0, "tilt_deg": 0.0, "normal_error_deg": 1.3e-14,
          "camera_height": 3.75, "floor_height": 1.3e-15},
}
_DESIGN_CLUTTER_FRACTION = 0.1622
_DESIGN_SYNTHETIC_FRACTION = 0.6
_DESIGN_YAW_TWIST_DEG = 0.13101270458640024


def _metric(**fields):
    print("HD1-METRIC", json.dumps(fields, sort_keys=True, allow_nan=False))


_CHAIN = {}


def _chain(name, grid):
    """(variant, depth mask, raw cloud, floor fit) for one fixture variant, computed once per module."""
    key = (name, tuple(grid))
    if key not in _CHAIN:
        v = hd1_scene.variant(name, *grid)
        mask = condition_depth(v.depth, v.confidence)
        raw = unproject_raw(v.frame, v.depth, mask.keep)
        _CHAIN[key] = (v, mask, raw, floor_of(raw))
    return _CHAIN[key]


def _first_row(height):
    """The SPEC 5.1 band in closed form: the bottom 25% of rows, H - ceil(H / 4)."""
    return height - math.ceil(height / 4)


def _conjugate(q):
    return (-q[0], -q[1], -q[2], q[3])


def _inlier_pixels(raw, fit):
    """The (row, col) pixels whose raw points lie in the fit's band, recomputed here."""
    candidate = raw.rows >= fit.first_row
    n = np.array(fit.normal)
    residual = np.abs(raw.points[candidate] @ n + fit.offset)
    inside = residual <= fit.inlier_band
    return set(zip(raw.rows[candidate][inside].tolist(), raw.cols[candidate][inside].tolist()))


def _level_record(name, grid, fit, truth):
    """Measured level and ground numbers beside their truths: printed, never judged."""
    s = truth.metres_per_unit
    record = {"variant": name, "grid": list(grid), "status": fit.status, "reason": fit.reason,
              "candidates": fit.candidates, "inliers": fit.inliers, "inlier_fraction": fit.inlier_fraction,
              "degenerate_samples": fit.degenerate_samples, "seed": fit.seed,
              "rms_over_median_depth": fit.rms_over_median_depth}
    if fit.status == "SUCCESS":
        lift = ground_offset(s, fit)
        record.update({
            "tilt_deg": fit.tilt_deg, "truth_tilt_deg": truth.tilt_deg,
            "tilt_error_deg": fit.tilt_deg - truth.tilt_deg,
            "normal_error_deg": normal_angle_deg(fit.normal, truth.floor_normal),
            "level_q_error_deg": quaternion_angle_deg(fit.level_xyzw, truth.level_xyzw),
            "camera_height_units": fit.camera_height, "truth_camera_height_units": truth.camera_height_units,
            "camera_height_error_units": fit.camera_height - truth.camera_height_units,
            "floor_height_units": fit.floor_height, "truth_floor_height_units": truth.floor_height_units,
            "floor_height_error_units": fit.floor_height - truth.floor_height_units,
            "floor_height_error_m": s * (fit.floor_height - truth.floor_height_units),
            "ground_offset_m": lift, "truth_ground_offset_m": s * truth.ground_offset_units,
            "ground_offset_error_m": lift - s * truth.ground_offset_units,
            "metres_per_unit_used": s, "level_xyzw": list(fit.level_xyzw),
            "truth_level_xyzw": list(truth.level_xyzw),
        })
    return record


# --- design 8.3, tests 1-5: the fixture variants ------------------------------------------

def test_variant_A_is_already_level():
    v, mask, raw, fit = _chain("A", (1280, 720))
    assert fit.status == "SUCCESS" and fit.reason is None
    assert fit.tilt_deg <= _PIN
    assert quaternion_angle_deg(fit.level_xyzw, (0.0, 0.0, 0.0, 1.0)) <= _PIN
    assert abs(fit.camera_height - v.truth.camera_height_units) <= _PIN
    assert abs(fit.floor_height) <= _PIN
    assert fit.inlier_fraction == 1.0
    assert fit.first_row == _first_row(720) == 540
    assert fit.candidates == int(np.count_nonzero(mask.keep[_first_row(720):, :]))
    json.dumps(fit.as_dict(), allow_nan=False)
    _metric(test="variant_A_level", fit=fit.as_dict(), design_figure_M=_DESIGN_FITS_1280["A"])


def test_variant_B_recovers_the_levelling_rotation():
    v, _, _, fit = _chain("B", (1280, 720))
    truth = v.truth
    closed_tilt = math.degrees(math.acos(math.cos(math.radians(3.0)) * math.cos(math.radians(5.0))))
    closed_floor = -1.5 * (1.0 - math.cos(math.radians(3.0)) * math.cos(math.radians(5.0)))
    assert fit.status == "SUCCESS"
    assert normal_angle_deg(fit.normal, truth.floor_normal) <= _PIN
    assert quaternion_angle_deg(fit.level_xyzw, truth.level_xyzw) <= _PIN
    assert abs(fit.tilt_deg - truth.tilt_deg) <= _PIN
    assert abs(fit.tilt_deg - closed_tilt) <= _PIN
    assert abs(fit.floor_height - truth.floor_height_units) <= _PIN
    assert abs(fit.floor_height - closed_floor) <= _PIN
    assert abs(ground_offset(1.0, fit) - truth.ground_offset_units) <= _PIN
    assert abs(fit.camera_height - truth.camera_height_units) <= _PIN
    assert fit.level_xyzw[1] == 0.0
    # A recorded non-goal: levelling cannot recover the yaw left in level (x) q_W.
    to_inverse_tilt = quaternion_angle_deg(fit.level_xyzw, _conjugate(truth.world_tilt_xyzw))
    _metric(test="variant_B_level", record=_level_record("B", (1280, 720), fit, truth),
            closed_form_tilt_deg=closed_tilt, closed_form_floor_height=closed_floor,
            angle_to_inverse_world_tilt_deg=to_inverse_tilt, truth_yaw_twist_deg=truth.yaw_twist_deg,
            design_figure_M=dict(_DESIGN_FITS_1280["B"], yaw_twist_deg=_DESIGN_YAW_TWIST_DEG))


def test_variant_C_fit_is_scale_free():
    a, _, raw_a, fit_a = _chain("A", (1280, 720))
    c, _, raw_c, fit_c = _chain("C", (1280, 720))
    assert fit_c.status == "SUCCESS"
    assert abs(fit_c.camera_height - c.truth.camera_height_units) <= _PIN
    assert abs(fit_c.camera_height - 1.5 / 0.4) <= _PIN
    assert fit_c.inlier_band == FLOOR_INLIER_REL * fit_c.median_depth
    assert fit_a.inlier_band == FLOOR_INLIER_REL * fit_a.median_depth
    assert fit_c.candidates == fit_a.candidates
    pixels_a, pixels_c = _inlier_pixels(raw_a, fit_a), _inlier_pixels(raw_c, fit_c)
    assert pixels_c == pixels_a
    assert len(pixels_c) == fit_c.inliers
    _metric(test="variant_C_scale_free", camera_height_units=fit_c.camera_height,
            truth_camera_height_units=c.truth.camera_height_units,
            camera_height_error_units=fit_c.camera_height - c.truth.camera_height_units,
            inlier_band_units=fit_c.inlier_band, inlier_band_a_m=fit_a.inlier_band,
            band_ratio=fit_c.inlier_band / fit_a.inlier_band, inlier_pixels=len(pixels_c),
            normal_error_deg=normal_angle_deg(fit_c.normal, c.truth.floor_normal),
            design_figure_M=_DESIGN_FITS_1280["C"])


def test_variant_D_masked_pixels_never_reach_the_fit():
    a, mask_a, _, fit_a = _chain("A", (1280, 720))
    d, _, _, fit_d = _chain("D", (1280, 720))
    first = _first_row(720)
    patches = d.truth.corruption["nan"] | d.truth.corruption["above_half_max"]
    expected = fit_a.candidates - int(np.count_nonzero(patches[first:, :]))
    assert fit_d.status == "SUCCESS"
    assert fit_d.candidates == expected
    assert normal_angle_deg(fit_d.normal, fit_a.normal) <= _PIN
    assert max(abs(x - y) for x, y in zip(fit_d.normal, fit_a.normal)) <= _PIN
    assert abs(fit_d.offset - fit_a.offset) <= _PIN
    _metric(test="variant_D_fit", candidates=fit_d.candidates, a_candidates=fit_a.candidates,
            patch_pixels_in_band=int(np.count_nonzero(patches[first:, :])),
            normal_difference_deg=normal_angle_deg(fit_d.normal, fit_a.normal),
            offset_difference=fit_d.offset - fit_a.offset)


def test_fit_repeats_with_the_fixed_seed():
    _, _, raw, first = _chain("B", (1280, 720))
    again = floor_of(raw)
    assert again == first, "two fits with the default seed differ"
    assert first.seed == FLOOR_SEED and first.as_dict()["seed"] == FLOOR_SEED
    small_v, _, small_raw, small_fit = _chain("B", (160, 90))
    assert floor_of(small_raw) == small_fit
    truth = small_v.truth
    for seed in (1, 7, 123456789):
        other = floor_of(small_raw, seed=seed)
        assert other.status == "SUCCESS" and other.seed == seed
        assert normal_angle_deg(other.normal, truth.floor_normal) <= _PIN
        assert abs(other.floor_height - truth.floor_height_units) <= _PIN
        assert abs(other.camera_height - truth.camera_height_units) <= _PIN
    _metric(test="fit_repeats", seeds=[FLOOR_SEED, 1, 7, 123456789],
            normal_error_deg_default_seed=normal_angle_deg(small_fit.normal, truth.floor_normal))


# --- design 8.3, tests 6-9: RANSAC and the UNKNOWN floor ----------------------------------

def test_ransac_rejects_outliers_on_a_synthetic_set():
    rng = np.random.default_rng(20261115)
    grid_rows, plane, clutter = 90, 6000, 4000
    xz = rng.uniform((-3.0, -8.0), (3.0, -2.0), size=(plane + clutter, 2))
    y = np.zeros(plane + clutter)
    y[plane:] = rng.uniform(0.2, 1.5, size=clutter)
    points = np.column_stack((xz[:, 0], y, xz[:, 1]))
    rows = rng.integers(_first_row(grid_rows), grid_rows, size=plane + clutter)
    depth = -xz[:, 1]                     # planar depth for a level camera looking down -Z
    fit = fit_floor(points, rows, depth, grid_rows=grid_rows, camera_position=(0.0, 1.5, 0.0))
    assert fit.status == "SUCCESS"
    assert fit.candidates == plane + clutter
    assert fit.inliers == plane and fit.inlier_fraction == plane / (plane + clutter) == 0.6
    assert fit.tilt_deg <= _PIN
    assert abs(fit.camera_height - 1.5) <= _PIN and abs(fit.floor_height) <= _PIN
    # Review RVM-05 (2026-11-15): the RMS is over the inliers only; the clutter would dominate it otherwise.
    assert fit.rms_over_median_depth <= 1e-12
    assert fit_floor(points, rows, depth, grid_rows=grid_rows, camera_position=(0.0, 1.5, 0.0)) == fit
    _metric(test="ransac_synthetic", inlier_fraction=fit.inlier_fraction, tilt_deg=fit.tilt_deg,
            camera_height=fit.camera_height, floor_height=fit.floor_height,
            rms_over_median_depth=fit.rms_over_median_depth,
            design_figure_M={"inlier_fraction": _DESIGN_SYNTHETIC_FRACTION, "tilt_deg": 1.3e-14})


def _mirrored_plane(h, n=40):
    """An n x n floor grid (n even) at y = +h and -h in a checkerboard, x in [-2, 2], z in [-6, -2].

    The checkerboard averages to zero and is uncorrelated with x and z, so the least-squares plane is
    y = 0 and every residual is exactly h: the RMS over the median planar depth is h / median. The
    planar depth is -z (a level camera looking down -Z), whose median is 4.0.
    """
    i, j = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    x = -2.0 + 4.0 * i / (n - 1)
    z = -6.0 + 4.0 * j / (n - 1)
    y = np.where((i + j) % 2 == 0, h, -h)
    points = np.column_stack((x.ravel(), y.ravel(), z.ravel()))
    return points, np.full(n * n, 89), -points[:, 2]


def test_fit_diagnostics_match_their_closed_forms():
    """Review RVM-05 (2026-11-15): the angle helper, the band's median and the residual RMS, pinned.

    Each is reported to D-1, and before this test each could be computed wrongly with every HD1 test
    green: an angle in radians, a median over every kept point, an RMS not divided by the median.
    """
    assert normal_angle_deg((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)) == 90.0
    assert normal_angle_deg((0.0, 2.5, 0.0), (0.0, 1.0, 0.0)) == 0.0
    assert normal_angle_deg((0.0, 1.0, 0.0), (0.0, -3.0, 0.0)) == 180.0
    for degrees in (1.0, 30.0, 60.0, 135.0):
        r = math.radians(degrees)
        assert abs(normal_angle_deg((math.cos(r), math.sin(r), 0.0), (1.0, 0.0, 0.0)) - degrees) <= 1e-12
    b = hd1_scene.variant("B", 160, 90).truth
    closed_tilt = math.degrees(math.acos(math.cos(math.radians(3.0)) * math.cos(math.radians(5.0))))
    assert abs(normal_angle_deg(b.floor_normal, (0.0, 1.0, 0.0)) - closed_tilt) <= 1e-12
    # The band's median is over the candidates (the bottom rows), not over every kept point.
    medians = {}
    for name, grid in (("A", (1280, 720)), ("B", (160, 90))):
        _, _, raw, fit = _chain(name, grid)
        candidates = raw.rows >= fit.first_row
        assert fit.median_depth == float(np.median(raw.depth[candidates]))
        assert fit.inlier_band == FLOOR_INLIER_REL * fit.median_depth
        assert fit.rms_over_median_depth <= 1e-12            # exact data: every inlier lies on the plane
        medians[name] = {"grid": list(grid), "candidates_median": fit.median_depth,
                         "all_kept_median": float(np.median(raw.depth)),
                         "rms_over_median_depth": fit.rms_over_median_depth}
    # The RMS on residuals known in closed form, with a median planar depth other than 1.
    h = 0.004
    points, rows, depth = _mirrored_plane(h)
    fit = fit_floor(points, rows, depth, grid_rows=90, camera_position=(0.0, 1.5, 0.0))
    median = float(np.median(depth))
    assert abs(median - 4.0) <= 1e-12 and fit.median_depth == median
    assert fit.status == "SUCCESS" and fit.inliers == fit.candidates == points.shape[0]
    assert abs(fit.rms_over_median_depth - h / median) <= 1e-9 * (h / median)
    _metric(test="fit_diagnostics", medians=medians, mirrored_plane={
        "h": h, "points": int(points.shape[0]), "median_depth": median,
        "rms_over_median_depth": fit.rms_over_median_depth, "closed_form": h / median,
        "tilt_deg": fit.tilt_deg, "floor_height": fit.floor_height, "camera_height": fit.camera_height})


def test_contact_strip_inside_the_band_is_reported():
    """Review RVM-10 (2026-11-15; design 2.4): non-floor points inside the inlier band bias the refit.

    A level floor grid with a vertical face standing on it at the box front (z = -2.8 m, |x| <= 0.5 m).
    The face's lowest row sits at half the band height, so it joins the inliers; its other rows are far
    above the band. The tilt and the floor-height bias are printed beside their truth, 0. Nothing about
    their size is asserted: only that the strip is the case meant (inside the band, among the inliers).
    """
    gx, gz = np.meshgrid(np.linspace(-2.0, 2.0, 41), np.linspace(-6.0, -2.0, 41), indexing="ij")
    floor = np.column_stack((gx.ravel(), np.zeros(gx.size), gz.ravel()))
    face_x = np.linspace(-0.5, 0.5, 21)
    heights = (None, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)           # None: the contact row, set from the band
    depth = np.concatenate((-floor[:, 2], np.full(face_x.size * len(heights), 2.8)))
    band = FLOOR_INLIER_REL * float(np.median(depth))
    strip_y = 0.5 * band
    face = np.array([(x, strip_y if y is None else y, -2.8) for y in heights for x in face_x])
    points = np.vstack((floor, face))
    rows = np.full(points.shape[0], 89)
    fit = fit_floor(points, rows, depth, grid_rows=90, camera_position=(0.0, 1.5, 0.0))
    assert fit.status == "SUCCESS" and fit.inlier_band == band
    strip = face_x.size
    assert fit.inliers == floor.shape[0] + strip
    assert all(math.isfinite(v) for v in (fit.tilt_deg, fit.floor_height, fit.camera_height))
    _metric(test="contact_strip", floor_points=int(floor.shape[0]), strip_points=strip,
            face_points_above_band=int(face.shape[0] - strip), band=band, strip_height=strip_y,
            inliers=fit.inliers, tilt_deg=fit.tilt_deg, truth_tilt_deg=0.0, floor_height=fit.floor_height,
            truth_floor_height=0.0, camera_height=fit.camera_height, truth_camera_height=1.5,
            normal=list(fit.normal), rms_over_median_depth=fit.rms_over_median_depth)


def test_floor_unknown_without_valid_bottom_rows():
    v = hd1_scene.variant("A", 1280, 720)
    depth = np.array(v.depth)
    depth[_first_row(720):, :] = np.nan
    mask = condition_depth(depth, v.confidence)
    raw = unproject_raw(v.frame, depth, mask.keep)
    fit = floor_of(raw)
    assert fit.status == "UNKNOWN"
    assert "bottom rows" in fit.reason
    assert fit.candidates == 0
    for name in ("normal", "offset", "level_xyzw", "tilt_deg", "camera_height", "floor_height",
                 "inlier_fraction"):
        assert getattr(fit, name) is None, name
    _metric(test="unknown_no_bottom_rows", fit=fit.as_dict())


def test_floor_unknown_below_the_inlier_fraction():
    v = hd1_scene.variant("A", 160, 90)
    clutter = np.random.default_rng(7).uniform(1.0, 10.0, size=(90, 160))
    every = np.ones((90, 160), dtype=bool)
    fit = floor_of(unproject_raw(v.frame, clutter, every))
    assert fit.status == "UNKNOWN"
    assert fit.inlier_fraction < FLOOR_MIN_INLIER_FRACTION
    assert fit.reason == "inlier fraction below min_inlier_fraction"
    assert fit.level_xyzw is None and fit.camera_height is None and fit.floor_height is None
    conditioned = condition_depth(clutter)
    conditioned_fit = floor_of(unproject_raw(v.frame, clutter, conditioned.keep))
    _metric(test="unknown_low_fraction", inlier_fraction=fit.inlier_fraction, candidates=fit.candidates,
            inliers=fit.inliers, conditioned_kept=conditioned.kept, conditioned_total=conditioned.total,
            conditioned_status=conditioned_fit.status, conditioned_reason=conditioned_fit.reason,
            design_figure_M={"inlier_fraction": _DESIGN_CLUTTER_FRACTION, "conditioned_kept": 0})


def test_floor_unknown_when_only_a_wall_is_in_view():
    v = hd1_scene.no_floor_view()
    mask = condition_depth(v.depth, v.confidence)
    raw = unproject_raw(v.frame, v.depth, mask.keep)
    fit = floor_of(raw)
    assert FLOOR_MAX_TILT_DEG == 30.0
    assert fit.status == "UNKNOWN"
    assert fit.reason == "dominant plane is not floor-like: tilted beyond max_tilt_deg"
    assert fit.inlier_fraction == 1.0
    assert abs(fit.tilt_deg - 90.0) <= _PIN
    assert fit.level_xyzw is None and fit.camera_height is None and fit.floor_height is None
    # Evidence for C-1: the SPEC's inlier rule alone (no tilt gate) calls the wall a floor.
    ungated = floor_of(raw, max_tilt_deg=90.0)
    assert ungated.status == "SUCCESS" and abs(ungated.tilt_deg - 90.0) <= _PIN
    _metric(test="unknown_wall_only", fit=fit.as_dict(), spec_rule_alone_status=ungated.status,
            spec_rule_alone_tilt_deg=ungated.tilt_deg)


# --- design 8.3, tests 10-13: rotation, ground and sign -----------------------------------

def test_smallest_rotation_has_no_yaw():
    assert smallest_rotation_to_up((0.0, 1.0, 0.0)) == (0.0, 0.0, 0.0, 1.0)
    assert smallest_rotation_to_up((0.0, 2.5, 0.0)) == (0.0, 0.0, 0.0, 1.0)
    rng = np.random.default_rng(20261115)
    worst = {"rn_minus_up": 0.0, "angle_minus_tilt_deg": 0.0}
    for _ in range(500):
        n = rng.normal(size=3)
        n[1] = abs(n[1]) + 1e-3
        n /= np.linalg.norm(n)
        q = smallest_rotation_to_up(n)
        assert q[1] == 0.0
        assert abs(sum(c * c for c in q) - 1.0) <= 1e-12
        rotated = rotation_matrix(q) @ n
        error = float(np.max(np.abs(rotated - np.array([0.0, 1.0, 0.0]))))
        tilt = math.degrees(math.atan2(math.hypot(n[0], n[2]), n[1]))
        angle = quaternion_angle_deg(q, (0.0, 0.0, 0.0, 1.0))
        assert error <= 1e-12
        assert abs(angle - tilt) <= 1e-12
        worst["rn_minus_up"] = max(worst["rn_minus_up"], error)
        worst["angle_minus_tilt_deg"] = max(worst["angle_minus_tilt_deg"], abs(angle - tilt))
    with pytest.raises(ContractError):
        smallest_rotation_to_up((0.0, -1.0, 0.0))
    _metric(test="smallest_rotation", samples=500, worst=worst)


def test_ground_offset_uses_the_importer_convention():
    _, _, _, fit = _chain("B", (160, 90))
    for s in (1.0, 0.4, 2.5):
        translate, rotate, uniform = ground_transform(s, fit.floor_height, y_down=False)
        assert ground_offset(s, fit) == translate[1]
        assert ground_offset(s, fit) == -s * fit.floor_height
        assert tuple(rotate) == (0.0, 0.0, 0.0)          # GAP-1: no levelling slot in the importer
        assert uniform == s
    with pytest.raises(ContractError):
        ground_offset(1.0, replace(fit, status="UNKNOWN"))
    for bad in (0.0, -1.0, float("nan"), True, None, "1.0"):
        with pytest.raises(ContractError):
            ground_offset(bad, fit)


def test_ground_offset_recovers_a_known_lift():
    v = hd1_scene.variant("A", 160, 90)
    px, py, pz = v.frame.pose.position
    lifted = replace(v.frame, pose=replace(v.frame.pose, position=(px, py + 0.37, pz)))
    mask = condition_depth(v.depth, v.confidence)
    fit = floor_of(unproject_raw(lifted, v.depth, mask.keep))
    assert fit.status == "SUCCESS"
    assert abs(fit.floor_height - 0.37) <= _PIN
    assert abs(ground_offset(1.0, fit) + 0.37) <= _PIN
    assert abs(fit.camera_height - 1.5) <= _PIN
    _metric(test="known_lift", floor_height=fit.floor_height, ground_offset=ground_offset(1.0, fit),
            camera_height=fit.camera_height, design_figure_M={"floor_height": 0.37, "ground_offset": -0.37})


def test_camera_height_is_signed():
    rng = np.random.default_rng(3)
    xz = rng.uniform((-2.0, -6.0), (2.0, -1.0), size=(500, 2))
    points = np.column_stack((xz[:, 0], np.zeros(500), xz[:, 1]))
    rows = np.full(500, 89)
    fit = fit_floor(points, rows, -xz[:, 1], grid_rows=90, camera_position=(0.0, -1.0, 0.0))
    assert fit.status == "SUCCESS"
    assert abs(fit.camera_height + 1.0) <= _PIN
    above = fit_floor(points, rows, -xz[:, 1], grid_rows=90, camera_position=(0.0, 1.0, 0.0))
    assert abs(above.camera_height - 1.0) <= _PIN


# --- additions beyond design 8.3 ----------------------------------------------------------

@pytest.mark.parametrize("name", ["A", "B", "C", "D"])
@pytest.mark.parametrize("grid", _GRIDS)
def test_level_and_ground_numbers_for_every_variant(name, grid):
    """The level and ground numbers for A to D at both grids, printed beside their truths."""
    v, _, _, fit = _chain(name, grid)
    truth = v.truth
    assert fit.status == "SUCCESS"
    assert normal_angle_deg(fit.normal, truth.floor_normal) <= _PIN
    assert quaternion_angle_deg(fit.level_xyzw, truth.level_xyzw) <= _PIN
    assert abs(fit.camera_height - truth.camera_height_units) <= _PIN
    assert abs(fit.floor_height - truth.floor_height_units) <= _PIN
    assert abs(ground_offset(truth.metres_per_unit, fit)
               - truth.metres_per_unit * truth.ground_offset_units) <= _PIN
    _metric(test="level_and_ground", record=_level_record(name, grid, fit, truth))


def test_fit_floor_refuses_malformed_input():
    points = np.zeros((4, 3))
    rows = np.full(4, 89)
    depth = np.ones(4)
    ok = {"grid_rows": 90, "camera_position": (0.0, 1.5, 0.0)}
    bad_keywords = [
        {"grid_rows": 0}, {"grid_rows": True}, {"grid_rows": 90.0},
        {"camera_position": (0.0, 1.5)}, {"camera_position": (0.0, float("nan"), 0.0)},
        {"seed": -1}, {"seed": 1.5}, {"iterations": 0}, {"inlier_rel": 0.0},
        {"inlier_rel": float("inf")}, {"min_inlier_fraction": 1.5}, {"max_tilt_deg": 0.0},
        {"max_tilt_deg": 91.0}, {"rows_fraction": 0.0}, {"rows_fraction": 1.5},
    ]
    for change in bad_keywords:
        with pytest.raises(ContractError) as caught:
            fit_floor(points, rows, depth, **dict(ok, **change))
        for value in change.values():
            if isinstance(value, float) and math.isfinite(value) and value not in (0.0, 1.0):
                assert repr(value) not in str(caught.value)
    bad_arrays = [
        (np.zeros((4, 2)), rows, depth), (np.zeros(4), rows, depth),
        (points, rows.astype(float), depth), (points, rows, np.ones(3)),
        (np.full((4, 3), np.nan), rows, depth), (points, rows, -depth),
        (points, np.full(4, 90), depth), (points, np.full(4, -1), depth),
        (points.astype(bool), rows, depth),
    ]
    for p, r, z in bad_arrays:
        with pytest.raises(ContractError):
            fit_floor(p, r, z, **ok)
    few = fit_floor(np.zeros((2, 3)), np.full(2, 89), np.ones(2), **ok)
    assert few.status == "UNKNOWN" and few.reason.startswith("fewer than 3") and few.candidates == 2
    flat = fit_floor(np.zeros((5, 3)), np.full(5, 89), np.ones(5), **ok)
    assert flat.status == "UNKNOWN" and flat.reason == "no non-degenerate plane sample"
    assert flat.degenerate_samples == flat.iterations


def test_floor_fit_record_is_json_safe_and_records_its_settings():
    _, _, _, fit = _chain("B", (160, 90))
    record = fit.as_dict()
    json.dumps(record, allow_nan=False)
    assert set(record) == {field for field in FloorFit.__dataclass_fields__}
    assert record["rows_fraction"] == FLOOR_ROWS_FRACTION
    assert record["inlier_rel"] == FLOOR_INLIER_REL
    assert record["min_inlier_fraction"] == FLOOR_MIN_INLIER_FRACTION
    assert record["max_tilt_deg"] == FLOOR_MAX_TILT_DEG
    assert record["first_row"] == _first_row(90) == 67 and record["grid_rows"] == 90
    assert isinstance(record["normal"], list) and isinstance(record["level_xyzw"], list)
    for name in ("tilt_deg", "camera_height", "floor_height", "inlier_fraction", "offset",
                 "rms_over_median_depth", "median_depth", "inlier_band"):
        assert type(record[name]) is float, name
    for name in ("candidates", "inliers", "seed", "iterations", "degenerate_samples"):
        assert type(record[name]) is int, name


def test_numpy_missing_reports_blocked_not_a_crash(monkeypatch):
    monkeypatch.setattr(hd1_level, "NUMPY_AVAILABLE", False)
    monkeypatch.setattr(hd1_level, "np", None)
    fit = hd1_level.fit_floor([[0.0, 0.0, 0.0]], [89], [1.0], grid_rows=90, camera_position=(0.0, 1.5, 0.0))
    assert fit.status == "BLOCKED" and "numpy" in fit.reason
    for name in ("candidates", "inliers", "normal", "level_xyzw", "camera_height", "inlier_fraction"):
        assert getattr(fit, name) is None, name
    assert fit.first_row == 67 and fit.seed == FLOOR_SEED
    json.dumps(fit.as_dict(), allow_nan=False)
    with pytest.raises(PhysicalBlocked, match="^BLOCKED: "):
        hd1_level.rotation_matrix((0.0, 0.0, 0.0, 1.0))
    # The pure-Python helpers need no numpy.
    assert hd1_level.smallest_rotation_to_up((0.0, 1.0, 0.0)) == (0.0, 0.0, 0.0, 1.0)
    assert hd1_level.quaternion_angle_deg((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, -1.0)) == 0.0
    # Bad thresholds still refuse: that check needs no numpy.
    with pytest.raises(ContractError):
        hd1_level.fit_floor([], [], [], grid_rows=90, camera_position=(0.0, 1.5, 0.0), max_tilt_deg=0.0)
