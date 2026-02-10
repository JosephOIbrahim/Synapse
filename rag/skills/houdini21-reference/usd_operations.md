# USD Stage Operations

## Prim Hierarchy

Solaris creates USD prims following a naming convention:
```
/sphere1          <- from sphere LOP named "sphere1"
/cube1            <- from cube LOP named "cube1"
/materials/       <- from materiallibrary
/lights/          <- from light LOPs
/cameras/         <- from camera LOPs
/Render/          <- from karmarenderproperties
```

### Scene Organization Best Practice
```
/World/
  /geo/           <- all geometry (meshes, instances)
  /lights/        <- all lights
  /cameras/       <- all cameras
  /materials/     <- all materials
/Render/          <- render settings
```
Use `scene_import` or manual hierarchy to enforce this structure.

## Common Prim Types

| USD Type | Created By | Notes |
|----------|-----------|-------|
| Sphere | `sphere` LOP | Has `radius` attribute |
| Cube | `cube` LOP | Has `size` attribute |
| Mesh | `sopimport` LOP | Arbitrary geometry from SOPs |
| Xform | `edit` LOP | Transform group |
| Scope | auto | Organizational grouping (no transform) |
| DomeLight | `domelight` LOP | Environment light |
| DistantLight | `distantlight` LOP | Directional light |
| RectLight | `rectlight` LOP | Area light |
| SphereLight | `spherelight` LOP | Point/sphere light |
| DiskLight | `disklight` LOP | Disk area light |
| CylinderLight | `cylinderlight` LOP | Tube light |
| Camera | `camera` LOP | Render camera |
| Material | `materiallibrary` | Shader container |

## Transforms

**DO NOT** set `xformOp:translate` directly via USD attribute.
Use an `edit` LOP node instead -- it handles the full xform stack correctly.

The `edit` node takes:
- `primpattern`: USD prim path (e.g., `/sphere1`)
- `tx`, `ty`, `tz`: translation
- `rx`, `ry`, `rz`: rotation (degrees)
- `sx`, `sy`, `sz`: scale

### Transform Order
USD xformOps apply in authored order. Houdini's `edit` node writes:
```
xformOp:translate, xformOp:rotateXYZ, xformOp:scale
```
This means: scale first, then rotate, then translate (read right to left).

## USD Attributes

### Reading Attributes
```python
# Via MCP tool: houdini_get_usd_attribute
# prim_path: "/sphere1"
# attribute_name: "xformOp:transform"
```

### Common Attributes
- `xformOp:transform` -- 4x4 matrix (local transform)
- `xformOp:translate` -- Translation vector
- `xformOp:rotateXYZ` -- Rotation in degrees
- `xformOp:scale` -- Scale vector
- `visibility` -- `"inherited"` or `"invisible"`
- `purpose` -- `"default"`, `"render"`, `"proxy"`, `"guide"`

### Light Attributes (encoded names)
- `inputs:intensity` -> `xn__inputsintensity_i0a` (always 1.0)
- `inputs:exposure` -> `xn__inputsexposure_vya` (brightness control)
- `inputs:color` -> `xn__inputscolor_kya` (vec3)
- `inputs:texture:file` -> `xn__inputstexturefile_i1a` (dome light HDRI)

### Material Attributes
- `material:binding` -- Material assignment (path to Material prim)
- `inputs:diffuseColor` -- Base color on shader
- `inputs:metallic` -- Metalness (0-1)
- `inputs:roughness` -- Roughness (0-1)

## Visibility and Purpose

### Visibility
- `inherited`: Visible (uses parent visibility)
- `invisible`: Hidden from all rendering

Set via `edit` LOP or `houdini_modify_usd_prim` with `active=False` to deactivate entirely.

### Purpose
| Purpose | Viewport | Render | Use Case |
|---------|----------|--------|----------|
| `default` | Yes | Yes | Normal geometry |
| `render` | No | Yes | Render-only detail (displacement, hair) |
| `proxy` | Yes | No | Low-res viewport stand-in |
| `guide` | Optional | No | Wireframe helpers, construction lines |

Set via `houdini_modify_usd_prim(prim_path, purpose="proxy")`.

## Composition Arcs (LIVRPS)

USD composition strength (strongest to weakest):

| Arc | Strength | LOP Node | Use Case |
|-----|----------|----------|----------|
| **L**ocal | Strongest | `edit`, attribute set | Direct overrides |
| **I**nherits | 2nd | `inheritsfrom` | Shared defaults |
| **V**ariantSets | 3rd | `variantset` | Switchable options |
| **R**eferences | 4th | `reference` | Import assets under a prim |
| **P**ayloads | 5th | `reference` (deferred) | Heavy assets, lazy-load |
| **S**ublayers | Weakest | `sublayer` | Merge full layers |

### Key Rules
- Stronger arcs override weaker ones on the same prim+attribute
- `Local` opinions always win -- this is how `edit` overrides referenced assets
- `Reference` imports an asset and places it at a specific location
- `Sublayer` merges entire stage layers (good for department overrides: anim, lighting, FX)

### Practical Layer Stacking
```
anim.usd (sublayer) --> layout.usd (sublayer) --> lighting.usd (sublayer) --> final.usd
```
Each department sublayers their work. Later sublayers are stronger (win on conflict).

## Material Binding

### Via MCP Tool
```python
# houdini_assign_material
# prim_pattern: "/World/geo/*"
# material_path: "/materials/chrome"
```

### Binding Strength
- Direct binding on a prim overrides inherited bindings from parent
- Collection-based binding can target multiple prims with one rule
- `purpose` binding targets specific render passes (preview vs full)

## Stage Info

The `houdini_stage_info` MCP tool returns all prims and their types.
Useful for verifying scene structure before rendering.

## Common LOP Nodes

| Node | Description | Key Parms |
|------|-------------|-----------|
| `sopimport` | Import SOP geometry to USD | `soppath` |
| `edit` | Edit prim transforms/attributes | `primpattern`, `tx/ty/tz` |
| `merge` | Merge multiple LOP streams | auto |
| `reference` | Reference external USD file | `filepath`, `primpath` |
| `sublayer` | Sublayer USD file | `filepath` |
| `materiallibrary` | Create materials | shader type, params |
| `assignmaterial` | Bind material to geometry | `primpattern`, `materialpath` |
| `rendergeometrysettings` | Set render visibility/subdiv | `primpattern` |
| `karmarenderproperties` | Karma quality settings | samples, bounces |
| `scene_import` | Import entire OBJ-level scene | `objects` |
| `null` | Output marker (set as display) | none |

## USD File Operations

### Export to USD
```python
# Use rop_usdoutput or usdrender ROP
# Set outputfile parm to: $HIP/export/scene.usd
```

### File Formats
| Extension | Description | Use Case |
|-----------|-------------|----------|
| `.usd` | Auto-detect (binary or ASCII) | General |
| `.usda` | ASCII (human-readable) | Debug, version control |
| `.usdc` | Binary (Crate format) | Production (smaller, faster) |
| `.usdz` | Zipped package | Distribution, AR/web |
