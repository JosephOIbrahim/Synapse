# MPM Solver (Material Point Method) -- Houdini 21

## Overview

MPM is a unified simulation framework for solids, granulars, and fluids. It represents materials as particles that transfer data to/from a background grid each substep, combining the strengths of Lagrangian (particle) and Eulerian (grid) methods. Houdini 21 adds surface tension, auto sleep, continuous emission, per-voxel friction/stickiness, improved deforming colliders, and 4 new post-simulation nodes.

## SOP-Level MPM Chain

```
source_geo -> mpmconfigure -> mpmsource -> mpmcollider -> mpmsolver -> post-sim nodes
```

Post-sim: `mpmsurface`, `mpmdebrissource`, `mpmpostfracture`, `mpmdeformpieces`

## Material Presets

| Preset | Use Case | Behavior |
|--------|----------|----------|
| Water | Liquids, splashes | Incompressible fluid, low viscosity |
| Snow | Snowfall, avalanches | Compressible granular, cohesion under compression |
| Sand | Dry granular piles, hourglasses | Non-cohesive granular, friction-dominated |
| Soil | Mudslides, wet terrain | Cohesive granular, moisture-dependent |
| Rubber | Elastic objects, bouncing | Hyperelastic solid, large deformation recovery |
| Metal | Bending, tearing, impact | Elastoplastic solid, permanent deformation past yield |
| Concrete | Fracture, crumbling | Brittle solid, fractures under tension |

## MPM Configure

Sets material properties on source geometry before simulation.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Particle Separation | `particlesep` | scene-dependent | Spacing between particles -- lower = more detail, slower |
| Material Preset | `materialpreset` | Water | Selects stiffness, density, viscosity defaults |
| Stiffness | `stiffness` | preset-dependent | Resistance to deformation -- multiply for stiffer response |
| Density | `density` | preset-dependent | Mass per unit volume |
| Viscosity | `viscosity` | preset-dependent | Internal resistance to flow |
| Friction | `friction` | preset-dependent | Inter-particle friction |

## MPM Source

Emits particles into the solver from configured geometry.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Emission Type | `emissiontype` | Volume | Volume, Surface, or Points |
| Particle Separation Multiplier | `particlesepmult` | 1 | 2 = 1/8 particles (fast iteration), 1 = final quality |
| Compression Hardening | `compressionhardening` | 0 | Small amounts promote tearing over bending (metal) |
| Phase ID | `phaseid` | 0 | Identifies material for multiphase surface tension |

### Source Tips
- Use **Surface** scatter mode for thin-walled objects to avoid wasting particles on interior
- Set particle separation multiplier to 2 during iteration, 1 for final renders
- Compression hardening > 0 on metal sources makes tearing more pronounced than bending

## MPM Collider

Converts collision geometry to SDF for the solver.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Collider Type | `collidertype` | Static | Static, Animated Rigid, or Deforming |
| Friction | `friction` | 1.0 | Surface friction coefficient |
| Stickiness | `stickiness` | 0.0 | Adhesion force on contact |
| Create VDB from Attribute | under Material > Friction | off | Reads per-voxel friction from point attribute |

### Per-Voxel Friction and Stickiness
- Paint friction/stickiness as a **point attribute** on the collider geometry
- MUST be point attribute, not primitive -- averaging during promotion collapses spatial variation
- Use **Cusp SOP** to split shared points before attribute promotion if starting from primitives
- Enable "Create VDB from Attribute" under Material > Friction on MPM Collider
- Values can exceed 100

### Deforming Colliders
- Set type to **Deforming** (not Static or Animated Rigid) for deforming meshes
- "Expand to Cover Velocity" enabled by default in H21
- Dilates the VDB based on collider velocity so the SDF remains valid at all substeps
- High friction/stickiness (100+) needed for adhesion effects

## MPM Solver Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Min Substeps | `minsubsteps` | varies | Minimum solver substeps per frame |
| Max Substeps | `maxsubsteps` | varies | Maximum solver substeps per frame |
| Material Condition | `materialcondition` | varies | Stability threshold -- lower for surface tension |
| Gravity | `gravity` | -9.81 | Gravity magnitude |
| Assume Unchanging Material Properties | `assumeunchanging` | on | DISABLE when emitting stiffer materials mid-sim |

## New H21 Simulation Features

### Surface Tension

Two methods available:

| Method | Pros | Cons |
|--------|------|------|
| Point-based | More stable, predictable | Higher VRAM usage |
| Grid-based | Faster, less VRAM | Less stable at high strength |

- **Strength**: Use 5x+ multiplier over default for visible droplet cohesion
- **Multiphase**: Each MPM Source gets a phase ID; surface tension strength is set per-source pair
- **Stability**: Increase min substeps and decrease material condition to prevent blowups
- **Collider interaction**: Friction/stickiness 100+ needed on colliders to counteract surface-tension levitation

### Auto Sleep

Particles transition between three states:

| State | Value | Behavior |
|-------|-------|----------|
| Active | 1 | Fully simulated |
| Boundary | 2 | Attributes updated but position frozen -- maintains correct interface with active particles |
| Passive/Inactive | 0 | Skipped entirely |

- **Velocity threshold**: Scene-scale dependent -- use 10x default for 100+ meter scenes
- **Delay**: Time before deactivation (0.5s = 12 frames at 24fps)
- **Speedup**: Up to 2x when large portions (90%+) are inactive
- **Staggered activation**: Material starts passive; collision event cascades activation through ~200 substeps

### Continuous Emission

- Enable **Overlapping Emission** to source particles where particles already exist
- **Expansion parameter**: Default 1 is barely visible; use ~25 for practical volume growth
- Works with any material preset

## Post-Simulation Nodes

### MPM Surface

Converts MPM particles to renderable geometry.

| Output Type | Use Case |
|-------------|----------|
| SDF | Collision geometry for secondary sims |
| Density VDB | Volumetric rendering (clouds, fog) |
| Polygon Mesh | Surface rendering |

**Surfacing methods:**
- **VDB from Particle** (CPU): Standard, reliable
- **Neural Point Surface / NPS** (GPU, ONNX-based): Faster, model-dependent quality

| NPS Model | Best For |
|-----------|----------|
| Balanced | General purpose |
| Smooth | Clean surfaces, viscous fluids |
| Liquid | Water, splashes |
| Granular | Sand, soil, snow |

**Filtering pipeline:** Dilation -> Smooth -> Erosion (applied sequentially)

- **Mask smooth**: Protects high-detail regions (min stretch Jp, curvature) from over-smoothing
- **VDB surface mask**: Prune polygons behind colliders to remove hidden faces
- **Chained pattern**: First MPM Surface for SDF + velocity transfer, second for render mesh -- saves farm time by sharing the SDF

### MPM Debris Source

Generates secondary particles from fracturing regions for spray, dust, and debris.

| Parameter | Description |
|-----------|-------------|
| Min Stretching (Jp) | Prune particles below this fracture threshold |
| Min Speed | Prune slow-moving debris |
| Max Distance to Surface | In dx units (auto-scales with particle separation) |
| Replication | Stretching-based and speed-based with ramp remapping |
| Velocity Spread | Distributes along velocity vector, eliminates stepping artifacts |

- Inputs: MPM particles (required), MPM Surface SDF + velocity (recommended)
- Downstream workflow: POP simulation -> density VDB for volumetric render

### MPM Post Fracture

Reverse-fracture workflow: simulate first, then fracture the original geometry along Jp crack lines.

| Parameter | Description |
|-----------|-------------|
| End Frame | Set manually (start frame auto-reads from metadata) |
| Min Stretching | Jp threshold -- controls fracture sensitivity |
| Filler Points | Uniform distribution prevents elongated shards |
| Max Filler Distance | Limits fillers to crack regions |
| Align Fractures to Stretch Points | Essential for metal tearing patterns |
| Cutting Method | Boolean (detailed, preferred) or Voronoi (faster) |

### MPM Deform Pieces

Drives pre-fractured or named geometry with MPM simulation data.

| Retargeting Type | Behavior | Trade-off |
|------------------|----------|-----------|
| Piece-based | Preserves original shape per piece | Visible cracks between pieces |
| Point-based | Smooth deformation, no cracks | Stretching artifacts on large deformation |
| Point and Piece (default) | Blends both modes | Best general-purpose result |

- **Stretch ratio**: Lower value = earlier switch from point to piece mode
- Requires `name` attribute on input geometry
- **No-fracture workflow**: Any geometry with a `name` attribute can be driven by MPM data
- Enable **Close Gaps** to reduce visible cracks in piece-based mode

## Performance Tips

- **Scale up small sims**: Multiply scene scale by 100x, then compensate with time scale x100 and gravity / 100
- **Auto sleep**: Up to 2x speedup when 90%+ particles are passive
- **Particle separation multiplier**: 2 for iteration (1/8 particle count), 1 for final quality
- **Surface scatter**: Use for thin-walled objects to avoid wasting particles on interior volume
- **Narrow-band render clouds**: Erode interior of density VDB to reduce point count by 50%+
- **First-frame OpenCL**: Compilation cost is one-time per session, not per frame
- **Chained MPM Surface**: Share SDF between collision and render passes to save farm time

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Explosion on emission | Assume Unchanging Material Properties ON with mixed stiffness | Disable the toggle |
| Surface tension levitation | Low friction/stickiness on colliders | Set friction/stickiness to 100+ |
| Surface tension instability | Too few substeps or high material condition | Increase min substeps, decrease material condition |
| Elongated shards | No filler points in Post Fracture | Add fillers, reduce spacing |
| Cracks in retargeted mesh | Pure piece-based retargeting | Use Point and Piece mode, enable Close Gaps |
| Color flicker on mesh | Adaptivity > 0 changing topology per frame | Set adaptivity to 0 |
| Poor granular meshing | Wrong NPS model selected | Use Granular model for sand, soil, snow |
| Sim ignores new material | Assume Unchanging enabled mid-emission | Disable before emitting different materials |
