# RFC — The `agent.usd` Ledger schema

> **Status:** DRAFT (for ratification). Author: CONDUCTOR/INTEGRATOR (agent.usd track).
> **Scope:** the durable provenance Ledger that today lives in markdown + JSONL, and its
> reconciliation to the **already-built** `agent.usd` v2.0.0 prim tree.
> **One-line thesis:** the schema is **already built and pinned**; the work is (1) a new
> `/SYNAPSE/agent/ledger/` subtree that captures every markdown-Ledger field, (2) **wiring**
> the five dormant provenance writers to live emit points, and (3) a durable, one-file-per-record
> persistence model. **No new USD authoring engine is required.**

All file:line citations below were re-verified live against the worktree this session
(2026-06-06). Where a doc disagrees with the code, the **code is ground truth** and the doc is
flagged as a ghost in §2 and §11.

---

## §1 — Problem / Motivation

SYNAPSE accumulates **provenance**: a stream of verified findings — confirmations, dead-ends,
doc-conformance checks, deferred risks — each with a verification tag, the build it was checked
against, the change it drove, and the measured delta. Today that stream lives in **two parallel
non-USD stores**:

1. `docs/SCIENCE_HARNESS_LEDGER.md` — a hand-maintained markdown Ledger. Its own header
   self-declares it **interim**: *"This is the interim home until Phase 0a's `synapse_write_file`
   lands the canonical Ledger in `agent.usd`"* (`docs/SCIENCE_HARNESS_LEDGER.md:3-5`). Append-only;
   `verified_by` is mandatory on every entry (same header).
2. `python/synapse/science/registry.py` — a frozen `Record` dataclass
   (`surface/kind/status/detail/context/timestamp`, `registry.py:8-15`) backed by an append-only
   JSONL file with an in-memory `(surface, kind)` dedup index and a `deposit_fn` seam
   (`registry.py:26-89`).

Meanwhile, CLAUDE.md §6 has **always** specified that provenance is supposed to land in
`agent.usd`, and the `agent.usd` schema **is already implemented** (see §2). The result is a
split brain: the canonical store named in the architecture (`agent.usd`) exists, is pinned by
~50 tests, and is **never fed the provenance stream** — while the provenance stream lives in two
ad-hoc files that the architecture calls "interim."

**This RFC closes that split** by (a) defining the missing `/SYNAPSE/agent/ledger/` subtree so the
markdown Ledger's richer fields have a typed home, (b) naming the live emit points where the
dormant USD writers should be called, and (c) adopting the already-resolved one-file-per-record
durable model so the USD becomes a *composed read-projection* rather than a mutable single file
rewritten on every record.

---

## §2 — Current State

**Lead: the schema is already built; it needs wiring + a ledger subtree.** Three stale doc claims
must be corrected.

### 2.1 What is actually built (verified)

`python/synapse/memory/agent_state.py` (687 lines, `SCHEMA_VERSION = "2.0.0"` at
`agent_state.py:33`) **already implements** the v2.0.0 prim tree via `pxr.Usd / Sdf / Vt`
(`agent_state.py:27`), with:

- a **USDA text fallback** for no-`pxr` environments (`agent_state.py:122-145`), and
- a **v0.1.0 → v2.0.0 migrator** (`migrate_to_v2`, `agent_state.py:164-165`),
- pinned by `tests/test_agent_state.py` (~50 tests including mocked-`pxr` round-trips).

It is **BUILT, not Phase-4-unbuilt.** It authors a **superset** of CLAUDE.md §6: beyond the
documented `/agent`, `/integrity`, `/routing_log`, `/handoff_chain`, `/memory`, it also defines
`/SYNAPSE/agent/tasks/`, `/SYNAPSE/agent/session_history/`, and `/SYNAPSE/agent/verification_log/`
(`agent_state.py:9-14`, `:81-100`).

### 2.2 The real gap: wiring (not authoring)

The provenance writers are **built but dormant — zero live callers**:

| Writer | Defined | Live caller? |
|---|---|---|
| `log_routing_decision` | `agent_state.py:399` | **none** (test-only) |
| `log_handoff` | `agent_state.py:456` | **none** (test-only) |
| `log_integrity` | `agent_state.py:325` | **none** (test-only) |
| `write_verification` | `agent_state.py:585` | **none** (test-only) |
| `create_task` | `agent_state.py:231` | **none** (test-only) |
| `log_session` | `agent_state.py:550` | **LIVE** — `mcp/session.py:198, :208` |
| `suspend_all_tasks` | `agent_state.py:275` | **LIVE** — `mcp/session.py:198, :207` |
| `initialize_agent_usd` | `agent_state.py:61` | **LIVE** — `scene_memory.py:136-137, :963-964` |

Consequence: the `routing_log`, `handoff_chain`, and `integrity` prims are authored **empty** at
init (`agent_state.py:90-100`) and **never populated** in production. The schema is a fully-built
container with no inflow on the audit branches.

### 2.3 Doc ghosts to correct (RECOMMENDED side-fixes — do NOT edit CLAUDE.md in this branch)

| # | Ghost | Location | Correction |
|---|---|---|---|
| G1 | `agent.usd Schema  🔶 Phase 4  —  —` (claims unbuilt) | `CLAUDE.md:812` (Status table) | It is **built + pinned**. Mark `✅ Built (needs wiring)`, file `python/synapse/memory/agent_state.py`, ~687 lines. |
| G2 | `Files: src/memory/agent_state.py, src/memory/agent_schema.usda` | `CLAUDE.md:523` (§9 Phase 4) and §14 file tree | Real path is `python/synapse/memory/agent_state.py`. **`agent_schema.usda` does not exist** — the USDA is generated inline (`agent_state.py:122-145`). |
| G3 | `Tf.MakeValidIdentifier` claimed for agent.usd path | CLAUDE.md §12 import-guards / §16 (R3 references `Tf`) | `agent_state.py` imports only `from pxr import Usd, Sdf, Vt` (`agent_state.py:27`) — **no `Tf`** — and hand-rolls `_safe_prim_name` (`agent_state.py:41`). The `Tf.MakeValidIdentifier` claim is true for `evolution.py` only, not `agent_state.py`. |

*(G3 nuance: the doc's `Tf` claim is correct for the Pokémon-evolution path. `evolution.py` is
where `Tf` would belong; `agent_state.py` deliberately avoids it. The RFC's §10 prim-name
decision picks ONE sanitizer to end the ambiguity.)*

### 2.4 Durability gap (verified)

Every `agent_state.py` writer ends with `stage.GetRootLayer().Save()` (e.g. `:112, :223, :244,
:364, :425, :481, :579, :603`) — a **full-file rewrite with no atomicity and no backup**. A crash
mid-`Save()` can truncate the only copy. Contrast: the durable write primitive
`python/synapse/cognitive/tools/write_report.py` (161 lines, **zero `hou`**) writes
**atomically** (tmp + `fsync` + `os.replace`, `write_report.py:132-148`) with optional
**generational backups** (`<name>.bak.1..N`, `write_report.py:83-97`). `agent_state.py` does
**not** use it. §6 addresses this.

---

## §3 — Target Schema

### 3.1 CLAUDE.md §6 — quoted verbatim

```
/SYNAPSE/agent/
    status, current_plan, dispatched_agents
/SYNAPSE/agent/integrity/
    session_fidelity, operations_total, operations_verified, anchor_violations
/SYNAPSE/agent/routing_log/
    decision_NNNN → fingerprint, primary_agent, advisory_agent, method, timestamp
/SYNAPSE/agent/handoff_chain/
    handoff_NNNN → from_agent, to_agent, task_id, fidelity_at_handoff
/SYNAPSE/memory/
    sessions/, decisions/, assets/, parameters/, wedges/
```

### 3.2 Reconciled to the as-built superset (ground truth)

The implemented tree is a strict **superset** of §3.1. Verified attribute names per writer:

```
/SYNAPSE/agent/                       status, current_plan, dispatched_agents
/SYNAPSE/agent/tasks/                 task_NNNN              (create_task, agent_state.py:231)
/SYNAPSE/agent/integrity/             synapse:session_fidelity, synapse:operations_total,
                                      synapse:operations_verified, synapse:anchor_violations
                                                             (log_integrity, agent_state.py:325-364)
/SYNAPSE/agent/routing_log/           decision_NNNN → synapse:fingerprint, synapse:primary_agent,
                                      synapse:advisory_agent, synapse:method, synapse:timestamp
                                                             (log_routing_decision, :417-423)
/SYNAPSE/agent/handoff_chain/         handoff_NNNN → synapse:from_agent, synapse:to_agent,
                                      synapse:task_id, synapse:fidelity_at_handoff, synapse:timestamp
                                                             (log_handoff, :473-479)
/SYNAPSE/agent/session_history/       session_NNNN           (log_session, agent_state.py:550)
/SYNAPSE/agent/verification_log/      verify_* → synapse:taskId, synapse:beforeState,
                                      synapse:afterState, synapse:checks, synapse:result
                                                             (write_verification, :597-601)
/SYNAPSE/memory/                      sessions/, decisions/, assets/, parameters/, wedges/
                                                             (evolution.py, charmeleon)
```

Three prim groups (`tasks`, `session_history`, `verification_log`) and their attributes are
**not documented in CLAUDE.md §6** but are real. The §6 doc should be widened to the as-built
shape (recommended doc side-fix, not in this branch).

### 3.3 NEW subtree — `/SYNAPSE/agent/ledger/`

The markdown Ledger carries **strictly more structure** than any existing prim group. None of
`routing_log` / `handoff_chain` / `verification_log` can hold a `DocConformance` or a `Deferred`
record without lossy coercion. So this RFC adds a **dedicated ledger subtree**, one prim per
record, named `<kind>_<ts>_<sha8>` (mirroring the durable filename in §5):

```
/SYNAPSE/agent/ledger/
  <kind>_<ts>_<sha8>  (Xform) →
    # ── universal fields (every Ledger kind) ──
    synapse:kind            String   # Confirmation | DeadEnd | DocConformance | Deferred | Decision
    synapse:verified_by     String   # MANDATORY — e.g. "V1". Empty → record is INVALID (see §11).
    synapse:against_build   String   # e.g. "21.0.631"   (LEDGER.md:16)
    synapse:change_applied  String   # what the finding drove   (LEDGER.md:61, :87, :101)
    synapse:measured_delta  String   # before/after evidence    (LEDGER.md:19, :62, :88)
    synapse:artifact_path   StringArray  # files/probes touched  (LEDGER.md:63, :89, :103)
    synapse:question        String   # the probe question
    synapse:timestamp       String   # ts (ISO)
    # ── DocConformance-only fields (LEDGER.md:38-44) ──
    synapse:claim_locus     String   # where the doc claim lives (e.g. "CLAUDE.md:812")
    synapse:code_locus      String   # where the ground truth lives
    synapse:bound_by        String   # "value" | "presence" | ...
    synapse:holds           Bool     # does the claim hold against code?
    # ── Deferred-only fields (LEDGER.md:46-49) ──
    synapse:stakes          String   # "high" | "medium" | "low"
    synapse:probed          Bool     # has it been investigated?
```

Field provenance is the markdown Ledger itself: universal fields appear on every entry; the
`DocConformance` block (`claim_locus / code_locus / bound_by / holds`) is verified at
`docs/SCIENCE_HARNESS_LEDGER.md:38-44`; the `Deferred` block (`stakes / probed`) at
`docs/SCIENCE_HARNESS_LEDGER.md:46-49`. `verified_by` mandatory is the LEDGER header rule
(`:3-5`).

**Rationale for a new subtree (not overloading an existing one):** `routing_log` is keyed by
routing fingerprint, `verification_log` by task; neither has slots for `verified_by`,
`against_build`, or the DocConformance quad. A flat `ledger` group with a uniform universal
field-set + kind-specific extensions is the minimum schema that is lossless against the markdown
source. Optional kind-specific fields are simply absent on prims of other kinds (USD attributes
are optional by construction).

---

## §4 — Session Grouping

The markdown Ledger is organized by **session headers** of the form
`## Session 2026-06-05 — Phase 0.0 · CONFIRM THE POSTURE … TRACK H`
(`docs/SCIENCE_HARNESS_LEDGER.md:9`, `:53`). These map directly to the **already-built**
`/SYNAPSE/agent/session_history/` group (`agent_state.py:97`, `log_session` at `:550`):

```
/SYNAPSE/agent/session_history/
  session_NNNN (Xform) →
    synapse:date         "2026-06-05"
    synapse:phase        "Phase 0.0 · CONFIRM THE POSTURE"
    synapse:track        "TRACK H"
    synapse:summary_text  …      (existing log_session field, mcp/session.py:212)
```

Each `/SYNAPSE/agent/ledger/<...>` prim then carries a `synapse:session` **relationship** (USD
`Sdf.ValueTypeNames` relationship or a string foreign-key) back to its `session_NNNN` prim, so a
session's findings are a queryable set without duplicating session metadata onto every record.
This is a pure read-grouping; it changes none of the existing `log_session` behavior, only adds
the back-link from new ledger records.

---

## §5 — Persistence / Append Model

**Adopt the already-resolved one-file-per-record model.** The append-model fork was settled in
`docs/SCIENCE_HARNESS_PHASE0A_SPEC.md §6` (`:222-241`): **option (a)+(c), composed.**

- **(a)** Each durable Ledger record is **one immutable file** `<kind>_<ts>_<sha8>.json`, written
  via the atomic write primitive to `root="ledger"` (`PHASE0A_SPEC.md:227-228, :235-236`). No
  shared growing file → no lost-update race, no O(n) full-rewrite.
- **(c)** `registry.py`'s append-only JSONL stays as the **in-session dedup index** the registry
  rebuilds itself from (`PHASE0A_SPEC.md:230-231, :237-239`); the `deposit_fn` is the seam that
  forwards each record to the durable per-record file (and/or Moneta).
- **Option (b) (give `write_report` an append mode) was explicitly rejected** — it would surrender
  the atomic-replace guarantee on the one path that must never fail (`PHASE0A_SPEC.md:232-234`).

**Recommendation for `agent.usd`:** make `agent.usd` a **composed read-projection**, not the
source of truth. The durable per-record JSON files are the source of truth; `agent.usd` is
**rebuilt from them** (sublayer / reference composition — the same mechanism the Pokémon
**charizard** stage uses for cross-scene references, CLAUDE.md §6). This means:

- A corrupt or deleted `agent.usd` is **always reconstructable** by replaying the per-record files.
- The `Save()` durability gap (§2.4) on `agent.usd` becomes **non-fatal**: the USD is derived, not
  primary.
- Writes are **append-by-new-file**, never in-place mutation of a large USD — matching the
  per-record file model end to end.

This mirrors the §6 Phase-0a "bonus": **identical file model to Tier-0 Floor provenance**
(`PHASE0A_SPEC.md:240-241`) — one mental model, one read tool across both tiers.

---

## §6 — Durability Seam

**Route all durable Ledger writes through `write_report`'s atomic+backup path.** Concretely:

- The **per-record `<kind>_<ts>_<sha8>.json`** files (§5) are written with
  `write_report(relative_path=…, content=…, base_dir=<ledger root>, backups=N)` — atomic
  (`write_report.py:132-148`) and generationally backed up (`write_report.py:83-97`). This is the
  durable substrate the LEDGER header points at (`LEDGER.md:3-5`).
- The **derived `agent.usd`** read-projection is rebuilt from those files. Because it is derived,
  its `Stage.Open → RootLayer.Save()` full-rewrite (§2.4) is an **accepted gap**: a crash mid-Save
  loses only the projection, which is regenerable. We document the gap rather than rewrite
  `agent_state.py`'s save path.
- **Alternative considered (and recommended only if the projection model is rejected):** if
  `agent.usd` must remain a primary mutable store, then `agent_state.py` should write to a
  sidecar temp file and `os.replace` onto `agent.usd` — i.e. adopt `write_report`'s atomic-replace
  discipline for the `.usd` itself. This is more invasive and is **not** the recommended path;
  the projection model (§5) makes it unnecessary.

---

## §7 — Wiring Plan

Two layers need wiring: (i) the **dormant USD writers** to live emit points, and (ii) the
**durable deposit** via the registry seam.

### 7.1 Dormant writers → live emit points

| Writer (dormant) | Natural live emit point |
|---|---|
| `log_routing_decision` (`agent_state.py:399`) | After `MOERouter.route()` resolves a fingerprint (the panel/`RoutingLog` layer already exists per CLAUDE.md §2.3; route its output here). |
| `log_handoff` (`agent_state.py:456`) | On every `AgentHandoff.verify()` success (CLAUDE.md §5 handoff protocol). |
| `log_integrity` (`agent_state.py:325`) | In Stage-5 VERIFY, once per `IntegrityBlock` (CLAUDE.md §3 pipeline). |
| `write_verification` (`agent_state.py:585`) | Same VERIFY stage, per task verification. |
| `create_task` (`agent_state.py:231`) | On task dispatch (Stage-3 PLAN / dispatch). |

Already live (do not re-wire): `log_session` + `suspend_all_tasks` at `mcp/session.py:198,207,208`;
`initialize_agent_usd` at `scene_memory.py:136-137,963-964`.

### 7.2 Durable deposit via the registry seam (cross-ref 0a-prime)

The new **ledger** records flow through `registry.py`'s `deposit_fn` (`registry.py:26, :86-87`):
`deposit_fn(asdict(rec))` should call `write_report` to land the per-record file (§6) **and** emit
the corresponding `/SYNAPSE/agent/ledger/` prim. `deposit_fn` is currently `None` at the science
entrypoint (per memory: "deposit_fn still =None at science entrypoint"), so this is a one-line
seam to fill — not new plumbing.

**Tier-0 funnel note:** the Phase-0a-prime spec resolves the **emit-time Floor hook** to a
new `CommandHandlerRegistry.invoke(cmd_type, payload, ctx)` primitive through which all three
invocation sites route (`PHASE0A_SPEC.md:266-271`). **This is spec'd but UNBUILT:** the live
`CommandHandlerRegistry` (`handlers.py:208`) today exposes `handle()` (`handlers.py:303`) and has
**no `invoke` method**. When `invoke()` lands, it is the natural unconditional emit point for
Tier-0 provenance — and the ledger writers in §7.1 can hang off the same funnel rather than being
scattered across call sites. Until then, wire §7.1 at the named pipeline stages.

---

## §8 — Migration (one-time backfill)

A one-time backfill converts the existing markdown Ledger into per-record files + prims:

1. **Parse** `docs/SCIENCE_HARNESS_LEDGER.md` into records. Reuse the markdown parser already
   built for memory: `evolution.parse_markdown_memory` (`evolution.py:118`) handles
   session/decision/parameter blocks; extend its block recognizer to the Ledger's
   `kind/verified_by/...` bullet format (the Ledger uses `**field:** value` bullets, a
   close cousin of the memory format).
2. **Emit one durable file per parsed record** (`<kind>_<ts>_<sha8>.json`, §5) via `write_report`.
3. **Compose** them into `agent.usd` under `/SYNAPSE/agent/ledger/` (§5 projection rebuild).
4. **Schema migration** of any pre-existing `agent.usd`: reuse `migrate_to_v2`
   (`agent_state.py:164`) to bring v0.1.0 stages to v2.0.0 before composing the ledger subtree in.
5. **Verify** round-trip fidelity = 1.0 (§11) before retiring the markdown Ledger to read-only
   archive. The markdown stays as an immutable backup (mirrors evolution's PRESERVE stage,
   CLAUDE.md §6).

No record is dropped: the markdown is the source for the backfill and is preserved after it.

---

## §9 — Composition with the Pokémon stages + Moneta

- **Pokémon stages.** `evolution.py` authors `/SYNAPSE/memory/` (sessions/decisions/assets/
  parameters) under the **same `synapse:` attribute namespace** the ledger uses (verified:
  `evolution.py:249-271` all use `synapse:*`). The ledger subtree therefore composes cleanly
  alongside `/SYNAPSE/memory/` in one stage — no namespace collision. The **charizard** tier's
  composition arcs (CLAUDE.md §6) are exactly the mechanism §5 leans on to make `agent.usd` a
  read-projection of per-record sublayers.
- **Moneta.** Moneta is SYNAPSE's memory substrate but is **default-OFF** (jsonl is the live
  default; `SYNAPSE_MEMORY_BACKEND=moneta|shadow` flips it). The ledger seam therefore must work
  with Moneta off: the per-record files (§5/§6) are the **degraded-mode** substrate, exactly as
  Phase-0a §7 specifies (*"prefer Moneta when enabled; fall back to `synapse_write_file` when
  Moneta is default-off (current state, v5.10.0)"*, `PHASE0A_SPEC.md:254-259`). `deposit_fn`
  forwards to Moneta **and/or** the per-record file; with Moneta off, the file path is canonical.

---

## §10 — Open Decisions (each with a recommendation)

| # | Fork | Options | **Recommendation** |
|---|---|---|---|
| D-1 | Canonical store | per-record files vs `agent.usd` vs JSONL | **Per-record JSON files are source-of-truth; `agent.usd` is a composed read-projection** (§5). Reason: reconstructable, durable, append-by-new-file. |
| D-2 | Record-schema unification | richer markdown superset vs lean `registry.Record` | **Unify on the richer markdown superset** (§3.3). `registry.Record` (`registry.py:8-15`) is a subset; widen it (or wrap it) to carry `verified_by/against_build/change_applied/measured_delta/artifact_path` rather than truncate the markdown. |
| D-3 | Prim-name sanitizer | `agent_state._safe_prim_name` vs `Tf.MakeValidIdentifier` | **Pick `_safe_prim_name`** (`agent_state.py:41`) for the ledger subtree — it is the sanitizer the agent.usd writers already use and needs no `Tf` import on the agent.usd path. (`evolution.py` may keep `Tf` independently; G3 only asks the docs to stop claiming `Tf` for `agent_state.py`.) |
| D-4 | Ledger subtree placement | `/SYNAPSE/agent/ledger/` vs reuse `verification_log` vs top-level | **`/SYNAPSE/agent/ledger/`** (§3.3). Keeps audit/provenance under `/agent/` with the other audit groups; avoids overloading `verification_log` (task-keyed) or `routing_log` (fingerprint-keyed). |
| D-5 | Moneta-first vs USD-first deposit | write Moneta then project to USD, or write USD then mirror to Moneta | **File-first, then both project to USD and (optionally) deposit to Moneta.** With Moneta default-off, the per-record file must be the unconditional write; Moneta is an enrichment when enabled (§9). |
| D-6 | Durability routing | route USD writes through `write_report` atomic path, or accept the `Save()` gap | **Accept the gap on the *derived* `agent.usd`; require atomic `write_report` only for the *primary* per-record files** (§6). The projection model makes the USD non-load-bearing for durability. |

---

## §11 — Acceptance Pins

A new test module (suggested `tests/test_agent_usd_ledger.py`) pins the contract. All pins must
hold headlessly with **no `hou` import** (the ledger path is non-Houdini), and must also pass in
the no-`pxr` fallback mode.

1. **Round-trip fidelity = 1.0 per kind.** For each Ledger kind
   (`Confirmation`, `DeadEnd`, `DocConformance`, `Deferred`, `Decision`): build a record → author
   the `/SYNAPSE/agent/ledger/<...>` prim → read it back → assert **byte-identical** field values
   (string attributes compared verbatim, including embedded slashes/quotes/newlines, which native
   USD typing preserves).
2. **Mandatory `verified_by`.** A record with empty/missing `verified_by` is **rejected** at
   deposit (mirrors the LEDGER header rule, `LEDGER.md:3-5`). Pin: deposit of a `verified_by=""`
   record raises / returns failure and writes **no** file and **no** prim.
3. **One-file-per-record.** Depositing N records produces N immutable
   `<kind>_<ts>_<sha8>.json` files; re-depositing the same `(kind, ts, sha8)` is a **no-op**
   (idempotent, dedup-indexed — mirrors `registry.record()` returning `False` on a known key,
   `registry.py:66-74`). No file is mutated in place.
4. **No-`pxr` fallback.** With `pxr` unavailable, the durable per-record files still write
   (atomic via `write_report`) and the ledger read-path degrades to reading the JSON files
   directly — the deposit path never raises on missing `pxr`.
5. **Composition projection.** Deleting `agent.usd` and rebuilding from the per-record files
   reproduces the `/SYNAPSE/agent/ledger/` subtree identically (source-of-truth = files, §5).
6. **Doc-conformance pin (fails loud on the stale Status row).** A pin asserts the as-built
   reality so a future revert of the doc fix re-breaks the test:
   - assert `agent_state.SCHEMA_VERSION == "2.0.0"`,
   - assert `agent_state.py` does **not** import `Tf` (G3),
   - assert the CLAUDE.md Status row for `agent.usd` is **not** `🔶 Phase 4` once G1 is applied
     (the pin reads `CLAUDE.md:812` and fails if it still says "Phase 4" after ratification),
   - assert `src/memory/agent_schema.usda` does **not** exist and the inline USDA fallback does
     (G2).

---

## Required doc side-fixes (RECOMMENDED — not applied in this branch)

The following CLAUDE.md corrections are **described here for the human to ratify and apply**. This
RFC branch does **not** edit CLAUDE.md.

- **G1 — Status row** (`CLAUDE.md:812`): change
  `| agent.usd Schema | 🔶 Phase 4 | — | — |` →
  `| agent.usd Schema | ✅ Built (needs wiring) | python/synapse/memory/agent_state.py | ~687 |`.
  The schema is built and pinned by `tests/test_agent_state.py`; "Phase 4 / unbuilt" is false.
- **G2 — §9 Phase 4 file path** (`CLAUDE.md:523`) and the §14 file tree: replace
  `src/memory/agent_state.py, src/memory/agent_schema.usda` with the real path
  `python/synapse/memory/agent_state.py`, and **delete the `agent_schema.usda` reference** — no
  such file exists; the USDA is generated inline (`agent_state.py:122-145`).
- **G3 — `Tf` ghost** (CLAUDE.md §12 import guards / §16 R3 as it pertains to agent.usd): the
  `Tf.MakeValidIdentifier` claim is correct for `evolution.py` but **not** for `agent_state.py`,
  which imports only `Usd, Sdf, Vt` (`agent_state.py:27`) and uses `_safe_prim_name`
  (`agent_state.py:41`). Qualify the doc so it does not imply `agent_state.py` uses `Tf`.
- **§6 schema widening** (optional): document the three as-built prim groups not in §6 —
  `/SYNAPSE/agent/tasks/`, `/session_history/`, `/verification_log/` — plus the new
  `/SYNAPSE/agent/ledger/` from this RFC.

---

## Appendix — Verified citation index

Every file:line in this RFC was re-read this session. Key anchors:

- `agent_state.py:33` `SCHEMA_VERSION = "2.0.0"`; `:27` `from pxr import Usd, Sdf, Vt` (no `Tf`);
  `:41` `_safe_prim_name`; `:61` `initialize_agent_usd`; `:164` `migrate_to_v2`;
  `:231` `create_task`; `:275` `suspend_all_tasks`; `:325` `log_integrity`;
  `:399` `log_routing_decision`; `:456` `log_handoff`; `:550` `log_session`;
  `:585` `write_verification`; `:81-100` empty audit prims authored at init;
  `:122-145` inline USDA fallback; `Save()` per write at `:112/:223/:244/:364/:425/:481/:579/:603`.
- `mcp/session.py:198,207,208` live `log_session` + `suspend_all_tasks` callers.
- `scene_memory.py:136-137, 963-964` live `initialize_agent_usd` callers.
- `evolution.py:118` `parse_markdown_memory`; `:249-271` `synapse:*` namespace shared.
- `write_report.py:83-97` backups; `:132-148` atomic write; zero `hou`.
- `registry.py:8-15` `Record`; `:26,86-87` `deposit_fn` seam; `:66-74` dedup `record()`.
- `docs/SCIENCE_HARNESS_LEDGER.md:3-5` interim header + mandatory `verified_by`;
  `:16` `against_build`; `:38-44` DocConformance fields; `:46-49` Deferred fields;
  `:61/:87/:101` `change_applied`; `:63/:89/:103` `artifact_path`; `:19/:62/:88` `measured_delta`.
- `docs/SCIENCE_HARNESS_PHASE0A_SPEC.md:222-241` append-model resolved (a)+(c);
  `:254-259` Moneta-fallback; `:266-271` `registry.invoke()` Tier-0 funnel (spec'd, unbuilt).
- `handlers.py:208` `CommandHandlerRegistry`; `:303` `handle()` — **no `invoke()`** today.
- `CLAUDE.md:523` §9 stale path; `:812` stale `🔶 Phase 4` Status row.
