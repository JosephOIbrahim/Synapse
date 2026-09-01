# BP2-METER — token meter measured (design note)

*Leg `BP2-METER`, branch `bp2/meter`. First leg of BP2 by design: every later
BP2 cap is set from this leg's first measured ledger. Docs anchor: docs/BATTLEPLAN.md
2026-09-01 sec.6 BP2-METER, sec.12 R-3/R-4.*

## What this leg makes true

The measurement machinery already existed and was never called: `rails.py`
`measure_transcript_tokens()` reads a Claude Code transcript's `message.usage`,
and `charge --transcript` was wired — but the only charge site (orchestrate.ps1's
pre-dispatch `Rails-Charge`) has no transcript yet, so every token field stayed
`UNKNOWN`. This leg adds the **post-close settle**: when a leg reaches `done` and
`-Budget` is set, the orchestrator resolves that leg's transcript and measures
what it actually spent, into the run ledger. Reuse-before-build (R-4): the
measurement, the ledger, and the cap arithmetic are all BP1-RAILS; this leg adds
the *call site* and the in-place settle semantics, plus per-leg tiers and a
bus-driven drift check.

## The two-phase charge model (why a settle is not a second turn)

A rails **turn = one leg DISPATCH** (not a conversational turn; sec.12 R-3). Two
rails operations touch one leg, one turn:

1. **pre-dispatch `charge`** (unchanged, BP1) — reserves the turn, enforces the
   turns floor, records the leg with tokens `UNKNOWN` (it has not run yet).
2. **post-close `settle`** (new, T1) — finds that same leg entry and fills the
   MEASURED tokens **in place**. It never adds a turn (`test_settle_measures_...`
   asserts `turns_spent == 1` after charge+settle), so turns are never
   double-counted.

`settle` then re-derives the run's token state from the whole leg list
(`_rederive_token_state`): `token_meter` is `"measured"` only when EVERY admitted
leg carries measured int tokens; a still-running (unsettled `UNKNOWN`) leg or a
settled-`UNKNOWN` leg keeps the run honest at `UNKNOWN` and enforcement on the
turns floor. This **heals** the pre-dispatch `UNKNOWN`: `UNKNOWN` means "not
currently known", not "known-bad", so measuring it later restores the meter
(`test_settle_heals_the_pre_dispatch_unknown`). A settle with no resolvable
transcript stays `UNKNOWN` — never zero, never an estimate (the negative control).

**The ceiling & the halt.** `enforced_unit` flips to `tokens` only when a ceiling
is set AND ≥1 leg was measured. A settle whose measured spend crosses the token
ceiling sets `status blocked / reason budget / blocked_on tokens` and returns exit
7; the leg already ran (its tokens are real spend) so it is never retroactively
refused — the halt stops the NEXT dispatch. The orchestrator's `Rails-Settle`
reads exit 7 and sets `$script:BudgetHalted`, and rails.py refuses further charges
on a blocked run, so the wave halts (never a silent continue).

## Status honesty (REFEREE bus finding, 2026-09-01, T4 class)

REFEREE flagged that the live orchestrator ledger read `status: "complete"` while
four legs were still running: `to_dict` mapped `open -> complete`. Fixed: a live
run reads **`open`**; `charge`/`settle` persist via `_persist()` (status
unchanged); only an explicit `close()` finalises `open -> complete`; `blocked`
unchanged. Vocabulary: **open** = live wave, **complete** = finalised close,
**blocked** = budget halt (`test_live_run_reads_open_not_complete`). Lands on this
branch; the running orchestrator (pid observed 2026-09-01) uses the main-tree
rails.py and is unaffected until a human merges.

## Tiers per leg (T2)

`rails_exec.json` gains a `referee` tier (`claude-fable-5`) — a LOOKUP only,
nothing else decides a model. `mission_schema.py` accepts an OPTIONAL `tier`,
`compile_wave.py` carries it onto the row only when present (tier-less rows stay
byte-identical), and `orchestrate.ps1` resolves `$leg.tier` via
`python harness/rails.py resolve <tier>` at dispatch, falling back to
`$manifest.model` (reasoning) if the alias cannot be honoured — the ADAPT the
preflight (runs/2026-09-01/preflight.json) anticipated.

## Drift check (T3)

`drift.py` (≤60 lines, pure Python, zero model calls) reads `bus/<wave>/bus.jsonl`
and, per leg, computes an on-target ratio over the last 5 `progress` messages
(fraction citing a `T<n>` / acceptance index). Below 0.6 → post a `refocus` from
`orchestrator` with the leg's mission targets VERBATIM; two refocus, still
drifting → `halt`. It never edits a mission or a manifest. orchestrate.ps1 runs it
once per poll, only when `-Budget` is set (additive).

## Additivity guarantee

Every orchestrate.ps1 change is gated behind `-Budget` (settle, drift) or a
`leg.tier` (model resolution). A `-DryRun` run **without** `-Budget` is
byte-identical to the pre-edit baseline — proven by `prove_bp2_meter_dryrun.ps1`
(empty diff, both sides run from inside `harness/` so `lib/quote-safe.ps1`
resolves and no CRLF/LF checkout artifact intrudes).

## Evidence

| Acceptance | Evidence |
|---|---|
| #1 measured ledger | `runs/2026-09-01/ledger_bp2-meter-settle.json` (12700/470/8482, named transcript) + this leg's own live session transcript measured in `bp2_meter_proof.json` |
| #2 negative control | `tests/test_rails.py::test_settle_no_transcript_is_unknown_enforced_turns` + `..._cli_settle_no_transcript_is_unknown` |
| #3 fixtures + enforced_unit | `tests/test_rails.py` fixtures + `test_enforced_unit_flips_to_tokens_only_when_ceiling_and_measured` |
| #4 tiny-ceiling halt | `runs/2026-09-01/ledger_bp2-meter-halt.json` (blocked/budget/tokens, exit 7) |
| #5 -DryRun byte-identical | `runs/2026-09-01/dryrun_bp2meter_diff.txt` (empty) via `prove_bp2_meter_dryrun.ps1` |
| #6 drift | `tests/test_drift.py` (6 cases) |
| #7 referee resolves | `python harness/rails.py resolve referee` -> `claude-fable-5`; `test_resolve_referee_prints_fable5` |
