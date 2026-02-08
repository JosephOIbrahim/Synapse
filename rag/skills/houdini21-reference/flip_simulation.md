# FLIP Fluid Simulation

## SOP-Level FLIP Chain

```
source_geo → fluidsource → flipsolver → particlefluidsurface
```

## Source Setup

1. Create source geometry (sphere, box, or custom mesh)
2. `fluidsource` SOP converts to particle field
   - `particle_separation`: 0.05 (smaller = more particles = slower)
   - `scatter_density`: 1.0

## FLIP Solver Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Particle Separation | `particlesep` | 0.05 | Resolution of fluid |
| Grid Scale | `gridscale` | 2.0 | Grid vs particle ratio |
| Substeps | `substeps` | 1 | Min substeps per frame |
| Viscosity | `viscosity` | 0.0 | Fluid thickness (0=water, high=honey) |
| Surface Tension | `surfacetension` | 0.0 | Surface tension force |
| Gravity | `gravity` | -9.81 | Gravity magnitude |
| Collision | collision input | — | Second input for collision geometry |

## Meshing (particlefluidsurface)

Converts FLIP particles to a renderable mesh:

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Particle Separation | `particlesep` | 0.05 | Must match solver |
| Voxel Scale | `voxelscale` | 1.0 | Surface detail |
| Influence Scale | `influencescale` | 2.0 | Particle radius |
| Droplet Scale | `dropletscale` | 0.0 | Small splash particles |

## Import to Solaris

Use `sopimport` LOP with `soppath` pointing to the `particlefluidsurface` node.
For splashes: separate `sopimport` for spray particles.

## Performance Tips

- Start with `particlesep=0.1` for preview, refine to 0.03-0.05 for final
- Enable "Reseeding" for consistent particle density
- Use collision volumes (VDB) for complex obstacles
- FLIP is memory-heavy: 0.02 separation on large domains can exhaust RAM
