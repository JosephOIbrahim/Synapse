# SPEC — the CTO review loop (`harness/cto/`)

*STATUS: DRAFT 2026-09-05 (scaffolded by Fable 5.1 as acting CTO; ratification = Joe's word).*

## Why this exists

Every prior SYNAPSE self-improvement mechanism built the **record** half (audit, ledger,
receipt) and left the **apply → closure** half dormant (`harness/rsi/SPEC.md`,
`harness/notes/RSI_SURFACE_AUDIT.md`: "nothing in this codebase has ever improved itself").
This loop is built around the closure half first. A finding is not a finding until it
carries a *closure predicate* the next run can execute without a human.

## The loop (one run = one turn of the crank)

```
SWEEP     run every open BACKLOG predicate -> closed / still-open / regressed
FIND      seven lanes, read-only: SCOUT DESIGN REVIEW HEALTH INTENT RECIPES RSI
VERIFY    one adversarial refuter per lane re-runs every repro; REFUTED dies here
SYNTH     CTO merge: dedupe, rank, gate, closure predicate per item
APPLY     gate=auto items only, forge in a worktree, one commit each, never merges
PERSIST   runs/<date>/report.json + BACKLOG.json + LEDGER.md line
```

`FIND` is exactly the current script in `.claude/workflows/cto-review.js`. Lanes are
prompts, not agents; adding a lane is one array entry.

## Five RSI components and where each lives

| Component | Where | Cannot be faked because |
|---|---|---|
| Signal | lane findings, each with `evidence` path:line + `repro` command | the refuter re-runs `repro`; no repro, no finding |
| Producer | the seven `FIND` lanes | read-only agents, evidence-anchored |
| Referee | `VERIFY` crucible per lane + `SYNTH` | default verdict is REFUTED |
| Apply | `APPLY` phase, `gate=auto` only | worktree + commit, never a merge |
| Closure | `SWEEP` runs `closure_predicate` of every open item | predicate is a shell command; exit 0 = closed |

## Gates (the honesty ladder)

- `auto` — reversible, test-covered, no product policy: gitignore, prune merged worktrees,
  doc drift with receipts. The loop may land these itself (still in a worktree, never master).
- `crux` — code fixes. Landed by a forge, attacked by a crucible, merge is Joe's word.
- `joe` — merges to master, consent/undo/RBAC, panel visual design decisions, rulings.

The loop never flips a gate. `STATE.json.autonomy` (`green|amber|red`) caps what APPLY
may touch per run; `red` = SWEEP+FIND+VERIFY+SYNTH only.

## Files

- `STATE.json` — run counter, autonomy, spawn cap, last run id.
- `BACKLOG.json` — open items (`{id,title,lane,severity,action,evidence,repro,gate,closure_predicate,opened_run,status}`).
- `LEDGER.md` — one line per run: date, run id, lanes, confirmed/refuted, closed-by-sweep, opened.
- `runs/<date>/report.json` — full synthesis + raw lane output for that run.

## Closure predicates — the contract

A predicate is a POSIX shell one-liner run from repo root with a 60 s timeout.
Exit 0 means closed. Anything else means open. A predicate that cannot be executed
(missing tool) is `UNKNOWN` and counts as open. Predicates never mutate.

## What this loop refuses

- To count a REFUTED finding anywhere but the refuted tally.
- To mark an item closed on a receipt, a STATUS.md line, or a commit message. Only the predicate.
- To merge, push, tag, or edit `VERSION`.
- To run the full 7k-test suite inside a lane (targeted files only; the ratchet owns the suite).
