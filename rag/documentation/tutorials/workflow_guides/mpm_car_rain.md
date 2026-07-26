---
title: "MPM Car Rain"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "car", "rain", "water", "environment", "surface_tension", "droplets", "splash", "ior", "index_of_refraction", "total_internal_reflection", "condensation", "puddle", "ripple", "collision_detection", "particle_level_collision", "mist", "secondary_simulation", "rendering_artifact"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_pumpkin_smash.md"
    reason: "Previous in series: MPM Pumpkin Smash"
  - path: "tutorials/workflow_guides/mpm_wolf_snow.md"
    reason: "Next in series: MPM Wolf Snow"
common_queries:
  - "How to simulate rain splashing on a car with MPM"
  - "How to fix total internal reflection artifacts on thin water sheets"
  - "How to set up IOR variation based on distance to collider"
  - "How to increase collision detection distance for water sticking to geometry"
  - "How to create reverse-time raindrop synchronization"
  - "How to add condensation layer to wet surfaces"
  - "How to create dynamic puddles with ripple solver"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=mKg7OWiBQE4"
  series: "SideFX MPM H21 Masterclass"
  part: 13
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Car Rain

**Source:** [SideFX MPM H21 Masterclass - Part 13](https://www.youtube.com/watch?v=mKg7OWiBQE4)
**Presenter:** Alex Wevinger

## Overview

This production demo builds a complete rain-on-car shot using MPM for the splash simulation layered with non-MPM elements for raindrops, mist, condensation, and puddles. The MPM simulation only handles the crown splashes and water trickling on the car surface, while surrounding layers are purpose-built for efficiency. A key rendering technique addresses total internal reflection artifacts on thin water sheets by varying IOR based on distance to the car surface.

## Key Concepts

### Reverse-Time Raindrop Synchronization
Raindrops are not simulated falling from the sky with MPM. Instead, impact positions are defined on the car surface, and time is reversed: starting from the impact frame, raindrops are lifted backward to their emission positions, then time and velocity are flipped back. This guarantees perfect synchronization between raindrop impacts and the pre-modeled crown splashes that feed the MPM source. The actual falling raindrops are rendered as instanced spheres with no MPM cost.

### Pre-Modeled Crown Splashes as MPM Source
Rather than relying on MPM to generate splash shapes, each raindrop impact has a manually shaped crown splash built from scattered points projected onto the car, shaped with velocity control, fused to remove overlaps, and converted via VDB from Particles. Velocity is transferred back to the mesh before feeding into MPM Source with continuous emission. This gives art-directable splash shapes while MPM handles the fluid dynamics after impact.

### IOR Distance Correction for Thin Water Sheets
When rendering thin water on a surface, air gaps between the water mesh and the car geometry cause total internal reflection: rays stay inside the water sheet and sample the HDR environment, producing unrealistic bright reflections. The fix is to compute distance from each mesh point to the car collider, store it as an IOR attribute, and remap it in the shader. Points very close to the car get IOR=1.0 (rays pass straight through), while points further away retain the normal water IOR of 1.33.

### Surface Tension and Collision Settings for Water Adhesion
Strong surface tension requires increased minimum substeps to maintain stability and a reduced material condition number. Particle-level collision is enabled for precise interaction with thin geometry. The collision detection distance is increased above the default of 1 to allow water particles to stick to the underside of geometry lips, enabling realistic water collection and dripping behavior at surface edges.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Solver | Simulate water splashes on car | water preset, surface tension on, min substeps increased, material condition reduced |
| MPM Source | Feed crown splash geometry | continuous emission enabled |
| MPM Surface | Mesh the water simulation | VDB from Particles mode, dilation + erosion + smoothing in sequence |
| Collision | Car as collider | particle-level collision on, detection distance increased above 1 |
| POP Solver | Mist burst from raindrop impacts | small water particulates for high-frequency detail |
| SOP Solver | Condensation layer | pscale reduced where water flows, restored over time |
| Ripple Solver | Dynamic puddle displacement | amplitude scaled to 25% for subtlety |

## Workflow Steps

1. **Prepare car geometry** -- Generate three versions: render model (with window thickness for refraction), watertight collider, and raindrop hit-area surface.
2. **Define impact positions** -- Isolate a grid above the car, scatter points, project onto car surface to get impact locations. Build oriented frames with surface-normal up vectors and random rotational variation.
3. **Model crown splashes** -- Copy ring shapes to impact points, sculpt splash profiles with velocity, fuse overlapping points, convert to VDB, transfer velocity back to mesh.
4. **Create reverse-time raindrops** -- Start from impact positions at frame 160, simulate backward to emission height, delete on arrival, then flip time and velocity to get forward-playing raindrops synchronized with splashes.
5. **Run MPM simulation** -- Water preset with strong surface tension, increased substeps, particle-level collision, increased detection distance. Kill points hitting the ground to save memory.
6. **Add mist layer** -- POP simulation of burst particulates at impact points, rendered as very small droplets for high-frequency detail.
7. **Mesh MPM output** -- VDB from Particles with sequential dilation, erosion, and smoothing. Compute distance-to-car attribute for IOR shader correction.
8. **Set up IOR shader** -- Remap distance attribute from [0,1] to [0, 1.33] in the rain material to eliminate total internal reflection on thin water sheets.
9. **Add condensation layer** -- Scatter points on car surface. Use a solver to reduce pscale where water flows and gradually restore it over time, creating dynamic condensation patterns.
10. **Build ground with puddles** -- Static puddles on concrete ground plus a dynamic puddle in front of the car using projected MPM kill-points displaced onto a grid with a ripple solver (amplitude at 25%).

## Tips & Insights

- Only simulate splashes with MPM; render falling raindrops as instanced spheres to save significant memory and compute.
- Increase collision detection distance above 1.0 to allow water to gather on geometry lips and edges before dripping, which is critical for realistic car-surface water behavior.
- Total internal reflection on thin water sheets is a common rendering artifact. The distance-based IOR remap (1.0 near surface, 1.33 further away) is a practical production fix.
- The dynamic puddle should extend along the full side of the car, not just the front, for better integration with the falling water kill zone.
- Resolution can be increased at any time via the global scale controller on the MPM container.
- The condensation layer and puddle system have nothing to do with MPM but add significant production value to the shot.

## Assets

| Asset | Path | Format |
|-------|------|--------|
| Porsche 718 Cayman GT4 | `car/` | External ([CGTrader](https://www.cgtrader.com/free-3d-models/car/sport-car/porsche-718-cayman-gt4-5734530d-8afb-4852-9421-b71bde9adce3)) |

*Asset root: `D:/HOUDINI_PROJECTS_2025/MPM_MASTERCLASS_FILES/`*

---
*Full transcript: [13_car_rain.md](../../_raw_documentation/mpm_masterclass/13_car_rain.md)*
