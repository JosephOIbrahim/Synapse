"""WS2 multi-client hardening — H1 parked-hash attribution + H2 hash-guarded rollback.

H1: the bridge parks the last computed scene hash per hash_target at op end and
compares it to the next op's scene_hash_before — a difference marks the op's
IntegrityBlock external_change_detected=True. Attribution ONLY: artists
legitimately edit between ops, so fidelity is untouched.

H2: the shared _guarded_rollback (sync _execute_houdini + async _sync_payload
exception sites) skips performUndo() when fn raised before mutating (the
CTO-review empty-group edge — performUndo would pop a foreign/artist block),
verifies the rollback actually restored the pre-op hash (else surfaces
"rollback_incomplete" honestly), and falls back to the pre-H2 unconditional
single performUndo() on sentinel hashes (which always differ and would
false-alarm). S1 (exactly ONE performUndo per failed op) stays pinned.

Idiom: patch shared.bridge MODULE globals (_HOU_AVAILABLE / hou / hdefereval),
never sys.modules — per the fake-residency trap and test_phase0c_s2_stage_hash.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shared.bridge as b  # noqa: E402
from shared.bridge import LosslessExecutionBridge, Operation  # noqa: E402
from shared.types import AgentID  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes: a node whose hash tracks _cook, and an undos that can really "undo"
# ---------------------------------------------------------------------------

class _FakeChild:
    """Child node with a stable sessionId — the topology component
    (authored-change proxy) of the undo-evidence rule."""

    _next_sid = 0

    def __init__(self):
        _FakeChild._next_sid += 1
        self._sid = _FakeChild._next_sid

    def sessionId(self):
        return self._sid

    def cookCount(self):
        return 0


class _FakeNode:
    """Minimal node: the R1 hash follows cookCount (+ children when tests
    append _FakeChild instances; empty by default so legacy hashes are
    unchanged)."""

    def __init__(self):
        self._cook = 0
        self._children = []

    def children(self):
        return list(self._children)

    def cookCount(self):
        return self._cook

    def geometry(self):
        return None


class _FakeUndos:
    """Records performUndo calls; when restores=True a rollback actually
    restores the node state captured at group entry (a real undo). With
    restores=False it simulates the undo popping the WRONG block (foreign
    interference) — state stays mutated."""

    def __init__(self, node, restores=True):
        self._node = node
        self.restores = restores
        self.undo_calls = 0
        self._pre = None

    def group(self, label):
        undos = self

        class _Ctx:
            def __enter__(ctx):
                undos._pre = undos._node._cook
                return ctx

            def __exit__(ctx, *args):
                return False

        return _Ctx()

    def performUndo(self):
        self.undo_calls += 1
        if self.restores and self._pre is not None:
            self._node._cook = self._pre


class _FakeHou:
    def __init__(self, node, undos):
        self._node = node
        self.undos = undos
        self.LopNode = type("LopNode", (), {})

    def node(self, path):
        return self._node


@pytest.fixture
def hou_env(monkeypatch):
    node = _FakeNode()
    undos = _FakeUndos(node)
    fake = _FakeHou(node, undos)
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", fake)
    return node, undos, fake


def _op(fn, summary="multiclient test"):
    # create_node is INFORM-gated — consent short-circuits before any gate.
    return Operation(
        agent_id=AgentID.HANDS,
        operation_type="create_node",
        summary=summary,
        fn=fn,
    )


# ---------------------------------------------------------------------------
# H1 — parked-hash attribution
# ---------------------------------------------------------------------------

class TestExternalChangeAttribution:
    def test_external_change_detected(self, hou_env):
        node, undos, _ = hou_env
        bridge = LosslessExecutionBridge()

        def mutate():
            node._cook += 1

        r1 = bridge.execute(_op(mutate))
        assert r1.success
        assert r1.integrity.external_change_detected is False

        # Foreign/artist edit BETWEEN ops
        node._cook += 5

        r2 = bridge.execute(_op(lambda: None))
        assert r2.success
        assert r2.integrity.external_change_detected is True
        # New field is serialized
        assert r2.integrity.to_dict()["external_change_detected"] is True

    def test_no_external_change_when_scene_untouched(self, hou_env):
        node, undos, _ = hou_env
        bridge = LosslessExecutionBridge()

        def mutate():
            node._cook += 1

        bridge.execute(_op(mutate))
        r2 = bridge.execute(_op(lambda: None))
        assert r2.integrity.external_change_detected is False

    def test_external_change_is_not_a_violation(self, hou_env):
        node, undos, _ = hou_env
        bridge = LosslessExecutionBridge()

        def mutate():
            node._cook += 1

        bridge.execute(_op(mutate))
        node._cook += 5  # foreign edit
        r2 = bridge.execute(_op(mutate))

        assert r2.success
        assert r2.integrity.external_change_detected is True
        assert r2.integrity.fidelity == 1.0  # attribution, NOT a violation
        assert bridge.operation_stats()["anchor_violations"] == 0


# ---------------------------------------------------------------------------
# H2 — hash-guarded rollback
# ---------------------------------------------------------------------------

class TestGuardedRollback:
    def test_rollback_skipped_when_no_mutation(self, hou_env):
        """fn raised before mutating: performUndo() would pop a foreign/artist
        block (the empty-group edge) — the guard must SKIP it."""
        node, undos, _ = hou_env
        bridge = LosslessExecutionBridge()

        def boom():
            raise RuntimeError("fails before mutating")

        r = bridge.execute(_op(boom))
        assert not r.success
        assert undos.undo_calls == 0
        assert r.integrity.delta_hash == "no_mutation_no_rollback"

    def test_rollback_incomplete_surfaced(self, hou_env):
        """performUndo did NOT restore the pre-op state (e.g. it popped a
        foreign block): report honestly, name the target, attribute."""
        node, undos, _ = hou_env
        undos.restores = False
        bridge = LosslessExecutionBridge()

        def mutate_then_boom():
            node._cook += 1
            raise RuntimeError("cook failed")

        r = bridge.execute(_op(mutate_then_boom))
        assert not r.success
        assert undos.undo_calls == 1
        assert r.integrity.delta_hash == "rollback_incomplete"
        assert "another MCP client" in (r.error or "")
        assert "/obj" in (r.error or "")

    def test_single_rollback_preserved(self, hou_env):
        """S1 regression: a failed mutating op performs EXACTLY ONE
        performUndo() (never zero, never a double rollback)."""
        node, undos, _ = hou_env
        bridge = LosslessExecutionBridge()

        def mutate_then_boom():
            node._cook += 1
            raise RuntimeError("cook failed")

        r = bridge.execute(_op(mutate_then_boom))
        assert not r.success
        assert undos.undo_calls == 1
        assert r.integrity.delta_hash == "rolled_back"
        assert node._cook == 0  # scene restored to pre-op state

    def test_sentinel_hash_falls_back_to_unconditional_rollback(
            self, hou_env, monkeypatch):
        """Sentinel hashes ('invalid_context' / timestamp fallback) always
        differ and would false-alarm — the guard must fall back to the pre-H2
        unconditional single performUndo() and NOT emit rollback_incomplete."""
        node, undos, fake = hou_env
        monkeypatch.setattr(fake, "node", lambda path: None)  # → invalid_context
        bridge = LosslessExecutionBridge()

        def boom():
            raise RuntimeError("fails")

        r = bridge.execute(_op(boom))
        assert not r.success
        assert undos.undo_calls == 1
        assert r.integrity.delta_hash == "rolled_back"

    def test_async_path_shares_guarded_rollback(self, hou_env, monkeypatch):
        """The async closure (_sync_payload) uses the SAME _guarded_rollback —
        the empty-group skip holds on the FastMCP path too."""
        node, undos, _ = hou_env
        monkeypatch.setattr(
            b, "hdefereval",
            SimpleNamespace(executeInMainThreadWithResult=lambda fn: fn()),
        )
        bridge = LosslessExecutionBridge()

        def boom():
            raise RuntimeError("fails before mutating")

        r = asyncio.run(bridge.execute_async(_op(boom)))
        assert not r.success
        assert undos.undo_calls == 0
        assert r.integrity.delta_hash == "no_mutation_no_rollback"

    def test_failed_op_parks_hash_for_next_attribution(self, hou_env):
        """After a rolled-back failure the post-rollback hash is parked, so a
        foreign edit after the failure is still attributed on the next op."""
        node, undos, _ = hou_env
        bridge = LosslessExecutionBridge()

        def mutate_then_boom():
            node._cook += 1
            raise RuntimeError("cook failed")

        bridge.execute(_op(mutate_then_boom))  # rolls back to _cook == 0
        node._cook += 3  # foreign edit after the failure
        r = bridge.execute(_op(lambda: None))
        assert r.integrity.external_change_detected is True


# ---------------------------------------------------------------------------
# Finding 1 — anchor flags from EVIDENCE, not self-attestation
# ---------------------------------------------------------------------------

class _FakeEvidenceUndos(_FakeUndos):
    """_FakeUndos + the H21.0.671 evidence APIs (areEnabled / undoLabels).

    ``capture=False`` models a flat undo stack after the group closes — in
    production indistinguishable from eviction at the undo memory limit or a
    non-undoable (cook-only) delta, so the evidence rule must treat it as
    INCONCLUSIVE, never a violation (CTO-pinned semantics 2026-07-10)."""

    def __init__(self, node, restores=True, enabled=True, capture=True):
        super().__init__(node, restores)
        self.enabled = enabled
        self.capture = capture
        self.labels: list[str] = []

    def areEnabled(self):
        return self.enabled

    def undoLabels(self):
        return list(self.labels)

    def group(self, label):
        undos = self

        class _Ctx:
            def __enter__(ctx):
                undos._pre = undos._node._cook
                return ctx

            def __exit__(ctx, *args):
                # A real closed group lands on the undo stack — unless undos
                # are disabled or the group captured nothing.
                if undos.enabled and undos.capture:
                    undos.labels.append(label)
                return False

        return _Ctx()


@pytest.fixture
def evidence_env(monkeypatch):
    node = _FakeNode()
    undos = _FakeEvidenceUndos(node)
    fake = _FakeHou(node, undos)
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", fake)
    return node, undos, fake


class TestUndoAnchorEvidence:
    def test_cook_delta_with_flat_undo_stack_is_inconclusive_not_violation(
            self, evidence_env, caplog):
        """CTO-pinned semantics (2026-07-10): the R1 scene hash digests
        cookCount + geo intrinsics, which shift on NON-undoable events (a
        lazy cook the op triggered, a frame change), and the undo stack
        legitimately stays flat for captured mutations (eviction at
        hou.undos.memoryUsageLimit). Flat depth + a changed hash is therefore
        INCONCLUSIVE — the anchor is KEPT (zero false violations, no phantom
        anchor_violations feeding the §16 advisor), with at most ONE warning
        per bridge instance."""
        node, undos, _ = evidence_env
        undos.capture = False  # flat stack: eviction / non-undoable delta
        bridge = LosslessExecutionBridge()

        def cook_mutate():
            node._cook += 1

        with caplog.at_level(logging.WARNING, logger="synapse.bridge"):
            r1 = bridge.execute(_op(cook_mutate))
            r2 = bridge.execute(_op(cook_mutate))

        assert r1.success and r2.success
        assert r1.integrity.undo_group_active is True
        assert r2.integrity.undo_group_active is True
        assert r1.integrity.fidelity == 1.0
        assert bridge.operation_stats()["anchor_violations"] == 0
        inconclusive = [rec for rec in caplog.records
                        if "did not grow" in rec.message]
        assert len(inconclusive) == 1  # once per bridge instance, not per op

    def test_undos_disabled_with_topology_change_is_violation(
            self, evidence_env):
        """areEnabled() False AND the topology component shifted (a child
        node was created): an authored structural change provably had no
        undo protection — the ONLY hard violation the evidence rule returns
        (CTO-pinned semantics)."""
        node, undos, _ = evidence_env
        undos.enabled = False
        bridge = LosslessExecutionBridge()

        def author():
            node._children.append(_FakeChild())

        r = bridge.execute(_op(author))
        assert r.integrity.undo_group_active is False
        assert r.integrity.fidelity < 1.0
        assert not r.success

    def test_undos_disabled_without_authored_change_keeps_anchor(
            self, evidence_env):
        """areEnabled() False but the op authored nothing structural (a
        cook-only delta — e.g. a read that lazily cooked a dirty node):
        nothing needed undo protection, the anchor is vacuously satisfied
        (CTO-pinned semantics; the previous rule hard-failed every op under
        a disabler() scope, including pure reads)."""
        node, undos, _ = evidence_env
        undos.enabled = False
        bridge = LosslessExecutionBridge()

        def cook_only():
            node._cook += 1

        r = bridge.execute(_op(cook_only))
        assert r.success
        assert r.integrity.undo_group_active is True
        assert r.integrity.fidelity == 1.0

    def test_exception_path_with_undos_disabled_records_unprotected(
            self, evidence_env):
        """F-E: the pre-group snapshot measured undos DISABLED and the op
        authored a structural change before raising (the no-op rollback
        cannot restore it) — the recorded IntegrityBlock must not claim the
        mutation was undo-protected."""
        node, undos, _ = evidence_env
        undos.enabled = False
        bridge = LosslessExecutionBridge()

        def author_then_boom():
            node._children.append(_FakeChild())
            raise RuntimeError("mutated then failed")

        r = bridge.execute(_op(author_then_boom))
        assert not r.success
        assert r.integrity.undo_group_active is False

    def test_undo_stack_growth_keeps_anchor(self, evidence_env):
        """Control: the mutation WAS captured (stack grew) — anchor holds."""
        node, undos, _ = evidence_env
        bridge = LosslessExecutionBridge()

        def mutate():
            node._cook += 1

        r = bridge.execute(_op(mutate))
        assert r.success
        assert r.integrity.undo_group_active is True
        assert r.integrity.fidelity == 1.0

    def test_evidence_unavailable_falls_back_to_true(self, hou_env):
        """Fake hou without areEnabled/undoLabels: the with-statement having
        been entered and exited without raising IS the wrap evidence — the
        pre-evidence behavior stays pinned."""
        node, undos, _ = hou_env
        assert not hasattr(undos, "undoLabels")
        bridge = LosslessExecutionBridge()

        def mutate():
            node._cook += 1

        r = bridge.execute(_op(mutate))
        assert r.success
        assert r.integrity.undo_group_active is True
        assert r.integrity.fidelity == 1.0


class TestMainThreadEvidence:
    def test_sync_execute_on_main_thread_is_true(self, hou_env):
        """bridge.execute() on the test's main thread: real evidence → True."""
        node, undos, _ = hou_env
        bridge = LosslessExecutionBridge()

        r = bridge.execute(_op(lambda: None))
        assert r.success
        assert r.integrity.main_thread_executed is True

    def test_async_payload_on_worker_thread_is_false(self, hou_env, monkeypatch):
        """Fake hdefereval runs _sync_payload on the executor WORKER thread;
        with the _on_main_thread seam unpatched the evidence honestly reads
        False → anchors fail → fidelity < 1.0."""
        node, undos, _ = hou_env
        monkeypatch.setattr(
            b, "hdefereval",
            SimpleNamespace(executeInMainThreadWithResult=lambda fn: fn()),
        )
        bridge = LosslessExecutionBridge()

        r = asyncio.run(bridge.execute_async(_op(lambda: None)))
        assert r.integrity.main_thread_executed is False
        assert r.integrity.fidelity < 1.0
        assert not r.success

    def test_async_payload_seam_patch_documents_production(
            self, hou_env, monkeypatch):
        """Production runs the payload on Houdini's main thread (hdefereval
        by construction). Tests emulate that by monkeypatching the module
        seam — the documented purpose of bridge._on_main_thread."""
        node, undos, _ = hou_env
        monkeypatch.setattr(
            b, "hdefereval",
            SimpleNamespace(executeInMainThreadWithResult=lambda fn: fn()),
        )
        monkeypatch.setattr(b, "_on_main_thread", lambda: True)
        bridge = LosslessExecutionBridge()

        r = asyncio.run(bridge.execute_async(_op(lambda: None)))
        assert r.success
        assert r.integrity.main_thread_executed is True
        assert r.integrity.fidelity == 1.0
