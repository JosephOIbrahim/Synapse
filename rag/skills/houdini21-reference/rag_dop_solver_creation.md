# DOP Solver Creation

## Triggers
dop solver, create solver, bullet solver, pyro solver, flip solver, vellum solver,
mpm solver, solver setup, solver substeps, solver type

## Context
Each simulation type has its own solver node. Solvers wire from merge output (objects + forces). Substeps control accuracy vs speed. Common solvers: Bullet RBD, Pyro, FLIP, Vellum, MPM.

## Code

```python
# Bullet RBD Solver — rigid body dynamics
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    dop_net = hou.node("/obj").createNode("dopnet", "rbd_sim")

    # RBD packed object (modern workflow)
    rbd = dop_net.createNode("rbdpackedobject", "fragments")
    rbd.parm("soppath").set("/obj/fractured_geo/OUT")

    # Ground plane for collision
    ground = dop_net.createNode("groundplane", "ground")

    # Gravity
    gravity = dop_net.createNode("gravity", "gravity1")

    # Merge: objects + forces
    merge = dop_net.createNode("merge", "merge1")
    merge.setInput(0, rbd)
    merge.setInput(1, ground)
    merge.setInput(2, gravity)

    # Bullet solver
    bullet = dop_net.createNode("bulletrbdsolver", "solver")
    bullet.parm("substeps").set(2)          # 2 substeps for moderate collisions
    # bullet.parm("substeps").set(10)       # 10+ for fast/thin objects
    bullet.parm("collisiondetection").set("sdf")
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
# Pyro Solver — fire, smoke, explosions
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    dop_net = hou.node("/obj").createNode("dopnet", "pyro_sim")

    # Smoke object defines the volume container
    smoke = dop_net.createNode("smokeobject", "container")
    smoke.parm("sizex").set(5)
    smoke.parm("sizey").set(10)
    smoke.parm("sizez").set(5)
    smoke.parm("divsize").set(0.05)     # voxel size

    # Source volume
    source = dop_net.createNode("sourcevolume", "source1")
    source.parm("soppath").set("/obj/emitter/OUT")

    # Pyro solver
    pyro = dop_net.createNode("pyrosolver", "solver")
    pyro.parm("substeps").set(1)          # usually 1 is fine for pyro
    pyro.parm("timescale").set(1.0)

    # Merge + wire
    merge = dop_net.createNode("merge", "merge1")
    merge.setInput(0, smoke)
    merge.setInput(1, source)
    pyro.setInput(0, merge)

    output = dop_net.createNode("output", "OUT")
    output.setInput(0, pyro)
    output.setDisplayFlag(True)

    dop_net.layoutChildren()

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# FLIP Solver — liquids
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    dop_net = hou.node("/obj").createNode("dopnet", "flip_sim")

    # FLIP object
    flip_obj = dop_net.createNode("flipobject", "liquid")
    flip_obj.parm("soppath").set("/obj/liquid_source/OUT")
    flip_obj.parm("particlesep").set(0.02)     # particle separation

    # FLIP solver
    flip_solver = dop_net.createNode("flipsolver", "solver")
    flip_solver.parm("substeps").set(2)
    flip_solver.parm("viscosity").set(0)        # 0 = water, higher = honey

    # Gravity
    gravity = dop_net.createNode("gravity", "gravity1")

    # Merge + wire
    merge = dop_net.createNode("merge", "merge1")
    merge.setInput(0, flip_obj)
    merge.setInput(1, gravity)
    flip_solver.setInput(0, merge)

    output = dop_net.createNode("output", "OUT")
    output.setInput(0, flip_solver)
    output.setDisplayFlag(True)

    dop_net.layoutChildren()

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# Substep guidelines for different simulation types
SUBSTEP_GUIDE = {
    # Solver type:          (default, thin/fast, heavy/complex)
    "bulletrbdsolver":      (2,       10,        4),
    "pyrosolver":           (1,       2,         1),
    "flipsolver":           (2,       5,         3),
    "vellumsolver":         (5,       10,        5),
    "mpmsolver":            (1,       4,         2),
}

# Rule of thumb:
# - Thin/fast objects colliding: increase substeps
# - Large/slow objects: default substeps are fine
# - More substeps = more accurate but slower
# - If objects pass through each other: double substeps
# - If sim is too slow: halve substeps and check quality
```

## Expected DOP Tree
```
dopnet1/
  ├─ rbdpackedobject1  (object)
  ├─ groundplane1      (collision object)
  ├─ gravity1          (force)
  ├─ merge1            (combines all above)
  ├─ bulletrbdsolver1  (solver, reads from merge)
  └─ output1           (display flag set)
```

## Common Mistakes
- Creating solver without connecting it to merge — solver has nothing to solve
- Using too few substeps for fast/thin objects — objects pass through each other
- Using too many substeps unnecessarily — simulation runs 10x slower with no visible benefit
- Connecting solver INTO merge instead of FROM merge — solver reads merge output, doesn't feed into it
- Forgetting ground plane for RBD — objects fall into void
- Not setting particle separation on FLIP — default may be too coarse or too fine for your scene scale
