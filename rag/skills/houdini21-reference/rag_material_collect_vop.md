# Multi-Renderer Material Switching

## Triggers
collect vop, multi renderer, material switching, renderer specific material,
karma cpu xpu material, render delegate material, universal material

## Context
For scenes rendered across multiple delegates (Karma CPU, Karma XPU, Arnold), use the Collect VOP pattern or USD material purpose to provide renderer-specific shader networks within a single material prim.

## Code

```python
# Method 1: USD Material Outputs for renderer-specific shaders
# A single UsdShadeMaterial can have multiple surface outputs,
# one per render context
import hou
from pxr import UsdShade, Sdf

stage = hou.node("/stage/materiallibrary1").editableStage()

mat_path = "/materials/universal_material"
mat = UsdShade.Material.Define(stage, mat_path)

# Create Karma CPU shader (full MaterialX Standard Surface)
karma_shader = UsdShade.Shader.Define(stage, f"{mat_path}/karma_surface")
karma_shader.CreateIdAttr("ND_standard_surface_surfaceshader")
karma_shader.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set((0.8, 0.2, 0.1))
karma_shader.CreateInput("metalness", Sdf.ValueTypeNames.Float).Set(0.0)
karma_shader.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.3)
karma_shader.CreateInput("subsurface", Sdf.ValueTypeNames.Float).Set(0.2)

# Create simplified XPU shader (no SSS for speed)
xpu_shader = UsdShade.Shader.Define(stage, f"{mat_path}/xpu_surface")
xpu_shader.CreateIdAttr("ND_standard_surface_surfaceshader")
xpu_shader.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set((0.8, 0.2, 0.1))
xpu_shader.CreateInput("metalness", Sdf.ValueTypeNames.Float).Set(0.0)
xpu_shader.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.3)
# No subsurface — faster on XPU

# Connect default surface output (used by any renderer)
mat.CreateSurfaceOutput().ConnectToSource(karma_shader.ConnectableAPI(), "out")

# Connect renderer-specific output
# Karma XPU looks for "karma:xpu" render context
xpu_output = mat.CreateOutput("karma:xpu:surface", Sdf.ValueTypeNames.Token)
xpu_output.ConnectToSource(xpu_shader.ConnectableAPI(), "out")

print(f"Created multi-renderer material: {mat_path}")
```

```python
# Method 2: Collect VOP inside Material Library
# The Collect VOP merges multiple shader outputs into one material
import hou

matlib = hou.node("/stage/materiallibrary1")
matlib.cook(force=True)

# Create material subnet
mat_subnet = matlib.createNode("subnet", "multi_render_mat")
mat_subnet.cook(force=True)

# --- High-quality shader (Karma CPU) ---
hq_surface = mat_subnet.createNode("mtlxstandard_surface", "hq_surface")
hq_surface.parm("base_color").set((0.8, 0.2, 0.1))
hq_surface.parm("metalness").set(0.0)
hq_surface.parm("specular_roughness").set(0.3)
hq_surface.parm("subsurface").set(0.2)          # SSS for skin-like look
hq_surface.parm("subsurface_scale").set(0.01)

# --- Fast shader (Karma XPU / preview) ---
fast_surface = mat_subnet.createNode("mtlxstandard_surface", "fast_surface")
fast_surface.parm("base_color").set((0.8, 0.2, 0.1))
fast_surface.parm("metalness").set(0.0)
fast_surface.parm("specular_roughness").set(0.3)
# No SSS — faster rendering

# --- Surface output (primary) ---
surface_out = mat_subnet.createNode("subnetconnector", "surface_output")
surface_out.parm("connectorkind").set("output")
surface_out.parm("parmname").set("surface")
surface_out.parm("parmlabel").set("Surface")
surface_out.parm("parmtype").set("surface")
surface_out.setInput(0, hq_surface)  # default uses HQ

mat_subnet.layoutChildren()
print("Multi-renderer material created")
```

```python
# Method 3: Switching materials via Python based on render delegate
import hou

def configure_materials_for_delegate(stage_path, delegate_name):
    """Swap material assignments based on which renderer will be used."""
    karma = hou.node(stage_path)
    renderer = karma.evalParm("renderer") if karma else delegate_name

    # Material mappings per delegate
    MATERIAL_MAP = {
        "BRAY_HdKarma": {
            # CPU: use full-quality materials
            "/geo/character/skin": "/materials/skin_sss",
            "/geo/character/eyes": "/materials/eyes_refraction",
            "/geo/environment/**": "/materials/env_hq",
        },
        "BRAY_HdKarmaXPU": {
            # XPU: use simplified materials
            "/geo/character/skin": "/materials/skin_simple",
            "/geo/character/eyes": "/materials/eyes_simple",
            "/geo/environment/**": "/materials/env_fast",
        },
    }

    assignments = MATERIAL_MAP.get(renderer, MATERIAL_MAP["BRAY_HdKarma"])
    print(f"Configuring materials for: {renderer}")
    for target, material in assignments.items():
        print(f"  {target} -> {material}")

    return assignments

# Usage
assignments = configure_materials_for_delegate(
    "/stage/karmarendersettings1", "BRAY_HdKarmaXPU"
)
```

## Expected Scene Graph
```
/materials/universal_material/  (UsdShadeMaterial)
  ├─ karma_surface              (UsdShadeShader — full quality, SSS)
  │    └─ outputs:out → material surface output (default)
  ├─ xpu_surface                (UsdShadeShader — fast, no SSS)
  │    └─ outputs:out → material karma:xpu:surface output
  └─ outputs:
       ├─ surface → karma_surface       (default render context)
       └─ karma:xpu:surface → xpu_surface  (XPU-specific)
```

## Common Mistakes
- Creating separate materials per renderer instead of multi-output — doubles scene complexity
- Forgetting to set the default surface output — renderer with no specific context gets nothing
- Using VEX shader as the default and MaterialX as XPU-specific — should be opposite (MaterialX as default)
- Not testing both render paths — XPU path may silently fall back to default if context name is wrong
