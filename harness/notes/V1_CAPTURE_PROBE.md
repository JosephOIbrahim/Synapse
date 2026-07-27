# V1 — THE CAPTURE-PATH PROBE

**Leg** `V1` · **Run** 2026-07-27 · **Build** Houdini **22.0.368**, Python 3.13.10, license **Indie**
**Model** `claude-opus-5[1m]` · **Profile** `harness/readonly-settings.json` (READ-ONLY)
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Binding** R50, R58, R73, R90, R25, R92, R93

> **Read this first.** V1 had already run once, at 10:19 today, and was ruled on as **R100–R106**.
> Its receipt and every probe script it wrote are **absent from the tree** — see *Drift* at the end.
> This run is an independent re-execution that leaves the producers behind. Where a result matches
> a prior ruling it is labelled **reproduces**; where it differs, that is called out explicitly.

Every number below names the script that emits it (Law 2). Every symbol carries
CONFIRMED / ABSENT / UNVERIFIABLE. Every ABSENT carries a same-class positive control (R50).

---

## The one-paragraph answer

**Capture works and is cheap-ish and deterministic. The MASK does not exist.** Karma 22.0.368
will hand you pixels in ~2.4 s, byte-reproducibly, with the denoiser off by default and never
touching the ID planes. What it will not hand you is a per-object integer identity: the ID AOVs
are float-only by construction, `primid` is per-polygon and collides across objects, and
`ray:objectid` returns the same handful of values for two disjoint spheres. **Step 4 of the
RETINA claim — "which pixels belong to X" — has no supplier on this renderer.** One candidate
remains un-probed (cryptomatte) and one new direction is now well-evidenced (Copernicus integer
readback at 2.4 ms).

---

## Q1 — What capture verbs exist?

**Method.** Full `dir()` dump per class rather than keyword search — a complete member list is
both the evidence for CONFIRMED and the same-class positive control R50 requires for ABSENT.
Then, because R73 exists, an **exhaustive sweep**: 853 top-level `hou` names, **530 classes
walked**, every member regex-matched against 22 capture tokens. R73's lesson is that a verified
narrow claim does not license a broad sentence; the sweep is the broad control.

*Producers:* `v1_capture_probe.py` → `v1_q1_symbols.json`; `v1_capture_sweep.py` →
`v1_q1_sweep.json`; `v1_capture_detail.py` → `v1_q1_detail.json`.

**The sweep earned its place** — it found four verbs the hand-written target list did not guess:
`hou.saveImageDataToFile`, `hou.GeometryViewport._captureFramebuffer`, `hou.IPRViewer.pixels`,
and `hou.GeometryViewportSettings.setUseDenoising`.

### Flipbook

| Symbol | Verdict | Anchor / control |
|---|---|---|
| `hou.SceneViewer.flipbook(viewport, settings, open_dialog)` | **CONFIRMED** (symbol) | `hou.SceneViewer` 279 members |
| `hou.SceneViewer.flipbookSettings() -> hou.FlipbookSettings` | **CONFIRMED** | same class |
| `hou.FlipbookSettings` — `output`, `outputToMPlay`, `resolution`, `frameRange`, `useResolution`, `beautyPassOnly`, `antialias`, `cropOutMaskOverlay`, `sessionLabel` | **CONFIRMED** (9/9) | 82 members |
| `hou.SceneViewer.saveViewToFile`, `.screenshot` | **ABSENT** | control: 279 members, `flipbook`/`curViewport`/`setCurrentState` resolve in the same run |

**What it writes:** `FlipbookSettings.output()` (a file path) or `outputToMPlay()`. Frame range,
resolution and motion-blur segments are all settable.

**Invocability is a different claim and it is UNVERIFIABLE here.** `hou.ui` is **not present** in
headless hython (`AttributeError: module 'hou' has no attribute 'ui'`), so no `SceneViewer`
instance can be obtained to call `flipbook()` on. Per R50 / H3a-F5, where no control is possible
the verdict is **UNVERIFIABLE, never ABSENT**. *Producer:* `v1_q3_cost_and_controls.py` phase D.

### RopNode → disk

| Symbol | Verdict | Anchor / control |
|---|---|---|
| `hou.RopNode.render(frame_range, res, output_file, …)` | **CONFIRMED**, and exercised — 11 renders written to disk this run | `hou.RopNode` 318 members |
| `cancel`, `abort`, `interrupt`, `stop`, `kill`, `killRender` | **ABSENT** (6/6) | control: same class, 318 members, `render` + `bypass` + `addRenderEventCallback` + `removeRenderEventCallback` all resolve in the same run |
| `hou.ActiveRender`, `hou.activeRenders` | **ABSENT** (module level) | control: 853 top-level names; `hou.hscript` and `hou.InterruptableOperation` present in same run |
| `hou.IPRViewer.killRender`, `.startRender`, `.pauseRender`, `.isRendering` | **CONFIRMED** (symbols) | `hou.IPRViewer` 104 members |

Independently **reproduces H3a-F1 / R58 / R73's narrow claim**: no cancel verb on `hou.RopNode`,
and `hou.ActiveRender` genuinely absent.

### Copernicus readback — the open SideFX ask

The brief flags this one: treat a clean path here as *surprising* and **verify twice**. So it was
verified twice, in two different kinds.

| Symbol | Verdict | Anchor / control |
|---|---|---|
| `hou.CopNode.layer(output_index=0) -> hou.ImageLayer` | **CONFIRMED** | `hou.CopNode` 340 members |
| `hou.ImageLayer.allBufferElements(storagetype, channels) -> BinaryString` | **CONFIRMED + exercised** | `hou.ImageLayer` 136 members |
| `hou.CopNode.allPixels`, `.planes`, `.xRes`, `.yRes`, `.saveImage`, `.layers`, `.cookLayer`, `.dataLayer` | **ABSENT** | control: `allPixels`, `planes`, `xRes`, `yRes`, `saveImage` **all resolve on `hou.Cop2Node`** (344 members) **in the same run** |

**Verification 1 — structural.** All seven storage types return byte-exact lengths for a
1024×1024×4 buffer, and repeat reads are byte-identical:

```
Float32  16,777,216 B   Int32  16,777,216 B     (4 ch x 4 B x 1,048,576 px)
Float16   8,388,608 B   Int16   8,388,608 B   Fixed16  8,388,608 B
Int8      4,194,304 B   Fixed8  4,194,304 B
repeat_identical = True for all seven
```

**Verification 2 — content.** A length-correct buffer can still be a placeholder, so:
*(a)* drive the source and require the bytes to move — `constant.f1 = 0.15` →
buffer `(0.15, 0.15, 0.15, 1.0)`, exact; *(b)* read a spatially varying source — `fractalnoise`
→ **949,595 distinct values** across 4,194,304 elements, min 0.179 max 1.000. A fixed default
cannot fake a gradient.

*Producers:* `v1_q1_cop_readback.py` → `v1_q1_cop_readback.json`;
`v1_q1_cop_content_control.py` → `v1_q1_cop_content_control.json`.

> **Honesty note.** The content check first returned **INCONCLUSIVE** and said so: it filtered for
> parms named `*color*`, the `constant` COP names them `f4r/f4g/f4b/f4a`, so nothing was set and
> an all-`1.0` buffer proved nothing. Diagnosis: under `signature = 'auto'` the node drives from
> the **`f1`** branch, so both the original probe and R102's spelling were aimed at an inactive
> branch. **My error, not a readback defect** — recorded because the first status was wrong and
> Law 3 says the status describes what happened.

> **Correction to R102.** R102 licenses the `hou.CopNode` ABSENT verdicts by "those same
> spellings resolving on `hou.Cop2Node`". That is true for `allPixels` / `planes` / `xRes` /
> `saveImage` — but **`getPixel` is ABSENT on `Cop2Node` too**. The real legacy spellings are
> `getPixelByUV`, `getPixelHSVByUV`, `getPixelLuminanceByUV`. `getPixel` should come out of
> R102's control list; it is an unspelled name, not a removed one.

### Viewport grab

| Symbol | Verdict | Anchor / control |
|---|---|---|
| `hou.GeometryViewport._captureFramebuffer(buffer_name, filename)` | **CONFIRMED** (symbol, private) | `hou.GeometryViewport` 93 members |
| `hou.GeometryViewport.saveViewToFile`, `.flipbook`, `.screenshot`, `.resolution` | **ABSENT** | control: same class 93 members; `saveViewToCamera`, `resolutionInPixels`, `queryPrimAtPixel`, `queryNodeAtPixel` resolve |
| `hou.IPRViewer.pixel(plane, x, y)`, `.pixels(plane)`, `.planes`, `.saveFrame` | **CONFIRMED** (symbols) | 104 members |
| `hou.saveImageDataToFile(data, w, h, file, flip_vertical=False)` | **CONFIRMED** | module level; writes `.pic`, 32-bit float, **RGBA only** |
| `hou.ui`, `hou.qt` | **UNVERIFIABLE** (not ABSENT) | absent from headless hython by construction — R50 / H3a-F5 |

All of `_captureFramebuffer`, `IPRViewer.*` and `flipbook` need a GUI. **In headless hython their
existence is CONFIRMED and their behaviour is UNVERIFIABLE.** Those are different claims and this
leg does not merge them.

---

## Q2 — Can a render emit an integer object-ID AOV?

**This is the crux, and the answer is no — on three independent grounds.**

*Producers:* `v1_q2_parmdetail.py` → `v1_q2_parmdetail.json`; `v1_q2_render.py` →
`v1_q2_render.json`; `v1_q2_analyse.py` → `v1_q2_analysis.json`;
`v1_q2_ingest_check.py` → `v1_q2_ingest_check.json`. Scene: `v1_scene_two_spheres.usda`.

### What Karma exposes

`karmarendersettings` carries `primid` and `element` toggles (**both default `False`**). Enabled,
they emit EXR parts named `primid` (channel `primid.id`) and `element` (channel `element.id`).

### 1. It is float by construction

`primidprecision` and `elementprecision` are menus with exactly two entries — **`['half','float']`**,
default `float`. **There is no integer option at the parm surface.** The emitted EXR channels are
`float`; beauty `C` is `half`.

### 2. Integer format is refused at render

Setting the husk per-AOV format to `int32` fails the render outright:

```
Unsupported image data format 'int32' in RenderVar /Render/Products/Vars/int_objectid
Error defining render products
-> OperationFailed, husk exit code 1, no output file
```

**Reproduces R100 / V1-F4.**

### 3. It does not identify OBJECTS

160×90 render of two disjoint spheres; sampling boxes taken well inside each sphere so background
cannot contaminate the count:

| AOV | left distinct | right distinct | **shared** | disjoint? |
|---|---|---|---|---|
| `primid` | 180 | 184 | **123** | **no** |
| `element` | 413 | 401 | **89** | **no** |
| `ray:objectid` | 6 | 7 | **6** | **no** |

`primid` is a **per-polygon** id whose range is reused by every object — 123 of ~180 values appear
inside *both* spheres. `ray:objectid` returns essentially one 6-value set shared by both.
**Reproduces R100 / V1-F1 and V1-F2** (different scene and resolution, so the counts differ; the
finding is identical).

### The values are not even integral — and here is why

| AOV | non-integral pixels | of 14,400 |
|---|---|---|
| `primid` | 583 | **4.05 %** |
| `element` | 993 | **6.90 %** |

**New mechanism, not recorded in R100–R106.** *Every* successful render in this leg logged:

```
Pixel filter 'minmax' - Mode idcover requires PrimId channel
```

The shipped default `primidfilter` / `elementfilter` is `["minmax",{"mode":"idcover"}]` — a
coverage-based *selection* filter that should never blend. It is **unsatisfied on every render**
and falls back, and the fallback is what blends. So R100-F3's blending observation is confirmed,
and the cause is a filter that is erroring rather than a filter that is averaging by design.

### Colour management — the one thing that is right

`oiio:ColorSpace` per part: `C` = **`lin_rec709`**, `element` = **`Raw`**, `primid` = **`Raw`**.
**`retina/ingest.py`'s claim that ID/data AOVs ride `Raw` and are never colour-transformed is
TRUE of the file.**

### The `ray:` prefix — silent zero, reproduced with a same-frame control

Custom render vars, one render, both spellings present in the **same EXR**:

| `sourceName` | result |
|---|---|
| `objectid` (bare) | part emitted, correctly named and shaped, **ALL ZEROS**, 1 distinct value, **no error, no warning** |
| `primid` (bare) | part emitted, **ALL ZEROS**, no error |
| `ray:primid` | real data — 315 distinct, max 99, identical to the built-in `primid` part |
| `ray:objectid` | non-zero (large negative floats — an int bit pattern read as float) |

**Reproduces R101** and strengthens it: bare-zero and ray:-nonzero occur **in one frame**, which
is the cleanest possible positive control. A pipeline reading the bare part receives zeros and has
no way to know it asked wrong.

### Does `retina/ingest.py` already know how to read it?

**Half true, and the broken half is a live defect.** Run — not read — against a real Karma frame:

```
parts                : [0] C   [1] element   [2] primid
ID_PART_NAMES        : ('primid', 'id', 'cryptomatte')
find_id_subimage()  -> 1   => part 'element'          <- NOT primid
read_id_plane()     -> ok, shape (90,160), max 1228.75  <- SUCCEEDS, wrong AOV
```

`find_id_subimage` substring-matches `"id"` against the **channel name `element.id`** and returns
`element` before it ever reaches `primid`. `read_id_plane` then reports success while handing back
the wrong plane — a success status over a wrong result (Law 3 shape). Its own error message tells
the caller to set `karmarendersettings.primid=1`; doing so does not make it read `primid`.

**Bounded by control (R73 discipline).** With `element` off, parts are `[C, primid]` and
`find_id_subimage` returns the **correct** index. **The defect is conditional** on an earlier part
whose part-or-channel name contains `"id"` — `element.id` is the one that ships.

**Why the suite never caught it.** `retina/tests/fixtures/exr_synth.py:multipart_exr_bytes` builds
exactly two parts, `C` + `primid`. The shadowing part is **absent from the fixture**, so the
ordering bug cannot fire. The path is exercised — against a fixture that cannot express the
failure. **Law 1: the check cannot fail.**

`retina/ingest.py:65` (`ID_PART_NAMES`), `retina/ingest.py:164` (`find_id_subimage`) — anchors
re-verified at commit `6983c73`.

---

## Q3 — What does one capture COST?

**Scene.** `harness/notes/v1_scene_two_spheres.usda` — two unit spheres separated in X, one dome
light, one camera at z=+9. Hand-authored so the cost number describes something stateable in one
sentence.

**Command.** `usdrender_rop.render(verbose=False)` under `hython3.13.exe`, Karma **CPU**,
`samplesperpixel=4`, `pathtracedsamples=16`, `primid`+`element` on, denoiser off.

*Producer:* `v1_q3_cost_and_controls.py` → `v1_q3_cost_and_controls.json`, phase C.

| resolution | wall-clock |
|---|---|
| 160 × 90 | **2.239 s** |
| 320 × 180 | **2.153 s** |
| 640 × 360 | **2.217 s** |
| 1280 × 720 | **2.502 s** |

**64× the pixels costs +12 % wall-clock.** The cost is almost entirely the **husk process spawn**,
not the rendering. The six-case matrix agrees independently: 2.153–2.502 s across eleven renders.

**The design consequence the brief asked for.** One capture is **~2.4 s, and resolution is nearly
free** — capture at full resolution costs the same as at thumbnail. So the question is not "what
resolution can we afford" but "how often can we afford 2.4 s". Per-mutation verification at 2.4 s
is a different product from one at 0.4 s, and this sits at the expensive end.

**Interruptibility.** `hou.RopNode` has no cancel verb (Q1). `hou.IPRViewer.killRender` exists but
requires a GUI. So a Karma-to-disk capture is **~2.4 s and not interruptible from the calling
thread**. *(Minor drift: the brief says R73 established `rkill` as the only render stop; R73's own
table also lists `hou.IPRViewer.killRender` as PRESENT.)*

**The cheap alternative, measured.** Copernicus readback of a full 1024×1024×4 float32 buffer:
**2.4 ms median** (min 2.367 ms, max 7.197 ms, 5 runs) — in-process, no disk, **~1000× cheaper**.

---

## Q4 — Is the denoiser controllable?

**Yes, per-render, and it is OFF BY DEFAULT.** *Producers:* `v1_q2_parmdetail.py`,
`v1_q2_analyse.py`.

| parm | default | menu |
|---|---|---|
| `karmarendersettings.denoiser` | **`off`** | `['off', 'optix', 'oidn']` |
| `denoise_aovs` | `C` | — |
| `denoise_separate_aovs` | `False` | — |

**Measured, not just declared.** With `denoiser='oidn'` versus the identical scene with it off:

| part | changed | max abs diff |
|---|---|---|
| `C` (beauty) | **14.03 % of pixels** | 0.1432 |
| `element` | **0.00 %** | **0.0** |
| `primid` | **0.00 %** | **0.0** |

So even when switched on, the denoiser touches only the AOVs named in `denoise_aovs` (default
`C`) and leaves the ID planes **bit-identical**. The RETINA doc's fear — that a denoiser makes a
one-prim mutation move pixels anywhere in frame — is real for beauty (14 % of pixels moved) and
**not a threat to the ID planes**.

Viewport-side control also exists: `hou.GeometryViewportSettings.setUseDenoising(bool)` /
`.useDenoising()` — CONFIRMED symbols, invocability UNVERIFIABLE headless. Copernicus ships
`denoiseai` and `denoisetvd` as COP node types (384 COP types total).

### Bonus, and it matters more than it cost: the instrument is DETERMINISTIC

Two renders of the identical scene, **separate husk processes** (different PIDs), no mutation:

```
C        identical=True   max_abs_diff=0.0
element  identical=True   max_abs_diff=0.0
primid   identical=True   max_abs_diff=0.0
```

**The sampling-noise floor on this path is ZERO.** `SYNAPSE_RETINA_VERIFY.md` §0 asserts *"Two
renders of the same scene differ — Monte Carlo. So `delta > 0` means nothing."* On Karma CPU at
fixed sampling, **cross-process, that is false** — `delta > 0` means something. The EXR *files*
differ in byte length (36,876 vs 36,899) because of metadata; the **pixels do not differ at all**.

This is V2's central question, answered early and for free. It should not be taken as
unconditional — one frame, one scene, one machine, CPU engine, fixed sample counts — but the
V2 control now has a strong prior instead of an assumption.

---

## Recommendation

### For pixels: `usdrender_rop.render()` → multi-part EXR → OIIO

**Cost** ~2.2–2.5 s per capture, flat to 1280×720. **Deterministic** — identical inputs give
pixel-identical output across processes. **Denoiser** off by default and harmless to ID planes.
**Colour** correct — ID/data AOVs are `Raw`, beauty is `lin_rec709`.

**Risks.** Not interruptible from the calling thread. husk is a separate process per capture, and
that spawn is the entire cost. Works on **Indie** on this build — note an older H21 finding
recorded husk silently no-opping on Indie; **that is superseded on 22.0.368**, verified by 11
renders that wrote real pixels.

### For the mask: NO VIABLE PATH FOUND. Precisely what is missing:

1. **No integer render-var format.** `primidprecision`/`elementprecision` offer only `half`/`float`;
   `int32` is refused at render with *"Unsupported image data format"*.
2. **No per-object identity.** `primid` is per-polygon and collides across objects (123 shared
   values between two disjoint spheres). `ray:objectid` returns a 6-value set shared by both.
3. **The shipped ID filter is broken.** `["minmax",{"mode":"idcover"}]` errors on every render
   (*"requires PrimId channel"*) and the fallback blends 4–7 % of pixels — concentrated exactly
   where a mask boundary lives.
4. **Cryptomatte is UN-PROBED.** `rendervar` carries a full cryptomatte parm group
   (`…karmacryptomatte`, `…karmacryptomatterank` default 6, `…karmacryptomattesidecar`).
   Cryptomatte is *designed* to be a per-object matte and this leg did not test it. **It is the
   single highest-value next probe** and V2 should not be declared dead until it is run.

### The direction R102 opened is real, and now better evidenced

`hou.CopNode.layer()` → `allBufferElements(Int32, channels)` returns an **exact-length integer
buffer** in **2.4 ms**, content-verified two ways, with just-in-time conversion between storage
types (per the API's own docstring). Karma cannot supply a mask; a COP graph computing one from
**geometry** rather than reading one from a render AOV is tractable and cheap. That is a V2 design
question, not a V1 finding, and it is recorded as a lead rather than a plan.

---

## Drift

**D1 — structural. V1 had already run, and its evidence is gone.**
V1 executed at 10:19 today and was ruled as **R100–R106** in `harness/notes/CTO_RULINGS_01.md`.
But branch `retina/v1-capture-probe` is **zero commits** ahead of the line, its worktree is empty,
and **no `V1.json` and no probe script exist anywhere in the tree.** R103 records why: the
read-only fence denies `Bash(git commit:*)`, so the product was never made durable, and the
worktree was later pruned.

Consequence: every figure in R100–R106 — `7.74 ms`, `50 ids each with 49 shared`, `7.4 % of
pixels` — currently has **no producer path in the tree**. That is a Law 2 violation created by the
fence design, not by the agent. This run exists to replace those with reproducible ones.

**D2 — the leg has no worktree, and the tree moved underneath it.**
`legs.json` declares `worktree: .claude/worktrees/v1-capture-probe`. That directory is **empty and
is not a registered git worktree**, so this leg ran against the **shared main checkout**. Mid-run,
a concurrent leg re-checked-out that directory from `feat/repair-heats-01 @ 2105453` to
`docs/how-we-know @ 6983c73`. All Q1–Q4 findings are VERIFIED-RUNTIME against the live Houdini
build and are unaffected; the one VERIFIED-STATIC finding (`retina/ingest.py`) was **re-verified
against the new commit** and holds. This is precisely the failure Constitution Article V's
one-worktree-per-agent rule exists to prevent, and it is the same mechanism that lost the first
V1's receipt.

**D3 — cosmetic.** The brief states *"R73 established the only render stop is `rkill`"*. R73's own
evidence table also lists `hou.IPRViewer.killRender` as PRESENT. Does not change V1's conclusions:
`killRender` needs a GUI, so a headless capture remains uninterruptible.
