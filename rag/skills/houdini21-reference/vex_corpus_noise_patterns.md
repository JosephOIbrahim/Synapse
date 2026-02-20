# VEX Corpus: Noise Patterns

> 41 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Intermediate (30 examples)

### Noise â

```vex
@Cd = noise(@P);
// One of the most common things you'll do is require procedural noise.
```
### Noise with Parameters and Animation

```vex
@Cd = noise(chv('offset') + @P * chv('fancyscale') * @Time);
// Progressive enhancement of noise: add channel parameters for scale/offset, then incorporate time-based animation.
```
### Quaternion Rotation Progressions

```vex
vector axis1;
axis1 = normalize(axis1);
axis1 = $PI/2;
@orient = quaternion(axis1);
// A progression of quaternion rotation examples showing evolution from basic axis rotation to randomized and animated variations.
```
### Random Rotation Quantization

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= $PI/2;
@orient = quaternion(axis);
// Three variations of quantized rotation around an axis: fixed 90-degree, random 90-degree increments per point using rand(), and noise-driven 90-degree rotations.
```
### Quantized Noise for Orientation

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P + @P.y);
axis *= trunc(@a*4)*(PI/2);
@orient = quaternion(axis);
// Uses noise based on point position to create quantized rotation angles by truncating the noise value multiplied by 4, then scaling by PI/2 to produce 90-degree increments.
```
### Storing noise as attribute

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P + f@time);
axis *= trunc(@a*4)*$PI/2;
@orient = quaternion(axis);
// Creates a float attribute @a to store the noise value for debugging and inspection in the geometry spreadsheet.
```
### Remapping noise with fit function

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*@Time);
@a = fit(@a, 0.4, 0.6, 0, 1);
axis *= trunc(@a*4)*@t/2;
@orient = quaternion(axis);
// Uses fit() to remap noise values: takes the range 0.4–0.6 from @a and stretches it to 0–1, creating more variance and contrast.
```
### Quaternion Rotation from Noise

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*f@lmn);
axis *= trunc(@a*4)*$PI/2;
@orient = quaternion(axis);
// Creates quaternion-based orientation by computing noise at each point, truncating and scaling to discrete 90-degree rotation angles around a user-defined axis.
```
### Interactive Noise Manipulation with Ramps

```vex
vector axis;
axis = normalize(axis);
@orient = quaternion(axis);

v@orient = quaternion(axis);
axis = chv("axis");
axis = normalize(axis);
// Demonstrates using channel references and ramps to get interactive visual feedback when tweaking noise values.
```
### Visualizing Attribute Data with Position

```vex
@a = noise(@P * @Time);
@a = chramp('noise_ramp', @a);

vector axis;
axis = chv('axis');
axis = axis * length(@orient, @a);
axis *= trunc(@a * 4) * ($PI / 2);
// Visualizes an attribute value by mapping it to point position, setting Y equal to a processed noise/ramp value (@a).
```
### Visualizing Data with Position

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = chramp('noise_range', @Cd);
axis *= trunc(@a * 4) * @P.z;
@P.y = @a;
@orient = quaternion(axis);
// Demonstrates visualizing attribute data by mapping a remapped color value (@a from chramp) to the Y position of points, making data visible through vertical displacement.
```
### Visualizing Attributes via Position

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@N = noise(@P*@Time);
@a = noise(@P*@Time*PI)*@b1/2;
@P.y = @a;
@orient = quaternion(axis);
// Maps an attribute value (@a) to @P.y, causing points to jump up and down based on noise-driven values.
```
### Curl Noise with Vector Offset

```vex
vector pos = chv('pos');
@P += pos * curlnoise((@P + {0,1,0}) * (@w * 0.2) * @Time, 0, 0);
// Offsets point positions using curl noise driven by a channel-referenced vector parameter.
```
### Noise with Channel Parameters

```vex
@Cd = noise(chv('offset') + @P * chv('fancyscale') * @Time);
// Progressive refinement of noise-based color assignment, building from basic noise(@P) to a fully parameterized expression using channel references for offset and scale.
```
### Noise Function with Parameters

```vex
@Cd = noise(chv('offset') + @P * chv('fancyscale'));
// Uses noise to generate color values by combining position with channel-referenced parameters for offset and scale control.
```
### Animating Noise with Offset and Time

```vex
@Cd = noise(chv('offset') + @P * chv('fancyscale') + @Time);
// Animates noise patterns by combining position (@P), scale parameters, offset controls, and time (@Time).
```
### Animating Noise with Offset Parameter

```vex
@Cd = noise(chv('offset') * @P * chv('fancyscale') * @Frame);
// Combines multiple parameters to control noise-based color attributes: vector offset, fancy scale, and frame-based animation.
```
### Animating Noise with Channels

```vex
@Cd = curlnoise(@P * chv('fancyscale') * @Time);
// Progression from basic noise to animated curl noise using channel references and time.
```
### Animated Noise with Channels

```vex
@Cd = curlnoise(chv('offset') + @P * chv('fancyscale') * @Time);
// Progressive building of animated noise expressions combining channel parameters with position, time, and noise functions.
```
### Animating Noise with Time

```vex
@Cd = curlnoise(@P * chv('fancyscale') * @Time);
// Animates noise patterns by incorporating @Time, creating moving color patterns.
```
### Curl Noise Color Animation

```vex
v@Cd = curlnoise(@P * chv('fancyscale') * @Time);
@Cd[1];
// Uses curlnoise to generate animated vector colors based on point position, scaled by a channel parameter and animated with @Time.
```
### Animating Curlnoise with Time

```vex
@Cd = curlnoise(@P * chv("fancyscale") * @Time);
// Uses curlnoise to generate animated color values by multiplying position with a channel parameter and @Time.
```
### Wispy Geometry Along Normals

```vex
vector pos = ch("noise") * noise(@P * @Time) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pt, pt1;
float stepsize;
// Creates wispy geometry by generating multiple points along the surface normal direction, with each point offset by curl noise to create organic variation.
```
### Normal Attribute in Polyline Generation

```vex
vector offset, pos;
int pt;
float stepsize;

pt = addpoint(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < @id + 1; i++) {
    // iterate and build polyline
}
// Demonstrates how the @N (normal) attribute is implicitly set and used when generating polylines with addpoint.
```
### Normal Calculation Methods in Polyline Generation

```vex
vector TOF = @noise(@Frame) * {1, 0, 1};
int pt = addpoint(0, @P + pos);
addvertex(0, prim, pt);

vector offset, pos;
int pr, pt;
float distance;
// Demonstrates how normal calculations can vary based on whether normals are set explicitly or calculated implicitly from geometry.
```
### Curl noise offset polyline

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    pos = @P + @N * i * stepsize;
    pos += curlnoise(pos * 0.5) * 0.1;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
// Creates a polyline by iterating 6 times, adding points at positions offset from the current point along its normal direction, scaled by iteration index and step size, with additional randomization from curl noise.
```
### getsamplestore

```vex
// Displaced lens CVEX shader using setsamplestore/getsamplestore
cvex displacedlens(
    // Inputs
    float x       = 0;
    float y       = 0;
    float Time    = 0;
    float dofx    = 0;
    float dofy    = 0;
    float aspect  = 1;
    float displaceScale = 1.0;
    float displaceGain  = 0.1;
    // Outputs
    export vector P = 0;
    export vector I = 0;
) {
    P = {x, y, 0};
    I = {1, 0, 0};
    vector displace = noise(P * displaceScale) * displaceGain;
    I += displace;
    // Store the displacement at the eye point 'P'
    int status = setsamplestore("displacedlens_d", P, displace);
}

surface mysurface() {
    // Get the displacement at the eye point 'Eye'
    vector displace = 0;
    int status = getsamplestore("displacedlens_d", Eye, displace);
    // use displace to shade the surface
}
// Demonstrates setsamplestore/getsamplestore for passing data between CVEX lens shaders and surface shaders in a displaced lens setup.
```
### mspace

```vex
// Accumulate noise in material space relative to rest position
forpoints(P) {
    vector npos = mspace(P) - mattrib("rest", P);
    nval += noise(npos);
}
// Uses mspace() to transform point positions into material space, then subtracts the rest position to compute noise relative to rest, avoiding noise swimming on deforming geometry.
```
### pnoise

```vex
// Periodic noise: tiling in X by 4 periods, Y by 5 periods
clr = pnoise(X*4, Y*5, 4, 5);
// Periodic noise function that tiles seamlessly. Arguments: position scaled by period count, then the period counts. Useful for looping or tiling noise patterns.
```
### TASK: classify_wrangle

```vex
@P += curlnoise(@P * ch("freq")) * ch("amp");
// **Purpose:** Determine the execution context of VEX code.
```


**Input Schema:**

**Output Schema:**

**Decision Rules:**
1.

## Advanced (11 examples)

### Make this rotation thing do what we want â

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P + @Time);
axis *= trunc(@a*4)*$PI/2;
@orient = quaternion(axis);
// Not quite behaving as expected — the truncate-and-scale pattern produces discrete 90-degree steps driven by animated noise.
```
### Quaternion Rotation from Noise

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@ptnum);
@a = fit(@a, 0, 1, 0, 1);
axis *= trunc(@a*5)*$PI/2;
@orient = quaternion(axis);
// Creates quaternion-based rotations: generates noise per point, fits it to a range, then quantizes to discrete rotation angles (multiples of PI/2).
```
### Quaternion Orientation from Axis

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P * @Time);
@a = chramp('noise_rearrange', @a);
axis *= trunc(@a * 8) * $PI / 2;
@P.y = @a;
// Creates point orientation using quaternions derived from noise-driven axis rotation and time-based up vector animation.
```
### Quaternion wobble with curl noise

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0, 1, 0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@0), {1, 0, 0});
headshake = quaternion(radians(20) * sin(@Time*3), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P * @Time * 0.2));
@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
// Declares a wobble quaternion variable and initializes it using curl noise applied to a Z-axis vector, layered with other quaternion rotations.
```
### Quaternion Wobble with Curl Noise

```vex
vector N, up;
vector4 orient, extract, headshake, wobble;

N = normalize(@P);
up = {0, 1, 0};
@orient = quaternion(maketransform(N, up));
extract = quaternion(radians(@Frame), {1, 0, 0});
headshake = quaternion(radians(20) * sin(@Time*3), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P * @Time * 0.2));
@orient = qmultiply(@orient, extract);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
// Creates a wobble rotation using curl noise driven by position and time, then multiplies it into the existing orientation quaternion chain.
```
### Quaternion Wobble with Curl Noise (chf variant)

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(v@P);
up = {0, 1, 0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1, 0, 0});
headshake = quaternion(radians(20) * sin(chf("time")*2), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P * chf("time") * 0.2));
@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
// Creates a compound orientation using multiple quaternion rotations: a base orientation from normalized position, a 90-degree X-axis rotation, an animated sine-based headshake on Y-axis, and a position/time-driven curl noise wobble.
```
### Layered Quaternion Rotations

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0, 1, 0};
@orient = maketransform(N, up);
extrarot = quaternion(radians(@Frame), {1, 0, 0});
headshake = quaternion(radians(20) * sin((@Time * chf("freq")) * 3), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P * @Time * 0.2));
@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
// Demonstrates building complex rotations by layering multiple quaternions through qmultiply.
```
### Quaternion Composition for Complex Orientations

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0, 1, 0};
@orient = maketransform(N, up);
extrarot = quaternion(radians(@N), {1, 0, 0});
headshake = quaternion(radians(2*@P.y + sin(@TimeInc + @ptnum)*3), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P * @Time * 0.2));
@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
// Demonstrates building complex orientations by composing multiple quaternions together using qmultiply.
```
### Converting Orient to N and Up Vectors

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
@N = {0, 1, 0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N), {1, 0, 0});
headshake = quaternion(radians(20) * sin((@TimeInc * chs("speed")) * 3), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P * @Time * 0.2));
@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
// Convert back: matrix3 m = qconvert(@orient); @N = {0,1,0} * m; up = {0,0,1} * m;
// Converts a quaternion orientation back into N and up vector attributes by converting the quaternion to a matrix3, then multiplying basis vectors by that matrix.
```
### Per-Point Time Offset for Quaternion Animation

```vex
vector h, up;
vector4 extrarot, headshake, wobble;

h = normalize(@P);
up = {0, 1, 0};
@orient = quaternion(maketransform(h, up));
extrarot = quaternion(radians(@N.x), {1, 0, 0});
headshake = quaternion(radians(20) * sin((@Time + @ptnum) * chv("us") * 3), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P * @Time * 0.2));
@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
// Uses point number (@ptnum) as a per-point time offset to create varied animation timing across copied instances.
```
### Converting Quaternion to Normal Vectors

```vex
vector H, N, up;
vector4 xtrarot, headshake, wobble;

H = normalize(@P);
N = {0, 1, 0};
@orient = quaternion(maketransform(N, up));
@xtrarot = quaternion(radians(90), {1, 0, 0});
headshake = quaternion(radians(20) * sin(@TimeInc * chf("mus") * 3), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P * @Time * 0.2));
@orient = qmultiply(@orient, @xtrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
// Convert back: matrix3 m = qconvert(@orient); @N = {0,1,0} * m; up = {0,0,1} * m;
// Converts a quaternion orientation to normal and up vectors by converting the quaternion to a matrix3 using qconvert(), then multiplying basis vectors by that matrix.
```

