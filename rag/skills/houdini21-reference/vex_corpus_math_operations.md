# VEX Corpus: Math Operations

> 981 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Beginner (77 examples)
### Basic arithmetic on attributes
```vex
// Addition, subtraction, multiplication on position components
@Cd = @P.x + 3;
@Cd = @P.x - 6;
@Cd = @P.x * 6 * 0.1;
@Cd = (@P.x - 6) * 0.1;

// Component-wise assignment
@Cd.x = @P.x * 3 * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;
```
### Type casting to avoid integer division
```vex
// Wrong: integer division truncates to 0
@Cd = @ptnum / @numpt;

// Correct: cast to float first
@Cd = float(@ptnum) / @numpt;
@Cd = float(@ptnum) / 100;
```
### Channel references
```vex
// ch() reads a float parameter slider
@Cd = float(@ptnum) / ch('scale');

// chv() reads a vector parameter
vector pos = @P * chv('fancyscale');

// chf() is explicit float variant
float s = chf('scale');
```
### Sine function for oscillation
```vex
// Basic sine wave on point number
@Cd = sin(@ptnum);

// With integer division fix and float cast
@Cd = sin(@ptnum / 100);
@Cd = sin(float(@ptnum) / 100);

// Channel-driven frequency
@Cd = sin(float(@ptnum) / ch('scale'));
```
### Variables for code clarity
```vex
float foo = float(@ptnum) / ch('scale');
@Cd = sin(foo);

float foo = @P.x / ch('scale');
@Cd = sin(foo);
```
### Point rotation with sin and cos
```vex
// Animate a single point in a circle
@P.x = sin(@Time);
@P.y = cos(@Time);
```
### Normalizing vectors
```vex
vector axis = p0 - p1;
axis = normalize(axis);
```
### Arrays
```vex
// Basic array declaration
int myarray[] = {1, 2, 3, 4};
int foo = myarray[2];

// Float and vector arrays with attribute syntax
float myFloatArray[] = {1, 2, 3, 4.5};
vector myVectorArray[] = {{1,2,3}, {4,5,6}, {7,8,9}};

f[]@a = {1, 2, 3, 4.5};
v[]@vecs = {{1,2,3}, {4,5,6}, {7,8,9}};

// Access by index
f@b = f[]@a[2];
v@c = v[]@vecs[1];
```
### Vector component access
```vex
vector myvector = {1, 2, 3};
v@a = {10, 15, 100};

// Dot notation and index notation are equivalent
float foo_dot   = @a.x;   // returns 10
float foo_index = @a[0];  // also returns 10
float foo_z     = @a[2];  // returns 100
```
### Query image dimensions
```vex
string map = chs('image');
float x, y;
teximport(map, 'texture:xres', x);
teximport(map, 'texture:yres', y);
@ratio = x / y;
```
### itoa and 64-bit precision
```vex
// 32-bit int wraps around above ~2.1 billion
s@test = itoa(2200000000);  // returns -2094967296

// Use 64-bit integer to avoid wrap
int64 big = 2200000000;
s@test = itoa(big);
```
### Modulo operator
```vex
// Creates looping/stepped values
@P.y = @ptnum % 5;          // steps 0-4 repeating
@Cd.r = @Time % 0.7;        // looping sawtooth over time
@Cd.r = @Time % 0.2;
```
### Normal-based color with conditional
```vex
@Cd = @N;
if (min(@Cd) < 0) {
    @Cd = 0.1;
}
```
### Up vector for copy orientation
```vex
v@up = {0, 1, 0};

// Animated circular up vector
v@up = set(sin(@Time), 0, cos(@Time));

// Per-point offset
float t = @Time * @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));
```
### Normal and position normalization
```vex
@N = normalize(@P);
@up = {0, 1, 0};

// Normalize point to unit sphere
@P = normalize(@P);
```
### Ternary operator
```vex
// If @Time modulo 1 equals 0, set 1, else set 0
@Cd = @Time % 1 == 0 ? 1 : 0;
```
### Mixing VEX and VOPs with snippets
```vex
P = P * myvector;
```

## Intermediate (774 examples)
### Distance from origin (length function)
```vex
// Basic distance field
float d = length(@P);
@Cd = d;

// Apply sine wave to distance
float d = length(@P);
@Cd = sin(d);

// Scale with channel reference
float d = length(@P);
d *= ch('scale');
@Cd = sin(d);
```
### Remapping sine output to 0-1 range
```vex
// Manual remap: sine outputs -1 to 1, shift to 0-2 then halve
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;

// Using fit() — same result with built-in clamping
float d = length(@P);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);

// One-liner version
@Cd = (sin(length(@P) * ch('scale')) + 1) * 0.5;
```
### Animating distance-based patterns with @Time
```vex
// Add @Time to shift rings outward over time
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d + @Time), -1, 1, 0, 1);

// Multiply @Time for expanding/contracting rings
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);
```
### Distance with non-uniform scaling and center
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);
```
### Distance-based Y displacement
```vex
float d = length(@P);
@P.y = d;

float d = length(@P);
@P.y = -d + 10;

float d = length(@P);
@P.y = d * 0.2;

float d = length(@P);
@P.y = d * 0.2 - 10;
```
### Clamp and fit with distance
```vex
float d = length(@P);
@P.y = clamp(d, 0, 5);

// fit remaps from one range to another
float d = length(@P);
float imin   = ch("fit_in_min");
float imax   = ch("fit_in_max");
float outMin = ch("fit_out_min");
float outMax = ch("fit_out_max");
d = fit(d, imin, imax, outMin, outMax);
@P.y = d;
```
### Chramp for height displacement
```vex
// Basic ramp-driven height
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);

// With time animation
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
### Sine with fit and ramp combined
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');

// Animated version
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
### Modulo for cyclic ramp mapping
```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
@P.y = chramp('myramp', d) * ch('height');
```
### Stepped quantizing with trunc
```vex
float d = length(@P);
d *= ch('scale');
d = trunc(d);
@P.y = d;

// Stepped ramp
float d = length(@P);
d *= ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```
### Normal-based displacement (sine wave ripple)
```vex
// Displace along normals with animated sine
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N * sin(d) * ch('wave_height');

// Radial wave Y displacement
float d = length(@P);
d *= ch("v_scale");
d += @Time;
@P.y = sin(d) * ch("wave_height");

// Animated ripple using frame
float d = length(@P);
d *= ch('v_scale');
d += @Frame;
@P += @N * sin(d) * ch('wave_height');
```
### Radial wave displacement with ramp
```vex
float d = length(@P);
d *= ch("v_scale");
d -= @Time;
@P += @N * sin(d) * ch("wave_height");
```
### Color ramp from distance field
```vex
// Distance -> sine -> fit -> color ramp
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp('myRamp', d);

// Animated version
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@Cd.y = chramp('myRamp', d);
```
### Dot product basics
```vex
// Y component of normal directly
@Cd = @N.y;
@Cd = -@N.y;

// Dot product with world up
@Cd = dot(@N, {0, 1, 0});

// Dot product with a channel-driven direction
@Cd = dot(@N, chv('angle'));
```
### Snow/ice effect with dot product threshold
```vex
float d = dot(@N, {0, 1, 0});
@Cd = {0, 0, 1};          // default blue
if (d > 0.5) {
    @Cd = {1, 1, 1};      // white on top faces
}

// Channel-driven cutoff
float d = dot(@N, {0, 1, 0});
@Cd = {0, 0, 1};
if (d > ch('cutoff')) {
    @Cd = {1, 1, 1};
}
```
### Cross product axis rotation
```vex
@N = cross(@N, {1, -1, 0});
```
### Conditional color with if-else
```vex
float d = dot(@P, {0, 1, 0});
@Cd = {0, 0, 1};
if (d > ch('cutoff')) {
    @Cd = {1, 1, 1};
} else {
    @Cd = {1, 0, 0};
}
```
### Floating-point epsilon comparison
```vex
// Never compare floats with == — use epsilon test
float foo = 0;
float bar = sin(PI);   // nearly 0 but not exactly

if (abs(foo - bar) < 0.00001) {
    @Cd = {1, 1, 0};   // yellow: equal within tolerance
} else {
    @Cd = {1, 0, 0};   // red: not equal
}
```
### Relpointbbox for normalized bounding box coords
```vex
// Get 0-1 position within bounding box
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

// Ramp-driven inflation along normals
vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```
### Custom attributes from distance
```vex
float d = length(@P);
@mydistance = d;
@Cd.r = sin(d);

// Named float attribute
f@d = length(@P);
f@d /= ch("scale");
@Cd = @d;
@Cd.r = sin(@d);
```
### pscale attribute
```vex
@pscale = ch('pscale');
```
### Animated pscale with sine wave
```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;
```
### Vector scale attribute (non-uniform)
```vex
// Uniform pscale
@pscale = ch('pscale');

// Non-uniform scale vector
@scale = {1, 5, 2.2};

// Component-wise assignment
@scale.x = 1;
@scale.y = d;
@scale.z = @Cd.g;

// Using set() with variables (curly braces don't allow variables)
float min, max, d;
min = ch('min');
max = ch('max');
@scale = set(min, d, min);
```
### Animated scale from distance
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t   = @Time * ch('speed');
d   = length(@P);
d   *= ch('frequency');
d   = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
### Multi-line operations for readability
```vex
float foo = 1;
foo *= 3;          // set range
foo += 1;          // ensure value never below 0
foo /= @Cd.x;      // reduce by red channel
foo += @N.y;       // add normal Y component
```
### Compound assignment operators
```vex
float d = length(@P);
d *= ch('scale');   // same as d = d * ch('scale')
d += @Time;         // same as d = d + @Time
d -= 1;
d /= 2;
d %= 1;
```
### Rotate with sin and cos (geometry)
```vex
float angle = atan(@P.x, @P.y);
@P.x += sin(@Time + angle);
@P.y += cos(@Time + angle);
```
### Twirl/spiral rotation
```vex
float angle  = atan(@P.x, @P.y);
float r      = length(set(@P.x, @P.y));
float amount = radians(ch('amount'));
float twirl  = r * ch('twirl');

@P.x = sin(amount + angle + twirl) * r;
@P.y = cos(amount + angle + twirl) * r;
```
### Length with fit remapping
```vex
int i    = 1 + len(@P);
f@x = fit(sin(i), 0, 1, 0.1, 3.1);
```
### Color ramp with vector cast
```vex
float min = chf('min');
float max = chf('max');
float d   = ch('frequency');
d = sin(d);
d = fit(d, -1, 1, min, max);
@scale = vector(min, max, 0);
@P.y += d / 2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
### Backface detection with normals
```vex
@Cd = @N;
if (dot(@N, {0,0,1}) < 0) {
    @Cd = 0.1;
}
```
### Nearest point color transfer with falloff
```vex
int   pt  = nearpoint(1, @P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d   = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```
### minpos — closest point on surface
```vex
// Find closest position on input 1 surface
vector pos = minpos(1, @P);
float d    = distance(@P, pos);
d         *= ch('scale');
@Cd        = d;
@Cd.r      = sin(d);
```
### Distance-based color with minpos variants
```vex
// Division variant
vector pos = minpos(1, @P);
float d    = distance(@P, pos);
d         /= ch("scale");
@Cd        = d;
@Cd.r      = sin(d);

// Green channel variant
vector pos = minpos(1, @P);
float d    = distance(pos, @P);
float s    = ch('scale');
@Cd        = d;
@Cd.g      = sin(d);

// Ramp variant
vector pos = minpos(1, @P);
float dist = distance(@P, pos);
@Cd        = chramp("calc", dist);
@Cd.r      = sin(dist);
```
### Nearest point displacement
```vex
int    pt  = nearpoint(1, @P);
vector pos = point(1, "P", pt);
float  d   = distance(@P, pos);
@P.y = d;
```
### Copying attributes between inputs
```vex
@P = @opinput1_P;
```
### Creating lines from points using normals
```vex
int pt = addpoint(0, {0, 3, 0});
addprim(0, "polyline", @ptnum, pt);

int pt = addpoint(0, @P + @N);
addprim(0, "polyline", @ptnum, pt);

vector pos = @N * noise(@P * @Time) * {1, 0.1, 1};
int pt     = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```
### Multi-point distance blending
```vex
v@P    = set(i@ptnum, 0, 0);
pos    = point(1, "P", i@ptnum);
d      = distance(@P, pos);
freq   = ch("freq");
float w = d * cos(freq);
w      = sin(w);
float amp = ch("amp") * ch("speed");
w      *= amp;
@P.y  += w;
```
### Animated curl noise color
```vex
@Cd = curlnoise(@P * chv('fancyscale') + @Time);
```
### Point attribute type declarations
```vex
s@greeting = "yessirree";
i@test     = 123;
f@scale    = ch("scale");
v@Cd       = fit(@P.y, 0, 1, 1, 0);
```
### Testing equality with if
```vex
int a = 3;
int b = 3;
if (a == b) {
    @Cd = {0, 1, 0};   // green if equal
}
```
### Conditional coloring using complex math
```vex
float a = length(v@P) * 2 + @ptnum % 5;
float b = dot(@N, {0, 1, 0}) * @Time;

if (a > b) {
    @Cd = {1, 0, 0};
}
```
### Frequency control with geometry resolution
```vex
float v = fit(0, 0, ch("radius"), 1, 10);
@P.y    = sin(length(@P) * v);
```
### Scaling position for color patterns
```vex
@Cd = @P.x;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.x + 2;
@Cd.z = @P.y;
```
### Variable in vector literal workaround
```vex
// This does NOT work — variables cannot be in curly brace literals
// vector myvec = {a, 2, 3};  // ERROR

// Use set() instead
float a = 42;
vector myvec = set(a, 2, 3);
```
### Distance-based height with ID offset
```vex
float d = length(@P);
d *= ch('scale');
d += @id;
d  = sin(d);
d *= ch('height');
@P.y = d;
```
### Combining sine with distance and time
```vex
float d = length(@P);
d  *= ch('scale');
d  -= @Time;
@P.y = ch("amp") * sin(d);
```
### Primitive intrinsic open/close
```vex
int open_close = int(rand(@primnum) * frame**2);
setprimintrinsic(0, "closed", @primnum, open_close);
```
### Animated wave with frequency and height
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y += sin(d * ch('freq'));
@P.y *= ch('height');
```
### Circular UV motion with primuv
```vex
vector uv;
uv.x = sin(@Time * 10);
uv.y = cos(@Time * 10);
uv   = fit(uv, -1, 1, -0.2, 0.2);
uv  += {0.5, 0.5};
@P   = primuv(1, "P", 0, uv);
@N   = primuv(1, "N", 0, uv);
```
### Circular UV animation variants
```vex
// Frame-driven
vector uv;
uv.x = sin(@Frame * 10);
uv.y = cos(@Frame * 10);
uv   = fit(uv, -1, 1, 0.2, 0.2);
uv  += {0.5, 0.5};
@P   = primuv(1, "P", 0, uv);
@N   = primuv(1, "N", 0, uv);

// Slow circle with 2x speed
vector uv;
uv.x = sin(@Time * 2);
uv.y = cos(@Time * 2);
uv   = fit(uv, -1, 1, -0.2, 0.2);
uv  += {0.5, 0.5};
@P   = primuv(1, "P", 0, uv);
@N   = primuv(1, "N", 0, uv);
```
### xyzdist — distance to surface with UV output
```vex
i@primid;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);

// Use stored UV to transfer attribute
@P = primuv(1, "P", @primid, @uv);
@N = primuv(1, "N", @primid, @uv);
```
### Orient attribute initialization
```vex
// Identity quaternion (no rotation)
@orient = {0, 0, 0, 1};
```
### Quaternion from angle and axis
```vex
float angle  = ch('angle');
vector axis  = chv('axis');
@orient = quaternion(angle, axis);

// Time-animated rotation
float angle  = @Time * ch('speed');
vector axis  = chv('axis');
@orient = quaternion(angle, axis);

// Compact one-liner
@orient = quaternion(@Time, chv('axis'));
```
### Per-point quaternion rotation with offset
```vex
float angle;
vector axis;

angle  = ch('angle');
angle += @ptnum * ch('offset');
angle += @Time * ch('speed');
axis   = chv('axis');

@orient = quaternion(angle, axis);
```
### Quaternion from normalized axis vector (axis-angle)
```vex
vector axis;
axis  = chv('axis');
axis  = normalize(axis);
axis *= @Time;   // magnitude = rotation amount in radians

@orient = quaternion(axis);
```
### Radians conversion for quaternions
```vex
vector axis;
axis       = chv('axis');
axis       = normalize(axis);
float angle = radians(90);    // 90 degrees -> PI/2 radians

@orient = quaternion(angle, axis);

// Using PI constant directly
float angle = PI / 2;
@orient = quaternion(angle, axis);
```
### Noise-based quaternion rotation
```vex
vector axis;
axis  = chv("axis");
axis  = normalize(axis);
float angle = trunc(noise(@P + @Time) * 4) * PI / 2;

@orient = quaternion(angle, axis);
```
### Ramp-remapped noise for quaternion
```vex
vector axis;
axis  = chv('axis');
axis  = normalize(axis);
@a    = noise(@P * @Time);
@a    = chramp('noise_remap', @a);
axis *= trunc(@a * 4) * (PI / 2);

@orient = quaternion(axis);
```
### Rotating up vector with sin and cos
```vex
float s = sin(@Time);
float c = cos(@Time);
@up = set(s, 0, c);

// With quaternion from N and up
@N  = {0, 1, 0};
@orient = quaternion(maketransform(@N, @up));
```
### Matrix to quaternion conversion
```vex
matrix3 m = ident();
@orient   = quaternion(m);

// From Euler angles (degrees via channel)
vector rot = radians(chv('euler'));
@orient    = eulertoquaternion(rot, 0);
```
### Quaternion slerp (spherical interpolation)
```vex
vector4 a     = {0, 0, 0, 1};   // identity
vector4 b     = quaternion(maketransform({0,1,0} * PI/2));
@orient = slerp(a, b, ch('blend'));

// With ramp-controlled blend
vector4 a     = {0, 0, 0, 1};
vector4 b     = quaternion({0,1,0} * PI/2);
float blend   = chramp('blendramp', @Time % 1);
@orient = slerp(a, b, blend);
```
### Quaternion slerp animation
```vex
vector4 target, base;
vector  axis;
float   seed, blend;

axis   = {0, 1, 0};
axis   = normalize(axis);
seed   = noise(@P + @Time);
seed   = chramp('noise_remap', seed);
axis  *= trunc(seed * 4) * (PI / 2);

target = quaternion(axis);
base   = {0, 0, 0, 1};
blend  = chramp('anim', @Time % 1);

@orient = slerp(base, target, blend);
```
### Orient from N and up via maketransform
```vex
@N  = normalize(@P);
@up = {0, 1, 0};
@orient = quaternion(maketransform(@N, @up));
```
### Extra rotation layered onto orient
```vex
@N   = normalize(@P);
@up  = {0, 1, 0};
@orient = quaternion(maketransform(@N, @up));

vector4 extrarot = quaternion(PI / 2, {1, 0, 0});
@orient = qmultiply(@orient, extrarot);
```
### Identity matrix
```vex
// Explicit
matrix3 m = [[1,0,0],[0,1,0],[0,0,1]];

// Using ident()
matrix3 m = ident();
```
### Reset primitive transform and position
```vex
matrix3 m = ident();
setprimintrinsic(0, 'transform', 0, m);
@P = {0, 0, 0};
```
### Setting packed primitive transform
```vex
vector  qorient = quaternion({0,1,0} * 2 * PI);
vector  qScale  = {1, 0.5, 2};

matrix3 m = ident();
scale(m, qScale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```
### Reading packed primitive transform
```vex
matrix pft = primintrinsic(0, "packedfullxform", @ptnum);
```
### Extracting rotation and scale from packed transform
```vex
matrix  pft         = primintrinsic(0, "packedfullxform", @ptnum);
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```
### Orient with scale matrix for instancing
```vex
@orient  = quaternion({0,1,0} * @Time);
@scale   = {1, 0.5, 1.5};

matrix3 m = ident();
scale(m, @scale);
m *= qconvert(@orient);

setprimintrinsic(0, 'transform', @ptnum, m);
```
### Animated instance orientation with distance offset
```vex
float d = length(@P);
float t = @Time - d * ch('offset');
v@up    = set(sin(t), 0, cos(t));
@P.y   += sin(t * 2) * 0.1;
```
### Multiple quaternion rotations (headshake + wobble)
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N         = normalize(@P);
up        = {0, 1, 0};
@orient   = quaternion(maketransform(N, up));
extrarot  = quaternion(radians(ch("angle")), {1, 0, 0});
headshake = quaternion(radians(20) * sin(@Time * 3), {0, 1, 0});
wobble    = quaternion(curlnoise(@P * chv("ns") + @Time) * radians(ch("wobble")));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```
### Extracting axes from quaternion orient
```vex
matrix3 m    = qconvert(@orient);
vector  axis[] = set(@N, @up);
@N  = normalize(axis[2]);   // Z axis
@up = normalize(axis[1]);   // Y axis
```

## Advanced (127 examples)
### Rotate with a matrix
```vex
// Create and rotate a 3x3 matrix
matrix3 m    = ident();
vector  axis = {0, 0, 1};
float   angle = radians(ch('amount'));

rotate(m, angle, axis);

// Apply rotation to position
@P *= m;
```
### optransform — read world transform of an object
```vex
matrix m = optransform('/obj/cam1');
@P *= m;
```
### Motion control camera with optransform
```vex
matrix m = optransform('/obj/moving_cube');
@P *= invert(m);
```
### Convert N to orient with dihedral
```vex
// Copy SOP assumes geometry points down Z axis
matrix3 m = dihedral({0, 0, 1}, @N);
@orient   = quaternion(m);
```
### Copies on surface with random rotation via orient
```vex
matrix3 m = dihedral({0, 1, 0}, @N);
rotate(m, @Time + rand(@ptnum) * ch('rot_rand'), @N);
@orient = quaternion(m);
```
### Scaling with matrices
```vex
matrix3 m = ident();
scale(m, chv('scale'));
@P *= m;
```
### Orient via euler values
```vex
vector rot = radians(chv('euler'));
@orient    = eulertoquaternion(rot, 0);
```
### Convert orient back to matrix
```vex
matrix m = qconvert(@orient);
```
### Intrinsics — set primitive sphere transform
```vex
matrix3 m = {1, 0, 0,
             0, 1, 0,
             0, 0, 1};
setprimintrinsic(0, 'transform', @ptnum, m);
```
### getpackedtransform and rotate
```vex
// Matrix to apply additional transform
matrix transform = ident();
rotate(transform, radians(45), {0, 1, 0});
translate(transform, {0, 1, 0});

matrix tf = getpackedtransform(0, @primnum);
setpackedtransform(0, @primnum, transform * tf);
```
### Spirally seaweed procedural geometry
```vex
// Spirally seaweed using sin and cos
vector offset, pos;
int    pr, pt;
float  stepsize;
float  x, y, inc;

pr       = addprim(0, 'polyline');
stepsize = 0.5;
```
### Scalar color ramp with animated scale boxes
```vex
float d    = ch('frequency');
float min  = ch('min');
float max  = ch('max');

d     = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
@P.y  -= d * 0.1;
d     = fit(d, min, max, 0, 1);
@Cd   = vector(chramp('color', d));
```
### Backface coloring via dot product
```vex
@Cd = @N;
if (dot(@N, {0, 0, 1}) < 0) {
    @Cd = 0.1;
}
```

## Function Reference
### efit
```vex
// Does NOT clamp output (unlike fit)
efit(.3, 0, 1, 10, 20) == 13
```
### fit
```vex
// Clamps output to [nmin, nmax]
fit(.3, 0, 1, 10, 20) == 13
```
### length / length2
```vex
length({1.0, 0, 0})    == 1.0
length({1.0, 1.0, 0})  == 1.41421

// Squared distance (cheaper — no sqrt)
length2({0.5, 0.75, 0}) == 0.8125
```
### swizzle
```vex
swizzle({10, 20, 30, 40}, 3, 2, 1, 0) == {40, 30, 20, 10}
swizzle({10, 20, 30, 40}, 0, 0, 0, 0) == {10, 10, 10, 10}
```
### serialize
```vex
vector v[] = {{1, 2, 3}, {7, 8, 9}};   // vector[] length 2
float  f[];
f = serialize(v);   // f[] length 6 = {1, 2, 3, 7, 8, 9}
```
### nuniqueval
```vex
int test = nuniqueval(0, "point", "foo") == npoints(0);
```
### typeid
```vex
// Check if the value for "foo" is a matrix
int type = typeid(d, "foo");
if (type == typeid(matrix())) {
    matrix m = d["foo"];
}
```
### computenormal
```vex
N = computenormal(P, "extrapolate", 1, "smooth", 0);
```
### filterstep
```vex
f = filterstep(0.5, s + t, "filter", "gauss", "width", 2);
```
### getderiv
```vex
// Get derivatives of point attribute 'N'
vector dNdu, dNdv;
getderiv(N, "N", 0, s, t, dNdu, dNdv);
```
### getuvtangents
```vex
// UV tangent at P in direction of N
vector Tu, Tv;
getuvtangents("/obj/geo1", P, N, Tu, Tv);
```
### ptransform
```vex
Pworld = ptransform("space:world", P);
```
### pcwrite
```vex
pcwrite("out.pc", "P", P, "N", N);
```
### photonmap
```vex
Cf = photonmap(
    map,
    P,
    normalize(frontface(N, I)),
    "nphotons", 100,
    "type", "diffuse",
    "error", 0.05,
    "filter", "convex"
);
```
### reflectlight
```vex
surface blurry_mirror(float angle = 3; int samples = 16; float bias = 0.05) {
    Cf = reflectlight(bias, 1, "angle", angle, "samples", samples);
}
```
### refract
```vex
refract(normalize(I), normalize(N), outside_to_inside_ior)
```
### trace
```vex
// Find position and normal for all hit points along ray
vector a_pos[];
vector a_nml[];
trace(P, dir, Time,
    "samplefilter", "all",
    "P", a_pos,
    "N", a_nml
);
```
### scatter
```vex
// Trace for intersection with scene
vector hitP = 0;
vector hitN = 0;
int    hit  = trace(P, I, Time, "P", hitP, "N", hitN);

// Scatter a random distance from intersection
vector idistribution = 0;
int    sid = israytrace ? SID : newsampler();
vector s;
nextsample(sid, s.x, s.y, "mode", "nextpixel");
float maxdist = 2.0 * s.x;

vector opoint     = 0;
vector onormal    = 0;
vector odirection = 0;
hit = scatter(hitP, hitN, I, idistribution, Time, maxdist,
              opoint, onormal, odirection);

// Trace again from exit point
hit = trace(opoint, odirection, Time, "P", hitP, "N", hitN);
```
### sample_bsdf
```vex
sample_bsdf(
    F, inI, outI, eval, type, sx, sy,
    "direct", 0,
    "import:sssmfp", sssmfp
);
```
### eval_bsdf
```vex
v = eval_bsdf(
    F, inI, dir,
    "direct", 0,
    "import:sssmfp", sssmfp
);
```
### sample_cauchy
```vex
sample_cauchy(1, 0, maxdist, u.x) * sample_direction_uniform(set(u.y, u.z))
```
### kspline
```vex
type kspline(basis, t, v0, k0, v1, k1, v2, k2) {
    float tk = spline("linearsolve", t, k0, k1, k2);
    return spline(basis, tk, v0, v1, v2);
}
```
### isbound
```vex
sop mycolor(vector uv = 0; string map = "") {
    if (isbound("uv") && map != "") {
        // Texture coordinates available
        v = colormap(map, uv);
    } else {
        // Fall back to random value
        v = random(id);
    }
}
```
### getlights
```vex
getlights("lightmask", "light*,^light2");
getlights("categories", "shadow|occlusion");
getlights(material(), P, "direct", 0);
```
### interpolate
```vex
vector hitP = interpolate(P, sx, sy);
```
### volumesmoothsample
```vex
vector P    = {1.0, 2.0, 3.0};
vector grad;
matrix3 hess;

float val1 = volumesmoothsample(0, "density", P, grad, hess);
vector u   = {0.1, 0.01, 0.001};
float val2 = volumesmoothsample(0, "density", P + u);

// Taylor expansion: val1 + dot(u, grad) ≈ val2
// Second order:     val1 + dot(u, grad) + 0.5 * dot(u, u*hess) ≈ val2
```

## USD VEX Functions
### usd_addattrib
```vex
// Add half-precision float attribute and set value
usd_addattrib(0, "/geo/sphere", "half_attrib", "half3");
usd_setattrib(0, "/geo/sphere", "half_attrib", {1.25, 1.50, 1.75});
```
### usd_addcollectionexclude / usd_addcollectioninclude
```vex
string collection_path = usd_makecollectionpath(0, "/geo/cube", "some_collection");
usd_addcollectionexclude(0, collection_path, "/geo/sphere3");
usd_addcollectioninclude(0, collection_path, "/geo/sphere4");
```
### usd_addorient
```vex
vector4 quat = eulertoquaternion(radians({30, 0, 0}), XFORM_XYZ);
usd_addorient(0, "/dst/cone", "my_orientation", quat);
```
### usd_addprimvar
```vex
// Add half-precision float primvar
usd_addprimvar(0, "/geo/sphere", "half_primvar", "half3");
usd_setprimvar(0, "/geo/sphere", "half_primvar", {1.25, 1.50, 1.75});

// Add color primvar with vertex interpolation
string pp = "/geo/sphere";
usd_addprimvar(0, pp, "color_primvar", "color3d[]", "vertex");
usd_setprimvar(0, pp, "color_primvar",
    vector[](array({1,0,0}, {0,1,0}, {0,0,1})));
```
### usd_addschemaattrib
```vex
usd_applyapi(0, "/geo", "GeomModelAPI");
usd_addschemaattrib(0, "/geo", "extentsHint", "float[]");
```
### usd_bindmaterial
```vex
usd_bindmaterial(0, "/geo/sphere", "/materials/metal");
```
### usd_blockprimvarindices
```vex
usd_blockprimvarindices(0, "/geo/sphere", "primvar_name");
```
### usd_blockrelationship
```vex
usd_blockrelationship(0, "/geo/cube", "relationship_name");
```
### usd_boundmaterialpath
```vex
string matpath = usd_boundmaterialpath(0, "/geo/sphere");
```
### usd_cleartransformorder
```vex
usd_cleartransformorder(0, "/geo/cone");
```
### usd_iprimvarlen / usd_iprimvarsize / usd_iprimvartypename
```vex
int array_length = usd_iprimvarlen(0, "/geo/cube", "array_primvar_name");
int tuple_size   = usd_iprimvarsize(0, "/geo/cube", "primvar_name");
string type_name = usd_iprimvartypename(0, "/geo/cube", "primvar_name");
```
### usd_isabstract / usd_isactive / usd_isinstance
```vex
int is_abstract  = usd_isabstract(0, "/geometry/sphere");
int is_active    = usd_isactive(0, "/geometry/sphere");
int is_instance  = usd_isinstance(0, "/geometry/sphere");
```
### usd_isarray / usd_isarrayprimvar / usd_isarrayiprimvar
```vex
int is_array      = usd_isarray(0, "/geometry/sphere", "some_attribute");
int is_arr_pv     = usd_isarrayprimvar(0, "/geometry/sphere", "some_primvar");
int is_arr_ipv    = usd_isarrayiprimvar(0, "/geometry/sphere", "some_primvar");
```
### usd_isindexedprimvar / usd_isiprimvar / usd_isprimvar
```vex
int is_indexed = usd_isindexedprimvar(0, "/geometry/sphere", "some_primvar");
int is_ipv     = usd_isiprimvar(0, "/geometry/sphere", "some_primvar");
int is_pv      = usd_isprimvar(0, "/geometry/sphere", "some_primvar");
```
### usd_iskind / usd_ismodel / usd_istype
```vex
int is_assembly = usd_iskind(0, "/geometry/sphere", "assembly");
int is_model    = usd_ismodel(0, "/geometry/sphere");

// Check type by alias and full name
int is_cube_by_alias  = usd_istype(0, "/geo/cube", "Cube");
int is_cube_by_name   = usd_istype(0, "/geo/cube", "UsdGeomCube");
int is_boundable      = usd_istype(0, "/geo/cube", "UsdGeomBoundable");
```
### usd_ismetadata
```vex
int has_doc         = usd_ismetadata(0, "/geo/sphere", "documentation");
int has_custom_data = usd_ismetadata(0, "/geo/cube", "customData:foo:bar");

// Check attribute custom data
string attrib_path  = usd_makeattribpath(0, "/geo/sphere", "attrib_name");
int has_attrib_foo  = usd_ismetadata(0, attrib_path, "customData:foo");
```
### usd_istransformreset / usd_isvisible
```vex
int is_xform_reset = usd_istransformreset(1, "/geo/cube");
int is_visible     = usd_isvisible(0, "/geometry/sphere");
```
### usd_localtransform / usd_worldtransform
```vex
matrix cube_local_xform = usd_localtransform(0, "/src/cube");
matrix cube_world_xform = usd_worldtransform(0, "/src/cube");
```
### usd_makecollectionpath / usd_makepropertypath
```vex
string collection_path = usd_makecollectionpath(0, "/geo/cube", "some_collection");
```
### usd_pointinstancetransform / usd_pointinstance_relbbox
```vex
// Get transform of the third instance
matrix xform = usd_pointinstancetransform(0, "/src/instanced_cubes", 2);

// Get relative bounding box position
vector pt     = {1, 0, 0};
vector rel_pt = usd_pointinstance_relbbox(0, "/src/instanced_spheres", 0, "render", pt);
```
### usd_primvar / usd_primvarelement
```vex
// Read primvar values
vector vec_value   = usd_primvar(0, "/geo/cube", "vec_primvar_name");
float  values[]    = usd_primvar(0, "/geo/cube", "primvar_name");
float  value       = usd_primvar(0, "/geo/cube", "primvar_name", 3);

// Time-sampled primvar
v[]@foo_at_current = usd_primvar(0, "/geo/sphere", "foo");
v[]@foo_at_frame_8 = usd_primvar(0, "/geo/sphere", "foo", 8.0);

// Element at index
float element2     = usd_primvarelement(0, "/geo/cube", "primvar_name", 2);
v@element_2_now    = usd_primvarelement(0, "/geo/sphere", "foo", 2);
v@element_2_f8     = usd_primvarelement(0, "/geo/sphere", "foo", 2, 8.0);
```
### usd_primvar metadata
```vex
int    element_size   = usd_primvarelementsize(0, "/geo/cube", "primvar_name");
int    indices[]      = usd_primvarindices(0, "/geo/cube", "indexed_primvar_name");
string interpolation  = usd_primvarinterpolation(0, "/geo/cube", "primvar_name");
int    array_length   = usd_primvarlen(0, "/geo/cube", "array_primvar_name");
string primvar_names[]= usd_primvarnames(0, "/geo/src_sphere");
int    tuple_size     = usd_primvarsize(0, "/geo/cube", "primvar_name");
string type_name      = usd_primvartypename(0, "/geo/cube", "primvar_name");
```
### usd_purpose / usd_variants / usd_variantselection
```vex
string purpose          = usd_purpose(0, "/geo/sphere");
string variants[]       = usd_variants(0, "/geo/shape_shifter", "shapes");
string selected_variant = usd_variantselection(0, "/geo/shape_shifter", "shapes");
```
### usd_relationshipforwardedtargets / usd_relationshipnames
```vex
string targets[]           = usd_relationshipforwardedtargets(0, "/geo/cube", "some_relationship");
string relationship_names[]= usd_relationshipnames(0, "/geo/cube");
```
### usd_relbbox
```vex
vector pt     = {1, 0, 0};
vector rel_pt = usd_relbbox(0, "/src/sphere", "render", pt);
```
### usd_removerelationshiptarget
```vex
usd_removerelationshiptarget(0, "/geo/cube", "relationship_name", "/geo/sphere");
```
### usd_setcollectionexcludes / usd_setcollectionincludes
```vex
string collection_path = usd_makecollectionpath(0, "/geo/cube", "some_collection");
usd_setcollectionexcludes(0, collection_path, array("/geo/sphere4", "/geo/sphere5"));
```
### usd_setcollectionexpansionrule
```vex
string collection_path = usd_makecollectionpath(0, "/geo/cube", "some_collection");
usd_setcollectionexpansionrule(0, collection_path, "explicitOnly");
```
### usd_setdrawmode
```vex
usd_setdrawmode(0, "/geo/sphere", "bounds");
usd_setdrawmode(0, "/geo/cube", "default");
```
### usd_setprimvarelement / usd_setprimvarelementsize
```vex
usd_setprimvarelement(0, "/geo/sphere", "float_arr_primvar", 2, 0.25);
usd_setprimvarelementsize(0, "/geo/mesh", "primvar_name", 2);
```
### usd_setprimvarindices / usd_setprimvarinterpolation
```vex
float values[]  = array(0, 100, 200, 300, 400, 500);
int   indices[] = array(5, 5, 4, 4, 3, 3, 2, 2, 1, 1, 0, 0);
usd_setprimvar(0, "/geo/mesh", "primvar_name", values);
usd_setprimvarindices(0, "/geo/mesh", "primvar_name", indices);

usd_setprimvarinterpolation(0, "/geo/mesh", "primvar_name", "faceVarying");
```
### usd_settransformorder
```vex
string ops[] = {
    "xformOp:translate:xform_cube_t",
    "xformOp:rotateZ:xform_cube_r",
    "xformOp:rotateXYZ:xform_cube_r",
    "xformOp:scale:xform_cube_s"
};
usd_settransformorder(0, "/geo/cube", ops);
```
### usd_transformname / usd_transformorder / usd_transformsuffix / usd_transformtype
```vex
// Build full name for a transform operation
string pivot_xform_name = usd_transformname(USD_XFORM_TRANSLATE, "cone_pivot");

// Get ordered list of transform ops
string cube_xform_ops[] = usd_transformorder(0, "/geo/cube");
string suffix           = usd_transformsuffix(cube_xform_ops[0]);
int    type             = usd_transformtype(cube_xform_ops[0]);
```

## Expert (3 examples)
### Rubiks cube rotation axes
```vex
if (randaxis == 0) axis = {1, 0, 0};
if (randaxis == 1) axis = {0, 1, 0};
if (randaxis == 2) axis = {0, 0, 1};
```
### VEX includes (external function libraries)
```vex
function float addfoo(float a; float b) {
    float result = a + b;
    return result;
}
```
### Vector component assignment clarity
```vex
@Cd    = v1;
@Cd.x  = curlnoise(@P * chv('fancyscale')) * @Time;
```
