# Houdini SOP Basics

## Triggers
sop, geometry, sphere, box, grid, transform, copy to points, scatter, merge,
boolean, extrude, bevel, wrangle, attrib, group, VDB, for each, cache, pack

## Context
SOP (Surface Operator) fundamentals in Houdini: primitive creation, transforms,
topology operations, copy/instancing, groups, VDB workflows, VEX wrangles,
and caching. All code is Houdini Python.

## Code

```python
# Create primitive geometry SOPs
import hou

geo = hou.node("/obj/geo1")
if not geo:
    geo = hou.node("/obj").createNode("geo", "geo1")

# Sphere
sphere = geo.createNode("sphere", "my_sphere")
sphere.parm("radx").set(1.0)
sphere.parm("rady").set(1.0)
sphere.parm("radz").set(1.0)
sphere.parm("rows").set(24)
sphere.parm("cols").set(48)

# Box
box = geo.createNode("box", "my_box")
box.parm("sizex").set(2.0)
box.parm("sizey").set(3.0)
box.parm("sizez").set(1.0)
box.parm("tx").set(0)
box.parm("ty").set(1.5)

# Grid
grid = geo.createNode("grid", "my_grid")
grid.parm("sizex").set(10.0)
grid.parm("sizey").set(10.0)
grid.parm("rows").set(50)
grid.parm("cols").set(50)

# Tube / Cylinder
tube = geo.createNode("tube", "my_tube")
tube.parm("radx").set(0.5)
tube.parm("height").set(2.0)
tube.parm("cap").set(1)  # Close ends

# Torus
torus = geo.createNode("torus", "my_torus")
torus.parm("radx").set(1.5)
torus.parm("rady").set(0.5)

geo.layoutChildren()
```

```python
# Transform and deformation
import hou

geo = hou.node("/obj/geo1")
box = geo.node("my_box")

# Transform SOP
xform = geo.createNode("transform", "move_it")
xform.setInput(0, box)
xform.parm("tx").set(3.0)
xform.parm("ty").set(1.0)
xform.parm("ry").set(45.0)    # Rotate 45 degrees around Y
xform.parm("sx").set(2.0)     # Scale 2x in X

# Mountain (noise displacement)
mountain = geo.createNode("mountain", "noisy_surface")
mountain.setInput(0, geo.node("my_grid"))
mountain.parm("height").set(0.5)
mountain.parm("elementsize").set(2.0)

# Peak (translate along normals)
peak = geo.createNode("peak", "inflate")
peak.setInput(0, geo.node("my_sphere"))
peak.parm("dist").set(0.2)

# Smooth
smooth = geo.createNode("smooth", "relax")
smooth.setInput(0, mountain)
smooth.parm("strength").set(0.5)
smooth.parm("iterations").set(5)

geo.layoutChildren()
```

```python
# Topology operations: extrude, bevel, boolean, subdivide
import hou

geo = hou.node("/obj/geo1")

# Poly extrude
extrude = geo.createNode("polyextrude", "extrude_faces")
extrude.setInput(0, geo.node("my_box"))
extrude.parm("dist").set(0.5)     # Extrusion distance
extrude.parm("inset").set(0.1)    # Inset before extruding

# Poly bevel
bevel = geo.createNode("polybevel", "bevel_edges")
bevel.setInput(0, extrude)
bevel.parm("offset").set(0.05)
bevel.parm("divisions").set(3)    # Subdivision segments

# Boolean (CSG union/intersect/subtract)
bool_sop = geo.createNode("boolean", "subtract")
bool_sop.setInput(0, geo.node("my_box"))
bool_sop.setInput(1, geo.node("my_sphere"))
bool_sop.parm("booleanop").set(2)  # 0=union, 1=intersect, 2=subtract

# Subdivide (Catmull-Clark)
subdiv = geo.createNode("subdivide", "smooth_subdiv")
subdiv.setInput(0, bevel)
subdiv.parm("iterations").set(2)

# Remesh to uniform triangles
remesh = geo.createNode("remesh", "uniform_tris")
remesh.setInput(0, geo.node("my_sphere"))
remesh.parm("targetsize").set(0.1)

# Poly reduce
reduce = geo.createNode("polyreduce", "decimate")
reduce.setInput(0, subdiv)
reduce.parm("percentage").set(50.0)  # Keep 50% of polys

geo.layoutChildren()
```

```python
# Copy-to-points and instancing
import hou

geo = hou.node("/obj/geo1")

# Scatter points on a grid
scatter = geo.createNode("scatter", "scatter_pts")
scatter.setInput(0, geo.node("my_grid"))
scatter.parm("npts").set(200)

# Set instance attributes on scattered points
wrangle = geo.createNode("attribwrangle", "instance_attrs")
wrangle.setInput(0, scatter)
wrangle.parm("snippet").set('''
// Copy-to-points reads these attributes from target points:
//   @P       -- position (required)
//   @orient  -- quaternion orientation (overrides N/up)
//   @N       -- normal (Z-axis direction)
//   @up      -- up vector (twist control with N)
//   @pscale  -- uniform scale
//   @scale   -- non-uniform scale (vector3)
// Priority: orient > N+up > v > nothing

f@pscale = fit01(rand(@ptnum), 0.5, 2.0);        // Random scale
v@N = set(0, 1, 0);                               // Point up
v@Cd = set(rand(@ptnum), rand(@ptnum+1), 0.5);    // Random color
''')

# Copy geometry to points (instancing)
copy = geo.createNode("copytopoints", "instance_trees")
copy.setInput(0, geo.node("my_sphere"))   # Source geometry
copy.setInput(1, wrangle)                  # Target points
copy.parm("pack").set(1)                   # Pack instances (massive memory savings)

geo.layoutChildren()
```

```python
# Merge, blast, fuse, dissolve
import hou

geo = hou.node("/obj/geo1")

# Merge multiple inputs
merge = geo.createNode("merge", "combine")
merge.setInput(0, geo.node("my_box"))
merge.setInput(1, geo.node("my_sphere"))
merge.setInput(2, geo.node("my_torus"))

# Blast (delete by group or pattern)
blast = geo.createNode("blast", "delete_bottom")
blast.setInput(0, merge)
blast.parm("group").set("@P.y<0")  # Delete points below Y=0
blast.parm("negate").set(0)         # 0=delete matching, 1=keep matching

# Fuse (merge nearby points)
fuse = geo.createNode("fuse", "weld_points")
fuse.setInput(0, merge)
fuse.parm("dist").set(0.01)         # Merge within distance
fuse.parm("consolidate").set(1)     # Also consolidate fused points

# Dissolve (remove edges keeping mesh)
dissolve = geo.createNode("dissolve", "clean_edges")
dissolve.setInput(0, geo.node("my_box"))
dissolve.parm("group").set("0-3")   # Dissolve prims 0 through 3

geo.layoutChildren()
```

```python
# Groups: create, combine, use
import hou

geo = hou.node("/obj/geo1")

# Group by expression (VEX-style in group parm)
group_create = geo.createNode("groupcreate", "top_points")
group_create.setInput(0, geo.node("my_box"))
group_create.parm("groupname").set("top")
group_create.parm("grouptype").set(0)  # 0=point group
group_create.parm("basegroup").set("@P.y>0.5")

# Group by bounding box
group_bbox = geo.createNode("groupcreate", "center_region")
group_bbox.setInput(0, group_create)
group_bbox.parm("groupname").set("center")
group_bbox.parm("grouptype").set(0)
group_bbox.parm("usebbox").set(1)
group_bbox.parm("bboxsizex").set(1.0)

# Group syntax in parameters:
#   "piece0 piece1"    -- named groups (space-separated)
#   "0-10"             -- point/prim number range
#   "@P.y>5"           -- expression (ad-hoc group)
#   "!group1"          -- negate (everything except)
#   "*"                -- all (explicit wildcard)

# Use group in blast
blast = geo.createNode("blast", "keep_top")
blast.setInput(0, group_create)
blast.parm("group").set("top")
blast.parm("negate").set(1)  # Keep matching (delete everything else)

geo.layoutChildren()
```

```vex
// VEX wrangle basics -- attribwrangle SOP
// Run over: Points (default), Primitives, Vertices, or Detail

// Set attributes
f@density = 1.0;
f@temperature = 2.0;
v@v = set(0, 3, 0);           // velocity
f@pscale = 0.05;              // point scale (REQUIRED for volumerasterize)

// Access position
vector pos = @P;
@P.y += sin(@P.x * 2.0) * 0.5;  // Sine wave displacement

// Random per-point (deterministic from point number)
f@rand = rand(@ptnum);
f@pscale = fit01(rand(@ptnum), 0.5, 2.0);

// Color
v@Cd = set(1, 0, 0);          // red

// Read from second input (input index 1)
vector other_pos = point(1, "P", @ptnum);
float other_val = point(1, "density", @ptnum);

// Ramp-driven attribute (reads spare parm on wrangle node)
f@falloff = chramp("falloff", fit(@P.y, 0, 10, 0, 1));

// Remove points by condition
if (@P.y < 0) removepoint(0, @ptnum);

// Create groups in VEX
i@group_top = (@P.y > ch("height_threshold")) ? 1 : 0;
```

```python
# VDB workflow: mesh -> VDB -> boolean -> mesh
import hou

geo = hou.node("/obj/geo1")

# Convert mesh to VDB signed distance field
vdb_from = geo.createNode("vdbfrompolygons", "mesh_to_vdb")
vdb_from.setInput(0, geo.node("my_box"))
vdb_from.parm("voxelsize").set(0.05)

# Second mesh to VDB
vdb_from2 = geo.createNode("vdbfrompolygons", "sphere_to_vdb")
vdb_from2.setInput(0, geo.node("my_sphere"))
vdb_from2.parm("voxelsize").set(0.05)

# VDB combine (boolean -- more stable than polygon boolean)
vdb_combine = geo.createNode("vdbcombine", "vdb_subtract")
vdb_combine.setInput(0, vdb_from)
vdb_combine.setInput(1, vdb_from2)
vdb_combine.parm("operation").set("sdf difference")  # union/intersect/difference

# Smooth VDB
vdb_smooth = geo.createNode("vdbsmooth", "smooth_result")
vdb_smooth.setInput(0, vdb_combine)
vdb_smooth.parm("iterations").set(3)

# Convert back to polygons
convert = geo.createNode("convertvdb", "vdb_to_mesh")
convert.setInput(0, vdb_smooth)
convert.parm("adaptivity").set(0.01)  # Low = more detail

geo.layoutChildren()
print("VDB boolean pipeline created")
```

```python
# For-each loops
import hou

geo = hou.node("/obj/geo1")

# For-each by pieces (process each connected component)
begin = geo.createNode("block_begin", "foreach_begin")
begin.parm("method").set(1)           # 1 = By Pieces
begin.parm("blockpath").set("../foreach_end")

# Operations inside loop (e.g., transform each piece)
xform = geo.createNode("transform", "per_piece_xform")
xform.setInput(0, begin)

end = geo.createNode("block_end", "foreach_end")
end.setInput(0, xform)
end.parm("itermethod").set(1)         # 1 = By Pieces
end.parm("method").set(1)
end.parm("class").set(0)              # 0 = Primitives
end.parm("attrib").set("name")        # Piece attribute

# For-each by count (run N iterations)
# begin.parm("method").set(0)         # 0 = By Count
# begin.parm("iterations").set(10)

# Feedback loop (output feeds next iteration)
# begin.parm("method").set(2)         # 2 = Feedback

geo.layoutChildren()
```

```python
# File cache and utility nodes
import hou

geo = hou.node("/obj/geo1")
output = geo.node("my_sphere")  # Whatever node to cache

# File cache: write geometry to disk
cache = geo.createNode("filecache", "disk_cache")
cache.setInput(0, output)
# .bgeo.sc = Blosc compressed (3-5x smaller than raw)
cache.parm("sopoutput").set("$HIP/cache/geo.$F4.bgeo.sc")
cache.parm("trange").set(1)       # 1 = Render Frame Range

# Null (output marker -- convention: name it OUT)
null_out = geo.createNode("null", "OUT")
null_out.setInput(0, cache)
null_out.setDisplayFlag(True)
null_out.setRenderFlag(True)

# Switch between inputs
switch = geo.createNode("switch", "quality_switch")
switch.setInput(0, geo.node("my_sphere"))  # Low-res
switch.setInput(1, geo.node("smooth_subdiv"))  # High-res
switch.parm("input").set(0)  # 0 = first input (low-res)

# Trail (compute velocity from animated geo)
trail = geo.createNode("trail", "compute_vel")
trail.setInput(0, output)
trail.parm("result").set(1)  # 1 = Compute velocity

# Volume rasterize: points with attributes -> volume fields
rasterize = geo.createNode("volumerasterizeattributes", "to_volume")
rasterize.setInput(0, geo.node("scatter_pts"))
rasterize.parm("attributes").set("density temperature")
# Points MUST have @pscale attribute for voxel radius

geo.layoutChildren()
```

## Common Mistakes
- Using polygon boolean instead of VDB boolean for complex shapes -- VDB is more stable and faster
- Forgetting `@pscale` on points before `volumerasterizeattributes` -- node needs it for radius
- For-each loops where a VEX wrangle would work -- wrangles are 10-100x faster for per-element ops
- Not packing instances in `copytopoints` -- unpacked copies consume massive memory
- Using `blast` to isolate work instead of groups -- groups preserve the full mesh for downstream
- Caching to `.bgeo` instead of `.bgeo.sc` -- Blosc compression is 3-5x smaller, same read speed
- Editing deployed files instead of source -- always edit repo source, redeploy with installer
