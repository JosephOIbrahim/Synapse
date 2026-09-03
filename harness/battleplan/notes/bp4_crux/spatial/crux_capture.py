"""BP4-CRUX / SPATIAL lane -- independent anchor re-derivation.

Crux-authored. Re-derives every acceptance number with its OWN code and its own
oracles, then compares to the published PROBE anchors and to what the tools
return. Nothing here trusts the builder test file.

Run: CRUX_SCR=<scratch clone> CRUX_OUT=<capture_out.json> hython crux_capture.py
"""
import json, math, os, sys, time

SCR = os.environ["CRUX_SCR"]
sys.path.insert(0, SCR + "/python")
sys.path.insert(1, SCR)

import numpy as np
from pxr import Usd, UsdGeom, Gf

import synapse.spatial as SP
from synapse.spatial import (synapse_spatial_describe, synapse_spatial_classify,
                             synapse_spatial_frustum)

OUT = {"binding": {}, "describe": {}, "classify": {}, "coverage": {},
       "frustum": {}, "notes": []}

# ---- binding proof (this process) -------------------------------------------
OUT["binding"] = {
    "synapse_spatial_file": SP.__file__,
    "under_scratch": SP.__file__.replace("\\", "/").lower().startswith(SCR.lower()),
    "queries_file": SP.queries.__file__,
}
print("BINDING", json.dumps(OUT["binding"], indent=1))

# ---- published anchors (re-read by the crux from PROBE, not from the test) --
B3_MIN = [-5.339412212371826, -5.957127571105957, -19.709951400756836]
B3_MAX = [2.660879135131836, 0.6965872645378113, 21.51317024230957]
S2 = {20: {"floor": 4919, "wall": 26900, "ceiling": 350, "other": 14824},
      35: {"floor": 6414, "wall": 34415, "ceiling": 963, "other": 5201},
      45: {"floor": 7733, "wall": 37441, "ceiling": 1819, "other": 0}}
RAW_UP = (0.0, -1.0, 0.0)

USDC = os.environ["SYNAPSE_WL_COMPONENT_USDC"]
GLB = os.environ["SYNAPSE_WL_COLLIDER_GLB"]

# =========================================================================== #
# (a) describe on the component .usdc                                         #
# =========================================================================== #
stage_c = Usd.Stage.Open(USDC)
PRIM = "/wl_import/WL_fixture/geo/proxy"
w0 = time.perf_counter()
d = synapse_spatial_describe(stage_c, prim_path=PRIM)
d_wall = time.perf_counter() - w0
assert d["status"] == "SUCCESS", d
dmin, dmax = d["bounds_m"]
delta_min = [abs(dmin[i] - B3_MIN[i]) for i in range(3)]
delta_max = [abs(dmax[i] - B3_MAX[i]) for i in range(3)]
worst = max(delta_min + delta_max)


def _own_bbox(stage, prim_path):
    """Crux bbox computed a SECOND way: no BBoxCache, points transformed with
    Gf.Matrix4d.Transform rather than a numpy hstack @ matrix -- independent of
    the tool row-vector convention."""
    root = stage.GetPrimAtPath(prim_path)
    xfc = UsdGeom.XformCache(Usd.TimeCode.Default())
    lo = np.array([np.inf] * 3)
    hi = np.array([-np.inf] * 3)
    nmesh = 0
    for prim in Usd.PrimRange(root):
        if prim.GetTypeName() != "Mesh":
            continue
        pts = UsdGeom.Mesh(prim).GetPointsAttr().Get()
        if not pts:
            continue
        m = xfc.GetLocalToWorldTransform(prim)
        wp = np.array([list(m.Transform(Gf.Vec3d(*p))) for p in pts], dtype=float)
        lo = np.minimum(lo, wp.min(axis=0))
        hi = np.maximum(hi, wp.max(axis=0))
        nmesh += 1
    return lo.tolist(), hi.tolist(), nmesh


o0 = time.perf_counter()
own_lo, own_hi, own_nmesh = _own_bbox(stage_c, PRIM)
own_wall = time.perf_counter() - o0
own_worst = max([abs(own_lo[i] - B3_MIN[i]) for i in range(3)] +
                [abs(own_hi[i] - B3_MAX[i]) for i in range(3)])

OUT["describe"] = {
    "prim_path": PRIM, "bounds_m": d["bounds_m"], "size_m": d["size_m"],
    "center_m": d["center_m"], "up_axis": d["up_axis"],
    "tool_seconds": d["seconds"], "wall_seconds": d_wall,
    "delta_vs_B3_min": delta_min, "delta_vs_B3_max": delta_max,
    "delta_vs_B3_worst": worst, "within_1e_3": worst <= 1e-3,
    "crux_own_bbox_gf": [own_lo, own_hi], "crux_own_meshes": own_nmesh,
    "crux_own_seconds": own_wall, "crux_own_worst_vs_B3": own_worst,
    "crux_own_vs_tool_worst": max(
        max(abs(own_lo[i] - dmin[i]) for i in range(3)),
        max(abs(own_hi[i] - dmax[i]) for i in range(3))),
}
print("DESCRIBE", json.dumps(OUT["describe"], indent=1))

# =========================================================================== #
# collider stage -- built the way the builder fixture does                    #
# =========================================================================== #
import hou
b0 = time.perf_counter()
geo = hou.node("/obj").createNode("geo", "crux_wl_col")
g = geo.createNode("gltf", "col")
(g.parm("gltffile") or g.parm("filename")).set(GLB.replace("\\", "/"))
unp = geo.createNode("unpack", "unp")
unp.setInput(0, g)
unp.cook(force=True)
si = hou.node("/stage").createNode("sopimport", "crux_wl_col")
si.parm("soppath").set(unp.path())
si.parm("primpath").set("/collider")
si.cook(force=True)
stage_g = si.stage()
build_s = time.perf_counter() - b0
meshes = [(p.GetPath().pathString,
           len(UsdGeom.Mesh(p).GetFaceVertexCountsAttr().Get() or []))
          for p in stage_g.Traverse() if p.GetTypeName() == "Mesh"]
meshes.sort(key=lambda t: -t[1])
MESH = meshes[0][0]
print("STAGE built in %.2fs; meshes=%r; picked %s" % (build_s, meshes[:5], MESH))
OUT["collider_stage"] = {"build_seconds": build_s, "meshes": meshes,
                         "picked": MESH}

# =========================================================================== #
# crux OWN triangle gather (independent of queries.py)                        #
# =========================================================================== #
def crux_gather(stage, prim_path):
    root = stage.GetPrimAtPath(prim_path)
    xfc = UsdGeom.XformCache(Usd.TimeCode.Default())
    Cs, Ns, As = [], [], []
    nfaces = 0
    for prim in Usd.PrimRange(root):
        if prim.GetTypeName() != "Mesh":
            continue
        m = UsdGeom.Mesh(prim)
        pts = m.GetPointsAttr().Get()
        fvc = m.GetFaceVertexCountsAttr().Get()
        fvi = m.GetFaceVertexIndicesAttr().Get()
        if not pts or not fvc or not fvi:
            continue
        mtx = xfc.GetLocalToWorldTransform(prim)
        P = np.array([list(mtx.Transform(Gf.Vec3d(*p))) for p in pts], dtype=float)
        fvc = list(fvc)
        fvi = list(fvi)
        nfaces += len(fvc)
        idx = []
        off = 0
        for c in fvc:
            for k in range(1, c - 1):
                idx.append((fvi[off], fvi[off + k], fvi[off + k + 1]))
            off += c
        idx = np.asarray(idx)
        a, b, c3 = P[idx[:, 0]], P[idx[:, 1]], P[idx[:, 2]]
        cr = np.cross(b - a, c3 - a)
        L = np.linalg.norm(cr, axis=1)
        n = cr / np.where(L[:, None] == 0, 1.0, L[:, None])
        if m.GetOrientationAttr().Get() == UsdGeom.Tokens.leftHanded:
            n = -n
        Cs.append((a + b + c3) / 3.0)
        Ns.append(n)
        As.append(0.5 * L)
    return (np.concatenate(Cs), np.concatenate(Ns), np.concatenate(As), nfaces)


gt0 = time.perf_counter()
CC, NN, AA, NFACE = crux_gather(stage_g, MESH)
gather_s = time.perf_counter() - gt0
print("CRUX GATHER tris=%d faces=%d in %.3fs" % (len(CC), NFACE, gather_s))
OUT["crux_gather"] = {"triangles": int(len(CC)), "faces": NFACE,
                      "seconds": gather_s}

up_u = np.asarray(RAW_UP, dtype=float)
ang = np.degrees(np.arccos(np.clip(NN @ up_u, -1.0, 1.0)))

# =========================================================================== #
# (b) classify at 20 / 35 / 45 -- tool vs crux oracle vs published S-2        #
# =========================================================================== #
for thr in (20, 35, 45):
    w0 = time.perf_counter()
    r = synapse_spatial_classify(stage_g, prim_path=MESH, max_angle_deg=thr,
                                 up=RAW_UP)
    wall = time.perf_counter() - w0
    assert r["status"] == "SUCCESS", r
    of = int((ang < thr).sum())
    oc = int((ang > 180.0 - thr).sum())
    ow = int(((ang > 90.0 - thr) & (ang < 90.0 + thr)).sum())
    oo = int(len(ang) - ((ang < thr) | (ang > 180.0 - thr) |
                         ((ang > 90.0 - thr) & (ang < 90.0 + thr))).sum())
    c = r["counts"]
    exp = S2[thr]
    OUT["classify"][str(thr)] = {
        "tool_counts": c, "tool_triangles": r["triangles"],
        "tool_faces": r["faces"], "tool_seconds": r["seconds"],
        "wall_seconds": wall,
        "crux_oracle": {"floor": of, "wall": ow, "ceiling": oc, "other": oo},
        "published_S2": exp,
        "delta_tool_vs_S2": {"floor": c["floor"] - exp["floor"],
                             "wall": c["wall"] - exp["wall"],
                             "ceiling": c["ceiling"] - exp["ceiling"],
                             "other": c["slope"] - exp["other"]},
        "delta_crux_vs_S2": {"floor": of - exp["floor"], "wall": ow - exp["wall"],
                             "ceiling": oc - exp["ceiling"],
                             "other": oo - exp["other"]},
        "exact_tool_vs_S2": (c["floor"] == exp["floor"] and c["wall"] == exp["wall"]
                             and c["ceiling"] == exp["ceiling"]
                             and c["slope"] == exp["other"]),
        "sum_equals_total": (c["floor"] + c["wall"] + c["ceiling"] + c["slope"]
                             == r["triangles"]),
        "ground_y": r["ground_y"]["value"],
        "dominant_floor_bin": r["dominant_floor_bin"],
        "floor_area_m2": r["floor_area_m2"],
    }
    print("CLASSIFY", thr, json.dumps(OUT["classify"][str(thr)], indent=1))

# =========================================================================== #
# (c) coverage / walls-both-sides / dominant floor bin -- crux own            #
# =========================================================================== #
THR = 35
floor = ang < THR
wall_m = (ang > 90.0 - THR) & (ang < 90.0 + THR)
zext = B3_MAX[2] - B3_MIN[2]
fz = CC[floor, 2]
fy = CC[floor, 1]
hist, edges = np.histogram(fy, bins=50)
k = int(hist.argmax())
binw = float(edges[1] - edges[0])
crux_ground = float(np.median(fy[(fy >= edges[k]) & (fy <= edges[k + 1])]))
wx = CC[wall_m, 0]
tool35 = synapse_spatial_classify(stage_g, prim_path=MESH, max_angle_deg=THR,
                                  up=RAW_UP)
OUT["coverage"] = {
    "max_angle_deg": THR,
    "floor_triangles": int(floor.sum()),
    "floor_z_min": float(fz.min()), "floor_z_max": float(fz.max()),
    "floor_z_span": float(fz.max() - fz.min()),
    "B3_z_extent": zext,
    "floor_z_span_fraction_of_extent": float((fz.max() - fz.min()) / zext),
    "lane_covered_gt_0p8": bool((fz.max() - fz.min()) / zext > 0.8),
    "wall_x_negative_count": int((wx < 0).sum()),
    "wall_x_positive_count": int((wx > 0).sum()),
    "walls_both_sides": bool((wx < 0).any() and (wx > 0).any()),
    "crux_dominant_floor_y": crux_ground,
    "crux_bin_width": binw,
    "crux_bin_lo": float(edges[k]), "crux_bin_hi": float(edges[k + 1]),
    "crux_bin_faces": int(hist[k]),
    "tool_ground_y": tool35["ground_y"]["value"],
    "abs_diff_tool_vs_crux": abs(tool35["ground_y"]["value"] - crux_ground),
    "within_one_bin_width": bool(
        abs(tool35["ground_y"]["value"] - crux_ground) <= binw),
}
print("COVERAGE", json.dumps(OUT["coverage"], indent=1))

# =========================================================================== #
# (d) frustum at the S-3 eye/fov                                              #
# =========================================================================== #
floor_y = tool35["ground_y"]["value"]
cx = (B3_MIN[0] + B3_MAX[0]) / 2.0
cz = (B3_MIN[2] + B3_MAX[2]) / 2.0
eye = (cx, floor_y - 1.6, cz)
w0 = time.perf_counter()
fr = synapse_spatial_frustum(stage_g, eye=eye, forward=(0, 0, 1), up=(0, 1, 0),
                             half_fov_deg=45, aspect=0.5625, prim_path=MESH)
fr_wall = time.perf_counter() - w0
assert fr["status"] == "SUCCESS", fr
V = CC - np.asarray(eye, dtype=float)
z = V[:, 2]
th = math.tan(math.radians(45.0))
tv = math.tan(math.radians(45.0 * 0.5625))
ins = (z > 0) & (np.abs(V[:, 0]) < z * th) & (np.abs(V[:, 1]) < z * tv)
oracle = int(ins.sum())
OUT["frustum"] = {
    "eye": list(map(float, eye)), "forward": [0, 0, 1], "half_fov_deg": 45.0,
    "aspect": 0.5625,
    "tool_inside": fr["inside"], "tool_total": fr["total"],
    "tool_fraction": fr["fraction"],
    "tool_seconds": fr["seconds"], "wall_seconds": fr_wall,
    "crux_oracle_inside": oracle,
    "abs_diff": abs(fr["inside"] - oracle),
    "two_pct_of_total": 0.02 * fr["total"],
    "within_2pct": abs(fr["inside"] - oracle) <= 0.02 * fr["total"],
    "exact_match": fr["inside"] == oracle,
}
print("FRUSTUM", json.dumps(OUT["frustum"], indent=1))

# =========================================================================== #
# timing summary -- wall clock is the honest number for acceptance row 2      #
# =========================================================================== #
OUT["timing_summary"] = {
    "describe_tool_seconds": OUT["describe"]["tool_seconds"],
    "describe_wall_seconds": OUT["describe"]["wall_seconds"],
    "classify45_tool_seconds": OUT["classify"]["45"]["tool_seconds"],
    "classify45_wall_seconds": OUT["classify"]["45"]["wall_seconds"],
    "frustum_tool_seconds": OUT["frustum"]["tool_seconds"],
    "frustum_wall_seconds": OUT["frustum"]["wall_seconds"],
    "budget_s": 5.0,
    "all_wall_under_budget": all(
        x < 5.0 for x in (OUT["describe"]["wall_seconds"],
                          OUT["classify"]["45"]["wall_seconds"],
                          OUT["frustum"]["wall_seconds"])),
}
print("TIMING", json.dumps(OUT["timing_summary"], indent=1))

with open(os.environ["CRUX_OUT"], "w", encoding="utf-8") as fh:
    json.dump(OUT, fh, indent=2)
print("WROTE", os.environ["CRUX_OUT"])
