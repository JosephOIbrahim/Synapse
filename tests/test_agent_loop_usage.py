"""Per-turn token-usage capture in ``run_turn`` (leg C1).

Before C1 the agent loop held the response object carrying ``.usage`` at the
``messages.create`` yield and threw it away — there was no per-turn token
accounting anywhere in non-vendor code. These tests pin the reader that closes
that gap.

**Every test states the condition under which it fails** (Constitution Law 1):

  captured            fails if the ``_record_usage`` call is removed from
                      ``run_turn``, or if it stops reading a field.
  absent_stays_empty  fails if usage is ever ESTIMATED rather than observed —
                      the whole point is that "unmeasured" stays visible.
  per_iteration       fails if only the final round-trip is recorded.
  cancelled           fails if the capture is moved below the post-yield
                      cancel check, which would under-report a turn the
                      account was still billed for.
  bool_rejected       fails if a truthy non-count leaks in as a token value.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from synapse.cognitive.agent_loop import (
    AgentTurnConfig,
    AgentTurnResult,
    STATUS_CANCELLED,
    STATUS_COMPLETE,
    run_turn,
)
from synapse.cognitive.dispatcher import Dispatcher


# Local doubles, deliberately the SAME minimal shape as the established ones in
# tests/test_agent_loop.py (content + stop_reason only). ``tests`` is not a
# package, so this file stays self-contained rather than importing across it.


class _MockBlock:
    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    def model_dump(self) -> Dict[str, Any]:
        return dict(self._data)


class _MockResponse:
    """Minimal stand-in for ``anthropic.types.Message`` — NO ``.usage``."""

    def __init__(self, content: List[Dict[str, Any]], stop_reason: str) -> None:
        self.content = [_MockBlock(b) for b in content]
        self.stop_reason = stop_reason


class _MockMessagesAPI:
    def __init__(self, script: List[Any]) -> None:
        self._script = list(script)
        self.create_calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.create_calls.append(kwargs)
        if not self._script:
            raise AssertionError("Mock Anthropic script exhausted")
        return self._script.pop(0)


class _MockClient:
    def __init__(self, script: List[Any]) -> None:
        self.messages = _MockMessagesAPI(script)


class _Usage:
    """Stand-in for ``anthropic.types.Usage``."""

    def __init__(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: Optional[int] = None,
        cache_creation_input_tokens: Optional[int] = None,
    ) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read_input_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens


class _UsageResponse(_MockResponse):
    """``_MockResponse`` plus the ``.usage`` a real Message carries."""

    def __init__(
        self, content: List[Dict[str, Any]], stop_reason: str, usage: Any
    ) -> None:
        super().__init__(content, stop_reason)
        self.usage = usage


@pytest.fixture
def bare() -> Dispatcher:
    return Dispatcher(is_testing=True)


def _text(msg: str) -> List[Dict[str, Any]]:
    return [{"type": "text", "text": msg}]


# --------------------------------------------------------------- captured --


def test_usage_is_captured_when_the_response_reports_it(bare: Dispatcher) -> None:
    client = _MockClient(
        [_UsageResponse(_text("done"), "end_turn", _Usage(1234, 56))]
    )
    result = run_turn(client, bare, "hello")

    assert result.status == STATUS_COMPLETE
    assert result.usage == [{"input_tokens": 1234, "output_tokens": 56}]
    assert result.total_tokens() == 1290


def test_cache_fields_are_captured_when_present(bare: Dispatcher) -> None:
    """The cache fields are the ONLY evidence that prompt caching saves
    anything. ``_with_prompt_cache`` asserts a specific saving with no
    instrument; this is the field that could ever settle it."""
    client = _MockClient(
        [
            _UsageResponse(
                _text("done"),
                "end_turn",
                _Usage(10, 2, cache_read_input_tokens=900,
                       cache_creation_input_tokens=17),
            )
        ]
    )
    result = run_turn(client, bare, "hello")

    assert result.usage[0]["cache_read_input_tokens"] == 900
    assert result.usage[0]["cache_creation_input_tokens"] == 17
    # total_tokens counts billed input+output only, never cache fields.
    assert result.total_tokens() == 12


def test_dict_usage_is_accepted(bare: Dispatcher) -> None:
    """A non-SDK client may report usage as a plain dict."""
    client = _MockClient(
        [
            _UsageResponse(
                _text("done"), "end_turn",
                {"input_tokens": 7, "output_tokens": 3},
            )
        ]
    )
    result = run_turn(client, bare, "hello")
    assert result.usage == [{"input_tokens": 7, "output_tokens": 3}]


# ----------------------------------------------------- absent stays empty --


def test_response_without_usage_records_nothing(bare: Dispatcher) -> None:
    """The pre-existing doubles carry only ``.content`` and ``.stop_reason``.

    Two things must hold: the loop must not raise, and it must not invent a
    number. An empty list is the honest record of "not measured"."""
    client = _MockClient([_MockResponse(_text("done"), "end_turn")])
    result = run_turn(client, bare, "hello")

    assert result.status == STATUS_COMPLETE
    assert result.usage == []
    assert result.total_tokens() == 0


def test_usage_none_records_nothing(bare: Dispatcher) -> None:
    client = _MockClient([_UsageResponse(_text("done"), "end_turn", None)])
    result = run_turn(client, bare, "hello")
    assert result.usage == []


def test_bool_is_not_mistaken_for_a_token_count(bare: Dispatcher) -> None:
    """``bool`` is an ``int`` subclass. A provider sending ``True`` must not
    land in the ledger as 1 token."""
    client = _MockClient(
        [
            _UsageResponse(
                _text("done"), "end_turn",
                {"input_tokens": True, "output_tokens": 5},
            )
        ]
    )
    result = run_turn(client, bare, "hello")
    assert result.usage == [{"output_tokens": 5}]


# ---------------------------------------------------------- per iteration --


def test_usage_accumulates_one_record_per_round_trip() -> None:
    """A tool-use turn makes two API round-trips. Both are billed, so both
    must appear — a meter that keeps only the last under-reports the turn."""
    d = Dispatcher(is_testing=True)
    d.register(
        "echo",
        lambda **kw: {"echoed": kw},
        schema={
            "description": "Echoes kwargs back.",
            "input_schema": {"type": "object", "properties": {}},
        },
    )

    client = _MockClient(
        [
            _UsageResponse(
                [{"type": "tool_use", "id": "t1", "name": "echo", "input": {}}],
                "tool_use",
                _Usage(100, 10),
            ),
            _UsageResponse(_text("done"), "end_turn", _Usage(200, 20)),
        ]
    )
    result = run_turn(client, d, "use the tool")

    assert result.status == STATUS_COMPLETE
    assert result.iterations == 2
    assert result.usage == [
        {"input_tokens": 100, "output_tokens": 10},
        {"input_tokens": 200, "output_tokens": 20},
    ]
    assert result.total_tokens() == 330


# --------------------------------------------------------------- cancelled --


def test_usage_of_a_completed_yield_survives_cancellation(bare: Dispatcher) -> None:
    """Cancelling after the yield does not refund it.

    The event is set by the mock at the moment the API call returns, so the
    loop cancels at the very next check. The round-trip still happened and
    still cost tokens; the receipt must say so."""
    import threading

    cancel = threading.Event()

    class _CancellingAPI:
        def __init__(self, response: Any) -> None:
            self._response = response

        def create(self, **_kwargs: Any) -> Any:
            cancel.set()  # cancelled *after* the yield completed
            return self._response

    class _Client:
        def __init__(self, response: Any) -> None:
            self.messages = _CancellingAPI(response)

    client = _Client(_UsageResponse(_text("hi"), "end_turn", _Usage(42, 7)))
    result = run_turn(client, bare, "hello", cancel_event=cancel)

    assert result.status == STATUS_CANCELLED
    assert result.usage == [{"input_tokens": 42, "output_tokens": 7}]


# ------------------------------------------------------------- the default --


def test_fresh_result_has_an_empty_usage_list() -> None:
    """Default must be a fresh list, not a shared mutable."""
    a = AgentTurnResult(status=STATUS_COMPLETE)
    b = AgentTurnResult(status=STATUS_COMPLETE)
    a.usage.append({"input_tokens": 1})
    assert b.usage == []
    assert b.total_tokens() == 0
