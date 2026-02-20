# Karma Property Namespaces

## Triggers
karma namespace, karma:object, karma:light, per-prim render property, render visibility,
matte object, phantom object, karma property, edit properties render

## Context
Karma uses namespaced USD properties for per-prim render control. `karma:object:` for geometry visibility/matte/phantom. `karma:light:` for light-specific overrides. Set these via Edit Properties LOP or USD API.

## Code

```python
# Setting karma per-prim properties via Edit Properties LOP
import hou

stage_net = hou.node("/stage")

# Create Edit Properties LOP to set karma render properties
edit_props = stage_net.createNode("editproperties", "karma_visibility")

# Target specific prims
edit_props.parm("primpattern").set("/geo/hero_mesh")

# --- Common karma:object: properties ---

# Visibility — hide from camera but keep in reflections/shadows
# Values: -1 (inherited), 0 (invisible), 1 (visible)
edit_props.parm("xn__karmaobjectvisibility_control_84b").set("set")
edit_props.parm("xn__karmaobjectvisibility_74b").set(1)

# Matte — object appears as solid color holdout (for compositing)
edit_props.parm("xn__karmaobjectmatte_control_l1b").set("set")
edit_props.parm("xn__karmaobjectmatte_k1b").set(0)  # 0=off, 1=on

# Phantom — invisible to camera but casts shadows and appears in reflections
edit_props.parm("xn__karmaobjectphantom_control_r1b").set("set")
edit_props.parm("xn__karmaobjectphantom_q1b").set(0)

# Shadow visibility
edit_props.parm("xn__karmaobjectshadow_control_p1b").set("set")
edit_props.parm("xn__karmaobjectshadow_o1b").set(1)

# Reflection visibility
edit_props.parm("xn__karmaobjectreflect_control_s1b").set("set")
edit_props.parm("xn__karmaobjectreflect_r1b").set(1)
```

```python
# Setting karma properties via USD API directly
import hou
from pxr import Usd, Sdf

lop_node = hou.node("/stage/editproperties1")
stage = lop_node.editableStage()

prim = stage.GetPrimAtPath("/geo/hero_mesh")

# karma:object:visibility (int)
vis_attr = prim.CreateAttribute(
    "karma:object:visibility",
    Sdf.ValueTypeNames.Int
)
vis_attr.Set(1)

# karma:object:matte (bool)
matte_attr = prim.CreateAttribute(
    "karma:object:matte",
    Sdf.ValueTypeNames.Bool
)
matte_attr.Set(False)

# karma:object:phantom (bool)
phantom_attr = prim.CreateAttribute(
    "karma:object:phantom",
    Sdf.ValueTypeNames.Bool
)
phantom_attr.Set(False)


# --- karma:light: properties ---
light_prim = stage.GetPrimAtPath("/lights/key_light")

# Light contribution multiplier
light_prim.CreateAttribute(
    "karma:light:contribution",
    Sdf.ValueTypeNames.Float
).Set(1.0)

# Light shadow enable
light_prim.CreateAttribute(
    "karma:light:shadow:enable",
    Sdf.ValueTypeNames.Bool
).Set(True)
```

```python
# Reading karma properties from a stage
import hou
from pxr import Usd

stage = hou.node("/stage/karmarendersettings1").stage()

# Query all prims with karma properties
for prim in stage.Traverse():
    karma_attrs = [
        a for a in prim.GetAttributes()
        if a.GetName().startswith("karma:")
    ]
    if karma_attrs:
        print(f"\n{prim.GetPath()}:")
        for attr in karma_attrs:
            val = attr.Get()
            print(f"  {attr.GetName()} = {val}")
```

```python
# Common karma:object property reference
# Property Name (USD)                    | Encoded Houdini Parm        | Type | Default
# karma:object:visibility                | xn__karmaobjectvisibility   | int  | -1 (inherit)
# karma:object:matte                     | xn__karmaobjectmatte        | bool | False
# karma:object:phantom                   | xn__karmaobjectphantom      | bool | False
# karma:object:shadow                    | xn__karmaobjectshadow       | int  | 1
# karma:object:reflect                   | xn__karmaobjectreflect      | int  | 1
# karma:object:refract                   | xn__karmaobjectrefract      | int  | 1
# karma:object:diffuse                   | xn__karmaobjectdiffuse      | int  | 1
# karma:object:volume                    | xn__karmaobjectvolume       | int  | 1
# karma:object:unseen                    | xn__karmaobjectunseen       | bool | False
```

## Expected Scene Graph
```
/geo/hero_mesh  (UsdGeomMesh)
  ├─ karma:object:visibility = 1
  ├─ karma:object:matte = False
  └─ karma:object:phantom = False
/lights/key_light  (UsdLuxDistantLight)
  ├─ karma:light:contribution = 1.0
  └─ karma:light:shadow:enable = True
```

## Common Mistakes
- Using friendly names (`karma:object:visibility`) in Houdini parm calls — must use encoded names (`xn__karmaobjectvisibility_74b`)
- Forgetting the `_control` parm — must set both `xn__..._control` to `"set"` AND the value parm
- Setting visibility to 0 expecting it to still cast shadows — visibility=0 removes from ALL ray types
- Using phantom when you want matte, or vice versa — phantom=invisible+shadows+reflections, matte=solid holdout
