# VEX Language Fundamentals

## Triggers
vex, wrangle, data type, variable, function, control flow, for loop,
if else, foreach, array, matrix, vector, type prefix, run over

## Context
VEX language fundamentals: types, control flow, inputs/outputs,
functions, preprocessor. Runs inside wrangle nodes or VOP networks.

## Code

```vex
// Data types: scalars
int i = 42;
float f = 3.14;
string s = "hello";

// Vector types
vector2 uv = {0.5, 0.5};          // 2 floats (u, v)
vector pos = {1.0, 2.0, 3.0};     // 3 floats (x, y, z)
vector4 q = {0, 0, 0, 1};         // 4 floats (quaternion/homogeneous)

// Matrix types
matrix2 m2 = ident();             // 2x2
matrix3 m3 = ident();             // 3x3 (rotation/scale)
matrix  m4 = ident();             // 4x4 (full transform)

// Arrays
int nums[] = {1, 2, 3};
float vals[] = array(0.1, 0.2);
string names[] = {"a", "b"};
vector pts[] = {};                 // Empty vector array
```

```vex
// Type prefixes for @-binding
// (none)/f@ = float     @density or f@density
// i@        = int       i@id
// v@        = vector    v@velocity
// u@        = vector2   u@uv
// p@        = vector4   p@orient
// s@        = string    s@name
// 2@        = matrix2   2@mtx
// 3@        = matrix3   3@transform
// 4@        = matrix    4@xform
// Prefix needed on FIRST USE only

f@density = 1.0;
i@id = @ptnum;
v@velocity = set(0, 1, 0);
s@name = sprintf("pt_%d", @ptnum);
p@orient = quaternion(radians(45), {0, 1, 0});
```

```vex
// Control flow: conditionals
if (@P.y > ch("threshold")) {
    @Cd = {1, 0, 0};  // Red above threshold
} else if (@P.y > 0) {
    @Cd = {0, 1, 0};  // Green above zero
} else {
    @Cd = {0, 0, 1};  // Blue below zero
}

// Ternary
float val = (@P.y > 0) ? 1.0 : 0.0;

// For loop
for (int i = 0; i < 10; i++) {
    vector offset = set(i * 0.1, 0, 0);
    addpoint(0, @P + offset);
}

// Foreach (arrays)
int pts[] = neighbours(0, @ptnum);
foreach (int pt; pts) {
    vector pos = point(0, "P", pt);
}

// While
int count = 0;
while (count < chi("max_iter")) {
    count++;
}
```

```vex
// Inputs and outputs: wrangle has up to 4 geometry inputs
// Input 0 (first, default)
vector pos0 = point(0, "P", @ptnum);

// Input 1 (second)
vector target = point(1, "P", @ptnum);

// Input 2, 3
float val = prim(2, "density", @primnum);
string name = detail(3, "name");

// Writing @attribute modifies output (input 0 + modifications)
@P = lerp(@P, target, ch("blend"));
```

```vex
// User-defined functions (declared before main code)
// VEX uses semicolons to separate parameter types
float remap(float val; float omin, omax, nmin, nmax) {
    float t = clamp((val - omin) / (omax - omin), 0, 1);
    return lerp(nmin, nmax, t);
}

vector rotate_around_axis(vector p; vector axis; float angle) {
    matrix3 m = ident();
    rotate(m, radians(angle), axis);
    return p * m;
}

// Usage
f@remapped = remap(@P.y, 0, 10, 0, 1);
@P = rotate_around_axis(@P, {0,1,0}, ch("angle"));
```

```vex
// Preprocessor
#include <math.h>
#include <voplib.h>
#define PI 3.14159265
#define SQR(x) ((x) * (x))
#define LERP(a, b, t) ((a) + (t) * ((b) - (a)))

// Execution contexts:
// SOP: attribwrangle -- runs over Points/Prims/Vertices/Detail
// DOP: gasFieldWrangle -- runs over voxels (@ix, @iy, @iz)
// CHOP: channelWrangle -- runs over samples (@C, @I, @Time)
// COP: pixelWrangle -- runs over pixels (@IX, @IY, @RESX, @RESY)

// Run-over modes (SOP):
// Points (default) -- @ptnum is current index
// Primitives       -- @primnum is current index
// Vertices         -- @vtxnum is current index
// Detail           -- runs once for entire geometry
```

```vex
// Spare parameters: ch() reads UI sliders on wrangle node
float radius = chf("radius");        // Float slider
int count = chi("count");            // Integer slider
vector color = chv("color");         // Color picker
string path = chs("filepath");       // String field
float ramp_val = chramp("falloff", @P.y / 10.0);  // Ramp

// ch() changes do NOT trigger VEX recompilation (fast to adjust)
// Changing wrangle code DOES trigger recompilation (first cook slower)
```

## Common Mistakes
- Missing type prefix on first use -- `@myattr` defaults to float, use `v@myattr` for vector
- Using VEX for simple expressions -- parameter fields with ch() are simpler for basic math
- Forgetting semicolons in function parameter types -- VEX uses `;` not `,` between types
- Using @ptnum in Detail mode -- undefined; use explicit loop with npoints(0)
