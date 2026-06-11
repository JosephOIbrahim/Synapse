# Scaffolding Solaris & Copernicus Knowledge for Houdini 21 — From First Principles

**A deep review of SYNAPSE's Solaris/Copernicus surface + a grounded, self-healing knowledge-scaffold design.**

> Date: 2026-06-08 · Target: Houdini 21.0.631 / 21.0.671 · SYNAPSE v5.11.0 (panel v9.0.0)
> Method: 5-agent codebase+RAG map → 3-angle scaffold design → adversarial crucible. Every claim below is cited to `file:line`; claims the crucible could not verify are marked **[unverified]**.

---

## 0. Executive summary

The instinct behind "scaffold knowledge from first principles" is right, but the gap is **not a documentation gap** — the repo already ships a rich, modern Solaris/Copernicus corpus. The gap is a **missing arbiter**. Three artifacts disagree about reality and nothing reconciles them:

1. **What the code does** — the `cops_*` handlers build **legacy COP2** node types (`cop2net`, `vopcop2gen`) and emit **non-compiling OpenCL** (`#define`-only, no `@KERNEL` body) → all-black output. Zero of it is verified on H21.
2. **What the repo RAG documents** — the **modern Copernicus** surface (`copnet`, `fractal_noise`, `opencl` with `#bind`/`@KERNEL`). The handlers contradict the repo's own knowledge base.
3. **What H21.0.631/671 actually is** — **unknown**: all 45 COPs tests are mock-based ("bridge down"), so no node type is confirmed to exist, cook, or render.

**The first-principles move** is to build the one thing none of the three has: a **verified node-type/kernel catalog** that carries per-fact provenance (`doc_only → V0_membership → V1_cook → flipbook_pixel_verified`) and acts as the single source of truth that **corrects** the code, **corrects** the docs, and is **CI-gated** so they stay converged. Crucially, **the engine to do this already exists and is already driven live for APEX** (`scripts/run_apex_verify.py`) — the work is to point it at COPs, not to build it.

**Highest-ROI slice (ship this first, in order):**
1. A **V0 conformance test** that source-scans `handlers_cops.py` for `createNode('<phantom>')` and fails CI on `cop2net`/`vopcop2gen` — *catches the divergence today, with no live build*.
2. **Fix the OpenCL emitters directly** (`handlers_cops.py:1010-1019`, `1101-1108`) — replace `#define`-only with the canonical `#bind`+`@KERNEL` template. *Self-contained; turns 3 dead tools into cooking ones.*
3. `cops_probes.py::COPS_SEED` + a generalized live driver (`require_second_seed=True`, control-type guard) → promote the catalog `V0 → V1` on real 631/671 builds.

Everything else (handler migration, doc correction, Moneta seeding, Solaris gap-fill) is evidence-led follow-on, gated on that catalog.

---

## Part I — Current state (the deep review)

### I.1 Solaris / USD / LOP / Karma — broad and mostly verified-live

SYNAPSE exposes **~26 USD/LOP/stage/Karma tools** across six handler files, all in one registry (`handlers.py:459-546`). Two authoring paradigms coexist:

- **Legacy tier — pythonscript LOPs** (`handlers_usd.py`): authoring runs as generated `pythonscript` LOP code where `hou.pwd().editableStage()` is valid *in-cook*. Covers prim/attr/variant/collection/light-linking/instancer/payload. Force-cooks to surface errors.
- **Compose tier — native nodes+parms** (`solaris_compose.py` + `solaris_compose_tools.py`): a phantom-guarded `create_lop`, real-file sublayer department stacks, read-back via `node.stage()`. Cleaner, reusable primitive layer.

The render surface is deep: 24-parm advanced-Karma map, 17 AOV presets, progressive/safe/farm renders, OIIO pixel QC (`handlers_render.py`). **The H21 gotchas are encoded in code and verified-live on 21.0.671**, not merely doc-claimed (see Appendix A).

**Solaris capability gaps** (what H21 can do that SYNAPSE can't):

| Gap | Evidence |
|---|---|
| **Inherits / Specializes** arcs — only L/V/R/P of LIVRPS covered | `handlers_usd.py` (no inherit/specialize tool) |
| **Variant edit-content** authoring (empty variants only, no `UsdEditContext` over-composition) | `handlers_usd.py:829-879` |
| **Layer flatten / export / save-sublayer** | compose tier creates dept `.usd` but no flatten/export command |
| **Value clips** (animation-clip stitching) | absent |
| **Full point-instancer** (orientations/scales/ids/velocities) | `handlers_usd.py:1437-1527` (positions+protoIndices only) |
| **RenderVar → RenderProduct.orderedVars** wiring | `handlers_render.py:901-1054` defines RenderVars but never attaches them to the product |
| **MaterialX node-graph depth** (triplanar, mix/blend, color-correct chains) | `handlers_material.py:440-633` (standard maps only) |
| **Light creation** (only *linking* exists) | `handlers_usd.py:1066-1185` |
| **Component Builder** asset authoring (purposes/proxy/variants) | only an ordering-table hint |

### I.2 Copernicus / COPs — wide, legacy-built, and unverified

SYNAPSE ships **21 `cops_*` tools** in one mixin (`handlers_cops.py`), dispatch fully wired (`handlers.py:594-620`). **The wiring is complete; the capability is not H21-grounded:**

- **Legacy node names.** `cops_create_network` builds `cop2net` (`handlers_cops.py:64`); `procedural_texture`/`bake`/`wetmap`/`stamp_scatter` build `vopcop2gen` (the legacy VOP COP2 generator). Only `cops_create_copnet` (`:90-153`) uses the modern `copnet` — and its docstring **defers verification** ("bridge down").
- **Non-functional OpenCL.** `cops_reaction_diffusion` (`:1010-1019`) and `cops_pixel_sort` (`:1101-1108`) emit only `#define` preambles — **no `@KERNEL{...}` body, no `#bind` decls**. Per the repo's own doc, this is the documented "Result is all black" failure (`copernicus_opencl_reference.md:399-403`).
- **Over-promising read tools.** `cops_analyze_render` / `cops_temporal_analysis` advertise pixel/NaN/flicker metrics but only inspect `node.errors()` + cook status — no `allPixels()` reads.
- **Zero H21 verification.** All 45 COPs tests are mock-based (`tests/test_cops.py:10`, `tests/test_forge_copernicus.py:8-11`). Nothing confirms any COP type resolves, cooks, or renders on 21.0.631.

The doc preamble fed to agents (`mcp_tools_cops.py:9-11`) *actively steers toward the legacy path* ("creates a COP2 container").

### I.3 The two RAGs — and which one is canonical

There are **two** knowledge stores, and they are very different:

| | `G:\HOUDINI21_RAG_SYSTEM` | repo `rag/skills/houdini21-reference/` |
|---|---|---|
| Index source | **SideFX Labs only** (803 HDA entries) | 96 `.md`, 129 indexed topics |
| Core Solaris | one 90-line **self-labeled stub** (`lop-solaris.md`) | `solaris_nodes/parameters/instancing/variants/...md` |
| Copernicus | **stale legacy-COP2** (`cops_compositing.md`: `/img`, `cop2net`, per-scanline); modern `cop/` names appear only as Labs *deprecation breadcrumbs* | **modern** `copernicus_python_api.md` (`copnet`, `fractal_noise`, `opencl`), `copernicus_opencl_reference.md` (`#bind`/`@KERNEL`/`@ix`/`@xres`), `copernicus_solver_patterns.md`, `copernicus_interop_pipelines.md` (`op:` live-texture paths) |

**Decisive fact:** `_get_knowledge_index` **defaults `rag_root` to the repo `rag/`**, *not* G: (`handlers.py:1381-1384`). The repo RAG is canonical; the `G:` store is the thinner, staler one. The standing belief that "recall reaches G:" only holds if `SYNAPSE_RAG_ROOT` is set. **The modern Copernicus knowledge the handlers should be using already lives in the repo RAG.**

### I.4 The scaffold infrastructure already exists (corrected)

> **Crucible correction to the initial map:** the science loop is **NOT** "zero live callers." `scripts/run_apex_verify.py:83` already calls `run_search(APEX_SEED, registry, ...)` against a live namespace built by `_build_namespace()` (`:39-69`, which enumerates `hou.nodeTypeCategories()`). The harness has a working live driver and catalog dump **for APEX**. The COPs task is *generalize it*, not *build the first one*.

| Component | What it gives | Status |
|---|---|---|
| **KnowledgeIndex** (`routing/knowledge.py:34-462`) | 4-strategy RAG retrieval, <500ms, no LLM; wired to recall/search via `handlers_memory.py::_augment_with_knowledge` | recall→RAG seam **closed + test-pinned** |
| **Science Harness** (`science/probe.py`, `loop.py`, `registry.py`) | pure `dir()`/catalog-membership `probe(namespace, ProbeSpec)`; `run_search` second-seed gate; `Registry` dedup + `deposit_fn` seam | live driver exists for **APEX only**; seeded only by `apex_probes.py`; `deposit_fn` never wired to a real sink |
| **Ledger** (`memory/ledger.py`) | append-only provenance, mandatory `verified_by` (V0/V1), per-record JSON SoT + agent.usd projection | built, ratified |
| **seed_corpus.py** | Moneta REFERENCE/SHOW pointer seeding | **filters to `'vex'` only** (`:64`) — Solaris/COPs not seeded |
| **Recipes** | `routing/recipes/*` (`RecipeRegistry`, **MCP-visible** via `synapse_list_recipes`) vs `panel/recipe_book.py` (richer dicts, **panel-only**) | two non-unified families |
| **Live introspection** | `synapse_inspect_stage` (Pydantic `StageAST`), `network_explain` | verified-live |

**Remaining seams:** the chat router (`TieredRouter` via `_handle_route_chat`) builds its `KnowledgeIndex` with `RoutingConfig.rag_root` defaulting to **`None`** — so chat-routing's Tier-1 lookup is **RAG-blind** (`router.py:104,178-181`). This is distinct from the (closed) recall/search seam.

---

## Part II — The core problem: a missing arbiter

The pathology is a **three-way divergence with no source of truth**:

```
   handler code            repo RAG (canonical)        live H21.0.631/671
   cop2net, vopcop2gen      copnet, fractal_noise,      ??? (unverified —
   #define-only OpenCL      opencl + #bind/@KERNEL       all tests mock-based)
        │                        │                            │
        └───── disagree ─────────┴──────── unverified ────────┘
                         (nothing reconciles them)
```

Each artifact drifts independently because none can check itself against ground truth. Writing *more* docs doesn't fix this — the good docs already exist and the code ignores them. **What's missing is a verified catalog that all three check against, and a CI latch that keeps them checking.**

---

## Part III — First-principles design: the provenance lattice

### III.1 The thesis (validated by the crucible)

> Knowledge for an agent operating a **live DCC** must be a **layered, provenance-carrying** model where each layer is independently verifiable, and a single engine promotes facts up the provenance ladder.

**The four layers:**

| Layer | What | Stored / verified by |
|---|---|---|
| **L0 — Primitives** | Which node types + module APIs actually exist | `science/probe.py` catalog-membership vs a live `hou.nodeTypeCategories()` dump → `Registry` JSONL → Ledger |
| **L1 — Composition** | USD LIVRPS arc semantics; the COP OpenCL kernel contract (`#bind`/`@KERNEL`) | V1-cooked: `createNode(...)`, `node.cook(force=True)`, assert `not node.errors()` — gated by L0 |
| **L2 — Operations** | Parameterized recipes = verified node graphs achieving an intent | `routing/recipes/RecipeRegistry`; a recipe is green only if every node type is an L0 champion + its kernel cooks |
| **L3 — Intent** | NL → operation/recipe + canonical doc | `KnowledgeIndex` (already wired) + Moneta pointers (`seed_corpus`) |

**The provenance ladder** — every fact carries exactly one rung, and the report's hard rule is *never assert above the rung you've reached*:

```
doc_only  →  V0_membership  →  V1_cook  →  flipbook_pixel_verified
(prose)      (catalog dump)    (cooks,     (Karma-interactive pixel
                                no errors)   sample — GUI only)
```

> **Crucible must-fix #1:** the render rung is **flipbook_pixel_verified, NOT "EXR written."** On the verified Indie license `husk`/`usdrender_rop.render()` **silently no-ops** (`verify_compose_render.py:18-44`) — an EXR-on-disk gate is *unobtainable*. The only working render-verify is a Karma-interactive flipbook + pixel sample.

### III.2 Why this is "first principles," concretely

The lattice is grounded *because* L0 is a live catalog dump, not doc prose. This is the exact lesson the codebase already paid for: **`APEX_SEED` originally shipped fictional `apex::rig::`/`apex::sop::` node names invented from docs, and was only corrected after a human dumped the live 5811-type catalog** (`apex_probes.py:9-34`). A knowledge scaffold that seeds node names from `copernicus_python_api.md` prose **repeats that failure**. Hence the Floor rule below.

---

## Part IV — The build plan (winning approach: CONVERGE)

Of three designs, the crucible named **CONVERGE** strongest: it treats the divergence as a missing-arbiter problem, makes migration *evidence-led*, ships value before any live build, and reuses the existing driver. The plan below is CONVERGE with all crucible must-fixes folded in.

### Phase 0 — value with no live build (ship first)

**0.1 V0 conformance test** — `tests/test_cops_catalog_conformance.py`. Source-scan `handlers_cops.py` for `createNode('<literal>')` and fail CI if a created type is on the known-phantom blacklist (`cop2net`, `vopcop2gen`) with no champion replacement. Pattern already used across the `phase0c` pin tests. **Catches the divergence today, no Houdini required.** Effort: **M**.

**0.2 Fix the OpenCL emitters directly** — `handlers_cops.py:1010-1019` (reaction_diffusion) and `:1101-1108` (pixel_sort). Replace the `#define`-only string with the canonical template from `copernicus_opencl_reference.md`: `#bind layer src?/!dst` + `#bind parm` + a real `@KERNEL{...}` body. Self-contained, waits on no catalog, **turns 3 non-cooking tools into cooking ones**. Effort: **M**. *(Highest correctness ROI in the whole plan.)*

### Phase 1 — the verified catalog (grounding)

**1.1 `python/synapse/science/cops_probes.py::COPS_SEED`** — modeled on `apex_probes.py`:
- `expect='absent'` for `cop2net`, `vopcop2gen` (falsify the handlers' legacy names),
- **`expect='unknown'`** for every modern name (`copnet`, `opencl`, `fractal_noise`, `color_correct`, `over`, `ramp`, `rop_comp`, solver pair).

> **Crucible must-fix #2 (Floor violation in waiting):** do **NOT** seed modern names as `expect='present'`. They come from doc prose and are unconfirmed — seeding them `present` is the APEX fictional-name failure mode. They become `present` only *after* the dump. Effort: **M**.

**1.2 Generalize the existing driver** — lift `run_apex_verify.py::_build_namespace` into a shared catalog builder, add `scripts/run_cops_verify.py` calling `run_search(COPS_SEED, registry, probe_fn, require_second_seed=True)`.

> **Crucible must-fix #3 (false-DEAD_END hole):** `loop.run_search` holds **champions** until a 2nd seed; **`dead_end`s record on the first seed, unguarded** (`loop.py:54-61`). An empty/mis-filtered catalog makes `probe()` return `present=False` for *everything* → a flood of false dead_ends. **Before recording any `expect='absent'` falsifier, assert the catalog is non-empty and contains a known-present control type (e.g. `null`).** And `require_second_seed=True` is **opt-in** — `run_apex_verify` opts *out*, so the gate is inert unless explicitly wired and run on **two real builds (631 + 671)**, seeding the second run's confirmed-set from the first. Effort: **M**.

**1.3 Guarded deposit adapter** — wire `Registry(deposit_fn=adapter)` so each verdict lands in the Ledger.

> **Crucible must-fix #4:** `ledger.deposit()` (note: `deposit`, not `append`) **throws on empty `verified_by`** (`ledger.py:267-269`), and `registry.record()` calls `deposit_fn` with **no try/except** (`registry.py:86-87`) — a non-V1 deposit **aborts the search loop mid-flight**. The adapter must (a) compute `verified_by` from run context (V1 only when the catalog is real/non-empty; otherwise skip the deposit, don't crash) and (b) be wrapped so any deposit failure is logged, never propagated. This is the genuine close of the `deposit_fn=None` gap. Effort: **S**.

### Phase 2 — reconciliation (evidence-led, gated on Phase 1)

**2.1 Migrate handler node names** off the phantoms, keyed to confirmed champions: `cop2net → copnet`; `vopcop2gen → ` its confirmed replacement at the ~9 sites. **Do this only after the catalog confirms targets** (membership ≠ role-fit — `apex_probes.py:35`).

> **Crucible must-fix #5:** renaming breaks the 45 mock tests (`test_cops.py`, `test_forge_copernicus.py` assert the *old* strings). Update them **in lockstep** and let the cook-verification test become the real gate. Effort: **M**.

**2.2 Doc corrections — a *different artifact* from the code fix.**

> **Crucible must-fix #6:** there is **no `createNode('usdrender')` in handler code** (grep-clean across `python/synapse/server/`). The phantom `usdrender` lives only in the RAG doc `solaris_nodes.md:508,711`; the handlers (`handlers_usd.py:1257,1280`) already tolerate both names read-side. **Fix the doc, not the handler.** Separately, reframe/split the stale `G:\...\cops_compositing.md` (legacy `/img`/`cop2net`) so it is never authoritative.

**2.3 Close L3** — lift the `seed_corpus.py:64` `'vex'`-only filter to an allow-set including `cop`/`copernicus`/`solaris`/`karma`; add corrected COP pointer entries. **First verify** `semantic_index.json` actually holds those topic keys — if it's vex-keyed only, the lift is a no-op until the index is regenerated, and the report should say so. Also wire `_handle_route_chat` to pass a resolved `rag_root` into `RoutingConfig` (one line) to close the chat-router RAG-blind seam. Effort: **S**.

### Phase 3 — Solaris parallel track

Solaris handlers are mostly verified-live, so the scaffold's Solaris value is different:
- **Same machinery, `SOLARIS_SEED`** — confirm the LIVRPS arc node types + the `usdrender` phantom (which lands as the *doc* fix above).
- **Fill the I.1 gaps as L2 recipes + L0/L1 facts**: Inherits/Specializes, value clips, full point-instancer, RenderVar→Product wiring, Component Builder, light creation, MaterialX graph depth.
- The compose tier (`solaris_compose.py`) is the clean primitive to build new authoring tools on — do not re-emit raw pythonscript strings.

### Build-order summary

```
Phase 0  (no Houdini)   0.1 V0 conformance test     [M]  ← catches divergence today
                        0.2 fix OpenCL emitters     [M]  ← 3 dead tools → cooking
Phase 1  (live 631/671) 1.1 COPS_SEED (unknown!)    [M]
                        1.2 generalized driver      [M]  ← + control-guard + 2 builds
                        1.3 guarded deposit adapter [S]  ← closes deposit_fn=None
Phase 2  (evidence-led) 2.1 handler migration       [M]  ← + lockstep mock tests
                        2.2 doc fixes (NOT code)    [S]
                        2.3 seed_corpus + chat seam [S]
Phase 3  (parallel)     SOLARIS_SEED + gap recipes  [L]
```

---

## Part V — Floor guardrails (the non-negotiables)

These are the things that, if violated, reproduce a failure the codebase has *already* paid for:

1. **Seed un-dumped modern names as `expect='unknown'`, never `present`.** (Repeats APEX fictional-names.)
2. **Guard every `expect='absent'` record** with a known-present control type, or an empty catalog writes false dead_ends.
3. **`require_second_seed=True` + two real builds (631 + 671).** The gate is opt-in and inert otherwise; it did *not* catch APEX's fictional names — a human catalog reconcile did.
4. **Wrap the deposit adapter**; compute `verified_by` from real run context. An unguarded `deposit()` throws and aborts the loop.
5. **Render-verify = flipbook pixel sample, not EXR.** EXR-on-disk is unobtainable on the Indie license.
6. **`usdrender` is a doc fix; `cop2net`/`vopcop2gen` are code fixes.** Different artifacts — don't conflate them.
7. **Migration breaks mock tests** — update in lockstep; treat the cook test as the real gate.
8. **Membership ≠ role-fit.** "`copnet` exists" does not mean it cooks or has the parms a handler sets — that's L1, a separate rung.
9. **`KnowledgeLookupResult` has no `provenance_status`** (`knowledge.py:21-31`) — provenance-aware retrieval ranking is net-new plumbing, not "reuse."

---

## Appendix A — Verified H21 gotcha ledger (encoded + live-confirmed on 21.0.671)

| Gotcha | Where | Status |
|---|---|---|
| `editableStage()` is `None` outside a LOP cook; author via pythonscript LOP / nodes+parms, read via `node.stage()` | `solaris_compose.py:20-21,90` | verified-live |
| `usdrender` is **phantom** (only `usdrender_rop`); compose path swaps it, older handlers tolerate both read-side | `solaris_compose.py:46-47`; `handlers_render.py:53,80`; `handlers_usd.py:1257,1280` | verified-live |
| `husk` **no-ops on Indie** — render writes nothing, no error → flipbook fallback | `handlers_render.py:381-423`; `verify_compose_render.py:18-44` | verified-live |
| `karmarendersettings.productName` parm does **not** author the RenderProduct prim (BL-007) — needs a pythonscript LOP | `solaris_compose_tools.py:52-64,155-160` | verified-live |
| sublayer LOP composes `filepathN` **strongest-last** (inverse of raw USD `subLayerPaths`) | `solaris_compose_tools.py:112-118` | verified-live |
| `set_usd_attribute` has **no typed coercion** (`attr.Set(repr(value))`) — Gf types fail at cook | `handlers_usd.py:382-388` | verified-live |
| OpenCL `#define`-only kernels (no `@KERNEL`/`#bind`) → **all-black** | `handlers_cops.py:1010-1019,1101-1108`; `copernicus_opencl_reference.md:399-403` | confirmed bug |
| `configure_light_linking` does **not** force-cook its LOP (errors deferred) | `handlers_usd.py:1173-1183` | verified-live |

## Appendix B — Open questions requiring the live probe (the V0 dump)

Until `scripts/run_cops_verify.py` runs on 631/671, these are **`doc_only`** and must not be asserted:

1. The **real Copernicus node-type category name** (`Cop2` vs a Copernicus-specific category) and the exact membership strings (versioned suffixes? e.g. `apex::autorigcomponent::2.0`-style).
2. Whether `copnet`, `opencl`, `fractal_noise`, `color_correct`, `over`, `ramp`, `rop_comp`, `block_begin/end` resolve on 21.0.631.
3. The **real OpenCL parm name** — handlers try `kernelcode`/`code`; `copernicus_python_api.md:111` says `kernelcode`, but it is **[unverified]** on a live `opencl` node.
4. Whether the modern generators (`fractal_noise` etc.) **cook error-free** with a minimal kernel (L1).
5. The `op:` MaterialX live-texture path form — node-NAME output (`op:/stage/copnet/OUT_albedo`) vs the handler's plane-suffix form `op:{path}/{plane}` (`handlers_cops.py:409-411`).

> The bridge was up briefly this session (panel verify succeeded) but the WS server is unstable and kept dying. **Running the catalog dump is Step 0 of grounding — not an appendix afterthought.** Everything in Phase 1+ is `doc_only`/`V0` until it runs.

---

*Method note: produced by a 5-agent codebase+RAG map (611k tokens), a 3-angle scaffold-design panel, and an adversarial crucible pass that re-read `science/probe.py`, `handlers_cops.py`, `routing/knowledge.py`, and `copernicus_opencl_reference.md`. The crucible overturned six claims in the initial synthesis (notably "zero live callers" and the EXR render gate); those corrections are folded into Parts I, III, IV, and V above.*
