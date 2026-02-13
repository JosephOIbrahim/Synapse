# Joy of VEX: Noise & Randomness

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
@Cd = curlnoise(@P*chv('fancyscale')*@Time);  // Animating Noise with Time and Parameters
v@Cd = curlnoise(@P*chv('fancyscale'))*0.5+0.5;  // Curl Noise Function Arguments
@Cd = curlnoise(@P * cv('fancyscale') + @Time);  // Curl Noise Color with Channel
```

## Noise Patterns

### Noise with Parameters and Animation [[Ep3, 60:14](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3614s)]
```vex
@Cd = noise(chv('offset') + @P * chv('fancyscale') * @Time);
```
Demonstrates progressive enhancement of noise by adding channel parameters for scale control and offset, then incorporating time-based animation. The final expression combines vector offset, vector scale multiplication, and time to create animated noise patterns that can be controlled via the UI.

### Noise Function Basics [[Ep3, 61:02](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3662s)]
```vex
noise(@P*chf('offset')+@v*chv('fancyscale')*@Time);
```
Introduction to working with noise in VEX, demonstrating how to combine position, velocity, and time with channel parameters to create animated noise patterns. The noise function takes spatial coordinates modified by scale and offset parameters to generate procedural variation.

### Noise with Position and Time [[Ep3, 61:06](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3666s)]
```vex
@Cd = noise(chv('offset')+@P*chv('fancyscale')*@Time);
```
Demonstrates progressive complexity in using noise functions with position data, from basic noise(@P) to more sophisticated combinations involving channel parameters for scale/offset control and time-based animation. The final version combines offset, scaled position, and time multiplication to create animated noise patterns on point colors.

### Noise Function with Parameters [[Ep3, 61:18](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3678s)]
```vex
@Cd = noise(chv('offset')+@P*chv('fancyscale'));
```
Demonstrates using the noise function to generate color values by combining position with channel-referenced parameters for offset and scale control. The chv() function reads vector parameters to enable real-time adjustment of noise characteristics through the interface.

### Noise with Channel References and Time [[Ep3, 62:58](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3778s)]
```vex
@Cd = noise(chv('offset')+@P*chv('fancyscale')+@Time);
```
Applies animated noise to point color by combining position scaled by a vector parameter, an offset parameter, and the current time attribute. The chv() function retrieves vector channel parameters, allowing for three-dimensional control over noise frequency and offset, while @Time drives the animation.

### Animating Noise with Offset and Time [[Ep3, 64:10](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3850s)]
```vex
@Cd = noise(chv('offset') + @P * chv('fancyscale') + @Time);
```
Demonstrates various methods for animating noise patterns by combining position (@P), scale parameters, offset controls, and time (@Time). The final version shows how to add an offset parameter, multiply position by a fancy scale vector, and add time to create animated noise-based color patterns.

### Animating Noise with Offset Parameter [[Ep3, 64:18](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3858s)]
```vex
@Cd = noise(chv('offset')*@P*chv('fancyscale')*@Frame);
```
Demonstrates combining multiple parameters to control noise-based color attributes, including vector offset, fancy scale, and frame-based animation. The chv() channel references allow interactive control of the noise pattern position and scale, while @Frame creates time-based animation.

## Curl Noise

### Animated Noise with Channels [[Ep3, 66:12](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3972s)]
```vex
@Cd = curlnoise(chv('offset')+@P*chv('fancyscale')*@Time);
```
Demonstrates progressive building of animated noise expressions by combining channel parameters with position, time, and noise functions. The final version uses curlnoise with offset, scaled position, and time multiplication to create evolving turbulent color patterns.

### Animating Noise with Time and Parameters [[Ep3, 66:14](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3974s)]
```vex
@Cd = curlnoise(@P*chv('fancyscale')*@Time);
```
Demonstrates progressive techniques for animating noise patterns using parameter channels and the @Time attribute. The final example uses curlnoise with a vector scale parameter multiplied by @Time to create evolving, divergence-free noise patterns that animate automatically over the timeline.

## Noise Patterns

### Animating Noise with Time [[Ep3, 67:02](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4022s)]
```vex
@Cd = noise(@P + chv('offset')) * @P * chv('fancyscale') + @time;
```
Creates animated noise-based color by adding a channel vector offset to position for noise sampling, multiplying the result by position and a scale vector, then adding time to animate the pattern. The combination of position multiplication and time addition produces stretched, flowing noise patterns that evolve over the timeline.

## Curl Noise

### Animated Curl Noise Color [[Ep3, 68:08](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4088s)]
```vex
@Cd = curlnoise(@P * chv('fancyscale') + @Time);
```
Uses curl noise to generate animated color values based on point positions and time. The fancyscale channel parameter controls spatial frequency, while @Time drives the animation. This creates smoothly evolving color patterns across geometry.

### Curlnoise Color Animation [[Ep3, 68:10](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4090s)]
```vex
@Cd = 0;
@Cd.x = curlnoise(@P * chv('fancyscale')).g * @Time;
```
Uses curlnoise to animate point color by extracting the green channel (g component) of the curl noise result and multiplying it by time, then assigning it to only the red color channel. This creates time-based color variations driven by the divergence-free curl noise field.

### Curl Noise Function Arguments [[Ep3, 68:50](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4130s)]
```vex
v@Cd = curlnoise(@P*chv('fancyscale'))*0.5+0.5;
```
This demonstrates how curl noise evaluates its input argument as a single expression before processing it. The entire calculation @P*chv('fancyscale') is evaluated first, then passed to curlnoise() as one input, with the result remapped to 0-1 range and assigned to color.

### Curl Noise Color Animation [[Ep3, 69:18](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4158s)]
```vex
v@Cd = curlnoise(@P * chv('fancyscale') * @Time);
@Cd[1]
```
Uses curlnoise to generate animated vector colors based on point position, scaled by a channel parameter and animated with @Time. Accesses the green channel component of the resulting color vector for further operations or visualization.

### Curl Noise Color with Channel [[Ep3, 69:30](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4170s)]
```vex
@Cd = curlnoise(@P * cv('fancyscale') + @Time);
```
Uses curl noise to generate a color based on position scaled by a custom channel parameter and animated with time. The curlnoise() function returns a 3D vector field that can be directly assigned to the color attribute, creating organic flowing color patterns.

### Animating Curlnoise with Time [[Ep3, 71:10](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4270s)]
```vex
@Cd = curlnoise(@P * chv("fancyscale") * @Time);
```
Uses curlnoise to generate animated color values by multiplying position with a channel parameter and the @Time attribute. This creates divergence-free noise that evolves over time, useful for creating flowing, swirling color patterns on geometry.

### Curlnoise Single Component Assignment [[Ep3, 72:04](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4324s)]
```vex
@Cd = 0;
@Cd.x = curlnoise(@P * chv('fancyscale') + @Time);
```
Demonstrates extracting a single component from curlnoise by first zeroing the color attribute, then assigning only the x component of the divergence-free vector field to create a grayscale noise pattern. This technique is useful when you want scalar noise values from a vector-based noise function.

### Curlnoise Color Components [[Ep3, 72:12](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4332s)]
```vex
v@Cd = vector(0);
v@Cd.x = curlnoise(@P * chv('fancyscale') + @Time).x;
```
This code demonstrates extracting the x component from curlnoise to drive color values. First the color attribute is zeroed, then a single component (x, which could also be accessed as r) of the curlnoise vector is assigned to the x channel of the color attribute, creating a grayscale animated effect based on curl noise.

### Noise Functions for Color Animation [[Ep3, 74:00](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4440s)]
```vex
@Cd = curlnoise(@P * chv('fancyscale') * @Time);
```
Demonstrates various noise-based approaches to animating color attributes, starting with simple noise and progressing to curlnoise with time-based animation. The final version uses curlnoise with controllable scale parameters and time multiplication to create animated color patterns based on point positions.

### Curl Noise Color Animation [[Ep3, 74:20](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4460s)]
```vex
@Cd = 0;
@Cd.x = curlnoise(@P * chv("fancyscale")) * @Time;
```
Creates animated color by using curl noise to drive the red color channel over time. The code initializes color to black, then sets only the red component using curl noise scaled by position and time, with the scale controlled by a channel parameter.

### Curlnoise with Time Animation [[Ep3, 74:22](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4462s)]
```vex
@Cd = @P;
@Cd.r = curlnoise(@P * chv('fancyscale') + @Time);
```
Assigns color to points by using curlnoise driven by animated position. The red channel is modulated by curlnoise that changes over time, creating animated color variation based on both spatial position and temporal evolution.

### Animated Curl Noise Color [[Ep3, 80:32](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4832s)]
```vex
@Cd = @P;
@Cd.x = curlnoise(@P * chv('fancyscale') + @Time);
```
Sets color based on position, then animates the red channel using curl noise driven by scaled position and time. The curl noise function generates a 3D vector field but only the x component is used for the red color channel.

### For Loop with Curl Noise [Needs Review] [[Ep5, 125:54](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7554s)]
```vex
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for(int i = 0; i < 6; i++) {
    offset = curlnoise(pos - @Time + i);
```
Sets up a for loop to iterate 6 times, calculating a curl noise offset for each iteration. The curl noise function is evaluated at the current position offset by negative time plus the iteration index, creating a time-varying noise pattern that differs for each loop iteration.

## Noise Patterns

### Random Primitive Removal with Seed Control [[Ep5, 144:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8670s)]
```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removepoint(0, @primnum, 1);
}

if(rand(@ptnum) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

if(rand(@ptnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}
```
Demonstrates using rand() with seed values to randomly remove primitives or points based on a cutoff threshold. The seed parameter allows for repeatable randomness, while the cutoff slider controls what percentage of geometry is removed, useful for creating natural-looking variations in geometry.

### Random Primitive Removal with Seed Control [[Ep5, 144:38](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8678s)]
```vex
if(rand(@primuv, ch('seed')) < ch('cutoff')){
    removepoint(0, @primuv, 1);
}
```
Uses a seeded random function to probabilistically remove points based on primitive UV coordinates and a cutoff threshold. The seed parameter allows control over the randomness pattern, while the cutoff slider determines the probability of point removal. This technique is useful for creating natural-looking variations in geometry by adding controlled randomness.

### Random Point Deletion with Seed [[Ep5, 159:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9582s)]
```vex
v@up = set(0, 1, 0);
if(rand(@primnum, ch('seed')) < ch('cutoff')) {
    removepoint(0, @primnum, 1);
}
```
Demonstrates random point deletion using rand() with a seed parameter for reproducibility and a cutoff threshold. The code sets an up vector and conditionally removes points based on whether a seeded random value falls below a user-controlled cutoff. This technique is mentioned as an alternative to using noise() for more structured deletion patterns.

### Noise vs Rand for Deletion [Needs Review] [[Ep5, 159:48](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9588s)]
```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

int pt = addpoint(0, (0,3,0));
addprim(0, 'polyline', @primnum, pt);

int pt = addpoint(0, @P + @N);
addprim(0, 'polyline', @ptnum, pt);
```
Demonstrates the difference between rand() and noise() for procedural deletion of primitives. While rand() provides pure white noise with a seed parameter, noise() offers more structured patterns that can be scaled, offset, and animated over time, making it useful for effects like noise flowing across a grid to control deletion patterns.

### Noise vs Rand for Deletion [[Ep5, 159:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9590s)]
```vex
if(rand(@primnum, ch('seed')) < ch('cutoff')){
    removeprim(0, @primnum, 1);
}

int pt = addpoint(0, {0,1,0});

if (@ptnum==0) {
    addpoint(0, {0,1,0});
}
```
Comparison of rand() versus noise() for structured deletion patterns. While rand() produces pure white noise, noise() offers more structure and can be scaled, offset, and animated over time, making it useful for flowing deletion patterns across geometry.

### Time-based wave animation with randomness [Needs Review] [[Ep5, 84:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5048s)]
```vex
vector pos;
int pts[];
int pt;
float d, s, f, t, e, a;

pts = nearpoints(1, @P, ch('radius'));

foreach(int pt; pts) {
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    s = fit(d, 0, ch('radius'), 1, 0);
    s = chramp('s', s);
    t = @Time * ch('speed');
    t += rand(pt);
    a = d * ch('amp');
    f = d * ch('freq');
    e += sin(t * f) * a;
}
```
Creates animated waves by accumulating sine-based displacement values from nearby points. Uses time multiplied by a speed channel, adds per-point randomness via rand(), and modulates wave amplitude and frequency based on distance from neighboring points.

### Time-based wave animation setup [Needs Review] [[Ep5, 84:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5050s)]
```vex
vector pos;
int pts[];
int pt;
float d, a, f, t;

pts = nearpoints(1, @P, 40);

foreach(int pt; pts){
    pos = point(1, "P", pt);
    d = distance(@P, pos);
    a = fit(d, 0, ch("radius"), 1, 0);
    d = clamp(d, a, 1);
    t = @Time * ch("speed");
    t += rand(pt);
    a = d * ch("amp");
    f = d * ch("freq");
```
Sets up time-based animation variables for wave effects by multiplying @Time with a speed parameter, adding per-point randomness using rand(pt) to offset timing, and computing amplitude and frequency based on distance. This creates animated waves with per-point variation and controllable speed.

## Curl Noise

### Quaternion wobble with curl noise [Needs Review] [[Ep7, 107:58](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6478s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@0), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P + @Time));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
```
Declares a wobble quaternion variable and initializes it using curl noise applied to a Z-axis vector. The curl noise input is driven by point position plus time, creating an animated vector field for rotation around the Z axis that will be multiplied into the final orientation.

### Quaternion Wobble with Curl Noise [Needs Review] [[Ep7, 108:26](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6506s)]
```vex
vector N, up;
vector4 extrarot, headshake, wobble;

N = normalize(@P);
up = {0,1,0};
@orient = quaternion(maketransform(N, up));
extrarot = quaternion(radians(ch("angle")), {1,0,0});
headshake = quaternion(radians(20) * sin(@Time*3), {0,1,0});
wobble = quaternion({0,0,1} * curlnoise(@P+@Time,2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```
Adds a third quaternion rotation layer using curl noise to create random wobbling motion. The wobble quaternion is constructed from curl noise sampled at the point's position plus time, multiplied by the Z-axis vector, creating position-based random rotations that vary over time. Each point gets its own unique wobble pattern since the noise lookup is based on @P.

### Quaternion Wobble with Curl Noise [[Ep7, 108:32](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6512s)]
```vex
vector h, up;
vector4 extrarot, headshake, wobble;

h = normalize(@P);
up = {0, 1, 0};
@orient = quaternion(maketransform(h, up));
extrarot = quaternion(radians(90), {1, 0, 0});
headshake = quaternion(radians(20) * sin(@Time * 3), {0, 1, 0});
wobble = quaternion({0, 0, 1} * curlnoise(@P + @Time * 0.2));

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```
Adds a wobble rotation to oriented geometry by creating a quaternion from curl noise based on point position plus time, then multiplying it with the existing orientation quaternions. The curl noise creates unique, natural-looking random wobbles for each point because it's position-based, and animates over time with the @Time offset.

## Noise Patterns

### Noise-based quaternion rotation animation [Needs Review] [[Ep7, 52:46](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3166s)]
```vex
vector axis1;
axis1 = chv("axis");
axis1 = normalize(axis1);
float angle = trunc(noise(@P + @Time) * 4) * $PI/2;

@orient = quaternion(angle, axis1);
```
Replaces random rotation with noise-based rotation that evolves over time, using position and time as noise input. The noise function creates more structured, coherent patterns compared to random values, and truncating the result to 4 discrete steps creates stepped rotations at 90-degree intervals that animate smoothly across space and time.

### Noise-Based Orientation with Quaternions [[Ep7, 52:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3170s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= trunc(noise(@P*@Frame)*4)*$PI/2;

@orient = quaternion(axis);
```
Replaces rand() with noise(@P*@Frame) to create spatially coherent, time-animated rotation axes for quaternion orientations. The noise function produces more structured, less random-looking results than pure random, with values that change smoothly over space and time when multiplied by @Frame.

### Quaternion Rotation from Noise [Needs Review] [[Ep7, 53:10](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3190s)]
```vex
vector axis1;
axis1 = chv('axis');
axis1 = normalize(axis1);
axis1 = trunc(noise(@P * @Time) * 4) * $PI / 2;

@orient = quaternion(axis1);
```
Creates randomized rotations using noise truncated to discrete angles (multiples of PI/2), then converts the result to a quaternion orientation. The truncation quantizes the noise output to create stepped rotations rather than smooth variation, which explains why certain rotation values appear less frequently.

### Quantized Noise for Orientation [Needs Review] [[Ep7, 53:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3194s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P + @P.y);
axis *= trunc(@a*4)*(PI/2);

@orient = quaternion(axis);
```
Uses noise based on point position to create quantized rotation angles by truncating the noise value multiplied by 4, then scaling by PI/2 to produce 90-degree increments. The axis vector is scaled by this quantized rotation value before being converted to a quaternion orientation attribute, resulting in stepped rather than continuous rotations.

### Remapping Noise with Fit and Ramp [[Ep7, 54:10](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3250s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+@Time);
axis *= trunc(@a*4)*PI/2;

@orient = quaternion(axis);

// With fit to expand noise range
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+@Time);
@a = fit(@a, 0.4, 0.6, 0, 1);
axis *= trunc(@a*4)*PI/2;

@orient = quaternion(axis);

// With chramp for artistic control
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P+@Time);
@a = chramp('noise_remap', @a);
```
Demonstrates three approaches to using noise for quaternion rotation: first storing raw noise in an @a attribute, then using fit() to remap the noise range from 0.4-0.6 to 0-1 for better distribution, and finally using chramp() to allow artistic control over noise remapping via a ramp parameter. The @a attribute is created for easier inspection in the geometry spreadsheet.

### Remapping noise with fit function [[Ep7, 55:44](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3344s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*@Time);
@a = fit(@a, 0.4, 0.6, 0, 1);
axis *= trunc(@a*4)*@t/2;

@orient = quaternion(axis);
```
Uses the fit() function to remap noise values by taking the range between 0.4 and 0.6 from the attribute @a and stretching it to fill the full 0 to 1 range, creating more variance and contrast in the noise distribution. This selective remapping creates more dramatic random rotations by amplifying values in the middle range of the noise.

### Quaternion Rotation from Noise [[Ep7, 56:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3380s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@P*f@lmn);
axis *= trunc(@a*4)*$PI/2;

@orient = quaternion(axis);
```
Creates quaternion-based orientation by computing a noise value at each point position, then truncating and scaling it to create discrete rotation angles (multiples of 90 degrees) around a user-defined axis. The axis vector is read from a channel parameter, normalized, then multiplied by the quantized noise value to create rotation angles that are stored as quaternions in the @orient attribute.

### Interactive Noise Manipulation with Ramps [Needs Review] [[Ep7, 60:02](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3602s)]
```vex
vector axis;
axis = normalize(axis);

@orient = quaternion(axis);

v@orient = quaternion(axis);
axis = chv("axis");
axis = normalize(axis);

@a = noise(@P*10);
@a = chv("a");

@orient = quaternion(axis);

@P.y = @a;

@orient = quaternion(axis);
```
Demonstrates using channel references and ramps to get interactive visual feedback when tweaking noise values. By connecting UI controls to noise parameters, you can adjust values in real-time and see how they affect the output, similar to adjusting levels in Photoshop. The ramp allows you to fit and remap the noise distribution dynamically.

### Visualizing Noise with Quaternion Rotation [[Ep7, 61:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3664s)]
```vex
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a = noise(@ptnum);
@a = chramp('noise_remap', @a);
axis *= trunc(@a/4)*(PI);
@orient = quaternion(axis);
```
This code generates noise-driven rotation by creating a normalized axis vector from a parameter, generating noise per point, remapping it through a ramp parameter, then using that value to create quaternion orientations. The truncation reduces rotation contrast by quantizing the angle values before converting to quaternions.

### Visualizing Data with Height and Orientation [[Ep7, 62:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3750s)]
```vex
vector axis;
axis = chv('a');
axis = normalize(axis);
axis = noise(@ptnum);
@a = chramp('noise_remap', @a);
axis *= trunc(@a*4)*(PI/2);
@P.y = @a;

@orient = quaternion(axis);

@N = {0,1,0};
float a = sin($F*0.1);
float c = cos($F*0.1);
@up = set(a,0,c);

@orient = quaternion(maketransform(@N, @up));
```
Uses noise-driven attribute values to control both point height (@P.y) and orientation through quaternions. The technique employs chramp to remap noise values and trunc to create discrete rotation steps, causing points to jump between different height levels based on threshold values that can be adjusted to visualize data distribution.

## Curl Noise

### Curl Noise with Vector Offset [Needs Review] [[Ep8, 90:28](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5428s)]
```vex
vector pos = chv('pos');
@P += pos * curlnoise((@P + {0,1,0}) * (@w * 0.2) * @Time, 0, 0);
```
Offsets point positions using curl noise driven by a channel-referenced vector parameter. The noise input combines the point position with a vertical offset, scaled by a point attribute @w and time, creating animated divergence-free flow patterns that can be controlled via the pos parameter.

## See Also
- **VEX Common Patterns** (`vex_patterns.md`) -- noise displacement patterns
- **VEX Functions Reference** (`vex_functions.md`) -- noise function signatures
