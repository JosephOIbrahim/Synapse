# USD Stage Operations

## Prim Hierarchy

Solaris creates USD prims following a naming convention:
```
/sphere1          ← from sphere LOP named "sphere1"
/cube1            ← from cube LOP named "cube1"
/materials/       ← from materiallibrary
/lights/          ← from light LOPs
/cameras/         ← from camera LOPs
/Render/          ← from karmarenderproperties
```

## Common Prim Types

| USD Type | Created By | Notes |
|----------|-----------|-------|
| Sphere | `sphere` LOP | Has `radius` attribute |
| Cube | `cube` LOP | Has `size` attribute |
| Mesh | `sopimport` LOP | Arbitrary geometry |
| Xform | `edit` LOP | Transform group |
| Scope | auto | Organizational grouping |
| DomeLight | `domelight` LOP | Environment light |
| DistantLight | `distantlight` LOP | Directional light |
| RectLight | `rectlight` LOP | Area light |
| Camera | `camera` LOP | Render camera |
| Material | `materiallibrary` | Shader container |

## Transforms

**DO NOT** set `xformOp:translate` directly via USD attribute.
Use an `edit` LOP node instead — it handles the full xform stack correctly.

The `edit` node takes:
- `primpattern`: USD prim path (e.g., `/sphere1`)
- `tx`, `ty`, `tz`: translation
- `rx`, `ry`, `rz`: rotation (degrees)
- `sx`, `sy`, `sz`: scale

## Reading USD Attributes

```python
# Via MCP tool: houdini_get_usd_attribute
# prim_path: "/sphere1"
# attribute_name: "xformOp:transform"
```

Common attributes:
- `xformOp:transform` — 4x4 matrix
- `visibility` — "inherited" or "invisible"
- `purpose` — "default", "render", "proxy", "guide"

## Composition Arcs

| Arc | LOP Node | Use Case |
|-----|----------|----------|
| Reference | `reference` | Import assets under a prim |
| Sublayer | `sublayer` | Merge full layers |
| Payload | `reference` (deferred) | Heavy assets |
| VariantSet | `variantset` | Switchable options |

## Stage Info

The `houdini_stage_info` MCP tool returns all prims and their types.
Useful for verifying scene structure before rendering.
