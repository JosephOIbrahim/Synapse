#!/usr/bin/env python3
"""worldlabs_pipeline_corrected.py

The CORRECTED, SELF-VERIFYING form of the "SYNAPSE Automated Pipeline: Gaussian Splat
Animation & Advanced Relighting (Parts 1 & 2)" blueprint (Parts 1 & 2 .docx).

Why this file exists
--------------------
The blueprint's own script cannot run on Houdini 22.0.400. Eleven of its calls raise,
or silently do nothing, against the live build. Every correction below was produced by
executing the blueprint's exact call in hython and reading the exception, not by reading
a document. The evidence ledger is `docs/intake/worldlabs-gaussian-pipeline-audit.md`;
the raw probe records are reproduced by running this file with `--verify`.

Nothing here is guessed. Where the blueprint's intent could not be settled by a probe
(rung F-OPEN-1..4), the code says OPEN and names the probe that would settle it, rather
than inventing a behaviour.

Run the verification (needs a Houdini licence, no scene required):

    env -u HOME "C:/Program Files/SideFX Software/Houdini 22.0.400/bin/hython.exe" \
        -s -P harness/probes/worldlabs_pipeline_corrected.py --verify

Build the graph (paths are arguments; nothing is hardcoded):

    hython -s -P harness/probes/worldlabs_pipeline_corrected.py --build \
        --desert-ply  /path/desert.ply \
        --jungle-ply  /path/jungle.ply \
        --collider    /path/collider.glb \
        --out         /path/frames/
"""
from __future__ import annotations

import argparse
import json
import sys

import hou

# ---------------------------------------------------------------------------
# The correction ledger. id -> (blueprint said, the truth, how it was proven)
# ---------------------------------------------------------------------------

FIXES = [
    ("F1", "hou.Node.disconnect() removes a node input",
     "hou.Node has no 'disconnect' member; unhook with node.setInput(i, None)",
     "node.disconnect(0) -> AttributeError: 'SopNode' object has no attribute 'disconnect'"),
    ("F2", "createNode('labs::bake_gsplat')",
     "createNode('bakegsplat') - a built-in H22 SOP, not a Labs node",
     "createNode('labs::bake_gsplat') -> OperationFailed: Invalid node type name"),
    ("F3", "createNode('labs::normals_from_gsplat')",
     "createNode('labs::normals_from_gsplats::1.0') - plural, versioned",
     "createNode('labs::normals_from_gsplat') -> OperationFailed: Invalid node type name"),
    ("F4", "normals node takes the collider colour on input 1",
     "labs::normals_from_gsplats::1.0 has ONE input; relighting is a LOP "
     "(labs::relight_gsplats::1.1), not a second SOP input",
     "normals.setInput(1, file) -> InvalidInput: Invalid input."),
    ("F5", "gltf.setParms({'filepath': ...})",
     "gltf::2.0 spells the file parm 'gltffile'",
     "gltf::2.0 parm list contains 'gltffile'; 'filepath' is absent"),
    ("F6", "gltf.setParms({'import_geometry_as': 1})",
     "gltf::2.0 spells it 'importnodegeometryas', token 'flattenedgeometry'",
     "setParms({'import_geometry_as':1}) -> Invalid parameter name; "
     "menu tokens are ('packedprimitive','flattenedgeometry')"),
    ("F7", "wrangle.parm('strength'|'spin'|'radius'|'falloff'|'drag'|'timestep')",
     "the six parameters do not exist and must be CREATED on a ParmTemplateGroup",
     "wrangle.parm('strength') -> None; .set() -> AttributeError: 'NoneType' ..."),
    ("F8", "karmarendersettings.parm('renderer').set('XPU')",
     "the parm is 'engine' and the token is 'xpu' (lower case)",
     "parm('renderer') -> None; parm('engine').set('xpu') -> ok"),
    ("F9", "karmarendersettings.parm('samples').set(256)",
     "the parm is 'samplesperpixel'",
     "parm('samples') -> None; parm('samplesperpixel').set(256) -> ok"),
    ("F10", "stage.createNode('usdrender')",
     "stage.createNode('usdrender_rop') - 'usdrender' does not resolve in /stage",
     "createNode('usdrender') -> OperationFailed: Invalid node type name"),
    ("F11", "distantlight.setInput(0, fog_box)",
     "distantlight::2.0 has NO inputs; intensity/exposure are USD-exposed parms",
     "distantlight.inputs() -> []; xn__inputsintensity_i0a is settable"),
]

# Claims in the blueprint's own "Corrected Error Audit" that the code does not implement.
# These are not node-level defects; they are prose that outruns the script.
UNPROVEN = [
    ("F-OPEN-1", "Coordinate-space mismatches fixed with UsdGeom.XformOp transform matrices",
     "the script contains no XformOp, no up-axis handling and no coordinate conversion. "
     "The repo's own intake records Marble as +Y-down (WL-EX-05) and rejects a prior "
     "blueprint for assuming Y-up - the same defect, now claimed as fixed.",
     "cook one World Labs export, read the point cloud's up axis, and diff the "
     "pre- and post-conversion bounds"),
    ("F-OPEN-2", "VEX syntax fragility eliminated by a pre-compiled VEX AST with Moneta v5 schema gates",
     "the script sets a raw VEX string on a wrangle - exactly the 'manual string-typed "
     "VEX wrangle' it claims to remove. There is no AST and no schema gate.",
     "assert that a VEX fragment is compiled from a template, not concatenated from a string"),
    ("F-OPEN-3", "Graph disconnection via programmatic traversal",
     "the only disconnection API the script names is the phantom in F1, and the script "
     "contains no traversal and no disconnection at all.",
     "the graph as written has nothing to disconnect - prove it or drop the claim"),
    ("F-OPEN-4", "Karma XPU 4D time-sample render and FFmpeg export to .mp4",
     "usdrender_rop has no video or ffmpeg output parm ('outputimage' is an image "
     "sequence), and the script never writes output_mov - it only prints a line saying it "
     "is exporting. The deliverable is never produced.",
     "render 2 frames to a real path and assert the file exists on disk afterwards"),
    ("F-OPEN-5", "The blast targets a point group named 'call'",
     "no node in the graph creates a group named 'call'; nothing in the script names a "
     "collider group. The blast removes whatever happens to be there - possibly nothing.",
     "cook the collider import and list the point groups it produces"),
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _find_parm_by_suffix(node: hou.Node, stem: str) -> hou.Parm | None:
    """Find a parm whose name contains `stem` (case-insensitive).

    Solaris exposes USD attributes through version-specific names like
    'xn__inputsintensity_i0a'. Those names carry a build hash, so they are resolved by
    pattern at runtime rather than hardcoded - a hardcoded name is a phantom waiting
    for the next build.
    """
    stem = stem.lower()
    for p in node.parms():
        if stem in p.name().lower():
            return p
    return None


def _exposed_value_parm(node: hou.Node, stem: str) -> hou.Parm | None:
    """The value parm behind an exposed USD input, e.g. inputsintensity -> ..._i0a."""
    stem = stem.lower()
    for p in node.parms():
        n = p.name().lower()
        if stem in n and not n.endswith("_control") and "_control_" not in n:
            return p
    return None


def _add_float_parms(node: hou.Node, specs) -> None:
    """Create float parms on a node so chf() can read them.

    F7: the blueprint assumed these existed. They do not. A wrangle carries no spare
    float parms, so they have to be added to its ParmTemplateGroup and the group has to
    be set back onto the node.
    """
    ptg = node.parmTemplateGroup()
    for name, label, default in specs:
        tmpl = hou.FloatParmTemplate(name, label, 1, default_value=(default,))
        ptg.append(tmpl)
    node.setParmTemplateGroup(ptg)


# ---------------------------------------------------------------------------
# the corrected build
# ---------------------------------------------------------------------------

def build_graph(desert_ply: str, jungle_ply: str, collider_glb: str,
                out_dir: str, strength: float = -1.0, spin: float = 1.0,
                radius: float = 30.0, falloff: float = 0.442, drag: float = 0.1,
                timestep: float = 1.57, engine: str = "xpu", samples: int = 256,
                f1: int = 1, f2: int = 60) -> dict:
    """Build the corrected graph. Returns a record of what was actually created."""
    made = {}

    env = hou.node("/obj").createNode("geo", "SYNAPSE_ENV_NETWORK")
    stage = hou.node("/stage")

    # ---- STAGE 1: object network (SOP) -----------------------------------
    file_desert = env.createNode("file", "file_desert_ply")
    file_desert.setParms({"file": desert_ply})
    made["file_desert_ply"] = file_desert.path()

    # F2: bakegsplat is a built-in H22 SOP. labs::bake_gsplat does not resolve.
    bake_desert = env.createNode("bakegsplat", "bake_desert")
    bake_desert.setInput(0, file_desert)
    made["bake_desert"] = bake_desert.path()

    # F3: plural + versioned node name.
    normals_desert = env.createNode("labs::normals_from_gsplats::1.0", "normals_desert")
    normals_desert.setInput(0, bake_desert)
    made["normals_desert"] = normals_desert.path()

    file_jungle = env.createNode("file", "file_jungle_ply")
    file_jungle.setParms({"file": jungle_ply})
    bake_jungle = env.createNode("bakegsplat", "bake_jungle")
    bake_jungle.setInput(0, file_jungle)
    normals_jungle = env.createNode("labs::normals_from_gsplats::1.0", "normals_jungle")
    normals_jungle.setInput(0, bake_jungle)
    made["normals_jungle"] = normals_jungle.path()

    # F5/F6: gltf::2.0 parm names. The blueprint's 'filepath' and 'import_geometry_as'
    # both raise Invalid parameter name.
    gltf_jungle = env.createNode("gltf", "gltf_jungle_collider")
    gltf_jungle.setParms({
        "gltffile": collider_glb,
        "importnodegeometryas": "flattenedgeometry",
    })
    color_jungle = env.createNode("color", "color_jungle")
    color_jungle.setInput(0, gltf_jungle)
    made["gltf_jungle_collider"] = gltf_jungle.path()

    # F4: the collider colour does NOT go into the normals node's input 1. The
    # normals node has one input. Stage-level relighting is a LOP and is wired
    # in STAGE 3.

    # ---- STAGE 2: VEX animation wrangle ----------------------------------
    anim_wrangle = env.createNode("attribwrangle", "anim_jungle_solver")
    anim_wrangle.setInput(0, normals_jungle)
    # F7: create the six parms the VEX reads, then set them.
    _add_float_parms(anim_wrangle, [
        ("strength", "Strength", strength),
        ("spin", "Spin", spin),
        ("radius", "Radius", radius),
        ("falloff", "Falloff", falloff),
        ("drag", "Drag", drag),
        ("timestep", "Timestep", timestep),
    ])
    anim_wrangle.parm("snippet").set(VEX_SOLVER)
    made["anim_jungle_solver"] = anim_wrangle.path()

    blast_node = env.createNode("blast", "blast_sky_blue")
    blast_node.setInput(0, anim_wrangle)
    blast_node.parm("group").set("call")  # F-OPEN-5: unproven group
    made["blast_sky_blue"] = blast_node.path()

    env_out = env.createNode("null", "ENV_OUT")
    env_out.setInput(0, blast_node)
    made["ENV_OUT"] = env_out.path()

    # ---- STAGE 3: Solaris stage (LOP) ------------------------------------
    sop_import = stage.createNode("sopimport", "import_synapse_env")
    sop_import.parm("soppath").set(env_out.path())
    made["import_synapse_env"] = sop_import.path()

    fog_box = stage.createNode("karmafogbox", "fog_box")
    made["fog_box"] = fog_box.path()

    # F11: distantlight::2.0 has no inputs, so the fog box is NOT wired into it.
    distant_light = stage.createNode("distantlight", "sun_light")
    inten = _exposed_value_parm(distant_light, "inputsintensity")
    expo = _exposed_value_parm(distant_light, "inputsexposure")
    if inten is not None:
        inten.set(15.0)
    if expo is not None:
        expo.set(4.0)
    made["sun_light"] = distant_light.path()
    made["sun_light_intensity_parm"] = inten.name() if inten else "UNRESOLVED"
    made["sun_light_exposure_parm"] = expo.name() if expo else "UNRESOLVED"

    # F8/F9: engine + samplesperpixel.
    render_settings = stage.createNode("karmarendersettings", "xpu_settings")
    render_settings.parm("engine").set(engine)
    render_settings.parm("samplesperpixel").set(samples)
    made["xpu_settings"] = render_settings.path()

    # F10: usdrender_rop, not usdrender. trange is a menu stored as an index;
    # index 1 is 'normal' = "Render Specific Frame Range".
    rop_karma = stage.createNode("usdrender_rop", "rop_karma_xpu")
    rop_karma.parm("trange").set(1)
    rop_karma.parm("f1").set(f1)
    rop_karma.parm("f2").set(f2)
    rop_karma.parm("outputimage").set(out_dir + "/synapse_$F4.exr")
    made["rop_karma_xpu"] = rop_karma.path()

    return made


# The VEX solver, unchanged in substance from the blueprint, but the six channels it
# reads are now parameters that exist (F7).
VEX_SOLVER = """
vector center = @P;
float strength = chf("strength");
float spin = chf("spin");
vector axis = chv("axis");
float radius = chf("radius");
float falloff = chf("falloff");
float drag = chf("drag");
float dt = chf("timestep");
vector offset = @P - center;
float dist = length(offset);
if (dist > 0.001 && radius > 0.0) {
    vector dir = offset / dist;
    float soft = clamp(falloff, 0.0, 1.0);
    float inner = radius * (1.0 - soft);
    float weight = 1.0 - smooth(inner, radius, dist);
    @v += dir * strength * weight * dt;
    if (length(axis) > 0.001 && spin != 0.0) {
        vector an = normalize(axis);
        vector tangent = cross(an, offset);
        @v += tangent * spin * weight * dt;
    }
}
if (drag > 0.0) {
    @v *= max(1.0 - (drag * dt), 0.0);
}
@P += @v * dt;
"""


# ---------------------------------------------------------------------------
# verification: every fix is asserted against the live build
# ---------------------------------------------------------------------------

def verify() -> int:
    """Assert each correction on the live build. A check that cannot fail is deleted."""
    results = []
    env = hou.node("/obj").createNode("geo", "VERIFY_ENV")
    stage = hou.node("/stage")

    def check(fix_id, label, fn):
        try:
            detail = fn()
            ok = True
        except Exception as e:  # noqa: BLE001
            detail = "%s: %s" % (type(e).__name__, e)
            ok = False
        results.append({"fix": fix_id, "label": label, "ok": ok, "detail": str(detail)})
        print("[%s] %-6s %-58s %s" % ("PASS" if ok else "FAIL", fix_id, label, detail))

    # F1
    def f1():
        n = env.createNode("null", "v_null")
        other = env.createNode("null", "v_null2")
        n.setInput(0, other)
        assert not hasattr(n, "disconnect"), "hou.Node.disconnect exists - re-check the fix"
        n.setInput(0, None)
        assert not n.inputs(), "setInput(0, None) did not unhook the input"
        return "no disconnect member; setInput(0, None) unhooks cleanly"
    check("F1", "hou.Node.disconnect is absent; setInput(0, None) unhooks", f1)

    # F2
    def f2():
        try:
            env.createNode("labs::bake_gsplat", "v_bad")
        except hou.OperationFailed:
            pass
        else:
            raise AssertionError("labs::bake_gsplat resolved - the fix may be stale")
        n = env.createNode("bakegsplat", "v_bake")
        return "live type %s" % n.type().name()
    check("F2", "bakegsplat resolves (labs::bake_gsplat does not)", f2)

    # F3
    def f3():
        try:
            env.createNode("labs::normals_from_gsplat", "v_bad2")
        except hou.OperationFailed:
            pass
        else:
            raise AssertionError("labs::normals_from_gsplat resolved - the fix may be stale")
        n = env.createNode("labs::normals_from_gsplats::1.0", "v_norm")
        return "live type %s" % n.type().name()
    check("F3", "labs::normals_from_gsplats::1.0 resolves", f3)

    # F4
    def f4():
        nm = env.createNode("labs::normals_from_gsplats::1.0", "v_norm2")
        f = env.createNode("file", "v_file")
        try:
            nm.setInput(1, f)
        except hou.InvalidInput:
            pass
        else:
            raise AssertionError("normals node accepted a second input - re-check the fix")
        return "one input only; setInput(1, ...) -> InvalidInput"
    check("F4", "normals node has one input; relight is a LOP", f4)

    # F5 / F6
    def f5():
        g = env.createNode("gltf", "v_gltf")
        assert g.parm("gltffile") is not None, "gltffile missing"
        assert g.parm("filepath") is None, "filepath exists on this build - re-check the fix"
        g.setParms({"gltffile": "/tmp/x.glb"})
        return "gltffile set ok"
    check("F5", "gltf::2.0 file parm is 'gltffile'", f5)

    def f6():
        g = env.createNode("gltf", "v_gltf2")
        try:
            g.setParms({"import_geometry_as": 1})
        except hou.OperationFailed:
            pass
        else:
            raise AssertionError("import_geometry_as resolved - re-check the fix")
        g.setParms({"importnodegeometryas": "flattenedgeometry"})
        items = g.parmTemplateGroup().find("importnodegeometryas").menuItems()
        assert "flattenedgeometry" in items, "token missing: %s" % (items,)
        return "tokens %s" % (items,)
    check("F6", "gltf flatten parm is 'importnodegeometryas'", f6)

    # F7
    def f7():
        w = env.createNode("attribwrangle", "v_wrangle")
        assert w.parm("strength") is None, "strength exists - re-check the fix"
        _add_float_parms(w, [("strength", "Strength", -1.0)])
        assert w.parm("strength") is not None, "strength not created"
        w.parm("strength").set(-1.0)
        return "created and settable"
    check("F7", "wrangle float parms are created, not assumed", f7)

    # F8 / F9
    def f8():
        k = stage.createNode("karmarendersettings", "v_krs")
        assert k.parm("renderer") is None, "renderer exists - re-check the fix"
        k.parm("engine").set("xpu")
        return "engine=%s" % k.parm("engine").evalAsString()
    check("F8", "karma engine parm is 'engine' with token 'xpu'", f8)

    def f9():
        k = stage.createNode("karmarendersettings", "v_krs2")
        assert k.parm("samples") is None, "samples exists - re-check the fix"
        k.parm("samplesperpixel").set(256)
        return "samplesperpixel=%s" % k.parm("samplesperpixel").eval()
    check("F9", "karma sample count parm is 'samplesperpixel'", f9)

    # F10
    def f10():
        try:
            stage.createNode("usdrender", "v_bad3")
        except hou.OperationFailed:
            pass
        else:
            raise AssertionError("usdrender resolved in /stage - re-check the fix")
        r = stage.createNode("usdrender_rop", "v_rop")
        r.parm("trange").set(1)
        assert r.parm("trange").evalAsString() == "normal", "trange index 1 is not 'normal'"
        return "trange index 1 -> %s" % r.parm("trange").evalAsString()
    check("F10", "usdrender_rop resolves; trange index 1 = 'normal'", f10)

    # F11
    def f11():
        d = stage.createNode("distantlight", "v_dl")
        assert not d.inputs(), "distantlight now has inputs - re-check the fix"
        inten = _exposed_value_parm(d, "inputsintensity")
        assert inten is not None, "no exposed intensity parm found"
        inten.set(15.0)
        return "intensity parm %s = %s" % (inten.name(), inten.eval())
    check("F11", "distantlight has no inputs; intensity is a USD-exposed parm", f11)

    print()
    failed = [r for r in results if not r["ok"]]
    print("VERIFIED %d/%d corrections against %s"
          % (len(results) - len(failed), len(results), hou.applicationVersionString()))
    for r in failed:
        print("  STILL BROKEN: %s %s -> %s" % (r["fix"], r["label"], r["detail"]))
    print()
    print("UNPROVEN claims in the blueprint (not node defects - the script never does this):")
    for uid, claim, why, probe in UNPROVEN:
        print("  %-9s %s" % (uid, claim))
        print("            why open : %s" % why)
        print("            to settle: %s" % probe)
    out = {"houdini": hou.applicationVersionString(), "results": results, "unproven": UNPROVEN}
    with open("harness/probes/worldlabs_pipeline_verification.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("\nwrote harness/probes/worldlabs_pipeline_verification.json")
    return 1 if failed else 0


# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verify", action="store_true",
                    help="assert every correction against the live build")
    ap.add_argument("--build", action="store_true", help="build the corrected graph")
    ap.add_argument("--desert-ply", default="")
    ap.add_argument("--jungle-ply", default="")
    ap.add_argument("--collider", default="")
    ap.add_argument("--out", default="./frames/")
    a = ap.parse_args(argv)
    if a.verify:
        return verify()
    if a.build:
        missing = [n for n, v in (("--desert-ply", a.desert_ply), ("--jungle-ply", a.jungle_ply),
                                  ("--collider", a.collider)) if not v]
        if missing:
            ap.error("missing required: %s" % ", ".join(missing))
        made = build_graph(a.desert_ply, a.jungle_ply, a.collider, a.out)
        print(json.dumps(made, indent=1))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
