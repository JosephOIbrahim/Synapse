# Joy of VEX: Geometry Operations

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
@orient = {0,0,0,1};         // Identity quaternion -- locks copied geo to fixed orientation
@N *= chv('scale_vec');       // Multiply normals by vector channel (non-uniform scale/flip)
@N = cross(@N, {1, -1, 0});  // Cross product normal reorientation (twirl/comb effect)
```

## Geometry Operations

### Distance-Based Position Manipulation [[Ep2](https://www.youtube.com/watch?v=OyjB5ZifIuU)]
```vex
// Cone shape: use distance from origin as Y height
float d = length(@P);
@P.y = d * 0.2;           // scale factor controls cone slope

// Add offset to shift the surface down in Y
@P.y = d * 0.2 - 10;

// Clamp height to flatten the cone tip
@P.y = clamp(d, 0, 7);   // flat top at Y=7

// Drive with a spare parameter
d *= ch("scale");
@P.y = d;
```

### Distance-Based Displacement from Nearest Point [[Ep3, 49:22](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2962s)]
```vex
// Find nearest point on second input, transfer color, displace Y by distance
int pt = nearpoint(1, @P);
@Cd = point(1, "Cd", pt);        // transfer color from nearest point
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
@P.y = -d;                       // negative = depress toward reference geometry

// Variant: positive Y displacement (height field from nearest point)
int pt2 = nearpoint(1, @P);
vector pos2 = point(1, "P", pt2);
float d2 = distance(@P, pos2);
@P.y = d2;
```

### Cross Product Normal Reorientation [[Ep4, 23:04](https://www.youtube.com/watch?v=66WGmbykQhI&t=1384s)]
```vex
// Single cross product -- normals rotate around the axis vector
@N = cross(@N, {1, -1, 0});

// Two-step gravity comb -- cross N with up to get perp, cross again for downward
vector tmp = cross(@N, {0, 1, 0});
@N = cross(@N, tmp);              // points normals downward (gravity comb)

// Swap operand order to reverse the comb direction
tmp = cross(@N, {0, 1, 0});
@N = cross(tmp, @N);

// Repeated cross products for grooming default orientation
tmp = cross(@N, {0,1,0});
tmp = cross(@N, tmp);
tmp = cross(@N, tmp);
tmp = cross(@N, tmp);
@N = cross(@N, tmp);
```

### Vector Subtraction for Direction Vectors [[Ep4, 34:24](https://www.youtube.com/watch?v=66WGmbykQhI&t=2064s)]
```vex
// Direction from point 0 to point 1 (both from explicit inputs)
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);
@N = b - a;                  // b-a points FROM a TOWARD b

// Per-point variant: current point toward a fixed reference point
vector origin = point(1, "P", 0);
@N = origin - @P;            // each point's normal aims at the reference

// Reverse: vectors radiating away from reference
@v = @P - origin;

// Alternative: explicit velocity attribute
vector p = v@P;
vector ref = point(1, "P", 0);
v@l = ref - p;               // l attribute stores the to-target vector
```

### Multiplying Normals by Vector [[Ep4, 45:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=2716s)]
```vex
// Non-uniform stretch/flip normals via vector channel
// x>1 stretches, z<0 flips normals that point in -Z, causing them to invert
@N *= chv('scale_vec');
```

### Relative Bounding Box Positioning [[Ep4, 48:10](https://www.youtube.com/watch?v=66WGmbykQhI&t=2890s)]
```vex
// relpointbbox returns 0-1 position of each point within the bounding box
@Cd = relpointbbox(0, @P);   // use all three axes as RGB color directly

// Access individual axis components
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;                // color driven by vertical position only

// Normalize positions first to get bounding box of a sphere-like distribution
@P = normalize(@P);
@Cd = relpointbbox(0, @P);
```

### Removing Geometry Conditionally [[Ep5, 132:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7954s)]
```vex
// Remove a single point
removepoint(0, @ptnum);

// Remove primitive, delete its points (arg3=1)
removeprim(0, @primnum, 1);

// Remove primitive, keep its points (arg3=0)
removeprim(0, @primnum, 0);

// Random deletion using a threshold channel
if (rand(@ptnum) < ch('cutoff')) {
    removepoint(0, @ptnum);
}

// Seeded randomness -- different seed = different pattern
if (rand(@ptnum * ch('seed')) < ch('cutoff')) {
    removepoint(0, @ptnum);
}

// Random prim deletion (run in Prim Wrangle)
if (rand(@primnum) < ch('cutoff')) {
    removeprim(0, @primnum, 1);   // also deletes points
}

// Seeded prim deletion
if (rand(@ptnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
```

### Setting Up Vector for Copy to Points [[Ep6, 44:48](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2688s)]
```vex
// @up controls the roll/twist of instances in Copy to Points
v@up = {0,0,1};   // local Y of copies aligns with world Z

// Animated @up -- rotates around Y using sin/cos of time
// combined with @N this gives full rotational control
v@up = set(sin(@Time), 0, cos(@Time));
```

### Resetting Primitive Transform Intrinsic [[Ep7, 131:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7888s)]
```vex
// Reset a packed prim's transform to identity (rotation/scale only)
// @P must be zeroed separately to fully reset position
matrix3 m = ident();
setprimintrinsic(0, "transform", @primnum, m);
@P = {0,0,0};
```

### Building a Transform Matrix from Orient and Scale [[Ep7, 133:36](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8016s)]
```vex
// Animate rotation around Y axis, combine with non-uniform scale
// scale() is IN-PLACE -- modifies matrix directly, does NOT return a value
@orient = quaternion({0,1,0} * @Time);
@scale  = {1, 0.3, 2};

matrix3 m = ident();
scale(m, @scale);            // in-place: m is now scaled identity
m *= qconvert(@orient);      // multiply in the rotation

setprimintrinsic(0, "transform", @primnum, m);

// Variant using local variables (same pattern, avoids touching attributes mid-build)
vector qorient = quaternion({0,1,0} * @Time);
vector vscale   = {1, 0.5, 2};

matrix3 m2 = ident();
scale(m2, vscale);
m2 *= qconvert(qorient);

setprimintrinsic(0, "transform", @ptnum, m2);
```

### Reading Packed Primitive Transform Intrinsics [[Ep7, 139:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8344s)]
```vex
// Read full 4x4 transform (translation + rotation + scale)
matrix pft = primintrinsic(0, "packedfullTransform", @ptnum);
4@xform = pft;               // store as matrix4 attribute for inspection
                             // bottom row of matrix = translation (human-readable)
                             // upper-left 3x3 = rotation + scale

// Extract just rotation+scale by casting to matrix3 (drops translation column)
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;

// Cast a 4x4 down to matrix3 from another variable
matrix3 m = matrix3(pft);
```

### Setting Primitive "closed" Intrinsic [[Ep7, 146:42](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8802s)]
```vex
// Toggle primitives between open polyline (0) and closed polygon (1)
// rand() * 2 cast to int gives 0 or 1

// Animated: use @Frame in seed so state changes over time
int openclose = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose);

// Multiply variant (same distribution, different seed pattern)
int openclose2 = int(rand(@primnum * @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose2);

// Combine packed transform read with closed-state animation
matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;

int open_load = int(rand(@ptnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, open_load);
```

### Setting Orient to Identity Quaternion [[Ep7, 30:36](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=1836s)]
```vex
// Identity quaternion: no rotation, overrides @N-driven copy orientation
@orient = {0,0,0,1};

// Static orient from channel references
float angle = ch('angle');
vector axis  = chv('axis');
@orient = quaternion(angle, axis);

// Animated orient using @Time as the rotation angle
float animAngle = @Time;
@orient = quaternion(animAngle, chv('axis'));
```

### Animated Per-Point Quaternion Rotation [[Ep7, 37:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2250s)]
```vex
// Each point gets its own offset angle + shared time-driven speed
float angle;
vector axis;

angle  = ch('angle');
angle += @ptnum * ch('offset');   // offset staggers rotation across points
angle += @Time  * ch('speed');    // speed scales the animation rate

axis = chv('axis');

@orient = quaternion(angle, axis);
```

### Instance Matrix to Quaternion Orientation [[Ep7, 89:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5390s)]
```vex
// Point copies toward nearest point on target geometry (input 1)
@orient = {0,0,0,1};
@pscale = 1;

int target   = nearpoint(1, @P);
vector base  = point(1, "P", target);

matrix m = ident();
// instance(matrix, N, up, pscale, v, rest) builds an instance transform
m = instance(m, base - @P, {0,1,0}, 1, {0,0,1}, 0);

@orient = quaternion(m);   // convert the matrix to a quaternion for @orient
```

### Orient Copied Geometry Outward from Sphere [[Ep7, 96:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5774s)]
```vex
// Normalize position to get outward normal; @up prevents twist
@N  = normalize(@P);
@up = {0,1,0};

// Build a full quaternion from the normal+up transform for clean orientation
@orient = quaternion(maketransform(@N, @up));
// maketransform(@N, @up) returns a matrix; quaternion() converts it
// result: instance Z-axis points away from sphere center
```

### Primitive UV Attribute Sampling [[Ep8, 25:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1520s)]
```vex
// Sample P and N from geometry input 1 at interactive UV position
vector uv = chv('uv');

// primav(geohandle, attrib, primnum, uv) -- bilinear attribute sample
@P = primav(1, "P", 0, uv);
@N = primav(1, "N", 0, uv);

// primmuv for per-axis UV sampling (tangent/derivative setup)
vector gx = primmuv(1, "P", 0, uv.x);
vector gy = primmuv(1, "P", 0, uv.y);
```

## Common Mistakes

```vex
// WRONG: scale() is in-place, do NOT assign its return value
matrix3 m = ident();
// m = scale(m, myscale);   // this is wrong -- scale() returns void

// CORRECT: call scale() without assignment
scale(m, myscale);           // m is modified directly

// WRONG: using @primnum inside removepoint() (point context)
removepoint(0, @primnum);    // @primnum is undefined in a point wrangle

// CORRECT: use @ptnum in point context, @primnum in prim context
removepoint(0, @ptnum);

// WRONG: removeprim() third arg meaning
removeprim(0, @primnum, 1);  // 1 = DELETE the points (not keep)
removeprim(0, @primnum, 0);  // 0 = KEEP the points

// WRONG: reading packedfullTransform with typo in intrinsic name
matrix bad = primintrinsic(0, "packedfulltramsform", @ptnum);  // typo -- returns garbage

// CORRECT: exact string matters
matrix good = primintrinsic(0, "packedfullTransform", @ptnum);
```

## See Also
- **VEX Common Patterns** (`vex_patterns.md`) -- geometry manipulation patterns
