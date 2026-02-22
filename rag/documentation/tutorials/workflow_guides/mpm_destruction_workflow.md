---
title: "MPM Destruction Workflow"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "destruction", "workflow", "fracture", "close_gaps", "metal_tearing", "retargeting", "post_fracture", "building_destruction", "piece_deformation", "point_deformation", "tolerance", "transition_width", "stretch_alignment", "meteorite"]
common_queries:
  - "How do I set up metal tearing with MPM?"
  - "What does Close Gaps do in MPM Deform Pieces?"
  - "How do I eliminate cracks in MPM destruction?"
  - "How can I speed up MPM fracture iteration?"
  - "What is the difference between tolerance and stretch ratio in MPM Deform Pieces?"
  - "How do I fracture a building with MPM?"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=mQuOe296oeg"
  series: "SideFX MPM H21 Masterclass"
  part: 10
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Destruction Workflow

**Source:** [SideFX MPM H21 Masterclass - Part 10](https://www.youtube.com/watch?v=mQuOe296oeg)
**Presenter:** Alex Wevinger

## Overview

This section demonstrates complete destruction workflows using MPM Post Fracture and MPM Deform Pieces together. Two examples are covered: a metal sheet tearing setup that introduces the critical Close Gaps mechanism, and a large-scale building destruction with a meteorite impact. The Close Gaps feature solves the problem of unrealistic cracks appearing in materials like metal that should either be torn or intact, with no intermediate cracking.

## Key Concepts

### Close Gaps Mechanism

When MPM Deform Pieces switches a piece from point-based to piece-based retargeting (due to excessive stretching), adjacent pieces receive slightly different rigid transformations, creating visible cracks. Close Gaps works at the **per-point** level rather than per-piece. For each point, it compares the position it would have under point-based deformation versus piece-based transformation. If the delta between the two positions is small, the point snaps back to point-based deformation, effectively closing the gap. If the delta is large (meaning the point is in a genuinely torn area), it stays at the piece-based position.

### Tolerance Parameter (Close Gaps)

The tolerance value controls how aggressively gaps are closed. Higher tolerance snaps cracks more aggressively, closing more gaps. Lower tolerance allows more cracks to persist. This operates analogously to the stretch ratio but at the point level rather than the piece level.

### Transition Width

To prevent jarring pops between frames when points switch between deformation modes, the transition width parameter creates a smooth interpolation over multiple frames. Increasing this value makes cracks open and close progressively rather than snapping instantaneously.

### Align Fracture to Stretch Pieces

In the MPM Post Fracture node, enabling "Align Fracture to Stretch Pieces" repositions fracture centroids so that the Jp (stretch) attribute points become the centers of fracture pieces. This ensures cracks appear precisely where the material is actually tearing, rather than at arbitrary Voronoi cell boundaries.

### Fast Fracture Iteration Trick

For large assets like buildings where full fracturing takes 10+ minutes, isolate a single piece for rapid iteration: use Connectivity to identify pieces, Blast to isolate one, then run MPM Post Fracture on just that piece. Fracturing a single piece takes roughly 5 seconds versus 10 minutes for the full asset. Dial in fracture settings on the isolated piece, then apply to the full geometry.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Post Fracture | Generates fracture geometry from MPM sim | Perform Fracture, Interior Details, Align Fracture to Stretch, Maximum Distance, Fracture Detail Multiplier |
| MPM Deform Pieces | Retargets fractured geo onto sim | Close Gaps (toggle), Tolerance, Transition Width, Stretch Ratio |
| MPM Solver | Runs the destruction simulation | (upstream, provides sim data) |
| Connectivity | Identifies connected pieces | Used to isolate single pieces for testing |
| Blast | Removes geometry by group | Used to isolate a piece for fast iteration |

## Workflow Steps

1. **Pipe rest geometry and simulation** -- Connect the rest mesh (with UVs) to MPM Post Fracture input 1, and the MPM simulation to input 2. Set end frame manually if not auto-flowing.
2. **Configure fracture density** -- Adjust the fracture detail multiplier and maximum distance. Visualize fill points to verify coverage matches the simulation extent.
3. **Enable Align Fracture to Stretch** -- For tearing materials, check this option so fracture centroids align with Jp stretch points, placing cracks at natural tear locations.
4. **Add interior details** -- Enable interior detail generation for realistic cross-section geometry at fracture surfaces.
5. **Connect MPM Deform Pieces** -- Pipe the fractured output into MPM Deform Pieces along with the simulation data.
6. **Enable Close Gaps** -- Toggle on for materials like metal that should not show intermediate cracks. Adjust tolerance and transition width to taste.
7. **Iterate on a single piece** -- For large assets, isolate one piece with Connectivity and Blast, tune fracture settings in seconds, then apply to the full geometry.

## Tips & Insights

- Close Gaps is essential for metal tearing -- without it, you get unrealistic cracks throughout the surface where pieces receive slightly different rigid transformations.
- The fill points generated by MPM Post Fracture respect the maximum distance parameter. Points only appear within that radius of existing MPM particles, preventing unnecessary computation in empty regions.
- When processing the full building example, the complete fracture pass took approximately 10 minutes. Always cache heavy fracture operations.
- The transition width parameter is critical for animation quality. Without it, gaps snap open and closed between frames, creating distracting pops.
- Small pieces can be excluded from fracturing automatically, reducing computation and preventing overly fragmented results on tiny geometry.

---
*Full transcript: [10_destruction_workflow.md](../../_raw_documentation/mpm_masterclass/10_destruction_workflow.md)*
