"""F6 hygiene bundle (freeze-relief, 2026-08-14).

Pins the six F6 items from docs/reviews/ui-freeze-fix-spec-2026-08-14.md.
Standalone (no hou): the run_on_main call sites are exercised via
monkeypatched marshals; the USD walk bound is a source-structure pin (the
walk itself needs a live pxr stage); the timeout/read-only entries are
pure table lookups.

Items:
  1. live_metrics scene-gather calls run_on_main with record_stall=False
     (stall detector stays a measure of REAL commands).
  2. handlers_usd._walk is visit-counter bounded, not results-only.
  3. reference_usd has a 30s entry in core/timeouts and the marshal reads
     it via timeout_for.
  4. houdini_capture_viewport is a known-slow tool.
  5. WS _handle_inspect_scene marshals at timeout_for("inspect_scene")=30s
     (matches /mcp).
  6. read-only reconciliation counts documented are live-derived; the
     divergence membership is pinned so the sets cannot silently re-diverge.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(_ROOT / "python"))

from synapse.core import timeouts  # noqa: E402


# ── Item 1: live_metrics scene gather is stall-opted-out ─────────────────

def test_live_metrics_scene_gather_not_stall_recorded(monkeypatch):
    """The 2s telemetry gather must NOT feed the stall detector that
    fast-fails real commands (F6 item 1; crucible mitigation: the F4
    in-flight register still observes the gather's hold via its label)."""
    import types

    from synapse.server import live_metrics

    calls = []

    def _fake_run_on_main(fn, timeout=None, record_stall=True, record_wait=True,
                          label=None):
        calls.append({
            "timeout": timeout,
            "record_stall": record_stall,
            "label": label,
        })
        # Do NOT invoke fn(): that closure touches the real hou API.
        return "gathered"

    # _collect_scene imports hou first; a bare stub module satisfies the
    # import while the fake marshal never runs the hou-touching closure.
    monkeypatch.setitem(sys.modules, "hou", types.ModuleType("hou"))
    import synapse.server.main_thread as mt
    monkeypatch.setattr(mt, "run_on_main", _fake_run_on_main)

    result = live_metrics.MetricsAggregator()._collect_scene()

    assert result == "gathered"
    assert calls, "run_on_main was never called"
    assert calls[0]["record_stall"] is False
    assert calls[0]["label"] == "live_metrics:_collect_scene"


# ── Item 2: query_prims walk is visit-bounded ────────────────────────────

def test_query_prims_walk_visit_counter_source():
    """Source pin: the walk stops on a visit bound, and 'truncated' covers
    the visit cap as well as the results limit. (The walk itself needs a
    live pxr stage; structure pinned here, behavior verified live.)"""
    src = (_ROOT / "python" / "synapse" / "server" / "handlers_usd.py").read_text(
        encoding="utf-8"
    )
    assert "_MAX_WALK_VISITS = 25000" in src
    assert "visits[0] >= _MAX_WALK_VISITS" in src
    assert "visits[0] += 1" in src
    assert 'len(results) >= limit or visits[0] >= _MAX_WALK_VISITS' in src


# ── Item 3: reference_usd budget owned by core/timeouts ──────────────────

def test_reference_usd_timeout_table():
    assert timeouts.SLOW_COMMANDS["reference_usd"] == 30.0
    # MCP tool name resolves via houdini_ prefix-stripping to the same entry.
    assert timeouts.timeout_for("reference_usd") == 30.0
    assert timeouts.timeout_for("houdini_reference_usd") == 30.0
    # Marshal site reads the table, never a parallel constant.
    src = (_ROOT / "python" / "synapse" / "server" / "handlers_usd.py").read_text(
        encoding="utf-8"
    )
    assert 'timeout=timeout_for("reference_usd")' in src


# ── Item 4: viewport capture flagged as known-slow ───────────────────────

def test_capture_viewport_is_known_slow():
    from synapse.panel.bridge_adapter import _KNOWN_SLOW_TOOLS
    assert "houdini_capture_viewport" in _KNOWN_SLOW_TOOLS


# ── Item 5: WS inspect_scene marshal matches the /mcp 30s budget ─────────

def test_inspect_scene_ws_marshal_budget():
    assert timeouts.timeout_for("inspect_scene") == 30.0
    src = (_ROOT / "python" / "synapse" / "server" / "handlers.py").read_text(
        encoding="utf-8"
    )
    assert 'timeout=timeout_for("inspect_scene")' in src
    assert 'label="handlers:_handle_inspect_scene"' in src


# ── Item 6: read-only divergence membership pinned (counts re-derived) ───

def test_read_only_divergence_membership_pinned():
    """The four tools read-only to the transport but MUTATING to the bridge.
    If either set changes, this fails loud instead of drifting silently.
    Membership (not the count) is the authority: the doc comment is a
    snapshot, read_only_set_divergence() recomputes live."""
    pytest.importorskip("synapse.panel.bridge_adapter")
    from synapse.mcp.server import read_only_set_divergence

    assert set(read_only_set_divergence()) == {
        "cops_temporal_analysis",
        "synapse_propose_graph",
        "synapse_render_processes",
        "synapse_validate_frame",
    }
