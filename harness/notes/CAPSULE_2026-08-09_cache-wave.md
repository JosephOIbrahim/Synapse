# CAPSULE 2026-08-09 — cache wave (Session 1 close)

**Wave:** Resource-aware cache intelligence · Phase 0+1 under ruling R-CACHE-1.
**Position at close:** Mile 2 of 5 — build team live and grinding, detached.

## In flight right now
- Mile 2 build: runner PID 59136, launched 12:26:33, log `harness/notes/scratch/mile2_build.log`,
  progress ticks `harness/notes/scratch/mile2_progress.log`.
- Worktree `C:/Users/User/SYNAPSE/.claude/worktrees/cache-p0` on `feat/cache-advisor-p0` @ de8c5edd (confirmed created).
- Team: lead (Sonnet, `claude -p`) + forge-models (Sonnet) + forge-host (Sonnet) + reviewer (crucible, Opus)
  + gatewarden subagent verdict gate. Expected final lines: M2_WORKTREE / M2_BRANCH / M2_COMMITS /
  M2_FILES / M2_TESTS / M2_NEGATIVE_CONTROL / M2_ASSAY: NOT RUN / M2_REVIEWER, then EXITCODE.

## Session 2 resume protocol (read-first, never blind)
1. Tail `mile2_build.log` — if EXITCODE present, parse the M2_ lines; else check PID 59136 alive and tail `mile2_progress.log`.
2. If reviewer BLOCKED or tests red: one bounded repair was already allowed in-mission; escalate rather than loop.
3. Mile 3 = run the assay script in hython on 22.0.400; record build/command/exit/artifact; NOT RUN if Houdini unavailable.
4. Mile 4 = Phase 1 advisor (caller: bridge registry + existing panel result surface, per ruling item 4) + regression sweep.
5. Merge and push are Joe's per-act words. Nothing is pushed. `drop.json`/`ratified` untouched.

## Done this session
- Mile 0: AGENT_TEAMS env on · blueprint landed docs/ (sha 8a5290e7…3a32e0, 1470 lines, both sides) · smoke PASS (1 repair) · FID/CI0 confirmed merged.
- Mile 1: team intake → `docs/intake/adjudication-resource-aware-cache.md` (16/6/16/5, 19/19 sustained, REVIEW_ONLY).
- Ruling: Joe approved adopt-with-amendments → `docs/reviews/cache-adjudication-ruling.md` (R-CACHE-1). Phase 2 blocked pending SideFX.

## Learnings banked
- `claude -p` team leads MUST be ordered to hold the turn until teammate traffic completes — otherwise the session ends mid-exchange. Mandatory boilerplate.
- Team peer messaging (SendMessage) works headless on this box. Teammate spawn under auto mode needs no interactive approval.
- Bridge (DC + Windows-MCP) dropped once mid-Mile-1; detached runner unaffected; Joe restarted; toasts unreliable — progress file + capsule is the visibility channel.
- Untracked new: blueprint, adjudication, ruling doc (commit in Mile 5 close). Scratch debris: smoke*/intake*/mile2* logs+runners, `~/.claude/teams/default` leftover — sweep at close.

## Token count (whole job, this session)
Agent sessions dispatched on Joe's plan: 14 (2 smoke runs ×3, intake ×3, mile2 ×5 incl. gatewarden). Retries: 1 (smoke). Chat-side orchestration tokens: unavailable. Per-agent token totals: unavailable (not captured in -p logs).


---

# SESSION 1b APPEND — 2026-08-09 ~14:40 (Joe overrode the noon close; wave continued)

**Position at this checkpoint:** Mile 4 of 5 — Phase 1 team live and detached (PID 9364, launched 14:34:34, liveness confirmed 14:37). Log `scratch/mile4_build.log`, ticks in `scratch/mile2_progress.log`. Expected final lines: M4_COMMIT / M4_CACHE_TESTS / M4_ASSAY / M4_FULL_SUITE / M4_REVIEWER, then EXITCODE.

## Landed since the noon capsule (all observed, branch feat/cache-advisor-p0)
- **M2 closed, reviewer CLEAR:** bd7af1cc (host probe) · bf0610b9 (pure package) · 08e7c642 (reviewer note: UNKNOWN had no producer). 15 files, 4667 insertions, 109/0 cache tests, negative control PASS. First M2 lead was killed by the `claude -p` 600s background ceiling — fix: `$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS='0'` in every runner (landmine #2; #1 is the hold-turn clause).
- **M3 live assay (hython 22.0.400):** after one surgical script repair (null has no tx; cook-before-for_last_cook; measurable unit cook) → 6/7 pass + one genuine CONTRACT FINDING, committed ede8d1b8.
- **THE FINDING (receipts on disk):** `hou.OpNode.lastCookTime()` on 22.0.400 returns accurate MILLISECONDS in a GUI session (`cache_h22_gui_assay_22.0.400.json`: wall 171.4ms → raw 171.14; ui_available true; run via `houdini -waitforui` + Computer Use) and unconditional **0.0 headless** (perfMon on or off; `cache_h22_contract_assay_22.0.400.json`). Deployment context (GUI) is fine; farms/tests/hbatch get nothing and must say UNKNOWN.
- **M3b closed, reviewer CLEAR:** ca7d749e — zero-guard wired as the UNKNOWN producer (0.0/None/negative + cookCount>0 → UNKNOWN + `lastCookTime_unreported`); assay item 3 re-specified as a declared delta (headless 0.0 is EXPECTED; fails loudly only if the contract changes); assay now 7/7 exit 0; boundary file 19/19.
- **Full-suite baseline verified by me:** 6 real failures, none cache-scoped: pkg_bootstrap R310 (Py3.14 vs cp311/cp313 vendored ABI), scene_memory validate_healthy_dir (known W1 Moneta pending), 4× statusline git-comparisons (worktree-environment class — *inference*; airtight version = rerun on bare master in Session 2 if wanted). A 7th `lastfailed` entry (`test_zero_ms_converts_to_zero_seconds_not_none`) is STALE pytest bookkeeping — that test was deleted+replaced by M3b's declared-delta test (line 248, 19/19 green).

## Session 2 protocol
1. Read-first: tail `mile4_build.log`; parse M4_ lines or confirm PID 9364 alive and tick-watch.
2. M4 CLEAR → **Mile 5 close (Joe's gates):** he reviews the commit series → merge word → push word (Gate C `$env:` form) → then commit the wave docs on master (blueprint, adjudication, ruling, capsule, gui-assay receipt) → SUPPORT_MATRIX row for the lastCookTime contract (GUI=ms verified · headless=0.0 verified, receipts named) → regression sweep on merged master (version conformance, latency harness, ratchet) → debris sweep (scratch runners/logs stay gitignored; delete `~/.claude/teams/default` leftover; drop stale lastfailed) → **full teach-down + Operator's Card** (queued, owed: run the advisor, run a team dispatch, both landmines, assay rerun command).
3. M4 BLOCKED → verbatim reason to Joe, fork, no loops (bounded-repair budget for M4: one).
4. Token ledger: +2 agent sessions M3b (forge Sonnet, crucible Opus) + lead; +3 M4 (lead Sonnet, forge Sonnet, crucible Opus); GUI assay = 0 model calls (script + Computer Use). Running total ~20 agent sessions, 1 retry (smoke), 2 in-flight repairs (M2b ceiling relaunch, M3 script fix). Exact tokens: unavailable.


---

# WAVE 2 APPEND — 2026-08-09 ~16:15 (pre-vacation push; Joe leaves tomorrow)

## Landed this wave
- **RELEASE v5.45.0 SHIPPED**: VERSION bump → six surfaces CONFORM → commit 8c41fe18 → tag v5.45.0
  (pytest pre+post PASS) → master+tag pushed (97dd936a..8c41fe18) → GitHub Release page live with
  Latest badge → panel verified by observation: hython via the package paths imports
  synapse.__version__ = 5.45.0. `synapse.json` is a versionless live pointer (SYNAPSE_ROOT) —
  updates with every release BY DESIGN; per-release check is the doctor stamp (step 8).
  Note: release commit swept in the morning wave's two record files (three-mile capsule +
  usdlux json) — flagged to Joe, house convention anyway.

## In flight
- **W1 Moneta**: PID 21220, launched 16:10:44, Opus lead + Opus forge + Opus crucible on worktree
  `w1-moneta` / branch `fix/memory-store-recovery` (pre-ruled name). Stages: A evidence via
  Autoresearch mission w1_moneta_stores → B FULL BACKUP to C:\Users\User\.synapse\backups\w1_2026-08-09\
  with verified manifest (hard gate before any mutation) → C build (env-var expansion fix, unify
  stores, conflict policy = keep-both never-delete, un-xfail PRST pair, scene_memory green,
  full suite r310-only) → D crucible data-safety review. Log scratch/w1_build.log, ticks
  scratch/w1_progress.log. Final block: W1_STORES_FOUND / W1_BACKUP / W1_COMMITS / W1_PRST /
  W1_SCENE_MEMORY / W1_FULL_SUITE / W1_REVIEWER. NO push/merge — those are session-3 acts.

## Phase 2 status
P2-as-written stays REJECTed (R-CACHE-1 e3: no in-flight cook cancel API on this build — Joe's own
SideFX escalation is the receipt — plus the 250ms boundedness law vs a 22–31min main-thread bake).
Achievable re-scope offered to Joe: (a) insertion-only (`synapse_insert_cache`, undoable — e3 never
touched it) buildable tonight in parallel; (b) out-of-process bake (detached hython child = killable
= cancellation by architecture, main thread never blocks) — designed post-vacation with its own
adjudication pass. Awaiting his word; do not build rejected scope on momentum.

## Session-3 resume protocol
1. Read-first: tail w1_build.log; parse W1_ block or confirm PID 21220 alive + tick-watch.
2. W1 CLEAR → Joe's gates: review series on fix/memory-store-recovery → merge word → push word →
   consider v5.45.1 or v5.46.0 (memory recovery is user-facing: minor bump likely) via RELEASE_CARD.
3. W1 BLOCKED → verbatim reason + fork, no loops. Backups at .synapse\backups\w1_2026-08-09\ are
   the recovery path — verify manifest before ANY retry touches stores.
4. If insert team was also dispatched: parse its M-INS_ block same pattern, worktree cache-ins.
5. Joe is ON VACATION — mobile-first: compress, lead with verdicts, board-style summaries.

## Ledger (wave 2)
Release = 0 agent sessions (instrument acts, recorded: VERSION edit, sync, commit 8c41fe18, tag,
push branch+tag, gh release). W1 = 3 Opus sessions in flight. Tokens: unavailable.

**16:2x addendum:** insert team DISPATCHED on Joe's word - worktree cache-ins, branch feat/cache-insert, log scratch/ins_build.log, ticks scratch/ins_progress.log, final block INS_*. Two Opus teams now parallel.

**16:5x addendum:** autonomous CLOSER dispatched at Joe's direction (scratch/closer.ps1) - waits for both verdicts, merges CLEAR-only, verifies suite vs allowed-failure set, one Gate C push; refuses loudly on any anomaly leaving merges local. Receipt: scratch/CLOSE_RECEIPT_2026-08-09.log. Session-3 first read = that receipt.
