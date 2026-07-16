# H22 SideFX-CTO Lens — 2026-07-16

> **Vendor's-eye synthesis pass over the H22 drop-week evidence set.** This document is paper. It mutates nothing.
> One question: *what did H22 change that these authors probably didn't notice, and that bites one or two releases from now?*
> Lane: **synthesis across artifacts the siloed scouts produced in isolation + first-principles vendor knowledge.** Not the assayer, not the doc-scout, not the crucible. Where a domain scout already caught a thing, it is marked *already covered* and dropped.

---

## Provenance

**Date:** 2026-07-16 · **Target build:** Houdini 22.0.368 (py 3.13.10 / USD 0.26.5 / PySide 6.8.3) · **Branch:** `feat/h22-drop-execution` (unmerged)

**Headless-PROVISIONAL note:** the live WS bridge was DOWN for the entire drop week; every runtime fact I lean on is either (a) a committed symbol-table entry (install-determined, headless-safe) or (b) a PROVISIONAL-headless probe from the artifacts below. No finding here upgrades a PROVISIONAL verdict — I inherit their tier. My own two symbol-table diffs (`h21_symbol_table.json` vs `h22_symbol_table.json`) are exact-equality on committed data: both tables are `truncated:false`, identical `depth {hou_pdg:2, pxr:1}` and `node_cap 300000`, so the added/removed sets are trustworthy at the depth captured.

**Artifacts read (cross-referenced, not re-derived):**

| Artifact | What I took from it |
|---|---|
| `docs/reviews/h22-cto-roadmap-2026-07-16.md` | The current plan. I EXTEND its lanes (NOW / WAVE-COUPLED / NEW-CAPABILITY / DEFER); I contradict nothing without probe evidence. |
| `harness/notes/verified_connectivity_H22.json` | 288-type node-wiring diff; Lop instancer/layout "removed"; Cop/light 3→8 miswire class |
| `docs/reviews/h22-cop-audit-verification.md` | 21 COP tools, 11 PASS / 10 CHANGED / 0 GONE; per-tool Cop2-vs-Cop surface truth |
| `docs/reviews/h22-doc-intel-2026-07-16-wave2.md` | Karma/TOPs/news deltas (KAR-*, TOPS-*, NWS-*) |
| `docs/reviews/h22-now-probes-2026-07-16.md` | N-2/N-3/N-5/N-6/N-7/N-8/N-9/N-10 live-headless probe results |
| `docs/intake/adjudication-h22-release-notes.md` / `-sidefx-h22-memo.md` | Vendor WHY: "COP Network - Old", APEX-MCP scope, OpenGL/Qt5 removal, Copernicus scope |
| `python/synapse/cognitive/tools/data/h21_symbol_table.json` + `h22_symbol_table.json` | The +3055 / −407 delta (I sampled it directly for Lens 7) |
| `shared/evolution.py`, `python/synapse/server/handlers_cops.py`, `python/synapse/routing/recipes/*` | Live SYNAPSE seams for the cross-references below |

**Ground rule inherited:** Rigging / KineFX / APEX is a structural non-goal. I note vendor movement there only as boundary-pressure context (§Lens 7), never as a recommendation.

---

## Lens 1 — Deprecation trajectory

### F1 · SYNAPSE's COP scaffold tools are pinned to the vendor-designated-sunset "COP Network - Old" surface — VERIFIED

**Evidence.** SideFX's own H22 docs demote the classic compositing network in so many words: *"Though both networks still exist, the Compositing network is now designated as `COP Network - Old`"* (`adjudication-sidefx-h22-memo.md` (d) sub-claim 1, quoted verbatim from `heightfields_cop/index.html`). That legacy surface is exactly `cop2net` / `vopcop2gen` / `Cop2Node`. The COP audit shows SYNAPSE leans on it hard: **six tools require the legacy surface for their primary function** — `cops_create_network` (→`cop2net`, #1), `cops_composite_aovs` (→`cop2net`, #8), `cops_procedural_texture` (`vopcop2gen` **Cop2-only**, #12), `cops_stylize` (`edge` **Cop2-only**, #16), `cops_bake_textures` (`vopcop2gen` **Cop2-only**, #18), `cops_stamp_scatter` (`vopcop2gen` **Cop2-only**, #20). The audit records that `vopcop2gen` **RAISES** inside the modern `copnet` container — so these tools are *structurally* pinned to the sunset surface, not merely defaulting to it. Grep confirms the density: **26 `cop2net`/`vopcop2gen`/`Cop2Node` references in `python/synapse/server/handlers_cops.py`.**

**What the domain scouts missed (why it's non-obvious).** The COP audit measured **present state, per tool**: legacy-removal contingency "did NOT fire", `Cop2Node.planes()` still works, verdict CHANGED not GONE. Correct — for this release. The CTO projection the per-tool lens can't make: **the vendor has published removal intent** ("COP Network - Old"), and the moment a future major retires `cop2net`, those six tools flip **CHANGED → GONE simultaneously** — from silent-no-op to hard-raise. That reframes roadmap **C-4** (the scaffold-rebuild cluster) from "rebuild because parms no-op today" into "**migrate off a substrate the vendor has flagged for removal**" — a moat-preservation deadline, not a cosmetic fix. It also widens C-4's scope: C-4 lists `procedural_texture`/`stamp_scatter`/`bake_textures`/`stylize`, but `create_network` and `composite_aovs` sit on the *same* sunsetting `cop2net` and belong in the same register.

**SYNAPSE seam.** `python/synapse/server/handlers_cops.py` (26 legacy refs; tools #1/#8/#12/#16/#18/#20). **Suggested lane:** extends **C-4 (NEW-CAPABILITY)** — add a legacy-surface dependency register to the honesty bound and re-scope C-4 as trajectory-driven migration. Not urgent (contingency didn't fire), but it should be *named* so it isn't rediscovered as an emergency next major.

*Other Lens-1 signals checked, already covered:* Qt5→Qt6 (`menu.exec_()` alias — roadmap N-13); OpenGL→Vulkan (adjudication claim 7 → G2; no direct Python-OpenGL seam in SYNAPSE — the viewport path is flipbook/`hou.*`, not GL). Nothing new there.

---

## Lens 2 — Rename intent

### F2 · The layout→paintinstances + instancer→copytopoints renames encode an instancing REORG — and the "official rename" is the wrong programmatic target — VERIFIED

**Evidence (all from `h22-now-probes-2026-07-16.md` §N-5).** Two renames, alias-backed, confirmed live: `Lop/layout` → **`Lop/paintinstances`** ("The Layout LOP is now named Paint Instances LOP", `solaris.txt` L137; `opalias Lop paintinstances layout`; 41/42 parms survive, **`method` dropped**) and `Lop/instancer` → **`Lop/copytopoints`** ("The Instancer LOP was renamed to Copy to Points", L143; 39/41 parms, `allowmissingprototypes`/`protooptionsgroup` dropped). Plus a genuinely-new third node: **`Lop/scatterinstances`** (`#since: 22.0`, *render-time Hydra generative procedural*, 167 parms) and a new `Lop/pointinstancer` (create+edit).

**What the domain scouts missed.** N-5 established both as clean 1:1 renames and correctly recommended "emit canonical new spellings, not the alias table." What it did **not** draw is the *reorg the rename pattern encodes*: H22 has split the old monolithic layout/instancer surface into an **intent-typed** family — `copytopoints` (deterministic, point-driven, scriptable), `paintinstances` (**interactive brush**, GUI-first — note the dropped `method` parm and the `layoutbrush*` SOP lineage), and `scatterinstances` (render-time, generative). SYNAPSE authors set-dressing **headless, from an agent** — so the semantically-correct successor for programmatic scatter is **`copytopoints`** (or `scatterinstances` for render-time), **not** the literal `paintinstances` rename of `layout`. A naive alias-following swap `layout → paintinstances` in the set-dressing recipes lands the agent on the brush-oriented node whose primary interaction model (paint) an agent can't drive, and whose dropped `method` parm any old emit path would still try to set.

**SYNAPSE seam.** The node-emit path — `server/solaris_graph_templates.py:393`, `server/handlers_solaris_assemble.py:54,69` (per roadmap SB-5) — not the recipe path (`routing/recipes/scene_recipes.py` already authors scatter via **raw USD `PointInstancer` schema**, which is rename-immune; the `layout*` hits there are all `layoutChildren()` graph-tidy calls, not the Layout LOP). **Suggested lane:** feeds **human gate 2** and **W-3 (WAVE-COUPLED)** — the gate-2 ruling should choose successors *by intent* (`copytopoints`/`scatterinstances`), not adopt the `paintinstances` alias by default. This **extends** SB-5/W-3; it does not contradict them.

---

## Lens 3 — Backend-precision drift

### F3 · SYNAPSE is structurally blind to backend-precision drift — reassuring today, a coverage hole the moment a real-numeric receipt ships — VERIFIED

**Evidence.** H22 ships a stack of no-API-change numeric shifts: Vulkan-only (OpenGL removed) + GPU subdivision, **ACES 2.0** CG-config (was ACES 1.3; N-9: `cg-config-v3.0.0_aces-v2.0_ocio-v2.5`, OCIO 2.5.0, default view `Un-tone-mapped`), **mipmaps now computed in linear space**, **MaterialX 1.39.5** (N-6: OpenPBR family present), imaketx changes. Each of these moves pixel/material/render values with no symbol delta. I checked SYNAPSE's exposure two ways: (a) the port-wave manifest's hard rule is **no golden may perform a real render**, so render goldens are structural (envelope/dispatch), not numeric; (b) the test suite runs **mock-`hou`** (the fake-residency pattern — sys.modules planted `hou` fakes), so **no test computes real Houdini numerics in CI** — the 235 numeric assertions across 28 test files are harness logic (scoring, allocation, frame-range integers), not pixel/VEX/geo-intrinsic output.

**The finding is the *conjunction*.** Existing exposure to backend-precision drift is genuinely **zero** (nothing to break — good). But that same architecture means backend-precision is a **wholly untested axis**: the instant **roadmap C-1** ships (real `hou.ImageLayer.computeAverage/Min/Max` pixel statistics in `cops_analyze_render`), SYNAPSE emits its first backend-sensitive *receipt* with no drift-detection harness behind it — and ACES 2.0 / linear mipmaps / MaterialX 1.39.5 are exactly the changes that would make those numbers move between builds while the envelope stays "clean". A receipt that says "average luminance 0.42" is only honest if 0.42 is reproducible; on a mock-`hou` CI it can't be checked. **This is a testing-architecture caveat on C-1**, not a defect in current code.

**SYNAPSE seam.** `python/synapse/server/handlers_cops.py:632-710` (`cops_analyze_render`, the C-1 target) + the CI test architecture (mock-`hou`). **Suggested lane:** attach to **C-1 (NEW-CAPABILITY)** as an acceptance note — any numeric receipt needs a tolerance-based fixture probe run under real hython, not a CI equality golden. **DEFER** the broader "real-numeric test harness" until a numeric receipt actually ships.

---

## Lens 4 — Cross-domain blast radius

### F4 · USD 0.26.5 is adjudicated as a Solaris/Karma concern, but it also underlies the agent.usd provenance substrate — the moat — whose fidelity==1.0 round-trip was never probed on H22 — INFERENCE (symbol-survival VERIFIED)

**Evidence that 0.26.5 is a non-trivial bump.** My symbol diff surfaces **unannounced OpenUSD module churn** that hit no what's-new page: **`pxr.Ndr` is entirely removed** (101 symbols → **0**, folded into `pxr.Sdr` 213 → 330), and **`pxr.Usd.ZipFile`/`ZipFileWriter` relocated to `pxr.Sdf.ZipFile`/`ZipFileWriter`**. So 0.26.5 reorganized modules, not just versioned. SYNAPSE touches neither (grep for `pxr.Ndr`/`pxr.Sdr`/`Usd.ZipFile` = zero hits) — those are honest nulls — but they establish that a USD major-ish bump landed under the hood.

**The cross-domain thread the siloed scouts never pulled.** Every artifact treats USD 0.26.5 as Solaris authoring (KAR-08, N-3) or a build fact. **No drop-week probe touched `shared/evolution.py` or `python/synapse/memory/agent_state.py`** — yet the Pokémon-model memory pipeline authors USD through the *same* `pxr` stack: `Usd.Stage.CreateInMemory`, `Tf.MakeValidIdentifier`, `Sdf.ValueTypeNames.{String,StringArray,Asset}`, `Vt.StringArray`, `GetRootLayer().ExportToString()` (`evolution.py:40,480-550`). I confirmed **all of those symbols survive on H22** — so the risk is **not** removal; it is **behavioral round-trip drift** (USDA serialization formatting, identifier sanitization edge cases, array/asset value handling) that the symbol table cannot see. And here is the sharp edge: evolution's VERIFY stage is a **`fidelity == 1.0` exact-equality gate** (companion.md round-trip diff; on <1.0 it **deletes the USD, preserves markdown, and aborts** — CLAUDE.md §6). This is **the only in-process exact-equality assertion SYNAPSE runs against real live `pxr` output.** If 0.26.5 drifted the round-trip even slightly, memory **silently refuses to evolve past Charmander** on H22, with no error surfaced to the artist — and the `memory-2` port wave would golden-pin whatever H22 produces as the contract.

**Why this is the highest-leverage item on my board.** It is the only *unowned, cheap, NOW-legal* probe that touches SYNAPSE's stated #1 differentiator (provenance/reversible memory), and its failure mode is a **silent abort** class — exactly the shape of thing the roadmap's own energy thesis says to catch before the goldens freeze. Every scout looked at Karma/COP/Solaris; the memory substrate sat in the blind spot between them.

**SYNAPSE seam.** `shared/evolution.py` (VERIFY/round-trip), `python/synapse/memory/agent_state.py` (agent.usd SCHEMA 2.0.0). **Suggested lane:** **NOW-probe** — run the evolution pipeline end-to-end under H22 hython on a fixture markdown (≥5 structured items to trip a real Charmander→Charmeleon evolve), assert `fidelity == 1.0`; if it drifts, that is a pre-`memory-1`/`memory-2` blocker, not a port-wave concern. **Confirms/refutes** by direct execution — the probe *is* the resolution.

---

## Lens 5 — Licensing / deployment shift

### F5 · The husk-Indie refutation removed H21's safety-by-no-op; combined with two other covered deltas it becomes a new agent-authored disk hazard — VERIFIED (compound of covered facts)

**Honest framing:** the headline deployment change — husk on Indie no longer silently no-ops — is **already covered** (N-2: the H21 trap is REFUTED, husk renders real EXRs on Indie, exit 0). I am not re-reporting it. The CTO addition is the **compound** that no single artifact states:

- **N-2:** on H21, an agent-authored *naked* husk call on Indie did **nothing** (silent no-op, zero output) — accidentally safe.
- **KAR-01 / N-7:** on H22, a flag-less husk call renders the stage's **full** `startTimeCode..endTimeCode` range (5-of-5 frames confirmed live with no `-f`/`-n`).
- **N-7 trap 2:** the default `productName` writes to **`$HIP/render/untitled.<node>.NNNN.exr`** — i.e. into the working/repo directory unless `-o` overrides.

Multiply them: **an agent-authored naked husk call that H21 rendered harmless now actively multi-frame-renders into the repo directory.** SYNAPSE's *own* flows are safe (they pass explicit frames and `-o` — grep-verified, per SB-6), so this is not a code break. The exposure is **corpus-shaped**: `rag_render_husk_cli.md` still frames single-frame as the ambient default, so a future agent following the corpus inherits the hazard. This sharpens **SB-6** (which frames the risk as farm *cost*) with the concrete new axis: **uncontrolled disk writes into the working tree**, and it strengthens the case for the W-6 corpus reseed to carry an explicit "always pass `-o` and an explicit frame flag" trap-pin, not just a frame-range note.

**SYNAPSE seam.** Corpus `rag/.../rag_render_husk_cli.md` (default-framing prose) + `handlers_render.py:529` (the now-retirable Indie fallback). **Suggested lane:** folds into **W-6 (corpus reseed)** + **N-2 wiring** — no new lane, a sharpened trap-pin.

*Other Lens-5 signals checked, no new exposure:* macOS Apple-Silicon-only (SYNAPSE's macOS CI runs the pure-Python suite, not Houdini — unaffected); py 3.13.10 / possible 3.11 build (the **sidecar** survival rule already handles interpreter split — adjudication gate-0.1, and this vindicates the posture rather than threatening it). The announced first-party APEX MCP is boundary-pressure, already adjudicated (C2 rider) — not mine to re-litigate.

---

## Lens 6 — Fragile success

### F6 · SYNAPSE has zero opalias awareness — alias-backed emits are silent time-bombs, and the U.1 connectivity probe's `nodeType()` lookup manufactures alias-masked false "removed" verdicts — VERIFIED

**Evidence.** N-5 proved `stage.createNode('layout')` **SUCCEEDS** on H22 (→ `Lop/paintinstances`) purely because `opalias Lop paintinstances layout` ships in `$HFS/houdini/OPcustomize` — while `hou.nodeType(lopCat,'layout')` returns **`None`** (the alias applies at *creation*, not *type lookup*). That single fact has two edges the scouts saw only half of:

1. **False-negative in the harness probe.** `verified_connectivity_H22.json` `diff.removed[2].note` asserts *"createNode('layout') in a LOP net will fail on H22"* — **REFUTED by N-5.** The U.1 connectivity probe (`host/introspect_connectivity.py`) decides membership via `nodeType()`, which ignores aliases, so it will keep reporting **alias-backed nodes as removed/broken when they still work.** N-5 caught this for `layout`; it is a **class**, not a one-off.
2. **Silent time-bomb in the emit path.** The mirror risk: any node SYNAPSE emits that resolves **only** through an opalias works today and **breaks silently the release SideFX retires the alias** (aliases are a migration courtesy, typically pulled 1–2 majors after a rename). SYNAPSE has **no opalias awareness anywhere** (grep `opalias` across the repo = zero), so it cannot distinguish "resolves natively" from "resolves via a courtesy alias about to expire."

**What the scouts missed.** N-5 handled the `layout` instance and correctly said "emit canonical spellings." The generalization — *the harness's membership oracle is alias-blind in both directions, and there is no mechanism to enumerate the exposed class* — is a harness-architecture finding, not a per-node one. It is cheap to close.

**SYNAPSE seam.** `host/introspect_connectivity.py` (nodeType-based membership) + `python/synapse/cognitive/tools/data/emitted_node_types.json` (the emit surface) + the `verified_connectivity_H22.json` diff notes. **Suggested lane:** **NOW-probe** — grep `$HFS/houdini/OPcustomize` for every `opalias Lop|Cop|Sop <new> <old>`, cross-reference against `emitted_node_types.json`, and enumerate exactly which SYNAPSE emits are alias-propped (i.e. work today, expire later). Feeds the **gate-2** connectivity-note correction (generalizing N-5's `layout` correction) and hardens the U.1 SCAFFOLD phase.

### F7 · The guard-everything defensive style converts H22 API removals into *silent* no-ops — structurally against the receipts-honesty thesis — VERIFIED

**Evidence.** SB-1 is the archetype: `CopNode.planes()` is gone, both call sites are `try/except(AttributeError)`-guarded, so the tool returns `planes:[]` with a **clean envelope and zero error**. The COP audit shows this is not one bug but a **pattern** — `limit`→`clamp` alias (max/high absent → threshold set "silently no-ops"), `block_end.method`/`blockpath` absent (simulate mode "silently no-ops"), `quantize` levels absent (toon/posterize "silently no-op"), Cop/light index miswire (wrong input, "cooks clean"). Every one is a `try/except` or None-guard that **degrades to silent-empty instead of raising.**

**The non-obvious synthesis.** The same defensive-guard discipline that makes SYNAPSE *robust* across the sidecar/standalone/production modes is precisely what makes its **receipts dishonest on a major version bump** — the product whose entire differentiator is "every operation recorded and true" has a codebase-wide idiom that **hides drift behind a passing envelope.** That is the deepest form of the roadmap's own energy thesis, stated as an *architectural class* rather than a list of tools: the guards need to **surface** a provenance warning (a degraded `IntegrityBlock` fidelity note) when a load-bearing symbol is absent, not swallow it. This is the difference between "fidelity 1.0, planes:[]" (a lie) and "fidelity <1.0, symbol `planes` absent on this build" (a receipt).

**SYNAPSE seam.** `handlers_cops.py` guard sites (446/684 and the parm-optional chains); the `IntegrityBlock` fidelity mechanism (`shared/bridge.py`) is the natural place to route a "guarded-degradation" signal. **Suggested lane:** a **NEW-CAPABILITY** hardening candidate — make guarded-optional degradations emit a fidelity-<1.0 provenance note instead of a silent empty result. Ranks below the concrete silent-break fixes (SB-1..SB-5 fix the *instances*); this fixes the *class* and stops the next major re-introducing it.

---

## Lens 7 — Unannounced delta

**Checked systematically; net-new SYNAPSE exposure: none.** I diffed the full committed symbol tables (+3055 / −407, both untruncated). Findings, honestly tiered:

- **New top-level `hou.*` classes (16):** all but four are already scout-covered (`CopCable`, `DetachedAttrib`, `Camera`, `CameraPrim`, `OpenCLDevice`, `ChannelEditor`, the `UniNode*` family, per NWS-02/03/05/10 + adjudication claim 10). The uncovered remainder — `hou.ApexUniGraphDebugger`, `hou.UniNode`/`UniNodeType`/`UniNodeTypeCategory`/`UniNodeConnection`/`UniStickyNote` — are the **APEX unified-graph** infrastructure (boundary-pressure context, **non-goal**, note-only); `hou.ChannelListPaneTab`, `hou.ViewerDragger2D`/`ViewerHandleDragger2D`/`ViewerStateDragger2D` are GUI/viewer-state SDK with no SYNAPSE seam.
- **Unannounced OpenUSD module reorg (VERIFIED, zero SYNAPSE exposure):** `pxr.Ndr` fully removed (101 → 0, folded into `pxr.Sdr` 213 → 330); `pxr.Usd.ZipFile`/`ZipFileWriter` relocated to `pxr.Sdf.ZipFile`/`ZipFileWriter`. **SYNAPSE imports neither** (grep clean) — honest nulls. The one forward-looking note (folded into F4): these prove USD 0.26.5 is a structural bump, which is *why* the unprobed memory round-trip (F4) matters. If a future material-discovery capability reaches for the shader registry, it must use `pxr.Sdr`, not `pxr.Ndr`, on H22.

Lens 7 produced no standalone finding — the delta was real but examined and clear. Reporting that is the point; a manufactured "unannounced" finding would be dishonest.

---

## Top findings (most load-bearing first)

| Rank | Finding | Lens | Tier | Lane | One-line stakes |
|---|---|---|---|---|---|
| **1** | **F4** — agent.usd/evolution USD round-trip never probed on H22 | 4 | INFERENCE (symbols VERIFIED) | NOW-probe | The moat's only exact-equality gate, unprobed on a structurally-churned USD; failure = silent memory-evolution abort + a frozen `memory-2` golden. Cheapest de-risk on my board. |
| **2** | **F6** — zero opalias awareness; alias-blind membership + expiring-alias emits | 6 | VERIFIED | NOW-probe | The connectivity oracle lies in both directions; a whole class of emits works today and expires silently. Cheap enumeration closes it. |
| **3** | **F2** — layout/instancer rename encodes an instancing reorg; `paintinstances` is the wrong headless target | 2 | VERIFIED | WAVE-COUPLED (gate 2 / W-3) | Gate-2 ruling should pick successors by intent (`copytopoints`/`scatterinstances`), not adopt the brush-node alias. |
| **4** | **F7** — guard-everything idiom turns H22 removals into silent no-ops | 6 | VERIFIED | NEW-CAPABILITY | Fixes the *class* behind SB-1..SB-5; makes receipts honest across the next major, not just this one. |
| **5** | **F1** — COP scaffold tools pinned to the vendor-sunset "COP Network - Old" | 1 | VERIFIED | extends C-4 | Six tools flip CHANGED→GONE together the release `cop2net` is retired; re-scope C-4 as trajectory-driven migration. |
| **6** | **F3** — backend-precision is a wholly untested axis (caveat on C-1) | 3 | VERIFIED | attach to C-1 / DEFER | No current exposure, but C-1's real pixel receipts ship with no drift harness. |
| **7** | **F5** — husk safety-by-no-op gone → agent-authored naked husk now writes multi-frame into the repo dir | 5 | VERIFIED (compound) | folds into W-6 | Corpus trap-pin: always `-o` + explicit frame flag. |

---

## Proposed flywheel candidates

> Ready-to-deposit specs for the human ratification gate. **I do not write these into `harness/state/flywheel_queue.json`** — the orchestrator hands them to the human; all stay `ratified:false`.

```
CTO-01  (kind: verification_probe · ratified:false · lane: NOW-probe · pri: P1)
  title: agent.usd / memory-evolution USD round-trip probe on H22.0.368
  what:  Run shared/evolution.py end-to-end under $HYTHON on a fixture markdown
         (>=5 structured items to trip a real Charmander->Charmeleon evolve);
         assert the VERIFY-stage fidelity == 1.0. Confirms the moat's only
         in-process exact-equality gate against live pxr survives USD 0.26.5.
  seam:  shared/evolution.py (VERIFY/round-trip), python/synapse/memory/agent_state.py
  evidence: docs/reviews/h22-sidefx-cto-lens-2026-07-16.md#F4 ; symbol-survival
         VERIFIED (h22_symbol_table.json: Tf.MakeValidIdentifier / Vt.StringArray /
         Sdf.ValueTypeNames.{String,StringArray,Asset} / Usd.Stage.CreateInMemory
         all present); USD module churn evidence (pxr.Ndr removed, ZipFile relocated)
  gate:  precedes memory-1 / memory-2 port waves; a <1.0 result is a merge blocker.
```

```
CTO-02  (kind: verification_probe + harness_hardening · ratified:false · lane: NOW-probe · pri: P1)
  title: opalias-dependency enumeration + alias-aware membership for U.1
  what:  Grep $HFS/houdini/OPcustomize for every 'opalias Lop|Cop|Sop <new> <old>';
         cross-ref against emitted_node_types.json; list every SYNAPSE emit that
         resolves ONLY via a courtesy alias (works now, expires later). Feed the
         gate-2 correction of verified_connectivity_H22.json diff.removed notes
         (generalize N-5's layout correction). Optional follow-on: teach
         host/introspect_connectivity.py to record alias-vs-native membership.
  seam:  host/introspect_connectivity.py ; emitted_node_types.json ;
         harness/notes/verified_connectivity_H22.json (diff.removed notes)
  evidence: docs/reviews/h22-sidefx-cto-lens-2026-07-16.md#F6 ;
         h22-now-probes-2026-07-16.md#N-5 (opalias layout proof; note REFUTED)
```

```
CTO-03  (kind: recipe_change · ratified:false · lane: WAVE-COUPLED (gate 2 / W-3) · pri: P1)
  title: instancing-reorg-aware successor selection for programmatic set-dressing
  what:  When gate 2 rules the layout/instancer successors, map by INTENT for the
         headless-agent context: deterministic scatter -> copytopoints; render-time
         generative -> scatterinstances (#since 22.0). Do NOT default-adopt the
         paintinstances alias (brush/GUI successor; 'method' parm dropped). Emit
         canonical new spellings; never type-check for 'layout'/'instancer'.
  seam:  server/solaris_graph_templates.py:393 ; server/handlers_solaris_assemble.py:54,69
  evidence: docs/reviews/h22-sidefx-cto-lens-2026-07-16.md#F2 ;
         h22-now-probes-2026-07-16.md#N-5 ; extends roadmap SB-5 / W-3
```

```
CTO-04  (kind: capability_migration · ratified:false · lane: extends C-4 (NEW-CAPABILITY) · pri: P2)
  title: legacy 'COP Network - Old' (cop2net/vopcop2gen) dependency register + C-4 re-scope
  what:  Record the six tools structurally pinned to the vendor-sunset surface
         (create_network, composite_aovs, procedural_texture, stylize, bake_textures,
         stamp_scatter) as a trajectory-driven migration target, not just a
         silent-no-op cleanup. Widen roadmap C-4 to include create_network +
         composite_aovs (same cop2net substrate). Contingency has NOT fired on
         22.0.368 -- this is naming the deadline, not an emergency.
  seam:  python/synapse/server/handlers_cops.py (26 legacy refs; tools #1/#8/#12/#16/#18/#20)
  evidence: docs/reviews/h22-sidefx-cto-lens-2026-07-16.md#F1 ;
         h22-cop-audit-verification.md ; adjudication-sidefx-h22-memo.md (d) sub-claim 1
```

```
CTO-05  (kind: harness_hardening · ratified:false · lane: NEW-CAPABILITY · pri: P2)
  title: guarded-degradation -> surfaced provenance warning (honesty-of-receipts)
  what:  Make load-bearing try/except(AttributeError) and None-guard degradations
         emit a fidelity<1.0 IntegrityBlock note ("symbol X absent on this build")
         instead of returning a clean envelope with empty data. Fixes the CLASS
         behind SB-1..SB-5 so the next major bump surfaces drift instead of hiding
         it. Pairs with a C-1 acceptance note: numeric receipts need tolerance-based
         hython fixtures, not mock-hou CI equality goldens (backend-precision axis).
  seam:  shared/bridge.py (IntegrityBlock fidelity) ; handlers_cops.py guard sites (446/684 + parm chains)
  evidence: docs/reviews/h22-sidefx-cto-lens-2026-07-16.md#F7 (+#F3 for the C-1 note) ;
         h22-cop-audit-verification.md silent-no-op pattern
```

---

## Closing

This lens is paper. It contradicts nothing in the roadmap — every finding **extends** a lane already there (C-1, C-4, W-3/SB-5, W-6, gate 2, memory waves). Six of seven lenses produced a genuinely-new load-bearing finding; **Lens 7 honestly produced none** (the unannounced USD reorg is real but has zero SYNAPSE exposure). The single highest-leverage item is CTO-01: the one cheap, unowned, NOW-legal probe that touches SYNAPSE's differentiator — the provenance memory substrate — on a USD version the symbol table proves was structurally reorganized, and whose failure mode is a silent abort a port-wave golden would freeze. Docs are intent, probes are truth; where this document and the live H22 runtime disagree, the runtime wins.
