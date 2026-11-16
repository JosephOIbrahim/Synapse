"""HD1 point cloud: numpy unprojection, its stages, the stride cap and the footprint (SPEC 6).

Pure numpy. No hou, no pxr and no I/O, mirroring spatial/path.py; importing
this module registers nothing.

    unproject_raw(frame, depth, keep)       stage "raw": the pose frame and units
    unproject_scaled(frame, depth, keep)    stage "scaled": metres, neither
                                            levelled nor grounded; the stage the
                                            contract's unproject_metric returns
    floor_of(raw)                           level.fit_floor on a raw cloud
    choose_stride(keep, cap)                the first 2-D stride that fits the cap
    footprint_radius(depth_m, stride, fx)   depth_m * stride / fx * k
    physical_cloud(frame, depth, keep, claim, floor)
                                            stage "physical": scale, then level,
                                            then ground, strided, with radii
    half_pixel_delta(frame, depth, keep)    BLU-C-HD-01 measured; never resolved

Convention. The unprojection matches the landed contract
(``atlas_contracts.unproject_metric``) operation for operation: camera-grid
pixel ``(x, y)`` (row 0 at the top) unprojects at ``x - cx`` and ``y - cy``, RUB
negates camera y and z, the quaternion rotates by ``v + w t + q x t`` with
``t = 2 q x v``, the position is added, and the scale multiplies the translated
point. So the scaled stage equals the contract point for point, and a scale
applies to depth and camera position together. ``bottom_up`` buffers are read
in camera-grid order. Pixel centres (``x + 0.5 - cx``, AT1 SPEC 7.3) are used
only inside ``half_pixel_delta``, through a private argument: there is no second
public convention (D-HD-04 is the owner's).

Order of application (SPEC 5): scale, then level, then ground, as
``p_final = R(level) * (s * p_raw) + (0, s * d, 0)``. The stride is a 2-D pixel
stride on the camera grid (rows and columns both divisible by it), the first
``s = 1, 2, 3, ...`` that keeps at most ``cap`` points; the count is not monotone
in ``s`` for sparse masks, so the scan never skips. Each point's footprint
radius is ``depth_m * stride / fx * k``.

Without numpy every function here raises PhysicalBlocked ("BLOCKED: ...").
Error messages are public-safe: they never echo an input value.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numbers
from typing import Any, Dict, Optional, Tuple

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - numpy is a dev extra; without it every step raises BLOCKED
    np = None  # type: ignore
    NUMPY_AVAILABLE = False

from ..atlas_contracts import ContractError, PosedRGBDFrame
from .level import STATUS_SUCCESS, FloorFit, PhysicalBlocked, fit_floor, ground_offset, rotation_matrix
from .scale import ScaleRefused, apply_claim

POINT_CAP = 250_000             # SPEC 6, AT1 SPEC 7.3: at most this many points, inclusive
FOOTPRINT_K = 0.75              # SPEC 6 proposal (D-1's to rule)
ORDER = ("scale", "level", "ground")
CONVENTION_LANDED = "x - cx (atlas_contracts.unproject_metric)"
CONVENTION_ALTERNATIVE = "x + 0.5 - cx (AT1 SPEC 7.3)"
FOOTPRINT_FORMULA = "radius_m = depth_m * stride / fx * k"


@dataclass(frozen=True, eq=False)
class RawCloud:
    """Stage "raw": no scale, no level, no ground. Arrays are read-only.

    ``grid`` is (height, width). ``rows`` and ``cols`` are camera-grid pixel
    indices (row 0 at the top) in raster order; ``depth`` is planar depth and
    ``points`` (N, 3) are in the pose frame, both in raw units.
    """

    frame_id: str
    grid: Tuple[int, int]
    rows: np.ndarray
    cols: np.ndarray
    depth: np.ndarray
    points: np.ndarray
    camera_position: Tuple[float, float, float]
    stage: str = "raw"


@dataclass(frozen=True, eq=False)
class ScaledCloud:
    """Stage "scaled": metres, neither levelled nor grounded; equals ``unproject_metric``.

    The cross-check stage (SPEC 6). Arrays are read-only; ``grid`` is (height, width).
    """

    frame_id: str
    grid: Tuple[int, int]
    rows: np.ndarray
    cols: np.ndarray
    depth_m: np.ndarray
    points_m: np.ndarray
    camera_position_m: Tuple[float, float, float]
    metres_per_unit: float
    stage: str = "scaled"


@dataclass(frozen=True, eq=False)
class PhysicalCloud:
    """Stage "physical": scaled, levelled, grounded and strided, with a radius per point.

    ``points_m`` (M, 3) and ``radius_m`` (M,) are in metres; ``colour`` is (M, 3)
    floats in [0, 1] or None. ``scale`` is the claim's record (provenancedNumber
    plus inputs). Arrays are read-only; ``grid`` is (height, width).
    """

    frame_id: str
    evidence_tier: str
    grid: Tuple[int, int]
    stride: int
    point_cap: int
    points_before_cap: int
    rows: np.ndarray
    cols: np.ndarray
    points_m: np.ndarray
    radius_m: np.ndarray
    colour: Optional[np.ndarray]
    scale: Dict[str, Any]
    level_xyzw: Tuple[float, float, float, float]
    ground_offset_m: float
    applied: Dict[str, bool]
    footprint_k: float
    stage: str = "physical"

    def describe(self) -> Dict[str, Any]:
        """JSON-safe: counts, bounds, radius statistics, the stride and the transform."""
        count = int(self.points_m.shape[0])
        bounds = radius = None
        if count:
            low, high = self.points_m.min(axis=0), self.points_m.max(axis=0)
            bounds = {"min": [_f(v) for v in low], "max": [_f(v) for v in high]}
            radius = {"min": _f(self.radius_m.min()), "median": _f(np.median(self.radius_m)),
                      "max": _f(self.radius_m.max())}
        scale = dict(self.scale)
        inputs = scale.pop("inputs", {})
        return {
            "stage": self.stage,
            "frame_id": self.frame_id,
            "evidence_tier": self.evidence_tier,
            "grid": list(self.grid),
            "stride": self.stride,
            "point_cap": self.point_cap,
            "points_before_cap": self.points_before_cap,
            "points": count,
            "bounds_m": bounds,
            "radius_m": radius,
            "footprint_k": self.footprint_k,
            "footprint": FOOTPRINT_FORMULA,
            "colour": self.colour is not None,
            "transform": {
                "order": list(ORDER),
                "scale": scale,
                "scale_inputs": dict(inputs),
                "level_xyzw": list(self.level_xyzw),
                "ground_offset_m": self.ground_offset_m,
                "applied": dict(self.applied),
            },
        }


def _f(value) -> float:
    """A plain Python float with -0.0 folded to 0.0."""
    return float(value) + 0.0


def _require_numpy(what: str) -> None:
    if not NUMPY_AVAILABLE:
        raise PhysicalBlocked("BLOCKED: " + what + " requires numpy")


def _real(value, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ContractError(message)
    number = float(value)
    if not math.isfinite(number):
        raise ContractError(message)
    return number


def _positive(value, message: str) -> float:
    number = _real(value, message)
    if not number > 0.0:
        raise ContractError(message)
    return number


def _integer(value, message: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or int(value) < minimum:
        raise ContractError(message)
    return int(value)


def _read_only(array):
    array.setflags(write=False)
    return array


def _frame(frame) -> PosedRGBDFrame:
    if not isinstance(frame, PosedRGBDFrame):
        raise ContractError("a PosedRGBDFrame is required")
    return frame


def _camera_grid(frame: PosedRGBDFrame, depth, keep):
    """(depth float64, keep bool) on the camera grid: a bottom_up buffer is read bottom row first."""
    camera = frame.intrinsics
    shape = (camera.height, camera.width)
    try:
        z = np.asarray(depth)
        k = np.asarray(keep)
    except (TypeError, ValueError, OverflowError):
        raise ContractError("depth and keep must be arrays on the camera grid") from None
    if z.dtype.kind not in "iuf" or z.shape != shape:
        raise ContractError("decoded depth must be an (H, W) real array on the camera grid")
    if k.dtype.kind != "b" or k.shape != shape:
        raise ContractError("keep must be an (H, W) bool mask on the camera grid")
    z = np.asarray(z, dtype=np.float64)
    if frame.decoded_row_order == "bottom_up":
        z, k = z[::-1], k[::-1]
    return z, k


def _unproject(frame: PosedRGBDFrame, z, k, offset: float):
    """(rows, cols, depth, points) in raw units, in the contract's operation order.

    ``offset`` is 0.0 (the landed convention) everywhere except the private
    half-pixel measurement, which passes 0.5.
    """
    rows, cols = np.nonzero(k)
    zz = z[rows, cols]
    if not (np.isfinite(zz).all() and (zz > 0.0).all()):
        raise ContractError("keep selects invalid depth")
    camera = frame.intrinsics
    x = cols if offset == 0.0 else cols + offset
    y = rows if offset == 0.0 else rows + offset
    qx, qy, qz, qw = frame.pose.quaternion_xyzw
    px, py, pz = frame.pose.position
    with np.errstate(over="ignore", invalid="ignore"):
        vx = (x - camera.cx) * zz / camera.fx
        vy = (y - camera.cy) * zz / camera.fy
        vz = zz
        if frame.pose.coordinate_system == "rub":
            vy, vz = -vy, -vz
        tx = 2 * (qy * vz - qz * vy)
        ty = 2 * (qz * vx - qx * vz)
        tz = 2 * (qx * vy - qy * vx)
        rx = vx + qw * tx + qy * tz - qz * ty
        ry = vy + qw * ty + qz * tx - qx * tz
        rz = vz + qw * tz + qx * ty - qy * tx
        points = np.column_stack((rx + px, ry + py, rz + pz))
    if not np.isfinite(points).all():
        raise ContractError("non-finite unprojected point")
    return rows, cols, zz, points


def unproject_raw(frame, depth, keep) -> RawCloud:
    """Every kept pixel in the pose frame and raw units: no scale, no level, no ground.

    ``depth`` and ``keep`` are (H, W) in the decoded buffer's row order; ``keep``
    must select only finite depths above 0. Inputs are never written.
    """
    _require_numpy("unproject_raw")
    frame = _frame(frame)
    z, k = _camera_grid(frame, depth, keep)
    rows, cols, zz, points = _unproject(frame, z, k, 0.0)
    camera = frame.intrinsics
    return RawCloud(frame.frame_id, (camera.height, camera.width), _read_only(rows), _read_only(cols),
                    _read_only(zz), _read_only(points), tuple(frame.pose.position))


def unproject_scaled(frame, depth, keep) -> ScaledCloud:
    """The raw cloud times the frame's ``metres_per_unit``: the contract's own stage.

    The frame must carry a scale (``scale.apply_claim``); without one this
    refuses with ScaleRefused("metric scale is unknown"), the contract's words.
    """
    _require_numpy("unproject_scaled")
    frame = _frame(frame)
    if frame.metres_per_unit is None:
        raise ScaleRefused("metric scale is unknown")
    z, k = _camera_grid(frame, depth, keep)
    rows, cols, zz, points = _unproject(frame, z, k, 0.0)
    scale = frame.metres_per_unit
    with np.errstate(over="ignore", invalid="ignore"):
        points_m = points * scale
        depth_m = zz * scale
    if not (np.isfinite(points_m).all() and np.isfinite(depth_m).all()):
        raise ContractError("non-finite unprojected point")
    camera = frame.intrinsics
    return ScaledCloud(frame.frame_id, (camera.height, camera.width), _read_only(rows), _read_only(cols),
                       _read_only(depth_m), _read_only(points_m),
                       tuple(_f(p * scale) for p in frame.pose.position), scale)


def floor_of(raw: RawCloud, **kwargs):
    """``level.fit_floor`` on a raw cloud's fields; keyword arguments pass through."""
    if not isinstance(raw, RawCloud):
        raise ContractError("a RawCloud is required")
    return fit_floor(raw.points, raw.rows, raw.depth, grid_rows=raw.grid[0],
                     camera_position=raw.camera_position, **kwargs)


def choose_stride(keep_camera_grid, cap=POINT_CAP) -> int:
    """The first ``s = 1, 2, 3, ...`` with ``count_nonzero(keep[::s, ::s]) <= cap``.

    A 2-D pixel stride on the camera grid, origin at the top-left. The scan
    starts at 1 and never skips, because the count is not monotone in ``s``. It
    ends by ``s = max(H, W)``, where at most one pixel remains.
    """
    _require_numpy("choose_stride")
    try:
        k = np.asarray(keep_camera_grid)
    except (TypeError, ValueError):
        raise ContractError("keep must be a non-empty 2-D bool mask") from None
    if k.dtype.kind != "b" or k.ndim != 2 or k.size == 0:
        raise ContractError("keep must be a non-empty 2-D bool mask")
    cap = _integer(cap, "cap must be a positive integer", 1)
    stride = 1
    while int(np.count_nonzero(k[::stride, ::stride])) > cap:
        stride += 1
    return stride


def footprint_radius(depth_m, stride, fx, k=FOOTPRINT_K):
    """``depth_m * stride / fx * k``, evaluated left to right: a footprint per point, in metres."""
    _require_numpy("footprint_radius")
    try:
        z = np.asarray(depth_m)
    except (TypeError, ValueError):
        raise ContractError("depth_m must be an array of finite depths above 0") from None
    if z.dtype.kind not in "iuf":
        raise ContractError("depth_m must be an array of finite depths above 0")
    z = np.asarray(z, dtype=np.float64)
    if not (np.isfinite(z).all() and (z > 0.0).all()):
        raise ContractError("depth_m must be an array of finite depths above 0")
    stride = _integer(stride, "stride must be a positive integer", 1)
    fx = _positive(fx, "fx must be a finite number above 0")
    k = _positive(k, "k must be a finite number above 0")
    return z * stride / fx * k


def _colour_grid(colour, shape, bottom_up: bool):
    try:
        c = np.asarray(colour)
    except (TypeError, ValueError):
        raise ContractError("colour must be an (H, W, 3) array on the camera grid") from None
    if c.shape != tuple(shape) + (3,):
        raise ContractError("colour must be an (H, W, 3) array on the camera grid")
    if c.dtype == np.uint8:
        c = c / 255.0
    elif c.dtype.kind == "f":
        c = np.asarray(c, dtype=np.float64)
        if not (np.isfinite(c).all() and (c >= 0.0).all() and (c <= 1.0).all()):
            raise ContractError("colour floats must be finite and in [0, 1]")
    else:
        raise ContractError("colour must be uint8, or floats in [0, 1]")
    return c[::-1] if bottom_up else c


def physical_cloud(frame, depth, keep, claim, floor, *, colour=None, cap=POINT_CAP,
                   k=FOOTPRINT_K) -> PhysicalCloud:
    """Scale, then level, then ground; then stride to the cap, with a footprint per point.

    ``frame`` is the dormant frame (no scale): the claim is applied here, and an
    unknown claim refuses (ScaleRefused). ``floor`` is the raw-unit fit of the
    same frame and must be SUCCESS. ``colour`` is optional: (H, W, 3) uint8, or
    floats in [0, 1], in the buffer's row order.
    """
    _require_numpy("physical_cloud")
    cap = _integer(cap, "cap must be a positive integer", 1)
    k = _positive(k, "k must be a finite number above 0")
    framed = apply_claim(_frame(frame), claim)
    if not isinstance(floor, FloorFit) or floor.status != STATUS_SUCCESS:
        raise ContractError("floor is UNKNOWN")
    camera = framed.intrinsics
    if floor.grid_rows != camera.height:
        raise ContractError("the floor was fitted on another grid")
    shape = (camera.height, camera.width)
    tint = None if colour is None else _colour_grid(colour, shape, framed.decoded_row_order == "bottom_up")
    scaled = unproject_scaled(framed, depth, keep)
    kept = np.zeros(shape, dtype=bool)
    kept[scaled.rows, scaled.cols] = True
    stride = choose_stride(kept, cap)
    chosen = (scaled.rows % stride == 0) & (scaled.cols % stride == 0)
    rows, cols = scaled.rows[chosen], scaled.cols[chosen]
    x, y, z = (np.ascontiguousarray(scaled.points_m[chosen, axis]) for axis in range(3))
    m = rotation_matrix(floor.level_xyzw)
    lift = ground_offset(framed.metres_per_unit, floor)
    # Written out per component, not as a matrix product, so the result repeats bit for bit.
    points = np.column_stack((
        m[0, 0] * x + m[0, 1] * y + m[0, 2] * z,
        m[1, 0] * x + m[1, 1] * y + m[1, 2] * z + lift,
        m[2, 0] * x + m[2, 1] * y + m[2, 2] * z,
    ))
    radius = footprint_radius(scaled.depth_m[chosen], stride, camera.fx, k)
    picked = None if tint is None else _read_only(np.ascontiguousarray(tint[rows, cols]))
    return PhysicalCloud(
        frame_id=framed.frame_id,
        evidence_tier=framed.depth.evidence_tier,
        grid=shape,
        stride=stride,
        point_cap=cap,
        points_before_cap=int(scaled.points_m.shape[0]),
        rows=_read_only(rows),
        cols=_read_only(cols),
        points_m=_read_only(points),
        radius_m=_read_only(radius),
        colour=picked,
        scale=claim.as_record(),
        level_xyzw=tuple(floor.level_xyzw),
        ground_offset_m=lift,
        applied={step: True for step in ORDER},
        footprint_k=k,
    )


def half_pixel_delta(frame, depth, keep) -> Dict[str, Any]:
    """BLU-C-HD-01 measured on one frame: landed ``x - cx`` against pixel centres.

    Unprojects every kept pixel twice, at ``(x - cx, y - cy)`` (the landed
    contract) and at ``(x + 0.5 - cx, y + 0.5 - cy)`` (AT1 SPEC 7.3), with the
    same depth, in metres; the frame must carry a scale. Returns the per-point
    shift's median, minimum and maximum beside the closed form at the median
    planar depth, ``0.5 * z_med * hypot(1/fx, 1/fy)``. ``resolved`` is always
    False: the convention is decision D-HD-04, not this module's.
    """
    _require_numpy("half_pixel_delta")
    frame = _frame(frame)
    if frame.metres_per_unit is None:
        raise ScaleRefused("metric scale is unknown")
    z, k = _camera_grid(frame, depth, keep)
    _, _, zz, landed = _unproject(frame, z, k, 0.0)
    if zz.size == 0:
        raise ContractError("keep selects no pixel")
    _, _, _, centres = _unproject(frame, z, k, 0.5)
    scale = frame.metres_per_unit
    shift = centres * scale - landed * scale
    delta = np.sqrt(shift[:, 0] * shift[:, 0] + shift[:, 1] * shift[:, 1] + shift[:, 2] * shift[:, 2])
    camera = frame.intrinsics
    z_med = float(np.median(zz * scale))
    return {
        "claim": "BLU-C-HD-01",
        "decision": "D-HD-04",
        "resolved": False,
        "convention_landed": CONVENTION_LANDED,
        "convention_alternative": CONVENTION_ALTERNATIVE,
        "grid": [camera.width, camera.height],
        "fx": camera.fx,
        "fy": camera.fy,
        "metres_per_unit": scale,
        "points": int(zz.size),
        "median_depth_m": _f(z_med),
        "delta_at_median_depth_m": _f(0.5 * z_med * math.hypot(1.0 / camera.fx, 1.0 / camera.fy)),
        "delta_at_median_depth_axis_m": [_f(0.5 * z_med / camera.fx), _f(0.5 * z_med / camera.fy)],
        "measured_delta_m": {"median": _f(np.median(delta)), "max": _f(delta.max()), "min": _f(delta.min())},
    }
