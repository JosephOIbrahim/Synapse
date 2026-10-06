"""F01: a missing router / metrics aggregator must raise, not return an error dict.

handle() wraps any returned dict as success=True, so an error dict reached
/mcp as a success (the BRIDGE-13 shape). Raising SynapseServiceError makes
handle() report success=False.
"""
import types

import pytest

from synapse.core.errors import SynapseServiceError
from synapse.server.handlers import SynapseHandler


def test_router_stats_without_router_raises():
    bare = types.SimpleNamespace()
    with pytest.raises(SynapseServiceError, match="Router not initialized"):
        SynapseHandler._handle_router_stats(bare, {})


def test_live_metrics_without_aggregator_raises():
    bare = types.SimpleNamespace(_metrics_aggregator=None)
    with pytest.raises(SynapseServiceError, match="Metrics aggregator not running"):
        SynapseHandler._handle_get_live_metrics(bare, {})
