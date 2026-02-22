# SOP Solver and Feedback Loops

## Triggers
solver, sop solver, feedback loop, frame by frame, growth, accumulation,
prev_frame, trail, custom simulation, reaction diffusion, wave, particle

## Context
SOP Solver and Solver SOP enable frame-by-frame feedback loops: output of
frame N feeds back as input to frame N+1. All code is Houdini Python and VEX.

## Code

```python
# Create a solver SOP with feedback loop
import hou

def create_solver_network(geo_path, source_node_name):
    """Create a solver SOP wired to a source node.
    Solver: frame 1 takes input as starting state.
    Frame N>1: takes OUTPUT of frame N-1 as input.
    Inside: Prev_Frame gives last frame's output, Input_1 gives original input."""
    geo = hou.node(geo_path)
    source = geo.node(source_node_name)
    if not geo or not source:
        return

    solver = geo.createNode("solver", "feedback_sim")
    solver.setInput(0, source)

    # Inside the solver: Prev_Frame and Input_1 are automatic
    # Add wrangles inside for per-frame operations
    solver_net = solver.node("d/s")  # Solver's internal network
    if solver_net:
        prev = solver_net.node("Prev_Frame")
        # Wrangle operates on previous frame's output
        wrangle = solver_net.createNode("attribwrangle", "per_frame_op")
        wrangle.setInput(0, prev)
        wrangle.parm("snippet").set('// Per-frame operation here\n@P += normalize(@P) * ch("speed") * @TimeInc;\n')
        solver_net.layoutChildren()

    # Cache after solver
    cache = geo.createNode("filecache", "solver_cache")
    cache.setInput(0, solver)
    cache.parm("sopoutput").set("$HIP/cache/solver.$F4.bgeo.sc")

    null = geo.createNode("null", "OUT")
    null.setInput(0, cache)
    null.setDisplayFlag(True)
    null.setRenderFlag(True)

    geo.layoutChildren()
    print("Solver: source -> solver (Prev_Frame -> wrangle) -> cache -> OUT")
    print("Key: must play forward from start frame (no random scrub)")
    return solver


create_solver_network("/obj/geo1", "scatter_pts")
```

```vex
// Point growth: move points outward each frame
// Inside solver wrangle, run over Points
@P += normalize(@P) * ch("growth_speed") * @TimeInc;

// Scale growth by noise for organic variation
float noise_val = noise(@P * ch("freq") + @Time * 0.5);
@P += normalize(@P) * noise_val * ch("growth_speed") * @TimeInc;
```

```vex
// Trail / motion history: accumulate point positions over time
// Inside solver wrangle, run over Detail
// Input 0 = Prev_Frame (accumulated trail), Input 1 = Input_1 (source)

// Add current position of source as new point
int npts_source = npoints(1);
for (int i = 0; i < npts_source; i++) {
    vector pos = point(1, "P", i);
    int pt = addpoint(0, pos);
    setpointattrib(0, "age", pt, 0.0);
    setpointattrib(0, "source_id", pt, i);
}

// Age existing points and remove old ones
float max_age = ch("max_age");  // e.g., 2.0 seconds
for (int i = npoints(0) - 1; i >= 0; i--) {
    float age = point(0, "age", i);
    age += @TimeInc;
    if (age > max_age) {
        removepoint(0, i);
    } else {
        setpointattrib(0, "age", i, age);
    }
}
```

```vex
// Accumulation / painting: build up attribute based on proximity
// Inside solver wrangle, run over Points
// Input 1 = Input_1 (animated emitter geometry)

int pts[] = pcfind(1, "P", @P, ch("radius"), 1);
if (len(pts) > 0) {
    f@painted = min(f@painted + ch("paint_rate") * @TimeInc, 1.0);
}
// painted accumulates over time, clamped at 1.0
v@Cd = set(f@painted, 1.0 - f@painted, 0);  // Visualize as color
```

```vex
// Custom particle system: emit, integrate, kill
// Inside solver -- TWO wrangles needed

// Wrangle 1: Emitter (run over Detail)
// Input 1 = Input_1 (emitter geometry)
for (int i = 0; i < chi("emit_count"); i++) {
    int src_pt = int(rand(i + @Frame * 137) * npoints(1));
    vector pos = point(1, "P", src_pt);
    int pt = addpoint(0, pos);
    vector vel = set(0, ch("emit_speed"), 0);
    vel += (vector(rand(pt * 3)) - 0.5) * ch("spread");
    setpointattrib(0, "v", pt, vel);
    setpointattrib(0, "age", pt, 0.0);
    setpointattrib(0, "pscale", pt, 0.05);
}
```

```vex
// Wrangle 2: Integrator (run over Points, after emitter wrangle)
// Apply gravity, integrate position, kill old particles
v@v += set(0, -9.81, 0) * @TimeInc;      // Gravity
@P += v@v * @TimeInc;                      // Euler integration
f@age += @TimeInc;

// Kill conditions
if (@P.y < ch("ground_y")) removepoint(0, @ptnum);
if (f@age > ch("max_life")) removepoint(0, @ptnum);
```

```vex
// Wave propagation on a grid
// Inside solver wrangle, run over Points
// Requires: f@height (current), f@height_prev (previous frame)
// Start: perturb center point's height on frame 1

float c = ch("wave_speed");   // Wave propagation speed
float damping = ch("damping"); // Energy loss per frame

// Laplacian: average of neighbor heights minus current
int neighbors[] = neighbours(0, @ptnum);
float avg = 0;
foreach (int n; neighbors) {
    avg += point(0, "height", n);
}
avg /= max(len(neighbors), 1);

float laplacian = avg - f@height;

// Wave equation: acceleration = c^2 * laplacian
float new_height = 2.0 * f@height - f@height_prev + c * c * laplacian;
new_height *= (1.0 - damping * @TimeInc);  // Damping

f@height_prev = f@height;
f@height = new_height;
@P.y = f@height;
```

```python
# SOP Solver in DOPs: custom logic inside DOP simulations
import hou

def add_sop_solver_to_dop(dopnet_path, existing_solver_name):
    """Add a SOP solver node after an existing DOP solver.
    SOP solver runs a SOP network each timestep on simulation geometry."""
    dopnet = hou.node(dopnet_path)
    if not dopnet:
        return

    existing = dopnet.node(existing_solver_name)
    if not existing:
        return

    # Create SOP solver DOP
    sop_solver = dopnet.createNode("sopsolver", "custom_forces")

    # Wire: existing_solver -> sop_solver -> output
    # Find what existing solver connects to
    outputs = existing.outputs()
    for out_node in outputs:
        for i in range(out_node.inputs().__len__()):
            if out_node.inputs()[i] == existing:
                out_node.setInput(i, sop_solver)
    sop_solver.setInput(0, existing)

    dopnet.layoutChildren()
    print(f"SOP solver '{sop_solver.name()}' added after '{existing_solver_name}'")
    print("Edit the SOP network inside to add custom per-timestep logic")
    return sop_solver


add_sop_solver_to_dop("/obj/fx_geo/dopnet1", "pyrosolver")
```

```python
# Reaction-diffusion setup using solver
import hou

def create_reaction_diffusion(geo_path, grid_size=100, grid_res=200):
    """Set up Gray-Scott reaction-diffusion on a grid using solver."""
    geo = hou.node(geo_path)
    if not geo:
        return

    # Grid with initial conditions
    grid = geo.createNode("grid", "rd_grid")
    grid.parm("sizex").set(grid_size)
    grid.parm("sizey").set(grid_size)
    grid.parm("rows").set(grid_res)
    grid.parm("cols").set(grid_res)

    # Initialize A=1, B=0 with random seed region
    init = geo.createNode("attribwrangle", "init_chemicals")
    init.setInput(0, grid)
    init.parm("snippet").set('''
f@A = 1.0;
f@B = 0.0;
// Seed region in center
float d = length(set(@P.x, @P.z, 0));
if (d < ch("seed_radius")) {
    f@B = 1.0;
    f@A = 0.0;
}
''')

    # Solver with reaction-diffusion wrangle
    solver = geo.createNode("solver", "rd_solver")
    solver.setInput(0, init)

    # Cache
    cache = geo.createNode("filecache", "rd_cache")
    cache.setInput(0, solver)
    cache.parm("sopoutput").set("$HIP/cache/rd.$F4.bgeo.sc")

    geo.layoutChildren()
    print("Reaction-diffusion: grid -> init -> solver -> cache")
    print("Inside solver: add wrangle with Gray-Scott diffuse+react equations")
    return solver


create_reaction_diffusion("/obj/geo1")
```

## Common Mistakes
- Using Input_1 instead of Prev_Frame for feedback -- geometry disappears on frame 2
- Scrubbing backward in timeline -- solver must play forward from start frame
- Adding geometry without removing old -- exponential slowdown each frame
- Not scaling velocities by @TimeInc -- results change with different FPS
- Solver inside for-each loop -- extremely slow; use single solver with piece-aware logic
- Non-deterministic operations inside solver -- use @ptnum or @id based seeds, not rand() alone
