# KineFX Rigging and Animation

## Triggers
kinefx, kine fx, kinefx rig, kinefx skeleton, kinefx retarget, kinefx ik, full body ik,
fbik, rigfullbodyik, bonedeform, bonecapture, bone capture, bone deform, motion clip,
motionclip, motionclipblend, motionclipsequence, retargetbiped, mappoints, rig stash pose,
rig_stashpose, kinefx fbx, kinefx usd, kinefx bvh, joint attribute, transform attribute,
skin weights, capture weights, procedural rig, kinefx vex, skeleton sop, kinefx crowd

## Context
KineFX is Houdini's SOP-based rigging and retargeting system. A skeleton is plain SOP geometry:
points = joints, polylines = bone connections. All SOP tools (wrangle, group, blast, merge)
work directly on skeletons. This makes rigs fully procedural and scriptable via Python and VEX.

---

## Skeleton Creation

```python
import hou

# --- Build a skeleton network from scratch ---
obj = hou.node("/obj")
geo = obj.createNode("geo", "kinefx_rig")
geo.moveToGoodPosition()

# Skeleton SOP: builds joint hierarchy from UI
skel = geo.createNode("skeleton", "skeleton1")

# Rig Pose: set initial pose interactively
rigpose = geo.createNode("rigpose", "rigpose1")
rigpose.setInput(0, skel)

# Stash rest pose — MUST do this before animation
stash = geo.createNode("rig_stashpose", "stashpose1")
stash.setInput(0, rigpose)

# Output null
out = geo.createNode("null", "OUT_skeleton")
out.setInput(0, stash)
out.setDisplayFlag(True)
out.setRenderFlag(True)

geo.layoutChildren()
```

```python
# --- Import skeleton + mesh from FBX ---
import hou

obj = hou.node("/obj")
geo = obj.createNode("geo", "fbx_character")

# File SOP reads FBX; KineFX auto-detects skeleton
file_sop = geo.createNode("file", "fbx_in")
file_sop.parm("file").set("D:/Characters/hero.fbx")

# kinefx_characterunpack splits packed character into skeleton + skin
unpack = geo.createNode("kinefx_characterunpack", "unpack1")
unpack.setInput(0, file_sop)
# Output 0 = skeleton (points+lines), Output 1 = skin mesh

skel_null = geo.createNode("null", "OUT_skel")
skel_null.setInput(0, unpack, 0)   # first output = skeleton

mesh_null = geo.createNode("null", "OUT_mesh")
mesh_null.setInput(0, unpack, 1)   # second output = skin mesh

geo.layoutChildren()
```

```python
# --- Import from USD (UsdSkel schema) ---
import hou

stage = hou.node("/stage")
sop_import = stage.createNode("sopimport", "kinefx_from_usd")
sop_import.parm("soppath").set("/obj/fbx_character/OUT_skel")
# USD automatically maps KineFX skeleton to UsdSkel skeleton prim
```

---

## Joint Attributes

```python
import hou

# Access skeleton geometry to read joint attributes
geo_node = hou.node("/obj/kinefx_rig/OUT_skeleton")
geo = geo_node.geometry()

# Iterate all joints (points)
for pt in geo.points():
    name      = pt.attribValue("name")       # str  — joint name e.g. "hip", "L_shoulder"
    transform = pt.attribValue("transform")  # matrix4 — local transform (16 floats)
    pos       = pt.position()                # hou.Vector3 — world position
    print(f"Joint: {name:20s}  pos={pos}")

# Find a specific joint by name
def joint_by_name(geo, joint_name):
    for pt in geo.points():
        if pt.attribValue("name") == joint_name:
            return pt
    return None

hip_pt = joint_by_name(geo, "hip")
if hip_pt:
    print("Hip world pos:", hip_pt.position())
```

```vex
// VEX: read all standard KineFX joint attributes in a wrangle
// Run over: Points  (each point = one joint)

string jname      = s@name;           // joint name
matrix xform      = 4@transform;      // local transform (matrix4)
matrix local_xf   = 4@localtransform; // local space transform
vector world_pos  = @P;               // world position of joint
vector4 orient_q  = p@orient;         // world orientation quaternion

// Print in a debug wrangle (remove for production)
printf("Joint: %s  pos: %v\n", jname, world_pos);
```

---

## Retargeting

```python
import hou

obj = hou.node("/obj")
geo = obj.createNode("geo", "retarget_rig")

# Source: animated capture (e.g., mocap BVH)
src_file = geo.createNode("file", "source_anim")
src_file.parm("file").set("D:/Mocap/walk_cycle.bvh")
# agent_bvhimport reads BVH into KineFX skeleton
bvh = geo.createNode("agent_bvhimport", "bvh_import")
bvh.setInput(0, src_file)

# Target: hero character skeleton (at rest pose)
tgt_file = geo.createNode("file", "target_skel")
tgt_file.parm("file").set("D:/Characters/hero_rest.bgeo")

# retargetbiped: auto-maps standard biped joints
retarget = geo.createNode("retargetbiped", "retarget1")
retarget.setInput(0, bvh)        # input 0 = source animated skeleton
retarget.setInput(1, tgt_file)   # input 1 = target rest skeleton

# Key retargetbiped parameters
retarget.parm("sourcerestpose").set(0)   # 0=use first frame as rest, 1=external input
retarget.parm("targetrestpose").set(0)
retarget.parm("scalemotion").set(1)      # 1=scale motion to match target proportions
retarget.parm("rootmotion").set(1)       # 1=transfer root (hip) translation

out = geo.createNode("null", "OUT_retargeted")
out.setInput(0, retarget)
out.setDisplayFlag(True)
geo.layoutChildren()
```

```python
# --- mappoints SOP: manual joint name mapping ---
import hou

geo_node = hou.node("/obj/retarget_rig")

mappts = geo_node.createNode("mappoints", "name_map")
mappts.setInput(0, geo_node.node("bvh_import"))   # source skeleton
mappts.setInput(1, geo_node.node("target_skel"))  # target skeleton

# Mapping mode: 0=by name, 1=by position, 2=manual
mappts.parm("mode").set(0)  # by name

# Manual name remaps (source_name -> target_name pairs)
# These live in a multiparm; index from 1
mappts.parm("numremaps").set(3)
mappts.parm("sourcename1").set("Hips")
mappts.parm("targetname1").set("hip")
mappts.parm("sourcename2").set("LeftUpLeg")
mappts.parm("targetname2").set("L_thigh")
mappts.parm("sourcename3").set("RightUpLeg")
mappts.parm("targetname3").set("R_thigh")
```

---

## Full-Body IK (FBIK)

```python
import hou

obj = hou.node("/obj")
geo = obj.createNode("geo", "fbik_rig")

# Skeleton with stashed rest pose feeds FBIK
skel = geo.createNode("file", "rest_skel")
skel.parm("file").set("D:/Characters/hero_rest.bgeo")

stash = geo.createNode("rig_stashpose", "stash1")
stash.setInput(0, skel)

fbik = geo.createNode("rigfullbodyik", "fbik1")
fbik.setInput(0, stash)   # skeleton with rest pose attribute

# --- FBIK parameters ---
fbik.parm("iterations").set(30)      # solver iterations; 10=fast/rough, 50=precise
fbik.parm("damping").set(0.5)        # prevents joint flipping (0=off, 1=max)
fbik.parm("pinroot").set(1)          # 1=keep root joint (hip) fixed in world space
fbik.parm("tolerance").set(0.0001)   # convergence threshold

# IK targets — each target is a world-space point the solver pulls toward
# targets multiparm: one entry per effector (hand, foot, head, etc.)
fbik.parm("numtargets").set(4)

# Left hand effector
fbik.parm("targetname1").set("L_hand")     # must match joint @name
fbik.parm("targetweight1").set(1.0)        # 1.0 = fully IK-driven
fbik.parm("targetpriority1").set(2)        # higher = more important

# Right hand
fbik.parm("targetname2").set("R_hand")
fbik.parm("targetweight2").set(1.0)
fbik.parm("targetpriority2").set(2)

# Left foot
fbik.parm("targetname3").set("L_foot")
fbik.parm("targetweight3").set(1.0)
fbik.parm("targetpriority3").set(3)        # feet highest priority (grounding)

# Right foot
fbik.parm("targetname4").set("R_foot")
fbik.parm("targetweight4").set(1.0)
fbik.parm("targetpriority4").set(3)

out = geo.createNode("null", "OUT_fbik")
out.setInput(0, fbik)
out.setDisplayFlag(True)
geo.layoutChildren()
```

```vex
// VEX: manually drive an IK target position from an animated null
// Place in a wrangle BEFORE the rigfullbodyik node
// Run over: Points, @name == "L_hand_target"

// Read target position from a world-space reference object
string ref_path = "/obj/hand_ctrl";   // Houdini object driving the hand
matrix ref_xform = optransform(ref_path);
vector target_pos = cracktransform(XFORM_SRT, XFORM_XYZ, 0, {0,0,0}, ref_xform);

// Set this joint's world position so FBIK sees it as the effector goal
@P = target_pos;
```

---

## Motion Clips

```python
import hou

obj = hou.node("/obj")
geo = obj.createNode("geo", "motion_clips")

# --- Create a motion clip from an animated skeleton ---
anim_skel = geo.createNode("file", "walk_anim")
anim_skel.parm("file").set("D:/Characters/walk_cycle.bgeo.sc")

clip_create = geo.createNode("motionclip", "clip_walk")
clip_create.setInput(0, anim_skel)
clip_create.parm("clipname").set("walk")
clip_create.parm("startframe").set(1)
clip_create.parm("endframe").set(30)
clip_create.parm("loopable").set(1)   # 1=mark as loopable for sequencing

# Second clip
run_anim = geo.createNode("file", "run_anim")
run_anim.parm("file").set("D:/Characters/run_cycle.bgeo.sc")

clip_run = geo.createNode("motionclip", "clip_run")
clip_run.setInput(0, run_anim)
clip_run.parm("clipname").set("run")
clip_run.parm("startframe").set(1)
clip_run.parm("endframe").set(20)
clip_run.parm("loopable").set(1)

# --- Blend between two clips ---
blend = geo.createNode("motionclipblend", "blend_walk_run")
blend.setInput(0, clip_create)   # clip A
blend.setInput(1, clip_run)      # clip B

# Blend weight: 0.0 = full walk, 1.0 = full run
# Keyframe this to crossfade
blend.parm("weight").setExpression("fit($F, 30, 60, 0, 1)")  # ramp from walk to run

blend.parm("blendtype").set(0)   # 0=crossfade, 1=additive
blend.parm("loopmode").set(1)    # 1=loop, 0=clamp, 2=ping-pong

# --- Sequence clips end-to-end ---
seq = geo.createNode("motionclipsequence", "sequence1")
seq.setInput(0, clip_create)   # first clip
seq.setInput(1, clip_run)      # appended after
seq.parm("blendframes").set(5) # 5-frame crossfade at transition

out = geo.createNode("null", "OUT_clips")
out.setInput(0, seq)
out.setDisplayFlag(True)
geo.layoutChildren()
```

---

## Skinning — bonecapture + bonedeform

```python
import hou

obj = hou.node("/obj")
geo = obj.createNode("geo", "skinning_rig")

# Rest pose mesh
rest_mesh = geo.createNode("file", "mesh_rest")
rest_mesh.parm("file").set("D:/Characters/hero_mesh_rest.bgeo")

# Rest pose skeleton
rest_skel = geo.createNode("file", "skel_rest")
rest_skel.parm("file").set("D:/Characters/hero_skel_rest.bgeo")

# Animated skeleton (time-dependent)
anim_skel = geo.createNode("file", "skel_anim")
anim_skel.parm("file").set("D:/Characters/hero_skel_anim.$F.bgeo")

# --- bonecapture: compute skin weights ---
capture = geo.createNode("bonecapture", "bonecapture1")
capture.setInput(0, rest_mesh)   # mesh to weight
capture.setInput(1, rest_skel)   # skeleton in rest pose

# Capture method: 0=Biharmonic (best quality, slow), 1=Proximity (fast)
capture.parm("method").set(0)            # Biharmonic
capture.parm("captureradius").set(0.5)   # search radius for joint influence
capture.parm("maxinfluences").set(4)     # max joints per point (4 is standard)
capture.parm("normalize").set(1)         # 1=normalize weights to sum=1.0

# Paint weights interactively: bonecapturepainter SOP after bonecapture

# Cache capture so it doesn't recompute every frame
cache = geo.createNode("filecache", "cache_weights")
cache.setInput(0, capture)
cache.parm("file").set("D:/Characters/hero_weights.$F.bgeo")
cache.parm("loadfromdisk").set(1)        # set to 1 after first cook

# --- bonedeform: apply animation to mesh ---
deform = geo.createNode("bonedeform", "bonedeform1")
deform.setInput(0, cache)       # weighted mesh (from bonecapture)
deform.setInput(1, rest_skel)   # rest skeleton (for reference bind pose)
deform.setInput(2, anim_skel)   # animated skeleton (time-varying)

deform.parm("method").set(0)    # 0=Linear Blend Skinning, 1=Dual Quaternion
deform.parm("dqblend").set(0.5) # 0.5=50% DQ blend (reduces candy-wrapper on twists)

out = geo.createNode("null", "OUT_deformed")
out.setInput(0, deform)
out.setDisplayFlag(True)
geo.layoutChildren()
```

```python
# --- Read and inspect skin weights after bonecapture ---
import hou
import json

geo_node = hou.node("/obj/skinning_rig/bonecapture1")
geo = geo_node.geometry()

bc_attrib = geo.findPointAttrib("boneCapture")  # the capture weight attribute
if bc_attrib:
    pt = geo.point(0)  # first vertex
    weights = pt.attribValue("boneCapture")
    # boneCapture is an array: [joint_idx, weight, joint_idx, weight, ...]
    pairs = [(weights[i], weights[i+1]) for i in range(0, len(weights), 2)]
    print("Point 0 weights:", pairs)
```

---

## Procedural Rigging in VEX

```vex
// VEX Wrangle: rotate a single joint by name
// Run over: Points

// Only affect the "spine1" joint
if (s@name == "spine1") {
    // Get current local transform
    matrix xform = 4@transform;

    // Build a 45-degree rotation around Y axis
    matrix rot = ident();
    rotate(rot, radians(45.0), {0, 1, 0});

    // Apply rotation to existing transform
    4@transform = xform * rot;
}
```

```vex
// VEX Wrangle: propagate hip twist into spine (procedural twist driver)
// Run over: Points

int hip_pt = nametopoint(0, "hip");
if (hip_pt < 0) return;  // hip not found — bail

// Read hip local transform
matrix hip_xf = point(0, "transform", hip_pt);

// Extract Euler rotation from hip transform (XYZ order)
vector hip_euler = cracktransform(XFORM_SRT, XFORM_XYZ, 1, {0,0,0}, hip_xf);
float hip_twist = hip_euler.y;  // Y = yaw / twist

// Apply scaled twist fraction to spine joints
string spine_joints[] = {"spine1", "spine2", "spine3"};
float twist_falloff = 0.3;  // each spine joint gets 30% of hip twist

foreach (int i; string jname; spine_joints) {
    int pt = nametopoint(0, jname);
    if (pt != @ptnum) continue;  // only modify this point in the loop

    matrix spine_xf = 4@transform;
    float fraction = twist_falloff * (i + 1);  // spine3 gets most twist
    matrix twist_rot = ident();
    rotate(twist_rot, radians(hip_twist * fraction), {0, 1, 0});
    4@transform = spine_xf * twist_rot;
}
```

```vex
// VEX Wrangle: procedural stretch — scale bone length along parent->child axis
// Run over: Points, group: "arm_joints"

int parent_pt = primvertex(0, @primnum, 0);  // first vertex of polyline = parent
if (parent_pt < 0) return;

vector parent_pos = point(0, "P", parent_pt);
vector child_pos  = @P;

// Stretch factor (could be driven by a channel or attribute)
float stretch = chf("stretch_amount");  // UI slider

vector dir    = normalize(child_pos - parent_pos);
float  length = distance(child_pos, parent_pos);

// Move this joint further along bone axis
@P = parent_pos + dir * length * stretch;
```

```vex
// VEX Wrangle: mirror left joints to right (procedural symmetry)
// Run over: Points

if (startswith(s@name, "L_")) {
    // Find the corresponding right joint
    string right_name = "R_" + s@name[2:];
    int right_pt = nametopoint(0, right_name);
    if (right_pt < 0) return;

    // Mirror position across YZ plane (negate X)
    vector left_pos = @P;
    setpointattrib(0, "P", right_pt, set(-left_pos.x, left_pos.y, left_pos.z));

    // Mirror transform: negate X column and X row of rotation
    matrix left_xf  = 4@transform;
    matrix mirror_m = ident();
    mirror_m = set(-1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1);  // X-flip
    matrix right_xf  = mirror_m * left_xf * mirror_m;
    setpointattrib(0, "transform", right_pt, right_xf);
}
```

---

## FBX / USD / BVH Import and Export

```python
import hou

# --- FBX Import via file SOP ---
obj = hou.node("/obj")
geo = obj.createNode("geo", "fbx_import")
f = geo.createNode("file", "fbx_file")
f.parm("file").set("D:/Characters/character.fbx")
# Houdini auto-detects FBX and unpacks into packed character geo

unpack = geo.createNode("kinefx_characterunpack", "unpack")
unpack.setInput(0, f)
# output 0 = skeleton, output 1 = skin mesh

# --- FBX Export via ROP ---
rop_net = hou.node("/out")
fbx_rop = rop_net.createNode("kinefx_fbxcharacterexport", "fbx_export")
fbx_rop.parm("skelpath").set("/obj/fbx_import/unpack")
fbx_rop.parm("sopoutput").set("D:/Export/hero_export.fbx")
fbx_rop.parm("trange").set(1)           # export frame range
fbx_rop.parm("f1").set(1)
fbx_rop.parm("f2").set(120)
fbx_rop.parm("exportscale").set(1.0)    # 1.0=meters; use 100.0 for cm FBX targets
fbx_rop.render()                        # execute export
```

```python
# --- USD Export: write skeleton as UsdSkel ---
import hou

stage = hou.node("/stage")

# sopimport LOP bridges KineFX skeleton into USD
sop_import = stage.createNode("sopimport", "skel_to_usd")
sop_import.parm("soppath").set("/obj/fbx_import/unpack")
sop_import.parm("importasusd").set(1)   # 1=use UsdSkel schema

# Configure output prim path
sop_import.parm("primpath").set("/characters/hero")

# USD ROP: write to disk
usd_rop = hou.node("/stage").createNode("usd_rop", "export_usd")
usd_rop.setInput(0, sop_import)
usd_rop.parm("lopoutput").set("D:/Export/hero.usd")
usd_rop.parm("trange").set(1)
usd_rop.parm("f1").set(1)
usd_rop.parm("f2").set(120)
usd_rop.render()
```

```python
# --- BVH Mocap Import ---
import hou

obj = hou.node("/obj")
geo = obj.createNode("geo", "mocap_bvh")

bvh = geo.createNode("agent_bvhimport", "bvh_in")
bvh.parm("bvhfile").set("D:/Mocap/run_01.bvh")
bvh.parm("scale").set(0.01)    # BVH usually in cm; convert to meters

# Output is a time-varying KineFX skeleton ready for retargeting
out = geo.createNode("null", "OUT_mocap")
out.setInput(0, bvh)
out.setDisplayFlag(True)
geo.layoutChildren()
```

---

## Common KineFX Issues

**Mesh doesn't deform**: The mesh is missing capture weight attributes. Run `bonecapture` on the rest pose mesh *before* connecting to `bonedeform`. The rest skeleton input on `bonedeform` must match the skeleton used during capture.

**Joints flip during animation**: Gimbal lock or IK instability. Increase `rigfullbodyik` damping (try 0.5-0.8). Check that rotation order on joints is consistent (default XYZ). Degenerate rest pose (zero-length bones) also causes flipping — verify all joints have non-zero separation.

**Retarget produces wrong poses**: Joint name mapping in `mappoints` is incorrect or rest poses don't match. Both source and target skeletons must be in a neutral T-pose or A-pose *at the rest pose frame*. Use `rig_stashpose` on both before retargeting.

**Skeleton not visible**: Display flag not set, or the geometry is empty because `kinefx_characterunpack` output index is wrong (0=skeleton, 1=mesh — easy to swap).

**Skin weights bleed across body parts**: Capture radius on `bonecapture` is too large, or Biharmonic method is bleeding through thin geometry. Lower `captureradius`, switch to Proximity for initial pass, then paint corrections with `bonecapturepainter`.

**FBX import has wrong scale**: FBX from Maya/Max is usually in centimeters. Scale the imported skeleton by 0.01 after unpack, or set `exportscale` to 100.0 on the export side. Match the unit expectation of the target pipeline.

**Motion clip pops at transition**: No blend frames between clips in `motionclipsequence`. Increase `blendframes` (5-10 frames). Clips must be loopable and end/start in compatible poses for seamless transitions.

**boneCapture attribute missing after cache load**: The `filecache` SOP may not be preserving the attribute type correctly. Verify the cached bgeo.sc was written with the weighted mesh (not the raw mesh). Load the cache into a geometry spreadsheet and confirm `boneCapture` appears as a float-array point attribute.
