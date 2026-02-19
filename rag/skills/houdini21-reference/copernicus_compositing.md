# Copernicus GPU Compositing (Houdini 21)

## Overview
Copernicus is Houdini 21's new GPU-accelerated compositing framework, replacing legacy COPs for production workflows. It runs inside COPnets but uses a modern node graph with GPU execution.

## Key Differences from Legacy COPs

| Feature | Legacy COPs | Copernicus |
|---------|------------|------------|
| Execution | CPU, per-scanline | GPU (OpenCL/Metal), full-frame |
| Performance | Minutes for 4K | Seconds for 4K |
| Data model | 2D image planes | Multi-layer, arbitrary channels |
| Integration | Standalone /img context | Embedded in SOPs/LOPs via cop2net |
| Color | Limited color management | OCIO-aware, ACES-ready |

## Core Node Categories

### Input/Output

| Node | Description |
|------|-------------|
| `cop:file` | Load EXR/JPEG/PNG sequences |
| `cop:rop_comp` | Write output to disk |
| `cop:karma_render` | Direct Karma render input (no disk round-trip) |

### Compositing Operations

| Node | Description |
|------|-------------|
| `cop:over` | Alpha-over composite |
| `cop:merge` | Multi-input merge with blend modes |
| `cop:premultiply` / `cop:unpremultiply` | Alpha premultiplication |
| `cop:shuffle` | Channel routing and rearrangement |
| `cop:layer_comp` | Beauty rebuild from AOVs |

### Color Correction

| Node | Description |
|------|-------------|
| `cop:grade` | Lift/Gamma/Gain (ASC CDL compatible) |
| `cop:exposure` | Exposure adjustment in stops |
| `cop:saturation` | Saturation control |
| `cop:tonemap` | HDR tonemapping (Reinhard, ACES, custom curve) |
| `cop:lut` | Apply LUT (1D/3D, .cube, .spi1d/.spi3d) |
| `cop:ocio_transform` | OCIO color space transform |

### Utility Passes

| Node | Description |
|------|-------------|
| `cop:crypto_extract` | Extract Cryptomatte selections |
| `cop:depth_effects` | Depth-based fog, DOF, atmospheric |
| `cop:motion_blur` | 2D motion blur from motion vectors |
| `cop:denoise` | OIDN or OptiX denoising |

### Filters

| Node | Description |
|------|-------------|
| `cop:blur` | GPU Gaussian blur |
| `cop:sharpen` | Unsharp mask |
| `cop:glow` | Bloom/glow effect |
| `cop:edge` | Edge detection |

## Production Render Comp Pipeline

### Basic Beauty + Utility Setup

```
file(beauty.exr) --+
file(depth.exr) ---+
file(normal.exr) --+---> layer_comp ---> grade ---> tonemap ---> rop_comp
file(crypto.exr) --+
```

### AOV Rebuild

```
file(direct_diffuse) ---+
file(indirect_diffuse) -+
file(direct_specular) --+---> layer_comp(add) ---> grade ---> rop_comp
file(indirect_specular) +
file(emission) ---------+
file(sss) --------------+
```

### Depth-Based Effects
- Load depth AOV, normalize to [0,1] range
- Depth fog: multiply depth by fog color, blend with beauty
- Depth DOF: use depth to drive per-pixel blur radius
- Atmospheric perspective: lerp beauty toward atmosphere color based on depth

### Cryptomatte Workflow
- Load crypto_material/crypto_object/crypto_asset EXR
- `crypto_extract`: pick mattes by material name, object name, or asset path
- Output: per-selection alpha mask for isolated color correction or replacement

## GPU Memory Notes
- Copernicus holds full frames in GPU VRAM
- 4K EXR with 20 AOVs: ~3-5 GB VRAM
- RTX 4090 (24GB): comfortable for most production comps
- If VRAM exceeded: falls back to CPU (slower but functional)
- Reduce AOV count or resolution for interactive preview

## Tips
- Always work in linear color space; apply display transform (ACES/sRGB) at output only
- Copernicus nodes are OCIO-aware -- set OCIO config via $OCIO env var
- For Karma integration: use `karma_render` input node to avoid disk I/O
- Export as EXR (half-float) for delivery, full-float only for position/depth passes
- Use `layer_comp` for beauty rebuild rather than manual add chains
