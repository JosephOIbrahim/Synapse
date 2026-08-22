# MEMORY BOARD — Spec

> Executes the amended *"Refactor SYNAPSE Memory Sub-System (LOOP v5.1)"* spec.
> Adjudication: `harness/memory/notes/BLUEPRINT_ADJUDICATION.md`.
> Evidence: `harness/memory/notes/AUDIT_2026-08-21.md`.
> Law: `AGENTS.md` (agent conduct) + `harness/loop/SPEC.md` (ladder law) + `CLAUDE.md`.

---

## What this board is, and what it is not

**It is a substrate-conformance board.** It proves the Moneta laws hold in live
SYNAPSE code and builds the deterministic pieces of PG-DRM that need no absent
substrate.

**It is NOT a LOOP rung and it does not re-sort the ladder.** The LOOP ladder
(`harness/loop/STATE.json`) is ratified. This board is a *sidecar* whose closed
rungs become **preconditions** that LOOP V0.2 consumes when SALUS and Hanish land.

**Boundary:** this board writes only under `harness/memory/`, `python/synapse/memory/`,
`python/synapse/loop/`, `tests/`, and `docs/`. It reads `harness/loop/` and never
writes it. `loop-orchestrator` owns that board; `memory-conductor` owns this one.

---

## The ladder (never re-sorted; a rung closes or it does not)

| Rung | Scope | Substrate needed | Gate to next |
|---|---|---|---|
| **M0** Audit | Legacy inventory, disposition per site, handle-authority census, panel call-site classification. | none | Every claim carries a path:line; `could_not_verify` written. **CLOSED 2026-08-21.** |
| **M1** Handle law | Make "one handle per storage URI, one owner" true in the code that actually runs. Fix the unlocked `get_synapse_memory()`; reconcile the two authorities; a URI-keyed registry, not a scalar. | **Moneta (live)** | A concurrency test that goes red on the current code and green after; both authorities named in one place; no third authority added. |
| **M2** PG-DRM kernel | `pgdrm.py` — a pure, deterministic, zero-LLM filter: `U = e^{−λt}` decay, exact-token contamination, vector-distance threshold. No port wiring, no substrate. | none | Hand-computed decay table passes; every branch exercised; a mutation proves each test bites. |
| **M3** Substrate scaffolds | Per-substrate degradation contract for Hanish (outbox), Octavius (narrowed read + capability flag), SALUS (fail-closed) + the V0.2 contract-amendment proposal. Papers only. | none | Each scaffold names its shape, its drain path, and its ratification gate. |
| **M4** Legacy retirement | Rename the surface, keep the reader, migrate the data. Retire the `evolve_memory` *verb*; rename `approval_token` → `plan_token`. | none | **HUMAN GATE** — removing a registered MCP tool is a public API break. |

**Explicitly out of scope (belongs to LOOP V0.2/V0.3, gated):** wiring PG-DRM
into `MemoryPort.query_and_filter`; any `deposit_settlement` that returns
`SUCCESS`; `wake_scene_relations` over real USD relations.

---

## The team (they talk over `bus/`, never by telepathy)

| Agent | Role | Writes |
|---|---|---|
| **memory-conductor** | Read-only conductor. Sequences one rung per dispatch, owns the spawn ledger, halts at every human gate. Runs nothing itself. | `STATE.json`, `bus/` |
| **moneta-cartographer** | Read-only census. Handle authorities, call graphs, thread ownership, legacy sites. Finds; never fixes. | `bus/`, `notes/` |
| **moneta-forge** | M1 implementer. Worktree, one atomic commit, never merges. Owns `python/synapse/memory/`. | code + tests |
| **pgdrm-kernel-forge** | M2 implementer. Pure kernel + hand-computed tables. Owns `python/synapse/loop/pgdrm.py`. Never touches port signatures. | code + tests |
| **substrate-envoy** | M3 author. Designs how SYNAPSE connects to Hanish / Moneta / Octavius, honestly, before they exist. Papers only. | `notes/`, `docs/` |
| **memory-crucible** | Adversarial. Hunts fabricated SUCCESS, tests that cannot fail, expectations copied from the brief, and the second-action regression. Did not build it. | `bus/` |

**File ownership is exclusive-write.** `moneta-forge` never edits
`python/synapse/loop/`; `pgdrm-kernel-forge` never edits
`python/synapse/memory/`. Collisions route through the conductor.

---

## Board law

1. **`AGENTS.md` applies in full.** The Seven Laws are not restated here; they bind.
2. **Absence has a shape** (`AGENTS.md` §2). Read-side narrows, write-side
   outboxes, gate-side fails closed. Nothing fabricates SUCCESS.
3. **Two authorities is worse than none.** No rung on this board may add a store
   singleton without first reconciling `store.py:1514` and `ledger.py:320`.
4. **The ratified §4 port surface does not move without Joe's word.** New
   parameters live on the kernel until the contract amendment is ratified.
5. **A rung closes on evidence, not on a leg reporting done.** Crucible attacks
   every rung before it is written closed.
6. **Falsification watch.** Two bookkeeping-only rungs in a row → stop, say the
   board is spinning.
7. **Spawn ledger is cross-run.** `spawned + budget > (spawn_cap − reserve)`
   refuses the dispatch.

---

## Run protocol

1. **Orient** — read `STATE.json`; `git status --porcelain`; `git worktree list`;
   check `bus/` mtimes for a live second conductor.
2. **Dispatch one rung** — `Workflow(name: 'memory-loop', args: {rung, date,
   autonomy, spawnedSoFar, armed: true})`. `armed` is per-run, never banked.
3. **Reconcile** — fold the returned `spawned` count into `STATE.json`; append
   the log entry; refresh the dashboard.
4. **Halt** — if the run returns `needs_joe` non-empty, present it verbatim and stop.

## Dashboard

```
python harness/memory/dashboard.py            # full board
python harness/memory/dashboard.py --bar      # one-line status bar
python harness/memory/dashboard.py --json     # machine readable
```
