# DOP Simulation Guard Pattern

## Triggers
simulation guard, setSimulationEnabled, disable simulation, simulation during edit,
dop crash during edit, simulation enabled, safe dop editing

## Context
ALWAYS wrap DOP network creation and modification in a simulation-enabled guard. Without it, Houdini may cook the simulation during construction, causing crashes, incorrect initial state, or partial results.

## Code

```python
# Basic simulation guard — REQUIRED for all DOP modifications
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    # --- Safe to create/modify DOP nodes here ---
    dop_net = hou.node("/obj/dopnet1")
    gravity = dop_net.createNode("gravity", "gravity1")
    gravity.parm("gravityy").set(-9.81)

    dop_net.layoutChildren()
    print("DOP modification complete")

finally:
    # ALWAYS restore previous state, even if an error occurred
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# Context manager version for cleaner code
import hou
from contextlib import contextmanager

@contextmanager
def simulation_guard():
    """Context manager that disables simulation during DOP edits."""
    was_enabled = hou.simulationEnabled()
    try:
        hou.setSimulationEnabled(False)
        yield
    finally:
        hou.setSimulationEnabled(was_enabled)

# Usage
with simulation_guard():
    dop_net = hou.node("/obj/dopnet1")

    # Create RBD setup
    rbd = dop_net.createNode("rbdpackedobject", "debris")
    rbd.parm("soppath").set("/obj/debris_geo/OUT")

    solver = dop_net.createNode("bulletrbdsolver", "solver")
    merge = dop_net.createNode("merge", "merge1")
    merge.setInput(0, rbd)
    solver.setInput(0, merge)

    dop_net.layoutChildren()
# Simulation auto-re-enabled here
```

```python
# Guard for parameter changes on existing DOP nodes
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    solver = hou.node("/obj/dopnet1/bulletrbdsolver1")

    # Changing substeps triggers re-simulation
    solver.parm("substeps").set(4)

    # Changing collision mode triggers re-simulation
    solver.parm("collisiondetection").set("sdf")

    # Changing force parameters
    gravity = hou.node("/obj/dopnet1/gravity1")
    gravity.parm("gravityy").set(-15.0)

finally:
    hou.setSimulationEnabled(sim_was_enabled)
    # Now simulation will re-cook with all changes applied at once
    # instead of re-cooking after each individual change
```

```python
# Guard for node deletion in DOP networks
import hou

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    dop_net = hou.node("/obj/dopnet1")

    # Safe to delete nodes — simulation won't try to cook mid-deletion
    old_force = dop_net.node("wind1")
    if old_force:
        # Disconnect first
        for output_conn in old_force.outputConnections():
            output_conn.outputNode().setInput(
                output_conn.inputIndex(), None
            )
        old_force.destroy()
        print("Removed wind force")

    dop_net.layoutChildren()

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# Diagnostic: check if simulation is enabled before DOP work
import hou

def safe_dop_edit(func):
    """Decorator that wraps any DOP editing function in a simulation guard."""
    def wrapper(*args, **kwargs):
        was_enabled = hou.simulationEnabled()
        if was_enabled:
            print("NOTE: Disabling simulation for safe DOP editing")
        try:
            hou.setSimulationEnabled(False)
            return func(*args, **kwargs)
        finally:
            hou.setSimulationEnabled(was_enabled)
    return wrapper

@safe_dop_edit
def build_pyro_sim(geo_path):
    """Example: build a pyro simulation network."""
    dop_net = hou.node("/obj").createNode("dopnet", "pyro_sim")

    smoke_obj = dop_net.createNode("smokeobject", "smoke1")
    smoke_obj.parm("soppath").set(geo_path)

    pyro_solver = dop_net.createNode("pyrosolver", "solver1")
    merge = dop_net.createNode("merge", "merge1")
    merge.setInput(0, smoke_obj)
    pyro_solver.setInput(0, merge)

    output = dop_net.createNode("output", "OUT")
    output.setInput(0, pyro_solver)
    output.setDisplayFlag(True)

    dop_net.layoutChildren()
    return dop_net

# Usage — simulation guard is automatic
pyro_net = build_pyro_sim("/obj/emitter_geo/OUT")
```

## Expected DOP Tree
```
(Any DOP network modification safely wrapped)
dopnet1/
  ├─ [nodes created/modified/deleted]
  └─ simulation re-cooks ONLY after guard releases
```

## Common Mistakes
- Forgetting to restore simulation state in `finally` block — simulation stays disabled permanently
- Using bare `hou.setSimulationEnabled(False)` without try/finally — exception leaves simulation off
- Modifying DOP parameters one at a time without guard — each change triggers a full re-simulation
- Creating nodes inside a loop without guard — N nodes = N re-simulation attempts
- Assuming simulation is already disabled — always save and restore the current state
