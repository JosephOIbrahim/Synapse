# Vellum Simulation

## Triggers
vellum, cloth sim, hair sim, grain sim, soft body, vellum cloth, vellum hair, vellum grains,
vellum solver, vellumcloth, vellumhair, vellumgrains, vellumsoftbody, vellumconstraints,
vellumcollider, vellumdrape, pin cloth, vellum pin, vellum cache, vellum collision,
vellum constraints, vellum solver substeps, vellum lops, vellum solaris, grain setup,
fabric sim, flag sim, curtain sim, fur sim, guide curves, grain friction, soft body tet

## Context
Vellum is Houdini's unified SOP-level solver for cloth, hair, grain, soft body, and balloon
simulations. All configure nodes (vellumcloth, vellumhair, etc.) have TWO outputs:
  output 0 = geometry,  output 1 = constraints.
Vellumsolver: input 0 = geometry, input 2 = constraints (0-indexed in Python API).
Always cache before rendering. Import to Solaris via sopimport LOP.

---

## Network Assembly

```python
import hou

# ── Full Vellum SOP network scaffold ──────────────────────────────────────────
geo = hou.node("/obj").createNode("geo", "vellum_sim")
geo.moveToGoodPosition()

# Source geometry (grid for cloth demo)
grid = geo.createNode("grid", "source_grid")
grid.parm("rows").set(20)
grid.parm("cols").set(20)
grid.parm("sizex").set(2.0)
grid.parm("sizey").set(2.0)

# Configure node -- produces geometry (output 0) AND constraints (output 1)
cloth = geo.createNode("vellumcloth", "configure_cloth")
cloth.setInput(0, grid)           # geometry in

# Solver -- input 0 = geo, input 2 = constraints (NOT input 1)
solver = geo.createNode("vellumsolver", "vellum_solver")
solver.setInput(0, cloth, 0)      # output 0 of configure = geo -> solver input 0
solver.setInput(2, cloth, 1)      # output 1 of configure = constraints -> solver input 2

# Output null
out = geo.createNode("null", "OUT_sim")
out.setInput(0, solver)
out.setDisplayFlag(True)
out.setRenderFlag(True)

geo.layoutChildren()
```

---

## Cloth Setup

```python
import hou

def setup_cloth(geo_node_path, source_node):
    """Wire and configure a cloth simulation."""
    geo = hou.node(geo_node_path)

    cloth = geo.createNode("vellumcloth", "configure_cloth")
    cloth.setInput(0, source_node)

    # ── Cloth stiffness ───────────────────────────────────────────────────────
    cloth.parm("stretchstiffness").set(10000)       # resist stretching
    cloth.parm("bendstiffness").set(0.001)           # resist bending (low = floppy)
    cloth.parm("compressionstiffness").set(10)       # resist compression
    cloth.parm("shearstiffness").set(10000)          # resist shear / diagonal stretch

    # ── Mass / thickness ──────────────────────────────────────────────────────
    cloth.parm("density").set(0.1)                   # kg/m^2
    cloth.parm("thickness").set(0.01)                # collision thickness in scene units

    # ── Damping ───────────────────────────────────────────────────────────────
    cloth.parm("dampingratio").set(0.01)             # 0 = no damping, 1 = overdamped

    # ── Self-collision (expensive -- disable for preview) ─────────────────────
    cloth.parm("selfcollisions").set(0)              # 0=off, 1=on

    return cloth


# ── Cloth material presets ────────────────────────────────────────────────────
# Use these values as (stretchstiffness, bendstiffness, density) tuples.
CLOTH_PRESETS = {
    "silk":          (5000,    0.0001,  0.05),   # very light, flowing
    "cotton_tshirt": (10000,   0.001,   0.10),   # Houdini default feel
    "denim":         (50000,   0.1,     0.30),   # heavy, stiff
    "leather":       (100000,  1.0,     0.50),   # very stiff, thick
    "flag_banner":   (8000,    0.0005,  0.08),   # light, responsive to wind
    "rubber_sheet":  (5000,    0.01,    0.40),   # stretchy, heavy
    "chiffon_veil":  (3000,    0.00001, 0.02),   # ultra-light, delicate
}

def apply_cloth_preset(cloth_node, preset_name):
    """Apply a fabric preset to a vellumcloth configure node."""
    stretch, bend, density = CLOTH_PRESETS[preset_name]
    cloth_node.parm("stretchstiffness").set(stretch)
    cloth_node.parm("bendstiffness").set(bend)
    cloth_node.parm("density").set(density)
    print(f"Applied cloth preset '{preset_name}': "
          f"stretch={stretch}, bend={bend}, density={density}")
```

---

## Draping (pre-settle onto body)

```python
import hou

def setup_drape(geo_node_path, cloth_configure_node, collision_body_node):
    """
    Add a vellumdrape step so the garment settles before the main sim.
    Drape runs a pre-simulation; its output is the 'rest' position for the solver.
    """
    geo = hou.node(geo_node_path)

    drape = geo.createNode("vellumdrape", "drape")
    drape.setInput(0, cloth_configure_node, 0)   # cloth geo
    drape.setInput(1, cloth_configure_node, 1)   # cloth constraints
    drape.setInput(2, collision_body_node)        # collision body

    drape.parm("frames").set(60)                 # pre-sim frames to settle garment
    drape.parm("substeps").set(3)                # substeps during drape solve

    # Wire drape output to the main solver
    solver = geo.createNode("vellumsolver", "vellum_solver")
    solver.setInput(0, drape, 0)    # draped geo -> solver geo input
    solver.setInput(2, drape, 1)    # draped constraints -> solver constraint input

    return drape, solver
```

---

## Hair Setup

```python
import hou

def setup_hair(geo_node_path, curve_source_node):
    """Configure vellumhair for guide-curve simulation."""
    geo = hou.node(geo_node_path)

    hair = geo.createNode("vellumhair", "configure_hair")
    hair.setInput(0, curve_source_node)   # input = polyline curves

    # ── Stiffness ──────────────────────────────────────────────────────────────
    hair.parm("stretchstiffness").set(10000)    # along-curve resist
    hair.parm("bendstiffness").set(0.1)          # 0.01 = very floppy, 1.0+ = stiff/short
    hair.parm("twistperstiffness").set(0.1)      # resist twisting

    # ── Shape ──────────────────────────────────────────────────────────────────
    hair.parm("width").set(0.01)                 # strand width for collision
    hair.parm("density").set(1.0)                # mass per unit length

    # ── Damping ────────────────────────────────────────────────────────────────
    hair.parm("dampingratio").set(0.02)

    # Solver wiring
    solver = geo.createNode("vellumsolver", "vellum_solver")
    solver.setInput(0, hair, 0)    # geo
    solver.setInput(2, hair, 1)    # constraints

    return hair, solver

# ── Hair stiffness presets ────────────────────────────────────────────────────
HAIR_PRESETS = {
    "long_flowing":  {"bendstiffness": 0.01,  "substeps": 5},   # wavy, loose
    "medium_wavy":   {"bendstiffness": 0.1,   "substeps": 3},   # default
    "short_stiff":   {"bendstiffness": 2.0,   "substeps": 2},   # cropped, rigid
    "cable_rope":    {"bendstiffness": 10.0,  "substeps": 5},   # stiff cable
}

def apply_hair_preset(hair_node, solver_node, preset_name):
    preset = HAIR_PRESETS[preset_name]
    hair_node.parm("bendstiffness").set(preset["bendstiffness"])
    solver_node.parm("substeps").set(preset["substeps"])
```

---

## Grain Setup

```python
import hou

def setup_grains(geo_node_path, source_node):
    """Configure vellumgrains for granular material simulation."""
    geo = hou.node(geo_node_path)

    grains = geo.createNode("vellumgrains", "configure_grains")
    grains.setInput(0, source_node)

    # ── Particle size and mass ─────────────────────────────────────────────────
    grains.parm("particlesep").set(0.05)         # spacing between grain centers
    grains.parm("density").set(1.0)              # mass per grain

    # ── Inter-grain behavior ───────────────────────────────────────────────────
    grains.parm("friction").set(0.5)             # higher = piles up more
    grains.parm("clusterstiffness").set(0.0)     # 0 = free-flowing, 1 = packed/snow
    grains.parm("clusterradius").set(0.0)        # radius for cluster constraint

    # Solver wiring
    solver = geo.createNode("vellumsolver", "vellum_solver")
    solver.setInput(0, grains, 0)
    solver.setInput(2, grains, 1)

    return grains, solver


# ── Grain material presets ────────────────────────────────────────────────────
# Values: (friction, clusterstiffness, notes)
GRAIN_PRESETS = {
    "dry_sand":   (0.5, 0.0,  "free-flowing, angle of repose ~30 deg"),
    "wet_sand":   (0.8, 0.5,  "clumps, holds shape loosely"),
    "snow":       (0.3, 0.8,  "packs and holds shape; cluster keeps it together"),
    "gravel":     (0.7, 0.0,  "rolling, non-sticky"),
    "sugar_salt": (0.2, 0.0,  "very free-flowing, low friction"),
}

def apply_grain_preset(grains_node, preset_name):
    friction, cluster, _ = GRAIN_PRESETS[preset_name]
    grains_node.parm("friction").set(friction)
    grains_node.parm("clusterstiffness").set(cluster)
    print(f"Grain preset '{preset_name}': friction={friction}, cluster={cluster}")
```

---

## Soft Body Setup

```python
import hou

def setup_softbody(geo_node_path, mesh_source_node):
    """
    Soft body requires a TETRAHEDRAL mesh as input.
    Wire: mesh -> remesh (solidconform) -> vellumsoftbody -> vellumsolver
    """
    geo = hou.node(geo_node_path)

    # Step 1: Convert surface mesh to solid tet mesh
    solid = geo.createNode("solidconform", "make_tet_mesh")
    solid.setInput(0, mesh_source_node)
    solid.parm("outputtetmesh").set(1)    # produce tetrahedral mesh
    solid.parm("maxedgelength").set(0.1)  # tet size -- smaller = denser/slower

    # Step 2: Soft body configure
    softbody = geo.createNode("vellumsoftbody", "configure_softbody")
    softbody.setInput(0, solid)

    # ── Deformation stiffness ──────────────────────────────────────────────────
    softbody.parm("shapestiffness").set(1.0)       # resist shape change (jelly < rubber)
    softbody.parm("volumestiffness").set(0.0)      # 0 = compressible, 1 = incompressible
    softbody.parm("dampingratio").set(0.1)         # oscillation damping

    # ── Soft body presets ──────────────────────────────────────────────────────
    # Jelly:   shapestiffness=0.1,  volumestiffness=0.5
    # Rubber:  shapestiffness=5.0,  volumestiffness=0.8
    # Muscle:  shapestiffness=10.0, volumestiffness=0.9, dampingratio=0.05

    solver = geo.createNode("vellumsolver", "vellum_solver")
    solver.setInput(0, softbody, 0)
    solver.setInput(2, softbody, 1)

    return softbody, solver
```

---

## Solver Configuration

```python
import hou

def configure_solver(solver_node, sim_type="cloth"):
    """
    Set vellumsolver parameters for different simulation types.
    sim_type: "cloth", "cloth_fast", "hair", "grains", "softbody"
    """
    # ── Substep / iteration presets ───────────────────────────────────────────
    SOLVER_PRESETS = {
        #             substeps  iterations  timescale  gravity
        "cloth":      (5,       100,        1.0,       -9.81),
        "cloth_fast": (15,      150,        1.0,       -9.81),   # fast-moving cloth
        "hair":       (4,        80,        1.0,       -9.81),
        "grains":     (2,        50,        1.0,       -9.81),
        "softbody":   (5,       100,        1.0,       -9.81),
    }

    substeps, iterations, timescale, gravity = SOLVER_PRESETS[sim_type]

    solver_node.parm("substeps").set(substeps)
    solver_node.parm("constraintiterations").set(iterations)
    solver_node.parm("timescale").set(timescale)

    # Gravity (Y-axis component)
    solver_node.parm("gravityx").set(0.0)
    solver_node.parm("gravityy").set(gravity)
    solver_node.parm("gravityz").set(0.0)

    # ── Ground plane ──────────────────────────────────────────────────────────
    solver_node.parm("groundplane").set(1)     # implicit ground (fast, no geo needed)
    solver_node.parm("groundpos").set(0.0)     # Y position of ground
    solver_node.parm("groundfriction").set(0.5)

    # ── Wind force (optional) ──────────────────────────────────────────────────
    # solver_node.parm("windx").set(1.0)       # world-space wind vector
    # solver_node.parm("windy").set(0.0)
    # solver_node.parm("windz").set(0.0)

    print(f"Solver configured for '{sim_type}': "
          f"substeps={substeps}, iterations={iterations}")
```

---

## Collision Setup

```python
import hou

def setup_collision(geo_node_path, animated_body_node, solver_node):
    """
    Prepare an animated mesh as a Vellum collider.
    Collider connects to solver input 1 (index 1 in 0-based Python API).
    """
    geo = hou.node(geo_node_path)

    # Add velocity attribute to collision mesh (required for moving colliders)
    trail = geo.createNode("trail", "compute_velocity")
    trail.setInput(0, animated_body_node)
    trail.parm("result").set(2)              # "Compute Velocity" mode
    trail.parm("velapproximation").set(0)    # central difference

    # Optionally simplify collision mesh for speed
    polyreduce = geo.createNode("polyreduce", "simplify_collider")
    polyreduce.setInput(0, trail)
    polyreduce.parm("percentage").set(20)    # 20% of original poly count
    polyreduce.parm("doquality").set(1)

    # Vellum collider prepare node
    collider = geo.createNode("vellumcollider", "collider_prepare")
    collider.setInput(0, polyreduce)
    collider.parm("thickness").set(0.01)     # match cloth thickness for stability

    # Wire to solver: input 1 (0-indexed) = collision geometry
    solver_node.setInput(1, collider)

    return collider


def enable_self_collision(cloth_configure_node, enable=True):
    """Toggle self-collision on a configure node. Expensive -- disable for preview."""
    cloth_configure_node.parm("selfcollisions").set(1 if enable else 0)
    if enable:
        # Self-collision needs tighter thickness for accuracy
        current = cloth_configure_node.parm("thickness").eval()
        print(f"Self-collision ON. Current thickness={current}. "
              "Increase substeps to 15+ for tight garments.")
```

---

## Pinning (VEX in wrangle before configure)

```vex
// ─── Attrib Wrangle: pin_by_height ───────────────────────────────────────────
// Run Over: Points
// Place BEFORE vellumcloth configure node.
// Sets i@stopped=1 to freeze points in place (pinned to world-space position).

float pin_height = chf("pin_height");   // create float channel, e.g. 0.9

if (@P.y > pin_height) {
    i@stopped = 1;    // Vellum reads this -- point won't move
}
```

```vex
// ─── Attrib Wrangle: pin_to_animated_geo ─────────────────────────────────────
// Run Over: Points
// For garment attachment: sample target position from animated mesh.
// Inputs: input 0 = cloth points, input 1 = animated body mesh

// Snap cloth point to nearest point on animated body
int nearest = nearpoint(1, @P);
vector target = point(1, "P", nearest);

// If close enough to body surface, pin it
float dist = distance(@P, target);
if (dist < chf("pin_radius")) {           // e.g. 0.05
    i@stopped = 1;
    @targetP = target;                    // vellumsolver uses targetP for animated pins
}
```

```vex
// ─── Attrib Wrangle: animated_pin_follow ─────────────────────────────────────
// Run Over: Points  -- place inside the solver's pre-roll or with vellumconstraintproperty
// Continuously update targetP so pinned points follow animation (per-frame wrangle).

int is_pinned = i@stopped;
if (is_pinned) {
    // Re-sample target from animated body each frame
    int nearest = nearpoint(1, @P);
    @targetP = point(1, "P", nearest);
}
```

```python
import hou

def add_pin_wrangle(geo_node_path, before_configure_node):
    """
    Insert a wrangle before vellumcloth to pin top edge by height.
    Adds a 'pin_height' channel parameter for easy adjustment.
    """
    geo = hou.node(geo_node_path)

    wrangle = geo.createNode("attribwrangle", "pin_by_height")
    wrangle.setInput(0, before_configure_node)

    # VEX: freeze any point above pin_height
    wrangle.parm("snippet").set(
        "float pin_height = chf('pin_height');\n"
        "if (@P.y > pin_height) { i@stopped = 1; }\n"
    )

    # Add the channel with a sensible default
    ptg = wrangle.parmTemplateGroup()
    parm = hou.FloatParmTemplate("pin_height", "Pin Height", 1, default_value=(0.9,))
    ptg.addParmTemplate(parm)
    wrangle.setParmTemplateGroup(ptg)
    wrangle.parm("pin_height").set(0.9)

    wrangle.parm("class").set(0)    # run over Points
    return wrangle
```

---

## Caching

```python
import hou

def setup_vellum_cache(geo_node_path, solver_node, cache_name="cloth"):
    """
    Add filecache after vellumsolver for geometry and optionally constraints.
    Always cache before rendering -- Vellum re-simulates from frame 1 otherwise.
    """
    geo = hou.node(geo_node_path)
    hip = hou.getenv("HIP")

    # ── Geometry cache ─────────────────────────────────────────────────────────
    geo_cache = geo.createNode("filecache", f"cache_{cache_name}_geo")
    geo_cache.setInput(0, solver_node, 0)    # solver output 0 = simulated geometry

    # .bgeo.sc = Blosc compressed (fastest read/write, smaller than .bgeo)
    geo_cache.parm("file").set(
        f"{hip}/cache/vellum/{cache_name}/$OS.$F4.bgeo.sc"
    )
    geo_cache.parm("loadfromdisk").set(0)    # 0=write (sim), 1=read (playback)
    geo_cache.parm("filetype").set(0)        # bgeo.sc

    # ── Constraint cache (optional -- useful for debugging) ────────────────────
    con_cache = geo.createNode("filecache", f"cache_{cache_name}_constraints")
    con_cache.setInput(0, solver_node, 1)    # solver output 1 = constraints

    con_cache.parm("file").set(
        f"{hip}/cache/vellum/{cache_name}_constraints/$OS.$F4.bgeo.sc"
    )
    con_cache.parm("loadfromdisk").set(0)

    # Output null reads from geo cache
    out = geo.createNode("null", "OUT_cached")
    out.setInput(0, geo_cache)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)

    print(f"Cache path: {hip}/cache/vellum/{cache_name}/")
    print("Set loadfromdisk=1 on both caches to read back without re-simulating.")

    return geo_cache, con_cache


def switch_cache_to_read(geo_cache_node, con_cache_node=None):
    """Flip caches to read mode (playback cached sim)."""
    geo_cache_node.parm("loadfromdisk").set(1)
    if con_cache_node:
        con_cache_node.parm("loadfromdisk").set(1)
    print("Cache switched to READ mode.")
```

---

## Import to Solaris / LOPs

```python
import hou

def import_vellum_to_lops(stage_node_path, sop_geo_node_path, vellum_cache_node_name):
    """
    Import cached Vellum geometry into LOPs via sopimport.
    If simulating cloth on a character: merge vellum sopimport with character sopimport.
    """
    stage = hou.node(stage_node_path)   # e.g. /stage

    # sopimport LOP: pulls SOP geometry into the USD stage each frame
    sop_import = stage.createNode("sopimport", "import_vellum_cloth")
    sop_import.parm("soppath").set(
        f"{sop_geo_node_path}/{vellum_cache_node_name}"
    )

    # USD primitive path where cloth will appear
    sop_import.parm("pathprefix").set("/cloth")

    # Time-varying: let it update every frame
    sop_import.parm("timevarying").set(1)

    # ── Merge with character (typical layered cloth workflow) ──────────────────
    # character_import = stage.node("import_character")
    # merge = stage.createNode("merge", "merge_cloth_and_character")
    # merge.setInput(0, character_import)
    # merge.setInput(1, sop_import)

    # ── Assign material to imported cloth ──────────────────────────────────────
    # mat_assign = stage.createNode("assignmaterial", "cloth_material")
    # mat_assign.setInput(0, sop_import)
    # mat_assign.parm("primpattern1").set("/cloth/geo/shape")
    # mat_assign.parm("matspecpath1").set("/materials/fabric_cotton")

    stage.layoutChildren()
    return sop_import


def full_vellum_lops_pipeline(hip_path, cache_name="cloth"):
    """
    Complete pipeline string (text description of node chain for reference).
    SOP: source -> vellumcloth -> vellumsolver -> filecache (write then read)
    LOP: sopimport -> (merge with character) -> assignmaterial -> karma
    """
    pipeline = {
        "sop_chain": [
            "source_geo",
            "vellumcloth (configure: 2 outputs -- geo + constraints)",
            "vellumsolver (in0=geo, in2=constraints)",
            f"filecache (write: {hip_path}/cache/vellum/{cache_name}/$F4.bgeo.sc)",
        ],
        "lop_chain": [
            "sopimport (soppath -> filecache OUT)",
            "merge (cloth + character)",
            "assignmaterial (primpattern = exact USD prim path)",
            "karma LOP",
            "usdrender ROP",
        ],
    }
    return pipeline
```

---

## Common Mistakes

**Cloth falls through body**: Collision thickness too thin or substeps too low. Increase `thickness` to match cloth thickness, set substeps to 15+ for tight-fitting garments.

**Cloth explodes on frame 1**: Extremely high stiffness (100000+) with only 5 substeps. Lower stiffness or raise substeps and constraint iterations together.

**Cloth is unexpectedly stretchy**: `stretchstiffness` is too low. Raise to 50000+ for non-stretch fabrics like denim.

**Hair passes through body**: Missing vellumcollider node, or collider not wired to solver input 1. Add Trail SOP before vellumcollider to supply velocity.

**Grains pile too high / won't spread**: Friction too high. Dry sand should be 0.3-0.5.

**Soft body collapses immediately**: Shape stiffness too low or no volume constraint. Raise `shapestiffness`, enable `volumestiffness` to 0.5+ for incompressible materials.

**Simulation is very slow**: Too many points combined with self-collision. Disable self-collision for preview, use simplified collision mesh (polyreduce to 10-20%).

**Jittery result / not converging**: Insufficient constraint iterations. Raise `constraintiterations` to 150+. Also check substeps -- too few for stiffness level.

**Garment starts in wrong position on character**: No drape step. Add `vellumdrape` node between configure and solver. Set frames=60-100, re-run when starting pose changes.

**solver input wiring wrong**: Configure node output 0 = geo -> solver input 0. Configure node output 1 = constraints -> solver input 2 (NOT input 1). Input 1 = collider geometry.

**filecache not updating**: Cache is in read mode (`loadfromdisk=1`). Flip to 0, re-sim, then flip back to 1 for playback.
