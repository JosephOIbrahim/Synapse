# Joy of VEX: Attributes

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
// *orient  // Orient Attribute Transformation
@Cd = @P.x;  // Accessing Vector Components
v@up = {0,0,1};  // Setting Up Vector Orientation
```

## Attribute Basics

### Accessing Vector Components [[Ep1, 19:28](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1168s)]
```vex
@Cd = @P.x;
```
Assigns the X component of the position attribute to the color attribute, resulting in all three RGB channels being set to the same value (the X coordinate). This demonstrates accessing individual vector components using dot notation (.x) and automatic type promotion from float to vector.

### Vector Component Access [[Ep1, 20:28](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1228s)]
```vex
@Cd = @P.x;

@Cd = @N.y;
```
Individual components of vector attributes can be accessed using dot notation (.x, .y, .z). Here, color is set to the X component of position, then to the Y component of the normal, demonstrating how single float values can be extracted from vector attributes and used to create masks or visualizations.

### Type Casting and Point Color Normalization [[Ep1, 39:22](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2362s)]
```vex
@Cd = float(@ptnum)/100;

@Cd = @ptnum;

@Cd = @ptnum/@numpt;
```
Demonstrates the importance of type casting in VEX when dividing integers. Shows three approaches to setting point color: casting point number to float before division, direct assignment (incorrect range), and dividing by total point count to normalize color values between 0 and 1.

### Variable Declaration and Type Casting [[Ep1, 50:52](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3052s)]
```vex
@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)*ch('scale'));

float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);

float foo = float(@ptnum)*ch('scale');
@Cd = sin(foo);
```
Demonstrates the progression from inline expressions to using named variables for code clarity. Shows how to declare a float variable 'foo' to store intermediate calculations (point number scaled by a channel parameter), making the code more readable and easier to debug. Emphasizes the importance of explicit type casting with float() when working with integer attributes like @ptnum.

### Variables vs Attributes [[Ep1, 54:06](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3246s)]
```vex
float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
```
Demonstrates the difference between local variables and attributes in VEX. The variable 'foo' is temporary throwaway data that only exists within the wrangle code, while @Cd is an attribute that gets saved on the geometry. This pattern helps keep code clean and organized while understanding when data needs to persist versus when it's just used for intermediate calculations.

### Animating with @Time [[Ep1, 96:50](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5810s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d),-1,1,0,1);

// Adding @Time for animation
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d+@Time),-1,1,0,1);
```
Demonstrates animating color patterns by adding the built-in @Time attribute to the sine wave calculation. The @Time attribute is automatically updated each frame, creating animated ripple effects without requiring additional setup. Note that @Time and other built-in attributes like @Frame are capitalized.

### Time attribute and animation [[Ep1, 96:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5816s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);
```
Demonstrates using the built-in @Time attribute (capitalized) to animate patterns over time. The distance calculation combined with sin() creates ripple patterns, and adding @Time to the distance value makes these patterns evolve automatically with playback. The @Frame attribute can also be used but animates faster since it increments by integers each frame.

### Animating with @Time Attribute [[Ep1, 96:58](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5818s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);
```
Demonstrates using the built-in @Time attribute to animate color patterns over time. The @Time attribute is capitalized and represents the current time in seconds, providing automatic animation without needing to explicitly reference $T or frame numbers. This creates a rippling color effect that evolves smoothly as the timeline plays.

### Animating patterns with @Time [[Ep1, 97:08](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5828s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);

// Animated version:
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d + @Time), -1, 1, 0, 1);
```
Demonstrates animating a radial sine wave pattern by adding the @Time attribute to the distance calculation. The @Time attribute provides the current time in seconds, creating smooth animation as the pattern evolves. This is slower than using @Frame (which changes by 1 each frame) because @Time increments fractionally based on the frame rate.

### Time-based Animation with @Time [[Ep1, 97:38](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5858s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@N = ch('scale');
@Cd = fit(sin(d*@Time),-1,1,0,1);
```
Demonstrates using the @Time attribute to create time-varying effects by combining it with distance calculations and sine waves. The @Time attribute updates smoothly based on seconds elapsed (at 24fps, reaching 1.0 after 24 frames), making it ideal for slower, continuous animations compared to @Frame which changes by integer values each frame.

### Time-based animation with @Time [[Ep1, 97:48](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5868s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d*@Time), -1, 1, 0, 1);
```
Creates animated color patterns by calculating distance from a center point and using @Time with sine function to create oscillating values. The @Time attribute provides frame-based animation where reaching frame 24 equals 1.0 in value, making it ideal for time-varying effects without additional setup. The fit() function remaps the sine wave output from [-1,1] to [0,1] for valid color values.

### Ramp Modulo Behavior Change [Needs Review] [[Ep2, 50:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3046s)]
```vex
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
@P.y = fit01(d, -0.1, 0.1);
@Cd.y = chramp("myRamp", d);
@Cd.y *= ch("height");
```
Creates animated wave displacement using distance from origin, sine function, and time. Uses chramp() to color based on the displacement value, noting that ramp behavior changed to no longer implicitly modulo values (which previously caused repeating patterns).

### Pseudo Attributes and Point Primitives [Needs Review] [[Ep3, 11:32](https://www.youtube.com/watch?v=fOasE4T9BRY&t=692s)]
```vex
float d = len(v@P - p1(0, @primnum, 0));
s@ry = sin(d);
```
Demonstrates using pseudo attributes and the p1() function to calculate distance from point position to primitive center. The distance is then used to create a sine wave pattern stored in a string attribute, illustrating how pseudo attributes like @primnum work similarly to other built-in attributes.

### Pseudo Attributes and Compilation [Needs Review] [[Ep3, 11:34](https://www.youtube.com/watch?v=fOasE4T9BRY&t=694s)]
```vex
// VCC compiler command (not VEX code)
// VCC -q $VOP_INCLUDEPATH -o $VOP_OBJECTFILE -e $VOP_ERRORFILE $VOP_SOURCEFILE
```
Discussion of pseudo attributes like @P, @ptnum, and @Time that are automatically generated by Houdini. Pseudo attributes differ from regular attributes as they are computed values - for example, primitive @P is generated from the center point of the primitive's point positions rather than being stored data.

### Vertex Attribute Manipulation with Distance [[Ep3, 14:38](https://www.youtube.com/watch?v=fOasE4T9BRY&t=878s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cry = sin(d);
```
Calculates the distance from the origin for each vertex position, scales it by a channel parameter, and assigns a sine wave pattern to a custom vertex attribute. This code runs on every vertex in the geometry, creating more data points than point-based operations since each point with connected primitives generates multiple vertices.

### Creating Custom Variables and Attributes [[Ep3, 21:42](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1302s)]
```vex
float d = length(@P);
@mydistance = d;
@Cd.r = sin(d);

// You can also use channel references
float scale = ch("scale");
@Cd.r = sin(@mydistance * scale);
```
This demonstrates creating custom variables in VEX to store intermediate calculations and output them as geometry attributes. By declaring variables with the @ prefix, they automatically appear in the geometry spreadsheet, making them valuable for debugging and visualization. Variables can be declared at any point in the code and reused throughout.

### Creating Custom Attributes with Variables [[Ep3, 21:44](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1304s)]
```vex
f@d = length(@P);
f@d /= ch("scale");
@Cd = @d;
@Cd.r = sin(@d);
```
Demonstrates creating a custom float attribute 'd' to store calculated distance values, which can then be used in subsequent operations and viewed in the geometry spreadsheet. The pattern shows how intermediate calculations can be stored as attributes for debugging and reuse, here computing distance from origin, scaling it, and using it to drive color.

### Distance Attributes and Color Assignment [[Ep3, 22:08](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1328s)]
```vex
float d = length(@P);
@mydistance = d;

@d = length(@P);
@Cd = d;
@Cd.r = sin(@d);
```
Demonstrates creating custom attributes by calculating distance from origin using length(@P), storing it in variables and custom attributes like @mydistance and @d. Shows how to assign distance values to color channels, including using sin() function to modulate the red color channel based on distance.

### Creating Custom Attributes from Distance [[Ep3, 22:14](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1334s)]
```vex
float d = length(@P);
@d = d;
@Cd.r = sin(@d);
```
Demonstrates creating custom attributes dynamically in VEX by calculating distance from origin and storing it in a custom attribute @d. The red channel of color is then driven by the sine of this distance value, showing how attributes can be created on-the-fly and used to drive other attributes.

### Distance to Point with Fit [Needs Review] [[Ep3, 37:22](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2242s)]
```vex
vector pos = v@pos[0];
float d = distance(pos, @P);
d *= ch('scale');
f@Cd = fit(d, 0, 1, 0, 1);
```
Reads a position vector from the first input's point 0, calculates the distance from each point to that position, scales it by a channel parameter, and uses fit() to remap the distance values into the color attribute. This demonstrates combining point attribute lookups, distance calculations, and value remapping for visualization.

### Distance-based color and wind [Needs Review] [[Ep3, 37:50](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2270s)]
```vex
vector pos = v@opinput1_P;
float d = distance(@P, pos);
f@scale = d;
@Cd = d;
v@v = v@wind * d;
```
Demonstrates reading position from a second input, calculating distance from current point to that position, and using the distance value to drive both color and a wind-scaled velocity vector. This pattern is commonly used for proximity-based effects where scattered points respond to a reference position.

### Transfer Color via Nearest Point [[Ep3, 39:58](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2398s)]
```vex
int pt = nearpoint(1, @P);
@Cd = point(1, "Cd", pt);
```
This code finds the closest point on the second input geometry and transfers its color attribute to the current point. The nearpoint() function returns the point number of the nearest point, which is then used with point() to read that point's Cd attribute.

### Transferring Attributes from Second Input [[Ep3, 42:26](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2546s)]
```vex
int pt = nearpoint(0, v@P);
@Cd = point(0, 'Cd', pt);
```
This demonstrates transferring attributes from a second input geometry by finding the nearest point on the reference geometry and copying its color attribute. The nearpoint() function locates the closest point on input 0 to the current point's position, then point() retrieves the color attribute from that nearest point.

### Understanding point() Function Syntax [[Ep3, 43:06](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2586s)]
```vex
int pt = nearpoints(0, @P);
@Cd = point(0, 'Cd', pt);
```
This demonstrates the syntax of the point() function, which retrieves an attribute value from a specific point. The code finds a nearby point using nearpoints(), then copies its Cd (color) attribute to the current point using point(), illustrating why the attribute name is passed as a string parameter rather than using direct attribute binding syntax.

### Point function attribute syntax [[Ep3, 43:18](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2598s)]
```vex
int pt = nearpoint(0, @P);
@Cd = point(0, 'Cd', pt);
```
This snippet demonstrates using nearpoint() to find the closest point and then reading its Cd attribute with the point() function. The explanation discusses why the attribute name 'Cd' must be passed as a string in quotes rather than using @ syntax, clarifying common confusion about when to use @ versus string literals for attribute access.

### Reading Non-Existent Attributes [[Ep3, 44:20](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2660s)]
```vex
int pt = nearpoint(0, v@P);
v@Cd = point(0, "Cd", pt);
```
Demonstrates what happens when attempting to read a color attribute (Cd) that doesn't exist on the input geometry. When an attribute doesn't exist, VEX returns a default zero-initialized value, which in this case produces a vector {0,0,0} for color.

### Handling Missing Attributes [[Ep3, 44:24](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2664s)]
```vex
int pt = nearpoint(0, @P);
v@Cd = point(0, "Cd", pt);
```
Demonstrates what happens when attempting to read a non-existent attribute from geometry. When the 'Cd' attribute doesn't exist on the input geometry, the point() function returns a zero vector (0,0,0) rather than throwing an error, resulting in black color values.

### Point Attributes via Input Reference [[Ep3, 49:58](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2998s)]
```vex
@P = @opinput1_P;
```
Demonstrates multiple approaches to reading point data from a second input, progressing from manual nearpoint lookups with distance calculations to the simplified @opinput syntax for direct attribute access. The final version @P = @opinput1_P directly assigns position from input 1 by point number.

### Direct Point Attribute Access [[Ep3, 50:04](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3004s)]
```vex
@P = point(1, 'P', @ptnum);

@P = @opinput1_P;
```
Demonstrates two equivalent methods for directly copying point positions from the second input. The first uses point() with @ptnum to read by point number, while the second uses the @opinput1_P shorthand to access the same data. Both methods copy positions directly without requiring nearpoint() lookups.

### Reading Points from Second Input [[Ep3, 52:04](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3124s)]
```vex
@P = point(1, 'P', @ptnum);

@opinput1_P;
```
Demonstrates two methods for reading point positions from the second input: using the point() function with input index 1, and using the @opinput1_P syntax which is shorthand for accessing attributes from specific inputs. Both approaches allow you to copy or reference geometry attributes from a different input stream.

### Reading Position from Second Input [[Ep3, 52:36](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3156s)]
```vex
@P = point(1, 'P', @ptnum);
```
This demonstrates reading point positions from a second input geometry using the point() function. The code sets the current point's position to match the corresponding point from input 1, using @ptnum to maintain point correspondence. The alternative @opinput1_P syntax achieves the same result more concisely.

### Reading Attributes from Second Input [[Ep3, 55:14](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3314s)]
```vex
vector pi = @opinput1_P;
vector cd1 = @opinput1_Cd;

@P = pi;
@Cd = cd1;
```
Demonstrates how to read attributes from the second input (input 1) of a wrangle node using the @opinput1_ prefix syntax. This allows you to transfer attributes like position and color from one geometry stream to another when point counts and numbers match.

### Reading Input Geometry Attributes [[Ep3, 55:18](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3318s)]
```vex
vector p1 = @opinput1_P;
vector cd1 = @opinput1_Cd;

@P = p1;
@Cd = cd1;
```
Demonstrates reading attributes from the second input geometry using the @opinput1_ prefix to access position and color. This technique allows you to copy attribute values from one input to another, enabling geometry blending and attribute transfer operations.

### Reading Quaternion Point Attributes [[Ep3, 59:56](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3596s)]
```vex
vector p1 = swlerpquat.p1;
vector cd1 = swlerpquat.Cd1;

@P = p1;
@Cd = cd1;
```
This code reads position and color attributes from another point referenced by the swlerpquat variable (likely from a nearpoint or similar lookup), then assigns those values to the current point's position and color attributes. This is a common pattern for transferring attributes between points in different geometric contexts.

### Vector component assignment clarity [[Ep3, 74:02](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4442s)]
```vex
@Cd = v1;
@Cd.x = curlnoise(@P*chv('fancyscale'))*@Time;
```
Demonstrates the difference between assigning a full vector versus assigning individual components. The code shows how to properly initialize a vector to ensure clarity when only modifying specific components, avoiding implicit assumptions in the VEX compiler.

### Reading Point Position from Second Input [Needs Review] [[Ep4, 11:06](https://www.youtube.com/watch?v=66WGmbykQhI&t=666s)]
```vex
vector pos = point(1, "P", @ptnum);
@Cd = dot(chv("angle"), pos);
```
Reads the position of a point from the second input using the point() function, then uses a dot product between a channel vector parameter and that position to drive color. This demonstrates how to reference geometry from multiple inputs and combine it with viewport-controlled parameters.

### Reading Point Positions with point() [[Ep4, 34:34](https://www.youtube.com/watch?v=66WGmbykQhI&t=2074s)]
```vex
vector a = @P;
vector b = point(1, 'P', 0);
```
Demonstrates two methods of accessing point positions: using the @P attribute binding for the current point, and using the point() function to read the position of a specific point (point 0) from input 1. This establishes the foundation for working with multiple point positions simultaneously.

### Reading points from multiple inputs [[Ep4, 34:40](https://www.youtube.com/watch?v=66WGmbykQhI&t=2080s)]
```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@i = b - a;

vector a = point(0, 0, "P", 0);
vector b = point(1, 0, "P", 0);

@i = b - a;

vector a = @P;
vector b = point(1, "P", 0);
```
Demonstrates reading point positions from multiple wrangle inputs using the point() function with different input indices. The first parameter specifies which input to read from (0 for first input, 1 for second input), allowing vectors to be constructed from different geometry streams and subtracted to create directional vectors.

### Point-to-Point Normal Direction [[Ep4, 37:18](https://www.youtube.com/watch?v=66WGmbykQhI&t=2238s)]
```vex
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);

@N = b - a;

// Alternative using current point
vector a = @P;
vector b = point(1, 'P', 0);

@N = b - a;
```
Demonstrates calculating a normal vector by subtracting two point positions. The first example references point 0 from input 0 and point 0 from input 1, while the second uses the current point position (@P) and a reference point from input 1, causing all points on a sphere to orient their normals toward a single target point that can be moved interactively.

### Vector Direction from Point [[Ep4, 38:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=2294s)]
```vex
vector origin = point(1, "P", 0);
@v = @P - origin;
```
Creates a velocity vector on each point that points away from a specific origin point (point 0 on input 1). By subtracting the origin position from the current point position, vectors radiate outward from the origin. This technique is useful for simulations where you want to set initial velocities that emanate from or converge to a specific point in space.

### Multiplying Normals by Channel Parameter [[Ep4, 41:58](https://www.youtube.com/watch?v=66WGmbykQhI&t=2518s)]
```vex
@N *= ch('scale');
```
Demonstrates multiplying the normal vector by a channel parameter to scale normals uniformly. The correction shows the difference between assigning (@N = ch('scale')) versus multiplying (@N *= ch('scale')) - multiplication preserves the vector direction while scaling its length, whereas assignment would set all components to the same scalar value.

### Scaling Normals with Vectors [[Ep4, 44:20](https://www.youtube.com/watch?v=66WGmbykQhI&t=2660s)]
```vex
@N *= chv('scalevec');
```
Demonstrates multiplying the normal vector by a vector parameter to scale normals non-uniformly along different axes. By setting certain components of the scale vector to zero or negative values, you can flatten normals along specific axes or reverse their direction, creating interesting deformations that stretch geometry along particular directions.

### Component Access on Vectors [[Ep4, 53:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=3182s)]
```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;
```
Demonstrates accessing individual components of a vector using dot notation. The y-component of the bbox vector (which contains normalized 0-1 bounding box coordinates) is extracted and assigned to the color attribute, creating a black-to-white gradient based on vertical position within the bounding box.

### Vector Component Access [[Ep5, 20:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=1250s)]
```vex
vector myvector = {1, 2, 1};

v@a = {10, 12, 100};

float foo = @a.x; // will return 10

float foo = @a[2]; // that's asking for index 2, which will return 100
```
Demonstrates two methods for accessing vector components in VEX: dot notation (@a.x) for named access to x/y/z components, and array index notation (@a[2]) for numeric index access where 0=x, 1=y, 2=z. Both approaches extract a single float value from a vector attribute.

### Vector component access methods [Needs Review] [[Ep5, 25:18](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=1518s)]
```vex
vector @vector = {1,2,3};
v@a = {10,15,100};

@foo = @x+1;
```
Demonstrates creating vector attributes and accessing vector components using different notations. Vector components can be accessed using .x, .y, .z or .r, .g, .b notation interchangeably. This introduces the concept that vectors have multiple ways to reference their components before transitioning to arrays for storing more than three elements.

### Setting pscale from channel parameter [Needs Review] [[Ep6, 15:20](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=920s)]
```vex
@pscale = ch("pscale");

float u, t;
t = fit01(@P.x * ch("speed"), 0, 1);
d = length(@P);
```
Introduces the @pscale attribute for controlling instance size in the Copy to Points SOP. The code reads a channel parameter value and assigns it to the pscale point attribute, which scales copied geometry uniformly. Additional variables are declared for animation timing based on point position.

### Setting pscale with channel reference [[Ep6, 15:28](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=928s)]
```vex
@pscale = ch('pscale');

float d, i;
i = @Time * ch('speed');
d = length(@P);
```
Demonstrates setting the pscale attribute using a channel reference for easy parameter control. The code also initializes variables for time-based animation (i) and distance from origin (d), suggesting preparation for scale manipulation based on these values.

### P-scale attribute basics [Needs Review] [[Ep6, 15:58](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=958s)]
```vex
@pscale = ch('pscale');

float d, i;
i = fit01(@P.y, 0, 1);
d = length(@P);
```
Demonstrates setting up the @pscale attribute using a channel reference for interactive control. The example shows how to uniformly scale instances or copied geometry on points, with discussion of adjusting pscale values to prevent overlapping when working with dense point grids.

### Animated pscale with UI controls [[Ep6, 20:14](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1214s)]
```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;

@pscale = ch('pscale');

@scale = {1, 5, 2.2};
```
Demonstrates animating point scale using time-based sine waves controlled by channel references for speed and frequency parameters, then shows alternative approaches using the @pscale attribute with a channel reference and the @scale vector attribute for per-axis control. The animated version creates traveling wave patterns by combining distance from origin, time, and sine functions to drive copy-to-points instancing.

### pscale vs scale attributes [[Ep6, 20:16](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1216s)]
```vex
@pscale = ch('pscale');

float d, i;
i = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += i;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;

@scale = {1, 1, 2.2};

@scale.x = 1;
```
Demonstrates creating animated @pscale using sine waves driven by time and distance from origin, then introduces @scale as a vector attribute that provides independent control over scaling on all three axes. The pattern uses frequency and speed parameters to control wavelength propagation through the geometry.

### Using @scale for non-uniform scaling [[Ep6, 21:02](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1262s)]
```vex
d = chf('frequency');
d += @Time;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));

// Different ways to set @scale vector:
@scale = {1, 5, 2.5};

@scale.x = 1;
@scale.y = d;
@scale.z = 0.5;

// This syntax doesn't work:
// @scale = {1, d, @Cd.g};

// Use set() function instead:
@scale = set(1, d, @Cd.g);
```
The @scale attribute allows non-uniform scaling on all three axes, unlike @pscale which scales uniformly. When creating vectors with variables or computed values, use the set() function rather than curly brace notation. The set() function is the proper way to construct vectors when incorporating math operations or variable references.

### Set Function for Vector Construction [Needs Review] [[Ep6, 21:10](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1270s)]
```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
@P = fit(sin(d), -1, 1, ch('min'), ch('max'));
@scale = d;

@scale.x = 1;
@scale.y = 0;
@scale.z = @Cd.g;

@scale = {1, 0, @Cd.g}; // nope

@scale = set(1, 0, @Cd.g); // better

float min, max, d, t;
min = ch('min');
```
Demonstrates the proper way to construct a vector using the set() function instead of brace notation when incorporating math operations or variable assignments. The set() function is preferred over curly braces {1, 0, @Cd.g} when building vectors with channel references or attribute components, especially when additional computation is involved.

### Vector Scale Using Set Function [Needs Review] [[Ep6, 21:18](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1278s)]
```vex
float d, t;
s = @Time * ch('speed');
s = length(@P);
s = ch('frequency');
d = t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@scale = d;

@scale = set(min, d, min);
```
Demonstrates transitioning from pscale to vector @scale attribute using the set() function. The code calculates a distance-based animation value using sine waves and fit(), then constructs a vector scale with set() to control per-axis scaling, allowing for more complex non-uniform scaling effects.

### Setting Scale with Vectors [[Ep6, 21:34](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1294s)]
```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d *= ch('frequency');
// d += t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;

float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Demonstrates transitioning from uniform @Pscale to non-uniform @scale attribute using vector values. The code comments out the previous uniform scaling approach and rewrites it to set @scale as a vector using set(), creating anisotropic scaling where different axes can scale independently based on the wave pattern.

### Non-uniform Scale with Vector [[Ep6, 22:00](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1320s)]
```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d = ch('frequency');
// d = t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @Cd.r = d;

@scale = {1, 5, 2.2};
```
Demonstrates setting the @scale attribute using vector literal syntax with curly braces to apply non-uniform scaling to geometry. Each component controls scaling on a different axis (X=1, Y=5, Z=2.2), showing how vectors can be assigned directly without separate component access.

### Vector initialization and scale attribute [[Ep6, 22:06](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1326s)]
```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d = ch('frequency');
// d = t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;
@scale = {1, 5, 2.2};

@scale.x = 1;
@scale.y = d;
@scale.z = @Cd.g;

@scale = {1, d, @Cd.g}; // nope

@scale = set(1, d, @Cd.g); // better

float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d = ch('frequency');
d = t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Demonstrates multiple methods of initializing vector values for the @scale attribute, comparing curly brace literal syntax (which doesn't work with variables) versus the set() function (which properly handles mixed literals and variables). Shows how to access individual vector components using .x, .y, .z notation and construct non-uniform scale values from channel parameters, time-based calculations, and color attributes.

### Non-uniform Scale Vector Assignment [[Ep6, 22:10](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1330s)]
```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d *= ch('frequency');
// d -= t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;
@scale = {1, 5, 2.2};

@scale.x = 1;
@scale.y = d;
@scale.z = @d.g;

float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d -= t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Demonstrates direct vector initialization using curly braces to set non-uniform scale values per axis. Shows how to assign a vector literal @scale = {1, 5, 2.2} to scale geometry differently on each axis (x=1, y=5, z=2.2). The code also includes commented-out animated scale code and component access examples.

### Non-Uniform Scale with Vectors [[Ep6, 22:14](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1334s)]
```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d = ch('frequency');
// d = t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;
@scale = (1, 5, 2.2);

float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d = ch('frequency');
d = t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Demonstrates setting non-uniform scale on points by assigning a vector to @scale. The first example uses a literal vector (1, 5, 2.2) to scale differently on each axis, then refactors to use the set() function to build a vector from computed values, where boxes scale 1x on X-axis, 5x on Y-axis, and 2.2x on Z-axis.

### Vector Assignment Syntax [[Ep6, 22:26](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1346s)]
```vex
// Direct vector literal assignment
@scale = {1, 5, 2.2};

// Component-wise assignment
@scale.x = 1;
@scale.y = d;
@scale.z = @Cd.g;

// Using set() function (preferred method)
@scale = set(1, d, @Cd.g);

// Complete example with set()
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Demonstrates three methods for assigning vector values: direct literal assignment with curly braces, component-wise assignment using dot notation, and the set() function which is the preferred method when mixing variables and literals. The set() function is more reliable than curly brace syntax when working with variable values.

### Non-uniform scaling with vector components [[Ep6, 22:40](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1360s)]
```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d *= ch('frequency');
// d += t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;

@scale.x = 1;
@scale.y = 2.5;
@scale.z = 0.5;

// Alternative approach:
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Demonstrates two methods for creating non-uniform scaling: directly setting individual vector components of @scale (x, y, z separately), or using the set() function to construct a vector with different values per axis. The commented code shows the evolution from uniform scaling to the final non-uniform approach.

### Vector Component Assignment with set() [[Ep6, 23:34](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1414s)]
```vex
// Commented out previous work:
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d = ch('frequency');
// d = t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;

// Direct component assignment works:
@scale.x = 1;
@scale.y = d;
@scale.z = @Cd.g;

// This syntax doesn't work with variables:
@scale = {1, d, @Cd.g}; // nope

// Must use set() function instead:
@scale = set(1, d, @Cd.g); // better

// Full working example:
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d = ch('frequency');
d = t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Demonstrates the limitation of curly bracket syntax for vector construction when using variables or attributes, showing that you cannot use {1, d, @Cd.g} with dynamic values. Instead, the set() function must be used to construct vectors with variable components, as in set(1, d, @Cd.g).

### Animating scale with sine waves [Needs Review] [[Ep6, 28:42](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1722s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d = d * ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```
Creates animated scaling by combining point distance from origin with time, modulating through a sine wave and fitting to min/max range. The scale attribute is set with the computed value affecting primarily the Y-axis, while X and Z remain at minimum scale.

### Non-uniform scale attribute with fit [Needs Review] [[Ep6, 29:28](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1768s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
```
Creates a non-uniform scale attribute by combining time-based animation with distance from origin. The code uses channel references for parameters, applies a sinusoidal wave modulated by both distance and time, then fits the result to a min/max range. The final scale vector allows different scaling in each axis (min, max, d) for use in copy-to-points instancing.

### Wave-based scaling and color with position [Needs Review] [[Ep6, 29:50](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1790s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Frame * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
t = fit(sin(d), -1, 1, min, max);
@scale = set(t, t, min);
@P.y = d/2;
t = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', t));
```
Creates animated wave-based scaling and coloring of geometry using sine waves modulated by distance from origin. The code calculates distance from origin, applies frequency and time offset, uses sine function to generate oscillating scale values, and applies a color ramp based on the distance value.

### Animated scale and color for instancing [Needs Review] [[Ep6, 30:02](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1802s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(d, 0, 1, min, max);
@scale = set(d, d, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Creates animated scale and color attributes on grid points for copy-to-points instancing. The distance from origin is calculated, modified by frequency and time parameters, then remapped to drive both uniform scale values and a color ramp lookup. Points are offset vertically by half their scale value to maintain ground contact.

### Animated Scale and Color on Grid Points [[Ep6, 30:20](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1820s)]
```vex
float min, max, d, i;
min = ch("min");
max = ch("max");
i = @Time * ch("speed");
d = length(@P);
d *= ch("frequency");
d += i;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp("color", d));
```
Creates animated scale and position offsets based on distance from origin, using sine waves driven by time. The code calculates distance from origin, applies frequency and animation, then uses the result to drive both a scale attribute for copy-to-points operations and vertical position displacement. Color is assigned via a ramp parameter mapped to the normalized distance value.

### Copy to Points Attribute Adjustment [[Ep6, 40:40](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2440s)]
```vex
float min, max, d, f;
min = ch('min');
max = ch('max');
f = @Time * ch('frequency');
d = length(@P);
d *= ch('frequency');
min = fit(sin(d), -1, 1, min, max);
@scale = set(min, min, d);
@P.y *= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Adjusts point attributes (scale, position, color) based on distance from origin for use with Copy to Points. Uses distance-based sine waves to create animated scaling effects, vertical position adjustments, and applies a color ramp based on normalized distance values.

### Setting Up Vector Orientation [[Ep6, 44:24](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2664s)]
```vex
v@up = {0,0,1};
```
Sets the up vector attribute to control orientation of copied geometry around the normal direction. The @up attribute defines which direction should be considered 'up' for the copy operation, with {0,0,1} pointing in the positive Z direction. This works in conjunction with the @N attribute to fully define the orientation of copied instances.

### Setting Up Vector for Copy to Points [[Ep6, 44:46](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2686s)]
```vex
v@up = {0, 0, 1};
```
Sets the up vector attribute to point in world Z direction, controlling the orientation of copied geometry around the normal axis. When used with Copy to Points, this explicitly defines how instances rotate around their pointing direction, with the Y-axis of copied geometry aligning to world Z.

### Setting Up Vector for Orientation [[Ep6, 45:10](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2710s)]
```vex
v@up = {0,0,1};

v@up = {0,1,0};

v@up = {0,v.y,1};
```
Demonstrates setting the @up vector attribute to control orientation around the normal vector. By explicitly setting @up to {0,0,1}, the local y-axis of oriented geometry will face the world z-axis, giving explicit control over rotation that Houdini would otherwise calculate automatically.

### Setting Up Vector for Orientation [[Ep6, 45:12](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2712s)]
```vex
v@up = {0,0,1};

v@up = {0,v.y};

v@up = {0,v.y,1};
```
Explicitly sets the @up vector attribute to control orientation of geometry. The final version sets the up vector to point along world Z-axis while maintaining the velocity's y-component, aligning the local z-axis with world z and orienting based on both velocity and the up vector.

### Setting Up Vector for Copy Orientation [[Ep6, 46:14](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2774s)]
```vex
v@up = {0, 1, 0};
```
Creates an up vector attribute that works with the normal vector to control the orientation of copied geometry. When used together, the normal and up vectors define a complete orientation system, preventing copied shapes from rotating freely around the normal axis.

### Animated Up Vector with Offset [[Ep6, 56:50](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3410s)]
```vex
float d = length(@P);
float t = @Time * d * v@offset;
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates an animated up vector that rotates in the XZ plane using sine and cosine, with the rotation speed modulated by distance from origin and an offset attribute. Additionally animates point Y positions with a frequency doubled sine wave, creating a combined rotation and wave effect.

### Animated Up Vector with Offset [Needs Review] [[Ep6, 56:58](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3418s)]
```vex
float d = length(@P);
float t = @Time * (1-offset);
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates an animated up vector that rotates in the XZ plane using sine and cosine, while simultaneously adding vertical oscillation to point positions. The offset variable controls the timing relationship between the rotation and vertical motion, allowing for phase-shifted animation effects.

### Extracting Packed Transform Matrix [[Ep7, 142:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8570s)]
```vex
matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);
4@a = pft;
```
Retrieves the packed full transform (4x4 transformation matrix) from a packed primitive using primintrinsic and stores it in a custom matrix attribute. This allows inspection and manipulation of the complete transformation data including translation, rotation, and scale information stored in packed geometry.

### Matrix Translation Component Visualization [Needs Review] [[Ep7, 144:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8658s)]
```vex
@P.x = @id == 1;
@P.y = 0.0;
@P.z = 0.5;
@Cd.x = 1;
@Cd.y = 0.0;
@Cd.z = 0.0;
@Cd.w = 1.0;
```
Demonstrates setting point position and color attributes to visualize matrix components. The position is conditionally set based on point ID, and color is set to red (RGB values with alpha). This code appears to be part of a larger demonstration explaining how 4x4 matrices encode translation values in the bottom row, with the upper 3x3 portion containing rotation and scale information.

### Primitive Intrinsics and Attribute Definition [Needs Review] [[Ep7, 155:26](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=9326s)]
```vex
int open_close = int(rand(@primnum)*frame**2);
setprimintrinsic(0, "closed", @primnum, open_close);

int @pnumclass = int(rand(@primnum)*2+1);
s@primattribs = "N, @closed, {Cd,uv@,@pnumclass}";
```
Sets a primitive intrinsic 'closed' attribute using randomized values based on primitive number and frame squared, then creates a primitive number classification and defines a string listing available primitive attributes. The code demonstrates both writing primitive intrinsics and documenting available attributes on geometry.

### Setting Orient Attribute Identity [[Ep7, 30:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=1814s)]
```vex
@orient = {0, 0, 0, 1};
```
Sets the orient attribute to an identity quaternion {0,0,0,1}, which represents no rotation and aligns geometry with the world axis orientation. This is the base level orientation where copied/instanced geometry will maintain their default orientation regardless of the point's rotation.

### Orient Attribute Transformation [Needs Review] [[Ep7, 91:44](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=5504s)]
```vex
// *orient
```
The *orient attribute can be prefixed with an asterisk to prevent it from being transformed by downstream transform nodes. This allows selective control over which attributes (like normals) get transformed versus which (like orientation) remain unchanged, preventing unwanted rotational transformations on specific attributes.

### Reading Color Attributes via UV Lookup [[Ep8, 54:40](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=3280s)]
```vex
i@primid;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', i@primid, @uv);

@Cd = primuv(1, 'Cd', i@primid, @uv);
```
Using xyzdist to find the closest primitive and UV coordinates on a grid, then using primuv to read both position and color attributes from that location. This allows points elevated above a grid to sample and adopt the color values from their nearest primitive below.

## See Also
- **VEX Attribute Access** (`vex_attributes.md`) -- attribute binding and type prefixes
- **VEX Fundamentals** (`vex_fundamentals.md`) -- wrangle execution contexts
