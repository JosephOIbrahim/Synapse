"""Floor guard for the NVIDIA / Nemotron panel provider.

Pins the OpenAI-compatible SSE state machine + the Anthropic<->OpenAI
translation + the <think> reasoning filter. A canned OpenAI chat-completions
stream must parse to the right ``(stop_reason, content_blocks)`` and emit the
right visible tokens, with reasoning stripped and nested tool args preserved.
Qt-free, hou-free, network-free.
"""
import json

from synapse.panel.providers.nemotron_provider import (
    NemotronProvider,
    _ThinkFilter,
    _to_openai_messages,
    _to_openai_tools,
    _endpoint,
)


class _FakeResponse:
    """Minimal http.client.HTTPResponse stand-in: ``.read(n)`` drains a buffer."""

    def __init__(self, data: bytes):
        self._buf = data

    def read(self, n: int = 4096) -> bytes:
        chunk, self._buf = self._buf[:n], self._buf[n:]
        return chunk


def _sse(chunks) -> bytes:
    """Render a list of OpenAI chat-completions delta dicts into an SSE stream."""
    out = []
    for ch in chunks:
        out.append("data: %s" % json.dumps({"choices": [ch]}))
        out.append("")
    out.append("data: [DONE]")
    out.append("")
    return ("\n".join(out) + "\n").encode("utf-8")


def _prov():
    return NemotronProvider(model="nvidia/nemotron-3-super-120b-a12b", max_tokens=4096)


def test_parses_text_and_tool_use_stream():
    tokens = []
    stream = _sse([
        {"delta": {"content": "Hello "}, "finish_reason": None},
        {"delta": {"content": "world"}, "finish_reason": None},
        {"delta": {"tool_calls": [
            {"index": 0, "id": "call_1",
             "function": {"name": "houdini_create_node", "arguments": '{"parent":"/obj",'}}]},
         "finish_reason": None},
        {"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": '"type":"geo"}'}}]},
         "finish_reason": "tool_calls"},
    ])
    stop, blocks = _prov()._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)

    assert tokens == ["Hello ", "world"]
    assert stop == "tool_use"
    assert blocks[0] == {"type": "text", "text": "Hello world"}
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["id"] == "call_1"
    assert blocks[1]["name"] == "houdini_create_node"
    # nested tool args reconstructed from the streamed argument fragments
    assert blocks[1]["input"] == {"parent": "/obj", "type": "geo"}


def test_end_turn_no_tools():
    tokens = []
    stream = _sse([
        {"delta": {"content": "done"}, "finish_reason": "stop"},
    ])
    stop, blocks = _prov()._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)
    assert stop == "end_turn"
    assert tokens == ["done"]
    assert blocks == [{"type": "text", "text": "done"}]


def test_think_spans_are_stripped_from_stream_and_block():
    tokens = []
    stream = _sse([
        {"delta": {"content": "<think>secret "}, "finish_reason": None},
        {"delta": {"content": "reasoning</think>visible "}, "finish_reason": None},
        {"delta": {"content": "answer"}, "finish_reason": "stop"},
    ])
    stop, blocks = _prov()._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)
    # the reasoning never reaches the user OR the replayed history
    joined = "".join(tokens)
    assert "secret" not in joined and "reasoning" not in joined
    assert "".join(tokens) == "visible answer"
    assert blocks == [{"type": "text", "text": "visible answer"}]


def test_think_filter_handles_tag_split_across_chunks():
    f = _ThinkFilter()
    # the open tag straddles a chunk boundary
    assert f.feed("a<thi") == "a"
    assert f.feed("nk>hidden</th") == ""
    assert f.feed("ink>b") == "b"


def test_message_translation_to_openai():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "calling"},
            {"type": "tool_use", "id": "c1", "name": "t", "input": {"x": 1}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "c1", "content": "ok"},
        ]},
    ]
    out = _to_openai_messages(messages, system="be helpful")
    # reasoning directive merged into the system turn (OFF by default)
    assert out[0]["role"] == "system"
    assert out[0]["content"].startswith("detailed thinking off")
    assert "be helpful" in out[0]["content"]
    assert out[1] == {"role": "user", "content": "hi"}
    asst = out[2]
    assert asst["role"] == "assistant" and asst["content"] == "calling"
    assert asst["tool_calls"][0]["id"] == "c1"
    assert asst["tool_calls"][0]["function"]["name"] == "t"
    assert json.loads(asst["tool_calls"][0]["function"]["arguments"]) == {"x": 1}
    tool_msg = out[3]
    assert tool_msg == {"role": "tool", "tool_call_id": "c1", "content": "ok"}


def test_tool_translation_to_openai_function():
    tools = [{"name": "foo", "description": "d", "input_schema": {"type": "object", "properties": {}}}]
    out = _to_openai_tools(tools)
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "foo"
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_default_endpoint_is_nvidia_nim():
    scheme, host, path = _endpoint()
    assert scheme == "https"
    assert host == "integrate.api.nvidia.com"
    assert path == "/v1/chat/completions"


def test_registry_builds_nemotron():
    from synapse.panel.providers.registry import build_provider, NVIDIA_MODEL
    prov = build_provider("nemotron")
    assert prov.id == "nemotron"
    assert prov.model_identity == NVIDIA_MODEL


# -- endpoint / scheme robustness (NVIDIA_BASE_URL overrides) ----------------

def test_endpoint_variants(monkeypatch):
    cases = {
        "https://host/":           ("https", "host", "/v1/chat/completions"),
        "https://host/v1/":        ("https", "host", "/v1/chat/completions"),
        "http://localhost:8000":   ("http", "localhost:8000", "/v1/chat/completions"),
        "host/openai/v1":          ("https", "host", "/openai/v1/chat/completions"),
        "https://openrouter.ai/api/v1": ("https", "openrouter.ai", "/api/v1/chat/completions"),
    }
    for base, exp in cases.items():
        monkeypatch.setenv("NVIDIA_BASE_URL", base)
        assert _endpoint() == exp, "base %r" % base


def test_trailing_slash_keeps_v1_prefix(monkeypatch):
    # the regression: a host-only base with a trailing slash must NOT drop /v1
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/")
    scheme, host, path = _endpoint()
    assert path == "/v1/chat/completions"


# -- think-filter edge cases ------------------------------------------------

def test_unclosed_think_drops_reasoning_no_crash():
    tokens = []
    stream = _sse([
        {"delta": {"content": "<think>reasoning that never closes"}, "finish_reason": "length"},
    ])
    stop, blocks = _prov()._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)
    assert "".join(tokens) == ""        # reasoning never reaches the user
    assert blocks == []                  # no visible text block emitted
    assert stop == "length"             # finish_reason passed through


def test_think_filter_flush_returns_partial_tail():
    f = _ThinkFilter()
    # a literal '<thi' at stream end (never completed to '<think>') is real content
    assert f.feed("answer<thi") == "answer"
    tail, unclosed = f.flush()
    assert tail == "<thi" and unclosed is False


# -- parallel tool calls + scheme ------------------------------------------

def test_two_parallel_tool_calls():
    tokens = []
    stream = _sse([
        {"delta": {"tool_calls": [
            {"index": 0, "id": "c0", "function": {"name": "a", "arguments": '{"x":1}'}}]},
         "finish_reason": None},
        {"delta": {"tool_calls": [
            {"index": 1, "id": "c1", "function": {"name": "b", "arguments": '{"y":2}'}}]},
         "finish_reason": "tool_calls"},
    ])
    stop, blocks = _prov()._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)
    assert stop == "tool_use"
    tus = [b for b in blocks if b["type"] == "tool_use"]
    assert len(tus) == 2
    assert tus[0]["name"] == "a" and tus[0]["input"] == {"x": 1}
    assert tus[1]["name"] == "b" and tus[1]["input"] == {"y": 2}


# -- resolve_key (.env side-effect) -----------------------------------------

def test_resolve_key_reads_env(monkeypatch):
    import synapse.host.auth  # ensure _load_dotenv already ran (idempotent)
    monkeypatch.delenv("NVIDIA_BASE_URL", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "  nvapi-xyz  ")
    assert _prov().resolve_key() == "nvapi-xyz"


def test_resolve_key_none_on_default_host_without_key(monkeypatch):
    import synapse.host.auth  # noqa: F401
    monkeypatch.delenv("NVIDIA_BASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert _prov().resolve_key() is None


def test_resolve_key_self_host_needs_no_key(monkeypatch):
    import synapse.host.auth  # noqa: F401
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_BASE_URL", "http://localhost:8000")
    assert _prov().resolve_key() == "not-needed"
