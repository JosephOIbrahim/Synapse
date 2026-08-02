"""R1 size-gate HONESTY: the IntegrityBlock records which stage-hash algorithm
actually ran (BRIDGE-FLOOR, 2026-08-01).

The gate default became real (10_000 prims, measured — see the constants block
in shared/bridge.py and scripts/probe_stage_hash_floor.py). House rule (same as
the live-envelope *_applicable anchors): a reduced-fidelity hash is recorded as
reduced-fidelity, never presented as the full one. These tests pin:

  1. gate SILENT below threshold — mode "full", full fidelity, byte-identical
     Flatten digest (zero behavior change for normal stages)
  2. gate FIRES above threshold — mode "reduced", stage_hash_full_fidelity=False,
     honestly serialized in to_dict()
  3. SYMMETRIC degradation — the mode chosen at scene_hash_before is pinned for
     scene_hash_after even when the mutation moves the stage across the
     threshold mid-op (the delta comparison never crosses algorithms)
  4. config override — SYNAPSE_STAGE_HASH_LARGE_MODE=full restores always-full
  5. the reduced mode's KNOWN blind spot (value-only edits read "no_change")
     is carried with the honest qualifier, and honest reduction is NOT an
     anchor violation (fidelity semantics untouched)
  6. the F-H composition-sweep shed is recorded (composition_checks_reduced)

Driven through the REAL execute paths with the multiclient fake-hou pattern
wrapping a REAL pxr stage. pxr required; skipped if unavailable.
"""
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


class _FakeObj:
    """Non-LOP node: no stage() at all — no composed content is ever hashed."""

    def children(self):
        return []

    def cookCount(self):
        return 0

    def geometry(self):
        return None


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
    """Fake hou around a real stage; threshold 3 prims so tiny stages exercise
    both sides of the gate; large mode at its default."""
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", "3")
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)

    def _install(stage_or_node):
        node = (stage_or_node if isinstance(stage_or_node, _FakeObj)
                else _FakeLop(stage_or_node))
        monkeypatch.setattr(b, "hou", _FakeHou(node))
        return node

    return _install


def _op(fn, **kw):
    # create_node is INFORM-gated — consent short-circuits before any gate.
    return Operation(
        agent_id=AgentID.HANDS,
        operation_type="create_node",
        summary="stage-hash honesty test",
        fn=fn,
        **kw,
    )


def _pinned_hash(bridge, mode: str, target="/obj") -> str:
    """Recompute the scene hash with the algorithm FORCED — the oracle for
    which algorithm backed a recorded hash."""
    bridge._stage_hash_begin_op()
    bridge._stage_hash_pin_mode(mode)
    try:
        return bridge._compute_scene_hash(target)
    finally:
        bridge._stage_hash_end_op()


# ── 1. gate silent below threshold ─────────────────────────────

def test_below_threshold_records_full_and_matches_flatten(env):
    stage = _stage(1)  # 2 prims total (< 3)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(_op(lambda: stage.DefinePrim("/root/new", "Cube")))
    blk = res.integrity
    assert res.success
    assert blk.stage_hash_mode == "full"
    assert blk.stage_hash_full_fidelity is True
    assert blk.scene_hash_after == _pinned_hash(bridge, "full")
    d = blk.to_dict()
    assert d["stage_hash_mode"] == "full"
    assert d["stage_hash_full_fidelity"] is True
    assert d["composition_checks_reduced"] is False


# ── 2. gate fires above threshold, recorded honestly ───────────

def test_above_threshold_records_reduced_honestly(env):
    stage = _stage(10)  # 11 prims (> 3)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(_op(lambda: stage.DefinePrim("/root/new", "Cube")))
    blk = res.integrity
    assert res.success
    assert blk.stage_hash_mode == "reduced"
    assert blk.stage_hash_full_fidelity is False, (
        "reduced-detail hash presented as full fidelity — the honesty rule "
        "this gate exists to uphold")
    assert blk.scene_hash_after == _pinned_hash(bridge, "reduced")
    assert blk.scene_hash_before != blk.scene_hash_after
    assert blk.delta_hash not in ("", "no_change")
    # Honest reduction is NOT an anchor violation.
    assert blk.fidelity == 1.0
    d = blk.to_dict()
    assert d["stage_hash_mode"] == "reduced"
    assert d["stage_hash_full_fidelity"] is False


# ── 3. symmetric before/after degradation (mode pinned) ────────

def test_mode_pinned_when_mutation_crosses_threshold_upward(env):
    """Before-hash sees 2 prims (full); the op adds 10. The after-hash must
    STILL be full — never reduced-after vs full-before."""
    stage = _stage(1)
    env(stage)
    bridge = LosslessExecutionBridge()

    def _grow():
        for i in range(10):
            stage.DefinePrim(f"/root/grown{i}", "Cube")

    res = bridge.execute(_op(_grow))
    blk = res.integrity
    assert res.success
    assert blk.stage_hash_mode == "full"
    assert blk.scene_hash_after == _pinned_hash(bridge, "full")
    assert blk.scene_hash_after != _pinned_hash(bridge, "reduced")


def test_mode_pinned_when_mutation_crosses_threshold_downward(env):
    """Before-hash sees 11 prims (reduced); the op deletes down to 2. The
    after-hash must STILL be reduced."""
    stage = _stage(10)
    env(stage)
    bridge = LosslessExecutionBridge()

    def _shrink():
        for i in range(1, 10):
            stage.RemovePrim(f"/root/p{i}")

    res = bridge.execute(_op(_shrink))
    blk = res.integrity
    assert res.success
    assert blk.stage_hash_mode == "reduced"
    assert blk.scene_hash_after == _pinned_hash(bridge, "reduced")
    assert blk.scene_hash_after != _pinned_hash(bridge, "full")


# ── 4. config override restores always-full ────────────────────

def test_large_mode_full_restores_always_full(env, monkeypatch):
    stage = _stage(10)
    env(stage)
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_LARGE_MODE", "full")
    bridge = LosslessExecutionBridge()
    res = bridge.execute(_op(lambda: stage.DefinePrim("/root/new", "Cube")))
    blk = res.integrity
    assert blk.stage_hash_mode == "full"
    assert blk.stage_hash_full_fidelity is True
    assert blk.scene_hash_after == _pinned_hash(bridge, "full")


def test_large_mode_env_parsing(monkeypatch):
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)
    assert b._stage_hash_large_mode() == "reduced"
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_LARGE_MODE", "STRUCTURAL")
    assert b._stage_hash_large_mode() == "structural"
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_LARGE_MODE", "full")
    assert b._stage_hash_large_mode() == "full"
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_LARGE_MODE", "garbage")
    assert b._stage_hash_large_mode() == "reduced", (
        "a bad value must never silently disable the gate")


# ── 5. the reduced blind spot carries its qualifier ─────────────

def test_value_only_edit_reads_no_change_but_block_says_reduced(env):
    """Above threshold a value-only mutation is invisible to the reduced
    signature — delta reads "no_change". That is only honest because the SAME
    block says stage_hash_full_fidelity=False. This test pins the pairing."""
    stage = _stage(10)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(
        _op(lambda: stage.GetPrimAtPath("/root/p0")
            .GetAttribute("radius").Set(99.0)))
    blk = res.integrity
    assert res.success
    assert blk.delta_hash == "no_change"  # the known blind spot...
    assert blk.stage_hash_mode == "reduced"  # ...carried WITH its qualifier
    assert blk.stage_hash_full_fidelity is False


def test_no_stage_hashed_records_empty_mode(env):
    """A non-LOP target hashes no composed content: mode "" (nothing to
    degrade), full fidelity by default."""
    env(_FakeObj())
    bridge = LosslessExecutionBridge()
    res = bridge.execute(_op(lambda: None))
    blk = res.integrity
    assert blk.stage_hash_mode == ""
    assert blk.stage_hash_full_fidelity is True


# ── 6. F-H composition-sweep shed is recorded ───────────────────

def test_composition_sweep_shed_recorded(env):
    stage = _stage(10)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(
        _op(lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
    blk = res.integrity
    assert res.success
    assert blk.composition_valid is True
    assert blk.composition_checks_reduced is True, (
        "the inherit/specialize sweep was shed by the size gate but the block "
        "did not say so")


def test_composition_sweep_not_shed_below_threshold(env):
    stage = _stage(1)
    env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(
        _op(lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
    blk = res.integrity
    assert res.success
    assert blk.composition_checks_reduced is False
