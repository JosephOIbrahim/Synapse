# RELAY — the execution arm of the RSI closure harness

*Built 2026-08-01, after RL-1 RECONCILE completed and PRs #51/#52/#53 merged. This file
documents how the ratified PLAN's remaining lines actually execute. It adds no new
predicates and no new ladder — `SPEC.md` (ratified) and `verify.py` remain the law and
the bar. If this file and SPEC disagree, SPEC wins.*

---

## What it is

Three artifacts, one relay:

| Artifact | Role |
|---|---|
| `.claude/workflows/rsi-closure.js` | The engine — one dispatch per phase, agent teams inside |
| `.claude/agents/rsi-closure-orchestrator.md` | The conductor — sequencing + gate discipline (registered next session; the main loop conducts until then) |
| `harness/rsi/briefs/` | Where DECIDE briefs and CLOSE packages land (created on first write) |

The bar is unchanged: `python harness/rsi/verify.py`. The board is unchanged:
`python harness/progress.py`. This relay ships **no new status surface** (R140).

## The three phases, mapped to PLAN

| Dispatch | PLAN line | What runs | Agents |
|---|---|---|---|
| `{phase:"signal"}` | RL-2 | A1/F/E fixed in **parallel worktrees** (no file overlap — verified: A1→`python/synapse/routing/router.py`, F→`shared/router.py` only, E→`forge/engine/`), each fix crucible-attacked | ~7 |
| `{phase:"decide"}` | RL-3 | Evidence briefs for A2 (wire-or-delete), S (wire-or-delete), C (substrate keystone) + cross-brief contradiction check + scribe | ~5 |
| `{phase:"close"}` | RL-5/RL-6 edge | R's L2 probe package (live only with `liveRender:true`), A3 disposition read off the C decision, optional O input-audit (`includeO:true`) | 3–4 |

Every phase ends with a **bar report**: verify.py output, P4's reason verbatim, rung
transitions (worktree claims marked PENDING-MERGE, never "landed"), and Joe's exact next
actions one per line.

## Non-negotiables encoded in the engine

- **Fix all three A1 defects or none** — call sites, tier-0 hardcode, unrecorded fallback.
  One of three leaves the signal lying.
- **Registry in the same commit as the signal fix** — `verify.py` P4 cross-checks code
  against registry in both directions; a split commit goes red by design.
- **F never persists `_session_fast_paths`** — persisting a failure-blind table is the
  registry's named worst-case. Honesty (L1) before durability (L4), always.
- **E may not invent a validator** — a real count or an honest "unvalidated" both pass
  L1; a rendered `0` pretending to be a measurement is the defect.
- **Refutation is a first-class result** — F's defect is a carried claim; if the forge
  refutes it, the registry gets corrected, nothing gets "fixed."
- **Agents recommend, Joe decides** — briefs end in paste-ready flywheel text;
  `flywheel_queue.json` and `DECISIONS.md` are fenced from every agent.
- **`liveRender` defaults false** — the R probe prepares a Joe-supervised package unless
  the flag is explicitly true, and even then: ping-first, bounded render only, 64×64,
  stop on any stall, leave created nodes for the artist's Ctrl+Z. This machine's render
  history earns the paranoia.

## Human gates (the relay halts at each)

1. Merge each signal-fix branch (after its crucible verdict reads SOUND).
2. Ratify/reject the three DECIDE recommendations — **C first or explicitly deferred;
   it is the keystone the other two compose around.**
3. Grant `liveRender` for R's live L2 evidence, or run the probe package yourself.
4. Any `dry_run` flip (A3) and any rung promotion past L3 (`P8`).

## Acceptance — what "the relay worked" means

Rung movement on the bar, nothing else:

- **SIGNAL done:** P4 reason flips to *"now carries an outcome … registry agrees"*; A1/F/E
  at L1 with evidence (or F honestly refuted); pinning tests green; suite floor held.
- **DECIDE done:** three briefs in `briefs/`, zero unresolved contradictions, Joe's three
  flips recorded (any direction — "deferred" counts, silence does not).
- **CLOSE done:** R at L2 with fingerprinted production/live evidence; A3 carries a
  disposition consistent with the C decision; CHAMPION.md scoreboard moves.

**Falsification (from SPEC, restated because it is the likeliest failure):** a phase
that produces more bookkeeping than rung movement gets said out loud in its bar report.
Two consecutive such phases → stop the relay; do not write a third RSI harness.

## Known limits, stated plainly

- A1's L1 fix does not close A1: the router has recorded **zero** production requests
  (live_metrics, 2026-08-01), so L2 needs real chat traffic after the fix lands.
- R's eval (`tests/rsi/eval_line_r_closure.py`) proves L3/L4 **properties under eval
  conditions**; run it with `python`, never pytest (`eval_` prefix collects zero — trap
  already burned once). L2 still requires non-eval evidence.
- The orchestrator agent registers at the **next** session start; in the session that
  built it, the main loop conducts directly.
