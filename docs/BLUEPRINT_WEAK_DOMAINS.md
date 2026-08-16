# SYNAPSE — Weak-Domain Production Blueprint

**Scope:** DOPs, VOPs, KineFX (moderate) · CHOPs, APEX, L-systems, Copernicus COPs (weak)
**Date:** 2026-08-16 · **Against:** SYNAPSE v5.42.x @ `C:\Users\User\SYNAPSE` · Houdini 22.0.400
**Basis:** live investigation of the repo, the local help cache, and the existing knowledge/verification infrastructure — not recall. Phase-0 probe receipts folded in.

---

## 0 · First principles — the collapse

The self-assessment reads as **seven knowledge gaps**. The investigation says it's actually **two infrastructure gaps and one boundary**, and most of the infrastructure already exists in the repo:

**FP1 — Never recall what the binary can tell you.**
Parameter names, input/output signatures, menu tokens, node type existence — the running Houdini session is the only authoritative source, and it's free to query. "Moderate on DOP parm semantics" is not a model-knowledge problem; it's the absence of a *compiled, per-build schema catalog* the agent consults before every `parm.set()`. The repo already does this ad hoc (`docs/conn_mtlx*.txt`, `docs/cop_node_parms.txt`, `.synapse/runtime_symbols.H21_0_671.json`, `host/introspect_nodetypes.py`). The blueprint makes it systematic.

**FP2 — Never assert what you haven't measured.**
This is already SYNAPSE law for renders ("unmeasured renders UNKNOWN"). The weak domains are weak precisely where that law hasn't been extended: a solver that was never cooked N frames, a kernel that was never dispatched, a rig that was never posed. Extend the UNKNOWN discipline from renders to *every* domain output kind. The scaffold markers (`"scaffolded": True, "cooked": False` + note, pinned by `tests/test_cops.py:977` and `test_m1_truth_contract.py`) are the honest half of this — the measuring half is what's missing.

**FP3 — Never promote without a golden.**
`rulebook/` (contracts, failures, fixtures, goldens, phantoms) and the `.claude/cook_probe_{sop,dop,cop,lop}.json` probes are the existing regression spine. Every tool that graduates out of scaffold status ships with a golden fixture + assertion, or it doesn't graduate.

**FP4 — Mechanics are automatable; intent is human.**
KineFX joint placement, APEX control feel, rig hierarchy taste — these are *intent*. The agent's production role there is: build the mechanical layer flawlessly (verified skeleton, initialized capture, valid graph), then **hand off at a named checkpoint**. Trying to automate intent is how rigging tools become uncanny; splitting the boundary is how they become useful.

**The collapse:** fix FP1 once (one catalog build) and every "I won't guess parm names" line in the self-assessment upgrades simultaneously. Fix FP2 once (one measurement layer) and every "creates the node but doesn't cook" line upgrades simultaneously. The seven domains then become **five short waves of domain-specific finishing work** on top of two shared substrates.

---

## 1 · Ground truth inventory — verified this session

**Documentation corpus**

| Source | Location | State |
|---|---|---|
| Help cache | `C:\Users\User\OneDrive\Documents\houdini22.0\config\Help\cache` | **Pre-parsed doc ASTs as JSON** — typed inputs/outputs (`inxform: Matrix4`), summaries, per-parm semantics, shared parm-include fragments (`nodes/dop/standard_*_parms.json`, `bullet_solver_parms.json`). Machine-readable with zero wiki-markup parsing. **Partial**: contains only visited pages (e.g. `nodes/apex/` holds 18 files, not the full callback library). Categories present: `apex, chop, cop, cop2, dop, vop, sop, lop, top, vex, …` |
| H21 RAG system | `G:\HOUDINI21_RAG_SYSTEM` | Full prior-generation corpus + semantic index + skills. The *pattern* for full-corpus extraction exists; it needs the H22 pass. |
| SYNAPSE K-track | `rag/` → `scripts/refresh_knowledge.py` (K.5) | One-command resync: dense embedding index (MiniLM) + scout BM25 corpus + K.0 baseline, with a **freshness gate** that reads RED on staleness. New domain corpora slot in here — the pipeline exists. |
| `$HFS` help zips | `C:\Program Files\Side Effects Software\Houdini 22.0.400` (probe 1, 2026-08-16) | Canonical complete corpus at `$HFS/houdini/help`. |

**Repo (what already exists — do not rebuild)**

- **Scaffold anatomy** (`python/synapse/server/handlers_cops.py`, 2,152 lines): `reaction_diffusion` already creates `block_begin`/`block_end` with **explicit solver binding** — `_bind_solver_block`, carrying the live-verified H22 note *"blockpath MOVED off block_end; implicit binding REFUTED-LIVE"* — wires an `opencl` COP between them, sets `iterations`, writes a `#define`-only kernel, and returns the honest marker. `pixel_sort` and `bake_textures` follow the same shape. **The graph topology, undo-grouping, main-thread marshaling, and binding are solved. Only kernel bodies + cook + measurement are missing.**
- **Tier ladder in embryo** (`tool_exposure`, pinned by `tests/test_phase3_exposure.py`): `doc_only` ("a promise, not surfaced") → `available` → `foreground`. Extend, don't invent.
- **Truth contracts**: `tests/test_m1_truth_contract.py` pins result shapes against implied-but-unobserved outcomes; `test_gate_fidelity_honesty_sourcepin.py`, `forge_engine_honest_signal` — the honesty enforcement layer is real and tested.
- **Introspection kit**: `host/introspect_nodetypes.py`, `introspect_cook_api.py`, `introspect_cook_truth.py`, `introspect_runtime.py`; per-build symbol dump precedent (`.synapse/runtime_symbols.H21_0_671.json` → needs an H22 sibling).
- **Harvest precedent**: `scripts/harvest_lop_catalog.py`, `mine_lop_knowledge.py`, `author_lop_knowledge_22.py` — the LOP domain already went through exactly the pipeline this blueprint generalizes.
- **APEX verify seed**: `scripts/run_apex_verify.py`, `docs/FORGE_SPEC_apex_verify_harness.md`, `tests/test_apex_provider_contract.py`, `test_apex_recipe_names.py` — a recipe/verify system exists in embryo.
- **APEX corpus adjacency**: the Houdini_Camera_Rig_System v5.0 rebuild is APEX-rigged for H22 — every working graph it produces is training corpus and golden material for Wave E.
- **Cook probes**: `.claude/cook_probe_{sop,dop,cop,lop}.json` — the probe-then-trust habit, ready to formalize.

---

## 2 · Substrate Phase 1 — the Schema Catalog

*One hython session converts every "I'd verify parm names against the live node" into "verified by construction."*

**Build** `scripts/build_node_catalog.py`, modeled on `harvest_lop_catalog.py`, output to `rag/catalog/h22.0.400/<category>.json` (build-keyed, like `runtime_symbols.H21_0_671.json`):

```python
# hython — one-time per Houdini build; regenerate on upgrade
import hou, json

for cat_name, cat in hou.nodeTypeCategories().items():
    rows = []
    for tname, ntype in cat.nodeTypes().items():
        entry = {
            "type": tname,
            "label": ntype.description(),
            "min_inputs": ntype.minNumInputs(),
            "max_inputs": ntype.maxNumInputs(),
            "parms": [],
        }
        for pt in ntype.parmTemplateGroup().entriesWithoutFolders():
            row = {"name": pt.name(), "label": pt.label(),
                   "type": pt.type().name()}
            # defaults / ranges / menu tokens+labels / conditionals where present
            for attr in ("defaultValue", "minValue", "maxValue",
                         "menuItems", "menuLabels"):
                if hasattr(pt, attr):
                    try: row[attr] = getattr(pt, attr)()
                    except Exception: pass
            entry["parms"].append(row)
        rows.append(entry)
    # write rag/catalog/h22.0.400/{cat_name}.json
```

**Domain-specific extensions:**

- **VOPs** — parm templates don't carry wire signatures. Instantiate each VOP type in a throwaway `matnet`, read `node.inputNames() / outputNames() / inputDataTypes() / outputDataTypes()`, destroy. One-time cost, thousands of types, minutes on the Threadripper. This turns the `conn_mtlx*.txt` manual probes into catalog rows — the exact workflow, industrialized.
- **APEX** — callbacks are not `hou.NodeType`s. **Dump path confirmed** (probe 2, 2026-08-16): enumerate `apex.callbackRegistry` + component/constraint/control/brush registries via `getRegistries`; extract typed ports from `apex.Signature`/`OverloadSet` → `rag/catalog/…/apex_callbacks.json`. The cache's doc-AST format (`nodes/apex/*.json`) already demonstrates the target schema: `internal`, typed `inputs_section` / `outputs_section` items.
- **CHOPs / DOPs / L-systems** — plain catalog rows suffice; the L-system SOP is one type with a large parm surface, fully covered by the dump.

**Docs join** — each catalog row gains a `doc` field by joining against the help ASTs (cache now; full corpus after the H22 RAG authoring pass through K.5). Parm-include fragments (`standard_*_parms.json`) resolve at join time so shared blocks land on every node that includes them.

**The Parm Gate** — the enforcement point that makes the catalog load-bearing. In `handler_helpers.py` (or `validation/`):

```python
def gated_set(node, parm_values: dict):
    """Reject unknown parm names BEFORE touching the node.
    On miss: raise with nearest-match suggestions from the catalog.
    On pass: set inside the existing undo-group discipline."""
```

Every handler in the weak domains routes parm writes through this. A hallucinated name becomes a **caught, self-correcting error with a suggestion**, never a silent no-op. (The `parm("kernelcode") or parm("code")` hedge in the current RD handler is the symptom this cures — **observed 2026-08-16: it's `kernelcode`; no `code` parm exists on the H22 opencl COP**.)

**Exit criteria (Mile 1–2):** catalog files exist for every category `hou.nodeTypeCategories()` returns · spot-audit 20 nodes per weak domain against the live session, zero mismatches · gate rejects a deliberately wrong parm name with a useful suggestion · K.5 freshness gate GREEN after `refresh_knowledge.py`.
**Estimate:** 2–3 sessions (dump script 1, VOP/APEX extensions 1, docs join + gate 1).

---

## 3 · Substrate Phase 2 — Cook-Verify contracts

*Extend "unmeasured renders UNKNOWN" to every output kind.*

**Measurement contracts, per output kind** (new module, e.g. `python/synapse/validation/measures.py`):

| Output kind | Measured signals | UNKNOWN when |
|---|---|---|
| Image (COPs) | resolution, channels, min/max/mean/σ per plane, non-uniformity, content hash | node never cooked |
| Sim (DOPs) | per-frame: NaN count, max ‖v‖, kinetic-energy ratio frame→frame, max strain vs rest length | fewer than N frames cooked |
| Geometry (SOP/KineFX) | point/prim counts, bbox, NaN scan, weight-normalization check | cook errored / not run |
| Channels (CHOPs) | sample count, range, variance pre/post | channel never sampled |
| Graph (VOPs/APEX) | compiles / `node.errors()` empty / graph invokes with test inputs | never compiled/invoked |

**Explosion signature (the vellum question, answered by instrument):** monotonic KE growth ratio > threshold across 5 consecutive frames, or max strain > bound, or any NaN → verdict `EXPLODING` with the offending frame and signal. No vibes.

**Tier ladder — extend the existing one.** Add a verification axis to tool metadata alongside the exposure tiers:

```
SCAFFOLD → SCHEMA_VERIFIED → COOK_VERIFIED → GOLDEN
```

Mapping: `SCAFFOLD` stays `doc_only` (already true — "a promise, not surfaced"); `SCHEMA_VERIFIED` may be `available` with disclosure; `COOK_VERIFIED`+ earns `foreground`. The agent states the tier when it reaches for a tool — the same honesty voice as the current scaffold notes, now with a ladder to climb.

**Golden harness** — formalize the cook probes: `rulebook/goldens/<domain>/…` fixtures with deterministic seeds; a hython runner (CI-able on the Threadripper) that cooks each golden and asserts its measurement contract. `tests/test_forge_copernicus.py` and friends are the seam to grow from.

**Exit criteria (Mile 3):** measures module covers all five kinds · vellum explosion detector fires on a deliberately broken golden and stays quiet on the healthy one · tier field live in the registry, disclosed in tool results · golden runner green in CI.
**Estimate:** 2 sessions.

---

## 4 · Phase 3 — Domain waves

### Wave A — Copernicus de-stub *(first: these are the named debts)*

**A1 · reaction_diffusion — author the kernel body.**
Everything around it works (blocks, binding, wiring, iterations). Remaining work:

1. **One docs lookup, not memory:** pin the H22 OpenCL COP kernel authoring contract — layer binding syntax, `@KERNEL` entry, writeback semantics — from the help AST for the `opencl` COP (visit the page once; the cache captures the AST). **Parm surface observed 2026-08-16** (27 parms): `kernelcode`, `kernelname`, `kerneloptions`, `usewritebackkernel`, `writebackkernelname` — the writeback kernel is a *parm-level contract*, which is exactly the state-carry mechanism the Gray-Scott feedback loop needs. Remaining lookup = kernel-body/binding syntax only. The binding layer already bit once (`blockpath` move, REFUTED-LIVE) — kernels get the same inspect-first treatment.
2. **Author Gray-Scott** against that contract: two-channel state (A,B), 5-tap Laplacian, `A += Da·∇²A − AB² + F(1−A)`, `B += Db·∇²B + AB² − (F+K)B`, seeded B-splat initial condition, iterate via the existing feedback block.
3. **Cook + measure:** run the block, read the output plane. Healthy Gray-Scott at the default F/k is *structured non-uniformity* — assert σ above threshold AND spatial autocorrelation in the mid-band (flat gray and white noise both fail). Golden: fixed seed, fixed iterations, stats + hash.
4. Flip the result payload: `"scaffolded"` key removed, `"cooked": True`, measured stats attached — and the truth-contract test updates from *pinning the debt* to *pinning the payment*.

**A2 · pixel_sort — the honest hard kernel.**
Span sort is genuinely awkward on GPU. Ship it in two tiers rather than faking one:

- **Tier 1 (COOK_VERIFIED fast):** threshold mask → per-row/column span segmentation → within-span sort by key (luma/hue/sat/val). If the catalog shows H22 offers a CPU/snippet COP path, a Python/CPU implementation ships first — *correct beats clever*. Verify: within every span, key values are monotonic (exact assertion, cheap to check).
- **Tier 2 (perf):** OpenCL row-parallel bitonic sort within spans. Same golden, faster cook. Only after Tier 1 is GOLDEN.

**A3 · bake_textures — catalog-first node selection.**
Copernicus grew 3D→2D rasterize/bake nodes in the 20.5+ line; **their exact H22 names and parms come from the catalog, not from memory** — this tool is the demonstration case for FP1. Wrap the shipped bake path (SOP import → rasterize/bake → output), verify by output-plane stats + UV-coverage ratio on a golden test asset.

**Also in scope:** the other `#define`-only kernels the test header lists (`growth_propagation`, `procedural_texture` variants, `wetmap`, `stylize` kernels) inherit the A1 pattern one by one.

**Done-when:** all three named stubs return `cooked: True` with measured stats, goldens green, tiers promoted, scaffold notes deleted from those payloads.
**Estimate:** 3 sessions (A1: 1 · A2 Tier 1: 1 · A3 + stragglers: 1).

### Wave B — DOPs sim doctor *(vellum first — the self-assessment's own example)*

- `vellum_setup` (cloth / hair / softbody / grain presets), every parm through the gate.
- **Cook-verify N frames** with the explosion detector from Phase 2 — the answer to *"why is this vellum constraint exploding"* becomes a measured verdict: the frame, the signal, the magnitude.
- **Remedy rulebook, docs-derived:** extract the vellum solver + constraint help ASTs (substeps ↔ stiffness stability, constraint iterations, collision thickness vs edge length, drag/damping bounds) into `rulebook/` rules **with doc citations** — encoded at build time from the corpus, applied at diagnosis time by matching the measured signature to the cited remedy. Never asserted from model memory.
- Same pattern stamps out `rbd_setup` and `pop_setup` (the bullet/RBD parm-include fragments are already in the cache).

**Done-when:** deliberately unstable golden diagnosed with correct remedy + citation; stable golden passes clean; tools COOK_VERIFIED.
**Estimate:** 2 sessions.

### Wave C — VOPs + CHOPs *(cheapest waves post-catalog)*

- **VOPs:** shader-graph builder resolves every wire against catalog signatures (typed input/output names — the industrialized `conn_mtlx*` probes). Verify: network compiles, `node.errors()` empty after cook, test-sphere material assignment cooks. Slots straight into the MaterialX cross-renderer patterns already in the skill library.
- **CHOPs:** don't boil the category — a **core-20 catalog-verified subset** (constant, channel, wave, noise, math, lag, filter, envelope, limit, trigger, count, record, geometry, object, export bindings) covers the production use cases: motion smoothing on transform channels, procedural parm drivers, bake-to-keys. Verify: numeric assertions on sampled channels (variance reduction after lag/filter; export binding resolves and drives the parm).
- **L-systems (micro-wave, folded in):** one SOP, big parm surface — fully catalog-covered. Ship a **preset library of validated rule strings** (classic bracketed systems: tree, bush, Koch, dragon), verify prim-count growth per generation on goldens.

**Done-when:** shader builder produces a compiling MaterialX network from intent; CHOP tools pass channel assertions; L-system presets golden.
**Estimate:** 2 sessions.

### Wave D — KineFX mechanical layer *(FP4 boundary made explicit)*

- **Agent-owned mechanics:** skeleton from template spec (biped/quad/prop; joints named to convention, positioned from bounding regions), capture initialization (biharmonic/proximity), `bonedeform` wiring.
- **Human-owned intent:** joint placement refinement, control shapes, hierarchy taste — the tool **ends at a named handoff checkpoint** that presents the verified mechanical state for posing.
- Verify: skeleton hierarchy valid, capture weights normalized (Σ=1 per point, measured), `bonedeform` cooks NaN-free on a test pose.

**Done-when:** template → verified deformable skeleton → clean handoff, golden per template.
**Estimate:** 2 sessions.

### Wave E — APEX recipe corpus *(thinnest training → lean hardest on inspection + own corpus)*

- **Dump path confirmed** (probe 2, 2026-08-16): enumerate `apex.callbackRegistry` + component/constraint/control/brush registries via `getRegistries`; extract typed ports from `apex.Signature`/`OverloadSet` → `rag/catalog/…/apex_callbacks.json`. Verify recipes with `apex.GraphExecutor` — the same primitive `run_apex_verify.py` builds on.
- **Grow the existing seed:** `run_apex_verify.py` + the recipe-name contract become a **recipe library** — composable, invocation-verified graph fragments (FK chain, IK setup, constraint stacks, control binding), each verified by *invoking the graph with test inputs* and checking outputs, not by trusting assembly.
- **Mine the two corpora on hand:** the camera-rig v5.0 APEX graphs (every working rig component is a recipe candidate + golden) and the `$HFS`-shipped APEX example graphs.
- Agent behavior in APEX: **compose verified recipes; never free-form a graph** from recall. Free-form authoring stays gated behind graph-invocation verification.

**Done-when:** callback catalog exists; ≥10 invocation-verified recipes including the camera-rig extractions; agent composition path uses recipes only.
**Estimate:** 2–3 sessions.

---

## 5 · Mile map

```
M0  Inventory + this blueprint + Phase-0 probes         ← DONE 2026-08-16
M1  Catalog dump runs, all categories, build-keyed       (P1)
M2  Docs join + Parm Gate live, K.5 GREEN                (P1)
M3  Measures + tier ladder + golden runner               (P2)
M4  Wave A shipped — COP stubs are real tools            (A)
M5  Wave B shipped — vellum doctor diagnoses by signal   (B)
M6  Wave C shipped — VOP wiring + CHOP core-20 + L-sys   (C)
M7  Wave D shipped — KineFX mechanical + handoff         (D)
M8  Wave E shipped — APEX recipes, weak list is empty    (E)
```

~15–17 half-day sessions, mile 0 → 8. Each mile is independently shippable and independently valuable — M2 alone retires every "I won't guess parm names" caveat.

---

## 6 · Phase-0 probes — receipts

```powershell
# 1. $HFS + build — ✅ RUN 2026-08-16: HFS = C:\Program Files\Side Effects Software\Houdini 22.0.400
#    VER = 22.0.400 → catalog key: rag/catalog/h22.0.400/

# 2. APEX registry entry point — ✅ RUN 2026-08-16: module surface = 78 symbols.
#    Confirmed: callbackRegistry, componentRegistry, constraintRegistry,
#    controlRegistry, brushRegistry, getRegistries, catalog, Registry/RegistryList,
#    Graph, GraphExecutor, GraphDebugger, Signature, OverloadSet.

# 3. Catalog dump shape — ✅ PROVEN LIVE 2026-08-16 via probe_phase0:
#    18 categories: Chop ChopNet Cop Cop2 CopNet Data Director Dop Driver Lop
#    Manager Object Shop Sop Top TopNet Vop VopNet · Cop (Copernicus) = 386 types
#    parmTemplateGroup walk succeeded on opencl COP (27 parms) — the exact
#    mechanism build_node_catalog.py industrializes at Mile 1.

# 4. Kernel contract — open the opencl COP help page once (cache captures the AST),
#    then confirm the catalog's parm row matches what the RD handler currently hedges on
#    STATUS: parm names observed (see §7); kernel-body syntax lookup remains.
```

Probe scripts live at `.token-saver/probe_phase0.py` and `.token-saver/probe_apex.py`.

---

## 7 · Risks & unknowns — the honest register

- ~~**APEX Python entry point**~~ — **RETIRED 2026-08-16, observed live**: `apex.callbackRegistry` (+ component/constraint/control/brush registries, `getRegistries`) is the dump target; `apex.Signature`/`OverloadSet` provide typed ports directly; `apex.GraphExecutor` is the invocation verifier. Help-cache ASTs remain the semantics join, not the fallback signature source.
- **OpenCL COP kernel contract in H22** — *parm names retired 2026-08-16* (`kernelcode` / `kernelname` / `kerneloptions` / `usewritebackkernel` / `writebackkernelname`, 27 parms total); the remaining unknown is kernel-body/binding **syntax**, which goes through one docs lookup before any kernel is authored. The `blockpath` incident is the precedent: Copernicus internals moved once this cycle; assume they can again.
- **Pixel-sort GPU kernel** — genuinely hard; the two-tier plan (CPU-correct first, GPU-fast second) prevents it from stalling Wave A.
- **Corpus completeness** — the cache holds only visited pages. Full coverage = the H22 authoring pass through `refresh_knowledge.py`, extending the `G:\HOUDINI21_RAG_SYSTEM` pattern. Until then, the catalog (from the binary) is complete even where docs are partial — names are always guaranteed; semantics fill in as the corpus grows.
- **Catalog staleness across builds** — solved by construction: build-keyed directories + the K.5 freshness gate; a Houdini upgrade turns the gate RED until the dump reruns.
- **VOP instantiation dump cost** — thousands of temp nodes; minutes on the Threadripper, once per build. Acceptable.

---

## 8 · Where new things live

```
scripts/build_node_catalog.py         # Phase 1 dump (models harvest_lop_catalog.py)
rag/catalog/h22.0.400/*.json          # build-keyed schema catalog
python/synapse/validation/measures.py # Phase 2 measurement contracts
handler_helpers.py :: gated_set()     # the Parm Gate
rulebook/goldens/<domain>/…           # per-wave golden fixtures
rulebook/… vellum remedy rules        # docs-cited diagnosis rules
rag/ + refresh_knowledge.py (K.5)     # docs corpora enter here; gate stays GREEN
```

Runtime lookup API for tools: `catalog.parms(category, node_type)` · `catalog.signature(category, node_type)` · `docs.parm(category, node_type, parm)` — cheap exact lookups first; the dense/BM25 paths remain for semantic questions ("why is my vellum exploding" → cited remedy rules).

---

*The through-line: SYNAPSE's tagline already contains the whole blueprint. "Honest by design: unmeasured renders UNKNOWN, never a guess" — Phase 1 removes the need to guess, Phase 2 removes the excuse not to measure, and the waves are just that sentence applied to seven contexts.*
