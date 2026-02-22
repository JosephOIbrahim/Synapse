---
title: "MPM Deform Pieces"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "mpmdeformpieces", "deformation", "pieces", "chunks", "post_simulation", "retargeting", "stretch_ratio", "point_deformation", "piece_transformation", "fracture_retarget", "copy_to_points", "instancing"]
common_queries:
  - "How do I retarget fractured pieces onto an MPM simulation?"
  - "What is the difference between point and piece retargeting modes?"
  - "How do I control cracking vs stretching in MPM deform pieces?"
  - "Can I use MPM deform pieces without fracturing the original asset?"
  - "What does the stretch ratio parameter do in MPM deform pieces?"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=iasTN8SZC4A"
  series: "SideFX MPM H21 Masterclass"
  part: 9
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Deform Pieces

**Source:** [SideFX MPM H21 Masterclass - Part 9](https://www.youtube.com/watch?v=iasTN8SZC4A)
**Presenter:** Alex Wevinger

## Overview

The MPM Deform Pieces node retargets fractured geometry onto an MPM simulation, driving each piece's motion from the simulated particle data. It provides two retargeting algorithms -- point-based and piece-based -- and blends between them using a stretch ratio threshold to eliminate both unwanted cracking and stretching artifacts. This node also supports arbitrary geometry instancing on MPM points without requiring the MPM Fracture node upstream.

## Key Concepts

### Retargeting Types: Point vs Piece

The node offers two fundamental retargeting algorithms. **Piece-based** retargeting finds the closest MPM particle to each fracture piece and applies that particle's full transformation matrix. This preserves piece shape but introduces visible cracks between adjacent pieces during mild deformation. **Point-based** retargeting ignores piece boundaries entirely -- each vertex finds its closest MPM particle and deforms independently. This eliminates cracks but introduces stretching artifacts where pieces span multiple MPM particles moving in different directions.

### Point and Piece Blending (Default Mode)

The default "Point and Piece" mode combines both algorithms. It starts with point-based deformation, then checks each piece's post-deformation size against its rest size. When the stretch exceeds the **stretch ratio** threshold, the node switches that piece to piece-based transformation. This gives clean, crack-free geometry in mildly deforming regions while preserving rigid piece shapes in areas of significant separation.

### Stretch Ratio Parameter

The stretch ratio defines the deformation threshold at which a piece switches from point-based to piece-based retargeting. Lower values trigger the switch earlier (less tolerance for stretching), while higher values allow more point-level deformation before falling back to rigid piece transforms.

### Using MPM Deform Pieces Without Fracturing

The node does not require MPM Fracture upstream. Any geometry with a `name` attribute can be driven by an MPM simulation. A practical workflow: fuse the first-frame MPM point cloud to reduce density, copy geometry onto those points with Copy to Points, add a `name` attribute, and pipe the result into MPM Deform Pieces. This is useful for instancing debris, props, or scattered objects that ride along with the simulation.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Deform Pieces | Retargets geometry onto MPM sim | Retargeting Type, Stretch Ratio, Close Gaps, Start/End Frame |
| MPM Solver (upstream) | Provides simulation data | Start Frame (auto-flows to Deform Pieces) |
| Fuse | Decimates MPM point cloud for instancing | Distance threshold |
| Copy to Points | Distributes geometry on MPM points | Target Points input |
| Attribute Wrangle | Adds required `name` attribute | Custom snippet |

## Workflow Steps

1. **Connect inputs** -- Pipe the fractured (or arbitrary) geometry into the first input and the MPM simulation into the second input of MPM Deform Pieces.
2. **Set frame range** -- Start and end frames auto-flow from the MPM Solver and upstream nodes. Override manually if needed.
3. **Choose retargeting type** -- Select "Point and Piece" (default) for the best blend of accuracy. Use "Piece" only or "Point" only for specific edge cases.
4. **Tune stretch ratio** -- Adjust the threshold to control where the algorithm switches between point and piece modes. Check the impact frame closely.
5. **Transfer attributes** -- Use the attribute transfer section to carry additional data (color, UVs, custom attributes) from the MPM simulation onto the deformed geometry.
6. **Alternative: instance without fracturing** -- Fuse the first-frame point cloud, copy geometry onto points, add a `name` attribute, then connect to MPM Deform Pieces with manual end frame set.

## Tips & Insights

- The start and end frame parameters appear grayed out when they are automatically inherited from upstream nodes. Override them by switching to manual mode.
- The `name` attribute is required on input geometry for the node to function correctly, whether using fractured pieces or custom instanced geometry.
- The "Close Gaps" option is not demonstrated in this section but is critical for metal tearing workflows -- covered in Part 10 (Destruction Workflow).
- For instancing workflows, the MPM point cloud on the first frame serves as the distribution source. Use Frame Hold to lock it to frame 1 before copying geometry.

---
*Full transcript: [09_mpmdeformpieces.md](../../_raw_documentation/mpm_masterclass/09_mpmdeformpieces.md)*
