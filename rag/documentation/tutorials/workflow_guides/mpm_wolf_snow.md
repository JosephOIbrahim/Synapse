---
title: "MPM Wolf Snow"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "wolf", "snow", "character_interaction", "deformation", "particles", "sleeping", "passive_particles", "boundary_particles", "camera_frustum", "terrain", "stiffness_noise", "vdb_rasterization", "mask_by_surface", "density_volume", "secondary_debris", "mpm_debris", "fur_simulation", "collider"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_car_rain.md"
    reason: "Previous in series: MPM Car Rain"
  - path: "tutorials/workflow_guides/mpm_creature_breach.md"
    reason: "Next in series: MPM Creature Breach"
common_queries:
  - "How to simulate snow interaction with animated characters in MPM"
  - "How to use the sleeping mechanism for mostly passive MPM scenes"
  - "How to optimize snow volume by clipping to camera frustum"
  - "How to blend dynamic MPM snow with static snow at render time"
  - "How to use mask by surface for snow density rasterization"
  - "How to set up stiffness noise for natural snow fracture"
  - "How to reduce simulation volume using depth-based projection"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=JUcON39F7zE"
  series: "SideFX MPM H21 Masterclass"
  part: 14
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Wolf Snow

**Source:** [SideFX MPM H21 Masterclass - Part 14](https://www.youtube.com/watch?v=JUcON39F7zE)
**Presenter:** Alex Wevinger

## Overview

This demo covers three wolves running through a snow terrain, combining animated character colliders (with Vellum fur) against an MPM snow simulation optimized through camera frustum culling, depth-based volume reduction, and the sleeping mechanism. The pipeline includes terrain preparation, dynamic/static snow splitting, secondary debris emission, and volume rendering with the mask-by-surface technique to preserve structural detail in the density rasterization.

## Key Concepts

### Camera-Frustum Volume Optimization
The wolves' trajectories are trailed and clipped to the camera frustum, then baked into a VDB with dilation and smoothing. This defines the minimum simulation region. The snow terrain is built only around this region, and points outside the camera view can be killed during simulation for additional savings.

### Depth-Based Volume Reduction
Even within the clipped region, the full snow depth is not needed everywhere. Where wolf paws penetrate deeply, the volume extends to accommodate displacement. At shallower depths near the surface, the snow volume is lerped back toward a projection onto the wolf trajectories, reducing the total simulation volume while keeping enough material for natural-looking displacement in every area.

### Sleeping Mechanism for Passive Snow
Since most snow remains undisturbed, the sleeping mechanism aggressively deactivates particles. The velocity threshold is increased above default so points are deactivated more quickly. The detail attribute `state` provides runtime statistics (active/passive/boundary percentages) -- at peak activity, 98% of particles remain passive. This attribute can be linked to a Font SOP for on-screen debug stats during flipbook.

### Stiffness Noise for Natural Fracture
The snow preset stiffness is slightly increased to produce larger cohesive chunks, then multiplied by a noise pattern remapped to a range of [2, 5]. This variation creates natural-looking fracture boundaries where weaker regions break apart while stronger patches hold together as the wolves' paws displace the snow.

### Mask by Surface for Density Rasterization
When rasterizing MPM snow particles to a density volume, the raw result appears fuzzy and lacks structural definition. Enabling "mask by surface" multiplies the density grid by an SDF representation of the meshed snow surface. This preserves the low and mid-frequency structural shapes while retaining high-frequency granular detail, giving a much more convincing snow appearance at render time.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Solver | Snow simulation with sleeping | snow preset, stiffness slightly increased, velocity threshold raised, sleeping enabled |
| MPM Source | Fill snow terrain with points | particle separation from container |
| MPM Debris | Emit secondary snow particles | Jp emission multiplied by 5, slow-particle emission multiplied by 2, point replicate reduced to 3 |
| MPM Surface | Mesh and rasterize snow | VDB from Particles, dilation/erosion kept small for granular look, mask by surface toggle |
| Vellum Solver | Fur simulation on wolves | pre-cached before main setup |
| VDB Rasterize | Convert particles to density volume | density multiplier dialed at render time in LOPs |
| POP Solver | Secondary debris simulation | same setup as other shots, packing-based air resistance |
| Trail SOP | Capture wolf paw trajectories | bake first 100 frames for path extraction |

## Workflow Steps

1. **Prepare wolf assets** -- Smooth animation, run Vellum fur sim, cache results. Duplicate wolf body for three instances.
2. **Build colliders** -- Body + rasterized fur VDB as deforming collider (moderate friction, low stickiness). Static snow terrain as static collider (high stickiness for wet snow adhesion).
3. **Define simulation region** -- Trail wolf paths, clip to camera frustum, bake to VDB with dilation. Build terrain bounding box with snow thickness and surface detail (wind-shaped patches).
4. **Optimize volume** -- Project terrain depth toward wolf trajectories using a lerp: deeper areas stay close to paw paths, surface areas retain original shape. Apply dilation for safety margin.
5. **Split dynamic and static snow** -- Dynamic region fills with MPM points. Static region extends to cover full camera view with a hole cut for the dynamic zone. Add fine surface detail to static mesh edges to match MPM particle bumpiness at the seam.
6. **Configure MPM material** -- Snow preset with increased stiffness, noise-modulated stiffness (remapped [2,5]), sleeping enabled with raised velocity threshold.
7. **Run simulation** -- Monitor active/passive/boundary ratios via the state detail attribute.
8. **Mesh dynamic snow** -- VDB from Particles with small dilation and erosion to preserve granularity. Balance smooth patches with high-frequency detail.
9. **Emit and simulate debris** -- MPM Debris with adjusted emission thresholds and reduced point replication. POP solver for secondary trajectories.
10. **Rasterize to density volumes** -- Convert both primary and secondary particles to density grids. Enable mask by surface on primary to restore structural definition. Merge density volumes and adjust multiplier at render time in Karma.

## Tips & Insights

- For mostly-passive scenes, the sleeping mechanism is essential. Raising the velocity threshold beyond default provides significant performance gains with minimal visual impact.
- The detail attribute `state` is a string on the simulation output giving active/passive/boundary percentages. Pipe it to a Font SOP for live debug feedback.
- Keep dilation and erosion small when meshing snow to maintain the granular look. Over-smoothing destroys the natural snow texture.
- The mask-by-surface toggle on MPM Surface is critical for snow: without it, rasterized density is uniformly fuzzy. With it, the SDF structure gives readable low/mid/high frequency detail.
- Add matching fine detail noise to the static snow edges where they meet the dynamic region so the seam is invisible at render time.
- The density multiplier for secondary particles is best dialed interactively in LOPs during test renders rather than set procedurally.
- Trees with snow on branches are optional scene dressing handled entirely in LOPs and TOPs; they can be disabled to save bake time.

## Assets

| Asset | Path | Format |
|-------|------|--------|
| Wolf (slow animation) | `wolf/wolf_slow.fbx` | FBX |
| Wolf (normal speed) | `wolf/wolf.fbx` | FBX |
| Wolf fur guides | `wolf/geo/guides.bgeo.sc` | BGEO |
| ML Groom Deformer | `wolf/ML_Groom_Deformer.hip` | HIP |
| Spruce Trees Pack | `trees/` | External ([Mantissa](https://ftp.mantissa.xyz/resources/trees/mantissa_spruce_trees_pack.zip)) |
| Fir Trees Pack | `trees/` | External ([Mantissa](https://ftp.mantissa.xyz/resources/fir_free/mantissa.xyz_free_firs.zip)) |

*Asset root: `D:/HOUDINI_PROJECTS_2025/MPM_MASTERCLASS_FILES/`*

---
*Full transcript: [14_wolf_snow.md](../../_raw_documentation/mpm_masterclass/14_wolf_snow.md)*
