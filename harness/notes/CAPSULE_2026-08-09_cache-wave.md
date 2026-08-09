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
