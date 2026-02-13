# Joy of VEX: Color

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Color Operations

### Distance-Based Color with Sine Wave [[Ep1, 109:14](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=6554s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scalePos');
@Cd = fit(sin(d*chf('time')),-1,1,0,1);
```
Creates an animated color pattern by calculating the distance from each point to a center position, applying a sine wave modulated by time, and fitting the result to color values. The position is first scaled by a vector channel parameter, and the distance is further scaled before the sine function creates oscillating values that are remapped from [-1,1] to [0,1] for color output.

## Color from Normals

### Vectors as Color Components [[Ep1, 14:26](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=866s)]
```vex
@Cd = @P;

@Cd = @N;

@Cd = @P.x;
```
Demonstrates how vectors can be assigned to color attributes since both are three-component values. The normal vector @N (0,1,0 for upward-pointing normals) maps directly to RGB color space, resulting in green when all normals point up. On curved geometry like a sphere or pig head, varying normal directions produce different colors based on their directional components.

### Visualizing normals with color [Needs Review] [[Ep1, 14:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=896s)]
```vex
@Cd = @P;

@Cd = @N;

@Cd = @N.x;
```
Demonstrates how position (@P) and normal (@N) vectors can be visualized as RGB colors by assigning them to @Cd. When normals are assigned to color, the resulting RGB values create a visual representation similar to normal maps, with different colors indicating different vector directions. Individual components (like @N.x) can also be visualized, showing a single color channel.

## Color from Position

### Position to Color Mapping [[Ep1, 15:00](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=900s)]
```vex
@Cd = @P;

@Cd = @P.x;
```
Demonstrates mapping position (@P) directly to color (@Cd), which visualizes spatial coordinates as RGB values. The first example maps the full vector to color, while the second extracts only the X component, creating a gradient. This technique produces colors similar to normal maps, where position/direction values translate to visible color variations across the geometry.

## Color from Normals

### Mapping Attributes to Color [[Ep1, 15:40](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=940s)]
```vex
@Cd = @N;

@Cd = @P;

@Cd = @P.x;
```
Demonstrates assigning different point attributes to color (@Cd). Setting @Cd = @N creates normal-map-like colors with bluish-greenish-reddish hues based on surface orientation. Setting @Cd = @P uses world-space position values as color, which can result in negative values (over-saturated or under-saturated colors outside the 0-1 range).

## Color from Position

### Assigning Position to Color [[Ep1, 16:00](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=960s)]
```vex
@Cd = @P;

@Cd = @P;

@Cd = @P.x;
```
Demonstrates assigning position values directly to color attributes. Setting @Cd to @P maps XYZ position values to RGB color channels, creating a spatial color gradient. Accessing individual components like @P.x allows isolating specific position axes for color assignment, though this can produce invalid color values when positions are negative or out of the 0-1 range.

## Color from Normals

### Position to Color Mapping Components [[Ep1, 17:00](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1020s)]
```vex
@Cd = @P;

@Cd = @P;

@Cd = @P.x;

@Cd = @N.y;
```
Demonstrates assigning position and normal components to color attributes. When using @P for color, points maintain their color based on world-space position regardless of transforms applied to the geometry. Component access (.x, .y) allows mapping individual vector components to color values, showing how negative positions result in over-dark colors (below black).

### Position vs Normal Color Assignment [[Ep1, 17:30](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1050s)]
```vex
@Cd = @P;

@Cd = @P.x;

@Cd = @N.y;
```
Demonstrates the difference between using position (@P) versus normals (@N) for color assignment. When color is based on position, transforming geometry changes the colors, but when based on normals, colors stay relative to surface orientation regardless of transforms. Component access (.x, .y) allows isolating individual vector components for color channels.

### Color from Normals vs Position [[Ep1, 18:08](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1088s)]
```vex
@Cd = @N;

@Cd = @P;

@Cd = @P.x;

@Cd = @N.y;
```
Demonstrates the visual difference between coloring geometry by normal direction (@N) versus world position (@P). Normal-based coloring maintains consistent colors based on surface orientation even when geometry rotates, while position-based coloring stays fixed in world space. Component access (.x, .y) allows isolating individual axes for more controlled color effects.

### Vector Component Access [[Ep1, 20:30](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1230s)]
```vex
@Cd = @N.y;
```
Sets the color attribute to the Y component of the normal vector, creating a gradient based on how much the surface faces upward or downward. This technique is similar to the Mask by Feature SOP, which colors geometry based on normal direction. Accessing individual vector components (.x, .y, .z) allows you to extract scalar values from vector attributes.

### Component-Based Color Assignment [[Ep1, 21:36](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1296s)]
```vex
@Cd = @N.y;

@Cd = @P.y;

@Cd = @P.x;

@Cd = @N.y;
```
Demonstrates assigning color based on individual vector components (x or y) from position or normal attributes. Points with higher y-component values (like 0.4) will be brighter/whiter, while negative y-values will be darker/black. This creates a spatial gradient where color intensity corresponds to vertical position or normal direction.

## Color Operations

### Offsetting Color Values [[Ep1, 23:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1436s)]
```vex
@Cd = @P.x + 3;
```
Adding a constant value of 3 to the position's x-component shifts the color visualization, moving the zero-point (where color transitions from black to white) to the left into negative space. This demonstrates how arithmetic operations on positional data affect color output and can be used to visualize coordinate shifts.

## Color from Position

### Offsetting Color Values with Position [[Ep1, 26:14](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1574s)]
```vex
@Cd = (@P.x - 6) * 0.3;
```
Demonstrates offsetting color values by subtracting a constant (6) from the x-position before scaling by 0.3. This shifts the gradient so that most values fall below zero (appearing black), illustrating how grouping operations in parentheses affects value ranges. The instructor emphasizes the importance of always ending VEX statements with semicolons to avoid errors.

### Remapping Position Components to Color [[Ep1, 30:16](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1816s)]
```vex
@Cd = (@P.x-0) * 0.;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;

@Cd = @ptnum;
```
Demonstrates remapping position components to color channels in non-standard ways. Instead of mapping X to red, Y to green, and Z to blue, this code swaps the axes (Z position drives green, Y position drives blue) and applies multipliers to create different color distributions. The final line shows an alternative approach of setting color based on point number.

### Remapping Position to Color Components [[Ep1, 30:22](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1822s)]
```vex
@Cd.x = @P.x * 3 * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;
```
Demonstrates remapping position components to color channels in non-standard ways. The X position (scaled) drives red, the Z position drives green, and the Y position drives blue, creating different color patterns than a direct XYZ-to-RGB mapping. This shows how swapping and scaling position components can create varied color effects.

## Color Operations

### Color from Point Number [[Ep1, 32:46](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1966s)]
```vex
@Cd = @ptnum;

@Cd = (@P.x - 0) * 0.3;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;

@Cd.x = @P.x * 0.3 * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;

@Cd = @ptnum;
```
Setting color (@Cd) equal to point number (@ptnum) assigns each point a color value based on its index. Since point numbers range from 0 to 899, most points exceed the color value of 1 (white), resulting in only point 0 appearing black while others are blown out to white, demonstrating the need for normalization when using point numbers for color.

### Color from Point Number [[Ep1, 32:54](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1974s)]
```vex
@Cd = (@P.x-0) * 0.1;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z+2;
@Cd.z = @P.y;

@Cd.x = @P.x-1 * 1.2;
@Cd.y = @P.z+2;
@Cd.z = @P.y;

@Cd = @ptnum;
```
Demonstrates assigning point color directly from point number using @ptnum. The previous attempts using position-based color assignments result in values outside the 0-1 color range, causing most points to appear white. Using @ptnum directly assigns each point's unique index as its color value, though this also needs normalization since point numbers exceed 1.

### Point Number to Color Mapping [[Ep1, 32:58](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1978s)]
```vex
@Cd = @ptnum;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z + 2;
@Cd.z = @P.y;

@Cd = (@P.x * 0.0) * 0.3;

@Cd = @ptnum;
```
Setting color (@Cd) directly to point number (@ptnum) creates undesirable results because point numbers on a grid from 0 to 899 exceed the valid color range of 0 to 1, resulting in nearly all white points except the first one at 0 (black). The code demonstrates this problem by assigning @ptnum to color, showing that point numbers need to be normalized to create a meaningful color gradient across geometry.

### Color from Point Number [[Ep1, 33:00](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1980s)]
```vex
@Cd = @ptnum;

@Cd.x = @P.x * 1.2;
@Cd.y = @P.z + 2;
@Cd.z = @P.y;

@Cd = @ptnum;
```
Sets color attribute to the point number value, demonstrating that point numbers go from 0 to 899 in this grid. Since color values are interpreted in 0-1 range, most points appear white (values > 1), with only point 0 appearing black. This illustrates the need to normalize point numbers to create a proper color ramp across geometry.

## Color from Normals

### Type casting for normalized color values [[Ep1, 35:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2156s)]
```vex
@Cd = float(@ptnum)/@numpt;
```
Demonstrates type casting by wrapping @ptnum in float() to ensure floating-point division when dividing by @numpt. This creates a normalized gradient from 0.0 to 1.0 across all points, avoiding integer division truncation. The resulting values produce a smooth color ramp from point 0 (black) to the last point (near white).

### Normalizing point numbers with division [[Ep1, 38:06](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2286s)]
```vex
@Cd = float(@ptnum)/@numpt;

// Alternative using hardcoded value:
@Cd = float(@ptnum)/100;
```
Demonstrates how to create a gradient by dividing @ptnum by @numpt to get normalized values between 0 and 1, where @ptnum changes for each point while @numpt remains constant as the total point count. Shows that replacing @numpt with a hardcoded value like 100 changes when the gradient reaches 1 (white), with higher point numbers exceeding 1 and clamping to white in visualization.

## Color Operations

### Channel-driven Sine Wave Color [[Ep1, 48:32](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2912s)]
```vex
@Cd = sin(float(@ptnum)/ch("scale"));
```
Uses a channel reference to control the frequency of a sine wave applied to point color, allowing interactive art direction of the color pattern. The point number is cast to float, divided by a channel parameter, and passed through sin() to create smooth oscillating color values that can be adjusted in real-time via the scale parameter.

### Color with sine and channel reference [[Ep1, 48:40](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2920s)]
```vex
@Cd = sin(float(@ptnum)/ch('scale'));
```
Uses a sine wave function to create oscillating color values based on point number, divided by a channel slider named 'scale' for art-direction control. The sine function creates peaks and valleys (oscillating between -1 and 1), producing varying color patterns that can be interactively adjusted via the scale parameter.

### Distance-based Color with Sin Function [[Ep1, 65:54](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3954s)]
```vex
float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
d *= ch('scale');
@Cd = sin(d);
```
Demonstrates progressive refinement of distance-based coloring: first assigning raw distance to color, then applying sine function for oscillating patterns, and finally adding a channel reference for interactive scaling control. This shows how to iterate from simple attribute assignment to parameter-driven procedural effects.

### Distance-based color with sin wave [[Ep1, 67:08](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4028s)]
```vex
float d = length(@P);

float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
d *= ch('scale');
@Cd = sin(d);
```
Demonstrates progressive development of distance-based coloring by first calculating distance from origin using length(@P), then applying that to color, then adding a sine wave pattern, and finally making it controllable via a channel reference parameter. Each iteration builds on the previous to create increasingly complex distance-based color patterns.

### Distance-based color with sine [Needs Review] [[Ep1, 68:06](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4086s)]
```vex
float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
@Cd = ch('scale');
@Cd = sin(d);
```
Demonstrates using distance from origin to drive color values. Shows progression from direct distance assignment to applying sine function for oscillating color patterns. Introduces a channel reference, though the final code appears to have an error where the channel value overwrites the distance before applying sine.

### Remapping sine values for color [[Ep1, 71:02](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4262s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = sin(d) + 1;

float d = length(@P);
d *= ch('scale');
@Cd = sin(d);

float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)/2;
```
Demonstrates fixing negative sine values for color attributes by adding 1 to shift the range from [-1,1] to [0,2], which prevents negative color values that would cause rendering issues. The code shows the progression from unclamped sine output to adding 1 to eliminate negatives, addressing the problem that sine returns values from -1 to 1 which are invalid for color attributes.

### Distance-based color patterns with center control [Needs Review] [[Ep1, 78:40](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4720s)]
```vex
float d = length(@P) * ch('scale');
@Cd = (sin(d)+1)*0.5;

@Cd = (sin(length(@P) * ch('scale'))+1)*0.5;

float d = distance(@P, {1,0,1});
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

vector center = chv('center');
float d = distance(@P, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

vector center = chv('center');
float d = distance(@P, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```
Progression from using length() to measure distance from origin to using distance() function to measure from arbitrary points in space. The distance() function allows specifying a second point parameter, enabling measurement from custom center points rather than only the origin. Final version uses a channel reference to make the center point user-controllable via a parameter.

### Distance and spare parameters [Needs Review] [[Ep1, 88:18](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5298s)]
```vex
vector pos = @P + chv('fancyscale');
vector center = chv('center');
float dist = length(pos - center);
dist *= ch('scaleish');
@Cd = (sin(dist)) * 0.5;
```
Demonstrates calculating distance between modified point positions and a center point, then using that distance with sine function to create a color pattern. The explanation focuses on the workflow detail that changing spare parameter types requires deleting and recreating them, as Houdini won't automatically remake existing parameters.

### Time-Based Animated Color Pattern [[Ep1, 97:30](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5850s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scalePD');
@Cd = fit(sin(d), -1, 1, 0, 1);
```
Creates an animated color pattern by calculating distance from a scaled position to a center point, multiplying by a time-varying channel parameter, and mapping the sine wave result to color values. The animation evolves over time using channel references that can be driven by $T (time in seconds) or $F (frame number).

### Time-based color animation [[Ep1, 97:50](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5870s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);
```
Creates an animated color effect using the @Time attribute combined with sine waves based on distance from a center point. The @Time attribute automatically evaluates the current frame time, allowing time-varying effects without additional setup. The fit() function remaps the sine wave's -1 to 1 range into 0 to 1 for valid color values.

### Animated color with time and sine [[Ep1, 97:52](https://www.youtube.com/watch?v=9gB1zB9Lg4&t=5872s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d*@time),-1,1,0,1);
```
Creates an animated color effect by multiplying position by a scale parameter, calculating distance from a center point, and using sine of distance multiplied by time to create oscillating colors. The @time attribute provides built-in frame-based animation without needing extra setup, making it convenient for time-varying effects.

### Time-varying color with sine wave [[Ep1, 98:00](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5880s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d*@Time),-1,1,0,1);
```
Creates an animated color effect using distance from a center point and the @Time global variable. The sine function oscillates between -1 and 1 based on distance and time, which is then remapped to 0-1 using fit() to drive the color attribute. This demonstrates how to create time-varying effects without caching frames, using built-in global attributes.

## Color from Ramps

### Ramp Modulo Behavior Change [[Ep2, 50:28](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3028s)]
```vex
float d = length(@P);
d = fit(d, scale);
d = sin(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp("my_ramp", d);
@Cd *= ch("height");
```
This code creates a color pattern by computing distance from origin, applying sine waves, and sampling a color ramp. The discussion focuses on how chramp() function behavior changed - it used to automatically modulo (repeat) input values, but newer versions of Houdini require explicit fit() or wrapping to handle values outside 0-1 range. The final color is scaled by a channel parameter.

### Color Ramp with Frame Animation [[Ep2, 50:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3032s)]
```vex
float d = length(@P);
d *= ch('scale');
d = @Frame;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp('myRamp', d);
@Cd *= ch('height');
```
This example demonstrates animating color using frame number and a color ramp parameter. The code takes the current frame value, applies a sine wave to create oscillation, fits the result to 0-1 range, and uses that normalized value to sample a color ramp, with additional control parameters for scale and height. The discussion notes that ramp behavior changed in newer Houdini versions regarding how values outside 0-1 range are handled (no longer automatically modulating/repeating).

### Color Ramp with Time Animation [[Ep2, 51:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3062s)]
```vex
float d = length(@P);
d *= ch('scale');
d = @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp('myRamp', d);
@Cd.y *= ch('height');
```
Uses time-based sine wave animation to drive a color ramp lookup, sampling the ramp with a fitted sine value and modulating the green color channel. The code demonstrates how to prepare a value for ramp sampling by normalizing the oscillating sine output from [-1,1] to [0,1] range, then applies channel-based scaling to the final color result.

### Animated Color Ramp Using Point Number [[Ep2, 60:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3602s)]
```vex
float d = length(@P);
d *= ch('scale');
d = @ptnum;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp('myramp', d);
@Cd.y *= ch('height');
```
This code creates an animated color pattern by converting point numbers into a sine wave, then remapping the oscillating values through a color ramp to control the green channel of point colors. The pattern can be scaled and adjusted in height using channel parameters, demonstrating how to combine mathematical functions with UI controls for dynamic visual effects.

### Sine Wave Animation with Color Ramp [[Ep2, 60:24](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3624s)]
```vex
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
d = (d+1)*0.5;
@Cd = chramp("myRamp",d);
@P.y += ch("height");
```
Creates an animated sine wave deformation based on distance from origin, then remaps the sine values from [-1,1] to [0,1] range to drive a color ramp. The position displacement and color assignment are controlled separately, allowing the wave pattern to drive both visual color variation and vertical height offset via channel parameters.

### Shaping Sine Waves with Ramps [[Ep2, 63:28](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3808s)]
```vex
float d = length(@P);
d *= ch("scale");
d = @Time;
d = sin(d);
@Cd = set(d, d, d);
@Cd.y = chramp("myRamp", d);
@Cd.y *= ch("height");
```
This example demonstrates using a ramp parameter to shape and clip sine wave patterns applied to point colors. The sine function generates oscillating values based on time, which are then remapped through a channel ramp to control the green color channel, allowing artistic control over the wave intensity and pattern.

### Per-Primitive Ramp Offset [[Ep2, 68:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4112s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= prim;
d %= 1;
@Cd.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
Creates a radial distance-based pattern using a ramp lookup, with per-primitive offset to create repeating concentric patterns. The primitive number offset (d -= prim) causes each primitive to sample the ramp at different values, creating variation. The modulo operation ensures values stay within 0-1 range for proper ramp sampling.

### Animated Color Ramp with Height [[Ep2, 68:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4136s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp('height', d);
@P.y *= ch('height');
```
Creates an animated radial pattern by calculating distance from origin, applying sine wave with time offset, and mapping to a color ramp. The fit function normalizes the sine output to 0-1 range for the color ramp lookup, while also scaling the geometry's Y position. The modulo operation is unnecessary here because fit already constrains values to the desired range.

### Distance-Based Color Ramp with Height [[Ep2, 69:22](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4162s)]
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
This code calculates distance from origin, applies modulo for repeating patterns, and uses sine wave transformation with a ramp parameter to drive color values. The distance value is fitted from sine's range (-1 to 1) into the 0-1 range required by the color ramp, and finally modifies point height using a channel parameter.

### Animated Radial Color Ramp [[Ep2, 70:52](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4252s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@Cd.y = chramp('myRamp', d);
```
Creates an animated radial color pattern by calculating distance from origin, scaling it, subtracting time for animation, using modulo to create repeating bands, and mapping the result through a ramp parameter to control the green color channel. The modulo operation creates cyclic patterns while time subtraction makes the bands move outward over time.

## Color Operations

### Sine Wave Color Pattern [[Ep2, 75:54](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4554s)]
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d *= fit(d, -1, 1, 0, 1);
@Cd = pal(d, d, d, d);
@P.y *= ch('height');
```
Creates a radial sine wave pattern using distance from origin, applies color using a palette function, and scales vertical position. The sine wave is fitted from -1,1 to 0,1 range before being used as palette input, while a channel controls the scale of the distance calculation and another controls height deformation.

## Color from Ramps

### Stepped Ramp Visualization [[Ep2, 89:36](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5376s)]
```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
@Cd.x = d;

d = length(@P);
d *= ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@Cd.y = d;
```
Demonstrates two methods for creating stepped color patterns: manually using truncation and division to create discrete steps, and using a custom ramp parameter to achieve similar results. The code compares the manual stepping approach (output to red channel) with the ramp-based approach (output to green channel) to visualize the relationship between these techniques.

### Stepped Ramps with Distance [[Ep2, 89:50](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5390s)]
```vex
float d = length(@P);
d *= ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@Cd.y = d;
```
Demonstrates creating stepped visual effects by calculating distance from origin, scaling it, and using a ramp parameter with truncation to create discrete bands. The progression shows evolution from manual truncation using trunc() to using a stepped ramp parameter with pre and post scale controls for more flexible artistic control.

## Color Operations

### Distance and Color Mapping [Needs Review] [[Ep3, 27:38](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1658s)]
```vex
float d = distance(v@P, @P);
d *= chf("scale");
@Cd = d;
@Cd.r = sin(d);
```
Calculates the distance from each point to itself (which is zero, likely setup for a xyzdist() follow-up), scales it by a channel parameter, assigns the distance to color, and modulates the red channel using a sine function. This demonstrates basic distance calculations and color manipulation patterns commonly used before introducing point cloud queries.

### Distance-based color using minpos and sin [[Ep3, 32:08](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1928s)]
```vex
vector pos = minpos(1, @P);
float d = distance(@P, pos);
d *= ch('scale');
@Cd = d;
@Cd.r = sin(d);
```
Finds the closest point position on the second input geometry using minpos, calculates the distance from the current point to that closest position, and uses this distance to create a color pattern. The red channel is modulated with a sine function to create a wave-like pattern based on distance, producing a pig-shaped gradient effect.

### Sine Function on Distance for Color [[Ep3, 5:32](https://www.youtube.com/watch?v=fOasE4T9BRY&t=332s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = 0;
@Cd.r = sin(d);
```
This example calculates the distance from the origin using length(@P), multiplies it by a channel parameter for scale, then uses the sine function to create an oscillating red color value based on that scaled distance. The @Cd attribute is initialized to black (0) before setting only the red component to the sine wave result.

### Distance-Based Color Rings [[Ep3, 6:04](https://www.youtube.com/watch?v=fOasE4T9BRY&t=364s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = d;
@Cd.r = sin(d);
```
Creates concentric color rings by calculating distance from origin using length(@P), scaling it with a channel parameter, and applying sine function to the red channel to produce oscillating color patterns. The technique combines distance calculations with channel references and trigonometric functions for visual effects.

### Color Gradients Using Distance [[Ep3, 7:24](https://www.youtube.com/watch?v=fOasE4T9BRY&t=444s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = @P;
@Cd.r = sin(d);
```
This code calculates the distance from the origin for each point, scales it using a channel parameter, assigns the position to color, and then modulates the red channel using a sine wave based on distance. The sine function creates smooth oscillating color transitions as points get further from the origin, resulting in color attributes that vary per point.

### Distance-Based Sine Wave Color [[Ep3, 7:42](https://www.youtube.com/watch?v=fOasE4T9BRY&t=462s)]
```vex
float d = length(@P);
d = ch('scale')*d;
@Cd = @P;
@Cd.r = sin(d);
```
Creates a radial color pattern by calculating distance from origin and applying a sine wave to the red channel. The scale parameter controls the frequency of the sine wave, while green and blue channels inherit position values. This produces smooth color gradients that appear as concentric bands radiating from the center.

## Color from Normals

### Dot Product for Color Masking [[Ep4, 12:20](https://www.youtube.com/watch?v=66WGmbykQhI&t=740s)]
```vex
vector pos = point(1, "P", 0);
@Cd = dot(@N, pos);
```
Retrieves the position of the first point from input 1 and uses the dot product between the current point's normal and that position to create a color value. This creates a gradient-based mask that responds to the relationship between surface normals and a reference point position, useful for creating procedural color falloffs.

### Dot Product for Conditional Coloring [Needs Review] [[Ep4, 68:38](https://www.youtube.com/watch?v=66WGmbykQhI&t=4118s)]
```vex
float d = dot(@N, {0,1,0});
@Cd = {1,0,0};
if(d > 0.3){
    @Cd = {1,1,1};
}
if(bbox.y < 0.5){
    @Cd = {0,1,0};
}
```
Creates a float variable to store the dot product between the point normal and an up vector {0,1,0}, then uses this value to conditionally set color to white when the dot product exceeds 0.3. This demonstrates combining dot product calculations with conditional logic to create more sophisticated color assignments based on surface orientation.

## Color from Ramps

### Multiply Blend Mode Color Mixing [[Ep5, 102:24](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6144s)]
```vex
int pts[];
int pt;
vector col, pos;
float d;

pts = nearpoints(1, @P, ch("radius"));

// treat this as ink on paper, so start with white paper
@Cd = 1;

foreach(pt; pts) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 0, 1);
    
    // adjust the ramp so its mostly 0,
    // and suddenly 1 at the end
    d = chramp("fade", d);
    
    // lerp is interpolate: we use d to make the colour
    // mostly unaffected, but close to pos, fade to white
    // at the radius border
    col = lerp(col, 1, d);
    
    // multiply the colour
    @Cd *= col;
}
```
Demonstrates color blending using multiply mode (like Photoshop multiply) rather than additive blending. Starts with white (@Cd = 1) representing paper, then multiplies nearby point colors with distance-based falloff using lerp to fade to white at the radius border. The multiplication approach simulates ink layering on paper where colors darken as they overlap.

### Color Blending via Multiply Mode [[Ep5, 102:28](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6148s)]
```vex
int pts[];
int pt;
vector col, pos;
float d;

pts = nearpoints(1, @P, chf("radius"));

foreach(pt; pts) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, chf("radius"), 1, 0);
    d = chramp("ramp", d);
    @Cd += col * d;
}
```
This snippet demonstrates a color blending exercise using nearpoints to sample nearby geometry colors and blend them additively with distance-based falloff. The challenge presented is to modify this additive blending approach to work like a multiply blend mode (similar to Photoshop's multiply operator), which requires understanding how multiplicative color math differs from additive.

### Multiply Color Blending with Near Points [[Ep5, 102:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=6170s)]
```vex
vector col, pos;
float d;

pts = nearpoints(1, @P, ch("radius"));

// treat this as ink on paper, so start with white paper
@Cd = 1;

foreach(pt; pts) {
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, ch("radius"), 1, 0, 1);
    
    // we adjust the ramp up its mostly d,
    // then suddenly 1 at the end
    d = chramp("fade", d);
    
    // Lerp is interpolate. we use d to make the colour
    // mostly the point colour, then quickly fade to
    // white at the radius border
    col = lerp(col, 1, d);
    
    // multiply the colour
    @Cd *= col;
}
```
This creates a Photoshop-like multiply blend effect by starting with white paper (@Cd = 1) and multiplying colors from nearby points. For each nearby point, it interpolates between the point's color and white based on distance using a ramp, then multiplies the result into the current color, simulating ink blending on paper.

## Color Operations

### Blending Multiple Point Colors [[Ep5, 51:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3072s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, 40);
@Cd = 0;

//start point
pos = point(1, 'P', pt);
col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;

//second point
pos = point(1, 'P', 1);
col = point(1, 'Cd', 1);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd += col * d;
```
Demonstrates accumulative color blending from multiple source points using += operator. The pattern reads position and color from specific points, calculates distance-based falloff with fit and clamp, then additively blends the color contribution into the current point's @Cd attribute, allowing multiple influences to combine.

### Multi-Point Color Blending [[Ep5, 51:54](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3114s)]
```vex
//first point
int pt = pts[0];
vector pos = point(1, 'P', pt);
float d;

pts = nearpoints(1, pos, ch('radius'));
@Cd = 0;

//offset point
int pt = pts[0];
vector pos = point(1, 'P', pt);
vector col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd -= col * d;

//second point
pt = pts[1];
pos = point(1, 'P', pt);
col = point(1, 'Cd', pt);
d = distance(@P, pos);
d = fit(d, 0, ch('radius'), 1, 0);
d = clamp(d, 0, 1);
@Cd -= col * d;
```
Extends color blending by accessing the second nearest point (pts[1]) in addition to the first, allowing colors to blend beyond initial Voronoi boundaries. Each point's color influence is calculated using distance-based falloff and subtracted from the current color, creating overlapping gradients between multiple source points.

### Color Blending with Foreach Loop [Needs Review] [[Ep5, 80:48](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4848s)]
```vex
vector pos, col;
int pts[];
int pt;
float d;

pts = nearpoints(1, @P, chf('r'));
@Cd = 0;

foreach(int pt; pts){
    pos = point(1, "P", pt);
    col = point(1, "Cd", pt);
    d = distance(@P, pos);
    d = fit(d, 0, chf('r'), 1, 0);
    d = clamp(d, 0, 1);
    @Cd += col * d;
}
```
Iterates through all nearby points within a radius and blends their colors together based on distance-weighted contributions. Each point's color is multiplied by an inverted, normalized distance value and accumulated into the current point's color, creating smooth color transitions across the geometry without hard edges.

## Color from Ramps

### Color and Scale from Distance Ramp [Needs Review] [[Ep6, 29:52](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1792s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = chramp('ramp', @id);
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(d, min, max, 0, 1);
vector scale = set(min, max, d);
@pscale = d/2;
@Cd = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color_ramp', d));
```
Calculates distance from origin, modulates it with frequency and ramp values, then uses fitted distance to drive both point scale and color through separate ramps. The scale attribute is set as a vector for non-uniform scaling, while @pscale provides uniform point scaling and @Cd is mapped through a color ramp based on the distance value.

### Color ramp from distance values [[Ep6, 31:54](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1914s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@P.y = 0;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
This code calculates an animated distance value using sine waves, flattens geometry to the ground plane by setting @P.y to 0, then remaps the distance value from 0-1 and uses it to sample a color ramp parameter for point colors. The fitted distance value drives color variation based on radial distance from origin.

### Color ramp with vector casting [Needs Review] [[Ep6, 33:18](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1998s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @prim * ch('speed');
d = length(@P);
d = d + t;
s = fit(sin(d), -1, 1, min, max);
@scale = set(s, s, s);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates using vector casting with chramp() to apply a color ramp to geometry. The code calculates a distance value, fits it to the 0-1 range, and uses chramp() with vector() casting to convert the ramp lookup into a color vector for @Cd. This provides a more flexible interface for controlling colors through Houdini's color ramp UI.

### Color ramp from distance with fit [Needs Review] [[Ep6, 33:20](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2000s)]
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
Creates animated color based on point distance from origin, using channel parameters for min/max range and speed. The distance value is animated by subtracting time, then remapped with fit() to 0-1 range before sampling a color ramp with chramp(). The vector cast converts the color ramp output to the proper @Cd attribute type.

### Color Ramp with Animated Scale [[Ep6, 33:22](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2002s)]
```vex
vector chramp(string colorMap, float input);

float min, max, d, t;
min = ch("min");
max = ch("max");
t = chf("speed");
d = length(@P);
d *= ch('frequency');
t -= d;
d = fit(sin(t), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Creates an animated ripple effect by calculating distance-based sine waves and using them to drive both scale and color via a color ramp. The distance from the origin modulates the animation timing, and the resulting values are mapped through a color ramp using chramp() with an explicit vector cast to assign colors to points.

### Color Ramp Vector Casting [[Ep6, 33:30](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2010s)]
```vex
d = ch('frequency');
d = t;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates using vector() casting on chramp() to convert a color ramp parameter into RGB values for @Cd attribute. The fit() function remaps the animated sine wave value to 0-1 range for proper color ramp sampling, while vector() tells Houdini to interpret the ramp as a color ramp rather than a float spline ramp.

### Color Ramp Vector Casting [[Ep6, 33:38](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2018s)]
```vex
d = ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), -1, 1, min, max);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates using vector() to cast a chramp() result into a color value for @Cd. The code applies a color ramp based on a fitted sine wave value, where the double fit() on d first maps the sine wave to a custom range (min, max), then normalizes it to 0-1 for the ramp lookup. The vector cast tells Houdini to interpret the chramp as a color ramp rather than a float spline.

### Color Ramp with Vector Cast [[Ep6, 33:52](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2032s)]
```vex
float d = chf('frequency');
float min = chf('min');
float max = chf('max');

d = fit(sin(d), -1, 1, min, max);
@scale = fit(d, min, max, 0, 1);
@P.y += d/2;

d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Applies a color ramp to geometry by using a vector cast on chramp() to convert a float ramp parameter into color values. The value d is fitted twice: first from sine wave range to min/max range, then normalized back to 0-1 range for proper color ramp sampling, demonstrating how to bridge between different value ranges when working with ramp parameters.

### Color Ramp with Vector Cast [Needs Review] [[Ep6, 34:04](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2044s)]
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
Uses vector() cast on chramp() to convert a float ramp parameter into a color ramp, which tells Houdini to create a color-based ramp interface rather than a spline-based one. The code performs two fit operations on 'd' to first scale the sine wave to custom min/max values for scaling/positioning, then remaps back to 0-1 range specifically for the color ramp lookup.

### Color Ramp with Vector Cast [Needs Review] [[Ep6, 34:06](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2046s)]
```vex
d = chf('frequency');
d += [];
d = fit01(d, min, max);
@scale = fit(d, min, max, 0, 1);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates using vector() cast with chramp() to convert a color ramp parameter into a vector for the @Cd attribute. The technique involves fitting values from a custom min-max range back to 0-1 range to properly drive the color ramp, effectively reversing an earlier fit operation to make the values compatible with ramp lookup.

### Color Ramps with Normalized Values [[Ep6, 34:16](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2056s)]
```vex
d = ch('frequency');
d = f;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0.0, 1.0);
@Cd = vector(chramp('color', d));
```
Demonstrates using double fit() calls to map values: first fitting a sine wave to min/max range for scale operations, then fitting back to 0-1 range to drive a color ramp. The two-step fit approach allows the same value to control both geometry scaling and color assignment through a ramp parameter, which expects normalized 0-1 input.

### Remapping Values for Color Ramp [[Ep6, 34:38](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2078s)]
```vex
d = ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d/3;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
This code demonstrates a double-fit technique to first map a sine wave to a custom min/max range for scale and position, then remap those values back to 0-1 range to drive a color ramp. The technique allows values scaled for geometric effects to be reused for color assignment without requiring separate calculations.

### Remapping values to drive color ramp [[Ep6, 34:40](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2080s)]
```vex
d = chf('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
This code demonstrates using multiple fit() operations to remap values through different ranges. The sine wave output is first fitted from [-1,1] to [min,max] for scale and position effects, then fitted back to [0,1] range to properly drive a color ramp parameter, showing how to reuse the same value for different purposes by remapping it appropriately.

### Remapping Values for Color Ramps [[Ep6, 34:42](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2082s)]
```vex
d = ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = set(@u * min, max, d);
@P.y += d / 2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
This code demonstrates using dual fit() operations to remap values for different purposes: first fitting a sine wave to min/max for scale and position, then fitting back to 0-1 range to drive a color ramp. The technique allows the same calculated value to control both geometric transformations and color through appropriate remapping.

### Remapping Values for Color Ramp [Needs Review] [[Ep6, 34:46](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2086s)]
```vex
d = chf('frequency');
d += f;
d = fit01(d, -1, 1);
float min = 0;
float max = 1;
@scale = fit(d, min, max, 0, 1);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates remapping frequency-based values through multiple fit operations to drive both scale attributes and color ramp lookups. The code chains transformations to convert values from the original range into normalized 0-1 space suitable for color ramp sampling, while also applying geometric deformation based on the intermediate values.

### Color ramp from scale values [Needs Review] [[Ep6, 34:48](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2088s)]
```vex
d = chf('frequency');
d += fit;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(@id, min, max, d);
@P.y -= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates remapping scale values to drive a color ramp parameter. Uses fit() to normalize the computed distance value (d) into the 0-1 range required by chramp(), then applies the resulting color to @Cd. This technique allows procedural patterns based on geometry properties to control color assignments through user-defined ramps.

### Remapping values for color ramp [[Ep6, 34:50](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2090s)]
```vex
d = chf('frequency');
d *= f;
d = fit(sin(d), -1, 1, min, max);
@scale = vector(max, max, d);
@P.y *= d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
This code takes computed scale values and remaps them to drive a color ramp. It uses fit() to convert the d variable from the min/max range back to 0-1 range, then feeds that normalized value into a color ramp parameter. This allows the same computed values that drive geometry scaling to also control point colors through a user-defined gradient.

### Color Ramp from Animated Values [[Ep6, 34:58](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2098s)]
```vex
d = chf('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d*u), max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates converting animated scale values into normalized 0-1 range to drive a color ramp parameter. The variable 'd' is transformed through multiple fit() operations to map sine wave values first to a min/max range for scale, then remapped to 0-1 for use with chramp(). This allows reusing the same animated value for both geometry transformation and color assignment.

## Color from Normals

### Color from Normal with Clamp [[Ep6, 41:40](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2500s)]
```vex
@Cd = @N;
if (min(@Cd) < 0) {
    @Cd = 0.1;
}
```
Sets primitive color to the normal vector value, then checks if any color component is negative and clamps the entire color to gray (0.1) if so. This prevents negative normal components from creating invalid colors, ensuring faces pointing in negative axis directions display as gray rather than black or invalid colors.

### Conditional Coloring Based on Normals [[Ep6, 43:18](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2598s)]
```vex
@Cd = @N;
if (sin(@d) < 0) {
    @Cd = 0.1;
}
```
Colors geometry based on normal direction, with front faces colored according to their axis-aligned normal components and back faces (where sine of @d is negative) colored a uniform gray (0.1). This creates a visual distinction between front and back faces, making it easy to identify surface orientation and axis alignment.
