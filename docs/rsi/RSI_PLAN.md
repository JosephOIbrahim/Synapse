# RSI SEED PLAN — the six audit items as lines

> **Logical layer:** PLAN (the live line structure). **Authored at:** INGEST.
> **Source:** `SYNAPSE_RSI_AUDIT.md` verdicts, transcribed per the harness SEED PLAN.
> **ROI = the audit's ordering, default until re-ranked in DELIBERATE.**
> Per-line *verifier state* (the notch) lives in `RSI_CHAMPION.md`; this file
> holds the *definitions*. The two are read together, never duplicated.

Each line names the **CLAIM** to verify (file:line), the **VERIFY** (the first
FORGE action — confirm-or-falsify before paying execution cost), the **CHANGE**,
what it **CLOSES** (the verifier that closes it), and the **NOTE**.

Lines R / O / S / F are the independent one-liners — held open together in
SIMULATED TEAM mode. Line E is the build (anti-lock-in machinery stays hot).
Line C is the INTEGRATE gate.

---

## LINE R — render-farm learning — **ROI 1 (highest)**

- **CLAIM** *(audit asserts — to confirm-or-falsify at L0)* — `server/render_diagnostics.py` learning is gated behind a dead
  guard: `_handle_render_sequence` injects memory only
  `if hasattr(self, '_memory') and self._memory is not None`
  (`handlers_render.py:858`), and `SynapseHandler.__init__` **never sets**
  `self._memory` → always `False` → every render runs with `memory=None`. The
  working pattern already exists at `handlers.py:1397` (`_handle_autonomous_render`).
- **VERIFY** — read both sites. Confirm the guard is permanently false and the
  `:1397` pattern is live. **CRUCIBLE:** is there ANY other path that sets
  `self._memory` (a second call site, a mixin, a late binding)? If yes, the
  claim is falsified.
- **CHANGE** — in `_handle_render_sequence`, replace the dead `hasattr` guard
  with `get_synapse_memory()` (mirror `:1397`). One line.
- **CLOSES** — **L2** across renders AND sessions: `record_fix_outcome()` →
  FEEDBACK JSONL → `_warmup_from_memory()` compounds on restart. **L3:** a
  learned fix changes a later render's settings vs. the static `ISSUE_REMEDIES`
  baseline.
- **NOTE** — fully-built code, currently unreachable. The audit asserts the
  persistence substrate already exists (rides the SynapseMemory FEEDBACK store) —
  if confirmed at L0, this is the only line seeded with persistence in place and
  its gap is *reachability* only.
- **STATUS (2026-06-01)** — ✅ **CLOSED at L2 (+L3).** Claim confirmed (survived
  7 CRUCIBLE attacks, zero drift); fix wired at `handlers_render.py`; 384 tests
  pass; eval `tests/rsi/eval_line_r_closure.py` proved L1/L2/L3 across two fresh
  processes. **Boundary:** `tops_render_sequence` (the PDG render path) is a
  *separate* entry that does not pass through this guard — a candidate follow-up
  line, not part of R's one-liner. Hardening left: L4 tier-integrity (STRESS).

## LINE O — §16 recursive observability — **ROI 2**

- **CLAIM** *(audit asserts — to confirm-or-falsify at L0)* — `RecommendationHistory` / `record()` / `to_jsonl` / `from_jsonl` /
  `analyze_history()` have **zero non-test callers**. The panel
  (`panel/agent_health.py:129`, `advise_from_bridge()`) computes recs fresh each
  poll and discards them; the `(kind,target) ≥5× → escalate` meta-recursion
  never fires in production.
- **VERIFY** — grep callers of each symbol. Confirm the lower half is dormant,
  not wired elsewhere (a daemon, a CLI, a test fixture that smuggles it live).
- **CHANGE** — one module-level `RecommendationHistory`: `from_jsonl()` at start,
  `record()` + `to_jsonl()` inside `_update_agent_health`, feed
  `analyze_history()` into the display.
- **CLOSES** — **L2:** history reloads on restart. **L3:** the ≥5× escalation
  actually fires and shows in the panel vs. a cold (no-history) baseline.
- **NOTE** — activates the entire dormant, already-tested lower half with one
  wiring change.

## LINE S — science registry → substrate — **ROI 3**

- **CLAIM** *(audit asserts — to confirm-or-falsify at L0)* — `deposit_fn` is wired to `None` at the `run_apex_verify`
  entrypoint; the registry exists (`.synapse/science/apex_registry.jsonl`) but
  never reaches the durable layer. The hook is documented as the Moneta /
  `synapse_write_report` injection point.
- **VERIFY** — read `run_apex_verify`. Confirm `deposit_fn=None` and that the
  hook is documented as the Moneta injection point.
- **CHANGE** — pass a `deposit_fn` at the entrypoint so dead-ends / champions
  persist into the PROTECTED tier.
- **CLOSES** — **L2 (closure, per the harness SEED PLAN):** falsifiability
  records survive into the durable substrate. **L3 (stretch, INGEST-proposed —
  the audit calls science's apply-half "records by design"):** a persisted
  dead-end makes a later `run_search` skip the known-absent surface vs. a cold
  registry.
- **NOTE** — feeds the protected tier directly — a partial down-payment on
  Line C. **Provenance note (see `RSI_DEADENDS.md`):** the registry's 10
  `nodetype` dead-ends are confirmed-absent *as spelled* (corrected probe); their
  real H21 type names may differ. A real-name discovery pass is parked for
  DELIBERATE, not decided here.

## LINE F — router learned fast-paths — **ROI 4**

- **CLAIM** *(audit asserts — to confirm-or-falsify at L0)* — `_session_fast_paths` is promoted **live inside `route()`** but is
  **in-memory only** — the single zero-persistence RSI store; it dies with the
  process. The §16 advisor exists precisely to ask a human to hand-promote these
  into the durable `FAST_PATHS`.
- **VERIFY** — read `route()`. Confirm promotion is live and storage is
  in-memory only.
- **CHANGE** — back `_session_fast_paths` with the substrate so promotions
  survive restart.
- **CLOSES** — **L2:** a learned fast-path short-circuits `route()` after a
  restart. **L3:** routing actually changes vs. a cold start.
- **NOTE** — EPHEMERAL-BY-DESIGN today — this line changes that design decision.
  L2-as-closure is the GOAL, not the start state.

## LINE E — FORGE engine: the real build — **ROI 5 (the build)**

- **CLAIM** *(audit asserts — to confirm-or-falsify at L0)* — `orchestrator.py:172-177` increments `fixes_applied += 1`
  `# Optimistic` and **discards the intent** — no fix generated, applied, or
  written; `fixes_validated` hardcoded `0` (`:214`). "Verify via re-run" is
  `FORGE.md` prose only. `forge/corpus/patterns/` (the middle maturity stage)
  doesn't exist on disk. No runnable entry point (no `__main__`/argparse);
  the corpus was seeded once (`ingest_relay_solaris.py`, all `created_cycle:0`).
- **VERIFY** — read `:172-177` and `:214`. Confirm the increment is optimistic
  and validation is hardcoded.
- **BUILD** — the executable stage: fix-generate → apply ATOMICALLY (undo-group
  wrapper, idempotent guard) → re-run-verify → set `fixes_validated` from the
  actual re-run. Add a runnable entry point. Make the corpus grow per-cycle
  (instantiate the missing `patterns/` middle stage).
- **CLOSES** — `fixes_validated` reflects reality; corpus demonstrably grows
  cycle-over-cycle (not all `created_cycle:0`).
- **NOTE** — the ONE large item. **KEEP full anti-lock-in machinery:**
  stagnation→reorganize, parallel sub-lines if the build forks, CRUCIBLE hostile
  from the start. Do not let the audit's framing lock the implementation
  trajectory.

## LINE C — convergence: two-tier substrate — **ROI 6 (= INTEGRATE gate)**

- **GOAL** — one durable substrate, two tiers:
  - **PROTECTED-IMMUTABLE** — falsifiability records + FORGE rules; never
    decays, never overwrites.
  - **DECAYING** — recommendations + render-fixes; inherits Moneta decay /
    consolidation / protected-floor / PruneAudit.
- **SHAPE** — **SUBTRACTIVE:** delete the five bespoke append-logs, repoint
  their persistence at the correct tier. Pure-logic layers untouched. Unlocks
  vector recall ACROSS all learned knowledge (today a render fix can't find a
  FORGE rule). The science registry's `deposit_fn` is the model wiring.
- **CLOSES** — system-level **L2** after migration; **L4** tier-integrity proofs
  at STRESS. This line IS the INTEGRATE gate.

---

### Ordering fork (to be RESOLVED in the first DELIBERATE, not here)

Close the one-liners onto TODAY's store and migrate to the two-tier substrate
later (Line C), OR build the substrate first? The audit's evidence — persistence
is already pluggable (`deposit_fn`, `SYNAPSE_MEMORY_BACKEND`) — argues
"close now, swap backend later" is LOW-rework, so the ROI ordering above
survives critique. **CRUCIBLE must confirm the swap-seam actually exists at each
cited point before the fork is settled.** This belongs to DELIBERATE — INGEST
records the default ordering and stops.
