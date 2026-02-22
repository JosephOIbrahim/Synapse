# Texture Parameter Overrides in Karma

## Triggers
texture override, texture parameter, per-prim texture, edit properties material,
texture path override, instanced material texture, udim, texture streaming

## Context
Override texture paths on instanced materials using Edit Properties LOP. This allows per-prim texture variation without duplicating material networks. CPU and XPU handle texture formats and UDIM differently.

## Code

```python
# Override texture on instanced material via Edit Properties LOP
import hou

stage_net = hou.node("/stage")

# Edit Properties LOP — override material parameters per prim
edit_props = stage_net.createNode("editproperties", "texture_override")

# Target specific prims that share a material
edit_props.parm("primpattern").set("/geo/building_01/facade")

# Override the base_color texture path on the bound material
# The property path follows: material:binding target → shader input
# Use the USD-encoded parameter name
edit_props.parm("xn__inputsbase_color_filename_yla").set(
    "$HIP/textures/building_01_diffuse.exr"
)
edit_props.parm("xn__inputsbase_color_filename_control_jma").set("set")
```

```python
# Per-instance texture variation using Material Override
import hou

stage_net = hou.node("/stage")

# Create instancer with material overrides
# Each instance gets its own texture path

# Method: Use SOP-level material attributes
sop_wrangle = hou.node("/obj/scatter_points").createNode("attribwrangle", "set_textures")
sop_wrangle.parm("class").set(0)  # Points
sop_wrangle.parm("snippet").set('''
// Assign different texture per instance based on point index
string textures[] = array(
    "$HIP/textures/var_01.exr",
    "$HIP/textures/var_02.exr",
    "$HIP/textures/var_03.exr",
    "$HIP/textures/var_04.exr"
);

int idx = @ptnum % len(textures);
s@texture_path = textures[idx];
''')
```

```python
# UDIM texture setup in MaterialX
import hou

matlib = hou.node("/stage/materiallibrary1")
matlib.cook(force=True)

mat_subnet = matlib.node("udim_material")
if mat_subnet:
    mat_subnet.cook(force=True)

    # Create MaterialX image node for UDIM texture
    tex_node = mat_subnet.createNode("mtlximage", "base_color_tex")

    # UDIM pattern — Houdini/USD uses <UDIM> token
    # File on disk: texture_1001.exr, texture_1002.exr, etc.
    tex_node.parm("file").set("$HIP/textures/hero_basecolor.<UDIM>.exr")

    # Color space
    tex_node.parm("colorspace").set("srgb_texture")  # for diffuse
    # Use "raw" for normal maps, roughness, metalness

    # Connect to standard surface
    surface = mat_subnet.node("mtlxsurface")
    if surface:
        surface.setInput(
            surface.inputIndex("base_color"),
            tex_node, 0
        )

    mat_subnet.layoutChildren()
```

```python
# CPU vs XPU texture handling differences
TEXTURE_SUPPORT = {
    "feature": [
        "EXR textures",
        "UDIM tiles",
        "UDIM limit",
        "Texture streaming",
        "Texture cache",
        "RAT (Houdini native)",
        "TX (RenderMan)",
        "Normal maps",
        "Displacement maps",
        "Volume textures (3D)",
    ],
    "karma_cpu": [
        "Full support",
        "Full support",
        "Unlimited",
        "Disk-based, unlimited",
        "RAM-based, configurable",
        "Full support",
        "Full support",
        "Tangent + object space",
        "Full support",
        "Full support",
    ],
    "karma_xpu": [
        "Full support",
        "Supported",
        "Limited by GPU VRAM",
        "GPU VRAM-limited",
        "GPU VRAM = cache size",
        "Converted to EXR",
        "Converted to EXR",
        "Tangent + object space",
        "Supported",
        "Limited support",
    ],
}

# Print comparison
for i, feature in enumerate(TEXTURE_SUPPORT["feature"]):
    cpu = TEXTURE_SUPPORT["karma_cpu"][i]
    xpu = TEXTURE_SUPPORT["karma_xpu"][i]
    print(f"  {feature:<25} CPU: {cpu:<25} XPU: {xpu}")
```

```python
# Verifying texture paths resolve correctly
import hou
import os
from pxr import UsdShade, Sdf

stage = hou.node("/stage/materiallibrary1").stage()

missing_textures = []
for prim in stage.Traverse():
    if prim.IsA(UsdShade.Shader):
        shader = UsdShade.Shader(prim)
        for inp in shader.GetInputs():
            val = inp.Get()
            if isinstance(val, Sdf.AssetPath):
                resolved = val.resolvedPath or val.path
                expanded = hou.text.expandString(resolved)
                # Skip UDIM — can't check individual tiles easily
                if "<UDIM>" in expanded or "<udim>" in expanded:
                    continue
                if not os.path.isfile(expanded):
                    missing_textures.append(
                        f"{prim.GetPath()}.{inp.GetBaseName()}: {expanded}"
                    )

if missing_textures:
    print(f"Missing textures ({len(missing_textures)}):")
    for mt in missing_textures:
        print(f"  {mt}")
else:
    print("All texture paths resolve correctly")
```

## Expected Scene Graph
```
/materials/hero_material/  (UsdShadeMaterial)
  └─ mtlxsurface          (UsdShadeShader)
       ├─ inputs:base_color ← base_color_tex (mtlximage)
       │    └─ file: "$HIP/textures/hero_basecolor.<UDIM>.exr"
       └─ inputs:specular_roughness ← roughness_tex (mtlximage)
            └─ file: "$HIP/textures/hero_roughness.<UDIM>.exr"
```

## Common Mistakes
- Using `<udim>` lowercase — Houdini/USD expects `<UDIM>` uppercase
- Forgetting color space on texture nodes — diffuse textures need `srgb_texture`, data maps need `raw`
- Not checking GPU VRAM when using many UDIM tiles on XPU — tiles must fit in VRAM
- Setting texture override on wrong prim — must target the geometry prim, not the material prim
- Using `$HIP` in texture paths without verifying it expands correctly at render time
