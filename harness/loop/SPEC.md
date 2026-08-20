# LOOP HARNESS — Spec

> Recycled from the repo's autoresearch family (autoresearch probe missions +
> apexforge bus + reach ladder ledger) to build and gate **THE LOOP v5.1**
> (`docs/THE_LOOP_v5.1.md`) as an additive seam over the live Moneta-backed substrate.
> Harness law below; blueprint law in the blueprint.

## What this harness proves

That the LOOP seam (`python/synapse/loop/`) can be added surgically and verified
mechanically — one ladder rung at a time — with honest seams where a substrate is not
installed. V0.0 is deliberately tiny: **recipe builds, precommit-before-mutation,
all turns EXPOSED, closure_rate 1.0, zero false verdicts, closes without Octavius.**

## The ladder (blueprint §5 — never re-sort)

| Rung | Scope | Gate to next |
|---|---|---|
| V0.0 | Recipe builds. StagePort CoW read-only. GREEN predicates from mapper. Precommit authored before hou.* mutations. All turns EXPOSED. | closure_rate = 1.0, zero false verdicts, closes without Octavius stage present. |
| V0.1 | SafetyPort (SALUS) f(I, S_k, a_{k+1}, Ω), N=20 sliding window. | Path state tracked multi-step; unauthorized sequences blocked. |
| V0.2 | PG-DRM in MemoryPort; first BLIND calibration samples. | Contaminated chunks dropped; first BLIND sample recorded. |
| V0.3 | StagePort metadata quine filter; drain points (LedgerPort.process()). | Zero quine propagation; prediction debt visible + falling. |
| V0.4 | Outer ring formation over MCP; SALUS evaluates path sequences. | Formation plan builds and settles under full path governance. |
| V0.5 | Metrology: jacobian-monologue ablations (K2 position control, PG-DRM, path latency) under Houdini 22. | Quantitative bounds on position bias and memory safety. |

## The team (agents talk to one another — via `bus.py`, never via telepathy)

- **loop-orchestrator** (`.claude/agents/loop-orchestrator.md`) — read-only conductor:
  sequences one rung per dispatch, owns the spawn ledger in `STATE.json`, halts at every
  human gate. Runs nothing itself.
- **V0.0-FORGE** — builds/hardens the seam code + pinning tests in a worktree, one atomic
  commit per leg, posts a receipt to the bus. Never merges, never pushes.
- **V0.0-MISSION** — authors + runs the probe mission against the forge branch, produces
  the evidence artifact + closure audit, posts a receipt. (Probe authoring = the
  question-author side; only probes produce answers.)
- **V0.0-CRUCIBLE** — adversarial reviewer. Attacks the receipts, the evidence, and the
  contract goalposts. Hostile by design, fair in method.
- Future rungs extend the roster (SafetyPort forge, PG-DRM forge, metrology runner, …).

## The instruments (all recycled)

- `runner.py` — probe-mission runner. Contract: heartbeat `state.json`, evidence
  `<artifact_prefix>_<rung>.json`, `DONE`/`FAILED` sentinel written LAST, every write
  atomic (tmp + os.replace). "Never trust the call, trust the artifact." Pure-python
  for V0.0 (`needs_hou: false`); a later rung may set `needs_hou: true`.
- `mission_schema.py` — validates missions; loop probe kinds live in `VALID_KINDS`.
- `probes.py` — the only module that resolves probe kinds against the live loop seam.
- `bus.py` + `bus/` — append-only JSONL inter-agent channel; claims/release discipline.
- `ledger/` — LedgerPort's real V0.0 precommit file (`v00_precommits.jsonl`).
- `STATE.json` — the ladder ledger: spawn cap 30 / reserve 2, per-rung budgets, receipt
  list, human gates, running log.
- `.claude/workflows/loop.js` — the dynamic workflow, one rung per run.

## Harness law (Article V + the phantom rule)

1. **Merge · push · tag · VERSION edit · contract ratification · flywheel flip — Joe,
   per act.** Never relayed by an agent message. A green receipt is a precondition for
   merge words, never a substitute.
2. **Absence is a measured fact, not a missing feature.** A port whose substrate is not
   installed reports `UNAVAILABLE` with a reason. Never fabricate SUCCESS/BLOCK/verdict.
3. **Runtime is truth.** Probe output beats pinned constants; a live-introspected surface
   beats a doc claim.
4. **Unmeasured renders UNKNOWN.** No estimates. An unmeasurable goalpost is written
   UNKNOWN and the rung does not green it.
5. **One conductor per board.** PID sweep + recent-file scan of `bus/` before any write.
   Two conductors writing one bus is a silent corruptor.
6. **Falsification watch.** Two consecutive bookkeeping-only rungs (no code touched, no
   contract authored, no evidence created) → STOP and tell Joe the harness is spinning.
7. **Code legs work in worktrees** (`loop/<rung>-<leg>`), one atomic commit per leg.
   Evidence artifacts land in main-tree `harness/loop/` as untracked files.

## Run protocol (orchestrator side)

1. Orient: read `STATE.json`, `git status --porcelain --untracked-files=no`, PID sweep,
   verify the rung is not `blocked`.
2. Dispatch one rung: `Workflow(name: 'loop', args: {rung, date, autonomy,
   spawnedSoFar, armed: true})`. `armed` is per-run, never banked.
3. Reconcile the returned `spawned` count back into `STATE.json`; append the log entry.
4. If the run returns `needs_joe` non-empty, present it verbatim and stop.
