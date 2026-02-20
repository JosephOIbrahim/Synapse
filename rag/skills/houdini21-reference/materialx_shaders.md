# MaterialX Shaders in Solaris

## Triggers

materialx, mtlxstandard_surface, mtlximage, material library, karma material, pbr shader, texture connection, colorspace, normal map, displacement, usd material binding, material assignment, matlib, create material, standard surface, base color, roughness, metalness, transmission, subsurface, coat, sheen, emission, opacity, udim, face subset, geomsubset, mtlxnormalmap, mtlxdisplacement, srgb_texture, raw colorspace, cook matlib

## Context

MaterialX Standard Surface is the default PBR shader for Karma in Houdini 21 Solaris. Materials are created inside a Material Library LOP; the matlib node must be cooked before any child shader nodes can be created inside it.

## Code

```python
# ── CRITICAL: always cook matlib before createNode ──────────────────────────
# Without cook(), the internal subnet does not exist and createNode returns None.

import hou

stage = hou.node("/stage")

# Create the Material Library LOP
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)  # MANDATORY before any createNode inside matlib
```

```python
# ── Basic MaterialX Standard Surface (inline values, no textures) ────────────

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)  # cook before createNode

# createNode on the matlib creates children inside the material subnet
surface = matlib.createNode("mtlxstandard_surface", "plastic_red")

# Base layer (diffuse)
surface.parm("base").set(1.0)               # diffuse weight (0-1)
surface.parm("base_color").set((0.8, 0.1, 0.08))  # red diffuse color

# Specular layer (GGX microfacet)
surface.parm("specular").set(1.0)           # specular weight
surface.parm("specular_roughness").set(0.4) # 0=mirror, 1=diffuse-like
surface.parm("specular_IOR").set(1.5)       # index of refraction (plastic ~1.5)
surface.parm("metalness").set(0.0)          # 0=dielectric, 1=metal

matlib.layoutChildren()
```

```python
# ── Metal presets ────────────────────────────────────────────────────────────

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

# Polished chrome
chrome = matlib.createNode("mtlxstandard_surface", "polished_chrome")
chrome.parm("base_color").set((0.95, 0.95, 0.95))
chrome.parm("metalness").set(1.0)           # full metal: base_color becomes specular tint
chrome.parm("specular_roughness").set(0.02) # near-mirror
chrome.parm("specular_IOR").set(2.5)        # conductor IOR

# Brushed metal (anisotropic)
brushed = matlib.createNode("mtlxstandard_surface", "brushed_metal")
brushed.parm("base_color").set((0.9, 0.9, 0.9))
brushed.parm("metalness").set(1.0)
brushed.parm("specular_roughness").set(0.25)
brushed.parm("specular_IOR").set(2.5)
brushed.parm("specular_anisotropy").set(0.8)  # directional brushing

matlib.layoutChildren()
```

```python
# ── Glass and transmission ───────────────────────────────────────────────────

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

# Clear glass
glass = matlib.createNode("mtlxstandard_surface", "clear_glass")
glass.parm("base").set(0.0)               # no diffuse
glass.parm("metalness").set(0.0)
glass.parm("specular_roughness").set(0.0) # perfect specular
glass.parm("specular_IOR").set(1.5)       # glass IOR
glass.parm("transmission").set(1.0)       # fully transmissive
glass.parm("transmission_color").set((1.0, 1.0, 1.0))

# Frosted glass
frosted = matlib.createNode("mtlxstandard_surface", "frosted_glass")
frosted.parm("base").set(0.0)
frosted.parm("specular_roughness").set(0.3)  # scatter causes frost
frosted.parm("specular_IOR").set(1.5)
frosted.parm("transmission").set(1.0)
frosted.parm("transmission_color").set((0.95, 0.97, 1.0))

matlib.layoutChildren()
```

```python
# ── Subsurface scattering: skin and marble ───────────────────────────────────

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

# Skin SSS
skin = matlib.createNode("mtlxstandard_surface", "skin")
skin.parm("base_color").set((0.8, 0.5, 0.4))
skin.parm("specular_roughness").set(0.35)
skin.parm("specular_IOR").set(1.4)
skin.parm("subsurface").set(0.6)                      # SSS weight
skin.parm("subsurface_color").set((0.9, 0.3, 0.2))   # deeper scatter color
skin.parm("subsurface_radius").set((1.0, 0.35, 0.15)) # RGB scatter distances
skin.parm("subsurface_scale").set(0.05)               # world-space scale

# Marble
marble = matlib.createNode("mtlxstandard_surface", "marble")
marble.parm("base_color").set((0.95, 0.93, 0.9))
marble.parm("specular_roughness").set(0.1)
marble.parm("subsurface").set(0.4)
marble.parm("subsurface_color").set((0.85, 0.82, 0.78))
marble.parm("subsurface_scale").set(0.1)

matlib.layoutChildren()
```

```python
# ── Coat and sheen layers ────────────────────────────────────────────────────

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

# Car paint (clear coat over metallic base)
car_paint = matlib.createNode("mtlxstandard_surface", "car_paint_red")
car_paint.parm("base_color").set((0.7, 0.05, 0.05))
car_paint.parm("metalness").set(0.5)
car_paint.parm("specular_roughness").set(0.15)
car_paint.parm("coat").set(1.0)            # clear coat weight
car_paint.parm("coat_color").set((1.0, 1.0, 1.0))
car_paint.parm("coat_roughness").set(0.02) # glossy clear coat

# Velvet fabric
velvet = matlib.createNode("mtlxstandard_surface", "velvet_navy")
velvet.parm("base_color").set((0.05, 0.08, 0.25))
velvet.parm("metalness").set(0.0)
velvet.parm("specular_roughness").set(0.8)
velvet.parm("sheen").set(0.8)                         # sheen weight
velvet.parm("sheen_color").set((0.1, 0.15, 0.4))     # edge highlight color
velvet.parm("sheen_roughness").set(0.3)

matlib.layoutChildren()
```

```python
# ── Texture connections: mtlximage -> mtlxstandard_surface ──────────────────
#
# Colorspace rules:
#   srgb_texture  -> color maps (diffuse, emission, coat color)
#   Raw           -> data maps (roughness, metalness, normal, displacement, AO)
#
# Getting this wrong produces washed-out or over-dark materials.
# Most common mistake: loading a roughness map as srgb_texture.

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

# Create the surface shader
surface = matlib.createNode("mtlxstandard_surface", "hero_material")

# ── Diffuse / albedo map (color data -> srgb_texture) ──
img_diffuse = matlib.createNode("mtlximage", "img_diffuse")
img_diffuse.parm("file").set("$HIP/textures/hero_diffuse.1001.exr")
img_diffuse.parm("colorspace").set("srgb_texture")  # authored in display space
img_diffuse.parm("signature").set("color3")         # output type
img_diffuse.setInput(0, None)                       # no UV input = default UVs

# Connect diffuse image out -> surface base_color in
surface.setNamedInput("base_color", img_diffuse, "out")

# ── Roughness map (data -> Raw) ──
img_rough = matlib.createNode("mtlximage", "img_roughness")
img_rough.parm("file").set("$HIP/textures/hero_roughness.1001.exr")
img_rough.parm("colorspace").set("Raw")    # linear data, not display color
img_rough.parm("signature").set("float")  # single-channel float

surface.setNamedInput("specular_roughness", img_rough, "out")

# ── Metalness map (data -> Raw) ──
img_metal = matlib.createNode("mtlximage", "img_metalness")
img_metal.parm("file").set("$HIP/textures/hero_metalness.1001.exr")
img_metal.parm("colorspace").set("Raw")
img_metal.parm("signature").set("float")

surface.setNamedInput("metalness", img_metal, "out")

matlib.layoutChildren()
```

```python
# ── Normal map setup: mtlximage -> mtlxnormalmap -> surface ─────────────────
#
# Normal maps require the mtlxnormalmap node between image and surface.
# The image must be Raw (linear); the normalmap node decodes tangent-space normals.
# DirectX normal maps: negate the G channel in mtlxnormalmap (space="tangent").

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

surface = matlib.createNode("mtlxstandard_surface", "textured_surface")

# Normal map image (MUST be Raw - it is a data map, not a color)
img_normal = matlib.createNode("mtlximage", "img_normal")
img_normal.parm("file").set("$HIP/textures/hero_normal.1001.exr")
img_normal.parm("colorspace").set("Raw")      # critical: never srgb_texture here
img_normal.parm("signature").set("color3")    # RGB normal data stored as color3

# Normal map decoder: converts [0,1] encoded normals -> [-1,1] tangent vectors
normalmap = matlib.createNode("mtlxnormalmap", "decode_normal")
normalmap.parm("space").set("tangent")        # tangent-space normal map (standard)
# For DirectX maps (G channel flipped): set normalmap.parm("scale") or negate Y

# Wire: img_normal.out -> normalmap.in -> surface.normal
normalmap.setNamedInput("in", img_normal, "out")
surface.setNamedInput("normal", normalmap, "out")

matlib.layoutChildren()
```

```python
# ── Displacement: mtlximage -> mtlxdisplacement -> material output ───────────
#
# Displacement in Karma requires:
#   1. A mtlxdisplacement node wired to the material's displacement output
#   2. karma:object:displacementbound on the geometry prim (must >= max displacement)
#   3. subdivisionScheme = "catmullClark" on the geometry
# Without displacementbound the surface clips at object bounds.

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

surface = matlib.createNode("mtlxstandard_surface", "displaced_rock")
surface.parm("base_color").set((0.3, 0.28, 0.25))
surface.parm("specular_roughness").set(0.7)

# Height / displacement map image (Raw linear data)
img_disp = matlib.createNode("mtlximage", "img_displacement")
img_disp.parm("file").set("$HIP/textures/rock_height.1001.exr")
img_disp.parm("colorspace").set("Raw")    # always Raw for displacement
img_disp.parm("signature").set("float")  # single-channel

# Displacement node: converts height values to displacement vectors
disp_node = matlib.createNode("mtlxdisplacement", "disp_output")
disp_node.parm("scale").set(0.05)   # world-space displacement magnitude
disp_node.parm("offset").set(0.0)   # shift before scaling (0.5 to center a 0-1 map)

# Wire: img_disp.out -> disp_node.displacement input
disp_node.setNamedInput("displacement", img_disp, "out")

# Wire surface + displacement to the material output node
# (matlib auto-creates a collect node that feeds the USD material prim)
# surface connects to "surface" port, disp_node connects to "displacement" port
collect = matlib.createNode("collect", "mat_output")
collect.setNamedInput("surface", surface, "out")
collect.setNamedInput("displacement", disp_node, "out")

matlib.layoutChildren()

# ── Set displacement bound on geometry prim via Python ──
# This must be done on the geometry USD prim, not the material
prim_path = "/World/geo/rock_mesh"
prim = hou.node("/stage").stage().GetPrimAtPath(prim_path)
if prim:
    attr = prim.CreateAttribute("karma:object:displacementbound",
                                 hou.parmTemplateType.Float)
    attr.Set(0.1)  # must be >= actual max displacement (scale value above)

    # Enable Catmull-Clark subdivision for displacement to work
    subdiv_attr = prim.CreateAttribute("subdivisionScheme",
                                        hou.parmTemplateType.String)
    subdiv_attr.Set("catmullClark")
```

```python
# ── UDIM textures ────────────────────────────────────────────────────────────
#
# UDIM tile numbering: 1001 = U(0-1),V(0-1), 1002 = U(1-2),V(0-1), etc.
# Use <UDIM> token in the file path; mtlximage auto-discovers and stitches tiles.

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

surface = matlib.createNode("mtlxstandard_surface", "hero_char")

# UDIM diffuse: <UDIM> token in filename
img_diffuse = matlib.createNode("mtlximage", "img_diffuse_udim")
img_diffuse.parm("file").set("$HIP/textures/hero_diffuse.<UDIM>.exr")
img_diffuse.parm("colorspace").set("srgb_texture")
img_diffuse.parm("signature").set("color3")

surface.setNamedInput("base_color", img_diffuse, "out")

# UDIM roughness
img_rough = matlib.createNode("mtlximage", "img_rough_udim")
img_rough.parm("file").set("$HIP/textures/hero_roughness.<UDIM>.exr")
img_rough.parm("colorspace").set("Raw")
img_rough.parm("signature").set("float")

surface.setNamedInput("specular_roughness", img_rough, "out")

matlib.layoutChildren()
```

```python
# ── USD material binding from Python ────────────────────────────────────────
#
# After building materials in a materiallibrary LOP, bind them in Solaris
# using assign_material LOP (pattern-based) or Python LOP (API-based).
# Exact prim paths are required -- wildcard patterns like /** often fail in Karma.

import hou
from pxr import UsdShade, UsdGeom

stage_node = hou.node("/stage")
stage = stage_node.stage()

# Get the material prim created by the materiallibrary LOP
# matlib names the prim after the shader node name
mat_prim = stage.GetPrimAtPath("/materials/plastic_red")
material = UsdShade.Material(mat_prim)

# Bind to a single geometry prim (exact path)
geo_prim = stage.GetPrimAtPath("/World/geo/body_mesh")
if geo_prim and material:
    UsdShade.MaterialBindingAPI(geo_prim).Bind(material)

# Bind to all children of a scope (loop version -- reliable for Karma)
scope_prim = stage.GetPrimAtPath("/World/geo")
for child in scope_prim.GetChildren():
    UsdShade.MaterialBindingAPI(child).Bind(material)
```

```python
# ── Collection-based binding (for complex multi-material scenes) ─────────────

import hou
from pxr import UsdShade, Usd

stage_node = hou.node("/stage")
stage = stage_node.stage()

chrome_mat = UsdShade.Material(stage.GetPrimAtPath("/materials/polished_chrome"))
red_mat    = UsdShade.Material(stage.GetPrimAtPath("/materials/plastic_red"))

# Bind chrome to specific face subset (GeomSubset)
subset_prim = stage.GetPrimAtPath("/World/geo/car_body/chrome_parts")
if subset_prim:
    UsdShade.MaterialBindingAPI(subset_prim).Bind(
        chrome_mat,
        materialPurpose=UsdShade.Tokens.full  # "full" = rendering, "preview" = viewport
    )

# Bind red plastic to remaining faces
body_prim = stage.GetPrimAtPath("/World/geo/car_body")
if body_prim:
    UsdShade.MaterialBindingAPI(body_prim).Bind(red_mat)
```

```python
# ── Face-level material assignment via GeomSubset ────────────────────────────
#
# GeomSubset splits a mesh into named face groups.
# Each subset can receive its own material binding.
# face indices are zero-based polygon indices.

import hou
from pxr import UsdGeom, UsdShade

stage_node = hou.node("/stage")
stage = stage_node.stage()

mesh_prim = stage.GetPrimAtPath("/World/geo/prop_box")
glass_mat = UsdShade.Material(stage.GetPrimAtPath("/materials/clear_glass"))
wood_mat  = UsdShade.Material(stage.GetPrimAtPath("/materials/oak_wood"))

# Define subsets on the mesh prim
glass_subset = UsdGeom.Subset.Define(stage, "/World/geo/prop_box/glass_faces")
glass_subset.CreateElementTypeAttr().Set("face")
glass_subset.CreateIndicesAttr().Set([0, 1, 2, 3])   # top face indices

wood_subset = UsdGeom.Subset.Define(stage, "/World/geo/prop_box/wood_faces")
wood_subset.CreateElementTypeAttr().Set("face")
wood_subset.CreateIndicesAttr().Set([4, 5, 6, 7, 8, 9, 10, 11])  # remaining faces

# Bind materials to each subset
UsdShade.MaterialBindingAPI(glass_subset.GetPrim()).Bind(glass_mat)
UsdShade.MaterialBindingAPI(wood_subset.GetPrim()).Bind(wood_mat)
```

```python
# ── Procedural texture: AO multiplied into diffuse via mtlxmultiply ──────────

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

surface = matlib.createNode("mtlxstandard_surface", "ao_blended")

# Diffuse color image
img_diffuse = matlib.createNode("mtlximage", "img_diffuse")
img_diffuse.parm("file").set("$HIP/textures/diffuse.1001.exr")
img_diffuse.parm("colorspace").set("srgb_texture")
img_diffuse.parm("signature").set("color3")

# AO map (data -> Raw, output as float then convert to color3 for multiply)
img_ao = matlib.createNode("mtlximage", "img_ao")
img_ao.parm("file").set("$HIP/textures/ao.1001.exr")
img_ao.parm("colorspace").set("Raw")       # AO is a data map
img_ao.parm("signature").set("color3")     # use color3 so multiply node types match

# Multiply node: diffuse * AO -> darkens crevices
multiply = matlib.createNode("mtlxmultiply", "ao_multiply")
multiply.parm("signature").set("color3")
multiply.setNamedInput("in1", img_diffuse, "out")
multiply.setNamedInput("in2", img_ao, "out")

surface.setNamedInput("base_color", multiply, "out")
matlib.layoutChildren()
```

```python
# ── Emission material (self-illuminating surface) ────────────────────────────

import hou

stage = hou.node("/stage")
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.cook(force=True)

emissive = matlib.createNode("mtlxstandard_surface", "neon_sign")

# Base layer: dim to let emission dominate
emissive.parm("base").set(0.0)

# Emission: weight > 0 enables self-illumination
# emission_color controls the emitted spectrum
# intensity controlled here by emission weight; no separate exposure parm on mtlx
emissive.parm("emission").set(5.0)                       # emission multiplier (can exceed 1)
emissive.parm("emission_color").set((0.0, 0.8, 1.0))    # cyan glow

# Optional: texture drives which areas emit
img_emit = matlib.createNode("mtlximage", "img_emit_mask")
img_emit.parm("file").set("$HIP/textures/neon_emission.exr")
img_emit.parm("colorspace").set("srgb_texture")  # authored as display color
img_emit.parm("signature").set("color3")

emissive.setNamedInput("emission_color", img_emit, "out")
matlib.layoutChildren()
```

## Common Mistakes

- **Forgetting `matlib.cook(force=True)`**: `createNode()` inside an uncooked matlib returns `None`. Always cook before creating child nodes.
- **Wrong colorspace on roughness/normal/metalness maps**: These are data maps and must use `"Raw"` (not `"srgb_texture"`). Loading roughness as sRGB produces washed-out, incorrectly gamma-corrected values.
- **Missing `mtlxnormalmap` decoder**: Connecting a raw normal map image directly to `surface.normal` skips the [-1,1] decode step, producing incorrect shading. Always insert a `mtlxnormalmap` node between `mtlximage` and the surface.
- **Displacement without `displacementbound`**: Karma clips displaced geometry at the original bounding box if `karma:object:displacementbound` is not set to a value >= the maximum displacement distance.
- **Displacement without subdivision**: `karma:object:displacementbound` set correctly but `subdivisionScheme` left as `"none"` -- displacement has no geometry to push. Set `"catmullClark"` on the mesh prim.
- **Wildcard material assignment paths**: Binding with `/World/geo/**` often fails to resolve in Karma. Use exact prim paths or loop over children explicitly.
- **GeomSubset indices**: Face indices are zero-based polygon indices matching the mesh topology -- not vertex or point indices.
- **Emission exceeding 1.0 with intensity**: `emission` weight can exceed 1.0 (it is a multiplier, not a 0-1 clamp), but keep all light source intensities at 1.0 per the Lighting Law. Emissive geometry brightness is controlled via `emission` weight only.
- **UDIM token case**: The token is `<UDIM>` (all caps) -- lowercase `<udim>` is not recognized by `mtlximage`.
- **`mtlxdisplacement` offset for 0-1 height maps**: A height texture ranging 0-1 displaces only upward. Set `offset` to `-0.5` to center the displacement around the original surface.
