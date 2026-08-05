# Moneta Production Harness — Architecture & Execution Plan

> **Date:** 2026-08-05  
> **Design method:** First-principles, harness-architect playbook  
> **Target:** Make the Moneta-SYNAPSE memory relationship a production powerhouse  
> **Shape:** Hybrid — Workflow Orchestrator (phased implementation) + Embedded RSI (ongoing loops)

---

## 0. THE JOB

**What the harness serves:** SYNAPSE's memory substrate — the Moneta-backed store that every memory operation flows through.

**What job it owns:** Ensure Moneta is used to its full production potential — durable, queried by vector, consolidated, USD-backed, and unified with the markdown living memory system.

**What actions agents may take:**
- Read and modify `python/synapse/memory/` files
- Read and modify `moneta/` package files (upstream)
- Run tests (`pytest tests/`)
- Create new test files
- Write documentation

**What must never happen:**
- Break the live Moneta backend (production is running on it)
- Lose data during migration
- Change the `MemoryStore` interface that callers depend on
- Flip `use_real_usd=True` without schema registration first
- Wire `run_sleep_pass` without a HumanGate

---

## 1. SYSTEM ARCHITECTURE

### 1.1 Subsystem Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                      MONETA PRODUCTION HARNESS                      │
│                                                                     │
│  ┌─────────────────────┐  ┌─────────────────────┐                  │
│  │  DURABILITY LAYER   │  │  CAPABILITY ACTIVATOR│                  │
│  │  (Phase 1)          │  │  (Phases 2-4)       │                  │
│  │                     │  │                     │                  │
│  │  • Periodic save    │  │  • Vector recall    │                  │
│  │  • WAL activation   │  │  • Consolidation    │                  │
│  │  • Crash recovery   │  │  • Attention        │                  │
│  │  • Test harness     │  │  • USD substrate    │                  │
│  └─────────┬───────────┘  └─────────┬───────────┘                  │
│            │                        │                              │
│  ┌─────────┴────────────────────────┴───────────┐                  │
│  │           MEMORY UNIFICATION BRIDGE          │                  │
│  │           (Phase 5)                          │                  │
│  │                                              │                  │
│  │  • Merge structured + markdown stores        │                  │
│  │  • Unified recall/search                     │                  │
│  │  • Remove evolution.py                       │                  │
│  └──────────────────────┬──────────────────────┘                  │
│                         │                                          │
│  ┌──────────────────────┴──────────────────────┐                  │
│  │           RSI LOOP CLOSER                    │                  │
│  │                                              │                  │
│  │  • Loop C: Ratify substrate                 │                  │
│  │  • Loop R: Render-farm learning             │                  │
│  │  • Loop A3: Remove evolution.py             │                  │
│  │  • Loop O: Observability                    │                  │
│  │  • Loop S: Science registry                │                  │
│  └──────────────────────┬──────────────────────┘                  │
│                         │                                          │
│  ┌──────────────────────┴──────────────────────┐                  │
│  │           EVALUATION HARNESS                 │                  │
│  │                                              │                  │
│  │  • Per-change test suite                     │                  │
│  │  • Regression floor                          │                  │
│  │  • Parity checks                             │                  │
│  │  • Mutation tests                            │                  │
│  └─────────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Primitives

| Primitive | What it does | Owns |
|---|---|---|
| **Durability Timer** | 30s periodic save in `MonetaBackedStore.add()` | `moneta_store.py` |
| **WAL Activator** | Call `signal_attention` on recall to write WAL | `moneta_store.py` |
| **Vector Recall** | Wire `Moneta.query()` into `MonetaBackedStore.search()` | `moneta_store.py` |
| **Consolidation Scheduler** | Periodic `run_sleep_pass` with PruneAudit | `handlers_memory.py` |
| **Attention Signaler** | Boost utility on memory access | `moneta_store.py` |
| **Schema Registrar** | Set `PXR_PLUGINPATH_NAME` in package env | `packages/synapse.json` |
| **USD Activator** | Set `use_real_usd=True` in `MonetaConfig` | `moneta_store.py` |
| **Memory Unifier** | Write scene_memory entries to Moneta | `scene_memory.py` |
| **RSI Rung Prover** | Verify each RSI loop rung | `harness/rsi/verify.py` |

### 1.3 Permission Boundaries

| Operation | Gate | Why |
|---|---|---|
| Add periodic save timer | INFORM | No data loss, no behavior change |
| Wire vector recall | INFORM | Read-side only, shadow-compared |
| Wire consolidation | APPROVE | Destructive — prunes memories |
| Register USD schema | INFORM | One env var, reversible |
| Enable `use_real_usd` | REVIEW | Adds pxr import, changes storage |
| Unify memory systems | REVIEW | Data migration, must be verified |
| Remove evolution.py | INFORM | Dead code removal |
| Pin Moneta dependency | INFORM | Build config change |

---

## 2. PHASED EXECUTION PLAN

### Phase 0: Foundation (Days 1-2)

**Goal:** Ratify the substrate, pin dependencies, fix the easy bugs.

| Task | Files | Effort | Risk |
|---|---|---|---|
| P0-1: Ratify Moneta (RSI loop C) | `harness/rsi/REGISTRY.json` | Decision | Low |
| P0-2: Fix Memory.id collision | `models.py` | 15 min | Low |
| P0-3: Pin Moneta dep in pyproject.toml | `pyproject.toml` | 5 min | Low |
| P0-4: Pin CI Moneta ref | `.github/workflows/ci.yml` | 5 min | Low |
| P0-5: Provision MONETA_DEPLOY_KEY | GitHub settings | 10 min | Low |

**Verification:** `pytest tests/test_moneta_*.py` passes. CI green.

### Phase 1: Durability (Days 3-5)

**Goal:** Close the crash-loss window.

| Task | Files | Effort | Risk |
|---|---|---|---|
| P1-1: Add 30s periodic save timer | `moneta_store.py` | 1 day | Low |
| P1-2: Add crash recovery test | `tests/test_moneta_integration.py` | 1 day | Low |
| P1-3: Document durability bounds | `moneta_store.py` docstring | 30 min | Low |

**Design for P1-1:**
```python
# In MonetaBackedStore.__init__:
self._last_save = 0.0
self._save_interval = 30.0  # seconds

# In add(), after deposit:
now = time.monotonic()
if now - self._last_save >= self._save_interval:
    self.save()
    self._last_save = now
```

**Verification:** `test_crash_loses_at_most_30s_of_deposits` — add memories, simulate crash (don't call close), reopen, assert count >= N-1.

### Phase 2: Vector Recall (Days 6-10)

**Goal:** Stop write amplification. Use Moneta's vector index for recall.

| Task | Files | Effort | Risk |
|---|---|---|---|
| P2-1: Fix cosine clamp upstream | `moneta/api.py`, `moneta/vector_index.py` | 1 day | Low |
| P2-2: Wire vector recall in shadow | `moneta_store.py` | 2 days | Medium |
| P2-3: Shadow-compare vector vs keyword | `tests/test_moneta_store.py` | 1 day | Low |
| P2-4: Flip vector recall live | `moneta_store.py` | 1 day | Medium |

**Design for P2-2:**
```python
def search(self, query: MemoryQuery) -> List[MemorySearchResult]:
    if query.text:
        embedding = self._embedder.embed(query.text)
        vector_results = self._handle.query(embedding, limit=query.limit * 3)
        memories = [Memory.from_json(r.payload) for r in vector_results]
        return score_memories(memories, query)
    return score_memories(self._iter_memories(), query)
```

**Verification:** `test_vector_recall_parity` — vector recall returns same top-N as keyword recall for a representative query set. `test_vector_recall_improvement` — vector recall finds relevant memories keyword recall misses.

### Phase 3: Consolidation & Attention (Days 11-15)

**Goal:** Activate time-decay, pruning, and attention weighting.

| Task | Files | Effort | Risk |
|---|---|---|---|
| P3-1: Gate run_sleep_pass through HumanGate | `handlers_memory.py`, `shared/constants.py` | 1 day | Low |
| P3-2: Wire periodic sleep pass | `moneta_store.py` | 1 day | Medium |
| P3-3: Add attention signaling on recall | `moneta_store.py` | 1 day | Medium |
| P3-4: Tune decay parameters | `moneta_store.py` | 2 days | Medium |
| P3-5: Add consolidation telemetry | `moneta_store.py`, `doctor.py` | 1 day | Low |

**Design for P3-2:**
```python
# In MonetaBackedStore.add(), after deposit:
self._add_count += 1
if self._add_count % 100 == 0 and self._handle.ecs.n > 1000:
    audit = self.run_sleep_pass()
    if audit.pruned > 0:
        logger.info("Sleep pass pruned %d memories", audit.pruned)
```

**Design for P3-3:**
```python
# In MonetaBackedStore.search(), after returning results:
if query.text and results:
    weights = {r.memory.id: r.score for r in results[:5]}
    self._handle.signal_attention(weights)
```

**Verification:** `test_consolidation_prunes_unprotected` — add unprotected memories, run sleep pass, assert pruned. `test_attention_boosts_utility` — signal attention, assert utility increased. `test_protected_memories_survive` — add protected memories, run sleep pass, assert not pruned.

### Phase 4: USD Substrate (Days 16-20)

**Goal:** Make the "USD cognitive substrate" claim literally true.

| Task | Files | Effort | Risk |
|---|---|---|---|
| P4-1: Register MonetaMemory schema | `packages/synapse.json` | 1 hour | Low |
| P4-2: Fix USD read path upstream | `moneta/usd_target.py` | 2-3 days | Medium |
| P4-3: Enable use_real_usd=True | `moneta_store.py` | 1 day | Medium |
| P4-4: Bridge Moneta USD with agent.usd | `agent_state.py` | 3-5 days | High |

**Verification:** `test_usd_substrate_roundtrip` — deposit memory, run sleep pass, read back from USD, assert content matches. `test_schema_registered` — `moneta_provenance()` reports `schema_registered=True`.

### Phase 5: Memory Unification (Days 21-25)

**Goal:** Merge the structured Moneta store with the markdown Living Memory system.

| Task | Files | Effort | Risk |
|---|---|---|---|
| P5-1: Write scene_memory entries to Moneta | `scene_memory.py` | 2 days | Medium |
| P5-2: Backfill existing markdown into Moneta | `backfill.py` | 1 day | Low |
| P5-3: Remove evolution.py | `memory/evolution.py` | 1 hour | Low |
| P5-4: Unify recall/search across all memory | `handlers_memory.py` | 3-5 days | High |

**Verification:** `test_unified_recall` — write memory through scene_memory, search through Moneta, assert found. `test_evolution_removed` — `import evolution` raises ImportError.

---

## 3. RSI LOOP CLOSURE PLAN

### Loop C: Substrate (currently L0, blocked at L0)

**Current state:** RATIFY-AND-STABILIZE adopted. Moneta IS the substrate. C-0 address bug fixed.

**To close L1 (HONEST):** The substrate CAN represent failure — `backend_fallback()` telemetry + doctor check already do this. L1 is effectively met.

**To close L2 (REACHABLE):** The substrate IS reached — 21/21 production inits. L2 is met.

**To close L3 (CONSUMED):** Something reads the substrate state AND a later decision differs. The doctor reads it. L3 is met.

**To close L4 (DURABLE):** The substrate survives a real process restart. The 159-row snapshot proves this. L4 is met.

**Action:** Promote loop C to L4. Flip `human_ratified` after Joe signs off.

### Loop R: Render-farm learning (currently L1, blocked at L2)

**Current state:** Signal is honest. Wiring is present. No production render has run.

**To close L2 (REACHABLE):** Run a render through the farm. This is blocked on production usage, not code.

**Action:** No code change needed. Monitor for first production render.

### Loop A3: Memory evolution (currently L2, blocked at L3)

**Current state:** evolution.py declares itself SUPERSEDED. Under moneta backend, it's dead code.

**To close L3 (CONSUMED):** Remove evolution.py. The Moneta store never triggers it.

**Action:** Remove `python/synapse/memory/evolution.py` and its call sites in `store.py:_check_evolution`. This is safe once Moneta is the default (Phase 0).

### Loop O: Observability (currently L0, blocked at L1)

**Current state:** RecommendationHistory exists. ConductorAdvisor reads bridge stats. But one input (router fingerprint counts) is failure-blind.

**To close L1 (HONEST):** Wire `MOERouter.outcome_counts()` into `ConductorAdvisor.analyze()`.

**Action:** Pass `router.outcome_counts()` alongside `router.fingerprint_counts()` in `advise_from_bridge()`.

### Loop S: Science registry (currently L0, blocked at L1)

**Current state:** The deposit_fn seam is live — `scripts/run_apex_verify.py` deposits 16 records per run. L2 is met.

**To close L1 (HONEST):** The signal CAN represent failure — it does (deposit failures are collected on `.failures`).

**Action:** Promote S to L2. The seam is already honest and reachable.

---

## 4. AGENT TEAM STRUCTURE

Each phase uses a dedicated agent team. Teams run sequentially (phases depend on each other), but tasks within a phase run in parallel where possible.

### Team Structure

```
Phase 0 Team (Foundation)
  ├── Agent 1: Ratify loop C + update REGISTRY.json
  ├── Agent 2: Fix Memory.id collision (models.py)
  └── Agent 3: Pin deps (pyproject.toml, ci.yml)

Phase 1 Team (Durability)
  ├── Agent 1: Add periodic save timer (moneta_store.py)
  ├── Agent 2: Add crash recovery test
  └── Agent 3: Document durability bounds

Phase 2 Team (Vector Recall)
  ├── Agent 1: Fix cosine clamp upstream (moneta package)
  ├── Agent 2: Wire vector recall in shadow (moneta_store.py)
  └── Agent 3: Add parity tests

Phase 3 Team (Consolidation)
  ├── Agent 1: Gate run_sleep_pass (handlers_memory.py)
  ├── Agent 2: Wire periodic sleep pass (moneta_store.py)
  └── Agent 3: Add attention signaling + tests

Phase 4 Team (USD Substrate)
  ├── Agent 1: Register schema (packages/synapse.json)
  ├── Agent 2: Fix USD read path upstream
  └── Agent 3: Enable use_real_usd + tests

Phase 5 Team (Unification)
  ├── Agent 1: Write scene_memory to Moneta
  ├── Agent 2: Backfill + remove evolution.py
  └── Agent 3: Unify recall/search
```

### Agent Handoff Protocol

```
Phase N-1 completes → Phase N begins
  ├── All Phase N-1 tests pass
  ├── All Phase N-1 verification criteria met
  └── Phase N-1 changes merged to working branch
```

---

## 5. EVALUATION HARNESS

### Per-Phase Acceptance Criteria

| Phase | Must pass | Must not regress |
|---|---|---|
| P0 | All moneta tests green | Existing test suite |
| P1 | Crash recovery test passes | Memory throughput |
| P2 | Vector recall parity >= 0.95 | Keyword recall quality |
| P3 | Consolidation prunes correctly | Protected memories survive |
| P4 | USD round-trip works | Moneta startup time |
| P5 | Unified recall finds all memories | Scene_memory writes |

### Regression Floor

```
pytest tests/ --tb=short -q | tail -1
# Must not decrease from current: 5393 passed
```

### Mutation Tests

Each phase includes mutation tests that verify the fix is real:
- P1: Remove save timer → crash test fails
- P2: Disable vector recall → parity test fails
- P3: Remove gate → sleep pass runs ungated
- P4: Remove schema registration → USD test fails
- P5: Remove unification → recall misses markdown entries

---

## 6. RISK REGISTER

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Periodic save timer slows adds | LOW | MEDIUM | Timer check is O(1); save is O(n) but only every 30s |
| Vector recall degrades search | MEDIUM | MEDIUM | Shadow-compare before flip; keep keyword fallback |
| Consolidation prunes wanted memories | LOW | MEDIUM | PruneAudit logs every prune; protected floors prevent it |
| USD schema registration breaks pxr | LOW | MEDIUM | Test in CI first; env var is reversible |
| Memory unification loses data | LOW | HIGH | Backup-first migration; keep markdown as export view |
| Moneta upstream changes break adapter | LOW | HIGH | Pin dependency; CI exercises Moneta |

---

## 7. EXECUTION ORDER (RECOMMENDED)

```
Week 1:  Phase 0 (Foundation) + Phase 1 (Durability)
Week 2:  Phase 2 (Vector Recall)
Week 3:  Phase 3 (Consolidation & Attention)
Week 4:  Phase 4 (USD Substrate)
Week 5:  Phase 5 (Memory Unification)
```

**The critical path:** Phase 0 → Phase 1 → Phase 2. Everything else can be reordered.

**The single highest-leverage item:** Phase 1 — the 30-second periodic save timer. One day of work closes the crash-loss window that is the only genuine production risk.

---

## 8. WHAT SUCCESS LOOKS LIKE

After all five phases:

1. **Every Moneta deposit is durable** — at most 30s of data lost on crash
2. **Vector recall is live** — the vector index is read, not just written
3. **Consolidation runs automatically** — low-utility memories are pruned, protected ones survive
4. **Attention boosts frequently-accessed memories** — recall improves with use
5. **USD substrate is real** — typed MonetaMemory prims on disk, schema registered
6. **Memory systems are unified** — one recall/search across all memory
7. **RSI loops are closed** — C at L4, R at L2, A3 removed, O at L1, S at L2
8. **Moneta dependency is pinned** — versioned, tested in CI, drift is loud

---

## 9. ROLLBACK GUIDE

Each change made in Phases 0-5 is documented below with its rollback command, data safety considerations, and order dependencies.

### Phase 0: Foundation

#### Memory.id collision fix (`python/synapse/memory/models.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or manually revert the `Memory.id` field change in `models.py` |
| **Data safety** | No data loss. The fix only changes how IDs are generated (deduplication logic). Reverting means old ID collision behavior returns — duplicate IDs may reappear on concurrent deposits, but no stored data is removed. |
| **Order** | None. Independent of all other changes. |

#### Moneta dep pin (`pyproject.toml`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or remove the `moneta` version pin from `[tool.poetry.dependencies]` / `[project.dependencies]` |
| **Data safety** | No data loss. Unpinning means future `pip install` may pull a newer Moneta version. If the newer version is backward-compatible, no issue. If not, the adapter layer may break. |
| **Order** | Roll back before CI Moneta ref pin if both point to the same version. |

#### CI Moneta ref pin (`.github/workflows/ci.yml`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or revert the `MONETA_REF` / `moneta-version` entry in the CI workflow YAML |
| **Data safety** | No data loss. CI will use the default (latest) Moneta ref instead of the pinned one. May cause CI drift if upstream Moneta changes. |
| **Order** | Roll back after or alongside the pyproject.toml pin if both reference the same version. |

#### Loop C ratification (`harness/rsi/REGISTRY.json`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or manually set loop C's `human_ratified` back to `false` and `level` back to its prior value in `REGISTRY.json` |
| **Data safety** | No data loss. The registry is a metadata file. Ratification status is advisory — reverting it does not change any runtime behavior. |
| **Order** | None. Independent. |

### Phase 1: Durability

#### Periodic save timer (`python/synapse/memory/moneta_store.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or remove the `_save_interval` / `_last_save` logic from `MonetaBackedStore.__init__()` and `add()` |
| **Data safety** | **Data loss risk.** Reverting removes the periodic save safety net. On process crash, all deposits since the last explicit `save()` or `close()` are lost. The crash-loss window reverts from 30s to unbounded. |
| **Order** | None. Independent of other phases. |

### Phase 2: Vector Recall

#### Cosine clamp fix (`moneta/api.py`, `moneta/vector_index.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or revert the `clamp(cosine, -1.0, 1.0)` / `max(-1.0, min(1.0, cosine))` change in the moneta package |
| **Data safety** | No data loss. Reverting means cosine values outside [-1, 1] may cause NaN in similarity scores, degrading recall quality. No stored data is affected. |
| **Order** | Roll back before vector recall wiring if the fix is a prerequisite for vector recall correctness. |

#### Vector recall wiring (`python/synapse/memory/moneta_store.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or revert `MonetaBackedStore.search()` to use keyword-only recall (iterate all memories, score by text match) |
| **Data safety** | No data loss. Search falls back to the slower keyword path. The vector index continues to be written (Moneta's own indexing is unaffected), but it is no longer read by the store. |
| **Order** | Roll back before or alongside the cosine clamp fix. |

### Phase 3: Consolidation & Attention

#### Periodic consolidation (`python/synapse/memory/moneta_store.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or remove the `_add_count` / modulo check and `run_sleep_pass()` call from `MonetaBackedStore.add()` |
| **Data safety** | **Data growth risk.** Reverting stops automatic pruning. Unprotected low-utility memories accumulate indefinitely, increasing store size and recall latency. No data is lost — the opposite: nothing gets pruned. |
| **Order** | Roll back after the sleep pass gate (P3-1) if the gate was added first. |

#### Attention signaling (`python/synapse/memory/moneta_store.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or remove the `signal_attention()` call from `MonetaBackedStore.search()` |
| **Data safety** | No data loss. Attention weights stop being updated on recall. Utility scores for frequently-accessed memories will decay naturally over time instead of being boosted. |
| **Order** | None. Independent. |

#### Sleep pass gate (`python/synapse/memory/handlers_memory.py`, `shared/constants.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or remove the `HumanGate` check from the `run_sleep_pass` handler and revert the gate level constant |
| **Data safety** | **Destructive risk.** Reverting removes the consent gate. `run_sleep_pass` becomes callable without human approval, which means consolidation can prune memories without oversight. Only revert if the gate is replaced by equivalent protection. |
| **Order** | Roll back before periodic consolidation (P3-2) if you want to prevent unattended pruning. |

### Phase 4: USD Substrate

#### Schema registration (`packages/synapse.json`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or remove the `PXR_PLUGINPATH_NAME` / `MONETA_USD_SCHEMA` env var from the package environment block |
| **Data safety** | No data loss. The USD schema is no longer registered, so `pxr` cannot resolve `MonetaMemory` prim types. Existing USD files on disk remain — they just can't be read through the typed schema. Raw USD I/O still works. |
| **Order** | Roll back before `use_real_usd` (P4-3) if schema registration is a prerequisite. |

#### `use_real_usd` (`python/synapse/memory/moneta_store.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or set `use_real_usd=False` in `MonetaConfig` and revert the USD write path in `MonetaBackedStore` |
| **Data safety** | **Data format change.** Reverting switches storage from real USD layers back to the JSON-in-Moneta fallback. Existing USD layers on disk are orphaned — they are not read by the fallback path. No data is deleted, but the USD layers become cold storage. Migration script needed to re-import. |
| **Order** | Roll back after schema registration (P4-1). Roll back before any Phase 5 changes that depend on real USD. |

### Phase 5: Memory Unification

#### Scene memory Moneta deposit (`python/synapse/memory/scene_memory.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or revert the Moneta `add()` call in `scene_memory.py` back to the old markdown-only write path |
| **Data safety** | **Data loss risk for new entries.** Reverting means scene memory entries written after the rollback go only to markdown, not to Moneta. Existing Moneta entries are untouched. The two stores diverge until a backfill runs. |
| **Order** | Roll back before unified recall (P5-4). |

#### `evolution.py` removal

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or restore `python/synapse/memory/evolution.py` from git: `git checkout <prior-sha> -- python/synapse/memory/evolution.py` |
| **Data safety** | No data loss. The file is dead code under Moneta. Restoring it re-enables the evolution path, but since Moneta is the default store, the evolution code path is never reached. Pure code resurrection. |
| **Order** | None. Independent. |

#### Unified recall (`python/synapse/memory/handlers_memory.py`)

| Field | Detail |
|---|---|
| **Rollback** | `git revert <commit-sha>` or revert `handlers_memory.py` to query Moneta and markdown stores separately, returning disjoint results |
| **Data safety** | No data loss. Recall splits back into two independent queries. Results may miss entries that were only in one store. No stored data is affected. |
| **Order** | Roll back after scene memory Moneta deposit (P5-1) and before removing evolution.py (P5-3) if the unified path depends on those. |

### Bulk Rollback

To roll back all phases at once:

```bash
# Identify the merge commit or last commit before Phase 0
git log --oneline --grep="Phase 0"  # find the first Phase 0 commit
git revert <first-phase-0-commit>..HEAD  # revert all changes since Phase 0 began
```

**Data safety for bulk rollback:**
- Any memories deposited through the Moneta store during Phases 1-5 remain in the Moneta database. The rollback does not delete them — they become orphaned if the code reverts to a pre-Moneta store.
- USD layers written during Phase 4 remain on disk but are unreadable without the schema registration.
- The crash-loss window widens from 30s back to unbounded.
- Consolidation stops — accumulated low-utility memories are no longer pruned.

**Recommended bulk rollback order (if doing it manually):**
1. Unified recall (P5-4)
2. Scene memory Moneta deposit (P5-1)
3. `use_real_usd` (P4-3)
4. Schema registration (P4-1)
5. Periodic consolidation (P3-2)
6. Sleep pass gate (P3-1)
7. Attention signaling (P3-3)
8. Vector recall wiring (P2-2)
9. Cosine clamp fix (P2-1)
10. Periodic save timer (P1-1)
11. All Phase 0 changes (any order)
