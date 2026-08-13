# SYNAPSE Memory Harness — Development Blueprint

**Audience:** A Claude Code session (or a senior engineer) updating the SYNAPSE harness.
**Grounding:** Written from first principles + the live `synapse_doctor` snapshot (2026-08-13).
**Goal:** Get memory to a *honestly production* state — where what the doctor reports is what is actually true — and lay out the next stage of evolution.

---

## 0. The coffee-shop version

Picture memory as a notebook on a bench in a park.

Right now we have a *good paper notebook* (the JSONL backend). It's always there, it never crashes, and it's easy to read. But:
- It's a single stack of pages — you can't have two people reading and writing different pages at once safely.
- Nothing is typed — a page that says "roughness = 0.5" is just ink; a program can't tell whether that's a float, a color, or a note.
- It grows by just adding pages forever; nobody ever consolidates the repeats.

We've built a *fancier storage cabinet* (the Moneta/USD backend) — nicer drawers, labeled slots, proper types. The cabinet itself exists and is registered. **But it's still empty** — we haven't moved a single page out of the paper notebook into the cabinet. So all our real memory still lives in the paper notebook, and the doctor honestly tells us so.

The entire blueprint below is: **make the cabinet actually usable, move the pages over safely without losing any, and only then declare victory.**

---

## 1. What the doctor actually told us (the real current state)

Parsed from the live snapshot — don't trust the color of the checks, read what they say:

| Check | Verdict | Honest meaning |
|---|---|---|
| `moneta_substrate` | **fail** | The Moneta backend is *registered* (schema resolves) but **no USD stage exists** at `cortex_root.usda`. So `in_use = None`. The store claims Moneta but has no real store. **This is the crux.** |
| `moneta_consolidation` | skipped | "store is not Moneta-backed" → live backend is JSONL, so consolidation is a no-op. |
| `vector_recall` | skipped | Same — no real store, so no vectors. |
| `use_real_usd` | skipped | Same. |
| `memory_key_fingerprint` | skipped | `no_sidecar` — no fingerprint sidecar file, so nothing to compare. |
| `symbol_table` | **ok** | Houdini symbol table stamped 22.0.400 matches running build — **no phantom-API risk here.** |
| `bridge_endpoint` / `mcp_coexistence` / `main_thread` / `houdini` | **ok** | The harness itself is healthy: bridge up, no foreign MCP ports, main thread not stalled, Houdini reachable. |
| `_integrity` | solid | scene hash stable, undo/consent/thread all true. |

**Net read:** the *harness* (the transport, the safety rails, the node graph grounding) is healthy. The *memory store* is the one thing holding us back — and it's not broken, it's **unbuilt**. That's a much better position to be in than "broken": it means the work is additive and safe.

---

## 2. First principles — what memory actually has to do

Before writing code, pin down the invariants a memory system must satisfy. Everything in this blueprint is judged against these.

**P1. Durable.** If Houdini or the bridge dies, memory survives on disk.
**P2. Queryable.** "Give me what we learned about Karma settings" returns the relevant pages, not the whole notebook.
**P3. Typed / structured.** A decision, a note, a reference, and a task are *different kinds* of things with different fields — a program can route on the type.
**P4. Composable.** Layers of memory (project vs scene vs session) combine the way USD layers do — stronger opinions win, nothing is lost.
**P5. Honest.** The doctor reports what is *actually true* at this moment. If the cabinet is empty, it says "empty", not "healthy".
**P6. Safe to evolve.** Moving from JSONL → USD must never destroy a memory. Migration is copy-and-verify, never cut-over-and-pray.
**P7. Consolidatable.** Old/repeated memories can be merged/pruned without losing the information content.

The Moneta/USD backend was built to satisfy P3, P4, P5, P7 better than JSONL can. It just isn't *materialized* yet.

---

## 3. Target architecture (what "done" looks like)

```
                    ┌──────────────────────────────┐
                    │   MemoryStore (interface)    │
                    │  P1-P7 invariants enforced   │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
   ┌──────────▼──────────┐                  ┌───────────▼──────────┐
   │   JSONL backend     │   (fallback)     │   Moneta backend     │  (primary)
   │  always available   │                  │  real USD stage:     │
   │  simple, robust     │                  │  cortex_root.usda    │
   │  P1,P2 only         │                  │  P1-P7               │
   └─────────────────────┘                  └───────────┬──────────┘
                                                        │
                                ┌───────────────────────┼───────────────┐
                                │                       │               │
                        ┌───────▼──────┐        ��───────▼──────┐  ┌──────▼─────┐
                        │  Typed prims │        │  Vector idx  │  │  Consol.   │
                        │  per memory  │        │  for recall  │  │  / pruning │
                        │  kind        │        │  (P2)        │  │  (P7)      │
                        └──────────────┘        └──────────────┘  └────────────┘
```

**Key architectural decision:** the two backends are **siblings behind one interface**, not a replacement chain. JSONL never disappears — it's the safety net. Moneta is the upgrade. A memory written is written to whichever backend is active; the doctor reports which one is *actually* in use, so there's no ambiguity.

---

## 4. The migration — phase by phase (each phase is independently verifiable)

### PHASE 0 — Harden the honest signal (cheap, do first)
**Problem:** `in_use` is `None` and consolidation/vector checks say "not Moneta-backed", but the store also *claims* `backend: moneta`. Two conflicting signals.

**Work items:**
- [ ] Make `moneta_substrate`'s `in_use` resolve deterministically: either materialize the stage, or report `backend: jsonl` (not `moneta`) until it truly is. **The store must not claim a backend it isn't actually using.**
- [ ] Write the missing `cortex_root.usda` stage at first Moneta init (a minimal typed root, see Phase 1), so `in_use` is a real check, not an "unresolvable".
- [ ] Make `memory_key_fingerprint` write a sidecar on first use so `no_sidecar` becomes `ok` (a fingerprint to detect tamper/corruption).
- [ ] **Definition of done:** doctor shows `moneta_substrate: ok` **OR** cleanly `jsonl` — never "unknown".

### PHASE 1 — Materialize a minimal Moneta store
**Problem:** schema is registered but no typed prims can be demonstrated.

**Work items:**
- [ ] At Moneta init, create `cortex_root.usda` with a valid `MonetaMemory` root prim and a version attribute.
- [ ] Implement write: each `synapse_memory_write` becomes a typed USD prim under the root, keyed by (kind, id).
- [ ] Implement read: `synapse_memory_query` walks the typed prims.
- [ ] Keep JSONL writes **in parallel** (dual-write) for this entire phase so nothing is at risk.
- [ ] **Definition of done:** write a memory, doctor shows `moneta_substrate: in_use=True`, read it back via query.

### PHASE 2 — Typed schema, routing on kind (the real payoff)
**Problem:** JSONL can't route by type. USD can.

**Work items:**
- [ ] Define the schema fields per kind (note / context / reference / task / decision), so the harness can filter and route without string matching.
- [ ] `synapse_recall` / `synapse_search` operate on typed prims, not free text only.
- [ ] **Definition of done:** a `kind` filter returns only that kind; a query no longer needs to slurp the whole store.

### PHASE 3 — Vector recall (P2 at depth)
**Problem:** semantic recall is skipped ("store not Moneta-backed").

**Work items:**
- [ ] Build a vector index *over* the USD store (embeddings per prim; index is derived data, rebuildable, never the source of truth).
- [ ] `synapse_recall` returns nearest neighbors by embedding with a confidence score.
- [ ] **Definition of done:** `vector_recall` check passes and returns ranked results with scores.

### PHASE 4 — Consolidation & pruning (P7)
**Problem:** consolidation is a no-op; memory only grows.

**Work items:**
- [ ] Implement the charmeleon→charizard evolution over the *real* store (currently gated because the store isn't Moneta-backed).
- [ ] A dry-run `synapse_evolve_memory` must return a prune audit (what merges, what prunes, before/after counts) and only apply when approved.
- [ ] **Definition of done:** a consolidation run demonstrably reduces count with an audit trail and zero information loss on protected memories.

### PHASE 5 — Migration & cut-over (the actual "go live")
**Problem:** all real memory is still in JSONL.

**Work items:**
- [ ] One-shot exporter: JSONL → typed USD prims, preserving ids so references survive.
- [ ] Verify: every JSONL memory has a corresponding USD prim (count + spot-check field fidelity). **No prim is dropped.**
- [ ] Flip the active backend to Moneta; keep JSONL as the automatic write-through safety net.
- [ ] **Definition of done:** existing memories survive the cut-over byte-for-byte in the new store, and new writes land in Moneta with JSONL fallback armed.

### PHASE 6 — Production hardening
- [ ] Crash-recovery: partial stage writes don't corrupt the root.
- [ ] Concurrency: two sessions writing don't clobber (USD layer composition already helps — confirm the merge semantics).
- [ ] Telemetry: doctor reports write-plane health (`write_plane`) for the *store*, not just the bridge.
- [ ] **Definition of done:** the doctor's memory section reads all-ok *and* the write-plane is independently verified.

---

## 5. Verifiable acceptance for the whole effort

A senior reviewer should be able to tick every box with evidence:

- [ ] No JSONL memory is lost in the migration (count + field-fidelity check).
- [ ] `synapse_doctor` memory checks are all `ok` or a clean, *true* fallback — never "unknown"/"skipped due to not-Moneta-backed".
- [ ] `synapse_recall`/`synapse_search` work off typed prims and can filter by kind.
- [ ] `synapse_evolve_memory` dry-runs and only applies on approval, with a prune audit.
- [ ] The harness can run with Moneta **or** fall back to JSONL transparently and the doctor says which, honestly.
- [ ] Every invariant P1–P7 has at least one test that fails if it's violated.

---

## 6. Guardrails (because this touches real memory)

- **Dual-write for phases 1–4.** Never move pages until the cabinet is proven.
- **Dry-run everything destructive.** `synapse_evolve_memory` and any pruning are preview-then-approve.
- **Non-destructive cut-over.** Migration is copy-and-verify; the JSONL notebook stays armed as the safety net.
- **One invariant per change.** Each PR should map to exactly one of P1–P7 so review is tractable.
- **Doctor is the source of truth.** A change isn't done until the doctor *shows* it, not until a comment claims it.

---

## 7. Suggested immediate first commit (keep it tiny)

Smallest verifiable step that starts the flywheel:

> **"Stop claiming moneta when it isn't in use."**
> In `moneta_substrate`, when `cortex_root.usda` does not exist, report the effective backend as `jsonl` (or materialize a minimal root). Either way, `in_use` becomes a deterministic boolean instead of `None`.

This single change makes the doctor honest, gives the next phase a clean baseline, and touches zero live memory. Then Phase 1's "materialize a minimal root" naturally follows.
