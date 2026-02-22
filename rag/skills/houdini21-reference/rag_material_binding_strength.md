# Material Binding Strength Override

## Triggers
material binding, binding strength, material override, material not working,
material not applying, default material, stronger than descendants, weaker than descendants,
unassign material, clear material

## Context
When re-assigning materials in Solaris, existing bindings may take precedence. The Assign Material LOP's Strength parameter controls binding priority. Use "strongerThanDescendants" to override existing bindings, or Unassign Material LOP to clear them first.

## Code

```python
# Assign material with strength override
import hou

stage_net = hou.node("/stage")

# Create Assign Material LOP
assign_mat = stage_net.createNode("assignmaterial", "override_material")

# Set primitives target — MUST use exact USD prim path
assign_mat.parm("primpattern1").set("/geo/hero_asset/shape")

# Set material path (full prim path in scene graph)
assign_mat.parm("matspecpath1").set("/materials/hero_mtlx")

# CRITICAL: Override existing bindings
# "weakerThanDescendants" — new binding loses to existing child bindings
# "strongerThanDescendants" — new binding overrides all descendant bindings
assign_mat.parm("bindingstrength1").set("strongerThanDescendants")
```

```python
# Checking current binding strength on a prim
import hou
from pxr import UsdShade

stage = hou.node("/stage/assignmaterial1").stage()

prim = stage.GetPrimAtPath("/geo/hero_asset/shape")
binding_api = UsdShade.MaterialBindingAPI(prim)

# Get direct binding
direct_binding = binding_api.GetDirectBinding()
if direct_binding.GetMaterial():
    mat_path = direct_binding.GetMaterialPath()
    strength = direct_binding.GetBindingStrength()
    print(f"Material: {mat_path}")
    print(f"Strength: {strength}")
    # UsdShade.Tokens.weakerThanDescendants = 0
    # UsdShade.Tokens.strongerThanDescendants = 1
else:
    print("No material binding on this prim")
```

```python
# Unassign Material LOP — clear existing bindings before re-assigning
import hou

stage_net = hou.node("/stage")

# First: clear existing material
unassign = stage_net.createNode("assignmaterial", "clear_material")
unassign.parm("primpattern1").set("/geo/hero_asset/**")
unassign.parm("matspecpath1").set("")  # empty path = unbind

# Then: assign new material (wired after unassign)
assign = stage_net.createNode("assignmaterial", "new_material")
assign.setInput(0, unassign)
assign.parm("primpattern1").set("/geo/hero_asset/shape")
assign.parm("matspecpath1").set("/materials/new_mtlx")
assign.parm("bindingstrength1").set("strongerThanDescendants")
```

```python
# Debugging: list all material bindings in stage
import hou
from pxr import UsdShade

stage = hou.node("/stage/assignmaterial1").stage()

print("Material bindings in stage:")
for prim in stage.Traverse():
    binding_api = UsdShade.MaterialBindingAPI(prim)
    direct = binding_api.GetDirectBinding()
    if direct.GetMaterial():
        mat_path = direct.GetMaterialPath()
        strength = direct.GetBindingStrength()
        strength_name = "stronger" if strength == 1 else "weaker"
        print(f"  {prim.GetPath()} -> {mat_path} ({strength_name})")
```

## Expected Scene Graph
```
/geo/hero_asset/shape  (UsdGeomMesh)
  └─ material:binding → /materials/hero_mtlx  [strength: strongerThanDescendants]
/materials/hero_mtlx/  (UsdShadeMaterial)
  └─ mtlxsurface (UsdShadeShader)
```

## Common Mistakes
- Not setting binding strength when overriding — default is "weakerThanDescendants" which loses to existing bindings
- Using `strongerThanDescendants` everywhere — can make later overrides impossible
- Trying to unbind with `None` instead of empty string `""` in matspecpath
- Forgetting that binding strength is per-assignment, not per-material — same material can have different strengths on different prims
