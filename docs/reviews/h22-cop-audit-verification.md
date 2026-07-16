> Drop-week runbook steps 5 + 9 verification — copied verbatim from `.scout/scout-20260716-0946/VERIFICATION.md`
> (that directory is gitignored; this copy is the reviewable artifact). Probed build 22.0.368, hython fallback, bridge down.

# VERIFICATION.md — ASSAYER V1 Hard Gate — Runbook Step 5: COP Audit Refresh

**Run:** scout-20260716-0946 · **Date:** 2026-07-16
**Role:** ASSAYER. One question per candidate: does this API exist on the live target build.
**Target build (derived from probe, verbatim):** hou.applicationVersionString() -> "22.0.368" (both probe batteries, identical).
**Blocks:** G9 COP conformity pass.

---

## Probe path

- **Path 1 (live bridge, preferred): DOWN.** Direct socket probe, verbatim:
  socket.connect(('127.0.0.1',9999)) -> PORT 9999: CLOSED/UNREACHABLE -> TimeoutError timed out.
  No bridge build string obtainable -> no bridge/hython mismatch derivable.
- **Path 2 (hython fallback): USED.** HYTHON env -> C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe. Probed build recorded from the probe itself: **22.0.368**. H21 is uninstalled on this machine (drop day 2026-07-15) — no competing build.
- **Standing caveat:** headless hython differs from the graphical session for site-packages/GUI submodules. All verdicts below are node-type registration, instantiation, HOM class surface, and parm presence — install/build-determined, headless-safe. Behavioral items (cook output, op:-path plane suffix resolution) are marked PENDING-BEHAVIORAL. Per protocol, headless PASS is **PROVISIONAL until reconfirmed on the live bridge**.
- **Probe hygiene:** read-only + in-memory createNode/destroy, nothing saved, zero disk mutation. Two batteries, both exit 0, **0 probe errors**. Scripts: scratchpad cop_audit_probe.py / cop_audit_probe2.py; every load-bearing probe and output is quoted verbatim below.

---

## Inventory derivation (the audited list)

Blueprint said **21 tools [INFERENCE]**. Real inventory derived from the registry, not the blueprint:

- C:\Users\User\SYNAPSE\mcp_tools_cops.py -> TOOL_NAMES = **21** entries; DISPATCH_KEYS = 21, 1:1. **Blueprint count CONFIRMED (21).**
- Handlers: C:\Users\User\SYNAPSE\python\synapse\server\handlers_cops.py -> 21 _handle_cops_* methods present, 1:1 with the registry.
- WARN Doc drift (not a gate failure): the handlers module docstring says "20 handlers" — stale by one (cops_create_copnet was added later). Registry and handler set agree at 21.

---

## Headline verdicts (strategic)

1. **The legacy-COP2-removal contingency did NOT fire on 22.0.368.** cop2net, vopcop2gen, copnet all resolve and instantiate (the exact cop_type_survival() trio in handlers_cops.py). Both Cop and Cop2 categories exist. The _cop_missing_type_message path stays dormant on this build.
2. **HOM-02 CONFIRMED on 22.0.368, with a nuance the doc-scout note missed:** hou.CopNode.planes -> **False** (gone from the Copernicus node class), but hou.Cop2Node.planes -> **True** and live-callable (['C','A']). The planes()-consuming tools degrade on Copernicus nodes and still fully work on legacy nodes. No hard crash anywhere — every call site is try/except-guarded.
3. **SOPs-to-COPs heightfield migration is live on the Cop surface:** 18 height* Cop types incl. heightfield_erode; oceanspectrum/oceanevaluate/camera also True. **No audited tool emits a migrated type directly** — exposure is through passthrough type params and index-based wiring (flags below).
4. **Solver-family parm drift:** Cop block_end has iterations but **no** method/blocktype/blockpath/block_begin parms -> simulate-mode and explicit block binding silently no-op in 4 tools.
5. **limit aliases to clamp on the Cop surface** (resolved type differs from requested type; max/high absent -> threshold set silently no-ops).

---

## Per-tool verdicts — 21/21 adjudicated · **PASS 11 · CHANGED 10 · GONE 0**

Verdict semantics: **PASS** = every load-bearing emitted symbol resolves on 22.0.368 (guarded optionals may be absent — noted). **CHANGED** = tool still functions but part of its emitted surface resolves differently, silently no-ops, or degrades on this build. **GONE** = load-bearing symbol absent -> tool errors.

WARN Honesty bound: H21 is uninstalled and no H21 COP parm baseline was ever captured, so CHANGED = *H22 truth vs what the code emits*, not a proven H21-to-H22 delta. Some no-op parms may have been no-ops on H21 too.

| # | Tool | Verdict | HF-flag | Evidence (verbatim probe results on 22.0.368) |
|---|---|---|---|---|
| 1 | cops_create_network | **PASS** | — | /obj createNode("cop2net") -> created, resolved_type:"cop2net", child_category:"Cop2" |
| 2 | cops_create_copnet | **PASS** | **FLAG** | /obj createNode("copnet") -> created, child_category:"Cop". starter passthrough now reaches 18 height* + oceanspectrum/oceanevaluate/camera types |
| 3 | cops_create_node | **PASS** | **FLAG** | generic createNode passthrough works in both containers. Category straddle is caller-visible: in copnet "limit" resolves to "clamp"; noise/vopcop2gen/composite/over/edge -> OperationFailed: Invalid node type name; all five fine in cop2net. Migrated heightfield_*/ocean*/camera are now valid type values |
| 4 | cops_connect | **PASS** | **FLAG** | hou.CopNode.setInput -> True, hou.Cop2Node.setInput -> True. Tool API intact; H21-remembered **input indices** on Cop nodes are silently wrong where migration re-ordered inputs (step-4 sweep: Cop/light 3->8 inputs, mask 2->7; Cop/file gained size_ref, probe: input_labels:["size_ref"]) |
| 5 | cops_set_opencl | **PASS** | — | Cop opencl: kernelcode -> True, kernelname -> True. Legacy vopcop2gen: ALL kernel-parm alts (kernelcode/opencl_code/code/snippet) -> False -> handler raises its guarded ValueError (clean error, no corruption) |
| 6 | cops_read_layer_info | **CHANGED** | — | hou.CopNode.planes -> **False**, .xRes/.yRes/.depth -> False (live copnet instance class "CopNode" confirms). hou.Cop2Node.planes -> True, live call -> ['C','A']; xRes() -> 512. On Copernicus nodes returns thin result (no resolution/data_type, planes:[]); full on legacy. Guarded — no crash |
| 7 | cops_to_materialx | **PASS** | — | Structural surface only (hou.node, parm.set, op:-path string) — intact. PENDING-BEHAVIORAL: op:<path>/<plane> suffix semantics on Copernicus (planes -> layers) not verifiable headless. Native usdmaterial Cop type exists ('usdmaterial' in Cop nodeTypes() -> True) as modernization target |
| 8 | cops_composite_aovs | **PASS** | note | cop2net OK; Cop2 file OK filename1 -> True (file/channel/plane -> False — AOV plane selection silently no-ops, guarded); Cop2 composite OK maxInputs 3, over OK 3 (>3 AOVs guarded-dropped by maxNumInputs() check). If rebuilt on Cop surface: Cop file has NO filename1-style parms probed present and 1 input size_ref |
| 9 | cops_analyze_render | **CHANGED** | — | same planes/xRes evidence as #6; cook/errors -> True on both classes. Report degrades on Copernicus nodes (no resolution/planes), full on legacy |
| 10 | cops_slap_comp | **PASS** | — | setDisplayFlag: CopNode -> True, Cop2Node -> True; blend/opacity parm sets are None-guarded. H22 native slapcompimport -> True (modernization candidate, not a break) |
| 11 | cops_create_solver | **CHANGED** | — | Cop block_begin OK / block_end OK; block_end.iterations -> True; method/blocktype -> **False** (singlepass/simulate silently no-ops); blockpath/block_begin -> **False** on block_end (block_begin has blockpath -> True) -> explicit end-to-begin binding silently no-ops. Cop2 parent: block types Invalid node type name (Cop-surface-only tool) |
| 12 | cops_procedural_texture | **CHANGED** | — | primary vopcop2gen Cop2-only, creates OK, but type/freq/frequency/octaves/turb/resx/resy ALL -> False -> every setting silently no-ops (scaffold node only). In copnet: createNode("vopcop2gen") RAISES (Invalid node type name) so the "noise" fallback is dead code (raise-not-None trap) — and Cop has no plain "noise" anyway ("noise" in Cop -> False) |
| 13 | cops_growth_propagation | **CHANGED** | — | Cop parent: blocks OK; dilateerode OK (size -> False, falls to radius -> True, OK); blur OK (blursize -> False, falls to size -> True, OK); "limit" -> **resolves "clamp"**, max/high -> False -> threshold set silently no-ops; block_end.blockpath -> False silently no-ops. Graph builds and wires |
| 14 | cops_reaction_diffusion | **CHANGED** | — | Cop opencl OK kernelcode -> True; blocks OK iterations -> True; blockpath -> False silently no-ops. Native reactiondiffusion_block_begin/_end exist on 22.0.368 (both True) — doc-described paradigm now probe-confirmed. Placeholder kernel by design (unchanged) |
| 15 | cops_pixel_sort | **PASS** | — | Cop opencl OK kernelcode -> True, setInput OK, setDisplayFlag OK. On a cop2net parent opencl raises Invalid node type name (clean error; vopcop2gen fallback unreachable — raise-not-None) |
| 16 | cops_stylize | **CHANGED** | — | per-style category straddle: "edge" Cop2-only OK (size -> True); "edgedetect" Cop-only OK; each style's fallback chain dead (createNode raises, never returns None). quantize OK BOTH surfaces but levels/steps -> False on BOTH -> toon/posterize levels silently no-op everywhere. risograph (quantize+vopcop2gen) legacy-only |
| 17 | cops_wetmap | **CHANGED** | — | Cop blocks OK, blur OK (size), bright OK (bright -> True). block_end.method/blocktype -> **False** -> frame-by-frame **simulate mode silently lost** (load-bearing for temporal decay); blockpath -> False silently no-ops |
| 18 | cops_bake_textures | **CHANGED** | — | vopcop2gen Cop2-only creates OK; resx/resy -> False -> resolution silently never set. In copnet: _create_cop_node raises the legible migration RuntimeError (designed behavior, confirmed reachable). Native bakegeometrytextures + ::2.0 exist in Cop (prior probe run, this build) |
| 19 | cops_temporal_analysis | **PASS** | — | hou.frame/setFrame core HOM; cook -> True, errors -> True on both node classes. Playhead save/restore is pure HOM |
| 20 | cops_stamp_scatter | **CHANGED** | — | vopcop2gen Cop2-only creates OK; seed/copies/count ALL -> False -> every stamp parameter silently no-ops (bare scaffold node). copnet parent -> legible migration error |
| 21 | cops_batch_cook | **PASS** | — | cook(force=True) OK + errors OK both classes; pure iteration otherwise |

---

## SOPs-to-COPs heightfield migration — flagged tools

Migration surface confirmed live on 22.0.368 (Cop category, 384 types):

```
cop_heightfield_types: heightfield_clip, heightfield_erode, heightfield_maskbyfeature,
  heightfield_project, heightfield_slump, heightfield_strata, heightfield_terrace,
  heightfield_visualize, heightfield_xform, heightfield_xform2d, heightfieldtomono,
  heighttoambientocclusion, heighttocaustics, heighttonormal, heighttoshadow,
  monotoheightfield, normaltoheight, refractfromheight
cop_migration_markers: heightfield_erode=True, oceanspectrum=True, oceanevaluate=True,
  camera=True, noise=False, slapcompimport=True, usdmaterial=True, rop_image=True,
  reactiondiffusion_block_begin=True, reactiondiffusion_block_end=True
```

**Directly flagged (input space or wiring semantics now include migrated types):**
- **cops_create_node** — type passthrough: all 18 height* + ocean* + camera are now valid create targets; emitted networks can contain migrated nodes SYNAPSE has no parm/index knowledge for.
- **cops_create_copnet** — starter passthrough: same exposure, Copernicus container.
- **cops_connect** — index-based setInput on Cop nodes where the migration re-ordered/renamed inputs (step-4 miswire class). API PASS; H21-remembered indices are silently wrong.

**Informational (adjacent, not input-space):**
- **cops_composite_aovs** — legacy path unaffected; any Cop-surface rebuild inherits file's new size_ref input and absent filename1-style parm names.
- **No audited tool emits a heightfield-migrated type name directly.** cops_procedural_texture's "noise" fallback does NOT collide (plain "noise" absent from Cop).

---

## QUARANTINE

**None.** No candidate met absent-load-bearing-symbol on 22.0.368. Zero GONE.

## PENDING-BEHAVIORAL (not V1-gateable headless; do not treat as verified)

1. op:<path>/<plane> texture-path resolution against Copernicus layer naming (cops_to_materialx).
2. Whether Cop solver blocks bind implicitly without the removed block_end.blockpath/method parms (affects tools 11/13/14/17 semantics, not existence).
3. Cook-through output of scaffold tools (12/14/15/18/20 — placeholder-by-design).

All three require the live bridge (or a GUI session) -> escalate to SCOUTMASTER for the reconfirm pass; per protocol all PASS verdicts above are PROVISIONAL-headless.

---

## Verbatim probe record

Battery 1 (cop_audit_probe.py, hython 22.0.368, exit 0, stderr empty) — key probes as executed:
- hou.applicationVersionString() -> "22.0.368"
- sorted(hou.nodeTypeCategories().keys()) -> includes both "Cop" and "Cop2"
- obj.createNode("cop2net") -> ok, childTypeCategory().name() -> "Cop2"; obj.createNode("copnet") -> ok -> "Cop"
- per-type registration scan: [cname for cname,cat in hou.nodeTypeCategories().items() if hou.nodeType(cat, t) is not None] for the 16 emitted child types (full matrix in table evidence)
- functional instantiation of all 16 types inside a live copnet AND a live cop2net (createNode -> type().name() or OperationFailed)
- hasattr(hou.CopNode, "planes") -> False · hasattr(hou.Cop2Node, "planes") -> True (+ full method matrix)
- parm presence via n.parm(p) is not None or n.parmTuple(p) is not None on live nodes; n.type().maxNumInputs(); n.inputLabels()
- sorted(cats["Cop"].nodeTypes().keys()) filters for height* + marker membership; len -> 384

Battery 2 (cop_audit_probe2.py, exit 0) — legacy-surface instance truth:
- cop2net "file" instance: type(n).__name__ -> "Cop2Node"; n.xRes() -> 512; n.planes() -> ["C","A"]
- Cop2 parm matrices for file/composite/over/vopcop2gen/noise/limit/quantize/edge/bright/blur/colorcorrect/dilateerode (values quoted in the table)
- hasattr(hou.CopNode,"setDisplayFlag") -> True · hasattr(hou.Cop2Node,"setDisplayFlag") -> True

Raw JSON outputs (byte-complete) retained at scratchpad cop_audit_probe.out / cop_audit_probe2.out for this session; every verdict-bearing value is quoted above.

---

## Compressed summary (for SCOUTMASTER / G9)

21/21 adjudicated on 22.0.368 (probe-derived) · PASS 11 · CHANGED 10 · GONE 0 · quarantine 0 · bridge DOWN -> hython path, PASS provisional-headless · legacy COP2 survives (cop2net/vopcop2gen/copnet all live) · HOM-02 confirmed: CopNode.planes gone, Cop2Node.planes alive · CHANGED drivers: planes/xRes degradation (2), solver blockpath+method parm loss (4), limit-to-clamp alias (1 shared), vopcop2gen/quantize parm no-ops (4), stylize straddle (1) · HF-migration flags: cops_create_node, cops_create_copnet, cops_connect (+composite_aovs informational) · 3 PENDING-BEHAVIORAL escalated

---
---

# Runbook Step 9: Adjudicated-Document Symbol Probes (G9 Pass 2 image candidates + whitepaper TOP splat/ML names)

**Run:** scout-20260716-0946 · **Date:** 2026-07-16
**Role:** ASSAYER. One question per candidate: does this API exist on the live target build.
**Target build (derived from probe, verbatim):** hou.applicationVersionString() -> "22.0.368" (both batteries, identical).
**Rule enforced:** nothing from either external document enters code without this V1 verdict.

## Probe path

- **Path 1 (live bridge): DOWN.** PowerShell Test-NetConnection localhost:9999 -> False (port not listening). No bridge build string obtainable -> no bridge/hython mismatch derivable.
- **Path 2 (hython fallback): USED.** HYTHON env -> C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe. Probed build: **22.0.368**. Per protocol, every PASS below is **PROVISIONAL-headless until reconfirmed on the live bridge**. All verdicts are symbol-existence / node-type registration / instantiation / parm presence — install-determined, headless-safe (note: headless dir(hou) omits GUI submodules; none of these candidates are GUI-scoped).
- **Probe hygiene:** read-only + in-memory createNode/destroy inside a scratch topnet, nothing saved, zero disk mutation. Batteries: scratchpad step9_probe.py / step9_probe2.py, both exit 0. Battery-1 stderr contained only two cosmetic Cop/fractalnoise handle-binding warnings (not probe errors).

---

## (a) hou.imageResolution + image-header-reading paths — G9 Pass 2

| Candidate | Verdict | Verbatim evidence (22.0.368) |
|---|---|---|
| hou.imageResolution | **PASS** (provisional-headless) | type -> "function"; live call hou.imageResolution($HFS/houdini/pic/Mandril.pic) -> (256, 256); doc head -> "Return the resolution of an image in a file." |
| hou.imageDepth | **PASS as enum ONLY — QUARANTINE any use as a header-reader** | exists, but type -> "type" (enum): members Float16/Float32/Int16/Int32/Int8; doc -> "Enumeration of image depths (data formats) for representing the pixels"; calling it hou.imageDepth(path) -> RAISED AttributeError: No constructor defined |
| hou._imagePlanes | **PASS-exists, PRIVATE-API flag** | underscore-private function; live call hou._imagePlanes(Mandril.pic) -> ("C",) [one-plane tuple]. Exists and works, but private surface — do NOT emit in production without SCOUTMASTER ruling; no public plane-listing equivalent exists on this build |
| hou.loadImageDataFromFile | **PASS-exists** (pixel read, NOT header-only) | type -> "function"; docstring empty. Reads full image data — heavier than a header probe; usable fallback only if pixel data is wanted anyway |
| hou.saveImageDataToFile | exists (builtin_function_or_method) | write path, out of scope for header reading |
| hou.imageInfo | **QUARANTINE — absent** | hasattr -> false |
| hou.imageHeader | **QUARANTINE — absent** | hasattr -> false |
| hou.readImageHeader | **QUARANTINE — absent** | hasattr -> false |
| hou.imageBounds | **QUARANTINE — absent** | hasattr -> false |
| hou.imageDataType | **QUARANTINE — absent** | hasattr -> false |
| hou.imagePlanes (public) | **QUARANTINE — absent** | hasattr -> false (only the private _imagePlanes exists) |
| hou.loadImageData / hou.loadImageDataAsGrayscaleArray / hou.imageFileDataAsString | **QUARANTINE — absent** | hasattr -> false (all three) |

**Full image surface, verbatim dir scan** (sorted(n for n in dir(hou) if "mage" in n)):
ImageLayer, NetworkImage, _ImageLayerTuple, _ImageLayerTupleGenerator, _imagePlanes, _loadImageDataFromFileWithAllPlanes, _lookupImageLayer, geometryViewportBackgroundImageFitMode, imageDepth, imageLayerBorder, imageLayerProjection, imageLayerStorageType, imageLayerTypeInfo, imageResolution, loadImageDataFromFile, saveImageDataToFile, viewportBGImageView

**Ruling for G9 Pass 2:** the ONLY public header-only reader on 22.0.368 is hou.imageResolution(path) (resolution). There is NO public API for plane names / depth / metadata from a file header — plane listing exists solely as private hou._imagePlanes, and depth exists solely as the hou.imageDepth enum. Any document text implying a richer public header-reading API is phantom-shaped on this build.

---

## (b) TOP splat / ML training node names — whitepaper adjudication

**Whitepaper name top::gaussian_splat_train: QUARANTINE — PHANTOM CONFIRMED.**
Verbatim: hou.nodeType(cats["Top"], c) is not None, for each spelling:
top::gaussian_splat_train -> false · gaussian_splat_train -> false · gaussiansplattrain -> false · gaussiansplat_train -> false · gaussiansplatting_train -> false.
Not present in the full Top registry either (183 Top types enumerated; regex splat|gauss|train|ml matched only the list below). Do NOT emit this name.

**Actual nodes, VERIFIED (registered + instantiated in a live topnet, create -> identity -> destroy):**

| Type name (emit this) | description() | Identity evidence |
|---|---|---|
| ml_traingsplats | "ML Train GSplats" | **the gaussian-splat trainer.** 156 parms; verbatim sample: datasetfolder, dataset_1..3, checkpointfile/checkpoints/checkpointsfolder, enabledensification/densification/densificationsched, refinestartiter/refinestopiter/mcmcrefinestartiter/mcmcrefinestopiter/refinescale2dstopiter, sh0lr/shnlr/shdegreeinterval, trainingdevice/overridedevice/deviceid, outputdirectory/outputbasename, seeddataset, cacheimages |
| ml_preprocessgsplats | "ML Preprocess GSplats" | 46 parms; sample: camerasource, cameras, imagesource, exrimagedir, datasetbasename, outputdirectory, resolution |
| ml_traincomputervision | "ML Train Computer Vision" | instantiates ok |
| ml_trainneuralcellularautomata | "ML Train Neural Cellular Automata" | instantiates ok |
| ml_trainoidn | "ML Train OIDN" | instantiates ok |
| ml_trainregression | "ML Train Regression" | instantiates ok |
| ml_trainstyletransfer | "ML Train Style Transfer" | instantiates ok |
| ml_regressionkernel | "ML Regression Kernel" | instantiates ok |
| ml_preprocesscomputervision / ml_preprocessoidn | "ML Preprocess Computer Vision" / "ML Preprocess OIDN" | instantiate ok |
| labs::ml_cv_rop_synthetic_data::1.0 and ::1.1 | "Labs ML CV ROP Synthetic Data" | instantiate ok |

**Adjacent splat surface on 22.0.368 (all-category scan, verbatim):**
- Cop: rasterizegsplats
- Sop: bakegsplat, surfacesplat, labs::splatter, labs::fast_gaussian_curvature::1.0
- Data (recipes): sidefx::recipe::ml::traingsplatsfromkarma (+ cop/paint splatter recipes)
- Driver: ml_exampleraw · Sop ML example/pose/regression family present (full list in step9_probe.out)

---

## QUARANTINE (step 9)

1. top::gaussian_splat_train (+ 4 spelling variants) — absent from the Top registry; whitepaper name is phantom. Correct name: ml_traingsplats (preprocess: ml_preprocessgsplats).
2. hou.imageInfo, hou.imageHeader, hou.readImageHeader, hou.imageBounds, hou.imageDataType, hou.imagePlanes, hou.loadImageData, hou.loadImageDataAsGrayscaleArray, hou.imageFileDataAsString — all absent from dir(hou) on 22.0.368.
3. hou.imageDepth(path) *as a callable header-reader* — symbol exists but is an enum; calling raises "No constructor defined".
4. hou._imagePlanes — exists + live-callable but underscore-private; quarantined from production emission pending SCOUTMASTER ruling.

## Verbatim probe record (step 9)

- Scripts: scratchpad step9_probe.py (battery 1) / step9_probe2.py (battery 2), both run under HYTHON 22.0.368, both exit 0. Raw JSON: scratchpad step9_probe.out (byte-complete) + battery-2 stdout captured in-session.
- Load-bearing probes as executed: hou.applicationVersionString() -> "22.0.368" · hou.imageResolution(pic) -> (256, 256) · hou._imagePlanes(pic) -> ("C",) · hou.imageDepth(...) -> AttributeError: No constructor defined · hou.nodeType(cats["Top"], "top::gaussian_splat_train") is not None -> False · len(cats["Top"].nodeTypes()) -> 183 · topnet createNode("ml_traingsplats").type().description() -> "ML Train GSplats" (destroyed after read).

## Compressed summary (step 9, for SCOUTMASTER)

Build 22.0.368 (probe-derived) · bridge DOWN -> hython path, all PASS provisional-headless · (a) hou.imageResolution VERIFIED live-callable ((256,256) on Mandril.pic); it is the ONLY public header-only reader — plane names private-only (_imagePlanes), depth enum-only (imageDepth); 9 phantom-shaped image names quarantined · (b) top::gaussian_splat_train PHANTOM CONFIRMED (5 variants absent from 183-type Top registry); real trainer = ml_traingsplats (+ ml_preprocessgsplats), full ML TOP train family enumerated + instantiated · quarantine: 4 classes · escalations: live-bridge reconfirm pass; SCOUTMASTER ruling on private _imagePlanes.
