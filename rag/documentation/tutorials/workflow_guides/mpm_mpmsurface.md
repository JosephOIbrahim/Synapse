---
title: "MPM Surface Meshing"
category: tutorials
subcategory: workflow_guides
keywords:
  - mpm
  - mpmsurface
  - meshing
  - surface_extraction
  - post_simulation
  - particle_to_mesh
  - neural_point_surface
  - vdb_from_particle
  - sdf
  - density_vdb
  - polygon_mesh
  - mask_smooth
  - vdb_surface_mask
  - attribute_transfer
  - snow
  - liquid
  - granular
common_queries:
  - "How do I convert MPM particles to a mesh?"
  - "What is neural point surface in Houdini 21?"
  - "How to transfer attributes from MPM simulation to mesh?"
  - "How to optimize MPM surface for rendering?"
  - "What is the mask smooth option on MPM Surface?"
  - "How to chain two MPM Surface nodes to avoid recomputing SDF?"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=ZNImPE9WbkI"
  series: "SideFX MPM H21 Masterclass"
  part: 6
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Surface Meshing

**Source:** [SideFX MPM H21 Masterclass - Part 6](https://www.youtube.com/watch?v=ZNImPE9WbkI)
**Presenter:** Alex Wevinger

## Overview

The MPM Surface node converts MPM particle simulations into renderable geometry -- SDF volumes, density VDBs, or polygon meshes. It is the MPM equivalent of the Particle Fluid Surface node used for FLIP. In Houdini 21, it integrates the new Neural Point Surface (NPS) method, which uses a 3D convolutional neural network to produce higher-quality surfaces with context-aware detail preservation. The node also supports mask-based smoothing, attribute transfer from rest geometry, and a polygon pruning workflow to optimize memory for Karma XPU renders.

## Key Concepts

### Output Types
MPM Surface provides three selectable outputs, each with its own parameter tab: a signed distance field (SDF), a density VDB, and a polygon mesh. The SDF and velocity outputs are commonly used as collider representations for secondary simulations, while density VDBs or polygon meshes serve as render representations.

### Surfacing Methods
Two surfacing approaches are available. **VDB from Particle** is the traditional method that splats each particle as a sphere into a volume grid -- reliable and CPU-friendly. **Neural Point Surface (NPS)** is new in H21 and runs an ONNX-based 3D convolutional neural network over a density grid built from the point cloud. NPS ships with four pre-trained models: Balanced, Smooth, Liquid (optimized for fluid), and Granular (optimized for sand, soil, snow). NPS performs localized treatment, producing smooth flat regions while preserving sharp detail in high-action areas. It requires a capable GPU with sufficient VRAM; CPU-only execution is significantly slower.

### Mask Smooth
The mask smooth option selectively protects high-detail regions from smoothing. It uses two MPM attributes: **minimum stretch** (the Jp attribute detecting material breakage) and **curvature**. Areas exceeding these thresholds are excluded from the smoothing pass, preserving cracks and sharp edges while smoothing calm regions. The mask can be visualized per-attribute to verify coverage.

### VDB Surface Mask (Polygon Pruning)
Connecting a static collider to the fourth input activates the VDB Surface Mask tab. This prunes polygons hidden behind collision geometry, saving memory for Karma XPU renders. Two parameters control the result: **mask offset** pushes the deletion boundary up or down, and **spread iterations** shrink the deletion mask to close gaps between the mesh and the collider. Increase spread iterations until no visible gap remains.

### Chained MPM Surface (SDF Reuse)
A common production pattern uses two MPM Surface nodes: one generates the SDF and velocity field for collision, and its output pipes into the second input of another MPM Surface that produces a density VDB or polygon mesh for rendering. The second node reuses the precomputed SDF and velocity from the first, eliminating duplicate computation and saving significant farm time.

### Attribute Transfer
The polygon mesh output supports attribute transfer from MPM particles (first input) and from a rest source model (third input). Connecting rest geometry with UVs to the third input enables per-island UV transfer without interpolation artifacts. Point attributes such as Cd (color) can be transferred by specifying them in the attribute list.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Surface | Convert particles to SDF / density / mesh | Output Type, Surface Method (VDB from Particle / Neural Point Surface), NPS Model |
| MPM Surface (filtering) | Post-process the SDF | Dilation, Smooth, Erosion (applied sequentially) |
| MPM Surface (mask smooth) | Protect detail from smoothing | Min Stretch, Curvature threshold |
| MPM Surface (velocity tab) | Generate velocity field | Voxel Size Scale (default upscaled to save disk) |
| MPM Surface (polygon mesh) | Mesh output settings | Adaptivity, Convert to Poly Soup |
| MPM Surface (VDB surface mask) | Prune hidden polygons | Mask Offset, Spread Iterations |
| Neural Point Surface | ML-based surfacing (embedded in MPM Surface) | Model: Balanced / Smooth / Liquid / Granular |

## Workflow Steps

1. **Drop MPM Surface** -- Connect MPM simulation output to the first input. Voxel size auto-configures from the simulation resolution.
2. **Choose surfacing method** -- Select VDB from Particle for CPU workflows, or Neural Point Surface with an appropriate model (Liquid, Granular, etc.) for GPU-accelerated quality.
3. **Apply filtering** -- Enable dilation, smooth, and erosion in sequence. Enable mask smooth to protect fracture edges and high-curvature areas.
4. **Select output type** -- Choose SDF for collision, density VDB for volumetric rendering, or polygon mesh for surface rendering.
5. **Transfer attributes** -- Enable attribute transfer from MPM particles (Cd, etc.) or connect rest geometry to the third input for UV transfer.
6. **Optimize with polygon pruning** -- Connect static colliders to the fourth input, enable VDB Surface Mask, adjust mask offset and spread iterations to remove hidden geometry.
7. **Chain for dual representation** -- Pipe the first MPM Surface output into the second input of a downstream MPM Surface to reuse SDF/velocity data for a separate render representation.

## Tips & Insights

- Neural Point Surface works best on GPU; fall back to VDB from Particle if running CPU-only.
- The Granular NPS model is purpose-built for sand, soil, and snow -- it is not always the best choice for other material types.
- UV transfer from the rest source model (third input) handles each UV island individually, avoiding interpolation bleed across seams.
- The chained MPM Surface pattern (output into second input) looks unusual in the node graph but is standard practice for producing both collision and render representations without redundant computation.
- When rendering with Karma XPU, always consider polygon pruning via the VDB surface mask to reduce VRAM consumption on dense simulations.

---
*Full transcript: [06_mpmsurface.md](../../_raw_documentation/mpm_masterclass/06_mpmsurface.md)*
