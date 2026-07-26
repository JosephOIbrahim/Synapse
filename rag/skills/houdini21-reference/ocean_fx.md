# Ocean FX

## Triggers
ocean, ocean fx, ocean spectrum, oceanevaluate, oceanflat, ocean flat, whitewater, flip ocean,
ocean flip, spectral ocean, ocean waves, wave simulation, ocean shader, ocean material,
ocean surface, water surface, water simulation, ocean cache, ocean solaris, ocean rendering,
sea state, ocean spectrum stack, multiple spectrums, ocean cusp, foam shader, water material

## Context
Houdini's ocean system combines spectral ocean generation with FLIP simulation for close-up
interaction. The spectral ocean is infinite and fast; FLIP handles splashes and object interaction.
Use `oceanspectrum -> oceanevaluate` for background ocean; add `oceanflat -> flipsolver` for hero
shots with objects entering the water.

---

## Ocean Spectrum Setup

```python
import hou

# ---- Build a complete ocean spectrum chain in /obj/geo1 ----
geo = hou.node("/obj").createNode("geo", "ocean_setup")

# 1. Ocean Spectrum -- generates wave frequency data (not geometry yet)
spectrum = geo.createNode("oceanspectrum", "spectrum_primary")

# Resolution: grid exponent, actual grid = 2^n pixels
# 10 = 1024x1024 (production), 8 = 256x256 (preview)
spectrum.parm("resolution").set(10)

# Physical size in world units (meters). Match to your camera frustum.
spectrum.parm("gridsize").set(100)

# Animate time -- use $T (current time in seconds)
spectrum.parm("time").setExpression("$T")

# Water depth in meters. Affects wave speed dispersion.
spectrum.parm("depth").set(100)

# Wind speed in m/s -- primary driver of wave height
spectrum.parm("windspeed").set(12)

# Wind direction in degrees (0 = +Z axis)
spectrum.parm("winddir").set(0)

# Directional spread: 0.0 = all waves in wind dir, 1.0 = omnidirectional
spectrum.parm("spread").set(0.5)

# Chop: wave peakiness. 0.0 = round sinusoids, 1.0 = sharp crests
spectrum.parm("chop").set(0.5)

# Random seed -- change per shot to avoid repeated tiling patterns
spectrum.parm("seed").set(42)

print(f"Spectrum node: {spectrum.path()}")
```

---

## Sea State Presets as Python Dictionaries

```python
import hou

# Sea state presets -- apply with apply_sea_state() below
SEA_STATES = {
    "calm_lake": {
        "windspeed": 3.0,
        "depth":     20.0,
        "chop":      0.0,
        "spread":    0.9,
        "gridsize":  50.0,
        # look: gentle ripples, near-mirror reflections
    },
    "light_chop": {
        "windspeed": 7.0,
        "depth":     50.0,
        "chop":      0.3,
        "spread":    0.7,
        "gridsize":  100.0,
        # look: sailboat conditions, slight foam at crests
    },
    "moderate_sea": {
        "windspeed": 12.0,
        "depth":     100.0,
        "chop":      0.5,
        "spread":    0.5,
        "gridsize":  150.0,
        # look: standard ocean, rolling swells, visible chop
    },
    "rough_sea": {
        "windspeed": 25.0,
        "depth":     200.0,
        "chop":      0.7,
        "spread":    0.4,
        "gridsize":  300.0,
        # look: storm waves, frequent whitecaps
    },
    "heavy_storm": {
        "windspeed": 40.0,
        "depth":     500.0,
        "chop":      0.9,
        "spread":    0.3,
        "gridsize":  500.0,
        # look: extreme waves, breaking crests everywhere
    },
}


def apply_sea_state(spectrum_node: hou.Node, preset_name: str) -> None:
    """Apply a sea state preset to an oceanspectrum node."""
    if preset_name not in SEA_STATES:
        raise ValueError(f"Unknown preset '{preset_name}'. Valid: {list(SEA_STATES)}")
    preset = SEA_STATES[preset_name]
    for parm_name, value in preset.items():
        parm = spectrum_node.parm(parm_name)
        if parm is not None:
            parm.set(value)
    print(f"Applied '{preset_name}' to {spectrum_node.path()}")


# Usage:
# apply_sea_state(hou.node("/obj/ocean_setup/spectrum_primary"), "moderate_sea")
```

---

## Multiple Spectrums Stacking

```python
import hou

def build_layered_spectrum(parent: hou.Node) -> list[hou.Node]:
    """
    Stack three oceanspectrum nodes for realistic multi-scale waves.
    Layer 1: primary swell   -- large, slow, directional
    Layer 2: wind chop       -- medium local waves
    Layer 3: surface ripples -- small surface detail
    Returns list of [spectrum1, spectrum2, spectrum3] nodes.
    """

    # Layer 1: Primary ocean swell
    # Large scale, slow wind, narrow directional spread
    swell = parent.createNode("oceanspectrum", "spectrum_swell")
    swell.parm("resolution").set(10)       # 1024x1024 for swell detail
    swell.parm("gridsize").set(500)        # 500m grid -- covers wide camera framing
    swell.parm("windspeed").set(15)        # strong wind for large swells
    swell.parm("winddir").set(0)           # primary wind direction
    swell.parm("spread").set(0.3)          # narrow spread -- focused swell direction
    swell.parm("chop").set(0.4)
    swell.parm("depth").set(200)
    swell.parm("seed").set(0)
    swell.parm("time").setExpression("$T")

    # Layer 2: Local wind chop
    # Medium scale, higher wind, broad spread
    chop = parent.createNode("oceanspectrum", "spectrum_chop")
    chop.parm("resolution").set(9)         # 512x512 -- chop doesn't need full res
    chop.parm("gridsize").set(100)         # 100m grid
    chop.parm("windspeed").set(8)
    chop.parm("winddir").set(25)           # slight angle offset from swell
    chop.parm("spread").set(0.7)           # broader spread for local chop
    chop.parm("chop").set(0.6)
    chop.parm("depth").set(100)
    chop.parm("seed").set(17)              # different seed -- avoids repetition
    chop.parm("time").setExpression("$T")

    # Layer 3: Surface ripples
    # Small scale, light wind, nearly omnidirectional
    ripples = parent.createNode("oceanspectrum", "spectrum_ripples")
    ripples.parm("resolution").set(8)      # 256x256 -- ripples are fine detail
    ripples.parm("gridsize").set(20)       # 20m grid -- tight tiling for small detail
    ripples.parm("windspeed").set(3)
    ripples.parm("winddir").set(-15)       # slight counter-angle for visual variety
    ripples.parm("spread").set(0.9)        # nearly omnidirectional ripples
    ripples.parm("chop").set(0.2)          # keep ripples round (low chop)
    ripples.parm("depth").set(50)
    ripples.parm("seed").set(99)
    ripples.parm("time").setExpression("$T")

    return [swell, chop, ripples]


# Build oceanevaluate that reads all three spectrums
def build_evaluate(parent: hou.Node, spectrums: list[hou.Node]) -> hou.Node:
    """Wire multiple spectrums into a single oceanevaluate node."""
    evaluate = parent.createNode("oceanevaluate", "ocean_evaluate")

    # oceanevaluate takes the grid on input 0; spectrums are referenced by name
    # Wire first spectrum into input 0 (the evaluate reads the rest by name)
    evaluate.setInput(0, spectrums[0])

    # Point the evaluate at all spectrum nodes via their node paths
    # oceanevaluate in H21 uses "spectrumfile" parameter per spectrum slot
    for i, spec in enumerate(spectrums):
        parm_name = f"spectrumpath{i + 1}" if i > 0 else "spectrumpath1"
        parm = evaluate.parm(parm_name)
        if parm is not None:
            parm.set(spec.path())

    # Full resolution output (downsample=0), displacement mode
    evaluate.parm("downsample").set(0)     # 0=full, 1=half-res, 2=quarter-res
    evaluate.parm("outputtype").set(0)     # 0=Displacement surface

    return evaluate


# Usage:
# geo = hou.node("/obj/ocean_setup")
# specs = build_layered_spectrum(geo)
# eval_node = build_evaluate(geo, specs)
```

---

## Ocean Evaluate Attributes

```python
import hou

# oceanevaluate produces these point attributes -- read them downstream
# This snippet reads attribute ranges from a cooked evaluate node for diagnostics

def inspect_ocean_attributes(evaluate_node: hou.Node) -> dict:
    """
    Read ocean surface attributes after cook.
    Returns dict of {attr_name: (min, max)} ranges for diagnostics.
    """
    geo = evaluate_node.geometry()
    attrs_to_check = ["P", "v", "cusp", "eigenvalues"]
    results = {}

    for attr_name in attrs_to_check:
        attr = geo.findPointAttrib(attr_name)
        if attr is None:
            results[attr_name] = None
            continue

        if attr.dataType() == hou.attribData.Float:
            if attr.size() == 1:
                vals = [p.attribValue(attr_name) for p in geo.points()]
                results[attr_name] = (min(vals), max(vals))
            else:
                # Vector attribute -- report magnitude range
                import math
                mags = [
                    math.sqrt(sum(c * c for c in p.attribValue(attr_name)))
                    for p in geo.points()
                ]
                results[attr_name] = (min(mags), max(mags))

    return results

# Attribute descriptions (reference):
# @P            -- Displaced world position (the actual ocean surface shape)
# @v            -- Surface velocity vector (use for foam/spray emission rates)
# @cusp         -- Wave crest sharpness; cusp > 0.5 triggers whitewater emission
# @eigenvalues  -- Wave convergence metric; high values = foam accumulation zones
```

---

## Ocean Flat for FLIP Blending

```python
import hou

def build_flip_ocean_chain(parent: hou.Node) -> dict[str, hou.Node]:
    """
    Build the full spectral->FLIP blending chain for hero shots.

    Chain:
      oceanspectrum -> oceanevaluate -> oceanflat -> (FLIP tank source)
      flipsolver -> particlefluidsurface -> (render mesh)

    Returns dict of created nodes.
    """
    nodes = {}

    # 1. Spectrum (use moderate_sea preset)
    spectrum = parent.createNode("oceanspectrum", "spectrum_hero")
    spectrum.parm("windspeed").set(12)
    spectrum.parm("gridsize").set(150)
    spectrum.parm("chop").set(0.5)
    spectrum.parm("depth").set(100)
    spectrum.parm("time").setExpression("$T")
    spectrum.parm("seed").set(7)
    nodes["spectrum"] = spectrum

    # 2. Evaluate
    evaluate = parent.createNode("oceanevaluate", "evaluate_hero")
    evaluate.setInput(0, spectrum)
    evaluate.parm("downsample").set(0)
    nodes["evaluate"] = evaluate

    # 3. Ocean Flat -- blends spectral ocean to a flat FLIP tank at edges
    ocean_flat = parent.createNode("oceanflat", "ocean_flat")
    ocean_flat.setInput(0, evaluate)

    # flatradius: distance from origin where the ocean transitions to flat
    # Set this slightly larger than your FLIP tank radius
    ocean_flat.parm("flatradius").set(30)   # 30m flat zone in center

    # blendwidth: how wide the blend zone is between flat and spectral
    # Rule: at least 2x the max wave amplitude (max amplitude ~ windspeed * 0.1)
    ocean_flat.parm("blendwidth").set(20)   # 20m blend zone

    nodes["ocean_flat"] = ocean_flat

    # 4. FLIP Source -- use the flattened ocean as the initial FLIP fill
    flip_source = parent.createNode("flipsource", "flip_source")
    flip_source.setInput(0, ocean_flat)
    # Use single-frame fill from the flattened ocean
    flip_source.parm("sourcetype").set(0)  # 0 = Volume fill
    nodes["flip_source"] = flip_source

    # 5. FLIP Solver
    flip_solver = parent.createNode("flipsolver", "flip_solver")
    # Wire flip_source into flip_solver input 0 (particles)
    flip_solver.setInput(0, flip_source)
    # Narrow band: only simulate particles near the surface (much faster)
    flip_solver.parm("narrowband").set(1)
    flip_solver.parm("narrowbandwidth").set(4)  # 4 voxels deep
    nodes["flip_solver"] = flip_solver

    # 6. Particle Fluid Surface -- mesh the FLIP particles
    pfs = parent.createNode("particlefluidsurface", "flip_mesh")
    pfs.setInput(0, flip_solver)
    pfs.parm("particlesep").set(0.05)      # voxel size relative to particle radius
    pfs.parm("smoothingiterations").set(5)
    nodes["flip_mesh"] = pfs

    # Layout the network for readability
    parent.layoutChildren()

    return nodes
```

---

## Whitewater Setup

```python
import hou

def build_whitewater(parent: hou.Node,
                     source_node: hou.Node,
                     use_flip: bool = False) -> dict[str, hou.Node]:
    """
    Build whitewater chain from either oceanevaluate (spectral-only)
    or flipsolver output (FLIP-driven).

    Emission thresholds:
      @cusp > 0.5        -- breaking wave crests
      @eigenvalues high  -- wave convergence / foam accumulation
      @v magnitude high  -- fast-moving surface (impact zones)
    """
    nodes = {}

    # Whitewater Source -- detects emission regions
    ww_source = parent.createNode("whitewatersource", "whitewater_source")
    ww_source.setInput(0, source_node)

    # Emission source: cusp attribute from oceanevaluate or FLIP surface
    ww_source.parm("usecusp").set(1)
    ww_source.parm("cuspthreshold").set(0.5)       # emit where cusp > 0.5
    ww_source.parm("useeigenvalue").set(1)
    ww_source.parm("eigenvaluethreshold").set(0.3)  # foam accumulation zones

    if use_flip:
        # Also emit from high-velocity FLIP surface (impact spray)
        ww_source.parm("usespeed").set(1)
        ww_source.parm("speedthreshold").set(2.5)   # m/s -- impacts and splashes
        ww_source.parm("useacceleration").set(1)
        ww_source.parm("accelerationthreshold").set(5.0)

    nodes["ww_source"] = ww_source

    # Whitewater Solver -- simulates foam, spray, and bubbles
    ww_solver = parent.createNode("whitewatersolver", "whitewater_solver")
    ww_solver.setInput(0, ww_source)    # source particles
    ww_solver.setInput(1, source_node)  # collision/constraint surface

    # Lifetime: foam lives longer than spray
    ww_solver.parm("foamlifetime").set(8.0)     # seconds
    ww_solver.parm("spraylifetime").set(3.0)
    ww_solver.parm("bubblelifetime").set(5.0)

    # Buoyancy -- bubbles and foam float up to surface
    ww_solver.parm("buoyancy").set(3.0)

    nodes["ww_solver"] = ww_solver

    return nodes

# Rendering notes (as comments -- see shader section for full MaterialX setup):
# Foam   -- render as flat surface particles, opacity from @age/@life ratio
# Spray  -- render as point cloud or tiny sphere instances
# Bubbles-- render as sub-surface particles with refraction
# All three layers composited in Karma as separate render geometry
```

---

## Ocean Shader Setup (MaterialX / Karma)

```python
import hou

def build_ocean_material(mat_context: hou.Node) -> hou.Node:
    """
    Build a Karma/MaterialX ocean water material.
    mat_context should be a materiallibrary or matnet node.

    Material properties:
      IOR         1.33  (water)
      Base color  deep blue-green absorption
      Roughness   0.01-0.05 (very smooth)
      Transmission enabled for refractive shallow water
      Displacement from @P offset for render-time wave detail
    """
    # Create a MaterialX Standard Surface subnet
    mat = mat_context.createNode("subnet", "ocean_water")
    mat_context.cook(force=True)  # cook matlib before adding shader children

    # Standard Surface shader node
    surface = mat.createNode("mtlxstandard_surface", "water_surface")

    # Base color -- very dark blue-green (deep water absorption)
    surface.parmTuple("base_color").set((0.005, 0.020, 0.035))

    # IOR: water = 1.33
    surface.parm("specular_IOR").set(1.33)

    # Roughness: 0.0 = mirror, 0.02 = slight wind ripple disturbance
    surface.parm("specular_roughness").set(0.02)

    # Transmission -- essential for transparent/refractive water
    surface.parm("transmission").set(1.0)
    surface.parm("transmission_color").set((0.1, 0.45, 0.55))   # teal absorption
    surface.parm("transmission_depth").set(5.0)                  # absorption depth m

    # No subsurface needed for open ocean (SSS is for skin/wax)
    surface.parm("subsurface").set(0.0)

    # Metalness 0 -- water is dielectric
    surface.parm("metalness").set(0.0)

    print(f"Ocean material: {mat.path()}")
    return mat


def build_foam_material(mat_context: hou.Node) -> hou.Node:
    """
    Build a simple foam/whitewater material.
    White diffuse with opacity driven by @life attribute.
    """
    mat_context.cook(force=True)
    mat = mat_context.createNode("subnet", "ocean_foam")

    surface = mat.createNode("mtlxstandard_surface", "foam_surface")

    # White diffuse -- foam scatters light broadly
    surface.parmTuple("base_color").set((0.92, 0.93, 0.94))  # slightly off-white
    surface.parm("base").set(1.0)

    # Very rough (foam is not reflective)
    surface.parm("specular_roughness").set(0.95)
    surface.parm("specular").set(0.05)

    # No transmission -- foam is opaque
    surface.parm("transmission").set(0.0)

    # Opacity mixing: connect @life point attribute via texture node in full setup
    # In wrangle upstream: f@Alpha = 1.0 - (@age / @life);  clamp(f@Alpha, 0, 1)
    # Then use mtlxgeompropvalue node reading "Alpha" -> mtlxmix opacity

    print(f"Foam material: {mat.path()}")
    return mat
```

---

## VEX: Whitewater Emission Mask

```vex
// whitewatersource_mask.vex
// Run in a Point Wrangle on oceanevaluate output.
// Outputs @mask attribute used by whitewatersource for emission weighting.

// Read ocean surface attributes
float cusp_val   = f@cusp;           // wave crest sharpness [0..1+]
vector eig       = v@eigenvalues;    // wave convergence vector
float vel_mag    = length(v@v);      // surface velocity magnitude

// Cusp contribution: breaking wave crests
// Threshold at 0.5 -- below this is normal wave, above is about to break
float cusp_mask = clamp((cusp_val - 0.5) / 0.5, 0.0, 1.0);

// Eigenvalue contribution: wave energy convergence (foam traps)
float eig_mag  = length(eig);
float eig_mask = clamp((eig_mag - 0.3) / 0.7, 0.0, 1.0);

// Velocity contribution: fast-moving surface (impact and drainage zones)
float vel_mask = clamp((vel_mag - 2.0) / 3.0, 0.0, 1.0);

// Combine all three with tunable weights
float w_cusp = 0.6;   // cusp drives most whitecap emission
float w_eig  = 0.3;   // eigenvalue for foam accumulation
float w_vel  = 0.1;   // velocity for impact zones

f@mask = clamp(
    cusp_mask * w_cusp +
    eig_mask  * w_eig  +
    vel_mask  * w_vel,
    0.0, 1.0
);

// Also write age-based opacity for foam rendering (if this is a foam particle)
// f@Alpha = 1.0 - (@age / @life);
```

---

## VEX: Foam Age Opacity

```vex
// foam_opacity.vex
// Run in a Point Wrangle on whitewatersolver output (foam particles).
// Writes @Alpha for opacity-mapped rendering in Karma.

// Normalized age: 0.0 at birth, 1.0 at death
float norm_age = @age / max(@life, 0.001);

// Fade in fast (0->0.2 of life), hold, fade out slowly (0.7->1.0 of life)
float fade_in  = smoothstep(0.0,  0.15, norm_age);
float fade_out = 1.0 - smoothstep(0.70, 1.0, norm_age);

f@Alpha = fade_in * fade_out;

// Density-based opacity: denser foam clusters are more opaque
// If whitewatersolver writes @density attribute:
float density_boost = clamp(f@density * 2.0, 0.0, 1.0);
f@Alpha = clamp(f@Alpha * (0.5 + 0.5 * density_boost), 0.0, 1.0);

// Scale point size for spray (tiny) vs foam (larger flat discs)
// Whitewatersolver writes @type: 0=foam, 1=spray, 2=bubble
if (i@type == 1) {
    // Spray: small, fast fade
    f@pscale = 0.02;
    f@Alpha *= (1.0 - norm_age);   // spray fades linearly
} else if (i@type == 0) {
    // Foam: larger flat disc on surface
    f@pscale = 0.15;
} else {
    // Bubble: medium, interior of wave
    f@pscale = 0.05;
}
```

---

## Caching Strategy

```python
import hou

def setup_ocean_caches(parent: hou.Node, cache_dir: str,
                       nodes: dict[str, hou.Node]) -> dict[str, hou.Node]:
    """
    Wire filecache nodes for a full ocean pipeline.
    All caches use .bgeo.sc (Blosc-compressed binary geo -- fastest I/O).

    Cache order matters for playback speed:
      1. ocean surface (small, fast to read)
      2. FLIP mesh     (medium)
      3. whitewater    (large -- cache spray/foam/bubbles separately)
    """
    caches = {}

    def make_cache(name: str, input_node: hou.Node, suffix: str) -> hou.Node:
        fc = parent.createNode("filecache", name)
        fc.setInput(0, input_node)
        # Use $F4 for 4-digit zero-padded frame numbers
        fc.parm("file").set(f"{cache_dir}/{suffix}/$F4.bgeo.sc")
        fc.parm("loadfromdisk").set(0)  # 0=cache and load, 1=load only
        return fc

    # 1. Ocean surface displaced mesh (per-frame, reads fast from SSD)
    if "evaluate" in nodes:
        caches["ocean_surface"] = make_cache(
            "cache_ocean_surface", nodes["evaluate"], "ocean_surface"
        )

    # 2. FLIP particle cache (cache raw particles, mesh separately)
    if "flip_solver" in nodes:
        caches["flip_particles"] = make_cache(
            "cache_flip_particles", nodes["flip_solver"], "flip_particles"
        )

    # 3. FLIP mesh cache
    if "flip_mesh" in nodes:
        caches["flip_mesh"] = make_cache(
            "cache_flip_mesh", nodes["flip_mesh"], "flip_mesh"
        )

    # 4. Whitewater particles (separate caches for foam/spray/bubble types)
    if "ww_solver" in nodes:
        caches["whitewater"] = make_cache(
            "cache_whitewater", nodes["ww_solver"], "whitewater"
        )

    parent.layoutChildren()
    return caches


# Simulate all caches for frame range:
def sim_ocean_range(cache_nodes: dict[str, hou.Node],
                    start: int, end: int) -> None:
    """Set all filecache nodes to write mode and sim the range."""
    for name, fc in cache_nodes.items():
        fc.parm("loadfromdisk").set(0)  # write mode

    # Simulate by evaluating each frame in sequence
    for frame in range(start, end + 1):
        hou.setFrame(frame)
        for name, fc in cache_nodes.items():
            fc.cook(force=True)
        print(f"Cached frame {frame}/{end}")

    # Switch all caches to read mode after sim
    for name, fc in cache_nodes.items():
        fc.parm("loadfromdisk").set(1)
    print("All ocean caches complete -- switched to read mode.")
```

---

## Solaris Import

```python
import hou

def import_ocean_to_solaris(stage: hou.Node,
                             sop_nodes: dict[str, hou.Node],
                             ocean_mat_path: str,
                             foam_mat_path: str) -> dict[str, hou.Node]:
    """
    Import ocean SOP geometry into the Solaris (LOPs) stage.
    Assigns water and foam materials.

    stage      -- /stage or any LOP network node
    sop_nodes  -- dict with keys: 'ocean_surface', 'flip_mesh', 'whitewater'
    ocean_mat_path -- USD path to water material e.g. '/materials/ocean_water'
    foam_mat_path  -- USD path to foam material e.g. '/materials/ocean_foam'
    """
    lop_nodes = {}

    # 1. Ocean surface displaced mesh
    if "ocean_surface" in sop_nodes:
        ocean_import = stage.createNode("sopimport", "import_ocean_surface")
        ocean_import.parm("soppath").set(sop_nodes["ocean_surface"].path())
        ocean_import.parm("primpath").set("/world/ocean/surface")
        ocean_import.parm("import_type").set("Auto")  # import as mesh
        lop_nodes["ocean_surface"] = ocean_import

        # Assign water material
        assign_ocean = stage.createNode("assignmaterial", "assign_water_mat")
        assign_ocean.setInput(0, ocean_import)
        assign_ocean.parm("primpattern1").set("/world/ocean/surface")
        assign_ocean.parm("matspecpath1").set(ocean_mat_path)
        lop_nodes["assign_ocean"] = assign_ocean

    # 2. FLIP mesh (hero water surface near interaction)
    if "flip_mesh" in sop_nodes:
        flip_import = stage.createNode("sopimport", "import_flip_mesh")
        flip_import.parm("soppath").set(sop_nodes["flip_mesh"].path())
        flip_import.parm("primpath").set("/world/ocean/flip_mesh")
        lop_nodes["flip_mesh"] = flip_import

        assign_flip = stage.createNode("assignmaterial", "assign_flip_mat")
        assign_flip.setInput(0, flip_import)
        assign_flip.parm("primpattern1").set("/world/ocean/flip_mesh")
        assign_flip.parm("matspecpath1").set(ocean_mat_path)
        lop_nodes["assign_flip"] = assign_flip

    # 3. Whitewater (point cloud -- render as Karma point instancer)
    if "whitewater" in sop_nodes:
        ww_import = stage.createNode("sopimport", "import_whitewater")
        ww_import.parm("soppath").set(sop_nodes["whitewater"].path())
        ww_import.parm("primpath").set("/world/ocean/whitewater")
        lop_nodes["whitewater"] = ww_import

        assign_foam = stage.createNode("assignmaterial", "assign_foam_mat")
        assign_foam.setInput(0, ww_import)
        assign_foam.parm("primpattern1").set("/world/ocean/whitewater")
        assign_foam.parm("matspecpath1").set(foam_mat_path)
        lop_nodes["assign_foam"] = assign_foam

    # 4. Merge all ocean geometry into one stream
    merge = stage.createNode("merge", "ocean_merge")
    inputs = [n for key, n in lop_nodes.items() if key.startswith("assign_")]
    for i, n in enumerate(inputs):
        merge.setInput(i, n)
    lop_nodes["merge"] = merge

    stage.layoutChildren()
    return lop_nodes
```

---

## Common Ocean Issues

**Ocean looks flat**: Wind speed too low. Increase `windspeed` to 10-15 and add chop (0.4-0.6). A single spectrum at low speed produces very gentle ripples -- increase speed first, then layer chop spectrum on top.

**Waves too uniform / tiling visible**: Using a single spectrum with small `gridsize`. Stack 2-3 spectrums at different grid sizes (500m / 100m / 20m). The tiling period of each spectrum differs, breaking repetition visually.

**FLIP surface doesn't match spectral ocean**: Missing `oceanflat` node between `oceanevaluate` and FLIP source. Without it the FLIP initial fill is a flat plane disconnected from the spectral shape. Add `oceanflat`, set `flatradius` larger than your tank and `blendwidth` at least 2x the max wave amplitude.

**Seam visible at FLIP/ocean edge**: `blendwidth` too narrow. Increase `blendwidth` and ensure the FLIP tank is large enough that splashes don't travel to the blend zone. As a rule, `flatradius` should be at least 1.5x the FLIP tank radius.

**No foam or whitewater appearing**: Cusp threshold too high for current sea state. Check `@cusp` max value using the `inspect_ocean_attributes()` helper above. If `@cusp` max is 0.3 and threshold is 0.5, no particles emit. Lower `cuspthreshold` to 70% of the actual cusp max.

**Render is too slow**: Water transmission with many bounces is expensive. Lower specular bounces to 4. Use caustics only for hero/close-up shots. For background ocean, disable transmission entirely and fake depth with absorption color in the base color.

**Whitewater particles disappear too fast**: `@life` too short. Increase `foamlifetime` in the whitewatersolver (8-12 seconds for ocean foam). Spray can stay at 2-4 seconds.
