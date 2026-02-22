# DOP Data Tree Navigation

## Triggers
dop data, DopData, dop hierarchy, dop subdata, freeze, extract geometry from dop,
dop records, dop object data, simulation data, dop geometry

## Context
DOP data forms a tree: simulation → objects → subdata (geometry, forces, solver state). Access via `hou.DopData`. Use `freeze()` to extract geometry from DOP objects. DOP records store per-object metadata.

## Code

```python
# Accessing DOP data tree from a DOP network
import hou

dop_net = hou.node("/obj/dopnet1")
sim = dop_net.simulation()

# --- List all DOP objects ---
objects = sim.objects()
for obj in objects:
    print(f"Object: {obj.name()}")

    # List subdata on this object
    for subdata_name in obj.subDataNames():
        subdata = obj.subData()[subdata_name]
        print(f"  Subdata: {subdata_name} ({subdata.dataType()})")

    # Common subdata names:
    # "Geometry"      — the simulated geometry
    # "Forces"        — accumulated forces
    # "Solver"        — solver state
    # "Position"      — position data
    # "PhysicalParms" — mass, bounce, friction
```

```python
# Extracting geometry from DOP objects using freeze()
import hou

dop_net = hou.node("/obj/dopnet1")
sim = dop_net.simulation()

for obj in sim.objects():
    # Get geometry subdata
    geo_data = obj.findSubData("Geometry")
    if geo_data is None:
        print(f"  {obj.name()}: no Geometry subdata")
        continue

    # freeze() extracts a hou.Geometry copy from DOP data
    # WITHOUT freeze(), the data is a live reference that changes each frame
    geo = geo_data.geometry()
    frozen_geo = geo.freeze()  # CRITICAL: creates independent copy

    print(f"  {obj.name()}: {frozen_geo.intrinsicValue('pointcount')} points")

    # Now you can read attributes from the frozen geometry
    for pt in frozen_geo.points()[:5]:  # first 5 points
        pos = pt.position()
        vel = pt.attribValue("v") if frozen_geo.findPointAttrib("v") else (0, 0, 0)
        print(f"    Point {pt.number()}: pos={pos}, vel={vel}")
```

```python
# Reading DOP records (metadata per object)
import hou

dop_net = hou.node("/obj/dopnet1")
sim = dop_net.simulation()

for obj in sim.objects():
    print(f"\nObject: {obj.name()}")

    # Object-level records
    record = obj.record("Basic")
    if record:
        # Common record fields
        fields = record.fieldNames()
        for field_name in fields:
            value = record.field(field_name)
            print(f"  {field_name} = {value}")

    # Simulation state records
    state_record = obj.record("Solver")
    if state_record:
        for field_name in state_record.fieldNames():
            print(f"  solver.{field_name} = {state_record.field(field_name)}")
```

```python
# Recursive subdata listing (full tree dump)
import hou

def dump_dop_tree(data, indent=0):
    """Recursively print the DOP data tree."""
    prefix = "  " * indent
    print(f"{prefix}{data.name()} ({data.dataType()})")

    # Print records
    for record_type in data.recordTypes():
        record = data.record(record_type)
        if record:
            print(f"{prefix}  [Record: {record_type}]")
            for field_name in record.fieldNames()[:10]:  # limit output
                print(f"{prefix}    {field_name} = {record.field(field_name)}")

    # Recurse into subdata
    for name in data.subDataNames():
        subdata = data.subData()[name]
        dump_dop_tree(subdata, indent + 1)

# Usage
dop_net = hou.node("/obj/dopnet1")
sim = dop_net.simulation()
for obj in sim.objects():
    dump_dop_tree(obj)
```

```python
# Accessing DOP data at specific simulation frame
import hou

dop_net = hou.node("/obj/dopnet1")

# Cook to specific frame first
hou.setFrame(50)

sim = dop_net.simulation()
for obj in sim.objects():
    geo_data = obj.findSubData("Geometry")
    if geo_data:
        geo = geo_data.geometry().freeze()
        bbox = geo.boundingBox()
        print(f"Frame 50 - {obj.name()}:")
        print(f"  Points: {len(geo.points())}")
        print(f"  Bounds: min={bbox.minvec()}, max={bbox.maxvec()}")
```

## Expected DOP Tree
```
Simulation
  └─ rbdpackedobject1
       ├─ [Record: Basic] name, objid, creation_time
       ├─ Geometry (SIM_GeometryCopy)
       │    └─ .geometry() → hou.Geometry (call .freeze() to extract)
       ├─ Forces (SIM_ForceData)
       ├─ Solver (SIM_SolverData)
       ├─ Position (SIM_PositionData)
       │    └─ [Record: Position] tx, ty, tz, rx, ry, rz
       └─ PhysicalParms (SIM_PhysicalParms)
            └─ [Record: PhysicalParms] mass, bounce, friction
```

## Common Mistakes
- Not calling `freeze()` on DOP geometry — data is a live reference, changes when frame advances
- Accessing simulation data without cooking to the target frame first
- Assuming `obj.geometry()` exists — must use `obj.findSubData("Geometry").geometry()`
- Modifying frozen geometry expecting it to affect the simulation — frozen copies are independent
- Iterating all points in a large sim without limiting — millions of points will hang the session
