# VEX Corpus: Geometry Creation

> 161 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Beginner (12 examples)

### Cross Product for Normals

```vex
@N = cross(@P, {0,1,0});
```

Computes point normals using the cross product between each point's position and the up vector (0,1,0).

### Vector Addition and Normal Visualization

```vex
vector a = chv('a');
vector b = chv('b');
@N = a+b;
```

Demonstrates vector addition by reading two vector parameters from the UI and assigning their sum to the point normal attribute.

### Point-Based Normal Direction

```vex
vector a = @P;
vector b = point(1, 'P', 0);

@N = b - a;
```

Calculates normals for all points on a sphere by creating vectors that point from each point's position (@P) toward a single reference point (point 0 from input 1).

### Vector from Point to Target

```vex
vector p = v@P;
vector b = point(1, "P", 0);

v@l = b - p;

vector origin = point(1, "P", 0);
@v = (p - origin);
```

Creates vectors pointing from each point in the geometry to a single target point on the second input.

### Vector Direction from Point

```vex
vector origin = point(1, "P", 0);
@v = @P - origin;
```

Creates a velocity vector on each point that points away from a specific origin point (point 0 on input 1).

### Coloring with relpointbbox

```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;
```

Uses relpointbbox() to get the relative position of each point within the bounding box of the input geometry (normalized 0-1 coordinates), then assigns the Y component of that normalized position t....

### Normalizing Points and Relative Bounding Box

```vex
@Cd = relpointbbox(0, @P);

@P = normalize(@P);

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;
```

Demonstrates using relpointbbox() to color geometry based on relative position within the bounding box.

### Setting Up Vector for Orientation

```vex
v@up = {0,0,1};

v@up = {0,1,0};

v@up = {0,v.y,1};
```

Demonstrates setting the @up vector attribute to control orientation around the normal vector.

### Declaring Vector UV Variable

```vex
vector uv;
```

Declares a vector variable named 'uv' that will be used to store UV coordinates or parametric values for sampling normals and positions from a grid geometry.

### Vector Subtraction for Direction Vectors

```vex
vector a = {0,1,0};
vector b = point(1,"P",0);

@v = b-a;

vector origin = point(1,"P",0);
@v = @P - origin;
```

Demonstrates using vector subtraction to create direction vectors between points.

### Setting Up Vector for Copy to Points

```vex
v@up = {0,0,1};

v@up = {0,1,0};
```

Demonstrates setting the @up vector attribute to control the rotational orientation of copied geometry.

### Setting Up Vector for Orientation

```vex
v@up = {0,0,1};

v@up = {0,v.y};

v@up = {0,v.y,1};
```

Explicitly sets the @up vector attribute to control orientation of geometry.

## Intermediate (128 examples)

### Combine quaternions with qmultiply â

```vex
vector4 foo = quaternion({1,0,0}*0.2));
```

Download scene: Download file: orient_qmultiply_compose.hip

A trick I learned from Raph Gadot, cheers!

Somewhere in the above examples are 2 quaternion tricks, using qmultiply for things, and cre....

### Spiral along curve â

```vex
float speed, angle, rand;
vector dir;
vector4 q;

dir = @N;
speed = @Time * ch('speed');
angle = speed+@curveu*ch('spirals');
q = quaternion(v@t*angle);
// ...
```

Download hip: Download file: spiral_along_curve.hip

A hint from clever person HowieM led to this pleasingly clean setup.

### Random dot patterns â

```vex
int tiles = chi('tiles');
float rand = ch('rand');
float start = ch('dotradius_start');
float end = ch('dotradius_end');
vector offset = rand(floor(@uv*tiles)) * {1,1,0};
offset = fit(offset,0,1,-rand,rand);
offset.z = 0;
@Cd = smooth(start, end , length(frac(@uv*tiles)*{2,2,0}-{1,1,0}+offset));
```

The end goal.

### Joy of Vex Day 3 â

```vex
float d = length(@P);
 d *= ch('v_scale');
 d += @Time;
 @P.y = sin(d);
```

Clamp and fit, waves

Hopefully you worked out those exercises from yesterday! So to make waves, we set @P.y:

(If you don't view with wireframes enabled, it'll look unshaded.

### Nearpoint and point â

```vex
int pt = nearpoint(1,@P);
 @Cd = point(1,'Cd',pt);
```

That gif of course leads to the question.

### An aside on the point function â

```vex
point(1, 'Cd', pt);
```

You might be wondering why the point function is formatted as

rather than

or even

The last can be explained easily, @Cd without quotes would be expanded to our current point's colour.

### Visualise the voronoi cell distances â

```vex
int pt = nearpoint(1,@P);
 @Cd = point(1,'Cd',pt);
 vector pos = point(1,'P',pt);
 float d = distance(@P, pos);
 @P.y = -d;
```

Back to coding!

Regarding how the voronoi cells work, we can visualise the distance to the nearest scatter point by putting it into @P.y; the cell edges should end up being the same height:.

### Distance-based color patterns

```vex
float d = distance(@P, {1,0,3});
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

float d = length(@P) * ch('scale');
@Cd = (sin(d)+1)*0.5;

@Cd = (sin(length(@P) * ch('scale'))+1)*0.5;
// ...
```

Demonstrates creating concentric ring color patterns using the distance() function to measure distance from points to a specific position in space.

### Remapping sine wave with fit

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d)-.1)*.5;

vector pos = @P * chv('fancyscale');
vector center = chv('center');
// ...
```

Demonstrates two approaches to remapping sine values for color: manual math adjustment using (sin(d)-.1)*.5, and the cleaner fit() function to remap sine's -1 to 1 range into 0 to 1 for valid color....

### Animating with @Time

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d),-1,1,0,1);

// Adding @Time for animation
vector pos = @P * chv('fancyscale');
// ...
```

Demonstrates animating color patterns by adding the built-in @Time attribute to the sine wave calculation.

### Animating with @Frame vs @Time

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = fit(sin(d*@Frame),-1,1,0,1);
```

Demonstrates animating color patterns using @Frame for rapid integer-based animation versus @Time for smoother float-based animation.

### Using fit() with channels

```vex
float imin = ch("fit_in_min");
float imax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d = fit(d, imin, imax, outmin, outmax);
@P.y = d;
```

Demonstrates using the fit() function to remap a variable's value range using channel references for interactive control.

### Cross Product with Normalized Position

```vex
vector pos = point(1, "P", 0);
pos = normalize(pos);
@Cd = dot(@N, pos);

@N = cross(@N, {0,1,0});
```

Reads a position from point 0 of input 1, normalizes it to create a direction vector, then computes a dot product with the surface normal to drive color.

### Cross Product for Normal Direction

```vex
@N = cross(@N, {1,0,0});
```

Demonstrates using the cross product to rotate normals by crossing them with a reference axis vector.

### Point-to-Point Vector Targeting

```vex
vector a = @P;
vector b = point(1, 'P', 0);

@N = b - a;

vector origin = point(1, 'P', 0);
@v = (@P - origin);
```

Creates vectors from all points in the geometry pointing toward a single reference point from the second input.

### Setting velocity from origin point

```vex
vector origin = point(1, 'P', 0);
@v = @P - origin;
```

Calculates velocity vectors by subtracting an origin point position from each point's position.

### Setting velocity from origin point

```vex
vector origin = point(1, "P", 0);
@v = origin;
```

Reads the position of point 0 from input 1 and assigns it to the velocity attribute.

### Explosion Velocity from Origin Point

```vex
vector origin = point(1, 'P', 0);
@v = (@P - origin) * ch('scale');
```

Creates an explosion effect by reading an origin point from the second input (input 1), computing the direction vector from that origin to each point, and scaling the result to set velocity.

### Velocity From Origin Point

```vex
f@z = ch('scale');

vector origin = point(1, 'P', 0);
@v = @P - origin;
```

Creates velocity vectors for an explosion effect by calculating the direction from an origin point (from second input) to each point's position.

### Velocity from Origin Point

```vex
vector origin = point(1, 'P', 0);
@v = (@P - origin);

@N = @v * ch('scale');
```

Sets velocity (@v) for each point by calculating a vector from an origin point (first point from input 1) to the current point position.

### Normalizing Points and relpointbbox

```vex
@P = normalize(@P);

@Cd = relpointbbox(0, @P);

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;
```

Demonstrates normalizing point positions to create a sphere, then using relpointbbox() to convert positions into normalized bounding box coordinates (0-1 range) for color assignment.

### Relative Bounding Box Positioning

```vex
@P = normalize(@P);

@Cd = relpointbbox(0, @P);

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

s@v = chv('scalevec');
```

Demonstrates using relpointbbox() to get a point's relative position within the bounding box of geometry.

### Wave propagation from nearest point

```vex
int pts1[];
int pt;
vector pos;
float d, w;

pts1 = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts1[0];
// ...
```

Finds the closest point using nearpoints, calculates distance to it, and creates animated waves based on that distance using sine and frame animation.

### Nearpoints ripple effect setup

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(0, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Creates a ripple effect by finding nearby points from a second geometry input, calculating the distance to the closest point, and applying a sine wave modulated by distance falloff and time.

### Blending ripples with falloff

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Extends the ripple effect to blend smoothly across multiple influence points by calculating a falloff weight based on distance.

### Creating Points Along Normal Direction

```vex
addpoint(0, @P + @N * 4);
```

Creates a new point at a position calculated by taking the current point position and offsetting it 4 units in the direction of the point's normal vector.

### Creating Lines with Noise Offset

```vex
vector pos = @N * noise(@Frame) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```

Creates a new point offset from each original point using noise-modulated normal direction, then connects each original point to its new point with a polyline primitive.

### Dynamic lines from points

```vex
vector pos = ch('pt') * normalize(@P - @ptnum) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, 'polyline', @ptnum, pt);
```

Creates dynamic waving lines by adding a new point offset from each original point using a normalized direction scaled by a channel parameter and a vector multiplier.

### Creating Lines from Points

```vex
vector pos = ch("x") + nrandom(@ptnum) * {1,0.1,1};
int pt = addpoint(0, pos);
addprim(0, "polyline", @ptnum, pt);
```

Creates a new point offset from a channel value with random noise, then connects each original point to its corresponding new point with a polyline primitive.

### Creating Polylines with Curl Noise

```vex
int pt = addpoint(0, @P - @N);
addprim(0, "polyline", @ptnum, pt);

vector pos = @N * noise(@P * @Frame) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
// ...
```

Demonstrates creating polyline primitives procedurally using addprim(), addpoint(), and addvertex().

### removeprim point retention flag

```vex
removeprim(0, @ptnum, 0);
```

The third argument of removeprim() controls whether points should be retained after primitive deletion: 1 deletes the points, 0 keeps them.

### Seaweed spiral growth animation

```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removepoint(0, @primnum, 1);
}

// spirally scanned using sin and cos
vector offset, pos;
int pr, pt;
int ptmax;
// ...
```

Creates animated spiraling seaweed tendrils by generating polylines that grow from each point, using sine and cosine functions to create spiral offsets that vary with time and point number.

### Color ramp with vector casting

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @prim * ch('speed');
d = length(@P);
d = d + t;
s = fit(sin(d), -1, 1, min, max);
@scale = set(s, s, s);
// ...
```

Demonstrates using vector casting with chramp() to apply a color ramp to geometry.

### Setting Up Vector Attribute

```vex
v@up = {0,0,1};
```

Creates an 'up' vector attribute pointing in the positive Z direction ({0,0,1}).

### Workflow: Commenting and Resetting

```vex
vector axis;
axis = chv("axis");
axis = normalize(axis);
@a = noise(@P*time);
@a = chramp("noise_rrange",@a);
axis *= trunc(@a*4)*(PI/2);
@P.y = @a;
@orient = quaternion(axis);
// ...
```

Demonstrates VEX workflow techniques including commenting out lines with Ctrl+/ while preserving end-of-line comments, and resetting spare parameters between examples.

### Quaternion from Matrix

```vex
@N = {0,1,0};
float s = sin(@Time);
float c = cos(@Time);
@up = set(s,0,c);

@orient = quaternion(maketransform(@N, @up));

matrix3 m = ident();
// ...
```

Demonstrates converting a matrix to a quaternion orientation using the quaternion() function.

### Quaternion slerp animation with ramps

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(0,1,0,$PI/2);
float blend = chramp('blendRamp',@Time%1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;
// ...
```

Demonstrates quaternion interpolation using slerp() to animate orientation between base and target rotations.

### Intrinsics Overview

```vex
v@alpha, @up, @pscale, @Ac
```

Introduction to intrinsic attributes in Houdini, setting up a clean scene with a sphere and transform node to begin exploring geometry intrinsics.

### Declaring UV vector parameter

```vex
vector uv = chv("uv");
```

Declares a vector variable 'uv' and populates it using the chv() function to read a vector channel parameter named 'uv'.

### Animating Point on Surface with primuv

```vex
uv.x = sin(@Frame*10);
uv.y = cos(@Frame*10);

UV = fit(uv, -1, 1, 0.2, 0.2);
UV += {0.2, 0.5};

@P = primuv(1, 'P', v.uv);
@N = primuv(1, 'N', v.uv);
```

Demonstrates attaching a point to an animated surface position using primuv().

### xyzdist on Primitive Surfaces

```vex
i@grid;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```

Demonstrates using xyzdist() on non-polygonal primitive surfaces like tubes, spheres, and discs to compute UV coordinates.

### xyzdist function setup

```vex
i@primid;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```

Setting up the xyzdist() function to measure distance from each point to the closest primitive on input 1 (a grid).

### xyzdist and primuv combined lookup

```vex
int @primid;
vector @uv;
float @dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, "P", @primid, @uv);
```

Uses xyzdist() to find the closest point on a surface (input 1), which returns the distance, primitive ID, and UV coordinates.

### Near Points Geometry Creation

```vex
int pts[] = nearpoints(1,@P,ch('d'),25);
int pt;
vector pos;
foreach (pt; pts) {
    pos = point(1,"P",pt);
    addpoint(0,pos);
}
```

Finds up to 25 nearby points within a channel-controlled distance from the current point's position, then creates new geometry points at each found point's location by reading their positions and a....

### Finding and Creating Points from Neighbors

```vex
int ps[];
nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;
foreach (pt; ps) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}
```

This code finds nearby points within a radius using nearpoints(), then iterates through each found point to retrieve its position from the second input and creates new points at those positions on ....

### Point Cloud Neighbor Query with Creation

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;
foreach (pt; pts) {
    pos = point(1, "P", pt);
    addpoint(0, pos);
}
```

Uses nearpoints() to find up to 25 points within a distance threshold from the current point, then iterates through the array to read each neighbor's position and create new points at those locatio....

### Nearpoint with Channel Parameter

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
int pt;
vector pos;

foreach(pt; pts){
    pos = point(1, 'P', pt);
    addpoint(0, pos);
}
```

Uses nearpoints() with a channel parameter to dynamically query points within a variable distance from the current point's position.

### Creating Points from Nearpoints Array

```vex
int pts[] = nearpoints(1, @P, ch('d'), 25);
i[]@a = pts;
int pt;
vector pos;

foreach(pt; pts){
    pos = point(1, 'P', pt);
    addpoint(0, pos);
// ...
```

This code finds nearby points using nearpoints(), stores them in an array attribute, then iterates through the array to create new points at each found position.

### Point Cloud Query with Point Addition

```vex
int pts[] = pcfind(1, "P", @P, ch('d'), 25);
i[]@a = pts;
int pt;
vector pos;

foreach(pt; pts){
    pos = point(1, "P", pt);
    addpoint(0, pos);
// ...
```

Uses pcfind to find nearby points from the second input geometry based on position and distance parameter, stores the point numbers in an array attribute, then iterates through the found points to ....

### Point Cloud Query with Foreach

```vex
int pts[] = pcfind(1, 'P', @P, ch('d'), 25);
i[]@a = pts;
int pt;
vector pos;

foreach(pt; pts){
    pos = point(1, 'P', pt);
    addpoint(0, pos);
// ...
```

Uses pcfind to find nearby points within a specified distance and stores the results in an array.

### Point Cloud Query and Geometry Creation

```vex
int ptsi[] = pcfind(1, 'P', @P, ch('d'), 25);
i@num = len(ptsi);
int pti;
vector pos;

foreach(pti; ptsi){
    pos = point(1, 'P', pti);
    addpoint(0, pos);
// ...
```

Uses pcfind to find nearby points within a channel-controlled distance, stores the count of found points, then iterates through each found point to read its position and create new geometry points ....

### Point Cloud Optimization with pcfind

```vex
int pts[] = pcfind(1, "P", @P, ch("d"), 25);
i[]@a = pts;
int pt;
vector pos;

foreach(pt; pts){
    pos = point(1, "P", pt);
    addpoint(0, pos);
// ...
```

Uses pcfind() to find nearby points within a radius, stores them in an array, then iterates through the found points to create new geometry at their positions.

### Fit Function with Channel Controls

```vex
float inmin = ch("fit_in_min");
float inmax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d = fit(d, inmin, inmax, outmin, outmax);
@P.y = d;
```

This code demonstrates using channel references to control the fit() function parameters, allowing interactive adjustment of input and output ranges.

### Color Transfer Using Nearest Point

```vex
int pt = nearpoint(1, @P);
@Cd = point(1, 'Cd', pt);
```

Finds the closest point from the second input geometry and transfers its color attribute to the current point.

### Nearest Point Color Transfer

```vex
int pt = nearpoint(1, @P);
@Cd = point(1, "Cd", pt);
```

Finds the nearest point on the second input geometry and copies its color attribute to the current point.

### Reading Non-Existent Attributes

```vex
int pt = nearpoint(0, v@P);
v@Cd = point(0, "Cd", pt);
```

Demonstrates what happens when attempting to read a color attribute (Cd) that doesn't exist on the input geometry.

### Handling Missing Attributes

```vex
int pt = nearpoint(0, @P);
v@Cd = point(0, "Cd", pt);
```

Demonstrates what happens when attempting to read a non-existent attribute from geometry.

### nearpoint and distance shorthand

```vex
int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
v@v = d;
```

Demonstrates using nearpoint() to find the closest point on input 1, then retrieving that point's position with point() and calculating the distance between the current point and the nearest point.

### Sine Wave Amplitude and Distance Falloff

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Applies a sine function to the distance-based frequency value, then multiplies by an amplitude parameter to control wave height.

### Animated sine wave ripples

```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
// ...
```

Creates animated sine wave ripples by finding nearby points and using their distance to modulate a time-based sine wave that displaces points vertically.

### Adding Points with Position Offset

```vex
addpoint(0, {0,0,0});

addpoint(0, {0.5,0,0});
```

Demonstrates two approaches to adding points in space using addpoint() with explicit position vectors.

### Creating Points for Polyline Primitive

```vex
int pt = addpoint(0, set(0, 3, 0));
```

Creates a new point at position (0, 3, 0) using addpoint() and stores the point number in an integer variable.

### Creating polylines with addprim

```vex
int pt = addpoint(0, {0,1,0});
addprim(0, 'polyline', @ptnum, pt);
```

Creates a new point at position {0,1,0} and stores its point number in variable pt.

### Creating polylines with addpoint

```vex
int pt = addpoint(0, {0,3,0});
addprim(0, "polyline", @ptnum, pt);
```

Creates a new point at position {0,3,0} and connects it to the current point with a polyline primitive.

### Animated Polylines with Noise

```vex
vector pos = @N + noise(@P - @Time) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```

Creates animated polylines from each point by calculating an offset vector using noise driven by position minus time, scaled non-uniformly, then adding a new point at that offset position and conne....

### Creating animated polylines from points

```vex
vector pos = ch3("rotate") * i * {1, 0, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```

Creates a polyline between each existing point and a newly generated point offset by an animated position vector.

### Creating Animated Lines from Points

```vex
vector pos = ch3("parm") * vector(0, 1, 0) + @Time * vector(1, 0, 1);
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```

Creates animated lines by adding a new point offset from each existing point based on a channel parameter and time, then connecting them with polyline primitives.

### Animated Lines from Points

```vex
vector pos = ch("p") * nrandom(@P + @Time) * {1,0.1,1};
int pt = addpoint(0, @P, pos);
addprim(0, "polyline", @ptnum, pt);
```

Creates animated lines extending from each point by generating a new point with time-varying noise offset, then connecting the original point to the new point with a polyline primitive.

### Time-Based Line Generation

```vex
vector pos = @N * noise(@P * chf("time")) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```

Creates polylines from each point by generating a new point offset along the normal direction, modulated by time-based noise.

### Wispy Lines with Curl Noise

```vex
vector pos = ch("pt") * {1,0,1};
vector pt = addpoint(0,@P+pos);
addprim(0,"polyline",@ptnum,pt);

vector offset, pos;
int pr, pt;
float stepsize;

// ...
```

Creates multiple points along each point's normal direction using a for loop, adding curl noise offset to each point position for a wispy effect.

### Point vs Vertex Normals in Geometry Creation

```vex
vector pos = (M * noise(@P * pTime)) * {1,0.3,1};
int pt = addpoint(0,@P+pos);
addprim(0, "polyline", @ptnum,pt);

vector pos = (M * noise(@P * pTime)) * {1,0.1,1};
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum,pt);

// ...
```

Demonstrates the difference between point normals and vertex normals when creating geometry procedurally.

### Normal calculation in rotation

```vex
vector pos = ch * rotation(0, @N*len) * {1,0,0,1};
int pt = addpoint(0, @P + pos);
addvertex(0, "polyline", @ptnum, pt);
```

Creates a rotated position vector using the point normal and rotation matrix, then adds a new point at the transformed position and connects it to form a polyline.

### Declaring Variables for Curve Generation

```vex
vector pos = (M * rotate(@P * ramp * {1,0,1}, 1));
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum, pt);

vector pos = (M * rotate(@P * @Tramp) * {1,0,1});
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum, pt);

// ...
```

Setting up variables for a procedural curve generation system using a for loop.

### Creating Polylines with Variables

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
```

Variable declarations for creating a polyline primitive.

### For loop polyline generation

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for(int i=0; i<6; i++) {
// ...
```

Uses a for loop to procedurally generate a polyline with multiple points displaced by curl noise, demonstrating how loops make geometry creation more flexible than manually adding individual points.

### Creating Polyline Primitives with Curl Noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<61; i++) {
// ...
```

Creates a polyline primitive by adding 61 points along the normal direction with curl noise offset applied.

### Creating Points for Polyline

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addpoint(0);
pt = addpoint(0, set(0, 3, 0));
```

Initializes variables for building a polyline and creates two points.

### Creating Point and Polyline Primitive

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pt = addpoint(0, {0,0,0});
pr = addprim(0, "polyline", pt);
```

Declares variables for procedural geometry creation, then creates a point at the origin and adds a polyline primitive that references that point.

### Creating Circle Primitives with addprim

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pt = addpoint(0, {0,3,0});
pr = addprim(0, "circle", pt);
```

Demonstrates creating a circle primitive using addprim() with the "circle" type, showing that addprim() can create procedural primitive types beyond just polylines and polygons.

### removeprim and removepoint modes

```vex
// Remove primitive with default mode
if(rand(@primnum) < ch('cutoff')){
    removeprim(0, @primnum, -1);
}

// Remove only the primitive, keep points
removeprim(0, @primnum, 1);

// ...
```

Demonstrates the different modes of removeprim() function, including the third argument which controls whether to keep points (-1 for default, 0 to remove unused points, 1 to keep all points).

### Random Primitive Removal with Seed Control

```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removepoint(0, @primnum, 1);
}

if(rand(@ptnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

// ...
```

Demonstrates using rand() with seed values to randomly remove primitives or points based on a cutoff threshold.

### Color Ramp with Sine Distance

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Creates an animated color effect using distance from origin, mapping sine wave values through a color ramp.

### Color Ramp with Fitted Distance

```vex
float min, max, d, t;
min = ch("min");
max = ch("max");
t = @primid * ch("speed");
d = length(@P);
d *= ch("frequency");
d += t;
@Cd = fit(sin(d), -1, 1, min, max);
// ...
```

Remaps a distance value (d) from the min-max range back into 0-1 range to properly sample a color ramp parameter using chramp().

### Quaternion Rotation with Axis Scaling

```vex
vector axis;

axis = chv("axis");
f@angle = ch("angle");
axis = normalize(axis);
axis *= f@angle;

@orient = quaternion(axis);
```

Creates a quaternion rotation by normalizing a vector axis from a parameter, then scaling it by an angle value.

### Instance Matrix to Quaternion Orientation

```vex
@P = v@P;
@orient = {0,0,0,1};
@pscale = 1;

int target = nearpoint(1,@P);
vector base = point(1,"P",target);
matrix m = ident();
m = instance(m, base-@P, {0,1,0}, 1, {0,0,1}, 0);
// ...
```

Creates instance orientations by finding the nearest point on a target geometry and building an instance matrix from that position.

### Matrix Types and Orientation Vectors

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};

// Convert quaternion orientation to matrix
matrix3 m = qconvert(Qorient);
// ...
```

Demonstrates converting quaternion orientation to matrix form and extracting orientation vectors.

### Surface Projection with xyzdist and primuv

```vex
i@primid;
v@uv;
f@dist;
@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, "P", @primid, @uv);
```

Uses xyzdist to find the closest point on a surface and stores the primitive ID and UV coordinates, then uses primuv to project the current point's position to that exact location on the surface.

### area

```vex
area(transform("ndc",P))
```

This function works because VEX “knows” that the variablePhas derivatives (dPduanddPdv).

### argsort

```vex
cvexmain(){// Given an array of strings...stringcolors[] ={"Red","Green","Blue","Orange","Violet","Indigo"};// Create an array with the corresponding lengthsint[]lengths={};foreach(stringname;colors){push(lengths,len(name));}// Sort the lengths and return an array containing the new orderingint[]ordering=argsort(lengths);// Get the array of color names but sorted by name lengthstringcolors_by_len[] =reorder(colors,ordering);printf("%s\n",colors_by_len);}// Prints {Red, Blue, Green, Orange, Violet, Indigo}
```

Signature: cvexmain(){// Given an array of strings...stringcolors[] ={"Red","Green","Blue","Orange","Violet","Indigo"};// Create an array with the corresponding lengthsint[]lengths={};foreach(strin....

### ckspline

```vex
Cf=ckspline(t,{1,1,1},    -0.25,// First key{.5,.5,.5},0.0,// Second key{.5,0,.5},0.25,// Third key{0,0,.8},1.0,// Fourth key{0,0,0},1.25// Fifth key);
```

Signature: Cf=ckspline(t,{1,1,1},    -0.25,// First key{.5,.5,.5},0.0,// Second key{.5,0,.5},0.25,// Third key{0,0,.8},1.0,// Fourth key{0,0,0},1.25// Fifth key);

The position along the spline to ....

### diffuse

```vex
diff=diffuse(nml,"lightmask","hero | fill");
```

Signature: diff=diffuse(nml,"lightmask","hero | fill");

Diffuse reflections.

### environment

```vex
vectordir=vtransform("space:current","space:object",{0,1,0});vectorclr=environment("sky.rat",dir);
```

To perform environment map lookups in object space, you must first transform the direction vector with thevtransform()function.

### gather

```vex
gather(vectororigin,vectordirection, ...){// Statements for rays that hit other surfaces}else{// Statements for rays which didn't hit any surface}
```

Signature: gather(vectororigin,vectordirection, ...){// Statements for rays that hit other surfaces}else{// Statements for rays which didn't hit any surface}

If you specify 0 samples, it will stil....

### gradient

```vex
surfacetest_grad(floatdensity=0){Cf=gradient(density);}
```

Functions which compute derivatives take additional arguments to
allow tuning of the derivative computation.

"extrapolate",int=0

Whether derivatives are
    “smooth” across patch boundaries.

### haslight

```vex
haslight(material(),P,light_num,"direct",0);
```

Signature: haslight(material(),P,light_num,"direct",0);

A string specifying a specific label.

### hedge_dstvertex

```vex
intdstvtx;// Get the destination vertex half-edge number 3.dstvtx=hedge_dstvertex("defgeo.bgeo",3);
```

Signature: intdstvtx;// Get the destination vertex half-edge number 3.dstvtx=hedge_dstvertex("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be a....

### hedge_postdstpoint

```vex
intpostdstpt;// Get the destination vertex half-edge number 3.postdstpt=hedge_postdstpoint("defgeo.bgeo",3);
```

Signature: intpostdstpt;// Get the destination vertex half-edge number 3.postdstpt=hedge_postdstpoint("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument....

### hedge_postdstvertex

```vex
intpostdstvtx;// Get the destination vertex half-edge number 3.postdstvtx=hedge_postdstvertex("defgeo.bgeo",3);
```

Signature: intpostdstvtx;// Get the destination vertex half-edge number 3.postdstvtx=hedge_postdstvertex("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argum....

### hedge_prim

```vex
intprim;// Get the primitive number of half-edge number 3.prim=hedge_prim("defgeo.bgeo",3);
```

Signature: intprim;// Get the primitive number of half-edge number 3.prim=hedge_prim("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be an intege....

### hedge_srcvertex

```vex
intsrcvtx;// Get the source vertex of half-edge number 3.srcvtx=hedge_srcvertex("defgeo.bgeo",3);
```

Signature: intsrcvtx;// Get the source vertex of half-edge number 3.srcvtx=hedge_srcvertex("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be an ....

### insert

```vex
insert(numbers; -1;100)
```

Signature: insert(numbers; -1;100)

Inserts thevalueinto the stringstrat the givenindex.

Ifindexis greater than the length of the string, thevaluewill simply be appended to the existingstr.

### intersect

```vex
// Intersect against the second input's geometry, using a ray at the current// point's position and in the direction of its velocity vector.vectororigin=@P;floatmax_dist=1000;vectordir=max_dist*normalize(@v);vectorisect_pos;floatisect_u,isect_v;intisect_prim=intersect(@OpInput2,origin,dir,isect_pos,isect_u,isect_v);// Return the farthest intersection instead.isect_prim=intersect(@OpInput2,origin,dir,isect_pos,isect_u,isect_v,"farthest",1);
```

Signature: // Intersect against the second input's geometry, using a ray at the current// point's position and in the direction of its velocity vector.vectororigin=@P;floatmax_dist=1000;vectordir=m....

### opdigits

```vex
stringdir,name;splitpath(opfullpath("."),dir,name);returnopdigits(name);
```

Signature: stringdir,name;splitpath(opfullpath("."),dir,name);returnopdigits(name);

opdigits("/obj/geo34/box21")- returns 21

opdigits("/obj/geo34/box")- returns 34

opdigits("/obj/geo34/box2.1")-....

### pointvertex

```vex
intvtx;// Get the linear vertex  of point 3vtx=pointvertex("defgeo.bgeo",3);
```

Signature: intvtx;// Get the linear vertex  of point 3vtx=pointvertex("defgeo.bgeo",3);

Use this to find linear vertex number of the first vertex to share this point.
    Then you can usevertexnex....

### primvertex

```vex
intlinearvtx;// Get the linear vertex value of vertex 2 of primitive 3.linearvtx=primvertex("defgeo.bgeo",3,2);
```

Signature: intlinearvtx;// Get the linear vertex value of vertex 2 of primitive 3.linearvtx=primvertex("defgeo.bgeo",3,2);

When running in the context of a node (such as a wrangle SOP), this argum....

### refractlight

```vex
surfaceglass(floateta=1.3,bias=0.005){floatKr,Kt;vectorR,T;vectorcf,of;floataf;frensel(normalize(I),normalize(N),eta,Kr,Kt,R,T);Cf=Kr*reflectlight(P,R,bias,Kr);refractlight(cf,of,af,P,T,bias,Kt);Cf+=Kt*cf;Af=clamp(Kr+af*Kt,0,1);Of=1;}
```

"categories",string="*"

Specifies lights to include/exclude by their “category” tags.
    This is the preferred include/exclude lights rather than pattern matching
    light names with the"lightma....

### texture

```vex
Cf=texture("map.rat",ss,tt,"pixelblur",2.0);
```

Samples the texture at the global S and T coordinates from the shading context.

### unserialize

```vex
vectorv[]floatf[] ={1,2,3,7,8,9};v=vector(unserialize(f));// Now v has a length of 2 and contains { {1,2,3}, {7,8,9} }
```

Signature: vectorv[]floatf[] ={1,2,3,7,8,9};v=vector(unserialize(f));// Now v has a length of 2 and contains { {1,2,3}, {7,8,9} }

The inverse operation toserialize.

### usd_addprim

```vex
// Adds a sphere primitive.usd_addprim(0,"/geo/sphere","Sphere");
```

Signature: // Adds a sphere primitive.usd_addprim(0,"/geo/sphere","Sphere");

A handle to the stage to write to.

### usd_addscale

```vex
// Scale the cubeusd_addscale(0,"/geo/cube","my_scale",{0.25,0.5,2});
```

Signature: // Scale the cubeusd_addscale(0,"/geo/cube","my_scale",{0.25,0.5,2});

A handle to the stage to write to.

### usd_addtranslate

```vex
// Translate the cubeusd_addtranslate(0,"/geo/cube","my_translation",{10,0, -2.5});
```

Signature: // Translate the cubeusd_addtranslate(0,"/geo/cube","my_translation",{10,0, -2.5});

A handle to the stage to write to.

### usd_collectionincludes

```vex
// Get collection's include list.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");stringinclude_list[]  =usd_collectionincludes(0,collection_path);
```

Signature: // Get collection's include list.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");stringinclude_list[]  =usd_collectionincludes(0,collection_path);

When run....

### usd_iprimvarnames

```vex
// Get the primvar names from the primitive and its ancestors.stringprimvar_names[] =usd_iprimvarnames(0,"/geo/src_sphere");
```

Signature: // Get the primvar names from the primitive and its ancestors.stringprimvar_names[] =usd_iprimvarnames(0,"/geo/src_sphere");

When running in the context of a node (such as a wrangle LOP....

### usd_kind

```vex
// Get the sphere primitive's kind.stringkind=usd_kind(0,"/geo/sphere");
```

Signature: // Get the sphere primitive's kind.stringkind=usd_kind(0,"/geo/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer representing the ....

### usd_pointinstance_getbbox

```vex
// Get the bounding box of the first instanced sphere.vectormin,max;usd_pointinstance_getbbox(0,"/src/instanced_spheres",0,"render",min,max);
```

Signature: // Get the bounding box of the first instanced sphere.vectormin,max;usd_pointinstance_getbbox(0,"/src/instanced_spheres",0,"render",min,max);

When running in the context of a node (such....

### usd_pointinstance_getbbox_center

```vex
// Get the center of the first instance's boundsng box.vectorcenter=usd_pointinstance_getbbox_center(0,"/src/instanced_spheres",0,"render");
```

Signature: // Get the center of the first instance's boundsng box.vectorcenter=usd_pointinstance_getbbox_center(0,"/src/instanced_spheres",0,"render");

When running in the context of a node (such ....

### usd_setprimvar

```vex
// Set the value of some primvars.usd_setprimvar(0,"/geo/sphere","float_primvar",0.25);usd_setprimvar(0,"/geo/sphere","string_primvar","foo bar baz");usd_setprimvar(0,"/geo/sphere","vector_primvar",{1.25,1.50,1.75});floatf_arr[] ={0,0.25,0.5,0.75,1};usd_setprimvar(0,"/geo/sphere","float_array_primvar",f_arr);
```

Signature: // Set the value of some primvars.usd_setprimvar(0,"/geo/sphere","float_primvar",0.25);usd_setprimvar(0,"/geo/sphere","string_primvar","foo bar baz");usd_setprimvar(0,"/geo/sphere","vect....

### usd_setvariantselection

```vex
// Set the variant "cone" in a variant set "shapes" on the "shape_shifter" primitive.usd_setvariantselection(0,"/geo/shape_shifter","shapes","cone");
```

Signature: // Set the variant "cone" in a variant set "shapes" on the "shape_shifter" primitive.usd_setvariantselection(0,"/geo/shape_shifter","shapes","cone");

A handle to the stage to write to.

### usd_setvisible

```vex
// Set the sphere primitive as visible.usd_setvisible(0,"/geo/sphere",true);
```

Signature: // Set the sphere primitive as visible.usd_setvisible(0,"/geo/sphere",true);

A handle to the stage to write to.

### usd_specifier

```vex
// Get the sphere primitive's specifier.stringspecifier=usd_specifier(0,"/geo/sphere");
```

Signature: // Get the sphere primitive's specifier.stringspecifier=usd_specifier(0,"/geo/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer re....

### usd_typename

```vex
// Get the primitive's type name, eg "Cube".stringtype_name=usd_typename(0,"/geo/cube");
```

Signature: // Get the primitive's type name, eg "Cube".stringtype_name=usd_typename(0,"/geo/cube");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer r....

### usd_uniquetransformname

```vex
// Construct a unique full name for a translation operation with suffix "cone_pivot"stringunique_xform_name=usd_uniquetransformname(0,"/geo/cone",USD_XFORM_TRANSLATE,"cone_pivot");
```

Signature: // Construct a unique full name for a translation operation with suffix "cone_pivot"stringunique_xform_name=usd_uniquetransformname(0,"/geo/cone",USD_XFORM_TRANSLATE,"cone_pivot");

When....

### usd_variantsets

```vex
// Get the variant sets available on the "shape_shifter" primitive.stringvariant_sets[] =usd_variantsets(0,"/geo/shape_shifter");
```

Signature: // Get the variant sets available on the "shape_shifter" primitive.stringvariant_sets[] =usd_variantsets(0,"/geo/shape_shifter");

When running in the context of a node (such as a wrangl....

### vertexindex

```vex
intlinearvtx;// Get the linear vertex value of vertex 2 of primitive 3.linearvtx=vertexindex("defgeo.bgeo",3,2);
```

Signature: intlinearvtx;// Get the linear vertex value of vertex 2 of primitive 3.linearvtx=vertexindex("defgeo.bgeo",3,2);

When running in the context of a node (such as a wrangle SOP), this argu....

### vertexnext

```vex
intvtx;// Get the next vertex of vertex 3vtx=vertexnext("defgeo.bgeo",3);
```

Signature: intvtx;// Get the next vertex of vertex 3vtx=vertexnext("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be an integer representing the....

### vertexpoint

```vex
intpt;// Get the point of vertex 3pt=vertexpoint("defgeo.bgeo",3);
```

Signature: intpt;// Get the point of vertex 3pt=vertexpoint("defgeo.bgeo",3);

When running in the context of a node (such as a wrangle SOP), this argument can be an integer representing the input ....

### vertexprim

```vex
intpt;// Get the primitive of vertex 3pt=vertexprim("defgeo.bgeo",3);
```

Signature: intpt;// Get the primitive of vertex 3pt=vertexprim("defgeo.bgeo",3);

To convert the linear index into a primitive number and primitive vertex number,
    usevertexprimandvertexprimindex.

### volume

```vex
volume({0.1,2.3,4.5})
```

This function relies on the fact that VEX “knows” thatposhas
    derivatives (dPdu,dPdv, anddPdz).
    Passing a literal vector instead of a special variables such asPwill return0since VEX will not....

## Advanced (21 examples)

### Access group names procedurally in vex â

```vex
s[]@groups  = detailintrinsic(0, 'primitivegroups');
i[]@prims =  expandprimgroup(0, s[]@groups[1]);
```

Download scene: Download file: group_random_delete_vex.hipnc

Chuffed with this one.

### More on rotation: Orient, Quaternions, Matricies, Offsets, stuff â

```vex
float angle = @Time;
vector axis = rand(@ptnum);
matrix3 m = ident();
rotate(m, angle, axis);
@orient = quaternion(m);
```

This stuff has taken a while to sink into my brain, so don't worry if it doesn't make sense at first.

### Dihedral to align fractured pieces â

```vex
@N = @P;
3@xform = dihedral(@N, {0,1,0});
@P = {0,0,0};
```

Download file: dihedral_sphere_pieces.hip

Another example along similar lines to the above, prompted by a question from Arvid Schneider.

### Distort colour with noise and primuv â

```vex
vector noise = curlnoise(@P*ch('freq')+@Time*0.5);
vector displace = noise - v@N * dot(noise, v@N); //project the noise to the surface
int prim;
vector uv;
xyzdist(0, @P + displace * ch("step_size"), prim, uv);
@Cd = primuv(0, "Cd", prim, uv);
```

Download hip: Download file: col_distort.hip

I've tried distorting surface values with noise before but never got it quite right, Jake Rice had the answer (Jake Rice ALWAYS has the answer).

### Addprim â

```vex
int pt = addpoint(0,{0,3,0});
 addprim(0,'polyline', @ptnum, pt);
```

Assuming you've read the points/verts/prims page by now, you should have an intuition that to create a polygon requires linking points together into a prim via verticies.

### Blending orients â

```vex
vector4 a = {0,0,0,1};
 vector4 b = quaternion({0,1,0}*$PI/2);
 @orient = slerp(a, b, ch('blend') );
```

So now we've covered hopefully every way you might have stored rotation and how to convert it to a quaternion.

### Combine orients with qmultiply â

```vex
@N = normalize(@P);
 @up = {0,1,0};
 @orient = quaternion(maketransform(@N,@up));
```

Another handy trick for quaternions that is tricky to do via other means.

Here's a polygon sphere, uniform scale 5, frequency 2, with some pigs copy sop'd onto it, where @N is normalize(@P), and @....

### Rotating Geometry with Quaternions

```vex
@N = {0,1,0};
float s = sin($Time);
float c = cos($Time);
@up = set(s,0,c);

@orient = quaternion(maketransform(@N, @up));

// Alternative methods shown:
// ...
```

Creates rotating geometry by constructing a quaternion orientation from an animated up vector.

### Quaternion slerp animation with noise-driven rotation

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(radians(0),{0}*$PI/2);
float blend = chramp('blendramp',@ptnum%1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;
// ...
```

Creates animated quaternion rotations using slerp interpolation between a base identity quaternion and a target rotation.

### Smooth Quaternion Interpolation with Slerp

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
float blend = chramp('blendramp',@Time);
@orient = slerp(a, b, blend);

vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * PI/2);
float blend = chramp('blendramp', @Time % 1);
// ...
```

Demonstrates smooth interpolation between quaternion orientations using slerp() instead of abrupt flipping.

### Quaternion Transformations with Matrix Extraction

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin(90*@Time), {0,1,0});
// ...
```

Builds a complex orientation quaternion by composing multiple rotations (base orientation, 90-degree rotation, time-based headshake, and curl noise wobble), then converts the final quaternion to a ....

### Extracting Axes from Quaternion Matrix

```vex
matrix3 m = qconvert(@orient);
vector axis[] = extractm(m);
@N = normalize(axis[2]); // z axis
@up = normalize(axis[1]); // y axis
```

Converts a quaternion orient attribute to a matrix, extracts the individual axis vectors using extractm(), and assigns the z-axis to @N and y-axis to @up for visualization.

### Orientation with Multiple Quaternion Rotations

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(chf("n")), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*chf("n")*3), {0,1,0});
// ...
```

Creates a complex orientation system by composing multiple quaternion rotations through qmultiply, starting with a base orientation from maketransform, then adding extrarot, headshake (time-based s....

### Quaternion Orientation with Dynamic Rotations

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@O), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time+chv("s"))*3), {0,1,0});
// ...
```

Creates an orient quaternion from a transformation matrix aligned to normalized point position and up vector, then applies multiple rotational modifications including a channel-driven parameter, ti....

### Quaternion Orientation with Curl Noise

```vex
vector N, up;
vector4 extract, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extract = quaternion(radians(@0), {1,0,0});
headshake = quaternion(radians(20) * sin((f@timeinput)*3), {0,1,0});
// ...
```

Creates complex orientation by combining multiple quaternion rotations: a base orientation aligned to the point normal, an extract rotation from a parameter, an animated headshake sine wave, and cu....

### Creating polyline between points

```vex
int pt = addpoint(0, {0,1,0});
addprim(0, "polyline", @ptnum, pt);
```

Creates a new point at position {0,1,0} and stores its point number in the variable 'pt', then creates a polyline primitive connecting the current point (@ptnum) to the newly created point.

### Creating Primitives with Points

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pt = addpoint(0, {0,3,0});
pr = addprim(0, "polyline", pt);
```

Demonstrates creating a primitive by first adding a point at a specific position using addpoint(), then creating a polyline primitive attached to that point using addprim().

### Quaternion SLERP Animation

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
float blend = chramp('blendRamp',@Time);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;
// ...
```

Demonstrates spherical linear interpolation (slerp) between quaternions to smoothly animate rotation orientations.

### Quaternion SLERP interpolation with noise

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * PI/2);
float blend = chramp('blendRamp',@Time*1);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;
// ...
```

Demonstrates spherical linear interpolation (SLERP) between quaternions for smooth rotation animation.

### Quaternion Rotation with Noise

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = normalize(axis);
seed = noise(0 + @Time);
seed = chramp('noise_range', seed);
axis *= trunc(seed*4) * (PI/2);
// ...
```

Creates animated quaternion rotations by using time-based noise to randomly select 90-degree rotations around a normalized axis.

### Quaternion orientation with noise wobble

```vex
vector N, up;
vector4 extrarots, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = maketransform(N, up);
extrarots = quaternion(radians(@P.x), {1,0,0});
headshake = quaternion(radians(20) * sin(@TimeInc*chf("nums")*3), {0,1,0});
// ...
```

Creates complex quaternion-based orientation by combining a base transform with three rotation layers: a positional rotation, an animated head-shake sine wave, and curl noise wobble.
