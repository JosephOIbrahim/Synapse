<!-- Shipped 2026-09-03 for wave BP4 from the claude.ai project skill `solaris-usd-composition` (references/composition-deep-dive.md).
     VOCABULARY and REFEREE only; runtime (pxr under hython 22.0.400) is truth.
     CTO note, honesty-by-design: the Specialize example's closing line ("if base changes ... spot1 gets 0.5 (base is stronger)")
     is WRONG per USD semantics - a prim's own local opinion wins over anything it specializes; specializes only supplies
     fallbacks that any stronger opinion overrides. Also the inherit list-editing claim "first added = strongest" is
     unverified here. Verify both against pxr on the build before citing either. -->

# USD Composition Deep Dive

## Arc Behavior Details

### Reference Arc

**Creates**: New namespace for referenced content
**Behavior**:
- Target root prim mapped to referencing prim path
- Opinions composed according to LIVRPS
- Nested references resolved recursively

```
# Example: /World/props/chair references chair.usd
# chair.usd has /Chair/geometry/mesh

Result:
/World/props/chair           <- reference root
/World/props/chair/geometry  <- from chair.usd
/World/props/chair/geometry/mesh
```

**Internal vs External**:
```python
# External reference (separate file)
prim.GetReferences().AddReference("./chair.usd")

# Internal reference (same stage)
prim.GetReferences().AddInternalReference("/classes/ChairClass")
```

### Payload Arc

**Identical to Reference except**:
- Can be unloaded via stage population mask
- Deferred loading improves stage open time
- Use for assets >1MB or complex hierarchies

```python
# Load control
stage.Load("/World/props/chair")      # Load specific payload
stage.Unload("/World/props/chair")    # Unload
stage.LoadAll()                        # Load everything
```

**H21 Best Practice**: Use payloads for hero assets, references for lightweight props.

### Sublayer Arc

**Behavior**:
- Layers stack with later layers stronger
- No namespace remapping
- Direct prim path correspondence

```
# Layer stack (bottom to top):
base.usd:       /World/light.intensity = 1.0
override.usd:   /World/light.intensity = 2.0

# Result: intensity = 2.0 (override wins)
```

**Sublayer vs Reference**:
- Sublayer: Same prim paths, opinion override
- Reference: New namespace, asset encapsulation

### Variant Set Arc

**Creates**: Switchable prim variations
**Behavior**:
- Variants are prim-local
- Selection stored as metadata
- Non-selected variants don't contribute opinions

```python
# Define variants
vset = prim.GetVariantSets().AddVariantSet("LOD")
vset.AddVariant("high")
vset.AddVariant("low")

# Author in variant context
vset.SetVariantSelection("high")
with vset.GetVariantEditContext():
    # Opinions go into "high" variant
    prim.GetAttribute("visibility").Set("inherited")
```

**Nested Variants**:
```
/chair{LOD=high}{material=wood}  <- Two variant selections
```

### Inherit Arc

**Creates**: Class-based property sharing
**Behavior**:
- Inheriting prim gets class opinions
- Changes to class propagate to all inheritors
- Class prims typically under `/__class__` or `/classes`

```python
# Define class
class_prim = stage.DefinePrim("/classes/PropClass")
class_prim.SetTypeName("")  # Abstract class
class_prim.CreateAttribute("prop:category", Sdf.ValueTypeNames.String).Set("furniture")

# Inherit from class
prim = stage.DefinePrim("/World/chair")
prim.GetInherits().AddInherit("/classes/PropClass")
# chair now has prop:category = "furniture"
```

### Specialize Arc

**Creates**: Template-based specialization
**Behavior**:
- Weakest arc (base wins over specialized)
- Good for "is-a" relationships
- Changes to base override specialized opinions

```python
# Base template
base = stage.DefinePrim("/templates/BaseLight")
base.CreateAttribute("intensity", Sdf.ValueTypeNames.Float).Set(1.0)

# Specialized version
spot = stage.DefinePrim("/lights/spot1")
spot.GetSpecializes().AddSpecialize("/templates/BaseLight")
spot.GetAttribute("intensity").Set(2.0)

# If base changes to intensity=0.5, spot1 gets 0.5 (base is stronger)   <- SEE CTO NOTE AT TOP: this line is wrong
```

## Nested Composition Resolution

### Resolution Order
1. Flatten local layer stack (sublayers)
2. Process arcs in LIVRPS order
3. For each arc, recursively resolve target
4. Compose opinions

### Example: Reference containing Variant
```
main.usd references chair.usd
chair.usd has VariantSet "style" with "modern" and "classic"

Resolution:
1. main.usd opens
2. Reference arc to chair.usd traversed
3. chair.usd sublayers composed
4. Variant "style" evaluated at current selection
5. Variant opinions composed
6. Result composed into main stage
```

## Relationship Targeting Across Arcs

### Path Resolution
Relationships and connections use composed paths:
```python
# In referenced asset
rel.AddTarget("/Chair/materials/wood")

# After referencing at /World/props/chair
# Target resolves to: /World/props/chair/materials/wood
```

### Cross-Reference Targeting
```python
# Target prim in different reference
material_rel.AddTarget("/World/materials/shared_wood")
# Works if target exists in composed stage
```

## List-Editing Operations

### Prepend, Append, Delete
```python
# References use list-editing
refs = prim.GetReferences()
refs.AddReference("base.usd")        # Appends by default
refs.AddReference("override.usd", position=Usd.ListPositionFrontOfPrependList)

# Explicit operations
refs.PrependReference("first.usd")   # Strongest
refs.AppendReference("last.usd")     # Weakest
refs.RemoveReference(ref)            # Remove specific
refs.ClearReferences()               # Remove all
```

### Inherit/Specialize List Editing
```python
inherits = prim.GetInherits()
inherits.AddInherit("/classes/A")    # First added = strongest inherit   <- unverified, see CTO note
inherits.AddInherit("/classes/B")    # B weaker than A

# Reorder
inherits.RemoveInherit("/classes/A")
inherits.AddInherit("/classes/A")    # Now A is weakest
```

## Debugging Composition

### Query Composition Arcs
```python
# Get prim's direct composition arcs
query = Usd.PrimCompositionQuery(prim)
for arc in query.GetCompositionArcs():
    print(f"Arc: {arc.GetArcType()}")
    print(f"  Target: {arc.GetTargetNode().GetPath()}")
    print(f"  Layer: {arc.GetTargetNode().GetLayerStack().identifier}")
```

### Find Opinion Source
```python
# Which layer provides attribute value?
attr = prim.GetAttribute("intensity")
stack = attr.GetPropertyStack(Usd.TimeCode.Default())
for spec in stack:
    print(f"Layer: {spec.layer.identifier}")
    print(f"Path: {spec.path}")
```

### Composition Errors
```python
# Check for composition errors
for error in stage.GetCompositionErrors():
    print(f"Error: {error}")
```
