"""R306: the honesty fields get CONSUMERS.

Commit 98b556f taught the IntegrityBlock to say when the R1 stage-hash size gate
degraded observation (``stage_hash_mode`` / ``stage_hash_full_fidelity`` /
``composition_checks_reduced``). A repo-wide grep then found no reader outside
``shared/bridge.py``, the deployment doc, and tests: honest at the point of
record, dead at the point of use. R306 gives them two readers and pins the
boundary the ruling drew around them.

Pinned here:

  1. ``operation_stats()`` counts reduced-mode ops — ADDITIVELY (the §16.2
     pre-existing key set is unchanged, proved in
     ``tests/test_live_integrity_envelope.py::test_operation_stats_keys_unchanged``).
  2. The counters are LIFETIME: log eviction / clear_operation_log() cannot age
     a session's blind spots out of the count.
  3. A degraded op that ALSO FAILED is still counted — the failure path appends
     through ``_fail_with_integrity``, so a silent drop there would hide exactly
     the ops most worth seeing.
  4. Exactly one tally per operation — no double count across the
     finalize / fail / live-envelope append sites.
  5. ``SessionIntegrityTracker`` counts the blind-spot case under its own label
     instead of it being invisible: reduced mode AND ``delta_hash="no_change"``
     means "this algorithm could not see a change", not "nothing changed".
  6. THE OUT-OF-SCOPE GUARD (R306 names it explicitly): none of this moves
     ``fidelity``. An honest reduction is not a pipeline bug; lowering fidelity
     is a contract amendment, not a rider on a surfacing lane. If a future edit
     folds reduced-mode into violations or fidelity, test 6 fails loudly.

The pxr-backed end-to-end tests skip when pxr is unavailable; the counter and
tracker contracts are proved with no pxr and no Qt.
"""

import os
import sys

import pytest

import shared.bridge as b
from shared.bridge import IntegrityBlock, LosslessExecutionBridge, Operation
from shared.types import AgentID

# Editable install resolves `synapse` -> python/synapse under stock CPython.
# Same purge idiom as tests/test_session_integrity_summary.py: hython launches
# with CWD=repo root where a sibling `synapse/` NAMESPACE dir shadows
# python/synapse. No-op under stock CPython.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PY = os.path.join(_ROOT, "python")
if _PY not in sys.path:
    sys.path.insert(0, _PY)
_cached = sys.modules.get("synapse")
if _cached is not None and getattr(_cached, "__file__", None) is None:
    for _m in [k for k in list(sys.modules)
               if k == "synapse" or k.startswith("synapse.")]:
        del sys.modules[_m]

from synapse.panel.session_integrity import SessionIntegrityTracker  # noqa: E402


# ── block builders (no pxr, no hou) ────────────────────────────

def _block(*, reduced=False, comp_reduced=False, verified=True,
           delta="abc123") -> IntegrityBlock:
    """A live-envelope-shaped block with the R306 flags set explicitly.

    ``verified=False`` breaks an anchor so fidelity < 1.0 — used to prove a
    degraded op is counted on the violation path too.
    """
    return IntegrityBlock(
        undo_group_active=True,
        main_thread_executed=verified,
        consent_verified=True,
        composition_valid=True,
        agent_id=AgentID.HANDS.value,
        operation_type="create_node",
        timestamp="2026-08-02T00:00:00",
        scene_hash_before="aaaa",
        scene_hash_after="bbbb",
        delta_hash=delta,
        stage_hash_mode="reduced" if reduced else "full",
        stage_hash_full_fidelity=not reduced,
        composition_checks_reduced=comp_reduced,
    )


# ── 1. operation_stats() counts reduced-mode ops ────────────────

class TestOperationStatsCounters:
    def test_clean_session_reports_zero(self):
        stats = LosslessExecutionBridge().operation_stats()
        assert stats["stage_hash_reduced_ops"] == 0
        assert stats["composition_checks_reduced_ops"] == 0

    def test_full_fidelity_ops_never_counted(self):
        bridge = LosslessExecutionBridge()
        for _ in range(3):
            bridge.record_external_block(_block())
        stats = bridge.operation_stats()
        assert stats["operations_total"] == 3
        assert stats["stage_hash_reduced_ops"] == 0
        assert stats["composition_checks_reduced_ops"] == 0

    def test_reduced_stage_hash_counted(self):
        bridge = LosslessExecutionBridge()
        bridge.record_external_block(_block(reduced=True))
        bridge.record_external_block(_block())          # full — not counted
        bridge.record_external_block(_block(reduced=True))
        assert bridge.operation_stats()["stage_hash_reduced_ops"] == 2

    def test_composition_shed_counted_independently(self):
        """The two flags are separate observations: a stage can shed the
        composition sweep while the hash itself ran full, and vice versa."""
        bridge = LosslessExecutionBridge()
        bridge.record_external_block(_block(comp_reduced=True))
        stats = bridge.operation_stats()
        assert stats["composition_checks_reduced_ops"] == 1
        assert stats["stage_hash_reduced_ops"] == 0

    def test_exactly_one_tally_per_operation(self):
        bridge = LosslessExecutionBridge()
        for _ in range(7):
            bridge.record_external_block(_block(reduced=True, comp_reduced=True))
        stats = bridge.operation_stats()
        assert stats["operations_total"] == 7
        assert stats["stage_hash_reduced_ops"] == 7
        assert stats["composition_checks_reduced_ops"] == 7

    def test_degraded_block_still_counted(self):
        """A reduced-mode op that also violated an anchor must not vanish from
        the reduced count — the failure path is where blind spots matter most."""
        bridge = LosslessExecutionBridge()
        bridge.record_external_block(_block(reduced=True, verified=False))
        stats = bridge.operation_stats()
        assert stats["anchor_violations"] == 1
        assert stats["operations_verified"] == 0
        assert stats["stage_hash_reduced_ops"] == 1

    def test_counters_are_lifetime_not_log_scoped(self):
        """Bounded log + clear_operation_log() cap IntegrityBlock DETAIL, not
        aggregate counters (same rule as the per-agent counters, §16.4)."""
        bridge = LosslessExecutionBridge(log_max_size=2)
        for _ in range(5):
            bridge.record_external_block(_block(reduced=True))
        assert bridge.operation_stats()["log_size"] == 2      # evicted
        assert bridge.operation_stats()["stage_hash_reduced_ops"] == 5
        bridge.clear_operation_log()
        assert bridge.operation_stats()["log_size"] == 0
        assert bridge.operation_stats()["stage_hash_reduced_ops"] == 5


# ── 2. end-to-end through the real execute path (pxr) ───────────

def _real_stage_env(monkeypatch, n_prims):
    """Fake hou around a REAL pxr stage — the multiclient pattern used by
    tests/test_stage_hash_honesty.py. Threshold 3 so a tiny stage trips the
    gate. Returns the stage."""
    pytest.importorskip("pxr")
    from pxr import Sdf, Usd

    class _FakeUndos:
        def group(self, label):
            class _Ctx:
                def __enter__(ctx):
                    return ctx

                def __exit__(ctx, *a):
                    return False
            return _Ctx()

    class _FakeLop:
        def __init__(self, stage):
            self._stage = stage

        def children(self):
            return []

        def cookCount(self):
            return 0

        def geometry(self):
            return None

        def stage(self):
            return self._stage

    class _FakeHou:
        def __init__(self, node):
            self._node = node
            self.undos = _FakeUndos()
            self.LopNode = type("LopNode", (), {})

        def node(self, path):
            return self._node

    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/root", "Xform")
    stage.SetDefaultPrim(root)
    for i in range(n_prims):
        p = stage.DefinePrim("/root/p%d" % i, "Sphere")
        p.CreateAttribute("radius", Sdf.ValueTypeNames.Double).Set(1.0)

    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "3")
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)
    monkeypatch.setattr(b, "hou", _FakeHou(_FakeLop(stage)))
    return stage


def _op(fn, **kw):
    return Operation(agent_id=AgentID.HANDS, operation_type="create_node",
                     summary="R306 surfacing test", fn=fn, **kw)


class TestEndToEnd:
    def test_below_threshold_leaves_counters_at_zero(self, monkeypatch):
        stage = _real_stage_env(monkeypatch, 1)      # 2 prims < 3
        bridge = LosslessExecutionBridge()
        res = bridge.execute(_op(lambda: stage.DefinePrim("/root/new", "Cube")))
        assert res.success
        assert res.integrity.stage_hash_full_fidelity is True
        assert bridge.operation_stats()["stage_hash_reduced_ops"] == 0

    def test_value_only_edit_above_threshold_is_visible_in_stats(self, monkeypatch):
        """THE blind-spot case, end to end: a value-only edit above threshold
        reads delta "no_change" because the reduced signature never reads
        values. Before R306 the op finalized verified/1.0 with nothing anywhere
        saying the observation was degraded. Now the stats say it."""
        stage = _real_stage_env(monkeypatch, 10)
        bridge = LosslessExecutionBridge()
        res = bridge.execute(_op(
            lambda: stage.GetPrimAtPath("/root/p0")
            .GetAttribute("radius").Set(99.0)))
        assert res.success
        assert res.integrity.delta_hash == "no_change"
        assert res.integrity.stage_hash_full_fidelity is False
        assert bridge.operation_stats()["stage_hash_reduced_ops"] == 1

    def test_composition_shed_reaches_stats(self, monkeypatch):
        stage = _real_stage_env(monkeypatch, 10)
        bridge = LosslessExecutionBridge()
        res = bridge.execute(_op(
            lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
        assert res.success
        assert res.integrity.composition_checks_reduced is True
        assert bridge.operation_stats()["composition_checks_reduced_ops"] == 1

    def test_failed_reduced_op_counted_via_fail_path(self, monkeypatch):
        """The op hashes reduced (mode recorded BEFORE fn runs), then raises →
        the block lands via _fail_with_integrity. It must still be counted."""
        _real_stage_env(monkeypatch, 10)
        bridge = LosslessExecutionBridge()

        def _boom():
            raise RuntimeError("op failed after the reduced hash")

        res = bridge.execute(_op(_boom))
        assert res.success is False
        assert res.integrity.stage_hash_full_fidelity is False
        assert bridge.operation_stats()["stage_hash_reduced_ops"] == 1


# ── 3. the session tracker stops hiding the blind spot ──────────

def _tracker_block(*, reduced=False, delta="abc123", fidelity=1.0):
    """The dict shape the tracker actually receives: IntegrityBlock.to_dict()
    via panel/bridge_adapter.py:396."""
    return {
        "operation": "set_parameter",
        "fidelity": fidelity,
        "delta_hash": delta,
        "stage_hash_mode": "reduced" if reduced else "full",
        "stage_hash_full_fidelity": not reduced,
    }


class TestSessionTracker:
    def test_blind_spot_case_is_counted_not_discarded(self):
        tr = SessionIntegrityTracker()
        tr.record(_tracker_block(reduced=True, delta="no_change"))
        s = tr.summary()
        assert s["unobservable_deltas"] == 1
        assert s["reduced_fidelity"] == 1
        assert tr.unobservable_delta_count == 1
        # counted, and counted as ITSELF — not as a violation, not as a mutation
        assert s["total"] == 1
        assert s["violations"] == 0

    def test_full_fidelity_no_change_is_not_a_blind_spot(self):
        """delta "no_change" under a FULL hash is a genuine no-op — the
        algorithm looked and saw nothing. Counting that as unobservable would
        be alarm fatigue, the mirror-image dishonesty."""
        tr = SessionIntegrityTracker()
        tr.record(_tracker_block(reduced=False, delta="no_change"))
        s = tr.summary()
        assert s["unobservable_deltas"] == 0
        assert s["reduced_fidelity"] == 0

    def test_reduced_with_observed_delta_is_not_unobservable(self):
        """Reduced mode DID see a structural change — degraded observation,
        but the delta itself was observed."""
        tr = SessionIntegrityTracker()
        tr.record(_tracker_block(reduced=True, delta="deadbeef"))
        s = tr.summary()
        assert s["reduced_fidelity"] == 1
        assert s["unobservable_deltas"] == 0

    def test_legacy_block_without_the_fields_is_safe(self):
        """Blocks predating 98b556f (and the Mile-4 test shape) carry neither
        field — absent must mean full fidelity, never a false blind-spot."""
        tr = SessionIntegrityTracker()
        tr.record({"operation": "create_node", "fidelity": 1.0})
        s = tr.summary()
        assert s["unobservable_deltas"] == 0
        assert s["reduced_fidelity"] == 0
        assert s["total"] == 1

    def test_summary_keys_are_additive(self):
        """The Mile-4 honesty contract (has_data et al.) is untouched; R306
        only adds."""
        assert set(SessionIntegrityTracker().summary()) == {
            "total", "verified", "violations", "fidelity", "has_data",
            "should_warn", "reduced_fidelity", "unobservable_deltas",
        }

    def test_blind_spot_never_moves_fidelity(self):
        """R306's EXPLICIT out-of-scope boundary. Ten unobservable deltas leave
        session fidelity at 1.0 and should_warn False. Making these fields lower
        fidelity is a contract amendment requiring its own ratification — if a
        future edit does it as a rider, this test fails."""
        tr = SessionIntegrityTracker()
        for _ in range(10):
            tr.record(_tracker_block(reduced=True, delta="no_change"))
        s = tr.summary()
        assert s["unobservable_deltas"] == 10
        assert s["fidelity"] == 1.0
        assert s["violations"] == 0
        assert s["should_warn"] is False
        assert tr.session_fidelity == 1.0

    def test_format_report_states_it_when_present(self):
        tr = SessionIntegrityTracker()
        tr.record(_tracker_block(reduced=True, delta="no_change"))
        html = tr.format_report()
        assert "reduced stage hash" in html
        assert "1 operation " in html          # singular, no plural 's'

    def test_format_report_silent_when_absent(self):
        tr = SessionIntegrityTracker()
        tr.record(_tracker_block())
        assert "reduced stage hash" not in tr.format_report()
