# RBD Simulation Setup

## Triggers
rbd, rigid body, rbd packed, rbd object, rbd setup, fracture simulation,
bullet solver, rbd constraint, rbd collision, rbd activation, rbd deactivation

## Context
Modern RBD uses Packed Objects with Bullet solver. Workflow: fracture SOP geometry → create RBD Packed Object in DOP → add ground + gravity → Bullet solver. Constraint networks control how pieces hold together and break apart.

## Code

```python
# Complete RBD packed object setup
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    # --- SOP-level: fracture source geometry ---
    # Assumes /obj/geo1 has fractured geometry with:
    # - name attribute (piece names)
    # - constraint geometry (primitive constraint network)

    # --- DOP-level: simulation setup ---
    obj_net = hou.node("/obj")
    dop_net = obj_net.createNode("dopnet", "rbd_sim")

    # RBD Packed Object (modern workflow — NOT rbdobject)
    rbd = dop_net.createNode("rbdpackedobject", "fragments")
    rbd.parm("soppath").set("/obj/geo1/OUT")

    # Collision geometry type
    # "convexhull" — fast, approximate
    # "concave" — slower, accurate for complex shapes
    # "box" — fastest, least accurate
    # "sphere" — fast, good for round objects
    rbd.parm("geo_representation").set("convexhull")

    # Initial state
    rbd.parm("computemass").set(1)       # auto-compute from volume
    rbd.parm("density").set(1000)         # kg/m³ (water=1000, steel=7800)
    rbd.parm("friction").set(0.5)
    rbd.parm("bounce").set(0.2)

    # Ground plane
    ground = dop_net.createNode("groundplane", "ground")
    ground.parm("friction").set(0.8)
    ground.parm("bounce").set(0.1)

    # Gravity
    gravity = dop_net.createNode("gravity", "gravity1")
    gravity.parm("gravityy").set(-9.81)

    # Merge objects + forces
    merge = dop_net.createNode("merge", "merge1")
    merge.setInput(0, rbd)
    merge.setInput(1, ground)
    merge.setInput(2, gravity)

    # Bullet solver
    bullet = dop_net.createNode("bulletrbdsolver", "solver")
    bullet.parm("substeps").set(2)

    bullet.setInput(0, merge)

    # Output
    output = dop_net.createNode("output", "OUT")
    output.setInput(0, bullet)
    output.setDisplayFlag(True)

    dop_net.layoutChildren()

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# RBD Constraint Network setup
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    dop_net = hou.node("/obj/rbd_sim")

    # Constraint network — holds pieces together until force threshold
    constraint = dop_net.createNode("constraintnetwork", "glue1")
    constraint.parm("soppath").set("/obj/geo1/constraint_geo")

    # Constraint type: glue (break on impact)
    constraint.parm("constrainttype").set("glue")

    # Break threshold — force needed to separate pieces
    # Low (100): brittle (glass)
    # Medium (1000): moderate (concrete)
    # High (10000): tough (metal)
    constraint.parm("strength").set(500)

    # Add constraint to merge (after objects, before solver)
    merge = dop_net.node("merge1")
    next_input = 0
    while merge.input(next_input) is not None:
        next_input += 1
    merge.setInput(next_input, constraint)

    dop_net.layoutChildren()

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# RBD activation/deactivation (sleeping)
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    dop_net = hou.node("/obj/rbd_sim")

    # Pop Awaken — wake up specific pieces on a trigger frame
    awaken = dop_net.createNode("popawaken", "trigger_break")
    awaken.parm("group").set("@name=piece*")      # which pieces to wake
    awaken.parm("activation").set("$FF > 24")      # wake after frame 24

    # Add to merge
    merge = dop_net.node("merge1")
    next_input = 0
    while merge.input(next_input) is not None:
        next_input += 1
    merge.setInput(next_input, awaken)

    # Alternative: SOP-level activation via @active attribute
    # On the source geometry, set:
    # i@active = 0;  // initially sleeping
    # if (@Frame > 24) i@active = 1;  // wake up

    dop_net.layoutChildren()

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# Extracting RBD simulation results
import hou

dop_net = hou.node("/obj/rbd_sim")
hou.setFrame(50)  # go to frame of interest

sim = dop_net.simulation()
for obj in sim.objects():
    geo_data = obj.findSubData("Geometry")
    if geo_data:
        geo = geo_data.geometry().freeze()
        print(f"{obj.name()}: {len(geo.points())} points")

        # Read piece transforms (packed primitives)
        for prim in geo.prims():
            if prim.type() == hou.primType.PackedPrim:
                xform = prim.fullTransform()
                name = prim.attribValue("name") if geo.findPrimAttrib("name") else ""
                print(f"  Piece '{name}': pos=({xform[3][0]:.2f}, {xform[3][1]:.2f}, {xform[3][2]:.2f})")
```

## Expected DOP Tree
```
rbd_sim/
  ├─ rbdpackedobject1    (packed RBD pieces)
  │    ├─ geo_representation: convexhull
  │    └─ density: 1000
  ├─ groundplane1         (collision)
  ├─ gravity1             (force, -9.81)
  ├─ constraintnetwork1   (glue, strength=500)
  ├─ merge1               (all above)
  ├─ bulletrbdsolver1     (substeps=2)
  │    └─ input ← merge1
  └─ output1              (display flag)
```

## Common Mistakes
- Using `rbdobject` instead of `rbdpackedobject` — packed is the modern, faster workflow
- Collision representation mismatch — convex hull for complex shapes may not collide correctly, use concave
- Objects fall through ground — ground plane friction/bounce too low, or collision geo too coarse
- Constraint network not connected to merge — constraints have no effect
- Missing @name attribute on SOP geometry — RBD can't identify individual pieces
- Setting density to 1.0 — that's 1 kg/m³ (lighter than air); water is 1000, concrete is 2400
