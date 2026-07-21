# Definition of Done — Sign-off

Branch `fix/marshal-deadlock-class` · commit `607fc73` + live verification
Live session: Houdini 22.0.368, PID 64396, Python 3.13.10, Indie, UI available.

**7 GREEN · 1 PARTIAL (ruled).**

---

## D1 — The Phase 0 repro no longer freezes · **GREEN**

Repro used: `houdini_capture_viewport` over `/mcp` — candidate B, a CONFIRMED
deadlock pre-fix (`readOnlyHint=True` → read-only branch marshals the whole
dispatch onto main → `handlers_render.py:208` self-marshals from main → permanent
park in `hdefereval._condition.wait()`).

| Check | Result |
|---|---|
| Tool executed, result returned | PNG returned, twice (640x360 empty, 480x270 with real Solaris sphere content) |
| UI stayed live | `Responding=True` immediately after |
| Bridge serves next turn | `pong`, protocol 4.0.0 |

**Pre-condition verified before the run** (why this is a real test and not a
stale-code false pass) — live identity probe:

```
exec_on_main                       : true     MCP dispatch DOES run on the Qt main thread
hr_has_RENDER_MAIN_TIMEOUT_S       : true     fixed code loaded
hr_module_hdefereval_present       : false    the bypass is gone from handlers_render
mt_id_matches_real_main            : true     fast-path-2 will fire correctly
marshal_guard                      : LOADED
hd_has_phantom_executeInMainThread : false    vendor confirms the phantom
```

The last line is live confirmation of a separate finding: `shared/bridge.py` was
calling `hdefereval.executeInMainThread`, which **does not exist on H22.0.368**.
Three marshals were failing silently.

---

## D2 — Main provably never blocks on a turn result · **GREEN**

Enforced in code, not by convention, and demonstrated on the live build:

```
run_on_main called FROM the main thread
  result          : "ok"
  elapsed         : 0.014 ms      direct call — never queued, never waited
  payload_ran_on  : MainThread
  payload_inline  : true
```

The identical call shape on the old primitive parks forever. 14µs instead.

Enforcement: `tests/test_marshal_lint.py` bans the unsafe primitive repo-wide with
a LINE-scoped allowlist that fails loudly when stale;
`server/marshal_guard.py::forbid_main_thread_block` fails fast at the call site.

---

## D3 — Degrades to a recoverable typed error, never a silent hang · **PARTIAL**

**What is proven (live).** Deliberate 6s main-thread hold:

```
slow_result     : "slow-done"    payload COMPLETED, not killed or lost
inline_overruns : 0 → 1          telemetry fired
violations      : 0              correctly NOT flagged — slow work is not a violation
next_turn_ms    : 0.022          next call served 22µs later
event: {kind: inline_overruns, thread: MainThread,
        where: 'main_thread.run_on_main:fast_path_2',
        elapsed_s: 6.0004, budget_s: 5.0}
```

Precise attribution, no false positive on legitimate slow work, process survives.
Guard precision matters: a guard that cries wolf gets disabled, and then the
deadlock returns.

**Why PARTIAL.** `websocket.py:471` dispatches handlers inline in a serial
`for message in websocket:` loop, so `cancel` / `emergency_stop` / `status` queue
behind the handler you are trying to cancel. The watchdog can degrade the server;
it cannot deliver a message the transport will not read. "The daemon survives to
serve the next turn" is therefore false *on that connection*.

Ruled out of scope (gate_log R2): the fix is moving handler dispatch to a worker
pool — a transport concurrency change, declined during a feature freeze days
before the Leg 1 demo recording. **#1 follow-up.**

---

## D4 — Lands on the WS production path, not just the Dispatcher · **GREEN**

All nine bypass sites migrated. Registry reality (measured, not from the README):
**115 registry / 123 listed / 104 legacy + 13 dispatcher + 6 nowhere** — the
blueprint's "104 of 105" denominator does not exist, and the 11 already-ported
tools **still terminate at `handlers.py`**. So the legacy WS path is the majority
path, and `handlers.py:1795` + `handlers_render.py` + `mcp/server.py` are exactly
where the fix landed.

---

## D5 — Full suite green, zero tests weakened · **GREEN**

```
4642 passed · 0 failed · 100 skipped · 87.70s
floor (harness/verify/suite_baseline.json): 4275 passed / 0 failed / 87 skipped
```

+367 passing, zero failures. One headless run, no live bridge — per gate_log R9,
concurrent per-agent subsets are not a gate under the known module-level
`sys.modules` hou-fake residency trap.

**Two test files changed, both flagged, neither weakened:**

- `tests/test_host_layer.py` — pinned `executeInMainThreadWithResult`, the
  primitive deliberately removed. Re-anchored onto `executeDeferred` and SPLIT to
  add coverage of the main-thread fast path — the actual deadlock fix, which had
  no test at all.
- `tests/test_render_offmain_c11.py` — had gone **vacuous**: it detected "inside
  the main-thread closure" via a fake the code no longer calls, so it passed while
  pinning nothing. Re-anchored onto `run_on_main` and proven able to fail.

No assertion relaxed, no skip/xfail added, no case deleted, no other test touched.

---

## D6 — Hostile suite green · **GREEN**

`tests/test_marshal_hostile.py`, 809 lines: main-thread caller, concurrent
result-swap race, cook-holds-main, cancel-mid-marshal (pinning C4 zombie-kill
including its documented residual), client disconnect, watchdog degradation.
Runs isolated and in full suite. Failability demonstrated per scenario — a guard
that cannot go red pins nothing, which is precisely the defect this sprint found
in `test_render_offmain_c11.py`.

---

## D7 — Live soak, zero freezes · **GREEN**

~25 tool calls in one live session: concurrent read-only (5 at once), concurrent
mutating (4 node creations at once, incl. a `/stage` LOP), Solaris/USD stage
introspection, two viewport captures through the former deadlock path, parameter
set, `execute_python`, a deliberate 6s main-thread hold, six undos.

```
violations      : 0      zero blocking-wait violations across the whole soak
inline_overruns : 2      both from the deliberate test, correctly attributed
stack_dumps     : 0      watchdog never needed to fire
Responding      : True   at every checkpoint
```

Concurrent calls each returned their own correct payload — **no result swapping**,
confirming the vendor `_last_result` module-global race is not reachable through
`run_on_main`. Scene restored to empty via undo.

---

## D8 — Operator card · **GREEN**

`docs/sprint_freeze/OPERATOR_CARD.md` — start/stop, healthy vs degraded turn
signatures, the two env knobs, four failure modes with recovery, budget tuning,
files safe to touch, and the honest limit.

---

## Honest limits — not claimed as fixed

1. **On main, a render cannot be made non-blocking — only made to complete.** The
   permanent freeze became a bounded stall. That is the ceiling of an in-process
   fix, stated in `handlers_render.py` and the operator card.
2. **The watchdog cannot un-wedge a main thread** already parked in a vendor
   condition wait or a native modal loop. Nothing in-process can. Its contract is
   diagnosis plus graceful degradation.
3. **D3 PARTIAL** — the cancel path (above).
4. **`/mcp` abandon-then-continue** — a 120s dispatch budget means a longer frame
   reports failure while the render continues and writes the file; an agent may
   re-dispatch and double-render. Pre-existing, strictly better than the previous
   permanent deadlock, documented not fixed (gate_log R5).
5. **`_resolve_marshal` degenerate case** — with a real `hdefereval` present but
   `synapse.server` broken, a mutation now runs off-main instead of refusing.
   Bounded by `anchors_hold` (fidelity drops, rollback fires), unreachable in
   production, fix shape recorded (gate_log R6 reasoning).
6. **`foreground_guard` bypass** on the three render orchestrators — pre-existing,
   correctly not rerouted (rerouting would break per-frame result semantics).

---

## Not signed by me

**Merge to master.** Release-week §0.5 reserves scope amendments to Joe, and this
sprint appears in no leg of `SYNAPSE_RELEASE_WEEK.md`. CTO authority over the
blueprint's gates is not authority over the governing document. The work stays on
`fix/marshal-deadlock-class` until Joe decides. See gate_log DRIFT-01 and R3.
