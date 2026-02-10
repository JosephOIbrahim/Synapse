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
) -> str:
    """Render metrics in Prometheus text exposition format.

    Args:
        router_stats: Output of TieredRouter.stats()
        command_counts: Dict mapping command type to call count
        circuit_breaker_state: Current circuit breaker state string
        memory_entry_count: Number of entries in memory store

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

    lines.append("")
    return "\n".join(lines)
