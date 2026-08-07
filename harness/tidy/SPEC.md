# TIDY — Unfinished-Work Closure + Housecleaning Harness

> The loop-closing harness. Every unfinished item in the working tree, every
> stale state file, every open gate — gets a disposition, an owner, and a
> path to closed. Nothing gets "no decision."

## What TIDY is

SYNAPSE's recurring failure mode is work that starts and never closes: probe
scripts left in `harness/notes/`, draft release notes superseded by finals,
state files that say `ready` after the work merged, a `$null` file where a
PowerShell error landed, data directories that should be gitignored. TIDY
inventories all of it, classifies each item, executes the safe dispositions,
prepares the gated ones, verifies nothing broke, and reports to the human
with a decision list.

TIDY is a **conductor**, not a sixth parallel harness. It routes unfinished
work to the existing harnesses' protocols (CLEAR, PHANTOM SWEEP, RSI, ROPE)
and to direct dispositions. It does not re-implement them.

## The loop

```
SWEEP → CLASSIFY → DISPATCH → VERIFY → REPORT
```

1. **SWEEP** — inventory the working tree, recent commits, harness state,
   open gates, CI health. (Fan-out recon agents.)
2. **CLASSIFY** — every item gets exactly one disposition. (Orchestrator agent.)
3. **DISPATCH** — execute safe dispositions, prepare gated ones. (Fan-out
   dispatch agents.)
4. **VERIFY** — confirm the loop closed: tree delta, state consistency,
   test baseline. (Verify agents.)
5. **REPORT** — human-readable report: what was done, what's gated, what
   needs the human. (Orchestrator agent.)

## Dispositions

| Disposition | Meaning | Executed by harness? | Gate |
|---|---|---|---|
| COMMIT | Real work, ship it | Prepares staged commit + message | Human approves commit |
| DROP | Garbage / artifact | Proposes deletion with rationale | Human approves delete |
| PARK | Draft/scratch worth keeping | Moves to `harness/notes/scratch/` | None (reversible) |
| MOVE | Right content, wrong place | Moves to correct location | None (reversible) |
| FIX | Broken / stale state | Diagnoses + proposes fix | Human applies |
| DEFER | Needs a decision not yet made | Records in report + state | None (surfaced) |

## Safety model

- **Never auto-commit, never auto-push, never auto-merge.** (Repo law.)
- **Never auto-delete real work.** Drops are proposals with rationale.
- **Never mutate another harness's state files** (`legs.json`, `STATE.json`,
  `flywheel_queue.json`, `drop.json`, `posture.json`). Diagnose and propose;
  recover via the producer path.
- **Safe actions execute:** file moves (reversible), file creation (harness
  files, reports), git staging (reversible), test runs (read-only).
- **Idempotent:** `STATE.json` records what's been done; re-runs skip
  completed items.

## Agent teams

- **RECON** (~11): git-status, recent-commits, harness-state, notes-probes,
  release-notes, docs-untracked, data-dirs, autoresearch, open-gates,
  ci-health, stray-files
- **CLASSIFY** (1 orchestrator): synthesizes the disposition table
- **DISPATCH** (~8): prepare-commits, propose-drops, park-scratch,
  move-items, diagnose-fixes, state-reconcile, data-dirs, open-gates
- **VERIFY** (3): tree-delta, state-consistency, test-baseline
- **REPORT** (1 orchestrator): final report + STATE.json update

## How to run

- **Mode 1 (cheap daily sweep):** `python harness/tidy/runner.py` — heuristic
  classification, no subagents.
- **Mode 2 (deep review):** the workflow script `harness/tidy/workflow.js` —
  the full agent team (24 agents).

## Acceptance criteria

1. Every unfinished-work item gets exactly one disposition (no orphans).
2. Safe dispositions execute; gated ones are prepared and surfaced.
3. No destructive action executes without a human gate.
4. The report enumerates every open human gate with its exact ask.
5. The harness is re-runnable (STATE.json idempotency).
6. The working tree after a run is clean or intentionally dirty with
   documented reasons.
