# APEX × H22 — Harness Blueprint, from first principles

**Grounded** 2026-08-17 against the live repo (`C:\Users\User\SYNAPSE`, v5.42.x),
`harness/DESIGN.md` (2026-08-03, H22.0.400), `python/synapse/science/apex_probes.py`
(re-seeded 2026-06-02 against **H21.0.671** — that stamp is itself a finding, see §4),
`python/synapse/science/apex_mcp_surface.json` (mock-recorded, re-record human-gated),
and the local H22 help cache at `OneDrive\Documents\houdini22.0\config\Help\cache`.

*Path note (2026-08-17 grounding pass): the blueprint's original shorthand
`science/...` and `panel/...` resolve to `python/synapse/science/...` and
`python/synapse/panel/...` in the live tree. All mission targets use the
resolved paths. Executed by `harness/apexforge/` (wave WA1).*

This document is written in the harness's own idiom: **CAPABILITY / GATE /
BENCH**, perturbation over structure, unmeasurable ≠ zero, evidence artifacts
over opaque weights.

---

## 1. First principles — what APEX actually is

Strip the marketing. APEX is three claims, each independently probe-able:

1. **A graph is geometry.** An APEX graph is stored as Houdini geometry
   (points = nodes, prims/wires = edges, dicts on points = parms). Everything
   the agent "knows" about a graph is therefore inspectable with the same
   geometry introspection SYNAPSE already trusts — no special access path.
2. **Nodes are typed callbacks, not HDAs.** `rig::CurveIK`, `transform::LookAt`
   are registered callbacks with **typed ports** (`Matrix4`,
   `VariadicArg<Matrix4>`, `Geometry`, …). The callback registry *is* the API
   surface. It is enumerable at runtime — which means the entire "2.x API
   surface" weak area is a **catalog dump, not a memorization problem**.
3. **Invoke is a function call.** `apex::invokegraph` / `apex::sceneinvoke`
   binds inputs, cooks, returns outputs. Deterministic in, deterministic out —
   which is what makes every rung below a *binary* pass/fail cook.

Corollary (the epistemic rule the whole blueprint hangs on):

> **Model memory is hypothesis. The live runtime is truth. The local help
> cache is the referee.** When docs and runtime disagree, that disagreement is
> not noise — it is a first-class finding (deprecation, version drift, or a
> phantom).

The DeepSeek self-assessment already made the right split: it flagged exactly
the three areas it would "verify against the live runtime rather than quote
from memory." This blueprint makes that split **structural** — the harness does
the verifying, and the model consumes evidence artifacts instead of trusting
recall.

---

## 2. The three weak areas, restated as testable claims

| # | DeepSeek's phrasing | Testable form | Workstream |
|---|---|---|---|
| W1 | "Deep APEX data types, @ vs $ subtleties, exact wire-typing rules" | For every (out-type, in-type) pair: does a wire connect, coerce, or reject? For every binding context: what does `@x` vs `$x` resolve to? | **CAPABILITY** → wire matrix probe |
| W2 | "APEX in Karma/Solaris context" | H22's LOPs beta: `apexsoprigbuilder` LOP, APEX Scene Animate LOP, Hydra scene-index render-time evaluation. Does a perturbed control move rendered pixels? | **CAPABILITY + BENCH** |
| W3 | "APEX 2.x API surface — precise node names and parameter encodings" | Full callback catalog + `::2.0` versions, diffed H21→H22, cross-referenced against help docs | **GATE** (known-correct answers exist) |

Note the asymmetry: **W3 is GATE, not BENCH.** Every question in it has one
right answer obtainable from the runtime. Hill-climbing it would be strictly
worse (DESIGN.md §3). W1 and W2 have real gradients — coverage of the type
matrix, rungs of the LOP ladder — so they carry bench weight.

---

## 3. What H22 changed (the delta the harness must absorb)

Confirmed against the H22 release docs:

- **LOPs toolset is beta and real** — APEX rigging/animation inside the USD
  stage; **APEX Animate LOP is a Hydra scene index plugin** doing render-time
  rig evaluation and deformation; Electra ships as a USD asset with rig
  variants. W2 stopped being an "intersection" and became a first-class
  context. The help cache already carries `lop/apexsoprigbuilder.json`.
- **Script language grew**: string/array slicing, FloatRamp/ColorRamp value
  setting, ramp types in graph interfaces. New type-system edge cases → new
  rows in the W1 matrix.
- **Graph debugger exposes port values** (tooltips in network view) and a
  right-click node-properties menu + **Open APEX Log**. The log is a
  harness-readable error channel — probes should capture it, not just stdout.
- **New/renamed surface** (W3 rows): APEX Rig Pose SOP (set driven keys),
  Control Extract 2.0, Configure Graph "Effects" mode, Scene Invoke's "APEX
  Scene Evaluate" alias, fuse-graph utilities on APEX Graph SOP, and the
  UsdSkel renames (`USD Animation Import` → `UsdSkel Animation Import`, etc.).
- **"Evaluate Rigs in Parallel"** default-on, and **"Cache Animation"**
  default-on — both change cook-timing assumptions any latency probe makes.
- **SideFX + NVIDIA demoed MCP-driven rigging agents in H22 at SIGGRAPH 2026**
  — the shipped H22 APEX MCP that `apex_mcp_surface.json` is waiting to record
  (its note: *"Re-record from the shipped H22 MCP is HUMAN-GATED (task 1.7)"*)
  exists. That gate can now be scheduled, not merely awaited.

---

## 4. GATE — known-correct work first (the walls, not the hills)

These are binary accepts. Do them before any bench run, in this order.

### G1 · Re-stamp the APEX truth surface for H22
`python/synapse/science/apex_probes.py` docstring says it plainly: seeded
against **H21.0.671**. That is the same defect class DESIGN.md already
prosecuted — *"symbol table stamped 22.0.397 against a running 22.0.400."* The
seeds themselves are probably still mostly valid (the 2026-06-02 re-seed killed
the fictional `apex::rig::` / `apex::sop::` namespaces), but *validity is
exactly what may not be assumed.* Re-run the seed set under H22, add rows for
the H22 additions (§3), and stamp the file with the build it was confirmed
against.

### G2 · Migrate the panel off the phantom names
`apex_probes.py` has carried this warning since June: *"recipes that still
reference the fictional names (`panel/apex_recipes.py`, `apex_explainer.py`)
must be migrated to these real names before they build."* Two months later the
supersession map exists and the migration hasn't happened. This is the COPs
scaffold-honesty rule applied to APEX: a recipe that names a node type that
does not exist is a phantom wearing a recipe's clothes. Contract it, goalpost
it (a test that greps emitted graphs for catalog-absent type names — pure
Python, real signal under stock pytest), and point a worker at it.

### G3 · Re-record `apex_mcp_surface.json` from the shipped H22 MCP
Mode A (mock) → Mode B (live). Human-gated stays human-gated — you launch it —
but the harness side is ready: same schema-digest mechanism, endpoint swapped
from `mock` to the shipped server. The diff between mock and live surfaces is
itself an evidence artifact.

### G4 · Symbol-table agreement
`cognitive/tools/data/h22_symbol_table.json` and `connectivity_22.json` get
the same treatment as G1: `harness/verify/version_agreement.py` already exists —
extend its contract to cover the APEX catalog stamp so drift becomes a red
check, not a discovery.

---

## 5. CAPABILITY — the ground-truth extractors that don't exist yet

Three builds. Each produces a versioned evidence artifact under
`harness/autoresearch/runs/`, following the run-artifact pattern that already
works (`solaris_basic` family).

### C1 · `apex_truth` mission — callback catalog + port signatures
A new mission `harness/autoresearch/missions/apex_basic.json` in the existing
schema, plus new probe kinds in `harness/autoresearch/probes.py` (the one file
allowed to touch `hou`): `apex_callback_discovery` (enumerate the registered
callback catalog: name, namespace, version `::2.0`, deprecation flag),
`apex_port_signature` (per callback: ordered in/out ports with declared types,
incl. `VariadicArg<T>` arity behavior), `type_existence` for the SOP-level
surface (`apex::invokegraph`, `sceneinvoke(::2.0)`, `rigpose` (new),
`controlextract(::2.0)`, `configuregraph`, `graph`, …), and a `chain_hash`
invoke smoke (minimal graph → invokegraph → cook → geometry hash, repeat 2).

Evidence out: `apex_truth_<build>.json` — every entry claim · value · probe ·
build · timestamp. The scout's **literal fence** then admits APEX names into
proposed missions only if this file proved them alive.

### C2 · Wire-typing matrix — W1 made mechanical
The "exact wire-typing rules for every node" are not learnable from prose;
they are a **product of two enumerable sets**. New probe kind
`apex_wire_matrix`:

1. From C1's port signatures, collect the set of distinct port types
   (`Matrix4`, `Float`, `Geometry`, `Dict`, `String`, arrays, ramps — H22
   adds ramp types to graph interfaces, so they're in scope).
2. For each ordered type pair, script-construct a two-node graph
   (`apex.Graph.addNode` + wire — both already champion-confirmed probes),
   attempt the wire, record: **connects / coerces / rejects** (+ exception
   text).
3. Same rig, `@` vs `$` resolution: a probe family that builds bind contexts
   (graph parms, scene hierarchy, invoke bindings) and records what each token
   form resolves to in each context. The output is a resolution table, not an
   explanation.

Evidence out: `apex_wire_matrix_<build>.json`. This single artifact converts
W1 from "subtleties I'd verify" into a lookup — and it regenerates per build,
so H22.5 drift is a re-run, not a re-learn.

### C3 · Help-cache cross-reference (the referee)
`OneDrive\Documents\houdini22.0\config\Help\cache\nodes\apex\*.json` is parsed
node help: per-node **typed inputs/outputs, `since` version, deprecation
status with successor links** (e.g. `rig::CurveIK` → deprecated → *"Use
rig::SampleSplineTransforms instead"*), context, namespace. That is exactly
the shape of C1's output, from an independent source.

Build `harness/autoresearch/xref_help.py` (plain Python, no `hou`):

- Parse `cache/nodes/apex/*.json` + `cache/nodes/sop/apex--*.json` +
  `cache/nodes/lop/apexsoprigbuilder.json` into the same claim schema as C1.
- **Three-way diff** per node: runtime says / docs say / recipes-corpus says.
  - runtime ∧ docs agree → confirmed row.
  - runtime present, docs absent → undocumented surface (fine, flag).
  - docs present, runtime absent → deprecation or phantom → quarantine
    candidate (`harness/phantoms/` already has the workflow).
  - type mismatch on a port → highest-value finding there is; file it.
- **Caveat, stated honestly:** the cache is lazily built — today it holds ~18
  APEX-related entries, i.e. what's been browsed/indexed locally, not the full
  set. Treat it as a high-precision, low-recall referee. For recall, the same
  parser can be pointed at the shipped help corpus (`$HFS/houdini/help`
  archives) in a follow-up; the cache proves the mechanism first.

---

## 6. BENCH — perturbation, the APEX edition (wave WA2)

DESIGN.md §4 verbatim, instantiated: *a literal-wired network does not move; a
procedurally-coupled one does.* For APEX the perturbation test is even
cleaner, because a rig is nothing but coupling:

**Rung ladder (each rung = prompt → build → assert structure → perturb → cook
→ assert downstream motion):**

| Rung | Task | Perturb | Assert changed |
|---|---|---|---|
| A1 | Two-node graph + invoke | input value | output value |
| A2 | FK chain (`apex::buildfkgraph`) on a probe skeleton | one control transform | descendant joint world xform |
| A3 | IK (`kinefx::twoboneik`) + FK blend | blend parm 0→1 | chain pose hash |
| A4 | Autorig component rig on Electra/Otto test geo | promoted control | skin point positions (bbox/hash) |
| A5 | **LOPs beta**: character via `apexsoprigbuilder` LOP, animate via APEX Scene Animate LOP | control keyframe | **stage**: UsdSkel points at t, then a 16×16 Karma render hash |
| A6 | Scene: two characters + camera, `sceneinvoke` | one character's clip offset | only that character's cook output (isolation, "Evaluate Rigs in Parallel" on) |

Scoring: existing `competence = Σ(weight·passed)/Σ(weight)` scalar.
**Weights per the audit posture:** W1-typed tasks highest (currently absent),
LOP-context (A5–A6) high (beta, moving target), plain rig-building medium.

A5's render step makes it **hython + Karma**: it must run through the
`.synapse/hytest.py` shim discipline (skip ≠ pass), and anything requiring
eyes-on-a-live-viewport is **autonomy: red**, exactly like
`heartbeat-relocation`.

---

## 7. Contracts (`.synapse/contracts/`)

| Contract | Tier | Goalpost sketch |
|---|---|---|
| `apex-truth-reseed.yaml` (G1+C1) | green | `apex_truth_<build>.json` exists, build == running build, all rank≥70 seeds confirmed |
| `apex-recipes-migration.yaml` (G2) | amber | pure-Python test: no emitted type name absent from apex_truth catalog |
| `apex-wire-matrix.yaml` (C2) | green | matrix artifact covers ≥ N type pairs; re-run is idempotent (repeat-2 hash) |
| `apex-help-xref.yaml` (C3) | green | xref report exists; zero unreviewed doc-vs-runtime type conflicts |
| `apex-lops-beta.yaml` (A5, WA2) | **amber→red** | stage-level asserts amber; live-render sign-off red, human-verified |
| `apex-mcp-rerecord.yaml` (G3, WA2) | **red** | Joe launches; digest diff mock→live archived |

---

## 8. The knowledge loop closes (what the model actually consumes)

Evidence artifacts feed the editable layer, never the engine
(DESIGN.md §6 boundaries hold):

```
apex_truth_<build>.json      ─┐
apex_wire_matrix_<build>.json ├─→  harness/bench/corpus/apex/   (EDITABLE)
help-xref report              ─┘    + scout literal fence vocabulary
                                    + panel apex_explainer/apex_recipes
                                      (post-G2, generated FROM evidence)
```

The model's context window then carries: the catalog, the matrix, the
deprecation map — **as data, versioned per build** — instead of memorized node
names. The model's job shrinks to reasoning over verified surface, which is
the job it's good at.

---

## 9. Sequence

| Phase | Work | Cost | Gate to next |
|---|---|---|---|
| 0 | G1 re-seed + G4 stamp agreement | hours | apex_truth green on current build |
| 1 | C1 mission + probe kinds | 1 day | catalog + ports artifact lands |
| 2 | C3 help-xref (plain Python, parallel-safe with 1) | ½ day | referee report, phantom candidates filed |
| 3 | G2 recipes migration (worker, amber) | ½–1 day | no phantom names emitted |
| 4 | C2 wire matrix | 1 day | W1 becomes a lookup |
| 5 | Bench rungs A1–A4 + weights | 1–2 days | baseline scalar exists |
| 6 | A5–A6 LOPs beta + G3 MCP re-record (Joe gates) | days | W2 measured, MCP surface live |
| 7 | Overnight bench loop, ARCHITECT→FORGE→CRUCIBLE | ongoing | compounding |

WA1 = phases 0–4 (legs TRUTH, XREF, WIRE, RECIPE + crucible ACRUX).
WA2 = phases 5–6. Phase 7 rides after both.

---

## 10. The failure this prevents (why it's built this way)

The June re-seed found the exact failure mode this blueprint is armor against:
**the model invented a plausible namespace (`apex::rig::`, `apex::sop::`) and
recipes shipped against it.** Catalog membership testing killed it once; the
help-xref referee + literal fence + G2 goalpost make the *class* unshippable.
Meanwhile the H21 stamp on apex_probes.py shows the second failure mode:
truth that was verified once and silently aged. Per-build artifacts with
version-agreement checks make staleness a red light instead of a surprise.

Unmeasurable is not zero. It is unknown, and it is excluded — and after phase
4, almost nothing about APEX is unknown.
