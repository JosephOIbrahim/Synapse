# Common Houdini Geometry Attributes

## Triggers
attribute, point attribute, prim attribute, vertex attribute, Cd, N, P, pscale,
orient, velocity, uv, rest, copy to points, instancing attribute, volume attribute

## Context
Reference for standard Houdini geometry attributes with code examples showing
creation, reading, and common patterns. Covers point, prim, vertex, detail, and
special-purpose attributes.

## Code

```python
# Create and read common point attributes
import hou

geo_node = hou.node("/obj/geo1/attribwrangle1")

# --- Reading attributes via Python ---
sop = hou.node("/obj/geo1/OUT")
if sop:
    geo = sop.geometry()

    # Read point positions
    positions = geo.pointFloatAttribValues("P")
    print(f"Point count: {geo.intrinsicValue('pointcount')}")

    # Read normals (if they exist)
    if geo.findPointAttrib("N"):
        normals = geo.pointFloatAttribValues("N")

    # Read colors
    if geo.findPointAttrib("Cd"):
        colors = geo.pointFloatAttribValues("Cd")

    # Read pscale
    if geo.findPointAttrib("pscale"):
        scales = geo.pointFloatAttribValues("pscale")

    # Read string attributes
    if geo.findPointAttrib("name"):
        names = geo.pointStringAttribValues("name")
```

```vex
// --- Point Attributes (VEX) ---

// Position (always exists)
v@P = set(0, 1, 0);  // move point to (0, 1, 0)

// Normal
v@N = normalize(v@P);  // point normal outward from origin

// Color (RGB, 0-1 range)
v@Cd = set(1, 0, 0);  // red

// Velocity (units/second, used for motion blur)
v@v = set(1, 0, 0);  // moving +X at 1 unit/sec

// Point scale (uniform, for copy-to-points)
f@pscale = 0.5;

// Non-uniform scale (vector3)
v@scale = set(1, 2, 1);  // stretch Y

// Orientation quaternion (highest priority for copy-to-points)
p@orient = quaternion(radians(45), set(0, 1, 0));  // 45 deg around Y

// Up vector (used with N for rotation, lower priority than orient)
v@up = set(0, 1, 0);

// Stable particle ID (survives death/birth in sims)
i@id = @ptnum;

// Age and lifespan (seconds)
f@age = 0.0;
f@life = 2.5;

// Rest position (lock procedural noise to surface)
v@rest = v@P;

// UV coordinates
v@uv = set(float(@ptnum) / float(@numpt), 0, 0);

// Material assignment
s@shop_materialpath = "/materials/hero_mtl";
```

```vex
// --- Primitive Attributes (VEX, run over Primitives) ---

// Prim name (controls USD prim path in Solaris)
s@name = sprintf("piece_%d", @primnum);

// Per-prim material
s@shop_materialpath = "/materials/ground_mtl";

// Alembic/USD hierarchy path
s@path = sprintf("/geo/pieces/piece_%d", @primnum);
```

```vex
// --- Detail Attributes (VEX, run over Detail) ---

// Store aggregate values
f@total_area = 0;
for (int i = 0; i < @numprim; i++) {
    f@total_area += primintrinsic(0, "measuredarea", i);
}

// Bounding box
vector bbox_min = getbbox_min(0);
vector bbox_max = getbbox_max(0);
v@bbox_center = (bbox_min + bbox_max) / 2.0;
f@bbox_size = length(bbox_max - bbox_min);
```

```vex
// --- Vertex Attributes (VEX, run over Vertices) ---

// Per-vertex UV (overrides point-level UV)
v@uv = set(vertexindex(0, @primnum, @vtxnum), 0, 0);

// Per-vertex normal (overrides point normal for hard edges)
v@N = prim_normal(0, @primnum, set(0.5, 0.5, 0));

// Per-vertex color
v@Cd = set(1, 0, 0);
```

```vex
// --- Copy-to-Points attribute priority ---
// The copytopoints SOP reads these from target points in this order:
//
// Rotation priority (highest to lowest):
//   1. p@orient   -- quaternion rotation (full control)
//   2. v@N + v@up -- rotation from normal and up vector
//   3. v@N alone  -- rotation from normal, up = {0,1,0}
//
// Scale:
//   1. v@scale    -- non-uniform scale (x, y, z)
//   2. f@pscale   -- uniform scale (single float)
//
// Other:
//   v@P           -- position (required)
//   v@v           -- velocity (for motion blur on instances)
//   v@pivot       -- pivot offset for rotation

// Example: scatter with random orientation
p@orient = quaternion(radians(rand(@ptnum) * 360), set(0, 1, 0));
f@pscale = fit01(rand(@ptnum + 1), 0.5, 1.5);
```

```vex
// --- Pyro / Volume Attributes ---
// These are volume primitives, not point attributes

// density: smoke/fire density (0-1+)
// temperature: heat for buoyancy calculation
// flame: visible flame intensity (0-1)
// fuel: combustible fuel source
// vel.x, vel.y, vel.z: volume velocity field components

// Read volume values in VEX:
float d = volumesample(0, "density", v@P);
float t = volumesample(0, "temperature", v@P);
vector vel = volumesamplev(0, "vel", v@P);
```

```vex
// --- FLIP Fluid Attributes ---
f@viscosity = 0.5;     // per-particle viscosity override
f@surface = 0.0;       // surface distance (from particlefluidsurface)
v@vorticity = set(0);  // curl of velocity field
f@droplet = 0.0;       // isolated particle flag for spray meshing
```

```vex
// --- RBD Constraint Attributes ---
s@constraint_name = "glue";     // constraint type
i@constraint_type = 0;          // 0=position, 1=rotation
f@strength = 1000.0;            // breaking threshold (force)
s@anchor_name = "piece_0";      // connected piece name
```

```python
# --- Intrinsic Attributes (read-only, via Python) ---
import hou

geo = hou.node("/obj/geo1/OUT").geometry()
for prim in geo.prims()[:5]:
    area = prim.intrinsicValue("measuredarea")
    perimeter = prim.intrinsicValue("measuredperimeter")
    typename = prim.intrinsicValue("typename")
    print(f"Prim {prim.number()}: type={typename}, area={area:.4f}, perim={perimeter:.4f}")

# For packed prims
for prim in geo.prims():
    if prim.intrinsicValue("typename") == "PackedGeometry":
        xform = prim.intrinsicValue("packedfulltransform")
        print(f"Packed prim {prim.number()} transform: {xform}")
```

## Common Mistakes
- Using v@P for noise input on deforming geo -- use v@rest instead to prevent swimming
- Forgetting type prefix on VEX attributes (f@, v@, i@, s@, p@)
- Writing to read-only attributes (@ptnum, @numpt, @Frame)
- Using @orient AND @N+@up together -- orient takes priority, @N is ignored
- Setting pscale=0 instead of deleting points -- creates zero-scale instances
- Using point-level UV when vertex-level UV is needed for hard seams
