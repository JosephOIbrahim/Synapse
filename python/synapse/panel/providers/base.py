"""StreamProvider — the panel chat worker's provider abstraction.

A provider owns exactly one thing: the per-provider transport plus the
request/response translation for a single streamed turn. It returns NORMALIZED
Anthropic-shaped content blocks (``text`` / ``tool_use``) and a ``stop_reason``,
so the worker's conversation loop and tool dispatch never learn which engine
produced the turn.

Contract
--------
* **No Qt, no hou.** Pure transport (stdlib HTTP). The worker injects the
  ``emit_token`` / ``should_abort`` callbacks so the provider can stream and
  honour cancellation without owning the QThread.
* ``stream`` returns ``(stop_reason, content_blocks)``; raise ``RuntimeError`` on
  a transport/stream error (the worker maps it to ``stream_error`` — the
  no-silent-fallback discipline, D3).
* **Model identity is data** (carried on the instance from the registry), never
  hardcoded in dispatch.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

EmitToken = Callable[[str], None]
ShouldAbort = Callable[[], bool]


class StreamProvider:
    """Base interface. Subclasses set ``id`` and implement the three methods."""

    id: str = "base"

    @property
    def model_identity(self) -> str:
        """The model string that authored this turn (Invariant P, display-only)."""
        return ""

    @property
    def label(self) -> str:
        """Short author-token label for the rail (defaults to the model id)."""
        return self.model_identity

    def resolve_key(self) -> Optional[str]:
        """Provider-specific API-key resolution. ``None`` ⇒ unconfigured."""
        raise NotImplementedError

    def key_error_message(self) -> str:
        """Human message shown when ``resolve_key`` returns nothing."""
        return "No API key found for provider %r." % self.id

    def stream(
        self,
        *,
        messages: List[dict],
        tools: List[dict],
        system: str,
        api_key: str,
        emit_token: EmitToken,
        should_abort: ShouldAbort,
    ) -> Tuple[Optional[str], List[dict]]:
        """Stream one turn.

        Emit text deltas via ``emit_token``; bail when ``should_abort()`` is
        true. Return ``(stop_reason, content_blocks)`` with Anthropic-shaped
        blocks. Raise ``RuntimeError`` on a transport/stream error.
        """
        raise NotImplementedError
