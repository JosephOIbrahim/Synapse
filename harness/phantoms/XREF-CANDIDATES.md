# XREF-CANDIDATES — help-cache cross-reference quarantine ledger (WA1-XREF / C3)

*Append-only. A **log entry, never a deletion** — same discipline as this
directory's `SPEC.md` and `LOG.md` (the PHANTOM SWEEP harness). A candidate here
is a **proposal to review**, gated to a human; nothing is quarantined or removed
by filing it. Lineage: `harness/phantoms/SPEC.md` (KEEP-vs-FIX discipline),
`docs/APEX_H22_BLUEPRINT.md` sec.5 C3.*

## What files a candidate

The C3 referee (`harness/autoresearch/xref_help.py`) runs a three-way diff per
node across **runtime** (`apex_truth` catalog), **docs** (the Houdini parsed-help
cache), and **recipes** (`python/synapse/panel/apex_recipes.py`). A node becomes
a **quarantine candidate** in exactly one situation:

> **docs present AND runtime KNOWN-absent** — a name the help cache still
> documents but the live catalog no longer exposes (a deprecation that was
> removed, or a phantom).

Two guards make this honest and keep it from manufacturing phantoms:

1. **Low-recall referee.** The cache holds only locally-browsed pages
   (~25 APEX entries), not the full product surface. **Absence from the cache is
   no-evidence, never product-absence.** A candidate is never raised on
   cache-silence.
2. **Runtime-consumed gate.** A candidate requires the runtime to have been
   **actually consumed** (`apex_truth` published on the bus + parsed). With the
   runtime UNKNOWN, *no* node can be called runtime-absent, so *zero* candidates
   are raised — the referee reports UNKNOWN, not a clean bill.

Every candidate carries **both anchors**: the cache file it came from **and**
the `apex_truth` entry it disagreed with. One anchor is an unanchored claim and
is not filed.

## Runs

### 2026-08-17 — run `apex_help_xref_wa1_20260817` (runtime CONSUMED)

- **Artifact:** `harness/autoresearch/runs/apex_help_xref_wa1_20260817/apex_help_xref_22.0.400.json`
- **Docs source:** `OneDrive/Documents/houdini22.0/config/Help/cache` (config `22.0`)
- **Runtime:** **CONSUMED** — WA1-TRUTH published `apex_truth_22.0.400.json`
  (build `22.0.400`) on the APEXFORGE bus mid-run; referee consumed it via
  `--runtime`. The callback registry enumeration is **COMPLETE** (2286 names,
  `count == len(names)`), which licenses calling a callback KNOWN-ABSENT. The
  SOP/LOP `type_exists` set is a probed subset (silence there → UNKNOWN).
- **Cache entries parsed:** 25 · **Recipe names scanned:** 24 · **Rows:** 55
  · **0 unclassified**.
- **Verdicts:** confirmed 17 · undocumented 27 · **quarantine-candidate 2** ·
  type-mismatch 0 · runtime-unknown 9.
- **Type-mismatch is 0 and UNMEASURABLE, not "all agree":** `apex_port_signature`
  exposes port **arity** but null port **names/types** even for non-hidden
  callbacks, so no port-TYPE comparison is possible against this artifact
  (`runtime_port_types_measurable=false`). Recorded, never dressed as a pass.

**Quarantine candidates filed this run: 2** (doc-present / runtime-KNOWN-absent,
both anchors present). **A candidate is a proposal to review, gated to a human —
never a deletion.**

| symbol | surface | docs anchor | runtime anchor | disposition note |
|---|---|---|---|---|
| `component::MappedConstraints` | apex_callback | `nodes/apex/component--MappedConstraints-.json` | `apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:*` | namespace `component` has **zero** registered callbacks → **likely a non-callback concept** (KineFX rig component, assembled by autorig), not a phantom. The help page is mis-filed under the callback dir; human decides doc-fix vs quarantine. |
| `controlgadget::SnapXFormToAxes` | apex_callback | `nodes/apex/controlgadget--SnapXFormToAxes.json` | `apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:*` | namespace `controlgadget` has **zero** registered callbacks → **likely a control-gadget concept** (viewport handle), not a phantom. Same disposition question. |

**Neither is a confirmed phantom.** Both are documented under `nodes/apex/` (the
callback help dir) yet absent from the complete callback registry because their
namespaces are not callback namespaces at all. That is a real doc-surface
discrepancy worth a human's eye; the referee flags, it does not judge.

#### Deprecation resolved by runtime (NOT a quarantine)

`rig::CurveIK` (`nodes/apex/rig--CurveIK.json`) is marked **deprecated** in docs
with successor `rig::SampleSplineTransforms`. Runtime says it is **present**
(hidden) in the registry → **confirmed-deprecated, NOT a phantom**. Runtime
truth over the docs referee: a deprecated-but-still-registered node is not
quarantined.

#### Recipes-side note (one writer per surface)

The referee **reads** `apex_recipes.py` read-only and flags; `WA1-RECIPE` is the
sole writer. Recipe types split against the consumed runtime as: several
**confirmed / undocumented** (catalog- or type_exists-present), and the generic
SOP types `bonegenerator` / `skeleton` / `null` **runtime-unknown** (outside
TRUTH's probed `type_exists` subset — UNKNOWN, never called absent). **Zero
recipe names proved phantom.** Any recipes-side phantom is a **bus finding to
WA1-RECIPE**, never filed here (this ledger is doc-vs-runtime only).
