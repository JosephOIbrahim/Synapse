"""Anthropic provider — the floor.

A faithful extraction of the original ``claude_worker`` raw-SSE transport,
re-expressed against the ``StreamProvider`` contract. The only changes from the
original ``_stream_request`` / ``_parse_sse_stream`` / ``_handle_sse_event`` are
that ``self.token_received.emit`` becomes the injected ``emit_token`` and
``self._abort`` becomes ``should_abort()``. Same body, same headers, same SSE
state machine. Non-200 and stream errors include bounded, sanitized diagnostic
hints; successful requests and model-access checks are unchanged.

Remote egress: ``api.anthropic.com:443`` (documented in docs/studio/EGRESS.md).
No Qt, no hou.
"""
from __future__ import annotations

import http.client
import json
import logging
import ssl

from .base import StreamProvider
from synapse.model_access import guarded_stream, stream_spec, before_stream_send, ModelRequestFailed

logger = logging.getLogger(__name__)

_API_HOST = "api.anthropic.com"
_API_PATH = "/v1/messages"
_API_VERSION = "2023-06-01"
_HTTP_TIMEOUT = 60


def _error_detail(data):
    """Classify service errors without echoing scene text, credentials or HTML.

    Error types are vendor-defined; the few message matches distinguish common
    invalid_request_error causes. Unknown wording stays unknown. These hints
    never trigger retries, account changes, or conversation edits.
    """
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return "No readable service details were returned."
    message = error.get("message")
    message = message.lower() if isinstance(message, str) and len(message) <= 8192 else ""
    if "credit balance" in message:
        return "Your Anthropic API credit balance is too low. Check billing in the Anthropic Console."
    if "spend limit" in message or "spending limit" in message:
        return "Your Anthropic account or workspace has reached its spend limit. Check the Anthropic Console."
    kind = error.get("type")
    if kind == "invalid_request_error":
        if "thinking" in message or "signature" in message:
            return "The service rejected the reasoning history. SYNAPSE's conversation replay needs inspection."
        if "prompt is too long" in message or "context window" in message:
            return "The conversation is too long for this model. Start a fresh conversation with a concise scene summary."
        if "tool_use" in message or "tool_result" in message:
            return "The service rejected the tool history. SYNAPSE's tool-result pairing needs inspection."
    hints = {
        "invalid_request_error": "The service rejected the request format or content. Check conversation and model settings.",
        "authentication_error": "The service rejected the API key. Check the Anthropic connection.",
        "billing_error": "The service reported a billing problem. Check the Anthropic Console.",
        "permission_error": "The account lacks permission for this resource. Check model access in the Anthropic Console.",
        "not_found_error": "The requested model or resource was not found. Check the selected model.",
        "rate_limit_error": "The account reached a rate limit or usage cap. Check limits in the Anthropic Console.",
        "overloaded_error": "The Anthropic service is temporarily overloaded. Try again later.",
        "api_error": "The Anthropic service reported an internal error. Try again later.",
        "timeout_error": "The Anthropic service timed out. Inspect any completed tool work before retrying.",
        "request_too_large": "The request is too large. Use a shorter conversation or smaller attachments.",
    }
    return hints.get(kind, "The service returned an unrecognized error.") if isinstance(kind, str) else "No readable service details were returned."


def _read_error_detail(response):
    """Bound diagnostic reads; malformed or unavailable bodies retain failure."""
    try:
        raw = response.read(8193)
        if len(raw) <= 8192:
            return _error_detail(json.loads(raw))
    except Exception:
        pass
    return "No readable service details were returned."


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


def _with_prompt_cache(tools, system, messages):
    """Mark the cacheable prefix with ephemeral cache breakpoints so it is
    cache-READ rather than re-prefilled on every turn.

    Breakpoint budget — Anthropic allows AT MOST 4 per request, and this
    function is the only place on the Claude path that stamps them:

      1. last tool definition        (static prefix: the ~18k-token tool block)
      2. system prompt               (static prefix)
      3. last content block of the   (moves forward each iteration — the
         last message                 standard incremental-caching pattern)

    = 3 total, within the limit. Breakpoints 1–2 cover the static prefix; a
    multi-turn build otherwise re-sends ~18k tool tokens per turn (25 turns
    ~= 475k redundant prefill tokens). Breakpoint 3 makes the ACCUMULATED
    CONVERSATION (tool_results included) a cache read on the next iteration
    of the worker's tool loop — without it every iteration re-prefills the
    whole history, an O(K^2) prefill term across up to 25 iterations.
    Because this copy is non-mutating, the caller's history never carries a
    marker: each request holds exactly one message breakpoint (the current
    last block), so markers cannot accumulate past the budget.

    Prompt caching is GA (no beta header needed). Non-mutating — returns
    (tools, system, messages) shaped for the request body. If the cached span
    is under the model's minimum it is simply not cached (still valid), so
    this never breaks the Claude path."""
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
    cached_messages = messages
    if messages:
        last = messages[-1]
        content = last.get("content") if isinstance(last, dict) else None
        stamped_content = None
        if isinstance(content, str) and content:
            # Plain-string content can't carry cache_control; wrap it into the
            # semantically identical single text block so it can. Only the
            # request body changes shape — the caller's history keeps the str.
            stamped_content = [{
                "type": "text", "text": content,
                "cache_control": {"type": "ephemeral"},
            }]
        elif isinstance(content, list) and content and isinstance(content[-1], dict):
            # Stamp (or re-stamp — idempotent, never a second breakpoint) the
            # last block. tool_result / text / image all accept cache_control.
            stamped_content = list(content)
            stamped_content[-1] = {
                **stamped_content[-1], "cache_control": {"type": "ephemeral"},
            }
        if stamped_content is not None:
            cached_messages = list(messages)
            cached_messages[-1] = {**last, "content": stamped_content}
    return cached_tools, cached_system, cached_messages


_USAGE_FIELDS = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
)


def _merge_usage(into, reported):
    """Fold an API-reported usage dict into ``into`` (in place), field by field.

    Only the four token-usage fields are read, and only integer values land —
    ``bool`` is an ``int`` subclass and must never be mistaken for a token
    count (same rule as the C1 agent-loop meter in
    ``synapse.cognitive.agent_loop``). Later reports overwrite earlier ones:
    ``message_start`` carries the input-side fields, ``message_delta`` the
    final cumulative ``output_tokens``."""
    if not isinstance(reported, dict):
        return
    for field in _USAGE_FIELDS:
        value = reported.get(field)
        if isinstance(value, int) and not isinstance(value, bool):
            into[field] = value


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

    @guarded_stream
    def stream(self, *, messages, tools, system, api_key, emit_token, should_abort):
        """Make one streaming API call, return ``(stop_reason, content_blocks)``."""
        # Reset the per-call usage record BEFORE the request so a failed call
        # can never surface the previous call's numbers as its own.
        self.last_usage = None
        cached_tools, cached_system, cached_messages = _with_prompt_cache(
            tools, system, _strip_internal_keys(messages))
        body: dict = {
            "model": stream_spec(self).model,
            "max_tokens": self._max_tokens,
            "stream": True,
            "messages": cached_messages,
            "tools": cached_tools,
        }
        if cached_system:
            body["system"] = cached_system

        payload = json.dumps(body).encode("utf-8")

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(_API_HOST, timeout=_HTTP_TIMEOUT, context=ctx)

        try:
            before_stream_send(self, api_key, payload, "https://" + _API_HOST + _API_PATH)
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
                raise ModelRequestFailed(
                    "Anthropic API error %s. %s" % (response.status, _read_error_detail(response))
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
            "usage": {},
        }

        event_type = None

        try:
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
                            logger.debug("Skipping non-JSON SSE data")
                    continue

                if line == "":
                    event_type = None
                    continue
        finally:
            # Publish observed usage even on abort or a mid-stream error —
            # those tokens were still billed. Empty ⇒ None: "not measured"
            # stays visible, never estimated (C1 discipline).
            self.last_usage = state["usage"] or None

        return state["stop_reason"], state["content_blocks"]

    def _handle_sse_event(self, event_type, data, state, emit_token):
        """Process a single SSE event, updating ``state`` in place."""

        if event_type == "message_start":
            # The one event that reports the input-side usage — including the
            # cache_read/cache_creation split that prices _with_prompt_cache.
            message = data.get("message")
            if isinstance(message, dict):
                self.reported_model = message.get("model")
                _merge_usage(state["usage"], message.get("usage"))

        elif event_type == "content_block_start":
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
                        logger.error("Failed to parse tool input JSON")
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
                self._stream_complete = True
                state["stop_reason"] = reason
            # message_delta carries cumulative usage at the TOP level (not
            # inside "delta") — the final output_tokens for the turn.
            _merge_usage(state["usage"], data.get("usage"))

        elif event_type == "message_stop":
            self._stream_complete = True

        elif event_type == "error":
            raise ModelRequestFailed("Anthropic stream error. " + _error_detail(data))
