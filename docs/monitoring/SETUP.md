# Synapse Monitoring Setup

Real-time monitoring for Synapse sessions. Artists can see scene health, routing performance, resilience state, and session statistics at a glance.

## Overview

Sprint E adds a **MetricsAggregator** that collects metrics on a background daemon thread every 2 seconds and stores them in a circular buffer (~10 minutes of history). An embedded **web dashboard** renders the data in a 4-panel grid (Scene, Routing, Resilience, Sessions).

Monitoring is enabled by default when the Synapse server starts. No additional configuration required.

## Accessing the Dashboard

Open a browser to the Houdini hwebserver dashboard route:

```
http://localhost:<hwebserver_port>/dashboard
```

The dashboard auto-connects to Synapse's WebSocket on port 9999 and polls `get_live_metrics` every 2 seconds.

### Dashboard Controls

- **Interval selector**: 1s / 2s / 5s / 10s polling rate
- **Pause/Resume**: Freeze the display without disconnecting

## Programmatic Access

### Via WebSocket

Send a `get_live_metrics` command:

```json
{"type": "get_live_metrics", "id": "1", "payload": {}}
```

Response contains `scene`, `routing`, `resilience`, and `session` metric groups.

For historical data, pass `history_count`:

```json
{"type": "get_live_metrics", "id": "2", "payload": {"history_count": 30}}
```

Returns up to 30 snapshots, newest first.

### Via MCP

The `synapse_live_metrics` tool is available in both stdio and Streamable HTTP MCP transports:

```
Tool: synapse_live_metrics
Arguments: {"history_count": 0}  // 0 = latest snapshot only
```

## Configuration

### Collection Interval

Set `SYNAPSE_METRICS_INTERVAL` environment variable to override the default 2-second interval:

```bash
# Collect every 5 seconds
set SYNAPSE_METRICS_INTERVAL=5.0
```

Minimum interval is 0.5 seconds. Values below this are clamped.

### History Size

Default: 300 snapshots (~10 minutes at 2s interval). Not currently configurable via environment variable.

## Metric Groups

### Scene

| Metric | Description |
|--------|-------------|
| `hip_file` | Current HIP file path |
| `current_frame` | Active frame number |
| `fps` | Scene FPS |
| `total_nodes` | Total nodes in scene |
| `lop_nodes` / `sop_nodes` / `obj_nodes` | Node counts by context |
| `warnings` | Nodes with warnings |
| `errors` | Nodes with errors |

### Routing

| Metric | Description |
|--------|-------------|
| `total_requests` | Total routed requests |
| `cache_hits` | Cache hit count |
| `cache_hit_rate` | Cache hit percentage |
| `tier_counts` | Requests per routing tier |
| `avg_latency_ms` | Weighted average latency |
| `knowledge_entries` | RAG knowledge entry count |

### Resilience

| Metric | Description |
|--------|-------------|
| `circuit_state` | Circuit breaker state (closed/open/half_open) |
| `circuit_trip_count` | Number of circuit breaker trips |
| `rate_limiter_active` | Whether rate limiting is rejecting requests |
| `rate_limit_rejects` | Total rate limit rejections |
| `health_status` | Overall health (healthy/degraded/critical) |
| `uptime_seconds` | Time since aggregator started |

### Session

| Metric | Description |
|--------|-------------|
| `active_sessions` | Active user sessions (studio mode) |
| `total_commands` | Total commands processed |
| `commands_per_minute` | Command throughput |
| `rbac_enabled` | Whether RBAC is active |
| `deploy_mode` | Deployment mode (local/studio-lan/studio-vpn) |

## Prometheus Integration

Live metrics are included in the existing Prometheus endpoint (`get_metrics` / `synapse_metrics` tool). Scene and session metrics are exported as additional gauges:

```
synapse_scene_nodes_total 342
synapse_scene_warnings 2
synapse_scene_errors 0
synapse_sessions_active 3
synapse_commands_per_minute 24.5
synapse_uptime_seconds 8100.0
```

## Troubleshooting

### "Metrics aggregator not running"

The aggregator starts automatically with the Synapse server. If you see this error:
1. Verify the Synapse server is running (check the Python Panel status)
2. Restart Synapse from the shelf

### Dashboard shows "connecting..."

The dashboard connects to `ws://localhost:9999/synapse`. Verify:
1. Synapse WebSocket server is running on port 9999
2. No firewall blocking localhost connections
3. Browser console for WebSocket errors

### No scene metrics (all zeros)

Scene metrics require `hou` module access. If running outside Houdini (e.g., standalone tests), scene metrics will be zeroed. This is expected behavior.
