"""
Tests for Synapse Live Metrics Aggregator (Sprint E: Phase 1)

No Houdini required — hou is stubbed before import.
"""

import dataclasses
import json
import os
import sys
import threading
import time
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: add python/ to path and stub 'hou' before importing
# ---------------------------------------------------------------------------

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)

# Stub hou before importing live_metrics (it tries to import hou in _collect_scene)
_original_hou = sys.modules.get("hou")


def _make_hou_stub():
    hou = types.ModuleType("hou")
    hou.hipFile = MagicMock()
    hou.hipFile.path = MagicMock(return_value="/tmp/test.hip")
    hou.frame = MagicMock(return_value=1)
    hou.fps = MagicMock(return_value=24.0)

    mock_node = MagicMock()
    mock_node.type.return_value.category.return_value.name.return_value = "Sop"
    mock_node.warnings.return_value = []
    mock_node.errors.return_value = []

    root = MagicMock()
    root.allSubChildren.return_value = [mock_node]
    hou.node = MagicMock(return_value=root)
    return hou


if "hou" not in sys.modules:
    sys.modules["hou"] = _make_hou_stub()

from synapse.server.live_metrics import (
    SceneMetrics,
    RoutingMetrics,
    ResilienceMetrics,
    SessionMetrics,
    MetricSnapshot,
    MetricsAggregator,
    snapshot_to_dict,
)


# ---------------------------------------------------------------------------
# Frozen dataclass tests
# ---------------------------------------------------------------------------

class TestDataModels:
    def test_scene_metrics_defaults(self):
        s = SceneMetrics()
        assert s.hip_file == ""
        assert s.total_nodes == 0
        assert s.fps == 24.0

    def test_scene_metrics_frozen(self):
        s = SceneMetrics(hip_file="test.hip")
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.hip_file = "other.hip"  # type: ignore[misc]

    def test_routing_metrics_defaults(self):
        r = RoutingMetrics()
        assert r.total_requests == 0
        assert r.tier_counts == ()

    def test_routing_metrics_frozen(self):
        r = RoutingMetrics(total_requests=5)
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.total_requests = 10  # type: ignore[misc]

    def test_resilience_metrics_defaults(self):
        r = ResilienceMetrics()
        assert r.circuit_state == "closed"
        assert r.health_status == "healthy"
        assert r.uptime_seconds == 0.0

    def test_session_metrics_defaults(self):
        s = SessionMetrics()
        assert s.active_sessions == 0
        assert s.deploy_mode == "local"

    def test_snapshot_defaults(self):
        snap = MetricSnapshot()
        assert snap.timestamp == 0.0
        assert isinstance(snap.scene, SceneMetrics)
        assert isinstance(snap.routing, RoutingMetrics)

    def test_snapshot_frozen(self):
        snap = MetricSnapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.timestamp = 99.0  # type: ignore[misc]

    def test_tier_counts_as_tuple(self):
        r = RoutingMetrics(tier_counts=(("cache", 10), ("regex", 5)))
        assert r.tier_counts[0] == ("cache", 10)
        assert r.tier_counts[1] == ("regex", 5)


# ---------------------------------------------------------------------------
# Aggregator tests
# ---------------------------------------------------------------------------

class TestAggregator:
    def test_init_defaults(self):
        agg = MetricsAggregator()
        assert agg._interval == 2.0
        assert agg.latest() is None

    def test_init_custom_interval(self):
        agg = MetricsAggregator(interval=5.0)
        assert agg._interval == 5.0

    def test_init_env_var_interval(self):
        with patch.dict(os.environ, {"SYNAPSE_METRICS_INTERVAL": "3.5"}):
            agg = MetricsAggregator()
            assert agg._interval == 3.5

    def test_init_interval_floor(self):
        agg = MetricsAggregator(interval=0.1)
        assert agg._interval == 0.5

    def test_collect_returns_snapshot(self):
        agg = MetricsAggregator()
        snap = agg._collect()
        assert isinstance(snap, MetricSnapshot)
        assert snap.timestamp > 0

    def test_collect_scene_no_hou(self):
        agg = MetricsAggregator()
        # Temporarily remove hou to simulate unavailable
        saved = sys.modules.get("hou")
        sys.modules["hou"] = None  # type: ignore[assignment]
        try:
            scene = agg._collect_scene()
            assert scene == SceneMetrics()
        finally:
            if saved is not None:
                sys.modules["hou"] = saved

    def test_collect_routing_no_router(self):
        agg = MetricsAggregator(router=None)
        routing = agg._collect_routing()
        assert routing == RoutingMetrics()

    def test_collect_routing_with_router(self):
        mock_router = MagicMock()
        mock_router.stats.return_value = {
            "total_routes": 100,
            "cache_hits": 40,
            "tiers": {
                "cache": {"count": 40, "avg_ms": 0.1},
                "regex": {"count": 30, "avg_ms": 1.5},
                "knowledge": {"count": 30, "avg_ms": 5.0},
            },
            "knowledge_entries": 50,
        }
        agg = MetricsAggregator(router=mock_router)
        routing = agg._collect_routing()
        assert routing.total_requests == 100
        assert routing.cache_hits == 40
        assert routing.cache_hit_rate == 40.0
        assert len(routing.tier_counts) == 3
        assert routing.knowledge_entries == 50

    def test_collect_resilience_no_monitor(self):
        agg = MetricsAggregator(health_monitor=None)
        res = agg._collect_resilience()
        assert res == ResilienceMetrics()

    def test_collect_resilience_with_monitor(self):
        mock_monitor = MagicMock()
        mock_monitor.to_dict.return_value = {
            "level": "healthy",
            "components": {
                "circuit_breaker": {"state": "closed", "trip_count": 2},
                "rate_limiter": {"rejection_rate": 0.1, "total_rejections": 5},
            },
        }
        agg = MetricsAggregator(health_monitor=mock_monitor)
        res = agg._collect_resilience()
        assert res.circuit_state == "closed"
        assert res.circuit_trip_count == 2
        assert res.rate_limiter_active is True
        assert res.rate_limit_rejects == 5
        assert res.health_status == "healthy"

    def test_collect_session_no_deps(self):
        agg = MetricsAggregator()
        sess = agg._collect_session()
        assert sess.active_sessions == 0
        assert sess.deploy_mode == "local"

    def test_collect_session_with_manager(self):
        mock_sm = MagicMock()
        mock_sm.count = 3
        agg = MetricsAggregator(session_manager=mock_sm)
        sess = agg._collect_session()
        assert sess.active_sessions == 3

    def test_start_stop(self):
        agg = MetricsAggregator(interval=0.5)
        agg.start()
        assert agg._thread is not None
        assert agg._thread.is_alive()
        assert agg._thread.daemon is True
        agg.stop()
        assert not agg._thread.is_alive()

    def test_start_idempotent(self):
        agg = MetricsAggregator(interval=0.5)
        agg.start()
        thread1 = agg._thread
        agg.start()  # second call should be no-op
        assert agg._thread is thread1
        agg.stop()

    def test_collects_after_start(self):
        agg = MetricsAggregator(interval=0.5)
        agg.start()
        time.sleep(1.0)
        agg.stop()
        assert agg.latest() is not None
        assert len(agg._history) >= 1

    def test_history_returns_newest_first(self):
        agg = MetricsAggregator(interval=0.5)
        agg.start()
        time.sleep(1.5)
        agg.stop()
        hist = agg.history(count=10)
        assert len(hist) >= 2
        assert hist[0]["timestamp"] >= hist[-1]["timestamp"]

    def test_history_count_limits(self):
        agg = MetricsAggregator()
        for i in range(10):
            snap = MetricSnapshot(timestamp=float(i))
            agg._history.append(snap)
        hist = agg.history(count=3)
        assert len(hist) == 3

    def test_history_bounded_by_maxlen(self):
        agg = MetricsAggregator(history_size=5)
        for i in range(10):
            agg._history.append(MetricSnapshot(timestamp=float(i)))
        assert len(agg._history) == 5


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_snapshot_to_dict(self):
        snap = MetricSnapshot(
            timestamp=1.0,
            scene=SceneMetrics(hip_file="test.hip", total_nodes=42),
            routing=RoutingMetrics(
                tier_counts=(("cache", 10), ("regex", 5)),
                total_requests=15,
            ),
        )
        d = snapshot_to_dict(snap)
        assert d["timestamp"] == 1.0
        assert d["scene"]["hip_file"] == "test.hip"
        assert d["scene"]["total_nodes"] == 42
        # tier_counts converted to dict
        assert d["routing"]["tier_counts"] == {"cache": 10, "regex": 5}

    def test_snapshot_to_dict_empty(self):
        snap = MetricSnapshot()
        d = snapshot_to_dict(snap)
        assert d["timestamp"] == 0.0
        assert d["scene"]["hip_file"] == ""
        assert d["routing"]["tier_counts"] == ()

    def test_snapshot_serializable_json(self):
        snap = MetricSnapshot(
            timestamp=1.0,
            routing=RoutingMetrics(tier_counts=(("t0", 5),)),
        )
        d = snapshot_to_dict(snap)
        text = json.dumps(d, sort_keys=True)
        assert '"tier_counts"' in text


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def teardown_module():
    if _original_hou is not None:
        sys.modules["hou"] = _original_hou
    elif "hou" in sys.modules:
        del sys.modules["hou"]
