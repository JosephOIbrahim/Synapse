---
title: "MPM H21 Masterclass Overview"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "overview", "houdini_21", "masterclass", "new_features", "mpm_solver"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_surface_tension.md"
    reason: "Next in series: MPM Surface Tension"
common_queries:
  - "What's new in MPM for Houdini 21?"
  - "MPM H21 masterclass overview"
  - "MPM post-simulation nodes overview"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=nD183jP3H4Y"
  series: "SideFX MPM H21 Masterclass"
  part: 0
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM H21 Masterclass Overview

**Source:** [SideFX MPM H21 Masterclass - Part 0](https://www.youtube.com/watch?v=nD183jP3H4Y)
**Presenter:** Alex Wevinger

## Overview

This masterclass by Alex Wevinger covers new MPM features and post-simulation workflow nodes introduced in Houdini 21. It is a follow-up to the Houdini 20.5 MPM masterclass and assumes prior knowledge of the MPM solver. The series is divided into two halves: new simulation features (Parts 1-5) and new post-simulation nodes with practical production demos (Parts 6-17).

## Key Concepts

### New Simulation Features (Parts 1-5)

- **Surface Tension** (Part 1) — Point-based and grid-based implementations for small-scale fluid effects like droplets on leaves.
- **Auto Sleep** (Part 2) — Performance optimization that deactivates particles below a velocity threshold, with three particle states: active, passive, and boundary.
- **Continuous Emission / Expansion** (Part 3) — Allows sourcing material on top of existing material to create internal pressure effects.
- **Per-Voxel Friction and Stickiness** (Part 4) — Spatial control over friction and stickiness on colliders without duplicating geometry (replacing the Houdini 20.5 workaround).
- **Improved Deforming Colliders** (Part 5) — Significantly improved handling of animated/deforming collision geometry.

### New Post-Simulation Nodes (Parts 6-9)

- **MPM Surface** (Part 6) — Streamlined surfacing/meshing of MPM particle data.
- **MPM Debris Source** (Part 7) — Emits debris particles based on where the material is fracturing.
- **MPM Post Fracture** (Part 8) — Takes the final state of an MPM simulation and fractures the original high-res asset to match.
- **MPM Deform Pieces** (Part 9) — Retargets MPM simulation dynamics onto the post-fractured asset, enabling RBD-like rigid body workflows using MPM for stiff materials (e.g., concrete).

### Practical Production Demos (Parts 10-17)

Parts 10-17 walk through real-world production setups (destruction workflows, paintball impacts, pumpkin smash, car rain, wolf in snow, creature breach, train wreck, building attack). These demonstrate how the new features and nodes combine in practical scenarios.

## Workflow Pattern

1. **MPM Configure** — Always the starting point for any MPM setup
2. **MPM Source** — Define source geometry and material presets (water, sand, snow, etc.)
3. **MPM Collider** — Set up collision geometry (static, animated rigid, or deforming)
4. **MPM Solver** — Run the simulation with new features (surface tension, auto sleep, etc.)
5. **Post-Sim Nodes** — MPM Surface, MPM Debris Source, MPM Post Fracture, MPM Deform Pieces

## Tips & Insights

- This is not an introduction to MPM; it assumes you already understand the solver at a high level.
- The HIP file with all 18 example scenes is provided for download, so you can follow along or study setups independently.
- MPM Post Fracture + MPM Deform Pieces work together to replicate RBD-like workflows: simulate stiff material with MPM, fracture the original asset to match, then retarget the dynamics.
- All production demo scenes (Parts 10-17) are not built from scratch in the videos; instead, the important parts of each setup are highlighted.

---
*Full transcript: [00_overview.md](../../_raw_documentation/mpm_masterclass/00_overview.md)*
