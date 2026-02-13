# MaterialX Shaders in Solaris

## Standard Surface Overview

MaterialX Standard Surface is the default PBR shader in Karma. It covers
metal, plastic, glass, skin, fabric, and most real-world materials.

### Input Groups

| Group | Key Inputs | Range | Notes |
|-------|-----------|-------|-------|
| **Base** | base, base_color | 0-1, color3 | Diffuse reflection weight and color |
| **Specular** | specular, specular_color, specular_roughness, specular_IOR | 0-1, color3, 0-1, 1.0-3.0 | GGX microfacet reflection |
| **Metalness** | metalness | 0-1 | 0 = dielectric, 1 = metal. Lerps base into specular |
| **Transmission** | transmission, transmission_color, transmission_depth | 0-1, color3, float | Glass/liquid transparency |
| **SSS** | subsurface, subsurface_color, subsurface_radius, subsurface_scale | 0-1, color3, color3, float | Skin, wax, marble |
| **Emission** | emission, emission_color | 0+, color3 | Self-illumination |
| **Coat** | coat, coat_color, coat_roughness | 0-1, color3, 0-1 | Clear coat layer (car paint, lacquer) |
| **Sheen** | sheen, sheen_color, sheen_roughness | 0-1, color3, 0-1 | Fabric/velvet edge reflection |
| **Thin Film** | thin_film_thickness, thin_film_IOR | float, float | Iridescence (soap bubbles, oil) |
| **Normal** | normal | normal3 | Tangent-space normal map |
| **Opacity** | opacity | color3 | Per-channel alpha cutout |

### Parameter Encoded Names (Houdini/USD)

In Houdini LOPs, MaterialX inputs use encoded names:

| Friendly Name | Encoded Parm Name | Type |
|---------------|-------------------|------|
| Base Color | `basecolor` | color3 |
| Base Weight | `base` | float |
| Metalness | `metalness` | float |
| Specular Weight | `specular` | float |
| Specular Roughness | `specular_roughness` | float |
| Specular IOR | `specular_IOR` | float |
| Specular Color | `specular_color` | color3 |
| Coat Weight | `coat` | float |
| Coat Roughness | `coat_roughness` | float |
| Coat Color | `coat_color` | color3 |
| Emission Weight | `emission` | float |
| Emission Color | `emission_color` | color3 |
| Transmission Weight | `transmission` | float |
| Transmission Color | `transmission_color` | color3 |
| Subsurface Weight | `subsurface` | float |
| Subsurface Color | `subsurface_color` | color3 |
| Subsurface Scale | `subsurface_scale` | float |
| Sheen Weight | `sheen` | float |
| Sheen Roughness | `sheen_roughness` | float |
| Normal Map | `normal` | vector3 |
| Opacity | `opacity` | color3 |

## Material Presets

### Brushed Metal
```
base_color: (0.9, 0.9, 0.9)
metalness: 1.0
specular_roughness: 0.25
specular_IOR: 2.5
```
For anisotropic brushed metal, add `specular_anisotropy: 0.8`.

### Polished Chrome
```
base_color: (0.95, 0.95, 0.95)
metalness: 1.0
specular_roughness: 0.02
specular_IOR: 2.5
```

### Matte Plastic
```
base_color: (desired color)
metalness: 0.0
specular_roughness: 0.4
specular_IOR: 1.5
```

### Glossy Plastic
```
base_color: (desired color)
metalness: 0.0
specular_roughness: 0.05
specular_IOR: 1.5
coat: 0.5
coat_roughness: 0.02
```

### Clear Glass
```
base_color: (1, 1, 1)
metalness: 0.0
specular_roughness: 0.0
specular_IOR: 1.5
transmission: 1.0
transmission_color: (1, 1, 1)
```

### Frosted Glass
```
base_color: (1, 1, 1)
metalness: 0.0
specular_roughness: 0.3
specular_IOR: 1.5
transmission: 1.0
transmission_color: (0.95, 0.97, 1.0)
```

### Skin (SSS)
```
base_color: (0.8, 0.5, 0.4)
metalness: 0.0
specular_roughness: 0.35
subsurface: 0.6
subsurface_color: (0.9, 0.3, 0.2)
subsurface_radius: (1.0, 0.35, 0.15)
subsurface_scale: 0.05
```

### Marble
```
base_color: (0.95, 0.93, 0.9)
metalness: 0.0
specular_roughness: 0.1
subsurface: 0.4
subsurface_color: (0.85, 0.82, 0.78)
subsurface_scale: 0.1
```

### Fabric/Velvet
```
base_color: (desired color)
metalness: 0.0
specular_roughness: 0.8
sheen: 0.8
sheen_color: (lighter tint of base)
sheen_roughness: 0.3
```

### Car Paint
```
base_color: (desired color)
metalness: 0.5
specular_roughness: 0.15
coat: 1.0
coat_color: (1, 1, 1)
coat_roughness: 0.02
```

## Texture Maps

### Standard PBR Texture Set

| Map | Connects To | Color Space | Notes |
|-----|-------------|-------------|-------|
| Diffuse/Albedo | base_color | sRGB | The base color map |
| Roughness | specular_roughness | Raw/Linear | White = rough, black = smooth |
| Metalness | metalness | Raw/Linear | White = metal, black = dielectric |
| Normal | normal | Raw/Linear | Tangent-space (OpenGL or DirectX) |
| Displacement | displacement | Raw/Linear | Height map for surface detail |
| AO (Ambient Occlusion) | base_color (multiply) | Raw/Linear | Bake-only, multiply with diffuse |
| Opacity | opacity | Raw/Linear | Alpha cutout |
| Emission | emission_color | sRGB | Emissive areas |

### UDIM Textures

UDIM tiles allow multi-tile UV layouts:
```
texture_file: $HIP/textures/hero_diffuse.<UDIM>.exr
```

UDIM tile numbering: 1001 = first tile (U:0-1, V:0-1), 1002 = second tile, etc.

### Connecting Textures in MaterialX

In Houdini's Material Library LOP:
1. Create a `mtlxstandard_surface` shader
2. Create a `mtlximage` node for each texture map
3. Connect `mtlximage.out` to the appropriate input on the surface shader
4. Set `file` parameter on each `mtlximage` to the texture path
5. Set `colorspace` to "srgb_texture" for color maps, "Raw" for data maps

### Color Space Rules

| Map Type | Color Space | Why |
|----------|-------------|-----|
| Diffuse, Emission, Coat Color | sRGB | Authored in display-referred space |
| Roughness, Metalness, AO, Normal, Displacement | Raw/Linear | Data maps, not display colors |
| HDR Environment | Linear | Already in scene-referred space |

**Getting this wrong** produces washed-out or over-dark materials. The most common mistake is loading a roughness map as sRGB.

## Displacement

### Displacement in Karma

```
# On the material:
displacement_scale: 0.05    # World-space displacement amount
displacement_offset: 0.0    # Offset before scaling

# On the geometry prim (or render settings):
karma:object:displacementbound: 0.1  # Must be >= max displacement
```

**Displacement bound** must be set correctly or geometry will clip.
Too large wastes memory; too small clips displaced surfaces.

### Subdivision for Displacement

Displacement requires subdivision:
```
subdivisionScheme: "catmullClark"
karma:object:dicingquality: 1.0   # 1.0 = standard, 0.5 = coarser, 2.0 = finer
```

## Material Assignment Patterns

### Direct Binding
```python
# Bind one material to one prim
UsdShade.MaterialBindingAPI(prim).Bind(material)
```

### Collection-Based Binding
```python
# Bind material to a collection of prims
binding_api = UsdShade.MaterialBindingAPI.Apply(parent_prim)
binding_api.Bind(material, bindingName="chrome_parts",
                 materialPurpose=UsdShade.Tokens.full)
```

### GeomSubset (Face-Level)
```python
# Assign different materials to different faces of one mesh
subset = UsdGeom.Subset.Define(stage, "/geo/mesh/face_group_A")
subset.CreateIndicesAttr().Set([0, 1, 2, 3])  # face indices
subset.CreateElementTypeAttr().Set("face")
UsdShade.MaterialBindingAPI(subset.GetPrim()).Bind(material_a)
```

### In Houdini
- **Assign Material LOP**: Pattern-based (`/World/geo/**`), fastest for bulk
- **Material Library LOP**: Create + assign in one node
- **Python LOP**: Full API access for complex binding logic

## MaterialX Nodes (Common)

| Node | Purpose | Common Use |
|------|---------|------------|
| `mtlxstandard_surface` | PBR surface shader | Main material shader |
| `mtlximage` | Texture file reader | Loading texture maps |
| `mtlxnoise2d` / `mtlxnoise3d` | Procedural noise | Procedural patterns |
| `mtlxmix` | Blend two values | Layering materials |
| `mtlxramp4` | Gradient ramp | Color/value mapping |
| `mtlxnormalmap` | Normal map processor | Converting tangent-space normals |
| `mtlxtiledimage` | Tiled texture reader | Repeating textures with UV controls |
| `mtlxmultiply` | Multiply values | Combining maps (AO * diffuse) |
| `mtlxadd` | Add values | Combining contributions |
| `mtlxfractal3d` | fBm fractal noise | Procedural variation |
| `mtlxcellnoise2d` | Voronoi noise | Organic patterns |
| `mtlxdisplacement` | Displacement output | Connect to material displacement |
