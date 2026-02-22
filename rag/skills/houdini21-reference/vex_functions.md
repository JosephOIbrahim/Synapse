# VEX Functions Reference

## Triggers

vex functions, vex reference, attribute access, @ syntax, geometry functions, spatial queries,
pcfind, pcopen, intersect, xyzdist, nearpoint, noise, curlnoise, math functions, vector ops,
lerp, fit, clamp, smooth, matrix, quaternion, dihedral, lookat, string functions, sprintf,
channel functions, ch(), chramp, addpoint, addprim, removepoint, removeprim, setpointattrib,
point(), prim(), detail(), npoints, nprims, rand, random, printf, wrangle, attribwrangle,
point wrangle, scatter, deformer, orient, copy to points, color ramp, noise deformation,
point cloud, pcfilter, ray intersect, distance to surface, group expression

## Context

VEX (Vector Expression Language) is Houdini's compiled shader/geometry language. Every code
block below is valid in an Attribute Wrangle (Run Over: Points unless noted). `0` refers to
the first input geometry handle. `geoself()` or `0` for write operations.

---

## Attribute Access — @ Syntax with Type Prefixes

```vex
// ── Type-prefixed attribute declaration (creates attr if missing) ──────────
f@density   = 1.0;              // float
i@id        = 42;               // integer
v@velocity  = {0, 1, 0};        // vector (3 floats)
u@color4    = {1, 0, 0, 1};     // vector4 (RGBA)
p@orient    = {0, 0, 0, 1};     // vector4 interpreted as quaternion
s@name      = "piece1";         // string
2@xform2    = ident();          // matrix2 (2×2)
3@xform3    = ident();          // matrix3 (3×3)
4@xform4    = ident();          // matrix4 (4×4)
i[]@neighbors = {};             // integer array

// ── Built-in geometry attributes (always available, no prefix needed) ──────
@P.y       += 1.0;              // point position (vector)
@N          = normalize(@P);    // surface normal (vector)
@Cd         = {1, 0, 0};        // diffuse color (vector) -- red
@v          = {0, 0, 0};        // velocity (vector)
@pscale     = 0.1;              // uniform point scale (float)
@width      = 0.05;             // curve/particle width (float)
@Alpha      = 1.0;              // opacity (float, 0=transparent)
@uv         = set(@P.x, @P.z, 0); // UV coordinates (vector, .z unused)
@rest       = @P;               // rest position for noise anchoring (vector)
@up         = {0, 1, 0};        // up vector for orient (vector)
@orient;                        // orientation quaternion (vector4)
@age;                           // particle age in seconds (float)
@life;                          // particle life expectancy in seconds (float)

// ── Context variables (read-only, no type prefix) ──────────────────────────
int   pt   = @ptnum;            // current point index (0-based)
int   npt  = @numpt;            // total point count on geometry
int   pr   = @primnum;          // current primitive index
int   npr  = @numprim;          // total primitive count
int   vx   = @vtxnum;           // current vertex index (linear)
float fr   = @Frame;            // current frame number (1.0, 1.041667…)
float t    = @Time;             // current time in seconds
float dt   = @TimeInc;          // time per frame (1.0 / FPS)
string ip1 = @OpInput1;         // SOP path of first input node
```

---

## Geometry Read Functions

```vex
// ── Read attributes from any input by element number ──────────────────────
vector pos    = point(0, "P",  3);          // point attr from input 0, ptnum 3
float  cd_r   = point(0, "Cd", @ptnum).x;   // red channel of neighbor's color
int    cls    = prim(0, "class", @primnum);  // prim attr
vector vtxN   = vertex(0, "N", @vtxnum);    // vertex attr by linear index
float  globalScale = detail(0, "scale");    // detail (single value for whole geo)

// ── Topology queries ───────────────────────────────────────────────────────
int  np  = npoints(0);                      // total points on input 0
int  npr = nprims(0);                       // total prims on input 0
int  nvx = nvertices(0);                    // total vertices on input 0
int  pvx = primvertexcount(0, @primnum);    // vertex count of this prim

int  pts[] = primpoints(0, @primnum);       // point nums belonging to this prim
int  prs[] = pointprims(0, @ptnum);         // prim nums touching this point
int  vtxs[]= pointvertices(0, @ptnum);      // vertex nums for this point

// vertex → point and vertex → prim lookups
int  ptOfVtx = vertexpoint(0, @vtxnum);     // which point owns this vertex
int  prOfVtx = vertexprim(0, @vtxnum);      // which prim owns this vertex

// prim intrinsics (area, centroid, bounds, etc.)
float area    = primintrinsic(0, "measuredarea",      @primnum);
float perim   = primintrinsic(0, "measuredperimeter", @primnum);
vector ctr    = primintrinsic(0, "measuredcentroid",  @primnum);
```

---

## Geometry Write Functions

```vex
// ── Write attributes to geoself (handle = 0) ──────────────────────────────
setpointattrib(0, "Cd",    @ptnum,   {1, 0, 0}, "set");   // set red
setpointattrib(0, "score", @ptnum,   42,         "add");   // increment integer
setprimattrib( 0, "class", @primnum, 2,          "set");
setvertexattrib(0, "uv",   @vtxnum,  {0.5,0.5,0}, "set");
setdetailattrib(0, "frame_count", @Frame, "set");

// ── Create geometry (use in detail wrangle, Run Over: Detail) ─────────────
int pt0 = addpoint(0, {0, 0, 0});           // new point at origin → ptnum
int pt1 = addpoint(0, {1, 0, 0});
int pr  = addprim(0, "poly");               // new empty polygon → primnum
addvertex(0, pr, pt0);                      // attach pt0 as first vertex
addvertex(0, pr, pt1);                      // attach pt1 as second vertex

// open polygon (polyline), closed curve, NURBS
int lin = addprim(0, "polyline");
int bez = addprim(0, "bezier");
int sph = addprim(0, "sphere");             // packed sphere prim

// ── Delete geometry ────────────────────────────────────────────────────────
removepoint(0, @ptnum);                     // delete current point
removepoint(0, @ptnum, 1);                  // delete and remove from all prims
removeprim(0, @primnum, 0);                 // delete prim, keep points
removeprim(0, @primnum, 1);                 // delete prim AND its points
removevertex(0, @vtxnum);                   // delete one vertex from its prim

// ── Groups ────────────────────────────────────────────────────────────────
setpointgroup(0, "top_pts", @ptnum,   1);   // add to group
setprimgroup( 0, "big_prs", @primnum, 0);   // remove from group
int in_grp = inpointgroup(0, "top_pts", @ptnum);   // 1 if in group
```

---

## Spatial Queries

```vex
// ── Nearest single point ───────────────────────────────────────────────────
int   near = nearpoint(0, @P);              // nearest ptnum (any distance)
int   near2= nearpoint(0, @P, 2.0);         // nearest within radius 2.0
vector nearP = point(0, "P", near);

// ── Multiple nearest points (array return) ────────────────────────────────
int near4[] = nearpoints(0, @P, 5.0, 4);    // up to 4 pts within r=5.0
foreach(int nb; near4) {
    vector nbP = point(0, "P", nb);
    @Cd += point(0, "Cd", nb);             // accumulate neighbor colors
}
@Cd /= len(near4) + 1;                     // average (include self)

// ── Point cloud — fast pre-sorted search ──────────────────────────────────
int handle = pcopen(0, "P", @P, ch("radius"), chi("maxpts"));
vector avg  = {0, 0, 0};
int    cnt  = 0;
while(pciterate(handle)) {
    vector nbP;
    pcimport(handle, "P", nbP);            // import any attribute from cloud
    avg += nbP;
    cnt++;
}
pcclose(handle);
if(cnt > 0) avg /= cnt;

// pcfind: one-shot array of ptnums (simpler than pcopen for simple lookups)
int found[] = pcfind(0, "P", @P, ch("radius"), chi("maxpts"));
// pcfilter: shorthand smooth — average attribute over cloud (no explicit loop)
int smHandle = pcopen(0, "P", @P, 1.5, 8);
@P = pcfilter(smHandle, "P");              // position-smooth in one call
pcclose(smHandle);

// ── Ray–geometry intersection ─────────────────────────────────────────────
vector  hitP, hitUV;
int     hitPrim;
float   hitDist;
// intersect returns distance (-1 = miss), fills pos/uvs/primnum by reference
hitDist = intersect(1, @P, {0,-1,0}, hitP, hitUV);   // shoot ray downward into input 1
if(hitDist >= 0) {
    @Cd = {0, 1, 0};                       // hit → green
    @P.y = hitP.y;                         // snap point to surface
}

// ── Closest surface point (distance + UV) ────────────────────────────────
int   nearPrim;
vector nearUV;
float dist = xyzdist(1, @P, nearPrim, nearUV);        // distance to nearest prim on input 1
vector surfP = primuv(1, "P", nearPrim, nearUV);       // evaluate position at that UV
vector surfN = primuv(1, "N", nearPrim, nearUV);       // normal at same location
```

---

## Math — Vector Operations

```vex
// ── Length and direction ───────────────────────────────────────────────────
float  mag  = length(@v);               // vector magnitude (uses sqrt)
float  mag2 = length2(@v);              // squared magnitude (no sqrt, faster for comparisons)
vector dir  = normalize(@v);            // unit-length direction

// ── Products ───────────────────────────────────────────────────────────────
float  align = dot(@N, {0,1,0});        // 1=facing up, 0=perpendicular, -1=facing down
vector perp  = cross(@N, {0,1,0});      // vector perpendicular to both (right-hand rule)

// ── Distance ──────────────────────────────────────────────────────────────
float  dist  = distance(@P, {0,0,0});   // Euclidean distance to origin
float  dist2 = distance2(@P, {0,0,0});  // squared distance (no sqrt)

// ── Reflection and refraction ─────────────────────────────────────────────
vector R = reflect(normalize(@v), @N);  // mirror velocity off surface normal
vector T = refract(normalize(@v), @N, 1.5); // refract (IOR=1.5, glass)

// ── Component access ──────────────────────────────────────────────────────
float  vy  = @v.y;                      // swizzle by name
float  vz  = getcomp(@v, 2);            // by index (0=x, 1=y, 2=z)
vector swz = @v.zyx;                    // swizzle reorder
vector v2  = set(@P.x, 0, @P.z);        // build vector from scalars
```

---

## Math — Interpolation and Remapping

```vex
// ── Linear interpolation ──────────────────────────────────────────────────
float  t     = @ptnum / (float)(@numpt - 1);   // 0..1 along point sequence
float  val   = lerp(0.0, 10.0, t);             // scalar lerp
vector col   = lerp({1,0,0}, {0,0,1}, t);      // vector lerp (red → blue)

// ── Spherical interpolation ───────────────────────────────────────────────
vector4 qa = quaternion(0,          {0,1,0});   // identity rotation
vector4 qb = quaternion(M_PI * 0.5, {0,1,0});  // 90° about Y
vector4 qr = slerp(qa, qb, t);                 // smooth quaternion blend
@orient = qr;

// ── Range remapping ───────────────────────────────────────────────────────
float h01 = fit(@P.y, -5.0, 5.0, 0.0, 1.0);   // remap height -5..5 → 0..1 (no clamp)
float hc  = efit(@P.y, -5.0, 5.0, 0.0, 1.0);  // same but clamped to output range
float h2  = fit01(h01, -2.0, 2.0);             // shorthand: 0-1 input remapped to -2..2

// ── Clamping and stepping ─────────────────────────────────────────────────
float  c  = clamp(val, 0.0, 1.0);              // hard clamp
float  s  = smooth(0.0, 1.0, val);             // hermite smooth-step (S-curve)
float  ss = smoothstep(0.0, 1.0, val);         // GLSL-style smooth-step
float  sss= smootherstep(0.0, 1.0, val);       // quintic smooth-step (C2 continuous)

// ── Ramp parameters (from wrangle UI) ────────────────────────────────────
float  rval = chramp("falloff",  h01);          // float ramp at position h01
vector rcol = chramp("colormap", h01);          // color ramp → vector

// ── Basic arithmetic ──────────────────────────────────────────────────────
float  a2   = abs(-3.5);            // 3.5
float  fl   = floor(3.7);           // 3.0
float  cl   = ceil(3.2);            // 4.0
float  rn   = round(3.5);           // 4.0
float  sg   = sign(-7.0);           // -1.0
float  mn   = min(a2, fl);
float  mx   = max(a2, fl);
float  pw   = pow(2.0, 10.0);       // 1024
float  sq   = sqrt(16.0);           // 4.0
float  lg   = log(M_E);             // 1.0 (natural log)
float  lg10 = log10(1000.0);        // 3.0
float  ex   = exp(1.0);             // e ≈ 2.71828
float  frc  = frac(3.7);            // 0.7 (fractional part)
float  md   = fmod(7.0, 3.0);       // 1.0 (modulo, float)
int    imd  = 7 % 3;                // 1 (modulo, integer)

// ── Trigonometry (radians) ────────────────────────────────────────────────
float  ang  = radians(45.0);        // 0.7854
float  deg  = degrees(M_PI);        // 180.0
float  s_   = sin(ang);
float  c_   = cos(ang);
float  t_   = tan(ang);
float  as_  = asin(0.5);            // π/6
float  ac_  = acos(0.5);            // π/3
float  at_  = atan(1.0);            // π/4
float  at2  = atan2(@P.z, @P.x);    // full-circle angle from X axis
```

---

## Noise Functions

```vex
// ── Perlin noise (0..1 output, smooth) ────────────────────────────────────
float  n1  = noise(@P);                             // position-based, 0..1
float  n2  = noise(@P * 3.0);                       // 3× frequency
float  n3  = noise(@P + @Time * 0.5);               // animated (no sliding)
vector vn  = noise(@P);                             // vector noise (3 channels)

// ── Signed Perlin (-1..1) ─────────────────────────────────────────────────
float  sn  = snoise(@P);                            // -1..1

// ── Fractal Brownian Motion (layered octaves) ─────────────────────────────
float fbm  = 0;
float amp  = 0.5;
vector pos = @P;
for(int oct = 0; oct < 5; oct++) {
    fbm += snoise(pos) * amp;
    pos *= 2.1;                                     // frequency doubles each octave
    amp *= 0.5;                                     // amplitude halves (persistence)
}
@P.y += fbm * ch("height");

// ── Curl noise (divergence-free, mass-conserving) ─────────────────────────
// Ideal for smoke advection, flow fields — does not pile up or drain
vector curl = curlnoise(@P * ch("freq") + @Time * 0.2);
@v += curl * ch("strength");                        // add turbulence to velocity

// ── Alligator noise (cellular, sharp creases) ─────────────────────────────
float  an  = anoise(@P * 2.0);                      // 0..1, cellular look

// ── Voronoi noise (cell distance + cell ID) ───────────────────────────────
vector cellP;
float  F1, F2;
int    cellID;
wnoise(@P, 0, F1, F2, cellP, cellID);              // F1=nearest-cell-dist, F2=second-nearest
float  edge = F2 - F1;                              // Worley edge factor

// ── Flow noise (animated without temporal sliding) ────────────────────────
float  fn  = flownoise(@P, @Time * 0.3);            // 4th arg is flow parameter

// ── Simplex noise (faster, fewer directional artifacts than Perlin) ────────
float  xn  = xnoise(@P);                            // -1..1 range

// ── Classic Houdini noise (original implementation) ───────────────────────
float  on  = onoise(@P);                            // 0..1
```

---

## String Functions

```vex
// ── Formatting and building ───────────────────────────────────────────────
string label = sprintf("piece_%02d", @ptnum);       // zero-padded: "piece_03"
string path  = concat("/obj/", s@name, "/geo");     // concatenate strings
int    slen  = strlen(label);                       // character count

// ── Substring and search ──────────────────────────────────────────────────
string sub   = substr(label, 6, 2);                 // from char 6, length 2 → "03"
int    found = strfind("piece", label);             // index of substring (-1 = not found)

// ── Pattern matching ──────────────────────────────────────────────────────
int    glob_ok = match("piece_*", label);           // glob: 1 if matches
int    re_ok   = re_match("piece_[0-9]+", label);   // regex: 1 if matches
string rep     = re_replace("_[0-9]+", "_X", label);// regex replace

// ── Split and join ────────────────────────────────────────────────────────
string parts[] = split(label, "_");                 // ["piece", "03"]
string joined  = join("_", parts);                  // "piece_03"
string stripped= strip("  hello  ");                // "hello"
string upper   = toupper(label);                    // "PIECE_03"
string lower   = tolower(upper);                    // "piece_03"

// ── Type conversions ──────────────────────────────────────────────────────
string fs = itoa(@ptnum);                           // int → string
int    si = atoi("42");                             // string → int
float  sf = atof("3.14");                           // string → float
```

---

## Channel (Parameter) Functions

```vex
// ── Read from this node's parameters ─────────────────────────────────────
float  scale   = ch("scale");                       // float param
int    iters   = chi("iterations");                 // integer param
vector pivot   = chv("pivot");                      // vector param
string texPath = chs("texture");                    // string param
float  rampVal = chramp("falloff", 0.5);            // ramp param at position 0.5
vector rampCol = chramp("colormap", 0.5);           // color ramp → vector

// ── Read from other nodes (relative path) ────────────────────────────────
float  extVal  = ch("../null1/scale");              // sibling node param
float  absVal  = ch("/obj/mynet/null1/scale");      // absolute path param

// ── Evaluate channel at arbitrary time ───────────────────────────────────
float  prev    = chf("scale", @Time - @TimeInc);    // param value at previous frame
float  next    = chf("scale", @Time + @TimeInc);    // param value at next frame
float  vel     = (next - prev) / (2.0 * @TimeInc);  // first derivative
```

---

## Matrix and Quaternion Functions

```vex
// ── Build transform matrices ──────────────────────────────────────────────
matrix4 ident4 = ident();                           // 4×4 identity
matrix3 ident3 = ident3();                          // 3×3 identity

// maketransform: order (e.g. XFORM_SRT), translate, rotate (radians), scale
matrix4 xf  = maketransform(XFORM_SRT,
                             {0,1,0},               // translate
                             {0, radians(45), 0},   // rotate Y 45°
                             {2, 2, 2});             // uniform scale 2×

// ── Decompose / invert ────────────────────────────────────────────────────
matrix4 inv = invert(xf);                           // inverse transform
matrix4 tp  = transpose(xf);                        // transpose (useful for normals)
float   det = determinant(xf);                      // scalar determinant

// ── Transform points and vectors ─────────────────────────────────────────
vector  tp2 = @P * xf;                              // transform point (homogeneous)
vector  tv  = vtransform(xf, @v);                   // transform direction (no translate)
vector  tn  = ntransform(xf, @N);                   // transform normal (uses inverse-transpose)

// ── Look-at orientation ───────────────────────────────────────────────────
vector  eye  = @P;
vector  tgt  = {0, 0, 0};
vector  upv  = {0, 1, 0};
matrix3 lookR = lookat(eye, tgt, upv);              // rotation matrix facing target

// ── Quaternion construction and use ──────────────────────────────────────
vector4 q1  = quaternion(radians(90), {0,1,0});     // 90° around Y axis
vector4 q2  = quaternion(matrix3(lookR));           // from rotation matrix
vector4 q3  = slerp(q1, q2, 0.5);                  // blend two quaternions

vector  rotV = qrotate(q1, {1,0,0});                // rotate vector by quaternion
matrix3 qMat = qconvert(q1);                        // quaternion → matrix3

// ── dihedral: minimal rotation from one vector to another ────────────────
// Used to align copy-to-points orientation
vector4 dq  = dihedral({0,0,1}, @N);               // rotation from +Z to @N
@orient = dq;                                       // assign to orient for copy-stamp

// ── Euler ↔ quaternion ────────────────────────────────────────────────────
vector  euler = {0, radians(45), 0};                // YXZ Euler in radians
vector4 qe   = eulertoquaternion(euler, XFORM_XYZ);
vector  back = quaterniontoeuler(qe, XFORM_XYZ);
```

---

## Utility and Debug

```vex
// ── Randomness (deterministic, stable across cooks) ───────────────────────
float  r1  = rand(@ptnum);                          // 0..1 float from int seed
float  r2  = rand(@ptnum * 1234567 + 42);           // scrambled seed
vector rv  = rand(@ptnum);                          // random vector (3 channels)
float  r3  = random(@ptnum);                        // alias for rand()

// Stable color per piece (survives topology changes if ID is stable)
v@Cd = set(rand(i@id),
           rand(i@id + 100000),
           rand(i@id + 200000));

// ── Debug output ──────────────────────────────────────────────────────────
printf("pt %d  P=(%g %g %g)\n", @ptnum, @P.x, @P.y, @P.z);   // Houdini console
if(@ptnum == 0) warning("first point processed");              // yellow node warning
if(det < 0.0001) error("degenerate transform on pt %d", @ptnum); // red error, stops cook

// ── Array utilities ───────────────────────────────────────────────────────
int arr[] = {3, 1, 4, 1, 5};
int  n    = len(arr);                               // 5
push(arr, 9);                                       // append
int  last = pop(arr);                               // remove and return last
int  idx  = find(arr, 4);                           // index of value (−1 if absent)
sort(arr);                                          // in-place sort (ascending)
reverse(arr);                                       // in-place reverse

// ── Bitwise (integer only) ────────────────────────────────────────────────
int flags = 0b1010;
int masked= flags & 0b0011;                         // AND
int toggle= flags ^ 0b1111;                         // XOR
int shifted=flags << 2;                             // left shift
```

---

## Common VEX Patterns

```vex
// ── Scatter height filter (delete below threshold) ────────────────────────
// Run Over: Points
if (@P.y < ch("min_height")) removepoint(0, @ptnum);

// ── Orient instances to surface normal (copy-to-points) ───────────────────
// Run Over: Points
v@up    = {0, 1, 0};
p@orient= dihedral({0, 0, 1}, @N);     // align +Z (prim default) to @N

// ── Color by height with ramp ─────────────────────────────────────────────
// Run Over: Points
float t = fit(@P.y, ch("min_y"), ch("max_y"), 0.0, 1.0);
v@Cd    = chramp("color_ramp", clamp(t, 0, 1));

// ── Sine-wave deformer ────────────────────────────────────────────────────
// Run Over: Points
float amp  = ch("amplitude");
float freq = ch("frequency");
float speed= ch("speed");
@P.y += sin(@P.x * freq + @Time * speed) * amp;

// ── Noise-based displacement ──────────────────────────────────────────────
// Run Over: Points
float noiseVal = noise(@P * ch("freq") + @Time * ch("anim_speed"));
@P += @N * noiseVal * ch("amplitude");

// ── Group points by height ────────────────────────────────────────────────
// Run Over: Points
if (@P.y > ch("threshold")) setpointgroup(0, "top", @ptnum, 1);

// ── Point cloud position smooth (Laplacian) ───────────────────────────────
// Run Over: Points
int   handle = pcopen(0, "P", @P, ch("radius"), chi("maxpts"));
@P = pcfilter(handle, "P");
pcclose(handle);

// ── Stable random color per piece (survives reorder) ─────────────────────
// Run Over: Points (requires i@id attribute)
float seed = i@id * 1234567.0;
v@Cd = set(rand(seed), rand(seed + 1), rand(seed + 2));

// ── Velocity from position delta (two-input wrangle) ─────────────────────
// Input 0 = current frame, Input 1 = previous frame geo (Time Shift SOP)
// Run Over: Points
vector prev = point(1, "P", @ptnum);
@v = (@P - prev) / @TimeInc;

// ── Ray-project to surface ────────────────────────────────────────────────
// Input 0 = points to project, Input 1 = target surface
// Run Over: Points
vector hitP, hitUV;
float  d = intersect(1, @P + {0,5,0}, {0,-1,0}, hitP, hitUV);
if (d >= 0) @P.y = hitP.y;

// ── Closest-surface normal transfer ──────────────────────────────────────
// Run Over: Points
int    nearPrim;
vector nearUV;
xyzdist(1, @P, nearPrim, nearUV);
@N = primuv(1, "N", nearPrim, nearUV);

// ── Build a procedural grid (detail wrangle) ──────────────────────────────
// Run Over: Detail
int   cols = chi("cols");
int   rows = chi("rows");
float spacing = ch("spacing");
for(int r = 0; r < rows; r++) {
    for(int c = 0; c < cols; c++) {
        vector pos = set(c * spacing, 0, r * spacing);
        int    pt  = addpoint(0, pos);
        setpointattrib(0, "Cd", pt, set(rand(pt), rand(pt+1), rand(pt+2)), "set");
    }
}

// ── FBM noise macro (reusable via #define or inline) ─────────────────────
// Run Over: Points
float fbm_noise(vector p; int octaves; float persistence; float lacunarity) {
    float result = 0;
    float amp    = 0.5;
    vector pos   = p;
    for(int i = 0; i < octaves; i++) {
        result += snoise(pos) * amp;
        pos    *= lacunarity;
        amp    *= persistence;
    }
    return result;
}
@P.y += fbm_noise(@P, 6, 0.5, 2.0) * ch("height");

// ── Matrix transform: rotate a vector about arbitrary axis ────────────────
// Run Over: Points
float   angle  = ch("angle_deg");
vector  axis   = normalize(chv("axis"));
vector4 q      = quaternion(radians(angle), axis);
@P             = qrotate(q, @P) + chv("pivot_offset");

// ── String attribute from ptnum with padding ──────────────────────────────
// Run Over: Points
s@name = sprintf("geo_%04d", @ptnum);

// ── Wrangle function: signed distance to plane ────────────────────────────
// Run Over: Points
float sdf_plane(vector p; vector origin; vector normal) {
    return dot(p - origin, normalize(normal));
}
float dist = sdf_plane(@P, chv("plane_origin"), chv("plane_normal"));
@Cd = dist > 0 ? {0,1,0} : {1,0,0};   // green above, red below
```

---

## See Also

- **Joy of VEX: Nearpoints and Proximity** (`joy_of_vex_nearpoints.md`) — tutorial examples with nearpoints, pcfind
- **Joy of VEX: Point Clouds** (`joy_of_vex_pcopen.md`) — tutorial examples with pcopen, pcfilter
- **Joy of VEX: Surface Sampling** (`joy_of_vex_surface_sampling.md`) — tutorial examples with primuv, xyzdist
