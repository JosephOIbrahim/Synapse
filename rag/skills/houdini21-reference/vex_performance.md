# VEX Performance Optimization

## Triggers
performance, optimize, speed, slow, fast, pcfind, pcopen, spatial query,
distance2, length2, bottleneck, profile, KD-tree, parallel

## Context
VEX performance patterns: spatial queries, attribute access, distance
comparisons, branching, loop patterns, compilation behavior.

## Code

```vex
// Spatial queries: O(log n) vs O(n)

// SLOW: nearpoints iterates all points O(n)
int pts_slow[] = nearpoints(0, @P, ch("radius"));

// FAST: pcfind uses KD-tree O(log n)
int pts_fast[] = pcfind(0, "P", @P, ch("radius"), chi("maxpts"));

// FASTEST: pcopen/pcfilter for aggregation (no array allocation)
int handle = pcopen(0, "P", @P, ch("radius"), chi("maxpts"));
float avg_density = pcfilter(handle, "density");
vector avg_pos = pcfilter(handle, "P");
pcclose(handle);
```

```vex
// Attribute access: direct vs string lookup

// SLOW: string lookup each iteration
for (int i = 0; i < npoints(0); i++) {
    float d = point(0, "density", i);  // String lookup each time
}

// FAST: use @-binding (compiled direct memory access)
float d = @density;  // Direct memory offset, no lookup

// FAST: cache reads outside loops
vector my_pos = @P;
int pts[] = neighbours(0, @ptnum);
foreach (int pt; pts) {
    float d = distance(my_pos, point(0, "P", pt));
}
```

```vex
// Distance comparisons: avoid sqrt

// SLOW: distance() uses sqrt internally
if (distance(@P, target) < radius) {
    @Cd = {1, 0, 0};
}

// FAST: compare squared values (no sqrt)
float r2 = radius * radius;
if (distance2(@P, target) < r2) {
    @Cd = {1, 0, 0};
}

// Same for length
float len_slow = length(@v);           // Uses sqrt
float len_fast = length2(@v);          // No sqrt
if (length2(@v) > speed2) { /* ... */ }
```

```vex
// Branching: branchless alternatives for SIMD

// SLOW: complex branching kills SIMD
if (@density > 0.7) {
    @Cd = {1, 0, 0};
} else if (@density > 0.3) {
    @Cd = {1, 1, 0};
} else {
    @Cd = {0, 0, 1};
}

// FAST: use lerp/smooth for branchless blends
float mask = smooth(0.3, 0.7, @density);
@Cd = lerp({0, 0, 1}, {1, 0, 0}, mask);

// FAST: use chramp for complex mappings (branchless)
@Cd = chramp("color_ramp", @density);
```

```vex
// Loop patterns: pre-size arrays

// SLOW: dynamic array growth (realloc each append)
int result[] = {};
for (int i = 0; i < 10000; i++) {
    append(result, i);
}

// FAST: pre-size array, direct index
int result[];
resize(result, 10000);
for (int i = 0; i < 10000; i++) {
    result[i] = i;
}

// FAST: break early when possible
int pts[] = pcfind(0, "P", @P, ch("radius"), 100);
foreach (int pt; pts) {
    if (point(0, "density", pt) > ch("threshold")) {
        f@found = 1;
        break;  // Don't process remaining points
    }
}
```

```vex
// Compilation and ch() behavior
// VEX compiles once, runs in parallel across all elements
// First cook is slower (compilation), subsequent are fast
// Changing wrangle code forces recompilation

// ch() reads do NOT trigger recompilation (fast to adjust at runtime)
float radius = chf("radius");     // Reads spare parm, no recompile
int count = chi("count");         // Same -- runtime parameter

// Avoid string operations in tight loops
// SLOW: sprintf in per-point code
s@label = sprintf("pt_%04d", @ptnum);  // String alloc per point

// FAST: use integer attributes where possible
i@label_id = @ptnum;  // Integer is much cheaper
```

```vex
// Run-over mode selection for performance
// Points:     per-point ops, attribute modification
// Primitives: per-face ops, prim attributes
// Detail:     global aggregation, single-pass counts
// Vertices:   UV operations, per-corner data

// Detail + explicit loops can be faster for small geometry
// with complex inter-element dependencies (avoids parallel overhead)

// Example: find min/max in Detail mode (single pass)
// Run over Detail
float min_y = 1e30;
float max_y = -1e30;
for (int i = 0; i < npoints(0); i++) {
    float y = point(0, "P", i).y;
    min_y = min(min_y, y);
    max_y = max(max_y, y);
}
f@min_y = min_y;
f@max_y = max_y;
```

## Common Mistakes
- O(n^2) spatial queries with nearpoints -- use pcfind (KD-tree) for O(log n)
- String attribute lookups inside loops -- cache values outside the loop
- Using distance() for comparisons -- use distance2() to avoid sqrt
- Complex branching in per-point code -- use lerp/smooth/chramp for branchless
- Dynamic array growth with append -- pre-size with resize() when count is known
- Using VEX wrangle where Detail mode suffices -- Detail avoids parallel overhead for global ops
