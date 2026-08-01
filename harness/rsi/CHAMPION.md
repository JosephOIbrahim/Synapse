# CHAMPION — the RSI ratchet

*Current best proven rung per loop. A rung is recorded here **only** after evidence gathered at HEAD. Never
promoted on a carried claim, a memory note, or a prior harness's numbering.*

**Frame 2026-08-01 · commit `f427320` · SPEC AWAITING RATIFICATION**

---

## Read this before reading the numbers

`harness/rsi/verify.py` reports **9 PASS / 0 FAIL** at frame time. That means **the registry is honest about
the code** — not that anything is closed. The scoreboard below is the closure measure, and it reads:

> **0 of 9 loops beneficial. 0 of 9 loops even reach L3 CONSUMED. Nothing in this codebase has yet improved
> itself.**

Both statements are true at once, and conflating them is the failure this file exists to prevent.

---

## Scoreboard

| Loop | Name | Rung | Blocked at | Danger if closed now |
|---|---|---|---|---|
| **A1** | EpochAdapter router adaptation | **L0** | L1 | **CRITICAL** — one-way ratchet to the 0.10 floor in 8 epochs |
| **A2** | OutcomeTracker reward signal | **L0** | L1 *(operative: L2)* | LOW while inert |
| **A3** | memory evolution (charmander) | **L2** | L3 | MEDIUM — deepens a module marked for removal |
| **R** | render-farm learning | — | L0 | LOW — recording an unverified rung is itself the risk |
| **O** | §16 observability | — | L0 | LOW — same |
| **S** | science registry → substrate | — | L0 | UNKNOWN pending RL-1 |
| **F** | router fast-path promotion | — | L1 | **HIGH** if only persistence is addressed |
| **E** | FORGE build counters | **L1** | L2 | **HIGH** — would compound unvalidated fixes |
| **C** | Moneta convergence | — | L0 | MEDIUM — relocates every loop's substrate at once |

**Highest rung anywhere: `A3` at L2 REACHABLE.** It fires on every 10th memory write and ends in a log line.

`R`, `O`, `S`, `F`, `C` show `—` rather than a number. That is not a demotion of the June work; it is
the honest consequence of the ladder collision recorded in `REGISTRY.json._ladder_collision_warning`. June's
L2 meant "survives a restart" — this ladder's L4. `RL-1` re-derives them.

---

## The three L1 failures — one now closed

The rung this harness added, and the reason it added it. Three of nine loops could not observe their own
failure. `E` was fixed on 2026-08-01 (`RL-2 SIGNAL`); `A1` and `F` remain open:

- **`A1`** — eight call sites pass `(tier, latency_ms)` only; `success` takes its `True` default at
  `router.py:917`. Plus `router.py:537` hardcodes tier-0 success. Plus `router.py:367-373` never records
  failures at all. *(verified at HEAD)*
- **`F`** — promotion is driven by fingerprint **frequency**, not outcome. A fingerprint that fails every
  time is promoted identically to one that always succeeds. *(carried; `RL-1` confirms)*
- **`E`** — ~~`fixes_validated` hardcoded `0`, `fixes_applied` incremented on classification~~ **CLOSED
  2026-08-01 (`RL-2`).** The first question decided the shape: **no verification phase exists** in
  `forge/engine` — `FORGE.md` Phase 5 is a human/Claude-Code procedure, not a module — so the `:214` comment
  that promised one ("Set after verification phase") was itself a phantom. Took the honest-reporting branch:
  `fixes_validated` is `None` = *unvalidated* unless a real re-run produced a number, the reporter prints the
  word rather than a numeral, and `fixes_applied` counts only confirmed applications. A missing measurement
  stated plainly beats an invented one. **Now blocked at L2** — nothing live constructs the orchestrator.

Every one of these would have been wired by the June thesis. That is the finding.

> **`E`'s closure is not `E`'s benefit.** The loop now reports honestly that it is not improving anything.
> That is a real rung and a real gain in trustworthiness, and it is *not* self-improvement. `E` reaches L2+
> only when an actual apply → re-run stage exists to feed `FixOutcome` evidence.

---

## Promotion rules

1. A rung is promoted **only** with evidence gathered at HEAD, recorded in `REGISTRY.json.evidence[rung]`.
2. Rungs are a contiguous prefix. No cherry-picking a high rung over an unproven low one (`P3`).
3. **No loop is promoted past L3 by an agent.** `human_ratified` is a human flip (`P8`).
4. A promotion to **L4 DURABLE** requires a genuine two-run proof across two fresh processes. One run is not
   a restart proof.
5. A promotion to **L5 BENEFICIAL** requires a before/after task metric with a producer path, and must
   survive the `P6` activity blacklist.
6. **Demotion is normal and carries no stigma.** If evidence stops supporting a rung, drop it and log it.
   A champion board that only goes up is a champion board that is lying.
