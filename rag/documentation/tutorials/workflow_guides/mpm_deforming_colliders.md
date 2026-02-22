---
title: "MPM Deforming Colliders"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "deforming_colliders", "collision", "animated_geometry", "velocity_expansion", "substep_interpolation"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_friction_stickiness.md"
    reason: "Previous in series: MPM Friction and Stickiness"
  - path: "tutorials/workflow_guides/mpm_mpmsurface.md"
    reason: "Next in series: MPM Surface Meshing"
common_queries:
  - "How to use deforming colliders in MPM?"
  - "MPM material sticking to fast-moving colliders"
  - "MPM expand to cover velocity"
  - "MPM substep interpolation for colliders"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=RylqkW5ePww"
  series: "SideFX MPM H21 Masterclass"
  part: 5
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Deforming Colliders

**Source:** [SideFX MPM H21 Masterclass - Part 5](https://www.youtube.com/watch?v=RylqkW5ePww)
**Presenter:** Alex Wevinger

## Overview

Houdini 21 significantly improves deforming collider support in MPM. The key addition is the "Expand to Cover Velocity" option on the MPM Collider, which dilates the VDB activation region based on the collider's velocity. This solves the fundamental problem of substep interpolation on fast-moving geometry, enabling material to properly stick to rapidly animated colliders like a swinging hammer.

## Key Concepts

### The Substep Interpolation Problem

MPM runs with many substeps (often 200+), so collider data is frequently sampled between integer frames. Without velocity expansion, the collider VDB is tightly bounded around the mesh at each integer frame. When sampling at substep 0.5 between frames 0 and 1:

- The sample point may fall outside the VDB bounds of both frame 0 and frame 1
- SDF (signed distance field) lookups return garbage data
- Velocity lookups return garbage data
- Interpolation between the two frames produces incorrect results
- Material cannot stick to the collider because the solver doesn't know where the collider is between frames

### How Velocity Expansion Fixes It

The "Expand to Cover Velocity" checkbox dilates the VDB activation region based on the collider's per-frame velocity. This ensures that:

1. The bounding box extends far enough to cover where the collider will be at any substep
2. Both SDF and velocity fields contain valid data at all substep sample positions
3. Interpolation between frames produces correct collision information
4. Material can properly stick to and travel with fast-moving deforming geometry

### Before vs After (Crag + Hammer Demo)

**Without velocity expansion**: Snow sticks to the hammer initially during slow motion, but detaches completely during the fast swing phase. All material falls off.

**With velocity expansion**: Snow sticks throughout the entire animation including the fast swing. Material trails behind on the ground, and some remains attached even after the hammer reaches its final pose.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Collider | Deforming collision geometry | Type: Deforming, **Expand to Cover Velocity** (checkbox, enabled by default in H21) |
| MPM Source | Source material | Preset (Snow), Friction (100), Stickiness (100) |
| MPM Configure | Setup | Particle Separation |
| MPM Solver | Simulation | — |

## Workflow Steps

1. **Set collider type to Deforming** — On MPM Collider, set the type to Deforming (not Static or Animated Rigid)
2. **Enable Expand to Cover Velocity** — This is on by default in H21. If upgrading from 20.5, make sure it's checked.
3. **Set high friction and stickiness** — Use values of 100 or higher on both to maximize material adhesion
4. **Run simulation** — Material should now stick to the collider through fast-moving sections

## Tips & Insights

- "Expand to Cover Velocity" is the default in H21. If you're debugging old scenes from H20.5 that don't stick properly, check this checkbox first.
- Even simple cases (a sphere pressing into a box and lifting back up) used to fail with deforming colliders in H20.5. This is now fixed.
- The VDB bounding box is visibly larger with velocity expansion enabled — this is expected and correct. The expanded region contains valid SDF and velocity data for substep interpolation.
- Use maximum friction and stickiness (100+) for sticky material effects. The high values are needed because MPM substep interpolation can smooth out adhesion forces.
- The improvement is most visible on fast-moving geometry. Slow-moving colliders may show little difference between old and new behavior.

---
*Full transcript: [05_deforming_colliders.md](../../_raw_documentation/mpm_masterclass/05_deforming_colliders.md)*
