# WA1-RECIPE — G2 phantom-name migration ledger

**Leg:** WA1-RECIPE (G2) · **Branch:** `wavea1/recipe` · **Date:** 2026-08-17
**Mission source:** `docs/APEX_H22_BLUEPRINT.md` sec.4 G2 — phantom-name migration + catalog-membership goalpost

## Authorities

| Role | Artifact | Anchor |
|---|---|---|
| Supersession map (fictional → real) | `python/synapse/science/apex_probes.py` | L24–33 (docstring) |
| Catalog membership (runtime truth) | `apex_truth_22.0.400.json` (WA1-TRUTH, 39 entries, 0 probe failures) | `harness/autoresearch/runs/apex_basic_20260817_122650/apex_truth_22.0.400.json` — `type_exists[*]` verdicts L3481–3894 |
| Handoff | APEXFORGE bus, wavea1 | WA1-TRUTH finding `n=18cca4904b84b1a0` (posts artifact path) |

**Rule:** every APEX/KineFX name emitted or presented as real must be catalog-proven
present (`type_exists[*]…exists:true` or a `apex_callback_catalog` name). The two
catalog-falsified phantoms (`apex::configuregraph::2.0`, `apex::fusegraph`,
`exists:false`) are treated as absent.

---

## Target 1 — `python/synapse/panel/apex_recipes.py` — NO EDIT REQUIRED

Read + AST-scanned: all 24 emitted `nodes[].type` values (13 distinct) are already
migrated to real names — **zero** `apex::rig::`/`apex::sop::`/`apex::autorig::`
strings (WA1-XREF independently confirmed this, bus `n=18cca4649fce0508`). Every
namespaced emitted type is catalog-present:

| emitted `nodes[].type` | catalog verdict |
|---|---|
| `kinefx::rigdoctor` | present (Sop) |
| `apex::buildfkgraph` | present (Sop) |
| `kinefx::twoboneik` | present (Vop) |
| `kinefx::blendtransforms` | present (Vop) |
| `apex::autorigbuilder` | present (Sop) |
| `apex::graph` | present (Sop) |
| `apex::configuregraph` | present (Sop) |
| `apex::invokegraph` | present (Sop) |
| `apex::configurecontrols` | present (Sop) |
| `apex::mapcharacter` | present (Sop) |
| `bonegenerator`, `skeleton`, `null` | non-namespaced stock SOPs — outside the APEX catalog's jurisdiction (not the phantom class) |

`kinefx::fullbodyik` appears once in `KINEFX_MIGRATION_GUIDE` **prose** (not an emitted
type), honestly flagged there as "catalog-listed sibling; unprobed". It is not a
phantom and is correctly excluded from the goalpost (Gate 1 extracts emitted
`nodes[].type` only, never prose tokens).

**The claim was posted for sole-writer discipline; the file was left byte-unchanged.**

---

## Target 2 — `python/synapse/panel/apex_explainer.py` — MIGRATED

### Edit A — artist-facing prose (`APEX_CONCEPTS["autorig"]["mental_model"]`)

| old (fictional) | new (real) | map anchor | note |
|---|---|---|---|
| `apex::sop::TransformObject` | `apex::configurecontrols` | apex_probes.py L31 (`apex::sop::transformobject → apex::configurecontrols / controlextract`) | "creates a transform control" — semantics preserved |
| `apex::sop::FK` | `apex::buildfkgraph` | apex_probes.py L24 (`apex::rig::fkfull → apex::buildfkgraph`) | "builds an FK chain" — semantics preserved |

Pure rename: the sentence still teaches "X creates a transform control, Y builds an
FK chain", now with catalog-present names instead of phantoms.

### Edit B — classifier substrings (`_APEX_TYPE_PATTERNS`)

These are **recognition substrings** matched against a live node's
`node.type().name()` (`if pat in lower`) — never emitted to `createNode`. Every
`apex::sop::` entry was dead: no real node type contains that segment, so the
recogniser matched nothing and real nodes fell through to the `if "apex" in lower`
bucket.

| old (fictional) | new (real) | map anchor |
|---|---|---|
| `apex::sop::invoke` | `apex::invokegraph` | L28 |
| `apex::sop::rig` | `apex::autorigbuilder` + `apex::autorigcomponent` | L27 (`apex::autorig::build → apex::autorigbuilder (+ autorigcomponent)`) |
| `apex::sop::fk` | `apex::buildfkgraph` | L24 |
| `apex::sop::ik` | `kinefx::twoboneik` | L25 (`apex::rig::ikfull → kinefx::twoboneik`) |
| `apex::sop::transformobject` | `apex::configurecontrols` + `apex::controlextract` | L31 |
| `apex::sop::blendtransform` | `kinefx::blendtransforms` | L26 (`apex::rig::blendtransform → kinefx::blendtransforms`) |
| `apex::sop::apexedit` (and bare legacy `apexedit`) | `apex::configuregraph` | L30 (`apex::sop::apexedit → apex::configuregraph`) |

The bare legacy `invoke` substring is retained (it already catches every invoke
variant — `apex::invokegraph`, `apex::sceneinvoke`, `cop::sopinvokegraph`).

### Disclosed reclassification (NOT a silent semantic edit)

Because the recognisers now carry real names, real rig nodes classify by their
actual type instead of falling through. Verified live (`_classify_apex_type`):

| node type | before | after | why after is correct |
|---|---|---|---|
| `apex::buildfkgraph` | apex_network (fallthrough) | **autorig** | FK build is rig logic |
| `apex::autorigbuilder` / `apex::autorigcomponent` | apex_network | **autorig** | autorig nodes |
| `apex::configurecontrols` / `apex::controlextract` | apex_network | **autorig** | control authoring |
| `kinefx::twoboneik` | kinefx | **autorig** | the phantom `apex::sop::ik` already lived in the autorig bucket — this realises the pre-existing intent |
| `kinefx::blendtransforms` | kinefx | **autorig** | the phantom `apex::sop::blendtransform` already lived in the autorig bucket — pre-existing intent |
| `apex::invokegraph` | invoke | invoke | unchanged |
| `apex::configuregraph` / `apex::graph` | apex_network | apex_network | unchanged |
| `kinefx::rigdoctor` / `apex::rigpose` / `skeleton` | kinefx | kinefx | unchanged |

This is disclosed, not silent: the reclassification is the direct consequence of
placing the real IK/blend/FK node names into the buckets their phantom predecessors
already occupied. Downstream (`_relevant_concepts`) now surfaces more apt teaching
concepts for these nodes (autorig / rig_logic vs the generic buckets). No existing
test pins the old classification (`grep` of `tests/` + `python/`: only
`test_apex_recipe_names.py` references these modules, and it scans `apex_recipes.py`
data only — never the explainer or `_classify_apex_type`).

---

## Finding for ruling — constraint recognisers have no SOP node successor

`apex::sop::parentconstraint` and `apex::sop::aimconstraint` (both in the `autorig`
bucket) were removed, **not renamed** — the supersession map has no constraint row,
and the apex_truth catalog has **no SOP constraint node type**. The real constraint
surface is graph-internal:

- APEX graph callbacks: `rig::PointConstraint`, `rig::PrimConstraint`,
  `rig::CurveConstraint`, `rig::UVConstraint`, `transform::LookAt` (all present in
  the `apex_callback_catalog` — they live *inside* the APEX graph via
  `apex.Graph.addNode`, not as SOP-createable node types).
- Or the `apex.Constraint` / `ConstraintManager` Python API (per the
  `constraint_setup` recipe caveat in `apex_recipes.py`).

Removing the two dead recognisers changes **no** runtime classification (no node
type name contains `parentconstraint`/`aimconstraint`), so it is behaviour-preserving
in practice; the lost *intent* (recognise constraint nodes) is what is flagged.
**For ruling:** should constraint recognition be re-added keyed on the real
graph-callback surface (`rig::*Constraint` / `transform::LookAt`)? Out of this
rename leg's scope.

---

## Target 3 & 4 — goalpost test

`tests/panel/test_apex_catalog_membership.py` — pure Python (ast + tokenize + json),
no `hou`, no `hython`, no `import synapse.*`, stock pytest.

- **Gate 1** `test_emitted_recipe_types_are_catalog_present` — extracts emitted
  `nodes[].type` from `apex_recipes.py` (AST), checks every APEX/KineFX-namespaced
  one against the fresh catalog's present-set. Catalog discovered from
  `APEX_TRUTH_CATALOG` env or the newest `apex_truth_*.json` under
  `harness/autoresearch/runs` / `python/synapse/autoresearch/runs`. **No catalog →
  raises `CatalogNotFound` (hard ERROR), never `pytest.skip`.**
- **Gate 2** `test_no_phantom_namespace_in_panel_string_literals` — `tokenize`-based
  scan of both modules' **string literals** (comments blanked, so a `#` migration
  comment documenting old names is exempt, and `#RRGGBB` colour literals are
  preserved) for `apex::(rig|sop|autorig)::`. Zero tolerance.
- **RED-leg demonstration** `test_missing_catalog_fails_loudly_never_skips` — proves
  discovery raises (empty search root + env-to-missing-file) and statically guards
  against a future `skip(` call sneaking into discovery.
- **Freshness** `test_catalog_is_the_apex_truth_artifact` — confirms the discovered
  JSON is a real `apex_truth` artifact carrying `apex::invokegraph`.

### Evidence (both acceptance states demonstrated)

```
# No catalog reachable (this branch alone, pre-merge) — RED leg, loud:
$ python -m pytest tests/panel/test_apex_catalog_membership.py
  test_emitted_recipe_types_are_catalog_present ......... FAILED (CatalogNotFound, not skip)
  test_no_phantom_namespace_in_panel_string_literals .... PASSED
  test_missing_catalog_fails_loudly_never_skips ......... PASSED
  test_catalog_is_the_apex_truth_artifact .............. FAILED (CatalogNotFound, not skip)
  => 2 failed, 2 passed, 0 skipped

# Fresh apex_truth catalog provided (the WA1-TRUTH handoff) — GREEN:
$ APEX_TRUTH_CATALOG=<…/apex_truth_22.0.400.json> python -m pytest tests/panel/test_apex_catalog_membership.py
  => 4 passed, 0 skipped
```

**By design, Gate 1 + freshness are RED on this branch in isolation** (the catalog
is WA1-TRUTH's committed artifact, not in this worktree). That redness *is* the
unshippability property. They go green when the catalog is discoverable — via the
`APEX_TRUTH_CATALOG` handoff now, or automatically once `wavea1/truth` merges (the
artifact is committed under `harness/autoresearch/runs/`). `0 skipped` in every run.

---

## Merge-awareness

- `python/synapse/cognitive/tools/data/emitted_node_types.json` — **not touched, no
  regen needed.** Its extractor (`scripts/extract_emitted_node_types.py`) scans
  `createNode("…")` literals + `APEX_SEED` + setdressing `VERIFIED_NODE_TYPES`.
  Neither `apex_recipes.py` nor `apex_explainer.py` contains a `createNode(` literal,
  and this leg edits neither `apex_probes.py` nor the setdressing test. `test_emitted_node_types.py`
  stays green on this branch (verified). WA1-TRUTH's regen (bus `n=18cca4e00fcefa58`)
  stands on its own branch; no collision from this leg.
- Sole writer to `apex_recipes.py` / `apex_explainer.py` this wave (crux criterion);
  bus claim `n=18cca686a6b05fdc` posted before edit, released on completion.
