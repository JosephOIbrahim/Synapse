# Ocean FX

## Overview

Houdini's ocean system combines spectral ocean generation with FLIP simulation for close-up interaction. The spectral ocean is infinite and fast; FLIP handles splashes and object interaction.

## Spectral Ocean Chain

For distant/mid-ground ocean without interaction:
```
oceanspectrum -> oceanevaluate -> null (render output)
```

For hero shots with interaction:
```
oceanspectrum -> oceanevaluate -> oceanflat (blend to tank) -> flipsolver (interaction) -> particlefluidsurface
```

## Ocean Spectrum

### oceanspectrum SOP
Generates ocean wave frequency data. This does NOT create geometry -- it creates a volume of wave amplitudes in frequency space.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Resolution | `resolution` | 10 | Grid exponent (2^n, so 10 = 1024x1024) |
| Grid Size | `gridsize` | 100 | Physical size in meters |
| Time | `time` | $T | Animation time |
| Depth | `depth` | 100 | Water depth in meters |
| Speed | `speed` | 10 | Wind speed in m/s |
| Direction | `direction` | 0 | Wind direction in degrees |
| Directional Spread | `spread` | 0.5 | How focused the waves are |
| Chop | `chop` | 0.5 | Wave peakiness (0=round, 1=sharp crests) |
| Seed | `seed` | 0 | Random seed for variation |

### Wave Scale Guidelines

| Sea State | Speed | Depth | Chop | Look |
|-----------|-------|-------|------|------|
| Calm lake | 2-4 | 20 | 0.0 | Gentle ripples |
| Light chop | 6-8 | 50 | 0.3 | Sailboat conditions |
| Moderate sea | 10-15 | 100 | 0.5 | Standard ocean |
| Rough sea | 20-30 | 200 | 0.7 | Storm waves |
| Heavy storm | 30-50 | 500 | 0.9 | Extreme waves, breaking crests |

### Multiple Spectrums
Stack 2-3 oceanspectrum nodes for realistic results:
1. **Primary swell**: Large, slow waves (speed=15, gridsize=500, spread=0.3)
2. **Wind chop**: Medium local waves (speed=8, gridsize=100, spread=0.7)
3. **Ripples**: Small surface detail (speed=3, gridsize=20, spread=0.9)

## Ocean Evaluate

### oceanevaluate SOP
Converts frequency data into actual displaced geometry.

| Parameter | Name | Default | Description |
|-----------|------|---------|-------------|
| Downsample | `downsample` | 0 | Reduce resolution (0=full, 1=half, 2=quarter) |
| Output Type | `outputtype` | Displacement | Surface, Displacement, or Spectrum |

### Generated Attributes
- `@P` -- Displaced position (ocean surface shape)
- `@v` -- Surface velocity (for foam/spray emission)
- `@cusp` -- Wave crest sharpness (for whitewater triggering)
- `@eigenvalues` -- Wave convergence (for foam detection)

## Ocean Surface Shader

Karma ocean rendering:
- **Refraction IOR**: 1.33 (water)
- **Base Color**: Deep blue-green `(0.005, 0.02, 0.03)`
- **Roughness**: 0.0-0.05 (very smooth for calm, slightly rougher for wind)
- **Opacity**: Use depth fade for shallow areas
- **Displacement**: Apply ocean displacement in shader for render-time detail
- **Foam**: Mix white diffuse material where `@cusp > threshold`

## FLIP Integration (Interactive Ocean)

For objects interacting with the ocean surface:

### Setup
```
oceanspectrum -> oceanevaluate -> oceanflat -> flipsolver
```

1. `oceanflat` blends the spectral ocean to a flat tank at the edges
   - `flatradius`: Distance from center where ocean transitions to flat
   - `blendwidth`: Width of the blend zone
   - This creates a "simulation tank" in the center with ocean waves at the boundary

2. Connect the flattened ocean as FLIP source (single frame, fill mode)
3. Add collision objects (ships, rocks, creatures)
4. Simulate FLIP in the tank area
5. Blend FLIP result back to spectral ocean for seamless edges

### Ocean Flat Tips
- Tank must be large enough that FLIP splashes don't reach the blend zone
- `blendwidth` should be at least 2x the largest wave amplitude
- Use narrow band FLIP for efficiency (only surface particles)

## Whitewater on Ocean

```
flipsolver -> whitewatersource -> whitewatersolver
```

Or for spectral-only (no FLIP):
```
oceanevaluate -> whitewatersource (use cusp/eigenvalue) -> whitewatersolver
```

### Emission Sources
- **Cusp**: Wave crests about to break (`@cusp > 0.5`)
- **Eigenvalue**: Areas where wave converges (`@eigenvalues > threshold`)
- **Speed**: Fast-moving water surface
- **Acceleration**: Rapidly changing velocity (impact zones)

### Whitewater Rendering
- **Foam**: Render as flat particles on the surface with alpha from age
- **Spray**: Render as points or tiny sphere instances
- **Mist**: Use very small particles with fog-like shader
- All three types mix together for realistic ocean effects

## Caching Strategy

```
oceanspectrum -> oceanevaluate -> filecache (ocean surface)
flipsolver -> filecache (FLIP particles)
whitewatersolver -> filecache (whitewater)
particlefluidsurface -> filecache (FLIP mesh)
```

- Ocean surface: cache displaced mesh per frame
- FLIP: cache particles and mesh separately
- Whitewater: cache spray/foam/bubble particles separately
- Use `.bgeo.sc` for all caches

## Import to Solaris

1. Spectral ocean: `sopimport` LOP -> ocean displaced mesh
2. FLIP mesh: separate `sopimport` LOP -> assign water material
3. Whitewater: `sopimport` LOP -> point rendering or instanced spheres
4. Merge all in LOPs

## Rendering Ocean in Karma

### Water Material
- IOR 1.33, very low roughness (0.0-0.02)
- Deep absorption color: dark blue-green
- Enable transmission and caustics for transparent shallow water
- Use displacement from ocean evaluate for render-time wave detail

### Foam Material
- White diffuse (albedo ~0.9)
- Mix with water material using `@cusp` or whitewater density
- Opacity from foam age/density attribute

### Environment
- Dome light with HDRI for sky reflection
- Distant light for sun (strong specular on water)
- Exposure: sun at 5-6 stops, dome at 1-2 stops

## Performance Tips

- Use `downsample=1` on oceanevaluate during layout (2x faster)
- Spectral ocean is near-instant to evaluate -- no caching needed for preview
- FLIP interaction: minimize tank size, use narrow band
- Cache everything to SSD (large frame sizes for whitewater)
- Render foam as points, not meshed geometry (much faster)
- Ocean shader: enable max ray depth 4+ for proper water transparency

## Common Ocean Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Ocean looks flat | Wind speed too low | Increase `speed` to 10-15, add chop |
| Waves too uniform | Single spectrum | Stack 2-3 spectrums at different scales |
| FLIP doesn't match ocean | Missing oceanflat blend | Add `oceanflat` to blend spectral to tank |
| Seam at FLIP/ocean edge | Blend zone too narrow | Increase `blendwidth` and `flatradius` |
| No foam/whitewater | Missing cusp emission | Use `@cusp > 0.5` threshold on whitewatersource |
| Render too slow (water) | Too many refraction bounces | Lower specular bounces to 4, use caustics only for hero |
| Ocean tiles visible | Grid size too small | Increase `gridsize` or add second spectrum layer |
