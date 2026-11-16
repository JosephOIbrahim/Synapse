"""HD1 point cloud (SPEC 6; design 8.5). Pure numpy: no hou, no pxr, no network.

The cross-check (principle H6): the numpy unprojection must equal the landed
contract's pure-Python ``unproject_metric`` point for point, compared at the scaled
stage (before levelling and grounding), on variants A and C at 160x90. Then the
stride cap, the footprint formula and the half-pixel measurement (BLU-C-HD-01,
D-HD-04), which is reported as a number and resolved nowhere. The design's measured
figures ([M]) are printed beside the measured values on ``HD1-METRIC`` lines (run
with -rP) and never asserted.
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

from synapse.worldlabs.atlas_contracts import ContractError, unproject_metric  # noqa: E402
from synapse.worldlabs.physical import cloud as hd1_cloud  # noqa: E402
from synapse.worldlabs.physical.cloud import (  # noqa: E402
    FOOTPRINT_K,
    POINT_CAP,
    PhysicalCloud,
    choose_stride,
    floor_of,
    footprint_radius,
    half_pixel_delta,
    physical_cloud,
    unproject_raw,
    unproject_scaled,
)
from synapse.worldlabs.physical.depth import condition_depth  # noqa: E402
from synapse.worldlabs.physical.level import PhysicalBlocked  # noqa: E402
from synapse.worldlabs.physical.scale import (  # noqa: E402
    ScaleRefused,
    apply_claim,
    asserted_fixture,
    from_camera_height,
    unknown_scale,
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
_LABEL = hd1_scene.LABELS
_PIN = 1e-9          # implementation-correctness pin on exact data, not a SPEC 9 tolerance
# The cross-check bound SPEC 6 and the M2 orders require. It is the same figure as SPEC 9's last
# row, which is D-1's to change: if D-1 changes it, this line changes with it (review R-7).
_SPEC6_CROSS_CHECK = 1e-9

# design.md [M] figures (in-memory re-derivation, 2026-11-14). Printed beside the
# measured value, never asserted: a difference is a finding, not an edit.
_DESIGN_CROSS = {"A": {"pixels": 14196, "max_abs_diff": 0.0}, "C": {"pixels": 14196, "max_abs_diff": 0.0}}
_DESIGN_STRIDE = {"1280x720": {"stride": 2, "points": 229991, "points_before_cap": 919964},
                  "160x90": {"stride": 1, "points": 14196}}
_DESIGN_HALF = {(1280, 720): {"median_depth_m": 3.837454, "delta_at_median_depth_m": 2.713490e-03,
                              "axis_m": 1.918727e-03, "measured_median_m": 2.713490e-03,
                              "measured_max_m": 4.348729e-03},
                (160, 90): {"median_depth_m": 3.874714, "delta_at_median_depth_m": 2.191869e-02,
                            "axis_m": 1.549885e-02, "measured_median_m": 2.191869e-02,
                            "measured_max_m": 3.473416e-02}}
_DESIGN_HALF_FIT = {(1280, 720): {"tilt_deg": 0.025293, "camera_height_error_m": -2.412e-04},
                    (160, 90): {"tilt_deg": 0.202113, "camera_height_error_m": -1.935e-03}}
_DESIGN_FOOTPRINT = {(1280, 720): {"S1": {"depth_m": 3.6117, "radius_mm": 5.42, "lateral_mm": 7.22,
                                          "along_view_mm": 18.28},
                                   "S2": {"depth_m": 3.3539, "radius_mm": 5.03, "lateral_mm": 6.71,
                                          "along_view_mm": 29.75}},
                     (160, 90): {"S1": {"radius_mm": 21.6, "along_view_mm": 71.5},
                                 "S2": {"radius_mm": 20.3, "along_view_mm": 118.0}}}


def _metric(**fields):
    print("HD1-METRIC", json.dumps(fields, sort_keys=True, allow_nan=False))


_CHAIN = {}


def _chain(name, grid, pixel_offset=0.0):
    """(variant, depth mask, raw cloud, floor fit) for one fixture variant, computed once per module."""
    key = (name, tuple(grid), pixel_offset)
    if key not in _CHAIN:
        v = hd1_scene.variant(name, *grid, pixel_offset=pixel_offset)
        mask = condition_depth(v.depth, v.confidence)
        raw = unproject_raw(v.frame, v.depth, mask.keep)
        _CHAIN[key] = (v, mask, raw, floor_of(raw))
    return _CHAIN[key]


_PHYSICAL = {}


def _physical(name, grid):
    """The physical cloud of one variant through the derived camera-height claim, once per module."""
    key = (name, tuple(grid))
    if key not in _PHYSICAL:
        v, mask, _, fit = _chain(name, grid)
        claim = from_camera_height(v.truth.declared_eye_height_m, fit)
        _PHYSICAL[key] = (v, claim, physical_cloud(v.frame, v.depth, mask.keep, claim, fit, colour=v.colour))
    return _PHYSICAL[key]


def _truth_chain(truth, raw_points):
    """SPEC 5's order on raw points, from the truth record alone: scale, then level, then the lift.

    ``s * R(truth.level_xyzw) * p + (0, s * truth.ground_offset_units, 0)``. The unit-quaternion
    matrix is written out here, not taken from ``level.rotation_matrix`` (review RVM-01).
    """
    x, y, z, w = truth.level_xyzw
    m = ((1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
         (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
         (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)))
    s = truth.metres_per_unit
    p = np.asarray(raw_points, dtype=np.float64).reshape(-1, 3) * s
    out = np.column_stack([m[i][0] * p[:, 0] + m[i][1] * p[:, 1] + m[i][2] * p[:, 2] for i in range(3)])
    out[:, 1] += s * truth.ground_offset_units
    return out


def _contract_grid(frame, depth):
    """The contract's unprojection as an (H*W, 3) array in camera-grid order, NaN where it masks."""
    flat = unproject_metric(frame, np.asarray(depth).ravel().tolist())
    out = np.full((len(flat), 3), np.nan)
    for index, point in enumerate(flat):
        if point is not None:
            out[index] = point
    return out


def _cross_check(framed, depth, keep):
    """(pixels both masks call valid, HD1 kept count, max |diff|, exactly equal) at the scaled stage."""
    scaled = unproject_scaled(framed, depth, keep)
    width = framed.intrinsics.width
    contract = _contract_grid(framed, depth)
    contract_valid = ~np.isnan(contract[:, 0])
    flat_index = scaled.rows * width + scaled.cols
    both = contract_valid[flat_index]
    ours = scaled.points_m[both]
    theirs = contract[flat_index[both]]
    difference = float(np.max(np.abs(ours - theirs))) if ours.size else None
    return int(np.count_nonzero(both)), int(scaled.rows.size), difference, bool(np.array_equal(ours, theirs))


# --- design 8.5, tests 1-3: the cross-check -----------------------------------------------

@pytest.mark.parametrize("name", ["A", "C"])
def test_numpy_unprojection_matches_the_contract(name):
    v, mask, _, fit = _chain(name, (160, 90))
    claims = {"asserted:fixture": asserted_fixture(v.truth.metres_per_unit, probe="tests/fixtures/hd1_scene.py#" + name),
              "derived:camera-height": from_camera_height(v.truth.declared_eye_height_m, fit)}
    for method, claim in claims.items():
        framed = apply_claim(v.frame, claim)
        both, kept, difference, exact = _cross_check(framed, v.depth, mask.keep)
        assert both == kept == mask.kept
        assert difference is not None and difference <= _SPEC6_CROSS_CHECK
        _metric(test="cross_check", variant=name, grid=[160, 90], claim=method,
                metres_per_unit=framed.metres_per_unit, pixels_both_valid=both, hd1_kept=kept,
                max_abs_diff_m=difference, exactly_equal=exact, spec_requirement="within 1e-9 (SPEC 6)",
                design_figure_M=_DESIGN_CROSS[name])


def test_cross_check_bottom_up_buffers():
    v, mask, _, _ = _chain("B", (160, 90))
    framed = apply_claim(v.frame, asserted_fixture(1.0, probe="tests/fixtures/hd1_scene.py#B"))
    flipped = replace(framed, decoded_row_order="bottom_up")
    depth_bu, keep_bu = np.ascontiguousarray(v.depth[::-1]), np.ascontiguousarray(mask.keep[::-1])
    top = unproject_scaled(framed, v.depth, mask.keep)
    bottom = unproject_scaled(flipped, depth_bu, keep_bu)
    assert np.array_equal(top.rows, bottom.rows) and np.array_equal(top.cols, bottom.cols)
    assert np.array_equal(top.points_m, bottom.points_m)
    both, kept, difference, exact = _cross_check(flipped, depth_bu, keep_bu)
    assert both == kept and difference <= _PIN
    assert np.array_equal(_contract_grid(flipped, depth_bu), _contract_grid(framed, v.depth), equal_nan=True)
    raw_bottom = unproject_raw(replace(v.frame, decoded_row_order="bottom_up"), depth_bu, keep_bu)
    assert np.array_equal(raw_bottom.rows, top.rows) and raw_bottom.grid == (90, 160)
    _metric(test="cross_check_bottom_up", pixels=both, max_abs_diff_m=difference, exactly_equal=exact)


def test_cross_check_rdf_frames():
    v, mask, _, _ = _chain("B", (160, 90))
    rdf = replace(v.frame, pose=replace(v.frame.pose, coordinate_system="rdf"))
    framed = apply_claim(rdf, asserted_fixture(0.4, probe="synthetic rdf re-labelling of B"))
    both, kept, difference, exact = _cross_check(framed, v.depth, mask.keep)
    assert both == kept == mask.kept and difference <= _PIN
    rub = unproject_scaled(apply_claim(v.frame, asserted_fixture(0.4, probe="B")), v.depth, mask.keep)
    assert not np.allclose(unproject_scaled(framed, v.depth, mask.keep).points_m, rub.points_m)
    _metric(test="cross_check_rdf", pixels=both, max_abs_diff_m=difference, exactly_equal=exact)


def test_cross_check_with_unequal_focal_lengths():
    """Review RVM-03 (2026-11-15): every fixture frame has fx == fy, so a swap of the two passed unseen.

    Variant A at 160x90 re-labelled with fy = 1.1 * fx: a synthetic frame for the cross-check and the
    half-pixel record, not a render of the scene.
    """
    v, mask, _, _ = _chain("A", (160, 90))
    camera = v.frame.intrinsics
    frame = replace(v.frame, intrinsics=replace(camera, fy=1.1 * camera.fx))
    framed = apply_claim(frame, asserted_fixture(1.0, probe="synthetic fy = 1.1 fx re-labelling of A"))
    fx, fy = framed.intrinsics.fx, framed.intrinsics.fy
    assert fy != fx
    both, kept, difference, exact = _cross_check(framed, v.depth, mask.keep)
    assert both == kept == mask.kept and difference <= _PIN
    record = half_pixel_delta(framed, v.depth, mask.keep)
    z_med = record["median_depth_m"]
    closed = 0.5 * z_med * math.hypot(1.0 / fx, 1.0 / fy)
    assert record["fx"] == fx and record["fy"] == fy
    assert record["delta_at_median_depth_axis_m"] == [0.5 * z_med / fx, 0.5 * z_med / fy]
    assert abs(record["measured_delta_m"]["median"] - closed) <= 1e-12 * closed
    _metric(test="cross_check_unequal_focal_lengths", grid=[160, 90], fx=fx, fy=fy, pixels_both_valid=both,
            max_abs_diff_m=difference, exactly_equal=exact,
            half_pixel_axis_m=record["delta_at_median_depth_axis_m"], half_pixel_closed_form_m=closed,
            half_pixel_measured_median_m=record["measured_delta_m"]["median"])


# --- design 8.5, tests 4-7: stages, agreement, stride and footprint -----------------------

@pytest.mark.parametrize("grid", _GRIDS)
def test_scaled_stage_is_neither_levelled_nor_grounded(grid):
    v, mask, _, fit = _chain("B", grid)
    scaled = unproject_scaled(apply_claim(v.frame, asserted_fixture(1.0, probe="B")), v.depth, mask.keep)
    floor_scaled = np.abs(scaled.points_m[v.labels[scaled.rows, scaled.cols] == _LABEL["floor"], 1])
    assert floor_scaled.min() > 1e-6, "B's scaled floor should still be tilted and off y = 0"
    _, _, cloud = _physical("B", grid)
    labels = v.labels[cloud.rows, cloud.cols]
    floor_y = np.abs(cloud.points_m[labels == _LABEL["floor"], 1])
    top_y = np.abs(cloud.points_m[labels == _LABEL["box_top"], 1] - 0.75)
    assert floor_y.size and top_y.size
    assert floor_y.max() <= _PIN and top_y.max() <= _PIN
    _metric(test="stages", variant="B", grid=list(grid),
            scaled_floor_abs_y_m={"min": float(floor_scaled.min()), "max": float(floor_scaled.max())},
            physical_floor_abs_y_max_m=float(floor_y.max()),
            physical_box_top_error_max_m=float(top_y.max()))


def _index(cloud, width):
    return cloud.rows.astype(np.int64) * width + cloud.cols.astype(np.int64)


def test_final_clouds_agree_across_A_C_D():
    grid = (1280, 720)
    _, _, a = _physical("A", grid)
    _, _, c = _physical("C", grid)
    _, _, d = _physical("D", grid)
    assert a.stride == c.stride == d.stride
    assert np.array_equal(a.rows, c.rows) and np.array_equal(a.cols, c.cols)
    c_difference = float(np.max(np.abs(c.points_m - a.points_m)))
    c_radius = float(np.max(np.abs(c.radius_m - a.radius_m)))
    assert c_difference <= 1e-12 and c_radius <= 1e-12
    shared, in_d, in_a = np.intersect1d(_index(d, grid[0]), _index(a, grid[0]), return_indices=True)
    d_difference = float(np.max(np.abs(d.points_m[in_d] - a.points_m[in_a])))
    assert shared.size and d_difference <= 1e-12
    _metric(test="final_agreement", grid=list(grid), c_points=int(c.rows.size), c_max_abs_diff_m=c_difference,
            c_max_radius_diff_m=c_radius, d_points=int(d.rows.size), d_shared_with_a=int(shared.size),
            d_max_abs_diff_m=d_difference, scales={"A": a.scale["value"], "C": c.scale["value"],
                                                   "D": d.scale["value"]})


@pytest.mark.parametrize("name", ["A", "B", "C", "D"])
@pytest.mark.parametrize("grid", _GRIDS)
def test_physical_cloud_matches_the_truth_chain_on_every_axis(name, grid):
    """Review RVM-01 (2026-11-15): x, y and z of the physical cloud against the truth chain on exact hits.

    The A, C and D scene is mirror-symmetric about x = 0, so checks on y alone, or of one variant
    against another, could not see an axis swap or a flipped x.
    """
    v, claim, cloud = _physical(name, grid)
    truth = v.truth
    # The helper is the fixture's own chain: it reproduces every drop site's recorded final position.
    site_error = max(float(np.max(np.abs(_truth_chain(truth, site.surface_raw)[0] - np.array(site.surface_final_m))))
                     for site in truth.sites)
    assert site_error <= 1e-12
    expected = _truth_chain(truth, v.truth_points()[cloud.rows, cloud.cols])
    error = np.abs(cloud.points_m - expected).max(axis=0)
    assert float(error.max()) <= _PIN
    _metric(test="truth_chain", variant=name, grid=list(grid), points=int(cloud.rows.size),
            claim_value=claim.value, truth_metres_per_unit=truth.metres_per_unit,
            max_abs_error_m_xyz=[float(e) for e in error], site_chain_max_abs_diff_m=site_error)


def test_ground_lift_is_applied_after_the_scale():
    """Review RVM-02 (2026-11-15): a scale other than 1 and a ground offset other than 0 in one frame.

    No fixture variant has both, so a lift applied unscaled passed every other test. Variant C's pose
    is lifted by 0.925 units (0.37 m at 0.4 m per unit): the floor rises with it, the fit's floor
    height is the lift, and grounding has to take off s times it, landing on C's unlifted truth chain.
    """
    v, mask, _, _ = _chain("C", (160, 90))
    lift_units = 0.925
    px, py, pz = v.frame.pose.position
    lifted = replace(v.frame, pose=replace(v.frame.pose, position=(px, py + lift_units, pz)))
    fit = floor_of(unproject_raw(lifted, v.depth, mask.keep))
    claim = from_camera_height(v.truth.declared_eye_height_m, fit)
    cloud = physical_cloud(lifted, v.depth, mask.keep, claim, fit)
    s = v.truth.metres_per_unit
    assert fit.status == "SUCCESS" and abs(fit.floor_height - lift_units) <= _PIN
    assert abs(claim.value - s) <= 1e-12 * s
    assert abs(cloud.ground_offset_m + s * lift_units) <= _PIN
    expected = _truth_chain(v.truth, v.truth_points()[cloud.rows, cloud.cols])
    error = np.abs(cloud.points_m - expected).max(axis=0)
    assert float(error.max()) <= _PIN
    labels = v.labels[cloud.rows, cloud.cols]
    floor_y = cloud.points_m[labels == _LABEL["floor"], 1]
    top_y = cloud.points_m[labels == _LABEL["box_top"], 1]
    _metric(test="lift_after_scale", grid=[160, 90], lift_units=lift_units, claim_value=claim.value,
            floor_height_units=fit.floor_height, ground_offset_m=cloud.ground_offset_m,
            truth_ground_offset_m=-s * lift_units, max_abs_error_m_xyz=[float(e) for e in error],
            physical_floor_y_m={"min": float(floor_y.min()), "max": float(floor_y.max()), "truth": 0.0},
            physical_box_top_y_m={"min": float(top_y.min()), "max": float(top_y.max()), "truth": 0.75})


def test_stride_cap():
    v, mask, _, _ = _chain("A", (1280, 720))
    _, _, cloud = _physical("A", (1280, 720))
    keep = mask.keep
    assert POINT_CAP == 250_000
    assert int(np.count_nonzero(keep)) > POINT_CAP >= int(np.count_nonzero(keep[::2, ::2]))
    assert cloud.stride == 2 and cloud.point_cap == POINT_CAP
    assert cloud.points_before_cap == mask.kept
    assert cloud.rows.size == int(np.count_nonzero(keep[::2, ::2])) <= POINT_CAP
    assert cloud.describe()["stride"] == 2 and cloud.describe()["points"] == cloud.rows.size
    _, small_mask, _, _ = _chain("A", (160, 90))
    _, _, small = _physical("A", (160, 90))
    assert small.stride == 1 and small.rows.size == small_mask.kept
    assert choose_stride(np.ones((1000, 1000), dtype=bool)) == 2
    assert int(np.count_nonzero(np.ones((1000, 1000), dtype=bool)[::2, ::2])) == POINT_CAP
    assert choose_stride(np.ones((1001, 1000), dtype=bool)) == 3
    # Not monotone in s: valid only on rows divisible by 3, so s = 3 keeps more than s = 2.
    sparse = np.zeros((120, 120), dtype=bool)
    sparse[::3, :] = True
    counts = {s: int(np.count_nonzero(sparse[::s, ::s])) for s in (1, 2, 3)}
    assert counts[3] > counts[2]
    assert choose_stride(sparse, cap=counts[2]) == 2
    assert choose_stride(sparse, cap=counts[3]) == 2
    assert choose_stride(sparse, cap=counts[2] - 1) > 3
    assert choose_stride(np.zeros((5, 7), dtype=bool), cap=1) == 1
    assert choose_stride(np.ones((5, 7), dtype=bool), cap=1) == 7
    for bad in (0, -1, True, 2.0):
        with pytest.raises(ContractError):
            choose_stride(sparse, cap=bad)
    _metric(test="stride_cap", grid=[1280, 720], stride=cloud.stride, points=int(cloud.rows.size),
            points_before_cap=cloud.points_before_cap, cap=POINT_CAP, small_grid=[160, 90],
            small_stride=small.stride, small_points=int(small.rows.size), sparse_counts=counts,
            design_figure_M=_DESIGN_STRIDE)


@pytest.mark.parametrize("name", ["A", "C"])
def test_footprint_formula(name):
    assert FOOTPRINT_K == 0.75
    for grid in ((1280, 720), (160, 90)):
        v, claim, cloud = _physical(name, grid)
        fx = v.frame.intrinsics.fx
        depth_m = v.depth[cloud.rows, cloud.cols] * claim.value
        assert np.array_equal(cloud.radius_m, depth_m * cloud.stride / fx * FOOTPRINT_K)
        assert np.array_equal(cloud.radius_m, footprint_radius(depth_m, cloud.stride, fx))
        assert cloud.footprint_k == FOOTPRINT_K
    custom = footprint_radius(np.array([2.0, 4.0]), 3, 125.0, k=0.5)
    assert np.array_equal(custom, np.array([2.0, 4.0]) * 3 / 125.0 * 0.5)
    for args in (([0.0], 1, 1.0), ([1.0], 0, 1.0), ([1.0], 1, 0.0), ([np.nan], 1, 1.0), ([1.0], True, 1.0)):
        with pytest.raises(ContractError):
            footprint_radius(*args)
    with pytest.raises(ContractError):
        footprint_radius([1.0], 1, 1.0, k=0.0)


def _site_spacing(cloud, site_m, width):
    """Radius at the cloud point nearest a site, and the distances to its stride neighbours."""
    nearest = int(np.argmin(np.sum((cloud.points_m - np.asarray(site_m)) ** 2, axis=1)))
    row, col = int(cloud.rows[nearest]), int(cloud.cols[nearest])
    lookup = {key: i for i, key in enumerate(_index(cloud, width).tolist())}

    def gap(dr, dc):
        other = lookup.get((row + dr) * width + (col + dc))
        return None if other is None else float(np.linalg.norm(cloud.points_m[other] - cloud.points_m[nearest]))

    s = cloud.stride
    # Both along-view neighbours (review RVM-06 / R-8): one stride up the image (row - stride) and one
    # stride down it (row + stride). Design 6.4 does not say which one its figures used.
    return {"pixel": [row, col], "distance_to_site_m": float(np.linalg.norm(cloud.points_m[nearest] - site_m)),
            "radius_mm": 1000.0 * float(cloud.radius_m[nearest]),
            "disc_diameter_mm": 2000.0 * float(cloud.radius_m[nearest]),
            "lateral_spacing_mm": None if gap(0, s) is None else 1000.0 * gap(0, s),
            "along_view_spacing_mm": {
                "row_minus_stride": None if gap(-s, 0) is None else 1000.0 * gap(-s, 0),
                "row_plus_stride": None if gap(s, 0) is None else 1000.0 * gap(s, 0)}}


@pytest.mark.parametrize("grid", _GRIDS)
def test_footprint_and_spacing_at_the_drop_sites_are_reported(grid):
    """Finding F-2's numbers: the footprint against the point spacing at S1 and S2. Printed, not judged."""
    v, _, cloud = _physical("A", grid)
    sites = {site.name: site for site in v.truth.sites}
    rows = {name: _site_spacing(cloud, np.array(sites[name].surface_final_m), grid[0]) for name in ("S1", "S2")}
    for name, row in rows.items():
        assert row["radius_mm"] > 0.0 and None not in row["along_view_spacing_mm"].values()
    stats = cloud.describe()["radius_m"]
    _metric(test="footprint_at_sites", grid=list(grid), stride=cloud.stride, k=cloud.footprint_k,
            radius_m=stats, sites=rows, design_figure_M=_DESIGN_FOOTPRINT[tuple(grid)])


# --- design 8.5, tests 8-9: the half pixel (BLU-C-HD-01, D-HD-04) --------------------------

@pytest.mark.parametrize("grid", _GRIDS)
def test_half_pixel_difference_is_reported_as_a_number(grid):
    v, mask, _, _ = _chain("A", grid)
    framed = apply_claim(v.frame, asserted_fixture(1.0, probe="tests/fixtures/hd1_scene.py#A"))
    record = half_pixel_delta(framed, v.depth, mask.keep)
    json.dumps(record, allow_nan=False)
    width = grid[0]
    fx = fy = 1000.0 * width / 1280.0
    z_kept = float(np.median(v.depth[mask.keep]))
    closed = 0.5 * z_kept * math.hypot(1.0 / fx, 1.0 / fy)
    measured = record["measured_delta_m"]["median"]
    assert abs(measured - closed) <= 1e-12 * closed
    assert record["median_depth_m"] == pytest.approx(z_kept, rel=1e-15, abs=0.0)
    assert record["delta_at_median_depth_m"] == pytest.approx(closed, rel=1e-12, abs=0.0)
    assert record["resolved"] is False and record["decision"] == "D-HD-04"
    assert record["claim"] == "BLU-C-HD-01" and record["points"] == mask.kept
    assert record["grid"] == [width, grid[1]] and record["fx"] == fx and record["fy"] == fy
    assert record["convention_landed"].startswith("x - cx")
    z_all = float(np.median(v.depth))
    _metric(test="half_pixel", grid=list(grid), record=record, closed_form_m=closed,
            closed_form="0.5 * z_med * hypot(1/fx, 1/fy)", median_depth_kept_m=z_kept,
            measured_minus_closed_m=measured - closed, median_depth_all_pixels_m=z_all,
            closed_form_at_all_pixel_median_m=0.5 * z_all * math.hypot(1.0 / fx, 1.0 / fy),
            design_figure_M=_DESIGN_HALF[tuple(grid)])


@pytest.mark.parametrize("grid", _GRIDS)
def test_half_pixel_render_mismatch_on_the_floor_fit(grid):
    """A frame rendered through pixel centres, read by the unchanged (landed) chain. Prints only."""
    v, _, _, fit = _chain("A", grid, pixel_offset=0.5)
    assert v.truth.pixel_offset == 0.5 and v.frame.frame_id.endswith("-centres")
    assert fit.status == "SUCCESS"
    assert math.isfinite(fit.tilt_deg) and math.isfinite(fit.camera_height)
    _metric(test="half_pixel_floor_fit", grid=list(grid), tilt_deg=fit.tilt_deg,
            camera_height_m=fit.camera_height, camera_height_error_m=fit.camera_height - 1.5,
            floor_height_m=fit.floor_height, inlier_fraction=fit.inlier_fraction,
            design_figure_M=_DESIGN_HALF_FIT[tuple(grid)])


# --- design 8.5, tests 10-12: refusals, the record, colour --------------------------------

def test_physical_cloud_refuses_unknown_scale_and_unknown_floor():
    v, mask, _, fit = _chain("A", (160, 90))
    claim = from_camera_height(1.5, fit)
    with pytest.raises(ScaleRefused):
        physical_cloud(v.frame, v.depth, mask.keep, unknown_scale(), fit)
    for floor in (replace(fit, status="UNKNOWN"), replace(fit, status="BLOCKED"), None, fit.as_dict()):
        with pytest.raises(ContractError, match="^floor is UNKNOWN$"):
            physical_cloud(v.frame, v.depth, mask.keep, claim, floor)
    wall = hd1_scene.no_floor_view()
    wall_mask = condition_depth(wall.depth, wall.confidence)
    wall_fit = floor_of(unproject_raw(wall.frame, wall.depth, wall_mask.keep))
    with pytest.raises(ContractError, match="^floor is UNKNOWN$"):
        physical_cloud(wall.frame, wall.depth, wall_mask.keep, asserted_fixture(1.0, probe="NOFLOOR"), wall_fit)
    scaled = apply_claim(v.frame, claim)
    with pytest.raises(ScaleRefused):
        physical_cloud(scaled, v.depth, mask.keep, claim, fit)
    _, _, _, big_fit = _chain("A", (1280, 720))
    with pytest.raises(ContractError, match="another grid"):
        physical_cloud(v.frame, v.depth, mask.keep, claim, big_fit)


def test_describe_is_json_safe_and_records_the_claim():
    v, claim, cloud = _physical("C", (160, 90))
    record = cloud.describe()
    json.dumps(record, allow_nan=False)
    transform = record["transform"]
    assert transform["scale"] == claim.provenanced_number()
    assert transform["scale_inputs"] == dict(claim.inputs)
    assert transform["applied"] == {"scale": True, "level": True, "ground": True}
    assert transform["order"] == ["scale", "level", "ground"]
    assert transform["level_xyzw"] == list(cloud.level_xyzw)
    assert transform["ground_offset_m"] == cloud.ground_offset_m
    assert record["evidence_tier"] == "SYNTHETIC" and record["frame_id"] == v.frame.frame_id
    assert record["stage"] == "physical" and record["grid"] == [90, 160]
    assert record["points"] == int(cloud.rows.size) and record["colour"] is True
    assert record["bounds_m"]["min"][1] == pytest.approx(0.0, abs=_PIN)
    assert record["bounds_m"]["max"][1] < 1.5
    for array in (cloud.rows, cloud.cols, cloud.points_m, cloud.radius_m, cloud.colour):
        assert not array.flags.writeable
    assert isinstance(cloud, PhysicalCloud)
    _metric(test="describe", record=record)


def test_colour_passes_through():
    v, _, cloud = _physical("A", (160, 90))
    assert cloud.colour.shape == (cloud.rows.size, 3) and cloud.colour.dtype == np.float64
    assert float(cloud.colour.min()) >= 0.0 and float(cloud.colour.max()) <= 1.0
    labels = v.labels[cloud.rows, cloud.cols]
    expected = {_LABEL["floor"]: "floor", _LABEL["box_top"]: "box", _LABEL["box_front"]: "box",
                _LABEL["box_side"]: "box", _LABEL["wall"]: "wall"}
    for label, colour_name in expected.items():
        chosen = labels == label
        if chosen.any():
            want = np.array(hd1_scene.COLOURS[colour_name]) / 255.0
            assert np.array_equal(cloud.colour[chosen], np.broadcast_to(want, (int(chosen.sum()), 3)))
    _, mask, _, fit = _chain("A", (160, 90))
    claim = from_camera_height(1.5, fit)
    as_floats = physical_cloud(v.frame, v.depth, mask.keep, claim, fit, colour=v.colour / 255.0)
    assert np.array_equal(as_floats.colour, cloud.colour)
    # Review RVM-04 (2026-11-15): a bottom_up buffer carries its colour bottom row first as well.
    flipped = replace(v.frame, decoded_row_order="bottom_up")
    bottom = physical_cloud(flipped, v.depth[::-1], mask.keep[::-1], claim, fit, colour=v.colour[::-1])
    assert np.array_equal(bottom.rows, cloud.rows) and np.array_equal(bottom.cols, cloud.cols)
    assert np.array_equal(bottom.points_m, cloud.points_m)
    assert np.array_equal(bottom.colour, cloud.colour)
    assert physical_cloud(v.frame, v.depth, mask.keep, claim, fit).colour is None
    for bad in (v.colour[:, :, :2], v.colour.astype(np.int32), v.colour / 255.0 * 2.0,
                np.full(v.colour.shape, np.nan)):
        with pytest.raises(ContractError):
            physical_cloud(v.frame, v.depth, mask.keep, claim, fit, colour=bad)


# --- additions beyond design 8.5 ----------------------------------------------------------

def test_inputs_are_never_written_and_keep_must_select_valid_depth():
    v, mask, _, _ = _chain("D", (160, 90))
    depth, keep = np.array(v.depth), np.array(mask.keep)
    raw = unproject_raw(v.frame, depth, keep)
    assert np.array_equal(depth, v.depth, equal_nan=True) and np.array_equal(keep, mask.keep)
    assert not raw.points.flags.writeable and not np.shares_memory(raw.depth, depth)
    every = np.ones(depth.shape, dtype=bool)
    with pytest.raises(ContractError, match="^keep selects invalid depth$"):
        unproject_raw(v.frame, depth, every)
    for bad_depth, bad_keep in ((depth[:, :-1], keep), (depth, keep[:, :-1]), (depth, keep.astype(np.uint8)),
                                (depth.astype(bool), keep), (None, keep)):
        with pytest.raises(ContractError):
            unproject_raw(v.frame, bad_depth, bad_keep)
    with pytest.raises(ContractError):
        unproject_raw(None, depth, keep)
    big = np.full(depth.shape, 1e308)
    framed = apply_claim(v.frame, asserted_fixture(1.0, probe="overflow"))
    with pytest.raises(ContractError, match="^non-finite unprojected point$"):
        unproject_scaled(framed, big, every)


def test_numpy_missing_raises_blocked(monkeypatch):
    v, mask, _, fit = _chain("A", (160, 90))
    monkeypatch.setattr(hd1_cloud, "NUMPY_AVAILABLE", False)
    calls = {
        "unproject_raw": lambda: hd1_cloud.unproject_raw(v.frame, v.depth, mask.keep),
        "unproject_scaled": lambda: hd1_cloud.unproject_scaled(v.frame, v.depth, mask.keep),
        "choose_stride": lambda: hd1_cloud.choose_stride(mask.keep),
        "footprint_radius": lambda: hd1_cloud.footprint_radius([1.0], 1, 1.0),
        "physical_cloud": lambda: hd1_cloud.physical_cloud(v.frame, v.depth, mask.keep, unknown_scale(), fit),
        "half_pixel_delta": lambda: hd1_cloud.half_pixel_delta(v.frame, v.depth, mask.keep),
    }
    for name, call in calls.items():
        with pytest.raises(PhysicalBlocked, match="^BLOCKED: "):
            call()
