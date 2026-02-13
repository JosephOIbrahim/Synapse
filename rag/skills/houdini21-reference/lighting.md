# Lighting in Solaris

## Light Node Types

| LOP Type | USD Type | Use Case |
|----------|----------|----------|
| `domelight` | DomeLight | Environment/HDRI |
| `distantlight` | DistantLight | Sun/directional |
| `rectlight` | RectLight | Area light (rectangular) |
| `disklight` | DiskLight | Disk area light |
| `cylinderlight` | CylinderLight | Tube light |
| `spherelight` | SphereLight | Point light (soft) |

## CRITICAL: Lighting Law

**Intensity is ALWAYS 1.0.** Brightness is controlled by **exposure** (logarithmic, in stops).
This applies to ALL PBR renderers: Karma, Arnold, RenderMan, V-Ray.

- **NEVER** set intensity above 1.0. It breaks energy conservation and causes fireflies.
- Each +1 stop of exposure = 2x brighter. Each -1 stop = 0.5x brighter.
- Exposure 0 = baseline (1x multiplier). Exposure 5 = 32x multiplier. Exposure 10 = 1024x.
- The final light contribution = intensity * color * 2^exposure. Since intensity=1.0, it simplifies to color * 2^exposure.

---

## CRITICAL: Parameter Name Encoding

Solaris encodes USD attribute names for use as Houdini parameters.
The encoding is NOT intuitive. Always use the `xn__` encoded names when setting parms directly.

### Complete USD Light Parameter Reference

| USD Attribute | Houdini Encoded Parm | Type | Notes |
|---------------|---------------------|------|-------|
| `inputs:intensity` | `xn__inputsintensity_i0a` | float | ALWAYS 1.0 (Lighting Law) |
| `inputs:color` | `xn__inputscolor_kya` | vec3 | RGB light color, set via parmTuple |
| `inputs:exposure` | `xn__inputsexposure_vya` | float | Brightness in stops (use THIS for brightness) |
| `inputs:exposure` (control) | `xn__inputsexposure_control_wcb` | string | Set to `"set"` to enable exposure override |
| `inputs:diffuse` | `xn__inputsdiffuse_vya` | float | Diffuse multiplier (0-1) |
| `inputs:specular` | `xn__inputsspecular_01a` | float | Specular multiplier (0-1) |
| `inputs:shadow:enable` | `xn__inputsshadowenable_2kb` | bool | Enable/disable shadows |
| `inputs:shadow:color` | `xn__inputsshadowcolor_o5a` | vec3 | Shadow tint color |
| `inputs:enableColorTemperature` | `xn__inputsenablecolortemperature_r5a` | bool | Use Kelvin color temp instead of RGB |
| `inputs:colorTemperature` | `xn__inputscolortemperature_u5a` | float | Color temperature in Kelvin |
| `inputs:normalize` | `xn__inputsnormalize_01a` | bool | Normalize intensity by area |
| `inputs:texture:file` | `xn__inputstexturefile_i1a` | string | HDRI path (DomeLight only) |
| `inputs:texture:format` | `xn__inputstextureformat_r1a` | string | Texture mapping mode |
| `inputs:shaping:cone:angle` | `xn__inputsshapingconeangle_bobja` | float | Spot cone angle in degrees |
| `inputs:shaping:cone:softness` | `xn__inputsshapingconesoftness_brbja` | float | Spot edge softness (0-1) |
| `inputs:shaping:focus` | `xn__inputsshapingfocus_i5a` | float | Focus for barn doors/shaping |

### Common Mistakes with Parameter Names

- **WRONG**: `intensity`, `light_intensity`, `inputs:intensity` -- raw USD names do not work as Houdini parms
- **WRONG**: `xn__inputsexposure_fya` -- outdated/incorrect encoding
- **RIGHT**: `xn__inputsexposure_vya` -- verified for Houdini 21 Solaris lights
- **RIGHT**: Use Synapse aliases (`exposure`, `intensity`, `color`) which resolve automatically

---

## Rotation

All lights use standard transform parms: `rx`, `ry`, `rz` (degrees).
Position uses: `tx`, `ty`, `tz`.
Scale uses: `sx`, `sy`, `sz` (useful for changing area light dimensions).

---

## Key:Fill Ratios (Exposure Math)

| Ratio | Stop Difference | Look |
|-------|----------------|------|
| 1.5:1 | 0.585 stops | Very flat, overcast |
| 2:1 | 1.0 stops | Subtle, broadcast, beauty |
| 3:1 | 1.585 stops (`log2(3)`) | Standard, narrative film |
| 4:1 | 2.0 stops | Dramatic, moody |
| 8:1 | 3.0 stops | Noir, extreme contrast |
| 16:1 | 4.0 stops | Silhouette, extreme low-key |

Formula: `fill_exposure = key_exposure - log2(ratio)`

---

## HDRI / Environment Lighting (DomeLight)

### Basic HDRI Setup

1. Create a `domelight` LOP in `/stage`
2. Set the HDRI texture path: parm `xn__inputstexturefile_i1a`
3. Set intensity to 1.0 (it already defaults to 1.0)
4. Adjust brightness via exposure: parm `xn__inputsexposure_vya`

```python
# Via Synapse
create_node(parent="/stage", type="domelight", name="env_light")
set_parm(node="/stage/env_light", parm="xn__inputstexturefile_i1a",
         value="$HFS/houdini/pic/hdri/HDRIHaven_parking_lot_2k.exr")
set_parm(node="/stage/env_light", parm="xn__inputsexposure_vya", value=0.0)
```

### HDRI Rotation

Rotate the environment map to position the sun or bright spot:
- `ry` controls horizontal rotation (pan the environment)
- `rx` controls vertical tilt
- Common workflow: render a low-res preview, rotate `ry` by 15-30 degree increments to find optimal sun position

```python
# Rotate HDRI to reposition the sun
set_parm(node="/stage/env_light", parm="ry", value=120.0)
```

### Texture Format Modes

The `inputs:texture:format` attribute controls how the HDRI is mapped:
- `automatic` (default) -- auto-detect based on image
- `latlong` -- equirectangular (most common for HDRIs)
- `mirroredBall` -- chrome ball capture
- `angular` -- angular/light probe format

### DomeLight Best Practices

- Use 2K-4K HDRI for preview, 8K+ for production renders
- EXR format preferred (full HDR range, no clipping)
- Start with exposure=0.0 and adjust from there
- When combining HDRI with CG lights, lower the dome exposure by 1-2 stops to avoid overexposure
- Use `inputs:diffuse` and `inputs:specular` multipliers to control HDRI contribution separately for diffuse fill vs. reflections

---

## Three-Point Lighting Setup

All lights use `intensity=1.0` (never change this). Brightness via exposure only.

```
Key Light:   distantlight, intensity=1.0, exposure=5.0,  ry=-45, rx=-35
Fill Light:  rectlight,    intensity=1.0, exposure=3.0,  ry=45,  rx=-20    (4:1 ratio, 2 stops below key)
Rim Light:   distantlight, intensity=1.0, exposure=4.5,  ry=180, rx=-30
Environment: domelight,    intensity=1.0, exposure=0.0                     (ambient baseline)
```

### Exact Parameter Setup for Three-Point Rig

**Key Light (DistantLight)**:
```python
create_node(parent="/stage", type="distantlight", name="key_light")
set_parm(node="/stage/key_light", parm="xn__inputsintensity_i0a", value=1.0)
set_parm(node="/stage/key_light", parm="xn__inputsexposure_vya", value=5.0)
set_parm(node="/stage/key_light", parm="ry", value=-45)
set_parm(node="/stage/key_light", parm="rx", value=-35)
# Optional: warm color temperature
set_parm(node="/stage/key_light", parm="xn__inputsenablecolortemperature_r5a", value=True)
set_parm(node="/stage/key_light", parm="xn__inputscolortemperature_u5a", value=5500)
```

**Fill Light (RectLight)**:
```python
create_node(parent="/stage", type="rectlight", name="fill_light")
set_parm(node="/stage/fill_light", parm="xn__inputsintensity_i0a", value=1.0)
set_parm(node="/stage/fill_light", parm="xn__inputsexposure_vya", value=3.0)
set_parm(node="/stage/fill_light", parm="ry", value=45)
set_parm(node="/stage/fill_light", parm="rx", value=-20)
# Large area = softer shadows
set_parm(node="/stage/fill_light", parm="sx", value=3.0)
set_parm(node="/stage/fill_light", parm="sz", value=3.0)
```

**Rim/Back Light (DistantLight)**:
```python
create_node(parent="/stage", type="distantlight", name="rim_light")
set_parm(node="/stage/rim_light", parm="xn__inputsintensity_i0a", value=1.0)
set_parm(node="/stage/rim_light", parm="xn__inputsexposure_vya", value=4.5)
set_parm(node="/stage/rim_light", parm="ry", value=180)
set_parm(node="/stage/rim_light", parm="rx", value=-30)
```

### Exposure Presets by Scenario

| Scenario | Key | Fill | Rim | Env | Key:Fill |
|----------|-----|------|-----|-----|----------|
| Product beauty | 4.0 | 3.0 | 3.5 | 1.0 | 2:1 |
| Broadcast/commercial | 5.0 | 3.415 | 4.5 | 1.0 | 3:1 |
| Dramatic narrative | 5.0 | 3.0 | 4.5 | 0.0 | 4:1 |
| Noir / low-key | 5.0 | 2.0 | 5.0 | -1.0 | 8:1 |
| Overcast exterior | 3.0 | 2.5 | -- | 2.0 | 1.5:1 |
| Character portrait | 4.0 | 2.415 | 3.5 | 0.5 | 3:1 |

---

## Product / Turntable Lighting

Designed for asset review and product visualization. Even, flattering light with minimal harsh shadows.

### Standard Product Setup

```
Top/Key:     rectlight,    exposure=4.0, rx=-70, ry=0    (directly above, slightly forward)
Side Fill A: rectlight,    exposure=3.0, ry=-90, rx=-15  (camera left)
Side Fill B: rectlight,    exposure=3.0, ry=90,  rx=-15  (camera right, symmetric)
Backdrop:    rectlight,    exposure=2.5, ry=180, rx=-10  (behind, subtle rim)
Environment: domelight,    exposure=1.0                  (ambient fill)
```

### Key Parameters

- Use large RectLights (`sx=5, sz=5`) for soft, wraparound illumination
- Enable `inputs:normalize` so light intensity stays consistent as you resize the area light
- Keep key:fill ratio at 2:1 or less for even coverage
- For turntable animation, lights stay fixed while the asset rotates on a Y-axis animated Xform

---

## Outdoor / Natural Lighting

### Sunlight Setup

```
Sun:         distantlight, exposure=6.0, rx=-45, ry=-30  (high angle, warm)
Sky:         domelight,    exposure=2.0                  (HDRI sky or solid blue fill)
Bounce:      rectlight,    exposure=1.0, rx=80, ry=180   (ground bounce, warm)
```

### Color Temperature Guide for Naturals

| Source | Kelvin | Use |
|--------|--------|-----|
| Candlelight | 1800-2000 | Intimate, warm interior |
| Tungsten/incandescent | 2700-3200 | Indoor warm light |
| Golden hour sun | 3500-4500 | Warm, cinematic outdoor |
| Daylight (noon) | 5500-6500 | Neutral white outdoor |
| Overcast sky | 6500-7500 | Cool, flat outdoor |
| Blue sky (shade) | 8000-10000 | Cool fill in shadows |

To use color temperature instead of RGB:
```python
set_parm(node="/stage/sun_light", parm="xn__inputsenablecolortemperature_r5a", value=True)
set_parm(node="/stage/sun_light", parm="xn__inputscolortemperature_u5a", value=5500)
```

### Time of Day Presets

| Time | Sun rx | Sun Exposure | Sky Exposure | Color Temp |
|------|--------|-------------|-------------|------------|
| Dawn | -5 | 3.0 | 0.5 | 3000 |
| Morning | -25 | 5.0 | 1.5 | 4500 |
| Noon | -80 | 6.0 | 2.0 | 6000 |
| Golden hour | -10 | 4.0 | 1.0 | 3500 |
| Dusk | -3 | 2.0 | 0.0 | 2500 |
| Moonlight | -30 | 0.0 | -2.0 | 8000 |

---

## Interior Lighting with Portals

### Portal Lights for Window Illumination

Portal lights help Karma sample outdoor light entering through windows more efficiently. Without portals, light through small windows causes heavy noise.

1. Place a `rectlight` at each window opening, sized to match the window
2. Set the rect light exposure to match the dome/sun
3. In Karma render properties, enable portal sampling

### Interior Lighting Setup

```
Window Portal: rectlight,    exposure=4.0, sized to window, facing inward
Practical A:   spherelight,  exposure=2.0, tx=lamp_pos  (table lamp)
Practical B:   spherelight,  exposure=1.5                (accent lamp)
Ambient:       domelight,    exposure=-1.0               (very low, just enough to prevent pure black)
```

### Tips for Interiors

- Use RectLights as practical stand-ins for ceiling fixtures (LED panels, fluorescent)
- CylinderLights work well for tube fluorescent fixtures
- Keep ambient dome very low (exposure -1 to 0) to maintain contrast
- Place SphereLight sources inside lamp geometry for realism
- Use warm color temperatures (2700-3200K) for residential interiors, cooler (4000-5000K) for offices

---

## Light Linking and Light Categories

Light linking controls which lights illuminate which objects. In USD/Solaris, this is done through collection-based light linking.

### Setting Up Light Categories

1. On the light LOP, use the `lightcategories` parameter to assign category tags
2. On geometry, use `lightcategories` to specify which light categories affect it
3. Categories are string tokens separated by spaces

### Collection-Based Linking (USD)

In USD, light linking uses collections on the light prim:
- `collection:lightLink:includeRoot` -- whether to include all geometry by default
- `collection:lightLink:includes` -- explicit list of geometry to illuminate
- `collection:lightLink:excludes` -- explicit list of geometry to exclude

### Via Python in LOPs

```python
# Create a light link edit
edit_node = stage_node.createNode("lightlinker", "link_key_to_hero")
# Configure which lights affect which geometry
# Light: /lights/key_light
# Geometry: /World/hero_character
```

---

## Shadow Controls

### Shadow Parameters

| Parameter | Encoded Name | Type | Notes |
|-----------|-------------|------|-------|
| Shadow Enable | `xn__inputsshadowenable_2kb` | bool | Toggle shadows on/off |
| Shadow Color | `xn__inputsshadowcolor_o5a` | vec3 | Default black (0,0,0). Tint for colored shadows |

### Shadow Quality (Karma Render Properties)

Shadow quality is controlled at the render level, not per-light:

| Parameter | Karma Parm | Default | Notes |
|-----------|-----------|---------|-------|
| Shadow bias | `karma:light:shadowbias` | 0.01 | Prevents self-shadowing artifacts |

### Shadow Softness

Shadow softness is determined by the physical size of the light source, not a separate "softness" parameter. This is physically-based behavior:
- **Larger area light** (bigger sx/sz on RectLight) = softer shadows
- **Smaller area light** = sharper shadows
- **DistantLight** angle parameter controls sun disk size, affecting shadow softness
- **SphereLight** radius controls softness

```python
# Soft shadows: make the light source large
set_parm(node="/stage/fill_light", parm="sx", value=5.0)
set_parm(node="/stage/fill_light", parm="sz", value=5.0)

# Sharp shadows: use small or distant light
set_parm(node="/stage/key_light", parm="sx", value=0.1)
```

### Disabling Shadows for Fill

Fill lights often look better without shadows to avoid double-shadow artifacts:
```python
set_parm(node="/stage/fill_light", parm="xn__inputsshadowenable_2kb", value=False)
```

---

## Light Shaping, Filters, and Barn Doors

### Spot Light Shaping (Cone)

Any light can be shaped into a spot using shaping attributes:

| Parameter | Encoded Name | Type | Notes |
|-----------|-------------|------|-------|
| Cone Angle | `xn__inputsshapingconeangle_bobja` | float | Full cone angle in degrees |
| Cone Softness | `xn__inputsshapingconesoftness_brbja` | float | Edge falloff (0=hard, 1=soft) |
| Focus | `xn__inputsshapingfocus_i5a` | float | Focus intensity toward center |

```python
# Turn a sphere light into a spot light
set_parm(node="/stage/spot", parm="xn__inputsshapingconeangle_bobja", value=30.0)
set_parm(node="/stage/spot", parm="xn__inputsshapingconesoftness_brbja", value=0.5)
```

### Barn Doors (via Light Filters)

Barn doors crop the light beam on four sides. In Karma, barn doors are implemented via light filter prims:

1. Create a `BarnDoorLight` filter prim as a child of the light
2. Set the four edge parameters (top, bottom, left, right) to control cropping
3. Edge softness parameters control the falloff at each edge

### IES Profiles

For realistic architectural lighting, use IES light distribution profiles:
- Set the `inputs:shaping:ies:file` attribute to the IES file path
- IES profiles define the angular light distribution measured from real luminaires
- Combine with SphereLight or DiskLight for realistic fixtures

---

## Diffuse and Specular Contribution

Each light can independently control its diffuse and specular contributions:

```python
# Light that only produces specular highlights (no diffuse shading)
set_parm(node="/stage/spec_only", parm="xn__inputsdiffuse_vya", value=0.0)
set_parm(node="/stage/spec_only", parm="xn__inputsspecular_01a", value=1.0)

# Light that only fills diffuse (no specular highlights)
set_parm(node="/stage/diff_fill", parm="xn__inputsdiffuse_vya", value=1.0)
set_parm(node="/stage/diff_fill", parm="xn__inputsspecular_01a", value=0.0)
```

This is useful for:
- Adding specular-only accent lights for eye highlights
- Diffuse-only fill to lift shadows without adding unwanted reflections
- Art-directing each light's contribution independently

---

## Light Visibility

### Camera Visibility

By default, area lights (RectLight, DiskLight, SphereLight, CylinderLight) are visible to the camera as bright shapes. The DomeLight is visible as the background.

To hide a light from the camera while keeping its illumination:
- Use `primvars:karma:object:visibility` on the light prim
- Or set the light's `purpose` to `guide` (visible in viewport, invisible in render)

### Viewport Display

In the Solaris viewport (Scene Viewer):
- Lights appear as wireframe icons at their position
- DomeLight shows as a sphere indicator
- Area lights show their shape and direction
- Enable **Display Options > Lighting > Use All Scene Lights** to see full lighting in the viewport
- The viewport uses GL approximations -- always render a test frame for accurate results

---

## Iterating on Lighting

### Progressive Render Workflow

1. **Viewport preview**: Use Karma viewport renderer (Hydra Storm or Karma CPU) for interactive feedback
2. **Low-res test**: Render 320x240, 4-8 samples to check basic exposure and color balance
3. **Mid-res check**: Render 960x540, 32 samples to evaluate shadows and composition
4. **Final quality**: Render at production resolution with full samples

### Fast Iteration Tips

- Use Karma XPU for GPU-accelerated renders (10-50x faster than CPU for most scenes)
- Disable motion blur and DOF during lighting iteration
- Use `variance` pixel oracle to skip converged pixels
- Set convergence threshold to 0.05 for fast preview, 0.005 for final
- Render a single frame before committing to a sequence
- Use viewport capture (`capture_viewport`) for instant feedback without rendering

### Exposure Adjustment Workflow

When adjusting overall scene brightness:
1. Set key light exposure first -- this anchors everything
2. Adjust fill relative to key using ratio math
3. Set rim exposure by eye (typically 0.5-1.0 stops below key)
4. Adjust dome exposure last to control ambient level
5. Never touch intensity -- always use exposure

---

## Setting Exposure via Synapse

```python
# SOP-level lights (OBJ context)
set_parm(node="/obj/key_light", parm="light_exposure", value=5.0)

# USD lights (LOP context) -- use encoded parm name
set_parm(node="/stage/key_light", parm="xn__inputsexposure_vya", value=5.0)
# Or use the human-readable alias (Synapse resolves it automatically)
set_parm(node="/stage/key_light", parm="exposure", value=5.0)
```

---

## Common Gotchas

### Lighting Law Violations

- **WRONG**: `set_parm(parm="intensity", value=5)` -- violates Lighting Law, causes fireflies and blown highlights
- **RIGHT**: `set_parm(parm="exposure", value=5)` -- logarithmic brightness control
- **WRONG**: Using `xn__inputsexposure_fya` -- this is an outdated/incorrect encoding
- **RIGHT**: Using `xn__inputsexposure_vya` -- verified for Houdini 21 Solaris lights

### Exposure Misunderstandings

- Exposure is LOGARITHMIC. Exposure 10 is not "twice as bright" as exposure 5. It is 32x brighter (2^5).
- Negative exposure is valid. Exposure -2 means 1/4 brightness (useful for very subtle fill or moonlight).
- Exposure 0 does NOT mean "off". It means 1x multiplier (intensity * 1). Use shadow:enable=False to turn a light off.

### Area Light Normalization

- When `inputs:normalize` is ON, resizing an area light does NOT change its total energy output (just softens shadows)
- When `inputs:normalize` is OFF (default for some types), making a light bigger also makes it brighter
- For consistent behavior, enable normalize on area lights: `xn__inputsnormalize_01a = True`

### DomeLight Pitfalls

- A DomeLight with no texture file produces a uniform white environment
- HDRI must be in a format Karma can read (EXR, HDR, TIFF). JPEG/PNG work but clip at 1.0 (no HDR range)
- Rotating the DomeLight rotates the ENTIRE environment including reflections
- Two DomeLights will double the ambient level -- typically you only want one
- DomeLight is always infinitely far away; position (`tx/ty/tz`) has no effect, only rotation matters

### Shadow Issues

- If shadows look blocky or have acne, increase shadow bias or make the light source larger
- Fill lights should generally have shadows disabled to avoid confusing double shadows
- DistantLight with angle=0 produces perfectly sharp shadows (may look CG-ish); increase angle for realism

### Light Not Appearing in Render

1. Check the light is connected in the LOP graph (wired into the merge before render properties)
2. Check the light prim is active (`active=True`)
3. Check exposure is not extremely negative (e.g., exposure=-20 is effectively invisible)
4. Check `inputs:diffuse` and `inputs:specular` are not both 0
5. Check light linking is not excluding the geometry
