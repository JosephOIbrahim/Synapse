# VEX Corpus: Channel References

> 169 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Beginner (13 examples)

### Normal Displacement with Channels

```vex
@P += @N * ch('push');
```

Displacing points along their normals automatically updates the normal vectors when smooth shading is applied.

### Vector Addition Basics

```vex
vector a = chv('a');
vector b = chv('b');
@P = a+b;
```

Demonstrates basic vector addition by creating two vector parameters and adding them together to set the point position.

### Vector Addition Basics

```vex
vector a = chv('a');
vector b = chv('b');
@N = a + b;
```

Demonstrates basic vector addition by creating two vector parameters and adding them together, storing the result in the normal attribute.

### Vector Addition Basics

```vex
vector a = chv('a');
vector b = chv('b');
@P = a + b;
```

Demonstrates basic vector addition by reading two vector parameters from channel references and setting the point position to their sum.

### Adding Vector to Position

```vex
vector a = chv('a');
@P += a;
```

Reads a vector parameter from a UI channel and adds it to the point position.

### Setting Normals with Channel Reference

```vex
@N = chf('scale');
```

Sets the normal vector (@N) to a uniform scalar value controlled by a channel parameter named 'scale'.

### Scaling Normals with Channel Reference

```vex
@N *= ch('scale');
```

Multiplies the normal vector by a channel parameter named 'scale', allowing interactive control over normal magnitude for effects like explosions or directional displacement.

### Scaling Normals with Channel

```vex
v@N * ch('scale');
```

Multiplies the normal vector by a channel parameter value, demonstrating vector multiplication with scalar values from channel references.

### Multiplication with Channel Reference

```vex
@P *= ch('scale');
```

Multiplies the position of each point by a channel parameter named 'scale', effectively scaling the geometry uniformly.

### Vector Scaling with Parameters

```vex
*= ch('scale');
```

Uses the compound assignment operator to scale a vector attribute by a channel parameter value.

### Vector-Vector Multiplication with chv()

```vex
@N *= chv('scalevec');
```

Demonstrates multiplying a normal vector by a vector channel parameter using chv().

### Setting pscale from channel

```vex
@pscale = ch('pscale');
```

Sets the pscale attribute for each point by reading a parameter value from a channel reference.

### Adding Vector to Normal

```vex
vector a = chv('a');
@N += a;
```

Creates a vector variable from a vector channel parameter, then adds that vector to the point normal attribute using the compound assignment operator.

## Intermediate (147 examples)

### Create UI controls â

```vex
@Cd.r = sin( @P.x *  5  );
```

Say you have this:

But you want to change 5 to another number.

### Example: Wave deformer â

```vex
@d = length(@P);
```

A classic.

### Attributes vs variables â

```vex
float foo;
vector bar = {0,0,0};
matrix m;

foo = 8;
bar.x += foo;
```

The examples given above all use the @ syntax to get and set attributes on points.

### Generate a disk of vectors perpendicular to a vector â

```vex
vector aim;
vector4 q;

aim = chv('aim');
@N = sample_circle_edge_uniform(rand(@ptnum));
q = dihedral({0,0,1}, aim);
@N = qrotate(q,@N);
@N *= ch('scale');
```

Download scene: Download file: disk_around_vector.hip

My first H16 demo scene, hooray!

Using another of the super handy sample_something_something functions, sample_circle_edge_uniform generates ....

### Distance â

```vex
float d = distance(@P, {1,0,3} );
 d *= ch('scale');
 @Cd = (sin(d)+1)*0.5;
```

Related to length is distance .

### Minpos â

```vex
vector pos = minpos(1,@P);
 float d = distance(@P, pos);
 d *= ch('scale');
 @Cd = 0;
 @Cd.r = sin(d);
```

You might have used the ray sop before, minpos is the vex equivalent of that; give it a position, and some geometry, it will return the closest position on the surface of that geometry.

### Dot product â

```vex
@Cd = @N.y;
```

Switch to a more complex model now, like tommy, make sure his textures are disabled and 'show uv texture' in the viewport is disabled so we're not distracted by those.

That looks like he's lit fro....

### Vector addition â

```vex
vector a = chv('a');
vector b = chv('b');
@N = a+b;
```

The maths textbook definition of adding vectors is to lie the vectors tip-to-tail, then draw a new vector from the start of the first to the end of the last.

### Vector multiplication â

```vex
@N *= ch('scale');
```

Multiplying a vector by a single number just multiplies each number inside the vector by the single number.

### Distance-based color patterns with center control

```vex
float d = length(@P) * ch('scale');
@Cd = (sin(d)+1)*0.5;

@Cd = (sin(length(@P) * ch('scale'))+1)*0.5;

float d = distance(@P, {1,0,1});
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
// ...
```

Progression from using length() to measure distance from origin to using distance() function to measure from arbitrary points in space.

### Vector scaling in distance calculations

```vex
vector center = chv('center');
float d = distance(@P * {0.5,1,1}, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

// Alternative versions:
// float d = distance(@P, {1,0,1});
// d *= ch('scale');
// ...
```

Demonstrates multiplying the position vector by another vector to scale individual components before computing distance.

### Using fit() with sin() for animation

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(d);

vector pos = @P * chv('fancyscale');
vector center = chv('center');
// ...
```

Demonstrates the progression of using fit() to remap values, starting with incomplete fit() calls, then properly using fit() to remap sin(d) from its natural range of -1 to 1 into the 0 to 1 range ....

### Animating patterns with @Time

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);

// Animated version:
vector pos = @P * chv('fancyscale');
// ...
```

Demonstrates animating a radial sine wave pattern by adding the @Time attribute to the distance calculation.

### Using fit() with animation

```vex
vector pos = @P * chv("fancyscale");
vector center = chv("center");
float d = distance(pos, center);
d *= ch("scale");
@Cd = fit(sin(d), -1, 1, 0, 1);

// Animated version
vector pos = @P * chv("fancyscale");
// ...
```

Demonstrates using the fit() function to map sine wave patterns to color values, creating radial color gradients from a center point.

### VEX Code Style Conventions

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = ch('scale');
@Cd = fit(sin(d*@Time), -1, 1, 0, 1);

foo = foo * 5;
foo *= 5;
// ...
```

Demonstrates different VEX code style conventions and operator shorthand syntax.

### Channel References and Art Directability

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = ch('scale');
@Cd = fit(sin(d*@Frame), -1, 1, 0, 1);

foo *= 5;

// ...
```

Demonstrates using channel references (ch() and chv()) to create art-directable VEX effects by exposing parameters that can be animated or adjusted interactively.

### Code Style and Mathematical Operations

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);

foo -= 5;
foo *= 5;
// ...
```

Demonstrates VEX code styling conventions and compound assignment operators for building complex mathematical expressions.

### Multi-line Code Organization

```vex
float foo = 1;

vector pos = set(0, sin(@Time), 0);
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d * chf('time')), -1, 1, 0, 1);

// ...
```

Breaking complex calculations into multiple lines with descriptive comments makes code easier to understand and debug.

### Position and Normal Manipulation

```vex
vector pos = v@P * exp(-length(v@P));
vector center = chv("center");
float radius = ch("radius");
v@P = set(pos.x, pos.y, pos.z);
@Cd = fit(length(pos), -3, 3, 0, 1);

float d = length(@P);
d *= ch('y_scale');
// ...
```

Demonstrates multiple position manipulation techniques including exponential decay based on distance from origin, color assignment using fitted length values, sinusoidal wave displacement along Y-a....

### Normal Updates After Displacement

```vex
float d = length(@P);
d *= ch("v_scale");
@P.y = sin(d);

@P += @N * ch("push");
```

Demonstrates displacing geometry along normals using a sine wave pattern based on distance from origin.

### Normal-based displacement

```vex
float d = length(@P);
d *= ch('N_scale');
d *= @Frame;
@P.y = sin(d);

@P += @N * ch('push');
```

This code demonstrates the difference between non-directional displacement (modifying only @P.y based on distance from origin) and proper normal-based displacement using @N.

### Animated Normal Displacement

```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N*sin(d);
```

Creates an animated wave displacement by calculating distance from origin, scaling it with a channel parameter, adding time for animation, and offsetting points along their normals using a sine wave.

### Animated Wave Displacement with Controls

```vex
float d = length(@P);
d *= ch('x_scale');
d += @Frame;
@P += @N * sin(d) * ch('wave_height');
```

Creates an animated wave displacement effect by calculating distance from origin, scaling it with a channel parameter, adding frame number for animation, and displacing points along their normals u....

### Animated Wave Displacement

```vex
float d = length(@P);
d *= ch("v_scale");
d += @Frame;
@P = @P * sin(d) * ch("wave_height");
```

Creates an animated radial wave displacement by calculating distance from origin, scaling it with parameters, adding frame-based animation, and applying a sine function modulated by wave height.

### Animated Wave Deformation

```vex
float d = length(@P);
d *= ch("y_scale");
d += @Time;
@P += @N*sin(d)*ch("wave_height");
```

Creates an animated wave deformation by calculating distance from origin, scaling it with a channel parameter, adding time for animation, and displacing points along their normals using a sine wave....

### Fit function with channel parameters

```vex
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
float outMin = ch('fit_out_min');
float outMax = ch('fit_out_max');
float d = fit(d, imin, imax, outMin, outMax);
@P.y = d;
```

Uses the fit() function to remap a value 'd' from one range to another, with input and output ranges controlled by channel parameters.

### Ramp Parameter with Distance

```vex
float d = length(v@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
```

This code calculates the distance from the origin using length(), scales it with a channel parameter, and then uses that scaled distance to sample a ramp parameter called 'myramp' which drives the ....

### Ramp-Based Height Displacement

```vex
float d = length(v@P);
@P.y = chramp('myramp', d);
```

Calculates the distance from the origin for each point and uses that distance to sample a ramp parameter named 'myramp', applying the result to the point's Y position.

### Animated Radial Wave Pattern

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Creates an animated radial wave pattern by calculating distance from origin, scaling and offsetting by time, using modulo to create repeating rings, then applying a ramp to control vertical displac....

### Stepped Ramp Channel Sampling

```vex
d = ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

Demonstrates using a stepped ramp parameter to create striated or quantized values for geometry displacement.

### Dot Product Basics

```vex
@Cd = @N.y;

@Cd = @N.y;

@Cd = dot(@N, {0,1,0});

@Cd = dot(@N, chv('angle'));
```

Demonstrates multiple ways to calculate the dot product between a normal vector and an up vector (0,1,0).

### Dot Product with Vectors and Channels

```vex
@Cd = dot(@N, {0,1,0});

@Cd = @N.y;

@Cd = dot(@N, {0,1,0});

@Cd = dot(@N, chv('angle'));

// ...
```

Demonstrates multiple approaches to computing dot products for lighting effects, starting with explicit vectors, then using component access, progressing to channel-driven vectors with chv(), and f....

### Dot Product Direction Comparison

```vex
@Cd = dot(@N, chv('angle'));

@Cd = dot(@N, (0,1,0));

@Cd = dot(@N, chv('angle'));

vector pos = point(1,"P",0);
@Cd = dot(@N, pos);
// ...
```

Demonstrates using dot product to compare normal direction against various reference vectors, including channel parameter vectors, hardcoded directions like (0,1,0), and point positions from other ....

### Dot Product with Point Reference

```vex
vector pos = point(1, 'P', 0);
@Cd = dot(@N, pos);

vector pos = point(1, 'P', 0);
@Cd = dot(@N, normalize(pos));

@Cd = dot(@N, chv('angle'));

// ...
```

Demonstrates using the point() function to read a position from a different input and calculate dot product with normals.

### Reading Point Position from Second Input

```vex
vector pos = point(1, "P", @ptnum);
@Cd = dot(chv("angle"), pos);
```

Reads the position of a point from the second input using the point() function, then uses a dot product between a channel vector parameter and that position to drive color.

### Vector Addition Basics

```vex
vector a = chv('a');
vector b = chv('b');
@N = a+b;

vector a = chv('a');
@N += a;

vector a = point(0,'P',@ptnum);
// ...
```

Demonstrates basic vector addition using channel references and the tip-to-tail method.

### Vector Addition Basics

```vex
vector a = chv('a');
@i += a;

vector b = point(0, "P", 0);
vector c = point(1, "P", 0);
```

Demonstrates basic vector addition by adding a channel vector parameter to an attribute.

### Vector Addition Basics

```vex
vector a = chv('a');
@P += a;

vector a = point(0, "P", @ptnum);
vector b = point(1, "P", @ptnum);
```

Demonstrates basic vector addition by adding a channel-referenced vector to point positions.

### Channel References and Point Queries

```vex
vector a = chv('a');
@i += a;

vector b = point(0,'P',0);
vector c = point(1,'P',0);
```

Demonstrates reading a vector channel parameter using chv() and adding it to a custom attribute @i.

### Vector Channel Parameters and Point Access

```vex
vector a = chv('a');
@N += a;

vector b = point(0, "P", 0);
vector c = point(1, "P", 0);
```

Demonstrates creating a vector channel parameter using chv() to add to normal attributes, and shows how to access point positions from different inputs using the point() function.

### Vector Subtraction Between Points

```vex
vector a = chv('A');
@N += a;

vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@N = b - a;

// ...
```

Demonstrates vector subtraction by reading positions from two different point sources using the point() function.

### Directional velocity from origin point

```vex
@v *= ch("scale");

@v = -@N;
@v *= ch("scale");

vector origin = point(1, 'P', 0);
@v = @P - origin;
@v *= ch("scale");
```

Sets velocity vectors radiating outward from an origin point by computing the direction from the origin to each point position.

### Vector Scaling and Direction

```vex
vector a = @P;
vector b = point(1, @ptnum, "P");

@N = b - a;

@N *= chv('scalevec');

vector origin = point(1, 'P', 0);
// ...
```

Calculates a vector from current point to a corresponding point in second input, then scales it by a channel vector parameter.

### Multiplying Normals by Vector

```vex
@N *= chv('scale_vec');
```

Multiplies the normal vector by a vector channel parameter to scale and flip normals non-uniformly.

### Normalized Bounding Box Deformation

```vex
vector bbox = relpointbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
// ...
```

Uses relpointbbox() to get normalized bounding box coordinates (0-1 range) for each point's position, then applies deformation along the normal based on the Y-axis bbox value.

### Relative Bounding Box Inflation

```vex
vector bbox = relbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```

Uses relbbox() to get normalized position within bounding box (0-1 space), then samples a ramp parameter based on the Y component to drive a displacement along normals.

### Setting Point Scale via Channel

```vex
@pscale = ch("pscale");
```

Sets the pscale attribute (which controls instance size in Copy to Points) by reading a channel parameter value.

### Using @scale for non-uniform scaling

```vex
d = chf('frequency');
d += @Time;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));

// Different ways to set @scale vector:
@scale = {1, 5, 2.5};

@scale.x = 1;
// ...
```

The @scale attribute allows non-uniform scaling on all three axes, unlike @pscale which scales uniformly.

### Color and Scale from Distance Ramp

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = chramp('ramp', @id);
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(d, min, max, 0, 1);
// ...
```

Calculates distance from origin, modulates it with frequency and ramp values, then uses fitted distance to drive both point scale and color through separate ramps.

### Packed Geometry with Scale and Color

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = fit01(v@pred);
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(d, min, max, 0, 1);
// ...
```

Creates packed geometry instances with non-uniform scaling based on distance from origin and a predecessor attribute.

### Animated scaling with ground plane offset

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Frame * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Demonstrates animating copy-to-points geometry with sine wave-driven scaling while offsetting the Y position by half the calculated distance to anchor objects to the ground plane.

### Color Ramp from Distance

```vex
vector @P, @Cd;
float @pscale, @N;
float min, max, d, t;

min = ch("min");
max = ch("max");
t = ch("speed");
d = length(@P);
// ...
```

Remaps a distance value from min/max range to 0-1 range to properly sample a color ramp parameter.

### Color ramp vector casting

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(d, -1, 1, min, max);
// ...
```

Demonstrates animating geometry scale and applying color based on point distance from origin.

### Color Ramp with Animated Scale

```vex
vector chramp(string colorMap, float input);

float min, max, d, t;
min = ch("min");
max = ch("max");
t = chf("speed");
d = length(@P);
d *= ch('frequency');
// ...
```

Creates an animated ripple effect by calculating distance-based sine waves and using them to drive both scale and color via a color ramp.

### Color Ramp Vector Casting

```vex
d = ch('frequency');
d = t;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using vector() casting on chramp() to convert a color ramp parameter into RGB values for @Cd attribute.

### Vector Cast for Color Ramps

```vex
d = chf('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using vector() to cast a chramp() result into a color attribute.

### Color Ramp with Vector Cast

```vex
d = chf('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(d, min, max, d);
@P.y += d.z;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates applying a color ramp to geometry using vector casting.

### Color Ramp with Vector Cast

```vex
d = ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Applies color to geometry using a color ramp parameter by casting chramp() result to a vector with the vector() function.

### Color Ramp with Vector Cast

```vex
d = chf('frequency');
d = fit01(d, -1, 1, min, max);
@scale = vector(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Maps a frequency parameter through fit01 and fit functions to create scaled geometry and applies color using a color ramp.

### Color Ramp from Fit Values

```vex
d = chf('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, 0);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using fit() to normalize a value range (min to max) into the 0-1 range needed for color ramp sampling.

### Color Ramp with Vector Cast

```vex
float d = chf('frequency');
float min = chf('min');
float max = chf('max');

d = fit(sin(d), -1, 1, min, max);
@scale = fit(d, min, max, 0, 1);
@P.y += d/2;

// ...
```

Applies a color ramp to geometry by using a vector cast on chramp() to convert a float ramp parameter into color values.

### Color Ramp with Vector Cast

```vex
d = chf('frequency');
d += fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), min, max, 0, 1);

d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

This code demonstrates using chramp() with a vector cast to create color ramping.

### Color Ramp with Vector Cast

```vex
d = chf('frequency');
d += [];
d = fit01(d, min, max);
@scale = fit(d, min, max, 0, 1);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using vector() cast with chramp() to convert a color ramp parameter into a vector for the @Cd attribute.

### Color Ramp with Vector Cast

```vex
d = ch('frequency');
d += @P.z;
d = fit01(d, -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d.z;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));

// ...
```

Demonstrates using vector() to cast chramp() output into a color ramp instead of a float spline.

### Color Ramps with Normalized Values

```vex
d = ch('frequency');
d = f;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0.0, 1.0);
@Cd = vector(chramp('color', d));
```

Demonstrates using double fit() calls to map values: first fitting a sine wave to min/max range for scale operations, then fitting back to 0-1 range to drive a color ramp.

### Remapping Values for Color Ramps

```vex
d = ch('frequency');
d = {};
d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), min, max, 0, 1);
@P.y -= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Uses two fit() operations to first map a sine wave to a custom min/max range for scaling purposes, then remaps the same value back to 0-1 range to drive a color ramp.

### Fit and Color Ramp Mapping

```vex
d = ch('frequency');
d += f;
f = fit(sin(d), -1, 1, min, max);
@scale = set(@Cd.x, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Uses two fit operations to remap values: first fitting a sine wave to a custom min/max range for scale calculations, then fitting those values back to 0-1 range to drive a color ramp.

### Remapping Values for Color Ramp

```vex
d = ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d/3;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

This code demonstrates a double-fit technique to first map a sine wave to a custom min/max range for scale and position, then remap those values back to 0-1 range to drive a color ramp.

### Remapping values to drive color ramp

```vex
d = chf('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

This code demonstrates using multiple fit() operations to remap values through different ranges.

### Color ramp from scale values

```vex
d = chf('frequency');
d += fit;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(@id, min, max, d);
@P.y -= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates remapping scale values to drive a color ramp parameter.

### Color Ramp from Scale Values

```vex
d = ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
@P.y -= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates mapping animated scale values to drive a color ramp by fitting the computed scale value from its min/max range to 0-1, then using chramp() to sample colors.

### Fit and Color Ramp Adjustments

```vex
vector4 col = {1,0,0,0,1};
i@cd = fit(@N, -1, 1, min, max);
@P.y = fit(@P.y, min, 0);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp("cr", d));
```

Demonstrates using fit() to remap values from normals and positions, combined with chramp() to apply color ramp lookups.

### Copy to Points Attribute Adjustment

```vex
float min, max, d, f;
min = ch('min');
max = ch('max');
f = @Time * ch('frequency');
d = length(@P);
d *= ch('frequency');
min = fit(sin(d), -1, 1, min, max);
@scale = set(min, min, d);
// ...
```

Adjusts point attributes (scale, position, color) based on distance from origin for use with Copy to Points.

### Quaternion Orientation Variations

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @Time*ch('offset');
angle *= @Time*ch('speed');

axis = chv('axis');
// ...
```

Three variations of quaternion-based orientation transformations demonstrating different approaches: the first uses @Time for both offset and speed, the second uses @ptnum for offset to vary per po....

### Remapping Noise with Fit and Ramp

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+@Time);
axis *= trunc(@a*4)*PI/2;

@orient = quaternion(axis);

// ...
```

Demonstrates three approaches to using noise for quaternion rotation: first storing raw noise in an @a attribute, then using fit() to remap the noise range from 0.4-0.6 to 0-1 for better distributi....

### VEX Comment Syntax Behavior

```vex
// Example showing VEX comment behavior
// Code context appears to be demonstrating that comments can be nested
// and how control+/ (comment toggle) behaves with existing comments

vector axis;
axis = chv('axis');
axis = normalize(axis);
@N = noise(@P * chf('freq'));
// ...
```

Demonstrates VEX comment syntax behavior when using keyboard shortcuts like Ctrl+/ to toggle comments.

### primuv function introduction

```vex
vector up = chv('up');

@P = primuv(0, "N", @ptnum, u);
```

Introduces the primuv() function which samples an attribute value from a primitive surface at a given parametric UV coordinate.

### Sample Position and Normal with primuv

```vex
vector uv = chv('uv');

@P = primuv(0, 'P', @ptnum, uv);
@N = primuv(1, 'N', @ptnum, uv);
```

This code samples position and normal attributes from primitives using UV coordinates.

### Sampling Surface Attributes with primuvfs

```vex
vector uv = chv('uv');

v@g0 = primuvfs(1, 'P', 0, uv);
v@g1 = primuvfs(1, 'N', 0, uv);
```

Uses primuvfs() to sample position and normal attributes at a specific UV coordinate on a primitive surface.

### Surface Sampling with primuv

```vex
vector uv = chv('uv');

@P = primuv(1, "P", 0, uv);
@N = primuv(1, "N", 0, uv);
```

Uses primuv() to sample position and normal attributes from a primitive surface at a given UV coordinate.

### Primitive UV Sampling Setup

```vex
vector uv = chv('uv');

vector gx = primmuv(1, 'P', u, uv.x);
vector gy = primmuv(1, 'P', u, uv.y);
```

Setting up a vector parameter to control UV coordinates, then sampling the position attribute from a second input geometry at two different UV locations (x and y components).

### Sampling Attributes with primuv

```vex
vector uv = chv('uv');

@P = primuv(1, 'P', @v, uv);
@N = primuv(1, 'N', @v, uv);
```

Uses primuv() to sample position and normal attributes from a second input geometry at specific UV coordinates.

### Sampling Geometry with primuv

```vex
vector uv = chv('uv');

@P = primuv(1, 'P', @u, @v);
@N = primuv(1, 'N', @u, @v);
```

Uses primuv() to sample position and normal attributes from a second input geometry based on UV coordinates.

### UV-based Position Lookup

```vex
vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
```

Uses a channel parameter to define a UV coordinate, then looks up the position attribute at that UV location on primitive 0 of the first input geometry.

### primuv sampling position and normal

```vex
vector uv = chv('uv');

@P = primuv(1, "P", v, uv);
@N = primuv(1, "N", v, uv);
```

Uses primuv() to sample both position and normal attributes from a primitive at UV coordinates specified by a channel parameter.

### Sampling UV Position and Normal

```vex
vector uv = chv('uv');

vector gx = primuv(1, 'P', 0, uv);
vector gN = primuv(1, 'N', 1, uv);
```

Retrieves a UV coordinate from a channel parameter and uses it to sample both position (P) and normal (N) attributes from a grid primitive.

### UV primitive attribute sampling

```vex
vector uv = chv('uv');

v@P = primuv(1, 'P', 0, uv);
v@N = primuv(1, 'N', 0, uv);
```

Uses primuv() to sample position and normal attributes from a primitive on input 1 at UV coordinates specified by a channel parameter.

### UV Parameter Sampling with primuv

```vex
vector uv = chv('uv');

@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```

Samples position and normal from a primitive surface using UV coordinates stored in a channel parameter.

### Sampling Position and Normal with primuv

```vex
vector uv = chv('uv');

@P = primuv(0, '', 'P', 0, uv);
@N = primuv(0, '', 'N', 0, uv);
```

Uses primuv() to sample both position and normal attributes from a primitive using UV coordinates.

### primuv for UV lookup

```vex
vector uv = chv('uv');

@P = primuv(1, 'P', @ptnum, uv);
@N = primuv(1, 'N', 0, uv);
```

Uses primuv() to sample position and normal attributes from the second input geometry at UV coordinates.

### Sampling Primitive Attributes with primuv

```vex
vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```

Uses primuv() to sample position and normal attributes from primitive 0 of the second input geometry at a UV coordinate specified by a channel parameter.

### Primitive UV Attribute Sampling

```vex
vector uv = chv('uv');
@P = primav(1, 'P', 0, uv);
@N = primav(1, 'N', 0, uv);
```

Uses primav() to sample position and normal attributes from a primitive at specified UV coordinates.

### Point Cloud Color Query

```vex
v@P, @P, ch('dist'), 'Cd');
```

Incomplete snippet showing parameters for a point cloud query function to retrieve color (Cd) attribute.

### Animated Wave Displacement

```vex
float d = length(@P);
d *= ch('v_scale');
d += @Frame;
@P += @N * sin(d) * ch('wave_height');
```

Creates an animated wave effect by calculating distance from origin, scaling and animating it with @Frame, then displacing points along their normals using sine function.

### Animated Wave with Sine Function

```vex
float d = length(@P);
d *= ch("v_scale");
d += @Time;
@P = @N * sin(d) * ch("wave_height");
```

Creates an animated wave effect by calculating distance from origin, scaling and offsetting by time, then displacing points along their normals using a sine function.

### Animated Wave Deformation with Channels

```vex
float d = length(@P);
d += @Time;
@P.y = @P.y * sin(d) * ch("wave_height");
```

Creates an animated wave deformation by calculating distance from origin, adding time offset, and modulating the Y position with a sine function scaled by a channel parameter.

### Fit Function with Channel Parameters

```vex
float angle = ch('fit_in_min');
float imagex = ch('fit_in_max');
float imagey = ch('fit_out_min');
float outmin = ch('fit_out_max');
float outmax = outmin;
@P.x = fit(angle, imagex, imagey, outmin, outmax);
@P.y = angle;
```

This code demonstrates using the fit() function with channel references to remap values from one range to another, setting the X position based on the remapped value and Y position to the original ....

### Ramp-Driven Position Deformation

```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('my-ramp', d);
```

This code calculates the distance of each point from the origin, scales it by a channel parameter, and uses that scaled distance to sample a ramp parameter which drives the Y position of points.

### Ramp Lookup with Distance Scaling

```vex
float d = length(@P);
d *= ch("scale");
@P.y = chramp("myRamp", d);
@P.y *= ch("height");
```

Calculates point distance from origin and uses it as a lookup value into a ramp parameter, scaled by a channel slider.

### Animated ramp displacement with time

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Creates an animated wave pattern by calculating distance from origin, scaling it with a channel parameter, offsetting by time, then using a ramp lookup to drive Y position displacement.

### Animated Ramp Displacement with Time

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('myramp', d);
@Cd = ch('height');
```

Creates an animated wave-like displacement by calculating distance from origin, scaling it, subtracting time for animation, and using the result to look up Y displacement values from a ramp parameter.

### Animated ramp-driven displacement

```vex
float d = length(@P);
d *= ch('scale');
d = d % 1;
@Cd = chramp('my-ramp', d);
@P.y = ch('height');
```

Creates an animated radial displacement pattern by calculating distance from origin, scaling it with a parameter, using modulo to create repeating bands, and applying a color ramp that also drives ....

### Animating Ramp with Time

```vex
float d = length(@P);
d *= ch('scale');
d *= @Time;
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Animates point positions vertically using a color ramp driven by both distance from origin and time.

### Ramp-Based Height Displacement

```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

This code displaces point height based on distance from origin using a ramp for shape control.

### Animated Color Ramp Using Point Number

```vex
float d = length(@P);
d *= ch('scale');
d = @ptnum;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp('myramp', d);
@Cd.y *= ch('height');
```

This code creates an animated color pattern by converting point numbers into a sine wave, then remapping the oscillating values through a color ramp to control the green channel of point colors.

### Sine Wave Height with Ramp

```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d += 0.5;
@Cy = chramp("myramp", d);
@Cy *= ch("height");
```

Calculates distance from origin, scales and applies sine function to create a wave pattern, then uses that pattern to sample a color ramp for the Y-component of point color, with an additional heig....

### Shaping Sine Waves with Ramps

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp('myRamp', d);
@Cd *= ch('height');
```

This technique creates animated sine wave patterns and uses a color ramp to shape and map the wave values to color.

### Ramp and Channel Parameter Control

```vex
f@y = chramp('mymap', @P.x);
@P.y *= ch('height');
```

Uses a ramp parameter to remap position values and a channel parameter to control height multiplication.

### Custom Ramp Function

```vex
vector ramp(float d){
    d *= ch('scale');
    d = fit(d, -1, 1, 0, 1);
    @P.y = chramp('myramp', d);
    @P.y *= ch('height');
}
```

Defines a custom function that processes a distance value through scaling, remapping, and a color ramp lookup to control point height.

### Animated Height Displacement with Ramps

```vex
float d = length(@P);
d *= ch('scale');
d += ch('time');
d %= 1;
@P.y = chramp('mycamp', d);
@P.y *= ch('height');
```

Creates animated vertical displacement by using distance from origin as a lookup into a color ramp parameter.

### Animated Color Ramp with Height

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp('height', d);
@P.y *= ch('height');
```

Creates an animated radial pattern by calculating distance from origin, applying sine wave with time offset, and mapping to a color ramp.

### Distance-Based Color Ramp with Height

```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
@Cd = d;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
d = chramp('my-ramp', d);
@P.y *= ch('height');
```

This code calculates distance from origin, applies modulo for repeating patterns, and uses sine wave transformation with a ramp parameter to drive color values.

### Radial Sine Wave with Ramp

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d,-1,1,0,1);
@P.y = chramp('myRamp',d);
@P.y *= ch('height');
```

Creates a radial sine wave pattern that displaces points vertically based on their distance from origin.

### Quantizing Data with Truncate

```vex
float d = length(@P);
float f = ch('scale');
d /= f;
d = trunc(d);
d *= f;
@P.y = d;
```

Demonstrates quantizing or stepping data by scaling values down, truncating to remove decimal portions, then scaling back up.

### Stepped Ramp Using Truncation

```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
d *= f;
@P.y = d;

// ...
```

Creates stepped values by dividing the distance from origin by a factor, truncating to remove decimals, then multiplying back by the factor to create quantized steps.

### Channel References for Attributes

```vex
@P = chs("input1_P");
@Cd = chv("input1_Cd");
```

Demonstrates using channel references (chs and chv) to read point position and color attributes from another node via UI parameters.

### Channel Reference Scale Vector

```vex
chv('scalevec');
```

Demonstrates using the chv() function to reference a vector channel parameter named 'scalevec'.

### Smooth deformation with fit

```vex
v = fit(d, 0, ch("radius"), 1, 0);
@P.y += v;
```

Uses fit() to create a smooth falloff value v based on distance d, then displaces points vertically by adding v to the Y component of position.

### Array Iteration with For Loop

```vex
int pts[];
int pt;
pts = inpointgroup(0, 'ring', pt);
for(int i=0; i<len(pts); i++){
    pt = pts[i];
    pts = pointneighbors(0, pt);
    vector pos = point(0, 'P', pt);
    float s = distance(@P, pos);
// ...
```

Iterates through points in a group using a for loop, accessing array elements with an index variable.

### Removing Primitives with Points

```vex
removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

// ...
```

The removeprim() function deletes primitives from geometry, with the third argument controlling whether associated points are kept (1) or deleted (0).

### Animated scale and color for instancing

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(d, 0, 1, min, max);
// ...
```

Creates animated scale and color attributes on grid points for copy-to-points instancing.

### Animated scale with color and position

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= 2 * ch('frequency');
d -= t;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Creates an animated radial wave pattern that modulates point scale, vertical position, and color using time-based sinusoidal oscillation.

### Color Ramp with Distance Remapping

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = prim * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
@P *= fit(d, -1, 1, min, max);
// ...
```

Remaps a distance attribute from its current range (min/max) back to a normalized 0-1 range for use with a color ramp.

### Color Ramp Vector Casting

```vex
d = ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), -1, 1, min, max);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using vector() to cast a chramp() result into a color value for @Cd.

### Color Ramp with Vector Cast

```vex
d = chf('frequency');
d = f[];
d = fit01(d, min, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using the vector() cast on chramp() to convert a float ramp into a color ramp for the @Cd attribute.

### Color Ramp with Vector Cast

```vex
d = chf('frequency');
d = f;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), min, max, 0, 1);
@P.y -= d/2;
d = fit(@d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Uses vector casting on chramp() to create a color ramp parameter interface instead of a float spline.

### Color Ramp with Vector Casting

```vex
d = ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using double fit() operations to convert scaled animation values back to a 0-1 range for driving a color ramp.

### Remapping Values for Color Ramps

```vex
float f = ch('frequency');
float d = f;
float min = ch('min');
float max = ch('max');

d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, min, d);
@P.y += d/2;
// ...
```

Demonstrates a two-step fit() workflow: first mapping a sine wave to a custom min/max range for geometry scale, then remapping those values back to 0-1 range to properly drive a color ramp.

### Remapping Values for Color Ramps

```vex
d = ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = set(@u * min, max, d);
@P.y += d / 2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

This code demonstrates using dual fit() operations to remap values for different purposes: first fitting a sine wave to min/max for scale and position, then fitting back to 0-1 range to drive a col....

### Color Ramp Mapping with Fit

```vex
d = chf('frequency');
d += f;
d = fit01(d, -1, 1, 0, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using two fit operations to map a value from a custom min/max range to 0-1 for color ramp lookup.

### Remapping Values for Color Ramp

```vex
d = chf('frequency');
d += f;
d = fit01(d, -1, 1);
float min = 0;
float max = 1;
@scale = fit(d, min, max, 0, 1);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
// ...
```

Demonstrates remapping frequency-based values through multiple fit operations to drive both scale attributes and color ramp lookups.

### Remapping values for color ramp

```vex
d = chf('frequency');
d *= f;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(max, max, d);
@P.y *= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

This code takes computed scale values and remaps them to drive a color ramp.

### Color Ramp from Scale Values

```vex
d = ch('frequency');
d *= f;
f = fit01(d, min, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Remaps scale values back into a normalized range to drive a color ramp.

### Color ramp from animated scale

```vex
d = ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(max, max, d);
@P.y -= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

This code animates point scale and color by using a sine wave to drive values.

### Color Ramp from Animated Values

```vex
d = chf('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d*u), max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates converting animated scale values into normalized 0-1 range to drive a color ramp parameter.

### primuv function introduction

```vex
vector uv = chv('uv');

primuv(1, 'P', 0, uv);
primuv(1, 'N', 0, uv);

vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```

The primuv() function samples attribute values from a primitive at a specific UV coordinate.

### error

```vex
if(!pointattribtype(0,chs("nameattrib")) !=2){error("Name attribute %s must be a string attribute!",chs("nameattrib"));return;}if(chf("distance") <0){error("")}floatminimumValue=chf("min");floatmaximumValue=chf("max");if(minimumValue>=maximumValue){error("Minimum (%f) must be strictly less than maximum (%f)!  It's unclear what should be done.",minimumValue,maximumValue);return;}
```

Signature: if(!pointattribtype(0,chs("nameattrib")) !=2){error("Name attribute %s must be a string attribute!",chs("nameattrib"));return;}if(chf("distance") <0){error("")}floatminimumValue=chf("min....

### foreach

```vex
foreach([element_type]value;array){}
```

Signature: foreach([element_type]value;array){}

This loops over the members of ‹array›.

### metamarch

```vex
intindex;vectorp0,p1;// Initialize input valuesindex= -1;p0=Eye;p1=P;result=0;while(metamarch(index,metaball_file,p0,p1,displace_bound)){result+=ray_march(metaball_file,p0,p1);}
```

Signature: intindex;vectorp0,p1;// Initialize input valuesindex= -1;p0=Eye;p1=P;result=0;while(metamarch(index,metaball_file,p0,p1,displace_bound)){result+=ray_march(metaball_file,p0,p1);}

Adds an....

### osd_lookuppatch

```vex
// This function can be used to move points generated by a scatter SOP to the// subdivision limit surface.  The scatter SOP needs to store the "sourceprim"// (the Output Attributes tab).  Texture coordinates also need to be// transferred from the source geometry.voidmovePointToLimitSurface(stringfile;vectorP,uv;intsourceprim){intpatch_id= -1;floatpatch_u,patch_v;if(osd_lookuppatch(file,sourceprim,uv.x,uv.y,patch_id,patch_u,patch_v,"uv")){vectortmpP;if(osd_limitsurface(file,"P",patch_id,patch_u,patch_v,tmpP))P=tmpP;}}
```

Signature: // This function can be used to move points generated by a scatter SOP to the// subdivision limit surface.

### osd_patches

```vex
int[]osd_patches(conststringfile;constface_id){intpatches[] ={};intfirst=osd_firstpatch(file,face_id);if(first>=0){intnpatches=osd_patchcount(file,face_id);for(inti=0;i<npatches;i++)append(patches,first+i);}returnpatches;}
```

Signature: int[]osd_patches(conststringfile;constface_id){intpatches[] ={};intfirst=osd_firstpatch(file,face_id);if(first>=0){intnpatches=osd_patchcount(file,face_id);for(inti=0;i<npatches;i++)appe....

### primfind

```vex
int[]prims=primfind(geometry,{-0.5, -0.5, -0.5},{0.5,0.5,0.5});foreach(intprim;prims){removeprim("primitives.bgeo",prim,1);}
```

Signature: int[]prims=primfind(geometry,{-0.5, -0.5, -0.5},{0.5,0.5,0.5});foreach(intprim;prims){removeprim("primitives.bgeo",prim,1);}

Find all the primitives whose bounding boxes overlap the giv....

### usd_attribtimesamples

```vex
// Get the time codes of a foo attribute.floattime_codes[] =usd_attribtimesamples(0,"/geo/cube","foo");
```

Signature: // Get the time codes of a foo attribute.floattime_codes[] =usd_attribtimesamples(0,"/geo/cube","foo");

When running in the context of a node (such as a wrangle LOP), this argument can ....

### usd_iprimvartimesamples

```vex
// Get primvar values at authored time samples on the given prim or its ancestor.float[]usd_iprimvartimesamplevalues(constintinput;conststringprimpath,primvarname){floatresult[];floattime_samples[] =usd_iprimvartimesamples(input,primpath,primvarname);foreach(floattime_code;time_samples){floatvalue=usd_iprimvar(input,primpath,primvarname,time_code);push(result,value);}returnresult;}
```

When running in the context of a node (such as a wrangle LOP), this argument can be an integer representing the input number (starting at 0) to read the stage from.

### usd_primvartimesamples

```vex
// Get the time codes of a foo primvar.floattime_codes[] =usd_primvartimesamples(0,"/geo/cube","foo");
```

Signature: // Get the time codes of a foo primvar.floattime_codes[] =usd_primvartimesamples(0,"/geo/cube","foo");

When running in the context of a node (such as a wrangle LOP), this argument can b....

### warning

```vex
if(primintrinsic(0,"typeid",@primnum) !=1){warning("Primitives that aren't polygons are being ignored.");return;}if(primintrinsic(0,"closed",@primnum) ==0||@numvtx<3){warning("Open or degenerate polygons are being ignored.");return;}floatminimumValue=chf("min");floatmaximumValue=chf("max");if(minimumValue>maximumValue){warning("Minimum (%f) can't be greater than maximum (%f); replacing minimum with maximum.",minimumValue,maximumValue);minimumValue=maximumValue;}
```

Signature: if(primintrinsic(0,"typeid",@primnum) !=1){warning("Primitives that aren't polygons are being ignored.");return;}if(primintrinsic(0,"closed",@primnum) ==0||@numvtx<3){warning("Open or de....

### Pattern: Gradient Ascent

```vex
// Move uphill on scalar field
float eps = 0.001;
vector grad;
grad.x = point(1, "density", @ptnum) - point(1, "density_x", @ptnum);
grad.y = point(1, "density", @ptnum) - point(1, "density_y", @ptnum);
grad.z = point(1, "density", @ptnum) - point(1, "density_z", @ptnum);
@P += normalize(grad) * ch("step");
```

// Move uphill on scalar field
float eps = 0.001;
vector grad;
grad.x = point(1, "density", @ptnum) - point(1, "density_x", @ptnum);
grad.y = point(1, "density", @ptnum) - point(1, "density_y", @ptnum.

## Advanced (9 examples)

### @scale â

```vex
float min, max, d, t;
 min = ch('min');
 max = ch('max');
 t = @Time * ch('speed');
 d = length(@P);
 d *= ch('frequency');
 d += t;
 d = fit(sin(d),-1,1,min,max);
// ...
```

Ok, so now we'll set the y scale of the boxes from d:

Play with the numbers and.

### Defining orients from other things â

```vex
float angle = ch('angle');
 vector axis = chv('axis');

 @orient = quaternion(angle, axis);
```

That 'no rotation' orient is pretty much the only time you set an orient vector manually.

### Quaternion blending with slerp

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(radians({0,1,0} * $F/2));
@orient = slerp(a, b, ch('blend'));

// Advanced version with ramp:
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
float blend = chramp('blendcap', @ptnum/1);
// ...
```

Uses slerp() to smoothly interpolate between two quaternions (identity and a rotation) based on a blend parameter.

### Quaternion Blending with Slerp

```vex
// Basic slerp between identity and rotation
vector4 a = {0,0,0,1};
vector4 b = quaternion(radians({0,1,0} * $F/2));
@orient = slerp(a, b, ch('blend'));

// Using PI for 90-degree rotation
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * $PI/2);
// ...
```

Demonstrates spherical linear interpolation (slerp) to smoothly blend between two quaternion rotations on the @orient attribute.

### Quaternion Slerp Blending with Time

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * $PI/2);
@orient = slerp(a, b, ch('blend'));

// Using point attribute for angle
vector4 a = {0,0,0,1};
vector4 b = quaternion(@y, {0,1,0} * $PI/2);
@orient = slerp(a, b, ch('blend'));
// ...
```

Demonstrates quaternion spherical interpolation (slerp) to smoothly blend between two orientations.

### Quaternion Slerp with Ramps

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
float blend = chramp('blend_map',@ptnum*1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;
// ...
```

Demonstrates spherical linear interpolation (slerp) between quaternions using ramp parameters for blend control.

### Smooth Quaternion Rotation Interpolation

```vex
vector4 a = {0,0,0,1};
vector4 b = normalize(vector4(0,1,0) * PI/2);
float blend = chramp('blendramp', @Time % 1);
@orient = slerp(a, b, blend);

vector axis;
axis = chv('axis');
axis = normalize(axis);
// ...
```

Demonstrates smooth rotation interpolation using quaternions by blending between two orientations with slerp() based on a time-driven ramp.

### Quaternion Slerp Rotation Animation

```vex
vector4 a = {0,0,0,1};
vector4 b = normalize(quaternion({0,1,0} * PI/2));
float blend = chramp('blendramp', @Time % 1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;
// ...
```

Uses slerp() to smoothly interpolate between quaternion orientations over time, creating animated rotation transitions.

### Converting Quaternion to Normal and Up Vectors

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time*chv("us"))*3), {0,1,0});
// ...
```

Demonstrates converting a quaternion orientation back into explicit normal and up vectors by first converting the quaternion to a 3x3 matrix using qconvert(), then multiplying basis vectors by that....
