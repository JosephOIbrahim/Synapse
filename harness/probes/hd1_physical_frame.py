#!/usr/bin/env python3
"""hd1_physical_frame.py - the HD1 collider and rest test (SPEC 7, SPEC 8) in headless hython.

One posed RGBD fixture frame -> the HD1 physical cloud (``synapse.worldlabs.physical``,
pure numpy) -> SOP points with ``pscale`` and ``Cd`` -> a VDB surface -> polygons -> a
static collider -> three spheres released through a SOP-level Bullet solve -> one
``.usdc`` per variant, written, re-opened and counted.

Paths are arguments; nothing is hardcoded. Every node type, parm and menu token the
probe uses is asserted on a fresh live instance before it is used (V0), and the ledger
records each live default the probe kept or changed, and why. The probe prints numbers
beside their truth. It never judges them: SPEC 9's tolerances belong to D-1.

Run on the pinned build (Houdini 22.0.400 hython, isolated prefs, never ``-I``):

    "$HYPYTHON" -s -P harness/probes/hd1_physical_frame.py --verify \
        --repo   <checkout holding python/synapse/worldlabs/physical and tests/fixtures/hd1_scene.py> \
        --out    <output folder outside the repo> \
        --run-id <folder name for this run> --variants A C

    "$HYPYTHON" -s -P harness/probes/hd1_physical_frame.py --v0-only --repo <...> --out <...> --run-id <...>

Receipts (no ``hou``; plain Python is enough):

    python harness/probes/hd1_physical_frame.py --finalize --out <...> --runs <run-id> [...] \
        --notes <checkout>/harness/notes/hd1

``--verify`` and ``--v0-only`` exit 1 when any step fails, after recording every failure
with its error. ``--finalize`` writes ``metrics.json`` and ``hashes.sha256`` under
``--notes``: the sha256 of every file in the named run folders, and of metrics.json.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import re
import sys
import time
import traceback

PRODUCER = "harness/probes/hd1_physical_frame.py"
SCHEMA = "hd1-m3-probe/1"
PINNED_BUILD = "22.0.400"

# SPEC 7. The settle threshold is "a small threshold" in the SPEC: this value is the
# probe's proposal, printed beside the measured speed so D-1 can rule on any other.
FRAMES = 120
FPS = 24.0
SETTLE_FRAMES = 12
SETTLE_SPEED_MPS = 0.01
USD_PRIMS_AUTHORED = 4          # /HD1_<v>, /HD1_<v>/geo, .../geo/points, .../geo/collider

NODE_TYPES = ("file", "vdbfromparticles", "convertvdb", "sphere", "pack", "name", "merge",
              "rbdbulletsolver", "attribwrangle", "grid")

# The parm plan: (node type, parm, action, value, why). "set" changes a live default,
# "keep" asserts the parm exists and records its live default, "expect" also asserts the
# default equals ``value``. Menu tokens are asserted against the live menu.
PARM_PLAN = (
    ("file", "file", "set", "<run>/<variant>/points_<variant>.bgeo.sc",
     "SPEC 7.1: SOP points from the cloud, read back from the probe's own bgeo"),
    ("vdbfromparticles", "voxelsize", "set", "min(pscale) / minvoxelradius",
     "the live default (0.1) is far above the footprint radii; particles under "
     "minvoxelradius voxels are culled, so the default would drop the observation"),
    ("vdbfromparticles", "minvoxelradius", "keep", None, "the voxel rule's divisor, live default kept"),
    ("vdbfromparticles", "radiusscale", "expect", 1.0, "pscale is the SPEC 6 footprint, unscaled"),
    ("vdbfromparticles", "builddistance", "expect", 1, "an SDF surface"),
    ("vdbfromparticles", "distancename", "keep", None, "the SDF grid's name"),
    ("vdbfromparticles", "footprint", "expect", 0, "sphere footprint (menu index 0 = sphere)"),
    ("vdbfromparticles", "bandwidthvoxels", "keep", None, "narrow band, live default"),
    ("convertvdb", "conversion", "set", "poly", "SPEC 7.2: VDB surface -> polygons"),
    ("convertvdb", "isovalue", "expect", 0.0, "the zero crossing of the SDF"),
    ("convertvdb", "adaptivity", "expect", 0.0, "no polygon reduction"),
    ("sphere", "type", "keep", None, "primitive type, live default"),
    ("sphere", "rad", "set", "(r, r, r), r = SPEC 7 sphere radius", "SPEC 7.3: radius 0.1 m"),
    ("sphere", "t", "set", "the site's release point", "SPEC 7.3: 0.5 m above each site"),
    ("pack", "pivot", "keep", None, "pivot location, live default (centroid)"),
    ("name", "class", "expect", 0, "primitive names (menu index 0 = primitive)"),
    ("name", "name1", "set", "S1 | S2 | S3", "one named piece per site"),
    ("rbdbulletsolver", "collision_bullet_georep", "set", "concave",
     "the live default (convexhull) would close the collider over the unobserved floor "
     "behind the box; SPEC 7 asks for the static collider the VDB surface describes"),
    ("rbdbulletsolver", "collision_initialstate", "set", "static",
     "SPEC 7.3: a static collider; the live default is animatedstatic"),
    ("rbdbulletsolver", "useground", "expect", 0, "menu index 0 = None: no ground plane under S3"),
    ("rbdbulletsolver", "usecollisions", "expect", 1, "input 4 is used as collision geometry"),
    ("rbdbulletsolver", "startframe", "expect", 1, "the solve starts on frame 1"),
    ("rbdbulletsolver", "solvefirstframe", "keep", None, "frame 1 is the release state"),
    ("rbdbulletsolver", "substep", "keep", None, "global substeps, live default"),
    ("rbdbulletsolver", "substeps", "keep", None, "Bullet substeps, live default"),
    ("rbdbulletsolver", "timescale", "keep", None, "live default"),
    ("rbdbulletsolver", "scale", "keep", None, "Bullet world scale, live default"),
    ("rbdbulletsolver", "addgravity", "keep", None, "live default"),
    ("rbdbulletsolver", "gravityy", "keep", None, "live default"),
    ("rbdbulletsolver", "margin", "keep", None, "piece collision padding, live default (part of the bias)"),
    ("rbdbulletsolver", "collision_margin", "keep", None,
     "collider collision padding, live default (part of the bias)"),
    ("rbdbulletsolver", "bounce", "keep", None, "live default"),
    ("rbdbulletsolver", "friction", "keep", None, "live default"),
    ("rbdbulletsolver", "collision_bounce", "keep", None, "live default"),
    ("rbdbulletsolver", "collision_friction", "keep", None, "live default"),
    ("rbdbulletsolver", "density", "keep", None, "live default"),
    ("rbdbulletsolver", "bullet_linear_sleep_threshold", "keep", None, "live default"),
    ("rbdbulletsolver", "sleepingtime", "keep", None, "live default"),
    ("attribwrangle", "class", "set", "vertex | primitive",
     "USD export only: the collider's topology as int arrays (no physics effect)"),
    ("attribwrangle", "snippet", "set", "vertexpoint / primvertexcount", "USD export only"),
)
MENU_TOKENS = {("convertvdb", "conversion"): "poly",
               ("rbdbulletsolver", "collision_bullet_georep"): "concave",
               ("rbdbulletsolver", "collision_initialstate"): "static",
               ("attribwrangle", "class"): ("vertex", "primitive")}
INPUT_LABELS = {("rbdbulletsolver", 0): "Geometry", ("rbdbulletsolver", 3): "Collision Geometry",
                ("vdbfromparticles", 0): "Particles to Convert"}

HOU_CALLS = ("hou.setFps", "hou.fps", "hou.setFrame", "hou.frame", "hou.expandString",
             "hou.Geometry.createPoints", "hou.Geometry.addAttrib",
             "hou.Geometry.setPointFloatAttribValuesFromString",
             "hou.Geometry.pointFloatAttribValuesAsString",
             "hou.Geometry.vertexIntAttribValuesAsString",
             "hou.Geometry.primIntAttribValuesAsString", "hou.Geometry.saveToFile",
             "hou.Geometry.intrinsicValue", "hou.Geometry.countPrimType",
             "hou.Geometry.boundingBox", "hou.Geometry.findPointAttrib", "hou.Prim.intrinsicNames",
             "hou.Prim.intrinsicValue", "hou.Prim.attribValue", "hou.Vertex.point",
             "hou.Polygon.normal", "hou.primType.Polygon", "hou.attribType.Point",
             "hou.sopNodeTypeCategory", "hou.nodeType")
NODE_METHODS = ("cook", "geometry", "setInput", "inputLabels", "warnings", "errors", "parm",
                "parmTuple")
PXR_CALLS = ("Usd.Stage.CreateNew", "Usd.Stage.Open", "Usd.Stage.Traverse", "Usd.Stage.TraverseAll",
             "Usd.Stage.SetDefaultPrim", "Usd.ModelAPI.SetKind", "Usd.ModelAPI.GetKind",
             "Usd.Prim.SetCustomDataByKey", "Usd.Prim.GetCustomDataByKey",
             "Usd.Prim.GetAppliedSchemas", "UsdGeom.Xform.Define", "UsdGeom.Scope.Define",
             "UsdGeom.Points.Define", "UsdGeom.Mesh.Define", "UsdGeom.SetStageUpAxis",
             "UsdGeom.GetStageUpAxis", "UsdGeom.SetStageMetersPerUnit",
             "UsdGeom.GetStageMetersPerUnit", "UsdGeom.StageHasAuthoredMetersPerUnit",
             "UsdGeom.Tokens.y", "UsdGeom.Tokens.proxy", "UsdGeom.Tokens.vertex",
             "UsdGeom.Tokens.none", "UsdGeom.Tokens.leftHanded", "UsdGeom.Tokens.rightHanded",
             "Kind.Tokens.component", "Vt.Vec3fArray.FromNumpy", "Vt.IntArray.FromNumpy",
             "Vt.FloatArray.FromNumpy", "Vt.StringArray", "Vt.Vec3fArray", "Gf.Quatd", "Gf.Vec3f",
             "Gf.Vec3d", "UsdGeom.PointBased.CreatePointsAttr", "UsdGeom.Points.CreateWidthsAttr",
             "UsdGeom.Points.SetWidthsInterpolation", "UsdGeom.Gprim.CreateDisplayColorPrimvar",
             "UsdGeom.Mesh.CreateFaceVertexCountsAttr", "UsdGeom.Mesh.CreateFaceVertexIndicesAttr",
             "UsdGeom.Mesh.CreateOrientationAttr", "UsdGeom.Mesh.CreateSubdivisionSchemeAttr",
             "UsdGeom.Imageable.CreatePurposeAttr", "UsdGeom.Boundable.CreateExtentAttr")

hou = None  # imported lazily: --finalize runs without Houdini


# ---------------------------------------------------------------------------
# recording
# ---------------------------------------------------------------------------

def _utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _short(value, limit=220) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


def _num(value):
    if isinstance(value, float):
        return "%.9g" % value
    return str(value)


class Recorder:
    """Checks and metrics for one run. A failed check records its error; nothing stops."""

    def __init__(self):
        self.checks = []
        self.metrics = {}

    def check(self, cid, label, fn):
        t0 = time.perf_counter()
        try:
            detail = fn()
            ok = True
            trace = None
        except Exception as exc:  # noqa: BLE001 - every failure is recorded, never raised
            detail = "%s: %s" % (type(exc).__name__, exc)
            ok = False
            trace = traceback.format_exc()[-2000:]
        row = {"id": cid, "label": label, "ok": ok, "detail": detail,
               "seconds": round(time.perf_counter() - t0, 4)}
        if trace:
            row["trace"] = trace
        self.checks.append(row)
        print("[%s] %-26s %s -> %s" % ("ASSERT held" if ok else "ASSERT FAILED", cid, label,
                                       _short(detail)), flush=True)
        return ok, detail

    def metric(self, scope, key, value, truth=None, error=None, unit=None):
        entry = {"value": value}
        line = "METRIC %s %s=%s" % (scope, key, _num(value))
        if truth is not None or error is not None:
            entry["truth"] = truth
            entry["error"] = error
            line += " truth=%s error=%s" % (_num(truth), _num(error))
        if unit:
            entry["unit"] = unit
            line += " unit=%s" % unit
        self.metrics.setdefault(scope, {})[key] = entry
        print(line, flush=True)

    def failed(self):
        return [c for c in self.checks if not c["ok"]]


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, default=str, allow_nan=True)
    os.replace(tmp, path)


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _inside(child, parent) -> bool:
    child, parent = os.path.normcase(os.path.realpath(child)), os.path.normcase(os.path.realpath(parent))
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:  # different drives
        return False


# ---------------------------------------------------------------------------
# environment and the HD1 chain (pure numpy, from --repo)
# ---------------------------------------------------------------------------

def _load_hou():
    global hou
    if hou is None:
        import hou as _hou  # noqa: PLC0415 - only the hython modes need it
        hou = _hou
    return hou


def _load_chain(repo):
    for p in (os.path.join(repo, "python"), repo):
        if p not in sys.path:
            sys.path.insert(0, p)
    import numpy as np  # noqa: PLC0415
    import synapse.worldlabs.physical as physical  # noqa: PLC0415
    from tests.fixtures import hd1_scene  # noqa: PLC0415
    return np, physical, hd1_scene


def _environment(repo, out, run_dir, rec):
    h = _load_hou()
    np, physical, hd1_scene = _load_chain(repo)
    import synapse  # noqa: PLC0415
    from pxr import Usd  # noqa: PLC0415
    phys_dir = os.path.dirname(physical.__file__)
    env = {
        "utc": _utc(), "houdini": h.applicationVersionString(), "licence": str(h.licenseCategory()),
        "ui_available": h.isUIAvailable(), "home_houdini": h.homeHoudiniDirectory(),
        "hip": h.expandString("$HIP"), "cwd": os.getcwd(), "python": sys.version.split()[0],
        "numpy": np.__version__, "usd": list(Usd.GetVersion()),
        "pref_dir_env": os.environ.get("HOUDINI_USER_PREF_DIR"),
        "home_env_inside_hython": os.environ.get("HOME"),
        "argv": sys.argv, "repo": repo, "out": out, "run_dir": run_dir,
        "synapse_file": synapse.__file__, "physical_dir": phys_dir,
        "fixture_file": hd1_scene.__file__, "fixture_version": hd1_scene.FIXTURE_VERSION,
        "probe_sha256": _sha256(os.path.abspath(__file__)),
        "chain_sha256": {name: _sha256(os.path.join(phys_dir, name))
                         for name in ("__init__.py", "depth.py", "level.py", "scale.py", "cloud.py")},
        "fixture_sha256": _sha256(hd1_scene.__file__),
        "spec7": {"frames": FRAMES, "fps": FPS, "settle_frames": SETTLE_FRAMES,
                  "settle_speed_mps_proposed": SETTLE_SPEED_MPS},
    }
    rec.check("ENV-build", "the live build is the pinned one",
              lambda: _expect(env["houdini"] == PINNED_BUILD, env["houdini"]))
    rec.check("ENV-chain", "the chain and fixture load from --repo",
              lambda: _expect(_inside(synapse.__file__, repo) and _inside(hd1_scene.__file__, repo),
                              {"synapse": synapse.__file__, "fixture": hd1_scene.__file__}))
    rec.check("ENV-out", "the output folder sits outside the repo",
              lambda: _expect(not _inside(out, repo), out))
    rec.check("ENV-hip", "$HIP and the cwd sit outside the repo",
              lambda: _expect(not _inside(env["hip"], repo) and not _inside(os.getcwd(), repo),
                              {"hip": env["hip"], "cwd": os.getcwd()}))
    return env


def _expect(condition, detail):
    if not condition:
        raise AssertionError(_short(detail, 400))
    return detail


# ---------------------------------------------------------------------------
# V0: every node type, parm, menu token, input label and API call, on the live build
# ---------------------------------------------------------------------------

def _resolve(root, dotted):
    obj = root
    for part in dotted.split(".")[1:]:
        obj = getattr(obj, part)
    return obj


def v0_checks(rec):
    h = _load_hou()
    cat = h.sopNodeTypeCategory()
    net = h.node("/obj").createNode("geo", "HD1_V0")
    for child in list(net.children()):
        child.destroy()
    fresh = {}
    v0 = {"node_types": {}, "parms": [], "input_labels": {}, "hou_calls": {}, "node_methods": {},
          "pxr_calls": {}}

    for name in NODE_TYPES:
        def _type(name=name):
            nt = h.nodeType(cat, name)
            _expect(nt is not None, "hou.nodeType(Sop, %r) is None" % name)
            node = net.createNode(name, "v0_" + name)
            fresh[name] = node
            hda = nt.definition()
            info = {"type": nt.name(), "description": nt.description(),
                    "hda_library": hda.libraryFilePath() if hda is not None else None}
            v0["node_types"][name] = info
            return info
        rec.check("V0-type-" + name, "SOP %s exists and instantiates" % name, _type)

    for node_type, parm, action, value, why in PARM_PLAN:
        def _parm(node_type=node_type, parm=parm, action=action, value=value, why=why):
            node = fresh[node_type]
            p = node.parm(parm)
            tuple_parm = p is None
            if tuple_parm:
                p = node.parmTuple(parm)
            _expect(p is not None, "%s has no parm or parm tuple %r" % (node_type, parm))
            live = p.eval()
            live = list(live) if isinstance(live, tuple) else live
            row = {"node": node_type, "parm": parm, "exists": True, "tuple": tuple_parm,
                   "live_default": live, "action": action, "probe_value": value, "why": why}
            if not tuple_parm:
                try:  # hou raises OperationFailed on a parm that has no menu
                    items = list(p.menuItems() or ())
                    labels = list(p.menuLabels() or ())
                except h.OperationFailed:
                    items, labels = [], []
                if items:
                    row["menu"] = items
                    row["menu_labels"] = labels
                token = MENU_TOKENS.get((node_type, parm))
                for tok in ((token,) if isinstance(token, str) else (token or ())):
                    _expect(tok in items, "%s.%s menu lacks %r: %s" % (node_type, parm, tok, items))
                if action == "expect":
                    _expect(live == value, "%s.%s live default %r, expected %r" % (node_type, parm, live, value))
                if (node_type, parm) == ("rbdbulletsolver", "useground"):
                    label = row["menu_labels"][row["menu"].index(str(live))]
                    row["live_default_label"] = label
                    _expect(label == "None", "useground default label is %r" % label)
                if (node_type, parm) == ("rbdbulletsolver", "collision_initialstate"):
                    row["live_default_token"] = items[live]
                if (node_type, parm) == ("convertvdb", "conversion"):
                    row["live_default_token"] = items[live]
            v0["parms"].append(row)
            return {k: row[k] for k in ("live_default", "action") if k in row}
        rec.check("V0-parm-%s.%s" % (node_type, parm), "%s.%s exists (%s)" % (node_type, parm, action), _parm)

    for (node_type, index), label in INPUT_LABELS.items():
        def _label(node_type=node_type, index=index, label=label):
            labels = list(fresh[node_type].inputLabels())
            v0["input_labels"][node_type] = labels
            _expect(len(labels) > index and labels[index] == label,
                    "%s input %d is %r, expected %r" % (node_type, index, labels, label))
            return labels[index]
        rec.check("V0-input-%s-%d" % (node_type, index), "%s input %d label" % (node_type, index), _label)

    def _calls():
        missing = []
        for dotted in HOU_CALLS:
            try:
                _resolve(h, dotted)
                v0["hou_calls"][dotted] = True
            except AttributeError:
                v0["hou_calls"][dotted] = False
                missing.append(dotted)
        node = fresh["null"] if "null" in fresh else fresh["merge"]
        for method in NODE_METHODS:
            present = hasattr(node, method)
            v0["node_methods"][method] = {"present": present, "on": type(node).__name__}
            if not present:
                missing.append("<SopNode>.%s" % method)
        _expect(not missing, {"missing": missing})
        return "%d hou calls + %d node methods present" % (len(HOU_CALLS), len(NODE_METHODS))
    rec.check("V0-hou-calls", "every hou call the probe makes exists", _calls)

    def _pxr():
        from pxr import Usd, UsdGeom, Sdf, Vt, Gf, Kind  # noqa: F401,PLC0415
        mods = {"Usd": Usd, "UsdGeom": UsdGeom, "Sdf": Sdf, "Vt": Vt, "Gf": Gf, "Kind": Kind}
        missing = []
        for dotted in PXR_CALLS:
            head, *rest = dotted.split(".")
            obj = mods[head]
            try:
                for part in rest:
                    obj = getattr(obj, part)
                v0["pxr_calls"][dotted] = True
            except AttributeError:
                v0["pxr_calls"][dotted] = False
                missing.append(dotted)
        _expect(not missing, {"missing": missing})
        return "%d pxr calls present" % len(PXR_CALLS)
    rec.check("V0-pxr-calls", "every pxr call the probe makes exists", _pxr)

    def _winding():
        grid = fresh["grid"]
        g = grid.geometry()
        prim = g.prims()[0]
        pts = [v.point().position() for v in prim.vertices()]
        a, b, c = pts[0], pts[1], pts[2]
        rh = (b - a).cross(c - a)
        hn = prim.normal()
        dot = rh.dot(hn)
        token = "leftHanded" if dot < 0 else "rightHanded"
        v0["winding"] = {"houdini_normal": list(hn), "right_hand_cross": list(rh), "dot": dot,
                         "usd_orientation": token}
        _expect(abs(dot) > 0.0, "degenerate grid polygon")
        return token
    ok, token = rec.check("V0-winding", "Houdini polygon winding vs USD orientation (grid SOP)", _winding)
    v0["usd_orientation"] = token if ok else None

    def _topology():
        import numpy as np  # noqa: PLC0415
        w_v, w_p = _topology_wrangles(net, fresh["grid"], "v0")
        g = w_p.geometry()
        counts = np.frombuffer(g.primIntAttribValuesAsString("hd1_nv"), dtype=np.int32)
        index = np.frombuffer(g.vertexIntAttribValuesAsString("hd1_pt"), dtype=np.int32)
        slow = [[v.point().number() for v in prim.vertices()] for prim in g.prims()]
        _expect(counts.tolist() == [len(s) for s in slow], "vertex counts differ from the slow path")
        _expect(index.tolist() == [i for s in slow for i in s], "vertex indices differ from the slow path")
        return "fast topology == slow path on %d polygons" % len(slow)
    rec.check("V0-topology", "the collider's USD topology path agrees with hou.Prim.vertices()", _topology)
    return v0


def _topology_wrangles(net, source, tag):
    w_v = net.createNode("attribwrangle", "topo_vtx_" + tag)
    w_v.setInput(0, source)
    w_v.parm("class").set(list(w_v.parm("class").menuItems()).index("vertex"))
    w_v.parm("snippet").set("i@hd1_pt = vertexpoint(0, @vtxnum);")
    w_p = net.createNode("attribwrangle", "topo_prim_" + tag)
    w_p.setInput(0, w_v)
    w_p.parm("class").set(list(w_p.parm("class").menuItems()).index("primitive"))
    w_p.parm("snippet").set("i@hd1_nv = primvertexcount(0, @primnum);")
    w_p.cook(force=True)
    errors = list(w_v.errors()) + list(w_p.errors())
    if errors:
        raise RuntimeError("topology wrangles: %s" % errors)
    return w_v, w_p


# ---------------------------------------------------------------------------
# one variant
# ---------------------------------------------------------------------------

def _set_menu(parm, token):
    items = list(parm.menuItems())
    if parm.parmTemplate().type().name() == "String":
        parm.set(token)
    else:
        parm.set(items.index(token))
    return items.index(token)


def run_variant(name, repo, run_dir, voxel_override, orientation, rec, record_path):
    h = _load_hou()
    np, physical, hd1_scene = _load_chain(repo)
    from pxr import Usd, UsdGeom, Vt, Gf, Kind  # noqa: PLC0415
    vdir = os.path.join(run_dir, name)
    os.makedirs(vdir, exist_ok=True)
    record = {"variant": name, "started_utc": _utc()}
    state = {}
    scope = name

    def save():
        record["checks"] = [c for c in rec.checks if c["id"].startswith(name + "-")]
        record["metrics"] = rec.metrics.get(scope, {})
        _write_json(record_path, record)

    # 1. the chain: scale, then level, then ground, as HD1-M2 landed it
    def _chain():
        v = hd1_scene.variant(name)
        mask = physical.condition_depth(v.depth, v.confidence)
        raw = physical.unproject_raw(v.frame, v.depth, mask.keep)
        fit = physical.floor_of(raw)
        _expect(fit.status == "SUCCESS", {"floor": fit.status, "reason": fit.reason})
        claim = physical.from_camera_height(v.truth.declared_eye_height_m, fit)
        cloud = physical.physical_cloud(v.frame, v.depth, mask.keep, claim, fit, colour=v.colour)
        _expect(cloud.points_m.shape[0] <= cloud.point_cap, "cap exceeded")
        state.update(v=v, mask=mask, fit=fit, claim=claim, cloud=cloud)
        t = v.truth
        record["truth"] = t.as_dict()
        record["fixture_digest"] = hd1_scene.fixture_digest(v)
        record["mask"] = {"kept": mask.kept, "total": mask.total, "dropped": mask.dropped}
        record["floor"] = fit.as_dict()
        record["claim"] = claim.as_record()
        record["cloud"] = cloud.describe()
        s_true = t.metres_per_unit
        rec.metric(scope, "chain.grid", list(t.grid))
        rec.metric(scope, "chain.mask_kept", mask.kept)
        rec.metric(scope, "chain.mask_total", mask.total)
        rec.metric(scope, "chain.floor_inlier_fraction", fit.inlier_fraction)
        rec.metric(scope, "chain.floor_rms_over_median_depth", fit.rms_over_median_depth)
        rec.metric(scope, "chain.level_angle_to_truth_deg",
                   physical.quaternion_angle_deg(fit.level_xyzw, t.level_xyzw), truth=0.0,
                   error=physical.quaternion_angle_deg(fit.level_xyzw, t.level_xyzw), unit="deg")
        rec.metric(scope, "chain.tilt_deg", fit.tilt_deg, truth=t.tilt_deg,
                   error=fit.tilt_deg - t.tilt_deg, unit="deg")
        rec.metric(scope, "chain.floor_height_units", fit.floor_height, truth=t.floor_height_units,
                   error=fit.floor_height - t.floor_height_units, unit="raw units")
        rec.metric(scope, "chain.camera_height_units", fit.camera_height, truth=t.camera_height_units,
                   error=fit.camera_height - t.camera_height_units, unit="raw units")
        rec.metric(scope, "chain.scale_claim_m_per_unit", claim.value, truth=s_true,
                   error=claim.value - s_true, unit="m/unit")
        rec.metric(scope, "chain.scale_claim_rel_error", (claim.value - s_true) / s_true, unit="ratio")
        rec.metric(scope, "chain.ground_offset_m", cloud.ground_offset_m,
                   truth=t.ground_offset_units * s_true,
                   error=cloud.ground_offset_m - t.ground_offset_units * s_true, unit="m")
        rec.metric(scope, "cloud.stride", cloud.stride)
        rec.metric(scope, "cloud.points", int(cloud.points_m.shape[0]))
        rec.metric(scope, "cloud.points_before_cap", cloud.points_before_cap)
        rec.metric(scope, "cloud.radius_min_m", float(cloud.radius_m.min()), unit="m")
        rec.metric(scope, "cloud.radius_median_m", float(np.median(cloud.radius_m)), unit="m")
        rec.metric(scope, "cloud.radius_max_m", float(cloud.radius_m.max()), unit="m")
        return {"stride": cloud.stride, "points": int(cloud.points_m.shape[0]),
                "claim": claim.provenanced_number()}
    ok, _ = rec.check(name + "-1-chain", "variant %s: depth -> floor -> claim -> physical cloud" % name, _chain)
    save()
    if not ok:
        return record

    net = h.node("/obj").createNode("geo", "HD1_%s" % name)
    for child in list(net.children()):
        child.destroy()

    # 2. SOP points: P, pscale (the footprint radius), Cd
    def _points():
        cloud = state["cloud"]
        P = np.ascontiguousarray(cloud.points_m, dtype=np.float32)
        R = np.ascontiguousarray(cloud.radius_m, dtype=np.float32)
        g = h.Geometry()
        g.createPoints(P.tolist())
        g.setPointFloatAttribValuesFromString("P", P.tobytes())
        g.addAttrib(h.attribType.Point, "pscale", 0.0)
        g.setPointFloatAttribValuesFromString("pscale", R.tobytes())
        if cloud.colour is not None:
            g.addAttrib(h.attribType.Point, "Cd", (1.0, 1.0, 1.0))
            g.setPointFloatAttribValuesFromString(
                "Cd", np.ascontiguousarray(cloud.colour, dtype=np.float32).tobytes())
        path = os.path.join(vdir, "points_%s.bgeo.sc" % name).replace("\\", "/")
        g.saveToFile(path)
        node = net.createNode("file", "points")
        node.parm("file").set(path)
        node.cook(force=True)
        got = node.geometry()
        back = np.frombuffer(got.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
        _expect(back.shape == P.shape and np.array_equal(back, P), "P did not round-trip through bgeo")
        rb = np.frombuffer(got.pointFloatAttribValuesAsString("pscale"), dtype=np.float32)
        _expect(np.array_equal(rb, R), "pscale did not round-trip")
        _expect(cloud.colour is None or got.findPointAttrib("Cd") is not None, "Cd missing")
        state.update(points_node=node, P=P, R=R)
        record["points_sop"] = {"path": path, "count": got.pointCount(),
                                "attribs": [a.name() for a in got.pointAttribs()]}
        rec.metric(scope, "points.sop_count", got.pointCount())
        return record["points_sop"]
    ok, _ = rec.check(name + "-2-points", "SOP points with pscale and Cd, bit-exact after bgeo", _points)
    save()
    if not ok:
        return record

    # 3. collider: points -> VDB surface -> polygons
    def _collider():
        R = state["R"]
        default_node = net.createNode("vdbfromparticles", "collider_vdb_live_default")
        default_node.setInput(0, state["points_node"])
        t0 = time.perf_counter()
        default_node.cook(force=True)
        d_secs = time.perf_counter() - t0
        record["vdb_at_live_default"] = {
            "voxelsize": default_node.parm("voxelsize").eval(),
            "seconds": d_secs, "vdb": _vdb_info(default_node.geometry()),
            "warnings": list(default_node.warnings()), "errors": list(default_node.errors())}
        default_node.destroy()

        vdb = net.createNode("vdbfromparticles", "collider_vdb")
        vdb.setInput(0, state["points_node"])
        minvr = vdb.parm("minvoxelradius").eval()
        rule = "min(pscale) / minvoxelradius (live default %s)" % minvr
        voxel = float(voxel_override) if voxel_override else float(R.min()) / float(minvr)
        vdb.parm("voxelsize").set(voxel)
        t0 = time.perf_counter()
        vdb.cook(force=True)
        t_vdb = time.perf_counter() - t0
        poly = net.createNode("convertvdb", "collider_poly")
        poly.setInput(0, vdb)
        _set_menu(poly.parm("conversion"), "poly")
        t0 = time.perf_counter()
        poly.cook(force=True)
        t_poly = time.perf_counter() - t0
        errs = list(vdb.errors()) + list(poly.errors())
        _expect(not errs, errs)
        mg = poly.geometry()
        prims = mg.intrinsicValue("primitivecount")
        verts = mg.intrinsicValue("vertexcount")
        polys = mg.countPrimType(h.primType.Polygon)
        _expect(prims > 0, "the collider has no polygons")
        _expect(polys == prims, "non-polygon prims in the collider: %d of %d" % (prims - polys, prims))
        bb = mg.boundingBox()
        info = {"voxel_size_m": voxel, "voxel_rule": "override" if voxel_override else rule,
                "minvoxelradius": minvr, "vdb": _vdb_info(vdb.geometry()),
                "vdb_warnings": list(vdb.warnings()), "poly_warnings": list(poly.warnings()),
                "points": mg.intrinsicValue("pointcount"), "polygons": prims, "vertices": verts,
                "triangles": verts - 2 * prims,
                "bounds_m": {"min": list(bb.minvec()), "max": list(bb.maxvec())},
                "cook_s": {"vdbfromparticles": t_vdb, "convertvdb": t_poly, "total": t_vdb + t_poly}}
        record["collider"] = info
        state.update(poly_node=poly, collider_min_y=bb.minvec()[1])
        rec.metric(scope, "collider.voxel_size_m", voxel, unit="m")
        rec.metric(scope, "collider.vdb_active_voxels", info["vdb"].get("activevoxelcount"))
        rec.metric(scope, "collider.polygons", prims)
        rec.metric(scope, "collider.triangles", verts - 2 * prims)
        rec.metric(scope, "collider.points", info["points"])
        for axis, i in (("x", 0), ("y", 1), ("z", 2)):
            rec.metric(scope, "collider.bounds_min_%s_m" % axis, bb.minvec()[i], unit="m")
            rec.metric(scope, "collider.bounds_max_%s_m" % axis, bb.maxvec()[i], unit="m")
        rec.metric(scope, "collider.cook_vdbfromparticles_s", t_vdb, unit="s")
        rec.metric(scope, "collider.cook_convertvdb_s", t_poly, unit="s")
        rec.metric(scope, "collider.cook_total_s", t_vdb + t_poly, unit="s")
        rec.metric(scope, "collider.vdb_at_live_default_active_voxels",
                   record["vdb_at_live_default"]["vdb"].get("activevoxelcount"))
        return {k: info[k] for k in ("voxel_size_m", "polygons", "triangles", "cook_s")}
    ok, _ = rec.check(name + "-3-collider", "vdbfromparticles -> convertvdb polygons", _collider)
    save()
    if not ok:
        return record

    # 4. USD: one .usdc, written, re-opened, counted (SPEC 8)
    def _usd():
        cloud, claim, v = state["cloud"], state["claim"], state["v"]
        w_v, w_p = _topology_wrangles(net, state["poly_node"], name)
        g = w_p.geometry()
        counts = np.frombuffer(g.primIntAttribValuesAsString("hd1_nv"), dtype=np.int32)
        index = np.frombuffer(g.vertexIntAttribValuesAsString("hd1_pt"), dtype=np.int32)
        mp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
        _expect(int(counts.sum()) == index.size == g.intrinsicValue("vertexcount"), "topology sizes")
        _expect(index.min() >= 0 and index.max() < mp.shape[0], "indices out of range")
        _expect(orientation in ("leftHanded", "rightHanded"), "winding unknown: %r" % orientation)
        path = os.path.join(vdir, "hd1_%s.usdc" % name).replace("\\", "/")
        _expect(not os.path.exists(path), "refusing to overwrite %s" % path)
        root_path = "/HD1_%s" % name
        stage = Usd.Stage.CreateNew(path)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        applied = dict(cloud.applied)
        if applied.get("scale"):
            UsdGeom.SetStageMetersPerUnit(stage, 1.0)  # SPEC 8: only when a claim was applied
        root = UsdGeom.Xform.Define(stage, root_path)
        stage.SetDefaultPrim(root.GetPrim())
        Usd.ModelAPI(root.GetPrim()).SetKind(Kind.Tokens.component)
        number = claim.provenanced_number()
        null_keys = sorted(k for k, val in number.items() if val is None)
        x, y, z, w = cloud.level_xyzw
        hd1 = {"tier": cloud.evidence_tier,
               "scale": {k: val for k, val in number.items() if val is not None},
               "level": Gf.Quatd(w, Gf.Vec3d(x, y, z)),
               "ground_offset": float(cloud.ground_offset_m),
               "applied": {k: bool(val) for k, val in applied.items()},
               "stride": int(cloud.stride),
               "fixture_sha256": record["fixture_digest"]}
        if null_keys:
            hd1["scale_null_keys"] = Vt.StringArray(null_keys)  # USD dictionaries cannot hold None
        root.GetPrim().SetCustomDataByKey("synapse:hd1", hd1)
        UsdGeom.Scope.Define(stage, root_path + "/geo")
        P, R = state["P"], state["R"]
        pts = UsdGeom.Points.Define(stage, root_path + "/geo/points")
        pts.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P))
        pts.CreateWidthsAttr(Vt.FloatArray.FromNumpy(np.ascontiguousarray(2.0 * R, dtype=np.float32)))
        pts.SetWidthsInterpolation(UsdGeom.Tokens.vertex)
        if cloud.colour is not None:
            pts.CreateDisplayColorPrimvar(UsdGeom.Tokens.vertex).Set(
                Vt.Vec3fArray.FromNumpy(np.ascontiguousarray(cloud.colour, dtype=np.float32)))
        lo, hi = (P - R[:, None]).min(axis=0), (P + R[:, None]).max(axis=0)
        pts.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, lo)), Gf.Vec3f(*map(float, hi))]))
        mesh = UsdGeom.Mesh.Define(stage, root_path + "/geo/collider")
        mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(np.ascontiguousarray(mp)))
        mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.ascontiguousarray(counts)))
        mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(np.ascontiguousarray(index)))
        mesh.CreateOrientationAttr(getattr(UsdGeom.Tokens, orientation))
        mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        mesh.CreatePurposeAttr(UsdGeom.Tokens.proxy)
        mlo, mhi = mp.min(axis=0), mp.max(axis=0)
        mesh.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float, mlo)), Gf.Vec3f(*map(float, mhi))]))
        t0 = time.perf_counter()
        stage.GetRootLayer().Save()
        t_save = time.perf_counter() - t0
        del stage

        t0 = time.perf_counter()
        st = Usd.Stage.Open(path)
        t_open = time.perf_counter() - t0
        listed = [p.GetPath().pathString for p in st.Traverse()]
        listed_all = [p.GetPath().pathString for p in st.TraverseAll()]
        rp = st.GetPrimAtPath(root_path)
        back = rp.GetCustomDataByKey("synapse:hd1")
        q = back["level"]
        q_xyzw = [q.GetImaginary()[0], q.GetImaginary()[1], q.GetImaginary()[2], q.GetReal()]
        cpts = UsdGeom.Points(st.GetPrimAtPath(root_path + "/geo/points"))
        cmesh = UsdGeom.Mesh(st.GetPrimAtPath(root_path + "/geo/collider"))
        physics = [p.GetPath().pathString for p in st.TraverseAll()
                   if p.GetTypeName().startswith("Physics")
                   or any(s.startswith("Physics") for s in p.GetAppliedSchemas())]
        info = {"path": path, "bytes": os.path.getsize(path), "save_s": t_save, "open_s": t_open,
                "prims_traverse": len(listed), "prims_all": len(listed_all), "prim_paths": listed_all,
                "up_axis": str(UsdGeom.GetStageUpAxis(st)),
                "meters_per_unit_authored": bool(UsdGeom.StageHasAuthoredMetersPerUnit(st)),
                "meters_per_unit": UsdGeom.GetStageMetersPerUnit(st),
                "kind": str(Usd.ModelAPI(rp).GetKind()), "default_prim": str(st.GetDefaultPrim().GetPath()),
                "custom_data_keys": sorted(back.keys()), "level_xyzw_back": q_xyzw,
                "stride_back": back["stride"], "tier_back": back["tier"],
                "scale_back": dict(back["scale"]), "applied_back": dict(back["applied"]),
                "points_back": len(cpts.GetPointsAttr().Get()),
                "collider_faces_back": len(cmesh.GetFaceVertexCountsAttr().Get()),
                "collider_points_back": len(cmesh.GetPointsAttr().Get()),
                "collider_purpose": str(cmesh.GetPurposeAttr().Get()),
                "collider_orientation": str(cmesh.GetOrientationAttr().Get()),
                "physics_prims_or_schemas": physics, "scale_null_keys": null_keys}
        record["usd"] = info
        _expect(len(listed_all) == USD_PRIMS_AUTHORED, "prim count %d" % len(listed_all))
        _expect(info["up_axis"] == "Y", info["up_axis"])
        _expect(info["meters_per_unit_authored"] and info["meters_per_unit"] == 1.0, "metersPerUnit")
        _expect(info["kind"] == "component", info["kind"])
        _expect(max(abs(a - b) for a, b in zip(q_xyzw, cloud.level_xyzw)) < 1e-12, "level quaternion")
        _expect(info["points_back"] == P.shape[0], "points count")
        _expect(info["collider_faces_back"] == counts.size, "face count")
        _expect(info["collider_purpose"] == "proxy", "purpose")
        _expect(not physics, physics)
        rec.metric(scope, "usd.prims_traverse", len(listed))
        rec.metric(scope, "usd.prims_all", len(listed_all))
        rec.metric(scope, "usd.bytes", info["bytes"])
        rec.metric(scope, "usd.points", info["points_back"])
        rec.metric(scope, "usd.collider_faces", info["collider_faces_back"])
        rec.metric(scope, "usd.collider_points", info["collider_points_back"])
        rec.metric(scope, "usd.save_s", t_save, unit="s")
        rec.metric(scope, "usd.open_s", t_open, unit="s")
        w_v.destroy()
        w_p.destroy()
        return {k: info[k] for k in ("path", "prims_all", "bytes")}
    rec.check(name + "-4-usd", "write the .usdc, re-open it, count the prims (SPEC 8)", _usd)
    save()

    # 5. rest test: a 0.1 m sphere released 0.5 m above each site, static collider, Bullet
    def _rest():
        v = state["v"]
        h.setFps(FPS)
        _expect(abs(h.fps() - FPS) < 1e-9, "fps is %s" % h.fps())
        merge = net.createNode("merge", "spheres")
        for i, site in enumerate(v.truth.sites):
            r = float(site.sphere_radius_m)
            sp = net.createNode("sphere", "sphere_" + site.name)
            sp.parmTuple("rad").set((r, r, r))
            sp.parmTuple("t").set(tuple(float(c) for c in site.release_final_m))
            pk = net.createNode("pack", "pack_" + site.name)
            pk.setInput(0, sp)
            nm = net.createNode("name", "name_" + site.name)
            nm.setInput(0, pk)
            nm.parm("name1").set(site.name)
            merge.setInput(i, nm)
        sol = net.createNode("rbdbulletsolver", "rest")
        sol.setInput(0, merge)
        sol.setInput(3, state["poly_node"])
        _set_menu(sol.parm("collision_bullet_georep"), "concave")
        _set_menu(sol.parm("collision_initialstate"), "static")
        settings = {p: sol.parm(p).eval() for p in (
            "collision_bullet_georep", "collision_initialstate", "useground", "usecollisions",
            "startframe", "solvefirstframe", "substep", "substeps", "timescale", "margin",
            "collision_margin", "bounce", "friction", "collision_bounce", "collision_friction",
            "gravityy", "density")}
        settings["collision_initialstate_token"] = list(
            sol.parm("collision_initialstate").menuItems())[settings["collision_initialstate"]]
        record["rest_settings"] = settings
        _expect(settings["collision_bullet_georep"] == "concave", settings["collision_bullet_georep"])
        _expect(settings["collision_initialstate_token"] == "static", settings["collision_initialstate_token"])
        _expect(settings["useground"] == 0, "useground %s" % settings["useground"])
        names = [s.name for s in v.truth.sites]
        traj = {n: [] for n in names}
        vel = {n: [] for n in names}
        t0 = time.perf_counter()
        for frame in range(1, FRAMES + 1):
            h.setFrame(frame)
            g = sol.geometry()
            errs = list(sol.errors())
            _expect(not errs, {"frame": frame, "errors": errs})
            has_v = g.findPointAttrib("v") is not None
            seen = set()
            for prim in g.prims():
                n = prim.attribValue("name")
                pt = prim.vertices()[0].point()
                traj[n].append(list(pt.position()))
                vel[n].append(list(pt.attribValue("v")) if has_v else None)
                seen.add(n)
            _expect(seen == set(names), {"frame": frame, "pieces": sorted(seen)})
        t_sim = time.perf_counter() - t0
        record["rest_solver"] = {"warnings": list(sol.warnings()), "sim_s": t_sim,
                                 "frames": FRAMES, "fps": FPS}
        rec.metric(scope, "rest.sim_s", t_sim, unit="s")
        rec.metric(scope, "rest.collision_margin_m", settings["collision_margin"], unit="m")
        rec.metric(scope, "rest.piece_margin_m", settings["margin"], unit="m")
        floor_y = state["collider_min_y"]
        sites = {}
        P, R = state["P"], state["R"]
        for site in v.truth.sites:
            n = site.name
            arr = np.asarray(traj[n], dtype=np.float64)
            _expect(arr.shape == (FRAMES, 3) and np.isfinite(arr).all(), "trajectory %s" % n)
            speed = np.linalg.norm(np.diff(arr, axis=0), axis=1) * FPS     # m/s, frames 2..FRAMES
            last = speed[-SETTLE_FRAMES:]
            final = arr[-1]
            truth = site.rest_height_m
            sx, _, sz = site.surface_final_m
            near = np.hypot(P[:, 0] - sx, P[:, 2] - sz) < 0.15
            radius = float(site.sphere_radius_m)
            rx, rz = float(site.release_final_m[0]), float(site.release_final_m[2])
            y = arr[:, 1]
            drift = np.hypot(arr[:, 0] - rx, arr[:, 2] - rz)
            # Stated rules (diagnostics, not verdicts). Indices are 0-based; frame = index + 1.
            contact = next((i + 1 for i, d in enumerate(np.diff(y)) if d >= 0.0), None)
            left = next((i for i, d in enumerate(drift) if d > radius), None)
            below = next((i for i, yy in enumerate(y) if yy < -radius), None)
            window = y[contact:(left if left is not None else FRAMES)] if contact is not None else y[:0]
            exit_xz = None if below is None else [float(arr[below, 0]), float(arr[below, 2])]
            exit_gap = None if below is None else float(
                np.hypot(P[:, 0] - exit_xz[0], P[:, 2] - exit_xz[1]).min())
            diag = {
                "rules": {"first_contact": "first frame whose centre y is not below the previous frame's",
                          "left_site": "first frame whose xz drift from release exceeds the sphere radius",
                          "on_site": "frames from first contact up to (not including) left_site",
                          "below_floor": "first frame whose centre y < -sphere radius",
                          "exit_nearest_observed_xz_m": "xz distance from the below_floor position to "
                                                        "the nearest cloud point"},
                "first_contact_frame": None if contact is None else contact + 1,
                "left_site_frame": None if left is None else left + 1,
                "on_site_frames": int(window.size),
                "on_site_height_median_m": float(np.median(window)) if window.size else None,
                "on_site_height_min_m": float(window.min()) if window.size else None,
                "on_site_height_max_m": float(window.max()) if window.size else None,
                "below_floor_frame": None if below is None else below + 1,
                "below_floor_xz_m": exit_xz, "exit_nearest_observed_xz_m": exit_gap,
                "max_drift_m": float(drift.max())}
            if truth is not None and window.size:
                diag["on_site_height_minus_truth_m"] = float(np.median(window) - truth)
            row = {"release_m": list(site.release_final_m), "final_centre_m": final.tolist(),
                   "final_height_m": float(final[1]), "truth_m": truth,
                   "error_m": None if truth is None else float(final[1] - truth),
                   "max_speed_last_frames_mps": float(last.max()), "settle_frames": SETTLE_FRAMES,
                   "settled": bool(last.max() < SETTLE_SPEED_MPS),
                   "fell_through": bool(final[1] < floor_y - site.sphere_radius_m),
                   "fell_through_rule": "final centre y < collider min y (%.6g) - sphere radius"
                                        % floor_y,
                   "lowest_height_m": float(arr[:, 1].min()),
                   "horizontal_drift_m": float(math.hypot(final[0] - site.release_final_m[0],
                                                          final[2] - site.release_final_m[2])),
                   "expect": site.expect, "observed_points_within_0.15m": int(near.sum()),
                   "pscale_median_within_0.15m": float(np.median(R[near])) if near.any() else None,
                   "trajectory_y": arr[:, 1].tolist(), "trajectory_xyz": arr.tolist(),
                   "solver_v_last": vel[n][-1], "diagnostics": diag}
            sites[n] = row
            for key in ("first_contact_frame", "left_site_frame", "on_site_frames",
                        "on_site_height_median_m", "on_site_height_min_m", "on_site_height_max_m",
                        "on_site_height_minus_truth_m", "below_floor_frame", "below_floor_xz_m",
                        "exit_nearest_observed_xz_m", "max_drift_m"):
                if key in diag:
                    rec.metric(scope, "rest.%s.%s" % (n, key), diag[key])
            rec.metric(scope, "rest.%s.final_height_m" % n, row["final_height_m"], truth=truth,
                       error=row["error_m"], unit="m")
            rec.metric(scope, "rest.%s.settled" % n, row["settled"])
            rec.metric(scope, "rest.%s.max_speed_last%d_mps" % (n, SETTLE_FRAMES),
                       row["max_speed_last_frames_mps"], unit="m/s")
            rec.metric(scope, "rest.%s.fell_through" % n, row["fell_through"])
            rec.metric(scope, "rest.%s.lowest_height_m" % n, row["lowest_height_m"], unit="m")
            rec.metric(scope, "rest.%s.horizontal_drift_m" % n, row["horizontal_drift_m"], unit="m")
            rec.metric(scope, "rest.%s.observed_points_within_0.15m" % n, row["observed_points_within_0.15m"])
            if row["pscale_median_within_0.15m"] is not None:
                rec.metric(scope, "rest.%s.pscale_median_within_0.15m" % n,
                           row["pscale_median_within_0.15m"], unit="m")
        record["rest"] = sites
        return {n: {k: sites[n][k] for k in ("final_height_m", "error_m", "settled", "fell_through")}
                for n in sites}
    rec.check(name + "-5-rest", "Bullet rest test, %d frames at %g fps, static concave collider"
              % (FRAMES, FPS), _rest)
    record["finished_utc"] = _utc()
    save()
    return record


def _vdb_info(geo):
    out = {"prims": geo.intrinsicValue("primitivecount")}
    for prim in geo.prims()[:4]:
        names = list(prim.intrinsicNames())
        out.setdefault("intrinsic_names", names)
        for key in names:
            if any(tag in key for tag in ("voxel", "vdb", "background", "name", "class")):
                try:
                    val = prim.intrinsicValue(key)
                    out[key] = val if isinstance(val, (int, float, str, bool)) else list(val)
                except Exception as exc:  # noqa: BLE001
                    out[key] = "error: %s" % exc
    return out


# ---------------------------------------------------------------------------
# receipts
# ---------------------------------------------------------------------------

_ACCOUNT_DIR = re.compile(r"([A-Za-z]:[\\/]+Users[\\/]+)(?!Example\b)[^\\/\"'\s]+")


def _publicize(value, roots):
    """Receipts are committed to a public repository, so every path in them is written without
    this machine's layout: a path inside the repository becomes repository-relative, a path under
    one of the named roots becomes <token>/..., and any remaining account folder (Users/<name>)
    is redacted to Users/Example. Vendor install paths are kept. Applied to keys and values."""
    if isinstance(value, dict):
        return {_publicize(k, roots): _publicize(v, roots) for k, v in value.items()}
    if isinstance(value, list):
        return [_publicize(v, roots) for v in value]
    if not isinstance(value, str):
        return value
    text = value.replace("\\\\", "/").replace("\\", "/")
    for prefix, token in roots:
        p = prefix.replace("\\", "/").rstrip("/")
        for cand in (p, p.lower(), p[:1].lower() + p[1:]):
            if cand and cand in text:
                text = text.replace(cand + "/", (token + "/") if token else "").replace(cand, token or ".")
    return _ACCOUNT_DIR.sub(r"\1Example", text)


def finalize(out_root, runs, notes):
    os.makedirs(notes, exist_ok=True)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    roots = [(os.path.abspath(notes), "harness/notes/hd1"), (os.path.abspath(out_root), "<out>"),
             (os.path.dirname(os.path.abspath(out_root)), "<lane>"), (repo_root, "")]
    metrics = {"schema": SCHEMA, "producer": PRODUCER, "written_utc": _utc(), "runs": [],
               "variants": {}, "v0": None, "environment": None, "outputs": {}}
    files = []
    for run in runs:
        run_dir = os.path.join(out_root, run)
        summary_path = os.path.join(run_dir, "run.json")
        summary = json.load(open(summary_path, encoding="utf-8")) if os.path.isfile(summary_path) else None
        metrics["runs"].append({"run_id": run, "summary": None if summary is None else {
            k: summary.get(k) for k in ("mode", "variants", "started_utc", "finished_utc",
                                        "checks_total", "checks_failed", "exit_code")}})
        if summary is not None:
            if summary.get("v0"):
                metrics["v0"] = summary["v0"]
            metrics["environment"] = summary.get("environment")
        for dirpath, _, names in os.walk(run_dir):
            for fname in names:
                files.append(os.path.join(dirpath, fname))
            for fname in names:
                if fname.startswith("record_") and fname.endswith(".json"):
                    rec = json.load(open(os.path.join(dirpath, fname), encoding="utf-8"))
                    metrics["variants"][rec["variant"]] = {"run_id": run, **{k: rec.get(k) for k in (
                        "started_utc", "finished_utc", "fixture_digest", "metrics", "claim", "mask",
                        "collider", "vdb_at_live_default", "usd", "rest_settings", "rest_solver")},
                        "rest": {n: {k: val for k, val in row.items()
                                     if k not in ("trajectory_y", "trajectory_xyz")}
                                 for n, row in (rec.get("rest") or {}).items()},
                        "checks": [{k: c.get(k) for k in ("id", "label", "ok", "detail")}
                                   for c in rec.get("checks", [])]}
    for path in sorted(files):
        if path.endswith(".tmp"):
            continue
        metrics["outputs"][path.replace("\\", "/")] = {"sha256": _sha256(path),
                                                       "bytes": os.path.getsize(path)}
    metrics = _publicize(metrics, roots)
    mpath = os.path.join(notes, "metrics.json")
    tmp = mpath + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:  # LF: the bytes git stores
        json.dump(metrics, fh, indent=1, default=str, allow_nan=True)
    os.replace(tmp, mpath)
    lines = ["%s  %s" % (v["sha256"], p) for p, v in sorted(metrics["outputs"].items())]
    lines.append("%s  %s" % (_sha256(mpath), _publicize(os.path.abspath(mpath), roots)))
    hpath = os.path.join(notes, "hashes.sha256")
    with open(hpath, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote %s (%d outputs) and %s" % (mpath, len(metrics["outputs"]), hpath))
    return 0


# ---------------------------------------------------------------------------

def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true", help="V0 checks, then every step per variant")
    mode.add_argument("--v0-only", action="store_true", help="only the live V0 checks")
    mode.add_argument("--finalize", action="store_true", help="write metrics.json and hashes (no hou)")
    ap.add_argument("--repo", help="checkout holding the HD1 chain and fixture")
    ap.add_argument("--out", required=True, help="output folder, outside the repo")
    ap.add_argument("--run-id", default=None, help="this run's folder under --out")
    ap.add_argument("--variants", nargs="+", default=["A", "C"])
    ap.add_argument("--voxel-size", type=float, default=None,
                    help="override the voxel rule (recorded as an override)")
    ap.add_argument("--runs", nargs="+", default=[], help="--finalize: run folders to include")
    ap.add_argument("--notes", default=None, help="--finalize: receipts folder")
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if a.finalize:
        if not a.notes or not a.runs:
            ap.error("--finalize needs --notes and --runs")
        return finalize(out, a.runs, os.path.abspath(a.notes))
    if not a.repo:
        ap.error("--repo is required")
    repo = os.path.abspath(a.repo)
    run_id = a.run_id or _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(out, run_id)
    os.makedirs(run_dir, exist_ok=True)
    rec = Recorder()
    summary = {"schema": SCHEMA, "producer": PRODUCER, "run_id": run_id,
               "mode": "verify" if a.verify else "v0-only", "variants": a.variants,
               "started_utc": _utc()}
    summary_path = os.path.join(run_dir, "run.json")
    print("HD1 probe %s run %s variants %s" % (summary["mode"], run_id, a.variants), flush=True)
    summary["environment"] = _environment(repo, out, run_dir, rec)
    _write_json(summary_path, summary)
    summary["v0"] = v0_checks(rec)
    _write_json(summary_path, summary)
    if a.verify:
        for name in a.variants:
            record_path = os.path.join(run_dir, name, "record_%s.json" % name)
            os.makedirs(os.path.dirname(record_path), exist_ok=True)
            print("--- variant %s" % name, flush=True)
            run_variant(name, repo, run_dir, a.voxel_size, summary["v0"].get("usd_orientation"),
                        rec, record_path)
    failed = rec.failed()
    summary.update(finished_utc=_utc(), checks_total=len(rec.checks), checks_failed=len(failed),
                   checks=[{k: c.get(k) for k in ("id", "label", "ok", "detail", "seconds")}
                           for c in rec.checks],
                   exit_code=1 if failed else 0)
    _write_json(summary_path, summary)
    print("CHECKS %d asserted, %d failed, on %s" % (len(rec.checks), len(failed),
                                                    summary["environment"]["houdini"]), flush=True)
    for c in failed:
        print("  FAILED %s %s -> %s" % (c["id"], c["label"], _short(c["detail"], 400)), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
