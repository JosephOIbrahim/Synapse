# CHAMPION — the RSI ratchet

*Current best proven rung per loop. A rung is recorded here **only** after evidence gathered at HEAD. Never
promoted on a carried claim, a memory note, or a prior harness's numbering.*

**Framed 2026-08-01 at `f427320` · SPEC RATIFIED 2026-08-01 · last updated by the `F` retirement (2026-08-01)**

---

## Read this before reading the numbers

`harness/rsi/verify.py` reports **9 PASS / 0 FAIL** at frame time. That means **the registry is honest about
the code** — not that anything is closed. The scoreboard below is the closure measure, and it reads:

> **0 of 9 loops beneficial. 0 of 9 loops even reach L3 CONSUMED. Nothing in this codebase has yet improved
> itself.**

Both statements are true at once, and conflating them is the failure this file exists to prevent.

**The registry still holds 9 entries; not all 9 are still live loops.** `F` was **retired** on 2026-08-01 —
its mechanism is deleted from the tree, and its entry is kept because `P9` requires all nine ids present and
because a retirement that erases its own evidence cannot be audited or reversed. A retired loop sits at **no
rung** and counts toward neither the numerator nor the denominator of "beneficial". Read `RETIRED` in the
scoreboard as *gone*, not as *stuck at zero*.

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
| **F** | ~~router fast-path promotion~~ | **RETIRED-2026-08-01** | — | N/A — the mechanism is deleted from the tree |
| **E** | FORGE build counters | **L1** | L2 | **HIGH** — would compound unvalidated fixes |
| **C** | Moneta convergence | — | L0 | MEDIUM — relocates every loop's substrate at once |

**Highest rung anywhere: `A3` at L2 REACHABLE.** It fires on every 10th memory write and ends in a log line.
`A1` reached **L1 HONEST** on 2026-08-01 (`RL-2`) — its signal can now represent failure. That is one rung,
not a closure: nothing consumes it and no production traffic has exercised it.

### `F` — RETIRED 2026-08-01. The harness's first genuine subtraction.

`F` moved `—` → **L1 HONEST** on 2026-08-01 (`RL-2`, R18), was **hardened in place** the same day by `RL-2c`
(R19) after the crucible attacked the fix itself — and was **deleted from the tree later the same day.** All
three events belong in the record together, because the middle one is what made the last one answerable.

**What went.** `_session_fast_paths` and the whole auto-promotion path in `shared/router.py` (the frequency
gate, the `CONSTANTS_HASH` stamp, the session-fast-path tier, `learn_fast_path()`, `record_outcome()`,
`outcome_counts()`, `_promotion_allowed()`, `_outcome_confirmed()`), the second writer
`RoutingLog.apply_learned_fast_paths()`, and the dead entry point `panel/tool_filter.py::filter_tools()` with
its private support. 37 honest, passing tests went with the mechanism they pinned.

**Why: dormant, not unfed.** Say it the harder way, because the two words imply different work — *unfed*
implies wiring a producer, *dormant* implies deciding whether the loop should exist. Nothing called
`record_outcome()`, **and** `filter_tools()` — the sole enclosing function of the sole non-test
`MOERouter.route()` call site — had **zero references in the entire repository**. No producer of outcomes and
no consumer of decisions: the promotion path ran zero times in production, so wiring it would have meant
inventing a customer for the mechanism rather than serving one. Two docs written independently of this
harness had already reached the same verdict (`docs/RFC_agent_usd_ledger.md:307` — "the dead
`panel/tool_filter.filter_tools` (no caller)"; `docs/SCIENCE_HARNESS_LEDGER.md:256` — "DORMANT").

**Deleting the same day's work is the point, not an embarrassment.** R18/R19 shipped hours earlier and were
good work. What the crucible caught in R18 — `record_outcome(fp, "FAIL")` incrementing the **success** tally,
because the gate was a bare `if success:` and every non-empty string is truthy — is exactly the kind of
defect that hides behind an unfed mechanism. A frequency counter with no failure channel can always be
excused as "not wired up yet." An honest channel with no producer is a mechanism nobody wants. **Making the
signal honest is what proved the loop was dormant rather than merely unfed**, and the retire-or-keep question
was only answerable because that work was done first. A ratchet that can only add is not a ratchet.

**The cut was narrow on purpose.** `MOERouter` itself is NOT dead — it is the panel-side classifier
(`agent_health.py:41`) — and `fingerprint_counts()` survives because `conductor_advisor.py:480` reads it live
to *recommend* a hand-tuned `FAST_PATHS` entry to a human. Counting is advice; promoting was
self-modification. Full deleted/kept ledger with the live caller that saved each survivor:
`REGISTRY.json` → loop `F` → `blocker`. Reintroduction fails loudly at
`tests/test_router_internals.py::TestPromotionRetired`.

**A third promotion door was found and deliberately NOT fixed here.**
`ConductorAdvisor._analyze_routing_promotions` (`shared/conductor_advisor.py:296-324`) recommends promotion
on frequency alone, with confidence *scaling* with frequency. It is filed under **`O`**, not `F`: that file is
already one of `O`'s surfaces and `O`'s own note calls it "the read side of this loop"; it writes no routing
table (it emits an INFO `Recommendation` a human acts on); and its `analyze()` input contract is
frequency-only by construction, so fixing it means widening **`O`'s** inputs. Ruling and evidence in
`REGISTRY.json` → loop `O` → `_third_door_note`. Lane F exposed `MOERouter.outcome_counts()` so `O` has a
source to consume when it gets there.

`R`, `O`, `S`, `C` show `—` rather than a number. That is not a demotion of the June work; it is
the honest consequence of the ladder collision recorded in `REGISTRY.json._ladder_collision_warning`. June's
L2 meant "survives a restart" — this ladder's L4. `RL-1` re-derives them.

---

## The three L1 failures — two closed, one landing

The rung this harness added, and the reason it added it. Three of nine loops could not observe their own
failure. `A1` and `E` now can (both `RL-2` 2026-08-01, both corrected the same day by `RL-2b`/`RL-2c`);
each was corrected the same day after its crucible attacked the remedy itself:

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
- **`F`** — ~~promotion is driven by fingerprint **frequency**, not outcome~~. **CONFIRMED at HEAD, CLOSED by
  `RL-2` (R18), hardened by `RL-2c` (R19) — then RETIRED the same day.** The claim was true and the fix was
  real: `record_outcome()` gave promotion an outcome channel, any recorded failure vetoed it, and the
  `learn_fast_path()` side door carried the identical defect and was closed too. Then the honest signal
  revealed there was no producer *and* no consumer, and the mechanism was deleted rather than fed. **This
  L1 is withdrawn — not because it was wrong, but because the code it described no longer exists.** See the
  `F` section above; the ladder does not apply to a retired loop.
- **`E`** — ~~`fixes_validated` hardcoded `0`, `fixes_applied` incremented on classification~~ **CLOSED
  2026-08-01 (`RL-2`).** The first question decided the shape: **no verification phase exists** in
  `forge/engine` — `FORGE.md` Phase 5 is a human/Claude-Code procedure, not a module — so the `:214` comment
  that promised one ("Set after verification phase") was itself a phantom. Took the honest-reporting branch:
  `fixes_validated` is `None` = *unvalidated* unless a real re-run produced a number, the reporter prints the
  word rather than a numeral, and `fixes_applied` counts only confirmed applications. A missing measurement
  stated plainly beats an invented one. **Now blocked at L2** — nothing live constructs the orchestrator.
  *(Corrected the same day — see the surviving-mutant note below.)*

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

> **`E`'s closure is not `E`'s benefit.** The loop now reports honestly that it is not improving anything.
> That is a real rung and a real gain in trustworthiness, and it is *not* self-improvement. `E` reaches L2+
> only when an actual apply → re-run stage exists to feed `FixOutcome` evidence.

### `E` — the surviving mutant at its own defect site

The first `RL-2` pass shipped 15 tests and a mutation claim. The crucible flipped
`metrics.py:44` back to `fixes_validated: int | None = 0` and **all fifteen still passed.**

The gap was one layer deep. The tests exercised the `CycleMetrics` dataclass default
(`schemas.py`) and `ForgeOrchestrator.process_results` above it — but never
`MetricsTracker.compute_cycle_metrics`, the single function *between* them where every
cycle's metrics are actually built. A fabricated `0` there re-fabricates a whole-cycle
measurement for any caller that omits the argument, invisibly to both layers that were
tested.

Four tests now kill it — one behavioural (`compute_cycle_metrics` with no validation
argument must yield the sentinel), one following it through to disk and to the rendered
box, one `inspect.signature` pin, one source pin. Proven in both directions: default → `0`
gives **4 red**, default → `None` gives **26 green**.

**The transferable rule:** a mutation claim is only worth what it was actually run against.
"Re-introducing the fabrication fails 4 tests" was true of the fabrication the author
happened to think of, at the layer the author happened to test. The defect site itself was
never called. Mutate the *line you changed*, not the behaviour you remember changing.

Two more crucible findings closed with it: the three legacy `fixes_validated: 0` rows in
`forge/metrics/cycles.json` (which made the repo's own `total_fixes_validated` report a
**measured** 0 for a project with no validator — now `null`, aggregate now `None`), and
per-cycle all-or-nothing validation (one outcome carrying a verdict used to flip the whole
cycle into reading as measured — `fixes_revalidated` now records the denominator and the
report prints a `! PARTIAL: N of M` row).

One deferred, deliberately: `process_results` still cross-checks nothing a caller asserts.
There is nothing in `forge/engine` to cross-check *against* — no apply stage, no re-run
stage, no execution surface — so any check it performed would be a self-assertion in a
different costume. The engine no longer manufactures counts on its own authority; that is
the whole of what this rung claims. The rest needs the real verifier that also blocks L2.

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
7. **Retirement is a legitimate outcome, and it outranks wiring.** A loop whose mechanism executes zero times
   in production is answering a *wire-or-delete* question, not a *wire* question. Delete is the right answer
   when there is no producer **and** no consumer — wiring one then means inventing a customer for the
   mechanism rather than serving one. A retired loop keeps its registry entry (`disposition: RETIRED-<date>`,
   `rungs_proven: []`, `blocked_at: L0`) with the evidence that established dormancy and a plain statement of
   what would have to be true to revive it. **Deleting your own recent work is not waste** — making a signal
   honest is often precisely what proves the loop should not exist, and that finding is the return on it.
