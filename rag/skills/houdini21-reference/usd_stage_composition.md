# USD Stage Composition and Layer Workflows

## Composition Arcs (LIVRPS)

```python
# LIVRPS strength ordering (strongest first):
LIVRPS = {
    "L": {"strength": 1, "arc": "Local opinions",  "example": 'prim.GetAttribute("radius").Set(2.0)'},
    "I": {"strength": 2, "arc": "Inherits",         "example": 'inherits = </class/hero>'},
    "V": {"strength": 3, "arc": "VariantSets",      "example": 'variantSet "color" = { "red" {} "blue" {} }'},
    "R": {"strength": 4, "arc": "References",        "example": 'references = @./assets/chair.usd@'},
    "P": {"strength": 5, "arc": "Payloads",          "example": 'payload = @./heavy_geo.usd@'},
    "S": {"strength": 6, "arc": "Sublayers",         "example": 'subLayers = [@./anim.usd@, @./model.usd@]'},
}
# Key rule: stronger arc's opinion always wins. Local edits override everything.
```

## Layer Stacking Patterns

### Multi-Department Pipeline

Standard production layer order (top = strongest):

```
shot_final.usd          (sublayer - comp's final tweaks)
  shot_fx.usd           (sublayer - FX overrides)
    shot_lighting.usd   (sublayer - lighting department)
      shot_anim.usd     (sublayer - animation curves)
        shot_layout.usd (sublayer - layout positions)
          asset.usd     (reference - model/materials)
```

```python
# Each department only edits their layer.
# Opinions cascade: lighting overrides layout, FX overrides lighting visibility.

# In Houdini/Solaris:
# sublayer1 (LOP) -> sublayer2 (LOP) -> merge (LOP)
# Sublayer: stacks opinions (weaker). Use for department overrides.
# Reference: brings asset under a prim path. Use for asset loading.
# Graft: moves prim subtree to new location. Use for scene assembly.

# Reference vs Sublayer decision:
COMPOSITION_GUIDE = {
    "Loading an asset (chair, tree, character)": "Reference -- isolates under target prim, can instance",
    "Adding department overrides (lighting, FX)": "Sublayer -- stacks on existing stage, opinions merge",
    "Combining multiple shots":                   "Sublayer -- each shot layer contributes to final",
    "Instancing same asset N times":              "Reference + instanceable -- single prototype, many instances",
    "Deferred loading (huge assets)":             "Payload -- like reference but lazy-loaded",
}
```

## Prim Hierarchy Best Practices

### Standard Scene Structure

```
/World
  /cameras
    /render_cam
    /turntable_cam
  /lights
    /key_light
    /fill_light
    /rim_light
    /dome_light
  /geo
    /hero
    /props
      /chair
      /table
    /environment
      /ground
      /walls
  /materials
    /hero_mat
    /props_chrome
    /ground_concrete
```

```python
# Naming conventions:
# - snake_case for prim names (not camelCase)
# - Group by function: /cameras/, /lights/, /geo/, /materials/
# - Assets get own scope: /geo/hero/ not /hero/
# - Materials under /materials/ or /World/materials/

# Common USD prim types
PRIM_TYPES = {
    # Transform
    "Xform":        "Grouping node with transform",
    # Geometry
    "Mesh":         "Polygonal mesh",
    "BasisCurves":  "Curves (hair, wires)",
    "Points":       "Point cloud",
    "Sphere":       "Implicit sphere shape",
    "Cube":         "Implicit cube shape",
    # Lighting
    "DomeLight":    "Environment/HDRI light",
    "DistantLight": "Sun/directional light",
    "RectLight":    "Rectangular area light",
    "DiskLight":    "Disk area light",
    "SphereLight":  "Point/sphere light",
    "CylinderLight":"Tube/strip light",
    # Camera
    "Camera":       "Render camera",
    # Shading
    "Material":     "Material container",
    "Shader":       "Individual shader node",
    # Organization
    "Scope":        "Non-transformable group",
    "GeomSubset":   "Face set for material binding",
    # Rendering
    "RenderProduct":"Output file definition",
    "RenderVar":    "AOV definition",
}
```

## Transforms

### Transform Stack

USD uses an ordered stack of transform operations:

```
xformOp:translate    -> position
xformOp:rotateXYZ   -> rotation (Euler)
xformOp:scale        -> scale
```

The `xformOpOrder` attribute defines execution order (right-to-left):
```python
xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]
# Applied as: Scale first, then Rotate, then Translate
```

### Common Transform Operations

```python
# Houdini Python (inside LOP context)
from pxr import UsdGeom, Gf

stage = hou.pwd().editableStage()
prim = stage.GetPrimAtPath("/World/geo/hero")
xform = UsdGeom.Xformable(prim)

# Set translate
xform.AddTranslateOp().Set(Gf.Vec3d(1.0, 2.0, 3.0))

# Set rotation (degrees)
xform.AddRotateXYZOp().Set(Gf.Vec3f(0, 45, 0))

# Set scale
xform.AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, 1.0))

# Reset transforms
xform.ClearXformOpOrder()
```

## VariantSets

VariantSets provide switchable configurations:

```python
# Define variants
prim = stage.DefinePrim("/World/geo/chair", "Xform")
vset = prim.GetVariantSets().AddVariantSet("style")
vset.AddVariant("modern")
vset.AddVariant("classic")
vset.AddVariant("rustic")

# Set active variant
vset.SetVariantSelection("modern")

# Author inside variant
with vset.GetVariantEditContext():
    # Opinions here only apply when "modern" is selected
    stage.DefinePrim("/World/geo/chair/mesh", "Mesh")
```

In Houdini: `Add Variant` LOP node creates VariantSets. `Set Variant` LOP switches selection.

## Instancing

### Point Instancer (many copies, GPU efficient)

```python
from pxr import UsdGeom

instancer = UsdGeom.PointInstancer.Define(stage, "/World/instances")
instancer.CreatePrototypesRel().SetTargets(["/World/prototypes/tree"])
instancer.CreatePositionsAttr().Set([Gf.Vec3f(0,0,0), Gf.Vec3f(5,0,3)])
instancer.CreateOrientationsAttr().Set([Gf.Quath(1,0,0,0), Gf.Quath(1,0,0,0)])
instancer.CreateScalesAttr().Set([Gf.Vec3f(1,1,1), Gf.Vec3f(0.8,0.8,0.8)])
instancer.CreateProtoIndicesAttr().Set([0, 0])
```

### Native Instancing (shared subtrees)

```python
# Mark prim as instanceable to share subtree (all refs share GPU memory)
prim.SetInstanceable(True)
```

## Visibility and Purpose

```python
# Hide prim (still composed, just invisible)
UsdGeom.Imageable(prim).MakeInvisible()

# Show prim
UsdGeom.Imageable(prim).MakeVisible()

# Purpose: default, render, proxy, guide
UsdGeom.Imageable(prim).GetPurposeAttr().Set("render")
```

```python
# Purpose tokens:          Viewport  Render  Use Case
# "default"                Yes       Yes     Normal geometry
# "render"                 No        Yes     Render-only detail (displacement, subdivision)
# "proxy"                  Yes       No      Viewport stand-in (low-poly)
# "guide"                  Optional  No      Construction guides, debug geo
```

## Material Binding

```python
from pxr import UsdShade

# Bind material to prim
material = UsdShade.Material.Get(stage, "/materials/chrome")
UsdShade.MaterialBindingAPI(prim).Bind(material)

# Bind to GeomSubset (face-level assignment)
subset = UsdGeom.Subset.Define(stage, "/World/geo/hero/face_group")
subset.CreateIndicesAttr().Set([0, 1, 2, 3])
subset.CreateElementTypeAttr().Set("face")
UsdShade.MaterialBindingAPI(subset.GetPrim()).Bind(material)

# Collection-based binding (pattern matching)
UsdShade.MaterialBindingAPI(prim).Bind(
    material,
    bindingName="chrome_bind",
    materialPurpose="full"
)
```

## Layer Operations

```python
# Layer stacking and management in Houdini Python
from pxr import Sdf, Usd

def inspect_stage_layers(stage):
    """List all layers contributing to the stage."""
    root_layer = stage.GetRootLayer()
    print(f"Root layer: {root_layer.identifier}")

    # Sublayers (weakest to strongest)
    for i, sub in enumerate(root_layer.subLayerPaths):
        print(f"  Sublayer {i}: {sub}")

    # Session layer (strongest, temporary edits)
    session = stage.GetSessionLayer()
    if session:
        print(f"Session layer: {session.identifier}")

    # All used layers
    used = stage.GetUsedLayers()
    print(f"\nTotal layers used: {len(used)}")
    for layer in used:
        print(f"  {layer.identifier}")

# inspect_stage_layers(stage)
```

```python
# Create and save individual layers for department pipeline
from pxr import Sdf, Usd

def create_department_layer(stage, department, output_path):
    """Create a new sublayer for a department's edits.
    Department layers stack: lighting > animation > layout."""
    layer = Sdf.Layer.CreateNew(output_path)

    # Add as sublayer (strongest position = index 0)
    root = stage.GetRootLayer()
    root.subLayerPaths.insert(0, output_path)

    # Set edit target to new layer
    stage.SetEditTarget(Usd.EditTarget(layer))
    print(f"Edit target: {department} layer ({output_path})")
    print("All edits now go to this layer only")
    return layer

# create_department_layer(stage, "lighting", "$HIP/layers/lighting.usd")
```

```python
# Configure layer metadata (default prim, up-axis, meters-per-unit)
from pxr import UsdGeom, Usd

def configure_root_layer(stage):
    """Set standard layer metadata."""
    root = stage.GetRootLayer()

    # Default prim (what gets loaded when referenced)
    stage.SetDefaultPrim(stage.GetPrimAtPath("/World"))

    # Up axis (Y-up for most DCCs, Z-up for some game engines)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)

    # Meters per unit (0.01 = centimeters, 1.0 = meters)
    UsdGeom.SetStageMetersPerUnit(stage, 0.01)

    print(f"Default prim: {stage.GetDefaultPrim().GetPath()}")
    print(f"Up axis: {UsdGeom.GetStageUpAxis(stage)}")
    print(f"Meters per unit: {UsdGeom.GetStageMetersPerUnit(stage)}")

# configure_root_layer(stage)
```

```python
# Query composition arcs on a prim
from pxr import Usd, Pcp

def inspect_composition(stage, prim_path):
    """Show all composition arcs affecting a prim (LIVRPS order)."""
    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        return

    query = Usd.PrimCompositionQuery(prim)
    arcs = query.GetCompositionArcs()
    print(f"Composition arcs for {prim_path}: {len(arcs)}")
    for arc in arcs:
        arc_type = arc.GetArcType()
        target = arc.GetTargetLayer()
        target_path = arc.GetTargetPrimPath()
        print(f"  {arc_type}: {target.identifier} -> {target_path}")

# inspect_composition(stage, "/World/geo/hero")
```

```python
# Houdini LOP node creation for common operations
import hou

def create_scene_assembly(stage_path="/stage"):
    """Create standard Solaris scene assembly nodes."""
    stage = hou.node(stage_path)
    if not stage:
        return

    # SOP Import -- bring geometry to stage
    sop_import = stage.createNode("sopimport", "import_hero")
    sop_import.parm("soppath").set("/obj/hero_geo/OUT")

    # Reference -- load external USD asset
    ref = stage.createNode("reference", "ref_environment")
    ref.parm("filepath1").set("$JOB/assets/environment/env.usd")
    ref.parm("primpath1").set("/World/geo/environment")

    # Sublayer -- department override layer
    sublayer = stage.createNode("sublayer", "lighting_layer")
    sublayer.parm("filepath1").set("$HIP/layers/lighting.usd")

    # Configure layer -- set metadata
    config = stage.createNode("configurelayer", "root_config")
    config.parm("defaultprim").set("/World")

    # Prune -- remove unwanted prims
    prune = stage.createNode("prune", "cleanup")
    prune.parm("primpattern1").set("/World/geo/construction_*")

    stage.layoutChildren()
    print("Scene assembly nodes created")


create_scene_assembly()
```

## Common Mistakes
- Sublayer vs reference confusion -- sublayer stacks opinions (departments), reference isolates assets
- Wrong LIVRPS understanding -- local opinions are STRONGEST, sublayers are WEAKEST
- Missing default prim -- referenced assets need a default prim or explicit prim path
- Editing wrong layer -- check stage.GetEditTarget() before authoring opinions
- VariantSet edits outside variant context -- use GetVariantEditContext() context manager
- Instancing without instanceable flag -- prim.SetInstanceable(True) required for shared GPU memory
