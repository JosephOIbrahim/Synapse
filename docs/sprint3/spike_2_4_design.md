# Spike 2.4 — Daemon ↔ Main-Thread Deadlock Fix (Design)

> **Authority:** ARCHITECT (design only). FORGE writes implementation;
> CRUCIBLE writes tests. This document is the contract between them.
>
> **Status:** Pre-implementation. No code mutated. Hostile Crucible
> turn from 4/20 still failing pending the fix this design specifies.
>
> **Sprint position:** Spike 2.4 is BLOCKING — Spike 3 (TopsEventBridge)
> does not open until §6 Gate Criteria are green.

---

## 1. Diagnosis

### 1.1 The deadlock topology, in code

The deadlock lives at the intersection of three real files:

| File | Function | Line(s) | Role in the deadlock |
|---|---|---|---|
| `python/synapse/host/daemon.py` | `SynapseDaemon.submit_turn` | 425–489 | Caller-thread (main thread in GUI Houdini) blocks on `result_queue.get(timeout=wait_timeout)` at L485 |
| `python/synapse/host/daemon.py` | `SynapseDaemon._process_request` | 532–562 | Daemon thread runs `run_turn(...)` synchronously at L544–550 |
| `python/synapse/cognitive/agent_loop.py` | `run_turn` | 173–301 | Daemon thread inside `run_turn` calls `dispatcher.execute(...)` at L282 |
| `python/synapse/cognitive/dispatcher.py` | `Dispatcher.execute` → `_execute_via_main_thread` | 212–291 | Daemon thread calls injected `main_thread_executor(fn, kwargs)` at L291 |
| `python/synapse/host/main_thread_executor.py` | `_exec_gui` | 126–178 | Daemon thread calls `hdefereval.executeInMainThreadWithResult(...)` (via worker thread) at L153, blocks on `done.wait(timeout=effective_timeout)` at L169 |

The deadlock is a classic two-party reverse-wait. Drawn end-to-end:

```
                                    (T0)  Main thread
                                          d.submit_turn(prompt, wait_timeout=60)
                                          → put on _request_queue   [daemon.py:482]
                                          → result_queue.get(60)    [daemon.py:485]
                                          ════════════════════════════ BLOCKED — main thread parked

                                    (T1)  Daemon thread picks up request
                                          _process_request(req)    [daemon.py:524]
                                          → run_turn(...)           [daemon.py:544]
                                          → dispatcher.execute('synapse_inspect_stage', ...)
                                                                    [agent_loop.py:282]
                                          → _execute_via_main_thread(fn, kwargs)
                                                                    [dispatcher.py:244, 291]
                                          → main_thread_exec(fn, kwargs)
                                                                    [main_thread_executor.py:197]
                                          → _exec_gui(fn, kwargs, 30)
                                                                    [main_thread_executor.py:126]
                                          → spawn worker → hdefereval.executeInMainThreadWithResult(λ)
                                                                    [main_thread_executor.py:153]
                                          → done.wait(timeout=30)   [main_thread_executor.py:169]
                                          ════════════════════════════ BLOCKED — daemon thread parked,
                                                                       worker is now blocked too:
                                                                       hdefereval queues the lambda
                                                                       onto Houdini's main-thread
                                                                       Qt event pump.

                                          (T2)  Houdini's main thread is supposed to drain
                                                that queue on its next event-pump tick.
                                                But the main thread is at (T0) — sitting
                                                in result_queue.get(60). It is not pumping
                                                Qt events. The lambda never executes.
                                          ════════════════════════════ DEADLOCK.

                                          30s later: done.wait fires its timeout →
                                                MainThreadTimeoutError [main_thread_executor.py:170]
                                                → propagates as AgentToolError back into the
                                                conversation [dispatcher.py:240–251].
                                                Same outcome on the next tool call.
                                                Same outcome on every tool call.
```

The exact symptom the 4/21 capsule recorded — **"30s MainThreadTimeoutError per tool call"** — is the `_exec_gui.done.wait(timeout=30)` at `main_thread_executor.py:169` hitting its budget after the lambda failed to run on Houdini's main thread.

The two function pairs that name the deadlock:

> **`SynapseDaemon.submit_turn` ↔ `_exec_gui` via `hdefereval.executeInMainThreadWithResult`.**
> One waits on a queue the other can't fill; the other waits on a thread the first one is supposed to be running.

### 1.2 Why Spike 2.3 unmasked rather than caused this

Spike 2.3 (`43ee77f`) added two surface fixes:

1. `_boot_inspector_transport()` — wired the Inspector's global transport to `synapse.host.transport.execute_python` at daemon boot, so `inspect_stage`'s internal call into the Inspector layer no longer raised `TransportNotConfiguredError` on first dispatch.
2. Honest `hou.secure` audit logging — orthogonal; not implicated.

Pre-2.3, the **first tool call inside `run_turn`** raised `TransportNotConfiguredError` *inside* the Inspector layer. That exception bubbled up to `Dispatcher.execute`'s `try/except` (dispatcher.py:240–251) and was wrapped as an `AgentToolError`. The `AgentToolError` returned via the in-process call chain — **never crossed the daemon-thread → main-thread boundary** — so `_exec_gui` never got a chance to attempt `hdefereval.executeInMainThreadWithResult`. The deadlock latent in that boundary was never exercised because the tool call short-circuited before reaching it.

Spike 2.3 fixed `TransportNotConfiguredError`. The Inspector now runs to completion. Inside its run-to-completion, it calls `synapse.host.transport.execute_python`, which calls `synapse.host.main_thread_exec`, which is `_exec_gui` in graphical Houdini. **That's the path that crosses the daemon ↔ main-thread boundary.** Once 2.3 made the path live, the deadlock that had always been latent in the architecture surfaced on every tool call.

The revert message at `cce7b34` calls this exactly right: *"Spike 2.3 wired Inspector transport at daemon boot, which fixed the `TransportNotConfiguredError` on first tool call. **This unmasked a deeper architectural deadlock**."*

### 1.3 What the architecture committed to that produced this

Two commitments from Sprint 3 Day 0 are jointly responsible:

- **`SynapseDaemon.submit_turn` is synchronous** (daemon.py:425–489). The caller blocks on the reply queue until the agent loop returns. In production GUI Houdini this caller is the panel/shelf invocation thread — which **is** the main thread.
- **`_exec_gui` requires the main thread to be pumping Qt events** to run the dispatched lambda (main_thread_executor.py:126–178). `hdefereval.executeInMainThreadWithResult` enqueues a callable onto Houdini's main-thread event queue and waits; the callable runs the next time the main thread services that queue. A main thread blocked on a `queue.Queue.get(timeout=...)` is not servicing the queue.

The two commitments are individually defensible but jointly toxic: the synchronous caller-side block holds the only thread that can drain the work the daemon-side dispatcher needs drained.

`_exec_headless` (main_thread_executor.py:181–194) does not deadlock because there's only one Python thread and `boot_gate=False` forces direct-call execution. The deadlock is **gui-specific**, which is why the Sprint 2 test suite stays green (all tests use `is_testing=True` or `_exec_headless`) and only the Crucible-against-graphical-Houdini run reproduces it.

---

## 2. Option chosen — A (Non-blocking submit_turn returning a Future)

The diagnosis localizes the deadlock to a single load-bearing assumption: **the main-thread caller of `submit_turn` cannot block on a queue, because that's the same thread `hdefereval` needs free**. Option A breaks that assumption directly and surgically. The daemon thread keeps owning the agent loop. The main thread keeps owning the Qt event pump. The caller's "I want my result" wait moves off the main thread entirely — back to the caller's chosen waiting strategy (poll, callback on completion, or explicit `result()` from a non-main thread).

Option B (Qt-pumping wait) requires processing Qt events from the main thread while it's parked, which means re-entering arbitrary Qt callbacks during what looks to the rest of Houdini like a single tool dispatch. That's a class of bug that does not show up in unit tests and shows up in artist sessions as "viewport double-clicked, agent did the wrong thing." Reject.

Option C (agent-loop off-daemon) reorganizes the threading topology — daemon owns transport, separate thread owns the agent loop. Defensible long-term, but it touches daemon boot, lifecycle, error propagation, the cancel-event plumbing, and the test surface. The diagnosis does not require it; Option A closes the deadlock with strictly less change. Reserve C for if Option A surfaces a follow-on issue we can't resolve inside the Future contract.

Option A is the smallest change that closes the deadlock without foreclosing B or C. It also aligns naturally with how Anthropic's SDK is structured (async/await over `client.messages.create`) — the Future-returning shape is what we'd want to grow toward anyway when Spike 3+ starts pushing perception events asynchronously.

---

## 3. Files to touch

### Modify

| File | Functions / methods that change | Nature of change |
|---|---|---|
| `python/synapse/host/daemon.py` | `SynapseDaemon.submit_turn` (L425–489) | Returns a `TurnHandle` instead of `AgentTurnResult`. No longer blocks on `result_queue.get`. |
| `python/synapse/host/daemon.py` | `SynapseDaemon._process_request` (L532–562) | Posts result via `TurnHandle._set_result(...)` instead of `request.result_queue.put_nowait`. Posts exceptions via `TurnHandle._set_exception(...)`. |
| `python/synapse/host/daemon.py` | `_AgentRequest` dataclass (L89–99) | Replace `result_queue` field with `handle: TurnHandle`. |
| `python/synapse/host/daemon.py` | `SynapseDaemon._drain_request_queue` (L413–421) | When dropping a stale request, mark its handle cancelled so any caller still holding it sees `TurnCancelled` instead of hanging forever. |
| `python/synapse/host/daemon.py` | Add `submit_turn_blocking` convenience (new method) | Thin wrapper around `submit_turn` + `handle.result(timeout=…)`. Documented as **never call from the Houdini main thread in GUI mode** — this is the legacy synchronous shape, retained for tests and headless callers only. |
| `python/synapse/host/__init__.py` | `__all__` and imports | Re-export `TurnHandle`, `TurnCancelled`, `TurnNotComplete`. |

### Create

| File | Purpose |
|---|---|
| `python/synapse/host/turn_handle.py` | Defines `TurnHandle`, `TurnCancelled`, `TurnNotComplete`. The Future-shaped return value of `submit_turn`. Pure stdlib (`threading.Event`, no asyncio dependency — caller decides their wait strategy). Lives in `synapse.host.*` because the lifecycle is daemon-bound. |

### Delete

None. The old `result_queue: queue.Queue` field on `_AgentRequest` is replaced, not deleted alongside it. Strangler Fig: WebSocket adapter path is not touched at all.

### Out of scope

- `synapse.cognitive.agent_loop.run_turn` — unchanged. Still synchronous from the daemon thread's perspective. The agent loop continues to call `dispatcher.execute` synchronously; what changes is who's waiting for the loop's *outermost* result.
- `synapse.cognitive.dispatcher.Dispatcher` — unchanged. Tool calls still route through it. `AgentToolError` envelope unchanged.
- `synapse.host.main_thread_executor` — unchanged. `_exec_gui` and `_exec_headless` paths unchanged. Tool calls still marshal through `hdefereval.executeInMainThreadWithResult` in GUI mode.
- `synapse.host.transport` — unchanged.
- `synapse.host.auth` — unchanged (see §8).
- WebSocket adapter (`mcp_server.py`) — unchanged. Strangler Fig invariant preserved.

---

## 4. Interface signatures

### 4.1 New file: `python/synapse/host/turn_handle.py`

```python
"""TurnHandle — Future-shaped return for SynapseDaemon.submit_turn.

Sprint 3 Spike 2.4: closes the daemon ↔ main-thread deadlock by moving
the caller's wait off the synchronous queue.get() path. The daemon
posts the result onto the handle when the agent loop completes; the
caller chooses their own waiting strategy (poll done(), wait on the
underlying Event, or block in result(timeout=...) from a non-main
thread).
"""

from __future__ import annotations

import threading
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.cognitive.agent_loop import AgentTurnResult


class TurnNotComplete(RuntimeError):
    """Raised by ``TurnHandle.result(timeout=…)`` when the timeout
    elapses without the daemon posting a result. The turn may still be
    running on the daemon thread; the handle remains valid."""


class TurnCancelled(RuntimeError):
    """Raised by ``TurnHandle.result(...)`` when the handle was cancelled
    before the daemon posted a result (e.g. daemon stop drained the
    request queue, or the caller invoked ``handle.cancel()``)."""


class TurnHandle:
    """Future-shaped result envelope for one ``submit_turn`` call.

    Thread-safe: multiple threads can call ``done()`` / ``result()`` /
    ``cancel()`` concurrently. The daemon thread is the sole writer
    (via the private ``_set_result`` / ``_set_exception`` methods);
    callers are readers.

    Lifecycle:
        pending    — created by submit_turn, daemon hasn't touched yet
        complete   — _set_result called, .result() returns the value
        failed     — _set_exception called, .result() re-raises the exc
        cancelled  — .cancel() called or daemon drained the request
    """

    def __init__(self) -> None: ...

    def done(self) -> bool:
        """True if the turn has completed, failed, or been cancelled."""

    def cancelled(self) -> bool:
        """True if the handle was cancelled before completion."""

    def result(
        self,
        timeout: Optional[float] = None,
    ) -> "AgentTurnResult":
        """Block until the turn completes or ``timeout`` elapses.

        ``timeout=None`` waits indefinitely. **Never call with timeout=None
        from the Houdini main thread in GUI mode** — that re-introduces
        the Spike 2.4 deadlock. Use ``done()`` polling or daemon-side
        completion callback instead.

        Raises:
            TurnNotComplete: timeout elapsed.
            TurnCancelled: handle was cancelled before completion.
            BaseException: whatever the daemon thread captured via
                ``_set_exception`` (rare; the agent loop already wraps
                most failures into AgentTurnResult.status).
        """

    def cancel(self) -> bool:
        """Cancel the handle. Returns True if cancellation took effect,
        False if the turn already completed. Does NOT cancel the agent
        loop itself — for that, call ``daemon.cancel()``. This only
        affects waiters on the handle."""

    @property
    def event(self) -> threading.Event:
        """The underlying completion Event. Exposed for callers that
        want to wait on multiple handles via something like
        ``threading.Event`` composition (or asyncio bridging in
        Spike 3+ when perception events arrive)."""

    # -- Daemon-side (private) -----------------------------------------

    def _set_result(self, result: "AgentTurnResult") -> None:
        """Daemon posts the agent-turn result. Idempotent on second
        call (logged + dropped). Public on the type but underscore-
        prefixed: callers must not invoke."""

    def _set_exception(self, exc: BaseException) -> None:
        """Daemon posts an unexpected exception that escaped run_turn
        (rare — the agent loop catches API errors itself). Same
        idempotency rules as ``_set_result``."""
```

### 4.2 Changed: `synapse.host.daemon._AgentRequest`

**Old (daemon.py:89–99):**

```python
@dataclass
class _AgentRequest:
    user_prompt: str
    config: AgentTurnConfig
    result_queue: "queue.Queue[AgentTurnResult]"
    submitted_at: float = field(default_factory=lambda: 0.0)
```

**New:**

```python
@dataclass
class _AgentRequest:
    user_prompt: str
    config: AgentTurnConfig
    handle: "TurnHandle"
    submitted_at: float = field(default_factory=lambda: 0.0)
```

### 4.3 Changed: `SynapseDaemon.submit_turn`

**Old (daemon.py:425–489):**

```python
def submit_turn(
    self,
    user_prompt: str,
    *,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    max_iterations: Optional[int] = None,
    wait_timeout: Optional[float] = None,
) -> AgentTurnResult:
    """... blocks on result_queue.get(timeout=wait_timeout) ..."""
```

**New:**

```python
def submit_turn(
    self,
    user_prompt: str,
    *,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    max_iterations: Optional[int] = None,
) -> TurnHandle:
    """Submit a prompt to the agent loop and return a TurnHandle
    immediately. Does NOT block. The caller polls handle.done(),
    waits on handle.event, or calls handle.result(timeout=...) from
    a thread that is NOT the Houdini main thread.

    Raises:
        DaemonBootError: daemon is not running.

    The ``wait_timeout`` parameter is removed from this signature —
    it conflated request submission with result waiting and was the
    direct vehicle for the Spike 2.4 deadlock. Callers that want a
    blocking shape use ``submit_turn_blocking`` from a non-main
    thread, or layer their own poll on top of ``handle.done()``.
    """
```

### 4.4 New: `SynapseDaemon.submit_turn_blocking` (convenience)

```python
def submit_turn_blocking(
    self,
    user_prompt: str,
    *,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    max_iterations: Optional[int] = None,
    wait_timeout: Optional[float] = None,
) -> AgentTurnResult:
    """Synchronous shape, retained for tests and headless callers.

    **DO NOT call from the Houdini main thread in GUI mode** — that
    re-introduces the Spike 2.4 deadlock. The method docstring and
    a runtime warning if ``hou.isUIAvailable()`` returns True and
    we appear to be on the main thread guard against accidental
    misuse. (Detection is best-effort — Python can't always tell —
    but the warning steers callers off the cliff.)

    Equivalent to::

        handle = self.submit_turn(...)
        return handle.result(timeout=wait_timeout)

    Raises:
        DaemonBootError: daemon is not running.
        TurnNotComplete: ``wait_timeout`` elapsed without a result.
            (Note: stdlib ``TimeoutError`` was the prior signal —
            we keep the new shape distinct so callers migrate
            cleanly. ``TurnNotComplete`` IS a subclass of
            ``RuntimeError``, not ``TimeoutError``, intentionally.)
    """
```

> **Open question for §7:** should `submit_turn_blocking` raise the existing stdlib `TimeoutError` (preserving the prior `submit_turn` contract for tests that catch `TimeoutError`) or the new `TurnNotComplete`? FORGE picks. CRUCIBLE pins whichever lands.

### 4.5 Changed: `SynapseDaemon._process_request`

**Old (daemon.py:532–562):**

```python
def _process_request(self, request: _AgentRequest) -> None:
    ...
    try:
        request.result_queue.put_nowait(result)
    except queue.Full:
        logger.debug("Dropping turn result — caller queue full")
```

**New:**

```python
def _process_request(self, request: _AgentRequest) -> None:
    """Run one agent turn against the configured client + dispatcher.

    Never lets a turn failure take down the daemon thread. Posts the
    result onto request.handle via _set_result; an unexpected
    exception escaping run_turn posts via _set_exception.

    Idempotency: if the handle is already complete (caller cancelled
    while we were running), _set_result is a no-op log entry. The
    daemon does not raise.
    """
    assert self._dispatcher is not None
    assert self._anthropic_client is not None
    try:
        result = run_turn(
            self._anthropic_client,
            self._dispatcher,
            request.user_prompt,
            cancel_event=self._cancel_event,
            config=request.config,
        )
        request.handle._set_result(result)
    except BaseException as exc:  # noqa: BLE001
        logger.exception("run_turn raised outside its own guard")
        synthesized = AgentTurnResult(
            status=STATUS_API_ERROR,
            error=f"{type(exc).__name__}: {exc}",
        )
        # Set the handle result with the synthesized failure first
        # so callers that polled .result() see the AgentTurnResult
        # shape they expect. _set_exception is reserved for
        # daemon-internal failures that don't fit AgentTurnResult.
        request.handle._set_result(synthesized)
```

### 4.6 Changed: `SynapseDaemon._drain_request_queue`

**Old (daemon.py:413–421):**

```python
def _drain_request_queue(self) -> None:
    try:
        while True:
            self._request_queue.get_nowait()
    except queue.Empty:
        pass
```

**New:**

```python
def _drain_request_queue(self) -> None:
    """Empty the request queue. Each drained request's handle is
    cancelled so any caller still waiting on it raises
    ``TurnCancelled`` instead of hanging forever (the Spike 2.4
    revert path retained the queue.Empty surface, which left
    handles dangling)."""
    try:
        while True:
            stale = self._request_queue.get_nowait()
            stale.handle.cancel()
    except queue.Empty:
        pass
```

### 4.7 Status constants — unchanged

`STATUS_COMPLETE`, `STATUS_CANCELLED`, `STATUS_API_ERROR`, `STATUS_MAX_ITERATIONS`, `STATUS_UNKNOWN_STOP` continue to mean exactly what they meant in `agent_loop.py`. `AgentTurnResult` shape unchanged. `AgentToolError` envelope shape unchanged. The Future contract sits **outside** the agent-loop result type.

---

## 5. Test plan for CRUCIBLE

CRUCIBLE writes the tests; the spec below is the contract. Hostile cases mandatory.

### 5.1 Deadlock regression — the test that was failing on 4/20

| File | Test name | What it asserts |
|---|---|---|
| `tests/test_host_layer.py` | `test_submit_turn_does_not_block_caller_thread` | After `daemon.submit_turn(prompt)`, the calling thread returns immediately (well under 1s) with a `TurnHandle`, even with a mock `main_thread_executor` that simulates `hdefereval` taking 5s. |
| `tests/test_host_layer.py` | `test_main_thread_can_pump_while_daemon_dispatches` | Caller thread is the one that "pumps" (executes the dispatched lambda when the test's mock executor signals). Without 2.4's fix this test deadlocks; with it, the lambda runs and the handle completes. |
| `tests/test_host_layer.py` | `test_crucible_full_turn_with_inspect_stage` | The 4/20 hostile turn that didn't run: full `run_turn` against a mock Anthropic client that emits a `synapse_inspect_stage` `tool_use` block, dispatcher routes through real `synapse.host.transport.execute_python` against an Inspector mock transport, handle completes within 5s with `STATUS_COMPLETE` and `len(tool_errors) == 0`. |

### 5.2 Baseline non-regression

| File | Test name | What it asserts |
|---|---|---|
| `tests/test_host_layer.py` | `test_submit_turn_handle_completes_for_simple_end_turn` | Mock client emits `end_turn` immediately; `handle.result(timeout=2)` returns `AgentTurnResult` with `STATUS_COMPLETE`, `iterations == 1`. Replaces the previous `test_submit_turn_end_to_end`. |
| `tests/test_host_layer.py` | `test_submit_turn_handle_completes_for_max_iterations` | Mock client never emits `end_turn`; handle eventually completes with `STATUS_MAX_ITERATIONS`. |
| `tests/test_host_layer.py` | `test_submit_turn_blocking_convenience_returns_result` | The legacy synchronous shape via `submit_turn_blocking(prompt, wait_timeout=5)` from a non-main thread returns the same `AgentTurnResult` the handle would. |
| `tests/test_host_layer.py` | `test_submit_turn_blocking_timeout_surfaces_distinctly` | A hanging mock client causes `submit_turn_blocking(wait_timeout=0.5)` to raise the documented timeout class (FORGE picks `TurnNotComplete` or `TimeoutError` — see §4.4 open question; this test pins the choice). |

### 5.3 Concurrent tool calls during agent reasoning

| File | Test name | What it asserts |
|---|---|---|
| `tests/test_host_layer.py` | `test_two_handles_in_flight_no_head_of_line_blocking` | Submit turn A (slow tool), then submit turn B (fast tool) before A's handle completes. Daemon processes them in submitted order (single-thread agent loop semantics preserved), but the **caller** holding A's handle never blocks B's submission. Both handles complete; A's result observed before B's via `event.wait()`. |
| `tests/test_host_layer.py` | `test_handle_done_polling_is_safe_under_concurrency` | Caller thread polls `handle.done()` 1000× from a tight loop while daemon is processing the turn. No race on the underlying Event; final value is True. |

### 5.4 Tool error during a tool call — `AgentToolError` envelope preservation

| File | Test name | What it asserts |
|---|---|---|
| `tests/test_host_layer.py` | `test_tool_error_envelope_preserved_through_handle` | Mock dispatcher tool raises `hou.ObjectWasDeleted`-style exception. Dispatcher wraps it as `AgentToolError`. Handle completes with `STATUS_COMPLETE`; `result.tool_errors[0]` is an `AgentToolError` with `error_type == "ObjectWasDeleted"`, non-empty `traceback_str`, the same shape `tests/test_dispatcher_port.py` already pins. **Envelope shape is byte-identical to pre-2.4.** |
| `tests/test_host_layer.py` | `test_unknown_tool_via_handle_returns_agent_tool_error` | Agent emits `tool_use` for a tool not registered. Same `AgentToolError(error_type="ToolNotRegistered")` arrives in `result.tool_errors`. |

### 5.5 Daemon shutdown mid-tool-call — clean teardown

| File | Test name | What it asserts |
|---|---|---|
| `tests/test_host_layer.py` | `test_stop_during_in_flight_turn_cancels_handle` | Submit a turn whose mock tool blocks on a `threading.Event` the test owns. Call `daemon.stop(timeout=2)` while the dispatch is mid-flight. The daemon's `cancel_event` propagates into `run_turn` (existing cancel check #3 at `agent_loop.py:269`). Handle observes `STATUS_CANCELLED` via `result()`. No orphaned threads (verify via `threading.enumerate()` count returns to baseline within 1s after `stop()`). |
| `tests/test_host_layer.py` | `test_stop_drains_pending_handles_as_cancelled` | Submit two turns rapidly; daemon picks up first, second sits in queue. Call `stop()` before the first completes. Both handles eventually transition: first to `STATUS_CANCELLED` via in-flight cancel, second to `cancelled()==True` via queue drain. **Neither handle is left dangling.** No `result()` call hangs. |
| `tests/test_host_layer.py` | `test_drained_handle_raises_TurnCancelled_on_result` | After a `stop()` drains an unprocessed request, calling `handle.result(timeout=2)` on it raises `TurnCancelled`. **Replaces the prior dangling-queue silent-loss behavior.** |
| `tests/test_host_layer.py` | `test_no_orphaned_main_thread_executor_workers` | After 10 submit→complete cycles, `threading.enumerate()` shows no leaked `synapse.host.main_thread_exec` worker threads. (Pins `_exec_gui`'s worker-thread cleanup contract — daemon teardown shouldn't leak, but worth bolting down explicitly given Spike 2.4 changed who blocks where.) |

### 5.6 TurnHandle unit tests

| File | Test name | What it asserts |
|---|---|---|
| `tests/test_turn_handle.py` (new file) | `test_handle_starts_pending` | Fresh handle: `done() is False`, `cancelled() is False`. |
| `tests/test_turn_handle.py` | `test_set_result_marks_done` | After `_set_result(...)`, `done() is True`, `result()` returns the value immediately. |
| `tests/test_turn_handle.py` | `test_result_timeout_raises_turn_not_complete` | Pending handle: `result(timeout=0.1)` raises `TurnNotComplete`. Handle remains valid; subsequent `_set_result` still completes it. |
| `tests/test_turn_handle.py` | `test_cancel_then_result_raises_turn_cancelled` | Cancel a pending handle; `result(timeout=1)` raises `TurnCancelled`. |
| `tests/test_turn_handle.py` | `test_cancel_after_complete_returns_false` | If the daemon already posted a result, `cancel()` returns False and `done() is True`. `result()` still returns the originally-set value. |
| `tests/test_turn_handle.py` | `test_set_result_idempotent` | Second `_set_result` call is logged and dropped; the originally-stored value wins. No exception raised. |
| `tests/test_turn_handle.py` | `test_concurrent_waiters_all_unblock` | 5 threads each call `handle.result(timeout=2)`; one thread calls `_set_result(...)`. All 5 waiters return the same value. No deadlock. |
| `tests/test_turn_handle.py` | `test_event_property_is_underlying_event` | `handle.event.wait(timeout=0)` is False before completion, True after `_set_result`. Confirms the public Event surface for asyncio-bridge work in Spike 3+. |

### 5.7 Cancel semantics regression

| File | Test name | What it asserts |
|---|---|---|
| `tests/test_host_layer.py` | `test_daemon_cancel_propagates_to_in_flight_handle` | `daemon.cancel()` mid-turn → handle completes with `STATUS_CANCELLED` (via the existing cancel checks in `run_turn`). Confirms 2.4 didn't break the existing cooperative-cancel contract from Spike 2.2. |
| `tests/test_host_layer.py` | `test_handle_cancel_does_not_stop_daemon` | `handle.cancel()` only affects waiters on that one handle. The daemon thread continues processing the request to completion, then drops the result on the cancelled handle (logged at debug, no error). Other handles remain healthy. |

### 5.8 Hostile Crucible (carries over from §6.Gate item 1)

| File | Test name | What it asserts |
|---|---|---|
| `tests/test_host_layer.py` | `test_hostile_crucible_turn_passes_against_live_executor_shim` | The 4/20 hostile turn re-run: full multi-iteration `run_turn` with a `tool_use` → `synapse_inspect_stage` → `tool_result` → `end_turn` script, against a `main_thread_executor` shim that simulates GUI Houdini's `hdefereval` semantics (caller-thread poll-and-pump). Handle completes within 10s. `result.tool_errors == []`. **No `MainThreadTimeoutError`, no 30s hang.** This test is the headless analog of the Crucible turn that didn't run end-of-day 4/20. The graphical-Houdini live verification remains a manual gate item. |

### 5.9 Test count delta target

CRUCIBLE: pre-2.4 baseline is the 2706 figure from Spike 2.3 (now reverted, so back to 2700-ish — confirm during repo audit). Post-2.4 must strictly increase. Net-new from §5: ~24 tests. Expected post-2.4 figure: **≥2724 passing**, same 5 pre-existing failures, zero new regressions. If the count drops, stop and surface — Sprint invariant 3 violated.

---

## 6. Gate criteria

Restated **verbatim** from `docs/sprint3/CONTINUATION_INSIDE_OUT_TOPS.md` § Spike 2.4 Gate (lines 131–137):

- [ ] Hostile Crucible turn passes (the one that didn't run end-of-day 4/20)
- [ ] Baseline turn re-runs without timeout
- [ ] Test suite green at ≥2700 passing
- [ ] No new regressions
- [ ] `hou.secure` audit revisited — env-var fallback path documented (carried from Sprint 3 parked bug)

**No work on Spike 3 until 2.4's gate is green.** Inside-out without a working agent loop is theoretical.

---

## 7. Risk register

### 7.1 Invariants threatened — and how the design preserves them

| Invariant | Status under Option A | Notes |
|---|---|---|
| All tool calls route through Dispatcher | **Preserved.** | `Dispatcher.execute` is unchanged. `agent_loop.run_turn` continues to call it synchronously from the daemon thread. The Future contract sits outside the agent loop. |
| `AgentToolError` envelope shape preserved | **Preserved.** | `AgentToolError` dataclass and `to_dict()` unchanged. `dispatcher.py:240–251` exception-wrap path unchanged. Tests in §5.4 pin the byte-exact envelope. |
| Test count strictly increases or holds | **Net +~24, expected to hold.** | §5.9 names the figure; §5 itemizes every new test. |
| No new dependencies — vendored anthropic stays the boundary | **Preserved.** | `TurnHandle` uses only `threading.Event` and `typing`. No asyncio dependency leaked into the cognitive layer. The `event` property exposes a plain `threading.Event`; asyncio bridging at Spike 3+ uses `asyncio.get_running_loop().run_in_executor(None, handle.event.wait)` or similar — that's the **caller's** problem, not the daemon's. |
| Strangler Fig — old WebSocket path stays operational | **Preserved.** | `mcp_server.py` not touched. WebSocket handlers continue to call `Dispatcher.execute` directly (synchronous, single-threaded — no main-thread deadlock surface). Only the in-process daemon caller path changes. |
| Hard API verification before any Houdini call | **No new `hou.*` API surface.** | Option A introduces no new `hou` calls. The detection in §4.4 (`submit_turn_blocking` warning when on main thread in GUI mode) uses `hou.isUIAvailable()` — already exercised by the boot gate. **No new live-Houdini `dir()` audit required.** Flagging this for FORGE: confirm before any other `hou.*` is accidentally added. |
| Cognitive boundary lint (no `import hou` under `synapse/cognitive/**`) | **Preserved.** | `TurnHandle` lives in `synapse.host.*`. `synapse.cognitive.*` is not modified. |

### 7.2 What could go wrong

1. **Caller convenience traps.** The most plausible failure mode is somebody (test code, panel UI code, future Spike 3 wiring) calling `submit_turn_blocking` from the Houdini main thread because it looks like the obvious shape. Mitigation: warning at runtime when both `hou.isUIAvailable()` is True and `threading.current_thread() is threading.main_thread()`. Test in §5 not specified for this; ADD if FORGE wants belt-and-suspenders.
2. **Handle leak.** A panel UI submits a turn, the user closes the panel, the handle goes out of scope before the daemon's result post. The result is dropped (handle becomes unreachable, daemon's `_set_result` is a no-op). No crash, no leak in the daemon thread, but the agent's reasoning history is lost. Mitigation: panel UI keeps a reference until at least `handle.done()`. Document in §4.1 docstring; not enforceable structurally.
3. **`submit_turn` rename breaks external callers.** Sprint 2 tests and possibly the Crucible runbook script assume the old synchronous shape. Mitigation: `submit_turn_blocking` is exactly the old shape; one-line search-and-replace migration. CRUCIBLE pins the migration in §5.2.
4. **`stop()` race.** If a request is mid-pop from the queue when `stop()` fires, the `_drain_request_queue` change in §4.6 cancels handles for not-yet-popped requests. The actively-processing request's handle still gets `_set_result(STATUS_CANCELLED)` from the in-flight cancel path. Both edge cases tested in §5.5.
5. **Two-thread-cancellation order ambiguity.** `daemon.cancel()` and `handle.cancel()` are now distinct. The semantics: `daemon.cancel()` stops the daemon (all handles cascade); `handle.cancel()` is local to one waiter. §5.7 pins this; document explicitly in `TurnHandle.cancel()` docstring.

### 7.3 Open questions (need orchestrator/human attention before FORGE picks up)

1. **`TimeoutError` vs `TurnNotComplete` for `submit_turn_blocking`.** Tests in `tests/test_host_layer.py:649` (`test_submit_turn_timeout_raises_timeouterror`) expect stdlib `TimeoutError`. If we keep `TimeoutError`, callers can't distinguish "result timed out" from "main-thread executor timed out" (also `TimeoutError`). If we move to `TurnNotComplete`, that test needs updating in §5.2. Joe / orchestrator: which?
2. **Scope of the runtime warning in `submit_turn_blocking`.** Is the warning a `logger.warning(...)` only, or do we promote to a `RuntimeError` when called from the main thread in GUI mode? Hard fail prevents silent re-introduction of the deadlock; soft warn keeps tests easier to write. Recommend hard fail; defer to orchestrator.
3. **Async-bridging API surface.** Spike 3 will want to compose `TurnHandle.event` with PDG event arrival. Should §4.1 add `__await__` or an `asyncio_future()` helper now, or wait for Spike 3.1 to surface the actual shape needed? Recommend: wait. Add nothing speculative. FORGE ships only what §4.1 specifies.
4. **`submit_turn` signature backward compatibility.** The removal of `wait_timeout` from `submit_turn` is technically a breaking change. The migration is mechanical (rename to `submit_turn_blocking`), and there are no external callers outside the codebase per Strangler Fig (WebSocket adapter doesn't call `submit_turn`). Confirm there are no callers outside `tests/` and the (manual) Crucible runbook before FORGE removes the old shape. Audit script: `rg -n 'submit_turn\b' --type py`.

### 7.4 Parked vs. in-scope

**In scope for Spike 2.4:**
- Future-shaped `submit_turn` and `TurnHandle`
- `submit_turn_blocking` convenience
- All tests in §5
- Documenting the env-var fallback path (§8a) — see decision below

**Parked (not opened in 2.4):**
- Asyncio-native `submit_turn` (would replace `threading.Event` with `asyncio.Future`)
- Multi-handle composition primitives (`TurnHandle.gather(...)`)
- Cancellation token unification (the `cancel_event` and `handle.cancel()` paths are intentionally separate; unifying them is a larger refactor)
- Streaming results (handle pushes incremental tokens) — Spike 4+ if at all
- `dispatcher.execute_async` — would let tools themselves return Futures, allowing the daemon thread to re-enter the agent loop while a tool call is pending. Real Option-C territory; reserve.

---

## 8. `hou.secure` note — env-var fallback path documented (option a)

Choosing option (a): document the current state of the env-var fallback path here. No follow-up commit required — the fallback already does what the Spike 2.4 gate item asks for. The 2.3 revert removed the import-time INFO probe but kept the runtime fallback intact.

### 8.1 Current state, post-revert

`python/synapse/host/auth.py` exposes:

- `CREDENTIAL_LABEL = "synapse_anthropic"`
- `ENV_VAR = "ANTHROPIC_API_KEY"`
- `get_anthropic_api_key() -> Optional[str]` — checks `_try_hou_secure()` first, then `_try_env_var()`, returns `None` if neither produces a non-empty/non-whitespace key.

Pre-2.3, the auth module had a runtime `_try_hou_secure` that probed for `hou.secure.password` and silently fell through to the env var on absence — which was the production-correct behavior (since `hou.secure` doesn't exist in Houdini 21.0.671 per `dir(hou)` audit captured in 43ee77f's commit message). Spike 2.3 added a one-shot import-time INFO log surfacing the fallback decision; the revert removed that log along with the (deadlock-causing) `_boot_inspector_transport`.

### 8.2 Why this is correct

The env var path is the **current production path**. The `hou.secure` probe is **forward-compatible** — it will pick up the credential store transparently when SideFX ships the API in a future Houdini build. The runtime probe's silent-fall-through is correct behavior; logging it isn't necessary for correctness, only for operator transparency.

### 8.3 What ships in Spike 2.4

A two-paragraph clarifying comment block at the top of `python/synapse/host/auth.py` (FORGE's job to add — not in this design's scope as code, but specified here as an artifact):

> **Production path: `ANTHROPIC_API_KEY` env var.**
> Houdini 21.0.671 does not expose `hou.secure`. The runtime
> `_try_hou_secure` probe is retained for forward compatibility:
> when SideFX ships a `hou.secure.password(label)` API in a future
> release, this module picks it up without code changes. Until
> then, `_try_hou_secure` returns `None` silently and the env var
> path is taken on every call. **No logging is emitted on
> fallback** — operators verify path liveness via boot-time
> `daemon._resolved_api_key` inspection, not log scraping.
>
> **Setting the credential:**
>
>     export ANTHROPIC_API_KEY=sk-ant-...
>
> Or, when `hou.secure` becomes available:
>
>     hou.secure.setPassword('synapse_anthropic', 'sk-ant-...')
>
> The label `synapse_anthropic` is shared with `spikes/spike_0.py`.
> Rename only in lockstep across both call sites and the deployment
> docs.

This comment block is the §6 gate item's "documented." No new tests required — `tests/test_host_layer.py` already covers env-var fallback (lines 27–82).

> **Audit trail this design produces:** §8 closes the gate item without re-introducing the import-time logging that the 2.3 revert removed. The fallback path is correct as-shipped post-revert; the only deficit was documentation, which §8.3 closes.

---

## 9. Summary for FORGE / CRUCIBLE handoff

- **One option chosen:** A — non-blocking `submit_turn` returning `TurnHandle`.
- **One file created:** `python/synapse/host/turn_handle.py`.
- **Three files modified:** `daemon.py` (signature changes + private writer wiring), `__init__.py` (re-exports), `auth.py` (comment-block clarification per §8.3).
- **One file added by CRUCIBLE:** `tests/test_turn_handle.py` (~8 cases per §5.6).
- **One file extended by CRUCIBLE:** `tests/test_host_layer.py` (~16 net-new cases per §5.1–5.5, 5.7–5.8). Existing tests `test_submit_turn_end_to_end`, `test_submit_turn_timeout_raises_timeouterror`, `test_submit_turn_raises_when_daemon_not_running`, `test_cancel_cuts_in_flight_turn`, `test_stop_drains_unprocessed_requests` need migration to the new shape — CRUCIBLE either updates in place or replaces with the §5.2 / §5.5 entries.
- **Test count target:** ≥2724 passing (≥2700 floor plus ~24 net-new).
- **Open questions:** §7.3 — orchestrator picks `TimeoutError` vs `TurnNotComplete`, and warn-vs-raise on main-thread `submit_turn_blocking` invocation.
- **Sprint invariants:** all preserved; verification matrix in §7.1.

*End of design. FORGE proceeds. CRUCIBLE follows.*
