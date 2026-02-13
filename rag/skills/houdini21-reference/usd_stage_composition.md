# USD Stage Composition and Layer Workflows

## Composition Arcs (LIVRPS)

USD resolves opinions via **LIVRPS** strength ordering (strongest first):

| Arc | Strength | Use Case | Example |
|-----|----------|----------|---------|
| **L**ocal opinions | 1 (strongest) | Direct attribute edits on a prim | `prim.GetAttribute("radius").Set(2.0)` |
| **I**nherits | 2 | Share properties across prim classes | `inherits = </class/hero>` |
| **V**ariantSets | 3 | Switchable options on a prim | `variantSet "color" = { "red" { ... } "blue" { ... } }` |
| **R**eferences | 4 | Bring in external assets | `references = @./assets/chair.usd@` |
| **P**ayloads | 5 | Deferred-load references (lazy) | `payload = @./heavy_geo.usd@` |
| **S**ublayers | 6 (weakest) | Stack layers in a stage | `subLayers = [@./anim.usd@, @./model.usd@]` |

**Key rule**: A stronger arc's opinion always wins. Local edits override everything.

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

Each department only edits their layer. Opinions cascade: lighting can override layout positions, FX can override lighting visibility.

### In Houdini/Solaris

```
sublayer1 (LOP) -> sublayer2 (LOP) -> merge (LOP)
```

- **Sublayer**: Stacks opinions (weaker than existing). Use for department overrides.
- **Reference**: Brings in an asset under a prim path. Use for asset loading.
- **Graft**: Moves a prim subtree to a new location. Use for scene assembly.

### Reference vs Sublayer Decision

| Scenario | Use | Why |
|----------|-----|-----|
| Loading an asset (chair, tree, character) | Reference | Isolates asset under target prim, can instance |
| Adding department overrides (lighting, FX) | Sublayer | Stacks on existing stage, opinions merge |
| Combining multiple shots | Sublayer | Each shot layer contributes to final |
| Instancing same asset N times | Reference + instanceable | Single prototype, many instances |
| Deferred loading (huge assets) | Payload | Like reference but lazy-loaded |

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

### Naming Conventions

- Use **snake_case** for prim names (not camelCase)
- Group by function: `/cameras/`, `/lights/`, `/geo/`, `/materials/`
- Assets get their own scope: `/geo/hero/` not `/hero/`
- Materials live under `/materials/` or `/World/materials/`

## Common Prim Types

| Type | Category | Purpose |
|------|----------|---------|
| `Xform` | Transform | Grouping node with transform |
| `Mesh` | Geometry | Polygonal mesh |
| `BasisCurves` | Geometry | Curves (hair, wires) |
| `Points` | Geometry | Point cloud |
| `Sphere`, `Cube`, `Cylinder`, `Cone`, `Capsule` | Geometry | Implicit shapes |
| `DomeLight` | Lighting | Environment/HDRI light |
| `DistantLight` | Lighting | Sun/directional |
| `RectLight` | Lighting | Area light (rectangular) |
| `DiskLight` | Lighting | Area light (disk) |
| `SphereLight` | Lighting | Point/sphere light |
| `CylinderLight` | Lighting | Tube/strip light |
| `Camera` | Camera | Render camera |
| `Material` | Shading | Material container |
| `Shader` | Shading | Individual shader node |
| `Scope` | Organization | Non-transformable group |
| `GeomSubset` | Geometry | Face set for material binding |
| `RenderProduct` | Rendering | Output file definition |
| `RenderVar` | Rendering | AOV definition |

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

Mark a prim as instanceable to share its subtree:
```python
prim.SetInstanceable(True)
```

All references to the same asset with `instanceable=True` share GPU memory.

## Visibility and Purpose

```python
# Hide prim (still composed, just invisible)
UsdGeom.Imageable(prim).MakeInvisible()

# Show prim
UsdGeom.Imageable(prim).MakeVisible()

# Purpose: default, render, proxy, guide
UsdGeom.Imageable(prim).GetPurposeAttr().Set("render")
```

| Purpose | Viewport | Render | Use Case |
|---------|----------|--------|----------|
| `default` | Yes | Yes | Normal geometry |
| `render` | No | Yes | Render-only detail (displacement, subdivision) |
| `proxy` | Yes | No | Viewport stand-in (low-poly) |
| `guide` | Optional | No | Construction guides, debug geo |

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

## Common USD Attributes

| Attribute | Type | Prim Types | Description |
|-----------|------|------------|-------------|
| `xformOp:translate` | double3 | Any Xformable | Position |
| `xformOp:rotateXYZ` | float3 | Any Xformable | Euler rotation |
| `xformOp:scale` | float3 | Any Xformable | Scale |
| `visibility` | token | Any Imageable | "inherited" or "invisible" |
| `purpose` | token | Any Imageable | "default", "render", "proxy", "guide" |
| `extent` | float3[] | Boundable | Bounding box [min, max] |
| `doubleSided` | bool | Mesh | Render both sides |
| `subdivisionScheme` | token | Mesh | "catmullClark", "loop", "bilinear", "none" |
| `faceVertexCounts` | int[] | Mesh | Vertex count per face |
| `faceVertexIndices` | int[] | Mesh | Vertex indices |
| `points` | point3f[] | Mesh/Points | Point positions |
| `normals` | normal3f[] | Mesh | Surface normals |

## Houdini LOP Node Quick Reference

| Node | Purpose | When to Use |
|------|---------|-------------|
| `sopimport` | Bring SOP geo to stage | First step for any SOP geometry |
| `reference` | Reference a USD file | Loading external assets |
| `sublayer` | Stack a USD layer | Department overrides |
| `edit` | Modify existing prims | Transform, visibility, attribute edits |
| `material_library` | Create materials | MaterialX/UsdPreviewSurface authoring |
| `assign_material` | Bind material to prims | Material assignment (supports patterns) |
| `light` | Create USD lights | Any light type |
| `camera` | Create USD camera | Render cameras |
| `render_settings` | Configure render | Karma settings, resolution, samples |
| `usdrender` | Render ROP | Trigger Karma render |
| `prune` | Remove prims | Clean up unwanted geometry |
| `configure_layer` | Set layer metadata | Default prim, up-axis, meters-per-unit |
| `graft` | Move prim subtree | Restructure hierarchy |
| `collection` | Define prim collections | For light linking, material binding |
