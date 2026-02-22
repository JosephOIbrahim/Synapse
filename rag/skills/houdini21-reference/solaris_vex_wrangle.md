# LOPs Wrangle / VEX in Solaris

## Triggers
lops wrangle, lop vex, usd wrangle, primpath expression, xformOp, displayColor lop,
usd_setrelationshiptargets, material assignment vex, usd_addrotate, lops attribute,
attribwrangle lop, wrangle lop, vex solaris, usd vex, set attribute lop vex,
xformOpOrder, usd_addtranslate, usd_addscale, usd_setattrib, usd_getattrib,
usd_typename, usd_istype, primpath pattern, collection pattern, primpath selector,
info:id, usd_flattenedxform, usd_worldtransform, usd_localtransform,
lops point wrangle, lops array attribute, displayColor array, primvar lop,
usd_setrelationship, material binding vex, texture path vex, op: prefix,
cross-stage read, usd_addrotateXYZ, usd_setxformorder, transform lop vex,
random orient lop, scatter orient vex, wrangle primitive lop, vex usd functions,
usd_makeattribpath, usd_isprim, usd_primchildren, usd_primtype, wrangle collection,
foreach prim vex, lop attribute wrangle node, solaris wrangle node, edit properties vex,
lops wrangle snippet, usd_setattrib array, primvars displayColor, xformOp translate,
xformOp rotate, xformOp scale, lops random color, lops conditional material,
usd_addprim, usd wrangle primpath, solaris vex functions, lops vex reference,
lop wrangle iterate prims, usd_setrelationshiptargets material, lop wrangle examples,
solaris attribute wrangle, lops transform vex, lops instancer orient

## Context
LOPs Wrangles operate on USD prims, not points/primitives like SOP VEX. There is no
`@P`, `@N`, or `@Cd` -- everything is accessed through USD VEX functions like
`usd_setattrib()`, `usd_getattrib()`, `usd_addtranslate()`, etc. The wrangle iterates
over prims matching a primpath pattern, and `@primpath` gives the current prim path as
a string. Array syntax is required for primvar writes, even single values.

## Code

### Creating a LOPs Wrangle Node in Python

```python
# Create and configure an Attribute Wrangle LOP in /stage
import hou

def create_lops_wrangle(stage_path="/stage", name="attribwrangle",
                        prim_pattern="/World/geo/*", snippet=""):
    """Create a LOPs Attribute Wrangle node with VEX code.

    Args:
        stage_path: Parent LOP network (default /stage).
        prim_pattern: USD primpath pattern to iterate over.
        snippet: VEX code to execute on each matching prim.

    Returns:
        The created hou.Node, or None on failure.
    """
    stage = hou.node(stage_path)
    if not stage:
        print(f"Couldn't find network: {stage_path}")
        return None

    wrangle = stage.createNode("attribwrangle", name)

    # Primpath pattern -- which prims to iterate over
    wrangle.parm("primpattern").set(prim_pattern)

    # VEX snippet
    wrangle.parm("snippet").set(snippet)

    # Run Over defaults to "Primitives" in LOPs context (USD prims)
    # No need to change unless you want detail-level execution

    wrangle.moveToGoodPosition()
    print(f"Created LOPs wrangle '{wrangle.path()}' on pattern: {prim_pattern}")
    return wrangle


# Example: wrangle that sets displayColor on all Mesh prims
vex_code = r'''
// Set all meshes to red
float colors[] = {1.0, 0.0, 0.0};
usd_setattrib(0, @primpath, "primvars:displayColor", colors);
'''

create_lops_wrangle(
    prim_pattern="{ usd_istype(0, @primpath, \"Mesh\") }",
    snippet=vex_code
)
```

```python
# Wire a wrangle into an existing LOP chain
import hou

def insert_wrangle_after(upstream_path, prim_pattern, snippet):
    """Insert a LOPs wrangle after an existing node, reconnecting downstream."""
    upstream = hou.node(upstream_path)
    if not upstream:
        print(f"Couldn't find node: {upstream_path}")
        return None

    parent = upstream.parent()
    wrangle = parent.createNode("attribwrangle", "property_wrangle")
    wrangle.parm("primpattern").set(prim_pattern)
    wrangle.parm("snippet").set(snippet)

    # Grab existing output connections before rewiring
    outputs = upstream.outputConnections()

    # Connect wrangle input to upstream output
    wrangle.setInput(0, upstream)

    # Reconnect downstream nodes to wrangle output
    for conn in outputs:
        conn.outputNode().setInput(conn.inputIndex(), wrangle)

    wrangle.moveToGoodPosition()
    return wrangle
```

### Setting displayColor (Array Syntax)

```vex
// displayColor is a Vec3f[] array in USD -- NOT a simple vector
// WRONG: v@displayColor = {1, 0, 0};  <-- does NOT work in LOPs
// CORRECT: use usd_setattrib with a float array

// Solid red color on all matching prims
float colors[] = {1.0, 0.0, 0.0};
usd_setattrib(0, @primpath, "primvars:displayColor", colors);
```

```vex
// Random displayColor per prim using @elemnum as seed
float r = rand(@elemnum * 13.37);
float g = rand(@elemnum * 7.91);
float b = rand(@elemnum * 3.14);

float colors[] = {r, g, b};
usd_setattrib(0, @primpath, "primvars:displayColor", colors);
```

```vex
// Conditional displayColor based on prim type
string prim_type = usd_typename(0, @primpath);

float colors[];
if (prim_type == "Mesh") {
    colors = {0.2, 0.6, 1.0};   // blue for meshes
} else if (prim_type == "Capsule" || prim_type == "Sphere") {
    colors = {1.0, 0.4, 0.1};   // orange for procedural shapes
} else {
    colors = {0.5, 0.5, 0.5};   // grey fallback
}

usd_setattrib(0, @primpath, "primvars:displayColor", colors);
```

### Transform Operations -- xformOp

```vex
// CRITICAL: Every xformOp you add MUST also be listed in xformOpOrder.
// Without xformOpOrder, transforms are silently ignored.

// Basic translate + rotate + scale
usd_addtranslate(0, @primpath, "xformOp:translate", {0, 1.5, 0});
usd_addrotate(0, @primpath, "xformOp:rotateXYZ", "XYZ", {0, 45, 0});
usd_addscale(0, @primpath, "xformOp:scale", {1, 1, 1});

// Set the xformOpOrder -- MUST list all ops in application order
string xform_order[] = {
    "xformOp:translate",
    "xformOp:rotateXYZ",
    "xformOp:scale"
};
usd_setattrib(0, @primpath, "xformOpOrder", xform_order);
```

```vex
// Translate only -- still needs xformOpOrder
float ty = sin(@elemnum * 0.5) * 2.0;
usd_addtranslate(0, @primpath, "xformOp:translate", set(0, ty, 0));

string xform_order[] = {"xformOp:translate"};
usd_setattrib(0, @primpath, "xformOpOrder", xform_order);
```

```vex
// Read existing transform -- get flattened world or local matrix
matrix local_xform = usd_localtransform(0, @primpath);
matrix world_xform = usd_worldtransform(0, @primpath);

// Get flattened (composed) transform across all sublayers
matrix flat = usd_flattenedxform(0, @primpath);

// Extract translate from existing local transform
vector pos = set(local_xform.ax, local_xform.ay, local_xform.az);
// Note: for translation, extract from column 3
pos = set(getcomp(local_xform, 3, 0),
          getcomp(local_xform, 3, 1),
          getcomp(local_xform, 3, 2));
```

### Randomizing Instance Orientations

```vex
// Run on an instancer's point instances or scattered prims
// Primpath pattern: /World/instancer/instances/*

// Random Y rotation per instance
float angle_y = rand(@elemnum * 42.17) * 360.0;  // degrees, not radians
usd_addrotate(0, @primpath, "xformOp:rotateXYZ", "XYZ", set(0, angle_y, 0));

string xform_order[] = {"xformOp:rotateXYZ"};
usd_setattrib(0, @primpath, "xformOpOrder", xform_order);
```

```vex
// Full random orient: random rotation on all axes + random scale variation
float seed = @elemnum * 137.035;

float rx = rand(seed)       * 15.0 - 7.5;   // slight tilt: -7.5 to +7.5 degrees
float ry = rand(seed + 1.0) * 360.0;         // full Y rotation
float rz = rand(seed + 2.0) * 15.0 - 7.5;   // slight tilt

float scale_vary = fit01(rand(seed + 3.0), 0.8, 1.2);  // 80%-120% scale

usd_addtranslate(0, @primpath, "xformOp:translate", {0, 0, 0});
usd_addrotate(0, @primpath, "xformOp:rotateXYZ", "XYZ", set(rx, ry, rz));
usd_addscale(0, @primpath, "xformOp:scale",
             set(scale_vary, scale_vary, scale_vary));

string xform_order[] = {
    "xformOp:translate",
    "xformOp:rotateXYZ",
    "xformOp:scale"
};
usd_setattrib(0, @primpath, "xformOpOrder", xform_order);
```

```python
# Python: create wrangle for scattering random orients on instances
import hou

stage = hou.node("/stage")
wrangle = stage.createNode("attribwrangle", "randomize_orient")
wrangle.parm("primpattern").set("/World/instancer/instances/*")

vex = r'''
float seed = @elemnum * 137.035;
float ry = rand(seed) * 360.0;
float scale_vary = fit01(rand(seed + 1.0), 0.85, 1.15);

usd_addrotate(0, @primpath, "xformOp:rotateXYZ", "XYZ", set(0, ry, 0));
usd_addscale(0, @primpath, "xformOp:scale",
             set(scale_vary, scale_vary, scale_vary));

string xform_order[] = {"xformOp:rotateXYZ", "xformOp:scale"};
usd_setattrib(0, @primpath, "xformOpOrder", xform_order);
'''

wrangle.parm("snippet").set(vex)
wrangle.moveToGoodPosition()
```

### Material Assignment via VEX

```vex
// Assign material using usd_setrelationshiptargets()
// This is the VEX equivalent of the Assign Material LOP

string targets[] = {"/World/mtl/myMaterial"};
usd_setrelationshiptargets(0, @primpath, "material:binding", targets);
```

```vex
// Conditional material assignment based on prim name
string prim_name = usd_name(0, @primpath);

string targets[];
if (match("*wall*", prim_name)) {
    targets = {"/World/mtl/brick"};
} else if (match("*floor*", prim_name)) {
    targets = {"/World/mtl/wood"};
} else if (match("*glass*", prim_name)) {
    targets = {"/World/mtl/glass"};
} else {
    targets = {"/World/mtl/default"};
}

usd_setrelationshiptargets(0, @primpath, "material:binding", targets);
```

```vex
// Random material from a palette (e.g., 5 color variants)
int mat_idx = int(rand(@elemnum * 99.7) * 5);  // 0-4

string mat_paths[] = {
    "/World/mtl/color_A",
    "/World/mtl/color_B",
    "/World/mtl/color_C",
    "/World/mtl/color_D",
    "/World/mtl/color_E"
};

string targets[] = {mat_paths[mat_idx]};
usd_setrelationshiptargets(0, @primpath, "material:binding", targets);
```

### Texture Path Manipulation

```vex
// Read existing texture path from a material prim
// Primpath pattern should target material shader prims, e.g.:
//   /World/mtl/*/mtlximage*  or  /World/mtl/hero_mtl/diffuse_tex

string tex_path = usd_getattrib(0, @primpath, "inputs:file");

// Replace version number in texture path
// e.g., "/textures/v003/diffuse.exr" -> "/textures/v004/diffuse.exr"
string updated = re_replace("v[0-9]+", "v004", tex_path);
usd_setattrib(0, @primpath, "inputs:file", updated);
```

```vex
// Batch-update UDIM texture paths across all materials
string tex_path = usd_getattrib(0, @primpath, "inputs:file");

if (len(tex_path) > 0) {
    // Swap texture root directory
    string updated = re_replace("^/old_server/textures",
                                "/new_server/textures", tex_path);
    usd_setattrib(0, @primpath, "inputs:file", updated);
}
```

### Reading USD Attributes Cross-Stage (op: prefix)

```vex
// Read an attribute from a DIFFERENT LOP node's stage output
// Use the op: prefix with the Houdini node path

// Read the world transform of a prim from another node's stage
matrix other_xform = usd_worldtransform(0, "op:/stage/transform1", @primpath);

// Read a custom attribute from a reference stage
string label = usd_getattrib(0, "op:/stage/sublayer_ref", @primpath, "custom:label");
```

```vex
// Compare attribute values between two stages
// Useful for delta/difference workflows

float current_val = usd_getattrib(0, @primpath, "primvars:density");
float ref_val = usd_getattrib(0, "op:/stage/reference_stage", @primpath, "primvars:density");

float delta = current_val - ref_val;

// Store the delta as a new attribute
usd_setattrib(0, @primpath, "primvars:density_delta", delta);
```

```python
# Python: create wrangle that reads cross-stage and computes difference
import hou

stage = hou.node("/stage")
wrangle = stage.createNode("attribwrangle", "compare_stages")
wrangle.parm("primpattern").set("/World/geo/**")

# Second input: connect the reference stage for op: reads
# Or use absolute node path in the VEX code with op: prefix
ref_node = hou.node("/stage/base_layer")
if ref_node:
    wrangle.setInput(1, ref_node)

vex = r'''
// Input 1 (index 1) is the reference stage
matrix ref_xform = usd_worldtransform(1, @primpath);
matrix cur_xform = usd_worldtransform(0, @primpath);

// Check if prim has moved
vector ref_pos = set(getcomp(ref_xform, 3, 0),
                     getcomp(ref_xform, 3, 1),
                     getcomp(ref_xform, 3, 2));
vector cur_pos = set(getcomp(cur_xform, 3, 0),
                     getcomp(cur_xform, 3, 1),
                     getcomp(cur_xform, 3, 2));

float dist = length(cur_pos - ref_pos);
if (dist > 0.001) {
    // Mark moved prims with a custom attribute
    usd_setattrib(0, @primpath, "custom:hasMoved", 1);
    usd_setattrib(0, @primpath, "custom:moveDistance", dist);
}
'''

wrangle.parm("snippet").set(vex)
wrangle.moveToGoodPosition()
```

### Primpath Expressions and Selectors

```vex
// Primpath patterns used in the wrangle's "Primitive Pattern" field
// These are set on the node parm, not in VEX code itself

// Simple glob -- all direct children of /World/geo
// primpattern = /World/geo/*

// Recursive glob -- all descendants
// primpattern = /World/geo/**

// Type filter -- only Mesh prims (VEX expression in braces)
// primpattern = { usd_istype(0, @primpath, "Mesh") }

// Multiple type filter
// primpattern = { usd_istype(0, @primpath, "Mesh") || usd_istype(0, @primpath, "BasisCurves") }

// Attribute filter -- prims with specific metadata
// primpattern = { usd_getattrib(0, @primpath, "custom:renderLayer") == "hero" }

// Collection-based -- prims in a USD collection
// primpattern = %/World/collections.renderGeo

// Combine glob and type filter with space (implicit AND)
// primpattern = /World/geo/** { usd_istype(0, @primpath, "Mesh") }
```

```python
# Python: set various primpath patterns on a wrangle node
import hou

wrangle = hou.node("/stage/attribwrangle1")
if wrangle:
    # All Mesh prims under /World
    wrangle.parm("primpattern").set(
        '{ usd_istype(0, @primpath, "Mesh") }'
    )

    # Only prims whose name contains "hero"
    wrangle.parm("primpattern").set(
        '{ match("*hero*", usd_name(0, @primpath)) }'
    )

    # All visible prims (not explicitly hidden)
    wrangle.parm("primpattern").set(
        '{ usd_getattrib(0, @primpath, "visibility") != "invisible" }'
    )
```

```vex
// Inside VEX: inspect prim hierarchy and type
string prim_type = usd_typename(0, @primpath);   // e.g., "Mesh", "Xform", "Scope"
string prim_name = usd_name(0, @primpath);        // leaf name, e.g., "shape"
int is_mesh = usd_istype(0, @primpath, "Mesh");   // 1 if Mesh or derived type
int exists = usd_isprim(0, @primpath);             // 1 if prim exists at path

// Get children of current prim
string children[] = usd_primchildren(0, @primpath);
int num_children = len(children);

// Walk children to find specific types
foreach (string child; children) {
    if (usd_istype(0, child, "GeomSubset")) {
        // Found a face set / geometry subset
        printf("Subset: %s\n", child);
    }
}
```

### Reading and Writing Array Attributes

```vex
// USD arrays in VEX use typed array syntax

// Read a float array attribute
float extent[] = usd_getattrib(0, @primpath, "extent");
// extent is a flat array: {xmin, ymin, zmin, xmax, ymax, zmax}

// Read string array
string variantSets[] = usd_getattrib(0, @primpath, "variantSets");

// Write a float array (e.g., custom weights)
float weights[] = {0.25, 0.5, 0.75, 1.0};
usd_setattrib(0, @primpath, "primvars:weights", weights);

// Write an int array (e.g., face indices for a subset)
int face_ids[] = {0, 1, 2, 5, 8, 13};
usd_setattrib(0, @primpath, "faceIndices", face_ids);
```

```vex
// Append to an existing array: read, append, write back
float existing[] = usd_getattrib(0, @primpath, "primvars:weights");
append(existing, 0.99);
usd_setattrib(0, @primpath, "primvars:weights", existing);
```

```vex
// Build a string array for custom purpose assignments
string purposes[];
string prim_type = usd_typename(0, @primpath);

if (prim_type == "Mesh") {
    append(purposes, "render");
    append(purposes, "proxy");
} else if (prim_type == "Xform") {
    append(purposes, "guide");
}

if (len(purposes) > 0) {
    usd_setattrib(0, @primpath, "custom:purposes", purposes);
}
```

### Full Python Pipeline: Wrangle with Parameters

```python
# Create a LOPs wrangle with channel references for artist control
import hou

def create_parameterized_wrangle(stage_path="/stage"):
    """Create a LOPs wrangle with spare parameters for artist tuning."""
    stage = hou.node(stage_path)
    if not stage:
        print(f"Couldn't find network: {stage_path}")
        return None

    wrangle = stage.createNode("attribwrangle", "color_by_height")
    wrangle.parm("primpattern").set('{ usd_istype(0, @primpath, "Mesh") }')

    # Add spare parameters for artist control
    ptg = wrangle.parmTemplateGroup()

    ptg.append(hou.FloatParmTemplate(
        "min_height", "Min Height", 1, default_value=(0.0,)
    ))
    ptg.append(hou.FloatParmTemplate(
        "max_height", "Max Height", 1, default_value=(10.0,)
    ))
    ptg.append(hou.FloatParmTemplate(
        "color_a", "Color A", 3, default_value=(0.1, 0.3, 0.8)
    ))
    ptg.append(hou.FloatParmTemplate(
        "color_b", "Color B", 3, default_value=(1.0, 0.2, 0.1)
    ))

    wrangle.setParmTemplateGroup(ptg)

    vex = r'''
// Color prims by their Y position (bounding box center)
float extent[] = usd_getattrib(0, @primpath, "extent");

// extent is {xmin, ymin, zmin, xmax, ymax, zmax}
float center_y = 0;
if (len(extent) >= 6) {
    center_y = (extent[1] + extent[4]) * 0.5;
}

float min_h = chf("min_height");
float max_h = chf("max_height");
float t = fit(center_y, min_h, max_h, 0, 1);
t = clamp(t, 0, 1);

vector col_a = chv("color_a");
vector col_b = chv("color_b");
vector blended = lerp(col_a, col_b, t);

float colors[] = {blended.x, blended.y, blended.z};
usd_setattrib(0, @primpath, "primvars:displayColor", colors);
'''

    wrangle.parm("snippet").set(vex)
    wrangle.moveToGoodPosition()
    print(f"Created parameterized wrangle: {wrangle.path()}")
    return wrangle

create_parameterized_wrangle()
```

## Gotchas

- VEX in LOPs has NO `@P`, `@N`, `@Cd` -- everything goes through `usd_setattrib`/`usd_getattrib`
- `@primpath` is the current prim (string); `@elemnum` is the iteration index
- xformOpOrder MUST list every xformOp you add, in order -- missing entries cause silent transform loss
- displayColor is `primvars:displayColor` (with the `primvars:` prefix) and requires array syntax even for a single color
- `usd_addrotate` angles are in DEGREES, not radians
- The wrangle runs on the ACTIVE layer -- prims from references/sublayers may need Edit Properties first to create an opinion on the active layer before the wrangle can modify them
- `usd_istype()` checks inheritance -- a Mesh is also a Gprim and an Imageable
- `usd_typename()` returns the exact type, not base types
- Array writes replace the entire array -- there is no `usd_appendattrib`; read, modify, write back
- Cross-stage reads with `op:` use Houdini node paths (e.g., `op:/stage/node`), not USD prim paths
- In primpath expression braces `{ }`, string comparisons use VEX syntax (`==`, `match()`) not USD query syntax
- The wrangle node type in LOPs is `attribwrangle` (same name as SOPs) -- context determines behavior
