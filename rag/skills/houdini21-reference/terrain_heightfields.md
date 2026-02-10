# Terrain and Heightfields

## Overview

Houdini's heightfield system uses 2D volume grids for terrain creation and modification. Each heightfield is a stack of layers: height, mask, sediment, bedrock, etc.

## Basic Terrain Chain

```
heightfield -> heightfield_noise -> heightfield_erode -> heightfield_scatter -> filecache
```

For import to LOPs: `filecache` -> `sopimport` LOP (or convert to poly mesh first)

## Heightfield Creation

### heightfield SOP
Creates the base terrain grid.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Size | `sizex` / `sizey` | 100/100 | Terrain size in units |
| Grid Spacing | `gridspacing` | 1.0 | Resolution per voxel |
| Height | `height` | 0 | Initial height |
| Orientation | `orientation` | XZ | Plane orientation |

### Resolution Guidelines
| Use Case | Grid Spacing | Result |
|----------|-------------|--------|
| Blocking/layout | 5.0 | Fast, rough shape |
| Mid-res preview | 1.0 | Good detail, fast |
| Hero terrain | 0.25-0.5 | High detail, slow ops |
| Close-up ground | 0.1 | Very high detail |

**Memory warning**: `gridspacing=0.1` on a 1000x1000 terrain = 100M voxels. Start coarse.

## Terrain Shaping

### heightfield_noise
Adds procedural noise layers to terrain.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Noise Type | `noisetype` | Perlin | fBm, Perlin, Worley, etc. |
| Height | `height` | 10.0 | Noise amplitude |
| Element Size | `elementsize` | 50.0 | Feature scale |
| Octaves | `octaves` | 8 | Detail layers |
| Roughness | `roughness` | 0.5 | High-frequency detail |
| Offset | `offset` | 0 | Noise offset for variation |

### heightfield_pattern
Geometric patterns for terracing, ridges, canyons.

| Pattern | Description | Use Case |
|---------|-------------|----------|
| Terraces | Flat steps | Rice paddies, mesa |
| Ridges | Parallel ridges | Sand dunes, plowed field |
| Radial | Circular pattern | Crater, volcano |
| Distort | Warp existing terrain | Breaking up regularity |

### heightfield_paint
Manual sculpting with a brush-based interface. Use for art-directed adjustments after procedural generation.

### heightfield_mask
Creates selection masks for targeted operations:
- By slope (steep areas, flat areas)
- By height (above/below threshold)
- By curvature (ridges, valleys)
- By noise (random selection)
- By object (intersection with geometry)

## Erosion

### heightfield_erode
The most important terrain node. Simulates natural erosion processes.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Erosion Mode | `erosionmode` | Hydraulic | Hydraulic, Thermal, or both |
| Iterations | `iterations` | 50 | Simulation length |
| Rain Amount | `rainamount` | 1.0 | Water per iteration |
| Erosion Rate | `eroderate` | 0.5 | Material removal speed |
| Sediment Cap | `sedimentcap` | 0.5 | Max carried sediment |
| Bank Angle | `bankangle` | 30 | Angle for thermal erosion |
| Global Erosion | `globalerosion` | 0.05 | Uniform erosion amount |

### Erosion Types

**Hydraulic Erosion**: Water flows downhill, carving channels.
- Creates realistic river valleys, gullies, drainage patterns
- `rainamount` controls how much water drives erosion
- Higher `iterations` = deeper, more developed channels
- `eroderate` too high = unrealistic deep cuts

**Thermal Erosion**: Material slides down steep slopes.
- Creates talus fans, scree slopes, softened ridges
- `bankangle` is the maximum stable slope angle
- Good for making terrain look weathered and natural

### Erosion Workflow Tips
1. Shape terrain with noise first (big features)
2. Run erosion at low-res (gridspacing=2) to get the flow pattern
3. Refine resolution (gridspacing=0.5) and re-erode for detail
4. Use masks to protect areas from erosion (buildings, roads)

## Terrain Layers

Heightfields maintain multiple named layers:

| Layer | Created By | Description |
|-------|-----------|-------------|
| `height` | heightfield | Main terrain elevation |
| `mask` | heightfield_mask | Selection mask (0-1) |
| `bedrock` | heightfield_erode | Hard rock layer |
| `debris` | heightfield_erode | Loose material |
| `sediment` | heightfield_erode | Deposited sediment |
| `water` | heightfield_erode | Water accumulation |
| `moisture` | custom | Moisture map for vegetation |

### Using Layers for Shading
Erosion layers drive material assignment:
- `height` -> snow line, vegetation zones
- `debris/sediment` -> dirt, gravel material
- `water` -> puddles, wetness
- Slope (from mask by slope) -> cliff vs grass

## Scatter on Terrain

### heightfield_scatter
Distributes points on terrain for vegetation, rocks, etc.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Point Count | `npts` | 1000 | Number of scatter points |
| Density Mask | `densitymask` | mask | Layer controlling density |
| Remove Overlap | `removeoverlap` | 1 | Prevent overlapping instances |
| Scale Range | `scalemin/scalemax` | 0.8/1.2 | Random scale variation |
| Orient to Normal | `orienttonormal` | 1 | Align to terrain surface |

### Scatter Workflow
```
heightfield_erode -> heightfield_mask (by slope < 30) -> heightfield_scatter -> copytopoints
```
1. Create mask for valid placement (not too steep, not underwater)
2. Scatter points on masked area
3. Copy tree/rock geometry to scattered points
4. Points inherit terrain normal for correct orientation

## Converting to Polygon Mesh

### heightfield_convert
Converts heightfield to polygon mesh for rendering.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Convert To | `converto` | Polygon Mesh | Mesh or VDB |
| LOD | `lod` | 1.0 | Level of detail (1=full res) |
| Triangulate | `triangulate` | 1 | Output triangles |

### LOD Pipeline
For large terrains, generate multiple LOD levels:
```
heightfield_convert(lod=1.0) -> filecache (hero)
heightfield_convert(lod=0.25) -> filecache (mid)
heightfield_convert(lod=0.05) -> filecache (far)
```

## Import to Solaris

Two approaches:
1. **Convert first**: `heightfield_convert` -> `filecache` -> `sopimport` LOP (polygon mesh)
2. **Direct heightfield**: `sopimport` LOP pointing to heightfield (Karma renders volumes natively)

For production: always convert to polygon mesh. Heightfield volumes are slower to render.

## Rendering Terrain in Karma

### Material Assignment
- Use slope/height/erosion layers as masks for material blending
- Typical setup: grass (flat), cliff (steep), snow (high), dirt (eroded)
- Transfer layer values to point attributes before sopimport
- Use MaterialX mix nodes to blend between surface materials

### Displacement
- Heightfield -> micro displacement in Karma for close-up detail
- Add rock detail, pebbles, and surface roughness via displacement map
- Keep displacement scale proportional to camera distance

## Performance Tips

- Start at gridspacing=2-5 for layout, refine to 0.5 for hero
- Erosion is O(iterations * grid_area) -- reduce either to speed up
- Use masks to limit erosion to relevant areas
- Cache after erosion (expensive to recompute)
- Convert to polygon mesh for rendering (faster than volume)
- Scatter with LOD: more instances near camera, fewer far away
- Use packed instances for trees/rocks (massive memory savings)

## Common Terrain Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Terrain looks artificial | No erosion | Run hydraulic + thermal erosion (50+ iterations) |
| Erosion too aggressive | Erosion rate too high | Lower `eroderate` to 0.1-0.3, increase iterations instead |
| Flat terrain (no features) | Noise amplitude too low | Increase `height` on heightfield_noise, add multiple octaves |
| Scatter on cliffs | No slope mask | Add heightfield_mask by slope, scatter only on flat areas |
| Memory exhaustion | Grid spacing too fine | Increase `gridspacing`, reduce terrain size |
| Render slow | Rendering heightfield volume | Convert to polygon mesh first |
| Banding artifacts | Too few grid divisions | Decrease `gridspacing` or add displacement in render |
