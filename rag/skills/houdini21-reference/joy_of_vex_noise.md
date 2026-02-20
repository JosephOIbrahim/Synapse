# Joy of VEX: Noise & Randomness

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Triggers
noise, rand, curlnoise, randomness, procedural, animated noise, curl noise, quaternion wobble, noise color, noise deletion, noise orientation, fit noise, chramp noise, quantized rotation, wave animation

## Context
VEX noise and randomness patterns from Matt Estela's Joy of VEX series. Covers noise(), curlnoise(), rand() with seed, noise-driven quaternion orientations, fit/chramp remapping, and wave animation.

## Code

### Quick Reference
```vex
// Animated curl noise color -- combine position, scale param, and @Time
@Cd = curlnoise(@P * chv('fancyscale') + @Time);

// Curl noise remapped to 0-1 range
v@Cd = curlnoise(@P * chv('fancyscale')) * 0.5 + 0.5;

// Single channel from curl noise
@Cd = curlnoise(@P * cv('fancyscale') + @Time);
```

### Noise with Parameters and Animation [[Ep3, 60:14](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3614s)]
```vex
// Progressive enhancement: add chv() for UI-controllable scale/offset, then @Time for animation.
// chv() reads a vector parameter -- gives 3D control over noise frequency and offset.
// @Time drives continuous animation; multiply by scale for speed control.
@Cd = noise(chv('offset') + @P * chv('fancyscale') * @Time);
```

### Noise Function Basics [[Ep3, 61:02](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3662s)]
```vex
// noise() takes spatial coords modified by scale and offset params to generate variation.
// Combine position, velocity, and time with channel parameters for animated noise.
noise(@P * chf('offset') + @v * chv('fancyscale') * @Time);
```

### Noise Function with Parameters [[Ep3, 61:18](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3678s)]
```vex
// chv() reads vector parameters for real-time UI adjustment of noise characteristics.
// Offset shifts the noise lookup position; fancyscale controls spatial frequency.
@Cd = noise(chv('offset') + @P * chv('fancyscale'));
```

### Noise with Channel References and Time [[Ep3, 62:58](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3778s)]
```vex
// Add @Time as a 4th coordinate to animate the noise pattern over the timeline.
// chv() provides 3D control; @Time drives animation independently of position.
@Cd = noise(chv('offset') + @P * chv('fancyscale') + @Time);
```

### Animating Noise with Offset Parameter [[Ep3, 64:18](https://www.youtube.com/watch?v=fOasE4T9BRY&t=3858s)]
```vex
// @Frame creates discrete per-frame steps; @Time is continuous (uses float seconds).
// Multiply channels together: offset * position * scale * frame = animated noise.
@Cd = noise(chv('offset') * @P * chv('fancyscale') * @Frame);
```

### Animated Noise with Time [[Ep3, 67:02](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4022s)]
```vex
// Adding @time (lowercase) to the result -- not the input -- shifts color over time.
// Multiplying by @P stretches the noise pattern outward from the origin.
@Cd = noise(@P + chv('offset')) * @P * chv('fancyscale') + @time;
```

### Animated Curl Noise Color [[Ep3, 68:08](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4088s)]
```vex
// curlnoise() returns a divergence-free 3D vector field (no sinks/sources).
// Directly assign to @Cd for organic flowing color patterns.
// fancyscale controls spatial frequency; @Time drives the animation.
@Cd = curlnoise(@P * chv('fancyscale') + @Time);
```

### Curlnoise Color Animation [[Ep3, 68:10](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4090s)]
```vex
// Extract a single channel (.g = green) from the curl noise vector result.
// Assign only to @Cd.x (red) to create grayscale-style time-varying color.
@Cd = 0;
@Cd.x = curlnoise(@P * chv('fancyscale')).g * @Time;
```

### Curl Noise Function Arguments [[Ep3, 68:50](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4130s)]
```vex
// curlnoise() evaluates its entire argument as one expression before processing.
// Multiply result by 0.5 + 0.5 to remap from [-1,1] to [0,1] range for color.
v@Cd = curlnoise(@P * chv('fancyscale')) * 0.5 + 0.5;
```

### Curl Noise Color Animation -- Single Component [[Ep3, 69:18](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4158s)]
```vex
// Assign the full vector to @Cd, then access .x / [0] / .r interchangeably.
v@Cd = curlnoise(@P * chv('fancyscale') * @Time);
// @Cd[1] accesses the green channel (same as @Cd.g or @Cd.y)
```

### Curl Noise Color with Channel [[Ep3, 69:30](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4170s)]
```vex
// cv() is an alias for chv() -- reads a vector channel parameter.
// curlnoise() returns a 3D vector; assign directly to @Cd for flowing color.
@Cd = curlnoise(@P * cv('fancyscale') + @Time);
```

### Animating Curlnoise with Time [[Ep3, 71:10](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4270s)]
```vex
// Double-quoted channel names work identically to single-quoted.
// curlnoise creates divergence-free swirling color -- useful for fluid-like effects.
@Cd = curlnoise(@P * chv("fancyscale") * @Time);
```

### Curlnoise Single Component Assignment [[Ep3, 72:04](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4324s)]
```vex
// Zero the full color first, then drive only the x (red) channel.
// Extracts scalar noise from a vector noise function by taking one component.
@Cd = 0;
@Cd.x = curlnoise(@P * chv('fancyscale') + @Time);
```

### Curlnoise Color Components [[Ep3, 72:12](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4332s)]
```vex
// vector(0) zeros all three components. Then assign only the .x component.
// .x, .r, and [0] are all equivalent ways to access the first component.
v@Cd = vector(0);
v@Cd.x = curlnoise(@P * chv('fancyscale') + @Time).x;
```

### Curl Noise Color Animation -- Red Channel [[Ep3, 74:20](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4460s)]
```vex
// Initialise to black, then drive only the red channel with curlnoise * time.
// Multiplying the curlnoise result by @Time grows the effect over the timeline.
@Cd = 0;
@Cd.x = curlnoise(@P * chv("fancyscale")) * @Time;
```

### Curlnoise with Time Animation [[Ep3, 74:22](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4462s)]
```vex
// Seed color from position, then override only the red channel with animated curlnoise.
// Adding @Time to the noise input translates the lookup through the field over time.
@Cd = @P;
@Cd.r = curlnoise(@P * chv('fancyscale') + @Time);
```

### Animated Curl Noise Color -- Position Seed [[Ep3, 80:32](https://www.youtube.com/watch?v=fOasE4T9BRY&t=4832s)]
```vex
// Same as above but uses .x instead of .r (identical in VEX).
// Curl noise generates a 3D vector; only the x component drives the red channel.
@Cd = @P;
@Cd.x = curlnoise(@P * chv('fancyscale') + @Time);
```

### For Loop with Curl Noise [[Ep5, 125:54](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=7554s)]
```vex
// Build a polyline by iterating, computing curl noise offset at each step.
// Subtracting @Time from pos shifts the lookup through the field for animation.
// Adding i gives each iteration a unique noise sample even at the same position.
vector offset, pos;
int pr, pt;
float stepsize;

pr = addprim(0, 'polyline');
stepsize = 0.5;

for (int i = 0; i < 6; i++) {
    offset = curlnoise(pos - @Time + i);
    pos += offset * stepsize;
    pt = addpoint(0, pos);
    addvertex(0, pr, pt);
}
```

### Random Primitive Removal with Seed Control [[Ep5, 144:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8670s)]
```vex
// rand() with a seed parameter gives repeatable randomness.
// cutoff slider controls what percentage of geometry is removed.
// Two-argument rand() hashes both values together for a unique result per seed.

// Remove primitives probabilistically (run over primitives)
if (rand(@primnum, ch('seed')) < ch('cutoff')) {
    removepoint(0, @primnum, 1);
}

// Remove based on point number (run over points)
if (rand(@ptnum) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}

// Remove primitives with seeded randomness (run over points)
if (rand(@ptnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
```

### Random Primitive Removal via Primitive UV [[Ep5, 144:38](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=8678s)]
```vex
// Hash on @primuv for UV-space-based randomness rather than integer primnum.
// seed changes the pattern; cutoff sets the removal threshold.
if (rand(@primuv, ch('seed')) < ch('cutoff')) {
    removepoint(0, @primuv, 1);
}
```

### Random Point Deletion with Seed [[Ep5, 159:42](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9582s)]
```vex
// Set an up vector, then conditionally delete points with seeded randomness.
// rand() = white noise; noise() = structured, scalable, animatable pattern.
v@up = set(0, 1, 0);
if (rand(@primnum, ch('seed')) < ch('cutoff')) {
    removepoint(0, @primnum, 1);
}
```

### Noise vs Rand for Deletion [[Ep5, 159:50](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=9590s)]
```vex
// rand() = pure white noise, good for scattered random removal.
// noise() = spatially coherent, can be scaled/animated -- flows across geometry.

// rand-based removal
if (rand(@primnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}

// Add a point and connect as polyline (example of procedural topology)
int pt = addpoint(0, {0, 1, 0});

// Conditional point addition on first point only
if (@ptnum == 0) {
    addpoint(0, {0, 1, 0});
}
```

### Time-based Wave Animation with Randomness [[Ep5, 84:08](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5048s)]
```vex
// Accumulate sine-wave displacement from all nearby points.
// rand(pt) offsets timing per-point so waves don't fire in sync.
// d*ch('freq') ties wave frequency to distance; d*ch('amp') ties amplitude.
vector pos;
int pts[];
int pt;
float d, s, f, t, e, a;

pts = nearpoints(1, @P, ch('radius'));

foreach (int pt; pts) {
    pos = point(1, "P", pt);
    d   = distance(@P, pos);
    s   = fit(d, 0, ch('radius'), 1, 0); // falloff: 1 at center, 0 at edge
    s   = chramp('s', s);                 // artistic ramp control over falloff
    t   = @Time * ch('speed');            // global time, scaled by speed
    t  += rand(pt);                       // per-point time offset for variety
    a   = d * ch('amp');                  // amplitude scales with distance
    f   = d * ch('freq');                 // frequency scales with distance
    e  += sin(t * f) * a;                 // accumulate sine displacement
}
@P.y += e;
```

### Time-based Wave Animation Setup [[Ep5, 84:10](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5050s)]
```vex
// Minimal setup: gather nearpoints, compute distance-based amplitude and frequency,
// then add rand(pt) to time so each point's wave is offset differently.
vector pos;
int pts[];
int pt;
float d, a, f, t;

pts = nearpoints(1, @P, 40);

foreach (int pt; pts) {
    pos = point(1, "P", pt);
    d   = distance(@P, pos);
    a   = fit(d, 0, ch("radius"), 1, 0); // falloff weight
    d   = clamp(d, a, 1);
    t   = @Time * ch("speed");           // scaled time
    t  += rand(pt);                      // per-point random time offset
    a   = d * ch("amp");
    f   = d * ch("freq");
}
```

### Quaternion Wobble with Curl Noise [[Ep7, 107:58](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6478s)]
```vex
// Build orientation from surface normal, add a fixed tilt (extrarot),
// then a sine-based head-shake (headshake).
// wobble uses curlnoise -- position-based so each point gets unique motion.
vector N, up;
vector4 extrarot, headshake, wobble;

N  = normalize(@P);
up = {0, 1, 0};
@orient  = quaternion(maketransform(N, up));
extrarot = quaternion(radians(@0), {1, 0, 0});
headshake = quaternion(radians(20) * sin(@Time * 3), {0, 1, 0});
wobble   = quaternion({0, 0, 1} * curlnoise(@P + @Time)); // Z-axis curl noise wobble

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
// @orient = qmultiply(@orient, wobble);  // add wobble layer when ready
```

### Quaternion Wobble with Curl Noise -- Full [[Ep7, 108:26](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6506s)]
```vex
// Three-layer orientation: base align + fixed tilt + head-shake + noise wobble.
// curlnoise(pos + time, roughness, attenuation) -- second arg controls roughness.
// Each point gets unique wobble because the noise lookup is keyed to @P.
vector N, up;
vector4 extrarot, headshake, wobble;

N  = normalize(@P);
up = {0, 1, 0};
@orient   = quaternion(maketransform(N, up));
extrarot  = quaternion(radians(ch("angle")), {1, 0, 0});
headshake = quaternion(radians(20) * sin(@Time * 3), {0, 1, 0});
wobble    = quaternion({0, 0, 1} * curlnoise(@P + @Time, 2)); // roughness = 2

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```

### Quaternion Wobble with Curl Noise -- Clean [[Ep7, 108:32](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6512s)]
```vex
// Slowed-down version: @Time * 0.2 reduces wobble animation speed.
// h = normalized position direction (radial from origin).
// 90-degree tilt aligns geometry standing on a sphere surface.
vector h, up;
vector4 extrarot, headshake, wobble;

h  = normalize(@P);
up = {0, 1, 0};
@orient   = quaternion(maketransform(h, up));
extrarot  = quaternion(radians(90), {1, 0, 0}); // 90-deg tilt to stand upright
headshake = quaternion(radians(20) * sin(@Time * 3), {0, 1, 0});
wobble    = quaternion({0, 0, 1} * curlnoise(@P + @Time * 0.2)); // slow wobble

@orient = qmultiply(@orient, extrarot);
@orient = qmultiply(@orient, headshake);
@orient = qmultiply(@orient, wobble);
```

### Noise-based Quaternion Rotation [[Ep7, 52:46](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3166s)]
```vex
// trunc(noise * 4) quantizes noise to 0/1/2/3, multiplied by PI/2 = 90-deg steps.
// This creates stepped rotations (0, 90, 180, 270) that animate as noise evolves.
// Using @P + @Time makes patterns spatially coherent and time-animated.
vector axis1;
axis1 = chv("axis");
axis1 = normalize(axis1);
float angle = trunc(noise(@P + @Time) * 4) * $PI / 2;

@orient = quaternion(angle, axis1);
```

### Noise-Based Orientation with Quaternions [[Ep7, 52:50](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3170s)]
```vex
// noise(@P * @Frame) -- multiply position by frame for time-animated noise.
// Axis is scaled by quantized angle, then quaternion(axis) uses axis-angle form
// where |axis| = angle in radians.
vector axis;
axis = chv('axis');
axis = normalize(axis);
axis *= trunc(noise(@P * @Frame) * 4) * $PI / 2;

@orient = quaternion(axis);
```

### Quaternion Rotation from Noise [[Ep7, 53:14](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3194s)]
```vex
// Use @P.y as a secondary noise seed to break up horizontal banding.
// trunc(@a * 4) * (PI/2) = four discrete rotation steps at 90-deg intervals.
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a   = noise(@P + @P.y);        // use y as additional seed to reduce banding
axis *= trunc(@a * 4) * (PI / 2);

@orient = quaternion(axis);
```

### Remapping Noise with Fit and Ramp [[Ep7, 54:10](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3250s)]
```vex
// Three approaches to controlling noise distribution for quaternion rotation.

// 1. Raw noise -- limited variance (noise() output clusters around 0.4-0.6)
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a   = noise(@P + @Time);
axis *= trunc(@a * 4) * PI / 2;
@orient = quaternion(axis);

// 2. fit() stretches the 0.4-0.6 cluster to full 0-1 range for better distribution
axis = chv('axis');
axis = normalize(axis);
@a   = noise(@P + @Time);
@a   = fit(@a, 0.4, 0.6, 0, 1); // expand midrange noise to full range
axis *= trunc(@a * 4) * PI / 2;
@orient = quaternion(axis);

// 3. chramp() for full artistic control via a ramp parameter widget
axis = chv('axis');
axis = normalize(axis);
@a   = noise(@P + @Time);
@a   = chramp('noise_remap', @a); // ramp lets you sculpt the distribution
axis *= trunc(@a * 4) * PI / 2;
@orient = quaternion(axis);
```

### Remapping Noise with Fit Function [[Ep7, 55:44](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3344s)]
```vex
// fit() remaps the 0.4-0.6 band of noise values to 0-1, amplifying contrast.
// This makes discrete rotation steps (trunc * PI/2) distribute more evenly.
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a   = noise(@P * @Time);
@a   = fit(@a, 0.4, 0.6, 0, 1); // stretch midrange to full range
axis *= trunc(@a * 4) * @t / 2;

@orient = quaternion(axis);
```

### Quaternion Rotation from Noise -- Lmn Freq [[Ep7, 56:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3380s)]
```vex
// f@lmn is a point attribute controlling per-point noise frequency.
// Discrete angles (multiples of PI/2 = 90 deg) stored as quaternions in @orient.
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a   = noise(@P * f@lmn);       // f@lmn = float "lmn" attribute for per-point freq
axis *= trunc(@a * 4) * $PI / 2;

@orient = quaternion(axis);
```

### Visualizing Noise with Quaternion Rotation [[Ep7, 61:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3664s)]
```vex
// chramp remaps noise distribution; trunc reduces to discrete steps.
// trunc(@a / 4) * PI -- note dividing by 4, not multiplying -- fewer steps.
vector axis;
axis = chv('axis');
axis = normalize(axis);
@a   = noise(@ptnum);              // per-point noise using integer ptnum
@a   = chramp('noise_remap', @a);  // artistic ramp control
axis *= trunc(@a / 4) * (PI);
@orient = quaternion(axis);
```

### Visualizing Data with Height and Orientation [[Ep7, 62:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3750s)]
```vex
// Drive both @P.y and @orient from the same noise value for visual data inspection.
// Points jump to discrete height levels set by trunc() thresholds.
// Second block shows a separate N + up -> orient pattern using frame-based up vector.
vector axis;
axis = chv('a');
axis = normalize(axis);
axis = noise(@ptnum);              // reuse noise as axis direction
@a   = chramp('noise_remap', @a);
axis *= trunc(@a * 4) * (PI / 2);
@P.y = @a;                         // lift point height to match noise value

@orient = quaternion(axis);

// Separate example: oscillating up vector drives orientation over time
@N  = {0, 1, 0};
float a = sin($F * 0.1);
float c = cos($F * 0.1);
@up = set(a, 0, c);                // rotating up vector in XZ plane
@orient = quaternion(maketransform(@N, @up));
```

### Curl Noise with Vector Offset [[Ep8, 90:28](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=5428s)]
```vex
// Offset point positions using curl noise for divergence-free flow displacement.
// @w is a point attribute (e.g., influence weight); scale by 0.2 to reduce magnitude.
// Adding {0,1,0} to @P shifts the noise lookup vertically to break horizontal symmetry.
// Third argument (0, 0) = roughness and attenuation overrides.
vector pos = chv('pos');
@P += pos * curlnoise((@P + {0, 1, 0}) * (@w * 0.2) * @Time, 0, 0);
```

## Common Mistakes

```vex
// WRONG: noise() output is NOT uniform -- it clusters around 0.4-0.6.
// Always use fit() or chramp() before feeding noise into trunc() for discrete steps.
// BAD -- most values will map to the same step:
@a = noise(@P);
axis *= trunc(@a * 4) * PI / 2;

// GOOD -- expand the range first:
@a = fit(noise(@P), 0.4, 0.6, 0, 1);
axis *= trunc(@a * 4) * PI / 2;

// WRONG: curlnoise returns a vector, not a float.
// Assigning directly to a float attribute truncates to the first component.
// EXPLICIT is better -- access .x / .r / [0] deliberately:
float val = curlnoise(@P).x;  // intentional scalar extraction

// WRONG: @Time vs @time (case matters in VEX).
// @Time = current time in seconds (float, same as $T).
// @time = same but lowercase -- both exist; be consistent.

// WRONG: rand(@primnum) on a point wrangle runs over points, not primitives.
// Use the correct iteration context for the wrangle type (points/prims/etc.).

// NOTE: curlnoise(@P * scale * @Time) -- multiplication order matters.
// @P * scale * @Time is NOT the same as @P * (scale + @Time).
// Use + @Time to add a time offset; use * @Time to scale position by time.
```

## See Also
- **VEX Common Patterns** (`vex_patterns.md`) -- noise displacement patterns
- **VEX Functions Reference** (`vex_functions.md`) -- noise function signatures
