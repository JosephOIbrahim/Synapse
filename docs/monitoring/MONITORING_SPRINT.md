# SYNAPSE -- Real-Time Monitoring Sprint Instructions

> **Sprint Goal:** Add a live metrics dashboard to SYNAPSE that streams scene health,
> render progress, cook times, memory usage, and routing statistics to connected clients
> in real time. Artists and TDs should be able to monitor their Houdini session at a
> glance without switching context.
>
> **Prerequisite:** Studio Deployment Sprint must be complete. The monitoring system
> needs multi-user sessions and RBAC (viewers can monitor, only leads can configure alerts).

---

## 0. PRE-FLIGHT -- Read Before Coding

1. **Read existing metrics:**
   - `python/synapse/server/metrics.py` -- Prometheus-format metrics (request counts, latencies, circuit breaker state)
   - `get_metrics` handler -- Returns memory store size, knowledge index coverage
   - `router_stats` handler -- Per-tier counts, latencies, cache hit rates
   - TOPS `tops_pipeline_status` -- Full topnet health check
   - TOPS `tops_get_cook_stats` -- Per-node cook timing

2. **Read existing transports:**
   - `server/websocket.py` -- Primary WebSocket transport (bidirectional)
   - `mcp/server.py` -- MCP Streamable HTTP (supports SSE for server-push)
   - `server/hwebserver_adapter.py` -- Houdini native HTTP

3. **Understand what's missing:**
   - No push mechanism -- all metrics are pull-only (client must request)
   - No historical data -- metrics are point-in-time snapshots
   - No alerting -- no thresholds, no notifications
   - No visual dashboard -- data is JSON only, no rendering

---

## 1. ARCHITECTURE

### Monitoring Stack

```
Dashboard UI (Web or Qt)
    |
    |-- WebSocket subscription (live push)
    |-- MCP SSE stream (server-sent events)
    |
Metrics Aggregator (NEW)
    |  Collects, buffers, and broadcasts metrics
    |  Configurable push interval (default: 2s)
    |
    +-- Scene Metrics Collector
    |   |-- Node count, cook state, errors/warnings
    |   |-- Memory usage (hou.hmath.availableMemory)
    |   |-- Frame range, current frame, FPS
    |   +-- USD stage prim count, layer count
    |
    +-- Render Metrics Collector
    |   |-- Active render progress (% complete, ETA)
    |   |-- Render history (last N renders with times)
    |   +-- Karma XPU vs CPU utilization
    |
    +-- TOPS Metrics Collector
    |   |-- Pipeline health (per-topnet)
    |   |-- Work item throughput (items/second)
    |   |-- Cook queue depth, scheduler utilization
    |   +-- Failure rate over time
    |
    +-- Routing Metrics Collector
    |   |-- Tier distribution (% per tier)
    |   |-- Cache hit rate over time
    |   |-- Average response latency by tier
    |   +-- Recipe trigger frequency
    |
    +-- System Metrics Collector
        |-- CPU, GPU, RAM utilization
        |-- Disk I/O (texture loading, cache writes)
        +-- Network (WebSocket message rate)
```

### Push vs Pull

| Method | Transport | Use Case |
|--------|-----------|----------|
| **Pull** (existing) | `get_metrics`, `router_stats` | On-demand snapshots |
| **Push** (new) | WebSocket subscription | Live dashboard updates |
| **SSE** (new) | MCP `GET /mcp` stream | MCP client monitoring |

The push system uses a **fan-out pattern**: one collector thread, multiple subscriber
connections. Each subscriber gets the same metric snapshot. No per-subscriber queries.

---

## 2. NEW MODULES

### 2.1 `server/live_metrics.py` -- Metrics Aggregator

```python
@dataclass
class MetricSnapshot:
    timestamp: float                  # time.monotonic()
    scene: SceneMetrics              # Node counts, cook state, memory
    render: RenderMetrics | None     # Active render progress (None if idle)
    tops: dict[str, TopnetMetrics]   # Per-topnet health (keyed by path)
    routing: RoutingMetrics          # Tier distribution, cache hits
    system: SystemMetrics            # CPU, GPU, RAM

class MetricsAggregator:
    """Collects metrics on a timer, broadcasts to subscribers."""
    _interval: float = 2.0           # Push interval in seconds
    _subscribers: set[Callable]      # Callback set (thread-safe)
    _collector_thread: threading.Thread
    _stop_event: threading.Event

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def subscribe(self, callback: Callable[[MetricSnapshot], None]) -> str: ...
    def unsubscribe(self, sub_id: str) -> None: ...
    def snapshot(self) -> MetricSnapshot: ...  # On-demand pull
```

### 2.2 `server/alerts.py` -- Threshold Alerting

```python
@dataclass
class AlertRule:
    name: str                        # "high_memory"
    metric_path: str                 # "system.ram_percent"
    threshold: float                 # 90.0
    comparison: str                  # "gt" | "lt" | "eq"
    cooldown: float = 300.0          # Don't re-alert for 5 minutes
    severity: str = "warning"        # "info" | "warning" | "critical"

class AlertManager:
    """Evaluates rules against snapshots, fires notifications."""
    _rules: list[AlertRule]
    _fired: dict[str, float]         # rule_name -> last_fired timestamp

    def evaluate(self, snapshot: MetricSnapshot) -> list[Alert]: ...
    def add_rule(self, rule: AlertRule) -> None: ...
    def remove_rule(self, name: str) -> None: ...
```

### 2.3 `server/dashboard.py` -- Embedded Web Dashboard

Lightweight HTML dashboard served from hwebserver. No external dependencies -- uses
vanilla HTML/CSS/JS with WebSocket for live updates.

```python
def register_dashboard_routes(server) -> None:
    """Register /dashboard endpoint on hwebserver."""
    # GET /dashboard -> HTML page with embedded JS
    # JS opens WebSocket to /synapse and subscribes to metrics
    # Dashboard auto-refreshes with push data
```

**Dashboard layout:**

```
+------------------------------------------+
| SYNAPSE Monitor           [2s] [pause]   |
+------------------------------------------+
| Scene          | Routing                  |
| Nodes: 342     | Cache: 89% hit           |
| Prims: 1,204   | T0: 45% | T1: 30%      |
| Memory: 4.2 GB | T2: 20% | T3: 5%       |
| Errors: 0      | Avg: 12ms               |
+------------------------------------------+
| Render                                    |
| [============>     ] 67% ETA: 2:34       |
| Karma XPU | 1920x1080 | 256 spp         |
+------------------------------------------+
| TOPS Pipeline          | Alerts          |
| /topnet1: healthy (25) | [!] RAM > 90%  |
| /topnet2: cooking (12) |                 |
+------------------------------------------+
```

---

## 3. PHASES

| Phase | Scope | Gate Files |
|-------|-------|------------|
| **Phase 1 -- Collector** | Metrics aggregator, scene + routing collectors, push via WebSocket | `server/live_metrics.py` exists |
| **Phase 2 -- Dashboard** | Web dashboard HTML/JS, hwebserver route, live updates | `server/dashboard.py` exists |
| **Phase 3 -- Alerts** | Threshold rules, alert manager, notification push | `server/alerts.py` exists, tests pass |
| **Phase 4 -- Polish** | Render progress tracking, TOPS throughput, Prometheus export | `docs/monitoring/SETUP.md` exists |

### Phase 1 Rules
- Collector runs in a daemon thread -- must not block Houdini's main thread
- Use `hdefereval.executeInMainThreadWithResult()` for hou.* calls (same as handlers)
- Metric snapshots are immutable dataclasses -- thread-safe by construction
- Fan-out uses `threading.Lock` for subscriber set, snapshot is replaced atomically
- Default interval 2 seconds -- configurable via `SYNAPSE_METRICS_INTERVAL`

### Phase 2 Rules
- Dashboard is a single HTML file with embedded CSS/JS -- no build step
- Served from hwebserver at `/dashboard` (GET)
- Uses existing WebSocket transport for live data
- No external CDN dependencies -- must work in air-gapped studios
- Responsive layout for 1080p and 4K displays

### Phase 3 Rules
- Alert rules stored in `~/.synapse/alerts.json`
- RBAC: only `lead` and `admin` roles can modify alert rules
- `viewer` and `artist` can see active alerts
- Cooldown prevents alert storms
- Alerts pushed to subscribers alongside metric snapshots

### Phase 4 Rules
- Render progress requires polling Karma ROP state (hwebserver adapter, main thread)
- TOPS throughput calculated from work item completion rate over sliding window
- Prometheus export at `/metrics` endpoint (text format, existing `metrics.py` pattern)
- Document Grafana integration for studios using Prometheus

---

## 4. FILESYSTEM GATES

Sprint E is complete when ALL of these exist:

```
python/synapse/server/live_metrics.py   -- Metrics aggregator
python/synapse/server/dashboard.py      -- Web dashboard
docs/monitoring/SETUP.md                -- Monitoring setup guide
```

**Verification:**
```bash
ls python/synapse/server/live_metrics.py python/synapse/server/dashboard.py \
   docs/monitoring/SETUP.md 2>/dev/null | wc -l
# Must return 3
python -m pytest tests/test_live_metrics.py -v
# Must pass
```

---

## 5. PERFORMANCE CONSTRAINTS

- Metrics collection must complete in < 100ms per cycle (2s interval leaves 1.9s idle)
- Main thread calls (hou.*) batched into a single `executeInMainThreadWithResult()` per cycle
- Subscriber notification is async (fire-and-forget to each WebSocket)
- Dashboard HTML/JS payload < 50KB (no frameworks, no images)
- Memory buffer: keep last 300 snapshots (10 minutes at 2s interval) for sparkline history

---

## 6. He2025 COMPLIANCE

| Pattern | Applied In |
|---------|-----------|
| `time.monotonic()` | Snapshot timestamps, alert cooldown tracking |
| `round_float()` | All metric values in snapshots (OUTPUT) |
| `dict(sorted())` | Metric snapshot serialization |
| `sorted()` | Alert lists, subscriber lists, topnet lists |
| `kahan_sum()` | Throughput rate calculation (sliding window) |
| `encoding="utf-8"` | alerts.json, dashboard HTML |

---

*Cross-reference: metrics.py for existing Prometheus format, resilience.py for circuit breaker metrics, CLAUDE.md for He2025 patterns.*
