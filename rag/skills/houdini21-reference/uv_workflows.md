# UV Workflows

## Triggers
uv, unwrap, flatten, layout, UDIM, texture coordinates, seam, uvproject,
uvflatten, uvlayout, uvtransform, uvquickshade, triplanar, uv transfer

## Context
UV mapping in Houdini SOPs: automatic unwrap, interactive flatten with seams,
projection, layout/packing, UDIM tiles, quality checking, and transfer.
All code is Houdini Python and VEX.

## Code

```python
# Basic UV pipeline: unwrap -> layout -> verify
import hou

geo = hou.node("/obj/geo1")
mesh = geo.node("my_box")  # Any mesh needing UVs

# Automatic unwrap (angle-based -- fast, good for simple shapes)
unwrap = geo.createNode("uvunwrap", "auto_uvs")
unwrap.setInput(0, mesh)
unwrap.parm("method").set(0)   # 0=Angle Based, 1=Conformal
unwrap.parm("scale").set(1.0)

# Pack UV islands efficiently
layout = geo.createNode("uvlayout", "pack_uvs")
layout.setInput(0, unwrap)
layout.parm("packingscale").set(0)     # 0=auto scale islands
layout.parm("padding").set(0.005)      # Minimum padding to prevent texture bleed at mips
layout.parm("axisalign").set(1)        # Align islands to axes
layout.parm("rotateallowed").set(1)    # Allow rotation for tighter packing

# Verify with checker pattern
checker = geo.createNode("uvquickshade", "check_uvs")
checker.setInput(0, layout)
# Uniform checker squares = good UVs
# Stretched = UV stretching (bad)
# Compressed = UV compression
# Rotated = UV shearing

geo.layoutChildren()
print("UV pipeline: unwrap -> layout -> quickshade checker")
```

```python
# Production UV flatten with seam control
import hou

geo = hou.node("/obj/geo1")
mesh = geo.node("hero_mesh")

# Step 1: Create edge group for seams
seam_group = geo.createNode("groupcreate", "uv_seams")
seam_group.setInput(0, mesh)
seam_group.parm("groupname").set("seams")
seam_group.parm("grouptype").set(2)  # 2=edge group

# Step 2: Interactive flatten with seams (production quality)
flatten = geo.createNode("uvflatten", "production_uvs")
flatten.setInput(0, seam_group)
flatten.parm("seamgroup").set("seams")       # Edge group defining cuts
flatten.parm("flattenmethod").set(0)         # 0=ABF, 1=LSCM, 2=SCP

# Step 3: Layout into single tile or UDIM
layout = geo.createNode("uvlayout", "pack_islands")
layout.setInput(0, flatten)
layout.parm("padding").set(0.005)

# Step 4: Verify
checker = geo.createNode("uvquickshade", "verify")
checker.setInput(0, layout)

geo.layoutChildren()
print("Production UV: seam group -> flatten -> layout -> verify")
```

```python
# UV projection methods
import hou

geo = hou.node("/obj/geo1")
mesh = geo.node("my_box")

# Planar projection (walls, floors, flat surfaces)
planar = geo.createNode("uvproject", "uv_planar")
planar.setInput(0, mesh)
planar.parm("projtype").set(0)   # 0=Planar
planar.parm("inittype").set(1)   # 1=Best projection axis

# Cylindrical projection (bottles, columns, pipes)
cylindrical = geo.createNode("uvproject", "uv_cylindrical")
cylindrical.setInput(0, mesh)
cylindrical.parm("projtype").set(1)   # 1=Cylindrical

# Spherical projection (globes, eyes, round objects)
spherical = geo.createNode("uvproject", "uv_spherical")
spherical.setInput(0, mesh)
spherical.parm("projtype").set(2)   # 2=Spherical

# Camera projection (matte painting, texture baking)
camera_proj = geo.createNode("uvproject", "uv_camera")
camera_proj.setInput(0, mesh)
camera_proj.parm("projtype").set(3)   # 3=Camera
camera_proj.parm("camera").set("/obj/cam1")

geo.layoutChildren()
```

```python
# UDIM tile layout for production assets
import hou

geo = hou.node("/obj/geo1")

# UDIM convention:
#   1001 = U:0-1, V:0-1 (first tile)
#   1002 = U:1-2, V:0-1 (second tile)
#   1011 = U:0-1, V:1-2 (row above first)
# Common assignment: body=1001, head=1002, arms=1003, legs=1004

# Enable UDIM packing
layout = geo.createNode("uvlayout", "udim_layout")
layout.setInput(0, geo.node("production_uvs"))
layout.parm("udimmode").set(1)          # 1=UDIM mode
layout.parm("udimtarget").set(1001)     # Starting UDIM tile
layout.parm("padding").set(0.005)

# UV transform: offset UVs to specific UDIM tile
uv_xform = geo.createNode("uvtransform", "move_to_udim")
uv_xform.setInput(0, layout)
uv_xform.parm("tx").set(1.0)           # Shift to UDIM 1002

geo.layoutChildren()
print("UDIM layout: start tile 1001")
```

```vex
// UV manipulation in VEX
// Run on Vertices (not Points!) for proper seam handling

// Read existing UVs (vertex attribute)
vector uv = v@uv;

// Scale UVs
v@uv *= 2.0;

// Offset UVs
v@uv.x += 0.5;
v@uv.y += 0.5;

// Rotate UVs 90 degrees around center
float angle = radians(90.0);
vector center = set(0.5, 0.5, 0);
vector offset = v@uv - center;
v@uv.x = center.x + offset.x * cos(angle) - offset.y * sin(angle);
v@uv.y = center.y + offset.x * sin(angle) + offset.y * cos(angle);

// Per-copy UV offset (for copytopoints with unique UVs)
// int copynum = i@copynum;
// v@uv.x += copynum;   // Offset each copy by one UDIM tile
```

```python
# UV transfer between meshes
import hou

geo = hou.node("/obj/geo1")

# attribtransfer: transfer UVs from source to target (different topology)
xfer = geo.createNode("attribtransfer", "transfer_uvs")
xfer.setInput(0, geo.node("target_mesh"))   # Mesh needing UVs
xfer.setInput(1, geo.node("source_mesh"))   # Mesh with good UVs
xfer.parm("pointattribs").set("")
xfer.parm("vertexattribs").set("uv")        # Transfer vertex UVs
xfer.parm("kernel").set(1)                   # 1=Inverse distance
xfer.parm("maxdist").set(0.1)               # Max transfer distance

# Specialized UV transfer (better for similar geometry)
uv_xfer = geo.createNode("uvtransfer", "uv_match")
uv_xfer.setInput(0, geo.node("target_mesh"))
uv_xfer.setInput(1, geo.node("source_mesh"))

geo.layoutChildren()
print("UV transfer from source to target mesh")
```

```python
# UV workflow for specific asset types
import hou

def uv_character(geo_path):
    """UV workflow for character models.
    Plan seams along natural edges: under arms, inside legs, back of head.
    Separate head, body, hands as distinct UV islands -> UDIM tiles."""
    geo = hou.node(geo_path)
    if not geo:
        return

    mesh = geo.displayNode()

    # Create seam groups for body parts
    seams = geo.createNode("groupcreate", "body_seams")
    seams.setInput(0, mesh)
    seams.parm("groupname").set("seams")
    seams.parm("grouptype").set(2)  # Edge group

    flatten = geo.createNode("uvflatten", "char_uvs")
    flatten.setInput(0, seams)
    flatten.parm("seamgroup").set("seams")

    layout = geo.createNode("uvlayout", "char_udim")
    layout.setInput(0, flatten)
    layout.parm("udimmode").set(1)
    layout.parm("udimtarget").set(1001)

    geo.layoutChildren()
    return layout


def uv_hard_surface(geo_path):
    """UV workflow for hard surface / props.
    Planar projection for flat faces, flatten for curved surfaces."""
    geo = hou.node(geo_path)
    if not geo:
        return

    mesh = geo.displayNode()

    # Planar project flat faces
    project = geo.createNode("uvproject", "flat_faces")
    project.setInput(0, mesh)
    project.parm("projtype").set(0)
    project.parm("inittype").set(1)

    # Layout into single tile
    layout = geo.createNode("uvlayout", "prop_layout")
    layout.setInput(0, project)
    layout.parm("padding").set(0.005)

    geo.layoutChildren()
    return layout


def uv_terrain_triplanar(geo_path):
    """Triplanar projection for terrain -- avoids UV stretching on steep slopes.
    Projects from X, Y, Z axes and blends by normal direction."""
    geo = hou.node(geo_path)
    if not geo:
        return

    mesh = geo.displayNode()

    # Triplanar: three planar projections blended by normal
    wrangle = geo.createNode("attribwrangle", "triplanar_uvs")
    wrangle.setInput(0, mesh)
    wrangle.parm("class").set(1)  # Run over vertices
    wrangle.parm("snippet").set('''
// Triplanar UV projection
vector N = normalize(v@N);
vector P = v@P;
float blend_sharpness = 4.0;

// Blend weights from normal direction
vector weights = pow(abs(N), blend_sharpness);
weights /= (weights.x + weights.y + weights.z);

// Three projections
vector2 uv_x = set(P.y, P.z);  // YZ plane (from X)
vector2 uv_y = set(P.x, P.z);  // XZ plane (from Y, top-down)
vector2 uv_z = set(P.x, P.y);  // XY plane (from Z)

// Weighted blend
vector2 final_uv = uv_x * weights.x + uv_y * weights.y + uv_z * weights.z;
v@uv = set(final_uv.x, final_uv.y, 0);
''')

    geo.layoutChildren()
    return wrangle
```

```python
# UV quality validation
import hou

def check_uv_quality(sop_path):
    """Check UV quality metrics on a SOP node."""
    node = hou.node(sop_path)
    if not node:
        return

    geo = node.geometry()

    # Check if UVs exist
    uv_attrib = geo.findVertexAttrib("uv")
    if not uv_attrib:
        uv_attrib = geo.findPointAttrib("uv")
    if not uv_attrib:
        print("No UV attribute found -- mesh needs UVs")
        return

    uv_class = "vertex" if geo.findVertexAttrib("uv") else "point"
    print(f"UV attribute: {uv_class} class")

    # Check UV range
    uv_min = [float('inf'), float('inf')]
    uv_max = [float('-inf'), float('-inf')]

    if uv_class == "vertex":
        for vtx in geo.iterVertices():
            uv = vtx.attribValue("uv")
            uv_min[0] = min(uv_min[0], uv[0])
            uv_min[1] = min(uv_min[1], uv[1])
            uv_max[0] = max(uv_max[0], uv[0])
            uv_max[1] = max(uv_max[1], uv[1])
    else:
        for pt in geo.points():
            uv = pt.attribValue("uv")
            uv_min[0] = min(uv_min[0], uv[0])
            uv_min[1] = min(uv_min[1], uv[1])
            uv_max[0] = max(uv_max[0], uv[0])
            uv_max[1] = max(uv_max[1], uv[1])

    print(f"UV range: ({uv_min[0]:.3f}, {uv_min[1]:.3f}) to ({uv_max[0]:.3f}, {uv_max[1]:.3f})")

    # For Karma: UVs named "uv" are auto-detected. Other names need explicit binding.
    print("Tip: Karma auto-detects 'uv' attribute. Other names need manual binding.")

check_uv_quality("/obj/geo1/uvlayout1")
```

## Common Mistakes
- UVs on points instead of vertices -- causes texture swimming on animation; promote to vertex UVs
- Seam visible in render -- move seams to hidden areas (under arms, behind ears, bottom of objects)
- Overlapping UV islands -- run `uvlayout` with padding to separate
- Missing padding in layout -- causes texture bleeding at lower mip levels; use 0.005 minimum
- VDB conversion destroys UVs -- always apply UVs after VDB operations, or use `uvproject` post-conversion
- Using wrong UV name for Karma -- must be named `uv` for auto-detection; custom names need binding
- Applying topology changes after UVs -- subdivide, remesh, boolean all break existing UVs; UV last in chain
