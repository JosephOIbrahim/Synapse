# MARSHAL BOUNDARY — OPERATOR CARD

*Houdini 22.0.368 · SYNAPSE v5.32.1 · branch `fix/marshal-deadlock-class`*

---

## THE ONE THING

Houdini's main thread is a **service, never a client.**

It runs short work posted to it and returns to the Qt event loop. Anything that
needs a result from `hou.*` waits **off** main. When main becomes a client of
itself, Houdini locks — permanently, not slowly.

---

## WHAT WAS BROKEN

`hdefereval.executeInMainThreadWithResult` has **no thread check**. Called from
the main thread it queues work for itself, then parks forever waiting for itself
to run it. Vendor-level, H22.0.368, every invocation.

SYNAPSE reached it from main by two routes. Nine call sites bypassed the safe
primitive the codebase already had.

**The fix:** all nine now go through `run_on_main`, which short-circuits
main-thread callers to a direct call. A source lint keeps the unsafe primitive
out.

---

## RUNNING IT

```
Start        Houdini → Python Panel → Synapse → Start Server
Verify       synapse_ping                        → expect a pong, not a timeout
Port         9999                                → must show a LISTEN entry
```

```powershell
# Is Houdini alive, or wedged? Run this from OUTSIDE the process.
Get-Process houdini* | Select Id,Responding,CPU,WorkingSet64
Get-NetTCPConnection -LocalPort 9999
```

`Responding=True` + **no** listener on 9999 → the server was never started.
`Responding=False` → the main thread is wedged. Go to FAILURE MODES.

---

## HEALTHY vs DEGRADED

**Healthy turn** — tool call in, result out, UI stays live throughout. Nothing in
the log.

**Degraded turn** — you get a *typed error and a stack dump*, and the next turn
still works. This is the system working as designed. A degraded turn is a
report, not a crash.

```
MainThreadStarvationError        main held past budget — stacks dumped
RuntimeError: main thread
  didn't respond in time         a marshal timed out; see the hazard below
marshal_guard warning            a blocking wait ran on main — telemetry only
```

**Silent hang with no log line** — should now be impossible. If you see one, that
is the bug returning; capture the stack dump and reopen this sprint.

---

## KNOBS

```
SYNAPSE_MARSHAL_GUARD            warn (default) | raise
SYNAPSE_MAIN_INLINE_BUDGET_S     seconds before an inline main-thread payload
                                 is reported as an overrun
```

**Leave the guard on `warn`.** It is pure telemetry with zero behaviour change.
Flip to `raise` only after a clean soak, and only outside a release freeze —
raising can break paths that block on main benignly.

Render budgets live in `handlers_render.py` and are deliberate, not defaults.
Do not "tune" them to make a slow render look fast:

```
_RENDER_MAIN_TIMEOUT_S      3600s   is-it-alive ceiling, NOT a latency target
_CAPTURE_MAIN_TIMEOUT_S       30s   matched to the caller's own budget
_FLIPBOOK_FALLBACK_TIMEOUT_S 120s   single-frame grab on an already-failed path
```

---

## FAILURE MODES

**1 · UI frozen, no log, no recovery**
The old deadlock. Should be unreachable. Capture the dump, then restart Houdini —
a thread parked in `hdefereval._condition.wait()` cannot be un-wedged in-process.
*Recovery: restart. Then file it — this is a regression.*

**2 · "Main thread didn't respond in time" but the render finished anyway**
Known and accepted. On `/mcp`, a 120s budget wraps the whole dispatch; a longer
frame reports failure while the render continues and writes the file.
*Recovery: check for the output before re-running. Do NOT blindly re-dispatch —
you will render it twice.*

**3 · UI unresponsive during a render, then returns**
Not a bug. On the main thread a render cannot be made non-blocking, only made to
**complete**. The freeze became a stall. That is the ceiling of an in-process fix.
*Recovery: wait. Watch cores/GPU to confirm real work.*

**4 · Cancel does nothing during a long operation**
Known limitation. `websocket.py:471` handles messages serially, so `cancel` queues
behind the handler you are trying to cancel.
*Recovery: out-of-band only — `scripts/render_watch.ps1`, or kill the process.*
*This is the #1 follow-up; it is not fixed.*

---

## WHERE IT LIVES

```
SAFE TO READ, DO NOT EDIT CASUALLY
  server/main_thread.py           the one true marshal — fast paths + C4 + C6
  server/marshal_guard.py         guard, typed errors, inline-overrun telemetry
  server/freeze_chain.py          pre-existing freeze detection (extended here)

ENFORCEMENT — if these go red, stop
  tests/test_marshal_lint.py      bans the unsafe primitive; line-scoped allowlist
  tests/test_marshal_hostile.py   adversarial suite for the boundary

EVIDENCE
  docs/sprint_freeze/marshal_map.md    every blocking wait, per thread
  docs/sprint_freeze/gate_log.md       gates, CTO rulings, errata
  docs/sprint_freeze/done_signoff.md   the eight-item proof
```

**Never** reintroduce `hdefereval.executeInMainThreadWithResult`. The lint will
catch it; the lint exists because it cost a permanent freeze.

---

## THE HONEST LIMIT

The watchdog **reports and recovers the server. It cannot un-wedge a main thread**
already parked in a vendor condition wait or inside a native modal loop. Nothing
in-process can. Diagnosis and graceful degradation is the contract — not unfreeze.
