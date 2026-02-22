# MaterialX as USD Prims

## Triggers
materialx usd, mtlx encoding, materialx prim, shader prim, mtlx namespace,
materialx usd api, read materialx, material _shader suffix, materialx sdf

## Context
MaterialX nodes in Houdini become USD shader prims under the Material prim. Parameters use Sdf value types. The material prim path may differ from the node name due to the `_shader` suffix on internal shader networks.

## Code

```python
# Reading MaterialX material structure from USD stage
import hou
from pxr import UsdShade, Sdf

stage = hou.node("/stage/materiallibrary1").stage()

# Traverse all materials
for prim in stage.Traverse():
    if prim.IsA(UsdShade.Material):
        mat = UsdShade.Material(prim)
        print(f"Material: {prim.GetPath()}")

        # Get surface shader connection
        surface_output = mat.GetSurfaceOutput()
        if surface_output:
            sources = surface_output.GetConnectedSources()
            for source_info in sources:
                shader_prim = source_info[0].GetPrim()
                print(f"  Surface shader: {shader_prim.GetPath()}")

                # Read shader type (info:id)
                shader_id = shader_prim.GetAttribute("info:id").Get()
                print(f"  Shader type: {shader_id}")
                # e.g., "ND_standard_surface_surfaceshader"

                # Read all shader inputs
                shader = UsdShade.Shader(shader_prim)
                for inp in shader.GetInputs():
                    name = inp.GetBaseName()
                    val = inp.Get()
                    if val is not None:
                        print(f"    {name} = {val}")
```

```python
# Writing MaterialX parameters via USD API
import hou
from pxr import UsdShade, Sdf, Gf

stage = hou.node("/stage/materiallibrary1").editableStage()

# Find existing shader prim
shader_path = "/materials/chrome_metal/mtlxsurface"
shader_prim = stage.GetPrimAtPath(shader_path)

if shader_prim.IsValid():
    shader = UsdShade.Shader(shader_prim)

    # Set base color (color3f)
    base_color_input = shader.GetInput("base_color")
    if base_color_input:
        base_color_input.Set(Gf.Vec3f(0.9, 0.85, 0.8))

    # Set metalness (float)
    metalness_input = shader.GetInput("metalness")
    if metalness_input:
        metalness_input.Set(1.0)

    # Set specular roughness (float)
    roughness_input = shader.GetInput("specular_roughness")
    if roughness_input:
        roughness_input.Set(0.1)

    print(f"Updated shader at {shader_path}")
```

```python
# Creating a MaterialX material from scratch via USD API
from pxr import UsdShade, Sdf, Gf

stage = hou.node("/stage/materiallibrary1").editableStage()

# Create material prim
mat_path = "/materials/glass"
mat_prim = UsdShade.Material.Define(stage, mat_path)

# Create Standard Surface shader
shader_path = f"{mat_path}/mtlxsurface"
shader = UsdShade.Shader.Define(stage, shader_path)
shader.CreateIdAttr("ND_standard_surface_surfaceshader")

# Set shader inputs with correct Sdf types
# Float inputs
shader.CreateInput("base", Sdf.ValueTypeNames.Float).Set(1.0)
shader.CreateInput("metalness", Sdf.ValueTypeNames.Float).Set(0.0)
shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(1.0)
shader.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.0)
shader.CreateInput("specular_IOR", Sdf.ValueTypeNames.Float).Set(1.5)
shader.CreateInput("transmission", Sdf.ValueTypeNames.Float).Set(0.95)

# Color3f inputs
shader.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1, 1, 1))
shader.CreateInput("transmission_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.98, 1.0, 0.98))

# Connect shader to material surface output
mat_prim.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "out")

print(f"Created glass material at {mat_path}")
```

```python
# The _shader suffix issue
# When Synapse's create_material handler builds a material, the USD prim path
# may include a _shader suffix that's not captured in the return value
#
# Example:
#   Houdini node: /stage/materiallibrary1/chrome_metal
#   USD Material prim: /materials/chrome_metal
#   USD Shader prim: /materials/chrome_metal/mtlxsurface
#
# But in some configurations:
#   USD Material prim: /materials/chrome_metal_shader
#   The _shader suffix comes from Houdini's internal naming
#
# To find the actual material path, query the stage:

import hou
from pxr import UsdShade

stage = hou.node("/stage/materiallibrary1").stage()
materials = []
for prim in stage.Traverse():
    if prim.IsA(UsdShade.Material):
        materials.append(str(prim.GetPath()))
        print(f"Material prim: {prim.GetPath()}")

# Use the actual USD path for material assignment, not the Houdini node name
```

```python
# Sdf.ValueTypeNames reference for MaterialX shader inputs
# | MaterialX Type | Sdf Value Type              | Python Type        |
# |----------------|-----------------------------|--------------------|
# | float          | Sdf.ValueTypeNames.Float    | float              |
# | color3         | Sdf.ValueTypeNames.Color3f  | Gf.Vec3f           |
# | vector3        | Sdf.ValueTypeNames.Vector3f | Gf.Vec3f           |
# | normal3        | Sdf.ValueTypeNames.Normal3f | Gf.Vec3f           |
# | string         | Sdf.ValueTypeNames.String   | str                |
# | integer        | Sdf.ValueTypeNames.Int      | int                |
# | boolean        | Sdf.ValueTypeNames.Bool     | bool               |
# | filename       | Sdf.ValueTypeNames.Asset    | Sdf.AssetPath(str) |
```

## Expected Scene Graph
```
/materials/chrome_metal/  (UsdShadeMaterial)
  └─ mtlxsurface         (UsdShadeShader)
       ├─ info:id: "ND_standard_surface_surfaceshader"
       ├─ inputs:base_color: (0.9, 0.85, 0.8)
       ├─ inputs:metalness: 1.0
       └─ inputs:specular_roughness: 0.1
```

## Common Mistakes
- Using Python float tuples `(0.8, 0.1, 0.1)` instead of `Gf.Vec3f(0.8, 0.1, 0.1)` for color inputs
- Expecting `Sdf.ValueTypeNames.Color3f` to accept `(r, g, b)` — must use Gf.Vec3f
- Forgetting `info:id` attribute on shader — renderer can't identify the shader type
- Not connecting shader output to material surface output — material has no visible shader
- Assuming Houdini node name matches USD prim path — the `_shader` suffix may be appended
