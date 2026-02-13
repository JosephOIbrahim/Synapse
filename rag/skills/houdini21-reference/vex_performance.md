# VEX Performance Optimization

## Core Principles

1. **VEX is parallel** -- each element processes independently. Avoid patterns that serialize.
2. **Minimize I/O** -- reading from other inputs or attributes is slower than local variables.
3. **Reduce function calls** -- cache results, avoid redundant lookups.
4. **Use squared distances** -- `distance2()` and `length2()` avoid `sqrt()`.

## Fast vs Slow Patterns

### Spatial Queries
```vex
// SLOW: nearpoints iterates all points O(n)
int pts[] = nearpoints(0, @P, radius);

// FAST: pcfind uses KD-tree O(log n)
int pts[] = pcfind(0, "P", @P, radius, maxpts);

// FASTEST: pcopen/pcfilter for aggregation (no array allocation)
int handle = pcopen(0, "P", @P, radius, maxpts);
float avg_density = pcfilter(handle, "density");
pcclose(handle);
```

### Attribute Access
```vex
// SLOW: reading attribute by name every iteration
for (int i = 0; i < npoints(0); i++) {
    float d = point(0, "density", i);  // String lookup each time
}

// FAST: use @-binding (compiled direct access)
float d = @density;  // Direct memory offset

// FAST: cache reads outside loops
vector my_pos = @P;
int pts[] = neighbours(0, @ptnum);
foreach (int pt; pts) {
    float d = distance(my_pos, point(0, "P", pt));
}
```

### Distance Comparisons
```vex
// SLOW: uses sqrt internally
if (distance(@P, target) < radius) { ... }

// FAST: compare squared values
float r2 = radius * radius;
if (distance2(@P, target) < r2) { ... }
```

### Branching
```vex
// SLOW: complex branching kills SIMD
if (complex_condition_1) { /* large block A */ }
else if (complex_condition_2) { /* large block B */ }

// FAST: use lerp/smooth for branchless blends
float mask = smooth(0.3, 0.7, @density);
@P += dir * mask;
```

### Loop Patterns
```vex
// SLOW: dynamic array growth (realloc)
int result[] = {};
for (int i = 0; i < 10000; i++) {
    append(result, i);
}

// FAST: pre-size array
int result[];
resize(result, 10000);
for (int i = 0; i < 10000; i++) {
    result[i] = i;
}
```

## Run-Over Mode Selection

| Mode | Best For | Avoid When |
|------|----------|------------|
| Points | Per-point operations, attribute modification | Need prim topology |
| Primitives | Per-face operations, prim attributes | Processing individual points |
| Detail | Global aggregation, single-pass counts | Per-element processing |
| Vertices | UV operations, per-corner data | Simple point/prim operations |

Detail + explicit loops is sometimes faster for small geometry with complex inter-element dependencies (avoids parallel overhead).

## Compilation and JIT

VEX compiles once, runs in parallel. First cook is slower (compilation), subsequent cooks are fast. Changing wrangle code forces recompilation.

```vex
// ch() changes do NOT trigger recompilation
float radius = chf("radius");   // Fast to adjust at runtime
```

## Common Bottleneck Checklist

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Slow with many points | O(n^2) spatial query | Switch to `pcfind` (KD-tree) |
| Slow first cook | VEX compilation | Cache compiled code, avoid dynamic snippets |
| Memory spike | Large per-element arrays | Use streaming (pcopen/pcfilter) |
| Uniform slowdown | String attribute lookups in loops | Cache outside loop |
| Frame-dependent slowdown | Growing geometry | Profile per-frame, check for leaks |
