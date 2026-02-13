# VEX Data Types and Conversions

## Type Hierarchy

| Type | Size | Description | Literal Example |
|------|------|-------------|-----------------|
| `int` | 4 bytes | 32-bit integer | `42`, `-1`, `0xFF` |
| `float` | 4 bytes | 32-bit float | `3.14`, `1e-5`, `.5` |
| `vector2` | 8 bytes | 2 floats | `{0.5, 0.5}` |
| `vector` | 12 bytes | 3 floats (xyz/rgb) | `{1, 2, 3}` |
| `vector4` | 16 bytes | 4 floats (quaternion/rgba) | `{0, 0, 0, 1}` |
| `matrix2` | 16 bytes | 2x2 matrix | `ident()` |
| `matrix3` | 36 bytes | 3x3 matrix (rotation/scale) | `ident()` |
| `matrix` | 64 bytes | 4x4 matrix (full transform) | `ident()` |
| `string` | varies | UTF-8 string | `"hello"` |

## Implicit Conversions

VEX promotes types automatically: `int -> float -> vector2 -> vector -> vector4`

```vex
float f = 5;            // int to float: f = 5.0
vector v = 2.0;         // float to vector: v = {2, 2, 2}
vector v = set(1, 2, 3); // explicit construction
```

## Explicit Conversions

```vex
int i = int(3.7);            // truncate: 3
float f = float(42);         // promote: 42.0
float x = v.x;               // component: or v[0]
vector v = set(x, y, z);     // construct

// String conversions
string s = itoa(42);         // "42"
string s = sprintf("%g", 3.14); // "3.14"
int i = atoi("42");
float f = atof("3.14");
```

## Quaternion Operations

Quaternions are `vector4` with (x, y, z, w) layout:

```vex
// Identity (no rotation)
vector4 q = {0, 0, 0, 1};

// From axis-angle
vector4 q = quaternion(radians(90), {0, 1, 0});

// From Euler angles
vector4 q = eulertoquaternion(radians(rot), XFORM_XYZ);

// From matrix3
matrix3 m = lookat({0,0,0}, {0,0,1});
vector4 q = quaternion(m);

// Apply rotation
vector rotated = qrotate(q, @P);

// Combine rotations
vector4 q_combined = qmultiply(q1, q2);

// Interpolate (spherical)
vector4 q_blend = slerp(q1, q2, chf("blend"));

// Invert
vector4 q_inv = qinvert(q);
```

## Matrix Operations

```vex
// Identity
matrix m = ident();

// Build from components
matrix m = maketransform(XFORM_TRS, XFORM_XYZ, translate, rotate, scale);

// Extract components
vector t, r, s;
cracktransform(XFORM_TRS, XFORM_XYZ, {0,0,0}, m, t, r, s);

// Transform point (includes translation)
vector world_pos = @P * m;

// Transform direction (no translation)
matrix3 m3 = matrix3(m);
vector world_dir = @N * m3;

// Invert
matrix inv = invert(m);

// Look-at rotation
matrix3 rot = lookat(from_pos, to_pos);

// Rotation between two vectors
matrix3 rot = dihedral(vec_a, vec_b);
```

## See Also
- **Joy of VEX: Quaternions** (`joy_of_vex_quaternions.md`) -- tutorial examples with slerp, qrotate, orient
- **Joy of VEX: Vector Math** (`joy_of_vex_vector_math.md`) -- tutorial examples with dot, cross, fit, normalize
