# SYNAPSE Marshal Map — Authoritative Synthesis

> **Scope:** thread marshalling and blocking-wait attribution across all four inbound paths.
> **Built from:** seven independent team maps + their adversarial verifiers. Every
> disagreement below was settled by reading the source; the deciding `file:line` is cited.
> **Repo state:** master `4c3deae`. **Host:** Houdini 22.0.368, Python 3.13 (host) / 3.14 (tools).
> **Date:** 2026-07-21.

---

## 0. The one fact everything else hangs on

`hdefereval.executeInMainThreadWithResult` is **an unconditional, untimed park with no
caller-thread check.**

Read from the vendor source,
`C:/Program Files/Side Effects Software/Houdini 22.0.368/houdini/python3.13libs/hdefereval.py`:

```
:43-44   executeInMainThreadWithResult(code, *a, **kw) -> _queueDeferred(code, args, kwargs, block=True)
:91      _queue.append((code, block, num_waits, args, kwargs))
:92-93   if block:
             _condition.wait()          # <-- NO timeout. NO current-thread test.
:169     _condition.notify()            # sole notifier, inside _processDeferred
:84      hou.ui.addEventLoopCallback(_active_callback)   # _processDeferred's only driver
```

The only notifier runs from Houdini's idle event-loop callback, i.e. **only when the main
thread is idle**. Therefore:

- Called from a **worker** thread → correct marshalling.
- Called from the **main** thread → the main thread parks in `_condition.wait()`, the Qt
  event loop stops, `_processDeferred` can never run, the queued payload never executes,
  and nothing can ever notify. **Permanent. Unrecoverable. No error, no timeout.
  Requires killing Houdini.**

Two corroborations, both independently useful:

1. **SideFX guards this themselves.** `houpythonportion/ui.py:1232-1272` (`_runInUIThread`)
   runs three inline-escape gates *before* touching hdefereval — `isinstance(current_thread(),
   threading._MainThread)`, `not hou.isUIAvailable()`, and `hou._isCurrentThreadHoldingHOMLock()`
   — the last carrying their comment *"we cannot defer calling the target function in the main
   thread or else we will hit a deadlock."* The check is unambiguously the **caller's**
   responsibility.
2. **No H22 regression.** `hdefereval.py` is byte-identical between H21.0.773 and H22.0.368.
   Any self-marshal in SYNAPSE has been latent all along.

`hdefereval` is also **UI-only** — `:240-241` raises `ImportError` when `hou.isUIAvailable()`
is False. Every import site must be guarded (SYNAPSE's `*_AVAILABLE` doctrine, CLAUDE.md §12).

### The correct in-repo primitive, for contrast

`python/synapse/server/main_thread.py::run_on_main` (def `:204`) does it right and is the
benchmark every other site should be measured against:

```
:230   if getattr(_tls, "on_main", False): return fn()        # fast path 1 — reentrancy
:240   if threading.current_thread().ident == _MAIN_THREAD_ID: return fn()   # fast path 2 — caller IS main
:281   hdefereval.executeDeferred(_on_main)                   # NON-blocking enqueue
:283   if not done.wait(timeout=timeout):                     # bounded Event wait
:284-5     abandoned[0] = True                                # C4 zombie kill, under state_lock
:288-92    raise RuntimeError("Houdini's main thread didn't respond in time ...")
```

**`run_on_main` never calls `executeInMainThreadWithResult`.** It uses `executeDeferred` +
`threading.Event`. This is stated in the module docstring at `main_thread.py:5-6`.

> **ERRATUM — h22-scout map, refuted.** That map asserted "the /synapse WS-handler thread
> reaches [`executeInMainThreadWithResult`] via `server/main_thread.run_on_main`." **False**,
> decided by `python/synapse/server/main_thread.py:281`. `run_on_main` is the one helper that
> is *not* the defect; it implements SideFX's gate (1) twice. The h22-scout verifier's verdict
> of WRONG on that attribution is upheld.

---

## 1. Thread model

| Thread | Created at | Owns | May touch `hou.*`? |
|---|---|---|---|
| **MAIN** (Qt/Houdini) | process start; ident cached `main_thread.py:31` `_MAIN_THREAD_ID` | Qt event loop, all `hou.*` execution, `_processDeferred` drain, all widget painting | **Yes — exclusively.** It is the only thread that may. |
| **hwebserver C++ pool** (≤4) | `hwebserver_adapter.py:330-335`, `max_num_threads=4, in_background=True` | `@hwebserver.urlHandler("/mcp")` and `@hwebserver.apiFunction` dispatch | No — must marshal |
| **`Synapse-Server`** (daemon) | `websocket.py:259-264` | WS accept loop | No |
| **WS per-connection** (1 per client) | `websockets/sync/server.py:285` `threading.Thread(target=self.handler, ...)` | `_handle_client` → serial `for message in websocket:` → `_handle_message` → `handlers.handle` | No — marshals via `run_on_main` |
| **`synapse.render.session.<token>`** (daemon) | `handlers_render.py:429-436` | off-main `_handle_render` body for the WS bounded path | No — marshals |
| **`ClaudeWorker` QThread** | `panel/claude_worker.py:49` `class ClaudeWorker(QThread)` | model HTTP streaming, tool-loop driving, `tool_requested.emit` | **No** — one violation, see §3 `tool_executor.py:150` |
| **`SynapseWSBridge` QThread** | `panel/ws_bridge.py` (legacy chat panel only) | legacy panel socket I/O | No |
| **`Synapse-Watchdog`** (daemon) | `resilience.py:572` | heartbeat-absence detection, `on_freeze` callback | No |
| **`Synapse-TelemetryFlush`** (daemon) | `telemetry_dump.py:277` | periodic telemetry flush | No |
| **`synapse.host.main_thread_exec`** (daemon, per call) | `host/main_thread_executor.py:162-167` | one blocking `executeInMainThreadWithResult` hop | marshals only |
| **SynapseDaemon thread** | `host/daemon.py:251-256` | cognitive agent loop `run_turn` | No — via `main_thread_exec` |
| **`mcp_server.py` process** (separate OS process) | Claude Desktop `stdio` launch | stdio JSON-RPC ↔ outbound WS client | **No `hou` at all** |

**Marshal primitives in the repo — there are three, with divergent contracts:**

| Primitive | File | Main-thread guard? | Timeout? | Zombie guard? |
|---|---|---|---|---|
| `run_on_main` | `server/main_thread.py:204` | **Yes** (`:230`, `:240`) | Yes (10s / 30s / caller) | **Yes** (`abandoned[0]`, `:284`) |
| `main_thread_exec` | `host/main_thread_executor.py:197` | **No** | Yes (30s, `:169`) | **No** — payload runs on as a zombie |
| raw `hdefereval.executeInMainThreadWithResult` | 9 call sites, §3 | **No** | **No** | **No** |

---

## 2. The four paths

### 2.1 `/mcp` — external MCP

There are **two distinct surfaces** under this name, with different thread topologies. This
distinction is load-bearing and was missed by several maps.

**2.1-A · In-Houdini HTTP `/mcp`** (what a local agent / the panel's MCP fast path hits)

```
TCP accept                                          [hwebserver C++ pool thread, ≤4]
  mcp/server.py:685  @hwebserver.urlHandler("/mcp")  [pool thread]
  :728  handle_request(body, session_id)             [pool thread]
  :313  _route_method(method, params)                [pool thread]
    ├─ "initialize"     → :367  executeInMainThreadWithResult(dispatch_tool, ...)  ══ MARSHAL, UNBOUNDED
    ├─ "resources/read" → :601  executeInMainThreadWithResult(handler.handle, cmd) ══ MARSHAL, UNBOUNDED
    └─ "tools/call"     → :412  _handle_tools_call
         ├─ read-only tool (:435) → :438 executeInMainThreadWithResult(dispatch_tool,...) ══ MARSHAL, UNBOUNDED
         │                          RETURNS at :451 — before the stall gate (:459),
         │                          before the rate limiter (:472), before the breaker (:482)
         └─ mutating tool          → :514 run_on_main(lambda: dispatch_tool(...),
                                            timeout=timeout_for(tool_name))          ══ MARSHAL, BOUNDED
                                       ↓ [MAIN THREAD from here]
                                    mcp/tools.py:85  dispatch_tool  (payload build →
                                       bridge.execute → undo group → 2 scene hashes →
                                       handler.handle → session-journal write in finally)
```

**The whole handler is marshalled, not just the `hou.*` leaf.** `mcp/server.py:514-517` wraps
the *entire* `dispatch_tool` closure. Every blocking wait anywhere inside the bridge, the
handler, or the journal write therefore executes **on the main thread**. This is the single
most consequential structural fact on this path.

Note the comment at `mcp/server.py:504-511`: the migration to `run_on_main` was applied to the
**mutating branch only**. Three raw-primitive bypasses remain (`:367`, `:438`, `:601`) — no
timeout, no stall accounting, no breaker.

**2.1-B · stdio bridge** (what Claude Desktop is actually configured with)

```
Claude Desktop ──stdio/JSON-RPC──▶ mcp_server.py  [SEPARATE OS PROCESS, no hou]
   :957 call_tool → :322 send_command → :355 await asyncio.wait({future}, timeout=cmd_timeout)
   ──WebSocket client──▶ ws://localhost:9999/synapse
      → hwebserver_adapter.py:93 SynapseWS.receive   [WS per-connection thread]
      → handlers.handle → run_on_main → MAIN
```

Path B marshals only the `hou.*` leaf; Path A marshals everything. **That asymmetry is why
`/mcp`-in-Houdini is a prime suspect and the stdio bridge is not.** `mcp_server.py` is an MCP
**stdio server that is a WebSocket client** — it accepts no WS connections and serves no
JSON-RPC over WS.

### 2.2 `/synapse` WS

```
accept loop                       ["Synapse-Server" daemon thread, websocket.py:259]
  websockets/sync/server.py:285   spawns ONE thread PER CONNECTION
  websocket.py:471  for message in websocket:        [per-connection thread]
  websocket.py:484  self._handle_message(...)        [per-connection thread — SYNCHRONOUS, INLINE]
     :675  stall gate: is_main_thread_stalled() and not probe_main_thread()
     handlers.py:413  with _lock_cm:                 [_MUTATION_LOCK, off-main only]
     handlers.py registry → _handle_*                 [per-connection thread]
        → server/main_thread.py:204 run_on_main       ══ MARSHAL, BOUNDED (guards + Event.wait)
           → hdefereval.executeDeferred(_on_main)
              → [MAIN] fn() → hou.*
```

**No WS or accept-loop code ever runs a handler on the main thread.** The socket path is
structurally clean. Its real defect is different: **head-of-line blocking**. `websocket.py:471`
→ `:484` is a serial inline loop with no queue, so a long handler blocks every subsequent
message *on that connection* — including `cancel`, `status`, and the app-level heartbeat fast
path at `:567-578`. `websockets`' own keepalive is disabled (`ping_interval=None,
ping_timeout=None`, `:310-311`), so a wedged connection looks dead to both liveness mechanisms.
The stall exemptions (`:663-668`) and `render_farm_cancel`'s read-only classification bypass the
C5 lock and the resilience gates but **not** the serial loop. Escape is per-connection only —
a cancel on a *second* connection gets its own thread and proceeds.

### 2.3 In-process daemon / cognitive Dispatcher

```
[caller thread]  daemon.submit_turn(...)        daemon.py:494 — non-blocking, returns TurnHandle
                 → _request_queue.put            daemon.py:556
[DAEMON thread]  daemon.py:691 queue.get(timeout=0.25)
                 :722 run_turn(...)              agent_loop.py
                 :232 client.messages.create(...)   ← unbounded HTTP, holds daemon thread
                 agent_loop.py:282 dispatcher.execute(tool)
                 → daemon.py:752  with suppress_modal_dialogs():
                 → daemon.py:753  main_thread_exec(fn, kwargs)
                    → host/main_thread_executor.py:162-7 spawn worker "synapse.host.main_thread_exec"
                       worker :153  executeInMainThreadWithResult(lambda: fn(**kwargs))  ══ MARSHAL, UNBOUNDED on worker
                    → caller :169  done.wait(timeout=30.0)                                ══ BOUNDED on caller
[caller thread]  handle.result(timeout=None)     turn_handle.py:161 — UNGUARDED
```

**This path is not reachable in production.** Repo-wide grep: `SynapseDaemon` is constructed
**nowhere** outside `tests/` and `docs/`. `main_thread_exec` has exactly two call sites —
`daemon.py:753` (daemon thread) and `host/transport.py:73` (wired only via the
`SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE` env var in `tests/test_inspect_live.py`). All three
`mcp_server.py` Dispatchers are built `is_testing=True` (`:583-586`, `:701-705`, `:834`), and
`Dispatcher.execute` only reaches `_execute_via_main_thread` (`dispatcher.py:267`, `:295`) when
`is_testing=False`. **`_execute_via_main_thread` → `main_thread_exec` → `_exec_gui` is
unreachable from all 115 registry tools.**

It nonetheless contains the sharpest *latent* API hazards in the repo — see §3 rows for
`turn_handle.py:161` and `daemon.py:719`.

### 2.4 Qt panel

```
[MAIN]   Send click → SynapsePanel._on_send → _start_worker (synapse_panel.py:1618)
         ClaudeWorker.start()  →  spawns WORKER-1
[WORKER-1] claude_worker.py run() → _conversation_loop → provider.stream() (HTTPS, correct)
           stop_reason "tool_use" → _execute_tool_block

           ┌── PATH A (healthy, 3 threads) ────────────────────────────────────┐
           │ :254 try_mcp_tool_call → tool_executor.py:150 hou.webServer.port() │
           │      → http POST localhost:<port>/mcp                              │
           │      → [hwebserver POOL thread] → mcp/server.py :438 or :514        │
           │      → MAIN idles, _processDeferred runs, hou.* on MAIN, notify     │
           │      → pool thread wakes → HTTP 200 → WORKER-1 resumes              │
           │ No thread ever waits on itself. This is the design working.         │
           └────────────────────────────────────────────────────────────────────┘

           ┌── PATH B (fallback — MCP unreachable — 2 threads, MAIN dies) ──────┐
           │ :279-280 `pass  # MCP unavailable` — failure SWALLOWED             │
           │ :289 self.tool_requested.emit(request)                             │
           │      AutoConnection, receiver affinity MAIN ⇒ QueuedConnection      │
           │ :293 request.done.wait(timeout=budget)   [WORKER-1 parks, bounded] │
           │ ──────────────── [MAIN THREAD] ─────────────────────────────────── │
           │ tool_executor.py:368 @QtCore.Slot(object) execute_tool             │
           │   :425 execute_through_bridge → bridge_adapter.py:387 bridge.execute│
           │        shared/bridge.py:1115 operation.fn() — runs on CALLER thread │
           │        bridge_adapter.py:371 handler.handle(command)                │
           │   (read-only tools: :429 handler.handle directly, no bridge)        │
           │ → handlers_render.py:396 current_thread()==main_thread() → TRUE     │
           │ → :397 return _attach_advisory(self._handle_render(payload))        │
           │ → :771 executeInMainThreadWithResult(_render_on_main)  ══ SELF-MARSHAL
           │ → hdefereval.py:93 _condition.wait()  ══ PERMANENT DEADLOCK          │
           └────────────────────────────────────────────────────────────────────┘
```

Affinity proof, hop by hop, all verified: `synapse_panel.py:261` `ToolExecutor(parent=self)`
inside `SynapsePanel.__init__`, itself called from `onCreateInterface`
(`houdini/python_panels/synapse_panel.pypanel:41-45`) on MAIN → QObject affinity is MAIN.
`synapse_panel.py:1645` connects a `QThread`'s signal to that slot with no connection-type
override (repo-wide grep for `BlockingQueued`/`DirectConnection`/`invokeMethod` under
`python/synapse` returns **zero** hits) → AutoConnection resolves to QueuedConnection → **the
slot runs on MAIN**. `tool_executor.py:372-374`'s own docstring states this.

**PATH B is entered only when `hou.webServer.port()` returns None or the localhost POST fails**
— both swallowed (`claude_worker.py:279-280`, `tool_executor.py:491-492`). This is why the bug
presents as *intermittent*: identical prompts either work perfectly or hard-freeze Houdini
depending on whether hwebserver is up.

---

## 3. BLOCKING-WAIT LEDGER

Sorted by risk. `CONFIRMED_DEADLOCK` = proven unrecoverable park, no timeout can end it.

### CONFIRMED_DEADLOCK

| # | file:line | expression | thread | waits on | timeout? | risk |
|---|---|---|---|---|---|---|
| 1 | `Houdini 22.0.368/…/hdefereval.py:93` | `_condition.wait()` | **whatever thread calls it — no check exists** | `_condition.notify()` from `_processDeferred`, drivable only by an idle MAIN | **NONE — no parameter exists** | **CONFIRMED_DEADLOCK** |
| 2 | `server/handlers_render.py:771` | `hdefereval.executeInMainThreadWithResult(_render_on_main)` | **MAIN** on panel PATH B (via `:396→:397`) and on `/mcp` mutating (via `mcp/server.py:514`) | row 1 | **NONE** | **CONFIRMED_DEADLOCK** |
| 3 | `server/handlers_render.py:208` | `executeInMainThreadWithResult(_flipbook_on_main_thread)` | **MAIN** on panel (read-only branch `tool_executor.py:429`) **and on `/mcp`** (`houdini_capture_viewport` `readOnlyHint=True` → `mcp/server.py:438` already put us on MAIN) | row 1 | **NONE** | **CONFIRMED_DEADLOCK** |
| 4 | `server/handlers_render.py:865` | `fb_ok, fb_path = executeInMainThreadWithResult(_flipbook_on_main)` | **MAIN**, same `_handle_render` body as row 2 (def `:455`, entered `:814` when `render_ok` is False on usdrender) | row 1 | **NONE** | **CONFIRMED_DEADLOCK** *(masked today — row 2 fires first)* |
| 5 | `server/handlers.py:1795` | `report = future.result(timeout=driver._max_wall_clock + 60.0)` | the **asyncio loop thread** — provably, since `get_running_loop()` at `:1776` only succeeds there | a Future resolved by the task created at `:1794` *on the loop it is now blocking* | 660s (but the inner budget **exceeds** the 600s outer `timeout_for`) | **CONFIRMED_DEADLOCK** *(self-deadlock; not reachable on WS, bites on hwebserver/FastMCP)* |

### HIGH

| # | file:line | expression | thread | waits on | timeout? | risk |
|---|---|---|---|---|---|---|
| 6 | `mcp/server.py:438` | `executeInMainThreadWithResult(dispatch_tool, handler, tool_name, arguments)` | hwebserver pool | MAIN running the **entire** `dispatch_tool` for every read-only tool | **NONE** — and returns at `:451` before the stall gate (`:459`), rate limiter (`:472`), breaker (`:482`) | HIGH |
| 7 | `mcp/server.py:367` | `executeInMainThreadWithResult(dispatch_tool, handler, "synapse_project_setup", {})` | hwebserver pool | MAIN, during the `initialize` handshake | **NONE**; wrapped in `except Exception: pass` (`:374-5`) which cannot catch a hang | HIGH |
| 8 | `mcp/server.py:601` | `executeInMainThreadWithResult(handler.handle, command)` | hwebserver pool | MAIN, `resources/read` | **NONE**; `_route_method` reaches it without passing any resilience gate | HIGH |
| 9 | `server/handlers.py:1112-1125` | `run_on_main` import → `_on_main()` → `hou.undos.group` → `_run_compiled` | **MAIN** when reached via `/mcp:514` — so `run_on_main` takes **fast path 2** (`main_thread.py:240`) and the 30s `_SLOW_TIMEOUT` **silently evaporates** | arbitrary user Python; `exec_globals` (`:1104`) = full `__builtins__`, no import filter | **budget nullified** | HIGH |
| 10 | `server/handlers_render.py:1806` / `:1937` / `:1322` | `self._handle_render(payload)` **direct**, bypassing `_handle_render_bounded` | **MAIN** on panel PATH B | row 2 — with **no** foreground guard, **no** single-flight, **no** wait budget | **NONE** | HIGH |
| 11 | `server/api_adapter.py:103` | `return hdefereval.executeInMainThreadWithResult(fn)` (`_on_main_thread`, `:96-104`) | **UNKNOWN** — hwebserver `apiFunction` dispatch thread unverified | row 1 | **NONE**, no thread guard, no `isUIAvailable` inline fallback | HIGH |
| 12 | `host/main_thread_executor.py:169` | `if not done.wait(timeout=effective_timeout):` | **whatever thread calls `main_thread_exec` — NO guard exists** | Event set by the spawned worker, itself parked in row 1 | 30.0s (`:68`) | HIGH *(structurally; LOW by reachability — see §4-C)* |
| 13 | `host/turn_handle.py:161` | `signaled = self._event.wait(timeout=timeout)` | **any caller of `TurnHandle.result()` — NO guard** | Event set by the daemon thread (`:234`) | **`timeout=None` default ⇒ unbounded** | HIGH *(latent — no production `SynapseDaemon`)* |
| 14 | `shared/bridge.py:1595` | `_time.sleep(GATE_POLL_INTERVAL)` in `_wait_for_decision` (`:1585-97`) | **MAIN** if a gated bridge is ever reached from the panel or `/mcp` | `proposal.decision` leaving PENDING — a card only MAIN can draw | 120s APPROVE / **300s CRITICAL** (`shared/constants.py:71-72`) | HIGH *(defused today — see §5)* |
| 15 | `server/handlers_render.py:783` | `time.sleep(0.25)` × `range(60)` | **MAIN** on panel PATH B and on `/mcp`; worker on WS | nothing — a ~15s wall-clock output-file poll | 15s hard bound | HIGH *(latent: unmasks the moment row 2 is fixed)* |

### MEDIUM / LOW

| # | file:line | expression | thread | waits on | timeout? | risk |
|---|---|---|---|---|---|---|
| 16 | `panel/ws_bridge.py:358` | `executeInMainThreadWithResult(_gather_context_on_main_thread)` | would be **MAIN** | row 1 | **NONE** | LOW — **dormant**: repo-wide grep for `gather_context` returns only the def at `:343`; `chat_panel.py:797`/`:887` call `_gather_context_if_stale` → the module-level helper directly |
| 17 | `server/render_farm.py:509` | `val_result = pending_validation.result()` | **MAIN** on panel (`synapse_render_sequence` is non-read-only, panel-dispatchable) | ThreadPoolExecutor future running `_handle_validate_frame` | **NO TIMEOUT AT ALL** | MEDIUM — not a deadlock (`_handle_validate_frame`, `handlers_render.py:1039-1264`, contains zero `hou`), but an unbounded MAIN block during OIIO/numpy validation |
| 18 | `server/handlers.py:1797` | `report = asyncio.run(driver.execute(intent))` | **MAIN** on panel (`synapse_autonomous_render` is panel-dispatchable, `bridge_adapter.py:98`) | an entire event loop run inline on the Qt thread | **NONE** | HIGH *on the panel* — and its `_HandlerAdapter.call` (`handlers.py:1723-33`) can dispatch a plan step named `render`, reaching row 2 |
| 19 | `panel/claude_worker.py:293` | `completed = request.done.wait(timeout=budget)` | **ClaudeWorker QThread** — correct | Event set by `tool_executor.py:456` on MAIN | `max(30.0, timeout_for(tool)+5.0)` | NONE — **this is the symptom surface**, see §4 |
| 20 | `server/main_thread.py:283` | `if not done.wait(timeout=timeout):` | worker only — MAIN callers short-circuit at `:230`/`:240` | Event set by `_on_main` via `executeDeferred` | 10s / 30s / caller-supplied | **NONE** — the correctly-built primitive |
| 21 | `server/main_thread.py:179` | `run_on_main(lambda: True, timeout=timeout)` (`probe_main_thread`) | WS per-connection | ≤2.0s bounded probe | 2.0s | NONE |
| 22 | `server/handlers.py:413` | `with _lock_cm:` (`_MUTATION_LOCK`) | WS per-connection only — MAIN gets `nullcontext` (`:396-398`) | untimed `Lock.acquire()` | none, but every holder's own waits are bounded | LOW — a 2nd WS client's mutating command can queue ~90s with no stall visibility |
| 23 | `server/handlers_render.py:436` | `worker.join(timeout=wait_budget)` | WS per-connection — unreachable from MAIN (`:397` returns first) | render-session thread | 60.0s (`:57`) | NONE |
| 24 | `server/handlers_render.py:370` | `run_on_main(_guard_probe, timeout=5.0)` | WS per-connection | bounded probe | 5.0s | NONE |
| 25 | `websocket.py:471` | `for message in websocket:` | WS per-connection | next frame — **and, transitively, on the previous `_handle_message` returning** | none | LOW mechanically, **HIGH operationally** — head-of-line blocking, §2.2 |
| 26 | `host/main_thread_executor.py:153` | `executeInMainThreadWithResult(lambda: fn(**kwargs))` | the spawned `synapse.host.main_thread_exec` worker — **structurally never MAIN** | MAIN | **NONE** — worker leaks forever on caller timeout | LOW (daemon=True, `:165`) |
| 27 | `host/daemon.py:618` | `return handle.result(timeout=wait_timeout)` | caller — **guarded** at `:608` → `:643-661` (raises when `isUIAvailable()` and `current_thread() is main_thread()`) | row 13 | `wait_timeout=None` default ⇒ unbounded off-main | LOW |
| 28 | `host/daemon.py:258` | `self._started_event.wait(timeout=5.0)` | caller — plausibly MAIN, **unguarded** | daemon thread reaching `:687` (pure Python, no `hou`) | 5.0s (`:80`) | LOW |
| 29 | `host/daemon.py:289` | `self._thread.join(timeout=timeout)` | caller — plausibly MAIN, **unguarded** | daemon thread exiting `_thread_main`; if a GUI tool dispatch is in flight it cannot be interrupted (`agent_loop.py:282`) | 10.0s (`:83`) | LOW — 10s UI freeze **plus a guaranteed lost mutation** |
| 30 | `host/daemon.py:691` | `self._request_queue.get(timeout=0.25)` | daemon | queue put / poll tick | 0.25s (`:86`) | NONE — this is the pre-Spike-2.4 deadlock *inverted* |
| 31 | `cognitive/agent_loop.py:232` | `response = client.messages.create(**create_kwargs)` | daemon | Anthropic HTTP round-trip | **none passed** in `create_kwargs` (`:219-228`) | NONE for deadlock; holds the daemon thread across the whole call |
| 32 | `shared/bridge.py:1266-1271` | `await asyncio.wait_for(loop.run_in_executor(None, lambda: executeInMainThreadWithResult(_sync_payload)), timeout=120.0)` | asyncio executor thread (R2 `/mcp` async path) | MAIN | 120.0s | LOW |
| 33 | `shared/bridge.py:~1417` | `while not cook_complete.is_set(): …` (R8 PDG) | bridge caller | PDG `CookComplete`/`CookError` event | `cook_timeout` | LOW |
| 34 | `mcp_server.py:355` | `done, _ = await asyncio.wait({future}, timeout=cmd_timeout)` | stdio-bridge asyncio loop — **separate process, no `hou`** | WS response future | `_SLOW_COMMANDS`/`COMMAND_TIMEOUT` | NONE — this is the layer that **reports** the freeze |
| 35 | `mcp_server.py:577` / `:819` | `fut.result(timeout=…)` | `asyncio.to_thread` worker, separate process | `run_coroutine_threadsafe` future | 30s / `transport_outer_budget` | NONE |
| 36 | `panel/ws_bridge.py:397` | `self.wait(5000)` | **MAIN** (click slot + `onDestroyInterface`) | bridge QThread exiting | 5.0s | LOW — legacy panel only |
| 37 | `panel/tool_executor.py:150` | `return hou.webServer.port()` | **ClaudeWorker QThread** — a `hou.*` call **off MAIN** | nothing | n/a | LOW as a hang; **notable as a thread-safety violation** and as the silent selector between PATH A and PATH B |
| 38 | `resilience.py:559` / `:609`, `telemetry_dump.py:273` / `:294`, `freeze_chain.py:95` | watchdog/telemetry joins, sleeps, `threading.Timer` | dedicated daemon threads | shutdown Events / poll cadence | 2.0s / 1.0s / interval | NONE — deliberately isolated so a frozen UI cannot stop detection |

**Counts: 5 CONFIRMED_DEADLOCK, 10 HIGH** (rows 6-15), plus row 18 which is HIGH on the panel
specifically. Nine raw `executeInMainThreadWithResult` call sites exist in SYNAPSE:
`handlers_render.py:208/771/865`, `mcp/server.py:367/438/601`, `api_adapter.py:103`,
`host/main_thread_executor.py:153`, `panel/ws_bridge.py:358`. **`handlers_render.py:396` is the
only `current_thread()`/`main_thread()` comparison in that entire file.**

---

## 4. Ranked root-cause candidates

Reported bug: *external model issues a tool command → agent responds normally → Houdini locks
→ mutation never executed.*

All four candidates produce the same **user-visible** symptom. They are distinguished by
**where the main thread's stack terminates** and **whether the agent's error text names a
timeout**. A single live GUI session with one stack dump can separate all four.

---

### Candidate A — Panel PATH B self-marshal in `_handle_render` — **STRONGEST**

**Mechanism.** hwebserver is down or the localhost `/mcp` POST fails →
`claude_worker.py:279-280` swallows it → `:289` emits `tool_requested` → QueuedConnection
delivers `ToolExecutor.execute_tool` **on MAIN** → `handlers_render.py:396` correctly *detects*
the main thread and deliberately runs `_handle_render` inline (`:397`) → `:771` calls
`executeInMainThreadWithResult` **from MAIN** → `hdefereval.py:93` parks forever. The Qt loop
dies, `_render_on_main` never runs, `request.done.set()` (`tool_executor.py:456`) never fires.
WORKER-1's bounded wait at `claude_worker.py:293` expires after `budget` and writes
*"Tool … did not finish within Ns — it may STILL be running inside Houdini"* (`:295-299`).
**The model then composes a normal final answer while Houdini is permanently frozen and the
mutation never executed.** That is the reported symptom, exactly.

**Proof of possibility.** `handlers_render.py:393-397` (the branch and its comment, *"A bounded
wait is impossible — the render must run on this very thread"* — the premise is right, the
implementation contradicts it, because `executeInMainThreadWithResult` does **not** run inline;
it enqueues and waits); `hdefereval.py:92-93`; `synapse_panel.py:261` + `:1645` (affinity);
`tool_executor.py:368-369` + `:425`; `bridge_adapter.py:387`; `shared/bridge.py:1115`.

**DISCRIMINATING OBSERVATION.** In a live stack dump, the **MAIN thread frame stack ends in
`hdefereval._queueDeferred` → `threading.Condition.wait`**, with `handlers_render._handle_render`
(or `_flipbook_on_main_thread`) below it and `tool_executor.execute_tool` below *that*.
Additionally `hdefereval._queue` is **non-empty** and contains the un-run payload. And
`ClaudeWorker` is alive in `Event.wait`, not dead. **No other candidate puts
`tool_executor.execute_tool` beneath a `Condition.wait` on MAIN.**

---

### Candidate B — `/mcp` read-only branch on a wedged main thread — **STRONG**

Two sub-shapes, both real, both distinguishable from A.

**B1 · `capture_viewport` self-marshal via `/mcp`.** `houdini_capture_viewport` carries
`readOnlyHint=True` (verified by importing the registry: `TOOL_JSON['houdini_capture_viewport']
['annotations']['readOnlyHint'] is True`). So on `/mcp` it takes the read-only branch at
`mcp/server.py:435` → `:438`, which marshals the **whole `dispatch_tool`** onto MAIN. Once on
MAIN, `_handle_capture_viewport` reaches `handlers_render.py:208` and issues
`executeInMainThreadWithResult` **from MAIN** — the identical Candidate-A deadlock, but on the
branch with **no** timeout at *either* layer (no `run_on_main`, no stall gate, no breaker).
A read-only tool that hard-deadlocks Houdini is the one nobody expects.

**B2 · Pool exhaustion.** With MAIN wedged for any reason, four concurrent read-only `/mcp`
calls park all four hwebserver pool threads (`hwebserver_adapter.py:334 max_num_threads=4`)
in row-1 waits, **killing `/mcp` and the `/synapse` WebSocket in the same process**, including
the panel heartbeat.

**DISCRIMINATING OBSERVATION.** The parked frames sit on **hwebserver pool threads** (thread
names are Houdini-internal, *not* `Synapse-*` and *not* `MainThread`), each terminating in
`hdefereval._queueDeferred` → `Condition.wait`, with `mcp/server._handle_tools_call` below.
For B1 specifically, MAIN *also* terminates in `Condition.wait` but with
`handlers_render._handle_capture_viewport` below it — **and `tool_executor.execute_tool` absent
from the MAIN stack.** That absence is what separates B1 from A.

---

### Candidate C — `execute_python` opens a modal on MAIN via `/mcp` — **PLAUSIBLE**

**Mechanism.** `mcp/server.py:514` marshals `dispatch_tool` onto MAIN. `handlers.py:1112` then
calls `run_on_main`, which — already on MAIN — takes **fast path 2** (`main_thread.py:240`) and
calls `fn()` **directly, discarding the 30s `_SLOW_TIMEOUT`**. `exec_globals` (`handlers.py:1104`)
is `{"hou": hou, "__builtins__": __builtins__}` — full builtins, no import filter. Injected code
that opens a native modal (`hou.ui.displayMessage`) parks MAIN in a nested modal event loop
indefinitely. Meanwhile `docs/FORGE_SPEC_execute_python_fix.md:22` records that dialog
suppression is composed around the **daemon executor only, NOT around the WS `run_on_main`
path**. Grep for `displayMessage|isUIAvailable|_suppress` across `python/synapse/server`:
**zero matches.** No suppression layer exists on any server path.

**DISCRIMINATING OBSERVATION.** MAIN's stack terminates in **Qt's nested modal event loop**
(`QDialog.exec` / `QEventLoop.exec` frames), **not** in `Condition.wait`. `hdefereval._queue`
may be non-empty but MAIN is not parked on the condition variable.
Corroborating live probe: `QApplication.activeModalWidget()` returns **non-None** (PySide6
6.8.3 ships in H22; stub-verified at `PySide6/QtWidgets.pyi:584`, runtime-unverified). And the
agent's error text will read *"Houdini's main thread didn't respond in time"* (`main_thread.py:288`
message) only if some *other*, off-main caller timed out — the `execute_python` call itself gets
no timeout at all, because fast path 2 ate it.

---

### Candidate D — `HumanGate` consent poll on MAIN — **DEFUSED, RECORD ONLY**

**Mechanism.** `shared/bridge.py:1513` `_check_consent` prefers `self._gate` over the callback;
`_check_consent_gate` (`:1537`) → `_wait_for_decision` (`:1585-97`) `time.sleep`-polls up to
300s **on the caller's thread**, which on the panel is MAIN, waiting for an approval card only
MAIN can draw. **This has happened live** — documented verbatim at `bridge_adapter.py:181-186`:
*"Confirmed live: 'make a box' → execute_python (CRITICAL) froze the GUI exactly here."*

**Why it is defused.** `LosslessExecutionBridge.__init__` (`shared/bridge.py:460-464`) *does*
install a real `HumanGate` by default, but the only live construction site nulls it:
`shared/bridge.py:1946-1947` — `bridge = LosslessExecutionBridge(consent_callback=lambda op: True)`
then `bridge._gate = None  # never the blocking HumanGate poll` — reinforced by
`bridge_adapter.py:217`.

> **ERRATUM — mcp-path map.** It claimed the grep for `LosslessExecutionBridge(` excluding tests
> found "the ONLY construction site" at `shared/bridge.py:1946`. **False as stated.**
> `.scout/s1_repro.py:40` contains a bare `bridge = LosslessExecutionBridge()` outside `tests/`.
> Immaterial to the live process (a scratch repro script, never imported by the server), so the
> LOW rating stands — but the invariant was asserted more strongly than the evidence supports.

**DISCRIMINATING OBSERVATION.** MAIN's stack terminates in `bridge._wait_for_decision` →
`time.sleep`, and MAIN is **cycling** (repeated dumps show a live sleep loop at
`GATE_POLL_INTERVAL`), not parked. A and B park on a condition variable; C parks in a Qt loop;
**D is the only candidate where MAIN is still running Python.** Also settled instantly by
reading `get_process_bridge()._gate` — non-None means the defusal was broken.

---

### The single live repro that separates all four

One graphical Houdini session. Reproduce the freeze, then from an **out-of-band** thread
(the watchdog thread or `scripts/render_watch.ps1`) capture `sys._current_frames()` per thread
plus `len(hdefereval._queue)`.

| Observation on the MAIN thread | Verdict |
|---|---|
| `Condition.wait` **with** `tool_executor.execute_tool` in the stack | **A** |
| `Condition.wait` **without** `execute_tool`, `_handle_capture_viewport` present | **B1** |
| MAIN idle/healthy, ≥1 hwebserver pool thread in `Condition.wait` | **B2** |
| Qt nested `QEventLoop.exec` / `activeModalWidget()` non-None | **C** |
| `time.sleep` inside `_wait_for_decision`, MAIN still cycling | **D** |

Add, in the same session, three cheap one-liners that close §7's unknowns: log
`threading.current_thread().name` + `is_main` at the top of `_mcp_url_handler`, in
`SynapseWS.receive`, and in one `@hwebserver.apiFunction` body.

---

## 5. What already exists — REUSE, do not rebuild

| Capability | Status | What ships | What is genuinely missing |
|---|---|---|---|
| **Thread-tagged marshal trace** | PARTIAL | `scripts/freeze_trace.py` — `_log()` (`:35`) stamps `threading.current_thread().name` + `time.monotonic()`, **fsyncs every line** (`:40`) so it survives a force-kill; idempotent `_wrap()` (`:49`, `_ft_wrapped` guard); already wraps `run_on_main` (`:113-118`, logging its `timeout=`), the panel tool path, and `bridge._wait_for_decision` (`:108`) | (1) **no env flag** — `install()` is unconditional at `:128`; repo-wide grep for `SYNAPSE_TRACE*` = zero. It is exec-pasted into the Python Shell by hand. (2) traces `run_on_main` as one ENTER/EXIT pair — **no phase instrumentation** (enqueue → executeDeferred → callback-start → `fn()` → `done.set`), which is where a starvation diagnosis lives. **Reuse the thread-tagging, fsync durability, and wrapper installer verbatim.** |
| **Freeze watchdog + escalation + durable dump** | PARTIAL | `resilience.py:509` `Watchdog` (lazy-arm `:543`, monitor `:606`, `on_freeze` `:620`) → `freeze_chain.py:50` `FreezeChain` (`ESCALATION_S=30.0`, `:47`) → `freeze_chain.py:138-144` calls `flush_telemetry(reason='sustained_freeze')` writing timestamped `freeze_dump_<UTC>.json`, newest-5 retention (`telemetry_dump.py:182-197`). Pinned by `tests/test_freeze_chain.py` (6 tests, real Watchdog) | (1) **No stack content.** Repo-wide grep for `faulthandler`, `_current_frames`, `dump_traceback`, `traceback.extract_stack` across `python/` **and** `scripts/` = **ZERO**. `collect_telemetry()` (`telemetry_dump.py:99-179`) dumps counters and histograms only. A freeze dump today tells you *that* MAIN stalled, never *where*. (2) **Wrong trigger.** It fires on heartbeat *absence*, not on marshal timeout; `main_thread.py:189 _record_timeout` only increments a counter and `logger.warning`s — it notifies no watchdog. **Add a `thread_stacks` section to `collect_telemetry()` and hook `_record_timeout` to it. Do not rebuild the watchdog, escalation timer, peek discipline (`freeze_chain.py:181-215`), or atomic-write/prune plumbing.** |
| **Typed main-thread-starvation error** | PARTIAL | `host/main_thread_executor.py:72` `class MainThreadTimeoutError(TimeoutError)` — already raised at `:170-174` with callable name, budget, and the honest caveat that the payload may still be running. Also `core/errors.py:96 OperationTimeoutError(SynapseServiceError)` | The **dominant** path is untyped: `server/main_thread.py:288` raises a bare `RuntimeError`. Callers can only catch by `RuntimeError` or string-match. `resilience.py:868` `SERVICE_ERROR_TYPES` already contains both `TimeoutError` and `RuntimeError`, so adopting a typed subclass is **behavior-parity, low risk**. **Reuse one of the two existing classes — do not invent a third hierarchy** (INTEGRATOR owns shared types, CLAUDE.md §13). |
| **Main-thread detection** | EXISTS | `main_thread.py:31` `_MAIN_THREAD_ID` (cached at import), `:230` `_tls.on_main` reentrancy flag, `:240` identity comparison; `handlers_render.py:396`; `daemon.py:643-661` `_guard_against_main_thread_blocking_call` | Nothing **raises, asserts, warns, or lints**. Both server guards silently *downgrade* to inline main-thread execution — which is the freezing path. The nine raw `executeInMainThreadWithResult` sites have no check at all. **Reuse `_MAIN_THREAD_ID` and `_tls`; add the fail-fast.** |
| **Canonical per-tool timeout table** | EXISTS | `core/timeouts.py:74 timeout_for(name, default)`, exact→alias→prefix lookup over `SLOW_COMMANDS` (`:18-63`: render=120, tops_batch_cook=300, render_sequence=600, tops_cook_and_validate=600, autonomous_render=600, solaris_build_graph=30). Consumers: `mcp/server.py:513-516`, `tool_executor.py:233-245`, `claude_worker.py:43-44`, `autonomy/driver.py:125`. Pinned by `tests/test_timeouts_c7.py:56-68`, `tests/test_l8_mitigation.py:29-45`. Genuine cost-model component: `foreground_guard.optix_cache_state()` (`:62-91`) | (1) It is **tool-name**-aware, not **cook**-aware — nothing reads cook progress or `node.cookCount()`. (2) `run_on_main` **never consults it** — it uses its own `_DEFAULT_TIMEOUT=10.0` / `_SLOW_TIMEOUT=30.0`. (3) Three *other* independent timeout constants live outside it: `main_thread.py:20-21`, `shared/constants.py` (`PDG_DEFER_TIMEOUT`, `GATE_TIMEOUT_*`), `handlers_render.py:57` `_RENDER_WAIT_BUDGET_S`. (4) **`safe_render` / `autonomous_render` / `render_progressively` have NO `SLOW_COMMANDS` entry** — `timeout_for` returns the 10.0 default, so `claude_worker._wait_budget` returns its 30s floor. **Do not build a second table** — `core/timeouts.py` is explicitly the one canonical table (C7). |
| **Operator card** | EXISTS | `docs/render-freeze-operator-card.md` — 99 lines, current: mechanism, kit table (`render_watch.ps1`, `build_freeze_repro.py`, `husk_spike.py`, `freeze_trace.py` — all four present on disk), husk-spike first move, isolation matrix with XPU/CPU/Mantra fingerprints + OptiX cold-cache caveat, kill/recover commands, Indie fix layer table, new `houdini_render` payload keys, 5-item ship gate | **Update in place.** Global CLAUDE.md: *"One card per system — update it, don't multiply."* Two staleness fixes owed: `:4` cites `handlers_render.py:497` but the live marshal is **`:771`**; `:16` describes `freeze_trace.py` without noting it is exec-paste-only with no env toggle. |
| **TOPS migration precedent** | EXISTS | `handlers_tops/_common.py:76-80` already migrated all 28 TOPS call sites to `run_on_main` (`_PDG_DEFER_TIMEOUT=60.0`), with the comment *"One edit covers all 28 TOPS call sites."* | `handlers_render.py` never got that edit. **The fix shape is already proven in-repo.** |
| **Dialog suppression** | EXISTS, NARROW | `host/dialog_suppression.py:105` `suppress_modal_dialogs()` — `@contextmanager`, no args, patches 9 `hou.ui` names to raisers, restores in `finally` (`:140-148`), nesting-safe, no-op outside Houdini | Single production call site: `daemon.py:752` — **daemon path only**, and that path is unreachable (§2.3). **The WS and `/mcp` paths have no suppression at all.** Two further defects, verified: the `finally` restore fires when `MainThreadTimeoutError` unwinds from `main_thread_executor.py:169-174` **while the dispatched payload is still live on MAIN** — the now-unsuppressed body can open a real modal that blocks MAIN unbounded; and `dialog_suppression.py:31-32` claims *"Dispatcher serializes its executor, so this cannot happen"*, but `cognitive/dispatcher.py` contains **no lock or serialization primitive anywhere**. |

---

## 6. Blueprint claim errata

Every factual error found in the originating plan, each with the deciding citation.

1. **`host/main_thread_executor.py` — WRONG PATH.** There is no `main_thread_executor.py` under
   the root `host/`. Root `host/` holds only 7 introspection scripts. The real file is
   **`python/synapse/host/main_thread_executor.py`** (242 lines). **This root-vs-package error
   applies to every `host/*` path in the plan.**
2. **`host/dialog_suppression.py` — WRONG PATH.** Same error; real path
   `python/synapse/host/dialog_suppression.py` (148 lines).
3. **`suppress_modal_dialogs` is a context manager, not a function.** `@contextmanager`,
   `dialog_suppression.py:105`, takes **no arguments**. `suppress_modal_dialogs()` used as a
   plain call does nothing.
4. **Its scope is per-tool-call and daemon-path-only.** One production call site,
   `daemon.py:752`. Deliberately not a lifetime patch (docstring `:15-22`: hostile co-tenancy —
   the artist is also clicking). **`docs/FORGE_SPEC_execute_python_fix.md:22`: the WS path is
   UNCOVERED.** Any plan assuming global suppression for `/synapse` traffic is wrong.
5. **`TurnHandle.wait()` DOES NOT EXIST.** `handle.wait()` raises `AttributeError`. The public
   surface (`turn_handle.py`) is `done()` `:116`, `cancelled()` `:124`, `result(timeout=...)`
   `:132`, `cancel()` `:176`, and an `event` **property** `:196`. Legal wait shapes:
   `handle.result(timeout=…)` or `handle.event.wait(…)`.
6. **`submit_turn` no longer accepts `wait_timeout=`.** Removed in Spike 2.4. `daemon.py:494`
   signature is `(user_prompt, *, system, model, max_tokens, max_iterations) -> TurnHandle`.
   Passing `wait_timeout=` **TypeErrors**.
7. **`AgentToolError` is not an exception.** `cognitive/dispatcher.py:58`,
   `@dataclass(frozen=True)`. Its docstring: *"The agent sees this as ordinary tool output — it
   is NEVER RAISED."* `raise AgentToolError(...)` / `except AgentToolError:` are both broken.
8. **`tests/test_cognitive_boundary.py` is a regex source lint, not a boundary contract.** 66
   lines, one test (`:41`), which rglobs `python/synapse/cognitive/**/*.py` and asserts
   `^\s*(?:import\s+hou\b|from\s+hou\b)` never matches. It enforces nothing about the
   dispatcher, routing, thread safety, or runtime behaviour.
9. **`docs/crucible_protocol.md` contains no "Commandment 7."** `grep -i commandment` returns
   **zero** hits in that file. The canonical text is **`docs/sprint2/SPRINT2_EXECUTE.md:45`**
   ("ADVERSARIAL VERIFICATION — Separate builder from breaker…"). Two divergent restatements
   exist elsewhere (`.claude/agents/panel-relay/CRUCIBLE.md:20`,
   `.git/RELEASE_WEEK_DRAFT_STAGE.md:65`) — cite SPRINT2_EXECUTE.md:45, never crucible_protocol.md.
10. **`mcp_server.py` is not a "WS JSON-RPC dispatch."** It is an MCP **stdio** server that is a
    WebSocket **client** (header `:3-20`; `stdio_server()` at `:1062`; `websockets.connect` at
    `:298`). It accepts no WS connections, serves no JSON-RPC over WS, and has zero `hou`.
11. **"104 of 105" — numerator right by coincidence, denominator and direction both wrong.**
    Verified by import: `len(TOOL_DEFS) == len(TOOL_DISPATCH) == len(TOOL_JSON) == 115`. Tools
    *listed* to the client = **123** (115 registry + 6 group-info + `synapse_inspect_stage` +
    `synapse_scout`). Correct sentence: **"104 of 115 registry tools (104 of 123 listed) still
    use the legacy WS→`server/handlers.py` path; 13 touch `cognitive/dispatcher.py`; 6 dispatch
    nowhere."** No denominator of 105 exists anywhere in the repo.
12. **The 11 ported tools still hit `handlers.py`.** `mcp_server.py:972-976`: *"Same
    command_type + payload + response envelope as the TOOL_DISPATCH fallback below; the WS
    handler stays the execution primitive."* `:832` literally rebuilds them from
    `TOOL_DISPATCH[_name]`. Only Inspector and Scout (2) avoid the plain WS handler — and the
    Inspector still makes one `execute_python` WS round-trip. Counting the 11 as "no longer
    hitting handlers.py" is wrong.
13. **`hdefereval.executeInMainThreadWithResultAndDelay` is a PHANTOM.** Recursive grep for both
    that name and the bare substring `AndDelay` across the entire H22.0.368 `houdini` tree:
    **zero hits** (control grep for `executeInMainThreadWithResult` correctly returned 6 files).
    The real third function is `executeDeferredAfterWaiting(code, num_waits, …)` (`:32-41`),
    which delays by a **count of event-loop ticks**, not milliseconds, and is non-blocking.
    Do not emit the `AndDelay` name (CLAUDE.md §11 rule 15).
14. **`hdefereval.executeInMainThread` is also a phantom** — yet `shared/bridge.py:1401`, `:1425`,
    `:1456` call it. The complete H22.0.368 export list is `executeDeferred`,
    `executeDeferredAfterWaiting`, `executeInMainThreadWithResult`, their snake_case aliases,
    `in_separate_thread`, `do_work_in_background_thread`. `:1401` raises `AttributeError` into a
    broad `except Exception` reported as *"PDG callback error"* (misleading); `:1425`/`:1456` sit
    under `except Exception: pass` and **fail silently**. Out of dimension, real, unfixed.
15. **`run_on_main` does not call `executeInMainThreadWithResult`** (h22-scout map's central
    attribution). Decided by `server/main_thread.py:281`.
16. **`shared/bridge.py:1946` is not the only non-test construction site** —
    `.scout/s1_repro.py:40` also constructs a bare `LosslessExecutionBridge()`. Immaterial to
    the live process; the invariant was overstated.
17. **`daemon.py:719-720` asserts sit OUTSIDE the try block at `:721`** — refuting the claim that
    `_process_request` "always posts." An `AssertionError` there propagates to `_thread_main`'s
    `except BaseException` (`:698-700`), exiting the loop without completing or cancelling the
    already-popped request's `TurnHandle`. Because the request was popped at `:691`,
    `_drain_request_queue` (`:475-490`) cannot reach it and `stop()` (`:273-296`) does not cancel
    it — a caller in `handle.result(timeout=None)` hangs forever with no daemon left to post.
18. **`docs/L8_FREEZE_FIX_DESIGN.md:17`** — *"there is no `timeout_for` in `main_thread.py`"* is
    true as written but misleading: the helper exists in `core/timeouts.py`; it was simply never
    wired into `main_thread.py`.
19. **`docs/render-freeze-operator-card.md:4`** cites `handlers_render.py:497`; the live blocking
    marshal is **`:771`**.
20. **The C11 comment at `handlers_render.py:747-750`** — *"they now run on the WS handler thread
    below"* — is **true only on the WS path**. On `/mcp` (`mcp/server.py:514` marshals the whole
    handler) and on panel PATH B, "below" is also MAIN.
21. **`hou.ui.updateMode` / `setUpdateMode` are DEPRECATED** on H22 (`hou.py:123830-123833`) in
    favour of module-level `hou.updateModeSetting()` / `hou.setUpdateMode()`. Same block
    deprecates `hou.ui.mainQtWindow`→`hou.qt.mainWindow`, `hou.ui.createQtIcon`→`hou.qt.createIcon`,
    `hou.ui.qtStyleSheet`→`hou.qt.styleSheet`. The shims install **only under `isUIAvailable()`**,
    so headless CI never sees the warning — silent divergence from the artist's session.
22. **`hou.InterruptableOperation(timeout_ms=…)` will not bound `node.render()`.** H22 docstring:
    *"the timeout is usually only checked when you call the updateProgress() method."* No
    preemption. The parameter is identical in H21.0.773 (`hou.py:65017`) and did not prevent the
    confirmed freeze. Do not lean on it as an H22 improvement.
23. **HOM already auto-marshals ~130 functions** — `houpythonportion/ui.py:1283-1417`
    `_ui_thread_funcs`, wrapped at `:1420-1428`. Includes `hou.RopNode.render`, `Node.createNode`,
    `Node.destroy`, `Node.setInput*`, `Parm.pressButton`, `hipFile.save/load/clear/merge`,
    `hou.hscript`, `SceneViewer.flipbook`. Worker-thread calls to these are already thread-safe
    **and deadlock-proof** (SideFX's gate 1 short-circuits inline on main) — SYNAPSE may be
    double-marshalling. **But `hou.Node.cook` and `hou.ui.setStatusMessage` are ABSENT from that
    list** (grep: 0 hits) — the two obvious "make Houdini do the expensive thing" entry points
    have **opposite** safety postures.
24. **`hdefereval` result delivery is not per-caller.** `_last_result` / `_last_exc_info`
    (`:18-19`) are **module-level globals**. With 2+ concurrent blocking callers, a later
    event-loop tick can overwrite `_last_result` before an already-notified caller re-acquires
    and reads it (`:94-95`) — **silently delivering thread B's result to thread A, with fidelity
    1.0 and no anchor violation.** SYNAPSE is exactly that shape (WS + panel + workers). Narrow
    race, but it is a lossless-guarantee hole, not just a hang.

---

## 7. Open unknowns — settleable only in a live GUI session

Stated as specific questions with the exact probe that answers each.

1. **What thread does hwebserver dispatch `@hwebserver.urlHandler` callbacks on?**
   Everything is *consistent* with a C++ pool thread — `max_num_threads=4`
   (`hwebserver_adapter.py:334`), the docstring at `mcp/server.py:416-417`, and the fact that
   `handlers.py:396` branches on main-vs-not at all — but **no runtime assertion was read.**
   *Probe:* log `threading.current_thread().name` and
   `threading.current_thread() is threading.main_thread()` at the top of `_mcp_url_handler`
   during one live tool call.

2. **Same question for `@hwebserver.apiFunction`** (decides whether `api_adapter.py:103` is a
   third CONFIRMED_DEADLOCK or merely correct-but-untimed). *Probe:* the same two-line log inside
   one `apiFunction` body, compared against `synapse.server.main_thread._MAIN_THREAD_ID`.

3. **Same question for `SynapseWS.receive`** (`hwebserver_adapter.py:93`) — confirms the WS path
   is genuinely off-main as mapped.

4. **Does `executeInMainThreadWithResult` short-circuit when called FROM main?** Source says no
   (`hdefereval.py:92-93`, no thread test) and the algorithm was replayed against a faithful stub
   past a 4s watchdog — but **that replay was against a stub, not against Houdini's real
   `hou.ui.addEventLoopCallback`.** *Probe:* from the Python Shell on MAIN, call it with a lambda
   that sets a flag; see whether it returns or hangs. **One line settles the single most
   load-bearing fact in this document.** (Expected: hangs. If it *returns*, candidates A and B1
   collapse and C/D rise.)

5. **Is `hou.RopNode.render` interruptible by `hou.InterruptableOperation(timeout_ms=…)`?**
   i.e. does it internally pump progress? *Probe:* wrap a long render, set `timeout_ms=60000`,
   see whether `hou.OperationInterrupted` ever fires.

6. **Does `QApplication.activeModalWidget()` work under Houdini 22's PySide6 6.8.3?** Confirmed
   present in the shipped stubs (`PySide6/QtWidgets.pyi:584`, `:586`) but **PySide6 could not be
   imported outside Houdini** (Qt DLL load failure under system Python). It is the only available
   proxy for "MAIN is in a nested modal loop" — HOM exposes **no** such API (the complete `hou.ui`
   surface, `hou.py:102053-105823`, has no `isModal`/`inModalLoop`/`nestedEventLoop`; the only
   modal-named symbols are the private, per-pane `NetworkEditor._startModalUI`/`_endModalUI`).
   *Probe:* call it from the Houdini Python Shell with a modal open.

7. **How often does panel PATH B actually fire?** The MCP-unreachable fallback is swallowed at
   `claude_worker.py:279-280` and `tool_executor.py:491-492` with no counter and no log.
   *Probe:* add a counter at the swallow sites and read it after a normal session. This decides
   whether Candidate A is the everyday bug or a rare one.

8. **Does any file outside this repository construct `SynapseDaemon`?** Inside the repo the answer
   is definitive: **zero** production instantiations. But an artist's `456.py`, a package JSON, a
   shelf tool, or an HDA callback could. That would promote `turn_handle.py:161` from latent to
   live. *Probe:* search `$HOUDINI_USER_PREF_DIR` (`scripts/`, `toolbar/`, `packages/`) and any
   installed synapse package JSON for `SynapseDaemon`, `submit_turn`, or `synapse.host`.

9. **Is the `_gate = None` defusal (Candidate D) intact at freeze time?** It is an assignment on a
   **process-wide singleton** applied only on the first `get_bridge()` call
   (`bridge_adapter.py:212 if _bridge is None`). Any later consumer that re-attaches a `_gate`
   re-arms a 300s main-thread sleep. *Probe:* read
   `synapse.shared.bridge.get_process_bridge()._gate` from the Python Shell during a live session.

10. **Does the `hdefereval` `_last_result` cross-thread race (erratum 24) actually fire in
    practice?** It requires 2+ simultaneous *blocking* marshals. *Probe:* two concurrent
    `/mcp` read-only calls (which use the raw blocking primitive at `mcp/server.py:438`) with
    distinguishable return payloads; check for a swap.

---

## 8. The fix shape, stated once

Not a plan — the structural conclusion this map forces.

1. **Route the nine raw `executeInMainThreadWithResult` sites through `run_on_main`**, or at
   minimum replicate its fast-path-2 thread test. The precedent is already in-repo and proven:
   `handlers_tops/_common.py:76-80`, one edit covering 28 call sites.
2. **Fix rows 2, 3, 4, and 10 in the same pass.** Rows 4 and 15 are masked *only* because row 2
   deadlocks first; fixing row 2 alone unmasks them. Row 10 (`:1806`, `:1937`, `:1322`) bypasses
   `_handle_render_bounded` entirely — the `:396` guard is the only thread check in the whole
   file, and those three never reach it.
3. **Convert silent-degrade into fail-fast.** Both existing guards downgrade to inline main-thread
   execution, which is the freezing path. There is currently no invariant stating that a
   main-thread caller reaching an unbounded wait is a bug.
4. **Add `thread_stacks` to `collect_telemetry()` and hook `_record_timeout` to the dump.**
   Without stack content a freeze dump can never distinguish the candidates in §4 — which is
   exactly why this document had to be written from source instead of from telemetry.
