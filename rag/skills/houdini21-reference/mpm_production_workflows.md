# MPM Production Workflows (Houdini 21)

## Overview

Production-proven MPM setups from the SideFX H21 Masterclass (parts 10-17). Each workflow demonstrates real-world techniques for specific destruction and effects scenarios using the MPM solver.

## Destruction Pipeline (Metal Tearing)

### Close Gaps Mechanism

Per-point level comparison between point-based and piece-based deformation:
- Small delta: snap to point-based (closes gap)
- Large delta: stay piece-based (genuine tear)

| Parameter | Description |
|-----------|-------------|
| Tolerance | Controls aggressiveness of gap closing |
| Transition width | Prevents pops at the threshold boundary |

### Fracture Alignment

- Align Fracture to Stretch: positions fracture centroids at Jp points
- Result: fracture lines follow the natural stress patterns from the MPM sim

### Fast Iteration Trick

Isolate a single piece with `Connectivity` + `Blast` to test fracture behavior:
- Single piece: ~5s sim time
- Full model: 10+ minutes
- Iterate on fracture settings per-piece, then apply to full model

## Slow-Motion Effects (Paintball Impact)

### Scale-Up Workflow

MPM loses precision at small physical scales. Scale up 100x and compensate:

| What | Adjustment |
|------|-----------|
| Geometry | Scale 100x |
| Time scale | Multiply by 100 |
| Gravity | Divide by 100 |

### Shell Setup (Paintball Casing)

| Parameter | Value | Notes |
|-----------|-------|-------|
| Preset | Rubber | Elastic deformation |
| Stiffness | 10x default | Resist initial deformation |
| Type | Surface | Hollow shell, not solid |

### Paint Interior

| Parameter | Value | Notes |
|-----------|-------|-------|
| Preset | Water | Liquid fill |
| Incompressibility | Increased | Prevents volume loss on impact |

### Surface Tension Settings

- Use point-based surface tension method
- Increase min substeps (prevents tunneling at tension boundaries)
- Reduce material condition number
- Set global substeps to 2

### Iteration vs Final Quality

| Setting | Iteration | Final |
|---------|-----------|-------|
| Particle separation multiplier | 2 | 1 |
| Meshing adaptivity | Default | 0 (prevents frame-to-frame topology changes causing color flicker) |

## Multi-Material Organic (Pumpkin Smash)

### Multi-Layer Setup

Each layer gets its own MPM material configuration:

| Layer | Purpose | Notes |
|-------|---------|-------|
| Skin | Outer shell with thickness | Defines break pattern |
| Flesh | Interior fibers | Stringy tearing behavior |
| Seeds | Instanced geometry | Scatter inside, separate collision |

### Point Optimization

| Stage | Point Count | Technique |
|-------|-------------|-----------|
| Initial | 40M | Raw scattered points |
| After fusing | 9M | Reduce overlaps between layers |
| After dedup | 12M (from 14M) | Remove redundant coincident points |

### Decoupled Sourcing

Configure materials on one point set, then transfer attributes to the optimized cloud. This separates material authoring from simulation geometry.

### Velocity Handling for Slow-Motion

| Context | Velocity Treatment |
|---------|-------------------|
| Rendering (motion blur) | Multiply velocity by time scale |
| Debris simulation | Divide velocity by time scale (real-time physics) |

### Post-Simulation

- UV transfer from rest model (pre-sim geometry)
- Depth-based dual-color for interior/exterior distinction
- Mask smooth using Jp (plastic deformation) + curvature
- Set adaptivity to 10x for GPU memory during meshing
- Clamp to first frame for pre-impact visibility (hold mesh static until impact frame)

## Rain and Surface Tension (Car Rain)

### Reverse-Time Raindrop Sync

1. Define impact locations on the car surface
2. Start simulation from impact frame
3. Backtrack particles to emission height using reversed velocity
4. Flip time and velocity for final render

This guarantees raindrops hit exactly where art direction requires.

### Pre-Modeled Crown Splashes

- Manually shape crown geometry for art-directable splashes
- Feed shaped geometry into MPM as initial conditions
- MPM handles post-impact dynamics (secondary droplets, flow)

### IOR Distance Correction

Air gaps between water mesh and car surface cause bright refraction artifacts:

| Distance to Collider | IOR Value | Effect |
|----------------------|-----------|--------|
| Near (touching) | 1.0 | Transparent, no refraction |
| Far (separated) | 1.33 | Full water refraction |

Compute distance-to-collider attribute and remap IOR accordingly.

### Key Settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| Surface tension | Strong | Holds droplets together |
| Substeps | Increased | Stability with high tension |
| Collision method | Particle-level | Better thin-film behavior |
| Collision detection distance | > 1 | Lets water gather at edges and seams |

### Secondary Effects (Non-MPM)

| Effect | Method |
|--------|--------|
| Mist | POP simulation |
| Condensation | SOP solver |
| Dynamic puddles | Ripple solver |

## Snow Interaction (Wolf in Snow)

### Camera-Frustum Optimization

1. Trail character paths through the shot
2. Clip trail to camera frustum
3. Bake clipped region to VDB
4. Only fill VDB region with MPM particles

### Depth-Based Volume Reduction

Lerp between full depth (where paw penetration occurs) and reduced depth (surface-only snow). Saves particles in areas that only need surface displacement.

### Auto Sleep

At peak, 98% of particles are passive (sleeping). Raise the velocity threshold for sleep activation to let particles settle faster.

| Metric | Value |
|--------|-------|
| Active at peak | ~2% |
| Passive at peak | ~98% |
| Debug attribute | `state` (detail string: active/passive/boundary percentages) |

### Stiffness Noise for Natural Fracture

- Increase base stiffness
- Multiply by noise field remapped to [2, 5] range
- Creates natural fracture boundaries where stiffness transitions occur

### Surface Mask

Multiply density grid by snow SDF to preserve structure and granularity at the surface while reducing interior particle count.

## Multi-Resolution Pipeline (Creature Breach)

### Two-Pass Strategy

| Pass | Separation | Particles | Purpose |
|------|-----------|-----------|---------|
| Low-res | 0.11 | Fewer | Identify fracture regions via Jp |
| High-res | 0.06 | 8x more | Detail in dynamic patch only |

### Workflow

1. Run low-res pass, identify fracture regions where Jp indicates plastic deformation
2. Non-fractured points become static colliders for the high-res pass
3. High-res pass fills only the dynamic patch region
4. Low-res geometry serves as animated deforming collider with very high friction and stickiness (hides resolution mismatch at boundaries)

### Velocity Clamping

Enforce max velocity in VEX: clamp displacement per frame to 0.25 units. Prevents explosion artifacts at resolution boundaries.

### Narrow-Band Render Cloud

| Stage | Point Count | Technique |
|-------|-------------|-----------|
| Initial fill | 166M | Fill at 0.04 separation |
| After erosion | 88M | 1 dilation, 1 smooth, 4 erosion passes |
| Full volume (avoided) | ~1B | Would be prohibitively expensive |

### Retargeting

Orient-based retargeting: capture to nearest MPM particle at rest position. Add noise to break Voronoi artifacts at capture boundaries.

## Large-Scale Metal (Train Wreck)

### Surface Scatter Mode

Use particles only on mesh surfaces for thin-walled metal objects. No need to fill interior volume for sheet metal.

### Compression Hardening

Augment metal material with compression hardening to promote tearing behavior over bending. Metal panels should rip apart, not deform like rubber.

### Varying Friction VDB

Per-point friction attribute baked to a VDB grid:

| Surface | Friction Value |
|---------|---------------|
| Rails | 0.5 |
| Ground | 1.25 |

### Consistent Point Count

Freeze deleted particles at their last known position instead of removing them. Required for retargeting compatibility -- point indices must remain stable across frames.

### Close Gaps

Same mechanism as the destruction pipeline: fills unnatural cracks between metal panels that occur during tearing.

### Debris Rolling Rotation

| Setting | Value | Notes |
|---------|-------|-------|
| Rotation axis | Perpendicular to velocity | Natural tumbling |
| Angular velocity | Perimeter-based | Larger debris rotates slower |
| Damping | 0.25 | Prevents infinite spinning |
| Storage attribute | Custom (not `w`) | Prevents POP solver override |

## Structural Destruction (Building Attack)

### Making Models Destruction-Ready

1. Fuse edges (remove tiny gaps in architectural models)
2. VDB-close remaining gaps (watertight geometry)
3. Add internal pillars (structural supports that fracture realistically)
4. Transfer UVs after cleanup

### Staggered Projectile Emission

1. Define hit locations and frames per projectile
2. Backtrack each projectile using velocity + gravity to find emission position
3. Emit at calculated positions so impacts land precisely on target

### Critical Setting

Disable "Assume Unchanging Material Properties" when emitting stiffer materials mid-simulation. Failing to do this causes the solver to use incorrect material properties for late-emitted particles.

### Consistent Point Count with Emission

Backward-solve from the frame when all particles exist. This ensures stable point counts for retargeting even with staggered emission.

### Vibration Damping

Lerp building points between frame 1 position and the last stable pre-impact frame. Removes solver-induced vibration in undamaged portions of the structure.

### Memory-Efficient Filler Points

Set max distance for filler points to restrict them to fracture lines only. For large buildings, filling the entire volume is prohibitively expensive.

### Per-Projectile Fracture

Use a unique fracture namespace per projectile with loop iteration suffix. Prevents fracture patterns from interfering across different impact zones.

## Cross-Workflow Production Patterns

| Pattern | Where Used | Description |
|---------|-----------|-------------|
| Scale-up for precision | Paintball, Car Rain | 100x scale, compensate time and gravity |
| Multi-resolution | Creature Breach | Low-res pass identifies fracture, high-res adds detail |
| Consistent point count | Train, Building | Freeze deleted particles for retargeting |
| Velocity tracking | Pumpkin, Paintball | Real-time velocity for debris, scaled for render motion blur |
| Close Gaps | Train, Destruction | Fills unnatural metal cracks between panels |
| Stiffness noise | Wolf, Building | Noise-driven stiffness creates natural fracture boundaries |
| Camera frustum culling | Wolf | Only simulate the visible region |
| Friction VDB | Train, Car Rain | Spatially varying friction via VDB grid |

## Performance Budgets

| Scene Type | Typical Particle Count | Sim Time | Key Optimization |
|------------|----------------------|----------|------------------|
| Small-scale (paintball) | 1-5M | Minutes | Scale up, reduce separation multiplier |
| Character interaction (wolf) | 10-50M | Hours | Auto sleep (98% passive) |
| Vehicle destruction (train) | 5-20M | Hours | Surface scatter, varying friction |
| Large structure (building) | 20-100M+ | Hours to days | Multi-res, staggered emission |
| Creature breach | 88-166M render | Hours | Narrow-band erosion, multi-res |
