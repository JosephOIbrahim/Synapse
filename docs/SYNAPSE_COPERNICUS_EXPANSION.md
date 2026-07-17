# SYNAPSE COPERNICUS EXPANSION — frozen build spec (C.3 · C.4 · C.10)

**`docs/SYNAPSE_COPERNICUS_EXPANSION.md`** · Repo: `C:\Users\User\SYNAPSE` (branch per orchestrator). All paths repo-relative.
**Status: RATIFIED SCOPE, BUILD-READY PAPER.** The three cycles this spec covers — `C.3-H22-neural-cops`, `C.4-H22-scaffold-rebuild`, `C.10-H22-terrain-exposure` — are `ratified: true` in `harness/state/flywheel_queue.json` (human: Joe, 2026-07-16 Copernicus-expansion directive, verbatim in each cycle's `note`; all other C.x cycles remain held). This spec is the MODE A paper that makes them executable with no design decisions left open except the OPEN DECISIONS block below.
**Governing gate:** merge-to-main, **per cycle, human** (blueprint §8 gate registry, mechanized in `docs/H22_AGENT_HARNESS.md` — same gate the port manifest names). No agent merges.
**Relay leg:** Leg 3-adjacent — MODE B feature cycles under the CTO roadmap's NEW-CAPABILITY lane (`docs/reviews/h22-cto-roadmap-2026-07-16.md` rows C-3/C-4; C.10 deposited directly to the queue), sequenced against the G1 `cops-1`/`cops-2` port waves per §Sequencing.
**Target build:** Houdini **22.0.368** — probe-derived in all three probe legs (`hou.applicationVersionString() -> "22.0.368"`, live WS bridge `ws://localhost:9999/synapse`, protocol 4.0.0), and in the COP audit (hython fallback, same build string).
**Grounding (verified this dispatch, read-only):** master = origin/master = `32dd597` "release: v5.26.0 — H22 live-verified"; tag `v5.26.0` exists; W.4 merge commit `34f41f7` in master history. **The queue's sequencing precondition ("builds start ONLY after W.4 merges … and the v5.26.0 push lands") is SATISFIED.** Suite floor of record: `harness/verify/suite_baseline.json` = **4275 / 0 / 87** (v5.24.0 floor re-derivation, 2026-07-14); last observed full-suite green post-W.4 merge was 4387/0/97 (queue note W.4).

---

## OPEN DECISIONS (human rules; everything else in this spec is complete either way)

**OD-A — Port-manifest inventory drift from new tools.** `docs/PORT_WAVE_MANIFEST.md` freezes the port inventory at **115** registry tools ("Wave total: … = 115"), and `tests/test_phase0c_doc1_toolcount.py` binds the CLAUDE.md banner ("115 MCP tools registered") to `len(TOOL_DEFS)`. C.3 adds 2 tools and C.10 adds 1 → registry lands at **118**. The banner bump ships in the same commit as each tool (the test forces it). What the manifest does about the delta is a human call:
- **(a)** one-line manifest addendum: the 3 new tools join `cops-2` (or a `cops-3` addendum wave) when the port reaches COPs;
- **(b)** the new tools are declared born-on-legacy-WS permanently and excluded from the port DoD count (documented exception, like ⚑OD-3).
- **Recommended: (a).** The new handlers are ordinary `TOOL_DISPATCH → send_command → handlers_cops.py` tools (§C.3 design) — nothing exempts them from the strangler-fig endgame.

**OD-B — C.4 scope: does the native reaction-diffusion pair ride this cycle?** The ratified queue title scopes C.4 to `procedural_texture/stamp_scatter/bake_textures/stylize`. But the C-4 roadmap row lists the **native RD block pair** among probe-confirmed modernization targets, and probe Leg A banked its complete template-level truth (model menu Gray-Scott/Kenjiro Maginu; `feed`/`kill` live on the **end** node; `blockpath` on **begin** only — verbatim in §Evidence). Re-authoring `cops_reaction_diffusion` from placeholder-kernel scaffold onto the native pair is a bounded, probe-backed rebuild — but it expands the ratified 4-tool title.
- **(a)** include RD re-author in C.4 (5th deliverable, D4.5 below is pre-written for it);
- **(b)** hold RD at scaffold semantics (the `cops-2` trap's default), bank the probe truth, new cycle later.
- **Recommended: (a)** — the truth is already paid for and the tool is currently a placebo; but the title expansion is the human's to grant.

**OD-C — C.10 verb name.** The queue entry names no verb. This spec uses **`cops_terrain_setup`** throughout as the provisional name (fits the `cops_<verb>` registry convention, reads in the palette's verb×context grid). Alternatives: `cops_terrain`, `cops_heightfield_chain`. Naming is the human's; a rename before build is a find-replace on this spec only.

**OD-D — W.4b(3) subsumption.** Unratified deposit `W.4b-H22-solver-followups` item (3) — the dead `createNode("limit")` fallback in the stylize toon branch (`handlers_cops.py:1649` per the deposit) — sits inside the function C.4 re-authors (D4.4). Recommend ruling that C.4 **subsumes** W.4b(3) (record the subsumption in the queue note) rather than two cycles editing the same lines. W.4b items (1)/(2) are untouched by C.4 and stay in their own deposit.

---

## Definition of Done (spec level)

The Copernicus expansion is DONE when all three cycles are human-merged to master, in the §Sequencing order (or a human-justified reorder), and:

1. **Every emitted node-type string and parm name in the new/re-authored code is probe-backed** — quoted from the three probe legs (§Evidence) or from `harness/notes/verified_connectivity_22.0.368.json` — or the code path that would emit it is gated behind a completed OWED probe (P-1/P-2 below). No exception; `phantom_clean` covers `hou.*` symbols but **not** node-type strings or parm names, so this is a spec-level discipline enforced by the per-cycle conformance tests.
2. **No silent no-op survives in the C.4 cluster:** every parameter the four (or five, OD-B) rebuilt tools accept is either authored on a verbatim-probed parm or reported un-authored in the response envelope (the W.4 `levels_applied` pattern, generalized — see D4 honesty contract).
3. **C.3 never claims a mask/depth capability the host cannot deliver:** model-absent ⇒ honest failure envelope (never a silently-empty layer), GPU state reported not guessed, and `synapse_doctor` carries the model/GPU preflight as a first-class check.
4. **C.10 wires by probed labels only** — every `setInput` in the terrain surface resolves through `python/synapse/core/wiring.py::wire_by_label` (`:192`) against the per-major catalog (`connectivity_22.json`), or by index 0 where the probe verified single-input semantics; no H21-remembered indices, no guessed labels.
5. **Registry/banner/palette/emitted-surface wiring complete per new tool** (the 8-step checklist in §C.3 design), with `tests/test_phase0c_doc1_toolcount.py` green at the new count.
6. **Code/corpus both:** the COP-02 precondition prose is seeded into the H22 reference corpus in the same cycle that ships C.3 (divergence rule — fixing code while `rag/` re-teaches the old world is a known failure class).
7. **Guardrails + floor:** `phantom_clean` and `suite_baseline` GREEN every cycle; full `pytest tests/` ≥ 4275/0 floor; live-marked tests green on the live bridge before each cycle's merge-ready claim (marker `live`, `pyproject.toml:93-95`).
8. **Owed probes discharged before the code that needs them:** P-1 (quiet-scene instantiation/cook pass) before C.3's cook-path test and C.10's label capture; P-2 (stamp-scatter target enumeration) before D4.3's modern branch is written.

---

## Evidence base — the three probe legs, tiered

All three legs ran 2026-07-16 against the **live WS bridge** on 22.0.368 (not hython — verdicts are **V1-LIVE**, install-determined registry/`parmTemplateGroup()` truth). All three legs hit **SCENE_BUSY**: `/obj/_recon_planes2` (joined mid-run by `_w4assay_net`) persisted through initial check + ≥60s re-check + final confirm; per politeness protocol **zero nodes were created, cooked, or destroyed** in any leg. Consequence: everything type-level below is V1-LIVE; everything instance-level (dynamic parms, `inputLabels` on live nodes, cooks) is **OWED** (probe P-1). The prior COP audit (`docs/reviews/h22-cop-audit-verification.md`) is the fourth evidence source — same build, hython path, verdicts **V1-HEADLESS-PROVISIONAL** where behavioral.

### Leg A — C.4 modernization targets (verbatim highlights)

| Target | V1-LIVE truth (verbatim from probe) |
|---|---|
| `bakegeometrytextures::2.0` (Cop) | Registered, `::1.0` base also registered. 72 parms; bake targets `bakenormal/bakeworldnormal/bakeposition/bakeocclusion/bakecurvature/bakeedge/bakecavity/bakethickness/bakeheight/bakealpha` (+ per-target `samples/dist/bias/type`), `tracer/tracingmode`, `uvattribute`, `udim/overrideudim`, `enablematchpieces/pieceattrib`, `quicksetup`, `attribs`; maxInputs 5. **NO resolution parms on the node — resolution lives on the copnet container** (Object-type `copnet` parms verbatim: `setres`, `res`, `resmenu`, `plane_size`). Legacy `resx/resy` have no equivalent. |
| `reactiondiffusion_block_begin` / `_end` (Cop) | begin = `[signature, blockpath, sepparm, continuousactivation]`, maxInputs 10. end = `model` (menu Gray-Scott / Kenjiro Maginu), `simulate` (Toggle, default True), `iterations` (10), `feed` (0.3), `kill` (0.3707), `alpha/beta/gamma(+raw)`, `gsdiffa/gsdiffb`, `kmdiffa/kmdiffb`, `reactionscale`, `startframe`, `substeps`, `timescale`, `cacheenabled`; maxInputs 2. **`blockpath` exists on begin and does NOT exist on end** — template-level confirmation of the W.4 live binding truth (author `begin.blockpath='../<end>'`; implicit binding is dead). Feed/kill rates live on the **end** node. |
| `usdmaterial` (Cop) | Registered; **ZERO type-level parm templates** (`usdmaterial_parms=[]` verbatim); maxInputs 2048. Pure input-driven aggregator. Instance-level dynamic parms UNKNOWN (SCENE_BUSY) — **do not author code assuming named parms exist on it.** |
| `slapcompimport` (Cop) | Registered; parms `[reload, live (Toggle, default True), slapcompcameraspace, slapcompaddaovs, aovs (Folder/multiparm)]`; maxInputs 2048. Not a file loader. |
| stylize levels (audit #16 follow-up) | Capability **renamed, not gone**: Cop `quantize` has `method` menu verbatim `['width','segments']` (default 1 = segments) + `segments` Int (default 16) — this IS the levels control. Cop2 `quantize` = `step` Float (0.1) + `quantize` menu `['optimal','here']`. Cop stylize-name regex scan matched only `['quantize','ramp']`. **Already consumed by W.4:** `handlers_cops.py:147` `_set_quantize_levels` authors exactly this (verified this dispatch). |

### Leg B — C.3 neural preconditions (verbatim highlights)

| Fact | V1-LIVE truth |
|---|---|
| Node types | `neural_layertomask_sam2`, `neural_layertodepth_moge2`, `denoiseai`, `neural_cellularautomatacore/-decode` all in `hou.nodeTypeCategories()['Cop'].nodeTypes()`. |
| SAM2 parms (37 total) | `modelpath` (String, default `shfs:/houdini/nodes/cop/neural_imagetomask_sam2/onnx/v1/` — note dir says *imagetomask*, type says *layertomask*), `model` (menu `('large','tiny','custom')`, default `tiny`), `downloadmodels` (Button), `usethreshold`/`threshold` (Toggle True / Float 0.5), `provider` (menu, `defaultExpression 'automatic'`, **menuItems() EMPTY at type level — dynamic, instance-only ⇒ OWED**), `deviceid` (Int 0). Prompt inputs (points/bbox) exist among the 37 but were not verbatim-enumerated ⇒ **not emit-able in v1**. |
| MoGe-2 parms (33 total) | `model` (menu `('moge-2-vitl-normal','custom')`), `modelfile` (String, default `shfs:/houdini/nodes/cop/neural_imagetodepth_moge2/onnx/moge-2-vitl-normal_v1.onnx`), `downloadmodels`, `provider` (dynamic, OWED), `deviceid`; plus verbatim-named `metricscale, applyskymask, removeedges, gsplat/creategsplat, camera, ransac*`. |
| `denoiseai` | 4 parms (`denoiser`='oidn', `auxareclean`, `prefilteraux`, `onlycpu`). **No modelpath/downloadmodels/provider/deviceid — OIDN is BUNDLED** (`$HFS/bin/OpenImageDenoise{,_core,_device_cpu,_device_cuda}.dll` present). The download preflight does NOT apply to it. |
| Model presence | **Filesystem check, not a hou call:** the `shfs:` scheme does NOT expand via `hou.text.expandString` (returned verbatim). Map `shfs:/<rest>` → `expandString('$SHFS') + '/<rest>'` then `os.path`. `$SHFS = C:/PROGRA~1/SIDEEF~1/shfs` (exists). On this machine SAM2/MoGe-2 models are **ABSENT** — `$SHFS/houdini/nodes/cop/` contains only the `neural_cellularautomatacore/onnx/denim/v1/` payload (which proves the `$SHFS/houdini/nodes/<cat>/<node>/` install layout). `$SHFS` is under Program Files ⇒ Download Models likely needs elevation. |
| GPU accessor | `hou.opencl.devices(device_type)` V1-LIVE — **required positional arg** (no-arg call raises). `hou.openCLDeviceType` members: **CPU, GPU only** (no 'automatic'/'directml') — OpenCL presence is a SEPARATE axis from ONNX execution-provider selection. This box: GPU = RTX 4090, CPU = TR PRO 7965WX. NWS-05's "locate the factory" open item is CLOSED. |
| Cook | NOT_RUN — doubly blocked (SCENE_BUSY + models absent anyway). **Empty-vs-real output verdict OPEN** ⇒ P-1. |

### Leg C — C.10 terrain exposure (verbatim highlights)

| Fact | Truth |
|---|---|
| Cop registry | 384 Cop types total [V1-LIVE]. `height*`-prefix scan → **15 types**: `heightfield_clip/_erode/_maskbyfeature/_project/_slump/_strata/_terrace/_visualize/_xform/_xform2d, heightfieldtomono, heighttoambientocclusion/-caustics/-normal/-shadow`. Plus `oceanevaluate/oceanspectrum` and a 6-type camera family. |
| **Reconciliation note (both probes are right)** | The audit's "18 height*" list (`h22-cop-audit-verification.md:81-85`) additionally contains `monotoheightfield, normaltoheight, refractfromheight` — a **substring**-family list of 18; Leg C's 15 is the **prefix** subset of the same registry. Leg C's "audit miscount" framing and its own "15+2 ocean+1 camera = 18" arithmetic are label-semantics noise, not a registry disagreement. Authoritative family for this spec: **the audit's 18 names ∪ ocean pair**, all V1 on 22.0.368. |
| No Cop terrain generator | `heightfield_noise` and bare `heightfield` do NOT exist in Cop (SOP-only). Base = generic 2D generator (`fractalnoise`/`worleynoise`/`ramp`/`constant`) feeding the `height` layer. |
| Parm surfaces (V1-LIVE, type level) | `fractalnoise` 42 parms (incl. `amp, elementsize, elementscale, noisetype, fractaltype, oct, lac, rough`, `post_*` block); `heightfield_erode` 24 (incl. `simulate, iterations, seed, erodability, flow, erosion, deposition, cutangle, reposeangle`); `heightfield_maskbyfeature` 29 (incl. `maskbyslope, minangle/maxangle, maskbyheight, maskbycurvature, maskbyocclusion, sloperamp/heightramp/...`); `heightfield_visualize` 11 (`heightscale, heightoffset, usetint, tint, colorramp, maskramp, ...`); `sopimport` 2 (`usesoppath, soppath`); `geotolayer::2.0` 7; `layertogeo::2.0` **0 parms**; Sop `copnet` ("COP Network") 54-parm ROP-style sibling `Sop/heightfield_output` is **disk export, not the live bridge**. |
| Catalog state (verified this dispatch) | `harness/notes/verified_connectivity_22.0.368.json` and packaged `python/synapse/cognitive/tools/data/connectivity_22.json` are both 293 entries, `houdini_version` 22.0.368. `Cop/heightfield_erode` IS cataloged with `input_labels ["height","debris","sediment","flow","erodability","rainfall"]`, `output_labels ["height","debris","sediment","flow"]`, `instantiated: true`. `Cop/{oceanspectrum,oceanevaluate,sopimport}` cataloged. **17 terrain-surface types uncataloged** (all other height*, `fractalnoise`, `geotolayer`, `layertogeo`, …) — `hou.NodeType.inputLabels` does not exist on Cop types (hasattr False, V1-LIVE), so labels require instantiation ⇒ P-1. |
| SOP bridge | Pair exists at type+parm level [V1-LIVE], **cook UNVERIFIED**: SOP→COP = `sopimport` (+ `geotolayer{,::2.0}`); COP→SOP = `layertogeo{,::2.0}` + Sop `copnet` evaluator. No `heightfield_import`-named Cop. |

### OWED probes (preconditions, not deliverables)

- **P-1 — quiet-scene instantiation + cook pass** (blocked SCENE_BUSY in all three legs; re-run when `/obj` is clear of `_recon_*`/`_w4assay_*`): instantiate and capture (a) SAM2/MoGe-2 **instance-level provider menu items**; (b) `usdmaterial` dynamic/instance parms; (c) live `inputLabels()` for `fractalnoise`, `heightfield_maskbyfeature`, `heightfield_visualize`, `geotolayer::2.0`, `layertogeo::2.0` (+ any C.10 chain member not yet cataloged); (d) fractalnoise `noisetype`/`fractaltype` **menu tokens** (names probed, tokens not); (e) minimal cooks: `bakegeometrytextures::2.0`, bound RD pair, and — once models are downloaded — the SAM2 empty-vs-real mask verdict. Output lands as a dated note under `harness/notes/` + a connectivity-catalog regen (both files, hash-stamped).
- **P-2 — stamp-scatter modern-surface enumeration.** No probe leg captured a Cop-surface successor for `cops_stamp_scatter` (Leg A did not target one; the audit only proved the legacy `vopcop2gen` parms dead). Regex scan of the 384 Cop types (`stamp|scatter|tile|repeat|mosaic|pattern`) + parm capture of candidates. **D4.3 does not build until P-2 lands.**
- **Escalation carried:** whether `/obj/_recon_planes2` is an active leg or debris from the 2026-07-16 W.1b planes probe is a SCOUTMASTER call (Leg A escalated it; unresolved as of this spec).

---

## CYCLE C.4 — COP scaffold rebuild cluster (build order: FIRST)

**Queue id:** `C.4-H22-scaffold-rebuild` (`ratified: true`). **Roadmap row:** C-4, P2 "silent-noop floor".
**Scope:** re-author the four audit-CHANGED scaffold tools onto the modern Cop surface — `cops_procedural_texture` (#12), `cops_bake_textures` (#18), `cops_stamp_scatter` (#20), and the residual `cops_stylize` (#16) straddle — **same tool names, no new registry rows** (behavior change under a ratified feature cycle, exactly the "separate, ratified feature" the port manifest's cops-2 trap reserves). Plus small in-file doc-drift fixes (below). RD is OD-B.

### The probe-verified truth it builds on

- Audit verdicts (V1, 22.0.368): #12 — `vopcop2gen` Cop2-only; `type/freq/frequency/octaves/turb/resx/resy` ALL False ⇒ every setting silently no-ops; the copnet "noise" fallback is dead code (createNode **raises**, never returns None; plain `noise` absent from Cop). #18 — `resx/resy` False ⇒ resolution never set; copnet parent raises the legible migration RuntimeError (`_create_cop_node`, `handlers_cops.py:293` — designed, confirmed reachable). #20 — `seed/copies/count` ALL False ⇒ every stamp parameter no-ops. #16 — per-style category straddle with dead fallback chains (raise-not-None); `risograph` legacy-only.
- Leg A: `bakegeometrytextures::2.0` full parm surface; **resolution on the copnet container** (`setres`/`res`); quantize/segments (already fixed by W.4 — `_set_quantize_levels`, `handlers_cops.py:147-174`, verified).
- Leg C: `fractalnoise` 42-parm surface = the modern procedural-texture generator.
- **Honesty bound (audit, verbatim):** "H21 is uninstalled and no H21 COP parm baseline was ever captured, so CHANGED = *H22 truth vs what the code emits*, not a proven H21-to-H22 delta." C.4 claims **repairs against H22 truth**, never "regression fixes."

### Design

All edits inside `python/synapse/server/handlers_cops.py` (2,152 lines this dispatch; handlers at `:1164` procedural_texture, `:1595` stylize, `:1841` bake_textures, `:2011` stamp_scatter). Branch on the parent's child category (the file's existing Cop/Cop2 pattern): **legacy Cop2 path preserved verbatim** (cop2net/vopcop2gen survive on 22.0.368 — audit headline 1; sunsetting them is CTO-04's cycle, not this one); **modern Cop path re-authored**:

- **D4.1 `cops_procedural_texture` (Cop branch):** create `fractalnoise` in the copnet; map payload → probed parms: `octaves→oct`, `frequency→1.0/elementsize` (frequency is the legacy vocabulary; `fractalnoise` has no freq parm — the reciprocal mapping is stated in the envelope as `mapped_to: elementsize`), amplitude passthrough → `amp`. `noise_type` is authored **only after P-1(d)** captures the `noisetype` menu tokens; until then the payload key is accepted, un-authored, and reported `noise_type_applied: false` (never guessed). `resolution` → **container** `setres=1` + `res` parmTuple (Leg A truth), never node-level `resx/resy`.
- **D4.2 `cops_bake_textures` (Cop branch):** create `bakegeometrytextures::2.0` (versioned type per COP-03: `::`-namespaced, never `-2.0`); map `map_types` → probed toggles (`normal→bakenormal`, `ao→bakeocclusion`, `curvature→bakecurvature`, `position→bakeposition`; plus new-in-H22 offers `worldnormal/edge/cavity/thickness/height/alpha` accepted under the same names); `high_res/low_res` SOP paths → the node's geometry inputs via `sopimport` (cataloged, out-label `geometry`) — exact input indices confirmed at build time from the P-1 label capture or by index with `maxInputs 5` bound. `resolution` → container `res` (same rule as D4.1). **v1 bakes in-graph only — no disk export** (no `rop_image`, no `touches_disk`; export is a follow-on so the APPROVE-gate surface is untouched).
- **D4.3 `cops_stamp_scatter` (Cop branch):** **blocked on P-2.** Until P-2 names a probed Cop-surface target, the Cop branch keeps the legible migration error (current designed behavior) — an honest refusal beats a rebuilt placebo. The Cop2 branch's dead parm-sets (`seed/copies/count`) are removed and the envelope reports `scaffold: true, parms_applied: []` honestly.
- **D4.4 `cops_stylize` residue:** delete the dead per-style fallback chains (audit: createNode raises `OperationFailed`, so every `or`-fallback is unreachable); replace with explicit per-surface style tables (Cop: `edgedetect`, `quantize`+`_set_quantize_levels`, `ramp`; Cop2: `edge`, `quantize(step)`, `vopcop2gen` risograph) and a clean per-style "not available on this surface" ValueError for the rest. Subsumes W.4b(3)'s dead `"limit"` literal if OD-D rules yes.
- **D4.5 (only if OD-B = (a)) `cops_reaction_diffusion` (Cop branch):** native `reactiondiffusion_block_begin/_end` pair; `begin.blockpath = '../<end_name>'` (W.4's live-verified binding shape); `feed/kill/model/iterations/simulate` on the **end** node per Leg A verbatim. Placeholder-kernel scaffold path retired on the Cop branch; Cop2 branch unchanged.
- **D4.6 doc-drift sweep (same commit):** `handlers_cops.py:8` "20 handlers" → true count; `:4` "Houdini 21 Copernicus" → dual-build framing; `mcp_tools_cops.py:3,9` "Houdini 21" likewise; GROUP_KNOWLEDGE scaffold sentences updated to the post-rebuild truth (`mcp_tools_cops.py:17-24`).

**Honesty contract (applies to every D4 deliverable):** every payload key is either authored on a verbatim-probed parm or echoed back with `<key>_applied: false` + reason — the generalized `levels_applied` pattern. This is the W.4b(2) lesson (inconsistent applied-verdict coverage) applied from birth. Cook-through remains out of the handlers (cooking stays `cops_batch_cook`'s job); the audit's PENDING-BEHAVIORAL #3 cook verdicts land via P-1, not via handler-side cooks.

### Tests

- **Unit** (`tests/test_cops.py` extension or `tests/test_cops_rebuild.py`): fake-`hou` patched at **handler-module globals** (the fake-residency trap — never `sys.modules` plants); per-tool: modern-branch parm authoring against a fake exposing the probed names; applied-verdict envelope for a fake missing a parm; container-resolution routing; stylize style tables both surfaces; migration-refusal path for D4.3.
- **Live-marked** (`tests/test_h22_cops_rebuild_live.py`, the `test_h22_cops_solver_live.py` skipif pattern, marker `live` per `pyproject.toml:93`): create a fresh copnet, run D4.1/D4.2 (+D4.5 if ruled in), assert probed parms authored + `levels_applied`-style verdicts all true, cook via `cops_batch_cook`, destroy. No hip save.
- **Conformance:** a test pinning every node-type string and parm name the rebuilt Cop branches emit against a frozen fixture list quoted from this spec's Evidence tables (spec-drift fails loud).

### DoD per deliverable (C.4)

| Deliverable | Done when |
|---|---|
| D4.1 procedural_texture | Cop branch emits `fractalnoise` only; probed-parm mapping live-verified; `noise_type` honest-deferred until P-1(d); container-res authored; envelope verdicts complete |
| D4.2 bake_textures | Cop branch emits `bakegeometrytextures::2.0`; map_types→probed toggles; container-res; no disk export; live create+cook green |
| D4.3 stamp_scatter | P-2 ruled: either probed rebuild green, or honest-refusal + Cop2 dead-set removal shipped with `scaffold:true` envelope |
| D4.4 stylize residue | zero unreachable fallbacks remain; per-surface style tables; unsupported style = clean error; (OD-D) `"limit"` literal gone from emitted surface |
| D4.5 (OD-B) reaction_diffusion | native pair, begin-side blockpath, end-side feed/kill/model; live bound cook green |
| D4.6 doc drift | handler count + H21 strings corrected in both files; GROUP_KNOWLEDGE truthful |
| Cycle gate | suite ≥ floor · phantom_clean GREEN · conformance test green · human merge |

---

## CYCLE C.3 — neural COP tools with preflight honesty (build order: SECOND)

**Queue id:** `C.3-H22-neural-cops` (`ratified: true`). **Roadmap row:** C-3, P3; COP-01 (VERIFIED, escalated) + COP-02 (the precondition truth) — `harness/notes/h22_doc_candidates.json:228-251`.
**Scope:** two new MCP tools — **`cops_segment_mask`** (SAM2, `neural_layertomask_sam2`) and **`cops_estimate_depth`** (MoGe-2, `neural_layertodepth_moge2`) — plus the **model/GPU preflight in `synapse_doctor`** shipped in the SAME commit ("part of the tool's honesty, not garnish" — roadmap C-3 verbatim), plus the COP-02 corpus seed.

### The probe-verified truth it builds on

Leg B, verbatim in §Evidence: node types V1-LIVE; parm whitelists; `shfs:`→`$SHFS` mapping rule; model-absence on this machine; the `$SHFS/houdini/nodes/<cat>/<node>/` layout proof; `hou.opencl.devices(device_type)` with required positional; OpenCL ≠ ONNX-EP axis; `denoiseai` exemption; provider menus instance-only (OWED P-1(a)).

### Design

New tools follow the live shipped pattern end-to-end (all integration points verified this dispatch):

1. Handlers `_handle_cops_segment_mask` / `_handle_cops_estimate_depth` on `CopsHandlerMixin` (`handlers_cops.py:317`), `run_on_main` + `hou.undos.group` like every sibling.
2. `reg.register(...)` rows in `python/synapse/server/handlers.py` (cops block `:673-699`).
3. `AuditCategory` map entries (`handlers.py:163-171` block; category PIPELINE).
4. Registry rows in `python/synapse/mcp/_tool_registry.py` `TOOL_DEFS` (cops rows from `:1140`); flags = write, non-destructive (the `cops_create_node` class).
5. `mcp_tools_cops.py` `TOOL_NAMES` + `DISPATCH_KEYS` (21 → 23) + GROUP_KNOWLEDGE sentence.
6. Palette/routing visibility: exact names added to `_AGENT_TOOL_MAP["HANDS"]` in `python/synapse/panel/tool_filter.py` (`:177-185` — the map is **exact-name**, not prefix; note in passing: `cops_create_copnet` is missing from that block today, a pre-existing gap this edit may fix in the same diff).
7. CLAUDE.md banner 115 → 117 (bound by `tests/test_phase0c_doc1_toolcount.py`).
8. Emitted-surface regen: `scripts/extract_emitted_node_types.py` → `python/synapse/cognitive/tools/data/emitted_node_types.json` (read by `harness/verify/checks.py:340`), so the two `neural_*` type strings enter the guarded emitted surface and future connectivity probes.

**Tool contract (both tools):**

- **Preflight inside the handler, before any node exists:** `_neural_model_status(node_type)` — pure function: read the type's `modelpath`/`modelfile` default from `parmTemplateGroup()`, map `shfs:/<rest>` → `hou.text.expandString('$SHFS') + '/<rest>'`, `os.path` check. Returns `{model_ready, model_dir, writable}`.
- **Model absent ⇒ honest failure, default-refuse:** raise `ValueError` whose message is the probe's one-actionable-message rule — model path checked, missing, `$SHFS` writability status, and the operator instruction ("run Download Models on a `neural_layertomask_sam2` node in the GUI; `$SHFS` is under Program Files and may need elevation"). **Never a silently-created node that cooks an empty mask** — that is the exact silent-wrongness mode COP-02 exists to prevent. Optional `create_anyway: true` payload flag creates the node scaffold and returns `model_ready: false` + the same message in the envelope (for artists preparing a graph ahead of a download).
- **v1 never presses `downloadmodels`** (network + Program Files write; elevation likely). If a later cycle wants it, it enters as a `touches_disk=True` APPROVE-gated op — out of scope here.
- **GPU reporting, not gating:** `hou.opencl.devices(hou.openCLDeviceType.GPU)` → envelope `gpu_opencl: [labels]` / `gpu_opencl_available: bool`. Empty list **does not block** (OpenCL presence ≠ ONNX EP truth — Leg B verbatim); the envelope says exactly what was measured and that EP selection is a separate axis (`provider` left at its `'automatic'` defaultExpression).
- **v1 parm whitelist (verbatim-probed names only):** SAM2 — `model`, `usethreshold`, `threshold`, `deviceid` (+ input wiring: layer input 0). MoGe-2 — `model`, `modelfile` (custom-model path passthrough), `deviceid`, and the verbatim-named toggles `metricscale`, `applyskymask`, `removeedges`. **No prompt-point/bbox args in v1** (names not verbatim-captured; unlocked by P-1). **No `provider` authoring** (menu tokens unknown until P-1(a)).
- **No handler-side cook.** Cook + empty-vs-real verification stays with `cops_batch_cook`/`cops_analyze_render`; the P-1(e) cook probe (post-download) is the evidence gate for ever claiming mask output in docs.

**Doctor preflight (same commit):** `_check_neural_models(handler)` appended to the `run_doctor` checks list (`python/synapse/server/doctor.py:589-599`; precedents `_check_symbol_table:279`, `_check_houdini:426`): status `skipped` when `hou` absent; per neural node type report model presence via `_neural_model_status`; `fail` ⇒ the single actionable message (model missing + writability); plus the GPU device list line. `denoiseai` explicitly exempted with the OIDN-bundled note.

**Corpus (same commit, code/corpus rule):** seed the COP-02 precondition prose (Download Models under `$SHFS`, EP axis, denoiseai exemption, the `shfs:` non-expansion trap) into the H22 reference corpus; W.6 carries the broader purge, but this seed rides C.3 so the tool and its operational truth ship together.

### Tests

- **Unit:** `_neural_model_status` is stock-python testable (fake expandString + tmp dirs): present/absent/unwritable paths; refuse-vs-`create_anyway` envelope shapes; GPU list marshalling with fake `hou.opencl`; doctor check all three statuses; parm-whitelist conformance (emitted names ⊆ the frozen Leg B fixture).
- **Live-marked:** on the live bridge with models absent (this machine's current state): `cops_segment_mask` default-refuses with the actionable message; `create_anyway` produces the node + `model_ready:false`; doctor reports the same truth. A second live test, `skipif` model-dir-absent, covers the models-present path (arms automatically once Download Models has been run) — the empty-vs-real cook assertion lives there, gated on P-1(e).

### DoD per deliverable (C.3)

| Deliverable | Done when |
|---|---|
| D3.1 `cops_segment_mask` | 8-step wiring complete; whitelist-only parms; model-absent = honest refusal envelope, live-verified on this (model-less) machine |
| D3.2 `cops_estimate_depth` | same bar; `modelfile` custom passthrough works |
| D3.3 doctor preflight | `_check_neural_models` in `run_doctor`; skipped/fail/ok all tested; actionable single message verbatim-includes path + writability |
| D3.4 corpus seed | COP-02 prose in the H22 corpus, same commit |
| D3.5 banner/count | `test_phase0c_doc1_toolcount.py` green at 117 |
| Cycle gate | suite ≥ floor · phantom_clean GREEN (note: `hou.opencl` is live-verified; if the committed h22 symbol table lacks it, re-introspect the table rather than allowlisting) · human merge |

---

## CYCLE C.10 — terrain/heightfield exposure (build order: THIRD)

**Queue id:** `C.10-H22-terrain-exposure` (`ratified: true`; deposited with the same 2026-07-16 directive — "terrain named explicitly").
**Scope:** the SOPs→COPs terrain migration is inventoried but SYNAPSE emits none of it. Build the terrain emission surface: **one new verb** `cops_terrain_setup` (OD-C) + **a recipe** in the routing recipe registry + catalog extension so the wiring is label-proven.

### The probe-verified truth it builds on

Leg C, §Evidence: the 18-name height family + ocean pair V1-LIVE; **no Cop heightfield generator** (base = `fractalnoise`-class feeding the `height` layer); core-five parm surfaces (fractalnoise/erode/maskbyfeature/visualize + bridges); `Cop/heightfield_erode` fully cataloged with 6 in / 4 out labels (verified in both catalog files this dispatch, 293 entries each); 17 terrain types uncataloged; `hou.NodeType.inputLabels` absent on Cop types (instance-only).

### Design

- **D10.1 — catalog extension first (the U.1 flywheel mechanism, not a hand edit):** the new emitted literals (`fractalnoise`, `heightfield_erode`, `heightfield_maskbyfeature`, `heightfield_visualize`, `sopimport`) enter the emitted surface via the C.10 code; `scripts/extract_emitted_node_types.py` regen; then the connectivity probe re-run under H22 hython regenerates `verified_connectivity_22.0.368.json` + packaged `connectivity_22.json` **with the P-1(c) label capture folded in** (both files, blake2b-stamped, byte-coherent — the U.1-H22 pattern). **No recipe wiring merges before this lands.**
- **D10.2 — `cops_terrain_setup` handler** (`CopsHandlerMixin`, same 8-step wiring checklist as C.3; registry 117 → 118; banner bump; palette HANDS entry): builds, inside a caller-supplied or freshly-created copnet — container `setres`/`res` authored per Leg A — the probe-verified chain: `fractalnoise` (base, mapped parms per D4.1's table — shared helper, single source) → `heightfield_erode` (wired **by label `height`**, catalog-backed; `simulate/iterations/seed/erodability` payload passthrough on verbatim-probed names) → optional `heightfield_maskbyfeature` (slope/height mask args on probed names) → `heightfield_visualize` (tint/colorramp display tail). Optional `sop_source` payload: `sopimport` + `soppath` feeding the chain instead of `fractalnoise` (out-label `geometry`, cataloged). Every `setInput` goes through `wire_by_label` (`python/synapse/core/wiring.py:192`) with `WiringError` surfacing honestly; the major-aware resolver (`_pkg_catalog_path`, `:80-89`) already serves `connectivity_22.json` on an H22 host. Display flag on the tail; **no cook** (cook = `cops_batch_cook`).
- **D10.3 — recipe:** new `python/synapse/routing/recipes/cop_recipes.py` with `register_cop_recipes(registry)` added to `RecipeRegistry._register_builtins` (`python/synapse/routing/recipes/base.py:178-189`) — a `Recipe` matching terrain/heightfield/erode phrasings whose steps drive `cops_create_copnet` + `cops_terrain_setup`, discoverable via the shipped `synapse_list_recipes` (`handlers.py:644,1430`). Proposal-flow users get the same truth for free: `GraphValidator` already spans the COP context (`graph_validator.py:33` `"COP": {"Cop","Cop2"}`; phase-5 host oracle `:480`), so a terrain `GraphProposal` validates against the live registry — the "propose→validate→build discipline" the queue entry names, satisfied by existing machinery plus the extended catalog, no new validator code.
- **Deliberately deferred** (recorded, not built): `geotolayer`/`layertogeo` rasterization round-trip (cook unverified, `layertogeo::2.0` has 0 parms — nothing to author until a cook probe proves the flow); ocean pair recipe (adjacent scope — enthusiasm-creep guard); `heightfield_output` disk export (ROP-style, touches disk, APPROVE surface); `monotoheightfield/normaltoheight/refractfromheight` converters (no parm capture in any leg).

### Tests

- **Unit:** graph-shape test with fake hou (chain built, labels requested, envelope lists nodes + wiring verdicts); recipe registration + text-match; payload passthrough only touches probed names (conformance fixture from Leg C tables).
- **Live-marked:** fresh copnet, full chain build, assert every wire landed on the cataloged label (`heightfield_erode` input `height` at its live index), maskbyfeature branch on/off, destroy, no hip save.
- **Catalog conformance:** every type/label the terrain surface emits exists in `connectivity_22.json` with `instantiated: true` — RED until D10.1 lands (correct: it sequences first).

### DoD per deliverable (C.10)

| Deliverable | Done when |
|---|---|
| D10.1 catalog extension | P-1(c) labels captured; both catalog files regenerated, hash-stamped, byte-coherent; conformance check green |
| D10.2 `cops_terrain_setup` | 8-step wiring complete (registry 118, banner, palette); chain builds live wired by label; honest WiringError path tested; container-res |
| D10.3 recipe | registered + matched + listed; proposal-flow validation demonstrated once against the live oracle |
| Cycle gate | suite ≥ floor · phantom_clean GREEN · no unprobed parm/type emitted · human merge |

---

## SEQUENCING

**Precondition (queue-mandated): SATISFIED.** W.4 merged (`34f41f7` in master history) and the v5.26.0 push landed (master = origin/master = `32dd597`, tag `v5.26.0`) — verified this dispatch. `handlers_cops.py` is unowned; these cycles may dispatch.

**Order: C.4 → C.3 → C.10, strictly serialized.** Justification:

1. **Same-file conflicts force serialization anyway:** all three touch `handlers_cops.py`; C.3 and C.10 additionally collide on `handlers.py` (register + audit blocks), `mcp_tools_cops.py`, `_tool_registry.py`, `tool_filter.py`, and the CLAUDE.md banner line (117 then 118 — two cycles editing the same integer is a rebase, not a merge conflict, if ordered).
2. **C.4 first:** it is the roadmap's P2 silent-noop **floor** (C.3 is P3); it has zero external dependencies (no models, no downloads, no catalog regen); and D4.1's fractalnoise mapping helper is shared source for C.10's D10.2 — building it first means C.10 consumes, not duplicates.
3. **C.3 second:** its testable v1 path is the model-ABSENT honest envelope — buildable on this machine today; the human can run Download Models (GUI, possibly elevated) in parallel, which arms the models-present live test and P-1(e) without blocking the cycle.
4. **C.10 third:** it needs P-1(c) + the catalog regen (D10.1) — the longest evidence tail — and inherits C.4's helper and C.3's freshly-exercised 8-step tool-wiring path.

A reorder is legal only if the human rules it and the colliding-file edits re-serialize accordingly.

**Interplay with the cops-1/cops-2 port waves (the manifest trap, stated explicitly):** `docs/PORT_WAVE_MANIFEST.md` wave `cops-2` carries all four C.4 tools with the rider "porting must not 'fix' the scaffold into a cook — that is a separate, ratified feature, not a port" (`:118`). **These cycles ARE that separate, ratified feature.** The two tracks stay clean under one rule each way:

- **These cycles land first (expected — port order is scene→usd→render→tops→cops, and only scene-1 has run per the queue's crucible deposits):** the cops-1/cops-2 parity goldens are captured later against the **rebuilt** handler behavior at port-time HEAD. The trap's `†`-scaffold annotations then apply only to whatever C.4 left honest-scaffold (D4.3 if P-2 refuses, RD if OD-B = (b)). The port still changes no behavior — it wraps whatever truth is live.
- **A cops wave somehow dispatches first:** PORT-FREEZE — the wave must not include any C.3/C.4/C.10 diff (a port is never a behavior change), its goldens pin scaffold semantics, and the C-cycle that lands after it **updates those parity goldens in its own commit** (a ratified behavior change replaces the golden with the new truth; softening a golden without the ratified cycle is the forbidden move).
- **New tools (C.3 ×2, C.10 ×1) are not in the frozen 115 inventory** → OD-A rules how the manifest absorbs them.

**Adjacent unratified deposits on the same file (do not silently absorb):** `W.4b-H22-solver-followups` (item 3 → OD-D; items 1–2 untouched), `C.1-H22-imagelayer-stats` (unratified, same-file — sequence after these cycles or ratify separately), `CTO-04` (cop2net sunset register — explicitly NOT this spec's scope; C.4 preserves the legacy branches).

---

## OUT OF SCOPE / ABSENT / UNKNOWN (the probes say no — so the spec says no)

**ABSENT on 22.0.368 (V1) — no deliverable may emit or promise these:**

- `levels`/`steps` parms on either quantize surface (renamed → Cop `method='segments'`+`segments` / Cop2 `step`; already handled, W.4).
- Bare `noise` Cop type; `vopcop2gen` in a copnet (raises `OperationFailed`); plain-`heightfield` and `heightfield_noise` Cop types (SOP-only — no Cop terrain generator exists).
- `resx`/`resy` resolution parms on the probed Cop nodes — resolution is container-level (`copnet.setres/res`).
- `block_end.{method,blocktype,blockpath,block_begin}` (W.4's settled truth; restated so no C.4 branch resurrects them).
- No-arg `hou.opencl.devices()` overload; `'automatic'`/`'directml'` members on `hou.openCLDeviceType` (CPU|GPU only — OpenCL is not the ONNX-EP axis).
- `shfs:` expansion via `hou.text.expandString` (returns verbatim — use the `$SHFS` mapping rule).
- A `heightfield_import`-named Cop; filename-style parms on `slapcompimport` (it is not a file loader).
- `hou.NodeType.inputLabels` on Cop types (instance-only).
- SAM2/MoGe-2 ONNX models on this machine (`$SHFS` scan — Download Models never run).

**UNKNOWN (OWED — gated behind P-1/P-2; any code needing them waits):**

- SAM2/MoGe-2 instance-level `provider` menu items (dynamic; empty at type level).
- `usdmaterial` instance/dynamic parms (zero at type level — do not author names against it).
- Fractalnoise `noisetype`/`fractaltype` menu tokens; live `inputLabels` for maskbyfeature/visualize/fractalnoise/geotolayer/layertogeo.
- Every cook verdict: bgt::2.0 bake output, bound RD pair, neural empty-vs-real mask, geotolayer/layertogeo round-trip (all SCENE_BUSY and/or model-blocked).
- A modern Cop stamp/scatter target (never probed — P-2).

**Out of scope by decision (recorded here so nobody "helpfully" adds them):**

- Pressing `downloadmodels` from any handler (network + Program Files write; would be APPROVE-gated `touches_disk` — separate cycle if ever).
- Disk export from bake or terrain (`rop_image`, `heightfield_output`) — keeps the APPROVE surface untouched in v1.
- `cop2net`/`vopcop2gen` sunset or `cops_create_network`/`cops_composite_aovs` widening (CTO-04's register, unratified).
- `usdmaterial`/`slapcompimport` adoption for `cops_to_materialx`/`cops_slap_comp` (#7/#10 are PASS tools; their modernization is a future cycle — probe truth banked in §Evidence).
- Ocean recipes; the converter trio (`monotoheightfield`/`normaltoheight`/`refractfromheight`); prompt-point/bbox segmentation args (post-P-1).
- Anything render, APEX/rigging, or `handlers_tops/` (standing structural refusals).

---

*Authored MODE B paper, HEAD `32dd597` (v5.26.0). Every count, path, and line number above was re-derived this dispatch (Read/Grep/import-and-len); probe quotes are verbatim from the three 2026-07-16 live-bridge legs and the 22.0.368 COP audit. Where this spec and the live runtime disagree, the runtime wins — re-probe, then amend the spec.*
