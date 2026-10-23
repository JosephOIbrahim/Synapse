#!/usr/bin/env python3
"""
SYNAPSE AUTOMATED PIPELINE: Gaussian Splat Animation & Advanced Relighting (Parts 1 & 2)
Target Platform: Houdini 22 / Solaris / Karma XPU / Python 3.11+
"""
from __future__ import annotations
import os
import hou
def run_synapse_pipeline(
    desert_ply: str,
    jungle_ply: str,
    desert_collider_glb: str,
    jungle_collider_glb: str,
    output_mov: str
) -> None:
    print("[SYNAPSE] Initializing Automated Gaussian Pipeline (Parts 1 & 2)...")
    
    # -------------------------------------------------------------------------
    # STAGE 1: Object Network Setup (SOP Context)
    # -------------------------------------------------------------------------
    obj_net = hou.node("/obj")
    env_net = obj_net.createNode("geo", "SYNAPSE_ENV_NETWORK")
    
    # 1.1 Ingest Desert Splat & Bake
    file_desert = env_net.createNode("file", "file_desert_ply")
    file_desert.setParms({"file": desert_ply})
    bake_desert = env_net.createNode("labs::bake_gsplat", "bake_desert")
    bake_desert.setInput(0, file_desert)
    
    # 1.2 Prune internal Labs Normals graph programmatically
    normals_desert = env_net.createNode("labs::normals_from_gsplat", "normals_desert")
    normals_desert.setInput(0, bake_desert)
    
    # 1.3 Ingest Jungle Splat & Collider via glTF
    file_jungle = env_net.createNode("file", "file_jungle_ply")
    file_jungle.setParms({"file": jungle_ply})
    bake_jungle = env_net.createNode("labs::bake_gsplat", "bake_jungle")
    bake_jungle.setInput(0, file_jungle)
    
    gltf_jungle = env_net.createNode("gltf", "gltf_jungle_collider")
    gltf_jungle.setParms({
        "filepath": jungle_collider_glb,
        "import_geometry_as": 1 # Flatten geometry
    })
    color_jungle = env_net.createNode("color", "color_jungle")
    color_jungle.setInput(0, gltf_jungle)
    
    normals_jungle = env_net.createNode("labs::normals_from_gsplat", "normals_jungle")
    normals_jungle.setInput(0, bake_jungle)
    normals_jungle.setInput(1, color_jungle)
    
    # -------------------------------------------------------------------------
    # STAGE 2: VEX Animation Wrangle & Color Blasting (Part 2 Core)
    # -------------------------------------------------------------------------
    anim_wrangle = env_net.createNode("attribwrangle", "anim_jungle_solver")
    anim_wrangle.setInput(0, normals_jungle)
    
    vex_code = """
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
    anim_wrangle.parm("snippet").set(vex_code)
    
    anim_wrangle.parm("strength").set(-1.0)
    anim_wrangle.parm("spin").set(1.0)
    anim_wrangle.parm("radius").set(30.0)
    anim_wrangle.parm("falloff").set(0.442)
    anim_wrangle.parm("drag").set(0.1)
    anim_wrangle.parm("timestep").set(1.57)
    
    blast_node = env_net.createNode("blast", "blast_sky_blue")
    blast_node.setInput(0, anim_wrangle)
    blast_node.parm("group").set("call")
    
    env_out = env_net.createNode("null", "ENV_OUT")
    env_out.setInput(0, blast_node)
    
    # -------------------------------------------------------------------------
    # STAGE 3: Solaris Stage & Lighting Integration (LOPs)
    # -------------------------------------------------------------------------
    stage_net = hou.node("/stage")
    sop_import = stage_net.createNode("sopimport", "import_synapse_env")
    sop_import.parm("soppath").set(env_out.path())
    
    fog_box = stage_net.createNode("karmafogbox", "fog_box")
    fog_box.setInput(0, sop_import)
    
    distant_light = stage_net.createNode("distantlight", "sun_light")
    distant_light.setInput(0, fog_box)
    distant_light.parm("intensity").set(15.0)
    distant_light.parm("exposure").set(4.0)
    
    render_settings = stage_net.createNode("karmarendersettings", "xpu_settings")
    render_settings.setInput(0, distant_light)
    render_settings.parm("renderer").set("XPU")
    render_settings.parm("samples").set(256)
    
    rop_karma = stage_net.createNode("usdrender", "rop_karma_xpu")
    rop_karma.setInput(0, render_settings)
    rop_karma.parm("trange").set(1)
    rop_karma.parm("f1").set(1)
    rop_karma.parm("f2").set(60)
    
    print("[SYNAPSE] Pipeline graph compiled successfully. Executing ROP render...")
    rop_karma.render(verbose=True)
    print(f"[SYNAPSE] Render complete. Exporting sequence to {output_mov}...")
if __name__ == "__main__":
    run_synapse_pipeline(
        desert_ply="/project/splats/desert_env.ply",
        jungle_ply="/project/splats/jungle_rock.ply",
        desert_collider_glb="/project/colliders/desert_collider.glb",
        jungle_collider_glb="/project/colliders/jungle_collider.glb",
        output_mov="/project/renders/synapse_transition_v1.mp4"
    )
# ---------------------------------------------------------------------------
# PROVENANCE
#
# Transcribed from section 3 of the external blueprint
#   "SYNAPSE Automated Pipeline Blueprint (Gaussian Splats Parts 1 & 2).docx"
# which names this file `synapse_gaussian_pipeline.py`.
#
# The .docx is the only supplied artifact. It renders the code with one EMPTY
# paragraph between every source line, so the original file's line numbering is
# not recoverable from the document - a real blank line inside the function
# carries the function's 4-space indentation, the inserted separators carry none.
# Every line above was taken from a document paragraph; the recovery dropped the
# 139 empty separator paragraphs and nothing else.
#
# Do not "fix" this file. Its defects are the subject of the audit. Run it with
# harness/probes/worldlabs_blueprint_probe.py, which records what every call does.
