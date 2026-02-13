# VEX Attribute Access Patterns

## Built-in Point Attributes

| Attribute | Type | Description | Default |
|-----------|------|-------------|---------|
| `@P` | vector | Position | {0,0,0} |
| `@N` | vector | Normal | {0,0,0} |
| `@Cd` | vector | Color (RGB 0-1) | {1,1,1} |
| `@Alpha` | float | Opacity | 1.0 |
| `@v` | vector | Velocity | {0,0,0} |
| `@pscale` | float | Point scale | 1.0 |
| `@orient` | vector4 | Orientation quaternion | {0,0,0,1} |
| `@up` | vector | Up vector (with @N for frame) | {0,1,0} |
| `@id` | int | Persistent ID (survives topology changes) | -1 |
| `@age` | float | Particle age (seconds) | 0.0 |
| `@life` | float | Particle lifespan (seconds) | -1 |
| `@rest` | vector | Rest position (for noise stability) | @P at creation |
| `@width` | float | Curve/line width | 0.0 |
| `@uv` | vector | UV coordinates | {0,0,0} |

## Context Variables (Read-Only)

| Variable | Type | Description |
|----------|------|-------------|
| `@ptnum` | int | Current point index (0-based) |
| `@numpt` | int | Total number of points |
| `@primnum` | int | Current primitive index |
| `@numprim` | int | Total number of primitives |
| `@vtxnum` | int | Current linear vertex index |
| `@numvtx` | int | Total number of vertices |
| `@elemnum` | int | Current element (generic, any run-over) |
| `@numelem` | int | Total elements (generic) |
| `@Time` | float | Current time in seconds |
| `@Frame` | float | Current frame number |
| `@TimeInc` | float | Time step between frames |
| `@OpInput1` | string | Path to first input node |

## Reading Attributes

### @-Shorthand (current element, fastest)
```vex
vector pos = @P;
float scale = @pscale;
int myint = i@myattr;
string name = s@name;
```

### Function Syntax (any element, any input)
```vex
// Read from any point on any input
vector pos = point(0, "P", 5);
vector target = point(1, "P", @ptnum);

// Read prim/vertex/detail
string name = prim(0, "name", @primnum);
vector uv = vertex(0, "uv", @vtxnum);
int count = detail(0, "numitems");
```

## Writing Attributes

### @-Shorthand (creates if doesn't exist)
```vex
@P = {0, 1, 0};
@Cd = {1, 0, 0};
f@density = 1.5;
v@myvel = set(1, 0, 0);
i@class = floor(rand(@ptnum) * 5);
s@name = sprintf("pt_%d", @ptnum);
```

### Function Syntax (any element, with mode)
```vex
setpointattrib(0, "Cd", ptnum, {1,0,0}, "set");
setprimattrib(0, "name", primnum, "group_a", "set");
setdetailattrib(0, "total_area", area, "set");

// Mode: "set", "add", "min", "max", "mult"
setpointattrib(0, "density", pt, 0.1, "add");  // Accumulate
```

## Groups

```vex
// Add/remove from group
i@group_selected = 1;
i@group_selected = 0;

// Check membership
if (inpointgroup(0, "mygroup", @ptnum)) { ... }
if (inprimgroup(0, "walls", @primnum)) { ... }

// Group from condition
i@group_large = (@pscale > 0.5) ? 1 : 0;
```

## Intrinsic Attributes

```vex
// Computed on-the-fly, not stored as regular attributes
float area = primintrinsic(0, "measuredarea", @primnum);
vector bounds = primintrinsic(0, "bounds", @primnum);
string type = primintrinsic(0, "typename", @primnum);
int closed = primintrinsic(0, "closed", @primnum);
```

## Attribute Promotion Patterns

### Point to Detail (sum all points) -- run over Detail
```vex
float total = 0;
for (int i = 0; i < npoints(0); i++) {
    total += point(0, "area", i);
}
f@total_area = total;
```

### Detail to Point (broadcast) -- run over Points
```vex
f@threshold = detail(0, "threshold");
```

### Nearest-Point Transfer (from input 1)
```vex
int near = nearpoint(1, @P);
if (near >= 0) {
    @Cd = point(1, "Cd", near);
}
```

### Distance-Weighted Blend (from input 1)
```vex
int pts[] = pcfind(1, "P", @P, chf("radius"), chi("maxpts"));
vector total_cd = {0,0,0};
float total_w = 0;
foreach (int pt; pts) {
    float d = distance(@P, point(1, "P", pt));
    float w = 1.0 / max(d, 0.001);
    total_cd += point(1, "Cd", pt) * w;
    total_w += w;
}
if (total_w > 0) @Cd = total_cd / total_w;
```
