# H22 Doc-Intel — Prioritized Report (Wave 2)

> **Provenance:** fetch-date `2026-07-16` · symbol-table stamp **22.0.368** · doc source **sidefx.com/docs/houdini22.0**
> **Wave 2 of the doc scout:** `tops_ml` / `karma_render` / `news_delta` · Wave 1 = `docs/reviews/h22-doc-intel-2026-07-15.md`
> Cross-verified from 35 findings against the introspected H22 `dir()` symbol table (`python/synapse/cognitive/tools/data/h22_symbol_table.json`) and the live SYNAPSE code/corpus surface. Every candidate below is **DOC-CLAIM** until its runtime probe runs under H22 hython. This report never mutates code.

---

## Executive Summary

35 doc-derived candidates, cross-checked against the committed 22.0.368 symbol table and the live SYNAPSE code/corpus surface.

**By bucket:** NEW_MCP_TOOL 6 · RECIPE_CHANGE 5 · API_MIGRATION 7 · CAPABILITY_GAP 12 · CORPUS_SEED 5
**By tier:** VERIFIED 21 (one carrying a confirmed PHANTOM inside it) · DOC-CLAIM 14
**By domain:** TOPs/ML 9 · Karma/render 14 · news/breaking-changes 12
**Escalations (breaking / version-bump smell):** 11 → `TOPS-01`, `KAR-01`, `KAR-02`, `KAR-03`, `KAR-06`, `KAR-08`, `KAR-13`, `KAR-14`, `NWS-01`, `NWS-02`, `NWS-03`
**Confirmed-absent phantom symbols:** 8 dotted names (see PHANTOM WATCH — 1 doc error + 7 table-confirmed removals)

**The headline signal:** three stories. First, the **PDG event surface survived the major intact** — every symbol R8 depends on is present in the 22.0.368 table (`TOPS-09`), so the port wave owes a behavior re-probe, not a rewrite; the doc even resolves the H21 wrapper-class ambiguity (`pdg.EventHandler` vs `PyEventHandler` — both real, both present in both majors, `TOPS-01`). Second, a **Karma recipe-drift cluster** hits SYNAPSE's render-path assumptions: husk now renders the stage's full frame range by default (`KAR-01`), the Pixel Filter Size parm is removed (`KAR-02`, table-confirmed), output naming gains the delegate name (`KAR-03`), and karma/husk schemas migrated string properties to **relationships** the `handlers_usd.py` read path cannot see (`KAR-08` — silent-breakage class). Third, wave 1's `HOM-02` live break is now **fully closed at the intel level**: `hou.CopNode.planes` is table-absent AND the complete replacement surface (`hou.CopCable`/`hou.DetachedAttrib`/`attrib()`/`cable()`) is table-present (`NWS-03`) — the two guarded call sites in `handlers_cops.py:446,684` silently degrade to `planes:[]` on H22 today. Biggest greenfield: the **H22 ML TOP family** (10 nodes, train→ONNX→COP-inference, zero SYNAPSE coverage — `TOPS-06`/`TOPS-07`) and **PDG Services** (`TOPS-08`, the warm-session lever aimed exactly at the ~2s Houdini cook floor the latency roadmap hit).

**Tier discipline (same rules as wave 1):** VERIFIED means the *dotted Python API symbols* resolve in the committed 22.0.368 table — it does **not** clear node-type-name strings (TOP/COP/LOP/VOP type names are never table-verifiable; probe before any `createNode`), VEX function names (vcc probe only), or CLI flags (`husk --help` probe only). `hdefereval` is outside table scope (the table introspects `hou`/`pdg`/`pxr` only) — absence there is a scope limitation, not a phantom verdict (see PHANTOM WATCH Tier C).

### TOP 10 Highest-Leverage

| # | Domain | Bucket | Item | Tier | Gap |
|---|---|---|---|---|---|
| 1 | news_delta | API_MIGRATION | **`NWS-03`** CopNode `planes()` → `CopCable`/`DetachedAttrib`/`attrib()`/`cable()` migration surface | VERIFIED | **LIVE SILENT BREAK**: both call sites try/except-guarded → `planes:[]` data loss, no error; stale corpus recipe too |
| 2 | karma_render | API_MIGRATION | **`KAR-08`** karma/husk USD schemas preserve **relationships**, not strings | VERIFIED | `get_usd_attribute` reads attributes only — migrated `karma:*` properties return None; cannot author rels |
| 3 | karma_render | RECIPE_CHANGE | **`KAR-02`** Pixel Filter Size parm REMOVED → Pixel Filter Scale | VERIFIED | Corpus documents the old parm (`pipeline_preferences.md`); no code exposure found |
| 4 | karma_render | RECIPE_CHANGE | **`KAR-01`** husk defaults to the stage's FULL frame range (not 1 frame) | DOC-CLAIM | All SYNAPSE flows pass explicit frames; naked agent-authored husk calls now multi-frame |
| 5 | karma_render | RECIPE_CHANGE | **`KAR-14`** husk license introspection / mode-forcing flags | DOC-CLAIM | Could convert the blind Indie-no-op flipbook fallback (`handlers_render.py:529`) into detection-driven |
| 6 | tops_ml | NEW_MCP_TOOL | **`TOPS-08`** PDG Services lifecycle (`pdg.ServiceManager`) | VERIFIED | Warm-session lever vs the ~2s cook floor; localscheduler-only rejection today; full verb surface table-confirmed |
| 7 | news_delta | NEW_MCP_TOOL | **`NWS-04`** `hou.ImageLayer` in-process pixel statistics | VERIFIED | `cops_analyze_render` ADVERTISES stats it never computes — this is the missing implementation |
| 8 | karma_render | NEW_MCP_TOOL | **`KAR-04`** RenderPass prims + `husk --pass` multi-pass renders | VERIFIED | Zero `UsdRender.Pass` usage; all 4 schema symbols table-present |
| 9 | karma_render | API_MIGRATION | **`KAR-06`** MaterialX 1.39.5 bump + 8 new MtlX VOP types | DOC-CLAIM | The 4 mtlx type names SYNAPSE emits are the concrete rename/retire exposure |
| 10 | tops_ml | CAPABILITY_GAP | **`TOPS-02`** Per-work-item telemetry events + `workItemById` phantom | VERIFIED (1 PHANTOM) | Percent/output-file/state-transition events unused; doc's `GraphContext.workItemById` is table-ABSENT — use `pdg.Graph.workItemById` |

Runner-ups: `TOPS-06`/`TOPS-07` (ML train→ONNX→inference, biggest greenfield but new-build not breakage), `NWS-01`/`NWS-02` (table-confirmed removals, zero callers — already COVERED), `KAR-03` (output naming — BL-007 walk resolves from parms, residual risk only).

---

## TOPs / ML

### NEW_MCP_TOOL

**`TOPS-06` — ML Computer Vision train→ONNX→COP-inference pipeline** · `DOC-CLAIM` · [tops/pdg/index.html](https://www.sidefx.com/docs/houdini22.0/tops/pdg/index.html)
Complete dataset→train→`.onnx`→inference loop (ML Preprocess/Train Computer Vision TOPs + ML Computer Vision Inference COP); zero SYNAPSE coverage — no ml/onnx/inference tool anywhere in `_tool_registry.py` (17 `tops_*` tools) or the cops surface. Candidate tools: `tops_ml_cv_train` + `cops_ml_inference`. Workflow doc: [computervisionworkflow.html](https://www.sidefx.com/docs/houdini22.0/tops/computervisionworkflow.html).
Probe: `cats=hou.nodeTypeCategories(); print(sorted(n for n in cats['Top'].nodeTypes() if 'ml' in n.lower())); print(sorted(n for n in cats['Cop'].nodeTypes() if 'ml' in n.lower() or 'inference' in n.lower()))` — node types are NOT in the symbol table, live scan required.
Gap: **GAP** — whole workflow class uncovered.

**`TOPS-08` — PDG Services lifecycle (`pdg.ServiceManager` + Service Create/Start/Stop/Reset/Delete TOPs)** · `VERIFIED` · [tops/pdg/index.html](https://www.sidefx.com/docs/houdini22.0/tops/pdg/index.html)
Persistent warm worker sessions — the exact lever against the ~2s Houdini cook floor from the latency roadmap; `handlers_tops/cook.py:150-156` rejects every non-local scheduler loudly, and `pdg.ServiceManager` appears nowhere in SYNAPSE code. All 5 symbols table-present, and the table confirms the full verb surface (`registerService`/`startService`/`stopService`/`resetService`/`resumeService`/`killService`/…) for a `tops_manage_service` tool.
Probe: `import pdg; print([m for m in dir(pdg.ServiceManager) if not m.startswith('_')]); print([m for m in dir(pdg.Service) if not m.startswith('_')])`
Gap: **GAP** — clean additive tool candidate; behavior remains DOC-CLAIM.

### API_MIGRATION

**`TOPS-01` — Handler wrapper class documented as `pdg.EventHandler` (not `PyEventHandler`) + `pass_handler`/`removeFromAllEmitters` teardown** · `VERIFIED` · [tops/events.html](https://www.sidefx.com/docs/houdini22.0/tops/events.html) · ⚠ ESCALATE
R8 manifest/corpus/memory record the `addEventHandler` return wrapper as `pdg.PyEventHandler`; the H22 doc names it `pdg.EventHandler` with `removeFromAllEmitters()` and a `pass_handler=False` third arg for self-removing handlers. Cross-ref verdict: BOTH classes are table-present in H21 AND H22 (likely base vs Python-callback subclass), so nothing SYNAPSE teaches is a dead symbol — the open question is only which class the wrapper reports and whether `pass_handler` is real. `shared/bridge.py:1289-1444` + `handlers_tops/diagnostics.py:604-636` already implement correct teardown without depending on the class name.
Probe: `import pdg; print([s for s in dir(pdg) if 'Handler' in s])`; live: `h = ctx.addEventHandler(lambda e: None, pdg.EventType.CookComplete); print(type(h).__name__, type(h).__mro__, hasattr(h,'removeFromAllEmitters')); import inspect; print(inspect.signature(ctx.addEventHandler))`
Gap: **PARTIAL** — teardown covered; `removeFromAllEmitters` + `pass_handler` unused; class-identity docs may need a one-line correction after the probe.

**`TOPS-09` — R8 PDG async-cook bridge symbol surface intact in H22** · `VERIFIED` · [tops/pdg/index.html](https://www.sidefx.com/docs/houdini22.0/tops/pdg/index.html)
Negative-confirmation: all 6 symbols `shared/bridge.py` R8 depends on (`pdg.EventType`, `PyEventHandler`, `EventHandler`, `GraphContext`, `CookComplete`, `CookError`) are present in the committed H22 table — the port wave needs a behavior re-probe, not a rewrite. Caveat preserved: on H21 `pdg.PyEventHandler(fn)` had NO constructor (the CLAUDE.md phantom warning) — re-verify that trap persists so the warning stays accurate.
Probe: `import pdg; assert hasattr(pdg.EventType,'CookComplete') and hasattr(pdg.EventType,'CookError')`; then `pdg.PyEventHandler(lambda e: None)` — expect `TypeError('No constructor defined')`; then `h = gc.addEventHandler(lambda e: None, pdg.EventType.CookComplete); print(type(h))`.
Gap: **COVERED** — symbol level clean; H21-recon behaviors (no-constructor trap, worker-thread delivery, wrapper return) remain DOC-CLAIM until the live re-probe.

### CAPABILITY_GAP

**`TOPS-02` — Rich per-work-item telemetry events: `NodeProgressUpdate`, `WorkItemCookPercentUpdate`, `WorkItemOutputFiles`, `WorkItemStateChange` (+ `lastState`/`currentState`)** · `VERIFIED (1 PHANTOM)` · [tops/events.html](https://www.sidefx.com/docs/houdini22.0/tops/events.html)
`tops_monitor_stream` (`handlers_tops/diagnostics.py:377-636`) is ALREADY push-based on `WorkItemStateChange`; what SYNAPSE does not use: per-item percent-complete, output-files-as-they-land, `WorkItemSetFile`, and `lastState`/`currentState` transition detail; `tops_get_cook_stats` remains poll-based. **PHANTOM caught:** the doc lists `pdg.GraphContext.workItemById` — table-ABSENT; the real symbol is `pdg.Graph.workItemById` (table-present, and the doc's own example uses `pdg_context.graph.workItemById`). Do NOT implement the GraphContext form.
Probe: `import pdg; print(sorted(s for s in dir(pdg.EventType) if any(k in s for k in ('Progress','Percent','OutputFiles','StateChange','SetFile')))); print(hasattr(pdg.GraphContext,'workItemById'))`; live: `print(hasattr(ctx,'workItemById'), hasattr(ctx.graph,'workItemById'))` — table predicts ctx False / ctx.graph True; on a captured event `print(hasattr(e,'lastState'), hasattr(e,'currentState'), hasattr(e,'workItemId'))`.
Gap: **PARTIAL** — push channel exists; the rich event set + transition detail uncovered.

**`TOPS-05` — `pdg.EventEmitter.supportedEventTypes` — runtime introspection of supported events per emitter** · `VERIFIED` · [tops/events.html](https://www.sidefx.com/docs/houdini22.0/tops/events.html)
The dir()-gate philosophy extended to PDG events: verify an event type is supported by THIS emitter at runtime instead of trusting doc tables — kills silently-never-firing handler registrations. No SYNAPSE code calls it (tops_diagnose/tops_monitor_stream register unconditionally). Table also shows `eventHandlers`/`hasEventHandler`/`removeAllEventHandlers`, and `supportedEventTypes` on `pdg.ServiceManager` too.
Probe: `import pdg; print(hasattr(pdg,'EventEmitter'), hasattr(pdg.EventEmitter,'supportedEventTypes'))`; live: `print(ctx.supportedEventTypes); print(top.getPDGNode().supportedEventTypes)` — confirm property-vs-method and return type.
Gap: **GAP** — clean additive hardening for existing monitor/diagnose handlers.

**`TOPS-07` — H22 ML TOP node family: 10 nodes (Computer Vision, GSplats, OIDN, Style Transfer, Neural Cellular Automata, Regression)** · `DOC-CLAIM` · [tops/pdg/index.html](https://www.sidefx.com/docs/houdini22.0/tops/pdg/index.html)
The TOP reference lists ML Preprocess/Train Computer Vision, ML Preprocess/Train GSplats (touches the render story), ML Preprocess/Train OIDN (custom Karma denoiser training), ML Train Style Transfer / Neural Cellular Automata / Regression + ML Regression Kernel. SYNAPSE has no ML story at all: no `ml*` tool, no handler, and corpus OIDN coverage is exclusively the Karma denoise post-process parm. Version provenance (which are new-in-22) also unverified. Node index: [nodes/top/index.html](https://www.sidefx.com/docs/houdini22.0/nodes/top/index.html).
Probe: `cats=hou.nodeTypeCategories(); ml=[t for n,t in cats['Top'].nodeTypes().items() if 'ml' in n.lower()]; print([(t.name(), t.description()) for t in ml])` — any doc title with no matching runtime type is a phantom.
Gap: **GAP** — entire node family uncovered.

### CORPUS_SEED

**`TOPS-03` — Threading contract: events fire on the emitting cook thread; only CookComplete may safely recook; hdefereval for UI/main-thread work** · `VERIFIED` · [tops/events.html](https://www.sidefx.com/docs/houdini22.0/tops/events.html)
H22 doc states verbatim that PDG events are processed on the emitting cook thread and starting another cook / changing parms / opening UI from a handler is unsafe EXCEPT CookComplete may recook the current graph — confirms the H21 worker-thread recon and validates the R8 `asyncio.Event` design. SYNAPSE code already embodies the constraint, but `rag/skills/houdini21-reference` has ZERO PDG event-system prose (no addEventHandler/EventType/cook-thread text anywhere) — scout/knowledge_lookup cannot teach this to agents. Note: `hdefereval` is outside table scope (not a phantom — see PHANTOM WATCH Tier C).
Probe: `import threading; seen={}; def f(e): seen['tid']=threading.get_ident()`; `ctx.addEventHandler(f, pdg.EventType.CookComplete); top.cookWorkItems(block=True); print(seen['tid'] == threading.main_thread().ident)` — expect False.
Gap: **PARTIAL** — code embodies it; corpus seed genuinely needed.

**`TOPS-04` — Work-item value events do NOT propagate to node/graph context — register on the work item itself** · `VERIFIED` · [tops/events.html](https://www.sidefx.com/docs/houdini22.0/tops/events.html)
Pre-H18 propagation is gone: to catch a work-item value event you must add a handler to the work item itself; WorkItemAdd/Remove/StateChange remain catchable at node/context level. SYNAPSE registers ONLY at context level everywhere (consistent with the emitter tables for those events), has zero per-item registrations, and the corpus is silent on the split — an agent authoring per-item attribute monitoring today would register at the wrong level and silently receive nothing. All 5 symbols table-present (incl. `pdg.WorkItem.addEventHandler`/`removeEventHandler`).
Probe: register the same callback for `pdg.EventType.WorkItemSetInt` once on ctx, once on a generated `pdg.WorkItem` (`wi.addEventHandler(f, pdg.EventType.WorkItemSetInt)`); set an int attrib during cook; count which fires — expect only the per-item one.
Gap: **GAP** — genuine corpus gap; behavior DOC-CLAIM until the two-registration probe.

---

## Karma / render

### NEW_MCP_TOOL

**`KAR-04` — RenderPass workflow: `husk --pass <prim_path>` + RenderPass prims under /Render, multiple passes per invocation** · `VERIFIED` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html)
`synapse_configure_render_passes` (`handlers_render.py` ~1150-1300) authors `UsdRender.Var` prims only — zero `UsdRender.Pass` usage anywhere in `python/synapse`. All four schema symbols (`Pass`, `Pass.Define`, `Pass.CreateRenderSourceRel`, `Pass.CreateInputPassesRel`) exact-match the committed H22 table. Genuine new tool surface: author real RenderPass prims + drive multi-pass husk renders.
Probe: `from pxr import Usd, UsdRender; s = Usd.Stage.CreateInMemory(); p = UsdRender.Pass.Define(s, '/Render/passA'); assert p` — then `husk --help | grep -- --pass` for the CLI half.
Gap: **GAP** — schema half table-verified; CLI half DOC-CLAIM.

**`KAR-07` — New LOP nodes: Texture Material Library (built-in COP texture pipeline), Image Filter (`HoudiniImageFilterList` prim), Karma Blocker Light Filter (`KarmaBlockerLightFilter` prim)** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html)
`_handle_create_textured_material` exists (`handlers_material.py:462`) — Texture Material Library is a direct native upgrade path for it. Zero references to blocker/imagefilter/texture-material-library anywhere in server code or corpus; `houdini_configure_light_linking` has no light-filter vocabulary at all. Node-type names stay DOC-CLAIM pending the createNode probe.
Probe: `[t for t in hou.lopNodeTypeCategory().nodeTypes() if any(k in t.lower() for k in ('texturemat','imagefilter','blocker'))]` for exact internal names; then create the blocker node, cook, read stage prim `typeName == 'KarmaBlockerLightFilter'`.
Gap: **PARTIAL** — textured-material tool exists (upgrade path); filters entirely uncovered.

### RECIPE_CHANGE

**`KAR-01` — husk now renders the USD stage's FULL frame range by default (startTimeCode/endTimeCode), not a single frame** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html) · ⚠ ESCALATE
SYNAPSE's own flows all pass explicit frames (`handlers_render.py` `frame_range=(cur,cur)`; `render_sequence.py:224-229` f1/f2; `rag_render_husk_cli.md` always `--frame`/`--frame-range`) — no naked husk invocation found. Residual risk: corpus prose frames single-frame as the ambient default, and any future agent-authored husk call omitting flags now multi-frames.
Probe: author a trivial stage with `SetStartTimeCode(1)`/`SetEndTimeCode(5)`, export, run `husk <file.usd>` with NO `-f`/`-n`, count output frames (expect 5 per doc, 1 per H21 behavior). Caveat: run a licensed-render check first — H21 husk silently no-ops on Indie.
Gap: **PARTIAL** — code covered by explicit flags; corpus default-framing stale.

**`KAR-02` — Pixel Filter Size parm REMOVED from Render Settings + Karma Render Settings LOPs; replaced by Pixel Filter Scale (backwards compat claimed)** · `VERIFIED` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html) · ⚠ ESCALATE
No SYNAPSE code authors a pixel-filter-size parm (repo-wide grep clean; the `handlers_render.py` alias map has no filter entry). Corpus exposure exists: `pipeline_preferences.md` documents "Pixel Filter | blackman-harris 1.5"; `common_errors.md` + `render_farm.md` set `karma_pixelfilterclamp` (a different parm, likely unaffected but confirm). `hou.NodeType.parmTemplateGroup` exact-matches the H22 table.
Probe: `ptg = hou.nodeType(hou.lopNodeTypeCategory(),'karmarendersettings').parmTemplateGroup(); [pt.name() for pt in ptg.entriesWithoutFolders() if 'filter' in pt.name().lower()]` — verify old parm absent/aliased, capture the new scale parm's exact name; repeat for `rendersettings`; confirm `karma_pixelfilterclamp` survives.
Gap: **PARTIAL** — code clean; corpus recipe stale.

**`KAR-03` — Default render output file naming now includes the delegate name (e.g. `karma.exr`, `husk_storm.exr`)** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html) · ⚠ ESCALATE
`handlers_render.py`'s BL-007 walk (lines 294-447) resolves output paths FROM the picture/outputimage parms with token expansion — it follows whatever default H22 authors; `panel/face_review.py` bl007_flag checks the resolved path on disk. Residual risk: the synthesized-default path (~line 431) and `solaris_compose_tools.py:55`'s pinned H21 "productName parm does NOT author the prim" trap both need re-verification if the parm-level default changed.
Probe: `n = hou.node('/stage').createNode('karmarendersettings'); n.evalParm('picture')` (+ the usdrender_rop `outputimage` default) — compare against BL-007 expectations; confirm whether the delegate-name default appears at parm level or only at husk runtime.
Gap: **PARTIAL** — walk is default-agnostic; two pinned assumptions need re-verification.

**`KAR-09` — Karma Uniform Volume Material rebuilt on Karma Volume VOP (replacing Karma Pyro Shader VOP); density field no longer required; XPU renders iso-surface VDBs directly** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html)
The feared stale recipe does NOT exist — zero pyro-shader/uniform-volume wiring in `handlers_material.py`, `rag_material_karma_xpu.md`, or the corpus. SYNAPSE has no volume-material surface at all, so this is fresh capability/corpus opportunity rather than breakage; the no-density-field change removes a validation assumption only if volume-render validation is ever added.
Probe: `[t for t in hou.vopNodeTypeCategory().nodeTypes() if 'kma' in t.lower() and 'volume' in t.lower()]` for the Karma Volume VOP internal name; then instantiate the gallery/recipe material and inspect the contained shader VOP.
Gap: **GAP** — no volume-material surface exists.

**`KAR-14` — husk license introspection + mode-forcing flags (new licensing system) — may make the H21 Indie silent no-op detectable** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html) · ⚠ ESCALATE
*(Source finding arrived truncated mid-sentence; adjudicated from the surviving fragment + the pinned H21 Indie-husk trap.)* SYNAPSE carries a blind workaround for exactly this — `handlers_render.py:529` falls back to viewport flipbook because "husk may fail on Indie" (memory-pinned: H21 husk silently no-ops on Indie, writes nothing, no errors). No license introspection exists anywhere in the codebase. If H22 husk exposes license-check/mode-forcing flags or errors loudly, the fallback becomes detection-driven instead of unconditional.
Probe: `husk --help` grep for license/mode-forcing flags; then on the Indie license attempt a 1-frame husk render of a trivial stage and verify H22 errors loudly (exit code + stderr) vs H21's silent zero-output no-op; record which signal the fallback should key on.
Gap: **PARTIAL** — fallback exists but blind; detection signal uncovered.

### API_MIGRATION

**`KAR-06` — MaterialX upgraded to 1.39.5 with 8 new MtlX VOP node types (Flake2D/3D, Fractal2D, Gltf Anisotropy Image, glTF Material, Hex Tiled Image, Hex Tiled Normal Map, Lat Long Image)** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html) · ⚠ ESCALATE
`handlers_material.py` hardcodes and emits exactly 4 mtlx type names — `mtlxstandard_surface`, `mtlximage`, `mtlxgeompropvalue`, `mtlxnormalmap` (lines 465-598 + `MTLX_*` constants); `cops_to_materialx` + `solaris_compose_tools.py` also emit mtlx; corpus recipes in `rag_material_mtlx_encoding.md` + `materialx_shaders.md`. Those 4 emitted types are the concrete rename/retire exposure for the 1.39.5 bump; none of the 8 new types appear anywhere. Node-type names never table-verifiable.
Probe: `mt = [t for t in hou.vopNodeTypeCategory().nodeTypes() if t.startswith('mtlx')]` — FIRST assert the 4 SYNAPSE-emitted names still exist, THEN check guessed new names (`mtlxhextiledimage`,`mtlxflake2d`,`mtlxfractal2d`,`mtlxlatlongimage` — doc gives labels only, internal names UNVERIFIED) and diff the full `mtlx*` set against `harness/notes/verified_nodetype_catalog_21.0.671.json`.
Gap: **PARTIAL** — 4 emitted names at bump risk; 8 new types uncovered.

**`KAR-08` — Karma and husk USD schemas now preserve RELATIONSHIPS instead of strings** · `VERIFIED` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html) · ⚠ ESCALATE
Cross-ref CONFIRMS the exposure: `handlers_usd.py` `get_usd_attribute` reads via `prim.GetAttribute(attr_name)` only (line 365, echoed 413) and there is ZERO `GetRelationships` usage anywhere in `handlers_usd.py` — `karma:*` properties that migrated to relationships return None from the read path and cannot be authored via `set_usd_attribute`. Both cited symbols exact-match the H22 table. Tools exist but cannot express relationships → silent-breakage class.
Probe: build `karmarendersettings` + a light with a light filter assigned, cook, `prim = node.stage().GetPrimAtPath(...)`; compare `[r.GetName() for r in prim.GetRelationships()]` vs string-typed attributes against the same setup's H21 corpus expectations — identify which `karma:*` properties migrated.
Gap: **PARTIAL** — read/write tools exist; relationship expressiveness missing.

### CAPABILITY_GAP

**`KAR-05` — husk resumable/partial-render controls: `--skip-existing-frames`, `--karma-percent-of-samples`, `--error-summary` (+ USD Render ROP Husk tab parm)** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html)
Zero skip_existing/skipexisting hits anywhere in `python/synapse/server`. `synapse_render_sequence` + `synapse_render_progressively` are registered tools (`_tool_registry.py:1053,1097`) with no resume-after-crash vocabulary — these flags are the native mechanism for both.
Probe: `husk --help` grep for `skip-existing-frames`, `karma-percent-of-samples`, `error-summary`; hython: scan the usdrender ROP's `parmTemplateGroup()` for a skipexisting-like parm.
Gap: **GAP** — resume capability entirely uncovered.

**`KAR-10` — Gaussian Splats: native USD `ParticleField3DGaussianSplat` schema, SOP↔LOP round-trip via SOP Import, Karma+TOPs asset-to-GSplat conversion toolset** · `VERIFIED` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html)
Zero gsplat/ParticleField/GaussianSplat references anywhere in `python/synapse` code (only the symbol tables). `houdini_query_prims`/`stage_info` are generic and surface GSplat prims as unknown types; no TOPs conversion tooling. Both cited symbols (`pxr.UsdVol.ParticleField`, `hou.GeometryViewportSettings.gsplatsAlphaCulling`) exact-match the H22 table — the runtime surface is real.
Probe: `from pxr import Usd, UsdVol; hasattr(UsdVol,'ParticleField')` and `Usd.SchemaRegistry().FindConcreteTypeByName('ParticleField3DGaussianSplat')` (or GetTypeFromName) — confirm the concrete schema name; note `KARMA_XPU_GSPLATS_RENDER_MODE` env var flips back to stochastic mode.
Gap: **GAP** — whole GSplat story uncovered.

**`KAR-11` — AOV surface expanded on Karma Render Settings LOP: Split Render Products by Render Var, Global AOV material, Create Separate Denoised AOVs (`_denoise` suffix), DCM Exclude Holdouts, Camera-Far-Clip depth background** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html)
`synapse_configure_render_passes` authors RenderVar presets only (17 presets, `UsdRender.Var.Define` — no RenderProduct splitting, no denoised-AOV pairs, no holdout/farclip vocabulary). Adjacent-but-different coverage: alias map has `enable_denoiser` (render-time denoiser, `handlers_render.py:1757`); corpus `karma_aov.md` carries H21 setup_denoising prose — neither expresses the new `_denoise`-suffix AOV knob or per-RenderVar file splitting.
Probe: `ptg = hou.nodeType(hou.lopNodeTypeCategory(),'karmarendersettings').parmTemplateGroup()`; scan `[pt.name() for pt in ptg.entriesWithoutFolders()]` for split/denoise/holdout/farclip names, record exact parm names for tool wiring.
Gap: **PARTIAL** — RenderVar half covered; product-splitting/denoised-AOV half uncovered.

### CORPUS_SEED

**`KAR-12` — Lighting: per-light Improve Volume Sampling (Equiangular MIS), geometry lights gain instancing + light filters + light-tree integration, colorSpace metadata on physical lights, Flip Rectangle Light Texture** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html)
Zero equiangular/MIS/volume-sampling references in corpus or server code. Seed targets exist (`lighting.md`, `karma_rendering_guide.md` in `rag/skills/houdini21-reference/`) but contain none of these knobs; `houdini_configure_light_linking` does not touch sampling/filter/colorSpace surfaces. Pure corpus-seed gap — nothing to break, everything to add.
Probe: `ptg = hou.nodeType(hou.lopNodeTypeCategory(),'light::2.0').parmTemplateGroup()`; grep parm names for equiangular/MIS + texture-flip entries; for geometry lights check `geometrylight`-type parm templates for instancing/filter rels.
Gap: **GAP** — seed-only.

**`KAR-13` — Color/texture pipeline bumps: ACES 3.0, mipmaps computed in linear color space, imaketx writes 16-bit float .tx, network-texture local disk cache default (`HOUDINI_TEXTURE_DISK_CACHE -network`), `--opaque-detect` auto-strips constant alpha** · `DOC-CLAIM` · [news/22/karma.html](https://www.sidefx.com/docs/houdini22.0/news/22/karma.html) · ⚠ ESCALATE
The corpus IS stale here — `aces_color_management.md` is pinned to the ACES 1.3-era config (`cg-config-v2.0.0_aces-v1.3_ocio-v2.3.ocio`, line 25) and titled "Houdini 21", so the ACES 3.0 bump invalidates its setup guidance. `cops_bake_textures` (`handlers_cops.py:1527`) has bit-depth/alpha expectations that meet the imaketx 16-bit-float + `--opaque-detect` changes; imaketx appears nowhere in `python/` or `rag/`. Seeding prevents agents chasing "lost alpha" as a bug.
Probe: `import PyOpenColorIO as OCIO; OCIO.GetCurrentConfig().getDescription()` (expect ACES 3.0-era builtin config); `imaketx --help` grep for `--opaque-detect` + 16-bit float format note.
Gap: **PARTIAL** — corpus actively stale (worse than absent).

---

## news / breaking-changes

### NEW_MCP_TOOL

**`NWS-04` — `hou.ImageLayer` gains in-process pixel statistics + image/world/local space conversion** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
All 10 symbols table-present. Cross-ref sharpens the case: `cops_analyze_render` (`handlers_cops.py:632-710`) ADVERTISES black-pixel/NaN/dynamic-range/noise checks in its docstring but computes NO pixel statistics at all — implementation only reads resolution, planes (via the broken `planes()` call), and cook errors. `ImageLayer.computeAverage/Min/Max` is precisely the missing implementation, in-process with no disk I/O. Zero ImageLayer usage in `python/synapse` today.
Probe: `assert 'computeAverage' in dir(hou.ImageLayer)`; cook a COP file node, get an ImageLayer via the CopCable wire, `print(layer.computeAverage(), layer.computeMax())` — confirm returns without disk I/O.
Gap: **GAP** — advertised capability finally implementable.

**`NWS-05` — `hou.OpenCLDevice` + `hou.openCLDeviceType`: OpenCL compute-device introspection from HOM** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
Both symbols table-present. NO device enumeration exists anywhere — `server/doctor.py` has zero gpu/opencl/device checks; `cops_set_opencl` (`handlers_cops.py:342`) only sets kernel source. GPU-compute preflight before OpenCL/Copernicus cooks is genuinely uncovered; `synapse_doctor`/`synapse_health` are natural hosts. Class is documented non-constructible — locate the factory/enumeration entry point before writing tool code.
Probe: `assert hasattr(hou,'OpenCLDevice'); print(dir(hou.OpenCLDevice)); print([s for s in dir(hou) if 'penCL' in s or 'opencl' in s.lower()])`
Gap: **GAP** — preflight class uncovered.

### API_MIGRATION

**`NWS-01` — `hou.Node` base-class REMOVALS: `copyNetworkBox`/`copyStickyNote`/`editableInputString(s)`/`setEditableInputString`** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html) · ⚠ ESCALATE
Table-confirmed removal: all 5 `hou.Node.*` symbols ABSENT from the committed table while `hou.SopNode`/`ChopNode`/`LopNetwork.copyNetworkBox` remain PRESENT — matches the doc exactly. Repo-wide grep: ZERO production callers (only the intake adjudication doc + symbol tables); rag corpus clean. The committed dir() table already encodes the removal, so the phantom guard is current.
Probe: `assert not hasattr(hou.Node,'copyNetworkBox') and not hasattr(hou.Node,'editableInputString'); assert hasattr(hou.SopNode,'copyNetworkBox')` — removal is base-class only.
Gap: **COVERED** — treat the 5 names as phantoms on generic `hou.Node` references going forward.

**`NWS-02` — `hou.ChannelEditorPane` REMOVED, replaced by `hou.ChannelEditor`** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html) · ⚠ ESCALATE
Table-confirmed rename: `ChannelEditorPane` ABSENT, `ChannelEditor` PRESENT. Zero callers anywhere in `python/synapse`, `panel/`, `host/`, or `rag/` (only the intake adjudication doc, which already flags it correctly). No migration work owed; future pane-tab enumeration must emit `hou.ChannelEditor`.
Probe: `assert not hasattr(hou,'ChannelEditorPane'); assert hasattr(hou,'ChannelEditor')`
Gap: **COVERED** — phantom-guard current.

**`NWS-03` — CopNode data-access replacement surface: `hou.CopCable` + `hou.DetachedAttrib` + `CopNode.attrib()/cable()/pairedNode()` — the migration target for removed `hou.CopNode.planes()`** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html) · ⚠ ESCALATE
All 9 replacement symbols PRESENT and `hou.CopNode.planes` ABSENT in the committed table — the migration target is real. Cross-ref CONFIRMS live breakage with a nuance: `handlers_cops.py:446` (`cops_read_layer_info`) and `:684` (`cops_analyze_render`) still call `node.planes()`, and BOTH sites are try/except(AttributeError)-guarded — on H22 they SILENTLY degrade to `planes:[]`. Silent data loss, not a crash (worse: no error surfaces). Zero CopCable/DetachedAttrib/cable()/attrib() usage anywhere. Stale corpus recipe teaching `planes()` at `rag/skills/houdini21-reference/copernicus_python_api.md:315` must be fixed too (code/corpus divergence rule). Closes the loop on wave 1's `HOM-02`.
Probe: `n=hou.node('/img').createNode('copnet').createNode('file'); c=n.cable(); print(type(c), dir(c))` — expect `hou.CopCable`; also `assert not hasattr(hou.CopNode,'planes')`.
Gap: **GAP** — migration owed at 2 call sites + 1 corpus recipe.

### CAPABILITY_GAP

**`NWS-06` — `hou.Volume` + `hou.NanoVDB` gain voxel statistics and data/display-window metadata** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
All 10 symbols table-present. `server/introspection.py:144-169` detects volumes only as a boolean `has_volumes` flag via type-name substring match — no voxel min/max/average, no window metadata anywhere in the introspection path. The `inspect_geometry`/GeoSummary host surface exists; the statistics capability is entirely absent. Cheap token-efficient volume summaries are a real OBSERVER upgrade.
Probe: `v = <geo with volume>.prims()[0]; print(v.computeAverage(), v.computeMax(), v.hasWindow()); assert 'computeAverage' in dir(hou.Volume) and 'resolution' in dir(hou.NanoVDB)`
Gap: **PARTIAL** — host surface exists; statistics absent.

**`NWS-07` — `hou.Geometry` batch list-attribute readers: `point/prim/vertex{Float,Int,String}ListAttribValues`** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
Full 9-method matrix (point/prim/vertex × Float/Int/String) verified table-present, plus `primByName` and `vertex`. `python/synapse` contains ZERO batch `*AttribValues` readers of any kind — no array-attribute read surface exists at all in geometry introspection, so the per-element-loop elimination this enables is fully uncovered.
Probe: `g = hou.node('/obj').createNode('geo').createNode('box').geometry(); assert 'pointFloatListAttribValues' in dir(g)`; exercise via an attribcreate array attrib then `g.pointFloatListAttribValues('myarr')`.
Gap: **GAP** — array-attribute reads uncovered.

**`NWS-08` — Solaris selection API: `hou.LopNetwork.selectionPaths()/setSelectionPaths()` (pxr.Sdf.Path) + `LopSelectionRule` point-instancer IDs** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
All 6 symbols table-present (`hou.LopNetwork` is a class, NOT the `hou.lop.*` 0-child blind-spot submodule — trap checked, does not apply). `houdini_get_selection` (`handlers.py:1040-1057`) returns `hou.selectedNodes()` only — node-level, capped at 50, no LOP prim selection at all; zero selectionPaths/LopSelectionRule usage anywhere.
Probe: `stage = hou.node('/stage'); assert 'selectionPaths' in dir(hou.LopNetwork); stage.setSelectionPaths([])` then `stage.selectionPaths()` — verify accepts/returns `pxr.Sdf.Path` list.
Gap: **PARTIAL** — tool exists; prim-path read/write capability missing.

**`NWS-09` — Viewport control additions: `GeometryViewport.tearOffCopy()/setCameraParms()/isVisible()`, `SceneViewer.showHydraProcedurals()`, `sceneViewerEvent.RendererChanged/ViewportCreated`** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
All 7 symbols table-present — these hang off real classes and the 18-child `hou.sceneViewerEvent` enum, NOT the 0-child `hou.ui`/`qt` blind spots, so table presence is trustworthy; behavior still needs a GUI session. `houdini_capture_viewport` (`handlers_render.py:135-202`) uses `sv.curViewport()` + flipbookSettings with no camera-parm injection, no isVisible preflight, no tearOffCopy; RendererChanged delegate monitoring uncovered.
Probe: in-session via execute_python: `vp = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer).curViewport(); assert hasattr(vp,'setCameraParms') and hasattr(vp,'tearOffCopy'); print(vp.isVisible())`
Gap: **PARTIAL** — capture tool exists; new controls unused.

**`NWS-10` — Cameras become geometry primitives: `hou.Camera` / `hou.CameraPrim` / `Geometry.createCameraPrim()` / `primType.CameraPrim` + `Plane`** · `VERIFIED` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
All 6 symbols table-present (`hou.primType` has 31 children, `hou.cameraProjection` 3 — real enums, not blind spots). `shot_render_ready` preflight (`handlers_render.py:1311+`) checks cameras via stage_info USD Camera prims only; render tooling has no awareness of the new geometry-level CameraPrim third representation.
Probe: writable geo via frozen()/editable path, then `cp = geo.createCameraPrim(); print(cp.focal(), cp.camera()); assert hasattr(hou,'CameraPrim')`
Gap: **PARTIAL** — /obj + USD camera scanning exists; geometry-prim cameras unrecognized.

**`NWS-11` — New VEX function `usd_bindmaterial()`: material binding from VEX** · `DOC-CLAIM` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
VEX language function — not verifiable via the Python dir() table by nature; stays DOC-CLAIM until the vcc probe runs. `usd_bindmaterial` appears nowhere in `python/synapse` or the rag corpus (H21 corpus predates it by definition); `houdini_assign_material` covers node-based per-prim binding, so the bulk/pattern-driven VEX path is the uncovered half. Corpus seed must be version-tagged H22-only.
Probe: `$HFS/bin/vcc --list-context cvex | grep usd_bindmaterial`; OR create a LOP attribwrangle with snippet `usd_bindmaterial(0, @primpath, "/materials/m");`, cook, assert no compile error in `node.errors()`.
Gap: **PARTIAL** — node-based binding covered; VEX path uncovered.

### CORPUS_SEED

**`NWS-12` — 17 other new VEX functions: OCIO color queries, OSD limit-surface evaluation, implicit surfaces, quaternion math, minjerk, random_shash, vertexprimuv, volumetransform** · `DOC-CLAIM` · [news/22/vex.html](https://www.sidefx.com/docs/houdini22.0/news/22/vex.html)
*(Source finding arrived TRUNCATED mid-JSON; adjudicated from intact fields.)* VEX language functions — not dir()-table-verifiable, DOC-CLAIM until vcc-probed. Spot-grep of minjerk/vertexprimuv/random_shash against `rag/` returns zero hits — the H21 corpus has none of these. Seeds must be H22-version-tagged so knowledge_lookup/scout never teach them against an H21 target.
Probe: `$HFS/bin/vcc --list-context cvex` (and surface/cvex contexts) then grep each of the 17 names; any name absent from vcc output stays doc-only and is NOT seeded into the corpus.
Gap: **GAP** — corpus-seed only, gated per-function on the vcc probe.

---

## PHANTOM WATCH

### Tier A — confirmed-absent dotted symbols (do NOT emit)

Table-verified ABSENT from `h22_symbol_table.json` @ 22.0.368. Emitting any of these on H22 is a phantom-API bug.

| Phantom | Verdict source | Use instead |
|---|---|---|
| `pdg.GraphContext.workItemById` | Doc error caught in `TOPS-02` — the doc's method list is wrong; its own example is right | `pdg.Graph.workItemById` (table-present): `ctx.graph.workItemById(...)` |
| `hou.Node.copyNetworkBox` | `NWS-01` base-class removal | subclass forms survive: `hou.SopNode/ChopNode/LopNetwork.copyNetworkBox` |
| `hou.Node.copyStickyNote` | `NWS-01` base-class removal | subclass forms (probe per category) |
| `hou.Node.editableInputString` | `NWS-01` base-class removal | subclass forms (probe per category) |
| `hou.Node.editableInputStrings` | `NWS-01` base-class removal | subclass forms (probe per category) |
| `hou.Node.setEditableInputString` | `NWS-01` base-class removal | subclass forms (probe per category) |
| `hou.ChannelEditorPane` | `NWS-02` rename | `hou.ChannelEditor` |
| `hou.CopNode.planes` | `NWS-03` (re-confirms wave-1 `HOM-02`) | `hou.CopCable` / `hou.DetachedAttrib` / `CopNode.attrib()` / `CopNode.cable()` |

Carried-forward H21 trap to re-verify (not new): `pdg.PyEventHandler(fn)` has no constructor on H21 — register raw callables via `addEventHandler`. Both `pdg.EventHandler` and `pdg.PyEventHandler` are table-present in H21 AND H22; neither name is a phantom (`TOPS-01`/`TOPS-09`).

### Tier B — node-type-name strings (NEVER table-verifiable — probe before any createNode)

Node type names live outside the dir() symbol table by nature. Every name below is a doc label or a guess until the live `nodeTypeCategories()` scan runs:

- **ML TOP family** (`TOPS-06`/`TOPS-07`): ML Preprocess/Train Computer Vision, ML Preprocess/Train GSplats, ML Preprocess/Train OIDN, ML Train Style Transfer, ML Train Neural Cellular Automata, ML Train Regression, ML Regression Kernel — internal names entirely unverified; any doc title with no matching runtime type is a phantom.
- **ML Computer Vision Inference COP** (`TOPS-06`) — internal name unverified.
- **MtlX VOP new types** (`KAR-06`): `mtlxhextiledimage`, `mtlxflake2d`, `mtlxfractal2d`, `mtlxlatlongimage` are GUESSED internal names from doc labels — UNVERIFIED. Also RE-ASSERT the 4 SYNAPSE-emitted names (`mtlxstandard_surface`, `mtlximage`, `mtlxgeompropvalue`, `mtlxnormalmap`) still exist post-1.39.5-bump before trusting any material tool on H22.
- **New LOP types** (`KAR-07`): Texture Material Library / Image Filter / Karma Blocker Light Filter — internal names unverified.
- **Karma Volume VOP** (`KAR-09`): internal name unverified (scan `kma*volume*`).
- **Instancing/scatter LOP names** — wave-1 carry-over (`SOL-03`): `scatterinstances` may be phantom; probe guards it.

### Tier C — coverage blind-spots (ABSENT from table but REAL — do NOT auto-reject; allowlist)

The headless introspection table covers `hou`/`pdg`/`pxr` only and omits GUI-dependent submodules. Absence here is a scope limitation, never a phantom verdict:

- **`hdefereval.*`** (`TOPS-03`) — outside table scope entirely; live-proven (imported in `shared/bridge.py` R2/R8 + `handlers_tops/diagnostics.py:399`). Allowlist.
- **`hou.ui` / `hou.qt` / GUI submodules** — 0 children in the headless table (the P2 phantom-guardrail trap). Allowlist; verify in-session only (`NWS-09` probes go through execute_python in a GUI session for behavior, though its 7 symbols ARE table-present on real classes).
- **`hou.lop.*`** — 0-child blind spot from wave 1. Checked for `NWS-08`: `hou.LopNetwork` is a top-level class, not affected. Keep the allowlist for genuine `hou.lop.*` references.
- **VEX language functions** (`NWS-11`/`NWS-12`) — never dir()-verifiable by nature; the gate is the vcc probe, not the table.
- **CLI flags** (`KAR-01`/`KAR-04`/`KAR-05`/`KAR-13`/`KAR-14`: husk/imaketx) — process CLI surface; the gate is `--help` output, not the table.

---

## ESCALATE

Breaking changes / version-bump smells. Each needs a human-visible decision or a priority probe during the port waves.

| ID | What breaks / smells | Severity driver |
|---|---|---|
| `NWS-03` | `hou.CopNode.planes` removed; `handlers_cops.py:446,684` silently degrade to `planes:[]` (try/except-guarded — no error surfaces) + stale corpus recipe at `copernicus_python_api.md:315` | **Live silent data loss on H22 today.** Migration surface table-verified — highest-priority port-wave item |
| `KAR-08` | karma/husk schemas migrated string properties → relationships; `get_usd_attribute`/`set_usd_attribute` cannot see or author them | Silent-breakage class: reads return None with no error |
| `KAR-02` | Pixel Filter Size parm REMOVED from both render-settings LOPs (table-confirmed via parm probe pending) | Corpus recipe stale; backwards-compat claimed but unverified |
| `KAR-01` | husk default flips from 1 frame → full stage frame range | Any flag-less husk invocation silently multi-frames (render-farm cost risk) |
| `KAR-03` | Default output naming gains delegate name | Two pinned path assumptions (`handlers_render.py:~431` synthesized default; `solaris_compose_tools.py:55` productName trap) need re-verification |
| `KAR-06` | MaterialX 1.39.5 bump | The 4 hardcoded mtlx type names SYNAPSE emits are rename/retire exposure |
| `KAR-13` | ACES 3.0 + linear-space mipmaps + imaketx 16-bit float + `--opaque-detect` | `aces_color_management.md` actively teaches the ACES 1.3 config — stale guidance, not just missing |
| `KAR-14` | husk licensing system changed | Chance to replace the blind Indie flipbook fallback with detection — or a new silent-failure shape |
| `TOPS-01` | Doc names the event wrapper `pdg.EventHandler`, SYNAPSE docs say `PyEventHandler` | Doc-identity drift only (both classes real, code doesn't depend on the name) — fix docs after probe |
| `NWS-01` | 5 `hou.Node` base-class methods removed | Zero callers — COVERED, but phantom-guard must stay current |
| `NWS-02` | `hou.ChannelEditorPane` → `hou.ChannelEditor` rename | Zero callers — COVERED, emit only the new name |

---

## How to use this

1. **Every candidate above is DOC-CLAIM until its probe runs under H22 hython** — including the VERIFIED ones. VERIFIED clears *symbol existence* in the committed 22.0.368 dir() table only; behavior, signatures, parm names, node-type names, VEX functions, and CLI flags all wait on their runtime probes (`scripts/h22_probe_candidates.py` → `h22-probe-adjudicate`, same pipeline as wave 1).
2. **Feed `harness/notes/h22_doc_candidates_wave2.json` to the flywheel as `ratified:false` entries.** Nothing here self-ratifies; the human ratification gate in `flywheel_queue.json` stays the promotion authority.
3. **This report never mutates code.** It is intel for the port waves (`h22-port-wave`), the corpus re-seed, and the phantom guard — the doc-scout lens is read-only external, writes only under `docs/` + `harness/notes/`.
4. **Docs = intent, runtime = truth.** Where this report and the live H22 runtime disagree, the runtime wins; where the doc and the symbol table disagreed, the table already won (`TOPS-02`'s `workItemById` catch).
5. Cross-wave links: `NWS-03` closes wave-1 `HOM-02` at the intel level; `NWS-04` supplies the implementation for the stats `cops_analyze_render` has always advertised; Tier C allowlists carry forward from wave 1 unchanged.
