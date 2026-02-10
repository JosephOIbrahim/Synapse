# Pyro FX Setup Guide

## SOP-Level Pyro Chain

```
source_geo -> scatter -> attribwrangle(emission) -> volumerasterizeattributes -> pyrosolver
```

For import to LOPs: `pyrosolver` -> `filecache` -> `sopimport` LOP

## Source Setup

### Scatter + Wrangle Pattern
```vex
// Source wrangle — run over Points
f@density = 1.0;
f@temperature = 2.0;
f@flame = 1.0;
f@pscale = 0.05;      // REQUIRED for volumerasterize
v@v = set(0, 3, 0);   // upward velocity for rising smoke/fire
```

### Source from Animated Geometry
For fire on a moving object:
1. Use `Trail` SOP to compute `v@v` (velocity) from animated geo
2. Scatter on surface each frame
3. Set `f@density` and `f@temperature` in wrangle
4. The velocity from the trail drives the flame direction

### Source from Curves/Lines
For fire along wires, fuses, trails:
1. Resample curve to even spacing
2. Copy small spheres to curve points
3. Use sphere points as emission source

## Volume Rasterize Setup

- `volumerasterizeattributes` converts point attributes to volume fields
- Set `attributes` parm to: `density temperature flame`
- Input must have scattered points (not raw geometry)
- Points MUST have `@pscale` attribute for volume radius
- `@pscale` controls emission radius: larger = softer, wider source

## Pyro Solver Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Voxel Size | `divsize` | 0.1 | Smaller = more detail, slower |
| Time Scale | `timescale` | 1.0 | Simulation speed |
| Dissipation | `dissipation` | 0.1 | Smoke fade rate |
| Temperature Cooling | `tempcooling` | 0.5 | Flame cooling speed |
| Enable Disturbance | `enable_disturbance` | 0 | Turbulence toggle |
| Disturbance | `disturbance` | 0.5 | Turbulence strength |
| Shredding | `shredding` | 0 | High-frequency breakup |
| Resize Padding | `resize_padding` | 0.3 | Container growth around sim |
| Buoyancy | `buoyancy` | 1.0 | Upward force from temperature |
| Gas Release | `gasrelease` | 0.1 | Container expansion speed |

## Combustion Model

Fire = fuel burning into heat + density:
- `f@fuel` consumed by combustion -> produces `f@temperature` + `f@density`
- `Burn Rate` controls how fast fuel converts
- `Flame Lifespan` controls how long visible flame persists
- Higher `temperature` -> stronger buoyancy -> faster rise

### Tuning Fire vs Smoke

| Look | Dissipation | Temp Cooling | Buoyancy | Disturbance |
|------|-------------|-------------|----------|-------------|
| Campfire | 0.05 | 0.3 | 0.8 | 0.3 |
| Explosion | 0.02 | 0.1 | 2.0 | 0.8 |
| Cigarette smoke | 0.15 | 0.8 | 0.3 | 0.1 |
| Industrial stack | 0.03 | 0.5 | 1.5 | 0.4 |
| Torch | 0.1 | 0.4 | 1.0 | 0.5 |

## Turbulence and Detail

### Disturbance (low frequency)
- `disturbance`: overall strength (0.3-0.8 typical)
- `dist_scale`: spatial frequency of turbulence
- `control_field`: tie disturbance to temperature (fire breaks up more in hot areas)

### Shredding (high frequency)
- `shredding`: strength of small-scale breakup
- Applied AFTER disturbance
- Makes smoke look wispy and detailed

### Curl noise (custom via Gas Wrangle)
For custom turbulence:
```vex
// In a Gas Wrangle DOP inside pyro solver
vector turb = curlnoise(@P * 2.0 + @Time * 0.5);
v@vel += turb * 0.5;
```

## Upresing

For production: simulate at low res, upres for render detail.
1. Simulate with `divsize=0.1` for fast iteration
2. Use `gasupres` microsolver or second pyrosolver with smaller voxels
3. Feed low-res velocity field into high-res container
4. High-res adds turbulence detail without re-simming

## Caching Strategy

Always cache before rendering:
```
pyrosolver -> filecache(file="$HIP/cache/pyro.$F4.bgeo.sc")
```
- Use `.bgeo.sc` (Blosc compressed) for volumes -- 3-5x smaller than raw
- Cache density, temperature, flame, vel fields
- For re-render without re-sim: load from `filecache` in "Read" mode

## Import to Solaris

Use `sopimport` LOP with `soppath` pointing to the pyrosolver or filecache node.
Wire into scene merge.

## Rendering Pyro in Karma

- Karma XPU renders volumes natively. No special setup needed.
- For better quality: increase `volumesteprate` in karmarenderproperties
- Volume step rate 0.25 (default) is fast but noisy; 0.5-1.0 for production
- Increase max samples for volume noise convergence
- Check that density values are reasonable (0.1-5.0 range)

## Common Pyro Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Container clips simulation | Resize padding too low | Increase `resize_padding` to 0.5+ |
| Fire disappears instantly | `tempcooling` too high | Lower to 0.2-0.3 |
| Smoke too uniform | No disturbance/shredding | Enable both, start with 0.3 each |
| Simulation drifts sideways | External velocity or wind | Check source velocity, wind force |
| Voxels visible in render | `divsize` too large | Reduce to 0.03-0.05 for final |
| Memory explosion | `divsize` too small for domain | Start coarse, refine after blocking |
