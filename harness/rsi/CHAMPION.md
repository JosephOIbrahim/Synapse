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
| **A1** | EpochAdapter router adaptation | **L1** | L2 | LOW at L1 — nothing consumes the adapter; CRITICAL still applies at L3 |
| **A2** | OutcomeTracker reward signal | **L0** | L1 *(operative: L2)* | LOW while inert |
| **A3** | memory evolution (charmander) | **L2** | L3 | MEDIUM — deepens a module marked for removal |
| **R** | render-farm learning | — | L0 | LOW — recording an unverified rung is itself the risk |
| **O** | §16 observability | — | L0 | LOW — same |
| **S** | science registry → substrate | — | L0 | UNKNOWN pending RL-1 |
| **F** | router fast-path promotion | — | L1 | **HIGH** if only persistence is addressed |
| **E** | FORGE build counters | — | L1 | **HIGH** — would compound unvalidated fixes |
| **C** | Moneta convergence | — | L0 | MEDIUM — relocates every loop's substrate at once |

**Highest rung anywhere: `A3` at L2 REACHABLE.** It fires on every 10th memory write and ends in a log line.
`A1` reached **L1 HONEST** on 2026-08-01 (`RL-2`) — its signal can now represent failure. That is one rung,
not a closure: nothing consumes it and no production traffic has exercised it.

`R`, `O`, `S`, `F`, `E`, `C` show `—` rather than a number. That is not a demotion of the June work; it is
the honest consequence of the ladder collision recorded in `REGISTRY.json._ladder_collision_warning`. June's
L2 meant "survives a restart" — this ladder's L4. `RL-1` re-derives them.

---

## The three L1 failures — one closed, two open

The rung this harness added, and the reason it added it. Three of nine loops could not observe their own
failure. `A1` now can:

- **`A1`** — ~~eight call sites pass `(tier, latency_ms)` only~~ **CLOSED `RL-2` 2026-08-01.** `success` is
  now a REQUIRED parameter (`router.py:937-962`), all nine call sites pass a real outcome, `_try_tier0`
  computes success from its responses (`router.py:557`) instead of hardcoding it, and the no-tier-matched
  fallback records a failure under `NO_TIER_KEY` (`router.py:386`) where it previously recorded nothing.
  `_try_tier2` carried the identical hardcode and was fixed in the same commit. Pinned by
  `tests/test_routing.py::TestRewardSignalHonesty` (10 tests, mutation-verified against three mutants).
  *(verified at HEAD; `verify.py` P4 reads 9/9 call sites)*
- **`F`** — promotion is driven by fingerprint **frequency**, not outcome. A fingerprint that fails every
  time is promoted identically to one that always succeeds. *(carried; `RL-1` confirms)*
- **`E`** — `fixes_validated` reportedly hardcoded `0`. *(carried; `RL-1` confirms)*

Every one of these would have been wired by the June thesis. That is the finding.

**What `A1` L1 does NOT mean.** The signal is honest; it is not *read*. The router has recorded zero
production requests — `synapse_live_metrics` on a live bridge returned `total_requests=0`, `tier_counts=[]`
on 2026-08-01. `A1` is blocked at **L2 REACHABLE** for want of traffic, not for want of code. Closure did
not move the scoreboard line below: still 0 of 9 beneficial, still 0 of 9 at L3.

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
