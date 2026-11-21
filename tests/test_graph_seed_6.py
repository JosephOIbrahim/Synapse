"""F01: a missing router / metrics aggregator must raise, not return an error dict.

handle() wraps any returned dict as success=True, so an error dict reached
/mcp as a success (the BRIDGE-13 shape). Raising SynapseServiceError makes
handle() report success=False.

R-014 adds the other half of the contract: when the router IS present — the
shipped case — the advertised synapse_router_stats tool must actually serve
stats. Before that repair TieredRouter was never constructed on any shipped
path, so this tool could only raise.
"""
import json
import types

import pytest

from synapse.core.errors import SynapseServiceError
from synapse.core.protocol import SynapseCommand
from synapse.server.handlers import SynapseHandler


def test_router_stats_without_router_raises():
    bare = types.SimpleNamespace()
    with pytest.raises(SynapseServiceError, match="Router not initialized"):
        SynapseHandler._handle_router_stats(bare, {})


# ── R-014: the success half — a default-constructed shipped handler serves it ──

_TIER_KEYS = {"cache", "recipe", "instant", "fast", "standard", "deep"}


def test_default_handler_owns_the_router():
    """SynapseHandler.__init__ is the construction seam both transports use.

    SynapseServer (/synapse) and MCPServer._get_handler (/mcp) both build
    their handler with SynapseHandler(); constructing the router here is what
    makes the tool answerable everywhere.
    """
    handler = SynapseHandler()
    assert getattr(handler, "_router", None) is not None


def test_default_handler_router_stats_succeeds():
    """router_stats through a default handler returns real stats, not an error.

    Nothing on the live dispatch path routes through the cascade, so the
    counters read zero — that is the honest statistic. The response shape is
    TieredRouter.stats(): per-tier counts plus cache/knowledge/epoch blocks.
    """
    handler = SynapseHandler()
    stats = handler._handle_router_stats({})
    assert stats["total_routes"] == 0
    assert set(stats["tiers"]) == _TIER_KEYS
    assert "epoch" in stats


def test_default_handler_dispatches_router_stats():
    """The tool answers through handle(), the path WS and /mcp share."""
    handler = SynapseHandler()
    response = handler.handle(
        SynapseCommand(type="router_stats", id="r014-1", payload={}))
    assert response.success is True
    assert response.data["total_routes"] == 0


def test_router_stats_through_mcp_tool_dispatch():
    """The registered tool name resolves to stats, never isError."""
    from synapse.mcp.tools import dispatch_tool

    result = dispatch_tool(SynapseHandler(), "synapse_router_stats", {})
    assert not result.get("isError")
    stats = json.loads(result["content"][0]["text"])
    assert stats["total_routes"] == 0


def test_live_metrics_without_aggregator_raises():
    bare = types.SimpleNamespace(_metrics_aggregator=None)
    with pytest.raises(SynapseServiceError, match="Metrics aggregator not running"):
        SynapseHandler._handle_get_live_metrics(bare, {})
