"""R-CACHE-1 insert slice -- gate tests for ``synapse_insert_cache`` (blueprint §17.3).

Runs with ZERO ``hou`` present -- every graph is a duck-typed fake, matching the convention in
tests/test_cache_assess_tool.py and tests/test_cache_no_forced_cook.py. The three §17.3 gate
requirements this file pins:

  1. CLASS REGISTRATION -- insert_cache uses the mutation/Review path (Operation.gate_level ==
     REVIEW, is_read_only False), is NOT in bridge_adapter._READ_ONLY_TOOLS, is NOT in
     _DISK_WRITING_TOOLS, and is registered as a mutation across the tool registry / handlers /
     RBAC (artist tier, never viewer).
  2. DECISION-ID REJECTION -- unknown id -> mismatched; expired id (old monotonic issue time) ->
     expired. No mutation occurs on rejection (the source node is never even resolved).
  3. LLM-EXPLANATION-CANNOT-ALTER-BOUNDARY-PLAN -- arbitrary caller text does not change the node
     type or parm set; the plan is derived solely from the stored decision's registry-resolved
     strategy. Proven structurally (no prose channel into resolve_boundary_plan) AND behaviorally
     (two runs, contradictory explanations, byte-identical parameter set).

A fake cache node whose ``cook()``/``save()``/``geometry()`` RAISE is the negative control that
the handler never writes to disk or cooks the File Cache.

Pure Python. Every test states the condition under which it fails.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYTHON_DIR = _REPO_ROOT / "python"
_HOST_DIR = _REPO_ROOT / "host"
for _p in (_PYTHON_DIR, _HOST_DIR, _REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import synapse.server.handlers_cache as hc  # noqa: E402
from synapse.cache_policy import NodeDescriptor, resolve_strategy  # noqa: E402


# =============================================================================================
# Fake graph -- exactly the surface insert_cache_core touches, nothing more.
# =============================================================================================

class _DiskWriteTripwire(AssertionError):
    """Distinct type so a disk-write/cook attempt is never confused with an ordinary assert."""


class _FakeParm:
    def __init__(self, name):
        self._name = name
        self.value = None
        self.set_calls = 0

    def set(self, v):
        self.set_calls += 1
        self.value = v


class _FakeNodeType:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _FakeConnection:
    def __init__(self, downstream, input_index, output_index=0):
        self._d = downstream
        self._i = input_index
        self._o = output_index

    def outputNode(self):
        return self._d

    def inputIndex(self):
        return self._i

    def outputIndex(self):
        return self._o


# The parm set a live ``filecache`` SOP exposes on H22.0.400 (probe 2026-08-09), restricted to
# the ones this slice sets.
_FILECACHE_PARMS = ("file", "filemethod", "filetype", "trange", "timedependent", "cachesim")


class _FakeNode:
    """Duck-typed stand-in for a hou SOP node. A plain class (no __getattr__), so any surface the
    handler touches that we did NOT model raises AttributeError and fails the test loudly rather
    than passing against a permissive mock. ``cook``/``save``/``geometry`` are DISK-WRITE
    TRIPWIRES -- insert must never call them."""

    def __init__(self, name, path, parent=None, type_name="box", parms=()):
        self._name = name
        self._path = path
        self._parent = parent
        self._type = type_name
        self._parms = {p: _FakeParm(p) for p in parms}
        self.inputs = {}          # input_index -> (source_node, output_index)
        self.out_conns = []       # list[_FakeConnection]
        self.created = []
        self.move_calls = 0

    def name(self):
        return self._name

    def path(self):
        return self._path

    def parent(self):
        return self._parent

    def type(self):
        return _FakeNodeType(self._type)

    def outputConnections(self):
        return list(self.out_conns)

    def setInput(self, idx, src, out=0):
        self.inputs[idx] = (src, out)

    def parm(self, name):
        return self._parms.get(name)

    def moveToGoodPosition(self):
        self.move_calls += 1

    def createNode(self, type_name, node_name):
        child = _FakeNode(node_name, f"{self._path}/{node_name}", parent=self,
                          type_name=type_name, parms=_FILECACHE_PARMS)
        self.created.append(child)
        return child

    # --- disk-write / cook tripwires: NEVER invoked by an insertion ---
    def cook(self, *a, **k):
        raise _DiskWriteTripwire("cook() called during insert -- would write cache to disk")

    def save(self, *a, **k):
        raise _DiskWriteTripwire("save() called during insert -- would write cache to disk")

    def geometry(self, *a, **k):
        raise _DiskWriteTripwire("geometry() called during insert")


def _make_source_graph(source_type="box", n_downstream=2):
    """container(geo) -> source -> {downstreamA, downstreamB}. Returns (container, source, [down])."""
    container = _FakeNode("geo1", "/obj/geo1", parent=None, type_name="geo")
    source = _FakeNode("solver1", "/obj/geo1/solver1", parent=container, type_name=source_type)
    downstream = []
    for i in range(n_downstream):
        d = _FakeNode(f"down{i}", f"/obj/geo1/down{i}", parent=container, type_name="null")
        d.setInput(0, source)
        source.out_conns.append(_FakeConnection(d, 0))
        downstream.append(d)
    return container, source, downstream


def _seed(store, descriptor, node_path="/obj/geo1/solver1", *, frame_range=None,
          proposed_path="unknown", td=None, issued_monotonic=None, strategy_id=None):
    """Seed the issued-decision store exactly as assess_cache_core does, for a chosen descriptor.
    strategy_id defaults to the real registry resolution (no drift); override it to force drift."""
    resolved = resolve_strategy(descriptor).strategy_id
    store.record("dec-1", {
        "strategy_id": strategy_id if strategy_id is not None else resolved,
        "strategy_supported": True,
        "decision": None,
        "evidence_digest": "sha256:deadbeef",
        "descriptor": descriptor,
        "node_path": node_path,
        "node_type": "solver1",
        "frame_range": frame_range,
        "proposed_path": proposed_path,
        "time_dependent_observed": td,
        "issued_monotonic": time.monotonic() if issued_monotonic is None else issued_monotonic,
    })
    return "dec-1"


def _sop_solver_descriptor():
    return NodeDescriptor(context="sop", is_solver_result=True)


# =============================================================================================
# Gate 1 -- class registration (mutation/Review, not read-only, not disk-writing)
# =============================================================================================

def test_gate_operation_resolves_to_review_and_is_not_read_only():
    """The load-bearing gate assertion: constructing the Operation the bridge would build for
    insert_cache yields REVIEW (via the shared/bridge.py:767 default -- insert_cache is
    deliberately NOT in OPERATION_GATES) and is_read_only False. Fails if insert_cache is ever
    mapped to a read-only prefix or a stricter/looser explicit gate without a deliberate diff."""
    from shared.bridge import Operation, GateLevel
    from shared.types import AgentID

    op = Operation(agent_id=AgentID.HANDS, operation_type="insert_cache", summary="x", fn=lambda: None)
    assert op.gate_level == GateLevel.REVIEW
    assert op.is_read_only is False


def test_gate_tool_not_read_only_and_not_disk_writing_in_bridge_adapter():
    import synapse.panel.bridge_adapter as ba

    assert ba.is_read_only("synapse_insert_cache") is False
    assert "synapse_insert_cache" not in ba._READ_ONLY_TOOLS
    assert "synapse_insert_cache" not in ba._DISK_WRITING_TOOLS
    assert ba._TOOL_TO_OPERATION["synapse_insert_cache"] == "insert_cache"


def test_gate_tool_registered_as_mutation_in_registry():
    import synapse.mcp._tool_registry as tr

    assert "synapse_insert_cache" in tr.TOOL_DISPATCH
    assert tr.TOOL_DISPATCH["synapse_insert_cache"][0] == "insert_cache"
    ann = tr.TOOL_JSON["synapse_insert_cache"]["annotations"]
    assert ann["readOnlyHint"] is False, "insert is a mutation, not read-only"
    assert ann["destructiveHint"] is False, "insertion is undoable/non-destructive"
    assert ann["idempotentHint"] is False, "each call creates a new node"
    # decision_id is the one required input; explanation is optional prose (receipt-only).
    props = tr.TOOL_JSON["synapse_insert_cache"]["inputSchema"]
    assert props["required"] == ["decision_id"]
    assert set(props["properties"].keys()) == {"decision_id", "explanation"}


def test_gate_command_registered_and_not_read_only_in_handlers():
    import synapse.server.handlers as h

    assert hasattr(h.SynapseHandler, "_handle_insert_cache")
    # A mutation MUST be absent from _READ_ONLY_COMMANDS so it takes the C5 lock + live envelope.
    assert "insert_cache" not in h._READ_ONLY_COMMANDS


def test_gate_rbac_insert_is_artist_tier_never_viewer():
    import synapse.server.rbac as rbac

    assert "insert_cache" in rbac._ARTIST_COMMANDS
    assert "insert_cache" not in rbac._VIEWER_COMMANDS
    # A viewer must NOT be able to insert; an artist must.
    assert rbac.check_permission(rbac.Role.VIEWER, "insert_cache") is False
    assert rbac.check_permission(rbac.Role.ARTIST, "insert_cache") is True


# =============================================================================================
# Gate 2 -- decision-ID rejection (no mutation on rejection)
# =============================================================================================

def test_reject_unknown_decision_id_is_mismatched_and_never_resolves_node():
    store = hc.IssuedDecisionStore()
    calls = [0]

    def tripwire():
        calls[0] += 1
        raise AssertionError("resolve_source_node called despite a rejected decision")

    r = hc.insert_cache_core(decision_id="never-issued", resolve_source_node=tripwire, store=store)
    assert r["status"] == "rejected"
    assert r["reason"] == "mismatched"
    assert calls[0] == 0, "no node may be resolved (let alone mutated) on a mismatched decision"
    assert "created_node_path" not in r


def test_reject_expired_decision_id_is_expired_and_never_resolves_node():
    store = hc.IssuedDecisionStore()
    # issued past the TTL window (monotonic in the past).
    old = time.monotonic() - hc.INSERT_CACHE_DECISION_TTL_SECONDS - 5.0
    _seed(store, _sop_solver_descriptor(), issued_monotonic=old)
    calls = [0]

    def tripwire():
        calls[0] += 1
        raise AssertionError("resolve_source_node called despite an expired decision")

    r = hc.insert_cache_core(decision_id="dec-1", resolve_source_node=tripwire, store=store)
    assert r["status"] == "rejected"
    assert r["reason"] == "expired"
    assert calls[0] == 0


def test_reject_strategy_drift_never_mutates():
    store = hc.IssuedDecisionStore()
    # Store a strategy_id that will NOT match the descriptor's real resolution.
    _seed(store, _sop_solver_descriptor(), strategy_id="sop_filecache_vdb_v1")
    calls = [0]

    def tripwire():
        calls[0] += 1
        raise AssertionError("resolve_source_node called despite strategy drift")

    r = hc.insert_cache_core(decision_id="dec-1", resolve_source_node=tripwire, store=store)
    assert r["status"] == "rejected"
    assert r["reason"] == "strategy_drift"
    assert calls[0] == 0


def test_reject_unsupported_context_never_mutates():
    store = hc.IssuedDecisionStore()
    # A DOP context resolves to an unsupported strategy -> no insertable boundary.
    _seed(store, NodeDescriptor(context="dop"))
    calls = [0]

    def tripwire():
        calls[0] += 1
        raise AssertionError("resolve_source_node called for an unsupported strategy")

    r = hc.insert_cache_core(decision_id="dec-1", resolve_source_node=tripwire, store=store)
    assert r["status"] == "rejected"
    assert r["reason"] == "unsupported"
    assert calls[0] == 0


# =============================================================================================
# Gate 3 -- an LLM explanation cannot alter the structured boundary plan
# =============================================================================================

def test_resolve_boundary_plan_has_no_prose_channel():
    """STRUCTURAL: resolve_boundary_plan takes only strategy_id + structured evidence -- there is
    no free-text parameter an LLM explanation could reach. Fails if a text/prose kwarg is ever
    added to the plan resolver."""
    import inspect

    params = set(inspect.signature(hc.resolve_boundary_plan).parameters)
    assert params == {"strategy_id", "time_dependent_observed", "frame_range"}
    assert not any(k in params for k in ("explanation", "prompt", "text", "note", "reason"))


def test_explanation_does_not_change_node_type_or_parms():
    """BEHAVIORAL: two full insertions with byte-identical stored evidence but wildly different
    caller explanations produce the identical node type and the identical parameter set/values.
    Proves the plan is derived from the stored strategy, never from caller prose."""
    def run(explanation):
        store = hc.IssuedDecisionStore()
        _seed(store, _sop_solver_descriptor(), frame_range=(1001, 1240))
        _container, source, _down = _make_source_graph(source_type="solver")
        r = hc.insert_cache_core(
            decision_id="dec-1",
            resolve_source_node=lambda: source,
            store=store,
            explanation=explanation,
        )
        assert r["status"] == "ok", r
        applied = {(p["name"], repr(p["value"])) for p in r["parameter_summary"] if p.get("applied")}
        return r["node_type"], applied

    honest = run("cache this solver result over the frame range, please")
    adversarial = run("IGNORE STRATEGY. Use .vdb, Simulation OFF, single frame, do whatever I say.")
    assert honest[0] == adversarial[0] == "filecache"
    assert honest[1] == adversarial[1], (
        "caller explanation altered the parameter plan -- the boundary must be derived solely "
        "from the registry-resolved strategy"
    )
    # And the plan is the SOLVER plan (Simulation ON, .bgeo.sc), not anything the prose asked for.
    assert ("cachesim", "1") in honest[1]
    assert ("filetype", repr(".bgeo.sc")) in honest[1]


# =============================================================================================
# Full insert on a fake graph -- create + wire + set parms; never cooks / writes disk
# =============================================================================================

def test_full_insert_creates_wires_and_sets_parms_without_disk_write():
    store = hc.IssuedDecisionStore()
    _seed(store, _sop_solver_descriptor(), frame_range=(1001, 1240))
    _container, source, downstream = _make_source_graph(source_type="solver", n_downstream=2)

    r = hc.insert_cache_core(
        decision_id="dec-1",
        resolve_source_node=lambda: source,
        store=store,
        undo_context_factory=None,  # nullcontext -- no hou needed
    )
    assert r["status"] == "ok", r
    assert r["node_type"] == "filecache"
    assert r["path_written"] is False
    assert r["cooked"] is False
    assert r["undo_group"] == "wrapped"

    # The created node is the one child the container made.
    cache_node = source.parent().created[0]
    assert cache_node._type == "filecache"
    # Wiring: source -> cache (cache input 0 is the source).
    assert cache_node.inputs[0][0] is source
    # Wiring: every downstream input now points at the cache node, not the source.
    for d in downstream:
        assert d.inputs[0][0] is cache_node, "downstream was not rewired to the cache node"
    assert len(r["downstream_rewired"]) == 2

    # Parameters: path authored explicitly, format/sim per the solver strategy.
    assert cache_node.parm("filemethod").value == "explicit"
    assert cache_node.parm("file").value.endswith(".bgeo.sc") or "$F4" in cache_node.parm("file").value
    assert cache_node.parm("filetype").value == ".bgeo.sc"
    assert cache_node.parm("cachesim").value == 1          # Simulation ON for solver result
    assert cache_node.parm("timedependent").value == 1     # Time Dependent ON for solver result
    assert cache_node.parm("trange").value == "normal"     # frame range 1001..1240

    # The receipt path parameter was SET but nothing was written / cooked (tripwires never fired).
    assert r["proposed_path"] == cache_node.parm("file").value


def test_vdb_strategy_selects_vdb_format():
    store = hc.IssuedDecisionStore()
    _seed(store, NodeDescriptor(context="sop", data_class="vdb_only"))
    _container, source, _down = _make_source_graph()
    r = hc.insert_cache_core(decision_id="dec-1", resolve_source_node=lambda: source, store=store)
    assert r["status"] == "ok", r
    cache_node = source.parent().created[0]
    assert cache_node.parm("filetype").value == ".vdb"


def test_absent_parm_is_skipped_defensively_not_crash():
    """If a File Cache parm the plan wants is absent on this build, it is recorded as skipped with
    a warning, not raised. Simulated with a cache node missing 'cachesim'."""
    store = hc.IssuedDecisionStore()
    _seed(store, _sop_solver_descriptor())

    _container, source, _down = _make_source_graph(source_type="solver")

    # Patch the container's createNode to return a cache node missing 'cachesim'.
    reduced = tuple(p for p in _FILECACHE_PARMS if p != "cachesim")

    def _create_reduced(type_name, node_name):
        child = _FakeNode(node_name, f"{source.parent()._path}/{node_name}", parent=source.parent(),
                          type_name=type_name, parms=reduced)
        source.parent().created.append(child)
        return child

    source.parent().createNode = _create_reduced

    r = hc.insert_cache_core(decision_id="dec-1", resolve_source_node=lambda: source, store=store)
    assert r["status"] == "ok", r
    skipped = [p for p in r["parameter_summary"] if not p.get("applied")]
    assert any(p["name"] == "cachesim" and p["reason"] == "parm_absent" for p in skipped)
    assert any("cachesim" in w for w in r["warnings"])


def test_default_path_derived_when_proposed_path_unknown():
    store = hc.IssuedDecisionStore()
    _seed(store, _sop_solver_descriptor(), proposed_path="unknown")
    _container, source, _down = _make_source_graph(source_type="solver")
    r = hc.insert_cache_core(decision_id="dec-1", resolve_source_node=lambda: source, store=store)
    assert r["status"] == "ok", r
    # $HIP-relative default keyed on the source node name, with the strategy's extension.
    assert r["proposed_path"].startswith("$HIP/cache/")
    assert r["proposed_path"].endswith(".bgeo.sc")
    assert "$F4" in r["proposed_path"]


def test_source_missing_is_clean_reject():
    store = hc.IssuedDecisionStore()
    _seed(store, _sop_solver_descriptor())
    r = hc.insert_cache_core(decision_id="dec-1", resolve_source_node=lambda: None, store=store)
    assert r["status"] == "rejected"
    assert r["reason"] == "source_missing"


# =============================================================================================
# assess -> insert end to end (the real store-writing path), still zero hou
# =============================================================================================

class _AssessInsertFakeNode(_FakeNode):
    """Fake supporting BOTH the assess surface (needsToCook/isTimeDependent/lastCookTime/
    cookCount/geometry/path/type) AND the insert surface (parent/outputConnections/createNode/
    setInput). Used only for the end-to-end test that seeds the store via the REAL assess path."""

    def __init__(self, *args, needs_to_cook=False, last_cook_ms=6000.0, cook_count=3,
                 time_dependent=True, **kwargs):
        super().__init__(*args, **kwargs)
        self._needs = needs_to_cook
        self._ms = last_cook_ms
        self._cc = cook_count
        self._td = time_dependent

    def needsToCook(self):
        return self._needs

    def isTimeDependent(self, for_last_cook=False):
        return self._td

    def lastCookTime(self):
        return self._ms

    def cookCount(self):
        return self._cc

    # NOTE: geometry() is a tripwire inherited from _FakeNode -- but this node is CLEAN
    # (needs_to_cook False), so observe_node_passively WILL call geometry(). Override it to
    # return a minimal geometry rather than raise, since a clean assess legitimately reads it.
    def geometry(self):
        class _G:
            def intrinsicValue(self, _n):
                return 1_048_576
        return _G()

    def type(self):
        return _FakeNodeType("Sop")  # assess classifies context from category name; keep it SOP


def test_assess_then_insert_end_to_end_through_the_real_store():
    """The real chain: assess_cache_core records the decision -> insert_cache_core consumes it.
    Uses one combined fake node and the module's own _ISSUED_DECISION_STORE via an injected store.
    Zero hou. Proves the two tools agree on the store contract."""
    from synapse.cache_policy import MachineProfile, CacheVolume

    issued = hc.IssuedDecisionStore()
    node = _AssessInsertFakeNode("solver1", "/obj/geo1/solver1",
                                 parent=_FakeNode("geo1", "/obj/geo1", type_name="geo"),
                                 type_name="Sop")
    # give it a downstream so insert has something to rewire
    downstream = _FakeNode("down0", "/obj/geo1/down0", parent=node.parent(), type_name="null")
    downstream.setInput(0, node)
    node.out_conns.append(_FakeConnection(downstream, 0))

    machine = MachineProfile(
        ram_total_bytes=128_000_000_000, ram_available_bytes=100_000_000_000,
        cache_volume=CacheVolume(free_bytes=1_000_000_000_000, total_bytes=2_000_000_000_000),
    )
    resp = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine, node_type="filecache",
        context="sop",  # pass explicitly; the fake's type() has no category() for _classify_context
        is_solver_result=True, frame_range=(1001, 1240),
        issued_decision_store=issued,
    )
    decision_id = resp["decision"]["decision_id"]
    assert issued.lookup(decision_id) is not None, "assess must record the issued decision"

    ins = hc.insert_cache_core(
        decision_id=decision_id, resolve_source_node=lambda: node, store=issued,
    )
    assert ins["status"] == "ok", ins
    assert ins["strategy_id"] == "sop_filecache_solver_result_v1"
    assert ins["evidence_digest"] == resp["decision"]["evidence_digest"]
    cache_node = node.parent().created[0]
    assert cache_node._type == "filecache"
    assert downstream.inputs[0][0] is cache_node
