# RSI DEADENDS — the PROTECTED-IMMUTABLE tier (seed)

> **Logical layer:** DEADENDS ≡ the protected-immutable falsifiability tier — a
> prototype of Line C's deliverable. **Authored at:** INGEST.
> **Seeded from:** `.synapse/science/apex_registry.jsonl` (read-only, the one
> registry read INGEST is permitted).
>
> **Invariants (Operating Principle 5 — the one place Moneta's decay model must
> NOT apply):**
> - Records here are **NEVER overwritten** and **NEVER decay**.
> - A verdict is only ever **superseded by an explicit, logged re-verification**
>   (a new appended record citing the old), never silently replaced.
> - **Read DEADENDS before proposing.** Every lens sees every dead end.
> - An attempt to overwrite/decay a record here is a **HALT**, not a delta.

The science `Registry` already enforces "dedup by `(surface,kind)`, never
overwrites a verdict." This tier is that guarantee made durable and global.

---

## Tier A — confirmed-ABSENT (dead-ends) · the first protected records

These are the harness's primary DEADENDS seed: APIs the science harness probed
and recorded **absent**. All 10 are `kind: nodetype` (produced by the corrected,
name-resolving probe — see *Scope* below), `timestamp: 0`.

| # | Surface | Kind | Verdict | Source recipes / context |
|---|---|---|---|---|
| 1 | `apex::rig::fkfull` | nodetype | dead_end | `fk_chain` / `fk_ik_blend` / `control_shapes` build this as the FK setup node |
| 2 | `apex::rig::ikfull` | nodetype | dead_end | `ik_chain` / `fk_ik_blend` IK solver (end effector + pole vector) |
| 3 | `apex::rig::blendtransform` | nodetype | dead_end | `fk_ik_blend` blends FK/IK; `KINEFX_MIGRATION_GUIDE` maps Skeleton Blend → this |
| 4 | `apex::autorig::build` | nodetype | dead_end | `autorig_biped` full-rig generator; `autorig` vs `rig` namespacing least certain |
| 5 | `apex::sop::graphdefaults` | nodetype | dead_end | `simple_deformer` seeds a base APEX graph rather than building from scratch |
| 6 | `apex::sop::fromkinefx` | nodetype | dead_end | `kinefx_to_apex` converts KineFX skeleton → APEX (skeleton only, not rig logic) |
| 7 | `apex::sop::invoke` | nodetype | dead_end | `apex_explainer` run-program bridge (APEX graph → SOP geo); canonical type string unverified |
| 8 | `rig_doctor` | nodetype | dead_end | mandatory pre-APEX skeleton validator (`fk_chain` / `autorig_biped` / `kinefx_to_apex`) |
| 9 | `apex::sop::transformobject` | nodetype | dead_end | `_APEX_TYPE_PATTERNS` autorig building block; casing/existence on 21.0.671 unverified |
| 10 | `apex::sop::apexedit` | nodetype | dead_end | `apex_explainer` APEX network editor vs `apex_editgraph` for the same role |

### Scope of the Tier-A verdicts — confirmed-absent **AS SPELLED**, real names not yet final

Stated precisely so an immutable dead-end is never over-read. (This corrects a
first-draft worry — see the FYI at the foot of this block.)

- **The probe that produced these is the CORRECTED one.** All 10 records carry
  `kind: nodetype`. The `getattr` false-negative belonged to the *earlier*
  `attr` probe (`getattr` cannot see node types); commit `1ac0b9e`
  ("feat(science): add nodetype probe kind — fix the node-type false-negative
  (#19)") added the `nodetype` kind, which resolves by **name via catalog
  membership** — not `getattr`. A `kind: nodetype` record can only come from the
  post-fix probe, so the `kind` field (present in the registry) is dispositive:
  these are **post-fix corrected-probe outputs**, not stale `getattr`-era
  artifacts. The probe-shape worry does **not** apply to these records.

- **What they actually confirm:** the exact type string is **absent as spelled**
  in the H21 21.0.671 node catalog. They do **not** establish that the
  capability is absent — the real APEX type name may differ in spelling or
  namespace. The registry's own `context` fields already hedge exactly this
  ("namespacing autorig vs rig is the least certain", "casing and existence …
  unverified", "which type string is canonical … is unverified"). The science
  harness's stated next step is to *discover the real APEX node-type names and
  correct the seeds*.

- **Seeding status:** `verification_status: CONFIRMED_ABSENT_AS_SPELLED` —
  faithful to a corrected-probe verdict — carried with a **`scope` caveat** so no
  future lens reads `apex::rig::fkfull → dead_end` as "APEX cannot do FK
  rigging." A later discovery of the real name does **not** overwrite these; it
  **appends** a new record (a different surface string) and cross-references via
  `superseded_by`. Immutability preserved; falsifiability preserved.

> **FYI at the gate (not a blocker):** an earlier draft of this seed worried the
> 10 might be `getattr` false-negatives. CRUCIBLE caught that `kind: nodetype`
> already rules that out — the corrected reading above replaces it. If you prefer
> maximum caution you may still hold them PROVISIONAL pending a real-name
> discovery pass; the default is CONFIRMED-ABSENT-AS-SPELLED with the scope
> caveat. Discovering the real names is itself live-code work (a DELIBERATE item
> on Line S), not an INGEST move.

## Tier B — confirmed-PRESENT (champions) · immutable verdicts, not dead-ends

The registry also holds two **confirmed-present** verdicts. They are not
dead-ends, but they are immutable falsifiability records (the registry never
overwrites either verdict), so they belong in the protected tier — recorded here
losslessly rather than discarded.

| Surface | Kind | Verdict | Status | Context |
|---|---|---|---|---|
| `apex.Graph` | attr | champion | CONFIRMED | first-class APEX graph type at the Python layer; recipes build/edit graphs before Invoke evaluates |
| `apex.Graph.addNode` | call | champion | CONFIRMED* | canonical APEX Graph mutator; *exact signature unverified on 21.0.671 |

Both are registry `champion` verdicts; INGEST records them from the registry read
alone (its two declared inputs are the audit + the one registry read).

---

## Protected-tier schema (ARCHITECT owns this)

Each protected record carries, beyond the raw registry fields
(`surface, kind, status, detail, context, timestamp`):

```
tier                 = PROTECTED-IMMUTABLE
verification_status  = CONFIRMED_ABSENT_AS_SPELLED | CONFIRMED_PRESENT
scope                = what the verdict actually proves (Tier A: "exact type
                       string absent in the H21 21.0.671 catalog" — NOT capability)
provenance           = source (apex_registry.jsonl @ INGEST) + corrected-probe note
immutable            = true        # never decay, never overwrite
superseded_by        = <id of a later re-verification / real-name record, or null>
```

`verification_status` + `scope` let a record be **stored** immutably while
carrying exactly what it proves — Tier A proves absence *as spelled* (not
capability-absence); Tier B proves presence. A future re-verification (e.g. the
real APEX type name) **appends** a new record and sets `superseded_by` rather
than overwriting. This preserves both the immutability invariant and
falsifiability.

**Total seeded:** 12 records (10 Tier-A confirmed-absent-as-spelled + 2 Tier-B
confirmed-present), lossless against the 12-line registry — zero dropped.
