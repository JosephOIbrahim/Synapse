"""BP4-SPATIAL — the World Labs read-only spatial lane (D3.3/D3.4).

Two tiers of test:

  * FIXTURE-INDEPENDENT (pure ``pxr``, authored geometry with known answers).
    These run in any OpenUSD environment and are the reproducible core — the
    crucible re-runs them in a fresh checkout with no external fixture.
  * FIXTURE-ANCHORED (PROBE numbers). These reproduce the published anchors on
    PROBE's b6_wl_component.usdc (describe → B-3 bbox) and the 46,993-tri GLB
    collider (classify → S-2 counts, frustum → re-derived S-3). PROBE left both
    binaries **uncommitted** (harness/notes/h22wl/bp3_probes/run_meta.txt:
    "deliberately unstaged"), so when they are absent these tests SKIP WITH A
    REASON — a visible skip, never a hidden pass (constitution: skip ≠ pass).

Anchors (PROBE, re-read live 2026-09-03, build 22.0.400):
  B-3 bbox        harness/notes/h22wl/bp3_probes/supplementary.txt (v2) + S-1
  S-2 counts      supplementary.txt v2 (46,993-tri UNPACKED collider)
  maxangle=45     scatterinstances 'Max Angle' default (P-5), live-introspected
  S-3 method      harness/probes/synapse_blueprint_probes.py:453 (stdout 0/2 was
                  degenerate — 2 packed prims; the real count is re-derived here)
"""
import math
import os
from pathlib import Path

import pytest

pytest.importorskip("pxr")      # marks this module needs_houdini (conftest CI0)
pytest.importorskip("numpy")

from pxr import Usd, UsdGeom, Gf   # noqa: E402
import numpy as np                 # noqa: E402

from synapse.spatial import (      # noqa: E402
    SCATTER_MAX_ANGLE_DEFAULT_DEG,
    synapse_spatial_classify,
    synapse_spatial_describe,
    synapse_spatial_frustum,
)

# ---- published PROBE anchors -------------------------------------------------
B3_BBOX = ([-5.339412212371826, -5.957127571105957, -19.709951400756836],
           [2.660879135131836, 0.6965872645378113, 21.51317024230957])
# supplementary.txt v2: thr -> (floor, wall, ceiling, slope) on 46,993 tris
S2_COUNTS = {20: (4919, 26900, 350, 14824),
             35: (6414, 34415, 963, 5201),
             45: (7733, 37441, 1819, 0)}
RAW_UP = (0.0, -1.0, 0.0)   # WL-EX-05: the fixture is +y-DOWN in the raw frame
TIMING_BUDGET_S = 5.0

_REPO = Path(__file__).resolve().parents[1]


# ============================================================================ #
#  helpers                                                                     #
# ============================================================================ #
def _real_hou():
    """The real Houdini `hou`, or None (the conftest fake is not it)."""
    try:
        import hou
    except ImportError:
        return None
    if getattr(hou, "__synapse_canonical__", False):
        return None      # conftest's fake — cannot build a live stage
    return hou


def _find_fixture(env_var, rel_names):
    """Resolve an uncommitted PROBE binary via env var, then known locations
    (this worktree's probe dir, sibling bp3-probe worktree, the machine path)."""
    p = os.environ.get(env_var)
    if p and Path(p).exists():
        return Path(p)
    roots = [_REPO, _REPO.parent / "bp3-probe",
             Path("C:/Users/User/SYNAPSE/.claude/worktrees/bp3-probe")]
    for root in roots:
        for rel in rel_names:
            cand = root / rel
            if cand.exists():
                return cand
    return None


_COMPONENT_REL = ["harness/notes/h22wl/bp3_probes/b6_wl_component.usdc"]
_GLB_REL = ["harness/fixtures/worldlabs/narrow_european_cobblestone_lane/"
            "narrow_european_cobblestone_lane_collider.glb"]


def _author_box_stage(half=1.0, orientation=UsdGeom.Tokens.rightHanded):
    """In-memory unit-ish cube as a triangulated Mesh (pure pxr, no fixture).

    Known answer under up=+Y: the +Y face is floor, -Y ceiling, the four side
    faces walls, nothing slope. Winding is chosen so rightHanded normals point
    OUT; the tool's orientation handling is exercised by the fixture path.
    """
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(stage, "/box")
    mesh = UsdGeom.Mesh.Define(stage, "/box/mesh")
    h = half
    pts = [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h),
           (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)]
    # each quad wound CCW seen from OUTSIDE -> outward normal (rightHanded)
    quads = [
        (0, 3, 2, 1),   # -Z
        (4, 5, 6, 7),   # +Z
        (0, 4, 7, 3),   # -X
        (1, 2, 6, 5),   # +X
        (0, 1, 5, 4),   # -Y
        (3, 7, 6, 2),   # +Y
    ]
    counts, indices = [], []
    for q in quads:
        counts.append(4)
        indices.extend(q)
    mesh.CreatePointsAttr([Gf.Vec3f(*p) for p in pts])
    mesh.CreateFaceVertexCountsAttr(counts)
    mesh.CreateFaceVertexIndicesAttr(indices)
    mesh.CreateOrientationAttr(orientation)
    return stage


def _independent_triangles(stage, prim_path, up_hint=None):
    """A SECOND, tool-independent gather of world-space centroids/normals — the
    oracle the frustum/classify assertions check the tool against."""
    root = stage.GetPrimAtPath(prim_path) if prim_path else stage.GetPseudoRoot()
    xf = UsdGeom.XformCache(Usd.TimeCode.Default())
    C, N = [], []
    for prim in Usd.PrimRange(root):
        if prim.GetTypeName() != "Mesh":
            continue
        m = UsdGeom.Mesh(prim)
        pts = np.asarray(m.GetPointsAttr().Get(), dtype=float)
        fvc = list(m.GetFaceVertexCountsAttr().Get() or [])
        fvi = list(m.GetFaceVertexIndicesAttr().Get() or [])
        if not fvc:
            continue
        mtx = np.asarray(xf.GetLocalToWorldTransform(prim), dtype=float)
        ptw = (np.hstack([pts, np.ones((len(pts), 1))]) @ mtx)[:, :3]
        flip = m.GetOrientationAttr().Get() == UsdGeom.Tokens.leftHanded
        off = 0
        for c in fvc:
            for k in range(1, c - 1):
                a, b, cc = fvi[off], fvi[off + k], fvi[off + k + 1]
                p0, p1, p2 = ptw[a], ptw[b], ptw[cc]
                n = np.cross(p1 - p0, p2 - p0)
                ln = np.linalg.norm(n)
                n = n / ln if ln else n
                if flip:
                    n = -n
                C.append((p0 + p1 + p2) / 3.0)
                N.append(n)
            off += c
    return np.asarray(C), np.asarray(N)


# module-scope lazy builders (build the hou stages once) -----------------------
@pytest.fixture(scope="module")
def collider_stage():
    hou = _real_hou()
    if hou is None:
        pytest.skip("needs a live Houdini runtime (real `hou`) to import the GLB")
    glb = _find_fixture("SYNAPSE_WL_COLLIDER_GLB", _GLB_REL)
    if glb is None:
        pytest.skip("collider GLB not found (PROBE left it uncommitted); set "
                    "SYNAPSE_WL_COLLIDER_GLB — see review doc §fixtures")
    geo = hou.node("/obj").createNode("geo", "bp4_wl_col")
    g = geo.createNode("gltf", "col")
    (g.parm("gltffile") or g.parm("filename")).set(str(glb).replace("\\", "/"))
    unp = geo.createNode("unpack", "unp")
    unp.setInput(0, g)
    unp.cook(force=True)
    si = hou.node("/stage").createNode("sopimport", "bp4_wl_col")
    si.parm("soppath").set(unp.path())
    si.parm("primpath").set("/collider")
    si.cook(force=True)
    stage = si.stage()
    mesh_path = max(
        (p.GetPath().pathString for p in stage.Traverse()
         if p.GetTypeName() == "Mesh"),
        key=lambda pp: len(UsdGeom.Mesh(stage.GetPrimAtPath(pp))
                           .GetFaceVertexCountsAttr().Get() or []))
    return stage, mesh_path


@pytest.fixture(scope="module")
def component_stage():
    usdc = _find_fixture("SYNAPSE_WL_COMPONENT_USDC", _COMPONENT_REL)
    if usdc is None:
        pytest.skip("b6_wl_component.usdc not found (PROBE left it uncommitted); "
                    "set SYNAPSE_WL_COMPONENT_USDC — see review doc §fixtures")
    return Usd.Stage.Open(str(usdc))


# ============================================================================ #
#  TIER 1 — fixture-independent (authored geometry, known answers)             #
# ============================================================================ #
def test_describe_synthetic_box_bounds():
    stage = _author_box_stage(half=1.0)
    r = synapse_spatial_describe(stage, prim_path="/box")
    assert r["status"] == "SUCCESS"
    assert r["bounds_m"][0] == pytest.approx([-1, -1, -1], abs=1e-6)
    assert r["bounds_m"][1] == pytest.approx([1, 1, 1], abs=1e-6)
    assert r["size_m"] == pytest.approx([2, 2, 2], abs=1e-6)
    assert r["is_empty"] is False
    assert r["seconds"] < TIMING_BUDGET_S


def test_describe_empty_stage_is_honest_unavailable():
    """No geometry -> UNAVAILABLE, never SUCCESS with zero bounds."""
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/empty")
    r = synapse_spatial_describe(stage)
    assert r["status"] == "UNAVAILABLE"
    assert "bounds_m" not in r


def test_classify_synthetic_box_structure():
    stage = _author_box_stage(half=1.0)
    r = synapse_spatial_classify(stage, prim_path="/box", up=(0, 1, 0))
    assert r["status"] == "SUCCESS"
    fr = r["surface_classes"]
    # cube is symmetric: 4/6 walls, 1/6 floor, 1/6 ceiling, no slope
    assert fr["slope"] == pytest.approx(0.0, abs=1e-9)
    assert fr["wall"] == pytest.approx(4 / 6, abs=1e-6)
    assert fr["floor"] == pytest.approx(1 / 6, abs=1e-6)
    assert fr["ceiling"] == pytest.approx(1 / 6, abs=1e-6)
    assert r["counts"]["floor"] + r["counts"]["ceiling"] == r["triangles"] // 3


def test_classify_default_max_angle_is_scatter_default():
    assert SCATTER_MAX_ANGLE_DEFAULT_DEG == 45.0
    stage = _author_box_stage()
    r = synapse_spatial_classify(stage, prim_path="/box")   # no max_angle arg
    assert r["surface_classes"]["max_angle_deg"] == 45.0


def test_frustum_synthetic_all_in_and_none_behind():
    stage = _author_box_stage(half=1.0)
    # camera on -Z looking +Z: the whole box is ahead -> all triangles inside
    allin = synapse_spatial_frustum(stage, eye=(0, 0, -10), forward=(0, 0, 1),
                                    prim_path="/box", half_fov_deg=45)
    assert allin["status"] == "SUCCESS"
    assert allin["inside"] == allin["total"] == 12
    # camera looking AWAY from the box -> nothing inside
    behind = synapse_spatial_frustum(stage, eye=(0, 0, -10), forward=(0, 0, -1),
                                     prim_path="/box", half_fov_deg=45)
    assert behind["inside"] == 0


def test_classify_unavailable_on_pointcloud_only():
    """A stage with no Mesh (e.g. splat Points) is honestly UNAVAILABLE."""
    stage = Usd.Stage.CreateInMemory()
    pts = UsdGeom.Points.Define(stage, "/pts")
    pts.CreatePointsAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 1, 1)])
    r = synapse_spatial_classify(stage)
    assert r["status"] == "UNAVAILABLE"


def test_no_default_on_registration():
    """Rule D-1: the lane is ratified:false, so nothing outside its own package
    imports or registers the spatial tools, and no SYNAPSE_SPATIAL_LANE gate is
    wired on. (evidence: check — also recorded as a grep in the review doc.)"""
    py_root = _REPO / "python"
    ref_hits, env_hits = [], []
    for py in py_root.rglob("*.py"):
        posix = py.as_posix()
        if "/synapse/spatial/" in posix:
            continue
        txt = py.read_text(encoding="utf-8", errors="ignore")
        if "synapse.spatial" in txt or "synapse_spatial_describe" in txt \
                or "synapse_spatial_frustum" in txt:
            ref_hits.append(posix)
        if "SYNAPSE_SPATIAL_LANE" in txt:
            env_hits.append(posix)
    root_mcp = _REPO / "mcp_server.py"
    if root_mcp.exists():
        t = root_mcp.read_text(encoding="utf-8", errors="ignore")
        assert "synapse.spatial" not in t and "synapse_spatial_" not in t
    assert ref_hits == [], f"spatial tools referenced outside their package: {ref_hits}"
    assert env_hits == [], f"SYNAPSE_SPATIAL_LANE wired outside the package: {env_hits}"


# ============================================================================ #
#  TIER 2 — fixture-anchored (PROBE numbers; skip-with-reason if absent)       #
# ============================================================================ #
def test_describe_component_usdc_matches_B3_bbox(component_stage):
    """describe on PROBE's b6_wl_component.usdc proxy == B-3 bbox within 1e-3."""
    r = synapse_spatial_describe(component_stage,
                                 prim_path="/wl_import/WL_fixture/geo/proxy")
    assert r["status"] == "SUCCESS"
    assert r["bounds_m"][0] == pytest.approx(B3_BBOX[0], abs=1e-3)
    assert r["bounds_m"][1] == pytest.approx(B3_BBOX[1], abs=1e-3)
    assert r["seconds"] < TIMING_BUDGET_S


@pytest.mark.parametrize("thr", [20, 35, 45])
def test_classify_collider_matches_S2_anchor(collider_stage, thr):
    """classify on the 46,993-tri GLB collider == S-2 published counts."""
    stage, mesh = collider_stage
    r = synapse_spatial_classify(stage, prim_path=mesh, max_angle_deg=thr,
                                 up=RAW_UP)
    assert r["status"] == "SUCCESS"
    assert r["triangles"] == 46993
    exp_floor, exp_wall, exp_ceil, exp_slope = S2_COUNTS[thr]
    c = r["counts"]
    # validated byte-exact live 2026-09-03; ±5 faces guards env variance only
    assert c["floor"] == pytest.approx(exp_floor, abs=5)
    assert c["wall"] == pytest.approx(exp_wall, abs=5)
    assert c["ceiling"] == pytest.approx(exp_ceil, abs=5)
    assert c["slope"] == pytest.approx(exp_slope, abs=5)
    assert r["seconds"] < TIMING_BUDGET_S


def test_classify_collider_lane_coverage_and_walls(collider_stage):
    """Brief T2: floor covers the lane; walls present on both sides (sign of x);
    dominant floor height matches the independently re-derived S-2 bin."""
    stage, mesh = collider_stage
    r = synapse_spatial_classify(stage, prim_path=mesh, max_angle_deg=35,
                                 up=RAW_UP)
    C, N = _independent_triangles(stage, mesh)
    a = np.degrees(np.arccos(np.clip(N @ np.asarray(RAW_UP), -1.0, 1.0)))
    floor = a < 35
    # floor covers the lane: its z-span is most of the collider z-extent
    zext = B3_BBOX[1][2] - B3_BBOX[0][2]
    fz = C[floor, 2]
    assert (fz.max() - fz.min()) / zext > 0.8
    # walls on both sides of x
    wx = C[(a > 55) & (a < 125), 0]
    assert (wx < 0).any() and (wx > 0).any()
    # dominant floor height within one bin width of the independent re-derivation
    fy = C[floor, 1]
    hist, edges = np.histogram(fy, bins=50)
    k = int(hist.argmax())
    ref = float(np.median(fy[(fy >= edges[k]) & (fy <= edges[k + 1])]))
    binw = float(edges[1] - edges[0])
    assert r["ground_y"]["value"] == pytest.approx(ref, abs=binw)


def test_frustum_collider_reproduces_S3(collider_stage):
    """frustum count == the re-derived S-3 count within 2% for the same eye/fov.
    (stdout S-3 was 0/2 on 2 packed prims — degenerate; the real substrate is
    the 46,993-tri collider.)"""
    stage, mesh = collider_stage
    # eye per S-3: (center.x, dominant_floor_y - 1.6, center.z), fwd +z
    cls = synapse_spatial_classify(stage, prim_path=mesh, max_angle_deg=35,
                                   up=RAW_UP)
    floor_y = cls["ground_y"]["value"]
    cx = (B3_BBOX[0][0] + B3_BBOX[1][0]) / 2.0
    cz = (B3_BBOX[0][2] + B3_BBOX[1][2]) / 2.0
    eye = (cx, floor_y - 1.6, cz)
    r = synapse_spatial_frustum(stage, eye=eye, forward=(0, 0, 1), up=(0, 1, 0),
                                half_fov_deg=45, aspect=0.5625, prim_path=mesh)
    assert r["status"] == "SUCCESS"
    # independent oracle: the S-3 tan-formula on a separate gather
    C, _ = _independent_triangles(stage, mesh)
    V = C - np.asarray(eye)
    z = V[:, 2]
    inside = ((z > 0)
              & (np.abs(V[:, 0]) < z * math.tan(math.radians(45)))
              & (np.abs(V[:, 1]) < z * math.tan(math.radians(45 * 0.5625))))
    oracle = int(inside.sum())
    assert oracle > 1000, "sanity: the eye should see much of the lane"
    assert abs(r["inside"] - oracle) <= 0.02 * r["total"]
    assert r["seconds"] < TIMING_BUDGET_S


# ============================================================================ #
#  TIER 2 — D3.4: run on a second existing stage without code change           #
# ============================================================================ #
def test_D34_solaris_basic_runs_without_code_change():
    """The three tools execute on fixtures/solaris.basic.json (built live) with
    NO code change, returning honest envelopes (SUCCESS or UNAVAILABLE, never an
    exception). solaris.basic has empty geometry, so UNAVAILABLE is the correct,
    honest answer — the point is portability, not a rich result."""
    hou = _real_hou()
    if hou is None:
        pytest.skip("needs a live Houdini runtime (real `hou`) to build the stage")
    fx = _REPO / "fixtures" / "solaris.basic.json"
    if not fx.exists():
        pytest.skip(f"second stage not found: {fx}")
    import json
    spec = json.loads(fx.read_text(encoding="utf-8"))
    stage_ctx = hou.node("/stage")
    made = {}
    for nd in spec["nodes"]:
        n = stage_ctx.createNode(nd["type"], "bp4_" + nd["name"])
        for pn, pv in (nd.get("parms") or {}).items():
            p = n.parm(pn)
            if p is not None:
                p.set(pv)
        made[nd["name"]] = n
    for dst, idx, src in spec.get("wires", []):
        if dst in made and src in made:
            made[dst].setInput(idx, made[src])
    disp = made[spec["display"]]
    disp.cook(force=True)
    stage = disp.stage()

    outs = {
        "describe": synapse_spatial_describe(stage),
        "classify": synapse_spatial_classify(stage),
        "frustum": synapse_spatial_frustum(stage, eye=(0, 1, -5)),
    }
    for name, out in outs.items():
        assert isinstance(out, dict) and "status" in out, name
        assert out["status"] in ("SUCCESS", "UNAVAILABLE"), (name, out)
