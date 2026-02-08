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
- **Correct**: `xn__inputscolor_zya` (but this is a vec3 — set via parmTuple)
- Individual: set via USD attribute `inputs:color`

### Light Exposure
- **Correct**: `xn__inputsexposure_fya`

### Dome Light Texture
- **Correct**: `xn__inputstexturefile_i1a`

## Rotation

All lights use standard transform parms: `rx`, `ry`, `rz`

## Three-Point Lighting Setup

```
Key Light:   distantlight, intensity=3-5, ry=-45, rx=-35
Fill Light:  rectlight or distant, intensity=1-2, ry=45, rx=-20
Rim Light:   distantlight, intensity=2-3, ry=180, rx=-30
Environment: domelight, intensity=0.5-1.0
```
