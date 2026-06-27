"""
Synapse Metrics Exporter

Simple Prometheus text format exporter. No external dependencies.
Exposes per-tier request counts, latencies, command counts,
circuit breaker state, and memory store size.

He2025 compliance:
- kahan_sum() for latency averages — stable across batch sizes
- round_float() on output — deterministic precision
- sorted() iteration on all dicts — order-independent
"""

import logging
from typing import Dict, Any, Optional

from ..core.determinism import kahan_sum, round_float

logger = logging.getLogger("synapse.metrics")


def render_prometheus(
    router_stats: Optional[Dict[str, Any]] = None,
    command_counts: Optional[Dict[str, int]] = None,
    circuit_breaker_state: str = "closed",
    memory_entry_count: int = 0,
    tool_durations: Optional[Dict[str, Any]] = None,
    dispatch_waits: Optional[Dict[str, Any]] = None,
    main_thread_directs: Optional[Dict[str, Any]] = None,
    scene_hashes: Optional[Dict[str, Any]] = None,
    panel_inlines: Optional[Dict[str, Any]] = None,
    live_snapshot: Optional[Dict[str, Any]] = None,
) -> str:
    """Render metrics in Prometheus text exposition format.

    Args:
        router_stats: Output of TieredRouter.stats()
        command_counts: Dict mapping command type to call count
        circuit_breaker_state: Current circuit breaker state string
        memory_entry_count: Number of entries in memory store
        tool_durations: Per-tool duration stats {tool: {count, sum_ms, buckets}}
        dispatch_waits: run_on_main enqueue→start wait histogram
            {count, sum_ms, max_ms, buckets} (C6 — attributes the dispatch floor)
        main_thread_directs: main-thread DIRECT-path fn() duration histogram
            {count, sum_ms, max_ms, buckets} (C6 — the inline panel/bridge path
            the dispatch-wait histogram never samples)
        scene_hashes: scene-hash (R1 stage-integrity) duration histogram
            {count, sum_ms, max_ms, buckets} — the Flatten floor on stage ops
        panel_inlines: panel inline (main-thread Qt) tool-dispatch summary
            {count, sum_ms, max_ms, slow_count, slowest_tool} (no buckets)
        live_snapshot: Optional MetricSnapshot dict from MetricsAggregator

    Returns:
        Prometheus-formatted text string.
    """
    lines = []

    # Tier request counts and latencies
    if router_stats:
        lines.append("# HELP synapse_tier_requests_total Total requests per routing tier")
        lines.append("# TYPE synapse_tier_requests_total counter")
        tiers = router_stats.get("tiers", {})
        for tier_name, tier_data in sorted(tiers.items()):
            count = tier_data.get("count", 0)
            lines.append(f'synapse_tier_requests_total{{tier="{tier_name}"}} {count}')

        lines.append("")
        lines.append("# HELP synapse_tier_latency_avg_ms Average latency per tier in milliseconds")
        lines.append("# TYPE synapse_tier_latency_avg_ms gauge")
        for tier_name, tier_data in sorted(tiers.items()):
            avg = tier_data.get("avg_ms", 0)
            lines.append(f'synapse_tier_latency_avg_ms{{tier="{tier_name}"}} {round_float(avg)}')

        lines.append("")
        lines.append("# HELP synapse_routes_total Total routed requests")
        lines.append("# TYPE synapse_routes_total counter")
        lines.append(f"synapse_routes_total {router_stats.get('total_routes', 0)}")

    # Per-command-type counts
    if command_counts:
        lines.append("")
        lines.append("# HELP synapse_commands_total Total commands by type")
        lines.append("# TYPE synapse_commands_total counter")
        for cmd_type, count in sorted(command_counts.items()):
            lines.append(f'synapse_commands_total{{type="{cmd_type}"}} {count}')

    # Circuit breaker state
    lines.append("")
    lines.append("# HELP synapse_circuit_breaker_state Current circuit breaker state (0=closed, 1=open, 2=half_open)")
    lines.append("# TYPE synapse_circuit_breaker_state gauge")
    state_map = {"closed": 0, "open": 1, "half_open": 2}
    lines.append(f"synapse_circuit_breaker_state {state_map.get(circuit_breaker_state, 0)}")

    # Memory store size
    lines.append("")
    lines.append("# HELP synapse_memory_entries_total Total entries in memory store")
    lines.append("# TYPE synapse_memory_entries_total gauge")
    lines.append(f"synapse_memory_entries_total {memory_entry_count}")

    # Per-tool call duration histogram (Mile 0 observability spine)
    if tool_durations:
        lines.append("")
        lines.append("# HELP synapse_tool_duration_ms Per-tool call duration in milliseconds")
        lines.append("# TYPE synapse_tool_duration_ms histogram")
        for tool, rec in sorted(tool_durations.items()):
            buckets = rec.get("buckets", {})
            for le in sorted(buckets, key=float):
                lines.append(
                    f'synapse_tool_duration_ms_bucket{{tool="{tool}",le="{le}"}} {buckets[le]}'
                )
            count = rec.get("count", 0)
            lines.append(
                f'synapse_tool_duration_ms_bucket{{tool="{tool}",le="+Inf"}} {count}'
            )
            lines.append(
                f'synapse_tool_duration_ms_sum{{tool="{tool}"}} {round_float(rec.get("sum_ms", 0.0))}'
            )
            lines.append(f'synapse_tool_duration_ms_count{{tool="{tool}"}} {count}')

    # run_on_main dispatch-wait histogram (C6 — the floor-attribution instrument).
    # Separates enqueue→callback-start wake latency from handler/hou work so the
    # "~2s mutation floor" can finally be attributed (T1 wake / T2 contention / T3
    # transport) instead of asserted.
    if dispatch_waits and dispatch_waits.get("count", 0) > 0:
        lines.append("")
        lines.append("# HELP synapse_dispatch_wait_ms run_on_main enqueue-to-start wait in milliseconds")
        lines.append("# TYPE synapse_dispatch_wait_ms histogram")
        buckets = dispatch_waits.get("buckets", {})
        for le in sorted(buckets, key=float):
            lines.append(f'synapse_dispatch_wait_ms_bucket{{le="{le}"}} {buckets[le]}')
        count = dispatch_waits.get("count", 0)
        lines.append(f'synapse_dispatch_wait_ms_bucket{{le="+Inf"}} {count}')
        lines.append(f'synapse_dispatch_wait_ms_sum {round_float(dispatch_waits.get("sum_ms", 0.0))}')
        lines.append(f'synapse_dispatch_wait_ms_count {count}')
        lines.append(f'synapse_dispatch_wait_ms_max {round_float(dispatch_waits.get("max_ms", 0.0))}')

    # Main-thread DIRECT-path fn() duration histogram (C6 continued). The dominant
    # panel/bridge path runs INLINE on the main thread and short-circuits
    # run_on_main, so the dispatch-wait histogram never samples it — count stays 0
    # on the path that matters. This surfaces that path's fn() duration so it is
    # finally attributed. Mirrors the dispatch_wait export.
    if main_thread_directs and main_thread_directs.get("count", 0) > 0:
        lines.append("")
        lines.append("# HELP synapse_main_thread_direct_ms Main-thread direct-path fn() duration in milliseconds")
        lines.append("# TYPE synapse_main_thread_direct_ms histogram")
        buckets = main_thread_directs.get("buckets", {})
        for le in sorted(buckets, key=float):
            lines.append(f'synapse_main_thread_direct_ms_bucket{{le="{le}"}} {buckets[le]}')
        count = main_thread_directs.get("count", 0)
        lines.append(f'synapse_main_thread_direct_ms_bucket{{le="+Inf"}} {count}')
        lines.append(f'synapse_main_thread_direct_ms_sum {round_float(main_thread_directs.get("sum_ms", 0.0))}')
        lines.append(f'synapse_main_thread_direct_ms_count {count}')
        lines.append(f'synapse_main_thread_direct_ms_max {round_float(main_thread_directs.get("max_ms", 0.0))}')

    # Scene-hash (R1 stage-integrity) duration histogram — the Flatten floor on
    # stage-touching ops. Same shape as dispatch_wait; mirrors its export.
    if scene_hashes and scene_hashes.get("count", 0) > 0:
        lines.append("")
        lines.append("# HELP synapse_scene_hash_ms Scene-hash (stage-integrity) duration in milliseconds")
        lines.append("# TYPE synapse_scene_hash_ms histogram")
        buckets = scene_hashes.get("buckets", {})
        for le in sorted(buckets, key=float):
            lines.append(f'synapse_scene_hash_ms_bucket{{le="{le}"}} {buckets[le]}')
        count = scene_hashes.get("count", 0)
        lines.append(f'synapse_scene_hash_ms_bucket{{le="+Inf"}} {count}')
        lines.append(f'synapse_scene_hash_ms_sum {round_float(scene_hashes.get("sum_ms", 0.0))}')
        lines.append(f'synapse_scene_hash_ms_count {count}')
        lines.append(f'synapse_scene_hash_ms_max {round_float(scene_hashes.get("max_ms", 0.0))}')

    # Panel inline (main-thread Qt slot) tool-dispatch duration. The accessor
    # tracks count/sum/max + a slow-op count (no buckets), so it exports as a
    # Prometheus summary plus a slow-op counter — the freeze-attribution signal,
    # labelled with the slowest contributing tool.
    if panel_inlines and panel_inlines.get("count", 0) > 0:
        lines.append("")
        lines.append("# HELP synapse_panel_inline_ms Panel inline (main-thread Qt) tool-dispatch duration in milliseconds")
        lines.append("# TYPE synapse_panel_inline_ms summary")
        count = panel_inlines.get("count", 0)
        lines.append(f'synapse_panel_inline_ms_sum {round_float(panel_inlines.get("sum_ms", 0.0))}')
        lines.append(f'synapse_panel_inline_ms_count {count}')
        lines.append(f'synapse_panel_inline_ms_max {round_float(panel_inlines.get("max_ms", 0.0))}')
        lines.append("# HELP synapse_panel_inline_slow_total Inline tool dispatches over the slow threshold")
        lines.append("# TYPE synapse_panel_inline_slow_total counter")
        slowest = panel_inlines.get("slowest_tool") or ""
        lines.append(f'synapse_panel_inline_slow_total{{slowest_tool="{slowest}"}} {panel_inlines.get("slow_count", 0)}')

    # Live metrics (Sprint E) — scene, session, uptime
    if live_snapshot:
        scene = live_snapshot.get("scene", {})
        session = live_snapshot.get("session", {})
        resilience = live_snapshot.get("resilience", {})

        lines.append("")
        lines.append("# HELP synapse_scene_nodes_total Total nodes in Houdini scene")
        lines.append("# TYPE synapse_scene_nodes_total gauge")
        lines.append(f"synapse_scene_nodes_total {scene.get('total_nodes', 0)}")

        lines.append("")
        lines.append("# HELP synapse_scene_warnings Nodes with warnings")
        lines.append("# TYPE synapse_scene_warnings gauge")
        lines.append(f"synapse_scene_warnings {scene.get('warnings', 0)}")

        lines.append("")
        lines.append("# HELP synapse_scene_errors Nodes with errors")
        lines.append("# TYPE synapse_scene_errors gauge")
        lines.append(f"synapse_scene_errors {scene.get('errors', 0)}")

        lines.append("")
        lines.append("# HELP synapse_sessions_active Active user sessions")
        lines.append("# TYPE synapse_sessions_active gauge")
        lines.append(f"synapse_sessions_active {session.get('active_sessions', 0)}")

        lines.append("")
        lines.append("# HELP synapse_commands_per_minute Command throughput")
        lines.append("# TYPE synapse_commands_per_minute gauge")
        lines.append(f"synapse_commands_per_minute {round_float(session.get('commands_per_minute', 0.0))}")

        lines.append("")
        lines.append("# HELP synapse_uptime_seconds Aggregator uptime in seconds")
        lines.append("# TYPE synapse_uptime_seconds gauge")
        lines.append(f"synapse_uptime_seconds {round_float(resilience.get('uptime_seconds', 0.0))}")

    lines.append("")
    return "\n".join(lines)
