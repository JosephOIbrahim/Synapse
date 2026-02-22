# Primvar-Driven Material Assignment

## Triggers
shop_materialpath, primvar material, attribute driven material, geometry material,
sop material, material attribute, primvar reader, material from attribute

## Context
SOP-level `shop_materialpath` attribute controls material assignment when geometry enters LOPs. Primvars (primitive variables) from SOP geometry become USD primvars that MaterialX shaders can read to drive parameters like color or roughness per-prim.

## Code

```python
# SOP-level: set shop_materialpath for automatic material binding in LOPs
import hou

geo_node = hou.node("/obj/geo1")
wrangle = geo_node.createNode("attribwrangle", "set_material")
wrangle.parm("class").set(1)  # Primitives

# shop_materialpath assigns material automatically when imported to LOPs
wrangle.parm("snippet").set('''
// Each prim gets a material based on its group membership
if (inprimgroup(0, "metal_parts", @primnum)) {
    s@shop_materialpath = "/materials/chrome";
} else if (inprimgroup(0, "rubber_parts", @primnum)) {
    s@shop_materialpath = "/materials/rubber";
} else {
    s@shop_materialpath = "/materials/default";
}
''')
```

```python
# SOP-level: create primvars that MaterialX shaders can read
import hou

geo_node = hou.node("/obj/geo1")
wrangle = geo_node.createNode("attribwrangle", "set_primvars")
wrangle.parm("class").set(1)  # Primitives

# These attributes become USD primvars when imported to LOPs
wrangle.parm("snippet").set('''
// Per-prim color variation — MaterialX can read this
v@displayColor = set(rand(@primnum), rand(@primnum+1), rand(@primnum+2));

// Per-prim roughness variation
f@roughness_variation = fit01(rand(@primnum * 42), 0.2, 0.8);

// Material ID for conditional assignment
i@material_id = @primnum % 3;
''')
```

```python
# LOP-level: configure SOP Import to promote attributes to primvars
import hou

stage_net = hou.node("/stage")
sop_import = stage_net.createNode("sopimport", "import_geo")
sop_import.parm("soppath").set("/obj/geo1/OUT")

# Attributes are promoted to primvars automatically by SOP Import
# But you can control which ones with the Primvars parameter:
# Default: all point/prim string and float attributes become primvars

# Verify primvars after cook
stage = sop_import.stage()
from pxr import UsdGeom
for prim in stage.Traverse():
    if prim.IsA(UsdGeom.Mesh):
        pvAPI = UsdGeom.PrimvarsAPI(prim)
        for pv in pvAPI.GetPrimvars():
            print(f"  {prim.GetPath()}: primvar:{pv.GetPrimvarName()} = {pv.Get()}")
```

```python
# MaterialX: reading primvars in a shader network
# In Houdini's Material Library, use mtlxgeompropvalue node to read primvars
import hou

matlib = hou.node("/stage/materiallibrary1")
matlib.cook(force=True)

# Inside a material subnet, create primvar reader
mat_subnet = matlib.node("varied_material")
if mat_subnet:
    mat_subnet.cook(force=True)

    # Create geompropvalue node to read a primvar
    prop_reader = mat_subnet.createNode("mtlxgeompropvalue", "read_color")
    # Set the primvar name to read
    prop_reader.parm("geomprop").set("displayColor")

    # Connect to standard surface base_color input
    surface = mat_subnet.node("mtlxsurface")
    if surface:
        surface.setInput(
            surface.inputIndex("base_color"),
            prop_reader, 0
        )

    mat_subnet.layoutChildren()
```

```python
# Reading shop_materialpath from USD stage to verify bindings
import hou
from pxr import UsdShade, UsdGeom

stage = hou.node("/stage/sopimport1").stage()

for prim in stage.Traverse():
    if prim.IsA(UsdGeom.Mesh):
        # Check material binding (from shop_materialpath)
        binding = UsdShade.MaterialBindingAPI(prim)
        direct = binding.GetDirectBinding()
        if direct.GetMaterial():
            print(f"{prim.GetPath()} -> {direct.GetMaterialPath()}")
        else:
            print(f"{prim.GetPath()} -> NO MATERIAL")
```

## Expected Scene Graph
```
/geo/piece_0  (UsdGeomMesh)
  ├─ material:binding → /materials/chrome  (from shop_materialpath)
  ├─ primvars:displayColor: (0.8, 0.3, 0.2)
  └─ primvars:roughness_variation: 0.45
/geo/piece_1  (UsdGeomMesh)
  ├─ material:binding → /materials/rubber
  ├─ primvars:displayColor: (0.2, 0.7, 0.5)
  └─ primvars:roughness_variation: 0.62
```

## Common Mistakes
- Setting `shop_materialpath` to Houdini node path instead of USD material prim path
- Forgetting that SOP point attributes don't auto-promote to USD primvars — only prim and detail attributes do reliably
- Using `@Cd` expecting it to drive MaterialX — must use `mtlxgeompropvalue` to read primvars in shader
- Not cooking matlib before connecting primvar reader nodes
- Spelling primvar name differently in SOP wrangle vs MaterialX geompropvalue node
