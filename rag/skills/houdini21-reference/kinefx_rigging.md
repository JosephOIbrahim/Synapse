# KineFX Rigging and Animation

## Overview

KineFX is Houdini's SOP-based rigging and retargeting system. Unlike traditional OBJ-level bone rigs, KineFX operates entirely in SOPs, making it procedural and easy to iterate.

## Core Concepts

### Skeleton = Points + Hierarchy
A KineFX skeleton is just SOP geometry:
- **Points** = joints
- **Polylines** = bone connections (parent -> child)
- **`@name`** attribute = joint name (string, per point)
- **`@transform`** attribute = local transform (matrix3 or matrix4, per point)

This means all SOP tools work on skeletons: wrangle, group, blast, merge.

## Skeleton Creation

### From Scratch
```
skeleton -> rigpose -> null (output)
```

### skeleton SOP
Creates a joint hierarchy from a UI skeleton builder.

### rig_stashpose
Saves the current pose as the "rest pose". Essential before animation.

### From Imported FBX/USD
```
file (FBX/USD) -> kinefx_characterunpack -> null
```
- `kinefx_characterunpack` extracts skeleton + skin from packed character
- Produces separate geometry for skeleton (points+lines) and mesh

## Joint Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `@name` | string | Joint name (e.g., "hip", "spine1", "L_shoulder") |
| `@transform` | matrix | Local transform (3x3 or 4x4) |
| `@localtransform` | matrix | Local space transform |
| `@P` | vector | World position of joint |
| `@orient` | vector4 | World orientation quaternion |

## Retargeting

### What is Retargeting?
Transferring animation from one skeleton to another (different proportions, different joint names).

### Retarget Chain
```
source_skeleton (animated) -> mappoints -> retarget_joints -> target_skeleton
```

### mappoints SOP
Maps joints between source and target by name or position:
- **By Name**: `source_hip` -> `target_Hips` (name mapping table)
- **By Position**: Nearest joint matching
- Manual mapping for non-matching names

### retargetbiped SOP
Specialized retarget for bipedal characters:
- Auto-maps standard biped joints (hip, spine, arms, legs, head)
- Handles proportion differences automatically
- `source_restpose` and `target_restpose` inputs for proportion matching

### Retarget Workflow
1. Load source animation (FBX/BVH/USD)
2. Load target character (with skeleton)
3. Set both to rest/T-pose
4. Use `retargetbiped` or `mappoints` to create mapping
5. Bake retargeted animation to target skeleton

## Full-Body IK

### rigfullbodyik SOP
Applies full-body inverse kinematics to a skeleton.

| Parameter | Name | Description |
|-----------|------|-------------|
| Targets | `targets` | Group of joints with IK targets |
| Iterations | `iterations` | Solver iterations (10-50) |
| Damping | `damping` | Prevents joint flipping |
| Pin Root | `pinroot` | Keep root joint fixed |

### IK Workflow
```
skeleton -> rig_stashpose -> rigfullbodyik -> null
```
1. Stash the rest pose
2. Set IK targets (usually hands, feet, head)
3. Animate targets
4. Full-body IK solves the chain

## Motion Clips

### What are Motion Clips?
Reusable animation segments stored as packed geometry. Can be blended, layered, and sequenced.

### motionclip SOP
Creates a motion clip from animated skeleton:
- `startframe` / `endframe`: Clip range
- `clipname`: Name for the clip

### motionclipblend SOP
Blends between multiple motion clips:
- Crossfade between walk -> run
- Layer upper body animation onto lower body
- Additive blending for secondary motion

### motionclipsequence SOP
Chains clips sequentially:
- Walk clip -> Turn clip -> Walk clip
- Auto-blend transitions between clips

## Skinning (Mesh Deformation)

### bonedeform SOP
Deforms mesh using skeleton animation:
```
rest_mesh + animated_skeleton -> bonedeform -> deformed_mesh
```

| Input | Description |
|-------|-------------|
| Input 1 | Rest pose mesh with capture weights |
| Input 2 | Rest pose skeleton |
| Input 3 | Animated skeleton |

### bonecapture SOP
Creates skin weights (capture attributes) on mesh:
- `method`: Biharmonic (best quality) or Proximity (fastest)
- Generates `@boneCapture` attribute (float array per point)

### Skinning Workflow
```
mesh -> bonecapture(skeleton) -> cache -> bonedeform(rest_skeleton, animated_skeleton) -> null
```
1. Import mesh and skeleton at rest pose
2. `bonecapture`: Compute skin weights
3. Paint weights if needed (bonecapturepainter)
4. `bonedeform`: Apply animation to mesh

## Procedural Rigging in VEX

KineFX skeletons are just points, so VEX works directly:

```vex
// Read joint transform
matrix m = point(0, "transform", @ptnum);

// Rotate a joint 45 degrees around Y
matrix rot = ident();
rotate(rot, radians(45), {0,1,0});
m *= rot;

// Write back
4@transform = m;
```

```vex
// Add twist to spine based on hip rotation
int hip_pt = nametopoint(0, "hip");
matrix hip_xform = point(0, "transform", hip_pt);
vector hip_rot = cracktransform(0, 0, 1, {0,0,0}, hip_xform);
float twist = hip_rot.y * 0.3;  // 30% of hip rotation
matrix spine_rot = ident();
rotate(spine_rot, radians(twist), {0,1,0});
4@transform = point(0, "transform", @ptnum) * spine_rot;
```

## Import/Export

### FBX
- Import: `kinefx_fbximport` or `file` SOP with FBX
- Export: `kinefx_fbxcharacterexport` ROP

### USD
- Skeleton auto-imports as KineFX via `sopimport` LOP
- Use `UsdSkel` schema for proper skeleton representation
- Blendshapes via `UsdSkelBlendShape`

### BVH (Motion Capture)
- Import: `agent_bvhimport` SOP
- Common for mocap data

## Performance Tips

- KineFX is SOP-based so it benefits from compiled SOPs
- Cache skinning weights (`bonecapture` is expensive)
- Use LOD skeletons: full skeleton for hero, reduced for background
- Motion clips are faster than re-evaluating animation per frame
- For crowds: KineFX feeds into the Agent system for crowd simulation

## Common KineFX Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Mesh doesn't deform | Missing capture weights | Run `bonecapture` on rest pose mesh |
| Joints flip during animation | Gimbal lock or IK instability | Increase IK damping, check rotation order |
| Retarget produces wrong poses | Joint mapping incorrect | Check `mappoints` mapping, verify rest poses match |
| Skeleton not visible | Missing display flag or wrong context | Set display flag, check SOP context |
| Skin weights bleed | Capture radius too large | Lower capture radius, paint weights manually |
| FBX import has wrong scale | Unit mismatch (cm vs m) | Scale skeleton by 0.01 if source is in cm |
| Motion clip pops at transition | No blend between clips | Add crossfade in `motionclipblend` |
