"""
Claude API Streaming Worker -- QThread with full tool-use conversation loop.

Runs on a background QThread. Streams text tokens to the panel via signals.
When Claude requests tool calls, emits ToolRequest objects for main-thread
execution via ToolExecutor, then feeds results back into the conversation.

No hou.* imports. No Houdini dependency. Per-engine transport is delegated
to a StreamProvider (providers/) — the conversation loop is engine-neutral.
"""

from __future__ import annotations

import copy
import json
import logging
import threading

try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    from PySide2.QtCore import QThread, Signal

from .providers.registry import (
    ANTHROPIC_MODEL as _MODEL,
    ANTHROPIC_MAX_TOKENS as _MAX_TOKENS,
    build_provider as _build_provider,
)
from .retry_breaker import ABANDON_THRESHOLD, breaker_message
from .tool_bridge import get_anthropic_tools_for_worker
from .tool_executor import ToolRequest, try_mcp_tool_call
from .worker_policy import denial_tool_result, is_tool_allowed_for_worker

# W5-PANEL item 3: fold each API call's real token usage into the per-task sink
# so the Token tab (face_token) can read a receipt instead of a dead counter.
# Import-guarded — a sink that fails to load must never break a turn.
try:
    from .usage_sink import USAGE_SINK
except Exception:  # pragma: no cover
    USAGE_SINK = None

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 25
_TOOL_WAIT_TIMEOUT = 30.0   # floor; C7 raises per-tool via _wait_budget()


def _wait_budget(tool_name):
    """Qt-fallback wait budget for a tool (C7): at least _TOOL_WAIT_TIMEOUT,
    raised to the shared per-tool table (+5s margin) for slow tools — a render
    (120s) or sequence (600s) must not be reported dead at 30s."""
    try:
        from synapse.core.timeouts import timeout_for
        return max(_TOOL_WAIT_TIMEOUT, timeout_for(tool_name) + 5.0)
    except Exception:
        return _TOOL_WAIT_TIMEOUT


def _spawn_off_main_tool_thread(executor, request: ToolRequest) -> None:
    """Run ``executor.execute_tool_off_main(request)`` on a short-lived daemon
    thread so the handler's internal ``run_on_main`` calls take the DEFERRED
    path instead of Fast path 2 inline. Lives at module scope so it is testable
    without constructing a full ClaudeWorker."""
    t = threading.Thread(
        target=executor.execute_tool_off_main,
        args=(request,),
        name="synapse.panel.tool.{}".format(request.tool_name),
        daemon=True,
    )
    t.start()


class ClaudeWorker(QThread):
    """Background worker that streams Claude API responses with tool-use loops.

    Signals:
        token_received(str):  Individual text tokens for streaming display.
        stream_done():        Conversation loop completed successfully.
        stream_error(str):    Error message on failure.
        tool_requested(object): Emits a ToolRequest for main-thread execution.
        tool_status(str, str, str):  (tool_name, status, summary) -- status is "running"/"done"/"error".
        render_receipt(object): RETINA T0 perception event for a render tool
            (or None — an honest 'no receipt'). Computed here on the worker
            thread, where the manifest + EXR-header file I/O belongs.
        integrity_updated(object): The session IntegrityBlock roll-up
            (``SessionIntegrityTracker.summary()`` dict) after each tracked
            result — the panel's "what changed" / fidelity readout (Mile 4).
    """

    token_received = Signal(str)
    stream_done = Signal()
    stream_error = Signal(str)
    tool_requested = Signal(object)
    tool_status = Signal(str, str, str)
    render_receipt = Signal(object)
    integrity_updated = Signal(object)

    def __init__(
        self,
        messages: list[dict],
        system_prompt: str = "",
        parent=None,
        tools: list[dict] | None = None,
        enforce_worker_policy: bool = True,
        provider=None,
    ) -> None:
        super().__init__(parent)
        self._messages: list[dict] = copy.deepcopy(messages)
        self._system: str = system_prompt
        # Autonomous worker: advertise only the allowlisted tool subset so the
        # LLM never sees a denied tool. enforce_worker_policy gates the
        # dispatch-side check (the load-bearing security boundary).
        self._enforce_worker_policy: bool = enforce_worker_policy
        self._tools: list[dict] = (
            tools if tools is not None else get_anthropic_tools_for_worker()
        )
        self._abort: bool = False
        # Off-main ToolExecutor for the bridge-DOWN fallback. Built lazily on
        # first use (on this worker thread) — the panel wires its own executor
        # to the tool_requested signal for the synchronous Qt slot path, but
        # this worker has no handle to that instance (the wiring lives in
        # synapse_panel.py, outside this module). A dedicated executor is safe:
        # execute_tool_off_main calls _dispatch directly (no Qt signal/slot),
        # and handler.handle's hou.* work routes through run_on_main regardless
        # of which ToolExecutor instance owns the handler.
        self._offmain_executor = None
        # F2 (2026-08-14): consecutive abandoned (main-thread timeout) attempts,
        # keyed by (tool_name, canonical input). Retries are new tool-use
        # iterations, so they bypass the WS stall gate's judgment — this is the
        # one hop that carries that information back into the retry path.
        self._retry_abandons: dict = {}
        # The engine for this turn. Defaults to the Claude floor; the panel
        # passes a selected provider for the multi-provider switch. Transport +
        # request/response translation live in the provider — the loop below is
        # engine-neutral (it consumes normalized Anthropic-shaped blocks).
        self._provider = provider if provider is not None else _build_provider()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def abort(self) -> None:
        """Signal the worker to stop at the next safe point."""
        self._abort = True

    def get_messages(self) -> list[dict]:
        """Return a copy of the current message history.

        Useful for the panel to sync conversation state after tool loops
        have appended assistant/user messages.
        """
        return copy.deepcopy(self._messages)

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Entry point executed on the background thread."""
        try:
            # Key resolution is the provider's concern (Anthropic → hou.secure /
            # ANTHROPIC_API_KEY; Gemini → GEMINI_API_KEY). On a missing key the
            # provider supplies the human-facing message — surfaced, never silent.
            api_key = self._provider.resolve_key()
            if not api_key:
                self.stream_error.emit(self._provider.key_error_message())
                return

            self._conversation_loop(api_key)
            if not self._abort:
                self.stream_done.emit()

        except Exception as exc:
            logger.exception("ClaudeWorker fatal error")
            self.stream_error.emit(str(exc))

    # ------------------------------------------------------------------
    # Core conversation loop
    # ------------------------------------------------------------------

    def _conversation_loop(self, api_key: str) -> None:
        """Repeat API calls until Claude stops requesting tools.

        Each iteration:
          1. Stream one API response, accumulating content blocks.
          2. If stop_reason is "tool_use", execute all tool calls on the
             main thread, append results, and loop.
          3. If stop_reason is "end_turn" or "max_tokens", return.
        """
        tool_calls_total = 0   # L9: tool calls across the whole turn-loop
        # W5-PANEL item 3: open a fresh per-task usage receipt keyed to the
        # SELECTED model, so the Token tab shows THIS task's spend, not a lifetime
        # total. model_identity is the provider's own name for the engine.
        if USAGE_SINK is not None:
            try:
                USAGE_SINK.begin_task(getattr(self._provider, "model_identity", None))
            except Exception:
                pass
        for iteration in range(_MAX_TOOL_ITERATIONS):
            if self._abort:
                return

            stop_reason, content_blocks = self._provider.stream(
                messages=self._messages,
                tools=self._tools,
                system=self._system,
                api_key=api_key,
                emit_token=self.token_received.emit,
                should_abort=lambda: self._abort,
            )

            # Fold this call's real usage into the task total BEFORE the abort
            # check — those tokens were billed even if the turn is aborting, and
            # the provider publishes last_usage on abort too (anthropic_provider
            # finally). None (no usage reported) counts the run but invents no
            # field, so a non-Anthropic engine stays honestly UNKNOWN.
            if USAGE_SINK is not None:
                try:
                    USAGE_SINK.add(getattr(self._provider, "last_usage", None))
                except Exception:
                    pass

            if self._abort:
                return

            if stop_reason == "tool_use":
                # Append the assistant message with all content blocks
                self._messages.append({
                    "role": "assistant",
                    "content": content_blocks,
                })

                # Process every tool_use block, collect results
                tool_results: list[dict] = []
                for block in content_blocks:
                    if block.get("type") != "tool_use":
                        continue

                    if self._abort:
                        return

                    result_msg = self._execute_tool_block(block)
                    tool_results.append(result_msg)
                    tool_calls_total += 1

                # Append all tool results in a single user message
                if tool_results:
                    self._messages.append({
                        "role": "user",
                        "content": tool_results,
                    })

            else:
                # end_turn, max_tokens, or anything else -- we're done.
                # L9: record the sequential-turn count (the dominant latency
                # term) so an imperative build (many turns) vs a one-shot
                # declarative call (1 turn) is measurable on disk.
                logger.info(
                    "Conversation complete: %d turns, %d tool calls",
                    iteration + 1, tool_calls_total,
                )
                return

        logger.warning(
            "Hit max tool-use iterations (%d) with %d tool calls, stopping -- "
            "likely an imperative build that should have been one declarative "
            "synapse_solaris_build_graph call",
            _MAX_TOOL_ITERATIONS, tool_calls_total,
        )

    # ------------------------------------------------------------------
    # Single tool execution
    # ------------------------------------------------------------------

    def _execute_tool_block(self, block: dict) -> dict:
        """Execute one tool_use block, preferring MCP dispatch.

        Tries the local MCP endpoint first (worker-thread safe, gets
        resilience + journal logging). Falls back to Qt signal-based
        main-thread dispatch if MCP is unavailable.

        Returns a tool_result content block for the next API call.
        """
        tool_use_id = block["id"]
        tool_name = block["name"]
        tool_input = block.get("input", {})

        # --- Allowlist gate (load-bearing security check) ---
        # The autonomous worker has no human in the loop. Deny anything outside
        # the worker policy BEFORE dispatch. enforce_worker_policy=False
        # preserves the interactive/human-in-the-loop path untouched.
        if self._enforce_worker_policy:
            allowed, reason = is_tool_allowed_for_worker(tool_name)
            if not allowed:
                summary = json.dumps(tool_input, default=str)[:120] if tool_input else ""
                self.tool_status.emit(tool_name, "error", reason)
                return denial_tool_result(tool_use_id, tool_name, reason)

        # --- F2 retry circuit-breaker ---
        cmd_key = (tool_name, json.dumps(tool_input, sort_keys=True, default=str))
        breaker_msg = self._check_retry_breaker(cmd_key)
        if breaker_msg is not None:
            self.tool_status.emit(tool_name, "error", breaker_msg)
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": breaker_msg,
                "is_error": True,
            }

        summary = json.dumps(tool_input, default=str)[:120] if tool_input else ""
        self.tool_status.emit(tool_name, "running", summary)

        # Track tool call for session integrity (best-effort)
        try:
            from synapse.panel.session_integrity import get_tracker
            get_tracker().record_tool_call(tool_name, tool_input)
        except Exception:
            pass

        # --- Try MCP dispatch first (worker-thread safe) ---
        try:
            mcp_result = try_mcp_tool_call(tool_name, tool_input)
            if mcp_result is not None:
                self._retry_abandons.pop(cmd_key, None)  # F2: success clears
                # Extract integrity block if present in result
                self._track_integrity(mcp_result)
                # RETINA T0: run the render's file-truth receipt off the Qt
                # thread (this IS the worker thread — correct place for the
                # manifest + EXR-header file I/O).
                self._emit_render_receipt(tool_name, mcp_result)
                self.tool_status.emit(tool_name, "done", summary)
                content_str = json.dumps(mcp_result, default=str)
                result = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content_str,
                    "is_error": False,
                }
                # THE LAST LINK. _handle_capture_viewport has always worked -
                # it reads the GL framebuffer correctly via the flipbook API and
                # writes a file. And the file went nowhere: this module
                # contained ZERO occurrences of "image" or "base64". SYNAPSE
                # could take the picture and had never shown one to a model.
                #
                # Anthropic accepts a LIST of content blocks inside a
                # tool_result, images included, so the whole gap was: notice the
                # path, read the bytes, attach the block.
                #
                # Returns `result` unchanged when the model cannot see, when the
                # file is missing or oversized, or when the tool returned no
                # path - and says WHY in the text the model reads, because a
                # silent failure here is indistinguishable from a model that
                # looked and saw nothing.
                try:
                    from .vision_attach import attach_image
                    # model_identity is the provider's own name for the engine
                    # (providers/base.py:34). Asking the PROVIDER rather than
                    # holding a copy means the multi-provider switch cannot
                    # leave this stale - the model that answers is the model
                    # whose capability was checked.
                    _model = getattr(self._provider, "model_identity", "") or ""
                    result, _verdict = attach_image(result, mcp_result, _model)
                    # THE VERDICT GOES TO THE PANEL, not just to the model.
                    #
                    # v1 put the refusal in the tool result and trusted the
                    # model to relay it. Measured on a live turn: glm-5:cloud
                    # received "not vision-capable, the capture was NOT sent",
                    # absorbed it, and answered "here's what I can see from the
                    # viewport capture" - fluent, plausible, entirely inferred
                    # from the node graph, and indistinguishable from sight.
                    #
                    # A note in a tool result is a REQUEST. This is the flag,
                    # and it rides the same rail as every other tool status, so
                    # it reaches the result surface where the model cannot
                    # author it away.
                    if _verdict is not None:
                        self.tool_status.emit("vision", _verdict[0], _verdict[1])
                except Exception:
                    pass
                return result
        except RuntimeError as exc:
            # MCP returned a JSON-RPC error — tool-level failure. The
            # main-thread-timeout variant ("...may STILL be running inside
            # Houdini...") is an ABANDON: the tool may still be executing, so
            # it counts toward the F2 retry circuit-breaker.
            if "STILL be running inside Houdini" in str(exc):
                self._note_abandon(cmd_key)
            self.tool_status.emit(tool_name, "error", summary)
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": str(exc),
                "is_error": True,
            }
        except Exception:
            pass  # MCP unavailable — fall through to signal path

        # --- Fallback: dispatch on a daemon thread (off-main) ---
        # The MCP path is down (try_mcp_tool_call returned None above), so the
        # hwebserver thread is not going to run the handler for us. The OLD
        # fallback emitted a Qt signal delivered via AutoConnection to
        # ToolExecutor.execute_tool on the MAIN thread — which meant the entire
        # handler (including node.render / execute_python / solaris_build_graph)
        # ran UNINTERRUPTIBLY on the GUI thread: every internal run_on_main call
        # hit Fast path 2 (main_thread.py:240, "caller IS main thread → fn()
        # inline, NO timeout possible"). That is the multi-second "cannot
        # select nodes" freeze the artist feels while chatting.
        #
        # Instead, run the SAME dispatch on a daemon thread. Because the daemon
        # thread is OFF main, handler.handle's internal run_on_main calls take
        # the DEFERRED path (hdefereval.executeDeferred + per-tool timeout,
        # interleaved with UI events) — identical to what the MCP path does
        # when the bridge is up. The main thread is freed for node selection /
        # viewport / the 1s FreezeChain heartbeat. The tool_requested signal +
        # execute_tool slot stay in place for any direct/test caller and as a
        # fallback-of-last-resort, but the worker no longer routes through
        # them.
        request = ToolRequest(
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            tool_input=tool_input,
        )

        self._dispatch_off_main(request)

        # Block until executor completes (or per-tool timeout — C7)
        budget = _wait_budget(tool_name)
        completed = request.done.wait(timeout=budget)
        if not completed:
            self._note_abandon(cmd_key)  # F2: worker-level abandon
            request.error = (
                f"Tool {tool_name!r} did not finish within {budget:.0f}s — it may "
                "STILL be running inside Houdini. Do not retry; check the scene/"
                "cook state first."
            )

        # Determine status
        if request.error:
            self.tool_status.emit(tool_name, "error", summary)
            content_str = request.error
            is_error = True
        else:
            self.tool_status.emit(tool_name, "done", summary)
            self._retry_abandons.pop(cmd_key, None)  # F2: success clears
            if isinstance(request.result, dict):
                self._track_integrity(request.result)
                # RETINA T0 receipt on the fallback (Qt executor) path too.
                self._emit_render_receipt(tool_name, request.result)
                content_str = json.dumps(request.result, default=str)
            elif request.result is not None:
                content_str = str(request.result)
            else:
                content_str = "OK"
            is_error = False

        result = {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content_str,
            "is_error": is_error,
        }
        # THE SAME ATTACH, ON THE OTHER BRANCH.
        #
        # _execute_tool_block has two paths - MCP first, then this Qt-signal
        # fallback - and the first version of this wired ONLY the MCP one. So
        # whether a viewport capture reached the model depended on which route
        # its tool happened to take, which is not a decision anyone made.
        #
        # Measured live: Fable 5, vision-capable, on a session that HAD the
        # code, answered "the capture tool gives me the image file, but it
        # doesn't stream the pixels back to me". It was right. The attach was
        # sitting on the branch its tool did not take.
        #
        # That is 'built and connected to nothing' with the connection half
        # made, which is harder to see than not making it at all.
        try:
            from .vision_attach import attach_image
            _model = getattr(self._provider, "model_identity", "") or ""
            result, _verdict = attach_image(result, request.result, _model)
            if _verdict is not None:
                self.tool_status.emit("vision", _verdict[0], _verdict[1])
        except Exception:
            pass
        return result

    # ------------------------------------------------------------------
    # Off-main fallback dispatch (bridge-DOWN path)
    # ------------------------------------------------------------------

    def _get_offmain_executor(self):
        """Lazily build the ToolExecutor used for the off-main fallback.

        Built on the worker thread on first use. ``ToolExecutor`` subclasses
        ``QObject``; constructing it parentless on a background thread gives it
        this thread's affinity, which is safe here because the off-main path
        never drives its Qt signals (``execute_tool_off_main`` skips the
        ``preflight_warning`` emit and never touches ``tool_requested``). The
        handler it lazy-loads routes all ``hou.*`` work through ``run_on_main``
        regardless of which executor instance owns it.
        """
        if self._offmain_executor is None:
            from .tool_executor import ToolExecutor
            self._offmain_executor = ToolExecutor()
        return self._offmain_executor

    def _dispatch_off_main(self, request: ToolRequest) -> None:
        """Spawn the daemon thread that runs the tool off the main thread.

        Thin instance wrapper around :func:`_spawn_off_main_tool_thread` so the
        executor is resolved via :meth:`_get_offmain_executor`.
        """
        executor = self._get_offmain_executor()
        _spawn_off_main_tool_thread(executor, request)

    # ------------------------------------------------------------------
    # F2 retry circuit-breaker (pure decision: panel/retry_breaker.py)
    # ------------------------------------------------------------------

    def _note_abandon(self, cmd_key) -> None:
        self._retry_abandons[cmd_key] = self._retry_abandons.get(cmd_key, 0) + 1

    def _check_retry_breaker(self, cmd_key):
        """Return the breaker sentence to stop this re-issue, or None.

        Opens only after ABANDON_THRESHOLD consecutive abandoned attempts of
        the SAME command AND with the F4 in-flight register
        (current_main_thread_holder — NEVER stall_state(), which is
        deferred-path-only and blind to the inline class this polices) showing
        a live holder. A cleared register means the prior hold finished
        between iterations, so the retry is safe and history resets.
        """
        abandons = self._retry_abandons.get(cmd_key, 0)
        if abandons < ABANDON_THRESHOLD:
            return None
        try:
            from synapse.server.main_thread import current_main_thread_holder
            holder = current_main_thread_holder()
        except Exception:
            holder = None
        msg = breaker_message(holder, abandons)
        if msg is not None:
            return msg
        if holder is None:
            self._retry_abandons.pop(cmd_key, None)
        return None

    # ------------------------------------------------------------------
    # Integrity tracking (best-effort)
    # ------------------------------------------------------------------

    def _track_integrity(self, result: dict | None) -> None:
        """Extract and record integrity block from tool result."""
        if not result or not isinstance(result, dict):
            return
        try:
            # MCP results may nest integrity in content or at top level
            integrity = None
            if "_integrity" in result:
                integrity = result["_integrity"]
            elif "content" in result and isinstance(result["content"], list):
                for item in result["content"]:
                    if isinstance(item, dict) and "text" in item:
                        try:
                            parsed = json.loads(item["text"])
                            if isinstance(parsed, dict) and "_integrity" in parsed:
                                integrity = parsed["_integrity"]
                                break
                        except (json.JSONDecodeError, TypeError):
                            pass

            if integrity and isinstance(integrity, dict):
                from synapse.panel.session_integrity import get_tracker
                tracker = get_tracker()
                tracker.record(integrity)

                # Surface the roll-up to the panel's fidelity readout (Mile 4).
                # Best-effort: a failing emit must never break the tool result.
                try:
                    self.integrity_updated.emit(tracker.summary())
                except Exception:
                    pass

                # Warn on low fidelity
                fidelity = integrity.get("fidelity", 1.0)
                if fidelity < 1.0:
                    logger.warning(
                        "Integrity violation: fidelity=%.2f op=%s",
                        fidelity, integrity.get("operation", "unknown"),
                    )
        except Exception:
            pass  # Never break tool dispatch for integrity tracking

    # ------------------------------------------------------------------
    # RETINA render receipt (best-effort, worker-thread compute)
    # ------------------------------------------------------------------

    def _emit_render_receipt(self, tool_name: str, result) -> None:
        """Compute the render's RETINA T0 (file-truth) receipt on THIS worker
        thread — where the manifest + EXR-header file I/O belongs — and emit it
        to the panel.

        Only render tools emit at all, so a non-render tool never disturbs a
        prior receipt. A render whose result carries a written manifest emits the
        real perception event; a render with no ``retina``/manifest emits
        ``None`` (an honest 'no receipt'), never a faked pass. Read-only: the
        panel path NEVER writes the sidecar (no ``emit_verdict``), and a receipt
        failure never breaks the tool result."""
        if "render" not in (tool_name or "").lower():
            return
        event = None
        try:
            from synapse.panel.render_receipt import compute_receipt
            event = compute_receipt(tool_name, result)
        except Exception:
            event = None
        try:
            self.render_receipt.emit(event)
        except Exception:
            pass


# ----------------------------------------------------------------------
# Headless turn execution (the bench's entry point)
# ----------------------------------------------------------------------

def run_turn_blocking(prompt: str, timeout: int = 90, system_prompt: str = None,
                      messages: list[dict] = None, provider=None) -> list[dict]:
    """Drive ONE full turn synchronously, with no Qt event loop and no panel.

    Built for `harness/bench/run_bench.py`, which scores SYNAPSE by driving the
    same stack an artist drives. It must be the same path, or the score measures
    something nobody uses.

    Why this can be synchronous: `ClaudeWorker.run()` is a thin wrapper --
    resolve the key, call `_conversation_loop`, emit done. `_conversation_loop`
    is a plain method. We construct the worker, never `start()` it, and call the
    loop directly on the caller's thread.

    Why tools still work without the panel: `_execute_tool_block` tries the
    local MCP endpoint first, which is worker-thread safe and needs no Qt
    wiring. The signal-based main-thread fallback is what the panel provides;
    headless simply never reaches it. If MCP is down, the tool call fails --
    loudly, as a tool error in the transcript, not as a silent skip.

    Signals emitted with nothing connected are no-ops, so the worker's
    `tool_status` / `token_received` chatter costs nothing here.

    Raises rather than returning empty. A missing key or a dead bridge is an
    INFRASTRUCTURE failure, and the bench must record it as `inconclusive`, not
    as a competence failure. Returning [] would let the scorer read a broken
    install as a model that cannot build a sphere -- the exact confusion this
    whole codebase's UNKNOWN rule exists to prevent.

    Args:
        prompt:        the artist's message, verbatim.
        timeout:       hard ceiling in seconds. Fixed budget is the discipline
                       that makes bench runs comparable; a turn that needs
                       longer has failed. Enforced by a watchdog that sets the
                       worker's abort flag -- the loop checks it between API
                       calls and tool blocks.
        system_prompt: overrides the default. None builds the shipped prompt.
        messages:      prior turns, for multi-turn tasks. None starts fresh.
        provider:      engine override; None takes the Claude floor.

    Returns:
        The full message list after the turn, Anthropic format -- the same
        thing `ClaudeWorker.get_messages()` hands the panel.
    """
    import threading

    if system_prompt is None:
        try:
            from synapse.panel.system_prompt import build_system_prompt
            system_prompt = build_system_prompt({})
        except Exception:
            # An empty system prompt makes the model EXPLAIN build requests
            # instead of executing them (see _build_system_prompt in
            # synapse_panel.py). Better to say so than to score the fallout.
            raise RuntimeError(
                "headless turn: system prompt unavailable; an empty prompt "
                "makes the model narrate instead of build, which would score "
                "as incompetence rather than as the harness fault it is")

    convo = list(messages or [])
    convo.append({"role": "user", "content": prompt})

    worker = ClaudeWorker(convo, system_prompt=system_prompt,
                          provider=provider)

    # Headless tool dispatch must NOT go off-main.
    #
    # _spawn_off_main_tool_thread exists so the handler's run_on_main calls take
    # the DEFERRED path -- correct in a graphical Houdini, where the marshal
    # hands work to the GUI main thread via hdefereval. Headless hython has no
    # hdefereval and no event loop, so that spawn guarantees the marshal fails:
    # every mutating tool then records main_thread_executed=False and the
    # integrity envelope reports hash_unavailable.
    #
    # Here the caller IS the main thread, so running the tool inline lands it
    # exactly where the marshal was trying to put it. Fast path 2 in
    # main_thread.run_on_main (the ident check) then handles it without ever
    # importing hdefereval. This is the goal of the deferral, not a bypass of it.
    #
    # Scoped to this instance. The panel's dispatch is untouched.
    def _dispatch_inline(request, _w=worker):
        _w._get_offmain_executor().execute_tool_off_main(request)

    worker._dispatch_off_main = _dispatch_inline

    api_key = worker._provider.resolve_key()
    if not api_key:
        raise RuntimeError("headless turn: %s"
                           % worker._provider.key_error_message())

    # Fixed budget. abort() is cooperative -- the loop honours it between API
    # calls and tool blocks, so a turn wedged inside one long tool call can
    # overrun. That is a real limit, stated rather than hidden.
    timer = threading.Timer(timeout, worker.abort)
    timer.daemon = True
    timer.start()
    try:
        worker._conversation_loop(api_key)
    finally:
        timer.cancel()

    if worker._abort:
        raise TimeoutError("headless turn exceeded its %ss budget" % timeout)

    return worker.get_messages()
