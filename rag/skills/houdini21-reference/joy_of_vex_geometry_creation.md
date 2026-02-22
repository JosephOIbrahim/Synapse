# Joy of VEX: Geometry Creation

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
addpoint(0, @P + @N * 4);  // Creating Points Along Normal Direction
int pt = addpoint(0, set(0, 3, 0));  // Creating Points for Polyline Primitive
addpoint(0, {0,0,0});  // Adding Points with Position Offset
```

## Adding Points & Geometry

### Creating Points with addpoint [[Ep5, 104:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6276s)]
```vex
int pt = addpoint(0, {0,1,0});

if (@ptnum==0) {
  addpoint(0, {0,1,0});
}
```
Introduction to creating geometry in VEX using the addpoint() function. The code demonstrates creating a new point at position {0,1,0}, with a conditional example showing how to add a point only when processing the first point (@ptnum==0). This marks the transition from geometry manipulation to geometry creation.

### addpoint return value storage [[Ep5, 107:28](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6448s)]
```vex
int pt = addpoint(0, {0,1,0});

if (@ptnum==0) {
    addpoint(1, {0,1,0});
}
```
The addpoint() function returns the point number index of the newly created point, which can be stored in a variable. When run on every point without conditional logic, this creates duplicate points at the same position (one new point per input point), resulting in stacked geometry that may need cleanup with a fuse node.

### Conditional Point Creation [[Ep5, 107:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6452s)]
```vex
int i = addpoint(0, {0, i, 0});

int pt = addpoint(0, {0, i, 0});

if (@ptnum == 0) {
    addpoint(0, {0, i, 0});
}
```
Demonstrates the problem of creating points in a loop without conditional checks, where addpoint creates a new point for every existing point on the grid, resulting in duplicate overlapping points. The solution uses an if statement to check @ptnum == 0 to ensure point creation only happens once, avoiding the creation of 200 points (100 original + 100 duplicates) stacked at the same location.

### Conditional Point Creation with addpoint [[Ep5, 107:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6456s)]
```vex
int pt = addpoint(0, {0,1,0});

if (@ptnum==0) {
    addpoint(0, {0,1,0});
}

int @i1 = addpoint(0, {0,1,0});
```
Using addpoint() inside a point wrangle creates a new point for every iteration through the geometry, resulting in duplicate points at the same location. To create only a single point, use a conditional statement like 'if (@ptnum==0)' to ensure addpoint() executes only once. The function returns the point number of the created point, which can be stored for later reference.

### Conditional Point Creation with addpoint [[Ep5, 107:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6470s)]
```vex
int pt = addpoint(0, (0,3,0));

int pt = addpoint(0, (0,3,0));

if (@ptnum==0) {
    addpoint(0, (0,5,0));
}

addpoint(0, @P + (0,5,0));
```
Demonstrates the problem of adding points in a point wrangle without conditional logic, where each input point creates a new point resulting in double the geometry. Shows how using an if statement with @ptnum==0 restricts point creation to only the first point, avoiding unwanted duplication. The final example shows adding a point offset from each input point's position.

### Adding Points with Position Offset [[Ep5, 108:56](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6536s)]
```vex
addpoint(0, {0,0,0});

addpoint(0, {0.5,0,0});
```
Demonstrates two approaches to adding points in space using addpoint() with explicit position vectors. The first creates a point at origin, while the second creates a point offset by 0.5 units in X. This method avoids needing fusing operations afterwards and can be run on a single point iteration.

### Adding Points Conditionally [[Ep5, 108:58](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6538s)]
```vex
// addpoint(0, {0,0,0});

if (@ptnum==0) {
    addpoint(0, @P+(0,1,0));
}

// addpoint(0, @P + (0,5,0));

// addpoint(0, @P + @N * 4);

for (int i = 0; i<10; i++) {
    addpoint(0, @P + @N * (i*0.1));
}
```
Demonstrates using conditional statements to add points selectively based on point number, avoiding the need for post-creation fusing. Shows progression from adding points at arbitrary positions to adding them relative to the current point's position and normal, with a loop creating multiple points along the normal direction at varying distances.

### Adding Points with Offsets [[Ep5, 109:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6582s)]
```vex
if (@ptnum==1) {
    addpoint(0, (0,1,0));
}

addpoint(0, @P + (0,1,0));

addpoint(0, @P + (0,5,0));

addpoint(0, @P + @N * 4);

for (int i = 0; i<10; i++) {
    addpoint(0, @P + @N * (i*1.1));
}
```
Demonstrates adding new points to geometry using addpoint() with various offset strategies. Shows progression from absolute positions to relative offsets based on @P and @N, culminating in a loop that creates multiple points scaled by normal direction. The addpoint() function doesn't require capturing its return value if you're not using the point number.

### addpoint without assignment [[Ep5, 110:20](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6620s)]
```vex
addpoint(0, @P * (0,1,0));

addpoint(0, @P + (0,5,0));

addpoint(0, @P + @N * 0.1);

for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * (i * 0.1));
}
```
The addpoint() function can be called without assigning its return value to a variable when you don't need to reference the point number later. Examples show creating points at various offsets from the current point position, including along the normal direction, with a loop demonstrating how to create multiple points at incremental distances.

### Creating Points Along Normal Direction [Needs Review] [[Ep5, 110:44](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6644s)]
```vex
addpoint(0, @P + @N * 4);
```
Creates a new point at a position calculated by taking the current point position and offsetting it 4 units in the direction of the point's normal vector. The addpoint function can be called without assigning its return value to a variable.

### Creating Points Along Normal with For Loop [Needs Review] [[Ep5, 112:58](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6778s)]
```vex
for(int i = 0; i < 10; i++){
    addpoint(0, @P + @N * 0.1 * i);
}
```
Uses a for loop to create 10 points along the surface normal, each spaced 0.1 units apart from the previous point. The loop counter 'i' is used to multiply the normal offset, creating points at progressively greater distances from the original point position.

### For loop with addpoint [Needs Review] [[Ep5, 113:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6792s)]
```vex
for(int i = 0; i < len; i++){
    addpoint(0, set * BB * (i * 0.1));
}
```
A for loop iterates from 0 to len, creating points at each iteration using addpoint. The loop counter i serves as an incrementing variable that can be used in calculations, in this case multiplied by 0.1 to space points along a path defined by set * BB.

## Creating Primitives

### Creating primitives with addprim [[Ep5, 114:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6850s)]
```vex
// Create a loop to add 10 points along the normal
for (int i = 0; i < 10; i++) {
    addpoint(0, @P + @N * (i * 0.1));
}

// Create a point and add it to a polyline primitive
int pt = addpoint(0, {0, 1, 0});
addprim(0, 'polyline', @ptnum, pt);
```
Demonstrates creating geometry primitives using addprim() function, which creates a polyline primitive by linking points together as vertices. The addprim() function provides a convenient way to create primitives with a specified type (like 'polyline') without manually managing vertex connections. Polylines are connected lines that aren't closed, distinguished from polygons.

## Adding Points & Geometry

### Creating Points with addpoint [Needs Review] [[Ep5, 114:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6852s)]
```vex
for(int i = 0; i < 4; i++){
    addpoint(0, @P * 0.8 * (1 + 0.1));
}
```
Uses a for loop to create 4 new points using addpoint() on geometry input 0. Each new point's position is based on the current point's @P position, scaled and offset. This demonstrates creating multiple points in preparation for building primitives, as primitives require points to be defined first before they can be linked together as vertices.

### Creating Points for Polyline Primitive [Needs Review] [[Ep5, 115:00](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6900s)]
```vex
int pt = addpoint(0, set(0, 3, 0));
```
Creates a new point at position (0, 3, 0) using addpoint() and stores the point number in an integer variable. This point will be used as part of constructing a polyline primitive by capturing its point ID for later use in an addprim() call.

## Creating Primitives

### Creating polyline between points [[Ep5, 115:24](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6924s)]
```vex
int pt = addpoint(0, {0,1,0});
addprim(0, "polyline", @ptnum, pt);
```
Creates a new point at position {0,1,0} and stores its point number in the variable 'pt', then creates a polyline primitive connecting the current point (@ptnum) to the newly created point. This technique is useful for generating lines or connections between existing and new geometry.

### Creating Lines Between Points [[Ep5, 115:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6934s)]
```vex
int pt = addpoint(0, (0,1,0));
addprim(0, 'polyline', @ptnum, pt);
```
Creates a new point at position (0,1,0) and stores its point number in the variable pt. Then creates a polyline primitive connecting the current point (@ptnum) to the newly created point, effectively drawing a line from each existing point to the shared destination point.

### Creating polylines from points [[Ep5, 116:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6970s)]
```vex
int pt = addpoint(0, {0,0,0});
addprim(0, 'polyline', @ptnum, pt);

int pt = addpoint(0, {0,1,0});
addprim(0, 'polyline', @ptnum, pt);

int pt = addpoint(0, @P+@N);
addprim(0, 'polyline', @ptnum, pt);
```
Creates a new point at a specific position using addpoint(), then connects it to the current point with addprim() to form a polyline primitive. Each iteration creates a new point at the origin (or offset position) and draws a line from the current point to it, resulting in duplicate points at the connection location that would need to be fused.

### Creating Lines from Points Using Normals [Needs Review] [[Ep5, 116:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7002s)]
```vex
int pt = addpoint(0, {0,3,0});
addprim(0, "polyline", @ptnum, pt);

int pt = addpoint(0, @P + @N);
addprim(0, "polyline", @ptnum, pt);

vector pos = @N * noise(@P * @time) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
```
Demonstrates creating polyline primitives from each point by adding a new point offset from the current position. The first example offsets to a fixed position, the second uses the normal direction, and the third applies noise-based displacement to the normal. Note that creating points at the same position may require fusing duplicate points afterward.

### Creating polylines with addpoint [[Ep5, 116:46](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7006s)]
```vex
int pt = addpoint(0, {0,3,0});
addprim(0, "polyline", @ptnum, pt);
```
Creates a new point at position {0,3,0} and connects it to the current point with a polyline primitive. This approach can create duplicate points at shared locations, requiring a fuse operation or alternative logic to avoid point accumulation.

### Creating polylines with noise-driven endpoints [[Ep5, 117:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7056s)]
```vex
int pt = addpoint(0, @P + 0);
addprim(0, 'polyline', @ptnum, pt);

int pt = addpoint(0, {0,3,0});
addprim(0, 'polyline', @ptnum, pt);

int pt = addpoint(0, @P - @N);
addprim(0, 'polyline', @ptnum, pt);

vector pos = rnoise(@Frame) * {1, 0.1, 1};
int pt = addpoint(0, pos);
addprim(0, 'polyline', @ptnum, pt);
```
Demonstrates creating polylines between existing points and newly generated points using addpoint() and addprim(). The final example shows using noise to offset the endpoint position, creating organic-looking lines suitable for grass or hair effects.

### Creating Lines with Noise Offset [[Ep5, 117:38](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7058s)]
```vex
vector pos = @N * noise(@Frame) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```
Creates a new point offset from each original point using noise-modulated normal direction, then connects each original point to its new point with a polyline primitive. The noise varies over time based on frame number, and the offset is scaled differently in each axis to create directional variation suitable for effects like grass or hair.

### Animated Polylines with Noise [[Ep5, 119:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7174s)]
```vex
vector pos = @N + noise(@P - @Time) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```
Creates animated polylines from each point by calculating an offset vector using noise driven by position minus time, scaled non-uniformly, then adding a new point at that offset position and connecting it with a polyline primitive. The noise animation creates waving lines that extend from the surface normal direction.

### Creating animated polylines from points [Needs Review] [[Ep5, 119:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7192s)]
```vex
vector pos = ch3("rotate") * i * {1, 0, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```
Creates a polyline between each existing point and a newly generated point offset by an animated position vector. The position is calculated using a channel reference multiplied by an iterator variable and a mask vector, then added to the current point position. This creates waving lines that animate over time and work on any input geometry.

### Creating Animated Lines from Points [Needs Review] [[Ep5, 119:54](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7194s)]
```vex
vector pos = ch3("parm") * vector(0, 1, 0) + @Time * vector(1, 0, 1);
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```
Creates animated lines by adding a new point offset from each existing point based on a channel parameter and time, then connecting them with polyline primitives. The offset position uses a combination of channel-driven vertical movement and time-based horizontal/depth movement, resulting in waving lines that work on any input geometry.

### Dynamic lines from points [[Ep5, 119:58](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7198s)]
```vex
vector pos = ch('pt') * normalize(@P - @ptnum) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, 'polyline', @ptnum, pt);
```
Creates dynamic waving lines by adding a new point offset from each original point using a normalized direction scaled by a channel parameter and a vector multiplier. Each point spawns a polyline primitive connecting it to the newly created point, producing geometry-dependent line patterns that animate based on the channel value.

### Creating Lines from Points [[Ep5, 120:00](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7200s)]
```vex
vector pos = ch("x") + nrandom(@ptnum) * {1,0.1,1};
int pt = addpoint(0, pos);
addprim(0, "polyline", @ptnum, pt);
```
Creates a new point offset from a channel value with random noise, then connects each original point to its corresponding new point with a polyline primitive. The randomness is scaled differently in each axis (1, 0.1, 1) to create varied line directions.

### Animated Lines from Points [[Ep5, 120:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7208s)]
```vex
vector pos = ch("p") * nrandom(@P + @Time) * {1,0.1,1};
int pt = addpoint(0, @P, pos);
addprim(0, "polyline", @ptnum, pt);
```
Creates animated lines extending from each point by generating a new point with time-varying noise offset, then connecting the original point to the new point with a polyline primitive. The noise is modulated by a channel parameter and scaled differently in Y (0.1) to create waving motion.

### Time-Based Line Generation [Needs Review] [[Ep5, 120:20](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7220s)]
```vex
vector pos = @N * noise(@P * chf("time")) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```
Creates polylines from each point by generating a new point offset along the normal direction, modulated by time-based noise. The noise is scaled non-uniformly to create asymmetric displacement, and each original point is connected to its new point via a polyline primitive.

### Multiple Points Along Normal with Noise [[Ep5, 120:24](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7224s)]
```vex
vector offset, pos;
int pt, pr;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
  offset = curlnoise(@P + @Time) * 0.2;
  pos = @P + @N * i * stepsize + offset;
  pt = addpoint(0, pos);
  addvertex(pr, pt);
}
```
Creates wispy lines by generating multiple points along each input point's normal direction using a for loop. Each point is offset by animated curlnoise, with positions stepped progressively along the normal, then connected into a polyline primitive using addvertex.

### Wispy Geometry Along Normals [Needs Review] [[Ep5, 120:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7230s)]
```vex
vector pos = ch("noise") * noise(@P * @Time) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pt, pt1;
float stepsize;

pt = addpoint(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P + @N * i * stepsize);
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates wispy geometry by generating multiple points along the surface normal direction, with each point offset by curl noise to create organic variation. The loop places 6 points stepping along the normal, adding curl noise offset at each step to create flowing, wispy strands emanating from the surface.

### Wispy Curves with Curlnoise [Needs Review] [[Ep5, 120:58](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7258s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates wispy polyline curves by iterating along each point's normal direction, adding multiple points displaced by curlnoise. Each iteration steps further along the normal while applying time-varying curl noise for organic motion, generating flowing hair-like geometry from surface points.

### Curlnoise wispy hair growth [Needs Review] [[Ep5, 121:00](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7260s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0,"polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P*@Time)*0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0,pos);
    addvertex(0,pr,pt);
}
```
Creates wispy procedural hair-like geometry by generating polylines that grow along normals with curlnoise offset at each step. Multiple points are added along the normal direction, each offset by animated curlnoise to create organic, wispy movement.

### Wispy Lines with Curl Noise [Needs Review] [[Ep5, 121:14](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7274s)]
```vex
vector pos = ch("pt") * {1,0,1};
vector pt = addpoint(0,@P+pos);
addprim(0,"polyline",@ptnum,pt);

vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0,"polyline");
stepsize = 0.5;

for(int i = 0; i < 10; i++) {
    offset = curlnoise(@P-@Time)*0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0,pos);
    addvertex(0,pr,pt);
}
```
Creates multiple points along each point's normal direction using a for loop, adding curl noise offset to each point position for a wispy effect. Uses @N (the implicit normal attribute) to extend the line in the normal direction, with each iteration stepping further along the normal while being perturbed by time-animated curl noise.

### Implicit normals in VEX [Needs Review] [[Ep5, 121:22](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7282s)]
```vex
vector pos = chv('@prim') * (1, 0.3, 1);
int pt = addpoint(0, @P * pos);
addprim(0, 'polyline', @ptnum, pt);

vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P * @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Demonstrates that @N (normal) can be read implicitly in VEX without explicitly creating it beforehand, as Houdini automatically calculates normals for geometry primitives. The code creates polylines growing along the normal direction with curl noise offsets, showing how the implicit normal attribute drives the geometry generation.

### Polyline with Curl Noise Offset [Needs Review] [[Ep5, 121:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7292s)]
```vex
vector pos = v@P;
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P - @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates polylines extending from each point along the normal direction with curl noise offsets. The loop generates multiple points along the normal vector, applying curl noise displacement based on world position and time, then connects them into a polyline primitive using addvertex.

### Implicit normals in geometry creation [Needs Review] [[Ep5, 121:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7312s)]
```vex
vector pos, offset;
int pr, pt;
float stepsize;

pr = addprim(0,"polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P - @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Demonstrates how Houdini uses implicit point normals when generating geometry along the @N direction. The code creates a polyline by iterating and adding points offset by the normal and curl noise, showing how normals affect geometry generation even when not explicitly set as vertex normals.

### Normals in Geometry Creation [Needs Review] [[Ep5, 122:00](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7320s)]
```vex
vector pos = ch("pos") * {1,0,1};
int pt = addpoint(0,@P+pos);
addprim(0,"polyline",@ptnum,pt);

vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0,"polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P-@Time)*0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0,pos);
    addvertex(0,pr,pt);
}
```
Demonstrates how implicit normals on grid geometry are used when creating new geometry with @N in loops. The code creates polylines that extend along the normal direction with curl noise offset, showing that point normals (whether explicitly set or implicitly available) drive the geometry generation direction.

## Adding Points & Geometry

### Polyline with Curl Noise Offset [[Ep5, 122:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7330s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addpoint(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < @i+1; i++) {
    offset = curlnoise(@P - @Time * i) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates a polyline primitive by iterating and adding points along the normal direction with curl noise displacement. Each point position is calculated by offsetting from @P along @N multiplied by the iteration count and step size, then adding animated curl noise for organic variation.

## Creating Primitives

### Point vs Vertex Normals in Geometry Creation [Needs Review] [[Ep5, 122:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7332s)]
```vex
vector pos = (M * noise(@P * pTime)) * {1,0.3,1};
int pt = addpoint(0,@P+pos);
addprim(0, "polyline", @ptnum,pt);

vector pos = (M * noise(@P * pTime)) * {1,0.1,1};
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum,pt);

vector offset, pos;
int pt, pr;
float stepsize;

pr = addprim(0,"polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P * pTime) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0,pos);
    addvertex(0,pr,pt);
}
```
Demonstrates the difference between point normals and vertex normals when creating geometry procedurally. The code shows how normals are implicitly set during point creation and can affect subsequent calculations whether explicitly defined or not. Setting normals at the point level versus vertex level produces different results in geometry generation workflows.

### Curl Noise Trail Generation [[Ep5, 122:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7354s)]
```vex
vector pos = @P;
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", pt, @ptnum, pt);

vector pos = @P + noise(@P + @Time) * {1, 0, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(pos) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Demonstrates progressive techniques for creating polyline trails from points. The final version uses a for loop to generate curved trails by stepping along the point normal direction while applying curl noise offsets at each step, creating organic curved geometry.

## Adding Points & Geometry

### Normal calculation in rotation [Needs Review] [[Ep5, 122:38](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7358s)]
```vex
vector pos = ch * rotation(0, @N*len) * {1,0,0,1};
int pt = addpoint(0, @P + pos);
addvertex(0, "polyline", @ptnum, pt);
```
Creates a rotated position vector using the point normal and rotation matrix, then adds a new point at the transformed position and connects it to form a polyline. The normal attribute is implicitly used in the rotation calculation, affecting how the geometry is oriented even when not explicitly set beforehand.

## Creating Primitives

### Normal Attribute in Polyline Generation [Needs Review] [[Ep5, 122:40](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7360s)]
```vex
vector offset, pos;
int pt;
float stepsize;

pt = addpoint(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < @id + 1; i++) {
    offset = curlnoise(@P - @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}

vector @s = @noise(@P * @Time) * {1, 0.3, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);
```
Demonstrates how the @N (normal) attribute is implicitly set and used when generating polylines with addpoint. The discussion explores whether the normal attribute is automatically calculated or needs to be explicitly referenced, showing subtle differences in behavior depending on how @N is accessed during point creation.

### Curl Noise Polylines with Normals [Needs Review] [[Ep5, 122:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7370s)]
```vex
vector offset = @nrelpe(@OpInput1)*{1,0.3,1};
int pt = addpoint(0,@P+pos);
addprim(0,"polyline",@ptnum,pt);

vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0,"polyline");
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P-@Time)*0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0,pos);
    addvertex(0,pr,pt);
}
```
Creates polyline primitives by iterating through points and adding vertices displaced by both the point normal and curl noise. The discussion explores whether normals need to be explicitly set before use or if they're implicitly calculated, concluding that explicitly setting normals beforehand gives more control over the displacement direction.

### Extruding Polylines with Normals [Needs Review] [[Ep5, 122:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7372s)]
```vex
vector pos = chv("pos");
int pt = addpoint(0, @P);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P - @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates extruded polyline geometry by iterating along point normals with curl noise displacement. The discussion focuses on how normals affect the extrusion direction and whether they need to be explicitly set or are implicitly calculated by the geometry operations.

### Normal Calculation Methods in Polyline Generation [Needs Review] [[Ep5, 123:06](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7386s)]
```vex
vector TOF = @noise(@Frame)*{1,0,1};
int pt = addpoint(0,@P+pos);
addvertex(0, prim, pt);

vector offset, pos;
int pr, pt;
float distance;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 0; i++) {
    offset = curlnoise(@P+TOF)*0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0,pos);
    addvertex(0,pr,pt);
}
```
Demonstrates how normal calculations can vary based on whether normals are set explicitly or calculated implicitly from geometry. The example shows polyline generation with displacement along normals, highlighting that pre-computing normals yields more predictable results than relying on implicit vertex normals.

### Normal Calculation Methods for Displacement [Needs Review] [[Ep5, 123:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7388s)]
```vex
vector pos = chv("pos");
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pt, pt1, pr;
float bias = 0;
float stepsize = 0.5;

pt = addpoint(0, @P);
pr = addprim(0, "polyline");

for (int i = 0; i < 10; i++) {
    offset = curlnoise(pos) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Demonstrates how normals can be calculated implicitly by Houdini based on vertex data versus being explicitly set beforehand. Different normal calculation methods can slightly alter displacement results, so explicitly setting normals upstream provides more predictable control for displacement operations along normal directions.

### Polyline growth with curl noise [Needs Review] [[Ep5, 123:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7390s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P + i * stepsize) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates a polyline primitive that grows from each point along its normal direction, with curl noise applied as offset at each step. The loop generates 10 points per polyline, spaced by stepsize intervals, with the curl noise evaluated at offset positions to create organic, flowing trajectories.

### Growing Lines with Curl Noise [Needs Review] [[Ep5, 123:26](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7406s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for (int i = 0; i < 10; i++) {
    offset = curlnoise(@P * @Time) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates polylines that grow from each input point along the normal direction with curl noise displacement applied at each step. Uses a for loop to iteratively add points along a path, combining directional growth (@N * i * stepsize) with animated curl noise offset for organic movement.

### Declaring Variables for Curve Generation [Needs Review] [[Ep5, 123:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7414s)]
```vex
vector pos = (M * rotate(@P * ramp * {1,0,1}, 1));
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum, pt);

vector pos = (M * rotate(@P * @Tramp) * {1,0,1});
int pt = addpoint(0, @P * pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0;

for (int i = 0; i < 10; i++) {
  offset = curlnoise(pos) * M * 0.2;
  pos = @P + @N * i * stepsize + offset;
  pt = addpoint(0, pos);
  addvertex(0, pr, pt);
}
```
Setting up variables for a procedural curve generation system using a for loop. The code declares vector, integer, and float variables to track position offsets, primitive and point numbers, and iteration step size for creating polylines with curl noise displacement.

## Adding Points & Geometry

### Creating polylines with curl noise [Needs Review] [[Ep5, 124:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7470s)]
```vex
vector offset, pos;
int pr, pt;
float stepSize;

pr = addpoint(0, "polyline");
stepSize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(@P * @time + 174.2);
    pos = @P + @N * i * offset;
    pt = addpoint(0, pos);
    setpointattrib(0, "polyline", pr, pt, "append");
}
```
Creates a polyline primitive for each point, then iteratively generates new points along the normal direction modified by curl noise, appending them to the polyline. The offset is calculated using curl noise sampled at the current point position multiplied by time for animation, creating organic flowing lines from each point.

## Creating Primitives

### Curl Noise Trail Generator [[Ep5, 125:56](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7556s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @time * 1) * 0.2;
    pos = @P + i * stepsize * offset;
    pt = addpoint(0, pos);
    addvertex(pr, pt);
}
```
Creates a polyline trail by iterating 6 times, calculating curl noise at animated positions offset by the loop iteration, and adding points along the noise-driven path. Each iteration adds a new vertex to the polyline, with the position offset by the iteration count multiplied by stepsize and the curl noise direction.

### Curl noise offset polyline [[Ep5, 127:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7632s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
}
```
Creates a polyline by iterating 6 times and adding points at positions offset from the current point along its normal direction, scaled by the iteration index and step size, with additional randomization from curl noise based on position and time. Each point's offset uses curl noise to create a flowing, turbulent displacement that evolves over time.

### Creating Polyline with Offset Points [[Ep5, 127:54](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7674s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time * i) * 0.2;
    pos = @P + (@N * i * stepsize) + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates a polyline primitive with six points positioned along the normal direction from the original point. Each point is offset by a combination of stepsize-scaled normal displacement and curlnoise-based randomization driven by time and loop index. The addvertex function connects each newly created point to the polyline primitive in sequence.

### Growing Polylines with Curvoise [[Ep5, 127:56](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7676s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curvoise(@P - @Time * i) * 0.2;
    pos = @P + (@N * i * stepsize) + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates a 6-point polyline growing from each input point along its normal direction with curvoise-based randomization. For each iteration, calculates an offset using animated curvoise noise, positions the new point along the normal scaled by step size plus the offset, adds the point, and connects it to the polyline primitive using addvertex.

### Procedural Fur Using Polylines [Needs Review] [[Ep5, 128:44](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7724s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates procedural fur-like polylines by generating a series of points along the normal direction from each input point. Each point's position is offset by animated curl noise to create a wavy, organic appearance, with points connected via vertices to form polyline primitives.

### Procedural Grass with Animated Curvature [[Ep5, 128:46](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7726s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.1;

for(int i=0; i<@i; i++) {
    offset = curvature(@P - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates procedural grass blades by generating polylines that extend from each point along its normal direction. Uses curvature noise with time animation to create wavy, organic-looking grass that moves, adding multiple points per iteration and connecting them into polylines.

## Adding Points & Geometry

### Animated Fur Using Curlnoise [Needs Review] [[Ep5, 128:56](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7736s)]
```vex
for (int i = 0; i < chi('i'); i++) {
    vector offset = curlnoise(f@Time*ch('z'))*ch('z');
    vector pos = @P + @N * i * chf('size') + offset;
    int pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates animated fur strands by iterating and generating points along the normal direction, offset by curlnoise based on time. Each iteration adds a new point at a position calculated from the original point, offset by the normal multiplied by step size and curlnoise displacement. The resulting wavy grass-like or fur effect responds dynamically to the time-based noise animation.

### Curl Noise Fur Displacement [Needs Review] [[Ep5, 128:58](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7738s)]
```vex
for (int i = 0; i < nprims(@opinput1); i++) {
    offset = curlnoise(@P[elem=i]) * 0.2;
    pos = @P + @N * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, prim, pt);
}
```
Creates wavy, organic-looking fur by iterating over primitives and displacing new points using curl noise combined with the normal direction and a step size. Each iteration adds a point offset by both the normal-scaled step size and curl noise-based offset, then adds it to the primitive.

### Curl Noise Grass Generation [Needs Review] [[Ep5, 129:00](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7740s)]
```vex
for (int i = 0; i < chi(""); i++) {
    offset = curlnoise((@P+i*chf("amp1"))*chf("freq2"));
    pos = @P + @N * chf("stepsize") + offset;
    pt = addpoint(0, pos);
    addvertex(0, @primnum, pt);
}
```
Generates wavy grass-like geometry by iterating to create points displaced by curl noise. Each iteration adds a point offset from the surface normal plus curl noise, creating organic flowing strands. The curl noise uses point position and iteration count to create varied turbulent displacement.

## Creating Primitives

### Animated Fur Using Curlnoise [Needs Review] [[Ep5, 129:20](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7760s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i = 0; i < 1; i++) {
    offset = curlnoise(pos - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates animated grass-like fur strands by generating polyline primitives that extend from surface normals, with curlnoise-based displacement animated by @Time. Each strand is built using the older workflow of creating an empty primitive, then adding points and vertices to it sequentially.

### Dynamic polyline growth with loop [Needs Review] [[Ep5, 130:44](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7844s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<@i; i++) {
    offset = curlnoise(pt - @Time * 1) * 0.2;
    pos = @P + ch('i') * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates a polyline primitive that grows dynamically by adding points in a loop, with each point positioned using a stepped offset plus curl noise displacement. The loop iterates based on a channel value, making the number of points easily adjustable without rewriting code, demonstrating a flexible approach to procedural geometry generation.

### Loop-based Polyline Creation [Needs Review] [[Ep5, 130:46](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7846s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<10; i++) {
    offset = curlnoise(@P - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(pr, pt);
}
```
Demonstrates building a polyline procedurally using a loop to add vertices incrementally. Each iteration adds a point offset along the normal with curl noise displacement, then adds that point as a vertex to the polyline primitive. This approach is more flexible than manually specifying each point, as the loop count can be easily changed.

### For loop polyline generation [[Ep5, 131:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7876s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, "polyline");
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(pr, pt);
}
```
Uses a for loop to procedurally generate a polyline with multiple points displaced by curl noise, demonstrating how loops make geometry creation more flexible than manually adding individual points. Each iteration creates a new point along the normal direction with an animated curl noise offset, then adds it as a vertex to the polyline primitive.

### Creating polylines with for loops [[Ep5, 131:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7890s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<61; i++) {
    offset = curlnoise(@P - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    addvertex(pr, pt);
}
```
Demonstrates creating a polyline primitive using a for loop that generates points along the surface normal direction, with curlnoise-based offset for variation. Shows the workflow of addprim, addpoint, and addvertex working together to build geometry procedurally, which is more flexible than manually creating individual points when dealing with larger point counts.

### For Loop Geometry Creation [[Ep5, 131:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7896s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time * i) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    setpointattrib(0, pr, pt);
}
```
Creates a polyline primitive with 6 points using a for loop, where each point is offset along the normal direction with curl noise distortion animated by time. Demonstrates combining addprim, addpoint, and setpointattrib to build geometry procedurally within a loop.

### For Loop Geometry Creation [Needs Review] [[Ep5, 131:48](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7908s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time + i) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    setpointattrib(0, pr, pt);
}
```
Creates a polyline primitive with multiple points using a for loop that iterates 6 times. Each iteration adds a new point offset from the current point position along the normal direction, with curlnoise adding animated variation, then connects the point to the polyline using setpointattrib (which should be addvertex).

### Creating Polylines with Curl Noise [Needs Review] [[Ep5, 131:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7912s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time * 1) * 0.2;
    pos = @P + @P * i * stepsize + offset;
    pt = addpoint(0, pos);
    setpointattrib(0, pr, pt);
}
```
Creates a polyline primitive with six points, positioning each point along a path influenced by curl noise that animates over time. The loop adds points sequentially, applying both a stepped offset and a noise-based displacement to create an organic, flowing line.

### Creating Polylines with Different Primitive Types [[Ep5, 132:00](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7920s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    setpointattrib(0, pr, pt);
}
```
Creates a polyline primitive and adds six points to it, where each point position is offset by curl noise and stepped along the normal direction. The code demonstrates using the 'polyline' primitive type with addprim(), which creates an open polygon rather than a closed one.

### Creating polyline with curl noise [Needs Review] [[Ep5, 132:18](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7938s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.01;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time * 1) * 0.2;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    setprimvertex(0, pr, pt, -1);
}
```
Creates a polyline primitive by adding six points in a loop, positioning each point along the normal direction with a small step size, then applying curl noise offset that animates over time. Each new point is added to the polyline primitive using setprimvertex to build the connected line.

### Creating Polyline Primitives with Curl Noise [[Ep5, 132:22](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7942s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<61; i++) {
    offset = curlnoise(@P - @Time + i) * 0.2;
    pos = @P + (@N * i * stepsize + offset);
    pt = addpoint(0, pos);
    addvertex(pr, pt);
}
```
Creates a polyline primitive by adding 61 points along the normal direction with curl noise offset applied. Each point is positioned based on the current point position, normal direction scaled by stepsize, and a time-animated curl noise displacement.

### Creating Polylines with Curl Noise [Needs Review] [[Ep5, 132:38](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7958s)]
```vex
int pt = addpoint(0, @P - @N);
addprim(0, "polyline", @ptnum, pt);

vector pos = @N * noise(@P * @Frame) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
addprim(0, "polyline", @ptnum, pt);

vector offset, pos;
int pt, p;
float stepsize;

p = addprim(0, "polyline");
stepsize = 0.5;

for(int i = 0; i < 10; i++) {
    offset = curlnoise(@P * @Frame) * 0.2;
    pos = set(0, i * stepsize + offset);
    pt = addpoint(0, pos);
    addvertex(0, p, pt);
}
```
Demonstrates creating polyline primitives procedurally using addprim(), addpoint(), and addvertex(). The first examples show simple point-to-point connections, while the final example creates a multi-segment polyline using a for loop with curl noise to offset each vertex position along the Y axis.

### Creating Polylines with Curl Noise Offset [[Ep5, 132:46](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7966s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i=0; i<6; i++) {
    offset = curlnoise(@P - @Time + i) * 0.2;
    pos = @P + (@N * i * stepsize + offset);
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```
Creates a polyline primitive with 6 points by iterating through a loop. Each point position is calculated based on the point's position offset along its normal, with additional curl noise displacement that varies over time and per iteration. The points are added to the polyline using addpoint and addvertex.

### Creating Point and Polyline Primitive [[Ep5, 133:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8022s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pt = addpoint(0, {0,0,0});
pr = addprim(0, "polyline", pt);
```
Declares variables for procedural geometry creation, then creates a point at the origin and adds a polyline primitive that references that point. The point holds the position data while the polyline primitive stores the connectivity information.

### Creating Primitives with Points [[Ep5, 134:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8056s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pt = addpoint(0, {0,3,0});
pr = addprim(0, "polyline", pt);
```
Demonstrates creating a primitive by first adding a point at a specific position using addpoint(), then creating a polyline primitive attached to that point using addprim(). The code shows variable declarations for tracking point and primitive IDs, with the point positioned at {0,3,0}.

### Creating Circle Primitives with addprim [[Ep5, 135:06](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8106s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pt = addpoint(0, {0,3,0});
pr = addprim(0, "circle", pt);
```
Demonstrates creating a circle primitive using addprim() with the "circle" type, showing that addprim() can create procedural primitive types beyond just polylines and polygons. The circle primitive is added at a specific point location, providing a way to visualize or create circular geometry procedurally.

### Seaweed Example Setup with Random Deletion [Needs Review] [[Ep5, 157:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9430s)]
```vex
if(rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprims(0, @primnum, 1);
}

// spirally seaweed using sin and cos
vector offset, pos;
int n, ps;
float stepsize;
float x, y, inc;
int pr = addprim(0, "polyline");
stepsize = 0.5;
```
Creates seaweed geometry by randomly removing primitives based on a cutoff value, then initializes variables for generating spiral seaweed patterns using sine and cosine functions. The code sets up a polyline primitive and defines step size for iterative point creation.

### Seaweed spiral growth animation [Needs Review] [[Ep5, 157:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9432s)]
```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removepoint(0, @primnum, 1);
}

// spirally scanned using sin and cos
vector offset, pos;
int pr, pt;
int ptmax;
float x, y, inc;
float stepsize;
pr = addprim(0, 'polyline');
stepsize = 0.5;

for (int i = 0; i < 50; i++) {
    inc = @ptnum * stepsize;
    x = cos(i * 0.4 + @Time * inc);
    y = sin(i * 0.4 + @Time * inc);
    offset = set(x, y, 0) * 0.1 * i;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    setpointattrib(0, "P", pt, pos);
    addvertex(0, pr, pt);
}
```
Creates animated spiraling seaweed tendrils by generating polylines that grow from each point, using sine and cosine functions to create spiral offsets that vary with time and point number. The code first randomly removes some primitives based on a seed and cutoff parameter, then builds spiral geometry by iteratively adding points along the normal direction with time-based spiral displacement.

### Seaweed with random culling and spiral offset [Needs Review] [[Ep5, 157:16](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9436s)]
```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')) {
    removeprims(0, @primnum, 1);
}

// spirally seaweed using sin and cos
vector offset, pos;
int pr, pt;
int nseg = 50;
float x, y, inc, stepsize;
pr = addprim(0, 'poly');
stepsize = 0.5;

for (int i = 0; i < nseg; i++) {
    inc = @ptnum * stepsize;
    x = cos(i * 0.4 * @P[1] * inc);
    y = sin(i * 0.4 * @P[1] * inc);
    offset = set(x, 0, y) * 0.1 * i;
    pos = @P + @N * i * stepsize + offset;
    pt = addpoint(0, pos);
    setpointattrib(0, "P", pt, pos);
}
```
This code randomly removes primitives based on a probability threshold, then creates spiraling seaweed geometry by generating points along a path using sine and cosine offsets. Each point is positioned along the normal direction with a circular spiral offset that increases with distance from the root.

## Adding Points & Geometry

### Near Points Geometry Creation [[Ep8, 59:56](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3596s)]
```vex
int pts[] = nearpoints(1,@P,ch('d'),25);
int pt;
vector pos;
foreach (pt; pts) {
    pos = point(1,"P",pt);
    addpoint(0,pos);
}
```
Finds up to 25 nearby points within a channel-controlled distance from the current point's position, then creates new geometry points at each found point's location by reading their positions and adding them to the output geometry. This technique can replicate or sample from nearby geometry, offering an alternative to tools like the Attribute Interpolate SOP.

## See Also
- **VEX Common Patterns** (`vex_patterns.md`) -- geometry creation patterns
- **VEX Functions Reference** (`vex_functions.md`) -- addpoint, addprim signatures
