"""Read-only spatial query tools for the World Labs lane (Intent 3, D3.3/D3.4).

Three pure-``pxr`` queries over a ``Usd.Stage``. They READ geometry and return
answers; **nothing is authored, no file is written**. They are the read side of
the ``space`` object in ``docs/intake/world_manifest.schema.json`` (v0,
ratified:false) — ``bounds_m``, ``surface_classes`` (fractions), a derived
ground-plane candidate, and a camera-frustum membership count.

    synapse_spatial_describe  -> world bounds + extent of a stage subtree
    synapse_spatial_classify  -> floor/wall/ceiling/slope fractions at a Max Angle
    synapse_spatial_frustum   -> face count inside a camera frustum

Why ``pxr`` and not ``hou`` (D-DEP-03).  These tools answer questions about a
USD component **at rest** (a ``.usdc`` on disk, or any live LOP ``.stage()``),
so the native reader is OpenUSD.  The closest *published spatial* method in the
repo is already ``pxr`` — the PROBE leg's S-1 walk uses
``UsdGeom.BBoxCache`` (``harness/probes/synapse_blueprint_probes.py:419``).
RECON's D-DEP-03 note (``harness/battleplan/notes/BP3_RECON.md:71``) records
that the *existing* bounds code is ``hou``-based, but that code introspects a
**live ``hou.Geometry``** in a running session — a different context.  For a
read-only query on a USD stage, ``pxr`` is the honest fit; this module never
imports ``hou``.

Correctness anchors (PROBE, re-read live 2026-09-03, build 22.0.400):
  * describe bounds == B-3 collider bbox
    (``harness/notes/h22wl/bp3_probes/supplementary.txt`` v2 + S-1)
  * classify counts == S-2 unpacked normal-class counts (supplementary.txt v2)
  * classify default ``max_angle_deg`` == scatterinstances 'Max Angle' default
    (P-5) == **45.0**, live-introspected 2026-09-03.

Both modes.  The module imports with or without ``pxr``/``numpy`` (SYNAPSE §12
import-guard convention); the tools return an honest ``BLOCKED`` status when a
dependency is absent rather than raising at import.

Lane status (rule D-1): the World Labs lane is ``ratified:false``, so these
tools are **unregistered** — no ``mcp_server`` import, no tool-registry entry.
See ``python/synapse/spatial/__init__.py`` for the opt-in wiring note.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, Optional, Sequence, Tuple

try:  # OpenUSD — present under hython / a USD install, absent on stock CI.
    from pxr import Usd, UsdGeom, Gf  # noqa: F401
    PXR_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only on stock interpreters
    Usd = UsdGeom = Gf = None  # type: ignore
    PXR_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    np = None  # type: ignore
    NUMPY_AVAILABLE = False


# scatterinstances 'Max Angle' (folder /Scattering/Masks/Up Axis Direction,
# parm `maxangle`) default, live-introspected on 22.0.400 (P-5). This is the
# classify default so a bare call matches the scatter Up-Axis mask the lane
# mirrors.
SCATTER_MAX_ANGLE_DEFAULT_DEG = 45.0

# Canonical up per the manifest schema (`space.up_axis` const "+Y"). The raw
# World Labs fixture is +y-DOWN (WL-EX-05), so a caller measuring the raw frame
# passes up=(0,-1,0) explicitly; the default is the post-conversion canonical.
DEFAULT_UP: Tuple[float, float, float] = (0.0, 1.0, 0.0)

_DEFAULT_PURPOSES = ("default", "render", "proxy")

# Status vocabulary (constitution): SUCCESS | UNAVAILABLE | BLOCKED. An empty
# payload under SUCCESS is the defect, so "no geometry" is UNAVAILABLE, never a
# SUCCESS with zero bounds.
STATUS_SUCCESS = "SUCCESS"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_BLOCKED = "BLOCKED"


def _dep_block() -> Optional[Dict[str, Any]]:
    """Return a BLOCKED envelope if a hard dependency is missing, else None."""
    missing = []
    if not PXR_AVAILABLE:
        missing.append("pxr (OpenUSD)")
    if not NUMPY_AVAILABLE:
        missing.append("numpy")
    if missing:
        return {"status": STATUS_BLOCKED,
                "reason": "spatial queries require " + " + ".join(missing)}
    return None


def _resolve_prim(stage, prim_path: Optional[str]):
    """The prim to query: an explicit path, else the stage default prim, else
    the pseudo-root. Returns (prim, error_dict|None)."""
    if prim_path:
        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            return None, {"status": STATUS_UNAVAILABLE,
                          "reason": f"prim not found: {prim_path}"}
        return prim, None
    dp = stage.GetDefaultPrim()
    if dp and dp.IsValid():
        return dp, None
    return stage.GetPseudoRoot(), None


def _iter_meshes(root_prim, purposes: Sequence[str]):
    """Yield UsdGeom.Mesh prims under (and including) root_prim whose computed
    purpose is in `purposes`."""
    keep = set(purposes)
    for prim in Usd.PrimRange(root_prim):
        if prim.GetTypeName() != "Mesh":
            continue
        purpose = UsdGeom.Imageable(prim).ComputePurpose()
        if purpose in keep:
            yield UsdGeom.Mesh(prim)


def _collect_triangles(stage, prim_path, purposes):
    """World-space per-triangle centroids, unit normals, and areas across every
    mesh under prim_path.

    Normals are geometric (cross product of the two triangle edges) and are
    flipped for a `leftHanded` mesh so a front face's normal points OUT — the
    orientation-correct convention (validated: leftHanded fixture needs the
    flip to reproduce the S-2 counts). Returns (centroids, normals, areas,
    n_meshes, n_faces) as numpy arrays, or (None, ...) with a reason.
    """
    root, err = _resolve_prim(stage, prim_path)
    if err:
        return None, err
    xf_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    all_c, all_n, all_a = [], [], []
    n_meshes = 0
    n_faces = 0
    for mesh in _iter_meshes(root, purposes):
        prim = mesh.GetPrim()
        pts_attr = mesh.GetPointsAttr().Get()
        fvc = mesh.GetFaceVertexCountsAttr().Get()
        fvi = mesh.GetFaceVertexIndicesAttr().Get()
        if not pts_attr or not fvc or not fvi:
            continue
        pts = np.asarray(pts_attr, dtype=float)
        xf = np.asarray(xf_cache.GetLocalToWorldTransform(prim), dtype=float)
        ptw = (np.hstack([pts, np.ones((len(pts), 1))]) @ xf)[:, :3]
        fvc = list(fvc)
        fvi = list(fvi)
        n_faces += len(fvc)
        # fan-triangulate each face
        tri = []
        off = 0
        for c in fvc:
            for k in range(1, c - 1):
                tri.append((fvi[off], fvi[off + k], fvi[off + k + 1]))
            off += c
        if not tri:
            continue
        tri = np.asarray(tri)
        p0, p1, p2 = ptw[tri[:, 0]], ptw[tri[:, 1]], ptw[tri[:, 2]]
        cross = np.cross(p1 - p0, p2 - p0)
        area = 0.5 * np.linalg.norm(cross, axis=1)
        ln = np.linalg.norm(cross, axis=1, keepdims=True)
        nrm = cross / np.where(ln == 0, 1.0, ln)
        if mesh.GetOrientationAttr().Get() == UsdGeom.Tokens.leftHanded:
            nrm = -nrm
        all_c.append((p0 + p1 + p2) / 3.0)
        all_n.append(nrm)
        all_a.append(area)
        n_meshes += 1
    if not all_c:
        return None, {"status": STATUS_UNAVAILABLE,
                      "reason": f"no mesh geometry under "
                                f"{prim_path or root.GetPath().pathString} "
                                f"for purposes {tuple(purposes)}"}
    C = np.concatenate(all_c)
    N = np.concatenate(all_n)
    A = np.concatenate(all_a)
    return (C, N, A, n_meshes, n_faces), None


def _unit(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n else v


def _provenance(method: str, probe: Optional[str] = None, tier: str = "derived"):
    return {"tool_lane": "world_labs_spatial", "ratified": False,
            "tier": tier, "method": method, "probe": probe,
            "build_note": "read-only; no prim authored, no file written"}


# --------------------------------------------------------------------------- #
#  Tool 1 — describe                                                          #
# --------------------------------------------------------------------------- #
def synapse_spatial_describe(stage, prim_path: Optional[str] = None,
                             purposes: Sequence[str] = _DEFAULT_PURPOSES
                             ) -> Dict[str, Any]:
    """World-space bounds and extent of a stage subtree (read-only).

    Uses ``UsdGeom.BBoxCache`` over the given imageable ``purposes`` (S-1's
    method). Returns the manifest ``bounds_m`` shape ``[[min],[max]]`` plus
    size/center and the stage up axis. Empty geometry is reported UNAVAILABLE,
    never a SUCCESS with zero bounds.
    """
    blocked = _dep_block()
    if blocked:
        return blocked
    prim, err = _resolve_prim(stage, prim_path)
    if err:
        return err
    t0 = time.perf_counter()
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), list(purposes))
    rng = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
    elapsed = time.perf_counter() - t0
    if rng.IsEmpty():
        return {"status": STATUS_UNAVAILABLE,
                "reason": f"no bounded geometry under "
                          f"{prim.GetPath().pathString} for purposes "
                          f"{tuple(purposes)}",
                "prim_path": prim.GetPath().pathString,
                "seconds": elapsed}
    mn, mx = rng.GetMin(), rng.GetMax()
    bounds_m = [[float(mn[i]) for i in range(3)],
                [float(mx[i]) for i in range(3)]]
    size_m = [bounds_m[1][i] - bounds_m[0][i] for i in range(3)]
    center_m = [(bounds_m[0][i] + bounds_m[1][i]) / 2.0 for i in range(3)]
    return {
        "status": STATUS_SUCCESS,
        "prim_path": prim.GetPath().pathString,
        "purposes": list(purposes),
        "bounds_m": bounds_m,
        "size_m": size_m,
        "center_m": center_m,
        "up_axis": UsdGeom.GetStageUpAxis(stage),
        "meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage)),
        "is_empty": False,
        "seconds": elapsed,
        "provenance": _provenance("UsdGeom.BBoxCache world bound", probe="B-3"),
    }


# --------------------------------------------------------------------------- #
#  Tool 2 — classify                                                          #
# --------------------------------------------------------------------------- #
def synapse_spatial_classify(stage, prim_path: Optional[str] = None,
                             max_angle_deg: float = SCATTER_MAX_ANGLE_DEFAULT_DEG,
                             up: Sequence[float] = DEFAULT_UP,
                             purposes: Sequence[str] = _DEFAULT_PURPOSES,
                             floor_bins: int = 50) -> Dict[str, Any]:
    """Surface-class fractions of a mesh subtree at a Max Angle (read-only).

    A face is FLOOR if its normal lies within ``max_angle_deg`` of ``up``,
    CEILING if within ``max_angle_deg`` of ``-up``, WALL if within
    ``max_angle_deg`` of the horizon (normal ⟂ up), else SLOPE. Mirrors the
    scatterinstances Up-Axis mask (P-5) — hence the 45° default. ``up`` defaults
    to the schema canonical +Y; the raw World Labs fixture is +y-DOWN, so a
    caller measuring the raw frame passes ``up=(0,-1,0)``.

    Also derives a ground-plane candidate: the dominant histogram bin of the
    floor faces' height along the up axis (S-2's method), returned as a
    provenanced number.
    """
    blocked = _dep_block()
    if blocked:
        return blocked
    got, err = _collect_triangles(stage, prim_path, purposes)
    if err:
        return err
    C, N, A, n_meshes, n_faces = got
    t0 = time.perf_counter()
    up_u = _unit(up)
    total = int(len(N))
    a = np.degrees(np.arccos(np.clip(N @ up_u, -1.0, 1.0)))
    thr = float(max_angle_deg)
    floor_mask = a < thr
    ceil_mask = a > (180.0 - thr)
    wall_mask = (a > (90.0 - thr)) & (a < (90.0 + thr))
    slope_mask = ~(floor_mask | ceil_mask | wall_mask)
    counts = {"floor": int(floor_mask.sum()), "wall": int(wall_mask.sum()),
              "ceiling": int(ceil_mask.sum()), "slope": int(slope_mask.sum())}
    fractions = {k: (v / total if total else 0.0) for k, v in counts.items()}

    # ground-plane candidate: dominant floor-height bin along the up axis.
    up_axis_idx = int(np.argmax(np.abs(up_u)))
    ground = {"value": None, "tier": "derived",
              "method": "S-2 dominant floor bin", "probe": "S-2"}
    dominant_bin = None
    floor_area = float(A[floor_mask].sum())
    if floor_mask.any():
        fh = C[floor_mask, up_axis_idx]
        hist, edges = np.histogram(fh, bins=floor_bins)
        k = int(hist.argmax())
        lo, hi = float(edges[k]), float(edges[k + 1])
        in_bin = fh[(fh >= lo) & (fh <= hi)]
        ground["value"] = float(np.median(in_bin))
        dominant_bin = {"lo": lo, "hi": hi, "width": float(edges[1] - edges[0]),
                        "faces": int(hist[k]), "axis_index": up_axis_idx}
    elapsed = time.perf_counter() - t0
    return {
        "status": STATUS_SUCCESS,
        "prim_path": prim_path,
        "meshes": n_meshes,
        "faces": n_faces,
        "triangles": total,
        "surface_classes": {"max_angle_deg": thr, **fractions},
        "counts": counts,
        "up": list(up_u),
        "ground_y": ground,
        "floor_area_m2": floor_area,
        "dominant_floor_bin": dominant_bin,
        "seconds": elapsed,
        "provenance": _provenance(
            "per-face geometric normal vs up axis; orientation-aware",
            probe="S-2"),
    }


# --------------------------------------------------------------------------- #
#  Tool 3 — frustum                                                           #
# --------------------------------------------------------------------------- #
def synapse_spatial_frustum(stage, eye: Sequence[float],
                            forward: Sequence[float] = (0.0, 0.0, 1.0),
                            up: Sequence[float] = (0.0, 1.0, 0.0),
                            half_fov_deg: float = 45.0, aspect: float = 0.5625,
                            near: float = 0.0, far: Optional[float] = None,
                            prim_path: Optional[str] = None,
                            purposes: Sequence[str] = _DEFAULT_PURPOSES
                            ) -> Dict[str, Any]:
    """Count mesh faces whose centroid falls inside a camera frustum (read-only).

    The camera-mask analogue of scatterinstances (S-3). ``half_fov_deg`` is the
    horizontal half-angle; the vertical half-angle is ``half_fov_deg * aspect``
    (S-3's convention, aspect 0.5625 = 720/1280). With ``forward=+z, up=+y`` this
    reproduces the S-3 world-axis test exactly. Returns the inside count, total,
    and fraction.
    """
    blocked = _dep_block()
    if blocked:
        return blocked
    got, err = _collect_triangles(stage, prim_path, purposes)
    if err:
        return err
    C, N, A, n_meshes, n_faces = got
    t0 = time.perf_counter()
    eye = np.asarray(eye, dtype=float)
    fwd = _unit(forward)
    right = _unit(np.cross(fwd, _unit(up)))
    up_o = _unit(np.cross(right, fwd))
    V = C - eye
    z = V @ fwd
    x = V @ right
    y = V @ up_o
    tan_h = math.tan(math.radians(half_fov_deg))
    tan_v = math.tan(math.radians(half_fov_deg * aspect))
    far_v = math.inf if far is None else float(far)
    inside = (z > near) & (z < far_v) & (np.abs(x) < z * tan_h) & (np.abs(y) < z * tan_v)
    count = int(inside.sum())
    total = int(len(C))
    elapsed = time.perf_counter() - t0
    return {
        "status": STATUS_SUCCESS,
        "prim_path": prim_path,
        "inside": count,
        "total": total,
        "fraction": (count / total if total else 0.0),
        "eye": list(map(float, eye)),
        "forward": list(map(float, fwd)),
        "half_fov_deg": float(half_fov_deg),
        "aspect": float(aspect),
        "near": float(near),
        "far": None if far is None else float(far),
        "seconds": elapsed,
        "provenance": _provenance(
            "centroid-in-frustum, S-3 half-angle test", probe="S-3"),
    }
