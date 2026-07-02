"""synapse.providers — the ``call_tool`` provider registry (D-H22-1).

A *tool provider* answers ``call_tool(name, args) -> envelope`` — the seam
through which SYNAPSE orchestrates external MCP servers (first: H22's native
APEX MCP) as one source among many. Deliberately a SIBLING of
``synapse.panel.providers``, not a member: ``StreamProvider`` streams LLM
turns (``panel/providers/base.py``); an MCP is a ``call_tool`` provider —
forcing a fake ``stream()`` would conflate two contracts. "Peer to the model
providers" (docs/SYNAPSE_H22_BOUNDARY.md §3.1) is honored at the
registry-concept level.

Contract
--------
* Pure Python, ZERO ``hou``. Registration is declarative; construction is
  lazy (the factory runs on first :func:`get`).
* Fail-loud: resolution / construction / transport problems raise
  :class:`ProviderError` — no silent fallback (the D3 no-silent-fallback
  discipline from ``panel/providers/base.py``).
"""

from __future__ import annotations

from typing import Any, Callable


class ProviderError(RuntimeError):
    """Raised on provider resolution, construction, or transport failure."""


_FACTORIES: dict[str, Callable[[], Any]] = {}
_INSTANCES: dict[str, Any] = {}


def register(provider_id: str, factory: Callable[[], Any]) -> None:
    """Declare ``provider_id`` → ``factory``. Lazy: the factory runs on the
    first :func:`get`. Re-registering drops any cached instance (test seam)."""
    _FACTORIES[provider_id] = factory
    _INSTANCES.pop(provider_id, None)


def get(provider_id: str) -> Any:
    """Resolve a provider, constructing (and caching) it on first use."""
    if provider_id in _INSTANCES:
        return _INSTANCES[provider_id]
    factory = _FACTORIES.get(provider_id)
    if factory is None:
        raise ProviderError(
            f"unknown provider '{provider_id}' (registered: {sorted(_FACTORIES)})")
    try:
        instance = factory()
    except ProviderError:
        raise
    except Exception as e:            # constructor failure IS a resolution failure
        raise ProviderError(
            f"provider '{provider_id}' failed to construct: {e}") from e
    _INSTANCES[provider_id] = instance
    return instance


def _make_apex_mcp() -> Any:
    from synapse.providers.apex_mcp import ApexMCPProvider   # lazy import
    return ApexMCPProvider()


# Default rows — H22's native APEX MCP (D-H22-1).
register("apex_mcp", _make_apex_mcp)
