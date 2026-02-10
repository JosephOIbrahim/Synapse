# SOP Solver and Feedback Loops

## Overview

SOP Solver and Solver SOP enable frame-by-frame feedback loops in Houdini. The output of frame N feeds back as input to frame N+1, enabling custom simulations, growth, and accumulation effects entirely in SOPs.

## Solver SOP

### What It Does
The `solver` SOP creates a feedback loop:
1. On frame 1: Takes input geometry as starting state
2. On frame N>1: Takes the OUTPUT of frame N-1 as input
3. Inside: SOP network processes geometry each frame
4. Result becomes input for next frame

### Basic Setup
```
source_geo -> solver -> null (output)
```

Inside the solver:
```
prev_frame (automatic) -> [your SOP operations] -> output (automatic)
```

### Key Rules
- **Frame-dependent**: Must play forward from start frame (no random access)
- **Previous frame**: The `Prev_Frame` node inside solver gives last frame's output
- **Input geometry**: Available via `Input_1` node inside solver
- **Cache**: Solver auto-caches recent frames for playback

## Common Solver Patterns

### Point Growth
```vex
// Inside solver wrangle (run over Points):
// Move points outward slowly each frame
@P += normalize(@P) * ch("growth_speed") * @TimeInc;
```

### Trail / Motion History
```vex
// Inside solver wrangle (run over Detail):
// Add current position of input as new point each frame
int pt = addpoint(0, point(1, "P", 0));  // 1 = second input (Input_1)
setpointattrib(0, "age", pt, 0.0);

// Age existing points
float age;
for (int i = 0; i < npoints(0); i++) {
    age = point(0, "age", i);
    setpointattrib(0, "age", i, age + @TimeInc);
}

// Remove old points
if (f@age > ch("max_age")) removepoint(0, @ptnum);
```

### Accumulation (Painting)
```vex
// Inside solver wrangle:
// Accumulate attribute based on proximity to animated emitter
int pts[] = pcfind(1, "P", @P, ch("radius"), 1);  // 1 = Input_1
if (len(pts) > 0) {
    f@painted = min(f@painted + ch("paint_rate") * @TimeInc, 1.0);
}
```

### Custom Particle System
```vex
// Inside solver wrangle (run over Detail):
// Emit from input geometry, simulate gravity, remove when below ground
// Emit
for (int i = 0; i < chi("emit_count"); i++) {
    vector pos = point(1, "P", int(rand(i + @Frame * 100) * npoints(1)));
    int pt = addpoint(0, pos);
    setpointattrib(0, "v", pt, set(0, ch("emit_speed"), 0) + rand(pt) * 0.5);
    setpointattrib(0, "age", pt, 0.0);
}
```

```vex
// Second wrangle inside solver (run over Points):
// Integrate velocity, apply gravity, kill old
v@v += set(0, -9.81, 0) * @TimeInc;
@P += v@v * @TimeInc;
f@age += @TimeInc;
if (@P.y < 0 || f@age > ch("max_life")) removepoint(0, @ptnum);
```

## SOP Solver DOP

For integrating custom SOP logic inside a DOP simulation:
- `sopsolver` DOP node runs a SOP network each timestep
- Input: current simulation geometry
- Output: modified geometry fed back to DOP
- Use for: custom forces, attribute modification, conditional behavior

### In Pyro DOPs
```
pyrosolver -> sopsolver (custom gas operations) -> output
```

### In RBD DOPs
```
rbdsolver -> sopsolver (custom constraint modification) -> output
```

## For-Each with Time Dependency

For-each loops can simulate solver-like behavior for independent pieces:
```
foreach_begin (by pieces) -> [operations] -> foreach_end
```

But for-each is NOT frame-dependent -- it processes all pieces on the current frame only. For true frame-to-frame feedback, use the solver SOP.

## Simulation Caching

### Manual Cache Inside Solver
Add `filecache` after solver to save results:
```
solver -> filecache(file="$HIP/cache/solver.$F4.bgeo.sc")
```

### Solver Cache Settings
- `Cache Memory`: Max memory for in-memory frame cache
- `Allow Caching to Disk`: Overflow to temp files
- `Start Frame`: Frame to initialize from

## Common Solver Recipes

### L-System Growth
```
// Start: single point at origin
// Each frame: branch and extend existing lines
// Wrangle inside solver adds points, creates lines based on rules
```

### Reaction-Diffusion
```
// Start: grid with random f@A and f@B values
// Each frame: diffuse A and B, react based on Gray-Scott model
// Wrangle uses pcfilter for diffusion, math for reaction
```

### Wave Propagation
```
// Start: grid with f@height = 0 everywhere
// Perturb center point
// Each frame: f@height based on neighbors (wave equation)
// f@height_new = 2*@height - @height_prev + c^2 * laplacian
```

### Crowd-like Agent Motion
```
// Start: scattered points with v@v velocity
// Each frame: steer toward goal, avoid neighbors, integrate
// Uses pcfind for neighbor detection
```

## Tips

- Always set a start frame on the solver (defaults to $FSTART)
- Can't randomly scrub -- must play forward from start frame
- For debugging: step frame-by-frame and inspect intermediate state
- Heavy solvers: cache to disk immediately, iterate on playback
- Solver inside for-each: be careful, this is very slow. Usually better to have one solver operating on all pieces.
- `@TimeInc` is the time step per frame (1/$FPS). Always multiply velocities by `@TimeInc` for frame-rate independence.

## Performance Tips

- Keep geometry count low inside solver (grows each frame = exponential slowdown)
- Delete old/dead elements inside the solver wrangle
- Use compiled blocks inside solver for 2-5x speedup
- For large point counts: use pcfind instead of looping over all points
- Cache solver output to disk -- replaying from cache is instant

## Common Solver Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Geometry disappears on frame 2 | Not using Prev_Frame output | Wire from Prev_Frame, not Input_1 |
| Solver resets on scrub | Playing backward or jumping frames | Always play forward from start frame |
| Exponential slowdown | Adding geometry without removing | Delete old elements based on age/condition |
| Different result each play | Non-deterministic operations inside solver | Use `@ptnum` or `@id` based seeds, not `rand()` alone |
| Solver inside for-each is slow | Double iteration overhead | Single solver with piece-aware logic instead |
| Geometry jitters | Velocities not scaled by @TimeInc | Multiply all velocity changes by `@TimeInc` |
