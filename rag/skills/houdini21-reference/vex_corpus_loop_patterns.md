# VEX Corpus: Loop Patterns

## Triggers
for loop, foreach, while, iteration, addpoint loop, addprim, polyline,
vertex index, curve iteration, conditional creation, point creation

## Context
VEX loop patterns: for/foreach/while, point creation in loops,
primitive creation, curve iteration, conditional geometry creation.

## Code

```vex
// Basic for loop syntax
for (int i = 0; i < 10; i++) {
    vector pos = @P + set(i * 0.1, 0, 0);
    addpoint(0, pos);
}
```

```vex
// CRITICAL: addpoint in point wrangle creates per-point duplicates
// WRONG: runs once PER EXISTING POINT, creating N copies
int pt = addpoint(0, {0, 1, 0});

// RIGHT: guard with @ptnum == 0 to create only once
if (@ptnum == 0) {
    int pt = addpoint(0, {0, 1, 0});
}

// RIGHT: use Detail mode for global geometry creation
// Run over Detail:
for (int i = 0; i < chi("count"); i++) {
    addpoint(0, set(i * 0.1, 0, 0));
}
```

```vex
// Create polyline primitives from points
// Run over Detail:
int pts[];
for (int i = 0; i < chi("count"); i++) {
    vector pos = set(cos(radians(i * 36.0)), i * 0.1, sin(radians(i * 36.0)));
    append(pts, addpoint(0, pos));
}
// Create polyline connecting all points
addprim(0, "polyline", pts);
```

```vex
// Create lines from existing points along normals
// Run over Points:
for (int i = 0; i < chi("segments"); i++) {
    int pt = addpoint(0, @P + @N * (i * ch("length")));
    if (i == 0) {
        addprim(0, "polyline", @ptnum, pt);
    } else {
        // Chain points into connected line
    }
}
```

```vex
// Iterate over curves: find median position across multiple curves
// Run over Points (input 0 = single curve, input 1 = many curves)
int curves = nprimitives(1);
vector avg_pos = {0, 0, 0};
for (int curve = 0; curve < curves; curve++) {
    int lv = vertexindex(1, curve, @ptnum);
    vector pos = vertex(1, "P", lv);
    avg_pos += pos;
}
@P = avg_pos / max(curves, 1);
```

```vex
// Foreach over neighbours
int pts[] = neighbours(0, @ptnum);
vector avg = {0, 0, 0};
foreach (int pt; pts) {
    avg += point(0, "P", pt);
}
avg /= max(len(pts), 1);
@P = lerp(@P, avg, ch("smooth_amount"));  // Laplacian smooth
```

```vex
// Iterate unique attribute values
// Run over Detail:
int count = nuniqueval(0, "point", "class");
for (int i = 0; i < count; i++) {
    int val = uniqueval(0, "point", "class", i);
    // Process each unique class value
    printf("Class %d found\n", val);
}
```

```vex
// Random open/closed polygon intrinsic
// Run over Primitives:
int make_open = int(rand(@primnum) * 2);
setprimintrinsic(0, "closed", @primnum, make_open);
```

```vex
// While loop with convergence check
// Run over Points:
vector target = point(1, "P", @ptnum);
int max_iter = chi("max_iterations");
float tolerance = ch("tolerance");
int iter = 0;
while (iter < max_iter) {
    vector delta = target - @P;
    if (length(delta) < tolerance) break;
    @P += delta * ch("step_size");
    iter++;
}
i@iterations = iter;
```

## Common Mistakes
- addpoint in Point mode without @ptnum==0 guard -- creates N copies instead of 1
- Forgetting to use Detail mode for global geometry creation -- Point mode runs per-element
- Growing arrays with append in tight loops -- pre-size with resize() when count is known
- Infinite while loops -- always include max_iter guard and break condition
