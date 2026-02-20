# VEX Corpus: Color Operations

> 79 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference, vex-corpus-blueprints

## Beginner (43 examples)

### Customise the UI elements

```vex
v@colour1 = chv('col1');
v@colour2 = chv('col2');
v@colour3 = chv('col3');
v@colour4 = chv('col4');
// The plug button scans for channel references and creates the default type with a default value.
```


### Get values from other points, other geo

```vex
// Read colour from point 5 on input 0
float otherCd = point(0, "Cd", 5);

// Read colour of current point
// @Cd
// Groundwork for attribute lookups across inputs.
```


### Colour from normals and position

```vex
// Assign normal vector directly to colour
@Cd = @N;

// Assign world position as colour
@Cd = @P;

// Assign single position component (float -> all channels)
@Cd = @P.x;

// Assign single normal component
@Cd = @N.y;
// One of the easiest things to do in VEX: set colour based on vector attributes.
```


### Attribute components

```vex
// Access .x / .y / .z sub-components with dot notation
@Cd = @P.x;
@Cd = @P.y;
@Cd = @P.z;

@Cd = @N.x;
@Cd = @N.y;
@Cd = @N.z;
// Vectors can be assigned to colour directly, or individual components can be accessed with dot notation.
```


### More on code style

```vex
// Verbose form
foo = foo * 5;

// Shorthand (C-style compound assignment)
foo *= 5;
foo += 2;
foo -= 1;
foo /= 4;
// C-style compound assignment operators are available in VEX.
```


### Joy of Vex Day 5 — modulo

```vex
// Modulo creates repeating integer patterns
@P.y = @ptnum % 5;

// Applied to colour channels
@Cd.r = @ptnum % 5;
@Cd.r = @Time % 0.7;
// Modulo (%) gives the remainder after division, creating repeating patterns across points.
```


### Position to Color Mapping

```vex
// Full vector: XYZ position maps to RGB
@Cd = @P;

// Single component: same float broadcast to all channels
@Cd = @P.x;
// Maps position coordinates directly to colour channels.
```


### Position vs Normal-Based Color

```vex
// Normal direction as colour
@Cd = @N;

// World position as colour
@Cd = @P;

// Single components
@Cd = @P.x;
@Cd = @N.y;
// Normal-based colour visualises surface orientation; position-based colour visualises world-space location.
```


### Single Component Math Operations

```vex
// Shift the zero-point by adding an offset
@Cd = @P.x + 3;

// Subtract to centre, then scale to 0-1 range
@Cd = (@P.x - 6) * 0.1;

// Larger scale with different offset
@Cd = (@P.x - 6) * 0.3;
// Arithmetic on position components controls the range and centre of a colour gradient.
```


### Component-wise color assignment

```vex
// Assign each RGB channel independently
@Cd.x = (@P.x - 3) * 1.2;
@Cd.y = @P.z + 2;
@Cd.z = @P.y;

// Map different position axes to each channel
@Cd.x = @P.x * 1.2;
@Cd.y = @P.z * 2;
@Cd.z = @P.y;
// Each RGB channel can be driven by a different attribute component.
```


### Point Number Color Assignment

```vex
// Direct assignment (raw point number — usually 0-899, mostly white)
@Cd = @ptnum;

// Normalise by dividing by total point count
@Cd = @ptnum / @numpt;
// Raw point numbers exceed the 0-1 colour range; divide by `@numpt` to normalise.
```


### Normalizing Values with fit()

```vex
// Remap position Y from world range (-1,1) to colour range (0,1)
@Cd = fit(@P.y, -1, 1, 0, 1);

// fit() signature: fit(value, srcmin, srcmax, dstmin, dstmax)
// Works on floats and vectors
float remapped = fit(@P.x, -5, 5, 0, 1);
vector remappedVec = fit(@P, {-5,-5,-5}, {5,5,5}, {0,0,0}, {1,1,1});
// `fit()` normalises values from one range to another without clamping.
```


### Color from Normal Y Component

```vex
// Upward-facing surfaces bright, downward dark
@Cd = @N.y;

// Invert: downward-facing surfaces bright
@Cd = -@N.y;
// The Y component of the normal vector makes a simple top-lit shading effect.
```


### Dot Product Lighting

```vex
// Dot product with up vector {0,1,0} = simple diffuse shading
@Cd = dot(@N, {0, 1, 0});

// Negate for inverted lighting
@Cd = -dot(@N, {0, 1, 0});
// Dot product between normal and a light direction vector produces a diffuse shading mask.
```


### Bounding Box Color Thresholding

```vex
// Get normalised bounding box coordinates (0-1 range)
vector bbox = relpointbbox(0, @P);

// Colour by vertical position in bounding box
@Cd = {1, 0, 0};           // default: red
if (bbox.y < 0.5) {
    @Cd = {0, 1, 0};        // lower half: green
}
// `relpointbbox()` returns normalised (0-1) coordinates within the geometry bounding box.
```


### Dot Product for Conditional Coloring

```vex
// Compare normal against up vector
float d = dot(@N, {0, 1, 0});

// Default colour
@Cd = {1, 0, 0};

// Override when facing up
if (d > 0.3) {
    @Cd = {1, 1, 1};
}
// Using the dot product result in a conditional allows selective colouring by surface orientation.
```


### Handling Negative Color Values

```vex
// Normals contain negative values — clamp or handle them
@Cd = @N;
if (min(@Cd) < 0) {
    @Cd = 0.1;
}

// Alternative: remap normals from (-1,1) to (0,1)
@Cd = (@N + 1) * 0.5;
// Negative colour values are clamped at display time but can cause unexpected results; remap normals to 0-1.
```


### Conditional Color Assignment

```vex
// Set colour from normal Z, then conditionally override
@Cd = @N.z;
if (sin(@Cd.x) > 0) {
    @Cd = 0.1;
}
// Conditional statements allow selective colour overrides based on computed values.
```


### Reading Second Input Attributes

```vex
// Read position and colour from input 1 using @opinput1_ prefix
vector p1  = @opinput1_P;
vector cd1 = @opinput1_Cd;

// Apply them to the current point
@P  = p1;
@Cd = cd1;
// The `@opinput1_` prefix reads attributes from the second input of a wrangle node.
```


## Intermediate (32 examples)

### Get existing attribute values

```vex
// Copy position attribute into a custom vector attribute
v@myvector = @P;

// Copy from another point on input 1
@P = point(1, 'P', @ptnum);
// The `@` symbol reads attributes as well as writes them.
```


### Multiple tests, other tests

```vex
// Nested if statements
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1, 0, 0};
    }
}

// Equivalent using && (AND)
if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1, 0, 0};
}

// OR operator
if (@P.x < -2 || @P.x > 2) {
    @Cd = {0, 0, 1};
}
// Conditional logic can be combined with `&&` (AND) and `||` (OR).
```


### Floating Point Comparison and Multiple Conditionals

```vex
// Never compare floats with ==; use epsilon test
float foo = 0.1 + 0.2;
float bar = 0.3;
if (abs(foo - bar) < 0.00001) {
    @Cd = {1, 0, 0};
}

// Nested conditional
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1, 0, 0};
    }
}
// Floating-point values should be compared with an epsilon tolerance, not equality.
```


### Dot Product for Color Masking

```vex
// Simple up-vector mask
@Cd = dot(@N, {0, 1, 0});

// Mask against position of point 0 from input 1
vector pos = point(1, "P", 0);
@Cd = dot(@N, pos);

// Normalise the direction before the dot product
pos = normalize(pos);
@Cd = dot(@N, pos);
// Normalising the direction vector before the dot product keeps results in the -1 to 1 range.
```


### Channel Operator Input Syntax

```vex
// Read position and colour from a Channel Operator input
vector p1  = OWInput1.P1;
vector cd1 = OWInput1.Cd;

@P  = p1;
@Cd = cd1;
// Demonstrates reading attributes from a Channel Operator input using the OWInput syntax.
```


### Matrix Translation Component Visualization

```vex
// Visualise matrix components by setting P and Cd directly
@P.x = @id == 1;
@P.y = 0.0;
@P.z = 0.5;

@Cd.x = 1;
@Cd.y = 0.0;
@Cd.z = 0.0;
@Cd.w = 1.0;
// Demonstrates setting point position and colour attributes to visualise matrix components.
```


### XYZ Distance with Prim UV Sampling

```vex
// Declare output attributes
i@primid;
v@uv;
f@dist;

// Find closest primitive on input 1
@dist = xyzdist(1, @P, @primid, @uv);

// Sample position and colour at that surface location
vector gp = primuv(1, 'P',  @primid, @uv);
@Cd       = primuv(1, 'Cd', @primid, @uv);
// `xyzdist()` finds the nearest point on geometry and returns distance, primitive ID, and UV coordinates.
```


### Transferring Attributes with primuv

```vex
// Declare scratch attributes
i@primid;
v@uv;
f@dist;

// Find closest primitive on input 1
@dist = xyzdist(1, @P, @primid, @uv);

// Snap position to surface and transfer colour
@P  = primuv(1, 'P',  @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
// `primuv()` samples any attribute at a parametric UV position on a primitive surface.
```


### Sample Color with primuv

```vex
int    @primid;
vector @uv;
float  @dist;

// Nearest primitive lookup
@dist = xyzdist(1, @P, @primid, @uv);

// Transfer both position and colour from the closest surface point
@P  = primuv(1, 'P',  @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
// After `xyzdist()` finds the closest point, `primuv()` samples both position and colour at that location.
```


### Reading Primitive Color with primuv

```vex
i@primId;
v@uv;
f@dist;

// Nearest surface lookup
@dist = xyzdist(1, @P, @primId, @uv);

// Read position and colour from that surface location
@P  = primuv(1, 'P',  @primId, @uv);
@Cd = primuv(1, 'Cd', @primId, @uv);
// Uses `xyzdist()` to find the closest primitive on input 1 and stores the primitive ID and UV coordinates.
```


### Proximity Attribute Sampling

```vex
// Find closest point on a primitive surface
@dist = xyzdist(1, @P, @ptid, @uv);

// Sample position and colour at that UV location
v@c  = primuv(1, "P",  @ptid, @uv);
@Cd  = primuv(1, "Cd", @ptid, @uv);
// Combines `xyzdist()` and `primuv()` for proximity-based attribute transfer.
```


### create_cdf

```vex
// Iterate over all lights, sampling their power
int[] li = getlights();
float values[];
resize(values, len(li));

int nsamples = 256;
int sid = israytrace ? SID : newsampler();

vector s, pos, clr;
float scale;

for (int i = 0; i < len(li); i++) {
    for (int j = 0; j < nsamples; j++) {
        nextsample(sid, s.x, s.y, "mode", "nextpixel");
        sample_light(li[i], P, s, Time, pos, clr, scale);
        values[i] += luminance(clr);
    }
    values[i] /= nsamples;
}

// Create a CDF of the power distribution
float cdf[] = create_cdf(values);

// Randomly select a light based on power distribution
nextsample(sid, s.x, s.y, "mode", "nextpixel");
int index = 0;
sample_cdf(cdf, s.x, index);

// Use the selected light: li[index]
// `create_cdf()` builds a cumulative distribution function for importance sampling lights by power.
```


### file_stat

```vex
#include <file.h>

// Default to red; turn green if file exists and is valid
v@Cd = {1, 0, 0};
file_stat s = file_stat("$HH/pic/Mandril.pic");
if (s->isValid()) {
    v@Cd = {0, 1, 0};
}
// `file_stat()` queries filesystem information for a given file path.
```


### illuminance

```vex
// Iterate over light sources illuminating point P
illuminance(P, N, M_PI / 2) {
    // Cl = light colour, L = direction to light (unnormalised)
    // Force shadow shader evaluation:
    // shadow(Cl);

    vector ldir = normalize(L);
    float  ndotl = dot(N, ldir);
    Cf += Cl * ndotl;
}
// `illuminance()` loops over lights that contribute to a surface point within the given cone angle.
```


### specularBRDF

```vex
// Combined specular + diffuse shading
vector nn = normalize(frontface(N, I));
vector ii = normalize(-I);

Cf = 0;
illuminance(P, nn) {
    vector ll = normalize(L);
    Cf += Cl * (specularBRDF(ll, nn, ii, rough) + diffuseBRDF(ll, nn));
}
// `specularBRDF()` and `diffuseBRDF()` compute physically-based BRDF contributions per light.
```


### split_bsdf

```vex
// Split BSDF into component lobes
float weights[];
bsdf  lobes[];
split_bsdf(lobes, hitF, weights);

// Get albedos of lobes
float albedos[];
resize(albedos, len(lobes));
for (int i = 0; i < len(lobes); i++) {
    albedos[i] = luminance(albedo(lobes[i], -hitnI)) * weights[i];
}

// Compute CDF for importance sampling
float cdf[] = compute_cdf(albedos);

// Randomly select a BSDF lobe based on albedo distribution
int index = 0;
sample_cdf(cdf, s.x, index);

// Use the selected lobe: lobes[index]
// `split_bsdf()` decomposes a BSDF into individual lobes for importance sampling in ray-tracing shaders.
```


### Attribute Syntax

```vex
// Reading attributes (@ prefix)
vector pos   = @P;          // Built-in position
float  scale = @pscale;     // Custom float attribute
int    id    = @id;         // Custom integer attribute

// Writing attributes
@Cd = {1, 0, 0};            // Set colour to red
@N  = normalize(@N);        // Modify normal in-place

// Typed attribute declarations (explicit type prefix)
v@myVec   = {0, 1, 0};     // vector
f@myFloat = 0.5;            // float
i@myInt   = 3;              // int
s@myStr   = "hello";        // string
// The `@` prefix reads and writes geometry attributes. Typed prefixes (`v@`, `f@`, `i@`) declare the attribute type.
```


## Advanced (3 examples)

### Random colour groups with vex

```vex
// Assign a random colour to each primitive group
string groups[] = detailintrinsic(0, 'primitivegroups');

foreach (string g; groups) {
    if (inprimgroup(0, g, @primnum) == 1) {
        @Cd = rand(random_shash(g));
    }
}
// `detailintrinsic()` lists all primitive groups; `random_shash()` hashes a string to a seed for `rand()`.
```


### xyzdist to get info about the closest prim to a position

```vex
// Declare output variables
float  distance;
int    myprim;
vector myuv;

// Find closest primitive on input 1
distance = xyzdist(1, @P, myprim, myuv);

// Sample any attribute at that location
@Cd = primuv(1, 'Cd', myprim, myuv);
@P  = primuv(1, 'P',  myprim, myuv);
// `xyzdist()` is similar to the Ray SOP — it finds the nearest surface point and returns parametric coordinates.
```


### xyzdist full workflow

```vex
// Declare scratch attributes on the geometry
i@primid;
v@uv;
f@dist;

// Find the nearest primitive on input 1
@dist = xyzdist(1, @P, @primid, @uv);

// Snap to surface and read colour
@P  = primuv(1, 'P',  @primid, @uv);
@Cd = primuv(1, 'Cd', @primid, @uv);
// `minpos()` gives the closest `@P` on geometry; `xyzdist()` additionally returns the primitive ID and UV for full attribute sampling.
```


## Expert (1 examples)

### Dot Product with Normal and Up Vector

```vex
// Dot product between surface normal and world up vector
// Result: 1.0 = facing up, 0.0 = perpendicular, -1.0 = facing down
@Cd = dot(@N, {0, 1, 0});

// Useful variants:
// Clamp negative values to 0 (only lit from above)
@Cd = max(0.0, dot(@N, {0, 1, 0}));

// Remap from (-1,1) to (0,1) for full range visualisation
@Cd = dot(@N, {0, 1, 0}) * 0.5 + 0.5;
// Uses the dot product between the surface normal (`@N`) and an up vector to generate a directional shading mask.
```

