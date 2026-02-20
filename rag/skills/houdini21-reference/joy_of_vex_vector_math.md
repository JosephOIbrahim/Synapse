# Joy of VEX: Vector Math

> Tutorial examples from The Joy of VEX video series by Matt Estela.
> Source: https://www.youtube.com/@MattEstela

## Triggers
vector math, dot product, cross product, normalize, length, distance, fit, clamp, modulo, matrix, identity matrix, quaternion, vector addition, vector subtraction, vector scaling, normal manipulation, color from position, integer division, float casting, trunc, ramp, chramp, chv, ident

## Context
VEX vector math fundamentals: arithmetic on attributes, remapping with fit/clamp, dot and cross products for directional effects, matrix operations, and normal manipulation. All examples run in Attribute Wrangle SOPs.

## Code

### Quick Reference
```vex
// --- Attribute arithmetic ---
@Cd = float(@ptnum) / @numpt;        // normalized 0..1 gradient across all points
@Cd = fit(@P.y, -1, 1, 0, 1);       // remap Y from -1..1 to 0..1
@Cd = dot(@N, {0,1,0});              // surface orientation vs up vector
@Cd = dot(@N, chv('angle'));         // interactive directional mask

// --- Distance and modulo ---
float d = length(@P);                // distance from origin
d %= 1;                              // wrap to 0..1 for cyclic patterns
@Cd.r = @Time % 1.0;                 // sawtooth color cycle per second

// --- Fit and clamp ---
d = fit(d, 0, 2, 0, 1);             // remap distance 0..2 to 0..1
d = clamp(d, 0, 1);                 // hard-clamp to valid range

// --- Vectors ---
*= ch('scale');                      // scale vector in place
matrix3 m = ident();                 // identity matrix (no rotation, no scale)
@N = cross(@N, {0,1,0});            // rotate normal 90° around Y axis
@N = normalize(@N);                 // ensure unit length after cross product
```

---

### Vector Operations

#### Color from Position Math [[Ep1, 22:28](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1348s)]
```vex
// Basic math on position/normal components to drive color
// Add, subtract, multiply scalar values to create gradients
@Cd = @N.y;           // color from normal Y component
@Cd = @P.x + 1;       // shift range upward by 1
@Cd = @P.x - 0;       // no offset (identity)
@Cd = @P.x * 0 * 0.1; // scale down position component
```

#### Single Component Math Operations [[Ep1, 22:58](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1378s)]
```vex
// Arithmetic on a single attribute component (@P.x) assigned to color
@Cd = @P.x + 1;           // offset range up by 1
@Cd = @P.x - 0;           // direct pass-through
@Cd = @P.x * 0 * 0.1;     // scale to near-zero
@Cd = (@P.x - 0) * 0.1;   // scale down — parentheses control order
```

#### Scaling and Offsetting Position for Color [[Ep1, 23:20](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1400s)]
```vex
// Progressively normalize position X into 0–1 color range
@Cd = @P.x;               // raw position as color
@Cd = @P.x - 1;           // offset
@Cd = @P.x - 0;           // no offset
@Cd = @P.x * 6 * 0.1;    // scale to fit 0–1
@Cd = (@P.x - 6) * 0.1;  // offset then scale — final normalized mapping
```

#### Arithmetic Operations on Color [[Ep1, 24:32](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=1472s)]
```vex
// Addition shifts the range; multiplication scales the gradient
// Parentheses control order when combining multiple operations
@Cd = @P.x + 3;          // shift range up by 3
@Cd = @P.x - 6;          // shift range down by 6
@Cd = @P.x * 6 * 0.1;   // scale factor applied twice
@Cd = (@P.x - 6) * 0.1; // offset first, then scale
```

#### Integer Division Pitfall [[Ep1, 33:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2036s)]
```vex
// WRONG: dividing two integers produces integer division (always 0 for ptnum < numpt)
// @ptnum and @numpt are both ints — fractional component is truncated
@Cd = @ptnum / @numpt;  // all zeros — no gradient produced
```

#### Type Casting for Integer Division [[Ep1, 35:42](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2142s)]
```vex
// FIX: cast to float first so division produces 0.0–1.0 range
@Cd = float(@ptnum) / @numpt;  // correct gradient 0 to nearly 1
@Cd = float(@ptnum) / 100;     // divide by constant instead of @numpt
```

#### Normalizing Point Numbers with Division [[Ep1, 37:56](https://www.youtube.com/watch?v=9gB1zBa9Lg4&t=2276s)]
```vex
// Standard idiom: 0-to-1 gradient across all points
// @ptnum increments per point; @numpt stays constant = smooth progression
// Replace @numpt with any constant to control where gradient reaches 1.0
@Cd = float(@ptnum) / @numpt;       // gradient 0..(N-1)/N
@Cd = float(@ptnum) / 100.0;        // gradient 0..0.99 for first 100 points
@Cd = 1.0 - float(@ptnum) / @numpt; // reversed: first point white, last black
```

---

### Remapping (fit, clamp)

#### Distance-Based Y Manipulation [[Ep2, 22:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1368s)]
```vex
// Use distance from origin to drive Y position
// Negation inverts the range; offset raises/lowers geometry
float d = length(@P);
@P.y = -d + 10;  // negate distance then offset upward by 10
```

#### Clamping Distance Values [[Ep2, 24:04](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1444s)]
```vex
// clamp(value, min, max) — constrains distance to 0..3
// Creates flat plateaus where distance would exceed bounds
float d = length(@P);
@P.y = clamp(d, 0, 3);
```

#### Clamp and Fit Functions [[Ep2, 27:18](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1638s)]
```vex
// fit(value, inMin, inMax, outMin, outMax) — remaps one range to another
// clamp() constrains without deleting geometry; fit() provides flexible remapping
float d = length(@P);
@P.y = fit(d, 0, 2, 0, 10);   // remap distance 0..2 to height 0..10
@P.y = clamp(d, 0, 1);        // or: hard-clamp to 0..1
```

#### Fit and Clamp Range Control [[Ep2, 27:58](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1678s)]
```vex
// Channel refs make fit() interactive; maps distance to 0..1 output
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
@P.y = fit(d, imin, imax, 0, 1);
```

#### Fit and Clamp Range Remapping [[Ep2, 28:00](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1680s)]
```vex
// Chain fit() then clamp() — remap range, then constrain sub-range
float d = length(@P);
float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
d = fit(d, imin, imax, 0, 1);   // remap to 0..1
d = clamp(d, 0.5, 1);           // constrain to upper half
@P.y = d;
```

#### Fit and Clamp Combination (Inverted) [[Ep2, 30:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1848s)]
```vex
// fit() with output 1..0 inverts the mapping (far=low, near=high)
// clamp() restricts to sub-range for fine control
float d = length(@P);
float lmin = ch('fit_in_min');
float lmax = ch('fit_in_max');
d = fit(d, lmin, lmax, 1, 0);  // inverted output: near maps to 1, far to 0
d = clamp(d, 0.5, 1);          // restrict to upper half
@P.y = d;
```

#### Chaining fit and clamp operations [[Ep2, 30:54](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1854s)]
```vex
// fit() inverts distance range 1..2 to 1..0, then clamp constrains result
float d = length(@P);
d = fit(d, 1, 2, 1, 0);   // remap and invert
d = clamp(d, 0.5, 1);     // constrain to subrange
@P.y = d;

float imin = ch('fit_in_min');
float imax = ch('fit_in_max');
```

#### Fit and Clamp with Channel Refs (Full) [[Ep2, 32:26](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=1946s)]
```vex
// All four fit() bounds exposed as channel references for full interactive control
float d = length(@P);
float imin   = ch('fit_in_min');
float imax   = ch('fit_in_max');
float outmin = ch('fit_out_min');
float outmax = ch('fit_out_max');
d = fit(d, imin, imax, outmin, outmax);
@P.y = d;
```

#### Remapping Values with Fit [[Ep2, 41:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=2490s)]
```vex
// fit() remaps a value from one range to another via channel-driven bounds
// Remapped result applied to Y position — foundation for ramp/curve work
float angle  = ch("fit_in_min");
float inmin  = ch("fit_in_min");
float inmax  = ch("fit_in_max");
float outmin = ch("fit_out_min");
float outmax = ch("fit_out_max");
float d = fit(angle, inmin, inmax, outmin, outmax);
@P.y = d;
```

#### Normalized Values and Fit Function [[Ep2, 66:44](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4004s)]
```vex
// Demonstrates fit() for normalizing into 0..1, plus various attribute types
s@greeting = "yessirree";
i@test     = 123;
f@scale    = ch("scale");
v@P        = @P * @test;
f@cd       = @P.y;
v@Cd       = fit(@P.y, 0, 1, 1, 0);  // normalize Y, inverted (fit returns vector here)
i@x        = 1;
@P.y       = chramp("coramp", @P.z);  // sample ramp with Z position
@P.y      *= ch("height");
```

#### Normalizing Values with fit() [[Ep2, 66:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4008s)]
```vex
// Convert Y from -1..1 to 0..1 — important for vectors like normals
// Normalized values describe direction independently of magnitude
@Cd = fit(@P.y, -1, 1, 0, 1);
```

---

### Length & Distance

#### Modulo for Cyclic Ramp Mapping [[Ep2, 51:52](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=3112s)]
```vex
// Modulo constrains distance to 0..1, creating repeating concentric bands
// chramp() samples a ramp parameter at that 0..1 value
float d = length(@P);
d *= ch('scale');          // scale distance so bands are denser/sparser
d %= 1;                    // wrap to 0..1 — creates cyclic repeat
@P.y *= chramp('myramp', d);
@P.y *= ch('height');
```

#### Modulo for Looping Values [[Ep2, 81:24](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4884s)]
```vex
// % creates looping values that repeat at regular intervals
@Cd.r   = @Time % 1;    // color loops every 1 second
@P.y    = @ptnum % 5;   // 5 repeating height levels across points

// Distance scaled and assigned directly
float d = length(@P);
d *= ch('scale');
@P.y = d;
```

#### Creating Stepped Distance Values [[Ep2, 83:16](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4996s)]
```vex
// Quantize smooth distance into discrete steps:
//   divide by factor → truncate decimals → multiply back
// Produces terraced/banded geometry instead of smooth ramp
float d = length(@P);
d *= ch("scale");
float f = ch("factor");
d /= f;          // bring into truncatable range
d = trunc(d);    // remove decimal — quantize to integer steps
d *= f;          // restore scale
@P.y = d;
```

#### Using trunc() for Value Scaling [[Ep2, 84:04](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5044s)]
```vex
// trunc() removes decimal component — values must be scaled first
// Very small or very large numbers won't produce useful steps without scaling
float d = length(@P);
d *= ch('scale');
float factor = ch('factor');
@P.y = d;          // before truncation — smooth ramp
d = trunc(d);
@P.y = d;          // after truncation — stepped ramp
```

#### Stepped Ramp Using Truncation with Ramp [[Ep2, 90:30](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5430s)]
```vex
// Combine quantization with a ramp for full control over step heights
float d = length(@P);
d *= ch('scale');
float f = ch('factor');
d /= f;
d = trunc(d);
d *= f;
@P.y = d;  // stepped ramp

// Further: drive steps through a ramp curve with pre/post scale
d *= ch('pre_scale');
d  = chramp('my_stepped_ramp', d);
d *= ch('post_scale');
@P.y = d;
```

#### Value Quantization with Modulo [[Ep2, 91:54](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5514s)]
```vex
// Quantize continuous distance into repeating color bands using modulo
float d = length(@P);
d *= ch('scale');
@Cd = chramp('ramp', d);   // map to ramp first

float f = ch('frequency');
d /= f;
d *= trunc(d);   // truncate — quantize
d %= f;          // modulo creates repeating band pattern
@Cd.y = d;       // assign to green channel
```

#### Matrix Types and Orientation Vectors [[Ep7, 114:04](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=6844s)]
```vex
// Convert quaternion orientation to matrix, then extract N and up vectors
// Two equivalent approaches:

vector N, up;
N  = normalize(@P);
up = {0,1,0};

// Approach 1: multiply basis vectors by matrix
matrix3 m = qconvert(Qorient);
@N  = {0,0,1} * m;   // Z-axis → forward/normal
@up = {0,1,0} * m;   // Y-axis → up

// Approach 2: directly access matrix rows
matrix3 m2 = qconvert(Qorient);
@N  = normalize(m2[2]);  // row 2 = Z axis (normal)
@up = normalize(m2[1]);  // row 1 = Y axis (up)
```

---

### Vector Operations

#### Modulo on Color Attributes [[Ep2, 79:28](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4768s)]
```vex
// % on integers creates stepped patterns; on floats creates sawtooth waves
@Cd.r = @ptnum % 5;   // integer modulo — 5 repeating color levels
@P.y  = @ptnum % 5;   // same pattern applied to position
@Cd.r = @Time % 0.7;  // float modulo — sawtooth cycling color animation
```

#### Modulo Operator Looping Behavior [[Ep2, 80:40](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4840s)]
```vex
// @Time % 0.2 creates rapid sawtooth: values climb 0..0.2 then reset
// Use whole numbers (e.g., % 2) for cleaner cycles; fractional = messy remainders
@Cd.r = @Time % 0.2;
```

#### Modulo operator with Time [[Ep2, 80:46](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=4846s)]
```vex
// Cycle position vertically every 5 units of time
@P.y  = @Time % 5;    // clean cycle — whole number divisor

// Fractional divisor produces messy remainders — use whole numbers when possible
@Cd.r = @Time % 0.7;
```

#### Modulo positioning and time-based color [[Ep2, 99:48](https://www.youtube.com/watch?v=OyjB5ZifIuU&t=5988s)]
```vex
// Point number modulo for stepped vertical positions
@P.y  = @ptnum % 5;

// Time modulo for cyclic red channel animation
@Cd.r = @Time % 0.7;
```

#### Vector Addition Basics [[Ep4, 31:54](https://www.youtube.com/watch?v=66WGmbykQhI&t=1914s)]
```vex
// Vector addition: place vectors tip-to-tail
// Result points from tail of 'a' to tip of 'b'
vector a = chv('a');
vector b = chv('b');
@N = a + b;
```

#### Vector Subtraction for Direction Vectors [[Ep4, 34:10–37:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=2050s)]
```vex
// b - a = direction vector FROM a TO b
// Reversing order (a - b) flips the direction
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);
@N = b - a;   // direction from input-0 point 0 toward input-1 point 0

// Using current point position as source (each point aims at target)
vector a2 = @P;
vector b2 = point(1, "P", 0);
@N = b2 - a2;

// Velocity vector from origin point
vector origin = point(1, "P", 0);
@v = @P - origin;   // each point's vector relative to origin
```

#### Vector Subtraction Between Points (Normals) [[Ep4, 36:56](https://www.youtube.com/watch?v=66WGmbykQhI&t=2216s)]
```vex
// All surface points read same target from input 1, compute direction to it
vector a = point(0, 'P', 0);
vector b = point(1, 'P', 0);
@N = b - a;
```

#### Vector Scaling with Parameters [[Ep4, 43:00–45:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=2580s)]
```vex
// *= scales vector in place; negative values invert direction
*= ch('scale');   // scale all components uniformly

// Per-axis scaling and direction flip using a vector channel
vector a = @P;
vector b = point(1, @ptnum, "P");  // corresponding point in second input
@N = b - a;
@N *= chv('scalevec');   // stretch X, negate Z, etc.

// Velocity relative to origin
vector origin = point(1, 'P', 0);
@v = @P - origin;
```

#### Vector Multiplication Setup [[Ep4, 41:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=2506s)]
```vex
// Placeholder: store current position and a reference point before multiplication
vector a = @P;
vector b = point(1, "P", 0);
@N = a + b;   // temporary sum — will be replaced with proper scale operation
```

#### Identity Matrix Creation [[Ep7, 127:54](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7674s)]
```vex
// Two equivalent ways to create a 3x3 identity matrix (no rotation, no scale)
matrix3 m = [[1,0,0,0,1,0,0,0,1]];  // explicit flat layout
matrix3 m2 = ident();                // cleaner built-in — identical result
```

#### Identity Matrix Definition [[Ep7, 128:20](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7700s)]
```vex
// Row-by-row explicit declaration vs ident() shorthand
// Diagonal = 1 (basis vectors intact), off-diagonal = 0 (no shear/rotation)
matrix3 m  = [[1,0,0],[0,1,0],[0,0,1]];
matrix3 m2 = ident();
```

#### Identity Matrix Declaration [[Ep7, 129:12](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7752s)]
```vex
// Verbose syntax: all 9 elements listed individually
// Foundation before learning ident() shorthand
matrix3 m = {1,0,0,0,1,0,0,0,1};
```

#### Identity Matrix Initialization [[Ep7, 129:28](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=7768s)]
```vex
// ident() = no rotation, no scale — equivalent to quaternion(0,0,0,1) for orient
matrix3 m = ident();
```

#### Matrix Casting 4x4 to 3x3 [[Ep7, 140:52](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8452s)]
```vex
// Cast 4x4 matrix down to 3x3 (drops translation row/column)
// Similar to casting float → int to truncate data
matrix3 m = matrix3(myFancyMatrix);

// Retrieve packed primitive's full 4x4 transform
matrix pft = primintrinsic(0, 'packedfulltransform', @ptnum);
4@a = pft;   // store as matrix attribute for inspection
```

#### Matrix Structure and Components [[Ep7, 144:00](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8640s)]
```vex
// 4x4 transformation matrix layout:
//   upper-left 3x3 = rotation + scale
//   4th column (indices [0][3],[1][3],[2][3]) = translation (human-readable)
//   bottom row = [0, 0, 0, 1] for homogeneous coordinates
matrix m = {0.365308, 0.584615, -0.121554, 0.0,
            -0.534593, 0.478389, 0.696304, 0.0,
            0.663726, -0.27805, 0.696304, 0.0,
            0.0, 0.0, 0.0, 1.0};
```

#### Extracting Rotation and Scale from 4x4 Matrix [[Ep7, 144:30](https://www.youtube.com/watch?v=9ztkhG7DhuA&t=8670s)]
```vex
// Float array attribute holding flattened 4x4 matrix (16 values)
// Translation visible in specific positions; cast to matrix3 to get rot+scale only
f[]@matrix3 = {0.54813, -0.13154, 0.0, 0.034593,
               0.478835, 0.006364, 0.0, 0.066738,
               0.27055, 0.006364, 0.0, 0.0,
               0.0, 0.0, 0.0, 1.0};
```

---

### Dot Product

#### Dot Product Basics [[Ep4, 3:54](https://www.youtube.com/watch?v=66WGmbykQhI&t=234s)]
```vex
// dot(A, B) measures alignment between two vectors
//   1  = same direction, 0 = perpendicular, -1 = opposite
// @N.y and dot(@N, {0,1,0}) are equivalent — pick whichever is clearer
@Cd = @N.y;                    // direct component access
@Cd = dot(@N, {0,1,0});        // explicit dot product with up vector
@Cd = dot(@N, chv('angle'));   // user-controlled direction via channel param
```

#### Dot Product with Normals [[Ep4, 4:14](https://www.youtube.com/watch?v=66WGmbykQhI&t=254s)]
```vex
// Negation inverts the range (flips light/shadow sides)
// chv() makes direction interactive; dot product measures angular alignment
@Cd = @N.y;
@Cd = -@N.y;                   // inverted
@Cd = dot(@N, {0,1,0});
@Cd = dot(@N, chv('angle'));   // user-controlled comparison direction
```

#### Dot Product for Directional Shading [[Ep4, 7:10](https://www.youtube.com/watch?v=66WGmbykQhI&t=430s)]
```vex
// Dot product compares direction of two vectors:
//   1 = same direction, 0 = 90 degrees apart, -1 = opposite
// Useful for coloring geometry based on normal alignment with any direction
@Cd = -@N.z;
@Cd = -@N.y;
@Cd = dot(@N, {0,1,0});
@Cd = dot(@N, chv('angle'));   // interactive direction control
```

#### Dot Product for Surface Orientation [[Ep4, 8:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=480s)]
```vex
// Compare surface normal against user-defined direction
// Returns -1 to 1: smooth gradient based on surface orientation vs input direction
@Cd = dot(@N, chv('angle'));

// Common remaps after dot product:
float facing = dot(@N, chv('angle'));
@Cd = max(0, facing);               // clamp negatives — one-sided lighting
@Cd = fit(facing, -1, 1, 0, 1);    // remap full -1..1 range to 0..1 for display
```

#### Dot Product with Normal and Up Vector [[Ep4, 8:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=492s)]
```vex
// dot(@N, up) = smooth -1..1 based on angle between normal and up axis
// parallel=1, perpendicular=0, opposite=-1
@Cd = dot(@N, {0, 1, 0});
```

#### Dot Product with Vectors and Channels [[Ep4, 8:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=526s)]
```vex
// Multiple equivalent approaches for top-down lighting calculations
@Cd = dot(@N, {0,1,0});        // explicit up vector
@Cd = @N.y;                    // equivalent shorthand
@Cd = dot(@N, chv('angle'));   // channel-driven direction
vector pos = point(0, 'P', 0);
@Cd = dot(@N, pos);            // use point position as direction (may need normalize)
```

#### Dot Product Direction Comparison [[Ep4, 9:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=586s)]
```vex
// Magnitude scaling can cause over-brightness — normalize when reading point positions
@Cd = dot(@N, chv('angle'));
@Cd = dot(@N, (0,1,0));
vector pos = point(1, "P", 0);
@Cd = dot(@N, pos);            // may be overbright if pos is far from origin
pos = normalize(pos);          // normalize to pure direction — removes magnitude
```

#### Dot Product with Point Reference [[Ep4, 10:34](https://www.youtube.com/watch?v=66WGmbykQhI&t=634s)]
```vex
// Progression: hardcoded direction → point lookup → normalized point → channel param
// Normalizing ensures dot product measures only angle, not distance
vector pos = point(1, 'P', 0);
@Cd = dot(@N, pos);            // raw: magnitude affects result

pos = normalize(pos);
@Cd = dot(@N, pos);            // normalized: pure directional alignment

@Cd = dot(@N, chv('angle'));   // final: fully interactive
```

#### Normalizing Vectors for Directional Dot Product [[Ep4, 14:08](https://www.youtube.com/watch?v=66WGmbykQhI&t=848s)]
```vex
// Without normalization: magnitude of pos vector affects dot product (unwanted)
// With normalization: dot product only evaluates direction — consistent masking
vector pos = point(1, "P", 0);
@Cd = dot(@N, pos);    // overbright if pos is far from origin

pos = normalize(pos);
@Cd = dot(@N, pos);    // correct: unit-length direction only
```

#### Normalizing Position for Dot Product Mask [[Ep4, 14:10](https://www.youtube.com/watch?v=66WGmbykQhI&t=850s)]
```vex
// normalize() → unit-length vector → dot product measures pure angle
// Prevents overbright results when control point is far from origin
vector pos = point(1, "P", 0);
pos = normalize(pos);
@Cd = dot(@N, pos);
```

#### Cross Product and Normal Manipulation [[Ep4, 17:44](https://www.youtube.com/watch?v=66WGmbykQhI&t=1064s)]
```vex
// Read point from second input, normalize, dot product for color mask
// Then modify normal using cross product with up vector
vector pos = point(1, "P", 0);
pos = normalize(pos);
@Cd = dot(@N, pos);        // directional color mask

@N = cross(@N, {0,1,0});   // rotate normal 90° — now points sideways
```

---

### Cross Product

#### Cross Product Normal Rotation [[Ep4, 19:34](https://www.youtube.com/watch?v=66WGmbykQhI&t=1174s)]
```vex
// cross(@N, {0,1,0}) rotates normals 90° — outward normals become side-facing
// Result is perpendicular to both inputs (right-hand rule)
@N = cross(@N, {0,1,0});
```

#### Cross Product for Surface Normals [[Ep4, 20:22](https://www.youtube.com/watch?v=66WGmbykQhI&t=1222s)]
```vex
// cross(@P, up) creates normals that lie along the surface (not outward)
// "Combs" normals around the Y-axis based on radial position
@N = cross(@P, {0,1,0});
```

#### Cross Product Right Hand Rule [[Ep4, 22:12](https://www.youtube.com/watch?v=66WGmbykQhI&t=1332s)]
```vex
// Double cross: first cross creates perpendicular tmp, second cross uses tmp
// Creates orthogonal vector system — final N perpendicular to both @N and up
vector tmp = cross(@N, {0,1,0});
@N = cross(@N, tmp);
```

#### Cross Product for Normal Calculation [[Ep4, 22:36](https://www.youtube.com/watch?v=66WGmbykQhI&t=1356s)]
```vex
// Two successive cross products create an orthogonal frame
// Different axis vectors ({1,1,0}) cause normals to twirl around that direction
@N = cross(@v, {1,1,0});   // cross velocity with diagonal axis

vector tmp = cross(@v, {0,1,0});
@N = cross(tmp, @v);       // second cross ensures perpendicularity to @v
```

#### Cross Product Normal Manipulation [[Ep4, 22:46](https://www.youtube.com/watch?v=66WGmbykQhI&t=1366s)]
```vex
// Normalize after cross product to maintain unit-length normals
// Different axis vectors ({1,1,0}, {1,0,0}, etc.) create different twirl directions
@N = cross(@N, {1,1,0});   // twirl around diagonal axis
@N = cross(@N, {1,0,0});   // twirl around X axis

vector tmp = cross(@N, {0,1,0});
@N = normalize(tmp);       // cross then normalize — proper workflow
```

#### Double Cross Product [[Ep4, 23:28](https://www.youtube.com/watch?v=66WGmbykQhI&t=1408s)]
```vex
// Cross N with a vector, store result, then cross again with original N
// Creates rotation pattern — normals rotate around axis defined by first cross
vector tmp = cross(@N, {0, -1, 0});
@N = cross(@N, tmp);
```

#### Multiple Cross Products and Cycles [[Ep4, 24:48](https://www.youtube.com/watch?v=66WGmbykQhI&t=1488s)]
```vex
// Repeated cross products cycle back to original orientation
// Used in grooming: double cross with {0,1,0} applies gravity to hair/fur
// 4 iterations = full 360° cycle back to start

// Double cross (90° rotation)
vector tmp = cross(@P, {0,1,0});
@N = cross(@N, tmp);

// Triple cross
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);

// Quadruple cross (full cycle — returns to original)
vector cross2 = cross(@N, {0,1,0});
cross2 = cross(@N, cross2);
cross2 = cross(@N, cross2);
cross2 = cross(@N, cross2);
@N = cross(@N, cross2);

// Quintuple cross
vector cross3 = cross(@N, {0,1,0});
cross3 = cross(@N, cross3);
cross3 = cross(@N, cross3);
cross3 = cross(@N, cross3);
cross3 = cross(@N, cross3);
@N = cross(@N, cross3);
```

#### Iterative Cross Product Rotations [[Ep4, 26:00](https://www.youtube.com/watch?v=66WGmbykQhI&t=1560s)]
```vex
// 4 cross operations = 360° rotation back to start
// Each additional cross = another 90° step around the axis
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

#### Sequential Cross Products for Vector Rotation [[Ep4, 26:02](https://www.youtube.com/watch?v=66WGmbykQhI&t=1562s)]
```vex
// 3 cross operations = 270° (or equivalently -90°)
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

#### Rotating Normals with Cross Products [[Ep4, 26:32](https://www.youtube.com/watch?v=66WGmbykQhI&t=1592s)]
```vex
// Each cross() with same starting @N advances 90° around the rotation axis
// No explicit matrices needed for 90° incremental rotations
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

#### Repeated Cross Product Operations [[Ep4, 28:30](https://www.youtube.com/watch?v=66WGmbykQhI&t=1710s)]
```vex
// Cascading cross products — 5-step chain
vector cross1 = cross(@N, {0,1,0});
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
cross1 = cross(@N, cross1);
@N = cross(@N, cross1);
```

---

## Common Mistakes

```vex
// MISTAKE 1: Integer division produces all zeros
@Cd = @ptnum / @numpt;   // both ints → truncated to 0

// FIX: cast one operand to float
@Cd = float(@ptnum) / @numpt;

// MISTAKE 2: Skipping normalize before dot product
vector pos = point(1, "P", 0);
@Cd = dot(@N, pos);      // overbright if pos is far from origin

// FIX: normalize first
pos = normalize(pos);
@Cd = dot(@N, pos);

// MISTAKE 3: Using % with fractional divisors creates messy values
@Cd.r = @Time % 0.7;    // fractional — sawtooth with irregular feel

// FIX: use whole number divisors for clean cycles
@Cd.r = @Time % 1.0;

// MISTAKE 4: fit() with identical in/out ranges is a no-op
// Always check that imin != imax to get meaningful remapping
float d = fit(length(@P), 0, 0, 0, 1);  // WRONG: inMin == inMax → undefined

// MISTAKE 5: Forgetting to cook matlib before createNode() on shader children
// matlib.cook(force=True) must be called first or createNode returns None

// MISTAKE 6: Cross product result not normalized — length varies with input vectors
@N = cross(@N, {0,1,0});       // length depends on sin of angle between inputs
@N = normalize(cross(@N, {0,1,0}));  // always normalize for consistent shading

// MISTAKE 7: Applying trunc() without pre-scaling — all decimals removed too early
// Scale first so values span a useful integer range, then truncate
float raw = length(@P);       // e.g. 0.0 .. 0.8 — trunc always gives 0
raw *= ch('scale');           // e.g. 0.0 .. 8.0 — now trunc gives 0,1,2...8
raw = trunc(raw);
```

## See Also
- **VEX Data Types** (`vex_types.md`) -- vector type hierarchy and conversions
- **VEX Functions Reference** (`vex_functions.md`) -- math function signatures
