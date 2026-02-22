---
title: "MPM Post Fracture"
category: tutorials
subcategory: workflow_guides
keywords:
  - mpm
  - mpmpostfracture
  - fracture
  - voronoi
  - boolean
  - destruction
  - post_simulation
  - Jp_attribute
  - stretching
  - filler_points
  - align_fractures
  - cutting_geometry
  - mpm_deform_pieces
  - crack_alignment
  - metal_tearing
common_queries:
  - "How does MPM fracture differ from RBD fracture?"
  - "What does MPM Post Fracture do?"
  - "How to fracture geometry based on MPM simulation?"
  - "What is align fractures to stretch points?"
  - "How do filler points work in MPM Post Fracture?"
  - "How to control fracture piece size in MPM?"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=XAQgQi3wkNU"
  series: "SideFX MPM H21 Masterclass"
  part: 8
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Post Fracture

**Source:** [SideFX MPM H21 Masterclass - Part 8](https://www.youtube.com/watch?v=XAQgQi3wkNU)
**Presenter:** Alex Wevinger

## Overview

The MPM Post Fracture node performs destruction fracturing in reverse order compared to RBD: instead of fracturing first and then simulating, MPM simulates first and then fractures based on where the material dynamically broke. It analyzes the Jp (stretch/fracture) attribute from the MPM simulation at the end frame to determine crack locations, then generates Voronoi or Boolean fracture geometry aligned to those cracks. The resulting pieces are designed for use with the downstream MPM Deform Pieces node.

## Key Concepts

### Reverse Fracture Workflow
In traditional RBD destruction, you pre-fracture geometry and then simulate rigid body dynamics. MPM inverts this: the MPM solver simulates continuous material deformation first, recording where stretching and breaking occur via the Jp attribute. MPM Post Fracture then reads the final simulation state and fractures the original geometry along those dynamic crack lines. This produces more physically plausible fracture patterns because the cracks follow the actual stress distribution.

### End Frame Requirement
The node requires an explicit end frame parameter because it needs to know the final simulation state to determine fracture locations. The start frame is automatically read from the MPM simulation metadata, but the end frame must be set manually.

### Piece Selection
The Piece Selection tab controls which geometry pieces are candidates for fracturing. A **minimum length** parameter filters out pieces that are too small to warrant further subdivision. Pieces below this threshold display in red (excluded) while valid candidates display in green. This prevents unnecessary computation on small fragments.

### Fracture Points
Fracture point generation is driven by the Jp attribute from the MPM simulation. The **min stretching** parameter controls the threshold: lowering it includes more points (more permissive), raising it requires stronger material breakage to qualify. A **fuse distance** parameter decimates the point cloud to prevent over-fragmentation.

### Filler Points
Using only MPM-derived fracture points can produce elongated shards that lack sufficient resolution for the material to bend naturally. **Filler points** add a uniform low-resolution distribution of fracture seeds throughout the volume. A **max distance** parameter limits filler points to regions near active MPM fracture points, preventing unnecessary subdivision in undamaged areas. Reducing the filler point spacing increases the base fracture resolution.

### Align Fractures to Stretch Points
This toggle is critical for crack recovery. Without it, fracture piece centroids are placed directly on the crack line, filling the crack with solid geometry that cannot separate. With it enabled, the centroids are shifted to neighboring positions on either side of the crack. This ensures the fracture seams align exactly with the dynamic crack in the MPM simulation, allowing pieces to separate cleanly when deformed. This is especially important for metal tearing effects; for materials like concrete it may be less critical.

### Cutting Method and Global Scale
Two cutting methods are available: **Boolean** produces detailed interior faces and is generally preferred, while **Voronoi** is faster but less detailed. The **global scale** parameter allows setups built at small scale to be ported to large-scale assets (e.g., buildings) by multiplying the scale uniformly.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Post Fracture | Fracture geometry from MPM sim data | Start Frame (auto), End Frame (manual), Name Space |
| MPM Post Fracture (piece selection) | Filter fracture candidates | Min Length |
| MPM Post Fracture (fracture points) | Generate fracture seeds | Min Stretching, Fuse Distance |
| MPM Post Fracture (filler points) | Add uniform base resolution | Filler Point Spacing, Max Distance to MPM Points |
| MPM Post Fracture (cutting) | Control fracture method | Cutting Method (Boolean / Voronoi), Geometry Type (Solid / Surface), Global Scale |
| MPM Post Fracture (align) | Align cuts to cracks | Align Fractures to Stretch Points (toggle) |
| MPM Post Fracture (interior) | Detail interior faces | Interior Detail settings |
| MPM Deform Pieces | Animate fractured pieces (downstream) | Requires matching name space |
| Exploded View | Visualize fracture result | Useful for inspecting piece separation |

## Workflow Steps

1. **Set up MPM simulation** -- Run the MPM solver with appropriate stiffness. The Jp attribute records where material stretches and breaks during the simulation.
2. **Drop MPM Post Fracture** -- Connect the source geometry to input 1 and the MPM simulation to input 2. Set the end frame manually.
3. **Tune piece selection** -- Enable the guide to visualize candidates. Increase min length to exclude small pieces from further fracturing.
4. **Adjust fracture points** -- Lower min stretching for more fracture detail, raise it for fewer, larger pieces. Adjust fuse distance to control point density.
5. **Add filler points** -- Reduce filler spacing to increase base fracture resolution. Set max distance to limit fillers to regions near active cracks.
6. **Enable align fractures** -- Turn on Align Fractures to Stretch Points, especially for tearing effects, to ensure fracture seams follow the simulation cracks.
7. **Choose cutting method** -- Select Boolean for detailed interior faces or Voronoi for speed. Enable interior detail as needed.
8. **Perform fracture** -- Enable Perform Fracture to generate the final cut geometry. Use Exploded View to inspect the result.

## Tips & Insights

- Always set the end frame explicitly -- the node cannot determine it from the simulation data automatically.
- The Jp attribute visualization (red = high stretch, purple = preserved rest volume) is the best diagnostic for understanding where fractures will occur.
- Filler points prevent elongated shards that resist bending. If pieces look unnaturally long, reduce the filler point spacing.
- Align Fractures to Stretch Points is essential for metal tearing workflows where clean crack separation must be visible. For chunky concrete destruction, it is less critical but still beneficial.
- The name space parameter must match between MPM Post Fracture and MPM Deform Pieces for the downstream deformation to work correctly.
- Use the guide visualization (green = included, red = excluded) to iterate on piece selection and fracture point parameters before enabling the actual fracture computation, which is more expensive.

---
*Full transcript: [08_mpmpostfracture.md](../../_raw_documentation/mpm_masterclass/08_mpmpostfracture.md)*
