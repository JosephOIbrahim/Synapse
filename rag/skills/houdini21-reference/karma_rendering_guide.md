# Karma Rendering Guide

## Engine Comparison

| Feature | Karma XPU | Karma CPU |
|---------|-----------|-----------|
| Backend | GPU + CPU hybrid | CPU only (multithreaded) |
| Speed | 5-20x faster for most scenes | Baseline |
| Quality | Production quality | Reference quality |
| Volumes | Supported (fast) | Supported (slower) |
| SSS | Supported | Supported (more accurate) |
| Displacement | Supported | Supported |
| Deep output | Supported | Supported |
| Nested dielectrics | Limited | Full support |
| OSL shaders | Not supported | Supported |
| Memory | GPU VRAM limited | System RAM (larger scenes) |
| Best for | Interactive, final for most shots | Complex optical effects, OSL |

**Default choice**: Karma XPU for everything unless you need OSL or nested glass.

## Render Settings Reference

### Resolution & Sampling

| Parameter | Encoded Name | Type | Default | Notes |
|-----------|-------------|------|---------|-------|
| Resolution | `res` | int2 | 1920x1080 | Set on usdrender ROP |
| Pixel samples | `karma:global:pathtracedsamples` | int | 64 | Primary quality control |
| Min samples | `karma:global:minpathtracedsamples` | int | 1 | Early termination floor |
| Convergence mode | `karma:global:convergencemode` | string | "automatic" | "automatic" or "manual" |
| Pixel oracle | `karma:global:pixeloracle` | string | "variance" | "uniform" or "variance" |

### Bounces

| Parameter | Encoded Name | Default | Production | Preview |
|-----------|-------------|---------|------------|---------|
| Diffuse bounces | `karma:global:diffuselimit` | 2 | 4-6 | 1-2 |
| Specular bounces | `karma:global:reflectlimit` | 4 | 6-8 | 2-3 |
| Transmission bounces | `karma:global:refractlimit` | 4 | 6-8 | 2-3 |
| Volume bounces | `karma:global:volumelimit` | 0 | 2-4 | 0-1 |
| SSS bounces | `karma:global:ssslimit` | 0 | 2-4 | 0 |

### Performance

| Parameter | Encoded Name | Notes |
|-----------|-------------|-------|
| Bucket size | `karma:global:bucketsize` | 32-64 for GPU, 16-32 for CPU |
| Russian roulette | `karma:global:russianroulettecutoff` | 0.01 default, lower = more accurate |
| Max ray depth | `karma:global:maxpathdepth` | Total bounce limit across all types |
| Light sampling | `karma:global:lightsamples` | Multiplier on per-light samples |

## Progressive Render Pipeline

Always validate iteratively. Never jump to production settings.

### Stage 1: Layout Check (5 seconds)
```
Resolution: 320x240
Samples: 4
Diffuse bounces: 1
No displacement, no SSS, no volumes
Purpose: Verify composition, camera, basic lighting
```

### Stage 2: Lighting Pass (30 seconds)
```
Resolution: 960x540
Samples: 16-32
Diffuse bounces: 2, Specular: 4
No displacement
Purpose: Evaluate lighting, materials, shadows
```

### Stage 3: Quality Preview (2-5 minutes)
```
Resolution: 1920x1080
Samples: 64
Full bounces
Enable displacement, SSS
Purpose: Near-final quality check
```

### Stage 4: Final Render (production time)
```
Resolution: 1920x1080 (or 4K)
Samples: 128-512
Full bounces, denoiser enabled
All features on
Purpose: Deliverable frame
```

## Denoising

### Intel OIDN (Recommended)

Karma supports built-in denoising via Intel Open Image Denoise:

| Parameter | Encoded Name | Value | Notes |
|-----------|-------------|-------|-------|
| Enable denoiser | `karma:global:denoisemode` | "oidn" | Or "optix" for NVIDIA |
| Albedo AOV | (auto-generated) | — | OIDN uses albedo for edge preservation |
| Normal AOV | (auto-generated) | — | OIDN uses normals for surface detail |

**Setup in Houdini:**
1. On the Karma render settings LOP, set `denoisemode` to "oidn"
2. Karma auto-generates the auxiliary albedo and normal AOVs
3. Denoising runs as a post-process on the rendered frame

### Denoising for Animation

For temporal stability (avoid flickering between frames):
- Use higher base samples (64+) before denoising — denoiser smooths noise but can't fix too-few-samples artifacts
- Enable motion vectors if available
- Consider rendering at higher samples rather than relying heavily on denoiser for hero shots

### When NOT to Denoise
- Debug renders (need to see actual noise levels)
- AOV-only renders (denoise the beauty pass, not utility passes)
- Cryptomatte and ID passes (denoiser corrupts integer data)

## AOVs (Render Passes)

### Standard Beauty AOVs

| AOV | Purpose | Use in Comp |
|-----|---------|-------------|
| `C` (beauty) | Final combined image | Base layer |
| `direct_diffuse` | Direct diffuse lighting | Relighting |
| `indirect_diffuse` | Bounced diffuse | GI control |
| `direct_specular` | Direct specular highlights | Highlight control |
| `indirect_specular` | Reflected light | Reflection control |
| `direct_emission` | Emissive surfaces | Glow effects |
| `sss` | Subsurface scattering | Skin/wax control |
| `direct_volume` | Direct volumetric lighting | Fog/atmosphere |
| `indirect_volume` | Bounced volumetric | Volume fill |

**Beauty rebuild**: `C = direct_diffuse + indirect_diffuse + direct_specular + indirect_specular + direct_emission + sss + direct_volume + indirect_volume`

### Utility AOVs

| AOV | Purpose | Type |
|-----|---------|------|
| `N` (normal) | World-space normals | vector3 |
| `P` (position) | World-space position | point3 |
| `depth` | Camera-space Z depth | float |
| `Albedo` | Surface base color (unlit) | color3 |
| `motionvector` | Per-pixel motion | vector3 |
| `crypto_material` | Cryptomatte by material | float |
| `crypto_object` | Cryptomatte by object | float |
| `crypto_asset` | Cryptomatte by asset | float |

### Deep Output

Deep images store multiple samples per pixel (for compositing volumetrics, transparency):

```
# On usdrender ROP
deep_output = True
deep_image_path = "$HIP/render/deep/shot.$F4.exr"
deep_compression = "zips"  # or "dwaa" for lossy
```

Use deep when: layered transparency, volumetric compositing, holdout mattes.

## Volume Rendering

### Key Settings

| Parameter | Good Default | Notes |
|-----------|-------------|-------|
| Volume step rate | 0.25 | Lower = faster but less accurate. 0.1 for preview, 0.25-0.5 for production |
| Volume shadow step rate | 0.5 | Can be coarser than primary step rate |
| Volume bounces | 2 | 0 for preview, 2-4 for production |
| Max volume depth | 4 | Number of overlapping volume boundaries |

### Performance Tips
- Volumes are expensive: reduce step rate for preview
- Bounding box matters: tight bounds = fewer empty steps
- VDB preferred over dense volumes for sparse data
- Disable volume bounces for first-pass lighting

## Camera Setup

### Essential Parameters

| Parameter | Encoded Name | Notes |
|-----------|-------------|-------|
| Focal length | `focalLength` | 35mm standard, 50mm portrait, 85mm close-up |
| Aperture | `horizontalAperture` | 36.0 for full-frame equivalent |
| Focus distance | `focusDistance` | Distance to in-focus plane (for DOF) |
| F-stop | `fStop` | Lower = more blur. 0 = no DOF |
| Near clip | `clippingRange[0]` | Avoid setting too low (Z-fighting) |
| Far clip | `clippingRange[1]` | Must encompass entire scene |

### Depth of Field

```python
# Enable DOF in Karma
camera_prim = stage.GetPrimAtPath("/World/cameras/render_cam")
camera_prim.GetAttribute("fStop").Set(2.8)        # Shallow DOF
camera_prim.GetAttribute("focusDistance").Set(5.0)  # Focus at 5 units
```

**DOF is per-camera, not a render setting.** Set `fStop > 0` to enable, `fStop = 0` to disable.

### Motion Blur

| Parameter | Setting | Notes |
|-----------|---------|-------|
| `karma:object:geovelblur` | 1 (on) | Deformation motion blur |
| `karma:object:xformsamples` | 2 | Transform blur sample count |
| `karma:object:geosamples` | 2 | Deformation blur sample count |
| Shutter open/close | 0.0 / 1.0 | Centered: -0.5 / 0.5 |

## Light Linking

### Collection-Based Light Linking

In Solaris, light linking uses USD collections:

```python
# Create a collection on the light
from pxr import UsdLux, Usd

light = UsdLux.RectLight.Get(stage, "/World/lights/key_light")
# Include specific geometry
light_api = light.GetPrim()
collection = Usd.CollectionAPI.Apply(light_api, "lightLink")
collection.CreateIncludesRel().SetTargets(["/World/geo/hero"])
# Exclude everything else
collection.CreateExpansionRuleAttr().Set("expandPrims")
```

In Houdini: Use the `Light Linker` LOP to set up per-light visibility without Python.

### Light Groups

Light groups let compositors control individual light contributions:

```
# In Karma render settings
Light group: key    -> /World/lights/key_light
Light group: fill   -> /World/lights/fill_light
Light group: rim    -> /World/lights/rim_light
```

Each group produces a separate AOV: `light_group_key`, `light_group_fill`, etc.

## Common Render Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Black render | No camera, no lights, or empty stage | Check camera assignment, verify lights have exposure > 0 |
| Fireflies | Intensity > 1.0 or roughness = 0.0 | Use exposure for brightness, minimum roughness 0.001 |
| Slow render | Too many bounces or high samples | Lower diffuse to 2, use variance pixel oracle |
| Noisy volumes | Low step rate | Increase volume step rate to 0.25+ |
| Missing geometry | Wrong `purpose` or visibility | Check purpose is "default", visibility is "inherited" |
| Material not showing | Unbound or wrong material path | Verify binding with `UsdShade.MaterialBindingAPI` |
| DOF not working | fStop = 0 | Set fStop > 0 and focusDistance to subject distance |
| Motion blur artifacts | Too few samples | Increase xformsamples/geosamples to 3-4 |

## Render Output Configuration

### On the Karma LOP (Render Settings)
```
picture: $HIP/render/beauty/shot.$F4.exr
```

### On the usdrender ROP
```
outputimage: $HIP/render/beauty/shot.$F4.exr
loppath: /stage/karmasettings  (or last displayed LOP)
```

**Both must agree.** If they differ, the ROP's `outputimage` takes precedence.

### Format Recommendations

| Format | Use Case | Notes |
|--------|----------|-------|
| EXR (half) | Production beauty + AOVs | 16-bit float, good balance |
| EXR (full) | Deep output, position pass | 32-bit float, for precision |
| JPEG | Quick preview | 8-bit, lossy, fast to view |
| PNG | Web/presentation | 8-bit, lossless |

Use `iconvert` from `$HFS/bin/` to convert: `iconvert input.exr output.jpg`
