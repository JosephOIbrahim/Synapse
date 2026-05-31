# Moneta ↔ SYNAPSE — Ship Report (Miles 2–8)

> **Outcome:** SYNAPSE's memory operations can be served by an in-process Moneta
> engine behind the unchanged `MemoryStore` interface. The two-store divergence,
> the dead gauge, the empty stubs, and the read/write path divergence become
> *structurally impossible* — there is one store and `count()` reads the engine's
> live entity count. Delivered **shadow-first, flag-gated, default-off.**

Governed by `MONETA_SYNAPSE_INTEGRATION_HARNESS.md`. Lenses: ARCHITECT / FORGE /
CRUCIBLE. Ratification: the Reconcile→Replace reversal (harness §10 Gate 1) was
ratified under delegated CTO authority for this run; production cutover stays
gated (below).

## What shipped

| Mile | Deliverable | Files |
|---|---|---|
| 2 | Deterministic `HashEmbedder` behind `Embedder` (PYTHONHASHSEED-independent) | `memory/embedding.py` |
| 3 | Import-guarded Moneta runtime; pxr-free ephemeral path | `memory/moneta_runtime.py` |
| 4 | `MonetaBackedStore` adapter (flag-gated, default off) | `memory/moneta_store.py`, `memory/store.py` |
| 5 | Shadow dual-write + parity diff harness | `memory/shadow_store.py` |
| 6 | Integration / composition, URI-lock seam | `tests/test_moneta_integration.py` |
| 7 | CRUCIBLE L4 fixes + adversarial pins | `memory/moneta_store.py`, `tests/test_moneta_crucible.py` |
| 8 | Backfill (count-agnostic, backup-first); `memory/evolution.py` deprecated + dormant under moneta (removal deferred to cutover); this report | `memory/backfill.py`, `memory/evolution.py` |

**Backend flag** (`SYNAPSE_MEMORY_BACKEND`, in `SynapseMemory._make_store`):
`jsonl` (default, unchanged) · `moneta` (in-process engine) · `shadow` (jsonl
primary + moneta shadow with parity diff). Unknown/unavailable → safe fallback to
`jsonl`; never breaks startup.

## Acceptance predicates

| AP | Status | Evidence |
|---|---|---|
| AP1 — Moneta API exists in H21 | ✅ (Mile 1, prior) | dir() 10/10 in H21.0.671; source re-verified here |
| AP2 — deposit→query round-trip | ✅ | `test_moneta_runtime` |
| AP3 — adapter honors MemoryStore contract | ✅ | `test_moneta_store`, `test_moneta_integration` |
| AP4 — gauge == count | ✅ | gauge *is* `store.count()` = `ecs.n` (`test_gauge_invariant_holds_under_moneta`) |
| AP5 — shadow parity | ✅ 1.0 | search parity-by-construction; `test_shadow_store` |
| AP6 — mutations through HumanGate/IntegrityBlock | ⚠️ honest | the memory store has **no** gate today (pre-existing); the adapter adds no bypass — gating stays at the tool layer (memory ops are INFORM). Unchanged from JSONL. |
| AP7 — replay determinism | ✅ | `test_replay_determinism_same_inputs_same_state` |
| AP8 — pinned decisions survive decay | ✅ | `test_decision_survives_many_sleep_passes` |
| AP9 — CI runs with no pxr | ✅ | `test_ephemeral_path_is_pxr_free` (clean subprocess) |

## CRUCIBLE L4 — defects fixed, weaknesses bounded

A 4-agent adversarial fan-out attacked decay/data-loss, concurrency, payload
edges, and isolation/recovery. **Two real defects fixed:**

1. **Protected-quota silent demotion** — the 101st protected memory was silently
   re-deposited unprotected (Moneta `quota_override=100`) and became prunable.
   Fixed: `from_storage_dir` sets `quota_override=100000`.
2. **Corrupt-snapshot startup-killer** — Moneta `hydrate()` does a bare
   `json.load`. Fixed: snapshot validated and **quarantined** (renamed +
   ERROR-logged, preserved) on corruption; fresh start, no crash, no silent loss.

## FC4 — closed by construction (gap-closing pass)

The single-writer hazard (`run_sleep_pass`/`ecs.remove` corrupting the
swap-and-pop index under concurrency) is **no longer a live-gated weakness**.
`MonetaBackedStore` now holds a serialization `RLock` guarding every engine
access (`add`/`_iter_memories`/`count`/`save`/`run_sleep_pass`/`close`), with
reads taking an atomic snapshot under the lock. Deadlock-free against the async
server: the adapter makes **zero `hou.*` calls** (AST-pinned by
`test_adapter_imports_no_hou`), so the lock is never held across an `hdefereval`
main-thread hop — the two synchronization domains are disjoint. Proven by a
standalone concurrency suite (`tests/test_moneta_fc4_audit.py`: concurrent
add+prune, iterate-during-prune, add losslessness, count-under-churn). The
background snapshot daemon remains off (persistence is via the guarded `save`).

**Documented bounded weaknesses (pinned by tests):**
- **Decay/consolidation expires unprotected memories** — but ONLY on explicit
  `run_sleep_pass`; normal add/read never loses data. Decisions/SHOW-tier/gate
  are protected. Now **auditable**: `run_sleep_pass` returns a `PruneAudit`
  (pruned ids/payloads/types + before/after counts) and logs a WARNING on any
  prune — loss is never silent.
- **`Memory.id` upstream collision** — `id` hashes content+type (created_at is
  empty at id-time), so identical content+type collides. JSONL dedups by id;
  Moneta appends both. Backfill is unaffected (existing ids are already unique).
  Deferred follow-up (see below).
- **`get_by_tag` raw case-sensitivity** (matches `search` semantics; no live
  callers); **shadow mode** runs the JSONL primary so evolution.py still fires
  there (only pure `moneta` keeps it dormant).

## Cutover procedure (staged — NOT auto-flipped)

The flag stays **default `jsonl`**. FC4 thread-safety is now structural (above),
so the remaining gate is operational verification under the live server, not a
correctness unknown. Recommended sequence:

1. Set `SYNAPSE_MEMORY_BACKEND=shadow` in a live session; accumulate parity over
   real traffic (target ratio 1.0 — already 1.0 in tests).
2. Confirm under the live async server that the daemon routes memory mutations
   without contending the Spike 2.4 main-thread/daemon hazard class (the RLock
   makes the engine itself safe; this is a server-wiring sanity check).
3. Run `python -m synapse.memory.backfill <.synapse> --execute` (backup-first).
4. Flip default to `moneta`; physically remove
   `python/synapse/memory/evolution.py`; keep markdown as an export view.

## Deferred follow-ups (designed, not in this PR)

A 6-agent ARCHITECT pass specced these; they are intentionally out of this PR's
scope (risk / requires external provisioning), with the recipe captured:
- **`Memory.id` collision fix** — reorder `models.py.__post_init__` to default
  `created_at` before `_generate_id` (+ optional `time_ns`/uuid entropy). Touches
  shared `models.py` and inverts one pinned test; lands before/with the cutover,
  separate PR.
- **AP6 gating of `run_sleep_pass`** — add `sleep_pass: approve` to
  `OPERATION_GATES`, map a `synapse_sleep_pass` tool through `bridge_adapter`'s
  `execute_through_bridge`. Not load-bearing yet (no prod caller invokes
  `run_sleep_pass`); add when it is wired to a tool.
- **CI actually exercises Moneta** — deploy-key checkout of the private
  `JosephOIbrahim/Moneta` (zero-dep, pxr-free) + `pip install -e ./_moneta` +
  a no-silent-skip tripwire. Requires a `MONETA_DEPLOY_KEY` repo secret (Joe to
  provision); until then the ~66 Moneta tests skip on CI and run locally.

## Test status
All new suites green where Moneta is importable: embedding (25, runs on CI —
dependency-free), moneta_runtime (5), moneta_store (16), shadow_store (6),
moneta_integration (5), moneta_crucible (30), backfill (5), fc4_audit (8).
**~66 of these are `skipif not moneta_available` and SKIP on CI / clean clones**
(no `moneta` package); they pass locally where Moneta is present. Full suite:
3021 local passing; the 15 failures are the pre-existing pxr-env baseline in
untouched files (they expect a pxr-absent env and fail because pxr IS installed
locally); zero new regressions.
