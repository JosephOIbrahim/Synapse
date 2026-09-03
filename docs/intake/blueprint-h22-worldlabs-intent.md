# SYNAPSE Blueprint — H22 Solaris and World Labs World Building, as Intent

**Status:** PROPOSAL · `ratified:false` · authorizes no code change, no corpus write, no version bump.
**Revision:** v0.3 (2026-09-02). v0.2 → v0.3: first-principles performance review — reading map (§0.0), §0.4/§0.5 order fixed, §1.2 wording, performance properties in §2.5, budgets on D2.4 / D3.3 / session 1, probe script: vectorised B-3/S-2, B-6 no longer cascades, S-3 eye from floor, B-6 writes the component to disk and prints its size. Nothing added to scope.
**Revision history:** v0.2 (2026-09-02). v0.1 → v0.2: CTO recommendations applied — rules D-1..D-4 (§0.3), strategic note (§0.5), gated done-conditions D1.7 / D2.7 / D3.6, demo fallback F-1 (§4.2), gate check in miles (§5), gate status in session 1 (§6), gated extensions (§9), risk register (§10), dependency decisions (§11). No intent changed.
**Compiled:** 2026-09-02, Claude (Fable 5.1) with the human, outside Houdini. No probe in this document has been run.
**Build referenced by SYNAPSE artifacts:** H22.0.368 (drop), symbol table 22.0.400 (later recon). Pin the build in every probe output.
**Companions (same project):** `Dossier - H22 Solaris and Karma (SYNAPSE Intake).md` (claims register, probes P-1..P-9, buckets), `Coffee Shop Notes - Solaris and Karma in Houdini 22.md` (digest), `H22 - Solaris - Houdini 22 HIVE.md` (transcript), `frames/hires_t_MMSS.jpg` (parameter panes).
**Sidecars (this drop):** `harness/probes/synapse_blueprint_probes.py` (P-0..P-9 + B-1..B-9 + S-1..S-3), `docs/intake/world_manifest.schema.json` (contract for Intent 3).
**Repo landing (2026-09-03):** this file, the probe script and the schema were dropped into the SYNAPSE repo by the CTO seat for wave BP3. Paths above are the landing paths; every other path in this document is still V0 until BP3-RECON reconciles it.

---

## 0. How to read this document

### 0.0 Reading map (context is the scarce resource)

- **Claude Code, session 1:** read §0.3 (rules), §6 (the script), §2.6 (fixtures), §2.7 (frame order). Skip everything else until the review doc asks a question only another section answers. Do not load the dossier beyond §3, §6, §9.
- **Gate check (after Mile 1):** §5, §9, §10, §11.
- **Humans:** §0–§3 in order. §4 only when the demo is being built.
- **Anyone editing:** D-3 first. Then the revision line.

### 0.1 Epistemology (inherited from SYNAPSE, extended)

- **P1 stands.** Runtime is ground truth. Provenance is not evidence. Two sources agreeing raises probe priority, never tier.
- **Every node type, parm name, prim type, repo path, and tool name in this document is V0** until a probe on the pinned build prints it. Labels read off frames stay labels.
- **Tier vocabulary** reuses the dossier (OBSERVED-SCREEN, STATED, VERIFIED-RUNTIME (SYNAPSE), INFERENCE-FP, UNKNOWN, V0) and adds two tiers for vendor material:
  - **DOC-STATED** — read from vendor documentation at a dated URL. First-party, unverified, subject to silent revision. Every DOC-STATED claim carries URL + read date.
  - **FIXTURE-VERIFIED** — checked against a downloaded World Labs example export (§2.6) with output captured. Strong for the file format; says nothing about worlds generated later or by other model versions.
- **Claim IDs:** `H22S-*` are the dossier's. New here: `WL-EX-nn` (Marble export), `WL-API-nn` (World API), `WL-APP-nn` (Marble app tools), `WL-HOU-nn` (Houdini-side splat tooling), `SP-nn` (spatial lane), `BLU-C-nn` (conflicts).

### 0.2 Intent versus result

An **intent** is a statement of what must be true. A **done-condition** is how we will know. **Implementation is derived by Claude Code on the live repo and is never written here as fact.** Where this document sketches a mechanism (a prim layout, a tool signature, a conversion order) it is a *proposal with a probe attached*, not a spec.

This is the same bet the H22 talk makes about USD: store the intent, compute the result at the last possible moment (dossier §2.3, §2.8). Applied to the plan itself.

### 0.3 Layer model

Three intents, each an independent layer with its own done-conditions. A fourth layer, the demo, **only references**.

```
Intent 1   SYNAPSE speaks H22 Solaris          stands alone; demo optional
Intent 2   You build worlds with World Labs     stands alone; SYNAPSE optional
Intent 3   SYNAPSE has spatial intelligence     stands alone; meets 1 and 2 only in demos
Demo       composition layer                    weakest opinion; references 1, 2, 3; authors nothing upstream
```

**Rule D-0:** the demo layer never adds a requirement to an intent layer. If a demo beat needs something an intent doesn't have, the beat is cut or the requirement is proposed to the intent layer through its own done-conditions.

**Rule D-1 — two keys.** Claude Code proposes; human + CTO ratify. The builder never ratifies its own probe, promotes its own claim, or opens its own gate. This rule is most important when it is most inconvenient.

**Rule D-2 — verified claims are the milestone; the demo is a consumer.** The metric for any mile is the count of V0s that became VERIFIED-RUNTIME or explicit UNKNOWN. A demo running on guessed parm names is a liability, not progress.

**Rule D-3 — gates, not doors.** Scope beyond the three intents enters only as a **gated extension** (§9): the trigger is written before the work, the work waits for probe evidence, and the gate is opened by D-1. Nothing is added to this document — no intent, lane, gate, or mile — until the Mile 1 review doc exists.

**Rule D-4 — one dependency decision at a time, written down.** Third-party packages, vendor skills, and library choices are decided once in the dependency register (§11) with the probe that forced them. Not revisited unless a probe forces it.

### 0.4 What was rejected on the way here

- The NotebookLM `synapse_worldlabs_master_pipeline.py` (2026-09-02). Six-chapter outline kept as a table of contents; code discarded. Reasons, recorded so nobody re-litigates: invented SOP type `usdcomponentoutput`; guessed parm names on real LOPs (`scatterinstances`, `imagefilter`); `HoudiniBatchContext` is H21-era manual-mode + undo, not the H22 edit state (dossier §2.1: batched mutation ≠ batched cooking); `hou.ui.setTriggerViewportUpdate` is not a known API; `WorldLabsClient` invents a semantic response Marble does not return; "Atlas" is not a World Labs product name found anywhere; VEX reads `v@N`/`v@scale` on splat PLYs that carry `scale_0..2` (log) and `rot_0..3`; blast logic inverted; `triangulate2d` on a 3D floor; Y-up assumed where Marble is +Y-down (WL-EX-05). Filed: provenance, not evidence.
- A single fused pipeline (collider → proxy purpose → scatter → manifest). Correct as *one* composition; wrong as *the* structure. Demoted to the demo layer (§4).

### 0.5 Strategic direction (a note, not an intent)

The three intents land SYNAPSE on the substrate that physical-AI pipelines use — OpenUSD, one world as one component, structure and appearance split, a named collider, metric and ground-aligned coordinates with provenance — without doing any physical AI. The lane fences (§2.9, §3.9) are deliberate. The gated extensions in §9 are the doors through those fences; each opens on evidence, never on ambition. This paragraph exists so nobody reads the fences as a lack of direction.

---

## 1. Intent 1 — SYNAPSE speaks H22 Solaris

### 1.1 Must be true

- **I1.a** SYNAPSE names the H22 Solaris/Karma surface Rob Pieke demoed with **runtime-verified** node types and parm names, or says UNKNOWN. Never a label passed off as a name.
- **I1.b** SYNAPSE reasons from the **three design moves** rather than memorizing eleven features: (1) push heavy evaluation into Hydra procedurals; (2) isolate edits on a layer (edit state) because Solaris has no fine-grained dependency tracking; (3) make outputs USD (image filters, render passes) so intent travels with the scene. Dossier §2 is the substrate; §2.1 (cook by re-composition) and §2.2 (Hydra as the render-time seam) are the two the agent must be able to explain unprompted.
- **I1.c** SYNAPSE carries the **presenter-stated limits** (dossier §4, H22S-LIM-01..11) as tool preconditions and answer caveats, not footnotes. Example: any image-filter tool refuses or warns when the renderer does not write its raster product through Husk (H22S-IF-06).
- **I1.d** SYNAPSE authors the new recipes **as USD**: masked scatter on a mesh, blocker light filter bound via `light:filters`, ordered image-filter list via `husk:orderedImageFilters`, `UsdRender.Pass` chain with `renderSource`. Never a HIP-only trick.
- **I1.e** SYNAPSE stays in lane: APEX-in-Hydra, Hydra hair, physics layout are recorded for awareness (D-H22-2, Non-Goal 1) and never authored.

### 1.2 Knowledge inventory (pointers, not copies)

| What | Where | Count |
|---|---|---|
| Claims, tiered | Dossier §3.1–§3.13 | 13 clusters |
| Presenter limits | Dossier §4 | 11 |
| Open tensions for a second source | Dossier §5 | 10 |
| Probe recipes | Dossier §6 → `synapse_blueprint_probes.py` P-1..P-9 | 9 |
| Bucket proposals | Dossier §7 | 10 rows |
| Frames (parameter panes) | `frames/hires_t_MMSS.jpg` | 29 full-res |

Already VERIFIED-RUNTIME by prior SYNAPSE sessions and **not to be re-derived** (P-1 re-checks existence because that is free and pins the build; it does not redo N-3/N-5 work): `paintinstances` rename and alias (N-5), `scatterinstances` type + 167 parms (N-5, SOL-03), `karmablockerlightfilter` + `KarmaBlockerLightFilter` + `light:filters` (N-3), `husk:orderedImageFilters` relationship on RenderSettings and RenderProduct (N-3), `UsdRender.Pass` symbols + `husk --pass` (KAR-04, N-7), MaterialX 1.39.5 (N-6), USD 0.26.5 (`drop.json`), `edit` and `materiallibrary` in `probe_confirmed_types`.

### 1.3 Done-conditions

| ID | Done when | Evidence artifact (V0 path) |
|---|---|---|
| D1.1 | P-1..P-9 run on the pinned build; stdout captured verbatim | `docs/reviews/h22-pieke-probes-<date>.md` |
| D1.2 | Dossier §9 merge worksheet rows filled from probe output; every V0 in §3 either named or marked UNKNOWN-AFTER-PROBE | same review doc |
| D1.3 | Promotion proposal: claim IDs moving to VERIFIED-RUNTIME, each with artifact path | `docs/reviews/h22-pieke-promotion-<date>.md`, `ratified:false` |
| D1.4 | Scatter Instances parameter surface (labels ↔ internal names, P-5) written as corpus seed | `harness/notes/scatterinstances_parms_22.0.x.json` |
| D1.5 | Three NEW_MCP_TOOL candidates stubbed **as signatures and preconditions only** (blocker filter, image filter list, render pass chain) — no implementation | `docs/intake/h22-tool-candidates-<date>.md` |
| D1.6 | Dossier §5 tensions each have a probe result or an explicit "not probed, blocked by X" line | review doc |
| D1.7 **(gated, G-3)** | Synthetic-data lane: pass chain + Labs ML CV Synthetics ROP produce depth / normal / ID / segmentation from a Marble world | opens only per §9 G-3 |

### 1.4 Tool candidates (from dossier §7, restated as intent + precondition)

| Candidate (V0 name) | Intent | Precondition SYNAPSE must check | Source claims |
|---|---|---|---|
| `synapse_author_light_blocker` | Author a `KarmaBlockerLightFilter` prim, bind to lights via `light:filters`, set collection includes/excludes | Render delegate is Karma (H22S-LB-03); shape ∈ probed enum | N-3, H22S-LB-01..04 |
| `synapse_author_image_filters` | Author an ordered `HoudiniImageFilterList` under `/Render`, target it from RenderProduct and/or RenderSettings | Product is a Husk raster product (H22S-IF-06); which relationship wins is open (dossier §5 Q4) | N-3, H22S-IF-01..08 |
| `synapse_author_render_pass_chain` | Author `UsdRender.Pass` with `renderSource` → settings → product, collections for renderable/matte/camera-visible/pruned | `husk --pass` present (KAR-04); one product per output file (H22S-RP-03) | KAR-04, N-7, H22S-RP-01..05 |
| `scene_recipes.py` scatter recipe (RECIPE_CHANGE) | Replace raw PointInstancer authoring with `scatterinstances` + masks where the source is static | Static source (H22S-SI-14); parm names from P-5 | SOL-03, H22S-SI-* |
| `_handle_create_textured_material` upgrade (RECIPE_CHANGE) | Native path via Texture Material Library LOP | Type name from P-2 (H22S-TM-03) | KAR-07 |

### 1.5 Out of lane

APEX Animate in Hydra, Hydra hair/fur, physics layout mode, per-instance shader variation internals (Rob disclaimed ownership, H22S-LIM-10). Record, do not author.

---

## 2. Intent 2 — You build worlds with World Labs

Independent of SYNAPSE. This is the human's craft workflow; SYNAPSE may sit inside it later but nothing here requires it.

### 2.1 Must be true

- **I2.a** Intent can go **out**: a layout blocked in Houdini (walls, openings, hero volumes, a camera position) becomes a generated world without redrawing it in Marble.
- **I2.b** Results come **in**: a generated world lands on a Solaris stage as one component — right way up, metric, ground at y=0 — and renders in Karma XPU.
- **I2.c** The two representations are kept distinct in the USD: the **splat is appearance** (a result; stored, never recomputed), the **collider is structure** (light, queryable, the substrate for every recipe and every spatial question).
- **I2.d** Coordinate conversion is **stateful and idempotent**: the manifest records which conversion steps have been applied to which file so nothing is flipped twice.
- **I2.e** The World API client is **not SYNAPSE code**. World Labs ships an agent skill; SYNAPSE owns only the Houdini side and the manifest adapter.

### 2.2 The two directions

**Out — intent to generation (app-side).**
Chisel accepts a template upload (GLB or FBX), a wall tool (draw perimeter, close, set height, cut doorways), a Panorama Camera (position, height, orientation), then a text prompt → Generate (WL-APP-02). Studio tools: Compose (connect multiple worlds into larger seamless environments), Record (cinematic camera animations, flythrough video); edit tools: pano edit, expand, variations (WL-APP-01). Rob's sequence at 02:07 — decide how the scene is organized, then where things sit relative to each other and to the world — is the shape of Chisel's input.
Houdini-side implication (V0): SOP blocking → GLB export (`gltf` ROP/SOP, V0) → Chisel template. Units and frame of the uploaded GLB are a probe (B-8).

**In — result to Solaris.**
Per world: splat (SPZ ~2M / low-res SPZ ~500k / PLY ~2M / low-res PLY ~500k), collider mesh GLB (100–200k tris, "optimized for simple physics"), optional high-quality mesh GLB (~600k tris textured + ~1M tris vertex-colour; up to an hour; 4 requests/hour/user; owned worlds only), 360 pano (equirect PNG 2560×1280), prompt image (WL-EX-01..04). Plan gating: Standard = splats + panos + colliders; Pro = HQ mesh + commercial rights; Free = generate only (WL-EX-08).

### 2.3 Marble facts ledger

All DOC-STATED, read 2026-09-02 unless tiered otherwise. Corroboration column reserved for FIXTURE-VERIFIED or runtime.

| ID | Claim | Tier | Source | Corr. |
|---|---|---|---|---|
| WL-EX-01 | Image exports: prompt image; 360 panorama equirect PNG 2560×1280 | DOC-STATED | docs.worldlabs.ai/marble/export/specs | |
| WL-EX-02 | Splat exports: SPZ ~2M, low-res SPZ ~500k, PLY ~2M, low-res PLY ~500k; SPZ is Marble-native compressed, PLY uncompressed with broader compatibility | DOC-STATED | specs | |
| WL-EX-03 | Collider mesh: GLB, coarse, for simple physics, 100–200k triangles | DOC-STATED | specs | |
| WL-EX-04 | HQ mesh: one GLB ~600k tris with texture, one ~1M tris with vertex colours; up to 1 h; rate-limited 4/h/user; owned worlds only | DOC-STATED | specs | |
| WL-EX-05 | **Frame:** default worlds are in the OpenCV system (+y down, +z forward). Fix for OpenGL-style DCCs: scale Y and Z by −1, X unchanged. Doc labels x as "+x left" on both systems — treat as a doc typo for x unchanged; verify handedness on a fixture (B-2) | DOC-STATED + open | specs FAQ | |
| WL-EX-06 | Low-res files are optimized to be perceptually similar to full-res; a hosted SPZ→PLY converter exists (spz-to-ply.netlify.app) for one-offs | DOC-STATED | export/gaussian-splat | |
| WL-EX-07 | Five example worlds with every export type downloadable from `wlt-ai-cdn.art/example_exports/…` (see §2.6) | DOC-STATED | specs | |
| WL-EX-08 | Plan gating: Standard = SPZ/PLY splats, 360 panos, collider meshes; Pro = HQ textured mesh + commercial rights; Free = generate only | DOC-STATED | export/gaussian-splat | |
| WL-API-01 | Completed world responses carry `assets.splats.spz_urls` {`500k`, `100k`, `full_res`} and `assets.splats.semantics_metadata` {`metric_scale_factor`, `ground_plane_offset`} | DOC-STATED | docs.worldlabs.ai/api/rendering-spz | |
| WL-API-02 | `metric_scale_factor` converts raw generated units to meters; `ground_plane_offset` places the metric ground plane at y=0. Apply scale to centers **and** sizes; apply the offset to centers only (y). Log-scale fields (`scale_0..2`): add `log(scale)`, do not multiply | DOC-STATED | rendering-spz | |
| WL-API-03 | `semantics_metadata` does **not** include renderer axis conversion. Generated SPZ use `marble_raw_opencv`; Marble's web viewer applies a 180° rotation about X. Order: metric + ground first, axis after | DOC-STATED | rendering-spz | |
| WL-API-04 | World API base `https://api.worldlabs.ai`; export endpoint `POST /marble/v1/worlds/{world_id}:export`; API-key auth | DOC-STATED | api/reference/worlds/export | |
| WL-API-05 | API billing is separate from Marble app credits; API credits are bought on the World Labs Platform, not in the app | DOC-STATED | api/faq | |
| WL-API-06 | API generation inputs: text, images, panoramas, multi-image, video. No 3D-blocking input via API in the docs index | DOC-STATED + INFERENCE (absence) | llms.txt index | |
| WL-API-07 | Model naming differs by surface: app tiers reported as 1.1 Plus / 1.1 / 1.0 / 1.0 Draft (SECONDARY, third-party blog); API FAQ names "Marble 0.1-mini" and "0.1-plus". Mapping page exists: `docs.worldlabs.ai/api/models` | V0 — resolve from the models page | faq; invideo.io (secondary) | |
| WL-APP-01 | App tools: Chisel (coarse 3D blocking → detailed worlds), Compose, Record, pano edit, expand, variations | DOC-STATED | llms.txt index | |
| WL-APP-02 | Chisel inputs: wall tool (perimeter, close, height, doorways), Panorama Camera (position, height, orientation), template upload GLB/FBX, text prompt → Generate. Extrude (Z), wall (X) tools; public mode toggle | DOC-STATED | marble/create/chisel-tools/chisel-basics | |
| WL-DEV-01 | Vendor agent skill: `npx skills add worldlabsai/marble-developer-api-skill --skill marble-developer-api` (`--global` optional; `--list` to verify). Provides API guidance + OpenAPI snapshot. Source mirrored at github.com/worldlabsai/marble-developer-api-skill. Vendor warns: never paste API keys into prompts, logs, or commits | DOC-STATED | api/agent-skill | |
| WL-HOU-01 | World Labs' Houdini page recommends GSOPs (github.com/cgnomads/GSOPs, develop branch), verified by World Labs on Houdini **20.5** only | DOC-STATED | marble/export/gaussian-splat/houdini | |
| WL-HOU-02 | Houdini 21: **Bake GSplat SOP** supports Gaussian Splatting in Karma XPU; expects a PLY input; SideFX calls it a technical preview | DOC-STATED | sidefx.com/docs/houdini/news/21/karma | |
| WL-HOU-03 | Houdini 22: **Labs Relight GSplats** LOP (Since 22.0) relights splats with USD lights + a BSDF (Dome/Distant/Sphere/Rect/Disk/Cylinder/Point, optional shadows, IBL); uses SH coefficients when present; writes lighting to `Cd`; result renders in Karma XPU or third-party splat renderers; can feed a **Rasterize GSplats COP** in Copernicus. Type string V0 | DOC-STATED | sidefx.com/docs/houdini/nodes/lop/labs--relight_gsplats | |
| WL-HOU-04 | Third-party: `houdini-gsplat` (Plattipus, MIT, H21 Solaris) — PLY Import LOP, Gsplat Instancer, Uruk; own Hydra render delegate; **no Karma/Storm rendering**; CPU only; macOS-tested | DOC-STATED (repo README) | github.com/plattipus/houdini-gsplat | |
| WL-HOU-05 | GSOPs 2.6 (CG Nomads): SOP-level toolkit on 20.5; Solaris LOPs (incl. "Gaussian Splats Import LOP") Patreon-gated | DOC-STATED (press) | digitalproduction.com 2025-07-22 | |
| BLU-C-01 | **Conflict.** API FAQ: the World API returns `.spz` only; direct `.ply` export via API not supported. Export endpoint reference: "PLY splat exports are converted synchronously, cached in GCS, and returned as completed operations." Both recorded; runtime settles it (merge rule 2) | CONFLICT | api/faq vs api/reference/worlds/export | |

### 2.4 Houdini ingest candidates (all V0)

| Path | What it would do | Why it matters | Probe |
|---|---|---|---|
| `file` SOP reads PLY | Raw splat attributes as points | Zero dependencies; baseline for attribute schema | B-1 |
| Bake GSplat SOP (H21+) | Karma XPU splat rendering from PLY | Native render path; tech-preview status on 22.0.x unknown | B-5, B-7 |
| Labs Relight GSplats LOP (H22) | Relight splats with stage lights | Implies a LOP-side splat representation Karma XPU renders | B-5, B-7 |
| GSOPs | Full splat toolkit; vendor-recommended | Verified on 20.5 only; external dependency decision for the repo | B-5 (if installed) |
| `gltf` SOP for collider | Collider mesh as SOP geometry | The structure half; scatter source; spatial substrate | B-3 |
| `USD Create Component` / `USD Create Proxy Geometry` (SOP, H22) | Package splat + collider as one component in SOPs; collider into the second (hand-made proxy) input | Pieke's SOP-side workflow, pivots survive | P-3, B-6 |

### 2.5 The world component — USD structure intent (proposal + probes)

One Marble world = one component. Reference the shot to it by **payload** (heavy: ~2M splats; unloadable) — not reference. Variants for tier and surface.

```
/WL_<world_id>              Xform, kind=component
  customData:worldlabs      {world_id, model, frame, semantics_metadata, source_urls, applied}
  variantSet splatTier      { full | low }          ← 2M vs 500k
  variantSet surface        { splat | hqmesh }      ← optional; hqmesh only if exported
  /geo
    /splat                  purpose=render           ← appearance; prim type per B-7 (V0)
    /collider               purpose=proxy            ← structure; Mesh from GLB
```

**Performance properties (from dossier §2.1 and §2.3 — these are why the structure is shaped this way):**

1. **Disk first.** The component is written to disk **once** (B-6 exports it; production path = SOP Import save-to-disk or a USD ROP) and the shot **payloads** the file. The live SOP→LOP chain exists for probes only. Two million points live upstream of a scatter LOP is exactly the "dirty as the universe" case; never ship it.
2. **Viewport draws the collider, Karma draws the splat.** With splat under `render` and collider under `proxy`, a viewport set to display proxy purpose moves ~150k triangles while Karma XPU consumes the splat. Confirm the Solaris viewer's display-purpose default on the pinned build (manual, session 1); if it shows `render` by default, the HIP sets it, the blueprint does not change.
3. **Spherical harmonics are the payload.** `f_rest_0..44` is 45 floats per point: ~360 MB of SH alone at 2M points, ~90 MB at 500k. Probes and layout use the **500k tier**; the 2M tier is a render-time variant. A `sh = full | dc` variant (strip to degree 0 for layout) is a candidate, V0, added only if B-6's exported size says so.
4. **Cook count is the honest measure** (H22S-ED-03). Any done-condition that touches the edit state or scatter reports the Performance Monitor cook-count column, not wall-clock alone.

Open (probes attached): whether `scatterinstances` accepts a `proxy`-purpose source prim (B-9); whether the Karma XPU splat path needs a specific prim/attribute layout that survives SOP Import (B-7); whether the pano belongs on the component (as `customData` asset path) or only in the shot layer as a dome-light texture (decision, not probe — default: shot layer).

### 2.6 Fixtures (no subscription required)

Base: `https://wlt-ai-cdn.art/example_exports/<slug>/<slug>_<variant>` where `<variant>` ∈ `2m.spz | 500k.spz | 2m.ply | 500k.ply | pano.png | collider.glb | hq.glb`.

| Slug | Marble world |
|---|---|
| `rustic_kitchen_with_natural_light` | 69a9fc22-63ad-4e4c-9514-065b9aa56340 |
| `elegant_library_with_fireplace` | 20fc27f9-5b1f-4c76-8b22-67b866195aaf |
| `modern_house_with_lush_landscaping` | e1d2610d-32a7-4364-acbb-8fcc97c1933d |
| `narrow_european_cobblestone_lane` | 54fad6e4-9c9b-43ba-be6d-f1e31cbe7a95 |
| `warm_traditional_kitchen_interior` | 30ac948d-6b19-4191-a12e-4ce4510ccfe7 |

Primary fixture for Miles 1–2: `narrow_european_cobblestone_lane` (exterior, clear ground plane, walls both sides, one obvious axis). Secondary: `modern_house_with_lush_landscaping` (mixed interior/exterior; tests the scatter recipe). Record SHA256 of every downloaded file in the review doc; the CDN can change silently.

### 2.7 Frame conversion — intent-level recipe

Order is a claim (WL-API-03), not a preference:

1. **Raw** (`marble_raw_opencv`, +y down, +z forward, arbitrary units).
2. **Metric + ground:** centers × `metric_scale_factor`; sizes × `metric_scale_factor`; centers.y −= `ground_plane_offset`. Log scales: `+ log(factor)`.
3. **Axis:** 180° about X (≡ scale Y −1, Z −1). Now +y up, −z forward.
4. **Houdini:** Y-up, right-handed. Verify handedness on the fixture (B-2); a mirrored lane is the visible symptom.

The manifest's `frame.applied` block records which of steps 2–3 have been baked into which file. **App exports may or may not already be metric** — the specs page gives no metadata for app exports; whether PLY headers or GLB `extras` carry any is probe B-4. Until B-4 answers, app-export `metric_scale_factor` and `ground_plane_offset` are **derived** by Intent 3 (§3.5) and tiered accordingly.

### 2.8 Done-conditions

| ID | Done when | Evidence |
|---|---|---|
| D2.1 | Fixture PLY attribute schema and counts printed from hython (B-1); handedness and up-axis confirmed on the raw file (B-2) | `docs/reviews/wl-bridge-probes-<date>.md` |
| D2.2 | Collider GLB imported; tri count within 100–200k; bounds compared to splat bounds in the same raw frame (B-3) | same |
| D2.3 | B-4 answers whether app exports carry scale/ground metadata | same |
| D2.4 | One fixture world on a stage as the §2.5 component, converted per §2.7, rendering in Karma XPU via husk to a small EXR with non-zero pixels (B-6, B-7). **Budget (recorded, not gated):** first pixel < 30 s at 1280×720 on the 500k tier, RTX 4090; exported component size printed | EXR + review doc; HIP kept as `harness/scenes/wl_fixture_lane.hip` (V0) |
| D2.5 | One SOP blocking (walls + doorway + camera marker) exported as GLB and accepted by Chisel as a template; generated world re-imported (B-8). **Needs a Standard plan to export the result** | screenshots + review doc |
| D2.6 | Manifest written for the fixture with every field's provenance filled (vendor / derived / probed / unknown) | `harness/fixtures/worldlabs/<slug>/world_manifest.json` (V0) |
| D2.7 **(gated, G-1)** | `UsdPhysicsCollisionAPI` applied to the collider prim as a variant (`physics` = `none | collision`); the exported USD opens in Isaac Sim with the collider recognised as a collision mesh | opens only per §9 G-1; evidence = Isaac Sim screenshot + `usdcat` of the variant |

### 2.9 Non-goals for Intent 2

No World API client in SYNAPSE (vendor skill). No SPZ decoder in SYNAPSE (convert to PLY upstream; BLU-C-01 decides where). No splat *editing* tools (GSOPs' lane). No robotics/sim (World Labs' own Isaac Sim path is not ours).

---

## 3. Intent 3 — SYNAPSE has spatial intelligence

Where Intents 1 and 2 meet, and only in demos. Standalone otherwise: the lane works on any stage, Marble-sourced or not.

### 3.1 Premise (first-party, STATED)

**SP-01** — Rob Pieke, 02:07: once you have components, you decide *how the scene is organized* (hierarchy, structure), and then *how things are placed spatially — relative to each other, relative to the world.* Two questions, in that order. The lane exists to answer both from geometry, not from labels. Anchors the lane the way 15:24 anchors D-track.

**SP-02 (INFERENCE-FP)** — Every answer the lane gives is a **computed signal field** over stage geometry: normal-versus-up, height, distance-to-mesh, frustum membership, occlusion. These are the same fields the H22 scatter masks (H22S-SI-07) and the wet/dry AO blend (H22S-MX-05) use. The lane points them at the agent instead of the renderer. Consequence: answers re-evaluate when the layout changes, exactly as Rob's demo ground did.

### 3.2 Lane declaration (proposal for `authoring_domains.json`, V0 shape)

```json
{
  "lane": "spatial",
  "ratified": false,
  "premise": ["SP-01 (Pieke 02:07)", "SP-02"],
  "substrate": "UsdGeomMesh / UsdGeomPointInstancer prims on stage; for Marble worlds the collider under purpose=proxy. Never the splat.",
  "scope": ["describe organization", "describe placement", "classify surfaces", "frustum membership", "placement candidates"],
  "authoring_later": ["place component at candidate", "scatterinstances recipe with masks", "camera from spawn"],
  "non_goals": ["physics simulation", "robotics / sim-to-real", "navmesh solvers", "APEX / CFX (Non-Goal 1)", "semantic labelling by ML"],
  "contract": "schemas/world_manifest.schema.json"
}
```

### 3.3 Must be true — the question set

**Organization** (Rob's first question):
- **I3.a** What components exist, with `kind`, `purpose` set, bounds, and payload/reference state?
- **I3.b** Is the hierarchy sane — kinds nest legally (assembly ⊃ group ⊃ component ⊃ subcomponent), purposes present where expected?

**Placement** (Rob's second question):
- **I3.c** World bounds, up axis, unit guess, ground height — with provenance (vendor / derived).
- **I3.d** Surface classes on a mesh: floor / wall / ceiling / slope by normal-vs-up with a max-angle threshold (same semantics as the scatter Up Axis mask), with areas and a dominant floor height.
- **I3.e** Candidate openings: floor-class regions adjacent to wall gaps above a height threshold. Marked *candidate*; no ML, no labels.
- **I3.f** From a camera: which prims and which floor regions are in frustum (with padding); placement candidates ranked by distance and visibility. Same semantics as the scatter Camera mask.
- **I3.g** Everything above is **read-only**. Authoring (placing, scattering, camera) is a later done-condition that consumes these answers; it never runs inside them.

### 3.4 Read-only query tools (V0 names, signatures as intent)

| Tool (V0) | Input | Output | Signal field |
|---|---|---|---|
| `synapse_spatial_describe` | stage node path, prim pattern | components + kinds + purposes; world bounds; up axis; units guess; ground estimate; manifest if present | bbox cache, kind/purpose metadata |
| `synapse_spatial_classify` | mesh prim, `max_angle_deg` (default per scatter mask) | per-face class floor/wall/ceiling/slope; areas; dominant floor height; candidate openings | normal·up, height histogram |
| `synapse_spatial_frustum` | camera prim, prim pattern, `padding` | in-frustum prims; floor regions in view; ranked placement candidates | frustum test, distance |

Implementation is Claude Code's, on the live repo, using `pxr` (`UsdGeom.BBoxCache`, `Usd.PrimRange`) and/or `hou` — whichever SYNAPSE's existing D-track tools already use. Not specified here.

### 3.5 Derived manifest fields (for app exports and non-Marble stages)

When vendor `semantics_metadata` is absent:
- `ground_plane_offset` ← dominant floor height from `synapse_spatial_classify` (raw frame, before axis fix — sign follows WL-EX-05).
- `metric_scale_factor` ← **UNKNOWN by default.** Derivation candidates, each a probe: doorway height ≈ 2.0–2.1 m (interiors); wall height cluster; user-supplied reference. A guess is written as a guess: `provenance: "derived:doorway-heuristic"`, never `vendor`.
- `up_axis` ← from the mesh normal distribution's dominant sign *after* the axis fix; confirms WL-EX-05 rather than assuming it.

### 3.6 Authoring hooks (later; consume §3.4, never embedded in it)

- Place a component at a ranked candidate (Xform op; pivot from SOP-side build per H22S-SOP-06).
- Masked scatter recipe on the collider: `scatterinstances` with Up Axis + Camera masks, prototypes from a second input (H22S-SI-07/09). Static source is fine — Marble worlds are static; H22S-LIM-03 does not bite.
- Camera from `spawn` (position + look) as a `UsdGeomCamera` in the shot layer.
- Pano as dome-light texture in the shot layer (LDR; reference only).

### 3.7 Done-conditions

| ID | Done when | Evidence |
|---|---|---|
| D3.1 | Lane entry proposed as a diff to `authoring_domains.json`, `ratified:false`, with non-goals | PR / diff in review doc |
| D3.2 | `world_manifest.schema.json` accepted into the repo (V0 path `schemas/`) | file present, validated with a JSON-schema check |
| D3.3 | The three read-only tools return correct answers on the primary fixture — **each < 5 s on a 200k-tri collider (recorded)** — bounds match B-3; floor class covers the lane; walls both sides; ground height within 5 cm of the vendor value **if** B-4 finds one, else recorded as derived | `docs/reviews/spatial-lane-probes-<date>.md` |
| D3.4 | Same three tools run on the secondary fixture and on one non-Marble stage (any existing SYNAPSE test scene) without code change | same |
| D3.5 | One authoring recipe — masked scatter on the collider — runs through SYNAPSE on the primary fixture and renders (Karma XPU) | EXR + review doc |
| D3.6 **(gated, G-2)** | `synapse_spatial_classify` accepts `agent_width_m` / `agent_height_m`; openings report `passable: true/false` instead of `candidate` | opens only per §9 G-2 |

### 3.8 Probes

S-1 kind/purpose walk on the fixture component; S-2 normal-vs-up classification thresholds vs the scatter mask's Max Angle (read P-5 output for the parm's default); S-3 frustum membership vs the scatter Camera mask (visual A/B in the Karma viewport). In `synapse_blueprint_probes.py`.

### 3.9 Non-goals

Physics, robotics, sim-to-real, navmesh solvers, ML semantic labelling, anything that edits the splat, APEX/CFX.

---

## 4. Demo — composition layer

### 4.1 Rule

References Intents 1–3. Authors nothing upstream (D-0). Every beat maps to exactly one intent; every beat has a cut rule.

### 4.2 Beat script

| # | Beat | Intent | Cut rule (what survives if this beat is cut) |
|---|---|---|---|
| 1 | Block a lane in SOPs: two walls, one doorway, a camera marker | 2-out | Beats 3–8 run on a fixture instead |
| 2 | Export GLB → Chisel template → pano camera → prompt → generate | 2-out | same as 1 |
| 3 | Export splat + collider → land on the stage as one component, right way up, metric, ground at y=0 | 2-in | This beat is the floor. **Fallback F-1 (§10 R-1):** if the splat will not render through a SYNAPSE-authored component, the collider + pano dome light carry beats 4–8 and the splat is viewport-only. Written now so demo day has no scramble |
| 4 | `synapse_spatial_describe` + `classify`: bounds, floor, walls, openings — read aloud from geometry | 3 | Beats 5–6 use hand-picked prims instead |
| 5 | Masked scatter on the collider (Up Axis + Camera masks), prototypes from the studio library | 1 + 3 | Beat 6 lights the bare world |
| 6 | Relight the splat with stage lights; blocker filter where light linking isn't enough | 1 (+ WL-HOU-03) | Beat 7 renders un-relit |
| 7 | Image-filter stack + two-pass chain (hero / no-hero) as USD; render via husk | 1 | Single beauty pass |
| 8 | Edit state: move the hero, cook count doesn't move, exit, one recook | 1 | Skip; say it instead |

### 4.3 Demo-only assets

Studio prototypes for beat 5 (trees/rocks) and a hero asset for beats 5–8 come from the existing library; nothing new is built for the demo. The demo HIP lives under `harness/scenes/demo_wl_lane.hip` (V0) and is never a test fixture.

---

## 5. Miles

| Mile | Intent | Done-conditions | Prerequisites |
|---|---|---|---|
| 1 | 1, 2-in | D1.1–D1.3, D2.1–D2.4 | Pinned build; fixture download; hython |
| 2 | 3 | D3.1–D3.4 | Mile 1; a non-Marble SYNAPSE test scene |
| **Gate check** | — | Every gate in §9 marked OPEN / CLOSED / UNDECIDED from Mile 1–2 probe output, by D-1 | Mile 1 review doc |
| 3 | 2-out, 1 (+ any gate opened) | D2.5, D3.5, D1.4–D1.6; D2.7 / D3.6 if opened | **Marble Standard plan** (export); studio prototypes |
| 4 | 2 | vendor skill installed; manifest adapter reads `semantics_metadata` from an API world; BLU-C-01 settled | API credits (separate from app) |
| 5 | demo | §4 script runs end to end; Operator's Card written | Miles 1–4 |

Miles 1–2 need **no subscription**. Nothing in Mile 4 is on the critical path for the demo if the demo uses an app-exported world.

---

## 6. Claude Code — first session

**Goal of session 1:** reconcile, fixture, probe, report. No tool implementation. No ratification. No corpus writes.

1. **Read** this document, then the dossier (§3, §5, §6, §7, §9). Read the coffee notes only if a claim needs its timestamp. Do not read the transcript unless a specific claim is disputed.
2. **Reconcile V0 paths.** Locate in the live repo: intake docs dir, reviews dir, probe scripts dir, `authoring_domains.json`, `verified_lop_solaris_knowledge_*.json`, `h22_doc_candidates.json`, `scene_recipes.py`, `handlers_material.py`, any existing D-track spatial/bbox helpers, the hython launcher SYNAPSE already uses. Write a **Reconciliation** section at the top of the review doc: `V0 path → actual path` for every path in this document. Where nothing matches, say so; do not create directories to make the blueprint true.
3. **Pin the build.** Print `hou.applicationVersionString()` and the USD/MaterialX versions at the top of every probe output.
4. **Fixture.** Download the primary fixture (`narrow_european_cobblestone_lane`: `500k.ply`, `collider.glb`, `pano.png`) into the reconciled fixtures dir. Record SHA256 and byte size for each. Do not download `2m.ply` or `hq.glb` until B-1 passes on 500k.
5. **Run probes** with hython, in this order, capturing stdout verbatim (**budget: 30 min wall time for the whole set, recorded in the summary**): P-1..P-9 (Intent 1) → B-1..B-9 (Intent 2) → S-1..S-3 (Intent 3). Any probe that raises is recorded with the traceback and marked BLOCKED, then the sequence continues.
6. **Fill** the dossier §9 merge worksheet from P-output, and this document's §2.3 Corroboration column from B-output.
7. **Write the review doc(s)** in the reconciled reviews dir: reconciliation, build pin, fixture hashes, probe outputs, promotion proposal (claim IDs → VERIFIED-RUNTIME with artifact paths), lane-entry diff proposal, **gate status for §9 (G-1..G-4: evidence found / not found — never OPEN; opening is D-1's)**, **risk status for §10 (R-1..R-4: triggered / clear / unknown)**, open questions carried forward.
8. **Stop.** Report what is verified, what is UNKNOWN, what is BLOCKED and by what. Hand back to human + CTO.

**Do not:** invent a parm name to make a probe pass; save a HIP with guessed node types; install GSOPs or any third-party package (repo dependency decision — ask); paste or log API keys; mark anything `ratified:true`; implement §1.4 or §3.4 tools; touch the demo.

**Vendor skill (Mile 4, not session 1):** `npx skills add worldlabsai/marble-developer-api-skill --skill marble-developer-api`. Install in the SYNAPSE repo scope, not global, so the OpenAPI snapshot is versioned with the manifest adapter.

---

## 7. New claims register (this document)

Dossier claims are not repeated. Everything here is DOC-STATED, INFERENCE-FP, or V0 until session 1 runs.

| ID | Claim | Tier | Probe |
|---|---|---|---|
| SP-01 | Organization first, placement second (Pieke 02:07) | STATED | — |
| SP-02 | Spatial answers are computed signal fields; same fields as scatter masks / AO blend | INFERENCE-FP | S-2, S-3 |
| WL-EX-01..08 | §2.3 | DOC-STATED | B-1..B-4 |
| WL-API-01..07 | §2.3 | DOC-STATED / V0 | Mile 4 |
| WL-APP-01..02 | §2.3 | DOC-STATED | B-8 (manual) |
| WL-DEV-01 | vendor agent skill | DOC-STATED | Mile 4 |
| WL-HOU-01..05 | Houdini-side splat tooling | DOC-STATED | B-5, B-7 |
| BLU-C-01 | API PLY export: FAQ vs endpoint reference conflict | CONFLICT | Mile 4 |
| BLU-01 | One Marble world = one `kind=component` prim; payload, not reference; splat under `purpose=render`, collider under `purpose=proxy` | PROPOSAL | B-6, B-7, B-9 |
| BLU-02 | Frame conversion order: metric+ground → axis → Houdini; `applied` flags make it idempotent | DOC-STATED (order) + PROPOSAL (flags) | B-2, B-4 |
| BLU-03 | The collider, not the splat, is the substrate for every recipe and every spatial answer | PROPOSAL | D3.3, D3.5 |
| BLU-04 | App exports carry no scale/ground metadata | UNKNOWN | B-4 |
| BLU-05 | Fallback F-1 (collider + pano dome, splat viewport-only) is demo-viable | UNKNOWN | B-7 + a manual Karma render of the collider with a dome light |

---

## 8. Open questions (carried, not answered)

1. Does `scatterinstances` accept a `purpose=proxy` source prim, or must the collider sit under `default` and be hidden another way? (B-9)
2. What prim/attribute layout does the Karma XPU splat path expect after SOP Import — does Bake GSplat's output survive to LOPs, or is the H22 Labs LOP path the only render route? (B-7)
3. Do Marble app exports (PLY header comments, GLB `extras`) carry `metric_scale_factor` / `ground_plane_offset`? (B-4)
4. Handedness after the Y/Z flip on a fixture: is the lane mirrored? (B-2)
5. Chisel template GLB: expected units and frame for uploads. (B-8, manual)
6. API PLY export: BLU-C-01. (Mile 4)
7. Model-name mapping app ↔ API. (`docs.worldlabs.ai/api/models`, Mile 4)
8. Dossier §5 Q1–Q10 remain open and are Intent 1's.

---

## 9. Gated extensions

Scope beyond the three intents. Each row is a **door in a fence**: the trigger is written here, the work waits for the evidence, the gate is opened only by human + CTO (D-1). Claude Code reports evidence found / not found; it never opens a gate. Status values: `CLOSED` (evidence not yet sought), `EVIDENCE-PENDING` (probes run, awaiting D-1), `OPEN` (done-condition active), `DECLINED` (human + CTO chose not to).

| Gate | Extension | Opens when (evidence) | Owner of the open | Becomes | Target mile | Status |
|---|---|---|---|---|---|---|
| G-1 | Sim-ready collider: `UsdPhysicsCollisionAPI` on `/geo/collider` as a variant; file opens in Isaac Sim | B-3 shows a manifold collider ≤200k tris **and** B-6 lands it under `purpose=proxy` **and** B-9 shows scatter still accepts it (or a `default`-purpose twin works) | human + CTO | D2.7 | 3 | CLOSED |
| G-2 | Embodied spatial answers: agent dimensions on `synapse_spatial_classify`; openings become `passable` | D3.3 passes on **both** fixtures and on the non-Marble scene (D3.4) | human + CTO | D3.6 | 3 | CLOSED |
| G-3 | Synthetic-data lane: pass chain + Labs ML CV Synthetics ROP → depth / normal / ID / segmentation datasets | D1.5 stub for the render-pass tool exists **and** a named consumer for the dataset is written in the gate row (who trains on it, on what) | human + CTO | D1.7 | 4 | CLOSED — no consumer named |
| G-4 | Relight seam for patent filing #3 (Labs Relight GSplats bake as a predictor test bed) | **Human's call only.** No probe opens this. Nothing enters the repo until the human says so | human | — | — | CLOSED — patent surface |

Rules for this table: a gate with no evidence column is not a gate, it is a wish; a gate whose evidence is met is still CLOSED until D-1 opens it; DECLINED gates keep their row so nobody re-proposes them by accident.

---

## 10. Risk register

Top risks to Miles 1–5, each with a fallback written **before** it is needed. Claude Code marks status in the review doc; nobody scrambles on demo day.

| Risk | What breaks | Signal | Fallback (pre-committed) | Owner | Status |
|---|---|---|---|---|---|
| R-1 | Karma XPU will not render the splat from a SYNAPSE-authored component (no native prim path survives SOP Import; Bake GSplat / Labs LOP path needed) | B-7 EXR empty or splat prim absent from the stage | **F-1:** collider + pano dome light carry demo beats 4–8; splat viewport-only. Demo floor becomes the collider, which is the substrate anyway (BLU-03) | Claude Code reports; CTO confirms | unknown |
| R-2 | Coordinate frame wrong: upside-down, mirrored, or double-flipped | B-2 bbox after flip; lane mirrored in viewer; manifest `frame.applied` inconsistent with file | Conversion is stateful (I2.d): fix once in the manifest, never per file. If mirrored, axis fix becomes a rotation, not a scale; record in `frame.axis_fix` | Claude Code | unknown |
| R-3 | Vendor drift: World Labs docs, CDN fixtures, model names change silently | fixture SHA256 mismatch on re-download; DOC-STATED claim contradicted by a later read | Every DOC-STATED claim is dated; fixtures are hashed; re-read on drift and re-tier, never overwrite | human | unknown |
| R-4 | Third-party splat tooling version gap (GSOPs verified on 20.5 only; houdini-gsplat H21, no Karma) | B-5 finds nothing native; only third-party paths exist | Decide per §11 D-DEP-01 once; if no native path on 22.0.x, R-1 fallback applies and the splat render path is an UNKNOWN in the corpus, not a workaround | human + CTO | unknown |

---

## 11. Dependency decisions

One decision at a time (D-4). Each row is decided **once**, with the probe that forced it, and is not revisited unless a probe forces it.

| ID | Decision | Forced by | Options (pre-filtered) | Decided | Rationale |
|---|---|---|---|---|---|
| D-DEP-01 | Install GSOPs in the SYNAPSE environment? | B-5 result | (a) no — native-only, accept UNKNOWN; (b) yes, pinned commit, documented as external; (c) defer to Mile 3 | pending | World Labs recommends it; verified on 20.5 only (WL-HOU-01); Solaris LOPs Patreon-gated (WL-HOU-05). Do not install in session 1 (§6) |
| D-DEP-02 | Vendor agent skill `marble-developer-api` | Mile 4 start | (a) repo-scoped, versioned with the manifest adapter; (b) global | (a) proposed | OpenAPI snapshot must version with the adapter |
| D-DEP-03 | `pxr` vs `hou` for spatial query tools (§3.4) | whatever existing D-track helpers already use | (a) match existing; (b) `pxr` only for portability | pending | Claude Code reports which the repo uses in the reconciliation section |
| D-DEP-04 | SPZ decoding | BLU-C-01 outcome | (a) never in SYNAPSE — PLY upstream; (b) vendor/community converter as an external step | (a) proposed | §2.9 non-goal |
| D-DEP-05 | Isaac Sim available for G-1 verification? | G-1 evidence met | (a) install Isaac Sim locally (free; RTX 4090 qualifies); (b) accept `usdcat` + `UsdPhysics` schema validation only, mark Isaac open as UNVERIFIED | pending | A gate that needs a tool nobody has is a hidden dependency; decide before G-1 is opened, not after |

---

## 12. Source ledger

| Item | Value |
|---|---|
| H22 talk | https://www.youtube.com/watch?v=6EaIVsFOLVg (SideFX, 2026-07-15), via dossier + coffee notes + transcript + frames |
| World Labs docs index | https://docs.worldlabs.ai/llms.txt (read 2026-09-02) |
| Export specs + fixtures | https://docs.worldlabs.ai/marble/export/specs |
| Export overview + plan gating | https://docs.worldlabs.ai/marble/export/gaussian-splat |
| Houdini page | https://docs.worldlabs.ai/marble/export/gaussian-splat/houdini |
| SPZ metadata + frame | https://docs.worldlabs.ai/api/rendering-spz |
| Chisel | https://docs.worldlabs.ai/marble/create/chisel-tools/chisel-basics |
| Agent skill | https://docs.worldlabs.ai/api/agent-skill |
| API FAQ / export endpoint | https://docs.worldlabs.ai/api/faq · https://docs.worldlabs.ai/api/reference/worlds/export |
| H21 Bake GSplat SOP | https://www.sidefx.com/docs/houdini/news/21/karma.html |
| H22 Labs Relight GSplats LOP | https://www.sidefx.com/docs/houdini/nodes/lop/labs--relight_gsplats.html |
| houdini-gsplat | https://github.com/plattipus/houdini-gsplat |
| Rejected input | `synapse_worldlabs_master_pipeline.py` (NotebookLM, 2026-09-02) — §0.4 |
| Compiler | Claude (Fable 5.1), 2026-09-02, no Houdini access, no World Labs account access |
