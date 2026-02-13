# Joy of VEX: Vector Math

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Vector Operations

### Color from Position Math [[Ep1, 22:28](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1348s)]
```vex
@Cd = @N.y;

@Cd = @P.x + 1;

@Cd = @P.x - 0;

@Cd = @P.x * 0 * 0.1;
```
Demonstrates basic mathematical operations on position and normal attributes to set color values. Shows how to add, subtract, and multiply scalar values to position components, creating gradients and variations in color based on geometric properties. These operations build toward more complex color manipulation techniques using mathematical expressions.

### Single Component Math Operations [[Ep1, 22:58](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1378s)]
```vex
@Cd = @P.x + 1;

@Cd = @P.x - 0;

@Cd = @P.x * 0 * 0.1;

@Cd = (@P.x - 0) * 0.1;
```
Demonstrates performing basic mathematical operations on a single component of an attribute (the x component of @P) and assigning the result to color. Shows various arithmetic operations including addition, subtraction, and multiplication on position components to drive visualization attributes.

### Scaling and offsetting position for color [[Ep1, 23:20](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1400s)]
```vex
@Cd = @P.x;

@Cd = @P.x - 1;

@Cd = @P.x - 0;

@Cd = @P.x * 6 * 0.1;

@Cd = (@P.x - 6) * 0.1;
```
Demonstrates basic mathematical operations (subtraction, multiplication) applied to a single component of position (@P.x) to control color values. Shows how to scale and offset position values to fit the 0-1 color range, progressing from direct assignment to normalized mappings using arithmetic.

### Arithmetic Operations on Color [[Ep1, 24:32](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1472s)]
```vex
@Cd = @P.x + 3;

@Cd = @P.x - 6;

@Cd = @P.x * 6 * 0.1;

@Cd = (@P.x - 6) * 0.1;
```
Demonstrates basic arithmetic operations (addition, subtraction, multiplication) applied to position values to modify color attributes. Adding or subtracting values shifts the color range by offsetting which positions map to positive/negative values, while multiplication scales the color gradient. Parentheses control operation order when combining multiple arithmetic operations.

### Integer Division Pitfall [[Ep1, 33:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2036s)]
```vex
@Cd = @ptnum / @numpt;
```
Demonstrates a common VEX pitfall where dividing two integers (@ptnum and @numpt) results in integer division, producing zero for all points because the fractional component is truncated. This occurs because both attributes are integers and VEX performs integer division when both operands are integers, losing the decimal values needed for a proper gradient.

### Type Casting for Integer Division [[Ep1, 35:42](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2142s)]
```vex
@Cd = float(@ptnum)/@numpt;

@Cd = float(@ptnum)/@numpt;

@Cd = float(@ptnum)/100;
```
Demonstrates casting @ptnum to float to prevent integer division when creating normalized values. By wrapping @ptnum with float(), the division produces decimal values ranging from 0 to nearly 1, rather than only 0 or 1 from integer division. The examples show dividing by @numpt (total points) and by a constant 100 to create gradients.

### Normalizing Point Numbers with Division [[Ep1, 37:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2276s)]
```vex
@Cd = float(@ptnum) / @numpt;
```
Divides the current point number by the total number of points to create a normalized 0-to-1 gradient across all points. The @ptnum attribute increments for each point while @numpt remains constant, creating smooth color progression. This can be modified by replacing @numpt with any constant value to control where the gradient reaches 1.0.

## Remapping (fit, clamp)

### Distance-Based Y Manipulation [Needs Review] [[Ep2, 22:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1368s)]
```vex
float d = length(@P);
@P.y = -d + 10;
```
Demonstrates using distance from origin (length(@P)) to drive point Y position with various mathematical operations. Shows how negation and offsets can be used to shift and invert value ranges, with the final example using negative distance plus an offset of 10 to raise and lower the geometry based on radial distance.

### Distance-based Y displacement with clamp and fit [[Ep2, 23:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1426s)]
```vex
float d = length(@P);
@P.y = fit(d, 1, 2, 1, 2);
```
Demonstrates various mathematical operations on point Y positions based on distance from origin. Uses length() to compute distance, then applies transformations like clamping (constraining values to a range) and fit() (remapping values from one range to another) to control the vertical displacement based on radial distance.

### Clamping Distance Values [[Ep2, 24:04](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1444s)]
```vex
float d = length(@P);
@P.y = clamp(d, 0, 3);
```
Calculates the distance from the origin for each point and uses the clamp function to constrain that distance value between 0 and 3, then assigns the clamped result to the y-component of the point position. This demonstrates how clamp takes three arguments: the value to constrain, the minimum bound, and the maximum bound.

### Clamping and Fitting Distance Values [[Ep2, 26:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1616s)]
```vex
float d = length(@P);
@P.y = clamp(d, 0, 1);
```
Uses the clamp function to constrain the distance-based height values between a minimum and maximum range, effectively flattening the geometry at the top and bottom boundaries. This prevents values from exceeding specified limits, creating flat plateaus where the distance would otherwise continue increasing or decreasing.

### Clamp and Fit Functions [[Ep2, 27:18](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1638s)]
```vex
float d = length(@P);
@P.y = fit(d, 0, 2, 0, 10);
```
Uses the fit() function to remap distance values from one range to another, demonstrating how to scale the y-position based on distance from origin. The clamp() function constrains values to a specified range without deleting geometry, while fit() provides more flexible range remapping.

### Fit and Clamp Range Control [[Ep2, 27:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1678s)]
```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
@P.y = fit(d, imin, imax, 0, 1);
```
Using the fit() function to remap distance values to a specific range, with channel references for dynamic parameter control. The fit() function maps an input range (defined by imin and imax) to an output range (0 to 1), useful for constraining values while maintaining proportional distribution. This approach is often combined with clamp() for additional range enforcement.

### Fit and Clamp Range Remapping [[Ep2, 28:00](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1680s)]
```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
d = fit(d, imin, imax, 0, 1);
d = clamp(d, 0.5, 1);
@P.y = d;
```
Demonstrates combining fit() and clamp() functions to remap and constrain distance values. The fit() function remaps distance from an input range (controlled by channel parameters) to a 0-1 range, then clamp() further constrains the result to 0.5-1 before assigning to point Y position.

### Fit and Clamp Combination [[Ep2, 30:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1848s)]
```vex
float d = length(@P);
float lmin = ch('fit_in_min');
float lmax = ch('fit_in_max');
d = fit(d, lmin, lmax, 1, 0);
d = clamp(d, 0.5, 1);
@P.y = d;
```
Demonstrates combining fit() and clamp() functions to remap and constrain distance values. The fit() function remaps the distance range while inverting it (output 1 to 0), then clamp() further restricts the result to a subrange between 0.5 and 1, with parameters controlled by channel references for interactive adjustment.

### Chaining fit and clamp operations [[Ep2, 30:54](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1854s)]
```vex
float d = length(@P);
d = fit(d, 1, 2, 1, 0);
d = clamp(d, 0.5, 1);
@P.y = d;

float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
```
Demonstrates combining fit() to remap and invert a distance range, followed by clamp() to constrain values to a sub-range, then applying the result to point Y positions. Shows how to chain multiple range operations and introduces channel references for parameterizing fit() inputs.

### Distance-based Y displacement with clamping [[Ep2, 30:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1856s)]
```vex
float d = length(@P);
d = fit(d, 0, 1, 1, 0);
d = clamp(d, 0.5, 1);
@P.y = d;
```
Calculates distance from origin, remaps the range inversely (far becomes near), then clamps values between 0.5 and 1.0 to limit the range, finally applying this to the Y position. This creates a height field where points further from origin get elevated, but with controlled minimum and maximum heights.

### Fit and Clamp Functions [[Ep2, 31:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1890s)]
```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
```
Demonstrates using fit() to remap values from one range to another and clamp() to constrain values within a minimum and maximum range. The code progressively shows different combinations of fit() and clamp() operations on distance values, culminating in channel-driven parameters for interactive control of the input range.

### Fit and Clamp with Channel Refs [[Ep2, 32:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1946s)]
```vex
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
float outmin = ch('fit_out_min');
float outmax = ch('fit_out_max');
d = fit(d, imin, imax, outmin, outmax);
@P.y = d;
```
Demonstrates using the fit() function to remap distance values from one range to another, then using clamp() to constrain values to a sub-range. The final version exposes all fit parameters as channel references for interactive control, allowing dynamic remapping of the distance field to control point height displacement.

### Fit and Clamp Range Remapping [[Ep2, 36:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2186s)]
```vex
float d = length(@P);
float imin = ch("fit_in_min");
float imax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d = fit(d, imin, imax, outmin, outmax);
@P.y = d;
```
This example demonstrates using the fit() function with channel references to remap distance values from an input range to an output range, allowing interactive control over how point heights are distributed. The input range clamps incoming distance values, while the output range stretches or compresses the remapped results, providing flexible control over the final height distribution.

### Remapping Values with Fit [[Ep2, 41:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2490s)]
```vex
float angle = ch("fit_in_min");
float inmin = ch("fit_in_min");
float inmax = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
float d = fit(angle, inmin, inmax, outmin, outmax);
@P.y = d;
```
This example demonstrates using the fit() function to remap a value from one range to another, with channel references providing control over input and output ranges. The remapped value is applied to the Y position of points, preparing for more advanced work with ramps and curves.

## Length & Distance

### Modulo for Cyclic Ramp Mapping [[Ep2, 51:52](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3112s)]
```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
@P.y *= chramp('myramp', d);
@P.y *= ch('height');
```
Uses the modulo operator to create cyclic patterns by constraining a distance-based value to the 0-1 range, which is then used to sample a ramp parameter for controlling point height. The modulo ensures the pattern repeats as distance increases, creating concentric bands of deformation.

## Remapping (fit, clamp)

### Normalized Values and Fit Function [[Ep2, 66:44](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4004s)]
```vex
s@greeting = "yessirree";
i@test = 123;
f@scale = ch("scale");
v@P = @P * @test;
f@cd = @P.y;
v@Cd = fit(@P.y, 0, 1, 1, 0);
i@x = 1;
@P.y = chramp("coramp", @P.z);
@P.y *= ch("height");
```
Demonstrates the use of the fit() function to normalize and remap values between different ranges. The example shows how to take values and bring them into a normalized 0-1 range, which is particularly important for working with vectors like normals where direction needs to be distinguished from magnitude.

### Normalizing Values with fit() [Needs Review] [[Ep2, 66:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4008s)]
```vex
@Cd = fit(@P.y, -1, 1, 0, 1);
```
Demonstrates using the fit() function to normalize values from one range to another, specifically converting position Y values from -1 to 1 into the 0 to 1 range. Normalized values are important for vectors like normals where direction needs to be described independently of magnitude.

## Vector Operations

### Modulo on Color Attributes [[Ep2, 79:28](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4768s)]
```vex
@Cd.r = @ptnum % 5;
@P.y = @ptnum % 5;
@Cd.r = @Time % 0.7;
```
Demonstrates using the modulo operator (%) to create repeating patterns in point attributes. The operator works on both integer values like @ptnum to create stepped patterns, and fractional values like @Time to create cycling color animations. This creates characteristic sawtooth wave patterns in the visualized data.

### Modulo Operator Looping Behavior [[Ep2, 80:40](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4840s)]
```vex
@Cd.r = @Time % 0.2;
```
Demonstrates the modulo operator with @Time to create a looping animation that cycles between 0 and 0.2. The fractional modulo divisor creates a rapid sawtooth pattern in the red color channel, with values repeatedly climbing to 0.2 and jumping back to zero, producing continuous cycling behavior.

### Modulo operator with Time [Needs Review] [[Ep2, 80:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4846s)]
```vex
@P.y = @Time % 5;

@Cd.r = @Time % 0.7;
```
Demonstrates using the modulo operator (%) with the @Time global variable to create cyclic animation values. The first example cycles position vertically every 5 time units, while the second applies a modulo with 0.7 to the red color channel, creating messy remainders due to the fractional divisor. Using whole numbers like 2 instead of 0.7 produces cleaner cyclic values.

## Length & Distance

### Modulo for Looping Values [[Ep2, 81:24](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4884s)]
```vex
@Cd.r = @Time % 1;

@P.y = @ptnum % 5;

float d = length(@P);
d *= ch('scale');
@P.y = d;
```
The modulo operator (%) creates looping values that repeat at regular intervals. Using @Time % 1 creates a color value that loops every second, while @ptnum % 5 distributes point heights into 5 repeating levels, demonstrating how modulo can create patterns across both time and geometry.

### Creating Stepped Distance Values [[Ep2, 83:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4996s)]
```vex
float d = length(@P);
d *= ch("scale");
float f = ch("factor");
d /= f;
d = trunc(d);
d *= f;
@P.y = d;
```
This technique creates stepped (quantized) values from smooth distance calculations by dividing the scaled distance by a factor, truncating to remove decimals, then multiplying back by the factor. The result produces discrete height levels in @P.y rather than smooth continuous values, useful for creating terraced or stepped geometric effects.

### Using trunc() for value scaling [[Ep2, 84:04](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5044s)]
```vex
float d = length(@P);
d *= ch('scale');
float factor = ch('factor');
@P.y = d;
d = trunc(d);
@P.y = d;
```
Demonstrates using the trunc() function to remove decimal components from scaled distance values. The technique requires first scaling values into a range where truncation produces meaningful stepped results, as very small or very large numbers won't benefit from decimal removal.

### Truncating Distance Values [Needs Review] [[Ep2, 89:24](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5364s)]
```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
d *= f;
@Cy = d;
```
This code calculates the distance from the origin using length(@P), scales it with channel parameters, then uses trunc() to quantize the distance value into discrete steps controlled by the 'factor' parameter. The truncated and rescaled distance is assigned to the custom @Cy attribute, creating stepped/banded distance values.

### Stepped Ramp Using Truncation [[Ep2, 89:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5396s)]
```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
d *= f;
@P.y = d;
```
Creates a stepped ramp effect by calculating distance from origin, scaling it, dividing by a factor value, truncating to remove decimals, then multiplying back by the factor. This technique produces discrete steps rather than continuous values, allowing for banded or terraced geometry.

### Stepped Ramp Using Truncation [[Ep2, 90:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5430s)]
```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
d *= f;
@P.y = d;

d *= ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```
Creates stepped values by dividing the distance from origin by a factor, truncating to remove decimals, then multiplying back by the factor to create quantized steps. The result is then mapped through a ramp with pre and post scaling to control the final displacement on the Y axis.

### Distance-based Color and Position [Needs Review] [[Ep2, 91:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5476s)]
```vex
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
@Cd.r = d;
d /= f;
@Cd.r = d;
d = trunc(d);
d += f;
@P.y = d;
```
This code calculates the distance from the origin using length(@P), scales and divides it by channel-driven parameters, then applies truncation to create stepped values. The truncated distance values are used to set red color and modify Y position, creating a stepped displacement pattern based on radial distance.

### Value Quantization with Modulo [Needs Review] [[Ep2, 91:54](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5514s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = chramp('ramp', d);

float f = ch('frequency');
d /= f;
d *= trunc(d);
d %= f;
@Cd.y = d;
```
Demonstrates quantizing continuous values into stepped functions by dividing distance by a frequency parameter, truncating to remove fractals, then using modulo to create repeating bands. The technique creates discrete color bands in the green channel based on quantized distance values from the origin.

## Vector Operations

### Modulo positioning and time-based color [[Ep2, 99:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5988s)]
```vex
@P.y = @ptnum % 5;

@Cd.r = @Time % 0.7;
```
Uses the modulo operator to create vertical position patterns based on point numbers, and applies time-based modulo to drive red color channel cycling. The modulo operation creates repeating patterns by wrapping values, useful for creating regular spacing or cyclical animation effects.

## Dot Product

### Dot Product with Point Reference [[Ep4, 10:34](https://www.youtube.com/watch?v=66WGmbykQhI&t=634s)]
```vex
vector pos = point(1, 'P', 0);
@Cd = dot(@N, pos);

vector pos = point(1, 'P', 0);
@Cd = dot(@N, normalize(pos));

@Cd = dot(@N, chv('angle'));

@Cd = dot(@N, chv('angle'));
```
Demonstrates using the point() function to read a position from a different input and calculate dot product with normals. Shows progression from using raw position vector, to normalized vector, to eventually replacing with a channel reference parameter for more interactive control. Normalizing the direction vector ensures the dot product only measures angle relationship without magnitude influence.

### Dot Product with Point Position [[Ep4, 10:36](https://www.youtube.com/watch?v=66WGmbykQhI&t=636s)]
```vex
@Cd = dot(@N, chv('angle'));

vector pos = point(1, 'P', 0);
@Cd = dot(@N, pos);

vector pos = point(1, 'P', 0);
pos = normalize(pos);
@Cd = dot(@N, pos);
```
Demonstrates using the dot product between surface normals and a direction vector, evolving from a parameter-driven angle to a point position lookup. Shows how to read a point's position from an input geometry using point() function, then normalizes it to create a direction vector. Normalizing removes magnitude so the dot product purely measures directional alignment rather than being affected by distance scaling.

### Normalized Direction for Surface Masking [[Ep4, 13:58](https://www.youtube.com/watch?v=66WGmbykQhI&t=838s)]
```vex
@Cd = dot(@N, {0,1,0});

vector pos = point(1, 'P', 0);
@Cd = dot(@N, pos);

pos = normalize(pos);
@Cd = dot(@N, pos);
```
Demonstrates creating a surface mask by calculating the dot product between surface normals and a direction vector from another input. Normalizing the position vector ensures the mask values remain in a valid 0-1 range regardless of the control point's distance, preventing overbright values and focusing purely on directional alignment rather than vector magnitude.

### Normalizing vectors for dot product [[Ep4, 14:08](https://www.youtube.com/watch?v=66WGmbykQhI&t=848s)]
```vex
vector pos = point(1, "P", 0);
@Cd = dot(@N, pos);

pos = normalize(pos);
@Cd = dot(@N, pos);
```
Demonstrates the importance of normalizing vectors before using them in dot product calculations. Without normalization, the magnitude of the position vector affects the result, causing unwanted brightness variations. Normalizing ensures the dot product only evaluates direction, producing consistent masking regardless of vector length.

### Normalizing Position for Dot Product Mask [[Ep4, 14:10](https://www.youtube.com/watch?v=66WGmbykQhI&t=850s)]
```vex
vector pos = point(1, "P", 0);
pos = normalize(pos);
@Cd = dot(@N, pos);
```
Demonstrates normalizing a position vector before using it in a dot product calculation to create a directional mask. By normalizing the position vector to unit length, the dot product result is based purely on direction rather than being influenced by the magnitude of the position vector, preventing overly bright results when the position is far from the origin.

### Normalizing Vectors for Directional Dot Product [[Ep4, 16:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=972s)]
```vex
vector pos = point(1, 'P', 0);
pos = normalize(pos);
@Cd = dot(@N, pos);
```
Retrieves a position vector from point 0 of the second input, normalizes it to unit length, then uses it in a dot product with surface normals to create a directional shading effect. Normalizing the direction vector ensures consistent lighting values regardless of the original vector's magnitude.

### Cross Product and Normal Manipulation [[Ep4, 17:44](https://www.youtube.com/watch?v=66WGmbykQhI&t=1064s)]
```vex
vector pos = point(1, "P", 0);
pos = normalize(pos);
@Cd = dot(@N, pos);

@N = cross(@N, {0,1,0});
```
Demonstrates cross product usage by reading a position from the second input, normalizing it, computing a dot product for color visualization, and then modifying the normal using cross product with an up vector. The cross product creates a new normal perpendicular to both the original normal and the Y-axis.

## Cross Product

### Cross Product Normal Rotation [[Ep4, 19:34](https://www.youtube.com/watch?v=66WGmbykQhI&t=1174s)]
```vex
@N = cross(@N, {0,1,0});
```
Computes the cross product of the normal vector with the up vector {0,1,0}, which rotates normals 90 degrees to point sideways. The cross product produces a vector perpendicular to both input vectors, effectively transforming outward-pointing normals into side-facing normals.

### Cross Product for Surface Normals [[Ep4, 20:22](https://www.youtube.com/watch?v=66WGmbykQhI&t=1222s)]
```vex
@N = cross(@P, {0,1,0});
```
Calculates normals that point along the surface rather than outward by using the cross product of the point position and the up vector {0,1,0}. This demonstrates the right-hand rule, creating normals that are perpendicular to both the position vector and the up vector, effectively 'combing' them along the surface.

### Cross Product Right Hand Rule [[Ep4, 22:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=1332s)]
```vex
vector tmp = cross(@N, {0,1,0});
@N = cross(@N, tmp);
```
Demonstrates the right-hand rule for cross products by first computing a perpendicular vector from the normal and up vector, then using that temporary vector to compute a second perpendicular direction. This creates an orthogonal vector system where the final normal direction is perpendicular to both the original normal and the up vector.

### Cross Product to Recalculate Normal [Needs Review] [[Ep4, 22:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=1334s)]
```vex
vector tmp = cross(@N, {0,1,0});
@N = cross(tmp, tmp);
```
Demonstrates the right-hand rule by computing a temporary vector from crossing the normal with the up vector, then crossing that result with itself to recalculate the normal. This illustrates how any two perpendicular vectors in a coordinate system can be used to derive the third using the cross product.

### Cross Product for Normal Manipulation [[Ep4, 22:26](https://www.youtube.com/watch?v=66WGmbykQhI&t=1346s)]
```vex
@N = cross(@N, {0,1,0});

vector tmp = cross(@N, {0,1,0});
@N = normalize(tmp);
```
Demonstrates using the cross product to rotate normals by crossing them with the Y-axis vector. The second form stores the cross product result in a temporary variable before normalizing it and assigning back to @N, showing the proper workflow for maintaining unit-length normals. This creates a twirling effect around the specified axis based on the right-hand rule.

### Cross Product for Normal Calculation [[Ep4, 22:36](https://www.youtube.com/watch?v=66WGmbykQhI&t=1356s)]
```vex
@N = cross(@v, {1,1,0});

vector tmp = cross(@v, {0,1,0});
@N = cross(tmp, @v);
```
Demonstrates using the cross product to compute normals by crossing velocity vectors with arbitrary axis vectors. The second approach creates an orthogonal frame by performing two successive cross products, ensuring the resulting normal is perpendicular to both the velocity and the intermediate temporary vector. Different axis vectors (like {1,1,0}) cause the normals to "twirl around" that specified axis direction.

### Cross Product for Normal Direction [[Ep4, 22:38](https://www.youtube.com/watch?v=66WGmbykQhI&t=1358s)]
```vex
@N = cross(@N, {1,0,0});
```
Demonstrates using the cross product to rotate normals by crossing them with a reference axis vector. The cross product follows the right-hand rule, producing a perpendicular vector that effectively twirls or combs normals around the specified axis direction. Different axis vectors will cause normals to orient around different directional axes.

### Cross Product Normal Manipulation [[Ep4, 22:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=1366s)]
```vex
@N = cross(@N, {1,1,0});
```
Uses the cross() function to compute a new normal direction perpendicular to both the current normal and a custom axis vector {1,1,0}. This creates a twirling effect where normals rotate around the specified axis, with the direction determined by the right-hand rule of cross products.

### Double Cross Product [[Ep4, 23:28](https://www.youtube.com/watch?v=66WGmbykQhI&t=1408s)]
```vex
vector tmp = cross(@N, {0, -1, 0});
@N = cross(@N, tmp);
```
Demonstrates a double cross product operation where the normal is first crossed with a vector, stored in a temporary variable, then crossed again with the original normal. This technique creates a specific rotation pattern where normals rotate around an axis defined by the first cross product.

### Multiple Cross Products and Cycles [[Ep4, 24:48](https://www.youtube.com/watch?v=66WGmbykQhI&t=1488s)]
```vex
vector tmp = cross(@P, {0,1,0});
@N = cross(@N, tmp);

vector tmp = cross(@P, {0,1,0});
@N = cross(@N, tmp);

vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);

vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);

vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);

vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```
Demonstrates that repeatedly applying cross products creates a cycle that eventually returns to the starting orientation. This technique is used in grooming operations to create gravity-based hair/fur layouts by performing double cross products with the up vector {0,1,0}. Triple, quadruple, and higher-order cross products will eventually cycle back to the original normal direction.

### Iterative Cross Product Rotations [[Ep4, 26:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=1560s)]
```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```
Demonstrates iterative application of the cross product to rotate normals around an axis. Takes the initial cross product of the normal with the up vector, then repeatedly crosses the original normal with the result to create cumulative rotations. After four cross operations, the normals rotate 360 degrees back to their starting orientation.

### Sequential Cross Products for Vector Rotation [[Ep4, 26:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=1562s)]
```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```
Demonstrates sequential cross product operations to rotate normals around an axis. Takes the cross product of the normal with the up vector, then crosses the normal with that result, and repeats the process to create a rotation sequence. This produces a 90-degree rotation pattern around the axis, where four iterations would complete a full circle.

### Rotating Normals with Cross Products [[Ep4, 26:32](https://www.youtube.com/watch?v=66WGmbykQhI&t=1592s)]
```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```
Demonstrates iterative rotation of normals by 90 degrees using repeated cross products. Each successive cross() operation with the same starting normal rotates the vector another 90 degrees around the rotation axis, creating a technique to rotate normals in 90-degree increments without explicit matrices.

### Repeated Cross Product Operations [[Ep4, 28:30](https://www.youtube.com/watch?v=66WGmbykQhI&t=1710s)]
```vex
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```
Demonstrates iterative application of the cross product function, repeatedly computing the cross product between the normal vector and an intermediate result. This creates a cascading transformation of the normal through multiple cross product operations, ultimately reassigning the final result back to @N.

## Vector Operations

### Vector Addition Basics [[Ep4, 31:54](https://www.youtube.com/watch?v=66WGmbykQhI&t=1914s)]
```vex
vector a = chv('a');
vector b = chv('b');
@N = a + b;
```
Demonstrates vector addition by reading two vector parameters and storing their sum in the normal attribute. Vector addition works geometrically by placing vectors tip-to-tail, where the resulting vector points from the tail of the first vector to the tip of the second vector.

### Vector Subtraction Setup [Needs Review] [[Ep4, 34:10](https://www.youtube.com/watch?v=66WGmbykQhI&t=2050s)]
```vex
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@N = b - a;

vector a = @P;
vector h = point(1, "P", 0);
```
Demonstrates setting up vector subtraction between two points by reading their positions from different input geometries. The first section shows calculating a direction vector (@N) from the difference between two point positions, while the second section begins a variation using the current point position (@P) as one of the vectors.

### Vector Subtraction Between Points [[Ep4, 34:22](https://www.youtube.com/watch?v=66WGmbykQhI&t=2062s)]
```vex
vector a = chv('A');
@N += a;

vector a = point(0, "P", 0);
vector b = point(1, "P", 0);

@N = b - a;

vector a = @P;
vector b = point(1, "P", 0);
```
Demonstrates vector subtraction by reading positions from two different point sources using the point() function. Shows progression from channel-based vector input to calculating direction vectors between points by subtracting their positions, with the final approach combining the current point's position with a referenced point.

### Vector Subtraction for Normals [[Ep4, 36:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=2216s)]
```vex
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);

@N = b - a;
```
Demonstrates vector subtraction to compute direction vectors by reading positions from two different inputs. Each point on the sphere (input 0) reads its own position as vector 'a' and a reference point's position from input 1 as vector 'b', then computes the direction vector (b - a) and assigns it to the normal attribute, making all points reference the same target point.

### Vector Subtraction for Direction Vectors [Needs Review] [[Ep4, 37:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=2276s)]
```vex
vector a = {0,1,0};
vector b = point(1,"P",0);

@v = b-a;

vector origin = point(1,"P",0);
@v = @P - origin;
```
Demonstrates using vector subtraction to create direction vectors between points. By subtracting two position vectors (b-a or @P-origin), you get a vector that points from one position to another, useful for connecting points or creating wire-like effects. Reversing the order (a-b) makes vectors point in the opposite direction.

## Dot Product

### Dot Product Basics [[Ep4, 3:54](https://www.youtube.com/watch?v=66WGmbykQhI&t=234s)]
```vex
@Cd = @N.y;

@Cd = @N.y;

@Cd = dot(@N, {0,1,0});

@Cd = dot(@N, chv('angle'));
```
Demonstrates multiple ways to calculate the dot product between a normal vector and an up vector (0,1,0). Shows the progression from direct component access (@N.y) to using the explicit dot() function, culminating in making the comparison vector user-controllable via a channel reference.

## Vector Operations

### Vector Multiplication Setup [Needs Review] [[Ep4, 41:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=2506s)]
```vex
vector a = @P;
vector b = point(1, "P", 0);

@N = a + b;
```
This code demonstrates setting up vectors for a multiplication operation by storing the current point position in vector 'a' and fetching point 0's position from input 1 into vector 'b'. The normal is temporarily set to the sum of these vectors as a placeholder before implementing proper multiplication with a scale parameter.

### Vector Scaling with Parameters [Needs Review] [[Ep4, 43:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=2580s)]
```vex
*= ch('scale');
```
Uses the compound assignment operator to scale a vector attribute by a channel parameter value. The *= operator multiplies the left-hand operand in place, allowing direct modification of vector attributes. When multiplied by negative values, this operation inverts the vector direction while changing its magnitude.

### Vector Scaling and Direction [[Ep4, 45:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=2714s)]
```vex
vector a = @P;
vector b = point(1, @ptnum, "P");

@N = b - a;

@N *= chv('scalevec');

vector origin = point(1, 'P', 0);
@v = @P - origin;
```
Calculates a vector from current point to a corresponding point in second input, then scales it by a channel vector parameter. The scaling can stretch vectors along certain axes (e.g., x-axis) and negate others (e.g., z-axis) to flip directions, creating interesting patterns where some vectors point inward while others maintain outward direction. Also demonstrates calculating velocity vectors relative to an origin point.

## Dot Product

### Dot Product with Normals [[Ep4, 4:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=254s)]
```vex
@Cd = @N.y;

@Cd = -@N.y;

@Cd = dot(@N, {0,1,0});

@Cd = dot(@N, chv('angle'));
```
Demonstrates the dot product as a method of multiplying vectors to get scalar results. Shows progression from component access (@N.y) to explicit dot product function, including negation for value inversion and using channel parameters for dynamic vector inputs. The dot product measures alignment between vectors, useful for lighting, falloffs, and directional effects.

### Dot Product for Directional Shading [[Ep4, 7:10](https://www.youtube.com/watch?v=66WGmbykQhI&t=430s)]
```vex
@Cd = -@N.z;

@Cd = -@N.y;

@Cd = dot(@N, {0,1,0});

@Cd = dot(@N, chv('angle'));
```
The dot product compares the direction of two vectors, returning 1 when they point in the same direction, 0 when perpendicular, and -1 when opposite. This allows coloring geometry based on how normals align with an arbitrary direction vector, rather than just using individual vector components. Using chv('angle') allows interactive control of the comparison direction via a parameter.

### Dot Product for Surface Orientation [[Ep4, 8:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=480s)]
```vex
@Cd = dot(@N, chv('angle'));
```
Uses the dot product to compare the surface normal (@N) against a user-defined direction vector from a channel reference. The dot product returns values from -1 to 1, where 1 means the vectors are aligned, 0 means perpendicular (90 degrees), and -1 means opposite directions, creating a smooth gradient based on surface orientation relative to the input direction.

### Dot Product with Normal and Up Vector [[Ep4, 8:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=492s)]
```vex
@Cd = dot(@N, {0, 1, 0});
```
Uses the dot product between the surface normal (@N) and an up vector (0,1,0) to generate a color value. The dot product returns a smooth range between -1 and 1 based on the angle between the two vectors, where parallel vectors return 1, perpendicular return 0, and opposite return -1.

### Dot Product with Vectors and Channels [[Ep4, 8:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=526s)]
```vex
@Cd = dot(@N, {0,1,0});

@Cd = @N.y;

@Cd = dot(@N, {0,1,0});

@Cd = dot(@N, chv('angle'));

vector pos = point(0, 'P', 0);
@Cd = dot(@N, pos);
```
Demonstrates multiple approaches to computing dot products for lighting effects, starting with explicit vectors, then using component access, progressing to channel-driven vectors with chv(), and finally using point attributes. Shows equivalence between @N.y and dot(@N, {0,1,0}) for top-down lighting calculations.

### Dot Product Direction Comparison [[Ep4, 9:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=586s)]
```vex
@Cd = dot(@N, chv('angle'));

@Cd = dot(@N, (0,1,0));

@Cd = dot(@N, chv('angle'));

vector pos = point(1,"P",0);
@Cd = dot(@N, pos);

vector pos = point(1,"P",0);
```
Demonstrates using dot product to compare normal direction against various reference vectors, including channel parameter vectors, hardcoded directions like (0,1,0), and point positions from other geometry. The dot product result is mapped to color, showing how surface orientation relates to the reference direction, though magnitude scaling can cause over-brightness that needs normalization.

## Length & Distance

### Matrix Types and Orientation Vectors [Needs Review] [[Ep7, 114:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6844s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};

// Convert quaternion orientation to matrix
matrix3 m = qconvert(Qorient);
@N = {0,0,1} * m;
@up = {0,1,0} * m;

// Alternative: extract from matrix rows
matrix3 m = qconvert(Qorient);
vector up = set(m);
@N = normalize(m[2]); // z axis
@up = normalize(m[1]); // y axis
```
Demonstrates converting quaternion orientation to matrix form and extracting orientation vectors. Shows two approaches: multiplying basis vectors by the matrix, or directly accessing matrix rows to extract the Z-axis (normal) and Y-axis (up vector) from the transformation matrix.

## Vector Operations

### Identity Matrix Creation [[Ep7, 127:54](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7674s)]
```vex
matrix3 m = [[1,0,0,0,1,0,0,0,1]];

matrix3 m = ident();
```
Demonstrates two equivalent ways to create a 3x3 identity matrix in VEX: explicitly defining the matrix values as a grid of numbers with ones on the diagonal and zeros elsewhere, or using the built-in ident() function which returns the same identity matrix. The identity matrix preserves transformations when used in matrix multiplication.

### Identity Matrix Definition [[Ep7, 128:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7700s)]
```vex
matrix3 m = [[1,0,0],[0,1,0],[0,0,1]];

matrix3 m = ident();
```
Demonstrates two ways to create a 3x3 identity matrix in VEX. The first explicitly defines the matrix as a grid where diagonal elements are 1 and off-diagonal elements are 0, representing the basis vectors for x, y, and z axes. The second uses the built-in ident() function as a shorthand for the same result.

### Identity Matrix Declaration [[Ep7, 129:12](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7752s)]
```vex
matrix3 m = {1,0,0,0,1,0,0,0,1};
```
Demonstrates the explicit declaration of a 3x3 identity matrix in VEX using literal values. This verbose syntax sets each of the nine matrix elements individually (diagonal ones, off-diagonal zeros), representing a matrix with no rotation or scaling applied. This method is shown as the foundation before introducing the cleaner ident() function approach.

### Identity Matrix Initialization [[Ep7, 129:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7768s)]
```vex
matrix3 m = ident();
```
The ident() function creates an identity matrix (no rotation, no scaling) - equivalent to a transform in world space with all diagonal values as 1 and all other values as 0. This is a cleaner alternative to manually writing out the matrix values with zeros and ones, and is similar to using quaternion(0,0,0,1) for orient attributes.

### Matrix Casting 4x4 to 3x3 [[Ep7, 140:52](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8452s)]
```vex
matrix3 m = matrix3(myFancyMatrix);

matrix pft = primintrinsic(0, 'packedfulltransform', @ptnum);

4@a = pft;
```
Demonstrates casting a 4x4 matrix to a 3x3 matrix using explicit type conversion with matrix3(). The example retrieves a packed primitive's full transform as a 4x4 matrix using primintrinsic, then shows how it could be cast down to a 3x3 matrix, similar to casting other data types like floats.

### Matrix Structure and Components [[Ep7, 144:00](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8640s)]
```vex
// Example 4x4 transformation matrix structure
matrix m = {0.365308, 0.584615, -0.121554, 0.0,
            -0.534593, 0.478389, 0.696304, 0.0,
            0.663726, -0.27805, 0.696304, 0.0,
            0.0, 0.0, 0.0, 1.0};

// First 3x3 block contains rotation and scale
// Last column (indices 3,7,11) contains translation
// Translation values are human-readable in the matrix
```
A 4x4 transformation matrix in VEX is structured with the upper-left 3x3 block containing rotation and scale information, while the fourth column (indices 3, 7, 11) contains the translation values which are directly human-readable. The bottom row is typically [0, 0, 0, 1] for homogeneous coordinates.

### Extracting rotation and scale from 4x4 matrix [Needs Review] [[Ep7, 144:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8670s)]
```vex
f[]@matrix3 = {0.54813, -0.13154, 0.0, 0.034593, 0.478835, 0.006364, 0.0, 0.066738, 0.27055, 0.006364, 0.0, 0.0, 0.0, 0.0, 1.0};
```
This declares a float array attribute containing 15 values representing a flattened 4x4 transformation matrix. The transcript discusses how translation values are visible in specific positions of the matrix, and introduces the concept of extracting just the rotation and scale components by converting to a 3x3 matrix.
