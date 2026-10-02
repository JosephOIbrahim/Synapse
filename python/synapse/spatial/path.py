"""The camera path read: the move, its clearance, and the trail (D6, 10/1).

Pure ``numpy`` over per-frame camera transforms the host has already measured.
No ``hou`` and no ``pxr``: the handler reads the scene and hands over plain
arrays, so every number here can be tested without Houdini, and every claim
can be checked against a known answer (the demo arc: radius 6 m, +/-10 deg,
eased, at 1.29 m).

    camera_frames(matrices)            positions and lens axes per frame
    summarize_move(frames, cam, ...)   the move: length, travel, height, yaw
                                       sweep, fitted radius, and a class
    clearance(frames, cam, points)     the nearest point to the lens, with a
                                       floater-resistant second figure
    outcome_line(...)                  the one sentence the panel shows
    trail_code(...)                    Python Script LOP code that draws the
                                       path; the HOST writes it, so the model
                                       never relays code or coordinates

Conventions. Matrices are 4x4 and row-vector, as USD and Houdini store them:
translation in the last row. A USD camera looks down its local -Z with +Y up.
Distances become metres through the stage's metersPerUnit. The move class is
SYNAPSE's own convention and is labelled tier ``derived``; every other number
is measured.

Directions and distances, never names: the world carries no semantic labels,
so nothing here says what a point belongs to. A camera that does not move is
``static``, measured. No geometry makes clearance UNKNOWN, never zero.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional, Sequence

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - numpy ships with Houdini and in CI
    np = None  # type: ignore
    NUMPY_AVAILABLE = False

STATUS_SUCCESS = "SUCCESS"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_BLOCKED = "BLOCKED"

# The move class (tier "derived"): SYNAPSE's convention, not a measurement.
STATIC_TRAVEL_M = 0.01      # under this, and under STATIC_ANGLE_DEG of turn: static
STATIC_ANGLE_DEG = 0.5
PAN_TRAVEL_M = 0.05         # under this with a turn: a pan or a tilt
CRANE_RATIO = 2.0           # vertical travel this many times the horizontal: a crane
ARC_MIN_ORBIT_DEG = 3.0     # a circle fit counts as an arc from this much orbit
ARC_MAX_RMS_FRAC = 0.02     # ... with the path within 2% of the radius
ARC_MAX_RADIUS_M = 100.0    # ... and a radius a set could hold
LINE_MAX_RMS_M = 0.02       # a straight move stays within 2 cm of its line
FACES_CENTRE_DEG = 5.0      # the lens stays within this of the arc's centre all move
MIN_CLASS_SAMPLES = 5       # fewer samples than this cannot name a move: class stays None

DEFAULT_NEAR_M = 0.5
DEFAULT_K = 10
POINT_METRIC = "nearest splat centre (extents not included)"
MESH_METRIC = "nearest mesh vertex (the surface between vertices can be closer)"

_CLASS_THRESHOLDS = {
    "static_travel_m": STATIC_TRAVEL_M, "static_angle_deg": STATIC_ANGLE_DEG,
    "pan_travel_m": PAN_TRAVEL_M, "crane_ratio": CRANE_RATIO,
    "arc_min_orbit_deg": ARC_MIN_ORBIT_DEG, "arc_max_rms_frac": ARC_MAX_RMS_FRAC,
    "arc_max_radius_m": ARC_MAX_RADIUS_M, "line_max_rms_m": LINE_MAX_RMS_M,
}


def _blocked() -> Optional[Dict[str, Any]]:
    if not NUMPY_AVAILABLE:
        return {"status": STATUS_BLOCKED, "reason": "the path read requires numpy"}
    return None


def _unit_rows(v):
    n = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(n == 0.0, 1.0, n)


def _r(x, nd=3):
    return None if x is None else round(float(x), nd)


def _plane(up_index: int):
    return tuple(i for i in range(3) if i != up_index)


# --------------------------------------------------------------------------- #
#  Camera frames                                                              #
# --------------------------------------------------------------------------- #
def camera_frames(matrices) -> Dict[str, Any]:
    """Positions and unit lens axes from row-vector 4x4 world matrices.

    ``forward`` is the camera's local -Z in world space, ``up`` its +Y and
    ``right`` its +X. Scale in the matrix does not leak into the axes.
    """
    m = np.asarray(matrices, dtype=float).reshape(-1, 4, 4)
    return {
        "position": m[:, 3, :3].copy(),
        "right": _unit_rows(m[:, 0, :3]),
        "up": _unit_rows(m[:, 1, :3]),
        "forward": -_unit_rows(m[:, 2, :3]),
    }


# --------------------------------------------------------------------------- #
#  The move                                                                   #
# --------------------------------------------------------------------------- #
def _fit_circle(xy):
    """Algebraic (Kasa) circle fit. Returns (centre, radius, rms) or None."""
    if len(xy) < 3:
        return None
    a = np.column_stack([xy[:, 0], xy[:, 1], np.ones(len(xy))])
    b = -(xy[:, 0] ** 2 + xy[:, 1] ** 2)
    try:
        sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    centre = np.array([-sol[0] / 2.0, -sol[1] / 2.0])
    r2 = float(centre @ centre - sol[2])
    if not math.isfinite(r2) or r2 <= 0.0:
        return None
    radius = math.sqrt(r2)
    rms = float(np.sqrt(np.mean((np.linalg.norm(xy - centre, axis=1) - radius) ** 2)))
    return centre, radius, rms


def _unwrapped_deg(angles_rad):
    return np.degrees(np.unwrap(angles_rad))


def summarize_move(frames: Sequence[float], cam: Dict[str, Any], up_index: int = 1,
                   meters_per_unit: float = 1.0) -> Dict[str, Any]:
    """Measure a camera move from its per-frame positions and lens axes."""
    blocked = _blocked()
    if blocked:
        return blocked
    frames = [float(f) for f in frames]
    p = np.asarray(cam["position"], dtype=float) * float(meters_per_unit)
    fwd = np.asarray(cam["forward"], dtype=float)
    if len(p) == 0 or len(p) != len(frames):
        return {"status": STATUS_UNKNOWN, "reason": "no camera samples to measure"}

    plane = _plane(up_index)
    h = p[:, plane]
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1) if len(p) > 1 else np.zeros(0)
    length = float(seg.sum())
    net = float(np.linalg.norm(p[-1] - p[0]))
    heights = p[:, up_index]
    vertical = float(heights.max() - heights.min())
    horizontal = float(np.linalg.norm(np.diff(h, axis=0), axis=1).sum()) if len(h) > 1 else 0.0

    # Heading and pitch of the lens. Looking straight up or down has no heading.
    fh = fwd[:, plane]
    fh_len = np.linalg.norm(fh, axis=1)
    has_heading = fh_len > 1e-6
    yaw_sweep = None
    if has_heading.any():
        yaw = _unwrapped_deg(np.arctan2(fh[has_heading, 0], fh[has_heading, 1]))
        yaw_sweep = float(yaw.max() - yaw.min())
    pitch = np.degrees(np.arcsin(np.clip(fwd[:, up_index], -1.0, 1.0)))
    pitch_range = float(pitch.max() - pitch.min())
    turn = max(yaw_sweep or 0.0, pitch_range)

    move: Dict[str, Any] = {
        "path_length_m": _r(length), "net_travel_m": _r(net),
        "horizontal_travel_m": _r(horizontal), "vertical_travel_m": _r(vertical),
        "height_m": [_r(heights.min()), _r(heights.max())],
        "yaw_sweep_deg": _r(yaw_sweep, 2), "pitch_range_deg": _r(pitch_range, 2),
        "radius_m": None, "orbit_deg": None, "fit_rms_m": None, "centre_m": None,
        "aim_to_centre_deg": None, "faces_centre": None, "direction": None,
    }

    cls: Optional[str] = "mixed"
    if len(frames) < MIN_CLASS_SAMPLES:
        # One frame is not "static" and two points are not a "truck": with too
        # few samples the numbers above stand and the move goes unnamed.
        cls = None
        move["class_note"] = "%d sample%s: too few to name the move" % (
            len(frames), "" if len(frames) == 1 else "s")
    elif length < PAN_TRAVEL_M:
        if turn < STATIC_ANGLE_DEG:
            cls = "static"
        else:
            cls = "pan" if (yaw_sweep or 0.0) >= pitch_range else "tilt"
    elif vertical >= CRANE_RATIO * horizontal and vertical >= PAN_TRAVEL_M:
        cls = "crane"
        move["direction"] = "up" if heights[-1] >= heights[0] else "down"
    else:
        fit = _fit_circle(h) if horizontal >= PAN_TRAVEL_M else None
        if fit is not None:
            centre, radius, rms = fit
            rel = h - centre
            orbit = _unwrapped_deg(np.arctan2(rel[:, 1], rel[:, 0]))
            orbit_deg = float(orbit.max() - orbit.min())
            if (radius <= ARC_MAX_RADIUS_M and rms <= ARC_MAX_RMS_FRAC * radius
                    and orbit_deg >= ARC_MIN_ORBIT_DEG):
                cls = "arc"
                move.update(radius_m=_r(radius), orbit_deg=_r(orbit_deg, 2), fit_rms_m=_r(rms, 4))
                centre_3d = [0.0, 0.0, 0.0]
                centre_3d[plane[0]], centre_3d[plane[1]] = float(centre[0]), float(centre[1])
                centre_3d[up_index] = float(heights.mean())
                move["centre_m"] = [_r(c) for c in centre_3d]
                if has_heading.any():
                    # Worst-case angle between the lens and the centre over the
                    # move: a camera that orbits a point keeps it near zero; one
                    # that holds its heading drifts by up to half the orbit.
                    to_c = _unit_rows(centre - h)
                    fhu = _unit_rows(fh)
                    cosang = np.clip(np.sum(to_c * fhu, axis=1)[has_heading], -1.0, 1.0)
                    aim = float(np.max(np.degrees(np.arccos(cosang))))
                    move["aim_to_centre_deg"] = _r(aim, 2)
                    move["faces_centre"] = bool(aim <= FACES_CENTRE_DEG)
        if cls != "arc" and len(h) >= 2:
            # A straight move: principal axis of the horizontal path.
            hc = h - h.mean(axis=0)
            _, _, vt = np.linalg.svd(hc, full_matrices=False)
            axis = vt[0]
            perp = hc - np.outer(hc @ axis, axis)
            line_rms = float(np.sqrt(np.mean(np.sum(perp ** 2, axis=1))))
            if line_rms <= max(LINE_MAX_RMS_M, 0.01 * horizontal):
                travel = h[-1] - h[0]
                if np.linalg.norm(travel) > 0:
                    travel = travel / np.linalg.norm(travel)
                mean_f = fh[has_heading].mean(axis=0) if has_heading.any() else None
                mean_r = np.asarray(cam["right"], dtype=float)[:, plane].mean(axis=0)
                if mean_f is not None and np.linalg.norm(mean_f) > 0:
                    cos_f = float(travel @ (mean_f / np.linalg.norm(mean_f)))
                    if abs(cos_f) >= 0.7:
                        cls = "dolly"
                        move["direction"] = "in" if cos_f > 0 else "out"
                    elif abs(cos_f) <= 0.3:
                        cls = "truck"
                        cos_r = float(travel @ (mean_r / (np.linalg.norm(mean_r) or 1.0)))
                        move["direction"] = "right" if cos_r > 0 else "left"
    move["class"] = cls
    move["class_tier"] = "derived"
    move["class_thresholds"] = dict(_CLASS_THRESHOLDS)
    return {"status": STATUS_SUCCESS, "frames_sampled": len(frames),
            "frame_range": [frames[0], frames[-1]], "move": move}


# --------------------------------------------------------------------------- #
#  Clearance                                                                  #
# --------------------------------------------------------------------------- #
def _side(v, right, up, forward):
    comps = {"right": float(v @ right), "above": float(v @ up), "ahead": float(v @ forward)}
    name, val = max(comps.items(), key=lambda kv: abs(kv[1]))
    if val >= 0:
        return name
    return {"right": "left", "above": "below", "ahead": "behind"}[name]


def clearance(frames: Sequence[float], cam: Dict[str, Any], points,
              meters_per_unit: float = 1.0, near_m: float = DEFAULT_NEAR_M,
              k: int = DEFAULT_K, metric: str = POINT_METRIC) -> Dict[str, Any]:
    """The nearest geometry point to the lens over the move.

    ``min_m`` is the single nearest point, so one floater can set it. That is
    why ``robust_min_m`` travels with it: the distance to the k-th nearest
    point, minimised over the frames. A large gap between the two says the
    minimum is a stray point, not a surface. ``within_near`` counts the points
    inside ``near_m`` of the lens on the minimum's frame.
    """
    blocked = _blocked()
    if blocked:
        return blocked
    if points is None or len(points) == 0:
        return {"status": STATUS_UNKNOWN, "metric": metric,
                "reason": "no geometry on the stage to measure against"}
    mpu = float(meters_per_unit)
    pts = np.asarray(points, dtype=float).reshape(-1, 3) * mpu
    pos = np.asarray(cam["position"], dtype=float) * mpu
    frames = [float(f) for f in frames]
    k = max(1, min(int(k), len(pts)))
    sq = np.einsum("ij,ij->i", pts, pts)
    best = (math.inf, -1, -1)            # (distance, frame index, point index)
    robust = (math.inf, -1)
    for i, c in enumerate(pos):
        d2 = np.maximum(sq - 2.0 * (pts @ c) + float(c @ c), 0.0)
        j = int(np.argmin(d2))
        if d2[j] < best[0] ** 2 or best[1] < 0:
            best = (math.sqrt(float(d2[j])), i, j)
        kth = math.sqrt(float(np.partition(d2, k - 1)[k - 1]))
        if kth < robust[0]:
            robust = (kth, i)
    dist, fi, pj = best
    c = pos[fi]
    d2_at = np.maximum(sq - 2.0 * (pts @ c) + float(c @ c), 0.0)
    within = int(np.count_nonzero(d2_at < near_m * near_m))
    v = pts[pj] - c
    side = _side(v, np.asarray(cam["right"])[fi], np.asarray(cam["up"])[fi],
                 np.asarray(cam["forward"])[fi])
    return {
        "status": STATUS_SUCCESS, "metric": metric,
        "min_m": _r(dist), "frame": frames[fi], "side": side,
        "robust_min_m": _r(robust[0]), "robust_frame": frames[robust[1]], "k": k,
        "within_near": within, "near_m": near_m, "point_count": int(len(pts)),
    }


# --------------------------------------------------------------------------- #
#  The sentence                                                               #
# --------------------------------------------------------------------------- #
_SIDE_PHRASE = {"right": "right of the lens", "left": "left of the lens",
                "above": "above the lens", "below": "below the lens",
                "ahead": "ahead of the lens", "behind": "behind the lens"}


def _fmt_frame(f):
    return str(int(f)) if float(f).is_integer() else "%.2f" % f


def outcome_line(camera: str, move: Dict[str, Any], clear: Optional[Dict[str, Any]]) -> str:
    """One sentence, composed by code from measured fields only.

    Heights are the camera's coordinate on the stage's up axis ("stage
    height"), not its height above whatever ground the scene has."""
    m = move.get("move", {}) if move.get("status") == STATUS_SUCCESS else {}
    name = camera.rsplit("/", 1)[-1] or camera
    cls = m.get("class")
    lo, hi = (m.get("height_m") or [None, None])
    if lo is None:
        height = ""
    elif hi - lo < 0.01:
        height = " at a stage height of %.2f m" % lo
    else:
        height = " between stage heights of %.2f m and %.2f m" % (lo, hi)
    sampled = move.get("frames_sampled") or 0
    if not m:
        what = "its move is UNKNOWN (%s)" % move.get("reason", "not measured")
    elif cls is None and sampled == 1:
        what = "one sample, at frame %s,%s (too few samples to name the move)" % (
            _fmt_frame(move["frame_range"][0]), height)
    elif cls is None:
        what = "%.2f m of travel over %d samples%s (too few samples to name the move)" % (
            m["path_length_m"], sampled, height)
    elif cls == "arc":
        what = "an arc of radius %.2f m through %.1f deg, %.2f m of travel%s" % (
            m["radius_m"], m["orbit_deg"], m["path_length_m"], height)
        if m.get("faces_centre"):
            what += ", aimed at the arc's centre"
    elif cls == "dolly":
        what = "a dolly %s, %.2f m%s" % (m.get("direction"), m["path_length_m"], height)
    elif cls == "truck":
        what = "a truck %s, %.2f m%s" % (m.get("direction"), m["path_length_m"], height)
    elif cls == "crane":
        what = "a crane %s, %.2f m" % (m.get("direction"), m["vertical_travel_m"])
    elif cls == "pan":
        what = "a pan through %.1f deg%s" % (m["yaw_sweep_deg"], height)
    elif cls == "tilt":
        what = "a tilt through %.1f deg%s" % (m["pitch_range_deg"], height)
    elif cls == "static":
        what = "static%s" % height
    else:
        what = "a mixed move, %.2f m of travel%s" % (m["path_length_m"], height)
    line = "%s: %s" % (name, what)
    if clear is None:
        return line + "."
    if clear.get("status") != STATUS_SUCCESS:
        return line + "; clearance is UNKNOWN (%s)." % clear.get("reason", "not measured")
    line += "; the %s comes to %.2f m, %s, at frame %s" % (
        clear["metric"].split(" (")[0], clear["min_m"],
        _SIDE_PHRASE.get(clear["side"], clear["side"]), _fmt_frame(clear["frame"]))
    if clear["robust_min_m"] >= 2.0 * max(clear["min_m"], 0.01):
        line += " (a stray point: the %dth nearest is %.2f m)" % (clear["k"], clear["robust_min_m"])
    return line + "."


# --------------------------------------------------------------------------- #
#  The trail                                                                  #
# --------------------------------------------------------------------------- #
TRAIL_START_RGB = (0.15, 0.55, 1.0)
TRAIL_END_RGB = (1.0, 0.45, 0.05)
# The trail's code is run by Houdini, so what goes into it is checked: prim
# paths are absolute paths of plain identifiers, and nothing else is text.
_PRIM_PATH_RE = re.compile(r"(/[A-Za-z_][A-Za-z0-9_]*)+")     # used with fullmatch


def trail_code(prim_path: str, frames: Sequence[float], cam: Dict[str, Any],
               camera: str = "", meters_per_unit: float = 1.0, purpose: str = "proxy",
               width_m: float = 0.02, tick_every: int = 10, tick_m: float = 0.5,
               start_rgb=TRAIL_START_RGB, end_rgb=TRAIL_END_RGB) -> str:
    """Python Script LOP code that authors the path as one BasisCurves prim.

    The host generates this and writes it into the node. The path is one linear
    curve through every sampled camera position, in stage units at default
    time, so the whole move shows at every frame. Every ``tick_every``-th
    sample adds a short tick along the lens axis, so the trail also shows where
    the camera aims. Colour runs from ``start_rgb`` on the first frame to
    ``end_rgb`` on the last. Each vertex carries its frame as the primvar
    ``camera_frame``. No customData is written.

    Houdini runs this code, so its only text inputs are checked: ``prim_path``
    and ``camera`` must be absolute USD paths of plain identifiers, ``purpose``
    one of the four USD purposes. Everything else in it is a number.
    """
    if purpose not in ("default", "render", "proxy", "guide"):
        raise ValueError("purpose must be default, render, proxy or guide")
    if not _PRIM_PATH_RE.fullmatch(str(prim_path)):
        raise ValueError("the trail's prim path must be an absolute USD path, not %r" % (prim_path,))
    if camera and not _PRIM_PATH_RE.fullmatch(str(camera)):
        raise ValueError("the camera must be an absolute USD prim path, not %r" % (camera,))
    pos = np.asarray(cam["position"], dtype=float)
    fwd = np.asarray(cam["forward"], dtype=float)
    frames = [float(f) for f in frames]
    if len(pos) < 2 or len(pos) != len(frames):
        raise ValueError("a trail needs at least two camera samples, one per frame")
    if not (np.isfinite(pos).all() and np.isfinite(fwd).all() and np.isfinite(frames).all()):
        raise ValueError("the camera's transform is not finite on every sampled frame")
    mpu = float(meters_per_unit) or 1.0
    tick = tick_m / mpu
    points = [tuple(round(float(x), 4) for x in p) for p in pos]
    counts = [len(points)]
    vframes = list(frames)
    if tick_every and tick_every > 0:
        for i in range(0, len(pos), int(tick_every)):
            tip = pos[i] + fwd[i] * tick
            points += [tuple(round(float(x), 4) for x in pos[i]),
                       tuple(round(float(x), 4) for x in tip)]
            counts.append(2)
            vframes += [frames[i], frames[i]]
    parent = prim_path.rsplit("/", 1)[0] or "/"
    lines = [
        "# SYNAPSE: camera path%s, frames %s-%s. Written by SYNAPSE's spatial read," % (
            (" of " + camera) if camera else "", _fmt_frame(frames[0]), _fmt_frame(frames[-1])),
        "# not by the model. A snapshot of the move: ask again after the move changes.",
        "from pxr import Sdf, UsdGeom, Vt",
        "stage = hou.pwd().editableStage()",
    ]
    if parent != "/":
        # Only when it is not there: an artist's own prim at that path keeps its type.
        lines += ["if not stage.GetPrimAtPath(%r):" % parent,
                  "    UsdGeom.Scope.Define(stage, %r)" % parent]
    lines += [
        "curves = UsdGeom.BasisCurves.Define(stage, %r)" % prim_path,
        "POINTS = %r" % (points,),
        "COUNTS = %r" % (counts,),
        "FRAMES = %r" % ([round(f, 3) for f in vframes],),
        "F0, F1 = %r, %r" % (frames[0], frames[-1]),
        "A, B = %r, %r" % (tuple(start_rgb), tuple(end_rgb)),
        "def _mix(f):",
        "    t = (f - F0) / (F1 - F0) if F1 != F0 else 0.0",
        "    return tuple(a + (b - a) * t for a, b in zip(A, B))",
        "curves.CreateTypeAttr(UsdGeom.Tokens.linear)",
        "curves.CreateWrapAttr(UsdGeom.Tokens.nonperiodic)",
        "curves.CreatePointsAttr(Vt.Vec3fArray(POINTS))",
        "curves.CreateCurveVertexCountsAttr(Vt.IntArray(COUNTS))",
        "curves.CreateWidthsAttr(Vt.FloatArray([%r]))" % round(width_m / mpu, 6),
        "curves.SetWidthsInterpolation(UsdGeom.Tokens.constant)",
        "curves.CreatePurposeAttr(%r)" % purpose,
        "curves.CreateDisplayColorPrimvar(UsdGeom.Tokens.vertex).Set(Vt.Vec3fArray([_mix(f) for f in FRAMES]))",
        "UsdGeom.PrimvarsAPI(curves.GetPrim()).CreatePrimvar(",
        "    'camera_frame', Sdf.ValueTypeNames.FloatArray, UsdGeom.Tokens.vertex).Set(Vt.FloatArray(FRAMES))",
        "_lo = [min(p[i] for p in POINTS) - %r for i in range(3)]" % round(width_m / mpu / 2.0, 6),
        "_hi = [max(p[i] for p in POINTS) + %r for i in range(3)]" % round(width_m / mpu / 2.0, 6),
        "curves.CreateExtentAttr(Vt.Vec3fArray([tuple(_lo), tuple(_hi)]))",
    ]
    return "\n".join(lines) + "\n"
