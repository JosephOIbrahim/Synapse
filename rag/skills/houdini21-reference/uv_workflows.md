# UV Workflows

## Overview

UV mapping assigns 2D texture coordinates to 3D geometry. Every mesh that receives textures needs UVs. Houdini provides both automatic and manual UV tools in SOPs.

## UV Attribute

- Stored as `v@uv` (vector3 — U, V, W where W is usually 0)
- Can exist on **points** or **vertices** (vertex UVs allow seams)
- Vertex UVs override point UVs at shared points
- Range: typically 0-1 per UV tile (UDIM tiles use integer offsets)

## Basic UV Chain

```
mesh -> uvunwrap (or uvflatten) -> uvlayout -> null
```

## UV Creation Nodes

| Node | Description | Use Case |
|------|-------------|----------|
| `uvunwrap` | Automatic unwrap (angle-based) | Quick UVs for simple shapes |
| `uvflatten` | Manual/interactive unwrap with seam control | Production UV layout |
| `uvproject` | Planar/cylindrical/spherical projection | Specific projection types |
| `uvtransform` | Transform existing UVs (translate/rotate/scale) | Adjusting UV placement |
| `uvlayout` | Pack UV islands efficiently | Final layout step |
| `uvquickshade` | Apply checker texture for UV verification | Debugging UV quality |

## UV Unwrap Methods

### uvunwrap (Automatic)
Best for quick results on organic or non-specific geometry.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Method | `method` | Angle Based | Angle-Based or Conformal |
| Scale | `scale` | 1.0 | UV scale |

### uvflatten (Production)
Interactive unwrap with seam painting. Best for production work.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Seams | `seamgroup` | -- | Edge group defining seam cuts |
| Method | `flattenmethod` | ABF | ABF, LSCM, or SCP |
| Pin Constraints | `pins` | -- | Pinned UV positions |

### UV Flatten Workflow
1. Select edges for seams (use `groupcreate` for edge group)
2. Feed edge group as `seamgroup` to `uvflatten`
3. Flatten minimizes distortion while respecting seams
4. Review with `uvquickshade` checker pattern

### uvproject (Projection)
Direct projection from camera or axis.

| Mode | Description | Use Case |
|------|-------------|----------|
| Planar | Flat projection along axis | Walls, floors |
| Cylindrical | Wrap around cylinder | Bottles, columns |
| Spherical | Wrap around sphere | Globes, eyes |
| Camera | Project from camera | Matte painting projection |

## UV Layout

### uvlayout SOP
Packs UV islands into tiles efficiently.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Scale | `packingscale` | 0 | 0=auto scale, 1=preserve |
| Padding | `padding` | 0.005 | Space between islands |
| Target UDIM | `udimtarget` | 1001 | Starting UDIM tile |
| Axis Align | `axisalign` | 1 | Align islands to axes |
| Rotate | `rotate` | 1 | Allow rotation for better packing |

### UDIM Tiles
For production assets with multiple texture maps:
- UDIM 1001 = U:0-1, V:0-1 (first tile)
- UDIM 1002 = U:1-2, V:0-1 (second tile)
- UDIM 1011 = U:0-1, V:1-2 (row above first)
- Convention: body=1001, head=1002, arms=1003, legs=1004

Enable UDIM in uvlayout: set `udimmode` to "UDIM"

## UV Transfer

### attribtransfer SOP
Transfer UVs from one mesh to another (different topology):
- Source: mesh with good UVs
- Target: mesh needing UVs
- Transfer `uv` attribute (vertex class)
- Works when meshes are close in world space

### uvtransfer SOP
Specialized UV transfer between similar geometry:
- Better than attribtransfer for UV-specific transfer
- Handles seam matching and topology differences

## UV Quality Checks

### uvquickshade
Applies a checker pattern to verify UV quality:
- Uniform checker squares = good UVs (minimal distortion)
- Stretched checkers = UV stretching (bad)
- Compressed checkers = UV compression
- Rotated checkers = UV shearing

### Common UV Problems
| Visual Symptom | Cause | Fix |
|---------------|-------|-----|
| Stretched texture | UV island stretched | Add seams, re-flatten |
| Texture swimming on animation | UVs on points, need vertex UVs | Promote to vertex UVs |
| Seam visible in render | UV seam in visible area | Move seam to hidden area, add padding |
| Overlapping texture | UV islands overlap | Run `uvlayout` with padding |
| Texture too blurry | UV island too small | Increase island scale or add UDIM tiles |

## UV for Specific Workflows

### Characters
1. Plan seams along natural edges (under arms, inside legs, back of head)
2. Separate head, body, hands as distinct UV islands
3. Layout into UDIM tiles (one tile per body part)
4. Use `uvflatten` with painted seam edges for minimal distortion

### Hard Surface / Props
1. `uvproject` planar for flat faces
2. `uvflatten` for curved surfaces
3. Pack all islands with `uvlayout` into single tile or UDIM
4. Align rectangular faces to UV axes for clean texturing

### Terrain
- UVs from heightfield are automatic (grid-aligned)
- For close-up: triplanar projection avoids UV stretching on steep slopes
- Triplanar: project from X, Y, Z axes and blend by normal direction

### Procedural Geometry
- `copytopoints` preserves source UVs on each copy
- For unique UVs per copy: use `uvtransform` with `@copynum` offset
- VDB-based geometry: needs uvproject after conversion (VDB destroys UVs)

## Tips

- Always check UVs with `uvquickshade` before texturing
- Vertex UVs are standard for production (allow seams at shared points)
- Padding in `uvlayout` prevents texture bleeding at mip levels (0.005 minimum)
- For Karma: UVs named `uv` are auto-detected. Other names need explicit binding.
- Transfer UVs early in the pipeline -- topology changes downstream break UVs
