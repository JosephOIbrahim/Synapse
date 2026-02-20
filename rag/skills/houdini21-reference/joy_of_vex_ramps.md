# Joy of VEX: Ramps & Parameters

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Quick Reference
```vex
chv('scalevec');          // Vector channel reference — returns vector3 from UI
@N = chf('scale');        // Float channel reference — assigns scalar to normal
vector uv = chv("uv");    // Declare vector variable from channel parameter
```

## Parameter Controls

### Channel references — ch(), chf(), chv() [[Ep1, 40:20](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2420s)]
```vex
// Replace hardcoded numbers with ch() to get interactive UI sliders.
// ch() auto-creates a spare parameter when you click "Create Parameters".

@Cd = float(@ptnum) / 100;           // hardcoded — no UI control

@Cd = float(@ptnum) / ch('scale');   // ch() reads a float parameter named 'scale'
                                     // quotes denote strings; auto-create via wrangle UI

@Cd = float(@ptnum) / ch();          // empty name — Houdini prompts to name it
```

### Using variables to store intermediate results [[Ep1, 50:02](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=3002s)]
```vex
// Store intermediate calculations in variables for readability and debugging.
// Progression: inline -> extracted variable -> parameterized.

@Cd = sin(@ptnum);                           // step 1: raw ptnum

@Cd = sin(float(@ptnum) / 100);             // step 2: cast + normalize

@Cd = sin(float(@ptnum) * ch('scale'));     // step 3: ch() replaces hardcoded 100

float foo = float(@ptnum) / ch('scale');    // step 4: extract to named variable
@Cd = sin(foo);                             // cleaner; easier to debug
```

### Scaling distance with channel reference [[Ep1, 72:54](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4374s)]
```vex
// Prefer multiplication over division (avoids divide-by-zero).
float d = length(@P);       // distance from origin
d *= ch('scale');           // multiply preferred over divide — no div-by-zero risk
@Cd = (sin(d) + 1) * 0.5;  // normalize sine to 0..1 range for color
```

### Vector channel parameter for interactive center point [[Ep1, 80:02](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=4802s)]
```vex
// chv() creates a 3-component vector parameter in the UI.
// Replaces hardcoded positions like {3,0,3} or {1,0,1}.

vector center = chv('center');    // interactive center point — drag in viewport
float d = distance(@P, center);
d *= ch('scale');
@Cd = (sin(d) + 1) * 0.5;
```

### Radial ring pattern — fully parameterized [[Ep1, 84:50](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5090s)]
```vex
// Complete parameterized radial ring generator.
// fancyscale: squish rings independently per axis (set default to {1,1,1})
// center:     move the ring origin interactively
// scale:      control ring frequency / spacing

vector pos    = @P * chv('fancyscale');    // per-axis position scale
vector center = chv('center');             // movable center point
float d       = distance(pos, center);
d            *= ch('scale');               // ring spacing / frequency
@Cd           = (sin(d) + 1) * 0.5;       // normalized color
```

### Storing distance as custom attribute [[Ep1, 85:54](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5154s)]
```vex
// f@ prefix writes a float point attribute — useful for debugging in spreadsheet.
vector pos    = @P * chv('fancyscale');
vector center = chv('center');
f@distance    = distance(pos, center);    // store as attribute for inspection
@distance    *= ch('scaling');
@Cd           = (sin(@distance) + 1) * 0.5;
```

### Explicit type: chf() vs ch() [[Ep1, 87:00](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5220s)]
```vex
// chf() is the explicit float version of ch() — preferred for clarity.
// chv() creates a vector parameter; chf()/ch() creates a float parameter.
// To change a parameter type (e.g., float -> vector): delete the spare parm and recreate.

vector pos    = @P + chv('fancyscale');
vector center = chv('center');
float d       = distance(pos, center);
d            *= chf('scale');             // chf() == ch() but self-documents type
@Cd           = (sin(d) + 1) * 0.5;
```

### Vector subtraction + length for distance [[Ep1, 88:12](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5292s)]
```vex
// Alternative to distance(): explicit vector delta then length().
// Useful when you need the direction vector (delta) for other purposes.

vector pos    = @P * chv('fancyscale');
vector center = chv('center');
vector delta  = pos - center;             // direction + magnitude
float d       = length(delta);            // extract scalar distance
d            *= ch('scalePos');
@Cd           = sin(d * 3) * 0.5;
```

### Animated sine wave with @Frame [[Ep1, 99:38](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=5978s)]
```vex
// Multiply distance by @Frame to animate ring movement over time.
// fit() replaces the manual (sin+1)*0.5 normalization.

vector pos    = @P * chv('fancyscale');
vector center = chv('center');
float d       = distance(pos, center);
@Cd           = fit(sin(d * @Frame), -1, 1, 0, 1);  // animated color rings
```

### Channel parameters with clamp [[Ep2, 100:12](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=6012s)]
```vex
// clamp() restricts output to a hard min/max range.
// Useful for preventing runaway values; compare with fit() which rescales.

float d = length(@P);
d       = ch('pre_scale');                  // override d with pre_scale slider
d       = clamp(d, ch('post_scale'), d);    // clamp: min=post_scale, max=d
d      += ch('post_scale');
@Cd     = d;
```

### Fitting all four bounds via channels [[Ep2, 29:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1742s)]
```vex
// Expose ALL four fit() args as channels for full interactive control.
// fit(value, in_min, in_max, out_min, out_max)

float d      = length(@P);
float inmin  = ch("fit_in_min");
float inmax  = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d            = fit(d, inmin, inmax, outmin, outmax);
@P.y         = d;                  // drive Y position from remapped distance
```

### Variant: drive color channel instead of position [[Ep2, 34:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2098s)]
```vex
// Same pattern as above, but targets @Cd.y (green channel) instead of @P.y.
float d      = length(@P);
float imin   = ch("fit_in_min");
float imax   = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
d            = fit(d, imin, imax, outmin, outmax);
@Cd.y        = d;
```

### Vector addition for normal / position offset [[Ep4, 30:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=1812s)]
```vex
// Add a vector channel parameter to @N or @P for interactive offset.
// += compound assignment: a += b  is shorthand for  a = a + b

vector a = chv('a');
vector b = chv('b');
@N = a + b;                // visualize sum of two UI vectors as normals

// Offset position (e.g., pre-sim velocity nudge):
@P += chv('offset');

// Add to existing normals:
@N += chv('a');
```

### Setting normals with scalar channel [[Ep4, 40:32](https://www.youtube.com/watch?v=66WGmbykQhI&t=2432s)]
```vex
// Assign a uniform scalar to @N — useful for explosion-style outward push.
@N = chf('scale');    // all components set to same scalar; controls push magnitude
```

### Parameterized quaternion rotation [[Ep7, 103:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6208s)]
```vex
// Build quaternion from normalized position, then apply an extra angle rotation.
// radians() converts degrees from UI slider to VEX radians.

@N                = normalize(@P);
@up               = {0, 1, 0};
@orient           = quaternion(maketransform(@N, @up));        // base orientation
vector4 extrarot  = quaternion(radians(chf("angle")), {1,0,0}); // X-axis rotation
@orient           = qmultiply(@orient, extrarot);              // apply on top
```

### Euler angles to quaternion [[Ep7, 71:38](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4298s)]
```vex
// chv() exposes 3 rotation sliders (degrees); convert to radians before use.
vector rot = radians(chv('euler'));          // degrees -> radians
@orient    = eulertoquaternion(rot, 0);     // 0 = XYZ rotation order
```

### Setting pscale from channel [[Ep6, 16:14](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=974s)]
```vex
// @pscale controls the size of copied/instanced geometry on each point.
@pscale = ch('pscale');    // uniform scale slider; prevents overlaps on dense grids
```

---

## chramp Usage

### Basic chramp — distance to ramp lookup [[Ep2, 45:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2726s)]
```vex
// chramp(param_name, value) — samples a ramp UI parameter at a given 0..1 value.
// The ramp output drives @P.y (height displacement).
// Scale 'd' so it stays in 0..1 range before passing to chramp.

float d  = length(@P);          // distance from origin (raw, unbounded)
d       *= ch('scale');         // bring into ~0..1 range
@P.y     = chramp('myramp', d); // ramp controls height profile
```

### chramp with height multiplier [[Ep2, 46:20](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2780s)]
```vex
// Add a separate height multiplier so scale and amplitude are independent.
float d  = length(@P);
d       *= ch("scale");             // controls ramp lookup position (frequency)
@P.y     = chramp("myRamp", d);
@P.y    *= ch("height");            // controls overall displacement amplitude
```

### chramp with time animation [[Ep2, 50:20](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3020s)]
```vex
// Add @Time to the lookup value to animate the ramp pattern over time.
// NOTE: In recent Houdini versions chramp() does NOT auto-modulo values > 1.
// Values outside 0..1 will not repeat the ramp — use fmod(d,1) if you need tiling.

float d  = length(@P);
d       *= ch('scale');
d       += @Time;                   // shifts lookup position each frame -> animation
@P.y     = chramp('my-ramp', d);
@P.y    *= ch('height');
```

### Normalize with sine + fit before ramp lookup [[Ep2, 50:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3026s)]
```vex
// chramp() expects 0..1 input. sin() outputs -1..1, so use fit() to normalize.
// abs() ensures the value is non-negative before sine modulation.

float d  = length(@P);
d       *= ch("scale");
d        = abs(d);                    // ensure non-negative
d        = sin(d);                    // -1..1 oscillation
d        = fit(d, -1, 1, 0, 1);      // normalize to 0..1 for ramp input
@P.y     = chramp("my-ramp", d);
@P.y    *= ch("height");
```

### fit() before ramp — the canonical pattern [[Ep2, 58:42](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3522s)]
```vex
// Standard pipeline: distance -> scale -> sin -> fit(-1,1,0,1) -> chramp -> height
// fit(-1,1,0,1) is the standard bridge between sine output and ramp input.

float d  = length(@P);
d       *= ch('scale');
d        = sin(d);
d        = fit(d, -1, 1, 0, 1);   // required: remap sine to valid ramp range
@P.y     = chramp('my-ramp', d);
@P.y    *= ch('height');
```

### Ramp driving both height and color [[Ep2, 62:50](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3770s)]
```vex
// Same ramp lookup can drive multiple attributes simultaneously.
float d  = length(@P);
d       *= ch('scale');
d       += sin(d);                  // adds self-interference ripple
d        = fit(d, 1, 3, 0, 1);     // note: custom fit range — adjust per mesh size
@P.y     = chramp('myRamp', d);    // height displacement
@Cd.y    = chramp('myRamp', d);    // same ramp controls green channel
@Cd.y   *= ch('height');
```

### Double-sine for tighter wave detail [[Ep2, 64:32](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3872s)]
```vex
// Apply sin() twice to compress and concentrate wave energy near peaks.
float d  = length(@P);
d       *= ch('scale');
d        = sin(d);
d        = sin(d);                  // second sin: creates sharper wave peaks
d        = fit(d, -1, 1, 0, 1);
@P.y     = chramp('myramp', d);
@P.y    *= ch('height');
```

### Simple 1D ramp — X position drives lookup [[Ep2, 65:02](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3902s)]
```vex
// Use X position directly as ramp input for a linear left-to-right gradient.
// Works when @P.x is already in 0..1 range (e.g., normalized grid).
f@y     = chramp('mymap', @P.x);
@P.y   *= ch('height');
```

### Ramp with compound assignment and color [[Ep2, 69:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4188s)]
```vex
// += and *= are compound assignment operators: d += x  means  d = d + x
float d  = length(@P);
d       *= ch('scale');
d       += @Time;                     // animate lookup position
@P.y     = chramp('my_ramp', d);
@Cd      = chramp('height', d);       // ramp can also drive color attribute directly
```

### Stepped quantization with ramp [[Ep2, 91:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5518s)]
```vex
// Stepped ramp creates discrete height levels (terraced/staircase effect).
// trunc() floors to integer — combined with stepped ramp gives hard steps.

float d  = length(@P);
v@Cd     = set(d);                        // debug: visualize raw distance as color
d        = chramp('my_stepped_ramp', d);  // stepped ramp preset in UI
d       *= d;                             // square to exaggerate level separation
d        = trunc(d);                      // snap to integer steps
@P.y     = d;
```

### Pre-scale / post-scale pattern for ramps [[Ep2, 97:50](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5870s)]
```vex
// Pre-scale: controls which region of the ramp is sampled (input frequency).
// Post-scale: controls the overall displacement amplitude (output gain).
// Separating them gives independent frequency and amplitude control.

float d  = length(@P);
d       *= ch("pre_scale");               // pre-scale: adjust ramp input range
d        = chramp("my_stepped_ramp", d); // stepped ramp for terraced output
d       *= ch("post_scale");             // post-scale: adjust output amplitude
@P.y     = d;
```

### Distance-based Y displacement with two scale channels [[Ep2, 99:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5986s)]
```vex
// Two channels accumulate: if geometry is pre-scaled, unexpected results can occur.
// Debug by commenting out one channel at a time to isolate the issue.

float d  = length(@P);
d       *= ch('scale');
float f  = ch('factor');    // second scale factor — both multiply; watch for drift
d       *= f;
d        = fit(d, 0, 1, 0, 1);  // identity fit here; adjust ranges to taste
@P.y     = d;
```

### Ramp controlling chramp subtraction [[Ep2, 101:34](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=6094s)]
```vex
// Subtract the ramp output from the scaled distance before applying to position.
// Creates an inverted or carved displacement relative to the ramp profile.

float d  = length(@P);
d        = ch('pre_scale');               // override with slider
d       -= chramp('my_stepped_ramp', d); // subtract ramp value from d
d       *= ch('post_scale');
@P.y     = d;
```

### Using chramp with relpointbbox [[Ep4, 55:04](https://www.youtube.com/watch?v=66WGmbykQhI&t=3304s)]
```vex
// relpointbbox() returns 0..1 position within the bounding box — perfect ramp input.
// bbox.y == 0 at bottom, 1 at top. Use it directly without fit().

vector bbox = relpointbbox(0, @P);
@Cd         = bbox;                        // debug: visualize bbox coords as color

// Progressive refinement:
@P += @N * bbox.y * ch('scale');          // linear displacement along normals

// With ramp for custom falloff profile:
float i  = chramp('inflate', bbox.y);     // bbox.y already 0..1 — no fit needed
@P      += @N * i * ch('scale');          // bulge or custom deformation shape
```

### Color ramp via vector() cast [[Ep6, 34:02](https://www.youtube.com/watch?v=yPaWl3AiSrc&t=2042s)]
```vex
// chramp() returns a float. Cast to vector() to get a color ramp (RGB) parameter.
// Two fit() calls: first maps sine to scale range, second normalizes for ramp input.

float d   = ch('frequency');
float mn  = ch('min');
float mx  = ch('max');
d         = fit(sin(d), -1, 1, mn, mx);  // map sine to custom min/max for scale
@scale    = fit(sin(d), mn, mx, 0, 1);   // renormalize to 0..1 for ramp input
@P.y     -= d / 2;
d         = fit(@scale, mn, mx, 0, 1);
@Cd       = vector(chramp('color', d));  // vector() cast: float ramp -> color ramp UI
```

### Noise remapped through ramp (interactive) [[Ep7, 56:44](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3404s)]
```vex
// Replace fit() with chramp() to get an interactive curve for noise remapping.
// The ramp x-axis position drives the lookup; the ramp output controls rotation.

vector axis;
axis         = chv('axis');
axis         = normalize(axis);
@a           = noise(@P * f@time);
@a           = chramp('noise_rerange', @a);  // interactive: drag ramp points in UI
axis        *= trunc(@a * 4) * $PI / 2;      // snap to 4 discrete rotation steps
@orient      = quaternion(axis);
```

### fit() vs chramp() for noise remapping — side by side [[Ep7, 57:18](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=3438s)]
```vex
// Version A: fixed fit range — fast but no interactive control
vector axis = normalize(chv('axis'));
@a          = noise(@P + @Time);
@a          = fit(@a, 0.4, 0.6, 0, 1);      // hardcoded input range
axis        = trunc(@a * 4) * $PI / 2;
@orient     = quaternion(axis);

// Version B: chramp — interactive ramp curve replaces fit()
vector axis = normalize(chv('axis'));
@a          = noise(@P + @Time);
@a          = chramp('noise_rerange', @a);   // drag ramp points for custom falloff
axis        = trunc(@a * 4) * $PI / 2;
@orient     = quaternion(axis);
```

### Quaternion slerp — three blend control methods [[Ep7, 78:00](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4680s)]
```vex
vector4 a = {0, 0, 0, 1};                         // identity quaternion
vector4 b = quaternion({0,1,0} * $PI / 2);         // 90-degree Y-axis rotation

// Method 1: direct channel slider
@orient = slerp(a, b, ch('blend'));                 // simple slider 0..1

// Method 2: @Time drives blend directly
float blend = @Time;
@orient     = slerp(a, b, blend);                  // linear auto-blend over time

// Method 3: chramp shapes the blend curve (ease-in/out, snap, etc.)
float blend2 = chramp('myramp', @Time);            // custom easing via ramp curve
@orient      = slerp(a, b, blend2);
```

### Quaternion slerp with time-modulo ramp [[Ep7, 78:24](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=4704s)]
```vex
// @Time % 1 cycles 0..1 each second — drives repeating ramp-controlled rotation.
// Ramp shape controls easing: S-curve = ease-in/out, step = snap, etc.

vector4 a     = {0, 0, 0, 1};
vector4 b     = quaternion({0,1,0} * $F / 2);
float blend   = chramp('blendramp', @Time % 1);  // cyclic ramp lookup
@orient       = slerp(a, b, blend);
```

### Wave frequency and radius parameters [[Ep5, 66:30](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=3990s)]
```vex
// nearpoints() finds all points within radius; chi() reads an integer channel.
// High frequencies can alias visually — reduce ch('freq') or increase radius.

int   pts[];
int   pt;
float d, w;

pts    = nearpoints(1, @P, ch('radius'), chi('num_of_points'));
pt     = pts[0];
@Cd    = point(1, 'P', pt);                // debug: colorize by nearest-point position
d      = distance(@P, point(1, 'P', pt));
w      = ch('freq');
w      = sin(w);
w      = ch('amp');
@P.y  += w;
```

### Per-point ripple with nearpoints loop [[Ep5, 89:12](https://www.youtube.com/watch?v=qPwiuQUT-N4&t=5352s)]
```vex
// When increasing grid size (e.g., 10x10 -> 50x50), scale radius and freq accordingly.
// fit() normalizes distance to 0..1 relative to ch('radius') — avoids hard cutoffs.

int pts[] = nearpoints(1, @P, 40);

foreach (int pt; pts) {
    vector pos = point(1, 'P', pt);
    float d    = distance(@P, pos);
    d          = fit(d, 0, ch('radius'), 1, 0);  // 1 at center, 0 at edge
    d          = clamp(d, 0, 1);                  // guard against outside-radius pts
    float t    = @Time * ch('speed');
    t         += rand(pt);                         // per-point phase offset -> organic feel
    float a    = d * ch('amp');
    float f    = d * ch('freq');
    @P.y      += sin(f * t) * a;
}
```

### Declaring UV vector parameter [[Ep8, 26:06](https://www.youtube.com/watch?v=KJUZD4PTyz0&t=1566s)]
```vex
// chv() creates a vector parameter in the UI for specifying UV coordinates.
// Use with primuv() to sample positions from input geometry by UV.
vector uv = chv("uv");    // exposes 3-component slider in wrangle UI
```

---

## Common Mistakes

```vex
// MISTAKE 1: Passing chramp values outside 0..1
// chramp() does NOT auto-modulo in recent Houdini versions.
// BAD: d may grow unbounded, ramp only evaluates correctly in 0..1
float d = length(@P) * ch('scale');
@P.y    = chramp('myramp', d);            // d could be > 1 -> ramp clamps flat

// GOOD: normalize first
d = fmod(d, 1.0);                         // tile the ramp by wrapping to 0..1
@P.y = chramp('myramp', d);

// Or use fit() to map a known range to 0..1:
d = fit(d, 0, 5, 0, 1);                  // if you know d stays in 0..5
@P.y = chramp('myramp', d);

// MISTAKE 2: Trying to change a spare parameter type without deleting it first
// If 'scale' already exists as a float, chv('scale') won't update it to vector.
// FIX: delete the spare parameter from the gear menu, then re-click "Create Parameters"

// MISTAKE 3: Assigning sin() output directly to chramp without normalization
// sin() returns -1..1; chramp() needs 0..1
float d = sin(length(@P) * ch('scale'));
// BAD:
@P.y = chramp('myramp', d);              // half the ramp is never sampled
// GOOD:
d    = fit(d, -1, 1, 0, 1);             // normalize before ramp lookup
@P.y = chramp('myramp', d);

// MISTAKE 4: Using distance() where length() is needed
// distance(a, b) = length(b - a); for distance-from-origin, use length(@P)
// BAD:
// float d = distance(@P);    // compile error: distance() requires two args
// GOOD:
float d = length(@P);         // distance from origin

// MISTAKE 5: Confusing ch() and chv() parameter types
// ch() / chf() -> float (single slider)
// chv()        -> vector (3-component XYZ slider)
// chi()        -> integer
// Using ch() when you meant chv() returns only the X component silently.
vector scale = chv('scale');    // correct: full XYZ control
// vs.
float scale2 = ch('scale');    // only X — silent truncation if you expected a vector
```

## See Also
- **VEX Functions Reference** (`vex_functions.md`) -- chramp, chf function signatures
