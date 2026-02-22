# VEX Attribute Access Patterns

## Triggers
attribute, attrib, point, prim, vertex, detail, group, intrinsic,
read attribute, write attribute, promote, transfer, pcfind

## Context
VEX attribute access patterns: reading, writing, groups, intrinsics,
promotion, and transfer between elements and inputs.

## Code

```vex
// Built-in point attributes reference
// @P       vector   Position
// @N       vector   Normal
// @Cd      vector   Color (RGB 0-1)
// @Alpha   float    Opacity
// @v       vector   Velocity
// @pscale  float    Point scale
// @orient  vector4  Orientation quaternion
// @up      vector   Up vector (with @N for frame)
// @id      int      Persistent ID (survives topology changes)
// @age     float    Particle age (seconds)
// @life    float    Particle lifespan (seconds)
// @rest    vector   Rest position (for noise stability)
// @width   float    Curve/line render width
// @uv      vector   UV coordinates

// Context variables (read-only)
// @ptnum   int      Current point index (0-based)
// @numpt   int      Total number of points
// @primnum int      Current primitive index
// @numprim int      Total number of primitives
// @vtxnum  int      Current linear vertex index
// @numvtx  int      Total number of vertices
// @Time    float    Current time in seconds
// @Frame   float    Current frame number
// @TimeInc float    Time step between frames
```

```vex
// Reading attributes: @-shorthand (current element, fastest)
vector pos = @P;
float scale = @pscale;
int myint = i@myattr;
string name = s@name;

// Function syntax: any element, any input
vector pos0 = point(0, "P", 5);           // Point 5 on input 0
vector target = point(1, "P", @ptnum);     // Same ptnum on input 1
string pname = prim(0, "name", @primnum);  // Prim attribute
vector uv = vertex(0, "uv", @vtxnum);     // Vertex attribute
int count = detail(0, "numitems");         // Detail (global) attribute
```

```vex
// Writing attributes: @-shorthand (creates if doesn't exist)
@P = {0, 1, 0};
@Cd = {1, 0, 0};
f@density = 1.5;
v@myvel = set(1, 0, 0);
i@class = floor(rand(@ptnum) * 5);
s@name = sprintf("pt_%d", @ptnum);

// Function syntax: any element, with accumulation mode
setpointattrib(0, "Cd", @ptnum, {1,0,0}, "set");
setprimattrib(0, "name", @primnum, "group_a", "set");
setdetailattrib(0, "total_area", 0.0, "set");

// Mode: "set", "add", "min", "max", "mult"
setpointattrib(0, "density", @ptnum, 0.1, "add");  // Accumulate
```

```vex
// Groups: create, test, and set membership
// Add/remove from group
i@group_selected = 1;  // Add to group "selected"
i@group_selected = 0;  // Remove from group

// Check membership
if (inpointgroup(0, "mygroup", @ptnum)) {
    @Cd = {1, 0, 0};  // Color grouped points red
}
if (inprimgroup(0, "walls", @primnum)) {
    removeprim(0, @primnum, 1);
}

// Group from condition
i@group_large = (@pscale > 0.5) ? 1 : 0;
i@group_top = (@P.y > ch("height")) ? 1 : 0;
```

```vex
// Intrinsic attributes: computed on-the-fly, not stored
float area = primintrinsic(0, "measuredarea", @primnum);
vector bounds = primintrinsic(0, "bounds", @primnum);
string type = primintrinsic(0, "typename", @primnum);
int closed = primintrinsic(0, "closed", @primnum);

// Set intrinsics (some are writable)
setprimintrinsic(0, "closed", @primnum, 1);
```

```vex
// Attribute promotion: point -> detail (sum all points)
// Run over Detail
float total = 0;
for (int i = 0; i < npoints(0); i++) {
    total += point(0, "area", i);
}
f@total_area = total;

// Average position (detail mode)
vector avg = {0, 0, 0};
for (int i = 0; i < npoints(0); i++) {
    avg += point(0, "P", i);
}
v@centroid = avg / max(npoints(0), 1);
```

```vex
// Detail -> point (broadcast)
// Run over Points
f@threshold = detail(0, "threshold");
```

```vex
// Nearest-point transfer from second input
int near = nearpoint(1, @P);
if (near >= 0) {
    @Cd = point(1, "Cd", near);
    f@density = point(1, "density", near);
}

// Distance-weighted blend from second input (KD-tree, fast)
int pts[] = pcfind(1, "P", @P, chf("radius"), chi("maxpts"));
vector total_cd = {0, 0, 0};
float total_w = 0;
foreach (int pt; pts) {
    float d = distance(@P, point(1, "P", pt));
    float w = 1.0 / max(d, 0.001);
    total_cd += point(1, "Cd", pt) * w;
    total_w += w;
}
if (total_w > 0) @Cd = total_cd / total_w;
```

```vex
// Check attribute existence before reading
if (haspointattrib(0, "density")) {
    f@density = point(0, "density", @ptnum);
}
if (hasprimattrib(0, "name")) {
    s@name = prim(0, "name", @primnum);
}

// Get attribute info
int atype = attribtype(0, "point", "Cd");     // 0=int, 1=float, 2=string
int asize = attribsize(0, "point", "Cd");     // Number of components (3 for vector)
```

## Common Mistakes
- Using @P in Detail mode -- @P is undefined in Detail; use point(0, "P", index) instead
- Forgetting type prefix on first use -- `@myattr` defaults to float; use `v@myattr` for vector
- Reading from wrong input -- point(0, ...) reads current geo, point(1, ...) reads second input
- Using nearpoints instead of pcfind -- nearpoints is O(n), pcfind uses KD-tree O(log n)
- Setting group with wrong prefix -- use `i@group_name`, not `@group_name` (float truncation)
