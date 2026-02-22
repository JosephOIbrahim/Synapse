# Wire and Strand Dynamics

## Triggers
wire, cable, rope, chain, strand, vellum hair, wire solver, catenary, coil,
power line, tendril, vine, pin constraint, width, curve dynamics

## Context
Wire simulation in Houdini: Vellum Hair (recommended) and DOP Wire Solver (legacy).
Covers setup, material presets, pinning, curve generation, rendering, wind forces.

## Code

```python
# Vellum Hair wire setup (recommended approach)
import hou

geo = hou.node("/obj/wires")
if not geo:
    geo = hou.node("/obj").createNode("geo", "wires")

# Create source curve (line between two points)
line = geo.createNode("line", "cable_curve")
line.parm("dist").set(5.0)
line.parm("points").set(50)  # 20-50 points per cable is enough
line.parm("diry").set(-0.3)  # Slight initial droop

# Resample for even spacing
resample = geo.createNode("resample", "even_spacing")
resample.setInput(0, line)
resample.parm("length").set(0.1)

# Vellum Hair configure
# TWO outputs: output 1 = geometry, output 2 = constraints
hair = geo.createNode("vellumhair", "wire_config")
hair.setInput(0, resample)
hair.parm("stretchstiffness").set(50000)  # Resistance to stretching
hair.parm("bendstiffness").set(1.0)       # Resistance to bending
hair.parm("density").set(0.5)             # Mass per length
hair.parm("width").set(0.02)              # Wire thickness for rendering

# Vellum Solver
# Input 1 = geometry (from hair output 1)
# Input 3 = constraints (from hair output 2)
solver = geo.createNode("vellumsolver", "wire_sim")
solver.setInput(0, hair, 0)   # Geometry from output 0
solver.setInput(2, hair, 1)   # Constraints from output 1
solver.parm("substeps").set(5)
solver.parm("groundplane").set(1)  # Enable ground

# Cache
cache = geo.createNode("filecache", "wire_cache")
cache.setInput(0, solver)
cache.parm("sopoutput").set("$HIP/cache/wire.$F4.bgeo.sc")

geo.layoutChildren()
print("Vellum wire setup: line -> resample -> vellumhair -> solver -> cache")
```

```python
# Wire material presets
import hou

WIRE_PRESETS = {
    "thin_cable":  {"stretchstiffness": 50000,  "bendstiffness": 1.0,   "density": 0.5, "width": 0.01},
    "heavy_rope":  {"stretchstiffness": 100000, "bendstiffness": 10.0,  "density": 2.0, "width": 0.03},
    "garden_hose": {"stretchstiffness": 80000,  "bendstiffness": 5.0,   "density": 1.0, "width": 0.02},
    "power_line":  {"stretchstiffness": 200000, "bendstiffness": 0.01,  "density": 3.0, "width": 0.015},
    "vine":        {"stretchstiffness": 5000,   "bendstiffness": 0.05,  "density": 0.3, "width": 0.008},
    "chain":       {"stretchstiffness": 100000, "bendstiffness": 0.0,   "density": 5.0, "width": 0.02},
    "fishing_line":{"stretchstiffness": 50000,  "bendstiffness": 0.001, "density": 0.01,"width": 0.002},
}


def apply_wire_preset(hair_node_path, preset_name):
    """Apply a wire material preset to a vellumhair node."""
    node = hou.node(hair_node_path)
    if not node:
        return

    preset = WIRE_PRESETS.get(preset_name)
    if not preset:
        print(f"Unknown preset: {preset_name}")
        print(f"Available: {list(WIRE_PRESETS.keys())}")
        return

    for parm, value in preset.items():
        p = node.parm(parm)
        if p:
            p.set(value)
    print(f"Applied '{preset_name}' preset")


apply_wire_preset("/obj/wires/wire_config", "heavy_rope")
```

```vex
// Pin endpoints of wire curves
// Run on Points BEFORE vellumhair configure node
// Sets i@stopped=1 to pin first and last point of each curve

int first = primpoint(0, @primnum, 0);
int last = primpoint(0, @primnum, nvertices(0, @primnum) - 1);

// Pin first and last point
if (@ptnum == first || @ptnum == last) {
    i@stopped = 1;  // Vellum reads this to pin points
}

// Alternative: pin only first point (dangling wire)
// if (@ptnum == first) i@stopped = 1;

// Alternative: pin by height (top edge of curtain)
// if (@P.y > ch("pin_height")) i@stopped = 1;
```

```python
# Attach wire to animated objects
import hou

def setup_wire_with_collider(geo_path, animated_geo_path):
    """Set up wire attached to animated geometry with collisions."""
    geo = hou.node(geo_path)
    if not geo:
        return

    # Import animated collision geometry
    obj_merge = geo.createNode("object_merge", "animated_obj")
    obj_merge.parm("objpath1").set(animated_geo_path)

    # Compute velocity for stable collisions
    trail = geo.createNode("trail", "compute_vel")
    trail.setInput(0, obj_merge)
    trail.parm("result").set(1)  # Compute velocity

    # Vellum collider
    collider = geo.createNode("vellumcollider", "collision")
    collider.setInput(0, trail)

    # Wire solver -- connect collider to input 2
    solver = geo.node("wire_sim")
    if solver:
        solver.setInput(1, collider)  # Collider on input 2 (index 1)

    geo.layoutChildren()
    print("Wire collision with animated geometry set up")

setup_wire_with_collider("/obj/wires", "/obj/animated_character")
```

```vex
// Generate catenary curve (hanging cable between two points)
// Run on a line SOP with many points (50+)
vector start = chv("start_point");   // e.g., set(-3, 5, 0)
vector end_pt = chv("end_point");    // e.g., set(3, 5, 0)
float sag = ch("sag");              // How much cable droops (e.g., 1.5)

float t = float(@ptnum) / float(@numpt - 1);
@P = lerp(start, end_pt, t);

// Catenary dip (parabolic approximation)
float mid_dip = 4.0 * sag * t * (1.0 - t);
@P.y -= mid_dip;
```

```vex
// Generate spiral/coil curve
// Run on a line SOP with many points
float t = float(@ptnum) / float(@numpt - 1);
float angle = t * ch("turns") * 360;    // Number of full rotations
float radius = ch("radius");             // Coil radius
float height = ch("height") * t;         // Total height

@P = set(cos(radians(angle)) * radius, height, sin(radians(angle)) * radius);
```

```vex
// Width variation: taper wire toward tips
// Run on Points
float t = float(vertexindex(0, @primnum, @ptnum)) / float(nvertices(0, @primnum) - 1);
f@width = lerp(ch("base_width"), ch("tip_width"), t);
// base_width=0.02, tip_width=0.005 for natural taper
```

```vex
// Wind force in solver wrangle (inside vellumsolver)
vector wind_dir = normalize(chv("wind_direction"));
float wind_speed = ch("wind_speed");
float turbulence = ch("turbulence");
float drag = ch("drag");

// Base wind
vector wind = wind_dir * wind_speed;

// Add turbulence via curl noise
wind += curlnoise(@P * 0.5 + @Time) * turbulence;

// Apply force
v@v += wind * @TimeInc * drag;
```

```python
# DOP Wire Solver (legacy -- use Vellum Hair instead for most cases)
import hou

hou.setSimulationEnabled(False)
try:
    geo = hou.node("/obj/wires_legacy")
    if not geo:
        geo = hou.node("/obj").createNode("geo", "wires_legacy")

    line = geo.createNode("line", "wire_curve")
    line.parm("dist").set(5.0)
    line.parm("points").set(30)

    # Wire capture (computes rest state)
    capture = geo.createNode("wirecapture", "wire_capture")
    capture.setInput(0, line)

    # DOP network
    dopnet = geo.createNode("dopnet", "wire_sim")

    wire_obj = dopnet.createNode("wireobject", "wire")
    wire_obj.parm("soppath").set(capture.path())
    wire_obj.parm("klinear").set(50000)     # Stretch stiffness
    wire_obj.parm("kangular").set(1.0)      # Bend stiffness
    wire_obj.parm("lineardensity").set(1.0) # Mass per length

    solver = dopnet.createNode("wiresolver", "solver")
    gravity = dopnet.createNode("gravity", "gravity")

    merge = dopnet.createNode("merge", "merge")
    merge.setInput(0, wire_obj)
    merge.setInput(1, solver)
    merge.setInput(2, gravity)
    merge.setDisplayFlag(True)

    dopnet.layoutChildren()
    geo.layoutChildren()
    print("Legacy wire solver setup (prefer Vellum Hair for new work)")

finally:
    hou.setSimulationEnabled(True)
```

```python
# Render material reference for wire types
WIRE_MATERIALS = {
    "cable":  {"base_color": (0.05, 0.05, 0.05), "roughness": 0.7, "metalness": 0.0},
    "rope":   {"base_color": (0.4, 0.3, 0.2),    "roughness": 0.9, "metalness": 0.0},
    "chain":  {"base_color": (0.6, 0.6, 0.6),    "roughness": 0.3, "metalness": 1.0},
    "vine":   {"base_color": (0.1, 0.3, 0.05),   "roughness": 0.6, "metalness": 0.0},
    "copper": {"base_color": (0.7, 0.4, 0.2),    "roughness": 0.4, "metalness": 1.0},
}

# Karma renders curves natively as tube primitives
# @width attribute controls render-time thickness
# Cross-section: round by default
# For thick rope: increase @width, add displacement for braiding texture
for name, mat in WIRE_MATERIALS.items():
    print(f"  {name}: color={mat['base_color']}, rough={mat['roughness']}, metal={mat['metalness']}")
```

## Common Mistakes
- Missing `@width` attribute -- wire is invisible in render without it; set `f@width = 0.01`
- Wire stretches too much -- increase `stretchstiffness` to 100000+
- Wire too stiff -- lower `bendstiffness` to 0.01-0.1 for natural draping
- Wire passes through collider -- add `vellumcollider`, increase substeps to 5+
- Endpoints move when they should be fixed -- set `i@stopped=1` on pinned points before configure
- Wire vibrates/jitters -- increase damping or substeps (5-10 for final)
- Using DOP Wire Solver for new work -- Vellum Hair is faster to iterate and has better collisions
