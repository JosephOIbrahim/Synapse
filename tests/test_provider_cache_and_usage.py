"""Prompt-cache message breakpoint + SSE usage capture (latency lane A, C4 ranks 1+2).

Rank 1: ``_with_prompt_cache`` now ALSO stamps ``cache_control`` on the last
content block of the last message, so the accumulated conversation becomes a
cache READ on the next tool-loop iteration instead of an O(K^2) re-prefill.
Rank 2: the SSE handler captures the ``message_start`` / ``message_delta``
usage fields onto ``provider.last_usage`` — the only producer that can ever
price rank 1 (``cache_read_input_tokens`` was previously dropped on the floor).

Doubles are the same minimal shapes as ``tests/test_providers_floor.py``
(``tests`` is not a package, so this file stays self-contained).

**Every test states the condition under which it fails** (Constitution Law 1):

  last_block_stamped     fails if the message breakpoint is dropped, lands on
                         the wrong block, or mutates the caller's history.
  budget                 fails if a request ever carries more than 4
                         breakpoints (Anthropic hard limit → 400).
  string_unharmed        fails if a non-last string-content message is
                         altered by the stamping pass.
  string_last_wrapped    fails if a string last message is corrupted (text
                         lost) or if the caller's history stops being a str.
  empty_noop             fails if an empty message list breaks the request.
  existing_marker        fails if re-stamping an already-marked block counts
                         as a second breakpoint.
  original_breakpoints   fails if the tools/system breakpoints regress.
  usage_captured         fails if the message_start branch is removed, stops
                         reading a field, or message_delta's final
                         output_tokens no longer wins.
  usage_absent_is_none   fails if usage is ever ESTIMATED rather than
                         observed — "unmeasured" must stay visible.
  usage_no_stale_carry   fails if a usage-free call can surface the previous
                         call's numbers as its own.
  bool_rejected          fails if a truthy non-count leaks in as tokens.
  additive_default       fails if ``last_usage`` stops being an additive,
                         default-None surface (would force changes on the
                         gemini/nemotron/ollama providers).
"""
import json

from synapse.panel.providers.anthropic_provider import (
    AnthropicProvider,
    _with_prompt_cache,
)
from synapse.panel.providers.base import StreamProvider


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


def _count_breakpoints(tools, system, messages) -> int:
    """Count every ``cache_control`` marker in a request body's three spans."""
    count = 0
    for tool in tools or []:
        if "cache_control" in tool:
            count += 1
    if isinstance(system, list):
        count += sum(1 for b in system if "cache_control" in b)
    for msg in messages or []:
        content = msg.get("content")
        if isinstance(content, list):
            count += sum(
                1 for b in content
                if isinstance(b, dict) and "cache_control" in b
            )
    return count


_TOOLS = [
    {"name": "houdini_create_node", "input_schema": {"type": "object"}},
    {"name": "houdini_scene_info", "input_schema": {"type": "object"}},
]
_SYSTEM = "You are SYNAPSE."


def _multi_turn_messages():
    """A realistic worker-loop history: user str → assistant tool_use →
    user tool_results (the shape every iteration ≥ 2 sends)."""
    return [
        {"role": "user", "content": "build a sphere"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "ok"},
            {"type": "tool_use", "id": "t1", "name": "houdini_create_node",
             "input": {"parent": "/obj"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "created"},
            {"type": "tool_result", "tool_use_id": "t2", "content": "also done"},
        ]},
    ]


# --------------------------------------------------------- last_block_stamped --


def test_breakpoint_lands_on_last_block_of_last_message():
    messages = _multi_turn_messages()
    ct, cs, cm = _with_prompt_cache(_TOOLS, _SYSTEM, messages)

    last_content = cm[-1]["content"]
    assert last_content[-1]["cache_control"] == {"type": "ephemeral"}
    # only the LAST block of the LAST message — not its siblings
    assert "cache_control" not in last_content[0]
    # the stamped block is otherwise the same tool_result
    assert last_content[-1]["tool_use_id"] == "t2"
    assert last_content[-1]["content"] == "also done"

    # non-mutating: the caller's history (reused next iteration, possibly by
    # another provider) never carries a marker
    assert "cache_control" not in messages[-1]["content"][-1]
    assert "cache_control" not in messages[1]["content"][-1]


# ------------------------------------------------------------------- budget --


def test_total_breakpoints_stay_within_anthropic_limit_of_4():
    ct, cs, cm = _with_prompt_cache(_TOOLS, _SYSTEM, _multi_turn_messages())
    total = _count_breakpoints(ct, cs, cm)
    # exactly: last tool + system + last message block
    assert total == 3
    assert total <= 4


# --------------------------------------------------------- string_unharmed --


def test_string_content_messages_before_the_last_pass_through_unharmed():
    messages = _multi_turn_messages()
    _ct, _cs, cm = _with_prompt_cache(_TOOLS, _SYSTEM, messages)
    assert cm[0] == {"role": "user", "content": "build a sphere"}
    assert isinstance(cm[0]["content"], str)
    # the assistant turn is untouched too
    assert cm[1] == messages[1]


# ----------------------------------------------------- string_last_wrapped --


def test_string_last_message_is_wrapped_into_an_equivalent_text_block():
    """Iteration 1 sends the user prompt as a plain str. A str cannot carry
    cache_control, so the request body wraps it into the semantically
    identical single text block — text preserved verbatim, marker attached,
    caller's history still the original str."""
    messages = [{"role": "user", "content": "build a sphere"}]
    _ct, _cs, cm = _with_prompt_cache(_TOOLS, _SYSTEM, messages)
    assert cm[-1]["content"] == [{
        "type": "text", "text": "build a sphere",
        "cache_control": {"type": "ephemeral"},
    }]
    assert cm[-1]["role"] == "user"
    # caller unharmed
    assert messages[-1]["content"] == "build a sphere"


# --------------------------------------------------------------- empty_noop --


def test_empty_messages_list_is_a_noop():
    ct, cs, cm = _with_prompt_cache(_TOOLS, _SYSTEM, [])
    assert cm == []
    # the static-prefix breakpoints still stamp
    assert _count_breakpoints(ct, cs, cm) == 2


# ---------------------------------------------------------- existing_marker --


def test_block_already_carrying_cache_control_is_not_double_counted():
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "hi",
         "cache_control": {"type": "ephemeral"}},
    ]}]
    ct, cs, cm = _with_prompt_cache(_TOOLS, _SYSTEM, messages)
    assert cm[-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert _count_breakpoints(ct, cs, cm) == 3  # not 4: re-stamp is idempotent


# ----------------------------------------------------- original_breakpoints --


def test_single_message_request_still_carries_the_original_breakpoints():
    """No-regression: the pre-existing static-prefix breakpoints (last tool +
    system prompt) survive the messages half exactly as before."""
    ct, cs, cm = _with_prompt_cache(
        _TOOLS, _SYSTEM,
        [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
    )
    assert ct[-1]["cache_control"] == {"type": "ephemeral"}
    assert all("cache_control" not in t for t in ct[:-1])
    assert cs == [{
        "type": "text", "text": _SYSTEM,
        "cache_control": {"type": "ephemeral"},
    }]
    # inputs not mutated
    assert all("cache_control" not in t for t in _TOOLS)


# ------------------------------------------------------------ usage_captured --


def test_usage_captured_from_message_start_and_message_delta():
    """The four usage fields land on ``provider.last_usage``;
    ``message_delta``'s cumulative output_tokens (top-level ``usage``, not
    inside ``delta``) overwrites message_start's placeholder. The
    ``(stop_reason, content_blocks)`` return contract is untouched."""
    prov = AnthropicProvider(model="claude-sonnet-4-6", max_tokens=4096)
    tokens: list = []
    stream = _sse([
        ("message_start", {"message": {"usage": {
            "input_tokens": 3571,
            "cache_read_input_tokens": 6656,
            "cache_creation_input_tokens": 120,
            "output_tokens": 2,
        }}}),
        ("content_block_start", {"index": 0, "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"index": 0, "delta": {"type": "text_delta", "text": "done"}}),
        ("content_block_stop", {"index": 0}),
        ("message_delta", {"delta": {"stop_reason": "end_turn"},
                           "usage": {"output_tokens": 727}}),
        ("message_stop", {}),
    ])

    stop_reason, blocks = prov._parse_sse_stream(
        _FakeResponse(stream), emit_token=tokens.append, should_abort=lambda: False)

    assert stop_reason == "end_turn"
    assert tokens == ["done"]
    assert blocks == [{"type": "text", "text": "done"}]
    assert prov.last_usage == {
        "input_tokens": 3571,
        "cache_read_input_tokens": 6656,
        "cache_creation_input_tokens": 120,
        "output_tokens": 727,  # message_delta final wins over message_start's 2
    }


# -------------------------------------------------------- usage_absent_is_none --


def test_stream_without_usage_leaves_last_usage_none():
    prov = AnthropicProvider(model="m", max_tokens=10)
    stream = _sse([
        ("content_block_start", {"content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"delta": {"type": "text_delta", "text": "x"}}),
        ("content_block_stop", {}),
        ("message_delta", {"delta": {"stop_reason": "end_turn"}}),
        ("message_stop", {}),
    ])
    prov._parse_sse_stream(
        _FakeResponse(stream), emit_token=lambda t: None, should_abort=lambda: False)
    assert prov.last_usage is None


# ------------------------------------------------------- usage_no_stale_carry --


def test_usage_free_parse_does_not_surface_the_previous_calls_usage():
    prov = AnthropicProvider(model="m", max_tokens=10)
    with_usage = _sse([
        ("message_start", {"message": {"usage": {"input_tokens": 9, "output_tokens": 1}}}),
        ("message_delta", {"delta": {"stop_reason": "end_turn"}}),
        ("message_stop", {}),
    ])
    prov._parse_sse_stream(
        _FakeResponse(with_usage), emit_token=lambda t: None, should_abort=lambda: False)
    assert prov.last_usage == {"input_tokens": 9, "output_tokens": 1}

    without_usage = _sse([
        ("message_delta", {"delta": {"stop_reason": "end_turn"}}),
        ("message_stop", {}),
    ])
    prov._parse_sse_stream(
        _FakeResponse(without_usage), emit_token=lambda t: None, should_abort=lambda: False)
    assert prov.last_usage is None


# ------------------------------------------------------------- bool_rejected --


def test_bool_is_not_mistaken_for_a_token_count():
    """``bool`` is an ``int`` subclass — a provider bug sending ``True`` must
    not land in the record as 1 token (same rule as the C1 agent-loop meter)."""
    prov = AnthropicProvider(model="m", max_tokens=10)
    stream = _sse([
        ("message_start", {"message": {"usage": {
            "input_tokens": True, "output_tokens": 5}}}),
        ("message_delta", {"delta": {"stop_reason": "end_turn"}}),
        ("message_stop", {}),
    ])
    prov._parse_sse_stream(
        _FakeResponse(stream), emit_token=lambda t: None, should_abort=lambda: False)
    assert prov.last_usage == {"output_tokens": 5}


# ---------------------------------------------------------- additive_default --


def test_last_usage_is_an_additive_default_none_surface():
    """Providers that don't capture usage (gemini/nemotron/ollama/custom)
    inherit ``None`` without any code change — the surface is additive to the
    ``(stop_reason, content_blocks)`` contract, never part of the tuple."""
    assert StreamProvider.last_usage is None

    class _Untouched(StreamProvider):
        id = "untouched"

    assert _Untouched().last_usage is None
