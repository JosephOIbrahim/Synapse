# Science Harness — APEX verify run (2026-06-02)

**Run by:** SYNAPSE Science Harness (`scripts/run_apex_verify.py`) on headless **hython
21.0.671**. Read-only `dir()` / catalog introspection — no scene mutation.
**Status:** results recorded. Champions = confirmed present+callable. The 10 corrected
names below are **catalog-present (confirmed) + role-matched (3-lens adjudicated), but their
signatures/exact behavior are NOT yet verified** — that's the next iteration. No "verified"
stamp claimed beyond what was probed.

---

## What ran

Second-seed run of the 12-seed `APEX_SEED` against a fresh registry
(`.synapse/science/apex_seed2_20260602.jsonl`, gitignored local run-data), in an independent
hython session — i.e. the harness's promotion-rule **second-seed form** for an API surface
(a second independent `dir()` environment). `apex` module present, full node catalog
(5811 types) live, 0 skipped → all 12 re-probed.

## Result vs the 2026-05-31 run

| | 2026-05-31 (seed 1) | 2026-06-02 (seed 2) |
|---|---|---|
| champions | 2 | **2 (reproduced)** |
| dead-ends (absent as spelled) | 10 | **10 (reproduced)** |

**Champions — confirmed on two independent seeds:**
- `apex.Graph` (attr) · `apex.Graph.addNode` (call) — present + callable.
- Wider confirmed-present Python surface (from `dir(apex)`, callability unprobed):
  `GraphExecutor, Control, MultiControl, TransformControl, Constraint, ConstraintManager,
  ControlManager, Registry, SceneGraph, SceneCharacter, graphops, findSkeletonJoints,
  getOutputShapeNamesFromRig, tagRigControls, …`.

## Tie-break RESOLVED — "absent as spelled" ≠ "capability absent"

The standing open question (were the 10 truly absent, or probe artifacts?) is resolved
against the live catalog. **Root cause:** the recipe seeds invented a namespacing that does
not exist. **APEX node types are flat `apex::<name>`** — there is no `::rig::` / `::sop::` /
`::autorig::` middle segment — and several rig operators live under **`kinefx::`**, not
`apex::`. The 10 are confirmed absent *as spelled* on two seeds, but 9/10 capabilities exist
under corrected names.

### Corrected mappings (3-lens consensus: literal-name / capability / skeptic)

**Strong rename — capability present, mis-namespaced:**
| Seed (fictional) | Real H21.0.671 | Confidence |
|---|---|---|
| `rig_doctor` | **`kinefx::rigdoctor`** | .92 / .97 / .92 |
| `apex::sop::invoke` | **`apex::invokegraph`** (SOP variant `sopinvokegraph`) | .90 / .85 / .85 |
| `apex::rig::blendtransform` | **`kinefx::blendtransforms`** (alt `kinefx::skeletonblend`) | .85 / .95 / .85 |
| `apex::autorig::build` | **`apex::autorigbuilder`** (+ `apex::autorigcomponent` parts) | .85 / .90 / .83 |
| `apex::rig::fkfull` | **`apex::buildfkgraph`** | .88 / .72 / .82 |
| `apex::rig::ikfull` | **`kinefx::twoboneik`** (+ `solveik`/`fullbodyik`/`ikchains`) | .60 / .70 / .70 |

**Capability present but diffuse (no 1:1 node — served by API + multiple nodes):**
| Seed | Where the capability lives |
|---|---|
| `apex::sop::graphdefaults` | `apex::graph` (the base graph itself) |
| `apex::sop::apexedit` | `apex.Graph` API (champion) + `apex::configuregraph` / `layoutgraph` / `mergegraph` |
| `apex::sop::transformobject` | `apex.TransformControl` (Python) authored via `apex::configurecontrols` / `controlextract` |

**Weakest — no clean target:** `apex::sop::fromkinefx` — KineFX & APEX share the
point-based skeleton, so "convert skeleton" is largely a no-op mediated by
`apex::mapcharacter` / `packcharacter` / `apex.findSkeletonJoints`. No dedicated converter.

## What this de-risks, and what it does NOT

- **De-risks:** the APEX recipe builds were targeting node-type strings that **do not exist**
  in H21.0.671. Any recipe build against the as-spelled names would have failed with
  "Invalid node type name." The corrected names are real catalog entries.
- **Does NOT yet confirm:** that each corrected node *does the intended job*, nor its
  parameter signature. Catalog membership ≠ behavioral fit. The 3-lens verdicts are role-
  *adjudication*, not behavioral verification.

## Re-seed + re-run + signature verification (DONE — same session, 2026-06-02)

`apex_probes.py` was re-seeded with the corrected real names (14 nodetype seeds, flat
`apex::*` + `kinefx::*`, + the 2 Python champions) and re-run on a fresh registry
(`.synapse/science/apex_corrected_20260602.jsonl`). Science tests stayed green (57 passed).

**Result: 16/16 champions, 0 dead-ends.** Every corrected name is confirmed present in the
H21.0.671 catalog. The reconciliation holds end-to-end.

### Signature verification (read-only `nodeType.parmTemplateGroup()` — no instantiation)

| Real name | category | inputs (min/max) | outputs | key parms |
|---|---|---|---|---|
| `apex::invokegraph` | **Sop** | 1 / 9999 | 1 | inputbindings, outputbindings, errorhandlingmode, asynccook |
| `apex::autorigbuilder` | **Sop** | 0 / 2 | 2 | autoupdaterig, updaterig, resetall, … (19) |
| `apex::buildfkgraph` | **Sop** | 2 / 2 | 1 | mode |
| `kinefx::twoboneik` | **Vop** ⚠ | 0 / 10 | 3 | signature, selectdriven/drivers, stretch, blend |
| `kinefx::blendtransforms` | **Vop** ⚠ | 0 / 4 | 1 | signature, components, bias |
| `kinefx::rigdoctor` | **Sop** | 1 / 1 | 1 | pointnames, hierarchy, transformations, visualize |
| `apex::graph` | **Sop** | 0 / 1 | 1 | editgraph, graphpath, riggingscripts |
| `apex::configuregraph` | **Sop** | 0 / 1 | 1 | mode, name, constraintparameters |
| `apex::autorigcomponent` | **Sop** | 0 / 2 | 2 | componentparameters, rigparameters, switcher |
| `apex::configurecontrols` | **Sop** | 1 / 2 | 1 | rig, skincontrolshape, useguides, guidesource |
| `apex::controlextract` | **Sop** | 1 / 1 | 2 | extractfromfolder, graphgeopath, group |
| `apex::mapcharacter` | **Sop** | 0 / 1 | 1 | rigpath, skeletonpath, mapbyname, mappings |
| `apex::packcharacter` | **Sop** | 0 / 4 | 1 | charname, shapepath, skelpath, rigpath |
| `apex::sceneinvoke` | **Sop** | 1 / 3 | 2 | animationclip, setrigpath, channelprimdatapath |

None deprecated. **Critical recipe finding:** `kinefx::twoboneik` (IK) and
`kinefx::blendtransforms` (FK/IK blend) are **`Vop`** nodes, not SOPs — they are
graph-internal compute nodes built *inside* an APEX graph (via `apex.Graph.addNode`), **not**
creatable as standalone SOPs. A recipe calling `houdini_create_node('kinefx::twoboneik')` at
SOP level would fail. This matches APEX's graph-as-VOP-network model: SOP-level nodes are the
container/bridge (rigdoctor → graph/mapcharacter/autorigbuilder → invokegraph), while IK/blend
logic lives as VOPs inside the graph.

**`apex.Graph.addNode` signature resolved:** `addNode(self, str, str) -> int` — closes the
"exact signature unverified" caveat. The graph mutator takes two strings, returns an int id.

## The actual next step (handoff to recipe migration — a build, not science)

`python/synapse/panel/apex_recipes.py` and `apex_explainer.py` still reference the fictional
names. Migrate them to the real names above, **and** respect the SOP/VOP split: build IK/blend
inside the APEX graph (`apex.Graph.addNode`), not as SOPs. Then a live build-and-cook of one
recipe (e.g. fk_chain) is the behavioral confirmation that closes the loop.

---

*Machine record: `.synapse/science/apex_seed2_20260602.jsonl` (gitignored). Reconciliation:
3-agent adversarial workflow over the live catalog dump. Champions confirmed on two seeds;
corrected names catalog-present, behavior-unverified.*
