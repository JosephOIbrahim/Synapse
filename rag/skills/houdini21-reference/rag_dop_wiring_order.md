# DOP Node Wiring Conventions

## Triggers
dop wiring, dop merge, dop connection, enforceWiringOrder, merge input,
dop node order, dop network wiring, connect dop nodes, dop merge pattern

## Context
DOPs use merge-based connections, NOT SOP-style direct wiring. Objects, forces, and solvers feed into merge nodes. Wiring order matters — objects first, then forces, then solvers. The merge node's `enforceWiringOrder` controls whether order is strict.

## Code

```python
# Standard DOP wiring pattern: objects + forces → merge → solver
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    # Create or get DOP network
    obj_net = hou.node("/obj")
    dop_net = obj_net.createNode("dopnet", "sim1")

    # --- Create objects ---
    rbd_obj = dop_net.createNode("rbdpackedobject", "hero_rbd")
    rbd_obj.parm("soppath").set("/obj/hero_geo/OUT")

    ground = dop_net.createNode("groundplane", "ground")

    # --- Create forces ---
    gravity = dop_net.createNode("gravity", "gravity1")
    gravity.parm("gravityy").set(-9.81)

    # --- Create solver ---
    bullet = dop_net.createNode("bulletrbdsolver", "solver1")

    # --- Wire via merge (THE CORRECT PATTERN) ---
    merge = dop_net.createNode("merge", "merge1")

    # Order matters: objects first, then forces
    merge.setInput(0, rbd_obj)    # input 0: RBD object
    merge.setInput(1, ground)     # input 1: ground plane
    merge.setInput(2, gravity)    # input 2: gravity force

    # Solver wires from merge output
    bullet.setInput(0, merge)

    # Set output/display
    output = dop_net.createNode("output", "OUT")
    output.setInput(0, bullet)
    output.setDisplayFlag(True)

    dop_net.layoutChildren()
    print("DOP network wired successfully")

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# Using findOrCreateMergeInput pattern for dynamic wiring
import hou

def add_to_dop_merge(dop_net, merge_node, new_node):
    """Add a new node to the next available merge input."""
    # Find the next empty input
    idx = 0
    while merge_node.input(idx) is not None:
        idx += 1
    merge_node.setInput(idx, new_node)
    return idx

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    dop_net = hou.node("/obj/sim1")
    merge = dop_net.node("merge1")

    # Add wind force to existing merge
    wind = dop_net.createNode("wind", "wind1")
    wind.parm("windspeed").set(5.0)
    input_idx = add_to_dop_merge(dop_net, merge, wind)
    print(f"Wind connected to merge input {input_idx}")

    dop_net.layoutChildren()

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# Verifying DOP wiring order
import hou

def verify_dop_wiring(dop_net):
    """Check that DOP merge inputs follow correct order."""
    issues = []
    for node in dop_net.children():
        if node.type().name() == "merge":
            saw_force = False
            saw_solver = False
            for i in range(node.inputs().__len__()):
                inp = node.input(i)
                if inp is None:
                    continue
                cat = inp.type().category().name()
                node_type = inp.type().name()

                # Check order: objects before forces before solvers
                is_force = node_type in ("gravity", "wind", "fan", "drag",
                                          "fieldforce", "popforce")
                is_solver = "solver" in node_type.lower()

                if is_force:
                    saw_force = True
                if is_solver:
                    saw_solver = True
                    if not saw_force:
                        issues.append(
                            f"Solver '{inp.name()}' before forces on "
                            f"merge '{node.name()}' input {i}"
                        )
    return issues

dop_net = hou.node("/obj/sim1")
issues = verify_dop_wiring(dop_net)
if issues:
    for issue in issues:
        print(f"WARNING: {issue}")
else:
    print("DOP wiring order verified")
```

## Expected DOP Tree
```
dopnet1/
  ├─ rbdpackedobject1  (object)
  ├─ groundplane1      (object)
  ├─ gravity1          (force)
  ├─ wind1             (force)
  ├─ merge1            (merge)
  │    ├─ input0 ← rbdpackedobject1
  │    ├─ input1 ← groundplane1
  │    ├─ input2 ← gravity1
  │    └─ input3 ← wind1
  ├─ bulletrbdsolver1  (solver)
  │    └─ input0 ← merge1
  └─ output1           (output)
       └─ input0 ← bulletrbdsolver1
```

## Common Mistakes
- Direct-wiring objects to solver (SOP-style) — DOPs require merge nodes to combine inputs
- Wrong merge input order — objects must come before forces for correct data flow
- Forgetting the output node — DOP network needs an output node with display flag
- Wiring solver into the merge — solver reads FROM merge, not INTO it
- Not disabling simulation during network construction — causes partial cooks mid-build
