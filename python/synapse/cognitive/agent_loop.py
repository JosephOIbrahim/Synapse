"""Anthropic Agent SDK turn runner — Sprint 3 Spike 2 Phase 2.

Runs one multi-iteration agent conversation to completion, dispatching
tool calls through a ``Dispatcher`` and honouring a cooperative
``threading.Event`` cancel flag at every API yield and every tool
dispatch. The Crucible protocol's resilience claims are rooted here:
this is where ``hou.ObjectWasDeleted`` routes through
``AgentToolError`` back into the conversation so the LLM can rewrite
its approach instead of silently retrying a stale pointer.

Scope boundary — why this lives in ``synapse.cognitive.*``
----------------------------------------------------------
The Anthropic SDK is a cognitive-layer concern (connecting to a
model, managing conversation state, dispatching tools). It has no
Houdini dependency. The Dispatcher's ``main_thread_executor`` is the
only thing that touches Houdini, and that's injected at Dispatcher
construction time — not imported here. Therefore: zero ``hou``
imports, composes across DCCs, enforced by the cognitive-boundary
lint.

Cancel semantics
----------------
The ``cancel_event`` is checked at three places:

  1. Before each ``client.messages.create`` call. An agent cancelled
     between turns exits clean with status ``"cancelled"``.
  2. Immediately after each response returns. If cancellation arrived
     while the network was yielding, the response content is
     discarded without tool dispatch.
  3. Between every tool dispatch inside a response. If the artist
     presses ESC mid-batch, remaining tools in that response are
     skipped.

The cancel never raises — it's cooperative. Callers see status
``"cancelled"`` and the partial conversation history to inspect what
happened.

``hou.ObjectWasDeleted`` and friends
------------------------------------
The Dispatcher already catches all tool exceptions and returns
``AgentToolError`` values (never raises). This module serializes the
error into the ``tool_result`` content for the next turn, so the LLM
sees structured error data and can re-inspect before retrying.
This is the "no silent retry on stale pointer" rubric line from the
SPRINT3 Crucible pass criteria.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from synapse.cognitive.dispatcher import AgentToolError, Dispatcher

logger = logging.getLogger(__name__)


DEFAULT_MODEL: str = "claude-sonnet-4-5"
"""Default Anthropic model. Override via AgentTurnConfig(model=...)."""

DEFAULT_MAX_TOKENS: int = 1024
"""Default per-response token ceiling."""

DEFAULT_MAX_ITERATIONS: int = 8
"""Default cap on API round-trips per turn. Prevents a runaway
tool-use loop. SPRINT3 Crucible: a well-behaved agent should recover
from ``hou.ObjectWasDeleted`` within 2–3 iterations; the cap protects
against pathological loops."""


# -- Result / status constants ----------------------------------------------

STATUS_COMPLETE: str = "complete"
"""Agent hit stop_reason == 'end_turn'. Normal exit."""

STATUS_CANCELLED: str = "cancelled"
"""cancel_event was set at a yield point. Partial history returned."""

STATUS_API_ERROR: str = "api_error"
"""Anthropic API call raised. Network, auth, rate limit, or SDK bug."""

STATUS_MAX_ITERATIONS: str = "max_iterations"
"""Loop hit ``max_iterations`` before stop_reason == 'end_turn'.
Usually means the agent is thrashing — inspect the history."""

STATUS_UNKNOWN_STOP: str = "unknown_stop_reason"
"""Anthropic returned a stop_reason this loop doesn't handle."""


@dataclass(frozen=True)
class AgentTurnConfig:
    """Configuration for one ``run_turn`` call.

    Attributes:
        model: Anthropic model identifier.
        max_tokens: Max tokens per response.
        max_iterations: Max API round-trips per turn.
        system: System prompt. Empty string ⇒ no system prompt.
    """

    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    system: str = ""


@dataclass
class AgentTurnResult:
    """Outcome of one ``run_turn`` call.

    Attributes:
        status: One of the ``STATUS_*`` constants.
        iterations: Number of API round-trips that completed.
        messages: Full conversation in Anthropic's messages shape.
        tool_calls_made: Count of tool dispatches attempted.
        tool_errors: ``AgentToolError`` values that came back from
            tool dispatches during this turn. Kept as a separate list
            for easy Crucible inspection — the messages list has the
            serialized form.
        error: Free-form error string populated when status in
            {api_error, unknown_stop_reason}. Empty otherwise.
    """

    status: str
    iterations: int = 0
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls_made: int = 0
    tool_errors: List[AgentToolError] = field(default_factory=list)
    error: str = ""


# -- Internal helpers -------------------------------------------------------


def _serialize_tool_output(output: Any) -> str:
    """Serialize tool output to a string for the Anthropic tool_result content.

    ``AgentToolError`` is converted via its ``.to_dict()`` to preserve
    structured context. Plain dicts serialize as sorted-key JSON for
    determinism. Anything else is best-effort stringified.
    """
    if isinstance(output, AgentToolError):
        return json.dumps(output.to_dict(), sort_keys=True)
    if isinstance(output, dict):
        return json.dumps(output, sort_keys=True)
    return str(output)


def _extract_text_blocks(content: Any) -> List[Dict[str, Any]]:
    """Normalize Anthropic response ``content`` into plain dicts.

    The SDK returns pydantic-like objects; we round-trip through dict
    so the conversation history is JSON-serializable.
    """
    normalized: List[Dict[str, Any]] = []
    for block in content:
        if hasattr(block, "model_dump"):
            normalized.append(block.model_dump())
        elif isinstance(block, dict):
            normalized.append(dict(block))
        else:
            # Last-resort: wrap as a text block with the repr.
            normalized.append({"type": "text", "text": repr(block)})
    return normalized


# -- Public entry point -----------------------------------------------------


def run_turn(
    client: Any,
    dispatcher: Dispatcher,
    user_prompt: str,
    *,
    cancel_event: Optional[threading.Event] = None,
    config: Optional[AgentTurnConfig] = None,
) -> AgentTurnResult:
    """Execute one multi-iteration agent turn.

    Args:
        client: Anthropic client instance (``anthropic.Anthropic`` or a
            test double with a ``messages.create`` method).
        dispatcher: Dispatcher the agent will route tool calls through.
        user_prompt: Initial user message content.
        cancel_event: Optional ``threading.Event``. When set, the loop
            exits at the next yield point with
            ``status=STATUS_CANCELLED``. A ``None`` value disables
            cancellation (tests / trivial cases).
        config: Optional configuration overrides. ``None`` uses
            ``AgentTurnConfig()`` defaults.

    Returns:
        ``AgentTurnResult`` with status, conversation history, and
        any tool errors observed. Never raises on expected failure
        modes — API errors and unknown stop reasons come back as
        status values, not exceptions.
    """
    cfg = config or AgentTurnConfig()
    result = AgentTurnResult(status=STATUS_COMPLETE)  # overwrite below

    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": user_prompt}
    ]
    result.messages = messages

    def _cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    for iteration in range(cfg.max_iterations):
        # -- Cancel check #1: before the API yield ------------------
        if _cancelled():
            result.status = STATUS_CANCELLED
            result.iterations = iteration
            return result

        create_kwargs: Dict[str, Any] = {
            "model": cfg.model,
            "max_tokens": cfg.max_tokens,
            "messages": messages,
        }
        if cfg.system:
            create_kwargs["system"] = cfg.system
        schemas = dispatcher.tool_schemas()
        if schemas:
            create_kwargs["tools"] = schemas

        # -- The yield itself ---------------------------------------
        try:
            response = client.messages.create(**create_kwargs)
        except BaseException as exc:  # noqa: BLE001 - any SDK / network err
            result.status = STATUS_API_ERROR
            result.iterations = iteration
            result.error = f"{type(exc).__name__}: {exc}"
            logger.exception("Agent-loop API call raised")
            return result

        # -- Cancel check #2: immediately after the yield -----------
        if _cancelled():
            result.status = STATUS_CANCELLED
            result.iterations = iteration + 1
            return result

        # Record assistant response
        content_blocks = _extract_text_blocks(response.content)
        messages.append({"role": "assistant", "content": content_blocks})

        stop_reason = getattr(response, "stop_reason", None)

        if stop_reason == "end_turn" or stop_reason == "stop_sequence":
            result.status = STATUS_COMPLETE
            result.iterations = iteration + 1
            return result

        if stop_reason != "tool_use":
            result.status = STATUS_UNKNOWN_STOP
            result.iterations = iteration + 1
            result.error = f"Unhandled stop_reason: {stop_reason!r}"
            return result

        # -- Tool-use path -------------------------------------------
        tool_results: List[Dict[str, Any]] = []
        for block in content_blocks:
            if block.get("type") != "tool_use":
                continue

            # -- Cancel check #3: before each tool dispatch --------
            if _cancelled():
                result.status = STATUS_CANCELLED
                result.iterations = iteration + 1
                # Messages already carry the assistant turn; tool
                # results are NOT appended because the conversation
                # was cut before the tools ran.
                return result

            tool_name = block.get("name", "")
            tool_input = block.get("input") or {}
            tool_use_id = block.get("id", "")

            dispatched = dispatcher.execute(tool_name, tool_input)
            result.tool_calls_made += 1
            if isinstance(dispatched, AgentToolError):
                result.tool_errors.append(dispatched)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": _serialize_tool_output(dispatched),
            })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Next iteration — loop continues through cancel check #1.

    # Loop budget exhausted
    result.status = STATUS_MAX_ITERATIONS
    result.iterations = cfg.max_iterations
    return result
