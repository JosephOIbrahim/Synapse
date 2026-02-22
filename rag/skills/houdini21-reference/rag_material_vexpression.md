# Dynamic Material Assignment with VEXpressions

## Triggers
vexpression material, dynamic material, conditional material, elemnum material,
attribute driven material, material per prim, lop vexpression, material expression

## Context
LOPs use VEXpressions for dynamic material assignment based on prim attributes. CRITICAL: LOPs iterate prims using `@elemnum`, NOT `@ptnum`. Use VEXpressions in Assign Material LOP's prim pattern or in wrangle LOPs for conditional material logic.

## Code

```python
# Basic VEXpression material assignment via Assign Material LOP
import hou

stage_net = hou.node("/stage")
assign = stage_net.createNode("assignmaterial", "conditional_assign")

# Assign based on prim index using @elemnum (NOT @ptnum in LOPs!)
# @elemnum = prim iteration index in LOP context
assign.parm("primpattern1").set("/geo/pieces/*")
assign.parm("matspecpath1").set("/materials/mat_A")

# VEXpression on prim pattern for filtering:
# Only assign to even-numbered prims
# Use the prim pattern VEXpression field if available
```

```python
# Using Attribute Wrangle LOP for conditional material assignment
import hou

stage_net = hou.node("/stage")

# Attribute Wrangle in LOP context — runs VEX over USD prims
wrangle = stage_net.createNode("attribwrangle", "material_assign_vex")
wrangle.parm("class").set(1)  # Primitives

# CRITICAL: In LOPs, use @elemnum for prim index, NOT @ptnum
# @ptnum does NOT exist in LOP wrangle context
vex_code = '''
// Assign different materials based on prim name or index
// @elemnum = current prim index (LOP-specific)
string prim_path = usd_primpath(0, @elemnum);

// Example: alternate materials based on index
if (@elemnum % 2 == 0) {
    // Set material binding attribute
    usd_setrelationship(0, prim_path, "material:binding",
                        array("/materials/metal"));
} else {
    usd_setrelationship(0, prim_path, "material:binding",
                        array("/materials/rubber"));
}
'''
wrangle.parm("snippet").set(vex_code)
```

```python
# Primvar-driven material assignment
# Use a SOP-level attribute to control material selection in LOPs
import hou

# SOP level: create material_id attribute on geometry
sop_wrangle = hou.node("/obj/geo1").createNode("attribwrangle", "set_mat_id")
sop_wrangle.parm("class").set(1)  # Primitives
sop_wrangle.parm("snippet").set('''
// Assign material ID based on geometry attribute
if (@Cd.r > 0.5) {
    s@material_id = "warm";
} else {
    s@material_id = "cool";
}
''')

# LOP level: read the attribute and assign materials
stage_net = hou.node("/stage")

# Multiple Assign Material LOPs with VEXpression prim patterns
# Pattern 1: warm materials
assign_warm = stage_net.createNode("assignmaterial", "assign_warm")
assign_warm.parm("primpattern1").set('%type:Mesh & %material_id=="warm"')
assign_warm.parm("matspecpath1").set("/materials/warm_mtl")

# Pattern 2: cool materials
assign_cool = stage_net.createNode("assignmaterial", "assign_cool")
assign_cool.setInput(0, assign_warm)
assign_cool.parm("primpattern1").set('%type:Mesh & %material_id=="cool"')
assign_cool.parm("matspecpath1").set("/materials/cool_mtl")
```

```python
# Reading primvars for material decisions via USD API
import hou
from pxr import UsdGeom, UsdShade, Sdf

stage = hou.node("/stage/sopimport1").stage()

# Check what primvars are available on geometry prims
for prim in stage.Traverse():
    if prim.IsA(UsdGeom.Mesh):
        pvAPI = UsdGeom.PrimvarsAPI(prim)
        primvars = pvAPI.GetPrimvars()
        for pv in primvars:
            name = pv.GetPrimvarName()
            val = pv.Get()
            if val is not None:
                print(f"  {prim.GetPath()}: {name} = {val}")

        # Check for material_id primvar specifically
        mat_id_pv = pvAPI.GetPrimvar("material_id")
        if mat_id_pv and mat_id_pv.Get():
            print(f"  -> material_id = {mat_id_pv.Get()}")
```

```python
# @elemnum vs @ptnum reference for LOP users
#
# | Context  | Iterator Variable | Iterates Over       |
# |----------|-------------------|---------------------|
# | SOP      | @ptnum            | Points (geometry)    |
# | SOP      | @primnum          | Primitives (faces)   |
# | LOP      | @elemnum          | USD prims            |
# | LOP      | @ptnum            | DOES NOT EXIST       |
#
# Common mistake: writing @ptnum in a LOP wrangle
# This compiles but iterates nothing or gives wrong results
# ALWAYS use @elemnum in LOP context
```

## Expected Scene Graph
```
/geo/pieces/
  ├─ piece_0  (UsdGeomMesh)
  │    └─ material:binding → /materials/metal  (via @elemnum % 2 == 0)
  ├─ piece_1  (UsdGeomMesh)
  │    └─ material:binding → /materials/rubber (via @elemnum % 2 == 1)
  └─ piece_2  (UsdGeomMesh)
       └─ material:binding → /materials/metal
```

## Common Mistakes
- Using `@ptnum` in LOP wrangles — DOES NOT EXIST in LOP context, use `@elemnum`
- Forgetting that VEXpressions in LOPs operate on USD prims, not SOP geometry
- Using SOP-style group syntax in LOP prim patterns — LOPs use USD collection/path patterns
- Not promoting SOP attributes to primvars — SOP attributes don't automatically become USD primvars
- Writing material bindings as string attributes instead of using `usd_setrelationship`
