# ACES Color Management in Houdini 21

## Overview
ACES (Academy Color Encoding System) provides a standardized color pipeline from texture input through rendering to display output. Houdini 21 supports ACES via OpenColorIO (OCIO) integration.

## OCIO Configuration

### Setting Up ACES
1. Download ACES OCIO config (cg-config-v2.0.0 recommended for VFX)
2. Set environment variable: `OCIO=path/to/config.ocio`
3. Houdini reads `$OCIO` on startup -- applies to all viewers, renderers, and COPs

### Houdini Environment Variable

```bash
# Windows (PowerShell)
setx OCIO "D:\ACES\cg-config-v2.0.0_aces-v1.3_ocio-v2.3.ocio"

# Or in houdini.env:
OCIO = "D:/ACES/cg-config-v2.0.0_aces-v1.3_ocio-v2.3.ocio"
```

### Verify in Houdini
- Edit -> Color Settings -> OpenColorIO should show ACES config
- Viewport: Display Options -> Color Correction -> OpenColorIO
- Select view transform: ACES 1.0 SDR-video or Un-Tone-Mapped

## Key ACES Color Spaces

| Color Space | Use | When |
|-------------|-----|------|
| `ACEScg` | Linear working space | Rendering, compositing, shading |
| `ACES2065-1` | Archival/interchange | File exchange between facilities |
| `sRGB` | Display (monitors) | Texture viewing, web output |
| `Rec.709` | Display (broadcast) | TV/broadcast delivery |
| `Raw` | No transform | Data textures (normal maps, displacement, masks) |
| `ACEScc` | Log working space | Color grading (Nuke, DaVinci) |

## Texture Handling

### Color Textures (Albedo, Diffuse)
- Source typically sRGB or Rec.709
- Must convert to ACEScg for rendering
- In MaterialX: set `colorspace` attribute on image node to `srgb_texture`
- Karma auto-converts based on OCIO roles

### Data Textures (Normal, Roughness, Displacement)
- No color transform -- these are data, not color
- Set to `Raw` in material color space settings
- MaterialX: `colorspace="Raw"` on image nodes
- NEVER apply ACES transform to data textures (breaks normal maps, displacement)

### HDRI Environment Maps
- Typically in linear space already (EXR)
- Set to `scene-linear Rec.709-sRGB` or `ACEScg` depending on source
- Greyscale Gorilla HDRIs: assume linear (set to scene-linear)

## Karma Rendering with ACES

### Render Space
- Karma renders in `ACEScg` (linear) when OCIO is configured
- All shading computations happen in ACEScg
- Output EXR is in ACEScg (no display transform baked in)

### Output Configuration
- Beauty EXR: ACEScg (linear, no transform)
- JPEG preview: apply ACES Output Transform (sRGB) via `iconvert` or Copernicus
- Utility AOVs (depth, normal, motion): Raw (no color transform)

### Display Transform
- Viewport uses ACES view transform for preview
- NEVER bake display transform into EXR output
- Apply view transform at display/delivery only

## Compositing with ACES

### Copernicus / COPs
- Use `cop:ocio_transform` for explicit conversions
- Working space: ACEScg throughout
- Grade/exposure operations in ACEScg (linear math is correct)
- Apply display transform (ACES Output -> sRGB) as final step before write

### Nuke Interop
- EXR from Karma: ACEScg
- Nuke reads as: ACES - ACEScg
- Both tools share same OCIO config = consistent color

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Textures look washed out | sRGB texture not converted to ACEScg | Set texture colorspace to srgb_texture |
| Textures oversaturated | Double conversion (sRGB applied twice) | Check OCIO config, verify single transform |
| Normal maps look wrong | ACES transform applied to data texture | Set to Raw colorspace |
| Viewport too dark/bright | Wrong display transform | Set viewport to ACES 1.0 SDR-video |
| EXR looks flat in viewer | Viewing linear without display transform | Apply ACES view transform in viewer |
| HDRI too bright/dim | Wrong source colorspace assumed | Verify HDRI is linear, set colorspace accordingly |
| Colors don't match between apps | Different OCIO configs | Standardize on one ACES config version |

## Best Practices
- One OCIO config per project, shared across all artists and tools
- Set `$OCIO` globally (not per-app) to ensure consistency
- Always render to EXR in ACEScg -- never bake view transforms
- Tag every texture with its source colorspace (sRGB, Raw, linear)
- Use cg-config-v2.0.0 (latest ACES + OCIO v2 features)
- Test color pipeline end-to-end before starting production: texture -> render -> comp -> display
