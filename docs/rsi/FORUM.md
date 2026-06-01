# FORUM — proposals · CRUCIBLE critiques · results

> **Logical layer:** FORUM. **Authored at:** INGEST (scaffold only).
> Net-new harness file. Coordination happens THROUGH this shared state — no
> central planner. Every wiring proposal gets adversarial CRUCIBLE review here
> **before** FORGE pays the execution cost. Weak claims die here.

**Status: ACTIVE — DELIBERATE ⇄ EXECUTE open (SPEC ratified 2026-06-01).**

## Log

### [DELIBERATE | line R] VERIFY-THE-AUDIT — render-farm dead `_memory` guard
- **PROPOSAL** — mirror `_handle_autonomous_render`: replace the always-false
  guard at `handlers_render.py:858` (`if hasattr(self,'_memory') and self._memory
  is not None`) with `get_synapse_memory()`, so `RenderFarmOrchestrator` receives
  a real store and `record_fix_outcome → FEEDBACK JSONL → _warmup_from_memory`
  compounds across renders/sessions.
- **CRUCIBLE** — attacked the claim 7 ways (hidden `__init__` setter; mixin /
  base / `@property` / `__getattr__`; class attr; post-construction DI; a second
  live entry; code drift). **CLAIM SURVIVES:** no path sets `self._memory` on
  `SynapseHandler` or any of its 11 mixins (none define `__init__`); the only
  `self._memory =` sites are unrelated classes (orchestrator, driver, router…).
  Zero drift — all cited lines exact. **Two complications (not falsifications):**
  (a) `tops_render_sequence` (`handlers.py:470 → _handle_tops_render_sequence`,
  the PDG path) is a SECOND render entry that never touches this guard — OUT OF
  SCOPE of the one-liner; a candidate follow-up line, not part of R. (b) the
  autonomy render path dispatches back through `_handle_render_sequence`, so it
  was starved too — the fix repairs that case as well (an argument FOR).
- **RESULT** — CONFIRMED. **R: dormant → claim-OK.**

### [DELIBERATE | fork] ORDERING FORK — close-now vs build-substrate-first
- **PROPOSAL** — close the one-liners onto today's jsonl store, migrate to Moneta
  at Line C (vs. building the two-tier substrate first).
- **CRUCIBLE** — confirmed the swap-seam at R's cited point: `get_synapse_memory()
  → SynapseMemory._make_store()` is backend-agnostic (`SYNAPSE_MEMORY_BACKEND`;
  jsonl default, moneta/shadow optional, fallback-on-failure). The fix wires a
  backend-agnostic handle; `record_fix_outcome`/`query_known_fixes` only touch
  `memory.add` + `memory.store.search`, which every backend implements. Closing R
  onto jsonl does NOT couple it to jsonl-forever — the only render-side rework to
  adopt Moneta later is the env flag. (Aside: Moneta is BUILT but default-OFF.)
- **RESULT** — RESOLVED: **"close now, swap backend later."** ROI ordering
  survives. The four one-liners close onto jsonl; Line C does the subtractive swap.

### [EXECUTE | line R] Wire `get_synapse_memory()` into `_handle_render_sequence`
- **PROPOSAL** — one mutation at `handlers_render.py:857-866` (dead guard → a
  `get_synapse_memory()` try/except mirroring `handlers.py:1396-1400`, local
  `logger`). No second edit: `RenderFarmOrchestrator` already null-guards
  `_memory`; handler `__init__` untouched.
- **CRUCIBLE** — test-impact watch (`test_render_farm_handler.py` hardcodes
  `handler._memory`): `get_synapse_memory()` degrades via try/except, so existing
  tests stay green. Verified.
- **RESULT** — **CLOSED.**
  - **L0** — claim confirmed; change parses/imports; **384 tests pass** (1 skip).
  - **L1** — in-process: `record_fix_outcome → query_known_fixes` reads it back
    (score 1.0).
  - **L2 — *** CLOSED *** ** across-restart, restart-aware: **2/2 FRESH python
    processes** reloaded the persisted FEEDBACK record (score 1.0).
  - **L3** — behavior-change: after restart, `_warmup_from_memory` returns the
    learned `{pathtracedsamples: 128.0}`; an empty store returns `{}`.
  - **Eval:** `tests/rsi/eval_line_r_closure.py`. **Boundary (honest):** the eval
    proves the store+orchestrator loop across a real restart (the harness's L2 for
    R); the handler wiring is proven by L0 + 384 green tests + the known-live
    mirror pattern, not by a live in-Houdini render.
  - **R: claim-OK → wired → L1 → L2 (CLOSED) → L3.**

## Entry format

```
### [<phase> | line <X>] <one-line proposal>
PROPOSAL   — the change + the verifier ladder + expected effect
CRUCIBLE   — the adversarial critique (the hidden cost, the second call site…)
RESULT     — PASS / FAIL / FALSIFIED, with the verifier evidence
```
