# H22 Per-Context Post-Mortem — What the Transition Actually Covered

**Date:** 2026-07-17
**Baseline:** SYNAPSE **v5.28.0** (release tag `v5.28.0` = `72de5f1`; later commits on master are docs-only) · Houdini **22.0.368** live
(py 3.13.10 / USD 0.26.5 / PySide 6.8.3 — `harness/state/drop.json`, version fields captured
inside H22.0.368).
**Discipline:** post-mortem, not brochure. Honest coverage is the point. This document maps
where the H22 transition's energy actually went, per Houdini context — including, loudly, where
it did **not** go. A reviewer should be able to see at a glance which contexts are solid and
which are ungrounded.

**Provenance of this document.** Every per-context section below is dropped **verbatim** from
its analyst's dispatch; the file/line/commit citations inside each section were verified by that
analyst within their own dispatch (h22-scribe truth discipline). The connective tissue —
executive summary, the coverage-honesty map one-liners, the cross-context roadmap, and this
provenance — is SCRIBE's, and its load-bearing claims were verified in this dispatch:

- **Baseline / HEAD / tag** — `git log`, `git tag`, `git rev-parse HEAD` (confirmed `72de5f1` = `v5.28.0`).
- **Drop fields** — `harness/state/drop.json` (22.0.368 / 3.13.10 / 0.26.5 / 6.8.3).
- **Artifact set present** — `docs/reviews/h22-now-probes-2026-07-16.md`,
  `docs/reviews/h22-cop-audit-verification.md`, `docs/reviews/h22-live-reconfirm-2026-07-16.md`,
  `docs/reviews/h22-pdg-perception-reaudit.md`, `docs/reviews/h22-qt-smoke.md`,
  `docs/reviews/h22-doc-intel-2026-07-16-wave2.md`,
  `docs/SYNAPSE_COPERNICUS_EXPANSION.md`, `docs/intake/adjudication-sidefx-h22-memo.md` — all
  confirmed present (Glob/`ls`). The `harness/notes/verified_connectivity_22.0.368.json` and
  `harness/notes/perception_truth_22.0.368.json` artifacts are **analyst-cited** (verified within
  the SOP/COP dispatches), not re-verified here.
- **Copernicus builds ratified** — `harness/state/flywheel_queue.json`: `C.4-H22-scaffold-rebuild`,
  `C.3-H22-neural-cops`, `C.10-H22-terrain-exposure` all carry `"ratified": true` (Grep confirmed).

---

## OPEN DECISIONS (human-only rulings — options stated, no ruling invented)

These are scope/naming calls the analysts surfaced that only the human can make. The roadmap
below assumes nothing about their outcome.

1. **CHOP scope ruling.** CHOP got only byproduct catalog coverage this cycle (11 uninstantiated
   rows). It is channels/motion — animation-adjacent, *not* rigging.
   - **Option A (analyst recommendation):** mark CHOP an explicit, documented **non-goal**, so future
     cycles stop generating byproduct catalog rows that read as partial coverage.
   - **Option B:** lift the non-goal and run one intentional CHOP arity+wiring probe (teach
     `host/introspect_connectivity.py:_make_container` to build a `chopnet`).

2. **DOP / MPM / sim frontier scope.** The dynamics/simulation frontier now carries a dedicated
   §4 analyst section, but that section documents an **untouched state** — no intentional probe,
   no H22 artifact beyond byproduct wiring rows, and (for MPM) zero SYNAPSE code. It is the single
   largest ungrounded domain, and the analyst's own P1 is this ruling.
   - **Option A (analyst recommendation):** formally out-of-scope — SYNAPSE's differentiator is
     COPs / Solaris-USD / Karma receipts, and sim is a different mountain; mark it a documented
     non-goal so byproduct `Dop/*` + `Sop/mpmsolver` catalog rows stop reading as partial coverage.
   - **Option B:** admit it as an in-scope frontier → queue a doc-scout pass over
     DOP/Bullet/Vellum/Pyro/MPM plus a first intentional live probe of the SOP-level solver set.

3. **Copernicus expansion naming (blocks C.10).** From `docs/SYNAPSE_COPERNICUS_EXPANSION.md`:
   OD-A (does the tool manifest go 115 → 118 as the 3 new C.3/C.10 tools land?) and OD-C (the
   terrain verb name). Naming call owed before C.10 merges.

4. **OpenPBR default-surface posture (VOP/MaterialX, design-not-probe).** Whether
   `mtlxopen_pbr_surface` should join or replace the current default `mtlxstandard_surface`.
   Analyst holds this UNGROUNDED — decide only behind a live wiring probe.

---

## 1. Executive Summary

The H22 transition's energy followed the product's spine and thinned out everywhere adjacent to
it. The deep work landed exactly where SYNAPSE's differentiator lives — **render/perception**
(the RETINA T0 receipt shipped as v5.28.0), **Copernicus/COPs** (the single most deeply probed
context: a full 21/21 tool audit plus two merged, live-reconfirmed fix waves and a live
buffer→numpy catalog), and **Solaris/LOP** (the flagship, three merged-and-code-cited waves:
set-dressing renames, karma-relationship handling, and major-aware wiring). **Panel/UI** and
**Memory/substrate** got their version-truth confirmed live (PySide 6.8.3 / py 3.13.10; the
lossless USD round-trip surviving the 0.26.5 reorg at fidelity 1.0) but not their real
surfaces exercised. The **PDG/TOP** event bridge SYNAPSE actually runs on (the R8 async-cook +
monitor-stream surface) was re-audited on 22.0.368 and holds intact — MODERATE — but every *new*
H22 TOP capability (the ML TOP family, PDG Services / warm-session against the ~2s cook floor) was
scouted from docs only and remains unbuilt. And the base layers the pipeline sits *on* got almost
nothing: **SOP** was
touched by exactly one wiring-only connectivity sweep with cook/parm/VEX behavior never probed;
**CHOP** received only byproduct catalog rows; and the whole **DOP/MPM simulation frontier** was
never touched at all. The honest shape: the transition is deep where the product is, provisional
where the product runs (headless probes with the live bridge mostly down, no H21 baseline to
diff against since H21 is uninstalled), and absent where the product doesn't go yet. That is a
defensible allocation — but only if the map below is read as a debt ledger, not a scoreboard.

---

## 2. The Coverage-Honesty Map

Ordered deepest-first so the gaps are unmissable at the bottom. This table is the spine of the
document.

| Context | Coverage | State (one line) | Top gap |
|---|---|---|---|
| **LOP / Solaris** | DEEP | Flagship win — three cycles merged + code-cited (W.3 set-dressing renames, W.5 karma-relationships, U.1-H22 major-aware wiring), two headless probe sections underneath. | `core/lop_knowledge.py` is still hardcoded to the H21 catalog (no major-aware resolution, no `_22` file) — `graph_validator` silently serves **H21 Solaris CONTEXT truth on an H22 stage**. WIRING went major-aware; CONTEXT did not. |
| **COP / Copernicus** | DEEP | Most deeply probed context — 21/21 tool audit + two merged, live-reconfirmed fix waves (W.1b planes-migration, W.4 solvers) + a live buffer→numpy catalog. | The entire generative frontier (C.4 scaffold, C.3 neural, C.10 terrain) is a **ratified, build-ready paper with zero shipped code**; 10 CHANGED scaffold tools remain silent-no-op placebos; every audit PASS is PROVISIONAL-HEADLESS. |
| **TOP / PDG** | MODERATE | The event bridge SYNAPSE actually runs on (R8 async cook + monitor stream) was `dir()`-audited + behavior-probed on 22.0.368 and holds intact (4/4 event-bridge truths, PROVISIONAL-headless). | The entire *new* H22 TOP capability surface is unbuilt and mostly ungrounded: PDG Services / warm-session (the exact lever against the ~2s cook floor) is symbol-present but behavior is DOC-CLAIM; the ML TOP family node-type names were never live-scanned; even the covered event bridge has no live-bridge reconfirm yet. |
| **VOP / MaterialX** | MODERATE | The 4 handler-emitted mtlx node types cleared headless on 22.0.368; single-source `mtlx_types.py` design paid off (one probe cleared every call site). | `mtlxstandard_volume` is table-absent on 22.0.368 yet still emitted at `render_recipes.py:701` — the `usd-2` fix wave never ran; the destruction recipe fails at `createNode` the moment it's instantiated on H22. |
| **Panel / UI** | MODERATE | Qt/PySide **6.8.3** + font/letter-spacing path VERIFIED-LIVE under H22 hython; a `panel-design-warden` review agent now gates the panel. | Never booted inside a **graphical** Houdini 22.0.368 session (G2). Every "live" claim is offscreen + a planted fake-`hou` stub — no real widget geometry, no GUI QFontDatabase, no composited pixels on H22. |
| **Memory / substrate** | MODERATE *(§4 body owed)* | Lossless USD round-trip survived the 0.26.5 reorg at **fidelity 1.0, VERIFIED-LIVE**. | The probed path is a **caller-less library**; the (deprecated) module an artist actually fires is a different, unprobed path. *[full analyst section_md was truncated in dispatch — see §4.]* |
| **SOP (geometry)** | SHALLOW | Exactly one H22 artifact — a wiring-only connectivity sweep (125 `Sop` types, clean, deterministic); the code path is version-stable HOM nobody re-verified for SOP. | SOP **parameters** on 22.0.368 are entirely unprobed — every `set_parm` and `execute_vex`'s own `parm("class")`/`parm("snippet")` calls sit on H21-era assumptions with no H22 artifact behind them. |
| **CHOP (channels / motion)** | SHALLOW | The only artifact is 11 byproduct nodetype rows in the connectivity catalog (all uninstantiated, container-abstained, byte-identical to H21). No tool, no handler, no intentional probe. | The real CHOP operator space is entirely unprobed on H22; the only substantive CHOP knowledge is a **stale H21-namespaced corpus doc** whose node-type strings were never re-probed on 22.0.368. |
| **DOP / MPM (sim frontier)** | **UNTOUCHED** | Dedicated §4 section documents an untouched state — no intentional probe, no H22 artifact beyond byproduct `Dop/*` + `Sop/mpmsolver` wiring rows; MPM has zero SYNAPSE code surface. | Everything below wiring-label arity. A future doc-scout target carried as honest debt, not hidden. Scope ruling owed (OPEN DECISION #2). |

**Honest untouched count:** across the **9 profiled contexts, exactly one is UNTOUCHED — DOP/MPM**
(dynamics/sim). It now carries a dedicated §4 section, but that section documents an *untouched
state*: no intentional probe, no H22 artifact beyond byproduct `Dop/*` + `Sop/mpmsolver` wiring
rows. Every other context got at least a SHALLOW artifact; **CHOP** sits at
SHALLOW-effectively-ungrounded (byproduct catalog rows only). The sim frontier is the real hole.

---

## 3. Note on the per-context sections

Each section in §4 is the analyst's verbatim dispatch. They carry, per context: what H22
changed (with provenance tier), what SYNAPSE probe-verified, what shipped/fixed, the honest
gaps, the **SYNAPSE interaction blueprint** (the forward contract for how to drive that context
on H22), and a prioritized roadmap. §5 merges every roadmap into one cross-context plan.

---

## 4. Per-Context Sections (verbatim)

### SOP (geometry)

**Coverage this cycle:** SHALLOW — SOP got one artifact, the wiring-only connectivity sweep; the base geometry layer was not where this cycle's energy went (that was Copernicus/COPs, Solaris, and RETINA/render), and no SOP cook/parameter/VEX behavior was probed.

**What H22 changed:** No known SOP behavior change, and none was probed. My own diff of the packaged H21→H22 connectivity catalogs (VERIFIED-ARTIFACT) shows the `Sop` category grew 119→125 entries with **0 removed** and **1 wiring change** — and every mover is either a structural non-goal or a catalog-coverage artifact, not a proven Houdini delta:
- 6 "new" entries: `apex::controlextract::2.0`, `apex::scenemerge`, `rbdmaterialfracture::4.0` (rigging/sim — out of scope), plus `copytopoints`, `copytopoints::2.0`, `camera` — which are **also absent from the H21 catalog** (`grep -c` → 0), so their appearance is the emit-list gaining coverage, NOT evidence they are H22-new (copytopoints/camera are long-standing SOPs — INFERENCE, base-model).
- 1 changed: `Sop/apex::controlextract` (rigging — non-goal).
- Net for the geometry nodes SYNAPSE actually uses (scatter, attribwrangle, merge, copytopoints, object_merge, switch…): **no wiring break detected.**

**What SYNAPSE probe-verified this cycle:**
- **125 `Sop` node types, wiring-only, live on 22.0.368** — input/output labels + min/max inputs + output count, e.g. `Sop/scatter` (2 in), `Sop/attribwrangle` (4 in: "Geometry to Process with Wrangle" + 3 ancillary), `Sop/copytopoints` (2 in). Clean sweep, `probe_errors: []`, deterministic (U.1 pin), `schema: verified_connectivity/v2`. Cite: `harness/notes/verified_connectivity_22.0.368.json` (Sop block lines 2319–4634; provenance block 5109–5117; `houdini_version: 22.0.368`). Generated by `host/introspect_connectivity.py` from `emitted_node_types.json`.
- **Packaged + checksummed as the running-major wiring authority** — `connectivity_22.json` (blake2b-stamped, byte-identical to the sweep), consumed by `wire_by_label`/`load_connectivity_catalog` per live Houdini major. Cite: `python/synapse/core/wiring.py:80-142,166-216`; committed at `2c17149` (U.1-H22 fold, validator half of W.3).
- **Phantom refutation, independently reconfirmed** — `walkonsurface` / `curveanimate` (the memo's invented "new SOP nodes") return **0 hits** in both the 288-type H22 connectivity catalog and the 35,903-symbol H22 table. Cite: `docs/intake/adjudication-sidefx-h22-memo.md` §(a) rows 4–5 + §(e); my own `grep -c` on `connectivity_22.json` and `verified_connectivity_22.0.368.json` → 0.

**What SYNAPSE shipped/fixed:** Nothing SOP-specific this cycle. The only SOP-touching deliverables are infrastructure that happens to cover SOP as one of many categories: the drop-week §9 connectivity sweep (`438c628`) and the U.1-H22 major-aware catalog fold (`2c17149`). No SOP handler code changed — `handlers_node.py` and `handlers.py::_handle_execute_vex` carry their pre-H22 dates (Jun 26 / Jul 10) and were not modified for H22 SOP behavior.

**The honest gaps — ungrounded or untouched:**
- **SOP parameters on 22.0.368 = UNPROBED.** The sweep is wiring-only. Every `set_parm` on a SOP, and `execute_vex`'s own `parm("class")` / `parm("snippet")` / `parm("snippet").set(...)` calls (`handlers.py:1216,1223`), assume H21-era parm names/menu values are unchanged. No H22 artifact backs that.
- **VEX-in-SOP semantics = UNGROUNDED (base-model only).** `_handle_execute_vex` (`handlers.py:1173-1302`) maps `run_over` → `class` menu value `{detail:0, points:1, vertices:2, primitives:3}` and cooks an `attribwrangle`. That mapping and the wrangle cook were **not** re-verified on 22.0.368 this cycle — trusted as version-stable, not probed. (Py 3.13/USD 0.26.5 changes don't obviously touch VEX, but "obviously" is inference, not a probe.)
- **The catalog is the emit-list subset, not a SOP census.** "0 SOP types removed in H22" is true only *within `emitted_node_types.json`*. No exhaustive dump of the whole `Sop` category exists for either major, so a real "which SOP nodes were added/removed in H22" question is unanswered.
- **`connect_nodes` bypasses the probe-truth catalog.** `_handle_connect_nodes` (`handlers_node.py:141-171`) wires by **raw `target_input` index** via `setInput`, not through `wire_by_label`. So the verified 22.0.368 SOP input labels only protect planner/recipe-emitted wiring (`routing/planner.py`, `routing/recipes/fx_recipes.py`); a direct `houdini_connect_nodes` call inherits **no** catalog guard against an index miswire.
- **create/delete/connect handlers were not re-probed for SOP on H22** — they're generic HOM (`createNode`, `setInput`, `destroy`), category-agnostic, presumed stable. Correct presumption almost certainly, but it is a presumption.

**SYNAPSE interaction blueprint for SOP on H22 (the forward contract):**
- **Create SOP nodes** with `houdini_create_node` (`parent=/obj/<geo>`, `type=scatter|attribwrangle|copytopoints|merge|…`). Generic HOM, safe on H22; the only special-case in the handler is `materiallibrary` auto-populate, which is a LOP and never fires for SOP.
- **Geometry attribute work** goes through `houdini_execute_vex` (`snippet` + `run_over`). It builds an `attribwrangle` in `/obj`, lints the snippet pre-cook, cooks, and returns a pattern-based VEX diagnosis on failure. Trust it — but if it ever returns a parm-not-found error, that's the unprobed-parm risk surfacing, not a snippet bug.
- **Wire by intent, not by memory.** Prefer `wire_by_label(node, "<Input Label>", src)` (backed by `connectivity_22.json`) over raw indices — the whole module exists because SOP input *indices* drift (the vellumsolver/rbdbulletsolver miswire class). It fails loud (`WiringError`) on an unknown type/label rather than guessing. For a direct `houdini_connect_nodes`, the `target_input` index is **not** catalog-checked — cross-check it against the sweep's `input_labels` for that type before wiring anything multi-input.
- **Lean on the 125-type H22 wiring catalog** for input/output labels + arity; treat it as ground truth for SOP wiring. Do **not** lean on it for parms, cook behavior, or "does this node exist at all beyond the emit list."
- **Traps:** (1) `walkonsurface`/`curveanimate` are PHANTOMS — never emit. (2) The catalog carries `apex::`, `kinefx::`, `musclesolver*`, `tissuesolver*`, `vellum*` SOP types — these are **structural non-goals (rigging/sim)**; visible ≠ buildable-on. (3) scout-gate (`synapse_scout`) any unfamiliar SOP node type or VEX function before emitting — the sweep proves wiring, not existence-in-runtime for symbols outside the emit list.
- **Recipe:** OBSERVE (`houdini_scene_info` / `houdini_network_explain`) → `create_node` → `wire_by_label` off `connectivity_22.json` → `execute_vex` for attributes → verify the cook came through clean.

**Roadmap (prioritized):**
- **P1 — Probe SOP parameters on 22.0.368** for the core geometry set SYNAPSE actually drives (attribwrangle, scatter, copytopoints, merge, object_merge, switch, group, blast, etc.): parm names, defaults, menu-item values. This closes the single largest SOP gap — every `set_parm` and `execute_vex`'s `class`/`snippet` parms are currently H21-assumed. Small, mechanical, high-value; mirror `host/introspect_connectivity.py` into a parm-introspection artifact.
- **P2 — Re-probe VEX-in-SOP live on 22.0.368:** confirm the `run_over`→`class` menu mapping (0–3) and a smoke `attribwrangle` cook, then attach `_handle_execute_vex`'s mapping to that probe artifact instead of leaving it as a hardcoded assumption.
- **P3 — Close the `connect_nodes` seam:** route the direct connect handler through the connectivity catalog (or at minimum arity-validate `target_input` against the probed `input_labels`) so hand-wired SOP connections inherit the same probe-truth guard the planner/recipes already have; and, only if a real question demands it, add an exhaustive `Sop`-category census beyond the emit list so "what changed in H22" can be answered category-wide rather than emit-list-wide.

---

### LOP/Solaris

**Coverage this cycle:** DEEP — three cycles merged with code landed and cited (W.3 set-dressing renames, W.5 karma-relationships, U.1-H22 major-aware wiring), backed by two headless probe sections (N-5, N-3); the one untouched limb is the CONTEXT-truth catalog.

**What H22 changed** (VERIFIED-ARTIFACT, headless-probed on 22.0.368; PROVISIONAL-headless per the probe doc's own stamp — no H21 baseline exists to diff against, H21 uninstalled):
- **Layout LOP → `Lop/paintinstances`** ("Paint Instances"). Verbatim rename from `$HFS/houdini/help/news.zip` → `22/solaris.txt` L137; `opalias Lop paintinstances layout` shipped; 41/42 parms survive, sole drop `method`. Live create+cook succeeded as `Lop/paintinstances`. (`docs/reviews/h22-now-probes-2026-07-16.md` §N-5)
- **Instancer LOP → `Lop/copytopoints`** ("Copy to Points"). whats-new L143; `opalias`+`oprename` shipped; 39/41 parms (dropped `allowmissingprototypes`, `protooptionsgroup`). (§N-5)
- **New H22 instancing complements** (renames aside): `scatterinstances` (render-time Hydra procedural, 167 parms, `#since 22.0`), `pointinstancer` (new create+edit), `retimeinstances` (aliased from `instanceretime`). (§N-5)
- **Karma/husk render properties are USD relationships, not attributes** on 10 names: `camera`, `products`, `orderedVars`, `husk:orderedImageFilters`, `light:filters`, the four `collection:lightLink/shadowLink:includes/excludes`, `collection:filterLink:*`, `proxyPrim`. Counter-finding that scopes it tight: **zero `karma:*` properties are relationships** — all 113 `karma:global/object:*` are plain attributes. (§N-3). Caveat carried verbatim from the probe: "camera/products/light:filters have been USD relationships upstream for multiple releases — the real story is handlers_usd.py never handled relationships at all, not that H22 moved anything."
- **Incidental LOP trap:** `karmarendersettings`/`camera` LOPs author prims named after the NODE (`/Render/probe_krs`, `/cameras/probe_cam`) — H21-era hardcoded `/Render/rendersettings` + `/cameras/camera1` defaults miss. (§N-2/N-7 husk session, "traps caught incidentally")

**What SYNAPSE probe-verified this cycle:**
- N-5 layout/instancer successor adjudication — 7 probe scripts, RENAME (not removal) confirmed, the false `verified_connectivity_H22.json` note ("createNode('layout') will fail on H22") REFUTED. Artifact: `docs/reviews/h22-now-probes-2026-07-16.md` §N-5 + scratchpad `n5_lop_catalog_22.0.368.json` (218-type LOP dump).
- N-3 karma relationship set — 4/4 probes, `light:filters` assignment live-verified (`GetRelationship` targets `['/blocker']` while `GetAttribute('light:filters').IsValid()` is False). Artifact: §N-3.
- Connectivity catalog re-probed and committed as `connectivity_22.json` (288 types, 269 instantiated, blake2b-stamped, determinism-pinned) — carries `Lop/paintinstances`, `Lop/copytopoints`, `Lop/pointinstancer` with input labels. Provenance: `harness/notes/verified_connectivity_H22.json` (interpreter = `hython.exe`, **headless**).

**What SYNAPSE shipped/fixed** (merged to master this cycle):
- **W.3-H22-setdressing (SB-5)** — commit `b5570f8` (merged/verified `2367f75`). Canonical H22 spellings emitted, never the `opalias`. `python/synapse/server/solaris_graph_templates.py:401-405` (`instanceable_assets` emits `paintinstances`, docstring 368-372 cites N-5); `python/synapse/server/handlers_solaris_assemble.py:53,58,76` (`_SOLARIS_NODE_ORDER` gains `pointinstancer`:300, `copytopoints`:310, `paintinstances`:650 with whats-new L137/L143 rename comments).
- **W.5-H22-karmarels (SB-4)** — commit `dab186d` (pre-usd-1 `ebca369`), live round-trip verified per merge note `97c6f25`. Relationship fallback in `python/synapse/server/handlers_usd.py`: read path `GetRelationship`→`GetTargets()` at lines 385-395 (was: RAISED ValueError on all 10 names); write path `SetTargets`/conservative `CreateRelationship` at lines 452-460 (was: `if attr:` silent no-op); hint now lists relationships too (401-405).
- **U.1-H22 fold (SB-2, validator half of W.3)** — commit `9b36b4d` (scaffold `2c17149`, data probe `28fe892`). Major-aware wiring resolution in `python/synapse/core/wiring.py`: `_running_houdini_major()` (66-77), `_pkg_catalog_path()` resolves `connectivity_<major>.json` for the running major (80-89), **fail-loud, never a silent cross-major fallback** (119-127). Per MEMORY v7 / release v5.26.0 (`32dd597`, "H22 live-verified") the wiring-fold code path was live-reconfirmed among 32 VERIFIED-LIVE verdicts (`ab4ac7a`) — I did not re-read that live artifact this pass, so I hold the underlying probe DATA at VERIFIED-ARTIFACT (headless) and the CODE PATH at live-verified-per-release.

**The honest gaps — ungrounded or untouched:**
- **U.5-H22 CONTEXT twin — UNTOUCHED, and it fails quietly.** `python/synapse/core/lop_knowledge.py:25-26` hardcodes `_PKG` to `lop_solaris_knowledge_21.json` with **no** `_running_houdini_major()` resolution — the exact major-awareness its sibling `wiring.py` got this cycle. Only the `_21.json` file exists (no `_22`). Because the loader is non-strict and the H21 file is present, `graph_validator.py:61` (`_lop_ordering_check` / `_phase5_context`, invoked at line 77) silently validates an **H22 stage against H21 Solaris role/USD-type/ordering truth**. Worse, that H21 catalog is corpus-authored and itself stale — it lists `rectlight`/`spherelight`/`disklight`/`cylinderlight` as distinct entries, which the assemble handler's own FIX 1 comment (`handlers_solaris_assemble.py:62-67`) says are phantom on H21.0.671. So the CONTEXT catalog neither knows the H22 renames nor is fully H21-true.
- **New H22 instancing complements catalogued but not wired.** `scatterinstances`, `mergepointinstancers`, `splitpointinstancers`, `extractinstances`, `modifypointinstances`, `retimeinstances` — zero matches in `handlers_solaris_assemble.py`. They exist in `connectivity_22.json` (so `wire_by_label` can resolve their inputs) but are absent from `_SOLARIS_NODE_ORDER`, so `_get_sort_key` drops each to the 800 default (`handlers_solaris_assemble.py:124`) — an instancer would sort into the render tier if auto-assembled. Only `paintinstances`/`copytopoints`/`pointinstancer` are placed correctly.
- **Everything under N-5/N-3 is PROVISIONAL-headless.** The bridge was DOWN for the whole 2026-07-16 probe session (`h22-now-probes-2026-07-16.md` provenance table); every PASS carries that stamp. `connectivity_22.json` data came from `hython.exe`, not the live served process.
- **No H21 baseline anywhere.** H21 uninstalled, perception window permanently closed — every "H22 changed X" for this context is ground-truth H22 shape, not a verified diff (§N-3 caveat, verbatim).
- **The husk-authored stage-default trap is flagged, not hardened.** LOP render/camera nodes naming prims after the node (`/Render/probe_krs`) is logged as "should be re-checked live before any panel/handler code relies on prim paths" — no code guard landed.
- **W.5 write path is deliberately conservative:** a scalar set on an unknown relationship name still no-ops (only a list-of-`/`-prefixed-paths triggers `CreateRelationship`). Correct-by-design, but a single bare-string filter target set won't author. (`handlers_usd.py:457-460`)
- **N-1, N-4 deferred, never run** (require the live WS bridge) — scope unstated in the probe doc; do not assume they are LOP/Solaris-clear.

**SYNAPSE interaction blueprint for this context on H22:**
- **Emit canonical H22 spellings, never the `opalias`.** Use `paintinstances` (not `layout`), `copytopoints` (not `instancer`), `pointinstancer`, `scatterinstances`. Never `node.type().name() == 'layout'`/`'instancer'` type-checks and never author the dropped parms (`method`, `allowmissingprototypes`, `protooptionsgroup`) — the alias makes creation silently succeed but type lookup (`hou.nodeType(lopCat,'layout')` → `None`) and old-name checks break (§N-5 gate-2 correction).
- **Wire by label, not index.** `core/wiring.py:wire_by_label(node, "Input Stage", src)` auto-resolves against `connectivity_22.json` for the running major; a missing per-major catalog fails loud (that IS the safety). Do not hand-guess LOP input indices.
- **Read/write karma & light-filter relationships through the normal attribute tools now.** `houdini_get_usd_attribute` / `houdini_set_usd_attribute` fall through to `GetRelationship`/`SetTargets` for `light:filters`, `camera`, `products`, `orderedVars`, `husk:orderedImageFilters`, `collection:*:includes/excludes`, `proxyPrim`. Pass relationship targets as a **list of `/`-prefixed prim paths** so the write path authors instead of no-opping. Do NOT try to set these as `karma:*` attributes — the `karma:*` surface is all plain attributes; only the 10 stock UsdRender/UsdLux/husk names are relationships.
- **Do NOT trust `lop_knowledge` ordering/role truth for H22 instancers or new set-dressing nodes** until the U.5-H22 re-probe lands. For auto-assembly, only `paintinstances`/`copytopoints`/`pointinstancer` are canonically placed; anything else in the instancing family sorts to the render tier.
- **Render output authoring unchanged:** `productName` still does not author the prim on 22.0.368 (BL-007 holds, §N-8 PIN B) — keep the direct-schema `_PRODUCT_NAME_CODE` path; `usdrender_rop.outputimage` default is empty so the synthesized `{base}.$F{pad}.exr` path is still required (§N-8 PIN A). Expect LOP-authored prim paths named after the node, not `/Render/rendersettings`.
- **Trust posture:** treat connectivity/wiring code paths as live-verified (v5.26.0); treat the N-5/N-3 probe DATA and the OCIO/pixel-filter corpus facts as headless-provisional until a live-bridge reconfirm re-stamps them.

**Roadmap (prioritized):**
- **P1 — Close the U.5-H22 twin gap.** Give `core/lop_knowledge.py` the same `_running_houdini_major()` / `_pkg_catalog_path()` resolution `wiring.py` has, then re-probe Solaris CONTEXT truth on 22.0.368 and commit `lop_solaris_knowledge_22.json` (roles, USD types, key parms, ordering rules, `known_absent`) — including the renamed instancers and dropping the stale per-shape light entries. This is the single load-bearing untouched item; today `graph_validator` runs H21 context against H22 stages.
- **P2 — Live-bridge reconfirm of N-5/N-3 and the stage-default trap.** Re-run the layout/instancer create+cook and the `light:filters` relationship round-trip through the live WS bridge to lift the PROVISIONAL-headless stamp, and decide whether to code-guard the node-named-prim-path trap (`/Render/<node>` vs `/Render/rendersettings`). Run N-1/N-4 here too.
- **P3 — Extend the canonical assemble order to the new H22 instancing family.** Add `scatterinstances`, `mergepointinstancers`, `splitpointinstancers`, `extractinstances`, `modifypointinstances`, `retimeinstances` to `_SOLARIS_NODE_ORDER` at their correct tiers (instancing ~300s), and consider a `scatterinstances`-based template in `solaris_graph_templates.py` for render-time generative scatter.

---

### COP / Copernicus

**Coverage this cycle:** DEEP — the read/analysis/node-API/solver layer is the single most deeply covered H22 context (a full 21/21 tool audit on 22.0.368, two merged-and-live-reconfirmed fix waves, and a live buffer catalog), *but* the generative frontier (neural/scaffold/terrain) is spec'd-only and remains zero-code UNBUILT — so "DEEP" describes the existing tool surface, not the expansion.

**What H22 changed:** (VERIFIED-LIVE / VERIFIED-ARTIFACT)
- **`hou.CopNode.planes` REMOVED** — the entire H21 read quartet (`planes()`/`xRes()`/`yRes()`/`depth()`) is gone from the Copernicus node class; `hou.Cop2Node.planes` survives and is live-callable (`['C','A']`). Three shipping tools (`read_layer_info`, `composite_aovs`, `analyze_render`) read through it → silent-degrade-to-`planes:[]` class break under H22. (`docs/reviews/h22-cop-audit-verification.md:37,124`; `docs/reviews/h22-doc-intel-2026-07-16-wave2.md:209-211`)
- **Replacement read surface exists and is verified:** `node.cable()` → `hou.CopCable` (`wireNames()` = the plane-name equivalent, `wireCount()`, `layerByIndex(0)`) → `hou.ImageLayer` (`bufferResolution()`, `storageType()`). All present + live-callable. (`docs/reviews/h22-live-reconfirm-2026-07-16.md:21-22`)
- **Solver-block parm drift:** Cop `block_end` LOST `method`/`blocktype`/`blockpath` — only `iterations` + `simulate` survive; `blockpath` MOVED to `block_begin`, so implicit end→begin binding is REFUTED-LIVE. (audit rows #11/#13/#14/#17; `docs/SYNAPSE_COPERNICUS_EXPANSION.md:54`)
- **`levels`/`steps` renamed, not gone:** Cop `quantize` now uses `method='segments'` + `segments` Int; Cop2 uses `step` Float. (Expansion §Leg A, `:57`)
- **Legacy-COP2-removal contingency did NOT fire:** `cop2net`/`vopcop2gen`/`copnet` all resolve and instantiate on 22.0.368 — both `Cop` and `Cop2` categories coexist. (audit headline 1, `:36`)
- **SOPs→COPs heightfield migration is live** on the Cop surface: 18 `heightfield_*`/`height*` types + `oceanspectrum`/`oceanevaluate` + camera family, 384 Cop types total. No audited tool emits a migrated type directly. (audit `:80-89`; Expansion §Leg C, `:75-76`)

**What SYNAPSE probe-verified this cycle:**
- **21/21 COP tools adjudicated on 22.0.368** → PASS 11 / CHANGED 10 / GONE 0, quarantine 0. Per-tool verdicts with verbatim probe evidence. (`docs/reviews/h22-cop-audit-verification.md:44-72`) — **PROVISIONAL-HEADLESS** (hython, bridge down).
- **The W.1b planes-migration replacement surface, live-reconfirmed:** `CopCable.wireNames()`→`['ramp']`, `.wireCount()`→`1`, `layerByIndex(0)`→`ImageLayer`; the loud-`api_drift` behavior fires end-to-end (proxy AttributeError → structured drift entry, healthy node carries no `api_drift` key). (`docs/reviews/h22-live-reconfirm-2026-07-16.md:21-27`, VERIFIED-LIVE)
- **W.4 solver truth, live-verified:** `method`/`blocktype` removal, `simulate` survival, `blockpath` moved to `block_begin`, explicit binding required. (Expansion `:54`; code `handlers_cops.py:1076-1135`)
- **Copernicus buffer→numpy readback, engine-real headless:** `copnet` generator → `cook(force=True)` → `layer()`→`hou.ImageLayer`; `bufferResolution()`→(1024,1024), `storageType()`→`Float32`, `allBufferElements()`→exact `w*h*ch*4` bytes, `np.frombuffer` roundtrip exact, **buffer row 0 == image BOTTOM (bottom-left origin; flip for OIIO top-down)**. (`harness/notes/perception_truth_22.0.368.json` item 4, verdict VERIFIED-LIVE; transport = headless hython, engine-real cook)
- **Expansion probe legs (live WS bridge, V1-LIVE type-level):** `bakegeometrytextures::2.0` full parm surface (resolution lives on the `copnet` container `setres`/`res`, not node-level `resx/resy`); native `reactiondiffusion_block_begin/_end` pair (feed/kill/model on the *end* node, blockpath on *begin*); `usdmaterial`/`slapcompimport` registered but input-driven (zero type-level parms); SAM2/MoGe-2/`denoiseai` node types present; `hou.opencl.devices(device_type)` (required positional). (`docs/SYNAPSE_COPERNICUS_EXPANSION.md:49-80`)
- **Phantom quarantines:** whitepaper `top::gaussian_splat_train` (+4 spellings) CONFIRMED PHANTOM — real trainer is `ml_traingsplats`; only public image-header reader on 22.0.368 is `hou.imageResolution` (plane names private-only `_imagePlanes`, depth enum-only). (`docs/reviews/h22-cop-audit-verification.md:185-218`)

**What SYNAPSE shipped/fixed:**
- **W.1 / W.1b — planes migration + loud-drift instinct: MERGED.** New replacement read surface `_copernicus_image_info` (`handlers_cops.py:239-290`) + LOUD `api_drift` machinery (`_warn_cop_drift_once:41`, `_cop_drift_issue:54`, `_read_or_drift:212`) — an AttributeError on any replacement symbol is now warn-once + a structured `api_drift` entry, because the silently-empty read is exactly what masked the original break (W.1 crucible sev-3). Merged `cd3983f` (Pass-3, suite 4358/0/92); repair commits `9db6306`, `c590629`. Live-reconfirmed VERIFIED-LIVE.
- **W.4 — solver blocks (SB-3): MERGED.** `_handle_cops_create_solver` (`:1066`) now drives `simulate` toggle instead of removed `method`/`blocktype`, and applies explicit `block_begin.blockpath` binding via `_bind_solver_block` (`:117`, used `:1135` and `:1304`); `_set_quantize_levels` (`:147`) authors the `method='segments'`+`segments` rename. Merged `34f41f7`, chore `59ca1fb` (suite 4387/0/97). W.4b follow-ups deposited unratified.
- **RETINA.M1 — Copernicus buffer→numpy perception catalog: MERGED** (`f9032e4`), shipped in T0 `v5.28.0` (`72de5f1`). This is catalog/perception truth feeding RETINA T1, **not** a new `cops_*` handler.
- **Copernicus Expansion spec: COMMITTED as paper only** (`09d265a`, `docs/SYNAPSE_COPERNICUS_EXPANSION.md`) — RATIFIED SCOPE, BUILD-READY, but **nothing built**.

**The honest gaps — ungrounded or untouched:**
- **The generative/neural/terrain frontier is SPEC'D but UNBUILT — zero code.** Confirmed absent from the codebase: `_handle_cops_segment_mask`, `_handle_cops_estimate_depth`, `_handle_cops_terrain_setup`, `_neural_model_status`, `register_cop_recipes`. Tool count is still `115` (CLAUDE.md banner) — the +3 from C.3/C.10 has not landed. C.4/C.3/C.10 are `ratified:true` in the queue with a full build paper, awaiting per-cycle human-merged builds in order C.4→C.3→C.10.
- **The 10 CHANGED scaffold tools remain silent-no-op placebos on the modern Cop surface.** `cops_procedural_texture` (#12), `cops_bake_textures` (#18), `cops_stamp_scatter` (#20) still emit `vopcop2gen` (Cop2-only) with every parm (`type/freq/octaves/resx/resy`, `seed/copies/count`) resolving False → silently never set; `cops_stylize` (#16) carries dead per-style fallback chains. These are audit-CHANGED, NOT fixed this cycle. (`handlers_cops.py:1164/1841/2011/1595`)
- **Every COP-audit PASS is PROVISIONAL-HEADLESS.** Probed via hython with the bridge DOWN; behavioral items (cook output, `op:<path>/<plane>` suffix resolution on Copernicus, implicit solver binding) are PENDING-BEHAVIORAL, explicitly not verified. The W.1b read surface and W.4 solver blocks *were* separately live-reconfirmed — but the 10 CHANGED scaffold verdicts were not.
- **No H21 COP parm baseline was ever captured** (H21 uninstalled on drop day). "CHANGED" = *H22 truth vs what the code emits*, not a proven H21→H22 delta — some no-ops may have been no-ops on H21 too. (audit `:48`)
- **OWED probes P-1 / P-2 block real emission.** All three expansion legs hit SCENE_BUSY, so instance-level truth is ungrounded: SAM2/MoGe-2 provider menu items, `usdmaterial` dynamic parms, `fractalnoise` `noisetype`/`fractaltype` menu tokens, live `inputLabels` for maskbyfeature/visualize/fractalnoise/geotolayer, **every cook verdict** (bake, bound RD pair, neural empty-vs-real mask, geo↔layer round-trip), and **a modern Cop stamp/scatter target (never probed at all — P-2).** (`docs/SYNAPSE_COPERNICUS_EXPANSION.md:82-86,258-264`)
- **SAM2/MoGe-2 ONNX models are ABSENT on this machine** — Download Models never run under `$SHFS` (Program Files, likely needs elevation). C.3's only testable path today is the model-absent honest-refusal envelope; the models-present cook path is unarmed. (`:67,256`)
- **Buffer→numpy is a catalog fact, not a shipping tool.** The RETINA readback proves the mechanism live but is wired into RETINA's perception tier, not any `cops_*` handler — `read_layer_info`/`analyze_render` read metadata via the `CopCable` path, not the numpy buffer.
- **RIGGING boundary (non-goal, context only):** the H22 ML TOP family (`ml_traingsplats`, gaussian-splat train→ONNX→COP-inference) and KineFX/APEX movement are noted as vendor surface — never a SYNAPSE COP target this cycle.

**SYNAPSE interaction blueprint for this context on H22:**
- **Read COP output through the migrated surface, never `node.planes()`.** For Copernicus (`hou.CopNode`) nodes use `cops_read_layer_info` / `cops_analyze_render` — they now route through `_copernicus_image_info` (`cable()`→`CopCable.wireNames/layerByIndex`→`ImageLayer.bufferResolution/storageType`). For legacy `Cop2Node`, `planes()`/`xRes()` still work. Trust the `api_drift` key: if it appears in a response, a replacement symbol vanished on this build — that is a loud signal, not noise; `planes:[]` with no `api_drift` key means a genuinely empty/uncooked node.
- **Solver blocks: pass `method='simulate'` to drive the `simulate` toggle** (never expect `method`/`blocktype` parms); binding is explicit via `block_begin.blockpath` — the handler already does this. Don't author `block_end.blockpath` (moved off).
- **Resolution is container-level.** Author `copnet.setres`/`res`, never node-level `resx/resy` on Cop nodes (they don't exist there).
- **The four scaffold tools are placebos on the Cop surface today.** If you call `cops_procedural_texture`/`bake_textures`/`stamp_scatter`/`stylize` expecting parameters to take effect on a `copnet`, they silently won't. Prefer `cops_create_node` + explicit parm sets against **probe-verified names** until C.4 lands. In a `copnet`, `vopcop2gen`/`noise` raise `OperationFailed` — the legacy fallbacks are dead code.
- **For raw pixel access, the buffer→numpy path is live:** cook the generator, `layer()`→`ImageLayer`, `allBufferElements()`→`np.frombuffer(...,float32).reshape(h,w,ch)`, and **flip vertically** (buffer is bottom-up / bottom-left origin).
- **Before emitting any COP node-type string or parm name, phantom-guard it** against the committed h22 symbol table (`synapse_scout`) — `phantom_clean` covers `hou.*` but NOT node-type/parm strings, so migrated heightfield types and neural nodes need explicit probe backing.
- **Traps:** don't emit `top::gaussian_splat_train` (phantom → `ml_traingsplats`); don't call `hou.imageDepth(path)` or `hou.imageInfo`/`imageHeader` (enum / absent); `shfs:` does NOT expand via `hou.text.expandString` (map to `$SHFS` + `os.path`).

**Roadmap (prioritized):**
- **P1 — Discharge P-1 (quiet-scene cook + instance probe) on the live bridge.** It is the single gate blocking C.4, C.10, *and* the audit's PENDING-BEHAVIORAL cook verdicts. Requires `/obj` clear of `_recon_*`/`_w4assay_*` debris (SCOUTMASTER call on `/obj/_recon_planes2`). Also reconfirm the 10 CHANGED verdicts on the live bridge to lift PROVISIONAL-HEADLESS.
- **P1 — Build C.4 (scaffold rebuild, build order FIRST):** re-author `procedural_texture`→`fractalnoise`, `bake_textures`→`bakegeometrytextures::2.0`, stylize residue cleanup, honest applied-verdict envelopes; kills the silent-no-op class. Zero external deps. Human-merge per cycle. (OD-B: whether native RD pair rides; OD-D: subsume W.4b(3).)
- **P2 — Build C.3 (neural COPs, SECOND):** `cops_segment_mask`/`cops_estimate_depth` + `synapse_doctor` model/GPU preflight, same commit. Testable today only via the model-absent honest-refusal envelope; run Download Models (GUI, elevated) in parallel to arm the cook test + P-1(e).
- **P2 — Run P-2 (stamp/scatter modern-target enumeration)** — never probed; D4.3 cannot build without it.
- **P3 — Build C.10 (terrain exposure, THIRD):** `cops_terrain_setup` + recipe + catalog extension (needs P-1(c) label capture). Resolve OD-A (manifest absorbing 3 new tools → 118) and OD-C (verb name).
- **P3 — Fix the corpus divergence:** `rag/skills/houdini21-reference/copernicus_python_api.md:315` still teaches `planes()`; must be seeded with the migrated read model or scout re-teaches the break.

---

### TOP/PDG

**Coverage this cycle:** MODERATE — the event-bridge surface SYNAPSE actually depends on (R8 async cook + monitor stream) was `dir()`-audited and behavior-probed on 22.0.368 and holds intact; the entire *new* H22 TOP capability surface (ML TOPs, PDG Services, rich per-item telemetry) was scouted from docs only and remains unbuilt.

**What H22 changed:** (all VERIFIED-LIVE via hython on `22.0.368` / py `3.13.10`, `docs/reviews/h22-pdg-perception-reaudit.md` — but PROVISIONAL: probed through the hython fallback, bridge was down)
- `pdg.Scheduler`: **2 real method removals** — `onWorkItemFileResult`, `onWorkItemSetAttribute` (102→101 members). Repo-wide grep = **0 hits**, nothing in SYNAPSE breaks (re-audit "Counts" + dir-diff table).
- `pdg.WorkItem`: **+4** methods (`geometryAttribValue`, `setGeometryAttrib`, `scriptDir`, `workingDir`), 0 removed.
- `pdg` module: `+curPlatform`, `+serviceSchedulerType`; `-ServiceClientLogType` (capitalized dup; lowercase survives). `pdg.GraphContext +schedulerForTypeName`; `pdg.SchedulerType +isPrivate`.
- `pdg.EventType`: **all 53 H21 member values byte-identical** (`All`=43, `CookComplete`=14, `CookError`=12); resolution map identical to H21.
- New capability surface (ML TOP family, PDG Services) is doc-described only — **node-type names UNVERIFIED**, no live `nodeTypeCategories()` scan run.

**What SYNAPSE probe-verified this cycle:**
- **4/4 H21 event-bridge behavioral truths hold on H22** (`h22-pdg-perception-reaudit.md`, drop-week Step 8): (1) `pdg.PyEventHandler(fn)` still has **no constructor** (`TypeError: No constructor defined`, incl. subclass trampoline); (2) raw-callable `gc.addEventHandler(cb, EventType)` is the working form and returns the `PyEventHandler` wrapper for `removeEventHandler`; (3) events fire on a **worker thread** (`is_main_seen:[false]`, threads `Dummy-2..11`); (4) `event.workItemId` exists, `event.workItem` does not — 9-attr `dir(event)` byte-identical to H21.
- **16 surfaces probed: 10 resolved / 6 phantom, resolution map IDENTICAL to H21**; phantoms still phantom: `hou.pdg`, `hou.pdg.scheduler`, `hou.pdg.workItem`, `hou.pdg.GraphContext`, `pdg.PyEventCallback`, `hou.pdgEventType` (re-audit "Phantoms still phantom").
- **Static-generator cook gotcha survives:** a static `genericgenerator` fires NO `WorkItemStateChange`/`CookedSuccess` — completion signals via `NodeCooked` + `CookComplete` only (re-audit "Cook-semantics note").
- **Symbol-level negative confirmation (VERIFIED-ARTIFACT, committed table):** all 6 symbols R8 depends on (`EventType`, `PyEventHandler`, `EventHandler`, `GraphContext`, `CookComplete`, `CookError`) present in the 22.0.368 table (`TOPS-09`); the doc's `pdg.GraphContext.workItemById` is **table-ABSENT — a doc error**; the real symbol is `pdg.Graph.workItemById` (`TOPS-02` PHANTOM catch, `h22-doc-intel-2026-07-16-wave2.md`).

**What SYNAPSE shipped/fixed:** Nothing code-side. No `handlers_tops/` change, no TOP/PDG port wave merged this cycle. The two deliverables are **review artifacts only**: the perception re-audit (persisted by the drop-week orchestrator, cycle commit `438c628`) and the doc-intel wave-2 report (`docs/reviews/h22-doc-intel-2026-07-16-wave2.md`). The R8 bridge (`shared/bridge.py:1289-1446`) and the two consumers (`diagnostics.py:377-639` monitor stream, `cook.py:134-179` scheduler) are unchanged — the audit's verdict was "re-probe, not rewrite," and only the probe half ran.

**The honest gaps — ungrounded or untouched:**
- **PROVISIONAL, not live:** every "hold on H22" verdict above is headless-hython (bridge unreachable this session). A **live-bridge reconfirm is still owed** to promote the 4 truths from PROVISIONAL → VERIFIED-LIVE. (Memory v7's live-reconfirm covered CTO-01 memory fidelity, not the pdg event bridge.)
- **PDG Services / warm-session (`TOPS-08`) — UNBUILT, behavior UNGROUNDED.** `pdg.ServiceManager` + Service Create/Start/Stop TOPs are the exact lever against the ~2s Houdini cook floor; symbols are table-present (VERIFIED-ARTIFACT) but **behavior is DOC-CLAIM** and `ServiceManager` appears **nowhere in `python/synapse`** (grep confirmed: only in the two symbol-table JSONs). No `tops_manage_service` tool exists.
- **ML TOP family (`TOPS-06`/`TOPS-07`) — UNTOUCHED, node-type names UNGROUNDED.** 10 doc-listed ML nodes (Computer Vision, GSplats, OIDN, Style Transfer, NCA, Regression). Internal names are **never table-verifiable** and were never live-scanned; the `ml_traingsplats`-real-name vs `top::gaussian_splat_train`-phantom distinction is a **doc-scout note, not a probe**. Zero `ml*`/inference tool in the 17 `tops_*` tools. *(New-build greenfield, not breakage; ML-render adjacent, not a rigging target — KineFX/APEX out of scope.)*
- **Rich per-item telemetry (`TOPS-02`/`TOPS-04`/`TOPS-05`) — UNBUILT.** `tops_monitor_stream` is already push-based on `WorkItemStateChange|CookProgress|CookComplete` (`diagnostics.py:604-609`), but per-item percent-complete, output-files-as-they-land, `supportedEventTypes` introspection, and per-work-item (vs context-level) registration are all uncovered; corpus is silent on the node-vs-item registration split.
- **Farm scheduling is structurally out:** `cook.py:152-157` raises loudly on any non-local scheduler — Deadline/Tractor/HQueue submission is deliberately not wired. Not an H22 regression, but it caps everything above (Services would still be localscheduler-only today).
- **Corpus PDG-event prose is empty:** `rag/skills/houdini21-reference` has zero `addEventHandler`/`EventType`/cook-thread text (`TOPS-03`) — scout/knowledge_lookup cannot teach the worker-thread contract to an agent.

**SYNAPSE interaction blueprint for this context on H22:**
- **Lean on R8 as-is.** `shared/bridge.py:1370-1446` is the verified pattern: register a **raw callable** via `graph_context.addEventHandler(fn, pdg.EventType.X)`, keep the returned wrapper, `removeEventHandler(wrapper)` in a `finally`. One `addEventHandler` call per event type.
- **Never** emit `pdg.PyEventHandler(fn)` — no constructor on either major. Never emit the phantoms `hou.pdg.*`, `hou.pdgEventType`, `pdg.PyEventCallback`.
- **Callbacks run on a worker thread.** Only touch thread-safe primitives inside (`threading.Event.set()` is fine); marshal any `hou.*` back to main via `hdefereval`. Never start a new cook / open UI from a handler except from `CookComplete`.
- **Completion detection:** for static generators, wait on `CookComplete` (+ `NodeCooked`), not `WorkItemStateChange` — static items never emit state-change/`CookedSuccess`. Use `event.workItemId` (int, `-1` on non-item events), not `event.workItem`.
- **Per-item lookups use `ctx.graph.workItemById` (`pdg.Graph`)**, never `ctx.workItemById` (`pdg.GraphContext` = table-absent doc error).
- **Scheduler = local only.** Don't offer farm types; `cook.py` rejects them by contract.
- **Node-type names are unverified** — probe `hou.nodeTypeCategories()['Top']` before any `createNode` of an ML/service/gsplat TOP.

**Roadmap (prioritized):**
- **P1 — Live-bridge reconfirm** of the 4 event-bridge truths (promote PROVISIONAL-headless → VERIFIED-LIVE) next time a live bridge is up. Cheapest honest close on the surface SYNAPSE actually runs on; also lets the CLAUDE.md PyEventHandler warning's tag extend to `22.0.368` with confidence.
- **P2 — `tops_manage_service` (TOPS-08 PDG Services / warm-session):** highest-leverage *new* capability, aimed straight at the ~2s cook floor. Gate on a behavior probe of `pdg.ServiceManager` verbs first (symbols already table-verified), then build additively.
- **P2 — Rich telemetry into `tops_monitor_stream` (TOPS-02):** add per-item percent-complete + output-files-as-they-land using `ctx.graph.workItemById`; harden registration with `supportedEventTypes` (TOPS-05).
- **P3 — ML TOP family (TOPS-06/07):** biggest greenfield but new-build not breakage; **must start with a live `nodeTypeCategories()['Top']` scan** to resolve the real `ml_traingsplats` name and kill the `top::gaussian_splat_train` phantom before any tool wiring.
- **P3 — Corpus seed** the PDG worker-thread + node-vs-item registration contract (TOPS-03/TOPS-04), H22-version-tagged, so scout/knowledge_lookup stop being silent here.

---

### CHOP (channels / motion)

**Coverage this cycle:** SHALLOW — the connectivity prober re-read arity for 11 generic node types under the `Chop/` category on live 22.0.368, but abstained on instantiation (no container built), so as a SYNAPSE feature-surface CHOP is effectively UNTOUCHED: no tool, no handler, no recipe, no intentional probe.

**What H22 changed:** No known change / not probed. CHOP arity and the container-abstention are byte-for-byte the same between `verified_connectivity_21.0.671.json` and `verified_connectivity_22.0.368.json` (same 11 `Chop/` keys, all `"instantiated": false`). SYNAPSE has never enumerated the real CHOP operator space on either build, so there is no baseline against which an H22 delta could even be measured.

**What SYNAPSE probe-verified this cycle:**
- Node-type **arity only** (`min_inputs` / `max_inputs` / `output_count`) for 11 emitted-surface types that resolve in the Chop category — `cop2net, dopnet, file, limit, lopnet, merge, noise, null, output, subnet, topnet` — read from the live 22.0.368 nodetype in hython. Cite: `harness/notes/verified_connectivity_22.0.368.json:4-157`. **VERIFIED-ARTIFACT** (arity read on the running build; committed catalog).
- **Container abstention re-confirmed:** every Chop row carries `"note": "no container for this category"` and `"instantiated": false` — the prober never builds a `chopnet`, so no instance-level wiring (`inputLabels`/`outputLabels`) is captured. Cite: `host/introspect_connectivity.py:114` (`_make_container` returns `None` for Chop — *"not needed by the emitted surface"*). **VERIFIED-ARTIFACT.**
- These 11 rows are **byproducts of the emitted recipe surface, not a CHOP probe** — they are generic container/utility names (merge, null, file, subnet, the nested-network stubs), not CHOP operators. **VERIFIED-ARTIFACT** (inspected the row set).

**What SYNAPSE shipped/fixed:** Nothing this cycle. No CHOP-domain code, tool, handler, recipe, or catalog work landed. The connectivity catalog rows are a side effect of the general nodetype/connectivity sweep, not a CHOP deliverable.

**The honest gaps — ungrounded or untouched:**
- **The real CHOP operator space is entirely unprobed on H22.** Wave, constant, noise-as-channel, lag, spring, jiggle, channel/fetch, expression, object, geometry (SOP↔CHOP), audio (audiofilein/audioin), channelwrangle, export/bake — none exist in any H22 artifact. **NULL (honestly absent).**
- **`rag/skills/houdini21-reference/chops.md` is the only substantive CHOP knowledge SYNAPSE holds, and it is stale.** It is explicitly `houdini21-reference`-namespaced; its `CHOP_GENERATORS`/`CHOP_FILTERS` node-type strings (`constant`, `wave`, `channel`, `audiofilein`, …) were verified against H21 corpus at best and **never re-probed on 22.0.368**. Any CHOP node-type string surfaced via `synapse_knowledge_lookup`/`synapse_scout` from this doc is **VERIFIED-ARTIFACT (H21 only) → treat as INFERENCE for H22**, not a live H22 verdict. **The scout `dir()` symbol table only guards `hou.*`/`pdg.*`/`pxr.*` dotted symbols — it does NOT validate CHOP node-type strings, so a phantom/renamed CHOP type would pass silently.**
- **`graph_oracle.py:28` lists `Chop` in `_TYPED_CATEGORIES`** (wires carry data types, alongside Vop/Shop) — a **dormant classification, INFERENCE-tier**: it is a code fact but never exercised, because no CHOP graph is ever constructed through the oracle. The typed-wire behavior for CHOP is unverified end-to-end on any build.
- **No provenance/undo path is defined for CHOP mutations** — there is no CHOP handler, so the "provenance or it didn't happen" contract has simply never been extended to this context. **NULL.**

**SYNAPSE interaction blueprint for this context on H22:**
- **Default stance: don't route CHOP work as if it's supported.** There is no CHOP MCP tool in the ~115-tool surface (the tool families are `houdini_*`, `cops_*`, `tops_*`, `synapse_*` — none channel/motion). Treat a CHOP request as an **unsupported-domain** case, not a routable task.
- **If a CHOP operation is genuinely required, the only path is the generic escape hatch:** `houdini_execute_python` to build a `chopnet` and its children by hand. That path is **ungated on the live `/synapse` transport** (CRITICAL gate exists only on the `/mcp` bridge) and produces **no CHOP-aware provenance** — so it is manual, unaudited-for-CHOP-semantics, and the agent owns correctness.
- **Do NOT trust CHOP node-type strings from the corpus as H22-live.** Before emitting any `createNode("<choptype>")`, verify the type exists on 22.0.368 (e.g. `hou.nodeType(hou.chopNodeTypeCategory(), "<type>")` via `houdini_execute_python`) — the phantom-API guard does not cover CHOP node names. The `chops.md` doc is a **starting hypothesis, not a verdict**.
- **The connectivity catalog will mislead here:** its `Chop/` rows describe generic emitted types with **no wiring data** (`input_labels: null`, `output_labels: null`). Do not read wireability of real CHOP operators from it — that data was never captured.
- **Trap to avoid:** the word "chop" in `fx_recipes.py` (ocean choppiness parameter) and "Chop" in `handlers_hda.py:24` (HDA category-name allowlist) are **not** CHOP-operator surfaces — don't mistake them for a live channel/motion capability.

**Roadmap (prioritized):**
- **P1 — Decide-and-document the non-goal explicitly.** CHOP is channels/motion; its practical use (procedural/secondary motion, camera shake, constraints, mocap, audio-reactive) is **animation-adjacent and outside SYNAPSE's stated differentiator** (COPs / Solaris-USD / Karma receipts). It is *not* rigging (KineFX/APEX is the structural non-goal), but it is close enough to the animation frontier that carrying it would be scope creep. **Recommend: mark CHOP an explicit, documented non-goal** so future cycles stop generating byproduct catalog rows that read as partial coverage.
- **P2 — If the non-goal is ever lifted:** run a single intentional CHOP arity+wiring probe by teaching `host/introspect_connectivity.py:_make_container` to build a `chopnet` container (one line: `return hou.node("/obj").createNode("chopnet", ...)` pattern, mirroring the Dop/Cop cases), which would turn the 11 abstained rows into real instance-level wiring truth and enumerate the actual CHOP operator space on 22.0.368.
- **P3 — Re-namespace or retire `rag/skills/houdini21-reference/chops.md`.** As long as it lives in the corpus unqualified, `scout`/`knowledge_lookup` can surface H21 CHOP node-type strings as if authoritative for H22. Either re-probe it into a `houdini22-reference` doc or tag it clearly stale so retrieval flags it as unverified-on-H22.

---

### VOP / MaterialX — shader graph plumbing

**Coverage this cycle:** MODERATE — the concrete break surface (the node-type names SYNAPSE actually emits) got probe-cleared headless, but nothing was live-reconfirmed, nothing shipped, and the confirmed phantom is still in the tree.

**What H22 changed:**
- MaterialX bumped to **1.39.5** (VERIFIED-ARTIFACT: `MaterialX.getVersionString()` → `'1.39.5'`, `docs/reviews/h22-now-probes-2026-07-16.md:154`). MaterialX rides inside OpenUSD, so this moved with the USD 0.26.5 bump — exactly the silent-breakage surface `mtlx_types.py:1-16` was built to guard.
- MTLX VOP set is now **239** node types (VERIFIED-ARTIFACT: `h22-now-probes-2026-07-16.md:153`). No runtime diff exists — `verified_nodetype_catalog_21.0.671.json` carries 0 mtlx entries (createNode-literal scope), so H21→H22 delta is **unmeasurable**, not measured.
- One SYNAPSE-emitted name went phantom: **`mtlxstandard_volume` is GONE** on 22.0.368 (VERIFIED-ARTIFACT: `in hou.vopNodeTypeCategory().nodeTypes()` → `False`, `h22-now-probes-2026-07-16.md:149`). Nearest survivors: `mtlxvolume`, `mtlxvolumematerial`, `mtlxabsorption_vdf`.
- New families present in the 239-set (OpenPBR `mtlxopen_pbr_surface` + converters, Chiang/deon hair BSDFs, the 1.39 pattern set, `mtlxunifiednoise2d/3d`, `mtlxhextiledimage/normalmap`, `mtlxUsdUVTexture23`, versioned `mtlxnormalmap::2.0`) — their presence is VERIFIED-ARTIFACT (listed in the probe dump), but "new-in-22" is UNGROUNDED (docs hint only, no baseline).

**What SYNAPSE probe-verified this cycle:**
- The **4 handler-emitted node types all resolve** on 22.0.368 — `mtlxstandard_surface`, `mtlximage`, `mtlxgeompropvalue`, `mtlxnormalmap` each `→ True` (VERIFIED-ARTIFACT, **provisional-headless**: `h22-now-probes-2026-07-16.md:142-145`). These are the exact strings every plumbing call site emits (single-sourced from `python/synapse/core/mtlx_types.py:19-24`; consumers verified at `handlers_material.py:511/519/533/598`, `handlers_node.py:82/87`, `solaris_compose_tools.py:251`, `pipeline_recipes.py:840-864`). One probe clears every site — the single-source design paid off.
- `mtlxstandard_volume` phantom pinned to a **single call site**: `render_recipes.py:701` (VERIFIED-ARTIFACT: `h22-now-probes-2026-07-16.md:149`; confirmed live in-tree — the line still reads `f"'{MTLX_STANDARD_VOLUME}', 'dust_shader')"`).
- Versioned `mtlxnormalmap::2.0` coexists with the bare name; bare-name `createNode` resolves per Houdini version preference (VERIFIED-ARTIFACT: `h22-now-probes-2026-07-16.md:145`) — behavior note, not a break.

**What SYNAPSE shipped/fixed:** **Nothing this cycle.** No VOP/MaterialX code changed. `render_recipes.py:701` still emits the `mtlxstandard_volume` phantom verbatim; `mtlx_types.py:25,33` still lists it in `MTLX_TYPES`. The N-6 gate-feed assigned the fix to **wave `usd-2`** (`h22-now-probes-2026-07-16.md:327`; the material handlers live in the `usd-2` wave, `PORT_WAVE_MANIFEST.md:98-99`) — and **usd-2 has not run** (git log shows merged waves scene-1/W.3/W.5/W.7+W.8/W.1b/W.4/U.1; no usd-2). The quarantine is OPEN.

**The honest gaps — ungrounded or untouched:**
- **[P1, live phantom] `mtlxstandard_volume` unfixed.** Table-absent on 22.0.368 but still emitted into generated recipe text at `render_recipes.py:701`. It is *latent* (recipe code is a string an agent/artist runs, not something SYNAPSE executes in-process) — but the instant the destruction recipe is instantiated on H22, `createNode('mtlxstandard_volume', 'dust_shader')` raises. Not fixed, not guarded, not scheduled beyond the un-run usd-2 wave.
- **[provisional] No live-bridge reconfirm of ANY mtlx verdict.** N-6 ran hython-headless with the bridge DOWN (`h22-now-probes-2026-07-16.md:10`). The live-reconfirm session (32 VERIFIED-LIVE verdicts, `docs/reviews/h22-live-reconfirm-2026-07-16.md`) contains **zero** MaterialX content — its "quarantine re-pins" were `hou.secure` + the removed COP quartet + solver binding, not mtlx. So the 4 PASS and the 1 QUARANTINE remain VERIFIED-ARTIFACT / provisional-headless, never VERIFIED-LIVE.
- **[untouched] The new 1.39.5 VOP surface is not wired and not wiring-probed.** SYNAPSE emits none of OpenPBR, hair BSDFs, hex-tiled, glTF, or the pattern set. Whether `mtlxopen_pbr_surface` should become the default surface (vs the current `mtlxstandard_surface`) is UNGROUNDED (base-model design opinion, no probe). The KAR-06 doc-intel "8 new types" names were partly GUESSED (`h22-doc-intel-2026-07-16-wave2.md:280`); N-6 found the real survivors but did not diff or wire them.
- **[latent] `mtlxnormalmap::2.0` version-resolution trap** — bare-name emission is verified to work, but which version it binds to on a given install is unpinned.
- **[boundary, correctly untouched] Shader *authoring* is a stated non-goal** (`mtlx_types.py` framing; SYNAPSE wires the graph — materiallibrary LOP + shader child + image/normalmap/UV nodes — it does not design shader parameter surfaces). Not a gap; a scope line. (Hair BSDFs here are *shading*, not KineFX/APEX rigging — rigging remains a separate structural non-goal and is not implicated.)

**SYNAPSE interaction blueprint for this context on H22:**
- **Use the plumbing tools, they're clear:** `houdini_create_material`, `houdini_create_textured_material`, `houdini_assign_material`, `houdini_read_material` (+ `synapse_solaris_build_graph` / `synapse_solaris_assemble_chain` for the Solaris side). Every one routes its node-type strings through `mtlx_types.py`, and those 4 strings are verified live-resolving on 22.0.368 (headless). Standard texture-material wiring (surface + image-per-map + normalmap between image and shader + geompropvalue for UVs) is safe.
- **Lean on this truth:** the 4 emitted node types exist; MaterialX is 1.39.5; single-source `mtlx_types.py` means one edit fixes every site.
- **Traps to avoid:** (1) Do **not** instantiate the destruction render recipe from `render_recipes.py` on H22 — its `dust_shader` line emits the dead `mtlxstandard_volume`; substitute `mtlxvolume`/`mtlxvolumematerial` and verify by probe first. (2) When emitting normal maps, the bare `mtlxnormalmap` may bind `::2.0` — pin the version if determinism matters. (3) USD/Solaris parm names are punycode (`xn__…`) and majority-phantom in the hand-map — pass them through byte-for-byte, never "clean up" (`PORT_WAVE_MANIFEST.md:100`). (4) All four PASS verdicts are headless — treat as strong-but-provisional until a live-bridge session touches them.
- **Recipe for any NEW MaterialX node (OpenPBR, hair, hex-tiled, patterns):** it is un-wired and un-probed — call `synapse_scout` on the dotted/type name (or a live `hou.nodeType(hou.vopNodeTypeCategory(), name)` gate) BEFORE emitting a `createNode`. The 239-name set is the candidate pool, not a verified-wireable list.

**Roadmap (prioritized):**
- **P1 — Kill the live phantom.** In `usd-2` (or a standalone fix): replace `mtlxstandard_volume` at `render_recipes.py:701` with a probe-verified volume node (`mtlxvolume` / `mtlxvolumematerial`), and either drop `MTLX_STANDARD_VOLUME` from `mtlx_types.py:25,33` or repoint it. This is the one concrete break the whole cycle surfaced and left open.
- **P2 — Live-reconfirm the 4 PASS + the quarantine.** Fold a MaterialX node-type check into the next live-bridge session so the surface graduates provisional-headless → VERIFIED-LIVE (currently zero live coverage).
- **P3 — Decide the OpenPBR posture (design, not probe-first).** Runtime-diff the 239-name set once a baseline exists, and adjudicate whether `mtlxopen_pbr_surface` should join/replace the default surface — but only behind a live wiring probe; today it is UNGROUNDED.

---

### Panel / UI

**Coverage this cycle:** MODERATE — Qt/PySide version-truth and the font/letter-spacing path are probe-verified live under H22 hython, and the `panel-design-warden` review agent shipped, but the graphical (G2) live-widget audit was never run on 22.0.368 and two known design debts (cyan/blue 3-source, 13 sub-26px targets) were deliberately left standing.

**What H22 changed:**
- **Qt5 dropped; PySide/Qt is now 6.8.3, Python 3.13.10** on Houdini 22.0.368 — confirmed exact against `harness/state/drop.json` and the live runtime (`docs/reviews/h22-qt-smoke.md:63-78`, PySide `__version__` == `qVersion()` == compile-time == 6.8.3, no binding/runtime skew). **VERIFIED-LIVE.**
- **Vulkan-era build.** The warden records this as a standing caution (`.claude/agents/panel-design-warden.md:26` "never assume OpenGL-path behaviors"). *Caveat:* a Qt Python widget panel paints through Qt's raster/native path, not the Houdini viewport compositor — so "Vulkan-era" is mostly a viewport-capture concern, and **no actual GPU/Vulkan compositor path was exercised** by any test this cycle (offscreen platform only). **INFERENCE** on relevance-to-panel; **NULL** on live evidence.
- `hdefereval` raises `ImportError`-by-design outside graphical Houdini — verified identical line in both H22.0.368 (`python3.13libs/hdefereval.py:240`) and sibling H21.0.773, so **this is NOT an H22 delta** (`h22-qt-smoke.md:113-115`).

**What SYNAPSE probe-verified this cycle** (all under `C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe`, `QT_QPA_PLATFORM=offscreen`):
- **3/3 drop.json fields exact-match live** (build / python / pyside) — `h22-qt-smoke.md:75-78`. **VERIFIED-LIVE.**
- **13/13 letter-spacing probe checks PASS** across all three repo call sites: `designsystem/fontload.py:187` (`tracked_font` PercentageSpacing 116%), `designsystem/components.py:47` (`apply_font_role` AbsoluteSpacing 1.00px), `health_infographic.py:236` (raw QFont AbsoluteSpacing 0.5px round-trip) — `h22-qt-smoke.md:130-157`. **VERIFIED-LIVE.**
- **Bundled Space Grotesk / Space Mono register cleanly** into H22's QFontDatabase (`build_mismatch: False`, native-fallback branch not needed) — `h22-qt-smoke.md:146-159`. **VERIFIED-LIVE** (but offscreen QFontDatabase, not the GUI one — see gaps).
- **Qt6 enum paths resolve live:** `QFont.Weight.Medium` → `<Weight.Medium: 500>`; shortened `QFont.PercentageSpacing` == canonical `QFont.SpacingType.PercentageSpacing` — `h22-qt-smoke.md:144-151`. **VERIFIED-LIVE.**
- **Panel instantiates** (`run_panel.py --smoke` → `SMOKE OK — SynapsePanel instantiated`, exit 0) — `h22-qt-smoke.md:123-128`. **VERIFIED-LIVE but with a planted fake-`hou` stub**, not real host `hou`.
- **G3 strict audit passes** (`audit_panel.py --strict` → exit 0, 1 WARN) under H22 hython — `h22-qt-smoke.md:163-177`. **VERIFIED-LIVE (offscreen).**

**What SYNAPSE shipped/fixed:**
- **`run_panel.py` `_Hou` stub gained `isUIAvailable() → False`** (8 lines, dev-harness only, zero panel/bridge source change) — fixed a FAIL-as-found G1 boot smoke; committed in the drop-week runbook cycle **438c628** (`h22-qt-smoke.md:117-121`).
- **`panel-design-warden` review agent shipped** — `.claude/agents/panel-design-warden.md`, commit **7ddbf5f** ("CTO cross-reference cycle"). Encodes the design system, the 4-gate order, and the earned traps as an enforceable review contract.
- **`docs/reviews/h22-qt-smoke.md`** committed as the drop-week step-6 artifact (438c628).
- Pre-drop Qt hardening (context, not this cycle): **fb1a30b** "fully-scope PySide6 enums for H22 Qt enum scoping."
- **The RETINA release cycle (v5.27.0 → v5.28.0) touched no panel source** — panel had no code changes in the most recent shipped cycle.

**The honest gaps — ungrounded or untouched:**
- **G2 (real graphical Houdini 22) was NEVER run.** `h22-qt-smoke.md:199-202` states it explicitly ("does not test panel behavior inside graphical Houdini"), and `audit_panel.py:6` *still names "G2 (Houdini 21.0.671)"* as its real-host reference — the graphical audit has not been re-pointed at 22.0.368. So no real on-screen widget geometry, no GUI-thread QFontDatabase, no Vulkan-composited pixels have ever been seen on H22. **NULL.**
- **"Panel boots on H22" rests on a fake-`hou` stub.** The instantiation is real-panel-code under real-PySide-6.8.3, but `sys.modules["hou"]` is a `_Hou` stub (`h22-qt-smoke.md:101-121`). Real-host boot is unproven. **Partial / stub-bound.**
- **Cyan/blue 3-source accent NOT reconciled — deliberately.** The accent lives in three places: `designsystem/tokens.py:29` (`SIGNAL = "#8FB3D9"`), `panel/tokens.py:75` (panel cyan re-export, "colors INTENTIONALLY stay… pinned by `test_hda_panel`"), and `message_formatter.py:39` (`_SIGNAL = "#8FB3D9"` local hardcode). Naive unification breaks `test_hda_panel`, left standing on purpose (`.claude/agents/panel-design-warden.md:39-40`). **Untouched by design.**
- **13 interactive targets under 26px** — pre-existing G3 WARN, `warnable=True` in `audit_panel.py:171-173` (`TARGET_FLOOR = 26`), **unchanged by H22 and unfixed** (`h22-qt-smoke.md:197`). Also measured from offscreen `sizeHint()`, not real rendered pixels. **Untouched.**
- **`menu.exec_()` unguarded at `chat_panel.py:499`** — the deprecated PySide6 alias. Four sibling sites in `synapse_panel.py` (940/972/1089/1432) are correctly guarded with `hasattr(menu, "exec")`; this one is not. Flagged in the warden (`:48-49`) but **not fixed this cycle.** Grounded, live in the tree. **Untouched.**
- **Shortened QFont enum spelling is compat, not canonical** — resolves on 6.8.3 (probe-verified) but is the "forgiving enum" form Qt has threatened to retire since 6.x. If a future PySide drops it, the touch-list is the three §4 call sites + `motion.py`'s `QEasingCurve.Type` pattern (`h22-qt-smoke.md:191-196`). **VERIFIED-LIVE now, fragile forward.**
- **LLM providers (Anthropic/Gemini/Ollama/Nemotron/Custom) are host-agnostic** — no H22 surface, not probed against H22, correctly out of scope. **NULL (no H22 relevance).**
- **Rigging/KineFX/APEX panel affordances:** structural non-goal — the smoke explicitly refuses them (`h22-qt-smoke.md:203`). Boundary context only.

**SYNAPSE interaction blueprint for this context on H22:**
- **Lean on:** PySide/Qt **6.8.3**, Python **3.13.10** as ground truth (`harness/state/drop.json`). The Qt6-primary / PySide2-fallback import pattern is correct and live-verified — PySide2 branches are dormant dead weight kept for CI portability, don't rip them out.
- **The one boot rule:** there is **NO PySide in stock python** — boot/smoke the panel **only** via hython offscreen (`QT_QPA_PLATFORM=offscreen`), never stock python (`panel-design-warden.md:33-34`). And any fake-`hou` stub run under hython **must** provide `isUIAvailable()` or `hdefereval`'s top-level `ImportError` becomes an `AttributeError` that escapes every `except ImportError` guard in the repo.
- **The real gate is the FULL `python -m pytest tests/`** (4275/0/87 floor), never a panel-only subset — sibling test files plant PySide stubs that leak module-globals and lie in isolation (`panel-design-warden.md:35-36`).
- **Design-review any `panel/` change through `panel-design-warden`** (the agent gates: `audit_panel.py --strict` exit 0 → seeded-contrast sweep → hython offscreen boot → full suite). It reinforces the design and refuses to weaken an audit to pass.
- **Traps to avoid:** (1) do NOT naively unify the 3-source accent — `test_hda_panel` pins it; (2) "connected" label ≠ bridge reachable — `synapse_ping` first; (3) `QApplication` must be a genuine PySide type when deciding `_HAVE_QT`; (4) guard any new `menu.exec()` / `dlg.exec()` call site with `hasattr(..., "exec")`.
- **New Qt/`hou` symbols** must be checked against `python/synapse/cognitive/tools/data/h22_symbol_table.json` (remember: GUI submodules `hou.ui`/`hou.qt` are omitted from the headless table — allowlist, don't phantom-flag them).

**Roadmap (prioritized):**
- **P1 — Run G2 on a real graphical Houdini 22.0.368 session.** Boot the actual `SynapsePanel` in the host (not a fake-`hou` stub), capture on-screen widget geometry + real GUI QFontDatabase, and re-point `audit_panel.py:6`'s stale "Houdini 21.0.671" G2 reference to 22.0.368. This is the single load-bearing hole: everything "live" today is offscreen+stubbed.
- **P2 — Fix the unguarded `menu.exec_()` at `chat_panel.py:499`** to the `hasattr(menu, "exec")` pattern already used four times in `synapse_panel.py` — cheap, isolated, removes a known deprecation landmine before a future PySide bump.
- **P2 — Real-pixel pass on the 13 sub-26px interactive targets** once G2 exists: confirm whether the offscreen `sizeHint()` WARN reflects true rendered geometry in the host, then either raise the targets to the 26px floor or ratify the WARN with real evidence.
- **P3 — Schedule (do not force) the cyan/blue 3-source reconciliation** as a deliberate, full-suite-green refactor that updates `test_hda_panel` in lockstep — never a naive unify.
- **P3 — Pre-stage the shortened-enum touch-list** (three §4 font call sites + `motion.py` `QEasingCurve.Type`) so a future PySide drop of the forgiving-enum spelling is a known, bounded edit.

---

### Memory / substrate

> **[UNVERIFIED — analyst section_md truncated in dispatch.]** The Memory/substrate analyst's
> full `section_md` did not arrive intact in this dispatch; only the headline and a partial
> `top_gap` were delivered. The body below is what was received; the remainder (what H22 changed,
> probe-verified, shipped/fixed, gaps, interaction blueprint, roadmap) is **owed from the
> memory/substrate analyst** and must be folded in before this section is treated as complete.
> SCRIBE will not fabricate the missing body.

**Coverage this cycle:** MODERATE.

**Headline (verbatim, delivered):** The lossless USD round-trip survived the 0.26.5 reorg
(fidelity 1.0, VERIFIED-LIVE) — but the path probed is a library with no live callers; the tool
an artist actually fires is a different, deprecated, unprobed module.

**Top gap (verbatim, delivered — truncated):** "The verified moat i…" *[cut off in dispatch]*.
Read against the headline: the verified USD-round-trip moat sits on a **caller-less library
path**, while the module an artist actually invokes is a separate, deprecated, **unprobed** path
— so the fidelity-1.0 result does not yet cover the live surface.

**Roadmap placeholder (P2, derived from the delivered headline — to be replaced by the analyst's own):**
Probe the deprecated module that artists actually fire on 22.0.368 and reconcile it against the
verified library round-trip, so the fidelity-1.0 result covers the live path rather than a
caller-less one. *Marked owed until the full section lands.*

---

### DOP / MPM (dynamics / sim)

**Coverage this cycle:** UNTOUCHED — the dynamics/simulation frontier (DOP / Bullet / Vellum / Pyro / FLIP / MPM) got no analyst section, no intentional probe, no cook/parm/solver-behavior verification, and no shipped code this cycle; the only H22 grounding is *byproduct wiring-label rows* that rode along in the SOP/DOP connectivity sweep, and MPM specifically has zero SYNAPSE code surface of any kind.

**What H22 changed:** No known dynamics/sim behavior change was probed, and none is claimed. I ran no live probe this dispatch — everything below is VERIFIED-ARTIFACT (catalog reads) or NULL. The one *artifact* delta I can cite honestly: the H22 connectivity catalog carries a `Dop/` block and a `Sop/mpmsolver` row with input/output wiring labels, byte-diffable against H21 — but that is emit-list wiring coverage, **not** a proven Houdini sim delta:
- **MPM is a SOP on modern Houdini, not a DOP** — `Sop/mpmsolver` (instantiated, inputs `MPM Sources` / `MPM Colliders` / `MPM Container` → output `MPM Output Particles`). Cite: `python/synapse/cognitive/tools/data/connectivity_22.json:3597-3614` (present identically in `connectivity_21.json:3397-3416`, so its H22 appearance is catalog coverage, **not** an H22-new symbol — INFERENCE that MPM predates H22, base-model).
- **A `Dop/` block exists in the H22 catalog** with wiring labels for `dopnet`, `flipsolver`(+`::2.0`), `pyrosolver`(+`::2.0`), `rigidbodysolver`, `rbdpackedobject`, `vellumsolver`, `vellumconstraints`, `vellumconstraintproperty`, `gravity`, `merge`, `noise`, `null`, `output`, `subnet`. Cite: `connectivity_22.json:954-1300`. Wiring-labels-only; no parm, cook, or solver-semantics truth attached.
- Net: **no verified H22 dynamics change and no verified break** — only the same wiring-catalog byproduct the SOP/CHOP contexts got, extended to the Dop category and `mpmsolver`.

**What SYNAPSE probe-verified this cycle:**
- **Nothing intentional for DOP/sim.** There is no dynamics analyst section, no `h22-dop`/`h22-sim` review doc (`Glob docs/**/*{dop,sim,vellum,pyro,rbd,mpm,flip,bullet}*` → **No files found**), and no live sim probe was run.
- **Byproduct only (VERIFIED-ARTIFACT, headless):** the `Dop/*` wiring rows + `Sop/mpmsolver` labels in `connectivity_22.json` (blake2b-stamped, from `host/introspect_connectivity.py`, `hython`-headless — same sweep the SOP analyst characterized). This proves *input/output arity+labels* for those types on 22.0.368, and nothing else (no parms, no cook, no sim result).
- **Refuting a false "probe":** the only DOP-labeled probe artifact in the repo, `.claude/cook_probe_dop.json`, is **H21.0.671, not H22** (`"houdini_version": "21.0.671"`) and is a single trivial cook-determinism trial (`dop:emptyobject`, parm `eo1/solvefirstframe`, cookcount delta 1) — a D-track cook-truth byproduct, not a sim-physics probe. It grounds nothing about H22 dynamics.

**What SYNAPSE shipped/fixed:** Nothing this cycle for DOP/sim. No dynamics handler exists to change — SYNAPSE has **no `houdini_*` / `mcp__synapse__*` DOP or sim tool** in the 115-tool surface. The only dynamics *code* surface is the routing-layer recipe pack `python/synapse/routing/recipes/fx_recipes.py` (registered via `recipes/base.py:182,188`): seven H21-authored `execute_python` string-template recipes — `pyro_source_setup` (L15), `vellum_cloth_sim` (L55), `rbd_destruction` (L105), `ocean_setup` (L166), `pyro_fire_sim` (L212), `vellum_wire_sim` (L273), `dop_network_setup` (L322). **None were re-probed or modified for H22**, and **none is MPM** — there is no MPM recipe, handler, or tool anywhere in `python/synapse/`.

**The honest gaps — ungrounded or untouched:**
- **MPM = UNGROUNDED (base-model only).** Joe asked about MPM directly; the honest answer was shallow-to-none. SYNAPSE's only MPM presence is (a) one byproduct wiring row (`connectivity_22.json:3597`) and (b) documentation in the `rag/` corpus — `rag/documentation/tutorials/workflow_guides/mpm_*.md` (~18 guides), `rag/documentation/_raw_documentation/mpm_masterclass/*`, `rag/skills/houdini21-reference/mpm_solver.md`, `mpm_production_workflows.md`. Corpus is *retrieval intent*, H21-namespaced, never re-probed on 22.0.368 — knowledge_lookup/scout can *re-teach* stale MPM strings. Every MPM parm, preset, DOP-data name, and solver behavior is base-model knowledge with no probe behind it.
- **The 7 fx sim recipes are H21 assumptions on an H22 runtime.** `vellum_cloth_sim`/`vellum_wire_sim` hardcode `vellumconstraints` presets + `vellumsolver` input-label wiring; `rbd_destruction` chains `rbdmaterialfracture`→`rbdbulletsolver`; `pyro_fire_sim` builds `pyrosolver`; `dop_network_setup` builds a classic `dopnet`+`rigidbodysolver`. Their `wire_by_label` calls carry U.1-catalog comments (e.g. `vellumsolver 0=Vellum/1=Constraint/2=Collision`, `fx_recipes.py:84-86`) — but **no cook was ever run on H22** to prove the createNode spellings resolve, the parm names still exist, or the caches actually cache a cooked sim. Every `.parm(...)` in those templates is H21-era, unverified on 22.0.368.
- **No cook / no parm / no solver-semantics truth for any sim node on H22.** The catalog proves wiring arity only. Sim is cook-heavy and time-dependent; nothing in this cycle stepped a solver, cached a frame, or verified a sim result on 22.0.368.
- **No H21 baseline.** H21 uninstalled on drop day — even the byproduct `Dop/*` catalog rows are ground-truth H22 shape, not a verified H21→H22 diff.
- **DOP is a named-but-unrun future probe target.** `harness/state/flywheel_queue.json:72` enumerates a per-context create-capability probe over `SOP/LOP/COP/TOP/DOP/MAT` — DOP is listed but only SOP/LOP were actually run this cycle. The scaffolding to probe DOP exists; it was never pointed at DOP.
- **Rigging solvers are boundary context, never a target.** The same catalog carries `musclesolver*`, `tissuesolver*`, `apex::*`, `kinefx::*` — **structural non-goals**. Visible in the sweep ≠ in-scope. Noted only so nobody reads their catalog presence as coverage.

**SYNAPSE interaction blueprint for this context on H22 (the forward contract):**
- **There is no sim tool — set expectations first.** SYNAPSE cannot "run a simulation" as a first-class op. The only affordance is the 7 natural-language recipe triggers in `fx_recipes.py` (e.g. "set up a vellum cloth sim", "create rbd destruction", "set up a pyro fire sim") which emit `execute_python`, plus falling through to raw `houdini_execute_python` / `houdini_create_node`. For MPM there is **no recipe at all** — an MPM ask lands entirely on raw execute_python.
- **MPM recipe (build-from-primitives, H22):** create `Sop/mpmsolver` via `houdini_create_node` (`type=mpmsolver`, parent a `/obj/geo`); wire with `wire_by_label(node, "MPM Sources"|"MPM Colliders"|"MPM Container", src)` — the labels ARE catalog-backed on H22 (`connectivity_22.json:3597`), so wiring is safe. **But every parm/preset is UNGROUNDED** — `synapse_scout` every `mpm*` symbol and parm name before emitting, and expect no verified result without a cook.
- **Sim solvers are SOP-level in modern Houdini** — `mpmsolver`, `vellumsolver`, `pyrosolver`, `rbdbulletsolver` are SOP "solver" nodes built under `/obj/geo`, not DOP-network nodes. Only reach for a classic `dopnet` (the `dop_network_setup` recipe path: `dopnet`+`rigidbodysolver`+`rbdpackedobject`+`gravity`+`merge`) when the classic DOP context is explicitly wanted.
- **Wire by label, never by index.** The `vellumsolver`/`rbdbulletsolver` input-index drift is exactly why `wire_by_label` exists (`fx_recipes.py:83-86,144-147`) — it fails loud on an unknown type/label rather than miswiring. `connectivity_22.json` backs the resolution for the running major.
- **Traps:** (1) Sims are cook-heavy + time-dependent — the recipes author a `filecache` but nothing steps the timeline or verifies a cooked frame; a "success" return means the network was built, **not** that it simulated. (2) Every parm in the fx recipes is H21-assumed — a parm-not-found on H22 is the unprobed-parm risk, not a bug in your call. (3) `musclesolver`/`tissuesolver`/`apex::`/`kinefx::` in the catalog are rigging **non-goals** — never emit them as a sim target. (4) MPM corpus docs are H21-namespaced and unverified — treat scout/knowledge_lookup MPM hits as *leads to verify*, not truth.
- **Trust posture:** wiring labels for `Dop/*` + `Sop/mpmsolver` = VERIFIED-ARTIFACT (headless). Everything else — parms, cook behavior, solver semantics, all MPM specifics, all 7 recipes' H22 correctness — is UNGROUNDED base-model. Scout-gate hard; prefer to tell the artist a sim path is unverified over silently emitting an H21 assumption.

**Roadmap (prioritized):**
- **P1 — Get the scope ruling (human; OPEN DECISION #2).** Decide whether dynamics is in-scope for SYNAPSE at all. The product's differentiator is COPs / Solaris-USD / Karma receipts, and sim is a different mountain. **Option A:** mark DOP/MPM a documented **non-goal** (mirrors the CHOP Option-A recommendation) so byproduct `Dop/*` + `Sop/mpmsolver` catalog rows stop reading as partial coverage. **Option B:** admit it as an in-scope frontier → P2. Nothing below should start until this is ruled.
- **P2 — (if in-scope) Queue an `h22-doc-scout` pass over the SideFX H22 dynamics docs.** The `h22-doc-scout` skill already exists and the `rag/` corpus (mpm_masterclass + the `mpm_*` workflow guides + vellum/pyro/rbd/flip skills) can seed intent. Output: a DOP/MPM `candidates.json` + a first **intentional** live probe of the SOP-level solver set the recipes already lean on (`mpmsolver`, `vellumsolver`, `pyrosolver`, `rbdbulletsolver`) — parm names, one smoke cook per solver, and MPM Sources/Colliders/Container wiring confirmed against a real cook rather than labels alone.
- **P3 — (if in-scope) Re-probe the 7 `fx_recipes.py` sim recipes on 22.0.368 and attach each to an artifact.** They are H21 `execute_python` templates: confirm every `createNode` spelling resolves, every `wire_by_label` index still holds against `connectivity_22.json`, and each `filecache` actually caches a *cooked* sim frame — then stamp each recipe with its H22 probe artifact instead of the current H21 assumption. Also point the already-scaffolded DOP context-capability probe (`flywheel_queue.json:72`) at DOP so "what can SYNAPSE create in DOP on H22" is answered by a probe, not by inference.

---

## 5. Cross-Context Roadmap (merged, prioritized)

Every context's roadmap folded into one plan. All items enter the flywheel **gated** — this
document mutates nothing; it only sequences. "Ratified" below means `"ratified": true` in
`harness/state/flywheel_queue.json` (SCRIBE-verified for C.4/C.3/C.10), still awaiting per-cycle
human-merged builds.

### P1 — blocking / near-term / ratified-ready

1. **RETINA M1b — sibling-honesty follow-up** *(render/perception, cross-cutting).* The just-shipped
   T0 receipt cycle (v5.28.0, `72de5f1`) carries an open M1b tail (`0039026`). Close it before the
   next receipt tier.
2. **U.5-H22 `lop_knowledge` fold** *(LOP/Solaris).* Give `core/lop_knowledge.py` the same
   `_running_houdini_major()` / `_pkg_catalog_path()` resolution `wiring.py` already has, then
   commit `lop_solaris_knowledge_22.json`. **Load-bearing:** today `graph_validator` silently runs
   H21 Solaris CONTEXT truth against H22 stages. This is the WIRING-went-major-aware / CONTEXT-did-not twin gap.
3. **Copernicus C.4 → C.3 → C.10** *(COP, ratified builds, build order fixed).* All three
   `ratified:true` in the queue. **C.4 first** (scaffold rebuild — kills the silent-no-op placebo
   class, zero external deps), **then C.3** (neural COPs + doctor preflight), **then C.10** (terrain).
   Human-merge per cycle. C.10 blocked on OPEN DECISIONS #3 (naming).
4. **COP P-1 live-bridge cook/instance probe** *(COP).* The single gate blocking C.4, C.10, *and*
   the audit's PENDING-BEHAVIORAL cook verdicts. Requires `/obj` cleared of `_recon_*`/`_w4assay_*`
   debris. Also lifts the 10 CHANGED scaffold verdicts from PROVISIONAL-HEADLESS.
5. **Kill the `mtlxstandard_volume` live phantom** *(VOP/MaterialX).* Replace it at
   `render_recipes.py:701` with a probe-verified volume node (`mtlxvolume`/`mtlxvolumematerial`) and
   drop/repoint `MTLX_STANDARD_VOLUME` in `mtlx_types.py:25,33`. The one concrete break the cycle
   surfaced and left open (the assigned `usd-2` wave never ran).
6. **Run Panel G2 on a real graphical Houdini 22.0.368 session** *(Panel/UI).* Every "live" panel
   claim today is offscreen + a fake-`hou` stub; re-point `audit_panel.py:6`'s stale "21.0.671" G2
   reference to 22.0.368 and capture real widget geometry + GUI QFontDatabase.
7. **Probe SOP parameters on 22.0.368** *(SOP).* For the core geometry set SYNAPSE drives
   (attribwrangle, scatter, copytopoints, merge, object_merge, switch, group, blast). Closes the
   single largest SOP gap — every `set_parm` and `execute_vex`'s `class`/`snippet` parms are H21-assumed.
8. **TOP/PDG live-bridge reconfirm** *(TOP/PDG).* Promote the 4 event-bridge truths (no-constructor
   `PyEventHandler`, raw-callable `addEventHandler`, worker-thread callbacks, `workItemId`) from
   PROVISIONAL-headless → VERIFIED-LIVE next time a live bridge is up — the cheapest honest close on
   the surface SYNAPSE actually runs on, and it lets the CLAUDE.md PyEventHandler warning extend to
   22.0.368 with confidence.

### P2 — unblocks or hardens

- **LOP:** live-bridge reconfirm of N-5/N-3 (layout/instancer create+cook, `light:filters` round-trip)
  to lift PROVISIONAL-HEADLESS; decide whether to code-guard the node-named-prim-path trap
  (`/Render/<node>` vs `/Render/rendersettings`); run the deferred N-1/N-4.
- **COP:** build **C.3 neural COPs** (sequenced under C.4; run Download Models GUI-elevated in
  parallel to arm the cook test); run **P-2** stamp/scatter modern-target enumeration (never probed).
- **VOP/MaterialX:** live-reconfirm the 4 PASS + the quarantine (zero live coverage today).
- **SOP:** re-probe VEX-in-SOP `run_over`→`class` menu mapping (0–3) + a smoke `attribwrangle` cook,
  then attach `_handle_execute_vex`'s mapping to the probe artifact.
- **Panel/UI:** fix the unguarded `menu.exec_()` at `chat_panel.py:499`; real-pixel pass on the
  13 sub-26px targets once G2 exists.
- **TOP/PDG:** build **`tops_manage_service`** (TOPS-08 PDG Services / warm-session) — the
  highest-leverage *new* capability, aimed at the ~2s cook floor; gate on a behavior probe of
  `pdg.ServiceManager` verbs first (symbols already table-verified). Add rich telemetry to
  `tops_monitor_stream` (per-item percent-complete + output-files-as-they-land via
  `ctx.graph.workItemById`; harden with `supportedEventTypes`).
- **Memory/substrate:** probe the deprecated live-caller module on 22.0.368 and reconcile it against
  the verified library round-trip *(owed — full analyst roadmap not yet delivered; see §4)*.

### P3 — deferred / design / debt-paydown

- **LOP:** extend `_SOLARIS_NODE_ORDER` to the new H22 instancing family (`scatterinstances`,
  `mergepointinstancers`, `splitpointinstancers`, `extractinstances`, `modifypointinstances`,
  `retimeinstances`); consider a `scatterinstances` template.
- **COP:** build **C.10 terrain** (sequenced last; needs P-1(c) label capture); fix corpus divergence
  (`rag/skills/houdini21-reference/copernicus_python_api.md:315` still teaches `planes()`); resolve
  OD-A (manifest 115→118) and OD-C (verb name) — OPEN DECISIONS #3.
- **SOP:** close the `connect_nodes` seam (route through the connectivity catalog / arity-validate
  `target_input`); exhaustive `Sop`-category census beyond the emit list.
- **VOP/MaterialX:** decide the OpenPBR default-surface posture behind a live wiring probe — OPEN
  DECISIONS #4.
- **Panel/UI:** schedule (don't force) the cyan/blue 3-source reconciliation with `test_hda_panel`
  updated in lockstep; pre-stage the shortened-enum touch-list.
- **CHOP:** re-namespace or retire `rag/skills/houdini21-reference/chops.md` so retrieval flags it
  unverified-on-H22.
- **TOP/PDG:** ML TOP family (TOPS-06/07) — biggest greenfield, new-build not breakage; **must start
  with a live `nodeTypeCategories()['Top']` scan** to resolve the real `ml_traingsplats` name and
  kill the `top::gaussian_splat_train` phantom before any tool wiring. Corpus-seed the PDG
  worker-thread + node-vs-item registration contract (TOPS-03/04), H22-tagged.

### UNGROUNDED DOMAINS — future doc-scout targets (honest debt, not hidden)

- **DOP / Bullet / Vellum / Pyro / MPM — the simulation frontier.** **UNTOUCHED.** A dedicated §4
  section now documents the untouched state, but there is no intentional probe and no H22 artifact
  beyond byproduct `Dop/*` + `Sop/mpmsolver` wiring rows. MPM has **zero** SYNAPSE code (not even a
  recipe); the 7 `fx_recipes.py` sim recipes (pyro/vellum/rbd/ocean/dopnet) are H21 `execute_python`
  templates never re-probed or cooked on 22.0.368. The single largest ungrounded domain. Scope ruling
  owed (OPEN DECISIONS #2) before any doc-scout pass is queued.
- **CHOP (channels / motion).** SHALLOW today — only byproduct catalog rows; the real operator space
  is unprobed on H22 and the only knowledge is a stale H21-namespaced corpus doc. Scope ruling owed
  (OPEN DECISIONS #1); if lifted, one intentional arity+wiring probe grounds it.
- **SOP depth (cook / parm / VEX census).** Wiring-only today. The parameter, cook, and VEX-semantics
  layers are ungrounded on 22.0.368 — the P1 parm probe above starts this, but the exhaustive
  category census remains debt.
- **TOP/PDG new-capability surface (greenfield debt, not breakage).** The event bridge SYNAPSE runs
  on is covered (MODERATE), but every *new* H22 TOP capability is scouted-from-docs-only and unbuilt:
  PDG Services / warm-session (`pdg.ServiceManager`, behavior DOC-CLAIM), the ML TOP family
  (node-type names never live-scanned), and rich per-item telemetry. Surfaced here as honest debt so
  a covered-context tag doesn't hide the unbuilt frontier underneath it.

---

## 6. Closing — the meta-lesson

**Probes beat memory.** Everything this document can stand behind was earned by a probe on the
live 22.0.368 runtime or a code-cited read of the tree; everything it flags as a gap is precisely
where a probe *didn't* run and an H21-era assumption is still load-bearing (`lop_knowledge`
serving H21 context on H22 stages; SOP parms; the `mtlxstandard_volume` phantom still in recipe
text). The cycle's discipline — probe truth over pinned constants — is the reason the coverage map
above can be honest about its own holes.

**The crucible earned its cost.** Adversarial passes caught real lies this cycle, not
hypothetical ones: the **RETINA dead `.done` sentinel** that fired before pixels existed
(`64e49fc`, "crucible caught a dead .done sentinel", repaired in the M1 Pass-2 that shipped as
T0); the COP **W.1b "loud drift" that was 1/3-implemented plus a crash regression** (the sev-3
that forced a Pass-3 before merge, `cd3983f`); and a **test-count honesty slip caught pre-push**
in an earlier drop-week cycle. Three catches — each one a claim that would have read as green and
wasn't.

**Coverage honesty over the victory lap.** The temptation after a major-version port is to
publish the wins — three merged Solaris waves, the deepest COP audit the project has run, a live
render receipt. Those are real. But the deliverable a reviewer needs is the map that shows the
SOP parameter layer is H21-assumed, the panel has never booted in a graphical H22 session, the
PDG warm-session lever against the cook floor is scouted but unbuilt, and the entire sim frontier
was never touched. This document is **paper**: it mutates nothing, ships
nothing, and gates nothing on its own. Every roadmap item above enters the flywheel through the
existing human ratification gate — the honest map is the product, the builds come later.
