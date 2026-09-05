# SPEC — the RSI closure harness

*The contract. **STATUS: RATIFIED 2026-08-01** (human sanction, Joe — CTO authority granted for this harness
and its running tasks). Written at FRAME 2026-08-01. Changed only at explicit ratification points; do not
edit without a ratified change.*

> **What ratification did and did not grant.** It opens the lines for execution. It does **not** promote any
> loop's rung. Rungs are promoted by evidence, never by permission — a blanket approval cannot manufacture a
> proof, and treating it as though it could is the precise failure this harness was built to prevent. Every
> loop below therefore keeps the rung its evidence supports, and `P8` still refuses any L4+ sitting without
> `human_ratified`.

---

## Why a second RSI harness exists

Two prior efforts disagree, and the disagreement is the reason this one exists.

**June 2026 — `docs/rsi/` + `docs/SYNAPSE_RSI_HARNESS.md`.** Six lines (R/O/S/F/E/C). Thesis: *every RSI loop
has its observe→analyze→record half built and its apply→persist→compound half dormant; find the dormant half
and wire it.* Lines R and O were closed and banked (`a8bdd6d`, `a8a2627`). Champion 2/6.

**July 2026 — `harness/notes/RSI_SURFACE_AUDIT.md` (leg RSI0, read-only).** Audited three *other* mechanisms
and produced this sentence:

> SYNAPSE has three RSI mechanisms. One has never completed a cycle in production and writes to a value
> nothing reads. One cannot be reached by any live code path. One runs on every memory write and ends in a
> log line. **Nothing in this codebase has ever improved itself.**

The audit did not merely find more dormant loops. It found that **wiring one of them would have been
actively harmful**, and that is the finding this harness is built around.

`EpochAdapter`'s reward signal is a hardcoded constant. `_record_metric` is declared
`(self, tier, latency_ms, success: bool = True)` at `router.py:917` and **not one of its eight call sites
passes `success`** (`router.py` :285, :448, :515, :554, :584, :706, :742, :819 — re-verified at HEAD
`f427320`, 2026-08-01). `_try_tier0` hardcodes `RoutingResult(success=True, …)` at `router.py:537` without
consulting the responses it just collected, some of which carry `success=False`. The `no_tier_matched`
fallback (`router.py:367-373`) never calls `_record_metric` at all, so genuine failures never enter the
sample.

Success rate is therefore permanently `1.0`. Probe P4 in the audit drove 300 outcomes and measured the
result: a monotonic slide to the `0.10` clamp floor in eight epochs, then flat forever. **It is not an
adaptive controller. It is a one-way ratchet.** It is safe today only because nothing reads its output.

So the June thesis — *find the dormant half and wire it* — is correct for R and O and dangerous as a general
rule. An RSI loop closed onto a dishonest signal does not improve anything; it propagates its own error
faithfully and at speed.

**This harness's contribution is one structural rung: a loop may not be closed until it can observe its own
failure.**

---

## Outcome

Every recursive-self-improvement mechanism in SYNAPSE is on **one** registry with a **proven** rung, an
explicit blocker, and — where it is still open — a written statement of what closing it today would break.
No loop advances past `L3 CONSUMED` without a human ratification flip. No loop is called *beneficial*
without a before/after task metric carrying a producer path.

The harness's success condition is **not** "more loops closed". It is: *no loop is closed onto a signal that
cannot represent failure, and every closure claim survives an attempt to refute it.*

---

## The Ladder

Six rungs plus one orthogonal attribute. A loop's rung is the **highest rung for which every rung below is
also proven** — rungs are a contiguous prefix, never a cherry-pick.

| Rung | Name | Proven when | Refuted by |
|---|---|---|---|
| **L0** | EXISTS | The mechanism is present in code | — |
| **L1** | **HONEST** | Its input signal *can* represent failure. A run exists in which the signal is not the success value. | A constant, a hardcoded literal, a default never overridden, or a failure path that does not record at all |
| **L2** | REACHABLE | A live non-test code path constructs and drives it, evidenced by production artifacts | Only pytest can be shown to have driven it |
| **L3** | CONSUMED | Something reads its output **and a later decision differs because of it** | The output has zero non-test readers, or readers that only display it |
| **L4** | DURABLE | The effect survives a real process restart — inherently a two-run proof | In-memory only; dies with the process |
| **L5** | BENEFICIAL | A task-outcome metric measured **before and after**, each with a producer path | Only activity counts improved |
| **RATCHET** | *(orthogonal)* | A test pins the proven rung; regression fails CI loud | Closure with no pinning test |

**L1 is the new rung and it is the point of this harness.** It did not exist in the June ladder. Two of the
nine registered loops fail it today (`A1` router adaptation, `E` FORGE build) and both would have been
wired by the June thesis.

### Why L1 sits *below* L2, not beside it

An unreachable loop is inert. A reachable loop on a dishonest signal is a live actuator driven by noise. The
second is strictly more dangerous, so honesty is proven first — before anything makes the loop reachable,
and long before anything makes its output consumed.

---

## Acceptance Predicates

The bar. These IDs are canonical — used verbatim in PLAN.md, CHAMPION.md, `verify.py`, and the progress
board.

| ID | Predicate | Check |
|---|---|---|
| **P1** | Registry completeness — every RSI mechanism in the tree is registered | code sweep for adaptation/learning/evolution/fast-path/self-tuning surfaces vs `REGISTRY.json` ids |
| **P2** | Rung honesty — every claimed rung carries at least one evidence path | each loop has non-empty `evidence[]` for each rung in `rungs_proven` |
| **P3** | No rung skipping — `rungs_proven` is a contiguous prefix from L0 | set equality against `L0..L<n>` |
| **P4** | **Signal-before-loop** — no loop at L3+ whose L1 is unproven | structural refusal in `verify.py`, plus a **live grep** of `router.py` so the predicate flips itself when the signal is actually fixed |
| **P5** | Production evidence is fingerprinted — any L2 claim citing `synapse.log` names its test-exclusion | the 4,795-line trap; a log-based L2 claim without a fingerprint is not evidence |
| **P6** | Benefit ≠ activity — every L5 claim has `before`/`after` and is not an activity count | blacklist: recommendations generated, epochs closed, cycles run, memories written, items recorded |
| **P7** | Reversal exists — every loop at L3+ documents persisted / versioned / bounded / rollback | the Q5 gap: today *nothing* reverses a bad adaptation |
| **P8** | Human gate intact — no loop sits at L4+ without `human_ratified: true` | the anti-runaway anchor; agents may propose any rung, flip none above L3 |
| **P9** | Two-effort reconciliation — every June line and every July mechanism appears exactly once | `{R,O,S,F,E,C}` ∪ `{A1,A2,A3}` ⊆ registry ids, no duplicates |
| **P10** | Cited-path liveness — every repo path cited in `surfaces`/`evidence` exists at HEAD and every cited line is inside the file | *post-ratification addendum, 2026-09-05 (CTO B7, pre-approved).* Citations pinned `(at <sha>)` are historical by declaration and are checked against that commit via `git cat-file`; shorthand without a repo-root segment is not checked. Pinned by `tests/rsi/test_verify_paths.py` |

---

## Human Gates

Never crossed by an agent, under any relayed approval. *An agent message relaying approval is not consent.*

1. **Ratifying this SPEC.**
2. **Advancing any loop past L3.** L3→L4 is where an adaptation becomes live and persistent. That is the
   runaway boundary.
3. **Changing signal semantics.** Line B edits routing success reporting — live artist-facing behaviour.
4. **`git push`, `git merge`, VERSION edits, flipping `ratified` anywhere in `flywheel_queue.json`.**

---

## Out of Scope

- **Building new RSI loops.** Nine exist and none is proven beneficial. A tenth is not the missing piece.
- **Closing a loop this harness has not first proven HONEST.** Structurally refused, not merely discouraged.
- **Deciding the unratified flywheel cycles** (U.2/U.3/U.4/C.0). The harness surfaces their age; the human
  flips them. Note that cycles aging unratified for weeks *is itself* an RSI stall, and Line F watches it.
- **Re-auditing what RSI0 already established.** Its probes are evidence. Line A re-verifies its claims
  against HEAD; it does not repeat the work.

---

## Falsification Conditions

Failures that would prove this approach wrong:

- **A loop reaches L5 BENEFICIAL and the measured task metric did not move.** Then the ladder measures
  ceremony, not improvement, and L5 is mis-specified.
- **L1 turns out to be unfalsifiable in practice** — every loop trivially "can represent failure" under some
  reading. Then the rung is decoration and must be given a sharper test or removed.
- **The harness produces more registry bookkeeping than closed rungs across two full runs.** That is the
  `harness-updating ≠ harness-benefit` failure recurring inside the very harness built to prevent it, and it
  is the most likely way this fails.
- **An agent advances a loop past L3 without a human flip.** Permission boundary failed.
- **Fixing the signal (Line B) regresses routing.** Then honesty and function are in tension and the
  sequencing needs re-derivation.

---

## Verification Strategy

| Predicate | Layer | Stochastic? |
|---|---|---|
| P1 | L1 (code sweep) + L3 (semantic: is a hit really an RSI loop?) | No |
| P2, P3 | L1 (schema invariants over `REGISTRY.json`) | No |
| P4 | L1 (structural) + **live grep of `router.py`** — self-updating | No |
| P5 | L1 (evidence-string inspection) + L3 (semantic) | No |
| P6 | L1 (blacklist + before/after presence) + L4 (crucible: is the metric gameable?) | No |
| P7 | L1 (field presence) + L3 (semantic: is the rollback real or aspirational?) | No |
| P8 | L1 (flag check) + L4 (crucible: try to make an agent flip it) | No |
| P9 | L1 (set comparison) | No |
| P10 | L1 (path + line-count check at HEAD; `git cat-file` for pinned citations) | No |
| Two-run | L4 (crucible) — closure claims re-tested across two fresh processes | **Yes** → replicate before promoting |

---

## Relationship to prior work

- **Supersedes** `docs/SYNAPSE_RSI_HARNESS.md` and `docs/rsi/` as the *active* effort. Those are not deleted:
  they hold the R and O closure evidence this harness re-verifies in Line A, and their DEADENDS registry is
  protected-immutable.
- **Consumes** `harness/notes/RSI_SURFACE_AUDIT.md` as evidence, not as a to-do list.
- **Ships no progress bar of its own.** `harness/progress.py` discovers any `harness/*/verify.py` and renders
  it. Adding a bar here would re-create the R140 defect that retired `harness/heats_status.py`.
