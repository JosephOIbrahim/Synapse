# SYNAPSE — Battle Plan

Grounded 2026-08-31 (Mon) against the LIVE repo: master `adfe59e0` = origin/master (ahead 0),
release commit **v5.57.0** ("the store stops having two owners") — `git describe` still says
`v5.56.0`, so the v5.57.0 tag is not cut (Joe's ritual word, parked). Live worktrees:
`mem/m1-handle-law` (merged), `mem/m2-pgdrm` (fix leg, not merged), `rope/beacon`,
`wcrux-scratch`. Untracked: `docs/REACH_BLUEPRINT.md`, `harness/reach/`, `harness/flow/`,
`.claude/agents/{reach-orchestrator,flow-conductor}.md`, `.claude/workflows/{reach,flow-sprint}.js`.
Also grounded against `harness/memory/STATE.json` (2026-08-21 board), `harness/AM_BATTLE_PLAN.md`
(2026-08-08 precedent: Fable 5 scaffolds, Opus 4.8 executes), `SYNAPSE_DEMO_WEEK_ROADMAP.md`
(08-30), `APEX_H22_BLUEPRINT.md` (08-17), `BETA_DONE.md` (08-30, by reference).

**Supersedes** `SYNAPSE_DEMO_WEEK_ROADMAP.md`.
**Does not supersede** `BETA_DONE.md` — that stays the definition of done. This is the when and the who.
**Executes as** harness wave **BP1** — `harness/battleplan/` (own bus, own worktree prefix `bp1-*`).

Observed input: memory-store recall returned **silent nothing**. No error. That is the
green-light-that-cannot-report-failure class — same shape as B1 (`CookedFail` doesn't
raise). It gets the same treatment: a contract that makes silence unshippable, not a patch.

---

## 1 · One rule, two clocks

**Rule:** does the demo or the beta need this? No → parked.

**Clock A — demo.** Demo-ready Sun Sep 6, with a dated fallback (§4).
**Clock B — beta.** `v6.0.0-beta.1` by Sep 30. Demo week is beta week 1, not a competing track.

Three things must be true for the demo: the harness doesn't eat tokens; memory visibly
works in one story; it looks good on screen. The second is broken and it is the only story
beat. It goes first.

---

## 2 · Gate 0 — today. Name the bucket before touching anything.

Silent recall has four places to hide. The probe discriminates them in order; the first
gate that fails names the bucket. **Run it twice** — under hython through `.synapse/hytest.py`
(BP1-TRIAGE, agent lane) and pasted into the live Houdini GUI Python shell (Joe's hands).
The demo runs in the GUI. A probe that passes only under the shim is the false-green lesson.
Headless Moneta is UNAVAILABLE by construction (`harness/memory/STATE.json` substrate_presence),
so G3/G4 under hython may legitimately render UNAVAILABLE — that is a measurement, not a fail.

| Gate | Check | Fails → bucket |
|---|---|---|
| **G1 ENV** | `PXR_PLUGINPATH_NAME` set, pointing at the Moneta `schema\` dir; package file under `OneDrive\Documents\houdini22.0`, absent from `C:\Users\User\houdini22.0` | Environment — the plugin never loads in the session the demo runs in |
| **G2 PLUGIN** | `pxr.Plug.Registry().GetAllPlugins()` has a `moneta`-named plugin | Schema not registered — attribute reads return `None`, no exception |
| **G3 LAYER** | after close → reopen, the memory layer is in `stage.GetLayerStack()` | Store reopened without composing its own layer — handle-law territory |
| **G4 RECALL** | `MemoryPort.query_and_filter(...)` of a known deposit returns it | Predicate / scope: wake predicate, `protected_floor`, quota, query shape |

Hypothesis on file, not the answer: M1's finding — two store authorities, `store.py:1517`
unlocked check-then-create, one orphan holding a Moneta handle — is exactly the mechanism of
a silent deposit. M1 shipped in v5.57.0. If recall is still silent, either a residual
ownership path exists (F4: `panel/shot_login.py:34` unproven) or the bucket is G1–G3. Rows decide.

Outcome map: G1/G2 fail in GUI, pass under hython → env bucket, hours. G3 fails → composition
bucket, ~1 day. G4 fails → recall-path bucket, ~1 day. All pass, repeat-2 pass → v5.57.0
closed it; the silent observation predates the fix. Record, move on.

Receipt: gate · environment · build (runtime-observed) · exception text or `none`. Commit
before receipt (CRX0). Artifact `harness/battleplan/runs/<date>/silent_recall_<env>.json`.

---

## 3 · The board — this week, three lanes

Sorted by what the work needs, not by priority. **HANDS** needs Joe in Houdini. **AGENT** is
wave BP1 in Claude Code worktrees while hands are busy. **WORD** is per-act, never banked.

**HANDS** — Joe, in Houdini
- Mon — Gate 0, GUI half: paste `harness/battleplan/notes/probe_silent_recall.py` into the Python shell. Receipt.
- Tue — on-camera round-trip: deposit → close scene → reopen → recall. Repeat 2. Screen-recorded; every test is footage. While there: the live Ctrl+Z receipt (W5-UNDO-GUI, standing open, human-hands-only) — it also feeds B2.
- Fri — Solaris network, 2h timebox. Panel spacing, 2h timebox, whitespace only.
- Sun — one full dry run.

**AGENT** — wave BP1, Opus 4.8, `harness/battleplan/` (burn discipline: pairs, then solo)
- pair 1 — **BP1-TRIAGE** (Gate 0 hython half, bucket on the bus) + **BP1-RAILS** (budget rails). Parallel-safe: TRIAGE is read-only, RAILS owns `harness/`.
- solo — **BP1-HONESTY** (recall-honesty contract + fix for the bucket TRIAGE named). Blocked on TRIAGE by design.
- solo — **BP1-CRUX** (adversarial crucible, read-only). Blocked on all three.
- cut — LOOPDOCS: `harness/loop/` is the loop-orchestrator's surface (one writer). The v01/v02 blocker re-statement lands as a note in `harness/battleplan/notes/` for that board to consume.
- Thu — OpenMontage rough cut from the Tue–Wed footage bank. Ugly is the plan.

**WORD** — Joe, per act
merge BP1 legs (after CRUX) · merge `mem/m2-pgdrm` (memory board gate) · push (Gate C) ·
**Tue 18:00 branch decision (§4)** · v5.57.0 tag (release ritual: bump → verify → tag) ·
ratify `memory-recall-honesty.yaml`.

Ops: every long op detached — `Start-Process -WindowStyle Hidden -PassThru -RedirectStandardOutput <log>`
— polled by log read. Nothing synchronous crosses the ~4-minute DC ceiling. Agents are dispatched
by `harness/orchestrate.ps1` from `arm_bp1.ps1`, never headless through DC.

---

## 4 · The week, with the branch

| Day | Mile | Done = |
|---|---|---|
| Mon 8/31 | 1 / 8 | BP1 armed. TRIAGE receipt names the bucket. GUI half run at the rig. |
| Tue 9/1 | 2 / 8 | Round-trip HIT on camera in the GUI, repeat 2. HONESTY receipt. **18:00 branch.** |
| Wed 9/2 | 3 / 8 | RAILS: capped run + ledger receipt. CRUX verdicts. Merge words. |
| Thu 9/3 | 4 / 8 | 60-second narrative + rough assembly. |
| Fri 9/4 | 5 / 8 | Two 2h timeboxes. Ship at the timer. |
| Sat–Sun | 6–8 / 8 | Finesse. Dry run. Demo-ready. |

**Tue 18:00 branch.** Round-trip HIT on camera → the table stands. No HIT → demo-ready
moves to **Sun Sep 13**; Wed–Sun become beta-W1 work (RAILS lands, B1/B2/B3 blueprints
open) and the recall fix continues as the W2 opener. Either branch, nothing done this week
is wasted — rails and the P0s are beta-required regardless. Decided by a receipt, not a feeling.

---

## 5 · Contracts (`.synapse/contracts/`, `git add -f`; ratification is Joe's word)

| Contract | Tier | Goalpost |
|---|---|---|
| `memory-recall-honesty.yaml` | green | Recall never returns empty-success. Inside the RATIFIED §4 envelope (param names + `STATUS ∈ SUCCESS|UNAVAILABLE|BLOCKED` unchanged): cannot observe env/plugin/layer → `UNAVAILABLE` + reason ∈ {`env_unset`,`plugin_unregistered`,`layer_uncomposed`}; ran and matched nothing → `SUCCESS` with `payload.hit=false` + reason ∈ {`predicate_nomatch`,`quota_pruned`}; hit → `SUCCESS`, `payload.hit=true`. Goalpost test: memory layer deliberately absent asserts `UNAVAILABLE(layer_uncomposed)`, never `[]`. |
| `harness-budget-rails.yaml` | green | Per-run cap in the unit the runtime reports (UNKNOWN never coerces to unlimited), hard stop → `blocked: budget`, spend ledger every run, execution seam as a lookup table (`harness/rails_exec.json`). Goalpost: a capped run completes with a ledger; a tiny-cap run halts. |
| `demo-round-trip.yaml` | **red** | Human-hands: deposit → close → reopen → recall, HIT on camera, repeat 2, in the GUI. Never simulatable. The Tue 18:00 branch predicate. |

The first one is the point of the week. B1 makes cook silence unshippable; this makes
recall silence unshippable. Same class, same weapon. The M-number ladder belongs to the
memory board (M2 is PG-DRM); this contract carries a board-local name until that board adopts it.

---

## 6 · Beta placement — Sep 7 → Sep 30

`BETA_DONE.md` owns the milestone content. This places; it doesn't redefine. Reconcile against its rows.

- **W2 · Sep 7–13** — B1 / B2 / B3 P0s (cook success-noop, reversibility claim, `enforce_worker_policy=False`). All three are honesty contracts, same class as §5. First full cold run of the fifteen-minute path. Fallback demo date lands here if Tue branched. Memory board M4 (evolve_memory retirement) stays behind its human gate.
- **W3 · Sep 14–20** — registry cut executed: ships / ships-marked / `experimental/`. One-command installer (fAI-read recommendation — in-box only if BETA_DONE says so).
- **W4 · Sep 21–27** — outside-tester dry run against the persona (H22 artist, not TD). Pass-criteria sweep. Docs.
- **W5 · Sep 28–30** — slack. Tag `v6.0.0-beta.1`.

---

## 7 · October — parked, unchanged

Hanish settle · Octavius tick runtime · SALUS · WA2 (APEX bench rungs A1–A6, LOPs-beta
amber→red, MCP re-record red) · weak-domain Waves A–E · REACH skill library (upstream of
Wave A, so first — blueprint is on disk, untracked) · in-process ONNX engine probe ·
nanoharness ablation grid · fabric initiative · Moneta phase work beyond the demo slice.
None of it is on the board until the beta tag exists.

---

## 8 · Calls made here — override by number

1. **Memory ahead of harness this week.** The roadmap had P1 first. Reversed: the story beat is critical path, and RAILS runs in the agent lane in parallel regardless.
2. **Hanish cut from the demo slice.** Demo = Moneta round-trip only. Settle isn't visible on screen and carries the october label.
3. **Tue 18:00 branch, Sep 13 fallback.** Dated kill-switch so the week can't become a store death-march.
4. **Recall honesty rides inside the ratified §4 envelope.** No new STATUS value, no param change; `UNAVAILABLE`+reason and `payload.hit` carry it. Amendment drafted only if a goalpost proves unreachable (M3 precedent).
5. **W5-UNDO-GUI folded into Tue.** Hands are in Houdini anyway.
6. **LOOPDOCS cut to a note.** `harness/loop/` has one writer and it isn't this wave.

---

*Stale check:* stamped 2026-08-31 against live master `adfe59e0`. One card per system —
update this file, don't multiply it. Run instructions live in `harness/battleplan/SPEC.md`.
