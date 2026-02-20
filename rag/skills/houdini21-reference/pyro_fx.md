# Pyro FX Setup Guide

## Triggers
pyro, fire, smoke, explosion, combustion, volume, pyrosolver, density, temperature,
flame, fuel, dissipation, turbulence, disturbance, shredding, volume rendering

## Context
Pyro simulation pipeline in Houdini: source setup, solver configuration, combustion model,
turbulence, caching, and Karma rendering. Includes the simulation guard pattern for safe
DOP operations.

## Code

```python
# Complete pyro pipeline: source -> rasterize -> solver -> cache
import hou

hou.setSimulationEnabled(False)
try:
    geo = hou.node("/obj/pyro_fx")
    if not geo:
        geo = hou.node("/obj").createNode("geo", "pyro_fx")

    # Step 1: Source geometry (emission points)
    sphere = geo.createNode("sphere", "source_shape")
    sphere.parm("radx").set(0.5)

    # Step 2: Scatter points on surface for emission
    scatter = geo.createNode("scatter", "emission_pts")
    scatter.setInput(0, sphere)
    scatter.parm("npts").set(1000)

    # Step 3: Set emission attributes via wrangle
    wrangle = geo.createNode("attribwrangle", "emission_attrs")
    wrangle.setInput(0, scatter)
    wrangle.parm("snippet").set('''
// Source attributes for pyro emission
f@density = 1.0;           // smoke density
f@temperature = 2.0;       // heat (drives buoyancy)
f@flame = 1.0;             // visible flame
f@fuel = 0.8;              // combustible fuel
f@pscale = 0.05;           // REQUIRED for volume rasterize radius
v@v = set(0, 3, 0);        // upward velocity for rising smoke
''')

    # Step 4: Convert points to volume fields
    rasterize = geo.createNode("volumerasterizeattributes", "to_volume")
    rasterize.setInput(0, wrangle)
    rasterize.parm("attributes").set("density temperature flame fuel")

    # Step 5: DOP network with pyro solver
    dopnet = geo.createNode("dopnet", "pyro_sim")

    smoke_obj = dopnet.createNode("smokeobject", "pyro_container")
    smoke_obj.parm("divsize").set(0.05)            # Voxel size
    smoke_obj.parm("initialSOP").set(rasterize.path())

    solver = dopnet.createNode("pyrosolver", "solver")
    solver.parm("timescale").set(1.0)
    solver.parm("dissipation").set(0.1)            # Smoke fade rate
    solver.parm("tempcooling").set(0.5)            # Flame cooling
    solver.parm("buoyancy").set(1.0)               # Upward force
    solver.parm("resize_padding").set(0.5)         # Container growth
    solver.parm("enable_disturbance").set(1)
    solver.parm("disturbance").set(0.4)            # Turbulence
    solver.parm("shredding").set(0.2)              # High-freq breakup

    source = dopnet.createNode("sopscalar", "source_field")
    source.parm("soppath").set(rasterize.path())
    source.parm("fieldname").set("density")

    merge = dopnet.createNode("merge", "sim_merge")
    merge.setInput(0, smoke_obj)
    merge.setInput(1, solver)
    merge.setInput(2, source)
    merge.setDisplayFlag(True)

    dopnet.layoutChildren()
    geo.layoutChildren()
    print(f"Pyro pipeline created at {geo.path()}")

finally:
    hou.setSimulationEnabled(True)
```

```vex
// Source wrangle -- emission attributes for different fire types
// Run over Points on scatter output

// --- Campfire ---
f@density = 1.0;
f@temperature = 2.0;
f@flame = 1.0;
f@fuel = 0.5;
f@pscale = 0.03;
v@v = set(0, 2, 0) + curlnoise(v@P * 3.0) * 0.3;  // slight turbulence

// --- Explosion ---
// f@density = 3.0;
// f@temperature = 5.0;
// f@flame = 2.0;
// f@fuel = 1.5;
// f@pscale = 0.1;
// v@v = normalize(v@P) * 10.0;  // radial outward burst

// --- Cigarette smoke ---
// f@density = 0.3;
// f@temperature = 0.5;
// f@flame = 0;
// f@pscale = 0.02;
// v@v = set(0, 0.5, 0);  // gentle upward drift
```

```python
# Pyro solver tuning presets
import hou

PYRO_PRESETS = {
    "campfire": {
        "dissipation": 0.05,
        "tempcooling": 0.3,
        "buoyancy": 0.8,
        "disturbance": 0.3,
        "shredding": 0.2,
        "divsize": 0.04,
    },
    "explosion": {
        "dissipation": 0.02,
        "tempcooling": 0.1,
        "buoyancy": 2.0,
        "disturbance": 0.8,
        "shredding": 0.5,
        "divsize": 0.05,
    },
    "cigarette_smoke": {
        "dissipation": 0.15,
        "tempcooling": 0.8,
        "buoyancy": 0.3,
        "disturbance": 0.1,
        "shredding": 0.05,
        "divsize": 0.02,
    },
    "industrial_stack": {
        "dissipation": 0.03,
        "tempcooling": 0.5,
        "buoyancy": 1.5,
        "disturbance": 0.4,
        "shredding": 0.15,
        "divsize": 0.06,
    },
    "torch": {
        "dissipation": 0.1,
        "tempcooling": 0.4,
        "buoyancy": 1.0,
        "disturbance": 0.5,
        "shredding": 0.3,
        "divsize": 0.03,
    },
}

def apply_pyro_preset(solver_path, preset_name):
    """Apply a pyro preset to a solver node."""
    solver = hou.node(solver_path)
    if not solver:
        print(f"Solver not found: {solver_path}")
        return

    preset = PYRO_PRESETS.get(preset_name)
    if not preset:
        print(f"Unknown preset: {preset_name}")
        print(f"Available: {list(PYRO_PRESETS.keys())}")
        return

    for parm_name, value in preset.items():
        p = solver.parm(parm_name)
        if p:
            p.set(value)
    print(f"Applied '{preset_name}' preset to {solver_path}")

apply_pyro_preset("/obj/pyro_fx/pyro_sim/solver", "campfire")
```

```vex
// Custom turbulence via Gas Wrangle inside pyro solver
// Create a Gas Wrangle DOP, wire after the solver
vector turb = curlnoise(v@P * ch("turb_scale") + @Time * ch("turb_speed"));
v@vel += turb * ch("turb_strength");

// Temperature-driven turbulence (more breakup in hot areas)
float temp = f@temperature;
float turb_mult = fit(temp, 0, 2, 0.1, 1.0);
v@vel += curlnoise(v@P * 3.0 + @Time * 0.5) * turb_mult * 0.5;
```

```python
# Cache pyro simulation to disk
import hou

def cache_pyro(sim_path, cache_dir="$HIP/cache/pyro"):
    """Cache pyro sim to bgeo.sc for efficient storage."""
    sim_node = hou.node(sim_path)
    if not sim_node:
        print(f"Sim node not found: {sim_path}")
        return

    geo = sim_node.parent()

    cache = geo.createNode("filecache", "pyro_cache")
    cache.setInput(0, sim_node)
    # .bgeo.sc = Blosc compressed, 3-5x smaller than raw for volumes
    cache.parm("sopoutput").set(f"{cache_dir}/pyro.$F4.bgeo.sc")
    cache.parm("trange").set(1)  # Render Frame Range

    print(f"Cache node created: {cache.path()}")
    print("Fields cached: density, temperature, flame, vel")
    print("To cache: set frame range, then click 'Save to Disk'")
    return cache

cache_pyro("/obj/pyro_fx/pyro_sim")
```

```python
# Import pyro to Solaris and configure volume rendering
import hou

def import_pyro_to_solaris(cache_path, stage_path="/stage"):
    """Import cached pyro to Solaris for Karma rendering."""
    stage = hou.node(stage_path)
    if not stage:
        return

    # SOP Import for pyro volumes
    sop_import = stage.createNode("sopimport", "pyro_import")
    sop_import.parm("soppath").set(cache_path)

    # Karma volume rendering settings
    # karmarenderproperties node for volume quality
    render_props = stage.node("karmarenderproperties1")
    if render_props:
        # Volume step rate: 0.25 (fast) to 1.0 (production)
        if render_props.parm("karma_volumesteprate"):
            render_props.parm("karma_volumesteprate").set(0.5)  # production quality
        # Shadow step rate can be coarser
        if render_props.parm("karma_volumeshadowsteprate"):
            render_props.parm("karma_volumeshadowsteprate").set(0.5)

    print(f"Pyro imported to Solaris, volume step rate=0.5")
    return sop_import

import_pyro_to_solaris("/obj/pyro_fx/pyro_cache")
```

```python
# Pyro source from animated geometry
import hou

hou.setSimulationEnabled(False)
try:
    geo = hou.node("/obj/pyro_fx")

    # For fire on a moving object:
    # 1. Object merge the animated geo
    animated = geo.createNode("object_merge", "moving_obj")
    animated.parm("objpath1").set("/obj/animated_hero")

    # 2. Trail SOP computes velocity from motion
    trail = geo.createNode("trail", "compute_vel")
    trail.setInput(0, animated)
    trail.parm("result").set(1)  # Compute velocity

    # 3. Scatter emission points on surface
    scatter = geo.createNode("scatter", "emit_pts")
    scatter.setInput(0, trail)
    scatter.parm("npts").set(500)

    # 4. Set pyro source attributes
    wrangle = geo.createNode("attribwrangle", "source_attrs")
    wrangle.setInput(0, scatter)
    wrangle.parm("snippet").set('''
f@density = 1.0;
f@temperature = 2.0;
f@flame = 1.0;
f@pscale = 0.04;
// v@v already inherited from trail -- drives flame direction
''')

    geo.layoutChildren()
    print("Animated pyro source created")

finally:
    hou.setSimulationEnabled(True)
```

## Expected DOP Tree
```
dopnet/
  smokeobject (divsize=0.05, initialSOP -> rasterize output)
  pyrosolver (dissipation=0.1, buoyancy=1.0, disturbance=0.4)
  sopscalar (source field from rasterize)
  merge (wires: container + solver + source)
```

## Common Mistakes
- Container clips simulation -- increase resize_padding to 0.5+
- Fire disappears instantly -- tempcooling too high, lower to 0.2-0.3
- Smoke too uniform -- enable disturbance (0.3) and shredding (0.2)
- Missing @pscale on source points -- volumerasterize needs it for radius
- divsize too small for preview -- start at 0.1, refine to 0.03-0.05 for final
- Not caching to disk before Solaris -- re-simulates every frame on render
- Volume step rate too low in Karma -- increase to 0.5-1.0 for production quality
