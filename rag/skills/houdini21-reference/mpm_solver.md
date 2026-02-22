# MPM Solver (Material Point Method) -- Houdini 21

## Triggers
mpm, material point method, mpm solver, mpm configure, mpm source, mpm collider,
mpmsurface, mpmdebrissource, mpmpostfracture, mpmdeformpieces, surface tension mpm,
auto sleep mpm, continuous emission mpm, granular sim, snow sim, sand sim, mud sim,
rubber sim, metal fracture mpm, concrete fracture mpm, mpm particles

## Context
MPM is a unified simulation framework for solids, granulars, and fluids. Particles
transfer data to/from a background grid each substep (Lagrangian + Eulerian hybrid).
Houdini 21 adds surface tension, auto sleep, continuous emission, per-voxel
friction/stickiness, improved deforming colliders, and 4 new post-simulation nodes.

SOP-level chain:
  source_geo -> mpmconfigure -> mpmsource -> mpmcollider -> mpmsolver -> post-sim nodes
Post-sim: mpmsurface, mpmdebrissource, mpmpostfracture, mpmdeformpieces

---

## Full Network Build (Python)

```python
import hou

# -- Get or create the SOP network context
obj = hou.node("/obj")
geo = obj.createNode("geo", "mpm_sim")
geo.moveToGoodPosition()

# Source geometry (e.g. a box of water, or import cached geo)
box = geo.createNode("box", "source_geo")
box.parm("sizex").set(2.0)
box.parm("sizey").set(1.0)
box.parm("sizez").set(2.0)

# Collider geometry (ground plane)
collider_box = geo.createNode("box", "collider_geo")
collider_box.parm("sizex").set(10.0)
collider_box.parm("sizey").set(0.2)
collider_box.parm("sizez").set(10.0)
collider_box.parm("ty").set(-1.0)

# Wire: source -> mpmconfigure -> mpmsource
configure = geo.createNode("mpmconfigure", "mpmconfigure1")
configure.setInput(0, box)

source = geo.createNode("mpmsource", "mpmsource1")
source.setInput(0, configure)

# Wire: collider_geo -> mpmcollider
collider = geo.createNode("mpmcollider", "mpmcollider1")
collider.setInput(0, collider_box)

# Wire solver: input0=source, input1=collider
solver = geo.createNode("mpmsolver", "mpmsolver1")
solver.setInput(0, source)
solver.setInput(1, collider)

geo.layoutChildren()
```

---

## mpmconfigure -- Material Presets and Properties

```python
import hou

configure = hou.node("/obj/mpm_sim/mpmconfigure1")

# -- Particle separation (lower = more detail, slower cook)
configure.parm("particlesep").set(0.05)   # scene-unit spacing between particles

# -- Material preset menu
# Preset indices: 0=Water, 1=Snow, 2=Sand, 3=Soil, 4=Rubber, 5=Metal, 6=Concrete
configure.parm("materialpreset").set(0)   # Water

# Material preset reference dictionary (what each preset configures internally):
MATERIAL_PRESETS = {
    "Water":    {"stiffness": 1e4,   "density": 1000.0, "viscosity": 0.001, "friction": 0.0},
    "Snow":     {"stiffness": 1.4e5, "density":  400.0, "viscosity": 0.0,   "friction": 0.3},
    "Sand":     {"stiffness": 1e6,   "density": 1600.0, "viscosity": 0.0,   "friction": 0.45},
    "Soil":     {"stiffness": 5e5,   "density": 1800.0, "viscosity": 0.0,   "friction": 0.4},
    "Rubber":   {"stiffness": 1e5,   "density": 1100.0, "viscosity": 0.0,   "friction": 0.8},
    "Metal":    {"stiffness": 2e8,   "density": 7800.0, "viscosity": 0.0,   "friction": 0.5},
    "Concrete": {"stiffness": 3e9,   "density": 2400.0, "viscosity": 0.0,   "friction": 0.6},
}

# -- Override individual material properties after setting preset
configure.parm("stiffness").set(1e4)     # resistance to deformation; higher = stiffer
configure.parm("density").set(1000.0)    # mass per unit volume (kg/m^3)
configure.parm("viscosity").set(0.001)   # internal resistance to flow; 0 = inviscid
configure.parm("friction").set(0.0)      # inter-particle friction coefficient
```

---

## mpmsource -- Emission Configuration

```python
import hou

source = hou.node("/obj/mpm_sim/mpmsource1")

# -- Emission type menu: 0=Volume, 1=Surface, 2=Points
source.parm("emissiontype").set(0)   # Volume: fills interior with particles

# Use Surface (1) for thin-walled objects to avoid wasting particles on interior:
# source.parm("emissiontype").set(1)

# -- Particle separation multiplier
# 2 = 1/8 the particle count of multiplier=1 (fast iteration)
# 1 = full resolution (final quality renders)
source.parm("particlesepmult").set(2)   # set to 1 before final sim

# -- Compression hardening (elastoplastic metals)
# 0 = default. Small positive values (0.1-1.0) make tearing more pronounced than bending.
source.parm("compressionhardening").set(0.0)
# For metal tearing effect:
# source.parm("compressionhardening").set(10.0)

# -- Phase ID for multiphase surface tension
# Each MPM Source that should interact via surface tension gets a unique integer ID
source.parm("phaseid").set(0)   # phase 0 (e.g. water)
# A second source (e.g. oil) would use phaseid=1; surface tension set per-pair on solver

# -- Continuous emission (overlapping emission)
# Allows new particles to emit where particles already exist
source.parm("overlapemission").set(1)    # enable overlapping emission
source.parm("expansion").set(25.0)       # default 1 is barely visible; use ~25 for growth
```

---

## mpmcollider -- Collision Geometry Setup

```python
import hou

collider = hou.node("/obj/mpm_sim/mpmcollider1")

# -- Collider type menu: 0=Static, 1=Animated Rigid, 2=Deforming
collider.parm("collidertype").set(0)   # Static: no movement, cheapest

# For deforming meshes (cloth, muscles driving MPM):
# collider.parm("collidertype").set(2)
# H21: "Expand to Cover Velocity" is ON by default -- dilates VDB by collider velocity
# so the SDF stays valid at all substeps. Leave enabled for deforming colliders.

# -- Surface friction and stickiness
collider.parm("friction").set(1.0)      # surface friction coefficient (0=frictionless)
collider.parm("stickiness").set(0.0)    # adhesion force on contact

# For surface-tension sims: levitation occurs unless friction/stickiness are high
collider.parm("friction").set(100.0)
collider.parm("stickiness").set(100.0)

# -- Per-voxel friction / stickiness from point attribute
# Workflow:
#   1. Paint "friction" as a POINT attribute on collider geo (not primitive)
#   2. If starting from primitives, use Cusp SOP to split shared points first
#      so averaging during VDB promotion preserves spatial variation
#   3. Enable the toggle below to read that attribute into the VDB
collider.parm("createvdbfromattrib").set(1)  # reads "friction" point attrib into VDB
# Per-voxel values can exceed 100 -- useful for selective adhesion zones
```

---

## mpmsolver -- Key Solver Parameters

```python
import hou

solver = hou.node("/obj/mpm_sim/mpmsolver1")

# -- Substep control
# More substeps = more stable but slower. Surface tension needs more substeps.
solver.parm("minsubsteps").set(1)
solver.parm("maxsubsteps").set(10)

# -- Material condition (stability threshold)
# Lower value = more substeps taken per frame = more stable
# Decrease for surface tension sims to prevent blowups
solver.parm("materialcondition").set(0.5)   # default ~1.0; use 0.25 for surface tension

# -- Gravity
solver.parm("gravity").set(-9.81)   # standard Earth gravity; negate to float upward

# -- CRITICAL: Assume Unchanging Material Properties
# ON  = solver caches material data after frame 1 (fast, wrong if emitting mixed materials)
# OFF = re-reads material properties every frame (required for mid-sim material changes)
solver.parm("assumeunchanging").set(0)   # DISABLE when emitting stiffer materials mid-sim

# -- Scale workaround for small sims (e.g. a 1cm object that blows up)
# Multiply scene scale x100, then compensate:
solver.parm("timescale").set(100.0)      # speed up sim time to match scaled space
solver.parm("gravity").set(-9.81 / 100)  # divide gravity to match scaled space
```

---

## Surface Tension (H21 New Feature)

```python
import hou

solver = hou.node("/obj/mpm_sim/mpmsolver1")

# -- Enable surface tension
solver.parm("surfacetension").set(1)

# -- Method: 0=Point-based (stable, higher VRAM), 1=Grid-based (fast, less stable)
solver.parm("surfacetensionmethod").set(0)   # point-based recommended

# -- Strength: multiply well above default for visible droplet cohesion
solver.parm("surfacetensionstrength").set(0.07)   # water ~0.072 N/m at room temp
# For dramatic beading/droplets, use 5-10x the physical value:
# solver.parm("surfacetensionstrength").set(0.5)

# -- Multiphase surface tension (e.g. water + oil separation)
# Each source gets a unique phaseid. Strength between phase pairs set on solver:
# Phase 0 (water) and Phase 1 (oil) separation strength:
solver.parm("multiphase_strength_0_1").set(0.3)   # adjust parm name per UI

# -- Stability settings for surface tension sims
solver.parm("minsubsteps").set(4)           # increase from default
solver.parm("maxsubsteps").set(20)          # allow more substeps
solver.parm("materialcondition").set(0.25)  # lower threshold = more stable
```

---

## Auto Sleep (H21 New Feature)

```python
import hou

solver = hou.node("/obj/mpm_sim/mpmsolver1")

# -- Enable auto sleep
solver.parm("autosleep").set(1)

# Particle states:
#   Active   (1): fully simulated
#   Boundary (2): attributes updated, position frozen -- maintains interface with active
#   Passive  (0): skipped entirely (biggest speedup)

# -- Velocity threshold below which particles deactivate
# Scale-dependent: use 10x default for scenes 100+ meters in size
solver.parm("sleepvelocitythreshold").set(0.01)   # default; raise for large scenes
# For a scene scaled to 100m:
# solver.parm("sleepvelocitythreshold").set(0.1)

# -- Delay before deactivation (seconds)
# 0.5s = 12 frames at 24fps -- prevents re-activation oscillation
solver.parm("sleepdelay").set(0.5)

# Speedup: up to 2x when 90%+ of particles are passive.
# Staggered activation: material starts passive; a collision event cascades
# activation through ~200 substeps as the wave propagates through the mass.
```

---

## Post-Simulation: mpmsurface

```python
import hou

solver = hou.node("/obj/mpm_sim/mpmsolver1")
geo = solver.parent()

surface = geo.createNode("mpmsurface", "mpmsurface1")
surface.setInput(0, solver)   # MPM particles from solver

# -- Output type: 0=SDF, 1=Density VDB, 2=Polygon Mesh
surface.parm("outputtype").set(2)   # Polygon Mesh for surface rendering

# -- Surfacing method: 0=VDB from Particle (CPU), 1=Neural Point Surface (GPU/ONNX)
surface.parm("surfacingmethod").set(0)   # VDB from Particle: reliable, standard

# Neural Point Surface (NPS) -- faster, GPU-accelerated, model-dependent:
# surface.parm("surfacingmethod").set(1)
# NPS model menu: 0=Balanced, 1=Smooth, 2=Liquid, 3=Granular
# surface.parm("npsmodel").set(2)   # Liquid model for water/splashes
# surface.parm("npsmodel").set(3)   # Granular model for sand/soil/snow

# -- Filtering pipeline (applied sequentially: Dilation -> Smooth -> Erosion)
surface.parm("dilate").set(1)          # expand SDF before smoothing
surface.parm("smooth").set(3)          # smooth iterations
surface.parm("erode").set(1)           # pull back to original volume

# -- Mask smooth: protect high-detail regions (high curvature, high Jp stretch)
surface.parm("masksmoothbystretch").set(1)    # protect fracturing regions from smoothing
surface.parm("masksmoothbycurvature").set(1)  # protect fine-detail edges

# -- VDB surface mask: prune polygons hidden behind colliders
surface.parm("vdbsurfacemask").set(1)         # removes hidden back-faces

# -- Chained pattern: first surface for SDF + velocity, second for render mesh
# Saves farm time by sharing SDF computation between collision and render passes
surface_sdf = geo.createNode("mpmsurface", "mpmsurface_sdf")
surface_sdf.setInput(0, solver)
surface_sdf.parm("outputtype").set(0)   # SDF output

surface_render = geo.createNode("mpmsurface", "mpmsurface_render")
surface_render.setInput(0, solver)
surface_render.setInput(1, surface_sdf)  # feed SDF into second surface
surface_render.parm("outputtype").set(2)  # Polygon Mesh

# -- For volumetric rendering (clouds, fog): use Density VDB output
# Erode interior to reduce point count by 50%+:
surface_vol = geo.createNode("mpmsurface", "mpmsurface_vol")
surface_vol.setInput(0, solver)
surface_vol.parm("outputtype").set(1)   # Density VDB
surface_vol.parm("erode").set(3)        # narrow-band: remove interior, keep shell

geo.layoutChildren()
```

---

## Post-Simulation: mpmdebrissource

```python
import hou

solver = hou.node("/obj/mpm_sim/mpmsolver1")
surface_sdf = hou.node("/obj/mpm_sim/mpmsurface_sdf")
geo = solver.parent()

debris = geo.createNode("mpmdebrissource", "mpmdebrissource1")
debris.setInput(0, solver)       # MPM particles (required)
debris.setInput(1, surface_sdf)  # MPM Surface SDF + velocity (recommended for quality)

# -- Fracture threshold: only emit debris from particles above this Jp stretch value
# Jp=1 means no stretch; values >1 indicate fracturing material
debris.parm("minstretchingjp").set(1.05)   # emit only from actively fracturing regions

# -- Speed filter: prune slow-moving debris (reduces noise from stationary zones)
debris.parm("minspeed").set(0.5)   # minimum velocity magnitude to emit debris

# -- Proximity filter: max distance from surface in dx units
# Auto-scales with particle separation -- keeps debris near the fracture surface
debris.parm("maxdisttosurface").set(3.0)   # in dx voxel units

# -- Replication (how many debris particles per source particle)
# Ramp remapping per stretching amount and per speed
debris.parm("replicationbystretching").set(1)   # more debris from faster-stretching regions
debris.parm("replicationbyspeed").set(1)        # more debris from faster-moving regions

# -- Velocity spread: distribute along velocity vector to eliminate stepping artifacts
debris.parm("velocityspread").set(0.3)   # fraction of velocity used for spread

# Downstream workflow:
#   mpmdebrissource -> POP Network -> VDB from Particles -> volumetric render
# Wire debris output into a POP Source, then render as density VDB for dust/spray

geo.layoutChildren()
```

---

## Post-Simulation: mpmpostfracture

```python
import hou

# Reverse-fracture workflow: simulate first, then fracture original geometry
# along Jp crack lines baked by the solver. Preferred over pre-fracturing.

solver = hou.node("/obj/mpm_sim/mpmsolver1")
original_geo = hou.node("/obj/mpm_sim/source_geo")   # pre-simulation clean mesh
geo = solver.parent()

fracture = geo.createNode("mpmpostfracture", "mpmpostfracture1")
fracture.setInput(0, solver)        # MPM particle data (crack info encoded in Jp)
fracture.setInput(1, original_geo)  # original un-fractured geometry to cut

# -- Frame range
# Start frame is auto-read from metadata written by the solver.
# End frame must be set manually (solver writes to parm at sim time if needed).
fracture.parm("endframe").set(hou.playbar.frameRange()[1])   # use timeline end

# -- Jp threshold: controls fracture sensitivity
# Lower values = fractures at smaller deformations (brittle)
# Higher values = only catastrophic deformations fracture (ductile)
fracture.parm("minstretchingjp").set(1.02)   # brittle concrete; use ~1.2 for ductile metal

# -- Filler points: uniform distribution prevents elongated/spiky shards
fracture.parm("fillerpoints").set(1)         # enable filler points
fracture.parm("fillerptdensity").set(0.05)   # filler spacing (scene units)
fracture.parm("maxfillerdist").set(0.1)      # limit fillers to crack regions (scene units)

# -- Align fractures to stretch point directions (essential for metal tearing patterns)
fracture.parm("alignfracturestostretching").set(1)

# -- Cutting method: 0=Boolean (detailed, preferred), 1=Voronoi (faster, less accurate)
fracture.parm("cuttingmethod").set(0)   # Boolean cutting for realistic fracture edges

geo.layoutChildren()
```

---

## Post-Simulation: mpmdeformpieces

```python
import hou

# Drives pre-fractured or named geometry with MPM simulation data.
# Requires `name` attribute on input geometry (standard packed prim convention).

solver = hou.node("/obj/mpm_sim/mpmsolver1")
fractured_geo = hou.node("/obj/mpm_sim/mpmpostfracture1")  # or any named geo
geo = solver.parent()

deform = geo.createNode("mpmdeformpieces", "mpmdeformpieces1")
deform.setInput(0, solver)        # MPM particle simulation data
deform.setInput(1, fractured_geo) # geometry with `name` attribute per piece

# -- Retargeting type menu:
# 0 = Piece-based:         preserves original shape per piece; visible cracks between pieces
# 1 = Point-based:         smooth deformation, no cracks; stretching artifacts at large deform
# 2 = Point and Piece:     blends both modes; best general-purpose result (default)
deform.parm("retargetingtype").set(2)   # Point and Piece (default, recommended)

# -- Stretch ratio: lower value = earlier switch from point-mode to piece-mode
# Controls the blend transition between smooth-deform and rigid-body-per-piece
deform.parm("stretchratio").set(1.5)    # default; lower (e.g. 1.1) for stiffer materials

# -- Close Gaps: reduce visible cracks in piece-based regions
deform.parm("closegaps").set(1)         # enabled by default in H21; keeps faces touching

# -- No-fracture workflow: any geometry with a `name` attribute can be driven by MPM.
# Example: tagged rubber bands, named cloth panels, labeled mechanical parts.
# The solver doesn't need to fracture them -- just provide matching name attributes.

# -- Add name attribute to source geometry if missing:
attrib_create = geo.createNode("attribcreate", "add_name_attrib")
attrib_create.setInput(0, fractured_geo)
attrib_create.parm("name1").set("name")
attrib_create.parm("class1").set(1)     # 1 = Primitive attribute
attrib_create.parm("type1").set(3)      # 3 = String
# Wire attrib_create output to deform input 1 when pieces lack name attrib

geo.layoutChildren()
```

---

## Auto-Build Complete MPM Network (Utility Function)

```python
import hou

def build_mpm_network(
    obj_context,
    network_name="mpm_sim",
    material_preset=0,          # 0=Water, 1=Snow, 2=Sand, 3=Soil, 4=Rubber, 5=Metal, 6=Concrete
    particle_sep=0.05,
    enable_surface_tension=False,
    enable_auto_sleep=True,
    min_substeps=1,
    max_substeps=10,
):
    """
    Build a complete MPM simulation network.
    Returns dict of created nodes keyed by role.
    """
    geo = obj_context.createNode("geo", network_name)
    geo.moveToGoodPosition()

    # Source geometry
    box = geo.createNode("box", "source_geo")
    box.parm("sizex").set(1.0)
    box.parm("sizey").set(1.0)
    box.parm("sizez").set(1.0)
    box.parm("ty").set(0.5)

    # Collider geometry (ground plane)
    ground = geo.createNode("box", "collider_geo")
    ground.parm("sizex").set(10.0)
    ground.parm("sizey").set(0.1)
    ground.parm("sizez").set(10.0)
    ground.parm("ty").set(-0.05)

    # mpmconfigure
    configure = geo.createNode("mpmconfigure", "mpmconfigure1")
    configure.setInput(0, box)
    configure.parm("particlesep").set(particle_sep)
    configure.parm("materialpreset").set(material_preset)

    # mpmsource
    source = geo.createNode("mpmsource", "mpmsource1")
    source.setInput(0, configure)
    source.parm("particlesepmult").set(2)   # fast iteration default

    # mpmcollider
    collider = geo.createNode("mpmcollider", "mpmcollider1")
    collider.setInput(0, ground)
    collider.parm("collidertype").set(0)   # Static
    collider.parm("friction").set(1.0)

    # mpmsolver
    solver = geo.createNode("mpmsolver", "mpmsolver1")
    solver.setInput(0, source)
    solver.setInput(1, collider)
    solver.parm("minsubsteps").set(min_substeps)
    solver.parm("maxsubsteps").set(max_substeps)
    solver.parm("assumeunchanging").set(0)   # safe default

    if enable_surface_tension:
        solver.parm("surfacetension").set(1)
        solver.parm("surfacetensionmethod").set(0)    # point-based
        solver.parm("surfacetensionstrength").set(0.07)
        solver.parm("minsubsteps").set(4)             # needs more substeps
        solver.parm("materialcondition").set(0.25)    # needs lower condition

    if enable_auto_sleep:
        solver.parm("autosleep").set(1)
        solver.parm("sleepvelocitythreshold").set(0.01)
        solver.parm("sleepdelay").set(0.5)

    # mpmsurface (polygon mesh)
    surface = geo.createNode("mpmsurface", "mpmsurface1")
    surface.setInput(0, solver)
    surface.parm("outputtype").set(2)        # Polygon Mesh
    surface.parm("surfacingmethod").set(0)   # VDB from Particle (CPU, reliable)
    surface.parm("smooth").set(3)

    geo.layoutChildren()

    return {
        "geo": geo,
        "source_geo": box,
        "collider_geo": ground,
        "configure": configure,
        "source": source,
        "collider": collider,
        "solver": solver,
        "surface": surface,
    }


# Usage:
# nodes = build_mpm_network(hou.node("/obj"), material_preset=2)  # Sand sim
# nodes = build_mpm_network(hou.node("/obj"), enable_surface_tension=True)  # Water droplets
# nodes["source"].parm("particlesepmult").set(1)  # Set to 1 before final sim
```

---

## Common Mistakes

- **Explosion on emission**: "Assume Unchanging Material Properties" is ON while emitting sources with different stiffness values. Disable it whenever mid-sim material changes occur.
- **Surface tension levitation**: Friction and stickiness on colliders are at default (1.0/0.0). Set both to 100+ to counteract surface-tension-induced levitation.
- **Surface tension instability / blowup**: Too few substeps or material condition too high. Increase min substeps to 4+, decrease material condition to 0.25.
- **Elongated shards from Post Fracture**: No filler points enabled. Add fillers and reduce filler spacing to prevent spiky, elongated geometry.
- **Cracks in retargeted mesh**: Using pure Piece-based retargeting in mpmdeformpieces. Switch to Point and Piece mode and enable Close Gaps.
- **Color/topology flicker on mesh**: Adaptivity > 0 causes the VDB topology to change per frame. Set adaptivity to 0 for animated sequences.
- **Poor granular surface quality**: Wrong NPS model selected. Use the Granular model for sand, soil, and snow; Liquid for water.
- **Sim ignores newly emitted material**: "Assume Unchanging" is enabled mid-emission of a different material type. Disable before starting the sim.
- **Per-voxel friction not working**: Friction is set as a primitive attribute instead of a point attribute. Convert to points first; use Cusp SOP to split shared points before VDB promotion.
- **mpmdeformpieces needs name attribute**: The input geometry lacks a `name` string primitive attribute. Add one via Attribute Create or ensure the fractured geo carries it from Post Fracture.
