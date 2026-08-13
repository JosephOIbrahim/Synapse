# SYNAPSE Latency Profile + Karma CPU/XPU Render Settings — Production Addendum

**Date:** 2026-08-12
**Companion to:** `SYNAPSE_production_readiness_report_2026.md`
**Grounding:** live `synapse_metrics` + `synapse_doctor` + Karma rendering reference

---

## Part 1 — Latency Profile (measured, not estimated)

All numbers below are from the live Prometheus metrics captured this session. They are the real cost of SYNAPSE's round-trips and main-thread work.

### 1.1 Tool-call latency (the "round-trip" cost)
Measured per-tool durations (sum / count → average):
```
context       20.8ms / 1   → ~21ms
get_health    68.6ms / 1   → ~69ms
memory_status 45.0ms / 1   → ~45ms
```
These are the **handler-thread** costs — the actual Houdini mutation work. They are small. **The latency problem is NOT the Houdini op; it is the round-trip and the main-thread path.**

### 1.2 Dispatch wait (enqueue → start on main thread)
```
dispatch_wait_ms: 91 samples, max 306ms, sum 5058ms
```
Average ~55ms, but the **tail is 306ms**. On a busy scene with heavy cooks, the main thread is busy and SYNAPSE waits. This is where "the tool feels slow" comes from — not the op, the queue.

### 1.3 Main-thread holds (the real stall risk)
```
main_thread_hold_ms: 91 samples, max 648ms (label: synapse_doctor)
main_thread_hold_slowest_ms{synapse_doctor} = 648.3ms
```
**A single diagnostic call held the main thread for 648ms.** For an artist in a flow state, that is a perceptible freeze — the viewport stutters mid-interaction. The doctor is the worst offender because it does a lot of I/O (log file, telemetry, bridge, symbol table).

### 1.4 Panel result path (the UI cost)
```
panel_result_ms_sum{phase="append"}   648.6ms  (slow: 1)
panel_result_ms_sum{phase="finalize"} 780.2ms  (slow: 1)
panel_result_ms_sum{phase="review"}    31.5ms
panel_result_ms_sum{phase="send"}       2.6ms
panel_result_ms_sum{phase="stream"}   178.6ms  (142 samples, max 164ms)
```
**append (648ms) and finalize (780ms) both exceed the slow threshold.** Streaming is fine (max 164ms). The cost is in assembling and finalizing the result document on the main thread.

### 1.5 Latency verdict
| Phase | Typical | Tail | Production impact |
|---|---|---|---|
| Tool op (handler) | 20–70ms | — | Negligible |
| Dispatch wait | ~55ms | 306ms | Perceptible on busy scenes |
| Main-thread hold | — | **648ms** | **Viewport freeze** |
| Panel append/finalize | — | **780ms** | **UI stall** |

**Bottom line:** The Houdini operations are fast. The latency is dominated by (a) main-thread holds and (b) panel result assembly — both of which stall the artist. **Fix these two and the tool feels instant.**

### 1.6 Latency recommendations
1. **Move panel append/finalize off the main thread** (or make them incremental/streaming). This is the single biggest latency win.
2. **Profile the 648ms doctor hold** — a diagnostic should never block the main thread for 0.6s. Defer heavy I/O to a worker thread.
3. **Add a main-thread budget** with a visible "working" indicator, so a stall reads as "tool is working" not "Houdini hung."
4. **Batch aggressively** (the tool already prefers one coarse call over N granular ones — keep that discipline; each round-trip is ~55ms+ of dispatch wait).

---

## Part 2 — Karma CPU vs XPU Render Settings

### 2.1 Engine choice — the 30-second version
| | **Karma XPU** | **Karma CPU** |
|---|---|---|
| Hardware | GPU + CPU hybrid | CPU only |
| Speed | **5–20× faster** | Reference quality |
| Default? | **Yes — use for almost all work** | No — use for finals/reference |
| OSL | Limited | **Full OSL support** |
| Nested dielectrics | Limited | **Full support** |
| Best for | Lookdev, iteration, most shots | Hero finals, complex glass/volumes |

**Rule of thumb:** XPU for everything except (a) hero final frames needing reference quality, (b) scenes that need full OSL, (c) nested-dielectric glass. CPU is the safety net, not the default.

### 2.2 Core render settings (the ones that matter)
The key quality knob is **pixel samples** — the Karma parameter is `karma:global:pathtracedsamples` (the "Pixel Samples" field on the Karma Render Settings node).

**Progressive pipeline** (the production workflow — render low, check, then raise):
| Stage | Resolution | Pixel samples | Purpose |
|---|---|---|---|
| 1 — Layout | 320×240 | 4 | Blocking, framing |
| 2 — Lighting | 960×540 | 16–32 | Light look, exposure |
| 3 — Quality | 1920×1080 | 64 | Lookdev, most shots |
| 4 — Final | 1920×1080+ | 128–512 | Hero finals |

**Bounce limits** (per-bounce quality control):
- `diffuselimit` — diffuse bounces (default ~2)
- `reflectlimit` — specular/reflection bounces
- `refractlimit` — transmission/refraction bounces
- `volumelimit` — volume bounces
- `ssslimit` — subsurface scattering bounces

**Convergence mode** — use convergence-based rendering (with a pixel oracle) instead of fixed samples when you want the renderer to stop when clean, saving time on easy areas.

### 2.3 Denoising
- **Intel OIDN** (`denoisemode='oidn'`) is the production denoiser.
- Use it for **previews and most shots** — it lets you drop pixel samples and still get clean results.
- For **hero finals**, render clean (no denoise) or denoise as a separate pass so you keep the raw data.

### 2.4 AOVs (render passes)
- **9 beauty AOVs:** C (beauty), direct/indirect diffuse, direct/indirect specular, emission, SSS, direct/indirect volume.
- **8 utility AOVs:** N (normal), P (position), depth, Albedo, motionvector, crypto_material/object/asset.
- Configure via `synapse_configure_render_passes` (e.g. `['beauty','diffuse','normal','crypto_object']`).

### 2.5 Camera & motion
- **DOF:** `fStop > 0` on the camera enables depth of field.
- **Motion blur:** `xformsamples` (transform) + `geosamples` (geometry) control motion-blur quality.

### 2.6 Volume rendering
- **Step rate** and **shadow step rate** control volume quality vs. speed. Lower step rate = finer, slower.

### 2.7 ROP setup specifics
- **Karma ROP** (`/out/karma`): direct driver with `picture`, `camera`, and `engine` (xpu/cpu) parms.
- **USD Render ROP** (`/out/usdrender`): USD-based with `loppath`, `outputimage`, `override_camera`, `override_res`. **Camera must be a USD prim path** (e.g. `/cameras/render_cam`), not a Houdini node path.
- **Resolution override:** `override_res` is a string menu (`''` / `'scale'` / `'specific'`); width/height are `res_user1`/`res_user2` on usdrender, `resolutionx`/`resolutiony` on karma.
- **XPU flush delay:** Karma XPU has a **~10–15s file flush delay** after `render()` returns — don't treat a slow return as a hang.

### 2.8 Common render issues → fixes
| Symptom | Likely cause | Fix |
|---|---|---|
| Black render | Camera not assigned / wrong path | Set `override_camera` to the USD prim path |
| Fireflies | Roughness < 0.01, low samples | Raise samples, keep roughness ≥ 0.01 |
| Noisy | Too few pixel samples | Raise `pathtracedsamples` or enable OIDN |
| Slow | Too many bounces | Trim `diffuselimit`/`reflectlimit` |
| Glass wrong | Nested dielectrics on XPU | Switch to CPU for that shot |

---

## Part 3 — How latency and render settings interact in production

The two topics connect in one important way: **the progressive render pipeline is the mitigation for SYNAPSE's latency.** Because the tool's main-thread holds and panel finalize can stall the artist, the workflow should be:

1. **Layout** at 320×240 / 4 samples — fast, low-stakes, minimal main-thread impact.
2. **Lighting** at 960×540 / 16–32 — the iteration loop where latency matters most; keep it light.
3. **Quality** at 1920×1080 / 64 — the "real" render; run it in **background** (`soho_foreground=0`) so the main thread stays free and SYNAPSE's holds don't fight the render.
4. **Final** at 128–512 samples — background, denoise off, AOVs on.

**Key production rule:** for anything above the lighting pass, render in **background mode** so the main thread is not blocked — this sidesteps both the 648ms doctor hold and the 780ms panel finalize, because the artist isn't waiting on the UI while the render runs.

---

## Part 4 — Concrete settings cheat-sheet

```
ENGINE:  karma_xpu (default) | karma_cpu (hero finals, OSL, nested glass)

PIXEL SAMPLES (karma:global:pathtracedsamples):
  layout    4
  lighting  16–32
  quality   64
  final     128–512

DENOISE:  oidn for previews/most shots; off for hero finals

BOUNCES:
  diffuselimit   2
  reflectlimit   4
  refractlimit  4
  volumelimit   2
  ssslimit      2

AOVs:  beauty + diffuse + normal + depth + crypto_object (start)
       add specular, emission, sss, motionvector as needed

RESOLUTION:  override_res='specific', res_user1=1920, res_user2=1080

CAMERA:  override_camera=<USD prim path>, fStop>0 for DOF

MOTION BLUR:  xformsamples=2, geosamples=2

RENDER MODE:  background (soho_foreground=0) for quality+ passes
```
