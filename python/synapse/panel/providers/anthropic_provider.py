"""Anthropic provider — the floor.

A faithful extraction of the original ``claude_worker`` raw-SSE transport,
re-expressed against the ``StreamProvider`` contract. The only changes from the
original ``_stream_request`` / ``_parse_sse_stream`` / ``_handle_sse_event`` are
that ``self.token_received.emit`` becomes the injected ``emit_token`` and
``self._abort`` becomes ``should_abort()``. Same body, same headers, same SSE
state machine, same ``RuntimeError`` on non-200 / stream error — **zero
behaviour change on the Claude path.**

Remote egress: ``api.anthropic.com:443`` (documented in docs/studio/EGRESS.md).
No Qt, no hou.
"""
from __future__ import annotations

import http.client
import json
import logging
import ssl

from .base import StreamProvider

logger = logging.getLogger(__name__)

_API_HOST = "api.anthropic.com"
_API_PATH = "/v1/messages"
_API_VERSION = "2023-06-01"
_HTTP_TIMEOUT = 60


def _strip_internal_keys(messages):
    """Return a copy of the history with provider-internal keys (e.g. a Gemini
    ``_gemini_thought_signature`` stashed on a tool_use block) removed from
    content blocks, so the Anthropic API never sees an unrecognized field.
    Non-mutating: the worker reuses the same history for the next (possibly
    Gemini) turn, which still needs the signature. A no-op data copy when no such
    keys exist — preserving the Claude path's zero-behaviour-change guarantee."""
    out = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_content = []
            for block in content:
                if isinstance(block, dict) and any(str(k).startswith("_gemini") for k in block):
                    block = {k: v for k, v in block.items() if not str(k).startswith("_gemini")}
                new_content.append(block)
            msg = {**msg, "content": new_content}
        out.append(msg)
    return out


def _with_prompt_cache(tools, system):
    """Mark the large, STATIC prefix — the ~18k-token tool block + the system
    prompt — with ephemeral cache breakpoints so it is cache-READ rather than
    re-prefilled on every turn. A multi-turn build otherwise re-sends ~18k tool
    tokens per turn (25 turns ~= 475k redundant prefill tokens); caching turns
    all but the first into reads. Prompt caching is GA (no beta header needed).
    Non-mutating — returns (tools, system) shaped for the request body. If the
    cached span is under the model's minimum it is simply not cached (still
    valid), so this never breaks the Claude path."""
    cached_tools = tools
    if tools:
        cached_tools = [dict(t) for t in tools]
        cached_tools[-1] = {**cached_tools[-1], "cache_control": {"type": "ephemeral"}}
    cached_system = system
    if isinstance(system, str) and system:
        cached_system = [{
            "type": "text", "text": system,
            "cache_control": {"type": "ephemeral"},
        }]
    return cached_tools, cached_system


class AnthropicProvider(StreamProvider):
    """Streams Anthropic Messages API responses (native ``input_schema`` tools)."""

    id = "claude"

    def __init__(self, model: str, max_tokens: int) -> None:
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model_identity(self) -> str:
        return self._model

    def resolve_key(self):
        # Canonical auth layer: hou.secure (where available) then the
        # ANTHROPIC_API_KEY env var, whitespace-stripped, never raising.
        from synapse.host.auth import get_anthropic_api_key
        return get_anthropic_api_key()

    def key_error_message(self) -> str:
        return (
            "No Anthropic API key found. Set it at the SYSTEM level so "
            "Houdini inherits it, then relaunch Houdini:  "
            'setx ANTHROPIC_API_KEY "sk-ant-..."  '
            "(a terminal-scoped `set` won't carry into Houdini on Windows). "
            "On builds exposing hou.secure you can instead run, in Houdini's "
            "Python shell: hou.secure.setPassword('synapse_anthropic', 'sk-ant-...')."
        )

    # ------------------------------------------------------------------
    # Streaming request
    # ------------------------------------------------------------------

    def stream(self, *, messages, tools, system, api_key, emit_token, should_abort):
        """Make one streaming API call, return ``(stop_reason, content_blocks)``."""
        cached_tools, cached_system = _with_prompt_cache(tools, system)
        body: dict = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "stream": True,
            "messages": _strip_internal_keys(messages),
            "tools": cached_tools,
        }
        if cached_system:
            body["system"] = cached_system

        payload = json.dumps(body).encode("utf-8")

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(_API_HOST, timeout=_HTTP_TIMEOUT, context=ctx)

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
                    "Anthropic API error %s: %s" % (response.status, error_body)
                )

            return self._parse_sse_stream(response, emit_token, should_abort)

        finally:
            conn.close()

    # ------------------------------------------------------------------
    # SSE parser (moved verbatim; ``token_received.emit``/``_abort`` → callbacks)
    # ------------------------------------------------------------------

    def _iter_lines(self, response, should_abort):
        """Yield lines from the HTTP response, handling chunked encoding."""
        buf = ""
        while True:
            if should_abort():
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

    def _parse_sse_stream(self, response, emit_token, should_abort):
        """Parse SSE events. Returns ``(stop_reason, content_blocks)``."""
        state = {
            "content_blocks": [],
            "current_block": None,
            "current_text": "",
            "stop_reason": None,
        }

        event_type = None

        for raw_line in self._iter_lines(response, should_abort):
            if should_abort():
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
                        self._handle_sse_event(event_type, data, state, emit_token)
                    except json.JSONDecodeError:
                        logger.debug("Skipping non-JSON SSE data: %s", data_str[:80])
                continue

            if line == "":
                event_type = None
                continue

        return state["stop_reason"], state["content_blocks"]

    def _handle_sse_event(self, event_type, data, state, emit_token):
        """Process a single SSE event, updating ``state`` in place."""

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
            elif block_type == "thinking":
                # Thinking block (adaptive/extended thinking). Accumulated and
                # returned UNCHANGED so it round-trips in replayed history —
                # the API requires thinking blocks back verbatim on the same
                # model. Never rendered (nothing is emitted for its deltas).
                state["current_block"] = {
                    "type": "thinking",
                    "thinking": "",
                    "signature": "",
                }
            elif block_type == "redacted_thinking":
                # Arrives complete in content_block_start — keep verbatim.
                state["current_block"] = dict(block)
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
                    emit_token(text)
                    if state["current_block"] and state["current_block"]["type"] == "text":
                        state["current_block"]["text"] += text

            elif delta_type == "input_json_delta":
                partial = delta.get("partial_json", "")
                state["current_text"] += partial

            elif delta_type == "thinking_delta":
                if state["current_block"] and state["current_block"]["type"] == "thinking":
                    state["current_block"]["thinking"] += delta.get("thinking", "")

            elif delta_type == "signature_delta":
                if state["current_block"] and state["current_block"]["type"] == "thinking":
                    state["current_block"]["signature"] = delta.get("signature", "")

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

                # Never append an empty text block: under display:"omitted" a
                # thinking-only or unknown block used to become {"text": ""},
                # which the API rejects on replay (400 on tool-loop turn 2).
                if block["type"] != "text" or block["text"]:
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
            raise RuntimeError("Anthropic stream error: %s" % error_msg)
