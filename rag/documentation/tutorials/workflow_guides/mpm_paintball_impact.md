---
title: "MPM Paintball Impact"
category: tutorials
subcategory: workflow_guides
keywords: ["mpm", "paintball", "impact", "splatter", "viscous_fluid", "collision", "surface_tension", "rubber_shell", "incompressibility", "slow_motion", "scale_up", "numerical_precision", "meshing", "mpm_surface", "vdb", "color_blending", "substeps", "material_condition"]
common_queries:
  - "How do I set up a paintball impact simulation in MPM?"
  - "How do I handle small-scale numerical precision issues in MPM?"
  - "How do I use surface tension in MPM?"
  - "How do I mesh MPM paint splatter with color?"
  - "What are good MPM surface settings for liquid tendrils?"
  - "How do I set up rubber shells in MPM?"
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=zj5ANrtD-X8"
  series: "SideFX MPM H21 Masterclass"
  part: 11
  total_parts: 18
  presenter: "Alex Wevinger"
---

# MPM Paintball Impact

**Source:** [SideFX MPM H21 Masterclass - Part 11](https://www.youtube.com/watch?v=zj5ANrtD-X8)
**Presenter:** Alex Wevinger

## Overview

This is the first practical demo scene in the masterclass, demonstrating a slow-motion paintball collision effect. Three paintballs converge on a central point, their rubber shells rupture, and paint splatters with detailed tendrils driven by surface tension. The setup covers scale-up techniques for numerical precision, dual-material simulation (rubber shell + liquid paint), surface tension configuration, and MPM Surface meshing with color blending.

## Key Concepts

### Scale-Up for Numerical Precision

Working at real-world paintball scale introduces numerical precision issues in the MPM solver. The solution is to scale the entire scene by 100x, then compensate by multiplying the time scale by 100 and dividing gravity by 100. This preserves physically correct behavior while avoiding floating-point edge cases at small scales. This technique is recommended for any slow-motion, small-scale MPM effect.

### Rubber Shell Setup

The paintball shells use the **rubber preset** with stiffness multiplied by 10 for a very rigid outer casing. The shell type is set to **surface** (hollow inside), not solid. Relaxation iterations are increased to ensure good particle coverage on the shell surface. Minor holes in the shell coverage are acceptable because the MPM Surface meshing step fills these gaps.

### Paint Fill (Liquid Interior)

The interior paint uses the **water preset** with increased incompressibility. Higher incompressibility makes the liquid resist compression more aggressively, producing more explosive splatter behavior on impact. The shell geometry is shrunk slightly before filling with paint particles to keep the liquid contained within the rubber boundary.

### Surface Tension Configuration

Surface tension is enabled on the MPM Solver using the **point-based method**, which is the most reliable option. Because surface tension introduces stiffness, the minimum substeps are increased and the material condition threshold is decreased to allow the solver to ramp up substeps more aggressively when needed. Two global substeps are also added for additional stability.

### Particle Separation Multiplier

A global control sets the particle separation multiplier. The final renders use a multiplier of 1 (full resolution), but during interactive work a value of 2 reduces the particle count to 1/8 of the final resolution in 3D, significantly speeding up iteration.

## Nodes & Parameters

| Node | Purpose | Key Parameters |
|------|---------|----------------|
| MPM Solver | Runs the paintball simulation | Surface Tension (point-based), Min Substeps, Material Condition, Global Substeps (2), Time Scale (100x), Gravity (/100) |
| MPM Configure Object (shell) | Sets up rubber shell material | Preset: Rubber, Stiffness Multiplier: 10x, Type: Surface, Relaxation Iterations: increased |
| MPM Configure Object (paint) | Sets up liquid paint interior | Preset: Water, Incompressibility: increased |
| MPM Domain | Defines simulation bounds | All bounds set to Delete (kills escaping particles) |
| MPM Surface (shell) | Meshes rubber shell particles | Output: Polygon Soup, Method: VDB from Particles, Filtering: light, Adaptivity: some |
| MPM Surface (paint) | Meshes paint particles | Output: Polygon Soup, Dilation/Erosion/Smoothing: aggressive, Adaptivity: 0 (prevents color flickering) |
| Attribute Transfer | Smooths paint colors | Transfers Cd between paint particles before meshing |

## Workflow Steps

1. **Build paintball sources** -- Create a circle, sample 3 points for initial positions, jitter for randomness, set velocity toward center, assign pscale and ball ID attributes, copy spheres onto points.
2. **Scale up by 100x** -- Apply uniform scale of 100 to all geometry. Multiply time scale by 100 and reduce gravity by 100 to compensate.
3. **Add surface variation** -- Apply noise to the paintball spheres, then smooth to create subtle organic deformation. Subdivide once for final detail.
4. **Configure rubber shells** -- Use MPM Configure Object with rubber preset, 10x stiffness, surface type, increased relaxation iterations.
5. **Configure paint fill** -- Shrink shell slightly, fill interior with MPM Configure Object using water preset and increased incompressibility. Preserve ball ID attribute.
6. **Set up solver** -- Enable surface tension (point-based), increase min substeps, decrease material condition, add 2 global substeps. Remove ground plane collision. Ensure ball ID flows through output.
7. **Correct velocity for slow motion** -- Multiply output velocity by the time scale factor so motion blur renders correctly at slow-motion playback.
8. **Mesh shells** -- Split shell particles, iterate per shell with For Each, run through MPM Surface with VDB from Particles method and light filtering.
9. **Mesh paint** -- Run Attribute Transfer to smooth Cd colors between paints. Mesh with MPM Surface using aggressive dilation, erosion, and smoothing. Set adaptivity to 0 to prevent color flickering.

## Tips & Insights

- Always scale up small-scale simulations to avoid MPM numerical precision issues. A 100x scale factor with compensated time and gravity is a reliable approach.
- Setting adaptivity to 0 on the paint mesh prevents frame-to-frame polygon topology changes that cause color flickering at material boundaries.
- The point-based surface tension method is the most stable option but requires careful substep tuning. If instabilities appear, lower the material condition threshold first.
- Each demo scene in the masterclass follows a consistent layout: a subnet for the effect, a Solaris setup for rendering, and a TOP network for dependency management.
- The particle separation multiplier at 2 gives 1/8 resolution in 3D -- use this for fast iteration, then set to 1 for final quality.

---
*Full transcript: [11_paintball_impact.md](../../_raw_documentation/mpm_masterclass/11_paintball_impact.md)*
