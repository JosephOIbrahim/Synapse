# BP8-CRUX - Verdicts for wave BP8

**Referee:** BP8-CRUX (adversarial crucible, branch `bp8/crux`, tier referee = Fable 5.1) · 2026-09-20
**Legs judged:** BP8-WATCHDOG (product `07f32f80`, receipt `c194d8a2`) and BP8-TIMEOUTS (product `03cf1872`, receipt `69687216`), both based on `79dbbfd9`. Neither is merged: `git branch --contains` names only the leg branches.

| Leg | CRUX verdict | JEV-SCREEN line (verbatim, `harness/jev/ledger/bp8.screen.jsonl`) | Agreement |
|---|---|---|---|
| BP8-WATCHDOG | **SOUND-WITH-NITS** | `screen BP8-WATCHDOG: REFEREE - full read; weak rows [1, 2, 4]; self_contradiction 0.22; crux_need 0.76` | agree (REFEREE beside SOUND*) |
| BP8-TIMEOUTS | **SOUND-WITH-NITS** | `screen BP8-TIMEOUTS: REFEREE - full read; weak rows [1, 2]; crux_need 0.80` | agree (REFEREE beside SOUND*) |

Neither leg is BROKEN. Neither leg is plain SOUND: WATCHDOG carries a `gui_required` row that is UNKNOWN (ceiling by rule), and both legs have guard holes the crucible's own mutations exposed (details per leg).

---

## Method

- **Fresh checkouts, never the builders' worktrees, never the main tree.** `git clone --shared -c core.longpaths=true` per leg under the session scratchpad: `w`/`wm`/`wp` at `c194d8a2` (bp8/watchdog), `t`/`tm` at `69687216` (bp8/timeouts), `m` at `64ccea8a` (master; master differs from the legs' base `79dbbfd9` by harness-only commits: `harness/battleplan/dashboard_bp8.py`). Shas in `bp8_crux/T1_probes.txt`.
- **Binding proven, not assumed.** Symbols that exist only on a leg (`router._llm_pool`, `handlers._ROUTE_OVERALL_TIMEOUT_S`) are `hasattr` True in the leg clone and False in the master clone; the watchdog test file run against the master package fails at import on `NO_RESPONSE_LINE`. (`T1_probes.txt`)
- **Interpreters.** Stock CPython 3.14.2 for everything; pinned hython 22.0.400 (Python 3.13.10, `SYNAPSE_HYTHON`, `QT_QPA_PLATFORM=offscreen`, via `.synapse/hytest.py`) for the real-Qt layer and for the vendored-SDK signature check. 22.0.429 is also installed and was never used.
- **Mutations.** 18 self-authored (`BP8-CRUX_mutations.json`, runner `bp8_crux/mutate.py`): each asserts its old text occurs exactly once, mutates, runs the leg's own test file with `-vv -rA`, restores the original bytes, and checks `git diff --quiet`; the baseline is proven green before the first mutation and after the last, in every run. No builder `proved_it_bites` row was replayed verbatim; W-M1 and T-M1/T-M2 are the mutations the two missions' `crucible_criteria` mandate.
- **The screen set depth only.** Both legs screened REFEREE, so both got a full read; the crucible's mutations are its own either way.
- **Nothing outside `harness/battleplan/notes/`, `harness/notes/receipts/BP8-CRUX.json` and the JEV ledger was written.** No product file edited, no contract feature flipped, no `gui_required` row measured.

## Screen pre-read (verbatim)

The receipts live on the leg branches, so the screen sees nothing from `bp8/crux`; the two receipts were staged untracked into `harness/notes/receipts/`, screened, and removed. Shadow table (`python harness/jev/jev_screen.py --wave bp8`):

```
leg           receipt  screen   crux             reason
BP8-TIDY      -        no receipt -
BP8-TIMEOUTS  green    REFEREE  -                weak rows [1, 2]; crux_need 0.74
BP8-WATCHDOG  green_wi REFEREE  -                weak rows [1, 2, 4]; self_contradiction 0.21; crux_need 0.76
```

Per-leg brief lines (`--leg`): the two lines in the table at the top. Jev is not bit-deterministic across runs (crux_need 0.74 vs 0.80 for TIMEOUTS, self_contradiction 0.21 vs 0.22 for WATCHDOG); the verdict word was REFEREE in all four judgments. Ledgers: `harness/jev/ledger/bp8.shadow.screen.jsonl`, `harness/jev/ledger/bp8.screen.jsonl` (committed on `bp8/crux`).

---

## BP8-WATCHDOG - SOUND-WITH-NITS

Receipt status `green_with_findings`, builder verdicts `pass, pass, pass, pass, UNKNOWN`. Product commit touches `python/synapse/panel/chat_panel.py` (+76/-4) and `tests/test_response_watchdog.py` (+306).

### Verdict rows (acceptance order; row index as the screen counts it)

| # | Predicate | Builder | CRUX | Crucible anchor (own) |
|---|---|---|---|---|
| 0 | after a send with no reply, waiting state is False and the typing indicator is hidden once the watchdog fires | pass | **pass** | Fresh clone, CPython: `test_watchdog_hang_clears_state_and_shows_one_line PASSED` (`bp8_crux/WATCHDOG_cpython_test_response_watchdog_c194d8a2.txt`). hython 22.0.400 offscreen: `test_real_qtimer_fires_and_stop_prevents_it PASSED`, 7 passed (`bp8_crux/WATCHDOG_hython22.0.400_offscreen_c194d8a2.txt`). Production wiring probe W-P1: `fired: true, waiting_cleared: true, no_response_lines: 1, hide_typing_indicator_calls: 1` (`bp8_crux/WATCHDOG_probe_wiring_baseline_hython22.0.400.json`). Reddened by W-M5 (`assert True is False` on the waiting flag) and W-M10 (`Expected 'start' to have been called once. Called 0 times.`). |
| 1 | a delivered response stops the watchdog; no 'no response' line appears afterwards | pass | **pass** | `test_delivered_response_stops_watchdog_and_no_late_line PASSED` under both interpreters. W-M1 (stop removed from the reply path only) reddens it right-reason: `Expected 'stop' to have been called once. Called 0 times.`; under hython W-M1 also reddens Layer 2 (`assert True is False` on `isActive()` after `_on_response`). |
| 2 | connection error and status->disconnected both clear the waiting state via the shared helper | pass | **pass** | Both helper tests PASSED under both interpreters. Grep on `c194d8a2`: `_waiting_for_response = False` at `chat_panel.py:160` (init) and `:900` (helper) only; `hide_typing_indicator()` at `:901` only - no third copy (`T1_probes.txt`). W-M3 and W-M4 redden each path on its own (`assert True is False`); W-M2 (helper stops hiding the indicator) reddens rows 0 and 2 together. |
| 3 | diff touches only chat_panel.py and tests; no hardcoded px or hex added | pass | **pass** | `git diff --stat 79dbbfd9 07f32f80`: exactly the two files above. Added lines matching `#[0-9a-f]{3,8}` or `[0-9]+px`: 0 (`T1_probes.txt`). The closing commit `c194d8a2` adds only `harness/notes/receipts/BP8-WATCHDOG.json`, which the constitution mandates. |
| 4 | in a live H22 panel a hung turn 2 shows the system line and the input works again | UNKNOWN | **UNKNOWN** | `gui_required`; the brief declares it UNKNOWN to the crucible. Probe W-P1 proves the production timer path under offscreen Qt, not a live panel against a real server-side hang. Joe's click. |

Regression re-run in the fresh clone: `tests/test_chat_panel.py` 85 passed / 17 skipped; `tests/panel/` 117 passed / 89 skipped (`bp8_crux/WATCHDOG_test_chat_panel_c194d8a2.txt`, `WATCHDOG_tests_panel_c194d8a2.txt`) - matches the receipt.

### Crucible criteria

- *"deletes the timer stop in _on_response and shows the second test reddens"* - done as W-M1, which removes the stop from the reply path only (the helper keeps it), so it isolates exactly the claim: reddens `test_delivered_response_stops_watchdog_and_no_late_line` and, under hython, the real-timer half; every other test stays green.
- *"authors its own mutations"* - 10, listed below; the builder's NAMED-but-not-executed rows (its proved_it_bites 3-5) were executed here as W-M3, W-M4, W-M10 and W-M9, and all redden.
- *"every verdict row carries the crucible's own anchor"* - table above.
- *"flips no contract feature and edits no product file"* - held.

### Mutations (10; 7 reddened, 3 survived by design as guard-hole probes)

| id | Mutation | Reddens | CPython | hython 22.0.400 |
|---|---|---|---|---|
| W-M1 | stop removed from `_on_response` only (legacy two lines restored there) | delivered-response test (+ Layer 2 under hython) | REDDENED | REDDENED |
| W-M2 | `_clear_waiting_state` no longer hides the typing indicator | hang test + both helper tests | REDDENED | REDDENED |
| W-M3 | `_on_connection_error` no longer calls the helper | connection-error test | REDDENED | REDDENED |
| W-M4 | disconnect branch of `_on_status_changed` no longer calls the helper | disconnect test | REDDENED | REDDENED |
| W-M5 | `_on_response_timeout` appends the line but never clears state | hang test (+ Layer 2) | REDDENED | REDDENED |
| W-M6 | **probe:** production `timeout.connect` line deleted in `createInterface` | nothing | SURVIVED | SURVIVED |
| W-M7 | **probe:** production timer made repeating (`setSingleShot(False)`) | nothing | SURVIVED | SURVIVED |
| W-M8 | **probe:** production interval set to 1 ms instead of `WATCHDOG_TIMEOUT_MS` | nothing | SURVIVED | SURVIVED |
| W-M9 | margin dropped (`_WATCHDOG_MARGIN_MS = 0`) | budget test (`assert 30000 > 30000`) | REDDENED | REDDENED |
| W-M10 | send path never arms the watchdog | hang + delivered + failed-send tests | REDDENED | REDDENED |

### Nits and findings

1. **Guard hole - the production wiring in `createInterface` is untested by the committed suite.** W-M6/W-M7/W-M8 survive under CPython *and* hython: the Layer-1 tests hand-inject a `MagicMock` timer, and the Layer-2 test rebuilds its own `QTimer` in `_wire_real_watchdog`, so `chat_panel.py:269-272` (parent, single-shot, interval, connect) is never what any test exercises. The crucible's probe (`bp8_crux/probe_watchdog_wiring.py`, hython 22.0.400 offscreen) builds the real interface and fires the *production* timer: today the wiring is right (single-shot, 35000 ms == `WATCHDOG_TIMEOUT_MS`, not armed until a send, parent `_root`, fires into `_on_response_timeout`, stays inactive after firing). Its negative control with the connect line deleted reports `fired: true, waiting_cleared: false, no_response_lines: 0` - the probe catches W-M6; the suite does not. Proposed follow-up: commit that probe as an offscreen test (spawn `BP8-WATCHDOG-WIRING-TEST`).
2. **Evidence provenance.** The receipt's rows 0 and 1 cite an "offscreen hython real-QTimer probe (RESULT ALL PASS)"; that script is not on the branch (the branch diff is the product file, the test file and the receipt). The crucible re-established the hython truth itself through `.synapse/hytest.py` pinned to 22.0.400: 7 passed. The claim was true; it was not reproducible from the branch alone.
3. **Skip is not pass, and the builder said so.** `test_real_qtimer_fires_and_stop_prevents_it` skips under stock CPython; CI evidence for the real timer exists only when the file runs under hython. Recorded, not held against the leg.
4. **Row 3 wording.** "diff touches only chat_panel.py and tests" holds for the product commit; the closing receipt commit necessarily adds a third file. Not a defect.
5. **Observation, out of scope.** `_on_response(response)` carries no turn id, so a late reply for turn N stops turn N+1's watchdog and a turn-(N+1) hang would then go unguarded. That is the pre-existing panel protocol shape, not something this leg introduced; noted for whoever adds request correlation.

**On the screen's reading.** Weak rows [1, 2, 4]: rows 1 and 2 pass on independent anchors and their mutations redden right-reason; row 4 is UNKNOWN as the screen suspected. The `self_contradiction 0.22` most plausibly reads the receipt's own "NAMED ... not separately executed" proved_it_bites rows against its pass verdicts; that was honest disclosure, and executing those exact mutations here confirmed every one.

**Verdict: SOUND-WITH-NITS.** Every headless row passes on the crucible's own anchors; the ceiling is forced by the UNKNOWN GUI row and reinforced by nit 1. **Screen vs CRUX: screen REFEREE, CRUX SOUND-WITH-NITS - agreement** (the screen's rule: CLEAR/REFEREE beside SOUND* is agreement). The screen pointed at the right rows; the guard hole it could not see is a test-structure fact, not an evidence-text fact.

---

## BP8-TIMEOUTS - SOUND-WITH-NITS

Receipt status `green`, builder verdicts `pass x5`. Product commit touches `python/synapse/routing/router.py`, `python/synapse/server/handlers.py`, `tests/test_bp8_timeouts.py`.

### Verdict rows

| # | Predicate | Builder | CRUX | Crucible anchor (own) |
|---|---|---|---|---|
| 0 | with a fake client sleeping 3x tier2_timeout, `_try_tier2` returns in under tier2_timeout + 1 s | pass | **pass** | Fresh clone: `test_try_tier2_returns_within_timeout PASSED`, call 1.03 s at `tier2_timeout=1.0` (`bp8_crux/TIMEOUTS_test_bp8_timeouts_leg_69687216.txt`, `--durations=0`). T-M1 (wall-clock timeout removed) reddens it: `AssertionError: took 3.01s`. T-M8 (timeout result with an empty answer) reddens the never-silent clause: `assert ''`. |
| 1 | same for the deep tier against tier3_timeout | pass | **pass** | `test_tier3_sync_returns_within_timeout PASSED`, call 1.00 s. T-M2 reddens it: `AssertionError: took 3.00s`. |
| 2 | a raising or timed-out route() produces a handler reply containing both `response` and `tier` | pass | **pass** | `test_handler_raising_route_replies_with_response_and_tier PASSED`; `test_handler_timed_out_route_replies_with_response_and_tier PASSED`, call 0.50 s at deadline 0.5. T-M3 (`except Exception` arm deleted) reddens: `RuntimeError: router blew up` propagates. T-M4 (deadline removed): `took 3.02s`. T-M5 (`tier` key dropped from the timeout reply): the `'tier' in reply` assertion fails. |
| 3 | the existing routing test suite is green; count before and after stated in the receipt | pass | **pass** | Master clone `64ccea8a`: `312 passed`; leg clone `69687216`: `312 passed` (`bp8_crux/TIMEOUTS_routing_suite_master_64ccea8a.txt`, `..._leg_69687216.txt`). Broader set (`test_handler_edge`, `test_handler_mutation_lock`, `test_model_lanes`, `test_model_routing_plan`): 45 / 45 (`bp8_crux/TIMEOUTS_broader_suite_*.txt`). Receipt's 312 -> 312 and 45 confirmed. |
| 4 | the mechanism used to pass the timeout is quoted from model_access.py with file:line | pass | **pass** | On `69687216`: `model_access.py:584 def guarded_create(client, *, lane, **kwargs)`, `:600 response = client.messages.create(**kwargs)`, `:650 timeout=60.0` (client-level ceiling). Runtime truth on the production interpreter: hython 22.0.400 / Python 3.13.10 loads the vendored `anthropic 0.96.0` and `Messages.create` has `timeout: float | httpx.Timeout | None | NotGiven = NOT_GIVEN`; CPython's pip `anthropic 0.75.0` likewise (`T1_probes.txt`). |

No UNKNOWN rows.

### Crucible criteria

- *"removes the timeout argument and shows the sleep test reddens"* - T-M1 and T-M2, both REDDENED right-reason (`took 3.01s` / `took 3.00s`).
- *"greps that no LLM call site in router.py is left without a timeout"* - on `69687216`, `router.py` has exactly two LLM call sites: `guarded_create(` at `:705` (tier 2) and `:939` (tier 3); each is submitted on `_llm_pool` (`:713`, `:947`) and awaited with `.result(timeout=_t2)` at `:715` and `.result(timeout=_t3)` at `:949`; there is no bare `messages.create(` in the file; the T0/T1 futures at `:344`/`:350` keep `timeout=2.0`. No site is left unbounded (`T1_probes.txt`).
- *"authors its own mutations"* - 8, below. *"every verdict row carries the crucible's own anchor"* - table above. *"flips no contract feature and edits no product file"* - held.

### Mutations (8; 6 reddened, 2 survived by design as guard-hole probes)

| id | Mutation | Reddens | Result |
|---|---|---|---|
| T-M1 | tier-2 `.result(timeout=_t2)` -> `.result()` | tier-2 sleep test (`took 3.01s`) | REDDENED |
| T-M2 | tier-3 `.result(timeout=_t3)` -> `.result()` | tier-3 sleep test (`took 3.00s`) | REDDENED |
| T-M3 | handler `except Exception` arm deleted | raising-router test (`RuntimeError: router blew up`) | REDDENED |
| T-M4 | handler `.result(timeout=deadline)` -> `.result()` | timed-out-router test (`took 3.02s`) | REDDENED |
| T-M5 | `"tier": "timeout"` removed from the timeout reply | timed-out-router test (`'tier' in reply`) | REDDENED |
| T-M6 | **probe:** `timeout=_t2` kwarg dropped from the tier-2 `guarded_create` call | nothing | SURVIVED |
| T-M7 | **probe:** `_record_metric(RoutingTier.STANDARD, ..., False)` dropped from the tier-2 timeout branch | nothing | SURVIVED |
| T-M8 | tier-2 timeout result carries `answer=""` | tier-2 sleep test (`assert ''`) | REDDENED |

### Nits and findings

1. **Guard hole - the SDK-side deadline is unpinned.** T-M6 survives: both fakes in `tests/test_bp8_timeouts.py` (`_make_slow_guarded_create`, `_fast`) accept and ignore `**kwargs`, and nothing asserts that `timeout=tier2_timeout` / `tier3_timeout` reaches `guarded_create`. That kwarg is the row-4 mechanism and the load-bearing half of the receipt's finding 3 ("an abandoned worker is bounded by the timeout= kwarg forwarded to the real SDK"): drop it and the wall-clock layer stays green while abandoned workers on the 4-worker `_llm_pool` run to the client-level 60 s ceiling (`model_access.py:650`). Follow-up: record the kwargs in the fake and assert them (spawn `BP8-TIMEOUTS-PINS`).
2. **Guard hole - the failure metric on timeout is untested.** T-M7 survives: target T1's clause "record the metric as a failure for that tier" has no test on the timeout path (same for the tier-3 branch by construction). Same spawn.
3. **The handler's safety comment states a false premise for a true conclusion.** `_handle_route_chat` says route() is safe off-thread because it "touches no hou.* API". It does reach one: `SynapseMemory.search` is `@_on_memory_main` (`memory/store.py:1758-1759`), which marshals through `_read_on_main` -> `run_on_main` whenever `hou` is present (`store.py:1326-1341`, `:1218-1241`), and route() reaches it twice - `enrich_context(memory=self._memory)` (`router.py:689-693` -> `context_enrichment.py:82`) and the tier-1 `KnowledgeIndex._match_memory` (`knowledge.py:818`); the memory handed in is the real owner (`handlers.py:1875 _memory_owner`). The offload is nevertheless safe, for a reason the comment does not name: `route_chat` is in `_READ_ONLY_COMMANDS` (`handlers.py:237`), and the server is `websockets.sync` (`websocket.py:365-380`) whose per-client thread calls `handler.handle()` directly on the read-only fast path (`websocket.py:566`, `:695-700`) - the handler never runs on Houdini's main thread, so a worker-to-main marshal behaves the same from the client thread and from `_route_pool`. The 28 s premise is also off: that fast path has no per-command kill at all (`websocket.py:700` has no timeout; "bypass resilience AND latency tracking"), and the 30 s the comment cites is `run_on_main`'s `_SLOW_TIMEOUT` (`main_thread.py:22`) for hou marshals *inside* handlers. Before this leg a hung route() blocked that client's server thread with no bound; 28 s is a new ceiling by design, which is the better story. If a later change ever dispatches `route_chat` onto the main thread, this offload would stall every memory-enriched turn until `run_on_main`'s 10 s timeout and count toward `is_main_thread_stalled()`. The comment should name the real invariant. Behaviour today is unaffected; this is a documentation nit with a sharp edge.
4. **Observation - asymmetric tier-2 exits.** A generic exception in `_try_tier2` returns None and falls through to tier 3 (`router.py:795-797`); a tier-2 timeout returns a failure result and does not. The note permits either; the receipt discloses the choice (finding 2). Not a defect. `RoutingResult` defines no `__bool__` (`router.py:88-90`), so `if result:` at `router.py:376` returns the timeout result as the builder intended.
5. **Context, not a nit.** `bp8_repro_ws.out.json` (13:15:23, pre-leg master, UTF-16 from a PowerShell redirect) shows both verdict turns answered in 3.05 s / 2.05 s with tier `standard` and the model-access denial text: the server-side turn-2 hang was not reproduced by that probe. This leg fixes the traced unbounded path; it is not a fix of a reproduced hang. The `ModelAccessDenied` path itself is preserved on the leg: the exception is raised in the `_llm_pool` worker, re-raised by `.result()`, and caught by the existing `except ModelAccessDenied` at `router.py:792`.

**On the screen's reading.** Weak rows [1, 2] were the deep-tier and handler rows; both pass on the crucible's own anchors and their mutations redden right-reason. The two guard holes (nits 1-2) are outside what evidence text can show.

**Verdict: SOUND-WITH-NITS.** All five rows pass on the crucible's own anchors and every mandated mutation reddens; the ceiling comes from the two guard holes and the safety-comment premise. **Screen vs CRUX: screen REFEREE, CRUX SOUND-WITH-NITS - agreement.**

---

## What only Joe can decide

- **BP8-WATCHDOG row 4** (live H22 panel: hung turn 2 shows the line, input works again) stays UNKNOWN - a click, not a guess. The builder's `for_ruling` says the same.
- **Merge words** for both legs. The crucible recommends merge for both, with the two spawns below ridden as follow-ups rather than blockers; that is Joe's call.
- **Whether nit 3 (TIMEOUTS) warrants a comment edit before merge** - it changes no behaviour.

## Artifacts (all on `bp8/crux`)

- `harness/battleplan/notes/BP8-CRUX_mutations.json` - the 18-mutation ledger with per-interpreter runs and right-reason strings, plus probe W-P1.
- `harness/battleplan/notes/bp8_crux/` - `mutate.py` (runner), `build_ledger.py`, `probe_watchdog_wiring.py`, `T1_probes.txt`, the three mutation logs, both probe outputs, and the pytest logs named per leg and sha.
- `harness/jev/ledger/bp8.screen.jsonl`, `harness/jev/ledger/bp8.shadow.screen.jsonl` - the screen judgments quoted above.
- Scratch clones stay in the session scratchpad (shared clones; disposable).
