# Joy of VEX: Geometry Operations

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Geometry Operations

### Cone Height Manipulation with Distance [[Ep2, 20:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1202s)]
```vex
float d = length(@P);
@P.y = d * 0.2;
```
This snippet calculates the distance of each point from the origin using length(@P), then uses that distance to set the Y position, creating a cone shape. By multiplying the distance by different values (like 0.2), adding offsets, or inverting with negative values, you can control the cone's height, orientation, and placement.

### Distance-based displacement with scaling and offset [[Ep2, 20:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1226s)]
```vex
float d = length(@P);
@P.y = d * 0.2 - 10;
```
This code calculates the distance from the origin using length(@P), then uses that distance to displace points vertically with a scale factor of 0.2 and an offset of -10. The scaling reduces the magnitude of the displacement while the subtraction shifts the entire displaced surface downward in Y.

### Distance-based height manipulation [[Ep2, 21:36](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1296s)]
```vex
float d = length(@P);
@P.y = clamp(d, 0, 7);
```
Demonstrates various ways to manipulate point height based on distance from origin, including linear mapping, squaring, inversion with offset, and clamping. The distance from origin is calculated using length() and applied to the Y position with different mathematical operations to create various surface shapes.

### Y-Position from Distance with Scale [[Ep2, 82:34](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4954s)]
```vex
float d = length(@P);
d *= ch("scale");
@P.y = d;
```
Calculates the distance from the origin to each point using length(@P), multiplies it by a channel parameter called "scale", and assigns the result to the Y component of the point position. This creates a funnel-like shape where each point's height is determined by its distance from the origin, controlled by a spare parameter.

### Distance-based Y displacement [[Ep2, 93:04](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5584s)]
```vex
float d = length(@P);

@P.y = d;
```
Calculates the distance from the origin to each point using length(@P) and assigns that distance value to the Y component of the point's position. This creates a displacement effect where points are moved vertically based on their distance from the origin, useful for creating distance-based deformations or as a setup for stepped graph effects.

### Distance-Based Y Displacement [[Ep3, 49:22](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2962s)]
```vex
int pt = nearpoint(1, @P);
@Cd = point(1, "Cd", pt);
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
@P.y = -d;
```
Finds the nearest point on the second input, reads its color and position, calculates the distance between the current point and that nearest point, then uses that distance to displace the Y component of the current point position negatively. This creates a distance-based deformation effect while also transferring color attributes.

### Distance-Based Point Displacement [[Ep3, 49:56](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2996s)]
```vex
int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
@P.y = d;
```
This code finds the nearest point from the second input to each point on the first input, calculates the distance between them, and uses that distance value to displace the Y-position of each point. The result creates a height field where the Y-value represents the proximity to the nearest point on the reference geometry.

### Shifting Points by Distance to Nearest Neighbor [[Ep3, 50:08](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3008s)]
```vex
int pt = nearpoint(1, @P);
@Cd = point(1, 'Cd', pt);
vector pos = point(1, 'P', pt);
float d = distance(@P, pos);
@P.y = -d;
```
Finds the nearest point on the second input, reads its position and color, then calculates the distance between the current point and that nearest point. The Y position of the current point is shifted downward by this distance value, creating a displacement effect based on proximity to the reference geometry.

### Cross Product Normal Reorientation [[Ep4, 23:04](https://www.youtube.com/watch?v=66WGmbykQhI&t=1384s)]
```vex
@N = cross(@N, {1, -1, 0});
```
Reorients point normals by computing the cross product between the existing normal and a custom axis vector {1, -1, 0}. This causes normals to rotate around the specified axis direction, creating a twirling or combing effect where all normals align relative to that axis rather than their original orientation.

### Cross product for hair combing [[Ep4, 24:04](https://www.youtube.com/watch?v=66WGmbykQhI&t=1444s)]
```vex
vector tmp = cross(@N, {0, 1, 0});
@N = cross(@N, tmp);
```
Creates a temporary vector by crossing the point normal with the up vector, then crosses the normal with this temp vector to produce a combed-down effect. This technique is commonly used as an initial step in grooming operations to create a gravity-based default orientation for hair or fur.

### Gravity-Based Vector Combing [[Ep4, 24:10](https://www.youtube.com/watch?v=66WGmbykQhI&t=1450s)]
```vex
vector tmp = cross(@N, {0,1,0});
@N = cross(tmp, @N);
```
Creates a gravity-based combing effect by computing two successive cross products to align normals downward. First crosses the normal with the up vector to get a perpendicular vector, then crosses that result back with the original normal to create downward-pointing vectors. This technique is commonly used as an initial step in grooming operations.

### Double Cross Product for Grooming [[Ep4, 24:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=1456s)]
```vex
vector tmp = cross(@N, {0,1,0});
tmp = cross(@N, tmp);
tmp = cross(@N, tmp);
tmp = cross(@N, tmp);
@N = cross(@N, tmp);
```
Demonstrates a double cross product technique commonly used in grooming operations to orient all normals downward, creating a gravity-based directional flow. The operation repeatedly crosses the normal with a temporary vector to achieve consistent downward-pointing vectors across the geometry.

### Vector Subtraction Between Points [[Ep4, 34:24](https://www.youtube.com/watch?v=66WGmbykQhI&t=2064s)]
```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@N = b - a;

vector a = @P;
vector b = point(1, "P", 0);
```
Demonstrates vector subtraction by reading positions from two different input points using the point() function. The normal attribute (@N) is set to the difference between point 1's position and point 0's position, creating a direction vector. An alternative approach stores the current point position in vector a while still reading point 1's position.

### Vector Subtraction with Points [Needs Review] [[Ep4, 34:28](https://www.youtube.com/watch?v=66WGmbykQhI&t=2068s)]
```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@i = b - a;

vector a = @P;
vector b = point(1, "P", 0);
```
Demonstrates vector subtraction by reading positions from two different input points using the point() function. The first section shows subtracting positions from two separate geometry inputs (inputs 0 and 1), while the second section shows using the current point's position (@P) and comparing it to a point from another input.

### Point Referencing for Direction Vectors [[Ep4, 37:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=2236s)]
```vex
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);

@N = b - a;

vector a = @P;
vector b = point(1, 'P', 0);

@N = b - a;
```
Demonstrates two approaches to creating direction vectors: first using point() to read from two explicit point positions, then using @P for the current point position and point() to reference a specific external point. The second method makes all points on a sphere orient their normals toward a single reference point, useful for effects like wires connecting to a target or radial alignment.

### Point-to-Point Vector Direction [[Ep4, 37:26](https://www.youtube.com/watch?v=66WGmbykQhI&t=2246s)]
```vex
vector a = @P;
vector b = point(1, 'P', 0);

@N = b - a;
```
Creates vectors pointing from every point on a sphere toward a single reference point by subtracting the current point position from a target point position. The vector a represents the current point being processed, vector b reads the position of point 0 from the second input, and their difference (b-a) creates a direction vector stored in @N that points from each sphere point toward the reference point.

### Point-to-Point Vector Targeting [[Ep4, 37:28](https://www.youtube.com/watch?v=66WGmbykQhI&t=2248s)]
```vex
vector a = @P;
vector b = point(1, 'P', 0);

@N = b - a;

vector origin = point(1, 'P', 0);
@v = (@P - origin);
```
Creates vectors from all points in the geometry pointing toward a single reference point from the second input. By computing @N = b - a (where b is the reference point and a is the current point), every point's normal becomes a direction vector pointing to that target location. This can be used for creating wire-like effects or radial connections from multiple points to a single target.

### Vector from Point to Target [[Ep4, 37:42](https://www.youtube.com/watch?v=66WGmbykQhI&t=2262s)]
```vex
vector p = v@P;
vector b = point(1, "P", 0);

v@l = b - p;

vector origin = point(1, "P", 0);
@v = (p - origin);
```
Creates vectors pointing from each point in the geometry to a single target point on the second input. By calculating 'b - p', each point gets a vector that connects to the reference point, useful for creating wire-like effects. Reversing to 'p - origin' creates vectors pointing away from the target instead.

### Vector Subtraction for Direction [[Ep4, 37:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=2266s)]
```vex
vector a = @P;
vector b = point(1, 'P', 0);

@N = b - a;

// Alternative: vectors pointing away from origin
vector origin = point(1, 'P', 0);
@v = @P - origin;

// Reversed direction
@N = a - b;
```
Demonstrates using vector subtraction to create vectors that point from each point toward (or away from) a specific reference point in space. By computing b-a, all points get normals pointing toward the reference point; reversing to a-b makes them point away. This technique is useful for creating radial effects, wire connections, or directional fields.

### Multiplying Normals by Vector [[Ep4, 45:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=2716s)]
```vex
@N *= chv('scale_vec');
```
Multiplies the normal vector by a vector channel parameter to scale and flip normals non-uniformly. Stretching normals in the x-axis and negating in the z-axis creates interesting effects where normals pointing in different directions are affected differently, causing some to flip inward while others maintain their original direction.

### Relative Bounding Box Positioning [[Ep4, 48:10](https://www.youtube.com/watch?v=66WGmbykQhI&t=2890s)]
```vex
@P = normalize(@P);

@Cd = relpointbbox(0, @P);

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

s@v = chv('scalevec');
```
Demonstrates using relpointbbox() to get a point's relative position within the bounding box of geometry. The function returns a vector with 0-1 values for each axis, which can be used directly as color or accessed by component (e.g., bbox.y). The normalize(@P) line appears to be preparatory work from earlier in the tutorial.

### Normalizing Points and Bounding Box [[Ep4, 48:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=2896s)]
```vex
@P = normalize(@P);

@Cd = relpointbbox(0, @P);

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;
```
Demonstrates normalizing point positions to create a sphere-like distribution, then using relpointbbox to get relative bounding box coordinates for coloring. The function returns a vector with normalized (0-1) position within the bounding box, with individual components (x, y, z) accessible for selective mapping.

### Removing Primitives Conditionally [[Ep5, 132:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7954s)]
```vex
removepoint(0, @ptnum);

removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) * ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
```
Demonstrates various ways to remove geometry elements using removepoint() and removeprim() functions. The conditional example uses rand() with a channel reference to randomly delete primitives based on a threshold, where the third argument to removeprim() controls whether to keep or delete the points (1=delete points, 0=keep points).

### Removing Points with Random Threshold [[Ep5, 135:24](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8124s)]
```vex
removepoint(0, @ptnum);

// removepoint(int geohandle, int point_number)
// removepoint(int geohandle, string pointgroup, int and_or_prims)

if (rand(@ptnum) < ch('cutoff')) {
    removepoint(0, @ptnum);
}

if (rand(@ptnum * ch('seed')) < ch('cutoff')) {
    removepoint(0, @ptnum);
}
```
The removepoint() function deletes points from geometry by specifying a geometry handle and point number. By combining it with rand() and a channel-referenced threshold value, you can randomly remove points with controllable probability. Adding a seed multiplier to the rand() function allows for variation in the random pattern.

### Removing Geometry with VEX [[Ep5, 135:28](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8128s)]
```vex
removepoint(0, @ptnum);

removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}

if (rand(@ptnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
```
Demonstrates how to delete points and primitives using removepoint() and removeprim() functions. The removeprim() function takes a third argument (0 or 1) to control whether to keep points when deleting primitives. Random deletion can be controlled using rand() with a channel reference for cutoff threshold and optional seed parameter.

### Removing Primitives with Points [[Ep5, 136:36](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8196s)]
```vex
removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

if (rand(@ptnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}
```
The removeprim() function deletes primitives from geometry, with the third argument controlling whether associated points are kept (1) or deleted (0). This can be combined with conditional logic using rand() to randomly remove primitives based on a probability threshold controlled by a channel reference.

### Removing Primitives with Conditions [[Ep5, 136:38](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8198s)]
```vex
removeprim(0, @ptnum, 1);

removeprim(0, @primnum, 1);

removeprim(0, @primnum, 0);

if (rand(@ptnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

if (rand(@ptnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}
```
Demonstrates using removeprim() to delete primitives, with control over whether to keep (0) or delete (1) associated points. Shows progressive examples including conditional removal based on random values compared against a channel slider, and seeded randomness for reproducible results.

### Random Primitive and Point Deletion [[Ep5, 140:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8432s)]
```vex
// Random primitive deletion in Prim Wrangle
if(rand(@primnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

// Point deletion example
removepoint(0, @ptnum);

// Remove primitive with points
removeprim(0, @primnum, 1);

// Remove primitive without points
removeprim(0, @primnum, 0);

// Random point deletion (incorrect - should use @ptnum not @primnum)
if(rand(@ptnum) < ch('cutoff')){
    removepoint(0, @primnum, 1);
}

// Random point deletion with seed
if(rand(@ptnum, ch('seed')) < ch('cutoff')){
    removepoint(0, @ptnum, 1);
}
```
Uses rand() to generate a value between 0 and 1 for each primitive or point, comparing it against a threshold parameter to randomly delete geometry. The removeprim() function's third argument (0 or 1) controls whether to also delete the associated points. The code shows both primitive-based deletion (in Prim Wrangle) and point-based deletion patterns, with the last example demonstrating seeded randomness for reproducible results.

### removeprim and removepoint modes [Needs Review] [[Ep5, 142:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8552s)]
```vex
// Remove primitive with default mode
if(rand(@primnum) < ch('cutoff')){
    removeprim(0, @primnum, -1);
}

// Remove only the primitive, keep points
removeprim(0, @primnum, 1);

// Remove primitive and unused points
removeprim(0, @primnum, 0);

// Remove point (note: using @primnum incorrectly)
if(rand(@ptnum) < ch('cutoff')){
    removepoint(0, @primnum, -1);
}

// Seeded random removal with proper syntax
if(rand(@ptnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, -1);
}
```
Demonstrates the different modes of removeprim() function, including the third argument which controls whether to keep points (-1 for default, 0 to remove unused points, 1 to keep all points). Shows random-based removal using rand() with both single-argument and seeded variants, though one example incorrectly uses @primnum in a point context with removepoint().

### Setting Up Vector for Copy to Points [[Ep6, 44:48](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2688s)]
```vex
v@up = {0,0,1};

v@up = {0,1,0};
```
Demonstrates setting the @up vector attribute to control the rotational orientation of copied geometry. The first example sets up to world Z-axis {0,0,1}, rotating the copied boxes so their local Y-axis aligns with world Z. The second example shows an alternative orientation with up pointing to world Y {0,1,0}.

### Animating Up Vector for Copy Orientation [[Ep6, 46:16](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2776s)]
```vex
v@up = {0,0,1};

v@up = set(sin(@Time), 0, cos(@Time));
```
Creates an animated up vector that rotates around the Y axis using sine and cosine of @Time. When combined with the normal vector, this provides complete rotational control for copied geometry by defining two perpendicular orientation vectors. The up vector starts as static {0,0,1} then becomes animated, causing copied shapes to rotate in sync with the time-based circular motion.

### Resetting Primitive Transform Intrinsic [[Ep7, 131:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7888s)]
```vex
matrix3 m = ident();
setprimintrinsic(0, "transform", 0, m);
```
Creates an identity matrix and uses setprimintrinsic() to reset a primitive's transform intrinsic back to its default state. This affects the packed primitive's transformation matrix but does not modify the underlying point position (@P), which must be set separately to fully reset geometry to its original state.

### Resetting Primitive Transform Intrinsic [[Ep7, 131:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7890s)]
```vex
matrix3 m = ident();
setprimintrinsic(0, "transform", 0, m);
@P = {0,0,0};
```
Demonstrates resetting a primitive's transform intrinsic to identity using setprimintrinsic() and zeroing the point position. The identity matrix resets all transforms (rotation, scale, translation), returning the primitive to its default state when combined with setting @P to origin.

### Reset Packed Primitive Transform [[Ep7, 131:34](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7894s)]
```vex
matrix3 m = ident();
setprimintrinsic(0, "transform", @primnum, m);
```
Creates an identity matrix and uses setprimintrinsic() to reset the transform intrinsic of a packed primitive back to its default state. This resets rotation, scale, and translation components stored in the packed primitive's transform intrinsic, effectively returning it to its original orientation and scale.

### Matrix from Orient and Scale [Needs Review] [[Ep7, 133:36](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8016s)]
```vex
matrix3 m = ident();
vector scale = {1, 0.5, 1};

@orient = quaternion(quaternion(0, 1, 0, 0) * @time);

m = scale(m, scale);
m = qconvert(@orient);

setprimintrinsic(0, 'transform', @primnum, m);
```
Creates a transformation matrix from orient quaternion and scale vector attributes, then applies it to primitive intrinsics. The orient quaternion is animated over time using a rotation around the Y-axis, combined with a non-uniform scale, then converted to a matrix and set as the primitive's transform intrinsic.

### Primitive Transform with Orient and Scale [[Ep7, 137:02](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8222s)]
```vex
@orient = quaternion({0,1,0} * @Time);
@scale = {1, 0.3, 2};

matrix3 m = ident();
scale(m, @scale);
m *= @convert(@orient);

setprimintrinsic(0, 'transform', @ptnum, m);
```
Creates an orientation quaternion rotating around the Y-axis over time, then builds a transformation matrix by starting with identity, scaling it non-uniformly, and multiplying by the converted quaternion orientation. The scale() function is an in-place operation that modifies the matrix directly without returning a value, and the final transform is applied to each primitive's intrinsic transform attribute.

### In-place Matrix Transform with Orient [[Ep7, 137:06](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8226s)]
```vex
@orient = quaternion({0,1,0} * @Time);
vscale = {1, 0.3, 2};

matrix m = ident();
scale(m, vscale);
m *= 4@orient;

setprimintrinsic(0, 'transform', @ptnum, m);
```
Demonstrates constructing a transformation matrix by combining scale and orientation quaternion, then applying it to a primitive's transform intrinsic. The scale() function operates in-place, modifying the matrix directly rather than returning a new value, which is why it doesn't require assignment. The matrix is multiplied by the quaternion (converted via 4@orient syntax) to incorporate rotation before being applied to the primitive.

### Matrix Scale and Quaternion Transform [Needs Review] [[Ep7, 137:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8250s)]
```vex
qorient = quaternion({0,1,0} * @Time);
vscale = {1, 0.5, 2};

matrix m = ident();
scale(m, vscale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```
Creates a transformation matrix by starting with an identity matrix, applying a non-uniform scale, then multiplying by a quaternion rotation converted to matrix form. The scale() function modifies the matrix in-place rather than returning a value, which is why it cannot be assigned. The final transform is applied to a primitive using setprimintrinsic.

### Matrix Transform with Primitives [[Ep7, 138:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8308s)]
```vex
qorient = quaternion({0,1,0} * @Time);
v@scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, v@scale);
m *= dconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```
Constructs a transformation matrix by combining scale and rotation (from quaternion) operations, then applies it to the 'transform' primitive intrinsic. This demonstrates how to manually build instance-like transformations using matrix operations, similar to what a Copy to Points SOP does internally. The scale() and rotate() functions modify matrices in-place rather than returning new ones, which is an unusual VEX pattern to be aware of.

### Matrix Construction from Instance Attributes [[Ep7, 138:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8310s)]
```vex
qorient = quaternion({0,1,0} * @Time);
v@scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, v@scale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```
Demonstrates how to construct a transformation matrix from instance attributes (scale and quaternion rotation) and apply it to a primitive's transform intrinsic. This approach mimics what a Copy SOP does, but manually iterates through points to set primitive transforms. The scale() and rotate() functions modify matrices in-place, which is a special pattern in VEX.

### Transform Intrinsic from Orient and Scale [[Ep7, 139:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8344s)]
```vex
@orient = quaternion({0,1,0} * @Time);
@scale = {1, 0.3, 2};

matrix3 m = ident();
scale(m, @scale);
m = qconvert(@orient);

setprimintrinsic(0, "transform", @ptnum, m);
```
Demonstrates constructing a matrix from instance attributes (@orient and @scale) and applying it to the transform intrinsic of packed primitives, replicating what a copy SOP would do. Creates an identity matrix, scales it, converts the orientation quaternion to a matrix, and sets it as the primitive's transform intrinsic.

### Transform Intrinsic from Matrix [[Ep7, 139:06](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8346s)]
```vex
qorient = quaternion({0,1,0} * @Time);
v@scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, v@scale);
m *= dconvert(qorient);

setprimintrinsic(0, "transform", @ptnum, m);
```
Demonstrates building a matrix3 transform from orient and scale attributes, then applying it to the 'transform' intrinsic of packed primitives. This mimics the behavior of a Copy SOP but done manually in VEX by constructing the transform matrix from identity, applying scale, then rotation via quaternion conversion.

### Transform Intrinsic with Matrices [[Ep7, 139:34](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8374s)]
```vex
@orient = quaternion({0,1,0} * @Time);
@scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, @scale);
m = qconvert(@orient);

setprimintrinsic(0, "transform", @ptnum, m);
```
Creates a matrix3 transform by combining scale and orientation (from quaternion), then applies it to the transform intrinsic of primitives. The transform intrinsic is a 3x3 matrix used for non-packed geometry, while packed geometry uses a 4x4 packedfullTransform matrix. This demonstrates manual matrix construction from separate rotation and scale components.

### Packed Full Transform Intrinsic [Needs Review] [[Ep7, 139:36](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8376s)]
```vex
matrix3 m = matrix3(myfancyMatrix);

matrix pft = prim(0, "intrinsic:packedfulltransform", @ptnum);

@a = pft;
```
Demonstrates accessing the packedfulltransform intrinsic from packed geometry, which returns a 4x4 matrix representing the full transformation including translation. Unlike the standard transform intrinsic which is a matrix3, packedfulltransform is a full 4x4 matrix that includes positional data.

### Setting packed primitive transform with matrix [[Ep7, 141:22](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8482s)]
```vex
vector qorient = quaternion({0,1,0} * 2*$PI);
@qScale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, @qScale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```
Constructs a transform matrix by creating an identity matrix, applying a scale, and then multiplying by a rotation matrix derived from a quaternion. The resulting matrix3 is set as the packed primitive's transform intrinsic, demonstrating how to compose transformations for packed geometry.

### Matrix Type Casting and Intrinsics [[Ep7, 141:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8484s)]
```vex
matrix3 m = matrix3(myFancyMatrix);

matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);

4@a = pft;
```
Demonstrates casting between matrix types and reading packed primitive transform data. The primintrinsic function retrieves the 4x4 packed full transform matrix from geometry, which can be cast to matrix3 if only rotation/scale is needed, or stored directly as a 4x4 matrix attribute using the 4@ prefix.

### Reading Packed Primitive Transform [[Ep7, 141:40](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8500s)]
```vex
matrix pft = primintrinsic(0, "packedfullxform", @ptnum);
```
Declares a matrix variable to store the full transformation matrix of a packed primitive using primintrinsic(). This reads the "packedfullxform" intrinsic attribute from the packed primitive corresponding to the current point number, capturing the complete 4x4 transform matrix including translation, rotation, and scale.

### Reading Packed Primitive Transform Matrices [[Ep7, 142:52](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8572s)]
```vex
matrix pft = primintrinsic(0, "packedfulltramsform", @ptnum);
4@a = pft;
```
Reads the full transformation matrix from a packed primitive using the primintrinsic function and stores it in a 4x4 matrix attribute. The packedfulltramsform intrinsic contains all transformation data (translation, rotation, scale) in a single matrix that can be inspected or manipulated. The last column of the matrix remains constant and can be used as an indicator when comparing matrices.

### Reading Packed Transform Matrix [[Ep7, 143:38](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8618s)]
```vex
matrix pft = printintrinsic(0, "packedfulltransform", @ptnum);
@Cd = pft;
```
Retrieves the packed full transform matrix from a packed primitive and assigns it to the color attribute for visualization. The 4x4 matrix contains rotation/scale in the upper 3x3 section (visualized in green) and translation in the bottom row (visualized in red), with the matrix stored in row-major order ending with [0,0,0,1] as the last four values.

### Reading Packed Transform Matrix [[Ep7, 143:56](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8636s)]
```vex
matrix xft = primintrinsic(0, "packedfulltransform", @ptnum);
4@xform = xft;
```
Retrieves the full transformation matrix from a packed primitive using primintrinsic and stores it in a matrix4 attribute. The resulting 4x4 matrix contains rotation/scale in the upper 3x3 section and translation in the bottom row, making the translate values human-readable while rotation requires matrix interpretation.

### Extracting Rotation and Scale from Packed Transform [Needs Review] [[Ep7, 144:36](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8676s)]
```vex
matrix pft = primintrinsic(0, 'packedfulltranosform', @ptnum);
4@a = pft;

matrix3 rotandscale = matrix3(pft);
```
Retrieves the full transformation matrix from a packed primitive using primintrinsic, stores it in a 4x4 matrix attribute, then extracts just the rotation and scale components by converting to a matrix3. The matrix3 constructor automatically extracts the upper-left 3x3 portion of the 4x4 matrix, which contains rotation and scale but excludes translation.

### Extracting Rotation and Scale from Packed Transform [Needs Review] [[Ep7, 145:12](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8712s)]
```vex
matrix pft = printintrinsic(0, "packedfulltramsform", @ptnum);
@Ga = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```
Demonstrates extracting a packed primitive's full transform as a matrix, storing it in a matrix attribute, then casting it to a matrix3 to isolate just the rotation and scale components (discarding translation). The matrix3 cast extracts the upper-left 3x3 portion of the 4x4 transform matrix, which contains rotation and scale but not translation information.

### Extracting Matrix3 from Packed Transform [Needs Review] [[Ep7, 145:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8714s)]
```vex
matrix pft = printintrinsic(0, "packedfulltramsform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```
Demonstrates extracting a 3x3 rotation and scale matrix from a packed primitive's full transform matrix by using the matrix3() cast. The full 4x4 transform is first read from the packed primitive intrinsic, then the upper-left 3x3 portion (containing rotation and scale) is extracted and stored in a separate attribute for inspection.

### Extracting rotation and scale from packed transform [[Ep7, 145:16](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8716s)]
```vex
matrix pft = primintrinsic(0, "packedfullTransform", @ptnum);
matrix3 rotandscale = matrix3(pft);
@matrix3b = rotandscale;
```
Demonstrates extracting the rotation and scale components from a packed primitive's full transform matrix by converting the 4x4 transform matrix to a 3x3 matrix. This isolates the rotation and scale information while discarding the translation component, storing the result in a 3x3 matrix attribute for inspection.

### Extracting Rotation and Scale from Packed Transform [Needs Review] [[Ep7, 145:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8718s)]
```vex
matrix pft = primintrinsic(0, "packedfullransform", @ptnum);
@ptg = pft;

matrix3 rotandscale = matrix3(pft);
@p3by3 = rotandscale;
```
Demonstrates extracting the 3x3 rotation and scale component from a packed primitive's 4x4 transform matrix by casting it to a matrix3. The primintrinsic function retrieves the full transform, which is stored in a 4x4 matrix attribute, then a matrix3 cast extracts just the upper-left 3x3 portion containing rotation and scale data (excluding translation).

### Extracting Rotation and Scale from Packed Transform [Needs Review] [[Ep7, 145:42](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8742s)]
```vex
matrix pft = primintrinsic(0, "packedfulltrransform", @ptnum);
matrix3 rotandscale = matrix3(pft);
3x3 = rotandscale;
```
Demonstrates extracting a packed primitive's full transform matrix using primintrinsic(), then converting it to a matrix3 to isolate the rotation and scale components (discarding translation). The 3x3 matrix attribute stores just the rotational and scale transformations, which is useful for operations with packed primitives in contexts like bullet simulations.

### Extracting Rotation and Scale from Packed Transform [[Ep7, 145:46](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8746s)]
```vex
matrix pft = primintrinsic(0, "packedfullttransform", @ptnum);
@Cd = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```
Extracts the packed full transform matrix from a packed primitive and converts it to a matrix3 to isolate the rotation and scale components (excluding translation). The 4x4 transform is first retrieved and assigned to color for visualization, then the upper-left 3x3 portion is extracted into a separate matrix3 attribute.

### Extracting Rotation and Scale from Packed Transform [[Ep7, 145:48](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8748s)]
```vex
matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```
Retrieves the full 4x4 packed transform matrix from a packed primitive, then extracts just the 3x3 rotation and scale component by casting it to matrix3. The upper-left 3x3 portion of a transform matrix contains rotation and scale information, while translation is stored in the fourth column.

### Animating Primitive Closed State [[Ep7, 146:42](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8802s)]
```vex
int openLove = int(rand(@primnum * @Frame * 7));
setprimintrinsic(0, "closed", @primnum, openLove);
```
Uses random values driven by primitive number and frame to animate whether primitives are open or closed via the 'closed' intrinsic attribute. This demonstrates how intrinsics provide access to primitive properties that aren't exposed as regular attributes, allowing for procedural animation of geometry states.

### Reading Packed Transform Intrinsics [[Ep7, 149:00](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8940s)]
```vex
matrix pft = primintrinsic(0, "packedfullransform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```
Demonstrates reading the 'packedfullransform' intrinsic from packed geometry using primintrinsic() to extract the full 4x4 transform matrix, then converting it to a matrix3 to isolate rotation and scale components. The full matrix is stored in attribute 'a' and the rotation/scale matrix in attribute 'b' for visualization or further processing.

### Packed Primitive Intrinsics and Closed Polygons [[Ep7, 149:02](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8942s)]
```vex
matrix pft = primintrinsic(0, "packedfullstransform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;

int open_load = int(rand(@ptnum+@Frame)*2);
setprimintrinsic(0, "closed", @primnum, open_load);
```
Demonstrates reading packed primitive transform intrinsics and extracting rotation/scale components using matrix casting. Also shows using the 'closed' intrinsic with setprimintrinsic() to randomly convert polygons to open polylines based on per-primitive random values combined with frame number.

### Setting Primitive Closed Intrinsic [[Ep7, 150:08](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9008s)]
```vex
int openclose = int(rand(@primnum * @Frame) ** 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```
Creates a random open/close state for each primitive using the primitive number and frame number as random seed, then uses setprimintrinsic() to set the "closed" intrinsic attribute. The random value is squared and converted to an integer to create a binary open/closed state that animates over time.

### Random Curve Open/Close with setprimintrinsic [[Ep7, 150:12](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9012s)]
```vex
int openclose = int(rand(@primnum*@Frame)**2);
setprimintrinsic(0, "closed", @primnum, openclose);
```
Creates a random integer (0 or 1) per primitive per frame using a scaled random function, then uses setprimintrinsic to toggle the 'closed' intrinsic attribute on curves. The multiplication by frame number ensures the random pattern changes over time, causing curves to randomly open and close during animation.

### Randomly Toggle Primitive Closed Intrinsic [[Ep7, 150:46](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9046s)]
```vex
int openclose = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```
Creates a random integer (0 or 1) per primitive based on primitive number and frame, then sets the primitive's 'closed' intrinsic attribute to randomly open or close curves over time. The rand() function generates values between 0 and 1, which when multiplied by 2 and cast to int produces either 0 or 1.

### Randomizing Primitive Open/Closed State [[Ep7, 151:02](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9062s)]
```vex
int open_loop = int(rand(@primnum * @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, open_loop);
```
Uses animated random values based on primitive number and frame to toggle primitives between open and closed states. The rand() function is multiplied by 2 and cast to int to produce values of 0 or 1, which are then applied to the 'closed' primitive intrinsic attribute using setprimintrinsic().

### Random Open/Closed Primitives [[Ep7, 151:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9074s)]
```vex
int openlook = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openlook);
```
This code randomly sets primitives to be open or closed using a random value based on primitive number and frame. The rand() function generates a value between 0-1, which is multiplied by 2 and cast to int, producing either 0 or 1, then applied to the 'closed' intrinsic attribute via setprimintrinsic().

### Random Primitive Open/Close Animation [[Ep7, 151:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9080s)]
```vex
int openclose = int(rand(@primnum * @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose);
```
Randomly sets primitives to be open or closed polygons on each frame using a randomized intrinsic attribute. The rand() function takes the primitive number multiplied by the current frame to generate a time-varying random value between 0 and 1, which is then scaled to 2 and cast to int to produce either 0 (open) or 1 (closed).

### Random Open/Closed Primitives [[Ep7, 151:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9088s)]
```vex
int openclosed = int(rand(@primnum + rand() * 2));
setprimintrinsic(0, "closed", @primnum, openclosed);
```
Randomly assigns primitives to be open or closed by generating a random integer (0 or 1) using the primitive number as a seed, then setting the 'closed' intrinsic attribute. This causes animated primitives to randomly switch between open and closed states when the random seed changes per frame.

### Random Open/Closed Polygon Intrinsic [[Ep7, 151:54](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9114s)]
```vex
int openLoop = int(rand(@primnum)*rand())*2);
setprimintrinsic(0, "closed", @primnum, openLoop);
```
Uses random values to assign primitives as either open or closed polygons by setting the 'closed' intrinsic attribute. The expression generates either 0 or 1 by multiplying two random values and multiplying by 2, which randomly determines polygon closure state and causes animated primitives to behave erratically.

### Random Open/Closed Polygon Animation [[Ep7, 151:56](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9116s)]
```vex
int openCase = int(rand(@primuv[0]*rand)*2);
setprimintrinsic(0, 'closed', @primnum, openCase);

int openClose = int(rand(@primnum+@Frame)*2);
setprimintrinsic(0, 'closed', @primnum, openClose);
```
Randomly animates polygons between open and closed states using the 'closed' primitive intrinsic. The first line shows a UV-based random assignment, while the second demonstrates frame-based animation by incorporating @Frame into the random seed to create flickering open/close behavior over time.

### Randomizing Primitive Closed State [[Ep7, 152:46](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9166s)]
```vex
int openClose = int(rand(@primnum*frame)*2);
setprimintrinsic(0, 'closed', @primnum, openClose);

int openClose = int(rand(@primnum+frame)*2);
setprimintrinsic(0, 'closed', @primnum, openClose);
```
Uses random values to toggle the 'closed' intrinsic attribute on primitives, controlling whether curves or polygons are open or closed. The code multiplies or adds the primitive number with the frame number to create animated randomization, then converts the rand() output to an integer (0 or 1) to set the closed state.

### Setting Orient to Identity Quaternion [[Ep7, 30:36](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=1836s)]
```vex
@orient = {0,0,0,1};
```
Setting the @orient attribute to the identity quaternion {0,0,0,1} locks copied geometry to a specific orientation, preventing it from inheriting rotation from the underlying normal or point orientation. This allows geometry to maintain a fixed orientation regardless of transforms applied to the copy target points, overriding default copy behavior that would normally orient based on the @N attribute.

### Animating Quaternion Orientations [[Ep7, 30:56](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=1856s)]
```vex
float angle = ch('angle');
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// Animated version
float angle = @Time;
vector axis = chv('axis');

@orient = quaternion(angle, axis);
```
Demonstrates how to create quaternion-based orientations using channel references for angle and axis parameters. Shows both static (using ch parameter) and animated versions (using @Time) to control instance orientations independently of geometry normals, allowing instances to maintain specific orientations regardless of underlying geometry transformations.

### Orient Attribute with Quaternions [[Ep7, 31:00](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=1860s)]
```vex
@orient = {0,0,0,1};

float angle = ch('angle');
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// Animating with time
float angle = @Time;
vector axis = chv('axis');

@orient = quaternion(angle, axis);
```
The @orient attribute controls instance orientation using quaternions, which lock copied geometry to specific rotations regardless of their normal attributes. By constructing quaternions from an angle and axis (using channel references or @Time), you can precisely control and animate the orientation of instanced geometry without relying on @N.

### Quaternion Rotation with Time Animation [[Ep7, 37:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=2250s)]
```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum * ch('offset');
angle += @Time * ch('speed');

axis = chv('axis');

@orient = quaternion(angle, axis);
```
Creates animated quaternion rotations per point by combining a base angle, point-number-based offset, and time-based speed multiplier. The offset parameter controls how much rotation varies between sequential points, while speed scales the time-based animation rate, creating sweeping rotation effects across the geometry.

### Instance Matrix to Quaternion Orientation [[Ep7, 89:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5390s)]
```vex
@P = v@P;
@orient = {0,0,0,1};
@pscale = 1;

int target = nearpoint(1,@P);
vector base = point(1,"P",target);
matrix m = ident();
m = instance(m, base-@P, {0,1,0}, 1, {0,0,1}, 0);

@orient = quaternion(m);
```
Creates instance orientations by finding the nearest point on a target geometry and building an instance matrix from that position. The matrix is constructed using the instance() function with up vector {0,1,0} and converted to a quaternion for the @orient attribute, allowing copies to point toward their target positions.

### Orient copied geometry with normals [[Ep7, 96:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5774s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
```
Setting the normal attribute (@N) to the normalized position vector orients copied geometry so that instances point outward from the sphere center. The @up vector helps control the twist/rotation of the instances, ensuring their bases face downward as much as possible while their forward axis (typically Z) points along the normal direction.

### Orient Points with Quaternions [[Ep7, 97:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5834s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N,@up));
```
Creates an orientation quaternion for each point by normalizing the position to get an outward-facing normal, defining an up vector, and converting the resulting transform matrix into a quaternion. This setup orients copied geometry so that each instance's Z-axis points away from the sphere center, with consideration for which direction the copied geometry should face (e.g., whether the front or back of a pig model faces outward).

### Primitive UV Sampling Setup [Needs Review] [[Ep8, 25:20](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1520s)]
```vex
vector uv = chv('uv');

vector gx = primmuv(1, 'P', u, uv.x);
vector gy = primmuv(1, 'P', u, uv.y);
```
Setting up a vector parameter to control UV coordinates, then sampling the position attribute from a second input geometry at two different UV locations (x and y components). This creates two geometry sample points that will likely be used for tangent/derivative calculations or grid construction.

### Primitive UV Attribute Sampling [[Ep8, 30:22](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1822s)]
```vex
vector uv = chv('uv');
@P = primav(1, 'P', 0, uv);
@N = primav(1, 'N', 0, uv);
```
Uses primav() to sample position and normal attributes from a primitive at specified UV coordinates. The UV coordinates are exposed as a channel parameter, allowing interactive control. This technique samples geometry-1's primitive-0 attributes at the given UV location and assigns them to the current point.
