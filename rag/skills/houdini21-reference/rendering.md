# Karma Rendering Reference

## ROP Types for /out

| Type Name | Description | Key Parms |
|-----------|-------------|-----------|
| `karma` | Native Karma driver | `picture`, `camera`, `engine` |
| `usdrender` | USD-based render driver | `loppath`, `outputimage`, `override_camera` |
| `ifd` | Mantra renderer | `vm_picture`, `camera` |
| `opengl` | OpenGL flipbook | `picture`, `camera` |

## Karma Engines

| Engine | Parm Value | Speed | Quality | Use Case |
|--------|-----------|-------|---------|----------|
| Karma XPU | `xpu` | Fast (GPU) | Production | Default for all work |
| Karma CPU | `cpu` | Slow | Reference | Volumes, SSS, complex shading |

**When to use CPU over XPU:**
- Nested dielectrics (glass inside liquid)
- Complex SSS (skin with multiple scatter profiles)
- Volume rendering with many scattering events
- When XPU produces fireflies that won't converge

## Karma ROP in /out -- Setup Checklist

1. Create: `hou.node("/out").createNode("usdrender", "render")`
2. Set `loppath` to LOP display node (e.g., `/stage/karma_settings`)
3. Set `renderer` to `BRAY_HdKarma`
4. Set `override_camera` to USD prim path (e.g., `/cameras/render_cam`)
5. Set `override_res` to `"specific"` (string, not int!)
6. Set `res_user1` (width) and `res_user2` (height)
7. Set `outputimage` to output file path

## IMPORTANT: output_file kwarg

`rop.render(output_file=...)` does NOT work for usdrender ROPs.
Must set `outputimage` or `picture` parm directly on the node.

## Karma Render Properties LOP

Create `karmarenderproperties` in /stage for quality control.

### Sample Settings

| Parameter | Name | Default | Production | Preview |
|-----------|------|---------|-----------|---------|
| Max Ray Samples | `karma:global:pathtracedsamples` | 64 | 128-256 | 16-32 |
| Min Ray Samples | `karma:global:minpathtracedsamples` | 1 | 16 | 1 |
| Pixel Oracle | `karma:global:pixeloracle` | `uniform` | `variance` | `uniform` |
| Convergence Threshold | `karma:global:convergencethreshold` | 0.01 | 0.005 | 0.05 |
| Max Diffuse Bounces | `karma:global:diffuselimit` | 2 | 4-6 | 1 |
| Max Specular Bounces | `karma:global:reflectlimit` | 4 | 6-8 | 2 |
| Volume Step Rate | `karma:global:volumesteprate` | 0.25 | 0.5-1.0 | 0.1 |

### Denoising

Karma XPU has built-in OIDN denoiser:
- Enable: `karma:global:enabledenoise` = 1
- Requires: `denoise_albedo` and `denoise_normal` AOVs
- For animation: use temporal denoising to avoid flickering

### Motion Blur

| Parameter | Name | Default |
|-----------|------|---------|
| Enable | `karma:object:xform_motionsamples` | 2 (on) |
| Shutter Open | `karma:global:shutteropen` | -0.25 |
| Shutter Close | `karma:global:shutterclose` | 0.25 |
| Deformation Blur | `karma:object:geo_motionsamples` | 1 (off, set to 2 for on) |

## Camera Path

Camera must be specified as USD prim path: `/cameras/render_cam`
NOT as Houdini node path: `/stage/render_cam`

## Resolution Override

The `override_res` parameter is a STRING MENU:
- `""` -- None (use USD settings)
- `"scale"` -- Percentage of resolution
- `"specific"` -- Specific resolution (enables res_user1/res_user2)

## Karma XPU File Flush

Karma XPU has a 10-15 second delay between render() returning and the
file being fully written to disk. Poll with 0.25s interval for up to 15s.

## Common Render Issues

### Black render
1. Check camera is assigned (`override_camera` is a USD prim path)
2. Check `loppath` points to a valid LOP node with a stage
3. Check lights exist and have exposure > 0
4. Check objects aren't set to `invisible`

### Fireflies (bright pixels)
1. Increase max samples to 256+
2. Enable pixel oracle `variance` mode
3. Lower convergence threshold to 0.001
4. Check for intensity > 1.0 on lights (Lighting Law violation)
5. Check roughness isn't exactly 0.0 (use 0.001 minimum)

### Slow renders
1. Reduce max ray bounces (diffuse=2, specular=4 for preview)
2. Use `variance` pixel oracle (skips converged pixels)
3. Lower resolution for iteration
4. Disable motion blur and DOF for layout
5. Use XPU instead of CPU

### Noisy volumes
1. Increase `volumesteprate` to 0.5-1.0
2. Increase max samples
3. Check volume density isn't too low (invisible but still scattering)

## Output Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| EXR (half) | `.exr` | Production (16-bit float, AOVs) |
| EXR (deep) | `.exr` | Deep compositing |
| JPEG | `.jpg` | Quick preview only |
| PNG | `.png` | Web preview (8-bit, lossless) |
| TIFF | `.tif` | Print / high-bit-depth |

## Render via Synapse

```python
# Quick preview render
render(width=1280, height=720)

# Production render with specific ROP
render(node="/out/karma_final", width=1920, height=1080)

# Check render settings
render_settings(node="/stage/karmarenderproperties1")

# Override samples for preview
render_settings(node="/stage/karmarenderproperties1", settings={
    "karma:global:pathtracedsamples": 32,
    "karma:global:pixeloracle": "variance"
})
```
