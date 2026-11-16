"""HD1 analytic fixture (SPEC section 3; design section 8.1). Pure numpy: no hou, no pxr, no network.

The fixture, ``tests/fixtures/hd1_scene.py``, is loaded by file path and never as a
package. Each truth field is checked against something the fixture did not compute:
a closed form, the dormant contract's own pure-Python unprojection, or a rule
re-derived in this file. The design's measured figures ([M]) are never asserted.
They are printed beside the measured value as ``HD1-METRIC`` lines (run with -rP).
Tolerances here are implementation-correctness pins on exact data, not the SPEC
section 9 acceptance tolerances, which belong to D-1.
"""
from __future__ import annotations

import ast
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from unittest.mock import patch

import pytest

np = pytest.importorskip("numpy")

from synapse.worldlabs.atlas_contracts import (  # noqa: E402
    PosedRGBDFrame, SpatialOperation, request_identity, unproject_metric,
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

_GRIDS = (hd1_scene.CHAIN_GRID, hd1_scene.CROSS_GRID)
_GRID_IDS = ["1280x720", "160x90"]
_LABEL = hd1_scene.LABELS
_PIVOT = (0.0, 1.5, 0.0)
_HALF_FLOAT_MAX = 65504.0


# ---------------------------------------------------------------------------
# Helpers, written here so no truth is checked against the code that made it
# ---------------------------------------------------------------------------

def _metric(name, **fields):
    print("HD1-METRIC", json.dumps({"metric": name, **fields}, sort_keys=True, allow_nan=False))


def _rx(degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _rz(degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _quat_matrix(q):
    x, y, z, w = (float(v) for v in q)
    return np.array([
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
        [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
        [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
    ])


def _hamilton(a, b):
    av, aw = np.array(a[:3], dtype=np.float64), float(a[3])
    bv, bw = np.array(b[:3], dtype=np.float64), float(b[3])
    vec = aw * bv + bw * av + np.cross(av, bv)
    return (float(vec[0]), float(vec[1]), float(vec[2]), aw * bw - float(av @ bv))


def _conjugate(q):
    return (-q[0], -q[1], -q[2], q[3])


def _quat_angle_deg(a, b):
    """Angle between two rotations, sign-invariant: 2 atan2(|vec(a b*)|, |w(a b*)|)."""
    x, y, z, w = _hamilton(a, _conjugate(b))
    return math.degrees(2.0 * math.atan2(math.sqrt(x * x + y * y + z * z), abs(w)))


def _level_and_ground(scaled, truth):
    """Level, then ground, on points that are already in metres."""
    shift = np.array([0.0, truth.metres_per_unit * truth.ground_offset_units, 0.0])
    return np.asarray(scaled, dtype=np.float64) @ _quat_matrix(truth.level_xyzw).T + shift


def _chain(raw, truth):
    """The SPEC's order of application: scale, then level, then ground."""
    return _level_and_ground(truth.metres_per_unit * np.asarray(raw, dtype=np.float64), truth)


_CONTRACT = {}


def _contract_points(name, metres_per_unit):
    """The contract's unprojection of a 160x90 variant as an (H, W, 3) array (NaN where masked)."""
    key = (name, metres_per_unit)
    if key not in _CONTRACT:
        v = hd1_scene.variant(name, *hd1_scene.CROSS_GRID)
        flat = unproject_metric(replace(v.frame, metres_per_unit=metres_per_unit), v.depth.ravel().tolist())
        width, height = v.truth.grid
        out = np.full((width * height, 3), np.nan)
        for index, point in enumerate(flat):
            if point is not None:
                out[index] = point
        out.setflags(write=False)
        _CONTRACT[key] = out.reshape(height, width, 3)
    return _CONTRACT[key]


def _edge_flags(depth, rel=0.05):
    """(valid, edge) under the 5% rule of SPEC section 4, re-derived here for the observability count."""
    z = np.asarray(depth, dtype=np.float64)
    with np.errstate(invalid="ignore"):
        valid = np.isfinite(z) & (z > 0.0) & (z <= _HALF_FLOAT_MAX)
        edge = np.zeros(z.shape, dtype=bool)
        pair = valid[:-1, :] & valid[1:, :] & (np.abs(z[:-1, :] - z[1:, :]) > rel * np.minimum(z[:-1, :], z[1:, :]))
        edge[:-1, :] |= pair
        edge[1:, :] |= pair
        pair = valid[:, :-1] & valid[:, 1:] & (np.abs(z[:, :-1] - z[:, 1:]) > rel * np.minimum(z[:, :-1], z[:, 1:]))
        edge[:, :-1] |= pair
        edge[:, 1:] |= pair
    return valid, edge


def _farthest_neighbour(z):
    padded = np.pad(np.asarray(z, dtype=np.float64), 1, constant_values=-np.inf)
    return np.maximum.reduce([padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]])


def _discontinuities(z, rel):
    padded = np.pad(np.asarray(z, dtype=np.float64), 1, constant_values=np.nan)
    centre = padded[1:-1, 1:-1]
    out = np.zeros(centre.shape, dtype=bool)
    with np.errstate(invalid="ignore"):
        for neighbour in (padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]):
            out |= np.abs(centre - neighbour) > rel * np.minimum(centre, neighbour)
    return out


def _chebyshev_band(mask, radius):
    padded = np.pad(mask, radius, constant_values=False)
    rows, cols = mask.shape
    out = np.zeros(mask.shape, dtype=bool)
    for dy in range(2 * radius + 1):
        for dx in range(2 * radius + 1):
            out |= padded[dy:dy + rows, dx:dx + cols]
    return out


def _rect(shape, rows, cols, width):
    def scaled(value):
        return (value * width) // 1280
    mask = np.zeros(shape, dtype=bool)
    mask[scaled(rows[0]):scaled(rows[1]), scaled(cols[0]):scaled(cols[1])] = True
    return mask


def _same(a, b):
    if np.issubdtype(np.asarray(a).dtype, np.floating):
        return bool(np.array_equal(a, b, equal_nan=True))
    return bool(np.array_equal(a, b))


def _span(mask, axis):
    hits = np.nonzero(mask.any(axis=axis))[0]
    return [int(hits[0]), int(hits[-1])] if hits.size else None


# ---------------------------------------------------------------------------
# 1. Frames
# ---------------------------------------------------------------------------

_FRAME_CASES = [(name, grid) for grid in _GRIDS for name in hd1_scene.VARIANTS]
_FRAME_CASES.append((hd1_scene.NOFLOOR, hd1_scene.CROSS_GRID))


@pytest.mark.parametrize("name,grid", _FRAME_CASES,
                         ids=["%s-%dx%d" % (name, grid[0], grid[1]) for name, grid in _FRAME_CASES])
def test_frames_pass_the_dormant_contract(name, grid):
    v = hd1_scene.variant(name, *grid)
    frame, (width, height) = v.frame, grid
    assert isinstance(frame, PosedRGBDFrame)
    assert v.name == v.truth.variant == name and v.truth.grid == (width, height)
    identities = (frame.frame_id, frame.image.asset_id, frame.depth.asset_id, frame.confidence.asset_id,
                  frame.pose.world_frame)
    assert all(identity.startswith("SYNTHETIC-") for identity in identities), identities
    assert [ref.evidence_tier for ref in (frame.image, frame.depth, frame.confidence)] == ["SYNTHETIC"] * 3
    assert (frame.image.media_type, frame.depth.media_type, frame.confidence.media_type) == (
        "image/png", "image/x-exr", "image/png")
    assert frame.metres_per_unit is None
    assert (frame.depth_encoding, frame.decoded_row_order, frame.pose.coordinate_system) == (
        "linear_exr_half", "top_down", "rub")
    # The digests name the decoded arrays the fixture returns, not files.
    assert frame.image.content_sha256 == hd1_scene.array_sha256(v.colour)
    assert frame.depth.content_sha256 == hd1_scene.array_sha256(v.depth)
    assert frame.confidence.content_sha256 == hd1_scene.array_sha256(v.confidence)
    # The declared pinhole: fx = fy = 1000 * W / 1280, principal point at the centre.
    cam = frame.intrinsics
    assert (cam.width, cam.height) == (width, height)
    assert cam.fx == cam.fy == 1000.0 * width / 1280.0
    assert (cam.cx, cam.cy) == (width / 2.0, height / 2.0)
    assert v.depth.shape == (height, width) and v.depth.dtype == np.float64
    assert v.confidence.shape == (height, width) and v.confidence.dtype == np.float64
    assert np.all((v.confidence >= 0.0) & (v.confidence <= 1.0))
    assert v.colour.shape == (height, width, 3) and v.colour.dtype == np.uint8
    assert v.labels.shape == (height, width) and v.labels.dtype == np.int8
    # replace() re-runs the contract's validation; an operation accepts the frame.
    assert replace(frame) == frame
    operation = SpatialOperation("SYNTHETIC-hd1-op-" + name, "SUCCEEDED",
                                 request_identity(((frame.frame_id, frame.image),)), (frame,))
    assert operation.frames == (frame,)
    if grid == hd1_scene.CROSS_GRID:
        points = unproject_metric(replace(frame, metres_per_unit=v.truth.metres_per_unit), v.depth.ravel().tolist())
        assert len(points) == width * height
        # The contract masks only the NaN patch; it keeps D's 1e5 patch (HD-05).
        masked = sum(point is None for point in points)
        assert masked == (int(v.truth.corruption["nan"].sum()) if v.truth.corruption else 0)


# ---------------------------------------------------------------------------
# 2. Depth is planar z
# ---------------------------------------------------------------------------

def test_depth_is_planar_z_not_ray_length():
    v = hd1_scene.variant("A", *hd1_scene.CROSS_GRID)
    points = _contract_points("A", 1.0)
    labels, tol = v.labels, 1e-9
    assert set(np.unique(labels).tolist()) <= set(_LABEL.values())
    floor = points[labels == _LABEL["floor"]]
    top = points[labels == _LABEL["box_top"]]
    front = points[labels == _LABEL["box_front"]]
    wall = points[labels == _LABEL["wall"]]
    floor_err = float(np.max(np.abs(floor[:, 1])))
    top_err = float(np.max(np.abs(top[:, 1] - 0.75)))
    front_err = float(np.max(np.abs(front[:, 2] + 2.8)))
    wall_err = float(np.max(np.abs(wall[:, 2] + 6.0)))
    assert max(floor_err, top_err, front_err, wall_err) <= tol
    assert np.all((top[:, 0] >= -0.5 - tol) & (top[:, 0] <= 0.5 + tol))
    assert np.all((top[:, 2] >= -3.8 - tol) & (top[:, 2] <= -2.8 + tol))
    assert np.all((front[:, 0] >= -0.5 - tol) & (front[:, 0] <= 0.5 + tol))
    assert np.all((front[:, 1] >= -tol) & (front[:, 1] <= 0.75 + tol))
    # Depth is the distance along the optical axis, not along the ray.
    centre = np.array(v.frame.pose.position)
    forward = np.array([0.0, math.sin(math.radians(-20.0)), -math.cos(math.radians(-20.0))])
    planar_err = float(np.max(np.abs((points - centre) @ forward - v.depth)))
    assert planar_err <= tol
    ray_gap = float(np.max(np.abs(np.linalg.norm(points - centre, axis=-1) - v.depth)))
    cam = v.frame.intrinsics
    u, w = (0 - cam.cx) / cam.fx, (0 - cam.cy) / cam.fy
    ratio = float(v.depth[0, 0] / np.linalg.norm(points[0, 0] - centre))
    assert ratio == pytest.approx(1.0 / math.sqrt(1.0 + u * u + w * w), rel=0, abs=1e-12)
    # truth_points() are the same hits as the contract's unprojection.
    truth_err = float(np.max(np.abs(v.truth_points() - points)))
    assert truth_err <= tol
    _metric("planar_depth", grid=[160, 90], floor_abs_y_max=floor_err, box_top_abs_dy_max=top_err,
            box_front_abs_dz_max=front_err, wall_abs_dz_max=wall_err, planar_err_max_m=planar_err,
            ray_length_minus_depth_max_m=ray_gap, pixel00_ratio=ratio, truth_points_vs_contract_max=truth_err,
            design={"planar_err_max_m": 8.9e-16, "ray_length_minus_depth_max_m": 1.3585,
                    "floor_abs_y_max": 2.2e-16, "wall_abs_dz_max": 8.9e-16})


# ---------------------------------------------------------------------------
# 3. Layout
# ---------------------------------------------------------------------------

_DESIGN_LAYOUT = {
    (1280, 720): {"floor": 511476, "floor_rows": [256, 719], "box": 97393, "box_top": 20656, "box_front": 76737,
                  "box_side": 0, "box_rows": [205, 503], "box_cols": [467, 813], "wall": 312731,
                  "wall_rows": [0, 255], "depth_min": 2.2079, "depth_max": 6.1500, "depth_median": 3.828251},
    (160, 90): {"floor": 7991, "floor_rows": [32, 89], "box": 1507, "box_top": 343, "box_front": 1164,
                "box_side": 0, "box_rows": [26, 62], "box_cols": [59, 101], "wall": 4902,
                "wall_rows": [0, 31], "depth_min": 2.2295, "depth_max": 6.1402, "depth_median": 3.874714},
}


@pytest.mark.parametrize("grid", _GRIDS, ids=_GRID_IDS)
def test_box_floor_and_wall_are_in_view_and_the_bottom_quarter_is_floor(grid):
    v = hd1_scene.variant("A", *grid)
    width, height = grid
    counts = {key: int((v.labels == value).sum()) for key, value in _LABEL.items()}
    assert all(counts[key] > 0 for key in ("floor", "box_top", "box_front", "wall")), counts
    assert sum(counts.values()) == width * height
    box = np.isin(v.labels, (_LABEL["box_top"], _LABEL["box_front"], _LABEL["box_side"]))
    assert not (box[0].any() or box[-1].any() or box[:, 0].any() or box[:, -1].any())
    first_row = (3 * height) // 4
    assert np.all(v.labels[first_row:] == _LABEL["floor"])
    assert np.all(np.isfinite(v.depth)) and np.all(v.depth > 0.0) and np.all(v.depth <= _HALF_FLOAT_MAX)
    # Every ray descends: no sky. Elevation of the top row's rays, from the pose.
    cam, rotation = v.frame.intrinsics, _quat_matrix(v.frame.pose.quaternion_xyzw)
    xs = np.arange(width, dtype=np.float64)
    rays = np.stack([(xs - cam.cx) / cam.fx, np.full(width, cam.cy / cam.fy), np.full(width, -1.0)], axis=-1)
    world = rays @ rotation.T
    below = np.degrees(np.arctan2(-world[:, 1], np.hypot(world[:, 0], world[:, 2])))
    assert np.all(below > 0.0)
    floor = v.labels == _LABEL["floor"]
    wall = v.labels == _LABEL["wall"]
    _metric("layout", grid=list(grid), first_floor_row=first_row,
            measured={"floor": counts["floor"], "floor_rows": _span(floor, 1), "box": int(box.sum()),
                      "box_top": counts["box_top"], "box_front": counts["box_front"],
                      "box_side": counts["box_side"], "box_rows": _span(box, 1), "box_cols": _span(box, 0),
                      "wall": counts["wall"], "wall_rows": _span(wall, 1), "depth_min": float(v.depth.min()),
                      "depth_max": float(v.depth.max()), "depth_median": float(np.median(v.depth)),
                      "top_row_centre_below_horizon_deg": float(below[width // 2]),
                      "top_row_min_below_horizon_deg": float(below.min()),
                      "hfov_deg": math.degrees(2.0 * math.atan(cam.cx / cam.fx)),
                      "vfov_deg": math.degrees(2.0 * math.atan(cam.cy / cam.fy))},
            design=dict(_DESIGN_LAYOUT[tuple(grid)], top_row_below_horizon_deg=0.201,
                        hfov_deg=65.238, vfov_deg=39.598))


# ---------------------------------------------------------------------------
# 4. Truth levelling records
# ---------------------------------------------------------------------------

def test_truth_levelling_records_are_self_consistent():
    up = np.array([0.0, 1.0, 0.0])
    cos_tilt = math.cos(math.radians(3.0)) * math.cos(math.radians(5.0))
    for name in hd1_scene.VARIANTS + (hd1_scene.NOFLOOR,):
        v = hd1_scene.variant(name, *hd1_scene.CROSS_GRID)
        t = v.truth
        normal = np.array(t.floor_normal)
        for q in (t.level_xyzw, t.world_tilt_xyzw, v.frame.pose.quaternion_xyzw):
            assert abs(sum(c * c for c in q) - 1.0) <= 1e-12
        assert abs(float(np.linalg.norm(normal)) - 1.0) <= 1e-12
        assert float(np.max(np.abs(_quat_matrix(t.level_xyzw) @ normal - up))) <= 1e-12
        assert t.level_xyzw[1] == 0.0                       # the smallest rotation carries no yaw
        assert t.ground_offset_units == -t.floor_height_units
        # The camera's signed height above n.p + d = 0, with d = -floor_height.
        position = np.array(v.frame.pose.position)
        assert float(normal @ position) - t.floor_height_units == pytest.approx(t.camera_height_units, abs=1e-12)
        assert t.metres_per_unit == (0.4 if name == "C" else 1.0)
        assert t.camera_height_units == pytest.approx(1.5 / t.metres_per_unit, abs=1e-12)
        assert t.declared_eye_height_m == 1.5
        _metric("truth_record", variant=name, record=t.as_dict())
        if name != "B":
            assert t.floor_normal == (0.0, 1.0, 0.0)
            assert t.level_xyzw == t.world_tilt_xyzw == (0.0, 0.0, 0.0, 1.0)
            assert t.world_tilt_pivot is None and t.tilt_deg == 0.0 and t.yaw_twist_deg == 0.0
            assert t.floor_height_units == 0.0 == t.ground_offset_units
            assert math.copysign(1.0, t.floor_height_units) == math.copysign(1.0, t.ground_offset_units) == 1.0
            continue
        # B, against closed forms built here: W = Rz(3 deg) Rx(5 deg), about the camera centre (C-2).
        tilt_matrix = _rz(3.0) @ _rx(5.0)
        closed_normal = np.array([-math.sin(math.radians(3.0)) * math.cos(math.radians(5.0)), cos_tilt,
                                  math.sin(math.radians(5.0))])
        assert float(np.max(np.abs(normal - tilt_matrix @ up))) <= 1e-12
        assert float(np.max(np.abs(normal - closed_normal))) <= 1e-12
        assert float(np.max(np.abs(_quat_matrix(t.world_tilt_xyzw) - tilt_matrix))) <= 1e-12
        assert t.world_tilt_pivot == _PIVOT == v.frame.pose.position
        assert t.tilt_deg == pytest.approx(math.degrees(math.acos(cos_tilt)), rel=0, abs=1e-12)
        assert t.floor_height_units == pytest.approx(-1.5 * (1.0 - cos_tilt), rel=0, abs=1e-15)
        half_angle = np.array([-normal[2], 0.0, normal[0], 1.0 + normal[1]])
        half_angle = tuple(float(c) for c in half_angle / np.linalg.norm(half_angle))
        level_vs_half_angle = _quat_angle_deg(t.level_xyzw, half_angle)
        assert level_vs_half_angle <= 1e-12
        twist = _hamilton(t.level_xyzw, t.world_tilt_xyzw)
        assert abs(twist[0]) <= 1e-12 and abs(twist[2]) <= 1e-12   # level (x) q_W is a pure yaw
        assert t.yaw_twist_deg == pytest.approx(_quat_angle_deg(t.level_xyzw, _conjugate(t.world_tilt_xyzw)),
                                                rel=0, abs=1e-12)
        assert t.yaw_twist_deg > 0.0
        _metric("truth_B", measured={"q_W": list(t.world_tilt_xyzw), "q_B": list(v.frame.pose.quaternion_xyzw),
                                     "q_B_norm_minus_1": sum(c * c for c in v.frame.pose.quaternion_xyzw) - 1.0,
                                     "floor_normal": list(t.floor_normal), "tilt_deg": t.tilt_deg,
                                     "level_xyzw": list(t.level_xyzw), "yaw_twist_deg": t.yaw_twist_deg,
                                     "floor_height_units": t.floor_height_units,
                                     "ground_offset_units": t.ground_offset_units,
                                     "camera_height_units": t.camera_height_units,
                                     "level_vs_half_angle_form_deg": level_vs_half_angle},
                closed_form={"tilt_deg": math.degrees(math.acos(cos_tilt)),
                             "floor_height_units": -1.5 * (1.0 - cos_tilt)},
                design={"q_W": [0.043604440090704404, 0.0011418224482834958, 0.026152033653420895,
                                0.9987058727081077],
                        "q_B": [-0.13048146415394216, -0.0034167773865678053, 0.0259530008862887,
                                0.9911051179817055],
                        "floor_normal": [-0.052136802128782245, 0.994829447880333, 0.08715574274765817],
                        "tilt_deg": 5.828991157608576,
                        "level_xyzw": [-0.04363431124572399, 0.0, -0.02610216354911549, 0.998706525431854],
                        "yaw_twist_deg": 0.13101270458640024, "floor_height_units": -0.00775582817950049})


# ---------------------------------------------------------------------------
# 5. Re-expressions of A
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("grid", _GRIDS, ids=_GRID_IDS)
def test_variants_are_exact_re_expressions_of_A(grid):
    a, b, c, d = (hd1_scene.variant(name, *grid) for name in hd1_scene.VARIANTS)
    # A's camera: Rx(-20 deg) as XYZW, with literal (not negative) zeros.
    q = a.frame.pose.quaternion_xyzw
    assert q == pytest.approx((math.sin(math.radians(-10.0)), 0.0, 0.0, math.cos(math.radians(-10.0))),
                              rel=0, abs=1e-15)
    assert math.copysign(1.0, q[1]) == math.copysign(1.0, q[2]) == 1.0
    assert a.frame.pose.position == (0.0, 1.5, 0.0)
    # B: the same image in a tilted world. The camera stays at the pivot; its rotation is W after A's.
    for field in ("depth", "confidence", "colour", "labels"):
        assert _same(getattr(b, field), getattr(a, field)), field
    assert b.frame.pose.position == a.frame.pose.position
    tilt_matrix = _rz(3.0) @ _rx(5.0)
    rotation_err = float(np.max(np.abs(_quat_matrix(b.frame.pose.quaternion_xyzw)
                                       - tilt_matrix @ _quat_matrix(q))))
    assert rotation_err <= 1e-12
    # C: the same scene written at 0.4 m per unit.
    assert np.array_equal(c.depth, a.depth / 0.4)
    assert c.frame.pose.position == tuple(p / 0.4 for p in a.frame.pose.position)
    assert c.frame.pose.quaternion_xyzw == q
    for field in ("confidence", "colour", "labels"):
        assert _same(getattr(c, field), getattr(a, field)), field
    # D: A everywhere outside its corruption masks.
    masks = d.truth.corruption
    touched = masks["nan"] | masks["above_half_max"] | masks["mixed"]
    assert np.array_equal(d.depth[~touched], a.depth[~touched])
    assert np.array_equal(d.confidence[~masks["low_confidence"]], a.confidence[~masks["low_confidence"]])
    assert _same(d.colour, a.colour) and _same(d.labels, a.labels)
    assert (d.frame.pose.position, d.frame.pose.quaternion_xyzw) == (a.frame.pose.position, q)
    assert d.frame.intrinsics == a.frame.intrinsics
    measured = {"B_rotation_vs_W_qA_max": rotation_err}
    if grid == hd1_scene.CROSS_GRID:
        pa, pb, pc = _contract_points("A", 1.0), _contract_points("B", 1.0), _contract_points("C", 0.4)
        pivot = np.array(_PIVOT)
        b_err = float(np.max(np.abs(pb - ((pa - pivot) @ tilt_matrix.T + pivot))))
        c_err = float(np.max(np.abs(pc - pa)))
        assert b_err <= 1e-12 and c_err <= 1e-12
        # truth_points() of B and C are the contract's hits too; D's are the clean scene's, i.e. A's.
        b_truth_err = float(np.max(np.abs(b.truth_points() - pb)))
        c_truth_err = float(np.max(np.abs(c.truth_points() * 0.4 - pc)))
        assert b_truth_err <= 1e-9 and c_truth_err <= 1e-9
        assert np.array_equal(d.truth_points(), a.truth_points())
        measured.update(contract_B_vs_W_A_minus_c_plus_c_max_m=b_err, contract_C_at_0p4_vs_A_max_m=c_err,
                        truth_points_B_vs_contract_max_m=b_truth_err,
                        truth_points_C_times_0p4_vs_contract_max_m=c_truth_err)
    _metric("re_expressions", grid=list(grid), measured=measured,
            design={"contract_B_vs_W_A_minus_c_plus_c_max_m": 1.8e-15, "contract_C_at_0p4_vs_A_max_m": 8.9e-16})


@pytest.mark.parametrize("name", hd1_scene.VARIANTS)
def test_truth_chain_puts_contract_points_on_the_floor_and_the_box_top(name):
    """The contract's (scaled) points, levelled and grounded with the truth record, land at y = 0 and 0.75.

    This is the check a wrong sign in floor_height or ground_offset cannot pass (why C-2 pivots at the camera).
    """
    v = hd1_scene.variant(name, *hd1_scene.CROSS_GRID)
    t = v.truth
    scaled = _contract_points(name, t.metres_per_unit)
    final = _level_and_ground(scaled.reshape(-1, 3), t).reshape(scaled.shape)
    clean = np.ones(v.labels.shape, dtype=bool)
    if t.corruption is not None:
        clean = ~(t.corruption["nan"] | t.corruption["above_half_max"] | t.corruption["mixed"])
    floor = clean & (v.labels == _LABEL["floor"])
    top = clean & (v.labels == _LABEL["box_top"])
    floor_err = float(np.max(np.abs(final[floor][:, 1])))
    top_err = float(np.max(np.abs(final[top][:, 1] - 0.75)))
    assert floor_err <= 1e-9 and top_err <= 1e-9
    raw_floor_y = np.abs(scaled[floor][:, 1])
    if name == "B":
        assert float(raw_floor_y.max()) > 1e-3     # before levelling, B's floor is not at y = 0
    _metric("truth_chain_on_contract_points", variant=name, grid=[160, 90], floor_abs_y_max_m=floor_err,
            box_top_abs_dy_max_m=top_err, raw_floor_abs_y_min_m=float(raw_floor_y.min()),
            raw_floor_abs_y_max_m=float(raw_floor_y.max()))


# ---------------------------------------------------------------------------
# 6. Sites
# ---------------------------------------------------------------------------

_DESIGN_SITES = {   # design section 2.8, [M]: surface [release]
    "B": {"S1": {"raw": [-1.235065743, 0.226938871, -3.418176118],
                 "release_raw": [-1.261134144, 0.724353595, -3.374598246],
                 "final": [-1.229337182, 0.0, -3.427752406]},
          "S2": {"raw": [0.02405005, 1.0410977, -3.352809311],
                 "release_raw": [-0.002018351, 1.538512424, -3.309231439],
                 "final": [0.07065942, 0.75, -3.430724987]},
          "S3": {"raw": [0.057222859, 0.408122803, -4.713229225],
                 "release_raw": [0.031154458, 0.905537527, -4.669651354],
                 "final": [0.067686838, 0.0, -4.730721588]}},
    "C": {"S1": {"raw": [-3.25, 0.0, -8.25], "release_raw": [-3.25, 1.25, -8.25]},
          "S2": {"raw": [0.0, 1.875, -8.25], "release_raw": [0.0, 3.125, -8.25]},
          "S3": {"raw": [0.0, 0.0, -11.5], "release_raw": [0.0, 1.25, -11.5]}},
}


@pytest.mark.parametrize("name", hd1_scene.VARIANTS)
def test_sites_rest_heights_and_release_points(name):
    truth_a = hd1_scene.variant("A", *hd1_scene.CROSS_GRID).truth
    t = hd1_scene.variant(name, *hd1_scene.CROSS_GRID).truth
    s, normal, d = t.metres_per_unit, np.array(t.floor_normal), -t.floor_height_units
    assert [site.name for site in t.sites] == ["S1", "S2", "S3"]
    assert [site.where for site in t.sites] == [
        "open floor in view", "top of the box", "floor behind the box, never observed"]
    assert [site.expect for site in t.sites] == ["rest", "rest", "fall_through"]
    heights = {"S1": 0.0, "S2": 0.75, "S3": 0.0}     # SPEC 3: floor at y = 0, box 0.75 high
    lift = np.array([0.0, 0.5, 0.0])
    for site in t.sites:
        h = heights[site.name]
        assert site.sphere_radius_m == 0.1
        assert float(normal @ np.array(site.surface_raw)) + d == pytest.approx(h / s, rel=0, abs=1e-12)
        assert float(np.max(np.abs(_chain(site.surface_raw, t) - site.surface_final_m))) <= 1e-12
        assert float(np.max(np.abs(_chain(site.release_raw, t) - site.release_final_m))) <= 1e-12
        assert float(np.max(np.abs(np.subtract(site.release_final_m, site.surface_final_m) - lift))) <= 1e-12
        # "Above" is the final +Y, which is the floor normal in the raw frame.
        release_step = np.subtract(site.release_raw, site.surface_raw)
        assert float(np.max(np.abs(release_step - (0.5 / s) * normal))) <= 1e-12
        assert site.surface_final_m[1] == pytest.approx(h, rel=0, abs=1e-12)
        if site.expect == "rest":
            assert site.rest_height_m == pytest.approx(h + 0.1, rel=0, abs=1e-12)
        else:
            assert site.rest_height_m is None
    assert [site.rest_height_m for site in t.sites] == [pytest.approx(0.10), pytest.approx(0.85), None]  # SPEC 7
    # Every variant is the same capture: the sites keep their mutual distances.
    finals = np.array([site.surface_final_m for site in t.sites])
    finals_a = np.array([site.surface_final_m for site in truth_a.sites])
    gaps = np.linalg.norm(finals[:, None] - finals[None, :], axis=-1)
    gaps_a = np.linalg.norm(finals_a[:, None] - finals_a[None, :], axis=-1)
    assert float(np.max(np.abs(gaps - gaps_a))) <= 1e-12
    if name != "B":
        assert float(np.max(np.abs(finals - finals_a))) <= 1e-12
    if name == "A":
        s1, s2, s3 = finals
        assert -0.5 <= s2[0] <= 0.5 and -3.8 <= s2[2] <= -2.8          # S2 on the box top
        assert not (-0.5 <= s1[0] <= 0.5 and -3.8 <= s1[2] <= -2.8)    # S1 on open floor
        assert s3[2] < -3.8 and abs(s3[0]) <= 0.5                       # S3 behind the box
    # The reference pair: the box's top-front corners, 1.0 m apart and 0.75 m up.
    pair_a, pair_b, known = t.reference_pair
    assert known == 1.0
    assert float(np.linalg.norm(np.subtract(pair_b, pair_a))) * s == pytest.approx(known, rel=0, abs=1e-12)
    assert float(np.max(np.abs(_chain(np.array([pair_a, pair_b]), t)[:, 1] - 0.75))) <= 1e-12
    _metric("sites", variant=name, measured=[site.as_dict() for site in t.sites],
            reference_pair=[list(pair_a), list(pair_b), known], design=_DESIGN_SITES.get(name))


# ---------------------------------------------------------------------------
# 7. Observability
# ---------------------------------------------------------------------------

_DESIGN_OBSERVABILITY = {
    (1280, 720): {"nearest_kept_to_S3_m": 0.8164, "S1_within_0p1": 1000, "S2_within_0p1": 625, "S3_within_0p25": 0,
                  "kept": 919964, "edge_dropped": 1636},
    (160, 90): {"nearest_kept_to_S3_m": 0.8767, "S1_within_0p1": 16, "S2_within_0p1": 10, "S3_within_0p25": 0,
                "kept": 14196, "edge_dropped": 204},
}


@pytest.mark.parametrize("grid", _GRIDS, ids=_GRID_IDS)
def test_s3_is_never_observed_and_s1_s2_are(grid):
    v = hd1_scene.variant("A", *grid)
    valid, edge = _edge_flags(v.depth)
    kept = valid & ~edge
    every = v.truth_points().reshape(-1, 3)
    points = every[kept.ravel()]
    sites = {site.name: np.array(site.surface_final_m) for site in v.truth.sites}
    distance = {key: np.linalg.norm(points - p, axis=1) for key, p in sites.items()}
    within = {"S1_within_0p1": int((distance["S1"] <= 0.1).sum()),
              "S2_within_0p1": int((distance["S2"] <= 0.1).sum()),
              "S3_within_0p25": int((distance["S3"] <= 0.25).sum())}
    assert within["S3_within_0p25"] == 0
    assert within["S1_within_0p1"] >= 1 and within["S2_within_0p1"] >= 1
    nearest_any = float(np.min(np.linalg.norm(every - sites["S3"], axis=1)))
    assert nearest_any > 0.25            # hidden before any conditioning, too
    by_label = {key: int((edge & (v.labels == value)).sum()) for key, value in _LABEL.items()}
    _metric("observability", grid=list(grid),
            measured=dict(within, nearest_kept_to_S3_m=float(distance["S3"].min()),
                          nearest_any_pixel_to_S3_m=nearest_any, kept=int(kept.sum()),
                          edge_dropped=int(edge.sum()), edge_dropped_by_label=by_label),
            design=_DESIGN_OBSERVABILITY[tuple(grid)])


# ---------------------------------------------------------------------------
# 8. Variant D
# ---------------------------------------------------------------------------

_DESIGN_D = {
    (1280, 720): {"nan": 1024, "above_half_max": 1024, "mixed": 779, "low_confidence": 5144,
                  "mixed_flagged_by_5pct_edge_rule": 779},
    (160, 90): {"nan": 16, "above_half_max": 16, "mixed": 97, "low_confidence": 664,
                "mixed_flagged_by_5pct_edge_rule": 97},
}


@pytest.mark.parametrize("grid", _GRIDS, ids=_GRID_IDS)
def test_variant_D_corruptions_match_their_masks(grid):
    a, d = hd1_scene.variant("A", *grid), hd1_scene.variant("D", *grid)
    width, height = grid
    masks = d.truth.corruption
    assert set(masks) == {"nan", "above_half_max", "mixed", "low_confidence"}
    for mask in masks.values():
        assert mask.shape == (height, width) and mask.dtype == bool and not mask.flags.writeable
    # The two patches: their declared 1280x720 bounds, scaled by width / 1280.
    assert np.array_equal(masks["nan"], _rect((height, width), (600, 632), (1000, 1032), width))
    assert np.array_equal(masks["above_half_max"], _rect((height, width), (600, 632), (200, 232), width))
    assert np.array_equal(np.isnan(d.depth), masks["nan"])
    assert np.array_equal(d.depth == 1.0e5, masks["above_half_max"])
    with np.errstate(invalid="ignore"):
        assert np.array_equal(d.depth > _HALF_FLOAT_MAX, masks["above_half_max"])
    # Mixed depths, re-derived from clean A: a jump of more than 10% to a farther neighbour -> the midpoint.
    z = a.depth
    far = _farthest_neighbour(z)
    assert np.array_equal(masks["mixed"], (far - z) > 0.10 * z)
    assert np.array_equal(d.depth[masks["mixed"]], ((z + far) / 2.0)[masks["mixed"]])
    # Low confidence: depth edges of clean A, widened to Chebyshev distance 2.
    band = _chebyshev_band(_discontinuities(z, 0.10), 2)
    assert np.array_equal(masks["low_confidence"], band)
    assert np.array_equal(d.confidence, np.where(band, 0.2, 1.0))
    # Patches sit on open floor in the bottom quarter, clear of each other and of the silhouette band.
    patches = masks["nan"] | masks["above_half_max"]
    assert not (masks["nan"] & masks["above_half_max"]).any()
    assert not (patches & (masks["low_confidence"] | masks["mixed"])).any()
    assert np.all(a.labels[patches] == _LABEL["floor"])
    assert np.all(np.nonzero(patches)[0] >= (3 * height) // 4)
    assert not (masks["mixed"] & ~masks["low_confidence"]).any()   # every mixed pixel is inside the band
    _, edge = _edge_flags(d.depth)
    _metric("variant_D", grid=list(grid),
            measured={"nan": int(masks["nan"].sum()), "above_half_max": int(masks["above_half_max"].sum()),
                      "mixed": int(masks["mixed"].sum()), "low_confidence": int(masks["low_confidence"].sum()),
                      "mixed_flagged_by_5pct_edge_rule": int((masks["mixed"] & edge).sum())},
            design=_DESIGN_D[tuple(grid)])


# ---------------------------------------------------------------------------
# 9. Determinism and read-only arrays
# ---------------------------------------------------------------------------

_HEX64 = re.compile(r"[0-9a-f]{64}")


def test_fixture_is_deterministic_and_read_only():
    receipts = {}
    for grid in _GRIDS:
        names = hd1_scene.VARIANTS + ((hd1_scene.NOFLOOR,) if grid == hd1_scene.CROSS_GRID else ())
        for name in names:
            first = hd1_scene.variant.__wrapped__(name, *grid)
            second = hd1_scene.variant.__wrapped__(name, *grid)
            cached = hd1_scene.variant(name, *grid)
            assert hd1_scene.variant(name, *grid) is cached
            for field in ("depth", "confidence", "colour", "labels"):
                assert _same(getattr(first, field), getattr(second, field)), (name, field)
                assert _same(getattr(first, field), getattr(cached, field)), (name, field)
                for v in (first, second, cached):
                    assert not getattr(v, field).flags.writeable, (name, field)
            if cached.truth.corruption is not None:
                for key, mask in cached.truth.corruption.items():
                    assert np.array_equal(first.truth.corruption[key], mask) and not mask.flags.writeable
            with pytest.raises(ValueError):
                cached.depth[0, 0] = 0.0
            assert first.frame == second.frame == cached.frame
            assert first.truth.as_dict() == second.truth.as_dict() == cached.truth.as_dict()
            digest = hd1_scene.fixture_digest(first)
            assert digest == hd1_scene.fixture_digest(second) == hd1_scene.fixture_digest(cached)
            receipts["%s-%dx%d" % (name, grid[0], grid[1])] = digest
    assert len(set(receipts.values())) == len(receipts)       # no two variants share a digest
    # No digest is pinned anywhere: they are per-run receipts (trig may differ by an ulp per platform).
    for path in (_FIXTURE, Path(__file__)):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        pinned = [node.value for node in ast.walk(tree)
                  if isinstance(node, ast.Constant) and isinstance(node.value, str) and _HEX64.fullmatch(node.value)]
        assert pinned == [], path.name
    _metric("fixture_digests", note="per-run receipts, never pinned", receipts=receipts)


# ---------------------------------------------------------------------------
# 10. Independence from the code under test
# ---------------------------------------------------------------------------

_ALLOWED_IMPORTS = {"__future__", "dataclasses", "functools", "hashlib", "math", "numpy",
                    "synapse.worldlabs.atlas_contracts"}


def test_fixture_is_independent_of_the_code_under_test():
    source = _FIXTURE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import in the fixture"
            imported.add(node.module)
    assert imported <= _ALLOWED_IMPORTS, sorted(imported - _ALLOWED_IMPORTS)
    dynamic = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Name) and node.func.id in {"__import__", "exec", "eval", "open"})
        or (isinstance(node.func, ast.Attribute) and node.func.attr in {"import_module", "write_text",
                                                                         "write_bytes", "tofile", "mkdir"}))]
    assert dynamic == []
    # Neither file earns the needs_houdini marker, and neither evicts the resident hou.
    from conftest import module_runtime_requirement
    this = Path(__file__).read_text(encoding="utf-8")
    assert module_runtime_requirement(source) is None
    assert module_runtime_requirement(this) is None
    _metric("fixture_imports", imported=sorted(imported))


def test_fixture_loads_and_renders_without_houdini_files_or_network():
    """Execute the fixture afresh under an import, file and network guard, then render with it."""
    import builtins
    import socket
    real_import = builtins.__import__
    forbidden = {"hou", "pxr", "hdefereval", "pdg", "PySide2", "PySide6", "toolutils", "pytest"}

    def guard(name, *args, **kwargs):
        if name.split(".")[0] in forbidden or "physical" in name.split("."):
            raise AssertionError("the fixture imported " + name)
        return real_import(name, *args, **kwargs)

    probe = "hd1_scene_import_probe"
    with patch.dict(sys.modules), \
            patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
            patch("builtins.open", side_effect=AssertionError("file I/O forbidden")), \
            patch.object(Path, "open", side_effect=AssertionError("file I/O forbidden")), \
            patch.object(Path, "mkdir", side_effect=AssertionError("file I/O forbidden")), \
            patch.object(Path, "write_text", side_effect=AssertionError("file I/O forbidden")), \
            patch.object(Path, "write_bytes", side_effect=AssertionError("file I/O forbidden")), \
            patch("builtins.__import__", side_effect=guard):
        spec = importlib.util.spec_from_file_location(probe, _FIXTURE)
        fresh = importlib.util.module_from_spec(spec)
        sys.modules[probe] = fresh
        spec.loader.exec_module(fresh)
        rendered = {name: fresh.variant.__wrapped__(name, *fresh.CROSS_GRID) for name in fresh.VARIANTS}
        wall_only = fresh.no_floor_view()
        truth_points = rendered["D"].truth_points()
        digests = {name: fresh.fixture_digest(v) for name, v in rendered.items()}
    assert fresh.NUMPY_AVAILABLE is True and fresh.STATUS_BLOCKED == "BLOCKED"
    for name, v in rendered.items():
        assert _same(v.depth, hd1_scene.variant(name, *hd1_scene.CROSS_GRID).depth), name
    assert truth_points.shape == (90, 160, 3) and np.all(np.isfinite(truth_points))
    assert len(set(digests.values())) == len(digests)
    # The wall-only view: every pixel is wall at the closed-form depth 6.0 - 5.0 = 1.0 (level camera).
    assert np.all(wall_only.labels == _LABEL["wall"])
    assert np.array_equal(wall_only.depth, np.full((90, 160), 1.0))
    assert wall_only.truth.sites == () and wall_only.truth.reference_pair is None


def test_every_builder_is_blocked_without_numpy():
    """With numpy's import refused, the fixture still loads and every builder raises BLOCKED.

    Runs on a throwaway copy of the module, never on the shared ``hd1_scene``.
    """
    import builtins
    real_import = builtins.__import__

    def no_numpy(name, *args, **kwargs):
        if name.split(".")[0] == "numpy":
            raise ImportError("numpy refused for this check")
        return real_import(name, *args, **kwargs)

    probe = "hd1_scene_blocked_probe"
    with patch.dict(sys.modules):
        with patch("builtins.__import__", side_effect=no_numpy):
            spec = importlib.util.spec_from_file_location(probe, _FIXTURE)
            blocked = importlib.util.module_from_spec(spec)
            sys.modules[probe] = blocked
            spec.loader.exec_module(blocked)
        assert blocked.NUMPY_AVAILABLE is False and blocked.np is None
        calls = {
            "variant": lambda: blocked.variant("A", 16, 9),
            "variant.__wrapped__": lambda: blocked.variant.__wrapped__("D", 16, 9),
            "no_floor_view": lambda: blocked.no_floor_view(),
            "render": lambda: blocked.render((0.0, 1.5, 0.0), (0.0, 0.0, 0.0, 1.0), 16, 9),
            "array_sha256": lambda: blocked.array_sha256([1.0]),
            "fixture_digest": lambda: blocked.fixture_digest(None),
        }
        outcomes = {}
        for label, call in calls.items():
            with pytest.raises(blocked.FixtureBlocked, match="^BLOCKED: "):
                call()
            outcomes[label] = blocked.STATUS_BLOCKED
    _metric("blocked_without_numpy", outcomes=outcomes)


def test_no_floor_view_sees_only_the_wall():
    v = hd1_scene.no_floor_view()
    assert v is hd1_scene.variant(hd1_scene.NOFLOOR, *hd1_scene.CROSS_GRID)
    assert v.frame.pose.position == (0.0, 1.5, -5.0) and v.frame.pose.quaternion_xyzw == (0.0, 0.0, 0.0, 1.0)
    assert np.all(v.labels == _LABEL["wall"])
    assert np.array_equal(v.depth, np.full((90, 160), 1.0))      # the wall at z = -6, the camera at z = -5
    points = _contract_points(hd1_scene.NOFLOOR, 1.0)
    assert float(np.max(np.abs(points[..., 2] + 6.0))) <= 1e-12
    # The floor exists but is out of view; its truth is the scene's, and no site or pair applies.
    t = v.truth
    assert t.floor_normal == (0.0, 1.0, 0.0) and t.camera_height_units == 1.5
    assert t.sites == () and t.reference_pair is None and t.corruption is None
    big = hd1_scene.no_floor_view(1280, 720)
    assert np.all(big.labels == _LABEL["wall"]) and np.array_equal(big.depth, np.full((720, 1280), 1.0))
    _metric("no_floor_view", grid=[160, 90], wall_pixels=int((v.labels == _LABEL["wall"]).sum()),
            depth_min=float(v.depth.min()), depth_max=float(v.depth.max()))


def test_builders_refuse_bad_arguments():
    with pytest.raises(ValueError):
        hd1_scene.variant("E")
    with pytest.raises(ValueError):
        hd1_scene.variant("A", 160.0, 90)
    with pytest.raises(ValueError):
        hd1_scene.variant("A", True, 90)
    with pytest.raises(ValueError):
        hd1_scene.variant("A", 160, 90, pixel_offset=0.25)
    with pytest.raises(ValueError):
        hd1_scene.render((0.0, 1.5, 0.0), (0.0, 0.0, 0.0, 2.0), 16, 9)
    centres = hd1_scene.variant("A", *hd1_scene.CROSS_GRID, pixel_offset=0.5)
    landed = hd1_scene.variant("A", *hd1_scene.CROSS_GRID)
    assert centres.truth.pixel_offset == 0.5 and landed.truth.pixel_offset == 0.0
    assert centres.frame.frame_id != landed.frame.frame_id        # a centre-rendered frame never shares an id
    assert not np.array_equal(centres.depth, landed.depth)
