# Joy of VEX: Trigonometry & Oscillation

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Triggers

- trigonometry, trig, sine, cosine, sin, cos
- oscillation, wave, ripple, radial wave
- fit, remap, normalize, range
- distance, length, origin
- up vector, rotation, spin, orient
- pscale, point scale, animated scale
- @Time, @Frame, animation, time offset

## Context

VEX trigonometry for procedural animation: radial ripples, oscillating color, animated
point scale, spinning orientation vectors. All examples run per-point in a wrangle node.

## Code

### Quick Reference
```vex
@P.y = sin(@P.x);                          // Sine wave: output range always [-1, 1]
float d = length(@P);                       // Distance from origin to each point
v@up = set(sin(@Time), 0, cos(@Time));      // Rotating up vector with time
@Cd = fit(sin(d), -1, 1, 0, 1);            // Remap sine output to [0,1] for color
```

### Compound assignment operators [Ep1, 100:42]
```vex
// *= is shorthand for @P = @P * ch('scaling') — cleaner, same result
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float delta = distance(pos, center);
@P *= ch('scaling');                        // compound assignment: multiply-and-assign
@Cd = fit(sin(delta), -1, 1, 0, 1);
```

### Sine Function for Color Animation [Ep1, 44:12]
```vex
// Progression: raw ptnum -> scaled float -> channel-controlled
@Cd = float(@ptnum)/ch('scale');            // step 1: linear gradient from point index

@Cd = sin(@ptnum);                          // problem: integer input gives chunky steps

@Cd = sin(@ptnum/100);                      // still integer division — still chunky

@Cd = sin(float(@ptnum)/100);              // cast to float first: smooth sine wave

@Cd = sin(float(@ptnum)*ch('scale'));       // use channel for interactive control

float foo = float(@ptnum)*ch('scale');      // store intermediate in variable for clarity
@Cd = sin(foo);
```

### Sine Wave with Integer Division Problem [Ep1, 47:12]
```vex
// Integer division truncates: sin(@ptnum/100) steps, not waves
// Cast to float before dividing to get smooth continuous oscillation
@Cd = sin(@ptnum/100);                      // BAD: integer division -> discrete steps

@Cd = sin(float(@ptnum)/100);              // GOOD: float division -> smooth wave

float foo = float(@ptnum)/ch('scale');      // channel reference for art-directable frequency
@Cd = sin(foo);
```

### Sine waves with CH function [Ep1, 48:34]
```vex
// ch('scale') enables interactive frequency control without code edits
@Cd = sin(float(@ptnum)/ch('scale'));

// Evolution from hardcoded to parameterized:
// @Cd = sin(@ptnum);              // integer — chunky
// @Cd = sin(@ptnum/100);          // still integer division
// @Cd = sin(float(@ptnum)/100);   // smooth but fixed frequency
// @Cd = sin(float(@ptnum)/ch('scale')); // fully parameterized

float foo = float(@ptnum)/ch('scale');      // named variable improves readability
@Cd = sin(foo);
```

### Clean Code and Using Variables [Ep1, 55:52]
```vex
// Break complex calculations into named steps for readability
float foo = @P.x/ch('scale');              // scaled X position
@Cd = sin(foo);                            // sine wave driven by position
```

### Length Function and Distance Calculations [Ep1, 61:02]
```vex
// length(@P) = distance from origin; then sine creates radial rings
float d = length(@P);
@Cd = sin(d);
```

### Distance to Origin and Sine Wave [Ep1, 62:26]
```vex
float d = length(@P);
@Cd = d;                                   // raw distance as color: bright = far

float d = length(@P);
@Cd = sin(d);                              // sine of distance: radial concentric rings
```

### Distance and Sine Progression [Ep1, 66:10]
```vex
// Build complexity gradually: position -> distance -> sine -> scaled sine
float foo = @P.y*ch('scale');
@Cd = sin(foo);                            // Y-axis wave

float d = length(@P);
@Cd = d;                                   // raw distance gradient

float d = length(@P);
@Cd = sin(d);                              // radial rings

float d = length(@P);
d *= ch('scale');                          // *= scales frequency of rings
@Cd = sin(d);
```

### Scaling Distance with Compound Operators [Ep1, 69:36]
```vex
// d *= ch('scale') == d = d * ch('scale') — ring frequency controlled by slider
float d = length(@P);
d *= ch('scale');
@Cd = sin(d);
```

### Remapping sine wave range [Ep1, 71:46]
```vex
// sin() outputs [-1, 1]; color needs [0, 1]
// (sin(d) + 1) / 2  shifts to [0,2] then halves to [0,1]
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d) + 1) / 2;
```

### Normalizing sine wave color range [Ep1, 72:00]
```vex
// Two equivalent forms for remapping sine from [-1,1] to [0,1]
float d = length(@P);
d *= ch('scale');
@Cd = (sin(d)+1)/2;                        // form 1: add 1, divide by 2

@Cd = (sin(length(@P) * ch('scale'))+1)*0.5;  // form 2: compact inline, *0.5 == /2
```

### Vector scaling in distance calculations [Ep1, 82:48]
```vex
// Multiply @P by a vector to scale individual axes before distance calc
// {0.5,1,1} compresses X by half -> elliptical ring pattern instead of circular
vector center = chv('center');
float d = distance(@P * {0.5,1,1}, center);   // non-uniform axis scaling
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;

// Variants:
// float d = distance(@P, {1,0,1});           // distance to fixed point off-center
// vector center = chv('center');
// float d = distance(@P, center);            // channel-controlled center
// d *= ch('scale');
// @Cd = (sin(d)+1)*0.5;
```

### Non-uniform position scaling for distance patterns [Ep1, 83:36]
```vex
// Storing scaled position in variable makes the intent explicit
vector center = chv('center');
vector pos = @P * {0.5, 1, 1};            // stretch X by 0.5 -> ellipse pattern
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;
```

### Remapping sine waves with fit [Ep1, 88:42]
```vex
// fit() is cleaner than manual (sin+1)*0.5 for range remapping
// Version 1: manual remap
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = (sin(d)+1)*0.5;                     // manual: add 1, halve

// Version 2: fit() — same result, clearer intent
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);          // fit remaps [-1,1] -> [0,1]

// Version 3: animate with @Time
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);  // multiply by time -> animated ripple
```

### Using fit() with sin() for animation [Ep1, 94:18]
```vex
// Progression: broken fit() -> correct fit() -> animated
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(d);                              // BROKEN: fit() needs 4 extra args

vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);          // correct: remap sin output to [0,1]

vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d * @Time), -1, 1, 0, 1);  // animated ripple via @Time
```

### Animating with @Frame vs @Time [Ep1, 97:12]
```vex
// @Frame = integer counter (jumpy); @Time = float in seconds (smooth)
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
@Cd = fit(sin(d*@Frame),-1,1,0,1);        // @Frame: fast integer-rate animation
```

### Code Style and Mathematical Operations [Ep1, 99:50]
```vex
// Compound operators chain math clearly; comments document intent
vector pos = @P * chv('fancyscale');
vector center = chv('center');
float d = distance(pos, center);
d *= ch('scale');
@Cd = fit(sin(d), -1, 1, 0, 1);

foo -= 5;
foo *= 5;
foo -= foo * 5 / @P.x * @N.y;

foo *= 1;       // set range
foo -= 1;       // make sure values never get below 0
foo /= @P.x;    // reduce range to within red value
foo += @N.y;    // add normal Y
```

### Length and Clamp Functions [Ep2, 18:52]
```vex
// length(@P) = distance from origin; displace along normal by sine of distance
float d = length(@P);
v@z = ch("_scale");
@P += @N * sin(d) * ch("wave_height");    // radial wave: push verts along normals
```

### Distance normalization and clamping [Ep2, 27:28]
```vex
// asin() domain is [-1,1]; clamp distance before passing to avoid NaN
float d = length(@P);
@P.y = d*d + 1 * 10;                      // squared distance drives Y position
d = asin(clamp(d, 0, 1));                 // clamp keeps d in valid asin range
```

### Animating Sine Waves with Ramps [Ep2, 49:06]
```vex
// d += @Time offsets the wave phase each frame -> outward-propagating ripple
float d = length(@P);
d *= ch('scale');
d += @Time;                               // add time to phase-shift animation
d = sin(d);
d = fit(d,-1,1,0,1);                      // normalize for ramp/color use
```

### Animating Grid with Ramp and Sin Wave [Ep2, 49:12]
```vex
// Two channel multipliers for independent scale and width control
float d = length(@P);
d *= ch('scale');
d *= ch('width');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
```

### Animating with sine wave [Ep2, 49:14]
```vex
// @Frame provides integer-rate animation; @Time is smoother
float d = length(@P);
d *= ch('scale');
d += @Frame;                              // integer frame offset for phase
d = sin(d);
d = fit(d, -1, 1, 0, 1);
```

### Animating Height with Ramp and Sine [Ep2, 49:40]
```vex
// Pattern: distance -> scale -> time offset -> sin -> fit -> drive attribute
float d = length(@P);
d *= ch('scale');
d += @Frame;
d = sin(d);
d = fit(d,-1,1,0,1);                      // use result with chramp() or @P.y
```

### Animated Ripple with Nested Trigonometry [Ep2, 52:12]
```vex
// Nested sin/cos creates complex wave interference patterns
float d = length(@P);
d *= ch('scale');
d -= @Time;                               // subtract time: ripple moves outward
@P.y = sin(d/cos(d/cos(d)));             // nested trig: intricate interference
@Cd = ch('height');
```

### Sine Wave Pattern with Fit [Ep2, 52:56]
```vex
// Standard animated radial ripple pattern
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);                 // normalize for color/ramp attrs
```

### Sine Wave with Ramp and Fit [Ep2, 65:32]
```vex
// Drive chramp with normalized sine for position, ch for color
float d = length(@P);
d *= ch('scale');
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);                 // fit required before chramp lookup
@P.y = chramp('myRamp', d);              // ramp controls vertical displacement
@Cd = ch('height');
```

### Normalizing Values with Fit [Ep2, 66:46]
```vex
// Normalized value drives both ramp-based color and a scalar height channel
float d = length(@P);
d *= ch("scale");
d += @Time;
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd.y = chramp("my ramp", d);            // ramp lookup needs [0,1] input
@Cd.x = chf("height");
```

### Sine Wave Output Range [Ep2, 67:54]
```vex
// sin() is always bounded [-1, 1] — never needs clamping, but needs remapping for color
@P.y = sin(@P.x);                        // creates continuous wave; Y stays in [-1, 1]
```

### Length function with fit remapping [Ep2, 6:10]
```vex
// len(@P) returns int length of position vector; fit remaps sine output to custom range
int i = 1 + len(@P);
f@x = fit(sin(i), 0, 1, 0.1, 3.1);      // remap [0,1] -> [0.1, 3.1] for custom attr
```

### Sine Wave Ripple with Color Ramp [Ep2, 71:20]
```vex
// Double sine for more complex oscillation; fit normalizes before ramp lookup
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = sin(d);                              // second sin creates interference-like shape
d *= fit(d, -1, 1, 0, 1);
@Cd = chramp('my_ramp', d);
@P.y *= ch('height');
```

### Radial Sine Wave Color and Height [Ep2, 71:30]
```vex
// set(d,d,d) broadcasts scalar d to all three color channels (grayscale)
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d,-1,1,0,1);
@Cd = set(d,d,d);                        // or: @Cd = vector(d);  — same result
@P.y *= ch('height');
```

### Distance-Based Ripple Pattern [Ep2, 74:16]
```vex
// vector(d) is equivalent shorthand for set(d,d,d)
float d = length(@P);
d *= ch('scale');
d = sin(d);
d = fit(d, -1, 1, 0, 1);
@Cd = vector(d);                         // scalar -> grayscale vector
@P.y *= ch('height');
```

### Distance-based Y displacement with channels [Ep3, 13:50]
```vex
// Classic ripple: scale distance by channel, displace Y by sine
float d = length(@P);
d *= ch("scale");
@P.y = sin(d);                           // ring-ripple mesh deformation
```

### Sine Wave Amplitude and Distance Falloff [Ep5, 64:18]
```vex
// fit(d, 0, radius, 1, 0) inverts distance -> wave amplitude fades to zero at radius edge
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
w = ch('amp') * w;                        // amplitude control
w *= fit(d, 0, ch('radius'), 1, 0);      // falloff: 1 at center, 0 at edge
@P.y += w;
```

### Animated sine wave displacement [Ep6, 18:08]
```vex
// d *= d creates squared distance -> frequency increases with distance from center
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= d * ch('frequency');                // squared: faster rings farther out
d += t;
d = sin(d);
@P.y += d;
```

### Animated Sine Wave Point Scale [Ep6, 18:10]
```vex
// fit() maps sine output to user-defined min/max instead of always [0,1]
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= d * ch('frequency');               // squared distance -> non-linear frequency
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));  // custom output range
@pscale = d;
```

### Animated Pscale with Fit and Sin [Ep6, 18:52]
```vex
// Radiating wave controls point scale — useful for instanced geometry
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, ch('min'), ch('max'));
@pscale = d;
```

### Animated sine wave scaling [Ep6, 19:08]
```vex
// Same wave drives both color and pscale simultaneously
float d, t;
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
@Cd = fit(sin(d), -1, 1, ch('min'), ch('max'));  // color from wave
@pscale = d;                                      // pscale from same wave
```

### Animated Scale from Distance [Ep6, 25:02]
```vex
// set(min, d, min) — distance wave affects Y scale only; X and Z stay at min
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);               // Y varies; X/Z locked to min
```

### Animated scale from distance [Ep6, 27:58]
```vex
// Z-axis scale varies with wave; useful for directional scale on instanced geo
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);              // X=min, Y=max, Z=wave value
@Cd = set(0, 1, 0);
```

### Animated scale based on distance [Ep6, 28:08]
```vex
// set(min, min, d) — wave drives Z only; uniform X/Y for blade/spike shapes
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, min, d);              // Z=wave, X/Y=min
```

### Animating Scale with Sine Wave [Ep6, 28:58]
```vex
// t = @ptnum * ch('speed') — per-point time offset creates staggered wave
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @ptnum * ch('speed');               // offset by point index, not global time
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
```

### Animated scaling with time and distance [Ep6, 29:14]
```vex
// Preserve @P.y as a separate attribute while animating scale
float min, max, d, t;
min = ch('min');
max = ch('max');
t = @Time * ch('speed');
d = length(@P);
d *= ch('frequency');
d += t;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, max, d);
@y = @P.y;                              // cache Y position for downstream nodes
```

### Animated Scale with Distance [Ep6, 29:26]
```vex
// fit(@Time * ch('speed'), 0, 1, 0, 1) normalizes time — useful for ramp-driven speed
float min = ch('min');
float max = ch('max');
float t = fit(@Time * ch('speed'), 0, 1, 0, 1);
float d = length(v@P);
float s = ch('frequency');
d = d * s;
d = fit(sin(d), -1, 1, min, max);
@scale = set(min, d, min);              // Y varies
// or:
@scale = set(min, min, d);             // Z varies
```

### Animating Up Vector with Time [Ep6, 46:32]
```vex
// up vector controls orientation of instanced geometry (e.g., copy-to-points)
v@up = set(0, 1, 0);                    // static: points up in Y

v@up = {0, 0, 1};                       // static: points in Z (inline vector syntax)

v@up = set(sin(@Time), 0, 0);           // animated: X oscillates over time
```

### Rotating Up Vector with Time [Ep6, 47:36]
```vex
// sin + cos in X/Z with Y=0 traces a unit circle -> continuous smooth rotation
v@up = set(sin(@Time), 0, cos(@Time));  // rotates in XZ plane; geometry spins around Y
```

### Animating Up Vector with Time Offsets [Ep6, 47:48]
```vex
// Progression: global rotation -> per-point offset -> distance-based offset
v@up = set(sin(@Time), 0, cos(@Time));  // all points rotate in sync

float t = @Time - @ptnum * 0.1;        // subtract ptnum offset: points lag behind
v@up = set(sin(t), 0, cos(t));

float t = @Time - @ptnum * ch('offset');  // channel-controlled stagger
v@up = set(sin(t), 0, cos(t));

float d = length(@P);
float t = @Time + d * ch('offset');    // distance-based offset: wave from center
```

### Time offset by point number [Ep6, 48:46]
```vex
// Each point's rotation lags by 0.1 * ptnum — creates cascading wave effect
float t = @Time + @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));
```

### Time-based rotation with point offset [Ep6, 48:50]
```vex
// Multiply (not add) ptnum into time: offset grows faster for distant points
float t = @Time * @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));
```

### Time-based rotation with offset [Ep6, 48:52]
```vex
// Three stagger methods: fixed factor, channel, distance-based
float t = @Time * 0.1 + @ptnum * 0.1;
v@up = set(sin(t), 0, cos(t));

// Channel-controlled stagger amount
float t = @Time * 0.1 + @ptnum * CH("offset");
v@up = set(sin(t), 0, cos(t));

// Distance-from-origin stagger: ripple propagates outward
float d = length(@P);
float t = @Time + d * CH("offset");
v@up = set(sin(t), 0, cos(t));
```

### Time-based Up Vector Animation [Ep6, 49:48]
```vex
// Combine time + ptnum + channel offset for art-directable wave stagger
float t = @Time + @ptnum + ch('offset');
v@up = set(sin(t), 0, cos(t));
```

### Distance-based Up Vector Animation [Ep6, 51:10]
```vex
// Distance multiplied by channel offset: closer points rotate slower/faster
float d = length(@P);
vector t = @Time * d * ch('offset');
v@up = set(sin(t), 0, cos(t));
```

### Wave Animation with Distance Offset [Ep6, 52:30]
```vex
// Dual effect: up vector rotates AND Y position bounces at double frequency
float d = length(@P);
float t = @Time - d * ch('offset');     // wave propagates outward from origin
v@up = set(sin(t), 0, cos(t));          // rotation in XZ plane
@P.y += sin(t * 2) * 0.5;              // double freq, half amplitude bounce
```

### Animated vector orientation with sine waves [Ep6, 54:02]
```vex
// Time * channel offset (not distance) — all points share same phase offset rate
float d = length(@P);
float t = @Time * ch('offset');
v@up = set(sin(t), 0, cos(t));
@P.y += sin(t * 2) * 0.5;              // secondary vertical oscillation at 2x freq
```

### Mixed vector and attribute operations [Ep6, 56:44]
```vex
// End-of-lesson exploration: distance, color vector, up, and Y displacement together
float d = length(@P);
vector c = {1-d, 0, d*offset};         // color varies with distance
v@up = set(sin(s), 0, cos(s));
@P.y += sin(s.x * 2) * 0.5;
```

### Animated up vector using distance and time [Ep6, 56:52]
```vex
// @Time * d * f@offset: per-point distance scales the time offset
float d = length(@P);
float t = @Time * d * f@offset;
v@up = set(sin(t), 0, cos(t));         // XZ rotation
@P.y += sin(t * 2) * 0.5;             // secondary vertical motion at 2x freq
```

### Animated up vector with distance [Ep6, 56:56]
```vex
// 1.0/'offset' channel reference style; normal animated at double frequency
float d = length(@P);
vector t = @Time * d * (1.0/'offset');
v@up = set(sin(t), 0, cos(t));
v@N = sin(t * 2) * 0.5;               // normal oscillates at 2x speed, 0.5 amplitude
```

### Rotating Up Vector with Sin and Cos [Ep7, 66:18]
```vex
// Classic sin/cos up-vector rotation: s starts 0, c starts 1 -> circular motion
int i = {0,1,0};
float s = sin(@Time);
float c = cos(@Time);
@up = set(s, 0, c);                    // rotate in XZ plane around Y axis
```

## Common Mistakes

```vex
// MISTAKE: integer division gives chunky results
@Cd = sin(@ptnum / 100);      // @ptnum is int -> division truncates -> steps

// FIX: cast to float first
@Cd = sin(float(@ptnum) / 100.0);

// MISTAKE: sine output [-1,1] used directly as color (dark/negative = black clamp)
@Cd = sin(d);

// FIX: remap to [0,1] before assigning to color
@Cd = fit(sin(d), -1, 1, 0, 1);
// or equivalently:
@Cd = (sin(d) + 1) * 0.5;

// MISTAKE: asin/acos without clamping -> NaN when input > 1
d = asin(d);                  // NaN if d > 1 (e.g., far-from-origin points)

// FIX: clamp to valid domain first
d = asin(clamp(d, -1.0, 1.0));

// MISTAKE: intensity > 1 in lights (violates Lighting Law)
// light_node.intensity = 5.0;  // WRONG

// FIX: keep intensity = 1.0, use exposure to control brightness
// light_node.intensity = 1.0;
// light_node.exposure = 2.0;  // +2 stops = 4x brighter

// MISTAKE: fit() called without all required arguments
@Cd = fit(d);   // BROKEN — needs fit(value, srcmin, srcmax, dstmin, dstmax)

// FIX:
@Cd = fit(d, 0, 10, 0, 1);
```

## See Also
- **VEX Functions Reference** (`vex_functions.md`) -- trigonometric function signatures
