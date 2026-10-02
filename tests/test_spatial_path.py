"""The camera path read (D6): known answers for the move, clearance and trail.

Pure numpy, no Houdini and no OpenUSD, so this runs on CI. Every case builds
camera matrices whose answer is known by construction, the way the demo arc is
known (radius 6 m, +/-10 deg, eased, at 1.29 m), and checks that the read
recovers it. The trail's code is executed against a real stage in
test_spatial_trail_pxr.py, which needs OpenUSD.
"""
from __future__ import annotations

import math
import os
import sys

import pytest

np = pytest.importorskip("numpy")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.spatial import path as sp  # noqa: E402

FRAMES = list(range(1, 121))


def _matrix(position, yaw_deg, pitch_deg=0.0, scale=1.0):
    """Row-vector world matrix of a camera at ``position`` turned ``yaw_deg``
    about +Y (and pitched about its own X). Its lens looks down local -Z."""
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    ry = np.array([[math.cos(y), 0, -math.sin(y)], [0, 1, 0], [math.sin(y), 0, math.cos(y)]])
    rx = np.array([[1, 0, 0], [0, math.cos(p), math.sin(p)], [0, -math.sin(p), math.cos(p)]])
    rot = (rx @ ry) * scale
    m = np.eye(4)
    m[:3, :3] = rot
    m[3, :3] = position
    return m


def _ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def _demo_arc(radius=6.0, half_deg=10.0, height=1.29, centre=(0.0, 0.0, -6.0), facing=True):
    mats = []
    for f in FRAMES:
        a = math.radians(-half_deg + 2 * half_deg * _ease((f - 1) / 119.0))
        pos = (centre[0] + radius * math.sin(a), height, centre[2] + radius * math.cos(a))
        mats.append(_matrix(pos, math.degrees(a) if facing else 0.0))
    return mats


def _cam(mats):
    return sp.camera_frames(mats)


# --------------------------------------------------------------------------- #
#  The move                                                                   #
# --------------------------------------------------------------------------- #
def test_the_demo_arc_is_recovered():
    r = sp.summarize_move(FRAMES, _cam(_demo_arc()))
    m = r["move"]
    assert r["status"] == "SUCCESS" and r["frames_sampled"] == 120
    assert m["class"] == "arc" and m["class_tier"] == "derived"
    assert m["radius_m"] == pytest.approx(6.0, abs=0.05)
    assert m["orbit_deg"] == pytest.approx(20.0, abs=0.5)
    assert m["height_m"] == [pytest.approx(1.29, abs=0.01)] * 2
    assert m["path_length_m"] == pytest.approx(6.0 * math.radians(20.0), abs=0.01)
    assert m["yaw_sweep_deg"] == pytest.approx(20.0, abs=0.5)
    assert m["faces_centre"] is True
    assert m["aim_to_centre_deg"] == pytest.approx(0.0, abs=0.01)
    assert m["centre_m"] == [pytest.approx(0.0, abs=0.01), pytest.approx(1.29, abs=0.01),
                             pytest.approx(-6.0, abs=0.01)]


def test_an_arc_that_keeps_its_heading_does_not_face_the_centre():
    m = sp.summarize_move(FRAMES, _cam(_demo_arc(facing=False)))["move"]
    assert m["class"] == "arc"
    assert m["yaw_sweep_deg"] == pytest.approx(0.0, abs=0.01)
    assert m["aim_to_centre_deg"] == pytest.approx(10.0, abs=0.05)   # half the orbit
    assert m["faces_centre"] is False


def test_a_camera_that_does_not_move_is_static_measured():
    m = sp.summarize_move(FRAMES, _cam([_matrix((1, 1.29, 2), 15)] * 120))["move"]
    assert m["class"] == "static"
    assert m["path_length_m"] == 0.0 and m["yaw_sweep_deg"] == 0.0


def test_a_turn_in_place_is_a_pan():
    mats = [_matrix((0, 1.5, 0), 30.0 * (f - 1) / 119.0) for f in FRAMES]
    m = sp.summarize_move(FRAMES, _cam(mats))["move"]
    assert m["class"] == "pan"
    assert m["yaw_sweep_deg"] == pytest.approx(30.0, abs=0.01)


def test_a_straight_push_down_the_lens_is_a_dolly_in():
    mats = [_matrix((0, 1.29, -8.0 * (f - 1) / 119.0), 0.0) for f in FRAMES]
    m = sp.summarize_move(FRAMES, _cam(mats))["move"]
    assert m["class"] == "dolly" and m["direction"] == "in"
    assert m["path_length_m"] == pytest.approx(8.0, abs=1e-6)


def test_a_sideways_move_is_a_truck():
    mats = [_matrix((3.0 * (f - 1) / 119.0, 1.29, 0), 0.0) for f in FRAMES]
    m = sp.summarize_move(FRAMES, _cam(mats))["move"]
    assert m["class"] == "truck" and m["direction"] == "right"


def test_a_rise_is_a_crane_up():
    mats = [_matrix((0, 1.0 + 2.0 * (f - 1) / 119.0, 0), 0.0) for f in FRAMES]
    m = sp.summarize_move(FRAMES, _cam(mats))["move"]
    assert m["class"] == "crane" and m["direction"] == "up"
    assert m["vertical_travel_m"] == pytest.approx(2.0, abs=1e-6)


def test_stage_units_become_metres():
    mats = [_matrix((0, 129.0, -800.0 * (f - 1) / 119.0), 0.0) for f in FRAMES]
    m = sp.summarize_move(FRAMES, _cam(mats), meters_per_unit=0.01)["move"]
    assert m["path_length_m"] == pytest.approx(8.0, abs=1e-6)
    assert m["height_m"][0] == pytest.approx(1.29, abs=1e-6)


def test_scale_in_the_matrix_does_not_bend_the_lens_axes():
    cam = _cam([_matrix((0, 1, 0), 0.0, scale=3.0)])
    assert np.allclose(cam["forward"][0], [0, 0, -1])
    assert np.allclose(np.linalg.norm(cam["right"][0]), 1.0)


def test_no_samples_is_unknown_not_zero():
    r = sp.summarize_move([], {"position": np.zeros((0, 3)), "forward": np.zeros((0, 3)),
                               "right": np.zeros((0, 3)), "up": np.zeros((0, 3))})
    assert r["status"] == "UNKNOWN"


# --------------------------------------------------------------------------- #
#  Clearance                                                                  #
# --------------------------------------------------------------------------- #
def _wall(x, n=2000, seed=7):
    rng = np.random.default_rng(seed)
    return np.column_stack([np.full(n, x), rng.uniform(0, 3, n), rng.uniform(-12, 1, n)])


def test_clearance_finds_the_nearest_point_its_frame_and_side():
    # A point 0.8 m above the lens at frame 64. The arc keeps its height and
    # moves at right angles to "up", so every other frame is farther away.
    cam = _cam(_demo_arc())
    i = 63                                   # frame 64
    near = cam["position"][i] + 0.8 * cam["up"][i]
    points = np.vstack([_wall(30.0), near[None, :]])
    c = sp.clearance(FRAMES, cam, points)
    assert c["status"] == "SUCCESS"
    assert c["min_m"] == pytest.approx(0.8, abs=1e-3)
    assert c["frame"] == 64.0 and c["side"] == "above"
    assert c["within_near"] == 0                 # 0.8 m is outside the 0.5 m count
    assert c["point_count"] == len(points)


@pytest.mark.parametrize("offset, side", [((0.6, 0, 0), "right"), ((-0.6, 0, 0), "left"),
                                          ((0, -0.6, 0), "below"), ((0, 0, 0.6), "behind")])
def test_clearance_names_the_side_of_the_lens(offset, side):
    cam = _cam([_matrix((0, 1.5, 0), 0.0)] * 3)      # lens down -Z, right +X, up +Y
    point = np.array([[0.0, 1.5, 0.0]]) + np.array(offset)
    c = sp.clearance([1, 2, 3], cam, point)
    assert c["side"] == side and c["min_m"] == pytest.approx(0.6, abs=1e-6)
    assert c["within_near"] == 0


def test_a_single_floater_is_flagged_by_the_robust_figure():
    # A stray point 0.3 m down the lens at frame 60, on the arc's radius, so no
    # other frame comes closer to it; the wall stays metres away.
    cam = _cam(_demo_arc())
    floater = cam["position"][59] + 0.3 * cam["forward"][59]
    points = np.vstack([_wall(4.0, n=5000), floater[None, :]])
    c = sp.clearance(FRAMES, cam, points)
    assert c["min_m"] == pytest.approx(0.3, abs=1e-3) and c["side"] == "ahead"
    assert c["frame"] == 60.0 and c["within_near"] == 1
    assert c["robust_min_m"] > 2 * c["min_m"]
    line = sp.outcome_line("/cameras/demo_cam", sp.summarize_move(FRAMES, cam), c)
    assert "a stray point" in line
    assert "comes to 0.30 m, ahead of the lens, at frame 60" in line


def test_the_sentence_reads_behind_the_lens_not_behind_of():
    cam = _cam([_matrix((0, 1.5, 0), 0.0)] * 3)
    c = sp.clearance([1, 2, 3], cam, np.array([[0.0, 1.5, 0.6]]))
    line = sp.outcome_line("/cameras/c", sp.summarize_move([1, 2, 3], cam), c)
    assert "0.60 m, behind the lens, at frame 1" in line


def test_no_geometry_makes_clearance_unknown():
    cam = _cam(_demo_arc())
    c = sp.clearance(FRAMES, cam, [])
    assert c["status"] == "UNKNOWN" and "no geometry" in c["reason"]
    line = sp.outcome_line("/cameras/demo_cam", sp.summarize_move(FRAMES, cam), c)
    assert "clearance is UNKNOWN" in line


def test_clearance_is_reported_in_metres():
    mats = [_matrix((0, 129.0, 0), 0.0)] * 3
    points = np.array([[0.0, 129.0, -250.0]])
    c = sp.clearance([1, 2, 3], _cam(mats), points, meters_per_unit=0.01)
    assert c["min_m"] == pytest.approx(2.5, abs=1e-6) and c["side"] == "ahead"


# --------------------------------------------------------------------------- #
#  The sentence and the trail                                                 #
# --------------------------------------------------------------------------- #
def test_the_outcome_line_states_the_measured_arc():
    cam = _cam(_demo_arc())
    line = sp.outcome_line("/cameras/demo_cam", sp.summarize_move(FRAMES, cam), None)
    assert line.startswith("demo_cam: an arc of radius 6.00 m through 20.0 deg")
    assert "at a stage height of 1.29 m" in line and "aimed at the arc's centre" in line


def test_trail_code_compiles_and_names_no_vendor():
    cam = _cam(_demo_arc())
    code = sp.trail_code("/guides/demo_cam_path", FRAMES, cam, camera="/cameras/demo_cam")
    compile(code, "<trail>", "exec")
    assert "editableStage()" in code and "customData" not in code
    assert "world labs" not in code.lower() and "worldlabs" not in code.lower()
    assert "'proxy'" in code


@pytest.mark.parametrize("bad", [dict(purpose="invisible"), dict(frames=[1])])
def test_trail_code_refuses_bad_input(bad):
    cam = _cam(_demo_arc())
    kwargs = dict(prim_path="/guides/p", frames=FRAMES, cam=cam)
    if "frames" in bad:
        kwargs["frames"] = bad["frames"]
        kwargs["cam"] = {k: v[:1] for k, v in cam.items()}
    else:
        kwargs.update(bad)
    with pytest.raises(ValueError):
        sp.trail_code(**kwargs)


@pytest.mark.parametrize("field, value", [
    ("prim_path", "/guides/p\nimport os"), ("prim_path", "guides/p"), ("prim_path", "/guides/p'"),
    ("prim_path", "/guides/p\n"), ("prim_path", "/"), ("prim_path", "/guides/my path"),
    ("camera", "/cameras/c\nimport os"), ("camera", "/cameras/c\n"), ("camera", "demo_cam"),
    ("camera", "/cameras/c # x"),
])
def test_trail_code_takes_only_plain_prim_paths_as_text(field, value):
    """Houdini runs the trail's code, so the only text that reaches it is a
    plain absolute prim path. A newline would start a new statement."""
    cam = _cam(_demo_arc())
    kwargs = dict(prim_path="/guides/p", frames=FRAMES, cam=cam, camera="/cameras/c")
    kwargs[field] = value
    with pytest.raises(ValueError):
        sp.trail_code(**kwargs)


def test_trail_code_refuses_a_transform_that_is_not_finite():
    mats = _demo_arc()
    mats[5] = mats[5].copy()
    mats[5][3, 0] = float("nan")
    with pytest.raises(ValueError):
        sp.trail_code("/guides/p", FRAMES, _cam(mats))


def test_every_line_of_the_trail_code_is_ours():
    """The code is a fixed program over numbers: two comment lines, one import,
    and no call that reaches outside the stage it is handed."""
    cam = _cam(_demo_arc())
    code = sp.trail_code("/guides/demo_cam_path", FRAMES, cam, camera="/cameras/demo_cam")
    lines = code.splitlines()
    assert lines[0].startswith("# SYNAPSE: camera path of /cameras/demo_cam, frames 1-120.")
    assert [ln for ln in lines if ln.startswith(("import ", "from "))] == ["from pxr import Sdf, UsdGeom, Vt"]
    for banned in ("open(", "exec(", "eval(", "__import__", "os.", "subprocess", "hou.node", "setFrame"):
        assert banned not in code


def test_the_mesh_metric_says_it_is_measured_at_vertices():
    assert "vertex" in sp.MESH_METRIC and "can be closer" in sp.MESH_METRIC
    cam = _cam([_matrix((0, 1.5, 0), 0.0)] * 3)
    c = sp.clearance([1, 2, 3], cam, np.array([[0.0, 1.5, -2.0]]), metric=sp.MESH_METRIC)
    line = sp.outcome_line("/cameras/c", sp.summarize_move([1, 2, 3], cam), c)
    assert "the nearest mesh vertex comes to 2.00 m, ahead of the lens" in line


@pytest.mark.parametrize("n, says", [
    (1, "one sample, at frame 1, at a stage height of 1.50 m (too few samples to name the move)"),
    (2, "0.50 m of travel over 2 samples at a stage height of 1.50 m (too few samples to name the move)"),
    (4, "1.50 m of travel over 4 samples"),
])
def test_too_few_samples_measure_but_do_not_name_the_move(n, says):
    """One frame is not "static" and two points are not a "truck"."""
    mats = [_matrix((0.5 * i, 1.5, 0), 0.0) for i in range(n)]
    frames = list(range(1, n + 1))
    r = sp.summarize_move(frames, _cam(mats))
    assert r["status"] == "SUCCESS" and r["move"]["class"] is None
    assert r["move"]["class_note"].startswith("%d sample" % n)
    assert r["move"]["height_m"] == [1.5, 1.5]                      # the numbers still stand
    assert says in sp.outcome_line("/cameras/c", r, None)


def test_five_samples_are_enough_to_name_a_move():
    mats = [_matrix((0.5 * i, 1.5, 0), 0.0) for i in range(sp.MIN_CLASS_SAMPLES)]
    r = sp.summarize_move(list(range(1, 6)), _cam(mats))
    assert r["move"]["class"] == "truck" and "class_note" not in r["move"]


def test_a_z_up_stage_gives_the_same_arc():
    """The same move on a Z-up stage: turn every Y-up matrix into Z-up
    coordinates (x, y, z) -> (x, -z, y) and measure with the up axis at 2."""
    to_z_up = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
    cam = _cam([m @ to_z_up for m in _demo_arc()])
    m = sp.summarize_move(FRAMES, cam, up_index=2)["move"]
    assert m["class"] == "arc" and m["faces_centre"] is True
    assert m["radius_m"] == pytest.approx(6.0, abs=0.05)
    assert m["height_m"] == [pytest.approx(1.29, abs=0.01)] * 2
    assert m["centre_m"] == [pytest.approx(0.0, abs=0.01), pytest.approx(6.0, abs=0.01),
                             pytest.approx(1.29, abs=0.01)]
    assert m["yaw_sweep_deg"] == pytest.approx(20.0, abs=0.5)
