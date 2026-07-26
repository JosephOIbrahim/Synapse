---
title: "MPM Surface Tension"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "surface_tension", "fluid_sim", "droplets", "mpm_solver", "viscosity", "multiphase", "grid_based", "point_based"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_overview.md"
    reason: "Previous in series: MPM H21 Masterclass Overview"
  - path: "tutorials/workflow_guides/mpm_auto_sleep.md"
    reason: "Next in series: MPM Auto Sleep"
  - path: "tutorials/workflow_guides/mpm_friction_stickiness.md"
    reason: "Related: friction and stickiness interact with surface tension"
common_queries:
  - "How does surface tension work in MPM?"
  - "MPM surface tension tutorial"
  - "MPM point-based vs grid-based surface tension"
  - "MPM multiphase surface tension setup"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=HAv1t7q7VRk"
  series: "SideFX MPM H21 Masterclass"
  part: 1
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Surface Tension

**Source:** [SideFX MPM H21 Masterclass - Part 1](https://www.youtube.com/watch?v=HAv1t7q7VRk)
**Presenter:** Alex Wevinger

## Overview

Houdini 21 adds surface tension to the MPM solver with two implementations: point-based (stable, higher VRAM) and grid-based (faster, slightly less stable). This video demonstrates both methods, covers multiphase surface tension for mixing materials, and shows how friction/stickiness interact with surface tension for effects like water droplets on leaves.

## Key Concepts

### Point-Based Surface Tension (Default)

The default method uses a point-based approach identical to the Vellum implementation. Each particle evaluates its neighbors to compute surface tension forces. This is the more stable and accurate method, but consumes more VRAM on GPU because every point must track all of its neighbors. The resolution of the surface tension effect scales directly with the point cloud resolution.

### Grid-Based Surface Tension

The alternative grid-based method is significantly faster but slightly less stable. It can produce occasional unmotivated velocity gains where blobs of fluid move in unexpected directions. Best suited for scenarios where perfect accuracy is not critical, such as drips and tendrils falling from objects emerging from water. For large-scale water interaction shots, the grid-based method offers a good speed-to-quality tradeoff.

### Multiphase Surface Tension

Multiple materials can have independent surface tension behavior using the phase system. Each MPM Source can define a surface tension strength and a phase ID (integer). Materials with different phase IDs will not attract each other. The MPM Solver's global surface tension strength acts as a multiplier on top of per-source values.

Note: Because all MPM materials share the same underlying grid, there will be some interpolation bleed — particles without surface tension can pick up slight motion from nearby particles that do have it, due to the particle-to-grid-to-particle transfer cycle.

### Collision Resolution for Thin Geometry

When colliders are thin (e.g., leaves), the default voxel resolution may not resolve them. Override the resolution directly on the MPM Collider node. Enable **Particle Level Collision** on the MPM Solver (Collision tab) with "Velocity Based Move Outside Collider" for water to flow on top of thin colliders instead of passing through.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Configure | Initialize MPM setup | Particle Separation |
| MPM Source | Define source geometry and material | Preset (Water), Surface Tension, Phase |
| MPM Collider | Collision geometry | Resolution override, Collision type |
| MPM Solver | Run simulation | Surface Tension (enable), Method (Point-based/Grid-based), Particle Level Collision, Friction, Stickiness |
| Color | Visualization of multiphase materials | — |

## Workflow Steps

1. **MPM Configure** — Start every MPM setup here; sets particle separation and domain
2. **Set up source and collider** — Connect source geometry to MPM Source (water preset), collision geometry to MPM Collider
3. **Resolve thin colliders** — Override resolution on MPM Collider; enable Particle Level Collision on MPM Solver > Collision tab
4. **Enable surface tension** — On MPM Solver, enable Surface Tension; choose point-based (stable) or grid-based (fast)
5. **Dial in strength** — Boost surface tension multiplier (e.g., 5x or higher) until droplets hold shape
6. **Increase friction/stickiness** — Use very high values to counteract surface tension pushing particles away from colliders; creates hanging droplet effects
7. **Multiphase setup** — Duplicate MPM Source, assign different phase IDs and surface tension values per material

## Tips & Insights

- Surface tension strength often needs to be 5x or higher to see visible droplet cohesion effects.
- Friction and stickiness values may need to be pushed very high when combined with surface tension, because surface tension forces cause particles to levitate slightly above the collider surface.
- The point-based method uses the same implementation as Vellum surface tension, so behavior should be familiar.
- Grid-based method is much faster but can produce "unmotivated" velocity artifacts — acceptable for drip/tendril effects, not ideal for hero close-up shots.
- For multiphase setups, the MPM Solver's surface tension strength becomes a global multiplier on top of per-source values.
- Grid interpolation causes slight bleed between phases — particles without surface tension near particles with it will pick up some motion.

---
*Full transcript: [01_surface_tension.md](../../_raw_documentation/mpm_masterclass/01_surface_tension.md)*
