# VEX Corpus: Miscellaneous Topics

## Triggers
slice, assert, find string, noise, noise remap, volume sample, point creation,
point lookup, vector subtraction, removeprim, removepoint, usd_setactive,
quaternion, gradient, open closed, ocean_sample, pluralize, replace,
texprintf, osd, packed transform, setpackedtransform

## Context
Miscellaneous VEX patterns: array slicing, assertions, string search, noise,
quaternions, geometry deletion, USD operations, packed transforms, OSD surfaces.

## Code

```vex
// Array slicing
int nums[] = {10, 20, 30, 40, 50, 60};
int a[] = slice(nums, 1, 3);                // {20, 30}         nums[1:3]
int b[] = slice(nums, 1, -1);               // {20, 30, 40, 50} nums[1:-1]
int c[] = slice(nums, 0, len(nums), 2);     // {10, 30, 50}     nums[::2] (every other)
```

```vex
// Debug assertion macro
#define assert(EXPR) \
    if (assert_enabled()) { \
        if (!(EXPR)) print_once( \
            sprintf("VEX Assertion Failed %s:%d - (%s)\n", \
                    __FILE__, __LINE__, #EXPR)); \
    }

// Usage: assert(@pscale > 0);
```

```vex
// String search with find()
string haystack = "mylongstring";
string needle = "str";
if (find(haystack, needle) >= 0) {
    i@found = 1;  // Substring found
}

// String replace
string str = "abcdef abcdef abcdef";
string new_str = replace(str, "def", "ghi");        // "abcghi abcghi abcghi"
string partial = replace(str, "def", "ghi", 2);     // Replace only first 2

// Pattern replace with wildcards
string swapped = replace_match("a_to_b", "*_to_*", "*(1)_to_*(0)");  // "b_to_a"

// Reverse
string rev = reverse("hello");  // "olleh"
int arr[] = {1, 2, 3, 4};
reverse(arr);                    // {4, 3, 2, 1} in-place
```

```vex
// Noise basics: combine position, time, and channel parameters
float n = noise(@P * chf("freq") + @Time * ch("speed"));
@Cd = noise(chv("offset") + @P * chv("scale") + @Time);

// Noise remap with chramp for artistic control
float raw = noise(@P * ch("noise_freq"));
float remapped = chramp("noise_remap", raw);
@P.y = remapped * ch("height");
```

```vex
// Visualizing data via position (debugging technique)
// Temporarily assign computed values to @P.y to see spatial variation
float a = noise(@P + @Time);
a = chramp("noise_range", a);
@P.y = a;  // See noise pattern as height displacement

// Noise-driven quaternion orientation
vector N = normalize(@P);
@orient = quaternion(maketransform(N, {0,1,0}));
vector4 wobble = quaternion(radians(20) * sin(@Time * chf("freq") * 3), {0,1,0});
@orient *= wobble;
```

```vex
// Volume cubic sampling with gradient and Hessian
vector P = {1.0, 2.0, 3.0};
vector grad;
matrix3 hess;

float val1 = volumecubicsample(0, "density", P, grad, hess);

// Taylor expansion approximation:
vector u = {0.1, 0.01, 0.001};
// First order:  val1 + dot(u, grad) ≈ volumecubicsample(0, "density", P+u)
// Second order: val1 + dot(u, grad) + 0.5 * dot(u, u*hess)
```

```vex
// Vector subtraction for direction
// Direction from point a to point b
vector a = point(0, "P", 0);
vector b = point(1, "P", 0);
@N = normalize(b - a);  // Points FROM a TOWARD b

// Using @P directly
vector target = point(1, "P", 0);
@N = normalize(target - @P);
```

```vex
// Random geometry deletion
// Prim Wrangle: random primitive deletion
if (rand(@primnum) < ch("cutoff")) {
    removeprim(0, @primnum, 1);  // 1 = also remove points
}

// Point Wrangle: random point deletion
if (rand(@ptnum) < ch("cutoff")) {
    removepoint(0, @ptnum);
}
```

```vex
// Spherical vs linear gradient
// Input 1: two points defining gradient range
vector p1 = point(1, "P", 0);
vector p2 = point(1, "P", 1);
float r = distance(p1, p2);
@Cd = (r - distance(@P, p1)) / r;  // Spherical gradient: 1 at p1, 0 at p2

// Linear gradient along axis
float t = fit(@P.y, p1.y, p2.y, 0, 1);
@Cd = set(t, t, t);
```

```vex
// Quaternion construction and composition
vector N = normalize(@P);
@N = N;
@orient = quaternion(maketransform(N, {0,1,0}));

// Additional rotations
vector4 extrarot = quaternion(radians(ch("extra_angle")), {1, 0, 0});
vector4 headshake = quaternion(
    radians(20) * sin(@Time * @ptnum * 3), {0, 1, 0});
@orient *= extrarot;
@orient *= headshake;

// Convert quaternion back to N and up
matrix3 m = qconvert(@orient);
@N = {0, 0, 1} * m;
v@up = {0, 1, 0} * m;
```

```vex
// Random open/closed polygon intrinsic
// Run over Primitives:
int openclose = int(rand(@primnum + @Frame) * 2);
setprimintrinsic(0, "closed", @primnum, openclose);
// 0 = open (polyline outline), 1 = closed (filled polygon)
```

```vex
// Ocean sample: displace points using ocean spectrum
@P += ocean_sample("spectrum.bgeo", 0, 1, 2, 0.7, @Time, 0, 0, @P);
```

```vex
// Packed primitive transforms
// Read current transform
matrix transform = getpackedtransform(0, @primnum);

// Build additional transform
matrix tf = ident();
rotate(tf, radians(45), {0, 1, 0});
translate(tf, {0, 1, 0});

// Apply combined transform
setpackedtransform(0, @primnum, transform * tf);
```

```vex
// OSD limit surface scattering (subdivision surfaces)
void scatterOnLimitSurface(string file, texmap; int geo_handle; int npts) {
    int npatches = osd_patchcount(file);
    for (int i = 0; i < npts; ++i) {
        int patch_id = nrandom() * npatches;
        float patch_s = nrandom();
        float patch_t = nrandom();
        int face_id;
        float face_u, face_v;
        if (osd_lookupface(file, patch_id, patch_s, patch_t,
                           face_id, face_u, face_v, "uv")) {
            vector clr = texture(texmap, face_u, face_v);
            vector P;
            osd_limitsurface(file, "P", patch_id, patch_s, patch_t, P);
            int ptnum = addpoint(geo_handle, P);
            if (ptnum >= 0) {
                addpointattrib(geo_handle, "Cd", clr);
                addpointattrib(geo_handle, "face_id", face_id);
            }
        }
    }
}
```

```vex
// UDIM texture path formatting
// texprintf resolves UDIM/UV tile patterns
string map1 = texprintf(3.1, 4.15, "map_<UDIM>.rat");           // "map_1044.rat"
string map2 = texprintf(3.1, 4.15, "map_%(U)02d_%(V)02d.rat");  // "map_04_05.rat"
```

```vex
// USD VEX: set prim active/inactive
usd_setactive(0, "/geo/sphere", true);   // Make prim active
usd_setactive(0, "/geo/hidden", false);  // Deactivate prim

// USD collection path validation
int valid = usd_iscollectionpath(0, "/geo/cube.collection:some_collection");
```

```vex
// Long operation progress tracking
int op_handle = opstart("Performing long operation");
// ... perform_long_operation() ...
if (op_handle >= 0) {
    opend(op_handle);
}
```

## Common Mistakes
- Forgetting slice uses exclusive end index -- slice(arr, 1, 3) returns indices 1,2 not 1,2,3
- Using removeprim with flag=0 leaves orphan points -- use flag=1 to clean up
- Not normalizing direction vectors from subtraction -- b-a gives direction but not unit length
- Using open/closed intrinsic without checking primitive type -- only works on polygon primitives
