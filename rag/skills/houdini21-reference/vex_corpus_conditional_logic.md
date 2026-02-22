# VEX Corpus: Conditional Logic

> 52 examples from vex-corpus. Sources: cgwiki-vex, joy-of-vex-youtube, sidefx-vex-reference

## Beginner (10 examples)

### Search an array with find

```vex
int myint = 0;
if (@Frame == 1 || @Frame == 25 || @Frame == 225 || @Frame == 35) {
    myint = 1;
}
// Set an int attrib to 1 on specific frames. Tip from Tomas Slancik.
```


### Conditional comparison operators

```vex
int foo;
if (foo == 3) {
    // double equals sign for comparison, not assignment
    // do something
}
// Use `==` for equality testing, not `=` (assignment).
```


### Nested Conditionals with Point Position

```vex
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1, 0, 0};
    }
}
// Nested if: point number > 50 AND x-position < 2.
```


### Conditional color assignment with less than

```vex
if (@ptnum < 5) {
    @Cd = {1, 0, 0};
}
// Set points 0–4 to red; leave point 5+ unchanged.
```


### Comparison Operators and Modulo

```vex
if (@ptnum >= 5) {
    @Cd = {1, 0, 0};
}
// Greater-than-or-equal comparison for conditional color.
```


### Flipping normals based on Z direction

```vex
@Cd = @N;
if (@Cd.z < 0) {
    @Cd = -@N;
}
// Color by normal, then flip if Z component is negative.
```


### Conditional Color with If-Else

```vex
int a = 3;
int b = 3;

if (a == b) {
    @Cd = {1, 1, 0};
} else {
    @Cd = {1, 0, 0};
}
// Basic if-else comparing two integer variables.
```


### Compound Conditional with AND Operator

```vex
if (@ptnum > 50 && @P.y < 2) {
    @Cd = {1, 0, 0};
}
// AND operator (`&&`): both conditions must be true.
```


### Logical OR operator in conditionals

```vex
if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1, 0, 0};
}
// OR operator (`||`): either condition is sufficient.
```


### Modulo Operator for Pattern Selection

```vex
if (@ptnum % 5 == 0) {
    @Cd = {1, 0, 0};
}
// Modulo selects every fifth point (divisible by 5).
```


## Intermediate (37 examples)

### Random delete points by threshold

```vex
if (rand(@ptnum) > ch('threshold')) {
    removepoint(0, @ptnum);
}
// Remove points randomly above a threshold. Via Matt Ebb.
```


### Remove points that don't have normals directly along an axis

```vex
if (max(abs(normalize(@N))) != 1) {
    removepoint(0, @ptnum);
}
// Keep only axis-aligned normals. Via Matt Ebb.
```


### If statement syntax overview

```vex
// Structure:
if (test_condition) {
    // code to execute;
    // end each line with a semicolon;
    // close with curly bracket
}

// Example:
if (@foo > 1) {
    @Cd = {1, 0, 0};
}
// VEX if-statement: test in `()`, body in `{}`, each statement ends with `;`.
```


### Compact single-line if

```vex
if (length(@P) * 2 + @ptnum % 5 == 0) {
    @Cd = {1, 0, 0};
}
// VEX ignores whitespace — braces can be on the same line.
```


### Assignment vs Equality Operators

```vex
if (@foo > 1) {
    // greater-than comparison
}

if (@ptnum < 50) {
    // less-than comparison
}

if (@name == "piece5") {
    // equality comparison — use == not =
}
// `==` tests equality; `=` assigns. Mixing them is a common bug.
```


### Conditional statements and channel references

```vex
int ifoo;
if (ifoo == 5) {
    // do something
}

vector bbox = relpointbbox(0, @P);
@Cd = {1, 0, 0};
if (bbox.y < 0.5) {
    @Cd = {0, 1, 0};
}
// Combining conditional syntax with channel references and bounding-box queries.
```


### Logical Operators and Nested Conditionals

```vex
// Float equality: compare with epsilon
if (abs(foo - bar) < 0.00001) {
    // close enough to treat as equal
    // works correctly for negative numbers too
}

// Nested equivalent to &&
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1, 0, 0};
    }
}

// Flat AND form
if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1, 0, 0};
}
// Epsilon comparison for floats; AND/OR logical operators; nested vs flat forms.
```


### Logical Operators AND and OR (expanded)

```vex
// Epsilon equality check
if (abs(foo - bar) < 0.00001) {
    // close enough — also handles negatives correctly
}

// Nested if (equivalent to &&)
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1, 0, 0};
    }
}

// Flat AND
if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1, 0, 0};
}

// OR
if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1, 0, 0};
}
// `&&` requires both conditions; `||` requires either one.
```


### Modulo Conditionals and Order of Operations

```vex
// Without braces (single-statement body)
if (@ptnum != 5)
    @Cd = {1, 0, 0};

// With braces (preferred)
if (@ptnum != 5) {
    @Cd = {1, 0, 0};
}

// Modulo: every 5th point
if (@ptnum % 5 == 0) {
    @Cd = {1, 0, 0};
}
// `!= ` is not-equal. Modulo selects periodic points.
```


### Time-based conditional color assignment

```vex
if (length(@P) * 2 + @ptnum % 5 > dot(@N, {0, 1, 0}) * @Time) {
    @Cd = {1, 0, 0};
}
// Compares a position/index expression against a time-scaled dot-product.
```


### Complex conditional with time-based comparison

```vex
if (length(@P) * 2 + @ptnum % 5 > dot(@N, {0, 1, 0}) * @Time) {
    @Cd = {1, 0, 0};
}
// Left side: position length + modulo index. Right side: normal dot-product scaled by time.
```


### Random Primitive Removal

```vex
if (rand(@primnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
// Per-primitive random removal using seed and cutoff channels.
```


### Random Primitive Removal (integer primnum)

```vex
if (rand(i@primnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
// Cast `@primnum` to int explicitly before passing to `rand()`.
```


### If-Else Conditional Logic

```vex
int a = 3;
int b = 3;

if (a == b) {
    @Cd = {1, 1, 0};
} else {
    @Cd = {1, 0, 0};
}
// Basic if-else comparing two integers.
```


### Logical Operators AND and OR (nested vs flat)

```vex
// Nested form
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1, 0, 0};
    }
}

// Flat AND form
if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1, 0, 0};
}

// OR form
if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1, 0, 0};
}
// Nested ifs are equivalent to `&&`. Use `||` for OR logic.
```


### Conditional Coloring with Complex Expression

```vex
if (length(@P) * 2 + @ptnum % 5 > dot(@N, {0, 1, 0}) * @Time) {
    @Cd = {1, 0, 0};
}
// Compound expression: position + index modulo vs normal dot-product × time.
```


### Creating Points with addpoint

```vex
// Store returned point number
int pt = addpoint(0, {0, 1, 0});

// Only create on point 0 (runs once)
if (@ptnum == 0) {
    addpoint(0, {0, 1, 0});
}
// `addpoint()` returns the new point's index. Guard with `@ptnum == 0` to avoid duplicates.
```


### addpoint return value storage

```vex
// addpoint returns the new point index
int pt = addpoint(0, {0, 1, 0});

// Create on input 1 only from point 0
if (@ptnum == 0) {
    addpoint(1, {0, 1, 0});
}
// Store return value to reference the new point later (e.g., for setpointattrib).
```


### Conditional Point Creation

```vex
if (@ptnum == 0) {
    addpoint(0, {0, 0, 0});
}
// Add a single point at the origin, guarded to run only once.
```


### Random Point Removal with Seed

```vex
// Simple random removal
if (rand(@ptnum) < ch('cutoff')) {
    removepoint(0, @ptnum);
}

// Seeded random removal
if (rand(@ptnum, ch('seed')) < ch('cutoff')) {
    removepoint(0, @ptnum, 1);
}
// Seeded form allows repeatable results via the seed channel.
```


### Random Primitive Deletion

```vex
if (rand(@ptnum) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
// Random threshold to delete primitives; channel slider controls density.
```


### Random Primitive Removal with Seed Control

```vex
if (rand(@primuv, ch('seed')) < ch('cutoff')) {
    removepoint(0, @primuv, 1);
}
// Uses primitive UV for randomness source with seeded control.
```


### Random Primitive Removal (no-brace form)

```vex
if (rand(@primnum, ch('seed')) < ch('chance'))
    removepoint(0, @primnum, 1);
// Single-statement body without braces — valid but less readable.
```


### Common Syntax Error: Missing Brackets

```vex
// Correct: brackets closed
if (rand(@primnum, ch('seed')) < ch('cutoff')) {
    removepoint(0, @primnum, 1);
}

// Common error: missing closing brace
// if (rand(@primnum, ch('seed')) < ch('cutoff')) {
//     removepoint(0, @primnum, 1);
// <-- missing }
// Always close every `{` with a matching `}`. Compiler error if omitted.
```


### Random Primitive Removal (removeprim variant)

```vex
if (rand(@primnum, ch('seed')) < ch('cutoff')) {
    removeprim(0, @primnum, 1);
}
// `removeprim` vs `removepoint` — use the one matching what you want to delete.
```


### Random Primitive Removal (double-quoted channels)

```vex
if (rand(@primnum, ch("seed")) < ch("cutoff")) {
    removeprim(0, @primnum, 1);
}
// Single or double quotes are both valid for channel name strings.
```


### getsmoothP

```vex
// Shadow shader using getsmoothP for smooth surface position
shadow fastshadow() {
    vector surfP;
    if (!getsmoothP(surfP, Eye, I)) {
        // Fall back to surface P if smooth P unavailable
        surfP = Ps;
    }
    vector shad = trace(
        surfP,
        normalize(L),
        Time,
        "raystyle", "shadow"
    );
    Cl *= ({1, 1, 1} - shad);
}
// `getsmoothP` retrieves interpolated surface position for shadow rays; fall back to `Ps` on failure.
```


### lightstate

```vex
vector Cd;
if (!lightstate("packed:Cd", Cd)) {
    // No Cd attribute on packed geometry — use default white
    Cd = 1;
}
// `lightstate` queries light/object properties; returns 0 on failure so `!` triggers the fallback.
```


### objectstate

```vex
vector Cd;
if (!objectstate("packed:Cd", Cd)) {
    // No Cd attribute on packed geometry — use default white
    Cd = 1;
}
// `objectstate` queries object properties at shading time; same pattern as lightstate.
```


### renderstate

```vex
vector Cd;
if (!renderstate("packed:Cd", Cd)) {
    // No Cd attribute on packed geometry — use default white
    Cd = 1;
}
// `renderstate` queries renderer global properties; returns 0 when property is absent.
```


### sample_geometry

```vex
surface geolight(int nsamples = 64) {
    vector sam;
    vector clr, pos;
    float angle, sx, sy;
    int sid;
    int i;

    sid = newsampler();
    Cf = 0;

    for (i = 0; i < nsamples; i++) {
        nextsample(sid, sx, sy, "mode", "qstrat");
        sam = set(sx, sy, 0.0);

        if (sample_geometry(
                P, sam, Time,
                "distribution", "solidangle",
                "scope", "/obj/sphere_object*",
                "ray:solidangle", angle,
                "P", pos,
                "Cf", clr)) {

            if (!trace(
                    P,
                    normalize(pos - P),
                    Time,
                    "scope", "/obj/sphere_object*",
                    "maxdist", length(pos - P) - 0.01)) {

                clr *= angle / (2 * PI);
                clr *= max(dot(normalize(pos - P), normalize(N)), 0);
            } else {
                clr = 0;
            }
        }
        Cf += clr;
    }
    Cf /= nsamples;
}
// Area light sampling loop: `sample_geometry` picks surface points, `trace` checks occlusion, then accumulates irradiance.
```


### teximport

```vex
matrix ndc;
if (teximport(map, "texture:worldtoNDC", ndc)) {
    vector P_ndc = pos * ndc;

    // Dehomogenize if perspective camera
    if (getcomp(ndc, 2, 3) != 0) {
        P_ndc.x = P_ndc.x / P_ndc.z;
        P_ndc.y = P_ndc.y / P_ndc.z;
    }

    // Scale and offset XY from [-1,1] to [0,1]
    P_ndc *= {.5, .5, 1};
    P_ndc += {.5, .5, 0};
}
// `teximport` reads the world-to-NDC matrix from a texture; the conditional guards against missing metadata.
```


## Advanced (5 examples)

### Logical Operators AND and OR

```vex
// OR: either condition
if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1, 0, 0};
}

// Equivalent nested form
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1, 0, 0};
    }
}

// OR form
if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1, 0, 0};
}
// `&&` requires both conditions true; `||` requires at least one.
```


### Comparison Operators and Modulo

```vex
if (@ptnum >= 5) {
    @Cd = {1, 0, 0};
}

if (@ptnum > 50 && @P.x < 2) {
    @Cd = {1, 0, 0};
}

if (@ptnum <= 10) {
    @Cd = {0, 1, 0};
}

if (@ptnum != 0) {
    @Cd = {0, 0, 1};
}

if (@ptnum % 3 == 0) {
    @Cd = {1, 1, 0};
}
// All comparison operators: `>=`, `<=`, `!=`, and modulo `%` for periodic selection.
```


### Comparison and Modulo Operators

```vex
if (@ptnum == 5) {
    @Cd = {1, 0, 0};
}

if (@ptnum > 50 || @P.x < 2) {
    @Cd = {1, 0, 0};
}

if (@ptnum != 5) {
    @Cd = {0, 1, 0};
}

if (@ptnum % 2 == 0) {
    @Cd = {0, 0, 1};
}
// Full set of comparison operators: `==`, `!=`, `>`, `<`, `>=`, `<=` and logical OR.
```


### Conditional Operators Comparison

```vex
// Nested
if (@ptnum > 50) {
    if (@P.x > 2) {
        @Cd = {1, 0, 0};
    }
}

// AND
if (@ptnum > 50 && @P.y < 2) {
    @Cd = {1, 0, 0};
}

// OR
if (@ptnum < 10 || @P.z > 5) {
    @Cd = {0, 1, 0};
}

// NOT EQUAL
if (@ptnum != 0) {
    @Cd = {0, 0, 1};
}
// All conditional operator forms: nested, `&&`, `||`, `!=`, `>=`, `<=`.
```


### Comparison Operators in Conditionals

```vex
// Greater than / less than
if (@ptnum > 50) {
    if (@P.x < 2) {
        @Cd = {1, 0, 0};
    }
}

// AND with different axis
if (@ptnum > 50 && @P.y < 2) {
    @Cd = {1, 0, 0};
}

// Not equal
if (@ptnum != 0) {
    @Cd = {0, 1, 0};
}

// Less than or equal
if (@ptnum <= 5) {
    @Cd = {0, 0, 1};
}

// Greater than or equal
if (@P.y >= 1.0) {
    @Cd = {1, 1, 0};
}
// All six comparison operators: `>`, `<`, `!=`, `<=`, `>=`, `==`.
```

