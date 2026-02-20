# Material Library LOP Setup

## Triggers
material library, matlib, create material, material subnet, matlib cook,
multiple materials, material library lop, material scope, matlib setup

## Context
Material Library LOP creates materials as USD shader prims. CRITICAL: call `matlib.cook(force=True)` BEFORE `createNode()` on shader children — without cook, the internal subnet doesn't exist and createNode returns None. Prefer multiple subnets in one matlib over separate matlib nodes.

## Code

```python
# Creating a Material Library with multiple materials
import hou

stage_net = hou.node("/stage")

# Create Material Library LOP
matlib = stage_net.createNode("materiallibrary", "materials")

# CRITICAL: Cook the matlib BEFORE creating child nodes
# Without this, the internal network doesn't exist yet
matlib.cook(force=True)

# Now create material subnets inside the matlib
# Each subnet becomes a USD Material prim
mat_net = matlib.node(".")  # the matlib IS the container

# --- Material 1: Metal ---
metal_subnet = matlib.createNode("subnet", "chrome_metal")
metal_subnet.cook(force=True)

# Create MaterialX Standard Surface inside subnet
mtlx = metal_subnet.createNode("mtlxstandard_surface", "mtlxsurface")
mtlx.parm("base").set(1.0)
mtlx.parm("basecolor").set((0.8, 0.8, 0.85))
mtlx.parm("metalness").set(1.0)
mtlx.parm("specular_roughness").set(0.15)

# Create surface output and connect
surface_output = metal_subnet.createNode("subnetconnector", "surface_output")
surface_output.parm("connectorkind").set("output")
surface_output.parm("parmname").set("surface")
surface_output.parm("parmlabel").set("Surface")
surface_output.parm("parmtype").set("surface")
surface_output.setInput(0, mtlx)

# --- Material 2: Rubber ---
rubber_subnet = matlib.createNode("subnet", "red_rubber")
rubber_subnet.cook(force=True)

mtlx2 = rubber_subnet.createNode("mtlxstandard_surface", "mtlxsurface")
mtlx2.parm("base").set(1.0)
mtlx2.parm("basecolor").set((0.8, 0.1, 0.1))
mtlx2.parm("metalness").set(0.0)
mtlx2.parm("specular_roughness").set(0.7)
mtlx2.parm("subsurface").set(0.2)

surface_output2 = rubber_subnet.createNode("subnetconnector", "surface_output")
surface_output2.parm("connectorkind").set("output")
surface_output2.parm("parmname").set("surface")
surface_output2.parm("parmlabel").set("Surface")
surface_output2.parm("parmtype").set("surface")
surface_output2.setInput(0, mtlx2)

matlib.layoutChildren()
```

```python
# Assigning materials directly in Material Library (no separate assign node)
import hou

matlib = hou.node("/stage/materials")

# Method: Use geopath parameters on the matlib node
# Each material subnet can have geometry assignment paths

# Number of material assignments
matlib.parm("materials").set(2)

# Material 1 assignment
matlib.parm("matnode1").set("chrome_metal")
matlib.parm("geopath1").set("/geo/body/shape")

# Material 2 assignment
matlib.parm("matnode2").set("red_rubber")
matlib.parm("geopath2").set("/geo/tires/shape")

# NOTE: geopath must match EXACT USD prim paths
# WRONG: /geo/body/*
# RIGHT: /geo/body/shape
```

```python
# Wiring matlib into standard Solaris chain
import hou

stage_net = hou.node("/stage")

# Standard wiring order: geometry FIRST, then matlib
merge = stage_net.node("merge1")      # merge of all geometry + lights
matlib = stage_net.node("materials")   # material library
camera = stage_net.node("camera1")
karma = stage_net.node("karmarendersettings1")

# Wire: merge -> matlib -> camera -> karma
matlib.setInput(0, merge)
camera.setInput(0, matlib)
karma.setInput(0, camera)

# Display flag on last node
karma.setDisplayFlag(True)
```

```python
# Verifying matlib created materials correctly
import hou
from pxr import UsdShade

matlib = hou.node("/stage/materials")
stage = matlib.stage()

# List all materials created by this matlib
material_scope = "/materials"  # default matlib scope
scope_prim = stage.GetPrimAtPath(material_scope)
if scope_prim.IsValid():
    for child in scope_prim.GetChildren():
        if child.IsA(UsdShade.Material):
            mat = UsdShade.Material(child)
            print(f"Material: {child.GetPath()}")

            # Check surface shader
            surface = mat.GetSurfaceOutput()
            if surface:
                sources = surface.GetConnectedSources()
                if sources:
                    shader = sources[0][0].GetPrim()
                    print(f"  Shader: {shader.GetPath()}")
                    shader_id = shader.GetAttribute("info:id").Get()
                    print(f"  Type: {shader_id}")
else:
    print(f"Material scope {material_scope} not found in stage")
```

## Expected Scene Graph
```
/materials/                          (Scope)
  ├─ chrome_metal/                   (UsdShadeMaterial)
  │    └─ mtlxsurface               (UsdShadeShader, ND_standard_surface_surfaceshader)
  │         ├─ metalness: 1.0
  │         └─ specular_roughness: 0.15
  └─ red_rubber/                     (UsdShadeMaterial)
       └─ mtlxsurface               (UsdShadeShader, ND_standard_surface_surfaceshader)
            ├─ metalness: 0.0
            └─ specular_roughness: 0.7
```

## Common Mistakes
- NOT calling `matlib.cook(force=True)` before createNode() — internal subnet doesn't exist, createNode returns None
- Using separate Assign Material nodes when geopath on matlib works — unnecessary complexity
- Material scope mismatch: matlib creates under `/materials/` by default, but assignment paths must match
- Wiring matlib BEFORE geometry merge — materials can't bind to prims that don't exist yet
- Creating shader nodes directly in matlib root instead of inside subnets — each material needs its own subnet
