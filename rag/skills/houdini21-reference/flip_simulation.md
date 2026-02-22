# FLIP Fluid Simulation

## Triggers
flip, fluid, water, liquid, splash, ocean, whitewater, foam, spray, bubbles, viscous, honey, lava, chocolate, particlefluidsurface, flipsolver, fluidsource, flip sim, fluid sim, fluid simulation, narrow band, meshing, flip cache

## Context
FLIP (Fluid Implicit Particle) is Houdini's primary fluid solver. SOP-level chain: source_geo -> fluidsource -> flipsolver -> particlefluidsurface. For Solaris/Karma: particlefluidsurface -> filecache -> sopimport LOP. Whitewater is a secondary simulation layered on top of the FLIP solve.

---

## Source Setup

```python
import hou

# ── Source setup: sphere emitting downward ──────────────────────────────────
geo = hou.node("/obj").createNode("geo", "flip_geo")

# Create source geometry
sphere = geo.createNode("sphere", "source_sphere")
sphere.parm("type").set(2)            # polygon sphere for cleaner VDB conversion
sphere.parm("radx").set(0.3)
sphere.parm("rady").set(0.3)
sphere.parm("radz").set(0.3)

# Convert geometry to FLIP source field
fluid_src = geo.createNode("fluidsource", "fluidsource1")
fluid_src.setInput(0, sphere)
fluid_src.parm("particlesep").set(0.05)        # particle separation -- smaller = higher res, slower
fluid_src.parm("scatterdensity").set(1.0)      # particle packing density
fluid_src.parm("initvel").set(1)               # enable initial velocity
fluid_src.parm("vx").set(0.0)
fluid_src.parm("vy").set(-2.0)                 # initial downward velocity
fluid_src.parm("vz").set(0.0)

geo.layoutChildren()
```

```python
# ── Continuous emitter: emit every frame from animated source ────────────────
fluid_src.parm("buildtype").set(1)             # 0=fill volume once, 1=continuous emit
fluid_src.parm("particlesep").set(0.04)        # emit separation (can differ from solver sep)

# ── Ocean surface init: init from oceanspectrum + oceanevaluate ─────────────
ocean_spec  = geo.createNode("oceanspectrum", "ocean_spectrum")
ocean_eval  = geo.createNode("oceanevaluate",  "ocean_evaluate")
ocean_eval.setInput(0, ocean_spec)
ocean_eval.parm("depth").set(50.0)             # water depth in scene units

fluid_src_ocean = geo.createNode("fluidsource", "fluidsource_ocean")
fluid_src_ocean.setInput(0, ocean_eval)
fluid_src_ocean.parm("initvel").set(1)         # inherit ocean surface velocity
```

---

## DOP Network + FLIP Solver

```python
import hou

# ── Build DOP network for FLIP ───────────────────────────────────────────────
obj = hou.node("/obj")
geo = obj.createNode("geo", "flip_container")

# AutoDopNetwork is the standard container Houdini creates via shelf
# Create it manually if needed:
dop_net = obj.createNode("dopnet", "dopnet1")
dop_net.parm("maxthreads").set(-1)             # -1 = use all available cores

# Inside the DOP network
flip_obj    = dop_net.createNode("flipobject",  "flip_fluid")
flip_solver = dop_net.createNode("flipsolver",  "flipsolver1")
gravity     = dop_net.createNode("gravity",     "gravity1")
merge       = dop_net.createNode("merge",       "merge1")

# Wire: flip_obj -> flipsolver -> gravity -> merge
flip_solver.setInput(0, flip_obj)
gravity.setInput(0, flip_solver)
merge.setInput(0, gravity)
```

```python
# ── FLIP Solver core parameters ──────────────────────────────────────────────
s = hou.node("/obj/dopnet1/flipsolver1")

# Resolution
s.parm("particlesep").set(0.05)        # particle separation (master resolution control)
s.parm("gridscale").set(2.0)           # pressure grid voxels = particlesep * gridscale
                                       # 2.0 is optimal; lower costs more with marginal gain

# Timestepping
s.parm("substeps").set(1)              # minimum substeps per frame (increase for fast colliders)
s.parm("maxsubsteps").set(10)          # CFL-based adaptive max substeps

# Physics
s.parm("viscosity").set(0.0)           # fluid thickness (0=water, 50-200=honey, 500-2000=lava)
s.parm("surfacetension").set(0.0)      # surface tension force
s.parm("gravx").set(0.0)
s.parm("gravy").set(-9.81)             # gravity in scene units/sec^2
s.parm("gravz").set(0.0)

# Particle maintenance
s.parm("reseed").set(1)                # 1=on -- maintains particle density; always leave on
s.parm("minparticles").set(4)          # min particles per voxel for reseeding
s.parm("maxparticles").set(16)         # max particles per voxel for reseeding

# Velocity transfer
s.parm("veltransfer").set("flip")      # "flip"=splashy, "pic"=smooth/damped, "picflip"=blend
s.parm("picflip").set(0.05)            # blend ratio: 0.05 = 95% FLIP + 5% PIC (reduces noise)
```

```python
# ── Narrow band (open-surface sims: rivers, oceans) ─────────────────────────
s = hou.node("/obj/dopnet1/flipsolver1")

s.parm("narrowband").set(1)            # enable narrow band -- 5-10x faster for deep water
s.parm("bandwidth").set(6)             # voxel layers to simulate near surface (6-10 typical)
                                       # DISABLE for enclosed volumes: pipes, containers, tanks
```

---

## Viscosity Presets

```python
import hou

# ── Viscosity presets dictionary ─────────────────────────────────────────────
FLUID_PRESETS = {
    "water": {
        "viscosity":      0.0,
        "surfacetension": 0.0,
        "picflip":        0.05,   # slight PIC blend reduces FLIP noise
        "substeps":       1,
        "notes":          "Fast splashes, energetic, default FLIP behavior",
    },
    "muddy_water": {
        "viscosity":      0.5,
        "surfacetension": 0.0,
        "picflip":        0.1,
        "substeps":       2,
        "notes":          "Slightly thick, sediment-like flow",
    },
    "blood": {
        "viscosity":      1.5,
        "surfacetension": 0.1,
        "picflip":        0.1,
        "substeps":       2,
        "notes":          "Slightly thicker than water, slight surface tension",
    },
    "chocolate": {
        "viscosity":      30.0,
        "surfacetension": 0.2,
        "picflip":        0.2,
        "substeps":       3,
        "notes":          "Medium viscosity, slow pour, surface tension holds shape",
    },
    "honey": {
        "viscosity":      150.0,
        "surfacetension": 0.5,
        "picflip":        0.3,
        "substeps":       4,
        "notes":          "Very slow, ropey, coils on itself -- use PIC-heavy blend",
    },
    "lava": {
        "viscosity":      1200.0,
        "surfacetension": 0.0,
        "picflip":        0.4,
        "substeps":       4,
        "notes":          "Extremely thick, almost solid flow, high substeps required",
    },
}


def apply_fluid_preset(solver_path: str, preset_name: str) -> None:
    """Apply a named viscosity preset to a FLIP solver node."""
    s = hou.node(solver_path)
    if s is None:
        raise ValueError(f"Couldn't find node at {solver_path!r}")
    preset = FLUID_PRESETS.get(preset_name)
    if preset is None:
        raise ValueError(f"Unknown preset {preset_name!r}. Available: {list(FLUID_PRESETS)}")

    s.parm("viscosity").set(preset["viscosity"])
    s.parm("surfacetension").set(preset["surfacetension"])
    s.parm("picflip").set(preset["picflip"])
    s.parm("substeps").set(preset["substeps"])
    print(f"Applied '{preset_name}' preset: viscosity={preset['viscosity']}, "
          f"substeps={preset['substeps']}  # {preset['notes']}")


# Usage:
# apply_fluid_preset("/obj/dopnet1/flipsolver1", "honey")
```

---

## Collision Setup

```python
import hou

# ── Static collider via VDB (preferred over raw polygons) ───────────────────
geo = hou.node("/obj/flip_geo")

# Build collision geo
box = geo.createNode("box", "collision_box")
box.parmTuple("size").set((4.0, 0.2, 4.0))    # flat floor plane
box.parmTuple("t").set((0.0, -1.5, 0.0))

# Convert to VDB for stability -- polygon colliders leak at thin geo
vdb = geo.createNode("vdbfrompolygons", "collision_vdb")
vdb.setInput(0, box)
vdb.parm("voxelsize").set(0.05)                # must be <= solver particlesep
vdb.parm("interiorbandwidth").set(4)           # interior band: 3-5 voxels
vdb.parm("exteriorbandwidth").set(4)           # exterior band: 3-5 voxels
vdb.parm("fillinterior").set(1)                # fill interior solid -- prevents leaking

# collision_source SOP feeds the DOP collision input
coll_src = geo.createNode("collisionsource", "collision_source1")
coll_src.setInput(0, vdb)
coll_src.parm("velocitytype").set("point")     # accurate velocity for moving colliders

geo.layoutChildren()
```

```python
# ── Animated / deforming collider ────────────────────────────────────────────
coll_src = hou.node("/obj/flip_geo/collision_source1")

coll_src.parm("deforming").set(1)              # enable deforming geometry mode
coll_src.parm("velocitytype").set("point")     # point velocity = per-vertex blur
# For fast-moving colliders, increase solver substeps to 2-4:
solver = hou.node("/obj/dopnet1/flipsolver1")
solver.parm("substeps").set(3)                 # prevent tunneling through fast colliders
solver.parm("maxsubsteps").set(6)
```

---

## Whitewater (Spray, Foam, Bubbles)

```python
import hou

# ── Whitewater source -- driven by FLIP sim output ───────────────────────────
geo = hou.node("/obj/flip_geo")

# Assumes FLIP particles are cached; connect whitewater source to the cache read
flip_cache = hou.node("/obj/flip_geo/filecache_flip")

ww_src = geo.createNode("whitewatersource", "whitewater_source")
ww_src.setInput(0, flip_cache)

# Emission thresholds -- tune to control density of secondary particles
ww_src.parm("min_speed").set(3.0)              # minimum velocity to emit (m/s); 2-5 typical
ww_src.parm("curvature_emit").set(1)           # emit from wave crests / high curvature
ww_src.parm("curvaturethreshold").set(0.3)     # curvature threshold for emission
ww_src.parm("acceleration_emit").set(1)        # emit where fluid rapidly changes direction
ww_src.parm("accelerationthreshold").set(5.0)
ww_src.parm("vorticitymin").set(2.0)           # minimum vorticity (spin) to emit

# ── Whitewater solver ─────────────────────────────────────────────────────────
ww_dop = hou.node("/obj").createNode("dopnet", "whitewater_dopnet")
ww_solver = ww_dop.createNode("whitewatersolver", "whitewatersolver1")

# Enable each secondary particle type
ww_solver.parm("emit_spray").set(1)            # spray: flung airborne droplets
ww_solver.parm("emit_foam").set(1)             # foam: surface froth / bubbles
ww_solver.parm("emit_bubbles").set(1)          # bubbles: underwater air pockets

# Lifetime controls (frames)
ww_solver.parm("spray_life").set(48)           # spray dies after ~2sec at 24fps
ww_solver.parm("foam_life").set(120)           # foam persists longer
ww_solver.parm("bubble_life").set(72)

# Depth threshold for bubble emission
ww_solver.parm("bubble_depth").set(0.3)        # depth below surface to emit bubbles
```

---

## Meshing (particlefluidsurface)

```python
import hou

# ── particlefluidsurface SOP -- converts FLIP particles to renderable mesh ───
geo = hou.node("/obj/flip_geo")
flip_cache = hou.node("/obj/flip_geo/filecache_flip")

mesh = geo.createNode("particlefluidsurface", "flip_mesh")
mesh.setInput(0, flip_cache)

# Core mesh parameters -- must match solver's particlesep
mesh.parm("particlesep").set(0.05)             # MUST match flipsolver particlesep exactly
mesh.parm("voxelscale").set(1.0)               # voxel size relative to particlesep
mesh.parm("influencescale").set(2.0)           # particle radius for surface reconstruction
                                               # too high = blobby; too low = holes; start at 2.0

# Droplet rendering (small splash particles rendered as spheres)
mesh.parm("dropletscale").set(0.5)             # >0 renders isolated particles as tiny spheres

# Surface smoothing
mesh.parm("smoothiter").set(5)                 # smoothing iterations (3 for preview, 5-8 for final)
mesh.parm("smoothscale").set(0.5)              # smoothing strength per iteration

# Dilate / erode surface thickness
mesh.parm("dilate").set(0)                     # positive = thicken (wetter look)
mesh.parm("erode").set(0)                      # positive = thin (drier, sharper)

# Transfer attributes to mesh surface for shading
mesh.parm("transferattribs").set(1)            # pass velocity, vorticity, curvature to mesh
# Shader can then use `v@v` for motion blur, `f@surface_tension` for foam masking

geo.layoutChildren()
```

```python
# ── Quality presets for meshing ───────────────────────────────────────────────
MESH_PRESETS = {
    "preview": {
        "particlesep":    0.10,   # coarse -- fast playback
        "influencescale": 2.0,
        "smoothiter":     3,
        "dropletscale":   0.0,    # skip droplet meshing for speed
    },
    "hero": {
        "particlesep":    0.03,   # fine -- matches high-res sim
        "influencescale": 1.8,    # slightly tighter for crisp splashes
        "smoothiter":     7,
        "dropletscale":   0.4,
    },
}

def apply_mesh_preset(mesh_path: str, preset_name: str) -> None:
    """Apply meshing quality preset to a particlefluidsurface node."""
    node = hou.node(mesh_path)
    if node is None:
        raise ValueError(f"Couldn't find node at {mesh_path!r}")
    p = MESH_PRESETS[preset_name]
    node.parm("particlesep").set(p["particlesep"])
    node.parm("influencescale").set(p["influencescale"])
    node.parm("smoothiter").set(p["smoothiter"])
    node.parm("dropletscale").set(p["dropletscale"])
    print(f"Mesh preset '{preset_name}' applied.")
```

---

## Caching Strategy

```python
import hou

# ── Cache FLIP particles (always cache before meshing or rendering) ───────────
geo = hou.node("/obj/flip_geo")
flip_solver_out = hou.node("/obj/dopnet1")      # DOP network output node

# Particle cache -- .bgeo.sc = Blosc compressed, fastest for FLIP
flip_cache = geo.createNode("filecache", "filecache_flip")
flip_cache.setInput(0, flip_solver_out)
flip_cache.parm("file").set('$HIP/cache/flip/flip.$F4.bgeo.sc')
flip_cache.parm("loadfromdisk").set(0)          # 0=write, 1=read back from disk
flip_cache.parm("startframe").set(hou.playbar.playbackRange()[0])
flip_cache.parm("endframe").set(hou.playbar.playbackRange()[1])

# Mesh cache -- cache processed mesh separately from particles
mesh_node = hou.node("/obj/flip_geo/flip_mesh")
mesh_cache = geo.createNode("filecache", "filecache_mesh")
mesh_cache.setInput(0, mesh_node)
mesh_cache.parm("file").set('$HIP/cache/flip_mesh/mesh.$F4.bgeo.sc')
mesh_cache.parm("loadfromdisk").set(0)

# Whitewater cache (separate from main sim)
ww_cache = geo.createNode("filecache", "filecache_whitewater")
# ww_cache.setInput(0, whitewater_out)
ww_cache.parm("file").set('$HIP/cache/whitewater/ww.$F4.bgeo.sc')

geo.layoutChildren()
```

```python
# ── Switch filecache to READ mode for re-use after sim completes ─────────────
def set_cache_mode(cache_path: str, mode: str = "read") -> None:
    """Toggle a filecache SOP between write and read mode."""
    node = hou.node(cache_path)
    if node is None:
        raise ValueError(f"Couldn't find node at {cache_path!r}")
    node.parm("loadfromdisk").set(1 if mode == "read" else 0)
    print(f"filecache '{cache_path}' set to {mode.upper()} mode.")

# set_cache_mode("/obj/flip_geo/filecache_flip", "read")
# set_cache_mode("/obj/flip_geo/filecache_mesh", "read")
```

---

## Solaris Import

```python
import hou

# ── Import cached FLIP mesh into LOPs / Solaris ───────────────────────────────
stage = hou.node("/stage")

# Primary fluid mesh
fluid_import = stage.createNode("sopimport", "flip_fluid_import")
fluid_import.parm("soppath").set("/obj/flip_geo/filecache_mesh")
fluid_import.parm("primpath").set("/fx/flip_fluid")
fluid_import.parm("importtype").set("auto")     # auto detects geo type

# Whitewater spray particles -- separate sopimport, rendered as points
spray_import = stage.createNode("sopimport", "whitewater_spray_import")
spray_import.parm("soppath").set("/obj/flip_geo/filecache_whitewater")
spray_import.parm("primpath").set("/fx/whitewater_spray")

# Merge both into the scene
merge_lop = stage.createNode("merge", "fx_merge")
merge_lop.setInput(0, fluid_import)
merge_lop.setInput(1, spray_import)

stage.layoutChildren()
```

---

## Full Build Script (with simulation guard)

```python
import hou

def build_flip_sim(
    container_path: str = "/obj",
    particle_sep:   float = 0.05,
    viscosity:      float = 0.0,
    substeps:       int   = 1,
    use_narrowband: bool  = False,
) -> dict:
    """
    Build a complete FLIP simulation network.
    Wraps the DOP cook in a simulation guard to prevent accidental re-simulation.
    Returns dict of created node paths.
    """
    obj = hou.node(container_path)
    nodes = {}

    # ── Simulation guard: disable auto-sim before building ───────────────────
    hou.setSimulationEnabled(False)
    try:
        # Geometry container
        geo = obj.createNode("geo", "flip_setup_geo")
        nodes["geo"] = geo.path()

        # Source sphere
        sphere = geo.createNode("sphere", "emit_sphere")
        sphere.parm("type").set(2)
        sphere.parm("radx").set(0.4)
        sphere.parm("rady").set(0.4)
        sphere.parm("radz").set(0.4)
        sphere.parmTuple("t").set((0.0, 2.0, 0.0))
        nodes["sphere"] = sphere.path()

        # Fluid source
        fsrc = geo.createNode("fluidsource", "fluidsource1")
        fsrc.setInput(0, sphere)
        fsrc.parm("particlesep").set(particle_sep)
        fsrc.parm("initvel").set(1)
        fsrc.parm("vy").set(-1.0)               # initial downward push
        nodes["fluidsource"] = fsrc.path()

        # Collision floor
        floor = geo.createNode("box", "floor_geo")
        floor.parmTuple("size").set((6.0, 0.1, 6.0))
        floor.parmTuple("t").set((0.0, -0.5, 0.0))

        floor_vdb = geo.createNode("vdbfrompolygons", "floor_vdb")
        floor_vdb.setInput(0, floor)
        floor_vdb.parm("voxelsize").set(particle_sep)
        floor_vdb.parm("interiorbandwidth").set(4)
        floor_vdb.parm("exteriorbandwidth").set(4)
        floor_vdb.parm("fillinterior").set(1)
        nodes["floor_vdb"] = floor_vdb.path()

        coll_src = geo.createNode("collisionsource", "collision_source1")
        coll_src.setInput(0, floor_vdb)
        nodes["collision_source"] = coll_src.path()

        # DOP network
        dop = obj.createNode("dopnet", "flip_dopnet")
        nodes["dopnet"] = dop.path()

        flip_obj    = dop.createNode("flipobject",  "flip_fluid")
        flip_solver = dop.createNode("flipsolver",  "flipsolver1")
        grav        = dop.createNode("gravity",     "gravity1")
        mrg         = dop.createNode("merge",       "merge1")

        flip_solver.setInput(0, flip_obj)
        grav.setInput(0, flip_solver)
        mrg.setInput(0, grav)

        # Solver parameters
        flip_solver.parm("particlesep").set(particle_sep)
        flip_solver.parm("gridscale").set(2.0)
        flip_solver.parm("viscosity").set(viscosity)
        flip_solver.parm("substeps").set(substeps)
        flip_solver.parm("reseed").set(1)
        flip_solver.parm("picflip").set(0.05)   # noise-reducing PIC blend
        if use_narrowband:
            flip_solver.parm("narrowband").set(1)
            flip_solver.parm("bandwidth").set(6)
        nodes["flipsolver"] = flip_solver.path()

        # Particle cache
        flip_cache = geo.createNode("filecache", "filecache_flip")
        flip_cache.parm("file").set("$HIP/cache/flip/flip.$F4.bgeo.sc")
        flip_cache.parm("loadfromdisk").set(0)
        nodes["flip_cache"] = flip_cache.path()

        # Mesh
        mesh = geo.createNode("particlefluidsurface", "flip_mesh")
        mesh.setInput(0, flip_cache)
        mesh.parm("particlesep").set(particle_sep)
        mesh.parm("influencescale").set(2.0)
        mesh.parm("smoothiter").set(5)
        mesh.parm("transferattribs").set(1)
        nodes["mesh"] = mesh.path()

        # Mesh cache
        mesh_cache = geo.createNode("filecache", "filecache_mesh")
        mesh_cache.setInput(0, mesh)
        mesh_cache.parm("file").set("$HIP/cache/flip_mesh/mesh.$F4.bgeo.sc")
        mesh_cache.parm("loadfromdisk").set(0)
        nodes["mesh_cache"] = mesh_cache.path()

        geo.layoutChildren()
        dop.layoutChildren()

        print(f"FLIP network built. particlesep={particle_sep}, "
              f"viscosity={viscosity}, substeps={substeps}")
        print("Re-enable simulation and cook DOP to start: hou.setSimulationEnabled(True)")

    finally:
        # ── Always restore simulation state -- even if build fails ──────────
        hou.setSimulationEnabled(True)

    return nodes


# Example:
# nodes = build_flip_sim(particle_sep=0.05, viscosity=0.0, substeps=1)
# nodes = build_flip_sim(particle_sep=0.05, viscosity=150.0, substeps=4)  # honey
```

---

## VEX: Custom Force on FLIP Particles

```vex
// Apply a vortex swirl force to FLIP particles in a DOP VEX node
// Context: DOPs, run over particles (v@force attribute)

vector pos = v@P;                          // current particle position
float  speed = chf("vortex_speed");        // shelf-driven strength, default 5.0
float  radius = chf("vortex_radius");      // effect radius, default 2.0

// Distance from world Y axis
float dist = sqrt(pos.x * pos.x + pos.z * pos.z);

if (dist < radius) {
    float  falloff  = 1.0 - (dist / radius);    // linear falloff from center
    vector tangent  = set(-pos.z, 0.0, pos.x);  // perpendicular to radial direction
    tangent = normalize(tangent);
    v@force += tangent * speed * falloff;        // add swirl force
}
```

```vex
// Velocity-dependent drag for viscous fluids (run on FLIP particles in DOPs)
// Reduces high-velocity outliers that cause fluid to tear at high viscosity

float drag_coeff = chf("drag");            // 0.0 = no drag, 0.1 = light, 0.5 = heavy
float max_speed  = chf("max_speed");       // clamp velocity above this threshold, e.g. 5.0

float speed = length(v@v);
if (speed > max_speed) {
    v@v = normalize(v@v) * max_speed;     // hard clamp on outlier particles
}

v@v *= (1.0 - drag_coeff);                // proportional drag
```

---

## Common Mistakes

- **Fluid explodes on frame 1**: Source geometry overlaps collision geo. Always leave a gap of at least 2x particlesep between emitter and colliders. Increase substeps to 2.

- **Leaking through walls**: Polygon collisions at thin geometry. Always use `vdbfrompolygons` with `fillinterior=1` for collision objects. Increase solver substeps to 3-4 for thin walls.

- **Blobby mesh**: `influencescale` too high. Start at 2.0, reduce toward 1.5 if too blobby. Increase `smoothiter` to 5-7 for a cleaner surface.

- **Holes in the surface mesh**: Too few particles in thin regions. Enable reseeding on the solver. Lower `particlesep` one step (e.g., 0.05 -> 0.04).

- **Viscous fluid tears apart**: Viscosity is set but substeps are too low for the motion speed. Increase substeps to 3-5. Increase PIC blend (`picflip` toward 0.3-0.4).

- **Surface jitter / noise**: FLIP velocity noise is normal at low particle counts. Blend with PIC (`picflip=0.05` is the minimum; go higher for viscous fluids). Also increase `smoothiter` on the mesh.

- **Simulation is very slow**: `particlesep` is too small for the domain. Start at 0.1 for preview, step down to 0.05 or 0.03 for final. Enable narrow band for open-surface sims (5-10x speedup).

- **Memory exhaustion**: Domain too large for the particle count. Use narrow band, reduce domain size, or increase `particlesep`. FLIP at 0.02 separation on a large domain can easily consume 64GB+.

- **filecache does not write**: `loadfromdisk` is set to 1 (read mode). Set it to 0 before cooking. Check that the output directory exists (Houdini will not create missing parent directories).
