"""perf_counters — the perf-ratchet instrument (I2 design, R304 lane R).

Counts the WORK UNITS one bridge operation performs — full-stage traversals,
prims visited, attributes examined, serialize calls — through the committed
fake-hou seam (tests/test_stage_hash_honesty.py:37-115 pattern), driving the
REAL ``LosslessExecutionBridge.execute()`` entry point so the count is total
by construction (a traversal added anywhere in the op path is counted without
this file knowing where).

COUNTED PROXY, NOT WALL-CLOCK (I2 §0): CI has no pxr (ci.yml installs
[dev,websocket,mcp]; pyproject has no usd-core extra), so a timer cannot gate
this repo; a deterministic counter cannot flake. The ratchet HOLDS a win; it
does not MEASURE one — no counter here is quotable as a latency figure.

PRECISION NOTE (I2 §3, carried verbatim on purpose): ``value_reads`` counts
values the BRIDGE reads. It does NOT count values pxr reads internally during
``Flatten()``. ``flatten_exports`` is the proxy for "the whole stage's values
were serialized." Reading ``value_reads == 0`` as "no value cost" would be
exactly the error the 07-27 ledger made.

FIDELITY LIMIT (I2 §12 / risk #1): the counting fake measures the CALL
PATTERN the bridge makes, not the cost pxr pays. If the fake drifts from the
real pxr API the counted pattern silently stops corresponding to reality.
The pxr-gated cross-check in tests/test_perf_ratchet.py (a counting PROXY
over a real Usd.Stage must produce the SAME counter dict) is the only guard,
and it SKIPS in CI — CI green does not cover fake/pxr drift.

DETERMINISM CONTRACT (I2 §5):
  1. ``shared.bridge._import_pxr_composition`` is ALWAYS patched here — on a
     machine WITH pxr, ``_verify_composition`` would otherwise take the
     class-arcs branch and pay one extra bounded traversal that a pxr-less
     machine does not (bridge.py ``class_arcs_enabled = Usd is not None``).
     Same code, different count — the patch closes flake source #1.
  2. Env is pinned, never inherited: both threshold env vars are set and the
     large-mode var deleted for the duration of every measurement
     (``_stage_hash_prim_threshold()`` reads env at CALL time, no cache).
  3. The fakes are pure: fixed ordering, generator-backed (no materialised
     prim lists — 10k-prim cells stay memory-flat), no time, no random, no
     filesystem.
  4. Counters are per-measurement instances, reset by construction — no
     cross-test bleed, no ordering dependence.
  5. The shipped-default blind spot (every cell pins its own env, so a revert
     of ``_DEFAULT_STAGE_HASH_PRIM_THRESHOLD`` leaves all counts green) is
     closed by the pinned_constants block in the floor, checked by
     harness/verify/perf_ratchet.py — NOT by this module.

Pure Python: no pxr, no hou, no sockets, importable on every CI leg.
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

# Repo root on sys.path: pytest gets this from `python -m pytest` (cwd), but
# direct execution and harness/verify/perf_ratchet.py's importlib load do not.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shared.bridge as b
from shared.bridge import LosslessExecutionBridge, Operation
from shared.types import AgentID

# ── the counter vocabulary — names are the contract; the floor keys on them ──

COUNTERS: tuple[str, ...] = (
    "scene_hash_calls",         # entries to _compute_scene_hash (instance wrap)
    "stage_traversals",         # passes STARTED over a whole stage (TraverseAll/Traverse)
    "prim_visits",              # prims YIELDED across all passes — the scale term
    "flatten_exports",          # stage.Flatten().ExportToString() serialize calls
    "value_reads",              # bridge-issued attr.Get / attr.GetTimeSamples
    "attrs_examined",           # attr.GetTypeName() peeks (volume probe / structural)
    "prop_name_reads",          # prim.GetAuthoredPropertyNames() calls
    "rel_target_reads",         # prim.GetAuthoredRelationships() (+GetTargets) calls
    "prim_state_reads",         # IsValid / IsActive / GetSpecifier / GetTypeName on prims
    "arc_queries",              # HasAuthoredReferences|Payloads|Inherits|Specializes
    "node_children_reads",      # hou node.children() calls
    "geometry_accessor_calls",  # node.geometry() calls
    "geometry_intrinsic_reads", # geo.intrinsicValue(...) calls
    "dependents_calls",         # node.dependents() + node.outputs() calls (R7 trace)
    "node_visits",              # nodes visited by the R7 trace (1 per dependents())
)

# NOT counted, on purpose (documented so nobody believes it is):
#   attr.GetNumTimeSamples() — structural metadata, not a value read; it only
#   runs on array attrs inside the volume probe and on the (UNPINNED in v1)
#   structural path. Fold it into value_reads only when the structural cell
#   is pinned, as its own promotion event.


class PerfScenarioError(RuntimeError):
    """The scenario's premise did not hold (wrong mode, unexpected success/
    failure). An instrument that half-ran must never return counts."""


def _new_counters() -> dict[str, int]:
    return {k: 0 for k in COUNTERS}


# ── counting fakes (multiclient pattern, forked from test_stage_hash_honesty) ──

class _Path:
    __slots__ = ("pathString",)

    def __init__(self, s: str):
        self.pathString = s


class _TypeName:
    __slots__ = ("isArray",)

    def __init__(self, is_array: bool):
        self.isArray = is_array


class _CountingAttr:
    """Flyweight authored attribute. v1 shape: one SCALAR attr per prim (the
    honesty-test '_stage()' shape: Sphere + authored double 'radius'), so the
    H10 volume probe examines it and moves on without a value read."""
    __slots__ = ("_c", "_tn")

    def __init__(self, counters: dict, is_array: bool = False):
        self._c = counters
        self._tn = _TypeName(is_array)

    def GetName(self):
        return "radius"

    def GetTypeName(self):
        self._c["attrs_examined"] += 1
        return self._tn

    def Get(self, _time=None):
        self._c["value_reads"] += 1
        return None

    def GetTimeSamples(self):
        self._c["value_reads"] += 1
        return []

    def GetNumTimeSamples(self):
        return 0  # deliberately uncounted — see module note


class _CountingPrim:
    """Flyweight prim, reused across yields (memory stays flat at 10k prims)."""
    __slots__ = ("_c", "_path", "_attrs")

    def __init__(self, counters: dict, path: str = "/perf/prim"):
        self._c = counters
        self._path = _Path(path)
        self._attrs = (_CountingAttr(counters),)

    def GetPath(self):
        return self._path

    def GetTypeName(self):
        self._c["prim_state_reads"] += 1
        return "Sphere"

    def GetSpecifier(self):
        self._c["prim_state_reads"] += 1
        return "def"

    def IsActive(self):
        self._c["prim_state_reads"] += 1
        return True

    def IsValid(self):
        self._c["prim_state_reads"] += 1
        return True

    def GetAuthoredPropertyNames(self):
        self._c["prop_name_reads"] += 1
        return ("radius",)

    def GetAuthoredRelationships(self):
        self._c["rel_target_reads"] += 1
        return ()

    def GetAuthoredAttributes(self):
        return self._attrs

    def HasAuthoredReferences(self):
        self._c["arc_queries"] += 1
        return False

    def HasAuthoredPayloads(self):
        self._c["arc_queries"] += 1
        return False

    def HasAuthoredInherits(self):
        self._c["arc_queries"] += 1
        return False

    def HasAuthoredSpecializes(self):
        self._c["arc_queries"] += 1
        return False


class _CountingLayer:
    __slots__ = ("_c", "_content")

    def __init__(self, counters: dict, content: str):
        self._c = counters
        self._content = content

    def ExportToString(self):
        self._c["flatten_exports"] += 1
        return self._content


class _CountingStage:
    """Generator-backed counting stage. ``add_prims`` is the test-side
    mutation hook (grows the prim count → the reduced signature and the
    Flatten export string both change)."""
    __slots__ = ("_c", "_n", "_prim")

    def __init__(self, counters: dict, n_prims: int):
        self._c = counters
        self._n = n_prims
        self._prim = _CountingPrim(counters)

    def _iter(self):
        c, prim = self._c, self._prim
        for _ in range(self._n):
            c["prim_visits"] += 1
            yield prim

    def TraverseAll(self):
        self._c["stage_traversals"] += 1
        return self._iter()

    def Traverse(self):
        self._c["stage_traversals"] += 1
        return self._iter()

    def Flatten(self):
        return _CountingLayer(self._c, f"usda:{self._n}")

    # test-side mutation (S-D rollback cell)
    def add_prims(self, k: int) -> None:
        self._n += k


class _CountingGeo:
    __slots__ = ("_c",)

    def __init__(self, counters: dict):
        self._c = counters

    def intrinsicValue(self, name):
        self._c["geometry_intrinsic_reads"] += 1
        return 0


class _CountingNode:
    """hou-node fake. ``stage``/``geo`` are optional so one class covers the
    LOP shape (stage, no geo), the plain-object shape (neither), and the S-C
    hybrid (BOTH — geo residue counted AND a live stage that must never be
    touched under include_stage=False; hasattr(node, 'stage') is True there
    on purpose, so the cell pins the STRUCTURAL skip, not an absent API)."""

    def __init__(self, counters: dict, stage=None, geo=None):
        self._c = counters
        self._stage = stage
        self._geo = geo
        if stage is None:
            # hasattr(node, "stage") gates the S2 block — a non-LOP node
            # must genuinely lack the attribute.
            self.stage = None
            del self.stage

    def children(self):
        self._c["node_children_reads"] += 1
        return ()

    def cookCount(self):
        return 0

    def geometry(self):
        self._c["geometry_accessor_calls"] += 1
        return self._geo


def _make_lop(counters, stage):
    node = _CountingNode(counters, stage=stage)
    node.stage = lambda: stage
    return node


class _CountingGraphNode:
    """R7 blast-radius graph node: dependents()/outputs() counted; no LOP
    anywhere in the v1 graph so the trace walks the whole fanout."""
    __slots__ = ("_c", "_path", "_deps", "_outs")

    def __init__(self, counters: dict, path: str):
        self._c = counters
        self._path = path
        self._deps: list = []
        self._outs: list = []

    def path(self):
        return self._path

    def dependents(self):
        self._c["dependents_calls"] += 1
        self._c["node_visits"] += 1  # 1:1 — _trace calls dependents() once per visited node
        return list(self._deps)

    def outputs(self):
        self._c["dependents_calls"] += 1
        return list(self._outs)


class _FakeUndos:
    def group(self, label):
        class _Ctx:
            def __enter__(ctx):
                return ctx

            def __exit__(ctx, *args):
                return False

        return _Ctx()

    def performUndo(self):  # no-op: the fake cannot revert (S-D pins that honestly)
        return None


class _LopMarker:
    """Stands in for hou.LopNode in isinstance checks (R7 trace)."""


class _CountingHou:
    def __init__(self, nodes: dict):
        self._nodes = nodes
        self.undos = _FakeUndos()
        self.LopNode = _LopMarker

    def node(self, path):
        return self._nodes.get(path)


class _FakeSdf:
    """Truthy stand-in: `Sdf is not None` enables the reference/payload arm."""


class _FakeTimeCode:
    @staticmethod
    def EarliestTime():
        return 0.0


class _FakeUsd:
    Prim = _CountingPrim
    TimeCode = _FakeTimeCode


def _fake_import_pxr():
    return _FakeSdf, _FakeUsd


# ── the seam: patch shared.bridge module globals + pin env, restore always ──

_ENV_PRIM = "SYNAPSE_STAGE_HASH_PRIM_THRESHOLD"
_ENV_VOLUME = "SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD"
_ENV_MODE = "SYNAPSE_STAGE_HASH_LARGE_MODE"

# The volume threshold every v1 cell pins. Pinned to the SHIPPED default's
# value so the cells measure the production regime, but via env so an
# operator's shell can never change a count. The shipped default itself is
# guarded separately by the floor's pinned_constants block.
PINNED_VOLUME_THRESHOLD = 500_000

_MISSING = object()


@contextmanager
def _patched(hou_obj, threshold: int):
    """Module-global monkeypatching (never sys.modules — the fake-hou
    residency trap, tests/conftest.py) + per-scenario env pinning."""
    saved = {
        "_HOU_AVAILABLE": b._HOU_AVAILABLE,
        "hou": b.hou,
        "_import_pxr_composition": b._import_pxr_composition,
    }
    saved_env = {k: os.environ.get(k, _MISSING)
                 for k in (_ENV_PRIM, _ENV_VOLUME, _ENV_MODE)}
    try:
        b._HOU_AVAILABLE = True
        b.hou = hou_obj
        b._import_pxr_composition = _fake_import_pxr  # flake source #1 — mandatory
        os.environ[_ENV_PRIM] = str(threshold)
        os.environ[_ENV_VOLUME] = str(PINNED_VOLUME_THRESHOLD)
        os.environ.pop(_ENV_MODE, None)
        yield
    finally:
        for k, v in saved.items():
            setattr(b, k, v)
        for k, v in saved_env.items():
            if v is _MISSING:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _wrap_scene_hash(bridge: LosslessExecutionBridge, counters: dict) -> None:
    """Count entries to _compute_scene_hash on THIS instance — fixture-level
    instrumentation of the entry point; zero production code touched."""
    inner = bridge._compute_scene_hash

    def counting(*args, **kwargs):
        counters["scene_hash_calls"] += 1
        return inner(*args, **kwargs)

    bridge._compute_scene_hash = counting


def _op(fn, **kw) -> Operation:
    # create_node is INFORM-gated — consent short-circuits before any gate.
    return Operation(
        agent_id=AgentID.HANDS,
        operation_type="create_node",
        summary="perf ratchet cell",
        fn=fn,
        **kw,
    )


# ── scenario drivers ─────────────────────────────────────────────────────────

def _mcp_lop_op(prims: int, threshold: int, expect_mode: str,
                stage_factory=None) -> dict[str, int]:
    """One bridge.execute() stage-touching op on the /mcp path: LOP hash
    target, touches_stage=True → the full before-hash / after-hash /
    composition-validation shape. fn is a no-op: the cell measures the per-op
    traversal ENVELOPE, not mutation semantics (delta reads no_change)."""
    counters = _new_counters()
    stage = (stage_factory(counters, prims) if stage_factory
             else _CountingStage(counters, prims))
    lop = _make_lop(counters, stage)
    hou_obj = _CountingHou({"/stage": lop})
    with _patched(hou_obj, threshold):
        bridge = LosslessExecutionBridge()
        _wrap_scene_hash(bridge, counters)
        res = bridge.execute(_op(lambda: None,
                                 touches_stage=True, stage_path="/stage"))
        if not res.success:
            raise PerfScenarioError(f"mcp_lop_op did not succeed: {res.error}")
        mode = res.integrity.stage_hash_mode
        if expect_mode and mode != expect_mode:
            raise PerfScenarioError(
                f"scenario premise violated: stage_hash_mode={mode!r}, "
                f"expected {expect_mode!r} (prims={prims}, threshold={threshold})")
    return counters


def mcp_lop_op_below_gate(prims: int = 100, threshold: int = 1000,
                          expect_mode: str = "full",
                          stage_factory=None) -> dict[str, int]:
    """S-A — gate silent below both terms: mode 'full', Flatten x2. Exists to
    prove the gate is silent, not to bound cost (below the gate the counter
    UNDERSTATES real cost: Flatten is O(value volume))."""
    return _mcp_lop_op(prims, threshold, expect_mode, stage_factory)


def mcp_lop_op_above_gate(prims: int = 5000, threshold: int = 1000,
                          expect_mode: str = "reduced",
                          stage_factory=None) -> dict[str, int]:
    """S-B — THE 98b556f CELL: above the prim gate, mode 'reduced',
    flatten_exports must be 0 (that IS the 4x win) and value_reads 0."""
    return _mcp_lop_op(prims, threshold, expect_mode, stage_factory)


def mcp_lop_op_above_gate_2x(prims: int = 10000, threshold: int = 1000,
                             expect_mode: str = "reduced") -> dict[str, int]:
    """S-B2 — THE SLOPE CELL: same env, 2N prims. (counter(2N)-counter(N))/N
    pins scale-dependent work; the bounded probes contribute 0 to the slope."""
    return _mcp_lop_op(prims, threshold, expect_mode)


def live_ws_op() -> dict[str, int]:
    """S-C — the live-envelope hash shape: two _compute_scene_hash(target,
    include_stage=False) calls (integrity_envelope.py's before/after), on a
    node that carries BOTH geometry (H1 residue — intrinsics counted) and a
    live stage() — which must NEVER be traversed or flattened. Pins the
    bridge.py promise 'the live /synapse path can NEVER hit stage.Flatten()'
    structurally, not because the stage was absent."""
    counters = _new_counters()
    stage = _CountingStage(counters, 5000)
    node = _CountingNode(counters, stage=None, geo=_CountingGeo(counters))
    node.stage = lambda: stage  # reachable on purpose — the skip is structural
    hou_obj = _CountingHou({"/geo/sop": node})
    with _patched(hou_obj, 1000):
        bridge = LosslessExecutionBridge()
        _wrap_scene_hash(bridge, counters)
        h1 = bridge._compute_scene_hash("/geo/sop", include_stage=False)
        h2 = bridge._compute_scene_hash("/geo/sop", include_stage=False)
        if not h1 or not h2:
            raise PerfScenarioError("live envelope hash returned empty")
    return counters


def rollback_op(prims: int = 5000, threshold: int = 1000) -> dict[str, int]:
    """S-D — the op fn mutates the stage then raises: worst-case hash count on
    the H2 guarded-rollback path. The fake undo cannot revert, so the branch
    taken is deterministic: hash differs → performUndo (no-op) → re-hash still
    differs → delta 'rollback_incomplete'. 3 scene-hash calls."""
    counters = _new_counters()
    stage = _CountingStage(counters, prims)
    lop = _make_lop(counters, stage)
    hou_obj = _CountingHou({"/stage": lop})

    def _mutate_and_raise():
        stage.add_prims(1)
        raise RuntimeError("perf ratchet S-D: deliberate failure")

    with _patched(hou_obj, threshold):
        bridge = LosslessExecutionBridge()
        _wrap_scene_hash(bridge, counters)
        res = bridge.execute(_op(_mutate_and_raise,
                                 touches_stage=True, stage_path="/stage"))
        if res.success:
            raise PerfScenarioError("rollback_op unexpectedly succeeded")
        if res.integrity.delta_hash != "rollback_incomplete":
            raise PerfScenarioError(
                f"rollback branch drifted: delta_hash="
                f"{res.integrity.delta_hash!r} (expected rollback_incomplete)")
    return counters


def blast_radius_trace(fanout: int = 8) -> dict[str, int]:
    """S-E — R7 _infer_stage_touch cost shape: flat fanout graph (root SOP →
    F dependents, no LOP anywhere) so the trace walks 1+F nodes and finds
    nothing. LINEAR_IN_NODES. No cost test for R7 existed before this."""
    counters = _new_counters()
    root = _CountingGraphNode(counters, "/geo/root")
    for i in range(fanout):
        root._deps.append(_CountingGraphNode(counters, f"/geo/dep{i}"))
    plain = _CountingNode(counters)  # hash target: no stage, no geo
    hou_obj = _CountingHou({"/geo/root": root, "/obj": plain})
    with _patched(hou_obj, 1000):
        bridge = LosslessExecutionBridge()
        _wrap_scene_hash(bridge, counters)
        res = bridge.execute(_op(lambda **kw: None,
                                 kwargs={"node_path": "/geo/root"}))
        if not res.success:
            raise PerfScenarioError(f"blast_radius_trace failed: {res.error}")
    return counters


def blast_radius_trace_2x(fanout: int = 16) -> dict[str, int]:
    return blast_radius_trace(fanout)


# ── registry: name → (driver, default params, env pins) ─────────────────────

SCENARIOS = {
    "mcp_lop_op_below_gate": mcp_lop_op_below_gate,
    "mcp_lop_op_above_gate": mcp_lop_op_above_gate,
    "mcp_lop_op_above_gate_2x": mcp_lop_op_above_gate_2x,
    "live_ws_op": live_ws_op,
    "rollback_op": rollback_op,
    "blast_radius_trace": blast_radius_trace,
    "blast_radius_trace_2x": blast_radius_trace_2x,
}

# env_pins the floor cells record (Law 2: the count's meaning depends on env).
ENV_PINS = {
    "SYNAPSE_STAGE_HASH_PRIM_THRESHOLD": "1000",
    "SYNAPSE_STAGE_HASH_VOLUME_THRESHOLD": str(PINNED_VOLUME_THRESHOLD),
    "SYNAPSE_STAGE_HASH_LARGE_MODE": "<unset>",
}


def measure(scenario: str, **params) -> dict[str, int]:
    """Run one scenario, return its counter dict. Deterministic: same args →
    byte-identical dict (json.dumps sort_keys equality), with or without pxr
    installed, regardless of operator env."""
    if scenario not in SCENARIOS:
        raise KeyError(f"unknown perf scenario {scenario!r}; "
                       f"known: {sorted(SCENARIOS)}")
    return SCENARIOS[scenario](**params)


def measure_all() -> dict[str, dict[str, int]]:
    """All v1 cells at their floor-default params, in a fixed order."""
    return {name: SCENARIOS[name]() for name in sorted(SCENARIOS)}


def counters_digest(counters: dict[str, int]) -> str:
    """Canonical byte form used for byte-identity assertions."""
    return json.dumps(counters, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":  # throwaway expected-value check (I2 build order #2)
    for name, c in measure_all().items():
        print(f"{name}: {counters_digest(c)}")
