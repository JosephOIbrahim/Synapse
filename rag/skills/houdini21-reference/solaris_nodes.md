# Solaris/LOP Node Types Reference

## Geometry

| Node Type | Description | Key Parms |
|-----------|-------------|-----------|
| `sphere` | USD Sphere prim | `tx`, `ty`, `tz` (via edit) |
| `cube` | USD Cube prim | `tx`, `ty`, `tz` (via edit) |
| `sopimport` | Import SOP geometry to LOPs | `soppath` |
| `null` | Pass-through / output marker | none |
| `merge` | Combine multiple inputs | auto |

**IMPORTANT:** There is NO `grid` or `plane` LOP node.
Use a cube with `sy=0.01` for ground planes.

## Lights

| Node Type | USD Type | Use Case |
|-----------|----------|----------|
| `domelight` | DomeLight | Environment/HDRI |
| `distantlight` | DistantLight | Sun/directional |
| `rectlight` | RectLight | Area light |
| `disklight` | DiskLight | Disk area light |
| `cylinderlight` | CylinderLight | Tube light |
| `spherelight` | SphereLight | Point light |

## Camera

| Node Type | Description | Key Parms |
|-----------|-------------|-----------|
| `camera` | USD Camera | `focalLength`, `fStop`, `tx/ty/tz`, `rx/ry/rz` |

## Materials

| Node Type | Description | Key Parms |
|-----------|-------------|-----------|
| `materiallibrary` | Container for shaders | children are shader nodes |
| `mtlxstandard_surface` | MaterialX PBR shader | `base_colorr/g/b`, `metalness`, `specular_roughness` |
| `assignmaterial` | Assign material to prims | `primpattern1`, `matspecpath1` |

**GOTCHA:** After creating `materiallibrary`, call `matlib.cook(force=True)` before creating child shader nodes. Otherwise `createNode()` returns `None`.

## Scene Structure

| Node Type | Description | Key Parms |
|-----------|-------------|-----------|
| `edit` | Transform/modify prims | `primpattern`, `tx/ty/tz`, `rx/ry/rz`, `sx/sy/sz` |
| `reference` | Reference external USD | `filepath1`, `primpath` |
| `sublayer` | Sublayer external USD | `filepath1` |

## Render

| Node Type | Description | Key Parms |
|-----------|-------------|-----------|
| `karmarenderproperties` | Karma render settings | `engine`, sample counts |
| `usdrender_rop` | Render driver (in /stage) | `loppath`, `outputimage` |

Note: `usdrender` in `/out` context is the standard render ROP.
