# Recipe: 3-Point Light Rig
**Category:** Lighting / Solaris  
**Renderer:** Karma XPU / Karma CPU  
**Context:** `/stage` (LOP network)  
**Status:** Verified working — H21, 2026-06-01

---

## What This Builds

Classic key/fill/rim lighting setup in Solaris using `light` LOP nodes with `UsdLuxRectLight` type. All three lights use:
- **Intensity locked at 1.0** (Lighting Law)
- **Brightness controlled by exposure** (logarithmic stops)
- **Color Temperature** for warm/cool separation
- **Rect area lights** for soft, controllable shadows

---

## The Rig

```
[existing chain tail]
        │
   [key_light]      ← 45° camera-left / up, warm 5600K, exposure +1.0
        │
   [fill_light]     ← camera-right / low, cool 6500K, exposure -0.585 (3:1 ratio)
        │
   [rim_light]      ← behind subject, cool blue 7500K, exposure +1.5
        │
   [LIGHTS_OUT]     ← null, display flag set
```

---

## Light Specifications

### Key Light — `key_light`
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Type | UsdLuxRectLight | Soft area light |
| Position | (-3, 3, 3) | Camera-left, elevated, forward |
| Rotation | (-35°, +35°, 0°) | Angled down toward subject |
| Exposure | +1.0 | Brightest light in the rig |
| Color Temp | 5600K | Warm neutral daylight |
| Size | 1.5 × 1.5 | Moderate softness |

### Fill Light — `fill_light`
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Type | UsdLuxRectLight | Soft area light |
| Position | (3.5, 1, 2.5) | Camera-right, lower than key |
| Rotation | (-10°, -40°, 0°) | Gentle angle into subject |
| Exposure | -0.585 | 3:1 key-to-fill ratio |
| Color Temp | 6500K | Slightly cooler than key |
| Size | 2.5 × 2.5 | Larger = softer fill |

> **3:1 ratio math:** Key exposure 1.0, fill -0.585 stops = key is ~3× brighter than fill. This gives clear but not harsh shadow side. Increase ratio (lower fill exposure) for drama. Decrease for flat/beauty work.

### Rim Light — `rim_light`
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Type | UsdLuxRectLight | Area light |
| Position | (2, 2.5, -4) | Behind subject, camera-right |
| Rotation | (-20°, -145°, 0°) | Faces forward (back-lighting subject) |
| Exposure | +1.5 | Punchy — rims need to cut |
| Color Temp | 7500K | Cool blue separation |
| Size | 0.8 × 1.2 | Narrow for crisp edge highlight |

---

## Key Decisions

### Why `light` LOP, not `rectlight`?
The `rectlight` node type doesn't exist in H21 LOP catalogue. Use `light` LOP and set `lighttype` to `UsdLuxRectLight`.

**Valid `lighttype` menu values:**
- `UsdLuxRectLight` — Rectangle (area)
- `UsdLuxSphereLight` — Sphere (area)
- `UsdLuxDiskLight` — Disk (area)
- `UsdLuxDistantLight` — Distant/Sun (directional)
- `UsdLuxCylinderLight` — Cylinder
- `point` — Point light

### Why Color Temperature, not manual color?
Color temperature is physically based and produces natural warm/cool shifts without saturation artifacts. Toggle on with `xn__inputsenableColorTemperature_omb = 1`.

### Why exposure over intensity?
Exposure is logarithmic (stops), matching photographic intuition. A 1-stop change doubles/halves perceived brightness. Intensity is linear and harder to reason about.

---

## Encoded Parameter Names (light LOP)

| Human name | Encoded parm name |
|------------|-------------------|
| intensity | `xn__inputsintensity_i0a` |
| exposure | `xn__inputsexposure_vya` |
| enableColorTemperature | `xn__inputsenableColorTemperature_omb` |
| colorTemperature | `xn__inputscolorTemperature_wcb` |
| width | `xn__inputswidth_zta` |
| height | `xn__inputsheight_mva` |
| radius | `xn__inputsradius_mva` |
| color R/G/B | `xn__inputscolor_ztar` / `_ztag` / `_ztab` |

---

## Python Build Script

```python
import hou

stage = hou.node('/stage')
tail = [n for n in stage.children() if n.isDisplayFlagSet()][0]

# KEY LIGHT
key = stage.createNode('light', 'key_light')
key.setInput(0, tail)
key.parm('lighttype').set('UsdLuxRectLight')
key.parm('tx').set(-3.0);  key.parm('ty').set(3.0);  key.parm('tz').set(3.0)
key.parm('rx').set(-35.0); key.parm('ry').set(35.0)
key.parm('xn__inputsintensity_i0a').set(1.0)
key.parm('xn__inputsexposure_vya').set(1.0)
key.parm('xn__inputsenableColorTemperature_omb').set(1)
key.parm('xn__inputscolorTemperature_wcb').set(5600)
key.parm('xn__inputswidth_zta').set(1.5)
key.parm('xn__inputsheight_mva').set(1.5)

# FILL LIGHT
fill = stage.createNode('light', 'fill_light')
fill.setInput(0, key)
fill.parm('lighttype').set('UsdLuxRectLight')
fill.parm('tx').set(3.5);  fill.parm('ty').set(1.0);  fill.parm('tz').set(2.5)
fill.parm('rx').set(-10.0); fill.parm('ry').set(-40.0)
fill.parm('xn__inputsintensity_i0a').set(1.0)
fill.parm('xn__inputsexposure_vya').set(-0.585)
fill.parm('xn__inputsenableColorTemperature_omb').set(1)
fill.parm('xn__inputscolorTemperature_wcb').set(6500)
fill.parm('xn__inputswidth_zta').set(2.5)
fill.parm('xn__inputsheight_mva').set(2.5)

# RIM LIGHT
rim = stage.createNode('light', 'rim_light')
rim.setInput(0, fill)
rim.parm('lighttype').set('UsdLuxRectLight')
rim.parm('tx').set(2.0);  rim.parm('ty').set(2.5);  rim.parm('tz').set(-4.0)
rim.parm('rx').set(-20.0); rim.parm('ry').set(-145.0)
rim.parm('xn__inputsintensity_i0a').set(1.0)
rim.parm('xn__inputsexposure_vya').set(1.5)
rim.parm('xn__inputsenableColorTemperature_omb').set(1)
rim.parm('xn__inputscolorTemperature_wcb').set(7500)
rim.parm('xn__inputswidth_zta').set(0.8)
rim.parm('xn__inputsheight_mva').set(1.2)

# OUTPUT
out = stage.createNode('null', 'LIGHTS_OUT')
out.setInput(0, rim)
out.setDisplayFlag(True)
stage.layoutChildren()
```

---

## Tuning Guide

| Goal | Adjustment |
|------|-----------|
| More dramatic | Lower fill exposure (e.g. -1.5 to -2.0) |
| Softer / beauty | Raise fill exposure (e.g. 0.0 to +0.5) |
| Warmer overall | Key temp → 4200K (tungsten), fill → 5600K |
| Colder / moonlight | Key temp → 8000K, rim → 10000K |
| Tighter rim | Reduce rim width/height (e.g. 0.4 × 0.8) |
| Wrap the subject | Increase fill and rim light sizes |
| No rim | Delete rim_light, rewire fill → LIGHTS_OUT |

---

## Common Issues

**Light not visible in render**  
→ Ensure the light LOP is wired into the chain. Floating nodes don't contribute to the stage.

**"Invalid menu item" on `lighttype`**  
→ Use `UsdLuxRectLight` not `rect`. Full list of valid values in the table above.

**`rectlight` node type not found**  
→ H21 doesn't expose `rectlight` as a standalone LOP. Use `light` LOP + set `lighttype`.

**Lights too bright / too dark**  
→ All intensity = 1.0 always. Only adjust `exposure`. Viewport and Karma XPU respond differently — trust Karma.

---
*Recipe verified by SYNAPSE v4.0.0 — Houdini 21*
