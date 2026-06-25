"""NVIDIA / Nemotron provider — Anthropic-envelope streaming over the
OpenAI-compatible chat-completions API.

Reaches an OpenAI-compatible endpoint (NVIDIA NIM cloud by default,
``integrate.api.nvidia.com/v1``) with stdlib ``http.client`` — consistent with
the Anthropic + Gemini providers' raw transport, so **no ``openai`` SDK** is
added to Houdini's Python. Returns NORMALIZED Anthropic-shaped content blocks
(``text`` / ``tool_use``) so the worker loop + tool dispatch are unchanged.

Endpoint-agnostic — the same OpenAI shape serves NVIDIA NIM cloud, OpenRouter,
Ollama cloud, or a self-hosted vLLM/SGLang/NIM. Pick the endpoint with
``NVIDIA_BASE_URL``; the model id selects the backend model.

Nemotron 'reasoning' models stream ``<think>...</think>`` as ordinary content.
Reasoning is OFF by default (a ``detailed thinking off`` system directive) —
the agent loop is tool-heavy and reasoning can exhaust ``max_tokens`` before the
tool call is emitted. A stateful filter strips any ``<think>`` that still leaks,
from BOTH the visible stream AND the returned text block (so replayed history
stays clean). ``NVIDIA_EMIT_REASONING=true`` requests reasoning ON (no filter).

Remote egress: ``integrate.api.nvidia.com:443`` by default (docs/studio/EGRESS.md).
The API key leaves as the ``Authorization: Bearer`` header, never in the payload.
No Qt, no hou. (Pattern ported from Comfy-Cozy ``agent/llm/_nvidia.py``.)
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import ssl
from urllib.parse import urlsplit

from .base import StreamProvider

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "integrate.api.nvidia.com"
_DEFAULT_BASE_PATH = "/v1"
_HTTP_TIMEOUT = 120

_REASONING_ON = "detailed thinking on"
_REASONING_OFF = "detailed thinking off"


def _emit_reasoning() -> bool:
    return os.environ.get("NVIDIA_EMIT_REASONING", "").strip().lower() in (
        "1", "true", "yes", "on")


def _endpoint():
    """(scheme, host, request_path) for the chat-completions call, honouring
    ``NVIDIA_BASE_URL`` (default NVIDIA NIM cloud). The scheme is preserved so a
    plaintext self-hosted endpoint (``http://localhost:8000``) connects over HTTP,
    not TLS. An all-slash path (``https://host/``) collapses to the ``/v1``
    default instead of dropping it."""
    base = os.environ.get("NVIDIA_BASE_URL", "").strip()
    if not base:
        return "https", _DEFAULT_HOST, _DEFAULT_BASE_PATH + "/chat/completions"
    parts = urlsplit(base if "//" in base else "https://" + base)
    scheme = parts.scheme or "https"
    host = parts.netloc or _DEFAULT_HOST
    # rstrip FIRST so '/' collapses to '' → falls back to /v1 (a host-only base
    # with a trailing slash must not lose the version prefix).
    path = parts.path.rstrip("/") or _DEFAULT_BASE_PATH
    return scheme, host, path + "/chat/completions"


class _ThinkFilter:
    """Strip ``<think>...</think>`` spans from a streamed text sequence. Stateful
    across chunks (a tag can straddle a chunk boundary). ``feed`` returns the
    visible remainder; reasoning text is dropped entirely."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self._in_think = False
        self._buf = ""

    def feed(self, text: str) -> str:
        self._buf += text
        out = []
        while self._buf:
            if not self._in_think:
                i = self._buf.find(self.OPEN)
                if i == -1:
                    keep = self._tail_len(self._buf, self.OPEN)
                    out.append(self._buf[: len(self._buf) - keep])
                    self._buf = self._buf[len(self._buf) - keep:]
                    break
                out.append(self._buf[:i])
                self._buf = self._buf[i + len(self.OPEN):]
                self._in_think = True
            else:
                j = self._buf.find(self.CLOSE)
                if j == -1:
                    keep = self._tail_len(self._buf, self.CLOSE)
                    self._buf = self._buf[len(self._buf) - keep:]
                    break
                self._buf = self._buf[j + len(self.CLOSE):]
                self._in_think = False
        return "".join(out)

    @staticmethod
    def _tail_len(s: str, tag: str) -> int:
        """Length of the longest suffix of ``s`` that is a prefix of ``tag``."""
        for k in range(min(len(s), len(tag) - 1), 0, -1):
            if tag.startswith(s[-k:]):
                return k
        return 0

    def flush(self):
        """At stream end: surface any buffered remainder that is NOT inside a
        think span (e.g. a held-back partial-tag tail like a literal '<thi' that
        never became '<think>'). If a ``<think>`` was left unclosed (the model was
        truncated mid-reasoning), the buffer is reasoning — dropped, and the
        caller is told via the returned ``unclosed`` flag. Idempotent."""
        unclosed = self._in_think
        out = "" if unclosed else self._buf
        self._buf = ""
        self._in_think = False
        return out, unclosed


def _to_openai_tools(tools):
    """Anthropic ``{name, description, input_schema}`` → OpenAI function tools."""
    out = []
    for tdef in tools or []:
        out.append({
            "type": "function",
            "function": {
                "name": tdef.get("name", ""),
                "description": tdef.get("description", ""),
                "parameters": tdef.get("input_schema") or {"type": "object", "properties": {}},
            },
        })
    return out


def _stringify(content):
    """Anthropic tool_result content → a plain string for an OpenAI tool message."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                parts.append(blk.get("text", "") if blk.get("type") == "text" else json.dumps(blk))
            else:
                parts.append(str(blk))
        return "\n".join(parts)
    return "" if content is None else str(content)


def _to_openai_messages(messages, system):
    """Anthropic messages → OpenAI ``messages`` (role/content + tool_calls /
    tool results), with the reasoning directive merged into the system turn."""
    directive = _REASONING_ON if _emit_reasoning() else _REASONING_OFF
    sys_text = (directive + ("\n" + system if system else ""))
    out = [{"role": "system", "content": sys_text}]

    for msg in messages or []:
        role = msg.get("role", "user")
        content = msg.get("content")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            out.append({"role": role, "content": "" if content is None else str(content)})
            continue

        text_parts, tool_calls, tool_results = [], [], []
        for blk in content:
            if not isinstance(blk, dict):
                text_parts.append(str(blk))
                continue
            btype = blk.get("type")
            if btype == "text":
                text_parts.append(blk.get("text", ""))
            elif btype == "tool_use":
                tool_calls.append({
                    "id": blk.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": blk.get("name", ""),
                        "arguments": json.dumps(blk.get("input", {}) or {}),
                    },
                })
            elif btype == "tool_result":
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": blk.get("tool_use_id", ""),
                    "content": _stringify(blk.get("content")),
                })

        if role == "assistant":
            entry = {"role": "assistant", "content": "".join(text_parts) or None}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            out.append(entry)
        else:  # user — tool_results become standalone tool messages
            if text_parts:
                out.append({"role": "user", "content": "".join(text_parts)})
            out.extend(tool_results)
    return out


class NemotronProvider(StreamProvider):
    """Streams NVIDIA Nemotron (OpenAI chat-completions) into the Anthropic envelope."""

    id = "nemotron"

    def __init__(self, model: str, max_tokens: int) -> None:
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model_identity(self) -> str:
        return self._model

    def resolve_key(self):
        # Ensure the project .env is loaded into os.environ. host.auth does this
        # at import (_load_dotenv), but a Nemotron-first session may never touch
        # the Anthropic path — so a key placed ONLY in <repo>/.env would be
        # missed without this. Import for its side-effect; never raise.
        try:
            import synapse.host.auth  # noqa: F401 — side-effect: loads <repo>/.env
        except Exception:
            pass
        v = os.environ.get("NVIDIA_API_KEY")
        if v and v.strip():
            return v.strip()
        # A self-hosted endpoint may need no key — only treat as unconfigured
        # when the default cloud host is in play.
        _scheme, host, _path = _endpoint()
        if host != _DEFAULT_HOST:
            return "not-needed"
        return None

    def key_error_message(self) -> str:
        return (
            "No NVIDIA API key found. Set NVIDIA_API_KEY (nvapi-...) at the SYSTEM "
            "level so Houdini inherits it, then relaunch Houdini:  "
            'setx NVIDIA_API_KEY "nvapi-..."  '
            "(a terminal-scoped `set` won't carry into Houdini on Windows). "
            "Point NVIDIA_BASE_URL at a self-hosted endpoint to skip the key."
        )

    # ------------------------------------------------------------------
    # Streaming request
    # ------------------------------------------------------------------

    def stream(self, *, messages, tools, system, api_key, emit_token, should_abort):
        body = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "stream": True,
            "messages": _to_openai_messages(messages, system),
        }
        otools = _to_openai_tools(tools)
        if otools:
            body["tools"] = otools

        payload = json.dumps(body).encode("utf-8")
        scheme, host, path = _endpoint()

        if scheme == "http":   # plaintext self-hosted (vLLM/Ollama default posture)
            conn = http.client.HTTPConnection(host, timeout=_HTTP_TIMEOUT)
        else:
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, timeout=_HTTP_TIMEOUT, context=ctx)
        try:
            headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
            if api_key and api_key != "not-needed":
                headers["Authorization"] = "Bearer %s" % api_key
            conn.request("POST", path, body=payload, headers=headers)
            response = conn.getresponse()
            if response.status != 200:
                error_body = response.read().decode("utf-8", errors="replace")
                raise RuntimeError("NVIDIA API error %s: %s" % (response.status, error_body))
            return self._parse_sse_stream(response, emit_token, should_abort)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # SSE parser (OpenAI chat-completions: data: {choices:[{delta:{...}}]})
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

    def _parse_sse_stream(self, response, emit_token, should_abort):
        tfilter = _ThinkFilter()
        text_acc = []
        tool_acc = {}   # index -> {"id","name","arguments"}
        finish = None

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
                logger.debug("Skipping non-JSON NVIDIA SSE data: %s", data_str[:80])
                continue

            for choice in data.get("choices", []) or []:
                delta = choice.get("delta", {}) or {}
                text = delta.get("content")
                if text:
                    visible = tfilter.feed(text)
                    if visible:
                        emit_token(visible)
                        text_acc.append(visible)
                for tc in delta.get("tool_calls", []) or []:
                    idx = tc.get("index", 0)
                    slot = tool_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function", {}) or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["arguments"] += fn["arguments"]
                if choice.get("finish_reason"):
                    finish = choice["finish_reason"]

        # Flush the filter: surface any held-back partial-tag tail; warn (don't
        # silently swallow) if the model left a <think> unclosed (truncation).
        tail, unclosed = tfilter.flush()
        if tail:
            emit_token(tail)
            text_acc.append(tail)
        if unclosed:
            logger.warning(
                "NVIDIA stream ended inside an unclosed <think> — reasoning was "
                "dropped and no visible answer followed (likely max_tokens truncation).")

        blocks = []
        text = "".join(text_acc)
        if text.strip():
            blocks.append({"type": "text", "text": text})
        for _idx, slot in sorted(tool_acc.items()):
            try:
                args = json.loads(slot["arguments"]) if slot["arguments"] else {}
            except json.JSONDecodeError:
                logger.error("Failed to parse NVIDIA tool args: %s", slot["arguments"][:200])
                args = {}
            blocks.append({
                "type": "tool_use",
                "id": slot["id"] or ("nemotron-%s-%d" % (slot["name"], _idx)),
                "name": slot["name"],
                "input": args if isinstance(args, dict) else {},
            })

        stop_reason = "tool_use" if tool_acc else (
            "end_turn" if finish in (None, "stop") else finish)
        return stop_reason, blocks
