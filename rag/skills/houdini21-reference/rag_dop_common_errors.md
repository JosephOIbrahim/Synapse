# DOP Common Errors and Diagnostics

## Triggers
dop error, simulation error, simulation explode, objects fall through, no object to solve,
simulation crash, dop not working, simulation unstable, dop debug, dop troubleshoot

## Context
Common DOP simulation failures with diagnostic code. Covers: frame-1 explosion, fall-through, missing objects, unexpected resets, freeze requirement, substep instability.

## Code

```python
# Diagnostic 1: Simulation explodes on frame 1
# Causes: overlapping objects, zero-volume pieces, extreme velocities
import hou

def diagnose_frame1_explosion(dop_path):
    """Check for common causes of frame-1 explosion."""
    dop_net = hou.node(dop_path)
    if not dop_net:
        print(f"DOP network not found: {dop_path}")
        return

    issues = []

    # Check RBD objects for source geometry issues
    for node in dop_net.children():
        if node.type().name() == "rbdpackedobject":
            sop_path = node.evalParm("soppath")
            sop_node = hou.node(sop_path)
            if sop_node is None:
                issues.append(f"{node.name()}: source SOP not found ({sop_path})")
                continue

            geo = sop_node.geometry()

            # Check for zero-volume pieces
            for prim in geo.prims():
                bbox = prim.boundingBox()
                vol = bbox.sizevec()
                if min(vol) < 0.001:
                    name = prim.attribValue("name") if geo.findPrimAttrib("name") else f"prim_{prim.number()}"
                    issues.append(f"Zero-volume piece: {name} (size: {vol})")

            # Check for overlapping centers
            centers = []
            for prim in geo.prims():
                c = prim.boundingBox().center()
                centers.append((c[0], c[1], c[2]))
            # Very rough overlap check
            for i in range(len(centers)):
                for j in range(i+1, min(i+50, len(centers))):
                    dist = sum((a-b)**2 for a, b in zip(centers[i], centers[j])) ** 0.5
                    if dist < 0.001:
                        issues.append(f"Overlapping piece centers at index {i} and {j}")

    if issues:
        print("FRAME 1 EXPLOSION - Likely causes:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("No obvious frame-1 issues found. Check initial velocities and collision gaps.")

diagnose_frame1_explosion("/obj/dopnet1")
```

```python
# Diagnostic 2: Objects fall through ground
# Causes: collision representation mismatch, scale issues, too few substeps
import hou

def diagnose_fall_through(dop_path):
    """Check for collision configuration issues."""
    dop_net = hou.node(dop_path)
    issues = []

    for node in dop_net.children():
        if node.type().name() == "rbdpackedobject":
            geo_rep = node.evalParm("geo_representation")
            sop_path = node.evalParm("soppath")
            sop_node = hou.node(sop_path)

            if sop_node:
                geo = sop_node.geometry()
                bbox = geo.boundingBox()
                min_dim = min(bbox.sizevec())

                # Very small objects need higher substeps or different collision
                if min_dim < 0.01:
                    issues.append(
                        f"{node.name()}: very small pieces ({min_dim:.4f}), "
                        f"geo_rep={geo_rep}. Try 'concave' or increase substeps."
                    )

                # Convex hull may miss concave shapes
                if geo_rep == "convexhull":
                    issues.append(
                        f"{node.name()}: using convexhull — if concave shapes "
                        f"fall through, switch to 'concave'"
                    )

        # Check solver substeps
        if "solver" in node.type().name().lower():
            substeps = node.evalParm("substeps") if node.parm("substeps") else 1
            if substeps < 2:
                issues.append(
                    f"{node.name()}: substeps={substeps}. "
                    f"Increase to 2-5 for thin/fast objects."
                )

    if issues:
        print("FALL-THROUGH - Possible causes:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Collision config looks OK. Check ground plane position and scene scale.")

diagnose_fall_through("/obj/dopnet1")
```

```python
# Diagnostic 3: "No object to solve" error
# Causes: solver not connected to merge, empty object group, wrong SOP path
import hou

def diagnose_no_object(dop_path):
    """Check why solver has no objects."""
    dop_net = hou.node(dop_path)
    issues = []

    solvers = [n for n in dop_net.children() if "solver" in n.type().name().lower()]
    for solver in solvers:
        # Check if solver has input
        input_node = solver.input(0)
        if input_node is None:
            issues.append(f"{solver.name()}: NO INPUT connected — wire from merge node")
            continue

        # Check if input is a merge with objects
        if input_node.type().name() == "merge":
            has_object = False
            for i in range(20):  # check up to 20 inputs
                inp = input_node.input(i)
                if inp is None:
                    break
                if "object" in inp.type().name().lower() or \
                   inp.type().name() in ("rbdpackedobject", "smokeobject", "flipobject"):
                    has_object = True
                    # Check if object's SOP path is valid
                    if inp.parm("soppath"):
                        sop_path = inp.evalParm("soppath")
                        if not hou.node(sop_path):
                            issues.append(
                                f"{inp.name()}: SOP path invalid ({sop_path})"
                            )
            if not has_object:
                issues.append(
                    f"Merge '{input_node.name()}' has no object nodes — "
                    f"only forces/constraints feed into solver"
                )

    if issues:
        print("NO OBJECT TO SOLVE - Causes:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Object configuration looks OK.")

diagnose_no_object("/obj/dopnet1")
```

```python
# Diagnostic 4: Simulation resets unexpectedly
# Cause: simulation was enabled during network modification
import hou

def diagnose_unexpected_reset():
    """Check if simulation is currently enabled (dangerous during edits)."""
    if hou.simulationEnabled():
        print("WARNING: Simulation is ENABLED")
        print("  Any DOP network edit will trigger re-simulation from frame 1")
        print("  Wrap modifications in simulation guard:")
        print("    sim_was_enabled = hou.simulationEnabled()")
        print("    try:")
        print("        hou.setSimulationEnabled(False)")
        print("        # ... your edits ...")
        print("    finally:")
        print("        hou.setSimulationEnabled(sim_was_enabled)")
    else:
        print("Simulation is disabled — safe to edit DOP networks")

diagnose_unexpected_reset()
```

```python
# Diagnostic 5: DOP data not accessible (freeze requirement)
import hou

def diagnose_dop_access(dop_path):
    """Check DOP data accessibility and remind about freeze()."""
    dop_net = hou.node(dop_path)
    sim = dop_net.simulation()

    objects = sim.objects()
    if not objects:
        print("No simulation objects found. Is the sim cached/cooked?")
        return

    for obj in objects:
        geo_data = obj.findSubData("Geometry")
        if geo_data is None:
            print(f"  {obj.name()}: No Geometry subdata")
            continue

        geo = geo_data.geometry()
        print(f"  {obj.name()}: {len(geo.points())} points (LIVE reference)")
        print(f"    Call .freeze() to get independent copy:")
        print(f"    frozen_geo = geo_data.geometry().freeze()")

        # Demonstrate freeze
        frozen = geo.freeze()
        print(f"    Frozen copy: {len(frozen.points())} points (independent)")

diagnose_dop_access("/obj/dopnet1")
```

```python
# Master diagnostic runner
import hou

def full_dop_diagnostic(dop_path):
    """Run all DOP diagnostics on a network."""
    print(f"=== DOP Diagnostic: {dop_path} ===\n")

    dop_net = hou.node(dop_path)
    if not dop_net:
        print(f"ERROR: DOP network not found at {dop_path}")
        return

    print("1. Simulation State:")
    diagnose_unexpected_reset()

    print("\n2. Frame 1 Explosion Check:")
    diagnose_frame1_explosion(dop_path)

    print("\n3. Fall-Through Check:")
    diagnose_fall_through(dop_path)

    print("\n4. Object Connectivity:")
    diagnose_no_object(dop_path)

    print("\n5. Data Access:")
    diagnose_dop_access(dop_path)

    print("\n=== Diagnostic Complete ===")

# Usage
full_dop_diagnostic("/obj/dopnet1")
```

## Expected Output
```
=== DOP Diagnostic: /obj/dopnet1 ===

1. Simulation State:
Simulation is disabled — safe to edit DOP networks

2. Frame 1 Explosion Check:
No obvious frame-1 issues found.

3. Fall-Through Check:
FALL-THROUGH - Possible causes:
  - fragments: using convexhull — if concave shapes fall through, switch to 'concave'

4. Object Connectivity:
Object configuration looks OK.

5. Data Access:
  fragments: 1250 points (LIVE reference)
    Call .freeze() to get independent copy

=== Diagnostic Complete ===
```

## Common Mistakes
- Not running diagnostics before tweaking parameters — diagnose first, fix second
- Ignoring zero-volume pieces — they cause infinite forces in Bullet solver
- Assuming simulation state persists between Houdini sessions — it doesn't, always recook
- Using `geo.points()` instead of `geo.freeze().points()` — live DOP geometry reference changes per frame
- Not checking SOP path validity before sim — invalid soppath silently produces empty objects
