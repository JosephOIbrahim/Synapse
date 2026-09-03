<!-- Shipped 2026-09-03 for wave BP4 from the claude.ai project skill `solaris-usd-composition` (Houdini 21 vintage).
     Role in this repo: VOCABULARY and REFEREE for the BP4-USDKNOW leg. It is not truth.
     Runtime is truth: every rule a leg promotes must carry a hython 22.0.400 anchor or stay DOC-STATED / PROPOSED.
     Companion: composition-deep-dive.md (same skill, references/). -->

# Solaris USD Composition

Decision frameworks for USD composition in Houdini 21 Solaris.

## Composition Arc Decision Tree

```
What are you trying to do?
│
├─ Load complete asset with materials
│  └─ Use REFERENCE
│     └─ Asset encapsulated, opinions composed
│
├─ Load heavy asset, defer until needed
│  └─ Use PAYLOAD
│     └─ Same as reference + unloadable
│
├─ Override/extend existing prims
│  └─ Use SUBLAYER
│     └─ Strongest layer wins
│
├─ Multiple variations (LOD, materials)
│  └─ Use VARIANT SET
│     └─ Switch without recomposing stage
│
├─ Share properties across prim types
│  └─ Use INHERIT
│     └─ Class-based property sharing
│
└─ Specialized version of base prim
   └─ Use SPECIALIZE
      └─ Weakest arc, base overrides child
```

## LIVRPS Strength Order

**L**ocal > **I**nherit > **V**ariant > **R**eference > **P**ayload > **S**pecialize

```
STRONGEST ─────────────────────────────> WEAKEST

Local opinions (direct attribute sets)
  │
  ├─ Inherit (class properties)
  │
  ├─ Variant (variant selections)
  │
  ├─ Reference (asset composition)
  │
  ├─ Payload (deferred references)
  │
  └─ Specialize (base templates)
```

## Quick Patterns

### Asset Reference
```
# Solaris: Reference LOP
Primitive Path: /assets/chair
Reference File: chair.usd
```

### Shot Layer Stack
```
# Bottom to top (weak to strong):
1. asset.usd        (base geometry)
2. materials.usd    (material assignments)
3. lighting.usd     (lights, exposure)
4. animation.usd    (transforms, deformations)
5. fx.usd           (simulations, particles)
6. shot_override.usd (shot-specific tweaks)
```

### Variant Selection
```python
# In LOP Python
stage = node.editableStage()
prim = stage.GetPrimAtPath("/assets/chair")
vset = prim.GetVariantSet("material")
vset.SetVariantSelection("wood")
```

## Common Gotchas

1. **Payload vs Reference**: Use payloads for heavy assets, references for lightweight. Payloads can be unloaded; references cannot.

2. **Sublayer order matters**: Later sublayers are stronger. Put overrides after base layers.

3. **Inherit requires class prim**: Target must be defined with `class` keyword.

4. **Variants are local**: Variant sets are per-prim, not global.

## Detailed References

See **composition-deep-dive.md** (shipped alongside) for:
- Arc behavior edge cases
- Nested composition resolution
- Relationship targeting across arcs
- List-editing operations

(The skill's `solaris-workflows.md` and `karma-integration.md` references were NOT shipped - shot-builder and render-delegate material outside BP4-USDKNOW's scope.)
