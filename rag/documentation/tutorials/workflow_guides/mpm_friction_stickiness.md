---
title: "MPM Friction and Stickiness"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "friction", "stickiness", "material_properties", "collision", "adhesion", "per_voxel", "vdb_attribute"]
agent_relevance:
  Librarian: 0.90
  GraphTracer: 0.75
  VexAuditor: 0.45
related_documents:
  - path: "tutorials/workflow_guides/mpm_continuous_emission.md"
    reason: "Previous in series: MPM Continuous Emission"
  - path: "tutorials/workflow_guides/mpm_deforming_colliders.md"
    reason: "Next in series: MPM Deforming Colliders"
  - path: "tutorials/workflow_guides/mpm_surface_tension.md"
    reason: "Related: friction/stickiness interact with surface tension"
common_queries:
  - "How to vary friction per voxel in MPM?"
  - "MPM per-voxel friction and stickiness"
  - "MPM collider friction attribute"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=UYj3sUThg-0"
  series: "SideFX MPM H21 Masterclass"
  part: 4
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Friction and Stickiness

**Source:** [SideFX MPM H21 Masterclass - Part 4](https://www.youtube.com/watch?v=UYj3sUThg-0)
**Presenter:** Alex Wevinger

## Overview

Houdini 21 introduces per-voxel varying friction and stickiness on MPM colliders, replacing the Houdini 20.5 workaround of duplicating colliders into separate objects with different friction values. A `friction` (and/or `stickiness`) point attribute on the collider geometry is automatically converted to a VDB grid by the MPM Collider node, providing spatial control without splitting geometry.

## Key Concepts

### Old Approach (H20.5)

In Houdini 20.5, varying friction required splitting the collider into separate MPM Collider nodes, each with a different friction value. This was tedious for complex patterns and added computational overhead from multiple collider objects.

### New Approach (H21): Attribute-Driven VDB

The MPM Collider node now has a "Create VDB from Attribute" checkbox under Material > Friction. When enabled, it reads a `friction` point attribute from the incoming geometry and converts it to a friction VDB grid. The same mechanism works for `stickiness`.

### Attribute Type Requirement

The MPM Collider expects a **point** attribute named `friction` (or `stickiness`). If you have a primitive attribute instead, it will be promoted to points — but on low-resolution geometry, averaging during promotion can collapse all values to a single average. Use a **Cusp** SOP to split shared points before promotion to preserve sharp friction boundaries.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Collider | Collision geometry with varying friction | Material > Friction > Create VDB from Attribute |
| Attribute Wrangle | Set friction/stickiness per-point | `f@friction = ingroup(0, "groupA", @primnum) ? 100 : 0;` |
| Cusp | Fix attribute promotion | Splits shared points so primitive-to-point promotion preserves boundaries |
| MPM Configure | Initialize setup | Particle Separation |

## Workflow Steps

1. **Prepare collider geometry** — Paint or compute a `friction` point attribute on the collider mesh (values typically 0-100)
2. **If using primitive groups** — Use a Wrangle to set `f@friction` per primitive, then add a Cusp SOP before the MPM Collider to avoid averaging during promotion
3. **Connect to MPM Collider** — Pipe the attributed geometry into the MPM Collider node
4. **Enable VDB creation** — On MPM Collider, under Material > Friction, check "Create VDB from Attribute"
5. **Verify** — Middle-click the MPM Collider to confirm a `friction` VDB grid exists; use visualization mode to see the spatial friction distribution
6. **Repeat for stickiness** — The same workflow applies to per-voxel stickiness

## Tips & Insights

- Always use **point** attributes for friction/stickiness. Primitive attributes get averaged during promotion and lose spatial variation on low-res geometry.
- If you must start from primitive attributes, add a Cusp SOP before the MPM Collider to split shared points and preserve boundaries.
- Both friction and stickiness support per-voxel variation using the same mechanism.
- The first simulation frame may be slow due to OpenCL kernel compilation — this is a one-time cost.
- This replaces the old pattern of duplicating colliders into separate MPM Collider nodes with different friction values.
- Friction values can be very high (100+) for strong adhesion effects.

---
*Full transcript: [04_friction_stickiness.md](../../_raw_documentation/mpm_masterclass/04_friction_stickiness.md)*
