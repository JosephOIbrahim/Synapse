# Solaris/LOP Parameter Reference

## Light Parameters (ALL light types)

| Parameter | Encoded Name | Type | Description |
|-----------|-------------|------|-------------|
| Intensity | `xn__inputsintensity_i0a` | float | Always 1.0 (Lighting Law) |
| Color | `xn__inputscolor_kya` | vec3 | Light color RGB |
| Exposure | `xn__inputsexposure_vya` | float | Brightness in stops (use this, not intensity) |
| Exposure Control | `xn__inputsexposure_control_wcb` | string | Set to `"set"` to enable exposure |
| Texture File | `xn__inputstexturefile_i1a` | string | HDRI for dome light |
| Enable Color Temp | `xn__inputsenablecolortemperature_r5a` | bool | Use color temperature |
| Color Temperature | `xn__inputscolortemperature_u5a` | float | Kelvin temperature |

## Camera Parameters

| Parameter | Name | Type | Default |
|-----------|------|------|---------|
| Focal Length | `focalLength` | float | 50 |
| F-Stop | `fStop` | float | 5.6 |
| Focus Distance | `focusDistance` | float | 5 |
| Horizontal Aperture | `horizontalAperture` | float | 36 |
| Position | `tx`, `ty`, `tz` | float | 0,0,0 |
| Rotation | `rx`, `ry`, `rz` | float | 0,0,0 |

## MaterialX Standard Surface (mtlxstandard_surface)

| Parameter | Name | Type | Range |
|-----------|------|------|-------|
| Base Color R | `base_colorr` | float | 0-1 |
| Base Color G | `base_colorg` | float | 0-1 |
| Base Color B | `base_colorb` | float | 0-1 |
| Metalness | `metalness` | float | 0-1 |
| Specular Roughness | `specular_roughness` | float | 0-1 |
| Specular | `specular` | float | 0-1 |
| Coat | `coat` | float | 0-1 |
| Emission Color R | `emission_colorr` | float | 0-1 |
| Emission Color G | `emission_colorg` | float | 0-1 |
| Emission Color B | `emission_colorb` | float | 0-1 |
| Opacity | `opacity` | float | 0-1 |

## Edit Node Parameters

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| Prim Pattern | `primpattern` | string | USD prim path pattern |
| Translate | `tx`, `ty`, `tz` | float | Translation |
| Rotate | `rx`, `ry`, `rz` | float | Rotation (degrees) |
| Scale | `sx`, `sy`, `sz` | float | Scale |

## USD Render ROP (in /out)

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| LOP Path | `loppath` | string | Path to LOP display node |
| Renderer | `renderer` | string | BRAY_HdKarma, etc. |
| Override Camera | `override_camera` | string | USD prim path |
| Override Resolution | `override_res` | string | "", "scale", "specific" |
| Width | `res_user1` | int | Override width pixels |
| Height | `res_user2` | int | Override height pixels |
| Output Image | `outputimage` | string | Render output path |

## Karma ROP (in /out)

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| Picture | `picture` | string | Output file path |
| Camera | `camera` | string | USD prim path |
| Engine | `engine` | string | "xpu" or "cpu" |
| Resolution X | `resolutionx` | int | Width pixels |
| Resolution Y | `resolutiony` | int | Height pixels |

## Assign Material

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| Prim Pattern | `primpattern1` | string | Target prim USD path |
| Material Path | `matspecpath1` | string | Material USD path |
