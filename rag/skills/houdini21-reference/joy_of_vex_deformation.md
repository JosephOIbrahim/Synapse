# Joy of VEX: Deformation

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
v = fit(0, ch("radius"), 1, 0);  // Fit and Sine Wave Deformation
float d = length(@P);  // Applying Sine Wave to Position
float d = length(@P);  // Distance-Based Displacement
```

## Wave Deformation

### Surface Displacement with Normals [[Ep2, 11:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=674s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d *= @Time;
@P.y = sin(d);

@P += @N * ch('push');
```
This demonstrates the difference between arbitrary displacement and normal-based displacement. The first section creates a wave effect by calculating distance from origin and modifying only the Y component, which doesn't respect the surface direction. The corrected approach uses @N to push points along their surface normals, properly respecting the geometry's orientation.

### Normal-based displacement [Needs Review] [[Ep2, 11:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=676s)]
```vex
float d = length(@P);
d *= ch('N_scale');
d *= @Frame;
@P.y = sin(d);

@P += @N * ch('push');
```
This code demonstrates the difference between non-directional displacement (modifying only @P.y based on distance from origin) and proper normal-based displacement using @N. The first section creates a wave pattern by calculating distance from origin and applying it to the Y axis, while the second section properly displaces points along their surface normals using a channel-driven push value.

### Normal-based Surface Displacement [[Ep2, 11:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=692s)]
```vex
float d = length(@P);
d *= ch("v_scale");
d *= PI;
@P.y = sin(d);

@P += @N * ch("push");
```
Creates a sinusoidal displacement pattern based on distance from origin, then offsets geometry along surface normals. The normal-based offset allows the undulation to follow the surface topology rather than occurring strictly in world space, producing more natural-looking deformation on curved surfaces.

### Animated Wave Displacement with Controls [[Ep2, 12:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=752s)]
```vex
float d = length(@P);
d *= ch('x_scale');
d += @Frame;
@P += @N * sin(d) * ch('wave_height');
```
Creates an animated wave displacement effect by calculating distance from origin, scaling it with a channel parameter, adding frame number for animation, and displacing points along their normals using a sine wave modulated by a height control. This technique produces radial wave patterns that propagate outward over time.

### Animated Sine Wave Deformation [[Ep2, 13:52](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=832s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N*sin(d)*ch('wave_height');
```
Creates an animated sine wave deformation on geometry by calculating distance from origin, scaling it with a channel parameter, adding time for animation, then offsetting points along their normals by the sine of this value multiplied by a wave height control. The combination of distance-based calculation and time creates rippling waves that emanate from the center.

### Animated Sine Wave Displacement [[Ep2, 13:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=838s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N*sin(d) * ch('wave_height');
```
Creates an animated ripple effect by calculating distance from origin, scaling it with a channel parameter, adding time for animation, then displacing points along their normals using a sine wave multiplied by a height control. The combination of distance-based calculation and time offset creates radial waves emanating from the center.

### Animated Wavelength Displacement [[Ep2, 14:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=842s)]
```vex
float d = length(@P);
d ^= ch('v_scale');
d += @Time;
@P += @N*sin(d);
```
Creates an animated displacement effect by calculating distance from origin, scaling it with a channel parameter, adding time for animation, and displacing points along normals using a sine wave. The exponentiation operator allows control over the wavelength scale, while time creates continuous wave motion.

### Animated wave with channel controls [[Ep2, 14:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=886s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d += @Time;
@P += @N * sin(d) * ch('wave_height');
```
Creates an animated wave displacement by calculating distance from origin, scaling it with a channel parameter, adding time for animation, and offsetting points along their normals using a sine wave multiplied by a wave height control. The combination of distance-based phase and time creates rippling wave motion across the geometry.

### Animated Wave Displacement [[Ep2, 14:52](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=892s)]
```vex
float d = length(@P);
d *= ch("v_scale");
d += @Frame;
@P = @P * sin(d) * ch("wave_height");
```
Creates an animated radial wave displacement by calculating distance from origin, scaling it with parameters, adding frame-based animation, and applying a sine function modulated by wave height. The v_scale parameter controls the frequency of waves while wave_height controls the displacement amplitude.

### Animated Wave Deformation [[Ep2, 15:24](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=924s)]
```vex
float d = length(@P);
d *= ch("y_scale");
d += @Time;
@P += @N*sin(d)*ch("wave_height");
```
Creates an animated wave deformation by calculating distance from origin, scaling it with a channel parameter, adding time for animation, and displacing points along their normals using a sine wave multiplied by a height parameter. The wave propagates outward from the origin over time, with adjustable scale and amplitude controls.

### Animated Wave Deformation with Channels [[Ep2, 16:00](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=960s)]
```vex
float d = length(@P);
d += @Time;
@P.y = @P.y * sin(d) * ch("wave_height");
```
Creates an animated wave deformation by calculating distance from origin, adding time offset, and modulating the Y position with a sine function scaled by a channel parameter. The channel parameters allow interactive control over wave height and scale, producing a dynamic ripple effect that propagates outward from the center.

### Wave Distortion with Distance [Needs Review] [[Ep2, 17:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1052s)]
```vex
float d = length(@P);
d -= ch("v_scale");
d *= 6*@Time;
@P.y = @P.y*sin(d) *ch("wave_height");
```
Creates an animated wave distortion effect by calculating distance from origin, offsetting and scaling it with time, then applying a sine wave to the Y position. The wave_height parameter controls amplitude while v_scale adjusts the wave frequency offset, creating a rippling effect that propagates across the geometry over time.

### Sine Wave Ripple Effect [[Ep2, 18:06](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1086s)]
```vex
float d = length(@P);
v@v = ch("_scale");
@P += @N * sin(d) * ch("wave_height");
```
Creates a ripple effect by calculating the distance from the origin to each point, then displacing points along their normals using a sine wave modulated by distance and controlled by channel parameters. The wave_height channel controls the amplitude of the ripple while the distance determines the phase, creating concentric wave patterns.

### Creating Sine Waves with Length [[Ep2, 18:38](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1118s)]
```vex
float d = length(@P);
d *= ch("scale");
@P += @N * sin(d) * ch("wave_height");
```
Demonstrates creating wave patterns by calculating distance from origin using length(), scaling it with a channel parameter, then displacing points along their normals using a sine function. Two channel parameters control the wavelength (scale) and amplitude (wave_height) of the resulting wave pattern.

## Ramp-Driven Deformation

### Ramp-Driven Position Deformation [[Ep2, 43:44](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2624s)]
```vex
float d = length(@P);
d *= ch('scale');
@P.y = chramp('my-ramp', d);
```
This code calculates the distance of each point from the origin, scales it by a channel parameter, and uses that scaled distance to sample a ramp parameter which drives the Y position of points. The technique allows for artistic control over deformation patterns using a visual ramp curve instead of mathematical functions.

### Scaling distance with ramp and channels [Needs Review] [[Ep2, 47:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2836s)]
```vex
float d = length(@P);
d *= ch('scale');
d = chramp('myramp', d);
@P.y = chramp('myramp', d);
```
This code calculates the distance of each point from the origin, scales it using a channel parameter, and then uses a ramp to remap those distance values to control the Y position of points. The technique allows for creating distance-based deformations across a grid that can be adjusted interactively via the scale parameter.

### Ramp-Driven Height Displacement [[Ep2, 48:18](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2898s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= ch('time');
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
This code uses the distance from origin to drive a ramp lookup, creating animated height displacement on geometry. The distance is scaled by a parameter, offset by time for animation, and the resulting ramp value is used to modify the Y position with an additional height multiplier for amplitude control.

### Animated Ramp Displacement with Height Control [[Ep2, 48:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2926s)]
```vex
float d = length(@P);
d *= ch("scale");
d -= @Time;
@P.y = chramp("myramp", d);
@P.y *= ch("Height");
```
Creates an animated vertical displacement effect by calculating distance from origin, scaling and offsetting it by time, then sampling a ramp to control the Y position. The final displacement is multiplied by a height parameter for overall amplitude control, creating a spreading wave-like deformation across the geometry.

## Wave Deformation

### Animated Ramp-Driven Displacement [[Ep2, 49:00](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2940s)]
```vex
float d = length(@P);
d *= ch('scale');
d += $T;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp('myramp', d);
@P.y *= ch('height');
```
Creates an animated wave displacement by calculating distance from origin, scaling it, adding time to create motion, then using sine and fit to normalize the value for color ramp lookup. The ramp value drives the vertical position of points, creating a rippling grid animation controlled by height multiplier.

### Animated ramp with time offset [[Ep2, 49:28](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2968s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d,-1,1,0,1);
@P.y = chramp('my_ramp',d);
@P.y *= ch('height');
```
Creates an animated wave pattern by calculating distance from origin, scaling it with a parameter, adding time to animate, applying sine function, and using the result to sample a ramp for vertical displacement. The fit() function normalizes the sine wave output from [-1,1] to [0,1] for proper ramp sampling.

### Animated radial wave with point offset [Needs Review] [[Ep2, 51:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3116s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = sin(d*ch('freq')/(@ptnum/100.0)*d);
@Cd *= ch('height');
```
Creates an animated radial wave pattern emanating from the origin by calculating distance from center, scaling and offsetting by time, then using sine function with point number offset and distance modulation to generate vertical displacement. The color is multiplied by a height parameter to visualize the wave intensity.

## Ramp-Driven Deformation

### Radial Ramp Displacement [Needs Review] [[Ep2, 52:42](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3162s)]
```vex
float d = length(@P);
d *= ch("scale");
d = qs(d);
d *= $PI;
@P.y = chramp("myamp", d);
@P.y *= ch("height");
```
Creates a radial displacement pattern by calculating distance from origin, scaling and wrapping it with qs() function, then using that as input to a ramp parameter to drive vertical position. The pattern repeats radially around the origin, creating a circular wave-like effect controlled by a ramp and height parameter.

## Wave Deformation

### Animated Sine Wave Displacement [[Ep2, 52:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3178s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = .1*sin(d);
@v.y = sin(length(@P));
```
Creates an animated sine wave displacement by calculating distance from origin, applying a channel-based scale, offsetting by time, and using the result to drive vertical position with sine. The velocity attribute is set based on the sine of distance, creating a ripple effect that propagates over time.

## Ramp-Driven Deformation

### Ramp-driven radial displacement [Needs Review] [[Ep2, 53:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3194s)]
```vex
float d = length(@P);
d *= ch('scale');
d %= 1;
@P.y = chramp('myramp', d);
@Cd = chramp('height', d);
```
Creates a radial displacement pattern by computing distance from origin, scaling and wrapping it with modulo to create repeating rings, then using a ramp to drive vertical displacement and color. The distance value is normalized to 0-1 range through the modulo operation, allowing the ramp to sample repeating concentric patterns.

## Wave Deformation

### Animated Radial Wave with Ramp [[Ep2, 54:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3296s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('myramp', d);
@N.y = ch('height');
```
Creates an animated radial wave effect by calculating distance from origin, scaling and animating it with time, then using a ramp to modulate the vertical position. The scale parameter controls wave frequency while the ramp lookup creates the wave shape, with the height parameter affecting the normal's y component.

### Animated Ramp Wave Effect [[Ep2, 55:38](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3338s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
Creates an animated wave effect by calculating distance from origin, scaling and animating it with time, then using that value to sample a ramp parameter which drives the Y position of points. The ramp allows artistic control over the wave shape while scale and height parameters control its frequency and amplitude.

## Ramp-Driven Deformation

### Animated Ramp Height Displacement [[Ep2, 56:24](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3384s)]
```vex
float d = length(@P);
d -= ch('scale');
d -= @Time;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
Creates an animated radial displacement effect by calculating distance from origin, offsetting it by scale and time parameters, then using that distance to sample a ramp channel which controls the Y position scaled by a height multiplier. The subtraction of @Time creates outward-moving waves over time.

## Wave Deformation

### Animated Ramp-Driven Wave Patterns [[Ep2, 56:56](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3416s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
@P.y = chramp('my-map', d);
@P.y *= ch('height');
```
Creates animated wave patterns by calculating distance from origin, scaling and offsetting by time, then using a ramp parameter to control vertical displacement. The ramp lookup value is animated by subtracting @Time from the scaled distance, creating waves that propagate over time. The final height is multiplied by a height parameter for amplitude control.

### Animated Waves with Ramp Control [[Ep2, 57:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3450s)]
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
Creates animated wave deformations by calculating distance from origin, animating it with time, applying sine wave oscillation, and then using a ramp parameter to shape the wave profile. The chramp lookup allows artistic control over the wave shape by mapping the oscillating value through a customizable ramp curve, which is then scaled by a height multiplier.

### Ramp and Distance Deformation [[Ep2, 58:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3494s)]
```vex
float d = length(@P);
d *= ch("scale");
d = abs(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("myram", d);
@P.y *= ch("height");
```
Creates a vertical deformation by calculating distance from origin, applying sine wave modulation, and using chramp() to lookup values from a ramp parameter. The distance is scaled and fitted to 0-1 range before being used as the ramp lookup value, which controls the Y position of points multiplied by a height parameter.

### Distance-based Height with ID Offset [Needs Review] [[Ep2, 59:00](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3540s)]
```vex
float d = length(@P);
d *= ch('scale');
d += @id;
d += sin(d);
d *= ch('height');
@P.y = d;
```
Calculates a distance value from the origin using point position length, scales it with a channel parameter, offsets by point ID, applies a sine wave modulation, and uses the result to drive the Y position of points. The final line was corrected from 'ch('height')' to 'd' as the intent is to assign the calculated distance value to the point's Y coordinate.

### Fit and Ramp for Wave Displacement [[Ep2, 59:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3566)]
```vex
float d = length(@P);
d *= ch("scale");
d -= sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```
This code creates a radial wave displacement by calculating distance from origin, applying sine wave modulation, and remapping the result through a ramp parameter for artistic control. The fit() function normalizes the sine wave's range from [-1,1] to [0,1] so it can properly drive the chramp() lookup, which then sets vertical position scaled by a height parameter.

### Ramp-driven displacement with fit [[Ep2, 59:44](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3584s)]
```vex
float d = length(@P);
d *= ch("scale");
d += 0;
d *= sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```
Creates a radial displacement pattern by calculating distance from origin, applying sine wave modulation, fitting the result to 0-1 range, and using it to sample a ramp parameter for vertical displacement. The fit function clamps the sine wave oscillation to a normalized range suitable for ramp lookup, while position values themselves can extend beyond typical bounds.

### Ramp-driven height displacement [[Ep2, 62:54](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3774s)]
```vex
float d = length(@P);
d *= ch("scale");
d *= @Time;
d = sin(d);

@P.y = chramp("my-ramp", d);
@P.y *= ch("height");
```
This creates animated vertical displacement using a color ramp for control. The distance from origin is calculated, scaled by time and parameters, then passed through sine to create oscillation, and finally the result is used to sample a ramp that drives the Y-position of points, scaled by a height multiplier.

### Ramp-Driven Height Displacement [Needs Review] [[Ep2, 68:12](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4092s)]
```vex
float d = length(@P);
d *= ch("scale");
d = sin(d);
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@P.y = chramp("my-ramp", d) * ch("height");
```
This code creates a radial wave pattern by calculating distance from origin, applying sine wave distortion, normalizing the result with fit(), and using a ramp parameter to drive vertical displacement. The double sine application creates more complex wave interference patterns, and the final height is controlled by a channel parameter for easy adjustment.

### Distance-Based Deformation with Ramps [[Ep2, 70:18](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4218s)]
```vex
float d = length(@P);
d *= ch('scale');
d *= sin(d);
d *= fit(d, -1, 1, 0, 1);
d = chramp('my-ramp', d);
@P.y *= ch('height');
```
This code calculates distance from origin using length(@P), applies sinusoidal waves, normalizes the result with fit(), and uses a color ramp to control vertical displacement. The technique chains multiple operations to create controllable distance-based deformations with UI parameters for scale and height.

### Animated Radial Wave Pattern [[Ep2, 71:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4262s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d %= 1;
@P.y = chramp('my-ramp', d);
@P.y *= ch('height');
```
Creates an animated radial wave pattern by calculating distance from origin, scaling and offsetting by time, using modulo to create repeating rings, then applying a ramp to control vertical displacement. The height is multiplied by a parameter for overall amplitude control, producing concentric animated waves emanating from the center.

### Animated Radial Sine Wave [[Ep2, 71:14](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4274s)]
```vex
float d = length(@P);
d *= ch('scale');
d -= @Time;
d = sin(d);
d = fit(d, -1, 0, 0, 1);
d = chramp('my_control_ramp', d);
@P.y += ch('height');
```
Creates an animated radial sine wave pattern by calculating distance from origin, scaling it, subtracting time for animation, applying sine function, and remapping the result through a ramp parameter. The final remapped value displaces points vertically and can be used to drive color or geometry deformation.

### Distance-based height displacement with ramps [[Ep2, 74:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4472s)]
```vex
float d = length(@P);
v@Cd = ch('color');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
d = chramp('height', d);
@P.y *= ch('height');
```
This example calculates the distance from the origin, applies a sine wave, normalizes it to 0-1 range, then uses a ramp parameter to control a vertical displacement multiplier. The code demonstrates core VEX patterns commonly used across production work, including distance fields, trigonometric functions, value remapping, and channel/ramp parameter integration.

## Ramp-Driven Deformation

### Ramp-Driven Height Displacement [[Ep2, 99:42](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5982s)]
```vex
float d = length(@P);
d *= ch('pre_scale');
d = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```
This code calculates the distance from the origin using length(@P), scales it with a pre-multiplier channel, remaps the value through a stepped ramp parameter, applies a post-scale multiplier, and assigns the result to the Y position to create height displacement. The technique demonstrates how to chain multiple transformations including ramp lookups to achieve controlled deformation based on radial distance.

## Wave Deformation

### Point Displacement with Channels [[Ep2, 9:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=598s)]
```vex
float d = length(@P);
d *= ch('v_scale');
d = @Time;
@P.y = sin(d);

@P += @N;

@P += @N * ch('push');
```
Demonstrates multiple techniques for displacing points including calculating distance from origin, using time-based sine wave deformation, and offsetting geometry along normals with channel-controlled strength. The code shows progressive iterations of displacement methods, with the final version using a 'push' parameter to control normal-based offset magnitude.

### Distance-Based Displacement [[Ep3, 10:42](https://www.youtube.com/watch?v=fOasE4T9BRY&t=642s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = d;
@P.y = sin(d);
```
Calculates the distance of each point from the origin using length(@P), scales it with a channel parameter, assigns the distance to color, and displaces points vertically using a sine wave based on the scaled distance. The code demonstrates why @P can be written in point context but not in primitive context, as point positions are point-level attributes.

### Distance to Surface Point [Needs Review] [[Ep3, 27:48](https://www.youtube.com/watch?v=fOasE4T9BRY&t=1668s)]
```vex
vector pos = point(1, @P);
float d = distance(@P, pos);
d *= chf("M1");
@Cd.r = sin(d);
```
Uses the point() function to find the closest point on a reference surface geometry (input 1) to the current point position, then calculates the distance between them. The distance is multiplied by a channel parameter and used with sine to create a color pattern in the red channel, producing proximity-based visualization.

### Sine Wave Color and Position [[Ep3, 7:26](https://www.youtube.com/watch?v=fOasE4T9BRY&t=446s)]
```vex
float d = length(@P);
d *= ch('scale');
@Cd = @P;
@P.y = sin(d);
```
Calculates distance from origin using length(@P), scales it with a channel parameter, and applies a sine wave to the Y position based on this distance. Each point stores its position as a color attribute, creating a visualization where point colors represent their spatial coordinates while the geometry deforms into a sine wave pattern.

### Applying Sine Wave to Position [[Ep3, 8:58](https://www.youtube.com/watch?v=fOasE4T9BRY&t=538s)]
```vex
float d = length(@P);
d *= ch('scale');
@P.y = sin(d);
```
This code calculates the distance from the origin for each point, scales it using a channel parameter, and applies a sine function to the Y position. This creates a wave pattern along the Y axis based on radial distance from the origin, demonstrating how the same sine calculation used for color can be applied to geometric deformation.

## Ramp-Driven Deformation

### Relative BBox Deformation with Ramps [[Ep4, 52:42](https://www.youtube.com/watch?v=66WGmbykQhI&t=3162s)]
```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float k = chramp('inflate', bbox.y);
@P += @N * k * ch('scale');
```
Uses relpointbbox to get normalized bounding box coordinates (0-1 range) for each point, then demonstrates progressive complexity: first visualizing the Y component as color, then scaling point positions along normals by the Y coordinate, and finally using a ramp parameter to control the deformation gradient. This creates height-based effects where the influence varies smoothly from bottom to top of the geometry's bounding box.

### Ramp-Driven Inflation Using Bounding Box [[Ep4, 53:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=3236s)]
```vex
vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```
Uses a ramp parameter to control point displacement along the normal based on vertical bounding box position. The bbox.y value (0-1 from bottom to top) drives a chramp lookup, allowing customizable inflation profiles instead of linear scaling. This creates more artistic control over geometry deformation compared to direct bbox multiplication.

### Ramp-driven geometry deformation [[Ep4, 55:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=3300s)]
```vex
vector bbox = relpointbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```
Uses a ramp parameter to control point displacement along the normal direction based on the point's relative Y position in the bounding box. The chramp function samples the ramp with the normalized bbox.y value (0-1), allowing for non-linear deformation profiles. This creates bulging or pinching effects on geometry by varying displacement strength across the vertical axis.

### Ramp-driven Geometry Inflation [[Ep4, 55:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=3316s)]
```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox;

vector bbox = relpointbbox(0, @P);
@Cd = @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```
Demonstrates using a ramp parameter to control geometry inflation based on normalized bounding box position. The chramp() function samples a ramp using bbox.y (0-1 vertical position) as input, allowing non-linear scaling control. The geometry is inflated along normals with the ramp-modulated scale value, creating effects like variable bulging across the vertical axis.

### Normalized Bounding Box Deformation [[Ep4, 56:16](https://www.youtube.com/watch?v=66WGmbykQhI&t=3376s)]
```vex
vector bbox = relpointbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');

vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```
Uses relpointbbox() to get normalized bounding box coordinates (0-1 range) for each point's position, then applies deformation along the normal based on the Y-axis bbox value. A ramp parameter provides artistic control over the inflation profile, while a scale channel controls overall displacement intensity, creating effects like bulges or localized geometry inflation.

### Ramp-Driven Inflation Effect [[Ep4, 56:54](https://www.youtube.com/watch?v=66WGmbykQhI&t=3414s)]
```vex
vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```
Uses relpointbbox() to get normalized bounding box coordinates (0-1) and drives displacement along normals with a ramp parameter. The chramp() function samples the 'inflate' ramp using the Y-axis bbox coordinate, allowing for vertical gradients and precise control over the inflation effect at different heights.

### Relative Bounding Box Scaling [[Ep4, 57:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=3476s)]
```vex
vector bbox = relpointbbox(0, @P);
@Cd = bbox.y;

vector bbox = relpointbbox(0, @P);
@P += @N * bbox.y * ch('scale');

vector bbox = relpointbbox(0, @P);
float t = chramp('inflate', bbox.y);
@P += @N * t * ch('scale');
```
Uses relpointbbox to get normalized (0-1) bounding box coordinates for each point, making position-based effects scale-independent. The pattern progresses from visualizing the normalized Y coordinate as color, to using it for uniform displacement, to using it with a ramp for controlled inflation effects. This approach allows geometry of any size to be processed consistently since coordinates are relative to the bounding box rather than absolute world space.

### Relative Bounding Box Scaling [[Ep4, 58:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=3482s)]
```vex
vector bbox = relpointbbox(0,@P);
float t = chramp('inflate',bbox.y);
@P += @N * t * ch('scale');
```
Uses relpointbbox() to get normalized bounding box coordinates (0-1 range) and drives position displacement via a ramp parameter, allowing the same effect to work consistently across different geometry scales. The Y component of the relative bounding box is fed into a ramp to control inflation amount, making it easy to create effects like mid-body bulges that adapt to any character's proportions.

### Relative Bounding Box Inflation [[Ep4, 58:24](https://www.youtube.com/watch?v=66WGmbykQhI&t=3504s)]
```vex
vector bbox = relbbox(0, @P);
float i = chramp('inflate', bbox.y);
@P += @N * i * ch('scale');
```
Uses relbbox() to get normalized position within bounding box (0-1 space), then samples a ramp parameter based on the Y component to drive a displacement along normals. This makes effects scale-independent and transferable between different geometry, maintaining the same relative deformation regardless of the input geometry's absolute size.

## Wave Deformation

### Animated Ripple Waves from Points [[Ep5, 63:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3810s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, "P", pt);
d = distance(@P, pos);
w = d * d / ch('freq');
w = w - @Time * ch('speed');
w = sin(w);
w = w * ch('amp');
w = fit(d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Creates animated ripple waves emanating from nearby points by calculating distance-based sine waves that progress over time. The frequency is controlled by distance squared, animated by subtracting time multiplied by speed, then modulated by amplitude and attenuated using fit to fade out at the radius boundary.

### Animated sine wave displacement [[Ep5, 63:34](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3814s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d * ch('freq') - @Time * ch('speed');
w = sin(w);
w = fit(w, -1, 1, ch('radius'), 1, 0);

@P.y += w;
```
Creates animated sine wave displacement by calculating distance to nearest point, modulating it with a frequency parameter and time-based speed control, then applying the result as vertical displacement. The subtraction of @Time * speed creates the wave progression animation, while fit() remaps the sine output to control amplitude based on distance from the nearest point.

### Animated sine wave ripples [Needs Review] [[Ep5, 66:20](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3980s)]
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
w = @Frame * ch('speed');
w = sin(w);
w *= ch('amp');
w = fit(d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Creates animated sine wave ripples by finding nearby points and using their distance to modulate a time-based sine wave that displaces points vertically. The wave amplitude is attenuated based on distance using fit(), and the animation is driven by @Frame. Multiple parameters control radius, frequency, speed, and amplitude of the ripples.

### Animated Sine Wave Ripples [[Ep5, 66:22](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3982s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, "P", pt);
d = distance(@P, pos);
w = d * ch('freq');
w = sin(w);
w = fit(w, -1, 1, ch('radius'), 1, 0);
@P.y += w;
```
Creates animated sine wave ripples emanating from nearby points by finding the nearest point, calculating distance-based sine waves controlled by frequency and radius parameters, and displacing points vertically. The frequency parameter controls wave density while radius affects both search distance and wave amplitude falloff.

### Wave Frequency and Radius Control [Needs Review] [[Ep5, 66:32](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3992s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('max_pt_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d * ch('freq');
d = sin(w);
w *= d;
@P.y += w;
```
Adjusts wave propagation by controlling frequency and radius parameters, demonstrating how higher frequency values can cause visual artifacts while lower frequencies produce smoother wave patterns. The code modifies the Y position based on sine wave calculations influenced by distance and frequency, though overlapping waves don't properly accumulate in this implementation.

### Fit and Sine Wave Deformation [[Ep5, 67:22](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4042s)]
```vex
v = fit(0, ch("radius"), 1, 0);
@P.y = sin(v) * 0.2;
```
Uses fit() to remap a value from 0 to a channel reference into a 0-1 range, then applies a sine wave to the Y position with a small amplitude. Higher geometry resolution is needed to avoid artifacts when deforming with high-frequency waves, as insufficient point density causes ugly angular deformation instead of smooth curves.

### Blending ripples with falloff [[Ep5, 69:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4170s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

pt = pts[0];
pos = point(1, 'P', pt);
d = distance(@P, pos);
w = d / ch('from');
w = @Time * ch('speed');
w = sin(w);
w *= fit(d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Extends the ripple effect to blend smoothly across multiple influence points by calculating a falloff weight based on distance. The fit() function creates a 0-1 falloff from the center to the radius edge, which is multiplied by the sinusoidal wave to create soft transitions between overlapping ripples. Using += instead of = allows multiple ripple influences to accumulate additively.

### Blending Multiple Ripple Effects [Needs Review] [[Ep5, 70:06](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4206s)]
```vex
int pts[];
int pt;
vector pos;
float d, w;

pts = nearpoints(1, @P, ch('radius'), chi('number_of_points'));

for(int i = 0; i < len(pts); i++) {
    pt = pts[i];
    pos = point(0, 'P', pt);
    d = distance(@P, pos);
    w = d * ch('freq');
    w += @Time * ch('speed');
    w = sin(w);
    w *= ch('amp');
    w *= fit(d, 0, ch('radius'), 1, 0);
    @P.y += w;
}

for(int i = 0; i < len(pts); i++) {
    pt = pts[i];
    pos = point(0, 'P', pt);
    d = distance(@P, pos);
    w = d * ch('freq');
    w += @Time * ch('speed');
    w = sin(w);
    w *= ch('amp');
    w *= fit(d, 0, ch('radius'), 1, 0);
    @P.y += w;
}
```
This code duplicates the ripple effect loop to blend multiple ripple influences together, using += on @P.y to accumulate the effects rather than overwriting them. The key technique is using @P.y += w instead of @P.y = w so that multiple ripple waves from different source points can be added together, allowing ripples to pass through and blend across voronoi cell boundaries.

### Multi-Point Ripple Accumulation [[Ep5, 70:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4208s)]
```vex
v@pos = point(1, 'P', @ptnum);
f@d = distance(@P, v@pos);
v@w = f@d * ch('freq');
v@w -= @Time * ch('speed');
v@w = sin(v@w);
v@w *= fit(f@d, 0, ch('radius'), 1, 0);
@P.y = v@w;

// Multiple ripples version
int pt = i[]@ps[0];
v@pos = point(1, 'P', pt);
f@d = distance(@P, v@pos);
float w = f@d * ch('freq');
w -= @Time * ch('speed');
w = sin(w);
w *= fit(f@d, 0, ch('radius'), 1, 0);
@P.y += w;
```
Demonstrates the critical difference between assignment (@P.y =) and accumulation (@P.y +=) when applying multiple ripple effects. Using += allows ripples from multiple source points to blend together additively, creating overlapping wave patterns that extend beyond individual Voronoi cell boundaries.

### Multi-Point Distance Blending [Needs Review] [[Ep5, 70:52](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=4252s)]
```vex
v@P = set(i@ptnum, 0, 0);
pos = point(1, "P", i@ptnum);
d = distance(@P, pos);
freq = ch("freq");
w = d * cos(freq);
w = sin(w);
amp = ch("amp") * ch("speed");
w *= amp;
w *= fit(d, 0, ch("radius"), 1, 0);

pt = primpoint(1, 0, 0);
pos = point(1, "P", pt);
d = distance(@P, pos);
w = d * cos(freq);
w = sin(w);
amp = ch("amp") * ch("speed");
w *= amp;
w *= fit(d, 0, ch("radius"), 1, 0);
@P.y += w;
```
Demonstrates blending multiple distance-based wave influences by computing wave effects from multiple source points and accumulating them. The code calculates distance-based wave deformation from different primitive points, using falloff and frequency controls to blend the effects smoothly across the geometry.

### Scale Animation with Length and Fit [Needs Review] [[Ep6, 26:24](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1584s)]
```vex
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
Creates animated scaling effect on geometry by computing distance from origin using length(@P), adding time-based offset, applying sine wave, and fitting the result to min/max range. The scale vector is constructed with min on X and Z axes while the animated value d controls Y axis, creating vertical scaling animation. This demonstrates how Houdini uses Z-axis as the up direction for geometry.

### Vector Component Swapping for Scale [[Ep6, 26:26](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1586s)]
```vex
float min, max, d, f;
min = ch('min');
max = ch('max');
f = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += f;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
```
Demonstrates swapping vector components in the scale attribute to control which axis receives the animated scaling effect. The code uses distance from origin with sine wave animation, then constructs a scale vector with min on X, max on Y, and the animated value d on Z, causing boxes to scale along the Z-axis which is Houdini's default up axis.

### Animated Scale with Radial Wave [[Ep6, 28:52](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1732s)]
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
@Cd.y = d;
```
Creates an animated radial wave effect by calculating distance from origin, modulating it with time-based sine wave, and applying the result to point scale and color. The distance calculation combined with sine and fit functions produces concentric rings that expand outward over time, with scale varying primarily in one axis and green channel reflecting the wave amplitude.

## Ramp-Driven Deformation

### Packed Geometry with Scale and Color [Needs Review] [[Ep6, 29:56](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1796s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = fit01(v@pred);
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(d, min, max, 0, 1);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('cd', d));
```
Creates packed geometry instances with non-uniform scaling based on distance from origin and a predecessor attribute. Uses distance and fit operations to control per-axis scale values via the @scale attribute, adjusts point positions vertically, and applies color using a channel ramp. This approach efficiently handles hundreds of packed geometries instead of millions of points.

## Wave Deformation

### Animated Scale and Color with Packing [[Ep6, 30:04](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1804s)]
```vex
float min, max, d, t;
min = 0;
max = ch("max");
t = fit(v@P.x, ch("speed"));
d = length(@P);
d *= ch("frequency");
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@P.y += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp("color", d));
```
Creates animated wave pattern by computing distance from origin, modulating it with sine wave based on frequency and speed parameters, then applying results to non-uniform scale attribute and vertical position offset. The computed distance value is remapped and used to drive color via a ramp parameter, demonstrating integration with packed geometry instancing workflow.

### Scaling and displacement with color ramp [Needs Review] [[Ep6, 30:16](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1816s)]
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
@P.y += d;
d = fit(d, min, max, 0, 1);
@Cd = chramp("color", d);
```
Creates animated scaling and vertical displacement based on distance from origin using sine waves. The displacement value is remapped to drive both the scale attribute (with min/max for x/y and calculated d for z) and a color ramp for point coloring. This builds on the previous snippet by adding position displacement and color ramping.

### Animated scaling with ground plane offset [[Ep6, 31:28](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=1888s)]
```vex
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Frame * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@Py += d/2;

float min, max, d, t;
min = ch('min');
max = ch('max');
t = @primnum * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@Py += d/2;
d = fit(d, min, max, 0, 1);
@Cd = vector(chramp('color', d));
```
Demonstrates animating copy-to-points geometry with sine wave-driven scaling while offsetting the Y position by half the calculated distance to anchor objects to the ground plane. The second variant uses @primnum instead of @Frame for per-primitive variation and adds color ramping based on the normalized distance value.

### Animating Up Vector with Time Offsets [[Ep6, 47:56](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2876s)]
```vex
v@up = set(sin(@Time), 0, cos(@Time));

v@up = set(sin(@Frame), 0, cos(@Frame));

float t = @Time - @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));

float d = length(@P);
float t = @Time + d * ch("offset");
v@up = set(sin(t), 0, cos(t));
```
Demonstrates animating the up vector attribute to create spinning motion by using sine and cosine functions with time values. Progresses from global animation using @Time or @Frame to per-point offsets using @ptnum, and finally to distance-based offsets using point position and a channel parameter, creating wave-like spinning patterns across copied geometry.

### Animated Y displacement with up vector [Needs Review] [[Ep6, 52:16](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3136s)]
```vex
float d = length(@P);
float t = @Time + d*ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Calculates a time-varying Y displacement based on distance from origin, where each point oscillates at different phases determined by its distance. The up vector is set to rotate in the XZ plane using sine and cosine, while the Y position is offset by a sine wave scaled to ±0.5 units that oscillates twice as fast as the base time.

### Animated Wave Displacement with Up Vector [Needs Review] [[Ep6, 52:26](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3146s)]
```vex
float d = length(@P);
float blob = @Time + d * chf('offset');
v@up = set(sin(blob), 0, cos(blob));
@P.y += sin(blob * 2) * 0.5;
```
Creates an animated wave displacement by combining time and distance from origin. The sine function applied to the blob variable drives both a custom up vector and vertical position displacement, with the displacement multiplied by 2 to speed up the animation and scaled by 0.5 to limit amplitude to ±0.5 range.

### Instance Orientation with Up Vector [[Ep6, 53:32](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3212s)]
```vex
float d = length(@P);
float t = @Time * d - d * chf('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Demonstrates animating instance orientation by setting the @up vector using time-based trigonometric functions, creating rotating instances. The position is also offset vertically with a wave motion that's double the frequency of the rotation, while the distance from origin modulates the animation timing.

### Animating up vector for instances [[Ep6, 53:36](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3216s)]
```vex
float d = length(@P);
float t = @Time * d * chf('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates animated dancing instances by computing a time-based offset from point distance, then using sine and cosine to rotate the up vector in a circular pattern while simultaneously offsetting point Y positions. The up vector combined with the normal vector defines the orientation of instanced geometry.

### Animating up vector for instance orientation [[Ep6, 53:38](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3218s)]
```vex
float d = length(@P);
float t = @Time*ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Demonstrates animating an up vector for controlling instance orientations using trigonometric functions. The up vector rotates in the XZ plane over time while the Y position oscillates, allowing instances to maintain proper orientation as they move. This approach uses both the up vector and normal vector to define where instances are positioned and how they're rotated.

### Animated Circle with Up Vector [[Ep6, 56:22](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3382s)]
```vex
float d = length(@P);
float t = @Time * d * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;
```
Creates an animated circular pattern by calculating distance-based time offset and using trigonometric functions to set both the up vector rotation and vertical displacement. The up vector rotates around the Y-axis based on the animated time value, while the Y position oscillates at twice the frequency.

### Time-Based Wave with Offset [[Ep6, 56:42](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=3402s)]
```vex
float d = length(@P);
float t = @Time * (1-@offset);
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * d;
```
Creates a time-animated wave effect that varies by distance from origin, using an offset attribute to control timing. The code calculates distance-based amplitude modulation, sets a rotating up vector, and applies a vertical sine wave displacement that oscillates at twice the offset-modified time rate.

### Circular Path with Sine and Cosine [[Ep8, 35:06](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=2106s)]
```vex
vector uv;

uv.x = sin(@Time*2);
uv.y = cos(@Time*2);

uv = fit(uv, -1, 1, -0.2, 0.2);

@P = primv(1, 'P', 0, uv);
@N = primv(1, 'N', 0, uv);
```
Creates circular motion by using sine and cosine functions on the same time value for UV coordinates, then uses fit() to scale the range from [-1,1] to [-0.2,0.2]. The scaled UV coordinates are used with primv() to sample position and normal attributes from the second input, creating a point that moves in a circular path across a primitive's parametric space.

## See Also
- **VEX Common Patterns** (`vex_patterns.md`) -- deformation pattern recipes
