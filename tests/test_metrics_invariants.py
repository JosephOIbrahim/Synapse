"""Observability invariants for the Mile 0 metrics spine.

These pin the bugs that Mile 0 fixed so they cannot silently regress:
- synapse_memory_entries_total must equal the live store's count (C-3).
- the per-tool duration histogram must be a well-formed Prometheus histogram.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server.metrics import render_prometheus  # noqa: E402
from synapse.memory.store import SynapseMemory  # noqa: E402
from synapse.memory.models import MemoryType  # noqa: E402


class _FakeBridge:
    """Minimal stand-in exposing the attribute the gauge path reads."""
    def __init__(self, synapse):
        self._synapse = synapse


def test_memory_gauge_equals_store_count(tmp_path):
    """The Prometheus gauge must report the live store count, not 0.

    Regression for C-3: the gauge read a non-existent bridge attribute and
    was pinned at 0 against a populated store. The invariant is simply
    gauge == bridge._synapse.store.count().
    """
    handler = SynapseHandler()
    mem = SynapseMemory(project_path=str(tmp_path))
    for i in range(37):
        mem.add(content=f"entry {i}", memory_type=MemoryType.NOTE, source="test")

    handler._bridge = _FakeBridge(mem)  # _get_bridge() returns cached _bridge
    out = handler._handle_get_metrics({})
    text = out["text"]

    assert f"synapse_memory_entries_total {mem.store.count()}" in text
    assert "synapse_memory_entries_total 37" in text
    assert "synapse_memory_entries_total 0" not in text


def test_tool_duration_histogram_is_well_formed():
    """Per-tool histogram: cumulative buckets, +Inf == count, sum present."""
    handler = SynapseHandler()
    for ms in [3.0, 7.0, 40.0, 120.0, 600.0]:
        handler._record_tool_duration("scene_info", ms)

    stats = handler.tool_duration_stats()
    buckets = stats["scene_info"]["buckets"]
    ordered = [buckets[k] for k in sorted(buckets, key=float)]
    assert ordered == sorted(ordered)                       # monotonic cumulative
    assert max(ordered) <= stats["scene_info"]["count"]      # bounded by count

    text = render_prometheus(memory_entry_count=0, tool_durations=stats)
    assert 'synapse_tool_duration_ms_bucket{tool="scene_info",le="+Inf"} 5' in text
    assert 'synapse_tool_duration_ms_count{tool="scene_info"} 5' in text
    assert 'synapse_tool_duration_ms_sum{tool="scene_info"}' in text
