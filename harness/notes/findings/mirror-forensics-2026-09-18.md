# Mirror forensics -- the encrypted mirror, the primary, and the eleven quarantine copies

**Date:** 2026-09-18 | **Lane:** TASKS 2 + 7b (MIRROR FORENSICS) | **Mode:** read-only, nothing written outside this file.

Store under examination: `C:/Users/User/AppData/Local/Temp/houdini_temp/untitled/.synapse/`

---

## How this was read

The mirror is Fernet-encrypted line by line. Every line carries the `SYNAPSE_ENC_V1:` prefix
(`python/synapse/core/crypto.py:32`) and is decrypted by `CryptoEngine.decrypt_line`
(`python/synapse/core/crypto.py:144`). The key resolves from `~/.synapse/encryption.key`
(`python/synapse/core/crypto.py:96`); that file exists on this machine.

No `MemoryStore`, `MonetaBackedStore` or `SynapseMemory` object was constructed. Houdini 22.0.400 holds
that store right now. `crypto.py` was loaded **by file path** via `importlib.util.spec_from_file_location`,
which pulls in stdlib plus `cryptography` and nothing else -- no package `__init__`, no store class,
no second handle against the storage URI. Every line was decrypted individually and `json.loads`-ed.

Key identity checks out both ways:

```
active key fingerprint:   6aa8f313
sidecar key.fingerprint:  6aa8f313
```

(sidecar path defined at `python/synapse/memory/store.py:342`; comparison logic at `store.py:344-358`)

**Decrypt error count across every file read below: 0.** Nothing in this store is unreadable.

---

## Headline counts -- recomputed, not inherited

The prior audit's figures were **253 primary-only / 4 mirror-only**. The mirror-only figure still holds.
The primary-only figure does not -- it is now zero.

| Measure | Value |
|---|---|
| `snapshot.json` rows | 1,162 |
| Primary distinct inner ids | 1,162 |
| Primary duplicate inner ids | 0 |
| `memory.jsonl` non-empty lines | 1,166 |
| `memory.jsonl` records decoded | 1,166 |
| `memory.jsonl` distinct ids | 1,166 |
| `memory.jsonl` duplicate ids | 0 |
| **Primary-only** (in snapshot, absent from mirror) | **0** |
| **Mirror-only** (in mirror, absent from snapshot) | **4** |

So the mirror is now a strict **superset** of the primary: 1,162 + 4 = 1,166. The 253 gap closed.

The likely closer sits on disk beside the store -- `memory.jsonl.pre-backfill-1789681905`, written
2026-09-17 16:30, holds 882 records. The mirror went 882 to 1,166 at that backfill, a gain of 284.
I did not run the backfill and did not verify its internals; the file's existence, timestamp and
record count are the evidence, and the arithmetic is consistent with the 253 having been written
mirror-ward at that moment.

---

## DELIVERABLE A -- the 4 mirror-only records

These four are the only records in this store at genuine risk of loss. They exist in `memory.jsonl`
and in all thirteen sidecar copies, and in **no** row of `snapshot.json`.

```
mem_1ed48dbc06ea
mem_3f27b6d52222
mem_cb73dd2c8061
mem_e2e9749cb3c3
```

### What they are, and why this matters more than "four records"

All four were created inside a six-minute window on **2026-09-06, 14:00:47 to 14:06:35**. All four are
the **v4 studio lookdev rig recipe** -- three near-identical `note` variants of the recipe plus the
`decision` that binds it to its trigger phrases.

The primary does not merely lack these four ids. It lacks **the entire v4 generation**. Searching all
1,162 primary payloads:

```
'STUDIO LOOKDEV RIG'    : 0 hits
'Basic Studio Lighting' : 0 hits
'hero_sphere'           : 0 hits
'v4'                    : 0 hits
```

The primary's Solaris-recipe lineage stops at v3:

```
2026-09-06T00:45:17Z  mem_ae38a9b2736d  note      DEFAULT SIMPLE SOLARIS NETWORK TEMPLATE (v1)
2026-09-06T00:45:17Z  mem_5e63df8d83e6  decision  "Create a simple solaris network" = v1
2026-09-06T00:48:38Z  mem_adf58a52df9a  note      DEFAULT SIMPLE SOLARIS NETWORK TEMPLATE -- v2
2026-09-06T00:48:42Z  mem_cb67ac3da274  decision  "Create a simple solaris network" = v2
2026-09-06T13:35:40Z  mem_d42816c8963c  note      CANONICAL "Create a Solaris Network" RECIPE -- v3
2026-09-06T13:35:43Z  mem_9e0826890122  decision  "Create a Solaris Network" = v3
                      ----- nothing after this -----
```

The practical consequence: anything recalling from the primary answers "Create a Solaris Network" with
**v3 -- the simple-sphere recipe**. The v4 studio lookdev rig the artist explicitly asked to save is
reachable only through the encrypted mirror. That is a behavioural gap, not just a row-count gap.

### The records, in full

#### `mem_3f27b6d52222`

```json
{
  "agent_id": "",
  "alternatives": [],
  "confidence": 1.0,
  "consolidated_into": null,
  "content": "CANONICAL STUDIO LOOKDEV RIG RECIPE — v4 (SUPERSEDES v3). Trigger phrases: \"Create a Solaris Network\" AND \"Basic Studio Lighting Setup\" (also \"studio lighting rig\", \"lookdev rig\", \"hero asset lookdev\"). Build this EXACT render-ready chain in /stage. This is a full studio lookdev/lighting-test rig with one hero asset.\n\nCHAIN (linear, each node input 0 = previous):\nAssets(merge) -> asset_materials(materiallibrary) -> mat_hero(materiallibrary) -> full_stage(merge) -> rendergeometrysettings2 -> karmarendersettings -> render_passes(pythonscript) -> renderpass1 -> usdrender_rop1.\n\nASSETS merge inputs (geometry first, then refs):\n- input 0: transform_reference_objects (xform wrapping reference_objects collection of matte_ball + reflection_ball)\n- input 1: cyc (sopcreate, the studio cyclorama wall)\n- input 2: one_unit_ruler (sopcreate, scale reference)\n- input 3: hero_sphere (sopcreate, THE HERO ASSET — polygon sphere, radius 1.5, rows 32 cols 64, pathprefix=/World/Assets/hero_sphere)\n\nMATERIALS:\n- asset_materials (materiallibrary, matpathprefix=/World/Materials/) has 5 entries: mat_macbeth (assigned /World/Assets/macbeth_card), mat_matte_ball (/World/Assets/matte_ball), mat_reflective_ball (/World/Assets/reflection_ball), mat_cyc (/World/Assets/cyc), mat_ruler (/World/Assets/one_unit_ruler). Each is a subnet VOP with mtlxstandard_surface + mtlxdisplacement + kma_material_properties.\n- mat_hero (materiallibrary, matpathprefix=/materials/) has 1 entry: mat_hero_shader (mtlxstandard_surface, POLISHED RED METAL: base=1, metalness=1, specular_roughness=0.05, base_color=[0.8,0.2,0.1]), assigned to /World/Assets/hero_sphere. This is the hero material.\n\nLIGHTS (via lightmixer1, sun+sky disabled by default in mixer):\n- sun (karmaphysicalsky) -> sun/sun (DistantLight) + sun/sky (KarmaSkyDomeLight)\n- Overhead (RectLight), Left (RectLight), Right (RectLight)\n- lights_merge combines them, feeds lightmixer1.\n\nCAMERAS: stage_front, stage_left, stage_right (all under /World/Cameras/), merged via cameras merge. Karma camera=/World/Cameras/stage_front.\n\nRENDER SETTINGS (karmarendersettings):\n- engine=xpu (Karma XPU), camera=/World/Cameras/stage_front\n- enabledof=0, enablemblur=0 (disabled for lookdev iteration)\n- denoiser=optix\n- render_passes pythonscript adds AOVs: beauty(C), diffuse(direct_diffuse), specular(direct_specular), normal(N), depth(Z)\n- usdrender_rop1 outputimage=$HIP/render/lookdev.$F4.exr\n\nKEY CONFIG NOTES:\n- Node TYPE names that WORK on this build: sopcreate, materiallibrary, camera, karmarendersettings, null, light, merge, xform, collection, renderpass, usdrender_rop, rendergeometrysettings, lightmixer, karmaphysicalsky. (NOT 'rectlight'/'arealight'/'cameranode'/'domelight' — phantom/deprecated.)\n- 'lighttype' menu index is unreliable �� author USD primtype directly via 'primtype' parm.\n- LIGHTING LAW: intensity ALWAYS 1.0, brightness via exposure only.\n- Hero sphere is a polygon sphere embedded in a sopcreate (not a separate /obj net).\n- The hero material is a SEPARATE materiallibrary (mat_hero) chained after asset_materials, NOT folded into it — keeps hero lookdev isolated.\n- render_passes is a pythonscript LOP wired between karmarendersettings and renderpass1.\n\nThis recipe is validated end-to-end (wiring tested, node types confirmed against this build's runtime). Reuse verbatim to avoid phantom-type failures and the shifting lighttype index.",
  "created_at": "2026-09-06T14:00:47Z",
  "embedding": null,
  "frame": 1,
  "frame_range": null,
  "hip_file": "untitled.hip",
  "hip_version": 0,
  "id": "mem_3f27b6d52222",
  "is_consolidated": false,
  "keywords": [],
  "links": [],
  "memory_type": "note",
  "node_paths": [],
  "reasoning": "",
  "ref_uri": "",
  "source": "ai",
  "status": "",
  "summary": "CANONICAL STUDIO LOOKDEV RIG RECIPE — v4 (SUPERSEDES v3). Trigger phrases: \"Create a Solaris Network...",
  "tags": [
    "solaris",
    "recipe",
    "template",
    "default",
    "network",
    "karma",
    "studio",
    "lookdev",
    "hero asset",
    "lighting rig"
  ],
  "tier": "shot",
  "updated_at": "2026-09-06T14:00:47Z"
}
```

#### `mem_e2e9749cb3c3`

```json
{
  "agent_id": "",
  "alternatives": [
    "Keeping the v3 simple-sphere recipe; or a scene_template LOP / lighting_rig template — but none embed the full studio lookdev rig (cyc",
    "matte/reflection balls",
    "Macbeth card",
    "ruler",
    "light mixer",
    "3 cameras",
    "hero sphere) the artist built",
    "so a custom canned recipe is more faithful."
  ],
  "confidence": 1.0,
  "consolidated_into": null,
  "content": "**Decision:** \"Create a Solaris Network\" AND \"Basic Studio Lighting Setup\" now both = v4 recipe: the full studio lookdev rig. Chain: Assets(merge: transform_reference_objects + cyc + one_unit_ruler + hero_sphere) -> asset_materials(5 materials) -> mat_hero(polished red metal hero material) -> full_stage(merge) -> rendergeometrysettings2 -> karmarendersettings(engine=xpu, denoiser=optix, no DOF/mblur) -> render_passes(beauty/diffuse/specular/normal/depth AOVs) -> renderpass1 -> usdrender_rop1(outputimage=$HIP/render/lookdev.$F4.exr). Lights via lightmixer1 (sun+sky disabled by default). Cameras stage_front/left/right.\n**Reasoning:** The artist explicitly asked to save this exact studio lookdev setup as a recipe recallable in a new SYNAPSE session, tagged with both trigger phrases. This network is validated end-to-end (wiring tested, node types confirmed against this build's runtime). Recording the decision plus the v4 reference keeps the canonical recipe authoritative and supersedes the v3 simple-sphere version.\n**Alternatives Considered:**\n- Keeping the v3 simple-sphere recipe; or a scene_template LOP / lighting_rig template — but none embed the full studio lookdev rig (cyc\n- matte/reflection balls\n- Macbeth card\n- ruler\n- light mixer\n- 3 cameras\n- hero sphere) the artist built\n- so a custom canned recipe is more faithful.",
  "created_at": "2026-09-06T14:00:50Z",
  "embedding": null,
  "frame": 1,
  "frame_range": null,
  "hip_file": "untitled.hip",
  "hip_version": 0,
  "id": "mem_e2e9749cb3c3",
  "is_consolidated": false,
  "keywords": [
    "recipe",
    "studio",
    "lookdev",
    "network",
    "setup"
  ],
  "links": [],
  "memory_type": "decision",
  "node_paths": [],
  "reasoning": "The artist explicitly asked to save this exact studio lookdev setup as a recipe recallable in a new SYNAPSE session, tagged with both trigger phrases. This network is validated end-to-end (wiring tested, node types confirmed against this build's runtime). Recording the decision plus the v4 reference keeps the canonical recipe authoritative and supersedes the v3 simple-sphere version.",
  "ref_uri": "",
  "source": "ai",
  "status": "",
  "summary": "**Decision:** \"Create a Solaris Network\" AND \"Basic Studio Lighting Setup\" now both = v4 recipe: the...",
  "tags": [
    "ai_decision"
  ],
  "tier": "shot",
  "updated_at": "2026-09-06T14:00:50Z"
}
```

#### `mem_1ed48dbc06ea`

```json
{
  "agent_id": "",
  "alternatives": [],
  "confidence": 1.0,
  "consolidated_into": null,
  "content": "CANONICAL STUDIO LOOKDEV RIG RECIPE — v4 (SUPERSEDES v3). Trigger phrases: \"Create a Solaris Network\" AND \"Basic Studio Lighting Setup\" (also \"studio lighting rig\", \"lookdev rig\", \"hero asset lookdev\"). Build this EXACT render-ready chain in /stage. Full studio lookdev/lighting-test rig with one hero asset.\n\nCHAIN (linear, each node input 0 = previous):\nAssets(merge) -> asset_materials(materiallibrary) -> mat_hero(materiallibrary) -> full_stage(merge) -> rendergeometrysettings2 -> karmarendersettings -> render_passes(pythonscript) -> renderpass1 -> usdrender_rop1.\n\nASSETS merge inputs (geometry first, then refs):\n- input 0: transform_reference_objects (xform wrapping reference_objects collection of matte_ball + reflection_ball)\n- input 1: cyc (sopcreate, studio cyclorama wall)\n- input 2: one_unit_ruler (sopcreate, scale reference)\n- input 3: hero_sphere (sopcreate, THE HERO ASSET — polygon sphere radius 1.5 rows 32 cols 64, pathprefix=/World/Assets/hero_sphere)\n\nMATERIALS:\n- asset_materials (materiallibrary, matpathprefix=/World/Materials/) has 5 entries: mat_macbeth(/World/Assets/macbeth_card), mat_matte_ball(/World/Assets/matte_ball), mat_reflective_ball(/World/Assets/reflection_ball), mat_cyc(/World/Assets/cyc), mat_ruler(/World/Assets/one_unit_ruler). Each is a subnet VOP with mtlxstandard_surface + mtlxdisplacement + kma_material_properties.\n- mat_hero (materiallibrary, matpathprefix=/materials/) has 1 entry: mat_hero_shader (mtlxstandard_surface POLISHED RED METAL: base=1 metalness=1 specular_roughness=0.05 base_color=[0.8,0.2,0.1]) assigned to /World/Assets/hero_sphere. Kept SEPARATE from asset_materials to isolate hero lookdev.\n\nLIGHTS (via lightmixer1, sun+sky disabled by default): sun(karmaphysicalsky)->sun/sun(DistantLight)+sun/sky(KarmaSkyDomeLight). Overhead/Left/Right RectLights. lights_merge combines, feeds lightmixer1.\n\nCAMERAS: stage_front, stage_left, stage_right under /World/Cameras/, merged via cameras merge. Karma camera=/World/Cameras/stage_front.\n\nRENDER SETTINGS (karmarendersettings): engine=xpu, camera=/World/Cameras/stage_front, enabledof=0, enablemblur=0, denoiser=optix. render_passes pythonscript adds AOVs: beauty(C), diffuse(direct_diffuse), specular(direct_specular), normal(N), depth(Z). usdrender_rop1 outputimage=$HIP/render/lookdev.$F4.exr.\n\nKEY CONFIG:\n- Node types that WORK: sopcreate, materiallibrary, camera, karmarendersettings, null, light, merge, xform, collection, renderpass, usdrender_rop, rendergeometrysettings, lightmixer, karmaphysicalsky. NOT rectlight/arealight/cameranode/domelight (phantom/deprecated).\n- lighttype menu index unreliable — author USD primtype directly via primtype parm.\n- LIGHTING LAW: intensity ALWAYS 1.0, brightness via exposure only.\n- Hero sphere is polygon sphere embedded in a sopcreate (not separate /obj net).\n- render_passes is a pythonscript LOP wired between karmarendersettings and renderpass1.\n\nValidated end-to-end (wiring tested, node types confirmed against this build's runtime). Reuse verbatim to avoid phantom-type failures and shifting lighttype index.",
  "created_at": "2026-09-06T14:03:51Z",
  "embedding": null,
  "frame": 1,
  "frame_range": null,
  "hip_file": "untitled.hip",
  "hip_version": 0,
  "id": "mem_1ed48dbc06ea",
  "is_consolidated": false,
  "keywords": [],
  "links": [],
  "memory_type": "note",
  "node_paths": [],
  "reasoning": "",
  "ref_uri": "",
  "source": "ai",
  "status": "",
  "summary": "CANONICAL STUDIO LOOKDEV RIG RECIPE — v4 (SUPERSEDES v3). Trigger phrases: \"Create a Solaris Network...",
  "tags": [
    "solaris",
    "recipe",
    "template",
    "default",
    "network",
    "karma",
    "studio",
    "lookdev",
    "hero asset",
    "lighting rig"
  ],
  "tier": "shot",
  "updated_at": "2026-09-06T14:03:51Z"
}
```

#### `mem_cb73dd2c8061`

```json
{
  "agent_id": "",
  "alternatives": [],
  "confidence": 1.0,
  "consolidated_into": null,
  "content": "CANONICAL STUDIO LOOKDEV RIG RECIPE — v4 (SUPERSEDES v3). Trigger phrases: \"Create a Solaris Network\" AND \"Basic Studio Lighting Setup\" (also \"studio lighting rig\", \"lookdev rig\", \"hero asset lookdev\"). Build this EXACT render-ready chain in /stage. Full studio lookdev/lighting-test rig with one hero asset.\n\nCHAIN (linear, each node input 0 = previous):\nAssets(merge) -> asset_materials(materiallibrary) -> mat_hero(materiallibrary) -> full_stage(merge) -> rendergeometrysettings2 -> karmarendersettings -> render_passes(pythonscript) -> renderpass1 -> usdrender_rop1.\n\nASSETS merge inputs (geometry first, then refs):\n- input 0: transform_reference_objects (xform wrapping reference_objects collection of matte_ball + reflection_ball)\n- input 1: cyc (sopcreate, studio cyclorama wall)\n- input 2: one_unit_ruler (sopcreate, scale reference)\n- input 3: hero_sphere (sopcreate, THE HERO ASSET — polygon sphere radius 1.5 rows 32 cols 64, pathprefix=/World/Assets/hero_sphere)\n\nMATERIALS:\n- asset_materials (materiallibrary, matpathprefix=/World/Materials/) has 5 entries: mat_macbeth(/World/Assets/macbeth_card), mat_matte_ball(/World/Assets/matte_ball), mat_reflective_ball(/World/Assets/reflection_ball), mat_cyc(/World/Assets/cyc), mat_ruler(/World/Assets/one_unit_ruler). Each is a subnet VOP with mtlxstandard_surface + mtlxdisplacement + kma_material_properties.\n- mat_hero (materiallibrary, matpathprefix=/materials/) has 1 entry: mat_hero_shader (mtlxstandard_surface POLISHED RED METAL: base=1 metalness=1 specular_roughness=0.05 base_color=[0.8,0.2,0.1]) assigned to /World/Assets/hero_sphere. Kept SEPARATE from asset_materials to isolate hero lookdev.\n\nLIGHTS (via lightmixer1, sun+sky disabled by default): sun(karmaphysicalsky)->sun/sun(DistantLight)+sun/sky(KarmaSkyDomeLight). Overhead/Left/Right RectLights. lights_merge combines, feeds lightmixer1.\n\nCAMERAS: stage_front, stage_left, stage_right under /World/Cameras/, merged via cameras merge. Karma camera=/World/Cameras/stage_front.\n\nRENDER SETTINGS (karmarendersettings): engine=xpu, camera=/World/Cameras/stage_front, enabledof=0, enablemblur=0, denoiser=optix. render_passes pythonscript adds AOVs: beauty(C), diffuse(direct_diffuse), specular(direct_specular), normal(N), depth(Z). usdrender_rop1 outputimage=$HIP/render/lookdev.$F4.exr.\n\nKEY CONFIG:\n- Node types that WORK: sopcreate, materiallibrary, camera, karmarendersettings, null, light, merge, xform, collection, renderpass, usdrender_rop, rendergeometrysettings, lightmixer, karmaphysicalsky. NOT rectlight/arealight/cameranode/domelight (phantom/deprecated).\n- lighttype menu index unreliable — author USD primtype directly via primtype parm.\n- LIGHTING LAW: intensity ALWAYS 1.0, brightness via exposure only.\n- Hero sphere is polygon sphere embedded in a sopcreate (not separate /obj net).\n- render_passes is a pythonscript LOP wired between karmarendersettings and renderpass1.\n\nValidated end-to-end (wiring tested, node types confirmed against this build's runtime). Reuse verbatim to avoid phantom-type failures and shifting lighttype index.",
  "created_at": "2026-09-06T14:06:35Z",
  "embedding": null,
  "frame": 1,
  "frame_range": null,
  "hip_file": "untitled.hip",
  "hip_version": 0,
  "id": "mem_cb73dd2c8061",
  "is_consolidated": false,
  "keywords": [],
  "links": [],
  "memory_type": "note",
  "node_paths": [],
  "reasoning": "",
  "ref_uri": "",
  "source": "ai",
  "status": "",
  "summary": "CANONICAL STUDIO LOOKDEV RIG RECIPE — v4 (SUPERSEDES v3). Trigger phrases: \"Create a Solaris Network...",
  "tags": [
    "solaris",
    "recipe",
    "template",
    "default",
    "network",
    "karma",
    "studio",
    "lookdev",
    "hero asset",
    "lighting rig"
  ],
  "tier": "shot",
  "updated_at": "2026-09-06T14:06:35Z"
}
```

---

## DELIVERABLE B -- the eleven quarantine copies

### They are one file, stored eleven times

All eleven `degraded-load` copies are **byte-identical**. Same size (1,394,474 bytes), same full SHA-256:

```
2d8cc01b70b265fcbab7ec86a11683bf82d2ba3b50ad422aae3083b29f5ff120
```

`memory.jsonl.pre-repair-1789674797` carries that same hash, making **twelve** identical copies of one
846-line file -- roughly 16.7 MB of the same bytes.

That is expected behaviour, not a second fault. `_quarantine_store` (`python/synapse/memory/store.py:362`)
copies the store aside on **every** degraded load; the call site is `store.py:459`, fired unconditionally
whenever `degraded_reason` is truthy (`store.py:447-459`). Eleven store opens while the store was
degraded produced eleven copies. The timestamps in the filenames are the eleven open times.

### Per-file table

Every row below was produced by decrypting the file line by line and comparing id sets against the
1,162-id primary and the 1,166-id live mirror.

| File | Bytes | Lines | Records | Distinct ids | Dupe ids | Decrypt errors | Ids not in primary | Ids not in live mirror | Strict subset of primary? |
|---|---|---|---|---|---|---|---|---|---|
| `memory.jsonl.degraded-load-1789506731` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789507423` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789508001` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789509778` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789513143` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789561952` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789585035` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789603251` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789652284` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789673481` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| `memory.jsonl.degraded-load-1789674135` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| *(context)* `memory.jsonl.pre-repair-1789674797` | 1,394,474 | 846 | 846 | 841 | 5 | 0 | 4 | 0 | **No** |
| *(context)* `memory.jsonl.pre-backfill-1789681905` | 1,428,673 | 882 | 882 | 882 | 0 | 0 | 4 | 0 | **No** |

The four ids missing from the primary are the same four in every file -- the v4 lookdev set:
`mem_1ed48dbc06ea`, `mem_3f27b6d52222`, `mem_cb73dd2c8061`, `mem_e2e9749cb3c3`.

**Plain answer to the question asked:** no quarantine copy is a strict subset of the primary. Each holds
those same four v4 records that the primary lacks. But none of them holds anything the **live mirror**
lacks either -- "ids not in live mirror" is 0 for all thirteen files. Nothing unique is trapped in a
quarantine copy at the id level.

### The one thing the quarantine copies hold that nothing else does

Five ids appear twice inside each 846-line copy -- 841 distinct ids across 846 lines. Those five are the
recorded blast radius of the 2026-09-15 outage. The two occurrences are **not** identical payloads, and
only one of the two survives in the live mirror and in the primary.

The surviving variant is the rich one. The lost variant is a metadata-stripped re-emission:

| id | created_at | fields that differ | surviving variant | lost variant |
|---|---|---|---|---|
| `mem_596cf755cfbf` | 2026-09-01T00:16:02Z | frame, hip_file, hip_version, source, tags | `source="ai"`, 4 tags, real hip path, frame=1, hip_version=19 | `source="auto"`, `tags=[]`, `hip_file=""`, `frame=null`, `hip_version=0` |
| `mem_d8486c1c0ee0` | 2026-09-02T13:14:29Z | frame, hip_file, source, tags | `source="ai"`, 4 tags, `untitled.hip`, frame=1 | `source="auto"`, `tags=[]`, `hip_file=""`, `frame=null` |
| `mem_ae38a9b2736d` | 2026-09-06T00:45:17Z | frame, hip_file, source, tags | `source="ai"`, 5 tags, `untitled.hip`, frame=1 | `source="auto"`, `tags=[]`, `hip_file=""`, `frame=null` |
| `mem_adf58a52df9a` | 2026-09-06T00:48:38Z | frame, hip_file, source, tags | `source="ai"`, 6 tags, `untitled.hip`, frame=1 | `source="auto"`, `tags=[]`, `hip_file=""`, `frame=null` |
| `mem_d42816c8963c` | 2026-09-06T13:35:40Z | frame, hip_file, source, tags | `source="ai"`, 7 tags, `untitled.hip`, frame=1 | `source="auto"`, `tags=[]`, `hip_file=""`, `frame=null` |

The content bodies are identical in every pair. Only provenance metadata was dropped in the second
emission. At payload level, each quarantine copy contains exactly **5 payloads** not byte-equal to any
live payload, and they are these five degraded twins -- strictly poorer copies of records that already
survive in full. `memory.jsonl.pre-backfill-1789681905` contains **0** such payloads.

**Verdict on the eleven copies as evidence:** they hold no unique record. They hold five degraded
duplicate payloads whose only value is as the physical artifact of the outage -- the before-picture.
They are not recovery material. Nothing in them is needed to reconstruct anything.

---

## What is actually at risk

One thing, and it is not in the quarantine pile.

**The v4 studio lookdev rig exists only in the encrypted mirror.** Four records, 2026-09-06 14:00-14:06.
The primary carries no trace of that generation -- not the ids, not the content, not a single matching
substring. If the mirror is ever treated as disposable because "the primary has everything", v4 goes
with it, and the recipe silently reverts to v3.

The eleven quarantine copies are storage cost, not risk. The risk is the asymmetry: the mirror is a
superset of the primary by exactly the four records the artist asked to be able to recall by name.

No remediation was performed. Nothing was deleted. The decision on what to do about the four records
belongs to the human reading this.

---

## Commands run

Four scripts, all read-only against the store, all run from the session scratchpad:

```
forensics.py   decrypt mirror + parse snapshot, set arithmetic both directions
dupes.py       full SHA-256 per file, duplicate-id enumeration
diff.py        field-level diff of duplicate payload variants
(inline)       primary substring search + 2026-09-06 recipe timeline
```

Nothing was written, moved, deleted or committed in the store directory. No memory store object was
constructed. No file under `.synapse/` was modified -- read-only throughout.

### The primary moved under the audit, and the numbers held

`snapshot.json` was rewritten by the live Houdini process partway through this audit -- its mtime
advanced from 14:07 to 14:36 while these scripts ran. That is the running session flushing, not this
audit writing. The full set arithmetic was re-run against the freshly written file at 14:38:48:

```
snapshot rows 1162  distinct 1162
mirror distinct 1166
primary-only 0   mirror-only 4
['mem_1ed48dbc06ea', 'mem_3f27b6d52222', 'mem_cb73dd2c8061', 'mem_e2e9749cb3c3']
```

Identical. Every figure in this document survives a live rewrite of the primary.

---

*Every count in this document came from a script run against the live files on 2026-09-18, not from a
prior audit and not from a docstring.*
