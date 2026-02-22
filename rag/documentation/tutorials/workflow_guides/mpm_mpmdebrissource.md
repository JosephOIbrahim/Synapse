---
title: "MPM Debris Source"
category: tutorials
subcategory: workflow_guides
keywords:
  - mpm
  - mpmdebrissource
  - debris
  - secondary_elements
  - secondary_emission
  - chunks
  - fragments
  - pop_simulation
  - point_replication
  - stretching
  - Jp_attribute
  - density_vdb
  - collider
  - high_frequency_detail
  - velocity_spread
common_queries:
  - "How do I add secondary debris to an MPM simulation?"
  - "What does MPM Debris Source do?"
  - "How to emit fine detail particles from MPM?"
  - "How to render MPM debris as density volume?"
  - "How to avoid stepping artifacts in debris emission?"
  - "How does max distance to surface work in MPM Debris Source?"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=83EffKFYeCU"
  series: "SideFX MPM H21 Masterclass"
  part: 7
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Debris Source

**Source:** [SideFX MPM H21 Masterclass - Part 7](https://www.youtube.com/watch?v=83EffKFYeCU)
**Presenter:** Alex Wevinger

## Overview

The MPM Debris Source node generates secondary emission points from an MPM simulation, adding high-frequency detail that the base particle resolution cannot capture. It is the MPM equivalent of the RBD Debris Source node. The node prunes candidate points based on material stretch (Jp attribute), speed, and proximity to the simulation surface, then replicates and spreads them along velocity vectors to produce continuous, stepping-free emission trails for downstream POP simulations.

## Key Concepts

### Purpose and Inputs
MPM Debris Source adds finer-scale detail on top of the base MPM particle cloud. The first input takes the MPM simulation particles (required). The second input takes the MPM Surface SDF and velocity representation (strongly recommended) -- this provides the surface distance field needed for proximity-based pruning.

### Point Pruning
The Prune Points section controls which MPM particles qualify as emission candidates. Three filters are available: **Minimum Stretching** uses the Jp attribute to select points where the material is breaking or stretching (lower values are more permissive, higher values are more conservative). **Minimum Speed** filters out slow-moving particles. **Max Distance to Surface** restricts emission to a band around the SDF surface -- particles too deep inside the collider are excluded, preventing unnatural debris spawning from within solid volumes. This distance is defined in multiples of dx (simulation voxel size), so it scales automatically with scene size. A final **Ratio to Keep** parameter uniformly reduces the candidate count.

### Point Replication
After pruning, isolated candidate points can be replicated based on stretching and speed attributes. Each attribute is remapped through a ramp: by default, the stretching value is multiplied by 10 and remapped to 0-1 to drive replication count. The same approach applies to speed. Increasing the multiplier produces more replicated points in high-stretch or high-speed regions.

### Velocity Spread
Emitting debris only at integer frames produces visible stepping artifacts -- clusters of particles separated by gaps. The **Spread Points Along Velocity** option distributes replicated points along the velocity vector within the distance traveled between two frames, producing continuous emission trails that look natural in motion.

### Attribute Handling
The node strips most attributes, keeping only pscale, velocity (v), and orient. Orient is not emitted by the MPM solver by default, but can be initialized as random orientations within the node for downstream instancing. The output pscale is scaled down to approximately one-third of the MPM particle pscale, ensuring debris reads as fine-scale detail.

### Rendering Debris as Density
For volumetric rendering, the debris output can be fed into a second MPM Surface node set to density VDB output. Since the debris is not an MPM simulation, the resolution must be overridden manually -- typically by referencing the voxel size from the main MPM Surface density grid via an expression. The debris density and main simulation density are then combined using a VDB Combine with maximum mode.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Debris Source | Generate secondary emission points | Start Frame, Time Scale, Emit at Integer Frame Only |
| MPM Debris Source (prune) | Filter emission candidates | Min Stretching, Min Speed, Max Distance to Surface, Ratio to Keep |
| MPM Debris Source (replicate) | Multiply points in active regions | Stretching Remap, Speed Remap, Multiplier |
| MPM Debris Source (spread) | Eliminate stepping artifacts | Spread Points Along Velocity |
| MPM Debris Source (attributes) | Control output attributes | Keep: pscale, v, orient; Pscale multiplier (~0.33x) |
| POP Network | Simulate debris dynamics | First input: emission points; Second input: collider |
| MPM Surface (for debris) | Surface debris as density VDB | Override Resolution (match main grid), Output Type: Density VDB |
| VDB Combine | Merge main + debris density | Operation: Maximum |

## Workflow Steps

1. **Connect inputs** -- Wire MPM simulation particles to input 1 and MPM Surface SDF/velocity output to input 2.
2. **Tune pruning** -- Adjust min stretching to control emission sensitivity. Enable max distance to surface to restrict candidates to a band around the SDF.
3. **Enable replication** -- Turn on stretching-based and speed-based replication. Adjust multipliers to control debris density.
4. **Spread along velocity** -- Enable velocity spread to eliminate per-frame stepping in emission trails.
5. **Simulate in POP** -- Feed the debris source output into a POP Network as emission (input 1), with the MPM Surface SDF as collider (input 2).
6. **Render as density** -- Pipe the POP output through a second MPM Surface set to density VDB, override the resolution to match the main grid, and combine with VDB Combine (maximum).

## Tips & Insights

- Always connect the MPM Surface SDF to the second input -- without it, max distance to surface pruning is unavailable and deep-interior particles may create unnatural collisions in the POP sim.
- The distance parameters are defined in dx units (simulation voxel size), so setups transfer across different scene scales without manual adjustment.
- For instanced debris (chunks, splinters), initialize the orient attribute within the node before sending to the POP simulation.
- When surfacing non-MPM particles (like POP debris) with MPM Surface, you must manually override the resolution since no MPM sim metadata is present -- use an expression referencing the main density grid's intrinsic voxel size.
- Reduce density opacity for the debris grid (e.g., multiply by 0.5) to keep fine particles looking appropriately transparent rather than overly opaque.

---
*Full transcript: [07_mpmdebrissource.md](../../_raw_documentation/mpm_masterclass/07_mpmdebrissource.md)*
