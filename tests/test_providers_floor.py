"""Floor guard for the panel provider extraction (FORGE: multi-provider).

The Anthropic provider is a faithful move of ``claude_worker``'s SSE transport.
This pins the SSE state machine: a canned Anthropic stream must parse to the same
``(stop_reason, content_blocks)`` and emit the same text tokens, with nested tool
args preserved. Qt-free, hou-free, network-free.
"""
import json

from synapse.panel.providers.anthropic_provider import AnthropicProvider, _API_HOST


class _FakeResponse:
    """Minimal http.client.HTTPResponse stand-in: ``.read(n)`` drains a buffer."""

    def __init__(self, data: bytes):
        self._buf = data

    def read(self, n: int = 4096) -> bytes:
        chunk, self._buf = self._buf[:n], self._buf[n:]
        return chunk


def _sse(events) -> bytes:
    """Render ``[(event, data_dict), ...]`` into an Anthropic SSE byte stream."""
    out = []
    for ev, data in events:
        out.append("event: %s" % ev)
        out.append("data: %s" % json.dumps(data))
        out.append("")  # blank line terminates the event
    return ("\n".join(out) + "\n").encode("utf-8")


def test_anthropic_provider_parses_text_and_tool_use_stream():
    prov = AnthropicProvider(model="claude-sonnet-4-6", max_tokens=4096)
    tokens: list = []
    stream = _sse([
        ("content_block_start", {"index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": "Hello "}}),
        ("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": "world"}}),
        ("content_block_stop", {"index": 0}),
        ("content_block_start", {"index": 1, "content_block": {
            "type": "tool_use", "id": "toolu_1", "name": "houdini_create_node", "input": {}}}),
        ("content_block_delta", {"index": 1, "delta": {
            "type": "input_json_delta", "partial_json": '{"parent":"/obj",'}}),
        ("content_block_delta", {"index": 1, "delta": {
            "type": "input_json_delta", "partial_json": '"type":"geo"}'}}),
        ("content_block_stop", {"index": 1}),
        ("message_delta", {"delta": {"stop_reason": "tool_use"}}),
        ("message_stop", {}),
    ])

    stop_reason, blocks = prov._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)

    assert stop_reason == "tool_use"
    assert tokens == ["Hello ", "world"]
    assert len(blocks) == 2
    assert blocks[0] == {"type": "text", "text": "Hello world"}
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["id"] == "toolu_1"
    assert blocks[1]["name"] == "houdini_create_node"
    # nested tool args reconstructed faithfully (the contract the loop depends on)
    assert blocks[1]["input"] == {"parent": "/obj", "type": "geo"}


def test_anthropic_provider_end_turn_no_tools():
    prov = AnthropicProvider(model="m", max_tokens=10)
    tokens: list = []
    stream = _sse([
        ("content_block_start", {"content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"delta": {"type": "text_delta", "text": "done"}}),
        ("content_block_stop", {}),
        ("message_delta", {"delta": {"stop_reason": "end_turn"}}),
        ("message_stop", {}),
    ])
    stop_reason, blocks = prov._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)
    assert stop_reason == "end_turn"
    assert tokens == ["done"]
    assert blocks == [{"type": "text", "text": "done"}]


def test_anthropic_provider_abort_stops_parsing():
    prov = AnthropicProvider(model="m", max_tokens=10)
    stream = _sse([("content_block_delta", {"delta": {"type": "text_delta", "text": "x"}})])
    stop_reason, blocks = prov._parse_sse_stream(
        _FakeResponse(stream), emit_token=lambda t: None, should_abort=lambda: True)
    assert blocks == []  # should_abort short-circuits the line iterator


def test_anthropic_provider_endpoint_is_anthropic():
    assert _API_HOST == "api.anthropic.com"


def test_worker_default_provider_is_claude_floor():
    """The worker, with no provider injected, builds the Anthropic floor — the
    zero-behaviour-change default. (Registry is the single model-id source.)"""
    from synapse.panel.providers.registry import build_provider, ANTHROPIC_MODEL
    prov = build_provider()
    assert prov.id == "claude"
    assert prov.model_identity == ANTHROPIC_MODEL


def test_anthropic_strips_gemini_internal_keys():
    """A Gemini-sourced tool_use block carries _gemini_thought_signature; the
    Claude body must never see it (Anthropic 400s on unknown fields). The strip
    is non-mutating — the worker reuses the history for the next Gemini turn."""
    from synapse.panel.providers.anthropic_provider import _strip_internal_keys
    messages = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "x", "name": "t", "input": {},
             "_gemini_thought_signature": "SIG"},
        ]},
        {"role": "user", "content": "hi"},
    ]
    out = _strip_internal_keys(messages)
    block = out[0]["content"][0]
    assert "_gemini_thought_signature" not in block
    assert block["type"] == "tool_use" and block["name"] == "t"
    assert out[1]["content"] == "hi"                       # str content untouched
    # non-mutating: the caller's history still carries the signature
    assert "_gemini_thought_signature" in messages[0]["content"][0]
