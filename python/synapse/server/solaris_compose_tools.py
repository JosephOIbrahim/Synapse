"""
SYNAPSE Solaris Compose Tools (PRD sections 7.1 / 7.2 / 7.3).

Tool LOGIC built on the ``solaris_compose`` primitive. Each function takes the
``/stage`` LOP network node + params and returns a result dict. The thin
handler wrappers (handlers_solaris_compose.py) parse the command payload and
dispatch these through the bridge, which owns undo/integrity/consent.

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


def _set(node, parm_name: str, value) -> bool:
    """Set a parm if present and unlocked. Returns True on success (used to
    detect missing/locked parms so we can fall back -- e.g. productName->picture)."""
    p = node.parm(parm_name)
    if p is None or p.isLocked():
        return False
    try:
        p.set(value)
        return True
    except Exception:
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
    caller routes this through the bridge for undo/integrity/consent.
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
    base = layer_dir or (hou.expandString("$HIP") + "/" + shot + "_layers")
    if not os.path.isdir(base):
        os.makedirs(base)
    weakest_first = list(reversed(depts))             # [layout, animation, lighting, fx, render]
    dept_files = []
    for d in weakest_first:
        fp = base + "/" + d + ".usd"
        if not os.path.exists(fp):
            Sdf.Layer.CreateNew(fp).Save()
        dept_files.append(fp)
    dept = sc.create_lop(stage_node, "sublayer", shot + "_dept_stack")
    created.append(dept)
    nf = dept.parm("num_files")
    if nf is not None:
        nf.set(len(dept_files))
    for i, fp in enumerate(dept_files, start=1):
        _set(dept, "filepath%d" % i, fp)

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
    exr = hou.expandString("$HIP") + "/render/" + shot + ".exr"
    product_via = "productName" if _set(krs, "productName", exr) else ("picture" if _set(krs, "picture", exr) else None)

    # 4. Provenance (synapse:* on a persistent node).
    prov_code = _PROVENANCE_CODE % {
        "delegate": engine,
        "reason": reason or ("Karma %s default scaffold; CPU fallback for OSL/nested-dielectric/SSS/deep-volume" % engine),
        "order": depts,
    }
    prov = sc.make_pythonscript_lop(stage_node, shot + "_provenance", prov_code)
    created.append(prov)
    sc.wire(prov, krs)

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

    return {
        "status": "created",
        "nodes": [n.path() for n in created],
        "output": out.path(),
        "engine": engine,
        "engine_set": engine_set,
        "camera_prim": cam_prim,
        "rendersettings_prim": rs_prim,
        "product_path": exr,
        "product_via": product_via,
        "layer_order_strongest_first": depts,
        "department_files_weakest_first": dept_files,
        "composition_errors": errs,
    }


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


def _expand_targets(stage, pattern: str) -> List[str]:
    """Resolve a primpattern to concrete composed prim paths. Supports an exact
    path, a glob ('/geo/*'), or a USD-style type expression ('//Mesh')."""
    import fnmatch
    if pattern.startswith("//"):
        type_name = pattern[2:]
        return [str(p.GetPath()) for p in stage.Traverse() if p.GetTypeName() == type_name]
    if "*" in pattern or "?" in pattern:
        return [str(p.GetPath()) for p in stage.Traverse()
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
