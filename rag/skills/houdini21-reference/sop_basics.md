# Houdini SOP Basics

## Primitive SOP Types

| Node Type | Description | Key Parms |
|-----------|-------------|-----------|
| `sphere` | Polygon sphere | `radx`, `rady`, `radz`, `scale`, `rows`, `cols` |
| `box` | Polygon box | `sizex`, `sizey`, `sizez`, `tx`, `ty`, `tz` |
| `grid` | Polygon grid | `sizex`, `sizey`, `rows`, `cols` |
| `torus` | Polygon torus | `radx`, `rady` |
| `tube` | Polygon tube/cylinder | `radx`, `height`, `cap` |
| `circle` | Polygon circle | `radx`, `rady`, `divs` |
| `line` | Polyline | `dist`, `points` |
| `platonic` | Platonic solids | `type` (tetra/cube/octa/dodeca/icosa) |

## Transform and Deformation

| Node | Description | Key Parms |
|------|-------------|-----------|
| `transform` | Transform geometry | `tx/ty/tz`, `rx/ry/rz`, `sx/sy/sz` |
| `edit` | Interactive point/prim editing | transform gizmo |
| `bend` | Bend geometry along axis | `angle`, `upvector` |
| `twist` | Twist geometry around axis | `twist`, `strength` |
| `lattice` | Lattice deformation | control points |
| `mountain` | Noise-based displacement | `height`, `scale` |
| `peak` | Translate along normals | `dist` |
| `smooth` | Smooth/relax geometry | `strength`, `iterations` |

## Topology Operations

| Node | Description | Key Parms |
|------|-------------|-----------|
| `merge` | Combine multiple inputs | auto |
| `blast` | Delete by group/pattern | `group`, `negate` |
| `dissolve` | Remove edges/faces keeping mesh | `group` |
| `fuse` | Merge nearby points | `dist`, `consolidate` |
| `divide` | Subdivide polygons | `bricker`, `computedual` |
| `polyextrude` | Extrude faces | `dist`, `inset` |
| `polybevel` | Bevel edges/points | `offset`, `segments` |
| `boolean` | CSG operations (union/intersect/subtract) | `booleanop` |
| `remesh` | Retopologize to uniform triangles | `targetsize` |
| `polyfill` | Fill holes in mesh | auto |
| `polyreduce` | Reduce polygon count | `percentage` |
| `subdivide` | Catmull-Clark subdivision | `iterations` |

## Copy and Instancing

| Node | Description | Key Parms |
|------|-------------|-----------|
| `copytopoints` | Instance geo onto points | first input=geo, second=points |
| `copy` | Copy and transform | `ncy` (count), `tx/ty/tz` (per copy) |
| `scatter` | Scatter points on surface | `npts` |
| `foreach_begin`/`end` | Loop over pieces/points | `method` (pieces/count/feedback) |
| `carve` | Cut/trim curves or surfaces | `firstu`, `secondu` |
| `sweep` | Sweep profile along curve | first=backbone, second=cross section |
| `resample` | Resample curve to uniform spacing | `length`, `maxlength` |

### Copy-to-Points Attributes
The `copytopoints` node reads these point attributes from the target points:
- `@P` - Position (required)
- `@orient` - Orientation quaternion (vector4) -- overrides N/up
- `@N` - Normal (direction to point Z-axis toward)
- `@up` - Up vector (twist control with N)
- `@pscale` - Uniform scale
- `@scale` - Non-uniform scale (vector)
- `@trans` - Additional translation offset (vector)

Priority: `orient` > `N`+`up` > `v` > nothing

## Utility Nodes

| Node | Description | Key Parms |
|------|-------------|-----------|
| `null` | Pass-through (output marker) | none |
| `switch` | Switch between inputs | `input` (index) |
| `attribwrangle` | Run VEX code | `snippet`, `class` |
| `attribcreate` | Create/set attribute without VEX | `name`, `type`, `value` |
| `attribpromote` | Convert attribute class | `inclass`, `outclass` |
| `attribtransfer` | Transfer attributes between geos | `pointattribs`, `primattribs` |
| `attribdelete` | Delete attributes | `ptdel`, `primdel` |
| `sort` | Sort points/prims | `ptsort` (by axis, random, etc.) |
| `trail` | Compute velocity from animated geo | `result` (velocity) |
| `timeshift` | Read geometry at different frame | `frame` |
| `filecache` | Cache to disk | `file`, `filemethod` |
| `file` | Read geometry from disk | `file` |

## CRITICAL: SOP vs LOP Parameter Names

SOP and LOP parameter names are DIFFERENT for similar concepts:

| Concept | SOP Name | LOP Name |
|---------|----------|----------|
| Sphere radius | `radx`, `rady`, `radz` | N/A (use edit for scale) |
| Position | `tx`, `ty`, `tz` | via `edit` node |
| Sphere detail | `rows`, `cols` | N/A |
| Box size | `sizex`, `sizey`, `sizez` | N/A |

## Groups

Groups select subsets of geometry for targeted operations.

### Group Types
- **Point group**: Selection of points (`@group_name` in VEX)
- **Prim group**: Selection of primitives
- **Edge group**: Selection of edges (no attribute, only in group parm)
- **Vertex group**: Selection of vertices

### Group Creation
| Node | Description |
|------|-------------|
| `groupcreate` | Create group by bounding box, normal, expression |
| `groupexpression` | Create group by VEX expression |
| `grouprange` | Create group by index range/pattern |
| `groupcombine` | Boolean operations on existing groups |
| `grouppromote` | Convert between point/prim/edge groups |

### Group Syntax in Parameters
Most SOP parameters accept group strings:
- `piece0 piece1` - Named groups (space-separated)
- `0-10` - Point/prim number range
- `@P.y>5` - Expression (ad-hoc group)
- `!group1` - Negate (everything except)
- `*` - All (explicit wildcard)

## VDB (Sparse Volumes)

| Node | Description | Key Parms |
|------|-------------|-----------|
| `vdbfrompolygons` | Mesh to VDB (SDF or fog) | `vdbtype`, `voxelsize` |
| `vdbcombine` | Boolean operations on VDBs | `operation` (union/intersect/subtract) |
| `vdbsmooth` | Smooth VDB fields | `iterations`, `width` |
| `vdbreshape` | Dilate/erode VDB SDF | `offset` |
| `convertVDB` | VDB to polygons | `adaptivity`, `isovalue` |
| `vdbactivate` | Activate/deactivate voxel regions | `region` |

### VDB Workflow (Modeling)
```
polygon_mesh -> vdbfrompolygons -> vdbcombine/vdbsmooth -> convertVDB -> polygon_mesh
```
This is the most reliable way to do complex boolean operations and smooth blending.

## VEX Wrangle Basics

The `attribwrangle` node runs VEX code on geometry.

### Key Parms
- `snippet`: VEX code to execute
- `class`: `point`, `prim`, `vertex`, or `detail`

### Run Over Modes
- **Points**: Code runs once per point. `@ptnum` is current index.
- **Primitives**: Code runs once per prim. `@primnum` is current index.
- **Vertices**: Code runs once per vertex. `@vtxnum` is current index.
- **Detail**: Code runs once for the entire geo. Use for global calculations.

### Common VEX Patterns

```vex
// Set attributes on points
f@density = 1.0;
f@temperature = 2.0;
v@v = set(0, 3, 0);
f@pscale = 0.05;

// Access position
vector pos = @P;

// Random per-point (deterministic from point number)
f@rand = rand(@ptnum);

// Color
v@Cd = set(1, 0, 0);  // red

// Read from second input
vector other_pos = point(1, "P", @ptnum);

// Ramp-driven attribute
f@falloff = chramp("falloff", fit(@P.y, 0, 10, 0, 1));
```

## Volume Rasterize

`volumerasterizeattributes` converts point attributes to volume fields:
- Input: scattered points with float/vector attributes
- `attributes` parm: space-separated list (e.g., `"density temperature flame"`)
- Points MUST have `@pscale` attribute (controls voxel radius per point)

## File Cache

`filecache` SOP writes geometry to disk:
- `file`: Output path (e.g., `$HIP/cache/sim.$F4.bgeo.sc`)
- `filemethod`: `explicit` or `constructed`
- `.bgeo.sc` = Blosc compressed (3-5x smaller than raw)
- Use for simulation caching before Solaris import
- "Read" mode plays back cached frames without recomputing

## For-Each Loops

For iterating over pieces, points, or feedback loops:
```
foreach_begin (method=pieces, piece attrib="name")
    ... operations on each piece ...
foreach_end
```

### Loop Methods
- **By Pieces**: Process each connected component or named piece separately
- **By Count**: Run N iterations (numbered 0 to N-1)
- **Feedback**: Output of each iteration feeds into next (accumulation)

## Performance Tips

- **Pack geometry** (`pack` SOP) for instances -- massively reduces memory and viewport cost
- Use `filecache` liberally for expensive nodes -- iterate faster downstream
- **Groups over blast**: Use groups to isolate work instead of deleting geometry
- **For-each is slow**: Avoid for-each when a VEX wrangle can do the same operation
- **VDB booleans**: Prefer over `boolean` SOP for complex operations -- more stable, faster
- **Compiled blocks**: Wrap for-each in compiled block for 2-5x speedup
- **Viewer LOD**: Use "Display as" > Points or Bounding Box for heavy geo during setup
