---
title: "MPM Building Attack"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "building", "attack", "destruction", "large_scale", "fracture", "collapse", "projectile", "continuous_emission", "watertight", "internal_structure", "assume_unchanging_material", "substeps", "backtrack_velocity", "consistent_point_count", "filler_points", "debris_instancing", "wind_density", "production_pipeline", "concrete"]
common_queries:
  - "How to destroy a building with MPM projectiles"
  - "Preparing non-watertight models for MPM destruction"
  - "Continuous emission of MPM projectiles mid-simulation"
  - "Assume unchanging material properties checkbox explained"
  - "How to maintain consistent point count with emitted MPM particles"
  - "Backtracking projectile positions using velocity"
  - "Adding internal structural pillars for building destruction"
  - "Filler points and max distance in MPM Post Structure"
  - "Wind resistance driven by point density for debris"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=beyRxMYzwsk"
  series: "SideFX MPM H21 Masterclass"
  part: 17
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Building Attack

**Source:** [SideFX MPM H21 Masterclass - Part 17](https://www.youtube.com/watch?v=beyRxMYzwsk)
**Presenter:** Alex Wevinger

## Overview

This production demo simulates multiple projectiles striking a building, causing progressive structural collapse and debris emission. The setup covers the full pipeline from making a non-watertight architectural model destruction-ready, to continuous MPM projectile emission with staggered timing, to fracturing and retargeting both the building and individual projectiles. Special attention is given to the "assume unchanging material properties" optimization and how introducing new materials mid-simulation requires it to be disabled.

## Key Concepts

### Making Architectural Models Destruction-Ready
Most downloadable building models are not watertight -- only visible surfaces are modeled. The preparation pipeline fuses open edges, closes gaps with VDB operations to produce a volumetric representation with clear inside/outside boundaries, and adds internal structural pillars to prevent unrealistic self-collapse. UVs from the original asset are transferred onto the cleaned volume for proper lookdev at render time.

### Staggered Projectile Emission System
Projectile hit locations are defined by scattering points on the target face of the building. Each projectile is assigned a hit frame between frame 48 and approximately frame 144 (3x48). Positions are backtracked from the hit point using the desired impact velocity and accumulated gravity per frame, producing natural ballistic trajectories. A domain box detects when each projectile enters the simulation region; it is emitted as MPM particles (sphere copies) on that single entry frame via continuous emission.

### Assume Unchanging Material Properties
This solver optimization (enabled by default) tells the MPM solver that material stiffness and density remain constant, allowing it to skip per-frame re-evaluation. When projectiles with much higher stiffness and density are introduced mid-simulation, this assumption becomes invalid -- the solver cannot add substeps to accommodate the stiffer material and the simulation explodes. Unchecking this option forces the solver to re-evaluate material properties every frame and adjust substeps accordingly.

### Consistent Point Count for Emitted Particles
Since projectiles appear at different frames, the point count changes over time, breaking retargeting tools. The solution: start from the last emission frame (frame 110, when all projectiles exist) and solve backwards in time to find rest positions. Points that have not yet been emitted are held static at their pre-emission position. Two branches merge: one with the simulated trajectories, one with static pre-emission positions. As particles appear in the simulation branch, they disappear from the static branch, producing a smooth transition with constant total count.

### Vibration Damping in Early Frames
The building MPM simulation exhibits slight vibration between the first frame and the first impact. A linear interpolation between frame 1 and frame 35 (the last stable frame before impact) smooths out this artifact. Alternatively, freezing at frame 35 works but is less smooth.

### Max Distance for Filler Points
The max distance parameter in MPM Post Structure controls how far filler points extend from actual fracture points. Reducing it restricts filler points to areas immediately adjacent to fracture lines, keeping the model memory-efficient. This is especially important for large buildings where unfractured regions should remain lightweight.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| VDB from Polygons | Convert building to watertight volume | Standard VDB workflow for gap closing |
| MPM Source (building) | Generate particles from building volume | Preset: Concrete, stiffness 2x default, noise on stiffness for variation |
| MPM Source (projectiles) | Emit projectile particles on entry to domain | Continuous emission, stiffness very high, density increased |
| MPM Solver | Simulate building destruction | Assume unchanging material properties: OFF, visualization and attribute output customized |
| MPM Post Structure | Detect fracture pieces from Jp attribute | Fuse distance increased, min stretching increased, align fracture to stretch (optional for concrete), max distance tuned for filler point spread |
| MPM Deformed Pieces | Retarget dynamics to original geometry | Default settings, per-projectile fracture namespace with loop iteration suffix |
| MPM Debris Source | Emit secondary debris | Min Jp and min speed thresholds increased to limit emission, replication reduced |

## Workflow Steps

1. **Prepare Building Model** -- Fuse edges, close gaps via VDB, add internal pillars for structural integrity. Transfer UVs from original to cleaned model.
2. **Configure Building MPM Source** -- Use concrete preset with 2x stiffness. Add noise to stiffness attribute for variation in fracture behavior.
3. **Set Up Projectile System** -- Scatter hit points on building face, assign staggered hit frames (48-144). Backtrack positions using impact velocity and gravity. Detect domain-box entry for single-frame emission as MPM spheres.
4. **Configure Solver** -- Uncheck "assume unchanging material properties" since projectiles introduce stiffer, denser material mid-simulation. Leave other settings at default.
5. **Run MPM Simulation** -- Projectiles strike the building progressively, causing localized fracture and structural collapse.
6. **Damp Early Vibration** -- Lerp building points between frame 1 and frame 35 to remove pre-impact vibration artifacts.
7. **Fix Projectile Point Count** -- Solve backwards from frame 110 to find pre-emission rest positions. Merge static and animated branches for constant total count. Backtrack pre-emission positions linearly using emission velocity.
8. **Fracture Projectiles** -- Loop over each projectile individually. Fracture with MPM Post Structure, using unique namespace per iteration to avoid name clashes. Retarget with MPM Deformed Pieces.
9. **Fracture Building** -- Run MPM Post Structure with increased fuse distance and min stretching. Tune max distance to keep filler points near fracture lines. Add interior detail geometry. Retarget to original UV-mapped building.
10. **Secondary Debris** -- Emit from Jp and speed thresholds with reduced replication. Vary pScale for randomness. Assign debris index for Solaris instancing. Sample building textures via UV attribute for colored debris.
11. **Debris Dynamics** -- Compute point density to drive wind/air resistance (dense clumps ignore wind, isolated particles catch it). Apply perimeter-based rolling rotation identical to the train wreck setup.

## Tips & Insights

- Always make architectural models watertight before MPM destruction -- VDB operations are the most reliable approach for closing gaps in downloaded models.
- Add internal structural geometry (pillars, floors) to prevent buildings from collapsing under their own weight before any impacts occur.
- Uncheck "assume unchanging material properties" whenever you introduce new materials mid-simulation with different stiffness or density -- this is the most common cause of simulation explosions with continuous emission.
- The backwards-solve trick for consistent point counts is reusable in any setup with staggered MPM emission: start from the frame when all particles exist and extrapolate backwards.
- The fracture namespace with loop iteration suffix is critical when fracturing multiple objects in a for-each loop -- without unique names, retargeting produces incorrect piece assignments.
- Filler point max distance is a key memory optimization for large structures: keep filler points concentrated near fracture lines rather than spread across the entire model.
- Point-density-driven wind resistance is the standard secondary debris technique across all masterclass scenes: densely packed debris behaves like solid chunks while isolated particles drift realistically.

## Assets

| Asset | Path | Format |
|-------|------|--------|
| KitBash3D Atlantis Temple of Triton | `buildings/` | External ([KitBash3D](https://kitbash3d.com/products/atlantis/temple-of-triton)) |

*Asset root: `D:/HOUDINI_PROJECTS_2025/MPM_MASTERCLASS_FILES/`*

---
*Full transcript: [17_building_attack.md](../../_raw_documentation/mpm_masterclass/17_building_attack.md)*
