---
title: "MPM Pumpkin Smash"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "pumpkin", "smash", "destruction", "organic", "fracture", "debris", "slow_motion", "time_scale", "multi_material", "meshing", "mpm_surface", "mpm_deform_pieces", "mpm_debris", "secondary_simulation", "uv_transfer", "depth_attribute", "mask_smooth"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_paintball_impact.md"
    reason: "Previous in series: MPM Paintball Impact"
  - path: "tutorials/workflow_guides/mpm_car_rain.md"
    reason: "Next in series: MPM Car Rain"
common_queries:
  - "How to set up a multi-material organic destruction in MPM"
  - "How to handle slow motion velocity in MPM simulations"
  - "How to mesh MPM particles with UV transfer from rest geometry"
  - "How to use MPM Deform Pieces for rigid embedded objects"
  - "How to emit debris from MPM simulations"
  - "How to protect detail with mask smooth on MPM Surface"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=OVQAAlh-3s8"
  series: "SideFX MPM H21 Masterclass"
  part: 12
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Pumpkin Smash

**Source:** [SideFX MPM H21 Masterclass - Part 12](https://www.youtube.com/watch?v=OVQAAlh-3s8)
**Presenter:** Alex Wevinger

## Overview

This demo shows a slow-motion pumpkin destruction using multi-layered organic materials (skin, flesh, seeds) hit by an animated hammer collider. The pumpkin is split into three material layers with distinct MPM material presets, each tuned independently. Key techniques include point-fusing to reduce particle counts, time-scale management for slow-motion velocity vectors, debris emission with MPM Debris, and post-simulation meshing using MPM Surface with UV transfer and depth-based mask smoothing.

## Key Concepts

### Multi-Material Layered Source Setup
The pumpkin geometry is split into three distinct components: an outer skin with thickness, internal flesh modeled with fibers running from skin to core, and scattered seed instances oriented toward the center. Each component receives its own MPM material configuration. The seeds use a rubber-like preset, while both skin and flesh start from the snow preset with custom iteration. The skin has compression hardening enabled; the flesh does not. Point counts are managed by fusing overlapping particles (40M down to 9M) and pruning flesh points that overlap with seeds.

### Decoupled Point Sourcing
MPM attributes can be configured on one point set and transferred to a different set for simulation. This allows you to define the material on the MPM Source output but actually simulate a fused, optimized point cloud. Transfer the MPM attributes (stiffness, material type) onto your custom points rather than using the source node output directly.

### Slow-Motion Time Scale Management
The hammer is animated at real-time speed, then the MPM solver applies a time scale for slow motion. Velocity vectors must be adjusted at multiple pipeline stages: multiply by the time scale for rendering (so motion blur reflects actual on-screen movement), and divide by the time scale when feeding into debris emission (so secondary simulations receive real-time velocity magnitudes for correct physical behavior).

### Post-Simulation Meshing with MPM Surface
The MPM Surface node handles meshing with built-in UV transfer from a rest model (piped into the third input) and attribute transfer from particles (depth, Cd). Mask Smooth protects high-detail areas: the Jp attribute masks tearing/stretching regions, and curvature masking preserves sharp features. Both prevent smoothing from destroying important fracture detail. Adaptivity is increased (10x) on flesh to reduce polygon count for GPU rendering with Karma XPU.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Source | Generate simulation points from geometry | particle separation (drives point count) |
| MPM Solver | Run the MPM simulation | material condition: 7, time scale (from scene), substeps ramped |
| MPM Debris | Emit secondary particles from sim | minimum speed (increased), point replicate (reduced), keep 10% |
| MPM Surface | Mesh particles to polygons with attribute transfer | mask smooth (Jp + curvature), adaptivity 10x, UV from rest input 3 |
| MPM Deform Pieces | Drive rigid pieces by MPM points | used standalone for seed instances (not with MPM Post Structure) |
| VDB from Particles | Convert particles to volume for seeds | basic settings with a couple of filters |
| POP Solver | Secondary debris simulation | air resistance modulated by packing density, collision handling |
| Clamp to First Frame | Hold data before sim start | ensures pumpkin is visible before frame 32 |

## Workflow Steps

1. **Model pumpkin layers** -- Split geometry into skin (with thickness), flesh (with fibers toward core), and seed instances scattered and oriented toward center.
2. **Optimize point cloud** -- Fuse overlapping points on flesh (40M to 9M), prune flesh/seed overlaps, delete remaining overlaps across all layers (14M to 12M).
3. **Configure materials** -- Assign MPM material presets per layer. Transfer MPM attributes from the material configuration points to the optimized simulation points.
4. **Set up collider** -- Animate the hammer at real-time speed with proper impact velocity. Time scale is applied at the solver level.
5. **Run MPM simulation** -- Material condition at 7 for aggressive substeps. Domain walls delete escaping points. Simulation starts at frame 32; use Clamp to First Frame for pre-impact visibility.
6. **Adjust velocity for render** -- Multiply velocity by time scale so motion blur matches slow-motion playback speed.
7. **Emit debris** -- Feed MPM Debris with real-time velocity (divide by time scale). Reduce emission rate and keep only 10% of generated points.
8. **Simulate secondaries** -- POP solver for spray/debris with packing-based air resistance and collision handling.
9. **Mesh the simulation** -- Split output by component. Skin: compute depth attribute for dual-color shading, transfer UVs from rest model via third input, use mask smooth (Jp + curvature). Flesh: increase adaptivity to reduce polygon count. Seeds: use MPM Deform Pieces to rigidly transform seed instances, bake to poly soup.

## Tips & Insights

- You do not need to simulate the points that come directly out of MPM Source. Configure materials on one set, then transfer attributes to an optimized point cloud for simulation.
- Start the simulation at a later frame (here frame 32) and use Clamp to First Frame so the object remains visible in earlier frames.
- Stiffness was globally increased as a late-stage tweak after iterating on the look -- there is no magic recipe, just iterate until the fracture behavior looks right.
- The MPM Surface post-simulation nodes in Houdini 21 are significantly more compact than the previous masterclass. Most technology is now embedded in the post-sim nodes.
- When meshing for Karma XPU, increase adaptivity aggressively to fit within GPU memory (28M polygons for flesh even at 10x adaptivity).
- For slow-motion shots, always track which pipeline stage needs real-time velocity vs. scaled velocity. Rendering needs scaled; debris emission needs real-time.

---
*Full transcript: [12_pumpkin_smash.md](../../_raw_documentation/mpm_masterclass/12_pumpkin_smash.md)*
