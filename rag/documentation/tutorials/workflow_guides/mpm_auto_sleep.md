---
title: "MPM Auto Sleep"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "auto_sleep", "optimization", "performance", "simulation", "rest_state", "boundary_particles", "staggered_activation"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_surface_tension.md"
    reason: "Previous in series: MPM Surface Tension"
  - path: "tutorials/workflow_guides/mpm_continuous_emission.md"
    reason: "Next in series: MPM Continuous Emission"
common_queries:
  - "How does auto sleep work in MPM?"
  - "MPM auto sleep performance optimization"
  - "MPM particle states active passive boundary"
  - "MPM staggered activation technique"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=MwSsXRof_7Y"
  series: "SideFX MPM H21 Masterclass"
  part: 2
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Auto Sleep

**Source:** [SideFX MPM H21 Masterclass - Part 2](https://www.youtube.com/watch?v=MwSsXRof_7Y)
**Presenter:** Alex Wevinger

## Overview

The auto sleep mechanism is a performance optimization that deactivates MPM particles below a velocity threshold, dramatically reducing simulation time in scenes where large portions of material are stationary. This video covers the three particle states (active, passive, boundary), the velocity threshold and delay parameters, and a creative use case: staggered activation where material starts passive and activates on contact.

## Key Concepts

### Three Particle States

MPM auto sleep introduces three states tracked by a `state` point attribute:

| State | Value | Behavior |
|-------|-------|----------|
| **Active** | 1 | Fully simulated — velocity, deformation gradient, and position all updated |
| **Passive/Inactive** | 0 | Frozen in space — not updated, not simulated |
| **Boundary** | 2 | Hybrid — attributes (deformation gradient, velocity) are updated but particles are never moved in space. Provides correct boundary conditions at the active/passive interface |

The boundary state is critical because MPM uses a dual particle-grid representation. Without boundary particles, the transition between active and passive regions would produce artifacts. Boundary particles maintain proper velocity and deformation data so that active particles near the boundary behave correctly.

### Velocity Threshold and Delay

Two parameters on the MPM Solver control sleep behavior:

- **Velocity Threshold** — Speed below which a particle is considered for deactivation. This is scene-scale dependent: small scenes can use small values, large scenes (e.g., 100+ meters) may need 10x the default.
- **Delay** — Time in seconds before a sub-threshold particle actually deactivates. At 24fps, a 0.5s delay means a particle must be below threshold for 12 consecutive frames before sleeping.

### Performance Characteristics

Auto sleep provides the most benefit when large portions of material are stationary for extended frame ranges. Example results from the demo scene (spaceship emerging from ground):

- Without auto sleep: ~1.7-1.8 FPS
- With auto sleep (during quiet periods): up to 13 FPS
- Overall speedup for full frame range: approximately 2x

**Important**: When most particles are active and moving, auto sleep adds overhead (state management, boundary updates) and can actually decrease performance. Only use it when you expect significant periods of particle inactivity.

### Staggered Activation Technique

Auto sleep can be used creatively to hold material in an unbalanced pose until an external force activates it. Example: a character model (Crag) stands in an unstable pose. Without auto sleep, the material collapses immediately under gravity. With auto sleep enabled and material starting as passive:

1. Material stays frozen in its initial pose
2. When a collider impacts (e.g., hits the knee), contact points activate
3. Thanks to MPM's many substeps (e.g., 226 substeps), the activation wave propagates through neighboring particles within a single frame
4. The entire model activates and reacts naturally to both gravity and the impact

This works because each substep activates a thin shell of new neighbors, and with hundreds of substeps, the wave reaches all particles within one displayed frame.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Solver | Simulation engine | Auto Sleep (enable), Velocity Threshold, Delay (seconds) |
| MPM Configure | Setup | Particle Separation (scale for large scenes: multiply by 10) |
| MPM Source | Source geometry | Material preset |
| MPM Collider | Collision geometry | Animated Rigid Collider type |

## Workflow Steps

1. **Set up MPM scene** — MPM Configure, Source, Collider as usual
2. **Enable Auto Sleep** — On the MPM Solver, toggle Auto Sleep on
3. **Adjust Velocity Threshold** — Scale proportionally to scene size (default works for small scenes; multiply by 10 for 100+ meter scenes)
4. **Set Delay** — Controls how quickly particles deactivate (0.5s = 12 frames at 24fps)
5. **Visualize state** — On MPM Solver, set "Color from Attribute" to visualize the state attribute (green=active, purple=passive, red=boundary)
6. **For staggered activation** — Start material as passive; the collision event naturally triggers the activation cascade through substeps

## Tips & Insights

- Auto sleep is most effective when large portions of material are inactive for long stretches. If everything is always moving, it adds overhead with no benefit.
- The boundary particle state is essential — it maintains correct deformation gradient and velocity data at the active/passive interface without moving the particles.
- For staggered activation, the high substep count in MPM (often 200+) is what allows the activation wave to propagate through the entire model within a single frame.
- Velocity threshold is scene-scale dependent. A 100-meter scene needs a threshold roughly 10x larger than a 1-meter scene.
- Visualizing the state attribute is essential for debugging — it shows exactly which particles are active, passive, or boundary at any given frame.
- The ~2x speedup observed in the demo is scene-specific. Actual gains depend on what fraction of particles are inactive and for how long.

---
*Full transcript: [02_auto_sleep.md](../../_raw_documentation/mpm_masterclass/02_auto_sleep.md)*
