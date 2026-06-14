"""Gemini provider — Anthropic-envelope streaming over the Gemini REST API.

Reaches ``generativelanguage.googleapis.com:443`` (``streamGenerateContent``,
SSE) with stdlib ``http.client`` — consistent with the Anthropic provider's raw
transport, so **no google-genai SDK / vendoring** is needed. Returns NORMALIZED
Anthropic-shaped content blocks via the ``gemini_translate`` layer
(functionDeclaration arg-repair + reconstruction), so the worker loop and tool
dispatch are unchanged and tool args stay faithful (kills the Leg-1 H3 loss).

Remote egress: ``generativelanguage.googleapis.com:443`` (docs/studio/EGRESS.md).
The API key leaves as the ``x-goog-api-key`` header (never inside the payload).
No Qt, no hou.
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import ssl

from . import gemini_translate as gt
from .base import StreamProvider

logger = logging.getLogger(__name__)

_API_HOST = "generativelanguage.googleapis.com"
_HTTP_TIMEOUT = 60


class GeminiProvider(StreamProvider):
    """Streams Gemini responses, translated to/from the Anthropic envelope."""

    id = "gemini"

    def __init__(self, model: str, max_tokens: int) -> None:
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model_identity(self) -> str:
        return self._model

    def resolve_key(self):
        for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            v = os.environ.get(var)
            if v and v.strip():
                return v.strip()
        return None

    def key_error_message(self) -> str:
        return (
            "No Gemini API key found. Set GEMINI_API_KEY at the SYSTEM level so "
            "Houdini inherits it, then relaunch Houdini:  "
            'setx GEMINI_API_KEY "AIza..."  '
            "(a terminal-scoped `set` won't carry into Houdini on Windows)."
        )

    # ------------------------------------------------------------------
    # Streaming request
    # ------------------------------------------------------------------

    def stream(self, *, messages, tools, system, api_key, emit_token, should_abort):
        # original Anthropic schemas, keyed by tool name, for arg reconstruction
        schema_by_name = {
            t.get("name", ""): (t.get("input_schema") or {}) for t in (tools or [])
        }

        body: dict = {
            "contents": gt.translate_messages(messages),
            "generationConfig": {"maxOutputTokens": self._max_tokens},
        }
        gtools = gt.translate_tools(tools)
        if gtools:
            body["tools"] = gtools
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}

        payload = json.dumps(body).encode("utf-8")
        path = "/v1beta/models/%s:streamGenerateContent?alt=sse" % self._model

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(_API_HOST, timeout=_HTTP_TIMEOUT, context=ctx)
        try:
            conn.request(
                "POST",
                path,
                body=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
            )
            response = conn.getresponse()
            if response.status != 200:
                error_body = response.read().decode("utf-8", errors="replace")
                raise RuntimeError("Gemini API error %s: %s" % (response.status, error_body))
            return self._parse_sse_stream(response, emit_token, should_abort, schema_by_name)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # SSE parser (Gemini: bare ``data:`` lines, GenerateContentResponse chunks)
    # ------------------------------------------------------------------

    def _iter_lines(self, response, should_abort):
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

    def _parse_sse_stream(self, response, emit_token, should_abort, schema_by_name):
        text_acc = []
        tool_blocks = []
        text_sig = None
        call_idx = 0

        for raw_line in self._iter_lines(response, should_abort):
            if should_abort():
                break
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                logger.debug("Skipping non-JSON Gemini SSE data: %s", data_str[:80])
                continue

            for cand in data.get("candidates", []) or []:
                content = cand.get("content", {}) or {}
                for part in content.get("parts", []) or []:
                    # thoughtSignature is a SIBLING of functionCall/text on the
                    # part. Gemini-3 thinking models REQUIRE it echoed back when
                    # the model's prior turn is replayed in history (the turn-2+
                    # 400). Capture it verbatim — it is an opaque handle.
                    sig = part.get("thoughtSignature")
                    text = part.get("text")
                    if text:
                        emit_token(text)
                        text_acc.append(text)
                        if sig:
                            text_sig = sig
                    fc = part.get("functionCall")
                    if fc:
                        name = fc.get("name", "")
                        args = fc.get("args", {}) or {}
                        fixed = gt.reconstruct_args(args, schema_by_name.get(name, {}))
                        block = {
                            "type": "tool_use",
                            # Gemini emits no stable call id we rely on — synthesize
                            # one so the tool_result round-trips on the next turn.
                            "id": "gemini-%s-%d" % (name, call_idx),
                            "name": name,
                            "input": fixed if isinstance(fixed, dict) else {},
                        }
                        if sig:
                            block["_gemini_thought_signature"] = sig
                        tool_blocks.append(block)
                        call_idx += 1

        blocks = []
        if text_acc:
            tblock = {"type": "text", "text": "".join(text_acc)}
            if text_sig:
                tblock["_gemini_thought_signature"] = text_sig
            blocks.append(tblock)
        blocks.extend(tool_blocks)
        # Gemini sets finishReason STOP even when returning calls; the presence of
        # tool calls is the signal the worker's loop needs.
        stop_reason = "tool_use" if tool_blocks else "end_turn"
        return stop_reason, blocks
