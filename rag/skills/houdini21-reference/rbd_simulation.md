# RBD (Rigid Body) Simulation

## Triggers
rbd, rigid body, fracture, destruction, constraint, glue, bullet solver, collision,
rbdmaterialfracture, assemble, packed primitive, debris, impact data

## Context
RBD simulation pipeline in Houdini: fracture geometry, set up constraints, simulate
with Bullet solver, extract impact data, and import to Solaris. Includes the simulation
guard pattern for safe DOP operations.

## Code

```python
# Full RBD pipeline: fracture -> assemble -> simulate
import hou

# Simulation guard -- disable live sim during setup
hou.setSimulationEnabled(False)
try:
    geo = hou.node("/obj/destruction")
    if not geo:
        geo = hou.node("/obj").createNode("geo", "destruction")

    # Step 1: Source geometry (box to destroy)
    box = geo.createNode("box", "source_geo")
    box.parm("sizex").set(4)
    box.parm("sizey").set(6)
    box.parm("sizez").set(2)
    box.parm("ty").set(3)  # Lift above ground

    # Step 2: Fracture with material-aware cuts
    fracture = geo.createNode("rbdmaterialfracture", "fracture")
    fracture.setInput(0, box)
    fracture.parm("fracturepoints").set(30)    # Number of pieces
    fracture.parm("materialtype").set(0)       # 0=Concrete, 1=Glass, 2=Wood
    fracture.parm("noise_amp").set(0.2)        # Surface noise on cuts
    fracture.parm("intdetail").set(1)          # Interior detail

    # Step 3: Pack pieces for efficient simulation
    assemble = geo.createNode("assemble", "pack_pieces")
    assemble.setInput(0, fracture)
    # Creates name attribute per piece, centers pivot at center of mass

    # Step 4: Create DOP network for simulation
    dopnet = geo.createNode("dopnet", "sim")

    # Step 5: RBD objects inside DOP
    rbdpacked = dopnet.createNode("rbdpackedobject", "pieces")
    rbdpacked.parm("soppath").set(assemble.path())

    # Step 6: Bullet solver
    solver = dopnet.createNode("bulletrbdsolver", "solver")
    solver.parm("substeps").set(2)  # 2-4 for fast impacts

    # Step 7: Ground plane
    ground = dopnet.createNode("groundplane", "ground")
    ground.parm("position").set(0)
    ground.parm("friction").set(0.5)
    ground.parm("bounce").set(0.3)

    # Step 8: Gravity
    gravity = dopnet.createNode("gravity", "gravity")

    # Wire DOP network: objects + solver + forces
    merge = dopnet.createNode("merge", "sim_merge")
    merge.setInput(0, rbdpacked)
    merge.setInput(1, solver)
    merge.setInput(2, ground)
    merge.setInput(3, gravity)
    merge.setDisplayFlag(True)

    dopnet.layoutChildren()
    geo.layoutChildren()
    print(f"RBD pipeline created at {geo.path()}")

finally:
    hou.setSimulationEnabled(True)
```

```python
# Constraint setup for controlled destruction
import hou

hou.setSimulationEnabled(False)
try:
    geo = hou.node("/obj/destruction")
    fracture = geo.node("fracture")
    assemble = geo.node("pack_pieces")

    if fracture and assemble:
        # Auto-generate constraints by proximity
        constraints = geo.createNode("rbdconstraintsfromrules", "constraints")
        constraints.setInput(0, assemble)
        constraints.parm("searchradius").set(0.5)     # Max distance between pieces
        constraints.parm("maxconstraints").set(6)      # Max connections per piece

        # Set constraint properties
        props = geo.createNode("rbdconstraintproperties", "glue_props")
        props.setInput(0, constraints)
        props.parm("constraint_type").set(0)           # 0=Glue
        props.parm("strength").set(500)                # Breaking force threshold

        geo.layoutChildren()
        print("Constraints created")

finally:
    hou.setSimulationEnabled(True)
```

```vex
// Progressive destruction: weaken pieces based on height
// Run on constraint geometry (Points mode)
float height = point(0, "P", @ptnum).y;

// Pieces higher up break first (lower strength at top)
f@strength = fit(height, 0, 10, 1000, 50);

// Alternatively: weaken pieces near an impact point
vector impact_pos = chv("impact_center");
float dist = distance(v@P, impact_pos);
f@strength = fit(dist, 0, ch("radius"), 0, 1000);  // weak near impact
```

```vex
// Impact data extraction (run on simulated RBD output)
// Read collision information from Bullet solver

f@impact_force = f@impulse;  // Magnitude of collision force
i@hit_object = i@hittable;   // ID of what was hit

// Use impact data to trigger secondary effects
if (f@impact_force > ch("dust_threshold")) {
    i@emit_dust = 1;         // Flag for dust emission
    f@dust_amount = f@impact_force / 1000.0;
}

// Color pieces by impact force for visualization
float normalized = clamp(f@impact_force / 500.0, 0, 1);
v@Cd = set(normalized, 1.0 - normalized, 0);  // Green->Red
```

```python
# Collision source setup for animated colliders
import hou

hou.setSimulationEnabled(False)
try:
    geo = hou.node("/obj/destruction")

    # Create collision source (VDB for faster, more stable collisions)
    collider_geo = hou.node("/obj").createNode("geo", "collider")

    # Animated sphere as wrecking ball
    sphere = collider_geo.createNode("sphere", "ball")
    sphere.parm("radx").set(1)

    # Animate position
    sphere.parm("tx").setKeyframe(hou.Keyframe(1, -5))
    sphere.parm("tx").setKeyframe(hou.Keyframe(24, 0))

    # Convert to VDB collision volume
    vdb = collider_geo.createNode("vdbfrompolygons", "collision_vdb")
    vdb.setInput(0, sphere)
    vdb.parm("voxelsize").set(0.05)
    vdb.setDisplayFlag(True)
    vdb.setRenderFlag(True)

    collider_geo.layoutChildren()
    print("Collision source created")

finally:
    hou.setSimulationEnabled(True)
```

```python
# Debris and secondary effects setup
import hou

hou.setSimulationEnabled(False)
try:
    geo = hou.node("/obj/destruction")

    # Scatter particles on fracture surfaces at impact time
    debris_geo = hou.node("/obj").createNode("geo", "debris")

    # Read RBD simulation output
    obj_merge = debris_geo.createNode("object_merge", "rbd_output")
    obj_merge.parm("objpath1").set("/obj/destruction/sim")

    # Scatter small particles on surfaces
    scatter = debris_geo.createNode("scatter", "debris_pts")
    scatter.setInput(0, obj_merge)
    scatter.parm("npts").set(500)

    # Inherit velocity from RBD pieces
    attrib_transfer = debris_geo.createNode("attribtransfer", "inherit_vel")
    attrib_transfer.setInput(0, scatter)
    attrib_transfer.setInput(1, obj_merge)
    attrib_transfer.parm("pointattribs").set("v")

    debris_geo.layoutChildren()
    print("Debris setup created")

finally:
    hou.setSimulationEnabled(True)
```

```python
# Cache simulation and import to Solaris
import hou

def cache_rbd_to_solaris(sim_path, cache_path="$HIP/cache/rbd.$F4.bgeo.sc"):
    """Cache RBD sim to disk, then import to Solaris."""
    sim_node = hou.node(sim_path)
    if not sim_node:
        print(f"Sim node not found: {sim_path}")
        return

    geo = sim_node.parent()

    # File cache for disk caching
    cache = geo.createNode("filecache", "rbd_cache")
    cache.setInput(0, sim_node)
    cache.parm("sopoutput").set(cache_path)
    cache.parm("trange").set(1)  # Render Frame Range

    # In Solaris: import cached geometry
    stage = hou.node("/stage")
    if stage:
        sop_import = stage.createNode("sopimport", "rbd_import")
        sop_import.parm("soppath").set(cache.path())
        print(f"Cached to {cache_path}, imported to /stage")

    geo.layoutChildren()
    return cache

cache_rbd_to_solaris("/obj/destruction/sim")
```

```python
# RBD solver tuning reference
SOLVER_SETTINGS = {
    "preview": {
        "substeps": 1,
        "fracturepoints": 10,
        "description": "Fast preview, low accuracy",
    },
    "production": {
        "substeps": 3,
        "fracturepoints": 50,
        "description": "Production quality, good accuracy",
    },
    "high_detail": {
        "substeps": 4,
        "fracturepoints": 200,
        "description": "High detail, slow but accurate",
    },
}

for preset, settings in SOLVER_SETTINGS.items():
    print(f"{preset}: substeps={settings['substeps']}, "
          f"pieces={settings['fracturepoints']} -- {settings['description']}")
```

## Expected DOP Tree
```
dopnet/
  rbdpackedobject (SOP path -> assemble output)
  bulletrbdsolver (substeps=2)
  groundplane (position=0, friction=0.5)
  gravity (-9.81)
  merge (wires: objects + solver + ground + gravity)
```

## Common Mistakes
- Not using assemble node before simulation -- unpacked geo is 10-100x slower
- Overlapping pieces on frame 1 -- add small gap or increase substeps to 4
- Constraint strength too low (< 100) -- pieces fall apart immediately
- Using polygon colliders instead of VDB -- less stable, slower
- Forgetting simulation guard (hou.setSimulationEnabled) during DOP setup
- Not caching RBD to disk before Solaris import -- re-simulates every frame
- Setting friction=0 -- pieces slide like ice (use 0.3-0.8 for realistic behavior)
