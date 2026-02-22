"""
Synapse Live Metrics Aggregator

Collects scene, routing, resilience, and session metrics on a daemon thread.
Stores snapshots in a bounded circular buffer for historical queries.

He2025 compliance:
- time.monotonic() for timestamps
- frozen dataclasses (thread-safe by construction)
- sorted() on all dict iterations
- round_float() on output values
- deque(maxlen=N) for bounded history
- daemon=True thread for clean shutdown
"""

import dataclasses
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.determinism import round_float

logger = logging.getLogger("synapse.live_metrics")


# =========================================================================
# Metric data models (frozen = thread-safe, no locks needed for reads)
# =========================================================================

@dataclass(frozen=True)
class SceneMetrics:
    hip_file: str = ""
    current_frame: int = 0
    fps: float = 24.0
    total_nodes: int = 0
    lop_nodes: int = 0
    sop_nodes: int = 0
    obj_nodes: int = 0
    warnings: int = 0
    errors: int = 0


@dataclass(frozen=True)
class RoutingMetrics:
    total_requests: int = 0
    cache_hits: int = 0
    cache_hit_rate: float = 0.0
    tier_counts: tuple = ()  # Tuple of (tier_name, count) pairs
    avg_latency_ms: float = 0.0
    knowledge_entries: int = 0


@dataclass(frozen=True)
class ResilienceMetrics:
    circuit_state: str = "closed"
    circuit_trip_count: int = 0
    rate_limiter_active: bool = False
    rate_limit_rejects: int = 0
    health_status: str = "healthy"
    uptime_seconds: float = 0.0


@dataclass(frozen=True)
class SessionMetrics:
    active_sessions: int = 0
    total_commands: int = 0
    commands_per_minute: float = 0.0
    rbac_enabled: bool = False
    deploy_mode: str = "local"


@dataclass(frozen=True)
class MetricSnapshot:
    timestamp: float = 0.0
    scene: SceneMetrics = field(default_factory=SceneMetrics)
    routing: RoutingMetrics = field(default_factory=RoutingMetrics)
    resilience: ResilienceMetrics = field(default_factory=ResilienceMetrics)
    session: SessionMetrics = field(default_factory=SessionMetrics)


# =========================================================================
# Aggregator
# =========================================================================

# Default 2s collection interval, overridable via env var
_DEFAULT_INTERVAL = 2.0
_DEFAULT_HISTORY_SIZE = 300  # ~10 min at 2s interval


class MetricsAggregator:
    """Collects metrics on a daemon thread and stores snapshots in a circular buffer.

    All dependencies are optional — missing components yield zeroed metrics.
    """

    def __init__(
        self,
        interval: float = _DEFAULT_INTERVAL,
        history_size: int = _DEFAULT_HISTORY_SIZE,
        router: Any = None,
        health_monitor: Any = None,
        session_manager: Any = None,
        server: Any = None,
    ):
        env_interval = os.environ.get("SYNAPSE_METRICS_INTERVAL")
        if env_interval:
            try:
                interval = float(env_interval)
            except ValueError:
                pass

        self._interval = max(0.5, interval)  # floor at 0.5s
        self._router = router
        self._health_monitor = health_monitor
        self._session_manager = session_manager
        self._server = server

        self._history: deque = deque(maxlen=history_size)
        self._latest: Optional[MetricSnapshot] = None
        self._start_time = time.monotonic()

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the daemon collector thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._start_time = time.monotonic()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="Synapse-Metrics",
        )
        self._thread.start()
        logger.info("Metrics aggregator started (interval=%.1fs)", self._interval)

    def stop(self) -> None:
        """Signal stop and wait for the collector thread to exit."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._interval + 1.0)
        logger.info("Metrics aggregator stopped")

    def latest(self) -> Optional[MetricSnapshot]:
        """Return the most recent snapshot, or None if nothing collected yet."""
        return self._latest

    def history(self, count: int = 60) -> List[Dict]:
        """Return up to *count* recent snapshots as JSON-serializable dicts.

        Returns newest-first order. Uses sort_keys=True via dataclasses.asdict()
        followed by sorted key reconstruction.
        """
        items = list(self._history)
        if count > 0:
            items = items[-count:]
        items.reverse()  # newest first
        return [self._snapshot_to_dict(s) for s in items]

    # ------------------------------------------------------------------
    # Collection loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Background collection loop."""
        while not self._stop_event.is_set():
            try:
                snapshot = self._collect()
                self._latest = snapshot
                self._history.append(snapshot)
            except Exception:
                logger.debug("Metrics collection error", exc_info=True)
            self._stop_event.wait(self._interval)

    def _collect(self) -> MetricSnapshot:
        """One full collection cycle."""
        return MetricSnapshot(
            timestamp=round_float(time.monotonic(), 3),
            scene=self._collect_scene(),
            routing=self._collect_routing(),
            resilience=self._collect_resilience(),
            session=self._collect_session(),
        )

    # ------------------------------------------------------------------
    # Per-domain collectors
    # ------------------------------------------------------------------

    def _collect_scene(self) -> SceneMetrics:
        """Collect scene metrics from hou module. Graceful if unavailable."""
        try:
            import hou
        except ImportError:
            return SceneMetrics()

        try:
            hip = hou.hipFile.path() or ""
            frame = int(hou.frame())
            fps = float(hou.fps())

            total = lop = sop = obj = warns = errs = 0
            for node in hou.node("/").allSubChildren():
                total += 1
                ctx = node.type().category().name()
                if ctx == "Lop":
                    lop += 1
                elif ctx == "Sop":
                    sop += 1
                elif ctx == "Object":
                    obj += 1
                if node.warnings():
                    warns += 1
                if node.errors():
                    errs += 1

            return SceneMetrics(
                hip_file=hip,
                current_frame=frame,
                fps=round_float(fps, 2),
                total_nodes=total,
                lop_nodes=lop,
                sop_nodes=sop,
                obj_nodes=obj,
                warnings=warns,
                errors=errs,
            )
        except Exception:
            logger.debug("Scene metrics collection failed", exc_info=True)
            return SceneMetrics()

    def _collect_routing(self) -> RoutingMetrics:
        """Collect routing stats from the tiered router."""
        if not self._router:
            return RoutingMetrics()

        try:
            stats = self._router.stats()
            tiers = stats.get("tiers", {})

            total_requests = stats.get("total_routes", 0)
            cache_hits = stats.get("cache_hits", 0)
            cache_hit_rate = round_float(
                (cache_hits / total_requests * 100.0) if total_requests > 0 else 0.0, 2
            )

            tier_counts = tuple(
                (name, data.get("count", 0))
                for name, data in sorted(tiers.items())
            )

            # Compute average latency across tiers
            total_latency = 0.0
            tier_count = 0
            for _name, data in sorted(tiers.items()):
                avg = data.get("avg_ms", 0)
                count = data.get("count", 0)
                if count > 0:
                    total_latency += avg * count
                    tier_count += count
            avg_latency = round_float(
                (total_latency / tier_count) if tier_count > 0 else 0.0, 2
            )

            knowledge_entries = stats.get("knowledge_entries", 0)

            return RoutingMetrics(
                total_requests=total_requests,
                cache_hits=cache_hits,
                cache_hit_rate=cache_hit_rate,
                tier_counts=tier_counts,
                avg_latency_ms=avg_latency,
                knowledge_entries=knowledge_entries,
            )
        except Exception:
            logger.debug("Routing metrics collection failed", exc_info=True)
            return RoutingMetrics()

    def _collect_resilience(self) -> ResilienceMetrics:
        """Collect resilience metrics from HealthMonitor."""
        if not self._health_monitor:
            return ResilienceMetrics()

        try:
            health = self._health_monitor.to_dict()
            components = health.get("components", {})

            cb = components.get("circuit_breaker", {})
            circuit_state = cb.get("state", "closed")
            circuit_trips = cb.get("trip_count", 0)

            rl = components.get("rate_limiter", {})
            rl_active = rl.get("rejection_rate", 0) > 0
            rl_rejects = rl.get("total_rejections", 0)

            health_status = health.get("level", "healthy")
            uptime = round_float(time.monotonic() - self._start_time, 1)

            return ResilienceMetrics(
                circuit_state=circuit_state,
                circuit_trip_count=circuit_trips,
                rate_limiter_active=rl_active,
                rate_limit_rejects=rl_rejects,
                health_status=health_status,
                uptime_seconds=uptime,
            )
        except Exception:
            logger.debug("Resilience metrics collection failed", exc_info=True)
            return ResilienceMetrics()

    def _collect_session(self) -> SessionMetrics:
        """Collect session and command metrics."""
        active = 0
        total_cmds = 0
        cmds_per_min = 0.0
        rbac = False
        mode = "local"

        # Session manager (Sprint D)
        if self._session_manager:
            try:
                active = self._session_manager.count
            except Exception:
                pass

        # Server command stats
        if self._server:
            try:
                if hasattr(self._server, "_command_queue"):
                    total_cmds = getattr(
                        self._server._command_queue, "total_processed", 0
                    )
            except Exception:
                pass

        # Commands per minute from uptime
        uptime_min = (time.monotonic() - self._start_time) / 60.0
        if uptime_min > 0 and total_cmds > 0:
            cmds_per_min = round_float(total_cmds / uptime_min, 2)

        # RBAC status
        try:
            from .rbac import is_rbac_enabled
            rbac = is_rbac_enabled()
        except Exception:
            pass

        # Deploy mode
        if self._server and hasattr(self._server, "_deploy_config"):
            try:
                mode = self._server._deploy_config.mode
            except Exception:
                pass

        return SessionMetrics(
            active_sessions=active,
            total_commands=total_cmds,
            commands_per_minute=cmds_per_min,
            rbac_enabled=rbac,
            deploy_mode=mode,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot_to_dict(snapshot: MetricSnapshot) -> Dict:
        """Convert snapshot to JSON-serializable dict with sorted keys."""
        d = dataclasses.asdict(snapshot)
        # Convert tier_counts tuple-of-tuples back to a dict for readability
        tc = d.get("routing", {}).get("tier_counts", ())
        if tc:
            d["routing"]["tier_counts"] = {name: count for name, count in tc}
        return d


def snapshot_to_dict(snapshot: MetricSnapshot) -> Dict:
    """Module-level helper for converting a snapshot to dict."""
    return MetricsAggregator._snapshot_to_dict(snapshot)
