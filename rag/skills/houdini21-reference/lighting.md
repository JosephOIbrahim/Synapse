# Lighting in Solaris

## Light Node Types

| LOP Type | USD Type | Use Case |
|----------|----------|----------|
| `domelight` | DomeLight | Environment/HDRI |
| `distantlight` | DistantLight | Sun/directional |
| `rectlight` | RectLight | Area light |
| `disklight` | DiskLight | Disk area light |
| `cylinderlight` | CylinderLight | Tube light |
| `spherelight` | SphereLight | Point light |

## CRITICAL: Parameter Name Encoding

Solaris encodes USD attribute names for use as Houdini parameters.
The encoding is NOT intuitive.

### Light Intensity
- **Correct**: `xn__inputsintensity_i0a`
- **WRONG**: `intensity`, `light_intensity`, `inputs:intensity`

### Light Color
- **Correct**: `xn__inputscolor_kya` (vec3 — set via parmTuple or USD attribute `inputs:color`)

### Light Exposure
- **Correct**: `xn__inputsexposure_vya`
- **Enable control**: `xn__inputsexposure_control_wcb` = `"set"`

### Dome Light Texture
- **Correct**: `xn__inputstexturefile_i1a`

## Rotation

All lights use standard transform parms: `rx`, `ry`, `rz`

## CRITICAL: Lighting Law

**Intensity is ALWAYS 1.0.** Brightness is controlled by **exposure** (logarithmic, in stops).
This applies to ALL PBR renderers: Karma, Arnold, RenderMan, V-Ray.

Each +1 stop of exposure = 2x brighter. Each -1 stop = 0.5x brighter.

### Key:Fill Ratios (exposure math)

| Ratio | Stop Difference | Look |
|-------|----------------|------|
| 2:1 | 1.0 stops | Subtle, broadcast, beauty |
| 3:1 | 1.585 stops (`log2(3)`) | Standard, narrative film |
| 4:1 | 2.0 stops | Dramatic, moody |
| 8:1 | 3.0 stops | Noir, extreme contrast |

Formula: `fill_exposure = key_exposure - log2(ratio)`

## Three-Point Lighting Setup

All lights use `intensity=1.0` (never change this). Brightness via exposure only.

```
Key Light:   distantlight, intensity=1.0, exposure=5.0,  ry=-45, rx=-35
Fill Light:  rectlight,    intensity=1.0, exposure=3.0,  ry=45,  rx=-20    (4:1 ratio, 2 stops below key)
Rim Light:   distantlight, intensity=1.0, exposure=4.5,  ry=180, rx=-30
Environment: domelight,    intensity=1.0, exposure=0.0                     (ambient baseline)
```

### Exposure Presets by Scenario

| Scenario | Key | Fill | Rim | Env | Key:Fill |
|----------|-----|------|-----|-----|----------|
| Product beauty | 4.0 | 3.0 | 3.5 | 1.0 | 2:1 |
| Broadcast/commercial | 5.0 | 3.415 | 4.5 | 1.0 | 3:1 |
| Dramatic narrative | 5.0 | 3.0 | 4.5 | 0.0 | 4:1 |
| Noir / low-key | 5.0 | 2.0 | 5.0 | -1.0 | 8:1 |
| Overcast exterior | 3.0 | 2.5 | -- | 2.0 | 1.5:1 |

### Setting Exposure via Synapse

```python
# SOP-level lights (OBJ context)
set_parm(node="/obj/key_light", parm="light_exposure", value=5.0)

# USD lights (LOP context) — use encoded parm name
set_parm(node="/stage/key_light", parm="xn__inputsexposure_vya", value=5.0)
# Or use the human-readable alias (Synapse resolves it automatically)
set_parm(node="/stage/key_light", parm="exposure", value=5.0)
```

### Common Mistakes

- **WRONG**: `set_parm(parm="intensity", value=5)` — violates Lighting Law
- **RIGHT**: `set_parm(parm="exposure", value=5)` — logarithmic brightness control
- **WRONG**: Using `xn__inputsexposure_fya` — this is an outdated/incorrect encoding
- **RIGHT**: Using `xn__inputsexposure_vya` — verified for Houdini 21 Solaris lights
