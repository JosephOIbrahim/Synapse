# Karma Render Cheat-Sheet — Progressive Presets

**What this is.** The four-stage progressive render pipeline, made concrete. Render low and fast, check, then raise. Parts 2–4 of `SYNAPSE_latency_and_karma_rendersettings_2026.md` turned into named presets you can invoke.

**One rule to remember:** anything above the lighting pass renders in **background** so the render doesn't fight the panel for Houdini's main thread. That's not a nicety — it's the operational mitigation for panel latency (addendum Part 3).

---

## Provenance (read this before trusting a name)

Every **parameter name** below was probe-verified against the **live Houdini 22.0.400** build on **2026-08-12** — created the real nodes on the bridge, read `node.parm(...)`, then destroyed them. Names are truth; **values are design choices** from the addendum's tables.

Three names the addendum's prose asserted turned out to be **phantom** on 22.0.400. The probe caught them; the presets ship the real names:

| Addendum prose | Real parm on 22.0.400 |
|---|---|
| `reflectlimit` | **`reflectionlimit`** |
| `refractlimit` | **`refractionlimit`** |
| `denoisemode` | **`denoiser`** (String menu: `off` / `optix` / `oidn`) |

Source of record: `python/synapse/core/render_presets.py` · `harness/notes/receipts/W1-KPRE.json`.

---

## The four presets

| Stage | Resolution | Pixel samples | Engine | Denoise | Render mode | Purpose |
|---|---|---|---|---|---|---|
| **layout** | 320×240 | 4 | xpu | off | **foreground** | Blocking / framing |
| **lighting** | 960×540 | 16–32 *(24)* | xpu | oidn | **foreground** | Light look / exposure |
| **quality** | 1920×1080 | 64 | xpu | oidn | **background** | Lookdev / most shots |
| **final** | 1920×1080+ | 128–512 *(256)* | cpu | off | **background** | Hero finals |

*Italic* values are the default chosen inside the addendum's band; the band travels with the preset (`pixel_samples_range`).

**Pixel samples** is the quality knob — parm `pathtracedsamples` (Int). **Render mode** is parm `soho_foreground`: `1` = foreground (blocks), `0` = background. Quality and final set `soho_foreground=0`.

**Invoke it:** `synapse_render_progressively` with `preset: "quality"` (one stage) or `stages: ["layout","lighting","quality","final"]` (a chain). Omit both and you get the unchanged test/preview/production ladder — the presets are strictly additive.

---

## Engine — XPU vs CPU

```
DEFAULT:  xpu   — 5–20× faster; use for layout, lighting, quality, most shots
CPU when:  hero finals needing reference quality
           full OSL
           nested-dielectric glass
```

Parm `engine` (String menu, tokens `cpu` / `xpu`). The `final` preset defaults to **cpu** because "hero finals" is exactly the reference-quality case; override to `xpu` when you don't need CPU-only features.

**XPU flush delay (not a hang):** Karma XPU flushes image tiles to disk **~10–15s AFTER `render()` returns**. A slow return on an XPU render is the flush finishing — do not treat it as a stall or kill it. This note travels with the preset surface (`XPU_FLUSH_DELAY_NOTE`).

---

## Bounce limits (production baseline)

Every preset applies this baseline. Names probe-verified on `karmarendersettings` + the `karma` ROP; all are Float parms.

```
diffuselimit     2
reflectionlimit  4      (NOT reflectlimit — phantom)
refractionlimit  4      (NOT refractlimit — phantom)
volumelimit      2
ssslimit         2
```

Fewer bounces = faster. Trim `diffuselimit` / `reflectionlimit` first when a shot is slow.

---

## Denoise policy

```
denoiser = oidn   — previews / most shots (lighting, quality). Intel OIDN lets
                    you drop pixel samples and still read clean.
denoiser = off    — hero finals. Render clean, or denoise as a separate pass so
                    the raw data survives.
```

Parm `denoiser` (String menu: `off` / `optix` / `oidn`). OIDN is the production denoiser here.

---

## AOV starter set

Configure via `synapse_configure_render_passes`. Start with:

```
beauty  +  diffuse  +  normal  +  depth  +  crypto_object
```

Add `specular`, `emission`, `sss`, `motionvector` as the shot needs them. The full surface is 9 beauty AOVs + 8 utility AOVs (addendum 2.4).

---

## Resolution & camera (the two easy footguns)

**Resolution** is applied by the existing render path, which sets the right parm per node type — you don't hand-name it. For reference, the probe-verified component names are:

```
karmarendersettings / karma ROP :  resolutionx / resolutiony
usdrender ROP                    :  res_user1 / res_user2   (+ override_res = "specific")
```

**Camera** must be a **USD prim path** on usdrender (`override_camera`, e.g. `/cameras/render_cam`) — never a Houdini node path. The presets deliberately carry **no** camera value: the camera is the artist's, and a preset must never smuggle a node path into it.

---

## Motion blur

```
xformsamples  2      (transform motion samples)
geosamples    2      (geometry deformation motion samples)
```

Both Int, probe-verified. DOF is a per-camera concern (`fStop > 0`), not a render-settings preset value.

---

## Known limitations (stated, not hidden)

- **Preset values are design choices, not measured optima.** The sample counts sit inside the addendum's bands; a specific shot may want more or fewer. The band travels with each preset so you can see the room.
- **`final` defaults to CPU.** That's the reference-quality read of "hero finals." If your final doesn't need OSL / nested glass / CPU reference, XPU is 5–20× faster — override `engine`.
- **The `_apply_karma_advanced_settings` map in the server has its own pre-existing phantom names** (`specularlimit`, `denoise_enable`, `xform_motionsamples`, `geo_motionsamples`) that do not exist on 22.0.400. The presets bypass that map and apply probe-verified names directly, so they are unaffected — but that map is unrelated tech debt worth a separate fix (recorded in the W1-KPRE receipt).
