# BP3 — H22 Solaris + World Labs Bridge Probe Review (2026-09-03)

**Leg:** BP3-PROBE · branch `bp3/probe` · wave BP3
**Source blueprint:** `docs/intake/blueprint-h22-worldlabs-intent.md` v0.3 — sec.6 steps 3–5,7; sec.2.6 fixtures; sec.2.8 D2.1–D2.4; sec.9 gates; sec.10 risks
**Probe script (unmodified):** `harness/probes/synapse_blueprint_probes.py` (P-0..P-9, B-1..B-9, S-1..S-3 = 22 probes)
**Evidence root:** `harness/notes/h22wl/bp3_probes/` — `stdout.txt` (verbatim), `probe_results.json`, `b6_wl_component.usdc`, `b7_wl_fixture.exr`, `synapse_blueprint_probes.hip`, `husk_pass_check.txt`, `supplementary.txt`, `run_meta.txt`
**Rule D-1 honored:** this doc reports evidence *found / not found* for gates G-1..G-4. It never writes OPEN. Opening a gate is human + CTO.
**Probe discipline honored:** `git diff master..HEAD -- harness/probes/` is empty. No probe was edited to make it pass. Wrong probes are recorded as findings (§Probe defects), not patched.

---

## 1. Build pin (P-0)

Verbatim, `stdout.txt:3-7`:

```
P-0  Build pin
Houdini: 22.0.400
USD: (0, 26, 5)
MaterialX: 1.39.5
```

Pinned build **22.0.400** (matches BP3-RECON). `hython` = `C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe`; `HOUDINI_USER_PREF_DIR=C:/Users/User/OneDrive/Documents/houdini22.0` (set explicitly per RECON). Run metadata: `harness/notes/h22wl/bp3_probes/run_meta.txt` (exit_code=0).

---

## 2. Reconciliation (V0 → actual, from BP3-RECON + this run)

| V0 path | Actual | Source |
|---|---|---|
| fixtures dir | `harness/fixtures/worldlabs/` | RECON finding |
| reviews dir | `docs/reviews/` | RECON finding |
| notes dir | `harness/notes/` | RECON finding |
| `schemas/world_manifest.schema.json` | `docs/intake/world_manifest.schema.json` (schemas/ has 0 tracked files) | RECON finding (M-1) |
| hython | pinned 22.0.400 (SYNAPSE_HYTHON unset → shim would pick 22.0.429; pinned here) | RECON finding (M-2) |
| gltf SOP `filename` parm | actual parm is **`gltffile`** on `gltf::2.0` (`n.parm('filename')` is None; B-3's label fallback resolves it) | this run, `supplementary.txt` v2 |

---

## 3. Fixtures (D-fixture; SHA256 = the receipt)

Downloaded from `https://wlt-ai-cdn.art/example_exports/narrow_european_cobblestone_lane/` into `harness/fixtures/worldlabs/narrow_european_cobblestone_lane/`. Byte sizes match the CDN `Content-Length` exactly. `2m.ply` / `hq.glb` were **not** fetched (B-1 gate; per blueprint sec.6 step 4).

**Git status:** `.ply` and `.glb` are NOT gitignored; `.png` IS (`.gitignore:107 *.png`). Because the repo auto-pushes feature branches to a **public** GitHub remote while an orchestrator runs, the fixture binaries are **left unstaged** and recorded here by absolute path + hash — this table is the receipt (blueprint sec.2.6; brief T1).

| File | Bytes | SHA256 | gitignored |
|---|---|---|---|
| `narrow_european_cobblestone_lane_500k.ply` | 34,000,416 | `be734a3049ebc995f945d2ffc20696ce3b181d95cd3051a3e06c60d3953beb65` | no (unstaged by choice) |
| `narrow_european_cobblestone_lane_collider.glb` | 959,216 | `08e75e0ad55ceea8ba9305bd1845749b741ca4337cda240e5a35253449eb00c9` | no (unstaged by choice) |
| `narrow_european_cobblestone_lane_pano.png` | 4,213,568 | `e6772fbd49df9456e174e397eb07a01f4f690183b8709cc1307a4cb23d821fdf` | yes |

Absolute dir: `C:/Users/User/SYNAPSE/.claude/worktrees/bp3-probe/harness/fixtures/worldlabs/narrow_european_cobblestone_lane/`

**PLY schema note (B-1):** header declares `element vertex 500000` with `x y z / nx ny nz / f_dc_0..2 / opacity / scale_0..2 / rot_0..3`. **No `f_rest_*` fields** — the 500k tier carries SH degree 0 (DC term) only, no higher-order SH. This is why the exported component (B-6) is 19.8 MB, not the ~90 MB the blueprint sec.2.5 property 3 estimated for 500k *with* `f_rest`.

---

## 4. Per-probe status (22 rows) — `probe_results.json`, summary at `stdout.txt:421-444`

| Probe | Status | s | One-line result |
|---|---|---|---|
| P-0 | RAN | 0.66 | 22.0.400 / USD (0,26,5) / MaterialX 1.39.5 |
| P-1 | RAN | 0.0 | all 16 cited LOP types present (True) |
| P-2 | RAN | 0.0 | label search → imagefilter, karmablockerlightfilter, renderpass, scatterinstances, texturemateriallibrary, copnet_filterlist |
| P-3 | RAN | 0.0 | `usdcreatecomponent`, `usdcreateproxygeometry` present |
| P-4 | RAN | 0.0 | **empty** — no parm labeled equiangular/volume-sampling found on `light::2.0` by that walk |
| P-5 | RAN | 0.0 | full scatterinstances parm surface dumped (167-parm class; `maxangle`=Max Angle in /Scattering/Masks/Up Axis Direction) |
| **P-6** | **BLOCKED** | — | `AttributeError('OpNode' object has no attribute 'stage')` — probe defect (§7) |
| P-7 | RAN | 0.09 | `UsdRender.Pass` define + renderSource True; husk `--pass` confirmed (§husk) |
| P-8 | RAN | 0.0 | `mtlxflake3d` present (True) |
| P-9 | RAN | 0.01 | executionmode {Deferred,Immediate}; Animation(Beta) {Static,Rigid,Deforming} |
| B-1 | RAN | 0.29 | 500000 points, prims 0; full splat attrib schema printed |
| B-2 | RAN | 0.34 | raw bbox + y-quantiles + post-flip corners; handedness not numeric (gui) |
| B-3 | RAN | 0.39 | gltf import = **2 packed prims** (not tris); bbox + splat/collider ratio |
| B-4 | RAN | 0.0 | **no metric/ground metadata** in PLY header or GLB extras → BLU-04 TRUE |
| B-5 | RAN | 0.01 | **native splat tooling present** (bakegsplat, relight_gsplats 1.0/1.1, rasterizegsplats, …) |
| B-6 | RAN | 0.35 | component built: splat=render, collider=proxy; usdc 19.8 MB |
| B-7 | RAN | 4.08 | EXR 1280×720 written but **RGB all-zero**; 6 "no render camera" errors |
| B-8 | RAN | 0.0 | manual Chisel checklist printed |
| B-9 | RAN | 0.23 | scatterinstances → GenerativeProcedural+PointInstancer; source not set to proxy (coll=None) |
| S-1 | RAN | 0.0 | organization walk: kinds/purposes/extents printed |
| S-2 | RAN | 0.0 | **degenerate on packed prims** (floor=0 wall=2); real classes in §6 |
| S-3 | RAN | 0.0 | **degenerate on packed prims** (0/2 in frustum); real geo in §6 |

**Total probe wall time: 6.5 s** (`stdout.txt:444`; sec.6 budget 1800 s). Whole-run wall (incl. Houdini startup) ≈ under 1 min; 30-min budget not approached.

---

## 5. Done-conditions — D1.1, D2.1–D2.4 (verdict + `stdout.txt` anchor)

| ID | Verdict | Evidence / anchor |
|---|---|---|
| **D1.1** — P-1..P-9 run on pinned build, stdout verbatim | **PASS** | P-1..P-9 all executed on 22.0.400; captured `stdout.txt:9-247`. P-6 recorded BLOCKED with traceback (`stdout.txt:223-230`) — a captured outcome, not a skip. P-4 ran but returned empty (no equiangular/volume-sampling label hit). |
| **D2.1** — B-1 PLY schema+counts printed; B-2 handedness + up-axis on raw file | **PASS (B-1 + up-axis) / UNKNOWN (handedness, gui_required)** | B-1 schema + 500000 count `stdout.txt:250-268`. B-2 raw bbox + y-quantiles `stdout.txt:271-277`: raw-y 95%≈+0.62 sits at the +y end → floor toward +y, consistent with WL-EX-05 (+y down). Handedness "not decidable numerically" `stdout.txt:277` → **UNKNOWN** (needs viewer A/B). |
| **D2.2** — collider imported; tri count within 100–200k; bounds vs splat in raw frame | **FAIL** | Imported + bounds compared: `stdout.txt:283-285` (splat/collider ratio [1.307,3.056,1.222]). Tri count: B-3 reports packed prims=2, **not** tris. Authoritative count (GLB accessors + Houdini unpack, agree) = **46,993 tris** → **BELOW** the 100–200k window (`supplementary.txt` v2 L90-92). WL-EX-03's "100–200k" does not hold for this fixture. |
| **D2.3** — B-4 answers whether app exports carry scale/ground metadata | **PASS (answered: NO)** | `stdout.txt:291-300`: PLY header carries no comment/obj_info scale lines; GLB `extras` None at top-level/scene/nodes. **BLU-04 = TRUE** → derive metric/ground in Intent 3. |
| **D2.4** — component per §2.5, converted per §2.7, renders in Karma XPU via husk to a small EXR with **non-zero pixels**; first-pixel <30 s | **FAIL** | Component authored correctly (B-6, `stdout.txt:319-336`; usdc 19.8 MB). Render (B-7) wrote a 1280×720 EXR but **RGB is entirely 0.0** (only alpha ~3.5% coverage) — see §B-7 verbatim + §8. 6× "No render camera defined" + 0 lights. Non-zero *color* pixels NOT produced. Budget moot (render errored, 4.08 s). |

---

## 6. Supplementary measurements (independent of the blueprint probe; `harness/notes/h22wl/bp3_supplementary.py` → `supplementary.txt`)

The blueprint probe measures the collider as **packed** geometry, which hides the truth behind three "RAN-but-degenerate" results (B-3 tri count, S-2, S-3). These are the exact green-that-can't-report-failure class this wave targets. Resolved by an independent measurement (no probe edit):

- **Real collider triangle count = 46,993 tris** (24,643 verts), confirmed two ways that agree exactly: GLB accessor parse (140,979 indices ÷ 3) and Houdini `gltf → unpack → divide` (`supplementary.txt` v2 L90-92). ⇒ D2.2 window = **BELOW**; gate G-1 "≤200k tris" = **met** (47k ≤ 200k).
- **Real normal-class breakdown (unpacked, raw-up=(0,−1,0) per WL-EX-05)** at max_angle=35°: **floor=6414, wall=34415, ceil=963, other=5201** of 46,993 polys (`supplementary.txt` v2 L94-96). Walls dominant, floor present, near-zero ceiling — the expected exterior-lane signature. This proves S-2/S-3's "floor=0 wall=2" was purely the packed-import artifact (2 packed prims), not a real classification.
- **EXR pixel stats** (OpenImageIO + `iinfo -v`, agree): 1280×720 RGBA 16-bit half; **min [0,0,0,0], max [0,0,0,1.0], avg [0,0,0,0.035]**. RGB channels are **flat zero**; only alpha carries ~3.5% coverage. Karma `husk:render_stats` (in EXR metadata): `point total 500000`, `polygon total 0`, `light 0`, all `shader_calls 0`, Optix device 0% contrib. The 500k splat loaded into Karma XPU but contributed **no radiance**; the proxy-purpose collider was excluded (0 polygons).

*Method note recorded for honesty:* the first supplementary run printed 0 geometry because it did not resolve the `gltf::2.0` file parm (name is `gltffile`, not `filename`/`file`); that 0 is a script artifact, corrected in v2 (`supplementary.txt` header + v2 block).

---

## 7. B-6 / B-7 verbatim (required quotes)

**B-6 exported component** — `stdout.txt:336`:

```
  exported harness/notes/h22wl/bp3_probes\b6_wl_component.usdc: 19.8 MB  (SH payload evidence for sec.2.5 property 3; production path = payload this file)
```

On disk: `b6_wl_component.usdc` = **19,756,921 bytes**. Stage structure (`stdout.txt:326-335`) confirms §2.5 intent — splat under `purpose=render` (`/geo/render/points_0`, Points), collider under `purpose=proxy` (`/geo/proxy/world`, Mesh); `WL_fixture` is `kind=component`. Note `stdout.txt:322` "proxy SOP second input failed: Invalid input." — the H22S-SOP-02 "second input = hand-made proxy" index (V0=1) is **invalid**; the proxy geo lands on input 0 (finding §Probe defects).

**B-7 render** — `stdout.txt:345-362` (verbatim key lines):

```
  krs parm by label ('engine',) -> engine | menu: ('cpu', 'xpu')
  rop parm by label ('renderer',) -> None
[14:49:03] No render camera defined in renderPassState        (×6)
-------- Error Summary --------
-------- 6 total errors --------
  EXR written: True harness/notes/h22wl/bp3_probes\b7_wl_fixture.exr 189224 bytes
  Non-zero pixel check: open in MPlay / `iinfo -v` (OIIO) if available. Splat prims may render as nothing if the XPU splat path needs Bake GSplat / Labs LOP output - see B-5.
```

The script's own `EXR written: True` is a **size>4096 check, not a render-success check** — the render errored (6×) and produced black RGB (§6, §8). This is recorded as a probe defect, not corrected.

**husk `--pass` shell check (P-7)** — `harness/notes/h22wl/bp3_probes/husk_pass_check.txt`:

```
  --list-passes                         List all render pass primitives in the
  --pass arg                            Render using a pass defined by the
```

⇒ `husk --pass` present on 22.0.400 (corroborates KAR-04 / N-7).

---

## 8. Gate evidence — G-1..G-4 (found / not found; never OPEN — D-1 owns opening)

| Gate | Evidence sought | Found? | Anchor |
|---|---|---|---|
| **G-1** Sim-ready collider (`UsdPhysicsCollisionAPI` variant) | (a) manifold collider ≤200k tris; (b) B-6 lands it under proxy; (c) B-9 scatter still accepts it | **PARTIAL** — (a) **≤200k FOUND** = 46,993 tris; *manifold* NOT checked (no manifold probe). (b) **FOUND** — `/geo/proxy/world` Mesh, purpose=proxy. (c) **NOT FOUND / UNKNOWN** — B-9 did not set source to the proxy prim (coll=None) and instance/purpose acceptance is Hydra-time (gui_required). | 46,993 = `supplementary.txt` v2 L92; proxy landing = `stdout.txt:330-333`; B-9 = `stdout.txt:374-392` |
| **G-2** Embodied spatial answers | D3.3 passes on both fixtures + non-Marble (D3.4) | **NOT FOUND** — Mile-2 scope; not exercised in this Mile-1 probe run. | out of session-1 scope (blueprint §5) |
| **G-3** Synthetic-data lane | D1.5 render-pass stub exists AND a named dataset consumer written | **NOT FOUND** — no tool stubs authored in session 1 (blueprint §6 forbids); no consumer named (blueprint §9 already: "CLOSED — no consumer named"). | blueprint §9 G-3 row |
| **G-4** Relight seam (patent #3) | none — human's call only, no probe opens it | **N/A (not sought)** — patent surface; no runtime evidence applies. | blueprint §9 G-4 row |

---

## 9. Risk status — R-1..R-4 (triggered / clear / unknown)

| Risk | Status | Evidence / anchor |
|---|---|---|
| **R-1** Karma XPU won't render the splat from a SYNAPSE-authored component | **TRIGGERED (signal observed; cause not fully isolated)** | R-1's own signal is "B-7 EXR empty": **RGB is flat 0.0** (`supplementary.txt` EXR stats). 500k splat points loaded into Karma XPU but 0 radiance; the splat's SH-DC base colour did not appear on the naive `usdrender_rop` path. Native splat render tools exist (B-5) but were not exercised. **Caveat / confound:** the render also had 0 lights and 6 camera errors (probe defects) — a lit render via Bake GSplat / Labs Rasterize/Relight is required to fully isolate splat-path capability. F-1 fallback (collider + pano dome carries the beats) should be treated as live. |
| **R-2** Coordinate frame wrong (upside-down / mirrored / double-flipped) | **UNKNOWN** | Numeric flip behaved as expected (min/max swap on Y,Z; +y-down consistent), `stdout.txt:271-277`. Mirror/handedness is gui_required (Open Q4) → cannot confirm headless. No numeric contradiction observed. |
| **R-3** Vendor drift (docs/CDN/model names change silently) | **CLEAR (baseline set)** | Three fixtures downloaded fresh and hashed (§3); byte sizes match CDN `Content-Length`. No prior hash to contradict; these SHA256s are now the drift baseline for re-download. |
| **R-4** Third-party splat tooling version gap (GSOPs 20.5-only; houdini-gsplat H21, no Karma) | **CLEAR** | B-5 found **native** splat tooling on 22.0.400: `bakegsplat` (SOP), `labs::relight_gsplats::1.0`/`1.1` (LOP), `rasterizegsplats` (COP), plus `labs::delight_gsplats`, `labs::normals_from_gsplats`, `labs::splatter`, `surfacesplat`. `stdout.txt:303-316`. A native path exists → GSOPs/houdini-gsplat not required for one (D-DEP-01 can lean "native"). |

---

## 10. Blueprint §8 open questions 1–5

| # | Question (probe) | Answer | Anchor |
|---|---|---|---|
| 1 | Does `scatterinstances` accept a `purpose=proxy` source prim? (B-9) | **UNKNOWN** — scatter instantiated against the component (`GenerativeProcedural` + `PointInstancer` produced) but the probe did NOT set the source to the proxy prim (coll=None); instance expansion + purpose acceptance is Hydra-time (gui_required). | `stdout.txt:374-392` |
| 2 | Karma XPU splat layout after SOP Import — does Bake GSplat output survive to LOPs, or is the Labs LOP path the only route? (B-7) | **UNKNOWN, leaning "naive path insufficient"** — 500k splat points loaded into Karma XPU but rendered 0 RGB via the plain SOP-Import→`usdrender_rop` path. Native tools (B-5) exist but were not exercised; the surviving-layout question is unresolved. | `stdout.txt:339-362`; B-5 `303-316` |
| 3 | Do Marble app exports carry `metric_scale_factor`/`ground_plane_offset`? (B-4) | **ANSWERED: NO** — neither PLY header nor GLB extras carry them. BLU-04 = TRUE. | `stdout.txt:291-300` |
| 4 | Handedness after Y/Z flip — is the lane mirrored? (B-2) | **UNKNOWN (gui_required)** — not decidable numerically; needs viewer A/B against the Marble world. | `stdout.txt:277` |
| 5 | Chisel template GLB — expected units/frame for uploads? (B-8, manual) | **UNANSWERED — blocked by:** needs the Marble app + a Standard plan (export); B-8 is a manual checklist, not a headless probe. | `stdout.txt:365-371` |

---

## 11. Probe defects found (findings, NOT patched — mission rule)

1. **P-6** BLOCKED — label search `('image filter',)` on the LOP category also matches **"COP Image Filter List"** (`copnet_filterlist`), which sorts before `imagefilter` and is picked as `types[0]`; the created node then has no `.stage()` → `AttributeError`. Fix (human): constrain to the exact `imagefilter` type or filter by category. `stdout.txt:223-230`.
2. **B-3 / S-2 / S-3** degenerate — the `gltf` SOP imports as **packed** geometry (2 packed prims); `intrinsicValue('primitivecount')` returns 2, not the 46,993 real tris, so the D2.2 tri check and all normal classification are meaningless as written. Fix: `unpack` before counting/classifying. Real numbers in §6.
3. **B-7** render mis-reports success — no render camera is set on the ROP/KRS (`render_settings.rendercamera=/cameras/camera1` vs actual `/cameras/wl_cam`) → 6 "No render camera defined" errors; no lights authored → black RGB; and `ok = os.path.getsize(out) > 4096` reports success on a failed render. Fix: set the ROP camera path, add a light, verify pixel stats (not size).
4. **B-9** source never set — the collider-prim search looks for a path ending `/collider`, but the proxy path is `/geo/proxy/world`; `coll=None`, so Open Q1 is not actually exercised. `stdout.txt:376`.
5. **gltf parm name** — the file parm on `gltf::2.0` is **`gltffile`**, not `filename`/`file`; B-3 only survives via its `parm_by_label` fallback. Minor; note in any corpus seed.
6. **B-6** proxy input index — "second input = hand-made proxy" (H22S-SOP-02, V0 index 1) raises "Invalid input"; the proxy geo lands on input 0 instead. `stdout.txt:322`.

None of the above were edited in `harness/probes/synapse_blueprint_probes.py` — verified `git diff master..HEAD -- harness/probes/` is empty.

---

## 12. Corroboration harvest (for the human/CTO promotion pass — not ratified here)

Runtime-confirmed on 22.0.400 (evidence = this run): all P-1 cited LOP types present; `usdcreatecomponent`/`usdcreateproxygeometry` (P-3); `UsdRender.Pass` + `husk --pass` (P-7); `mtlxflake3d` (P-8); scatter `executionmode`/Animation menus (P-9); full scatterinstances parm surface incl. `maxangle` (P-5, seed for D1.4); PLY splat schema (B-1); no app-export metric metadata → BLU-04 (B-4); native splat tooling incl. `bakegsplat`/`relight_gsplats`/`rasterizegsplats` (B-5); component splat=render/collider=proxy (B-6). **UNKNOWN-after-probe:** equiangular MIS label on `light::2.0` (P-4 empty); splat XPU beauty path (B-7); scatter-accepts-proxy (B-9); handedness (B-2). Promotion of any claim to VERIFIED-RUNTIME is D-1's, not this leg's.
