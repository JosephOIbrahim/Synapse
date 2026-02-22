---
title: "MPM Continuous Emission"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "continuous_emission", "expansion", "particle_emission", "source", "fluid_source", "overlapping_emission", "fill", "container", "liquid", "volume_fill"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_auto_sleep.md"
    reason: "Previous in series: MPM Auto Sleep"
  - path: "tutorials/workflow_guides/mpm_friction_stickiness.md"
    reason: "Next in series: MPM Friction and Stickiness"
common_queries:
  - "How to fill a container with MPM?"
  - "MPM continuous emission expansion"
  - "MPM overlapping emission"
  - "How to source material on top of existing material in MPM?"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=AGjuRlj5sm4"
  series: "SideFX MPM H21 Masterclass"
  part: 3
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Continuous Emission

**Source:** [SideFX MPM H21 Masterclass - Part 3](https://www.youtube.com/watch?v=AGjuRlj5sm4)
**Presenter:** Alex Wevinger

## Overview

Continuous emission with expansion solves the problem of filling containers or adding material on top of existing material in MPM. By default, MPM prevents new particles from being emitted where particles already exist (since adding more particles to an already-occupied voxel wastes computation). The expansion parameter creates internal pressure that pushes existing particles outward, creating void pockets where new particles can be introduced.

## Key Concepts

### Why Default Emission Cannot Fill Containers

MPM uses a dual particle-grid representation where approximately 8 particles occupy each voxel. Adding more particles to an already-occupied voxel provides no additional detail — all particles in a voxel contribute to a single voxel state, and that state is scattered back to the particles. So by default, MPM rejects new particles if existing particles are already nearby, preventing wasteful computation.

### How Expansion Works

The expansion parameter on MPM Source creates internal pressure that pushes existing particles away from the emission region. This cycle repeats every substep:

1. Internal pressure pushes existing particles outward from the emitter
2. Particles move, creating void pockets near the emission source
3. New particles can now be introduced in the empty space
4. The process repeats, gradually growing the volume of material

With expansion set to 1, growth is very slow. Setting it to 25 produces visible volume growth suitable for filling a wine glass or similar container.

### Material Flexibility

Continuous emission works with any MPM material preset, not just liquids. The demo shows both water (filling a wine glass until overflow) and snow (filling with a stiff granular material). Different materials produce dramatically different visual results when continuously emitted into a container.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Configure | Initialize MPM setup | Particle Separation |
| MPM Source | Source geometry and material | Continuous Emission (enable), Overlapping Emission (enable), Expansion (default 1, try 25 for visible filling), Material Preset |
| MPM Collider | Container/collision geometry | Resolution override, Particle Level Collision |
| MPM Solver | Simulation | — |

## Workflow Steps

1. **MPM Configure** — Start as always
2. **Set up source and collider** — Source is the emitter geometry, collider is the container (e.g., wine glass)
3. **Increase collider resolution** — For thin colliders like glass walls, override resolution on MPM Collider and enable Particle Level Collision
4. **Enable continuous emission** — On MPM Source, enable Continuous Emission
5. **Enable overlapping emission** — On MPM Source, enable Overlapping Emission to allow particles where particles already exist
6. **Set expansion** — Increase the Expansion parameter (try 25) to create internal pressure that pushes existing particles out, making room for new ones
7. **Choose material preset** — Water, snow, or any other preset; each produces different filling behavior

## Tips & Insights

- Expansion of 1 is barely visible. Use values around 25 for practical container-filling scenarios.
- This feature was specifically designed for the Houdini 21 launch demo (cookie and cream shot) where whipped cream was being added on top of a drink.
- Works with all material presets — not limited to liquids. Snow, sand, and other materials can all be continuously emitted.
- The 8-particles-per-voxel limit is fundamental to MPM. Adding more particles per voxel does not increase detail, only computation cost.
- For visualization, use a Point Wrangle with `@Cd = chramp("color", @Frame / max_frame)` to color particles by emission time, showing how material layers build up.

---
*Full transcript: [03_continuous_emission.md](../../_raw_documentation/mpm_masterclass/03_continuous_emission.md)*
