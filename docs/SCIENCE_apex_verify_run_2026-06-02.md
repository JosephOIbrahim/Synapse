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

## Next iteration (the harness's clear next run)

Re-seed `python/synapse/science/apex_probes.py` with the corrected names (flat `apex::*` +
`kinefx::*`) and re-run — the strong-rename six should promote to champions; then verify
signatures/roles (node `.parmTemplateGroup()` / SideFX help) before any recipe build relies
on them. This is a harness re-run + a build, not new architecture.

---

*Machine record: `.synapse/science/apex_seed2_20260602.jsonl` (gitignored). Reconciliation:
3-agent adversarial workflow over the live catalog dump. Champions confirmed on two seeds;
corrected names catalog-present, behavior-unverified.*
