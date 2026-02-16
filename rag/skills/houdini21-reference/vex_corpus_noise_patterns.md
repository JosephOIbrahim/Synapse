# VEX Corpus: Noise Patterns

> 41 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Intermediate (30 examples)

### Noise â

```vex
@Cd = noise(@P);
```

One of the most common things you'll do is require procedural noise.

### Noise with Parameters and Animation

```vex
@Cd = noise(chv('offset') + @P * chv('fancyscale') * @Time);
```

Demonstrates progressive enhancement of noise by adding channel parameters for scale control and offset, then incorporating time-based animation.

### Quaternion Rotation Progressions

```vex
vector axis1;

axis1 = normalize(axis1);
axis1 = $PI/2;

@orient = quaternion(axis1);

vector axis;
// ...
```

A progression of quaternion rotation examples showing evolution from basic axis rotation to randomized and animated variations.

### Random Rotation Quantization

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= $PI/2;

@orient = quaternion(axis);

vector axis;
// ...
```

Demonstrates three variations of quantized rotation around an axis: first a fixed 90-degree rotation, then random 90-degree increments per point using rand(), and finally noise-driven 90-degree rot....

### Quantized Noise for Orientation

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P + @P.y);
axis *= trunc(@a*4)*(PI/2);

@orient = quaternion(axis);
```

Uses noise based on point position to create quantized rotation angles by truncating the noise value multiplied by 4, then scaling by PI/2 to produce 90-degree increments.

### Storing noise as attribute

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+f@time);
axis *= trunc(@a*4)*$PI/2;

@orient = quaternion(axis);
```

Creates a float attribute @a to store the noise value for debugging and inspection in the geometry spreadsheet.

### Remapping noise with fit function

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*@Time);
@a = fit(@a, 0.4, 0.6, 0, 1);
axis *= trunc(@a*4)*@t/2;

@orient = quaternion(axis);
```

Uses the fit() function to remap noise values by taking the range between 0.4 and 0.6 from the attribute @a and stretching it to fill the full 0 to 1 range, creating more variance and contrast in t....

### Quaternion Rotation from Noise

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*f@lmn);
axis *= trunc(@a*4)*$PI/2;

@orient = quaternion(axis);
```

Creates quaternion-based orientation by computing a noise value at each point position, then truncating and scaling it to create discrete rotation angles (multiples of 90 degrees) around a user-def....

### Interactive Noise Manipulation with Ramps

```vex
vector axis;
axis = normalize(axis);

@orient = quaternion(axis);

v@orient = quaternion(axis);
axis = chv("axis");
axis = normalize(axis);
// ...
```

Demonstrates using channel references and ramps to get interactive visual feedback when tweaking noise values.

### Visualizing Attribute Data with Position

```vex
@a = noise(@P * @Time);
@a = chramp('noise_ramp', @a);

vector axis;
axis = chv('axis');
axis = axis * length(@orient, @a);
axis *= trunc(@a * 4) * ($PI / 2);

// ...
```

Demonstrates visualizing an attribute value by mapping it to point position, specifically setting the Y component of @P equal to a processed noise/ramp value (@a).

### Visualizing Data with Position

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = chramp('noise_range', @Cd);
axis *= trunc(@a * 4) * @P.z;
@P.y = @a;
@orient = quaternion(axis);
```

Demonstrates visualizing attribute data by mapping a remapped color value (@a from chramp) to the Y position of points, making the data visible through vertical displacement.

### Visualizing Attributes via Position

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@N = noise(@P*@Time);
@a = noise(@P*@Time*PI)*@b1/2;
@P.y = @a;

@orient = quaternion(axis);
// ...
```

Demonstrates visualization technique by mapping an attribute value (@a) to point position (@P.y), causing points to jump up and down based on noise-driven values.

### Curl Noise with Vector Offset

```vex
vector pos = chv('pos');
@P += pos * curlnoise((@P + {0,1,0}) * (@w * 0.2) * @Time, 0, 0);
```

Offsets point positions using curl noise driven by a channel-referenced vector parameter.

### Noise with Channel Parameters

```vex
@Cd = noise(chv('offset')+@P*chv('fancyscale')*@Time);
```

Demonstrates progressive refinement of noise-based color assignment, building from basic noise(@P) to a fully parameterized expression using channel references for offset, scale (with vector contro....

### Noise Function with Parameters

```vex
@Cd = noise(chv('offset')+@P*chv('fancyscale'));
```

Demonstrates using the noise function to generate color values by combining position with channel-referenced parameters for offset and scale control.

### Animating Noise with Offset and Time

```vex
@Cd = noise(chv('offset') + @P * chv('fancyscale') + @Time);
```

Demonstrates various methods for animating noise patterns by combining position (@P), scale parameters, offset controls, and time (@Time).

### Animating Noise with Offset Parameter

```vex
@Cd = noise(chv('offset')*@P*chv('fancyscale')*@Frame);
```

Demonstrates combining multiple parameters to control noise-based color attributes, including vector offset, fancy scale, and frame-based animation.

### Animating Noise with Channels

```vex
@Cd = curlnoise(@P*chv('fancyscale')*@Time);
```

Demonstrates progression from basic noise to animated curl noise using channel references and time.

### Animated Noise with Channels

```vex
@Cd = curlnoise(chv('offset')+@P*chv('fancyscale')*@Time);
```

Demonstrates progressive building of animated noise expressions by combining channel parameters with position, time, and noise functions.

### Animating Noise with Time

```vex
@Cd = curlnoise(@P * chv('fancyscale') * @Time);
```

Demonstrates how to animate noise patterns by incorporating @Time into the noise function, creating moving color patterns.

### Curl Noise Color Animation

```vex
v@Cd = curlnoise(@P * chv('fancyscale') * @Time);
@Cd[1]
```

Uses curlnoise to generate animated vector colors based on point position, scaled by a channel parameter and animated with @Time.

### Animating Curlnoise with Time

```vex
@Cd = curlnoise(@P * chv("fancyscale") * @Time);
```

Uses curlnoise to generate animated color values by multiplying position with a channel parameter and the @Time attribute.

### Wispy Geometry Along Normals

```vex
vector pos = ch("noise") * noise(@P * @Time) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pt, pt1;
float stepsize;

// ...
```

Creates wispy geometry by generating multiple points along the surface normal direction, with each point offset by curl noise to create organic variation.

### Normal Attribute in Polyline Generation

```vex
vector offset, pos;
int pt;
float stepsize;

pt = addpoint(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < @id + 1; i++) {
// ...
```

Demonstrates how the @N (normal) attribute is implicitly set and used when generating polylines with addpoint.

### Normal Calculation Methods in Polyline Generation

```vex
vector TOF = @noise(@Frame)*{1,0,1};
int pt = addpoint(0,@P+pos);
addvertex(0, prim, pt);

vector offset, pos;
int pr, pt;
float distance;

// ...
```

Demonstrates how normal calculations can vary based on whether normals are set explicitly or calculated implicitly from geometry.

### Curl noise offset polyline

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Creates a polyline by iterating 6 times and adding points at positions offset from the current point along its normal direction, scaled by the iteration index and step size, with additional randomi....

### getsamplestore

```vex
cvexdisplacedlens(// Inputsfloatx=0;floaty=0;floatTime=0;floatdofx=0;floatdofy=0;floataspect=1;floatdisplaceScale=1.0;floatdisplaceGain=0.1;// OutputsexportvectorP=0;exportvectorI=0;
){P={x,y,0};I={1,0,0};vectordisplace=noise(P*displaceScale) *displaceGain;I+=displace;// Store the displacement at the eye point, 'P'intstatus=setsamplestore("displacedlens_d",P,displace);}surfacemysurface(){// Get the displacement at the eye point, 'Eye'vectordisplace=0;intstatus=getsamplestore("displacedlens_d",Eye,displace);//...}
```

Signature: cvexdisplacedlens(// Inputsfloatx=0;floaty=0;floatTime=0;floatdofx=0;floatdofy=0;floataspect=1;floatdisplaceScale=1.0;floatdisplaceGain=0.1;// OutputsexportvectorP=0;exportvectorI=0;
){P....

### mspace

```vex
forpoints(P){vectornpos=mspace(P) -mattrib("rest",P);nval+=noise(npos);}
```

Signature: forpoints(P){vectornpos=mspace(P) -mattrib("rest",P);nval+=noise(npos);}

Adds an item to an array or string.

Returns the indices of a sorted version of an array.

Efficiently creates a....

### pnoise

```vex
clr=pnoise(X*4,Y*5,_4,5_)
```

Signature: clr=pnoise(X*4,Y*5,_4,5_)

Adds an item to an array or string.

Returns the indices of a sorted version of an array.

Efficiently creates an array from its arguments.

### TASK: classify_wrangle

```vex
@P += curlnoise(@P * ch("freq")) * ch("amp");
```

**Purpose:** Determine the execution context of VEX code.

**Input Schema:**

**Output Schema:**

**Decision Rules:**
1.

## Advanced (11 examples)

### Make this rotation thing do what we want â

```vex
vector axis;
 axis = chv('axis');
 axis = normalize(axis);
 @a = noise(@P+@Time);
 axis *= trunc(@a*4)*$PI/2;

 @orient = quaternion(axis);
```

So clearly its not broken, but its not quite behaving as it should.

### Quaternion Rotation from Noise

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@ptnum);
@a = fit(@a, 0, 1, 0, 1);
axis *= trunc(@a*5)*$PI/2;

@orient = quaternion(axis);
```

Creates quaternion-based rotations by generating noise per point, fitting it to a range, then quantizing it to discrete rotation angles (multiples of PI/2).

### Quaternion Orientation from Axis

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P * @Time);
@a = chramp('noise_rearrange', @a);
axis *= trunc(@a * 8) * $PI / 2;
@P.y = @a;

// ...
```

Creates point orientation using quaternions derived from noise-driven axis rotation and time-based up vector animation.

### Quaternion wobble with curl noise

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@0), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
// ...
```

Declares a wobble quaternion variable and initializes it using curl noise applied to a Z-axis vector.

### Quaternion Wobble with Curl Noise

```vex
vector N, up;
vector4 orient, extract, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extract = quaternion(radians(@Frame), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
// ...
```

Creates a wobble rotation using curl noise driven by position and time, then multiplies it into the existing orientation quaternion chain.

### Quaternion Wobble with Curl Noise

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(v@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin(chf("time")*2), {0,1,0});
// ...
```

Creates a compound orientation using multiple quaternion rotations: a base orientation from normalized position, a 90-degree X-axis rotation, an animated sine-based headshake on Y-axis, and a posit....

### Layered Quaternion Rotations

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = maketransform(N, up);
extrarot = quaternion(radians(@Frame), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time*chf("freq"))*3), {0,1,0});
// ...
```

Demonstrates building complex rotations by layering multiple quaternions through qmultiply.

### Quaternion Composition for Complex Orientations

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = maketransform(N, up);
extrarot = quaternion(radians(@N), {1,0,0});
headshake = quaternion(radians(2*@P.y + sin(@TimeInc+@ptnum)*3), {0,1,0});
// ...
```

Demonstrates building complex orientations by composing multiple quaternions together using qmultiply.

### Converting Orient to N and Up Vectors

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
@N = (0,1,0);
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N), (1,0,0));
headshake = quaternion(radians(20) * sin((@TimeInc*chs("speed"))*3), (0,1,0));
// ...
```

Converts a quaternion orientation back into N and up vector attributes by converting the quaternion to a matrix3, then multiplying basis vectors by that matrix.

### Per-Point Time Offset for Quaternion Animation

```vex
vector h, up;
vector4 extrarot, headshake, wobble;

h = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(h, up));
extrarot = quaternion(radians(@N.x), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time + @ptnum) * chv("us") * 3), {0,1,0});
// ...
```

Demonstrates using point number (@ptnum) as a per-point time offset to create varied animation timing across copied instances.

### Converting Quaternion to Normal Vectors

```vex
H = normalize(@P);
N = {0,1,0};
@orient = quaternion(maketransform(N, up));
@xtrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin(@TimeInc*chf("mus")*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P*@Time*0.2));

@orient = qmultiply(@orient, @xtrarot);
// ...
```

Converts a quaternion orientation to normal and up vectors by first converting the quaternion to a matrix3 using qconvert(), then multiplying basis vectors by that matrix.
