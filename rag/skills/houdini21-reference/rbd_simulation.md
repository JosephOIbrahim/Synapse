# RBD (Rigid Body) Simulation

## SOP-Level RBD Chain

```
geometry -> rbdmaterialfracture -> assemble -> rigidsolver
```

For import to LOPs: `rigidsolver` -> `filecache` -> `sopimport` LOP

## Fracture Setup

### rbdmaterialfracture
Voronoi fracture with material-aware cuts:

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Scatter Points | `fracturepoints` | 20 | Number of fracture pieces |
| Min/Max Pts | `minpts`/`maxpts` | 5/100 | Point range per piece |
| Noise | `noise_amp` | 0.0 | Surface noise on cuts |
| Interior Detail | `intdetail` | 0 | Add detail to cut faces |
| Material Type | `materialtype` | Concrete | Preset fracture patterns |

### Material Type Presets
- **Concrete**: Chunky, irregular pieces
- **Glass**: Sharp, radial fractures
- **Wood**: Splintery, grain-following cracks

### assemble
Converts fractured geometry to packed primitives:
- Packs each piece for faster simulation (10-100x vs unpacked)
- Generates `name` attribute per piece (required for constraints)
- Creates `@P` at center of mass for each piece

## Rigid Solver Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Substeps | `substeps` | 1 | Collision accuracy (2-4 for fast impacts) |
| Gravity | `gravity` | -9.81 | Gravity magnitude |
| Ground Plane | `groundplane` | 1 | Enable implicit ground |
| Ground Position | `groundpos` | 0 | Ground height |
| Friction | `friction` | 0.5 | Surface friction |
| Bounce | `bounce` | 0.5 | Restitution (bounciness) |

## Constraint Networks

For controlled destruction -- pieces hold together until force exceeds threshold.

### Constraint Types
| Type | Use Case | Key Parm |
|------|----------|----------|
| `Glue` | Break on impact (threshold) | `strength` |
| `Hard` | Rigid connection (unbreakable) | -- |
| `Hinge` | Rotate around axis (doors) | `angle_limit` |
| `Cone Twist` | Limited rotation (joints) | `cone_angle` |
| `Soft` | Spring connection (deformable) | `stiffness` |

### Setting Up Constraints
1. `rbdconstraintsfromrules` -- auto-generate by proximity
   - `search_radius`: how far to look for neighboring pieces
   - `max_constraints`: max connections per piece
2. `rbdconstraintproperties` -- define strength and type
   - `constraint_type`: Glue, Hard, Hinge, Cone, Soft
   - `strength`: breaking force threshold (0 = infinite)
3. Connect constraints to solver's constraint input (3rd input)

### Progressive Destruction Pattern
For building collapse or sequential breaking:
```
rbdconstraintsfromrules -> rbdconstraintproperties
    strength based on height: pieces higher up break first
```

```vex
// In constraint wrangle: weaken upper pieces
float height = point(0, "P", @primnum).y;
f@strength = fit(height, 0, 10, 1000, 50);  // weaker at top
```

## Collision Sources

### Animated Colliders
- Use `staticobject` DOP for animated collision geo
- Enable "Deforming" for non-rigid animated meshes
- Use `collision_source` SOP to build VDB collision volume
- VDB collisions are faster and more stable than polygon

### Impact Data
Extract impact information after sim:
```vex
// Read impact force from solver
f@impact = f@impulse;  // force of collision
```
- `i@hittable`: what was hit
- `f@impulse`: collision force magnitude
- Use impact data to trigger effects (dust, sparks, sound)

## Debris and Secondary Effects

### Small Debris Particles
1. Scatter particles on fracture surfaces at frame of impact
2. Use POP solver for lightweight debris
3. Inherit velocity from RBD pieces at impact time
4. Much cheaper than simulating tiny RBD pieces

### Dust from Impact
1. Read impact data from RBD sim
2. Emit pyro source at impact points
3. Scale emission by impact force

## Simple Destruction Example

```
box -> rbdmaterialfracture(20 pieces) -> assemble -> rigidsolver
```

Add an animated `sphere` as collision source to trigger breakage.

## Performance Tips

- Use packed primitives (assemble node) -- 10-100x faster than unpacked
- Start with low fracture count (10-20) for preview
- Cache simulation via `filecache` before Solaris import
- Bullet solver (default) handles thousands of pieces efficiently
- Increase substeps to 2-4 for fast-moving colliders
- Use `Sleeping` to deactivate resting pieces (huge speedup)

## Import to Solaris

Use `sopimport` LOP pointing to the `rigidsolver` output.
For large simulations, cache to disk first with `filecache` SOP.

## Common RBD Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Pieces explode on frame 1 | Overlapping geometry | Add small gap between pieces, increase substeps |
| Pieces pass through floor | No ground plane or too fast | Enable ground plane, increase substeps to 4 |
| Constraints break too easily | Strength too low | Increase `strength` (try 500-1000) |
| Constraints never break | Strength too high or infinite | Lower strength, check impact force range |
| Simulation jitters | Insufficient substeps | Increase to 3-4 substeps |
| Pieces float or drift | Sleeping threshold too aggressive | Lower sleep threshold or disable |
| Slow simulation | Too many active pieces | Enable sleeping, reduce fracture count |
