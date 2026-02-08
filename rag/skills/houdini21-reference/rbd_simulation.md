# RBD (Rigid Body) Simulation

## SOP-Level RBD Chain

```
geometry → rbdmaterialfracture → assemble → rigidsolver
```

## Fracture Setup

### rbdmaterialfracture
Voronoi fracture with material-aware cuts:

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Scatter Points | `fracturepoints` | 20 | Number of fracture pieces |
| Min/Max Pts | `minpts`/`maxpts` | 5/100 | Point range per piece |
| Noise | `noise_amp` | 0.0 | Surface noise on cuts |
| Interior Detail | `intdetail` | 0 | Add detail to cut faces |

### assemble
Converts fractured geometry to packed primitives:
- Packs each piece for faster simulation
- Generates `name` attribute per piece

## Rigid Solver Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Substeps | `substeps` | 1 | Collision accuracy |
| Gravity | `gravity` | -9.81 | Gravity magnitude |
| Ground Plane | `groundplane` | 1 | Enable implicit ground |
| Ground Position | `groundpos` | 0 | Ground height |
| Friction | `friction` | 0.5 | Surface friction |
| Bounce | `bounce` | 0.5 | Restitution (bounciness) |

## Constraints

For controlled destruction:
1. `rbdconstraintproperties` — define constraint types
2. `rbdconstraintsfromrules` — auto-generate constraints between pieces
3. Constraint types: `glue` (break threshold), `hinge`, `cone`, `hard`

## Simple Destruction Example

```
box → rbdmaterialfracture(20 pieces) → assemble → rigidsolver
```

Add an animated `sphere` as collision source to trigger breakage.

## Import to Solaris

Use `sopimport` LOP pointing to the `rigidsolver` output.
For large simulations, cache to disk first with `filecache` SOP.

## Performance Tips

- Use packed primitives (assemble node) — 10-100x faster than unpacked
- Start with low fracture count (10-20) for preview
- Cache simulation via `filecache` before Solaris import
- Bullet solver (default) handles thousands of pieces efficiently
