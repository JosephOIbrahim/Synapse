"""H10: the R1 size gate re-keyed on AUTHORED ARRAY VOLUME (Lane B, 2026-08-02).

Adjudicated finding (crucible C2 live probe, severity 4/5): per-op stage-hash
cost tracks authored array volume, not prim count. A 4-prim PointInstancer with
2M instances cost 2017.9 ms/op while _stage_exceeds(stage, 10000) returned
False — a 16,677x miss. Ruling: "re-parameterize, do not re-litigate."

These tests pin the volume term added to the gate decision point
(shared/bridge.py::_hash_stage_signature -> _stage_volume_exceeds):

  (a) the C2 repro TRIPS the gate at defaults — small-prim/high-volume
      PointInstancer routes to the reduced signature, prim probe still False
  (b) below BOTH thresholds the hash stays byte-identical to the pre-gate
      Flatten algorithm (zero behavior change for normal stages)
  (c) the probe is BOUNDED — short-circuits at the volume threshold (huge
      stages are not fully walked) and gives up at the attribute budget
      (attr-dense stages cannot make the probe itself expensive); counter
      proof via duck-typed fakes, no pxr needed
  (d) SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD env override respected, same
      parsing contract as the prim threshold
  (e) honesty fields: a volume-term trip records stage_hash_mode="reduced" /
      stage_hash_full_fidelity=False exactly like a prim-term trip, and the
      volume term does NOT shed _verify_composition's sweep (prim-keyed, H3)

Probe cost measured at this HEAD (Python 3.14.2 / pxr 0.26.5, median of 5):
0.013 ms on the 2M-instance repro vs 1361.5 ms/hash for the Flatten it gates;
budgeted worst case (10k-prim/40k-scalar-attr stage) 6.5 ms.
pxr-dependent tests skip cleanly when pxr is unavailable (CI has no pxr).
"""
import hashlib

import pytest

import shared.bridge as b
from shared.bridge import LosslessExecutionBridge, Operation
from shared.constants import HASH_LENGTH
from shared.types import AgentID

try:
    from pxr import Sdf, Usd, Vt  # noqa: F401
    _HAS_PXR = True
except ImportError:
    _HAS_PXR = False

pxrskip = pytest.mark.skipif(not _HAS_PXR, reason="pxr (OpenUSD) not available")


# ── duck-typed fakes for the probe-bound proofs (no pxr) ────────

class _ArrayTypeName:
    isArray = True


class _ScalarTypeName:
    isArray = False


class _FakeAttr:
    def __init__(self, n_elements, counter, array=True):
        self._n = n_elements
        self._c = counter
        self._tn = _ArrayTypeName() if array else _ScalarTypeName()

    def GetTypeName(self):
        return self._tn

    def Get(self, *args):
        self._c["value_peeks"] += 1
        return [0] * self._n  # len() works; the probe must never read elements

    def GetNumTimeSamples(self):
        return 0


class _FakePrim:
    def __init__(self, attrs):
        self._attrs = attrs

    def GetAuthoredAttributes(self):
        return self._attrs


class _FakeStage:
    def __init__(self, prims, counter):
        self._prims = prims
        self._c = counter

    def TraverseAll(self):
        for p in self._prims:
            self._c["prims_traversed"] += 1
            yield p


def _counting_stage(n_prims, elements_per_prim, array=True):
    counter = {"prims_traversed": 0, "value_peeks": 0}
    prims = [
        _FakePrim([_FakeAttr(elements_per_prim, counter, array=array)])
        for _ in range(n_prims)
    ]
    return _FakeStage(prims, counter), counter


# ── (c) probe bounds: short-circuit + attribute budget ──────────

def test_volume_probe_short_circuits_at_threshold():
    """A huge stage must NOT be fully walked: with 1000 array elements per prim
    and a threshold of 2500, the walk stops at prim 3 (1000 -> 2000 -> 3000)."""
    stage, counter = _counting_stage(1000, 1000)
    assert LosslessExecutionBridge._stage_volume_exceeds(stage, 2500) is True
    assert counter["prims_traversed"] == 3, (
        f"probe walked {counter['prims_traversed']} prims of 1000 — the volume "
        "short-circuit did not bound the walk")


def test_volume_probe_attr_budget_bounds_scalar_walk():
    """Attr-dense stages cannot make the probe expensive: after the attribute
    budget is exhausted without a trip, the probe gives up (False -> full path,
    the pre-H10 status quo). Scalar attributes are never value-peeked."""
    n = b._STAGE_HASH_VOLUME_ATTR_BUDGET + 500
    stage, counter = _counting_stage(n, 10, array=False)
    assert LosslessExecutionBridge._stage_volume_exceeds(stage, 0) is False
    assert counter["prims_traversed"] == b._STAGE_HASH_VOLUME_ATTR_BUDGET + 1, (
        "probe did not stop at the attribute budget")
    assert counter["value_peeks"] == 0, (
        "probe called Get() on scalar attributes — the size peek must be "
        "restricted to array-typed attributes")


def test_volume_probe_attr_budget_parameter_respected():
    stage, counter = _counting_stage(100, 1, array=True)
    assert LosslessExecutionBridge._stage_volume_exceeds(
        stage, 10_000, attr_budget=10) is False
    assert counter["prims_traversed"] == 11


def test_volume_probe_below_threshold_walks_all_and_returns_false():
    stage, counter = _counting_stage(5, 10)
    assert LosslessExecutionBridge._stage_volume_exceeds(stage, 1000) is False
    assert counter["prims_traversed"] == 5


# ── (d) env override: same parsing contract as the prim threshold ─

def test_volume_threshold_env_parsing(monkeypatch):
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", raising=False)
    assert b._stage_hash_volume_threshold() == \
        b._DEFAULT_STAGE_HASH_VOLUME_THRESHOLD
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", "garbage")
    assert b._stage_hash_volume_threshold() == \
        b._DEFAULT_STAGE_HASH_VOLUME_THRESHOLD
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", "-7")
    assert b._stage_hash_volume_threshold() == \
        b._DEFAULT_STAGE_HASH_VOLUME_THRESHOLD
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", "250")
    assert b._stage_hash_volume_threshold() == 250


def test_volume_env_override_changes_gate_decision(monkeypatch):
    """(d) live: a stage whose volume sits between two override values flips
    the probe verdict with the env var — no pxr needed (duck-typed stage)."""
    stage, _ = _counting_stage(4, 100)  # 400 elements total
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", "100")
    assert LosslessExecutionBridge._stage_volume_exceeds(
        stage, b._stage_hash_volume_threshold()) is True
    stage2, _ = _counting_stage(4, 100)
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", "100000")
    assert LosslessExecutionBridge._stage_volume_exceeds(
        stage2, b._stage_hash_volume_threshold()) is False


# ── pxr stage builders ──────────────────────────────────────────

def _pointinstancer_stage(n_instances):
    """The C2 repro shape: prim-light (4 prims), value-heavy (2 arrays of
    n_instances elements on a PointInstancer)."""
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/root", "Xform")
    stage.SetDefaultPrim(root)
    proto = stage.DefinePrim("/root/proto", "Sphere")
    proto.CreateAttribute("radius", Sdf.ValueTypeNames.Double).Set(0.1)
    pi = stage.DefinePrim("/root/instancer", "PointInstancer")
    pi.CreateRelationship("prototypes").SetTargets([proto.GetPath()])
    pi.CreateAttribute("protoIndices", Sdf.ValueTypeNames.IntArray).Set(
        Vt.IntArray(n_instances))
    pi.CreateAttribute("positions", Sdf.ValueTypeNames.Point3fArray).Set(
        Vt.Vec3fArray(n_instances))
    return stage


def _small_stage():
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/root", "Xform")
    stage.SetDefaultPrim(root)
    child = stage.DefinePrim("/root/child", "Mesh")
    child.CreateAttribute("points", Sdf.ValueTypeNames.Point3fArray).Set(
        Vt.Vec3fArray(8))
    child.CreateAttribute("radius", Sdf.ValueTypeNames.Double).Set(1.0)
    return stage


def _old_flatten_hash(stage):
    flat = stage.Flatten().ExportToString()
    return hashlib.sha256(flat.encode("utf-8")).hexdigest()[:HASH_LENGTH]


# ── (a) the C2 repro, pinned ────────────────────────────────────

@pxrskip
def test_c2_repro_small_prim_high_volume_trips_gate(monkeypatch):
    """THE adjudicated miss: prim probe False, volume probe True, and the
    decision point routes to the reduced signature — all at stock defaults."""
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", raising=False)
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", raising=False)
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)
    # 300_001 instances -> 600_002 authored elements > the 500_000 default,
    # on 4 prims (the C2 shape, scaled to keep the test fast).
    stage = _pointinstancer_stage(300_001)
    bridge = LosslessExecutionBridge()
    assert bridge._stage_exceeds(stage, b._stage_hash_prim_threshold()) is False, (
        "repro invalidated: the prim term tripped — this stage no longer "
        "reproduces the C2 miss")
    assert bridge._stage_volume_exceeds(
        stage, b._stage_hash_volume_threshold()) is True, (
        "the volume term did NOT trip on the C2 repro shape — H10 regressed")
    assert bridge._hash_stage_signature(stage) == \
        bridge._reduced_stage_signature(stage), (
        "gate tripped but the decision point did not route to the reduced path")


@pxrskip
def test_time_sampled_only_arrays_counted(monkeypatch):
    """An array authored ONLY at time samples (no default) still counts:
    len(earliest sample) x num samples, without reading every sample."""
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", raising=False)
    stage = Usd.Stage.CreateInMemory()
    root = stage.DefinePrim("/root", "Xform")
    stage.SetDefaultPrim(root)
    pts = stage.DefinePrim("/root/anim", "Mesh").CreateAttribute(
        "points", Sdf.ValueTypeNames.Point3fArray)
    pts.Set(Vt.Vec3fArray(300_000), Usd.TimeCode(1.0))
    pts.Set(Vt.Vec3fArray(300_000), Usd.TimeCode(2.0))
    bridge = LosslessExecutionBridge()
    # 300k x 2 samples = 600k > 500k default.
    assert bridge._stage_volume_exceeds(
        stage, b._stage_hash_volume_threshold()) is True


# ── (b) below both thresholds: byte-identical full path ─────────

@pxrskip
def test_below_both_thresholds_byte_identical_flatten(monkeypatch):
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", raising=False)
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", raising=False)
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)
    stage = _small_stage()  # 3 prims, 8 array elements — under both gates
    bridge = LosslessExecutionBridge()
    assert bridge._stage_volume_exceeds(
        stage, b._stage_hash_volume_threshold()) is False
    assert bridge._hash_stage_signature(stage) == _old_flatten_hash(stage), (
        "below-both-thresholds hash diverged from the pre-gate Flatten "
        "algorithm — the zero-behavior-change guarantee broke")


@pxrskip
def test_volume_env_override_respected_on_real_stage(monkeypatch):
    """(d) with pxr: lowering the volume threshold gates a small-array stage;
    raising it un-gates the repro shape."""
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", raising=False)
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)
    bridge = LosslessExecutionBridge()

    stage = _small_stage()  # 8 authored array elements
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", "4")
    assert bridge._hash_stage_signature(stage) == \
        bridge._reduced_stage_signature(stage)

    big = _pointinstancer_stage(300_001)
    monkeypatch.setenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", "10000000")
    assert bridge._hash_stage_signature(big) == _old_flatten_hash(big)


# ── (e) honesty fields through the real execute path ────────────
# Multiclient fake-hou pattern wrapping a REAL pxr stage — the same harness
# tests/test_stage_hash_honesty.py uses for the prim term.

class _FakeUndos:
    def group(self, label):
        class _Ctx:
            def __enter__(ctx):
                return ctx

            def __exit__(ctx, *args):
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


def _op(fn, **kw):
    return Operation(
        agent_id=AgentID.HANDS,
        operation_type="create_node",  # INFORM-gated: consent short-circuits
        summary="volume-gate honesty test",
        fn=fn,
        **kw,
    )


@pytest.fixture
def volume_env(monkeypatch):
    """Fake hou around a real pxr stage; PRIM threshold at its stock default
    (so only the volume term can trip), volume + large mode at defaults."""
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_PRIM_THRESHOLD", raising=False)
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD", raising=False)
    monkeypatch.delenv("SYNAPSE_STAGE_HASH_LARGE_MODE", raising=False)

    def _install(stage):
        monkeypatch.setattr(b, "hou", _FakeHou(_FakeLop(stage)))

    return _install


@pxrskip
def test_volume_trip_records_reduced_honestly(volume_env):
    """When the VOLUME term (not the prim term) trips, the IntegrityBlock
    honesty fields read exactly as a prim-term trip: mode "reduced",
    full_fidelity False, fidelity untouched (H11 is separate)."""
    stage = _pointinstancer_stage(300_001)  # 4 prims — prim term cannot trip
    volume_env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(_op(lambda: stage.DefinePrim("/root/new", "Cube")))
    blk = res.integrity
    assert res.success
    assert blk.stage_hash_mode == "reduced"
    assert blk.stage_hash_full_fidelity is False, (
        "volume-gated reduced hash presented as full fidelity")
    assert blk.fidelity == 1.0  # honest reduction is NOT an anchor violation
    d = blk.to_dict()
    assert d["stage_hash_mode"] == "reduced"
    assert d["stage_hash_full_fidelity"] is False


@pxrskip
def test_volume_trip_does_not_shed_composition_sweep(volume_env):
    """DO-NOT pin: the volume term gates the stage HASH only. On a 4-prim
    stage above the VOLUME threshold, _verify_composition's inherit/specialize
    sweep must still run (composition_checks_reduced stays False) — shedding
    it is prim-keyed (H3, deferred)."""
    stage = _pointinstancer_stage(300_001)
    volume_env(stage)
    bridge = LosslessExecutionBridge()
    res = bridge.execute(
        _op(lambda: stage.DefinePrim("/root/new", "Cube"),
            touches_stage=True, stage_path="/stage"))
    blk = res.integrity
    assert res.success
    assert blk.stage_hash_mode == "reduced"  # the hash gate DID trip...
    assert blk.composition_checks_reduced is False, (
        "the volume term shed the composition sweep — it must stay prim-keyed")
