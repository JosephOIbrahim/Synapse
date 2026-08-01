# SYNAPSE review — 2026-08-01

*Produced by a 12-agent read-only review (`wf_8ce1778e-d22`, 1,700,845 subagent tokens, 582 tool
uses, 36 min) plus inline live probing. Read-only: nothing here was fixed by the review itself.*

## Read this first — the 12 CRITICAL findings

- FREEZE FORENSICS is diagnosis-only: the PRIMARY remediation and all 3 hazard tickets have zero code landed
- Four local branches hold unlanded work with no remote backup
- CI is red at HEAD on a CLAUDE.md version-banner drift, not the mcp drop
- A reproducible ~2.01s per-call floor exists on the live websockets path and is invisible to every in-process timer
- 17,167 ms max dispatch wait plus a main-thread timeout 146 s before measurement started
- Class 4 is diagnosis-only — HEAD commit changed zero source files and all five remediation items are unaddressed
- Panel prompt-send path runs tools INLINE on the Qt main thread — 46 recorded stalls, worst 46.7 seconds
- Same tool, two paths: synapse_inspect_scene is 1.98ms on /mcp and 10,005ms main-thread-blocking on the panel
- FREEZE VERDICT: SYNAPSE does freeze Houdini today — Class 4 prompt-send grip is diagnosed, mapped, and entirely unrepaired
- Main-thread grip is unmeasured on the exact path the Class 3 fix created — no Class 4 fix can be proven to work
- A harness check reports GREEN over a live PDG defect it structurally cannot see
- Four branches carrying finished, verified work exist only on this disk

**Counts:** 12 critical · 37 high · 66 medium · 29 low · 11 info (155 total).

This file is large by design — it is the evidence corpus. Jump to a severity heading
rather than reading it end to end.


Distilled into the repo so the investigation never has to be re-run. Every finding carries the
evidence its agent gathered; `verification_status` is the agent's own claim about that evidence.


---

## CRITICAL

### FREEZE FORENSICS is diagnosis-only: the PRIMARY remediation and all 3 hazard tickets have zero code landed

**Claim.** HEAD commit f427320 added 347 lines across 3 files, all documentation/workflow — none of the 5 ranked remediation items in harness/notes/FREEZE_FORENSICS_20260731.md:83-97 has an implementation.

**Why it matters.** This is the live artist-facing bug — a Houdini hard-freeze mid-chat. The forensics correctly re-classified it as the MITIGATED-only residual of class 1 generalized ('the wait was bounded, the payload never was', :67), which means the v5.40.1 release note 'the chat no longer grips the UI' is true only for the class-3 path. The h9 hazard is the sharpest: a live wire with zero emitters, one `.emit` away from re-arming the class this repo just closed.

**Action.** Split by size. TRIVIAL/ENGINEERING now: item 3 (disarm or regression-test the h9 wire, synapse_panel.py:1937-1938) and item 2 (fix the stale attribution string, tool_executor.py:57-96/:472-479) — the latter is a prerequisite for trusting the next forensics run. SMALL: h8 (wrap the disconnect-finally hou calls in run_on_main) and h10 (bound the pre-auth recv). LARGE, needs a design call: item 1, capping mid-turn main-thread payload footprint across ~20 cook(force=True) sites — handlers_render.py:109-113 states plainly 'nothing in Python can interrupt the main thread from the main thread', so this is architecture, not a patch.

**Evidence.**

- `git show --stat --oneline f427320` -> `.claude/agents/freeze-forensics-orchestrator.md | 22 +++`, `.claude/workflows/freeze-forensics.js | 216 ++++`, `harness/notes/FREEZE_FORENSICS_20260731.md | 109 ++++` — '3 files changed, 347 insertions(+)'. Zero source files.
- harness/notes/FREEZE_FORENSICS_20260731.md:3 — 'Diagnosis only. No code changes.'
- harness/notes/FREEZE_FORENSICS_20260731.md:27-28 — 'h7 — handler-heavy-tool (CONFIRMED; survived three crucible kill attempts). Mid-turn tool payloads hold the Houdini main thread uninterruptibly. The v5.40.1 fix (class 3, d15d9b2) bounded the *caller wait*, never the running payload.'
- harness/notes/FREEZE_FORENSICS_20260731.md:43-47 — three OPEN hazard tickets with named closing probes: h8 off-main hou disconnect (`server/websocket.py:605-606`), h9 armed inline slot (`panel/synapse_panel.py:1937-1938`, 'One `.emit` re-arms class 3'), h10 pre-auth recv (`server/websocket.py:480`).
- harness/notes/FREEZE_FORENSICS_20260731.md:41 — a named follow-on defect that will corrupt the NEXT investigation: the `tool_executor` log string 'Inline tool ... ran Xms on the main thread (Qt loop stalled this long)' is stale post-fix and 'will misattribute future freezes. This corrupted forensics this run and will corrupt the next one.'

*VERIFIED · freeze · effort: large*

### Four local branches hold unlanded work with no remote backup

**Claim.** fix/corpus-usdrender-rop (96b3978, 14 commits), clear/l5-phantom-scanner (eb1e110), feat/panel-ux-pass (0d27a17) and wip/panel-goalposts (c3a6032) all contain content absent from master AND have no ref on origin, so the only copy is this disk.

**Why it matters.** The corpus branch is the fix for a documented failure class (the RAG corpus re-teaching a phantom API after the code was fixed). Losing it means the phantom teaching stays live and has to be re-derived. The panel-goalposts branch is 1,130 lines of test work with a single copy.

**Action.** Push all four to origin as backup branches before any further worktree/branch cleanup. This is a `git push -u origin <branch>` x4 and requires no merge decision.

**Evidence.**

- git for-each-ref refs/heads -> 'fix/corpus-usdrender-rop||', 'clear/l5-phantom-scanner||', 'feat/panel-ux-pass||', 'wip/panel-goalposts|origin/master|[ahead 2, behind 626]' (empty upstream field = no tracking remote)
- git ls-remote --heads origin | grep -Ei 'l5-phantom|panel-ux-pass|corpus-usdrender|panel-goalposts' -> only 'refs/heads/archive/retina-m2-orphan' returned; none of the four have a remote ref
- patch-id --stable of every branch-unique commit vs merge-base..master: all UNLANDED (e.g. 'UNLANDED eb1e110c | feat(verify): extend phantom lint to pdg/pxr (CLEAR L5 G2)', 14x 'UNLANDED ... fix(corpus): ... usdrender_rop')
- git grep -c -P 'usdrender(?!_rop)' master -- rag/skills/houdini21-reference -> 56 bare-phantom lines across 14 files; same grep on fix/corpus-usdrender-rop -> 13 lines across 9 files
- diffstat merge-base..branch: l5-phantom-scanner 277 insertions/3 files; panel-ux-pass 75 insertions/3 files; panel-goalposts 1130 insertions/8 files (5 new tests/panel/*.py)

*VERIFIED · unfinished-work · effort: trivial*

### CI is red at HEAD on a CLAUDE.md version-banner drift, not the mcp drop

**Claim.** master CI fails at HEAD f427320 because VERSION says 5.41.0 while CLAUDE.md's banner still says v5.40.1; the release commit 8dfa23d bumped one and not the other, and test_phase0c_doc1_version_conformance.py enforces the pair.

**Why it matters.** Every PR goes red on merge-base, exactly the symptom the memory attributes to the mcp drop — so the team may 'fix' an already-fixed dependency and never touch the real cause. The fix is a one-token edit to a doc banner.

**Action.** Update CLAUDE.md:3 banner from `SYNAPSE v5.40.1` to `SYNAPSE v5.41.0`. Then consider adding the banner bump to the release checklist so a VERSION bump can't ship without it.

**Evidence.**

- VERSION file contents: `5.41.0`
- CLAUDE.md:3 `> **Target:** Houdini 22.0.368 (dual-build with H21 artifacts) · SYNAPSE v5.40.1 · Python 3.13 · 123 MCP tools registered`
- Local repro: `python -m pytest tests/test_phase0c_doc1_version_conformance.py -q` -> `FAILED tests/test_phase0c_doc1_version_conformance.py::test_version_single_sourced_and_docs_conform` / `AssertionError: CLAUDE.md does not state the canonical SYNAPSE version v5.41.0 (DOC-1: update the banner -- or this test if the version changed).` / `1 failed, 2 warnings in 0.38s`
- tests/test_phase0c_doc1_version_conformance.py:44 `assert f"v{canonical}" in claude`
- `gh run list` -> run 30679790433, headBranch master, displayTitle 'docs(forensics): freeze forensics relay', conclusion `failure` (this is HEAD)

*VERIFIED · unfinished-work · effort: trivial*

### A reproducible ~2.01s per-call floor exists on the live websockets path and is invisible to every in-process timer

**Claim.** On 2026-07-27, 35 of 35 read-only commands measured a 2.01s median end-to-end (range 2.00–2.07s) across two independent client stacks, while in-process instrumentation on the same build family records sub-ms to ~100ms — leaving ~2000ms per call unattributed and contradicting the report's 'T2 = ms class on websockets' and 'not a transport problem' verdicts.

**Why it matters.** The standing authority document routes all latency effort at turn-count and perceived latency on the premise that transport is milliseconds. If ~2s of every tool call is transport/protocol overhead, then a 10-tool build spends ~20s in a bin the report declares negligible — and every recommendation in Section 5 is prioritized against a wrong ledger.

**Action.** Do not amend the report (human gate). Escalate this as the single highest-value input to the Section 5 item-1 re-measure: instrument one span OUTSIDE the handler (client send -> client recv) and bisect against the existing dispatch_wait/main_thread_direct histograms. The mechanism is currently undetermined, so measure before theorizing.

**Evidence.**

- harness/notes/forensic/s1_artifacts/ws_readonly_sweep.json — computed distribution: n=35, min=2.0, max=2.07, median=2.01, p95=2.03 (seconds). Direct WS client, fresh connection per call.
- harness/notes/forensic/s1_artifacts/mcp_surface_probe.json — computed distribution over the external MCP stdio surface: median=2.01, 30+ tools at exactly 2.01s. Different client stack, same figure.
- Producer #1 verified sleep-free: harness/notes/forensic/s1_ws_readonly_sweep.py:77-96 `one_shot()` — t0=time.time(), connect, send, recv-until-matching-id. No sleep anywhere in the loop (lines 104-126).
- Producer #2 verified sleep-free: harness/notes/forensic/s1_mcp_surface_probe.py:91-112 `wait_for()` — q.get(timeout=min(remaining,1.0)) returns the instant the reader thread enqueues; no pacing delay.
- Not connection setup: mcp_server.py:202 `_ws_connection = None` is a module global reused at :270/:275 — the MCP path holds a PERSISTENT connection and still pays 2.01s.

*VERIFIED · latency · effort: small*

### 17,167 ms max dispatch wait plus a main-thread timeout 146 s before measurement started

**Claim.** The live dispatch-wait histogram records a 17,167.1 ms maximum, 7 samples over 1000 ms, 3 over 2000 ms and 2 over 4000 ms; synapse_doctor separately reports last_timeout_ts 1785592504.5058525, which is 145.8 s before my first ping at 1785592650.3308887.

**Why it matters.** A 17.2-second enqueue-to-start wait means the Houdini main thread was completely unavailable for 17 seconds - that is the artist-visible freeze, captured in this process. The timeout 2.4 minutes before I started proves the failure mode is live in the current session, not a historical artifact carried forward from a prior report.

**Action.** Treat the 17.2 s max as the primary freeze exhibit. Add a timestamp and a caller label to the max sample so the worst stall can be correlated to an action; without that, this number can never be attributed to a cause.

**Evidence.**

- synapse_metrics -> synapse_dispatch_wait_ms_max 17167.1001 (identical in all three scrapes)
- synapse_metrics @C -> {le="250"} 33919 ; {le="500"} 33919 ; {le="1000"} 33920 ; {le="2000"} 33924 ; {le="4000"} 33925 ; {le="+Inf"} 33927 -> 8 samples >250 ms, 7 >1000 ms, 3 >2000 ms, 2 >4000 ms
- synapse_doctor -> checks[main_thread].result.stall = {"stalled":false,"consecutive_timeouts":0,"last_timeout_ts":1785592504.5058525}
- synapse_ping (first call this lane) -> timestamp 1785592650.3308887; 1785592650.33 - 1785592504.51 = 145.8 s
- C:/Users/User/SYNAPSE/python/synapse/server/main_thread.py:311 if not done.wait(timeout=timeout) -> _record_timeout

*VERIFIED · freeze · effort: medium*

### Class 4 is diagnosis-only — HEAD commit changed zero source files and all five remediation items are unaddressed

**Claim.** Commit f427320 (HEAD) is documentation-only, and every one of the five remediation items its forensics doc raised is verifiably still open in the source at HEAD.

**Why it matters.** The most recent work on the artist's #1 freeze produced a map, not a repair. Anyone reading the commit log sees freeze work at HEAD and may assume the grip is handled; it is not. The mid-turn payload can still hold Houdini's main thread for tens of seconds during normal chat.

**Action.** Treat Class 4 as fully open. Start with remediation item 1 — timebox or chunk the cook-heavy handlers — and pin it with the doc's own test: dispatch a handler that holds main >10s via the off-main worker path and assert the freeze heartbeat keeps beating.

**Evidence.**

- git show --stat f427320 → exactly 3 files: `.claude/agents/freeze-forensics-orchestrator.md | 22 +++`, `.claude/workflows/freeze-forensics.js | 216 ++++`, `harness/notes/FREEZE_FORENSICS_20260731.md | 109 ++++` — 347 insertions, 0 deletions, no source file touched
- Commit body verbatim: 'Remediation ticket in the doc; no fixes dispatched (human gate).'
- harness/notes/FREEZE_FORENSICS_20260731.md:3 — '**Diagnosis only. No code changes.**'
- Item 1 (PRIMARY, cap the payload) OPEN: `grep -rn 'cook(force=True)' python/synapse/server/ | wc -l` → 21 sites, none timeboxed; python/synapse/server/main_thread.py:302 runs `result_holder[0] = fn()` with no timer
- Item 2 (stale attribution string) OPEN: python/synapse/panel/tool_executor.py:475-479 unchanged

*VERIFIED · unfinished-work · effort: large*

### Panel prompt-send path runs tools INLINE on the Qt main thread — 46 recorded stalls, worst 46.7 seconds

**Claim.** The synapse.panel.tool_executor path executes tools synchronously on the Houdini main thread, self-reporting 46 separate occasions where the Qt event loop was stalled past its 1000ms threshold, the worst being houdini_set_parm at 46,724ms.

**Why it matters.** This is the Class-4 GUI-grip bug in its own words. The panel's own instrumentation states the Qt loop was stalled — meaning the artist's node graph was completely unresponsive for up to 46 seconds while a single prompt-driven tool ran. The mechanism is not contention or queueing; it is direct synchronous execution on the UI thread.

**Action.** Move panel tool execution off the main thread onto the same dispatch path /mcp uses, or at minimum chunk and yield to the Qt event loop. Treat houdini_capture_viewport and houdini_create_node as the priority offenders by frequency and magnitude.

**Evidence.**

- C:/Users/User/.synapse/logs/synapse.log:18721 — `2026-07-31 12:51:49,705 [synapse.panel.tool_executor] WARNING: Inline tool 'houdini_set_parm' ran 46724ms on the main thread (Qt loop stalled this long; slow threshold 1000ms)`
- `grep -c "on the main thread (Qt loop stalled" synapse.log` → 46
- Census of the 46: houdini_capture_viewport appears ~10x in the 20,324–24,219ms band; houdini_create_node 24,872ms (2026-07-31 12:04:53); cops_create_network 8,775ms; houdini_execute_python 9,591ms (2026-07-29 15:48:33)
- Production fingerprint, not pytest: logger namespace is `synapse.panel.tool_executor`, tool names are real bridge tools, and the surrounding lines (18717-18722) are synapse.resilience / synapse.freeze_chain / synapse.panel.claude_worker — none carry the pytest temp-path marker that the 448 pytest-authored lines in this file do.

*VERIFIED · freeze · effort: medium*

### Same tool, two paths: synapse_inspect_scene is 1.98ms on /mcp and 10,005ms main-thread-blocking on the panel

**Claim.** The identical tool synapse_inspect_scene cost 1.9771ms server-side when I called it via /mcp today, and 10,005ms of Qt-loop stall when the panel called it on 2026-07-31 — a ~5,000x path-dependent difference that proves a clean /mcp measurement carries zero information about panel behaviour.

**Why it matters.** This is the empirical justification for the /mcp vs /synapse two-path safety split in CLAUDE.md, and it is the reason my lane's clean result must not be read as exoneration. Any future probe that exercises only /mcp will keep returning green while the panel keeps freezing artists. It also shows the freeze is not tool-intrinsic — the same code is fast on the other path.

**Action.** Adopt this pair as the standing regression control for the GUI-grip fix: the same tool must be measured on BOTH paths, and the panel number is the only one that speaks to freeze. Also investigate the recurring exact 10005ms value as a distinct timeout defect.

**Evidence.**

- My live /mcp call, synapse_metrics histogram: `synapse_tool_duration_ms_sum{tool="inspect_scene"} 1.9771` with `synapse_tool_duration_ms_count{tool="inspect_scene"} 1` — that count of 1 is my call, this run
- C:/Users/User/.synapse/logs/synapse.log — `2026-07-31 08:46:26,765 [synapse.panel.tool_executor] WARNING: Inline tool 'synapse_inspect_scene' ran 10005ms on the main thread (Qt loop stalled this long; slow threshold 1000ms)`
- Adjacent panel entry same morning: `2026-07-31 08:44:41,290 'houdini_create_node' ran 10005ms` — the repeated exact 10005ms value indicates a 10-second timeout ceiling, not measured work

*VERIFIED · freeze · effort: small*

### FREEZE VERDICT: SYNAPSE does freeze Houdini today — Class 4 prompt-send grip is diagnosed, mapped, and entirely unrepaired

**Claim.** The unbounded main-thread payload at main_thread.py:302 froze the artist's Houdini seven times on 2026-07-31 for up to 44.4 seconds AFTER the v5.40.1 fix shipped, and none of the five remediation items in the forensics ticket has any code at HEAD.

**Why it matters.** This is the artist-facing bug the whole review was called to answer, and the answer is that it is live. During ordinary panel chat, a turn that dispatches a cook-heavy or render tool locks the node graph for tens of seconds with no cap, no chunking, no cancel, and no automatic recovery. Anyone reading the commit log sees freeze work at HEAD and may reasonably assume it is handled; it is not. Worse, freeze_chain.py:154-158 logs 'No live SynapseServer breaker to open' and :171-173 skips the emergency halt, so escalation collects evidence and does nothing else.

**Action.** ENGINEERING (large, needs a design call): timebox or chunk the cook-heavy handlers — roughly 21 `cook(force=True)` sites plus execute_python. But do the instrument gap FIRST (see freeze-fix-unverifiable), because handlers_render.py:109-113 states plainly that nothing in Python can interrupt the main thread from the main thread, so this is architecture rather than a patch and will need measurement to steer it.

**Evidence.**

- RE-VERIFIED IN THIS PASS — `grep 'Main thread recovered' ~/.synapse/logs/synapse.log | grep '2026-07-31'` returns seven heartbeat-derived freezes: 11:25:53 (10.3s), 12:04:52 (25.8s), 12:07:43 (21.1s), 12:41:49 (44.4s, 'post-escalation: resetting breaker'), 12:51:03 (24.3s), 12:51:26 (23.2s), 12:51:49 (23.1s). Freeze counts by date: 34 on 07-28, 32 on 07-29, 14 on 07-31.
- THE CONTROL THAT MAKES THIS LOAD-BEARING, re-verified: PR #50 (the Class 3 fix) merged d15d9b2 on 2026-07-30; v5.40.1 released 293484c 2026-07-31 08:48. `grep marshal_guard ~/.synapse/logs/synapse.log | awk '{print $1}' | uniq -c` → 21 records on 2026-07-28, 4 on 2026-07-29, and ZERO on every date after. The Class 3 instrument went silent while the freezes continued — so the old mechanism was dead
- MECHANISM RE-READ IN SOURCE THIS PASS — python/synapse/server/main_thread.py:290-311: `_record_dispatch_wait(...)` at :296 times the queue wait, then `result_holder[0] = fn()` at :302 runs with no surrounding perf_counter and no bound; `done.wait(timeout=timeout)` at :311 bounds only the CALLER's wait, not the payload.
- PYTEST-POLLUTION CONTROL RUN IN THIS PASS (run rule 5): all pytest-marked lines on 2026-07-31 are timestamped 21:46; `grep '2026-07-31 1[12]:' | grep -c pytest-of-User` → 0. The 11:25–12:51 freeze window is clean production evidence.
- freeze_dump_20260731_164134.json self-reports `synapse_version: 5.40.1`, `is_frozen: true`, `escalated: true`, `total_heartbeats: 6713` — a real ~2h session — AND `main_thread_direct: {count: 0}`, proving run_on_main Fast path 2 (the Class 3 mechanism) never fired during the freeze.

*VERIFIED · freeze · effort: large*

### Main-thread grip is unmeasured on the exact path the Class 3 fix created — no Class 4 fix can be proven to work

**Claim.** The deferred payload's duration is never timed, and marshal_guard's read surfaces have zero production callers and are absent from the freeze dump, so the quantity any Class 4 remediation would improve is not recorded anywhere.

**Why it matters.** This is the meta-finding and it explains why three days of freeze investigation produced a thorough map and zero repair. The Class 3 fix correctly moved callers off the main thread — which moved every payload onto the one path with no duration instrument. The only sink built to observe long inline main-thread payloads is write-only in production and missing from the artifact forensics reads first. This should be fixed BEFORE the Class 4 remediation, not after, or the remediation ships unverifiable.

**Action.** ENGINEERING (small): wrap `fn()` at main_thread.py:302 in a perf_counter pair feeding a third histogram (deferred-payload duration); add `marshal_guard.guard_stats()` plus a bounded slice of `guard_events()` to `collect_telemetry()` at telemetry_dump.py:107-163; and drop the count > 0 guard in metrics.py so the panel-inline series always exports with zero rather than vanishing.

**Evidence.**

- RE-VERIFIED IN THIS PASS — `grep -rn 'guard_stats\|guard_events' python/ shared/ mcp_server.py mcp_tools_*.py` excluding definitions returns ZERO production callers.
- RE-VERIFIED IN THIS PASS — `grep -n marshal_guard python/synapse/server/telemetry_dump.py` → ABSENT. Lane C leg 1 confirmed empirically that freeze_dump_20260731_164134.json's keys are ['dispatch_waits','freeze','live_metrics_latest','main_thread_direct','pid','reason','scene_hash','synapse_version','tool_durations','ts'] with no marshal_guard key.
- python/synapse/server/main_thread.py:296 records the queue wait immediately above :302's untimed `fn()` — the instrument sits adjacent to the defect and misses it. The module's own comment at :94-97 documents the intended split (wait on the worker path, duration on the main thread) but the duration sink `_record_main_thread_direct` is wired only into Fast path 2, never into `_on_main`.
- Consequence visible in the data: freeze_dump_20260731_164134.json `dispatch_waits.max_ms = 24927.68` over 3262 samples is one caller's queue wait — the shadow of an occupied main thread, not a measurement of the payload occupying it.
- Lane B lane 2 found the same gap from the live side: `synapse_panel_inline_ms` and `synapse_panel_inline_slow_total` are declared in metrics.py:174-182 but appear in none of three live Prometheus scrapes, because the exporter is guarded on count > 0 — so an unexercised path is indistinguishable from a dead recorder.

*VERIFIED · freeze · effort: small*

### A harness check reports GREEN over a live PDG defect it structurally cannot see

**Claim.** harness/verify/checks.py:1557 tests for the literal string `dirtyAllTasks(remove_files=True)`, but shared/bridge.py:1718 passes a variable, so the substring never matches and check_farm_headless returns ok:true with detail 'no reachable dirtyAllTasks(remove_files=True)' while the R8 PDG failure rollback raises TypeError on every invocation.

**Why it matters.** This is the purest silent-risk item in the report: a guard that is structurally incapable of seeing the thing it exists to see, producing a green board entry an operator will read as clearance. When a farm or TOPS cook fails through the bridge the artist is told the tasks were dirtied for recook; they were not, and a retry recooks against stale, undirtied work items reusing bad caches. The same literal-substring fragility likely applies to other _read_src-based checks in the same file.

**Action.** ENGINEERING (small): replace the literal fingerprint with a regex or AST match (`dirtyAllTasks\s*\(\s*remove_files\s*=`), rename the kwarg to `remove_outputs` and migrate to `hou.TopNode.dirtyAllWorkItems`, then probe it live once under hython before claiming the rollback works. Audit the other _read_src checks in harness/verify/checks.py for the same false-green class.

**Evidence.**

- RE-VERIFIED IN THIS PASS — shared/bridge.py:1716-1723 reads `lambda: top_node.dirtyAllTasks(remove_files=remove_files)` wrapped in `except Exception as _rb_exc: rollback_note = f" Rollback (dirtyAllTasks) failed: {_rb_exc}."` — the failure is recorded, not rolled back.
- RE-VERIFIED IN THIS PASS — harness/verify/checks.py:1557 `if bridge_src and "dirtyAllTasks(remove_files=True)" in bridge_src:` and :1568 the green detail string; `grep -c 'dirtyAllTasks(remove_files=True)' shared/bridge.py` → 0. The fingerprint cannot match the live call.
- Live signature from the repo's own probe, harness/notes/h22_compat_ledger.json:197 — 'The live 22.0.368 signature is dirtyAllTasks(self, remove_outputs). Keywords ARE accepted but only under the real name, so this raises TypeError on EVERY invocation ... Settled by inspect.Signature.bind - nothing was invoked.' Corroborated by h22_compat_ledger_v2.json:102 reading the build-shipped hom.zip, which 
- Reachability: shared/bridge.py:1350-1351 routes `cook_pdg_chain` to `_execute_pdg_deferred`, and panel/bridge_adapter.py:110-132 maps tops_batch_cook / tops_cook_and_validate / tops_multi_shot / cops_batch_cook onto it.
- CLAUDE.md §1.7 already documents the defect in prose ('This rollback has never executed') — the new finding is that the guard written to catch it is a false green.

*VERIFIED · risk · effort: small*

### Four branches carrying finished, verified work exist only on this disk

**Claim.** fix/corpus-usdrender-rop (14 commits), clear/l5-phantom-scanner (the L5 phantom scanner plus the P5.1 proposal), feat/panel-ux-pass and wip/panel-goalposts (1,130 lines of panel tests) have no ref on origin, and several live in .claude/worktrees/ where a prune destroys them.

**Why it matters.** The phantom sweep's entire round-2 corpus repair and the L5 scanner extension both evaporate on a `git worktree prune -f` or a branch delete, and this repository has already lost-and-recovered work in exactly this way once. Pushing is backup, not promotion — it does not pre-empt any ratification gate.

**Action.** HUMAN GATE (trivial, four commands): `git push -u origin` each of the four branches before any further worktree or branch cleanup. This is the single cheapest risk reduction in the report.

**Evidence.**

- RE-VERIFIED IN THIS PASS — a loop over `git show-ref --verify refs/remotes/origin/<b>` returns LOCAL-ONLY for all four: fix/corpus-usdrender-rop (96b3978), clear/l5-phantom-scanner (eb1e110), feat/panel-ux-pass (0d27a17), wip/panel-goalposts (c3a6032).
- The corpus branch is the fix for a documented failure class: `git grep -c -P 'usdrender(?!_rop)' master -- rag/skills/houdini21-reference` → 56 bare-phantom lines across 14 files; the same grep on the branch → 13 lines across 9 files.
- `git log --all --oneline -- harness/clear/PROPOSED-P5.1.md` → only eb1e110: the P5.1 proposal exists on that one unpushed branch and nowhere else. `git diff --shortstat master...clear/l5-phantom-scanner` → 3 files, 277 insertions.
- PRIOR BURN, SAME CLASS, recorded in harness/legs.json leg V0: 'archive/retina-m2-orphan carries 1,966 lines on no other branch - found in a workflow worktree nothing was backing up, preserved minutes before pruning.' `git worktree list` shows 18 live worktrees under .claude/worktrees/.
- CONVERGENT DISCOVERY — found independently by two Lane A modalities (declared-harness-state and version-control-surface) using different methods, then re-verified here.

*VERIFIED · risk · effort: trivial*


---

## HIGH

### The 289-item decisions board has no closure mechanism; verified false-opens are sitting on it

**Claim.** harness/decisions.py collects receipt for_ruling[] entries but has no resolved/closed/retired concept, so items whose work has demonstrably landed remain counted as open — I verified three.

**Why it matters.** The board is the harness's answer to 'what is waiting on a human'. If an unknown fraction of 289 is already done, every triage sitting starts by re-reading resolved items, which is exactly the ATTENTION bottleneck decisions.py:24-30 says it exists to fix. It also makes the count monotonically increasing — the board can never go down, which SPEC.md:38 names as a falsification condition for the CLEAR harness ('The board count goes UP after a run ... the harness is net-producing work').

**Action.** ENGINEERING (small-medium): add a per-item resolution channel — either a `resolved` / `resolved_by` field on receipt `for_ruling[]` entries that collect() filters out, or a `harness/state/resolved.json` keyed by (leg, text-hash) that decisions.py subtracts. Then do one sweep pass to retire the already-landed items. Do NOT hand-edit DECISIONS.md; it is derived.

**Evidence.**

- harness/decisions.py:115-160 — collect() appends every `for_ruling` entry unconditionally: `for fr in (d.get("for_ruling") or []): items.append({"kind": "ruling", ...})`. grep for resolved|closed|retire|dismiss|answered in the file returns only line 71 (`GREEN = {"green","pass",...}`, a receipt-status set) — no per-item closure path.
- FALSE-OPEN 1 — harness/state/DECISIONS.md:47 still lists ruling L3 'Three panel affordances lie to the artist ... gate Approve/Re[ject]'. But the fix HAS landed: python/synapse/panel/gate_widget.py:513-514 docstring reads 'marked decided and ``decision_announced`` is NOT emitted. A consent gate that reports success on a swallowed exception is worse than no gate', with the emits now guarded at :521
- FALSE-OPEN 2 — DECISIONS.md:31 still lists 'Root hygiene: delete the 8 delete-classed TRACKED dirs (_solaris_fix/, SYNAPSE-asm-* x4, SYNAPSE-fx-* x3 = 11 tracked files)'. Command: `git ls-files | grep -c '^_solaris_fix/\|^SYNAPSE-asm-\|^SYNAPSE-fx-'` -> `0`.
- FALSE-OPEN 3 — DECISIONS.md:33 still lists 'docs/*.txt - 15 untracked scratch files, zero tracked. Remove and broaden the ignore rule?'. Commands: `git ls-files docs/ | grep -c '\.txt$'` -> `0` tracked; `git check-ignore docs/*.txt | wc -l` -> `48` ignored. The ignore rule was already broadened.
- harness/state/DECISIONS.md:3 — 'Generated 2026-07-31 09:32 by `harness/decisions.py`. Do not hand-edit - it is derived.' — so the only way to retire an item is to edit the source receipt JSON in harness/notes/receipts/.

*VERIFIED · hygiene · effort: medium*

### CLEAR's 3 remaining FAILs are human gates whose PASS routes require writing agent-forbidden files

**Claim.** P2.1, P3.4 and P3.5 all FAIL, and every branch of their OR-conditions terminates in DECISIONS.md (derived, do-not-hand-edit) or flywheel_queue.json (deny-list fence, ratified is human-only) — so no amount of engineering clears them.

**Why it matters.** The CLEAR harness's own LOG.md:17 reports '5 PASS / 3 FAIL ... remaining 3 = human gates'. That is accurate, but the framing understates it: two of the three (P3.4, P3.5) have an 'OR a deferral entry' escape hatch that reads like agent-clearable work and is not. Any future run that tries to clear them will burn a cycle discovering the fence.

**Action.** HUMAN GATE (trivial each, ~10 minutes total for Joe): (1) flip or explicitly defer flywheel cycle C.0; (2) add a husk-render-cure park entry to flywheel_queue.json citing the Indie block; (3) either write docs/reviews/synapse-latency-report-2026-07-27-addendum.md or record a 'latency addendum gated, deferred' entry. ENGINEERING follow-up (trivial): P3.4/P3.5's OR-branches should point at a file an agent CAN write, or SPEC should say plainly they are human-only.

**Evidence.**

- P2.1 FAIL — harness/clear/verify.py:127-152 requires flywheel cycle C.0 to have `ratified: true` or `deferred`. Live read of harness/state/flywheel_queue.json: C.0 is `status='candidate' ratified=False`, title 'Context-capability truth: per-Houdini-context (SOP/LOP/COP/TOP/DOP/MAT) create-capability probe...'. flywheel_queue.json _doc: 'ratified is flipped by a HUMAN only (anti-runaway anchor...)'
- P3.4 FAIL — reproduced verify.py:92-97 `_husk_deferral_present()` exactly in-process: `husk present: True` but `re.search(r"\b(park|defer|indie)\b", hay, re.I)` -> `False`. The only husk hits are the unrelated cycle `C.8-H22-husk-resume` (DECISIONS.md:20). verify.py:93-95 comment: 'A husk deferral must live in the board substrate, not only the harness's own DEADENDS.md'.
- P3.5 FAIL — `docs/reviews/synapse-latency-report-2026-07-27-addendum.md` ABSENT (test -f -> ADDENDUM ABSENT); and reproduced verify.py:215-217 in-process: `"latency" in hay.lower()` -> `False`. The word 'latency' appears nowhere in DECISIONS.md + flywheel_queue.json, so the deferral branch cannot match either.
- harness/clear/DEADENDS.md:20-24 pre-registers 'latency-report-direct-edit' as REJECTED: 'Joe's gate. The report is checked-in and gated. Flag only; do not edit without Joe.'
- harness/state/DECISIONS.md:28 — ruling L0: 'L1 gap-closure is gate-REFUSED: flywheel_queue.json C.0 is ratified:false, and that file sits inside the deny-list fence.'

*VERIFIED · unfinished-work · effort: trivial*

### Two unmerged branches carrying finished work are LOCAL-ONLY with no origin backup

**Claim.** clear/l5-phantom-scanner (the L5 phantom scanner + the P5.1 proposal) and fix/corpus-usdrender-rop (14 corpus commits) exist only in this working copy — no origin ref — and both sit in .claude/worktrees/ where a prune destroys them.

**Why it matters.** The phantom sweep's entire round-2 corpus repair ('claim now true: no corpus file teaches the usdrender node type', harness/phantoms/LOG.md row FIX-R2) and the L5 scanner extension both evaporate on a `git worktree prune -f` or a branch delete. The repo has already lost-and-recovered work this exact way once.

**Action.** HUMAN GATE (trivial — Gate C is human by SPEC.md:27): `git push -u origin clear/l5-phantom-scanner` and `git push -u origin fix/corpus-usdrender-rop`, before any merge decision. Pushing is backup, not promotion; it does not pre-empt the ratification gates below.

**Evidence.**

- Loop over `git branch --no-merged master`, testing `git show-ref --verify refs/remotes/origin/<b>`: `LOCAL-ONLY clear/l5-phantom-scanner (eb1e110 feat(verify): extend phantom lint to pdg/pxr (CLEAR L5 G2))`; `LOCAL-ONLY fix/corpus-usdrender-rop (96b3978 fix(corpus): karma_rendering_guide.md round-2 usdrender residue)`. Also local-only: feat/panel-ux-pass, forge/scout-opportunities, wip/panel-goalp
- `git diff --shortstat master...clear/l5-phantom-scanner` -> '3 files changed, 277 insertions(+), 4 deletions(-)'. `git log --all --oneline -- harness/clear/PROPOSED-P5.1.md` -> only `eb1e110` — the P5.1 proposal exists on that one unpushed branch and nowhere else.
- `git log --oneline master..fix/corpus-usdrender-rop` -> 14 commits (c15e906..96b3978), `13 files changed, 50 insertions(+), 50 deletions(-)`.
- `git worktree list` -> 18 worktrees live under C:/Users/User/SYNAPSE/.claude/worktrees/, including clear-l5-phantom-scanner and phantom-corpus-fix.
- Prior burn, same class, recorded in harness/legs.json leg V0: 'archive/retina-m2-orphan carries 1,966 lines on no other branch - found in a workflow worktree nothing was backing up, preserved minutes before pruning.'

*VERIFIED · risk · effort: trivial*

### PHANTOM SWEEP: SPEC unratified, 35-file corpus fix unmerged, 6 quarantine entries await Joe, digest rebuild queued

**Claim.** The PHANTOM SWEEP harness completed two fix rounds with SOUND crucible verdicts but every one of its exit gates is still shut — SPEC is PROPOSED, the fix branch is unmerged, rulebook/phantoms.json is unpopulated, and the content_digest rebuild is unstarted.

**Why it matters.** CLAUDE.md Safety Rule 15 names phantom APIs as SYNAPSE's #1 failure class, and the rulebook discipline section says 'Never reference a quarantined symbol; the phantom lint fails CI.' Right now the corpus fix that makes the claim true is unmerged, and the six quarantine facts that would make the lint enforce it live only in a markdown packet. The gap between 'proven' and 'enforced' is entirely human-gate width.

**Action.** HUMAN GATE (small, one sitting): ratify harness/phantoms/SPEC.md; populate the 6 draft rows (+ usdrender) into rulebook/phantoms.json; merge fix/corpus-usdrender-rop. Then ENGINEERING (small): the queued content_digest rebuild, and a decision on the 25 UNCLASSIFIED cap-swallowed hits.

**Evidence.**

- harness/phantoms/SPEC.md:3 — '*PROPOSED — awaits Joe's ratification, same discipline as CLEAR's SPEC.*'
- harness/phantoms/LOG.md (FIX-R2 row) — 'claim now true: no corpus file teaches the usdrender node type; **merge = Joe's gate**; content_digest rebuild queued as follow-up'
- harness/phantoms/QUARANTINE-PACKET-2026-07-31.md:3 — 'Nothing in this file has been ratified by Joe. Proposed `rulebook/phantoms.json` entries are populated by Joe, never by the harness. The L5 merge is **not authorized** by this document.'
- QUARANTINE-PACKET §1 — 6 candidates, two independent assays, '6/6 quarantine holds — all ABSENT' (pdg.PyEventCallback, hou.cookPDGGraph, hou.pdg.scheduler, hou.pdg.workItem, hou.pdg.GraphContext, hou.pdg.cookWorkItems), with draft JSON rows written out for Joe to copy.
- QUARANTINE-PACKET §1 adjacent note — 'rulebook/phantoms.json contains **no `usdrender` entry** today — the phantom verdict rests on the H21.0.671 recon memory only ... Consider ratifying `usdrender` alongside the corpus fix.'

*VERIFIED · unfinished-work · effort: small*

### Master publishes a self-refuted Tier-1 figure; the correction sits uncommitted in a worktree

**Claim.** harness/notes/forensic/S2_PREMORTEM.md on master still asserts '95 of the 228 palette rows (41.7%) send an English description to the model instead of dispatching' at lines 185 and 808, while the uncommitted copy in .claude/worktrees/s2-forensic corrects it to 21/228 (9.2%) and states the correction 'cuts a Tier-1 headline by 4.5x'.

**Why it matters.** This repo has already been burned by a control pinned to a document's own wrong figure. Here the wrong figure is the committed one and the evidence-backed correction is the uncommitted one, so anyone citing S2_PREMORTEM.md from git cites a number its own author refuted.

**Action.** Read the 239-line delta in .claude/worktrees/s2-forensic and decide commit-vs-discard. Do not prune that worktree until the decision is made.

**Evidence.**

- git grep -n '41.7%' master -- harness/notes/forensic/S2_PREMORTEM.md -> 'master:...:185:**95 of the 228 palette rows (41.7%) send an English description...' and ':808:| 5 | **95 of 228 palette rows (41.7%) send prose, not dispatch**'
- diff master vs .claude/worktrees/s2-forensic/harness/notes/forensic/S2_PREMORTEM.md -> 239 lines only in worktree, 68 only in master; worktree text: '**21 of the 228 palette rows (9.2%)** ... > **Corrected by the adversarial pass, and the correction cuts a Tier-1 headline by 4.5x.**'
- mtimes: worktree S2_PREMORTEM.md 2026-07-27 15:50:34, S2.json 15:51:17; master's last commit for both = 83a4820 2026-07-27 15:36:40 -> the worktree copy is the later state
- master S2.json status_reason: 'Adversarial pass DISPATCHED (3 hostile lenses) - see for_ruling R-S2-1 for its disposition.' vs worktree S2.json: 'ADVERSARIAL PASS RAN - 3 hostile lenses ... ALL 14 are APPLIED ... four numbers broken and corrected'

*VERIFIED · unfinished-work · effort: small*

### R8 PDG failure rollback still raises TypeError on every invocation at HEAD

**Claim.** shared/bridge.py:1718 calls top_node.dirtyAllTasks(remove_files=remove_files) while the live H22.0.368 signature is dirtyAllTasks(self, remove_outputs), so the call raises TypeError, is swallowed at :1722, and the R8 PDG failure-recovery rollback has never executed — unchanged on HEAD f427320.

**Why it matters.** When a farm/TOPS cook fails through the bridge, the artist is told the tasks were dirtied for recook. They were not. A retry recooks against stale, undirtied work items and silently reuses bad caches — the failure is recorded, not recovered. The successor API (dirtyAllWorkItems) also takes remove_outputs, so the fix is a one-word rename plus a live probe.

**Action.** Rename the kwarg to remove_outputs and migrate to hou.TopNode.dirtyAllWorkItems, then probe it live once under hython before claiming the rollback works. Do not cite PDG dirty-propagation as functional until that probe exists. Track: harness/state/DECISIONS.md:122 already carries the open ruling.

**Evidence.**

- shared/bridge.py:1716-1723 — `await _marshal_await(_rom, lambda: top_node.dirtyAllTasks(remove_files=remove_files), 30.0,); dirtied = True; except Exception as _rb_exc: rollback_note = f" Rollback (dirtyAllTasks) failed: {_rb_exc}."`
- harness/notes/h22_compat_ledger.json:197 (repo's own live probe) — "shared/bridge.py:1718 calls top_node.dirtyAllTasks(remove_files=remove_files). The live 22.0.368 signature is dirtyAllTasks(self, remove_outputs). Keywords ARE accepted but only under the real name, so this raises TypeError on EVERY invocation ... Settled by inspect.Signature.bind - nothing was invoked."
- harness/notes/h22_compat_ledger_v2.json:102 — hom.zip reader returns `dirtyAllTasks(self, remove_outputs)` plus verbatim deprecation notice 'This method is deprecated in favor of [Hom:hou.TopNode#dirtyAllWorkItems].'
- Reachability: shared/bridge.py:1350-1351 — `if operation.operation_type == "cook_pdg_chain": return await self._execute_pdg_deferred(operation, integrity)`; python/synapse/panel/bridge_adapter.py:110-132 maps tops_batch_cook / tops_cook_and_validate / tops_multi_shot / cops_batch_cook onto cook_pdg_chain
- git log --oneline -3 -- shared/bridge.py → 607fc73, baaf371, b26372c (no fix since the defect was documented in docs/RELEASE_NOTES_v5.35.0.md:86)

*VERIFIED · unfinished-work · effort: small*

### The harness check guarding the PDG rollback defect is a literal-string fingerprint that cannot match the live call

**Claim.** harness/verify/checks.py:1557 tests `if "dirtyAllTasks(remove_files=True)" in bridge_src`, but bridge.py:1718 passes a variable (`remove_files=remove_files`), so the substring is absent and check_farm_headless returns ok:true with detail "no reachable dirtyAllTasks(remove_files=True)" while the defect is live.

**Why it matters.** This is a guard that structurally cannot see the thing it exists to see. It is worse than no guard: it produces a green board entry that an operator will read as clearance. The same fragility applies to any other check in checks.py that fingerprints source by exact-literal substring.

**Action.** Replace the literal-substring fingerprint with an AST or regex match on the call site (`dirtyAllTasks\s*\(\s*remove_files\s*=`), and audit the other _read_src-based checks in harness/verify/checks.py for the same class of false-green.

**Evidence.**

- harness/verify/checks.py:1556-1559 — `bridge_src, _ = _read_src(ctx, "shared/bridge.py")` then `if bridge_src and "dirtyAllTasks(remove_files=True)" in bridge_src:`
- harness/verify/checks.py:1568-1569 — green detail string: "no reachable dirtyAllTasks(remove_files=True); scout version check enforced in external processes"
- `grep -c "dirtyAllTasks(remove_files=True)" shared/bridge.py` → `0` (verified on HEAD)
- harness/notes/forensic/S3_PLAN.md:489-494 — repo's own S2 forensic already flagged it: "farm_headless passes on a literal-string fingerprint (checks.py:1557 ...) while the live call reaches the same defect through a variable (shared/bridge.py:1718) — a fingerprint artefact, not a clearance ... Both re-read at HEAD and still current"

*VERIFIED · risk · effort: small*

### CLAIM PARTLY WRONG: the mcp list_tools breakage is fixed; only the 'CI is red' half survives

**Claim.** The mcp==1.26.0 pin from 9c8fe87 is present and effective — the collection error at mcp_server.py:899 and the 2 test failures are gone from CI, which now reports 5255 passed with a single unrelated failure.

**Why it matters.** A stale 'the mcp library broke us' note sends someone to re-pin or migrate the decorator API that is already pinned and working, while the actual red stays.

**Action.** Retire the mcp-drop item from the open list; keep only the pyproject.toml:53 relaxation note (migrate mcp_server.py:899/:956 to the new decorator API before unpinning). Note the pin is a conservative known-good, not a probed last-good boundary — the commit message says so itself.

**Evidence.**

- pyproject.toml:59 `"mcp==1.26.0",` inside the `[project.optional-dependencies].mcp` extra, with the drop documented at pyproject.toml:53
- mcp_server.py:899 is exactly `@server.list_tools()` (and :956 `@server.call_tool()`) — line numbers in the memory are accurate
- Live probe: `mcp version: 1.26.0` / `Server.list_tools: True` / `Server.call_tool: True`
- .github/workflows/ci.yml:44 `- run: pip install -e ".[dev,websocket,mcp]"` — the pinned extra is the one CI installs
- CI log for HEAD shows no collection error: `1 failed, 5255 passed, 196 skipped`

*VERIFIED · unfinished-work · effort: trivial*

### CLAIM WRONG: PR #48 and PR #46 are both merged, and B1/B2/B5 are fixed

**Claim.** PR #48 (solaris harden) merged 2026-07-22 and PR #46 (rulebook + H22 proof leg) merged 2026-07-17; three of the five named B-blockers are verifiably repaired in the tree at HEAD.

**Why it matters.** Two 'needs Joe's merge' items have been merged for 10-15 days. Chasing a merge that already happened is pure waste, and it makes the rest of the memory less trustworthy.

**Action.** Close claims 2 and 3 outright. Re-audit only B3 and B4 (merge-input overwrite; build_graph non-idempotency) — I did not verify those two either way.

**Evidence.**

- `gh pr list --state all` -> #48 `{"state":"MERGED","mergedAt":"2026-07-22T12:25:20Z","title":"feat(harness): codify the Solaris hardening pipeline — seam-gate, runner, spine"}`
- `gh pr list --state all` -> #46 `{"state":"MERGED","mergedAt":"2026-07-17T15:26:38Z","title":"docs: H22 per-context post-mortem — coverage-honesty map + per-context blueprints"}`
- B1 source of truth docs/reviews/solaris-wiring-gap-ledger-2026-07-21.md:65 claims `.get(type_name, 800)` collides with usdrender_rop 800; at HEAD python/synapse/server/handlers_solaris_assemble.py:134 `_UNRANKED_RANK = 690` and :191 `return _SOLARIS_NODE_ORDER.get(_base_type_name(node), _UNRANKED_RANK)` — 690 < the `"usdrender_rop": 800` at :113. FIXED.
- B2 claimed `grep -c undos handlers_solaris_assemble.py -> 0`; at HEAD the same grep returns `8`. FIXED.
- B5 claimed `grep known_absent|lop_knowledge|node_type_exists python/synapse/server/` was empty; at HEAD python/synapse/server/handlers_solaris_graph.py:58 `entry = (content.get("known_absent") or {}).get(type_name)` and :51 `from ..core.lop_knowledge import load_lop_catalog`. FIXED.

*VERIFIED · unfinished-work · effort: trivial*

### U7's first gate condition (read-mix p95 > 5ms) is already met by 406x; the gate survives only on its second condition

**Claim.** The U7 hwebserver-migration gate is an AND of two numeric conditions; condition 1 (read-mix p95 > 5 ms) is satisfied at ~2030 ms by the 2026-07-27 sweep, while condition 2 (a fresh hwebserver A/B re-measuring its ~2070 ms ping floor as < 5 ms) has never been run on H22 — so the item stays parked, but for only one of its two stated reasons.

**Why it matters.** The lane brief warned that an item whose gate number is already met is silently actionable. Half of U7's AND is now demonstrably satisfied by a 406x margin — a fact the report does not carry. Anyone re-reading the gate as 'nothing has moved' is wrong.

**Action.** Record that U7 condition 1 is met and condition 2 is untested on H22. Note the producer caveat honestly: the gate names `_benchmark_latency.py` as its producer and my figure comes from the S1 sweep, a different instrument — so re-run the named producer before treating the gate as formally tripped.

**Evidence.**

- Exact park condition, LATENCY_PLAN.md:297-301: "build ONLY if `_benchmark_latency.py` p95 for the read mix (ping, get_health, get_scene_info, get_selection, context) exceeds **5 ms** over a real session AND a fresh hwebserver A/B re-measures its prior ~2070 ms ping floor (2026-02-08 table) as below 5 ms."
- Condition 1 measured: ws_readonly_sweep.json read-mix members — synapse_ping 2.06s, synapse_health 2.01s, houdini_scene_info 2.01s, houdini_get_selection 2.01s, synapse_context 2.02s. Overall sweep p95 = 2.03s = 2030 ms vs a 5 ms threshold.
- Condition 2 unmet: no hwebserver A/B artifact exists on H22. The only A/B is LATENCY_PLAN.md:193-199, dated 2026-02-08, on H21.
- Report's own status line, docs/reviews/synapse-latency-report-2026-07-27.md:80: "Leave U5/U6/U7 parked behind their numeric reopen-gates; re-state the U6 anchor first."

*INFERRED · latency · effort: small*

### The report's biggest open lever is mis-scoped as handler work; the declarative mechanism is already domain-agnostic

**Claim.** Section 5 item 3 frames extending declarative coverage to COPs/TOPS as new build work, but propose_graph/instantiate_graph are already fully context-agnostic — the only gap is system-prompt steering, making the highest-seconds-saved lever a small change rather than a large one.

**Why it matters.** The report calls this 'the only lever that removes whole seconds per item' and implies per-domain engineering. If the mechanism already generalizes, the work is prompt surgery — a cheap win currently priced as an expensive one, which is exactly how high-value items get deferred.

**Action.** Re-scope item 3 from 'build declarative coverage for COPs/TOPS' to 'steer the model to the existing generic propose_graph/instantiate_graph, and REMOVE the four conflicting system_prompt rules identified at LATENCY_SOLARIS_REVIEW.md:230'. Validate with a COPs build over the generic path before writing any new handler.

**Evidence.**

- python/synapse/host/graph_builder.py:131-140 — `parent = hou.node(proposal.parent_path)` then `parent.createNode(n.node_type, n.friendly_name or None)`. Nothing Solaris-specific in the instantiation core.
- python/synapse/host/graph_oracle.py:34 — `cat = hou.nodeTypeCategories().get(category)`; the category is a parameter, resolving Cop2/Top/Sop/Lop alike.
- python/synapse/host/graph_oracle.py:28 — `_TYPED_CATEGORIES = frozenset({"Vop", "Chop", "Shop"})` is used only by `is_typed_category` for wire type-checking (:70-71), NOT as a whitelist.
- Steering gap: `grep propose_graph|solaris_build_graph python/synapse/panel/system_prompt.py` -> solaris_build_graph at :81, :85, :132, :187 and synapse_batch at :78; propose_graph appears ZERO times.
- No per-domain declarative tools exist: `grep cops_build_graph|tops_build_graph|cops_propose|tops_propose python/synapse/ --include=*.py` returns empty; the registry has only synapse_solaris_assemble_chain (:679), synapse_solaris_build_graph (:700), synapse_solaris_scene_template (:776), plus generic synapse_propose_graph (:1288) / synapse_instantiate_graph (:1300).

*VERIFIED · unfinished-work · effort: small*

### Section 5 item 1 (the live re-measure) has never been run and is unblocked for the first time

**Claim.** The report's number-one action — bring the bridge up and run the Section 7 re-measure — remains un-run, evidenced by an idle live session with zero commands and no tool durations, while the bridge is confirmed reachable for this run.

**Why it matters.** Every open item in the report is gated on this one measurement, and the 2.01s floor finding above makes it materially more valuable than the report anticipated — the re-measure as specified would still miss the floor, because all six of its steps read in-process histograms.

**Action.** Run the Section 7 sequence, but add a step 0: record client-observed wall time per call alongside the histograms. Without that outer span the re-measure will report single-digit milliseconds and confirm the wrong conclusion. Also reconcile the 22.0.368 vs 22.0.397 baseline before tagging any number H22.

**Evidence.**

- ~/.synapse/logs/telemetry.json (mtime 2026-08-01 10:05:03, synapse_version 5.41.0, reason "periodic"): `"tool_durations": {}`, `"session": {"total_commands": 0, "commands_per_minute": 0.0}`, `"routing": {"total_requests": 0, "avg_latency_ms": 0.0}`.
- Bridge reachability for this run confirmed by the dispatch brief: synapse_ping returned {"pong":true,"protocol_version":"4.0.0"}.
- Report item under test, docs/reviews/synapse-latency-report-2026-07-27.md:75: "**Bring the bridge up and run the 7-17 §7 re-measure** ... One session; resolves the only open measurement dispute on this engine."
- Report's own framing of the blocker, :7: "The §7-17 one-command live re-measure is **still owed** and remains the single highest-value next measurement."
- Baseline drift to check during the re-measure: telemetry.json `hip_file` = "C:/Program Files/Side Effects Software/Houdini 22.0.397/bin/untitled.hip", while the report's baseline line :3 states Houdini 22.0.368.

*VERIFIED · unfinished-work · effort: small*

### Every run_on_main dispatch waits ~53 ms before it starts; zero live samples under 50 ms

**Claim.** Enqueue-to-start wait for a main-thread marshal has a hard floor in the (50,100] ms band: across 106 dispatches captured live over 215.343 s, 0 were under 50 ms, 105 (99.06%) fell in (50,100] ms, 1 in (100,250] ms, mean 53.27 ms - measured while the main thread was idle.

**Why it matters.** Any tool that must touch hou.* from a worker thread pays >=50 ms before its own work starts. A 5-node build that marshals 5 times burns ~265 ms purely in queue sit. The latency authority (docs/reviews/synapse-latency-report-2026-07-27.md:19) records T3 as 'ms when main thread is free' - measured with a free main thread the floor is ~53 ms, an order of magnitude above that claim, so the tier model understates the fixed cost of every marshal.

**Action.** Correct the T3 row in the latency report with this measured floor, then determine whether hdefereval.executeDeferred is serviced by a fixed-interval pump. If so, evaluate a direct Qt queued-connection or a dedicated main-thread runnable for read-only marshals so short hou.* reads stop paying the pump interval.

**Evidence.**

- synapse_ping -> timestamp 1785592682.3777823 (anchor A)
- synapse_metrics @A -> synapse_dispatch_wait_ms_bucket{le="10"} 0 ; {le="50"} 53 ; {le="100"} 33802 ; _count 33821 ; _sum 1805113.8853
- synapse_ping -> timestamp 1785592897.720771 (anchor C)
- synapse_metrics @C -> synapse_dispatch_wait_ms_bucket{le="10"} 0 ; {le="50"} 53 ; {le="100"} 33907 ; _count 33927 ; _sum 1810760.8596
- Derived window A->C: dt=215.343 s, dcount=106, dsum=5646.974 ms -> mean 53.27 ms; d(le=50)=0, d(le=100)=105, d(le=250)=1

*VERIFIED · latency · effort: medium*

### The prompt-send GUI-grip path exports no telemetry - panel inline metrics are absent from every scrape

**Claim.** synapse_panel_inline_ms and synapse_panel_inline_slow_total are declared in metrics.py but appear in none of the three live scrapes, because the exporter is guarded on count > 0 and the panel inline recorder has zero samples. The exact path under freeze investigation is invisible in Prometheus.

**Why it matters.** The freeze under investigation is a panel prompt-send freeze. The one metric family that would attribute it - inline main-thread Qt tool dispatch duration and slow-op count, labelled with the slowest tool - emits nothing. Worse, the count>0 guard makes the series vanish rather than export zero, so an operator scraping the bridge cannot distinguish 'no panel activity' from 'instrumentation broken'. This blocks all future measurement of the actual bug.

**Action.** Drop the count>0 guard for panel_inline (and ideally for dispatch_wait, main_thread_direct, scene_hash) so the series always exports with 0. Absent series break rate() and make an unexercised path indistinguishable from a dead recorder.

**Evidence.**

- synapse_metrics (3 scrapes) -> no line matching synapse_panel_inline anywhere in the returned text
- C:/Users/User/SYNAPSE/python/synapse/server/metrics.py:174 if panel_inlines and panel_inlines.get("count", 0) > 0:
- C:/Users/User/SYNAPSE/python/synapse/server/metrics.py:176 synapse_panel_inline_ms HELP line (declared but unreachable at count 0)
- C:/Users/User/SYNAPSE/python/synapse/server/metrics.py:182 synapse_panel_inline_slow_total HELP line
- C:/Users/User/SYNAPSE/python/synapse/server/handlers.py:1565-1566 from ..panel.tool_executor import panel_inline_stats

*VERIFIED · missing-instrumentation · effort: trivial*

### synapse_router_stats errors out and all routing/tier latency metrics are absent

**Claim.** synapse_router_stats returns {"error":"Router not initialized"}, synapse_live_metrics reports routing.total_requests 0 / avg_latency_ms 0.0 / tier_counts [], and the four routing metric families declared in metrics.py never appear in the scrape. There is zero per-tier latency visibility on the live bridge.

**Why it matters.** Tier cascade routing is a documented latency lever, but on the live bridge it reports zero requests while the bridge is demonstrably serving traffic. You cannot tune routing you cannot see, and any future claim about tier distribution or per-tier latency has no live source to check against.

**Action.** Determine whether the router is genuinely never initialized in the in-Houdini deployment or whether the stats accessor is wired to a different instance. Until resolved, treat every routing/tier latency figure in the latency report as unmeasurable rather than as zero.

**Evidence.**

- synapse_router_stats -> {"error":"Router not initialized"}
- synapse_live_metrics -> "routing":{"avg_latency_ms":0.0,"cache_hit_rate":0.0,"cache_hits":0,"knowledge_entries":0,"tier_counts":[],"total_requests":0}
- synapse_metrics (3 scrapes) -> no synapse_tier_requests_total, no synapse_tier_latency_avg_ms, no synapse_routes_total, no synapse_commands_total
- C:/Users/User/SYNAPSE/python/synapse/server/metrics.py:60,68,75,82 declare exactly those four families behind conditionals

*VERIFIED · missing-instrumentation · effort: medium*

### A ~0.49 Hz background stream produces 33,927 main-thread dispatches and 30.2 minutes of cumulative queue wait

**Claim.** Main-thread dispatches accrue at 0.44-0.52 per second continuously, independent of tool traffic. Over the process lifetime that is 33,927 dispatches and 1,810,760.86 ms (30.2 min) of cumulative enqueue-to-start wait, while only 42 tool calls total are recorded in the per-tool histogram.

**Why it matters.** 33,927 marshals for 42 tool calls means background polling, not user work, owns the main-thread queue. Each one occupies the deferred-eval pump, and a user action arriving behind them inherits the ~53 ms floor at minimum. This is a continuous, permanently-on tax on GUI responsiveness.

**Action.** Identify the 0.49 Hz producer and confirm whether it is the 2 s panel context poll marshalling hou.* reads back on-main after commit d15d9b2 moved the gather off-thread. If so, coalesce or cache the reads so an idle panel does not enqueue ~43,000 marshals per day.

**Evidence.**

- Window A->C: dcount 106 over dt 215.343 s -> 0.4923 dispatches/s
- Window A->B: dcount 39 over dt 87.677 s (ping anchors 1785592682.3778 -> 1785592770.0548) -> 0.4449/s
- Window B->C: dcount 67 over dt 127.666 s -> 0.5248/s
- synapse_metrics @C -> synapse_dispatch_wait_ms_sum 1810760.8596 ; _count 33927
- synapse_metrics @C per-tool counts sum to 42 (doctor 3, execute_python 1, get_health 2, get_live_metrics 1, get_metrics 2, inspect_scene 1, ping 31, router_stats 1)

*VERIFIED · latency · effort: medium*

### Live bridge is 5.40.1 while repo HEAD is 5.41.0 - measurements predate the CLEAR L3 fixes

**Claim.** synapse_doctor reports the running tree as synapse 5.40.1 (and the install stamp as 5.23.0), while the repo VERSION, pyproject.toml and __init__.py all say 5.41.0. Every number in this lane therefore describes a bridge built before commits 9c9bc8e (P3.3 websocket cancel), 340db86 (P3.1) and 8dfa23d (v5.41.0).

**Why it matters.** Anyone reading these live numbers as the current state of master would be wrong. The bridge process was published 2026-07-31T18:40 UTC, before the v5.41.0 release commit, so the P3.3 mid-frame websocket cancel fix is not in the process that produced this dispatch-wait histogram. Re-measuring after a restart could move every figure here.

**Action.** Record the bridge build (5.40.1, pid 56116, published 2026-07-31T18:40:36Z) alongside any latency figure derived from this session, and re-run the measurement against a 5.41.0 bridge before treating the floor or the 17 s tail as current.

**Evidence.**

- synapse_doctor -> checks[version] status "fail", detail "synapse 5.40.1 / protocol 4.0.0; install stamp says 5.23.0 - installed tree and stamp disagree"
- cat VERSION -> 5.41.0
- pyproject.toml:7 version = "5.41.0"
- python/synapse/__init__.py:123 __version__ = "5.41.0"
- synapse_doctor -> checks[bridge_endpoint] detail "C:/Users/User/.synapse/bridge.json: ws://localhost:9999 (pid 56116, published 2026-07-31T18:40:36.561299+00:00)"

*VERIFIED · risk · effort: trivial*

### The executeDeferred wake floor is ~54 ms, not ~2 s — measured 33,920 times, and the data was already on disk

**Claim.** Every off-main-thread hou call pays ~54 ms of pure queue-sit latency before any Houdini work runs; this reproduces across two independent production sessions and no sample in either has ever completed in under 50 ms.

**Why it matters.** Two things flip on this number. First, the ~2 s wake-floor hypothesis (T1 / the disputed hwebserver dispatch floor) is refuted on H22 with a large sample, so effort parked behind that gate can be released. Second, 54 ms is now a hard unit price: any proposal that changes the number of off-main marshals per operation can be costed in milliseconds instead of argued about, which is what makes findings 2, 3 and 4 below actionable rather than speculative.

**Action.** Publish the number as the marshal unit cost and close the C6/T1 attribution item. Then stop overwriting the dataset (see telemetry-overwritten-per-session) and re-run the same read after a real mutating workload to get the busy-main tail, which this idle sample does not cover.

**Evidence.**

- Session A (pid 56116, v5.40.1, ~19.3 h uptime), C:/Users/User/.synapse/logs/telemetry.json read 2026-08-01 ~10:00 EDT: dispatch_waits count=33833, sum_ms=1805742.9986 -> mean 53.37 ms, max_ms=17167.1. Cumulative 'le' buckets: {1:0, 5:0, 10:0, 50:53, 100:33814, 250:33825, ...} => 33,761 samples (99.8%) fall in (50,100] ms and ZERO fall at or below 10 ms.
- Session B (pid 3696 = live `hindie`, v5.41.0 @ HEAD, 181 s uptime), same file re-read 2026-08-01 10:07 EDT after it rotated: dispatch_waits count=87, sum_ms=4716.7 -> mean 54.21 ms, max_ms=145.3. Buckets {1:0,5:0,10:0,50:0,100:86,250:87} => 86 of 87 in (50,100], zero at or below 50 ms. Two independent samples agree to within 1.6%.
- Producer path: python/synapse/server/main_thread.py:288 `t_enqueue = time.perf_counter()` -> :296 `_record_dispatch_wait((time.perf_counter() - t_enqueue) * 1000.0)` inside `_on_main`, i.e. the histogram times exactly enqueue -> callback-start, nothing else. Recorded at :309 `hdefereval.executeDeferred(_on_main)`.
- Not pytest pollution: telemetry.json is written only by `flush_telemetry(reason='periodic')` (python/synapse/server/telemetry_dump.py:200,219), whose flusher is started from `start_hwebserver` (python/synapse/server/hwebserver_adapter.py:288). Session B's pid 3696 is the live Houdini: `Get-Process -Id 3696` -> `3696 hindie 8/1/2026 10:03:07 AM`, matching ~/.synapse/bridge.json {"pid": 3696, "port"
- This directly answers the item docs/reviews/synapse-latency-report-2026-07-27.md §5.1 lists as the top open action ('pull synapse_metrics reading dispatch_wait and main_thread_direct together ... resolves the only open measurement dispute') and the hypothesis parked at python/synapse/server/main_thread.py:42-48 ('Buckets straddle the 2000 ms suspect so T1's signature (mass at/near 2000) is unmista

*VERIFIED · latency · effort: trivial*

### The live integrity envelope adds two ~54 ms marshals to every mutating command, inside the process-wide mutation lock, and hides them from the histogram that exists to attribute marshal cost

**Claim.** Every mutating /synapse command performs three main-thread round trips instead of one — the handler's own plus two observe-only scene-hash captures — costing roughly 108 ms extra at the measured wake floor, while both extra captures pass record_wait=False so they never appear in the dispatch-wait histogram.

**Why it matters.** This is the largest architecture-imposed, LLM-independent cost I can quantify. It roughly triples the marshal count of every mutating command (~108 ms added to a command whose own marshal is ~54 ms plus 1-70 ms of hou work), it is held inside the process-wide _MUTATION_LOCK so it extends the window during which every other mutating command from every client is blocked, and the instrument built to attribute marshal cost systematically under-reports mutating ops by 3x. A 10-node imperative build pays about 1.08 s of pure wake latency for provenance whose consent/composition/undo anchors are all recorded not-applicable.

**Action.** Decide the envelope's price knowingly rather than invisibly. Cheapest correct fix: reuse the previous operation's parked after-hash as this operation's before-hash (shared/bridge.py already parks hashes via _park_hash) to halve it to one marshal. Failing that, flip record_wait=True so the tax is at least visible, or default SYNAPSE_LIVE_ENVELOPE off on the live path. Do not move the captures outside the C5 lock — they must bracket the op.

**Evidence.**

- python/synapse/server/handlers.py:526-539: `with _lock_cm:` then `:528 _hash_before = _envelope.capture_scene_hash(command.payload)`, `:529 result = self._registry.invoke(...)`, `:539 _hash_after = _envelope.capture_scene_hash(command.payload)` — both captures are inside the C5 lock.
- python/synapse/server/integrity_envelope.py:218-223: `return run_on_main(lambda: bridge._compute_scene_hash(target, include_stage=False), timeout=_capture_timeout(), record_stall=False, record_wait=False)` — each capture is a full run_on_main round trip, and record_wait=False excludes it from _record_dispatch_wait.
- python/synapse/server/main_thread.py:295-296: `if record_wait: _record_dispatch_wait(...)` — confirms the exclusion is unconditional for these callers.
- Handlers themselves marshal exactly once: an indentation-scoped scan of every `run_on_main(` call site under python/synapse/server/ for an enclosing `for`/`while` at lower indent returned no hits. So the 3:1 ratio is entirely the envelope, not handler design.
- Corroboration that the envelope fires on the live path and that its hashes are cheap while its wakes are not: session A telemetry shows tool_durations with exactly one mutating command (execute_python, count=1) and scene_hash count=3, max_ms=0.088 — i.e. the hash COMPUTE is sub-millisecond; the cost is the two ~54 ms wakes, which are invisible in dispatch_waits (33,833 ≈ the 2 s metrics poll alone

*VERIFIED · latency · effort: medium*

### Scene hashing has been measured at over 4 seconds per call during a real freeze episode, and the bridge does two per operation

**Claim.** A production freeze dump records 44 scene-hash calls totalling 23.4 s (mean 532 ms, max 4305 ms), against an idle-scene baseline of 0.09 ms — so the R1 integrity hash is a multi-second cost under real conditions and is invoked twice per bridge operation.

**Why it matters.** This is the largest single per-operation cost I found evidence for, and it lands on the integrity path that runs on every bridge-routed mutation. On the panel path bridge.execute runs inline on the main thread, so a multi-second hash is a multi-second GUI freeze, not just added latency. It is also the one number here that no existing document cites — the 2026-07-27 latency report's T5 bin assumes provenance is 'ms class, deliberately kept off the hot path', which this dump contradicts.

**Action.** Attribute it before optimising: instrument the Flatten leg and the node.geometry() leg separately (both already sit inside one timed wrapper, so a second histogram is cheap), then decide between enabling the existing structural signature via SYNAPSE_STAGE_HASH_PRIM_THRESHOLD and reusing the parked after-hash as the next before-hash. I could not attribute it myself — see blind spots.

**Evidence.**

- C:/Users/User/.synapse/logs/freeze_dump_20260731_164134.json (reason='sustained_freeze', pid 45712): scene_hash {count: 44, sum_ms: 23428.91, max_ms: 4305.39}; cumulative buckets {1:22, 5:22, 10:27, 50:30, 100:32, 250:34, 500:34, 1000:34, 2000:39, 4000:42} => 5 calls in (1000,2000] ms and 2 calls above 4000 ms.
- Idle-scene control from the same instrument: telemetry.json session A scene_hash {count:3, max_ms:0.0876} on a 9-node scene. Same code, four orders of magnitude apart.
- Two calls per bridge operation: shared/bridge.py:1257 and :1266 (also :1227/:1229 on the standalone path).
- Timing wrapper that produced the numbers: shared/bridge.py:708-715 `_t0 = time.perf_counter() ... finally: _record_scene_hash_ms((time.perf_counter() - _t0) * 1000.0)`.
- Two candidate cost centres inside the hashed block, both on the same code path: shared/bridge.py:821 `stage.Flatten().ExportToString()` (full composed-stage USDA serialization) and shared/bridge.py:758-763 `geo = node.geometry(); geo.intrinsicValue('pointcount'/'primitivecount'/'bounds')`.

*VERIFIED · latency · effort: medium*

### Only 1 of 5 registered render commands routes through the bounded wrapper; three bypass it and all ship as MCP tools

**Claim.** `_handle_render_bounded` is registered for exactly one command (`render`); `safe_render`, `render_progressively`, and `render_sequence` each call `_handle_render` directly, skipping the session/token flow, the 60s wait budget, and the foreground guard.

**Why it matters.** On the /synapse WS path these commands hold the handler thread inside a run_on_main marshal bounded only by _RENDER_MAIN_TIMEOUT_S (3600s, handlers_render.py:133) — the exact serial-message-loop jam the bounded wrapper was built to prevent. render_progressively multiplies it by three sequential renders. The forensics doc's own remediation 1(c) asked for this confirmation; the answer is that the bound does not cover them.

**Action.** Either route these three through `_handle_render_bounded` (giving them token/poll semantics), or document them as explicitly foreground-blocking and gate them behind `assess_foreground_render` the way the bounded path does at handlers_render.py:473-484.

**Evidence.**

- python/synapse/server/handlers.py:670 — `reg.register("render", self._handle_render_bounded)` — the only bounded registration
- python/synapse/server/handlers_render.py:2233 — `render_result = self._handle_render(render_payload)` inside `_handle_safe_render` (registered handlers.py:763)
- python/synapse/server/handlers_render.py:2364 — `render_result = self._handle_render(render_payload)` inside `_handle_render_progressively` (registered handlers.py:764), executed once per pass across THREE passes
- python/synapse/server/render_farm.py:88 — `render_frame=handler._handle_render` — the orchestrator behind `render_sequence` (registered handlers.py:753)
- mcp_tools_render.py:48-53 — `synapse_render_sequence`, `synapse_render_progressively`, `synapse_safe_render`, `synapse_autonomous_render` are all exposed tools

*VERIFIED · freeze · effort: medium*

### The off-main marshal records queue WAIT but never payload DURATION — main-thread grip is unmeasured on the path the Class 3 fix created

**Claim.** `run_on_main`'s deferred path instruments the enqueue→start wait but places no timer around `fn()`, so the time a payload actually holds Houdini's main thread is not recorded anywhere on the off-main path.

**Why it matters.** PR #50 moved panel tool dispatch off-main, which is correct — but it moved every payload onto the one path with no duration instrument. That is why the 07-31 forensics had to infer h7 from heartbeat gaps and second-order queue waits instead of reading the payload's runtime directly. Without this measurement, remediation item 1 cannot be verified after it lands.

**Action.** Wrap `fn()` at main_thread.py:302 in a perf_counter pair and feed a third histogram (deferred-payload duration), or reuse `note_main_thread_inline_overrun` with a distinct `where`. This is the missing half of the C6 attribution work and is a prerequisite for proving any Class 4 fix.

**Evidence.**

- python/synapse/server/main_thread.py:290-307 — `_on_main` calls `_record_dispatch_wait(...)` at :296 (enqueue→start) then `result_holder[0] = fn()` at :302 with no surrounding perf_counter
- python/synapse/server/main_thread.py:94-97 comment confirms the split scope: '_dispatch_wait ... is the enqueue→start WAIT on the worker path; this one is the fn() DURATION on the main thread' — but the DURATION sink (`_record_main_thread_direct`) is wired ONLY into Fast path 2 at :241-248, never into `_on_main`
- Consequence visible in the data: ~/.synapse/logs/freeze_dump_20260731_164134.json has `main_thread_direct.count = 0` and `dispatch_waits.max_ms = 24927.7` — the 24.9s is one caller's queue wait, i.e. the shadow of an occupied main thread, not a measure of the payload that occupied it

*VERIFIED · freeze · effort: small*

### marshal_guard's inline-overrun ledger has zero production consumers and is absent from the freeze dump

**Claim.** `guard_stats()` and `guard_events()` — the read surfaces for the sink built specifically to observe long inline main-thread payloads — are referenced only by tests, and `collect_telemetry()` does not gather them, so the freeze dump cannot see inline overruns at all.

**Why it matters.** The forensics doc's own §2 says the inline residual is 'otherwise completely invisible.' Its evidence sink is write-only in production and missing from the very artifact (the freeze dump) that forensics reads first. The log line is the only escape hatch, and logs rotate and are pytest-polluted.

**Action.** Add `marshal_guard.guard_stats()` (and a bounded slice of `guard_events()`) to `collect_telemetry()` at telemetry_dump.py:107-163 so every freeze dump carries the inline-overrun ledger.

**Evidence.**

- python/synapse/server/marshal_guard.py:401 `def guard_events(...)`, :407 `def guard_stats(...)` — both public
- `grep -rn 'guard_stats\|guard_events' python/ mcp_server.py mcp_tools_*.py shared/` (excluding the defs) → no matches; only tests/test_marshal_hostile.py references them
- python/synapse/server/telemetry_dump.py:107-163 — `collect_telemetry()` gathers only `dispatch_waits`, `main_thread_direct`, `scene_hash`, `tool_durations`, `freeze`; no marshal_guard key
- Partial mitigation exists: marshal_guard.py:284-290 emits a `logger.warning`, which is why the 25 production records in ~/.synapse/logs/synapse.log were recoverable at all

*VERIFIED · freeze · effort: trivial*

### Complete production freeze chain captured end-to-end inside a panel prompt conversation

**Claim.** The log contains the full causal chain of one GUI-grip event on 2026-07-31: heartbeat loss at 12:51:31, main thread frozen 23.1s, recovery at 12:51:49, immediately followed by the panel reporting a 46,724ms inline main-thread tool run, all bracketed by a panel claude_worker conversation that completed 6 turns / 5 tool calls.

**Why it matters.** This removes the need to reproduce the freeze live. The chain shows the trigger (a panel prompt conversation issuing tool calls), the mechanism (inline main-thread execution), and the symptom (watchdog-confirmed 23.1s freeze) in one contiguous sequence. It is the strongest single piece of evidence in my lane and it independently corroborates the panel-inline finding.

**Action.** Cite this exact line range as the reference reproduction in the verdict doc. Use the freeze_dump JSON schema as the acceptance signal — a fixed build should produce zero sustained_freeze dumps under an equivalent panel conversation.

**Evidence.**

- C:/Users/User/.synapse/logs/synapse.log:18717 — `12:51:31,337 [synapse.resilience] WARNING: FREEZE DETECTED! No heartbeat for 5.0s`
- synapse.log:18718 — `12:51:31,360 [synapse.freeze_chain] WARNING: Main thread frozen for 5.0s — escalation in 25s unless it recovers`
- synapse.log:18719 — `12:51:49,441 [synapse.resilience] INFO: Main thread recovered (was frozen for 23.1s)`
- synapse.log:18721 — `12:51:49,705 [synapse.panel.tool_executor] WARNING: Inline tool 'houdini_set_parm' ran 46724ms on the main thread`
- synapse.log:18722 — `12:52:17,263 [synapse.panel.claude_worker] INFO: Conversation complete: 6 turns, 5 tool calls`

*VERIFIED · freeze · effort: trivial*

### Every /mcp call opens a new websocket connection, imposing a hard ~2.01s floor against a 0.057ms handler

**Claim.** There is no connection reuse on the /mcp path: each tool call establishes a fresh websocket, producing a reproducible ~2.010s wall-clock floor per call while the server-side handler executes in 0.057ms — roughly a 35,000x overhead ratio.

**Why it matters.** This is a genuine live defect my probe found on its own path. It makes every agent interaction ~2s slower than the work requires, and constant connection churn is a plausible contributor to the transient drop I hit mid-probe. It is separate from the GUI-grip bug and would not be caught by any static review.

**Action.** Reuse a single persistent websocket per MCP client session instead of connecting per call. Verify by re-running the four-ping control and confirming the deltas collapse toward the sub-millisecond handler cost.

**Evidence.**

- Four control pings, server-authored timestamps: 1785592778.8805432, 1785592780.8905227, 1785592782.9047654, 1785592784.9161630 → deltas 2.0100s, 2.0142s, 2.0114s
- Millisecond-exact 1:1 mapping to server connection log (anchor: doctor `last_timeout_ts` 1785592504.5058525 == synapse.log:19120 `2026-08-01 09:55:04,505`): +274.375s→09:59:38,880 client_00034; +276.385s→09:59:40,890 client_00035; +278.399s→09:59:42,904 client_00036; +280.410s→09:59:44,916 client_00037. Four calls, four new connections, four for four.
- Server-side cost of that same work: `synapse_tool_duration_ms_sum{tool="ping"} 1.7587` over `_count 31` → 0.0567ms mean, all 31 in the le="5" bucket
- CONTROL (this is the load-bearing part): the identical ~2.01s spacing occurred WITHOUT any heavy read in the batch, so the cadence is unconditional and is NOT induced by load. Client IDs 00008→00011 at 2.005s spacing predate my first ping entirely.
- Log inter-arrival histogram over my window: 2.005s ×4, 2.015s ×2, 2.010s ×2, 2.004s ×2

*VERIFIED · latency · effort: medium*

### 99.8% of main-thread dispatches wait 50–100ms to start while the work itself averages 0.2ms; tail reaches 17.2 seconds

**Claim.** Across 33,948 samples the run_on_main enqueue-to-start wait has a hard floor in the 50–100ms band (33,875 samples = 99.8%), with only 53 samples under 50ms, while the actual main-thread work is 0.2ms mean / 0.895ms max — and the wait tail reaches 17,167ms.

**Why it matters.** The queue, not the work, is the entire cost — a 267x ratio of waiting to working. The uniform 50–100ms floor is the signature of a fixed-interval poll rather than contention. The 7 sub-second-plus outliers and the 17.2s maximum are each a visible GUI hitch that the current 'not stalled' health summary reports as healthy.

**Action.** Identify the main-thread executor's poll interval and replace polling with event-driven wakeup to remove the floor. Separately, add alerting on the dispatch_wait tail — a 17.2s wait currently surfaces nowhere except this histogram's max field.

**Evidence.**

- synapse_metrics: `synapse_dispatch_wait_ms_bucket{le="50"} 53`, `{le="100"} 33928`, `{le="1000"} 33941`, `{le="2000"} 33945`, `{le="4000"} 33946`, `{le="+Inf"} 33948`; `_sum 1811857.2742`; `_max 17167.1001` → mean 53.4ms
- Work for comparison: `synapse_main_thread_direct_ms_sum 1.2619` over `_count 6`, `_max 0.895` → the executed function is essentially free
- Tail decomposition: 7 waits exceeded 1s, 3 exceeded 2s, 2 exceeded 4s, max 17.2s, in a process with ~69,483 one-per-second heartbeats (~19h uptime)
- Independently corroborated by synapse_doctor main_thread check: `not stalled (0 consecutive timeouts, 33876 dispatch-wait samples, max 17167ms)`
- A main-thread timeout fired at 09:55:04 today, ~2.7 minutes BEFORE my first ping — synapse.log:19120 — so it is production traffic, not mine

*VERIFIED · freeze · effort: medium*

### The bounded render wrapper guards 1 of 5 registered render commands; the other four are shipped MCP tools

**Claim.** `_handle_render_bounded` is registered only for `render`; safe_render, render_progressively, render_sequence and autonomous_render reach `_handle_render` directly, inheriting a 3600-second marshal budget with no wait budget, no token flow, and no foreground guard.

**Why it matters.** An agent or artist invoking safe_render, render_progressively, render_sequence or autonomous_render can hold Houdini for the full render duration with no bound and no way to stop it; render_progressively multiplies the exposure by three sequential renders. This is Class 1's real residual, and the bounded wrapper's existence makes it easy to assume coverage that is not there.

**Action.** ENGINEERING (medium): either route the three bypassing handlers through `_handle_render_bounded` so they gain token and poll semantics, or gate them behind `assess_foreground_render` the way the bounded path does at handlers_render.py:473-484. Separately assert off-main before the sleep loop at handlers_render.py:964 and add main-thread `time.sleep` in a handler to whatever lint pins the marshal surface.

**Evidence.**

- RE-VERIFIED IN THIS PASS — `grep -n 'reg.register("...")' python/synapse/server/handlers.py` returns handlers.py:670 `reg.register("render", self._handle_render_bounded)` as the ONLY bounded registration, alongside :753 render_sequence, :763 safe_render, :764 render_progressively, :802 autonomous_render pointing at unbounded handlers.
- Bypass call sites: handlers_render.py:2233 `render_result = self._handle_render(render_payload)` inside _handle_safe_render; :2364 the same inside _handle_render_progressively, executed once per pass across THREE passes; render_farm.py:88 `render_frame=handler._handle_render` behind render_sequence.
- Exposed to agents: mcp_tools_render.py:31-32 and :52-53 register synapse_safe_render and synapse_render_progressively as first-class MCP tools, so the unbounded route is agent-reachable.
- handlers_render.py:133 `_RENDER_MAIN_TIMEOUT_S = 3600.0` — the budget the bypassing paths inherit is one hour.
- A seam the primary remediation would miss (Lane C leg 3, code re-read by Lane C verdict): handlers_render.py:964-971 is a hard 15s `time.sleep(0.25)` × 60 file-existence poll. The comment above it says 'Off-main from here' but that refers to the absence of hou calls, not the calling thread — so a main-thread caller executes the sleep on main, and because it is neither a cook nor hou work, timeboxi

*VERIFIED · freeze · effort: medium*

### One line can silently reopen the only freeze class with a verified fix, and nothing in CI would notice

**Claim.** python/synapse/panel/synapse_panel.py:1938 connects `worker.tool_requested` to the main-thread `execute_tool` slot; there are zero production emitters and zero tests preventing one, so a single `.emit()` re-arms Class 3.

**Why it matters.** Class 3 is the one freeze class with a fix verified three independent ways. This is the single line that can undo it, and a future contributor restoring the signal path for a plausible reason would reopen a closed freeze with no CI signal at all.

**Action.** ENGINEERING (trivial): delete the connect at synapse_panel.py:1938 since it has no emitters, or add a source-lint test in the style of tests/test_marshal_lint.py asserting zero `tool_requested.emit` in python/synapse.

**Evidence.**

- python/synapse/panel/synapse_panel.py:1938 — `self._worker.tool_requested.connect(self._tool_executor.execute_tool)`; the signal is declared at claude_worker.py:84.
- `grep -rn 'tool_requested' python/ tests/` returns 6 hits total — the declaration, three comments, and the one connect. `grep -rn 'tool_requested.emit' python/ tests/` returns EMPTY: no emitters, no test coverage.
- The slot is the freeze path: tool_executor.py:377-392 `execute_tool` docstring states it 'runs on the thread that owns the ToolExecutor (the main thread)'.
- Named as remediation item 3 in harness/notes/FREEZE_FORENSICS_20260731.md:90-92 with the exact pin requested: 'regression test asserting no production emitter of tool_requested; or disconnect the wire'.
- CONVERGENT — found independently by Lane C leg 1 and re-derived in Lane C's adversarial verdict.

*VERIFIED · risk · effort: trivial*

### The 'ran Xms on the main thread' log string misattributes queue-wait timeouts as GUI grip, and a passing test pins it

**Claim.** `_dispatch` is shared by the main-thread slot and the off-main daemon path but logs 'on the main thread' unconditionally, so post-fix records are daemon wall-time; tests/test_panel_preflight.py asserts that exact wording, making the fix test-breaking.

**Why it matters.** The numbers a triager would most naturally quote are the contaminated ones. This already corrupted one forensics run by the ticket's own admission, and because the fix now carries a test-breaking cost it is likelier to be deferred again — compounding across every future investigation.

**Action.** ENGINEERING (small): pass a flag through `_dispatch` distinguishing slot from daemon and branch the message ('held the main thread' versus 'dispatch took'), then update tests/test_panel_preflight.py:248-262 to assert the discriminating label rather than the shared substring. Do this before the next freeze investigation, not after.

**Evidence.**

- tool_executor.py:472-479 — the warning inside `_dispatch`'s finally: "Inline tool %r ran %.0fms on the main thread (Qt loop stalled this long; slow threshold %.0fms)". Both callers share it: :390 `self._dispatch(request, emit_preflight=True)` from the main-thread slot and :517 from `execute_tool_off_main` on a daemon thread. Even the helper docstring at :67 carries the stale claim.
- MISATTRIBUTION PROVEN WITH LIVE DATA (Lane C leg 1): the log records `'houdini_create_node' ran 10005ms on the main thread` and `'synapse_inspect_scene' ran 10005ms on the main thread` — both exactly 10005ms, i.e. run_on_main's `_DEFAULT_TIMEOUT` of 10.0s (main_thread.py:20) plus overhead. Those are queue-wait TIMEOUTS reported as main-thread occupancy.
- tests/test_panel_preflight.py:259 filters `"ran" in r.message and "main thread" in r.message` then asserts the list is non-empty — so correcting the message breaks a currently-green test.
- harness/notes/FREEZE_FORENSICS_20260731.md:41 names the consequence itself: the string 'will misattribute future freezes. This corrupted forensics this run and will corrupt the next one.'

*VERIFIED · risk · effort: small*

### Freeze escalation has no breaker to open and no halt to fire — it collects evidence and does nothing

**Claim.** When a freeze passes the escalation threshold, freeze_chain logs 'No live SynapseServer breaker to open (hwebserver transport has no resilience layer)' and then skips the emergency halt, so there is no automatic recovery for the artist.

**Why it matters.** The artist has no automatic escape from a freeze in progress, and no manual one either — render_stop cannot reach a foreground render on 22.0.368. Equally important for documentation honesty: escalation is currently described in places as a mitigation, and it is not; the dump is the only deliverable.

**Action.** HUMAN GATE (decide scope) then ENGINEERING: stop describing escalation as a mitigation anywhere it appears, and decide whether the hwebserver transport should gain a resilience layer at all — the alternative is accepting that freeze handling is evidence collection only and saying so plainly.

**Evidence.**

- python/synapse/server/freeze_chain.py:154-158 emits the breaker error; :171-173 skips the halt with 'No ACTIVE bridge — emergency halt skipped (escalation never constructs one)'.
- CONFIRMED FIRING IN PRODUCTION during the 44.4s freeze — ~/.synapse/logs/synapse.log:18698 carries the breaker line and :18699 the skipped-halt line, both inside the 2026-07-31 12:41 event.
- Live today: the log carries `[synapse.hwebserver] INFO: Native C++ server -- no watchdog, no circuit breaker` 40 times, most recently 2026-08-01 10:04:05.
- CONVERGENT — Lane C leg 1 found it in source, Lane C leg 2 found the production firing, Lane C's verdict re-derived both.

*VERIFIED · freeze · effort: unknown*

### Master publishes a Tier-1 forensic figure its own author refuted; the correction sits uncommitted in a worktree

**Claim.** harness/notes/forensic/S2_PREMORTEM.md on master asserts '95 of the 228 palette rows (41.7%) send an English description to the model instead of dispatching' at lines 185 and 808, while the later uncommitted copy in .claude/worktrees/s2-forensic corrects it to 21/228 (9.2%) and states the correction 'cuts a Tier-1 headline by 4.5x'.

**Why it matters.** This repository has already been burned by a control pinned to a document's own wrong figure. Here the wrong figure is the committed one and the evidence-backed correction is the uncommitted one, so anyone citing S2_PREMORTEM.md from git cites a number its own author refuted — and one worktree prune makes the correction unrecoverable.

**Action.** HUMAN GATE (small): read the 239-line delta in .claude/worktrees/s2-forensic and decide commit versus discard. Do not prune that worktree until the decision is made. Note the reviewing lane could not establish that nobody deliberately reverted it, so this genuinely needs a human ruling rather than an automatic merge.

**Evidence.**

- `git grep -n '41.7%' master -- harness/notes/forensic/S2_PREMORTEM.md` → matches at :185 and :808.
- Diff master versus the worktree copy: 239 lines only in the worktree, 68 only in master; the worktree text reads '**21 of the 228 palette rows (9.2%)** ... Corrected by the adversarial pass, and the correction cuts a Tier-1 headline by 4.5x.'
- mtimes establish which is later: worktree S2_PREMORTEM.md 2026-07-27 15:50:34 and S2.json 15:51:17, versus master's last commit for both at 83a4820 2026-07-27 15:36:40.
- Master's S2.json says the adversarial pass was 'DISPATCHED'; the worktree's says 'ADVERSARIAL PASS RAN - 3 hostile lenses ... ALL 14 are APPLIED ... four numbers broken and corrected'.

*VERIFIED · risk · effort: small*

### The richest latency dataset is atomically overwritten every session and was destroyed mid-investigation

**Claim.** ~/.synapse/logs/telemetry.json is a single-file periodic atomic overwrite with no rotation, so each Houdini restart destroys the accumulated dispatch-wait, scene-hash and tool-duration histograms of the prior session.

**Why it matters.** The instrument works and the data is good; it simply does not survive. Every latency question the project asks has to wait for a fresh session to re-accumulate, which is a direct cause of the marshal-attribution question staying open for months. Retaining one file per session would have closed it with no new instrumentation.

**Action.** ENGINEERING (trivial): add a timestamped session-final flush on shutdown, or roll telemetry.json to telemetry_<pid>_<ts>.json before overwrite — mirroring the freeze-dump naming that already exists in the same module. Retention can be as simple as keeping the last N.

**Evidence.**

- python/synapse/server/telemetry_dump.py:200-219 — `flush_telemetry(reason='periodic')` performs a tmp + os.replace overwrite of telemetry.json; only non-periodic reasons get a timestamped file.
- OBSERVED LIVE DURING THIS REVIEW (Lane B lane 3): at ~10:00 EDT telemetry.json contained pid 56116 with 33,833 dispatch-wait samples; at 10:07 EDT the same path contained pid 3696 with 87 samples. The 33,833-sample dataset no longer exists on disk.
- Only freeze-triggered dumps persist with timestamps (five freeze_dump_*.json files) — history survives for freezes and never for healthy sessions.
- Concrete consequence: docs/reviews/synapse-latency-report-2026-07-27.md §5 lists the dispatch-wait re-measure as the top open action while a 33,833-sample answer was sitting in this file, and it has since been overwritten.

*VERIFIED · risk · effort: trivial*

### CI is red at HEAD on a one-token documentation drift, not the dependency breakage the standing notes blame

**Claim.** VERSION says 5.41.0 while CLAUDE.md's banner still says v5.40.1, and tests/test_phase0c_doc1_version_conformance.py enforces the pair — so every PR goes red on merge-base for a reason unrelated to the mcp library.

**Why it matters.** Every PR is red on merge-base, which is exactly the symptom the memory index attributes to the mcp library drop. A maintainer following that note would re-pin or migrate an already-working dependency and never touch the real cause. The fix is a one-token edit.

**Action.** ENGINEERING (trivial): update the CLAUDE.md banner to v5.41.0, then add the banner bump to the release checklist so a VERSION bump cannot ship without it. Separately retire the mcp-drop item from the open list, keeping only the pyproject.toml:53 note that mcp_server.py:899 and the call_tool decorator must migrate before the pin can be lifted.

**Evidence.**

- RE-VERIFIED IN THIS PASS — `cat VERSION` → `5.41.0`; `sed -n '3p' CLAUDE.md` → '> **Target:** Houdini 22.0.368 (dual-build with H21 artifacts) · SYNAPSE v5.40.1 · Python 3.13 · 123 MCP tools registered'.
- tests/test_phase0c_doc1_version_conformance.py:44 `assert f"v{canonical}" in claude`. Local repro (Lane A): 'AssertionError: CLAUDE.md does not state the canonical SYNAPSE version v5.41.0'.
- CI log for HEAD run 30679790433: `FAILED tests/test_phase0c_doc1_version_conformance.py::test_version_single_sourced_and_docs_conform` and `1 failed, 5255 passed, 196 skipped` — a single failure, no collection error.
- THE STANDING NOTE IS NOW WRONG: the mcp==1.26.0 pin from 9c8fe87 is present at pyproject.toml:59 and effective — live probe shows `mcp version: 1.26.0`, `Server.list_tools: True`. The collection error at mcp_server.py:899 is gone from CI.
- The release commit 8dfa23d bumped VERSION and left the banner behind.

*VERIFIED · unfinished-work · effort: trivial*

### The 289-item decisions board has no closure mechanism, so verified-resolved items stay counted as open

**Claim.** harness/decisions.py collects receipt for_ruling[] entries unconditionally and has no resolved, closed or retired concept, so items whose work has demonstrably landed remain on the board — three were verified false-open.

**Why it matters.** The board is the harness's answer to 'what is waiting on a human'. If an unknown fraction of 289 is already done, every triage sitting starts by re-reading resolved items — the exact attention bottleneck decisions.py:24-30 says it exists to fix. It also makes the count monotonically increasing, which harness/clear/SPEC.md:38 names as a falsification condition for the clearance harness.

**Action.** ENGINEERING (medium): add a per-item resolution channel — either a `resolved`/`resolved_by` field on receipt for_ruling entries that collect() filters out, or a harness/state/resolved.json keyed by (leg, text-hash) that decisions.py subtracts — then do one sweep to retire the already-landed items. Add a `deposited_at` field so age stops depending on a shared file clock. Do not hand-edit DECISIONS.md; it is derived.

**Evidence.**

- RE-VERIFIED IN THIS PASS — `grep -n 'resolved\|closed\|retire\|dismiss' harness/decisions.py` returns nothing at all: there is no per-item closure path. collect() at :115-160 appends every `for_ruling` entry unconditionally.
- RE-VERIFIED IN THIS PASS — false-open 2: DECISIONS.md:31 still lists 'delete the 8 delete-classed TRACKED dirs'; `git ls-files | grep -c '^_solaris_fix/\|^SYNAPSE-asm-\|^SYNAPSE-fx-'` → 0. False-open 3: DECISIONS.md:33 still lists 'docs/*.txt - 15 untracked scratch files'; `git ls-files docs/ | grep -c '\.txt$'` → 0 tracked, and 48 are gitignored.
- False-open 1 (Lane A): DECISIONS.md:47 still lists the panel consent-gate ruling, but the fix landed — python/synapse/panel/gate_widget.py:513-514 reads 'A consent gate that reports success on a swallowed exception is worse than no gate', with the emits now guarded at :521 and :550.
- RE-VERIFIED IN THIS PASS — harness/state/DECISIONS.md:3 'Do not hand-edit - it is derived,' and :5 '289 open, 0 older than 30d.' The only retirement route today is editing the source receipt JSON by hand.
- Compounding defect: decisions.py:160-176 assigns every flywheel item `ages.get(rel)` from the single last-commit timestamp of flywheel_queue.json, so one shared clock covers all 26 and any commit to that file resets every age to zero. decisions.py:35-40 states the aging gate is what makes the loop closed rather than merely observable.

*VERIFIED · hygiene · effort: medium*

### Every MCP tool call opens a new websocket, imposing a ~2.01s floor against a 0.057ms handler

**Claim.** There is no connection reuse on the MCP path: each tool call establishes a fresh websocket, producing a reproducible ~2.01s wall-clock floor per call while the server-side handler executes in microseconds.

**Why it matters.** This is the single largest available latency reduction and it is architectural rather than model-bound. A ten-tool build spends roughly twenty seconds in connection setup. It also nuances the standing latency report: the report's claim that the websocket transport is millisecond-class is not wrong, but it never accounted for per-call connection establishment, so its 'latency is not a transport problem' conclusion rests on an incomplete ledger.

**Action.** ENGINEERING (medium): reuse a single persistent websocket per MCP client session instead of connecting per call. Verify by re-running the four-ping control and confirming the deltas collapse toward the sub-millisecond handler cost. Note this likely also fixes the transient connection drop observed during the probe, since both are symptoms of connection churn.

**Evidence.**

- MECHANISM, live and millisecond-exact (Lane C leg 2): four control pings at server timestamps 1785592778.88, 1785592780.89, 1785592782.90, 1785592784.92 → deltas 2.0100s, 2.0142s, 2.0114s, each mapping 1:1 to a distinct new server-side connection (client_00034 through client_00037 at 09:59:38.880, 40.890, 42.904, 44.916).
- SERVER-SIDE COST FOR COMPARISON: `synapse_tool_duration_ms_sum{tool="ping"} 1.7587` over `_count 31` → 0.0567ms mean, all 31 samples in the le="5" bucket.
- INDEPENDENT CORROBORATION FROM A SEPARATE DATE AND TWO SEPARATE CLIENT STACKS (Lane B lane 1): harness/notes/forensic/s1_artifacts/ws_readonly_sweep.json → n=35, median 2.01s, range 2.00–2.07; mcp_surface_probe.json over the external MCP stdio surface → median 2.01s. Both producers verified sleep-free at s1_ws_readonly_sweep.py:77-96 and s1_mcp_surface_probe.py:91-112.
- A FIXED FLOOR, NOT WORK: houdini_get_parm fails instantly ('Couldn't find parameter') at 2.01s; synapse_knowledge_lookup (RAG-backed) at 2.00s. And the control matters — the identical spacing occurs with no heavy read in the batch, so it is not load-induced.
- Client-side singleton confirmed in source (Lane B lane 3): mcp_server.py:202 `_ws_connection = None` is a module global reused at :270/:275 — so the stdio bridge is designed to hold one connection, which makes the observed per-call reconnection a defect rather than the design.

*VERIFIED · latency · effort: medium*

### The main-thread marshal wake floor is ~53ms with zero samples under 50ms — refuting the 2-second wake hypothesis and establishing a hard unit price

**Claim.** Every off-main hou call pays roughly 53 milliseconds of pure queue-sit before any Houdini work begins; this reproduces across two independent production sessions with 33,920 samples and no sample in either has ever completed under 50ms.

**Why it matters.** Two things flip on this number. The parked 2-second wake hypothesis is refuted with a large sample, releasing effort held behind that gate. And 53ms becomes a hard unit price, so any proposal that changes the number of marshals per operation can be costed in milliseconds rather than argued about — which is what makes the envelope and metrics-poll findings below actionable.

**Action.** ENGINEERING (trivial to publish, medium to fix): publish the number as the marshal unit cost and close the attribution item, correcting the latency report's tier row. Then determine whether hdefereval.executeDeferred is serviced by a fixed-interval pump; if so, evaluate an event-driven wakeup for short read-only marshals. Add histogram edges at 20/30/60/80ms and 8s/16s/32s, since the dominant bin is 50ms wide and the 4s-to-17s tail collapses into one opaque bucket.

**Evidence.**

- Session A (pid 56116, v5.40.1, ~19.3h uptime), telemetry.json: dispatch_waits count=33833, sum_ms=1805742.9986 → mean 53.37ms, max_ms=17167.1. Cumulative buckets {1:0, 5:0, 10:0, 50:53, 100:33814} — 99.8% land in (50,100] and ZERO at or below 10ms.
- Session B (pid 3696 = the live hindie process, 181s uptime): count=87, sum_ms=4716.7 → mean 54.21ms; buckets {1:0,5:0,10:0,50:0,100:86}. Two independent samples agreeing to within 1.6%.
- Producer verified: main_thread.py:288 `t_enqueue = time.perf_counter()` → :296 `_record_dispatch_wait(...)` inside `_on_main` — the histogram times exactly enqueue to callback-start.
- Measured live by a second lane at the same time (Lane B lane 2): over a 215.343s window with ping-anchored counter deltas, 106 fresh samples, mean 53.27ms, ZERO under 50ms, while the main thread was idle (9-node scene, no render).
- REFUTES a standing hypothesis: main_thread.py:42-48 parks the buckets specifically so that a ~2000ms wake floor would be 'unmistakable'. Observed mass is at 50–100ms.

*VERIFIED · latency · effort: medium*

### The live integrity envelope adds two hidden ~54ms marshals to every mutating command and excludes them from the histogram meant to attribute marshal cost

**Claim.** Every mutating /synapse command performs three main-thread round trips instead of one — the handler's own plus two observe-only scene-hash captures — costing roughly 108ms extra inside the process-wide mutation lock, and both extra captures pass record_wait=False so they never appear in the dispatch-wait histogram.

**Why it matters.** This is the largest architecture-imposed, model-independent cost that can be quantified. It roughly triples the marshal count of every mutating command, it is held inside the process-wide mutation lock so it extends the window blocking every other client, and the instrument built to attribute marshal cost systematically under-reports mutating operations threefold. A ten-node imperative build pays about 1.08 seconds of pure wake latency for provenance whose consent, composition and undo anchors are all recorded not-applicable.

**Action.** ENGINEERING (medium): price the envelope knowingly rather than invisibly. Cheapest correct fix is reusing the previous operation's parked after-hash as this operation's before-hash (shared/bridge.py already parks hashes), halving it to one marshal. Failing that, flip record_wait=True so the tax is at least visible. Do not move the captures outside the lock — they must bracket the operation.

**Evidence.**

- python/synapse/server/handlers.py:526-539 — `with _lock_cm:` then :528 `_hash_before = _envelope.capture_scene_hash(...)`, :529 `result = self._registry.invoke(...)`, :539 `_hash_after = _envelope.capture_scene_hash(...)`. Both captures are inside the mutation lock.
- python/synapse/server/integrity_envelope.py:218-223 — each capture is `run_on_main(..., record_stall=False, record_wait=False)`, a full round trip; main_thread.py:295-296 `if record_wait: _record_dispatch_wait(...)` confirms the exclusion.
- The cost is the wakes, not the hashing: telemetry shows scene_hash count=3 max_ms=0.088 on an idle scene — sub-millisecond compute, two ~54ms wakes.
- Handlers themselves marshal exactly once: an indentation-scoped scan of every run_on_main call site under python/synapse/server/ for an enclosing loop returned no hits, so the 3:1 ratio is entirely the envelope. This also answers the brief's 'N-node build pays N round trips' question in the negative — marshal batching inside handlers is not an available win.
- The envelope is observe-only: integrity_envelope.py:269-282 records consent_verified, composition_valid and undo_group_active all False with *_applicable=False.

*VERIFIED · latency · effort: medium*


---

## MEDIUM

### CLEAR line L5 exists only in FORUM/LOG — the ratified SPEC and PLAN have no L5, and P5.1 lives on an unpushed branch

**Claim.** L5 was opened, fanned out, and returned a verified scanner, but SPEC.md still has 8 predicates and PLAN.md still has 4 lines; P5.1 is a PROPOSED-only file inside a worktree, carrying a mandatory implementation precondition that has not been met.

**Why it matters.** The harness correctly refused to self-edit its own ratified contract — that is the anti-runaway anchor working. But the consequence is that a finished, crucible-verified capability (24 tests, 1303-file production scan, 0 false flags per LOG.md:17) is invisible to the bar it was built for, and its correctness depends on an implementation precondition that is documented in a file only one unpushed branch knows about.

**Action.** HUMAN GATE then ENGINEERING (small): Joe ratifies P5.1 into SPEC.md; then the verify.py implementation MUST inject EXPECTED_HOUDINI_VERSION=22.0.368 (non-negotiable per the proposal's own measurement) and the merge must carry the hdefereval allowlist plus the two missing snake_case aliases. Push the branch first (see local-only-unmerged-branches).

**Evidence.**

- harness/clear/SPEC.md:13-22 — the predicate table ends at P4.1; no P5.1. SPEC.md:3 — 'changed only at explicit ratification points. Do not edit without a ratified change.'
- harness/clear/PLAN.md:5,21,37,54 — lines L1/L2/L3/L4 only; no L5 section.
- harness/clear/verify.py:237-246 — PREDICATES list holds exactly the 8 SPEC IDs; no phantom check runs in CLEAR's bar. This is the G1 gap named in FORUM.md:24: 'CLEAR's bar (`harness/clear/verify.py`) runs no phantom check. The #1 failure class is outside work-clearance.'
- harness/clear/LOG.md:17 — 'HALT: Joe — ratify P5.1 (SPEC+verify) and/or merge clear/l5-phantom-scanner; §1.7 constructability quarantine = open follow-up'
- .claude/worktrees/clear-l5-phantom-scanner/harness/clear/PROPOSED-P5.1.md — 'Ratification precondition — expected-build injection is mandatory ... P5.1's implementation in CLEAR's verify.py MUST set `scout.EXPECTED_HOUDINI_VERSION = <target build>` before calling `_load_symbol_table()`', with the measured consequence of skipping it: '152 pxr depth-2 symbols are h22-only ... 152 false-FAIL vectors 

*VERIFIED · unfinished-work · effort: small*

### 26 of 52 flywheel cycles are unratified proposals, including 3 whole cycle CLASSES (S.0 studio, R.0 release, C.0 capability)

**Claim.** harness/state/flywheel_queue.json holds 52 cycles, exactly 26 with ratified:false; the known U.2/U.3/U.4/C.0 are confirmed, and there are 22 more.

**Why it matters.** None of these is blocked; all are unread. Two carry named correctness risk rather than feature value — W.5b's silent relationship-authoring and CTO-01's never-re-probed USD round-trip — and those two are indistinguishable from the 24 feature proposals in the current flat list.

**Action.** HUMAN GATE (medium — this is the sitting the CLEAR L2 line was built to enable): rank the 26 by risk-vs-feature first. Suggested first pass: ratify or reject CTO-01 (moat gate, never re-probed on H22) and W.5b (silent wrong author) before touching the seven C.*-H22 feature cycles, which are explicitly held behind 'receipts first'.

**Evidence.**

- Parsed harness/state/flywheel_queue.json: 'RATIFIED: 26   UNRATIFIED: 26   TOTAL: 52'. All 26 unratified carry status='candidate'.
- The full list: U.2, U.3, U.4, C.0, S.0, R.0, C.1-H22-imagelayer-stats, C.2-H22-pxr-authoring, C.5-H22-pdg-telemetry, C.6-H22-pdg-services, C.7-H22-prune-lop, C.8-H22-husk-resume, C.9-H22-renderpass, W.3b-H22-nodeflow-corpus, CTO-01-memory-usd-roundtrip, CTO-02-opalias-enumeration, CTO-03-instancing-intent-successor, CTO-04-cop2net-sunset-register, CTO-05-guarded-degradation-honesty, W.5b-H22-write
- Blocking-reason clusters, from each cycle's own `note`: seven C.*-H22 cycles are 'deposited unratified (CTO hold: features wait — receipts first)'; five CTO-0* are 'Deposited from the sidefx-cto lens first pass (read-only advisory; agent proposed the spec, human ratifies)'; six W.*b/U.*b are crucible follow-ups all ending 'Human flip.'
- Two carry silent-wrongness risk in their own text: W.5b — 'a custom string[] attribute name ... gets SILENTLY authored as a relationship; converts a prior no-op into a possibly-wrong author'; CTO-01 — the memory-evolution USD round-trip is 'The moat's ONLY in-process exact-equality gate against live pxr, never re-probed on H22 despite USD 0.26.5 module reorg'.
- harness/decisions.py:24-30 — the triage finding: 'The triage of those 26 found only 5 to be agent-decidable; 20 are genuine human judgement calls ... 24 of the 26 gate nothing mechanically. The bottleneck is triage ATTENTION, not authority.'

*VERIFIED · unfinished-work · effort: medium*

### harness/legs.json state is stale — all 22 'ready' legs already have receipts, and R16's done.json is still absent

**Claim.** legs.json reports 22 ready / 7 done / 3 blocked, but every one of the 22 'ready' legs has a written receipt in harness/notes/receipts/, so the field the orchestrator gates on is not a completion record.

**Why it matters.** Two legs (H2, H1) and the integration leg F1 are marked 'blocked', and F1 'Runs LAST - gated on every evidence-producing leg'. If 'ready' does not mean 'not yet run', the orchestrator's dependency gate cannot distinguish a leg that never started from one that finished a week ago — which is how the same leg gets dispatched twice (see the H2 double-dispatch below).

**Action.** ENGINEERING (medium): make the orchestrator write leg state back on receipt completion, or build the missing harness/state/done.json that R16 asked for, keyed by (leg, receipt-sha). Until then, treat harness/notes/receipts/ as the completion record and legs.json state as dispatch-intent only.

**Evidence.**

- Counted from harness/legs.json: `Counter({'ready': 22, 'done': 7, 'blocked': 3})` over 32 legs.
- Cross-check against harness/notes/receipts/: all 22 'ready' legs have an existing receipt — RES(green), H3a(green), H3b(green), H4(amber), H5(green), H6(green), H7(green), H8(green), U1(green), V0(green_with_findings), V1(green), C1(green), RSI0(green), S0(green), S2(green), S3(green), I0(green), I1(green), E0(green), E1(no status), V2(green), V3(no status). Zero 'ready' legs are missing a receipt
- Stale note, verifiable: harness/legs.json leg H4 note reads 'Queued 2026-07-25, NEVER DISPATCHED - its brief was written into SYNAPSE_REPAIR_HEATS.md section 8 instead of this manifest' — yet harness/notes/receipts/H4.json exists (28,358 bytes, dated Jul 27, status 'amber', 5 for_ruling entries).
- harness/legs.json:_comment — 'The orchestrator owns: dependency gating, worktree creation, trust, launch, receipt monitoring, branch backup, and notification' — i.e. it reads this manifest for gating.
- R16 confirmation: `test -f harness/state/done.json` -> ABSENT. CTO_RELAY_01_RULING.md:280 — 'R16 · The harness has no completion memory'. The proposed alternative `ledger_truth.json` exists only inside worktrees (10 hits under .claude/worktrees/), none at the repo root.

*VERIFIED · hygiene · effort: medium*

### Four closed CTO rulings (R52-R55) are implemented only on an unmerged branch

**Claim.** repair/ledger-moneta-seam @ eb25abe holds 2,012 insertions that are unmerged into master, and CTO_RULINGS_01.md states the implementations of R52-R55 live only there.

**Why it matters.** This is the repo's clearest case of decided-but-not-delivered: the decision cost was paid, the implementation exists, and it is drifting further from mergeable with every change to moneta_runtime.py. R91 explicitly forbids the cheap fix (merge LEDGER first).

**Action.** ENGINEERING (medium): dispatch the U1 provenance-union leg as R91 specifies — author the five-field moneta_provenance() carrying the mutation pins both halves already wrote, with LEDGER's half landing inside that union. Note U1.json exists (status green, 4 for_ruling) so U1 has run at least once; confirm whether the union actually landed on master before re-dispatching.

**Evidence.**

- harness/notes/CTO_RULINGS_01.md:2521-2523 — 'LEDGER's ruled items **R52, R53, R54 and R55 are all DECIDED** — and implemented *only* in that stranded code. **Four rulings I closed are currently un-shipped**, and every further change to `moneta_runtime.py` widens the gap LEDGER's patch must cross.'
- `git log --oneline -1 repair/ledger-moneta-seam` -> `eb25abe leg(LEDGER): moneta seam - two defects closed, bounded revision walk`; `git diff --shortstat master...repair/ledger-moneta-seam` -> '8 files changed, 2012 insertions(+), 23 deletions(-)'; the branch appears in `git branch --no-merged master`.
- The named rulings: CTO_RULINGS_01.md:1394 'RULING 52 — LEDGER FR1: pin Moneta for release, keep the worktree for development'; :1406 'RULING 53 — FR2: build the reconciler. FR3: wire recall'; :1420 'RULING 54 — FR4: env var with repo-relative default. FR5: dedupe at read time'; :1431 'RULING 55 — FR6'.
- The prescribed unblock is authoring, not merging — CTO_RULINGS_01.md ruling 91: 'The union is AUTHORED, not merge-resolved. No automatic strategy produces a five-field function. It gets a leg with a precise brief' and 'LEDGER's half lands as part of that union, not before it.'
- harness/legs.json leg U1 ('provenance union', state='ready') carries that brief: 'R91 ... Neither has all five. LEDGER's 2,012 insertions are stranded at eb25abe and R52-R55 are DECIDED but un-shipped. This is AUTHORING, not merge resolution.'

*VERIFIED · unfinished-work · effort: medium*

### All 26 flywheel items share one clock — any commit to flywheel_queue.json resets every age to zero

**Claim.** harness/decisions.py derives every flywheel item's age from the single last-commit timestamp of flywheel_queue.json, so the 30-day overdue gate cannot fire for the flywheel class as long as that file keeps being edited.

**Why it matters.** decisions.py:35-40 says the aging gate is what makes the loop CLOSED rather than merely OBSERVABLE: 'A queue without a clock is a queue nobody has to answer.' A clock that resets whenever anyone adds a cycle is not that. The 26 have in truth been waiting since well before 2026-07-17 (the commit that set the clock was a revert, not a deposit).

**Action.** ENGINEERING (small): add a `deposited_at` field to the flywheel cycle schema and to receipt for_ruling entries — decisions.py's own docstring already names the absence as 'a finding in its own right'. Fall back to git age only when the field is missing.

**Evidence.**

- harness/decisions.py:160-176 — in the flywheel loop, every item is appended with `"age": ages.get(rel)` where `rel = "harness/state/flywheel_queue.json"` — one value for all 26.
- harness/decisions.py:95-113 (file_ages) derives age from a `git log` timestamp pass over file paths; the module docstring says 'Neither the receipt schema nor the flywheel schema records when an item was deposited (a finding in its own right). Age is therefore DERIVED from git'.
- `git log -1 --format="%ai %h %s" -- harness/state/flywheel_queue.json` -> `2026-07-17 14:38:40 -0400  87553ab  revert: undo the manufactured strategy ratification (cae465f)`. Consistent with DECISIONS.md showing all 26 flywheel rows as '13d' at 2026-07-31.
- harness/decisions.py:68 `MAX_DAYS = int(os.environ.get("SYNAPSE_DECISION_MAX_DAYS", 30))`; :181 `return [i for i in items if i["age"] is not None and i["age"] > MAX_DAYS * DAY]`; docstring:7-9 'Exits 6 when any item has waited longer than SYNAPSE_DECISION_MAX_DAYS (default 30). That exit code is the whole point'.
- harness/state/DECISIONS.md:5 — '289 open, 0 older than 30d.' The zero is currently earned by a shared 13-day clock, not by 289 individually-young items. Same structure applies per-receipt-file for the 242 ruling items.

*VERIFIED · risk · effort: small*

### P3.2 passes on a version pin; mcp_server.py:899 still calls the dropped list_tools() API

**Claim.** The CI drift was cured by pinning mcp==1.26.0, not by migrating the code — the dropped decorator is still in source, and pyproject's own comment says the pin must be lifted after migration.

**Why it matters.** The predicate is honestly written and honestly passing, but 'resolved' here means 'deferred with a pin'. The migration debt is real and the pin blocks every future mcp upgrade until it is paid. It is worth naming so the P3.2 PASS is not later read as 'the decorator API was migrated'.

**Action.** ENGINEERING (small): migrate mcp_server.py:899 and the call_tool decorator to the >=1.27 API, then lift the pin to a bounded range. Not urgent — the pin is a valid mitigation and CI is green — but track it, because pyproject's comment is currently the only place the debt is recorded.

**Evidence.**

- `grep -n list_tools mcp_server.py` -> `899:@server.list_tools()` and `900:async def list_tools():` — still present on master.
- pyproject.toml:52-59 — 'mcp = [ # Pinned: mcp >=1.27 dropped Server.list_tools()/Server.call_tool() decorators, which mcp_server.py:899 (@server.list_tools()) and the call_tool decorator ... after migrating mcp_server.py to the new decorator API. See CLEAR P3.2. "mcp==1.26.0",]'
- harness/clear/verify.py:187-189 — `if (not uses_dropped) or pinned: return PASS` — the predicate is satisfied by EITHER branch, so the pin alone clears it. verify.py:168-171 documents this as deliberate: 'Source-level check (CI-vs-local mcp difference makes a pure pytest check dishonest on a green local box)'.
- harness/clear/SPEC.md:18 — P3.2 is stated as 'CI mcp drift resolved (mcp pinned OR `mcp_server.py:899` updated)' — so the OR is contractual, not a verifier bug.

*VERIFIED · unfinished-work · effort: small*

### Four security-critical human-gated tasks (S.1/S.2/S.3/R.9) are unblocked by posture.json but unstarted

**Claim.** harness/tasks.json holds 13 human-gated tasks; the S-track trigger (posture.json) has already fired, yet S.1/S.2/S.3 — which close the consent and RBAC criticals — remain gated, alongside R.9's fail-closed defaults.

**Why it matters.** posture.json declares solo/auto_approve=true, which makes the ungated posture a documented per-mode choice rather than a defect — CLAUDE.md §1.2 says the same. That is defensible today and is the exact thing that must change before any second seat. The relevant fact for this report is that the work is unblocked and unstarted, and R.9 is blocked behind an unratified flywheel cycle rather than behind engineering.

**Action.** HUMAN GATE first (small): decide whether the studio track is in scope at all this cycle — if it is not, say so in the board so S.1/S.2/S.3 stop reading as pending. If it is, R.0 needs ratifying to unblock R.9. The engineering itself (single-source policy table, dispatch-boundary consent, per-connection RBAC) is LARGE and is explicitly 'human-authored, harness-gated' per the task gates.

**Evidence.**

- harness/tasks.json — 13 tasks with human_gate truthy out of 80; 32 crit=True; modes A=58 / B=22.
- harness/state/posture.json (exists, 142 bytes): `{"mode": "solo", "identity_model": "single local artist, one seat on localhost; no multi-user surface exposed", "auto_approve": true}` — S.0's gate says 'Writing posture.json is the S-track trigger', so the trigger has fired and S.1/S.2/S.3 (blocked_on='posture') are unblocked.
- S.2 gate text: 'arm consent on the non-panel bridges + record the consent source ... Closes the #1 critical (consent auto-approve/absent everywhere).'
- S.3 gate text: 'move authn/RBAC to the dispatch boundary keyed by per-connection identity ... Closes criticals 2 + the identity race (SEC-1).'
- R.9 (blocked_on='release_ratified') gate text: 'Closes the shared/bridge.py get_process_bridge disarm S.2 cannot see (`bridge._gate = None` + `consent_callback=lambda op: True`) and the entirely-ungated auth surface (no key ⇒ every token passes; empty Origin ⇒ ...)'. R.0 (release-readiness) is one of the 26 unratified cycles, so release_ratified is false — R.9 is transitively blocked on a flywheel

*VERIFIED · unfinished-work · effort: large*

### The H2 leg halted on a concurrent-writer collision and its four human decisions are still untracked

**Claim.** .claude/h2-halt/H2_HALT_EVIDENCE.md records a live two-agents-one-worktree collision with four explicit 'For the human' items, is untracked in the working tree, and legs H2/H1/F1 remain state='blocked'.

**Why it matters.** F1 (integrate) gates on every evidence-producing leg, and H2 is blocked, so the whole integration line is parked behind an unresolved canonicality question. The evidence recording it is untracked — one clean checkout from gone.

**Action.** HUMAN GATE (trivial to decide, small to execute): rule which H2 run is canonical, then commit or deliberately drop .claude/h2-halt/ so the ruling survives. ENGINEERING (small): reconcile the 18-vs-17 bucket-2 count with a producer path before either number is cited again.

**Evidence.**

- .claude/h2-halt/H2_HALT_EVIDENCE.md:1-6 — 'H2 — HALTED before Part A. Concurrent-writer collision in the dispatch worktree ... Reason: Constitution Article V — two agents in one directory.' Evidence table shows HEAD moving without the agent's action (cherry-pick in reflog), a 17KB instrument appearing, and `set_purpose.py` 'observed modified then restored between calls'.
- Its §3 'For the human' items, none of which appear resolved in any state file: (1) 'Decide which H2 run is canonical and stop the other. Two receipts for one leg is worse than none.' (2) re-dispatch into a fresh worktree off c1d194b. (3) hand §2 to the canonical run. (4) 'the in-flight matrix currently mutates python/synapse/mcp/tool_impls/solaris/*.py in place. If that process is killed mid-cycle
- Two receipts do exist for the one leg: harness/notes/receipts/H2.json (4,658 bytes) and H2b.json (31,578 bytes) — the collision the note warned about.
- harness/legs.json: H2 state='blocked' ('R42/R43: unblocks when residency is gone'), H1 state='blocked', F1 state='blocked' ('Runs LAST - gated on every evidence-producing leg').
- Unresolved numeric delta recorded in the same file: 'Note the count: 18, not 17. RES.json and R43 both say bucket 2 is "~17 tests" ... On this composition the failure count is 18. Whichever H2 run completes should reconcile that delta rather than inherit either number — Law 2, no number without a producer.'

*VERIFIED · risk · effort: small*

### wf_4131d29a-13b-4 worktree holds an uncommitted 24-test L5 draft disjoint from the branch that was rescued

**Claim.** The worktree at .claude/worktrees/wf_4131d29a-13b-4 has uncommitted modifications to harness/verify/checks.py and tests/test_phantom_guardrail.py plus an untracked harness/clear/PROPOSED-P5.1.md; it holds 24 tests whose names do not overlap the 24 tests on clear/l5-phantom-scanner at all (13 unique per side).

**Why it matters.** The branch is chronologically later and was described as the rescue, but the two implementations are structurally different — the worktree draft may cover cases the rescue dropped. Pruning the worktree destroys the only copy.

**Action.** Before pruning wf_4131d29a-13b-4, diff its 13 unique tests against the branch's and confirm nothing was lost in the rescue. Then prune.

**Evidence.**

- git -C .claude/worktrees/wf_4131d29a-13b-4 status --porcelain -> ' M harness/verify/checks.py', ' M tests/test_phantom_guardrail.py', '?? harness/clear/'
- grep -c '^def test_' : master 11, clear/l5-phantom-scanner 24, wf_4131 worktree 24
- comm on test-function names: 13 worktree-only (test_unified_flags_pdg_phantom_when_absent, test_unified_resolves_pxr_alias, ...) and 13 branch-only (test_pdg_camelname_miss_gets_actionable_hint, test_real_h22_table_usdrender_stage_absent, ...) -> zero overlap
- mtimes: worktree checks.py 2026-07-31 10:10:52, test file 10:11:12, PROPOSED-P5.1.md 10:13:20; branch commit eb1e110 at 2026-07-31 13:48:50 -> the worktree draft predates the rescued branch
- wc -l harness/verify/checks.py: master 2769, branch 2818, worktree 2833

*VERIFIED · unfinished-work · effort: small*

### feat/scene-model is 1,967 unlanded insertions, backed up on origin but parked since 2026-07-18

**Claim.** feat/scene-model (1584343) is 2 commits / 11 files ahead of merge-base 0f14c950 and 334 behind master; every one of its source files is absent from master's tree.

**Why it matters.** Real feature work with ~920 lines of tests sitting unmerged for two weeks and drifting 334 commits behind master; the longer it parks the more expensive the eventual rebase.

**Action.** Decide merge-or-close on feat/scene-model. Loss risk is low (origin has it); the cost is rebase drift.

**Evidence.**

- git merge-base/rev-list: 'feat/scene-model | ahead=2 behind=334 | mb=0f14c950 | last=2026-07-18 19:31:24'
- patch-id --stable: 'UNLANDED d02b0ed0 | feat(scene-model): Mile 0 measurement slice', 'UNLANDED 15843434 | fix(scene-model): Mile 0 fix pass'
- git cat-file -e master:<file> -> ABSENT for python/synapse/server/read_ledger.py, python/synapse/panel/turns_ledger.py, python/synapse/core/jsonl_ledger.py, scripts/scene_model_report.py
- diffstat: 11 files changed, 1967 insertions(+), 56 deletions(-) including tests/test_read_ledger.py (495) and tests/test_turns_ledger.py (425)
- upstream tracking: 'feat/scene-model|origin/feat/scene-model|' (in sync, so a remote copy exists)

*VERIFIED · unfinished-work · effort: medium*

### .claude/h2-halt/H2_HALT_EVIDENCE.md carries three unresolved findings and exists in one uncommitted copy

**Claim.** The H2 halt evidence file is untracked, not ignored, and records three still-open items: an 18-vs-17 residency failure-count delta that RES.json and R34 both state as 17, a `pytest -k solaris` oracle that selects exactly one skipping test, and an F1 anchor that may point at the wrong tree.

**Why it matters.** This is the only record of a concurrent-writer collision plus three concrete evidence defects (a wrong pinned count, a vacuous oracle clause, a possibly-stale file anchor). It is one accidental `git clean` from gone, and the findings are exactly the kind this repo re-derives expensively.

**Action.** COMMIT it as harness evidence (e.g. under harness/notes/) rather than dropping it, and file the three findings against the H2/RES ledger.

**Evidence.**

- .claude/h2-halt/H2_HALT_EVIDENCE.md: 'Note the count: 18, not 17. RES.json and R43 both say bucket 2 is "~17 tests" ... On this composition the failure count is 18. Whichever H2 run completes should reconcile that delta rather than inherit either number - Law 2, no number without a producer.'
- same file: '`-k` selects on **test name**, not path. From the repo root it matches **one** test, which skips: 1 skipped, 4508 deselected, 2 errors in 11.59s ... It is a decoration in exactly the sense R34 and Law 1 name, sitting inside the oracle of the leg written to remove decorations.'
- same file: 'This tree also contains **python/synapse/mcp/tool_impls/solaris/{import_megascans,create_variants,set_purpose}.py** - *inside* the package. F1's premise may have changed since L2.'
- git check-ignore -v .claude/h2-halt/H2_HALT_EVIDENCE.md -> NOT-IGNORED; git status shows it as '??' (single uncommitted copy)

*VERIFIED · unfinished-work · effort: trivial*

### panel/routing_log.py ("Phase 5 of the MOE wiring plan") is a complete writer with zero producers

**Claim.** RoutingLog implements log_decision / write_to_usd / apply_learned_fast_paths / _write_native_usd / _write_template_usd, but no code anywhere in python/, shared/, panel, or scripts/ calls any of them, so its decision list is permanently empty and the two panel faces that consume it always silently render nothing.

**Why it matters.** Two UI features an artist would expect — the "ROUTED <primary> + <advisory>" authorship credit on the review face and the routing summary on the work face — are structurally dead, and fail silently rather than showing an error. Session fast-path learning across sessions (the stated point of persisting to agent.usd) also never happens.

**Action.** Decide: either wire a producer (the panel-side MOERouter.route() call site is the natural hook, per shared/router.py) and call write_to_usd() at session end, or delete RoutingLog and the two dead consumer branches. Half-built is the worst of the three states.

**Evidence.**

- python/synapse/panel/routing_log.py:7 — module docstring: "Phase 5 of the MOE wiring plan."
- python/synapse/panel/routing_log.py:54 `def log_decision`, :100 `def apply_learned_fast_paths`, :119 `def write_to_usd`, :236 `def get_routing_log`
- `grep -rn --include=*.py "write_to_usd|\.log_decision\(|apply_learned_fast_paths" python/synapse shared panel scripts` → only the definitions themselves; zero call sites. Repeated against tests/ → zero hits for write_to_usd/apply_learned_fast_paths.
- Consumer 1 python/synapse/panel/face_work.py:298-306 — `decisions = get_routing_log().to_dict().get("decisions", []) ... if not decisions: return ""`
- Consumer 2 python/synapse/panel/face_review.py:534-548 — `refresh_provenance` ... `if not decisions: return` (the ROUTED credit row never renders)

*VERIFIED · unfinished-work · effort: medium*

### Seven agent.usd provenance writers and three readers have zero production callers

**Claim.** log_routing_decision, log_handoff, log_integrity, set_dispatched_agents, resume_task, abandon_task, migrate_to_v2, get_integrity, get_handoff_chain and get_dispatched_agents in python/synapse/memory/agent_state.py are called only from tests/test_agent_state.py; the corresponding agent.usd prims (/SYNAPSE/agent/routing_log, /handoff_chain, /integrity, dispatched_agents) are therefore always empty in production.

**Why it matters.** CLAUDE.md's core promise is "every handoff traceable, every scene state reconstructable" and harness/CLAUDE.md states "Provenance or it didn't happen. ... No ledger entry ⇒ incomplete." The §1.3 IntegrityBlock and the §5 handoff provenance chain never reach agent.usd on any live path. An operator opening agent.usd after a session finds those sections empty and cannot distinguish "nothing happened" from "nothing was recorded."

**Action.** Pick the two that carry the product claim — log_integrity (fed from LosslessExecutionBridge._finalize / server/integrity_envelope.py) and log_handoff — and wire them; mark the rest explicitly reserved-for-future in the module docstring so a future auditor is not re-deriving this. migrate_to_v2 having no caller means any pre-v2 agent.usd on disk silently degrades all three writers to a warn-and-return-"".

**Evidence.**

- Definitions: python/synapse/memory/agent_state.py:168 migrate_to_v2, :299 resume_task, :312 abandon_task, :329 log_integrity, :371 get_integrity, :403 log_routing_decision, :512 log_handoff, :541 get_handoff_chain, :570 set_dispatched_agents, :587 get_dispatched_agents
- Caller sweep over python/ shared/ scripts/ host/ panel (excluding _vendor and agent_state.py itself) returned count 0 for every one of the ten names
- Repo-wide sweep including tests found hits only in tests/test_agent_state.py (e.g. :218 log_routing_decision, :229 log_handoff, :210 log_integrity, :236 set_dispatched_agents, :204 resume_task)
- Contrast — these ARE wired: create_task/update_task_status/write_verification at python/synapse/server/handlers.py:1781,1788,1820,1918-1919,1953-1954; log_session/suspend_all_tasks at python/synapse/mcp/session.py:198-208 and python/synapse/server/websocket.py:603-613
- The prims exist and are created empty: python/synapse/memory/agent_state.py:90-100 (routing_log, handoff_chain, session_history, verification_log, ledger)

*VERIFIED · unfinished-work · effort: medium*

### The default memory backend routes a live MCP tool into code that declares itself SUPERSEDED and "do not extend", while its replacement tool is a no-op

**Claim.** With SYNAPSE_MEMORY_BACKEND unset (verified: default 'jsonl'), the registered MCP tool synapse_evolve_memory dispatches into python/synapse/memory/evolution.py — a module whose own docstring says it is SUPERSEDED by Moneta and "Do not extend it" — while the Moneta-era replacement tool synapse_sleep_pass is documented in the registry as a "No-op under the default jsonl backend."

**Why it matters.** Both memory-maintenance tools an operator can reach are wrong for the shipped configuration: one runs deprecated code the repo forbids extending, the other does nothing at all. Neither surfaces that to the caller at invocation time (sleep_pass says it in the tool description; evolve_memory says nothing). The gating condition — "live async-server (FC4) verification" — is named but there is no in-code marker of whether it has been met.

**Action.** Either flip the default to moneta once FC4 is signed off, or make synapse_sleep_pass return an explicit refusal (not a silent no-op) naming the required env var. Do not leave both memory tools dead-ended by default.

**Evidence.**

- python/synapse/memory/evolution.py:7-15 — ".. deprecated:: Moneta integration (Mile 8) This hand-rolled charmander->charmeleon->charizard USD evolution is SUPERSEDED by the Moneta backend ... It remains live only for the legacy default ``jsonl`` backend and will be removed when ``SYNAPSE_MEMORY_BACKEND`` defaults to ``moneta`` after the live async-server (FC4) verification. Do not extend it."
- python/synapse/server/handlers.py:798 — `reg.register("evolve_memory", self._handle_evolve_memory)`; python/synapse/server/handlers_memory.py:246-248 — `from ..memory.evolution import check_evolution, evolve_to_charmeleon`
- python/synapse/mcp/_tool_registry.py:1076-1081 — synapse_sleep_pass: "Run Moneta consolidation/decay ... No-op under the default jsonl backend."
- Default confirmed: python/synapse/memory/store.py:810 `backend = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl")`; `.env` has no MEMORY_BACKEND entry; `os.environ.get('SYNAPSE_MEMORY_BACKEND')` → None

*VERIFIED · unfinished-work · effort: medium*

### Autonomy driver checkpoints are written three times per run into a dict nothing in production reads

**Claim.** python/synapse/autonomy/driver.py:_checkpoint writes to an in-memory self._checkpoints at three call sites, and _resume reads it, but _resume has zero production callers (only tests/test_autonomy_driver.py:275 and tests/test_forge_integration.py:402,407) — the promised disk persistence ("Phase 3") never landed.

**Why it matters.** An autonomous render loop that dies mid-run — a real scenario given the render-freeze class this repo is actively investigating — has no resume. The operator restarts from the plan stage and re-pays the whole cost. The checkpointing code creates the appearance of crash-resilience that does not exist, and the tests pin the API without pinning the capability.

**Action.** Either persist checkpoints (a JSON sidecar under ~/.synapse/ is enough) and expose a resume entry point on the handler, or delete _checkpoint/_resume and the tests so the driver's crash posture is honest.

**Evidence.**

- python/synapse/autonomy/driver.py:532-536 — `def _checkpoint(...)` docstring: "Checkpoints are in-memory for now. Phase 3 will persist to disk."
- Write sites: driver.py:176 `self._checkpoint("plan_created", ...)`, :221 `self._checkpoint(f"iteration_{iteration}", ...)`, :270 `self._checkpoint("prediction", ...)`
- Read site: driver.py:544-554 `_resume`; caller sweep over python/ shared/ scripts/ → the definition only. Including tests/ → tests/test_autonomy_driver.py:275, tests/test_forge_integration.py:402,407 (tests only).
- driver.py:129 — `self._checkpoints: Dict[str, Dict[str, Any]] = {}` (per-instance, per-run)

*VERIFIED · unfinished-work · effort: medium*

### Three registered COP MCP tools build graphs that produce no output

**Claim.** cops_reaction_diffusion, cops_pixel_sort and cops_bake_textures are registered, dispatchable MCP tools whose handlers create a node graph with a placeholder #define-only kernel, never cook it, and (for bake) never write files — disclosed in both the tool description and the returned payload.

**Why it matters.** An artist who asks for reaction-diffusion or a texture bake gets a graph and a success response. The honesty is present in the payload, but a natural-language agent summarizing the result can easily drop the note and report success. Three of the COP tool surface's headline capabilities are named-but-empty.

**Action.** Leave them registered only if the caller-facing summary path preserves the scaffolded/cooked flags; otherwise move them to PENDING_TOOL_DEFS (the mechanism exists at _tool_registry.py:1541-1558 and is currently empty) until a real kernel body is authored.

**Evidence.**

- python/synapse/mcp/_tool_registry.py:1443 — "Gray-Scott reaction-diffusion solver SCAFFOLD (placeholder #define-only kernel; node not cooked)."
- python/synapse/mcp/_tool_registry.py:1457 — "Pixel-sort scaffold by luminance/hue (placeholder kernel; node not cooked)."
- python/synapse/mcp/_tool_registry.py:1495 — "UV texture baking SCAFFOLD: creates placeholder map nodes; does NOT bake or write files."
- python/synapse/server/handlers_cops.py:1495-1502 — returns `"scaffolded": True, "cooked": False, "note": "Solver graph scaffolded with a placeholder #define-only kernel — no kernel body authored and the node was not cooked; it produces no reaction-diffusion output until a real kernel is written."`
- python/synapse/server/handlers_cops.py:1583-1586 and :1921-1926 — same scaffolded/cooked-false shape for pixel_sort and bake_textures

*VERIFIED · unfinished-work · effort: large*

### Three flywheel tracks (C.0, S.0, R.0) shipped with specs, checks and tests but are unratified; the D-track lead is refuted

**Claim.** harness/state/flywheel_queue.json shows C.0 (context-capability), S.0 (studio-readiness, 24 findings), and R.0 (release-readiness, 12 gates) all with status 'candidate' and ratified:false despite shipped evidence artifacts; D.0 (diagnostic truth) is ratified:true, refuting the briefed claim that the D-track awaits a ratification flip.

**Why it matters.** This is intentional-dormant, not rot — the human gate is a deliberate anti-runaway design. But the cost is real: S.0 wraps 24 verified deployment findings and R.0 wraps 12 release-blocking defects, and neither loop can drive a fix until a one-line human flip. The work is built and idle. Separately, the brief's D-track premise is out of date and should not be carried forward.

**Action.** Treat this as a single human decision item, not engineering work: review C.0/S.0/R.0 and flip or explicitly decline each, recording the reason in harness/state/DECISIONS.md. Correct the D-track premise in any downstream brief.

**Evidence.**

- harness/state/flywheel_queue.json — parsed: U.1 ratified=True, U.2/U.3/U.4 ratified=False, C.0 ratified=False, S.0 ratified=False, R.0 ratified=False, D.0 ratified=True
- S.0 entry evidence list: harness/notes/spec-S-studio-readiness.md, docs/reviews/synapse-studio-readiness-2026-07-06.html, harness/verify/checks.py, tests/test_s_track.py — all shipped; note: "Queued per the anti-runaway anchor for the same sign-off U.5 got."
- R.0 entry note: "The R.R verdict is computable UNRATIFIED via checks.py --task R.R; ratification only lets the loop DRIVE the fixes."
- D.0 entry: `"ratified": true`, note ends "Queued per the anti-runaway anchor for the same human sign-off U.5 received."
- Queue schema doc: "ratified is flipped by a HUMAN only (anti-runaway anchor ...); an unratified candidate is a proposal, never a work order."

*VERIFIED · unfinished-work · effort: trivial*

### RETINA F9 is a real defect at HEAD but the V2 gate it blocks was killed by CTO ruling

**Claim.** The F9 units mismatch (display-referred 0..1 thresholds applied to un-transformed scene-linear HDR) is still present in the tree, but the leg it is recorded as blocking — RETINA V2 — was ruled nonexistent, so 'F9 blocks V2' no longer describes anything actionable.

**Why it matters.** The memory frames F9 as a gating blocker. It is not gating anything — V2 is cancelled. But the defect is still live in shipped code that the panel's render receipt path exercises, so downgrading it to 'not blocking' must not be read as 'not a bug'.

**Action.** Re-file F9 as a standalone correctness bug against retina/t1.py + qc_profiles.toml, decoupled from the dead V2 gate. V0.json:393 already recommends repair (c) as a one-line honesty guard.

**Evidence.**

- retina/ingest.py:158-160 `The beauty plane ... Left un-transformed: it is already linear (``lin_rec709``)` — confirms un-transformed scene-linear pixels at HEAD
- retina/qc_profiles.toml:38-39 `black_threshold = 0.001` / `blown_threshold = 0.999` — the 0..1 display-referred window, unchanged
- retina/t1.py:454-459 `clip_percent(plane, low=profile["black_threshold"], high=profile["blown_threshold"], ...)` — the mismatch seam is intact
- harness/notes/receipts/V0.json F9 entry: severity `SHOWSTOPPER-for-V2`, tier `VERIFIED-RUNTIME`, `blocking: "V2 — the declared gate."`
- harness/notes/CTO_RULINGS_01.md:2817 `**Ruled: RETINA-VERIFY's V2–V4 do not exist as designed.** The mask is the primitive's foundation and Karma does not supply one.`

*VERIFIED · unfinished-work · effort: small*

### D1 render-view is still a no-op, and its stated blocker is pinned to an uninstalled H21 build

**Claim.** _on_open_render is still a deliberate no-op, but the in-code justification cites the H21.0.671 symbol table while the runtime is H22.0.368 — and two of the three symbols in the API chain it declines to write are present in BOTH tables.

**Why it matters.** The claim is still open, so the memory is right — but the rationale is doubly stale: it is pinned to a build that is no longer installed, and it treats a documented table blind-spot as a refutation. A reader could either wrongly conclude the API is missing on H22, or wrongly conclude the halt is obsolete and guess the phantom chain.

**Action.** Keep the halt, but re-ground the comment on H22.0.368 and note that only `hou.ui.curDesktop` is unconfirmable (submodule blind spot) while `hou.paneTabType.IPRViewer` and `hou.Desktop.paneTabOfType` are confirmed on both tables. A single live `hasattr(hou.ui, 'curDesktop')` probe in a graphical session closes D1 — but that probe is a human/live action, not a read.

**Evidence.**

- python/synapse/panel/synapse_panel.py:1366-1380 `def _on_open_render(self):` ... `# D1 (panel finishing harness) — render-view surface is an OPEN ITEM.` ... `hou.ui is absent from the headless H21.0.671 symbol table (unconfirmable)` ... `# Confirmed-API render-view surface intentionally NOT written (D1 halt).` / bare `return`
- synapse_panel.py:899 `self._review_face.open_render_requested.connect(self._on_open_render)` — the button is wired and enabled
- harness/notes/receipts/L3.json:46 `Imports hou, then bare return at :1206. Documented D1 halt. Button is enabled and gives zero feedback.` severity `debt`
- Symbol-table probe (python json load of h21/h22 tables): H22 ver=22.0.368 count=35903 -> `hou.paneTabType` True, `hou.paneTabType.IPRViewer` True, `hou.Desktop.paneTabOfType` True, `hou.ui` False. Identical results for H21 ver=21.0.671 count=33255.
- CHANGELOG.md:279 states the known cause of the hou.ui gap: `the committed symbol table is blind to `hou` submodule members` — so 'absent from the table' is not evidence of absence for hou.ui

*VERIFIED · unfinished-work · effort: small*

### VERIFIED STILL OPEN: rulebook runtime_baseline pinned to uninstalled H21.0.671, and the rulebook has zero ratified sections

**Claim.** rulebook/manifest.json declares houdini_graphical 21.0.671 while the live host is 22.0.368, and its `sections` array is empty — so the meta-tests that would catch drift have nothing to bind against.

**Why it matters.** The rulebook advertises itself as the contract authority but is calibrated to a build nobody runs, on Python 3.11 while the host is 3.13. Its own meta-tests are structurally incapable of noticing, and with sections empty the binding gate passes on the empty set — a green that certifies nothing.

**Action.** Mile 1 harvest must re-baseline manifest.json to 22.0.368 / the live hython / 3.13, and the meta-test should assert the baseline against a probed runtime rather than merely checking key presence. Ratifying is a human gate.

**Evidence.**

- rulebook/manifest.json:3-8 `"runtime_baseline": { "houdini_graphical": "21.0.671", "hython": "21.0.631", "python": "3.11", "platform": "win_amd64" }`
- rulebook/manifest.json:10 `"sections": []` — no ratified content
- rulebook/VERSION -> `0.1.0`
- Live bridge: `mcp__synapse__synapse_ping` -> `{"pong":true,"protocol_version":"4.0.0","timestamp":1785592853.8943064}`; run ground truth pins the host at Houdini 22.0.368 / Python 3.13
- tests/rulebook/test_rulebook_meta.py:121-125 asserts only that the four keys EXIST (`assert {"houdini_graphical","hython","python","platform"} <= set(rb)`) — it never compares them to the live runtime, so the drift is invisible to CI

*VERIFIED · risk · effort: medium*

### CLAIM SPLIT: gate-0.1 is ruled and its contingency executed; the ui/ -> panel/ fold is genuinely still open

**Claim.** gate-0.1 was decided Sidecar on 2026-07-10 with the cp313 re-vendor contingency already executed, so it is closed; but python/synapse/ui/ still ships 8 tracked modules and is deliberately unremoved because tests pin it.

**Why it matters.** Half this claim is dead weight (gate-0.1 has been ruled for three weeks and executed), half is live. Carrying them as one item means the closed half keeps resurrecting the open half's urgency, or vice versa.

**Action.** Split the item: close gate-0.1; keep 'ui/ -> panel/ fold' open with its real blocker recorded (test_v5_features.py:54-82 pins ui/ existence, and panel/ lacks create_panel). Note claude-progress.md:73 already deems the deferral deliberate, not forgotten.

**Evidence.**

- docs/H22_PHASE0_RECONCILIATION.md:57 `VERIFIED (gate-0.1-sidecar-vs-abi3.md:83-91): "DECISION — 2026-07-10 (human sanction): Sidecar" ... The gate is ruled, not pending.`
- CHANGELOG.md:212 `the vendor tree gained a cp313 ABI alongside cp311 (gate-0.1's drop-day contingency — _VENDOR_PYS = {(3,11),(3,13)})`
- CHANGELOG.md:215 `ABI verdict — cp313 ≠ cp311 confirmed gate-0.1 re-opened, and its contingency already executed`
- Live corroboration from the local pytest run's conftest warning: `the bundled native wheels under ...\python\synapse\_vendor ship cp311 + cp313 win_amd64 binaries` — the re-vendor is real on disk
- SYNAPSE_RELEASE_WEEK.md:149 `Gate 0.1 ... is strictly the packaging decision (sidecar vs abi3), not an H22-support gate.`

*VERIFIED · unfinished-work · effort: medium*

### VERIFIED STILL OPEN: feat/scene-model is parked 334 commits behind master

**Claim.** feat/scene-model holds 2 commits not on master and is 334 behind; its Mile 0 artifacts are largely absent from HEAD. The 'CTO ALLOW-with-10-conditions' half of the claim I could not locate.

**Why it matters.** The branch is real and parked, so the work is genuinely unfinished — but 334 commits of drift means a merge is now a rebase-and-re-verify, not a merge. And C0.json independently measured that the linear-token problem the graft was meant to solve is still unmitigated at HEAD (~181 chars/node, no cap).

**Action.** Either rebase feat/scene-model onto master and re-run its Mile 0 instruments, or formally retire the branch and re-file the token-budget problem C0.json:119 measured. Locate or re-issue the CTO conditions before restarting — I found no record of them in the repo.

**Evidence.**

- `git rev-list --left-right --count master...feat/scene-model` -> `334	2` (master ahead 334, branch ahead 2)
- `git log --oneline -5 feat/scene-model` -> `1584343 fix(scene-model): Mile 0 fix pass — honest instruments (3 adversarial reviews applied)` / `d02b0ed feat(scene-model): Mile 0 measurement slice — read ledger, turns ledger, baseline report`
- harness/notes/receipts/C0.json:119 `No delta/diff/dirty engine anywhere at HEAD; \`git merge-base --is-ancestor feat/scene-model HEAD\` -> ANCESTOR-NO and 3 of 4 scene-model artifacts are ABSENT.`
- Searches for the ruling text returned nothing: `git grep -n "ALLOW-with|ALLOW with|10 conditions|ten conditions" -- harness/ docs/ .claude/` -> no output; `grep -n -i "scene.model" harness/notes/CTO_RULINGS_01.md` -> no output; `grep -n -i "scene.model" harness/state/DECISIONS.md` -> no output
- Only file matching scene-model under harness/notes, docs, .claude: harness/notes/receipts/C0.json

*VERIFIED · unfinished-work · effort: large*

### All four U1–U4 instruments remain absent at HEAD f427320

**Claim.** None of the four instrumentation items the report calls 'the unlock-everything-else work' exist in the tree — time-to-first-token, turns-per-build, LLM-stream-duration, and percentiles all return zero grep hits.

**Why it matters.** The dominant cost term is unmeasurable from inside the system, so every latency claim in the authority document stays second-hand. This is the meta-blocker for resolving the 2s floor finding above.

**Action.** Keep U1–U4 as Section 5 item 2, unchanged, and add a fifth instrument: an end-to-end client-observed span, which is the only one that would have caught the 2.01s floor.

**Evidence.**

- `grep -rn "time_to_first_token|ttft|TTFT|first_token" python/synapse/ --include=*.py` -> empty (U1).
- `grep -rn "turns_per_build|turns_total|synapse_turns" python/synapse/ --include=*.py` -> empty (U2).
- `grep -rn "stream_duration|llm_stream|stream_ms" python/synapse/ --include=*.py` -> empty (U3).
- `grep -rn "p95|percentile|quantile" python/synapse/observability/*.py python/synapse/panel/*.py` -> empty (U4).
- Report's claim under test, docs/reviews/synapse-latency-report-2026-07-27.md:69: "The four U1–U4 instruments from the 7-17 report remain the unlock-everything-else work and none have landed." — still true at HEAD.

*VERIFIED · unfinished-work · effort: medium*

### Post-v5.40.1 the executeDeferred wake went from sub-millisecond to a 50–100ms mode on every marshalled call

**Claim.** Production telemetry shows dispatch_wait shifted from all-samples-under-1ms on v5.40.0 to a tight 50–100ms mode on v5.40.1+, with main_thread_direct dropping to zero — a measured latency cost of the freeze fix that post-dates the report's v5.40.0 baseline.

**Why it matters.** The freeze fix traded ~0.5ms inline dispatch for ~53ms marshalled dispatch per call — a correct safety trade, but a real and unrecorded latency regression that the standing report (baseline v5.40.0) cannot know about.

**Action.** Record the trade explicitly so it is not rediscovered as a defect. At ~53ms per call it is far below the 2s floor and should not be optimized until that floor is explained.

**Evidence.**

- v5.40.0, ~/.synapse/logs/freeze_dump_20260730_155705.json: dispatch_waits count=6, max_ms=0.736, buckets {1:6,...} (all <=1ms); main_thread_direct count=363.
- v5.40.0, freeze_dump_20260730_160334.json: dispatch_waits count=5, max_ms=0.736, all <=1ms; main_thread_direct count=363.
- v5.40.1, freeze_dump_20260731_124610.json: dispatch_waits count=107, buckets {1:0,5:0,10:0,50:0,100:94} — 94 of 107 land in (50,100]; main_thread_direct count=0.
- v5.41.0 TODAY, ~/.synapse/logs/telemetry.json (mtime 2026-08-01 10:05:03): dispatch_waits count=29, buckets {1:0,5:0,10:0,50:0,100:29} — 29/29 in (50,100], mean 53.4ms, max_ms=78.46; main_thread_direct count=0.
- Mechanism corroborated by harness/notes/FREEZE_FORENSICS_20260731.md:5 — "`main_thread_direct count=0` post-fix" and :64 — class 3 closed at d15d9b2 via daemon-thread dispatch.

*VERIFIED · latency · effort: trivial*

### The U6 render gate is written against an empty metric while a different metric shows 12x its threshold

**Claim.** U6 fires on render-tool `synapse_tool_duration_ms` p95 > 2000 ms, but tool_durations is empty in every available production artifact, while dispatch_waits — a metric the gate does not read — recorded a 24927 ms max during the freeze the same fix class is meant to prevent.

**Why it matters.** A gate that reads a metric which is structurally always empty can never fire, so U6 is parked by instrument choice rather than by evidence. This is the failure mode the lane brief warned about, inverted: not a met gate, but an unfireable one.

**Action.** Do not build U6 on this basis. Re-state the U6 anchor first (as the 7-17 report already instructs), and decide explicitly whether the gate should read tool_duration, dispatch_wait, or the freeze heartbeat — currently it reads the one surface with no samples.

**Evidence.**

- Exact park condition, LATENCY_PLAN.md:293-296: "build ONLY if `synapse_tool_duration_ms` p95 for render tools (`autonomous_render`/`safe_render`/`render`/`render_sequence`) exceeds **2000 ms** over a real session, OR `_benchmark_latency.py` shows create_node/mutation median above 2000 ms."
- Gate producer is empty: ~/.synapse/logs/telemetry.json today -> `"tool_durations": {}`; and `"session": {"total_commands": 0}`. All five freeze dumps report tool_durations ABSENT ("no live handler" / None).
- Unread metric far past threshold: freeze_dump_20260731_164134.json dispatch_waits count=3262, max_ms=24927.68 — 12.5x the 2000 ms gate number.
- Report already flags the anchor as suspect, docs/reviews/synapse-latency-report-2026-07-17.md:173: "**anchor is STALE** — the '~2 s floor' this gate cites was refuted (1–70 ms, v5.17.0); **re-state the anchor before trusting the gate**."
- Corroborating mechanism, harness/notes/FREEZE_FORENSICS_20260731.md:34 — handlers_render.py:109-113: the panel-inline payload "runs with NO bound of any kind."

*VERIFIED · risk · effort: small*

### Section 5 item 5 (SessionStart ping fix) is DONE in code but has zero consumers

**Claim.** Commit 340db86 genuinely landed the ping gate on the SessionStart hook, so the item is complete as written — but the freeze forensics establishes the verdict is printed to stdout, persisted nowhere, and read by nothing, so the recurring false-start cost it targeted is only removed for a human reading the console.

**Why it matters.** Marking item 5 simply DONE would overstate the benefit. The F6 incident class (workflows trusting a stale 'connected' signal) is only closed for the human-readable path; any programmatic consumer would still need its own probe.

**Action.** Mark item 5 DONE-with-caveat: the lying string is fixed, the incident class is not fully closed for machine consumers. No further work needed unless a programmatic consumer is added.

**Evidence.**

- Code verified at .claude/hooks/synapse_hooks_bridge.py:162-168 — "# F6: ping BEFORE reporting connected. Only claim \"connected\" if the" / `if ping_bridge():` / `print("Synapse bridge connected.")` / else `"Synapse bridge not reachable — "`. `ping_bridge()` defined at :28.
- Commit 340db86 message: "add ping_bridge() — a real stdlib socket.create_connection probe to the Synapse WS port (honoring SYNAPSE_HOST/SYNAPSE_PORT, 1.5s timeout) — and gate the SessionStart 'connected' report on it."
- Inertness, harness/notes/FREEZE_FORENSICS_20260731.md:53 — "h6-p31 — ping gate. Commit `340db86` touches only `.claude/hooks/synapse_hooks_bridge.py` (a subprocess); the ping verdict is printed to stdout, persisted nowhere, zero consumers. Per-tool-call availability is `hou.webServer.port()` at `python/synapse/panel/tool_executor.py:154-159`, not SessionStart."
- Report item under test, docs/reviews/synapse-latency-report-2026-07-27.md:79: "**Fix the SessionStart connected-check to ping** — cheap, removes a recurring false-start cost."

*VERIFIED · unfinished-work · effort: trivial*

### Three load-bearing citations in the report are stale or second-hand at HEAD

**Claim.** The report's central '~95% / 1–70 ms' anchor points at a line that no longer holds it and is a changelog assertion rather than primary data; its serial-loop citation points at the auth block; and its module paths omit the package directories.

**Why it matters.** The report is the standing authority and is behind a human gate, so readers cannot self-correct. The 95% figure in particular is the premise for the entire 'not a transport problem' conclusion, and it resolves only to a changelog sentence.

**Action.** When the human gate opens, repoint CHANGELOG.md:293 -> :441, repoint websocket.py:471-484 -> :103/:546, and add package paths. Flag the 95% figure as changelog-sourced pending the item-1 re-measure.

**Evidence.**

- Stale line: report cites `[PRIOR — CHANGELOG.md:293, v5.17.0]`. `sed -n '288,296p' CHANGELOG.md` returns composition-validation and bridge-fix text, no latency figures. The actual claim is at CHANGELOG.md:441 — "A live-measured investigation found the dominant cost is the **LLM turn (~95%)**; Houdini ops run **1–70 ms**" — inside the v5.17.0 section whose header is at :423.
- Second-hand producer: CHANGELOG.md:441 asserts a measurement; no primary artifact (session dump, benchmark output) is cited anywhere for the 95% figure.
- Stale line: report F7 cites `websocket.py:471-484` for the serial `for message in websocket:` loop. `sed -n '468,486p' python/synapse/server/websocket.py` at HEAD is the auth_required handshake block. The pump is now `for message in iter_messages(websocket, cancel_event):` at :546, with iter_messages defined at :103.
- Path drift: report cites `graph_builder.py:131-160` and `graph_validator.py`; actual paths are python/synapse/host/graph_builder.py and python/synapse/cognitive/graph_validator.py.
- Verified-good citations (for contrast): claude_worker.py:34 `_MAX_TOOL_ITERATIONS = 25` exact; main_thread.py:20 `_DEFAULT_TIMEOUT = 10.0` exact; LATENCY_PLAN.md:25 "HDL: createNode() ~5-20ms" exact; LATENCY_PLAN.md:195 hwebserver ping 2070ms exact; docs/LATENCY_SOLARIS_REVIEW.md:96,:209 the 25-turn figure exact.

*VERIFIED · hygiene · effort: trivial*

### 1 of 13 pings lost the connection outright while health reported healthy

**Claim.** My third sequential synapse_ping returned a connection-loss error rather than a pong, between successful pings at 1785592658.24 and 1785592669.80 - an 11.6 s gap. synapse_health called minutes later still returned healthy:true and the circuit breaker stayed closed at state 0 throughout.

**Why it matters.** A 7.7% ping-drop rate on an otherwise idle bridge means any workflow that trusts a prior 'connected' signal will intermittently pay a full timeout-and-diagnose cycle. This is an independent live reproduction of the class the latency report calls F6, and neither the health endpoint nor the circuit breaker registered it.

**Action.** Instrument transport-level drops as a counter (synapse_ws_reconnects_total or similar). Today a dropped connection leaves no trace in metrics at all, so the drop rate is only observable by a human noticing a failed call.

**Evidence.**

- synapse_ping (attempt 3) -> "Couldn't reach Synapse - Lost connection while sending ping and couldn't reconnect: Connection lost during ping"
- synapse_ping (attempt 2) -> timestamp 1785592658.2410061
- synapse_ping (attempt 4) -> timestamp 1785592669.8037717
- synapse_health -> {"healthy":true,"houdini_available":true,"protocol_version":"4.0.0"}
- synapse_metrics -> synapse_circuit_breaker_state 0 in all three scrapes

*VERIFIED · risk · effort: small*

### Uptime, sessions, commands-per-minute and total-commands all report zero after ~19 hours and 33,927 dispatches

**Claim.** synapse_uptime_seconds is 0.0, synapse_sessions_active 0, synapse_commands_per_minute 0.0, synapse_memory_entries_total 0, and live_metrics session.total_commands 0 - on a bridge published 2026-07-31T18:40 UTC that has serviced 33,927 main-thread dispatches and 42 recorded tool calls.

**Why it matters.** Throughput and uptime are the denominators for every rate you would want to compute. With all of them pinned at zero you cannot express latency per command, dispatches per session, or degradation over uptime - I had to derive the dispatch rate by hand from ping-anchored counter deltas because no rate metric exists.

**Action.** Wire uptime_seconds and total_commands to real sources. Until then, treat every rate in any latency document as hand-derived and note the derivation method inline.

**Evidence.**

- synapse_metrics (all 3 scrapes) -> synapse_uptime_seconds 0.0 ; synapse_sessions_active 0 ; synapse_commands_per_minute 0.0
- synapse_live_metrics -> "session":{"active_sessions":0,"commands_per_minute":0.0,"deploy_mode":"local","rbac_enabled":false,"total_commands":0}
- synapse_live_metrics -> "resilience":{...,"uptime_seconds":0.0} while the same response carries "timestamp":84306.466
- synapse_doctor -> bridge_endpoint published 2026-07-31T18:40:36Z ; log_file mtime 2026-08-01T13:58:50Z (~19.3 h apart)

*VERIFIED · missing-instrumentation · effort: small*

### Queue depth drives backpressure decisions but is never exported

**Claim.** BackpressureController.evaluate is fed self._command_queue.size() and compares it against a queue_critical threshold, but no queue-depth or backpressure-level metric appears in metrics.py's export list or in any live scrape.

**Why it matters.** When the bridge sheds load it tells the user 'Synapse is under heavy load right now', but the input that triggered that decision is invisible. You cannot tell whether a slow turn was queue saturation or main-thread stall, which is exactly the discrimination the freeze investigation needs.

**Action.** Export a synapse_command_queue_depth gauge and a synapse_backpressure_level gauge from the same call site that already reads queue.size() at websocket.py:835.

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/server/websocket.py:834-835 self._backpressure.evaluate(queue_size=self._command_queue.size(), ...)
- C:/Users/User/SYNAPSE/python/synapse/server/resilience.py:695-697 if queue_size >= self.config.queue_critical: return self._level, {"reason":"queue_critical",...}
- C:/Users/User/SYNAPSE/python/synapse/mcp/server.py:196 def __init__(self, max_queue_size: int = 100)
- grep of all 18 lines.append("# HELP ...") in metrics.py -> no queue, depth, or backpressure metric among them
- synapse_live_metrics -> resilience block exposes circuit_state, trip_count, rate_limit_rejects, rate_limiter_active - no queue depth

*VERIFIED · missing-instrumentation · effort: trivial*

### Main-thread timeouts are counted only consecutively and reset on the next success, so session totals are unrecoverable

**Claim.** _consecutive_timeouts is incremented on timeout and reset to 0 by _record_success on the very next successful marshal; only last_timeout_ts survives. No cumulative timeout counter is exported to Prometheus, so the number of main-thread timeouts in a session cannot be recovered.

**Why it matters.** A timeout that happened 146 seconds before I measured already reads as consecutive_timeouts 0. The system structurally forgets how often it froze. Any claim about freeze frequency - including 'the freeze is fixed' - has no counter to check against.

**Action.** Add a monotonic synapse_main_thread_timeouts_total counter alongside the existing consecutive-timeout stall gate. The stall gate needs the resetting counter; observability needs the monotonic one. They are different instruments.

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/server/main_thread.py:189-195 _record_timeout increments _consecutive_timeouts and sets _last_timeout_ts
- C:/Users/User/SYNAPSE/python/synapse/server/main_thread.py:199-201 _record_success sets _consecutive_timeouts = 0
- C:/Users/User/SYNAPSE/python/synapse/server/main_thread.py:323 _record_success() called on every successful marshal
- synapse_doctor -> stall {"consecutive_timeouts":0,"last_timeout_ts":1785592504.5058525} - a timeout demonstrably occurred yet the count reads 0
- synapse_metrics (3 scrapes) -> no timeout counter of any name in the exported text

*VERIFIED · missing-instrumentation · effort: trivial*

### Dispatch-wait bucket edges cannot resolve the floor between 10 and 50 ms, nor anything above 4 s

**Claim.** _DISPATCH_WAIT_BUCKETS_MS is (1,5,10,50,100,250,500,1000,2000,4000). With 99.06% of live samples landing in the single (50,100] bin and the max at 17,167 ms falling into an opaque (4000,+Inf] bin holding 2 samples, the histogram cannot locate the floor more precisely than a 50 ms-wide bin nor characterise the multi-second tail at all.

**Why it matters.** The dominant bin is 50 ms wide and holds essentially all traffic, so the histogram cannot show whether a fix moved the floor from 90 ms to 55 ms. At the other end, everything from 4 s to 17 s collapses into one bin, so the freeze tail has no shape. Both ends of the distribution that matter are the two the buckets resolve worst.

**Action.** Add edges at 20, 30, 60, 80 to resolve the floor and at 8000, 16000, 32000 to give the freeze tail shape. Also stamp the max sample with a timestamp so the worst stall is correlatable.

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/server/main_thread.py:48 _DISPATCH_WAIT_BUCKETS_MS = (1, 5, 10, 50, 100, 250, 500, 1000, 2000, 4000)
- synapse_metrics @C -> {le="4000"} 33925 ; {le="+Inf"} 33927 -> exactly 2 samples between 4 s and the 17,167 ms max
- Live window A->C: 105 of 106 samples in the single (50,100] bin - no sub-bin resolution available
- synapse_metrics -> synapse_dispatch_wait_ms_max 17167.1001 carries no timestamp and never decays across scrapes

*VERIFIED · missing-instrumentation · effort: trivial*

### MetricsAggregator is ~96% of all main-thread marshals and does an unconditional full-scene walk every 2 s with no consumers

**Claim.** The metrics daemon marshals a full hou.node('/').allSubChildren() traversal onto Houdini's main thread every 2 seconds regardless of whether any client reads metrics, and it accounts for essentially all main-thread marshal traffic in an idle session.

**Why it matters.** On the 9-node default scene this is free, which is why it has never surfaced. On a production scene the same code inserts an O(N) Python traversal plus 2N error/warning queries onto the artist's main thread every 2 seconds, forever — a periodic GUI hitch and direct contention with every command marshal. It also means the dispatch-wait histogram, the project's only marshal instrument, is measuring the aggregator rather than user work unless that is accounted for.

**Action.** Gate the collector on an actual subscriber (panel open / metrics command seen recently), or make the scene walk adaptive: cache the node census and refresh it only when a cheap signal changes. Measure on a real production hip before choosing — I could not, since the only live scene is 9 nodes.

**Evidence.**

- Attribution control, session B: 181 heartbeats at heartbeat_interval=1.0 (python/synapse/server/resilience.py:521,609) => 181 s uptime; expected 2 s polls = 90.5; observed dispatch_waits count = 87 (96 %). tool_durations contains only {'ping'} — zero user commands ran. So every recorded marshal is the metrics poll.
- Same ratio at scale in session A: 69,483 heartbeats => ~19.3 h; expected polls 34,741; observed dispatch_waits 33,833 (97.4 %).
- python/synapse/server/live_metrics.py:91 `_DEFAULT_INTERVAL = 2.0`; :186 `self._stop_event.wait(self._interval)`; :218-254 `_gather()` iterates `for node in hou.node("/").allSubChildren():` calling `node.warnings()` and `node.errors()` per node; :255 `return run_on_main(_gather, timeout=_SCENE_COLLECT_TIMEOUT)`.
- Started unconditionally on the shipped transport: python/synapse/server/hwebserver_adapter.py:316-318 `_metrics_aggregator = MetricsAggregator(); _handler.set_metrics_aggregator(...); _metrics_aggregator.start()`. No subscriber check anywhere.
- No consumer in the same snapshot: session A live_metrics_latest shows session.total_commands=0, session.active_sessions=0, routing.total_requests=0.

*VERIFIED · latency · effort: small*

### Every bridge stage hash runs a full stage.TraverseAll() whose result is provably always False, then Flattens anyway

**Claim.** _hash_stage_signature calls _stage_exceeds with a threshold of 2^62, so the probe iterates the entire USD stage counting prims, can never reach the early-exit, always returns False, and the code then executes the full Flatten path it would have executed regardless.

**Why it matters.** On the Solaris path — the headline path, and the one where hash_target is a LOP with a stage — every bridge operation pays two full Python-level traversals of the composed stage for a boolean that is a compile-time constant. The cost scales with prim count on exactly the scenes where latency is already worst, and it buys nothing.

**Action.** Early-return False from _hash_stage_signature when _stage_hash_prim_threshold() is the unbounded default, before calling _stage_exceeds. Behaviour is bit-identical; only the wasted traversal disappears. Note shared/bridge.py:1937 is a second _stage_exceeds call site and should be checked for the same condition.

**Evidence.**

- shared/bridge.py:404 `_DEFAULT_STAGE_HASH_PRIM_THRESHOLD = 1 << 62  # effectively unbounded => Flatten always`
- shared/bridge.py:809 `large = self._stage_exceeds(stage, _stage_hash_prim_threshold())`
- shared/bridge.py:825-833 `def _stage_exceeds(stage, threshold): n = 0; for _ in stage.TraverseAll(): n += 1; if n > threshold: return True; return False` — the early exit requires n > 2^62, so the loop always runs to exhaustion.
- shared/bridge.py:821 `flat = stage.Flatten().ExportToString()` — the path actually taken, unchanged.
- The comment at shared/bridge.py:399-403 confirms the default is deliberate ('Structural stage-hash is OPT-IN, OFF by default'), so the wasted probe is an unintended side effect of that decision, not the decision itself.

*VERIFIED · latency · effort: trivial*

### The project's richest latency dataset is atomically overwritten every session and was destroyed mid-investigation

**Claim.** telemetry.json is a single-file periodic atomic overwrite with no rotation, so each Houdini restart destroys the accumulated dispatch-wait, scene-hash and tool-duration histograms of the prior session.

**Why it matters.** The instrument works and the data is good — it just does not survive. Every latency question the project asks has to wait for a fresh session to re-accumulate, which is exactly why the C6/T1 attribution stayed open for months. Retaining one file per session would have closed it without any new instrumentation.

**Action.** Add a timestamped session-final flush on shutdown (or roll telemetry.json to telemetry_<pid>_<ts>.json before overwrite, mirroring the freeze-dump naming that already exists in the same module). Retention policy can be trivial — keep the last N.

**Evidence.**

- python/synapse/server/telemetry_dump.py:200-219 `def flush_telemetry(reason='periodic', ...)` -> `if reason == 'periodic':` atomic overwrite of telemetry.json (tmp + os.replace); only non-periodic reasons get a timestamped file.
- Observed live during this analysis: `ls -la ~/.synapse/logs/` at ~10:00 EDT showed telemetry.json mtime 09:58 containing pid 56116 / 33,833 dispatch-wait samples; `stat` at 10:07 EDT showed mtime 10:07:03 and the file now contained pid 3696 / 87 samples. The 33,833-sample dataset no longer exists on disk.
- Only the freeze-triggered dumps persist with timestamps: freeze_dump_20260730_155705.json, _20260730_160334.json, _20260731_124610.json, _20260731_164134.json, _20260801_014600.json — i.e. history survives only for freezes, never for healthy sessions.
- Consequence is concrete: the 2026-07-27 latency report §5 lists the dispatch-wait re-measure as the top open action while a 33,833-sample answer was sitting in this file and has since been overwritten.

*VERIFIED · hygiene · effort: trivial*

### The Claude Code MCP client holds one shared WebSocket connection, so the mapped 'escape is per-connection only' mitigation does not apply to it

**Claim.** mcp_server.py multiplexes every tool call over a single module-global WebSocket connection, so the per-connection escape hatch that docs/sprint_freeze/marshal_map.md identifies as the mitigation for head-of-line blocking is structurally unavailable to the registered MCP client — including the render_in_progress poll during a 60 s bounded render.

**Why it matters.** If hwebserver dispatches SynapseWS.receive per-connection rather than per-message, then a 60 s bounded render from Claude Code blocks Claude Code's own poll of that render, and the token mechanism that makes the bounded render 'responsive' does not work for the client that most needs it. Separately, _MUTATION_LOCK (python/synapse/server/handlers.py:250,511) serialises mutating commands process-wide for the render's full 60 s hold regardless of transport, which is a real cross-client ceiling.

**Action.** Answer the question the repo's own map leaves open (docs/sprint_freeze/marshal_map.md:600, 'Same question for SynapseWS.receive — confirms the WS path'): probe whether hwebserver serialises per connection. If it does, have mcp_server.py open a second short-lived connection for poll/cancel/status commands — small change, and it restores the mitigation the design already assumes.

**Evidence.**

- Registered server is the stdio bridge: .mcp.json -> {"synapse": {"type": "stdio", "command": "python", "args": ["mcp_server.py"]}}.
- Single shared connection: mcp_server.py:202 `_ws_connection = None` (module global); :257 `async def _get_connection()` returns that singleton for every call; :322-327 `send_command` docstring — 'Supports true parallel dispatch -- multiple concurrent send_command calls share a single recv loop that routes responses by ID.' Client-side concurrency is real; it is all on one connection.
- The mapped mitigation: docs/sprint_freeze/marshal_map.md:177-178 — 'The stall exemptions ... and render_farm_cancel's read-only classification bypass the C5 lock and the resilience gates but not the serial loop. Escape is per-connection only — a cancel on a second connection gets its own thread and proceeds.'
- The escape that depends on it: a bounded render holds its caller for up to 60 s (python/synapse/server/handlers_render.py:57 `_RENDER_WAIT_BUDGET_S = 60.0`; :603 `worker.join(timeout=wait_budget)`) and hands back a render_in_progress token to be polled; the poll's exemptions are applied only after the message is dequeued (python/synapse/server/handlers.py:506-508 and python/synapse/server/websocke
- Scope correction I had to make mid-analysis: the serial loop at python/synapse/server/websocket.py:546-559 is on the LEGACY transport. The shipped one is hwebserver (python/synapse/server/hwebserver_adapter.py:330-335, `hwebserver.run(..., in_background=True, max_num_threads=4)`), whose own comment at :309-312 calls websocket.py 'legacy' and hwebserver 'this dominant hwebserver path'. The panel fo

*INFERRED · risk · effort: small*

### Freeze dumps are stamped UTC while logs are local — the newest dump reads as post-diagnosis but is a pre-release pytest artifact

**Claim.** `freeze_dump_20260801_014600.json` appears to postdate the diagnosis commit but is 2026-07-31 21:46 local, 34 minutes BEFORE it, and its surrounding log window carries the pytest fingerprint — so it is not a production freeze.

**Why it matters.** I nearly reported this dump as 'the freeze recurred after the diagnosis was written' — a false alarm that would have misdirected the fix. Anyone triaging by `ls ~/.synapse/logs/` will hit the same trap, and it compounds with the known pytest log pollution. The last VERIFIED production freeze is 2026-07-31 12:41 local, before the diagnosis.

**Action.** Stamp freeze dump filenames in local time, or add a `local_ts` field alongside `ts` in `collect_telemetry()`. Separately, have `flush_telemetry` record whether it ran under pytest so test-authored dumps are self-identifying.

**Evidence.**

- python/synapse/server/telemetry_dump.py:242 — `stamp = datetime.now(timezone.utc).strftime(...)` — filenames are UTC
- Offset confirmed against the doc-cited dump: log line 18697 `2026-07-31 12:41:35,324 [synapse.freeze_chain] ERROR: Freeze evidence dumped: ...freeze_dump_20260731_164134.json` → 16:41 UTC = 12:41 local, UTC-4
- So `20260801_014600` UTC = 2026-07-31 21:46 local; f427320 committed 2026-07-31 22:20:00 -0400
- Pytest fingerprint in that window: log lines 18767-18773 at 21:46:49 show `Cannot start hwebserver: hwebserver not available — must run inside Houdini` and repeated `Write flush error ... C:\Users\User\AppData\Local\Temp\tmptcdd44fh\project\.synapse\memory.jsonl` — tmpdir paths, not a Houdini session
- Dump internals agree: `synapse_version = 5.40.1` (the tree's value until 8dfa23d at 21:48:32), `total_heartbeats = 1`, `dispatch_waits.count = 0`, `main_thread_direct.max_ms = 11.6` — no real WS traffic, no long payload

*VERIFIED · risk · effort: trivial*

### The misattributing 'ran Xms on the main thread' log string is not just unfixed — a passing test pins it

**Claim.** `_dispatch` is shared by the main-thread slot and the off-main daemon path but logs 'on the main thread' unconditionally, and `tests/test_panel_preflight.py` asserts that exact wording, so the forensics doc's remediation item 2 would break a green test.

**Why it matters.** Two of the three 07-31 numbers a reader would take as main-thread grip are queue-wait timeouts. This corrupted the last forensics run (the doc says so) and will corrupt the next one — and the fix now carries a test-breaking cost, which makes it likelier to be deferred again.

**Action.** Pass a flag through `_dispatch` distinguishing slot-vs-daemon and branch the message ('held the main thread' vs 'dispatch took'), then update tests/test_panel_preflight.py:248-262 to assert the discriminating label rather than the shared substring.

**Evidence.**

- python/synapse/panel/tool_executor.py:472-479 — the warning inside `_dispatch`'s `finally`: "Inline tool %r ran %.0fms on the main thread (Qt loop stalled this long; slow threshold %.0fms)"
- Both callers share it: :390 `self._dispatch(request, emit_preflight=True)` (main-thread slot `execute_tool`) and :517 `self._dispatch(request, emit_preflight=False)` (`execute_tool_off_main`, daemon)
- tests/test_panel_preflight.py:259 — `slow_logs = [r for r in caplog.records if "ran" in r.message and "main thread" in r.message]` then `assert slow_logs`
- MISATTRIBUTION PROVEN WITH LIVE DATA: ~/.synapse/logs/synapse.log records `2026-07-31 08:44:41,290 ... 'houdini_create_node' ran 10005ms on the main thread` and `2026-07-31 08:46:26,765 ... 'synapse_inspect_scene' ran 10005ms on the main thread` — both exactly 10005ms, i.e. run_on_main's `_DEFAULT_TIMEOUT` of 10.0s (main_thread.py:20) plus overhead. Those are queue-wait TIMEOUTS reported as main-t
- Same defect inflates the headline number: `2026-07-31 12:51:49,705 ... 'houdini_set_parm' ran 46724ms on the main thread` is daemon wall-time, not 46.7s of GUI grip

*VERIFIED · risk · effort: small*

### The class-3 inline wire is still connected with zero production emitters and zero tests preventing one

**Claim.** `worker.tool_requested` is declared and connected to the main-thread `execute_tool` slot but never emitted in production, and no test asserts that — a single `.emit()` re-arms the Class 3 freeze.

**Why it matters.** Class 3 is the one class with a verified fix. This is the single line that can undo it, and nothing in CI would notice. A future contributor restoring the 'signal path' for a plausible reason reopens a closed freeze.

**Action.** Cheapest durable fix is a source-lint test in the style of test_marshal_lint.py asserting zero `tool_requested.emit` in python/synapse — or simply delete the connect at synapse_panel.py:1938 since it has no emitters.

**Evidence.**

- python/synapse/panel/claude_worker.py:84 — `tool_requested = Signal(object)`
- python/synapse/panel/synapse_panel.py:1938 — `self._worker.tool_requested.connect(self._tool_executor.execute_tool)`
- `grep -rn 'tool_requested' python/ tests/` → 6 hits total, all in claude_worker.py (declaration + 3 comments) and the one synapse_panel.py connect. Zero `.emit(` calls, zero test references.
- The slot it targets is the freeze path: tool_executor.py:377-392 `execute_tool` docstring states it 'runs on the thread that owns the ToolExecutor (the main thread)'
- Named as remediation item 3 in harness/notes/FREEZE_FORENSICS_20260731.md:90-92 with the exact pin requested: 'regression test asserting no production emitter of tool_requested; or disconnect the wire'

*VERIFIED · risk · effort: trivial*

### The websocket disconnect handler calls hou.* off the main thread with no marshal

**Claim.** `_handle_client`'s `finally` block calls `hou.hipFile.path()` and `hou.getenv` directly on the WS handler thread, outside any `run_on_main` marshal.

**Why it matters.** Every other hou.* touch in the server layer is marshalled; this one is not, and it fires on every disconnect. CLAUDE.md §11 rule 3 ('All hou.* calls via hdefereval') is violated here. It is the kind of latent violation that produces an unreproducible crash rather than a clean error.

**Action.** Wrap the two reads in `run_on_main` with a short timeout, or pre-cache hip/job path at connect time on the main thread and read the cache in the finally block.

**Evidence.**

- python/synapse/server/websocket.py:604-606 — `if HOU_AVAILABLE:` / `hip_path = hou.hipFile.path()` / `job_path = hou.getenv("JOB", os.path.dirname(hip_path))`
- These sit inside the `finally:` at :567 of the client handler, which runs on the connection's own thread — the same thread that took the off-main deferred path for every command
- Downstream at :607-624 the block then calls `ensure_scene_structure`, `suspend_all_tasks`, `log_session`, `write_session_end`
- Wrapped only in a broad `except Exception` at :625-626 that logs a warning — a thread-safety violation would degrade silently, not fail loud
- Named as remediation item 4 in harness/notes/FREEZE_FORENSICS_20260731.md:93-95; refuted as the 07-31 cause but explicitly retained as a standing hazard ticket

*VERIFIED · risk · effort: trivial*

### The marshal ban lint scans only python/synapse and shared — repo-root and six other shipped trees are outside the guardrail

**Claim.** `test_marshal_lint._SOURCE_ROOTS` covers two directories, leaving mcp_server.py, mcp_tools_*.py, houdini/, scripts/, retina/, forge/, agent/, and host/ unguarded against the blocking marshal and the H22 phantom.

**Why it matters.** The lint is the only thing keeping Class 2 closed. Its authors deliberately made the allowlist line-scoped to kill a blind spot (:98-102) but left a larger one at the root level. mcp_server.py in particular is a Houdini-facing dispatch surface where a blocking marshal would be a natural mistake.

**Action.** Add the repo root (non-recursive, for the mcp_*.py modules) plus houdini/, host/, agent/, retina/, and forge/ to `_SOURCE_ROOTS`. It should stay green today, which makes it a zero-risk widening.

**Evidence.**

- tests/test_marshal_lint.py:73-76 — `_SOURCE_ROOTS = (_REPO_ROOT / "python" / "synapse", _REPO_ROOT / "shared",)`
- Uncovered trees confirmed to exist and ship: repo-root `mcp_server.py`, `mcp_tools_render.py`, `mcp_tools_usd.py`, `mcp_tools_cops.py`, `mcp_tools_tops.py`, `mcp_tools_memory.py`, `mcp_tools_scene.py`, plus houdini/, scripts/, retina/, forge/, agent/, host/
- Currently CLEAN — I scanned each individually for `executeInMainThreadWithResult|executeInMainThread\b|_queueDeferred` and found zero hits — so this is a coverage gap, not a live violation
- The lint's own docstring at :35-38 states its intent is to 'run on every CI invocation' as the structural half of the L8 fix

*VERIFIED · risk · effort: trivial*

### On the main-thread caller path a render runs inline with no bound, and a passing test pins that as an invariant

**Claim.** When the caller IS the main thread, `_handle_render_bounded` branches to a direct inline `_handle_render` with no wait budget and no render session, and `test_main_thread_caller_renders_inline` pins the no-session behaviour.

**Why it matters.** This is the true residual of Class 1 and the code is honest about it — nothing in Python can interrupt the main thread from the main thread. The practical exposure is now smaller because PR #50 moved panel dispatch off-main, so the /mcp read-only dispatch is the main remaining way to reach it. But the foreground guard (foreground_guard.py) is the only protection, and once a render starts there is no stop.

**Action.** Do not retune the timeouts (the comment at :130-132 is right). Close the double-render hazard instead by registering a render_session around the inline call, which requires re-negotiating the invariant that test_render_bounded.py:224 pins — a decision for that test's owner.

**Evidence.**

- python/synapse/server/handlers_render.py:517 — `if _threading.current_thread().ident == _MAIN_THREAD_ID:` → :543 `return _attach_advisory(self._handle_render(payload))` with only telemetry in the `finally`
- handlers_render.py:109-113 states it plainly: 'the payload runs inline with NO bound of any kind. That is honest by construction... The panel freezes for the render's duration.'
- handlers_render.py:530-540 — the residual note: registering a render_session here would make retry-after-false-timeout safe, but is not done because `tests/test_render_bounded.py::test_main_thread_caller_renders_inline` pins `rs.summary() == []`
- tests/test_render_bounded.py:224 `test_main_thread_caller_renders_inline` — passes at HEAD (part of the 32-test green run)
- Abandon-then-continue hazard documented at handlers_render.py:115-128: on /mcp the outer 120s marshal reports FAILURE while the render continues and writes the frame; a retry double-renders

*VERIFIED · freeze · effort: medium*

### The attached scene is an empty default untitled.hip — the assigned load test applied no load

**Claim.** Contrary to the brief's statement that the bridge is attached to a real artist's scene, the session holds a virgin default untitled.hip from the Houdini install directory containing 9 manager nodes and zero SOP, LOP, or OBJ nodes, so my heavy-read load test could not generate meaningful load.

**Why it matters.** Steps 2 and 3 of my assigned protocol are void: I measured heavy-read behaviour against a 10-node empty scene, which is why /mcp looked clean. A negative load result here is not evidence of absence. Any conclusion drawn from my load test alone would be a false negative, and the brief's premise that a real artist scene was attached is incorrect.

**Action.** Re-run the load test only against a scene with real node counts before accepting any /mcp latency conclusion. Do not record my clean load result as a pass.

**Evidence.**

- synapse_live_metrics scene block: `"hip_file": "C:/Program Files/Side Effects Software/Houdini 22.0.397/bin/untitled.hip"`, `"total_nodes": 9`, `"sop_nodes": 0`, `"lop_nodes": 0`, `"obj_nodes": 0`
- synapse_inspect_scene(max_depth=5) returned only root + the 9 stock managers (obj, out, ch, shop, img, vex, mat, stage, tasks); `"issues": []`, `"artist_notes": []`
- synapse_metrics gauge: `synapse_scene_nodes_total 9`
- Stable across 3 historical snapshots (timestamps 84509.794, 84511.846, 84513.897) — not a transient state

*VERIFIED · risk · effort: small*

### Running build differs from the brief on both Houdini and SYNAPSE version; doctor reports 3 failing checks including a stale symbol table

**Claim.** The live session runs Houdini 22.0.397 and SYNAPSE 5.40.1 with an install stamp claiming 5.23.0, not the Houdini 22.0.368 / SYNAPSE v5.41.0 asserted in the run brief, and synapse_doctor returns 3 FAIL / 6 ok / 1 skipped.

**Why it matters.** Three ground-truth facts handed to every agent in this run are wrong, so any lane that trusted the stated build without checking has drawn conclusions about code that is not running. The stale symbol table is a cross-lane hazard specifically: it is stamped for 22.0.368 while 22.0.397 is live, which undermines any phantom-sweep or symbol-authority verdict produced this run.

**Action.** Correct the run's ground-truth block, and re-validate any symbol-table-dependent finding from other lanes against the 22.0.397 runtime before ratifying.

**Evidence.**

- synapse_doctor version check, status fail: `synapse 5.40.1 / protocol 4.0.0; install stamp says 5.23.0 — installed tree and stamp disagree`
- synapse_doctor symbol_table check, status fail: `stamp 22.0.368 (35903 symbols, blake2b 265b433af49698ab8654db4340b6f489) != running 22.0.397 — regenerate via host/introspect_runtime.py (scout distrusts a version-mismatched table)`
- synapse_doctor moneta_substrate check, status fail: `registered=False ... PXR_PLUGINPATH_NAME is unset`
- telemetry.json and every freeze_dump both report `"synapse_version": "5.40.1"`
- synapse_doctor summary: `{"fail": 3, "ok": 6, "skipped": 1}`

*VERIFIED · risk · effort: small*

### Bridge connection dropped outright mid-probe on a bare ping

**Claim.** Ping 3 of my 5-ping baseline failed with a hard connection loss and no successful reconnect on that attempt, while the Houdini side remained demonstrably alive throughout.

**Why it matters.** A bare ping — the cheapest possible call — dropped during a short probe window, and the failure was in the transport rather than in Houdini. Combined with the one-connection-per-call finding, this suggests the churn itself is a reliability liability, and it means agents can see spurious 'Houdini is down' signals while Houdini is fine.

**Action.** Add a bounded retry with backoff on the client transport, and re-test after implementing connection reuse — the two are likely the same root cause.

**Evidence.**

- Live tool response: `Couldn't reach Synapse — Lost connection while sending ping and couldn't reconnect: Connection lost during ping`
- Houdini side was healthy across the drop: telemetry.json showed heartbeats advancing 69,423→69,483, `"is_frozen": false`, `"freeze_count": 0`
- The next ping succeeded normally (server timestamp 1785592746.386401), so the failure was transient and transport-local, not a Houdini stall
- Connection-churn context: 89 `Client connected` lines vs 57 disconnect lines in the current log

*VERIFIED · risk · effort: small*

### Shipped panel walks the entire Python heap on Houdini's main thread every 4 seconds, forever, while no bridge exists

**Claim.** `SynapsePanel._update_health` fires every 4 s on the Qt/main thread and calls `agent_health._find_bridge_instance`, which memoizes only a POSITIVE bridge lookup in a weakref and returns `None` without caching the negative — so while no `LosslessExecutionBridge` exists in the process (the default state from panel construction until the first non-read-only tool dispatch) every tick performs a complete `gc.get_objects()` walk plus an `isinstance` test per object, on the main thread, with no stop on hide or close.

**Why it matters.** This is a periodic, unbounded-in-heap-size main-thread hold that belongs to NONE of the four known classes: it is not a tool payload (class 1/h7), not a marshal self-deadlock (class 2), not the chat-time Qt fallback (class 3), and not freeze_chain escalation (class 4). It fires with zero artist interaction — opening the panel once is enough — and never stops. It will not hard-freeze Houdini, but it establishes a permanent main-thread duty cycle proportional to the session's Python heap, which is exactly the 'Houdini feels sticky while SYNAPSE is open' signature that gets misattributed to whatever tool ran last. It is also invisible to every existing guard: `tests/test_marshal_lint.py` bans only the blocking/phantom marshal primitives (`test_no_blocking_main_thread_marshal` :239, `test_no_phantom_main_thread_marshal` :264) and says nothing about main-thread work volume.

**Action.** Cache the negative lookup (set a sentinel so a miss is scanned at most once per N ticks), or drop the gc scan entirely and call `shared.bridge.get_process_bridge()` directly — bridge_adapter.py:198-204 already documents it as the single process-wide accessor, which makes the heap scan redundant. Cheapest correct fix: move `poll_agent_health()` onto a daemon thread the way `_poll_context` was moved (`ws_bridge.gather_context_off_main`, ws_bridge.py:113-159) and stop the timer in `hideEvent`/`closeEvent`.

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/panel/agent_health.py:60-71 — `if _BRIDGE_REF is not None: cached = _BRIDGE_REF(); if cached is not None: return cached` / `for obj in gc.get_objects(): if isinstance(obj, LosslessExecutionBridge): _BRIDGE_REF = weakref.ref(obj); return obj` / `return None` — the `return None` at :71 does NOT set `_BRIDGE_REF`, so the miss is re-scanned every call
- C:/Users/User/SYNAPSE/python/synapse/panel/agent_health.py:53-58 docstring concedes the hazard: 'The scan over gc.get_objects() can be costly in a large Houdini session, and the panel polls on a timer' — the mitigation described covers only the cache-hit case
- C:/Users/User/SYNAPSE/python/synapse/panel/synapse_panel.py:367-371 — `self._health_timer = QTimer(self); self._health_timer.setInterval(4000); self._health_timer.timeout.connect(self._update_health); self._health_timer.start(); self._update_health()`
- C:/Users/User/SYNAPSE/python/synapse/panel/synapse_panel.py:1472-1483 — `_update_health` → `agent_health.poll_agent_health()`, guarded only by `if wf is None or agent_health is None: return`
- grep for timer lifecycle in synapse_panel.py returned `.start()` at :362, :370, :393 and NO `.stop()`, no `hideEvent`, no `showEvent`; `closeEvent` at :2129-2140 only removes the selection callback — the timer runs for the panel object's lifetime regardless of visibility

*VERIFIED · freeze · effort: trivial*

### 15-second `time.sleep` poll loop inside a handler its own comment documents as main-thread-reachable

**Claim.** `_handle_render` polls for the render output file with `for _ in range(60): ... time.sleep(0.25)` — a hard 15 s wall-clock sleep with no thread check and no marshal involved — inside a function whose own comment at :946-949 states that main-thread callers (panel Qt slot, /mcp read-only dispatch, any reentrant handler) execute it inline via run_on_main Fast path 2.

**Why it matters.** The forensics' standing verdict is h7 'long main-thread payload', and its primary remediation is to timebox the cook-heavy handlers. A `time.sleep` file-existence poll would survive that remediation completely: it is not a cook, not a marshal, and not `hou` work, so chunking hou payloads leaves it untouched. On any main-thread-reachable call it is a deterministic 15 s GUI hold with no telemetry attribution (marshal_guard's inline-overrun sink only fires from run_on_main Fast path 2 and this sleep sits OUTSIDE the run_on_main call at :957).

**Action.** Assert off-main at the top of the poll (`if threading.current_thread().ident == threading.main_thread().ident:` → skip the sleep loop and return a 'poll pending' result, or hand the poll to the existing render-poll registry), and add the sleep loop to whatever lint pins the marshal surface so a main-thread `time.sleep` in a handler fails CI.

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/server/handlers_render.py:964-971 — `# -- Off-main from here (pure file IO / subprocess, zero hou) ---` / `for _ in range(60):` / `if Path(out_path).exists() and Path(out_path).stat().st_size > 0: render_ok = True; break` / `time.sleep(0.25)`
- C:/Users/User/SYNAPSE/python/synapse/server/handlers_render.py:946-953 — `# THE freeze. executeInMainThreadWithResult here meant every main-thread caller (panel Qt slot, /mcp read-only dispatch, any reentrant handler) enqueued the render for itself... run_on_main runs it directly on such a caller instead (fast path 2)` — establishes that the enclosing function does run on the main thread for those
- The comment's 'Off-main from here' claim is about the absence of `hou` calls, not about the calling thread: nothing between :957 (the run_on_main return) and :971 switches threads
- harness/notes/FREEZE_FORENSICS_20260731.md §5 item 1 scopes the PRIMARY remediation to `cook(force=True)` sites and `execute_python` — i.e. hou work — so a `time.sleep` loop is outside that remediation's reach

*VERIFIED · freeze · effort: small*

### WebSocket sends from Qt slots use a socket left in blocking mode with no timeout — including the HALT button

**Claim.** `SynapseWSBridge.send_command` / `.send` call `self._ws.send(msg_json)` directly from main-thread Qt slots, and the underlying `websockets` 15.0.1 sync client sets `sock.settimeout(None)` after the handshake, so the write is an unbounded blocking `sendall` on the main thread if the peer stops draining.

**Why it matters.** An artist's emergency escape hatch performs an unbounded blocking socket write on the GUI thread. The server-side recv pump is serial, so the exact condition that motivates pressing HALT (a handler holding the main thread) is the condition under which the server stops draining — the escape hatch can block on the thing it exists to escape. This mechanism is distinct from all four known classes: it is neither a marshal nor a payload, it is transport backpressure reaching the GUI thread.

**Action.** Route all `send_command`/`send` through the existing `_send_queue` + `_queue_lock` path (ws_bridge.py:416-417) unconditionally and let the QThread drain it — the queue already exists and is already used as the not-connected fallback; the fast-path direct `.send()` is the only unbounded leg. Alternatively call `self._ws.socket.settimeout(n)` after connect.

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/panel/ws_bridge.py:409-414 (`if self._ws is not None: try: self._ws.send(msg_json); return`) and :510-518 (same shape in `send`)
- C:/Users/User/SYNAPSE/python/synapse/panel/ws_bridge.py:249-253 — `connect(url, open_timeout=3.0, close_timeout=2.0)`; no read/write deadline is configured for the steady state
- Live library inspection: `python -c "import websockets; print(websockets.__version__)"` → `15.0.1`; source scan of `websockets/sync/client.py` shows `sock.settimeout(None)` at lines 200 and 221 (post-handshake), and `websockets/sync/connection.py` sets a timeout only in the close path (lines 782, 997)
- `inspect.getsource(websockets.sync.connection.Connection.send)` — signature is `send(self, message, text=None)`; grep for 'timeout' in that method body returned nothing
- Main-thread callers: chat_panel.py:1030-1033 `_poll_integrity` (a 5 s QTimer slot, timer created at :244-246) and chat_panel.py:1022-1028 `_on_emergency_halt` — the HALT button (`self._halt_btn.clicked.connect(self._on_emergency_halt)` at chat_panel.py:650)

*VERIFIED · freeze · effort: trivial*

### Twenty TOPS handlers open with a dead `import hdefereval` that gates them on a module this repo records as unimportable headless

**Claim.** Every TOPS handler body begins with an unguarded `import hdefereval` that is never used — the actual marshal goes through `_run_in_main_thread_pdg` → `run_on_main` — so in headless hython, where the repo's own record says `hdefereval` is unimportable, all TOPS handlers raise ImportError on their first statement after the `HOU_AVAILABLE` check.

**Why it matters.** A dead import silently converts every TOPS/PDG tool into an ImportError in headless hython — the exact environment the repo uses for offscreen panel verification and CI probes. It is also a false signal for anyone auditing the marshal surface: a grep for `hdefereval` shows 20 hits in TOPS that look like blocking marshals and are not.

**Action.** Delete the 20 vestigial `import hdefereval` lines plus the one at `_common.py:66`. No behaviour depends on them.

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/server/handlers_tops/cook.py:31-38 — `if not HOU_AVAILABLE: raise RuntimeError(_HOUDINI_UNAVAILABLE)` then `import hdefereval` then `node_path = resolve_param(...)`; a grep for `hdefereval` inside that function body (lines 34-95) returns only the import itself and the NEXT handler's own import at :95
- 20 such sites: cook.py:34,95,143,227,281,325,370,419; diagnostics.py:42,125,248,399; work_items.py:40,126,201,279; render_sequence.py:108,357; wedge.py:30,94
- The real marshal: `handlers_tops/_common.py:81-82` — `from ..main_thread import run_on_main` / `result = run_on_main(func, timeout=effective_timeout)`; the `import hdefereval` at _common.py:66 is likewise unused
- Repo record (MEMORY.md, h22-cook-cancel-probe and phantom-sweep entries): 'hdefereval unimportable headless' / 'hdefereval = 6th headless-blind module'
- Repo-wide grep for actual attribute use `hdefereval.<attr>(` returns only two live hits: server/main_thread.py:309 and host/main_thread_executor.py:290 — neither in handlers_tops

*VERIFIED · hygiene · effort: trivial*

### The only record of a concurrent-writer collision — with four undecided human items — is untracked

**Claim.** .claude/h2-halt/H2_HALT_EVIDENCE.md records a live two-agents-one-worktree collision and four explicit 'For the human' items, is untracked and not ignored, and legs H2, H1 and F1 remain blocked behind it.

**Why it matters.** The whole integration line is parked behind an unresolved canonicality question whose only record is untracked. Two receipts for one leg is worse than none, and the 18-versus-17 delta will otherwise be inherited rather than reconciled.

**Action.** HUMAN GATE (trivial to decide): rule which H2 run is canonical, then COMMIT .claude/h2-halt/ as harness evidence rather than dropping it — it holds live undecided rulings. ENGINEERING (small) follow-up: reconcile the 18-versus-17 bucket-2 count with a producer path before either number is cited again.

**Evidence.**

- .claude/h2-halt/H2_HALT_EVIDENCE.md:1-6 — 'H2 — HALTED before Part A. Concurrent-writer collision in the dispatch worktree ... Reason: Constitution Article V — two agents in one directory,' with an evidence table showing HEAD moving without the agent's action.
- Its §3 items, none resolved in any state file: decide which H2 run is canonical and stop the other; re-dispatch into a fresh worktree; hand §2 to the canonical run; and a warning that the in-flight matrix mutates python/synapse/mcp/tool_impls/solaris/*.py in place and can leave a deliberately broken implementation in the working tree if killed.
- The collision it warned about already happened: harness/notes/receipts/ holds both H2.json (4,658 bytes) and H2b.json (31,578 bytes) for the one leg.
- An unresolved numeric delta in the same file: 'Note the count: 18, not 17. RES.json and R43 both say bucket 2 is "~17 tests" ... Whichever H2 run completes should reconcile that delta rather than inherit either number — Law 2, no number without a producer.'
- `git check-ignore -v` → NOT-IGNORED; git status shows it as untracked, i.e. one accidental clean from gone. CONVERGENT — flagged by two Lane A modalities independently.

*VERIFIED · risk · effort: small*

### The only structural guard keeping the marshal-deadlock class closed does not scan the repo root or six shipped trees

**Claim.** tests/test_marshal_lint.py:73-76 sets `_SOURCE_ROOTS` to python/synapse and shared only, leaving mcp_server.py, mcp_tools_*.py, houdini/, scripts/, retina/, forge/, agent/ and host/ outside the ban on the blocking marshal and the H22 phantom.

**Why it matters.** This lint is the sole structural reason freeze Class 2 stays closed — and it is the good kind of guard, one that fails loudly rather than relying on convention. mcp_server.py in particular is a Houdini-facing dispatch surface where a blocking marshal would be a natural mistake and would pass CI today.

**Action.** ENGINEERING (trivial): add the repo root (non-recursive, for the mcp_*.py modules) plus houdini/, host/, agent/, retina/ and forge/ to `_SOURCE_ROOTS`. It stays green today, so this is a free widening. Preserve the empty allowlists — adding an entry to silence red would reopen the class.

**Evidence.**

- tests/test_marshal_lint.py:73-76 — `_SOURCE_ROOTS = (_REPO_ROOT / "python" / "synapse", _REPO_ROOT / "shared",)`.
- Uncovered trees confirmed to exist and ship: repo-root mcp_server.py and six mcp_tools_*.py modules, plus houdini/, scripts/, retina/, forge/, agent/, host/.
- CURRENTLY CLEAN — Lane C leg 1 scanned each individually for `executeInMainThreadWithResult|executeInMainThread\b|_queueDeferred` and found zero hits, so widening is zero-risk today.
- The lint's authors already killed a related blind spot deliberately (line-scoped allowlists at :98-102, both empty at :122 and :127), which is why this larger gap is worth naming rather than assuming intentional.

*VERIFIED · risk · effort: trivial*

### The orchestrator's dependency gate reads a state field that does not mean what it says, and the completion record it asked for is absent

**Claim.** harness/legs.json reports 22 legs as 'ready', but every one of the 22 already has a written receipt in harness/notes/receipts/, and harness/state/done.json — the completion memory ruling R16 requested — does not exist.

**Why it matters.** If 'ready' does not distinguish never-started from finished-a-week-ago, the dependency gate cannot prevent a leg being dispatched twice — which is precisely what produced the H2 collision and its two receipts for one leg.

**Action.** ENGINEERING (medium): make the orchestrator write leg state back on receipt completion, or build the harness/state/done.json that R16 asked for, keyed by (leg, receipt-sha). Until then treat harness/notes/receipts/ as the completion record and legs.json state as dispatch-intent only.

**Evidence.**

- Counted from harness/legs.json: 22 ready, 7 done, 3 blocked over 32 legs. Cross-checked against harness/notes/receipts/: all 22 'ready' legs have an existing receipt (RES, H3a, H3b, H4, H5, H6, H7, H8, U1, V0, V1, C1, RSI0, S0, S2, S3, I0, I1, E0, E1, V2, V3). Zero are missing one.
- Demonstrably stale note: legs.json leg H4 reads 'Queued 2026-07-25, NEVER DISPATCHED' — yet harness/notes/receipts/H4.json exists at 28,358 bytes dated Jul 27 with status amber and 5 for_ruling entries.
- `test -f harness/state/done.json` → ABSENT. harness/notes/CTO_RELAY_01_RULING.md:280 — 'R16 · The harness has no completion memory.' The proposed alternative ledger_truth.json exists only inside worktrees.
- legs.json's own _comment states the orchestrator owns 'dependency gating, worktree creation, trust, launch, receipt monitoring, branch backup, and notification' — i.e. it reads this manifest to gate.

*VERIFIED · hygiene · effort: medium*

### A background metrics poll accounts for ~96% of all main-thread marshals and walks the whole scene every 2 seconds with no subscriber

**Claim.** MetricsAggregator marshals a full `hou.node('/').allSubChildren()` traversal onto Houdini's main thread every 2 seconds regardless of whether any client reads metrics, accounting for essentially all marshal traffic in an idle session.

**Why it matters.** On the observed 9-node default scene this is free, which is why it has never surfaced. On a production scene the same code inserts an O(N) Python traversal plus 2N error and warning queries onto the artist's main thread every 2 seconds, forever — a periodic GUI hitch and direct contention with every command marshal. It also means the dispatch-wait histogram is measuring the aggregator rather than user work unless that is accounted for.

**Action.** ENGINEERING (small): gate the collector on an actual subscriber (panel open, or a metrics command seen recently), or make the scene walk adaptive by caching the node census and refreshing only on a cheap change signal. Measure on a real production hip before choosing — the only live scene available was 9 nodes.

**Evidence.**

- Attribution control (Lane B lane 3): session B ran 181 heartbeats at 1.0s → 181s uptime; expected 2s polls = 90.5; observed dispatch_waits = 87 (96%), with tool_durations containing only 'ping' — zero user commands. Session A: ~19.3h → expected ~34,741 polls, observed 33,833 (97.4%).
- python/synapse/server/live_metrics.py:91 `_DEFAULT_INTERVAL = 2.0`; :186 `self._stop_event.wait(self._interval)`; :218-254 `_gather()` iterates `for node in hou.node("/").allSubChildren():` calling `node.warnings()` and `node.errors()` per node; :255 `return run_on_main(_gather, ...)`.
- Started unconditionally on the shipped transport: hwebserver_adapter.py:316-318 constructs and starts the aggregator with no subscriber check.
- No consumer in the same snapshot: session.total_commands=0, active_sessions=0, routing.total_requests=0.
- CONVERGENT — Lane B lane 2 independently derived a 0.44–0.52 dispatches/second background stream from ping-anchored counter deltas and traced it to a 2-second panel timer, reaching the same conclusion from live data rather than source.

*VERIFIED · latency · effort: small*

### The agent.usd provenance writers and the routing log are complete implementations with zero producers

**Claim.** Ten agent_state writers and readers have no production callers, and panel/routing_log.py implements a full USD routing-log writer that nothing anywhere invokes — so two panel features silently render nothing and the agent.usd provenance sections are always empty.

**Why it matters.** CLAUDE.md's core promise is that every handoff is traceable and every scene state reconstructable, and harness/CLAUDE.md states 'Provenance or it didn't happen.' The IntegrityBlock and handoff provenance chain never reach agent.usd on any live path, so an operator opening agent.usd after a session cannot distinguish 'nothing happened' from 'nothing was recorded'. migrate_to_v2 having no caller also means any pre-v2 agent.usd on disk silently degrades the writers.

**Action.** HUMAN GATE (decide) then ENGINEERING (medium): pick the two that carry the product claim — log_integrity fed from the bridge's finalize path and log_handoff — and wire them, marking the rest explicitly reserved-for-future in the module docstring. For routing_log, choose deliberately between wiring a producer at the panel-side router call site and deleting it plus the two dead consumer branches. Half-built is the worst of the three states.

**Evidence.**

- RE-VERIFIED IN THIS PASS — caller sweeps over python/, shared/ and scripts/ excluding agent_state.py itself return 0 production callers for log_routing_decision, log_handoff, log_integrity and migrate_to_v2. Lane A found the same for set_dispatched_agents, resume_task, abandon_task, get_integrity, get_handoff_chain and get_dispatched_agents; only tests/test_agent_state.py exercises them.
- RE-VERIFIED IN THIS PASS — `grep -rn 'write_to_usd\|\.log_decision(\|apply_learned_fast_paths' python/synapse shared scripts` excluding definitions returns NOTHING: routing_log.py has zero producers.
- Its two consumers fail silently: face_work.py:298-306 `if not decisions: return ""` and face_review.py:534-548 `if not decisions: return` — so the routing summary and the ROUTED authorship credit never render, with no error.
- The prims are created empty: agent_state.py:90-100 creates routing_log, handoff_chain, session_history, verification_log and ledger.
- CONTRAST — these ARE wired, showing the sweep is sound: create_task/update_task_status/write_verification at handlers.py:1781-1954, and log_session/suspend_all_tasks at mcp/session.py:198-208 and websocket.py:603-613.

*VERIFIED · unfinished-work · effort: medium*

### Both memory-maintenance tools are wrong for the shipped configuration: one runs deprecated code, the other is a no-op

**Claim.** With the default jsonl backend, synapse_evolve_memory dispatches into a module whose own docstring says it is superseded and 'Do not extend it', while the Moneta-era replacement synapse_sleep_pass is documented as a no-op under that same default.

**Why it matters.** Neither tool surfaces its situation to the caller at invocation time — sleep_pass says it in the tool description, evolve_memory says nothing. The gating condition ('live async-server FC4 verification') is named but there is no in-code marker of whether it has been met, so nobody can tell from the tree whether the cutover is blocked or merely forgotten.

**Action.** HUMAN GATE (small): decide whether FC4 has been met. Then ENGINEERING (medium): either flip the default to moneta, or make synapse_sleep_pass return an explicit refusal naming the required env var rather than silently doing nothing. Reconcile the two selectors before any cutover.

**Evidence.**

- python/synapse/memory/evolution.py:7-15 — 'SUPERSEDED by the Moneta backend ... It remains live only for the legacy default ``jsonl`` backend and will be removed when ``SYNAPSE_MEMORY_BACKEND`` defaults to ``moneta`` after the live async-server (FC4) verification. Do not extend it.'
- The live route: handlers.py:798 `reg.register("evolve_memory", self._handle_evolve_memory)` and handlers_memory.py:246-248 `from ..memory.evolution import check_evolution, evolve_to_charmeleon`.
- python/synapse/mcp/_tool_registry.py:1076-1081 — synapse_sleep_pass: 'Run Moneta consolidation/decay ... No-op under the default jsonl backend.'
- Default confirmed: memory/store.py:810 `os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl")`, .env has no entry, and the env var reads None.
- A latent divergence worth noting: two independent selectors read the same variable with different valid-value sets — store.py:883 rejects 'sqlite' while sqlite_store.py:749 accepts it.

*VERIFIED · unfinished-work · effort: medium*

### The phantom sweep proved its claims and every exit gate is still shut

**Claim.** The PHANTOM SWEEP harness completed two fix rounds with sound crucible verdicts, but its SPEC is unratified, the corpus fix branch is unmerged, rulebook/phantoms.json holds none of the six confirmed quarantine entries, and the content_digest rebuild is unstarted.

**Why it matters.** CLAUDE.md safety rule 15 names phantom APIs as SYNAPSE's number-one failure class and the rulebook discipline says 'Never reference a quarantined symbol; the phantom lint fails CI.' Right now the corpus fix that makes the claim true is unmerged and the six facts that would make the lint enforce it live only in a markdown packet. The distance between proven and enforced is entirely human-gate width.

**Action.** HUMAN GATE (small, one sitting): push the fix branch first, ratify harness/phantoms/SPEC.md, populate the six draft rows plus usdrender into rulebook/phantoms.json, then merge. ENGINEERING (small) follow-up: the queued content_digest rebuild and a decision on the 25 unclassified hits.

**Evidence.**

- harness/phantoms/SPEC.md:3 — 'PROPOSED — awaits Joe's ratification, same discipline as CLEAR's SPEC.'
- harness/phantoms/LOG.md FIX-R2 row — 'claim now true: no corpus file teaches the usdrender node type; **merge = Joe's gate**; content_digest rebuild queued as follow-up'.
- harness/phantoms/QUARANTINE-PACKET-2026-07-31.md:3 — 'Proposed `rulebook/phantoms.json` entries are populated by Joe, never by the harness. The L5 merge is **not authorized** by this document.' §1 records 6 candidates with two independent assays and '6/6 quarantine holds — all ABSENT'.
- An adjacent gap the packet names itself: 'rulebook/phantoms.json contains **no `usdrender` entry** today — the phantom verdict rests on the H21.0.671 recon memory only.'
- Not clean: LOG.md records 'final totals 163/188 classified (128 KEEP / 35 FIX) with **25 UNCLASSIFIED**'.

*VERIFIED · unfinished-work · effort: small*

### The clearance harness's three remaining failures are human gates whose only pass routes require writing agent-forbidden files

**Claim.** P2.1, P3.4 and P3.5 all fail, and every branch of their conditions terminates in DECISIONS.md (derived, do-not-hand-edit) or flywheel_queue.json (deny-list fence, human-only ratification) — so no amount of engineering clears them.

**Why it matters.** The harness's LOG accurately reports '5 PASS / 3 FAIL ... remaining 3 = human gates', but two of the three carry an 'OR a deferral entry' escape hatch that reads like agent-clearable work and is not. Any future run attempting them burns a cycle rediscovering the fence.

**Action.** HUMAN GATE (trivial, roughly ten minutes total): flip or explicitly defer flywheel cycle C.0; add a husk-render park entry citing the Indie block; and either write the latency addendum or record a 'latency addendum gated, deferred' entry. ENGINEERING (trivial) follow-up: point the P3.4/P3.5 alternative branches at a file an agent can write, or state plainly in SPEC that they are human-only.

**Evidence.**

- P2.1: harness/clear/verify.py:127-152 requires flywheel cycle C.0 to be ratified or deferred; the live queue shows C.0 status='candidate', ratified=False, and the file's own _doc says 'ratified is flipped by a HUMAN only (anti-runaway anchor)'.
- P3.4: reproducing verify.py:92-97 in-process gives `husk present: True` but the park/defer/indie regex → False. verify.py:93-95 requires the deferral to 'live in the board substrate, not only the harness's own DEADENDS.md'.
- P3.5: docs/reviews/synapse-latency-report-2026-07-27-addendum.md is absent, and the word 'latency' appears nowhere in DECISIONS.md or flywheel_queue.json, so the alternative deferral branch cannot match either.
- harness/clear/DEADENDS.md:20-24 pre-registers direct edits to the latency report as REJECTED: 'Joe's gate. The report is checked-in and gated.'
- harness/state/DECISIONS.md:28 records the same conclusion: 'L1 gap-closure is gate-REFUSED.'

*VERIFIED · unfinished-work · effort: trivial*

### 26 of 52 flywheel cycles are unread proposals, and two carry named correctness risk indistinguishable from 24 feature requests

**Claim.** harness/state/flywheel_queue.json holds 52 cycles with exactly 26 ratified:false, all status='candidate'; none is blocked, all are unread, and two describe silent-wrongness risks rather than features.

**Why it matters.** None of these is blocked; all are unread. The problem is that two items carrying named correctness risk sit in a flat list beside 24 feature proposals, so the risk items get the same attention as the features — which is to say none.

**Action.** HUMAN GATE (medium — this is the sitting the clearance harness's L2 line was built to enable): rank the 26 by risk versus feature first. Suggested first pass: ratify or reject CTO-01 (the moat's only exact-equality gate, never re-probed on H22) and W.5b (silent wrong author) before touching the seven feature cycles explicitly held behind 'receipts first'.

**Evidence.**

- Parsed from harness/state/flywheel_queue.json: 'RATIFIED: 26 UNRATIFIED: 26 TOTAL: 52', including three whole classes (S.0 studio, R.0 release, C.0 capability), seven C.*-H22 cycles held under 'CTO hold: features wait — receipts first', five CTO-0* advisory items, and six crucible follow-ups ending 'Human flip.'
- THE TWO WITH RISK, in their own text: W.5b — 'a custom string[] attribute name ... gets SILENTLY authored as a relationship; converts a prior no-op into a possibly-wrong author'; CTO-01 — the memory-evolution USD round-trip is 'The moat's ONLY in-process exact-equality gate against live pxr, never re-probed on H22 despite USD 0.26.5 module reorg'.
- harness/decisions.py:24-30 records the triage result: 'only 5 to be agent-decidable; 20 are genuine human judgement calls ... 24 of the 26 gate nothing mechanically. The bottleneck is triage ATTENTION, not authority.'
- CONTRADICTION RESOLVED IN FAVOUR OF DIRECT READ: the standing memory index describes the D-track as dormant awaiting a ratification flip, but a direct JSON parse shows D.0 is ratified:true. The direct read is stronger evidence than the memory note; the D-track premise should not be carried forward.
- R.9 (fail-closed security defaults) is transitively blocked on R.0 being unratified, so a security task is gated behind a flywheel flip rather than behind engineering.

*VERIFIED · unfinished-work · effort: medium*

### Four closed rulings are implemented only on an unmerged branch and drift further from mergeable with every change

**Claim.** repair/ledger-moneta-seam @ eb25abe holds 2,012 insertions unmerged into master, and the rulings document states the implementations of R52 through R55 live only there.

**Why it matters.** This is the clearest candidate for decided-but-not-delivered work, but the two lanes disagree on whether it is still true — one read the ruling document, the other probed master's content and found the union function present. That disagreement is itself the finding: nobody currently knows whether R52 through R55 shipped.

**Action.** ENGINEERING (small to determine, medium if real): read master's moneta_provenance() and confirm whether it carries all five R64 fields including LEDGER's half. If it does, retire the ruling as landed. If it does not, dispatch the U1 provenance-union leg as ruling 91 specifies — authoring, not merge resolution. Do not merge the branch first either way.

**Evidence.**

- harness/notes/CTO_RULINGS_01.md:2521-2523 — 'LEDGER's ruled items **R52, R53, R54 and R55 are all DECIDED** — and implemented *only* in that stranded code. **Four rulings I closed are currently un-shipped**, and every further change to `moneta_runtime.py` widens the gap LEDGER's patch must cross.'
- `git diff --shortstat master...repair/ledger-moneta-seam` → 8 files, 2012 insertions, 23 deletions; the branch appears in `git branch --no-merged master`.
- The prescribed unblock forbids the cheap fix — ruling 91: 'The union is AUTHORED, not merge-resolved. No automatic strategy produces a five-field function ... LEDGER's half lands as part of that union, not before it.'
- harness/legs.json leg U1 carries that brief and is state='ready'.
- IMPORTANT NUANCE FROM A SECOND LANE: content probing found master:python/synapse/memory/moneta_runtime.py:567 already defines `moneta_provenance(` and tests/test_ledger_moneta_seam.py is byte-identical on master, added by 189180d 'U1 - moneta_provenance() is one function with all five R64 fields'. So the union may already have landed and the rulings document may be stale.

*INFERRED · unfinished-work · effort: medium*

### The live runtime is Houdini 22.0.397 / SYNAPSE 5.40.1, not the 22.0.368 / v5.41.0 this run was told to assume

**Claim.** Three ground-truth facts handed to every agent in this run are wrong: the running Houdini is 22.0.397, the running SYNAPSE is 5.40.1 with an install stamp claiming 5.23.0, and actual git HEAD is 77ca1ec rather than f427320.

**Why it matters.** Two consequences. First, no measurement taken this run covers the P3.1/P3.2/P3.3 clearance fixes, because the process predates them — so latency and freeze figures describe 5.40.1. Second and more broadly, the committed symbol table is stamped 22.0.368 against a 22.0.397 runtime, which means any phantom-authority or symbol-membership verdict produced this run is calibrated against a build that is not running.

**Action.** ENGINEERING (small): regenerate the symbol table via host/introspect_runtime.py for 22.0.397, then re-validate any symbol-table-dependent finding before ratifying it. HUMAN GATE: decide whether the freeze and latency figures should be re-measured against a restarted 5.41.0 bridge before they are treated as current.

**Evidence.**

- RE-VERIFIED IN THIS PASS — `git log --oneline -3` → HEAD is 77ca1ec 'feat(harness): RSI closure harness + all-harness progress board' (9 files, 1,615 insertions, all under harness/), one commit past the brief's f427320.
- LIVE (Lane C leg 2): synapse_doctor version check status fail — 'synapse 5.40.1 / protocol 4.0.0; install stamp says 5.23.0 - installed tree and stamp disagree'; symbol_table check status fail — 'stamp 22.0.368 (35903 symbols) != running 22.0.397 — regenerate via host/introspect_runtime.py (scout distrusts a version-mismatched table)'. Doctor summary: 3 fail, 6 ok, 1 skipped.
- CORROBORATED INDEPENDENTLY by two latency lanes reading telemetry from disk: live_metrics hip_file = 'C:/Program Files/Side Effects Software/Houdini 22.0.397/bin/untitled.hip', and every freeze dump reports synapse_version 5.40.1.
- The bridge process was published 2026-07-31T18:40:36Z (pid 3696 at the time of measurement), before the v5.41.0 release commit.

*VERIFIED · risk · effort: small*

### CONTRADICTION: the headline panel-stall figures (10,005ms and 46,724ms) are not main-thread grip and must not be quoted as such

**Claim.** One lane presented '1.98ms on the MCP path versus 10,005ms on the panel' as a 5,000x path-dependent difference; another lane showed 10,005ms is the run_on_main default timeout reported through a string that fires on both the main-thread and daemon paths. The second lane's evidence is stronger and its reading should govern.

**Why it matters.** Averaging these two readings would produce a wrong number in the report of record. The freeze conclusion is unchanged and if anything better supported — it now rests on heartbeat evidence rather than on a contaminated instrument — but anyone quoting 46.7 seconds of GUI grip would be quoting daemon wall-time and would be corrected in the next review.

**Action.** ENGINEERING (documentation, trivial): quote only the heartbeat-derived freeze durations until the attribution string is fixed (see stale-attribution-corrupts-forensics). Treat the panel-versus-MCP path split as real and important — it is — but stop citing that specific pair as its evidence.

**Evidence.**

- The claim under dispute: synapse_inspect_scene measured 1.9771ms server-side via MCP, versus a log record of "'synapse_inspect_scene' ran 10005ms on the main thread".
- WHY THE SECOND READING WINS — structural: tool_executor.py:472-479 sits in `_dispatch`'s finally, and `_dispatch` is called from BOTH :390 (main-thread slot) and :517 (off-main daemon), so the phrase 'on the main thread' is unconditional and cannot discriminate.
- WHY IT WINS — numeric: two separate records read exactly 10005ms ('houdini_create_node' and 'synapse_inspect_scene'). main_thread.py:20 sets `_DEFAULT_TIMEOUT = 10.0`. A repeated exact value is a timeout signature, not measured work.
- The same defect inflates the 46,724ms figure: post-fix (after PR #50 merged 2026-07-30) that path is a daemon thread, so the number is daemon wall-time, not GUI grip. Ten of the 46 recorded stalls are dated 2026-07-31 and therefore post-fix.
- THE DEFENSIBLE FIGURES ARE THE HEARTBEAT-DERIVED ONES, re-verified in this pass: 10.3s, 21.1s, 23.1s, 23.2s, 24.3s, 25.8s and 44.4s on 2026-07-31. Those come from the Qt timer itself stalling and are independent of the misattributing string.

*VERIFIED · risk · effort: trivial*

### Uptime, sessions, commands-per-minute and routing all report confident zeros on a bridge with 33,948 dispatches

**Claim.** synapse_uptime_seconds is 0.0, sessions_active 0, commands_per_minute 0.0, total_commands 0 and routing total_requests 0, on a process with roughly 19 hours of heartbeats, 33,948 recorded main-thread dispatches and 42 recorded tool calls; synapse_router_stats returns 'Router not initialized'.

**Why it matters.** These are the denominators for every rate anyone would want. With all of them pinned at zero, latency per command and degradation over uptime cannot be expressed, and both measuring lanes had to derive rates by hand from ping-anchored counter deltas. Anyone triaging a freeze from the metrics surface sees an idle, healthy-looking system — which is why the 17.2-second dispatch wait is invisible everywhere except the raw histogram's max field.

**Action.** ENGINEERING (small): wire uptime_seconds and total_commands to real sources or remove the gauges — publishing confident zeros is worse than publishing nothing. Add a monotonic main-thread-timeout counter alongside the existing resetting stall gate (they are different instruments), and export queue depth from the call site that already reads it.

**Evidence.**

- Live scrape (Lane C leg 2 and Lane B lane 2, independently): `synapse_uptime_seconds 0.0`, `synapse_sessions_active 0`, `synapse_commands_per_minute 0.0`; live_metrics session block all zeros; routing block `{"total_requests": 0, "avg_latency_ms": 0.0, "tier_counts": []}`.
- Contradicted in the same scrape by `synapse_dispatch_wait_ms_count 33948` and `synapse_tool_duration_ms_count{tool="ping"} 31`; zeros persisted identically across three snapshots.
- synapse_router_stats → `{"error":"Router not initialized"}`, and the four routing metric families declared in metrics.py:60-82 never appear in any scrape.
- Related gaps: no queue-depth or backpressure gauge is exported despite websocket.py:834-835 feeding `self._command_queue.size()` into the backpressure evaluator, and main-thread timeouts are only counted consecutively and reset on the next success (main_thread.py:189-201), so session totals are structurally unrecoverable.

*VERIFIED · hygiene · effort: small*

### The latency report's biggest open lever is scoped as new handler work when the mechanism is already domain-agnostic

**Claim.** Extending declarative graph coverage to COPs and TOPS is framed as building new per-domain tools, but propose_graph and instantiate_graph are already fully context-agnostic — the only gap is system-prompt steering.

**Why it matters.** The report calls this the only lever that removes whole seconds per item and implies per-domain engineering. If the mechanism already generalizes, the work is prompt surgery — a cheap win currently priced as an expensive one, which is exactly how high-value items get deferred indefinitely.

**Action.** ENGINEERING (small): re-scope from 'build declarative coverage for COPs/TOPS' to 'steer the model to the existing generic propose_graph/instantiate_graph, and REMOVE the four conflicting system_prompt rules'. Validate with a COPs build over the generic path before writing any new handler. Note the latency report itself is behind a human gate, so the re-scope needs Joe before it can be recorded there.

**Evidence.**

- python/synapse/host/graph_builder.py:131-140 — `parent = hou.node(proposal.parent_path)` then `parent.createNode(n.node_type, ...)`: nothing Solaris-specific in the instantiation core.
- python/synapse/host/graph_oracle.py:34 — `cat = hou.nodeTypeCategories().get(category)`, resolving Cop2/Top/Sop/Lop alike; the `_TYPED_CATEGORIES` frozenset at :28 is used only for wire type-checking, not as a whitelist.
- The steering gap: system_prompt.py names solaris_build_graph at :81, :85, :132 and :187, and propose_graph ZERO times. No per-domain declarative tools exist — greps for cops_build_graph / tops_propose return empty.
- A prior diagnosis the current report drops: docs/LATENCY_SOLARIS_REVIEW.md:230 attributes the 25-turn blowup to 'the model picking the wrong strategy among four conflicting prompt rules' and warns 'adding a 5th rule to 4 contradictory ones won't reliably win.'

*VERIFIED · latency · effort: small*

### The shipped panel walks the entire Python heap on the main thread every 4 seconds while no bridge exists

**Claim.** agent_health._find_bridge_instance caches a positive bridge lookup in a weakref but never memoizes the negative, so a full gc.get_objects() walk runs on the Qt main thread on every 4-second health tick until a bridge is constructed — and the timer is never stopped on hide or close.

**Why it matters.** This is a periodic main-thread hold belonging to none of the four known freeze classes, and it fires with zero artist interaction — opening the panel once is enough. It will not hard-freeze Houdini, which is why it is rated medium rather than higher, but it establishes a permanent duty cycle proportional to session heap size: the plausible cause of a 'Houdini feels sticky while SYNAPSE is open' complaint that then gets misattributed to whatever tool ran last.

**Action.** ENGINEERING (trivial): call shared.bridge.get_process_bridge() directly instead — bridge_adapter.py already documents it as the single process-wide accessor, which makes the heap scan redundant — or at minimum cache the negative and stop the timer in hideEvent and closeEvent. Measure inside Houdini with a production scene before ranking it any higher.

**Evidence.**

- python/synapse/panel/agent_health.py:60-71 — the positive path sets `_BRIDGE_REF`, but `return None` at :71 does not, so every miss re-scans. The scan is `for obj in gc.get_objects(): if isinstance(obj, LosslessExecutionBridge):` — O(heap) with an isinstance per object.
- python/synapse/panel/synapse_panel.py:367-370 constructs the QTimer at 4000ms, connects it and starts it in __init__; `grep -n '_health_timer'` returns exactly those four lines — no .stop(), no hideEvent, no closeEvent teardown.
- The module's own docstring at :53-58 concedes 'The scan over gc.get_objects() can be costly in a large Houdini session, and the panel polls on a timer' — but the mitigation described covers only the cache-hit case.
- The bridge is lazily constructed (shared/bridge.py:2234-2241, reached only via execute_through_bridge or get_session_report), so 'no bridge yet' is the default state from panel construction until the first non-read-only dispatch.
- Cost scaling measured at roughly 46ns per object (1.0ms at 12k objects, 194ms at 4.2M) — but on plain CPython, not inside Houdini.

*VERIFIED · freeze · effort: trivial*

### A crucible-verified phantom scanner is invisible to the clearance bar it was built for, and its correctness depends on an unmet precondition

**Claim.** Clearance line L5 exists only in LOG and FORUM; the ratified SPEC still has 8 predicates and PLAN still has 4 lines, and the P5.1 proposal lives on an unpushed branch carrying a mandatory implementation precondition that has not been met.

**Why it matters.** The harness correctly refused to self-edit its own ratified contract — the anti-runaway anchor working as designed. The cost is that a finished, verified capability (24 tests, a 1,303-file production scan, zero false flags) is invisible to the bar it was built for, and its correctness rests on a precondition documented only on one unpushed branch. Note also that the expected-build injection interacts with the symbol-table drift above: the table is stamped 22.0.368 while 22.0.397 runs.

**Action.** HUMAN GATE then ENGINEERING (small): push both branches first, then ratify P5.1 into SPEC. The implementation MUST inject the expected Houdini version (non-negotiable per its own measurement) and the merge must carry the hdefereval allowlist plus the two missing aliases. Before pruning the other worktree, diff its 13 unique tests against the branch's to confirm nothing was lost.

**Evidence.**

- harness/clear/SPEC.md:13-22 ends at P4.1 with no P5.1, and SPEC.md:3 says it is 'changed only at explicit ratification points'. PLAN.md:5,21,37,54 covers L1 through L4 only.
- harness/clear/verify.py:237-246 holds exactly the 8 SPEC IDs — no phantom check runs in the clearance bar, which is the gap FORUM.md:24 names: 'The #1 failure class is outside work-clearance.'
- The precondition, from the proposal itself: 'P5.1's implementation in CLEAR's verify.py MUST set `scout.EXPECTED_HOUDINI_VERSION = <target build>` before calling `_load_symbol_table()`', with the measured consequence of skipping it — '152 pxr depth-2 symbols are h22-only ... 152 false-FAIL vectors on legal H22 work; 24 pxr symbols are h21-only ... 24 false-PASS vectors against an H22 target.'
- A second lane found a disjoint 24-test draft in a different worktree whose test names have ZERO overlap with the branch's 24 (13 unique per side), predating the branch by hours — so the rescue may have dropped cases.
- The quarantine packet adds that the merge should carry an hdefereval allowlist fix, and notes the proposed allowlist omits two snake_case aliases.

*VERIFIED · unfinished-work · effort: small*

### Three registered COP tools build graphs that produce no output

**Claim.** cops_reaction_diffusion, cops_pixel_sort and cops_bake_textures are dispatchable MCP tools whose handlers create a node graph with a placeholder kernel, never cook it, and for the bake never write files.

**Why it matters.** The honesty is present in the payload, which is genuinely good practice — but an artist asking for reaction-diffusion or a texture bake gets a graph and a success response, and a natural-language agent summarizing the result can easily drop the note and report success. Three headline COP capabilities are named-but-empty.

**Action.** HUMAN GATE (decide): keep them registered only if the caller-facing summary path is confirmed to preserve the scaffolded and cooked flags; otherwise move them to PENDING_TOOL_DEFS until a real kernel body is authored. The kernel authoring itself is large.

**Evidence.**

- python/synapse/mcp/_tool_registry.py:1443 — 'Gray-Scott reaction-diffusion solver SCAFFOLD (placeholder #define-only kernel; node not cooked)'; :1457 the pixel-sort equivalent; :1495 'UV texture baking SCAFFOLD: creates placeholder map nodes; does NOT bake or write files.'
- python/synapse/server/handlers_cops.py:1495-1502 returns `"scaffolded": True, "cooked": False` with a note stating it 'produces no reaction-diffusion output until a real kernel is written'; :1583-1586 and :1921-1926 carry the same shape.
- A mechanism for holding them back already exists and is empty: _tool_registry.py:1541-1558 PENDING_TOOL_DEFS.

*VERIFIED · unfinished-work · effort: large*


---

## LOW

### The 2026-07-25 push-denied remediation ticket is verifiably stale and still sitting untracked

**Claim.** Both branches the ticket blocks on are now on origin and its commit is an ancestor of master, so the blocker is resolved — but PLAN.md's disposal step was never executed and the file is still in the untracked list.

**Why it matters.** Small, but it is the residue of the CLEAR harness's own L1 line — the line whose stated goal (PLAN.md:7) was 'Get the 6 latency-relay files off the untracked list ... and dispose of stale scratch.' Half the goal shipped; the disposal half did not, and the untracked list is what the next survey will read as open work.

**Action.** HUMAN GATE (trivial): decide commit-as-scratch-archive vs remove-and-broaden-ignore for the four items, then execute. Note .claude/h2-halt/ should be committed rather than removed — it holds live undecided rulings (see h2-double-dispatch-open).

**Evidence.**

- .claude/remediation_ticket_2026-07-25_push_denied.md — 'What is blocked: git push -u origin feat/cto-relay-01 ; git push origin archive/root-scratch-2026-07-25 ... What unblocks it: 1. Joe runs the two git push lines himself.'
- `git branch -a --list "*cto-relay-01*" "*root-scratch*"` -> `remotes/origin/archive/root-scratch-2026-07-25` and `remotes/origin/feat/cto-relay-01` — both pushed.
- `git merge-base --is-ancestor d9b8aa3 master` -> success ('d9b8aa3 IS ancestor of master') — the ticket's blocked commit is merged.
- harness/clear/PLAN.md:19 — 'Dispose of stale scratch: the 2026-07-25 remediation ticket is STALE (its branches are gone/merged) → close it; docs/synapse_health_report.md (stale, says v5.33.0), docs/mat_dump.json, .claude/h2-halt/ → triage'. The L1 line's LOG row (LOG.md:9) records only the 6-file commit d0716f5; the disposal step is not recorded as done.
- All four disposal targets remain in the untracked list at HEAD: .claude/remediation_ticket_2026-07-25_push_denied.md, docs/synapse_health_report.md, docs/mat_dump.json, .claude/h2-halt/.

*VERIFIED · hygiene · effort: trivial*

### CTO-RELAY-01's own top-3 list: R1 and R2 have landed, R14 (hython permission) has no visible grant

**Claim.** Of the three items the relay ruling singled out, two are done in source and the third — a permission grant the ruling says is 'not engineering work' — is still named as the blocker for the panel arc's live verification.

**Why it matters.** This is the cleanest illustration of the closure gap: two of the three highest-cost-of-delay items in the whole relay ruling were fixed, and nothing in the harness's state files knows it. The third is a one-word human grant that the ruling itself flags as unblocking two legs' missing verification.

**Action.** HUMAN GATE (trivial): grant or explicitly decline the hython permission for panel verification, and record it. ENGINEERING (trivial): retire the R1/R2 board items at their source receipts once the closure mechanism from decisions-board-no-closure exists.

**Evidence.**

- harness/notes/CTO_RELAY_01_RULING.md:350-355 — 'THE THREE THINGS, IF YOU ONLY DO THREE: 1. R1 — correct the reversibility claim. 2. R2 — make the two gate emits conditional. Three lines. 3. R14 — grant the hython permission. It is not engineering work, and it unblocks the verification the last two legs are missing.'
- R1 LANDED: CLAUDE.md Identity section now reads 'Wrapping is not reversing. (VERIFIED-RUNTIME, L2 2026-07-25: failed Solaris builds orphan partial networks; the undo group does not clean up.)' and §1.1 Undo Grouping now says 'Grouping only: no automatic rollback on the exception path.'
- R2 LANDED: python/synapse/panel/gate_widget.py:513-514 — 'marked decided and ``decision_announced`` is NOT emitted. A consent gate that reports success on a swallowed exception is worse than no gate'; emits at :531-534 and :560-562 now sit after guarded except blocks at :521 / :550.
- R14 NOT VISIBLY GRANTED: CTO_RELAY_01_RULING.md 'WHAT THE RELAY DID NOT DO' — 'Produced no screenshots and verified nothing rendering — hython denied.' No corresponding grant appears in harness/state/posture.json, drop.json, or DECISIONS.md.
- Both R1 and R2 nevertheless remain counted as open on the board (DECISIONS.md:47 for the R2/L3 item) — see decisions-board-no-closure.

*VERIFIED · unfinished-work · effort: trivial*

### All 7 .claude/commit_*.txt are spent scaffolding for commits that already landed

**Claim.** Each of the seven untracked .claude/commit_*.txt files is byte-identical (modulo a missing trailing newline) to the message of a commit already on master.

**Why it matters.** Seven permanently-dirty entries in `git status` train the eye to ignore untracked files, which is how the six latency-relay files sat untracked for weeks in the first place.

**Action.** DROP all seven, and add `.claude/commit_*.txt` to .gitignore so the `git commit -F <file>` workflow stops leaving residue.

**Evidence.**

- diff of each file vs `git log -1 --format=%B <sha>` after trailing-whitespace strip: the ONLY difference reported for all 7 is '\ No newline at end of file'
- mapping: commit_changelog.txt->c0b9c2e, commit_clear_bookkeeping.txt->15123f4, commit_clear_scaffold.txt->8fbabd1, commit_latency_relay.txt->d0716f5, commit_p3_1.txt->340db86, commit_p3_2.txt->9c8fe87, commit_p3_3.txt->9c9bc8e
- git check-ignore -v on each -> NOT-IGNORED (they will keep showing in git status)

*VERIFIED · hygiene · effort: trivial*

### The 2026-07-25 push-denied remediation ticket is resolved and should be closed

**Claim.** Both blocked pushes named in .claude/remediation_ticket_2026-07-25_push_denied.md completed: d9b8aa3 is an ancestor of master and both branches exist on origin.

**Why it matters.** An open BLOCKER file that is not actually blocking anything costs attention on every survey pass.

**Action.** DROP the ticket file (its content is fully reconstructable from the reflog and origin refs).

**Evidence.**

- git merge-base --is-ancestor d9b8aa3 master -> YES; git merge-base --is-ancestor 08196df master -> YES
- git for-each-ref | grep -Ei 'cto-relay|root-scratch' -> refs/remotes/origin/feat/cto-relay-01 4abf68a, refs/remotes/origin/archive/root-scratch-2026-07-25 08196df, refs/tags/pre-cto-relay-merge 0b3e377
- git reflog -> '4abf68a HEAD@{2026-07-25 18:16:46}: merge feat/cto-relay-01: Fast-forward'
- master:harness/clear/PLAN.md:19 already records this: 'the 2026-07-25 remediation ticket is STALE (its branches are gone/merged) -> close it'

*VERIFIED · hygiene · effort: trivial*

### q2-baseline worktree shows 280 modified files that are 100% CRLF noise

**Claim.** The .claude/worktrees/q2-baseline worktree reports 280 modified tracked files / 111,091 insertions / 111,091 deletions, and `git diff --ignore-cr-at-eol` reports nothing at all — every change is a line-ending difference.

**Why it matters.** A worktree that always shows 280 dirty files makes any real uncommitted change invisible — precisely the condition under which the prior worktree-stripper incident nearly took 40 files.

**Action.** Renormalize line endings in that worktree (or prune it — it holds zero real content changes). Do not prune until the .q2tmp_* scratch dirs are confirmed disposable.

**Evidence.**

- git -C .claude/worktrees/q2-baseline status --porcelain | cut -c1-2 | sort | uniq -c -> '280  M' and '7 ??'
- git diff --shortstat -> '280 files changed, 111091 insertions(+), 111091 deletions(-)'
- git diff --ignore-cr-at-eol --shortstat -> (empty); git diff --ignore-cr-at-eol --name-only -> (empty)
- stderr repeated for every file: 'warning: in the working copy of ..., CRLF will be replaced by LF the next time Git touches it'
- untracked scratch: .q2msg, .q2tmp_gate2/, .q2tmp_iso/, .q2tmp_raw/, .sh_tmp1/, .sh_tmp2/, .sh_tmpA/

*VERIFIED · hygiene · effort: trivial*

### Three wf_* worktrees are stale duplicates of already-landed CLEAR L3 work

**Claim.** wf_bf92d587-317-1 and -2 hold working copies of the P3.1 and P3.3 fixes that already landed as 340db86 and 9c9bc8e; -1 is byte-identical to master, -2 holds a strictly earlier draft (2 tests vs master's 3) plus — escape artifacts where master has literal em-dashes.

**Why it matters.** 18 worktrees is a large surface; three of them provably hold nothing unique, and one contains a mojibake variant of a shipped file that could be re-applied by accident.

**Action.** Prune wf_bf92d587-317-1 and -2 (verified no unique content). Hold wf_4131d29a-13b-4 until its disjoint L5 tests are reviewed.

**Evidence.**

- git -C .claude/worktrees/wf_bf92d587-317-1 diff --ignore-cr-at-eol --stat master -- .claude/hooks/synapse_hooks_bridge.py -> empty; tests/test_sessionstart_ping.py IDENTICAL to master copy
- git -C .claude/worktrees/wf_bf92d587-317-2 diff master -- python/synapse/server/websocket.py -> 4 hunks, all of the form '-... — try again...' / '+... — try again...' (escape-sequence artifact only)
- diff of wf_bf92d587-317-2/tests/test_websocket_cancel_reachable.py vs master's: master says 'so all three tests fail. This was verified empirically by reverting the recv loop...' where the worktree says 'so both tests fail' -> worktree is the earlier draft
- all three worktrees sit on branches at 293484c (release v5.40.1), which is an ancestor of master

*VERIFIED · hygiene · effort: trivial*

### 83 unreachable commits — dropped stashes — are recoverable now and will be gc'd

**Claim.** `git stash list` is empty but `git fsck --unreachable` reports 83 unreachable commits, all of the 'WIP on <branch>' / 'index on <branch>' stash shape plus three named ones; spot-checked entries correspond to work already on master.

**Why it matters.** These are the only trace of intermediate states from the H1/RES/U1/heats legs. They survive only until the next gc; if any of them turns out to hold a variant worth keeping, the window is finite.

**Action.** No action required for work-loss — the spot-checked contents landed. If you want a safety net, note that `git fsck --unreachable` is the recovery path and it expires at gc time.

**Evidence.**

- git stash list -> (empty, exit 0)
- git fsck --unreachable --no-progress | grep -c '^unreachable commit' -> 83
- newest entries: '2026-07-28 15:32:53 |b6392a1| WIP on feat/repair-heats-01: 9ea6501 fix(orchestrator): R168...', '2026-07-27 00:07:47 |0ef9108| On repair/u1-provenance-union: u1-after', '2026-07-26 20:23:37 |89d916c| gate-c control: an empty commit that WOULD fast-forward master'
- spot check 0ef9108 (u1-after) -> 7 files / 2105 insertions covering ledger.py, moneta_runtime.py, tests/test_ledger_moneta_seam.py — all of which are on master via 189180d

*VERIFIED · risk · effort: trivial*

### docs/mat_dump.json, docs/synapse_health_report.md and .token-saver/ are already-surveyed scratch awaiting a triage decision

**Claim.** Three of the twelve untracked entries are stale scratch that master's own CLEAR plan already lists for disposal; none is ignored, so they persist in git status.

**Why it matters.** The health report is the only one with residual value and it is stale-by-version; the capsule names a live gate list (symbol-table regen due, quarantine packet pending) that would be lost silently.

**Action.** DROP mat_dump.json and synapse_health_report.md (regenerable via synapse_doctor / the material dump path); COMMIT or transcribe the .token-saver capsule's OPEN HUMAN GATES list before dropping it; add `.token-saver/` to .gitignore.

**Evidence.**

- master:harness/clear/PLAN.md:19 -> 'Dispose of stale scratch: ... `docs/synapse_health_report.md` (stale, says v5.33.0), `docs/mat_dump.json`, `.claude/h2-halt/` -> triage (commit as scratch-archive or remove + broaden ignore).'
- docs/synapse_health_report.md header: '**Generated:** 2026-07-27 / **Synapse Version:** 5.33.0 (Protocol 4.0.0)' — six releases behind HEAD (v5.41.0)
- docs/mat_dump.json is an 8,488-byte MaterialX/standard-surface parameter dump ('rubber': base_color/specular/coat/transmission floats); no reference anywhere in master except PLAN.md
- git check-ignore -v on all three -> NOT-IGNORED
- .token-saver/session-capsule-2026-07-31.md is a context-reset session capsule naming the freeze-forensics relay, five open human gates and 'Live build = H22.0.397; symbol table stamped 22.0.368 (regen due per build)'

*VERIFIED · hygiene · effort: trivial*

### graph_builder.py's "provenance writers are dormant — no live caller yet" comment is stale

**Claim.** python/synapse/host/graph_builder.py:279 asserts the agent.usd provenance writers have no live caller, but graph_synth_runtime.py:139-143 constructs the one GraphBuilder with provenance_writer=_agent_usd_provenance, which calls agent_state.log_decision, and that path is reachable from the live handler at handlers_graph_synth.py:90.

**Why it matters.** A stale "this is dormant" comment is a trust tax: it makes a reader (or an auditing agent) under-count what actually works, and it made the standing CLAUDE.md status-table note "⚠ provenance writers dormant" read as blanket-true when it is only true for the ten functions in the finding above.

**Action.** Narrow the comment to name which writers are still unwired (the ten listed in agent-usd-writers-dormant) rather than the whole family.

**Evidence.**

- python/synapse/host/graph_builder.py:275-281 — "(Residual: the agent.usd provenance writers are dormant — no live caller yet — so default is a no-op.)"
- python/synapse/host/graph_synth_runtime.py:139-143 — `_builder = GraphBuilder(_get_store(), validator_factory=_build_validator, provenance_writer=_agent_usd_provenance,)`
- python/synapse/host/graph_synth_runtime.py:109-122 — `_agent_usd_provenance` imports `from synapse.memory.agent_state import log_decision` and calls `log_decision(agent_usd, payload)`
- python/synapse/server/handlers_graph_synth.py:90 — `result = graph_synth_runtime.instantiate(proposal_id)`

*VERIFIED · hygiene · effort: trivial*

### The cognitive Dispatcher's production main-thread branch raises NotImplementedError; all three production dispatchers are constructed with is_testing=True

**Claim.** python/synapse/cognitive/dispatcher.py:308-313 raises NotImplementedError whenever main_thread_executor is None, and mcp_server.py constructs every production Dispatcher with is_testing=True (lines 584, 702, 834), so the marshal path is never used and the FloorGate provenance wrap is admitted in-code to be missing from the production branch.

**Why it matters.** Today this is benign — those dispatchers host no direct hou.* work. The hazard is latent and shaped exactly like the freeze classes already found in this repo: is_testing=True runs the tool synchronously on the calling thread, so the first hou-touching tool added to any of these three dispatchers runs off the main thread with no Tier-0 provenance and no error. The flag name also makes the production server read as if it is in test mode.

**Action.** Rename the parameter to something honest for production (e.g. inline_execution) or add an assertion that tools registered under is_testing=True carry a pure_python/ws_passthrough marker. Close or explicitly delete the Sprint-3-Spike-1 seam rather than leaving a raise in a production code path.

**Evidence.**

- python/synapse/cognitive/dispatcher.py:300-313 — "Spike 1.0 intentionally leaves this unwired. Spike 1 supplies a ``main_thread_executor`` ... Until then, this path raises ``NotImplementedError``" then `raise NotImplementedError("Dispatcher main-thread marshal path is unwired — this lands in Sprint 3 Spike 1.")`
- python/synapse/cognitive/dispatcher.py:250-259 — "NOTE: the production _execute_via_main_thread branch below is NOT yet routed through the gate (and is itself unwired today — main_thread_executor=None raises). Live autonomy provenance is covered via the server registry adapter ... not this dispatcher path; wiring the prod branch is a follow-up."
- mcp_server.py:583-585 `_inspector_dispatcher = _Dispatcher(is_testing=True, tools={...})`; mcp_server.py:701-704 `_scout_dispatcher = _Dispatcher(is_testing=True, ...)`; mcp_server.py:834 `_ported_dispatcher = _Dispatcher(is_testing=True, tools=tools)`
- Mitigation confirmed: the three dispatchers host pure-Python tools (scout, inspect_stage) or WS-passthrough tools that marshal on the server side (mcp_server.py:832-834 uses _make_ws_passthrough_tool)

*VERIFIED · risk · effort: small*

### VERIFIED STILL OPEN (as designed): Moneta is default-OFF, jsonl is the live default

**Claim.** The memory is accurate: SYNAPSE_MEMORY_BACKEND defaults to jsonl, and Moneta only engages when the env var explicitly selects moneta or shadow.

**Why it matters.** Confirms the claim rather than contradicting it. Worth noting there are TWO independent selectors reading the same env var (store.py:810 and sqlite_store.py:749) with different valid-value sets — store.py:883 rejects `sqlite` while sqlite_store.py accepts it. That is a latent divergence if the cutover ever flips the default.

**Action.** No action needed on the claim itself. Before any Moneta cutover, reconcile the two selectors so `sqlite` and `moneta` mean the same thing to both.

**Evidence.**

- python/synapse/memory/store.py:810 `backend = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl").strip().lower()`
- python/synapse/memory/store.py:804-806 docstring `Default ``jsonl`` is the unchanged behavior. ``moneta`` routes through the Moneta engine (Mile 4); it falls back to JSONL with a warning if Moneta can't be imported`
- python/synapse/memory/ledger.py:298 `MONETA_BACKENDS = ("moneta", "shadow")` and :329 `return os.environ.get("SYNAPSE_MEMORY_BACKEND", "").strip().lower() in MONETA_BACKENDS`
- python/synapse/memory/evolution.py:14 `removed when ``SYNAPSE_MEMORY_BACKEND`` defaults to ``moneta`` after the` — the cutover is explicitly still future work
- python/synapse/memory/sqlite_store.py:749 `backend = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl").lower().strip()` — same default, second selector

*VERIFIED · hygiene · effort: small*

### CLAIM WRONG: panel audit Mile 4 (IntegrityBlock readout) shipped in v5.31.0

**Claim.** The Mile 4 fidelity readout is implemented and merged — panel/integrity_readout.py exists at HEAD and has since commit 1304e4b.

**Why it matters.** Another stale 'open' item. Low severity because the cost is only wasted attention, but it compounds the pattern.

**Action.** Close the claim. Note CHANGELOG.md:121 flags that the panel's Qt tests skip under stock CI and the honesty guarantee rests on ast source-pins — so if that surface is ever revisited, the pins are the thing to check, not the Qt tests.

**Evidence.**

- python/synapse/panel/integrity_readout.py exists at HEAD
- `git log --oneline -3 -- python/synapse/panel/integrity_readout.py` -> `92a48eb fix(panel): H4 - one colour authority, resolved at the source` / `1304e4b feat(panel): Mile 4 — surface the IntegrityBlock/fidelity readout (honest, guarded)`
- CHANGELOG.md:121 `**M4 — THE FIDELITY READOUT ("what changed"; `panel/integrity_readout.py`, `session_integrity.py`):** ... Now the Work face shows an honest session-fidelity readout: no operations → "no operations tracked yet" (never a false green 100%), any violation → amber, 3+ → red.`

*VERIFIED · unfinished-work · effort: trivial*

### Two load-bearing status docs advertise authority while frozen on a superseded runtime

**Claim.** docs/verification_ledger.md declares itself LOCKED against Houdini 21.0.631 and docs/synapse_status_report.md is a 2026-06-01 snapshot, yet neither carries a superseded marker while the live host is 22.0.368.

**Why it matters.** Both read as current-state authorities. `Ledger Status: LOCKED` in particular signals 'settled truth' when it means 'frozen against a runtime we no longer ship on'. The D1 comment already shows how an H21-era hou.ui note propagates into live code decisions.

**Action.** Add a superseded-as-of header to both, naming 22.0.368 and pointing at the current authority. Do not delete — the Sprint-1 evidence rows are still useful provenance.

**Evidence.**

- docs/verification_ledger.md:3-7 `**Target Runtime:** Houdini 21.0.631` / `**Daily Driver:** 21.0.631 (confirmed 2026-04-18)` / `**Lock Duration:** Sprints 1–4` / `**Ledger Status:** LOCKED`
- docs/verification_ledger.md:31 footnote `hou.ui.processEvents() does NOT exist in H21.0.631` — a hou.ui claim about a build two majors stale, adjacent to the live D1 hou.ui question
- docs/synapse_status_report.md:2-5 `**Date:** 2026-06-01` / `**Protocol Version:** 4.0.0` / `**Evolution Stage:** Charmander (markdown / flat)`
- docs/synapse_status_report.md:20 claims `178 entries in store` — a point-in-time number presented in a WHAT IS WORKING section with no as-of qualifier
- Live host per run ground truth and `synapse_ping`: Houdini 22.0.368, protocol_version 4.0.0

*VERIFIED · hygiene · effort: small*

### The report's 'cancel is unreachable' finding is stale; the cancel half was fixed after the report was committed

**Claim.** Section 2 #3 and F7 describe cancellation as unreachable behind the serial per-connection loop, but commit 9c9bc8e (P3.3) replaced the blocking iterator with a 100ms cancel-polling generator — the cancel half is closed while the serial half remains true.

**Why it matters.** Pass 2 should not re-propose a cancel-reachability fix that already landed. The precise remaining gap is narrower than the report states: serial message handling per connection, not uninterruptible cancellation.

**Action.** Treat 'cancel unreachable' as SETTLED/closed by 9c9bc8e. Keep 'per-connection serial handling' as an open structural note only.

**Evidence.**

- python/synapse/server/websocket.py:103-124 `iter_messages(websocket, cancel_event, poll_interval=CANCEL_POLL_INTERVAL)` — "Replaces ``for message in websocket:`` (P3.3). The plain iterator blocks inside the websocket's recv and cannot be interrupted mid-frame; this loop calls ``websocket.recv(timeout=poll_interval)`` so it wakes up regularly and re-checks the cancel event."
- python/synapse/server/websocket.py:100 `CANCEL_POLL_INTERVAL = 0.1`.
- Serial half still true: websocket.py:546 `for message in iter_messages(...)` with :559 `self._handle_message(websocket, message, client_id)` called inline in the loop body.
- Corroborated at harness/notes/FREEZE_FORENSICS_20260731.md:54 — "h6-p33 — recv loop. P3.3 verified clean: `iter_messages` at `websocket.py:103-124` has no mis-consume; `cancel_event` is fresh per connection (`:438`) and popped at `:569-570`; the serial pump starves only the *next* message, never the GUI."
- Chronology: the report was committed in d0716f5, which is older than 9c9bc8e in the run's HEAD-first commit list.

*VERIFIED · latency · effort: trivial*

### synapse_doctor is the slowest instrumented tool at ~518 ms mean, roughly 9,000x the ping handler

**Claim.** The doctor tool records 3 samples totalling 1555.4342 ms - mean 518.5 ms - all falling in the (500,1000] bucket, while the ping handler averages 0.0567 ms over 31 samples. Doctor is three orders of magnitude more expensive than any other read tool measured.

**Why it matters.** Half a second per doctor call is fine for an on-demand diagnostic but would be ruinous if wired into a poll or a health beat. It is worth pinning as a known cost before anyone adds it to a timer, and it is a useful ceiling reference: no other read path comes within 250x of it.

**Action.** Keep doctor off any timer or startup-blocking path, and note the ~518 ms cost in the latency report's tool-cost table alongside the sub-millisecond reads.

**Evidence.**

- synapse_metrics @C -> synapse_tool_duration_ms_sum{tool="doctor"} 1555.4342 ; _count{tool="doctor"} 3 ; all 3 in bucket le="1000" with le="500" at 0
- synapse_metrics @C -> synapse_tool_duration_ms_sum{tool="ping"} 1.7587 ; _count{tool="ping"} 31 -> mean 0.0567 ms, all 31 under 5 ms
- synapse_metrics @C -> other read tools: get_health 0.0766/2, get_live_metrics 0.0961/1, get_metrics 2.0236/2, inspect_scene 1.9771/1, router_stats 0.0314/1

*VERIFIED · latency · effort: trivial*

### Per-tool counters incremented without a corresponding call from this agent, so single-caller attribution is unsound

**Claim.** Between my second and third metrics scrape I made only 4 pings and 1 metrics call, yet tool_duration counts for doctor (2 -> 3, +509.52 ms) and get_health (1 -> 2) both incremented, and ping incremented by 9 against my 4 calls. The counters are process-global and cannot attribute calls to a caller.

**Why it matters.** The most likely explanation is concurrent traffic from other lanes in this same evaluation run hitting the same bridge, which means my derived dispatch rate carries a foreign-traffic confound. I bounded it: ~14 non-mine tool calls over 215 s is 0.065/s against a 0.49/s dispatch rate, so foreign traffic explains at most 13% and the background-pressure finding survives. But no metric carries a session or client label, so this can only be bounded, never resolved.

**Action.** Add a client/session label to tool_duration, or expose a per-connection counter, so a measuring agent can subtract its own traffic. Until then, any single-agent measurement against a shared live bridge must state the confound explicitly.

**Evidence.**

- synapse_metrics @B -> _count{tool="doctor"} 2 ; _sum 1045.911 ; _count{tool="get_health"} 1 ; _count{tool="ping"} 22
- synapse_metrics @C -> _count{tool="doctor"} 3 ; _sum 1555.4342 ; _count{tool="get_health"} 2 ; _count{tool="ping"} 31
- My calls between B and C: synapse_ping x4, synapse_metrics x1 - zero doctor, zero health
- Low absolute doctor count (3 over a ~19 h process) refutes a background timer as the explanation

*INFERRED · risk · effort: small*

### Freeze escalation has no breaker to open on the live transport — confirmed in today's log

**Claim.** The freeze chain's escalation path logs 'No live SynapseServer breaker to open' on every escalation because the hwebserver transport ships without a resilience layer, and the live session today reports exactly that.

**Why it matters.** Escalation is observation only. When a freeze passes 30s, SYNAPSE writes a dump and can do nothing else — it cannot shed load, cannot open a breaker, cannot halt. This matches the doc's h4 refutation (escalation is effect, not cause) but it also means there is no automatic recovery for the artist, only evidence collection.

**Action.** No fix needed for the freeze taxonomy — but stop describing escalation as a mitigation anywhere it appears. The dump is the deliverable; the halt is not wired on this transport.

**Evidence.**

- python/synapse/server/freeze_chain.py:154-158 — `else: logger.error("No live SynapseServer breaker to open (hwebserver transport has no resilience layer) — proceeding to the halt check")`
- ~/.synapse/logs/synapse.log lines 18528 and 18698 — that error fired on both 2026-07-31 escalations (08:46:10 and 12:41:35)
- Live today: line 19177 `2026-08-01 10:04:05,237 [synapse.hwebserver] INFO: Native C++ server -- no watchdog, no circuit breaker` — the string appears 40 times in the log
- freeze_chain.py:171-173 — the emergency halt is likewise skipped: 'No ACTIVE bridge — emergency halt skipped (escalation never constructs one)'

*VERIFIED · freeze · effort: unknown*

### The pre-auth websocket recv is unbounded (studio-mode only, dead locally)

**Claim.** `websocket.recv()` in the authentication handshake has no timeout, but the branch is unreachable in the single-user localhost posture.

**Why it matters.** Holds no locks and touches no marshal state, so it cannot freeze the GUI — it is a connection-thread hang, not a Houdini hang. Only matters if multi-user deployment is ever pursued.

**Action.** Bound it with a timeout plus a cancel-event check, matching the `iter_messages` idiom at :116-124. Low urgency.

**Evidence.**

- python/synapse/server/websocket.py:480 — `auth_msg = json.loads(next(iter([websocket.recv()])))` — no timeout argument, unlike the bounded `recv(timeout=poll_interval)` at :118
- Gated at :466-470 by `auth_required = auth_key is not None or (self._deploy_config and self._deploy_config.auth_required)`
- Dead locally: ~/.synapse/logs/synapse.log line 19176 `2026-08-01 10:05:27,283 [synapse.auth] INFO: Authentication disabled (no SYNAPSE_API_KEY or auth.key found)`
- Named as remediation item 5 in harness/notes/FREEZE_FORENSICS_20260731.md:96-97, scoped 'studio mode only'

*VERIFIED · risk · effort: trivial*

### Twenty-plus handlers_tops modules import hdefereval and never use it

**Claim.** Files under `python/synapse/server/handlers_tops/` execute `import hdefereval` inside handler bodies but make no attribute access on the module.

**Why it matters.** Harmless today but misleading: a reader auditing marshal sites sees twenty hdefereval imports in the TOPS layer and has to prove a negative on each. It also means these handlers would raise ImportError outside Houdini for a module they do not need.

**Action.** Remove the unused imports, or if they are an intentional in-Houdini availability probe, replace them with the module's existing `HOU_AVAILABLE` guard and say so in a comment.

**Evidence.**

- `grep -rn 'hdefereval' python/` shows `import hdefereval` at handlers_tops/cook.py:34, :95, :143, :227, :281, :325, :370, :419; work_items.py:40, :126, :201, :279; diagnostics.py:42, :125, :248, :399; render_sequence.py:108, :357; wedge.py:30, :94
- `grep -rn 'hdefereval\.\w+' python/` returns ZERO hits in any handlers_tops file — the only live attribute accesses repo-wide are main_thread.py:309 and main_thread_executor.py:290
- Example verified by reading: python/synapse/server/handlers_tops/cook.py:34 imports it, then `_run()` at :41-79 uses only `hou.node`, `node.getPDGNode()`, `node.cook(...)`

*VERIFIED · hygiene · effort: trivial*

### Routing, session, and uptime metrics are hardcoded zeros despite 33,948 real dispatches

**Claim.** The live_metrics routing and session blocks and the corresponding Prometheus gauges report all zeros — total_requests 0, uptime_seconds 0.0, commands_per_minute 0.0, active_sessions 0 — while the same snapshot's dispatch histogram records 33,948 dispatches and 31 ping calls.

**Why it matters.** An uptime of 0.0 on a process with ~19 hours of heartbeats is self-evidently broken. Anyone triaging a freeze from the metrics surface would see an idle, healthy-looking system. This is why the 17.2s dispatch wait and the 46.7s panel stall are invisible to every dashboard view except the raw histograms.

**Action.** Wire the routing/session aggregator to the real dispatch counters, or remove the gauges — publishing confident zeros is worse than publishing nothing.

**Evidence.**

- synapse_live_metrics routing block: `"total_requests": 0, "avg_latency_ms": 0.0, "cache_hits": 0, "cache_hit_rate": 0.0, "knowledge_entries": 0, "tier_counts": []`
- synapse_live_metrics session block: `"active_sessions": 0, "commands_per_minute": 0.0, "total_commands": 0`
- synapse_metrics gauges: `synapse_uptime_seconds 0.0`, `synapse_sessions_active 0`, `synapse_commands_per_minute 0.0`
- Contradicted in the same scrape by `synapse_dispatch_wait_ms_count 33948` and `synapse_tool_duration_ms_count{tool="ping"} 31`
- Zeros persisted identically across all 3 historical snapshots

*VERIFIED · hygiene · effort: small*

### Dormant Houdini event hooks would do a full file read + rewrite on the main thread on every parm change

**Claim.** `synapse/hooks/synapse_hooks_houdini.py` registers `ParmTupleChanged` callbacks whose handler appends to a JSONL file and then calls `_maybe_rotate`, which reads the ENTIRE file into memory and rewrites it — synchronous disk I/O on Houdini's main thread per event — but nothing in the repo imports or auto-loads this module, so it is currently inert.

**Why it matters.** Houdini node event callbacks execute on the main thread by construction. A slider drag emits ParmTupleChanged continuously; each event here costs an append plus a full-file read and potentially a full-file rewrite. If this module is ever wired into a startup script it becomes an immediate, severe, artist-facing freeze that no existing guard covers — marshal_guard's scoping rule explicitly excludes benign main-thread file I/O.

**Action.** Before this is ever wired: buffer events in memory and flush from a daemon thread, and replace `_maybe_rotate`'s read-all/rewrite-all with a size check plus periodic truncation. If it is abandoned, delete it so it cannot be revived by a future 123.py.

**Evidence.**

- C:/Users/User/SYNAPSE/synapse/hooks/synapse_hooks_houdini.py:35-53 — `_write_event` does `os.makedirs(...)` then `with open(EVENTS_FILE, 'a', ...) as f: f.write(line)` then `_maybe_rotate()`
- C:/Users/User/SYNAPSE/synapse/hooks/synapse_hooks_houdini.py:56-65 — `_maybe_rotate` does `f.readlines()` over the whole file, and on overflow `f.writelines(lines[-MAX_EVENTS:])` — a full rewrite
- C:/Users/User/SYNAPSE/synapse/hooks/synapse_hooks_houdini.py:111-118 — watched child events include `hou.nodeEventType.ParmTupleChanged`; :195 `node.addEventCallback(_get_child_events(), _on_child_event)`; :183 `_write_event(f"node_{name}", path, ...)`
- C:/Users/User/SYNAPSE/synapse/hooks/synapse_hooks_houdini.py:28 `MAX_EVENTS = 200`
- Not auto-loaded: repo-wide grep for `synapse_hooks_houdini|register_scene_callbacks` (excluding .claude/.git/.pytest) hits only the module's own docstring at :9-17 and its own definitions; `houdini/` (the hpath) contains no 123.py/456.py/pythonrc.py

*VERIFIED · risk · effort: small*

### Second gc heap scan on panel activation, with no caching at all

**Claim.** `chat_panel._find_running_server` walks `gc.get_objects()` with no weakref cache and no negative memoization; it is reached from `_ensure_server`, which runs on `onActivateInterface` (every time the panel becomes visible) and on the Connect button.

**Why it matters.** Bounded in frequency (the successful path caches into `hou.session._synapse_server` at :311/:331), so this is a one-shot activation cost rather than a recurring one — but it is the same anti-pattern as the health-timer scan and shows the gc-introspection idiom is used in more than one place. It is also on the legacy panel, so it is not live on this install.

**Action.** Replace both gc-introspection lookups with the explicit registries that already exist (`hou.session._synapse_server` for the server, `shared.bridge.get_process_bridge()` for the bridge).

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/panel/chat_panel.py:83-89 — `def _find_running_server(): import gc; for obj in gc.get_objects(): if type(obj).__name__ == 'SynapseServer' and getattr(obj, '_running', False): return obj; return None`
- C:/Users/User/SYNAPSE/python/synapse/panel/chat_panel.py:296-312 — `_ensure_server` early-returns only if `hou.session._synapse_server` is already set AND running; otherwise it calls `_find_running_server()` at :309
- C:/Users/User/SYNAPSE/python/synapse/panel/chat_panel.py:262-267 — `onActivateInterface` calls `self._ensure_server()`
- Same measured scaling as the health-timer scan: ~194 ms at 4.2M objects on plain CPython

*VERIFIED · freeze · effort: trivial*

### MemoryStore's writer-priority lock uses untimed condition waits and is held across full-file encrypted disk I/O

**Claim.** `ReadWriteLock._acquire_read` and `_acquire_write` call `self._cond.wait()` with no timeout, and the write lock is held across whole-file operations — a full read-and-decrypt at `store.py:329` and a full build-and-encrypt-and-write at `store.py:458` — while a 2 s daemon flusher independently takes locks on the same store.

**Why it matters.** Unbounded-by-construction waits held across encrypted whole-file I/O. On the shipped panel path tool dispatch is off-main (claude_worker.py:368-374), so a stall here wedges a worker thread rather than the GUI — which is why this ranks low. It becomes a main-thread hold the moment any run_on_main payload touches the store.

**Action.** Give `_acquire_read`/`_acquire_write` a bounded `wait(timeout=...)` with a loop and a diagnostic on expiry, and move the encrypt/serialize work outside the write lock (build the buffer first, hold the lock only for the swap).

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/memory/store.py:112-117 — `def _acquire_read(self): with self._cond: while self._writer or self._writer_waiting > 0: self._cond.wait()` (no timeout)
- C:/Users/User/SYNAPSE/python/synapse/memory/store.py:125-131 — `_acquire_write` same untimed `self._cond.wait()`
- C:/Users/User/SYNAPSE/python/synapse/memory/store.py:329-331 — `with self._lock.write_lock(): with open(self.memory_file, 'r', encoding='utf-8') as f: for line_num, line in enumerate(f, 1):` — whole-file read + per-line decrypt inside the lock
- C:/Users/User/SYNAPSE/python/synapse/memory/store.py:458-466 — `with self._lock.write_lock():` then builds every memory line with `crypto.encrypt_line(line)` and writes the file
- C:/Users/User/SYNAPSE/python/synapse/memory/store.py:198-204, 221-232 — a `daemon=True` flusher thread running `_flush_loop` on a 2.0 s interval

*VERIFIED · freeze · effort: medium*

### The standing latency report's central anchor points at a line that no longer holds it and resolves only to a changelog assertion

**Claim.** The report's '~95% LLM turn / 1–70ms Houdini ops' anchor cites CHANGELOG.md:293, which now contains unrelated text; the real claim is at :441 and is a changelog sentence with no primary artifact behind it. Two other load-bearing citations have also drifted.

**Why it matters.** The report is the standing authority and sits behind a human gate, so readers cannot self-correct. The 95% figure in particular is the premise for its entire 'not a transport problem' conclusion and resolves to a single unsourced changelog sentence — which is exactly the kind of number the per-call connection floor above calls into question.

**Action.** HUMAN GATE (Joe owns the report) then ENGINEERING (trivial): when the gate opens, repoint the changelog and websocket citations, add package paths, mark the 95% figure as changelog-sourced pending a re-measure, and record 'cancel unreachable' as closed by 9c9bc8e. Also record that the hwebserver migration gate's first condition (read-mix p95 above 5ms) is now met by a wide margin while its second remains untested.

**Evidence.**

- `sed -n '288,296p' CHANGELOG.md` returns composition-validation and bridge-fix text, no latency figures. The actual claim is at CHANGELOG.md:441 — 'the dominant cost is the **LLM turn (~95%)**; Houdini ops run **1–70 ms**' — and no session dump or benchmark output is cited anywhere for it.
- The report cites websocket.py:471-484 for the serial message loop; at HEAD that range is the auth handshake block, and the pump is now `for message in iter_messages(...)` at :546 with iter_messages defined at :103.
- Module paths omit their package directories (graph_builder.py and graph_validator.py are under python/synapse/host/ and python/synapse/cognitive/).
- Verified-good citations for contrast: claude_worker.py:34 `_MAX_TOOL_ITERATIONS = 25`, main_thread.py:20 `_DEFAULT_TIMEOUT = 10.0`, and the LATENCY_PLAN hwebserver ping figure are all exact.
- One report finding is now stale in the good direction: the 'cancel is unreachable' item was closed by 9c9bc8e, which replaced the blocking iterator with a 100ms cancel-polling generator at websocket.py:103-124. Only the serial-handling half remains true.

*VERIFIED · hygiene · effort: trivial*

### The production tree contains zero TODO/FIXME markers — every real gap is prose-only and therefore ungateable

**Claim.** A grep for TODO, FIXME, XXX and HACK across the routing, autonomy, server, memory and cognitive packages plus shared/, host/, agent/ and retina/ returns no hits; every capability gap in this report was found through prose phrases instead.

**Why it matters.** Any future audit, CI lint or agent that greps for conventional markers gets a clean bill of health over eight real gaps. The prose disclosure here is high quality and genuinely better than a bare TODO — but it is not machine-greppable, so the dormant surface cannot be counted or regression-gated and has to be rediscovered by hand each time.

**Action.** ENGINEERING (small): adopt one machine-readable marker convention (for example `# SYNAPSE-GAP: <id>` tied to a harness check) for gaps deliberately left open, and narrow the stale graph_builder.py comment to name only the writers that are genuinely unwired.

**Evidence.**

- `grep -rn --include=*.py -E "TODO|FIXME|XXX|HACK" python/synapse/{routing,autonomy,server,memory,cognitive}` → no output. The same pattern plus 'not wired|dormant|do not extend|Phase [0-9]' over shared/, host/, agent/ and retina/ returns exactly one hit (shared/conductor_advisor.py:335).
- By contrast the prose sweep surfaced eight real gaps at graph_builder.py:279, routing_log.py:7, evolution.py:9, driver.py:535, dispatcher.py:302, and _tool_registry.py:1443/1457/1495.
- One consequence already observed: graph_builder.py:279's 'provenance writers are dormant — no live caller yet' is now stale, because graph_synth_runtime.py:139-143 does pass a provenance_writer reachable from a live handler — so a reader under-counts what works.

*VERIFIED · hygiene · effort: small*

### Untracked scratch and stale memory notes keep resurfacing as open work

**Claim.** Seven .claude/commit_*.txt files are byte-identical to already-landed commit messages, the 2026-07-25 push-denied ticket is resolved, and the memory index still describes two merged PRs and one shipped panel milestone as open.

**Why it matters.** Twelve permanently-dirty untracked entries train the eye to ignore untracked files, which is how six latency-relay files sat unnoticed for weeks. Stale memory notes are worse: acting on 'PR #48 needs merging' burns a review cycle on already-merged work and erodes trust in the rest of the index.

**Action.** HUMAN GATE (trivial): drop the seven commit-message files and add `.claude/commit_*.txt` to .gitignore; drop the push-denied ticket and the stale health report and mat dump; transcribe the .token-saver capsule's open-gates list before dropping it and add `.token-saver/` to .gitignore. Keep .claude/h2-halt/ — commit it instead. ENGINEERING (trivial): correct the two memory notes about PRs #46 and #48 and the panel Mile 4 entry.

**Evidence.**

- All seven commit-message files diff clean against their landed commits (c0b9c2e, 15123f4, 8fbabd1, d0716f5, 340db86, 9c8fe87, 9c9bc8e) with the only difference being a missing trailing newline; `git check-ignore -v` shows all seven NOT-IGNORED, so they persist in git status permanently.
- The ticket is stale: `git merge-base --is-ancestor d9b8aa3 master` succeeds and both named branches exist on origin (origin/feat/cto-relay-01, origin/archive/root-scratch-2026-07-25). harness/clear/PLAN.md:19 already records it as stale and lists a disposal step that was never executed.
- STALE MEMORY NOTES, verified: `gh pr list --state open` → empty; #46 MERGED 2026-07-17, #48 MERGED 2026-07-22, #50 MERGED 2026-07-30. The memory index says 'PR #48, unmerged' and 'PR #46 needs Joe's merge'. Separately, panel Mile 4 shipped — python/synapse/panel/integrity_readout.py exists since 1304e4b.
- Also awaiting triage: docs/synapse_health_report.md (stale, reports v5.33.0), docs/mat_dump.json, and .token-saver/ (which contains a session capsule naming five open human gates).

*VERIFIED · hygiene · effort: trivial*

### Twenty TOPS handlers open with a dead hdefereval import that breaks them in headless hython

**Claim.** Every TOPS handler body begins with an unguarded `import hdefereval` that is never used — the real marshal goes through run_on_main — so in headless hython, where this repo records hdefereval as unimportable, all TOPS handlers raise ImportError on their first statement.

**Why it matters.** A dead import silently converts every TOPS and PDG tool into an ImportError in headless hython — the exact environment used for offscreen panel verification and CI probes. It is also a false signal for anyone auditing the marshal surface: twenty hits that look like blocking marshals and are not.

**Action.** ENGINEERING (trivial): delete the twenty vestigial imports plus the one in _common.py. No behaviour depends on them.

**Evidence.**

- Twenty sites: handlers_tops/cook.py:34,95,143,227,281,325,370,419; diagnostics.py:42,125,248,399; work_items.py:40,126,201,279; render_sequence.py:108,357; wedge.py:30,94 — plus _common.py:66.
- A repo-wide grep for actual attribute use `hdefereval\.\w+(` returns only two live hits, neither in handlers_tops: server/main_thread.py:309 and host/main_thread_executor.py:290.
- The real marshal is handlers_tops/_common.py:81-82 — `from ..main_thread import run_on_main` then `result = run_on_main(func, timeout=effective_timeout)`.
- The repo's own memory records hdefereval as unimportable headless and as the sixth headless-blind module.

*VERIFIED · hygiene · effort: trivial*

### Freeze dumps are stamped UTC while logs are local, making a pre-release test artifact read as a post-diagnosis production freeze

**Claim.** telemetry_dump.py stamps dump filenames in UTC while the log is local (UTC-4), so freeze_dump_20260801_014600.json appears to postdate the diagnosis commit but is 2026-07-31 21:46 local — 34 minutes before it — and its surrounding log window carries the pytest fingerprint.

**Why it matters.** Anyone triaging by directory listing hits the same trap, and it compounds with the known pytest log pollution. The correct reading is that the last verified production freeze is 2026-07-31 12:41 local, before the diagnosis was written.

**Action.** ENGINEERING (trivial): stamp dump filenames in local time or add a `local_ts` field alongside `ts` in collect_telemetry, and have flush_telemetry record whether it ran under pytest so test-authored dumps are self-identifying.

**Evidence.**

- python/synapse/server/telemetry_dump.py:242 — `stamp = datetime.now(timezone.utc).strftime(...)`.
- Offset confirmed against a doc-cited dump: the log line at 12:41:35 local references freeze_dump_20260731_164134.json, i.e. 16:41 UTC = 12:41 local.
- The dump's internals agree it is not a production freeze: synapse_version 5.40.1, total_heartbeats 1, dispatch_waits.count 0 — no real websocket traffic. Its log window at 21:46:49 shows 'Cannot start hwebserver: hwebserver not available' and repeated writes to a pytest tmpdir path.
- No log lines exist at all between 2026-08-01 00:00 and 02:00.
- The reviewing lane reported nearly filing this as 'the freeze recurred after the diagnosis' — a false alarm that would have misdirected the fix.

*VERIFIED · risk · effort: trivial*

### Four security-critical tasks are unblocked by the posture file and unstarted, with one gated behind an unratified flywheel cycle

**Claim.** harness/state/posture.json exists and declares solo mode with auto_approve true — which is the studio track's trigger — so S.1, S.2 and S.3 are unblocked and unstarted, while R.9 is transitively blocked on the unratified R.0 release cycle.

**Why it matters.** The posture file makes the ungated stance a documented per-mode choice rather than a defect, and CLAUDE.md §1.2 says the same — that is defensible today for single-user localhost. The relevant fact is simply that the work is unblocked, unstarted, and currently indistinguishable from pending, and that one of the four is waiting on a flywheel flip.

**Action.** HUMAN GATE first (small): decide whether the studio track is in scope this cycle at all — if not, say so in the board so these stop reading as pending; if yes, ratify R.0 to unblock R.9. The engineering itself (single-source policy table, dispatch-boundary consent, per-connection RBAC) is large and is explicitly human-authored by its own gates.

**Evidence.**

- harness/state/posture.json: `{"mode": "solo", "identity_model": "single local artist, one seat on localhost; no multi-user surface exposed", "auto_approve": true}` — S.0's gate states that writing this file is the trigger.
- S.2's gate text: 'arm consent on the non-panel bridges + record the consent source ... Closes the #1 critical (consent auto-approve/absent everywhere).' S.3: 'move authn/RBAC to the dispatch boundary keyed by per-connection identity.'
- R.9 is blocked_on='release_ratified' and R.0 is one of the 26 unratified cycles, so it is gated behind a flywheel flip rather than behind engineering. Its text names 'the entirely-ungated auth surface (no key ⇒ every token passes)'.
- harness/tasks.json holds 13 human-gated tasks out of 80, with 32 marked critical.

*VERIFIED · unfinished-work · effort: large*


---

## INFO

### There are zero open PRs; #46/#47/#48/#50 are all MERGED, contradicting the standing notes

**Claim.** `gh pr list --state open` returns an empty array; PR #46 (rulebook/proof-leg docs), #47, #48 (solaris harden) and #50 (mainthread freeze) are all in state MERGED.

**Why it matters.** The memory index still says 'Solaris harden harness (PR #48, unmerged)' and 'PR #46 needs Joe's merge'. Acting on those notes would waste a review cycle on already-merged work.

**Action.** Correct the two memory notes (solaris-harden-harness.md, synapse-rulebook-and-proof-leg.md) to record #46/#48 as merged.

**Evidence.**

- gh pr list --state open --json number,title,headRefName,baseRefName,mergeable,isDraft,updatedAt --limit 50 -> []
- gh pr view 46 -> {"state":"MERGED","updatedAt":"2026-07-17T15:26:40Z"}; 47 -> MERGED 2026-07-22; 48 -> MERGED 2026-07-22T12:25:21Z; 50 -> MERGED 2026-07-30T16:21:36Z
- gh auth status -> 'Logged in to github.com account joe002 (keyring)', scopes include 'repo' (authenticated, so the empty list is authoritative)

*VERIFIED · unfinished-work · effort: trivial*

### Six branches look unlanded to --contains/patch-id but their content IS on master

**Claim.** repair/h1-schemas-b, repair/ledger-moneta-seam, origin/repair/fake-hou-residency, forge/scout-opportunities, archive/retina-m2-orphan and worktree-wf_3b183969-cdc-3 all landed — some by patch-id match, some only visible by content probe after patch-id said UNLANDED.

**Why it matters.** This is the exact trap the lane warned about, and patch-id alone was insufficient on three of the six — re-homing a test into a different file defeats it. These six branches are safe to delete; deleting them without the content probe would have been a coin flip.

**Action.** Safe to delete all six local refs. Record that patch-id must be paired with a content probe when a leg re-homes files.

**Evidence.**

- patch-id MATCH: forge/scout-opportunities all 5 commits (5287006d->fc63067c, ea32f791->ee04f0bd, 76d8fca2->ed4e4d9b, bb5819a3->5b163456, a0453f3f->c1926c11); archive/retina-m2-orphan + worktree-wf_3b183969-cdc-3 (f3be38c3->1d160a9a)
- patch-id said UNLANDED for repair/h1-schemas-b 0929d568, but content probe: master:python/synapse/mcp/tool_impls/solaris/schema_create_variants.py:101 '# R33, 2026-07-26. Was ["created", "extended", "already_exists"]' AND the derived-AST pin was re-homed into tests/test_solaris_tool_registration.py:414 test_schema_return_status_enum_matches_implementation / :523 test_schema_reader_recovers_every_a
- patch-id said UNLANDED for repair/ledger-moneta-seam eb25abed, but master:python/synapse/memory/moneta_runtime.py:567 'def moneta_provenance(' and tests/test_ledger_moneta_seam.py is byte-identical on master (added by 189180d 'feat(memory): U1 - moneta_provenance() is one function with all five R64 fields')
- patch-id said UNLANDED for origin/repair/fake-hou-residency 6db6fd7, but master:tests/conftest.py has 8 HOU_REIMPORT_GUARD hits, tests/test_hou_reimport_guard.py is PRESENT, and `git diff master origin/repair/fake-hou-residency -- tests/conftest.py tests/test_hou_reimport_guard.py` is empty

*VERIFIED · unfinished-work · effort: trivial*

### origin/toolkit is a 12-commit, 5,276-line fossil from the pre-package era

**Claim.** origin/toolkit (67d6a44) is 12 commits ahead of merge-base 6f004a32 (2026-02-09) with 5,276 insertions across 21 files, all under paths (houdini/python_panels/, design/tokens.py, houdini/toolbar/) that predate the current python/synapse/ layout.

**Why it matters.** It is the largest unlanded remote branch by line count and it appears in every branch survey, but its file layout no longer exists in the repo, so it cannot be merged — only mined.

**Action.** Classify explicitly as abandoned/archive so it stops re-surfacing in surveys. If the Sprint C agent planning work matters, mine it deliberately rather than rebasing.

**Evidence.**

- git branch -r --no-merged master -> 'origin/toolkit  ahead=12  last=2026-02-13'
- git log --oneline 6f004a32..origin/toolkit -> 12 commits incl. 'feat(agent): Sprint C — multi-goal planning, checkpoint/resume, self-healing', 'feat(panel): wire Connect button to actually start/stop WebSocket server'
- git diff --stat 6f004a32..origin/toolkit | tail -5 -> 'design/tokens.py | 27 +-', 'houdini/python_panels/synapse_panel.pypanel | 216 ++-', 'houdini/scripts/python/synapse_shelf.py | 351 ++-', '21 files changed, 5276 insertions(+), 141 deletions(-)'

*VERIFIED · unfinished-work · effort: unknown*

### Master is fully pushed, no stashes, no unpushed tags

**Claim.** Nothing on master is unpushed and there is no hidden local-only state in stashes or tags.

**Why it matters.** Establishes that the loss surface is confined to branches and worktrees, not to master or to hidden git state.

**Action.** None. Use this as the baseline for the cleanup pass.

**Evidence.**

- git rev-list --left-right --count origin/master...master -> '0\t0'
- git stash list -> empty
- comm -23 <(git tag) <(git ls-remote --tags origin | ...) -> empty (no local-only tags)
- git for-each-ref refs/heads: only repair/fake-hou-residency [ahead 2, behind 1] and wip/panel-goalposts [ahead 2, behind 626] show ahead counts; both of repair/fake-hou-residency's ahead commits (0b5806ca, c0cc415b) verified IN MASTER

*VERIFIED · unfinished-work · effort: trivial*

### The core production tree contains zero TODO/FIXME/XXX/HACK markers — unfinished work is recorded in prose only

**Claim.** A grep for TODO|FIXME|XXX|HACK across python/synapse/{routing,autonomy,server,memory,cognitive}, shared/, host/, agent/ and retina/ returns no hits; every real capability gap in this lane was found instead through prose phrases like "dormant", "not wired", "SCAFFOLD", "unreachable", "Phase N", and "do not extend".

**Why it matters.** Any future audit, CI lint, or agent that greps for conventional markers on this repo will report a clean bill of health over the eight real gaps above. The convention here is high-quality prose disclosure, but it is not machine-greppable, so it cannot be gated.

**Action.** Adopt one machine-readable marker convention (e.g. a `# SYNAPSE-GAP: <id>` comment tied to a harness check) for the gaps that are deliberately left open, so the dormant surface can be counted and regression-gated instead of re-discovered by hand each audit.

**Evidence.**

- `grep -rn --include=*.py -E "TODO|FIXME|XXX|HACK" python/synapse/routing python/synapse/autonomy python/synapse/server python/synapse/memory python/synapse/cognitive` → no output
- `grep -rn --include=*.py -E "TODO|FIXME|XXX|HACK|not wired|dormant|never executed|do not extend|Phase [0-9]|not yet" shared/ host/ agent/ retina/` → exactly one hit: shared/conductor_advisor.py:335 ("...shipped through the agent.usd schema (Phase 4 of CLAUDE.md §9)")
- By contrast the prose sweep surfaced: python/synapse/host/graph_builder.py:279, python/synapse/panel/routing_log.py:7, python/synapse/memory/evolution.py:9, python/synapse/autonomy/driver.py:535, python/synapse/cognitive/dispatcher.py:302, python/synapse/mcp/_tool_registry.py:1443/1457/1495, python/synapse/memory/scene_memory.py:190

*VERIFIED · hygiene · effort: small*

### Class 2 (marshal self-deadlock) is FIXED-VERIFIED with a structural lint guarding it

**Claim.** No shipped source calls the blocking marshal or the H22 phantom; both live marshal sites are non-blocking with explicit thread checks; a source lint and 32 targeted tests pass at HEAD.

**Why it matters.** This class is closed and, unusually, protected by a guardrail that fails loudly rather than a convention — the line-scoped allowlist design at test_marshal_lint.py:92-121 specifically prevents the file-wide blind spot that previously hid the largest marshalling module.

**Action.** No action. Preserve the empty allowlists; adding an entry to silence red would reopen the class.

**Evidence.**

- Exactly two live `hdefereval.executeDeferred` call sites repo-wide: python/synapse/server/main_thread.py:309 and python/synapse/host/main_thread_executor.py:290 (verified by `grep -rn 'hdefereval\.\w+' python/` — every other hit is prose)
- Thread checks present: main_thread.py:240 `if threading.current_thread().ident == _MAIN_THREAD_ID:` (Fast path 2) and main_thread_executor.py:241 `if threading.current_thread() is threading.main_thread():`
- Zero `executeInMainThreadWithResult` / `executeInMainThread` / `_queueDeferred` call sites in houdini/, agent/, scripts/, retina/, forge/, host/, demo/, claude/, synapse/, or repo-root *.py (scanned individually)
- tests/test_marshal_lint.py:239 `test_no_blocking_main_thread_marshal` and :264 `test_no_phantom_main_thread_marshal`, both with EMPTY allowlists (:122, :127) and a staleness assertion at :284
- `python -m pytest tests/test_marshal_lint.py tests/test_render_bounded.py tests/test_websocket_cancel_reachable.py tests/test_main_thread.py -q` → '32 passed, 2 warnings in 8.98s'

*VERIFIED · freeze · effort: trivial*

### Class 3 (Qt-fallback inline) is FIXED-VERIFIED — tests pass and the production log shows the overrun records stopping the day the fix merged

**Claim.** The bridge-DOWN tool fallback dispatches on a daemon thread at HEAD, is pinned by 8 dedicated tests asserting off-main execution, and the live log shows main-thread inline overruns ceasing after the fix merged.

**Why it matters.** This is the one class where the fix, the test, and independent production telemetry all agree. The 48.35s `handlers.execute_python:inline` record on 2026-07-28 shows what the artist was living with before it.

**Action.** No action on the fix itself. Close the h9 residual (separate finding) so it cannot be re-armed.

**Evidence.**

- python/synapse/panel/claude_worker.py:374 `self._dispatch_off_main(request)` → :461 `_spawn_off_main_tool_thread(executor, request)` → :50-61 daemon `threading.Thread(target=executor.execute_tool_off_main, ...)`
- python/synapse/panel/tool_executor.py:497-523 `execute_tool_off_main` runs `_dispatch` on the caller's (daemon) thread
- tests/test_offmain_fallback.py:203 `test_offmain_fallback_runs_handler_off_main` asserts `handler.thread_idents[0] != main_ident`; :225 asserts run_on_main itself is called off-main
- `python -m pytest tests/test_offmain_fallback.py tests/test_context_poll_offmain.py tests/test_marshal_hostile.py tests/test_main_thread_zombie.py -q` → '42 passed, 2 warnings in 5.88s'
- LIVE CORROBORATION — ~/.synapse/logs/synapse.log holds 25 `[synapse.marshal_guard] WARNING: Main-thread inline payload at main_thread.run_on_main:fast_path_2` records ranging 5.18s–48.35s, all dated 2026-07-28 and 2026-07-29, and NONE after PR #50 merged 2026-07-30

*VERIFIED · freeze · effort: trivial*

### Concurrent agents shared the bridge during my probe window, contaminating latency attribution

**Claim.** 34 client connections were established during my ~2.5 minute probe window while I issued roughly 12 MCP calls, so the majority of bridge traffic in that window originated from other agents in this evaluation run.

**Why it matters.** My probe was not isolated. This is a confound I cannot remove after the fact, and it is the reason I anchored the ~2.01s finding on a millisecond-exact 1:1 mapping of four specific pings to four specific connection IDs rather than on aggregate counters, which are shared. Future live lanes should be serialized against the bridge.

**Action.** Serialize live-probe lanes, or tag each agent's connections with a distinguishable client identifier so per-agent attribution is possible.

**Evidence.**

- synapse.log 09:57:30–10:00:08 shows client_4.0.0_00006 through client_4.0.0_00039 = 34 connections
- Client IDs 00006–00010 were established at 2.005s spacing BEFORE my first ping (server ts 1785592667.66 → 09:57:47.66 → client_00011)
- Server-side tool_durations recorded calls I never made: `get_live_metrics` and `get_metrics` counts incremented in telemetry.json before I invoked either
- Ping count reached 31 server-side against roughly 12 pings from me

*VERIFIED · hygiene · effort: small*

### The untimed-send and second heap-scan seams live in chat_panel/ws_bridge, which the installed package does not load

**Claim.** The Houdini package's `hpath` exposes only `houdini/python_panels/synapse_panel.pypanel`, which loads `synapse.panel.synapse_panel`; that module contains zero references to `ws_bridge`, `chat_panel`, or `SynapseWSBridge`, so seams in those two modules are latent-legacy rather than live on this install.

**Why it matters.** Severity ranking for the two chat_panel/ws_bridge seams depends entirely on this. It also means the repo carries two panel implementations with divergent freeze postures — the shipped one stops no timers, the legacy one does (`onDeactivateInterface`, chat_panel.py:275-281) — so a future revert or re-point would silently change which seams are live.

**Action.** Either delete the legacy chat_panel/ws_bridge pair or state its status in-file, so the next freeze investigation does not spend time on a module that cannot fire.

**Evidence.**

- `cat packages/synapse.json` → `"hpath": "$SYNAPSE_ROOT/houdini"`
- `find houdini/ -type f` → `houdini/python_panels/synapse_panel.pypanel`, `houdini/scripts/python/synapse_shelf.py`, `houdini/toolbar/synapse.shelf` (no 123.py / 456.py / pythonrc.py)
- `houdini/python_panels/synapse_panel.pypanel` line 45: `from synapse.panel.synapse_panel import onCreateInterface as _build`
- grep for `ws_bridge|chat_panel|SynapseWSBridge` across synapse_panel.py, face_work.py, tool_executor.py, claude_worker.py returned zero hits
- `python/synapse/panel/synapse_chat.pypanel` (which does load `SynapseChatPanel`) is NOT under the hpath python_panels directory

*VERIFIED · freeze · effort: small*

### The cross-client mutation lock is held across a marshal, correctly scoped off-main but with an unbounded acquire

**Claim.** `_MUTATION_LOCK` is held across `registry.invoke()` — which marshals to the main thread and can run for minutes — but the guard at handlers.py:509-510 excludes main-thread callers, so this cannot self-deadlock the GUI; it can only make one off-main transport thread wait unboundedly behind another.

**Why it matters.** This is the lane's named lock-across-marshal pattern, and it is the one place where it is done RIGHT — worth recording as a positive control so a future refactor does not remove the `is not threading.main_thread()` clause without understanding why it is there. The residual (unbounded off-main acquire) is a transport-wedge, not a GUI freeze, and matches marshal_guard's documented out-of-scope list.

**Action.** No change needed. Consider a lint or comment marker pinning the main-thread exclusion at :510 so it survives refactors.

**Evidence.**

- C:/Users/User/SYNAPSE/python/synapse/server/handlers.py:250 — `_MUTATION_LOCK = threading.Lock()` (the only definition; grep found exactly two references repo-wide)
- C:/Users/User/SYNAPSE/python/synapse/server/handlers.py:509-511 — `_serialize = (_mutating and threading.current_thread() is not threading.main_thread())` / `_lock_cm = _MUTATION_LOCK if _serialize else contextlib.nullcontext()`
- C:/Users/User/SYNAPSE/python/synapse/server/handlers.py:526-539 — `with _lock_cm:` wraps `capture_scene_hash`, `self._registry.invoke(...)` and a second `capture_scene_hash`
- C:/Users/User/SYNAPSE/python/synapse/server/handlers.py:497-499 comment states the intent verbatim: 'skip on the main thread — already serialized there, and locking would deadlock run_on_main'

*VERIFIED · risk · effort: trivial*

### Negative result: the blocking-marshal surface is fully migrated and both remaining marshals are correctly guarded

**Claim.** There are exactly two live `hdefereval` invocation sites in the entire non-test, non-vendored tree; both use the non-blocking `executeDeferred`, both perform a thread-identity check before the wait, both bound the wait with a timeout, and both carry an abandoned-flag zombie kill — and there are zero live `executeInMainThreadWithResult` calls.

**Why it matters.** Answers the lane's first question definitively: no call site is missing BOTH a timeout and a thread-identity check, so there is no fifth *deadlock* class hiding in the marshal surface. The remaining freeze exposure is entirely about main-thread work VOLUME (inline payloads, timers, sleeps, socket writes), not about marshal correctness — which redirects remediation effort away from the marshal layer.

**Action.** Extend `test_marshal_lint.py` beyond banned primitives to also flag main-thread work volume patterns — `gc.get_objects()`, `time.sleep` and untimed socket writes reachable from a Qt slot or QTimer — since that is where the residual now lives.

**Evidence.**

- Repo-wide grep for `hdefereval\.[a-zA-Z_]*\(` across python/, shared/, scripts/, host/, synapse/, mcp_server.py returned only: `python/synapse/host/main_thread_executor.py:290: hdefereval.executeDeferred(_on_main)` and `python/synapse/server/main_thread.py:309: hdefereval.executeDeferred(_on_main)` — every other hit was a comment or docstring
- C:/Users/User/SYNAPSE/python/synapse/server/main_thread.py:230-231 (Fast path 1 reentrancy), :240 (`if threading.current_thread().ident == _MAIN_THREAD_ID:` → inline), :286-307 (state_lock + abandoned flag), :311 (`if not done.wait(timeout=timeout):`)
- C:/Users/User/SYNAPSE/python/synapse/host/main_thread_executor.py:241 (`if threading.current_thread() is threading.main_thread():` → inline), :276-288 (state_lock + abandoned), :292 (`if not done.wait(timeout=effective_timeout):`)
- All 20 TOPS `import hdefereval` sites are dead imports; the real marshal is `handlers_tops/_common.py:81-82` → `run_on_main(func, timeout=effective_timeout)`
- `shared/bridge.py:1411` records the migration: `# Was: hdefereval.executeInMainThreadWithResult(_sync_payload)`

*VERIFIED · freeze · effort: medium*
