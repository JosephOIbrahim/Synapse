# SYNAPSE Memory Harness — Engineering Specification for Claude Code

**Companion to:** `docs/SYNAPSE-memory-blueprint.md` (the strategy/phase doc).
**This doc:** the *where* and *how* — exact files, exact functions, exact failure modes, and the acceptance test for each change.
**Grounding:** live `synapse_doctor` + `synapse_health` snapshot, 2026-08-13.

---

## 0. THE ONE ROOT CAUSE (read this first)

The live health check reports:

```
write_plane: degraded
  reason: memory backend 'moneta' was selected but this process fell back to jsonl
          (init failed: ValueError: embedding dim mismatch: expected 384, got 256)
  backend_fallback: { requested: moneta, served: jsonl, reason: "init failed: ValueError: embedding dim mismatch: expected 384, got 256" }
```

**This one error is the cause of every downstream symptom:**
- `moneta_substrate: fail` (schema registered but no usable store)
- `in_use = None` (init aborted before the stage was materialized)
- `moneta_consolidation / vector_recall / use_real_usd: skipped` ("store is not Moneta-backed")
- `write_plane: degraded`

**The bug:** the vector index is configured for **384-dim** embeddings, but the embedding provider produced **256-dim** vectors. Moneta init validates dims, throws `ValueError`, and the harness falls back to JSONL. The store never materializes.

**Fix the dim mismatch and the whole memory stack comes alive.** Everything else in this spec is hardening on top of that.

---

## 1. Where the code lives (map the repo first)

The repo root is `C:\Users\User\SYNAPSE`. Before editing, run a file map to confirm exact paths (the tree may have moved since this doc was written):

```bash
cd C:\Users\User\SYNAPSE
find . -name '*.py' -not -path '*/.git/*' -not -path '*/__pycache__/*' | sort
```

**Files you are almost certainly looking for** (confirm by grep, don't trust names blindly):

| Concern | Grep for | Likely file(s) |
|---|---|---|
| Moneta backend init | `class Moneta`, `def init`, `embedding` | `src/synapse/memory/moneta*.py` or `src/synapse/moneta*.py` |
| Embedding dim constant | `384`, `256`, `embedding_dim`, `dim` | the embedding provider module |
| Backend selection / fallback | `backend_fallback`, `requested`, `served`, `jsonl` | `src/synapse/memory/store.py` or `backend.py` |
| Doctor memory checks | `moneta_substrate`, `in_use`, `vector_recall` | `src/synapse/doctor.py` or `src/synapse/ops/doctor*.py` |
| Health / write_plane | `write_plane`, `degraded`, `backend_fallback` | `src/synapse/health.py` or `src/synapse/bridge/health*.py` |
| Memory write/query | `synapse_memory_write`, `synapse_memory_query` | `src/synapse/memory/*.py` |
| Evolution / consolidation | `charmeleon`, `charizard`, `evolve`, `prune` | `src/synapse/memory/evolve*.py` |

**Grep-first rule:** every path above is a *guess*. Run `grep -rn "embedding dim mismatch"` and `grep -rn "384"` to find the exact source of the error, then follow the call stack. Do not edit a file you haven't confirmed contains the symbol.

---

## 2. Phase 0 — Fix the dim mismatch (the actual bug)

**Goal:** Moneta init succeeds; `write_plane` goes `degraded → ok`.

**Find the source of the error:**
```bash
grep -rn "embedding dim mismatch" C:\Users\User\SYNAPSE
grep -rn "expected 384" C:\Users\User\SYNAPSE
grep -rn "got 256" C:\Users\User\SYNAPSE
```

**Likely fix (one of these, confirm which):**
- **A. The provider is wrong.** The embedding provider returns 256-dim but the index expects 384. Either switch the provider to one that emits 384, or change the index's `embedding_dim` to 256. **Prefer making the index read the provider's actual dim at init** rather than hardcoding 384 — that way a future provider change can't silently break init again.
- **B. A stale cached embedding.** If 256-dim vectors were written to disk under a 384-dim index, the fix is to invalidate/rebuild the index (it's derived data — see Phase 3). Delete the stale index and rebuild from the source memories.

**Acceptance test:**
```bash
# after the fix, run the doctor and health checks
# moneta_substrate must be: ok  (in_use = True)
# write_plane must be:      ok  (not degraded)
# no "embedding dim mismatch" anywhere in the log
```

**Do NOT** paper over it by catching the `ValueError` and silently staying on JSONL. That's what's happening now and it's why the doctor is dishonest. The fix is to make init *succeed*.

---

## 3. Phase 1 — Materialize the Moneta store

**Goal:** a real `cortex_root.usda` exists and typed prims can be written/read.

**Where:** the Moneta backend module (found in Phase 0).

**Work items:**
- [ ] On init, after the dim check passes, create the stage at the resolved `usd_root` (the doctor showed `C:\Users\User\AppData\Local\Temp\houdini_temp\untitled\.synapse\.moneta\cortex_root.usda`). Create a `MonetaMemory` root prim with a `version` attribute.
- [ ] Implement `write(kind, id, payload)` → a typed USD prim under the root, keyed by `(kind, id)`.
- [ ] Implement `query(...)` → walk the typed prims.
- [ ] **Dual-write:** for this phase, every write also goes to JSONL so nothing is at risk. The JSONL path is the safety net; it never goes away.

**Acceptance test:**
```bash
# write a memory, then:
# 1. the .usda file exists and is non-empty
# 2. doctor shows moneta_substrate: in_use=True
# 3. query returns the memory you wrote
# 4. the same memory is ALSO in the JSONL store (dual-write verified)
```

---

## 4. Phase 2 — Typed schema, routing on kind

**Goal:** `synapse_recall`/`synapse_search` filter by kind without string-matching the whole store.

**Where:** the schema definition + the query/recall modules.

**Work items:**
- [ ] Define per-kind fields: `note`, `context`, `reference`, `task`, `decision`. Each has a distinct set of attributes (e.g. `decision` carries `reasoning` + `alternatives`; `task` carries `status`).
- [ ] `synapse_recall` / `synapse_search` accept a `kind` filter and route on the typed prim, not free text.

**Acceptance test:**
```bash
# a kind-filtered query returns ONLY that kind
# a query no longer needs to slurp the entire store to find one memory
```

---

## 5. Phase 3 — Vector recall (semantic search)

**Goal:** `vector_recall` check passes; recall returns ranked nearest neighbors with scores.

**Where:** the embedding/index module (the one with the dim bug).

**Work items:**
- [ ] Build a vector index **over** the USD store. The index is *derived data* — rebuildable from source memories, never the source of truth.
- [ ] `synapse_recall` returns nearest neighbors by embedding with a confidence score.
- [ ] **Critical:** the index's `embedding_dim` must be read from the provider at init (see Phase 0 fix A), so a provider change can't break init again.

**Acceptance test:**
```bash
# doctor shows vector_recall: ok
# recall("karma settings") returns ranked results with scores, not a raw dump
```

---

## 6. Phase 4 — Consolidation & pruning

**Goal:** `synapse_evolve_memory` dry-runs and only applies on approval, with a prune audit.

**Where:** the evolve/consolidation module.

**Work items:**
- [ ] Implement charmeleon→charizard evolution over the *real* store (currently gated because the store isn't Moneta-backed — unblocking Phase 0/1 unblocks this).
- [ ] Dry-run returns a prune audit: what merges, what prunes, before/after counts.
- [ ] Apply only when approved. Protected memories are never pruned.

**Acceptance test:**
```bash
# a dry-run returns an audit with before/after counts and a list of pruned ids
# nothing is pruned until explicitly approved
# protected memories survive a consolidation run
```

---

## 7. Phase 5 — Migration & cut-over

**Goal:** existing JSONL memories survive into Moneta byte-for-byte; new writes land in Moneta with JSONL fallback armed.

**Where:** a new migration module + the backend-selection logic.

**Work items:**
- [ ] One-shot exporter: JSONL → typed USD prims, preserving ids so references survive.
- [ ] Verify: every JSONL memory has a corresponding USD prim (count + spot-check field fidelity). **No prim is dropped.**
- [ ] Flip active backend to Moneta; keep JSONL as automatic write-through.

**Acceptance test:**
```bash
# count of JSONL memories == count of USD prims after migration
# spot-check 5 memories: every field matches byte-for-byte
# new writes land in Moneta; JSONL still receives them (fallback armed)
```

---

## 8. Phase 6 — Production hardening

- [ ] Crash-recovery: partial stage writes don't corrupt the root.
- [ ] Concurrency: two sessions writing don't clobber (confirm USD layer-merge semantics).
- [ ] Telemetry: doctor reports `write_plane` for the *store*, not just the bridge.
- [ ] **Acceptance:** doctor's memory section reads all-ok *and* write-plane is independently verified.

---

## 9. Guardrails (non-negotiable)

- **Dual-write for phases 1–4.** Never move pages until the cabinet is proven.
- **Dry-run everything destructive.** Preview-then-approve for evolution/pruning.
- **Non-destructive cut-over.** Migration is copy-and-verify; JSONL stays armed.
- **One invariant per change.** Each PR maps to exactly one of P1–P7 (from the blueprint).
- **Doctor is the source of truth.** A change isn't done until the doctor *shows* it.

---

## 10. The first commit (tiny, high-value)

> **"Fix the embedding dim mismatch so Moneta init succeeds."**

1. `grep -rn "embedding dim mismatch"` → find the exact throw site.
2. Make the index read the provider's actual dim at init (or switch provider to 384).
3. Rebuild any stale 256-dim index.
4. Run doctor + health: `moneta_substrate: ok`, `write_plane: ok`.

This single change unblocks every downstream phase and makes the doctor honest. Everything else builds on it.
