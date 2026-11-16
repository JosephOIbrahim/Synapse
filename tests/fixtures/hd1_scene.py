"""HD1 analytic scene: one posed RGBD frame whose answers are known (SPEC section 3).

A pure numpy renderer for wave HD1, the physical frame. It draws a floor, a box
standing on it and a back wall, seen by a pinhole camera 1.5 m above the floor
and pitched down 20 degrees, and it hands back each variant's posed frame, its
decoded arrays and a truth record.

This module is the answer key, not code under test. It imports numpy, the
standard library and the dormant contract (``atlas_contracts``) only. It never
imports an HD1 module, pytest or Houdini, because the HD1 tests and the hython
probe both load it by file path. It writes no files and prints nothing.

    variant(name, width, height, *, pixel_offset)   "A".."D" or "NOFLOOR", cached
    no_floor_view(width, height)                    the wall-only view
    render(position, xyzw, width, height, *, ...)   planar depth and truth labels
    array_sha256(a)                                 digest of one decoded array
    fixture_digest(v)                               digest of one whole variant

Conventions, matching the landed contract:

* Scene truth is in metres with +Y up. That is the variant A frame.
* The camera is RUB (x right, y up, z back; it looks down its local -Z) and its
  pose is camera-to-world: an XYZW unit quaternion and a position.
* Depth is planar: the distance along the optical axis, not along the ray.
  Pixel (x, y) on the camera grid (row 0 at the top) looks along
  ``R * ((x + o - cx) / fx, -(y + o - cy) / fy, -1)``. The camera-space z of
  that ray is exactly -1, so the ray parameter of the nearest hit is the depth.
  ``o = 0.0`` is the landed convention (``x - cx``) and the default;
  ``o = 0.5`` renders through pixel centres, for the half-pixel measurement
  (D-HD-04) only.
* Rotations are written out per component. Nothing goes through a matrix
  product, so a render is bit-identical every time it runs in a process.
  Digests are per-run receipts and are never pinned: trig can differ by an ulp
  between platforms.

Variants share one scene. A is the plain path. B rotates the world by a 3
degree roll and a 5 degree pitch about the camera centre (ruling C-2). C writes
everything at 0.4 m per unit. D corrupts A's decoded arrays. NOFLOOR is a
camera 1 m from the wall that sees nothing else. Every frame carries
``metres_per_unit=None``, which is what a dormant frame carries; the truth
record says what the scale really is.

Without numpy every builder raises ``FixtureBlocked`` (status BLOCKED), the
spatial/path.py pattern for a missing numpy.
"""
from __future__ import annotations

from dataclasses import dataclass
import functools
import hashlib
import math

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - numpy ships with the dev extra and in CI
    np = None  # type: ignore
    NUMPY_AVAILABLE = False

from synapse.worldlabs.atlas_contracts import (
    AssetRef, CameraIntrinsics, CameraPose, PosedRGBDFrame, canonical,
)

STATUS_BLOCKED = "BLOCKED"

FIXTURE_VERSION = "hd1-scene-v1"
CHAIN_GRID, CROSS_GRID = (1280, 720), (160, 90)       # (width, height)
LABELS = {"floor": 1, "box_top": 2, "box_front": 3, "box_side": 4, "wall": 5}
NO_SURFACE_LABEL = 0                                   # render() only: a ray that hits nothing
VARIANTS = ("A", "B", "C", "D")
NOFLOOR = "NOFLOOR"
PIXEL_OFFSETS = (0.0, 0.5)

# Scene truth, metres, +Y up: the variant A frame.
FLOOR_Y = 0.0
BOX_MIN = (-0.5, 0.0, -3.8)
BOX_MAX = (0.5, 0.75, -2.8)
WALL_Z = -6.0
CAMERA_POSITION_M = (0.0, 1.5, 0.0)
CAMERA_PITCH_DEG = -20.0              # about +X; negative looks down
FOCAL_PX_PER_1280 = 1000.0            # fx = fy = 1000 * width / 1280, cx = width / 2, cy = height / 2
EYE_HEIGHT_M = 1.5                    # declared input to derived:camera-height
COLOURS = {"floor": (128, 128, 128), "box": (200, 120, 40), "wall": (60, 90, 160)}

# Variant B: W = Rz(roll) * Rx(pitch), active, column vectors, pitch first.
# p_B = W (p_A - pivot) + pivot, with the pivot at the camera centre (ruling C-2).
B_ROLL_DEG = 3.0
B_PITCH_DEG = 5.0
B_PIVOT_M = CAMERA_POSITION_M

# Variant C: units = metres / 0.4.
C_METRES_PER_UNIT = 0.4

# Variant D: four corruptions of A's decoded arrays. Pixel bounds are given at
# 1280x720 and scale by width / 1280 (rows too), half-open, floor-divided.
D_NAN_ROWS, D_NAN_COLS = (600, 632), (1000, 1032)
D_BIG_ROWS, D_BIG_COLS = (600, 632), (200, 232)
D_BIG_VALUE = 1.0e5                   # finite, above the half-float ceiling 65504
D_JUMP_REL = 0.10                     # a depth discontinuity: |dz| > 0.10 * min(z, z_n)
D_LOW_CONFIDENCE = 0.2
D_BAND_RADIUS = 2                     # Chebyshev distance of the low-confidence band (ruling: depth edges)

# NOFLOOR: 1 m from the wall, level, so the whole image is wall.
NOFLOOR_POSITION_M = (0.0, 1.5, -5.0)
NOFLOOR_XYZW = (0.0, 0.0, 0.0, 1.0)

# Drop sites (SPEC section 7), in the A frame. The release point is the sphere
# centre 0.5 m above the surface point along the final +Y (ruling: the centre).
SPHERE_RADIUS_M = 0.1
RELEASE_LIFT_M = 0.5
SITE_SPECS = (
    ("S1", "open floor in view", (-1.3, 0.0, -3.3), "rest"),
    ("S2", "top of the box", (0.0, 0.75, -3.3), "rest"),
    ("S3", "floor behind the box, never observed", (0.0, 0.0, -4.6), "fall_through"),
)
# derived:reference-length: the box's top-front corners, 1.0 m apart.
REFERENCE_PAIR_M = ((-0.5, 0.75, -2.8), (0.5, 0.75, -2.8), 1.0)

_IDENTITY_XYZW = (0.0, 0.0, 0.0, 1.0)
_UP = (0.0, 1.0, 0.0)


class FixtureBlocked(RuntimeError):
    """Status BLOCKED: the analytic fixture needs numpy."""


def _require_numpy():
    if not NUMPY_AVAILABLE:
        raise FixtureBlocked("BLOCKED: the hd1 fixture requires numpy")


def _f(value):
    """A plain Python float with -0.0 folded to 0.0, so canonical JSON is stable."""
    return float(value) + 0.0


def _vec(values):
    return tuple(_f(v) for v in values)


# ---------------------------------------------------------------------------
# Quaternion and rotation helpers (XYZW, Hamilton, active, column vectors)
# ---------------------------------------------------------------------------

def _qmul(a, b):
    """Hamilton product a (x) b, XYZW."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + bw * ax + (ay * bz - az * by),
            aw * by + bw * ay + (az * bx - ax * bz),
            aw * bz + bw * az + (ax * by - ay * bx),
            aw * bw - (ax * bx + ay * by + az * bz))


def _qmat(q):
    """Unit XYZW quaternion -> 3x3 rotation, as nested tuples."""
    x, y, z, w = q
    return ((1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)))


def _apply(m, x, y, z):
    """m * (x, y, z) for Python floats or numpy arrays, written out per component."""
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z,
            m[1][0] * x + m[1][1] * y + m[1][2] * z,
            m[2][0] * x + m[2][1] * y + m[2][2] * z)


def _qangle_deg(q):
    """Rotation angle of a unit quaternion, sign-invariant, in degrees."""
    x, y, z, w = q
    return math.degrees(2.0 * math.atan2(math.sqrt(x * x + y * y + z * z), abs(w)))


def _camera_xyzw_a():
    """Variant A's camera-to-world rotation, Rx(-20 deg). y and z are literal 0.0."""
    half = math.radians(CAMERA_PITCH_DEG) / 2.0
    return (math.sin(half), 0.0, 0.0, math.cos(half))


def _world_tilt_xyzw():
    """Variant B's world rotation q_W = q_z(3 deg) (x) q_x(5 deg): pitch first, then roll."""
    roll, pitch = math.radians(B_ROLL_DEG) / 2.0, math.radians(B_PITCH_DEG) / 2.0
    q_roll = (0.0, 0.0, math.sin(roll), math.cos(roll))
    q_pitch = (math.sin(pitch), 0.0, 0.0, math.cos(pitch))
    return _qmul(q_roll, q_pitch)


def _smallest_rotation_to_up(normal):
    """The smallest rotation taking a unit normal to +Y, from its axis and angle.

    The axis is n x Y = (-n_z, 0, n_x), so the rotation has no yaw (y is 0.0).
    """
    nx, ny, nz = normal
    sine = math.hypot(nz, nx)
    if sine == 0.0:
        if ny > 0.0:
            return _IDENTITY_XYZW
        raise ValueError("a downward normal has no unique smallest rotation to +Y")
    angle = math.atan2(sine, ny)
    k = math.sin(angle / 2.0) / sine
    return (_f(-nz * k), 0.0, _f(nx * k), _f(math.cos(angle / 2.0)))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _check_grid(width, height):
    for value in (width, height):
        if type(value) is not int or value <= 0:
            raise ValueError("grid width and height must be positive Python ints")


def _check_offset(pixel_offset):
    if type(pixel_offset) not in (int, float) or pixel_offset not in PIXEL_OFFSETS:
        raise ValueError("pixel_offset must be 0.0 (landed: x - cx) or 0.5 (pixel centres)")


def _focal(width):
    return FOCAL_PX_PER_1280 * width / 1280.0


def _rays(camera_xyzw, width, height, pixel_offset):
    """World ray directions (Dx, Dy, Dz), each (H, W), with unit camera-space depth."""
    f = _focal(width)
    cx, cy = width / 2.0, height / 2.0
    u = (np.arange(width, dtype=np.float64) + pixel_offset - cx) / f
    v = -(np.arange(height, dtype=np.float64) + pixel_offset - cy) / f
    dx = np.broadcast_to(u[None, :], (height, width))
    dy = np.broadcast_to(v[:, None], (height, width))
    dz = np.full((height, width), -1.0)
    return _apply(_qmat(camera_xyzw), dx, dy, dz)


def _intersect(position, rays):
    """Exact nearest hit along each ray: (planar depth, int8 label)."""
    px, py, pz = (float(p) for p in position)
    dx, dy, dz = rays
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        t_floor = np.where(dy < 0.0, (FLOOR_Y - py) / dy, np.inf)
        t_wall = np.where(dz < 0.0, (WALL_Z - pz) / dz, np.inf)
        near, far = [], []
        for d, p, lo, hi in ((dx, px, BOX_MIN[0], BOX_MAX[0]),
                             (dy, py, BOX_MIN[1], BOX_MAX[1]),
                             (dz, pz, BOX_MIN[2], BOX_MAX[2])):
            t1 = (lo - p) / d
            t2 = (hi - p) / d
            near.append(np.minimum(t1, t2))
            far.append(np.maximum(t1, t2))
        near = np.stack(near, axis=-1)
        t_near = np.nanmax(near, axis=-1)
        t_far = np.nanmin(np.stack(far, axis=-1), axis=-1)
        hit = (t_near <= t_far) & (t_near > 0.0)
        t_box = np.where(hit, t_near, np.inf)
        depth = np.minimum(np.minimum(t_floor, t_wall), t_box)
        # Which slab set t_near: x -> side, y -> top, z -> front (named for the fixture's cameras).
        slab = np.argmax(np.where(np.isnan(near), -np.inf, near), axis=-1)
        box_label = np.array([LABELS["box_side"], LABELS["box_top"], LABELS["box_front"]], dtype=np.int8)[slab]
        labels = np.where(t_box <= np.minimum(t_floor, t_wall), box_label,
                          np.where(t_floor <= t_wall, LABELS["floor"], LABELS["wall"])).astype(np.int8)
        labels = np.where(np.isfinite(depth), labels, NO_SURFACE_LABEL).astype(np.int8)
    return depth, labels


def render(camera_position, camera_xyzw, width, height, *, pixel_offset=0.0):
    """Planar depth and truth labels of the scene, seen from a RUB camera-to-world pose.

    Returns ``(depth, labels)``: ``(H, W)`` float64 on the camera grid (row 0 at the
    top), and ``(H, W)`` int8 labels from ``LABELS`` (0 where a ray hits nothing,
    which never happens in a fixture variant). The scene is in metres.
    """
    _require_numpy()
    _check_grid(width, height)
    if type(pixel_offset) not in (int, float) or not math.isfinite(pixel_offset):
        raise ValueError("pixel_offset must be a finite real number")
    q = tuple(float(v) for v in camera_xyzw)
    if len(q) != 4 or abs(sum(v * v for v in q) - 1.0) > 1e-9:
        raise ValueError("camera_xyzw must be a unit XYZW quaternion")
    position = tuple(float(v) for v in camera_position)
    if len(position) != 3:
        raise ValueError("camera_position must have three components")
    return _intersect(position, _rays(q, width, height, float(pixel_offset)))


def _colour(labels):
    lut = np.zeros((6, 3), dtype=np.uint8)
    lut[LABELS["floor"]] = COLOURS["floor"]
    for name in ("box_top", "box_front", "box_side"):
        lut[LABELS[name]] = COLOURS["box"]
    lut[LABELS["wall"]] = COLOURS["wall"]
    return lut[labels]


# ---------------------------------------------------------------------------
# Variant D's corruptions, built on clean A
# ---------------------------------------------------------------------------

def _scaled(value, width):
    return (value * width) // 1280


def _patch(shape, rows, cols, width):
    mask = np.zeros(shape, dtype=bool)
    mask[_scaled(rows[0], width):_scaled(rows[1], width), _scaled(cols[0], width):_scaled(cols[1], width)] = True
    return mask


def _neighbour_max(z):
    """Largest 4-neighbour depth per pixel; -inf where a pixel has none. No wrap-around."""
    out = np.full(z.shape, -np.inf)
    np.maximum(out[1:, :], z[:-1, :], out=out[1:, :])
    np.maximum(out[:-1, :], z[1:, :], out=out[:-1, :])
    np.maximum(out[:, 1:], z[:, :-1], out=out[:, 1:])
    np.maximum(out[:, :-1], z[:, 1:], out=out[:, :-1])
    return out


def _jump_pixels(z, rel):
    """Both pixels of every 4-neighbour pair with |z_a - z_b| > rel * min(z_a, z_b)."""
    flags = np.zeros(z.shape, dtype=bool)
    vertical = np.abs(z[:-1, :] - z[1:, :]) > rel * np.minimum(z[:-1, :], z[1:, :])
    flags[:-1, :] |= vertical
    flags[1:, :] |= vertical
    horizontal = np.abs(z[:, :-1] - z[:, 1:]) > rel * np.minimum(z[:, :-1], z[:, 1:])
    flags[:, :-1] |= horizontal
    flags[:, 1:] |= horizontal
    return flags


def _dilate(mask, radius):
    """Every pixel within Chebyshev distance ``radius`` of a set pixel. No wrap-around."""
    out = np.zeros_like(mask)
    rows, cols = mask.shape
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out[max(dy, 0):rows + min(dy, 0), max(dx, 0):cols + min(dx, 0)] |= \
                mask[max(-dy, 0):rows + min(-dy, 0), max(-dx, 0):cols + min(-dx, 0)]
    return out


def _corrupt(clean, width):
    """(depth, confidence, masks) for variant D, from A's clean depth."""
    shape = clean.shape
    nan_mask = _patch(shape, D_NAN_ROWS, D_NAN_COLS, width)
    big_mask = _patch(shape, D_BIG_ROWS, D_BIG_COLS, width)
    far = _neighbour_max(clean)
    # Mixed depths: the near side of a jump of more than 10% takes the midpoint of
    # itself and its farthest 4-neighbour, as a depth sensor blends a silhouette.
    mixed = (far - clean) > D_JUMP_REL * clean
    band = _dilate(_jump_pixels(clean, D_JUMP_REL), D_BAND_RADIUS)
    depth = clean.copy()
    depth[mixed] = (clean[mixed] + far[mixed]) / 2.0
    depth[nan_mask] = np.nan
    depth[big_mask] = D_BIG_VALUE
    confidence = np.where(band, D_LOW_CONFIDENCE, 1.0)
    masks = {"nan": nan_mask, "above_half_max": big_mask, "mixed": mixed, "low_confidence": band}
    for mask in masks.values():
        mask.setflags(write=False)
    return depth, confidence, masks


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class Site:
    """One drop site of the rest test (SPEC section 7)."""

    name: str                       # "S1" | "S2" | "S3"
    where: str
    surface_raw: tuple              # the variant's raw frame and units
    release_raw: tuple              # sphere centre at release, raw frame and units
    surface_final_m: tuple          # after the truth chain: scale, then level, then ground
    release_final_m: tuple          # surface_final_m + (0, 0.5, 0): the sphere centre
    rest_height_m: float | None     # 0.10, 0.85, None
    expect: str                     # "rest" | "fall_through"
    sphere_radius_m: float = SPHERE_RADIUS_M

    def as_dict(self) -> dict:
        return {"name": self.name, "where": self.where, "surface_raw": list(self.surface_raw),
                "release_raw": list(self.release_raw), "surface_final_m": list(self.surface_final_m),
                "release_final_m": list(self.release_final_m), "rest_height_m": self.rest_height_m,
                "expect": self.expect, "sphere_radius_m": self.sphere_radius_m}


@dataclass(frozen=True, eq=False)
class Truth:
    """What the chain should recover from one variant. The frame itself carries no scale."""

    variant: str
    grid: tuple                     # (width, height)
    pixel_offset: float             # 0.0 (landed) or 0.5 (pixel centres)
    metres_per_unit: float          # 1.0, or 0.4 for C
    declared_eye_height_m: float    # 1.5: the input to derived:camera-height
    camera_height_units: float      # the camera's height above the floor, raw units
    floor_normal: tuple             # unit, raw frame
    level_xyzw: tuple               # the smallest rotation floor_normal -> +Y
    tilt_deg: float
    world_tilt_xyzw: tuple          # q_W for B, identity otherwise
    world_tilt_pivot: tuple | None  # (0, 1.5, 0) for B, None otherwise
    yaw_twist_deg: float            # the pure yaw left in level (x) q_W; 0.0 except B
    floor_height_units: float       # floor y after levelling, before grounding (= -d in n.p + d = 0)
    ground_offset_units: float      # = -floor_height_units
    sites: tuple                    # (S1, S2, S3); () for NOFLOOR
    reference_pair: tuple | None    # (a_raw, b_raw, known_length_m); None for NOFLOOR
    corruption: dict | None         # D only: {"nan", "above_half_max", "mixed", "low_confidence"} -> (H, W) bool
    params_sha256: str              # canonical JSON of the declared geometry (machine-independent)

    def as_dict(self) -> dict:
        """JSON-safe: masks become pixel counts."""
        corruption = None
        if self.corruption is not None:
            corruption = {key: int(mask.sum()) for key, mask in sorted(self.corruption.items())}
        pair = None
        if self.reference_pair is not None:
            pair = [list(self.reference_pair[0]), list(self.reference_pair[1]), self.reference_pair[2]]
        return {"variant": self.variant, "grid": list(self.grid), "pixel_offset": self.pixel_offset,
                "metres_per_unit": self.metres_per_unit, "declared_eye_height_m": self.declared_eye_height_m,
                "camera_height_units": self.camera_height_units, "floor_normal": list(self.floor_normal),
                "level_xyzw": list(self.level_xyzw), "tilt_deg": self.tilt_deg,
                "world_tilt_xyzw": list(self.world_tilt_xyzw),
                "world_tilt_pivot": None if self.world_tilt_pivot is None else list(self.world_tilt_pivot),
                "yaw_twist_deg": self.yaw_twist_deg, "floor_height_units": self.floor_height_units,
                "ground_offset_units": self.ground_offset_units, "sites": [s.as_dict() for s in self.sites],
                "reference_pair": pair, "corruption_pixels": corruption, "params_sha256": self.params_sha256}


@dataclass(frozen=True, eq=False)
class Variant:
    """One fixture frame: the posed frame, its decoded arrays and its truth."""

    name: str                       # "A".."D", or "NOFLOOR"
    frame: PosedRGBDFrame           # metres_per_unit None
    depth: np.ndarray               # (H, W) float64, read-only, top_down
    confidence: np.ndarray          # (H, W) float64 in [0, 1], read-only (ones except D)
    colour: np.ndarray              # (H, W, 3) uint8, read-only
    labels: np.ndarray              # (H, W) int8 truth labels: tests only, never fed to the chain
    truth: Truth

    def truth_points(self) -> np.ndarray:
        """(H, W, 3) exact hits ``C + t * D`` in the raw frame and units, on demand.

        For D these are the scene's hits, not the corrupted buffer's.
        """
        _require_numpy()
        width, height = self.truth.grid
        pose = self.frame.pose
        depth = self.depth
        if self.truth.corruption is not None:
            depth, _ = render(pose.position, pose.quaternion_xyzw, width, height,
                              pixel_offset=self.truth.pixel_offset)
        dx, dy, dz = _rays(pose.quaternion_xyzw, width, height, float(self.truth.pixel_offset))
        px, py, pz = pose.position
        return np.stack((px + depth * dx, py + depth * dy, pz + depth * dz), axis=-1)


# ---------------------------------------------------------------------------
# Truth construction
# ---------------------------------------------------------------------------

def _scene_declaration():
    return {
        "floor_y": FLOOR_Y, "box_min": list(BOX_MIN), "box_max": list(BOX_MAX), "wall_z": WALL_Z,
        "camera_position_m": list(CAMERA_POSITION_M), "camera_pitch_deg": CAMERA_PITCH_DEG,
        "camera_axes": "rub", "camera_to_world": True, "depth": "planar",
        "focal_px_per_1280": FOCAL_PX_PER_1280, "principal_point": "width/2, height/2",
        "eye_height_m": EYE_HEIGHT_M, "labels": dict(LABELS),
        "colours": {key: list(value) for key, value in COLOURS.items()},
        "sites": [[name, where, list(point), expect] for name, where, point, expect in SITE_SPECS],
        "sphere_radius_m": SPHERE_RADIUS_M, "release_lift_m": RELEASE_LIFT_M,
        "reference_pair_m": [list(REFERENCE_PAIR_M[0]), list(REFERENCE_PAIR_M[1]), REFERENCE_PAIR_M[2]],
    }


def _variant_declaration(name):
    if name == "B":
        return {"world_roll_deg": B_ROLL_DEG, "world_pitch_deg": B_PITCH_DEG,
                "composition": "Rz(roll) Rx(pitch), active, pitch first", "pivot_m": list(B_PIVOT_M)}
    if name == "C":
        return {"metres_per_unit": C_METRES_PER_UNIT}
    if name == "D":
        return {"nan_rows_cols_1280": [list(D_NAN_ROWS), list(D_NAN_COLS)],
                "big_rows_cols_1280": [list(D_BIG_ROWS), list(D_BIG_COLS)], "big_value": D_BIG_VALUE,
                "jump_rel": D_JUMP_REL, "low_confidence": D_LOW_CONFIDENCE, "band_radius": D_BAND_RADIUS,
                "band": "depth edges, Chebyshev", "mixed": "midpoint with the farthest 4-neighbour"}
    if name == NOFLOOR:
        return {"camera_position_m": list(NOFLOOR_POSITION_M), "camera_xyzw": list(NOFLOOR_XYZW)}
    return {}


def _params_sha256(name, width, height, pixel_offset):
    body = {"version": FIXTURE_VERSION, "variant": name, "grid": [width, height],
            "pixel_offset": float(pixel_offset), "scene": _scene_declaration(),
            "declared": _variant_declaration(name)}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def _to_raw(name, point):
    """An A-frame point (metres) in a variant's raw frame and units."""
    if name == "B":
        q_w = _world_tilt_xyzw()
        c = B_PIVOT_M
        rotated = _apply(_qmat(q_w), point[0] - c[0], point[1] - c[1], point[2] - c[2])
        return _vec(rotated[i] + c[i] for i in range(3))
    if name == "C":
        return _vec(v / C_METRES_PER_UNIT for v in point)
    return _vec(point)


def _truth_chain(raw, metres_per_unit, level_xyzw, ground_offset_units):
    """Scale, then level, then ground: the SPEC's order of application."""
    scaled = tuple(metres_per_unit * v for v in raw)
    levelled = _apply(_qmat(level_xyzw), *scaled)
    return _vec((levelled[0], levelled[1] + metres_per_unit * ground_offset_units, levelled[2]))


def _sites(name, metres_per_unit, level_xyzw, ground_offset_units):
    out = []
    for site, where, surface_a, expect in SITE_SPECS:
        release_a = (surface_a[0], surface_a[1] + RELEASE_LIFT_M, surface_a[2])
        surface_final = _truth_chain(_to_raw(name, surface_a), metres_per_unit, level_xyzw, ground_offset_units)
        out.append(Site(
            name=site, where=where,
            surface_raw=_to_raw(name, surface_a),
            release_raw=_to_raw(name, release_a),
            surface_final_m=surface_final,
            release_final_m=_vec((surface_final[0], surface_final[1] + RELEASE_LIFT_M, surface_final[2])),
            rest_height_m=_f(surface_a[1] + SPHERE_RADIUS_M) if expect == "rest" else None,
            expect=expect,
        ))
    return tuple(out)


def _truth(name, width, height, pixel_offset, corruption):
    metres_per_unit = C_METRES_PER_UNIT if name == "C" else 1.0
    # The camera's declared height above the floor, in metres; B's pivot is the camera, so B keeps it.
    camera_height_m = (NOFLOOR_POSITION_M if name == NOFLOOR else CAMERA_POSITION_M)[1] - FLOOR_Y
    world_tilt, pivot = _IDENTITY_XYZW, None
    normal, offset = _UP, 0.0                      # floor plane n.p + d = 0 in the raw frame
    if name == "B":
        world_tilt, pivot = _world_tilt_xyzw(), B_PIVOT_M
        m = _qmat(world_tilt)
        normal = _vec((m[0][1], m[1][1], m[2][1]))  # W applied to +Y
        # The A floor y = 0 becomes n.(p - c) + c_y = 0, so d = c_y - n.c.
        offset = pivot[1] - (normal[0] * pivot[0] + normal[1] * pivot[1] + normal[2] * pivot[2])
    level = _smallest_rotation_to_up(normal)
    twist = _qangle_deg(_qmul(level, world_tilt)) if name == "B" else 0.0
    sites, pair = (), None
    if name != NOFLOOR:
        sites = _sites(name, metres_per_unit, level, offset)
        pair = (_to_raw(name, REFERENCE_PAIR_M[0]), _to_raw(name, REFERENCE_PAIR_M[1]), _f(REFERENCE_PAIR_M[2]))
    return Truth(
        variant=name, grid=(width, height), pixel_offset=_f(pixel_offset), metres_per_unit=_f(metres_per_unit),
        declared_eye_height_m=_f(EYE_HEIGHT_M),
        camera_height_units=_f(camera_height_m / metres_per_unit),
        floor_normal=_vec(normal), level_xyzw=_vec(level),
        tilt_deg=_f(math.degrees(math.atan2(math.hypot(normal[0], normal[2]), normal[1]))),
        world_tilt_xyzw=_vec(world_tilt), world_tilt_pivot=None if pivot is None else _vec(pivot),
        yaw_twist_deg=_f(twist), floor_height_units=_f(-offset), ground_offset_units=_f(offset),
        sites=sites, reference_pair=pair, corruption=corruption,
        params_sha256=_params_sha256(name, width, height, pixel_offset),
    )


def array_sha256(a) -> str:
    """sha256 over ``dtype.str | shape |`` and the C-contiguous bytes of one decoded array.

    Fixture frames digest decoded arrays, not EXR or PNG file bytes: no file exists.
    """
    _require_numpy()
    arr = np.ascontiguousarray(a)
    digest = hashlib.sha256()
    digest.update(("%s|%s|" % (arr.dtype.str, ",".join(str(int(n)) for n in arr.shape))).encode("ascii"))
    digest.update(arr.tobytes(order="C"))
    return digest.hexdigest()


def _frame(name, width, height, pixel_offset, position, xyzw, depth, confidence, colour):
    frame_id = "SYNTHETIC-hd1-%s-%dx%d%s" % (name, width, height, "-centres" if pixel_offset else "")
    f = _focal(width)
    return PosedRGBDFrame(
        frame_id,
        AssetRef(frame_id + "-rgb", array_sha256(colour), "image/png"),
        AssetRef(frame_id + "-depth", array_sha256(depth), "image/x-exr"),
        AssetRef(frame_id + "-confidence", array_sha256(confidence), "image/png"),
        CameraIntrinsics(int(width), int(height), float(f), float(f), float(width / 2.0), float(height / 2.0)),
        CameraPose(_vec(position), _vec(xyzw), "rub", "SYNTHETIC-hd1-world-" + name),
        "linear_exr_half", "top_down", metres_per_unit=None,
    )


@functools.lru_cache(maxsize=None, typed=True)
def variant(name: str, width: int = 1280, height: int = 720, *, pixel_offset: float = 0.0) -> Variant:
    """One fixture variant, cached. Arrays are read-only so the cache is safe to share.

    ``variant.__wrapped__`` renders afresh: B, C and D re-render A's scene rather than
    reading A from the cache, so two uncached calls are two independent renders.
    The cache is typed, so ``variant("A", 160.0, 90)`` is refused rather than served
    the cached ``variant("A", 160, 90)``.
    """
    _require_numpy()
    if name not in VARIANTS and name != NOFLOOR:
        raise ValueError("variant name must be one of A, B, C, D or NOFLOOR")
    _check_grid(width, height)
    _check_offset(pixel_offset)
    offset = float(pixel_offset)
    if name == NOFLOOR:
        position, xyzw = NOFLOOR_POSITION_M, NOFLOOR_XYZW
    else:
        position, xyzw = CAMERA_POSITION_M, _camera_xyzw_a()
    depth, labels = render(position, xyzw, width, height, pixel_offset=offset)
    colour = _colour(labels)
    confidence = np.ones((height, width), dtype=np.float64)
    corruption = None
    if name == "B":
        xyzw = _qmul(_world_tilt_xyzw(), xyzw)      # q_B = q_W (x) q_A; position stays at the pivot
    elif name == "C":
        depth = depth / C_METRES_PER_UNIT
        position = tuple(p / C_METRES_PER_UNIT for p in CAMERA_POSITION_M)
    elif name == "D":
        depth, confidence, corruption = _corrupt(depth, width)
    for array in (depth, confidence, colour, labels):
        array.setflags(write=False)
    frame = _frame(name, width, height, offset, position, xyzw, depth, confidence, colour)
    truth = _truth(name, width, height, offset, corruption)
    return Variant(name, frame, depth, confidence, colour, labels, truth)


def no_floor_view(width: int = 160, height: int = 90) -> Variant:
    """The wall-only view: camera (0, 1.5, -5.0), identity quaternion, 1.0 m from the wall.

    Its truth keeps the scene's floor (normal +Y, camera 1.5 m above it), but no site
    and no reference pair: none of them is in view.
    """
    return variant(NOFLOOR, width, height)


def fixture_digest(v: Variant) -> str:
    """sha256 of canonical JSON {version, variant, grid, pixel_offset, params, array digests}.

    A per-run receipt, never a pinned literal.
    """
    _require_numpy()
    body = {"version": FIXTURE_VERSION, "variant": v.name, "grid": list(v.truth.grid),
            "pixel_offset": v.truth.pixel_offset, "params": v.truth.params_sha256,
            "arrays": {"depth": array_sha256(v.depth), "confidence": array_sha256(v.confidence),
                       "colour": array_sha256(v.colour), "labels": array_sha256(v.labels)}}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
