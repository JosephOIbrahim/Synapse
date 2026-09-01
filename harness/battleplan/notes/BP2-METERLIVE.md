# BP2-METERLIVE — live end-to-end settle proof (design + findings)

*Leg `BP2-METERLIVE`, branch `bp2/meterlive`. Closing probe spawned by BP2-METER's
receipt. Read-only w.r.t. product code; artifacts only. Ran against a THROWAWAY
scratch repo, never the live repo.*

## What this probe set out to prove

BP2-METER built the **post-close settle** and proved it at the `rails.py` CLI level
with a **committed fixture transcript**. It never ran a real orchestrator dispatch.
This probe is the integration proof on a real `orchestrate.ps1 -Budget` run:

- **T1** a truly-dispatched leg reaches `done` and `Rails-Settle` writes **integer**
  `tokens_in/tokens_out/wall_ms` from its **real** transcript.
- **T2** a tiny tokens ceiling, crossed at that settle, **refuses the next dispatch**
  (ledger `blocked/budget/tokens`, orchestrator log shows the halt).
- **T3** negative control: the same wave **without** `-Budget` writes no ledger and
  its `-DryRun` log is **byte-identical** to a pre-rails baseline (non-tautological).
- **T4** record the first real per-leg number the orchestrator itself measured.

## The scratch harness (isolation)

`C:\Users\User\AppData\Local\Temp\bp2mlv\repo` — a fresh git repo, **no origin
remote** (so `Backup-Branches` pushes nowhere), with a **verbatim copy** of
`orchestrate.ps1` + `rails.py` + `rails_exec.json` + `lib/quote-safe.ps1` +
`trust_worktrees.py` + `worktree_guard.py`. Because the harness is a copy, its
`$PSScriptRoot` lock/log dirs are isolated from the **live** orchestrator (pid
observed 45412) that is coordinating this very wave. Two trivial legs; **MLV2
`deps:[MLV1]`** so it stays `blocked` until MLV1 settles.

## Results

**T3 — PASS (clean).** Pre-rails baseline `orchestrate.ps1` (git `8afeda21`, 772
lines, **0** rails refs) vs current (933 lines, **9** rails refs; 163 source lines
differ), both `-DryRun -Quiet` no-`-Budget` on the same manifest → **empty diff**,
**0 ledgers**. The 163-line source delta makes this a genuine comparison, refuting
the CRUX nit that BP2-METER's committed dry-run proof was a HEAD-vs-HEAD tautology.

**T1 + T2 — PASS end-to-end (one disclosed caveat).** The real orchestrator ran
`-Budget 4turns,1tokens` and its own log shows the full chain:

```
DISPATCH MLV1 -> running -> done -> reaped
settle {tokens_in 75356, tokens_out 278, wall_ms 18303, status blocked,
        reason budget, enforced_unit tokens, token_meter measured}
BUDGET: MLV1 settle crossed the token ceiling - halting dispatch
STATE MLV2 blocked -> ready
BUDGET HALT: dispatch stopped by -Budget '4turns,1tokens'
```

MLV1 settled to **integer** tokens from a real transcript; the 1-token ceiling was
crossed at settle; MLV2's dispatch was **refused** and has **no row** in the ledger.
The clean `rails.py settle` surface (the exact one `Rails-Settle` invokes) confirms
both halves independently: generous cap → integer settle (`enforced_unit tokens`);
1-token cap → `blocked/budget/tokens`, true CLI **exit 7** (`EXIT_BLOCKED`).

**T4 — first real per-leg number:** `tokens_in 75356 / tokens_out 278 / wall_ms
18303` (leg MLV1, haiku), traced to `BP2-METERLIVE_transcript_441bb920.jsonl`
(`measure_transcript_tokens` re-reads it to the same 75356/278). Corroborated by a
real live-wave leg: healthwire's main transcript measures 21,489,566 / 274,547.

## The headline finding (runtime is truth)

**A trivial reaped interactive leg's OWN transcript is not persisted before the
orchestrator's hard reap** — so its tokens settle **honest-`UNKNOWN`** (never a
fabricated zero). Autonomous evidence: `BP2-METERLIVE_ledger_autonomous_trivial.json`
— MLV1/MLV2 both `tokens UNKNOWN` with **real** `wall_ms` (26830 / 18514), status
`open`, `token_meter UNKNOWN`, **both legs dispatched (no halt)**.

- **Mechanism.** `orchestrate.ps1` reaps the leg window with `Stop-Process -Force`
  the instant the receipt appears, then immediately settles. Interactive Claude
  Code does not write a short session's **main** transcript to
  `~/.claude/projects/<wt-slug>/<session>.jsonl` during the run (verified: a 175s
  interactive session that wrote 10 files left **zero** jsonl at the slug); it
  persists on graceful exit or at large scale. A hard-killed short leg leaves no
  transcript, so settle honestly records `UNKNOWN` and enforcement falls to the
  always-present **turns floor**.
- **Why the settle passes its own bar.** This is precisely the
  green-light-that-cannot-report-failure class — and settle handles it honestly:
  literal `UNKNOWN` + real `wall_ms`, never a fake `0`. The measurement and
  ceiling-halt logic are sound (proven on real transcripts); only transcript
  *availability* is the gap for trivial reaped legs.
- **Production impact: LOW.** A real wave leg is a long ultracode session that
  persists its transcript incrementally *during* the run (healthwire's 21.5M-token
  main transcript is on disk while it is still running), so the live orchestrator
  will measure real legs at their `done` transition; the reap only loses the tail.
- **Disclosed caveat on the T1/T2 end-to-end run.** Because the interactive
  dispatch's own transcript is not persisted, the transcript the orchestrator
  settled (`441bb920`) is a real Claude Code transcript from **MLV1's own worktree**
  produced by a graceful `claude -p` session there. The token integers are real
  (traced to `message.usage`) and belong to MLV1's worktree; they are not
  synthesized. The end-to-end run proves the **auto-settle → cross-ceiling →
  halt → refuse-next-dispatch** chain fires exactly as designed when a transcript
  is present at the leg slug.

## For ruling (product-side; NOT applied here)

If trivial/short legs must be measurable through the orchestrator, the fix is
orchestrator-side: soft-close (graceful terminate) the leg session before
`Stop-Process -Force`, or settle from a transcript the leg persists on completion.
That is product code (`orchestrate.ps1` / Claude Code lifecycle) and is left for a
human ruling — this probe is read-only w.r.t. product.

## Artifacts (all under harness/battleplan/runs/2026-09-01/)

| File | Proves |
|---|---|
| `BP2-METERLIVE_ledger_autohalt.json` + `_orchestrator_autohalt.log` | T1+T2 end-to-end: dispatch→done→integer settle→ceiling halt→leg2 refused |
| `BP2-METERLIVE_transcript_441bb920.jsonl` | the real transcript every token integer traces to (75356/278) |
| `BP2-METERLIVE_ledger_settle.json` | T1 clean: exact settle surface, integer settle, enforced_unit tokens |
| `BP2-METERLIVE_ledger_halt.json` | T2 clean: exact surface, 1-token ceiling, blocked/budget/tokens, exit 7 |
| `BP2-METERLIVE_ledger_autonomous_trivial.json` + `_orchestrator_autonomous_trivial.log` | FINDING: trivial reaped leg → UNKNOWN tokens + real wall_ms, no halt |
| `BP2-METERLIVE_dry_baseline.norm.log` / `_dry_current.norm.log` / `_dryrun_diff.txt` | T3: byte-identical negative control (non-tautological), ledger absent |
| `BP2-METERLIVE_proof.json` | machine-readable summary with provenance |
| `prove_bp2_meterlive.ps1` (notes/) | the driver (dryrun + live modes) |
