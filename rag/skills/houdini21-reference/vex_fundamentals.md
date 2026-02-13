# VEX Language Fundamentals

## Execution Contexts

VEX runs inside **wrangle nodes** or **VOP networks** that compile to VEX.

| Context | Wrangle Node | Runs Over | Variables Available |
|---------|-------------|-----------|-------------------|
| SOP | Attribute Wrangle | Points, Prims, Vertices, Detail | `@ptnum`, `@numpt`, `@primnum`, `@numprim` |
| DOP | Gas Field Wrangle | Voxels | `@ix`, `@iy`, `@iz`, `@resx`, `@resy`, `@resz` |
| CHOP | Channel Wrangle | Samples | `@C`, `@I`, `@Time` |
| COP | Pixel Wrangle | Pixels | `@IX`, `@IY`, `@RESX`, `@RESY` |

### Run-Over Modes (SOP Context)
- **Points** (default) -- code runs once per point, `@ptnum` is current index
- **Primitives** -- code runs once per prim, `@primnum` is current index
- **Vertices** -- code runs once per vertex, `@vtxnum` is current index
- **Detail** -- code runs once for entire geometry (global operations)

## Data Types

```vex
// Scalar types
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

## Type Prefixes (@-binding)

| Prefix | Type | Example | Default If New |
|--------|------|---------|----------------|
| (none) | float | `@density` | 0.0 |
| `f@` | float | `f@density` | 0.0 |
| `i@` | int | `i@id` | 0 |
| `v@` | vector | `v@velocity` | {0,0,0} |
| `u@` | vector2 | `u@uv` | {0,0} |
| `p@` | vector4 | `p@orient` | {0,0,0,0} |
| `s@` | string | `s@name` | "" |
| `2@` | matrix2 | `2@mtx` | identity |
| `3@` | matrix3 | `3@transform` | identity |
| `4@` | matrix | `4@xform` | identity |

The prefix is only needed on the **first use** of an attribute in your code.

## Control Flow

```vex
// Conditionals
if (condition) {
    // ...
} else if (other) {
    // ...
} else {
    // ...
}

// Ternary
float val = condition ? a : b;

// For loop
for (int i = 0; i < n; i++) { ... }

// Foreach (arrays)
int pts[] = neighbours(0, @ptnum);
foreach (int pt; pts) {
    vector pos = point(0, "P", pt);
}

// While
while (condition) { ... }
```

## Inputs and Outputs

Wrangle nodes have up to 4 geometry inputs, accessed by index:

```vex
// Input 0 (default, first input)
vector pos = point(0, "P", @ptnum);

// Input 1 (second input)
vector target = point(1, "P", @ptnum);

// Input 2, 3
float val = prim(2, "density", @primnum);
string name = detail(3, "name");
```

Writing to `@attribute` modifies the output geometry (always input 0 with modifications).

## User-Defined Functions

```vex
// Declared before main code
float remap(float val; float omin, omax, nmin, nmax) {
    float t = clamp((val - omin) / (omax - omin), 0, 1);
    return lerp(nmin, nmax, t);
}
```

Note: VEX uses semicolons to separate parameter types in function signatures.

## Preprocessor

```vex
#include <math.h>
#include <voplib.h>
#define PI 3.14159265
#define SQR(x) ((x) * (x))
```

## VEX vs HScript Expressions

| Feature | VEX (Wrangles) | HScript (Parameter Fields) |
|---------|----------------|---------------------------|
| Speed | Compiled, parallel | Interpreted, serial |
| Geometry access | Full read/write | Read-only via `point()` |
| Use case | Heavy processing | Simple parameter expressions |
| Syntax | C-like | `$F`, `ch("parm")` |
| Variables | `@P`, `@ptnum` | `$PT`, `$NPT` |

Rule of thumb: If processing more than a few hundred points or modifying geometry, use VEX.

## See Also
- **Joy of VEX: Attributes** (`joy_of_vex_attribs.md`) -- tutorial examples with attribute creation and binding
- **Joy of VEX: Flow Control** (`joy_of_vex_flow_control.md`) -- tutorial examples with loops, conditionals, foreach
