# PLAN — the RSI closure harness

*Six lines. Line IDs are `RL-<n>` to avoid colliding with loop IDs (`A1/A2/A3/R/O/S/F/E/C`) — note that
loop `E` and a line called "ratchet" would otherwise both want the letter E. Per the repo's citation
discipline, `RL-` is this harness's namespace and does not collide with `PL-M` (proof-leg) or `RBK-M`
(rulebook).*

**Nothing in this plan executes until SPEC.md is ratified.**

---

## Reading the board

`harness/progress.py` discovers this harness automatically (any `harness/*/verify.py` is a harness) and
renders its bar beside CLEAR's. There is no `harness/rsi/progress.py`, deliberately — a per-harness bar with
its layout baked in is the R140 defect that retired `harness/heats_status.py`.

    python harness/progress.py            # all harness bars + what is running now
    python harness/rsi/verify.py          # this harness only, 9 predicates

**A 9/9 bar means the registry is honest about the code. It does not mean the loops are closed.** At frame
time the bar reads 9/9 with *zero* loops beneficial and *zero* loops even reaching L3. That is the intended
reading: the predicates gate honesty, and closure is measured by rung, on CHAMPION.md.

---

## Line order, and why

The order is forced by the ladder, not chosen for convenience. `RL-2` cannot be skipped ahead of, because
every closure line below it would be closing onto a signal that cannot represent failure.

```
RL-1 RECONCILE ──► RL-2 SIGNAL ──► RL-3 DECIDE ──► RL-5 RATCHET
       │                 │                              ▲
       │                 └──────► RL-4 BENEFIT ─────────┘
       └──────────────────────────────────────► RL-6 DECAY WATCH (continuous)
```

---

## RL-1 · RECONCILE · blocks everything

**Goal:** one true starting state. Today six of nine loops sit at `rungs_proven: []` — not because they are
worthless, but because their evidence is two months old and *numbered on a different ladder*.

**The ladder collision, stated once.** The June harness (`docs/rsi/SPEC.md`) used L0–L4 with different
meanings: **June-L2 meant "survives a real restart"**, which is *this* ladder's **L4**; **June-L3 meant
"alters a later decision"**, which is this ladder's **L3**. So "Line R closed at L2+L3" does not import. It
must be re-derived, rung by rung, against HEAD.

**Work:**
1. For `R` and `O`, re-derive every rung at HEAD under this ladder. Both have named fix commits (`a8bdd6d`,
   `a8a2627`) and `R` has an eval at `tests/rsi/eval_line_r_closure.py` (`f43a534`) — confirm all three still
   exist and still pass before recording anything.
2. For `S`, `F`, `E`, locate the real call sites. Three carried claims have **unconfirmed paths**:
   `deposit_fn=None at run_apex_verify` (S), and `orchestrator.py:172-177` / `:214` (E) — the file may have
   moved. A claim whose path does not resolve is not demoted, it is *re-located or dropped*.
3. Record `R`'s known parked boundary: `tops_render_sequence` (the PDG path) is a separate render entry that
   never hit the guard.

**Done when:** every loop has a rung derived from evidence gathered at HEAD, and `P2`/`P3` still pass.

**Human gate:** none. Read-only re-derivation.

---

## RL-2 · SIGNAL · highest leverage in the harness

**Goal:** make the loops able to observe their own failure. This is the line that distinguishes this harness
from June's.

**Work — `A1`, the router reward signal.** Three independent defects, all re-verified at HEAD `f427320`:
1. Eight call sites pass only `(tier, latency_ms)` — `router.py` :285, :448, :515, :554, :584, :706, :742,
   :819 — so `success` takes its `True` default at `router.py:917` every time, forever.
2. `_try_tier0` hardcodes `RoutingResult(success=True, …)` at `router.py:537` without consulting the
   `responses` it just collected, which can carry `success=False`. This is a status describing what was
   *attempted*, not what *happened*.
3. The `no_tier_matched` fallback (`router.py:367-373`) never calls `_record_metric` at all, so genuine
   failures do not even enter the sample.

Fix all three or none. Fixing only (1) still leaves tier-0 lying and failures invisible.

**Work — `E`, the FORGE validation counter.** If `RL-1` confirms `fixes_validated` is a hardcoded `0`, it is
the same defect class: the loop authoring its own success value. Same fix shape.

**Verification:** `harness/rsi/verify.py` P4 flips *itself* when this lands — it greps `router.py` rather
than reading a status field. Expect P4's reason line to change from "still constant" to "now carries an
outcome", at which point the registry must be updated in the same commit or P4 goes red for staleness. That
is intentional: the bar catches a code fix that did not update the registry, and a registry update that did
not fix the code.

**Regression risk:** honest failure reporting changes routing behaviour the moment anything consumes it.
Nothing consumes it today (that is `A1`'s L3 gap), so this line is safe to land *before* closure — which is
precisely why it goes first.

**Human gate: YES.** Signal semantics are artist-facing routing behaviour.

---

## RL-3 · DECIDE · the two questions that are not engineering

**`A2` — wire or delete.** `OutcomeTracker` has never recorded a single outcome and cannot: `AgentExecutor`
has zero non-test constructions, the only occurrence being inside a module docstring
(`python/synapse/agent/__init__.py:12`). It is unreachable, not merely unfed. Either it is the missing
substrate every other loop needs, or it is dead weight. Resurrecting it by default is the wrong reflex.

**`C` — substrate before persistence.** Moneta is built and importable but default-OFF; `store.py:810`
defaults `SYNAPSE_MEMORY_BACKEND` to `jsonl` and it is unset on this machine. Confounder to avoid:
`.synapse/config.yaml:17` says `memory_backend: "flat"`, a **different key the store selector never reads** —
it is not configuration, and must not be cited as such. Decide the substrate before any loop persists onto
it, or the persistence work lands on ground that is about to move.

**Human gate: YES, both.**

---

## RL-4 · BENEFIT LEDGER · makes L5 reachable at all

**Goal:** without this, no loop can *ever* be proven beneficial, and the harness degenerates into the exact
failure it was built to prevent — recording more, benefiting none.

**Work:** a before/after measurement substrate. Each closed loop declares one task-outcome metric with a
producer path, measured on both sides of the closure. The `P6` blacklist already refuses the tempting
substitutes: recommendations generated, epochs closed, cycles run, memories written, items recorded.

**Candidate metrics** (must be task outcomes, not machinery counts): routing accuracy against a fixed input
set · phantom-API emission rate · turns-to-completion on a fixed scene task · failed-operation rate.

**Design constraint learned in this repo:** do not pin a control to the figure printed in the document under
test. A control copied from the brief passes green while pinning the brief's error — that has happened here
before, where a "161" was really 171.

**Human gate:** none to build. Ratifying a metric as *the* benefit metric is a human call.

---

## RL-5 · RATCHET · protect what closed

**Goal:** a proven rung cannot silently regress.

**Work:** one pinning test per proven rung. Follow the existing house pattern — *protect green → select red →
fix → prove real → protect green* — and read the suite floor at `merge-base(master, HEAD)` so a sprint
cannot lower its own bar. Advance only on human-promoted counts.

**Done when:** every loop with `rungs_proven` non-empty has a test that fails if that rung regresses.

---

## RL-6 · DECAY WATCH · continuous

**Goal:** notice when the system quietly stops improving.

Two decay signals, both already visible:

1. **Rung regression** — a loop drops a rung. `RL-5`'s pinning tests are the detector.
2. **Ratification stall** — proposals aging unratified. `harness/state/flywheel_queue.json` currently holds
   `U.2`, `U.3`, `U.4` and `C.0` as unratified candidates. A cycle queue that generates candidates faster
   than a human ratifies them **is an RSI stall**: the loop's apply step is a human who has not been asked
   at a good moment. Surfacing the age is the harness's job; flipping `ratified` is never the harness's job.

**Human gate:** the harness reports ages and ranks. It never flips `ratified`.

---

## Falsification, restated as a scoreboard

From SPEC.md, the most likely way this harness fails: **it produces more registry bookkeeping than closed
rungs across two full runs.** If run 2 ends with more registry prose and the same rung count as run 1, stop
and say so plainly rather than writing a third RSI harness.
