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
| 8 | Backfill (count-agnostic, backup-first), evolution.py retired, this report | `memory/backfill.py`, `memory/evolution.py` |

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

**Documented bounded weaknesses (pinned by tests):**
- **Decay/consolidation expires unprotected memories** — but ONLY on explicit
  `run_sleep_pass`; normal add/read never loses data. Decisions/SHOW-tier/gate
  are protected. (Behavior change from JSONL's never-delete; it is the intended
  consolidation feature, made observable and opt-in.)
- **Single-writer (FC4)** — Moneta's ECS is single-writer. Concurrent `add` is
  GIL-atomic today, but a concurrent prune (`ecs.remove`) corrupts state. The
  async FastMCP server **must serialize all memory mutations onto one thread**
  (the same discipline the bridge uses for `hou.*`). The background snapshot
  daemon is deliberately NOT started for this reason.
- **`Memory.id` upstream collision** — `id` hashes content+type (created_at is
  empty at id-time), so identical content+type collides. JSONL dedups by id;
  Moneta appends both. Pinned; fix belongs in `models.py` (out of scope here).
- **`get_by_tag` raw case-sensitivity** (matches `search` semantics; no live
  callers); **shadow mode** runs the JSONL primary so evolution.py still fires
  there (only pure `moneta` retires it).

## Cutover procedure (staged — NOT auto-flipped)

The flag stays **default `jsonl`**. The one action deliberately *not* taken from
a standalone session is flipping production to `moneta` by default, because the
**FC4 async-server deadlock/serialization check requires the running FastMCP
server** and cannot be verified headless. Recommended sequence:

1. Set `SYNAPSE_MEMORY_BACKEND=shadow` in a live session; accumulate parity over
   real traffic (target ratio 1.0 — already 1.0 in tests).
2. Verify under the live async server that memory mutations are serialized (no
   concurrent `run_sleep_pass` vs `add`); confirm no deadlock (the known Spike
   2.4 main-thread/daemon hazard class).
3. Run `python -m synapse.memory.backfill <.synapse> --execute` (backup-first).
4. Flip default to `moneta`; remove `evolution.py`; keep markdown as an export
   view.

## Test status
All new suites green: embedding (25), moneta_runtime (5), moneta_store (16),
shadow_store (6), moneta_integration (5), moneta_crucible (30), backfill (5).
Full suite: pre-existing pxr-env failures only (untouched files); zero new
regressions.
