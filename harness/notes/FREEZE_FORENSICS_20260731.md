# FREEZE FORENSICS — 2026-07-31

**Diagnosis only. No code changes.**
Master: `8dfa23d`. All file:line citations verified against this HEAD.
Telemetry pack: `freeze_dump_20260731_164134.json` (heartbeat gap 30.04s / max_latency 25.8s; dispatch_waits max 24927ms across 3262 samples; 14 consecutive main-thread timeout warnings 12:41:17–47; `main_thread_direct count=0` post-fix).

---

## 1. SYMPTOM SHAPE DISCRIMINATOR

Three live shapes, distinguished by one observation each.

| Shape | Mechanism | Distinguishing observation | One-line watch protocol |
|---|---|---|---|
| **A — Qt-grab** | A payload is executing *on* the Houdini main thread; the Qt event loop cannot beat. | **Heartbeat gap >5s** in the freeze dump — the 1s FreezeChain Qt timer itself stalls. Panel Qt timer dead = main thread *occupied*, not starved. | `tail -f ~/.synapse/logs/synapse.log` for `[synapse.server.freeze_chain]` lines; a heartbeat gap >5s during the send = Qt-grab. |
| **B — Marshal starvation** | Main thread is *free* (UI responsive) but command dispatch queue-waits pile up; GUI feels laggy, not frozen. | **dispatch_waits histogram grows** while heartbeat keeps beating. | Query `get_metrics` dispatch_waits histogram before/after the turn; janky UI + beating heart + growing dispatch_waits = starvation, not grab. |
| **C — Escalation wedge** | freeze_chain trips the circuit-breaker path and wedges subsequent traffic. | **A read-only WS command fails after** a freeze — breaker open / escalation wedged. | After a freeze, send one read-only WS command; success = non-causal (h4 already refuted), failure = class-4 wedge live. |

Today's evidence is unambiguously **Shape A**: heartbeat gap 30.04s / max_latency 25.8s with the panel Qt timer dead, `main_thread_direct count=0` (Fast path 2 never fired post-fix), and the 12:41:07 freeze falling inside an 11-turn / 10-tool-call conversation completing at 12:45:13. The main thread was *inside a payload*, not deadlocked and not starved.

---

## 2. RANKED ROOT CAUSES

### Standing

**h7 — handler-heavy-tool (CONFIRMED; survived three crucible kill attempts).**
Mid-turn tool payloads hold the Houdini main thread uninterruptibly. The v5.40.1 fix (class 3, d15d9b2) bounded the *caller wait*, never the running payload.

Mechanism, file:line:

- `python/synapse/panel/claude_worker.py:348-374` — tools dispatch on a daemon thread (off-main); `:377-378` `request.done.wait(budget)` bounds only the worker's wait. The error text itself admits the tool "may STILL be running inside Houdini."
- `python/synapse/server/main_thread.py:285` — "A payload already inside fn() when the timeout fires is the accepted residual race." `:290-307` — `_on_main` runs `fn()` with no internal timer; deferred `:311` bounds queue-wait only. Nested `run_on_main` legs collapse inline via Fast path 1 (`:230-231`).
- `python/synapse/server/handlers_render.py:109-113` — verbatim: the panel-inline payload runs with NO bound of any kind; "nothing in Python can interrupt the main thread from the main thread." Production frames legitimately run minutes-to-hours, so the payload cannot be blanket-capped.
- Gripping tools reachable on the chat path: `node.render`; `cook(force=True)` at `handlers_node.py:79`, `handlers_material.py:90`, `:246`, `:508`, `handlers_usd.py` (13 sites), `handlers_cops.py:929`, `:1987`, `:2127`, `handlers_render.py:2014`; ungated `execute_python` at `handlers.py:1987`; `capture_viewport` flipbook; all-nodes traversal in `live_metrics.py:227`.

Telemetry attribution: heartbeat max_latency 25.8s proves *occupation* (Qt timer itself dead) not starvation; 12:41:17–47 shows 14 consecutive main-thread timeout warnings stacked on one payload; the 12:51:49 conversation (6-turn / 5-tool) is sandwiched by freeze-chain recoveries of 24.3 / 23.2 / 23.1s.

Attack survival: three kill attempts failed — (a) no direct `execute_tool` bypass exists on the worker path; (b) the 0-tool-call adjacency dissolved under timeline correlation (every freeze sits inside a multi-tool conversation); (c) heartbeat max_latency rules out marshal starvation.

**Follow-on defect (not h7 itself):** the `tool_executor` log string "Inline tool ... ran Xms on the main thread (Qt loop stalled this long)" is stale post-fix — on the off-main path it measures daemon `_dispatch` wall-time and will misattribute future freezes. This corrupted forensics this run and will corrupt the next one.

### OPEN (hazard tickets — closing probe named)

- **h8 — off-main hou disconnect.** Real hazard: `python/synapse/server/websocket.py:605-606` calls `hou.hipFile.path()` / `hou.getenv` in the disconnect `finally`, off-main. Refuted as today's cause (exactly ONE connection logged all day; stable-connection freezes refute). Stands as a hazard ticket. Closing probe: wrap in `run_on_main` or pre-cache the paths at connect time on main.
- **h9 — armed inline slot.** `python/synapse/panel/synapse_panel.py:1937-1938` wires `worker.tool_requested → tool_executor.execute_tool`. Live wiring, ZERO production emitters of `tool_requested` — ARMED-WIRE-INERT. One `.emit` re-arms class 3. Closing probe: regression test asserting no production emitter, or disconnect the wire.
- **h10 — pre-auth recv.** `python/synapse/server/websocket.py:480` is an unbounded `websocket.recv()`, but it holds no locks and touches no marshal state before `:748`; dead code locally (auth_required=False; 0 auth lines vs 53 connects). Closing probe: bound with timeout + cancel check; relevant only to studio mode.

### REFUTED (each listed once, with the killing line)

- **h2 — context-gather-inline.** Mechanism real at `python/synapse/panel/synapse_panel.py:1888-1902` but the accessors are trivially bounded; telemetry attributes every stall to tool payloads, never to prompt-build. Killed by per-turn attribution.
- **h4 — freeze-chain-misfire.** The breaker has NEVER opened in production — hwebserver transport has no resilience layer: `python/synapse/server/freeze_chain.py:154-158` logs "No live SynapseServer breaker to open" at every escalation; `circuit_trip_count` = 0 during a live escalation. Escalation is effect, not cause.
- **h6-p31 — ping gate.** Commit `340db86` touches only `.claude/hooks/synapse_hooks_bridge.py` (a subprocess); the ping verdict is printed to stdout, persisted nowhere, zero consumers. Per-tool-call availability is `hou.webServer.port()` at `python/synapse/panel/tool_executor.py:154-159`, not SessionStart.
- **h6-p33 — recv loop.** P3.3 verified clean: `iter_messages` at `websocket.py:103-124` has no mis-consume; `cancel_event` is fresh per connection (`:438`) and popped at `:569-570`; the serial pump starves only the *next* message, never the GUI.

---

## 3. TAXONOMY RECONCILIATION

| Standing cause | Known class | Class status | Closure-check evidence |
|---|---|---|---|
| h7 (payload on main) | **Class 1 — render grip** | MITIGATED-only | The bounded wait never bounded the payload: `handlers_render.py:109-113` (panel Qt slot IS the main thread → Fast path 2 → no bound possible). Class 1 was scoped to render tools; h7 generalizes it to every cook/`execute_python` payload — but shares the mechanism, not a new one. **Not class 5.** |
| (none standing) | **Class 2 — marshal self-deadlock** | CLOSED at v5.33.0 | `main_thread_direct count=0` in today's dump — Fast path 2 migrated inline runs, deadlocks gone. Not implicated today. |
| (none standing) | **Class 3 — chat-time Qt fallback** | CLOSED at d15d9b2 / v5.40.1 | `claude_worker.py:348-374` daemon-thread dispatch + context-gather off-main; telemetry shows zero Fast-path-2 fires. h9 is the one-armed-wire residual of this class (hazard ticket, §2 OPEN). |
| (h4 refuted) | **Class 4 / D3 — freeze_chain escalation** | MITIGATED-only | Cannot un-wedge a parked main thread; hwebserver has NO breaker (`freeze_chain.py:154-158`). Not causal today; escalation recoveries are downstream of h7 payloads. |

Verdict: no class 5 declared. Today's freeze is the **known MITIGATED-only residual of class 1, generalized** — the wait was bounded, the payload never was.

---

## 4. TODAY'S REGRESSION CHECK

**Verdict: `9c9bc8e` (P3.3) and `340db86` (P3.1) are both REFUTED as causes of today's freezes.**

- **P3.3 (`9c9bc8e`)** — websocket recv loop verified clean (§2, h6-p33): fresh `cancel_event` per connection, no mis-consume; the serial pump starves at most the next message. Nothing in it holds the GUI.
- **P3.1 (`340db86`)** — the SessionStart ping gate is a hook-side subprocess; its verdict goes to stdout and is persisted nowhere; it cannot set Houdini-side state. Tool availability is re-probed per call via `hou.webServer.port()` (`tool_executor.py:154-159`).
- **Bisect evidence:** none needed. Today's freeze telemetry (heartbeat gap, timeout-warning stacks, conversation correlation) matches the known class-1 / h7 shape — long main-thread payload — not a new mechanism. The 08:44 and 12:41 freezes pre-date/parallel the push pattern and reproduce the pre-P3 signature exactly. **The symptom is not new since today; it is the known residual of bounding the wait, not the payload.**

---

## 5. REMEDIATION TICKET (ranked by leverage — ticket only, no code changes)

1. **[PRIMARY] Cap the mid-turn main-thread payload footprint on the chat path.**
   Owner: `python/synapse/panel/claude_worker.py` + `python/synapse/server/handlers*.py`.
   Direction: (a) chunk or timebox the cook-heavy handlers (`cook(force=True)` sites: `handlers_node.py:79`, `handlers_material.py:90/:246/:508`, `handlers_usd.py` (13 sites), `handlers_cops.py:929/:1987/:2127`) so a single payload cannot hold main >N seconds; (b) for `execute_python` on the off-main path, split into staged sub-payloads or require explicit consent for payloads expected >5s (the pre-flight advisory at `tool_executor.py:477` exists but is advisory-only); (c) worst offender is renders — confirm `_handle_render_bounded` (`handlers_render.py`) actually routes all 6 render tools and the panel path cannot bypass it.
   Pin: dispatch a handler that holds main >10s via the worker off-main path; assert the GUI heartbeat keeps beating (freeze stats show no heartbeat gap).
2. **[SECONDARY] Fix the stale 'Inline tool … on the main thread' attribution string** so daemon-path wall-time is not recorded as main-thread time — future forensics depend on it.
   Owner: `python/synapse/panel/tool_executor.py` (`:57-96`, `:472-479`).
   Pin: unit test asserting the record label discriminates Fast-path-2 inline from daemon-path dispatch.
3. **[HAZARD — do not skip] Disarm the armed-but-inert class-3 wire:** `worker.tool_requested → tool_executor.execute_tool` (`python/synapse/panel/synapse_panel.py:1937-1938`).
   Owner: `synapse_panel.py`.
   Pin: regression test asserting no production emitter of `tool_requested`; or disconnect the wire.
4. **[HAZARD] Wrap the disconnect-`finally` hou calls** (`python/synapse/server/websocket.py:605-606`) in `run_on_main`, or pre-cache hip/job path at connect time on main.
   Owner: `python/synapse/server/websocket.py`.
   Pin: marshal lint extension.
5. **[HAZARD — studio mode only] Bound the pre-auth recv** (`python/synapse/server/websocket.py:480`) with a timeout + cancel check.
   Owner: `websocket.py`.

---

## 6. LIVE REPRO PROTOCOL

Joe sends one prompt on the real scene while the telemetry surfaces are watched. Correlate with "Conversation complete: N turns, M tool calls" log lines to attribute per turn.

1. **Protocol A — Qt-grab.** `tail -f ~/.synapse/logs/synapse.log` watching for `[synapse.server.freeze_chain]` lines. A heartbeat gap >5s during the send = main occupied = Shape A (today's shape). No gap = shape is not grab.
2. **Protocol B — marshal starvation.** Snapshot the `get_metrics` dispatch_waits histogram before and after the turn. GUI janky *while heartbeat keeps beating* and dispatch_waits grow = Shape B. Post-v5.33.0 this is expected to stay empty on the panel path.
3. **Protocol C — escalation wedge.** Immediately after a freeze, send one read-only WS command. Success = breaker/escalation non-causal (already refuted today — `freeze_chain.py:154-158`, `circuit_trip_count` 0). Failure = class-4 wedge live and h4 must be re-opened.

Expected outcome given today's evidence: A fires (heartbeat gap), B stays flat, C succeeds — triple-confirming h7 / Shape A as the sole standing cause.
