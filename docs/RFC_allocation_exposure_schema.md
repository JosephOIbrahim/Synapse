# RFC — The `Allocation` / `Exposure` schema (v5 Track-C precondition)

**Status:** ARCHITECT artifact — a **PROPOSAL for Michael Gold**, not a decision and not an
implementation. Design-only. No `agent.usd` schema is modified by this RFC; no §2/§3/§8 code ships.

> **Read order:** §0 (what this is and what it gates) → §3 (the core typed-vs-customData question,
> the one Gold actually decides) → §1/§2 (the rung-scale migration and the `Allocation` prim) → §4
> (`Exposure`) → §6 (decided-by-Gold + what stays blocked). Five minutes: §0, §3 recommendation, §6.

---

## §0 — What this is, and what it gates

`SYNAPSE_SCIENCE_HARNESS_v5.md` adds two organs — an **allocation pre-gate** (§3 of v5) and a
**provenance→exposure projection** (§8 of v5). Both need durable USD state, and both must be
**consistent with the already-ratified `agent.usd` Ledger RFC (`docs/RFC_agent_usd_ledger.md`,
D-1..D-6 ratified)** rather than a fresh paradigm. This RFC proposes that schema.

It is a **Track-C precondition.** Per the v5 runbook, Track C stays closed until (a) Track H is
green, (b) the operator says "begin Track C," and **(c) this RFC is ratified by Gold.** Nothing
here is built before ratification (§6).

**Grounding in D-1..D-6 (inherited, not re-litigated):**

| Ratified | What it fixes for this RFC |
|---|---|
| **D-1** | per-record JSON file = source of truth; `agent.usd` `/ledger/` = **derived read-projection**. → `Allocation` is a file-first record; `Exposure` is a *pure function of the files*, never stored. |
| **D-2** | rich superset + generic `extra` catch-all (lossless). → new `Allocation` fields are *modeled*, not jammed into `extra`; the catch-all stays the safety net. |
| **D-3** | `_safe_prim_name` sanitizer (no `Tf`). → unchanged; reused for `Allocation` prim names. |
| **D-4** | subtree at `/SYNAPSE/agent/ledger/`. → `Allocation` lands there as a Ledger kind; `Exposure` proposes a sibling or no subtree (§4). |
| **D-5** | file-first, then best-effort USD projection; Moneta optional/off. → unchanged. |
| **D-6** | atomic `write_report` for the primary files; accept the `Save()` gap on derived USD. → unchanged. |

The existing `ledger.LedgerRecord` already projects to USD as a `/SYNAPSE/agent/ledger/<stem>`
`Xform` prim carrying `synapse:<field>` **string attributes** (`ledger.py::_project_to_usd`). That
as-built pattern is the spine the proposals below extend.

---

## §1 — The `verified_by` rung-scale migration

v5 §2 refines the rung scale. This **changes an existing field's allowed values**, so it carries a
migration obligation.

```
v4 (current):   {V0, V1, V1-degraded}
v5 (proposed):  {doc_only, V0_membership, V1_cook, V1_output, V1-degraded}
```

- `doc_only` — **new.** A claim from prose; backs **no** assertion (the scaffold's whole point).
- `V0_membership` ← v4 `V0` (exists per `dir()`/catalog).
- `V1_cook` + `V1_output` ← **split** v4 `V1`. `V1_cook` = executes/cooks, no errors. `V1_output` =
  the eval signal *is* the intended output (a rendered pixel, or a bug reproduced-then-resolved on a
  fresh seed). `flipbook_pixel_verified` is the render-domain instance of `V1_output`.
- `V1-degraded` — unchanged (live unavailable, caveat stated).

### 1.1 Migration — a read shim, NOT a rewrite (D-1 immutability)

The per-record JSON files are immutable (D-1) and the markdown Ledger is append-only. History is
**not** rewritten. A **pure read-time mapping** translates legacy tokens to the v5 scale when a
record is consumed:

```
legacy V0          → V0_membership
legacy V1          → V1_cook        (CONSERVATIVE — never auto-promoted to V1_output)
legacy V1-degraded → V1-degraded
(absent)           → doc_only        (defensive; an unverified record should not have deposited)
```

**The conservative rule is load-bearing:** legacy `V1` collapsed *cook* and *output*. We cannot know
which a historical `V1` was, so it reads as the **weaker** `V1_cook`. A historical claim is **never**
auto-promoted to `V1_output` — output-correctness must be re-earned by a fresh `V1_output`
verification. (This mirrors the Task-B `against_build` cutover I already shipped: legacy entries read
as the conservative tier, source untouched.)

**Where it lives:** a pure function, e.g. `ledger.read_rung(raw_verified_by) -> v5_token`, applied at
*read/projection* time. `deposit()` continues to accept the open string (D-2 keeps `verified_by` an
open field; the validation is "non-empty + non-`against_build`-empty," not a closed enum) so the
migration never blocks a write. The conformance pin (`_conformance.py`) single-sources the five
tokens so a typo can't silently introduce a sixth.

> **Decision for Gold (§3 applies):** the five tokens are *data values*, not a schema location — they
> ship as a single-sourced constant + a DOC-1 conformance pin regardless of the §3 placement choice.
> The shim is logic, not schema. **Recommendation: accept as-is; this part needs no Gold schema call.**

---

## §2 — The `Allocation` entry/prim

The substrate-relevance verdict, first-class so a target **cannot be worked without one** (v5 §2/§3).
Proposed as a **new Ledger kind** (consistent with the existing `Confirmation`/`DeadEnd`/`DocConformance`
/`Deferred`/`SubstrateAssumption`/`CRUCIBLE` kinds), so it inherits the whole D-1..D-6 machinery for
free (file-first SoT, atomic write, USD projection, `extra` catch-all, `_safe_prim_name`).

```
Allocation (LedgerRecord, kind="Allocation")
├── target        : str            # the surface/capability/question under consideration
├── verdict       : token ∈ {admit, downstream, defer}
├── thesis_locus  : str            # authoring | composition | proof(render) | downstream | out-of-scope
├── rationale     : str            # one line: why this verdict, against the substrate thesis
├── decided_by    : token ∈ {gate, operator-override}   # downstream REQUIRES operator-override
└── verified_by   : str            # the verdict is itself an artifact (usually V0_membership)
                                    #   + against_build (Task B: mandatory, fail-closed)
```

**Modeled, not `extra` (D-2).** `target`/`verdict`/`thesis_locus`/`rationale`/`decided_by` become
modeled `LedgerRecord` fields (like the existing DocConformance-only / Deferred-only blocks). They
then auto-project as `synapse:target`, `synapse:verdict`, … via the existing
`_project_to_usd` loop over `_MODELED_ATTRS` — **zero new projection code.**

**The two v5 Ledger-violation guards this enables (enforced by the §3 composer, not this schema):**
- *Violation #6* — a target in the Workflow graph with **no `Allocation`**, or one whose
  `verdict=downstream` lacks `decided_by=operator-override`. The schema makes both states
  *representable and queryable* (`synapse:verdict` + `synapse:decided_by`); the gate enforces.
- The `defer` verdict pairs with a `Deferred` entry (existing kind) — no new machinery.

> **Decision for Gold (§3):** *where* the `Allocation` prim's fields live in USD (namespaced string
> attrs on the ledger prim — the as-built pattern — vs `customData` vs a typed schema) is the §3
> question.

---

## §3 — THE CORE QUESTION: typed USD schema vs `customData` (Gold decides)

This is the one decision that touches substrate conventions and is **Gold's to make.** It applies to
both `Allocation` (§2) and any USD materialization of `Exposure` (§4). Three placement options:

### Option A — `customData` dict on the artifact prim
Author the `Allocation`/rung data as a `customData` dictionary **on the target's own prim** (e.g., the
capability/node/stage prim it allocates).

| | |
|---|---|
| **Queryability** | weak — `prim.GetCustomData()` returns an opaque dict; no per-field `UsdAttribute` query, no `Usd.PrimRange` filtering by value |
| **Schema rigidity** | none — free-form dict; tolerates the `extra` catch-all naturally |
| **Migration cost** | low — no codegen, no plugin; but **co-locates audit data on the artifact**, mixing provenance into the scene-graph prim |
| **Consistency w/ D-1..D-6** | **breaks D-1/D-4** — D-1 says the *file* is SoT and `/ledger/` is the projection; putting it as `customData` on the artifact scatters provenance out of the ledger subtree |

### Option B — Typed USD schema (IsA or single-apply API schema)
Register a `SynapseAllocation` API schema via `usdGenSchema` (the `usd-schema-registration` path),
deploy `generatedSchema.usda` + `plugInfo.json`.

| | |
|---|---|
| **Queryability** | strongest — typed `Get*Attr()`, schema-validated, `HasAPI<SynapseAllocation>()` |
| **Schema rigidity** | high — **fights D-2's `extra` catch-all** (a typed schema rejects unmodeled fields; lossless backfill needs the open dict) |
| **Migration cost** | **high** — codegen + plugin registration + `PXR_PLUGINPATH_NAME` deployment across hython/graphical; a build-and-deploy step, not a data edit |
| **Consistency w/ D-1..D-6** | partial — durable, but the rigidity contradicts D-2; over-engineered for an **append-only audit record** |

### Option C — Namespaced string attributes on a dedicated `/ledger/` prim (the as-built pattern) ★
Exactly what `ledger.py::_project_to_usd` already does: a `/SYNAPSE/agent/ledger/<Allocation_ts_sha8>`
`Xform` prim with `synapse:target`, `synapse:verdict`, `synapse:thesis_locus`, … **string attributes**,
plus `synapse:extra_*` for the catch-all.

| | |
|---|---|
| **Queryability** | good — per-field `UsdAttribute` query by name; `Usd.PrimRange` over `/ledger/` filters by `synapse:verdict` |
| **Schema rigidity** | low/right — open attribute set; the `extra_*` attrs preserve D-2 losslessness |
| **Migration cost** | **near-zero** — `Allocation` is just another Ledger kind; reuses the existing projection loop, sanitizer, atomic writer |
| **Consistency w/ D-1..D-6** | **fully consistent** — file-is-SoT (D-1), under `/SYNAPSE/agent/ledger/` (D-4), `_safe_prim_name` (D-3), atomic files + accepted Save gap (D-6) |

### Recommendation (for Gold to accept / modify / reject)

**Adopt Option C for `Allocation`** — extend the as-built Ledger-projection pattern; it is the only
option fully consistent with D-1..D-6, needs no codegen, and preserves D-2's losslessness. Reserve
**Option A (`customData`)** only if Gold specifically wants allocation data *co-located on the target
artifact* for in-context scene queries (accepting the D-1 scatter). **Reject Option B (typed schema)**
for the Ledger: schema rigidity contradicts the `extra` catch-all and the codegen/deploy cost is
unjustified for append-only audit records — the place for a typed schema, if ever, is a future
read-API over the projection, not the write path.

---

## §4 — The `Exposure` projection (derived, never authored)

`Exposure` maps a capability's **current highest rung → a co-pilot exposure tier** (v5 §8):

| Rung | Exposure tier |
|---|---|
| `doc_only` | not surfaced |
| `V0_membership` | surfaced, marked unverified |
| `V1_cook` | available |
| `V1_output` | trusted / foreground |
| `V1-degraded` | surfaced, caveat shown |

**The decision §4 must make: materialize in USD, or compute-on-read?**

Per **Ledger violation #7** (authoring an exposure tier its rung does not justify is a violation) and
**D-1** (USD is a *derived* projection, never a hand-authored source), `Exposure` should be a **pure
function of the Ledger, computed on read — NOT stored.**

```
exposure(capability) = tier( max_rung( ledger_records_for(capability) ) )
```

- **Recommendation: compute-on-read, no USD materialization.** A pure function (e.g.
  `exposure.tier_for(capability) -> tier`) over the Ledger records. The panel (v5 §8 seam) renders the
  function's output live; there is **no `/exposure/` subtree to fall out of sync.** This makes
  violation #7 *structurally impossible* — you cannot author a tier that doesn't exist as authored
  state.
- **If Gold wants a materialized cache** (e.g. for non-Python USD consumers): a `/SYNAPSE/agent/exposure/`
  subtree that is **regenerated wholesale from the Ledger** on each rebuild (never hand-edited),
  carrying `synapse:capability` + `synapse:tier` string attrs (Option C shape). It must be marked
  derived/regenerable and rebuilt by the same pass that rebuilds `/ledger/` (§5 of the Ledger RFC), so
  it cannot drift. This is a *cache*, not a source; the compute-on-read function remains canonical.

**The capability→rung join is net-new plumbing, not reuse.** `KnowledgeLookupResult`
(`routing/knowledge.py:21-31`) has **no `provenance_status` field** today; the join between a
capability identifier and its highest Ledger rung must be built. This RFC flags it as new work that
the §8 FORGE spec (blocked, §6) will specify — it is **not** a "reuse the KnowledgeIndex" freebie.

---

## §5 — Worked shape (illustrative; not normative until ratified)

An `Allocation{admit}` for the COPs-OpenCL-fix target, projected under Option C:

```
/SYNAPSE/agent/ledger/Allocation_2026_06_08T_..._a1b2c3d4
    synapse:kind          = "Allocation"
    synapse:target        = "cops_reaction_diffusion OpenCL emitter"
    synapse:verdict       = "admit"
    synapse:thesis_locus  = "composition"          # feeds materials → the render
    synapse:rationale     = "substrate-adjacent: COP texture → material → render proof"
    synapse:decided_by    = "gate"
    synapse:verified_by   = "V0_membership"
    synapse:against_build  = "21.0.631"            # Task B: mandatory
    synapse:session        = "Session 2026-06-08 — ..."
```

`Exposure` for that capability is **not** a prim — it is `tier_for("cops_reaction_diffusion")` computed
from the highest rung in its Ledger records (today: `doc_only` → *not surfaced*; after the OpenCL fix
cooks: `V1_cook` → *available*).

---

## §6 — Decided by Gold, not here · what stays blocked until ratification

> **This RFC decides nothing. Michael Gold ratifies, modifies, or rejects the §3 placement (and the §4
> materialize-vs-compute call). No `agent.usd` schema change and no Track-C code ship before that.**

**Blocked until this RFC is ratified:**

1. The **§2 rung-scale-migration FORGE spec** (single-source the five tokens, the `read_rung` shim, the
   `VerifiedClaim` Floor hook for `verified_layer`, the conformance pin).
2. The **§3 allocation-pre-gate FORGE spec** (the per-target gate at the composer head, the
   operator-override path, the self-policing second-pass detector).
3. The **§8 exposure-projection FORGE spec** (the `tier_for` pure function, the capability→rung join,
   the panel render seam, demotion semantics).
4. **All Track-C code** (any writer to `agent.usd` implementing `Allocation`/`Exposure`).
5. The two open v5 §7 sub-questions this RFC surfaces but does not settle: the **allocation-gate
   boundary for substrate-*adjacent* targets** (is "feeds the substrate one hop downstream" `admit` or
   `operator-override`? — procedural-texture generation is the test case), and **exposure demotion
   latency** (vanish immediately vs grey-out-until-session-end; `V1-degraded` foreground vs background
   on a mid-session bridge drop). These are design calls that ride alongside the schema decision.

**Not blocked (ships independently of this RFC):** Track H (A–D), already complete; the Task-B
`against_build` policy, already shipped; the DOC-1 tool-count pins, already shipped.

---

*End of ARCHITECT artifact. This is a proposal for Michael Gold. Allocate at intake, verify on the
floor, surface by the rung — but only after the schema that carries the rung is ratified by the owner
of the substrate's conventions.*
