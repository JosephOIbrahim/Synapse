# CAPSULE 2026-08-31 — BP1 battle plan wave
Grounded against live repo at 16:39. Boot from this. Do not assert anything not in this file.

---

## Where we are

**master** `9e444d90` = origin/master (ahead 0). Last release commit: v5.57.0
("the store stops having two owners") — tag NOT cut (Joe's word, parked).
Houdini build observed by probe: **22.0.417** (all docs say 22.0.400 — drift noted, non-blocking).

**Wave BP1** is live. Orchestrator pid 25656. Four legs, Opus 4.8, own bus
(`harness/battleplan/bus/bp1/bus.jsonl`, 13 lines). Arm commit: `9e444d90`.

| Leg | State | Branch | Ahead | Key output |
|---|---|---|---|---|
| BP1-TRIAGE | RECEIPT green+findings | bp1/triage | 2 | bucket=env; probe script; hython run artifact |
| BP1-RAILS | RECEIPT green | bp1/rails | 2 | rails.py + CLI + rails_exec.json seam + 26 tests pass |
| BP1-HONESTY | RECEIPT green+findings | bp1/honesty | 2 | ports.py committed (5d518935); LAUNCH_PATH_FIX.md |
| BP1-CRUX | RUNNING | bp1/crux | 0 | adversarial review in progress; flag NOT landed yet |

**Next auto-move:** CRUX commits verdicts → writes
`harness/notes/h22/BP1_CRUX_LANDED.flag`. That is the trigger for Joe's merge
words. Nothing merges before CRUX.

---

## The problem that started all of this

Silent recall: `MemoryPort.query_and_filter` returned an empty list with no
error on store miss. Same failure class as BASTION B1 (cook success-noop).

**TRIAGE named the bucket: `env`** (hython half).
- G1 ENV: FAIL — `PXR_PLUGINPATH_NAME` unset under hython.
- G2 PLUGIN: FAIL — Moneta plugin not in registry.
- G3/G4: UNKNOWN — headless Moneta is UNAVAILABLE by construction.

Root cause (file:line from TRIAGE): `packages/synapse.json` lives only in
`OneDrive/Documents/houdini22.0/packages/`. The Houdini GUI honors the OneDrive
Documents redirect → G1/G2 may pass in the GUI. `hython` resolves classic
`C:/Users/User/houdini22.0/` → package absent → `PXR_PLUGINPATH_NAME` never set
→ Moneta unimportable.

**HONESTY fixed the code side** (commit `5d518935`):
- `_layer_observable()` seam added to MemoryPort.
- `query_and_filter` now returns `UNAVAILABLE / layer_uncomposed` (or `env_unset`
  / `plugin_unregistered`) when it cannot observe its substrate.
- On genuine no-match: `SUCCESS` with `payload.hit=false, reason=predicate_nomatch`.
- Empty list under SUCCESS is now structurally impossible to return.
- `tests/test_memory_recall_honesty.py` — 3 honesty cases + 1 regression mutation that must turn red.
- `tests/test_loop_contracts.py` unchanged and green.
- §4 parameter names and STATUS values (`SUCCESS|UNAVAILABLE|BLOCKED`) byte-identical.

**The env fix is Joe's hands** — not code, launch-path:
Read `.claude/worktrees/bp1-honesty/harness/battleplan/notes/LAUNCH_PATH_FIX.md`
Three options documented. Short version: add `synapse.json` to classic prefs dir,
or set env vars in a hython wrapper, or set `HOUDINI_USER_PREF_DIR` before hython.

**GUI bucket still UNKNOWN.** TRIAGE's bucket is hython-half only. The GUI paste
decides whether the GUI silence is also env or deeper (layer / recall path).
Script: `.claude/worktrees/bp1-triage/harness/battleplan/notes/probe_silent_recall.py`
Paste into Houdini 22.0.417 Python shell → four rows.

---

## Active worktrees

```
master                              C:/Users/User/SYNAPSE
bp1/crux    (RUNNING)               .claude/worktrees/bp1-crux
bp1/honesty (closing)               .claude/worktrees/bp1-honesty
bp1/rails   (closing)               .claude/worktrees/bp1-rails
bp1/triage  (closing)               .claude/worktrees/bp1-triage
rope/beacon                         C:/Users/User/rope-beacon-wt
mem/m1-handle-law (merged, live wt) C:/Users/User/synapse-m1-handle-wt
mem/m2-pgdrm (fix, not merged)      C:/Users/User/synapse-m2-pgdrm-wt
wcrux-scratch (detached HEAD)       .claude/worktrees/wcrux-scratch
```

---

## Contracts

| Contract | State |
|---|---|
| `memory-recall-honesty.yaml` | PENDING ratification — Joe word |
| `harness-budget-rails.yaml` | PENDING ratification — Joe word |
| `demo-round-trip.yaml` | PENDING ratification — Joe word (red, GUI only) |
| `loop-v00.yaml` | RATIFIED |

---

## What shipped this session (all unmerged, behind CRUX + Joe's words)

1. `docs/BATTLEPLAN.md` — supersedes demo roadmap; owns the week + beta placement + 6 override calls.
2. `harness/battleplan/` — full wave harness (missions, prompts, rows, bus, arm, dashboard, SPEC).
3. `harness/rails.py` + `harness/rails_exec.json` — budget rails, hard stop, spend ledger, model seam. 26 tests pass.
4. `python/synapse/loop/ports.py` — recall honesty envelope. Real product code.
5. `tests/test_memory_recall_honesty.py` — goalpost tests.
6. `harness/battleplan/notes/probe_silent_recall.py` — dual-env Gate 0 probe.
7. `harness/battleplan/runs/2026-08-31/silent_recall_hython.json` — hython receipt.
8. `harness/battleplan/notes/LAUNCH_PATH_FIX.md` — env-bucket fix, Joe's hands.
9. Three contracts in `.synapse/contracts/`.

---

## Joe's checklist — next chat opens here

- [ ] Re-poll CRUX: `python harness\battleplan\dashboard_bp1.py --once`  
      or say "update dashboard". Wait for `harness/notes/h22/BP1_CRUX_LANDED.flag`.
- [ ] Read CRUX verdicts: SOUND = merge-ready; SOUND-WITH-NITS = merge with noted items; BROKEN = named leg doesn't ride.
- [ ] Merge words (per-act): `bp1/triage` · `bp1/rails` · `bp1/honesty` · `bp1/crux` — after CRUX SOUND on each.
- [ ] Push + v5.57.0 tag (release ritual: bump → verify → tag → Gate C push).
- [ ] Ratify three contracts — your word, one at a time.
- [ ] GUI probe — paste `probe_silent_recall.py` in Houdini Python shell. Four rows. Decides whether the demo beat is in reach.
- [ ] LAUNCH_PATH_FIX.md — read and execute one option before Tuesday if GUI probe shows G1/G2 fail there too.
- [ ] Tue 18:00 branch decision — two camera HITs → demo Sep 6; no HITs → Sep 13 (beta W1, nothing wasted).

---

## Standing open items (not this week)

- v5.57.0 tag not cut (parked, Joe word)
- `mem/m2-pgdrm` not merged (memory board, separate word)
- `harness/notes/h22/UNFINISHED_WORK_REVIEW_2026-08-20.md` — untracked, unreviewed
- REACH blueprint (`docs/REACH_BLUEPRINT.md`, `harness/reach/`) — post-demo
- FLOW (`harness/flow/`, `.claude/workflows/flow-sprint.js`) — post-demo
- BASTION B1/B2/B3 — W2 (Sep 7–13)
- WA2 APEX bench rungs A1–A6 — october
- Hanish / Octavius / SALUS — october
- W5-UNDO-GUI — Tue hands session

---

## Board commands

```powershell
python harness\battleplan\dashboard_bp1.py --once   # poll once
python harness\battleplan\dashboard_bp1.py          # live + board.html
python harness\battleplan\bus.py read bp1           # bus
python harness\battleplan\status_bp1.py             # one-pass status
```

---

## Constitutional gates (always held)

merge words · push · tag/publish · drop.json writes · contract ratification —
all per-act Joe words. CTO authority for execution acts (authoring, commits, ops)
is standing. One writer per surface. No amends on master. CRUX before merge.
