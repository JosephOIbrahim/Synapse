# Temporal Coherence in Animation Rendering

## Overview
Temporal coherence = visual consistency between frames. Flickering, swimming textures, popping geometry, and inconsistent noise all break the illusion of continuous motion. This reference covers prevention techniques across the Houdini/Karma pipeline.

## Common Temporal Artifacts

| Artifact | Cause | Fix |
|----------|-------|-----|
| Noise flickering | Insufficient samples | Increase pixel samples (64+ for denoiser input) |
| Texture swimming | UV-dependent noise without temporal seed | Lock noise to world space or use rest position |
| Geometry popping | Adaptive mesh changing topology per frame | Set adaptivity to 0 or use consistent topology |
| Shadow flickering | Undersampled area lights | Increase light samples or light size |
| Firefly persistence | Single bright pixel persists across frames | Clamp indirect intensity, increase roughness floor |
| Denoiser smearing | Temporal denoiser over-smoothing motion | Provide accurate motion vectors, increase base samples |
| LOD transitions | Abrupt detail changes between frames | Use smooth LOD transitions with overlap range |
| Volume flickering | Insufficient volume step rate | Increase step rate to 0.25+ for production |

## Noise and Sampling
- Karma uses stratified sampling with blue-noise distribution
- Temporal stability improves with higher base samples regardless of denoiser
- Minimum 64 pixel samples before denoising for animation
- Variance-based convergence (`pixeloracle: variance`) adapts per-pixel -- regions with motion get more samples

## Denoising for Animation

### Intel OIDN
- Frame-by-frame denoising (no temporal component)
- Relies on high base samples for frame-to-frame consistency
- Auxiliary AOVs (albedo, normal) improve edge preservation
- Safe for production -- no temporal artifacts introduced

### NVIDIA OptiX
- GPU-accelerated denoising
- Also frame-by-frame in Karma
- Slightly different noise pattern than OIDN -- pick one and stay consistent per sequence

### Best Practices
- Denoise beauty pass only, NOT utility AOVs (depth, normal, cryptomatte)
- Higher base samples (64-128) + denoise > lower samples (16-32) + heavy denoise
- Consistent denoiser across entire sequence (don't switch mid-shot)
- Test on 10-frame range before committing to full sequence

## Texture and Shading Stability
- Use `rest` position attribute for procedural noise (locks to object space)
- Avoid `@P` for noise input on deforming geometry -- use rest or UV
- MaterialX noise nodes: connect `rest` to position input
- Displacement: use consistent subdivision level per frame (not adaptive)
- Bump mapping: test at animation speed, not single frame

## Geometry Consistency
- MPM Surface: set adaptivity=0 for animation (prevents topology changes)
- Fluid meshing: consistent voxel size across frames
- Adaptive subdivision: lock to fixed level for animation sequences
- Hair/fur: consistent strand count per frame (avoid per-frame regrowth)
- Point instancing: stable instance IDs across frames

## Motion Blur
- Essential for temporal coherence at 24fps
- Transform motion blur: `xformsamples` = 2 (minimum for linear motion)
- Deformation motion blur: `geosamples` = 2-3 (for deforming geometry)
- Velocity-based blur: requires `v` (velocity) attribute on geometry
- Shutter: centered (-0.5 to 0.5) or trailing (0.0 to 1.0) -- pick one per project
- Disable motion blur for debug renders (see actual frame content)

## Volume Rendering Stability
- Volume step rate: 0.25 minimum for production animation
- Consistent VDB voxel size across frame range
- Shadow step rate can be coarser (0.5) but must also be consistent
- Pyro: cache with consistent grid bounds to prevent step-rate aliasing

## Render Settings for Animation Consistency

| Setting | Single Frame | Animation |
|---------|-------------|-----------|
| Pixel samples | 32-64 | 64-128 |
| Convergence | Variance | Variance (higher threshold) |
| Diffuse bounces | 2-4 | 4 (consistent) |
| Volume step rate | 0.1-0.25 | 0.25 (minimum) |
| Denoiser | Optional | Recommended (same across sequence) |
| Motion blur | Off for stills | On (essential) |
| Adaptivity | Fine for stills | 0 for meshed fluids |

## Validation Workflow
1. Render 3 consecutive frames (e.g., 48, 49, 50)
2. Flip between them rapidly in MPlay or viewer
3. Check for: noise pattern changes, texture swimming, geometry pops, shadow flicker
4. If flickering detected: increase samples in the artifact region
5. Render 10-frame range, encode to video, review at realtime speed
6. Only commit to full sequence after passing 10-frame validation
