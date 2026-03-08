"""
Claude API Streaming Worker -- QThread with full tool-use conversation loop.

Runs on a background QThread. Streams text tokens to the panel via signals.
When Claude requests tool calls, emits ToolRequest objects for main-thread
execution via ToolExecutor, then feeds results back into the conversation.

No hou.* imports. No Houdini dependency. Uses only stdlib for HTTP.
"""

from __future__ import annotations

import copy
import http.client
import json
import logging
import os
import ssl
from typing import Optional

try:
    from PySide6.QtCore import QThread, Signal
except ImportError:
    from PySide2.QtCore import QThread, Signal

from .tool_bridge import get_anthropic_tools
from .tool_executor import ToolRequest, try_mcp_tool_call

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 25
_TOOL_WAIT_TIMEOUT = 30.0
_HTTP_TIMEOUT = 60
_API_HOST = "api.anthropic.com"
_API_PATH = "/v1/messages"
_API_VERSION = "2023-06-01"
_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


class ClaudeWorker(QThread):
    """Background worker that streams Claude API responses with tool-use loops.

    Signals:
        token_received(str):  Individual text tokens for streaming display.
        stream_done():        Conversation loop completed successfully.
        stream_error(str):    Error message on failure.
        tool_requested(object): Emits a ToolRequest for main-thread execution.
        tool_status(str, str, str):  (tool_name, status, summary) -- status is "running"/"done"/"error".
    """

    token_received = Signal(str)
    stream_done = Signal()
    stream_error = Signal(str)
    tool_requested = Signal(object)
    tool_status = Signal(str, str, str)

    def __init__(
        self,
        messages: list[dict],
        system_prompt: str = "",
        parent=None,
        tools: list[dict] | None = None,
    ) -> None:
        super().__init__(parent)
        self._messages: list[dict] = copy.deepcopy(messages)
        self._system: str = system_prompt
        self._tools: list[dict] = tools if tools is not None else get_anthropic_tools()
        self._abort: bool = False

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
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                self.stream_error.emit("ANTHROPIC_API_KEY not set in environment")
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
        for iteration in range(_MAX_TOOL_ITERATIONS):
            if self._abort:
                return

            stop_reason, content_blocks = self._stream_request(api_key)

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

                # Append all tool results in a single user message
                if tool_results:
                    self._messages.append({
                        "role": "user",
                        "content": tool_results,
                    })

            else:
                # end_turn, max_tokens, or anything else -- we're done
                return

        logger.warning(
            "Hit max tool-use iterations (%d), stopping", _MAX_TOOL_ITERATIONS
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

        # Block until executor completes (or timeout)
        completed = request.done.wait(timeout=_TOOL_WAIT_TIMEOUT)
        if not completed:
            request.error = f"Tool {tool_name!r} timed out after {_TOOL_WAIT_TIMEOUT}s"

        # Determine status
        if request.error:
            self.tool_status.emit(tool_name, "error", summary)
            content_str = request.error
            is_error = True
        else:
            self.tool_status.emit(tool_name, "done", summary)
            if isinstance(request.result, dict):
                self._track_integrity(request.result)
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
                get_tracker().record(integrity)

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
    # Streaming API request
    # ------------------------------------------------------------------

    def _stream_request(self, api_key: str) -> tuple[Optional[str], list[dict]]:
        """Make one streaming API call, return (stop_reason, content_blocks).

        Parses the SSE stream, emitting token_received for each text delta.
        Accumulates tool_use input JSON across multiple delta events.
        """
        # Build request body
        body: dict = {
            "model": _MODEL,
            "max_tokens": _MAX_TOKENS,
            "stream": True,
            "messages": self._messages,
            "tools": self._tools,
        }
        if self._system:
            body["system"] = self._system

        payload = json.dumps(body).encode("utf-8")

        # HTTPS connection
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(
            _API_HOST, timeout=_HTTP_TIMEOUT, context=ctx
        )

        try:
            conn.request(
                "POST",
                _API_PATH,
                body=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": _API_VERSION,
                },
            )

            response = conn.getresponse()
            if response.status != 200:
                error_body = response.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Anthropic API error {response.status}: {error_body}"
                )

            return self._parse_sse_stream(response)

        finally:
            conn.close()

    # ------------------------------------------------------------------
    # SSE parser
    # ------------------------------------------------------------------

    def _iter_lines(self, response: http.client.HTTPResponse):
        """Yield lines from the HTTP response, handling chunked encoding."""
        buf = ""
        while True:
            if self._abort:
                return
            chunk = response.read(4096)
            if not chunk:
                if buf:
                    yield buf
                return
            buf += chunk.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                yield line

    def _parse_sse_stream(
        self, response: http.client.HTTPResponse
    ) -> tuple[Optional[str], list[dict]]:
        """Parse SSE events from the HTTP response.

        Returns (stop_reason, content_blocks).

        State is tracked via a mutable dict so the event handler can
        update current_block and text accumulator in place.
        """
        state = {
            "content_blocks": [],
            "current_block": None,
            "current_text": "",
            "stop_reason": None,
        }

        event_type: Optional[str] = None

        for raw_line in self._iter_lines(response):
            if self._abort:
                break

            line = raw_line.strip()

            if line.startswith("event:"):
                event_type = line[6:].strip()
                continue

            if line.startswith("data:"):
                data_str = line[5:].strip()
                if event_type and data_str and data_str != "[DONE]":
                    try:
                        data = json.loads(data_str)
                        self._handle_sse_event(event_type, data, state)
                    except json.JSONDecodeError:
                        logger.debug("Skipping non-JSON SSE data: %s", data_str[:80])
                continue

            if line == "":
                event_type = None
                continue

        return state["stop_reason"], state["content_blocks"]

    def _handle_sse_event(
        self, event_type: str, data: dict, state: dict
    ) -> None:
        """Process a single SSE event, updating state in place."""

        if event_type == "content_block_start":
            block = data.get("content_block", {})
            block_type = block.get("type", "text")

            if block_type == "tool_use":
                state["current_block"] = {
                    "type": "tool_use",
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input": {},
                }
            else:
                state["current_block"] = {
                    "type": "text",
                    "text": "",
                }
            state["current_text"] = ""

        elif event_type == "content_block_delta":
            delta = data.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta":
                text = delta.get("text", "")
                if text:
                    self.token_received.emit(text)
                    if state["current_block"] and state["current_block"]["type"] == "text":
                        state["current_block"]["text"] += text

            elif delta_type == "input_json_delta":
                partial = delta.get("partial_json", "")
                state["current_text"] += partial

        elif event_type == "content_block_stop":
            block = state["current_block"]
            if block is not None:
                if block["type"] == "tool_use" and state["current_text"]:
                    try:
                        block["input"] = json.loads(state["current_text"])
                    except json.JSONDecodeError:
                        logger.error(
                            "Failed to parse tool input JSON: %s",
                            state["current_text"][:200],
                        )
                        block["input"] = {}

                state["content_blocks"].append(block)
                state["current_block"] = None
                state["current_text"] = ""

        elif event_type == "message_delta":
            delta = data.get("delta", {})
            reason = delta.get("stop_reason")
            if reason:
                state["stop_reason"] = reason

        elif event_type == "message_stop":
            pass  # End of message, stop_reason already captured

        elif event_type == "error":
            error_msg = data.get("error", {}).get("message", str(data))
            raise RuntimeError(f"Anthropic stream error: {error_msg}")
