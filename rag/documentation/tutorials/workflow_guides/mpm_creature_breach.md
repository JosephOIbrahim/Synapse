---
title: "MPM Creature Breach"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "creature", "breach", "terrain", "soil", "character_fx", "animated_collider", "multi_resolution", "stickiness", "secondary_debris", "point_deform", "orient_retarget", "narrow_band", "brute_character", "production_pipeline"]
common_queries:
  - "How to simulate a creature breaking through terrain with MPM"
  - "Multi-resolution MPM simulation workflow"
  - "How to use low-res MPM sim as collider for high-res sim"
  - "Animated deforming collider with MPM"
  - "Narrow-band point cloud for render efficiency"
  - "MPM soil stickiness on animated characters"
  - "Retarget MPM dynamics onto high-resolution point cloud"
  - "Enforce maximum velocity on animated characters for MPM"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=Y16j3XTaX-Q"
  series: "SideFX MPM H21 Masterclass"
  part: 15
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Creature Breach

**Source:** [SideFX MPM H21 Masterclass - Part 15](https://www.youtube.com/watch?v=Y16j3XTaX-Q)
**Presenter:** Alex Wevinger

## Overview

This production demo shows a creature ("Brute," shipped with H21) breaching through terrain, simulated entirely with the MPM solver. The key innovation is a multi-resolution pipeline: a coarse MPM pass identifies where fracturing occurs, then a high-resolution pass concentrates particles only in those regions. An ultra-high-res narrow-band point cloud is retargeted from the simulation data for final rendering, achieving near-billion-point detail without filling the entire volume.

## Key Concepts

### Multi-Resolution MPM Pipeline
The core strategy runs two sequential MPM simulations. The first pass uses coarse particle separation (0.11) to quickly identify fracture regions via the Jp (determinant of deformation gradient) attribute. Points that never fracture are converted into static colliders. The second pass runs at nearly double the resolution (0.06) -- roughly 8x the particle count in 3D -- but only fills the dynamic patch where fracturing actually occurs. This concentrates computational resources exactly where detail is needed.

### Enforce Maximum Velocity on Animated Characters
A VEX wrangle enforces a maximum displacement of 0.25 units per frame on the animated character. For each point, the delta between current and previous frame positions is computed. If displacement exceeds the threshold, it is clamped to 0.25 multiplied by the displacement direction. This prevents MPM material from exploding when the animation moves too fast.

### Low-Res Sim as Animated Deforming Collider
The low-resolution MPM simulation doubles as an animated deforming collider for the high-resolution pass. Friction and stickiness are set to very high values so that high-resolution particles feel fully connected to the low-res pieces, hiding the resolution mismatch at render time.

### Narrow-Band Render Point Cloud
For the final renderable geometry, the dynamic terrain patch is filled at even higher resolution (0.04 particle separation). The interior is then pruned, keeping only a narrow band of particles on exterior surfaces and crack interiors. This reduces 166 million points down to approximately 88 million while preserving all visible detail. At full resolution, this approach would yield roughly 1 billion points for the entire volume -- the narrow-band optimization makes it tractable.

### Orient-Based Retargeting
Each MPM particle carries an orient attribute from the solver. High-resolution render points are captured to their nearest MPM particle at rest, with noise added to break up Voronoi-diagram artifacts. At each frame, rest-position points are transformed by converting the orient quaternion to a 3x3 matrix and multiplying, then translated back into animated space.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Source (terrain) | Generate soil particles from dynamic terrain patch | Preset: Soil, stiffness multiplied by 160 |
| MPM Source (high-res) | Second-pass source at higher resolution | Particle separation: 0.06 |
| MPM Solver (low-res) | Coarse simulation to detect fracture regions | Default settings, particle separation: 0.11 |
| MPM Solver (high-res) | Detailed simulation of fracture zone | Default settings, high friction/stickiness on colliders |
| MPM Debris Source | Emit secondary debris from stretching/speed | Min Jp and min speed animated over time to throttle emission |
| Attribute Wrangle (velocity clamp) | Enforce max displacement per frame | Threshold: 0.25 units/frame |
| Point Deform | Transfer animation to high-res character mesh | Standard point deform from low-res to high-res |

## Workflow Steps

1. **Build Terrain** -- Create ground from a grid with noise, add mountain asset for the breach point, scatter rock assets.
2. **Prepare Animated Character** -- Import Brute animation (Alembic), retarget to high-res mesh, enforce max velocity (0.25 units/frame) via wrangle.
3. **Generate Motion Mask** -- Sample character positions across the frame range to build an SDF stencil isolating the dynamic terrain patch.
4. **Run Low-Res MPM Sim** -- Simulate terrain with soil preset at coarse resolution (0.11). Character acts as animated deforming collider with stickiness enabled.
5. **Analyze Jp Attribute** -- Gather maximum Jp across all frames. Blast points that never fracture and convert them to static colliders.
6. **Run High-Res MPM Sim** -- Fill only the dynamic patch at 0.06 resolution. Use low-res sim pieces as animated deforming colliders with maximum friction and stickiness.
7. **Build Narrow-Band Render Cloud** -- Fill terrain at 0.04 resolution, erode inward (1 dilation, 1 smooth, 4 erosion), prune interior points. Store rest attribute for shading.
8. **Retarget Dynamics** -- Capture render points to nearest MPM particle (with noise offset). Transform via orient quaternion to 3x3 matrix each frame.
9. **Secondary Debris** -- Combine both MPM sims as colliders. Emit debris from Jp and speed thresholds, animate emission limits to prevent runaway particle counts. Drive wind/air resistance by point density.

## Tips & Insights

- The multi-resolution pipeline is essential for production scale: filling the entire volume at 0.06 separation would be impractical on a standard GPU, but targeting only fracture regions keeps it manageable.
- Adding noise to the nearest-particle capture breaks the clean Voronoi cell boundaries and produces more organic fracture lines.
- Animating the debris emission thresholds (minimum Jp and minimum speed) over time prevents particle counts from exploding as the simulation progresses.
- The narrow-band approach (exterior surfaces + crack interiors only) can reduce point counts by 50% or more with no visible quality loss at render time.
- The velocity clamping wrangle is a simple but critical safeguard -- fast animation limbs will otherwise scatter MPM material in all directions.

## Assets

| Asset | Path | Format |
|-------|------|--------|
| Brute Creature Model | `broot/broot_modelMain.abc` | Alembic |
| Brute Creature Rig v1 | `broot/rigMain.bgeo.sc` | BGEO |
| Brute Creature Rig v2 | `broot/rigMain_v02.bgeo.sc` | BGEO |
| Brute USD Lookdev | `broot/lookdev/usd/assets/broot/broot.usd` | USD |

*Asset root: `D:/HOUDINI_PROJECTS_2025/MPM_MASTERCLASS_FILES/`*

---
*Full transcript: [15_creature_breach.md](../../_raw_documentation/mpm_masterclass/15_creature_breach.md)*
