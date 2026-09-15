# v2 investigation + build wave — 2026-09-14

Seven investigation runs and two build waves against the SYN-V2-001 blueprint
(`harness/v2-20260913/artifacts/v2-instantiate-gate/SYNAPSE_V2_BLUEPRINT_B.1.md`,
untracked, ruled instructional rather than governing).

## Merged to master

Suite gate: floor `8869 passed / 412 skipped / 0 failed` at `bd65e4b6`,
after `8880 passed / 412 skipped / 0 failed` at `5ea7dbdf`. +11 tests, all
executing (skips unchanged). Local only — not pushed.

| Commit | Fix |
|---|---|
| `3cef7957` | date-stamp every session journal entry |
| `da960082` | announce the system-prompt fallback instead of substituting silently |
| `5ea7dbdf` | stop `log_decision` silently discarding out-of-schema payload keys |

## HELD — do not merge without rework

**`42ae6899`** on `worktree-wf_8a870870-1d5-3` — *upgrade a legacy agent.usd
instead of dropping its decisions.*

Two independent attack lenses, different mechanism traces, same severity-4
conclusion: **the verify reads its own write buffer, not disk.** A migration
that never lands still reports `"2.0.0"` to all eight `ensure_scene_structure`
callers, and cross-process it destroys a persisted decision record while doing
so. That is the failure class the fix exists to eliminate, reproduced inside the
fix's own honesty mechanism.

Three more, all in `BUILD-WAVE1-report.md` §7:
- puts a whole-layer `Usd.Stage.Open → mutate → Save()` on the hot path of every
  memory operation, reachable from eight modules across two processes, while
  `agent_state.py` holds no lock of any kind
- `migrate_to_v2` replaces `customLayerData` wholesale, dropping `synapse:status`
  from a stub-seeded store
- its five tests sit under a pxr class gate; stock CI has no OpenUSD, so the
  merge gate executes **zero assertions** against the migration

Pass 3 scope is in `BUILD-WAVE1-report.md` §7. The branch is intact; nothing is
orphaned.

## Also open

- `worktree-wf_061df37e-b74-3` (`ad90240a`) and `-4` (`25b714d3`) — F2/F4 panel
  fixes. **Gate joe**: both change what the artist sees. Built, not merged.
- `.scratch/` is **not** in `.gitignore`, and workflow agents write there by
  default. Worth one line in `.gitignore` so agent output cannot be swept into a
  commit by `git add -A`.

## Contents

| File | What |
|---|---|
| `G3-observation-gaps.html` | four record systems, all write-only; the LOOP is dormant by configuration |
| `WAVE0-ship-floor.html` | Moneta refuted; the live gap is the upgrade path; signing unsigned by design |
| `WAVES23-proposal-surface/` | proposal mode already exists; all three apply guarantees broke under attack |
| `BUILD-WAVE1-report.md` | the four builds, the collision that wasn't, the merge order |
| `suite-floor-bd65e4b6.txt` · `suite-after-5ea7dbdf.txt` | the gate, both sides |
