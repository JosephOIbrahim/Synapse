# MPM Production Workflows (Houdini 21)

## Triggers
mpm, material point method, mpm solver, mpm destruction, metal tearing, mpm slow motion,
paintball impact, pumpkin smash, multi-material mpm, rain simulation, surface tension,
snow interaction, mpm snow, multi-resolution mpm, creature breach, train wreck, mpm metal,
building destruction, structural destruction, mpm fracture, close gaps mpm, mpm retargeting,
mpm particles, mpm velocity, mpm stiffness, mpm friction, mpm auto sleep, mpm substeps,
narrow-band render cloud, mpm compression hardening, mpm production, mpm workflow,
mpm scale-up, mpm point cloud, mpm debris, mpm render, mpm Jp attribute

## Context
Production-proven MPM setups from the SideFX H21 Masterclass (parts 10-17). Each workflow
covers a specific destruction or effects scenario using the MPM solver. All Python code targets
the Houdini 21 Python API and runs inside a Python SOP or Houdini session unless noted.

---

## Destruction Pipeline — Metal Tearing

### Close Gaps: Per-Point Level Comparison

```python
# VEX wrangle: "close_gaps" — run Over Points
# Compares point-based vs piece-based deformation delta to decide whether to close a gap.
# Small delta = snap to point-based (closes gap). Large delta = stay piece-based (real tear).

float tolerance       = chf("tolerance");        # gap-closing aggressiveness (try 0.01–0.05)
float transition_width = chf("transition_width"); # prevents pops at threshold (try 0.005–0.02)

vector pt_deform   = v@point_deform;   # deformation from point-based (no fracture)
vector piece_deform = v@piece_deform;  # deformation from piece-based (fracture-aware)

float delta = length(pt_deform - piece_deform);

# Smooth blend near the tolerance threshold to avoid discontinuities
float weight = fit(delta, tolerance, tolerance + transition_width, 0.0, 1.0);

# weight=0 → point-based (close gap), weight=1 → piece-based (keep tear)
v@P += lerp(pt_deform, piece_deform, weight);
```

### Fracture Alignment to Stress Patterns

```python
# Python SOP: align fracture centroids to Jp (plastic deformation) hotspots
# Run after MPM sim; input 0 = MPM points with Jp, input 1 = fracture pieces

import hou

node = hou.pwd()
geo_mpm   = node.inputGeometry(0)   # MPM sim output
geo_frac  = node.inputGeometry(1)   # voronoi/boolean fracture pieces

out = node.geometry()
out.merge(geo_frac)

# Build Jp lookup: for each fracture piece, find the highest-Jp MPM point inside it
piece_attr = geo_mpm.findPointAttrib("piece")
jp_attr    = geo_mpm.findPointAttrib("Jp")

if piece_attr and jp_attr:
    from collections import defaultdict
    piece_jp = defaultdict(list)
    for pt in geo_mpm.points():
        p  = pt.attribValue("piece")
        jp = pt.attribValue("Jp")
        piece_jp[p].append((jp, pt.position()))

    # Move each fracture centroid to the highest-Jp point inside that piece
    centroid_attr = out.addAttrib(hou.attribType.Prim, "fracture_centroid", hou.Vector3())
    for prim in out.prims():
        piece_id = prim.attribValue("name") if out.findPrimAttrib("name") else str(prim.number())
        if piece_id in piece_jp:
            best = max(piece_jp[piece_id], key=lambda x: x[0])
            prim.setAttribValue("fracture_centroid", best[1])
```

### Fast Iteration: Isolate a Single Piece

```python
# Python snippet: blast everything except piece index 0 for rapid fracture testing
# Single piece: ~5 s sim time vs 10+ min for full model

import hou

def isolate_piece_for_test(geo_node_path, piece_index=0):
    """
    Prepend a Connectivity + Blast SOP to isolate one fracture piece.
    Call this before the MPM solver during iteration, remove for final sim.
    """
    net = hou.node(geo_node_path).parent()

    conn = net.createNode("connectivity", "connectivity_isolate")
    conn.setInput(0, hou.node(geo_node_path))
    conn.parm("connecttype").set(0)   # primitive connectivity

    blast = net.createNode("blast", "blast_isolate")
    blast.setInput(0, conn)
    blast.parm("group").set(f"@class!={piece_index}")
    blast.parm("negate").set(False)

    blast.layoutChildren()
    return blast

# Usage: replace mpm_solver input with the returned blast node during iteration
test_geo = isolate_piece_for_test("/obj/metal_geo/OUT_fractured")
```

---

## Slow-Motion Effects — Paintball Impact

### Scale-Up Workflow

```python
# Python SOP: apply 100x scale-up and compensate gravity / time scale
# MPM loses precision at small physical scales (< 0.05 m features).
# Scale everything up and adjust solver parameters to compensate.

import hou

SCALE_FACTOR = 100.0   # 100x scale-up

def configure_mpm_for_slowmo(mpm_solver_path):
    solver = hou.node(mpm_solver_path)
    if solver is None:
        raise RuntimeError(f"MPM solver not found: {mpm_solver_path}")

    # Time scale multiplied by 100 (same-speed physics at new scale)
    cur_timescale = solver.parm("timescale").eval()
    solver.parm("timescale").set(cur_timescale * SCALE_FACTOR)

    # Gravity divided by 100 (world-space gravity stays correct after scale)
    cur_gravity = solver.parm("gravity").eval()   # typically -9.81
    solver.parm("gravity").set(cur_gravity / SCALE_FACTOR)

    print(f"[MPM slowmo] timescale={solver.parm('timescale').eval():.2f}  "
          f"gravity={solver.parm('gravity').eval():.4f}")

# VEX wrangle: scale geometry 100x before MPM solver
# (attach to Transform SOP with scale=100 or inline in a wrangle)
```

```vex
// VEX wrangle: scale geometry before MPM — run Over Points
// Slot this before the DOP network input.
v@P *= 100.0;
```

### Shell Setup — Paintball Casing

```python
# Python: configure rubber shell material on an MPM Object DOP
import hou

def setup_paintball_shell(dop_net_path, object_name="paintball_shell"):
    """Configure a hollow rubber shell for paintball casing."""
    net = hou.node(dop_net_path)

    mpm_obj = net.createNode("mpmobject", object_name)

    # Rubber preset values
    mpm_obj.parm("preset").set("rubber")        # elastic deformation base
    mpm_obj.parm("type").set("surface")         # hollow shell — NOT solid fill

    # 10x stiffer than rubber default to resist initial deformation
    default_stiffness = mpm_obj.parm("stiffness").eval()
    mpm_obj.parm("stiffness").set(default_stiffness * 10.0)

    return mpm_obj
```

### Paint Interior — Liquid Fill

```python
# Python: configure water-like liquid fill inside the paintball shell
import hou

def setup_paint_fill(dop_net_path, object_name="paint_fill"):
    """Configure the liquid paint interior of the paintball."""
    net = hou.node(dop_net_path)

    mpm_obj = net.createNode("mpmobject", object_name)

    # Water preset: liquid behavior
    mpm_obj.parm("preset").set("water")

    # Increased incompressibility to prevent volume loss on impact
    base_incompress = mpm_obj.parm("incompressibility").eval()
    mpm_obj.parm("incompressibility").set(base_incompress * 3.0)

    return mpm_obj
```

### Surface Tension Settings

```python
# Python: configure surface tension on the MPM solver for paintball liquid
import hou

def configure_surface_tension(mpm_solver_path):
    solver = hou.node(mpm_solver_path)

    # Point-based surface tension method (more stable than grid-based for thin films)
    solver.parm("surfacetension_method").set("point")

    # Raise min substeps: prevents tunneling at tension boundaries
    solver.parm("minsubsteps").set(4)

    # Global substeps = 2 for stability with strong tension
    solver.parm("substeps").set(2)

    # Reduce material condition number to improve solver stability
    solver.parm("condnum").set(0.1)

    print("[MPM] Surface tension configured: point method, minsubsteps=4, substeps=2")
```

### Iteration vs Final Quality Settings

```python
# Python: switch between iteration and final quality presets
import hou

def set_mpm_quality(mpm_solver_path, mode="iteration"):
    """
    mode="iteration": fast preview (2x particle separation, default adaptivity)
    mode="final":     production quality (1x separation, adaptivity=0 prevents color flicker)
    """
    solver = hou.node(mpm_solver_path)

    if mode == "iteration":
        solver.parm("particlesep_mult").set(2.0)   # 2x separation = 8x fewer particles
        # leave adaptivity at default
        print("[MPM quality] ITERATION mode: 2x separation multiplier")

    elif mode == "final":
        solver.parm("particlesep_mult").set(1.0)   # full resolution
        # Adaptivity=0 prevents frame-to-frame topology changes causing UV/color flicker
        solver.parm("adaptivity").set(0.0)
        print("[MPM quality] FINAL mode: 1x separation, adaptivity=0")
```

---

## Multi-Material Organic — Pumpkin Smash

### Multi-Layer Setup

```python
# Python SOP: build three-layer MPM point cloud (skin / flesh / seeds)
import hou

def build_pumpkin_layers(geo_node_path):
    """
    Returns a merged point cloud with mpm_material attribute set per layer.
    Layers: skin (outer shell), flesh (stringy interior), seeds (instanced geo).
    """
    net = hou.node(geo_node_path).parent()

    # --- Skin layer: scatter on outer surface with shell thickness ---
    skin_scatter = net.createNode("scatter", "skin_scatter")
    skin_scatter.parm("npts").set(2_000_000)
    # parm "sourcegrouptype" selects surface scatter

    skin_attrib = net.createNode("attribwrangle", "skin_attrib")
    skin_attrib.setInput(0, skin_scatter)
    skin_attrib.parm("snippet").set('s@mpm_material = "skin";')

    # --- Flesh layer: volume-fill interior ---
    flesh_scatter = net.createNode("scatter", "flesh_scatter")
    flesh_scatter.parm("npts").set(30_000_000)

    flesh_attrib = net.createNode("attribwrangle", "flesh_attrib")
    flesh_attrib.setInput(0, flesh_scatter)
    flesh_attrib.parm("snippet").set('s@mpm_material = "flesh";')

    # --- Seeds: instance geometry scattered inside volume ---
    seed_scatter = net.createNode("scatter", "seed_scatter")
    seed_scatter.parm("npts").set(200)

    seed_attrib = net.createNode("attribwrangle", "seed_attrib")
    seed_attrib.setInput(0, seed_scatter)
    seed_attrib.parm("snippet").set('s@mpm_material = "seed";')

    # Merge all layers
    merge = net.createNode("merge", "pumpkin_merge")
    merge.setInput(0, skin_attrib)
    merge.setInput(1, flesh_attrib)
    merge.setInput(2, seed_attrib)

    merge.layoutChildren()
    return merge
```

### Point Optimization: Fuse + Deduplicate

```python
# VEX wrangle: tag duplicate coincident points for removal
# Target: reduce 40M raw points → ~9M after fuse, ~12M after dedup

# Step 1: Fuse SOP settings (Python)
import hou

def optimize_mpm_points(fuse_node_path, dedup_node_path):
    """Apply fuse and deduplication settings for multi-layer MPM point clouds."""
    fuse = hou.node(fuse_node_path)
    fuse.parm("dist").set(0.001)       # snap points closer than 0.001 units
    fuse.parm("dosnap").set(True)
    fuse.parm("recompute_n").set(True)

    # Deduplicate: remove coincident points between layers
    dedup = hou.node(dedup_node_path)
    # Typically an "fuse" SOP with "unique points" mode
    dedup.parm("fusedist").set(0.0005)

    print(f"[MPM optimize] Fuse dist=0.001, dedup dist=0.0005")
    print("[MPM optimize] Expected: 40M → 9M (fuse) → 12M (after dedup adds back boundary)")
```

### Decoupled Material Sourcing

```python
# Python SOP: configure materials on reference cloud, transfer to optimized cloud
# This separates material authoring from simulation geometry.

import hou

def transfer_mpm_attributes(source_node_path, optimized_node_path, output_node_path):
    """
    Transfer mpm_material and stiffness attributes from source (with material setup)
    to the fused/optimized point cloud used for simulation.
    """
    net = hou.node(source_node_path).parent()

    attrib_transfer = net.createNode("attribtransfer", "mpm_attrib_transfer")
    attrib_transfer.setInput(0, hou.node(optimized_node_path))   # destination
    attrib_transfer.setInput(1, hou.node(source_node_path))       # source with materials

    # Transfer point attributes: mpm_material, stiffness, friction
    attrib_transfer.parm("ptattribs").set("mpm_material stiffness friction")
    attrib_transfer.parm("searchmethod").set(0)   # 0 = nearest point

    return attrib_transfer
```

### Velocity Handling for Slow-Motion

```python
# VEX wrangle: "velocity_split" — run Over Points
# Splits velocity usage: render motion blur uses scaled velocity, debris sims use real-time.

float time_scale = chf("time_scale");   # match MPM solver time scale (e.g., 100.0)
string mode      = chs("mode");         # "render" or "debris"

if (mode == "render") {
    // Motion blur: multiply by time scale so blur length is correct in slow-motion
    v@v *= time_scale;
} else {
    // Debris simulation: divide by time scale so debris moves at real-time speed
    v@v /= time_scale;
}
```

### Post-Simulation: UV Transfer + Depth Masking

```python
# Python SOP: post-sim operations — UV transfer, depth-based coloring, mesh clamping
import hou

def setup_pumpkin_post_sim(net_path, rest_geo_path, sim_output_path):
    net = hou.node(net_path)

    # 1. UV transfer from pre-sim rest geometry
    uv_transfer = net.createNode("attribtransfer", "uv_transfer")
    uv_transfer.setInput(0, hou.node(sim_output_path))   # deformed mesh
    uv_transfer.setInput(1, hou.node(rest_geo_path))     # original UVs
    uv_transfer.parm("ptattribs").set("uv")
    uv_transfer.parm("searchmethod").set(0)

    # 2. Depth-based dual-color mask (interior orange vs exterior green)
    color_wrangle = net.createNode("attribwrangle", "depth_color")
    color_wrangle.setInput(0, uv_transfer)
    color_wrangle.parm("snippet").set("""
// depth_color VEX: run Over Points
float depth = fit01(clamp(f@depth_normalized, 0, 1), 0, 1);
// interior: orange-yellow; exterior: dark green
vector interior_col = {0.9, 0.5, 0.1};
vector exterior_col = {0.2, 0.35, 0.1};
v@Cd = lerp(exterior_col, interior_col, depth);
""")

    # 3. Jp + curvature mask smooth
    smooth_wrangle = net.createNode("attribwrangle", "jp_smooth_mask")
    smooth_wrangle.setInput(0, color_wrangle)
    smooth_wrangle.parm("snippet").set("""
// Jp (plastic deformation) drives smoothing mask; curvature refines it
float jp_mask   = fit(f@Jp, 1.0, 1.5, 0.0, 1.0);   // 1.0 = undeformed, >1 = deformed
float curv_mask = fit(f@curvature, -0.5, 0.5, 1.0, 0.0);
f@smooth_mask   = jp_mask * curv_mask;
""")

    # 4. Clamp mesh to first frame (hold static before impact frame)
    time_blend = net.createNode("timeblend", "hold_pre_impact")
    time_blend.setInput(0, smooth_wrangle)
    # Set frame range in the TimeBlend SOP to clamp at impact frame

    return time_blend
```

---

## Rain and Surface Tension — Car Rain

### Reverse-Time Raindrop Sync

```python
# Python: emit raindrops at pre-calculated positions so each hits its target exactly
import hou

def build_reverse_time_droplets(impact_points_path, emission_height, gravity=-9.81):
    """
    Given impact point positions and frame numbers, backtrack each droplet
    to find its emission position at the given emission_height.
    Returns a point cloud with emission P and v attributes.
    """
    net = hou.node(impact_points_path).parent()

    # Attrib wrangle: backtrack velocity from impact frame to emission height
    backtrack = net.createNode("attribwrangle", "backtrack_droplets")
    backtrack.setInput(0, hou.node(impact_points_path))
    backtrack.parm("snippet").set(f"""
// Backtrack VEX: run Over Points
// f@impact_frame stores the frame when this droplet hits the surface
float fps         = 24.0;
float impact_t    = f@impact_frame / fps;
float emit_height = {emission_height};                  // world-space Y of emission
float g           = {gravity};                          // gravity m/s^2

// Time for droplet to fall from emit_height to impact Y (quadratic)
float dy   = emit_height - v@P.y;
float disc = v@v.y * v@v.y + 2.0 * g * dy;
if (disc < 0) disc = 0.0;
float t_fall = (-v@v.y - sqrt(disc)) / g;

// Emission position: reverse velocity over t_fall
v@emit_P = v@P - v@v * t_fall - set(0, 0.5 * g * t_fall * t_fall, 0);
v@emit_P.y = emit_height;                               // snap to emission plane
""")

    # Flip time: reverse velocity for actual simulation
    flip_vel = net.createNode("attribwrangle", "flip_velocity")
    flip_vel.setInput(0, backtrack)
    flip_vel.parm("snippet").set("v@v *= -1.0;")

    return flip_vel
```

### IOR Distance Correction

```python
# VEX wrangle: "ior_correction" — run Over Points on final water mesh
// Fixes bright refraction artifacts from air gaps between water and car surface.
// Distance-to-collider attribute drives IOR blend.

float dist_to_collider = f@dist_to_car;   # pre-computed by Attribute From Map or VDB
float near_thresh = 0.002;                # touching threshold
float far_thresh  = 0.02;                 # fully separated threshold

float ior_water = 1.333;
float ior_air   = 1.0;

// Near surface: IOR→1.0 (no refraction through thin film)
// Far from surface: IOR→1.333 (full water refraction)
f@ior = fit(dist_to_collider, near_thresh, far_thresh, ior_air, ior_water);
```

```python
# Python: configure IOR ramp in a mantra/karma shader via Python
import hou

def set_ior_ramp(material_node_path):
    """Set the IOR ramp on a water surface material — near=1.0, far=1.333."""
    mat = hou.node(material_node_path)
    ramp_parm = mat.parm("ior_ramp")
    if ramp_parm:
        # basis=linear, positions=[0,1], values=[1.0, 1.333]
        ramp = hou.Ramp(
            (hou.rampBasis.Linear, hou.rampBasis.Linear),
            (0.0, 1.0),
            (1.0, 1.333)
        )
        ramp_parm.set(ramp)
```

### Key Solver Settings

```python
# Python: configure MPM solver for rain / surface tension simulation
import hou

def configure_rain_solver(mpm_solver_path):
    solver = hou.node(mpm_solver_path)

    # Strong surface tension to hold droplets together on car surface
    solver.parm("surfacetension").set(0.072)         # water ~0.072 N/m
    solver.parm("surfacetension_method").set("point") # point-based for thin films

    # Increased substeps for stability with high tension
    solver.parm("substeps").set(4)
    solver.parm("minsubsteps").set(2)

    # Particle-level collision for better thin-film behavior on curved surfaces
    solver.parm("collisionmethod").set("particle")

    # Collision detection distance > 1 particle radius:
    # lets water gather and bead at panel edges and door seams
    sep = solver.parm("particlesep").eval()
    solver.parm("collisiondist").set(sep * 1.5)

    print("[MPM rain] surface_tension=0.072, substeps=4, collision=particle")
```

### Secondary Effects (Non-MPM)

```python
# Python: create secondary effect nodes alongside the MPM sim
import hou

def build_rain_secondary_fx(net_path, mpm_output_path):
    net = hou.node(net_path)
    mpm_out = hou.node(mpm_output_path)

    # Mist: POP simulation driven by high-velocity MPM particles
    pop_source = net.createNode("popsource", "mist_source")
    pop_source.parm("birthtype").set(0)   # rate-based
    pop_source.parm("birthrate").set(5000)
    # Connect mist POP net to receive fast-moving droplet positions as source

    # Condensation: SOP solver on car surface geometry
    sop_solver = net.createNode("sopsolver", "condensation_solver")
    # SOP solver grows/shrinks condensation point cloud per frame

    # Dynamic puddles: ripple solver on ground plane
    ripple = net.createNode("ripplesolver", "puddle_ripple")
    ripple.parm("viscosity").set(0.05)

    return pop_source, sop_solver, ripple
```

---

## Snow Interaction — Wolf in Snow

### Camera-Frustum Culling

```python
# Python SOP: restrict MPM fill to camera frustum only
import hou

def build_frustum_vdb(camera_path, trail_geo_path, padding=2.0):
    """
    1. Trail character paths through the shot.
    2. Clip trail to camera frustum.
    3. Bake clipped region to VDB.
    Only fill VDB region with MPM particles.
    """
    net = hou.node(trail_geo_path).parent()

    # Frustum geometry from camera
    frustum = net.createNode("camerafrustum", "cam_frustum")
    frustum.parm("camera").set(camera_path)
    frustum.parm("depth").set(50.0)   # depth of snow field

    # Intersect character trail with frustum
    trail = net.createNode("trail", "char_trail")
    trail.setInput(0, hou.node(trail_geo_path))
    trail.parm("traillen").set(100)   # frames of trail

    boolean_node = net.createNode("boolean", "trail_frustum_clip")
    boolean_node.setInput(0, trail)
    boolean_node.setInput(1, frustum)
    boolean_node.parm("booleanop").set("intersect")

    # Convert clipped trail to VDB for MPM particle fill region
    vdb_from_poly = net.createNode("vdbfrompolygons", "frustum_vdb")
    vdb_from_poly.setInput(0, boolean_node)
    vdb_from_poly.parm("voxelsize").set(0.05)

    return vdb_from_poly
```

### Depth-Based Volume Reduction

```python
# VEX wrangle: "depth_volume_lerp" — run Over Points on MPM fill cloud
// Lerp between full depth (paw penetration zones) and surface-only depth.
// Saves particles in areas that only need surface displacement.

float surface_depth = chf("surface_depth");  # thin surface layer depth (e.g., 0.05)
float full_depth    = chf("full_depth");      # full sim depth under paw contact (e.g., 0.3)
float contact_mask  = f@contact_mask;         # pre-baked: 1.0 under paws, 0.0 elsewhere

float max_depth = lerp(surface_depth, full_depth, contact_mask);

// Remove particles below depth threshold
vector surface_n = v@N;
float pt_depth   = -dot(v@P - v@surface_P, surface_n);  // signed depth below surface

if (pt_depth > max_depth) {
    removepoint(0, @ptnum);
}
```

### Auto Sleep Configuration

```python
# Python: configure auto-sleep on MPM solver for snow efficiency
# At peak: ~98% passive particles, ~2% active
import hou

def configure_snow_autosleep(mpm_solver_path):
    solver = hou.node(mpm_solver_path)

    # Raise velocity threshold: particles settle to sleep faster after disturbance
    # Default is low; snow should sleep quickly after paw passes
    solver.parm("sleepthreshold").set(0.05)    # particles below this speed → sleep

    # Enable state debugging attribute to monitor active/passive percentages
    solver.parm("debugstate").set(True)
    # The "state" detail attribute will contain:
    # "active: 2%, passive: 96%, boundary: 2%"

    print("[MPM snow] sleep_threshold=0.05, debug_state=True")
    print("[MPM snow] Expected: 98% passive at peak, 2% active under paw contact")
```

### Stiffness Noise for Natural Fracture Boundaries

```python
# VEX wrangle: "stiffness_noise" — run Over Points on MPM source points
// Noise-driven stiffness creates natural fracture boundaries where stiffness transitions.
// Without this, snow fractures in perfectly straight lines.

float base_stiffness = chf("base_stiffness");    # start high (e.g., 5000)
float noise_freq     = chf("noise_freq");         # noise frequency (e.g., 2.5)
float noise_seed     = chf("noise_seed");         # per-shot seed

// Noise remapped to [2, 5] range — multiplied against base stiffness
float n = noise(v@P * noise_freq + set(noise_seed, 0, 0));
float mult = fit(n, 0.0, 1.0, 2.0, 5.0);

f@stiffness = base_stiffness * mult;
```

### Surface Mask: Preserve Snow Structure

```python
# Python SOP: multiply MPM density grid by snow SDF to preserve surface granularity
import hou

def build_snow_surface_mask(vdb_density_path, snow_sdf_path):
    net = hou.node(vdb_density_path).parent()

    # VDB combine: density * surface SDF mask
    combine = net.createNode("vdbcombine", "snow_surface_mask")
    combine.setInput(0, hou.node(vdb_density_path))
    combine.setInput(1, hou.node(snow_sdf_path))

    # Multiply operation: preserves density only where SDF is near-surface
    combine.parm("operation").set("multiply")
    combine.parm("aname").set("density")
    combine.parm("bname").set("surface")

    return combine
```

---

## Multi-Resolution Pipeline — Creature Breach

### Two-Pass Strategy Setup

```python
# Python: configure two MPM solvers — low-res fracture identification, high-res detail
import hou

def setup_two_pass_mpm(dop_net_path):
    """
    Pass 1: low-res (separation=0.11) — identify fracture regions via Jp attribute.
    Pass 2: high-res (separation=0.06) — detail only in dynamic fracture patch.
    """
    net = hou.node(dop_net_path)

    # --- Low-res solver ---
    solver_lo = net.createNode("mpmobject", "creature_lo_res")
    solver_lo.parm("particlesep").set(0.11)
    solver_lo.parm("preset").set("clay")   # creature flesh base

    # --- High-res solver: only fills the dynamic patch ---
    solver_hi = net.createNode("mpmobject", "creature_hi_res")
    solver_hi.parm("particlesep").set(0.06)    # 0.06 vs 0.11 → ~8x more particles
    solver_hi.parm("preset").set("clay")

    print("[MPM two-pass] lo-res sep=0.11, hi-res sep=0.06 (~8x particle count)")
    return solver_lo, solver_hi
```

### Extract Fracture Patch via Jp

```python
# Python SOP: use Jp attribute from low-res pass to build high-res fill region
import hou

def extract_fracture_patch(lo_res_geo_path, jp_threshold=1.2):
    """
    Jp > jp_threshold indicates plastic deformation (fracture zone).
    Non-fractured points become static colliders for the high-res pass.
    """
    net = hou.node(lo_res_geo_path).parent()

    # Tag fractured vs static points
    jp_tag = net.createNode("attribwrangle", "jp_fracture_tag")
    jp_tag.setInput(0, hou.node(lo_res_geo_path))
    jp_tag.parm("snippet").set(f"""
// Jp=1.0 is rest (undeformed); >1.0 = stretched; threshold flags fracture zone
i@is_fractured = (f@Jp > {jp_threshold}) ? 1 : 0;
""")

    # Blast: separate dynamic patch
    dynamic_patch = net.createNode("blast", "dynamic_patch")
    dynamic_patch.setInput(0, jp_tag)
    dynamic_patch.parm("group").set("@is_fractured=1")
    dynamic_patch.parm("negate").set(True)   # keep fractured points

    # Static collider: non-fractured region at high friction + stickiness
    static_collider = net.createNode("blast", "static_collider")
    static_collider.setInput(0, jp_tag)
    static_collider.parm("group").set("@is_fractured=0")
    static_collider.parm("negate").set(True)

    return dynamic_patch, static_collider
```

### Velocity Clamping at Resolution Boundaries

```python
# VEX wrangle: "velocity_clamp" — run Over Points — prevents explosion artifacts
// Enforce max displacement per frame at resolution boundary between lo and hi-res.
// 0.25 units/frame is the empirically safe limit for this separation ratio.

float max_disp_per_frame = chf("max_disp");   # 0.25 units (default)
float fps = 24.0;

float speed = length(v@v);
float max_speed = max_disp_per_frame * fps;

if (speed > max_speed) {
    v@v = normalize(v@v) * max_speed;
}
```

### Narrow-Band Render Cloud (Erosion Pipeline)

```python
# Python SOP: build narrow-band render cloud — 166M → 88M via erosion
import hou

def build_narrow_band_cloud(fill_node_path, separation=0.04):
    """
    Fill geometry at fine separation (0.04), then erode to keep only a surface shell.
    Full volume at 0.04 sep = ~1B points. Narrow band after erosion = ~88M.
    1 dilation + 1 smooth + 4 erosion passes = surface-only shell.
    """
    net = hou.node(fill_node_path).parent()

    fill = hou.node(fill_node_path)

    # Convert to VDB density for erosion operations
    vdb = net.createNode("vdbfrompoints", "fill_vdb")
    vdb.setInput(0, fill)
    vdb.parm("voxelsize").set(separation * 0.5)

    # Dilation pass (1x) — ensures full surface coverage
    dilate = net.createNode("vdbactivate", "dilate_1x")
    dilate.setInput(0, vdb)
    dilate.parm("operation").set("dilate")
    dilate.parm("iterations").set(1)

    # Smooth pass (1x) — removes jagged voxels
    smooth = net.createNode("vdbsmooth", "smooth_1x")
    smooth.setInput(0, dilate)
    smooth.parm("iterations").set(1)

    # Erosion passes (4x) — removes interior, keeps surface shell
    erode = net.createNode("vdbactivate", "erode_4x")
    erode.setInput(0, smooth)
    erode.parm("operation").set("erode")
    erode.parm("iterations").set(4)

    # Scatter final render cloud into narrow-band shell
    scatter = net.createNode("scatter", "render_cloud")
    scatter.setInput(0, erode)
    scatter.parm("density").set(1.0 / (separation ** 3))

    print(f"[MPM narrow-band] fill sep={separation}, estimated 166M→88M after erosion")
    return scatter
```

### Orient-Based Retargeting

```python
# Python SOP: capture render cloud to nearest MPM particle and add noise
import hou

def build_retargeting(render_cloud_path, mpm_rest_path, mpm_anim_path):
    net = hou.node(render_cloud_path).parent()

    # Capture: nearest MPM particle in rest pose
    capture = net.createNode("attribtransfer", "mpm_capture")
    capture.setInput(0, hou.node(render_cloud_path))
    capture.setInput(1, hou.node(mpm_rest_path))
    capture.parm("ptattribs").set("orient N")
    capture.parm("searchmethod").set(0)   # nearest point

    # Deform: apply animated MPM motion to render cloud
    deform = net.createNode("attribwrangle", "retarget_deform")
    deform.setInput(0, capture)
    deform.parm("snippet").set("""
// Break Voronoi artifacts at capture boundaries with noise
float noise_amp  = chf("boundary_noise_amp");    // e.g., 0.02
float noise_freq = chf("boundary_noise_freq");   // e.g., 8.0

vector noise_offset = noise(v@P * noise_freq + {0, @Frame * 0.1, 0}) - {0.5, 0.5, 0.5};
v@P += noise_offset * noise_amp * (1.0 - f@capture_weight);
""")

    return deform
```

---

## Large-Scale Metal — Train Wreck

### Surface Scatter Mode

```python
# Python: configure MPM object for thin-walled sheet metal (surface particles only)
import hou

def setup_metal_surface_scatter(dop_net_path, object_name="train_metal"):
    net = hou.node(dop_net_path)

    mpm_obj = net.createNode("mpmobject", object_name)
    mpm_obj.parm("preset").set("metal")
    mpm_obj.parm("type").set("surface")     # surface scatter only — no interior fill
    mpm_obj.parm("thickness").set(0.003)    # sheet metal thickness in scene units

    # Compression hardening: promotes tearing over bending
    # Metal panels should rip apart, not deform like rubber
    mpm_obj.parm("compressionhardening").set(5.0)   # augments metal material

    print(f"[MPM metal] type=surface, thickness=0.003, compression_hardening=5.0")
    return mpm_obj
```

### Varying Friction VDB

```python
# Python SOP: bake per-surface friction to a VDB grid
import hou

FRICTION_TABLE = {
    "rails":  0.5,    # steel-on-steel: low friction
    "ground": 1.25,   # rough ballast: high friction
    "ties":   0.8,    # wood ties: medium friction
}

def build_friction_vdb(surface_geo_path, voxel_size=0.05):
    """
    Bake friction attribute to a VDB fog volume.
    MPM solver reads this grid per-particle to apply spatially varying friction.
    """
    net = hou.node(surface_geo_path).parent()

    # Tag each surface piece with friction value
    friction_tag = net.createNode("attribwrangle", "friction_tag")
    friction_tag.setInput(0, hou.node(surface_geo_path))
    friction_tag.parm("snippet").set("""
string surf = s@surface_type;
if (surf == "rails")       f@friction = 0.5;
else if (surf == "ground") f@friction = 1.25;
else if (surf == "ties")   f@friction = 0.8;
else                       f@friction = 0.7;   // default
""")

    # Bake friction to VDB
    vdb = net.createNode("vdbfrompolygons", "friction_vdb")
    vdb.setInput(0, friction_tag)
    vdb.parm("voxelsize").set(voxel_size)
    vdb.parm("surfaceattributes").set("friction")

    return vdb
```

### Consistent Point Count — Freeze Deleted Particles

```python
# VEX wrangle: "freeze_deleted" — run Over Points
// Freeze deleted particles at their last known position instead of removing them.
// Required for retargeting: point indices must remain stable across all frames.

int is_deleted = i@deleted;    # MPM sets this flag when a particle is removed

if (is_deleted) {
    // Hold position from previous frame — do NOT remove the point
    v@v = {0, 0, 0};           # zero velocity
    v@P = v@last_P;            # last known position (stored each frame before this wrangle)
    i@active = 0;              # mark as inactive for solver (won't affect sim)
}

// Each frame: cache current position for next frame's freeze
v@last_P = v@P;
```

### Debris Rolling Rotation

```python
# VEX wrangle: "debris_rotation" — run Over Points on separated debris pieces
// Natural tumbling: rotation axis perpendicular to velocity, angular speed perimeter-based.

float damping = 0.25;           # prevents infinite spinning
vector vel    = v@v;
float  speed  = length(vel);

if (speed > 0.001) {
    // Rotation axis: perpendicular to velocity direction
    vector up    = {0, 1, 0};
    vector right = cross(normalize(vel), up);
    if (length(right) < 0.001) right = {1, 0, 0};  // fallback for vertical motion

    // Angular velocity: larger debris (bigger perimeter) rotates slower
    float radius   = f@pscale * 0.5;
    float omega    = speed / max(radius, 0.01);     // v = r*omega → omega = v/r

    // Store on custom attribute (NOT @w — POP solver would override @w)
    v@debris_w = normalize(right) * omega;
}

// Apply damping to existing rotation
v@debris_w *= (1.0 - damping * f@TimeInc);
```

---

## Structural Destruction — Building Attack

### Making Models Destruction-Ready

```python
# Python SOP: prep pipeline — fuse edges, VDB close, add pillars, transfer UVs
import hou

def prep_building_for_mpm(geo_node_path, pillar_positions=None):
    net = hou.node(geo_node_path).parent()
    geo_in = hou.node(geo_node_path)

    # Step 1: Fuse edges — remove tiny gaps in architectural models
    fuse = net.createNode("fuse", "fuse_edges")
    fuse.setInput(0, geo_in)
    fuse.parm("dist").set(0.005)   # 5mm tolerance for architectural gap fusing

    # Step 2: VDB close — make geometry watertight
    vdb_close = net.createNode("vdbfrompolygons", "vdb_watertight")
    vdb_close.setInput(0, fuse)
    vdb_close.parm("voxelsize").set(0.02)

    vdb_to_poly = net.createNode("convertvdb", "vdb_to_poly")
    vdb_to_poly.setInput(0, vdb_close)
    vdb_to_poly.parm("conversion").set(0)   # VDB to polygons

    # Step 3: Add internal pillars (structural supports for realistic fracture)
    if pillar_positions:
        merge = net.createNode("merge", "add_pillars")
        merge.setInput(0, vdb_to_poly)
        for i, pos in enumerate(pillar_positions):
            tube = net.createNode("tube", f"pillar_{i}")
            tube.parm("radx").set(0.15)
            tube.parm("rady").set(0.15)
            tube.parm("height").set(3.0)
            # Translate to position
            xform = net.createNode("xform", f"pillar_xform_{i}")
            xform.setInput(0, tube)
            xform.parm("tx").set(pos[0])
            xform.parm("ty").set(pos[1])
            xform.parm("tz").set(pos[2])
            merge.setNextInput(xform)

    # Step 4: Transfer UVs from original clean mesh
    uv_transfer = net.createNode("attribtransfer", "uv_transfer")
    uv_transfer.setInput(0, merge if pillar_positions else vdb_to_poly)
    uv_transfer.setInput(1, geo_in)
    uv_transfer.parm("ptattribs").set("uv")

    return uv_transfer
```

### Staggered Projectile Emission

```python
# Python: backtrack each projectile to calculate emission position
import hou, math

GRAVITY = -9.81   # m/s^2

def compute_projectile_emission(
    impact_pos,        # (x, y, z) world-space impact target
    impact_frame,      # frame when projectile hits
    emit_height,       # Y height to emit from
    velocity_mag=50.0, # projectile speed m/s
    fps=24.0
):
    """
    Given a target impact position and frame, backtrack the projectile to
    find the emission position at emit_height so it lands exactly on target.
    Returns (emit_pos, emit_velocity, emit_frame).
    """
    impact_t = impact_frame / fps

    # Vertical component: solve for time to fall from emit_height to impact_pos.y
    dy = impact_pos[1] - emit_height   # negative (falling)
    # y = emit_height + vy*t + 0.5*g*t^2 → 0 = 0.5*g*t^2 + vy*t - dy
    # Use vy from velocity_mag direction angle
    angle_rad = math.radians(30)   # launch angle above horizontal
    vy = velocity_mag * math.sin(angle_rad)

    disc = vy**2 - 2 * GRAVITY * dy
    if disc < 0:
        raise ValueError(f"Cannot reach impact height {impact_pos[1]} from emit_height {emit_height}")

    t_flight = (-vy - math.sqrt(disc)) / GRAVITY   # positive root

    emit_frame = impact_frame - int(t_flight * fps)

    # Horizontal components: backtrack from impact position
    vx = velocity_mag * math.cos(angle_rad)
    emit_x = impact_pos[0] - vx * t_flight
    emit_z = impact_pos[2]
    emit_pos = (emit_x, emit_height, emit_z)

    emit_velocity = (vx, vy, 0.0)

    return emit_pos, emit_velocity, emit_frame

# Example usage:
impacts = [
    ((2.5, 0.0, 0.0), 48),   # projectile 1: hits at frame 48
    ((5.0, 3.0, 1.0), 72),   # projectile 2: hits at frame 72
]

for pos, frame in impacts:
    ep, ev, ef = compute_projectile_emission(pos, frame, emit_height=30.0)
    print(f"  emit_pos={ep}, emit_vel={ev}, emit_frame={ef}")
```

### Disable Unchanging Material Properties

```python
# Python: disable "Assume Unchanging Material Properties" for mid-sim emission
import hou

def configure_late_emission(mpm_solver_path):
    """
    CRITICAL: Must disable 'Assume Unchanging Material Properties' when emitting
    stiffer projectile materials mid-simulation. Leaving it enabled causes the
    solver to use incorrect material properties for late-emitted particles.
    """
    solver = hou.node(mpm_solver_path)

    # Disable the assumption — solver recomputes material props each step
    solver.parm("assumeunchangingmaterial").set(False)

    print("[MPM building] 'Assume Unchanging Material Properties' DISABLED")
    print("[MPM building] Required for staggered projectile emission with varying stiffness")
```

### Vibration Damping for Undamaged Structure

```python
# VEX wrangle: "vibration_damp" — run Over Points on building MPM output
// Lerp building points between frame 1 position and last stable pre-impact frame.
// Removes solver-induced vibration in undamaged portions of the structure.

int   impact_frame   = chi("impact_frame");    # first frame of any impact
float damp_blend     = chf("damp_blend");      # 0.0=no damp, 1.0=full freeze (try 0.7)

// is_undamaged: 1 if this point never fractured (pre-computed, cached to attrib)
int undamaged = i@is_undamaged;

if (undamaged && @Frame < impact_frame) {
    // Before impact: freeze to rest position (eliminates pre-impact solver vibration)
    v@P = v@rest_P;
    v@v = {0, 0, 0};
} else if (undamaged && @Frame >= impact_frame) {
    // After impact: blend between animated and rest to damp residual vibration
    v@P = lerp(v@P, v@rest_P, damp_blend);
}
```

### Per-Projectile Fracture Namespace

```python
# Python: create per-projectile voronoi fracture with unique namespaces
import hou

def create_per_projectile_fractures(building_geo_path, impact_positions, seed_base=42):
    """
    Use unique fracture namespace per projectile (with loop iteration suffix).
    Prevents fracture patterns from interfering across different impact zones.
    """
    net = hou.node(building_geo_path).parent()
    building = hou.node(building_geo_path)

    fracture_outputs = []

    for i, (impact_pos, impact_frame) in enumerate(impact_positions):
        namespace = f"projectile_{i:03d}"   # unique per-projectile

        # Voronoi points centered on impact position with radial falloff
        scatter = net.createNode("scatter", f"scatter_{namespace}")
        scatter.setInput(0, building)
        scatter.parm("npts").set(200)
        scatter.parm("seed").set(seed_base + i)   # unique seed per projectile

        # Voronoi fracture with namespaced piece names
        vfrac = net.createNode("voronoifracture", f"vfrac_{namespace}")
        vfrac.setInput(0, building)
        vfrac.setInput(1, scatter)
        vfrac.parm("innerpieceattrib").set(f"piece_{namespace}")   # namespaced attribute
        vfrac.parm("seed").set(seed_base + i * 100)

        fracture_outputs.append(vfrac)
        print(f"[MPM building] fracture namespace: {namespace}")

    # Merge all fracture regions
    merge = net.createNode("merge", "all_fractures")
    for j, node in enumerate(fracture_outputs):
        merge.setInput(j, node)

    return merge
```

### Memory-Efficient Filler Points

```python
# Python: restrict filler points to fracture lines only (not full volume)
import hou

def configure_filler_points(mpm_object_path, max_fill_distance=0.5):
    """
    For large buildings, filling the entire volume with filler particles is
    prohibitively expensive (billions of points). Restrict filler to fracture lines.
    max_fill_distance: maximum distance from a fracture line to place filler points.
    """
    mpm_obj = hou.node(mpm_object_path)

    # Set max filler distance — only fills within this distance of fracture geometry
    mpm_obj.parm("fillerdist").set(max_fill_distance)

    # Filler type: fracture-lines only (not volume fill)
    mpm_obj.parm("fillertype").set("fracture")

    print(f"[MPM building] filler restricted to {max_fill_distance} units from fracture lines")
```

---

## Cross-Workflow Utility Functions

```python
# Python: shared utility functions used across multiple MPM workflows
import hou

def freeze_deleted_particles_setup(geo_node_path):
    """
    Add a wrangle that freezes deleted particles at last known position.
    Used by: Train Wreck, Building Attack — any workflow needing stable point indices.
    """
    net = hou.node(geo_node_path).parent()
    freeze = net.createNode("attribwrangle", "freeze_deleted")
    freeze.setInput(0, hou.node(geo_node_path))
    freeze.parm("snippet").set("""
// Cache current position before freeze logic
v@last_P = (i@freeze_initialized == 0) ? v@P : v@last_P;
i@freeze_initialized = 1;

if (i@deleted) {
    v@P = v@last_P;
    v@v = {0, 0, 0};
    i@active = 0;
}
""")
    return freeze


def backward_solve_emission_frame(solver_path, stable_frame):
    """
    Configure MPM solver to backward-solve from the stable frame.
    Ensures all particles exist at stable_frame for correct retargeting.
    Used by: Building Attack staggered emission.
    """
    solver = hou.node(solver_path)
    solver.parm("startframe").set(stable_frame)
    solver.parm("reversesolve").set(True)
    print(f"[MPM] Backward-solve from frame {stable_frame}")


def apply_scale_up(geo_node_path, scale_factor=100.0):
    """
    Apply scale-up to source geometry before MPM solver.
    Used by: Paintball (100x), any sub-centimeter MPM sim.
    """
    net = hou.node(geo_node_path).parent()
    xform = net.createNode("xform", "scale_up")
    xform.setInput(0, hou.node(geo_node_path))
    xform.parm("scale").set(scale_factor)
    return xform


def configure_multi_res_collider(static_collider_path, friction=5.0, stickiness=2.0):
    """
    Set high friction and stickiness on the low-res static collider region.
    Hides resolution mismatch at the boundary between lo-res and hi-res passes.
    Used by: Creature Breach multi-resolution pipeline.
    """
    coll = hou.node(static_collider_path)
    coll.parm("friction").set(friction)
    coll.parm("stickiness").set(stickiness)
    print(f"[MPM multi-res] boundary collider: friction={friction}, stickiness={stickiness}")
```

---

## Common Mistakes / Common Issues

**Close Gaps threshold too aggressive:** Setting tolerance too high merges real tears, making metal appear to re-weld itself. Start at 0.01 and increase until only genuine gaps close.

**Scale-up gravity not compensated:** Forgetting to divide gravity by the scale factor makes objects appear to float or fall in slow motion even in the non-slowed footage. Always update timescale AND gravity together.

**Adaptivity left at default for final render:** Default adaptivity changes mesh topology frame-to-frame, causing UV and color attribute flicker on liquid surfaces. Set adaptivity=0 for any final render involving color or UV transfer.

**Jp threshold wrong for creature breach:** Too low a Jp threshold (e.g., 1.05) includes elastic-only regions as "fractured," making the high-res patch enormous. Too high (e.g., 2.0) misses early fracture zones. Start at 1.2 and calibrate per-shot.

**Point indices unstable without freeze:** Retargeting assumes stable point indices. Deleting MPM particles that die mid-sim shifts all subsequent indices. Always use the freeze-deleted-particles pattern on any shot using retargeting.

**"Assume Unchanging Material Properties" left enabled:** For staggered emission (building attack), this causes all late-emitted particles to silently adopt the material properties of the first emission batch. The symptom is projectiles that fail to fracture or behave like concrete instead of steel.

**Missing VDB cook before createNode on matlib:** Not specific to MPM, but common in post-sim material setups. Cook the materiallibrary before calling createNode on shader children; without cook the internal subnet doesn't exist and createNode returns None.

**Backward-solve start frame wrong:** If the backward-solve frame is after the last staggered emission, some particles don't exist yet at that frame. The stable frame must be at or after the last particle is emitted.

**Surface tension instability:** Strong surface tension with too few substeps causes tunneling at tension boundaries. Always pair increased surface tension with increased minsubsteps (start at 4) and set substeps=2 globally.

**Narrow-band erosion over-aggressively removes surface:** More than 4 erosion passes on the render cloud can eat into the visible surface layer. Check the resulting point count and visual coverage before committing to the erosion pass count.
