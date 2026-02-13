# Joy of VEX: Ramps & Parameters

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
chv('scalevec');  // Channel Reference Scale Vector
@N = chf('scale');  // Setting Normals with Channel Reference
vector uv = chv("uv");  // Declaring UV vector parameter
```

## Parameter Controls

### Channel references in expressions [[Ep1, 40:20](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2420s)]
```vex
@Cd = float(@ptnum)/100;

@Cd = float(@ptnum)/ch('scale');

@Cd = float(@ptnum)/ch();
```
Demonstrates replacing hardcoded numeric values with channel references using the ch() function to create UI parameters. This allows interactive control of values without editing code, by referencing parameter names like 'scale' or auto-creating parameters when the function is left incomplete.

### Channel References in VEX [[Ep1, 41:46](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2506s)]
```vex
@Cd = float(@ptnum)/ch('scale');
```
Demonstrates using the ch() function to reference a parameter named 'scale' from the VEX wrangle node interface, allowing dynamic control over color values. The ch() function takes a string parameter name and returns its value, which can then be used in expressions. Quotes denote strings in VEX, and the parameter can be auto-created using the wrangle's UI button if it doesn't exist.

### Channel references for parameter control [[Ep1, 43:18](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2598s)]
```vex
@Cd = float(@ptnum)/ch('scale');

@Cd = sin(@ptnum);
```
Demonstrates using the ch() function to reference a user interface parameter ('scale') that controls color output, allowing for interactive art direction without rewriting code. Shows progression from dividing point numbers by a slider value to using sine function for different color patterns.

### Variables and Channel References [[Ep1, 50:02](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3002s)]
```vex
@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)*ch('scale'));

float foo = float(@ptnum)*ch('scale');
@Cd = sin(foo);

float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
```
Demonstrates storing intermediate calculations in variables rather than inline expressions. The example shows extracting the channel reference calculation into a variable named 'foo', which makes the code more readable and easier to debug. This progression also illustrates common debugging practices like fixing parenthesis errors.

### Variables and Channel References [[Ep1, 50:12](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3012s)]
```vex
@Cd = sin(@ptnum);

@Cd = sin(@ptnum/100);

@Cd = sin(float(@ptnum)/100);

@Cd = sin(float(@ptnum)/ch('scale'));

float foo = float(@ptnum)/ch('scale');
@Cd = sin(foo);
```
This demonstrates the progression from hardcoded values to parameterized expressions by introducing variables and channel references. The point number is cast to float, divided by a channel parameter 'scale', stored in a variable 'foo', then passed to sin() to set color. This shows how to create reusable, adjustable code by extracting complex expressions into named variables and connecting them to UI parameters.

### Scaling distance with channel reference [[Ep1, 72:54](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4374s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```
Calculates distance from origin and scales it using a channel parameter for control. The scaled distance drives a color value through a sine function normalized to 0-1 range. This demonstrates why multiplying by parameters is preferred over division to avoid potential divide-by-zero errors.

### Distance with Channel-Referenced Center [[Ep1, 80:02](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4802s)]
```vex
vector center = chv('center');
float d = distance(@P, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```
This code refactors the distance-based color pattern to use a vector parameter for the center point, allowing dynamic control via a channel reference. The distance calculation and sine-based color mapping remain the same, but now the center point can be adjusted interactively through the parameter interface rather than being hardcoded in the VEX code.

### Vector Channel Parameter for Center [[Ep1, 80:16](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4816s)]
```vex
float d = distance(@P, {3,0,3});
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

float d = distance(@P, {1,0,1});
d += ch('scale');
@Cd = (sin(d)+1)*0.5;

vector center = chv('center');
float d = distance(@P, center);
d += ch('scale');
@Cd = (sin(d)+1)*0.5;
```
Demonstrates the progression from hardcoded center points to a parameterized vector channel. The final version uses chv('center') to create a vector parameter that allows interactive control of the concentric ring pattern's origin point, replacing the hardcoded {3,0,3} and {1,0,1} positions.

### Parameterized Position and Color [[Ep1, 84:18](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5058s)]
```vex
vector pos = @P * chv('fancy_scale');
vector center = chv('center');
vector d = normalize(pos - center);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;
```
Creates a parameterized color effect by scaling position with a vector channel reference, computing the normalized direction from a center point, and converting a sine wave distance calculation to color values. The code demonstrates replacing hard-coded values with channel references (chv) to make the effect adjustable via UI parameters.

### Channel References for Interactive Parameters [[Ep1, 84:50](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5090s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```
Demonstrates converting hardcoded values to channel references using ch() and chv() functions to create interactive UI parameters. The 'fancyscale' vector parameter allows scaling position coordinates independently in X, Y, Z before distance calculation, enabling real-time manipulation of concentric color rings. Setting default values to (1,1,1) maintains the original appearance while providing artistic control.

### Channel Parameters for Interactive Pattern Control [[Ep1, 85:14](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5114s)]
```vex
vector pos = @P * chv('anyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;
```
Demonstrates adding channel parameter references to VEX code for interactive control of a radial ring pattern generator. By using chv() for vector parameters and ch() for float parameters, the pattern's scale, center position, and ring spacing can be adjusted in real-time through the UI without modifying code.

### Channel References for Radial Patterns [[Ep1, 85:50](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5150s)]
```vex
vector pos = @P + chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;
```
Demonstrates creating a controllable radial ring pattern by exposing multiple parameters through channel references. Uses distance from a movable center point, scales it, and applies sine function to generate color values, showing how strategic parameter placement enables quick iteration on procedural patterns.

### Radial Pattern with Channel References [Needs Review] [[Ep1, 85:54](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5154s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
f@distance = distance(pos, center);
@distance *= ch('scaling');
@Cd = (sin(@distance) + 1) * 0.5;
```
Demonstrates creating a controllable radial ring pattern by exposing channel parameters through chv() and ch() for scaling and center position. The pattern uses distance from a center point combined with sine wave calculations to drive color values, creating movable and squishable rings.

### Vector vs Float Channel Parameters [[Ep1, 86:34](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5194s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('_scale');
@Cd = sin(d) * 1 * 0.5;
```
Demonstrates the difference between using ch() for float parameters and chv() for vector parameters when creating UI controls. The code calculates color based on distance from a center point, scaling position and distance values using channel references. Shows how changing a parameter type from float to vector (ch to chv) requires recreating the parameter if it already exists.

### Changing Parameter Types and Spare Parameters [[Ep1, 86:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5216s)]
```vex
vector pos = @P + chv('fancyscale');
vector center = chv('center');
@Cd = length(pos, center);
@P *= chv('scale');
@Cd = (sin(@P))*0.5;
```
Demonstrates the use of channel reference functions (ch vs chv) for accessing parameters, and addresses the workflow for changing parameter types after they've been created. When you need to change a parameter type (e.g., from float to vector), you can delete all spare parameters and remake them, or manually delete individual spare parameters.

### Channel Parameters and Type Conversion [Needs Review] [[Ep1, 87:00](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5220s)]
```vex
vector pos = @P + chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= chf('scale');
@Cd = (sin(d)+1)*0.5;
```
Demonstrates how to use channel reference functions to expose parameters in the UI, including the importance of using the correct type (chv for vectors, chf for floats). The code calculates distance from a center point and uses it to create a sinusoidal color pattern. Also shows that changing parameter types requires deleting and recreating spare parameters.

### Converting Parameters to Vector Type [[Ep1, 87:14](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5234s)]
```vex
vector pos = @P * chv('scale');
vector center = chv('center');
float dist = distance(pos, center);
dist *= chv('scale');
@Cd = (sin(dist) * 1) * 0.5;
```
Demonstrates how to manage spare parameters when converting between types (float to vector). When a channel reference like chv() needs to change type, you can delete all spare parameters and let them regenerate, or selectively delete and recreate individual parameters to match the new type.

### Managing Spare Parameters [[Ep1, 87:24](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5244s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
f@dist = distance(pos, center);
@dist *= chv('scale');
@Cd = (sin(@dist)+1)*0.5;

vector pos = @P * chv('fancyscale');
vector center = chv('center');
f@d = distance(pos, center);
@d *= chv('scale');
@Cd = (sin(@d)+1)*0.5;
```
Two variants of the same distance-based color calculation demonstrating spare parameter workflow. When changing parameter types (like converting 'scale' from float to vector), you can either delete all spare parameters and recreate them, or delete individual parameters and re-add them to update their type definitions.

### Spare Parameters and Type Casting [Needs Review] [[Ep1, 87:26](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5246s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
vector d = distance(pos, center);
d *= chv('scale');
@Cd = (sin(d)+1)*0.5;
```
Demonstrates creating channel reference spare parameters and handling implicit type casting issues. The code calculates distance from a center point and uses it to create a color pattern, with discussion of properly casting between vector and float types when using distance() and managing spare parameters through deletion and recreation.

### Parameter Type Casting and Distance [Needs Review] [[Ep1, 88:12](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5292s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
vector delta = pos - center;
float d = length(delta);
d *= ch('scalePos');
@Cd = sin(d * 3) * 0.5;
```
Demonstrates computing distance from a point to a center using vector subtraction and length(), then using that distance to drive color with a sine wave. Also highlights the importance of explicit type casting when creating parameters - if you need to change a parameter's type (e.g., from vector to float), you must delete and recreate it rather than just clicking the create parameter button again.

### Parameter Type Management [Needs Review] [[Ep1, 88:22](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5302s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
vector delta = pos - center;
float dist = length(delta);
@Cd = sin(dist) + 0.5;
```
Demonstrates the importance of properly managing spare parameter types in VEX. Once a parameter is created with a specific type (float vs vector), it must be deleted and recreated to change its type, as simply modifying the channel reference won't automatically update the parameter interface.

### Channel References and Art Directability [Needs Review] [[Ep1, 99:38](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5978s)]
```vex
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = ch('scale');
@Cd = fit(sin(d*@Frame), -1, 1, 0, 1);

foo *= 5;

foo = foo * 1 + 1 / @Cd.x * @N.y;

foo *= 1; // set range
foo += 1; // make sure values never get below 0
foo /= @Cd.x; // reduce range to within red value
foo *= @N.y; // sanitize normal on y

foo *= 1; // set range
foo += 1; // make sure values never get below 0
foo /= @Cd.x; // reduce range to within red value
foo *= @N.y; // sanitize normal on y
```
Demonstrates using channel references (ch() and chv()) to create art-directable VEX effects by exposing parameters that can be animated or adjusted interactively. The code shows distance-based color manipulation using fit() and sin() functions combined with @Frame for animation, along with various normalization techniques using color and normal attributes.

### Channel Parameters and Clamping [Needs Review] [[Ep2, 100:12](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=6012s)]
```vex
float d = length(@P);
d = ch('pre_scale');
d = clamp(d, ch('post_scale'), d);
d += ch('post_scale');
@Cd = d;
```
This code demonstrates controlling values using channel parameters with ch() function and the clamp() function to constrain values within a range. The distance value is replaced by pre_scale parameter, clamped using post_scale as minimum, then offset by post_scale before assigning to color, creating a controlled stepped or striated effect.

## chramp Usage

### Remapping Values with Ramps [Needs Review] [[Ep2, 101:34](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=6094s)]
```vex
float d = length(@P);
d = ch('pre_scale');
d -= chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```
This code demonstrates a common VEX workflow of taking values through different ranges and transformations. It calculates distance, applies pre-scaling via a channel parameter, subtracts a ramped value using chramp(), applies post-scaling, and assigns the result to the Y position, illustrating how to fit and manipulate values for desired effects.

## Parameter Controls

### Fitting and Clamping with Channels [[Ep2, 29:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1742s)]
```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
d = fit(d, imin, imax, 1, 0);
d = clamp(d, 0.5, 1);
@P.y = d;
```
Demonstrates using fit() to remap distance values from a custom input range (controlled by channel parameters) to an output range of 1 to 0, then applying an additional clamp() to restrict the result between 0.5 and 1 before assigning to the Y position. This creates a controlled vertical displacement based on distance from the origin with parameter-driven input bounds.

### Channel-Driven Fit Range [[Ep2, 33:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2012s)]
```vex
float d = length(@P);
float inmin = ch("fit_in_min");
float inmax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d = fit(d, inmin, inmax, outmin, outmax);
@P.y = d;
```
Creates channel references for all fit() function parameters, allowing interactive control of input and output ranges from the parameter interface. This demonstrates how to expose VEX calculations to the UI by using ch() to read parameter values and apply them to geometry transformations based on distance from origin.

### Channel-driven fit with UI parameters [[Ep2, 34:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2098s)]
```vex
float d = length(@P);
float imin = ch("fit_in_min");
float imax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d = fit(d, imin, imax, outmin, outmax);
@Cd.y = d;
```
Demonstrates creating a user interface for the fit function by exposing all input and output range parameters as channels. Uses ch() to read parameter values and allows interactive control of the remapping ranges, with spare parameters automatically created from the channel references.

### Fit Function with Channel Parameters [Needs Review] [[Ep2, 40:20](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2420s)]
```vex
float angle = ch('fit_in_min');
float imagex = ch('fit_in_max');
float imagey = ch('fit_out_min');
float outmin = ch('fit_out_max');
float outmax = outmin;
@P.x = fit(angle, imagex, imagey, outmin, outmax);
@P.y = angle;
```
This code demonstrates using the fit() function with channel references to remap values from one range to another, setting the X position based on the remapped value and Y position to the original input angle. The channel parameters provide UI controls for the input and output ranges of the fit operation.

## chramp Usage

### Ramp-driven Y displacement [[Ep2, 43:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2626s)]
```vex
float d = length(@P);
d *= fit(scale);
@P.y = chramp('myramp', d);
```
This code calculates the distance from the origin for each point, scales it using a fit operation, then uses that scaled distance to sample a custom ramp parameter and assign the result to the Y position. The technique allows for ramp-controlled radial displacement patterns that can be adjusted interactively.

### Distance to Ramp Mapping [[Ep2, 44:10](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2650s)]
```vex
float d = length(@P);
d = d * (v@scale);
@P.y = chramp('myramp', d);
```
Uses the length() function to calculate distance from origin, scales it by a vector parameter, then uses chramp() to map the scaled distance value through a ramp parameter to control the Y position of points. This demonstrates how to normalize distance values to a 0-1 range for ramp lookups to create interesting height variations.

### Ramp Parameter with Distance [[Ep2, 45:22](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2722s)]
```vex
float d = length(v@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
```
This code calculates the distance from the origin using length(), scales it with a channel parameter, and then uses that scaled distance to sample a ramp parameter called 'myramp' which drives the Y position of each point. The chramp() function evaluates the ramp parameter at the given distance value, allowing for artistic control over point displacement based on distance.

### Using chramp with distance [[Ep2, 45:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2726s)]
```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
```
Creates a ramp-based deformation by calculating the distance from the origin using length(@P), scaling it with a channel parameter, and then using that distance value to evaluate a ramp parameter that drives the Y position of points. The chramp function takes a ramp parameter name ('myramp') and evaluates it at the scaled distance value to create smooth vertical displacement.

### Ramp Lookup with Distance Scaling [[Ep2, 46:20](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2780s)]
```vex
float d = length(@P);
d *= ch("scale");
@P.y = chramp("myRamp", d);
@P.y *= ch("height");
```
Calculates point distance from origin and uses it as a lookup value into a ramp parameter, scaled by a channel slider. The ramp output is applied to the Y position and multiplied by a height control, allowing interactive adjustment of both the distance scale and the final displacement magnitude.

### Chramp Modulo Behavior Change [[Ep2, 50:20](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3020s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
Uses chramp() to sample a ramp parameter based on distance from origin plus time, then applies that value to the Y position with a height multiplier. The discussion focuses on a feature change where chramp() no longer automatically modulos values, meaning values outside 0-1 range won't repeat the ramp pattern.

### Ramp-based height displacement [[Ep2, 50:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3026s)]
```vex
float d = length(@P);
d *= ch("scale");
d = abs(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```
This code creates a radial displacement pattern by calculating distance from origin, applying trigonometric transformation, and using a ramp parameter to control the vertical displacement of points. The chramp() function samples a color ramp UI parameter which no longer automatically wraps/modulos values as it did in earlier Houdini versions.

### Ramp-driven height with distance fitting [Needs Review] [[Ep2, 51:04](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3064s)]
```vex
float d = length(@P);
d *= ch('scale');
d = fit(d, 1, 1, 0, 1);
@P.y = chramp('myRamp', d);
@P.y *= ch('height');
```
Calculates distance from origin, scales and remaps it using fit(), then uses the remapped value to sample a ramp parameter that drives vertical displacement. The fit() function normalizes the distance range before sampling the ramp, allowing for controlled height distribution based on radial distance.

### Ramp-driven height with channel offset [[Ep2, 53:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3196s)]
```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
@P.y += ch('height');
```
This code calculates the distance from the origin, scales it with a channel parameter, and uses that scaled distance to sample a ramp parameter that drives the Y position. An additional height channel parameter is added as an offset to vertically shift the entire ramp-driven surface.

### Ramp-Based Height Displacement [[Ep2, 53:18](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3198s)]
```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
This code displaces point height based on distance from origin using a ramp for shape control. The distance is calculated, scaled by a channel parameter, then used to sample a color ramp which determines the Y displacement, finally multiplied by a height multiplier for amplitude control.

### Ramp Parameter Modulation [[Ep2, 53:22](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3202s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = chramp('myramp', d);
@P.y = chramp('myramp', d);
```
This code calculates distance from origin using length(@P), scales it with a channel slider, then uses that scaled distance value to sample a ramp parameter. The ramp controls both the color (@Cd) and the vertical position (@P.y) of points, creating a radial pattern that can be shaped by adjusting the ramp curve.

### Ramp Wave Shaping [[Ep2, 57:10](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3430s)]
```vex
float d = length(v@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
Creates an animated wave pattern by using distance from origin as input to a ramp parameter, allowing the ramp curve to shape the wave form. By adjusting the ramp's curve shape, different wave patterns can be created (triangle waves, sawtooth waves, etc.), demonstrating how ramps provide artistic control over mathematical functions.

### Ramp-Driven Geometry Animation [Needs Review] [[Ep2, 57:44](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3464s)]
```vex
float d = length(@P);
d = ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = chramp('myramp', d);
@P.y = ch('height');
```
Demonstrates using a color ramp to drive vertical point displacement by calculating distance, applying sine wave transformation, and using chramp() to lookup values that control the Y position. The ramp profile shapes the animation pattern over time, allowing artists to dial in custom displacement shapes interactively.

### Ramps and Fit Range [[Ep2, 58:28](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3508s)]
```vex
float d = length(@P);
d *= ch('scale');
d += 1;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
This demonstrates using fit() to normalize a sine wave from its natural -1 to 1 range into 0 to 1, making it suitable for ramp sampling. The chramp() function requires input values between 0 and 1 to properly evaluate the ramp parameter, so fit() remaps the oscillating sine values to this normalized range before applying the ramp to control point height.

### Ramp Parameter Control [[Ep2, 58:42](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3522s)]
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
Uses a ramp parameter to control point displacement height by computing radial distance, applying sine wave modulation, and remapping the sine output (-1 to 1) to valid ramp lookup range (0 to 1). The chramp() function samples the ramp parameter and multiplies by a height control for final vertical displacement.

### Ramp-based Height Displacement [[Ep2, 58:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3538s)]
```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```
This code creates a radial sine wave pattern and uses a ramp parameter to control vertical displacement. The distance from origin is scaled, passed through a sine function, normalized from -1,1 to 0,1, then sampled through a color ramp to drive the Y position, allowing for custom height profiles based on the ramp curve shape.

### Ramp-driven height and color mapping [[Ep2, 62:50](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3770s)]
```vex
float d = length(@P);
d *= ch('scale');
d += sin(d);
d = fit(d, 1, 3, 0, 1);
@P.y = chramp('myRamp', d);
@Cd.y = chramp('myRamp', d);
@Cd.y *= ch('height');
```
This code calculates a distance-based value from the origin, applies scaling and sine wave modulation, then remaps it to 0-1 range using fit(). The remapped value is used to sample a ramp parameter which drives both vertical position and green color channel intensity, with an additional height multiplier for color.

### Combining Distance Fields with Ramps [[Ep2, 64:10](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3850s)]
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myamp', d);
@P.y *= ch('height');
```
Creates a radial wave pattern by calculating distance from origin, applying sine wave modulation, and using a ramp parameter to control the vertical displacement shape. The distance is scaled and normalized using fit() to provide smooth input values (0-1) for the ramp lookup, with final height controlled by a channel parameter.

### Ramp Parameters with Distance Field [[Ep2, 64:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3872s)]
```vex
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
Creates a radial wave pattern by calculating distance from origin, applying sine functions for wave oscillation, then using fit() to normalize the result to 0-1 range before sampling a ramp parameter. The ramp lookup is multiplied by a height slider to control amplitude, allowing interactive adjustment of the wave profile through the ramp interface.

### Ramp and Channel Parameter Control [[Ep2, 65:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3902s)]
```vex
f@y = chramp('mymap', @P.x);
@P.y *= ch('height');
```
Uses a ramp parameter to remap position values and a channel parameter to control height multiplication. The chramp function samples a custom ramp using the x position, storing the result in a custom attribute, then scales the Y position by a slider value to control the overall height of the deformation.

### Custom Ramp Function [Needs Review] [[Ep2, 66:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3976s)]
```vex
vector ramp(float d){
    d *= ch('scale');
    d = fit(d, -1, 1, 0, 1);
    @P.y = chramp('myramp', d);
    @P.y *= ch('height');
}
```
Defines a custom function that processes a distance value through scaling, remapping, and a color ramp lookup to control point height. The function takes a float input, scales it using a channel parameter, fits it to 0-1 range, samples a ramp parameter, and multiplies the result by a height channel to set the Y position of points.

### Compound Assignment Operators [Needs Review] [[Ep2, 69:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4188s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
@P.y = chramp('my_ramp', d);
@Cd = chramp('height', d);
```
Demonstrates compound assignment operators like += and *= as shorthand for operations. The variable d is calculated from point position length, scaled by a channel parameter, then incremented by @Time using the += operator (equivalent to d = d + @Time). The result drives both vertical displacement via a ramp and color assignment.

### Stepped Quantization with Ramps [[Ep2, 91:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5518s)]
```vex
float d = length(@P);
v@Cd = set(d);
d = chramp('my_stepped_ramp', d);
d *= d;
d = trunc(d);
@P.y = d;
```
This code creates a stepped quantization effect by calculating distance from origin, passing it through a stepped ramp, squaring the result, and then truncating to integer values. The truncated distance values are applied to the Y position, creating discrete height levels. The chramp parameter allows interactive control of the stepping pattern.

### Ramp-Based Stepped Effect [[Ep2, 92:40](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5560s)]
```vex
float d = length(@P);
d /= 10;
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```
Creates a stepped displacement effect by normalizing point distance from origin, sampling a stepped ramp parameter, and applying the result to vertical position. This technique provides a more controllable alternative to mathematical truncation by using a UI ramp to define the stepping pattern, allowing for artistic control over the stepped appearance.

### Pre-scale and Post-scale with Ramps [[Ep2, 95:18](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5718s)]
```vex
float d = length(@P);
d *= 10;
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```
Creates a terrain-like height displacement by calculating distance from origin, applying a pre-scale multiplier, sampling a stepped ramp parameter, then applying a post-scale channel parameter to control the final y-position. This demonstrates a workflow pattern of pre-processing input values before ramp lookup and post-processing the result for better control.

### Stepped Ramp for Height Displacement [[Ep2, 96:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5790s)]
```vex
float d = length(@P);
d *= chf('amplitude');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```
Calculates distance from origin and uses it to sample a stepped ramp parameter, creating terraced height displacement on geometry. The code demonstrates using ramp presets (specifically a stepped ramp) to create non-continuous height variations controlled by channel parameters for amplitude and post-scale adjustments.

### Stepped Ramp with Pre/Post Scale [[Ep2, 97:50](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5870s)]
```vex
float d = length(@P);
d *= ch("pre_scale");
d = chramp("my_stepped_ramp", d);
d *= ch("post_scale");
@P.y = d;
```
This code calculates distance from origin using length(@P), applies pre-scaling, then samples a stepped ramp to create discrete height levels, and finally applies post-scaling before assigning the result to the Y position. The stepped ramp creates distinct plateau levels rather than smooth transitions, allowing for terraced or layered geometric effects.

## Parameter Controls

### Distance-based Y displacement with channel scaling [Needs Review] [[Ep2, 99:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5986s)]
```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d *= f;
d = fit(d, 0, 1, 0, 1);
@P.y = d;
```
Calculates the distance from origin using length(@P), scales it by two channel parameters 'scale' and 'factor', then remaps the distance value with fit() and applies it to the Y position. This demonstrates debugging workflow after discovering unexpected pre-scaling of geometry, showing how channel references can accumulate and affect results.

### Vector Addition and Normal Visualization [[Ep4, 30:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=1812s)]
```vex
vector a = chv('a');
vector b = chv('b');
@N = a+b;
```
Demonstrates vector addition by reading two vector parameters from the UI and assigning their sum to the point normal attribute. This technique allows interactive manipulation of point normals through the parameter interface, with visualization options to display the actual length of the resulting normal vectors.

### Vector Channel Parameter and Point Lookup [Needs Review] [[Ep4, 32:34](https://www.youtube.com/watch?v=66WGmbykQhI&t=1954s)]
```vex
vector a = chv('a');
@N += a;

vector a = point(1, 'P', @i);
vector b = point(1, 'P', @i);
```
Demonstrates adding a vector channel parameter to the normal attribute and introduces the point() function for reading position attributes from input geometry. The code shows how to retrieve vector parameters from the UI with chv() and how to access point attributes from a specific input using point index.

### Adding Vector Channel to Normals [[Ep4, 33:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=1996s)]
```vex
vector a = chv('a');
@N += a;
```
Creates a vector parameter 'a' using chv() and adds it to the normal vector using the += compound assignment operator. This allows interactive adjustment of normal directions via a UI parameter, useful for controlling velocities before simulations or adjusting point behaviors like rigid body explosions.

### Vector Addition for Velocity [[Ep4, 34:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=2042s)]
```vex
vector a = chv('a');
@P += a;
```
Demonstrates adding a vector parameter to point positions, with practical applications for adjusting velocities on points entering simulations. This technique is useful for setting initial velocities on rigid body simulations or other dynamics setups where direction control from point positions is needed.

### Setting Normals with Channel Reference [[Ep4, 40:32](https://www.youtube.com/watch?v=66WGmbykQhI&t=2432s)]
```vex
@N = chf('scale');
```
Sets the normal vector (@N) to a uniform scalar value controlled by a channel parameter named 'scale'. This demonstrates using a channel reference to control direction and magnitude of normals, which can be used to create explosion-like effects or blast simulations. The instructor shows adjusting the scale value to control how much geometry is pushed in the normal direction.

### Channel Reference Scale Vector [[Ep4, 46:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=2806s)]
```vex
chv('scalevec');
```
Demonstrates using the chv() function to reference a vector channel parameter named 'scalevec'. This is part of a discussion about using clamp() versus fit() functions to control vector attribute ranges, where clamp provides hard cutoffs while fit scales values proportionally into a target range.

## chramp Usage

### Using chramp with relpointbbox [[Ep4, 55:04](https://www.youtube.com/watch?v=66WGmbykQhI&t=3304s)]
```vex
vector bbox = relpointbbox(0,@P);
@Cd = relpointbbox(0, @P);

vector bbox = relpointbbox(0,@P);
@Cd = bbox;

vector bbox = relpointbbox(0,@P);
@P += @N*bbox.y*ch('scale');

vector bbox = relpointbbox(0,@P);
float i = chramp('inflate',bbox.y);
@P += @N*i*ch('scale');
```
Demonstrates progressive refinement of a bounding box-based displacement effect, culminating in using chramp() to create a custom remapping curve. The chramp() function takes the normalized bbox.y value (0-1) and allows for non-linear scaling control via a ramp parameter, enabling bulging or other custom deformation profiles along the vertical axis.

## Parameter Controls

### Wave Frequency and Radius Parameters [Needs Review] [[Ep5, 66:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3990s)]
```vex
int pts[];
int pt;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('num_of_points'));

pt = pts[0];
@Cd = point(1, 'P', pt);
d = distance(@P, point(1, 'P', pt));
w = ch('freq');
w = sin(w);
w = ch('amp');
@P.y += w;
```
Demonstrates adjusting frequency and radius parameters to control wave behavior, showing how high frequencies can create visual artifacts and how radius affects wave overlap. The code retrieves nearest points and applies sine-based displacement, but the logic flow appears incomplete as the distance calculation and sine function usage need refinement.

### Grid Size Parameter Adjustment [[Ep5, 89:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5352s)]
```vex
int pts[] = nearpoints(1, @P, 40);

foreach(int pt; pts){
    vector pos = point(1, 'P', pt);
    float d = distance(@P, pos);
    d = fit(d, 0, ch('radius'), 1, 0);
    d = clamp(d, 0, 1);
    float t = @Time * ch('speed');
    t += rand(pt);
    float a = d * ch('amp');
    float f = d * ch('freq');
    @P.y += sin(f * t) * a;
}
```
Demonstrates how parameter values need to scale proportionally with geometry size. When increasing grid size from 10x10 to 50x50, the radius parameter should be adjusted to 8 and frequency to 10 to maintain similar visual results, as the spatial relationships between points change with larger grids.

### Setting pscale attribute with channel [Needs Review] [[Ep6, 16:00](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=960s)]
```vex
@pscale = ch("pscale");

float d, t;
t = fit01(chf("speed"), 0, 1);
d = length(@P);
```
Demonstrates creating a pscale attribute controlled by a channel parameter, allowing uniform scaling of points via a UI slider. This is commonly used to control the size of instanced geometry or point sprites, particularly useful when dealing with dense grids where you need to prevent overlapping geometry.

### Setting pscale from channel parameter [[Ep6, 16:14](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=974s)]
```vex
@pscale = ch('pscale');
```
Sets the point scale attribute (@pscale) using a channel reference to allow interactive manipulation of instanced geometry size. This is commonly used when copying geometry to points to control instance scale, particularly useful for preventing overlaps when the grid has high point density.

## chramp Usage

### Color Ramp with Vector Cast [[Ep6, 34:02](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2042s)]
```vex
d = chf('frequency');
d = f;
d = fit(sin(d), -1, 1, min, max);
@scale = fit(sin(d), min, max, 0, 1);
@P.y -= d/2;
d = fit(@d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Uses vector casting on chramp() to create a color ramp parameter interface instead of a float spline. Two fit() operations are chained to first map a sine wave to a custom range for scale, then remap that value back to 0-1 range for driving the color ramp, allowing the same data to control both scale and color attributes.

### Color Ramp with Fit Normalization [[Ep6, 34:14](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2054s)]
```vex
float d = ch('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = vector(min, max, 0);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates using two fit() functions in sequence to first map a sine wave to a custom min/max range for scaling and positioning, then normalize that value back to 0-1 range to properly drive a color ramp. The second fit() ensures the chramp() receives values in the expected 0-1 range, while the first fit() controls the visual scale of the effect.

## Parameter Controls

### Parameterized Quaternion Rotation with Slider [[Ep7, 103:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6208s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(radians(chf("angle")), {1,0,0});
@orient = qmultiply(@orient, extrarot);
```
Creates an orientation quaternion from normalized position as normal and up vector, then applies an additional rotation controlled by an angle parameter slider. The extra rotation is constructed using radians conversion and quaternion multiplication, allowing interactive adjustment of the rotation amount around the X-axis.

### Dynamic Quaternion Rotation Parameter [[Ep7, 103:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6210s)]
```vex
@N = normalize(@P);
@up = {0,1,0};
@orient = quaternion(maketransform(@N, @up));
vector4 extrarot = quaternion(radians(ch('angle')), {1,0,0});

@orient = qmultiply(@orient, extrarot);
```
Creates an interactive rotation control by replacing a hard-coded rotation value with a channel reference. Uses radians() to convert a UI angle parameter into radians, creates a quaternion from it, and multiplies it with the base orientation to allow real-time adjustment of the rotation amount via a slider.

## chramp Usage

### Ramp Control for Noise Remapping [[Ep7, 56:44](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3404s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*f@time);
@a = chramp('noise_rerange', @a);
axis *= trunc(@a*4)*$PI/2;

@orient = quaternion(axis);
```
Demonstrates replacing a fit() function with chramp() to remap noise values using an interactive ramp parameter. The ramp provides visual control over how noise values translate to rotation angles, where the x-axis position of points drives the ramp lookup and the ramp output controls rotation increments.

### Chramp for Interactive Noise Remapping [[Ep7, 57:10](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3430s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P * @Time);
@a = chramp('noise_range', @a);
axis = trunc(@a * 4) * @PI / 2;

@orient = quaternion(axis);
```
Replaces a fixed fit() function with chramp() to enable interactive remapping of noise values via a ramp parameter. The chramp() function takes the noise_range parameter name and uses @a to drive the x-axis of the ramp, allowing real-time adjustment of how noise values map to rotation angles. This provides more flexible artistic control than hardcoded fit ranges.

### Interactive Ramp Control for Noise [[Ep7, 57:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3438s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+@Time);
@a = fit(@a, 0.4, 0.6, 0, 1);
axis = trunc(@a*4)*$PI/2;

@orient = quaternion(axis);

// Improved version using chramp:
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+@Time);
@a = chramp('noise_rerange', @a);
axis = trunc(@a*4)*$PI/2;

@orient = quaternion(axis);
```
Demonstrates replacing fit() with chramp() to enable interactive UI control for remapping noise values. The chramp function creates a ramp parameter that can be adjusted in real-time to control how noise values drive the rotation axis, providing more artistic control than hardcoded fit ranges.

### Ramp Parameter for Noise Remapping [Needs Review] [[Ep7, 57:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3444s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*@Time);
@a = chramp('noise_rerange', @a);
axis = trunc(@a*4)*@a/2;

@orient = quaternion(axis);
```
Demonstrates using chramp() to create an interactive ramp parameter that remaps noise values, providing artist-friendly control over the noise distribution. The ramp parameter 'noise_rerange' is driven by the noise value @a along its horizontal axis, allowing for custom falloff curves and value redistribution without hardcoding fit() ranges.

## Parameter Controls

### Euler to Quaternion Rotation [[Ep7, 71:38](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4298s)]
```vex
vector rot = radians(chv('euler'));
@orient = eulertoquaternion(rot, 0);
```
Demonstrates converting Euler angle rotations to quaternion orientation by reading a vector parameter, converting degrees to radians, and using eulertoquaternion() to set the @orient attribute. This allows using familiar rotation controls in the UI while storing rotation as a quaternion for proper interpolation and transformation.

## chramp Usage

### Animating Quaternion Blend with Ramp [[Ep7, 78:00](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4680s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
float blend = chramp('blendramp', $T % 1);
4@orient = slerp(a, b, blend);
```
Uses a channel ramp parameter to control the blend value between two quaternions over time. The time value modulo 1 cycles between 0 and 1, which drives the ramp lookup to create repeating animated rotation. This demonstrates how any 0-1 value can be passed through a ramp for artistic control over interpolation.

### Quaternion Slerp with Ramp Control [[Ep7, 78:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4704s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0} * $F/2);
float blend = chramp('blendramp', @Time % 1);
@orient = slerp(a, b, blend);
```
This demonstrates using a ramp parameter to control the blend factor in a quaternion slerp operation. The chramp() function samples a 'blendramp' parameter using @Time modulo 1 (cycling 0-1), allowing artistic control over the interpolation curve between two quaternion orientations. By adjusting the ramp shape, you can create varied rotation behaviors like ease-in/ease-out or snap rotations.

### Quaternion Slerp with Ramps [[Ep7, 78:54](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4734s)]
```vex
vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
@orient = slerp(a, b, ch('blend'));

vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
float blend = @Time;
@orient = slerp(a, b, blend);

vector4 a = {0,0,0,1};
vector4 b = quaternion({0,1,0}*$PI/2);
float blend = chramp('myramp', @Time);
@orient = slerp(a, b, blend);
```
Demonstrates three methods of controlling quaternion interpolation: using a channel reference, using @Time directly, and using a ramp lookup with chramp(). The chramp() approach allows for custom interpolation curves including back-and-forth motion by editing ramp control points with different interpolation methods (monotone, Catmull-Rom).

## Parameter Controls

### Declaring UV vector parameter [Needs Review] [[Ep8, 26:06](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1566s)]
```vex
vector uv = chv("uv");
```
Declares a vector variable 'uv' and populates it using the chv() function to read a vector channel parameter named 'uv'. This allows the user to specify UV coordinates through the parameter interface, which will later be used with primuv() to sample positions from the first input geometry.

## See Also
- **VEX Functions Reference** (`vex_functions.md`) -- chramp, chf function signatures
