# Material Common Errors and Diagnostics

## Triggers
material error, grey shader, default material, material not visible, material debug,
material troubleshoot, material not working, material assignment failed, matlib error

## Context
Consolidated material error patterns with diagnostic code. Covers: grey/default shader appearing, material not visible in Karma, matlib cook error, wrong prim paths, @ptnum vs @elemnum, scope mismatch.

## Code

```python
# Diagnostic 1: Grey/default shader appearing (binding didn't take)
import hou
from pxr import UsdShade, UsdGeom

def diagnose_grey_shader(stage_node_path):
    """Find geometry with missing or broken material bindings."""
    stage = hou.node(stage_node_path).stage()
    issues = []

    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Gprim):
            continue

        binding = UsdShade.MaterialBindingAPI(prim)
        direct = binding.GetDirectBinding()

        if not direct.GetMaterial():
            # No binding at all
            issues.append(f"NO BINDING: {prim.GetPath()}")
        else:
            # Has binding — check if material prim exists
            mat_path = direct.GetMaterialPath()
            mat_prim = stage.GetPrimAtPath(mat_path)
            if not mat_prim.IsValid():
                issues.append(
                    f"BROKEN BINDING: {prim.GetPath()} -> {mat_path} (material prim not found)"
                )
            elif not mat_prim.IsA(UsdShade.Material):
                issues.append(
                    f"WRONG TYPE: {prim.GetPath()} -> {mat_path} "
                    f"(prim is {mat_prim.GetTypeName()}, not Material)"
                )

    if issues:
        print(f"GREY SHADER issues ({len(issues)}):")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("All geometry has valid material bindings")
    return issues

diagnose_grey_shader("/stage/karmarendersettings1")
```

```python
# Diagnostic 2: Material not visible in Karma render
import hou
from pxr import UsdShade

def diagnose_invisible_material(stage_node_path, material_path):
    """Check why a specific material isn't visible in render."""
    stage = hou.node(stage_node_path).stage()
    issues = []

    mat_prim = stage.GetPrimAtPath(material_path)
    if not mat_prim.IsValid():
        issues.append(f"Material prim not found: {material_path}")
        # Suggest similar paths
        parent_path = "/".join(material_path.rsplit("/", 1)[:-1]) or "/"
        parent = stage.GetPrimAtPath(parent_path)
        if parent.IsValid():
            children = [str(c.GetPath()) for c in parent.GetChildren()]
            issues.append(f"  Available materials: {children[:10]}")
        return issues

    mat = UsdShade.Material(mat_prim)

    # Check surface output exists
    surface = mat.GetSurfaceOutput()
    if not surface:
        issues.append(f"No surface output on {material_path}")
        return issues

    # Check shader connection
    sources = surface.GetConnectedSources()
    if not sources:
        issues.append(f"Surface output not connected to any shader")
        return issues

    shader_prim = sources[0][0].GetPrim()
    shader_id = shader_prim.GetAttribute("info:id").Get()
    if not shader_id:
        issues.append(f"Shader at {shader_prim.GetPath()} missing info:id attribute")

    # Check binding strength
    # Find all prims bound to this material
    bound_prims = []
    for prim in stage.Traverse():
        binding = UsdShade.MaterialBindingAPI(prim)
        direct = binding.GetDirectBinding()
        if direct.GetMaterialPath() == material_path:
            strength = direct.GetBindingStrength()
            bound_prims.append((str(prim.GetPath()), strength))

    if not bound_prims:
        issues.append(f"No geometry is bound to {material_path}")
    else:
        print(f"Material {material_path} bound to {len(bound_prims)} prims:")
        for path, strength in bound_prims:
            s = "stronger" if strength == 1 else "weaker"
            print(f"    {path} (strength: {s})")

    if issues:
        print(f"INVISIBLE MATERIAL issues:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print(f"Material {material_path} looks correctly configured")
    return issues

diagnose_invisible_material("/stage/karmarendersettings1", "/materials/hero_mtlx")
```

```python
# Diagnostic 3: matlib cook error (createNode returns None)
import hou

def diagnose_matlib_cook(matlib_path):
    """Check if Material Library needs cooking before child creation."""
    matlib = hou.node(matlib_path)
    if not matlib:
        print(f"Material Library not found: {matlib_path}")
        return

    # Check if matlib has been cooked
    # If not cooked, internal network doesn't exist
    children = matlib.children()

    if not children:
        print("Material Library has no children — likely not cooked yet")
        print("FIX: Call matlib.cook(force=True) BEFORE createNode()")
        print("")
        print("Example:")
        print("  matlib = hou.node('" + matlib_path + "')")
        print("  matlib.cook(force=True)  # CRITICAL")
        print("  subnet = matlib.createNode('subnet', 'my_material')")
    else:
        print(f"Material Library has {len(children)} children — cook OK")
        for child in children:
            print(f"  {child.name()} ({child.type().name()})")

diagnose_matlib_cook("/stage/materiallibrary1")
```

```python
# Diagnostic 4: Wrong prim path in assignment
import hou
from pxr import UsdGeom

def diagnose_path_mismatch(stage_node_path, intended_pattern):
    """Check if a prim pattern matches anything in the stage."""
    stage = hou.node(stage_node_path).stage()

    # Check for common path errors
    issues = []
    suggestions = []

    # Try exact path match
    exact_prim = stage.GetPrimAtPath(intended_pattern)
    if exact_prim.IsValid():
        print(f"Exact match: {intended_pattern} exists ({exact_prim.GetTypeName()})")
        return

    # No exact match — find similar paths
    print(f"No prim found at: {intended_pattern}")

    # Common mistakes
    if intended_pattern.endswith("/*"):
        issues.append("Wildcard /* in material binding — use exact prim path")
        base = intended_pattern[:-2]
        parent = stage.GetPrimAtPath(base)
        if parent.IsValid():
            suggestions = [str(c.GetPath()) for c in parent.GetChildren()]

    elif "/materials/" in intended_pattern.lower() and "/mtl/" not in intended_pattern:
        # Check if materials are under /mtl/ instead
        alt_path = intended_pattern.replace("/materials/", "/mtl/")
        alt_prim = stage.GetPrimAtPath(alt_path)
        if alt_prim.IsValid():
            issues.append(f"Wrong scope: materials are under /mtl/, not /materials/")
            suggestions = [alt_path]

    if not suggestions:
        # Fuzzy search — find all prims and suggest close matches
        all_paths = [str(p.GetPath()) for p in stage.Traverse()]
        target_name = intended_pattern.split("/")[-1]
        suggestions = [p for p in all_paths if target_name in p][:5]

    if issues:
        for issue in issues:
            print(f"  Issue: {issue}")
    if suggestions:
        print(f"  Suggestions: {suggestions}")

diagnose_path_mismatch("/stage/merge1", "/rubbertoy/geo/shape")
diagnose_path_mismatch("/stage/merge1", "/rubbertoy/*")
```

```python
# Diagnostic 5: @ptnum vs @elemnum in LOPs
def diagnose_lop_vex_error(vex_code):
    """Check for common VEX mistakes in LOP context."""
    issues = []

    if "@ptnum" in vex_code:
        issues.append(
            "@ptnum used in LOP context — this does NOT exist in LOPs. "
            "Use @elemnum for prim iteration."
        )

    if "@primnum" in vex_code and "sop" not in vex_code.lower():
        issues.append(
            "@primnum may not work as expected in LOPs. "
            "Use @elemnum for prim index."
        )

    if "shop_materialpath" in vex_code and "s@" not in vex_code:
        issues.append(
            "shop_materialpath should be string type: s@shop_materialpath"
        )

    if issues:
        print("LOP VEX issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("VEX code looks OK for LOP context")

# Test
diagnose_lop_vex_error('@ptnum % 2 == 0')
diagnose_lop_vex_error('@elemnum % 2 == 0')
```

```python
# Master material diagnostic
import hou

def full_material_diagnostic(stage_node_path):
    """Run all material diagnostics."""
    print(f"=== Material Diagnostic: {stage_node_path} ===\n")

    print("1. Grey Shader Check:")
    diagnose_grey_shader(stage_node_path)

    print("\n2. Material Library Health:")
    stage = hou.node(stage_node_path).stage()
    from pxr import UsdShade
    mat_count = sum(1 for p in stage.Traverse() if p.IsA(UsdShade.Material))
    shader_count = sum(1 for p in stage.Traverse() if p.IsA(UsdShade.Shader))
    print(f"  Materials: {mat_count}, Shaders: {shader_count}")

    print("\n3. Binding Summary:")
    from pxr import UsdGeom
    bound = 0
    unbound = 0
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Gprim):
            binding = UsdShade.MaterialBindingAPI(prim)
            if binding.GetDirectBinding().GetMaterial():
                bound += 1
            else:
                unbound += 1
    print(f"  Bound geometry: {bound}, Unbound: {unbound}")

    print("\n=== Diagnostic Complete ===")

full_material_diagnostic("/stage/karmarendersettings1")
```

## Expected Output
```
=== Material Diagnostic: /stage/karmarendersettings1 ===

1. Grey Shader Check:
All geometry has valid material bindings

2. Material Library Health:
  Materials: 3, Shaders: 3

3. Binding Summary:
  Bound geometry: 5, Unbound: 0

=== Diagnostic Complete ===
```

## Common Mistakes
- Not cooking matlib before createNode — returns None, no error message
- Material scope mismatch: matlib creates `/materials/` but assignment targets `/mtl/`
- Using @ptnum in LOP VEXpressions — doesn't exist, use @elemnum
- Binding to wildcard paths expecting per-prim variation — all matched prims get same material
- Not checking binding strength — weaker binding silently loses to existing one
- Assuming material prim name matches Houdini node name — _shader suffix may be appended
