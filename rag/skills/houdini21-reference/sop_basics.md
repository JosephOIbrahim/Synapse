# Houdini SOP Basics

## Common SOP Node Types

| Node Type | Description | Key Parms |
|-----------|-------------|-----------|
| `sphere` | Polygon sphere | `radx`, `rady`, `radz`, `scale`, `rows`, `cols` |
| `box` | Polygon box | `sizex`, `sizey`, `sizez`, `tx`, `ty`, `tz` |
| `grid` | Polygon grid | `sizex`, `sizey`, `rows`, `cols` |
| `torus` | Polygon torus | `radx`, `rady` |
| `tube` | Polygon tube | `radx`, `height` |
| `circle` | Polygon circle | `radx`, `rady` |
| `scatter` | Scatter points on surface | `npts` |
| `null` | Pass-through (output marker) | none |
| `merge` | Combine inputs | auto |
| `transform` | Transform geometry | `tx/ty/tz`, `rx/ry/rz`, `sx/sy/sz` |
| `attribwrangle` | Run VEX code | `snippet`, `class` |
| `filecache` | Cache to disk | `file`, `filemethod` |

## CRITICAL: SOP vs LOP Parameter Names

SOP and LOP parameter names are DIFFERENT for similar concepts:

| Concept | SOP Name | LOP Name |
|---------|----------|----------|
| Sphere radius | `radx`, `rady`, `radz` | N/A (use edit for scale) |
| Position | `tx`, `ty`, `tz` | via `edit` node |
| Sphere detail | `rows`, `cols` | N/A |
| Box size | `sizex`, `sizey`, `sizez` | N/A |

## VEX Wrangle Basics

The `attribwrangle` node runs VEX code on geometry.

### Key Parms
- `snippet`: VEX code to execute
- `class`: `point`, `prim`, `vertex`, or `detail`

### Common VEX Patterns

```vex
// Set attributes on points
f@density = 1.0;
f@temperature = 2.0;
v@v = set(0, 3, 0);
f@pscale = 0.05;

// Access position
vector pos = @P;

// Random per-point
f@rand = rand(@ptnum);

// Color
v@Cd = set(1, 0, 0);  // red
```

## Volume Rasterize

`volumerasterizeattributes` converts point attributes to volume fields:
- Input: scattered points with float/vector attributes
- `attributes` parm: space-separated list (e.g., `"density temperature flame"`)
- Points MUST have `@pscale` attribute

## File Cache

`filecache` SOP writes geometry to disk:
- `file`: Output path (e.g., `$HIP/cache/sim.$F4.bgeo.sc`)
- `filemethod`: `explicit` or `constructed`
- Use for simulation caching before Solaris import
