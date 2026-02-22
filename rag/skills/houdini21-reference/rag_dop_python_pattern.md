# Complete DOP Network Creation Pattern

## Triggers
dop python, create dop network, build simulation, full dop setup, dop from scratch,
simulation python, dop template, dop master pattern, automated simulation

## Context
Master pattern for creating a complete DOP network from scratch via Python. Covers: source geometry, DOP network creation, objects, forces, constraints, solver, output, caching. All other DOP RAG entries are building blocks for this pattern.

## Code

```python
# Complete end-to-end DOP network creation
# This is the master pattern — all DOP RAG entries feed into this
import hou
import os

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    # ============================================
    # Step 1: Verify source geometry exists
    # ============================================
    source_sop = hou.node("/obj/fractured_geo/OUT")
    if source_sop is None:
        raise RuntimeError("Source geometry not found at /obj/fractured_geo/OUT")

    # Verify it has required attributes
    geo = source_sop.geometry()
    has_name = geo.findPrimAttrib("name") is not None
    has_pieces = len(set(p.attribValue("name") for p in geo.prims())) if has_name else 0
    print(f"Source geometry: {len(geo.points())} points, {has_pieces} pieces")

    if not has_name:
        print("WARNING: No @name attribute — RBD won't identify individual pieces")

    # ============================================
    # Step 2: Create DOP network
    # ============================================
    obj_net = hou.node("/obj")
    dop_net = obj_net.createNode("dopnet", "rbd_simulation")

    # Frame range
    dop_net.parm("startframe").set(1)

    # Enable checkpointing for long sims
    cache_dir = hou.text.expandString("$HIP/sim_cache")
    os.makedirs(cache_dir, exist_ok=True)
    dop_net.parm("cacheenabled").set(1)
    dop_net.parm("cachedir").set("$HIP/sim_cache")
    dop_net.parm("checkpointinterval").set(10)

    # ============================================
    # Step 3: Create objects
    # ============================================
    # RBD Packed Object (modern workflow)
    rbd = dop_net.createNode("rbdpackedobject", "fragments")
    rbd.parm("soppath").set("/obj/fractured_geo/OUT")
    rbd.parm("geo_representation").set("convexhull")
    rbd.parm("computemass").set(1)
    rbd.parm("density").set(2400)      # concrete density
    rbd.parm("friction").set(0.6)
    rbd.parm("bounce").set(0.1)

    # Ground plane
    ground = dop_net.createNode("groundplane", "ground")
    ground.parm("friction").set(0.8)
    ground.parm("bounce").set(0.05)

    # ============================================
    # Step 4: Create forces
    # ============================================
    gravity = dop_net.createNode("gravity", "gravity1")
    gravity.parm("gravityy").set(-9.81)

    # Optional: wind force
    wind = dop_net.createNode("wind", "wind1")
    wind.parm("windspeed").set(3.0)
    wind.parm("winddirx").set(1.0)
    wind.parm("winddiry").set(0.0)
    wind.parm("winddirz").set(0.0)

    # ============================================
    # Step 5: Create constraints (optional)
    # ============================================
    # Only if source geo has constraint geometry
    constraint_sop = hou.node("/obj/fractured_geo/constraints_OUT")
    if constraint_sop:
        constraint = dop_net.createNode("constraintnetwork", "glue_constraints")
        constraint.parm("soppath").set(constraint_sop.path())
        constraint.parm("constrainttype").set("glue")
        constraint.parm("strength").set(800)
    else:
        constraint = None

    # ============================================
    # Step 6: Wire via merge (correct order)
    # ============================================
    merge = dop_net.createNode("merge", "merge_all")
    input_idx = 0

    # Objects first
    merge.setInput(input_idx, rbd);       input_idx += 1
    merge.setInput(input_idx, ground);    input_idx += 1

    # Then forces
    merge.setInput(input_idx, gravity);   input_idx += 1
    merge.setInput(input_idx, wind);      input_idx += 1

    # Then constraints
    if constraint:
        merge.setInput(input_idx, constraint); input_idx += 1

    # ============================================
    # Step 7: Create solver
    # ============================================
    bullet = dop_net.createNode("bulletrbdsolver", "solver")
    bullet.parm("substeps").set(2)
    bullet.setInput(0, merge)

    # ============================================
    # Step 8: Output
    # ============================================
    output = dop_net.createNode("output", "OUT")
    output.setInput(0, bullet)
    output.setDisplayFlag(True)

    # ============================================
    # Step 9: Layout and organize
    # ============================================
    dop_net.layoutChildren()

    # Summary
    print(f"DOP Network created: {dop_net.path()}")
    print(f"  Objects: fragments, ground")
    print(f"  Forces: gravity, wind")
    print(f"  Constraints: {'glue' if constraint else 'none'}")
    print(f"  Solver: Bullet (substeps=2)")
    print(f"  Checkpoints: {cache_dir} (every 10 frames)")

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# Adding a DOP Import + File Cache for output
import hou
import os

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    # Create output geometry node
    obj_net = hou.node("/obj")
    output_geo = obj_net.createNode("geo", "sim_output")

    # Delete default file node
    for child in output_geo.children():
        child.destroy()

    # DOP Import — brings simulation results into SOPs
    dop_import = output_geo.createNode("dopimport", "import_sim")
    dop_import.parm("doppath").set("/obj/rbd_simulation")
    dop_import.parm("objpattern").set("*")
    dop_import.parm("importstyle").set("fetch")

    # File Cache — write to disk per frame
    cache = output_geo.createNode("filecache", "cache_sim")
    cache.setInput(0, dop_import)

    cache_path = "$HIP/geo_cache/rbd_sim.$F4.bgeo.sc"
    cache.parm("file").set(cache_path)
    cache.parm("filemode").set(2)  # Write mode

    # Ensure output directory exists
    cache_dir = os.path.dirname(hou.text.expandString(cache_path))
    os.makedirs(cache_dir, exist_ok=True)

    cache.setDisplayFlag(True)
    cache.setRenderFlag(True)
    output_geo.layoutChildren()

    print(f"Output configured: {cache_path}")

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

## Expected DOP Tree
```
/obj/rbd_simulation/        (DOP Network)
  ├─ fragments               (rbdpackedobject, source: /obj/fractured_geo/OUT)
  ├─ ground                  (groundplane)
  ├─ gravity1                (gravity, -9.81)
  ├─ wind1                   (wind, speed=3.0)
  ├─ glue_constraints        (constraintnetwork, strength=800)
  ├─ merge_all               (merge)
  │    ├─ input0 ← fragments
  │    ├─ input1 ← ground
  │    ├─ input2 ← gravity1
  │    ├─ input3 ← wind1
  │    └─ input4 ← glue_constraints
  ├─ solver                  (bulletrbdsolver, substeps=2)
  │    └─ input0 ← merge_all
  └─ OUT                     (output, display flag)

/obj/sim_output/             (SOP geometry)
  ├─ import_sim              (dopimport ← /obj/rbd_simulation)
  └─ cache_sim               (filecache → $HIP/geo_cache/rbd_sim.$F4.bgeo.sc)
```

## Common Mistakes
- Not verifying source geometry has @name attribute before creating RBD Packed Object
- Wiring constraint network after solver instead of into merge — constraints have no effect
- Forgetting simulation guard — simulation cooks mid-construction, corrupting initial state
- Not setting File Cache to Write mode (filemode=2) — defaults to Read, produces no output
- Creating DOP network inside /stage (LOP context) — DOPs belong in /obj
