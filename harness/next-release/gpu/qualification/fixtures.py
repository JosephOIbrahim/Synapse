"""Deterministic parity fixtures for NR-GPU-QUALIFICATION: the R2 change-mask chain.

The parity input boundary (G0 receipt, section 11, slice 2) is two float32 (H, W) planes, so
every builder returns two 2-D float32 planes, which retina.t1._luma leaves unchanged. Each
builder returns (before, after, diff_threshold, morph_radius); the defaults are 0.02 and 1
(retina/qc_profiles.toml).

Status: the first seven ids are G0-PROPOSED (G0 receipt slice 2; report 02-ops section 7), not
ruled. nan_in_luma_plane is INFERENCE: a NaN in a luma plane is a CPU-versus-CUDA
threshold-parity hazard.

Design rule: every boundary or changed region is a solid patch at least 2r+1 pixels across, so a
pixel the GPU classifies differently survives the morphological open and reaches the mask
digest. A disagreement on an isolated pixel would be opened away and parity would pass
vacuously. The edge fixture also carries thin features (2 px strips, a corner square of side 2)
whose fate under the open depends on how the border is treated, so a border-handling
difference shows in the mask too.

check_relations() proves each fixture's stated relation exactly, in float32 NumPy arithmetic:
|after - before| is the rounded float32 subtraction followed by abs, which is what cv2.absdiff
computes on two float32 planes (INFERENCE: IEEE float32). Nothing here imports cv2.
"""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np

DEFAULT_DIFF_THRESHOLD = 0.02
DEFAULT_MORPH_RADIUS = 1

G0_PROPOSED = (
    "edges_and_corners",
    "diff_at_threshold",
    "diff_one_ulp_below",
    "diff_one_ulp_above",
    "non_contiguous_odd_stride",
    "size_not_multiple_of_16_or_32",
    "empty_change_set",
)
INFERENCE = ("nan_in_luma_plane",)
FIXTURE_IDS = G0_PROPOSED + INFERENCE
STATUS = {**{f: "G0-PROPOSED" for f in G0_PROPOSED}, **{f: "INFERENCE" for f in INFERENCE}}

FRAME = (64, 96)          # multiples of 32: only the size fixture has partial tiles
ODD_FRAME = (257, 263)    # neither side is a multiple of 16 or 32
VIEW = (37, 41)           # shape of the non-contiguous views
VIEW_STEP = (3, 5)        # odd element steps: every 3rd row, every 5th column
CHANGE = np.float32(0.5)  # an unambiguous change: exact in float32, far above any profile threshold

RELATIONS = {
    "edges_and_corners": (
        "changed patches (|diff| exactly 0.5) on all four corners and all four edges: corner squares "
        "of side 2, 3, 4 and 5, edge strips 2 and 3 px thick and edge patches 6 px thick; every other "
        "pixel has |diff| 0"),
    "diff_at_threshold": (
        "solid 6x6 patches whose float32 |diff| is exactly float32(diff_threshold), reached as 0 to t, "
        "t to 0 and t to 2t; one 8x8 patch with |diff| 0.5; every other pixel has |diff| 0"),
    "diff_one_ulp_below": (
        "as diff_at_threshold, with |diff| one float32 ulp below float32(diff_threshold) "
        "(numpy.nextafter toward -inf)"),
    "diff_one_ulp_above": (
        "as diff_at_threshold, with |diff| one float32 ulp above float32(diff_threshold) "
        "(numpy.nextafter toward +inf)"),
    "non_contiguous_odd_stride": (
        "both planes are non-contiguous 37x41 views with odd element strides (every 3rd row, every "
        "5th column); every base pixel outside the view differs by 0.5, so a stride error shows"),
    "size_not_multiple_of_16_or_32": (
        "a 257x263 frame, neither side a multiple of 16 or 32; changed patches straddle rows and "
        "columns 16 and 32 and reach the last row and column, past the last full 32 tile"),
    "empty_change_set": (
        "no pixel has |diff| above float32(diff_threshold): half the frame identical, half a "
        "checkerboard of plus or minus the largest power of two at most a quarter of the threshold"),
    "nan_in_luma_plane": (
        "solid NaN patches in before only, after only and both, one touching a changed 8x8 patch; "
        "NumPy's strict > leaves every NaN pixel unflagged"),
}


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def _texture(shape: tuple[int, int], seed: int) -> np.ndarray:
    """A deterministic background of multiples of 1/256 in [0.125, 0.359375], exact in float32,
    so adding CHANGE or a power-of-two step and subtracting again stays exact."""
    h, w = shape
    i = np.arange(h, dtype=np.int64)[:, None]
    j = np.arange(w, dtype=np.int64)[None, :]
    k = (7 * i + 13 * j + 31 * seed) % 61
    return k.astype(np.float32) / np.float32(256.0) + np.float32(0.125)


def _change(after: np.ndarray, before: np.ndarray, patches) -> None:
    for rows, cols in patches:
        after[rows, cols] = before[rows, cols] + CHANGE


def _t32(diff_threshold: float) -> np.float32:
    """The threshold as the CPU chain compares it: NumPy 2 casts the Python float to float32."""
    t32 = np.float32(diff_threshold)
    if not (np.isfinite(t32) and t32 > 0):
        raise ValueError(f"diff_threshold must be finite and positive, got {diff_threshold!r}")
    return t32


def ulp_below(diff_threshold: float) -> np.float32:
    return np.nextafter(_t32(diff_threshold), np.float32(-np.inf))


def ulp_above(diff_threshold: float) -> np.float32:
    return np.nextafter(_t32(diff_threshold), np.float32(np.inf))


def _boundary(target: np.float32, diff_threshold: float, morph_radius: int):
    before = _texture(FRAME, 1)
    after = before.copy()
    rows = slice(8, 14)
    before[rows, 8:14] = 0.0                       # 0 -> t
    after[rows, 8:14] = target
    before[rows, 24:30] = target                   # t -> 0
    after[rows, 24:30] = 0.0
    before[rows, 40:46] = target                   # t -> 2t, an exact non-zero subtraction
    after[rows, 40:46] = target * np.float32(2.0)
    _change(after, before, [(slice(40, 48), slice(60, 68))])   # clearly changed control
    return before, after, float(diff_threshold), int(morph_radius)


def _at_threshold(diff_threshold, morph_radius):
    return _boundary(_t32(diff_threshold), diff_threshold, morph_radius)


def _one_ulp_below(diff_threshold, morph_radius):
    return _boundary(ulp_below(diff_threshold), diff_threshold, morph_radius)


def _one_ulp_above(diff_threshold, morph_radius):
    return _boundary(ulp_above(diff_threshold), diff_threshold, morph_radius)


def _edges_and_corners(diff_threshold, morph_radius):
    before = _texture(FRAME, 2)
    after = before.copy()
    h, w = FRAME
    _change(after, before, [
        # corner squares of side 2, 3, 4 and 5
        (slice(0, 2), slice(0, 2)),
        (slice(0, 3), slice(w - 3, w)),
        (slice(h - 4, h), slice(0, 4)),
        (slice(h - 5, h), slice(w - 5, w)),
        # thin edge strips, 2 and 3 px thick
        (slice(0, 2), slice(20, 34)),
        (slice(h - 3, h), slice(20, 34)),
        (slice(12, 26), slice(0, 3)),
        (slice(12, 26), slice(w - 2, w)),
        # edge patches thick enough to survive the open whatever the border
        (slice(0, 6), slice(50, 60)),
        (slice(h - 6, h), slice(50, 60)),
        (slice(36, 46), slice(0, 6)),
        (slice(36, 46), slice(w - 6, w)),
    ])
    return before, after, float(diff_threshold), int(morph_radius)


def _non_contiguous_odd_stride(diff_threshold, morph_radius):
    (vh, vw), (sr, sc) = VIEW, VIEW_STEP
    base_before = _texture((vh * sr + 1, vw * sc + 2), 4)
    base_after = base_before + CHANGE           # every base pixel outside the view differs
    inner_before = _texture(VIEW, 5)
    inner_after = inner_before.copy()
    _change(inner_after, inner_before, [
        (slice(5, 12), slice(5, 12)),
        (slice(20, 26), slice(30, 38)),
        (slice(0, 4), slice(0, 6)),
        (slice(vh - 5, vh), slice(vw - 5, vw)),
    ])
    view = (slice(1, None, sr), slice(2, None, sc))
    base_before[view] = inner_before
    base_after[view] = inner_after
    return base_before[view], base_after[view], float(diff_threshold), int(morph_radius)


def _size_not_multiple_of_16_or_32(diff_threshold, morph_radius):
    before = _texture(ODD_FRAME, 3)
    after = before.copy()
    h, w = ODD_FRAME
    _change(after, before, [
        (slice(28, 37), slice(28, 37)),         # straddles row 32 and column 32
        (slice(12, 21), slice(250, 259)),       # straddles row 16 and column 256
        (slice(100, 108), slice(12, 21)),       # straddles column 16
        (slice(250, 257), slice(100, 110)),     # straddles row 256 and reaches the last row
        (slice(h - 6, h), slice(w - 6, w)),     # the last-row, last-column corner
        (slice(60, 80), slice(w - 3, w)),       # a 3 px strip on the last column
        (slice(h - 3, h), slice(150, 170)),     # a 3 px strip on the last row
        (slice(120, 140), slice(0, 2)),         # a 2 px strip on the first column
    ])
    return before, after, float(diff_threshold), int(morph_radius)


def _empty_change_set(diff_threshold, morph_radius):
    t32 = _t32(diff_threshold)
    step = np.float32(2.0 ** math.floor(math.log2(float(t32) / 4.0)))
    before = _texture(FRAME, 6)
    after = before.copy()
    h, w = FRAME
    i = np.arange(h)[:, None]
    j = np.arange(w // 2)[None, :]
    sign = np.where((i + j) % 2 == 0, np.float32(1.0), np.float32(-1.0)).astype(np.float32)
    after[:, : w // 2] = before[:, : w // 2] + sign * step
    return before, after, float(diff_threshold), int(morph_radius)


def _nan_in_luma_plane(diff_threshold, morph_radius):
    before = _texture(FRAME, 7)
    after = before.copy()
    nan = np.float32(np.nan)
    rows = slice(8, 14)
    before[rows, 8:14] = nan                     # before only
    after[rows, 24:30] = nan                     # after only
    before[rows, 40:46] = nan                    # both planes
    after[rows, 40:46] = nan
    _change(after, before, [(slice(40, 48), slice(40, 48))])   # changed control
    before[40:48, 48:54] = nan                   # before only, touching the control's right side
    return before, after, float(diff_threshold), int(morph_radius)


BUILDERS = {
    "edges_and_corners": _edges_and_corners,
    "diff_at_threshold": _at_threshold,
    "diff_one_ulp_below": _one_ulp_below,
    "diff_one_ulp_above": _one_ulp_above,
    "non_contiguous_odd_stride": _non_contiguous_odd_stride,
    "size_not_multiple_of_16_or_32": _size_not_multiple_of_16_or_32,
    "empty_change_set": _empty_change_set,
    "nan_in_luma_plane": _nan_in_luma_plane,
}


def build(fid: str, *, diff_threshold: float = DEFAULT_DIFF_THRESHOLD,
          morph_radius: int = DEFAULT_MORPH_RADIUS):
    """(before, after, diff_threshold, morph_radius) for one fixture id; fresh arrays every call."""
    return BUILDERS[fid](diff_threshold, morph_radius)


def _layout(a: np.ndarray) -> dict:
    return {"shape": [int(n) for n in a.shape], "dtype": a.dtype.str,
            "strides": [int(n) for n in a.strides],
            "c_contiguous": bool(a.flags.c_contiguous), "f_contiguous": bool(a.flags.f_contiguous)}


def construction_digest(before: np.ndarray, after: np.ndarray, diff_threshold: float,
                        morph_radius: int) -> str:
    """sha256 over the planes' layout (shape, dtype, strides), the base arrays of views, the
    threshold as float.hex() and the radius, then the C-order bytes of every array."""
    arrays = [before, after]
    head = {"diff_threshold": float(diff_threshold).hex(), "morph_radius": int(morph_radius)}
    for name, a in (("before", before), ("after", after)):
        head[name] = _layout(a)
        if isinstance(a.base, np.ndarray):
            head[name]["base"] = _layout(a.base)
            arrays.append(a.base)
    h = hashlib.sha256(json.dumps(head, sort_keys=True, separators=(",", ":")).encode("ascii"))
    for a in arrays:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Relations, proved exactly in float32
# ---------------------------------------------------------------------------

def plane_diff(before: np.ndarray, after: np.ndarray) -> np.ndarray:
    """|after - before| in float32."""
    b = np.asarray(before, dtype=np.float32)
    a = np.asarray(after, dtype=np.float32)
    with np.errstate(invalid="ignore"):
        return np.abs(a - b)


def _solid(mask: np.ndarray, side: int) -> bool:
    """True when mask holds a solid side x side square of True."""
    m = np.asarray(mask, dtype=bool)
    if m.ndim != 2 or side < 1 or m.shape[0] < side or m.shape[1] < side:
        return False
    c = np.zeros((m.shape[0] + 1, m.shape[1] + 1), dtype=np.int64)
    c[1:, 1:] = m.astype(np.int64).cumsum(axis=0).cumsum(axis=1)
    s = c[side:, side:] - c[:-side, side:] - c[side:, :-side] + c[:-side, :-side]
    return bool((s == side * side).any())


def _values_outside(d: np.ndarray, allowed) -> list[str]:
    finite = d[~np.isnan(d)]
    extra = sorted(set(np.unique(finite).tolist()) - {float(v) for v in allowed})
    if extra:
        return [f"|diff| takes values outside {sorted(float(v) for v in allowed)}: {extra[:4]}"]
    return []


def _boundary_check(kind: str):
    def check(before, after, d, t32, side):
        p = []
        if kind == "at":
            target = t32
        elif kind == "below":
            target = np.nextafter(t32, np.float32(-np.inf))
            if not (target < t32 and np.nextafter(target, np.float32(np.inf)) == t32):
                p.append("the below value is not one float32 ulp under float32(diff_threshold)")
        else:
            target = np.nextafter(t32, np.float32(np.inf))
            if not (target > t32 and np.nextafter(target, np.float32(-np.inf)) == t32):
                p.append("the above value is not one float32 ulp over float32(diff_threshold)")
        if np.isnan(d).any():
            p.append("a |diff| is NaN")
        p += _values_outside(d, (0.0, target, CHANGE))
        at = d == target
        if not _solid(at, side):
            p.append(f"no solid {side}x{side} patch at the boundary |diff|; a flip could be opened away")
        routes = {
            "0 to t": (before == 0) & (after == target),
            "t to 0": (before == target) & (after == 0),
            "t to 2t": (before == target) & (after == target * np.float32(2.0)),
        }
        for name, where in routes.items():
            if not _solid(where, side):
                p.append(f"no solid patch reaches the boundary |diff| as {name}")
        if not _solid(d == CHANGE, side):
            p.append("no clearly changed control patch")
        flagged = d > t32
        if kind == "above" and not flagged[at].all():
            p.append("NumPy's strict > does not flag the one-ulp-above pixels")
        if kind != "above" and flagged[at].any():
            p.append("NumPy's strict > flags a pixel at or under the threshold")
        return p
    return check


def _edges_check(before, after, d, t32, side):
    p = ["a |diff| is NaN"] if np.isnan(d).any() else []
    p += _values_outside(d, (0.0, CHANGE))
    ch = d == CHANGE
    h, w = ch.shape
    corners = {"top-left": ch[0, 0], "top-right": ch[0, w - 1],
               "bottom-left": ch[h - 1, 0], "bottom-right": ch[h - 1, w - 1]}
    p += [f"the {k} corner pixel has no change" for k, v in corners.items() if not v]
    edges = {"top": (ch[:side, :], ch[0, 1:-1]), "bottom": (ch[h - side:, :], ch[h - 1, 1:-1]),
             "left": (ch[:, :side], ch[1:-1, 0]), "right": (ch[:, w - side:], ch[1:-1, w - 1])}
    for k, (band, line) in edges.items():
        if not _solid(band, side):
            p.append(f"no solid {side}x{side} changed patch on the {k} edge")
        if not line.any():
            p.append(f"the {k} edge has no change away from its corners")
    return p


def _strided_check(before, after, d, t32, side):
    p = []
    for name, a in (("before", before), ("after", after)):
        if a.flags.c_contiguous or a.flags.f_contiguous:
            p.append(f"{name} is contiguous")
        steps = [s // a.itemsize for s in a.strides]
        if any(s % a.itemsize for s in a.strides) or not all(st % 2 == 1 for st in steps):
            p.append(f"{name} element strides {steps} are not all odd")
        if not isinstance(a.base, np.ndarray):
            p.append(f"{name} is not a view of a larger array")
    if p:
        return p
    if np.isnan(d).any():
        p.append("a |diff| is NaN")
    p += _values_outside(d, (0.0, CHANGE))
    if not _solid(d == CHANGE, side):
        p.append("no solid changed patch inside the view")
    bb, ba = before.base, after.base
    if bb.shape != ba.shape or bb.dtype != np.float32 or ba.dtype != np.float32:
        p.append("the two base arrays differ in shape or dtype")
    else:
        bd = plane_diff(bb, ba)
        outside_changed = int(np.count_nonzero(bd == CHANGE)) - int(np.count_nonzero(d == CHANGE))
        if outside_changed != bb.size - d.size:
            p.append("a base pixel outside the view does not differ by 0.5; a stride error could pass")
    return p


def _size_check(before, after, d, t32, side):
    p = []
    h, w = d.shape
    for name, n in (("height", h), ("width", w)):
        if n % 16 == 0 or n % 32 == 0:
            p.append(f"{name} {n} is a multiple of 16 or 32")
    if np.isnan(d).any():
        p.append("a |diff| is NaN")
    p += _values_outside(d, (0.0, CHANGE))
    ch = d == CHANGE
    if not ch[h - 1, :].any():
        p.append("no change on the last row")
    if not ch[:, w - 1].any():
        p.append("no change on the last column")
    if not (ch[32 * (h // 32):, :].any() and ch[:, 32 * (w // 32):].any()):
        p.append("no change in the partial tiles past the last full 32 tile")
    for b in (16, 32):
        if h > b and not (ch[b - 1, :] & ch[b, :]).any():
            p.append(f"no change straddles row {b}")
        if w > b and not (ch[:, b - 1] & ch[:, b]).any():
            p.append(f"no change straddles column {b}")
    if not _solid(ch, side):
        p.append("no solid changed patch")
    return p


def _empty_check(before, after, d, t32, side):
    p = []
    if np.isnan(d).any():
        p.append("a |diff| is NaN")
    if (d > t32).any():
        p.append("a pixel has |diff| above the threshold")
    if not (d > 0).any():
        p.append("every |diff| is zero; the compare never sees a non-zero difference")
    if not (d == 0).any():
        p.append("no identical pixels")
    return p


def _nan_check(before, after, d, t32, side):
    p = []
    nb, na, nd = np.isnan(before), np.isnan(after), np.isnan(d)
    kinds = {"before only": nb & ~na, "after only": na & ~nb, "both planes": nb & na}
    p += [f"no solid {side}x{side} NaN patch in {k}" for k, m in kinds.items() if not _solid(m, side)]
    if not np.array_equal(nd, nb | na):
        p.append("NaN |diff| is not exactly where a plane holds NaN")
    p += _values_outside(d, (0.0, CHANGE))
    ch = d == CHANGE
    if not _solid(ch, side):
        p.append("no clearly changed control patch")
    if (d > t32)[nd].any():
        p.append("NumPy's strict > flagged a NaN pixel")
    near = np.zeros_like(ch)
    near[1:, :] |= ch[:-1, :]
    near[:-1, :] |= ch[1:, :]
    near[:, 1:] |= ch[:, :-1]
    near[:, :-1] |= ch[:, 1:]
    if not (near & nd).any():
        p.append("no NaN patch touches a changed patch")
    return p


_CHECKS = {
    "edges_and_corners": _edges_check,
    "diff_at_threshold": _boundary_check("at"),
    "diff_one_ulp_below": _boundary_check("below"),
    "diff_one_ulp_above": _boundary_check("above"),
    "non_contiguous_odd_stride": _strided_check,
    "size_not_multiple_of_16_or_32": _size_check,
    "empty_change_set": _empty_check,
    "nan_in_luma_plane": _nan_check,
}


def check_relations(fid: str, before, after, diff_threshold, morph_radius) -> list[str]:
    """Every way the fixture breaks its stated relation; an empty list means it holds exactly."""
    if fid not in _CHECKS:
        return [f"unknown fixture id {fid!r}"]
    if not (isinstance(before, np.ndarray) and isinstance(after, np.ndarray)):
        return ["the planes are not numpy arrays"]
    p = [f"{n} is not a 2-D float32 plane (ndim {a.ndim}, dtype {a.dtype})"
         for n, a in (("before", before), ("after", after)) if a.ndim != 2 or a.dtype != np.float32]
    if before.shape != after.shape:
        p.append(f"plane shapes differ: {before.shape} and {after.shape}")
    t = float(diff_threshold)
    if not (math.isfinite(t) and t > 0):
        p.append("diff_threshold is not finite and positive")
    if not (isinstance(morph_radius, int) and morph_radius >= 0):
        p.append("morph_radius is not a non-negative int")
    if p:
        return p
    t32 = np.float32(t)
    d = plane_diff(before, after)
    if not np.array_equal(d > t, d > t32):
        p.append("NumPy did not compare the Python float threshold at float32")
    return p + _CHECKS[fid](before, after, d, t32, 2 * morph_radius + 1)
