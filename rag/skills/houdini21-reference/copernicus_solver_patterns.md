# Copernicus Solver & Feedback Patterns — Houdini 21

Block Begin/End architecture for iterative image processing, growth, reaction-diffusion, and 2D fluid.

## Block Begin / Block End Architecture

```
Block Begin
  Input 0 (Primary): initial state / source image
  Input 1 (Feedback): previous iteration output (auto-wired from Block End)
  Input 2 (Passthrough): data that flows through unchanged

Block End
  Parameters:
    iterations:      sub-steps per frame (int)
    simulate:        ON = frame-dependent, enables scrubbing/caching
    live_simulation: ON = continuous real-time playback
    method:          "feedback" for iterative processing (display: "Feedback Loop")
```

### Wiring Convention

```
                  +----------------------------+
                  |                            |
Source -> Block Begin -> [processing] -> Block End -> Output
              |                              ^
              | feedback port                |
              +------------------------------+
```

### Multi-Field Solvers via Cables

```
Feedback and passthrough inputs accept cables (multi-layer bundles).
This enables coupled multi-field dynamics:

Example — Growth with Direction:
  Cable: [growth_state, direction_field, density_map]
  All three fed back each iteration
  Each field reads the others for coupled dynamics
```

### Invoke COP (External Solver Control)

```
Invoke COP:
  - References a Block Begin/End pair
  - Controls iteration count from outside the block
  - Use when: calling the solver from a different network branch
```

## Growth Propagation (DLA-style)

### Network Architecture

```
seed_mask (Mono) -----------------------------------------+
direction_field (UV, optional) ----------------------+    |
                                                     |    |
                                                     v    v
                                                Block Begin
                                                     |
                                            +--------+
                                            |        |
                                            |   OpenCL: expand
                                            |   (grow active pixels
                                            |    into neighbors)
                                            |        |
                                            |   OpenCL: distance
                                            |   (distance from front
                                            |    for color mapping)
                                            |        |
                                            |   Color Ramp
                                            |   (map distance->color)
                                            |        |
                                            +----> Block End --> Output

Feedback: growth state (mono layer)
```

### Growth Kernel

```c
#bind layer state? val=0          // Current growth state (feedback)
#bind layer seed? val=0           // Initial seed mask
#bind layer direction? val=0      // Optional direction field (UV)
#bind layer !dst
#bind parm float threshold val=0.5
#bind parm float randomness val=0.3
#bind parm int seed_val val=42

// GPU-friendly hash for per-pixel randomness
float hash(float2 p) {
    float3 p3 = fract((float3)(p.x, p.y, p.x) * 0.1031f);
    p3 += dot(p3, p3.yzx + 33.33f);
    return fract((p3.x + p3.y) * p3.z);
}

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float current = @state.x;

    // Already grown — preserve
    if (current > 0.5f || @seed.x > 0.5f) {
        @dst = (float4)(1.0f, 0.0f, 0.0f, 1.0f);
        return;
    }

    // Count active neighbors in 8-connected grid
    int active_neighbors = 0;
    float2 avg_dir = (float2)(0.0f);

    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            if (dx == 0 && dy == 0) continue;
            int2 npos = clamp(pos + (int2)(dx, dy),
                              (int2)(0),
                              (int2)(@xres-1, @yres-1));
            // Sample neighbor state
            float ns = @state.x;  // at npos offset
            if (ns > 0.5f) {
                active_neighbors++;
                avg_dir += (float2)((float)dx, (float)dy);
            }
        }
    }

    // Growth probability based on neighbor count + direction
    float prob = 0.0f;
    if (active_neighbors > 0) {
        prob = @threshold;

        // Directional bias from UV field
        float2 dir = @direction.xy;
        if (length(dir) > 0.01f) {
            float2 growth_dir = normalize(avg_dir);
            float alignment = dot(normalize(dir), growth_dir);
            prob *= (1.0f + alignment) * 0.5f;
        }

        // Stochastic jitter
        float r = hash((float2)(pos.x + @seed_val, pos.y));
        prob += (r - 0.5f) * @randomness;
    }

    float result = (prob > 0.5f) ? 1.0f : 0.0f;
    @dst = (float4)(result, 0.0f, 0.0f, 1.0f);
}
```

### Growth Parameter Guide

```
Growth Speed (threshold):
  0.1 - 0.3: Slow, crystal-like branching
  0.3 - 0.6: Balanced organic growth
  0.6 - 1.0: Fast, explosive expansion

Branching Density (neighbor count threshold):
  1 neighbor required:  Dense, filled growth
  2 neighbors required: Moderate branching
  3+ neighbors:         Thin, sparse branches (dendrites)

Randomness:
  0.0:       Deterministic smooth wavefront
  0.1 - 0.3: Natural organic variation
  0.5+:      Chaotic rough edges

Direction Bias (UV field strength):
  0.0: Omnidirectional
  0.5: Preferential + branching
  1.0: Strongly directional (vein-like)

Seed Placement Strategies:
  Point seeds:   Growth from specific locations
  Edge seeds:    Growth from image borders
  Noise seeds:   Random scattered origins
  Mask seeds:    Growth from arbitrary regions
```

### Growth Variations

```
DLA (Diffusion Limited Aggregation):
  Random walk + aggregate on contact
  Result: fractal branches, lightning, coral

Cellular Automata:
  Rule-based expansion (Game of Life style)
  Result: organic patterns, crystal growth

Directional Growth:
  Bias expansion via UV field
  Result: veins, cracks following stress lines
```

### Animation Strategies

```
Method 1: Frame simulation (Simulate ON)
  1-4 iterations per frame, growth evolves over time
  Best for: organic reveals, natural growth

Method 2: Static with animated parameters
  High iterations, recompute per frame
  Animate seed position, threshold, direction
  Best for: looping motion graphics

Method 3: Growth + dissolve cycle
  Forward growth -> hold -> reverse erode
  Best for: breathing/pulsing organic effects
```

## Reaction-Diffusion (Gray-Scott Model)

### Built-in Copernicus Parameters

```
Feed rate (f):     0.01 - 0.08 typical
Kill rate (k):     0.04 - 0.07 typical
Diffusion A (dA):  1.0 (fast diffuser)
Diffusion B (dB):  0.5 (slow diffuser)
Time step (dt):    1.0

Pattern Map (f, k parameter space):
  f=0.02, k=0.05 -> spots (mitosis)
  f=0.04, k=0.06 -> stripes (worms)
  f=0.03, k=0.06 -> labyrinthine (maze)
  f=0.06, k=0.06 -> coral / branching worms
```

### Custom Gray-Scott OpenCL

```c
#bind layer A? val=1           // Chemical A concentration (feedback)
#bind layer B? val=0           // Chemical B concentration (feedback)
#bind layer !outA
#bind layer !outB
#bind parm float feed val=0.04
#bind parm float kill val=0.06
#bind parm float dA val=1.0
#bind parm float dB val=0.5
#bind parm float dt val=1.0

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));
    float a = @A.x;
    float b = @B.x;

    // Discrete Laplacian (5-point stencil)
    float lapA = 0.0f, lapB = 0.0f;
    float center_weight = -4.0f;

    // Sample 4 cardinal neighbors
    int2 offsets[4] = {
        (int2)(1,0), (int2)(-1,0),
        (int2)(0,1), (int2)(0,-1)
    };

    for (int i = 0; i < 4; i++) {
        int2 npos = clamp(pos + offsets[i],
                          (int2)(0), (int2)(@xres-1, @yres-1));
        lapA += @A.x;  // at npos
        lapB += @B.x;  // at npos
    }
    lapA += center_weight * a;
    lapB += center_weight * b;

    // Gray-Scott reaction equations
    float reaction = a * b * b;
    float newA = a + (@dA * lapA - reaction + @feed * (1.0f - a)) * @dt;
    float newB = b + (@dB * lapB + reaction - (@kill + @feed) * b) * @dt;

    @outA = (float4)(clamp(newA, 0.0f, 1.0f), 0.0f, 0.0f, 1.0f);
    @outB = (float4)(clamp(newB, 0.0f, 1.0f), 0.0f, 0.0f, 1.0f);
}
```

## Flow Block (2D Fluid Solver) — Houdini 21

### Architecture

```
Flow Block Begin ---- [force nodes] ---- Flow Block End

Auto-feedback fields:
  - Color (advected pigment)
  - Velocity (UV field)
  - Temperature (scalar)

Additional feedback via cable input for custom fields.
```

### Available Force Nodes

```
Buoyancy:        temperature -> upward velocity
Vorticity:       curl confinement, preserves swirls
Turbulence:      noise-driven velocity perturbation
Axis Force:      rotation around center point
Custom Velocity: user-defined UV field as force input
```

### License Requirement

```
Flow Blocks + Pyro COPs require DOP-level license:
  OK: Houdini FX, Indie, Apprentice, Education
  NO: Houdini Core
```

## Iteration vs Frame Count

```
Iterations (sub-steps per frame):
  High -> smoother simulation, slower per-frame cook
  Use for: fast phenomena, numerical stability
  Start with: 1-4, increase only if unstable

Frame count (temporal evolution):
  More frames -> more VRAM for cache
  Use for: temporal evolution, animation
```

## Caching Strategy

```
Simulate ON, Live OFF:
  Frame bar controls simulation
  Houdini caches frames in memory
  Scrubbing works (within cached range)

Live Simulation ON:
  Continuous playback, no scrubbing
  Great for interactive exploration

For SYNAPSE batch processing:
  Simulate ON, Live OFF
  Cook frame range via Python
  Export specific frames as EXR via File COP
```

## Memory Management

```
Memory per cached frame (4K = 4096x4096 square texture):
  1 Mono field, 4K, 32-bit float = 64 MB
  3 Mono fields, 4K, 32-bit float = 192 MB
  3 Mono fields, 4K, 32-bit, 100 frames = ~19 GB

Solutions for large simulations:
  1. Checkpoint to disk (File COP at intervals)
  2. Simulate at lower res, upres after
  3. Use 16-bit precision (half) where possible
  4. Limit cache frame range in Block End
  5. Clear cache between shots
```

## Distance Field Post-Process (After Growth)

```
After growth completes, compute distance for color mapping:

1. Run JFA (Jump Flooding) in separate Block solver
2. Map distance through color ramp
3. Result: gradient coloring by growth age/distance

Alternative: iterative dilation with distance tracking
  Each iteration: dilate by 1px, increment distance counter
  Cheaper than JFA, coarser result
  Good enough for ramp mapping
```

## Python: Solver Network Creation

```python
import hou

copnet = hou.node("/obj/copnet1")

# Create Block pair
block_begin = copnet.createNode("block_begin")
block_end = copnet.createNode("block_end")

# Processing node inside the block
opencl = copnet.createNode("opencl")

# Wire: source -> block_begin -> opencl -> block_end
block_begin.setInput(0, source_node)    # Primary input
opencl.setInput(0, block_begin)         # Process feedback
block_end.setInput(0, opencl)           # Close loop

# Configure solver
block_end.parm("method").set("feedback")   # Feedback loop mode
block_end.parm("iterations").set(10)       # Sub-steps per frame
block_end.parm("simulate").set(True)       # Frame-dependent

# Set display flag on block end
block_end.setDisplayFlag(True)
block_end.setRenderFlag(True)
```
