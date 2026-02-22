# USD Path Expressions vs Houdini Prim Patterns

## Triggers
usd path expression, prim pattern, material path, prim selection, wildcard prim,
collection target, material assignment path, exact prim path, glob pattern lop

## Context
Material bindings require EXACT USD prim paths — not wildcards. Houdini LOPs support both path expressions (glob-like) for node targeting and exact paths for bindings. CRITICAL: material assignment targets must resolve to specific prims.

## Code

```python
# CORRECT: Exact prim paths for material assignment
import hou

assign = hou.node("/stage").createNode("assignmaterial", "mat_assign")

# Exact path — THIS WORKS
assign.parm("primpattern1").set("/geo/hero_asset/mesh_shape")
assign.parm("matspecpath1").set("/materials/hero_mtlx")

# WRONG: Wildcard — material binding doesn't resolve
# assign.parm("primpattern1").set("/geo/hero_asset/*")
# This may work for TARGETING (selecting prims) but the binding
# on each matched prim points to the same material
```

```python
# Understanding the difference: targeting vs binding

# TARGETING (selecting which prims to affect) — wildcards OK
# These patterns select prims for the operation:
targeting_patterns = [
    "/geo/hero_asset/**",           # all descendants
    "/geo/*/mesh_shape",            # any intermediate parent
    "%type:Mesh",                   # all Mesh-type prims
    "/geo/pieces/piece_*",          # wildcard on name
    "%type:Mesh & /geo/**",         # type filter + path filter
]

# BINDING (what material to assign) — MUST be exact path
# The matspecpath is a specific USD material prim:
binding_paths = [
    "/materials/hero_mtlx",         # exact material prim path
    "/materials/chrome",            # exact
    # "/materials/*"                # WRONG — this is not a valid material
]
```

```python
# Finding exact prim paths for material assignment
import hou
from pxr import UsdGeom

stage = hou.node("/stage/merge1").stage()

# List all mesh prims with their exact paths
mesh_paths = []
for prim in stage.Traverse():
    if prim.IsA(UsdGeom.Mesh):
        path = str(prim.GetPath())
        mesh_paths.append(path)
        print(f"Mesh: {path}")

# Use these exact paths in material assignment
# Example output:
# Mesh: /rubbertoy/geo/shape        <- USE THIS in primpattern
# Mesh: /pig/geo/shape              <- USE THIS
# NOT:  /rubbertoy/*                <- DON'T USE wildcard
```

```python
# Prim pattern syntax reference for Houdini LOPs
import hou

# Houdini LOP prim patterns (for node targeting, NOT material binding)
PATTERN_EXAMPLES = {
    # Exact path
    "/geo/hero": "Single specific prim",

    # Wildcard (glob-style)
    "/geo/*": "Direct children of /geo",
    "/geo/**": "All descendants of /geo",
    "/geo/piece_*": "Prims matching name pattern",

    # Type filter
    "%type:Mesh": "All UsdGeomMesh prims",
    "%type:Light": "All light prims",
    "%type:Material": "All material prims",

    # Combined
    "%type:Mesh & /geo/**": "Meshes under /geo",
    "%type:Mesh | %type:BasisCurves": "Meshes or curves",

    # Attribute filter (Houdini-specific)
    '%type:Mesh & @purpose=="render"': "Render-purpose meshes",

    # Collection-based
    "/geo.collection:render_geo": "Prims in a named collection",
}

for pattern, desc in PATTERN_EXAMPLES.items():
    print(f"  {pattern:<45} — {desc}")
```

```python
# Validating that assignment paths resolve to actual prims
import hou
from pxr import UsdGeom

def validate_material_assignment(stage, prim_pattern, material_path):
    """Check that both the target prims and material exist."""
    issues = []

    # Check material exists
    mat_prim = stage.GetPrimAtPath(material_path)
    if not mat_prim.IsValid():
        issues.append(f"Material not found: {material_path}")

    # Check target prims exist
    # For exact paths, check directly
    if not any(c in prim_pattern for c in ['*', '%', '&', '|']):
        # Exact path
        target = stage.GetPrimAtPath(prim_pattern)
        if not target.IsValid():
            issues.append(f"Target prim not found: {prim_pattern}")
            # Suggest similar paths
            parent_path = "/".join(prim_pattern.split("/")[:-1])
            parent = stage.GetPrimAtPath(parent_path)
            if parent.IsValid():
                children = [str(c.GetPath()) for c in parent.GetChildren()]
                if children:
                    issues.append(f"  Did you mean one of: {children[:5]}")
    else:
        # Pattern — count matching prims
        matches = 0
        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                matches += 1
        if matches == 0:
            issues.append(f"Pattern '{prim_pattern}' matched 0 prims")

    if issues:
        print("VALIDATION FAILED:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print(f"OK: '{prim_pattern}' -> '{material_path}'")
        return True

# Usage
stage = hou.node("/stage/merge1").stage()
validate_material_assignment(stage, "/rubbertoy/geo/shape", "/materials/rubber")
validate_material_assignment(stage, "/rubbertoy/*", "/materials/rubber")  # warns
```

## Expected Scene Graph
```
# CORRECT assignment with exact path:
/rubbertoy/geo/shape  (UsdGeomMesh)
  └─ material:binding → /materials/rubber  [resolved, renders correctly]

# INCORRECT assignment with wildcard:
# Wildcard may select prims but binding still needs exact material path
```

## Common Mistakes
- Using `/rubbertoy/*` as material assignment target — must use exact path `/rubbertoy/geo/shape`
- Confusing prim pattern (selects targets) with material path (must be exact)
- Using `**` expecting it to recursively bind materials — it selects prims, each gets the same binding
- Forgetting that Material Library scope affects paths — `/materials/` vs `/mtl/` depends on matlib config
- Not querying actual prim paths from stage before writing assignment — paths from memory may be wrong
