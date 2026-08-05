# Moneta ↔ SYNAPSE — Deep Review & Next-Level Architecture

> **Date:** 2026-08-05  
> **Method:** 6-agent parallel scout + first-principles analysis  
> **Status:** Moneta IS the live substrate (21/21 production inits); ratification pending

---

## 1. EXECUTIVE SUMMARY

Moneta is already SYNAPSE's memory substrate in production. The flip happened in `packages/synapse.json` (commit `b2c2c04`, deployed 2026-07-27) and has been running without a functional complaint for 10 days. 159 production rows exist in a real Moneta snapshot. The C-0 address bug is fixed (PR #60). The backend fallback is now loud.

**But Moneta is being used as a JSONL replacement with extra steps.** The vector index is written on every deposit and never read. The WAL is configured and never written to. The USD schema is unregistered. The consolidation/decay engine is never triggered. The embedder is a hash-based bootstrap that produces vectors no one queries against.

**The gap is not that Moneta doesn't work. The gap is that SYNAPSE is using 15% of what Moneta offers, and the remaining 85% is either deliberately deferred or structurally blocked.**

This review identifies every blockage — on both sides of the Moneta/SYNAPSE boundary — and proposes a phased path to the next level of memory capability.

---

## 2. WHAT MONETA IS (First Principles)

Moneta is an **in-process memory engine** with four capabilities:

| Capability | What it does | Status in SYNAPSE |
|---|---|---|
| **Deposit/Query** | Store and retrieve memory entities | ✅ Live — every add/search uses this |
| **Vector Similarity** | Cosine-similarity ranking over embeddings | ❌ Written, never read |
| **Time Decay** | Exponential utility decay with configurable half-life | ❌ Never triggered (no `run_sleep_pass` caller) |
| **Consolidation** | Prune low-utility memories, stage cold ones to USD | ❌ Never triggered |
| **Attention Weighting** | Boost utility via `signal_attention` | ❌ Never called |
| **USD Authoring** | Write typed MonetaMemory prims to USD sublayers | ❌ `use_real_usd` never set |
| **Durability** | Snapshot + WAL for crash recovery | ⚠️ Partial — snapshot on close/atexit only |

**Data model** — `Memory` (frozen dataclass):
- `entity_id` (UUID), `payload` (str — SYNAPSE's `Memory.to_json()`), `semantic_vector` (list[float])
- `utility` (float, starts at 1.0, decays), `attended_count` (int), `protected_floor` (float)
- `state` (VOLATILE / STAGED_FOR_SYNC / CONSOLIDATED), `usd_link` (Optional)

**Backends:**
- `MockUsdTarget` (default) — JSONL log or in-memory buffer, no pxr needed
- `UsdTarget` — real USD via pxr.Sdf, typed MonetaMemory prims, sublayer rotation

---

## 3. THE CURRENT PIPELINE (What Actually Happens)

```
User/Agent → MCP tool → handler → SynapseMemory.add()
  → MonetaBackedStore.add()
    → HashEmbedder.embed(content) → 256-dim vector
    → handle.deposit(payload, embedding, protected_floor)
      → ECS in-memory insert
      → VectorIndex.upsert() ← WRITTEN, NEVER READ
    → returns memory.id
  → NO save() ← in-memory only
  → NO signal_attention() ← WAL never written
```

```
User/Agent → MCP tool → handler → SynapseMemory.search()
  → MonetaBackedStore.search()
    → _iter_memories() → snapshot ECS → deserialize payloads
    → score_memories() → pure-Python tag/keyword/text scoring
    → return ranked results
  → Moneta.query() NEVER CALLED ← vector index unused
```

**The vector index is pure write amplification.** Every deposit writes to it. Nothing reads it. SYNAPSE's `score_memories()` reimplements the JSONL store's keyword/tag/text scoring in Python — deliberately, as a "parity target" — and the vector query is described as "a deliberate later upgrade, measured against keyword recall in shadow first."

---

## 4. BLOCKAGES — MONETA SIDE

These are issues in the Moneta package itself that affect SYNAPSE.

### B-M1: Cosine Inversion (F5) — Unclamped Cosine × Utility

**Location:** `moneta/api.py:413`, `moneta/vector_index.py:165`  
**Severity:** HIGH (upstream), ZERO (SYNAPSE — unreachable)  
**Status:** Documented, upstream issue

`Moneta.query()` ranks by `cosine_similarity * utility`. Cosine can be negative (measured 5.74% for short tokens, 36.4% for disjoint symbols). A negative cosine × positive utility = negative score, which ranks BELOW a zero-score item. **Reinforcing a memory can bury it.**

SYNAPSE never calls `Moneta.query()`, so this is unreachable today. But if anyone later wires `MonetaBackedStore.search` to `self._handle.query(...)`, this bug activates immediately.

**Fix:** `max(cos, 0.0)` in `api.py:413` and `vector_index.py:165`. Upstream issue.

### B-M2: Attention Weight Unvalidated (F6) — NaN Deletes Memories

**Location:** `moneta/api.py:430`, `moneta/ecs.py:211-212`  
**Severity:** HIGH (upstream), ZERO (SYNAPSE — unreachable)  
**Status:** Documented, upstream issue

`signal_attention` casts weights to float without validation. NaN or negative values set utility to 0.0, which makes the memory immediately prunable. SYNAPSE never calls `signal_attention`, so this is unreachable.

### B-M3: USD Write-Only (F7)

**Location:** `moneta/usd_target.py`  
**Severity:** MEDIUM (upstream), ZERO (SYNAPSE — `use_real_usd` never set)  
**Status:** Documented, upstream issue

`UsdTarget` writes typed prims but has zero read APIs. Even if SYNAPSE enabled `use_real_usd=True`, there's no way to read the authored USD back. The `usd_link` field is never assigned anywhere in the package.

### B-M4: `vector_persist_path` Accepted, Never Read (F2)

**Location:** `moneta/api.py:134`, `moneta/vector_index.py:75-81`  
**Severity:** LOW  
**Status:** Documented

The config field is accepted, passed through, and then the vector index warns "persistence not yet implemented" and ignores it. SYNAPSE never passes this field.

### B-M5: No `__version__` in Moneta Package

**Location:** `moneta/__init__.py`  
**Severity:** MEDIUM  
**Status:** Documented, upstream issue

No `__version__` anywhere in the package. `importlib.metadata.version("moneta")` returns `1.2.0rc1` for rc1, rc2, and rc2+N — cannot discriminate builds. SYNAPSE's `moneta_runtime.py` works around this by reading git SHA from filesystem metadata.

### B-M6: Snapshot Daemon Races Single-Writer ECS

**Location:** `moneta/durability.py:231-251`  
**Severity:** MEDIUM  
**Status:** Deliberately not started by SYNAPSE

`start_background()` snapshots from a non-main thread with no lock on `ecs.iter_rows()`. SYNAPSE explicitly rejects this (`moneta_store.py:195-198`). The daemon is structurally incompatible with SYNAPSE's async server.

---

## 5. BLOCKAGES — SYNAPSE SIDE

These are issues in SYNAPSE's integration layer.

### B-S1: No Per-Deposit Durability

**Location:** `moneta_store.py:292-310`  
**Severity:** CRITICAL  
**Status:** Known, bounded

`deposit()` writes to the in-memory ECS and returns. No `save()`, no WAL write, no daemon. The only persistence is:
- `atexit.register(store.close)` — covers clean exit only
- Explicit `save()` calls — never called in production

**Houdini crash = 100% loss since last snapshot.** This repo has a crash harness because crashes happen.

**Mitigation:** The per-record JSON file (ledger) is the durable source of truth. But the main memory store has no such fallback.

**Fix options:**
1. Per-deposit `save()` — O(n) snapshot per add, expensive
2. Upstream deposit-WAL — Moneta needs a WAL v2 with typed deposit records
3. Periodic save timer — 30s interval, bounded loss window

### B-S2: Vector Index is Write-Only

**Location:** `moneta_store.py:292-310` (deposit writes to vector index), `moneta_store.py:359-360` (search uses `score_memories`, not `query`)  
**Severity:** MEDIUM  
**Status:** Deliberate, documented

Every deposit writes to Moneta's vector index. Nothing reads it. SYNAPSE's `score_memories()` does pure-Python keyword/tag/text scoring. The vector index is pure write amplification — CPU time, memory, and I/O for a data structure that is populated and never queried.

**Fix:** Either:
1. Start using `Moneta.query()` for vector recall (requires fixing B-M1 first)
2. Stop writing to the vector index (requires Moneta API change — no opt-out today)

### B-S3: Schema Not Registered

**Location:** `moneta_runtime.py:76-78`, `doctor.py:362-366`  
**Severity:** MEDIUM  
**Status:** Deliberately deferred

`PXR_PLUGINPATH_NAME` is unset. The schema assets exist at `C:/Users/User/Moneta/schema/` (plugInfo.json, generatedSchema.usda, MonetaSchema.usda) but are not wired. `synapse_doctor` reports `moneta_substrate` status = `fail` because `registered=False`.

**Fix:** One env var in `packages/synapse.json`. Deferred because it adds a hard `pxr` import to the memory path and buys nothing while `use_real_usd` is False.

### B-S4: No USD Authored

**Location:** `moneta_store.py:215-227`  
**Severity:** LOW (today), HIGH (if USD substrate is the goal)  
**Status:** Deliberately deferred

`from_storage_dir` builds `MonetaConfig` without `use_real_usd=True`. All 159 production rows have `usd_link=None`. SYNAPSE authors zero USD through Moneta.

**Fix:** Set `use_real_usd=True` in `MonetaConfig`. Requires B-S3 (schema registration) first. Requires B-M3 (USD read path) to be useful.

### B-S5: WAL is Inert

**Location:** `moneta_store.py:220-226`  
**Severity:** MEDIUM  
**Status:** Documented

Moneta's WAL is configured but never written to. SYNAPSE never calls `signal_attention`, which is the only WAL writer. The WAL path is exercised zero times in production.

**Fix:** Either start calling `signal_attention` (adds attention-weighting capability) or remove the WAL config to avoid misleading future readers.

### B-S6: `run_sleep_pass` Ungated

**Location:** `handlers_memory.py:290-314`  
**Severity:** LOW (no production caller)  
**Status:** Deferred follow-up (FU-2)

`run_sleep_pass` permanently prunes unprotected memories and is currently ungated. It has no production caller yet, so this is not urgent — but when wired, it should route through `HumanGate` at APPROVE.

### B-S7: Memory.id Collision

**Location:** `models.py:128-150`  
**Severity:** LOW (JSONL dedups, Moneta appends)  
**Status:** Deferred follow-up (FU-1)

`Memory.__post_init__` generates id before defaulting `created_at`, so identical content+type collides. JSONL dedups by id; Moneta appends both. Fix is a reorder in `__post_init__`.

### B-S8: ~66 Tests Skip on CI

**Location:** `.github/workflows/ci.yml`  
**Severity:** MEDIUM  
**Status:** Deferred follow-up (FU-3)

Moneta tests are `skipif not moneta_available` and skip on CI. The CI workflow has conditional checkout gated on `MONETA_DEPLOY_KEY` secret (not yet provisioned). Joe needs to create the deploy key.

### B-S9: Moneta is an Unpinned Dependency

**Location:** `pyproject.toml`, `.github/workflows/ci.yml`  
**Severity:** MEDIUM  
**Status:** Known

No version pin in `pyproject.toml`. CI checks out branch tip, not a tagged release. `importlib.metadata.version("moneta")` returns `1.2.0rc1` for rc1, rc2, and rc2+N — cannot detect drift.

### B-S10: Two Memory Systems Coexist

**Location:** `memory/moneta_store.py` (structured store) vs `memory/scene_memory.py` (markdown living memory)  
**Severity:** MEDIUM  
**Status:** Architectural

Moneta backs the structured `MemoryStore` (add/search/recall). But the "Living Memory" system (`scene_memory.py`) writes to markdown files (`memory.md`, `project.md`) and has its own TF-IDF search. These are separate systems with separate data. A memory written through one is invisible to the other.

### B-S11: The Recall/RAG Seam

**Location:** `handlers_memory.py:69-102`  
**Severity:** MEDIUM  
**Status:** Known, partially addressed

`recall`/`search` see Moneta only, not the RAG corpus. `_augment_with_knowledge()` bridges the gap additively — best-effort, never raises. The VEX corpus goal (seed Moneta pointers) is partially addressed by `seed_corpus.py` but hasn't been run.

### B-S12: `evolution.py` is Dormant Dead Code

**Location:** `memory/evolution.py`  
**Severity:** LOW  
**Status:** Documented as SUPERSEDED

`evolution.py` declares itself SUPERSEDED by Moneta and says "do not extend it." Under the moneta backend, `_check_evolution` is never called. Under jsonl, it still fires. The module should be removed when the default flips to moneta.

---

## 6. THE NEXT LEVEL — Phased Architecture

### Phase 0: Ratify and Stabilize (NOW — days)

**Goal:** Make the current Moneta integration production-grade.

| Item | What | Effort | Risk |
|---|---|---|---|
| P0-1 | **Ratify Moneta as the substrate** (RSI loop C) | Decision | Low — it's already live |
| P0-2 | **Fix Memory.id collision** (FU-1) | 15 min | Low |
| P0-3 | **Provision MONETA_DEPLOY_KEY** (FU-3) | 10 min | Low |
| P0-4 | **Pin Moneta dependency** in pyproject.toml | 5 min | Low |
| P0-5 | **Pin CI Moneta ref** to a tagged release | 5 min | Low |

### Phase 1: Durability (WEEK 1)

**Goal:** Close the crash-loss window.

| Item | What | Effort | Risk |
|---|---|---|---|
| P1-1 | **Periodic save timer** — 30s interval snapshot | 1 day | Low |
| P1-2 | **Per-deposit WAL write** — requires Moneta WAL v2 (upstream) | 2-3 days | Medium |
| P1-3 | **Crash recovery test** — verify snapshot+WAL replay | 1 day | Low |

**Design for P1-1:**
```python
# In MonetaBackedStore.__init__ or from_storage_dir
self._save_interval = 30.0  # seconds
self._last_save = time.monotonic()
# In add(), after deposit:
now = time.monotonic()
if now - self._last_save >= self._save_interval:
    self.save()
    self._last_save = now
```

This bounds the loss window to 30 seconds without the O(n) cost of per-deposit snapshots. The timer is checked on add() — no background thread needed.

### Phase 2: Activate the Vector Index (WEEK 2-3)

**Goal:** Stop write amplification and start using Moneta's vector recall.

| Item | What | Effort | Risk |
|---|---|---|---|
| P2-1 | **Fix cosine clamp upstream** (B-M1) | 1 day | Low — pure math change |
| P2-2 | **Wire MonetaBackedStore.search to Moneta.query()** | 2 days | Medium — changes recall behavior |
| P2-3 | **Shadow-compare vector vs keyword recall** | 2 days | Low — use existing ShadowMemoryStore |
| P2-4 | **Swap HashEmbedder for semantic embedder** | 2-3 days | Medium — re-embedding needed |

**Design for P2-2:**
```python
def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
    # Hybrid: vector recall + keyword scoring
    if query.text:
        embedding = self._embedder.embed(query.text)
        vector_results = self._handle.query(embedding, limit=query.limit * 3)
        # Rerank with keyword scoring
        memories = [Memory.from_json(r.payload) for r in vector_results]
        return score_memories(memories, query)
    return score_memories(self._iter_memories(), query)
```

This is the minimal change: use vector recall as a candidate pre-filter, then rerank with the existing keyword scoring. No behavior change for non-text queries.

### Phase 3: Activate Consolidation (WEEK 3-4)

**Goal:** Start using Moneta's time-decay and pruning to manage memory growth.

| Item | What | Effort | Risk |
|---|---|---|---|
| P3-1 | **Gate run_sleep_pass through HumanGate** (FU-2) | 1 day | Low |
| P3-2 | **Wire periodic sleep pass** — e.g., every 100 adds | 1 day | Medium — first production caller |
| P3-3 | **Tune decay parameters** — half-life, prune thresholds | 2 days | Medium — affects recall |
| P3-4 | **Add attention signaling** — boost utility on recall | 2 days | Medium — new behavior |

**Design for P3-2:**
```python
# In MonetaBackedStore.add(), after deposit:
self._add_count += 1
if self._add_count % 100 == 0:
    # Opportunistic consolidation — only when pressure is low
    if self._handle.ecs.n > 1000:  # only if we have enough memories
        audit = self.run_sleep_pass()
        if audit.pruned > 0:
            logger.info("Sleep pass pruned %d memories", audit.pruned)
```

### Phase 4: USD Substrate (WEEK 4-6)

**Goal:** Make the "USD cognitive substrate" claim literally true.

| Item | What | Effort | Risk |
|---|---|---|---|
| P4-1 | **Register MonetaMemory schema** (B-S3) | 1 hour | Low — one env var |
| P4-2 | **Enable use_real_usd=True** (B-S4) | 1 day | Medium — adds pxr import |
| P4-3 | **Fix USD read path upstream** (B-M3) | 2-3 days | Medium — upstream work |
| P4-4 | **Bridge Moneta USD with agent.usd** | 3-5 days | High — architectural |

### Phase 5: Unify Memory Systems (WEEK 6-8)

**Goal:** Merge the structured Moneta store with the markdown Living Memory system.

| Item | What | Effort | Risk |
|---|---|---|---|
| P5-1 | **Write scene_memory entries to Moneta** | 2 days | Medium |
| P5-2 | **Backfill existing markdown into Moneta** | 1 day | Low |
| P5-3 | **Remove evolution.py** | 1 hour | Low — dead code |
| P5-4 | **Unify recall/search across all memory** | 3-5 days | High |

---

## 7. THE CRITICAL PATH

The single highest-leverage item is **Phase 1 — Durability**. Without it, every Houdini crash loses the session's memory. This is the one genuine production risk.

The second-highest leverage item is **Phase 2 — Activate the Vector Index**. It converts write amplification into actual capability and is the foundation for everything after it.

**Recommended order:**
1. Phase 0 (ratify + pin) — this week
2. Phase 1 (durability) — next week
3. Phase 2 (vector recall) — week after
4. Phase 3 (consolidation) — after vector recall is stable
5. Phase 4 (USD) — after consolidation
6. Phase 5 (unify) — last

---

## 8. WHAT NOT TO DO

| Don't | Why |
|---|---|
| Fix cosine clamp in SYNAPSE | `Moneta.query()` has zero callers. Fix upstream. |
| Fix attention validation in SYNAPSE | `signal_attention` has zero callers. Fix upstream. |
| Fix USD read path in SYNAPSE | `use_real_usd` is never set. Fix upstream. |
| Enable `use_real_usd` before schema registration | Dead bytes — type name on disk, runtime can't resolve it. |
| Start background snapshot daemon | Races the single-writer ECS. SYNAPSE already correctly rejected this. |
| Vendor Moneta | Pure Python, co-developed by same author. Pin + probe instead. |
| Remove evolution.py before default flip | Still live under jsonl default for non-Houdini processes. |
| Wire run_sleep_pass without HumanGate | Destructive op must be gated. |

---

## 9. THE MONETA-SYNAPSE CONTRACT

What each side owes the other:

**Moneta owes SYNAPSE:**
1. A stable, versioned API surface (export `__version__`, tag releases)
2. A deposit-WAL that actually records deposits (WAL v2)
3. Clamped cosine in `query()` (`max(cos, 0.0)`)
4. A USD read path (not just write-only)
5. An opt-out for vector index writes (to stop write amplification)

**SYNAPSE owes Moneta:**
1. A pinned dependency (not branch-tip tracking)
2. CI that actually exercises Moneta (deploy key)
3. A production caller for `run_sleep_pass` (to validate consolidation)
4. A production caller for `signal_attention` (to validate attention)
5. Schema registration (one env var)
6. `use_real_usd=True` (to validate USD authoring)

---

## 10. RISK ASSESSMENT

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Houdini crash loses memory | MEDIUM | HIGH | Phase 1 (periodic save) |
| Moneta API drift breaks adapter | LOW | HIGH | Pin dependency + CI |
| Vector recall degrades search | MEDIUM | MEDIUM | Shadow-compare before flip |
| Consolidation prunes wanted memories | LOW | MEDIUM | PruneAudit + protected floors |
| USD schema registration breaks pxr import | LOW | MEDIUM | Test in CI first |
| Two memory systems diverge further | HIGH | MEDIUM | Phase 5 unification |

---

## 11. IMMEDIATE NEXT STEPS

1. **Ratify Moneta as the substrate** (RSI loop C — Joe's decision)
2. **Fix Memory.id collision** (FU-1 — 15 min, low risk)
3. **Provision MONETA_DEPLOY_KEY** (FU-3 — 10 min)
4. **Pin Moneta dependency** in pyproject.toml
5. **Build periodic save timer** (Phase 1 — 1 day)
6. **Fix cosine clamp upstream** (Phase 2 prerequisite)
7. **Wire vector recall in shadow** (Phase 2 — 2 days)

---

## 12. APPENDIX: Key File Map

| File | Role | Lines |
|---|---|---|
| `python/synapse/memory/moneta_runtime.py` | Import guard + 5-condition substrate probe | 702 |
| `python/synapse/memory/moneta_store.py` | MonetaBackedStore adapter | 464 |
| `python/synapse/memory/store.py` | Backend selector + MemoryStore (JSONL) | 1360 |
| `python/synapse/memory/shadow_store.py` | ShadowMemoryStore dual-write harness | 163 |
| `python/synapse/memory/embedding.py` | HashEmbedder (bootstrap) | 117 |
| `python/synapse/memory/backfill.py` | JSONL-to-Moneta migration | 120 |
| `python/synapse/memory/ledger.py` | Ledger deposit with Moneta enrichment | ~560 |
| `python/synapse/memory/models.py` | Memory data model | 319 |
| `python/synapse/memory/evolution.py` | Legacy evolution (SUPERSEDED) | 443 |
| `python/synapse/memory/scene_memory.py` | Markdown Living Memory system | ~1200 |
| `python/synapse/memory/seed_corpus.py` | VEX corpus pointer seeder | 207 |
| `python/synapse/server/doctor.py` | Moneta substrate check (H6/R64) | ~460 |
| `python/synapse/server/handlers_memory.py` | Memory MCP handlers | ~315 |
| `python/synapse/mcp/_tool_registry.py` | MCP tool definitions | ~1081 |
| `python/synapse/science/deposit.py` | Science→Ledger deposit adapter | ~100 |
| `packages/synapse.json` | Houdini package env (flips moneta ON) | 29 |
| `docs/MONETA_SYNAPSE_INTEGRATION_HARNESS.md` | Integration constitution | 298 |
| `docs/MONETA_SYNAPSE_SHIP_REPORT.md` | Miles 2-8 ship report | 126 |
| `docs/MONETA_FOLLOWUPS.md` | 3 deferred follow-ups | 141 |
| `docs/MONETA_SYNAPSE_HANDOFF_Mile2.md` | Handoff capsule | 99 |
| `docs/reviews/moneta-p0-synapse-execution-plan-2026-07-21.md` | P0 execution plan | 207 |
| `docs/reviews/h22-c3-moneta-decision.md` | C3 "one Moneta" ruling | 79 |
| `harness/rsi/REGISTRY.json` | RSI registry (loop C) | 398 |
| `harness/rsi/briefs/C-substrate-decision-brief-2026-08-01.md` | C-substrate decision brief | 48 |
| `C:/Python314/Lib/site-packages/moneta/` | Moneta package (v1.2.0rc1) | 12 files |
