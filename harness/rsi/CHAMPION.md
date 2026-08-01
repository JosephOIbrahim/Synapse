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
| **A1** | EpochAdapter router adaptation | **L1** | L2 | LOW at L1 — nothing consumes the adapter; **FAST is still structurally 1.0** (documented, not fixed); CRITICAL still applies at L3 |
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

- **`A1`** — ~~eight call sites pass `(tier, latency_ms)` only~~ **CLOSED `RL-2` 2026-08-01, CORRECTED
  `RL-2b` the same day.** `success` is now a REQUIRED parameter (`router.py:1019`), all **ten** call sites
  pass a real outcome, `_try_tier0` computes success from its responses instead of hardcoding it, and the
  no-tier-matched fallback records a failure under `NO_TIER_KEY` (`router.py:390`) where it previously
  recorded nothing. `_try_tier2` carried the identical hardcode and was fixed in the same commit.

  **What `RL-2` got wrong, and `RL-2b` fixed.** Passing `result.success` at every call site is not honesty
  if the `RoutingResult`'s own success is a literal. `_try_tier3` built `success=True` and recorded it **at
  launch**, before the background worker had any outcome — so an async DEEP route scored 1.0 no matter how
  it ended, and the worker's real verdict never entered the sample. `_try_tier3` now records nothing at
  launch; `_tier3_worker` (`router.py:808-864`) records what it observes.

  Pinned by `tests/test_routing.py::TestRewardSignalHonesty` (10 tests) and
  `::TestAsyncDeepSignalHonesty` (5 tests), mutation-verified against five mutants across the two passes.
  *(verified at HEAD; `verify.py` P4 reads 10/10 call sites)*

  **Scope it honestly:** `INSTANT`, `STANDARD`, `RECIPE`, `DEEP`, `CACHE` and `no_tier` can carry failure.
  **`FAST` cannot** — `_try_tier1` executes nothing and only reaches `_record_metric` on its success path;
  its low-confidence exit is a cascade decision, not a tier failure. `FAST`'s 1.0 is definitional, not
  evidence. Documented in code and registry, deliberately not "fixed".
- **`F`** — promotion is driven by fingerprint **frequency**, not outcome. A fingerprint that fails every
  time is promoted identically to one that always succeeds. *(carried; `RL-1` confirms)*
- **`E`** — `fixes_validated` reportedly hardcoded `0`. *(carried; `RL-1` confirms)*

Every one of these would have been wired by the June thesis. That is the finding.

**What `A1` L1 does NOT mean.** The signal is honest; it is not *read*. `A1` is blocked at **L2 REACHABLE**
for **two** reasons — and `RL-2` named only the second, while explicitly ruling out the first:

1. **The production router has no command channel.** `python/synapse/server/handlers.py:1625` builds
   `TieredRouter(config=config)` — the only non-test construction in the tree — and `command_fn` defaults
   to `None`. Tier 0 and tier 2 both gate execution on `self._command_fn`, so in production they *cannot
   execute a command at all*, `responses` is permanently empty, and the corrected
   `all(r.success for r in responses)` is permanently `all([])`. The honest tier-0/tier-2 signal is
   **unreachable from the live path**, not merely un-exercised.
2. **Zero production requests.** `synapse_live_metrics` on a live bridge returned `total_requests=0`,
   `tier_counts=[]` on 2026-08-01.

`RL-2`'s blocker read *"L2 needs live routed traffic through TieredRouter — not another code change."*
**That was false and is retracted.** Traffic alone would not exercise the corrected paths: a router with no
command channel cannot execute a command, so it can never observe one fail. L2 needs the wiring *and* the
traffic — and wiring the command channel is a signal-semantics change behind the human gate.

Closure did not move the scoreboard line below: still 0 of 9 beneficial, still 0 of 9 at L3.

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
