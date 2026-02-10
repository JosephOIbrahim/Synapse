# Vellum Simulation

## Overview

Vellum is Houdini's unified solver for cloth, hair, grain, soft body, and balloon simulations. It runs in SOPs (not DOPs), making it faster to iterate than traditional DOP setups.

## SOP-Level Vellum Chain

```
source_geo -> vellumconfigure* -> vellumdrape (optional) -> vellumsolver -> null (output)
```

For import to LOPs: `vellumsolver` -> `filecache` -> `sopimport` LOP

## Configure Nodes

Vellum uses `vellumconfigure*` SOPs to define simulation behavior:

| Node | Description | Use Case |
|------|-------------|----------|
| `vellumconstraints` | Generic constraint setup | Custom configurations |
| `vellumcloth` | Cloth + constraints | Fabric, flags, curtains |
| `vellumhair` | Hair/fur curves + constraints | Hair, fur, cables, ropes |
| `vellumgrains` | Grain particles + constraints | Sand, snow, sugar, pebbles |
| `vellumsoftbody` | Tet mesh + constraints | Jelly, muscle, rubber |
| `vellumballoon` | Inflatable mesh + constraints | Balloons, airbags |
| `vellumstruts` | Strut constraints between points | Rigid structures, bridges |

### Output Convention
All configure nodes have TWO outputs:
- **Output 1**: Geometry (the mesh/curves/points)
- **Output 2**: Constraints (the constraint geometry)

Both must be connected to the `vellumsolver`:
- Solver **Input 1**: Geometry
- Solver **Input 3**: Constraints

## Cloth Setup

### Basic Cloth
```
grid -> vellumcloth -> vellumsolver
```

### Key Parameters (vellumcloth)

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Stretch Stiffness | `stretchstiffness` | 10000 | Resistance to stretching |
| Bend Stiffness | `bendstiffness` | 0.001 | Resistance to bending |
| Compression Stiffness | `compressionstiffness` | 10 | Resistance to compression |
| Thickness | `thickness` | 0.01 | Collision thickness |
| Density | `density` | 0.1 | Mass per area |
| Damping | `dampingratio` | 0.01 | Motion damping |

### Cloth Material Presets

| Fabric | Stretch | Bend | Density | Notes |
|--------|---------|------|---------|-------|
| Silk | 5000 | 0.0001 | 0.05 | Very light, flowing |
| Cotton T-shirt | 10000 | 0.001 | 0.1 | Default feel |
| Denim | 50000 | 0.1 | 0.3 | Heavy, stiff |
| Leather | 100000 | 1.0 | 0.5 | Very stiff, thick |
| Flag/banner | 8000 | 0.0005 | 0.08 | Light, responsive |
| Rubber sheet | 5000 | 0.01 | 0.4 | Stretchy, heavy |
| Chiffon/veil | 3000 | 0.00001 | 0.02 | Ultra-light, delicate |

### Draping

For garments that need to settle onto a body before animation:
```
tshirt_geo -> vellumcloth -> vellumdrape -> vellumsolver
```
- `vellumdrape` pre-simulates the cloth settling onto the collision body
- Set `frames` to 50-100 for complex garments
- Outputs the "rest" position that the actual simulation starts from

## Hair Setup

### Basic Hair
```
curves -> vellumhair -> vellumsolver
```

### Key Parameters (vellumhair)

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Stretch Stiffness | `stretchstiffness` | 10000 | Along-curve stretch |
| Bend Stiffness | `bendstiffness` | 0.1 | Bending resistance |
| Width | `width` | 0.01 | Hair strand width |
| Density | `density` | 1.0 | Mass per length |

### Hair Tips
- Generate guide curves first, sim guides, then interpolate dense hair for render
- Pin root points to animated character mesh using `vellumconstraintproperty` with Pin type
- Use `vellumpostprocess` to smooth results and add clumping
- For long flowing hair: lower bend stiffness (0.01), increase substeps
- For short stiff hair: higher bend stiffness (1.0+)

## Grain Setup

### Basic Grains
```
source_geo -> vellumgrains -> vellumsolver
```

### Key Parameters (vellumgrains)

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Particle Size | `pscale` | 0.05 | Grain radius |
| Friction | `friction` | 0.5 | Inter-grain friction |
| Density | `density` | 1.0 | Mass per grain |
| Cluster Stiffness | `clusterstiffness` | 1.0 | Stiffness of clusters |

### Grain Material Presets

| Material | Friction | Cluster | Notes |
|----------|----------|---------|-------|
| Dry sand | 0.5 | 0.0 | Free-flowing |
| Wet sand | 0.8 | 0.5 | Clumps together |
| Snow | 0.3 | 0.8 | Packs and holds shape |
| Gravel | 0.7 | 0.0 | Rolling, non-sticky |
| Sugar/salt | 0.2 | 0.0 | Very free-flowing |

## Soft Body Setup

### Basic Soft Body
```
mesh -> remesh (uniform tets) -> vellumsoftbody -> vellumsolver
```

### Key Parameters (vellumsoftbody)

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Shape Stiffness | `shapestiffness` | 1.0 | Resistance to deformation |
| Volume Stiffness | `volumestiffness` | 0.0 | Resistance to volume change |
| Damping | `dampingratio` | 0.1 | Motion damping |

**Important**: Input mesh MUST be tetrahedral. Use `remesh` or `solidconform` to create tet mesh first.

## Vellum Solver Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Substeps | `substeps` | 5 | Solver accuracy (5-10 for cloth, 1-3 for grains) |
| Constraint Iterations | `constraintiterations` | 100 | Convergence iterations |
| Time Scale | `timescale` | 1.0 | Simulation speed |
| Gravity | `gravity` | -9.81 | Gravity magnitude |
| Ground Plane | `groundplane` | 1 | Enable implicit ground |
| Ground Position | `groundpos` | 0 | Ground height |
| Friction | `friction` | 0.5 | Ground friction |

### Substep Guidelines
| Simulation Type | Substeps | Iterations |
|----------------|----------|------------|
| Cloth (normal) | 5 | 100 |
| Cloth (fast motion) | 10-20 | 150 |
| Hair | 3-5 | 80 |
| Grains | 1-3 | 50 |
| Soft body | 5 | 100 |

## Collision Setup

### Self-Collision
Enable via `selfcollisions` parm on configure node. Essential for cloth folding.
Increases solve time 2-5x. Disable during early iterations.

### External Colliders
```
animated_body -> vellumcollider -> vellumsolver (input 2 = collider)
```
- `vellumcollider` SOP prepares collision geometry
- Input animated/deforming mesh with velocity (`trail` SOP for `v@v`)
- Set `thickness` to match cloth thickness for stable collisions

### Collision Tips
- Use simplified collision meshes (polyreduce) for faster solving
- Enable "Compute Missing Normals" on collider for open meshes
- For tight-fitting garments: increase substeps to 15-20
- If cloth passes through: decrease cloth `thickness`, increase `substeps`

## Pinning and Constraints

### Pin to Animated Geometry
```vex
// In a wrangle before configure node:
// Pin top edge of cloth to animated character
if (@P.y > ch("pin_height")) i@stopped = 1;
```

Or use `vellumconstraintproperty`:
- Set constraint type to "Pin"
- Use group to select pinned points
- Enable "Match Animation" to follow animated geometry

### Constraint Types
| Type | Description | Use Case |
|------|-------------|----------|
| Distance | Maintain distance between points | Stretch resistance |
| Bend | Maintain angle between edges | Bending resistance |
| Pin | Fix points to position/animation | Attachment points |
| Attach to Geometry | Bind to animated mesh | Garment on character |
| Weld | Fuse two surfaces | Seams, stitching |
| Stitch | Soft connection between surfaces | Layered cloth |
| Pressure | Internal pressure | Balloons, inflatable |

## Caching Strategy

Always cache Vellum before rendering:
```
vellumsolver -> filecache(file="$HIP/cache/vellum.$F4.bgeo.sc")
```
- Cache constraints too if needed for debugging: second filecache on constraint output
- For character FX: cache vellum separately from character animation
- Use `.bgeo.sc` (Blosc compressed) for fastest read/write

## Import to Solaris

Use `sopimport` LOP with `soppath` pointing to the `vellumsolver` output (or filecache in Read mode).

For cloth on character: merge vellum sopimport with character sopimport in LOPs, then assign material.

## Rendering Vellum in Karma

### Cloth
- Apply woven fabric material (base_color from texture, roughness 0.3-0.7)
- Enable displacement for fabric weave detail
- Subdivision in render: 1-2 levels for smooth silhouettes

### Hair
- Use hair shader (mtlxstandard_surface with `thin_walled=1`)
- Set curve rendering: "Round" cross-section
- Melanin-based color or direct color attribute from `v@Cd`

### Grains
- Render as spheres (point instancing) or use `particlefluidsurface` for meshing
- For sand: matte material with roughness 0.8-1.0, subtle color variation via `v@Cd`

## Performance Tips

- Start with low-res mesh for cloth (500-2000 polys), refine after blocking
- Disable self-collision during early iterations
- Use simplified collision meshes (polyreduce the body)
- Lower constraint iterations (50) for previewing, increase (150+) for final
- Cache frequently -- Vellum iteration is fastest with cached inputs
- For grains: use larger `pscale` for preview, reduce for final detail
- `vellumdrape` is expensive -- only re-drape when starting pose changes

## Common Vellum Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Cloth falls through body | Thickness too thin or substeps too low | Increase `thickness`, increase `substeps` to 15+ |
| Cloth explodes | Extremely high stiffness with few substeps | Lower stiffness or increase substeps/iterations |
| Stretchy cloth (shouldn't be) | Stretch stiffness too low | Increase `stretchstiffness` to 50000+ |
| Hair goes through body | Missing or bad collision setup | Add `vellumcollider`, increase substeps |
| Grains pile too high | Friction too high | Lower `friction` to 0.3-0.5 |
| Soft body collapses | Shape stiffness too low | Increase `shapestiffness`, add volume constraint |
| Slow simulation | Too many points + self-collision | Simplify mesh, disable self-collision for preview |
| Jittery result | Insufficient iterations | Increase `constraintiterations` to 150+ |
| Garment doesn't fit | No drape step | Add `vellumdrape` before solver |
