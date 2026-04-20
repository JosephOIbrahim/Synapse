"""Dispatcher — pure-Python tool-call interface (Sprint 3 Spike 1.0).

The Dispatcher is the single entry point through which tool calls reach
Houdini. It replaces the outside-in WebSocket → handler pipeline of
Sprint 2 with an in-process, Strangler-Fig-friendly boundary that can
be driven from either the embedded Agent SDK (inside hython) or the
existing WebSocket adapter (for external clients during migration).

Key design properties
---------------------

1. **Zero ``hou`` imports.** This module composes across DCCs. Thread
   marshaling to the Houdini main loop lives in ``synapse.host.*`` and
   is injected via the ``main_thread_executor`` callable. The cognitive
   layer never imports Houdini directly.

2. **Fail-visible, not fail-fast.** Unhandled tool exceptions do not
   propagate out of ``execute()``. They are wrapped into structured
   ``AgentToolError`` values and **returned**, so the LLM sees failures
   as ordinary tool output and can rewrite its approach next turn.
   Raising would short-circuit the agent loop — exactly the opposite
   of what a self-correcting agent needs.

3. **Test-mode bypass (Invariant 1).** ``is_testing=True`` runs the
   tool synchronously on the caller's thread and skips any Qt-event-loop
   dependency. Headless ``hython`` does not pump a Qt event loop;
   without this bypass the 2606-test suite hangs indefinitely.

4. **JSON-serializable API boundary (Invariant 3, transition only).**
   Tool kwargs and return values are JSON-serializable — URIs (strings),
   dicts, numbers, booleans, lists. Native ``hou.Node`` objects across
   the boundary break the WS adapter's JSON-RPC marshaller. This is a
   Phase-4 lift point, not a Sprint-3 fight.

Spike 1.0 scope
---------------
- ``is_testing=True`` path: **live**.
- ``is_testing=False`` path: raises ``NotImplementedError`` with a clear
  message pointing at Spike 1. The hdefereval marshal is wired there,
  not here. The test bypass is the deliverable.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Union


ToolFn = Callable[..., Dict[str, Any]]
"""Tool callable contract: accepts keyword arguments, returns a JSON-
serializable dict. Must NOT raise in the happy path — exceptions are
caught by the Dispatcher and wrapped as ``AgentToolError``."""


@dataclass(frozen=True)
class AgentToolError:
    """Structured, JSON-serializable error returned by ``Dispatcher.execute``.

    The agent sees this as ordinary tool output — it is never raised.
    Fields are chosen to give the LLM enough context to rewrite its
    approach without retrying blindly.

    Attributes:
        tool_name: The tool that failed.
        error_type: Exception class name (e.g. ``"KeyError"``,
            ``"ObjectWasDeleted"``, ``"ToolNotRegistered"``). Stringified
            so the whole value survives JSON serialization.
        error_message: ``str(exception)`` — the exception's own message.
        traceback_str: Full traceback, truncated only if it would blow
            the agent's context window (see ``_TRACEBACK_MAX_LEN``).
            Empty string when the error has no upstream traceback
            (e.g. ToolNotRegistered, ToolReturnTypeError).
        timestamp: Unix epoch seconds when the error was observed.
    """

    tool_name: str
    error_type: str
    error_message: str
    traceback_str: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for JSON-RPC marshalling."""
        return {
            "agent_tool_error": True,
            "tool_name": self.tool_name,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "traceback_str": self.traceback_str,
            "timestamp": self.timestamp,
        }


_TRACEBACK_MAX_LEN = 4000
"""Cap tracebacks to 4 KB. Prevents a runaway C++ stack walk from
blowing the agent's context window."""


class Dispatcher:
    """Pure-Python tool dispatcher with test-mode bypass.

    A Dispatcher owns an immutable-by-convention tool registry and a
    single entry point, ``execute(tool_name, kwargs)``. It is the
    Strangler-Fig seam between the existing WebSocket adapter and the
    future in-process Agent SDK.

    Typical wiring (production, arrives in Spike 1):

        from synapse.cognitive.dispatcher import Dispatcher
        from synapse.host.thread import main_thread_exec

        dispatcher = Dispatcher(
            tools={'synapse_inspect_stage': inspect_stage, ...},
            main_thread_executor=main_thread_exec,
        )

    Typical wiring (tests, arrives now in Spike 1.0):

        dispatcher = Dispatcher(is_testing=True, tools={'tool': fn})
        result = dispatcher.execute('tool', {'arg': 1})
    """

    def __init__(
        self,
        *,
        is_testing: bool = False,
        tools: Optional[Mapping[str, ToolFn]] = None,
        main_thread_executor: Optional[Callable[[ToolFn, Dict[str, Any]],
                                                Dict[str, Any]]] = None,
    ) -> None:
        """Construct a Dispatcher.

        Args:
            is_testing: When True, ``execute`` runs tools synchronously
                on the calling thread and skips ``main_thread_executor``.
                Required for the 2606-test suite (no Qt loop to pump).
            tools: Optional initial tool registry. Maps tool name to
                a callable accepting JSON-serializable kwargs and
                returning a dict.
            main_thread_executor: Optional callable of the shape
                ``(fn, kwargs) -> dict`` that marshals ``fn(**kwargs)``
                onto Houdini's main thread. Wired in Spike 1 via
                ``synapse.host.*`` — must be None or the testing
                bypass path. When left unset and ``is_testing=False``,
                ``execute`` returns a NotImplementedError as an
                ``AgentToolError`` rather than raising.
        """
        self.is_testing = is_testing
        self._tools: Dict[str, ToolFn] = dict(tools) if tools else {}
        self._main_thread_executor = main_thread_executor

    # -- Tool registry surface (minimal — full registration arrives in Spike 1) --

    def register(self, tool_name: str, fn: ToolFn) -> None:
        """Register a tool callable under ``tool_name``.

        Overwrites any previous registration under the same name.
        """
        self._tools[tool_name] = fn

    def is_registered(self, tool_name: str) -> bool:
        return tool_name in self._tools

    # -- Execute --

    def execute(
        self,
        tool_name: str,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], AgentToolError]:
        """Dispatch ``tool_name`` with ``kwargs``.

        Never raises. Failures come back as ``AgentToolError`` so the
        agent can see them as data and recover.

        Returns:
            On success: the tool's dict return value.
            On failure: an ``AgentToolError`` with structured context.
        """
        effective_kwargs: Dict[str, Any] = dict(kwargs) if kwargs else {}

        fn = self._tools.get(tool_name)
        if fn is None:
            return self._error(
                tool_name=tool_name,
                error_type="ToolNotRegistered",
                error_message=(
                    f"No tool registered under {tool_name!r}. "
                    f"Known tools: {sorted(self._tools.keys())}"
                ),
                traceback_str="",
            )

        try:
            if self.is_testing:
                result = fn(**effective_kwargs)
            else:
                result = self._execute_via_main_thread(fn, effective_kwargs)
        except Exception as exc:
            return self._error(
                tool_name=tool_name,
                error_type=type(exc).__name__,
                error_message=str(exc),
                traceback_str=traceback.format_exc()[:_TRACEBACK_MAX_LEN],
            )

        # A tool can also return an AgentToolError directly (structured
        # failure without an exception); pass it through unchanged.
        if isinstance(result, AgentToolError):
            return result

        if not isinstance(result, dict):
            return self._error(
                tool_name=tool_name,
                error_type="ToolReturnTypeError",
                error_message=(
                    f"Tool {tool_name!r} returned "
                    f"{type(result).__name__}, expected dict"
                ),
                traceback_str="",
            )
        return result

    # -- Internal --

    def _execute_via_main_thread(
        self,
        fn: ToolFn,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Non-testing path: marshal to Houdini's main thread.

        Spike 1.0 intentionally leaves this unwired. Spike 1 supplies a
        ``main_thread_executor`` from ``synapse.host.*`` that wraps
        ``hdefereval.executeInMainThreadWithResult``. Until then, this
        path raises ``NotImplementedError`` (caught by ``execute`` and
        wrapped as an ``AgentToolError`` — never propagates).
        """
        if self._main_thread_executor is None:
            raise NotImplementedError(
                "Dispatcher main-thread marshal path is unwired — "
                "this lands in Sprint 3 Spike 1. For now, construct "
                "with is_testing=True or supply main_thread_executor."
            )
        return self._main_thread_executor(fn, kwargs)

    @staticmethod
    def _error(
        *,
        tool_name: str,
        error_type: str,
        error_message: str,
        traceback_str: str,
    ) -> AgentToolError:
        return AgentToolError(
            tool_name=tool_name,
            error_type=error_type,
            error_message=error_message,
            traceback_str=traceback_str,
            timestamp=time.time(),
        )
