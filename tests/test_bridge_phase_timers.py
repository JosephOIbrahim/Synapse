"""R302 rank 6 — the shared T4 instrument: non-saturating phase timers.

Before this change shared/bridge.py carried exactly ONE perf_counter pair
(the _compute_scene_hash wrapper), so the other T4 scale terms were
unobservable by construction:

  - _verify_composition — the Scene Integrity anchor's full-stage traversal
    per stage-touching op, main-thread time inside the open undo group
    (H3: the second-largest scale term, zero timing)
  - _infer_stage_touch — the R7 dependents() blast-radius trace, once per
    bridge op, scaling with the target container's NODE count (H2 axis)

BUCKET DESIGN IS THE POINT (G4, harness/latency/LEDGER.md §5): every
pre-existing histogram saturates at a finite 4000-5000 ms top edge, so a
6,900 ms sample increments NO in-memory bucket — the mechanism by which the
6.9-7.7 s/op regime hid inside a "1-70 ms" ledger. The new ladder resolves
0.1 ms .. 60 s and ends in +Inf: every sample lands in an in-memory bucket.

These tests pin: the exact bucket edges, the non-saturating property (a
7 s sample lands in a finite bucket; a 100 s sample still lands in +Inf),
recording through the REAL wrappers on both execute paths, and the additive
surfacing through telemetry_dump + render_prometheus.
"""

from types import SimpleNamespace

import shared.bridge as b
from shared.bridge import LosslessExecutionBridge, Operation
from shared.types import AgentID


# ── the pinned bucket ladder ────────────────────────────────────

EXPECTED_EDGES = (
    0.1, 0.25, 0.5, 1, 2.5, 5, 10, 25, 50, 100, 250, 500,
    1000, 2500, 5000, 10000, 25000, 60000, float("inf"),
)


def test_phase_bucket_edges_pinned():
    """The ladder resolves 0.1ms..60s and ends in +Inf. A silent edit that
    re-saturates the top (the G4 defect class) fails here loudly."""
    assert b._BRIDGE_PHASE_BUCKETS_MS == EXPECTED_EDGES
    assert b._BRIDGE_PHASE_BUCKETS_MS[-1] == float("inf"), (
        "the ladder must end in +Inf — a finite top edge is exactly how the "
        "6.9-7.7s regime hid inside the scene_hash histogram (G4)")
    assert b._BRIDGE_PHASE_BUCKETS_MS[0] <= 0.1
    # 60s must be resolvable by a FINITE edge (not only by +Inf).
    finite = [e for e in b._BRIDGE_PHASE_BUCKETS_MS if e != float("inf")]
    assert max(finite) >= 60000


def test_phase_histogram_is_non_saturating():
    """The regression the old ladder had: a sample in the 6.9-7.7s regime
    must increment a FINITE bucket, and even an absurd sample must land in
    the in-memory +Inf bucket (count is not its only trace)."""
    b.reset_composition_stats()
    try:
        b._record_composition_ms(7000.0)  # the BRIDGE-FLOOR regime
        s = b.composition_stats()
        assert s["buckets"][10000] == 1, (
            "a 7s sample must land in a finite bucket — on the old "
            "4000ms-top ladder it incremented nothing")
        assert s["buckets"][float("inf")] == 1

        b._record_composition_ms(100_000.0)  # beyond every finite edge
        s = b.composition_stats()
        assert s["buckets"][float("inf")] == 2, (
            "a sample beyond the top finite edge must still land in the "
            "in-memory +Inf bucket")
        assert s["count"] == 2
        assert s["max_ms"] == 100_000.0
    finally:
        b.reset_composition_stats()


def test_phase_histogram_cumulative_recording():
    """Same cumulative <= semantics as every other house histogram."""
    b.reset_stage_touch_stats()
    try:
        b._record_stage_touch_ms(3.0)
        s = b.stage_touch_stats()
        assert s["buckets"][2.5] == 0
        assert s["buckets"][5] == 1
        assert s["buckets"][60000] == 1
        assert s["buckets"][float("inf")] == 1
    finally:
        b.reset_stage_touch_stats()


# ── recording through the REAL wrappers ────────────────────────

def _op(fn, **kw):
    return Operation(
        agent_id=AgentID.HANDS,
        operation_type="create_node",  # INFORM — consent short-circuits
        summary="phase timer test",
        fn=fn,
        **kw,
    )


def test_infer_stage_touch_records_on_execute(monkeypatch):
    """Every execute() samples the stage_touch histogram — including the
    standalone path (the wrapper sits at the definition, so every call site
    is covered by construction)."""
    monkeypatch.setattr(b, "_HOU_AVAILABLE", False)
    b.reset_stage_touch_stats()
    try:
        bridge = LosslessExecutionBridge()
        res = bridge.execute(_op(lambda: None))
        assert res.success
        s = b.stage_touch_stats()
        assert s["count"] == 1
        assert s["buckets"][float("inf")] == 1
    finally:
        b.reset_stage_touch_stats()


def test_verify_composition_records_duration(monkeypatch):
    """A direct _verify_composition call records exactly one sample, and the
    verdict is unchanged by the timing wrapper."""
    monkeypatch.setattr(b, "_HOU_AVAILABLE", False)
    b.reset_composition_stats()
    try:
        bridge = LosslessExecutionBridge()
        assert bridge._verify_composition("/stage/x") is True
        s = b.composition_stats()
        assert s["count"] == 1
        assert s["sum_ms"] >= 0.0
    finally:
        b.reset_composition_stats()


def test_verify_composition_records_on_stage_touching_execute(monkeypatch):
    """The sync execute path samples the composition histogram exactly once
    per stage-touching op."""

    class _FakeUndos:
        def group(self, label):
            class _Ctx:
                def __enter__(ctx):
                    return ctx

                def __exit__(ctx, *args):
                    return False

            return _Ctx()

        def performUndo(self):
            pass

    class _FakeNode:
        def children(self):
            return []

        def cookCount(self):
            return 0

        def geometry(self):
            return None

    fake_hou = SimpleNamespace(
        undos=_FakeUndos(),
        node=lambda path: _FakeNode(),
        LopNode=type("LopNode", (), {}),
    )
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", fake_hou)

    b.reset_composition_stats()
    try:
        bridge = LosslessExecutionBridge()
        res = bridge.execute(
            _op(lambda: None, touches_stage=True, stage_path="/stage/l"))
        assert res.success
        assert b.composition_stats()["count"] == 1
    finally:
        b.reset_composition_stats()


# ── surfacing: telemetry_dump + prometheus (additive keys) ──────

def test_collect_telemetry_carries_phase_sections():
    from synapse.server.telemetry_dump import collect_telemetry

    b.reset_composition_stats()
    b.reset_stage_touch_stats()
    try:
        b._record_composition_ms(1.0)
        b._record_stage_touch_ms(2.0)
        out = collect_telemetry()
        assert out["composition"]["count"] == 1
        assert out["stage_touch"]["count"] == 1
        # Additive: the pre-existing sections are untouched.
        assert "scene_hash" in out
    finally:
        b.reset_composition_stats()
        b.reset_stage_touch_stats()


def test_render_prometheus_exports_phase_histograms():
    from synapse.server.metrics import render_prometheus

    stats = {
        "count": 2,
        "sum_ms": 7001.0,
        "max_ms": 7000.0,
        "buckets": {e: 0 for e in EXPECTED_EDGES},
    }
    stats["buckets"][10000] = 1
    stats["buckets"][25000] = 1
    stats["buckets"][60000] = 1
    stats["buckets"][float("inf")] = 2

    text = render_prometheus(compositions=stats, stage_touches=stats)
    assert 'synapse_composition_ms_bucket{le="10000"} 1' in text
    assert 'synapse_composition_ms_bucket{le="+Inf"} 2' in text
    assert "synapse_composition_ms_count 2" in text
    assert 'synapse_stage_touch_ms_bucket{le="+Inf"} 2' in text
    # The in-memory inf edge must NOT leak as a duplicate le="inf" line.
    assert 'le="inf"' not in text


def test_render_prometheus_silent_when_phase_stats_empty():
    from synapse.server.metrics import render_prometheus

    text = render_prometheus()
    assert "synapse_composition_ms" not in text
    assert "synapse_stage_touch_ms" not in text
