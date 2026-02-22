---
title: "MPM Train Wreck"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "train", "wreck", "destruction", "large_scale", "metal_tearing", "debris", "varying_friction", "friction_vdb", "surface_scatter", "close_gap", "instancing", "sparks", "debris_rotation", "angular_velocity", "retarget", "consistent_point_count", "filler_points", "production_pipeline"]
common_queries:
  - "How to simulate a train wreck with MPM metal tearing"
  - "MPM surface scatter mode vs volume mode"
  - "Varying friction with friction VDB in MPM"
  - "How to maintain consistent point count for MPM retargeting"
  - "Close gap feature for metal tearing"
  - "Debris instancing from MPM simulation"
  - "Angular velocity and rolling rotation for debris particles"
  - "Compression hardening for explosive fracture in MPM"
  - "How to fuse overlapping points in MPM source"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=fwAuygMxk2w"
  series: "SideFX MPM H21 Masterclass"
  part: 16
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Train Wreck

**Source:** [SideFX MPM H21 Masterclass - Part 16](https://www.youtube.com/watch?v=fwAuygMxk2w)
**Presenter:** Alex Wevinger

## Overview

This production demo simulates a train derailing and tearing apart as it tumbles across terrain. The setup demonstrates MPM metal destruction with varying friction grids, surface-mode particle scattering, and the close-gap feature for realistic metal tearing. A complete secondary pipeline produces instanced debris with physically-motivated rolling rotation, plus sparks split from the same particle simulation.

## Key Concepts

### Surface Scatter Mode for Thin Shells
Unlike typical volume-fill workflows, this setup uses the MPM Source in surface mode to scatter particles only on mesh surfaces. This is appropriate for the thin-walled train geometry. The relax option ensures even point distribution, and fuse overlapping points is enabled to eliminate redundant particles where panels overlap, saving computation without losing detail.

### Compression Hardening for Metal Fracture
The metal preset is augmented with additional compression hardening to promote tearing over bending. Without compression hardening, the metal tends to deform plastically without separating. Adding even a small amount encourages explosive breakage and clean tears when the train impacts the ground.

### Varying Friction via VDB Grid
A per-point friction attribute is authored on the collider geometry: 0.5 on the rails (low friction for sliding) and 1.25 on everything else (high friction for gripping). This attribute drives a friction VDB grid via the "friction create VDB from attribute" feature. The result: the train slides along the rails until it derails, then catches and tears on the high-friction ground and obstacles.

### Synthetic Colliders for Gripping
Boxes and angular shapes are added to the ground plane as synthetic colliders. These prevent the train from simply sliding across the terrain and instead force it to grip, roll, and tear as it tumbles. The ground plane friction is also increased in the solver settings.

### Consistent Point Count for Retargeting
The MPM container deletes particles that exit the bounding box, which causes a changing point count over time. The MPM Post Structure and MPM Deformed Pieces nodes require consistent point counts. The fix: loop through all frames and freeze deleted points in their last known position, ensuring the count remains constant (e.g., 144,639 throughout) while only the final render step prunes the frozen pieces.

### Close Gap for Metal Tearing
The close-gap toggle on the MPM Deformed Pieces node fills unnatural cracks between fractured metal panels. Without it, fracture boundaries show sharp geometric gaps that read as broken polygons rather than torn metal. Enabling close-gap produces significantly more convincing metal tear lines.

### Debris Rolling Rotation
Secondary debris particles receive physically-motivated rotation. A VEX wrangle computes an axis perpendicular to velocity (via cross product with an up vector), calculates how much of the particle's perimeter (2 * PI * radius) is traversed per frame, and converts that to angular velocity. A 0.25 multiplier damps the spin to prevent unrealistically fast rotation on airborne debris. The angular velocity is stored in a custom attribute (not `w`) to prevent the POP solver from overriding it.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Source (train) | Scatter particles on train surface | Preset: Metal, type: Surface, relax: on, fuse overlapping: on, compression hardening increased, stiffness multiplied up |
| MPM Source (track) | Generate collider from track and ground | Friction attribute: 0.5 (rails), 1.25 (ground/obstacles) |
| Friction VDB | Create varying friction grid from attribute | Driven by per-point friction attribute |
| MPM Solver | Simulate train destruction | Ground plane friction increased, all else default |
| MPM Post Structure | Detect fracture pieces from simulation | Align fracture to stretch points toggle (taste-dependent) |
| MPM Deformed Pieces | Retarget dynamics to original geometry | Close gap: enabled, velocity computed, consistent point count required |
| MPM Debris Source | Emit secondary debris particles | Minimum stretching reduced for more emission |
| Attribute Wrangle (rotation) | Compute rolling angular velocity for debris | Perimeter-based rotation, 0.25 damping multiplier |

## Workflow Steps

1. **Prepare Train Model** -- Combine exterior train asset with interior details (seats) for visible interiors when the train tears open.
2. **Build Track and Ground** -- Merge rail assets, add synthetic box colliders for gripping. Author friction attribute (0.5 on rails, 1.25 elsewhere) and generate friction VDB.
3. **Configure MPM Source** -- Use surface scatter mode with relaxation and fuse overlapping points. Apply metal preset with increased compression hardening and stiffness.
4. **Run MPM Simulation** -- Solver uses default settings with increased ground plane friction. Train slides on rails, derails, tumbles, and tears on high-friction ground.
5. **Fix Point Count** -- Loop through all frames, freeze deleted particles at their last position to maintain constant count for retargeting tools.
6. **Fracture and Retarget** -- Run MPM Post Structure (adjust filler points as needed), then MPM Deformed Pieces with close-gap enabled. Transfer deleted attribute and prune frozen pieces.
7. **Prepare Secondary Debris** -- Emit debris particles, split into sparks and debris streams. Prune early-frame particles and reduce density at specific frames for art direction.
8. **Compute Debris Rotation** -- VEX wrangle calculates perimeter-based angular velocity with 0.25 damping. Store in custom attribute to bypass POP solver orientation handling.
9. **Instance Debris Geometry** -- Extract small train pieces as packed primitives. Assign debris index per particle for instancing. Prepare rock instances for landscape scatter. Set up Solaris instancing with proper index attributes.

## Tips & Insights

- Surface scatter mode is more appropriate than volume fill for thin-walled objects like vehicles -- it avoids wasting particles in empty interior space.
- Compression hardening is the key parameter for controlling whether metal bends or tears. Even a small increase dramatically changes the fracture behavior.
- The varying friction VDB is a powerful art-direction tool: low friction on rails for smooth travel, high friction on ground for dramatic tumbling and tearing.
- Always check for consistent point count before running MPM Post Structure and MPM Deformed Pieces -- changing counts will cause retargeting failures.
- The close-gap feature is essential for metal tearing shots; without it, fracture lines look like broken polygons rather than torn material.
- The filler point count in MPM Post Structure may need tuning -- excessive filler points add computation without improving visual quality.
- Storing angular velocity in a custom attribute (not `w`) prevents the POP solver from overriding your carefully computed rolling rotation.

## Assets

| Asset | Path | Format |
|-------|------|--------|
| EMD GP7 Western Pacific 713 | `train/EMD_GP7_Western_Pacific_713 (1)/scene.usdc` | USDC |
| Subway Car | `train/Subway_Car/scene.usdc` | USDC |
| Railway Track (parts/rail) | `train_tracks/Railway_track_train_route_Railway_parts_rail/scene.usdc` | USDC |
| Train Track | `train_tracks/Train_Track/scene.usdc` | USDC |
| Train Tracks and Cart | `train_tracks/Train_Tracks_and_Train_Cart/scene.usdc` | USDC |
| Rocky Summit Landscape | `landscape/Rocky_summit_in_Mondarrain/scene.usdc` | USDC |
| Boulder 01 (4K) | `rocks/boulder_01_4k.usdc/boulder_01_4k.usdc` | USDC |
| Namaqualand Boulder 02 (4K) | `rocks/namaqualand_boulder_02_4k.usdc/namaqualand_boulder_02_4k.usdc` | USDC |
| Namaqualand Boulder 05 (4K) | `rocks/namaqualand_boulder_05_4k.usdc/namaqualand_boulder_05_4k.usdc` | USDC |
| Rock 09 (4K) | `rocks/rock_09_4k.usdc/rock_09_4k.usdc` | USDC |
| Rock Moss Set 01 (4K) | `rocks/rock_moss_set_01_4k.usdc/rock_moss_set_01_4k.usdc` | USDC |
| Rock Moss Set 02 (4K) | `rocks/rock_moss_set_02_4k.usdc/rock_moss_set_02_4k.usdc` | USDC |

*Asset root: `D:/HOUDINI_PROJECTS_2025/MPM_MASTERCLASS_FILES/`*

---
*Full transcript: [16_train_wreck.md](../../_raw_documentation/mpm_masterclass/16_train_wreck.md)*
