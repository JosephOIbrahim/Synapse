# VEX Corpus: Edge & Topology

> 88 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Beginner (2 examples)

### Linear vertex or find the starting point on every curve

```vex
// @vtxnum is the linear vertex index; useful to identify the first vertex of each curve
i@a = @vtxnum;

// Identify the first vertex of each curve: vertex 0 of its primitive
// vertexprimindex returns local offset within the primitive
int local_vtx = vertexprimindex(0, @vtxnum);
if (local_vtx == 0) {
    // This is the first vertex on its curve
    i@is_start = 1;
} else {
    i@is_start = 0;
}
```

### Ensure unique names

```vex
// Append primnum to @name to guarantee uniqueness across copied geometry
@name += '_' + itoa(@primnum);

// Common pattern: build a fully qualified name from class + primnum
string base = s@class;
if (len(base) == 0) base = "prim";
@name = base + '_' + itoa(@primnum);
```

## Intermediate (80 examples)

### Cross product

```vex
// Cross @N with up axis to produce a vector perpendicular to both.
// Result is the tangent direction along the surface at each point.
@N = cross(@N, {0,1,0});

// Normalize to keep unit length after the cross
@N = normalize(@N);
```

### Cross Product Right Hand Rule

```vex
// Two successive cross products; first produces a tangent, second re-orients @N.
// The right-hand rule means: fingers point from A toward B, thumb points to result.
vector tmp = cross(@N, {0,1,0});   // tangent in XZ plane
@N = cross(@N, tmp);               // binormal back around to a downward normal
@N = normalize(@N);
```

### Cross product vector orientation

```vex
// Cross with an arbitrary axis to skew the resulting normal direction.
// {1,1,0} is diagonally oriented; adjust axis to control the lean angle.
@N = cross(@N, {1,1,0});
@N = normalize(@N);
```

### Cross Product for Normal Calculation

```vex
// Cross velocity with an axis vector to derive a surface normal
@N = cross(@v, {1,1,0});

// Alternative: build normal from two successive velocity crosses
vector tmp = cross(@v, {0,1,0});
@N = cross(tmp, @v);
```

### Double Cross Product

```vex
// Cross with negative-Y to flip the direction before the second cross
vector tmp = cross(@N, {0, -1, 0});
@N = cross(@N, tmp);
```

### Cross product for hair combing

```vex
// Double cross creates a combed-down effect on surface normals
vector tmp = cross(@N, {0, 1, 0});
@N = cross(@N, tmp);
```

### Cross Product for Gravity Combing

```vex
// Cross velocity with the tangent plane to comb normals toward gravity
vector tmp = cross(@N, {0, 1, 0});
@N = cross(@v, tmp);
```

### Gravity-Based Vector Combing

```vex
// Swap argument order in the second cross to reverse the comb direction
vector tmp = cross(@N, {0,1,0});
@N = cross(tmp, @N);
```

### Double Cross Product for Grooming

```vex
// Repeated cross products accumulate rotation; orients normals downward
vector tmp = cross(@N, {0,1,0});
tmp = cross(@N, tmp);
tmp = cross(@N, tmp);
tmp = cross(@N, tmp);
@N = cross(@N, tmp);
```

### Iterative Cross Product Rotations

```vex
// Each iteration rotates the accumulated vector another 90 degrees
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

### Sequential Cross Products for Vector Rotation

```vex
// Two iterations: tangent then binormal-aligned normal
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

### Iterative Cross Product Application

```vex
// Five iterations build a strongly rotated normal direction
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

### Normalizing Points and Relative Bounding Box

```vex
// Project points onto unit sphere, then colorize by normalized Y position
@P = normalize(@P);

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;
```

### Using chramp with relpointbbox

```vex
// Basic bounding-box color visualization
vector bbox = relpointbbox(0, @P);
@Cd = relpointbbox(0, @P);

// Assign bounding-box vector directly as color
vector bbox2 = relpointbbox(0, @P);
@Cd = bbox2;

// Displace along normal, scaled by bounding-box Y and a channel ramp
vector bbox3 = relpointbbox(0, @P);
@P += @N * bbox3.y * ch('scale');
```

### Creating polylines with noise-driven endpoints

```vex
// Grow a zero-length polyline from each point (baseline)
int pt = addpoint(0, @P + 0);
addprim(0, 'polyline', @ptnum, pt);

// Grow toward a fixed world-space target
int pt2 = addpoint(0, {0,3,0});
addprim(0, 'polyline', @ptnum, pt2);

// Grow one unit along the surface normal
int pt3 = addpoint(0, @P - @N);
addprim(0, 'polyline', @ptnum, pt3);
```

### Procedural Fur Using Polylines

```vex
// Create a 6-segment polyline fur strand from each surface point
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * 0.5);
    pos    = @P + @N * i * stepsize + offset * 0.1;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Procedural Grass with Animated Curvature

```vex
// Grass blades that animate with @Time via curlnoise
vector offset, pos;
int pr, pt;
float stepsize = 0.1;

pr = addprim(0, 'polyline');
for (int i = 0; i < 8; i++) {
    offset = curlnoise(@P + i * 0.3 + @Time);
    pos    = @P + @N * i * stepsize + offset * 0.05;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Creating Polylines with Different Primitive Types

```vex
// Polyline with curl-noise driven points; vary stepsize to change density
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P * 2 + i * 0.4);
    pos    = @P + @N * i * stepsize + offset * 0.2;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Removing Primitives Conditionally

```vex
// Delete a point by number
removepoint(0, @ptnum);

// Delete a primitive and keep its points
removeprim(0, @primnum, 1);

// Delete a primitive but remove its points too
removeprim(0, @primnum, 0);

// Randomly cull primitives using a threshold channel
if (rand(@ptnum) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
```

### Identity Quaternion for Orient Attribute

```vex
// Identity quaternion: no rotation, aligns copies to world axes.
// Use this as a default before building a rotation from N/up vectors.
@orient = {0, 0, 0, 1};

// Build orient from normal + up for instancing (common pattern)
vector up   = {0, 1, 0};
vector side = normalize(cross(@N, up));
up          = normalize(cross(side, @N));
matrix3 m   = set(side, up, @N);
@orient     = quaternion(m);
```

### Animating Primitive Closed State

```vex
// Randomly open/close curves each frame based on primnum seed.
// Values > 0 close the primitive; 0 leaves it open.
int openLove = int(rand(@primnum * @Frame * 7));
setprimintrinsic(0, "closed", @primnum, openLove);
```

### Setting closed intrinsic randomly

```vex
// Produce 0 or 1 per primitive; toggles polygon outline vs filled face
int openclose = int(rand(@primnum * @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```

### Setting Primitive Closed Intrinsic

```vex
// Squaring the random result biases toward 0 (more closed frames)
int openclose = int(rand(@primnum * @Frame) ** 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```

### Random Open/Closed Primitives

```vex
// Simple frame-animated open/close toggle
int openlook = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openlook);
```

### Randomizing Primitive Closed State

```vex
// Multiply-based seed for the random call
int openClose = int(rand(@primnum * @Frame) * 2);
setprimintrinsic(0, 'closed', @primnum, openClose);

// Addition-based seed — different spatial distribution
int openClose2 = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, 'closed', @primnum, openClose2);
```

### Transferring Attributes from Second Input

```vex
// Find nearest point on input 0, copy its color to input 1 points.
// Run this wrangle over input 1 geometry.
int pt = nearpoint(0, v@P);
@Cd = point(0, 'Cd', pt);

// Also copy a float attribute and a vector attribute from the nearest point
f@density = point(0, 'density', pt);
v@vel     = point(0, 'v',       pt);
```

### Rotating Normals with Cross Products

```vex
// Three iterations: produces a 270-degree equivalent rotation
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

### Cross Product Rotation

```vex
// Six iterations of cross-product accumulation for full rotation
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
```

### Conditional Point Creation with addpoint

```vex
// Without a condition every input point creates an extra point (doubles geo)
int pt = addpoint(0, {0,3,0});

// Guard with a condition so only point 0 adds the extra geometry
if (@ptnum == 0) {
    addpoint(0, {0,5,0});
}
```

### Creating Lines Between Points

```vex
// Add a point at world origin, connect it to the current point with a polyline
int pt = addpoint(0, {0,1,0});
addprim(0, 'polyline', @ptnum, pt);
```

### Creating polylines from points

```vex
// Connect current point to origin
int pt0 = addpoint(0, {0,0,0});
addprim(0, 'polyline', @ptnum, pt0);

// Connect current point to Y=1
int pt1 = addpoint(0, {0,1,0});
addprim(0, 'polyline', @ptnum, pt1);

// Grow one step along surface normal
int pt2 = addpoint(0, @P + @N);
addprim(0, 'polyline', @ptnum, pt2);
```

### Polyline with Curl Noise Offset

```vex
// Build a fur strand using curlnoise to offset each segment
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * stepsize);
    pos    = @P + @N * i * stepsize + offset * 0.15;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Creating polylines with curl noise

```vex
// Six-segment strand; curlnoise provides organic variation
vector offset, pos;
int pr, pt;
float stepSize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P * 1.5 + i * 0.3);
    pos    = @P + @N * i * stepSize + offset * 0.1;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Creating polyline with for loop

```vex
// Iterate over all points to build per-point polyline strands
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < @numpt; i++) {
    offset = curlnoise(@P + i * 0.2);
    pos    = @P + @N * i * stepsize + offset * 0.1;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Growing Polylines with Curvoise

```vex
// Classic 6-step growth; curvoise-style randomisation via curlnoise
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * stepsize + rand(@primnum));
    pos    = @P + @N * i * stepsize + offset * 0.2;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Animated Fur Using Curlnoise

```vex
// Animate the noise lookup with @Time for wind-blown fur
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + i * 0.3 + @Time * 0.5);
    pos    = @P + @N * i * stepsize + offset * 0.15;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Dynamic polyline growth with loop

```vex
// Loop count driven by a per-point integer attribute @i
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < @i; i++) {
    offset = curlnoise(@P * 2 + i * stepsize);
    pos    = @P + @N * i * stepsize + offset * 0.1;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Loop-based Polyline Creation

```vex
// Ten-step polyline; good base template for variable-length strands
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * 0.4);
    pos    = @P + @N * i * stepsize + offset * 0.1;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Creating polylines with for loops

```vex
// High segment count (61) for dense, smooth strands
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 61; i++) {
    offset = curlnoise(@P + i * 0.1);
    pos    = @P + @N * i * stepsize + offset * 0.05;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### For Loop Geometry Creation

```vex
// Six-point strand with time-animated curlnoise displacement
vector offset, pos;
int pr, pt;
float stepsize = 0.5;

pr = addprim(0, 'polyline');
for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P * 2 + i * 0.3 + @Time);
    pos    = @P + @N * i * stepsize + offset * 0.12;
    pt     = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Noise vs Rand for Deletion

```vex
// rand() gives uncorrelated per-primitive values; good for scatter deletion
if (rand(@primnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}

// Grow a test polyline from origin to point along normal
int pt = addpoint(0, {0,3,0});
addprim(0, 'polyline', @primnum, pt);

int pt2 = addpoint(0, @P + @N);
addprim(0, 'polyline', @primnum, pt2);
```

### Random Curve Open/Close with setprimintrinsic

```vex
// Square the random output to skew distribution toward closed
int openclose = int(rand(@primnum * @Frame) ** 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```

### Randomly Toggle Primitive Closed Intrinsic

```vex
// Multiply by 2 then truncate to get 0 or 1
int openclose = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```

### Randomizing Primitive Open/Closed State

```vex
// Uses multiplication seed for more spatially varied results
int open_loop = int(rand(@primnum * @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, open_loop);
```

### Random Polygon Open/Closed Animation

```vex
// Addition seed; each primitive independently flips per frame
int openCase = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openCase);
```

### Random Open/Closed Polygon Animation

```vex
// primuv-based seed (less common)
int openCase = int(rand(@primuv[0] * rand(@primnum)) * 2);
setprimintrinsic(0, 'closed', @primnum, openCase);

// Standard addition seed for comparison
int openClose = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, 'closed', @primnum, openClose);
```

### nearpoints point cloud query

```vex
// Find up to 25 neighbours within distance ch('d'), then scatter new points
int pts[] = nearpoints(1, @P, ch('d'), 25);
v@N = {0,0,0};
foreach (int pt; pts) {
    vector pos = point(1, "P", pt);
    addpoint(0, pos);
}
```

### agentlayerbindings

```vex
// Retrieve the collision layer, then iterate over its static bindings
// to accumulate world transforms for each bound joint.
string layer = agentcollisionlayer(0, @primnum);
int[] bindings = agentlayerbindings(0, @primnum, layer, "static");
matrix xforms[] = agentworldtransforms(0, @primnum);
foreach (int idx; bindings) {
    matrix xform = xforms[idx];
}
```

### agentrigfind

```vex
// Look up the Hips joint index; if found, read its local transform.
int idx = agentrigfind(0, @primnum, "Hips");
if (idx >= 0) {
    matrix local_xforms[] = agentlocaltransforms(0, @primnum);
    matrix xform = local_xforms[idx];
}
```

### bouncemask

```vex
// Combine reflect and refract bounce masks into a single bitmask.
// Use in a surface/light shader to test which bounce types are active.
int reflect_or_refract = bouncemask("reflect refract");

// Test a specific bounce type in a shader context
if (bouncemask("diffuse") & reflect_or_refract) {
    // handle diffuse + reflect/refract overlap
}
```

### hedge_dstpoint

```vex
// Get the destination point of half-edge number 3.
// Half-edge goes from srcpoint -> dstpoint along an edge.
int dstpt;
dstpt = hedge_dstpoint("defgeo.bgeo", 3);

// Get both endpoints of the half-edge
int srcpt = hedge_srcpoint("defgeo.bgeo", 3);
// Edge spans from srcpt to dstpt
```

### hedge_equivcount

```vex
// Classify an edge as boundary, interior, or non-manifold
int is_boundary    = 0;
int is_interior    = 0;
int is_nonmanifold = 0;

int numeq = hedge_equivcount("defgeo.bgeo", 3);
if (numeq == 1)
    is_boundary = 1;
else if (numeq >= 3)
    is_nonmanifold = 1;
else
    is_interior = 1;
```

### hedge_isequiv

```vex
// Test if half-edges 2 and 3 are oppositely oriented equivalents
int opposite = 0;
if (hedge_isequiv("defgeo.bgeo", 2, 3)) {
    if (hedge_srcpoint("defgeo.bgeo", 2) == hedge_dstpoint("defgeo.bgeo", 3))
        opposite = 1;
}
```

### hedge_isprimary

```vex
// Count edges (not half-edges) by checking the primary flag.
// Every undirected edge has exactly one primary half-edge.
int numedges = 0;
if (hedge_isprimary("defgeo.bgeo", 3))
    numedges++;

// Walk all half-edges of a primitive and count only primary ones
int start = primhedge(0, @primnum);
int h = start;
int edge_count = 0;
do {
    if (hedge_isprimary(0, h))
        edge_count++;
    h = hedge_next(0, h);
} while (h != start);
```

### hedge_isvalid

```vex
// Only query source point if the half-edge index is valid.
// hedge_* functions return -1 for invalid indices; always guard.
int srcpt = -1;
if (hedge_isvalid("defgeo.bgeo", 3))
    srcpt = hedge_srcpoint("defgeo.bgeo", 3);

// Safe pattern: check validity before any hedge traversal
int h = pointhedge(0, @ptnum);
if (hedge_isvalid(0, h)) {
    int dstpt = hedge_dstpoint(0, h);
}
```

### hedge_next

```vex
// Advance to the next half-edge around the primitive face.
// Traverses the face loop: hedge -> next -> next -> ... -> back to start.
int nexthedge;
nexthedge = hedge_next("defgeo.bgeo", 3);

// Walk an entire face loop
int start = primhedge(0, @primnum);
int cur   = start;
int vtx_count = 0;
do {
    vtx_count++;
    cur = hedge_next(0, cur);
} while (cur != start);
// vtx_count now equals the number of vertices in this primitive
```

### hedge_nextequiv

```vex
// Count all half-edges equivalent to half-edge 3 by walking the equivalence ring
int num_equiv = 0;
int h = 3;
do {
    h = hedge_nextequiv("defgeo.bgeo", h);
    num_equiv++;
} while (h != 3);
```

### hedge_presrcpoint

```vex
// Get the point before the source point of half-edge 3.
// Useful for computing edge tangents or curvature along a polygon edge loop.
int presrcpt;
presrcpt = hedge_presrcpoint("defgeo.bgeo", 3);

// Compute the direction from pre-source to source
vector pre_pos = point(0, "P", presrcpt);
vector src_pos = point(0, "P", hedge_srcpoint("defgeo.bgeo", 3));
vector edge_dir = normalize(src_pos - pre_pos);
```

### hedge_presrcvertex

```vex
// Get the vertex before the source vertex of half-edge 3.
// Vertex-level equivalent of hedge_presrcpoint; useful for UV seam detection.
int presrcvtx;
presrcvtx = hedge_presrcvertex("defgeo.bgeo", 3);
```

### hedge_prev

```vex
// Get the previous half-edge in the face loop.
// Combined with hedge_next, allows bidirectional face traversal.
int prevhedge;
prevhedge = hedge_prev("defgeo.bgeo", 3);

// Reverse-walk a face loop to collect points in reverse winding order
int start = primhedge(0, @primnum);
int h     = start;
int rev_pts[];
do {
    append(rev_pts, hedge_srcpoint(0, h));
    h = hedge_prev(0, h);
} while (h != start);
```

### hedge_primary

```vex
// Retrieve the canonical (primary) half-edge equivalent to half-edge 3.
// Primary half-edge is the authoritative representative of an undirected edge.
int primhedge_result;
primhedge_result = hedge_primary("defgeo.bgeo", 3);

// Use to deduplicate: only process each undirected edge once
if (hedge_isprimary(0, @hedge)) {
    // process this edge exactly once
    int pt0 = hedge_srcpoint(0, @hedge);
    int pt1 = hedge_dstpoint(0, @hedge);
}
```

### hedge_srcpoint

```vex
// Get the source point of half-edge 3.
// Together with hedge_dstpoint, gives both endpoints of a directed edge.
int srcpt;
srcpt = hedge_srcpoint("defgeo.bgeo", 3);

// Compute edge midpoint
int dstpt   = hedge_dstpoint("defgeo.bgeo", 3);
vector pmid = (point(0, "P", srcpt) + point(0, "P", dstpt)) * 0.5;
```

### neighbours

```vex
// Collect all neighbour point indices for a given point using neighbourcount + neighbour
int[] neighbours_of(int opinput, ptnum) {
    int i, n;
    int result[];
    n = neighbourcount(opinput, ptnum);
    resize(result, n);
    for (i = 0; i < n; i++)
        result[i] = neighbour(opinput, ptnum, i);
    return result;
}
```

### osd_limitsurface

```vex
// Sample 100 random points per OSD patch on the limit surface and emit new points
int npatches = osd_patchcount(0);
for (int patch = 0; patch < npatches; patch++) {
    for (int v = 0; v < 100; v++) {
        vector P;
        if (osd_limitsurface(0, "P", patch, nrandom(), nrandom(), P)) {
            int ptid = addpoint(geoself(), P);
        }
    }
}
```

### pointedge

```vex
// Test whether an edge exists between points 23 and 25
int edge_count = 0;
int h0 = pointedge("defgeo.bgeo", 23, 25);
if (h0 != -1) {
    // Edge exists between the two points
    edge_count++;
}
```

### pointhedge

```vex
// Count the number of edges (not half-edges) incident to point 23
int edge_count = 0;
int hout = pointhedge("defgeo.bgeo", 23);
while (hout != -1) {
    if (hedge_isprimary("defgeo.bgeo", hout))
        edge_count++;
    int hin = hedge_prev("defgeo.bgeo", hout);
    if (hedge_isprimary("defgeo.bgeo", hin))
        edge_count++;
    hout = pointhedgenext("defgeo.bgeo", hout);
}
```

### pointhedgenext

```vex
// Walk all half-edges around point 23; count primary edges only
int edge_count = 0;
int hout = pointhedge("defgeo.bgeo", 23);
while (hout != -1) {
    if (hedge_isprimary("defgeo.bgeo", hout))
        edge_count++;
    int hin = hedge_prev("defgeo.bgeo", hout);
    if (hedge_isprimary("defgeo.bgeo", hin))
        edge_count++;
    hout = pointhedgenext("defgeo.bgeo", hout);
}
```

### polyneighbours

```vex
// Return all primitives sharing an edge with the given primitive
int[] polyneighbours(const string opname; const int primnum) {
    int result[] = {};
    int start = primhedge(opname, primnum);
    for (int hedge = start; hedge != -1; ) {
        for (int nh = hedge_nextequiv(opname, hedge);
             nh != hedge;
             nh = hedge_nextequiv(opname, nh))
        {
            int prim = hedge_prim(opname, nh);
            if (prim != -1 && prim != primnum)
                append(result, prim);
        }
        hedge = hedge_next(opname, hedge);
        if (hedge == start) break;
    }
    return result;
}
```

### primvertexcount

```vex
// Get the vertex count of primitive 3.
// Polygons: vertex count == side count (triangle=3, quad=4, etc.).
int nvtx;
nvtx = primvertexcount("defgeo.bgeo", 3);

// Flag non-triangular faces for a cleanup pass
if (primvertexcount(0, @primnum) != 3) {
    i@non_tri = 1;
}
```

### usd_addrelationshiptarget

```vex
// Add the sphere prim as a target of cube's named relationship.
// Does not replace existing targets — appends to the target list.
usd_addrelationshiptarget(0, "/geo/cube", "relationship_name", "/geo/sphere");

// Add multiple targets in sequence
usd_addrelationshiptarget(0, "/geo/cube", "lights", "/lights/key");
usd_addrelationshiptarget(0, "/geo/cube", "lights", "/lights/fill");
usd_addrelationshiptarget(0, "/geo/cube", "lights", "/lights/rim");
```

### usd_blockprimvar

```vex
// Block (opinion-block) a primvar so it is invisible to descendants.
// Useful to prevent inherited primvars from leaking into child prims.
usd_blockprimvar(0, "/geo/sphere", "primvar_name");

// Block a list of primvars on the same prim
string[] vars_to_block = {"displayColor", "displayOpacity", "normals"};
foreach (string v; vars_to_block) {
    usd_blockprimvar(0, "/geo/sphere", v);
}
```

### usd_isrelationship

```vex
// Returns 1 if "some_relationship" exists on /geo/cube, else 0.
// Guards against querying relationship targets on non-existent relationships.
int is_valid_relationship = usd_isrelationship(0, "/geo/cube", "some_relationship");

if (is_valid_relationship) {
    string[] targets = usd_relationshiptargets(0, "/geo/cube", "some_relationship");
    // process targets array
}
```

### usd_setrelationshiptargets

```vex
// Replace the target list of "new_relation" on /geo/cube with two sphere prims.
// Unlike usd_addrelationshiptarget, this overwrites the entire target list.
usd_setrelationshiptargets(
    0,
    "/geo/cube",
    "new_relation",
    array("/geo/sphere6", "/geo/sphere7")
);

// Clear a relationship by setting an empty target array
usd_setrelationshiptargets(0, "/geo/cube", "new_relation", {});
```

### usd_settransformreset

```vex
// Make /geo/cone ignore its parent's transform (identity world xform).
// Equivalent to "Reset Transform" in the USD spec (xformOpOrder = []).
usd_settransformreset(0, "/geo/cone", 1);

// Re-enable inherited transforms by clearing the reset flag
usd_settransformreset(0, "/geo/cone", 0);
```

### vertexcurveparam

```vex
// Map a ramp parameter along a curve using the arc-length parameterisation
// Note: @vtxnum also works when iterating over points
float u = vertexcurveparam(0, @vtxnum);
// Convert from unit space to unit-length space so spacing is arc-length uniform
u = primuvconvert(0, u, @primnum, PRIMUV_UNIT_TO_UNITLEN);
@width = chramp("width", u);
```

### vertexhedge

```vex
// Get the half-edge that originates from vertex 2.
// From the half-edge you can then traverse the face loop.
int vtxhedge;
vtxhedge = vertexhedge("defgeo.bgeo", 2);

// Walk from vertex to its outgoing half-edge and get the destination point
if (hedge_isvalid(0, vtxhedge)) {
    int dstpt = hedge_dstpoint(0, vtxhedge);
    // dstpt is the next point in the primitive's winding order
}
```

### vertexprev

```vex
// Get the previous vertex in the primitive loop before vertex 3.
// Use to walk the vertex ring backward around a polygon.
int vtx;
vtx = vertexprev("defgeo.bgeo", 3);

// Walk backward to collect all vertices of the primitive
int prim_of_vtx = vertexprim(0, @vtxnum);
int cur_vtx     = @vtxnum;
int vtx_ring[];
do {
    append(vtx_ring, cur_vtx);
    cur_vtx = vertexprev(0, cur_vtx);
} while (cur_vtx != @vtxnum);
```

### vertexprimindex

```vex
// Decompose linear vertex 6 into its owning primitive and local vertex offset.
// vertexprim gives the primitive; vertexprimindex gives the 0-based offset within it.
int prim, vtx;
prim = vertexprim("defgeo.bgeo", 6);
vtx  = vertexprimindex("defgeo.bgeo", 6);

// Reconstruct the linear vertex from primitive + local index (inverse operation)
int linear_vtx = primvertex(0, prim, vtx);
```

## Advanced (5 examples)

### Remove Geometry

```vex
// Delete the current point; use in a point wrangle.
// Downstream geometry rebuilds connectivity automatically.
removepoint(0, @ptnum);

// Conditional removal: keep only points above Y=0
if (@P.y < 0) {
    removepoint(0, @ptnum);
}

// Remove a primitive while keeping its points
removeprim(0, @primnum, 0);

// Remove a primitive and delete its orphaned points
removeprim(0, @primnum, 1);
```

### Orient basics

```vex
// Identity quaternion: no rotation applied to instanced copies.
// {x, y, z, w} format; w=1 is the identity.
@orient = {0, 0, 0, 1};

// Build orient from the point normal + a stable up vector
vector up_axis = {0, 1, 0};
// Fallback if normal is parallel to up
if (abs(dot(@N, up_axis)) > 0.999)
    up_axis = {1, 0, 0};
vector side = normalize(cross(@N, up_axis));
vector up   = normalize(cross(side, @N));
matrix3 basis = set(side, up, @N);
@orient = quaternion(basis);
```

### Quaternion Interpolation with Slerp

```vex
// Smooth slerp between identity and a PI/2 rotation around @up
vector4 a = {0, 0, 0, 1};
vector4 b = quaternion(0, v@up, ch('PI/2'));
float blend = chramp('blendramp', @Time % 1);
@orient = slerp(a, b, blend);

// Alternative: quaternion from explicit components
vector4 a2 = {0, 0, 0, 1};
vector4 b2 = quaternion(1, 0, 1, 0) * PI / 2;
float blend2 = chramp('blendwramp', @Time % 1);
@orient = slerp(a2, b2, blend2);
```

### For loops with iteration-based spacing

```vex
// Space points evenly along normal using loop index as multiplier
for (int i = 0; i < 10; i++) {
    addpoint(0, @P + (i * @N * 4));
}

// Fractional step size for denser sampling
for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * (i * 0.1));
}
```

### Removing Points and Primitives

```vex
// Remove a point by its point number
removepoint(0, @ptnum);

// Remove a primitive and keep its points in the geometry
removeprim(0, @primnum, 1);
```

## Expert (1 examples)

### Solver sop and wrangles for simulation

```vex
// Game-of-Life style cellular automaton inside a Solver SOP
// Run over primitives; each cell checks its four neighbours
int left   = prim(0, 'Cd', @primnum - 1);
int right  = prim(0, 'Cd', @primnum + 1);
int top    = prim(0, 'Cd', @primnum + 30);
int bottom = prim(0, 'Cd', @primnum - 30);

int total = left + right + top + bottom;

if (total == 1 && @Cd == 1) {
    // Lone live cell survives
    @Cd = 1;
} else if (total == 3) {
    // Dead cell with 3 live neighbours is born
    @Cd = 1;
} else {
    // All other cells die
    @Cd = 0;
}
```
