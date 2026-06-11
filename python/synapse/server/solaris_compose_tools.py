"""
SYNAPSE Solaris Compose Tools (PRD sections 7.1 / 7.2 / 7.3).

Tool LOGIC built on the ``solaris_compose`` primitive. Each function takes the
``/stage`` LOP network node + params and returns a result dict. The thin
handler wrappers (handlers_solaris_compose.py) parse the command payload,
marshal to Houdini's main thread, and own the undo group; the panel bridge
adds audit (integrity) on top.

Recipe verified live on Houdini 21.0.671 (Mile 2 mechanism probe, 2026-05-30):
  - ``karmarendersettings`` is self-contained: engine (cpu->xpu), camera,
    resolutionx/y, primpath, productName/picture -- one node IS the Karma XPU
    render config. (Generic ``rendersettings`` carries a locked resolution2 +
    VRay/PRMan cruft; avoided.)
  - ``subLayerPaths`` is STRONGEST-FIRST; appended in dept order -> render at
    index 0 (strongest). Authored in a pythonscript LOP (persistent via the
    node; editableStage() is valid in-cook).
"""

from typing import List, Optional, Tuple
import logging

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False

from synapse.server import solaris_compose as sc
from synapse.server.handler_helpers import _is_resolver_uri, _path_warnings

_log = logging.getLogger(__name__)

# Department layers, STRONGEST-FIRST (subLayerPaths index 0 = strongest).
# render overrides fx overrides lighting overrides animation overrides layout.
DEPARTMENT_LAYERS_STRONGEST_FIRST = ["render", "fx", "lighting", "animation", "layout"]

# Embedded provenance LOP-cook script. FLAT top-level only (the LOP cook, like
# the bridge, can split globals/locals -- no nested functions referencing module
# names). DefinePrim/CreateAttribute via editableStage() composes downstream (the
# established handlers_usd.py pattern); a subLayerPaths edit does NOT, so the
# department stack uses a `sublayer` LOP + real files (see build_karma_xpu_shot).
_PROVENANCE_CODE = '''
from pxr import Sdf
_node = hou.pwd()
_stage = _node.editableStage()
_p = _stage.DefinePrim("/SYNAPSE/shotsetup", "Scope")
_p.CreateAttribute("synapse:delegate", Sdf.ValueTypeNames.String).Set(%(delegate)r)
_p.CreateAttribute("synapse:reason", Sdf.ValueTypeNames.String).Set(%(reason)r)
_p.CreateAttribute("synapse:layer_order", Sdf.ValueTypeNames.StringArray).Set(list(%(order)r))
'''

# karmarendersettings creates a RenderProduct but its productName PARM does NOT
# author the prim's productName attr (verified live) -> shots would silently have
# no output path (BL-007). Author it directly via the schema (guaranteed).
# M2-D: the literal carries $HIP/$F4 tokens and is expanded AT COOK TIME via
# hou.text.expandString -- the ROP sets the frame before each LOP cook, so every
# rendered frame's stage carries that frame's filename (a pre-expanded literal
# sent every farm frame to ONE file). FLAT statements only (split-globals).
_PRODUCT_NAME_CODE = '''
from pxr import UsdRender
_node = hou.pwd()
_stage = _node.editableStage()
_rps = [p for p in _stage.Traverse() if p.GetTypeName() == "RenderProduct"]
if not _rps:
    _rps = [_stage.DefinePrim("/Render/Products/renderproduct", "RenderProduct")]
# Author on the FIRST RenderProduct only -- do not clobber other products.
_pn = hou.text.expandString(%(exr)r)
UsdRender.Product(_rps[0]).CreateProductNameAttr().Set(_pn)
'''


def _set(node, parm_name: str, value) -> bool:
    """Set a parm if present and unlocked. Returns True on success (used to
    detect missing/locked parms so we can fall back -- e.g. productName->picture)."""
    p = node.parm(parm_name)
    if p is None:
        _log.debug("parm %r absent on %s", parm_name, node.path())
        return False
    if p.isLocked():
        _log.debug("parm %r locked on %s", parm_name, node.path())
        return False
    try:
        p.set(value)
        return True
    except Exception as e:
        _log.warning("parm %r set failed on %s: %s", parm_name, node.path(), e)
        return False


def build_karma_xpu_shot(
    stage_node,
    shot: str = "shot",
    resolution: Tuple[int, int] = (1920, 1080),
    engine: str = "xpu",
    layer_dir: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict:
    """Scaffold a render-ready Karma XPU shot (PRD 7.1 / GAP-1).

    Builds: a render-strongest department sublayer stack
    [render, fx, lighting, animation, layout]; a camera wired as the render
    camera; a Karma ``karmarendersettings`` (engine=xpu) with camera + resolution
    + productName; synapse:* provenance; a display OUTPUT. Returns a result dict.

    All node ops go through the solaris_compose primitive (phantom-guarded). The
    handler owns the undo group + main-thread marshal. Department .usd files
    created on disk are reported in ``disk_writes`` and are NOT undoable --
    rollback never deletes artist files.
    """
    if not HOU_AVAILABLE:
        raise sc.ComposeError("hou unavailable -- build_karma_xpu_shot needs the live bridge")

    import os
    from pxr import Sdf
    depts = list(DEPARTMENT_LAYERS_STRONGEST_FIRST)   # render..layout (conceptual strongest-first)
    created = []

    # 1. Department sublayer stack via a `sublayer` LOP.
    # VERIFIED on 21.0.671: the sublayer LOP composes filepathN as STRONGEST
    # (last wins) -- the OPPOSITE of raw USD subLayerPaths. So fill the filepaths
    # WEAKEST-FIRST: filepath1=layout ... filepath5=render (render strongest).
    # M2-D: the compose tier creates real files on disk -- a resolver URI has
    # no filesystem dirname to makedirs into. Fail loud, never half-build.
    if layer_dir and _is_resolver_uri(layer_dir):
        raise sc.ComposeError(
            "layer_dir can't be a resolver URI -- the compose tier creates "
            "real layer files on disk; pass a filesystem path or a $-token path"
        )
    base_raw = layer_dir or ("$HIP/" + shot + "_layers")
    base = hou.expandString(base_raw)  # disk ops keep the expanded form
    if not os.path.isdir(base):
        os.makedirs(base)
    weakest_first = list(reversed(depts))             # [layout, animation, lighting, fx, render]
    dept_files = []
    dept_files_raw = []
    disk_writes = []  # files THIS call created (outside the undo system)
    for d in weakest_first:
        fp = base + "/" + d + ".usd"
        if not os.path.exists(fp):
            Sdf.Layer.CreateNew(fp).Save()
            disk_writes.append(fp)
        dept_files.append(fp)
        dept_files_raw.append(base_raw + "/" + d + ".usd")
    dept = sc.create_lop(stage_node, "sublayer", shot + "_dept_stack")
    created.append(dept)
    _set(dept, "num_files", len(dept_files))  # guarded (locked/missing -> logged, not crash)
    # M2-D: PARMS keep the unexpanded tokens (the sublayer LOP expands $HIP
    # natively at cook) -- a pre-expanded absolute broke on any $HIP move.
    for i, fp_raw in enumerate(dept_files_raw, start=1):
        _set(dept, "filepath%d" % i, fp_raw)

    # 2. Camera (render camera).
    cam = sc.create_lop(stage_node, "camera", shot + "_cam")
    created.append(cam)
    sc.wire(cam, dept)
    cam_prim = "/cameras/" + shot + "_cam"
    _set(cam, "primpath", cam_prim)
    _set(cam, "tz", 6.0)
    _set(cam, "ty", 1.0)
    _set(cam, "focalLength", 50.0)
    if _set(cam, "lookatenable", True):
        _set(cam, "lookatpositiony", 1.0)

    # 3. Karma XPU render settings (self-contained: engine/camera/resolution/product).
    krs = sc.create_lop(stage_node, "karmarendersettings", shot + "_karma_xpu")
    created.append(krs)
    sc.wire(krs, cam)
    rs_prim = "/Render/rendersettings"
    _set(krs, "primpath", rs_prim)
    engine_set = _set(krs, "engine", engine)
    _set(krs, "camera", cam_prim)
    _set(krs, "resolutionx", int(resolution[0]))
    _set(krs, "resolutiony", int(resolution[1]))
    # M2-D: keep $HIP unexpanded + add $F4 -- a pre-expanded token-free
    # productName wrote EVERY sequence frame to one file, overwriting itself.
    exr_raw = "$HIP/render/" + shot + ".$F4.exr"
    _set(krs, "productName", exr_raw)  # best-effort parm (does NOT author the prim attr)
    # Author productName onto the RenderProduct prim (the parm alone doesn't -> BL-007).
    prodname = sc.make_pythonscript_lop(stage_node, shot + "_productname",
                                        _PRODUCT_NAME_CODE % {"exr": exr_raw})
    created.append(prodname)
    sc.wire(prodname, krs)
    product_via = "pythonscript:RenderProduct.productName"

    # 4. Provenance (synapse:* on a persistent node).
    prov_code = _PROVENANCE_CODE % {
        "delegate": engine,
        "reason": reason or ("Karma %s default scaffold; CPU fallback for OSL/nested-dielectric/SSS/deep-volume" % engine),
        "order": depts,
    }
    prov = sc.make_pythonscript_lop(stage_node, shot + "_provenance", prov_code)
    created.append(prov)
    sc.wire(prov, prodname)

    # 5. OUTPUT null (display flag = terminal of the chain).
    out = sc.create_lop(stage_node, "null", "OUTPUT")
    created.append(out)
    sc.wire(out, prov)
    try:
        out.setGenericFlag(hou.nodeFlag.Display, True)
    except Exception:
        pass

    stage_node.layoutChildren()

    # Read back the composed stage (the [REAL] verifier reads through this).
    rstage = sc.read_stage(out)
    errs = sc.composition_errors(rstage)

    result = {
        "status": "created",
        "nodes": [n.path() for n in created],
        "output": out.path(),
        "engine": engine,
        "engine_set": engine_set,
        "camera_prim": cam_prim,
        "rendersettings_prim": rs_prim,
        "product_path": exr_raw,
        "product_name_resolution": "cook-time (per-frame via hou.text.expandString)",
        "product_via": product_via,
        "layer_order_strongest_first": depts,
        "department_files_weakest_first": dept_files,
        "department_parm_paths": dept_files_raw,
        "disk_writes": disk_writes,
        "disk_writes_undoable": False,
        "composition_errors": errs,
    }
    pw = _path_warnings(layer_dir or "", context="layer_dir")
    if pw:
        result["path_warnings"] = pw
    return result


# ---------------------------------------------------------------------------
# Mile 3 -- matlib_bind (PRD 7.2 / GAP-2 / BL-008)
# ---------------------------------------------------------------------------

def ensure_mtlx_material(stage_node, name, prefix="/materials/", color=None,
                         input_node=None, shader_type="mtlxstandard_surface"):
    """Create a materiallibrary + a MaterialX standard-surface material.

    Returns (material_prim_path, matlib_node). Recipe verified on 21.0.671:
    matpathprefix -> material prim path = prefix + name; shader via
    matlib.createNode(shader_type, name).
    """
    if not HOU_AVAILABLE:
        raise sc.ComposeError("hou unavailable -- ensure_mtlx_material needs the live bridge")
    matlib = sc.create_lop(stage_node, "materiallibrary", name + "_matlib")
    if input_node is not None:
        sc.wire(matlib, input_node)
    if not prefix.endswith("/"):
        prefix += "/"
    _set(matlib, "matpathprefix", prefix)
    sh = matlib.createNode(shader_type, name)
    if color is not None:
        for pn in ("base_color", "basecolor"):
            pt = sh.parmTuple(pn)
            if pt is not None:
                try:
                    pt.set(color)
                    break
                except Exception:
                    pass
    matlib.layoutChildren()
    return prefix + name, matlib


def _expand_targets(stage, pattern: str, limit: int = 100000) -> List[str]:
    """Resolve a primpattern to concrete composed prim paths. Supports an exact
    path, a glob ('/geo/*'), or a USD-style type expression ('//Mesh').
    Traversal is bounded by `limit` (TERMINATION)."""
    import fnmatch
    import itertools
    if pattern.startswith("//"):
        type_name = pattern[2:]
        return [str(p.GetPath()) for p in itertools.islice(stage.Traverse(), limit)
                if p.GetTypeName() == type_name]
    if "*" in pattern or "?" in pattern:
        return [str(p.GetPath()) for p in itertools.islice(stage.Traverse(), limit)
                if fnmatch.fnmatch(str(p.GetPath()), pattern)]
    prim = stage.GetPrimAtPath(pattern)
    return [pattern] if (prim and prim.IsValid()) else []


def bind_material(stage_node, material_path: str, targets, input_node=None,
                  strength: Optional[str] = None) -> dict:
    """Bind one material to a target prim set via an assignmaterial LOP (GAP-2).

    targets: a primpattern or list of them -- exact path, glob ('/geo/*'), or
    type expression ('//Mesh'). Binds on the COMPOSED prim path; the assignmaterial
    LOP is downstream so it wins by LIVRPS over a referenced asset's own binding.

    Verifies via ComputeBoundMaterial that EVERY resolved prim computes
    `material_path`, and reports patterns that matched nothing and prims that
    resolved to a different/no material (OBSERVABILITY -- never bind silently).
    """
    if not HOU_AVAILABLE:
        raise sc.ComposeError("hou unavailable -- bind_material needs the live bridge")
    from pxr import UsdShade
    if isinstance(targets, str):
        targets = [targets]
    if input_node is None:
        kids = stage_node.children()
        input_node = stage_node.displayNode() or (kids[-1] if kids else None)

    # The assignmaterial LOP groks exact paths + globs, but NOT '//Type'
    # expressions (verified live), so expand those to concrete prim paths on the
    # input (composed) stage before binding; pass globs/exact through unchanged.
    in_stage = sc.read_stage(input_node) if input_node is not None else None
    assign_pats, unmatched = [], []
    for pat in targets:
        if pat.startswith("//"):
            exp = _expand_targets(in_stage, pat) if in_stage is not None else []
            if not exp:
                unmatched.append(pat)
            assign_pats.extend(exp)
        else:
            assign_pats.append(pat)
    assign_pats = list(dict.fromkeys(assign_pats))  # dedup, preserve order

    assign = sc.create_lop(stage_node, "assignmaterial", "synapse_bind")
    if input_node is not None:
        sc.wire(assign, input_node)
    _set(assign, "nummaterials", len(assign_pats))
    for i, pp in enumerate(assign_pats, start=1):
        _set(assign, "primpattern%d" % i, pp)
        _set(assign, "matspecmethod%d" % i, "path")
        _set(assign, "matspecpath%d" % i, material_path)
        _set(assign, "bindmethod%d" % i, "direct")
        if strength:
            _set(assign, "strength%d" % i, strength)  # best-effort; LOP may not expose it

    # Verify: expand the ORIGINAL targets on the RESULT stage + check binding.
    rstage = sc.read_stage(assign)
    verified = []
    all_bound = (len(unmatched) == 0)
    seen = set()
    for pat in targets:
        prims = _expand_targets(rstage, pat)
        if not prims and not pat.startswith("//"):
            unmatched.append(pat)
            all_bound = False
            continue
        for pp in prims:
            if pp in seen:
                continue
            seen.add(pp)
            res = UsdShade.MaterialBindingAPI(rstage.GetPrimAtPath(pp)).ComputeBoundMaterial()
            bm = res[0]
            bound = str(bm.GetPath()) if (bm and bm.GetPrim().IsValid()) else None
            ok = (bound == material_path)
            all_bound = all_bound and ok
            verified.append({"prim": pp, "bound": bound, "ok": ok})

    return {
        "status": "bound" if all_bound else "partial",
        "assign_node": assign.path(),
        "material": material_path,
        "targets": targets,
        "all_bound": all_bound,
        "verified": verified,
        "unmatched_patterns": unmatched,
        "unbound": [v["prim"] for v in verified if not v["ok"]],
    }


# ---------------------------------------------------------------------------
# Mile 4 -- shot_render_ready (PRD 7.3 / GAP-3): the OBSERVABILITY tool
# ---------------------------------------------------------------------------

_GPRIM_TYPES = {
    "Mesh", "Sphere", "Cube", "Cylinder", "Capsule", "Cone", "Points",
    "BasisCurves", "NurbsCurves", "Volume", "PointInstancer",
}


def _assess_stage(stage, engine_hint=None, max_prims=5000) -> dict:
    """Pure-pxr readiness assessment over E3. Returns {ready, engine, clauses,
    details}. Separated from assess_render_ready so it is testable on an
    in-memory Usd.Stage (no Houdini)."""
    from pxr import UsdShade, UsdRender
    import os
    prims = list(stage.Traverse())
    clauses, details = {}, {}

    def setc(name, passed, info=None):
        clauses[name] = "pass" if passed else "fail"
        if info is not None:
            details[name] = info

    # 1. RenderSettings present + render camera resolves to a Camera prim.
    rs_prims = [p for p in prims if p.GetTypeName() == "RenderSettings"]
    if not rs_prims:
        setc("rendersettings", False, "no RenderSettings prim")
        setc("camera", False, "no RenderSettings -> no render camera")
    else:
        setc("rendersettings", True)
        crel = UsdRender.Settings(rs_prims[0]).GetCameraRel()
        tgts = list(crel.GetTargets()) if crel else []
        cam_ok = False
        if tgts:
            cp = stage.GetPrimAtPath(tgts[0])
            cam_ok = bool(cp and cp.IsValid() and cp.GetTypeName() == "Camera")
        setc("camera", cam_ok, None if cam_ok else "render camera unresolved (targets=%s)" % [str(x) for x in tgts])

    # 2. No composition errors.
    errs = [str(e) for e in stage.GetCompositionErrors()]
    setc("composition_errors", not errs, errs[:5] if errs else None)

    # 3. Every LOADED render-purpose gprim resolves a material (payload-aware:
    #    a prim behind an unloaded payload is flagged unloaded, not missing).
    unbound, unloaded, checked = [], [], 0
    for p in prims:
        if checked >= max_prims:
            break
        if p.GetTypeName() in _GPRIM_TYPES:
            checked += 1
            if not p.IsLoaded():
                unloaded.append(str(p.GetPath()))
                continue
            res = UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()
            bm = res[0]
            if not (bm and bm.GetPrim().IsValid()):
                unbound.append(str(p.GetPath()))
    setc("materials_bound", not unbound, {"unbound": unbound[:25]} if unbound else None)
    if unloaded:
        details["unloaded_payloads"] = unloaded[:25]

    # 4. productName parent dir writable (RenderProduct prims and/or the
    #    self-contained karmarendersettings RenderSettings.productName attr).
    names = []
    for p in prims:
        if p.GetTypeName() == "RenderProduct":
            a = UsdRender.Product(p).GetProductNameAttr()
            if a and a.Get():
                names.append(str(a.Get()))
    for rsp in rs_prims:
        a = rsp.GetAttribute("productName")
        if a and a.IsValid() and a.Get():
            names.append(str(a.Get()))
    names = list(dict.fromkeys(names))
    if not names:
        setc("output_path", False, "no productName (no RenderProduct / RenderSettings.productName)")
    else:
        bad = []
        for pn in names:
            ex = hou.expandString(pn) if (HOU_AVAILABLE and hasattr(hou, "expandString")) else pn
            d = os.path.dirname(ex) or "."
            if os.path.isdir(d):
                if not os.access(d, os.W_OK):
                    bad.append("%s (dir not writable)" % ex)
            else:
                par = os.path.dirname(d) or "."
                if not (os.path.isdir(par) and os.access(par, os.W_OK)):
                    bad.append("%s (parent dir missing/not writable)" % ex)
        setc("output_path", not bad, bad if bad else None)
        details["product_paths"] = names

    # 5. AOVs present as RenderVar prims.
    rv = [str(p.GetPath()) for p in prims if p.GetTypeName() == "RenderVar"]
    setc("aovs", bool(rv), {"rendervars": rv} if rv else "no RenderVar prims (no AOVs configured)")

    # 6. No XPU-incompatible content under an XPU delegate. v1 detects the
    #    tractable subset (OSL shaders + Volume prims); nested-dielectric/SSS
    #    are NOT auto-detected (would need shader-graph analysis).
    engine = engine_hint
    if engine is None:
        for rsp in rs_prims:
            for an in ("karma:engine", "engine"):
                a = rsp.GetAttribute(an)
                if a and a.IsValid() and a.Get():
                    engine = str(a.Get())
                    break
            if engine:
                break
    if engine and "xpu" in str(engine).lower():
        issues = []
        for p in prims[:max_prims]:
            if p.GetTypeName() == "Volume":
                issues.append("%s (Volume -- deep volumes weak on XPU)" % p.GetPath())
            sh = UsdShade.Shader(p)
            if sh.GetPrim().IsValid():
                ida = sh.GetIdAttr()
                sid = str(ida.Get()) if (ida and ida.Get()) else ""
                if "osl" in sid.lower():
                    issues.append("%s (OSL shader '%s' -- unsupported on XPU)" % (p.GetPath(), sid))
        setc("xpu_compatible", not issues, issues[:25] if issues else None)
        details["xpu_detection_scope"] = "v1: OSL shaders + Volume prims; nested-dielectric/SSS not auto-detected"
    else:
        clauses["xpu_compatible"] = "n/a"

    ready = all(v == "pass" for v in clauses.values() if v in ("pass", "fail"))
    return {"ready": ready, "engine": engine, "clauses": clauses, "details": details}


def _resolve_read_stage(node):
    """Resolve a /stage LopNetwork (-> display node) or a LOP node to its
    composed read-only Usd.Stage."""
    if isinstance(node, hou.LopNetwork):
        dn = node.displayNode()
        if dn is None:
            kids = node.children()
            dn = kids[-1] if kids else None
        if dn is None:
            raise sc.StageUnavailableError("%s is empty" % node.path())
        return sc.read_stage(dn)
    return sc.read_stage(node)


def assess_render_ready(stage_node, engine_hint=None, max_prims=5000) -> dict:
    """Render-readiness report over E3 (PRD 7.3 / GAP-3). Read-only -- composes
    nothing. Returns {ready, engine, clauses, details}; each false clause names
    the offending prim/path. Turns BL-007/008 from silent into a pre-flight report.
    """
    if not HOU_AVAILABLE:
        raise sc.ComposeError("hou unavailable -- assess_render_ready needs the live bridge")
    return _assess_stage(_resolve_read_stage(stage_node), engine_hint=engine_hint, max_prims=max_prims)
