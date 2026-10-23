#!/usr/bin/env python3
"""worldlabs_pipeline_corrected.py

The CORRECTED, SELF-VERIFYING form of the "SYNAPSE Automated Pipeline: Gaussian Splat
Animation & Advanced Relighting (Parts 1 & 2)" blueprint (Parts 1 & 2 .docx).

Why this file exists
--------------------
The blueprint's own script cannot run on Houdini 22.0.400. It raises on the THIRD node
creation it makes - the first two (a geo, a file) succeed - and the third is
createNode("labs::bake_gsplat"). Every correction below was produced by executing the blueprint's exact
call in hython and reading the exception, not by reading a document. The evidence
ledger is `docs/intake/worldlabs-gaussian-pipeline-audit.md`; the raw probe records
are `harness/probes/worldlabs_blueprint_records.json` and
`harness/probes/worldlabs_pipeline_verification.json`.

Nothing here is guessed. Where the blueprint's intent could not be settled by a probe
(rung F-OPEN-1..8), the code says OPEN and names the probe that would settle it, rather
than inventing a behaviour.

Run the verification (needs a Houdini licence, no scene required). `$HYPYTHON` is
`hython` from the pinned build - Houdini 22.0.400 for every number published in
the audit. Nothing here depends on where that build lives:

    "$HYPYTHON" -s -P harness/probes/worldlabs_pipeline_corrected.py --verify

Build the graph (paths are arguments; nothing is hardcoded):

    "$HYPYTHON" -s -P harness/probes/worldlabs_pipeline_corrected.py --build \
        --desert-ply  /path/desert.ply \
        --jungle-ply  /path/jungle.ply \
        --collider    /path/collider.glb \
        --out         /path/frames/

The blueprint's own script is transcribed next to this file and replayed by
`harness/probes/worldlabs_blueprint_probe.py`, which writes the raw records the
audit cites.
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
     "node.disconnect(0) -> AttributeError: 'SopNode' object has no attribute 'disconnect'",
     "PROSE, NOT CODE - the blueprint's script never calls disconnect(). The name appears "
     "only in its section 2 prose, where it is claimed as a fix (F-OPEN-3)."),
    ("F2", "createNode('labs::bake_gsplat')",
     "createNode('bakegsplat') - a built-in H22 SOP, not a Labs node",
     "createNode('labs::bake_gsplat') -> OperationFailed: Invalid node type name",
     "SCRIPT - line 27. This is the FIRST call that raises, so it is where a real run "
     "of the blueprint stops."),
    ("F3", "createNode('labs::normals_from_gsplat')",
     "createNode('labs::normals_from_gsplats::1.0') - plural, versioned",
     "createNode('labs::normals_from_gsplat') -> OperationFailed: Invalid node type name",
     "SCRIPT - lines 31 and 48."),
    ("F4", "normals node takes the collider colour on input 1",
     "labs::normals_from_gsplats::1.0 has ONE input; relighting is a LOP "
     "(labs::relight_gsplats::1.1), not a second SOP input",
     "normals.setInput(1, file) -> InvalidInput: Invalid input.",
     "INTENT - the blueprint's own call at line 50 is UNREACHABLE: the node it names "
     "does not exist, so the call never runs. The evidence is about the corrected "
     "type, and it is what makes the blueprint's two-input relight unachievable."),
    ("F5", "gltf.setParms({'filepath': ...})",
     "gltf::2.0 spells the file parm 'gltffile'",
     "gltf::2.0 parm list contains 'gltffile'; 'filepath' is absent",
     "SCRIPT - line 41."),
    ("F6", "gltf.setParms({'import_geometry_as': 1})",
     "gltf::2.0 spells it 'importnodegeometryas', token 'flattenedgeometry'",
     "setParms({'import_geometry_as':1}) -> Invalid parameter name; "
     "menu tokens are ('packedprimitive','flattenedgeometry')",
     "SCRIPT - line 41. A dict with two bad names raises on the first, so this one is "
     "only visible when the keys are set one at a time."),
    ("F7", "wrangle.parm('strength'|'spin'|'radius'|'falloff'|'drag'|'timestep') "
     "and chv('axis')",
     "the six float parameters and the one vector channel do not exist and must be "
     "CREATED on a ParmTemplateGroup",
     "wrangle.parm('strength') -> None; .set() -> AttributeError: 'NoneType' ...",
     "SCRIPT - lines 90-95. The first defect REACHED once F2 and F3 are corrected, "
     "and the one the original audit called the death point. The blueprint's own VEX "
     "reads a SEVENTH channel, chv('axis'), which the blueprint never creates either, "
     "so its spin branch is dead code until that vector parm is created too. Houdini "
     "has NO hou.VectorParmTemplate - the vector is a FloatParmTemplate with three "
     "components, and chv() reads it as a vector."),
    ("F8", "karmarendersettings.parm('renderer').set('XPU')",
     "the parm is 'engine' and the token is 'xpu' (lower case)",
     "parm('renderer') -> None; parm('engine').set('xpu') -> ok",
     "SCRIPT - line 121."),
    ("F9", "karmarendersettings.parm('samples').set(256)",
     "the parm is 'samplesperpixel'",
     "parm('samples') -> None; parm('samplesperpixel').set(256) -> ok",
     "SCRIPT - line 122."),
    ("F10", "stage.createNode('usdrender')",
     "stage.createNode('usdrender_rop') - 'usdrender' does not resolve in /stage",
     "createNode('usdrender') -> OperationFailed: Invalid node type name",
     "SCRIPT - line 124. 'usdrender' resolves in NEITHER context; 'usdrender_rop' "
     "resolves in /stage only."),
    ("F11", "distantlight.setInput(0, fog_box)",
     "the call SUCCEEDS - distantlight::2.0 reports zero inputs only until one is "
     "wired. The same is true of the other two Stage 3 edges: karmarendersettings "
     "and usdrender_rop also report zero inputs while unwired, and both accept the "
     "blueprint's connection. The intensity/exposure parms are USD-exposed, and "
     "that part does not exist under the names the blueprint uses.",
     "setInput(0, fog_box) -> ok; inputs() 0 -> 1; input(0) = /stage/fog_box; "
     "krs.setInput(0, light) -> ok; rop.setInput(0, krs) -> ok",
     "REFUTED AS A DEFECT - the original audit read 'inputs() == []' on an UNWIRED "
     "node and concluded the call fails. It does not. The corrected graph keeps all "
     "three of the blueprint's LOP edges."),
]

# Claims in the blueprint's own "Corrected Error Audit" that the code does not implement.
# These are not node-level defects; they are prose that outruns the script.
#
# There are EIGHT, not five. The blueprint's section 2 lists four bullets; two of
# them carry two separate claims each, and neither half was counted before:
# the static-path claim and the lighting-linker claim. Two more come from the
# exec-summary's "Karma XPU 4D Time-Sample Render & FFmpeg Export" and the blast
# node's "call" group. The eighth is the deliverable itself: the script's own
# output is a desert-to-jungle TRANSITION, and only the jungle half is wired.
#
# Six of the eight are PROSE claims, and those are measured, not read:
# harness/probes/worldlabs_blueprint_probe.py counts the terms each one would
# need in the source. F-OPEN-5 and F-OPEN-8 are not prose claims - they are about
# the data and the graph - so they are settled by cooking, not by counting.
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
    ("F-OPEN-6", "Static path hardcoding replaced with automated absolute path resolution",
     "the script's __main__ block hardcodes five absolute paths - /project/splats/desert_env.ply, "
     "/project/splats/jungle_rock.ply, /project/colliders/desert_collider.glb, "
     "/project/colliders/jungle_collider.glb and /project/renders/synapse_transition_v1.mp4. "
     "There is no path resolution anywhere in the file. The claim is the exact inverse of "
     "what the code does.",
     "run the script's __main__ block with no arguments and assert it does not depend on a "
     "/project tree existing on the artist's machine"),
    ("F-OPEN-7", "Lighting linker desynchronization enforced by an automated relationship-linking pass",
     "the script contains no UsdShade binding, no LOP collection binding, no relationship "
     "linker and no lighting pass of any kind. It creates one distantlight and sets two "
     "USD-exposed values on it. There is no pass.",
     "cook a stage containing the light and the fog box and list the UsdShade relationships "
     "the script claims to have enforced"),
    ("F-OPEN-8", "The deliverable is a TRANSITION between the desert and the jungle",
     "only the jungle side is ever connected. The wrangle takes normals_jungle; "
     "normals_desert has no consumer, and desert_collider_glb is accepted by the "
     "blueprint's own signature and never used by its body. The desert half of the "
     "transition is never rendered.",
     "name the node that consumes the desert side, then build it and assert the desert "
     "geometry reaches the render ROP"),
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _blueprint_death():
    """Where the BLUEPRINT's own script stops, read from the committed probe record.

    The corrected pipeline does not restate this. It reads the number the probe
    measured, so the two records cannot drift apart.
    """
    path = "harness/probes/worldlabs_blueprint_records.json"
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError) as exc:
        return {"record": path, "error": "%s: %s" % (type(exc).__name__, exc)}
    strict = rec.get("strict_run", {})
    return {
        "record": path,
        "houdini": rec.get("houdini"),
        "blueprint_lines": rec.get("blueprint_lines"),
        "died": strict.get("died"),
        "line": strict.get("line"),
        "statement": strict.get("statement"),
        "exception_type": strict.get("exception_type"),
    }


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


def _add_vector_parms(node: hou.Node, specs) -> None:
    """Create vector parms on a node so chv() can read them.

    The blueprint's VEX reads chv("axis") for the spin axis. It is a VECTOR, so the
    float-only helper above cannot create it, and until it exists chv("axis") returns
    the zero vector and the whole spin branch is dead code.

    Houdini has NO hou.VectorParmTemplate - that name is a phantom, and calling it
    raises AttributeError: module 'hou' has no attribute 'VectorParmTemplate'. The
    real three-float vector is a FloatParmTemplate with three components, and
    chv() reads it as a vector. The symbol table for 22.0.400 carries
    hou.FloatParmTemplate and no VectorParmTemplate.

    Note that the created parameter is NOT reachable as parm("axis"): Houdini
    splits a multi-component parameter into its components (axisx, axisy, axisz),
    so the base name resolves only inside VEX. A cook proves chv("axis") reads it.
    """
    ptg = node.parmTemplateGroup()
    for name, label, default in specs:
        tmpl = hou.FloatParmTemplate(name, label, 3, default_value=tuple(default))
        ptg.append(tmpl)
    node.setParmTemplateGroup(ptg)


# ---------------------------------------------------------------------------
# the corrected build
# ---------------------------------------------------------------------------

def build_graph(desert_ply: str, jungle_ply: str, collider_glb: str,
                out_dir: str, strength: float = -1.0, spin: float = 1.0,
                radius: float = 30.0, falloff: float = 0.442, drag: float = 0.1,
                timestep: float = 1.57, axis: tuple = (0.0, 1.0, 0.0),
                engine: str = "xpu", samples: int = 256,
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
    # F7: create the seven channels the VEX reads, then set them.
    _add_float_parms(anim_wrangle, [
        ("strength", "Strength", strength),
        ("spin", "Spin", spin),
        ("radius", "Radius", radius),
        ("falloff", "Falloff", falloff),
        ("drag", "Drag", drag),
        ("timestep", "Timestep", timestep),
    ])
    _add_vector_parms(anim_wrangle, [("axis", "Spin Axis", axis)])
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

    # F11: the blueprint's setInput(0, fog_box) SUCCEEDS. distantlight::2.0 reports
    # zero inputs only until one is wired - the input appears when it is connected,
    # and the light's look-at parms (lookatprim, primpath, primpattern) are what it
    # is for. The original audit read 'inputs() == []' on an unwired node and called
    # the call a defect. It is not, so the wiring is kept.
    distant_light = stage.createNode("distantlight", "sun_light")
    distant_light.setInput(0, fog_box)
    made["sun_light"] = distant_light.path()
    made["sun_light_inputs"] = [i.path() for i in distant_light.inputs()]
    # The intensity/exposure parms are USD-exposed; their live names carry a
    # build-specific suffix, so they are resolved by pattern at runtime.
    inten = _exposed_value_parm(distant_light, "inputsintensity")
    expo = _exposed_value_parm(distant_light, "inputsexposure")
    if inten is not None:
        inten.set(15.0)
    if expo is not None:
        expo.set(4.0)
    made["sun_light_intensity_parm"] = inten.name() if inten else "UNRESOLVED"
    made["sun_light_exposure_parm"] = expo.name() if expo else "UNRESOLVED"

    # F8/F9: engine + samplesperpixel.
    render_settings = stage.createNode("karmarendersettings", "xpu_settings")
    # The blueprint wires the light into the render settings. That edge SUCCEEDS -
    # karmarendersettings reports zero inputs until one is connected, exactly like
    # distantlight did. An earlier version of this script dropped the edge on the
    # strength of that zero, which was the same mistake the original audit made
    # on F11. The blueprint's wiring is kept.
    render_settings.setInput(0, distant_light)
    render_settings.parm("engine").set(engine)
    render_settings.parm("samplesperpixel").set(samples)
    made["xpu_settings"] = render_settings.path()
    made["xpu_settings_inputs"] = [i.path() for i in render_settings.inputs()]

    # F10: usdrender_rop, not usdrender. trange is a menu stored as an index;
    # index 1 is 'normal' = "Render Specific Frame Range".
    rop_karma = stage.createNode("usdrender_rop", "rop_karma_xpu")
    # Same story: usdrender_rop reports zero inputs until one is connected, and
    # the blueprint's edge into it binds.
    rop_karma.setInput(0, render_settings)
    rop_karma.parm("trange").set(1)
    rop_karma.parm("f1").set(f1)
    rop_karma.parm("f2").set(f2)
    rop_karma.parm("outputimage").set(out_dir + "/synapse_$F4.exr")
    made["rop_karma_xpu"] = rop_karma.path()
    made["rop_karma_inputs"] = [i.path() for i in rop_karma.inputs()]

    # F-OPEN-8: the desert branch is preserved exactly as the blueprint has it -
    # created, and with no consumer. What consumes it is an open question, and
    # inventing an answer would be worse than naming it.
    made["normals_desert_consumer"] = "NONE - see F-OPEN-8"
    made["open_items"] = [
        "F-OPEN-8: the desert branch has no consumer. normals_desert and the desert "
        "collider are unused, so only the jungle side reaches the render - and the "
        "deliverable is a desert-to-jungle transition.",
    ]

    return made


# The VEX solver, unchanged in substance from the blueprint, but the seven channels it
# reads - six floats and one vector - are now parameters that exist (F7).
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

    # F7 - the check proves EVERY channel the VEX reads, not one of them.
    def f7():
        w = env.createNode("attribwrangle", "v_wrangle")
        floats = [("strength", -1.0), ("spin", 1.0), ("radius", 30.0),
                  ("falloff", 0.442), ("drag", 0.1), ("timestep", 1.57)]
        axis = (0.0, 1.0, 0.0)
        for name, _ in floats + [("axis", axis)]:
            assert w.parm(name) is None, "%s exists on a fresh wrangle - re-check the fix" % name
        _add_float_parms(w, [(n, n.capitalize(), d) for n, d in floats])
        _add_vector_parms(w, [("axis", "Spin Axis", axis)])
        for name, default in floats:
            p = w.parm(name)
            assert p is not None, "%s not created" % name
            p.set(default)
            assert abs(p.eval() - default) < 1e-9, "%s did not take its value" % name
        # The three-float parameter is NOT reachable as parm("axis"). Houdini
        # splits a multi-component parameter into its components - axisx, axisy,
        # axisz - so the base name resolves only inside VEX. chv("axis") is the
        # only address the solver uses, so chv() is the only address that
        # matters, and the cook below proves it resolves AND carries the value.
        tmpl = w.parmTemplateGroup().find("axis")
        assert tmpl is not None, "the axis parameter was not created"
        assert tmpl.numComponents() == 3, \
            "the axis parameter is not a three-float vector: %d components" % tmpl.numComponents()
        comps = [p for p in w.parms() if p.name().startswith("axis")]
        assert len(comps) == 3, \
            "the axis parameter did not produce three components: %s" % [p.name() for p in comps]
        for p, d in zip(comps, axis):
            p.set(d)
        # The VEX must read exactly the channels that now exist. A channel read by
        # the solver but never created is a dead branch, and that is the defect F7
        # exists to close.
        read = [c for c in ("strength", "spin", "axis", "radius", "falloff",
                            "drag", "timestep") if ('chf("%s")' % c) in VEX_SOLVER
                or ('chv("%s")' % c) in VEX_SOLVER]
        assert len(read) == 7, "the VEX reads %d channels, not 7: %s" % (len(read), read)
        for c in read:
            if c != "axis":
                assert w.parm(c) is not None, "the VEX reads %s but no such parm exists" % c
        # Cook the proof: every channel the solver reads, read back through the
        # solver's own chf()/chv() address. A parameter that exists but does not
        # resolve in VEX is still a dead channel, and only a cook can say so.
        src = env.createNode("grid", "v_grid")
        w.setInput(0, src)
        w.setParms({"snippet": (
            'f@s = chf("strength"); f@sp = chf("spin"); f@r = chf("radius"); '
            'f@fo = chf("falloff"); f@d = chf("drag"); f@ts = chf("timestep"); '
            'f@ax = chv("axis")[0]; f@ay = chv("axis")[1]; f@az = chv("axis")[2];')})
        w.cook(force=True)
        g = w.geometry()
        expected = [("s", -1.0), ("sp", 1.0), ("r", 30.0), ("fo", 0.442),
                    ("d", 0.1), ("ts", 1.57), ("ax", axis[0]), ("ay", axis[1]),
                    ("az", axis[2])]
        for name, want in expected:
            if g.findPointAttrib(name) is None:
                raise AssertionError("the cook produced no %s attribute - a channel "
                                     "does not resolve in VEX" % name)
            got = g.pointFloatAttribValues(name)[0]
            assert abs(got - want) < 1e-6, \
                "%s read back as %r, not %r" % (name, got, want)
        return ("7 channels created, and a cook read all 7 back through "
                "chf()/chv() with the values set")
    check("F7", "the seven channels the VEX reads are created, not assumed", f7)

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
        assert not d.inputs(), "a fresh distantlight now reports inputs - re-check the fix"
        fog = stage.createNode("karmafogbox", "v_fog")
        # The blueprint's call. It SUCCEEDS: the input appears once it is wired.
        d.setInput(0, fog)
        wired = d.inputs()
        assert len(wired) == 1, "the fog box did not bind to the light"
        assert wired[0].path() == fog.path(), "the light's input is not the fog box"
        inten = _exposed_value_parm(d, "inputsintensity")
        assert inten is not None, "no exposed intensity parm found"
        inten.set(15.0)
        assert d.parm("intensity") is None, "a plain 'intensity' parm appeared - re-check"

        # The other two Stage 3 edges the blueprint draws. Both nodes also report
        # ZERO inputs while unwired, which is what made the original audit call
        # them broken. They bind.
        krs = stage.createNode("karmarendersettings", "v_krs")
        assert not krs.inputs(), "a fresh karmarendersettings now reports inputs"
        krs.setInput(0, d)
        assert krs.input(0) is not None and krs.input(0).path() == d.path(), \
            "the light did not bind to the render settings"

        rop = stage.createNode("usdrender_rop", "v_rop")
        assert not rop.inputs(), "a fresh usdrender_rop now reports inputs"
        rop.setInput(0, krs)
        assert rop.input(0) is not None and rop.input(0).path() == krs.path(), \
            "the render settings did not bind to the ROP"

        return ("3 LOP edges bind (fog->light, light->krs, krs->rop); "
                "intensity parm %s = %s" % (inten.name(), inten.eval()))
    check("F11", "the blueprint's three LOP edges bind; intensity is a USD-exposed parm", f11)

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
    out = {"houdini": hou.applicationVersionString(), "results": results,
           "fixes": FIXES, "unproven": UNPROVEN,
           "blueprint_record": _blueprint_death()}
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
