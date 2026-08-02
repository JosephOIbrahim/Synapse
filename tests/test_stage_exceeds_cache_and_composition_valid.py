"""R302 rank 5 (H3 free-half) — two audit-honesty fixes, pinned:

1. THE _stage_exceeds CACHE. One bridge op used to walk the stage twice for
   the same prim-count verdict: once in _hash_stage_signature (the size
   gate) and again in _verify_composition (the F-H sweep gate) — ~2 ms/op
   above threshold (C4). The verdict is now parked in the per-op
   thread-local at the before-hash probe and REUSED by the sweep gate.
   Per-op pinning semantics (same as stage_hash_mode): the verdict is the
   BEFORE-stage's, and it never leaks outside the op.

2. composition_valid HONESTY. The field had ZERO assignment sites — a
   constant True that anchors_hold could never falsify, making Scene
   Integrity the one anchor without Finding-1 evidence-derivation. Now:
   True = validation ran and passed; False = ran and failed (recorded on
   the failed op's block); composition_applicable=False = it did not run
   (non-stage ops, the standalone path, the PDG path) — never a fake True.

Driven through the REAL execute paths with the multiclient fake-hou pattern
wrapping a REAL pxr stage (same template as test_stage_hash_honesty).
pxr required for the cache tests; skipped if unavailable.
"""

import asyncio
from types import SimpleNamespace

import pytest

import shared.bridge as b
from shared.bridge import LosslessExecutionBridge, Operation
from shared.types import AgentID

pytest.importorskip("pxr")
from pxr import Sdf, Usd  # noqa: E402


# ── fakes: multiclient pattern + a real composed stage ────────

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


class _FakeLop:
    """LOP-like node: no SOP geometry, real pxr stage."""

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


def _stage(n_prims: int) -> Usd.Stage:
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/root", "Xform")
    stage.SetDefaultPrim(root)
    for i in range(n_prims):
        p = stage.DefinePrim(f"/root/p{i}", "Sphere")
        p.CreateAttribute("radius", Sdf.ValueTypeNames.Double).Set(1.0)
    return stage


@pytest.fixture
def env(monkeypatch):
    """Fake hou around a real stage; threshold 3 prims so tiny stages
    exercise both sides of the gate (test_stage_hash_honesty template)."""
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "3")
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)

    def _install(stage):
        monkeypatch.setattr(b, "hou", _FakeHou(_FakeLop(stage)))

    return _install


@pytest.fixture
def count_stage_exceeds(monkeypatch):
    """Class-level counting wrapper around the REAL _stage_exceeds — catches
    the hash-gate call AND the sweep-gate call."""
    calls = []
    orig = LosslessExecutionBridge._stage_exceeds

    def counting(stage, threshold):
        calls.append(threshold)
        return orig(stage, threshold)

    monkeypatch.setattr(
        LosslessExecutionBridge, "_stage_exceeds", staticmethod(counting))
    return calls


def _op(fn, **kw):
    # create_node is INFORM-gated — consent short-circuits before any gate.
    return Operation(
        agent_id=AgentID.HANDS,
        operation_type="create_node",
        summary="stage-exceeds cache test",
        fn=fn,
        **kw,
    )


# ── 1. the cache: one probe per op, both sides of the gate ─────

def test_stage_exceeds_probed_once_per_op_above_threshold(
        env, count_stage_exceeds):
    """Above threshold the op used to probe twice (hash gate + sweep gate).
    The sweep gate must now REUSE the hash gate's verdict: exactly ONE
    _stage_exceeds walk for the whole op — and the sweep still sheds."""
    stage = _stage(10)  # 11 prims (> 3)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(
        _op(lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
    assert res.success
    assert res.integrity.composition_checks_reduced is True, (
        "cache reuse must preserve the shed decision")
    assert len(count_stage_exceeds) == 1, (
        f"expected exactly 1 _stage_exceeds probe per op (cache reuse), "
        f"got {len(count_stage_exceeds)} — the redundant sweep-gate walk "
        f"is back")


def test_stage_exceeds_probed_once_per_op_below_threshold(
        env, count_stage_exceeds):
    """Below threshold the cached False must equally suppress the sweep
    gate's own probe — and the sweep must NOT shed."""
    stage = _stage(1)  # 2 prims (< 3)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(
        _op(lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
    assert res.success
    assert res.integrity.composition_checks_reduced is False
    assert len(count_stage_exceeds) == 1


def test_bare_verify_composition_probes_itself(env, count_stage_exceeds):
    """A direct _verify_composition call OUTSIDE an op has no cache — it
    must run its own probe (cache miss falls back to the walk)."""
    stage = _stage(10)
    env(stage)
    bridge = LosslessExecutionBridge()
    assert bridge._verify_composition("/stage") is True
    assert len(count_stage_exceeds) == 1


def test_cache_does_not_leak_past_op_end(env, count_stage_exceeds):
    """After an op completes, a bare _verify_composition call must NOT
    inherit the op's parked verdict — _stage_hash_end_op clears it."""
    stage = _stage(10)
    env(stage)
    bridge = LosslessExecutionBridge()
    bridge.execute(
        _op(lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
    del count_stage_exceeds[:]
    assert bridge._verify_composition("/stage") is True
    assert len(count_stage_exceeds) == 1, (
        "bare call after an op reused a stale per-op verdict — end_op did "
        "not clear the cache")


# ── 2. composition_valid honesty: ran+passed / ran+failed / N-A ─

def test_composition_valid_true_when_ran_and_passed(env):
    stage = _stage(1)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(
        _op(lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
    blk = res.integrity
    assert res.success
    assert blk.composition_valid is True
    assert blk.composition_applicable is True
    assert blk.fidelity == 1.0


def test_composition_valid_false_when_ran_and_failed(env, monkeypatch):
    """A failed validation must be recorded as composition_valid=False on
    the FAILED op's block — previously the field stayed a constant True and
    the Scene Integrity anchor could never be falsified."""
    stage = _stage(1)
    env(stage)
    bridge = LosslessExecutionBridge()
    monkeypatch.setattr(bridge, "_verify_composition", lambda sp: False)
    res = bridge.execute(
        _op(lambda: None, touches_stage=True, stage_path="/stage"))
    blk = res.integrity
    assert not res.success
    assert "Composition violation" in (res.error or "")
    assert blk.composition_valid is False
    assert blk.composition_applicable is True
    assert blk.anchors_hold is False
    assert blk.fidelity == 0.0


def test_composition_not_run_records_not_applicable_sync(env):
    """A non-stage-touching op runs no validation — the qualifier must say
    so instead of the default-True pair reading as 'validated'."""
    stage = _stage(1)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(_op(lambda: None))  # touches_stage=False
    blk = res.integrity
    assert res.success
    assert blk.composition_applicable is False
    assert blk.composition_valid is True  # raw default, gated N/A
    assert blk.fidelity == 1.0  # N/A is honest, never a violation


def test_composition_valid_wired_on_async_path(env, monkeypatch):
    """_sync_payload (execute_async) carries the same wiring — both the
    ran-and-passed assignment and the not-run qualifier."""
    stage = _stage(1)
    env(stage)
    # Substituted module attr → _resolve_marshal takes the standalone branch
    # (fn() inline) — the documented seam (test_bridge_multiclient template).
    # The payload runs on the executor worker thread, so the main-thread
    # evidence seam is patched True (the documented production emulation —
    # test_async_payload_seam_patch_documents_production).
    monkeypatch.setattr(
        b, "hdefereval",
        SimpleNamespace(executeInMainThreadWithResult=lambda fn: fn()),
    )
    monkeypatch.setattr(b, "_on_main_thread", lambda: True)
    bridge = LosslessExecutionBridge()

    res = asyncio.run(bridge.execute_async(
        _op(lambda: stage.DefinePrim("/root/new1", "Cube"),
            touches_stage=True, stage_path="/stage")))
    assert res.success
    assert res.integrity.composition_valid is True
    assert res.integrity.composition_applicable is True

    res2 = asyncio.run(bridge.execute_async(_op(lambda: None)))
    assert res2.success
    assert res2.integrity.composition_applicable is False


def test_composition_valid_false_on_async_path(env, monkeypatch):
    stage = _stage(1)
    env(stage)
    monkeypatch.setattr(
        b, "hdefereval",
        SimpleNamespace(executeInMainThreadWithResult=lambda fn: fn()),
    )
    monkeypatch.setattr(b, "_on_main_thread", lambda: True)
    bridge = LosslessExecutionBridge()
    monkeypatch.setattr(bridge, "_verify_composition", lambda sp: False)
    res = asyncio.run(bridge.execute_async(
        _op(lambda: None, touches_stage=True, stage_path="/stage")))
    assert not res.success
    assert res.integrity.composition_valid is False
    assert res.integrity.fidelity == 0.0


def test_standalone_path_records_not_applicable(monkeypatch):
    """_execute_direct never runs validation — anchor N/A, honestly."""
    monkeypatch.setattr(b, "_HOU_AVAILABLE", False)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(_op(lambda: None, touches_stage=True,
                             stage_path="/stage"))
    assert res.success
    assert res.integrity.composition_applicable is False
    assert res.integrity.fidelity == 1.0


def test_pdg_path_records_not_applicable(monkeypatch):
    """The PDG cook path never runs validation either — anchor N/A on its
    standalone branch (parity). Driven directly: on the execute_async route
    a standalone process short-circuits into _execute_direct before the PDG
    dispatch, so the deferred coroutine is exercised on its own."""
    monkeypatch.setattr(b, "_HOU_AVAILABLE", False)
    bridge = LosslessExecutionBridge()
    op = Operation(
        agent_id=AgentID.CONDUCTOR,
        operation_type="cook_pdg_chain",
        summary="pdg N/A qualifier test",
        fn=lambda: None,
        kwargs={"node_path": "/tasks/topnet1"},
    )
    integrity = b.IntegrityBlock(
        agent_id=AgentID.CONDUCTOR.value,
        operation_type="cook_pdg_chain",
        consent_verified=True,  # execute_async stamps this before dispatch
    )
    res = asyncio.run(bridge._execute_pdg_deferred(op, integrity))
    assert res.success
    assert res.integrity.composition_applicable is False


# ---------------------------------------------------------------------------
# K4 (R302 crucible) — an op that fails BEFORE validation must not claim a pass
# ---------------------------------------------------------------------------

def test_consent_denied_op_does_not_claim_composition_ran(env):
    """Consent-denied returns before any validation — the block must say N/A.

    Before the K4 fix the dataclass defaults (valid=True, applicable=True)
    made a consent-denied block read "validation ran and passed", which under
    the new honest semantics is a false receipt for an op whose stage was
    never inspected.
    """
    stage = _stage(10)
    env(stage)
    bridge = LosslessExecutionBridge()
    # The consent MACHINERY has its own tests (three-tier fallback, gate
    # levels). What is under test here is only what the block records when
    # the denial happens, so the verdict is forced at the seam.
    bridge._check_consent = lambda _op: False
    res = bridge.execute(
        _op(lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
    assert res.success is False, "consent was denied; the op must not succeed"
    assert res.integrity.composition_applicable is False, (
        "a consent-denied op never ran composition validation; the block must "
        "record composition_applicable=False, not inherit a default that "
        "reads 'ran and passed'")


def test_raising_op_does_not_claim_composition_ran(env):
    """An op whose fn raises before the anchor must also say N/A."""
    stage = _stage(10)
    env(stage)
    bridge = LosslessExecutionBridge()

    def _boom():
        raise RuntimeError("op exploded before the anchor")

    res = bridge.execute(_op(_boom, touches_stage=True, stage_path="/stage"))
    assert res.success is False
    assert res.integrity.composition_applicable is False, (
        "the op raised before composition validation ran; the block must not "
        "claim the anchor passed")
