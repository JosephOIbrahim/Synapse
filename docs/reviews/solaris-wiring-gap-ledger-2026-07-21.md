<!-- Recon ledger: SYNAPSE Solaris wiring + node recognition on H22.0.368.
Produced 2026-07-21 by a 27-agent read-only workflow (26 reported, 1 died on a
StructuredOutput retry cap: the live-path lens, covered by corroboration).
3.57M subagent tokens, 1083 tool calls. Phase 0 of section 3 is committed at
6bbb302; contradiction C1 was caused by a working-tree change made DURING the
recon and is settled at 218 Lop entries / 100%. -->

# SYNAPSE Solaris/LOP Hardening — Decision Ledger
**Target:** H22.0.368 · **Source:** 25 independent recon passes · **Synthesis verified:** 4 spot-checks re-run live this session

---

## 0. HEADLINE

The validation layer is excellent and unreachable. The build layer is reachable and unvalidated.

SYNAPSE has a probe-verified H22 LOP catalog, a live-`hou` node-type oracle, a fail-loud label-wiring resolver, and an atomic rollback builder. **None of them are on the code path an artist actually hits.** Every gap below is a routing failure, not a knowledge failure. Almost nothing here needs to be invented — it needs to be wired.

---

## 1. ASSET REGISTER — do not rebuild

### 1.1 Validation & recognition (strong, correct, wired to *one* path)

| Asset | File:line | State |
|---|---|---|
| `HouExistenceOracle` — live `hou.nodeType(cat,name)` type oracle, no coverage ceiling | `python/synapse/host/existence_adapter.py:39-47` | built + wired (`graph_builder.py:67-70`, `graph_synth_runtime.py:59-62`) + docstring records why scout was *refuted* for this job |
| `GraphValidator` 5 phases + `_lop_ordering_check` | `python/synapse/cognitive/graph_validator.py:38-395` | error/advisory severity split is reasoned, not accidental (`:305-309`) |
| `GraphBuilder` atomic build: TOCTOU re-validate, one undo group, destroy-created-inside-group on failure, structured FAILED | `python/synapse/host/graph_builder.py:105-192` | **This is the reference rollback pattern.** Pinned `tests/test_graph_builder_mile3.py:311-333` |
| Per-major catalog resolution, no cross-major fallback, blake2b integrity | `python/synapse/core/lop_knowledge.py:54-113`, `python/synapse/core/wiring.py:66-142` | fails loud naming the expected filename |
| `wire_by_label` / `resolve_input_index` — fail-loud label→index | `python/synapse/core/wiring.py:166-216` | correct design, zero LOP callers |
| MCP process routing: `propose_graph`/`instantiate_graph` deliberately NOT intercepted in-process (no `hou` there) | `python/synapse/mcp/server.py:888-897` | correct and load-bearing |

### 1.2 H22 truth artifacts (probe-authored, current)

- `harness/notes/h22_lop_catalog_live_22.0.368.json` — **218 LOP types**, per-type `deprecated`/`min_inputs`/`max_inputs`/`is_generator`/`label`. The single richest recognition artifact in the repo. **UNTRACKED** (verified: `?? harness/notes/h22_lop_catalog_live_22.0.368.json`).
- `harness/notes/lop_solaris_probe_22.0.368_2026-07-17.json` — 38 probes, `houdini_version_match: true`, captures the `instancer→copytopoints` silent-alias trap and per-shape-light removal verbatim.
- `python/synapse/cognitive/tools/data/lop_solaris_knowledge_22.json` — 28 entries, 18 probe-confirmed, 6 `known_absent` **all independently verified genuinely absent**. Zero false quarantines.
- `python/synapse/cognitive/tools/data/h22_symbol_table.json` — 35,903 symbols, `truncated:false`. Settled every layout/marshal API question this session without launching Houdini.

### 1.3 Correct Solaris domain knowledge already encoded

- **Merge/sublayer strength inversion** (higher input index = stronger, opposite of raw `subLayerPaths`) — `handlers_solaris_graph.py:196,233,239`. Confirmed against SideFX shipped doc `lop/merge.txt:16` and `lop/sublayer.txt:40`.
- `detect_order_ambiguities` — surfaces, never auto-reorders — `handlers_solaris_graph.py:187-251`, 7 tests.
- `_merge_chain_order` — never permutes an existing spine — `handlers_solaris_assemble.py:156-180`.
- H22 renames already applied in code with doc citations: `copytopoints` (`:57`), `paintinstances` (`:78`); per-shape-light consolidation documented `:62-66`.
- `python/synapse/core/usd_punycode.py` — **27/27 entries verified against the live H22 probe, zero mismatches.** Do not touch.
- MaterialX parenting: shaders created inside `materiallibrary`, never at `/stage` — `handlers_material.py:249,511`.
- `guards.py` — complete 10-function idempotency library, test-pinned (`tests/test_guards.py:745`).
- `assess_render_ready` / `_assess_stage` — pure-pxr, 6-clause, pinned against **real** in-memory USD stages — `solaris_compose_tools.py:389-529`.
- `bind_material` post-bind verification via `ComputeBoundMaterial` — `solaris_compose_tools.py:345-365`. This is the observability pattern to copy.
- Layout-before-`setDisplayFlag` ordering (`handlers_solaris_graph.py:457-481`) — guards a real CUDA double-init segfault. **Do not reorder.**
- `hasattr(node,'setDisplayFlag')` guard `:477` — verified necessary: `hou.Node.setDisplayFlag` absent, `hou.LopNode.setDisplayFlag` present.
- 30s `_SLOW_TIMEOUT` on both Solaris handlers — deliberate anti-spiral, `tests/test_l8_mitigation.py:44`.
- `run_on_main` reentrancy + main-thread fast paths — `main_thread.py:225-328`. Post-v5.33.0, the nested `shot_render_ready → assemble_chain` call is safe.

---

## 2. GAP LEDGER (deduplicated; corroboration count = independent agents reporting it)

### BLOCKERS

| # | Gap | Corrob. | Evidence | Production impact |
|---|---|---|---|---|
| **B1** | **`_SOLARIS_NODE_ORDER` default 800 == `usdrender_rop` 800.** Unranked LOPs sort *after* the render ROP. | 4 | `handlers_solaris_assemble.py:124` (`.get(type_name, 800)`) vs `:86`. Insertion test is strict `>` (`:176`). **184 of 218 live types unranked** (incl. `merge`, `plane`, `shadowcatcher`, `graftstages`, `layerbreak`, `xform`, `prune`). | Ground plane + shadow catcher wired downstream of the ROP. Reported `wired`, laid out cleanly, renders nothing. Silent wrong output. |
| **B2** | **`assemble_chain` has ZERO undo wrapping while rewiring the artist's existing nodes.** | 3 | Verified live: `grep -c undos handlers_solaris_assemble.py` → **0**. `setInput(0,prev)` at `:364` bare, no try/except. Not in the `integrity_envelope.py:19-28` known-unwrapped list — undocumented. | Mid-loop failure leaves a half-rewired network with no single Ctrl+Z and no record of which links changed. Worse than build_graph: it destroys *existing* connections. |
| **B3** | **`assemble_chain` silently overwrites merge inputs and does not report it.** | 2 (one reproduced end-to-end) | `_reconstruct_chain:137-153` follows **input 0 only** → merge DAG linearized; `merge` absent from order table → 800; `_merge_chain_order` inserts upstream; `:363-368` calls `setInput(0,prev)` without reading or reporting the prior link. Reproduced: 3-asset merge + one light → `geo_0` severed from `merge[0]`. | Merge input index *is* USD opinion strength. SYNAPSE silently changes layer strength and reports two clean new connections. |
| **B4** | **`solaris_build_graph` is fully non-idempotent — identical call twice builds a duplicate parallel network and moves the display flag to it.** | 2 (one reproduced) | `handlers_solaris_graph.py:425` raw `createNode`, no existence check anywhere in `_on_main` (`406-508`). H22 stub `hou.py:17240-17245` documents auto-uniquify. Reproduced: `/stage` 7→14 children, `display_node` moved to `OUTPUT1`, `status='created'`, `warnings=[]`. | Core artist loop is build→look→rebuild. Second build is drawn *superimposed* on the first. Invisible until it doubles the cook or shows up in the render. Makes SYNAPSE unsafe to point at a populated shot. |
| **B5** | **Live creation paths perform ZERO node-type validation.** All H22 recognition knowledge is unreachable from them. | 5 | `grep known_absent\|lop_knowledge\|node_type_exists python/synapse/server/` → **empty**. `handlers_solaris_graph.py:425` and `handlers_node.py:61-63` both raw. Knowledge reachable only via `propose_graph`/`instantiate_graph`. | `createNode('grid')` for a ground plane raises bare `OperationFailed` — while `known_absent['grid']` holds the exact remediation ("use the plane LOP"). One bad type rolls back the entire N-node build. |
| **B6** | **Panel system prompt teaches the INVERTED layer-strength rule.** | 3 | Verified live: `system_prompt.py:177` — *"input 0 has highest opinion strength in USD"*. Contradicts `handlers_solaris_graph.py:196,233,239`, SideFX `lop/merge.txt:16`, and the live `GetPropertyStack` probe. Also `:121`. | The LLM builds every merge/sublayer stack backwards. Lighting/material overrides lose to base layers. No error, wrong render. **Cheapest blocker in the repo to fix.** |
| **B7** | **Templates author ZERO parameters.** | 2 | All 7 `TEMPLATES` executed: `parms_authored=0` each. `solaris_graph_templates.py:45` (camera), `:56` (render tail). 0/7 set `usdrender_rop.loppath`. | The one-shot "build me a scene" path yields a topologically plausible graph where nothing is configured: unaimed camera, no resolution, no output path, ROP with no LOP path. Renders black. |
| **B8** | **RAG corpus re-teaches 15 phantom light `createNode` sites.** | 3 | `rag/skills/houdini21-reference/lighting.md:163,324,392,490,532,547` ×9 `rectlight`, ×4 `spherelight`, ×1 each disk/cylinder. `semantic_index.json:827` describes all four as current. All absent from the 218-type catalog. | Code/corpus divergence firing on the highest-traffic Solaris surface. The fix landed in code and the knowledge catalog; the corpus that feeds `knowledge_lookup`/`scout` still hands the model failing code. Any 3-point rig request. |
| **B9** | **`karmarenderproperties` is DEPRECATED on 22.0.368 and is in the shared render tail of every template.** | 5 | Live catalog: exactly **two** deprecated LOPs — `karma`, `karmarenderproperties`. Emitted `solaris_graph_templates.py:56,215,272,337`; `planner.py:700`; `render_recipes.py:581,713,895`; `pipeline_recipes.py:413,997`; `hda_recipes.py:193`; `prompt_to_hda.py:238`. **`tests/test_solaris_graph.py:616-619` actively pins the deprecated spelling.** | Every SYNAPSE-built render chain plants a node SideFX deprecated two majors ago. Studios with a no-deprecated-nodes review rule bounce the shot. Breaks hard on the next major, and the suite has been asserting the broken name. |
| **B10** | **`assess_render_ready` has no lights clause — certifies an unlit scene as render-ready.** | 1 | `solaris_compose_tools.py:389-505`: clauses are rendersettings/camera/composition_errors/materials_bound/output_path/aovs/xpu_compatible. `ready = all(v=='pass')` `:503`. `build_karma_xpu_shot` creates zero lights. | The sanctioned XPU shot builder produces a scene its own validator green-lights and which renders pure black. |
| **B11** | **`create_material(category=…)` returns a material path that does not exist; `assign_material` never validates it.** | 1 (reproduced) | `handlers_material.py:240-243` writes to `/materials/{category}/{name}`; `_query_material_usd_path:102-111` walks **direct children of `/materials` only** → falls back to `/materials/{name}` `:88` → written verbatim to `matspecpath1` `:320`. Only `prim_pattern` is validated `:333`. | Both calls report success. Artist gets default grey at render with no error anywhere. |

### MAJOR

| # | Gap | Corrob. | Evidence | Impact |
|---|---|---|---|---|
| M1 | 218-type live catalog is **untracked**, has no producer script, zero code readers | 4 | Verified: `?? harness/notes/h22_lop_catalog_live_22.0.368.json`. `grep h22_lop_catalog_live` → 0 hits repo-wide | One `git clean` destroys the only full-surface H22 recognition artifact. CI cannot see it. |
| M2 | `build_graph` cannot reference an existing scene node — extension is impossible via the structured tool | 2 | `handlers_solaris_graph.py:56-62` rejects any connection endpoint not in the payload. Documented workaround `system_prompt.py:139-146` routes to raw `execute_python` (ungated, full `__builtins__`) | The most common Solaris op after initial build falls off the audited path into arbitrary code exec. |
| M3 | `SynapseUserError` does not accept `suggestion=` → **TypeError on every invalid-graph rejection** | 1 | `core/errors.py:22-30` (no `__init__`) vs `handlers_solaris_graph.py:315-318` and `handlers_solaris_compose.py:106`. Reproduced: `TypeError: takes no keyword arguments`. Lands in bare `except` `handlers.py:562` | Every typo'd node id / cycle / bad display_node surfaces as internal Python noise. The designed diagnostic is unreachable. |
| M4 | `build_graph` silently drops unresolvable parm names, reports success | 2 | `handlers_solaris_graph.py:434-437` — `if p is not None`. `resolve_param` imported `:18`, never applied. No parmTuple branch, no miss reported | Model passes `intensity`/`exposure` on `light::2.0` (punycode parms) → all dropped, success returned. Rig at defaults, artist believes it's dialed in. |
| M5 | `_set()` in compose tier discards every parm failure except `engine` | 1 | `solaris_compose_tools.py:75-90`; only `:174` captures the bool. camera/resx/resy/productName/primpath/num_files/filepath# all discarded. Result dict reports them as facts `:222-239` | Green `created` dict listing a camera prim and 1920×1080 output; Karma renders black. |
| M6 | `num_files` (sublayer multiparm count) unverified on H22 — 5-layer dept stack may silently collapse to 1 | 1 | `solaris_compose_tools.py:150` return discarded. H22 knowledge `sublayer.key_parms` = `[filepath#, positionindex, positiontype]` — `num_files` absent, and the entry carries an explicit H21→H22 drift gotcha. `num_files` is Folder-type (H21 artifact) so leaf-only probe omission is *not* proof of absence | The tier's entire USD-correctness premise. Only `layout.usd` loads; all five reported as wired. |
| M7 | Layout: absolute (0,0), no existing-node awareness | 3 | `handlers_solaris_graph.py:466,469` pass no `start_x/start_y`; `handler_helpers.py:455-558` never reads `parent.children()` / `.position()` / `.size()`. Reproduced live: two builds → 4/4 tile-on-tile overlap, dx=dy=0.000 | See §5. |
| M8 | Layout: within-layer order is **alphabetical**, not input-index → guaranteed crossings on merges | 3 | `handler_helpers.py:543-544,555-558` uses `sorted_ids` order; `conn['input']` never passed. Reproduced: merge inputs 2 and 3 drawn crossed | `detect_order_ambiguities` tells the artist to eyeball merge input order; the layout scrambles exactly that. |
| M9 | Layout: no parent barycenter → trunk teleports sideways at first layer boundary | 2 | `handler_helpers.py:555-558`; parent x never consulted. Reproduced: `geo` @x=+3.50, its own child `matlib` @x=0.00 | Stated promise ("clean vertical columns, studio style") not delivered on any multi-root graph. |
| M10 | Zero netbox / sticky-note authoring anywhere in production | 1 | `grep createNetworkBox\|createStickyNote` across `*.py` → 0 production hits. All APIs confirmed present in H22 symbol table | 60-node shot arrives as one undifferentiated 68-unit column. |
| M11 | Timeout race: a build in flight at 30s completes into the scene *after* the artist is told it failed and to retry | 1 | `main_thread.py:296-298` checks `abandoned[0]` only *before* `fn()`; residual documented `:288-295`. Error text `:312-316` says "Try again in a moment" | Retry builds a second complete graph. The exact spiral the 30s bump was meant to kill. |
| M12 | Failed mutations produce zero provenance — no IntegrityBlock, no created-node list | 1 | `handlers.py:524-529` `_submit_logs` only on the success path; all four except arms `:538-567` return flat `error=str(e)` | Half-built network leaves no audit trace. §16 observability sees only successes; failure rates structurally invisible. |
| M13 | Rollback failure logged to a server logger, original exception re-raised unchanged | 1 | `handlers_solaris_graph.py:488-494` `logger.warning` then bare `raise` | Artist sees "Hit a snag" and reasonably assumes nothing happened. 4 stranded nodes in `/stage`. |
| M14 | `performUndo()` called with no undo-enabled guard | 1 | `grep isEnabled\|areEnabled\|disableUndos python/synapse/` → 0 hits in `server/`. `handlers_solaris_graph.py:489` unconditional; same pattern ×8 in `handlers_cops.py` | If the group never opened, `performUndo()` pops the artist's own last action. **Unverifiable from the symbol table — needs a live probe.** |
| M15 | `assemble_chain` mode `nodes`/`after` steals already-wired nodes with no check and no skip entry | 1 | `handlers_solaris_assemble.py:258-263, 278-283` — no `_is_unwired` test (contrast `:247`); `:364` unconditional `setInput` | Mid-chain node yanked out, former upstream dangling, reported under `wired` as a clean addition. |
| M16 | `assemble_chain` cannot see anything the material handlers built | 1 | `_is_unwired:127-129` requires **both** zero inputs and zero outputs; `handlers_material.py:235,315` both `setInput(0,node)` | The repair tool reports "nothing to wire" on exactly the misplacement `_wire_display` already flagged as `needs_rewire`. |
| M17 | Disjoint existing chains silently orphaned (single anchor only) | 1 | `handlers_solaris_assemble.py:314-318` keeps one anchor; other chains appear in neither `chain_paths` nor `skipped` | Half the network ignored, reported as success. |
| M18 | Layout translates the entire existing network — anchor position applied to chain ROOT | 1 | `handlers_solaris_assemble.py:386-393` + `handler_helpers.py:494-495` places `nodes[0]` at origin | Adding one light teleports a 10-node hand-laid network ~11 units down. |
| M19 | Zero behavioral tests on the mutation bodies of both Solaris handlers | 3 | `grep _handle_solaris_build_graph tests/` → nothing. All 32 `test_solaris_assembly.py` tests exercise pure tables. `conftest.py:103,296-297` makes `undos` a MagicMock — rollback is structurally untestable | Every gap above ships green. A fix has no failing test to drive it. |
| M20 | `_infer_parent` misroutes ~18 real LOP types to `/obj`; `intent`/`current_network` params were designed and never shipped | 2 | `routing/planner.py:52` signature is `(params)` only vs spec `(params, intent, current_network)`. Ran it: `sopcreate`→`/obj`, `camera`→`/obj`. Regression tests were rewritten to inject context and quietly dropped both from the parametrized guard (`tests/test_solaris_context.py:73-93,139-155`) | Artist standing in `/stage` says "add a camera" → lands in `/obj`. Tests fitted to the bug. |
| M21 | Solaris block never fires when the artist is in `/obj` (the Houdini default) | 1 | `system_prompt.py:253` gates on `/stage`/`/lop` in the network path; `synapse_panel.py:1598` defaults `/obj`. `_OBJ_CONTEXT_GUIDANCE:203-216` mentions Solaris/LOP/Karma/USD **zero** times | "Build me a lookdev network" from `/obj` gets SOP guidance. Every wiring rule withheld from the request that needs it. |
| M22 | The prompt's anti-phantom safety rule points at a tool that structurally cannot answer it — and returns **false confidence for the removed lights** | 2 | `scout.py:149` `_DOTTED_RE` requires a dotted prefix; bare `rectlight` yields empty `symbols`, no verdict. Doc-presence fallback resolves `rectlight`→`pxr.UsdLux.RectLight` = EXISTS. `existence_adapter.py:6-13` records the same refutation (`node_type_exists("box","Sop")→False`) | The guardrail manufactures the false confidence it exists to prevent, on exactly the four removed light types. |
| M23 | `solaris_guardrails.py` — 295 lines, test-pinned, **zero production callers** | 2 | `grep solaris_guardrails\|PRODUCTION_RULES\|check_light_intensity` → only its own file + its test. Own docstring `:22-27` concedes wiring is "a deliberate follow-up pass" | Lighting Law, camera-target validation, tuple-parm check all inert. Passing tests imply an enforced standard that isn't. |
| M24 | `guards.py` reachable only from `execute_python` | 2 | `handlers.py:76,1208-1209` only | Using the safer structured tool gives *less* idempotency protection than the ungated arbitrary-code path. Incentive inverted. |
| M25 | Compose tier (`shotsetup_karma_xpu`, `matlib_bind`, `assess_render_ready`) has **zero MCP TOOL_DEFS entries** — WS-only | 3 | `grep` in `_tool_registry.py` → 0 hits, yet `tool_filter.py:171-172` advertises all three and `bridge_adapter.py:161` marks shotsetup disk-writing | The only correct `engine=xpu` builder is unreachable by the LLM. The `touches_disk` APPROVE elevation is dead code. "karma xpu" is unsatisfiable on every reachable path. |
| M26 | `_detect_karma_engine` never checks the `engine` parm | 1 | `handlers_render.py:210` looks for `renderer`/`karmarenderertype`/`renderengine`; real parm is `engine` (`solaris_compose_tools.py:174`, H22 knowledge `key_parms:['engine','primpath']`) | SYNAPSE cannot recognize its own XPU node. Reports generic "karma". |
| M27 | `_find_render_rop` returns a `karmarendersettings` LOP as if it were a ROP | 1 | `handlers_render.py:149-156` `_RENDER_TYPES` includes it. Catalog: `karmarendersettings` max_outputs=1 (LOP), `usdrender_rop` max_outputs=0 (ROP) | Render path handed a settings LOP. On the XPU shot there is no ROP at all. |
| M28 | Auto-fix discovers only `karmarenderproperties` by type name | 1 | `handlers_render.py:1503` exact string compare; `handlers_solaris_assemble.py:101` `scene_template` emits `karmarendersettings` | Quality parms written to the ROP where they don't exist. Silent no-op, identical noisy re-render, ×3 retries of farm time. |
| M29 | MCP `initialize` tells every client all mutations are undo-group transactions | 1 | `python/synapse/mcp/server.py:460-461`. Falsified by `handlers_solaris_assemble.py` (0 undo) and `handlers_node.py` (0 undo, verified) | The LLM is explicitly misinformed about the safety floor on the tools that lack it, so it retries freely. Converts a code gap into a behavioral amplifier. |
| M30 | Both Solaris tools advertise `destructiveHint=False, idempotentHint=True` | 1 | `_tool_registry.py:698,726` tuples end `False, False, True` | Both hints wrong in the unsafe direction. Clients skip the artist prompt and treat retry as free. |
| M31 | `_ORDER_DEPENDENT_TYPES` carries 4 phantoms and misses the real multi-input H22 types | 3 | `handlers_usd.py:1599-1608`: `merge::2.0`, `graft`, `graft::2.0`, `switchif` all absent on H22. Missing: `graftstages`(max 9999), `graftbranches`, `layerreplace`, `addvariant`, `reference`, `shotswitch`. Same drift `handlers_solaris_graph.py:183` | `graftstages` is *the* shot-assembly node; two inputs landing on the same destination path silently overwrite, and both detectors report CLEAN. |
| M32 | Render pre-flight validates the wrong branch — `render_node` is not an alias for `node` | 3 | `autonomy/validator.py:299-301` sends `render_node`; `handlers_usd.py:1641` reads `node`; `core/aliases.py:22` has no `render_node`. Falls through to display-node auto-discovery | Green light it did not earn. Multi-branch stage: validates the beauty branch, submits the deep branch. |
| M33 | No sublayer-LOP strength-stack guardrail (`filepath#`/`positionindex`/`positiontype`) | 2 | Both detectors key on multi-**input** topology only. `grep positiontype\|positionindex python/synapse` → data files only | A 5-layer dept stack on one sublayer node has one input, reports `clean:true`. The highest-stakes strength decision in a shot is unguarded — and the controlling parm changed name in H22. |
| M34 | `bind_material` never moves the display flag or re-lays-out | 1 | No `setGenericFlag`/`layoutChildren` in `bind_material`; `:314-316` reads `displayNode()` | First bind invisible in viewport (reports `bound`); second bind hangs a sibling off OUTPUT, orphaning the first. |
| M35 | `ensure_mtlx_material` has no live caller and violates the repo's own materiallibrary cook gotcha | 1 | `:266` `matlib.createNode(...)` with no prior cook; catalog gotcha: "call `matlib.cook(force=True)` first, else `createNode()` returns None" | `matlib_bind` can only bind pre-existing materials. If wired as-is, `sh` is None → AttributeError. |
| M36 | `scripts/verify_compose_render.py` — the only live `[REAL]` verification vehicle for the compose tier — is API-drifted and TypeErrors on both calls | 1 | `:107` passes nonexistent `params=` kwarg; `:114` 4 positional args → "multiple values for `input_node`". Referenced by no test, no CI | Every "verified live on H21.0.671" claim in that tier is unreproducible. No runnable path to re-verify on H22. |
| M37 | `graph_synth` drops `ProposedNode.position` entirely; no display flag set | 1 | `grep -n position host/graph_builder.py` → nothing. No `setDisplayFlag` in the builder. Sibling path does it (`handlers_node.py:65`) | Correct wiring, all nodes stacked at (0,0), viewport unchanged → reads as a failed build → re-run → duplicates. |
| M38 | `MergeStrategy` parsed, zero consumers — `replace_children` silently behaves as `merge` | 1 | `grep merge_strategy` → 3 sites, all parse/store. Nothing in builder/validator/handlers | "Rebuild this network" adds instead of replaces. The documented APPROVE gate does not exist. |
| M39 | `propose_graph` MCP schema is an opaque `object` — 10-field nested shape undocumented; missing keys raise bare KeyError | 1 | `_tool_registry.py:1124-1126`; `tools/propose_graph.py:43-45,67-69` | Model must infer `'new'/'existing'` and case-sensitive `'SOLARIS'` from a 5-word parenthetical, and gets raw Python errors instead of structured `errors[]` — no self-correction loop. |
| M40 | LOP-phase `network_type` check is **case-sensitive** while P4 normalizes — `'Solaris'` disables the entire known-absent blocklist | 1 (reproduced) | `graph_validator.py:312` exact `!= "SOLARIS"` vs `:435` `.upper()`. Reproduced: `'SOLARIS'`+`instancer`→invalid; `'Solaris'`→**VALID**. Every fixture uses uppercase | One capitalization loses all six H22 rejections. Proposal validates clean and instantiates. |
| M41 | Three mutually exclusive `lighttype` vocabularies in-tree, none probed | 1 | `render_recipes.py:310,318` `'UsdLuxRectLight'`; `recipe_book.py:437-439` `'distantlight'`; `hda_recipes.py:113` `'distant'`. `'UsdLuxRect'` occurs 0× in any probe artifact | At most one is real. Wrong token → light silently stays default sphere. Unprobed phantom class. |
| M42 | `recipe_book` 3-point rig wires three lights into a merge — the anti-pattern the templates document as wrong | 1 | `recipe_book.py:437-445` vs `solaris_graph_templates.py:11-13` | Two subsystems teach opposite rules for the most basic Solaris wiring question. |
| M43 | `recipe_book` emits an LLM prompt targeting `/obj/geo1` for LOP-context recipes | 1 | `recipe_book.py:955` default parent, `:986` imperative one-node-at-a-time instruction, `:434` `'context':'LOP'` | Light LOPs cannot be created in a SOP net. |
| M44 | `lighting_rig` has no rim light — a 3-point request returns 2 points | 1 | `solaris_graph_templates.py:251` default `["domelight","light","light"]` | The single most common lighting request, silently wrong, with authoritative-looking node names. |
| M45 | `create_node` response echoes the **requested** type, hiding silent aliasing | 2 | `handlers_node.py:68-70` uses `node_type` (caller string), not `new_node.type().name()`. Catalog documents `instancer`→`copytopoints` alias; probe shows `domelight`→`domelight::3.0` | Artist and LLM both believe type X was created when Houdini made Y. Downstream parm sets target the wrong namespace. |
| M46 | No alembic import path exists | 1 | `grep -i alembic python/` → one `.abc` string in `dependency_map.py:44`. No handler accepts `.abc` | Most common asset-ingest op in a VFX shop has no tool → falls to ungated `execute_python`. |
| M47 | `_resolve_lop_node` rejects `/stage` and hard-fails with no selection | 1 | `handlers_usd.py:218-233` gates on `hasattr(node,'stage')`; `hou.LopNetwork.stage` absent from symbol table (`dir()`-based, so absence is real) | The most natural path is rejected; headless/agentic flows hard-fail before doing anything. |
| M48 | Corpus teaches `sublayer.parm("position")` — absent as spelled on H22 | 2 | `solaris_nodes.md:601-602`, `scene_assembly.md:49,124,144`. Probe: `h21_key_parms:{position:absent}`; real parms `positiontype`/`positionindex` | `parm()` returns None → silent no-op (layer strength never set) or AttributeError. |
| M49 | `usd_stage_composition.md` states sublayer direction backwards and contradicts itself 27 lines later | 1 | `:260` "weakest to strongest" vs `:287` "strongest position = index 0" vs `:386` "sublayers are WEAKEST". Ground truth `HUSD_EditLayers.h:41-47` | Dept stack composes without error and subtly wrong. |
| M50 | H22 catalog behavior is not test-pinned; CI exercises H21 truth only | 2 | `tests/test_lop_flywheel.py` version stamp `:132` is 21.0.671; standalone loader resolves `_21`. `plane` (real on H22) asserted rejected; `instancer`/`rectlight` (broken on H22) asserted passing | Integrity is pinned; **behavior is not**. Injection seam already exists (`graph_validator.py:46`) — ~10 lines to close. |
| M51 | Nothing enforces or checks RenderSettings prims under `/Render` | 1 | `lop/rendersettings.txt:19` requires it. Correct path hardcoded in 2 places, zero validators. `primpath` is artist-writable | husk finds no valid RenderSettings; failure surfaces as an empty render at the end of a farm submission. |
| M52 | No modeling of material **binding strength** (`bindstrength#`) | 2 | H22 probe lists `bindstrength#`/`bindmethod#`/`bindpurpose#`; `handlers_material.py:319-320` sets only `primpattern1`/`matspecpath1`. `grep bindstrength python/` → probe artifact only | The most common "connected but wrong" material failure: collection binding loses to descendant bindings. Network perfect, `validate_ordering` clean. |
| M53 | Panel prompt pinned to Houdini 21.0.671 on an H22 target | 4 | `system_prompt.py:51,184,188`; `_tool_registry.py:1120,1151` ("live H21 runtime"); `agent_prompts.py` same | Model biases ambiguous API judgements toward H21 and second-guesses correct rejections. |
| M54 | `emitted_node_types.json` gate is literal-only — blind to interpolated `createNode` | 1 | `scripts/extract_emitted_node_types.py:123` category `createNode_literal`. `planner.py:648` f-string emits `grid`/`font` (both **absent** on H22) — all four geo types unregistered | The phantom gate has a permanent blind corridor. Has a real catch history (`b793c99` purged 9), so this is a live mechanism with a structural hole. |
| M55 | `_layout_dag_vertical` branch collapse: an unrelated root's wire runs down the trunk through intervening nodes | 1 (reproduced) | `handler_helpers.py:552-553` — single-node layer lands exactly on `start_x`. Reproduced: `dome`→`merge` edge spans depth 0→3 along x=0.00 through `matlib` and `assign` | On the most common Solaris shape, the light's wire is drawn through two unrelated LOPs. Artist cannot read opinion order from the graph. |

### MINOR (compressed)

`payload` phantom in the order table (`handlers_solaris_assemble.py:45`) · `_SOLARIS_CHAIN_TEMPLATES` dead, contains SOP names, cited as a shipped deliverable in `.gate_passed` · `mergepointinstancers` false-positives via `startswith("merge")` · `lighting_rig` empty-input guard unreachable (`solaris_graph_templates.py:251-253`) · 4 untested `ValueError` guards + untested `overlay_connections` branch · overlay node without `'type'` passes validation then KeyErrors inside the undo group · `hdri_lighting`/`lighting_rig` duplicate the render tail (a `karmarenderproperties` fix will be partial in 3 places) · `dry_run` still takes the mutation lock and emits a phantom live IntegrityBlock · `dry_run` preview paths wrong once the network is non-empty · AOV render-node match doesn't strip `::` (`handlers_solaris_assemble.py:412`) · `after` mode raises while `nodes` mode soft-skips · uniform `"SYNAPSE: build_graph"` comment forced on with `DisplayComment` on every node · `template_params` `**kwargs` splat with no schema `properties` · spacing constants H21-derived, `hou.Node.size` never called · `parent = hou.node()` inside undo group but outside try (`graph_builder.py:131-133`) · `ProposalStore` in-memory, 30-min TTL, dies on restart · `verified_connectivity_H22.json` carries a **refuted** note ("createNode('instancer') will fail") · `h22-cto-roadmap` names the wrong instancer successor (`pointinstancer`, should be `copytopoints`) · `graph_validator.py:300-301` comment asserts `plane` "does not exist in any build" — false on H22 · `docs/verification_ledger.md` LOCKED at 21.0.631 · `shopnet` unreachable from disk-only derivation · SideFX Labs LOPs live outside `$HFS` (9 types) · `houdini/help/files/` HDAs are doc examples, not loadable types · `LOP/README` build line stale (python3.10) · TCPS composition trap documented only in a header comment, no check anywhere.

---

## 3. THE CRITICAL PATH

Ordered by (blast radius × cheapness). Each step is shippable and testable independently.

### Phase 0 — one-line truth fixes (hours)

1. **`python/synapse/panel/system_prompt.py:177` + `:121`** — invert to "HIGHER input index = STRONGER opinion (opposite of raw USD `subLayerPaths`)". Fix the direction-blind test `tests/test_solaris_graph.py:648-651` to assert the *direction*, not the presence of a phrase. → **B6**
2. **`python/synapse/core/errors.py:26-30`** — give `SynapseUserError.__init__` a `suggestion` kwarg. → **M3** (unblocks every Solaris diagnostic)
3. **Commit `harness/notes/h22_lop_catalog_live_22.0.368.json`** + write `scripts/harvest_lop_catalog.py` + add a `harness/verify/checks.py` freshness verb. → **M1** (unblocks steps 4, 5, 8)
4. **`python/synapse/cognitive/graph_validator.py:312`** — `.upper()` the network_type check. → **M40**

### Phase 1 — stop destroying artist work (days)

5. **`python/synapse/server/handlers_solaris_assemble.py`**
   - Wrap `_on_main` in `hou.undos.group` + explicit rollback (copy `handlers_solaris_graph.py:419,483-494`). → **B2**
   - Extend `_SOLARIS_NODE_ORDER` from the committed 218-type catalog; change the default from `800` to a sentinel that sorts *before* the render tier and returns an `unranked` warning; drop the `payload` phantom. → **B1**
   - `_reconstruct_chain`: walk all inputs, not `inputs()[0]`. → **B3**
   - Wiring loop: read the prior connection, report every overwrite in the response (copy the `bind_material` observability shape, `solaris_compose_tools.py:345-365`). → **B3**
   - Modes `nodes`/`after`: apply `_is_unwired`, emit `skipped` for already-wired targets. → **M15**
   - Report un-merged disjoint chains. → **M17**
   - Fix the layout origin: anchor position belongs to the anchor, not the chain root. → **M18**

6. **`python/synapse/server/handlers_solaris_graph.py`**
   - Call `guards.ensure_node` instead of raw `createNode` at `:425`. → **B4**
   - Call `lop_type_exists`/`canonical_type` (`solaris_compose.py:105-134`) + the committed catalog **before** opening the undo group; reject with the catalog's remediation string. Add a deprecation advisory. → **B5, B9**
   - Route parm names through `resolve_param` + a `parmTuple` branch; return `parms_missed` in the response. → **M4**
   - Add an `existing_nodes` schema field so extension stops routing to `execute_python`. → **M2**
   - On failure, return the created-so-far list and rollback status in the payload, not just `str(e)`. → **M12, M13**

7. **`python/synapse/mcp/_tool_registry.py:698,726`** — flip `destructive=True`; `idempotent=False` until step 6 lands. **`python/synapse/mcp/server.py:460-461`** — correct the safety claim. → **M29, M30**

### Phase 2 — make the output correct (days)

8. **`python/synapse/server/solaris_graph_templates.py`** — `karmarenderproperties` → `karmarendersettings` in **all three** tail copies (`_build_render_tail:56`, `lighting_rig:272`, `hdri_lighting:337`, `render_pass_split:215`); collapse the duplicated tails into one function first. Then `planner.py:700`, `render_recipes.py:581,713,895`, `pipeline_recipes.py:413,997`, `hda_recipes.py:193`, `prompt_to_hda.py:238`. Update `tests/test_solaris_graph.py:616-619` and `tests/test_solaris_assembly.py`. → **B9**
9. **Templates author parms.** Minimum: `usdrender_rop.loppath`, camera `focalLength`+transform, `resolutionx/y`, `productName`, `engine`. Add a `lookdev` template. Add the rim light to `lighting_rig:251`. → **B7, M44**
10. **Register the compose tier in `_tool_registry.py`** — `shotsetup_karma_xpu` / `matlib_bind` / `assess_render_ready`. Add a lights clause to `_assess_stage` and make `build_karma_xpu_shot` *call* `assess_render_ready` before returning. Capture every `_set()` return. → **B10, M5, M25**
11. **Corpus purge** — `rag/skills/houdini21-reference/lighting.md` (15 sites), `solaris_nodes.md:601`, `scene_assembly.md:49,124,144`, `usd_stage_composition.md:260`, `semantic_index.json:827,1566`, `_solaris_fix/solaris_network_blueprint.md`. Add a `tests/test_corpus_lop_conformance.py` on the `usdlux` precedent. → **B8, M48, M49**
12. **`python/synapse/server/handlers_material.py`** — `_query_material_usd_path` recursive walk; validate `material_path` against the stage in `_handle_assign_material`; set `bindstrength`. → **B11, M52**

### Phase 3 — make it readable (days)

13. **`python/synapse/server/handler_helpers.py:455-558`** — origin offset from existing children's bbox; input-index ordering within a layer; parent-barycenter x; grid-snap to the measured `U=0.2824`. → **M7, M8, M9, M55**
14. **Netbox/sticky pass** — section from the (now-extended) rank table, `fitAroundContents()` + margins. All APIs confirmed present. → **M10**

### Phase 4 — close the honesty loop

15. **`tests/`** — real fake-`hou` coverage for both `_on_main` bodies: double-build idempotency, merge-overwrite reporting, rollback-to-zero, unranked-type placement, input-index→x ordering. → **M19**
16. **Live probe under hython:** `positiontype` default on H22, `num_files` presence, `lighttype` menu tokens, `hou.undos` enabled-guard availability. → **M6, M14, M41**

---

## 4. RECOGNITION VERDICT

| Metric | Value | Source |
|---|---|---|
| Live LOP types on 22.0.368 | **218** | Two independent sources agree exactly: `lop_solaris_probe_22.0.368_2026-07-17.json` `total_lop_types` and `h22_lop_catalog_live_22.0.368.json` `count` |
| Version-collapsed core names | 200 | probe `total_lop_corenames` |
| HDA-defined (from `OPlibLop.hda`) | 114 | `hotl -B`, strict subset of live |
| `lop_solaris_knowledge_22.json` entries | 28 (27 Lop + 1 deliberate Vop cross-ref) | — |
| `known_absent` | 6, **all verified genuinely absent** — zero false quarantines | — |
| `connectivity_22.json` Lop entries | **37 or 196 — CONTESTED, see §6** | — |
| Union recognition (using 37) | **46 / 218 = 21.1%** | — |
| Semantic knowledge (role/parms) | 27 / 218 = **12.4%** | — |
| Label-wiring resolvable | 32 / 218 = **14.7%** (5 catalogued types have `input_labels: null`) | — |
| `_SOLARIS_NODE_ORDER` coverage | 34 real / 218 = **15.6%**; 184 default to rank 800 | verified live |
| Deprecated LOP types on 22.0.368 | **exactly 2**: `karma`, `karmarenderproperties` — SYNAPSE emits the second in ≥11 places | — |
| Recognition consumers on the live creation path | **0** | verified: `grep known_absent\|lop_knowledge\|node_type_exists python/synapse/server/` → empty |
| Disk-only derivability ceiling | 223 names, recall 0.9954, precision 0.9731; **wiring truth NOT derivable** (5 of 198 help pages carry `@inputs`) | — |

**Verdict:** the *quality* of what SYNAPSE knows is high and probe-grounded. The *coverage* is ~1/5 and the *reachability from the artist path is zero*. The 218-type artifact that closes ~80% of the coverage gap already exists on disk and is untracked. This is a wiring problem with a data-plumbing tail, not a research problem.

---

## 5. LAYOUT VERDICT

**Measured live (hython 22.0.368):** LOP tile = **1.1296 × 0.2824** network units, identical across every type probed. Native `layoutChildren` strides: 1.1295 vertical, 2.2592 horizontal, 0.4518 diagonal fan-in stagger. `NetworkBox.fitAroundContents()` padding = exactly 0.20 all sides.

| Property | State |
|---|---|
| Within-build collision | **None.** `V=1.2` = 4.25× tile height, `H=3.5` = 3.1× tile width. Sparse, not colliding. Initial overlap hypothesis **refuted**. |
| Across-build collision | **Total.** Absolute (0,0), zero existing-node awareness. Reproduced: two builds → 4/4 pairs at dx=dy=0.000. |
| Flow direction | Correct (Y-decreasing = top-to-bottom). |
| Layer assignment | Correct — longest-path, not naive BFS. Diamond A→B,C→D gives 0,1,1,2. |
| Within-layer order | **Alphabetical** (`sorted_ids`). Input index never consulted → guaranteed merge crossings. |
| Column formation | **Broken.** No parent barycenter — `geo` at x=+3.50, its own child `matlib` at x=0.00. |
| Wire routing | **Broken.** Single-node layers land on `start_x`, so an unrelated root's wire runs down the trunk through intervening nodes. |
| Netboxes / sticky notes | **Zero production usage.** All APIs confirmed present in the H22 symbol table. |
| Node coloring | Correct by omission — H22 already colors LOPs semantically by type (camera blue, domelight amber, materiallibrary teal). Do not recolor. |
| Spacing provenance | H21-derived constants, `hou.Node.size` available and never called. |
| Nested contexts (sopnet, matlib subnets) | No layout pass at all — falls back to `layoutChildren`. |
| Layout regimes in one network | Two, incompatible: `moveToGoodPosition()` (create_node) vs absolute-(0,0) (build_graph). |
| `moveToGoodPosition` on unwired nodes | `handlers_node.py:60-65` positions before any `setInput` — nothing to be "good" relative to → repeated calls pile up. |
| Test coverage of failures | Zero. All 10 layout tests are MagicMock; real tile dimensions never enter an assertion. |
| `setPositionAfterNode` | **PHANTOM on H22** — 0 hits across 35,903 symbols. Do not reach for it when fixing create_node. |

**Verdict:** the algorithm is sound; the *inputs* are wrong (no origin, no input index, no parent x) and the *semantic layer* (netboxes, sections, notes) does not exist. A one-shot build looks acceptable. A second build, a merge, or any pre-existing content looks broken.

---

## 6. CONTRADICTIONS — flagged, not averaged

**C1 — `connectivity_22.json` Lop coverage: 37 vs 196.**
Five reports say 293 total / **37 Lop**. One report says 476 total / **196 Lop**. This is a 5× disagreement on the single number that decides how much wiring truth exists.
**Likely cause, and it matters:** `git status` shows `M harness/notes/verified_connectivity_22.0.368.json` — *modified in the working tree during this recon*. An agent probably regenerated/expanded connectivity mid-session, so different agents read different files.
**Action:** re-measure `connectivity_22.json` Lop count as step 0 of Phase 1, and decide whether to commit or revert the working-tree modification. Do not plan against either number until settled. **All §4 percentages assume 37 and are the pessimistic bound.**

**C2 — Merge/sublayer opinion-strength direction. RESOLVED, not open.**
`system_prompt.py:177` and `docs/training/karma_xpu_solaris_production_setups.md:91,233` say input 0 is strongest. `handlers_solaris_graph.py:196,233,239`, `handlers_usd.py:1723-1727`, `rag/.../solaris_network_blueprint.md:74` say higher index is stronger.
**The handlers are right.** Ground truth is SideFX's own shipped doc: `houdini/help/nodes.zip → lop/merge.txt:16` ("Layers in earlier inputs are *weaker* than layers in later inputs") and `lop/sublayer.txt:40` ("weaker to stronger, from left to right"), plus a live `GetPropertyStack` probe recorded in `forge/backlog/human_review.json:178-184`. Fix the prompt and the training doc.

**C3 — Sublayer strength: `filepath#` last-strongest vs `setAddLayerPosition(0)` = strongest.**
`solaris_compose_tools.py:123-126` (LOP multiparm, verified H21) vs `HUSD_EditLayers.h:41-47` (C++ API position arg). **These are different surfaces, not a contradiction** — the LOP multiparm inverts relative to the API. But the compose claim is H21-only and **untested** (`tests/test_solaris_compose_tools.py:23-28` pins only the constant list, never the `reversed()` at `:137`). A future "fix" to match raw USD would invert department strength across every shot and the suite stays green.
**Action:** pin the inversion with a test; explicitly set `positiontype` instead of relying on a default; re-probe the default on H22.

**C4 — `instancer` successor: `copytopoints` vs `pointinstancer`.**
`docs/reviews/h22-cto-roadmap-2026-07-16.md:76,130` and `h22-drop-execution-2026-07-15.md:48` say `pointinstancer`. The live probe says `createNode('instancer')` → `created_type: copytopoints`, and `handlers_solaris_assemble.py:57` already ships `copytopoints`. **Probe wins.** The shipped code is correct; the still-open P1 roadmap item points a future fix at the wrong node. `pointinstancer` authors a USD PointInstancer prim; `copytopoints` authors real copies — swapping them changes what lands on the stage. Correct the roadmap.

**C5 — `verified_connectivity_H22.json` carries a claim its own probe refutes.**
The artifact says `createNode('instancer')` "will fail on H22". The probe says it silently succeeds as `copytopoints`. The refutation is written up in two review docs; **the artifact was never corrected** and is cited as evidence in `h22-cto-roadmap:20,76`. Anyone grounding on it writes a `try/except` that never fires while the real failure mode (silent alias + `hou.nodeType()` returning None) goes unhandled.

**C6 — `karmaphysicalsky` on H22.**
One report: present in the 218-type live catalog. Another: absent from `connectivity_22.json`, absent from `lop_solaris_knowledge_22.json` and its `known_absent`, no entry in the symbol table, and the only documented caveat is tagged "(H21)". `hdri_lighting` depends on it.
**Action:** single lookup against the committed 218-type catalog. Cheap, unresolved, blocks the HDRI template.

**C7 — `layoutChildren()`: forbidden or fine?**
`handlers_solaris_graph.py:457-462` abandons it as a CUDA double-init segfault risk with Karma nodes. `solaris_compose_tools.py:208` calls it on `/stage` **after** creating a `karmarendersettings` — the exact hazard. And `system_prompt.py:136,145` + `agent_prompts.py:125` instruct the LLM to always call it.
Either the race is real (compose can segfault an unsaved scene, and the prompt teaches the crash) or it is not (the rationale for the custom engine is a doc lie). **Both are live. Needs adjudication before Phase 3.**

**C8 — `materiallibrary` inline `geopath#` vs separate `assignmaterial`.**
`system_prompt.py:122-124` and `agent_prompts.py:49` tell the model to skip assign nodes. The tool surface (`houdini_assign_material`), the ordering rule (`assignmaterial_requires_material_source`), five `recipe_book.py` recipes, and SideFX's own doc (`lop/materiallibrary.txt:40` explicitly recommends a separate assign node) all say the opposite. Behavior differs by whether the model follows the prompt or the tool descriptions. Also: `assign#` (the per-entry enable toggle) is real and never set anywhere.

**C9 — Did `_solaris_fix` land?**
One report: fully landed, all four legs, exit criterion met (`grep -c 'params.get("parent","/obj")'` → 0). Another: landed *structurally weaker* — `intent` and `current_network` params dropped, signal sets shrank ~50→14, and the regression tests were rewritten to fit the weaker implementation.
**Both true.** The `/obj`-default-bias fix is genuinely in; the context-awareness half is not, and the tests were fitted to hide it (see M20). Do not read "landed" as "done".

**C10 — `handlers_solaris_compose.py` undo/marshal state.**
`.synapse/_vfx_probe_digest.md:6-10` records a P0: "compose handlers mutate off the main thread with zero undo coverage". Verified fixed — `handlers_solaris_compose.py:55,71,89,97,114,120,128,134,148,152` all use `run_on_main` + `hou.undos.group` + `performUndo` rollback. **The digest is stale.** Do not re-fix.

---

## 7. ONE-LINE SUMMARY FOR THE CTO

Build nothing new. Commit one untracked JSON, invert one prompt sentence, add one kwarg to one exception class, then spend the effort routing four existing safety mechanisms (`HouExistenceOracle`, `guards.py`, the 218-type catalog, `GraphBuilder`'s rollback pattern) into the two handlers artists actually call — `handlers_solaris_assemble.py` and `handlers_solaris_graph.py`. Every blocker in this ledger is downstream of that routing.