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

try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    from PySide2.QtCore import QThread, Signal

from .providers.registry import (
    ANTHROPIC_MODEL as _MODEL,
    ANTHROPIC_MAX_TOKENS as _MAX_TOKENS,
    build_provider as _build_provider,
)
from .tool_bridge import get_anthropic_tools_for_worker
from .tool_executor import ToolRequest, try_mcp_tool_call
from .worker_policy import denial_tool_result, is_tool_allowed_for_worker

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
        turns_done = 0         # API round trips COMPLETED (streams returned)
        # Outcome for the U2 record. Every exit path is captured (fix pass
        # 2026-07-18 — recording only completion/cap gave the distribution
        # survivorship bias: the Stop button exists precisely to kill
        # runaway imperative loops, so aborted sends skew LONG and were
        # exactly the tail this instrument was built to measure). "error"
        # is the default so an exception from provider.stream records
        # honestly via the finally below before propagating to run().
        outcome = "error"
        try:
            for iteration in range(_MAX_TOOL_ITERATIONS):
                if self._abort:
                    outcome = "aborted"
                    return

                stop_reason, content_blocks = self._provider.stream(
                    messages=self._messages,
                    tools=self._tools,
                    system=self._system,
                    api_key=api_key,
                    emit_token=self.token_received.emit,
                    should_abort=lambda: self._abort,
                )
                turns_done = iteration + 1

                if self._abort:
                    outcome = "aborted"
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
                            outcome = "aborted"
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
                    # L9: the sequential-turn count (the dominant latency
                    # term) so an imperative build (many turns) vs a one-
                    # shot declarative call (1 turn) is measurable on disk.
                    logger.info(
                        "Conversation complete: %d turns, %d tool calls",
                        turns_done, tool_calls_total,
                    )
                    outcome = "completed"
                    return

            logger.warning(
                "Hit max tool-use iterations (%d) with %d tool calls, "
                "stopping -- likely an imperative build that should have "
                "been one declarative synapse_solaris_build_graph call",
                _MAX_TOOL_ITERATIONS, tool_calls_total,
            )
            outcome = "cap"
        finally:
            self._record_turns(turns_done, tool_calls_total,
                               hit_cap=(outcome == "cap"), outcome=outcome)

    def _record_turns(self, turns: int, tool_calls: int, hit_cap: bool,
                      outcome: str = "completed") -> None:
        """U2 instrument (scene-model Mile 0): persist the turns-per-send
        record the L9 log line above only *logs*. Lazy import + broad
        except — zero behavior change on any failure, worker-thread safe
        (turns_ledger serializes with its own module lock). ``model`` is
        the CTO-gate 6b confound control (mid-window model updates must be
        visible in the baseline)."""
        try:
            from .turns_ledger import append_turn_record
            append_turn_record(
                provider_id=getattr(self._provider, "id", "unknown"),
                turns=turns,
                tool_calls=tool_calls,
                hit_cap=hit_cap,
                outcome=outcome,
                model=getattr(self._provider, "model_identity", None),
            )
        except Exception:
            logger.debug("turns ledger record failed", exc_info=True)

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
                # Extract integrity block if present in result
                self._track_integrity(mcp_result)
                # RETINA T0: run the render's file-truth receipt off the Qt
                # thread (this IS the worker thread — correct place for the
                # manifest + EXR-header file I/O).
                self._emit_render_receipt(tool_name, mcp_result)
                self.tool_status.emit(tool_name, "done", summary)
                content_str = json.dumps(mcp_result, default=str)
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": content_str,
                    "is_error": False,
                }
        except RuntimeError as exc:
            # MCP returned a JSON-RPC error — tool-level failure
            self.tool_status.emit(tool_name, "error", summary)
            return {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": str(exc),
                "is_error": True,
            }
        except Exception:
            pass  # MCP unavailable — fall through to signal path

        # --- Fallback: Qt signal to main-thread executor ---
        request = ToolRequest(
            tool_use_id=tool_use_id,
            tool_name=tool_name,
            tool_input=tool_input,
        )

        self.tool_requested.emit(request)

        # Block until executor completes (or per-tool timeout — C7)
        budget = _wait_budget(tool_name)
        completed = request.done.wait(timeout=budget)
        if not completed:
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

        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content_str,
            "is_error": is_error,
        }

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
