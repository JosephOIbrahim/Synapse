# Karma AOV and Render Pass Setup

## What are AOVs?
AOV = Arbitrary Output Variable. Extra render passes beyond beauty (RGBA).
Used for compositing: separate diffuse, specular, emission, etc.

## Setting Up AOVs in Karma

### Using Karma Render Properties LOP
1. Create `karmarenderproperties` LOP in /stage
2. In "Image Output" section, add extra image planes
3. Each plane = one AOV

### Common AOV Names (Karma)
| AOV Name | Description |
|----------|-------------|
| `C` or `beauty` | Final combined beauty pass |
| `direct_diffuse` | Direct diffuse illumination |
| `indirect_diffuse` | Indirect (bounced) diffuse |
| `direct_specular` | Direct specular/reflection |
| `indirect_specular` | Indirect specular |
| `direct_emission` | Emissive surfaces |
| `sss` | Subsurface scattering |
| `direct_coat` | Clearcoat direct |
| `albedo` | Surface albedo (base color) |
| `N` | World-space normals |
| `P` | World-space position |
| `Z` or `depth` | Camera depth |
| `motionvector` | 2D motion vectors |
| `crypto_material` | Cryptomatte by material |
| `crypto_object` | Cryptomatte by object |
| `crypto_asset` | Cryptomatte by asset |

## Cryptomatte Setup
Cryptomatte generates ID mattes for compositing selection.
1. Add `crypto_material` and/or `crypto_object` AOV
2. In Nuke/Comp: use Cryptomatte node to select objects by clicking
3. No manual matte creation needed

## Denoising AOVs
Karma XPU supports built-in denoising:
- `denoise_albedo` - Albedo for denoiser guide
- `denoise_normal` - Normal for denoiser guide
- Enable via `karmarenderproperties` "Denoising" section

## Deep Output
Deep compositing preserves per-sample depth:
1. Set output format to `.exr` with deep flag
2. Enable "Deep Output" in render properties
3. Allows depth-correct compositing in Nuke

## Light Groups
Separate AOVs per light or light group:
1. Tag lights with `lightGroup` attribute
2. AOVs auto-generated as `{aov}_{lightgroup}`
3. Enables per-light adjustment in comp

## Render Resolution
- usdrender ROP: `res_user1` (width), `res_user2` (height)
- karma ROP: `resolutionx`, `resolutiony`
- Override: `override_res` = `"specific"` to enable custom resolution

## Compositing Workflow (AOV Rebuild)

In Nuke/comp, rebuild beauty from AOVs:
```
beauty = direct_diffuse + indirect_diffuse + direct_specular + indirect_specular + direct_emission + sss
```
This lets you adjust each lighting contribution independently in post.

## Tips
- Always render `crypto_object` + `crypto_material` for comp flexibility
- Use `N` and `P` passes for relighting and depth effects in comp
- `motionvector` pass enables 2D motion blur in comp (cheaper than 3D)
- For animation: render at least 128 samples with variance oracle for clean AOVs
