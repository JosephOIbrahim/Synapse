# VEX Corpus: Math Operations

> 981 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Beginner (77 examples)

### Rotate a single point with sin and cos â

```vex
@P.x = sin(@Time);
@P.y = cos(@Time);
```

Say you have a single point at the origin, and you want to animate it going round in a circle.

### Normalizing vectors â

```vex
vector axis = p0-p1;
```

Martin Geupel via twitter sent me this:

...youÂ mightÂ wantÂ toÂ normalizeÂ theÂ axisÂ inÂ yourÂ "RotateÂ primsÂ aroundÂ anÂ edge"Â tutorialÂ onÂ theÂ HoudiniVexÂ pageÂ ;)

When I wrote this tutor....

### Mixing vex and vops with snippets â

```vex
P = P * myvector;
```

Often I'll start something in vops, then realise part of my network would be much neater as a few lines of vex.

### Arrays â

```vex
int myarray[] = {1,2,3,4};

int foo = myarray[2];
```

Standard vex array variables are like most c-style languages:

You can create array attributes too by inserting '[]' between the type declaration and the @:

You can use the opintputN syntax from b....

### Query image width and height â

```vex
string map=chs('image');
float x, y;
teximport(map, 'texture:xres', x);
teximport(map, 'texture:yres', y);
@ratio = x/y;
```

Download hip: Download file: uv_scale_from_image.hip

The teximport function lets you query a few proprties of an image (full list here: https://www.sidefx.com/docs/houdini/vex/functions/teximport.....

### itoa and 64 bit precision limits â

```vex
s@test= itoa(2200000000);
// returns -2094967296
```

Someone on discord had an issue that could be summarised as this:

This is due to limits of the default 32 bit integer type; values above around 2100000000 will wrap around to negative values.

The....

### Basic maths â

```vex
@Cd = @P.x + 3;
```

Vex is based on C (like a lot of computer languages), meaning that simple arithmetic is easy to do.

For example, if you switch to the grid, and use @Cd = @P.x, if you look at the geometry spreadsh....

### Assigning to components â

```vex
@Cd.x = @P.x-3 * 1.2;
 @Cd.y = @P.z+2;
 @Cd.z = @P.y;
```

Earlier we were reading components and assigning to @Cd.

### Channels â

```vex
@Cd = float(@ptnum)/ch('scale');
```

When using wrangles, you'll find that you'll get certain values you want to keep changing, like the second part of the wrangle code above.

### Sine â

```vex
@Cd = sin(@ptnum);
```

Time to introduce our first vex function, sin :

This gives a basic wave function that oscillates between -1 and 1.

### Variables â

```vex
float foo = float(@P.x)/ch('scale');
 @Cd = sin(foo);
```

Debated bringing this up on day 1 or wait until later, but you're a big kid, you can handle it.

Things prefixed with an @ are attributes , data sitting on the geometry.

### Component Math Operations

```vex
@Cd = @P.x + 1;

@Cd = @P.x - 0;

@Cd = @P.x * 6 * 0.1;

@Cd = (@P.x - 6) * 0.1;
```

Demonstrates basic mathematical operations on a single component of a vector attribute.

### Arithmetic Operations on Color

```vex
@Cd = @P.x + 3;

@Cd = @P.x - 6;

@Cd = @P.x * 6 * 0.1;

@Cd = (@P.x - 6) * 0.1;
```

Demonstrates basic arithmetic operations (addition, subtraction, multiplication) applied to position values to modify color attributes.

### Scaling Color Values with Multiplication

```vex
@Cd = (@P.x * 6) * 0.1;
```

Demonstrates using parentheses to control order of operations when calculating color from position.

### Remapping Position to Color Components

```vex
@Cd.x = @P.x * 3 * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;
```

Demonstrates remapping position components to color channels in non-standard ways.

### Normalizing Point Numbers for Color

```vex
@Cd = @ptnum;

@Cd = @ptnum / @numpt;
```

Demonstrates the problem of directly assigning point numbers to color (values exceed 1.0 and appear white) and the solution of dividing by the total point count to create a normalized 0-1 color ramp.

### Integer Division Pitfall

```vex
@Cd = @ptnum / @numpt;
```

Demonstrates a common VEX pitfall where dividing two integers (@ptnum and @numpt) results in integer division, producing zero for all points because the fractional component is truncated.

### Integer Division Pitfall

```vex
@Cd = @ptnum/@numpt;

@Cd = float(@ptnum)/@numpt;

@Cd = float(@ptnum)/100;
```

Demonstrates a common VEX pitfall where dividing two integers (@ptnum and @numpt) results in integer division, producing zero for most points.

### Type Casting to Float

```vex
@Cd = float(@ptnum)/@numpt;

@Cd = float(@ptnum)/@numpt;

@Cd = float(@ptnum)/100;
```

Demonstrates the need for type casting to avoid integer division truncation.

### Float Casting for Color Division

```vex
@Cd = float(@ptnum) / @numpt;

// Alternative with fixed denominator:
// @Cd = float(@ptnum) / 100;
```

Demonstrates casting @ptnum to float before division to avoid integer division truncation.

### Type casting for normalized color values

```vex
@Cd = float(@ptnum)/@numpt;
```

Demonstrates type casting by wrapping @ptnum in float() to ensure floating-point division when dividing by @numpt.

### Normalizing Point Numbers with Division

```vex
@Cd = float(@ptnum) / @numpt;
```

Divides the current point number by the total number of points to create a normalized 0-to-1 gradient across all points.

### Normalizing point numbers with division

```vex
@Cd = float(@ptnum)/@numpt;

// Alternative using hardcoded value:
@Cd = float(@ptnum)/100;
```

Demonstrates how to create a gradient by dividing @ptnum by @numpt to get normalized values between 0 and 1, where @ptnum changes for each point while @numpt remains constant as the total point count.

### Type Casting and Point Color Normalization

```vex
@Cd = float(@ptnum)/100;

@Cd = @ptnum;

@Cd = @ptnum/@numpt;
```

Demonstrates the importance of type casting in VEX when dividing integers.

### Normalizing Point Numbers to Color

```vex
@Cd = float(@ptnum)/100;

@Cd = float(@ptnum)/@numpt;

@Cd = float(@ptnum)/@numpt;

@Cd = float(@ptnum)/10.0;
```

Demonstrates multiple approaches to converting point numbers to normalized color values, showing the progression from hardcoded division to using the @numpt attribute for proper normalization.

### Channel References in VEX

```vex
@Cd = float(@ptnum)/100;

@Cd = float(@ptnum)/@numpt;

@Cd = float(@ptnum)/10;

@Cd = float(@ptnum)/ch('scale');
```

Demonstrates different approaches to normalizing color values by dividing point numbers, culminating in the use of ch() to reference a parameter slider.

### Channel references in expressions

```vex
@Cd = float(@ptnum)/100;

@Cd = float(@ptnum)/ch('scale');

@Cd = float(@ptnum)/ch();
```

Demonstrates replacing hardcoded numeric values with channel references using the ch() function to create UI parameters.

### Channel references for parameter control

```vex
@Cd = float(@ptnum)/ch('scale');

@Cd = sin(@ptnum);
```

Demonstrates using the ch() function to reference a user interface parameter ('scale') that controls color output, allowing for interactive art direction without rewriting code.

### Channel References and Sine Function

```vex
@Cd = float(@ptnum)/ch('scale');

@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);
```

Demonstrates using channel references with ch() to control color gradients by dividing point numbers, then introduces the sine function to create oscillating color patterns.

### Sine Wave Color Animation

```vex
@Cd = sin(@ptnum/100);
```

Uses the sine function to create an oscillating color value based on point number.

### Channel-driven Sine Wave Color

```vex
@Cd = sin(float(@ptnum)/ch("scale"));
```

Uses a channel reference to control the frequency of a sine wave applied to point color, allowing interactive art direction of the color pattern.

### Color with sine and channel reference

```vex
@Cd = sin(float(@ptnum)/ch('scale'));
```

Uses a sine wave function to create oscillating color values based on point number, divided by a channel slider named 'scale' for art-direction control.

### Variables for Code Clarity

```vex
float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
```

Demonstrates using a local variable 'foo' to store an intermediate calculation before applying it to @Cd.

### Position-Based Color with Channel

```vex
float foo = float(@P.x)/ch('scale');
@Cd = sin(foo);
```

Demonstrates driving color by X position instead of point number, dividing position by a channel-referenced scale parameter and applying sine function.

### Sine Wave Color with Channel Reference

```vex
float foo = @P.x/ch('scale');
@Cd = sin(foo);
```

Demonstrates using a variable to store a normalized position value divided by a channel parameter, then applying a sine function to drive color.

### Length Function and Distance Calculations

```vex
float d = length(@P);
@Cd = sin(d);
```

Demonstrates using the length() function to calculate the distance from the origin to each point's position, then applying sine wave modulation to create a color gradient based on that distance.

### Distance to Origin and Sine Wave

```vex
float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
```

Calculates the distance from each point to the origin using length(@P) and applies it to the color attribute.

### Converting Parameters to Vector Type

```vex
vector pos = @P * chv('scale');
vector center = chv('center');
float dist = distance(pos, center);
dist *= chv('scale');
@Cd = (sin(dist) * 1) * 0.5;
```

Demonstrates how to manage spare parameters when converting between types (float to vector).

### Multi-line operations for readability

```vex
float foo = 1;
foo *= 3;          // set range
foo += 1;          // make sure values never get below 0
foo /= @Cd.x;      // reduce range to within red value
foo += @N.y;       // addition normal on y
```

Breaking complex mathematical operations across multiple lines with comments improves code readability and maintainability.

### Length function with fit remapping

```vex
int i = 1 + len(@P);
f@x = fit(sin(i), 0, 1, 0.1, 3.1);
```

Uses the len() function to calculate the length of the position vector, adds 1, then applies sine and remaps the result from 0-1 range to 0.1-3.1 range using fit().

### Distance-Based Displacement

```vex
float d = length(@P);
@P.y = d;
```

Calculates the distance from the origin to each point using length(@P) and assigns that distance value to the Y position, creating a displacement effect.

### Length Function for Distance Mapping

```vex
float d = length(@P);
@P.y = -d + 10;
```

Uses the length function to calculate distance from origin, then remaps this distance to the Y position with inversion and offset.

### Cone Height Manipulation with Distance

```vex
float d = length(@P);
@P.y = d * 0.2;
```

This snippet calculates the distance of each point from the origin using length(@P), then uses that distance to set the Y position, creating a cone shape.

### Distance Mapping and Inversion

```vex
float d = length(@P);
```

Calculates the distance from the origin to each point using the length() function on the position attribute.

### Distance from Origin

```vex
float d = length(@P);

@P.y = d;
```

Calculates the distance of each point from the origin using the length() function, then remaps the Y position of each point based on that distance value.

### Modulo operator with Time

```vex
@P.y = @Time % 5;

@Cd.r = @Time % 0.7;
```

Demonstrates using the modulo operator (%) with the @Time global variable to create cyclic animation values.

### Modulo positioning and time-based color

```vex
@P.y = @ptnum % 5;

@Cd.r = @Time % 0.7;
```

Uses the modulo operator to create vertical position patterns based on point numbers, and applies time-based modulo to drive red color channel cycling.

### Scaling distance and sine color

```vex
@d *= ch("scale");
@Cd = 0;
@Cd.r = sin(@d);
```

Scales a custom distance attribute @d using a channel parameter, initializes the color attribute to zero, then sets the red component using the sine of the scaled distance.

### Distance Attributes and Color Assignment

```vex
float d = length(@P);
@mydistance = d;

@d = length(@P);
@Cd = d;
@Cd.r = sin(@d);
```

Demonstrates creating custom attributes by calculating distance from origin using length(@P), storing it in variables and custom attributes like @mydistance and @d.

### Cross product with custom axis

```vex
@N = cross(@N, {1, -1, 0});
```

Computes the cross product between the normal vector and a custom axis vector {1, -1, 0}, causing normals to rotate around that specified axis.

### Dot Product Snow Effect

```vex
float d = dot(@N, {0,1,0});
@Cd = {0,0,1};
if(d > 0.5){
    @Cd = {1,1,1};
}
```

Uses a dot product between surface normals and the up vector to simulate snow settling on top surfaces.

### Vector component access methods

```vex
vector @vector = {1,2,3};
v@a = {10,15,100};

@foo = @x+1;
```

Demonstrates creating vector attributes and accessing vector components using different notations.

### Array Indexing and Retrieval

```vex
float myFloatArray[] = {1,2,3,4,5};
vector myVectorArray[] = {{1,2,3},{4,5,6},{7,8,9}};

f[]@a = {2,3,4,5};
v[]@vecs = {{1,2,3},{4,5,6}};

f@b = f[]@a[2];
v@c = v[]@vecs[1];
```

Demonstrates accessing individual elements from float and vector arrays using zero-based indexing.

### Variable in Vector Literal

```vex
float a = 42;
vector myvec = {a, 2, 3};
```

Demonstrates that variables cannot be directly used inside vector literal syntax with curly braces {a, 2, 3}.

### Normal-based color with fallback

```vex
@Cd = @N;
if (length(@Cd) < 0) {
    @Cd = 0.1;
}
```

Sets color based on the point normal, with a conditional check that appears to have an OCR error (length cannot be negative).

### Visualizing Normals with Color

```vex
@Cd = @N;
if (min(@Cd) < 0) {
  @Cd = 0.1;
}
```

Assigns the normal vector to the color attribute for visualization, but negative color values render as black.

### Conditional Coloring Based on Normals

```vex
@Cd = @N;
if (sin(@d) < 0) {
    @Cd = 0.1;
}
```

Colors geometry based on normal direction, with front faces colored according to their axis-aligned normal components and back faces (where sine of @d is negative) colored a uniform gray (0.1).

### Setting Up Vector for Copy Orientation

```vex
v@up = {0, 1, 0};
```

Creates an up vector attribute that works with the normal vector to control the orientation of copied geometry.

### Distance-based displacement with scaling and offset

```vex
float d = length(@P);
@P.y = d * 0.2 - 10;
```

This code calculates the distance from the origin using length(@P), then uses that distance to displace points vertically with a scale factor of 0.2 and an offset of -10.

### Distance calculations and remapping

```vex
float d = length(@P);
@P.y = d*-1 + 10;
```

Calculates the distance from the origin using length() and remaps it to position points vertically, demonstrating various transformation approaches from simple distance to inverted and scaled values.

### Sine Wave Output Range

```vex
@P.y = sin(@P.x);
```

The sine function outputs values constrained between -1 and 1, with the lowest point at -1 and highest at 1.

### Modulo Operator for Looping Values

```vex
@P.y = @ptnum % 5;
```

The modulo operator (%) returns the remainder of division, creating a cycling pattern of values from 0 to 4.

### Modulo with Color Attributes

```vex
@Cd.r = @Time % 0.7;
```

Demonstrates using the modulo operator with the @Time attribute to create a repeating sawtooth pattern in the red color channel.

### Modulo Operator Looping Behavior

```vex
@Cd.r = @Time % 0.2;
```

Demonstrates the modulo operator with @Time to create a looping animation that cycles between 0 and 0.2.

### Distance-based Color with Sine Wave

```vex
float d = len(v@P);
v@Cd = set(d);
v@Cd.y = sin(d);
```

Calculates the distance from origin for each point, assigns it to all color channels, then modulates the green channel with a sine wave based on distance.

### Creating Custom Attributes from Distance

```vex
float d = length(@P);
@d = d;
@Cd.r = sin(@d);
```

Demonstrates creating custom attributes dynamically in VEX by calculating distance from origin and storing it in a custom attribute @d.

### Distance-Based Color Using fitrange

```vex
vector pos = fitrange(1, @ptnum);
float d = distance(@P, pos);
d *= ch('scale');
@Cd = d;
@Cd *= ch('id');
```

Creates a color gradient based on the distance from each point to a position calculated using fitrange, scaled by two channel parameters.

### Copying Attributes Between Inputs

```vex
@P = @opinput1_P;
```

Demonstrates multiple methods to copy attributes from a second input, progressing from verbose nearpoint/point lookups to the streamlined @opinputN_attribute syntax.

### Channel Reference for Multiplication

```vex
ch('scale');
```

A channel reference using ch() to retrieve a parameter value named 'scale', which will be used for multiplication operations with normals.

### Dot product normal coloring

```vex
float d = dot(@N, {0,1,0});
@Cd = {0,0,0};
if (d > 0) {
    @Cd = {1,1,1};
}
```

Uses the dot product to compare each point's normal vector against an upward-pointing vector {0,1,0}.

### Vector Component Access

```vex
vector myvector = {1, 2, 1};

v@a = {10, 12, 100};

float foo = @a.x; // will return 10

float foo = @a[2]; // that's asking for index 2, which will return 100
```

Demonstrates two methods for accessing vector components in VEX: dot notation (@a.x) for named access to x/y/z components, and array index notation (@a[2]) for numeric index access where 0=x, 1=y, 2=z.

### Array Syntax in VEX

```vex
float myFloatArray[] = {1, 2, 3, 4.5};
vector myVectorArray[] = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};

f[]@a = {1, 2, 3, 4.5};
v[]@vecs = {{1, 2, 3}, {4, 5, 6}, {7, 8, 9}};

@P = f[]@a[2];
v@c = v[]@vecs[1];
```

Arrays in VEX can be declared using bracket notation for both local variables and attributes.

### Point Array Variable Declaration

```vex
int pts[];
int pt;
```

Declares two integer variables: an empty array 'pts' to store multiple point numbers, and a single integer 'pt' for individual point operations.

### Color from Normal with Clamping

```vex
@Cd = @N;
if (min(@Cd) < 0) {
    @Cd = 0.1;
}
```

Sets point color equal to the normal vector, then checks if any color component is negative using the min() function.

### Circular Motion with Up Vector

```vex
v@up = set(sin(@Time), 0, cos(@Time));
```

Creates circular motion by setting the up vector using sine and cosine of @Time, keeping the Y component at zero so the vector rotates in a horizontal plane.

### Time-based rotation with point offset

```vex
float t = @Time * @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));
```

Creates a time variable that combines the current time with the point number, scaled by 0.1 to create per-point timing offsets.

### Normal and Up Vector Setup

```vex
@N = normalize(@P);
@up = {0,1,0};
```

Sets the normal vector (@N) to the normalized position of each point, making it point radially outward from the origin.

## Intermediate (774 examples)

### Rotate geometry with sin and cos â

```vex
float angle = atan(@P.x, @P.y);

@P.x += sin(@Time+angle);
@P.y += cos(@Time+angle);
```

The problem is all the points are getting an identical rotation value.

### Rotate into a twirl or spiral â

```vex
float angle = atan(@P.x, @P.y);
float r = length(set(@P.x, @P.y));
float amount = radians(ch('amount'));
float twirl = r*ch('twirl');

@P.x = sin(amount+angle+twirl)*r;
@P.y = cos(amount+angle+twirl)*r;
```

Now you can experiment with silly things.

### Joy of Vex Day 2 â

```vex
float d = length(@P);
```

Length and distance functions, animate with @Time

Vex has lots of functions.

### Fit â

```vex
vector pos = @P * chv('fancyscale');
 vector center = chv('center');
 float d = distance(pos, center );
 d *= ch('scale');
 @Cd = fit(sin(d),-1,1,0,1);
```

That add one and divide by 2 step can be replaced by another function, fit .

### Other uses for length, and introduce clamp â

```vex
float d = length(@P);
 @P.y = d;
```

Take out sin for now, go back to a grid, map d to P.y:

Get an inverted cone.

### Chramp and waves â

```vex
float d = length(@P);
 d *= ch('scale');
 @P.y = chramp('myramp',d);
```

Eg, to alter distance from the previous lesson:

So we specify the name of the ramp (myramp, but it could be anything), and what will be used for the x-axis, d in this case.

If you're doing this f....

### Making smooth things stepped via quantising â

```vex
float d = length(@P);
 d *= ch('scale');
 @P.y = d;
```

Go back to the usual trick of P.y based on distance to the origin:

The result is a smooth funnel shape.

### Faking trunc with a chramp â

```vex
float d = length(@P);
 d *= ch('pre_scale');
 d = chramp('my_stepped_ramp', d);
 d *= ch('post_scale');
 @P.y = d;
```

An equally valid way to get stepping is to draw in a stepped graph into a channel ramp.

### Joy of Vex Day 6 â

```vex
float d = length(@P);
 d *= ch('scale');
 @Cd = 0;
 @Cd.r = sin(d);
```

Point wrangle vs prim wrangle vs detail wrangle, user defined attributes

Set colour from a sine wave based distance as we've been doing:

Now on the 'run over' drop down, change it from points to ....

### Moving beyond P N Cd ptnum â

```vex
float d = length(@P);
 @mydistance = d;
```

All the demos so far have written results directly to position or colour.

### Joy of Vex Day 10 â

```vex
@P = normalize(@P);
```

relpointbbox

I mentioned earlier that normalising values makes a lot of operations easier, saves you having to mentally scale values to match.

### Testing for equality â

```vex
int a = 3;
int b = 3;
if ( a == b) {   // yes this works
```

Say we had two variables a and b, and want to test if they're equal.

### Bonus chapter, ternary operator, yet another way to format if statements â

```vex
@Cd = @Time%1==0 ? 1 : 0;
```

There's a super terse shorthand if statement that combines test and assignment and else all in one line called the ternary operator:

That means 'if Time modulo 1 (ie its exactly on the 1 second, 2....

### Arrays â

```vex
vector myvector = {1,2,3};
```

Arrays are lists of values.

### Scaling and offsetting position for color

```vex
@Cd = @P.x;

@Cd = @P.x - 1;

@Cd = @P.x - 0;

@Cd = @P.x * 6 * 0.1;

// ...
```

Demonstrates basic mathematical operations (subtraction, multiplication) applied to a single component of position (@P.x) to control color values.

### Normalizing Point Numbers for Color

```vex
@Cd.x = @P.x;
@Cd.y = @P.y;
@Cd.z = @P.z;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.x + 2;
@Cd.z = @P.y;

// ...
```

Demonstrates progression from directly mapping position to color, to assigning raw point numbers (which exceed the 0-1 color range), to normalizing point numbers by dividing by total point count to....

### Channel References in VEX

```vex
@Cd = float(@ptnum)/ch('scale');
```

Demonstrates using the ch() function to reference a parameter slider, allowing dynamic control of the color ramp scale instead of hardcoding values.

### Sine Function for Color Animation

```vex
@Cd = float(@ptnum)/ch('scale');

@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

// ...
```

Demonstrates using the sine function to create oscillating color values based on point numbers.

### Sine Function for Color Animation

```vex
@Cd = float(@ptnum)/ch('scale');

@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

// ...
```

Demonstrates the progressive refinement of using the sine function with point numbers to create animated color patterns.

### Sine wave color oscillation

```vex
@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)/ch('scale'));

// ...
```

Demonstrates using the sin() function to create oscillating color values based on point numbers.

### Sine Wave with Integer Division

```vex
@Cd = sin(@ptnum/100);

@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

// ...
```

Demonstrates the progression from integer division producing chunky results to proper float casting for smooth sine wave color gradients.

### Sine waves with CH function

```vex
@Cd = sin(float(@ptnum)/ch('scale'));

// Evolution from hardcoded to parameterized:
// @Cd = sin(@ptnum);
// @Cd = sin(@ptnum/100);
// @Cd = sin(float(@ptnum)/100);
// @Cd = sin(float(@ptnum)/ch('scale'));

// ...
```

Creates a smooth sine wave pattern by dividing point number by a user-controlled scale parameter.

### Variables and Channel References

```vex
@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)*ch('scale'));

// ...
```

Demonstrates storing intermediate calculations in variables rather than inline expressions.

### Variable Declaration and Type Casting

```vex
@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)*ch('scale'));

// ...
```

Demonstrates the progression from inline expressions to using named variables for code clarity.

### Distance-based color with sine wave

```vex
float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
d *= chf('scale');
// ...
```

Demonstrates progressive enhancement of distance-based coloring.

### Distance-based Color with Sin Function

```vex
float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
d *= ch('scale');
// ...
```

Demonstrates progressive refinement of distance-based coloring: first assigning raw distance to color, then applying sine function for oscillating patterns, and finally adding a channel reference f....

### Distance and Sine Progression

```vex
float foo = @P.y*ch('scale');
@Cd = sin(foo);

float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);
// ...
```

A progression showing how to calculate distance from origin using length(@P) and apply sine waves to create color patterns.

### Distance-based color with sin wave

```vex
float d = length(@P);

float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

// ...
```

Demonstrates progressive development of distance-based coloring by first calculating distance from origin using length(@P), then applying that to color, then adding a sine wave pattern, and finally....

### Distance from Origin Visualization

```vex
float d = length(@P);
@Cd = d;

// Applying sine wave
float d = length(@P);
@Cd = sin(d);

// With ramp (note: chramp alone doesn't work without input)
// ...
```

Calculates each point's distance from the origin using length(@P) and assigns it to color (@Cd) to visualize the distance field.

### Distance-based color with sine

```vex
float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
@Cd = ch('scale');
// ...
```

Demonstrates using distance from origin to drive color values.

### Scaling Distance with Compound Operators

```vex
float d = length(@P);
d *= ch('scale');
@Cd = sin(d);
```

Demonstrates the compound assignment operator *= to scale a distance value.

### Scaling Distance with Compound Assignment

```vex
float d = length(@P);
d *= ch("scale");
@Cd = sin(d);
```

Demonstrates using the compound assignment operator (*=) to scale the distance value by a channel parameter.

### Sine wave pattern generator

```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)/2;
```

Creates a radial ring pattern by calculating distance from origin, scaling it with a channel parameter, and applying sine function to generate oscillating color values.

### Remapping sine values for color

```vex
float d = length(@P);
d *= ch('scale');
@Cd = sin(d) + 1;

float d = length(@P);
d *= ch('scale');
@Cd = sin(d);

// ...
```

Demonstrates fixing negative sine values for color attributes by adding 1 to shift the range from [-1,1] to [0,2], which prevents negative color values that would cause rendering issues.

### Remapping sine wave range

```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d) + 1) / 2;
```

Demonstrates remapping a sine function output from [-1, 1] to [0, 1] range for color values.

### Normalizing sine wave color range

```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)/2;

// Alternative compact form:
@Cd = (sin(length(@P) * ch('scale'))+1)*0.5;
```

Demonstrates how to normalize sine wave output from a range of [-1,1] to [0,1] for color values.

### Scaling distance with channel reference

```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```

Calculates distance from origin and scales it using a channel parameter for control.

### One-line vs multi-line code readability

```vex
@Cd = (sin(length(@P)*ch('scale'))+1)*0.5;
```

Demonstrates that complex VEX expressions can be written on a single line, but emphasizes that breaking code into multiple lines is often preferable for readability and maintainability in productio....

### Code Style and Readability

```vex
@Cd = (sin(length(@P) * ch('scale')) * 1) * 0.5;
```

Demonstrates that complex VEX expressions can be written as a single line, but emphasizes that code readability and maintainability in a studio environment is often more important than brevity.

### Code Readability Best Practices

```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

float d = length(@P) * ch('scale');
@Cd = (sin(d)+1)*0.5;

@Cd = (sin(length(@P) * ch('scale'))+1)*0.5;
// ...
```

Demonstrates that the same color calculation can be written in multiple ways, from multi-line with intermediate variables to a single compressed line.

### Code Readability and Variable Extraction

```vex
// Complex one-liner
@Cd = (sin(length(@P)*ch('scale'))%1)*0.5;

// Extracted to variable for clarity
float d = length(@P) * ch('scale');
@Cd = (sin(d)%1)*0.5;

// Using distance to fixed point
// ...
```

Demonstrates best practices for code readability by extracting complex expressions into intermediate variables.

### Distance-based color with parameters

```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

float d = length(@P) * ch('scale');
@Cd = (sin(d)+1)*0.5;

float d = distance(@P, {1,0,1});
// ...
```

Demonstrates progressive refinement of distance-based coloring using both length() and distance() functions.

### Distance with Channel-Referenced Center

```vex
vector center = chv('center');
float d = distance(@P, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```

This code refactors the distance-based color pattern to use a vector parameter for the center point, allowing dynamic control via a channel reference.

### Vector Channel Parameter for Center

```vex
float d = distance(@P, {3,0,3});
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

float d = distance(@P, {1,0,1});
d += ch('scale');
@Cd = (sin(d)+1)*0.5;

// ...
```

Demonstrates the progression from hardcoded center points to a parameterized vector channel.

### Non-uniform position scaling for distance patterns

```vex
vector center = chv('center');
vector pos = @P * {0.5, 1, 1};
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;
```

Demonstrates non-uniform scaling of position components by multiplying @P with a vector constant, allowing independent control over pattern stretching along different axes.

### Parameterized Position and Color

```vex
vector pos = @P * chv('fancy_scale');
vector center = chv('center');
vector d = normalize(pos - center);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;
```

Creates a parameterized color effect by scaling position with a vector channel reference, computing the normalized direction from a center point, and converting a sine wave distance calculation to ....

### Channel References for Interactive Control

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = length(pos, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```

Replaces hard-coded vectors with channel references using chv() and ch() functions to create interactive parameters.

### Channel Parameters for Scale Control

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```

Demonstrates using channel references (chv for vector, ch for float) to create UI parameters that control the scale transformation and center point of a distance-based color pattern.

### Channel Parameters for Interactive Pattern Control

```vex
vector pos = @P * chv('anyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;
```

Demonstrates adding channel parameter references to VEX code for interactive control of a radial ring pattern generator.

### Channel References for Radial Patterns

```vex
vector pos = @P + chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```

Demonstrates creating a controllable radial ring pattern by exposing multiple parameters through channel references.

### Radial Pattern with Channel References

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
f@distance = distance(pos, center);
@distance *= ch('scaling');
@Cd = (sin(@distance) + 1) * 0.5;
```

Demonstrates creating a controllable radial ring pattern by exposing channel parameters through chv() and ch() for scaling and center position.

### Vector Parameters for Position Scaling

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scaleD');
@Cd = (sin(d * s)) * 0.5;
```

Demonstrates using channel vector parameters (chv) to scale position and define a center point, then calculates distance-based color using sine waves.

### Vector vs Float Channel Parameters

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('_scale');
@Cd = sin(d) * 1 * 0.5;
```

Demonstrates the difference between using ch() for float parameters and chv() for vector parameters when creating UI controls.

### Changing Parameter Types and Spare Parameters

```vex
vector pos = @P + chv('fancyscale');
vector center = chv('center');
@Cd = length(pos, center);
@P *= chv('scale');
@Cd = (sin(@P))*0.5;
```

Demonstrates the use of channel reference functions (ch vs chv) for accessing parameters, and addresses the workflow for changing parameter types after they've been created.

### Channel Parameters and Type Conversion

```vex
vector pos = @P + chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= chf('scale');
@Cd = (sin(d)+1)*0.5;
```

Demonstrates how to use channel reference functions to expose parameters in the UI, including the importance of using the correct type (chv for vectors, chf for floats).

### Managing Spare Parameters in Wrangles

```vex
vector pos = @P * chv("anyscale");
vector center = chv("center");
float d = distance(pos, center);
d *= chf("scale");
@Cd = (sin(d)+1)*0.5;
```

Demonstrates techniques for managing spare parameters in VEX wrangles, including deleting and recreating all spare parameters or selectively removing and re-adding individual parameters.

### Managing Spare Parameters

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
f@dist = distance(pos, center);
@dist *= chv('scale');
@Cd = (sin(@dist)+1)*0.5;

vector pos = @P * chv('fancyscale');
vector center = chv('center');
// ...
```

Two variants of the same distance-based color calculation demonstrating spare parameter workflow.

### Spare Parameters and Type Casting

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
vector d = distance(pos, center);
d *= chv('scale');
@Cd = (sin(d)+1)*0.5;
```

Demonstrates creating channel reference spare parameters and handling implicit type casting issues.

### Distance-based sine pattern with parameters

```vex
vector pos = @P * chv("xyscale");
vector center = chv("center");
float d = distance(pos, center);
d *= chv("scale");
@Cd = (sin(d)*3)*0.5;
```

Creates a color pattern by calculating the distance from each point to a center position, then applies a sine wave pattern scaled by a parameter.

### Managing Spare Parameters and Type Casting

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= chf('scale');
@Cd = (sin(d) * 1) * 0.5;
```

Demonstrates creating a distance-based color pattern using channel references, with discussion of managing spare parameters by deleting and recreating them.

### Parameter Type Casting and Distance

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
vector delta = pos - center;
float d = length(delta);
d *= ch('scalePos');
@Cd = sin(d * 3) * 0.5;
```

Demonstrates computing distance from a point to a center using vector subtraction and length(), then using that distance to drive color with a sine wave.

### Distance and spare parameters

```vex
vector pos = @P + chv('fancyscale');
vector center = chv('center');
float dist = length(pos - center);
dist *= ch('scaleish');
@Cd = (sin(dist)) * 0.5;
```

Demonstrates calculating distance between modified point positions and a center point, then using that distance with sine function to create a color pattern.

### Parameter Type Management

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
vector delta = pos - center;
float dist = length(delta);
@Cd = sin(dist) + 0.5;
```

Demonstrates the importance of properly managing spare parameter types in VEX.

### Remapping sine waves with fit

```vex
// Version 1: Manual remapping
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

// Version 2: Using fit function
// ...
```

Demonstrates three approaches to remapping sine wave output from [-1,1] to [0,1] for color visualization: manual calculation (sin(d)+1)*0.5, using the fit() function for clarity, and animating the ....

### Animating patterns with fit and sine

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);
```

Uses fit() to remap sine wave values from their natural range (-1 to 1) into the 0-1 range needed for color attributes.

### fit() with built-in clamping

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);
```

Demonstrates how fit() automatically clamps output values to the specified range (0 to 1), ensuring values never exceed the target bounds even when the input (sin(d)) is pushed outside its normal r....

### Animating patterns with @Time

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d + @Time), -1, 1, 0, 1);
```

Animates a radial sine wave pattern by adding the built-in @Time attribute to the distance calculation.

### Animating with @Time

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d*@Time), -1, 1, 0, 1);
```

Demonstrates animating a color pattern over time by multiplying the distance-based sine wave by the @Time attribute.

### Time-Based Animated Color Pattern

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scalePD');
@Cd = fit(sin(d), -1, 1, 0, 1);
```

Creates an animated color pattern by calculating distance from a scaled position to a center point, multiplying by a time-varying channel parameter, and mapping the sine wave result to color values.

### Time-based Animation with @Time

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@N = ch('scale');
@Cd = fit(sin(d*@Time),-1,1,0,1);
```

Demonstrates using the @Time attribute to create time-varying effects by combining it with distance calculations and sine waves.

### Time-based animation with @Time

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d*@Time),-1,1,0,1);
```

Creates an animated color effect by calculating distance from a center point and using @Time to drive a sine wave pattern.

### Time-based color animation

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);
```

Creates an animated color effect using the @Time attribute combined with sine waves based on distance from a center point.

### Animated color with time and sine

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d*@time),-1,1,0,1);
```

Creates an animated color effect by multiplying position by a scale parameter, calculating distance from a center point, and using sine of distance multiplied by time to create oscillating colors.

### Time-varying patterns with @Time

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = fit(sin(d), -1, 1, 0, 1);

// Animated version:
vector pos = @P * chv('fancyscale');
vector center = chv('center');
// ...
```

Demonstrates how to create time-varying color patterns by multiplying distance calculations with the built-in @Time attribute.

### Time-based Animation Fix

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = fit(sin(d*@Time), -1, 1, 0, 1);

// Corrected version:
vector pos = @P * chv('fancyscale');
vector center = chv('center');
// ...
```

Demonstrates the difference between multiplying versus adding @Time to distance in a sine function for color animation.

### Compound assignment operators

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float delta = distance(pos, center);
@P *= ch('scaling');
@Cd = fit(sin(delta), -1, 1, 0, 1);
```

Demonstrates compound assignment operators in VEX, specifically the *= operator which multiplies and assigns in one step (cleaner than writing @P = @P * ch('scaling')).

### Multi-line Operations Clarity

```vex
float foo = 1;

// Single line version:
// foo = foo * 3 + 1 / @Cd.x + @N.y;

// Multi-line version for clarity:
foo *= 3;        // set range
foo += 1;        // make sure values never get below 0
// ...
```

Demonstrates how breaking complex mathematical operations across multiple lines with comments improves code readability.

### Code Review and Debugging Practices

```vex
float foo = 1;

vector pos = v@P - vector(centroid);
vector center = chv('center');
float r = distance(pos, center);
r *= ch('scale');
@Cd = fit(sin(r+chf('time')), -1, 1, 0, 3);
```

Discussion of debugging practices and troubleshooting VEX code when visual results don't match expectations.

### Debugging Visual Results in VEX

```vex
vector pos = @P * chv('anyscale');
vector center = chv('center');
vector d = normalize(pos - center);
d *= ch('scaleb');
@Cd = fit(sin(d.x), -1, 1, 0, 1);
```

This code demonstrates a complete example combining position transformation, distance calculation, and color animation.

### Distance-Based Color with Sine Wave

```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scalePos');
@Cd = fit(sin(d*chf('time')),-1,1,0,1);
```

Creates an animated color pattern by calculating the distance from each point to a center position, applying a sine wave modulated by time, and fitting the result to color values.

### Animated sine wave displacement

```vex
float d = length(@P);
d *= ch("x_scale");
d += @Time;
@P.y = sin(d);

@P += @N * ch("push");
```

Creates an animated sine wave displacement by calculating distance from origin, scaling it with a channel parameter, adding time for animation, then applying sine function to Y position.

### Animated wave displacement with channels

```vex
float d = length(@P);
d *= ch('v_scale');
d = @P.y * sin(d);

@P += @N * ch('push');
```

Creates animated wave displacement by computing distance from origin, scaling it via channel, then using sine function to generate wave pattern.

### Point Displacement with Channels

```vex
float d = length(@P);
d *= ch('v_scale');
d = @Time;
@P.y = sin(d);

@P += @N;

@P += @N * ch('push');
```

Demonstrates multiple techniques for displacing points including calculating distance from origin, using time-based sine wave deformation, and offsetting geometry along normals with channel-control....

### Distance-Based Displacement with Normals

```vex
float d = length(@P);
d *= ch('v_scale');
@P.y = sin(d);

@P += @N * ch('push');
```

This snippet calculates the distance from the origin to each point, scales it with a channel parameter, and uses that to create a sine wave displacement in the Y direction.

### Displacement with Normal Updates

```vex
float d = length(@P);
d *= ch("v_scale");
@P.y = sin(d);

@P += @N * ch('push');
```

Demonstrates how to displace geometry along normals while automatically updating the normal vectors.

### Surface Displacement with Normals

```vex
float d = length(@P);
d *= ch('v_scale');
d *= @Time;
@P.y = sin(d);

@P += @N * ch('push');
```

This demonstrates the difference between arbitrary displacement and normal-based displacement.

### Normal-based Surface Displacement

```vex
float d = length(@P);
d *= ch("v_scale");
d *= PI;
@P.y = sin(d);

@P += @N * ch("push");
```

Creates a sinusoidal displacement pattern based on distance from origin, then offsets geometry along surface normals.

### Animated Normal Displacement with Sine Wave

```vex
float d = length(@P);
d *= ch("_scale");
d += @Time;
@P += @N*sin(d) *ch('wave_height');
```

Creates an animated ripple effect by calculating distance from origin, scaling it, adding time-based animation, and displacing points along normals using a sine wave modulated by channel controls.

### Animated Wave Displacement

```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N * sin(d) * ch('wave_height');
```

Creates an animated wave displacement by calculating distance from origin, scaling it, adding time to create animation, then displacing points along their normals using a sine function.

### Animated Normal Displacement Wave

```vex
float d = length(@P);
d *= ch('v_scale');
d += @Frame;
@P += @N*sin(d)*ch('wave_height');
```

Creates an animated wave effect by displacing points along their normals using a sine function.

### Animated Sine Wave Displacement

```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N*sin(d) * ch('wave_height');
```

Creates an animated ripple effect by calculating distance from origin, scaling it with a channel parameter, adding time for animation, then displacing points along their normals using a sine wave m....

### Animated Wavelength Displacement

```vex
float d = length(@P);
d ^= ch('v_scale');
d += @Time;
@P += @N*sin(d);
```

Creates an animated displacement effect by calculating distance from origin, scaling it with a channel parameter, adding time for animation, and displacing points along normals using a sine wave.

### Animated Radial Wave Displacement

```vex
float d = length(@P);
d *= ch("v_scale");
d += @Frame;
@P.y = sin(d) * ch("wave_height");
```

Creates an animated radial wave pattern by calculating distance from origin, scaling it with a channel parameter, adding frame number for animation, and applying a sine function to displace points ....

### Animated Sine Wave Displacement

```vex
float d = length(@P);
d *= ch("v_scale");
d += @Time;
@P += @N*sin(d) * ch("wave_height");
```

Creates an animated wave displacement effect by calculating distance from origin, scaling and offsetting it by time, then displacing points along their normals using a sine function.

### Radial Wave Displacement

```vex
float d = length(@P);
d *= ch("v_scale");
d *= @Time;
@P.y = sin(d) * ch("wave_height");
```

Creates an animated radial wave effect by calculating distance from origin, scaling it by time and a user parameter, then using sine function to displace points vertically.

### Sine Wave Ripple Effect

```vex
float d = length(@P);
v@v = ch("_scale");
@P += @N * sin(d) * ch("wave_height");
```

Creates a ripple effect by calculating the distance from the origin to each point, then displacing points along their normals using a sine wave modulated by distance and controlled by channel param....

### Distance-based ripple waves

```vex
float d = length(@P);
v@v = @N * -d;
f@cd = ch("wave_height");
@P += @N * sin(d) * ch("wave_height");
```

Creates a ripple wave effect by calculating the distance from the origin using length() and offsetting points along their normals based on a sine function.

### Length and Clamp Functions

```vex
float d = length(@P);
v@z = ch("_scale");
@P += @N * sin(d) * ch("wave_height");
```

Demonstrates using the length() function to calculate distance from origin, combined with clamp() for value constraining and sin() for wave deformation.

### Distance-based height mapping with clamp

```vex
float d = length(@P);
@P.y = clamp(d, 0, 5);
```

Calculates the distance from the origin for each point and uses it to set the Y position, with clamp limiting the maximum height to 5 units.

### Distance-based height manipulation with clamp

```vex
float d = length(@P);
@P.y = clamp(d, 0, 1);
```

Demonstrates various mathematical operations on point height based on distance from origin using the length() function.

### Distance normalization and clamping

```vex
float d = length(@P);
@P.y = d*d + 1 * 10;
d = asin(clamp(d, 0, 1));
```

This code calculates the distance from the origin using length(), applies a squared transformation to the Y position, then uses asin() with a clamped distance value to ensure input values stay with....

### fit and clamp together

```vex
float d = length(@P);
float imin = ch("fit_in_min");
float imax = ch("fit_in_max");
float outMin = ch("fit_out_min");
float outMax = ch("fit_out_max");
d = fit(d, imin, imax, outMin, outMax);
@P.y = d;
```

Demonstrates using fit() and clamp() functions together to remap and constrain distance values.

### Distance to Ramp Mapping

```vex
float d = length(@P);
d = d * (v@scale);
@P.y = chramp('myramp', d);
```

Uses the length() function to calculate distance from origin, scales it by a vector parameter, then uses chramp() to map the scaled distance value through a ramp parameter to control the Y position....

### Using ramps with distance

```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
```

This code calculates the distance from the origin to each point, scales it using a channel parameter, and then uses that scaled distance to drive the Y position via a ramp parameter.

### Using chramp for Y displacement

```vex
float d = length(@P);
d *= ch("scale");
@P.y = chramp("myramp", d);
```

Calculates the distance from origin for each point, scales it with a channel parameter, then uses a ramp parameter to look up a value that displaces the Y position.

### Animating Ramp with Time

```vex
float height = length(@P);
float d = ch('scale');
d *= @Time;
@P.y = chramp('myramp', d);
```

This code animates point positions using a ramp parameter that evolves over time.

### Ramp-Driven Height Displacement

```vex
float d = length(@P);
d *= ch('scale');
d = chramp('myramp', d);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Creates height displacement by calculating distance from origin, scaling it with a channel parameter, and using a ramp to modulate the Y position.

### Ramp-Driven Height Displacement

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Creates a wave-like displacement on the Y axis by calculating distance from origin, scaling and applying sine function, then using the result to sample a ramp that controls height.

### Ramp-Driven Height Displacement

```vex
float d = length(@P);
d *= ch('scale');
d -= ch('time');
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

This code uses the distance from origin to drive a ramp lookup, creating animated height displacement on geometry.

### Animated Sine Wave Displacement

```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
@P.y += sin(d * ch("wave_scale") * d);
@Cd.y *= ch("height");
```

Creates an animated wave effect by calculating distance from origin, modulating it with time, and applying a sine wave displacement to point positions.

### Animated Ramp Displacement with Height

```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
@P.y = chramp("myramp", d);
@P.y *= ch("Height");
```

Creates an animated vertical displacement by calculating distance from origin, scaling and offsetting by time, then sampling a ramp parameter to drive Y position.

### Distance-based height displacement with ramp

```vex
float d = length(@P);
d *= ch("scale");
d -= ch("bias");
@P.y = chramp("myramp", d);
@P.y *= ch("height");
```

Calculates the distance from origin for each point, scales and offsets it using channel parameters, then uses that distance to sample a ramp and set the Y position.

### Chramp Modulo Behavior Change

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Uses chramp() to sample a ramp parameter based on distance from origin plus time, then applies that value to the Y position with a height multiplier.

### Ramp-based height displacement

```vex
float d = length(@P);
d *= ch("scale");
d = abs(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```

This code creates a radial displacement pattern by calculating distance from origin, applying trigonometric transformation, and using a ramp parameter to control the vertical displacement of points.

### Ramp Modulo Behavior Change

```vex
float d = length(@P);
d = fit(d, scale);
d = sin(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp("my_ramp", d);
@Cd *= ch("height");
```

This code creates a color pattern by computing distance from origin, applying sine waves, and sampling a color ramp.

### Color Ramp with Frame Animation

```vex
float d = length(@P);
d *= ch('scale');
d = @Frame;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp('myRamp', d);
@Cd *= ch('height');
```

This example demonstrates animating color using frame number and a color ramp parameter.

### Ramp Modulo Behavior Change

```vex
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
@P.y = fit01(d, -0.1, 0.1);
@Cd.y = chramp("myRamp", d);
@Cd.y *= ch("height");
```

Creates animated wave displacement using distance from origin, sine function, and time.

### Ramp-driven height with distance fitting

```vex
float d = length(@P);
d *= ch('scale');
d = fit(d, 1, 1, 0, 1);
@P.y = chramp('myRamp', d);
@P.y *= ch('height');
```

Calculates distance from origin, scales and remaps it using fit(), then uses the remapped value to sample a ramp parameter that drives vertical displacement.

### Modulo for Cyclic Ramp Mapping

```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
@P.y *= chramp('myramp', d);
@P.y *= ch('height');
```

Uses the modulo operator to create cyclic patterns by constraining a distance-based value to the 0-1 range, which is then used to sample a ramp parameter for controlling point height.

### Animated Radial Ramp Displacement

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my_ramp', d);
@P.y *= ch('height');
```

Creates an animated radial displacement pattern by calculating distance from origin, scaling and offsetting it by time, then using that value to sample a ramp parameter which drives Y-position disp....

### Animated Ripple with Nested Trigonometry

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = sin(d/cos(d/cos(d)));
@Cd = ch('height');
```

Creates an animated ripple effect using nested trigonometric functions where distance from origin is scaled, time-shifted, and passed through nested sine and cosine operations.

### Radial Ramp Displacement

```vex
float d = length(@P);
d *= ch("scale");
d = qs(d);
d *= $PI;
@P.y = chramp("myamp", d);
@P.y *= ch("height");
```

Creates a radial displacement pattern by calculating distance from origin, scaling and wrapping it with qs() function, then using that as input to a ramp parameter to drive vertical position.

### Animated Sine Wave Displacement

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = .1*sin(d);
@v.y = sin(length(@P));
```

Creates an animated sine wave displacement by calculating distance from origin, applying a channel-based scale, offsetting by time, and using the result to drive vertical position with sine.

### Animated Sine Wave Displacement

```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
@P.y = ch("amp") * sin(d);
@v.y = chf("dist");
```

Creates an animated sine wave displacement by calculating distance from origin, scaling it with a channel parameter, subtracting time for animation, and applying a sine function to the Y position.

### Animated Wave Displacement with Time

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y += sin(d * ch('freq'));
@P.y *= ch('height');
```

Creates an animated radial wave pattern by calculating distance from origin, subtracting time for animation, then applying a sine wave to the Y position.

### Animated Ramp-Driven Wave Patterns

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-map', d);
@P.y *= ch('height');
```

Creates animated wave patterns by calculating distance from origin, scaling and offsetting by time, then using a ramp parameter to control vertical displacement.

### Ramp-based Height Displacement

```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```

This code creates a radial sine wave pattern and uses a ramp parameter to control vertical displacement.

### Distance-based Height with ID Offset

```vex
float d = length(@P);
d *= ch('scale');
d += @id;
d += sin(d);
d *= ch('height');
@P.y = d;
```

Calculates a distance value from the origin using point position length, scales it with a channel parameter, offsets by point ID, applies a sine wave modulation, and uses the result to drive the Y ....

### Color Ramping with Distance

```vex
float d = length(@P);
d *= ch('scale');
d += @id;
d *= sin(chf('height'));
d = clamp(d, 0, 1);
@Cd = chramp('myrramp', d);
@P.y *= ch('height');
```

Creates a color gradient based on distance from origin, modified by point ID and sine wave modulation.

### Color mapping with distance and channels

```vex
float d = length(@P);
d *= ch('scale');
d += @id;
d += s;
@Cd.y = chramp('mymap', d);
@Cd.g = ch('height');
```

This code calculates a distance value from the origin using point position, then modulates it with channel parameters, point ID, and a variable 's'.

### Ramp-based Height Displacement

```vex
float d = length(@P);
d *= ch("scale");
d += ch("offset");
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Creates a radial wave pattern by computing distance from origin, applying sine wave, then using a ramp to control vertical displacement.

### Ramp-driven displacement with fit

```vex
float d = length(@P);
d *= ch("scale");
d += 0;
d *= sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```

Creates a radial displacement pattern by calculating distance from origin, applying sine wave modulation, fitting the result to 0-1 range, and using it to sample a ramp parameter for vertical displ....

### Sine Wave Animation with Color Ramp

```vex
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
d = (d+1)*0.5;
@Cd = chramp("myRamp",d);
@P.y += ch("height");
```

Creates an animated sine wave deformation based on distance from origin, then remaps the sine values from [-1,1] to [0,1] range to drive a color ramp.

### Ramp-driven height displacement

```vex
float d = length(@P);
d *= ch("scale");
d *= @Time;
d = sin(d);

@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```

This creates animated vertical displacement using a color ramp for control.

### Shaping Sine Waves with Ramps

```vex
float d = length(@P);
d *= ch("scale");
d = @Time;
d = sin(d);
@Cd = set(d, d, d);
@Cd.y = chramp("myRamp", d);
@Cd.y *= ch("height");
```

This example demonstrates using a ramp parameter to shape and clip sine wave patterns applied to point colors.

### Animated Wave with Ramp Control

```vex
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
@Cd = set(d, d, d);
@P.y = chramp("myRamp", d);
@P.y *= ch("height");
```

Creates an animated sine wave displacement based on distance from origin, using time to animate the pattern.

### Combining Distance Fields with Ramps

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myamp', d);
@P.y *= ch('height');
```

Creates a radial wave pattern by calculating distance from origin, applying sine wave modulation, and using a ramp parameter to control the vertical displacement shape.

### Sine Wave with Ramp and Fit

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myRamp', d);
@Cd = ch('height');
```

Creates an animated sine wave pattern by calculating distance from origin, applying time offset, and using the result to drive both vertical position via a ramp lookup and color.

### Normalized Values and Fit Function

```vex
s@greeting = "yessirree";
i@test = 123;
f@scale = ch("scale");
v@P = @P * @test;
f@cd = @P.y;
v@Cd = fit(@P.y, 0, 1, 1, 0);
i@x = 1;
@P.y = chramp("coramp", @P.z);
// ...
```

Demonstrates the use of the fit() function to normalize and remap values between different ranges.

### Fit and Ramp Displacement

```vex
float d = length(@P);
d *= ch('scale');
d += 1;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

This code creates vertical displacement by computing distance from origin, applying sine wave modulation, and using fit() to normalize the sine output from [-1,1] to [0,1].

### Per-Primitive Ramp Offset

```vex
float d = length(@P);
d *= ch('scale');
d -= prim;
d %= 1;
@Cd.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Creates a radial distance-based pattern using a ramp lookup, with per-primitive offset to create repeating concentric patterns.

### Radial Wave Deformation with Ramp

```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
d = chramp('my-ramp', d);
@P.y *= d;
@P.y *= ch('height');
```

Creates a radial wave pattern by calculating distance from origin, applying modulo for repetition, using sine for wave shape, and mapping through a ramp parameter for artistic control.

### Distance-Based Deformation with Ramps

```vex
float d = length(@P);
d *= ch('scale');
d *= sin(d);
d *= fit(d, -1, 1, 0, 1);
d = chramp('my-ramp', d);
@P.y *= ch('height');
```

This code calculates distance from origin using length(@P), applies sinusoidal waves, normalizes the result with fit(), and uses a color ramp to control vertical displacement.

### Animated Radial Color Ramp

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@Cd.y = chramp('myRamp', d);
```

Creates an animated radial color pattern by calculating distance from origin, scaling it, subtracting time for animation, using modulo to create repeating bands, and mapping the result through a ra....

### Sine Wave Ripple with Color Ramp

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = sin(d);
d *= fit(d, -1, 1, 0, 1);
@Cd = chramp('my_ramp', d);
@P.y *= ch('height');
```

Creates a radial sine wave pattern from the origin using point distance, applies double sine for more complex oscillation, remaps the result to 0-1 range, and colors points using a ramp while scali....

### Radial Sine Wave Color and Height

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d,-1,1,0,1);
@Cd = set(d,d,d);
@P.y *= ch('height');
```

Creates a radial sine wave pattern by calculating distance from origin, applying sine function, then remapping the result to a 0-1 range for grayscale color assignment.

### Distance-based height displacement with ramps

```vex
float d = length(@P);
v@Cd = ch('color');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
d = chramp('height', d);
@P.y *= ch('height');
```

This example calculates the distance from the origin, applies a sine wave, normalizes it to 0-1 range, then uses a ramp parameter to control a vertical displacement multiplier.

### Modulo for Looping Values

```vex
@Cd.r = @Time % 1;

@P.y = @ptnum % 5;

float d = length(@P);
d *= ch('scale');
@P.y = d;
```

Demonstrates using the modulo operator (%) to create looping values over time and across geometry.

### Stepped Radial Height Mapping

```vex
float d = length(@P);
v@Cd = set(1);
d *= chf("scale");
d = trunc(d);
@P.y = d;
```

Creates a stepped cylindrical height effect by calculating the distance from the origin, scaling it with a channel parameter, truncating to integer steps, and applying the result to the Y position.

### Ramp-Based Height Displacement

```vex
float d = length(@P);
d *= ch("pre_scale");
d = chramp("ramp", d);
d *= ch("post_scale");
@P.y = d;
```

This technique calculates radial distance from the origin, scales it using pre and post scale parameters, and remaps the value through a ramp parameter to create height displacement.

### Stepped Ramp Height Mapping

```vex
float d = length(@P);
d = fit(d, 0, 1, 0, 1);
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

Calculates the distance of each point from the origin, evaluates a stepped color ramp parameter to create discrete height levels, then applies a post-scale multiplier.

### Stepped Ramp Evaluation

```vex
float d = length(@P);
d *= 10;
d = chramp("my_stepped_ramp", d);
d *= ch("post_scale");
@P.y = d;
```

This code demonstrates using a stepped ramp parameter to control point displacement.

### Stepped Ramp with UI Controls

```vex
float d = length(@P);
d = fit01(d, 0, 1);
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

This code displaces point heights based on distance from origin using a custom stepped ramp parameter.

### Distance-based Y displacement with channel scaling

```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d *= f;
d = fit(d, 0, 1, 0, 1);
@P.y = d;
```

Calculates the distance from origin using length(@P), scales it by two channel parameters 'scale' and 'factor', then remaps the distance value with fit() and applies it to the Y position.

### Color from Distance with Sine

```vex
float d = length(@P);
@Cd = chv('scale');
d *= 4;
@Cd.r = sin(d);
```

Calculates distance from origin using point position, retrieves a color parameter from a channel, scales the distance by 4, then applies a sine wave to modulate the red channel.

### Distance-based color with sine wave

```vex
float d = length(@P);
d *= ch('scale');
@Cd.r = sin(d);
@Cd.y = sin(d);
```

This example calculates the distance from the origin using length(@P), scales it with a channel parameter, and applies a sine function to create oscillating color values in the red and green channels.

### Sine Function on Distance for Color

```vex
float d = length(@P);
d *= ch('scale');
@Cd = 0;
@Cd.r = sin(d);
```

This example calculates the distance from the origin using length(@P), multiplies it by a channel parameter for scale, then uses the sine function to create an oscillating red color value based on ....

### Distance-Based Sine Wave Color

```vex
float d = length(@P);
d = ch('scale')*d;
@Cd = @P;
@Cd.r = sin(d);
```

Creates a radial color pattern by calculating distance from origin and applying a sine wave to the red channel.

### Distance-Based Displacement

```vex
float d = length(@P);
d *= ch('scale');
@Cd = d;
@P.y = sin(d);
```

Calculates the distance of each point from the origin using length(@P), scales it with a channel parameter, assigns the distance to color, and displaces points vertically using a sine wave based on....

### Distance-based color animation

```vex
float d = length(@P);
d += ch('scale');
@Cd.y = sin(d);
```

Creates a wave pattern in the green color channel by calculating the distance from the origin, adding a user parameter for scale control, and applying a sine function to the result.

### Creating Custom Variables and Attributes

```vex
float d = length(@P);
@mydistance = d;
@Cd.r = sin(d);

// You can also use channel references
float scale = ch("scale");
@Cd.r = sin(@mydistance * scale);
```

This demonstrates creating custom variables in VEX to store intermediate calculations and output them as geometry attributes.

### Creating Custom Attributes with Variables

```vex
f@d = length(@P);
f@d /= ch("scale");
@Cd = @d;
@Cd.r = sin(@d);
```

Demonstrates creating a custom float attribute 'd' to store calculated distance values, which can then be used in subsequent operations and viewed in the geometry spreadsheet.

### Distance-Based Color with Sine Wave

```vex
vector pos = minpos(0, @P);
float d = distance(@P, pos);
d *= ch('scale');
@Cd = d;
@Cd.r = sin(d);
```

This code finds the closest point in the geometry using minpos, calculates the distance to it, and applies a sine wave modulation to the red channel of the color attribute.

### Sine wave coloring from distance

```vex
vector pos = minpos(1, @P);
float d = distance(pos, @P);
d *= ch('scale');
@Cd = 0;
@Cd.r = sin(d);
```

This code finds the nearest point on the second input geometry, calculates the scaled distance to it, and uses a sine wave of that distance to drive the red color channel.

### Distance to Point with Fit

```vex
vector pos = v@pos[0];
float d = distance(pos, @P);
d *= ch('scale');
f@Cd = fit(d, 0, 1, 0, 1);
```

Reads a position vector from the first input's point 0, calculates the distance from each point to that position, scales it by a channel parameter, and uses fit() to remap the distance values into ....

### Animated Curl Noise Color

```vex
@Cd = curlnoise(@P * chv('fancyscale') + @Time);
```

Uses curl noise to generate animated color values based on point positions and time.

### Dot Product Basics

```vex
@Cd = @N.y;

@Cd = -@N.y;

@Cd = dot(@N, {0,1,0});

@Cd = dot(@N, chv('angle'));
```

Introduction to the dot product as a way of multiplying vectors to get scalar results.

### Dot Product for Directional Shading

```vex
@Cd = -@N.z;

@Cd = -@N.y;

@Cd = dot(@N, {0,1,0});

@Cd = dot(@N, chv('angle'));
```

The dot product compares the direction of two vectors, returning 1 when they point in the same direction, 0 when perpendicular, and -1 when opposite.

### Dot Product for Surface Orientation

```vex
@Cd = dot(@N, chv('angle'));
```

Uses the dot product to compare the surface normal (@N) against a user-defined direction vector from a channel reference.

### Dot Product with Point Position

```vex
@Cd = dot(@N, chv('angle'));

vector pos = point(1, 'P', 0);
@Cd = dot(@N, pos);

vector pos = point(1, 'P', 0);
pos = normalize(pos);
@Cd = dot(@N, pos);
```

Demonstrates using the dot product between surface normals and a direction vector, evolving from a parameter-driven angle to a point position lookup.

### Reading Point Position from Second Input

```vex
vector pos = point(1, "P", 0);
@Cd = dot(@N, chv("angle"));
```

Uses the point() function to read the position attribute from the first point (index 0) of the second input (input 1), storing it in a vector variable.

### Normalizing vectors for dot product

```vex
vector pos = point(1, "P", 0);
@Cd = dot(@N, pos);

pos = normalize(pos);
@Cd = dot(@N, pos);
```

Demonstrates the importance of normalizing vectors before using them in dot product calculations.

### Normalizing Vectors for Dot Product

```vex
vector pos = point(1, 'P', 0);
pos = normalize(pos);
@Cd = dot(@N, pos);
```

Demonstrates normalizing a vector before using it in a dot product calculation to prevent overly bright values.

### Cross Product for Normal Manipulation

```vex
@N = cross(@N, {0,1,0});

vector tmp = cross(@N, {0,1,0});
@N = normalize(tmp);
```

Demonstrates using the cross product to rotate normals by crossing them with the Y-axis vector.

### Multiple Cross Products and Cycles

```vex
vector tmp = cross(@P, {0,1,0});
@N = cross(@N, tmp);

vector tmp = cross(@P, {0,1,0});
@N = cross(@N, tmp);

vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
// ...
```

Demonstrates that repeatedly applying cross products creates a cycle that eventually returns to the starting orientation.

### Point Cloud Length Query

```vex
@pt = @ptnum % length(1, "/pack");
```

Uses the length() function to query the number of primitives in a packed geometry path, then uses modulo operator to cycle point numbers through available packed primitives.

### Relative BBox Deformation with Ramps

```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float k = chramp('inflate', bbox.y);
// ...
```

Uses relpointbbox to get normalized bounding box coordinates (0-1 range) for each point, then demonstrates progressive complexity: first visualizing the Y component as color, then scaling point pos....

### Ramp-Driven Inflation Using Bounding Box

```vex
vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```

Uses a ramp parameter to control point displacement along the normal based on vertical bounding box position.

### Ramp-driven displacement using bounding box

```vex
vector bbox = relpointbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```

Uses a ramp parameter to control displacement magnitude based on the normalized Y position within the bounding box.

### Ramp-driven Geometry Inflation

```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox;

vector bbox = relpointbbox(0, @P);
@Cd = @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
// ...
```

Demonstrates using a ramp parameter to control geometry inflation based on normalized bounding box position.

### Ramp-Driven Inflation Effect

```vex
vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
// ...
```

Uses relpointbbox() to get normalized bounding box coordinates (0-1) and drives displacement along normals with a ramp parameter.

### Relative Bounding Box Scaling

```vex
vector bbox = relpointbbox(0,@P);
float t = chramp('inflate',bbox.y);
@P += @N * t * ch('scale');
```

Uses relpointbbox() to get normalized bounding box coordinates (0-1 range) and drives position displacement via a ramp parameter, allowing the same effect to work consistently across different geom....

### Threshold-based normal masking

```vex
float d = dot(@N, {0,1,0});
@Cd = {0,0,1};
if(d > ch('cutoff')){
    @Cd = {1,1,1};
}
```

Uses a dot product between the point normal and up vector to determine surface orientation, then colors points white if they face upward beyond a threshold value controlled by a channel parameter.

### Conditional Color Assignment with Dot Product

```vex
float d = dot(@P, {0,1,0});
@Cd = {0,0,1};
if (d > ch('cutoff')) {
    @Cd = {1,1,1};
} else {
    @Cd = {1,0,0};
}
```

Uses dot product to classify points based on their Y-position, then explicitly sets color to white if above the cutoff threshold or red if below.

### Conditional color assignment with if-else

```vex
float d = dot(@P, {0,1,0});
if(d < ch('cutoff')){
    @Cd = {1,1,1};
} else {
    @Cd = {1,0,0};
}
```

Uses an if-else statement to explicitly assign white color when dot product is below cutoff, red otherwise.

### Floating Point Precision Errors

```vex
float foo = 0;
float bar = sin(PI);

if(foo == bar) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```

Demonstrates floating point precision errors where sin(PI) returns a value extremely close to zero (approximately -8.74228e-8) but not exactly zero, causing the equality comparison to fail.

### Floating Point Comparison Issues

```vex
float foo = 0;
float bar = sin(@P.y);

if(foo == bar) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```

Demonstrates a common floating point precision error where sin(@P.y) produces values extremely close to zero (like 0.00000087) but not exactly zero, causing equality comparisons to fail.

### Float comparison tolerance

```vex
float foo = 0;
float bar = sin(@P[1]);

if(foo - bar < 0.00001) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```

Demonstrates safe float comparison by using a tolerance threshold instead of testing for exact equality.

### Epsilon Test for Float Comparison

```vex
float foo = 1.25;
float bar = -1.25;

if(abs(foo - bar) < 0.00001) {
    @Cd = {1,1,0};
}
else {
    @Cd = {1,0,0};
// ...
```

Demonstrates an epsilon test for comparing floating-point numbers, which checks if the absolute difference between two values is below a small threshold (0.00001) rather than testing exact equality.

### Epsilon Comparison for Floating Point

```vex
float foo = 1.25;
float bar = 1.25;

if(abs(foo - bar) < 0.00001) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```

Demonstrates epsilon testing for comparing floating-point numbers by checking if their absolute difference is less than a small threshold (0.00001) rather than testing exact equality.

### Conditional Color Based on Comparisons

```vex
float a = length(v@P) * 2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (a > b){
    @Cd = {1,0,0};
}
```

This exercise demonstrates conditional coloring using if statements.

### Conditional color based on math expression

```vex
vector @P;
float a = length(@P) * 2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (a > b){
    @Cd = {1,0,0};
}
```

Compares two mathematical expressions to conditionally set point color to red.

### Vector and Array Indexing

```vex
vector myvector = {1,2,3};

v@a = {10,12,100};

float foo = @a.x; // will return 10

float foo = @a[2]; // that's asking for index 2, which will return 100

// ...
```

Demonstrates two methods for accessing vector components: dot notation (.x, .y, .z) and array-style indexing ([0], [1], [2]).

### Declaring Array Attributes

```vex
float myFloatArray[] = {1,2,3,4,5};
vector myVectorArray[] = {{1,2,3},{4,5,6},{7,8,9}};

f[]@a = {1,2,3,4,5};
v[]@vecs = {{1,2,3},{4,5,6},{7,8,9}};
```

Demonstrates two ways to declare array attributes in VEX: using local variables (float[], vector[]) and using geometry attributes (f[]@, v[]@).

### Nearest Point Color Transfer with Falloff

```vex
int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
vector col = point(1, "Cd", pt);
float d = distance(@P, pos);
d = fit(d, 0, ch("radius"), 1, 0);
d = clamp(d, 0, 1);
@Cd = col * d;
```

Finds the nearest point from the second input, retrieves its position and color, then applies that color to the current point with a distance-based falloff.

### Nearest Points Array Assignment

```vex
v@p = v@opinput1_P(0, v@P, 0);
int pts[];
int pt;
vector pos;
vector col;
float d;

// first point
// ...
```

Demonstrates storing nearpoints results in an array and accessing individual elements by index to read their attributes.

### Frequency Control with Geometry Resolution

```vex
v = fit(0, 0, ch("radius"), 1, 10);
@P.y = sin(length(@P) * v);
```

Demonstrates using fit() to map a channel slider to a frequency multiplier for a sine wave deformation.

### Multi-Point Distance Blending

```vex
v@P = set(i@ptnum, 0, 0);
pos = point(1, "P", i@ptnum);
d = distance(@P, pos);
freq = ch("freq");
w = d * cos(freq);
w = sin(w);
amp = ch("amp") * ch("speed");
w *= amp;
// ...
```

Demonstrates blending multiple distance-based wave influences by computing wave effects from multiple source points and accumulating them.

### Creating Lines from Points Using Normals

```vex
int pt = addpoint(0, {0,3,0});
addprim(0, "polyline", @ptnum, pt);

int pt = addpoint(0, @P + @N);
addprim(0, "polyline", @ptnum, pt);

vector pos = @N * noise(@P * @time) * {1, 0.1, 1};
int pt = addpoint(0, @P + pos);
```

Demonstrates creating polyline primitives from each point by adding a new point offset from the current position.

### Setting scale with channel reference

```vex
@scale = ch("pscale");
```

Sets the scale attribute for copied instances by referencing a parameter slider named 'pscale' using the ch() function.

### Setting pscale from channel parameter

```vex
@pscale = ch("pscale");

float u, t;
t = fit01(@P.x * ch("speed"), 0, 1);
d = length(@P);
```

Introduces the @pscale attribute for controlling instance size in the Copy to Points SOP.

### Setting pscale with channel reference

```vex
@pscale = ch('pscale');

float d, i;
i = @Time * ch('speed');
d = length(@P);
```

Demonstrates setting the pscale attribute using a channel reference for easy parameter control.

### P-scale attribute basics

```vex
@pscale = ch('pscale');

float d, i;
i = fit01(@P.y, 0, 1);
d = length(@P);
```

Demonstrates setting up the @pscale attribute using a channel reference for interactive control.

### Setting pscale attribute with channel

```vex
@pscale = ch("pscale");

float d, t;
t = fit01(chf("speed"), 0, 1);
d = length(@P);
```

Demonstrates creating a pscale attribute controlled by a channel parameter, allowing uniform scaling of points via a UI slider.

### Setting pscale with channel reference

```vex
@pscale = ch('pscale');

float d, t;
f@len = ch('speed');
d = length(@P);
```

Creates a pscale attribute controlled by a channel parameter, allowing interactive manipulation of point scale values.

### Animated point scaling with sine wave

```vex
float d, t;
t = @Time * chf('speed');
d = length(@P);
t += d * ch('frequency');
d = fit(sin(t), -1, 1, ch('min'), ch('max'));
@pscale = d;
```

Creates animated point scaling by combining time-based animation with distance from origin.

### Animated sine wave displacement

```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= d * ch('frequency');
d += t;
d = sin(d);
@P.y += d;
```

Creates an animated radial sine wave effect by calculating distance from origin, scaling it by frequency, adding time-based animation, and applying sine function to displace points vertically.

### Animated Sine Wave Point Scale

```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= d * ch('frequency');
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;
```

Creates an animated radial sine wave effect by combining distance-from-origin with time, then applying sine function and remapping to control point scale.

### Sine Wave Point Scale Animation

```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;
```

Creates an animated pulsing effect by combining point distance from origin with time, passing through sine function, and remapping the result to control point scale.

### Animated sine wave scaling

```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
@Cd = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;
```

Creates time-animated sine wave patterns by calculating distance from origin, modulating it with time and frequency parameters, then mapping the sine wave to both color (via fit) and point scale.

### Animated pscale with distance

```vex
@pscale = ch("pscale");

float d, t;
t = @Time * ch('speed');
d = length(@P);
d = ch('frequency') * d + t;
@pscale = d;
```

Creates an animated point scale based on distance from origin and time.

### Animated pscale with UI controls

```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;

// ...
```

Demonstrates animating point scale using time-based sine waves controlled by channel references for speed and frequency parameters, then shows alternative approaches using the @pscale attribute wit....

### pscale vs scale attributes

```vex
@pscale = ch('pscale');

float d, i;
i = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += i;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// ...
```

Demonstrates creating animated @pscale using sine waves driven by time and distance from origin, then introduces @scale as a vector attribute that provides independent control over scaling on all t....

### Set Function for Vector Construction

```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
@P = fit(sin(d), -1, 1, ch('min'), ch('max'));
@scale = d;

// ...
```

Demonstrates the proper way to construct a vector using the set() function instead of brace notation when incorporating math operations or variable assignments.

### Vector Scale Using Set Function

```vex
float d, t;
s = @Time * ch('speed');
s = length(@P);
s = ch('frequency');
d = t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@scale = d;

// ...
```

Demonstrates transitioning from pscale to vector @scale attribute using the set() function.

### Setting Scale with Vectors

```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d *= ch('frequency');
// d += t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;

// ...
```

Demonstrates transitioning from uniform @Pscale to non-uniform @scale attribute using vector values.

### Non-uniform Scale with Vector

```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d = ch('frequency');
// d = t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @Cd.r = d;

// ...
```

Demonstrates setting the @scale attribute using vector literal syntax with curly braces to apply non-uniform scaling to geometry.

### Vector initialization and scale attribute

```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d = ch('frequency');
// d = t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;
@scale = {1, 5, 2.2};
// ...
```

Demonstrates multiple methods of initializing vector values for the @scale attribute, comparing curly brace literal syntax (which doesn't work with variables) versus the set() function (which prope....

### Non-uniform Scale Vector Assignment

```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d *= ch('frequency');
// d -= t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;
@scale = {1, 5, 2.2};
// ...
```

Demonstrates direct vector initialization using curly braces to set non-uniform scale values per axis.

### Non-Uniform Scale with Vectors

```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d = ch('frequency');
// d = t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;
@scale = (1, 5, 2.2);
// ...
```

Demonstrates setting non-uniform scale on points by assigning a vector to @scale.

### Vector Assignment Syntax

```vex
// Direct vector literal assignment
@scale = {1, 5, 2.2};

// Component-wise assignment
@scale.x = 1;
@scale.y = d;
@scale.z = @Cd.g;

// ...
```

Demonstrates three methods for assigning vector values: direct literal assignment with curly braces, component-wise assignment using dot notation, and the set() function which is the preferred meth....

### Non-uniform scaling with vector components

```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d *= ch('frequency');
// d += t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;

// ...
```

Demonstrates two methods for creating non-uniform scaling: directly setting individual vector components of @scale (x, y, z separately), or using the set() function to construct a vector with diffe....

### Setting Individual Vector Components

```vex
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d *= ch('frequency');
// d -= t;
// d = cos(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;

// ...
```

Demonstrates how to set individual components of a vector attribute using dot notation.

### Vector Component Assignment with set()

```vex
// Commented out previous work:
// float d, t;
// t = @Time * ch('speed');
// d = length(@P);
// d = ch('frequency');
// d = t;
// d = fit(sin(d), -1, 1, ch('min'), ch('max'));
// @scale = d;
// ...
```

Demonstrates the limitation of curly bracket syntax for vector construction when using variables or attributes, showing that you cannot use {1, d, @Cd.g} with dynamic values.

### Animated Scale from Distance

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
```

Creates an animated scale attribute based on distance from origin.

### Vector Component Swapping for Scale

```vex
float min, max, d, f;
min = ch('min');
max = ch('max');
f = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Demonstrates swapping vector components in the scale attribute to control which axis receives the animated scaling effect.

### Non-uniform scaling with fit and set

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

Creates non-uniform scaling animation using distance from origin combined with time.

### Animated scale from distance

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

Creates animated non-uniform scale based on distance from origin, using sine wave with time offset and frequency control.

### Animated scale based on distance

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

Creates animated scaling effect by calculating distance from origin, applying frequency multiplier and time offset, then using sine wave fitted to min/max range to drive Z-axis scale.

### Animating scale with sine waves

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d = d * ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Creates animated scaling by combining point distance from origin with time, modulating through a sine wave and fitting to min/max range.

### Animated Scale with Radial Wave

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

Creates an animated radial wave effect by calculating distance from origin, modulating it with time-based sine wave, and applying the result to point scale and color.

### Animating Scale with Sine Wave

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @ptnum * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Creates animated scale variation across points by combining distance from origin with point number, then applying a sine wave modulated by frequency and speed parameters.

### Non-uniform scaling for copy-to-points

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = fit(rand(@ptnum), 0, 1, min, max);
d = length(@P);
d *= chf('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Creates non-uniform scaling for copied geometry by combining distance-based sine wave patterns with random variation.

### Animated Scale with Distance

```vex
float min = ch('min');
float max = ch('max');
float t = fit(@Time * ch('speed'), 0, 1, 0, 1);
float d = length(v@P);
float s = ch('frequency');
d = d * s;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
// ...
```

Creates animated scale variation based on point distance from origin using sine wave.

### Wave-based scaling and color with position

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Frame * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
t = fit(sin(d), -1, 1, min, max);
// ...
```

Creates animated wave-based scaling and coloring of geometry using sine waves modulated by distance from origin.

### Animated Scale and Color with Packing

```vex
float min, max, d, t;
min = 0;
max = ch("max");
t = fit(v@P.x, ch("speed"));
d = length(@P);
d *= ch("frequency");
d += t;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Creates animated wave pattern by computing distance from origin, modulating it with sine wave based on frequency and speed parameters, then applying results to non-uniform scale attribute and verti....

### Scaling and displacement with color ramp

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

Creates animated scaling and vertical displacement based on distance from origin using sine waves.

### Animated Scale and Color on Grid Points

```vex
float min, max, d, i;
min = ch("min");
max = ch("max");
i = @Time * ch("speed");
d = length(@P);
d *= ch("frequency");
d += i;
d = fit(sin(d), -1, 1, min, max);
// ...
```

Creates animated scale and position offsets based on distance from origin, using sine waves driven by time.

### Animating waves with color ramp

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

Creates an animated wave displacement on geometry based on distance from origin, using sine wave with time offset.

### Animated Scale and Vertical Displacement

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

Creates an animated ripple effect by computing a distance-based sine wave that drives both non-uniform scale and vertical displacement.

### Remapping Distance for Color Ramps

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d = d * ch('frequency');
t = fit(sin(d), -1, 1, min, max);
@P.y = t * 0.5;
// ...
```

Modulates the Y position of points using a sine wave based on distance from origin, then remaps that distance value to a 0-1 range for use with a color ramp.

### Color Ramp Driven by Distance

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

Creates animated color based on distance from origin.

### Color Ramp from Distance

```vex
vector chramp(string name);
vector chramp(string color, float t);

float min, max, d, t;
min = ch("min");
max = ch("max");
t = @primnum + ch("speed");
d = length(@P);
// ...
```

Uses the chramp() function to map a distance-based value to a color ramp parameter.

### Color Ramp with Distance-Based Animation

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

Creates an animated scaling and color effect based on distance from origin using a sine wave pattern.

### Fit Distance for Color Ramp

```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d = fit(sin(d * t), -1, 1, min, max);
@P.y = d;
// ...
```

Remaps the distance attribute from its min/max range back to 0-1 range so the color ramp can properly sample colors.

### Color Ramp with Animated Scale

```vex
float d = chf('frequency');
float min = 0;
float max = 1;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(d, max, d);
@P.y -= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Uses a sine wave frequency parameter to drive both box scaling and color via a color ramp.

### Color Ramp with Scale

```vex
float min = chf('min');
float max = chf('max');
float d = chf('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
@P.y -= d * 0.1;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Creates animated boxes that scale and move vertically based on a sine wave, with colors mapped from a color ramp parameter.

### Color Ramp with Vector Cast

```vex
float d = ch('frequency');
d = fit01(d, 0, 1);
float min = 0;
float max = 1;
d = fit01(d, min, max);
@scale = fit01(d, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
// ...
```

Demonstrates using a color ramp parameter with vector() cast to apply color gradients to geometry.

### Color Ramp with Vector Cast

```vex
float d = ch('frequency');
float min = -1;
float max = 1;
d = fit01(sin(d), 0, 1, min, max);
@scale = fit(d, min, max, 0, 1);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
// ...
```

Demonstrates using vector() to cast a chramp() result into a color attribute.

### Color Ramp with Vector Cast

```vex
d = chf('frequency');
d += fit01(sin(d), min, max);
@scale = fit01(sin(d), min, max);
@P.y = pow(d, 2);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Applies a color ramp to geometry by casting chramp() to a vector type, which tells Houdini to interpret the parameter as a color ramp instead of a float spline ramp.

### Color Ramp with Vector Cast

```vex
float d = chf('frequency');
float min = chf('min');
float max = chf('max');

d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), min, max, d);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Uses double fit() operations to first map a sine wave to a custom min/max range, then normalize it back to 0-1 for driving a color ramp.

### Color Ramp from Fit Values

```vex
d = ch('frequency');
d += [];
d = fit01(d, -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d.z;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));

// ...
```

Demonstrates using double fit operations to map values from a custom min/max range back into the 0-1 range required by color ramps.

### Color Ramp with Fit Normalization

```vex
float d = ch('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, 0);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using two fit() functions in sequence to first map a sine wave to a custom min/max range for scaling and positioning, then normalize that value back to 0-1 range to properly drive a co....

### Color Ramp with Normalized Values

```vex
float min = chf('min');
float max = chf('max');
float d = ch('frequency');
d = sin(d);
d = fit(d, -1, 1, min, max);
@scale = d;
@P.y += d/2;
d = fit(d, min, max, 0, 1);
// ...
```

Uses two fit() operations to first map a sine wave to custom min/max range for scaling geometry, then remaps those values back to 0-1 range to properly drive a color ramp.

### Scaling and Color Ramp Mapping

```vex
float min = 0;
float max = 1;
float d = ch('frequency');
d = fit01(d, -1, 1);
@scale = fit(sin(d), min, max, 0, 1);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

This snippet uses multiple fit operations to map a frequency channel value through sine for scale animation, then remaps the result back to 0-1 range to drive a color ramp.

### Color Ramp from Scale Values

```vex
float d = ch('frequency');
float min = 0;
float max = 1;
float i = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(i), -1, 1, min, max);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Demonstrates using two fit() functions to map values from a custom min/max range back to 0-1 range for driving a color ramp.

### Color Ramp with Distance Fit

```vex
@P.y -= d/2;
d = fit(@d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Adjusts point position downward by half the distance, then remaps a distance attribute from its original range to 0-1 using fit().

### Offset and Color Ramp

```vex
@P.y += d/2;
d = fit01(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Offsets point positions vertically by half the distance value, remaps the distance using fit01 with custom min/max parameters, then applies a color ramp based on the remapped distance.

### Backface Detection with Normals

```vex
@Cd = @N;
if (sin(@Cd) < 0) {
    @Cd = 0.1;
}
```

Colors geometry based on normal direction, then uses sine function to detect backfaces.

### Setting Up Vector for Copy to Points

```vex
v@up = {0, 0, 1};
```

Sets the up vector attribute to point in world Z direction, controlling the orientation of copied geometry around the normal axis.

### Animating Up Vector with Time

```vex
v@up = set(0,
            1,
            0
);

v@up = {0, 0, 1};

v@up = set(sin(@Time), 0, 0);
```

Demonstrates setting the up vector (@up) attribute to control orientation of geometry.

### Animating Up Vector with Time Offsets

```vex
v@up = set(sin(@Time), 0, cos(@Time));

v@up = set(sin(@Time), 0, cos(@Time));

float t = @Time - @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));

float t = @Time - @ptnum * ch('offset');
// ...
```

Creates a circular spinning motion by animating the up vector using sine and cosine functions with @Time.

### Animating Up Vector with Time Offsets

```vex
v@up = set(sin(@Time), 0, cos(@Time));

v@up = set(sin(@Frame), 0, cos(@Frame));

float t = @Time - @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));

float d = length(@P);
// ...
```

Demonstrates animating the up vector attribute to create spinning motion by using sine and cosine functions with time values.

### Time-based Up Vector Animation

```vex
float t = @Time + @ptnum + ch('offset');
v@up = set(sin(t), 0, cos(t));
```

Creates an animated up vector that rotates in the XZ plane by combining scene time, point number, and a channel-controlled offset parameter.

### Distance-based Up Vector Animation

```vex
float d = length(@P);
vector t = @Time * d * ch('offset');
v@up = set(sin(t), 0, cos(t));
```

Creates animated up vectors that rotate in the XZ plane based on each point's distance from the origin.

### Wave Animation with Distance Offset

```vex
float d = length(@P);
float t = @Time - d * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates an animated wave effect by calculating a time offset based on distance from origin, then uses that offset to animate both the up vector (rotating around Y axis) and the Y position (vertical....

### Animated vertical oscillation with sine

```vex
float d = length(@P);
float t = @Time * @offset;
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates dancing geometry by animating the vertical position of points using a sine function.

### Animated Instance Orientation

```vex
float d = length(@P);
float t = @Time * (1 + d * @offset);
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates animated orientation for instanced geometry using time-based rotation.

### Animated vector orientation with sine waves

```vex
float d = length(@P);
float t = @Time * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

This snippet demonstrates animating both vector orientation and position using time-based sine waves.

### Animating geometry with time and up vector

```vex
float d = length(@P);
float t = @Time * chf('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * d;
```

Calculates distance from origin and creates time-based animation using a channel reference for offset control.

### Time-Based Wave with Offset

```vex
float d = length(@P);
float t = @Time * (1-@offset);
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * d;
```

Creates a time-animated wave effect that varies by distance from origin, using an offset attribute to control timing.

### Mixed vector and attribute operations

```vex
float d = length(@P);
vector c = {1-d, 0, d*offset};
v@up = set(sin(s), 0, cos(s));
@P.y += sin(s.x * 2) * 0.5;
```

This snippet demonstrates multiple unrelated operations: calculating distance from origin, creating a color vector based on distance and an offset parameter, setting an up vector using sine and cos....

### Animated Up Vector with Offset

```vex
float d = length(@P);
float t = @Time * d * v@offset;
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates an animated up vector that rotates in the XZ plane using sine and cosine, with the rotation speed modulated by distance from origin and an offset attribute.

### Animated up vector using distance and time

```vex
float d = length(@P);
float t = @Time * d * f@offset;
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates an animated rotation effect by computing distance from origin and combining it with time to drive an up vector that rotates in the XZ plane.

### Distance-based color ramp with wave

```vex
float d = length(@P);
vector c = chramp('c', d * chf('offset'));
v@up = set(sin(s), 0, cos(s));
@P.y += sin(s * 2) * chf('wave');
```

Calculates distance from origin and uses it to sample a color ramp with an offset parameter.

### Animated up vector with distance

```vex
float d = length(@P);
vector t = @Time * d * (1.0/'offset');
v@up = set(sin(t), 0, cos(t));
v@N = sin(t * 2) * 0.5;
```

Creates an animated up vector that rotates based on distance from origin and time, using a channel reference to 'offset' parameter.

### Animated Up Vector with Offset

```vex
float d = length(@P);
float t = @Time * (1-offset);
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates an animated up vector that rotates in the XZ plane using sine and cosine, while simultaneously adding vertical oscillation to point positions.

### Time-based wave with rotation vector

```vex
float d = length(@P);
float t = @Time - d * chf('offset');
v@up = set(sin(t), 0, cos(t));
@P.y = sin(t * 2) * 0.5;
```

Creates a wave effect that propagates outward from the origin by calculating distance from center and offsetting time accordingly.

### Distance-Based Animated Up Vector

```vex
float d = length(@P);
float t = @Time - d * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.1;
```

Creates an animated up vector that rotates based on time offset by distance from origin, while also adding vertical oscillation.

### Orient Attribute Initialization

```vex
@orient = {0,0,0,1};
```

Initializes the orient attribute as a quaternion with identity rotation values (0,0,0,1).

### Orient Attribute Initialization

```vex
@orient = {@x, @y, @z, 1};
```

Initializes the @orient quaternion attribute using point position coordinates (@x, @y, @z) with a w-component of 1.

### Animating Quaternion Orientations

```vex
float angle = ch('angle');
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// Animated version
float angle = @Time;
vector axis = chv('axis');
// ...
```

Demonstrates how to create quaternion-based orientations using channel references for angle and axis parameters.

### Orient Attribute with Quaternions

```vex
@orient = {0,0,0,1};

float angle = ch('angle');
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// Animating with time
// ...
```

The @orient attribute controls instance orientation using quaternions, which lock copied geometry to specific rotations regardless of their normal attributes.

### Animating Orient with Time

```vex
float angle = ch('angle');
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// Animated version using time
float angle = @Time;
vector axis = chv('axis');
// ...
```

Demonstrates creating an @orient quaternion attribute by combining an angle and axis vector, then progressively refining it to use @Time for automatic animation.

### Animating Orientation with Time

```vex
float angle = ch('angle');
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// Using @Time to animate
float angle = @Time;
vector axis = chv('axis');
// ...
```

Demonstrates creating an @orient quaternion attribute from an angle and axis, first using channel references for static control, then replacing the angle parameter with @Time to create smooth rotat....

### Animating Quaternion Rotation with Time

```vex
float angle = @Time;
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// More concise version:
@orient = quaternion(@Time, chv('axis'));
```

Demonstrates using the @Time attribute to drive quaternion rotation angle, creating smooth animation of geometry spinning around a user-defined axis.

### Compacting Quaternion Code

```vex
float angle = @Time;
vector axis = chv('axis');

@orient = quaternion(angle, axis);

// Compact version:
@orient = quaternion(@Time, chv('axis'));
```

Demonstrates code refactoring by condensing multi-line quaternion setup into a single compact line.

### Quaternion Rotation with Parameters

```vex
float angle = @Time;
vector axis = chv('axis');

angle = ch('angle');
angle = @Time*ch('speed');

axis = chv('axis');

// ...
```

Creates a quaternion-based rotation by combining time with a speed parameter and a user-defined axis.

### Quaternion Rotation with Per-Point Offsets

```vex
// Compact version:
@orient = quaternion(@Time, chv("axis"));

// Expanded version with offsets:
float angle;
vector axis;

angle = ch("angle");
// ...
```

Demonstrates two approaches to creating quaternion rotations: a compact one-line version using @Time directly, and an expanded version that builds the rotation angle from multiple components includ....

### Point-based quaternion rotation offsets

```vex
float angle = @Time;
vector axis = chv('axis');

@orient = quaternion(@Time, chv('axis'));


float angle;
vector axis;
// ...
```

Demonstrates refactoring quaternion rotation code from compact single-line form to expanded multi-line form, then extending it with point number-based offsets.

### Animating Quaternion Rotation with Time

```vex
float angle;
vector axis;

angle = ch('angle');
angle += gettime();
axis = chv('axis');

@orient = quaternion(angle, axis);
```

Creates a time-based rotation by reading an angle parameter with ch(), adding the current frame time using gettime(), and combining it with an axis vector to create a quaternion stored in @orient.

### Animated Quaternion Rotation

```vex
float angle;
vector axis;

angle = ch('angle');
angle *= @Time * ch('speed');
axis = chv('axis');

@orient = quaternion(angle, axis);
```

Creates an animated rotation by building a quaternion from a time-scaled angle and axis.

### Quaternion orientation with point offset

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum * ch('offset');
axis = chv('axis');

@orient = quaternion(angle, axis);
```

Creates per-point rotation orientations using quaternions, where each point's rotation angle is offset based on its point number multiplied by an offset parameter.

### Animating Quaternion Rotations with Time

```vex
float angle;
vector axis;

angle = ch('angle');
angle += ch('offset');
angle += @Time * ch('speed');
axis = chv('axis');

// ...
```

Builds an animated rotation by creating a quaternion from an angle and axis, where the angle is composed of a base value, an offset, and a time-based component scaled by speed.

### Quaternion Rotation with Time Animation

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum * ch('offset');
angle += @Time * ch('speed');

axis = chv('axis');
// ...
```

Creates animated quaternion rotations per point by combining a base angle, point-number-based offset, and time-based speed multiplier.

### Animating Quaternion Rotation with Time

```vex
float angle;
vector axis;

angle = ch('angle');
axis = chv('axis_of_rot');
angle *= @Time * ch('speed');
axis = chv('axis');

// ...
```

Creates animated quaternion rotation by multiplying a base angle by @Time and a speed parameter.

### Quaternion Rotation with Offset

```vex
float angle;
vector axis;

angle = ch('angle');
angle += (@Time * ch('offset'));
angle += @Time * ch('speed');

axis = chv('axis');
// ...
```

Demonstrates how to create per-point quaternion rotations by combining a base angle from a channel with time-based offsets and speed multipliers.

### Quaternion Rotation with Frame Offset

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @Frame * ch('offset');
angle = @Time * ch('speed');

axis = chv('axis');
// ...
```

Creates a rotation using quaternions where the angle is controlled by channel parameters and modified by frame offset and time-based speed.

### Quaternion rotation with axis variation

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum*ch('offset');
angle += @Time*ch('speed');
axis = chv('axis');

// ...
```

Demonstrates quaternion rotation with customizable axis parameter, creating progressive rotation variations across points by accumulating angle contributions from base angle, point-number offset, a....

### Animated Quaternion Rotation with Offset

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @Time * ch('speed');
angle += @ptnum * ch('offset');
axis = chv('axis');

// ...
```

Creates animated rotation using quaternions with per-point offset control.

### Quaternion Rotation with Time and Offset

```vex
float angle;
vector axis;

angle = ch('angle');
angle += ch('offset')*@ptnum*ch('speed');
angle += @Time * ch('speed');
axis = chv('axis');

// ...
```

This code creates per-point rotations using quaternions, combining a base angle with point-number-based offsets and time-based animation.

### Normalized Axis Quaternion Rotation

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum*ch('offset');
angle += @Time*ch('speed');

axis = chv('axis');
// ...
```

Creates per-point rotation using quaternions with a normalized rotation axis.

### Normalizing Rotation Axis for Orient

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum*ch('offset');
angle *= @Time * ch('speed');

axis = chv('axis');
// ...
```

Demonstrates normalizing a rotation axis vector before using it to create an orient quaternion attribute.

### Scaling Axis to Zero for Quaternion

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= 0;

@orient = quaternion(angle, axis);
```

Demonstrates scaling a normalized axis vector to zero using the *= operator before passing it to a quaternion function.

### Quaternion Rotation with Scaled Axis

```vex
vector axis;

axis = chv('axis');
axis = normalize(axis);
axis *= 10;

@orient = quaternion(axis);
```

Creates a rotation quaternion from a normalized axis vector whose magnitude is then scaled by a parameter.

### Time-based Quaternion Rotation

```vex
vector axis1;
axis1 = chv('axis');
axis1 = normalize(axis1);
axis1 *= @Time;

@orient = quaternion(axis1);
```

Creates a smooth rotation around a custom axis by scaling the normalized axis vector by @Time and converting it to a quaternion orientation.

### Quaternion Axis-Angle Rotation

```vex
vector axis1;
axis1 = chv('axis');
axis1 = normalize(axis1);
axis1 *= {max};

@orient = quaternion(axis1);
```

Demonstrates creating a quaternion rotation from an axis-angle representation, where the axis direction defines the rotation axis and the vector's magnitude defines the rotation amount in radians.

### Quaternion Axis-Angle Representation

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis = {1,0,0};

@orient = quaternion(axis);

vector axis;
// ...
```

Demonstrates the axis-angle representation of quaternions where a vector's length (magnitude) encodes rotation amount while its direction encodes the rotation axis.

### Vector-Driven Quaternion Rotation

```vex
vector axis;

axis = chv('axis');
axis = normalize(axis);
axis *= @Time;

@orient = quaternion(axis);
```

Creates a quaternion rotation from a normalized vector axis scaled by @Time.

### Quaternion from Normalized Axis

```vex
vector axis;

axis = chv('axis');
axis = normalize(axis);
axis = @Cd;

@orient = quaternion(axis);
```

Creates a quaternion orientation from a normalized vector axis.

### Quaternion from Axis Vector

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);

@orient = quaternion(axis);
```

Creates a quaternion orientation from a user-defined axis vector parameter.

### Quaternion angle issue with degrees

```vex
vector axis;

axis = chv("axis");
axis = normalize(axis);
axis = 45;

@orient = quaternion(axis);
```

This code demonstrates a common mistake when creating quaternions where the angle parameter is set to 45, expecting degrees, but the quaternion() function actually expects radians.

### Quaternions with Radians

```vex
vector axis1;

axis1 = chv('axis1');
axis1 = normalize(axis1);
axis1 *= 45;

@orient = quaternion(axis1);
```

Demonstrates that the quaternion() function expects rotation angles in radians, not degrees.

### Quaternion Rotation Angles in Radians

```vex
vector axis;
axis = chv("axis");
axis = normalize(axis);
axis = 1.570795;

@orient = quaternion(axis);
```

The quaternion() function expects rotation angles in radians, not degrees.

### Quaternion Rotation with Radians

```vex
vector axis;

axis = chv("axis");
axis = normalize(axis);
axis *= 1.570795;

@orient = quaternion(axis);
```

Creates a quaternion rotation by taking an axis vector parameter, normalizing it, and multiplying by 1.570795 radians (approximately π/2 or 90 degrees).

### Quaternion 90 Degree Rotation

```vex
vector axis;
axis = chv("axis");
axis = normalize(axis);
axis *= 1.570795;

@orient = quaternion(axis);
```

Creates a 90-degree rotation quaternion by normalizing an axis vector from a parameter and multiplying it by π/2 (1.570795 radians).

### Quaternion Rotation with Radians

```vex
vector axis;

axis = chv("axis");
axis = normalize(axis);
axis = 1.570795;

@orient = quaternion(axis);
```

Demonstrates creating a quaternion rotation using a hardcoded radian value (1.570795, approximately π/2) for a 90-degree rotation.

### Quaternion 90 Degree Rotation

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= 1.570795;

@orient = quaternion(axis);
```

Creates a quaternion rotation by multiplying a normalized axis vector by approximately π/2 (1.570795 radians), which equals 90 degrees.

### Converting Degrees to Radians for Quaternions

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis = radians(axis);

@orient = quaternion(axis);
```

Demonstrates using the radians() function to convert degree values to radians before creating a quaternion orientation.

### Radians Function for Quaternions

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= radians(90);

@orient = quaternion(axis);
```

Demonstrates using the radians() function to convert degrees to radians for quaternion rotation.

### Radians and PI for Quaternion Rotations

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= radians(90);

@orient = quaternion(axis);

// Alternative using $PI:
// ...
```

Demonstrates two alternative methods for converting degrees to radians when creating quaternion rotations: using the radians() function to convert 90 degrees, or using the built-in $PI constant div....

### Quaternion Rotation with Radians

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
float angle = radians(90);

@orient = quaternion(angle, axis);
```

Creates a quaternion rotation using the radians() function to convert 90 degrees to radians for cleaner code.

### Converting Degrees to Radians

```vex
vector axis;

axis = chv('axis');
axis = normalize(axis);
axis = radians(90);

@orient = quaternion(axis);
```

Uses the radians() function to convert 90 degrees to radians for quaternion rotation, simplifying angle calculations.

### Quaternion Rotation with Pi Constant

```vex
vector axis1;
axis1 = chv('axis');
axis1 = normalize(axis1);
float angle = pi / 2;

@orient = quaternion(angle, axis1);
```

Demonstrates creating a quaternion rotation using Houdini's built-in pi constant instead of the radians() function.

### PI constant without dollar sign

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
float angle = PI/2;

@orient = quaternion(angle, axis);

// Alternative with randomized rotation
// ...
```

Demonstrates using the PI constant directly without the dollar sign prefix (a change introduced around January 2023).

### Noise-based quaternion rotation animation

```vex
vector axis1;
axis1 = chv("axis");
axis1 = normalize(axis1);
float angle = trunc(noise(@P + @Time) * 4) * $PI/2;

@orient = quaternion(angle, axis1);
```

Replaces random rotation with noise-based rotation that evolves over time, using position and time as noise input.

### Quaternion Rotations with Noise

```vex
vector axis1;
axis1 = chv("axis");
axis1 = normalize(axis1);
axis1 *= trunc(noise(@P*chf("freq"))*4)*$PI/2;

@orient = quaternion(axis1);
```

Creates random 90-degree rotations by using normalized noise values multiplied by PI/2 increments.

### Quaternion Rotation from Noise

```vex
vector axis1;
axis1 = chv('axis');
axis1 = normalize(axis1);
axis1 = trunc(noise(@P * @Time) * 4) * $PI / 2;

@orient = quaternion(axis1);
```

Creates randomized rotations using noise truncated to discrete angles (multiples of PI/2), then converts the result to a quaternion orientation.

### Ramp Control for Noise Remapping

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*f@time);
@a = chramp('noise_rerange', @a);
axis *= trunc(@a*4)*$PI/2;

@orient = quaternion(axis);
```

Demonstrates replacing a fit() function with chramp() to remap noise values using an interactive ramp parameter.

### Chramp for Interactive Noise Remapping

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P * @Time);
@a = chramp('noise_range', @a);
axis = trunc(@a * 4) * @PI / 2;

@orient = quaternion(axis);
```

Replaces a fixed fit() function with chramp() to enable interactive remapping of noise values via a ramp parameter.

### Interactive Ramp Control for Noise

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+@Time);
@a = fit(@a, 0.4, 0.6, 0, 1);
axis = trunc(@a*4)*$PI/2;

@orient = quaternion(axis);
// ...
```

Demonstrates replacing fit() with chramp() to enable interactive UI control for remapping noise values.

### Ramp-Driven Quaternion Rotation

```vex
@a = chramp('noise_remap', @a);
axis *= trunc(@a * 4) * (PI / 2);

@orient = quaternion(axis);
```

Uses a channel ramp parameter to remap noise values, then truncates and scales the result to create discrete 90-degree rotation steps.

### Ramp Parameter for Noise Remapping

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*@Time);
@a = chramp('noise_rerange', @a);
axis = trunc(@a*4)*@a/2;

@orient = quaternion(axis);
```

Demonstrates using chramp() to create an interactive ramp parameter that remaps noise values, providing artist-friendly control over the noise distribution.

### Visualizing Noise with Quaternion Rotation

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@ptnum);
@a = chramp('noise_remap', @a);
axis *= trunc(@a/4)*(PI);
@orient = quaternion(axis);
```

This code generates noise-driven rotation by creating a normalized axis vector from a parameter, generating noise per point, remapping it through a ramp parameter, then using that value to create q....

### Rotating Up Vector with Sin and Cos

```vex
int i = {0,1,0};
float s = sin(@Time);
float c = cos(@Time);
@up = set(s, 0, c);
```

Uses sine and cosine of time to create a rotating up vector that circles around the Y-axis.

### Quaternion Rotation with Animated Up Vector

```vex
@N = {0,1,0};
float s = sin(@Time);
float c = cos(@Time);
@up = set(s, 0, c);

@orient = quaternion(maketransform(@N, @up));
```

Creates a rotating orientation by computing an animated up vector that circles around using sine and cosine of time.

### Matrix to Quaternion Conversion

```vex
matrix3 m = ident();
@orient = quaternion(m);

matrix3 m = ident();
@orient = quaternion(m);

vector rot = radians(chv('euler'));
@orient = eulertoquaternion(rot, 0);
```

Demonstrates three methods of setting quaternion orientation: converting from a matrix3 identity matrix, and converting from Euler angles using channel references.

### Euler to Quaternion Conversion

```vex
vector rot = radians(chv('euler'));
@orient = eulertoquaternion(rot, 0);
```

Converts Euler angle rotations (XYZ degrees) from a vector parameter into a quaternion orientation.

### Euler to Quaternion Conversion

```vex
vector rot = radians(chv("euler"));
@orient = eulertoquaternion(rot, 0);
```

Converts Euler angles (in degrees) from a channel parameter to a quaternion and stores it in the @orient attribute.

### Quaternion Blending with Slerp

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion(maketransform({0,1,0} * PI/2));

@orient = slerp(a, b, ch('blend'));
```

Uses the slerp() function to perform spherical linear interpolation between two quaternions, blending from identity quaternion 'a' to a 90-degree rotation 'b' around the Y-axis.

### Quaternion Interpolation with Chramp

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$FF/2);
float blend = chramp("Time", $FF%1);
@orient = slerp(a, b, blend);
```

Uses chramp() to create a ramped blend value from a time-based parameter ($FF%1), then applies that blend to spherically interpolate (slerp) between two quaternion orientations.

### Animating Quaternion Blend with Ramp

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
float blend = chramp('blendramp', $T % 1);
4@orient = slerp(a, b, blend);
```

Uses a channel ramp parameter to control the blend value between two quaternions over time.

### Quaternion Slerp with Ramp Control

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * $F/2);
float blend = chramp('blendramp', @Time % 1);
@orient = slerp(a, b, blend);
```

This demonstrates using a ramp parameter to control the blend factor in a quaternion slerp operation.

### Quaternion Slerp Setup

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = {0, 1, 0};
axis = normalize(axis);
seed = noise(@P + @Time);

// ...
```

Prepares variables for quaternion spherical interpolation by normalizing an axis vector, generating a noise-based seed value from position and time, and setting up base and target quaternions for r....

### Quaternion Slerp Animation

```vex
axis = normalize(axis);
seed = noise(@ptnum);
seed = chramp('noise_remap', seed);
axis *= trunc(seed * 4) * @P[2];

target = quaternion(axis);
base = {0, 0, 0, 1};
blend = chramp('anim', @Time % 1);
// ...
```

Uses slerp (spherical linear interpolation) to smoothly blend between a base quaternion and a target quaternion over time.

### Quaternion Orientation with Transform Order

```vex
@vis = normalize(@vis);
seed = chf("seed");
seed = chramp("noise_orange", seed);
@vis = trunc(@vis) * @P[2];

target = quaternion(@vis);
base = {0, 0, 0, 1};
blend = chramp("anim", @Frame % 1);
// ...
```

Demonstrates how the order of transform nodes affects orientation attribute behavior.

### Spherical Interpolation with Orient

```vex
@orient = slerp(base, target, blend);
```

Uses spherical linear interpolation (slerp) to smoothly blend between two quaternion orientations stored in 'base' and 'target' variables, with the blend factor controlling the interpolation amount....

### Quaternion slerp animation

```vex
vector4 target, base;
vector axis;
float seed, blend;

@axis = chv('axis');
@axis = normalize(@axis);

target = quaternion(@axis);
// ...
```

Creates smooth quaternion rotation animation using slerp (spherical linear interpolation) between an identity quaternion and a target orientation.

### Orient Attribute with Quaternions

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N,@up));
```

Creates an orientation quaternion for each point by normalizing the point position to use as the normal direction, defining an up vector, and constructing a transformation matrix that is converted ....

### Creating Quaternions with Extra Rotation

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));

vector4 extrarot = quaternion($PI/2, {1,0,0});
```

Demonstrates creating a base quaternion orientation from normalized position and up vector using maketransform(), then defines an additional quaternion rotation for later combination.

### Identity Matrix Creation

```vex
matrix3 m = [[1,0,0,0,1,0,0,0,1]];

matrix3 m = ident();
```

Demonstrates two equivalent ways to create a 3x3 identity matrix in VEX: explicitly defining the matrix values as a grid of numbers with ones on the diagonal and zeros elsewhere, or using the built....

### Identity Matrix Definition

```vex
matrix3 m = [[1,0,0],[0,1,0],[0,0,1]];

matrix3 m = ident();
```

Demonstrates two ways to create a 3x3 identity matrix in VEX.

### Resetting Primitive Transform and Position

```vex
matrix3 m = ident();
setprimintrinsic(0, 'transform', 0, m);
@P = {0,0,0};
```

Creates an identity matrix and uses it to reset a primitive's transform intrinsic back to default, then resets all point positions to the origin.

### Casting Matrix4 to Matrix3

```vex
matrix3 m = matrix3(myFancyAxesMatrix);

matrix pft = primintrinsic(0, "packedfullTransform", @ptnum);

4@a = pft;
```

Demonstrates extracting the packed full transform intrinsic from packed geometry, which returns a 4x4 matrix, and casting it to a matrix3 to obtain a 3x3 transformation matrix.

### Setting packed primitive transform with matrix

```vex
vector qorient = quaternion({0,1,0} * 2*$PI);
@qScale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, @qScale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Constructs a transform matrix by creating an identity matrix, applying a scale, and then multiplying by a rotation matrix derived from a quaternion.

### Matrix Type Casting and Intrinsics

```vex
matrix3 m = matrix3(myFancyMatrix);

matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);

4@a = pft;
```

Demonstrates casting between matrix types and reading packed primitive transform data.

### Reading Packed Primitive Transform

```vex
matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);
```

Reads the packed full transform intrinsic from a packed primitive as a 4x4 matrix.

### Reading Packed Transform Intrinsic

```vex
matrix pft = primintrinsic(0, "packedfullransform", @ptnum);
4@a = pft;
```

Retrieves the packed full transform intrinsic from a primitive as a matrix and stores it in a 4x4 matrix attribute for debugging.

### Reading Packed Transform Matrix

```vex
matrix pft = primintrinsic(0, "packedfullransform", @ptnum);

@a = pft;
```

Reads the packed primitive's full transformation matrix using primintrinsic() and stores it in a 4x4 matrix attribute.

### Extracting Packed Transform Matrix

```vex
matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);
4@a = pft;
```

Retrieves the packed full transform (4x4 transformation matrix) from a packed primitive using primintrinsic and stores it in a custom matrix attribute.

### Reading Packed Primitive Transform Matrices

```vex
matrix pft = primintrinsic(0, "packedfulltramsform", @ptnum);
4@a = pft;
```

Reads the full transformation matrix from a packed primitive using the primintrinsic function and stores it in a 4x4 matrix attribute.

### Reading Packed Transform Matrix

```vex
matrix pft = printintrinsic(0, "packedfulltransform", @ptnum);
4@a = pft;
```

Reads the packed full transform intrinsic attribute as a 4x4 matrix and stores it in a matrix attribute.

### Reading Packed Primitive Transform Matrix

```vex
matrix pft = printintrinsic(0, "packedfullTransform", @ptnum);
i@a = pft;
```

Reads the packed primitive's full transform matrix using printintrinsic() and stores it in a matrix variable.

### Reading Packed Transform Matrix

```vex
matrix pft = primintrinsic(0, "packedfulltrasnform", @ptnum);
4@a = pft;
```

Retrieves the 4x4 transformation matrix from a packed primitive and stores it in a matrix attribute.

### Reading Packed Transform Matrix

```vex
matrix xft = primintrinsic(0, "packedfulltransform", @ptnum);
4@xform = xft;
```

Retrieves the full transformation matrix from a packed primitive using primintrinsic and stores it in a matrix4 attribute.

### Extracting Rotation-Scale from Matrix

```vex
matrix3 rotandscale = matrix3(pf);

rotandscale;
```

Demonstrates extracting the rotation and scale components from a 4x4 transformation matrix by casting it to a matrix3, which strips out the translation row and column.

### Extracting Rotation-Scale from Matrix

```vex
matrix3 rotandscale = matrix3(p1{});
```

Extracts the 3x3 rotation and scale component from a 4x4 transformation matrix by casting it to matrix3.

### Extracting Matrix3 from Packed Transform

```vex
matrix pft = printintrinsic(0, "packedfulltramsform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```

Demonstrates extracting a 3x3 rotation and scale matrix from a packed primitive's full transform matrix by using the matrix3() cast.

### Extracting rotation and scale from packed transform

```vex
matrix pft = primintrinsic(0, "packedfullTransform", @ptnum);
matrix3 rotandscale = matrix3(pft);
@matrix3b = rotandscale;
```

Demonstrates extracting the rotation and scale components from a packed primitive's full transform matrix by converting the 4x4 transform matrix to a 3x3 matrix.

### Extracting Rotation and Scale from Packed Transform

```vex
matrix pft = primintrinsic(0, "packedfullttransform", @ptnum);
@Cd = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```

Extracts the packed full transform matrix from a packed primitive and converts it to a matrix3 to isolate the rotation and scale components (excluding translation).

### Primitive Intrinsics and Attribute Definition

```vex
int open_close = int(rand(@primnum)*frame**2);
setprimintrinsic(0, "closed", @primnum, open_close);

int @pnumclass = int(rand(@primnum)*2+1);
s@primattribs = "N, @closed, {Cd,uv@,@pnumclass}";
```

Sets a primitive intrinsic 'closed' attribute using randomized values based on primitive number and frame squared, then creates a primitive number classification and defines a string listing availa....

### Circular Motion with primuv

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.5, 2);
@P += {0, 3, uv.x};

// ...
```

Creates circular motion by using sin/cos with @Time to generate UV coordinates, then uses primuv() to sample a position from the first input geometry.

### Circular Motion via primuv

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0, 2);

uv *= {0.5, 0.5};
// ...
```

Creates circular motion by using sine and cosine of time to generate UV coordinates, then samples a position on a primitive using primuv().

### Circular Motion with primuv

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0, 0.2);
uv += {0.5, 0.5};

// ...
```

Creates circular motion by generating UV coordinates using sin/cos of time, then remapping the values to a small range centered at (0.5, 0.5) to sample positions from the primitive on input 1.

### Circular Motion with primuv

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.2, 0.5);
uv += {0.5, 0.5};

// ...
```

Creates circular motion by using sine and cosine of time to generate UV coordinates that move in a circle.

### Circular UV Motion Sampling

```vex
vector uv;

uv.x = sin(@Frame*10);
uv.y = cos(@Frame*10);

uv = fit(uv, -1, 1, 0.2, 0.2);
uv += set(0.5, 0.5, 0);

// ...
```

Animates a point in circular motion by using sine and cosine of the frame number to generate UV coordinates, then samples position and normal attributes from input geometries using primuv().

### Circular Motion with primuv

```vex
vector uv;

uv.x = sin(@Frame*10);
uv.y = cos(@Frame*10);

uv = fit(uv, -1, 1, 0.2, 0.2);
uv += {0.5, 0.5};

// ...
```

Creates circular motion by using sine and cosine of the frame number to generate UV coordinates, then samples position and normal attributes from primitives using primuv().

### Animating UV sampling with trigonometry

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.2, 0.8);
uv += {0.5, 0.5};

// ...
```

Creates circular motion by computing UV coordinates using sine and cosine functions driven by @Time, then samples position and normal attributes from input 1 at those animated UV coordinates.

### Circular Path with Sine and Cosine

```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);

@P = primv(1, 'P', 0, uv);
// ...
```

Creates circular motion by using sine and cosine functions on the same time value for UV coordinates, then uses fit() to scale the range from [-1,1] to [-0.2,0.2].

### Circular UV Animation with Primuv

```vex
vector uv;

uv.x = sin(6*@Time*2);
uv.y = cos(6*@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += set(0.5, 0.5, 0);

// ...
```

Creates circular motion by using sine and cosine functions with the same time-based input on different UV axes.

### Circular UV Animation with Fit

```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);

@P = primuv(1, 'P', 0, uv);
// ...
```

Creates circular motion by combining sin and cos functions with @Time for UV coordinates, then remaps the range from [-1,1] to [-0.2,0.2] using fit() to scale down the motion.

### Animated UV Circle Sampling

```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

// ...
```

Creates a circular animation path by using sine and cosine of time to generate UV coordinates, which are then scaled down and offset to stay within valid UV space (0-1).

### Circular UV Animation with primuv

```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

// ...
```

Creates circular animation by calculating UV coordinates using sine and cosine of time, fitting the range from -1,1 to -0.2,0.2, then offsetting by 0.5 to center.

### Circular UV animation with primuv

```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

// ...
```

Creates a circular motion path by using sin and cos of time to generate UV coordinates that animate in a circle.

### Circular UV Animation with primuv

```vex
vector uv;

uv.x = sin($T*$TPI*2);
uv.y = cos($T*$TPI*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

// ...
```

Creates circular motion by calculating UV coordinates using sin and cos functions, then uses primuv to sample both position and normal from a surface geometry (input 1).

### Circular UV Animation with primuv

```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

// ...
```

Creates circular motion by using sine and cosine of time to generate UV coordinates, fitting them to a constrained range around the center (0.5, 0.5), then sampling position and normal attributes f....

### Animated UV Sampling on NURBS

```vex
vector uv;

uv.x = sin(@Time * 10);
uv.y = cos(@Time * 10);

uv = fit(uv, -1, 1, 0.2, 0.8);
uv += {0.5, 0.5};

// ...
```

Creates animated UV coordinates using sine and cosine of time, fits them to a specific range, then samples position and normal attributes from a NURBS surface at those UV coordinates.

### Animating Points on NURBS Surface with UV

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

vector UV = fit(uv, -1, 1, 0.2, 0.8);
UV += {0.5, 0.5, 0};

// ...
```

Creates animated circular motion on a surface by calculating UV coordinates using sine and cosine of time, fitting them to a specific range, then sampling position and normal attributes from a NURB....

### Animating Point on NURBS Surface

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.2, 0.2);
uv += {0.5, 0.5};

// ...
```

Creates a circular animation path on a NURBS surface by generating UV coordinates using sine and cosine of time.

### UV Sampling Animated NURBS Surface

```vex
vector uv;

uv.x = sin(@Time*u);
uv.y = cos(@Time*u);

uv = fit(uv, -1, 1, 0.2, 0.8);
uv += set(0.5, 0.5, 0.0);

// ...
```

Samples position and normal attributes from a NURBS surface (input 1) using dynamically calculated UV coordinates that animate in a circular pattern over time.

### Animated UV Surface Sampling

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

v@UV = fit(uv, -1, 1, 0.2, 0.2);
v@UV += {0.5, 0.5};

// ...
```

Creates animated UV coordinates using sine and cosine of time, fits them to a normalized range centered at 0.5, then samples position and normal attributes from a reference geometry's surface using....

### Animated UV sampling on surface

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

UV = fit(uv, -1, 1, 0.2, 0.8);
UV += {0.5, 0.5};

// ...
```

Creates animated UV coordinates using sine and cosine functions driven by @Time, remaps them from -1:1 range to 0.2:0.8, offsets by 0.5 to center, then samples position and normal attributes from a....

### Animating Point on Surface with UV

```vex
vector uv;

uv.x = sin(@Time*4);
uv.y = cos(@Time*4);

vector UV = fit(uv, -1, 1, 0.2, 0.8);
UV += {0.5, 0.5, 0};

// ...
```

Creates an animated UV coordinate using sine and cosine of time, fits the range to (0.2-0.8), offsets to center, then samples position and normal from a surface geometry at input 1 using primuv.

### Animated UV Surface Sampling

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

UV = fit(uv, -1, 1, 0.2, 0.8);
UV += (0.5, 0.5);

// ...
```

Creates animated UV coordinates using sine and cosine of @Time multiplied by 10, fits them to a range, then uses primuv() to sample position and normal attributes from input 1 at those UV coordinates.

### Animating Points on Surface with primuv

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

// ...
```

Animates a point riding along a surface by computing UV coordinates using sine and cosine of @Time, fitting them to a small range around (0.5, 0.5), then sampling position and normal from a referen....

### Animating Point on Surface with UV

```vex
vector uv;

uv.x = sin(@Time*10);
uv.y = cos(@Time*10);

uv = fit(uv, -1, 1, 0.2, 0.8);
uv += {0.5, 0.5};

// ...
```

Animates a point's position and normal by sampling UV coordinates that move in a circular pattern on a surface.

### Animated UV Surface Sampling

```vex
vector uv;

uv.x = sin(@Time*u);
uv.y = cos(@Time*u);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += set(0.5, 0.5, 0);

// ...
```

Creates animated UV coordinates using sine and cosine functions driven by time, then samples position and normal data from a reference surface at those coordinates.

### Animating Point on Surface with primuv

```vex
uv.x = sin(@Frame*10);
uv.y = cos(@Frame*10);

uv = fit(uv, -1, 1, 0.2, 0.2);
uv += {0.2, 0.5};

@P = primuv(1, 'P', uv);
@N = primuv(1, 'N', uv);
```

This code animates a point riding along a surface by calculating UV coordinates that vary with the frame number using sine and cosine functions.

### Attaching Object to Surface Using primuv

```vex
vector uv;

uv.x = sin($T*2);
uv.y = cos($T*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

// ...
```

Demonstrates attaching a point to an animated surface position using primuv() lookups.

### Parametric UV Sampling with Primuv

```vex
vector uv;

uv.x = sin(PI*ue**2);
uv.y = cos(PI*ue**2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

// ...
```

Creates animated UV coordinates using sine and cosine functions based on a time variable, fits them to a smaller range centered at 0.5, then samples position and normal attributes from a primitive ....

### Animated UV Sampling with Primuv

```vex
vector uv;

uv.x = sin(@id*@Time*2);
uv.y = cos(@id*@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5, 0.5};

// ...
```

Creates animated UV coordinates using sine and cosine functions driven by point id and time, then uses primuv() to sample both position and normal attributes from a NURBS surface, causing points to....

### xyzdist with UV and prim attributes

```vex
i@prim1d;
v@uv;
@dist;

@dist = xyzdist(1, @P, @prim1d, @uv);
```

Uses xyzdist() to find the closest point on geometry from input 1, storing the resulting primitive ID in @prim1d and UV coordinates in @uv.

### xyzdist with primitive UVs

```vex
i@primid;
v@up;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```

Uses xyzdist to find the closest point on a second input geometry, returning the distance and writing the primitive ID and UV coordinates to attributes.

### xyzdist Introduction

```vex
@grid;
v@v;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```

The xyzdist function finds the minimum distance from a point to a surface geometry and outputs the primitive ID and UV coordinates of the closest point on that surface.

### xyzdist Setup with Attributes

```vex
@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```

Sets up xyzdist() to find the closest point on input geometry (input 1) to the current point position.

### xyzdist basic setup

```vex
@ptnum;
v@uv;
@dist;

@dist = xyzdist(1, @P, @ptnum, @uv);
```

Sets up attribute declarations for xyzdist() function to find the closest point on input 1 (a grid) to the current point position.

### XYZ Distance Setup with UV Sampling

```vex
int prim = 0;
vector uv;
f@dist;

uv = fit(uv, -1, 1, -0.2, 0.2);
uv *= {0.5, 0.5};

@P = primuv(1, "P", 0, uv);
// ...
```

Initializes variables for distance calculations and UV-based primitive sampling.

### xyzdist primitive distance query

```vex
i@ptnum1;
v@uv;
f@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```

Uses xyzdist() to find the closest point on input geometry (input 1) to the current point position.

### xyzdist output attributes

```vex
i@prim1d;
v@uv1;
f@dist;

@dist = xyzdist(1, @P, @prim1d, @uv1);
```

Demonstrates that xyzdist() returns multiple values: the distance (explicit return), primitive ID (written to @prim1d), and UV coordinates (written to @uv1).

### xyzdist Multiple Return Values

```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);
```

The xyzdist function demonstrates VEX's ability to return multiple values from a single function call.

### xyzdist Multi-Value Return

```vex
i@primid;
v@uv;
@dist;

@dist = xyzdist(1, @P, @primid, @uv);

@P = primuv(1, 'P', @primid, @uv);
```

The xyzdist() function demonstrates a powerful VEX pattern where a single function call can return multiple values through its parameters.

### Attribute Interpolation with primuv

```vex
@dist = xyzdist(1, @P, @primid, @uv);

v@c = primuv(1, 'P', @primid, @uv);
v@cd = primuv(1, 'Cd', @primid, @uv);
```

Uses xyzdist to find the closest primitive and UV coordinates on a source geometry, then uses primuv to interpolate position and color attributes from that source primitive at the found UV location.

### Find Closest Point on Geometry

```vex
@P = minpos(1, @P);
```

Uses minpos() to snap each point to the nearest position on the geometry in input 1.

### Animated Position with ID and Frame

```vex
v@P.y = f@id * (3.1415) * sin(i@Frame * 0.2) * (3.0, 0);
//op = curlnoise(s(1,1,1) * @Time * 0.2) * (3, 0, 9);
```

Modifies the Y position of points using their ID multiplied by pi and a sine wave based on frame number, creating an animated wave pattern.

### Fake Ambient Occlusion via DOT Product

```vex
@Cd = @dist;

int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```

Demonstrates creating a fake ambient occlusion effect by computing the dot product between a point's normal and the averaged normals of nearby points from a point cloud.

### Fake Ambient Occlusion with Point Clouds

```vex
int pc = pcopen(0, "P", @P, ch("maxdist"),
    chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```

Creates a fake ambient occlusion effect by opening a point cloud and comparing the averaged normals of nearby points to the current point's normal using a dot product.

### Ambient Occlusion with Fit

```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch('gamma'));
```

Creates ambient occlusion by opening a point cloud, computing the dot product between the current point's normal and the averaged normal from nearby points, then remapping the dot product range fro....

### Ambient Occlusion with Gamma Correction

```vex
int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, chi("gamma"));
```

This creates an ambient occlusion effect by sampling nearby normals using a point cloud, computing the dot product between the point's normal and the averaged nearby normals, then remapping the res....

### Ambient Occlusion with Gamma Control

```vex
int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch("gamma"));
```

This snippet creates an ambient occlusion effect by comparing the current point's normal with the averaged normals of nearby points using a point cloud.

### Point Cloud Normal Comparison

```vex
int pc = pcopen(0, "P", @P, ch('maxdist'), chi('numpoints'));
vector pcn = normalize(pcfilter(pc, "N"));
vector norm = normalize(@N);
float dot = dot(norm, pcn);
@Cd = fit(dot, -1, 1, 0, 1);
@Cd = pow(@Cd, ch('gamma'));
```

Opens a point cloud handle and filters the averaged normals from nearby points.

### Disconnected Code Conclusion

```vex
int pc = pcopen(0, "P", @P, ch("maxdist"), chi("numpoints"));
vector pos = normalize(jitter(pc, 'R'));
vector norm = normalize(nml);
@Cd = fit(den, -1, 1, 0, 1);
@Cd = fit(den, -1, 1, 0, 1);
@Cd = pow(@Cd, chf("gamma"));
```

This code snippet demonstrates disconnected operations that are not actively functioning in the scene setup.

### Nearpoints and Dot Product Color Mapping

```vex
int pts[] = nearpoints(0, "P", @P, ch('maxdist'), chi('numpoints'));
vector pos = point(0, pts[0], "P");
vector dir = normalize(@P - pos);
vector norm = normalize(chi('dir'));
float dot = dot(dir, norm);
@Cd = fit(dot, -1, 1, 0, 1);
```

This code finds the nearest point within a specified distance, calculates the direction vector from that point to the current point, then computes the dot product between this direction and a norma....

### Sine Wave Displacement with Channels

```vex
float d = length(@P);
d *= ch("y_scale");
d += @Time;
@P.y = sin(d);

@P *= @N;

@P += @N * ch("push");
```

Creates animated sine wave displacement by calculating distance from origin, scaling it with a channel parameter and time offset, then applying sine function to Y position.

### Animated Wave with Point Displacement

```vex
float d = length(@P);
d *= ch('y_scale');
d += @Time;
@P.y = sin(d);

@P += @N;

@P *= @N * ch('push');
```

Creates an animated wave effect by calculating distance from origin using length(), scaling and offsetting by time, then applying sine function to Y position.

### Animated Sine Wave Deformation

```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N*sin(d)*ch('wave_height');
```

Creates an animated sine wave deformation on geometry by calculating distance from origin, scaling it with a channel parameter, adding time for animation, then offsetting points along their normals....

### Wave Distortion with Distance

```vex
float d = length(@P);
d -= ch("v_scale");
d *= 6*@Time;
@P.y = @P.y*sin(d) *ch("wave_height");
```

Creates an animated wave distortion effect by calculating distance from origin, offsetting and scaling it with time, then applying a sine wave to the Y position.

### Creating Sine Waves with Length

```vex
float d = length(@P);
d *= ch("scale");
@P += @N * sin(d) * ch("wave_height");
```

Demonstrates creating wave patterns by calculating distance from origin using length(), scaling it with a channel parameter, then displacing points along their normals using a sine function.

### Length Function Distance Mapping

```vex
float d = length(@P);
v@d = ch("_scale");
@P *= ch("_scale");
@P += @N * sin(d) * ch("wave_height");
```

Demonstrates using the length() function to calculate distance from origin, storing it for use in subsequent deformations.

### Distance Clamping with Y Position

```vex
float d = length(@P);
@P.y = clamp(d, 0, 7);
```

Calculates the distance from each point to the origin using length(@P), then clamps that distance value between 0 and 7 and assigns it to the Y position.

### Negation Shorthand and Fit Function

```vex
float d = length(@P);
@P.y = fit(d, 1, 2, 1, 2);
```

Demonstrates using negation shorthand (-d instead of d * -1) for cleaner code when inverting distance values.

### Clamping Distance Values

```vex
float d = length(@P);
@P.y = clamp(d, 0, 3);
```

Calculates the distance from the origin for each point and uses the clamp function to constrain that distance value between 0 and 3, then assigns the clamped result to the y-component of the point ....

### Clamp and Fit Functions

```vex
float d = length(@P);
@P.y = fit(d, 0, 2, 0, 10);
```

Uses the fit() function to remap distance values from one range to another, demonstrating how to scale the y-position based on distance from origin.

### Fit Function Range Mapping

```vex
float d = length(@P);
@P.y = fit(d, 0, 5, 0, 10);
```

Demonstrates using the fit() function to remap values from one range to another.

### Fit and Clamp Range Control

```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
@P.y = fit(d, imin, imax, 0, 1);
```

Using the fit() function to remap distance values to a specific range, with channel references for dynamic parameter control.

### Fit and Clamp Range Remapping

```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
d = fit(d, imin, imax, 0, 1);
d = clamp(d, 0.5, 1);
@P.y = d;
```

Demonstrates combining fit() and clamp() functions to remap and constrain distance values.

### Fitting and Clamping with Channels

```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
d = fit(d, imin, imax, 1, 0);
d = clamp(d, 0.5, 1);
@P.y = d;
```

Demonstrates using fit() to remap distance values from a custom input range (controlled by channel parameters) to an output range of 1 to 0, then applying an additional clamp() to restrict the resu....

### Fit and Clamp Combination

```vex
float d = length(@P);
float lmin = ch('fit_in_min');
float lmax = ch('fit_in_max');
d = fit(d, lmin, lmax, 1, 0);
d = clamp(d, 0.5, 1);
@P.y = d;
```

Demonstrates combining fit() and clamp() functions to remap and constrain distance values.

### Chaining fit and clamp operations

```vex
float d = length(@P);
d = fit(d, 1, 2, 1, 0);
d = clamp(d, 0.5, 1);
@P.y = d;

float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
```

Demonstrates combining fit() to remap and invert a distance range, followed by clamp() to constrain values to a sub-range, then applying the result to point Y positions.

### Distance-based Y displacement with clamping

```vex
float d = length(@P);
d = fit(d, 0, 1, 1, 0);
d = clamp(d, 0.5, 1);
@P.y = d;
```

Calculates distance from origin, remaps the range inversely (far becomes near), then clamps values between 0.5 and 1.0 to limit the range, finally applying this to the Y position.

### Fit and Clamp Functions

```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
```

Demonstrates using fit() to remap values from one range to another and clamp() to constrain values within a minimum and maximum range.

### Fit and Clamp with Channel Refs

```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
float outmin = ch('fit_out_min');
float outmax = ch('fit_out_max');
d = fit(d, imin, imax, outmin, outmax);
@P.y = d;
```

Demonstrates using the fit() function to remap distance values from one range to another, then using clamp() to constrain values to a sub-range.

### Fit and Clamp with Channels

```vex
float d = length(@P);
float imin = ch("fit_in_min");
float imax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d = fit(d, imin, imax, outmin, outmax);
@P.y = d;
```

Calculates the distance from the origin using length(@P), then remaps that distance using the fit() function with channel-driven input and output ranges.

### Channel-Driven Fit Range

```vex
float d = length(@P);
float inmin = ch("fit_in_min");
float inmax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d = fit(d, inmin, inmax, outmin, outmax);
@P.y = d;
```

Creates channel references for all fit() function parameters, allowing interactive control of input and output ranges from the parameter interface.

### Channel-driven fit with UI parameters

```vex
float d = length(@P);
float imin = ch("fit_in_min");
float imax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d = fit(d, imin, imax, outmin, outmax);
@Cd.y = d;
```

Demonstrates creating a user interface for the fit function by exposing all input and output range parameters as channels.

### Remapping Values with Fit

```vex
float angle = ch("fit_in_min");
float inmin = ch("fit_in_min");
float inmax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
float d = fit(angle, inmin, inmax, outmin, outmax);
@P.y = d;
```

This example demonstrates using the fit() function to remap a value from one range to another, with channel references providing control over input and output ranges.

### Channel-driven fit remapping

```vex
float inmin = ch('fit_in_min');
float inmax = ch('fit_in_max');
float outmin = ch('fit_out_min');
float outmax = ch('fit_out_max');
v@P.y = fit(v@P.y, inmin, inmax, outmin, outmax);
```

Demonstrates using the fit() function to remap Y position values based on parameter-driven input and output ranges.

### Ramp-based displacement using distance

```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('my-rmp', d);
```

This code calculates the distance of each point from the origin, scales it with a channel parameter, and uses that scaled distance to sample a ramp parameter which then drives the Y position of eac....

### Ramp-driven Y displacement

```vex
float d = length(@P);
d *= fit(scale);
@P.y = chramp('myramp', d);
```

This code calculates the distance from the origin for each point, scales it using a fit operation, then uses that scaled distance to sample a custom ramp parameter and assign the result to the Y po....

### Using Ramp Parameters in VEX

```vex
float d = length(@P);
d = ch('scale');
@P.y = chramp('myramp', d);
```

This code uses a ramp parameter to control the Y position of points based on their distance from the origin.

### Ramp-Based Height Displacement with Velocity

```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
@v.y *= ch('height');
```

Uses distance from origin to sample a ramp parameter for vertical displacement.

### Ramp-Driven Displacement with Offset

```vex
float d = length(@P);
d *= ch('scale');
d += ch('offset');
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Uses distance from origin scaled by a parameter to sample a ramp, then applies that value to displace point positions vertically.

### Scaling distance with ramp and channels

```vex
float d = length(@P);
d *= ch('scale');
d = chramp('myramp', d);
@P.y = chramp('myramp', d);
```

This code calculates the distance of each point from the origin, scales it using a channel parameter, and then uses a ramp to remap those distance values to control the Y position of points.

### Scaling Ramp Output with Channel

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

This code calculates a distance value from the origin, modulates it with scale and time, then uses it to sample a ramp which drives the Y position.

### Vertical Displacement with Ramp and Time

```vex
float d = length(@P);
d *= ch('scale');
d += time;
@P.y = chramp('myramp', d);
@Cd = chramp('myramp', d);
```

Creates animated vertical displacement by calculating distance from origin, scaling it, adding time for animation, and using a ramp to control the Y position.

### Distance-based Height Animation with Ramps

```vex
float d = length(@P);
d *= ch('scale');
d -= $T;
d.y *= ch('Height');
d.y = clamp(d.y, 0, 1);
d.y = chramp('Height');
@Cd = ch('color');
@P.y -= ch('height');
```

Creates an animated effect based on point distance from origin, scaled and clamped to drive a height ramp lookup.

### Animated Ramp Displacement

```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
@P.y = chramp("myramp", d);
@P.y *= ch("height");
```

Creates an animated wave displacement effect by calculating distance from origin, scaling and animating it with @Time, then sampling a ramp parameter to drive vertical position.

### Animated Ramp Displacement with Time

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Creates an animated radial displacement effect by calculating distance from origin, subtracting time to create scrolling animation, and using a color ramp to drive Y-position displacement.

### Animated Ramp-Driven Displacement

```vex
float d = length(@P);
d *= ch('scale');
d += $T;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Creates an animated wave displacement by calculating distance from origin, scaling it, adding time to create motion, then using sine and fit to normalize the value for color ramp lookup.

### Animating Sine Waves with Ramps

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d,-1,1,0,1);
```

This example demonstrates animating a sine wave pattern by adding @Time to the distance calculation, creating ripple animation across a grid.

### Animating Grid with Ramp and Sin Wave

```vex
float d = length(@P);
d *= ch('scale');
d *= ch('width');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
```

Creates an animated wave pattern by calculating distance from origin, scaling it with channel parameters, applying a sine function, and remapping the result from the sine range (-1 to 1) to (0 to 1).

### Animating with sine wave

```vex
float d = length(@P);
d *= ch('scale');
d += @Frame;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
```

Creates animated wave pattern by calculating distance from origin, adding frame number for time evolution, applying sine function, and remapping the result from [-1,1] to [0,1] range.

### Animated ramp with time offset

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d,-1,1,0,1);
@P.y = chramp('my_ramp',d);
@P.y *= ch('height');
```

Creates an animated wave pattern by calculating distance from origin, scaling it with a parameter, adding time to animate, applying sine function, and using the result to sample a ramp for vertical....

### Animating Sine Wave with Frame

```vex
float d = length(@P);
d *= ch('scale');
d += @Frame;
d = sin(d);
d = fit(d,-1,1,0,1);
```

This code creates an animated sine wave pattern by calculating distance from origin, scaling it, adding the frame number for animation, then applying sine and remapping the result from -1,1 range t....

### Animated ramp-driven displacement

```vex
float d = length(@P);
d *= ch('scale');
d += @Frame;
d = sin(d);
d = fit(d,-1,1,0,1);
@P.y = chramp('my_ramp',d);
@P.y *= ch('height');
```

Creates an animated wave pattern by calculating distance from origin, adding frame number for animation, applying sine function, then using the result to lookup a color ramp value which drives Y-ax....

### Color Ramp with Time Animation

```vex
float d = length(@P);
d *= ch('scale');
d = @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp('myRamp', d);
@Cd.y *= ch('height');
```

Uses time-based sine wave animation to drive a color ramp lookup, sampling the ramp with a fitted sine value and modulating the green color channel.

### Animated Color Ramp with Time

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@Cd.y = chramp('mymap', d);
@Cd.y *= ch('height');
```

Creates an animated color effect by calculating distance from origin, scaling and offsetting it by time, then using that value to sample a color ramp and apply it to the green color channel.

### Animated radial wave with point offset

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = sin(d*ch('freq')/(@ptnum/100.0)*d);
@Cd *= ch('height');
```

Creates an animated radial wave pattern emanating from the origin by calculating distance from center, scaling and offsetting by time, then using sine function with point number offset and distance....

### Animated sine wave with time offset

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = sin(d * ch('freq')) * ch('height');
```

Creates an animated radial sine wave by calculating distance from origin, scaling it, subtracting time to create motion, and applying a sine function modulated by frequency and height parameters.

### Animated ramp displacement with time

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('myramp', d);
```

Creates an animated wave effect by calculating distance from origin, scaling it, subtracting time to create motion, and using a ramp parameter to control the vertical displacement.

### Ramp-driven Y displacement with offset

```vex
float d = length(@P);
d *= ch('scale');
d -= ch('offset');
@P.y = chramp('myramp', d);
@Cd.y = ch('height');
```

This snippet calculates distance from the origin, scales and offsets it, then uses a ramp parameter to drive vertical displacement of points.

### Radial ramp pattern with modulo

```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Creates a repeating radial pattern by calculating distance from origin, scaling it, and using modulo to create repeating bands from 0-1.

### Repeating Ramp Pattern

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Creates a repeating animated wave pattern by calculating distance from origin, scaling and animating it with time, then using modulo to create repetition.

### Sine Wave Pattern with Fit

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
```

Creates an animated radial sine wave pattern by calculating distance from origin, scaling and offsetting by time, applying sine function, then remapping the result from the sine range (-1 to 1) to ....

### Ramp-Driven Radial Displacement

```vex
float d = length(@P);
d *= ch('scale');
d += ch('height');
@P.y = chramp('myramp', d);
@Cd = ch('height');
```

Uses radial distance from origin to drive vertical displacement via a ramp parameter, with scaling and height offset controls.

### Ramp-driven radial displacement

```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
@P.y = chramp('myramp', d);
@Cd = chramp('height', d);
```

Creates a radial displacement pattern by computing distance from origin, scaling and wrapping it with modulo to create repeating rings, then using a ramp to drive vertical displacement and color.

### Ramp-driven height with channel offset

```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
@P.y += ch('height');
```

This code calculates the distance from the origin, scales it with a channel parameter, and uses that scaled distance to sample a ramp parameter that drives the Y position.

### Ramp Parameter Modulation

```vex
float d = length(@P);
d *= ch('scale');
@Cd = chramp('myramp', d);
@P.y = chramp('myramp', d);
```

This code calculates distance from origin using length(@P), scales it with a channel slider, then uses that scaled distance value to sample a ramp parameter.

### Animated Radial Wave with Ramp

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('myramp', d);
@N.y = ch('height');
```

Creates an animated radial wave effect by calculating distance from origin, scaling and animating it with time, then using a ramp to modulate the vertical position.

### Animated Wave Pattern with Ramp

```vex
float d = length(@P);
d *= ch("scale");
d -= g*time;
@P.y = chramp("myramp", d);
@P.y -= ch("Height");
```

Creates an animated radial wave pattern by calculating distance from origin, scaling and animating it over time, then using a ramp lookup to control the Y position.

### Ramp-Controlled Wave Animation

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@Cd.y = ch('height');
```

Creates an animated wave effect by calculating distance from origin, scaling and animating it with time, then using a ramp parameter to control the height displacement of points.

### Animated Ramp Height Displacement

```vex
float d = length(@P);
d -= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Creates an animated radial displacement effect by calculating distance from origin, offsetting it by scale and time parameters, then using that distance to sample a ramp channel which controls the ....

### Ramp Wave Shaping

```vex
float d = length(v@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Creates an animated wave pattern by using distance from origin as input to a ramp parameter, allowing the ramp curve to shape the wave form.

### Animated Ramp-Driven Waves

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@P.y = chramp('mymap', d);
@P.y *= ch('height');
```

Creates animated radial waves by calculating distance from origin, scaling and offsetting by time, then using modulo to create repeating patterns.

### Animated Waves with Ramp Control

```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
d %= 1;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("myRamp", d);
@P.y *= ch("height");
```

Creates animated wave deformations by calculating distance from origin, animating it with time, applying sine wave oscillation, and then using a ramp parameter to shape the wave profile.

### Animating Ramp with Time

```vex
float d = length(@P);
v@Cd = ch("color");
d = @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("myrang", d);
@P.y *= ch("height");
```

Uses the @Time global variable with sin() to create oscillating animation that drives a ramp lookup.

### Ramp-Driven Geometry Animation

```vex
float d = length(@P);
d = ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp('myramp', d);
@P.y = ch('height');
```

Demonstrates using a color ramp to drive vertical point displacement by calculating distance, applying sine wave transformation, and using chramp() to lookup values that control the Y position.

### Ramp and Distance Deformation

```vex
float d = length(@P);
d *= ch("scale");
d = abs(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("myram", d);
@P.y *= ch("height");
```

Creates a vertical deformation by calculating distance from origin, applying sine wave modulation, and using chramp() to lookup values from a ramp parameter.

### Ramps and Fit Range

```vex
float d = length(@P);
d *= ch('scale');
d += 1;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

This demonstrates using fit() to normalize a sine wave from its natural -1 to 1 range into 0 to 1, making it suitable for ramp sampling.

### Ramp-Driven Height Displacement

```vex
float d = length(@P);
d *= ch('scale');
d = clamp(d, 0, 1);
d *= sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Creates a radial displacement pattern by calculating distance from origin, applying sine wave modulation, and using a ramp parameter to control vertical height.

### Ramp Parameter Control

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```

Uses a ramp parameter to control point displacement height by computing radial distance, applying sine wave modulation, and remapping the sine output (-1 to 1) to valid ramp lookup range (0 to 1).

### Animated Height Displacement with Ramps

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('mycramp', d);
@P.y *= ch('height');
```

Creates an animated ripple effect by calculating distance from origin, modulating it with sine waves over time, and using a ramp parameter to control vertical displacement.

### Animated Sine Wave with Ramp

```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```

Creates an animated sine wave pattern by calculating distance from origin, applying time offset, and mapping the sine result through a ramp parameter for vertical displacement.

### Fit and Ramp for Wave Displacement

```vex
float d = length(@P);
d *= ch("scale");
d -= sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```

This code creates a radial wave displacement by calculating distance from origin, applying sine wave modulation, and remapping the result through a ramp parameter for artistic control.

### Sine Wave Deformation with Ramps

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d += 1;
@P.y = chramp('myrang', d);
@Cd.y = chr('height');
```

Creates a radial sine wave deformation by calculating distance from origin, scaling it, applying sine, then using that value to drive a height ramp for position and a color ramp for the green channel.

### Animated Radial Wave with Ramp

```vex
float d = length(@P);
d *= ch("scale");
d += $T;
d += sin(d);
d += 1;
@P.y = chramp("myRamp", d);
@P.y *= ch("height");
```

Creates an animated radial wave pattern by calculating distance from origin, adding time and sine wave modulation, then using a ramp to control vertical displacement.

### Sine wave color ramp pattern

```vex
float d = length(@P);
d *= ch("scale");
d = fit(d, 0, 1, 0, 1);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp("myRamp", d);
@P.y *= ch("height");
```

Creates a radial sine wave pattern by calculating distance from origin, applying a sine function, and mapping the oscillating values through a color ramp.

### Sine Wave Color Ramp

```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp("myRamp", d);
@Cd.y += ch("height");
```

Creates a radial sine wave pattern based on distance from origin, scales it with a channel parameter, then fits the sine output from [-1,1] to [0,1] range to sample a color ramp for the green channel.

### Animated Color Ramp with Sine Wave

```vex
float d = length(@P);
d *= ch('scale');
d *= @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp('myRamp', d);
@P.y *= ch('height');
```

This creates an animated sine wave pattern by calculating distance from origin, scaling it by time, and fitting the sine result to 0-1 range for use with a color ramp.

### Ramp-driven height and color mapping

```vex
float d = length(@P);
d *= ch('scale');
d += sin(d);
d = fit(d, 1, 3, 0, 1);
@P.y = chramp('myRamp', d);
@Cd.y = chramp('myRamp', d);
@Cd.y *= ch('height');
```

This code calculates a distance-based value from the origin, applies scaling and sine wave modulation, then remaps it to 0-1 range using fit().

### Sine Wave Color Ramp

```vex
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp("my_ramp", d);
@P.y += ch("height");
```

Creates animated sine wave patterns by calculating distance from origin, animating it with time, and mapping the sine wave result through a fit function to normalize values between 0 and 1.

### Ramp-Shaped Sine Wave Color

```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp("myRamp", d);
@Cy *= ch("height");
```

Creates a radial sine wave pattern based on distance from origin, then uses a color ramp to map the sine values to colors, allowing for custom wave shaping.

### Ramp-driven height displacement

```vex
float d = length(@P);
d = fit(d, 0, chf('scale'), 0, 1);
d = sin(d * chf('freq'));
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y += chf('height');
```

Creates a radial displacement pattern by calculating distance from origin, applying sine wave oscillation controlled by frequency parameter, and using a ramp to modulate the final height displacement.

### Ramp Parameters with Distance Field

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```

Creates a radial wave pattern by calculating distance from origin, applying sine functions for wave oscillation, then using fit() to normalize the result to 0-1 range before sampling a ramp parameter.

### Sine Wave Height with Ramp Control

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('mycmap', d);
@P.y *= ch('height');
```

Creates an animated sine wave pattern by computing distance from origin, adding time, and applying a sine function.

### Normalizing Values with Fit

```vex
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp("my ramp", d);
@Cd.x = chf("height");
```

This code demonstrates normalizing sine wave values from their natural range of -1 to 1 into a 0 to 1 range using the fit function.

### Normalizing Values

```vex
float a = chf("scale");
v@Cd = @P / chv("height");
v@Cd = chramp("color_ramp", @Cd);
```

Demonstrates normalizing position values by dividing by a height parameter to create a 0-1 range suitable for color ramps.

### Ramp-Driven Height Displacement

```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d) * ch("height");
```

This code creates a radial wave pattern by calculating distance from origin, applying sine wave distortion, normalizing the result with fit(), and using a ramp parameter to drive vertical displacement.

### Sine Wave with Ramp Mapping

```vex
float d = length(@P);
d *= ch('scale');
f@d = d;
d = sin(d);
d = fit(d,-1,1,0,1);
@P.y = chramp('my-map',d);
@P.y *= ch('height');
```

Creates a radial sine wave pattern by calculating distance from origin, applying sine function, then fitting the result to 0-1 range.

### Animated radial ripple effect

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@P.y = chramp('myramp', d);
@Cd = chramp('height', d);
```

Creates an animated radial ripple effect by calculating distance from origin, scaling it, subtracting time for animation, and using modulo to create repeating waves.

### Compound Assignment Operators

```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
@P.y = chramp('my_ramp', d);
@Cd = chramp('height', d);
```

Demonstrates compound assignment operators like += and *= as shorthand for operations.

### Ripple Effect with Distance Scaling

```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = set(d, 0, d);
@P.y *= ch("height");
```

Creates a ripple pattern by calculating distance from origin, applying sine wave modulation, and mapping the result to color.

### Animated Radial Sine Wave

```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d = sin(d);
d = fit(d, -1, 0, 0, 1);
d = chramp('my_control_ramp', d);
@P.y += ch('height');
```

Creates an animated radial sine wave pattern by calculating distance from origin, scaling it, subtracting time for animation, applying sine function, and remapping the result through a ramp parameter.

### Distance-Based Color Ramp

```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp("my_ramp", d);
@P.y *= ch("height");
```

Creates a distance-based color pattern by calculating the length from the origin, applying a sine wave pattern, and mapping the result through a color ramp.

### HSV Color from Distance Ripples

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d *= fit(d, -1, 1, 0, 1);
@Cd = hsvtorgb(set(d, 1, 1));
@P.y *= ch('height');
```

Creates concentric ripple patterns by calculating distance from origin, applying sine wave distortion, and mapping the result to HSV color values.

### Distance-Based Ripple Pattern

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = vector(d);
@P.y *= ch('height');
```

Creates a radial ripple pattern by calculating distance from origin, applying sine wave modulation, and remapping the result to color.

### Distance-based point displacement

```vex
float d = length(@P);
d *= ch('scale');
f@d = d;
d = sin(d);
d *= fit(d, -1, 1, 0, 1);
@P *= (1 + d * ch('amount'));
@Cy += ch('height');
```

Creates a ripple-like displacement effect by calculating distance from origin, applying sine wave modulation, and using the result to scale point positions.

### Ramp-driven wave deformation

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
d = chramp('height', d);
@P.y *= d;
```

Creates a wave pattern based on distance from origin, then uses a ramp parameter to control the height deformation.

### Sine Wave Color Pattern

```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d *= fit(d, -1, 1, 0, 1);
@Cd = pal(d, d, d, d);
@P.y *= ch('height');
```

Creates a radial sine wave pattern using distance from origin, applies color using a palette function, and scales vertical position.

### Modulo Division Patterns

```vex
float d = length(@P);
v@Cd = ch('scale');
d *= 3;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
d = chramp('test', d);
@Cd *= ch('height');
```

Creates color patterns using distance-based modulo division and ramp remapping.

### Channel-Driven Displacement

```vex
float d = length(@P);
d *= ch("scale");
@P.y = d;
```

Calculates the distance from the origin using length(@P), multiplies it by a channel parameter called 'scale', and displaces points vertically by setting @P.y to that scaled distance value.

### Creating Stepped Distance Values

```vex
float d = length(@P);
d *= ch("scale");
float f = ch("factor");
d /= f;
d = trunc(d);
d *= f;
@P.y = d;
```

This technique creates stepped (quantized) values from smooth distance calculations by dividing the scaled distance by a factor, truncating to remove decimals, then multiplying back by the factor.

### Using trunc() for value scaling

```vex
float d = length(@P);
d *= ch('scale');
float factor = ch('factor');
@P.y = d;
d = trunc(d);
@P.y = d;
```

Demonstrates using the trunc() function to remove decimal components from scaled distance values.

### Distance Scaling with Y Position

```vex
float d = length(@P);
d *= ch('scale');
@P.y = d;
```

This code calculates the distance of each point from the origin using length(), scales it by a channel parameter, and assigns the result to the Y position.

### Quantizing Data with Truncate

```vex
float d = length(@P);
d *= ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

This technique demonstrates quantizing continuous data by using the truncate function (or ramp) to create stepped values from smooth distance calculations.

### Quantizing Distance with Scale Factor

```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
d *= f;
@P.y = d;
```

This code quantizes the Y position of points based on their distance from the origin.

### Truncating Distance Values

```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
d *= f;
@Cy = d;
```

This code calculates the distance from the origin using length(@P), scales it with channel parameters, then uses trunc() to quantize the distance value into discrete steps controlled by the 'factor....

### Stepped Ramp Visualization

```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
@Cd.x = d;

d = length(@P);
// ...
```

Demonstrates two methods for creating stepped color patterns: manually using truncation and division to create discrete steps, and using a custom ramp parameter to achieve similar results.

### Stepped Ramps with Distance

```vex
float d = length(@P);
d *= ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@Cd.y = d;
```

Demonstrates creating stepped visual effects by calculating distance from origin, scaling it, and using a ramp parameter with truncation to create discrete bands.

### Distance-based Color and Position

```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
@Cd.r = d;
d /= f;
@Cd.r = d;
// ...
```

This code calculates the distance from the origin using length(@P), scales and divides it by channel-driven parameters, then applies truncation to create stepped values.

### Stepped Ramp with Truncation

```vex
float d = length(@P);
d *= ch("pre_scale");
d = chramp("my_stepped_ramp", d);
d *= ch("post_scale");
@P.y = d;
```

Demonstrates creating stepped values by using truncation operations on distance-based calculations.

### Value Quantization with Modulo

```vex
float d = length(@P);
d *= ch('scale');
@Cd = chramp('ramp', d);

float f = ch('frequency');
d /= f;
d *= trunc(d);
d %= f;
// ...
```

Demonstrates quantizing continuous values into stepped functions by dividing distance by a frequency parameter, truncating to remove fractals, then using modulo to create repeating bands.

### Stepped Quantization with Ramps

```vex
float d = length(@P);
v@Cd = set(d);
d = chramp('my_stepped_ramp', d);
d *= d;
d = trunc(d);
@P.y = d;
```

This code creates a stepped quantization effect by calculating distance from origin, passing it through a stepped ramp, squaring the result, and then truncating to integer values.

### Ramp-Based Stepped Effect

```vex
float d = length(@P);
d /= 10;
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

Creates a stepped displacement effect by normalizing point distance from origin, sampling a stepped ramp parameter, and applying the result to vertical position.

### Ramp-driven Height Displacement

```vex
float d = length(@P);
d *= ch('prc_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

Calculates distance from origin and uses it to lookup values from a stepped ramp parameter, applying pre and post scaling controls.

### Stepped Ramp Distance Displacement

```vex
float d = length(@P);
d += ch('sss_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

Displaces point Y positions based on distance from origin.

### Pre-scale and Post-scale with Ramps

```vex
float d = length(@P);
d *= 10;
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

Creates a terrain-like height displacement by calculating distance from origin, applying a pre-scale multiplier, sampling a stepped ramp parameter, then applying a post-scale channel parameter to c....

### Stepped Ramp for Height Displacement

```vex
float d = length(@P);
d *= chf('amplitude');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

Calculates distance from origin and uses it to sample a stepped ramp parameter, creating terraced height displacement on geometry.

### Stepped Height Functions

```vex
float d = length(@P);
d *= chf("prescale_height", 0);
d += chf("post_scale");
@P.y = d;
```

Creates stepped or striated height variations by calculating distance from origin and applying channel-based scaling.

### Channel Parameters and Clamping

```vex
float d = length(@P);
d = ch('pre_scale');
d = clamp(d, ch('post_scale'), d);
d += ch('post_scale');
@Cd = d;
```

This code demonstrates controlling values using channel parameters with ch() function and the clamp() function to constrain values within a range.

### Remapping Values with Ramps

```vex
float d = length(@P);
d = ch('pre_scale');
d -= chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

This code demonstrates a common VEX workflow of taking values through different ranges and transformations.

### Reading Ramp Parameters

```vex
float ramp_val;
vector ramp_clr;
float d = chf('post_scale');
ramp_val = chramp('my_stepped_ramp', d);
@Cd = ramp_val;
```

This example demonstrates reading channel parameters and evaluating a ramp parameter.

### Distance-based color with sine wave

```vex
float d = length(@P);
d *= chf('scale');
@Cd.r = sin(d);
```

Calculates the distance from origin using length(@P), scales it with a channel parameter, and assigns a sine wave pattern to the red color channel.

### Distance-based color with sine wave

```vex
float d = length(@P);
d *= ch('scale');
@Cd.r = sin(d);
```

Calculates the distance from the origin for each point, scales it using a channel parameter, and applies a sine function to create an oscillating red color component.

### Sine Wave Concentric Rings

```vex
float d = length(@P);
d *= ch('scale');
@Cd = @P;
@Cd.r = sin(d);
```

Creates concentric ring patterns by calculating distance from origin, scaling it with a channel slider, and applying a sine function to the red color channel.

### Distance-Based Color Rings

```vex
float d = length(@P);
d *= ch('scale');
@Cd = d;
@Cd.r = sin(d);
```

Creates concentric color rings by calculating distance from origin using length(@P), scaling it with a channel parameter, and applying sine function to the red channel to produce oscillating color ....

### Sine Wave Color Patterns

```vex
float d = length(@P);
d *= ch("scale");
@Cd = d;
@Cd.r = sin(d);
```

Creates a radial color pattern by calculating the distance from the origin, scaling it with a channel parameter, and applying a sine function to the red color component.

### Sine wave geometry displacement

```vex
float d = length(@P);
d *= ch("scale");
@Cd = d;
@P.y = sin(d);
```

Calculates distance from origin, scales it by a channel parameter, assigns the distance to color, then uses the sine of that distance to displace points vertically.

### Sine Wave Color and Position

```vex
float d = length(@P);
d *= ch('scale');
@Cd = @P;
@P.y = sin(d);
```

Calculates distance from origin using length(@P), scales it with a channel parameter, and applies a sine wave to the Y position based on this distance.

### Sine Wave Displacement on Y Position

```vex
float d = length(@P);
d *= ch("scale");
@P.y = sin(d);
```

Displaces points vertically using a sine wave based on their distance from the origin.

### Applying Sine Wave to Position

```vex
float d = length(@P);
d *= ch('scale');
@P.y = sin(d);
```

This code calculates the distance from the origin for each point, scales it using a channel parameter, and applies a sine function to the Y position.

### Sine Wave Displacement on Y-Axis

```vex
float d = length(@P);
d += ch("scale");
@P.y = sin(d);
```

Calculates the distance from the origin using length(@P), adds a channel value to offset the wave pattern, then applies a sine function to displace geometry along the y-axis.

### Distance-Based Color and Normal Modification

```vex
float d = length(@P);
d *= ch("scale");
@Cd = sin(d);
@N.y = sin(d);
```

Calculates distance from origin using length of position vector, scales it with a channel parameter, then uses sine function to create cyclic patterns in color and vertical normal component.

### Pseudo Attributes and Point Primitives

```vex
float d = len(v@P - p1(0, @primnum, 0));
s@ry = sin(d);
```

Demonstrates using pseudo attributes and the p1() function to calculate distance from point position to primitive center.

### Vertex Attribute Manipulation with Distance

```vex
float d = length(@P);
d *= ch('scale');
@Cry = sin(d);
```

Calculates the distance from the origin for each vertex position, scales it by a channel parameter, and assigns a sine wave pattern to a custom vertex attribute.

### Distance to Closest Point

```vex
vector pos = minpos(1, @P);
@d = distance(@P, pos);
@d = ch("scale");
@Cd = @d;
@Cd.r = sin(@d);
```

Uses minpos() to find the closest point on input 1, then calculates the distance from current point to that position.

### Distance and Color Mapping

```vex
float d = distance(v@P, @P);
d *= chf("scale");
@Cd = d;
@Cd.r = sin(d);
```

Calculates the distance from each point to itself (which is zero, likely setup for a xyzdist() follow-up), scales it by a channel parameter, assigns the distance to color, and modulates the red cha....

### Distance and Color Assignment

```vex
int d = length(@P);
@Cd = ch("scale") * d;
@Cd = @P;
@Cd.r = sin(d);
```

This snippet demonstrates basic distance calculations and color manipulation.

### Distance to Surface Point

```vex
vector pos = point(1, @P);
float d = distance(@P, pos);
d *= chf("M1");
@Cd.r = sin(d);
```

Uses the point() function to find the closest point on a reference surface geometry (input 1) to the current point position, then calculates the distance between them.

### Type Casting and Attribute Assignment

```vex
int id = length(@P);
v@Cd = set(id*10.5);
s@Cd = @j;
@Cd.r = sin(@id);
```

Demonstrates various attribute type declarations and assignments in VEX.

### Finding Closest Point with minpos

```vex
vector pos = minpos(0, @P);
```

Declares a vector variable to store the position of the closest point found using the minpos function.

### Finding Closest Surface Position

```vex
vector pos = minpos(1, @P);
```

The minpos() function finds the closest position on the surface of the second input geometry (input 1) to the current point's position.

### Distance to Closest Surface Point

```vex
vector pos = minpos(1, @P);
float d = distance(pos, @P);
d *= ch("scale");
@Cd = sin(d);
```

Uses minpos() to find the closest point on input geometry (input 1), then calculates the distance from the current point to that closest position.

### Distance to Closest Surface Point

```vex
vector pos = minpos(1, @P);
float d = distance(@P, pos);
d *= ch("scale");
@Cd = sin(d);
```

Uses minpos() to find the closest point on input geometry 1, then calculates the distance from the current point to that closest position.

### Distance-based color with channel scaling

```vex
vector pos = minpos(1, @P);
float d = distance(@P, pos);
d *= chf("scale");
@Cd = d;
@Cd.r = sin(d);
```

Calculates the distance from each point to the nearest point in the second input using minpos(), scales that distance by a channel parameter, and uses it to set color values with a sine wave modula....

### Distance-Based Color with Sine Wave

```vex
vector pos = minpos(1, @P);
float d = distance(@P, pos);
d *= ch('scale');
@Cd = d;
@Cd.r = sin(d);
```

Finds the closest point in the first input using minpos(), calculates distance to it, scales the result with a channel parameter, then initializes color to the distance value and applies a sine wav....

### Distance to Secondary Input Geometry

```vex
vector pos = minpos(1, @P);
float dist = distance(@P, pos);
@Cd = chramp("calc", dist);
@Cd.r = sin(dist);
```

Calculates the distance from each point to the closest point on a secondary input geometry using minpos().

### Distance and Sine Wave Coloring with MinPos

```vex
vector pos = minpos(1, @P);
float d = distance(@P, pos);
@s = ch("scale");
@Cd = d;
@Cd.r = sin(d);
```

Uses minpos() to find the closest point on the second input geometry, calculates distance to it, and applies a sine wave to the red channel for oscillating color patterns.

### Distance-based Color with minpos

```vex
vector pos = minpos(1, @P);
float d = distance(@P, pos);
d /= ch("scale");
@Cd = d;
@Cd.r = sin(d);
```

Uses minpos() to find the closest point on input 1, then calculates distance from current point to that position.

### Distance-based coloring using minpos

```vex
vector pos = minpos(1, @P);
float d = distance(pos, @P);
f@r = ch('scale');
@Cd = d;
@Cd.y = sin(d);
```

For each point on a grid, this code finds the closest position on another geometry (input 1) and stores it in a variable.

### Distance-based color using minpos

```vex
vector pos = minpos(1, @P);
float d = distance(@P, pos);
float s = ch('scale');
@Cd = d;
@Cd.g = sin(d);
```

For each point on the grid, finds the closest position on the second input geometry (the pig) and stores it in a vector variable.

### Distance-based color and wind

```vex
vector pos = v@opinput1_P;
float d = distance(@P, pos);
f@scale = d;
@Cd = d;
v@v = v@wind * d;
```

Demonstrates reading position from a second input, calculating distance from current point to that position, and using the distance value to drive both color and a wind-scaled velocity vector.

### Distance-Based Point Displacement

```vex
int pt = nearpoint(1, @P);
vector pos = point(1, "P", pt);
float d = distance(@P, pos);
@P.y = d;
```

This code finds the nearest point from the second input to each point on the first input, calculates the distance between them, and uses that distance value to displace the Y-position of each point.

### Reading Quaternion Point Attributes

```vex
vector p1 = swlerpquat.p1;
vector cd1 = swlerpquat.Cd1;

@P = p1;
@Cd = cd1;
```

This code reads position and color attributes from another point referenced by the swlerpquat variable (likely from a nearpoint or similar lookup), then assigns those values to the current point's ....

### Curlnoise Color Animation

```vex
@Cd = 0;
@Cd.x = curlnoise(@P * chv('fancyscale')).g * @Time;
```

Uses curlnoise to animate point color by extracting the green channel (g component) of the curl noise result and multiplying it by time, then assigning it to only the red color channel.

### Curl Noise Function Arguments

```vex
v@Cd = curlnoise(@P*chv('fancyscale'))*0.5+0.5;
```

This demonstrates how curl noise evaluates its input argument as a single expression before processing it.

### Curl Noise Color with Channel

```vex
@Cd = curlnoise(@P * cv('fancyscale') + @Time);
```

Uses curl noise to generate a color based on position scaled by a custom channel parameter and animated with time.

### Curlnoise Single Component Assignment

```vex
@Cd = 0;
@Cd.x = curlnoise(@P * chv('fancyscale') + @Time);
```

Demonstrates extracting a single component from curlnoise by first zeroing the color attribute, then assigning only the x component of the divergence-free vector field to create a grayscale noise p....

### Curlnoise Color Components

```vex
v@Cd = vector(0);
v@Cd.x = curlnoise(@P * chv('fancyscale') + @Time).x;
```

This code demonstrates extracting the x component from curlnoise to drive color values.

### Color component access methods

```vex
@Cd = @Cd;
@Cd.r = curlnoise(@P * chv('fancyscale') + @Time);
@Cd.x = curlnoise(@P * chv('fancyscale') + @Time);
```

Demonstrates that color vector components can be accessed using both .r/.g/.b and .x/.y/.z notation interchangeably.

### Curlnoise Color Animation

```vex
@Cd.x = curlnoise(@P * chv('fancyscale')) * @Time;
```

Animates the red color channel using curlnoise driven by point position and a UI scale parameter, multiplied by the current time.

### Curl Noise Color Animation

```vex
@Cd = 0;
@Cd.x = curlnoise(@P * chv("fancyscale")) * @Time;
```

Creates animated color by using curl noise to drive the red color channel over time.

### Curlnoise with Time Animation

```vex
@Cd = @P;
@Cd.r = curlnoise(@P * chv('fancyscale') + @Time);
```

Assigns color to points by using curlnoise driven by animated position.

### Animated Curl Noise Color

```vex
@Cd = @P;
@Cd.x = curlnoise(@P * chv('fancyscale') + @Time);
```

Sets color based on position, then animates the red channel using curl noise driven by scaled position and time.

### Cross Product to Recalculate Normal

```vex
vector tmp = cross(@N, {0,1,0});
@N = cross(tmp, tmp);
```

Demonstrates the right-hand rule by computing a temporary vector from crossing the normal with the up vector, then crossing that result with itself to recalculate the normal.

### Ramp-driven displacement with bbox

```vex
vector bbox = relpointbbox(0, @P);
float i = chramp("inflate", bbox.y);
@P += @N * i;
```

Uses a ramp parameter to control displacement strength based on the point's relative Y position in the bounding box.

### Relative Bounding Box Scaling

```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
// ...
```

Uses relpointbbox to get normalized (0-1) bounding box coordinates for each point, making position-based effects scale-independent.

### If-Else Color Assignment

```vex
float d = dot(@N, {0,1,0});
if(d > ch('cutoff')){
    @Cd = {1,1,1};
} else {
    @Cd = {1,0,0};
}
```

Uses an if-else statement to explicitly assign white color when the dot product exceeds the cutoff threshold, and red color otherwise.

### Floating-Point Precision and Conditionals

```vex
float foo = 0;
float bar = sin(@P);

if(foo == bar) {
    @Cd = {1,1,0};
} else {
    @Cd = {1,0,0};
}
```

Demonstrates floating-point precision issues when comparing calculated values.

### Floating Point Precision Errors

```vex
float foo = 0;
float bar = sin(@P);

if(foo == bar) {
    @Cd = {0,1,0};
} else {
    @Cd = {1,0,0};
}
```

Demonstrates a floating point precision error where comparing sin(@P) to zero using == fails because floating point calculations can produce values extremely close to zero (like 0.00000087) but not....

### Floating Point Epsilon Comparison

```vex
float foo = 1.251;
float bar = 1.251;

if(abs(foo - bar) < 0.00001) {
    @Cd = {0,1,0};
} else {
    @Cd = {1,0,0};
}
```

Demonstrates epsilon testing for comparing floating point numbers, using a small tolerance value (0.00001) instead of direct equality to account for floating point precision errors.

### Code Formatting with Variables

```vex
float a = length(@P)*2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (a > b){
    @Cd = {1,0,0};
}
```

Demonstrates using variables to improve code readability by storing complex calculations in named variables 'a' and 'b' before comparison.

### Code Formatting with Variables

```vex
float a = length(@P)^2 + @ptnum % 5;
float b = dot(@N, {0,1,0}*@Time);
if( a > b){
    @Cd = {1,0,0};
}
```

Demonstrates cleaner code formatting by extracting complex conditional expressions into named variables.

### If Statement Curly Brace Styles

```vex
float a = length(@P) * 2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (a > b){
    @Cd = {1,0,0};
}
```

Demonstrates two common code formatting styles for if statements: curly braces on the same line versus on separate lines.

### If statement conditional coloring

```vex
float s = length(v@P) * 2 + @ptnum % 5;
float b = dot(@N, {0,1,0}) * @Time;

if (s > b){
    @Cd = {1,0,0};
}
```

Demonstrates conditional coloring using an if statement that compares two computed values: one based on position length and point number modulo, and another based on normal direction dot product wi....

### Nearpoints Array Manual Processing

```vex
int pts[];
int pt;
float d;
vector pos;
vector col;

d = 0;
pt = pts[0];
// ...
```

Demonstrates manually processing each point in a nearpoints array by explicitly accessing pts[0] and pts[1] individually, calculating distance, fitting values, and accumulating color contributions.

### Fit and Sine Wave Deformation

```vex
v = fit(0, ch("radius"), 1, 0);
@P.y = sin(v) * 0.2;
```

Uses fit() to remap a value from 0 to a channel reference into a 0-1 range, then applies a sine wave to the Y position with a small amplitude.

### Multi-Point Ripple Accumulation

```vex
v@pos = point(1, 'P', @ptnum);
f@d = distance(@P, v@pos);
v@w = f@d * ch('freq');
v@w -= @Time * ch('speed');
v@w = sin(v@w);
v@w *= fit(f@d, 0, ch('radius'), 1, 0);
@P.y = v@w;

// ...
```

Demonstrates the critical difference between assignment (@P.y =) and accumulation (@P.y +=) when applying multiple ripple effects.

### Voronoi Cell Ripple Blending

```vex
int pt = pt3[];
vector pos = point(1, 'P', pt);
float d = distance(@P, pos);
float w = d * ch('freq');
w = @Time * ch('speed');
w = sin(w);
w = ch('amp') * w;
w = fit(w, -1, 1, ch('radius'), 1, 0);
// ...
```

Creates ripple effects across Voronoi cell boundaries by sampling neighboring cell points and applying distance-based sine waves.

### Multiple Point Ripple Blending

```vex
int pt = pts[i];
vector pos = point(0, 'P', pt);
float d = distance(@P, pos);
float w = d * ch('freq');
w += @Time * ch('speed');
float s = sin(w);
w = s * ch('amp');
w *= fit(d, 0, ch('radius'), 1, 0);
// ...
```

Creates blended ripple effects from multiple source points by calculating distance-based sine waves that fade out based on a radius parameter.

### For Loop Over Point Array

```vex
int i;

for(i=1; i<11; i+=1) {
    @a = i;
}

for(i=0; i<len(pts); i++) {
    pt = pts[i];
// ...
```

Demonstrates using a for loop to iterate over an array of points as an alternative to foreach.

### For Loop with Curl Noise

```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i = 0; i < 6; i++) {
// ...
```

Sets up a for loop to iterate 6 times, calculating a curl noise offset for each iteration.

### Setting Scale Vector with Set Function

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

Demonstrates setting a vector attribute using the set() function instead of curly brace notation.

### Animated scaling with time and distance

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

Creates animated scaling based on distance from origin and time.

### Color ramp from distance values

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

This code calculates an animated distance value using sine waves, flattens geometry to the ground plane by setting @P.y to 0, then remaps the distance value from 0-1 and uses it to sample a color r....

### Color ramp with vector cast

```vex
float min, max, d, t;
min = ch("min");
max = ch("max");
t = @primnum * ch("speed");
d = length(@P);
d = d * ch("frequency");
@P.y = t;
@Cd = fit(sin(d), -1, 1, min, max);
// ...
```

Uses a color ramp parameter to drive point color based on distance from origin.

### Color ramp from distance with fit

```vex
float min, max, d, t;
min = ch("min");
max = ch("max");
t = @primnum * ch("speed");
d = length(@P);
d = d - t;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp("color", d));
```

Creates animated color based on point distance from origin, using channel parameters for min/max range and speed.

### Color Ramp with Vector Cast

```vex
float d = ch('frequency');
d += @Time;
float min = chf('min');
float max = chf('max');
float f = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), min, max, d);
@P.y += d;
d = fit(d, min, max, 0, 1);
// ...
```

Demonstrates using vector() cast on chramp() to create a color ramp instead of a float ramp.

### Color Ramp with Vector Cast

```vex
float d = chf('frequency');
float min = chf('min');
float max = chf('max');
d = fit(sin(d), -1, 1, min, max);
@scale = fit(d, min, max, 0, 1);
@P.y -= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```

Uses vector() cast on chramp() to convert a float ramp parameter into a color ramp, which tells Houdini to create a color-based ramp interface rather than a spline-based one.

### Color Ramp with Sine Wave

```vex
vector4 wrangler_pointwrangler1
{
    float frequency = 3;
    float d = @P.y;
    d = fit(sin(d * frequency), -1, 1, 0, 1);
    @Cd = vector(chramp("x", d));
}
```

Creates a color gradient across geometry by using a sine wave to modulate the Y position, fitting the result to a 0-1 range, and sampling a color ramp.

### Animating Up Vector for Copy Orientation

```vex
v@up = {0,0,1};

v@up = set(sin(@Time), 0, cos(@Time));
```

Creates an animated up vector that rotates around the Y axis using sine and cosine of @Time.

### Animating Up Vector with Sine

```vex
v@up = set(sin(@Time), 0,
```

Begins defining an animated up vector using the set() function with sin(@Time) for the X component to create rotation over time.

### Time offset by point number

```vex
float t = @Time + @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));
```

Creates a time variable offset by point number to produce staggered rotation animations across points.

### Time-based rotation with offset

```vex
float t = @Time * 0.1 + @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));

// With channel reference
float t = @Time * 0.1 + @ptnum * CH("offset");
v@up = set(sin(t), 0, cos(t));

// Distance-based offset
// ...
```

Creates time-based rotation using sine and cosine for the up vector, with progressive offset added via point number or distance from origin.

### Animated Y displacement with up vector

```vex
float d = length(@P);
float t = @Time + d*ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Calculates a time-varying Y displacement based on distance from origin, where each point oscillates at different phases determined by its distance.

### Distance-Based Wave Animation

```vex
float d = length(@P);
float t = @Time * d * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates an animated wave effect where each point's motion is influenced by its distance from the origin.

### Animated Wave Displacement with Up Vector

```vex
float d = length(@P);
float blob = @Time + d * chf('offset');
v@up = set(sin(blob), 0, cos(blob));
@P.y += sin(blob * 2) * 0.5;
```

Creates an animated wave displacement by combining time and distance from origin.

### Instance Orientation with Up Vector

```vex
float d = length(@P);
float t = @Time * d - d * chf('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Demonstrates animating instance orientation by setting the @up vector using time-based trigonometric functions, creating rotating instances.

### Animating up vector for instances

```vex
float d = length(@P);
float t = @Time * d * chf('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates animated dancing instances by computing a time-based offset from point distance, then using sine and cosine to rotate the up vector in a circular pattern while simultaneously offsetting poi....

### Animating up vector for instance orientation

```vex
float d = length(@P);
float t = @Time*ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Demonstrates animating an up vector for controlling instance orientations using trigonometric functions.

### Animated curve on circle

```vex
float d = length(@P);
float t = @Time * (1-d/ch('offset'));
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates an animated wave effect on a circular path by calculating distance from origin and using it to offset the time parameter.

### Animated Up Vector with Y Offset

```vex
float d = length(@P);
float t = @Time * 2 * (1-'offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```

Creates an animated rotation using a custom up vector and vertical displacement.

### Quaternion from Axis Vector

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis = @orient;

@orient = quaternion(axis);
```

Creates a quaternion rotation from an axis vector by reading a channel parameter, normalizing it, and converting it to a quaternion stored in the @orient attribute.

### Quaternions with Radians Issue

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis = {0, 1, 0};

@orient = quaternion(axis);
```

Creates an orientation quaternion from an axis vector, demonstrating a common pitfall where the quaternion() function expects rotation angles in radians, not degrees.

### Creating Orientation from Normal and Up

```vex
vector @orient = quaternion(maketransform(@N, @up));
```

Converts the point's normal (@N) and up vector (@up) into an orientation quaternion using maketransform to create a transformation matrix, then converts that matrix to a quaternion stored in the @o....

### Matrix to Quaternion Conversion

```vex
matrix3 m = ident();
@orient = quaternion(m);

@orient = {0,0,0,1};

vector rot = radians(chv('euler'));
@orient = eulertoquaternion(rot, 0);
```

Demonstrates three methods of setting orientation: converting an identity matrix3 to a quaternion, directly assigning quaternion values, and converting Euler angles from a channel parameter.

### Quaternion Slerp with Ramps

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
@orient = slerp(a, b, ch('blend'));

vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
float blend = @Time;
@orient = slerp(a, b, blend);
// ...
```

Demonstrates three methods of controlling quaternion interpolation: using a channel reference, using @Time directly, and using a ramp lookup with chramp().

### Orient Attribute Transformation

```vex
// *orient
```

The *orient attribute can be prefixed with an asterisk to prevent it from being transformed by downstream transform nodes.

### Converting vectors to quaternions

```vex
v@orient = quaternion(maketransform(@N, @up));
v@up = {0,1,0};
```

Demonstrates creating a quaternion orientation from normal and up vectors by first building a transform matrix with maketransform(), then converting it to a quaternion.

### Identity Matrix Declaration

```vex
matrix3 m = {1,0,0,0,1,0,0,0,1};
```

This demonstrates the explicit syntax for declaring a 3x3 identity matrix in VEX by listing all nine values in row-major order.

### Setting Primitive Transform Intrinsic

```vex
matrix3 m = ident();

setprimintrinsic(0, "transform", 0, m);
```

Creates an identity matrix and uses setprimintrinsic() to write to a primitive's transform intrinsic.

### Resetting Primitive Transform Intrinsic

```vex
matrix3 m = ident();
setprimintrinsic(0, "transform", 0, m);
```

Creates an identity matrix and uses setprimintrinsic() to reset a primitive's transform intrinsic back to its default state.

### Resetting Primitive Transform Intrinsic

```vex
matrix3 m = ident();
setprimintrinsic(0, "transform", 0, m);
@P = {0,0,0};
```

Demonstrates resetting a primitive's transform intrinsic to identity using setprimintrinsic() and zeroing the point position.

### Reset Packed Primitive Transform

```vex
matrix3 m = ident();
setprimintrinsic(0, "transform", @primnum, m);
```

Creates an identity matrix and uses setprimintrinsic() to reset the transform intrinsic of a packed primitive back to its default state.

### Matrix Casting 4x4 to 3x3

```vex
matrix3 m = matrix3(myFancyMatrix);

matrix pft = primintrinsic(0, 'packedfulltransform', @ptnum);

4@a = pft;
```

Demonstrates casting a 4x4 matrix to a 3x3 matrix using explicit type conversion with matrix3().

### Reading Packed Primitive Transform Matrix

```vex
matrix pft = prim(@OpInput1, "packedfulltransform", @ptnum);
4@a = pft;
```

Reads the packed primitive's full transformation matrix using the prim() function and stores it in a 4x4 matrix attribute.

### Reading Packed Transform Matrix

```vex
matrix pft = printintrinsic(0, "packedfulltransform", @ptnum);
@Cd = pft;
```

Retrieves the packed full transform matrix from a packed primitive and assigns it to the color attribute for visualization.

### Extracting Rotation and Scale from Packed Transform

```vex
matrix pft = primintrinsic(0, "packedfullransform", @ptnum);
@ptg = pft;

matrix3 rotandscale = matrix3(pft);
@p3by3 = rotandscale;
```

Demonstrates extracting the 3x3 rotation and scale component from a packed primitive's 4x4 transform matrix by casting it to a matrix3.

### Attaching Point Using Prim UV

```vex
vector uv;

uv.x = sin(6*Time*2);
uv.y = cos(6*Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);
uv += {0.5,0.5};

// ...
```

Uses animated UV coordinates to attach a point to a specific location on a primitive surface.

### xyzdist Multiple Return Values

```vex
i@primid;
v@uv;
f@dist;
@dist = xyzdist(1, @P, @primid, @uv);
```

Demonstrates how xyzdist() returns multiple values simultaneously: the distance as the function return value, and the primitive ID and UV coordinates through the reference parameters.

### xyzdist Multi-Output Pattern

```vex
i@grid;
v@uv;
@ui1;

@ui1 = xyzdist(1, @P, @grid, @uv);
```

The xyzdist() function returns the distance to the closest point on a geometry surface while simultaneously writing additional data (primitive ID and UV coordinates) to referenced variables.

### Snapping Points with xyzdist

```vex
@P = xyzdist(1, @P);
```

Uses xyzdist to snap each point to the closest position on the geometry from the second input.

### abs

```vex
if(abs(n) >1){// n is greater than 1 or less than -1}
```

Signature: if(abs(n) >1){// n is greater than 1 or less than -1}

Returns the absolute (positive) equivalent of the number.

### agentclipsample

```vex
floatvalue=agentclipsample(0,@primnum,"walk",1.2,"latch_leftfoot");
```

Signature: floatvalue=agentclipsample(0,@primnum,"walk",1.2,"latch_leftfoot");

When running in the context of a node (such as a wrangle SOP), this argument can be an integer representing the input....

### agentclipsamplelocal

```vex
matrixxforms[] =agentclipsamplelocal(0,@primnum,"agent1_clip.walk",1.2);
```

Signature: matrixxforms[] =agentclipsamplelocal(0,@primnum,"agent1_clip.walk",1.2);

When running in the context of a node (such as a wrangle SOP), this argument can be an integer representing the ....

### agentclipsampleworld

```vex
matrixxforms[] =agentclipsampleworld(0,@primnum,"agent1_clip.walk",1.2);
```

Signature: matrixxforms[] =agentclipsampleworld(0,@primnum,"agent1_clip.walk",1.2);

When running in the context of a node (such as a wrangle SOP), this argument can be an integer representing the ....

### array

```vex
vectorv[] =vector[](array(1,{1,2,3},3,s,t,Cl,P,N));floatf[] =float[](array(1,2,s,t,length(P-L),length(N)));
```

Signature: vectorv[] =vector[](array(1,{1,2,3},3,s,t,Cl,P,N));floatf[] =float[](array(1,2,s,t,length(P-L),length(N)));

Returns an array of items of the given type.

### attribsize

```vex
// Get the size of the position attribute of "defgeo.bgeo"intsize=attribsize("defgeo.bgeo","point","P");
```

Signature: // Get the size of the position attribute of "defgeo.bgeo"intsize=attribsize("defgeo.bgeo","point","P");

When running in the context of a node (such as a wrangle SOP), this argument can....

### ch

```vex
// Get the X transform of the box1 SOP at 1.5s into the animationfloattx=ch("/obj/geo1/box1/tx",1.5)
```

Signature: // Get the X transform of the box1 SOP at 1.5s into the animationfloattx=ch("/obj/geo1/box1/tx",1.5)

Evaluates a channel (or parameter) and return its value.

### colormap

```vex
colormap(map,u,v,"smode","decal","tmode","repeat","border",{.1,1,1});colormap(map,u,v,"mode","clamp","width",1.3);colormap(map,u,v,"filter","gauss","width",1.3,"mode","repeat");
```

Signature: colormap(map,u,v,"smode","decal","tmode","repeat","border",{.1,1,1});colormap(map,u,v,"mode","clamp","width",1.3);colormap(map,u,v,"filter","gauss","width",1.3,"mode","repeat");

Uses th....

### computenormal

```vex
N=computenormal(P,"extrapolate",1,"smooth",0);
```

Signature: N=computenormal(P,"extrapolate",1,"smooth",0);

In shading contexts, computes the normal for position P using the cross product of the derivatives of P.

### cvex_bsdf

```vex
F=cvex_bsdf("...","...","label","diffuse","N",N);
```

This interface is subject to change in future versions of Houdini,
    though any potential changes will likely not require fundamental
    changes to the structure of your shaders.

### efit

```vex
efit(.3,0,1,10,20) ==13
```

Signature: efit(.3,0,1,10,20) ==13

Takes the value in the range (‹omin›, ‹omax›) and shifts it to the corresponding value in the new range (‹nmin›, ‹nmax›).
    Unlikefit, this function does not c....

### eval_bsdf

```vex
v=eval_bsdf(F,inI,dir,"direct",0,// Specify indirect illumination"import:sssmfp",sssmfp,// Read the exported sssmfp parameter...
);
```

Signature: v=eval_bsdf(F,inI,dir,"direct",0,// Specify indirect illumination"import:sssmfp",sssmfp,// Read the exported sssmfp parameter...
);

BSDF to evaluate.

### filterstep

```vex
f=filterstep(0.5,s+t,"filter","gauss","width",2);
```

Examples of specifying filter parameters:

If the texture is a deep.ratfile, you can use the"channel"keyword argument
to specify a channel in the file:

When you read a texture in a format other th....

### fit

```vex
fit(.3,0,1,10,20) ==13
```

Signature: fit(.3,0,1,10,20) ==13

Takes the value in the range (‹omin›, ‹omax›) and shifts it to the corresponding value in the new range (‹nmin›, ‹nmax›).

The function clamps the given value the....

### getderiv

```vex
// Get derivatives of point attribute 'N'vectordNdu,dNdv;getderiv(N,"N",0,s,t,dNdu,dNdv);
```

If derivatives are queried for a polygonal mesh it is interally sampled as a Subdivision Surface.

### getlights

```vex
getlights("lightmask","light*,^light2");getlights("categories","shadow|occlusion");getlights(material(),P,"direct",0);
```

Signature: getlights("lightmask","light*,^light2");getlights("categories","shadow|occlusion");getlights(material(),P,"direct",0);.

### getpackedtransform

```vex
// matrix to transform bymatrixtransform=ident();rotate(transform,radians(45),{0,1,0});translate(transform,{0,1,0});matrixtf=getpackedtransform(0,@primnum);setpackedtransform(0,@primnum,transform*tf);
```

Signature: // matrix to transform bymatrixtransform=ident();rotate(transform,radians(45),{0,1,0});translate(transform,{0,1,0});matrixtf=getpackedtransform(0,@primnum);setpackedtransform(0,@primnum,....

### getuvtangents

```vex
// Get UV tangent at 'P', searching the surface in the direction of 'N'vectorTu,Tv;getuvtangents("/obj/geo1",P,N,Tu,Tv);
```

Signature: // Get UV tangent at 'P', searching the surface in the direction of 'N'vectorTu,Tv;getuvtangents("/obj/geo1",P,N,Tu,Tv);

The object must have a vector attribute named “uv”.

### hair

```vex
bsdfhair(vectorN;vectortip;floatlobe_shift;floatlobe_width_lon, ...){cvex_bsdf("hair_eval","hair_sample","label","diffuse","tip",tip,"lobe_shift",lobe_shift,"lobe_width_lon",lobe_width_lon,
    ...);}bsdfhair(vectorN;vectortip;floatlobe_shift;floatlobe_width_lon,floatlobe_with_azi, ...){cvex_bsdf("hair_eval","hair_sample","label","refract","tip",tip,"lobe_shift",lobe_shift,"lobe_width_lon",lobe_width_lon,"lobe_width_azi",lobe_width_azi,
    ...);}bsdfhair(vectorN;vectortip;floatlobe_shift;floatlobe_width_lon,floatglint_shift;floatglint_intensity, ...){cvex_bsdf("hair_eval","hair_sample","label","reflect","tip",tip,"lobe_shift",lobe_shift,"lobe_width_lon",lobe_width_lon,"glint_shift",glint_shift,"glint_intensity",glint_intensity,
    ...);}
```

Signature: bsdfhair(vectorN;vectortip;floatlobe_shift;floatlobe_width_lon, ...){cvex_bsdf("hair_eval","hair_sample","label","diffuse","tip",tip,"lobe_shift",lobe_shift,"lobe_width_lon",lobe_width_l....

### interpolate

```vex
vectorhitP=interpolate(P,sx,sy);
```

Signature: vectorhitP=interpolate(P,sx,sy);

Adds an item to an array or string.

Returns the indices of a sorted version of an array.

Efficiently creates an array from its arguments.

### isbound

```vex
sopmycolor(vectoruv=0;stringmap=""){if(isbound("uv") &&map!=""){// User has texture coordinates here, so create// velocity based on a texture map.v=colormap(map,uv);}else{// No texture coordinates, so use a random valuev=random(id);}
```

Signature: sopmycolor(vectoruv=0;stringmap=""){if(isbound("uv") &&map!=""){// User has texture coordinates here, so create// velocity based on a texture map.v=colormap(map,uv);}else{// No texture c....

### kspline

```vex
typekspline(basis,t,v0,k0,v1,k1,v2,k2...){floattk=spline("linearsolve",t,k0,k1,k2, ...);returnspline(basis,tk,v0,v1,v2, ...);}
```

Samples a curve defined by a series of value/position pairs.
    This is useful for specifying a 1D data ramp.

### length

```vex
length({1.0,0,0}) ==1.0;length({1.0,1.0,0}) ==1.41421;
```

Signature: length({1.0,0,0}) ==1.0;length({1.0,1.0,0}) ==1.41421;

Simply returns the given number.

### length2

```vex
length2({0.5,0.75,0}) ==0.8125;
```

Signature: length2({0.5,0.75,0}) ==0.8125;

Returns the squared distance of the vector.

### nuniqueval

```vex
inttest=nuniqueval(0,"point","foo") ==npoints(0)
```

Signature: inttest=nuniqueval(0,"point","foo") ==npoints(0)

When running in the context of a node (such as a wrangle SOP), this argument can be an integer representing the input number (starting a....

### pcwrite

```vex
pcwrite("out.pc","P",P,"N",N)
```

Signature: pcwrite("out.pc","P",P,"N",N)

Writes data for the current shading point out to a point cloud file.

### photonmap

```vex
Cf=photonmap(map,P,normalize(frontface(N,I)),"nphotons",100,"type","diffuse","error",0.05,"filter","convex);
```

Signature: Cf=photonmap(map,P,normalize(frontface(N,I)),"nphotons",100,"type","diffuse","error",0.05,"filter","convex);

You can specify additional keyword,value argument pairs to set the
behavior ....

### ptransform

```vex
Pworld=ptransform("space:world",P);
```

Signature: Pworld=ptransform("space:world",P);

Transforms the vector using the given transform matrix.

### reflectlight

```vex
surfaceblurry_mirror(floatangle=3;intsamples=16;floatbias=0.05){Cf=reflectlight(bias,1,"angle",angle,"samples",samples);}
```

Signature: surfaceblurry_mirror(floatangle=3;intsamples=16;floatbias=0.05){Cf=reflectlight(bias,1,"angle",angle,"samples",samples);}

‹bias› is typically a small number (for example 0.005) used to ....

### refract

```vex
refract(normalize(I),normalize(N),outside_to_inside_ior)
```

Signature: refract(normalize(I),normalize(N),outside_to_inside_ior)

Adds an item to an array or string.

Returns the indices of a sorted version of an array.

Efficiently creates an array from its....

### sample_bsdf

```vex
sample_bsdf(F,inI,outI,eval,type,sx,sy,"direct",0,// Specify indirect illumination"import:sssmfp",sssmfp,// Read the exported sssmfp parameter...
);
```

Signature: sample_bsdf(F,inI,outI,eval,type,sx,sy,"direct",0,// Specify indirect illumination"import:sssmfp",sssmfp,// Read the exported sssmfp parameter...
);

The BSDF to sample.

### sample_cauchy

```vex
!vex
sample_cauchy(1,0,maxdist,u.x) * sample_direction_uniform(set(u.y,u.z))
```

Signature: !vex
sample_cauchy(1,0,maxdist,u.x) * sample_direction_uniform(set(u.y,u.z))

Sample multivariate Cauchy distributions with median 0 and scale 1.

### scatter

```vex
// Trace for intersection with scenevectorhitP=0;vectorhitN=0;inthit=trace(P,I,Time,"P",hitP,"N",hitN);// Scatter a random distance from the intersectionvectoridistribution=0;intsid=israytrace?SID:newsampler();vectors;nextsample(sid,s.x,s.y,"mode","nextpixel");floatmaxdist=2.0*s.x;vectoropoint=0;vectoronormal=0;vectorodirection=0;hit=scatter(hitP,hitN,I,idistribution,Time,maxdist,opoint,onormal,odirection);// Trace again from the exit point of the scatteringhit=trace(opoint,odirection,Time,"P",hitP,"N",hitN);
```

Signature: // Trace for intersection with scenevectorhitP=0;vectorhitN=0;inthit=trace(P,I,Time,"P",hitP,"N",hitN);// Scatter a random distance from the intersectionvectoridistribution=0;intsid=isra....

### serialize

```vex
vectorv[] ={{1,2,3},{7,8,9}};// A vector[] of length 2floatf[];f=serialize(v);// Now f[] has a length of 6 and equals { 1,2,3,7,8,9 }
```

Signature: vectorv[] ={{1,2,3},{7,8,9}};// A vector[] of length 2floatf[];f=serialize(v);// Now f[] has a length of 6 and equals { 1,2,3,7,8,9 }.

### swizzle

```vex
swizzle({10, 20, 30, 40}, 3, 2, 1, 0) == {40, 30, 20, 10}
swizzle({10, 20, 30, 40}, 0, 0, 0, 0) == {10, 10, 10, 10}
```

Signature: swizzle({10, 20, 30, 40}, 3, 2, 1, 0) == {40, 30, 20, 10}
swizzle({10, 20, 30, 40}, 0, 0, 0, 0) == {10, 10, 10, 10}.

### trace

```vex
// Find the position and normal for all hit points along the ray,// regardless of visibility.vectora_pos[];vectora_nml[];trace(P,dir,Time,"samplefilter","all","P",a_pos,"N",a_nml);
```

Sends a ray from ‹P› along the normalized vector ‹D›.

### typeid

```vex
// Check if the value for "foo" is a matrix.inttype=typeid(d,"foo");if(type==typeid(matrix()){matrixm=d["foo"];}
```

Signature: // Check if the value for "foo" is a matrix.inttype=typeid(d,"foo");if(type==typeid(matrix()){matrixm=d["foo"];}

Returns a numeric code identifying the valueâs type.

### usd_addattrib

```vex
// Adds a half-precision float attribute and sets its falue.usd_addattrib(0,"/geo/sphere","half_attrib","half3");usd_setattrib(0,"/geo/sphere","half_attrib",{1.25,1.50,1.75});
```

Signature: // Adds a half-precision float attribute and sets its falue.usd_addattrib(0,"/geo/sphere","half_attrib","half3");usd_setattrib(0,"/geo/sphere","half_attrib",{1.25,1.50,1.75});

A handle ....

### usd_addcollectionexclude

```vex
// Exclude sphere3 from cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_addcollectionexclude(0,collection_path,"/geo/sphere3");
```

Signature: // Exclude sphere3 from cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_addcollectionexclude(0,collection_path,"/geo/sphere3");

A han....

### usd_addcollectioninclude

```vex
// Include sphere4 in cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_addcollectioninclude(0,collection_path,"/geo/sphere4");
```

Signature: // Include sphere4 in cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_addcollectioninclude(0,collection_path,"/geo/sphere4");

A handl....

### usd_addorient

```vex
// Orient the cubevector4quat=eulertoquaternion(radians({30,0,0}),XFORM_XYZ);usd_addorient(0,"/dst/cone","my_orientation",quat);
```

Signature: // Orient the cubevector4quat=eulertoquaternion(radians({30,0,0}),XFORM_XYZ);usd_addorient(0,"/dst/cone","my_orientation",quat);

A handle to the stage to write to.

### usd_addprimvar

```vex
// Adds a half-precision float primvar and sets its falue.usd_addprimvar(0,"/geo/sphere","half_primvar","half3");usd_setprimvar(0,"/geo/sphere","half_primvar",{1.25,1.50,1.75});// Adds a color primitive with 'vertex' interpolation.usd_addprimvar(0,pp,"color_primvar","color3d[]","vertex");usd_setprimvar(0,pp,"color_primvar",vector[](array({1,0,0},{0,1,0},{0,0,1})));
```

Signature: // Adds a half-precision float primvar and sets its falue.usd_addprimvar(0,"/geo/sphere","half_primvar","half3");usd_setprimvar(0,"/geo/sphere","half_primvar",{1.25,1.50,1.75});// Adds a....

### usd_addschemaattrib

```vex
// Adds a half-precision float attribute and sets its falue.usd_applyapi(0,"/geo","GeomModelAPI");usd_addschemaattrib(0,"/geo","extentsHint","float[]");
```

Signature: // Adds a half-precision float attribute and sets its falue.usd_applyapi(0,"/geo","GeomModelAPI");usd_addschemaattrib(0,"/geo","extentsHint","float[]");

A handle to the stage to write to.

### usd_bindmaterial

```vex
// Assigns a metal material to the sphere geometry.usd_bindmaterial(0,"/geo/sphere","/materials/metal");
```

Signature: // Assigns a metal material to the sphere geometry.usd_bindmaterial(0,"/geo/sphere","/materials/metal");

A handle to the stage to write to.

### usd_blockprimvarindices

```vex
// Block the primvar indices.usd_blockprimvarindices(0,"/geo/sphere","primvar_name");
```

Signature: // Block the primvar indices.usd_blockprimvarindices(0,"/geo/sphere","primvar_name");

A handle to the stage to write to.

### usd_blockrelationship

```vex
// Clear the cube's relationship.usd_blockrelationship(0,"/geo/cube","relationship_name");
```

Signature: // Clear the cube's relationship.usd_blockrelationship(0,"/geo/cube","relationship_name");

A handle to the stage to write to.

### usd_boundmaterialpath

```vex
// Get the sphere primitive's material.stringmatpath=usd_boundmaterialpath(0,"/geo/sphere");
```

Signature: // Get the sphere primitive's material.stringmatpath=usd_boundmaterialpath(0,"/geo/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an integ....

### usd_cleartransformorder

```vex
usd_cleartransformorder(0,"/geo/cone");
```

Signature: usd_cleartransformorder(0,"/geo/cone");

A handle to the stage to write to.

### usd_collectioncomputedpaths

```vex
// Get all objects in cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");stringmembers[] =usd_collectioncomputedpaths(0,collection_path);
```

Signature: // Get all objects in cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");stringmembers[] =usd_collectioncomputedpaths(0,collection_path);

Wh....

### usd_collectioncontains

```vex
// Check if sphere3 is in cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");intcontains_sphere3=usd_collectioncontains(0,collection_path,"/geo/sphere3");
```

Signature: // Check if sphere3 is in cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");intcontains_sphere3=usd_collectioncontains(0,collection_path,"/g....

### usd_collectionexcludes

```vex
// Get collection's exclude list.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");stringexclude_list[]  =usd_collectionexcludes(0,collection_path);
```

Signature: // Get collection's exclude list.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");stringexclude_list[]  =usd_collectionexcludes(0,collection_path);

When run....

### usd_collectionexpansionrule

```vex
// Get collection's expansion rule.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");stringexpansion_rule=usd_collectionexpansionrule(0,collection_path);
```

Signature: // Get collection's expansion rule.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");stringexpansion_rule=usd_collectionexpansionrule(0,collection_path);

exp....

### usd_findtransformname

```vex
// Find the transform operation name for the pivot translation, and add an iverse of it.stringxform_name=usd_findtransformname(0,"/geo/cone","cone_pivot");usd_addinversetotransformorder(0,"/geo/cone",xform_name);
```

Signature: // Find the transform operation name for the pivot translation, and add an iverse of it.stringxform_name=usd_findtransformname(0,"/geo/cone","cone_pivot");usd_addinversetotransformorder(....

### usd_flattenediprimvar

```vex
// Get the value of a flattened primvar on the cube primitive or cube's ancestor.floatflat_values[] =usd_flattenediprimvar(0,"/geo/cube","primvar_name");f[]@flat_primvar_at_current_frame=usd_flattenediprimvar(0,"/geo/sphere","bar");f[]@flat_primvar_at_frame_7=usd_flattenediprimvar(0,"/geo/sphere","bar",7.0);
```

Signature: // Get the value of a flattened primvar on the cube primitive or cube's ancestor.floatflat_values[] =usd_flattenediprimvar(0,"/geo/cube","primvar_name");f[]@flat_primvar_at_current_frame....

### usd_flattenediprimvarelement

```vex
// Get the value of a flattened primvar on the cube primitive or cube's ancestor.floatflat_value=usd_flattenediprimvarelement(0,"/geo/cube","primvar_name",3);f@flat_primvar_element_10_at_current_frame=usd_flattenediprimvarelement(0,"/geo/sphere","bar",10);f@flat_primvar_element_10_at_frame_7=usd_flattenediprimvarelement(0,"/geo/sphere","bar",10,7.0);
```

Signature: // Get the value of a flattened primvar on the cube primitive or cube's ancestor.floatflat_value=usd_flattenediprimvarelement(0,"/geo/cube","primvar_name",3);f@flat_primvar_element_10_at....

### usd_flattenedprimvar

```vex
// Get the value of a flattened primvar on the cube primitive.floatflat_values[] =usd_flattenedprimvar(0,"/geo/cube","primvar_name");f[]@flat_primvar_at_current_frame=usd_flattenedprimvar(0,"/geo/sphere","bar");f[]@flat_primvar_at_frame_7=usd_flattenedprimvar(0,"/geo/sphere","bar",7.0);
```

Signature: // Get the value of a flattened primvar on the cube primitive.floatflat_values[] =usd_flattenedprimvar(0,"/geo/cube","primvar_name");f[]@flat_primvar_at_current_frame=usd_flattenedprimva....

### usd_flattenedprimvarelement

```vex
// Get the value of a flattened primvar on the cube primitive.floatflat_value=usd_flattenedprimvarelement(0,"/geo/cube","primvar_name",3);f@flat_primvar_element_10_at_current_frame=usd_flattenedprimvarelement(0,"/geo/sphere","bar",10);f@flat_primvar_element_10_at_frame_7=usd_flattenedprimvarelement(0,"/geo/sphere","bar",10,7.0);
```

Signature: // Get the value of a flattened primvar on the cube primitive.floatflat_value=usd_flattenedprimvarelement(0,"/geo/cube","primvar_name",3);f@flat_primvar_element_10_at_current_frame=usd_f....

### usd_getbbox

```vex
// Get the sphere's bounding box.vectormin,max;usd_getbbox(0,"/src/sphere","render",min,max);
```

Signature: // Get the sphere's bounding box.vectormin,max;usd_getbbox(0,"/src/sphere","render",min,max);

When running in the context of a node (such as a wrangle LOP), this argument can be an inte....

### usd_getbbox_max

```vex
// Get the sphere's bounding box.vectormax=usd_getbbox_max(0,"/src/sphere","render");
```

Signature: // Get the sphere's bounding box.vectormax=usd_getbbox_max(0,"/src/sphere","render");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer repr....

### usd_getbbox_min

```vex
// Get the sphere's bounding box.vectormin=usd_getbbox_min(0,"/src/sphere","render");
```

Signature: // Get the sphere's bounding box.vectormin=usd_getbbox_min(0,"/src/sphere","render");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer repr....

### usd_getbbox_size

```vex
// Get the sphere's bounding box.vectorsize=usd_getbbox_size(0,"/src/sphere","render");
```

Signature: // Get the sphere's bounding box.vectorsize=usd_getbbox_size(0,"/src/sphere","render");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer re....

### usd_getbounds

```vex
// Get the sphere's bounding box.vectormin,max;usd_getbounds(0,"/src/sphere","render",min,max);
```

Signature: // Get the sphere's bounding box.vectormin,max;usd_getbounds(0,"/src/sphere","render",min,max);

When running in the context of a node (such as a wrangle LOP), this argument can be an in....

### usd_getpointinstancebounds

```vex
// Get the second sphere's bounding box.vectormin,max;usd_getpointinstancebounds(0,"/src/instanced_spheres",1,"render",min,max);
```

Signature: // Get the second sphere's bounding box.vectormin,max;usd_getpointinstancebounds(0,"/src/instanced_spheres",1,"render",min,max);

When running in the context of a node (such as a wrangle....

### usd_hasapi

```vex
// Check if the primitive has a USD Geometry Model API applied.inthas_geom_model_api_by_name=usd_hasapi(0,"/geo/sphere","UsdGeomModelAPI");inthas_geom_model_api_by_alias=usd_hasapi(0,"/geo/sphere","GeomModelAPI");
```

Signature: // Check if the primitive has a USD Geometry Model API applied.inthas_geom_model_api_by_name=usd_hasapi(0,"/geo/sphere","UsdGeomModelAPI");inthas_geom_model_api_by_alias=usd_hasapi(0,"/g....

### usd_haspayload

```vex
inthas_payload=usd_haspayload(0,"/geo/sphere");
```

Signature: inthas_payload=usd_haspayload(0,"/geo/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer representing the input number (starting at....

### usd_iprimvar

```vex
// Get the value of some primvars on the cube primitive or cube's ancestor.vectorvec_value=usd_iprimvar(0,"/geo/cube","vec_primvar_name");floatvalues[] =usd_iprimvar(0,"/geo/cube","primvar_name");floatvalue=usd_iprimvar(0,"/geo/cube","primvar_name",3);v[]@foo_at_current_frame=usd_iprimvar(0,"/geo/sphere","foo");v[]@foo_at_frame_8=usd_iprimvar(0,"/geo/sphere","foo",8.0);
```

Signature: // Get the value of some primvars on the cube primitive or cube's ancestor.vectorvec_value=usd_iprimvar(0,"/geo/cube","vec_primvar_name");floatvalues[] =usd_iprimvar(0,"/geo/cube","primv....

### usd_iprimvarelement

```vex
// Get the value of some primvars on the cube primitive or its ancestor.floatvalue=usd_iprimvarelement(0,"/geo/cube","primvar_name",3);v@element_2_at_current_frame=usd_iprimvarelement(0,"/geo/sphere","foo",2);v@element_2_at_frame_8=usd_iprimvarelement(0,"/geo/sphere","foo",2,8.0);
```

Signature: // Get the value of some primvars on the cube primitive or its ancestor.floatvalue=usd_iprimvarelement(0,"/geo/cube","primvar_name",3);v@element_2_at_current_frame=usd_iprimvarelement(0,....

### usd_iprimvarelementsize

```vex
// Get the element size of a primvar on the cube primitive or its ancestor.intelement_size=usd_iprimvarelementsize(0,"/geo/cube","primvar_name");
```

Signature: // Get the element size of a primvar on the cube primitive or its ancestor.intelement_size=usd_iprimvarelementsize(0,"/geo/cube","primvar_name");

When running in the context of a node (....

### usd_iprimvarindices

```vex
// Get the index array of an indexed primvar.intindices[] =usd_iprimvarindices(0,"/geo/cube","indexed_primvar_name");
```

Signature: // Get the index array of an indexed primvar.intindices[] =usd_iprimvarindices(0,"/geo/cube","indexed_primvar_name");

When running in the context of a node (such as a wrangle LOP), this....

### usd_iprimvarinterpolation

```vex
// Get the interpolation style of the primvar on the cube or its parent.stringinterpolation=usd_iprimvarinterpolation(0,"/geo/cube","primvar_name");
```

Signature: // Get the interpolation style of the primvar on the cube or its parent.stringinterpolation=usd_iprimvarinterpolation(0,"/geo/cube","primvar_name");

When running in the context of a nod....

### usd_iprimvarlen

```vex
// Get the array length of the primvar on cube or its ancestor.intarray_length=usd_iprimvarlen(0,"/geo/cube","array_primvar_name");
```

Signature: // Get the array length of the primvar on cube or its ancestor.intarray_length=usd_iprimvarlen(0,"/geo/cube","array_primvar_name");

When running in the context of a node (such as a wran....

### usd_iprimvarsize

```vex
// Get the tuple size of a primvar on the cube primitive or its ancestor.inttuple_size=usd_iprimvarsize(0,"/geo/cube","primvar_name");
```

Signature: // Get the tuple size of a primvar on the cube primitive or its ancestor.inttuple_size=usd_iprimvarsize(0,"/geo/cube","primvar_name");

When running in the context of a node (such as a w....

### usd_iprimvartypename

```vex
// Get the type name of the primvar on cube or its ancestor..stringtype_name=usd_iprimvartypename(0,"/geo/cube","primvar_name");
```

Signature: // Get the type name of the primvar on cube or its ancestor..stringtype_name=usd_iprimvartypename(0,"/geo/cube","primvar_name");

When running in the context of a node (such as a wrangle....

### usd_isabstract

```vex
// Check if the sphere primitive is abstract.intis_abstract=usd_isabstract(0,"/geometry/sphere");
```

Signature: // Check if the sphere primitive is abstract.intis_abstract=usd_isabstract(0,"/geometry/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an ....

### usd_isactive

```vex
// Check if the sphere primitive is active.intis_active=usd_isactive(0,"/geometry/sphere");
```

Signature: // Check if the sphere primitive is active.intis_active=usd_isactive(0,"/geometry/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an intege....

### usd_isarray

```vex
// Check if attribute "some_attribute" is an array.intis_array=usd_isarray(0,"/geometry/sphere","some_attribute");
```

Signature: // Check if attribute "some_attribute" is an array.intis_array=usd_isarray(0,"/geometry/sphere","some_attribute");

When running in the context of a node (such as a wrangle LOP), this ar....

### usd_isarrayiprimvar

```vex
// Check if primvar "some_primvar" is an array.intis_array=usd_isarrayiprimvar(0,"/geometry/sphere","some_primvar");
```

Signature: // Check if primvar "some_primvar" is an array.intis_array=usd_isarrayiprimvar(0,"/geometry/sphere","some_primvar");

When running in the context of a node (such as a wrangle LOP), this ....

### usd_isarrayprimvar

```vex
// Check if primvar "some_primvar" is an array.intis_array=usd_isarrayprimvar(0,"/geometry/sphere","some_primvar");
```

Signature: // Check if primvar "some_primvar" is an array.intis_array=usd_isarrayprimvar(0,"/geometry/sphere","some_primvar");

When running in the context of a node (such as a wrangle LOP), this a....

### usd_isindexedprimvar

```vex
// Check if primvar "some_primvar" on sphere is indexed.intis_indexed=usd_isindexedprimvar(0,"/geometry/sphere","some_primvar");
```

Signature: // Check if primvar "some_primvar" on sphere is indexed.intis_indexed=usd_isindexedprimvar(0,"/geometry/sphere","some_primvar");

When running in the context of a node (such as a wrangle....

### usd_isinstance

```vex
// Check if the sphere primitive is an instance.intis_instance=usd_isinstance(0,"/geometry/sphere");
```

Signature: // Check if the sphere primitive is an instance.intis_instance=usd_isinstance(0,"/geometry/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be ....

### usd_isiprimvar

```vex
// Check if the sphere primitive or its ancestor has a primvar "some_primvar".intis_primvar=usd_isiprimvar(0,"/geometry/sphere","some_primvar");
```

Signature: // Check if the sphere primitive or its ancestor has a primvar "some_primvar".intis_primvar=usd_isiprimvar(0,"/geometry/sphere","some_primvar");

When running in the context of a node (s....

### usd_iskind

```vex
// Check if the sphere primitive is of an assembly kind.intis_assembly=usd_iskind(0,"/geometry/sphere","assembly");
```

Signature: // Check if the sphere primitive is of an assembly kind.intis_assembly=usd_iskind(0,"/geometry/sphere","assembly");

When running in the context of a node (such as a wrangle LOP), this a....

### usd_ismetadata

```vex
// Check if the primitives have various metadata:inthas_doc=usd_ismetadata(0,"/geo/sphere","documentation");inthas_custom_foo_bar=usd_ismetadata(0,"/geo/cube","customData:foo:bar");// Check if the attribute has custom data setstringattrib_path=usd_makeattribpath(0,"/geo/sphere","attrib_name");inthas_attrib_foo=usd_ismetadata(0,attrib_path,"customData:foo");
```

Signature: // Check if the primitives have various metadata:inthas_doc=usd_ismetadata(0,"/geo/sphere","documentation");inthas_custom_foo_bar=usd_ismetadata(0,"/geo/cube","customData:foo:bar");// Ch....

### usd_ismodel

```vex
// Check if the sphere primitive is a model.intis_model=usd_ismodel(0,"/geometry/sphere");
```

Signature: // Check if the sphere primitive is a model.intis_model=usd_ismodel(0,"/geometry/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer....

### usd_isprimvar

```vex
// Check if the sphere primitive has a primvar "some_primvar".intis_primvar=usd_isprimvar(0,"/geometry/sphere","some_primvar");
```

Signature: // Check if the sphere primitive has a primvar "some_primvar".intis_primvar=usd_isprimvar(0,"/geometry/sphere","some_primvar");

When running in the context of a node (such as a wrangle ....

### usd_istransformreset

```vex
// Check if the cube's transform is reset.intis_xform_reset=usd_istransformreset(1,"/geo/cube");
```

Signature: // Check if the cube's transform is reset.intis_xform_reset=usd_istransformreset(1,"/geo/cube");

When running in the context of a node (such as a wrangle LOP), this argument can be an i....

### usd_istype

```vex
// Check if the primitive is a Cube and is boundableintis_cube_by_alias=usd_istype(0,"/geo/cube","Cube");intis_cube_by_name=usd_istype(0,"/geo/cube","UsdGeomCube");intis_boundable_by_name=usd_istype(0,"/geo/cube","UsdGeomBoundable");
```

Signature: // Check if the primitive is a Cube and is boundableintis_cube_by_alias=usd_istype(0,"/geo/cube","Cube");intis_cube_by_name=usd_istype(0,"/geo/cube","UsdGeomCube");intis_boundable_by_nam....

### usd_isvisible

```vex
// Check if the sphere primitive is visible.intis_visible=usd_isvisible(0,"/geometry/sphere");
```

Signature: // Check if the sphere primitive is visible.intis_visible=usd_isvisible(0,"/geometry/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an int....

### usd_localtransform

```vex
// Get the cube's local transform.matrixcube_local_xform=usd_localtransform(0,"/src/cube");
```

Signature: // Get the cube's local transform.matrixcube_local_xform=usd_localtransform(0,"/src/cube");

When running in the context of a node (such as a wrangle LOP), this argument can be an intege....

### usd_makecollectionpath

```vex
// Obtain the full path to the collection "some_collection" on the cube primitive.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");
```

Signature: // Obtain the full path to the collection "some_collection" on the cube primitive.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");

When running in the cont....

### usd_makepropertypath

```vex
// Obtain the full path to the property "prop_name" on the cube primitive.stringprop_path=usd_makepropertypath(0,"/geo/cube","prop_name");
```

Signature: // Obtain the full path to the property "prop_name" on the cube primitive.stringprop_path=usd_makepropertypath(0,"/geo/cube","prop_name");

When running in the context of a node (such as....

### usd_makerelationshippath

```vex
// Obtain the full path to the relationship "relationship_name" on the cube primitive.stringrelationship_path=usd_makerelationshippath(0,"/geo/cube","relationship_name");
```

Signature: // Obtain the full path to the relationship "relationship_name" on the cube primitive.stringrelationship_path=usd_makerelationshippath(0,"/geo/cube","relationship_name");

When running i....

### usd_metadata

```vex
// Get the documentation string of the cube primitive.stringdocs=usd_metadata(0,"/geo/cube","documentation");// Get custom data from a parameter.stringattrib_path=usd_makeattribpath(0,"/geo/cube","some_attribute");floatcustom_val=usd_metadata(0,attrib_path,"customData:foo:bar");
```

Signature: // Get the documentation string of the cube primitive.stringdocs=usd_metadata(0,"/geo/cube","documentation");// Get custom data from a parameter.stringattrib_path=usd_makeattribpath(0,"/....

### usd_metadataelement

```vex
// Get the value of an element at index 3 in the "foo:bar" array custom data.stringdocs=usd_metadataelement(0,"/geo/cube","customData:foo:bar",3);
```

Signature: // Get the value of an element at index 3 in the "foo:bar" array custom data.stringdocs=usd_metadataelement(0,"/geo/cube","customData:foo:bar",3);

When running in the context of a node ....

### usd_metadatalen

```vex
// Get the array length of metadata on the cube primitive.intlength=usd_metadatalen(0,"/geo/cube","customData:name");
```

Signature: // Get the array length of metadata on the cube primitive.intlength=usd_metadatalen(0,"/geo/cube","customData:name");

When running in the context of a node (such as a wrangle LOP), this....

### usd_metadatanames

```vex
// Get the metadata names from the primitive.stringprim_metadata_names[] =usd_metadatanames(0,"/geo/sphere");// Get the metadata names from the attribute.stringattrib_path=usd_makeattribpath(0,"/geo/sphere","attrib_name");stringattrib_metadata_names[] =usd_metadatanames(0,attrib_path);
```

Signature: // Get the metadata names from the primitive.stringprim_metadata_names[] =usd_metadatanames(0,"/geo/sphere");// Get the metadata names from the attribute.stringattrib_path=usd_makeattrib....

### usd_name

```vex
// Get the primitive name, ie "cube".stringname=usd_name(0,"/geo/cube");
```

Signature: // Get the primitive name, ie "cube".stringname=usd_name(0,"/geo/cube");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer representing the ....

### usd_parentpath

```vex
// Get the path of the primitive's parent, ie "/geo".stringpath=usd_parentpath(0,"/geo/cube");
```

Signature: // Get the path of the primitive's parent, ie "/geo".stringpath=usd_parentpath(0,"/geo/cube");

When running in the context of a node (such as a wrangle LOP), this argument can be an int....

### usd_pointinstance_getbbox_max

```vex
// Get the max of the first instance's boundsng box.vectormax=usd_pointinstance_getbbox_max(0,"/src/instanced_spheres",0,"render");
```

Signature: // Get the max of the first instance's boundsng box.vectormax=usd_pointinstance_getbbox_max(0,"/src/instanced_spheres",0,"render");

When running in the context of a node (such as a wran....

### usd_pointinstance_getbbox_size

```vex
// Get the size of the first instance's boundsng box.vectorsize=usd_pointinstance_getbbox_size(0,"/src/instanced_spheres",0,"render");
```

Signature: // Get the size of the first instance's boundsng box.vectorsize=usd_pointinstance_getbbox_size(0,"/src/instanced_spheres",0,"render");

When running in the context of a node (such as a w....

### usd_pointinstance_relbbox

```vex
// Get the point's position relative to the bounding box of the first instance.vectorpt={1,0,0};vectorrel_pt=usd_pointinstance_relbbox(0,"/src/instanced_spheres",0,"render",pt);
```

Signature: // Get the point's position relative to the bounding box of the first instance.vectorpt={1,0,0};vectorrel_pt=usd_pointinstance_relbbox(0,"/src/instanced_spheres",0,"render",pt);

When ru....

### usd_pointinstancetransform

```vex
// Get the transform of the third instance.matrixxform=usd_pointinstancetransform(0,"/src/instanced_cubes",2);
```

Signature: // Get the transform of the third instance.matrixxform=usd_pointinstancetransform(0,"/src/instanced_cubes",2);

When running in the context of a node (such as a wrangle LOP), this argume....

### usd_primvar

```vex
// Get the value of some primvars on the cube primitive.vectorvec_value=usd_primvar(0,"/geo/cube","vec_primvar_name");floatvalues[] =usd_primvar(0,"/geo/cube","primvar_name");floatvalue=usd_primvar(0,"/geo/cube","primvar_name",3);v[]@foo_at_current_frame=usd_primvar(0,"/geo/sphere","foo");v[]@foo_at_frame_8=usd_primvar(0,"/geo/sphere","foo",8.0);
```

Signature: // Get the value of some primvars on the cube primitive.vectorvec_value=usd_primvar(0,"/geo/cube","vec_primvar_name");floatvalues[] =usd_primvar(0,"/geo/cube","primvar_name");floatvalue=....

### usd_primvarelement

```vex
// Get the value of some primvars on the cube primitive.floatvalue=usd_primvarelement(0,"/geo/cube","primvar_name",3);v@element_2_at_current_frame=usd_primvarelement(0,"/geo/sphere","foo",2);v@element_2_at_frame_8=usd_primvarelement(0,"/geo/sphere","foo",2,8.0);
```

Signature: // Get the value of some primvars on the cube primitive.floatvalue=usd_primvarelement(0,"/geo/cube","primvar_name",3);v@element_2_at_current_frame=usd_primvarelement(0,"/geo/sphere","foo....

### usd_primvarelementsize

```vex
// Get the element size of a primvar on the cube primitive.intelement_size=usd_primvarelementsize(0,"/geo/cube","primvar_name");
```

Signature: // Get the element size of a primvar on the cube primitive.intelement_size=usd_primvarelementsize(0,"/geo/cube","primvar_name");

When running in the context of a node (such as a wrangle....

### usd_primvarindices

```vex
// Get the index array of an indexed primvar.intindices[] =usd_primvarindices(0,"/geo/cube","indexed_primvar_name");
```

Signature: // Get the index array of an indexed primvar.intindices[] =usd_primvarindices(0,"/geo/cube","indexed_primvar_name");

When running in the context of a node (such as a wrangle LOP), this ....

### usd_primvarinterpolation

```vex
// Get the interpolation style of the primvar on the cube.stringinterpolation=usd_primvarinterpolation(0,"/geo/cube","primvar_name");
```

Signature: // Get the interpolation style of the primvar on the cube.stringinterpolation=usd_primvarinterpolation(0,"/geo/cube","primvar_name");

When running in the context of a node (such as a wr....

### usd_primvarlen

```vex
// Get the array length of the primvar on cube.intarray_length=usd_primvarlen(0,"/geo/cube","array_primvar_name");
```

Signature: // Get the array length of the primvar on cube.intarray_length=usd_primvarlen(0,"/geo/cube","array_primvar_name");

When running in the context of a node (such as a wrangle LOP), this ar....

### usd_primvarnames

```vex
// Get the primvar names from the primitive.stringprimvar_names[] =usd_primvarnames(0,"/geo/src_sphere");
```

Signature: // Get the primvar names from the primitive.stringprimvar_names[] =usd_primvarnames(0,"/geo/src_sphere");

When running in the context of a node (such as a wrangle LOP), this argument ca....

### usd_primvarsize

```vex
// Get the tuple size of a primvar on the cube primitive.inttuple_size=usd_primvarsize(0,"/geo/cube","primvar_name");
```

Signature: // Get the tuple size of a primvar on the cube primitive.inttuple_size=usd_primvarsize(0,"/geo/cube","primvar_name");

When running in the context of a node (such as a wrangle LOP), this....

### usd_primvartypename

```vex
// Get the type name of the primvar on cube.stringtype_name=usd_primvartypename(0,"/geo/cube","primvar_name");
```

Signature: // Get the type name of the primvar on cube.stringtype_name=usd_primvartypename(0,"/geo/cube","primvar_name");

When running in the context of a node (such as a wrangle LOP), this argume....

### usd_purpose

```vex
// Get the sphere primitive's purpose.stringpurpose=usd_purpose(0,"/geo/sphere");
```

Signature: // Get the sphere primitive's purpose.stringpurpose=usd_purpose(0,"/geo/sphere");

When running in the context of a node (such as a wrangle LOP), this argument can be an integer represen....

### usd_relationshipforwardedtargets

```vex
// Get the list of forwarded targets in cube's "some_relationship" relationship.stringtargets[] =usd_relationshipforwardedtargets(0,"/geo/cube","some_relationship");
```

Signature: // Get the list of forwarded targets in cube's "some_relationship" relationship.stringtargets[] =usd_relationshipforwardedtargets(0,"/geo/cube","some_relationship");

When running in the....

### usd_relationshipnames

```vex
// Get the relationship names from the primitive.stringrelationship_names[] =usd_relationshipnames(0,"/geo/cube");
```

Signature: // Get the relationship names from the primitive.stringrelationship_names[] =usd_relationshipnames(0,"/geo/cube");

When running in the context of a node (such as a wrangle LOP), this ar....

### usd_relbbox

```vex
// Get the points relative position.vectorpt={1,0,0};vectorrel_pt=usd_relbbox(0,"/src/sphere","render",pt);
```

Signature: // Get the points relative position.vectorpt={1,0,0};vectorrel_pt=usd_relbbox(0,"/src/sphere","render",pt);

When running in the context of a node (such as a wrangle LOP), this argument ....

### usd_removerelationshiptarget

```vex
// Remove the sphere from cube's relationship.usd_removerelationshiptarget(0,"/geo/cube","relationship_name","/geo/sphere");
```

Signature: // Remove the sphere from cube's relationship.usd_removerelationshiptarget(0,"/geo/cube","relationship_name","/geo/sphere");

A handle to the stage to write to.

### usd_setcollectionexcludes

```vex
// Set the exludes list on the cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_setcollectionexcludes(0,collection_path,array("/geo/sphere4","/geo/sphere5"));
```

Signature: // Set the exludes list on the cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_setcollectionexcludes(0,collection_path,array("/geo/sph....

### usd_setcollectionexpansionrule

```vex
// Set the expansion rule on the cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_setcollectionexpansionrule(0,collection_foo,"explicitOnly");
```

Signature: // Set the expansion rule on the cube's collection.stringcollection_path=usd_makecollectionpath(0,"/geo/cube","some_collection");usd_setcollectionexpansionrule(0,collection_foo,"explicit....

### usd_setdrawmode

```vex
// Set the sphere to draw as bounds and the cube to draw as default.usd_setdrawmode(0,"/geo/sphere","bounds");usd_setdrawmode(0,"/geo/cube","default");
```

Signature: // Set the sphere to draw as bounds and the cube to draw as default.usd_setdrawmode(0,"/geo/sphere","bounds");usd_setdrawmode(0,"/geo/cube","default");

A handle to the stage to write to.

### usd_setprimvarelement

```vex
// Set the value of an element at index 2 in the array primvar.usd_setprimvarelement(0,"/geo/sphere","float_arr_primvar",2,0.25);
```

Signature: // Set the value of an element at index 2 in the array primvar.usd_setprimvarelement(0,"/geo/sphere","float_arr_primvar",2,0.25);

A handle to the stage to write to.

### usd_setprimvarelementsize

```vex
// Set the primvar's element size to 2.usd_setprimvarelementsize(0,"/geo/mesh","primvar_name",2);
```

Signature: // Set the primvar's element size to 2.usd_setprimvarelementsize(0,"/geo/mesh","primvar_name",2);

A handle to the stage to write to.

### usd_setprimvarindices

```vex
// Set the primvar's value and indices.floatvalues[]  =array(0,100,200,300,400,500);intindices[] =array(5,5,4,4,3,3,2,2,1,1,0,0);usd_setprimvar(0,"/geo/mesh","primvar_name",values);usd_setprimvarindices(0,"/geo/mesh","primvar_name",indices);
```

Signature: // Set the primvar's value and indices.floatvalues[]  =array(0,100,200,300,400,500);intindices[] =array(5,5,4,4,3,3,2,2,1,1,0,0);usd_setprimvar(0,"/geo/mesh","primvar_name",values);usd_s....

### usd_setprimvarinterpolation

```vex
// Set the primvar's interpolation style.usd_setprimvarinterpolation(0,"/geo/mesh","primvar_name","faceVarying");
```

Signature: // Set the primvar's interpolation style.usd_setprimvarinterpolation(0,"/geo/mesh","primvar_name","faceVarying");

A handle to the stage to write to.

### usd_settransformorder

```vex
stringops[] ={"xformOp:translate:xform_cube_t","xformOp:rotateZ:xform_cube_r","xformOp:rotateXYZ:xform_cube_r","xformOp:scale:xform_cube_s"};usd_settransformorder(0,"/geo/cube",ops);
```

Signature: stringops[] ={"xformOp:translate:xform_cube_t","xformOp:rotateZ:xform_cube_r","xformOp:rotateXYZ:xform_cube_r","xformOp:scale:xform_cube_s"};usd_settransformorder(0,"/geo/cube",ops);

A ....

### usd_transformname

```vex
// Construct a full name for a translation operation with suffix "cone_pivot"stringpivot_xform_name=usd_transformname(USD_XFORM_TRANSLATE,"cone_pivot");
```

Signature: // Construct a full name for a translation operation with suffix "cone_pivot"stringpivot_xform_name=usd_transformname(USD_XFORM_TRANSLATE,"cone_pivot");

The numerical code for the trans....

### usd_transformorder

```vex
// Get the cube's transform order.stringcube_xform_ops[] =usd_transformorder(0,"/geo/cube");
```

Signature: // Get the cube's transform order.stringcube_xform_ops[] =usd_transformorder(0,"/geo/cube");

When running in the context of a node (such as a wrangle LOP), this argument can be an integ....

### usd_transformsuffix

```vex
// Get the suffix of the first transform operation on the cubestringcube_xform_ops[] =usd_transformorder(0,"/geo/cube");stringsuffix=usd_transformsuffix(cube_xform_ops[0]);
```

Signature: // Get the suffix of the first transform operation on the cubestringcube_xform_ops[] =usd_transformorder(0,"/geo/cube");stringsuffix=usd_transformsuffix(cube_xform_ops[0]);

The full nam....

### usd_transformtype

```vex
// Get the type of the first transform operation on the cubestringcube_xform_ops[] =usd_transformorder(0,"/geo/cube");inttype=usd_transformtype(cube_xform_ops[0]);
```

Signature: // Get the type of the first transform operation on the cubestringcube_xform_ops[] =usd_transformorder(0,"/geo/cube");inttype=usd_transformtype(cube_xform_ops[0]);

The full name of the ....

### usd_variants

```vex
// Get the variants in the variant set "shapes" on a "shape_shifter" primitive.stringvariants[] =usd_variants(0,"/geo/shape_shifter","shapes");
```

Signature: // Get the variants in the variant set "shapes" on a "shape_shifter" primitive.stringvariants[] =usd_variants(0,"/geo/shape_shifter","shapes");

When running in the context of a node (su....

### usd_variantselection

```vex
// Get the currently selected variant in the variant set "shapes" on a "shape_shifter" primitive.stringselected_variant=usd_variantselection(0,"/geo/shape_shifter","shapes");
```

Signature: // Get the currently selected variant in the variant set "shapes" on a "shape_shifter" primitive.stringselected_variant=usd_variantselection(0,"/geo/shape_shifter","shapes");

When runni....

### usd_worldtransform

```vex
// Get the cube's world transform.matrixcube_world_xform=usd_worldtransform(0,"/src/cube");
```

Signature: // Get the cube's world transform.matrixcube_world_xform=usd_worldtransform(0,"/src/cube");

When running in the context of a node (such as a wrangle LOP), this argument can be an intege....

### volumesmoothsample

```vex
vectorP={1.0,2.0,3.0};vectorgrad;matrix3hess;floatval1=volumesmoothsample(0,"density",P,grad,hess);vectoru={0.1,0.01,0.001};floatval2=volumesmoothsample(0,"density",P+u);// By Taylor expansion we have:// `val1 + dot(u, grad)` is approximately equal to `val2`// And the second order approximation:// `val1 + (u, grad) + 0.5 * dot(u, u*hess)`// is appriximately equal to `val2`
```

Signature: vectorP={1.0,2.0,3.0};vectorgrad;matrix3hess;floatval1=volumesmoothsample(0,"density",P,grad,hess);vectoru={0.1,0.01,0.001};floatval2=volumesmoothsample(0,"density",P+u);// By Taylor exp....

### TASK: extract_attributes

```vex
float density = point(1, "density", @ptnum);
@Cd = fit(density, 0, 1, {0,0,1}, {1,0,0});
@pscale = ch("scale") * density;
```

**Purpose:** Identify all attributes read from and written to.

**Input Schema:**

**Output Schema:**

**Identification Rules:**

1.

## Advanced (127 examples)

### Rotate with a matrix â

```vex
// create a matrix
matrix3 m = ident();

// rotate the matrix
vector axis = {0,0,1};
float angle = radians(ch('amount'));

rotate(m, angle, axis);
// ...
```

That all works, but gets a little tricky if you want to do rotations that aren't perfectly aligned on the x/y/z axis.

### Get transform of objects with optransform â

```vex
matrix m = optransform('/obj/cam1');
@P *=m;
```

Download scene: Download file: optransform_pig.hipnc

Copy positions from points to other points is easy enough, but if you want to read the transform of, say, a camera, the naive way might be to c....

### optransform to do a motion control style camera â

```vex
matrix m = optransform('/obj/moving_cube');
@P *= invert(m);
```

Download scene: Download file: moco_example_scene.hip

Question Gary Jaeger asked on the Sidefx list, its something I've had at the back of my mind for years, finally got a chance to try it out.

W....

### Convert N to Orient with dihedral â

```vex
matrix3 m = dihedral( {0,0,1} , @N);
@orient = quaternion(m);
```

You have some geo that you want to copy onto points, matching @N, but save this as @orient so it won't be ambiguous.

The copy sop assumes your geo points down the z-axis, so you need to work out h....

### Convert N and Up to Orient with maketransform â

```vex
lookat(vector from, vector to, vector up);
```

Swapping between @N+@up and @orient, looks identical, hooray!

Download scene: Download file: convert_n_and_up_to_orient.hipnc

'Hang on' you might say, 'how is the previous solution not ambiguous?'.

### Copies to sit on a surface, with random rotation, with orient â

```vex
matrix3 m = dihedral({0,1,0},@N);
rotate(m, @Time+rand(@ptnum)*ch('rot_rand'), @N);
@orient = quaternion(m);
```

Download scene: Download file: rotate_around_n.hipnc

Trees on a lumpy terrain, pigs on a bigger pig, graphic chickens on a sphere, usual drill.

### Scaling with vex and matrices â

```vex
matrix3 m = ident();
scale(m,chv('scale'));
@P *= m;
```

Download scene: Download file: vex_matrix_scale.hipnc

There's lots of ways of course, here's probably the simplest way if you have polygons:

First we define an empty matrix with ident().

### Exercises â

```vex
// spirally seaweed using sin and cos
 vector offset, pos;
 int pr, pt;
 float stepsize;
 float x, y, inc;
 pr = addprim(0,'polyline');
 stepsize = 0.5;

// ...
```

The seaweed example above doesn't lock the roots in place, fix that.

### Copy sop basics â

```vex
@pscale = ch('pscale');
```

Back to the trusty grid, create a box, copytopoints sop, connect the box to the first input of the copy sop, and wrangle to the second:

If you display the copy sop, you get the expected result; a ....

### Vectors and set â

```vex
@scale = {1, 5 , 2.2};
```

I covered this earlier, but worth a refresher as we'll use it today.

### Joy of Vex Day 16 â

```vex
@Cd = @N;
 if (min(@Cd)<0) {
  @Cd = 0.1;
 }
```

copy sop, midweight instance attributes (scale, N)

More tricks with attributes and the copy sop!

This time to make it a little easier to visualise, we'll make a colour coded cube that's scaled do....

### Orient via N and up â

```vex
@N = {0,1,0};
 float s = sin(@Time);
 float c = cos(@Time);
 @up = set(s,0,c);

 @orient = quaternion(maketransform(@N, @up));
```

So we've defined @orient via angle and axis, and axis+length of axis, what else? Well, we used @N and @up previously to define a stable rotation, surely there's a way to port that to a quaternion.

### Orient via euler values â

```vex
vector rot = radians(chv('euler'));
 @orient = eulertoquaternion( rot, 0);
```

You might want to define orient in terms of '30 degrees, around x, 10 around y, -23 around z', as if you were rotating things using a transform sop or the high level transform controls on objects.

### Convert back to matrix â

```vex
matrix m = qconvert(@orient);
```

Hopefully by now you're getting the concept that quaternions are a handy black box of rotation.

### Intrinsics â

```vex
matrix3 m = {1,0,0,0,1,0,0,0,1};
```

Create a primitive sphere (as in the default sphere type, none of the poly or nurbs types).

### Intrinsics vs orient and scale â

```vex
@orient = quaternion({0,1,0}*@Time);
 v@scale = {1,0.5,1.5};

 matrix3 m = ident();
 scale(m, @scale);
 m *= qconvert(@orient);

 setprimintrinsic(0,'transform',@ptnum,m);
```

What happens then if we apply @scale and @orient to this sphere?

I'll tell you; nothing.

### Transform vs Packedfulltransform â

```vex
matrix3 m = matrix3( myfancy4x4matrix);
```

The transform intrinsic is a matrix3, is read/write, and contains the rotation and scale for your primitive.

If you have packed geo, there'll be a packedfulltransform intrinsic.

### Primuv â

```vex
vector uv = chv('uv');

 @P = primuv(1,'P',0,uv);
 @N = primuv(1,'N',0,uv);
```

How do you stick things to geometry in vex? We learned about minpos earlier, but thats not really sticking as much as finding the closest position.

To properly stick stuff you use primuv .

### Setting Orientation with Quaternions

```vex
float angle = ch('angle');
vector axis = chv('axis');

@orient = quaternion(angle, axis);
```

Creates a quaternion from a channel-driven angle and axis vector, then assigns it to the orient attribute to lock geometry instances in a specific orientation.

### Quaternion Axis Magnitude Issues

```vex
float angle1;
vector axis1;

angle = ch('angle');
axis1 = chv('axis1')-chv('offset');
angle += 2*(int * ch('speed'));
axis = chv('axis');

// ...
```

Demonstrates how the magnitude of the axis vector affects quaternion rotation behavior, causing non-uniform rotational speed.

### Quaternion Rotation with Normalization

```vex
float angle;
vector axis;

angle = ch('angle');
angle = @primnum*ch('offset');
angle += @Time * ch('speed');
axis = chv('axis');

// ...
```

Creates quaternion-based rotation using angle and axis, with per-primitive offset and time-based animation.

### Quaternion Orient with Normalized Axis

```vex
float angle;
vector axis;

angle = ch('angle');
angle *= optime * ch('offset');
angle *= fit01(rand(@ptnum));

axis = chv('axis');
// ...
```

This code creates per-point orientation quaternions by computing a randomized angle (scaled by time and point number) and normalizing a user-defined axis vector.

### Quaternion Rotation with Multiple Time Offsets

```vex
float angle;
vector axis;

angle = ch('angle');
angle += @ptnum * ch('offset');
angle += @Time * ch('speed');

axis = chv('axis');
// ...
```

Creates quaternion-based rotation using three angle components: a base angle from a channel, an offset multiplied by point number for per-point variation, and a time-based component for animation.

### Vector to Quaternion Conversion

```vex
vector axis1;
axis1 = chv('axis');
axis1 = normalize(axis1);
axis1 = @P * me;

@orient = quaternion(axis1);
```

Demonstrates creating a quaternion orientation from a normalized vector axis.

### Noise-Based Orientation with Quaternions

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= trunc(noise(@P*@Frame)*4)*$PI/2;

@orient = quaternion(axis);
```

Replaces rand() with noise(@P*@Frame) to create spatially coherent, time-animated rotation axes for quaternion orientations.

### Quaternion rotation from noise

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = chramp('noise_range', @P);
axis *= trunc(@a * 4) * chi('i') / 2;

@orient = quaternion(axis);
```

Creates a quaternion orientation by sampling a noise ramp, quantizing the value using trunc(), and applying it to a normalized axis vector.

### Quaternion Blending with SLERP

```vex
vector rot = radians(chv('euler'));
@orient = eulertoquaternion(rot, 0);

vector4 a = {0,0,0,1};
vector4 b = quaternion(0,1,0,$PI/2);
@orient = slerp(a, b, ch('blend'));

vector4 a = {0,0,0,1};
// ...
```

Demonstrates converting Euler angles to quaternions using eulertoquaternion() with rotation order parameter (0=XYZ), then shows how to blend between two quaternion orientations using slerp().

### Quaternion Interpolation with Ramps

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
float blend = @Time%1;
@orient = slerp(a, b, blend);

// Alternate version with channel ramp:
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
// ...
```

Demonstrates quaternion interpolation using slerp() with different blend methods: modulo operator for cyclic snapping behavior, and chramp() to control interpolation with a custom ramp.

### Quaternion Slerp with Ramps

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$F/2);
float blend = chramp('blendmap',@Time);
@orient = slerp(a, b, blend);

vector4 target, base;
vector axis;
float seed, blend;
// ...
```

Demonstrates spherical linear interpolation (slerp) between quaternions using ramp parameters for blend control.

### Quaternion Slerp with Noise Animation

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@ptnum);
seed = chramp('noise_remap', seed);
// ...
```

Creates smooth animated rotation by using slerp to interpolate between identity orientation and a per-point random target rotation.

### Smooth Quaternion Rotation with Slerp

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = {0,1,0};
axis = normalize(axis);
seed = chramp(@ptnum);
seed = chramp('noise_rerrange', seed);
// ...
```

Uses slerp (spherical linear interpolation) to smoothly interpolate between a base quaternion identity and random target rotations over time.

### Quaternion Slerp with Noise Remap

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = chramp('noise_remap', seed);
axis = trunc(seed) * $PI / 2;
// ...
```

Creates a quaternion orientation by normalizing an axis vector from a channel parameter, remapping a seed value through a ramp, and using spherical linear interpolation (slerp) to blend between a b....

### Quaternion rotation with noise seed

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@P + @Time);
seed = chramp('noise_rerange', seed);
// ...
```

Creates animated orientation by building a quaternion from an axis-angle representation where the angle is driven by noise remapped through a ramp.

### Quaternion Animation with Slerp

```vex
// attribute Wrangle pointwrangle1

vector axis = chv('axis');
axis = normalize(axis);
float seed = noise(@ptnum + @Time);
seed = chramp('noise_range', seed);
float angle = trunc(seed * 4) * (PI / 2);

// ...
```

Creates animated quaternion rotations using slerp interpolation between a base orientation and a target quaternion.

### Quaternion slerp with ramp blend

```vex
@attribute Wrangle1_pointwrangle1

base = {0,0,0,1};
blend = chramp('colors', @Time % 1);

@orient = slerp(base, target, blend);
```

Uses slerp to interpolate between a base quaternion and a target quaternion based on a time-driven color ramp value.

### Quaternion SLERP Blending

```vex
v@Cd = set(rand(@ptnum), rand(@ptnum+1), rand(@ptnum+2));
vector4 base = set(0, 0, 0, 1);
float blend = chramp('angle', @Time % 1);

@orient = slerp(base, target, blend);
```

Demonstrates spherical linear interpolation (SLERP) between quaternions using a ramp parameter to control the blend factor.

### Quaternion Slerp Animation with Noise

```vex
float blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@ptnum, @Time);
seed = chramp('noise_remap', seed);
axis *= trunc(seed*2)*$PI/2;

// ...
```

Creates animated quaternion rotations using slerp interpolation between a base identity quaternion and a target orientation.

### Quaternion Interpolation with Noise

```vex
i[]@attribute0;
s[]@attribute1;

axis = normalize(axis);
seed = noise(@Frame);
seed = chramp('noise_range', seed);
axis = trunc(seed*3)*axis;

// ...
```

Uses noise and ramps to create animated quaternion rotations by generating random axis selections through truncated noise values.

### Quaternion Slerp with Noise-Based Rotation

```vex
axis = normalize(axis);
seed = noise(0*@Time);
seed = chramp('noise_rcramp',seed);
axis *= trunc(seed*5)*@P/7;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim',@Frame%);
// ...
```

Demonstrates spherical linear interpolation (slerp) between a base identity quaternion and a target rotation derived from noise-modulated axis vectors.

### Quaternion Slerp Animation

```vex
axis = normalize(axis);
seed = chrand(0*@Time);
seed = chramp('noise_rexramp',seed);
axis *= trunc(seed*4)*@P/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim',@Time%1);
// ...
```

Creates animated quaternion orientations by interpolating between a base quaternion and a randomized target quaternion using slerp.

### Quaternion SLERP Animation with Noise

```vex
axis = normalize(axis);
seed = noise(@Time);
seed = chramp('noise_rerange',seed);
axis *= trunc(seed*2)*$PI/2;

target = quaternion(axis);
base = {0,0,0,1};
blend = chramp('anim',@Time%1);
// ...
```

This code animates orientation using spherical linear interpolation (slerp) between a base quaternion and a target quaternion derived from a noise-driven axis.

### Quaternion Transformations and Layering

```vex
@v = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@v,@up));

vector4 extrarot = quaternion($PI/2, {1,0,0});
```

Creates a base orientation quaternion by normalizing point position as direction vector and using maketransform with an up vector, then prepares an additional quaternion rotation of 90 degrees arou....

### Quaternion Orient Setup with Extra Rotation

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N,@up));

vector4 extrarot = quaternion($PI/2, {1,0,0});
```

Creates an orientation quaternion for each point by building a transform matrix from normalized position as normal and world up vector, then stores it in @orient attribute.

### Quaternion Rotation Composition

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));

vector4 extrarot = quaternion($PI/2, {1,0,0});

@orient = qmultiply(@orient, extrarot);
```

Creates an orientation quaternion from normalized position vectors using maketransform, then applies an additional 90-degree rotation around the X-axis using qmultiply.

### Quaternion Multiplication for Compound Rotations

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N,@up));

vector4 extrarot = quaternion($PI/2, {1,0,0});

@orient = qmultiply(@orient, extrarot);
```

Creates a base orientation quaternion from normalized position and up vector, then defines an additional 90-degree rotation around the X-axis.

### Quaternion Extra Rotation

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(PI/2, {1,0,0});
```

Creates a quaternion representing a 90-degree rotation around the x-axis using the quaternion() function with PI/2 as the angle and (1,0,0) as the axis.

### Combining Quaternion Rotations

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N,@up));
vector4 extrarot = quaternion($F/2, {1,0,0});

@orient = qmultiply(@orient, extrarot);
```

Creates a base orientation using normalized position as normal direction, then applies an additional animated rotation around the X-axis using quaternion multiplication.

### Quaternion Rotation Multiplication

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(PI/2, {1,0,0});
@orient = qmultiply(@orient, extrarot);

// Alternative with channel reference:
vector h, up;
// ...
```

Demonstrates multiplying quaternions using qmultiply() to apply an additional 90-degree rotation to orientation attributes.

### Quaternion Rotation Combination

```vex
vector N, up;
N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N,up));
vector4 extrarot = quaternion(radians(90), {1,0,0});

@orient = qmultiply(@orient, extrarot);
```

Creates an orientation quaternion from a transform matrix based on normalized position, then applies an additional 90-degree rotation around the X-axis using quaternion multiplication.

### Parametric Rotation with Quaternions

```vex
@N = normalize(@P);
vector up = {0,1,0};
@orient = quaternion(maketransform(@N, up));
vector4 extrarot = quaternion(radians(ch("angle")), {1,0,0});
@orient = qmultiply(@orient, extrarot);
```

Creates an orientation quaternion from a transform matrix built from normalized position and up vector, then applies an additional rotation around the X-axis controlled by an angle parameter slider.

### Parameterized Quaternion Rotation with Slider

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(radians(chf("angle")), {1,0,0});
@orient = qmultiply(@orient, extrarot);
```

Creates an orientation quaternion from normalized position as normal and up vector, then applies an additional rotation controlled by an angle parameter slider.

### Quaternion Rotation with Channel Parameter

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extratrot = quaternion(radians(ch("angle")), {1,0,0});

@orient = qmultiply(@orient, extratrot);
```

Creates an orientation quaternion using normalized point position as normal vector and an up vector, then applies an additional rotation controlled by a channel parameter.

### Animated Head Shake with Quaternions

```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@id), {1,0,0});
headshake = quaternion(radians(2*@id) * sin(@Time*3), {0,1,0});
// ...
```

Creates an animated head shake rotation by combining quaternions.

### Combining Multiple Quaternion Rotations

```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@P.x), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
// ...
```

Demonstrates chaining multiple quaternion rotations together using qmultiply.

### Quaternion Rotation Composition

```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(20), {1,0,0});
headshake = quaternion(radians(20) * sin(@Frame*3), {0,1,0});
// ...
```

Demonstrates composing multiple quaternion rotations by successively multiplying them with qmultiply().

### Combining Quaternion Rotations

```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin(@Frame*3), {0,1,0});
// ...
```

Demonstrates how to combine multiple quaternion rotations using qmultiply() by successively multiplying rotations into the @orient attribute.

### Combining quaternion rotations

```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@D), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
// ...
```

Demonstrates combining multiple quaternion rotations by successively calling qmultiply on the @orient attribute.

### Quaternion Rotations with Wobble

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@D), {1,0,0});
headshake = quaternion(radians(20) * sin(chf("Time")*3), {0,1,0});
// ...
```

Creates a quaternion-based orientation system for points by establishing a local transform from normalized position and up vector, then applies multiple rotation layers: a pitch rotation based on @....

### Quaternion Rotations with Wobble

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@Frame), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
// ...
```

Combines multiple quaternion rotations to create complex animated orientation on points.

### Quaternion Wobble with Curl Noise

```vex
vector h, up;
vector4 extrarot, headshake, wobble;

h = normalize(@P);
up = {0, 1, 0};
@orient = quaternion(maketransform(h, up));
extrarot = quaternion(radians(90), {1, 0, 0});
headshake = quaternion(radians(20) * sin(@Time * 3), {0, 1, 0});
// ...
```

Adds a wobble rotation to oriented geometry by creating a quaternion from curl noise based on point position plus time, then multiplying it with the existing orientation quaternions.

### Per-Point Time Offset in Quaternion Animation

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@D), {1,0,0});
headshake = quaternion(radians(20) * sin((@TimeInc + @ptnum) * 3), {0,1,0});
// ...
```

Demonstrates using per-point time offsets by adding @ptnum to @TimeInc in the headshake quaternion calculation, creating varied shaking motion across copied instances.

### Quaternion Composition and Rotation

```vex
vector N, up;
vector@ extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N), {0,1,0});
headshake = quaternion(radians(20) * sin((@Time+chsraw(0))*3), {0,1,0});
// ...
```

Demonstrates composing multiple quaternion rotations by creating separate quaternions for base orientation, extra rotation from normals, animated headshake, and curl noise wobble, then combining th....

### Converting Quaternions to Matrices

```vex
vector R, up;
vector4 extrarot, headshake, wobble;

R = normalize(@P);
N = {0,1,0};
@orient = maketransform(N, up);
extrarot = quaternion(radians(90), {1,0,0});

// ...
```

Demonstrates building complex quaternion rotations through multiplication (base orientation, 90-degree rotation, time-based headshake, and noise-based wobble), then converting the final quaternion ....

### Converting Quaternions to Matrices

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,0,1};
@orient = maketransform(N, up);
extrarot = quaternion(radians(ch("tilt")), {1,0,0});
headshake = quaternion(radians(20) * sin((@Frame*@ptnum)*3), {0,1,0});
// ...
```

Demonstrates converting a quaternion orientation to a matrix using qconvert().

### Matrix assignment from quaternion

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@x), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*chv("m")*3), {0,1,0});
// ...
```

Converts a quaternion rotation (stored in @orient) to a matrix and assigns it to a matrix3 attribute for visualization in the geometry spreadsheet.

### Converting Quaternion to Matrix

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(chf("s")), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time*chf("s"))*3), {0,1,0});
// ...
```

Converts a quaternion orientation into a matrix attribute for inspection.

### Converting quaternions to matrix

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin((@TimeInc * @chs("speed")) * 3), {0,1,0});
// ...
```

Demonstrates converting a quaternion orientation (built from multiple rotation layers) into a matrix representation using qconvert().

### Quaternion Orientation with Multiple Rotations

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@N.x), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time + @ptnum) * 3), {0,1,0});
// ...
```

Creates complex orientation behavior by building a base quaternion from normalized position and up vector, then applies three additional rotations (extra rotation, animated headshake, and curl nois....

### Converting Quaternions to Matrix

```vex
vector N, up;
vector4 extract, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extract = quaternion(radians(M), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time+@ptnum)*3), {0,1,0});
// ...
```

Demonstrates converting a compound quaternion rotation (built from multiple quaternion multiplications) into a matrix using qconvert().

### Converting Quaternions to Normals via Matrix

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@P), {1,0,0});
headshake = quaternion(radians(20) * sin((@TimeInc+chv("hs"))*3), {0,1,0});
// ...
```

Converts a quaternion orientation to a normal vector by first converting the quaternion to a 3x3 matrix using qconvert(), then multiplying a base vector {0,0,1} by that matrix to transform it.

### Quaternion Animation with Multiple Rotations

```vex
vector N, up;
vector@ extract, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extract = quaternion(radians(@N), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time), {0,1,0});
// ...
```

Creates a compound quaternion rotation by building a base orientation from point position, then multiplying it with three separate rotation quaternions: one extracted from point normal, one for a t....

### Quaternion Orientation with Noise Wobble

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@Frame), {1,0,0});
headshake = quaternion(radians(20) * sin((@TimeInc*chf("speed"))*3), {0,1,0});
// ...
```

Creates complex orientation using quaternion composition with three rotation layers: a base orientation from normalized position, an X-axis rotation, a sinusoidal Y-axis headshake, and a curl noise....

### Extracting Axes from Quaternion Orientation

```vex
matrix3 m = qconvert(@orient);
vector n = normalize(v@orient);
@N = normalize(m[2]); // z axis
@up = normalize(m[1]); // y axis
```

Demonstrates extracting directional vectors from a quaternion orientation by converting to a matrix3 and accessing its rows directly.

### Extracting Axes from Quaternion Matrix

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@R), {1,0,0});
headshake = quaternion(radians(2.0) * sin((@TimeInc+chv("hs"))*3), {0,1,0});
// ...
```

Converts the final quaternion orientation to a matrix3 and extracts directional axes by multiplying canonical basis vectors with the rotation matrix.

### Quaternion Rotations with Multiple Transforms

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@X), {1,0,0});
headshake = quaternion(radians(2*@Z) * sin((@Time+ch("offset"))*3), {0,1,0});
// ...
```

Creates a base orientation using maketransform from normalized position and up vector, then applies three additional rotations via quaternion multiplication: extrarot based on X position, headshake....

### Identity Matrix Initialization

```vex
matrix3 m = ident();
```

The ident() function creates an identity matrix (no rotation, no scaling) - equivalent to a transform in world space with all diagonal values as 1 and all other values as 0.

### Orient and Scale Matrix Transform

```vex
@orient = quaternion(0, 1, 0);
v@scale = {1, 1, 1};

matrix3 m = ident();
scale(m, @scale);
m *= qconvert(@orient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Creates a quaternion orientation attribute and scale vector, then builds a 3x3 transformation matrix by starting with an identity matrix, applying scale, and multiplying by the converted quaternion.

### Matrix Transform with Quaternion and Scale

```vex
@orient = quaternion({0,1,0} * @Time);
v@scale = {1, 0.5, 1.5};

matrix3 m = ident();
scale(m, @scale);
m *= qconvert(@orient);

setprimintrinsic(0, 'transform', @primnum, m);
```

Creates a primitive transformation matrix by combining non-uniform scaling with a time-based rotation quaternion.

### Transform Matrix with Orient and Scale

```vex
@orient = quaternion({0,1,0} * @Time);
@scale = {1, 0.5, 2};

matrix m = ident();
scale(m, @scale);
m *= qconvert(@orient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Creates a transform matrix by combining orientation and scale attributes.

### In-place Matrix Transform with Orient

```vex
@orient = quaternion({0,1,0} * @Time);
vscale = {1, 0.3, 2};

matrix m = ident();
scale(m, vscale);
m *= 4@orient;

setprimintrinsic(0, 'transform', @ptnum, m);
```

Demonstrates constructing a transformation matrix by combining scale and orientation quaternion, then applying it to a primitive's transform intrinsic.

### Matrix Scale and Quaternion Transform

```vex
qorient = quaternion({0,1,0} * @Time);
vscale = {1, 0.5, 2};

matrix m = ident();
scale(m, vscale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Creates a transformation matrix by starting with an identity matrix, applying a non-uniform scale, then multiplying by a quaternion rotation converted to matrix form.

### Matrix Transform with Primitives

```vex
qorient = quaternion({0,1,0} * @Time);
v@scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, v@scale);
m *= dconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Constructs a transformation matrix by combining scale and rotation (from quaternion) operations, then applies it to the 'transform' primitive intrinsic.

### Matrix Construction from Instance Attributes

```vex
qorient = quaternion({0,1,0} * @Time);
v@scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, v@scale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Demonstrates how to construct a transformation matrix from instance attributes (scale and quaternion rotation) and apply it to a primitive's transform intrinsic.

### Matrix Casting and Packed Transforms

```vex
matrix3 m = matrix(myFancyx4xmatrix);

matrix pft = primintrinsic(0, "packedfullTransform", @ptnum);

4@a = pft;
```

Demonstrates how to extract a packed primitive's full transform using primintrinsic() and cast a 4x4 matrix to a 3x3 matrix using the matrix() constructor.

### Matrix casting and primitive transforms

```vex
qorient = quaternion({0,1,0} * @Time);
vscale = {1, 0.5, 2};

matrix m = ident();
scale(m, vscale);
m *= qconvert(qorient);

setprimintrinsic(0, "transform", @ptnum, m);
```

Creates a rotation quaternion based on time, applies non-uniform scaling to an identity matrix, then converts and multiplies the quaternion rotation into the matrix.

### Matrix Transform with Quaternion Orientation

```vex
qorient = quaternion({0,1,0} * 2*$TAU);
vqscale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, vqscale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Creates a 3x3 transformation matrix by combining a quaternion rotation and a scale vector.

### Casting Matrix4 to Matrix3 Transform

```vex
qorient = quaternion({0,1,0} * @Time);
@vscale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, @vscale);
m *= qconvert(qorient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Demonstrates reading a primitive's transform intrinsic as a matrix4 and converting it to matrix3 for manipulation.

### Matrix Structure and Components

```vex
// Example 4x4 transformation matrix structure
matrix m = {0.365308, 0.584615, -0.121554, 0.0,
            -0.534593, 0.478389, 0.696304, 0.0,
            0.663726, -0.27805, 0.696304, 0.0,
            0.0, 0.0, 0.0, 1.0};

// First 3x3 block contains rotation and scale
// Last column (indices 3,7,11) contains translation
// ...
```

A 4x4 transformation matrix in VEX is structured with the upper-left 3x3 block containing rotation and scale information, while the fourth column (indices 3, 7, 11) contains the translation values ....

### Extracting Rotation and Scale from Matrix

```vex
matrix3 rotandscale = matrix3(xf());
```

Creates a 3x3 matrix by extracting the rotation and scale components from a 4x4 transformation matrix.

### Extracting rotation and scale from 4x4 matrix

```vex
f[]@matrix3 = {0.54813, -0.13154, 0.0, 0.034593, 0.478835, 0.006364, 0.0, 0.066738, 0.27055, 0.006364, 0.0, 0.0, 0.0, 0.0, 1.0};
```

This declares a float array attribute containing 15 values representing a flattened 4x4 transformation matrix.

### Extracting Rotation and Scale from Packed Transform

```vex
matrix pft = primintrinsic(0, 'packedfulltranosform', @ptnum);
4@a = pft;

matrix3 rotandscale = matrix3(pft);
```

Retrieves the full transformation matrix from a packed primitive using primintrinsic, stores it in a 4x4 matrix attribute, then extracts just the rotation and scale components by converting to a ma....

### Extracting Rotation and Scale from Packed Transform

```vex
matrix pft = printintrinsic(0, "packedfulltramsform", @ptnum);
@Ga = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```

Demonstrates extracting a packed primitive's full transform as a matrix, storing it in a matrix attribute, then casting it to a matrix3 to isolate just the rotation and scale components (discarding....

### Extract rotation and scale matrix3

```vex
matrix3 rotandscale = matrix3(pft);
```

Creates a matrix3 variable from a packedfulltransform (pft) matrix4, extracting only the rotation and scale components while discarding the translation.

### Extract rotation and scale from packed transform

```vex
matrix prt = primintrinsic(0, "packedfulltransform", @ptnum);
@prt = prt;

matrix3 rotandscale = matrix3(prt);
@3x3 = rotandscale;
```

Extracts the rotation and scale components from a packed primitive's full transform matrix by converting the 4x4 transform matrix to a 3x3 matrix.

### Extracting rotation and scale matrix

```vex
matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);
matrix3 rotandscale = matrix3(pft);
@P = rotandscale;
```

Extracts the 3x3 rotation and scale components from a packed primitive's full transform matrix by casting the 4x4 matrix to a matrix3.

### Extracting Rotation and Scale from Packed Transform

```vex
matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```

Retrieves the full 4x4 packed transform matrix from a packed primitive, then extracts just the 3x3 rotation and scale component by casting it to matrix3.

### Packed Primitive Intrinsics

```vex
matrix pft = primintrinsic(0, "packedfulltramsform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```

Reading the packedfulltramsform intrinsic returns a matrix containing the complete transformation of a packed primitive.

### Reading Packed Transform Intrinsics

```vex
matrix pft = primintrinsic(0, "packedfullransform", @ptnum);
4@a = pft;
matrix3 rotandscale = matrix3(pft);
3@b = rotandscale;
```

Demonstrates reading the 'packedfullransform' intrinsic from packed geometry using primintrinsic() to extract the full 4x4 transform matrix, then converting it to a matrix3 to isolate rotation and ....

### Orient attribute with dihedral

```vex
float d = length(@P);
float t = @Time - d * chi('offset');
v@up = set(sin(t), 0, cos(t));
@orient = dihedral({1,0,0}, v@up);
```

Calculates an orient quaternion attribute by determining the rotation needed to align the X-axis with a dynamically computed up vector.

### Quaternion Axis-Angle Rotation

```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis = {1,0,0};

@orient = quaternion(axis);
```

Demonstrates creating a quaternion orientation from an axis vector using the quaternion() constructor.

### Quaternion from Matrix Transform

```vex
vector axis = trunc(@P * @P.y);
vector @N = @P;

@orient = quaternion(axis);

float s = sin(@Time);
float c = cos(@Time);
vector @up = set(s, 0, c);
// ...
```

Demonstrates multiple approaches to creating quaternion orientations, including building them from axis vectors, constructing them from custom transform matrices using maketransform() with normal a....

### Quaternion Interpolation with SLERP

```vex
vector rot = radians(chv('euler'));
@orient = eulertoquaternion(rot, 0);

vector4 a = {0,0,0,1};
vector4 b = quaternion(0,1,0)*$PI/2);
@orient = slerp(a, b, ch('blend'));

vector4 a = {0,0,0,1};
// ...
```

Demonstrates converting Euler angles to quaternions using eulertoquaternion() with rotation order parameter (0=XYZ, 1=YZX, 2=ZXY), then shows how to interpolate between two quaternions using the sl....

### Quaternion Blending with Slerp

```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * PI/2);
@orient = slerp(a, b, ch('blend'));
```

Creates two quaternions: a neutral rotation and a 90-degree rotation around the Y-axis.

### Quaternion Rotation with Noise-Driven Slerp

```vex
vector4 target, base;
vector axis;
float seed, blend;

axis = chv('axis');
axis = normalize(axis);
seed = noise(@ptnum);
seed = chramp('noise_remap', seed);
// ...
```

Creates randomized rotation orientations using quaternions by generating noise-based rotation angles per point, converting them to quaternion representations, then using spherical linear interpolat....

### Quaternion slerp with time modulation

```vex
vector4 base = {u, v, 0, x};
float blend = chramp('angle', @Time % 1);

@orient = slerp(base, target, blend);
```

Creates a smooth interpolation between base and target quaternions using slerp, with the blend factor driven by a ramp keyed to modulo time.

### Quaternion Extra Rotation Setup

```vex
v@N = normalize(v@P);
v@up = {0,1,0};
@orient = quaternion(maketransform(v@N, v@up));
vector4 extrarot = quaternion(PI/2, {1,0,0});
```

Creates an orient quaternion from normalized position vectors and an up vector using maketransform, then defines an additional quaternion representing a 90-degree rotation around the x-axis.

### Quaternion Rotation Multiplication

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(@P/2, {1,0,0});
@orient = qmultiply(@orient, extrarot);
```

Creates a base orientation quaternion from normalized position vectors, then defines an additional rotation quaternion representing a 90-degree rotation around the x-axis.

### Quaternion Rotation Composition

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));

vector4 extrarot = quaternion($PI/2, {1,0,0});

@orient = qmultiply(@orient, extrarot);

// ...
```

Demonstrates composing quaternion rotations by creating an initial orientation from a normal and up vector, then applying an additional 90-degree rotation around the X-axis using qmultiply.

### Parameterized Quaternion Rotation

```vex
@P = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extratrot = quaternion(radians(ch("angle")), 0, 0);

@orient = qmultiply(@orient, extratrot);
```

Replaces a hardcoded 90-degree rotation with a user-controllable angle parameter using a channel reference.

### Dynamic Quaternion Rotation with Channel Slider

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(radians(ch("angle")), {1,0,0});

@orient = qmultiply(@orient, extrarot);
```

Creates an orientation quaternion from normalized position and up vector, then applies an additional rotation controlled by a channel slider.

### Dynamic Quaternion Rotation Parameter

```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(radians(ch('angle')), {1,0,0});

@orient = qmultiply(@orient, extrarot);
```

Creates an interactive rotation control by replacing a hard-coded rotation value with a channel reference.

### Quaternion Head Shake Animation

```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), N);
// ...
```

Creates an animated head shake rotation by generating a quaternion based on a sine wave of time multiplied by 20 degrees.

### Quaternion multiplication for head rotation

```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@D), {1,0,0});
headshake = quaternion(radians(20) * sin(@Frame*3), {0,1,0});
// ...
```

This code creates complex rotations by multiplying quaternions together.

### Combining Quaternion Rotations

```vex
vector N, up;
vector4 extrarot, headshake;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(20), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
// ...
```

Demonstrates how to combine multiple quaternion rotations using qmultiply to create complex orientation effects.

### Quaternion Wobble with Curl Noise

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(ch("angle")), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
// ...
```

Adds a third quaternion rotation layer using curl noise to create random wobbling motion.

### Extracting Axes from Quaternion Orient

```vex
matrix3 m = qconvert(@orient);
vector axis[] = set(@N, @up);
@N = normalize(axis[2]); // z axis
@up = normalize(axis[1]); // y axis
```

Converts an orient quaternion to a matrix, then extracts and normalizes the Y and Z axes as @N and @up attributes for visualization.

### Extracting Axes from Quaternion Orientation

```vex
matrix3 m = qconvert(@orient);
vector axis[] = set(@);
@N = normalize(axis[2]); // z axis
@up = normalize(axis[1]); // y axis
```

Converts a quaternion orientation to a matrix, then extracts individual axis vectors from that matrix using array indexing.

### Converting Quaternions to Matrix Axes

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(90), {1,0,0});
headshake = quaternion(radians(20) * sin((@Time*chv("ns"))*3), {0,1,0});
// ...
```

Converts a quaternion orientation to a 3x3 matrix using qconvert, then extracts individual axis vectors from the matrix rows.

### Complex Orientation with Multiple Quaternion Rotations

```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(1), 0, 0);
headshake = quaternion(radians(20) * sin(@Time*chv("us")*3), {0,1,0});
// ...
```

Creates a complex animated orientation for eyeball geometry by combining multiple quaternion rotations: a base orientation aligned to the point normal, a small tilt, an animated headshake using sin....

### Matrix from Orient and Scale

```vex
matrix3 m = ident();
vector scale = {1, 0.5, 1};

@orient = quaternion(quaternion(0, 1, 0, 0) * @time);

m = scale(m, scale);
m = qconvert(@orient);

// ...
```

Creates a transformation matrix from orient quaternion and scale vector attributes, then applies it to primitive intrinsics.

### Matrix Transform with Orient and Scale

```vex
@orient = quaternion({0,1,0} * @Time);
v@scale = {1, 0.5, 1.5};

matrix3 m = ident();
scale(m, v@scale);

setprimintrinsic(0, 'transform', 0, m);
```

Creates a quaternion orientation based on animated Y-axis rotation, defines a non-uniform scale vector, builds an identity matrix and applies the scale to it, then assigns the transformed matrix to....

### Transform Matrix from Quaternion and Scale

```vex
@orient = quaternion({0,1,0} * @Time);
@scale = {1, 0.5, 1.5};

matrix3 m = ident();
scale(m, @scale);
m *= qconvert(@orient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Builds a transform matrix by creating an identity matrix, applying non-uniform scale, then multiplying by a rotation matrix converted from a time-animated quaternion.

### Primitive Transform with Orient and Scale

```vex
@orient = quaternion({0,1,0} * @Time);
@scale = {1, 0.3, 2};

matrix3 m = ident();
scale(m, @scale);
m *= @convert(@orient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Creates an orientation quaternion rotating around the Y-axis over time, then builds a transformation matrix by starting with identity, scaling it non-uniformly, and multiplying by the converted qua....

### Transform Intrinsic from Orient and Scale

```vex
@orient = quaternion({0,1,0} * @Time);
@scale = {1, 0.3, 2};

matrix3 m = ident();
scale(m, @scale);
m = qconvert(@orient);

setprimintrinsic(0, "transform", @ptnum, m);
```

Demonstrates constructing a matrix from instance attributes (@orient and @scale) and applying it to the transform intrinsic of packed primitives, replicating what a copy SOP would do.

### Quaternion Rotation with Scale Matrix

```vex
@orient = quaternion({0,1,0} * @Time);
vector vscale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, vscale);
m *= dconvert(@orient);

setprimintrinsic(0, 'transform', @ptnum, m);
```

Creates a time-based rotation quaternion around the Y-axis and combines it with a non-uniform scale using a matrix3.

### Reading Packed Primitive Transform

```vex
matrix pft = primintrinsic(0, "packedfullxform", @ptnum);
```

Declares a matrix variable to store the full transformation matrix of a packed primitive using primintrinsic().

### Extracting Rotation and Scale from Packed Transform

```vex
matrix pft = primintrinsic(0, "packedfulltrransform", @ptnum);
matrix3 rotandscale = matrix3(pft);
3x3 = rotandscale;
```

Demonstrates extracting a packed primitive's full transform matrix using primintrinsic(), then converting it to a matrix3 to isolate the rotation and scale components (discarding translation).

## Expert (3 examples)

### Rubiks cube â

```vex
if (randaxis==0) axis = {1,0,0};
if (randaxis==1) axis = {0,1,0};
if (randaxis==2) axis = {0,0,1};
```

Download scene: Download file: rubiks_cube.hipnc

As per usual I worked this out a while ago, forgot, took a few stabs to remember how I did it, fairly sure this method is cleaner than the original.

### Vex includes â

```vex
function float addfoo(float a; float b)
{
    float result = a + b;
    return result;
}
```

You can create libraries of functions in external files, and pull them in as you'd do in C.

To start with, make a vex/includes folder under your houdini preferences folder.

### Vector component assignment clarity

```vex
@Cd = v1;
@Cd.x = curlnoise(@P*chv('fancyscale'))*@Time;
```

Demonstrates the difference between assigning a full vector versus assigning individual components.
