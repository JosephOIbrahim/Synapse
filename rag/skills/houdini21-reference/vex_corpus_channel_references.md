# VEX Corpus: Channel References
> 169 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Beginner (13 examples)
### Normal Displacement with Channels
```vex
@P += @N * ch('push');
```
// Normal-based displacement; smooth shading auto-updates normals.
### Vector Addition Basics
```vex
vector a = chv('a');
vector b = chv('b');
@P = a+b;
```
### Vector Addition Basics
```vex
vector a = chv('a');
vector b = chv('b');
@N = a + b;
```
### Vector Addition Basics
```vex
vector a = chv('a');
vector b = chv('b');
@P = a + b;
```
### Adding Vector to Position
```vex
vector a = chv('a');
@P += a;
```
### Setting Normals with Channel Reference
```vex
@N = chf('scale');
```
### Scaling Normals with Channel Reference
```vex
@N *= ch('scale');
```
// Interactive normal scale for explosions or directional displacement.
### Scaling Normals with Channel
```vex
v@N * ch('scale');
```
### Multiplication with Channel Reference
```vex
@P *= ch('scale');
```
### Vector Scaling with Parameters
```vex
*= ch('scale');
```
### Vector-Vector Multiplication with chv()
```vex
@N *= chv('scalevec');
```
### Setting pscale from channel
```vex
@pscale = ch('pscale');
```
### Adding Vector to Normal
```vex
vector a = chv('a');
@N += a;
```
## Intermediate (147 examples)
### Create UI controls â
```vex
@Cd.r = sin( @P.x *  5  );
```
Say you have this:
// Replace magic numbers with ch() to expose UI sliders.
### Example: Wave deformer â
```vex
@d = length(@P);
```
### Attributes vs variables â
```vex
float foo;
vector bar = {0,0,0};
matrix m;
foo = 8;
bar.x += foo;
```
// @ syntax reads/writes point attributes; undecorated variables are local.
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
// sample_circle_edge_uniform + dihedral + qrotate aligns a disk to an aim direction.
### Distance â
```vex
float d = distance(@P, {1,0,3} );
 d *= ch('scale');
 @Cd = (sin(d)+1)*0.5;
```
// distance() from arbitrary point; length() measures from origin.
### Minpos â
```vex
vector pos = minpos(1,@P);
 float d = distance(@P, pos);
 d *= ch('scale');
 @Cd = 0;
 @Cd.r = sin(d);
```
// minpos() returns closest surface point on input geo (VEX equivalent of Ray SOP).
### Dot product â
```vex
@Cd = @N.y;
```
// @N.y gives up-facing value; equivalent to dot(@N, {0,1,0}).
### Vector addition â
```vex
vector a = chv('a');
vector b = chv('b');
@N = a+b;
```
// Tip-to-tail vector addition via chv() parameters.
### Vector multiplication â
```vex
@N *= ch('scale');
```
// Scalar multiplication scales each vector component.
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
// length() from origin, distance() from arbitrary center point.
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
// Non-uniform @P scale before distance() creates elliptical patterns.
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
// fit() remaps sin(d) from -1..1 to 0..1 for color output.
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
// Add @Time to d for animated radial pattern.
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
// Radial color gradient: fit(sin(d), -1, 1, 0, 1).
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
// foo *= 5 is shorthand for foo = foo * 5.
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
// ch()/chv() expose art-directable parameters on the node UI.
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
// Use compound operators: -=, *= for cleaner code.
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
// Split complex calculations into named intermediate variables.
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
// exp(-length(v@P)) creates exponential position decay from origin.
### Normal Updates After Displacement
```vex
float d = length(@P);
d *= ch("v_scale");
@P.y = sin(d);
@P += @N * ch("push");
```
// Sine wave Y displacement then push along @N.
### Normal-based displacement
```vex
float d = length(@P);
d *= ch('N_scale');
d *= @Frame;
@P.y = sin(d);
@P += @N * ch('push');
```
// @Frame multiplies d to create frame-speed animation.
### Animated Normal Displacement
```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N*sin(d);
```
// @Time animates wave; @N*sin(d) displaces along surface normals.
### Animated Wave Displacement with Controls
```vex
float d = length(@P);
d *= ch('x_scale');
d += @Frame;
@P += @N * sin(d) * ch('wave_height');
```
// wave_height channel scales final displacement amplitude.
### Animated Wave Displacement
```vex
float d = length(@P);
d *= ch("v_scale");
d += @Frame;
@P = @P * sin(d) * ch("wave_height");
```
// @P = @P * sin(d) scales position by wave; note: *= would be cleaner.
### Animated Wave Deformation
```vex
float d = length(@P);
d *= ch("y_scale");
d += @Time;
@P += @N*sin(d)*ch("wave_height");
```
// Classic wave deformer pattern: d += @Time animates, @N*sin(d) displaces.
### Fit function with channel parameters
```vex
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
float outMin = ch('fit_out_min');
float outMax = ch('fit_out_max');
float d = fit(d, imin, imax, outMin, outMax);
@P.y = d;
```
// All fit() ranges exposed as ch() parameters for interactive remapping.
### Ramp Parameter with Distance
```vex
float d = length(v@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
```
// Scale d before chramp() lookup to control which part of ramp is sampled.
### Ramp-Based Height Displacement
```vex
float d = length(v@P);
@P.y = chramp('myramp', d);
```
// Direct distance-to-ramp lookup for height displacement.
### Animated Radial Wave Pattern
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
// d %= 1 creates repeating ring bands; ramp shapes the profile.
### Stepped Ramp Channel Sampling
```vex
d = ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```
// Stepped ramp produces quantized striated displacement values.
### Dot Product Basics
```vex
@Cd = @N.y;
@Cd = @N.y;
@Cd = dot(@N, {0,1,0});
@Cd = dot(@N, chv('angle'));
```
// @N.y == dot(@N, {0,1,0}) == dot(@N, chv('angle')).
### Dot Product with Vectors and Channels
```vex
@Cd = dot(@N, {0,1,0});
@Cd = @N.y;
@Cd = dot(@N, {0,1,0});
@Cd = dot(@N, chv('angle'));
// ...
```
// chv('angle') makes the comparison direction interactive.
### Dot Product Direction Comparison
```vex
@Cd = dot(@N, chv('angle'));
@Cd = dot(@N, (0,1,0));
@Cd = dot(@N, chv('angle'));
vector pos = point(1,"P",0);
@Cd = dot(@N, pos);
// ...
```
// Dot product with point(1,"P",0) uses world position as light direction.
### Dot Product with Point Reference
```vex
vector pos = point(1, 'P', 0);
@Cd = dot(@N, pos);
vector pos = point(1, 'P', 0);
@Cd = dot(@N, normalize(pos));
@Cd = dot(@N, chv('angle'));
// ...
```
// normalize(pos) for directional dot product regardless of point distance.
### Reading Point Position from Second Input
```vex
vector pos = point(1, "P", @ptnum);
@Cd = dot(chv("angle"), pos);
```
// point(1, "P", @ptnum) reads matching point from input 1.
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
// Tip-to-tail: chv() parameters + point() reads.
### Vector Addition Basics
```vex
vector a = chv('a');
@i += a;
vector b = point(0, "P", 0);
vector c = point(1, "P", 0);
```
// chv() adds to @i attribute; point() reads from any input.
### Vector Addition Basics
```vex
vector a = chv('a');
@P += a;
vector a = point(0, "P", @ptnum);
vector b = point(1, "P", @ptnum);
```
### Channel References and Point Queries
```vex
vector a = chv('a');
@i += a;
vector b = point(0,'P',0);
vector c = point(1,'P',0);
```
### Vector Channel Parameters and Point Access
```vex
vector a = chv('a');
@N += a;
vector b = point(0, "P", 0);
vector c = point(1, "P", 0);
```
### Vector Subtraction Between Points
```vex
vector a = chv('A');
@N += a;
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);
@N = b - a;
// ...
```
// b - a gives direction from a to b; use normalize() for unit vector.
### Directional velocity from origin point
```vex
@v *= ch("scale");
@v = -@N;
@v *= ch("scale");
vector origin = point(1, 'P', 0);
@v = @P - origin;
@v *= ch("scale");
```
// @v = @P - origin radiates velocity outward from origin point.
### Vector Scaling and Direction
```vex
vector a = @P;
vector b = point(1, @ptnum, "P");
@N = b - a;
@N *= chv('scalevec');
vector origin = point(1, 'P', 0);
// ...
```
// b - a direction from input0 to input1, scaled by chv() for non-uniform stretch.
### Multiplying Normals by Vector
```vex
@N *= chv('scale_vec');
```
// chv() scale_vec enables per-axis normal scaling.
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
// relpointbbox() returns 0-1 position within bbox; chramp shapes inflation falloff.
### Relative Bounding Box Inflation
```vex
vector bbox = relbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```
// relbbox() vs relpointbbox(): relbbox uses input geo bbox.
### Setting Point Scale via Channel
```vex
@pscale = ch("pscale");
```
// @pscale controls uniform instance size in Copy to Points SOP.
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
// @scale allows per-axis scaling; @pscale is uniform only.
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
// chramp(@id) adds per-instance variation via the ramp offset.
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
// fit01(v@pred) remaps predecessor attribute for per-instance phase offset.
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
// Offset @P.y by d/2 to keep base on ground plane while scaling height.
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
// fit(d, min, max, 0, 1) normalizes distance for chramp() input.
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
// Animated scale + color from distance; fit maps to min/max range.
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
// chramp() signature: chramp(string name, float input) returns float.
### Color Ramp Vector Casting
```vex
d = ch('frequency');
d = t;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
// vector(chramp('color', d)) casts float ramp to RGB for @Cd.
### Vector Cast for Color Ramps
```vex
d = chf('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
// vector(chramp('color', d)) turns a color ramp into @Cd.
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
### Color Ramp with Vector Cast
```vex
d = chf('frequency');
d = fit01(d, -1, 1, min, max);
@scale = vector(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
### Color Ramp from Fit Values
```vex
d = chf('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, 0);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
// Two fit() calls: first maps to min/max for scale, second back to 0-1 for chramp().
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
### Color Ramp with Vector Cast
```vex
d = chf('frequency');
d += fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), min, max, 0, 1);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
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
// Double fit: sin->min/max for scale, then min/max->0-1 for color ramp.
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
### Fit and Color Ramp Adjustments
```vex
vector4 col = {1,0,0,0,1};
i@cd = fit(@N, -1, 1, min, max);
@P.y = fit(@P.y, min, 0);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp("cr", d));
```
// fit() on @N and @P.y before chramp() lookup.
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
// angle += @Time*ch('offset') + @ptnum variation for per-point phase.
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
// trunc(noise*4)*PI/2 quantizes noise to 0, 90, 180, 270 degree rotations.
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
// Ctrl+/ toggles comments; double-commenting adds //// prefix.
### primuv function introduction
```vex
vector up = chv('up');
@P = primuv(0, "N", @ptnum, u);
```
// primuv(input, attrib, primnum, uv) samples surface at parametric UV.
### Sample Position and Normal with primuv
```vex
vector uv = chv('uv');
@P = primuv(0, 'P', @ptnum, uv);
@N = primuv(1, 'N', @ptnum, uv);
```
// Sample P and N from different inputs at same UV.
### Sampling Surface Attributes with primuvfs
```vex
vector uv = chv('uv');
v@g0 = primuvfs(1, 'P', 0, uv);
v@g1 = primuvfs(1, 'N', 0, uv);
```
// primuvfs() vs primuv(): primuvfs uses face-vertex UV space.
### Surface Sampling with primuv
```vex
vector uv = chv('uv');
@P = primuv(1, "P", 0, uv);
@N = primuv(1, "N", 0, uv);
```
### Primitive UV Sampling Setup
```vex
vector uv = chv('uv');
vector gx = primmuv(1, 'P', u, uv.x);
vector gy = primmuv(1, 'P', u, uv.y);
```
// Sample x and y UV components separately for gradient/tangent calculations.
### Sampling Attributes with primuv
```vex
vector uv = chv('uv');
@P = primuv(1, 'P', @v, uv);
@N = primuv(1, 'N', @v, uv);
```
### Sampling Geometry with primuv
```vex
vector uv = chv('uv');
@P = primuv(1, 'P', @u, @v);
@N = primuv(1, 'N', @u, @v);
```
### UV-based Position Lookup
```vex
vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
```
### primuv sampling position and normal
```vex
vector uv = chv('uv');
@P = primuv(1, "P", v, uv);
@N = primuv(1, "N", v, uv);
```
### Sampling UV Position and Normal
```vex
vector uv = chv('uv');
vector gx = primuv(1, 'P', 0, uv);
vector gN = primuv(1, 'N', 1, uv);
```
### UV primitive attribute sampling
```vex
vector uv = chv('uv');
v@P = primuv(1, 'P', 0, uv);
v@N = primuv(1, 'N', 0, uv);
```
### UV Parameter Sampling with primuv
```vex
vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
### Sampling Position and Normal with primuv
```vex
vector uv = chv('uv');
@P = primuv(0, '', 'P', 0, uv);
@N = primuv(0, '', 'N', 0, uv);
```
### primuv for UV lookup
```vex
vector uv = chv('uv');
@P = primuv(1, 'P', @ptnum, uv);
@N = primuv(1, 'N', 0, uv);
```
### Sampling Primitive Attributes with primuv
```vex
vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
### Primitive UV Attribute Sampling
```vex
vector uv = chv('uv');
@P = primav(1, 'P', 0, uv);
@N = primav(1, 'N', 0, uv);
```
// primav() is an alternative spelling; same interface as primuv().
### Point Cloud Color Query
```vex
v@P, @P, ch('dist'), 'Cd');
```
// Incomplete pcfind snippet; use pcfind(0, "P", @P, ch('dist'), 10) pattern.
### Animated Wave Displacement
```vex
float d = length(@P);
d *= ch('v_scale');
d += @Frame;
@P += @N * sin(d) * ch('wave_height');
```
// @Frame adds integer-frame animation speed; use @Time for smooth motion.
### Animated Wave with Sine Function
```vex
float d = length(@P);
d *= ch("v_scale");
d += @Time;
@P = @N * sin(d) * ch("wave_height");
```
### Animated Wave Deformation with Channels
```vex
float d = length(@P);
d += @Time;
@P.y = @P.y * sin(d) * ch("wave_height");
```
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
// All fit() ranges exposed as ch() for interactive control.
### Ramp-Driven Position Deformation
```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('my-ramp', d);
```
### Ramp Lookup with Distance Scaling
```vex
float d = length(@P);
d *= ch("scale");
@P.y = chramp("myRamp", d);
@P.y *= ch("height");
```
### Animated ramp displacement with time
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
// d -= @Time moves the ramp sample point over time, creating wave travel.
### Animated Ramp Displacement with Time
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('myramp', d);
@Cd = ch('height');
```
### Animated ramp-driven displacement
```vex
float d = length(@P);
d *= ch('scale');
d = d % 1;
@Cd = chramp('my-ramp', d);
@P.y = ch('height');
```
// d % 1 creates repeating 0-1 bands for ring pattern.
### Animating Ramp with Time
```vex
float d = length(@P);
d *= ch('scale');
d *= @Time;
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
// d *= @Time multiplies distance by time, accelerating wave with frame count.
### Ramp-Based Height Displacement
```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
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
// sin(@ptnum) + fit + chramp drives green channel color from point index.
### Sine Wave Height with Ramp
```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d += 0.5;
@Cy = chramp("myramp", d);
@Cy *= ch("height");
```
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
// fit(sin(d),-1,1,0,1) maps wave to 0-1 before chramp lookup.
### Ramp and Channel Parameter Control
```vex
f@y = chramp('mymap', @P.x);
@P.y *= ch('height');
```
### Custom Ramp Function
```vex
vector ramp(float d){
    d *= ch('scale');
    d = fit(d, -1, 1, 0, 1);
    @P.y = chramp('myramp', d);
    @P.y *= ch('height');
}
```
// Custom VEX function encapsulates scale+remap+chramp pipeline.
### Animated Height Displacement with Ramps
```vex
float d = length(@P);
d *= ch('scale');
d += ch('time');
d %= 1;
@P.y = chramp('mycamp', d);
@P.y *= ch('height');
```
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
// Animated radial sine -> fit -> chramp pipeline.
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
### Radial Sine Wave with Ramp
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d,-1,1,0,1);
@P.y = chramp('myRamp',d);
@P.y *= ch('height');
```
### Quantizing Data with Truncate
```vex
float d = length(@P);
float f = ch('scale');
d /= f;
d = trunc(d);
d *= f;
@P.y = d;
```
// trunc(d/f)*f quantizes to multiples of f (staircase effect).
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
### Channel References for Attributes
```vex
@P = chs("input1_P");
@Cd = chv("input1_Cd");
```
// chs() reads string channel; chv() reads vector channel.
### Channel Reference Scale Vector
```vex
chv('scalevec');
```
### Smooth deformation with fit
```vex
v = fit(d, 0, ch("radius"), 1, 0);
@P.y += v;
```
// fit(d, 0, radius, 1, 0) creates a falloff: 1 at center, 0 at radius edge.
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
// inpointgroup() + for loop iterates over group members.
### Removing Primitives with Points
```vex
removeprim(0, @primnum, 1);
removeprim(0, @primnum, 0);
if (rand(@ptnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}
// ...
```
// removeprim(geo, prim, keeppts): 1=delete points, 0=keep points.
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
// vector(chramp()) converts float spline ramp to color ramp for @Cd.
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
// fit01 + fit two-step for scale -> color ramp workflow.
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
// Pattern: fit(sin->min/max for scale) then fit(min/max->0-1 for chramp).
### primuv function introduction
```vex
vector uv = chv('uv');
primuv(1, 'P', 0, uv);
primuv(1, 'N', 0, uv);
vector uv = chv('uv');
@P = primuv(1, 'P', 0, uv);
@N = primuv(1, 'N', 0, uv);
```
### error
```vex
if (!pointattribtype(0, chs("nameattrib")) != 2) {
    error("Name attribute %s must be a string attribute!", chs("nameattrib"));
    return;
}
if (chf("distance") < 0) {
    error("");
}
float minimumValue = chf("min");
float maximumValue = chf("max");
if (minimumValue >= maximumValue) {
    error("Minimum (%f) must be strictly less than maximum (%f)!",
          minimumValue, maximumValue);
    return;
}
```
// Validates name attribute type, distance range, and min/max ordering.
### foreach
```vex
foreach([element_type]value;array){}
```
// Loops over members of an array.
### metamarch
```vex
int index;
vector p0, p1;
// Initialize input values
index = -1;
p0 = Eye;
p1 = P;
result = 0;
while (metamarch(index, metaball_file, p0, p1, displace_bound)) {
    result += ray_march(metaball_file, p0, p1);
}
```
// Marches through metaball geometry, accumulating ray march results per segment.
### osd_lookuppatch
```vex
// Move scatter SOP points to subdivision limit surface.
// Scatter SOP must store "sourceprim" (Output Attributes tab).
// Transfer texture coordinates from source geometry first.
void movePointToLimitSurface(string file; vector P, uv; int sourceprim) {
    int patch_id = -1;
    float patch_u, patch_v;
    if (osd_lookuppatch(file, sourceprim, uv.x, uv.y,
                        patch_id, patch_u, patch_v, "uv")) {
        vector tmpP;
        if (osd_limitsurface(file, "P", patch_id, patch_u, patch_v, tmpP))
            P = tmpP;
    }
}
```
### osd_patches
```vex
int[] osd_patches(const string file; const face_id) {
    int patches[] = {};
    int first = osd_firstpatch(file, face_id);
    if (first >= 0) {
        int npatches = osd_patchcount(file, face_id);
        for (int i = 0; i < npatches; i++)
            append(patches, first + i);
    }
    return patches;
}
```
### primfind
```vex
int[] prims = primfind(geometry, {-0.5, -0.5, -0.5}, {0.5, 0.5, 0.5});
foreach (int prim; prims) {
    removeprim("primitives.bgeo", prim, 1);
}
```
// Find primitives in bounding box and remove them.
### usd_attribtimesamples
```vex
// Get the time codes of a foo attribute.
float time_codes[] = usd_attribtimesamples(0, "/geo/cube", "foo");
```
### usd_iprimvartimesamples
```vex
// Get primvar values at authored time samples on a prim or its ancestor.
// Input 0 = first wrangle LOP input stage.
float[] usd_iprimvartimesamplevalues(
        const int input; const string primpath, primvarname) {
    float result[];
    float time_samples[] = usd_iprimvartimesamples(input, primpath, primvarname);
    foreach (float time_code; time_samples) {
        float value = usd_iprimvar(input, primpath, primvarname, time_code);
        push(result, value);
    }
    return result;
}
```
### usd_primvartimesamples
```vex
// Get the time codes of a foo primvar.
float time_codes[] = usd_primvartimesamples(0, "/geo/cube", "foo");
```
### warning
```vex
if (primintrinsic(0, "typeid", @primnum) != 1) {
    warning("Primitives that aren't polygons are being ignored.");
    return;
}
if (primintrinsic(0, "closed", @primnum) == 0 || @numvtx < 3) {
    warning("Open or degenerate polygons are being ignored.");
    return;
}
float minimumValue = chf("min");
float maximumValue = chf("max");
if (minimumValue > maximumValue) {
    warning("Minimum (%f) can't be greater than maximum (%f); clamping.",
            minimumValue, maximumValue);
    minimumValue = maximumValue;
}
```
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
// fit(sin(d),-1,1,min,max) drives @scale.y from animated wave.
### Defining orients from other things â
```vex
float angle = ch('angle');
 vector axis = chv('axis');
 @orient = quaternion(angle, axis);
```
// quaternion(angle, axis) with angle in radians and normalized axis.
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
// slerp(a, b, blend) interpolates quaternions; use chramp for per-point blend.
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
// identity quaternion = {0,0,0,1}; use $PI/2 for 90-degree target rotation.
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
// @y attribute (point angle) drives per-point rotation target.
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
// chramp('blend_map', @ptnum*1) per-point blend from ramp parameter.
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
// @Time % 1 loops blend 0->1 each second; chramp shapes the easing curve.
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
// maketransform(N, up) builds rotation matrix; multiply quaternions to chain rotations.