# VEX Corpus: Flow & Visualization

> 61 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Intermediate (54 examples)

### Wispy Curves with Curlnoise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize + @Time * 0.3) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Wispy polyline curves grown along normals with curlnoise displacement.
```


### Curl Noise Polylines with Normals

```vex
vector offset = normalize(@N) * {1, 0.3, 1};
int pt = addpoint(0, @P + offset);
addprim(0, "polyline", @ptnum, pt);

vector pos;
int pr;
float stepsize = 0.5;

pr = addprim(0, "polyline");
for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Creates polyline primitives displaced by both point normal and curl noise.
```


### Polyline growth with curl noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Polyline grows from each point along its normal with animated curl noise offset.
```


### Creating Polylines with Curl Noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Six-point polyline with animated curl noise position offsets.
```


### Removing Points with Random Threshold

```vex
// removepoint(int geohandle, int point_number)
// removepoint(int geohandle, string pointgroup, int and_or_prims)

if (rand(@ptnum) < ch("cutoff")) {
    removepoint(0, @ptnum);
}
// Deletes points whose random value falls below the cutoff channel.
```


### Seaweed Example Setup with Random Deletion

```vex
if (rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}

// Spirally seaweed using sin and cos
vector offset, pos;
int n, ps;
float stepsize;

n = chi("nseg");
stepsize = chf("stepsize");
ps = addprim(0, "polyline");
for (int i = 0; i < n; i++) {
    float t = float(i) / float(n);
    offset = set(sin(t * 6.28) * 0.2, 0, cos(t * 6.28) * 0.2);
    pos = @P + @N * i * stepsize + offset;
    int pt = addpoint(0, pos);
    addvertex(0, ps, pt);
}
// Randomly removes primitives, then builds spiral seaweed with sin/cos offset.
```


### Near Points to New Geometry

```vex
int pt1[] = nearpoints(1, @P, ch("d"), 25);
int pt;
vector pos;
foreach (pt; pt1) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}
// Finds up to 25 nearby points from input 1 and creates new points at each position.
```


### Point Cloud Basics Setup

```vex
int pts[] = nearpoints(1, @P, ch("d"), 25);
v@Cd = 1;
foreach (int pt; pts) {
    vector pos = point(1, "P", pt);
    addpoint(0, pos);
}
// Finds nearby points and creates new geometry at each found position.
```


### Point Cloud Creation Loop

```vex
int pts[] = nearpoints(1, @P, ch("d"), 25);
int pt;
vector pos = 0;
foreach (pt; pts) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}
// Finds nearby points within a distance and creates new points at their positions.
```


### Animating Wave with Delays

```vex
v@visualize = 0;
int npts[];
int pts[];
float d, f, t;

pts = nearpoints(1, @P, 40);

foreach (int pt; pts) {
    d = distance(@P, point(1, "P", pt));
    f = fit01(rand(@ptnum), 0.0, 1.0);
    t = @Time - f * 0.5;
    @P.y += sin(t * 6.28 + d * 0.5) * 0.2;
}
// Animated wave with per-point randomized time delays using nearpoints.
```


### Adding Points Conditionally

```vex
if (@ptnum == 0) {
    addpoint(0, @P + set(0, 1, 0));
}
// Adds a point above point zero only — avoids fusing after mass creation.
```


### Adding Points with Offsets

```vex
if (@ptnum == 1) {
    addpoint(0, set(0, 1, 0));
}

addpoint(0, @P + set(0, 1, 0));

addpoint(0, @P + set(0, 5, 0));
// Demonstrates conditional and unconditional addpoint with positional offsets.
```


### addpoint without assignment

```vex
addpoint(0, @P * set(0, 1, 0));

addpoint(0, @P + set(0, 5, 0));

addpoint(0, @P + @N * 0.1);

for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * (i * 0.1));
}
// addpoint() return value can be discarded when the point number is not needed later.
```


### Creating points along normals with loops

```vex
addpoint(0, @P + set(0, 5, 0));

addpoint(0, @P + @N * 4);

for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * (i * 0.1));
}
// Creates points offset from current position along the surface normal.
```


### Creating Points Along Normal with For Loop

```vex
for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * 0.1 * i);
}
// Creates 10 points along the surface normal, each 0.1 units apart.
```


### For loop with addpoint

```vex
int len = chi("len");
for (int i = 0; i < len; i++) {
    addpoint(0, @P + @N * (i * 0.1));
}
// Loop from 0 to len, creating points incrementally along the normal.
```


### Creating Points with addpoint

```vex
for (int i = 0; i < 4; i++) {
    addpoint(0, @P * 0.8 * (1 + 0.1 * i));
}
// Creates 4 new points scaled outward from the current position.
```


### Multiple Points Along Normal with Noise

```vex
vector offset, pos;
int pt, pr;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.15;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Creates wispy lines along the normal direction using curl noise displacement.
```


### Curlnoise wispy hair growth

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize + @Time * 0.3) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Procedural hair-like geometry grown along normals with animated curlnoise.
```


### Implicit normals in VEX

```vex
vector pos = chv("pos") * set(1, 0.3, 1);
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset;
float stepsize = 0.5;
int pr = addprim(0, "polyline");

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// @N can be read implicitly — Houdini auto-calculates normals for geometry primitives.
```


### Polyline with Curl Noise Offset

```vex
vector pos = v@P;
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset;
float stepsize = 0.5;
int pr = addprim(0, "polyline");

for (int i = 0; i < 10; i++) {
    offset = curlnoise(pos + i * stepsize + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Creates polylines from each point along the normal with curl noise offsets.
```


### Implicit normals in geometry creation

```vex
vector pos, offset;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Implicit point normals used when generating geometry along the @N direction.
```


### Normals in Geometry Creation

```vex
vector pos = chv("pos") * set(1, 0, 1);
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset;
float stepsize = 0.5;
int pr = addprim(0, "polyline");

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Implicit normals on grid geometry used when creating new geometry with @N in loops.
```


### Curl Noise Trail Generation

```vex
vector pos = @P;
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", pt, @ptnum);

vector pos2 = @P + noise(@P + @Time) * set(1, 0, 1);
int pt2 = addpoint(0, @P + pos2);
addprim(0, "polyline", @ptnum, pt2);
// Progressive techniques for creating polyline trails from points.
```


### Extruding Polylines with Normals

```vex
vector pos = chv("pos");
int pt = addpoint(0, @P);
addprim(0, "polyline", @ptnum, pt);

vector offset;
float stepsize = 0.5;
int pr = addprim(0, "polyline");

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Extruded polyline geometry along point normals with curl noise displacement.
```


### Normal Calculation Methods for Displacement

```vex
vector pos = chv("pos");
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum, pt);

vector offset;
int pr, pt1;
float bias = 0;
float stepsize = 0.5;

pr = addprim(0, "polyline");
for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize + bias) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt1 = addpoint(0, pos);
    addvertex(0, pr, pt1);
}
// Implicit vs explicit normals — Houdini derives normals from vertex data automatically.
```


### Growing Lines with Curl Noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Polylines grow from each input point along the normal with curl noise at each step.
```


### Curl Noise Trail Generator

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise((@P + i * stepsize) + @Time * 0.3) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Six-step trail with animated curl noise driving each point position.
```


### Creating Polyline with Offset Points

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Polyline with six points positioned along the normal direction.
```


### Animated Fur Using Curlnoise

```vex
int pr = addprim(0, "polyline");
for (int i = 0; i < chi("i"); i++) {
    vector offset = curlnoise(@Time * ch("z")) * ch("z");
    vector pos = @P + @N * i * chf("size") + offset;
    int pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Animated fur strands grown along normals with curlnoise driven by time.
```


### Curl Noise Fur Displacement

```vex
int pr = addprim(0, "polyline");
float stepsize = 0.5;
vector offset, pos;
int pt;

for (int i = 0; i < nprims(@opinput1); i++) {
    offset = curlnoise(@P) * 0.2;
    pos = @P + @N * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Wavy fur created by displacing points with curl noise combined with normal direction.
```


### Curl Noise Grass Generation

```vex
int pr = addprim(0, "polyline");
vector offset, pos;
int pt;

for (int i = 0; i < chi("nseg"); i++) {
    offset = curlnoise((@P + i * chf("amp1")) * chf("freq2"));
    pos = @P + @N * chf("stepsize") + offset;
    pt = addpoint(0, pos);
    addvertex(0, @primnum, pt);
}
// Wavy grass-like geometry created by iterating points displaced by curl noise.
```


### Creating polyline with curl noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.01;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.1;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Six-point polyline with small step size and animated curl noise offset.
```


### Creating Polylines with Curl Noise Offset

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * stepsize + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Six-point polyline primitive with curl noise offsets at each vertex.
```


### Removing Primitives with Conditions

```vex
// removeprim(geohandle, primnum, and_points)
// and_points=1 deletes associated points; and_points=0 keeps them

removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) < ch("cutoff")) {
    removeprim(0, @primnum, 1);
}
// Uses removeprim() to delete primitives; second arg controls associated point deletion.
```


### Random Prim Removal Setup

```vex
if (rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}

// Initialize variables for spiral seaweed
vector offset, pos;
int pr, pt;
// Randomly removes primitives per-primitive based on a seeded cutoff threshold.
```


### Seaweed with random culling and spiral offset

```vex
if (rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}

// Spirally seaweed using sin and cos
vector offset, pos;
int pr, pt;
int nseg = 50;
float stepsize = chf("stepsize");

pr = addprim(0, "polyline");
for (int i = 0; i < nseg; i++) {
    float t = float(i) / float(nseg);
    offset = set(sin(t * 6.28 * 3) * 0.1, 0, cos(t * 6.28 * 3) * 0.1);
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Randomly culls primitives, then creates spiraling seaweed geometry via sin/cos offsets.
```


### Random Point Deletion with Seed

```vex
v@up = set(0, 1, 0);
if (rand(@primnum, ch("seed")) < ch("cutoff")) {
    removepoint(0, @primnum, 1);
}
// Random point deletion using a seeded rand() for reproducible results.
```


### Noise vs Rand for Deletion

```vex
if (rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprim(0, @primnum, 1);
}

int pt = addpoint(0, {0, 1, 0});

if (@ptnum == 0) {
    addpoint(0, {0, 1, 0});
}
// Comparison of rand() vs noise() for structured deletion patterns.
```


### Point Cloud Manual Point Iteration

```vex
int pts[] = pcfind(1, "P", @P, ch("d"), 25);
int pt;
vector pos;
foreach (pt; pts) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}
// Manual point cloud iteration: pcfind nearby points, retrieve positions, create new points.
```


### agentrigchildren

```vex
int[] queue = {transform};
while (len(queue) > 0) {
    int i = removeindex(queue, 0);
    printf("%d\n", i);
    foreach (int child; agentrigchildren(0, @primnum, i)) {
        push(queue, child);
    }
}
// BFS traversal of an agent rig hierarchy using agentrigchildren.
```


### agentrigparent

```vex
int root;
while (true) {
    int parent = agentrigparent(0, @primnum, transform);
    if (parent < 0) {
        root = transform;
        break;
    } else {
        transform = parent;
    }
}
matrix root_xform = agentworldtransform(0, @primnum, root);
// Walks up the agent rig hierarchy to find the root transform.
```


### findattribval

```vex
// Find the primitive whose "id" attribute equals 10
int prim_num = findattribval(0, "prim", "id", 10);
// Note: you can use idtoprim(0, 10) instead
// Searches for a primitive by attribute value; idtoprim() is a faster alternative.
```


### nextsample

```vex
int nsamples = 10;
int sid = israytrace ? SID : newsampler();
float sx, sy;

for (int i = 0; i < nsamples; i++) {
    if (israytrace) {
        nextsample(sid, sx, sy, "mode", "nextpixel");
    } else {
        nextsample(sid, sx, sy, "mode", "qstrat");
    }
    // Sample something using sx/sy...
}
// Quasi-random sampling loop using nextsample; mode differs between ray and pixel contexts.
```


### opstart

```vex
int started = opstart("Performing long operation");
perform_long_operation();
if (started >= 0) {
    opend(started);
}
// opstart/opend bracket long operations to show progress in the Houdini UI.
```


### pcfind

```vex
int closept[] = pcfind(filename, "P", P, maxdistance, maxpoints);
P = 0;
foreach (int ptnum; closept) {
    vector closepos = point(filename, "P", ptnum);
    P += closepos;
}
P /= len(closept);
// Finds nearby points in a point cloud file and averages their positions.
```


### pcfind_radius

```vex
int closept[] = pcfind_radius(
    filename, "P", "pscale", 1.0,
    P, maxdistance, maxpoints
);
P = 0;
foreach (int ptnum; closept) {
    vector closepos = point(filename, "P", ptnum);
    P += closepos;
}
P /= len(closept);
// Like pcfind but uses a per-point scale attribute to weight the search radius.
```


### print_once

```vex
// Only print "Hello world" one time
for (int i = 0; i < 100; ++i) {
    print_once("Hello world\n");
}

// Print a missing texture warning just once across all shaders
print_once(
    sprintf("Missing texture map: %s\n", texture_map),
    "global",
    1
);
// print_once suppresses duplicate messages across all iterations/shaders.
```


### rand

```vex
vector pos = 1;
float seed = 0;
pos *= rand(seed);
// rand() returns a pseudo-random value; multiply by vector to randomize position.
```


### shadowmap

```vex
shadowmap(
    mapname,
    pz,
    spread,
    bias,
    quality,
    "channel",
    channel
);
// Samples a shadow map with spread, bias, and quality parameters.
```


### usd_setcollectionincludes

```vex
// Set the includes list on the cube's collection
string collection_path = usd_makecollectionpath(
    0,
    "/geo/cube",
    "some_collection"
);
usd_setcollectionincludes(
    0,
    collection_path,
    array("/geo/sphere1", "/geo/sphere2")
);
// Builds a USD collection path then sets its includes list to the given prim paths.
```


### usd_setpurpose

```vex
// Set the sphere primitive to be traversable only for rendering
usd_setpurpose(0, "/geo/sphere", "render");
// Sets USD purpose on a prim: "render", "proxy", "guide", or "" (default).
```


### usd_setvisibility

```vex
#include <usd.h>
// Make the sphere primitive visible
usd_setvisibility(0, "/geo/sphere", USD_VISIBILITY_VISIBLE);

// Configure the cube primitive to inherit visibility from parent
usd_setvisibility(0, "/geo/cube", USD_VISIBILITY_INHERIT);
// Controls USD visibility: USD_VISIBILITY_VISIBLE or USD_VISIBILITY_INHERIT.
```


### vnoise

```vex
// 1D noise
float fp0, fp1, p1x, p1y, p2x, p2y;
vector vp0, vp1;
float f1, f2;
int seed = 0;

vnoise(s * 10, 0.8, seed, f1, f2, fp0, fp1);
vnoise(s * 10, t * 10, 0.8, 0.8, seed, f1, f2, p1x, p1y, p2x, p2y);
vnoise(P * 10, {0.8, 0.8, 0.8}, seed, f1, f2, vp0, vp1);
// Voronoi noise in 1D, 2D, and 3D forms; returns feature distances and cell positions.
```


## Advanced (6 examples)

### Create geometry

```vex
int pt = addpoint(0, {0, 3, 0});
// Minimal geometry creation — addpoint returns the new point number.
```


### Remove geometry, nearpoints, parallel code

```vex
float max = ch("max");
int limit = chi("limit");
int pts[] = nearpoints(0, @P, max);
if (len(pts) > limit) {
    removepoint(0, @ptnum);
}
// Removes over-dense points: if more than `limit` neighbors exist within `max` radius, delete the point.
```


### Orient via vector length

```vex
vector axis;
axis = chv("axis");
axis = normalize(axis);
axis *= 0;

@orient = quaternion(axis);
// Defines a quaternion from a scaled axis vector; zero-length axis yields identity rotation.
```


### Quaternion Rotation with Slerp

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv("axis");
axis = normalize(axis);
seed = noise(@P + @Time);
seed = chramp("noise_remap", seed);
blend = seed;

// Build a 90-degree rotation around the axis
target = quaternion(radians(90), axis);
base = set(0, 0, 0, 1);  // identity
@orient = slerp(base, target, blend);
// Noise-driven random 90-degree rotations, smoothly interpolated via slerp.
```


### For loops with addpoint

```vex
for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * (i * 0.1));
}
// Creates 10 points along the normal, each 0.1 units from the previous.
```


### Removing Geometry with VEX

```vex
removepoint(0, @ptnum);

removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) < ch("cutoff")) {
    removeprim(0, @primnum, 1);
}
// Demonstrates removepoint() and removeprim(); second arg on removeprim controls point deletion.
```


## Expert (1 examples)

### Pseudo Attributes and Compilation

```vex
// VCC compiler command (not VEX code)
// VCC -q $VOP_INCLUDEPATH -o $VOP_OBJECTFILE -e $VOP_ERRORFILE $VOP_SOURCEFILE

// Pseudo attributes are auto-injected by Houdini's VEX compiler:
// @P      -> position (vector)
// @ptnum  -> current point number (int)
// @Time   -> current time in seconds (float)
// @Frame  -> current frame number (float)
// @opinput1 -> handle to second input geometry (int)
// Pseudo attributes like @P, @ptnum, @Time are compiler-injected — not stored on geometry.
```

