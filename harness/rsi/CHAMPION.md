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
| **F** | router fast-path promotion | **L1** | L2 | **HIGH** if only persistence is addressed |
| **E** | FORGE build counters | — | L1 | **HIGH** — would compound unvalidated fixes |
| **C** | Moneta convergence | — | L0 | MEDIUM — relocates every loop's substrate at once |

**Highest rung anywhere: `A3` at L2 REACHABLE.** It fires on every 10th memory write and ends in a log line.

`F` moved `—` → **L1 HONEST** on 2026-08-01 (`RL-2`, R18), then was **hardened in place** the same day by
`RL-2c` (R19) after the crucible attacked the fix itself. That is the first L1 this harness has *earned by
fixing code* rather than by re-deriving a claim — and the first rung to survive an attack on its own remedy.
It changes no closure number.

**What the crucible caught in R18.** The new `record_outcome()` gated on a bare `if success:`, so
`record_outcome(fp, "FAIL")` did not merely fail to veto — it **manufactured positive evidence**, because
every non-empty string is truthy. Reproduced at `eca11ef`: after reporting a *failure*, `outcome_counts()`
read `(1, 0)` and `_outcome_confirmed` read `True`. A signal that upgrades garbage into a success is worse
than the constant it replaced, because the constant was at least *visibly* a constant. `success` is now
checked by identity against `True`/`False`; anything else raises and records nothing. Second hole, also
fixed: `outcome_confirmed` could never go `False → True`, since promotion fires on the frequency-crossing
call — necessarily before any outcome exists.

**F's real blocker is dormancy, not a missing feed.** Say it the harder way, because the two words imply
different work — *unfed* implies wiring a producer, *dormant* implies deciding whether the loop should exist.
Nothing calls `record_outcome()`, **and** `filter_tools()` — the sole enclosing function of the sole non-test
`MOERouter.route()` call site — has **zero references in the entire repository**. The promotion path runs
zero times in production. That makes L2 a **wire-or-delete** question, the same one `A2` faces, and answering
it comes before any wiring. Two docs written independently of this harness already reached the same verdict
(`docs/RFC_agent_usd_ledger.md:307` — "the dead `panel/tool_filter.filter_tools` (no caller)";
`docs/SCIENCE_HARNESS_LEDGER.md:256` — "DORMANT").

**A third promotion door was found and deliberately NOT fixed here.**
`ConductorAdvisor._analyze_routing_promotions` (`shared/conductor_advisor.py:296-324`) recommends promotion
on frequency alone, with confidence *scaling* with frequency. It is filed under **`O`**, not `F`: that file is
already one of `O`'s surfaces and `O`'s own note calls it "the read side of this loop"; it writes no routing
table (it emits an INFO `Recommendation` a human acts on); and its `analyze()` input contract is
frequency-only by construction, so fixing it means widening **`O`'s** inputs. Ruling and evidence in
`REGISTRY.json` → loop `O` → `_third_door_note`. Lane F exposed `MOERouter.outcome_counts()` so `O` has a
source to consume when it gets there.

`R`, `O`, `S`, `F`, `E`, `C` show `—` rather than a number. That is not a demotion of the June work; it is
the honest consequence of the ladder collision recorded in `REGISTRY.json._ladder_collision_warning`. June's
L2 meant "survives a restart" — this ladder's L4. `RL-1` re-derives them.

---

## The three L1 failures

The rung this harness added, and the reason it added it. Three of nine loops cannot observe their own
failure:

- **`A1`** — eight call sites pass `(tier, latency_ms)` only; `success` takes its `True` default at
  `router.py:917`. Plus `router.py:537` hardcodes tier-0 success. Plus `router.py:367-373` never records
  failures at all. *(verified at HEAD)*
- **`F`** — ~~promotion is driven by fingerprint **frequency**, not outcome~~. **CONFIRMED at HEAD, then
  CLOSED by `RL-2` (R18).** The claim was true: `route()` took only `features`, no outcome parameter existed
  on `MOERouter`, and the promotion block gated on the frequency counter alone. `record_outcome()` now gives
  it an outcome channel and any recorded failure vetoes promotion — through `route()` *and* through the
  `learn_fast_path()` side door, which `RL-2` found carried the identical defect. **Hardened by `RL-2c`
  (R19)** after the crucible showed the remedy had its own hole: `record_outcome(fp, "FAIL")` was counted as
  a *success*. **F is at L1, blocked at L2:** nothing calls `record_outcome()` yet, so every entry written
  today is stamped `outcome_confirmed=False`. Honest, and **dormant** — not merely unfed.
- **`E`** — `fixes_validated` reportedly hardcoded `0`. *(carried; `RL-1` confirms)*

Every one of these would have been wired by the June thesis. That is the finding.

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
