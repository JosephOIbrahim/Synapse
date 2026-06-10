# Karma XPU Production Setups — Houdini 21 / Solaris
**Authored by SYNAPSE | Training Reference | H21 Confirmed**

---

## Preamble — Confirmed Valid LOP Node Types (H21, this build)

These are **empirically verified** in this H21 session. Do NOT trust knowledge base guesses.

| Purpose | Node Type | Notes |
|---|---|---|
| Geo from USD file | `reference::2.0` | Use `primpath1`, `filepath1` parms |
| Geo from SOPs | `sopcreate` | Internal sopnet is locked — use file SOP inside |
| Material container | `materiallibrary` | Auto-creates `mtlxstandard_surface` + `uv_reader` inside |
| Material assignment | `materiallinker` | Preferred over `assignmaterial` in H21 |
| Camera | `camera` | parms: `resx`, `resy`, `focal`, `aperture`, `fstop` |
| Area/rect light | `light::2.0` | ⚠️ `rectlight` is INVALID — use this versioned name |
| Dome/env light | `domelight::3.0` | ⚠️ `domelight` alone is INVALID — use versioned |
| Distant light | `distantlight::2.0` | ⚠️ Also needs versioned name |
| Render settings | `rendersettings` | USD RenderSettings prim |
| Karma renderer LOP | `karma` | Contains internal `usdrender_rop` + `karmarenderproperties` |
| Live IPR | `liverender` | Contains internal usdrender_rop |
| Merge streams | `merge` | Input 0 = strongest USD opinion |
| Output marker | `null` | Set display flag here at end of chain |
| Render ROP | `usdrender` | In `/out` only; `loppath=/stage`, `camera=/cameras/cam` |

### mtlxstandard_surface parm names (confirmed)
`base_colorr/g/b`, `specular_roughness`, `metalness`, `subsurface`, `subsurface_colorr/g/b`,
`transmission`, `coat`, `coat_roughness`, `emission`, `emission_colorr/g/b`, `opacityr/g/b`

---

## Setup 1 — Hero Product / Lookdev Shot
**Use case:** Single hero asset, 3-point + dome lighting, anamorphic camera, full AOV output.
**Ideal for:** Product viz, character lookdev, asset approval.

```
reference::2.0 (asset)
  → materiallibrary (PBR shader)
    → materiallinker (assign mat to geo)
      → camera (anamorphic spec)
        → light::2.0 (key, 45° above-right, exposure 1.5)
          → light::2.0 (fill, opposite, exposure -0.5 relative)
            → light::2.0 (rim, behind-left, exposure 1.0)
              → domelight::3.0 (HDRI env, exposure 0.25)
                → rendersettings
                  → null OUTPUT ← display flag
```

**Karma XPU ROP** (`/out/karma_rop`, type: `usdrender`):
- `loppath` = `/stage`
- `camera` = `/cameras/phantom_anamorphic_cam`
- Pixel samples: 64–128 for final, 16 for preview
- Enable OIDN denoiser for speed

**Camera — Phantom Flex4K Anamorphic:**
- `resx=4096`, `resy=2160`
- `focal=50`, `aperture=36`, `fstop=2.8`
- `aspectratiox=2.0`, `aspectratioy=1.0` (2x anamorphic squeeze)

---

## Setup 2 — Multi-Asset Environment / Layout Shot
**Use case:** Multiple assets composed via USD, department-layered stage.
**Ideal for:** Set dressing, environment layout, FX integration.

```
reference::2.0 (hero_asset)   reference::2.0 (ground_plane)   reference::2.0 (bg_asset)
       ↓                              ↓                               ↓
    [stream A]                    [stream B]                      [stream C]
         \                            |                            /
          ──────────── merge (input order = USD opinion strength) ─
                                      ↓
                               materiallibrary
                                      ↓
                               materiallinker
                                      ↓
                                   camera
                                      ↓
                           light::2.0 (key)
                                      ↓
                           light::2.0 (fill)
                                      ↓
                          domelight::3.0 (HDRI)
                                      ↓
                             rendersettings
                                      ↓
                               null OUTPUT
```

**Key principle:** `merge` input 0 = strongest USD composition opinion. Put hero asset on input 0.

**USD Hierarchy target:**
```
/World/geo/hero_asset
/World/geo/ground
/World/geo/bg
/World/lights/key_light
/World/cameras/render_cam
/materials/hero_mat
```

---

## Setup 3 — Karma XPU Animation Shot (Motion Blur + AOVs)
**Use case:** Animated sequence, multi-pass EXR output, denoised.
**Ideal for:** Sequence rendering, compositing handoff.

```
sopcreate (animated geo from SOP network)
  → materiallibrary
    → materiallinker
      → camera (with focal length animation)
        → light::2.0 (key)
          → domelight::3.0
            → rendersettings  ← pixel samples 64, motion blur ON
              → karma (LOP)   ← renderer=XPU, AOVs configured here
                → null OUTPUT
```

**Motion blur settings on `rendersettings`:**
- `xformsamples` = 2 (transform motion blur)
- `geosamples` = 2 (deformation blur)
- Shutter: open=-0.25, close=0.25 (centered on frame)

**AOV stack (via `karmastandardrendervars` inside karma LOP):**
- `C` — Beauty (RGBA, half float EXR)
- `diffuse_indirect` + `diffuse_direct`
- `specular_indirect` + `specular_direct`
- `N` — World normal (useful for Nuke relighting)
- `P` — World position
- `depth` — Z-depth for fog/DOF in comp
- `Albedo` — For denoiser training data
- `crypto_object`, `crypto_material` — Cryptomatte IDs

**Karma XPU render quality ladder:**
| Pass | Resolution | Samples | Purpose |
|---|---|---|---|
| Wedge/test | 320×240 | 4 | Quick look |
| Preview | 960×540 | 16 | Director approval |
| Near-final | 1920×1080 | 64 | Comp work |
| Final | 1920×1080 | 128–256 | Delivery |

---

## Setup 4 — Physical Sky / Exterior Lighting
**Use case:** Outdoor scenes with sun/sky model.
**Ideal for:** Arch-viz, exteriors, time-of-day animation.

```
reference::2.0 (environment mesh)
  → materiallibrary
    → materiallinker
      → camera
        → karmaphysicalsky  ← ⚠️ leave primitive path as default /lights/$OS
          → light::2.0 (fill — bounce simulation, low exposure)
            → rendersettings
              → null OUTPUT
```

**⚠️ Known H21 karmaphysicalsky bug:** Changing the primitive path from `/lights/$OS`
detaches the sun direction from the sky model. Leave it default.

**Sun direction:** Controlled via the physical sky's `azimuth` and `elevation` parms.
Time-of-day animation: keyframe `elevation` from sunrise (5°) through noon (90°) to dusk (5°).

---

## Setup 5 — Instanced Scene / Hero + Environment Scatter
**Use case:** High-density instance rendering (foliage, rocks, crowds).
**Ideal for:** Feature film environments, game-ready asset validation.

```
reference::2.0 (hero_asset_prototype)
  → UsdGeomPointInstancer (scatter instances via Python/VEX)
    → materiallibrary (single shared material — instancing-aware)
      → materiallinker
        → camera
          → domelight::3.0 (HDRI)
            → light::2.0 (key)
              → rendersettings  ← enable instanceable flag on prototype prim
                → null OUTPUT
```

**Instancing rule:** Set `instanceable=True` on the prototype prim.
Karma XPU handles GPU-accelerated instance culling natively.

---

## Setup 6 — Lookdev Turntable (TOPS-driven)
**Use case:** Auto-rotating camera for asset review, wedged lighting variants.
**Ideal for:** Asset library generation, client deliverables, training data creation.

```
reference::2.0 (asset)
  → materiallibrary
    → materiallinker
      → camera  ← rotation driven by $F expression: ry = $F * (360/framerange)
        → domelight::3.0 (HDRI — 3 variants via TOPS wedge)
          → light::2.0 (key)
            → rendersettings  ← 48 frames = full 360°
              → null OUTPUT
                        ↓
               /obj/topnet1 — TOPS wedge over HDRI variant
```

**TOPS wedge setup:**
- Wedge attribute: `hdri_path` — 3 HDRI environments
- ROP Fetch: feed `/out/karma_rop`
- Output: `$HIP/render/turntable_v{wedgeindex}.$F4.exr`

---

## Lighting Law (Karma — Always Follow)
```
Intensity = ALWAYS 1.0
Brightness = Exposure only (logarithmic stops)

Key light:   exposure ~ 1.5  (above and 45° to subject)
Fill light:  exposure ~ 0.0  (opposite key, soft)
Rim light:   exposure ~ 1.0  (behind subject, separation)
Dome light:  exposure ~ 0.25 (HDRI env, subtle)
```

Key:Fill ratio 3:1 = 1.585 stops difference.

---

## USD Composition Strength (LIVRPS — memorise this)
```
Local > Inherits > VariantSets > References > Payloads > Sublayers
```
In a `merge` LOP: **input 0 = strongest**. Wire hero geo to input 0.

---

## Common Errors & Fixes

| Error | Cause | Fix |
|---|---|---|
| `rectlight` invalid | Wrong type name | Use `light::2.0` |
| `domelight` invalid | Unversioned name | Use `domelight::3.0` |
| `distantlight` invalid | Unversioned name | Use `distantlight::2.0` |
| `Cannot create node inside locked asset` | sopcreate inner net locked | Use `reference::2.0` + file SOP or keep sopcreate default |
| Black render | Camera path wrong in ROP | Must be USD prim path e.g. `/cameras/cam1` not Houdini path |
| Material not showing | materiallinker not wired | Always wire matlib → materiallinker → rest of chain |
| Render hangs | soho_foreground=0 | Set `soho_foreground=1` on usdrender ROP for sync write |
| XPU slow first frame | Shader compilation | Normal — compiles once then caches for session |
| Physical sky sun detached | Primitive path changed | Leave karmaphysicalsky path as `/lights/$OS` |

---

*Document generated by SYNAPSE | Session: 2026-06-08 | H21.0.671*
