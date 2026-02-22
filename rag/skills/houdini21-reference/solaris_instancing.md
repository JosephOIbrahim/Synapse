# Solaris Instancing Reference

## Triggers
instancer, point instancer, instance, prototype, scatter, RBD instance, light instance,
retime, copy to points lop, instanceable, instanceable flag, prototype index, protoIndices,
instance positions, instance orientations, scatter and align, sop scatter lop, instancer lop,
light instancing, reference mode, RBD to instance, sop import instancer, point instancer lop,
prototype container, prototype paths, instance transform, instance scale, Cd to color mapping,
primvar, attribute mapping, retime instancer, animated prototype, variant instancing,
duplicate variant, set variant instancing, instance id, random instance, scatter density,
instance seed, point count, prototype count, nested instancer, instance visibility,
instance render, instanceable mesh, mark instanceable, configure primitive instanceable,
xformOpOrder instance, instance rotation, quaternion orient, pscale instance, N up instance,
instance material, per-instance override, instance proxy, point instancer karma,
solaris instance, lop instance, usd instance, prototype prim, instance array, instance count,
scatter points lop, instance attribute, instance primvar, instance color, instancer node,
point instancer setup, instancer workflow, karma instancing, karma xpu instance,
multi prototype, prototype selection, instance offset, instance animation

## Context
Point Instancer is Solaris's native GPU-efficient instancing system, creating thousands
of copies from prototypes without duplicating geometry data. Houdini 21 uses the `instancer`
LOP which reads SOP scatter points and maps them to USD prototypes. All instance transforms
come from point attributes (P, orient, pscale, N+up) -- same convention as SOP Copy to Points.

## Code

### Basic Point Instancer Setup

```python
import hou

# Create a basic point instancer in Solaris
# The instancer LOP reads points from a SOP network and instances
# USD prototypes at each point location.

stage = hou.node("/stage")

# --- Step 1: Create geometry to scatter on (a ground plane) ---
ground = stage.createNode("sopcreate", "ground_plane")
# Dive inside to build the SOP network
ground_sop = ground.node("sopnet").node("create")
# The sopcreate has an embedded SOP network; configure via parms
ground.parm("primpath").set("/World/ground")

# --- Step 2: Create the prototype geometry ---
# Import a SOP-level asset as the prototype prim
proto_import = stage.createNode("sopimport", "tree_prototype")
proto_import.parm("soppath").set("/obj/tree_geo/OUT")
proto_import.parm("primpath").set("/World/Prototypes/tree")

# --- Step 3: Create the instancer LOP ---
instancer = stage.createNode("instancer", "tree_scatter")

# Source of scatter points (SOP path)
instancer.parm("soppath").set("/obj/scatter_points/OUT")

# Where the PointInstancer prim lives in USD
instancer.parm("primpath").set("/World/Instances/trees")

# Prototype source: reference existing prims on the stage
instancer.parm("protosource").set(1)  # 1 = "Second Input Primitives"

# --- Step 4: Wire the network ---
# Input 0: stage context (ground, lights, etc.)
# Input 1: prototype geometry
merge_ctx = stage.createNode("merge", "merge_context")
merge_ctx.setInput(0, ground)
instancer.setInput(0, merge_ctx)
instancer.setInput(1, proto_import)

instancer.setDisplayFlag(True)
stage.layoutChildren()
print(f"Instancer created at {instancer.path()}")
```

### SOP-to-Instancer Workflow

```python
import hou

# Full workflow: scatter points in SOPs, bring into Solaris instancer.
# SOP attributes (P, orient, pscale, Cd) map to USD instance properties.

# --- SOP side: create scatter points with attributes ---
obj = hou.node("/obj")
geo = obj.createNode("geo", "scatter_source")

# Create a grid to scatter on
grid = geo.createNode("grid", "base_grid")
grid.parm("sizex").set(20.0)
grid.parm("sizey").set(20.0)
grid.parm("rows").set(50)
grid.parm("cols").set(50)

# Scatter points on the grid
scatter = geo.createNode("scatter", "scatter_pts")
scatter.setInput(0, grid)
scatter.parm("npts").set(500)
scatter.parm("seed").set(42)  # Deterministic seed

# Add pscale attribute (random sizes)
wrangle_scale = geo.createNode("attribwrangle", "add_pscale")
wrangle_scale.setInput(0, scatter)
wrangle_scale.parm("snippet").set(
    '@pscale = fit01(rand(@ptnum * 0.123 + 7), 0.5, 2.0);'
)

# Add orient attribute (random Y rotation via quaternion)
wrangle_orient = geo.createNode("attribwrangle", "add_orient")
wrangle_orient.setInput(0, wrangle_scale)
wrangle_orient.parm("snippet").set(
    'float angle = rand(@ptnum * 0.456) * $PI * 2;\n'
    '// Quaternion for Y-axis rotation: (cos(a/2), 0, sin(a/2), 0)\n'
    '// Houdini quaternion order is (x, y, z, w)\n'
    'float ca = cos(angle * 0.5);\n'
    'float sa = sin(angle * 0.5);\n'
    '@orient = set(0, sa, 0, ca);'
)

# Add Cd attribute (random green/brown for foliage)
wrangle_cd = geo.createNode("attribwrangle", "add_color")
wrangle_cd.setInput(0, wrangle_orient)
wrangle_cd.parm("snippet").set(
    'float r = rand(@ptnum * 0.789);\n'
    'if (r < 0.5) {\n'
    '    @Cd = set(0.15, 0.4 + rand(@ptnum) * 0.3, 0.1);  // green\n'
    '} else {\n'
    '    @Cd = set(0.35, 0.25, 0.1);  // brown\n'
    '}'
)

# Add protoIndices for multi-prototype selection
# 0 = first prototype, 1 = second, etc.
wrangle_proto = geo.createNode("attribwrangle", "add_proto_index")
wrangle_proto.setInput(0, wrangle_cd)
wrangle_proto.parm("snippet").set(
    'int num_prototypes = 3;\n'
    'i@protoindex = int(rand(@ptnum * 0.321) * num_prototypes) % num_prototypes;'
)

# Output null
out = geo.createNode("null", "OUT")
out.setInput(0, wrangle_proto)
out.setDisplayFlag(True)
out.setRenderFlag(True)
geo.layoutChildren()

# --- Solaris side: instancer with attribute mapping ---
stage = hou.node("/stage")

instancer = stage.createNode("instancer", "foliage_instances")
instancer.parm("soppath").set(f"{geo.path()}/OUT")
instancer.parm("primpath").set("/World/Instances/foliage")

# Attribute mapping: SOP Cd -> USD primvar displayColor
# The instancer automatically maps:
#   P          -> positions
#   orient     -> orientations (quaternion)
#   pscale     -> scales (uniform)
#   protoindex -> protoIndices
# For Cd -> displayColor primvar, use the "Point Attributes" section:
instancer.parm("usealiasattribs").set(True)

# Prototype source: specify paths explicitly
instancer.parm("protosource").set(0)  # 0 = "Prototype Primitives"
instancer.parm("protopath1").set("/World/Prototypes/tree_pine")
instancer.parm("protopath2").set("/World/Prototypes/tree_oak")
instancer.parm("protopath3").set("/World/Prototypes/bush")

stage.layoutChildren()
print(f"Multi-prototype instancer: {instancer.path()}")
print("Attributes mapped: P, orient, pscale, protoindex, Cd")
```

### RBD-to-Instancer Workflow

```python
import hou

# After an RBD simulation, packed prims carry transform + name.
# Each packed prim name maps to a prototype in the instancer.
# This preserves sim transforms (P, orient from packed intrinsics).

stage = hou.node("/stage")

# --- Assume RBD sim output at /obj/rbd_sim/OUT ---
# Packed fragments have: name (piece name), P, orient (from intrinsics)

# Step 1: Import the rest geometry as prototypes
# Each unique packed prim name becomes a separate prototype
proto_import = stage.createNode("sopimport", "rbd_prototypes")
proto_import.parm("soppath").set("/obj/rbd_sim/REST_GEO")
proto_import.parm("primpath").set("/World/Prototypes/fracture")
# Use hierarchy import to preserve piece names as child prims
proto_import.parm("pathattr").set("name")

# Step 2: Create instancer from sim output
instancer = stage.createNode("instancer", "rbd_instances")
instancer.parm("soppath").set("/obj/rbd_sim/OUT")
instancer.parm("primpath").set("/World/Instances/debris")

# Prototype source: second input
instancer.parm("protosource").set(1)
instancer.setInput(1, proto_import)

# The instancer reads packed prim transforms automatically:
#   Packed intrinsic 'transform' -> instance orientations + positions
#   Packed intrinsic 'name'/'path' -> prototype matching

# Step 3: For animated RBD (frame range), ensure time dependency
# The instancer re-evaluates the SOP path each frame when
# the SOP has time-dependent cooking

instancer.setDisplayFlag(True)
stage.layoutChildren()
print("RBD instancer: packed prims mapped to prototypes by name")
```

### Light Instancing

```python
import hou

# Instance lights via point instancer.
# IMPORTANT: Karma does NOT support instanced lights in native mode.
# You MUST use reference mode for light instances to render in Karma.

stage = hou.node("/stage")

# --- Step 1: Create the light prototype ---
light_proto = stage.createNode("light", "spot_light_proto")
light_proto.parm("primpath").set("/World/Prototypes/spot_light")
light_proto.parm("xn__inputsintensity_i0a").set(1.0)  # Lighting Law: always 1.0
light_proto.parm("xn__inputsexposure_vya").set(3.0)    # Brightness via exposure
light_proto.parm("xn__inputsexposure_control_wcb").set("set")

# --- Step 2: Create scatter points for light positions ---
# (Assume SOP with light positions at /obj/light_positions/OUT)
# Each point = one light instance

# --- Step 3: Create instancer for lights ---
light_instancer = stage.createNode("instancer", "light_array")
light_instancer.parm("soppath").set("/obj/light_positions/OUT")
light_instancer.parm("primpath").set("/World/Instances/lights")

# CRITICAL: Set to reference mode for Karma compatibility
# Native instancing mode will NOT render lights in Karma
light_instancer.parm("lightinstancing").set(1)  # 1 = reference mode

# Prototype source: second input
light_instancer.setInput(1, light_proto)
light_instancer.parm("protosource").set(1)

light_instancer.setDisplayFlag(True)
stage.layoutChildren()
print("Light instancer (reference mode) for Karma compatibility")
print("REMINDER: Karma ignores natively instanced lights -- always use reference mode")
```

### Mark Geometry as Instanceable

```python
import hou

# Use Configure Primitive LOP to set the instanceable flag on mesh prims.
# When instanceable=True, Karma treats the prim as shared geometry,
# significantly reducing VRAM usage for repeated meshes.

stage = hou.node("/stage")

# --- Mark a specific prim as instanceable ---
config_prim = stage.createNode("configureprimitive", "mark_instanceable")

# Target the prim(s) to mark
# Use a collection pattern or explicit path
config_prim.parm("primpattern").set("/World/Props/**")

# Enable the instanceable flag
config_prim.parm("instanceable").set(True)

# GOTCHA: Set instanceable on the parent Xform prim, NOT on the Mesh prim directly.
# The Mesh is a child of the Xform; instanceable applies at the Xform level.
# Example hierarchy:
#   /World/Props/chair  (Xform) <- set instanceable HERE
#     /World/Props/chair/mesh (Mesh) <- NOT here

print("Marked /World/Props/** as instanceable for render efficiency")
print("Karma will share geometry data across matching instances")


# --- Batch-mark multiple prim patterns ---
def mark_instanceable(stage_path, prim_patterns):
    """Mark multiple prim patterns as instanceable in one pass."""
    import hou
    stage_node = hou.node(stage_path)
    if not stage_node:
        print(f"Couldn't find stage node at {stage_path}")
        return None

    last_node = None
    for i, pattern in enumerate(prim_patterns):
        cfg = stage_node.createNode(
            "configureprimitive",
            f"instanceable_{i}"
        )
        cfg.parm("primpattern").set(pattern)
        cfg.parm("instanceable").set(True)
        if last_node:
            cfg.setInput(0, last_node)
        last_node = cfg

    if last_node:
        stage_node.layoutChildren()
    return last_node


# Usage: mark all props and vegetation as instanceable
mark_instanceable("/stage", [
    "/World/Props/**",
    "/World/Vegetation/**",
    "/World/Rocks/**",
])
```

### Variant Instancing Workaround

```python
import hou

# USD does NOT natively instance prims with different variant selections.
# Workaround: Create N copies of the prim with Duplicate LOP, set a
# different variant on each copy, then feed all copies as prototypes
# to the instancer.

stage = hou.node("/stage")

# --- Assume: asset at /World/tree has variants: pine, oak, birch ---
# The asset is already on stage (via reference or sublayer)

# Step 1: Duplicate the prim for each variant
# Each duplicate gets a unique path under /World/Prototypes/
def create_variant_prototypes(stage_node, source_prim, variant_set,
                               variant_names, proto_root="/World/Prototypes"):
    """Create separate prims for each variant selection.
    Returns list of prototype prim paths."""
    import hou
    proto_paths = []
    last_node = None

    for i, variant in enumerate(variant_names):
        # Duplicate the source prim
        dup = stage_node.createNode("duplicate", f"dup_{variant}")
        dup.parm("sourceprimpath1").set(source_prim)
        dup.parm("destprimpath1").set(f"{proto_root}/{variant}")
        if last_node:
            dup.setInput(0, last_node)
        last_node = dup

        # Set the variant on the duplicated prim
        set_var = stage_node.createNode("setvariant", f"var_{variant}")
        set_var.setInput(0, dup)
        set_var.parm("primpath").set(f"{proto_root}/{variant}")
        set_var.parm("variantset").set(variant_set)
        set_var.parm("variantname").set(variant)
        last_node = set_var

        proto_paths.append(f"{proto_root}/{variant}")

    stage_node.layoutChildren()
    return last_node, proto_paths


# Usage:
node, proto_paths = create_variant_prototypes(
    stage,
    source_prim="/World/tree",
    variant_set="treeType",
    variant_names=["pine", "oak", "birch"],
    proto_root="/World/Prototypes/trees"
)

# Step 2: Feed variant prototypes to instancer
instancer = stage.createNode("instancer", "variant_scatter")
instancer.parm("soppath").set("/obj/scatter_points/OUT")
instancer.parm("primpath").set("/World/Instances/forest")

# Set prototype paths from variant copies
for i, path in enumerate(proto_paths):
    instancer.parm(f"protopath{i + 1}").set(path)

instancer.parm("protosource").set(0)  # Prototype Primitives
if node:
    instancer.setInput(0, node)

instancer.setDisplayFlag(True)
stage.layoutChildren()
print(f"Variant instancing: {len(proto_paths)} prototypes from variant set")
```

### Retime Instancer for Animated Prototypes

```python
import hou

# When prototypes have animation (walk cycles, growing plants, etc.),
# use the Retime Instances LOP to offset animation per instance.
# Each instance can start its animation at a different frame.

stage = hou.node("/stage")

# --- Assume: instancer already exists with animated prototypes ---

# Step 1: Add frame offset attribute in SOPs
# Each scatter point gets a random start frame offset
obj = hou.node("/obj")
geo = obj.node("scatter_source")
if geo:
    wrangle_offset = geo.createNode("attribwrangle", "frame_offset")
    wrangle_offset.parm("snippet").set(
        '// Random frame offset within animation range (e.g., 0 to 48 frames)\n'
        'f@timeoffset = rand(@ptnum * 0.654) * 48.0;'
    )
    # Wire after scatter, before OUT
    out_node = geo.node("OUT")
    if out_node:
        prev_input = out_node.input(0)
        wrangle_offset.setInput(0, prev_input)
        out_node.setInput(0, wrangle_offset)
        geo.layoutChildren()

# Step 2: Create Retime Instances LOP in Solaris
retime = stage.createNode("retimeinstances", "retime_walk_cycles")

# Source instancer prim to retime
retime.parm("primpath").set("/World/Instances/characters")

# Offset attribute from the point data
retime.parm("offsetattrib").set("timeoffset")

# Retime mode: "Offset" shifts each instance's time
# "Absolute" sets each instance to a specific frame
retime.parm("mode").set(0)  # 0 = Offset

# Speed scale (1.0 = normal, 0.5 = half speed, 2.0 = double)
retime.parm("speedscale").set(1.0)

# Cycling mode for looping animations
# 0 = None (clamp), 1 = Repeat, 2 = Mirror
retime.parm("cycling").set(1)  # Repeat for walk cycles

retime.setDisplayFlag(True)
stage.layoutChildren()
print("Retime Instances: each instance plays animation at different offset")
print("Cycling=Repeat ensures seamless looping for walk cycles")
```

### Complete Scatter-to-Render Pipeline

```python
import hou

# End-to-end workflow: scatter in SOPs, instance in Solaris,
# mark instanceable, set up camera and render.

stage = hou.node("/stage")
obj = hou.node("/obj")

# --- SOP: scatter points on imported terrain ---
scatter_geo = obj.createNode("geo", "rock_scatter")

grid = scatter_geo.createNode("grid", "terrain")
grid.parm("sizex").set(50)
grid.parm("sizey").set(50)
grid.parm("rows").set(100)
grid.parm("cols").set(100)

# Add noise for terrain variation
mountain = scatter_geo.createNode("mountain", "terrain_noise")
mountain.setInput(0, grid)
mountain.parm("height").set(3.0)

scatter = scatter_geo.createNode("scatter", "rock_points")
scatter.setInput(0, mountain)
scatter.parm("npts").set(200)
scatter.parm("seed").set(7)

# Attributes for instances
wrangle = scatter_geo.createNode("attribwrangle", "instance_attribs")
wrangle.setInput(0, scatter)
wrangle.parm("snippet").set(
    '// Random scale\n'
    '@pscale = fit01(rand(@ptnum * 0.111), 0.3, 1.5);\n'
    '\n'
    '// Random Y rotation quaternion\n'
    'float angle = rand(@ptnum * 0.222) * $PI * 2;\n'
    'float ca = cos(angle * 0.5);\n'
    'float sa = sin(angle * 0.5);\n'
    '@orient = set(0, sa, 0, ca);\n'
    '\n'
    '// Normal for up-vector alignment (from terrain surface)\n'
    '// orient takes priority over N+up when both exist\n'
    '\n'
    '// Prototype index (3 rock variations)\n'
    'i@protoindex = int(rand(@ptnum * 0.333) * 3) % 3;'
)

sop_out = scatter_geo.createNode("null", "OUT")
sop_out.setInput(0, wrangle)
sop_out.setDisplayFlag(True)
sop_out.setRenderFlag(True)
scatter_geo.layoutChildren()

# --- Solaris: build instance scene ---
# Import terrain
terrain_import = stage.createNode("sopimport", "terrain_mesh")
terrain_import.parm("soppath").set(f"{scatter_geo.path()}/terrain_noise")
terrain_import.parm("primpath").set("/World/terrain")

# Import rock prototypes (assume 3 rock SOPs exist)
protos = []
for i, name in enumerate(["rock_a", "rock_b", "rock_c"]):
    proto = stage.createNode("sopimport", f"proto_{name}")
    proto.parm("soppath").set(f"/obj/rocks/{name}/OUT")
    proto.parm("primpath").set(f"/World/Prototypes/{name}")
    protos.append(proto)

# Merge prototypes
proto_merge = stage.createNode("merge", "merge_prototypes")
for i, p in enumerate(protos):
    proto_merge.setInput(i, p)

# Create instancer
instancer = stage.createNode("instancer", "rock_instances")
instancer.parm("soppath").set(f"{scatter_geo.path()}/OUT")
instancer.parm("primpath").set("/World/Instances/rocks")
instancer.parm("protosource").set(1)  # Second input primitives
instancer.setInput(0, terrain_import)
instancer.setInput(1, proto_merge)

# Mark prototypes as instanceable for Karma VRAM efficiency
config = stage.createNode("configureprimitive", "mark_instanceable")
config.setInput(0, instancer)
config.parm("primpattern").set("/World/Prototypes/**")
config.parm("instanceable").set(True)

config.setDisplayFlag(True)
stage.layoutChildren()
print("Complete scatter pipeline: 200 rock instances from 3 prototypes")
print("Prototypes marked instanceable for Karma memory efficiency")
```

### Gotchas

```python
# === INSTANCING GOTCHAS IN HOUDINI 21 / SOLARIS ===

# 1. protoIndices must be 0-based and match prototype count exactly
#    If you have 3 prototypes, valid indices are 0, 1, 2.
#    An index of 3 or higher causes missing instances (silent failure).
#    WRONG:  i@protoindex = int(rand(@ptnum) * 3) + 1;  // 1,2,3
#    RIGHT:  i@protoindex = int(rand(@ptnum) * 3) % 3;  // 0,1,2

# 2. orient attribute is quaternion (x, y, z, w) -- same as SOP convention
#    Houdini uses (x, y, z, w) order, NOT (w, x, y, z) like some DCC apps.
#    For Y-axis rotation: set(0, sin(angle/2), 0, cos(angle/2))

# 3. pscale of 0 makes instances INVISIBLE (common scatter bug)
#    Always clamp: @pscale = max(@pscale, 0.001);
#    Default if missing: pscale = 1.0 (full size)

# 4. Karma XPU has limits on nested instancers
#    Maximum 2 levels of nesting as of Houdini 21.
#    Example: instancer A instances instancer B instances mesh = 2 levels (OK)
#    3+ levels: Karma XPU silently drops the deepest level.
#    Karma CPU handles deeper nesting but at a performance cost.

# 5. instanceable flag goes on parent Xform, NOT on Mesh
#    /World/Props/chair  (Xform) <- instanceable = True HERE
#      /World/Props/chair/mesh  (Mesh) <- NOT here

# 6. N+up vs orient attribute priority
#    If both 'orient' (quaternion) and 'N'+'up' (vectors) exist on a point,
#    'orient' takes priority. Remove orient if you want N+up alignment.

# 7. Karma light instancing requires reference mode
#    Native point instancer mode does NOT render instanced lights in Karma.
#    Always set lightinstancing = 1 (reference mode) for light arrays.

# 8. Large instance counts and viewport performance
#    >100k instances can slow the viewport. Use:
#    - Point display mode in viewport (not full geometry)
#    - LOD settings on the instancer node
#    - Viewport > Optimize > Instance Draw Limit

# 9. SOP Cd attribute mapping
#    SOP Cd (vector3) maps to USD displayColor primvar automatically.
#    For per-instance color overrides in materials, bind the primvar
#    explicitly in your MaterialX/Karma shader network.

# 10. Animated prototypes and time sampling
#     If prototypes have animation, the instancer samples all prototypes
#     at the SAME frame unless you use Retime Instances LOP.
#     Without retime, all instances animate in perfect sync.
```
