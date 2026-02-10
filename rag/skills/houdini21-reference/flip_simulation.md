# FLIP Fluid Simulation

## SOP-Level FLIP Chain

```
source_geo -> fluidsource -> flipsolver -> particlefluidsurface
```

For import to LOPs: `particlefluidsurface` -> `filecache` -> `sopimport` LOP
For splashes: separate `sopimport` for spray/foam particles

## Source Setup

1. Create source geometry (sphere, box, or custom mesh)
2. `fluidsource` SOP converts to particle field
   - `particle_separation`: 0.05 (smaller = more particles = slower)
   - `scatter_density`: 1.0
   - Enable "Initialize Velocity" and set `v@v` for initial motion

### Source Types
- **Fill container**: Single frame emission into a box/mesh volume
- **Continuous emitter**: Emit every frame from animated source
- **Object splash**: Animated collision object entering still water
- **Ocean surface**: Initialize from `oceanspectrum` + `oceanevaluate`

## FLIP Solver Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Particle Separation | `particlesep` | 0.05 | Resolution of fluid |
| Grid Scale | `gridscale` | 2.0 | Grid vs particle ratio |
| Substeps | `substeps` | 1 | Min substeps per frame |
| Viscosity | `viscosity` | 0.0 | Fluid thickness (0=water, high=honey) |
| Surface Tension | `surfacetension` | 0.0 | Surface tension force |
| Gravity | `gravity` | -9.81 | Gravity magnitude |
| Collision | collision input | -- | Second input for collision geometry |
| Reseeding | `reseed` | 1 | Maintain particle density |
| Velocity Transfer | `veltransfer` | FLIP | FLIP, PIC, or blend |

### Viscosity Presets

| Fluid | Viscosity | Surface Tension | Notes |
|-------|-----------|-----------------|-------|
| Water | 0.0 | 0.0 | Default, fast splashes |
| Muddy water | 0.5 | 0.0 | Slightly thick |
| Honey | 50-200 | 0.5 | Very slow, ropey pours |
| Lava | 500-2000 | 0.0 | Extremely thick, slow flow |
| Chocolate | 10-50 | 0.2 | Medium viscosity |
| Blood | 0.5-2.0 | 0.1 | Slightly thicker than water |

### Velocity Transfer Methods
- **FLIP** (default): Low viscosity, splashy. Can be noisy.
- **PIC**: Smooth but over-damped. Good for viscous fluids.
- **Blend** (`picflip`=0.05): Best of both -- 95% FLIP + 5% PIC reduces noise while keeping energy.

### Narrow Band

Enable `narrowband` for large open-surface simulations (rivers, oceans):
- Only simulates particles near the surface
- 5-10x faster for deep water where subsurface detail doesn't matter
- `bandwidth`: Number of voxel layers to simulate (6-10 typical)
- Disable for enclosed volumes (pipes, containers) where all fluid matters

## Collision Setup

### Static Colliders
1. Create collision geometry (mesh or VDB)
2. Connect to solver's second input (collision)
3. Use `staticobject` DOP or `collision_source` SOP

### Animated Colliders
1. `collision_source` SOP with "Deforming" enabled
2. Set `velocity_type` to "Point" for accurate velocity transfer
3. Increase solver `substeps` to 2-4 for fast-moving colliders

### VDB Collisions (preferred)
- `vdbfrompolygons` before collision input -- faster and more stable
- Interior band width: 3-5 voxels
- Exterior band width: 3-5 voxels
- Much more stable than polygon collisions at thin geometries

## Whitewater (Spray, Foam, Bubbles)

Add after FLIP solve for secondary effects:
```
flipsolver -> whitewatersource -> whitewatersolver
```

| Type | Controls | Visual |
|------|----------|--------|
| Spray | `emit_spray` + curvature threshold | Flung droplets |
| Foam | `emit_foam` + velocity threshold | Surface froth |
| Bubbles | `emit_bubbles` + depth threshold | Underwater air |

### Whitewater Source
- `min_speed`: Minimum velocity to emit (2-5 typical)
- `curvature_emit`: Emit from high-curvature areas (wave crests)
- `acceleration_emit`: Emit where fluid rapidly changes direction
- `vorticitymin`: Minimum vorticity for emission

## Meshing (particlefluidsurface)

Converts FLIP particles to a renderable mesh:

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Particle Separation | `particlesep` | 0.05 | Must match solver |
| Voxel Scale | `voxelscale` | 1.0 | Surface detail |
| Influence Scale | `influencescale` | 2.0 | Particle radius for surface |
| Droplet Scale | `dropletscale` | 0.0 | Small splash particles |
| Smoothing | `smoothiter` | 3 | Surface smoothing iterations |
| Dilate/Erode | `dilate` / `erode` | 0/0 | Thicken or thin surface |

### Meshing Tips
- `influencescale` too high = blobby. Too low = holes. Start at 2.0.
- `dropletscale` > 0 renders small splash particles as spheres
- Enable "Transfer Attributes" to pass velocity, vorticity to mesh for shader use
- For final: increase `smoothiter` to 5-8 for cleaner surface

## Caching Strategy

Always cache before meshing or rendering:
```
flipsolver -> filecache(file="$HIP/cache/flip.$F4.bgeo.sc")
```
- Cache particles as `.bgeo.sc` (Blosc compressed)
- Cache mesh separately: `particlefluidsurface -> filecache`
- For re-sim: change filecache to "Read" mode
- Whitewater cached separately from main sim

## Import to Solaris

Use `sopimport` LOP with `soppath` pointing to the `particlefluidsurface` node.
For splashes: separate `sopimport` for spray particles with point rendering.

## Rendering FLIP in Karma

- Meshed fluid: Standard material with high specular, low roughness
- IOR ~1.33 for water, ~1.5 for glass/liquid
- Enable caustics for transparent fluids (expensive)
- Spray particles: Use "render as points" or instance tiny spheres
- Foam: Render as points with opacity falloff by age

## Performance Tips

- Start with `particlesep=0.1` for preview, refine to 0.03-0.05 for final
- Enable "Reseeding" for consistent particle density
- Use VDB collision volumes for complex obstacles
- Enable `narrowband` for open-surface sims (5-10x faster)
- FLIP is memory-heavy: 0.02 separation on large domains can exhaust RAM
- `gridscale=2.0` is optimal for most cases. Lower = slower, marginal gain.
- Cache to SSD if possible -- FLIP writes large files per frame
- Velocity transfer blend (`picflip=0.05`) reduces noise without killing energy

## Common FLIP Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Fluid explodes on frame 1 | Overlapping source and collision | Gap between source and colliders, increase substeps |
| Fluid leaks through walls | Thin collision geometry | Use VDB collisions, increase substeps to 3-4 |
| Blobby surface mesh | `influencescale` too high | Lower to 1.5-2.0, increase smoothing |
| Holes in surface | Not enough particles | Enable reseeding, lower `particlesep` |
| Viscous fluid tears apart | Viscosity too low for motion | Increase viscosity, increase substeps |
| Noise/jitter on surface | FLIP velocity noise | Blend with PIC (`picflip=0.05`), increase smoothing |
| Slow simulation | `particlesep` too small | Start coarse (0.1), use narrow band for open surfaces |
| Memory exhaustion | Domain too large for particle count | Narrow band, reduce domain, increase `particlesep` |
