# H22 CTO Roadmap — 2026-07-16

> **The single prioritized roadmap for SYNAPSE on Houdini 22.0.368.** This document is paper. It mutates nothing.
> Synthesized from three judge lenses over the full drop-week evidence set; every item carries its evidence artifact.

---

## Provenance

**Date:** 2026-07-16 · **Target build:** Houdini 22.0.368 (py 3.13.10 / USD 0.26.5 / PySide 6.8.3) · **Branch:** `feat/h22-drop-execution` (unmerged)

**Inputs (all repo-relative):**

| Input | Role |
|---|---|
| `harness/notes/h22_doc_candidates.json` | Doc-intel wave 1 (Solaris/COPs/HOM) — 42 candidates, 37 probe-VERIFIED under H22 hython, 0 refuted, 5 NOT_RUNNABLE |
| `harness/notes/h22_doc_candidates_wave2.json` | Doc-intel wave 2 (TOPs-ML/Karma/news-delta) — 35 candidates, DOC-CLAIM until probed (21 symbol-table VERIFIED) |
| `docs/reviews/h22-doc-intel-2026-07-15.md` / `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` | The two scout reports (TOP-10 / PHANTOM WATCH / ESCALATE) |
| `docs/reviews/h22-cop-audit-verification.md` | RUNTIME TRUTH: 21 COP tools — 11 PASS / 10 CHANGED / 0 GONE, parm-level no-op evidence, 3 PENDING-BEHAVIORAL |
| `harness/notes/verified_connectivity_H22.json` | RUNTIME TRUTH: node-wiring diff 21.0.671→22.0.368 (+9/−3/3 changed; Lop instancer+layout removed; Cop/light miswire class) |
| `docs/intake/adjudication-h22-release-notes.md` | Release-notes adjudication (C2 closed-with-rider; G-gap deltas; 1 boundary-pressure event) |
| `docs/reviews/h22-drop-execution-2026-07-15.md` | Drop-day record (OPEN: Solaris layout ruling, rewire_assess vcc pin, chat_panel exec_ guard) |
| `docs/reviews/h22-pdg-perception-reaudit.md` / `docs/reviews/h22-quarantine-repin.md` | pdg re-audit (4/4 truths hold) + phantom re-pins (4/4 stay QUARANTINE; hou.secure GUI caveat) |
| `docs/PORT_WAVE_MANIFEST.md` | 115-tool / 11-sub-wave port plan; OD-1/2/3 open decisions; per-wave traps |
| Panel warden assessment (this session) | Verbatim audit verdict: **"G3 RESULT: pass · 1 WARN"** (authoritative hython-offscreen run on H22.0.368; the WARN = 13/22 interactive targets under 26px). "ASSESSMENT COMPLETE — no edits made." |

**Judge lenses and merge rule:** three independent rankings — **ARTIST-VALUE** (silent no-ops/miswires > loud breaks > new features), **RISK** (cost-of-inaction weighted by parity-golden freeze exposure), **COMPETITIVE-MOAT** (receipts/reversibility/provenance honesty in the lanes SideFX left empty). Merge: top-8 by 2+ lenses → **P1**; top-8 by one lens → **P2**; single-lens tail → **P3** unless it is a silent break, which floors at **P2**.

**Gate state snapshot (fixed context — not re-derived here):** MODE B armed (`harness/state/drop.json` exists, untracked). Human gates OPEN: (1) ratify U.1-H22 in `flywheel_queue.json`, (2) Solaris layout-LOP successor ruling, (3) merge `feat/h22-drop-execution` → master, (4) OD-1/2/3 rulings in the manifest. Port waves dispatch ONLY after ratify + manifest gates. Posture = solo. Rigging/KineFX/APEX is **structurally REFUSED** (boundary-pressure event logged and rejected in the adjudication — the refusal got *more* correct, not less). All drop-week probe PASSes are **PROVISIONAL-headless** (bridge was down at every probe); one live-bridge reconfirm pass is owed.

---

## 2. THE ENERGY THESIS

This cycle's energy goes to **making the receipts honest before the port waves freeze them**. SYNAPSE's differentiator is that every operation is recorded, reversible, and true — and right now, on H22, several recorded operations are quietly false: two tools return `planes:[]` with a clean envelope while the data is gone (NWS-03), the USD read path returns `None` for migrated karma relationships with no error (KAR-08), four COP tools accept simulate-mode settings the runtime silently ignores (block_end parm loss), and index-based Cop wiring lands masks in the wrong input with a recorded success (Cop/light 3→8 miswire class). The port-wave machinery makes this urgent rather than merely embarrassing: **each wave captures parity goldens that byte-pin the current envelope as the contract** — an unfixed silent break that reaches its wave gets golden-pinned as correct behavior, converting a bug into a spec. So the sequence is: (1) run the one live-bridge session that converts every PROVISIONAL-headless verdict to trusted truth and settles the three PENDING-BEHAVIORAL unknowns; (2) burn down the cheap NOW-legal probes that sharpen every gated fix; (3) flip the human gates; (4) land the silent-break fixes **with or before** their waves; and only then (5) let the new-capability moat work — neural COPs, reversible pxr authoring, PDG telemetry, warm services — earn its own ratification. Features wait. Truth of receipts first.

---

## 3. SILENT-BREAK REGISTER

> Every item where SYNAPSE currently does something wrong on H22 **with no error surfaced**. These outrank everything else. **PORT-FREEZE** = a parity golden pins the broken behavior if the fix does not land with or before the named wave.

### SB-1 · `CopNode.planes()` silent data loss — **P1** (all 3 lenses)

- **What happens today:** `cops_read_layer_info` (`handlers_cops.py:446`) and `cops_analyze_render` (`handlers_cops.py:684`) call `node.planes()`. `hou.CopNode.planes` is **gone** on 22.0.368 (`hasattr → False`, confirmed live); both call sites are try/except-guarded, so an artist asking "what layers does my comp have" gets `planes:[]` with **zero error**. `Cop2Node.planes` survives, masking the break on legacy nets (degradation is Copernicus-surface-only — the nuance the wave-1 note missed; wave-1 also flagged `composite_aovs`, which the COP audit adjudicated PASS-with-note).
- **Evidence:** `harness/notes/h22_doc_candidates_wave2.json` NWS-03 (= wave-1 HOM-02, all 9 replacement symbols PRESENT, `planes` ABSENT) · `docs/reviews/h22-cop-audit-verification.md` tools #6/#9 CHANGED (`.xRes/.yRes/.depth` also gone) · `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` ESCALATE #1 · doc: https://www.sidefx.com/docs/houdini22.0/news/22/vex.html
- **Fix shape:** migrate 2 call sites to `cable()`/`layer()`/`CopCable`/`ImageLayer` (full replacement surface table+probe VERIFIED) **+ fix the corpus recipe** `rag/.../copernicus_python_api.md:315` which still teaches `planes()` (code/corpus divergence rule — fix both or scout re-teaches the break).
- **Lane + wave:** WAVE-COUPLED — must merge **before or with wave `cops-1`** (both tools are `[RO]` in cops-1; their goldens assert the response envelope on a fixture). Blocked on: doc-candidate ratification + merge of `feat/h22-drop-execution`. Port waves must NOT "fix" this themselves — a behavior change is not a port.
- **PORT-FREEZE:** unfixed, cops-1 golden-pins `planes:[]` data loss as the correct contract.

### SB-2 · Cop input-index miswire class — **P1** (all 3 lenses)

- **What happens today:** `Cop/light` went 3→8 inputs (`N`→`normal`; `mask` moved index 2→**7**); `Cop/file` gained a `size_ref` input. Any `setInput` wiring by remembered H21 index feeds the **wrong input** — the comp cooks clean, renders plausible, and is wrong. `cops_connect` is API-PASS; nothing errors anywhere.
- **Evidence:** `harness/notes/verified_connectivity_H22.json` `diff.changed` ("MISWIRE CLASS" note, verbatim) · `docs/reviews/h22-cop-audit-verification.md` tool #4 HF-flag ("H21-remembered input indices silently wrong").
- **Fix shape:** the H22 connectivity catalog is already probed, deterministic (3 byte-identical runs, 0 probe errors) and diffed; the packaged truth (`python/synapse/cognitive/tools/data/connectivity_21.json`) stays H21 until the **U.1-H22 SCAFFOLD phase** folds it in. This is exactly the drift class U.1 exists to catch.
- **Lane + wave:** WAVE-COUPLED — blocked on **human gate 1 (ratify U.1-H22 in `flywheel_queue.json`)**. Touches `cops_connect` (wave cops-1).
- **PORT-FREEZE:** destructive-tool goldens pin dispatch not wiring, so no direct golden freeze — but the port preserves the miswire indefinitely until U.1-H22 lands.

### SB-3 · COP solver-block parm loss + alias no-ops — **P1** (2 lenses top-8)

- **What happens today:** `block_end` lost `method`/`blocktype`/`blockpath` (all → False on live nodes) — **simulate mode and explicit block binding silently no-op** in `cops_create_solver` / `cops_growth_propagation` / `cops_reaction_diffusion` / `cops_wetmap` (tools #11/#13/#14/#17; wetmap's frame-by-frame temporal decay is load-bearing and silently lost — an artist gets a static wetmap with a clean result envelope). Also: `limit` resolves to `clamp` with `max`/`high` absent → threshold sets no-op; `quantize` `levels`/`steps` absent on BOTH surfaces → toon/posterize no-op everywhere (tool #16).
- **Evidence:** `docs/reviews/h22-cop-audit-verification.md` headline verdicts #4/#5 + tools #11/#13/#14/#16/#17 + PENDING-BEHAVIORAL #2.
- **Fix shape:** the honest next step is the **probe, not a blind rewrite** — whether Cop blocks bind implicitly without `blockpath`/`method` is PENDING-BEHAVIORAL #2 and headless cannot answer it. Probe rides the live-bridge pass; the re-authoring fix then rides its own ratified cycle.
- **Lane + wave:** probe = NOW (live bridge); fix = WAVE-COUPLED, must precede **cops-1** (`cops_create_solver`) and **cops-2** (`growth_propagation`/`reaction_diffusion`/`wetmap`/`stylize`) golden capture.
- **PORT-FREEZE:** unfixed, cops-1/cops-2 golden-pin the no-op envelopes.
- **Honesty bound (from the audit, verbatim class):** H21 is uninstalled and no H21 COP parm baseline was ever captured — CHANGED = H22 truth vs what the code emits, not a proven H21→H22 delta.

### SB-4 · karma relationship reads return `None` — **P1** (all 3 lenses)

- **What happens today:** karma/husk USD schemas migrated string properties → **USD relationships**. `handlers_usd.py` reads via `prim.GetAttribute()` only (lines 365/413) — **zero** `GetRelationships` usage anywhere — so a lighter querying a migrated `karma:*` property gets `None` with no error, and `set_usd_attribute` cannot author the relationship at all. Wrong render-settings reads feed `shot_render_ready` and render tooling downstream.
- **Evidence:** `harness/notes/h22_doc_candidates_wave2.json` KAR-08 (both schema symbols table-VERIFIED) · `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` ESCALATE table · doc: https://www.sidefx.com/docs/houdini22.0/news/22/karma.html
- **Fix shape:** two halves. (a) **Identification probe** — build karmarendersettings + a light-filter assignment, cook, diff `prim.GetRelationships()` vs string attributes to identify which `karma:*` properties migrated: hython-runnable, **NOW-legal, not yet run**. (b) Relationship-aware read/write extension to `get/set_usd_attribute` — own ratification.
- **Lane + wave:** probe = NOW; fix = WAVE-COUPLED, must precede **usd-1** golden capture (`houdini_get_usd_attribute` is `[RO]` in usd-1 — third sub-wave in dispatch order).
- **PORT-FREEZE:** unfixed, usd-1 golden-pins the None-returning read envelope.

### SB-5 · `Lop/instancer` + `Lop/layout` removed — **P1** (all 3 lenses; loud, not silent — floors here because it takes the flagship set-dressing lane down whole)

- **What happens today:** `createNode('instancer')` / `createNode('layout')` **raise** on H22 (connectivity diff, version-stripped matching included). `instancer`→`pointinstancer` is a **confirmed rename** (SOL-03 re-probe: `instancer` ABSENT, `pointinstancer` present); `layout` has **no successor found in any category** — that ruling is open human gate 2. Emitting sites: `server/solaris_graph_templates.py:393`, `server/handlers_solaris_assemble.py:54,69`, `routing/recipes/scene_recipes.py`, `tests/test_setdressing_recipe.py`, palette filters. Drop-day record: multi-site — **do NOT half-fix**; wants a live create+cook test, not a string swap.
- **Evidence:** `harness/notes/verified_connectivity_H22.json` `diff.removed` · `docs/reviews/h22-drop-execution-2026-07-15.md` OPEN #1 · `harness/notes/h22_doc_candidates.json` SOL-03.
- **Fix shape:** human layout ruling first (a NOW-legal nodetype-catalog successor probe can feed it), then one ratified flywheel fix covering all sites + live create+cook test.
- **Lane + wave:** WAVE-COUPLED — blocked on **human gate 2**; rides before **usd-2** (`synapse_solaris_assemble_chain`/`synapse_solaris_build_graph`/`houdini_create_point_instancer` all port in usd-2).
- **PORT-FREEZE:** usd-2 ports the set-dressing surface with the break intact (goldens assert dispatch, so the break ships loud but frozen).

### SB-6 · husk full-frame-range default — **P2** (RISK top-8; silent **cost**, not silent wrongness)

- **What happens today (doc-claim, unprobed):** husk now defaults to the stage's FULL `startTimeCode..endTimeCode` range, not 1 frame. SYNAPSE code is covered (every flow passes explicit frames — grep-verified: `handlers_render.py` `frame_range=(cur,cur)`, `render_sequence.py:224-229`), but corpus prose (`rag_render_husk_cli.md`) frames single-frame as the ambient default — a future agent-authored naked husk call now renders a 240-frame stage silently. Burns a night or a farm budget with no error.
- **Evidence:** `harness/notes/h22_doc_candidates_wave2.json` KAR-01 · wave-2 ESCALATE table.
- **Fix shape:** NOW = behavior probe (trivial 5-frame stage, no flags, count outputs — run the KAR-14 license check first per the Indie trap) + written trap-pin. Corpus default-framing re-seed rides the ratified reseed cycle.
- **Lane + wave:** NOW probe; corpus fix WAVE-COUPLED (reseed cycle). No golden freeze (no golden may perform a real render — manifest hard rule).

**Adjacent trust-hazard (registered, not a break):** `cops_analyze_render` **advertises** black-pixel/NaN/dynamic-range/noise QC it has never computed on any build — an agent receiving a "clean" analysis report believes checks ran that never did (NWS-04, `handlers_cops.py:632-710`). The fix is a NEW-CAPABILITY build (see lane 6), ranked here because **cops-1 golden-pins the phantom-QC envelope** too.

---

## 4. LANE: NOW (pre-ratification-legal)

> Paper, probes, corpus-correction specs, panel reinforcement. Nothing here needs a ratification flip. Effort: S < half a day · M = a day-ish · L = multi-day.

| # | Pri | Item | Evidence | Effort |
|---|---|---|---|---|
| N-1 | **P1** | **Live-bridge reconfirm pass.** Bring the bridge up inside an H22.0.368 GUI session (panel installed + hconfig-verified — this is the owed pass, not a new gate) and in one sitting: convert every PROVISIONAL-headless PASS (COP audit 21/21, quarantine re-pins, pdg re-audit, step-9 probes) to trusted truth; settle the 3 PENDING-BEHAVIORAL items (op:-path plane suffix semantics for `cops_to_materialx`; implicit solver-block binding — decides SB-3's fix shape; scaffold cook-through); touch `hou.secure` (GUI-only-vs-absent); run the KAR-02/KAR-03/KAR-11 parm probes and TOPS live-cook event probes. Cheapest de-risking act on the board — one flipped verdict post-golden is a freeze event. | `h22-cop-audit-verification.md` (PENDING-BEHAVIORAL + provisional protocol) · `h22-quarantine-repin.md` · `h22-pdg-perception-reaudit.md` | **M** |
| N-2 | **P1** | **KAR-14 husk license probe + signal spec.** `husk --help` grep for license/mode-forcing flags + one 1-frame husk attempt on the Indie license; record exit code + stderr. Determines whether the pinned H21 trap (husk silently no-ops on Indie, writes nothing — `handlers_render.py:529` works around it blindly) is now detectable, differently shaped, or gone. Wiring the detection into the fallback follows ratification. | `h22_doc_candidates_wave2.json` KAR-14 · memory pin synapse-h21-render-husk-indie · `handlers_render.py:529` | **S** |
| N-3 | **P1** | **KAR-08 identification probe** — which `karma:*` properties migrated to relationships (build karmarendersettings + light filter, cook, diff `GetRelationships()` vs attributes). Hython-runnable; gates the SB-4 fix design. | `h22_doc_candidates_wave2.json` KAR-08 | **S** |
| N-4 | **P1** | **COP solver-block behavioral probe** (PENDING-BEHAVIORAL #2: do Cop blocks bind implicitly without `blockpath`/`method`?) + per-tool remediation spec for the SB-3 class. Rides N-1 — headless cannot answer it. | `h22-cop-audit-verification.md` tools #11/#13/#14/#17 | **S** (once bridge is up) |
| N-5 | **P1** | **Solaris layout-successor catalog probe** — full LOP nodetype-catalog scan for layout-shaped successors (name/label/HDA) to feed the human gate-2 ruling with evidence instead of memory. | `verified_connectivity_H22.json` diff.removed · drop-execution OPEN #1 | **S** |
| N-6 | **P2** | **KAR-06 MaterialX probe** — FIRST assert the 4 SYNAPSE-emitted mtlx names (`mtlxstandard_surface`/`mtlximage`/`mtlxgeompropvalue`/`mtlxnormalmap`, `handlers_material.py:465-598`) still exist post-1.39.5, THEN diff the full `mtlx*` set vs the H21 catalog (the 8 new-type internal names are guesses until this runs). Clears or breaks the whole material surface before **usd-2** ports it. | `h22_doc_candidates_wave2.json` KAR-06 | **S** |
| N-7 | **P2** | **KAR-01 husk frame-range probe + trap pin** — 5-frame stage, flag-less husk, count outputs; license check (N-2) first, same husk session; write the trap-pin (docs/memory, same mechanism as the PyEventHandler warning). | `h22_doc_candidates_wave2.json` KAR-01 · `rag_render_husk_cli.md` | **S** |
| N-8 | **P2** | **KAR-03 parm-default probe** — `karmarendersettings`/`usdrender_rop` picture/outputimage defaults: does the delegate-name default appear at parm level? Re-verifies two pinned assumptions: the BL-007 synthesized-default path (`handlers_render.py:~431`) and the "productName does NOT author the prim" pin (`solaris_compose_tools.py:55`). Wrong pins = false render-verification results (quiet operator-trust erosion). | `h22_doc_candidates_wave2.json` KAR-03 · wave-2 ESCALATE | **S** |
| N-9 | **P2** | **KAR-13 color-pipeline probe + correction spec** — `PyOpenColorIO.GetCurrentConfig()` (expect ACES 3.0-era) + `imaketx --help` grep (`--opaque-detect`, 16-bit-float). `aces_color_management.md:25` pins the ACES 1.3-era `.ocio` filename — **actively wrong**, an agent following it authors a silently wrong color pipeline; `--opaque-detect` alpha-stripping will get chased as a "lost alpha" bug. Spec the corpus correction now; the rag/ edit rides review/reseed. | `h22_doc_candidates_wave2.json` KAR-13 · `rag/skills/houdini21-reference/aces_color_management.md:25` | **S** |
| N-10 | **P2** | **KAR-02 pixel-filter parm probe** — `parmTemplateGroup()` scan of both render-settings LOPs: confirm Pixel Filter **Size** absent / **Scale** present + `karma_pixelfilterclamp` survival (corpus `pipeline_preferences.md` documents the removed parm; `common_errors.md`/`render_farm.md` set the clamp). Rides N-1. | `h22_doc_candidates_wave2.json` KAR-02 | **S** |
| N-11 | **P3** | **`scripts/rewire_assess.py:40` DEFAULT_VCC fix** — hard-points at uninstalled H21 `vcc.exe`; derive from `--houdini-exe`/`HYTHON`. One-line dev-tool fix that **unblocks the only verification gate for the 18 new H22 VEX functions** (NWS-11/12 — never dir()-table-verifiable; any corpus seed before the vcc probe violates phantom discipline). | drop-execution OPEN #3 · `h22_doc_candidates_wave2.json` NWS-11/NWS-12 | **S** |
| N-12 | **P3** | **NWS-11/12 vcc probes** (after N-11) — `vcc --list-context` grep for `usd_bindmaterial` + 17 others; any name absent stays doc-only, never seeded. | `h22_doc_candidates_wave2.json` NWS-11/NWS-12 | **S** |
| N-13 | **P3** | **Panel: guard `chat_panel.py:499`** — the last unguarded `menu.exec_()` (deprecated PySide6 alias under Qt 6.8.3); copy the `hasattr(menu, "exec")` pattern from the four guarded sites in `synapse_panel.py` (:940/:972/:1089/:1432 — warden-verified). Panel work is pre-ratification-legal. | drop-execution OPEN #3 · warden §2 | **S** |
| N-14 | **P3** | **Panel: touch-target floor** — the only live G3 WARN on H22 ("interactive targets: 22 found, 13 under 26px [WARN]", verbatim). Sizing approach (padding vs hit-area expansion) is a taste decision — **needs the human's call before fixing** (warden item 2). | warden §1 Run B verbatim | **S–M** |
| N-15 | **P3** | **Panel: cyan reconciliation** — 9 live call sites render legacy cyan `#00D4FF` from `panel/tokens.py` (conn dot, command palette, context bar, HDA views, quick actions, error translator, recipe book, apex recipes) against the ONE-accent (#8FB3D9) law. This IS the 3-source gremlin: reconcile only with full `pytest tests/` green (deliberate test pin at `panel/tokens.py:75` — "panel cyan ≠ designsystem accent — pinned by test_hda_panel"), **never naively**. Fold in the 6 stale "cyan" docstrings (`styles.py`) + the `message_formatter.py:39` duplicated `#8FB3D9` literal. | warden §3 + roadmap items 3/5/6 | **M** |
| N-16 | **P3** | **`audit_panel.py` stale H21 hython pointer** — the gate tool's no-PySide help text still points at `Houdini 21.0.671\bin\hython.exe` (uninstalled). Post-drop doc drift inside the gate itself; owner-level fix (outside warden's edit scope). | warden §1 side finding | **S** |

**NOW lane count: 16 items** (7 probe/paper, 4 panel, 2 dev-hygiene, 1 session, 2 spec).

---

## 5. LANE: WAVE-COUPLED

> Items riding U.1-H22 ratification or a specific port sub-wave from `docs/PORT_WAVE_MANIFEST.md` (dispatch order: scene-1 → scene-2 → usd-1 → usd-2 → render → tops-1 → tops-2 → cops-1 → cops-2 → memory-1 → memory-2). Port waves must not "fix" any of these themselves — behavior change is never a port (manifest non-goals).

| # | Pri | Item | Rides | Evidence |
|---|---|---|---|---|
| W-1 | **P1** | **NWS-03 planes() migration** — 2 call sites (`handlers_cops.py:446,684`) → `cable()`/`layer()` + corpus fix `copernicus_python_api.md:315`. **Must land before or with `cops-1`** (SB-1 PORT-FREEZE). | doc-candidate ratification + merge gate → before **cops-1** | SB-1 |
| W-2 | **P1** | **U.1-H22 connectivity fold** — SCAFFOLD phase updates the packaged catalog (`connectivity_21.json` → H22 truth) so `cops_connect` wiring is provably runtime-true; kills the Cop/light miswire class. Explicitly gated in `flywheel_queue.json` (cycle U.1-H22, `status: candidate`, `ratified: false`). | **human gate 1** → adjacent to **cops-1** | SB-2 · `verified_connectivity_H22.json` follow_up_feeds |
| W-3 | **P1** | **instancer→pointinstancer rename + layout successor repair** — all emitting sites in one ratified fix + live create+cook test; do NOT half-fix. | **human gate 2** → before **usd-2** | SB-5 |
| W-4 | **P1** | **COP solver-block re-authoring** (SB-3 class: simulate mode, block binding, limit→clamp, quantize levels) — fix shape decided by N-4's behavioral probe; one ratified cycle across the 4+ tools. | N-4 probe → before **cops-1** (`create_solver`) + **cops-2** (growth/RD/wetmap/stylize) | SB-3 |
| W-5 | **P1** | **KAR-08 relationship-aware `get/set_usd_attribute`** — extend the read path to `GetRelationships()` + author relationships; scoped by N-3's identification probe. | own ratification → before **usd-1** | SB-4 |
| W-6 | **P2** | **Stale-corpus purge bundle (`houdini22-reference` re-seed):** ACES 1.3 config (KAR-13, actively wrong), husk single-frame default framing (KAR-01), Pixel Filter Size recipe (KAR-02), planes() COP recipe (rides W-1). scout/knowledge_lookup re-teach every one of these each agent turn until purged — code/corpus divergence rule, both or neither. Probes N-7/N-9/N-10 sharpen the seeds first. | ratified corpus-reseed cycle (rag/ edits via normal merge review) | `h22_doc_candidates_wave2.json` KAR-13/01/02 · wave-2 ESCALATE |
| W-7 | **P2** | **KAR-03 pin corrections** (only if N-8 flips a pin): synthesized-default path in `handlers_render.py:~431` and/or the productName trap comment in `solaris_compose_tools.py:55`. | N-8 probe → before **render** wave golden capture | `h22_doc_candidates_wave2.json` KAR-03 |

**WAVE-COUPLED lane count: 7 items.**

---

## 6. LANE: NEW-CAPABILITY

> Feature candidates needing their **own ratification** (flywheel NEW_MCP_TOOL discipline; entries stay `ratified:false`). Each carries the moat rationale and the probe that must pass first. Moat frame (adjudication, G4): the announced first-party APEX MCP is a rigging-scoped, not-yet-shipped preview ("preview… released later" — single-outlet, deferral corroborated by five silent official surfaces); SYNAPSE's four differentiation columns — **in-process perception events · undo-wrapped mutation · provenance · substrate memory** — remain unoccupied by anything announced. Position complementary, never competing (D-H22-1).

| # | Pri | Item | Moat rationale | Probe that must pass first | Evidence |
|---|---|---|---|---|---|
| C-1 | **P2** | **NWS-04 — `hou.ImageLayer` pixel statistics in `cops_analyze_render`** | Receipts honesty: implement the black-pixel/NaN/dynamic-range checks the docstring has always advertised and never computed; turns COP render analysis into a real perception receipt. Same call sites as W-1 — **sequence into the same cycle** so handlers_cops.py is touched once. | `computeAverage/Min/Max` live call on a cooked COP layer (all 10 symbols table-VERIFIED; confirm no disk I/O) | `h22_doc_candidates_wave2.json` NWS-04 · `handlers_cops.py:632-710` |
| C-2 | **P2** | **SOL-04 — reversible pxr-authoring tool** (pythonscript-LOP + `editableStage()`) | Deepest direct deepener of the reversibility/consent column: a consent-gated, undo-wrapped, IntegrityBlock-producing USD authoring path replacing CRITICAL-gate raw `execute_python` for set-dressing. Exactly the surface the announced APEX MCP does not touch. Idiom already live internally (`handlers_usd.py`). | Already probe-VERIFIED on 22.0.368 (pythonscript LOP + editableStage + stage) — remaining gate is ratification + merge | `h22_doc_candidates.json` SOL-04/SOL-07/SOL-09 |
| C-3 | **P3** | **COP-01 — neural COP tools** (`cops_segment_mask` SAM2 / `cops_estimate_depth` MoGe-2) **with the COP-02 precondition encoded** | Loudest new Copernicus surface in a lane with zero first-party MCP competition; mattes + depth are weekly artist reach. **Must ship WITH the truth:** nodes silently produce empty masks until models are downloaded ($SHFS) + a GPU execution provider exists (COP-02) — otherwise the new tool ships its own silent-wrongness mode. Bundle the NWS-05 `hou.OpenCLDevice` preflight into `synapse_doctor` as part of the tool's honesty, not garnish. | Node class runtime-VERIFIED (`neural_layertomask_sam2`/`neural_layertodepth_moge2`/`denoiseai` live in 'Cop'); remaining probes: live SAM2 node parm scan (model/provider parms), $SHFS model-presence check, NWS-05 device-list accessor locate | `h22_doc_candidates.json` COP-01/COP-02 · `h22_doc_candidates_wave2.json` NWS-05 · wave-1 ESCALATE #2 |
| C-4 | **P2** (silent-noop floor) | **COP scaffold rebuild cluster** — `cops_procedural_texture` / `cops_stamp_scatter` / `cops_bake_textures` (+ stylize toon/posterize levels) on the modern Cop surface | Every stamp/frequency/resolution/levels setting silently does nothing today (bare scaffold nodes — tools #12/#16/#18/#20). Honesty bound: no H21 parm baseline exists; some were no-ops pre-drop too. Modernization targets probe-confirmed (`bakegeometrytextures::2.0`, native RD block pair, `usdmaterial`, `slapcompimport`). Texture baking is weekly work. | Scaffold cook-through probe (PENDING-BEHAVIORAL #3, rides N-1); then per-tool rebuild spec | `h22-cop-audit-verification.md` #12/#16/#18/#20 · manifest cops-2 trap ("porting must not 'fix' the scaffold into a cook — separate, ratified feature") |
| C-5 | **P3** | **TOPS-02 + TOPS-05 — per-work-item perception telemetry** (`WorkItemCookPercentUpdate`, `WorkItemOutputFiles`, `lastState`/`currentState` transitions + `supportedEventTypes` runtime gate) | Directly deepens the in-process perception-events column in the PDG lane; `tops_monitor_stream` is already push-based — this makes farm receipts granular. TOPS-05 = the dir()-gate philosophy applied to events (kills silently-never-firing registrations). **Phantom already caught:** `pdg.GraphContext.workItemById` is table-ABSENT — use `pdg.Graph.workItemById`. R8 surface confirmed intact on H22 (pdg re-audit 4/4). | Live-cook event-behavior probe (worker-thread + emitter-support confirmation) — rides N-1 | `h22_doc_candidates_wave2.json` TOPS-02/TOPS-05 · `h22-pdg-perception-reaudit.md` |
| C-6 | **P3** | **TOPS-08 — `tops_manage_service`: PDG Services warm-session lifecycle** (`pdg.ServiceManager`) | The native lever against the ~2s Houdini cook floor (latency-roadmap conclusion); competitive-numbers edge vs the "token-efficient" APEX MCP marketing (adjudication claim 11 → G6 measured numbers gain urgency). `handlers_tops/cook.py:150-156` rejects every non-local scheduler today; `pdg.ServiceManager` appears nowhere in SYNAPSE code. | `dir(pdg.ServiceManager)`/`dir(pdg.Service)` verb-surface probe before designing the tool | `h22_doc_candidates_wave2.json` TOPS-08 |
| C-7 | **P3** | **SOL-02 — Prune-LOP tool** (reversible-by-construction prim deactivation) | Literal reversibility differentiation: deactivation-not-deletion means the revert path is native to the op, composing with the undo/provenance envelope. Genuine tool gap. | Already probe-VERIFIED (`prune` LOP exists on 22.0.368) — remaining gate is ratification | `h22_doc_candidates.json` SOL-02 |
| C-8 | **P3** | **KAR-05 — husk resume controls** (`--skip-existing-frames` / `--karma-percent-of-samples` / `--error-summary`) into `synapse_render_sequence`/`render_progressively` | Real weekly value rendering solo: a crashed overnight render restarts from frame 1 today (zero resume vocabulary at `_tool_registry.py:1053,1097`). Failure here is loud and merely expensive — hence below the silent classes. | `husk --help` flag probe (bundle with N-2/N-7 in one husk session) | `h22_doc_candidates_wave2.json` KAR-05 |
| C-9 | **P3** (merge-rule tail: no judge lens carried it top-8; surfaces here because it is wave-2 TOP-10 #8 and a genuine tool gap) | **KAR-04 — RenderPass prims + `husk --pass` multi-pass rendering** | Render-orchestration lane: `synapse_configure_render_passes` authors `UsdRender.Var` prims only — **zero `UsdRender.Pass` usage anywhere in `python/synapse`** — so SYNAPSE speaks only half the H22 RenderPass vocabulary. Authoring real Pass prims under `/Render` + driving multi-pass husk invocations extends the render-receipts surface; natural cycle-mate of C-8 (same husk wiring). | Schema half: `UsdRender.Pass.Define` on an in-memory stage (hython, NOW-legal; all 4 schema symbols — `Pass`/`Define`/`CreateRenderSourceRel`/`CreateInputPassesRel` — already table-VERIFIED). CLI half: `husk --help` grep for `--pass` — **bundle into the same husk session as N-2/N-7/C-8** (CLI flags are never table-verifiable; the gate is `--help` output). | `h22_doc_candidates_wave2.json` KAR-04 · `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` TOP-10 #8 · doc: https://www.sidefx.com/docs/houdini22.0/news/22/karma.html |

**NEW-CAPABILITY lane count: 9 items.** (KAR-14's detection *wiring* is the follow-on to N-2 and folds into the render-recipe cycle rather than a tenth entry.)

---

## 7. HUMAN GATE CHECKLIST

One line each on what flipping it unblocks.

1. **Ratify U.1-H22 in `flywheel_queue.json`** — unblocks the SCAFFOLD phase that folds the probed H22 connectivity catalog into the packaged truth: kills the Cop/light miswire class (W-2) and re-arms wiring-drift detection for every future build.
2. **Solaris layout-LOP successor ruling** — unblocks the multi-site set-dressing repair (W-3); N-5's catalog probe feeds it; until ruled, `assemble_chain`/`build_graph` recipes stay hard-broken on H22.
3. **Merge `feat/h22-drop-execution` → master** — lands the H22 symbol table, cp313 re-vendor, panel install hygiene, and Wave-0 suite honesty on master; every ratified fix cycle and every port wave stacks on this merge.
4. **OD-1/2/3 rulings in `docs/PORT_WAVE_MANIFEST.md`** — OD-1 sub-wave enum (recommended (b): the workflow `wave` enum edit is human/forge scope), OD-2 wrap-vs-reimplement (recommended (a): wrap), OD-3 the 4 WS-exception tools (propose/instantiate_graph, undo/redo — recommended (b): pass-through). No wave dispatches until ruled + manifest merged.
5. **`hou.secure` live-bridge reconfirm** — the one quarantine verdict carrying a GUI caveat (headless can't distinguish absent from GUI-only-lazy; `hou.text`/`hou.qt` calibration proves the blind spot is real); until the live touch, the auth resolver does **not** auto-adopt (`h22-quarantine-repin.md`). Rides N-1.
6. **`hou._imagePlanes` private-API ruling** — SCOUTMASTER call: it is the ONLY plane-listing API on 22.0.368 (public `imagePlanes` absent; `imageDepth` is an enum, not a reader) but underscore-private — quarantined from production emission pending the ruling (`h22-cop-audit-verification.md` step-9 QUARANTINE #4).
7. **C2 rider version bump** — the adjudication's one escalation: C2's text ("no public evidence of a first-party MCP/agent surface") needs a rider now that the APEX MCP preview is announced (rigging lane, deferred); human + CTO decide rider vs closure-as-designed (`docs/intake/adjudication-h22-release-notes.md` claim 3).
8. **Ratify the doc-candidate / silent-break fix cycles + the corpus-reseed cycle in `flywheel_queue.json`** — gate 1 covers ONLY U.1-H22 (the SB-2 connectivity fold). The fix cycles this roadmap's own P1s ride are **separate `ratified:false` entries**: W-1 (planes migration — the board's #1 item), W-4 (solver-block re-authoring), W-5 (KAR-08 relationship reads, before usd-1), W-6 (stale-corpus purge), and every NEW-CAPABILITY entry (C-1–C-9). A human flipping gates 1–7 alone still leaves SB-1/SB-3/SB-4's fixes blocked — this flip is what unblocks them.

---

## 8. ESCALATIONS CARRIED

Every `escalate:true` item from both candidate files, deduped (14 flags → 13 lines; NWS-03 = wave-1 HOM-02).

| ID(s) | One line |
|---|---|
| **NWS-03 / HOM-02** | `hou.CopNode.planes` removed → live silent `planes:[]` data loss at `handlers_cops.py:446,684` + stale corpus recipe; migration surface fully verified — **P1, SB-1, rides cops-1**. |
| **KAR-08** | karma/husk schemas migrated strings → relationships; `get/set_usd_attribute` blind to them — **P1, SB-4, probe NOW, fix before usd-1**. |
| **KAR-14** | husk licensing system changed — chance to make the Indie silent-no-render trap detectable (or learn its new shape) — **P1, probe N-2**. |
| **KAR-01** | husk default flips to FULL stage frame range — flag-less agent-authored calls silently multi-frame; probe + trap-pin + corpus reframe (SB-6). |
| **KAR-02** | Pixel Filter Size parm removed → Scale; corpus recipe stale; `karma_pixelfilterclamp` survival unconfirmed — probe N-10, reseed W-6. |
| **KAR-03** | Default output naming gains delegate name — two pinned path assumptions (`handlers_render.py:~431`, `solaris_compose_tools.py:55`) need re-verification — probe N-8. |
| **KAR-06** | MaterialX 1.39.5 bump — the 4 hardcoded mtlx type names SYNAPSE emits are the rename/retire exposure — probe N-6 before usd-2. |
| **KAR-13** | ACES 3.0 + linear mipmaps + imaketx 16-bit float + `--opaque-detect` — `aces_color_management.md` actively teaches the 1.3-era config — probe N-9, purge W-6. |
| **TOPS-01** | Doc names the event wrapper `pdg.EventHandler`, SYNAPSE says `PyEventHandler` — doc-identity drift only (both classes table-present both builds; pdg re-audit re-confirmed raw-callable registration + wrapper on H22); fix docs after the live probe. |
| **NWS-01** | 5 `hou.Node` base-class removals (copyNetworkBox etc.) — zero callers repo-wide, COVERED; phantom guard already current (subclass forms survive). |
| **NWS-02** | `hou.ChannelEditorPane` → `hou.ChannelEditor` — zero callers, COVERED; emit only the new name. |
| **COP-01** | Neural Copernicus class is real and genuinely new (runtime-confirmed) — signals the scope of the same rewrite that removed `planes()`; capability rides C-3. |
| **COP-12** | Copernicus category key: probe RESOLVED the escalation — `Cop` is live and distinct from legacy `Cop2`/`CopNet`; `handlers_cops.py` already distinguishes them; guard stays. |

---

## 9. CLOSING

This roadmap is paper. It mutates nothing — no code, no catalog, no corpus, no queue. Every fix, tool, and reseed named above enters through its own gated cycle; all flywheel entries stay `ratified:false` until the human flips them; port waves dispatch only after the ratify + manifest gates; merges are human, per commit. Docs are intent, probes are truth, and where this document and the live H22 runtime disagree, the runtime wins.
