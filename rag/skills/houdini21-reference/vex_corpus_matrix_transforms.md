# VEX Corpus: Matrix Transforms

## Triggers
matrix, transform, rotate, scale, quaternion, orient, maketransform,
packed transform, intrinsic, qconvert, dconvert, usd transform, pivot

## Context
VEX matrix and transform patterns: constructing matrices, quaternion
conversions, packed primitive transforms, USD transform operations.

## Code

```vex
// Construct matrices from components
vector4 v = set(1.0, 2.0, 3.0, 4.0);

// matrix3: 3x3 (rotation + scale), row-major order
matrix3 m = set(1.0, 2.0, 3.0,
                4.0, 5.0, 6.0,
                7.0, 8.0, 9.0);

// Identity matrices
matrix3 m3 = ident();    // 3x3 identity
matrix  m4 = ident();    // 4x4 identity

// Build transform from SRT components
#include <math.h>
vector translate = {1, 2, 3};
vector rotate_deg = {3, 45, 60};
vector scale_vec = {0.5, 0.25, 2.0};
matrix xform = maketransform(XFORM_SRT, XFORM_XYZ,
                              translate, rotate_deg, scale_vec);
```

```vex
// Rotate geometry around an axis
matrix3 m = ident();
float angle = radians(ch("angle"));
vector axis = normalize(chv("axis"));
rotate(m, angle, axis);
@P *= m;

// Rotate prims around an edge (between first two points)
int points[] = primpoints(0, @primnum);
vector p0 = point(0, "P", points[0]);
vector p1 = point(0, "P", points[1]);
vector edge_axis = normalize(p0 - p1);

matrix3 rot = ident();
rotate(rot, radians(ch("fold_angle")), edge_axis);

// Translate to origin, rotate, translate back
@P -= p0;
@P *= rot;
@P += p0;
```

```vex
// Quaternion orientation: the standard for copy-to-points
// Create orient from N and up vectors
vector N = normalize(@P);
vector up = {0, 1, 0};
@orient = quaternion(maketransform(N, up));

// Orient from matrix3
matrix3 m = ident();
@orient = quaternion(m);

// Rotate orient by additional rotation
@orient *= quaternion(radians(ch("extra_rotation")), {0, 1, 0});

// Animated orient with time-based wobble
@orient = quaternion(maketransform(normalize(@P), {0,1,0}));
@orient *= quaternion(radians(20) * sin(@Time * chf("freq") * 3), {0,1,0});
```

```vex
// Convert quaternion back to N and up vectors
matrix3 m = qconvert(@orient);
@N = {0, 0, 1} * m;   // Z-axis = forward direction
@up = {0, 1, 0} * m;  // Y-axis = up direction

// Extract all three axes from orient
vector x_axis = {1, 0, 0} * m;
vector y_axis = {0, 1, 0} * m;
vector z_axis = {0, 0, 1} * m;
```

```vex
// Packed primitive transform intrinsics
// Read the full 4x4 transform (includes translation)
matrix pft = primintrinsic(0, "packedfulltransform", @ptnum);
4@full_xform = pft;

// Extract rotation+scale (3x3) from the 4x4
matrix3 rot_and_scale = matrix3(pft);
3@rot_scale = rot_and_scale;

// Build and set transform intrinsic from orient + scale
vector4 qorient = quaternion({0, 1, 0} * @Time);
vector my_scale = {1, 0.5, 2};

matrix3 m = ident();
scale(m, my_scale);
m *= qconvert(qorient);
setprimintrinsic(0, "transform", @ptnum, m);
```

```vex
// USD transform operations (LOP wrangle)
#include <usd.h>

// Rotate around Z axis
usd_addrotate(0, "/geo/cube", "", USD_AXIS_Z, 30);

// Rotate around Y axis with named suffix
usd_addrotate(0, "/geo/mesh", "geo_rotation", USD_AXIS_Y, -45);

// Euler rotation
usd_addrotate(0, "/geo/cone", "cone_rotation",
              USD_ROTATE_XYZ, {0, 30, 45});

// Full matrix transform
#include <math.h>
matrix xform = maketransform(XFORM_SRT, XFORM_XYZ,
                              {1,2,3}, {3,45,60}, {0.5,0.25,2});
usd_addtransform(0, "/geo/cube", "my_xform", xform);
```

```vex
// USD pivot rotation (translate, rotate, inverse-translate)
#include <usd.h>

// Build pivot transform: rotate around Z through point (1,0,0)
string pivot_suffix = "some_pivot";
string pivot_name = usd_transformname(USD_XFORM_TRANSLATE, pivot_suffix);

usd_addtranslate(0, "/geo/cone", pivot_suffix, {1, 0, 0});
usd_addrotate(0, "/geo/cone", "some_rotation", USD_AXIS_Z, -90);
usd_addinversetotransformorder(0, "/geo/cone", pivot_name);
```

```vex
// Repeated transform steps in USD
#include <usd.h>

string step_suffix = "step";
usd_addtranslate(0, "/geo/cone", step_suffix, {1, 0, 0});

string step_name = usd_transformname(USD_XFORM_TRANSLATE, step_suffix);

// Rotate, then repeat the translation step, then rotate again
usd_addrotate(0, "/geo/cone", "first_rotation", USD_AXIS_Z, -30);
usd_addtotransformorder(0, "/geo/cone", step_name);
usd_addrotate(0, "/geo/cone", "second_rotation", USD_AXIS_Z, 45);
usd_addtotransformorder(0, "/geo/cone", step_name);
```

```vex
// Volume sampling with gradient and Hessian matrices
vector P = {1.0, 2.0, 3.0};
matrix3 grad, hessX, hessY, hessZ;

// Cubic interpolation with derivative info
vector val1 = volumecubicsamplev(0, "vel", P, grad, hessX, hessY, hessZ);

// Taylor expansion approximation:
vector u = {0.1, 0.01, 0.001};
// First order:  val1 + u * grad  ≈  volumecubicsamplev(0, "vel", P+u)
// Second order includes Hessian terms for better accuracy

// Smooth sampling variant
vector sval = volumesmoothsamplev(0, "vel", P, grad, hessX, hessY, hessZ);
```

## Common Mistakes
- Applying rotation around origin instead of pivot -- translate to origin first, rotate, translate back
- Forgetting to normalize axis before rotate() -- unnormalized axis produces skewed rotation
- Using matrix3 for packed transforms that need translation -- use full matrix (4x4) for packedfulltransform
- qconvert vs dconvert confusion -- qconvert: quaternion->matrix3, dconvert: dual quaternion->matrix3
