"""HD1 floor fit, levelling rotation and ground offset (SPEC 5.1, 5.2).

Pure numpy over plain arrays: the fields of a raw (unscaled) point cloud. No
hou, no pxr and no I/O, mirroring spatial/path.py; importing this module
registers nothing.

    fit_floor(points, rows, depth, ...)   RANSAC floor plane in raw units, with
                                          a fixed seed so runs repeat
    smallest_rotation_to_up(normal)       the levelling rotation, XYZW, no yaw
    rotation_matrix(xyzw)                 the 3x3 matrix of a unit quaternion
    normal_angle_deg(a, b)                angle between two directions
    quaternion_angle_deg(a, b)            angle between two rotations
    ground_offset(scale_value, floor)     the importer's lift, in metres

Order of estimation (SPEC 5): the floor is fitted first, in raw units, because
both the levelling rotation and the camera-height scale are read off the fit.
Order of application: scale, then level, then ground. The full transform is
``p_final = R(level) * (s * p_raw) + (0, s * d, 0)`` for the fitted plane
``n.p + d = 0``.

The fit. Candidates are the points on the bottom ``rows_fraction`` of the
camera grid's rows (SPEC 5.1). The inlier band is ``inlier_rel`` of the
candidates' median planar depth, so the fit is scale-free. RANSAC keeps the
first best three-point plane, two SVD refits of the inliers follow, and the
normal is oriented to +Y (the world-up prior). Below ``min_inlier_fraction`` of
inliers the floor is UNKNOWN (the SPEC's rule). A plane tilted more than
``max_tilt_deg`` from +Y is UNKNOWN too: a wall-only view is a perfect plane,
so the SPEC's rule alone would call it a floor. That gate is HD1's own
(conflict C-1, ruled by the owner). It approximately mirrors the importer's
floor cosine 0.866, which is cos(30.0029 deg), so a plane tilted between 30.0
and 30.0029 degrees is floor to the importer and UNKNOWN here. An UNKNOWN fit
carries its diagnostics (normal, tilt, fraction, residual, counts) but never a
levelling rotation, camera height or floor height, so nothing downstream can
mistake it for a floor.

``ground_offset`` reuses ``importer.ground_transform`` with ``y_down=False``
for the scale and the lift. That function has no levelling slot (gap GAP-1),
so the levelling rotation is HD1's own, recorded as an XYZW quaternion; the
importer is not changed.

Without numpy, ``fit_floor`` reports BLOCKED with a reason and
``rotation_matrix`` raises PhysicalBlocked, the spatial/path.py pattern. Error
messages and reasons are public-safe: they never echo an input value.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numbers
from typing import Any, Dict, Optional, Tuple

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - numpy is a dev extra; without it the fit reports BLOCKED
    np = None  # type: ignore
    NUMPY_AVAILABLE = False

from ..atlas_contracts import ContractError
from ..importer import ground_transform

STATUS_SUCCESS = "SUCCESS"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_BLOCKED = "BLOCKED"

FLOOR_ROWS_FRACTION = 0.25          # SPEC 5.1: the bottom 25% of the grid's rows
FLOOR_SEED = 20261114               # any fixed int; recorded in every fit
FLOOR_ITERATIONS = 256              # >= ln(1 - 0.999) / ln(1 - 0.3 ** 3) = 252.4
FLOOR_INLIER_REL = 0.01             # inlier band: 1% of the candidates' median planar depth
FLOOR_MIN_INLIER_FRACTION = 0.3     # SPEC 5.1: below this the floor is UNKNOWN
FLOOR_MAX_TILT_DEG = 30.0           # C-1, ruled by the owner; importer._FLOOR_NORMAL_COS = 0.866 is cos(30.0029 deg)
FLOOR_REFINE_PASSES = 2

_BLOCKED_REASON = "floor fitting requires numpy"
_NO_CANDIDATES = "no valid depth in the bottom rows (rows_fraction of the grid)"
_TOO_FEW = "fewer than 3 valid points in the bottom rows (rows_fraction of the grid)"
_DEGENERATE = "no non-degenerate plane sample"
_LOW_FRACTION = "inlier fraction below min_inlier_fraction"
_TOO_STEEP = "dominant plane is not floor-like: tilted beyond max_tilt_deg"
_IDENTITY_XYZW = (0.0, 0.0, 0.0, 1.0)


class PhysicalBlocked(RuntimeError):
    """Status BLOCKED: an HD1 array step needs numpy. The message starts 'BLOCKED: '."""


@dataclass(frozen=True)
class FloorFit:
    """One floor fit. Every field is a str, int, float, tuple or None, so == compares fits.

    ``normal`` is unit with ``n_y >= 0``, in the raw frame; ``offset`` is ``d`` in
    ``n.p + d = 0``, in raw units. ``camera_height`` is ``n.c + d`` (signed, raw
    units) and ``floor_height`` is ``-d``: the floor's y after levelling and
    before grounding. ``rms_over_median_depth`` is the inliers' RMS residual over
    the candidates' median planar depth. The thresholds the fit ran with are
    recorded beside the result.
    """

    status: str                                     # "SUCCESS" | "UNKNOWN" | "BLOCKED"
    reason: Optional[str]
    normal: Optional[Tuple[float, float, float]]
    offset: Optional[float]
    level_xyzw: Optional[Tuple[float, float, float, float]]
    tilt_deg: Optional[float]
    camera_height: Optional[float]
    floor_height: Optional[float]
    inlier_fraction: Optional[float]
    rms_over_median_depth: Optional[float]
    candidates: Optional[int]
    inliers: Optional[int]
    first_row: int
    grid_rows: int
    median_depth: Optional[float]
    inlier_band: Optional[float]
    seed: int
    iterations: int
    degenerate_samples: Optional[int]
    rows_fraction: float
    inlier_rel: float
    min_inlier_fraction: float
    max_tilt_deg: float

    def as_dict(self) -> Dict[str, Any]:
        """JSON-safe record of every field; tuples become lists."""
        out: Dict[str, Any] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            out[name] = list(value) if isinstance(value, tuple) else value
        return out


def _f(value) -> float:
    """A plain Python float with -0.0 folded to 0.0."""
    return float(value) + 0.0


def _real(value, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ContractError(message)
    number = float(value)
    if not math.isfinite(number):
        raise ContractError(message)
    return number


def _integer(value, message: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or int(value) < minimum:
        raise ContractError(message)
    return int(value)


def _vector(value, count: int, message: str) -> Tuple[float, ...]:
    try:
        items = tuple(value)
    except TypeError:
        raise ContractError(message) from None
    if len(items) != count:
        raise ContractError(message)
    return tuple(_real(item, message) for item in items)


def smallest_rotation_to_up(normal) -> Tuple[float, float, float, float]:
    """The smallest rotation taking ``normal`` to +Y, as a unit XYZW quaternion.

    ``q = normalize((-n_z, 0, n_x, 1 + n_y))``: the half-angle form of
    ``(n x Y, 1 + n.Y)``, stable for small angles. Its y component is exactly
    0.0, so the rotation carries no yaw. A normal pointing straight down has no
    unique smallest rotation and is refused. Pure Python.
    """
    nx, ny, nz = _vector(normal, 3, "normal must be three finite numbers")
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if not length > 0.0 or not math.isfinite(length):
        raise ContractError("normal must be a non-zero finite direction")
    nx, ny, nz = nx / length, ny / length, nz / length
    x, z, w = -nz, nx, 1.0 + ny
    norm = math.sqrt(x * x + z * z + w * w)
    if not norm > 0.0:
        raise ContractError("a downward normal has no unique smallest rotation to +Y")
    return (_f(x / norm), 0.0, _f(z / norm), _f(w / norm))


def rotation_matrix(xyzw):
    """The 3x3 rotation matrix (float64) of a unit XYZW quaternion; active, column vectors."""
    x, y, z, w = _vector(xyzw, 4, "quaternion must be four finite numbers")
    if abs(x * x + y * y + z * z + w * w - 1.0) > 1e-9:
        raise ContractError("unit XYZW quaternion required; no implicit normalization")
    if not NUMPY_AVAILABLE:
        raise PhysicalBlocked("BLOCKED: rotation_matrix requires numpy")
    return np.array([
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
        [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
        [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
    ], dtype=np.float64)


def normal_angle_deg(a, b) -> float:
    """Angle between two directions in degrees, ``atan2(|a x b|, a.b)``; scale-free. Pure Python."""
    ax, ay, az = _vector(a, 3, "directions must be three finite numbers")
    bx, by, bz = _vector(b, 3, "directions must be three finite numbers")
    cx, cy, cz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    return math.degrees(math.atan2(math.sqrt(cx * cx + cy * cy + cz * cz), ax * bx + ay * by + az * bz))


def quaternion_angle_deg(a, b) -> float:
    """Angle between two rotations in degrees, ``2 atan2(|vec(a b*)|, |w(a b*)|)``.

    Sign-invariant, since q and -q are the same rotation. Pure Python.
    """
    ax, ay, az, aw = _vector(a, 4, "quaternions must be four finite numbers")
    bx, by, bz, bw = _vector(b, 4, "quaternions must be four finite numbers")
    bx, by, bz = -bx, -by, -bz                      # conjugate of b
    x = aw * bx + bw * ax + (ay * bz - az * by)
    y = aw * by + bw * ay + (az * bx - ax * bz)
    z = aw * bz + bw * az + (ax * by - ay * bx)
    w = aw * bw - (ax * bx + ay * by + az * bz)
    return math.degrees(2.0 * math.atan2(math.sqrt(x * x + y * y + z * z), abs(w)))


def ground_offset(scale_value, floor: FloorFit) -> float:
    """The lift in metres that puts the fitted floor at y = 0 after scaling and levelling.

    Calls ``importer.ground_transform(s, floor.floor_height, y_down=False)`` and
    returns its translate y, ``-s * floor_height = s * d``. Its ``floor_raw`` is the
    floor's height after levelling, an extension of the importer's meaning
    (GAP-1). The scale is a value the caller already holds as a claim: there is
    no default.
    """
    s = _real(scale_value, "scale must be a finite number above 0")
    if not s > 0.0:
        raise ContractError("scale must be a finite number above 0")
    if not isinstance(floor, FloorFit) or floor.status != STATUS_SUCCESS:
        raise ContractError("floor is UNKNOWN")
    translate, rotate, uniform = ground_transform(s, floor.floor_height, y_down=False)
    if tuple(rotate) != (0.0, 0.0, 0.0) or uniform != s:
        raise ContractError("the importer's ground convention is not scale-then-lift")
    return _f(translate[1])


def _first_row(grid_rows: int, rows_fraction: float) -> int:
    """The first candidate row: grid_rows - ceil(grid_rows * rows_fraction)."""
    return grid_rows - int(math.ceil(grid_rows * rows_fraction))


def _arrays(points, rows, depth, grid_rows: int):
    try:
        p = np.asarray(points)
        r = np.asarray(rows)
        z = np.asarray(depth)
    except (TypeError, ValueError, OverflowError):
        raise ContractError("points, rows and depth must be numeric arrays") from None
    if p.dtype.kind not in "iuf" or p.ndim != 2 or p.shape[1] != 3:
        raise ContractError("points must be an (N, 3) array of real numbers")
    if r.dtype.kind not in "iu" or r.ndim != 1 or z.dtype.kind not in "iuf" or z.ndim != 1:
        raise ContractError("rows must be integers and depth real numbers, one per point")
    if not (p.shape[0] == r.shape[0] == z.shape[0]):
        raise ContractError("points, rows and depth must have one entry per point")
    p = np.asarray(p, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    if not np.isfinite(p).all():
        raise ContractError("points must be finite")
    if not (np.isfinite(z).all() and (z > 0.0).all()):
        raise ContractError("depth must be finite and above 0")
    if r.size and (int(r.min()) < 0 or int(r.max()) >= grid_rows):
        raise ContractError("rows must lie on the camera grid")
    return p, r, z


def fit_floor(points, rows, depth, *, grid_rows, camera_position, seed=FLOOR_SEED,
              iterations=FLOOR_ITERATIONS, inlier_rel=FLOOR_INLIER_REL,
              min_inlier_fraction=FLOOR_MIN_INLIER_FRACTION, max_tilt_deg=FLOOR_MAX_TILT_DEG,
              rows_fraction=FLOOR_ROWS_FRACTION) -> FloorFit:
    """Fit the floor plane among the points on the bottom rows of the camera grid.

    ``points`` is (N, 3) in the raw frame and units, ``rows`` (N,) camera-grid
    rows (0 at the top) and ``depth`` (N,) planar depth in raw units: the
    fields of a raw cloud. ``camera_position`` is in the same raw frame. Returns
    a FloorFit whose status is SUCCESS, UNKNOWN (with a reason) or BLOCKED.
    Inputs are never written.
    """
    grid_rows = _integer(grid_rows, "grid_rows must be a positive integer", 1)
    camera = _vector(camera_position, 3, "camera_position must be three finite numbers")
    seed = _integer(seed, "seed must be a non-negative integer", 0)
    iterations = _integer(iterations, "iterations must be a positive integer", 1)
    inlier_rel = _real(inlier_rel, "inlier_rel must be a finite number above 0")
    if not inlier_rel > 0.0:
        raise ContractError("inlier_rel must be a finite number above 0")
    min_fraction = _real(min_inlier_fraction, "min_inlier_fraction must be a finite number in [0, 1]")
    if not 0.0 <= min_fraction <= 1.0:
        raise ContractError("min_inlier_fraction must be a finite number in [0, 1]")
    max_tilt = _real(max_tilt_deg, "max_tilt_deg must be a finite number in (0, 90]")
    if not 0.0 < max_tilt <= 90.0:
        raise ContractError("max_tilt_deg must be a finite number in (0, 90]")
    fraction = _real(rows_fraction, "rows_fraction must be a finite number in (0, 1]")
    if not 0.0 < fraction <= 1.0:
        raise ContractError("rows_fraction must be a finite number in (0, 1]")
    first_row = _first_row(grid_rows, fraction)

    record: Dict[str, Any] = {
        "status": STATUS_UNKNOWN, "reason": None, "normal": None, "offset": None,
        "level_xyzw": None, "tilt_deg": None, "camera_height": None, "floor_height": None,
        "inlier_fraction": None, "rms_over_median_depth": None, "candidates": None,
        "inliers": None, "first_row": first_row, "grid_rows": grid_rows, "median_depth": None,
        "inlier_band": None, "seed": seed, "iterations": iterations, "degenerate_samples": None,
        "rows_fraction": fraction, "inlier_rel": inlier_rel, "min_inlier_fraction": min_fraction,
        "max_tilt_deg": max_tilt,
    }
    if not NUMPY_AVAILABLE:
        record.update(status=STATUS_BLOCKED, reason=_BLOCKED_REASON)
        return FloorFit(**record)

    p, r, z = _arrays(points, rows, depth, grid_rows)
    candidate = r >= first_row
    count = int(np.count_nonzero(candidate))
    record.update(candidates=count)
    if count == 0:
        record.update(reason=_NO_CANDIDATES)
        return FloorFit(**record)
    if count < 3:
        record.update(reason=_TOO_FEW)
        return FloorFit(**record)

    pc = p[candidate]
    xs, ys, zs = (np.ascontiguousarray(pc[:, axis]) for axis in range(3))
    median_depth = float(np.median(z[candidate]))
    band = inlier_rel * median_depth
    record.update(median_depth=_f(median_depth), inlier_band=_f(band))

    def residual(n, d):
        # Written out per component, not as a matrix product, so a fit repeats bit for bit.
        return xs * n[0] + ys * n[1] + zs * n[2] + d

    rng = np.random.default_rng(seed)
    tiny = 1e-12 * median_depth * median_depth
    best, best_count, degenerate = None, -1, 0
    for _ in range(iterations):
        i, j, k = (int(v) for v in rng.choice(count, 3, replace=False))
        a = pc[i]
        n = np.cross(pc[j] - a, pc[k] - a)
        length = math.sqrt(float(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]))
        if not length > tiny:
            degenerate += 1
            continue
        n = n / length
        d = -float(n[0] * a[0] + n[1] * a[1] + n[2] * a[2])
        inliers = int(np.count_nonzero(np.abs(residual(n, d)) <= band))
        if inliers > best_count:                    # strict: the first best wins, so ties repeat
            best, best_count = (n, d), inliers
    record.update(degenerate_samples=degenerate)
    if best is None:
        record.update(reason=_DEGENERATE)
        return FloorFit(**record)

    n, d = best
    for _ in range(FLOOR_REFINE_PASSES):
        inside = np.abs(residual(n, d)) <= band
        if int(np.count_nonzero(inside)) < 3:
            break
        q = pc[inside]
        centroid = q.mean(axis=0)
        n = np.linalg.svd(q - centroid, full_matrices=False)[2][2]
        n = n / math.sqrt(float(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]))
        d = -float(n[0] * centroid[0] + n[1] * centroid[1] + n[2] * centroid[2])
    if n[1] < 0.0:                                  # the world-up prior; n_y == 0 is left to the tilt gate
        n, d = -n, -d
    res = residual(n, d)
    inside = np.abs(res) <= band
    inliers = int(np.count_nonzero(inside))
    nx, ny, nz = (_f(v) for v in n)
    tilt = math.degrees(math.atan2(math.hypot(nx, nz), ny))
    rms = math.sqrt(float(np.mean(res[inside] ** 2))) / median_depth if inliers else None
    record.update(normal=(nx, ny, nz), offset=_f(d), tilt_deg=_f(tilt), inliers=inliers,
                  inlier_fraction=_f(inliers / count),
                  rms_over_median_depth=None if rms is None else _f(rms))
    if inliers / count < min_fraction:
        record.update(reason=_LOW_FRACTION)
        return FloorFit(**record)
    if tilt > max_tilt:
        record.update(reason=_TOO_STEEP)
        return FloorFit(**record)
    record.update(
        status=STATUS_SUCCESS,
        level_xyzw=smallest_rotation_to_up((nx, ny, nz)),
        camera_height=_f(nx * camera[0] + ny * camera[1] + nz * camera[2] + d),
        floor_height=_f(-d),
    )
    return FloorFit(**record)
