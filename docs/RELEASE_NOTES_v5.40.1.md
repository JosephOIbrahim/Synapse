# v5.40.1 — the chat no longer grips the UI

*A third inline-main-thread freeze class, closed on the panel/agent-loop path. You are mid-chat with Synapse, no render running, and Houdini's UI grips — you cannot select nodes until the tool call finishes. Distinct from the in-process render freeze (v5.33.0's bounded mitigation) and the hdefereval self-deadlock (v5.33.0's deletion). Two commits, one fix: stop reaching `hou.*` from the main thread when the bridge is down.*

---

## The grip, and where it came from

`ClaudeWorker` runs on a background QThread, not the main thread. Each tool call tries the local MCP endpoint first. When ws://localhost:9999 is **up**, the call rides the hwebserver `/mcp` thread and marshals onto the main thread cleanly — the deferred path, with a timeout, interleaved with UI events.

When the bridge is **down**, that try returns `None` and the worker used to fall back to `self.tool_requested.emit(request)` — a Qt signal, AutoConnection. The slot `ToolExecutor.execute_tool` then ran **on the main thread**, `handler.handle` ran inline, and every internal `run_on_main` hit `main_thread.py:240` Fast path 2: "caller IS main thread → `fn()` inline, NO timeout possible." The GUI stalled for the handler's full duration. Node selection, the viewport, and the 1s FreezeChain heartbeat all froze.

The panel's own 10s context-gather poll had the same shape — a Qt slot calling the gather inline on the main thread.

## The lying "connected" signal

This was not a broken-bridge-only failure. SessionStart reports the bridge "connected" even when it is unreachable (the 2026-07-27 latency report, F6). So a bridge that is actually down silently routed every tool call through the freezing fallback in ordinary sessions. "Connected" is not reachable — always ping first.

This release does **not** fix that signal. It routes around it: the freeze cannot fire regardless of whether the signal lies.

## The fix

**`6f354ae` — tool dispatch off the main thread.** `claude_worker.py` replaces the `tool_requested.emit(request)` fallback with a daemon `threading.Thread(name="synapse.panel.tool.<tool>")` targeting a new `executor.execute_tool_off_main(request)`. Because the daemon is off the main thread, `run_on_main` inside the handler takes the deferred path (`hdefereval.executeDeferred` + per-tool timeout, interleaved with UI events) — identical to the bridge-up path. The worker's `request.done.wait(budget)` and the C7 "did not finish, do not retry" contract are unchanged.

**`bf74ed7` — context-gather off the main thread (same class).** New module-scope `ws_bridge.gather_context_off_main` spawns a daemon thread → `run_on_main(_gather_context_on_main_thread, timeout=2.0, record_stall=False, record_wait=False)`. The `record_stall=False` / `record_wait=False` keep this advisory read out of the stall detector and the dispatch-wait histogram — observe-only posture. `_gather_context_if_stale` no longer gathers inline: it returns the cache and fire-and-forgets a refresh on stale. The LLM treats context as advisory, so a stale cache is honest.

## Numbers, with producers

| Figure | Producer |
|---|---|
| 5,330 passed · 0 failed · 137 skipped | local Windows `python -m pytest tests/ -q` (CI red on `mcp` drift, not this fix) |
| +14 net vs v5.40.0 (5,316) | `6c72572` (v5.40.0 baseline) → `bf74ed7` (final) |
| 8 tests pinning off-main tool dispatch | `tests/test_offmain_fallback.py` (`6f354ae`) |
| 6 tests pinning off-main context-gather | `tests/test_context_poll_offmain.py` (`bf74ed7`) |
| 4 contract updates (net 0) | `tests/test_chat_panel.py::TestStaleContextGather` (`bf74ed7`) |
| PR #50, merge `d15d9b2` | both commits preserved, no squash |

Not live-measured. The bridge was down at diagnosis — which is exactly the state the fix targets — so the live test is: restart the panel with the bridge down, chat through a tool call, and try selecting nodes. They stay selectable.

## Known limitations — what this release does not claim

- **Not live-measured.** The fix targets the bridge-down state that was live at diagnosis; the on-screen proof is Joe's, not a harness stamp.
- **The lying "connected" signal (F6) is still live.** This release routes around it; it does not make SessionStart truthful. The cheap cure — SessionStart pings before reporting "connected" (latency report §5 #5) — remains open.
- **The residual in-process render freeze is a separate class.** Out-of-process husk/hython is the cure and is Indie-blocked. This release does not touch it.
- **The websocket read loop's cancel gap is still open.** `websocket.py:471` serial `for message in websocket:` makes cancel unreachable mid-frame.
- **The 7-27 latency report's §1 verdict is now partly stale.** "Houdini-side is milliseconds" holds for the bridge-up path; in the bridge-down case this closed, the whole handler ran inline on the GUI thread (seconds-class). An addendum is owed; the report is not edited here without a gate.
- **CI is red on the runners, not from this fix.** The `mcp` library on the CI runners dropped `server.list_tools()` (collection error at `mcp_server.py:899`), pre-existing since 2026-07-29. Local Windows suite is green because the local `mcp` still has it. Fix is a separate follow-up: pin `mcp`, or update `mcp_server.py:899` to the new decorator API.