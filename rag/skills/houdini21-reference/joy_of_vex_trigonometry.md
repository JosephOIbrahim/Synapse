# Joy of VEX: Trigonometry & Oscillation

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
@P.y = sin(@P.x);  // Sine Wave Output Range
float d = length(@P);  // Length Function and Distance Calculations
v@up = set(sin(@Time), 0, cos(@Time));  // Rotating Up Vector with Time
```

## Trigonometric Functions

### Compound assignment operators [Needs Review] [[Ep1, 100:42](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=6042s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float delta = distance(pos, center);
@P *= ch('scaling');
@Cd = fit(sin(delta), -1, 1, 0, 1);
```
Demonstrates compound assignment operators in VEX, specifically the *= operator which multiplies and assigns in one step (cleaner than writing @P = @P * ch('scaling')). The code shows how compound operators work with geometry attributes and channel references, making code more concise and readable.

### Sine Function for Color Animation [[Ep1, 44:12](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2652s)]
```vex
@Cd = float(@ptnum)/ch('scale');

@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)*ch('scale'));

float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
```
Demonstrates using the sine function to create oscillating color values based on point numbers. Shows progression from basic division to scaling point numbers appropriately (dividing by 100 or using a channel reference) before applying sine, and introduces storing intermediate calculations in variables for clarity.

### Sine Function for Color Animation [[Ep1, 44:16](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2656s)]
```vex
@Cd = float(@ptnum)/ch('scale');

@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)*ch('scale'));

float foo = float(@ptnum)*ch('scale');
@Cd = sin(foo);
```
Demonstrates the progressive refinement of using the sine function with point numbers to create animated color patterns. Shows the importance of scaling point numbers to reasonable ranges (dividing by 100 or using channel references) to work effectively with trigonometric functions, and introduces storing intermediate calculations in variables.

## Waves & Oscillation

### Sine Wave with Integer Division [[Ep1, 47:12](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2832s)]
```vex
@Cd = sin(@ptnum/100);

@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)*ch('scale'));

float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
```
Demonstrates the progression from integer division producing chunky results to proper float casting for smooth sine wave color gradients. Shows how integer math causes discrete stepping in the sine function output, and how casting @ptnum to float before division creates smooth continuous waves. Introduces channel references for interactive parameter control.

### Sine waves with CH function [[Ep1, 48:34](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2914s)]
```vex
@Cd = sin(float(@ptnum)/ch('scale'));

// Evolution from hardcoded to parameterized:
// @Cd = sin(@ptnum);
// @Cd = sin(@ptnum/100);
// @Cd = sin(float(@ptnum)/100);
// @Cd = sin(float(@ptnum)/ch('scale'));

// Can also assign to variable:
float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
```
Creates a smooth sine wave pattern by dividing point number by a user-controlled scale parameter. The float cast prevents integer division truncation, allowing the sine function to produce smooth oscillations across points. Using ch('scale') enables interactive art direction of the wave frequency without editing code.

## Trigonometric Functions

### Clean Code and Using Variables [[Ep1, 55:52](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3352s)]
```vex
float foo = @P.x/ch('scale');
@Cd = sin(foo);
```
This example demonstrates clean code practices by using an intermediate variable 'foo' to store the scaled position calculation before applying the sine function to color. Using descriptive variable names and breaking calculations into steps makes code more readable and maintainable for yourself and others.

### Length Function and Distance Calculations [[Ep1, 61:02](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3662s)]
```vex
float d = length(@P);
@Cd = sin(d);
```
Demonstrates using the length() function to calculate the distance from the origin to each point's position, then applying sine wave modulation to create a color gradient based on that distance. This combines spatial distance calculation with trigonometric functions for visual effects.

## Waves & Oscillation

### Distance to Origin and Sine Wave [Needs Review] [[Ep1, 62:26](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3746s)]
```vex
float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
```
Calculates the distance from each point to the origin using length(@P) and applies it to the color attribute. The second variant applies a sine function to the distance value to create a wave pattern. The third snippet is incomplete but follows the same pattern of storing the distance calculation.

## Trigonometric Functions

### Distance and Sine Progression [[Ep1, 66:10](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3970s)]
```vex
float foo = @P.y*ch('scale');
@Cd = sin(foo);

float d = length(@P);
@Cd = d;

float d = length(@P);
@Cd = sin(d);

float d = length(@P);
d *= ch('scale');
@Cd = sin(d);
```
A progression showing how to calculate distance from origin using length(@P) and apply sine waves to create color patterns. Demonstrates building complexity by adding channel references to scale the distance values before applying sine function.

### Scaling Distance with Compound Operators [[Ep1, 69:36](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4176s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = sin(d);
```
Demonstrates the *= compound assignment operator to scale the distance value by a channel slider. The compound operator d *= ch('scale') is shorthand for d = d * ch('scale'), allowing the distance to be multiplied and reassigned in one line. This scaled distance is then used in a sine function to create rings whose frequency is controlled by the scale parameter.

### Scaling Distance with Compound Assignment [[Ep1, 69:40](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4180s)]
```vex
float d = length(@P);
d *= ch("scale");
@Cd = sin(d);
```
Demonstrates using the compound assignment operator (*=) to scale the distance value by a channel parameter. This shorthand d *= ch("scale") is equivalent to d = d * ch("scale"), multiplying the existing distance variable by the scale parameter and reassigning it back to d. The scaled distance is then used in the sine function to create rings whose frequency can be controlled by the scale parameter.

## Waves & Oscillation

### Remapping sine wave range [[Ep1, 71:46](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4306s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d) + 1) / 2;
```
Demonstrates remapping a sine function output from [-1, 1] to [0, 1] range for color values. First adds 1 to shift the range to [0, 2], then divides by 2 to compress it to [0, 1], ensuring valid color values. Uses parentheses to group the addition operation before division to achieve the correct order of operations.

### Normalizing sine wave color range [[Ep1, 72:00](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4320s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)/2;

// Alternative compact form:
@Cd = (sin(length(@P) * ch('scale'))+1)*0.5;
```
Demonstrates how to normalize sine wave output from a range of [-1,1] to [0,1] for color values. The expression adds 1 to shift the range to [0,2], then divides by 2 (or multiplies by 0.5) to compress it to [0,1], preventing over-bright values that would clamp to white.

## Trigonometric Functions

### Vector scaling in distance calculations [[Ep1, 82:48](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4968s)]
```vex
vector center = chv('center');
float d = distance(@P * {0.5,1,1}, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

// Alternative versions:
// float d = distance(@P, {1,0,1});
// d *= ch('scale');
// @Cd = (sin(d)+1)*0.5;

// vector center = chv('center');
// float d = distance(@P, center);
// d *= ch('scale');
// @Cd = (sin(d)+1)*0.5;
```
Demonstrates multiplying the position vector by another vector to scale individual components before computing distance. Multiplying @P by {0.5,1,1} scales only the X component by 0.5, effectively stretching the distance calculation along the X-axis while leaving Y and Z unaffected.

### Non-uniform position scaling for distance patterns [[Ep1, 83:36](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5016s)]
```vex
vector center = chv('center');
vector pos = @P * {0.5, 1, 1};
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;
```
Demonstrates non-uniform scaling of position components by multiplying @P with a vector constant, allowing independent control over pattern stretching along different axes. The X component is scaled by 0.5 while Y and Z remain at 1.0, creating an elliptical distance pattern instead of a circular one. This technique provides fine-grained control over pattern distortion before calculating distance to center.

## Waves & Oscillation

### Remapping sine waves with fit [[Ep1, 88:42](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5322s)]
```vex
// Version 1: Manual remapping
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

// Version 2: Using fit function
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);

// Version 3: Animating with @Time
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);
```
Demonstrates three approaches to remapping sine wave output from [-1,1] to [0,1] for color visualization: manual calculation (sin(d)+1)*0.5, using the fit() function for clarity, and animating the pattern by multiplying distance by @Time before passing to sine. The fit() function provides a cleaner, more readable way to remap values between ranges.

## Trigonometric Functions

### Using fit() with sin() for animation [[Ep1, 94:18](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5658s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(d);

vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);

vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);
```
Demonstrates the progression of using fit() to remap values, starting with incomplete fit() calls, then properly using fit() to remap sin(d) from its natural range of -1 to 1 into the 0 to 1 range needed for color. Finally introduces animation by multiplying distance by @Time before passing to sin(), creating an animated ripple effect.

### Animating with @Frame vs @Time [[Ep1, 97:12](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5832s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = fit(sin(d*@Frame),-1,1,0,1);
```
Demonstrates animating color patterns using @Frame for rapid integer-based animation versus @Time for smoother float-based animation. The sine wave's frequency is modulated by distance from center and multiplied by the frame/time variable, creating animated ripple effects that evolve at different rates.

### Code Style and Mathematical Operations [Needs Review] [[Ep1, 99:50](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5990s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);

foo -= 5;
foo *= 5;
foo -= foo * 5 / @P.x * @N.y;

foo *= 1; // set range
foo -= 1; // make sure values never get below 0
foo /= @P.x; // reduce range to within red value
foo += @N.y; // addition normal on y
```
Demonstrates VEX code styling conventions and compound assignment operators for building complex mathematical expressions. Shows how to chain operations and use comments to document intent, building color patterns from distance calculations and normal attributes.

### Length and Clamp Functions [[Ep2, 18:52](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1132s)]
```vex
float d = length(@P);
v@z = ch("_scale");
@P += @N * sin(d) * ch("wave_height");
```
Demonstrates using the length() function to calculate distance from origin, combined with clamp() for value constraining and sin() for wave deformation. The final example shows how to create a radial wave effect by offsetting points along their normals based on the sine of their distance from the origin, scaled by a channel parameter.

### Distance normalization and clamping [Needs Review] [[Ep2, 27:28](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1648s)]
```vex
float d = length(@P);
@P.y = d*d + 1 * 10;
d = asin(clamp(d, 0, 1));
```
This code calculates the distance from the origin using length(), applies a squared transformation to the Y position, then uses asin() with a clamped distance value to ensure input values stay within the valid range of -1 to 1. The clamping prevents values from going outside the acceptable domain for arcsine, avoiding errors while preserving all geometry.

## Waves & Oscillation

### Animating Sine Waves with Ramps [[Ep2, 49:06](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2946s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d,-1,1,0,1);
```
This example demonstrates animating a sine wave pattern by adding @Time to the distance calculation, creating ripple animation across a grid. The sine output is remapped from [-1,1] to [0,1] using fit(), making it suitable for driving a ramp parameter that controls the vertical displacement of points.

### Animating Grid with Ramp and Sin Wave [Needs Review] [[Ep2, 49:12](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2952s)]
```vex
float d = length(@P);
d *= ch('scale');
d *= ch('width');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
```
Creates an animated wave pattern by calculating distance from origin, scaling it with channel parameters, applying a sine function, and remapping the result from the sine range (-1 to 1) to (0 to 1). This technique generates ripple effects that can be further modulated with time.

### Animating with sine wave [[Ep2, 49:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2954s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Frame;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
```
Creates animated wave pattern by calculating distance from origin, adding frame number for time evolution, applying sine function, and remapping the result from [-1,1] to [0,1] range. This produces a rippling wave effect that animates over time.

## Trigonometric Functions

### Animating Height with Ramp and Sine [[Ep2, 49:40](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2980s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Frame;
d = sin(d);
d = fit(d,-1,1,0,1);
```
This code calculates distance from origin using length(@P), scales and offsets it by frame number to create animation, then applies sine wave and fits the result from [-1,1] to [0,1] range. The original version used chramp() to drive the Y position, but the final version demonstrates a mathematical approach using sin() and fit() for wave animation.

### Animated Ripple with Nested Trigonometry [[Ep2, 52:12](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3132s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = sin(d/cos(d/cos(d)));
@Cd = ch('height');
```
Creates an animated ripple effect using nested trigonometric functions where distance from origin is scaled, time-shifted, and passed through nested sine and cosine operations. The complex nesting of sin(d/cos(d/cos(d))) produces interesting wave interference patterns that evolve over time.

## Waves & Oscillation

### Sine Wave Pattern with Fit [[Ep2, 52:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3176s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
```
Creates an animated radial sine wave pattern by calculating distance from origin, scaling and offsetting by time, applying sine function, then remapping the result from the sine range (-1 to 1) to a normalized 0-1 range. The fit() function normalizes the sine wave output for consistent attribute values that work better with color or other normalized attributes.

### Sine Wave with Ramp and Fit [Needs Review] [[Ep2, 65:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3932s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myRamp', d);
@Cd = ch('height');
```
Creates an animated sine wave pattern by calculating distance from origin, applying time offset, and using the result to drive both vertical position via a ramp lookup and color. The sine output is remapped from [-1,1] to [0,1] using fit() to work properly with chramp().

## Trigonometric Functions

### Normalizing Values with Fit [[Ep2, 66:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4006s)]
```vex
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp("my ramp", d);
@Cd.x = chf("height");
```
This code demonstrates normalizing sine wave values from their natural range of -1 to 1 into a 0 to 1 range using the fit function. The normalized value is then used to drive color through a ramp parameter and height channel, showing how normalized values are essential for controlling attributes like normals and directions versus scalar values like speed.

## Waves & Oscillation

### Sine Wave Output Range [[Ep2, 67:54](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4074s)]
```vex
@P.y = sin(@P.x);
```
The sine function outputs values constrained between -1 and 1, with the lowest point at -1 and highest at 1. When used with sin(@P.x), it creates a wave pattern where the height never exceeds these bounds, similar to but distinct from a fit01 operation.

## Trigonometric Functions

### Length function with fit remapping [[Ep2, 6:10](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=370s)]
```vex
int i = 1 + len(@P);
f@x = fit(sin(i), 0, 1, 0.1, 3.1);
```
Uses the len() function to calculate the length of the position vector, adds 1, then applies sine and remaps the result from 0-1 range to 0.1-3.1 range using fit(). This creates a custom floating point attribute 'x' based on oscillating position vector magnitude.

## Waves & Oscillation

### Sine Wave Ripple with Color Ramp [[Ep2, 71:20](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4280s)]
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = sin(d);
d *= fit(d, -1, 1, 0, 1);
@Cd = chramp('my_ramp', d);
@P.y *= ch('height');
```
Creates a radial sine wave pattern from the origin using point distance, applies double sine for more complex oscillation, remaps the result to 0-1 range, and colors points using a ramp while scaling vertical positions. The double sine operation creates a more intricate wave interference pattern.

### Radial Sine Wave Color and Height [[Ep2, 71:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4290s)]
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d,-1,1,0,1);
@Cd = set(d,d,d);
@P.y *= ch('height');
```
Creates a radial sine wave pattern by calculating distance from origin, applying sine function, then remapping the result to a 0-1 range for grayscale color assignment. The Y position is scaled by a channel parameter to control height variation.

## Trigonometric Functions

### Distance-Based Ripple Pattern [[Ep2, 74:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4456s)]
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = vector(d);
@P.y *= ch('height');
```
Creates a radial ripple pattern by calculating distance from origin, applying sine wave modulation, and remapping the result to color. The pattern is controlled by channel parameters for scale and height, demonstrating how to combine mathematical functions with UI parameters for procedural effects.

### Distance-based Y displacement with channels [[Ep3, 13:50](https://www.youtube.com/watch?v=fOasE4T9BRY&t=830s)]
```vex
float d = length(@P);
d *= ch("scale");
@P.y = sin(d);
```
Calculates the distance from the origin for each point, scales it by a channel parameter, and uses the sine of that scaled distance to displace points vertically. This creates a ripple effect where the wave frequency is controlled by the scale channel parameter.

## Waves & Oscillation

### Sine Wave Amplitude and Distance Falloff [[Ep5, 64:18](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3858s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d * ch('freq');
w = sin(w);
w = ch('amp') * w;
w *= fit(d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Applies a sine function to the distance-based frequency value, then multiplies by an amplitude parameter to control wave height. Finally, multiplies the wave by a fit function that inverts the distance, creating a falloff effect where waves are stronger near the source point and fade toward the radius edge.

### Animated sine wave displacement [[Ep6, 18:08](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1088s)]
```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= d * ch('frequency');
d += t;
d = sin(d);
@P.y += d;
```
Creates an animated radial sine wave effect by calculating distance from origin, scaling it by frequency, adding time-based animation, and applying sine function to displace points vertically. The combination of distance-based frequency and time produces expanding ripple waves.

### Animated Sine Wave Point Scale [[Ep6, 18:10](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1090s)]
```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= d * ch('frequency');
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;
```
Creates an animated radial sine wave effect by combining distance-from-origin with time, then applying sine function and remapping to control point scale. The time value is scaled by a speed parameter, multiplied with the squared distance scaled by frequency, then used to drive a sine wave that's remapped from its natural -1 to 1 range to user-defined min/max channel values.

## Trigonometric Functions

### Animated Pscale with Fit and Sin [[Ep6, 18:52](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1132s)]
```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;
```
Creates animated point scale by combining distance from origin with time, applying sine wave modulation, then remapping the -1 to 1 sine output to custom min/max values using fit(). The result produces a radiating wave pattern controlled by speed, frequency, and amplitude parameters.

## Waves & Oscillation

### Animated sine wave scaling [[Ep6, 19:08](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1148s)]
```vex
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
@Cd = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;
```
Creates time-animated sine wave patterns by calculating distance from origin, modulating it with time and frequency parameters, then mapping the sine wave to both color (via fit) and point scale. The combination produces evolving, rippling visual effects where both color and size change based on the sine wave propagation.

## Trigonometric Functions

### Animated Scale from Distance [Needs Review] [[Ep6, 25:02](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1502s)]
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
Creates an animated scale attribute based on distance from origin. Calculates distance from origin, multiplies by frequency, applies sine wave, fits to min/max range, and assigns to scale vector with distance affecting Y-axis scaling primarily.

### Animated scale from distance [[Ep6, 27:58](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1678s)]
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
@Cd = set(0, 1, 0);
```
Creates animated non-uniform scale based on distance from origin, using sine wave with time offset and frequency control. The scale vector varies from min to max on the z-axis while keeping x and y at min/max respectively, creating a ripple effect for copied geometry.

### Animated scale based on distance [Needs Review] [[Ep6, 28:08](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1688s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, min, d);
```
Creates animated scaling effect by calculating distance from origin, applying frequency multiplier and time offset, then using sine wave fitted to min/max range to drive Z-axis scale. The @scale attribute is set with uniform X/Y (min) but variable Z (d) for directional scaling along the normal.

## Waves & Oscillation

### Animating Scale with Sine Wave [Needs Review] [[Ep6, 28:58](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1738s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @ptnum * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
```
Creates animated scale variation across points by combining distance from origin with point number, then applying a sine wave modulated by frequency and speed parameters. The sine output is remapped from [-1,1] to [min,max] range and applied to the Z component of the scale attribute.

## Trigonometric Functions

### Animated scaling with time and distance [Needs Review] [[Ep6, 29:14](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1754s)]
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
@y = @P.y;
```
Creates animated scaling based on distance from origin and time. Combines point distance from origin with time-based animation, applies sine wave with fit to create oscillating scale values, and sets the z-component of @scale while preserving y position.

### Animated Scale with Distance [Needs Review] [[Ep6, 29:26](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1766s)]
```vex
float min = ch('min');
float max = ch('max');
float t = fit(@Time * ch('speed'), 0, 1, 0, 1);
float d = length(v@P);
float s = ch('frequency');
d = d * s;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);
// or
@scale = set(min, min, d);
```
Creates animated scale variation based on point distance from origin using sine wave. The code calculates distance, applies frequency multiplier, and uses fit to map sine wave oscillation to min/max range, then assigns to scale attribute on different axes.

### Animating Up Vector with Time [[Ep6, 46:32](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2792s)]
```vex
v@up = set(0,
            1,
            0
);

v@up = {0, 0, 1};

v@up = set(sin(@Time), 0, 0);
```
Demonstrates setting the up vector (@up) attribute to control orientation of geometry. The up vector is first set using the set() function, then shown using inline vector syntax. Finally, the up vector is animated by using sin(@Time) for the x-component, making the orientation change over time based on the global Time attribute.

### Rotating Up Vector with Time [[Ep6, 47:36](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2856s)]
```vex
v@up = set(sin(@Time), 0, cos(@Time));
```
Creates a rotating up vector using sine and cosine functions driven by @Time. The sine and cosine functions working in conjunction create circular motion by oscillating between 1 and -1, while keeping the middle component at zero ensures the vector rotates in a horizontal plane. This rotating up vector, combined with a normal pointing up, causes geometry (like cubes) to spin around the normal axis.

### Animating Up Vector with Time Offsets [[Ep6, 47:48](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2868s)]
```vex
v@up = set(sin(@Time), 0, cos(@Time));

v@up = set(sin(@Time), 0, cos(@Time));

float t = @Time - @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));

float t = @Time - @ptnum * ch('offset');
v@up = set(sin(t), 0, cos(t));

float d = length(@P);
float t = @Time + d * ch('offset');
```
Creates a circular spinning motion by animating the up vector using sine and cosine functions with @Time. The middle component is kept at zero to maintain horizontal rotation. Progressive refinements add per-point time offsets using @ptnum and distance-based offsets using length(@P) to create wave-like propagation effects across points.

### Time offset by point number [[Ep6, 48:46](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2926s)]
```vex
float t = @Time + @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));
```
Creates a time variable offset by point number to produce staggered rotation animations across points. Each point's rotation lags behind the previous point by 0.1 times its point number, creating a wave-like propagation effect through the grid.

### Time-based rotation with point offset [[Ep6, 48:50](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2930s)]
```vex
float t = @Time * @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));
```
Creates a time variable that combines the current time with the point number, scaled by 0.1 to create per-point timing offsets. Uses sine and cosine of this time value to generate rotating up vectors, creating a wave-like rotation effect where each successive point along the grid has a slight phase offset in its rotation.

### Time-based rotation with offset [[Ep6, 48:52](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2932s)]
```vex
float t = @Time * 0.1 + @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));

// With channel reference
float t = @Time * 0.1 + @ptnum * CH("offset");
v@up = set(sin(t), 0, cos(t));

// Distance-based offset
float d = length(@P);
float t = @Time + d * CH("offset");
v@up = set(sin(t), 0, cos(t));
```
Creates time-based rotation using sine and cosine for the up vector, with progressive offset added via point number or distance from origin. The offset value is scaled to create a wave-like propagation effect across points, with the CH() function allowing user control of the offset multiplier.

### Time-based Up Vector Animation [[Ep6, 49:48](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2988s)]
```vex
float t = @Time + @ptnum + ch('offset');
v@up = set(sin(t), 0, cos(t));
```
Creates an animated up vector that rotates in the XZ plane by combining scene time, point number, and a channel-controlled offset parameter. The sine and cosine functions produce circular motion, while the offset parameter scales the contribution of time and point number to control the wave propagation speed.

### Distance-based Up Vector Animation [[Ep6, 51:10](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3070s)]
```vex
float d = length(@P);
vector t = @Time * d * ch('offset');
v@up = set(sin(t), 0, cos(t));
```
Creates animated up vectors that rotate in the XZ plane based on each point's distance from the origin. The rotation timing is offset by distance multiplied by a channel parameter, creating a falloff wave effect where closer points animate differently than farther points.

## Waves & Oscillation

### Wave Animation with Distance Offset [[Ep6, 52:30](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3150s)]
```vex
float d = length(@P);
float t = @Time - d * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates an animated wave effect by calculating a time offset based on distance from origin, then uses that offset to animate both the up vector (rotating around Y axis) and the Y position (vertical oscillation). The Y position uses a doubled frequency and is scaled by 0.5 to constrain movement between -0.5 and +0.5 units, creating a bouncing motion that propagates outward.

### Animated vector orientation with sine waves [[Ep6, 54:02](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3242s)]
```vex
float d = length(@P);
float t = @Time * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
This snippet demonstrates animating both vector orientation and position using time-based sine waves. It creates a time variable offset by a channel parameter, uses it to animate an 'up' vector in the XZ plane via sin/cos, and simultaneously offsets points vertically with a doubled frequency sine wave.

## Trigonometric Functions

### Mixed vector and attribute operations [Needs Review] [[Ep6, 56:44](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3404s)]
```vex
float d = length(@P);
vector c = {1-d, 0, d*offset};
v@up = set(sin(s), 0, cos(s));
@P.y += sin(s.x * 2) * 0.5;
```
This snippet demonstrates multiple unrelated operations: calculating distance from origin, creating a color vector based on distance and an offset parameter, setting an up vector using sine and cosine, and modifying Y position with a sine wave. The code appears to be a collection of examples rather than a cohesive algorithm, possibly from end-of-lesson exercises.

### Animated up vector using distance and time [[Ep6, 56:52](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3412s)]
```vex
float d = length(@P);
float t = @Time * d * f@offset;
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates an animated rotation effect by computing distance from origin and combining it with time to drive an up vector that rotates in the XZ plane. Additionally animates vertical position using a doubled frequency sine wave for secondary motion.

### Animated up vector with distance [[Ep6, 56:56](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3416s)]
```vex
float d = length(@P);
vector t = @Time * d * (1.0/'offset');
v@up = set(sin(t), 0, cos(t));
v@N = sin(t * 2) * 0.5;
```
Creates an animated up vector that rotates based on distance from origin and time, using a channel reference to 'offset' parameter. The normal attribute is also animated with a sine wave at double frequency scaled to half amplitude. The combination creates distance-based animated orientation for instancing or other orientation-dependent operations.

### Rotating Up Vector with Sin and Cos [[Ep7, 66:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3978s)]
```vex
int i = {0,1,0};
float s = sin(@Time);
float c = cos(@Time);
@up = set(s, 0, c);
```
Uses sine and cosine of time to create a rotating up vector that circles around the Y-axis. The sine starts at zero, oscillates to 1 and -1, while cosine starts at 1 and oscillates, creating perpendicular waves that together produce circular motion when combined in a vector.

## See Also
- **VEX Functions Reference** (`vex_functions.md`) -- trigonometric function signatures
