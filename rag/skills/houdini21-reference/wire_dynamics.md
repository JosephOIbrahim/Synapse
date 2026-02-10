# Wire and Strand Dynamics

## Overview

Wire dynamics simulate flexible linear objects: cables, ropes, chains, tentacles, vines, power lines, hair-like strands. Houdini offers two approaches: DOP Wire Solver and Vellum Hair.

## When to Use Which

| Approach | Best For | Pros | Cons |
|----------|----------|------|------|
| Vellum Hair | Modern workflows, most cases | SOP-based, fast iteration, good collisions | Less direct control over physical params |
| Wire Solver (DOPs) | Legacy, specific physical control | Precise material properties | DOP setup, slower iteration |

**Recommendation**: Use Vellum Hair for most wire/cable work. Use Wire Solver only when you need exact physical material properties.

## Vellum Hair for Wires

### Basic Setup
```
curve_geo -> vellumhair -> vellumsolver -> null
```

### Key Parameters

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Stretch Stiffness | `stretchstiffness` | 10000 | Resistance to stretching |
| Bend Stiffness | `bendstiffness` | 0.1 | Resistance to bending |
| Density | `density` | 1.0 | Mass per length |
| Width | `width` | 0.01 | Wire thickness |

### Wire Material Presets

| Wire Type | Stretch | Bend | Density | Notes |
|-----------|---------|------|---------|-------|
| Thin cable | 50000 | 1.0 | 0.5 | Flexible but holds shape |
| Heavy rope | 100000 | 10.0 | 2.0 | Thick, droops under weight |
| Garden hose | 80000 | 5.0 | 1.0 | Semi-rigid, curls |
| Power line | 200000 | 0.01 | 3.0 | Very taut, minimal bend |
| Vine/tendril | 5000 | 0.05 | 0.3 | Flexible, light |
| Chain | 100000 | 0.0 | 5.0 | No bend resistance, heavy |
| Fishing line | 50000 | 0.001 | 0.01 | Nearly zero bend, very light |

### Pinning Endpoints
```vex
// Wrangle before vellumhair:
// Pin first and last point of each curve
int first = primpoint(0, @primnum, 0);
int last = primpoint(0, @primnum, nvertices(0, @primnum) - 1);
if (@ptnum == first || @ptnum == last) i@stopped = 1;
```

Or use groups:
1. Create point group for endpoints
2. In `vellumhair`, set Pin group to endpoint group

### Attaching to Animated Objects
```
animated_geo -> trail (compute v@v) -> vellumcollider
curve_geo -> vellumhair -> vellumsolver
```
- Connect collider to solver input 2
- Pin wire endpoints to animated geometry using `Attach to Geometry` constraint

## DOP Wire Solver (Legacy)

### Setup
```
curve_geo -> wirecapture -> wireobject DOP -> wiresolver DOP
```

### Key DOP Parameters

| Parameter | Name | Description |
|-----------|------|-------------|
| Linear Density | `lineardensity` | Mass per unit length |
| Stretch Stiffness | `klinear` | Resistance to length change |
| Bend Stiffness | `kangular` | Resistance to angle change |
| Damping | `dampingcoeff` | Motion damping |

## Curve Generation for Wires

### Catenary (hanging cable)
```vex
// Generate catenary curve between two points
// In wrangle on a line SOP (many points):
vector a = chv("start_point");
vector b = chv("end_point");
float sag = ch("sag");  // how much the cable droops

float t = float(@ptnum) / float(@numpt - 1);
@P = lerp(a, b, t);

// Catenary dip (parabolic approximation)
float mid_dip = 4.0 * sag * t * (1.0 - t);
@P.y -= mid_dip;
```

### Spiral/Coil
```vex
// Generate spiral curve
float t = float(@ptnum) / float(@numpt - 1);
float angle = t * ch("turns") * 360;
float radius = ch("radius");
float height = ch("height") * t;
@P = set(cos(radians(angle)) * radius, height, sin(radians(angle)) * radius);
```

### Scatter Curves Between Points
For networks of wires (power lines, spider web):
1. Create connection points (scatter on poles/structures)
2. Use `add` SOP to create polylines between connected points
3. `resample` for even point spacing
4. `vellumhair` to simulate draping

## Rendering Wires

### Karma Curve Rendering
- Curves render natively in Karma as tube primitives
- `@width` attribute controls render-time thickness
- Cross-section: round by default
- For thick rope: increase `@width`, add displacement for texture

### Material
- Cable: dark rubber material (roughness 0.6-0.8, dark base color)
- Rope: fibrous material with bump map for braiding detail
- Chain: metal material (metalness 1.0, roughness 0.3)
- Vine: green organic material with SSS

### Width Variation
```vex
// Taper wire thickness toward tips
float t = float(vertexindex(0, @primnum, @ptnum)) / float(nvertices(0, @primnum) - 1);
f@width = lerp(ch("base_width"), ch("tip_width"), t);
```

## Wind and External Forces

### In Vellum
Add a `vellumconstraintproperty` with "Wind" type:
- `windspeed`: Wind velocity
- `winddirection`: Direction vector
- `dragcoeff`: How much the wire catches wind

### In VEX (inside solver)
```vex
// Custom wind force in solver wrangle
vector wind = chv("wind_direction") * ch("wind_speed");
// Add noise for turbulence
wind += curlnoise(@P * 0.5 + @Time) * ch("turbulence");
v@v += wind * @TimeInc * ch("drag");
```

## Performance Tips

- Resample curves to consistent point count before simulation
- Fewer points per curve = faster sim (20-50 points per cable is enough)
- Use low substeps for preview (2-3), increase for final (5-10)
- Cache results before rendering
- For many wires: simulate guide wires, interpolate rest at render time

## Common Wire Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Wire stretches too much | Stretch stiffness too low | Increase `stretchstiffness` to 100000+ |
| Wire too stiff (doesn't drape) | Bend stiffness too high | Lower `bendstiffness` to 0.01-0.1 |
| Wire vibrates/jitters | Insufficient damping or substeps | Increase damping, increase substeps to 5+ |
| Wire passes through collider | Collision not set up or too few substeps | Add `vellumcollider`, increase substeps |
| Endpoints move (should be fixed) | Missing pin constraint | Set `i@stopped=1` on pinned points |
| Wire invisible in render | Missing `@width` attribute | Set `f@width = 0.01` on curve points |
| Heavy wire doesn't sag enough | Density too low | Increase `density`, lower bend stiffness |
