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
// Dot notation (.x/.y/.z) extracts a float from a vector; auto-promotes back to vector on assignment
@Cd = @P.x;
```

### Vector Component Access [[Ep1, 20:28](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1228s)]
```vex
// .x/.y/.z on any vector attribute extracts a float — useful for masks and visualizations
@Cd = @P.x;  // color = X position
@Cd = @N.y;  // color = Y normal component
```

### Type Casting and Point Color Normalization [[Ep1, 39:22](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2362s)]
```vex
// Integer / integer = integer in VEX — must cast to float for fractional results
@Cd = float(@ptnum)/100;  // correct: explicit cast

@Cd = @ptnum;             // wrong range: assigns large integers directly

@Cd = @ptnum/@numpt;      // normalize 0-1 by dividing by total point count
```

### Variable Declaration and Type Casting [[Ep1, 50:52](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3052s)]
```vex
// Progression: inline -> cast -> named variable for readability
@Cd = sin(@ptnum);                        // @ptnum is int, sin() promotes it
@Cd = sin(@ptnum/100);                    // still int division — wrong
@Cd = sin(float(@ptnum)/100);             // correct: explicit float cast
@Cd = sin(float(@ptnum)*ch('scale'));     // add channel-driven scale
// Using a named variable makes complex expressions easier to read and debug:
float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
float foo = float(@ptnum)*ch('scale');
@Cd = sin(foo);
```

### Variables vs Attributes [[Ep1, 54:06](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3246s)]
```vex
// Local var (foo): temporary, lives only in this wrangle, never saved to geo
// Attribute (@Cd):  persists on the geometry after the wrangle runs
float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
```

### Animating with @Time [[Ep1, 96:50](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5810s)]
```vex
// @Time is a built-in attribute (capitalized) — current time in seconds, auto-updates each frame
// Static radial sine wave:
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d),-1,1,0,1);

// Animated version: add @Time to the distance to make the wave travel over time
@Cd = fit(sin(d+@Time),-1,1,0,1);
```

### @Time Animation Variations [[Ep1, 96:56–97:48](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5816s)]
```vex
// @Time = current time in seconds (at 24fps, equals 1.0 after 24 frames)
// @Frame increments by 1 per frame — faster animation than @Time
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');

// Static wave (no time)
@Cd = fit(sin(d), -1, 1, 0, 1);

// Travelling wave: add @Time to shift the pattern each frame
@Cd = fit(sin(d + @Time), -1, 1, 0, 1);

// Multiply @Time into the distance for frequency-scaled animation
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);
```

### Ramp Modulo Behavior Change [Needs Review] [[Ep2, 50:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3046s)]
```vex
// chramp() no longer implicitly modulos values — repeating patterns need explicit fmod()
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
@P.y = fit01(d, -0.1, 0.1);
@Cd.y = chramp("myRamp", d);
@Cd.y *= ch("height");
```

### Pseudo Attributes and Point Primitives [Needs Review] [[Ep3, 11:32](https://www.youtube.com/watch?v=fOasE4T9BRY&t=692s)]
```vex
// Pseudo attributes (@P, @ptnum, @Time) are computed by Houdini, not stored in geo
// Primitive @P = centroid of primitive's point positions (computed, not stored)
float d = len(v@P - p1(0, @primnum, 0));
s@ry = sin(d);
```

### Pseudo Attributes and Compilation [Needs Review] [[Ep3, 11:34](https://www.youtube.com/watch?v=fOasE4T9BRY&t=694s)]
```vex
// VCC compiler command (not VEX code)
// VCC -q $VOP_INCLUDEPATH -o $VOP_OBJECTFILE -e $VOP_ERRORFILE $VOP_SOURCEFILE
```

### Vertex Attribute Manipulation with Distance [[Ep3, 14:38](https://www.youtube.com/watch?v=fOasE4T9BRY&t=878s)]
```vex
// Vertex wrangles run per-vertex — more iterations than points (each point has multiple vertices)
float d = length(@P);
d *= ch('scale');
@Cry = sin(d);
```

### Creating Custom Attributes [[Ep3, 21:42–22:14](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1302s)]
```vex
// @ prefix creates a geometry attribute — appears in the spreadsheet and persists after the wrangle
// f@ prefix explicitly declares a float attribute (vs auto-detected type)
float d = length(@P);
@mydistance = d;          // custom attribute stores distance for debugging / reuse
@Cd.r = sin(d);

// Explicit type prefix version:
f@d = length(@P);
f@d /= ch("scale");
@Cd = @d;
@Cd.r = sin(@d);

// Minimal form: create attribute and drive color in three lines
float d = length(@P);
@d = d;
@Cd.r = sin(@d);
```

### Distance to Point with Fit [Needs Review] [[Ep3, 37:22](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2242s)]
```vex
// Read point 0 position from first input, measure distance, remap for color
vector pos = v@pos[0];
float d = distance(pos, @P);
d *= ch('scale');
f@Cd = fit(d, 0, 1, 0, 1);
```

### Distance-based color and wind [Needs Review] [[Ep3, 37:50](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2270s)]
```vex
// @opinput1_P reads position from second wrangle input by matching point number
vector pos = v@opinput1_P;
float d = distance(@P, pos);
f@scale = d;
@Cd = d;
v@v = v@wind * d;  // proximity-based velocity: farther points get more wind
```

### Transfer Color via Nearest Point [[Ep3, 39:58–44:24](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2398s)]
```vex
// nearpoint(input, pos) -> point number of closest point on that input
// point(input, "attribname", ptnum) -> reads attribute — name MUST be a string, not @ syntax
int pt = nearpoint(1, @P);
@Cd = point(1, "Cd", pt);   // transfers color from nearest point on input 1

// Same pattern reading from input 0:
int pt = nearpoint(0, @P);
@Cd = point(0, 'Cd', pt);

// If the attribute doesn't exist on the input, point() returns zero (0,0,0 for vectors) — no error
v@Cd = point(0, "Cd", pt);  // returns {0,0,0} (black) if Cd doesn't exist
```

### Point Attributes from Second Input [[Ep3, 49:58–52:36](https://www.youtube.com/watch?v=fOasE4T9BRY&t=2998s)]
```vex
// Two equivalent ways to copy point positions from input 1 by point number:
@P = point(1, 'P', @ptnum);   // explicit: point(input, attrib, ptnum)
@P = @opinput1_P;             // shorthand: @opinput<N>_<attrib> — same result, cleaner syntax
```

### Reading Multiple Attributes from Second Input [[Ep3, 55:14](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3314s)]
```vex
// @opinput1_<attrib> reads any attribute from input 1 at the same point number
// Requires matching point counts between inputs
vector pi  = @opinput1_P;
vector cd1 = @opinput1_Cd;
@P  = pi;
@Cd = cd1;
```

### Reading Quaternion Point Attributes [[Ep3, 59:56](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3596s)]
```vex
// Read position and color from a point struct (e.g. from slerp/quat lookup)
vector p1  = swlerpquat.p1;
vector cd1 = swlerpquat.Cd1;
@P  = p1;
@Cd = cd1;
```

### Vector component assignment clarity [[Ep3, 74:02](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4442s)]
```vex
// Initialize the full vector first, then modify individual components for clarity
@Cd = v1;
@Cd.x = curlnoise(@P*chv('fancyscale'))*@Time;
```

### Reading Point Position from Second Input [Needs Review] [[Ep4, 11:06](https://www.youtube.com/watch?v=66WGmbykQhI&t=666s)]
```vex
// dot(chv("angle"), pos) projects position onto a viewport-controlled direction vector
vector pos = point(1, "P", @ptnum);
@Cd = dot(chv("angle"), pos);
```

### Reading Point Positions with point() [[Ep4, 34:34](https://www.youtube.com/watch?v=66WGmbykQhI&t=2074s)]
```vex
// @P = current point; point(input, attrib, ptnum) = specific point from any input
vector a = @P;
vector b = point(1, 'P', 0);  // point 0 from input 1
```

### Reading points from multiple inputs [[Ep4, 34:40](https://www.youtube.com/watch?v=66WGmbykQhI&t=2080s)]
```vex
// point(input, "attrib", ptnum) — first arg is input index (0=first, 1=second)
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);
@i = b - a;  // direction vector from input-0 point 0 to input-1 point 0

// Using current point as 'a':
vector a = @P;
vector b = point(1, "P", 0);
```

### Point-to-Point Normal Direction [[Ep4, 37:18](https://www.youtube.com/watch?v=66WGmbykQhI&t=2238s)]
```vex
// Subtract two positions to get a direction vector and assign to @N
// Using @P (current point) makes every point aim its normal at a single target
vector a = @P;
vector b = point(1, 'P', 0);
@N = b - a;
```

### Vector Direction from Point [[Ep4, 38:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=2294s)]
```vex
// @P - origin = vector radiating outward from origin — useful for explosion/sim initial velocities
vector origin = point(1, "P", 0);
@v = @P - origin;
```

### Multiplying Normals by Channel Parameter [[Ep4, 41:58](https://www.youtube.com/watch?v=66WGmbykQhI&t=2518s)]
```vex
// *= preserves direction and scales length; = would set all components to the same scalar
@N *= ch('scale');
```

### Scaling Normals with Vectors [[Ep4, 44:20](https://www.youtube.com/watch?v=66WGmbykQhI&t=2660s)]
```vex
// Multiply by a vector for per-axis scaling: zero flattens, negative reverses
@N *= chv('scalevec');
```

### Component Access on Vectors [[Ep4, 53:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=3182s)]
```vex
// relpointbbox() returns normalized 0-1 position within the bounding box
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;  // black-to-white gradient along Y axis
```

### Vector Component Access [[Ep5, 20:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=1250s)]
```vex
// Two equivalent ways to access vector components: dot notation or array index
vector myvector = {1, 2, 1};
v@a = {10, 12, 100};
float foo = @a.x;   // dot notation  -> 10  (x=0, y=1, z=2)
float foo = @a[2];  // index notation -> 100 (index 2 = z component)
```

### Vector component access methods [Needs Review] [[Ep5, 25:18](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=1518s)]
```vex
// .x/.y/.z and .r/.g/.b are interchangeable on vectors; arrays needed for >3 elements
vector @vector = {1,2,3};
v@a = {10,15,100};
@foo = @x+1;
```

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
