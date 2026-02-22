# VEX Common Patterns and Examples

## Deformation Patterns

### Sine Wave Deformation
```vex
float amp = chf("amplitude");
float freq = chf("frequency");
float offset = chf("offset");
@P.y += sin(@P.x * freq + offset + @Time) * amp;
```

### Noise Displacement Along Normal
```vex
float amp = chf("amplitude");
float freq = chf("frequency");
float n = snoise(@P * freq + @Time * chf("speed"));
@P += @N * n * amp;
```

### Twist Deformation
```vex
float twist_amount = chf("twist") * @P.y;
float c = cos(twist_amount);
float s = sin(twist_amount);
float x = @P.x * c - @P.z * s;
float z = @P.x * s + @P.z * c;
@P.x = x;
@P.z = z;
```

### Taper via Ramp
```vex
float taper = chramp("taper_profile", fit(@P.y, chf("ymin"), chf("ymax"), 0, 1));
@P.x *= taper;
@P.z *= taper;
```

## Color Patterns

### Color by Height
```vex
float t = fit(@P.y, chf("min_height"), chf("max_height"), 0, 1);
@Cd = chramp("color_ramp", t);
```

### Color by Curvature
```vex
int pts[] = neighbours(0, @ptnum);
float curvature = 0;
foreach (int pt; pts) {
    vector n2 = point(0, "N", pt);
    curvature += 1.0 - dot(@N, n2);
}
curvature /= max(len(pts), 1);
@Cd = chramp("curvature_ramp", curvature);
```

### Random Color Per Piece
```vex
int piece = i@piece;
float hue = rand(piece * 13.37);
float sat = fit(rand(piece * 7.13), 0, 1, 0.5, 1.0);
@Cd = hsvtorgb(set(hue, sat, 1.0));
```

## Geometry Generation

### Spiral Points (Detail Wrangle)
```vex
int npts = chi("num_points");
float radius = chf("radius");
float height = chf("height");
float turns = chf("turns");

for (int i = 0; i < npts; i++) {
    float t = float(i) / float(npts - 1);
    float angle = t * turns * 2 * PI;
    float r = radius * (1.0 - t * chf("taper"));
    vector pos = set(cos(angle) * r, t * height, sin(angle) * r);
    int pt = addpoint(0, pos);
    setpointattrib(0, "pscale", pt, lerp(chf("scale_start"), chf("scale_end"), t), "set");
}
```

### Connect Points as Polyline (Detail Wrangle)
```vex
int npts = npoints(0);
if (npts < 2) return;
int prim = addprim(0, "polyline");
for (int i = 0; i < npts; i++) {
    addvertex(0, prim, i);
}
```

### Grid from Scratch (Detail Wrangle)
```vex
int rows = chi("rows");
int cols = chi("cols");
float spacing = chf("spacing");

int pts[];
resize(pts, rows * cols);
for (int r = 0; r < rows; r++) {
    for (int c = 0; c < cols; c++) {
        vector pos = set(c * spacing, 0, r * spacing);
        pts[r * cols + c] = addpoint(0, pos);
    }
}

for (int r = 0; r < rows - 1; r++) {
    for (int c = 0; c < cols - 1; c++) {
        int p0 = pts[r * cols + c];
        int p1 = pts[r * cols + c + 1];
        int p2 = pts[(r+1) * cols + c + 1];
        int p3 = pts[(r+1) * cols + c];
        addprim(0, "poly", p0, p1, p2, p3);
    }
}
```

## Grouping Patterns

### Group by Bounding Box
```vex
vector bmin = chv("bbox_min");
vector bmax = chv("bbox_max");
i@group_inside = (@P.x >= bmin.x && @P.x <= bmax.x &&
                  @P.y >= bmin.y && @P.y <= bmax.y &&
                  @P.z >= bmin.z && @P.z <= bmax.z) ? 1 : 0;
```

### Group by Normal Direction
```vex
vector up = {0, 1, 0};
float threshold = chf("angle_threshold");
i@group_upfacing = (dot(@N, up) > threshold) ? 1 : 0;
```

### Group Every Nth Point
```vex
int n = chi("every_nth");
i@group_selected = (@ptnum % n == 0) ? 1 : 0;
```

## Solver / Simulation Patterns

### Point Advection (Inside SOP Solver)
```vex
vector vel = v@v;
float dt = @TimeInc;
@P += vel * dt;

// Gravity
v@v += {0, -9.81, 0} * dt;

// Ground collision
if (@P.y < 0) {
    @P.y = 0;
    v@v.y = abs(v@v.y) * chf("bounce");
    v@v *= chf("friction");
}
```

### Attribute Decay Over Time
```vex
float decay = chf("decay_rate");
f@temperature *= pow(decay, @TimeInc * 30);  // Frame-rate independent
```

## Transfer / Blend Patterns

### Transfer by Proximity (from input 1)
```vex
float radius = chf("radius");
int pts[] = pcfind(1, "P", @P, radius, chi("maxpts"));

if (len(pts) > 0) {
    float total_w = 0;
    vector total_cd = {0,0,0};
    foreach (int pt; pts) {
        float d = distance(@P, point(1, "P", pt));
        float w = 1.0 - smooth(0, radius, d);
        total_cd += point(1, "Cd", pt) * w;
        total_w += w;
    }
    if (total_w > 0) {
        @Cd = lerp(@Cd, total_cd / total_w, chf("blend"));
    }
}
```

### Smooth / Relax Points
```vex
int pts[] = neighbours(0, @ptnum);
if (len(pts) == 0) return;

vector avg = {0,0,0};
foreach (int pt; pts) {
    avg += point(0, "P", pt);
}
avg /= len(pts);

float strength = chf("smooth_strength");
@P = lerp(@P, avg, strength);
```

### Edge Detection
```vex
int pts[] = neighbours(0, @ptnum);
float max_diff = 0;
foreach (int pt; pts) {
    float diff = abs(@density - point(0, "density", pt));
    max_diff = max(max_diff, diff);
}
f@edge = max_diff;
i@group_edges = (max_diff > chf("edge_threshold")) ? 1 : 0;
```

## fBm Noise Layering
```vex
float n = 0;
float amp = 1.0;
float freq = 1.0;
for (int i = 0; i < chi("octaves"); i++) {
    n += snoise(@P * freq) * amp;
    freq *= 2.0;
    amp *= 0.5;
}
@P += @N * n * chf("amplitude");
```

## See Also
- **Joy of VEX: Deformation** (`joy_of_vex_deformation.md`) -- tutorial examples with wave displacement, ramp-driven deformation
- **Joy of VEX: Noise & Randomness** (`joy_of_vex_noise.md`) -- tutorial examples with snoise, curlnoise patterns
- **Joy of VEX: Geometry Creation** (`joy_of_vex_geometry_creation.md`) -- tutorial examples with addpoint, addprim
