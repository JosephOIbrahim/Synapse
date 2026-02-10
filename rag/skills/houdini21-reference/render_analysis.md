# Render Analysis Guide

## Overview

Analyzing renders is essential for iterating toward production quality. This guide covers what to look for when evaluating lighting, exposure, composition, noise, and material quality in Karma renders.

## Exposure Analysis

### Key Metrics
- **Overall brightness**: Is the image correctly exposed? Not too dark (crushed shadows) or too bright (blown highlights)?
- **Key:fill ratio**: Is the contrast between lit and shadow sides appropriate for the mood?
- **Highlight clipping**: Are specular highlights pure white (clipped) or retaining detail?
- **Shadow detail**: Can you see detail in the darkest areas?

### Exposure Adjustment via Synapse

All adjustments use **exposure** (stops), never intensity:
```
# Too dark overall: increase key light exposure
set_parm(node="/stage/key_light", parm="exposure", value=6.0)

# Fill too weak (harsh shadows): increase fill exposure
set_parm(node="/stage/fill_light", parm="exposure", value=4.0)

# Too bright overall: decrease dome/environment exposure
set_parm(node="/stage/dome_light", parm="exposure", value=-1.0)
```

### Stop Math Quick Reference
| Change | Effect |
|--------|--------|
| +1 stop | 2x brighter |
| -1 stop | 0.5x brightness |
| +2 stops | 4x brighter |
| -2 stops | 0.25x brightness |
| +0.5 stop | ~1.4x brighter |

## Noise Analysis

### Types of Render Noise
| Noise Type | Appearance | Fix |
|-----------|------------|-----|
| General noise | Grain across image | Increase max samples (128 -> 256) |
| Shadow noise | Noisy in dark areas | Increase min samples, use variance oracle |
| Specular noise | Fireflies on reflective surfaces | Enable clamping, increase specular bounces |
| Volume noise | Grain in smoke/fog | Increase volume step rate (0.5 -> 1.0) |
| Caustic noise | Bright speckles through glass | Enable caustics with higher samples, or disable caustics |

### Sample Settings for Noise Reduction
```
# Preview (fast, noisy)
render_settings(node="/stage/karmarenderproperties1", settings={
    "karma:global:pathtracedsamples": 32,
    "karma:global:pixeloracle": "uniform"
})

# Production (clean)
render_settings(node="/stage/karmarenderproperties1", settings={
    "karma:global:pathtracedsamples": 256,
    "karma:global:minpathtracedsamples": 16,
    "karma:global:pixeloracle": "variance",
    "karma:global:convergencethreshold": 0.005
})
```

### Denoising
For faster clean results:
- Enable built-in OIDN denoiser: `karma:global:enabledenoise = 1`
- Requires `denoise_albedo` and `denoise_normal` AOVs
- Denoiser works best on 64+ samples
- For animation: temporal denoising reduces flickering

## Lighting Composition

### Three-Point Lighting Check
1. **Key light**: Dominant light source, defines shadow direction. Should be brightest.
2. **Fill light**: Softens shadows on opposite side. Should be 1.5-3 stops below key.
3. **Rim/back light**: Separates subject from background. Similar to key exposure.

### Common Lighting Issues
| Issue | Visual Sign | Fix |
|-------|------------|-----|
| Flat lighting | No shadows, uniform brightness | Increase key:fill ratio (3:1 or higher) |
| Harsh lighting | Deep black shadows | Add fill light, raise fill exposure |
| No depth separation | Subject blends with background | Add rim light, adjust exposure |
| Hot spots | Blown white areas | Lower light exposure, check intensity=1.0 |
| Wrong mood | Too bright for dramatic scene | Increase key:fill ratio, lower env exposure |
| Color cast | Unwanted color tint | Check light colors, environment HDRI white balance |

### Lighting by Scenario
| Scenario | Key:Fill Ratio | Env Exposure | Mood |
|----------|---------------|--------------|------|
| Product beauty | 2:1 | 1.0 | Clean, inviting |
| Broadcast | 3:1 | 1.0 | Professional, clear |
| Dramatic | 4:1 | 0.0 | Moody, cinematic |
| Horror/noir | 8:1+ | -1.0 | Dark, tense |
| Overcast | 1.5:1 | 2.0 | Soft, natural |

## Material Quality

### What to Check
- **Roughness range**: Pure 0.0 roughness causes fireflies. Use 0.001 minimum.
- **Metalness**: Should be 0.0 (dielectric) or 1.0 (metal). Avoid 0.3-0.7 range (physically incorrect).
- **Base color value**: Metals have colored specular, not colored diffuse. Dark diffuse + high metalness = correct metal.
- **Fresnel**: At grazing angles, all materials become more reflective. If edges look wrong, check IOR.

### Common Material Issues
| Issue | Visual Sign | Fix |
|-------|------------|-----|
| Plastic look | Too uniform specular | Add roughness variation via texture |
| Fireflies | Bright pixel artifacts | Set roughness minimum 0.001, lower max specular bounces |
| Black metal | Metal with no reflection | Add environment light (dome light) for reflections |
| Glowing edges | Incorrect fresnel/IOR | Check material IOR setting, verify normal direction |
| Flat surface | No micro-detail | Add roughness map, displacement, or bump map |

## Composition Analysis

### Rule of Thirds
- Key subjects should align with 1/3 grid lines
- Camera focal point at intersection of thirds
- Negative space on opposite side of subject

### Depth Cues
- **Atmospheric perspective**: Distant objects slightly hazier (volume fog)
- **DOF**: Shallow depth of field draws focus (lower fStop value)
- **Scale reference**: Include recognizable objects for scale
- **Occlusion**: Foreground elements overlapping background adds depth

## Iteration Workflow

### Fast Iteration (Layout/Blocking)
1. Render at 640x360 with 16 samples, uniform oracle
2. Check composition, lighting direction, overall exposure
3. Adjust light positions and exposures
4. Re-render until composition reads well

### Quality Iteration (Lookdev)
1. Render at 1280x720 with 64 samples, variance oracle
2. Check material quality, noise, color
3. Adjust materials, add detail textures
4. Enable denoiser for quick clean preview

### Final Quality
1. Render at full resolution with 256+ samples
2. Enable all AOVs for compositing
3. Verify no clipping, noise, or artifacts
4. Export EXR with AOVs for post-production

## Render-Analyze-Adjust Loop

The most productive workflow with Synapse:
1. **Render**: Use `houdini_render` at preview quality
2. **Analyze**: Look at the returned image — check exposure, noise, composition
3. **Adjust**: Modify light exposure, camera position, material properties
4. **Re-render**: Verify the adjustment improved the image
5. **Iterate**: Repeat until satisfied, then render at final quality
