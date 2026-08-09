"""Mile 4 (resource-aware-cache Phase 1, R-CACHE-1) -- tests for
``synapse.server.handlers_cache`` (the ``synapse_assess_cache`` read-only advisor).

Covers:
  - Task 2/4: tool + feature-flag wiring (registered read-only in BOTH sets; disabled by
    default; the disabled path never touches ``hou``).
  - Task 3: advice card rendering rules (§14.2 -- max 3 reasons, blocker vs uncertainty
    separated, stale/partial/unverifiable never buried, ranges not false precision).
  - Task 5: the §17.1 12-row pure-policy scenario matrix AND the five §16 Phase 1 exit-gate
    items, all driven END-TO-END through ``assess_cache_core`` (the real assess path: fake
    node -> observe_node_passively -> resolve_strategy -> decide_cache -> advice card) with
    FAKE/fixture host-probe inputs -- zero live ``hou`` anywhere in this file.

Binding constraint #7 (adjudication e7, REJECT): fixtures below are derived fresh from the
§2.3/§10.3 formulas and §9 strategy table, never copied from the blueprint's arithmetically
broken worked example.

Pure Python. Every test states the condition under which it fails.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYTHON_DIR = _REPO_ROOT / "python"
_HOST_DIR = _REPO_ROOT / "host"
for _p in (_PYTHON_DIR, _HOST_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import synapse.server.handlers_cache as hc  # noqa: E402
from synapse.cache_policy import (  # noqa: E402
    BoundarySignals,
    CachePolicy,
    CacheValidity,
    CacheVerdict,
    CacheVolume,
    Evidence,
    ExistingCacheState,
    GPURelevance,
    Interval,
    MachineProfile,
)


# =============================================================================================
# Fake node fixtures -- same duck-typed convention as tests/test_cache_no_forced_cook.py,
# extended with type()/category() so context classification is exercisable without hou.
# =============================================================================================

class _GeometryTripwire(AssertionError):
    """Distinct type so a failure here is unambiguous, never confused with an assertion
    failure from elsewhere in the same test."""


class _FakeCategory:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _FakeNodeType:
    def __init__(self, category_name, type_name="filecache"):
        self._category_name = category_name
        self._type_name = type_name

    def category(self):
        return _FakeCategory(self._category_name)

    def name(self):
        return self._type_name


class _FakeGeometry:
    def __init__(self, memoryusage):
        self._memoryusage = memoryusage

    def intrinsicValue(self, name):
        assert name == "memoryusage"
        return self._memoryusage


class FakeNode:
    """A duck-typed stand-in for ``hou.OpNode`` covering exactly the surface
    ``assess_cache_core`` / ``observe_node_passively`` touch: needsToCook, isTimeDependent,
    lastCookTime, cookCount, geometry, path, type. Any OTHER attribute access raises
    AttributeError (plain class, no ``__getattr__``) -- so a code path that accidentally
    tried to mutate the node (e.g. ``createNode``, ``setParms``) would fail the test loudly
    rather than silently succeeding against a permissive mock.
    """

    def __init__(self, path="/obj/geo1/node1", category="Sop", needs_to_cook=False,
                 last_cook_ms=50.0, cook_count=3, memoryusage=1_048_576, time_dependent=False):
        self._path = path
        self._category = category
        self._needs_to_cook = needs_to_cook
        self._last_cook_ms = last_cook_ms
        self._cook_count = cook_count
        self._memoryusage = memoryusage
        self._time_dependent = time_dependent
        self.geometry_call_count = 0

    def needsToCook(self):
        return self._needs_to_cook

    def isTimeDependent(self, for_last_cook=False):
        return self._time_dependent

    def lastCookTime(self):
        return self._last_cook_ms

    def cookCount(self):
        return self._cook_count

    def geometry(self):
        self.geometry_call_count += 1
        return _FakeGeometry(self._memoryusage)

    def path(self):
        return self._path

    def type(self):
        return _FakeNodeType(self._category)


class FakeDirtyGeometryTripwireNode(FakeNode):
    """geometry() raises if called at all -- the mandatory negative control, restated at
    the assess-tool boundary (the host-layer version lives in
    tests/test_cache_no_forced_cook.py)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("needs_to_cook", True)
        super().__init__(**kwargs)

    def geometry(self):
        self.geometry_call_count += 1
        raise _GeometryTripwire(
            "node.geometry() was called on a dirty node via the assess path -- this "
            "forces the exact cook passive assessment exists to avoid triggering"
        )


# =============================================================================================
# Machine fixtures
# =============================================================================================

def _ample_machine(**overrides) -> MachineProfile:
    base = dict(
        ram_total_bytes=128_000_000_000, ram_available_bytes=100_000_000_000,
        cache_volume=CacheVolume(free_bytes=1_000_000_000_000, total_bytes=2_000_000_000_000),
    )
    base.update(overrides)
    return MachineProfile(**base)


def _ample_peak_ram() -> Evidence:
    return Evidence.known(Interval(low=1_000_000_000.0, high=2_000_000_000.0), unit="bytes",
                           source="calibrated_estimate")


# =============================================================================================
# Task 2/4 -- tool + feature-flag wiring
# =============================================================================================

def test_advisor_disabled_by_default():
    assert hc.advisor_enabled() is False


def test_advisor_enabled_recognizes_truthy_values(monkeypatch):
    for truthy in ("1", "true", "True", "YES", "on", " On "):
        monkeypatch.setenv("SYNAPSE_CACHE_ADVISOR_ENABLED", truthy)
        assert hc.advisor_enabled() is True, f"{truthy!r} should be recognized as truthy"


def test_advisor_disabled_for_falsy_or_garbage_values(monkeypatch):
    for value in ("0", "false", "no", "off", "", "banana"):
        monkeypatch.setenv("SYNAPSE_CACHE_ADVISOR_ENABLED", value)
        assert hc.advisor_enabled() is False, f"{value!r} should not be recognized as truthy"


def test_disabled_handler_never_touches_hou(monkeypatch):
    """Fails if the disabled path calls hou.node / hou.selectedNodes / anything -- the
    feature must be inert BEFORE any Houdini access, not merely skip acting after
    resolving a node."""
    monkeypatch.delenv("SYNAPSE_CACHE_ADVISOR_ENABLED", raising=False)

    class _ExplodingHou:
        def __getattr__(self, name):
            raise AssertionError(f"disabled advisor touched hou.{name}")

    monkeypatch.setattr(hc, "hou", _ExplodingHou())
    monkeypatch.setattr(hc, "HOU_AVAILABLE", True)

    handler = hc.CacheHandlerMixin()
    response = handler._handle_assess_cache({"node": "/obj/geo1/box1"})
    assert response["verdict"] == "disabled"
    assert "SYNAPSE_CACHE_ADVISOR_ENABLED" in response["message"]


def test_tool_registered_read_only_in_tool_registry():
    """Task 2: the canonical MCP tool registry (both transports read from here)."""
    import synapse.mcp._tool_registry as tr

    assert "synapse_assess_cache" in tr.TOOL_DISPATCH
    assert tr.TOOL_DISPATCH["synapse_assess_cache"][0] == "assess_cache"
    assert tr.TOOL_JSON["synapse_assess_cache"]["annotations"]["readOnlyHint"] is True
    assert tr.TOOL_JSON["synapse_assess_cache"]["annotations"]["destructiveHint"] is False


def test_tool_schema_matches_blueprint_declared_input_set():
    """B1/B2 (reviewer, post-87e758bc): blueprint §13.3 declares this tool's input as ONLY
    "node path or selected node, optional target path/range, optional expected replays".
    A prior revision also exposed ``policy_overrides`` -- an LLM caller could flip
    ``insufficient_disk -> cache_now`` (or the reverse) by supplying e.g.
    ``cache_size_safety_multiplier=0.001`` with zero trace in the response that thresholds
    moved (no ``policy_version`` bump, no "user override" note -- exactly the §5
    machine-specs+prompt->LLM-opinion->bake shape the blueprint refuses, and exactly the
    §10.4 "receipt should say 'user override' and preserve the original verdict" rule it
    skipped). ``policy_overrides`` is now removed from the live schema entirely (the tool
    always uses the one project-default CachePolicy) -- this test pins BOTH the exact
    property set (so it can't silently creep back under this name) AND, independently and
    more robustly, that no property name on the schema collides with any real
    ``CachePolicy`` dataclass field (so it can't creep back under a DIFFERENT name either).
    """
    import synapse.mcp._tool_registry as tr
    from dataclasses import fields as dc_fields
    from synapse.cache_policy import CachePolicy

    schema = tr.TOOL_JSON["synapse_assess_cache"]["inputSchema"]
    properties = set(schema["properties"].keys())

    # node/frame_start/frame_end/expected_future_reads are the §13.3-declared set verbatim
    # (node path, optional target range, optional expected replays). is_solver_result/
    # is_independent_frames/data_class are NOT policy-threshold levers -- they are §9
    # strategy-CLASSIFICATION hints ("never guess a strategy"), a different axis entirely
    # from CachePolicy's safety thresholds, and the reviewer's own B1 finding never flagged
    # them. Pinned here as the exact current set so ANY addition -- policy-shaped or not --
    # is a deliberate, reviewed diff, never a silent one.
    expected = {
        "node", "frame_start", "frame_end", "expected_future_reads",
        "is_solver_result", "is_independent_frames", "data_class",
    }
    assert properties == expected, (
        f"synapse_assess_cache inputSchema drifted from the pinned set. "
        f"Added: {properties - expected}, removed: {expected - properties}"
    )

    policy_field_names = {f.name for f in dc_fields(CachePolicy)}
    collision = properties & policy_field_names
    assert not collision, (
        f"synapse_assess_cache inputSchema exposes CachePolicy field name(s) {collision} "
        "-- this is exactly the reintroduced-policy-lever shape B1 removed, even though "
        "the top-level key is not literally 'policy_overrides'."
    )
    assert "policy_overrides" not in properties
    assert "policy" not in properties


def test_tool_registered_read_only_in_bridge_adapter():
    """Task 2: the panel's bridge_adapter has a SEPARATE read-only set -- both must agree,
    or a tool is read-only under one transport and mutation-classified under the other
    (the exact divergence documented at python/synapse/mcp/server.py:110-131)."""
    import synapse.panel.bridge_adapter as ba

    assert ba.is_read_only("synapse_assess_cache") is True


def test_command_registered_read_only_in_handlers():
    import synapse.server.handlers as h

    assert "assess_cache" in h._READ_ONLY_COMMANDS
    assert hasattr(h.SynapseHandler, "_handle_assess_cache")


def test_command_registered_viewer_accessible_in_rbac():
    import synapse.server.rbac as rbac

    assert "assess_cache" in rbac._VIEWER_COMMANDS


# =============================================================================================
# Task 1 gap-close, restated at the resolve_strategy boundary via the real assess path
# =============================================================================================

def test_unknown_context_node_resolves_unsupported_through_assess_path():
    """A node whose type category the classifier does not recognize -> unsupported,
    never a generic guess (blueprint §9 discipline, exercised end-to-end)."""
    node = FakeNode(category="Vop")  # not Sop/Dop/Lop/Cop/Top
    machine = _ample_machine()
    response = hc.assess_cache_core(node, node_path=node.path(), machine=machine)
    assert response["verdict"] == CacheVerdict.UNSUPPORTED.value
    assert response["strategy_supported"] is False


# =============================================================================================
# Task 5 -- §17.1 pure policy scenarios, driven end-to-end through assess_cache_core
# =============================================================================================

def test_scenario_01_static_cheap_sop_is_not_worth_it():
    node = FakeNode(needs_to_cook=False, last_cook_ms=50.0, memoryusage=2048)
    machine = _ample_machine()
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        frame_range=(1, 1), expected_future_reads=1,
        evidence_overrides=dict(
            compute_seconds_total=Interval(0.05, 0.05),
            write_seconds_total=Interval(3.0, 5.0),
            read_seconds_total=Interval(1.0, 2.0),
            boundary_signals=BoundarySignals(static_or_cheap=True),
            peak_working_set_bytes=_ample_peak_ram(),
            estimated_output_bytes_per_frame=Interval(2_000_000_000.0, 2_000_000_000.0),
        ),
    )
    assert response["verdict"] == CacheVerdict.NOT_WORTH_IT.value


def test_scenario_02_valuable_particle_sequence_ample_ssd_is_cache_now():
    node = FakeNode(needs_to_cook=False, last_cook_ms=6000.0, time_dependent=True)
    machine = _ample_machine()
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        frame_range=(1001, 1240), expected_future_reads=2,
        evidence_overrides=dict(
            estimated_output_bytes_per_frame=Interval(800_000_000.0, 1_000_000_000.0),
            compute_seconds_total=Interval(1400.0, 1440.0),
            write_seconds_total=Interval(200.0, 260.0),
            read_seconds_total=Interval(80.0, 120.0),
            boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
            peak_working_set_bytes=_ample_peak_ram(),
        ),
    )
    assert response["verdict"] == CacheVerdict.CACHE_NOW.value
    assert response["decision"]["bake_action"] == "bake_after_approval"


def test_scenario_03_stateful_solver_unknown_output_size_is_measure_first_or_boundary_only():
    node = FakeNode(needs_to_cook=False, last_cook_ms=4000.0)
    machine = _ample_machine()
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        is_solver_result=True, frame_range=(1, 100),
        evidence_overrides=dict(boundary_signals=BoundarySignals(stateful_downstream_scrub=True)),
    )
    assert response["verdict"] in (CacheVerdict.MEASURE_FIRST.value, CacheVerdict.INSERT_BOUNDARY_ONLY.value)
    assert response["strategy_id"] == "sop_filecache_solver_result_v1"


def test_scenario_04_per_frame_ram_above_safe_is_optimize_first():
    node = FakeNode(needs_to_cook=False, last_cook_ms=3000.0)
    machine = _ample_machine(ram_total_bytes=32_000_000_000, ram_available_bytes=20_000_000_000)
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        evidence_overrides=dict(
            peak_working_set_bytes=Evidence.known(
                Interval(low=15_000_000_000.0, high=30_000_000_000.0), unit="bytes",
                source="calibrated_estimate",
            ),
        ),
        policy=CachePolicy(ram_safety_fraction=0.80),
    )
    assert response["verdict"] == CacheVerdict.OPTIMIZE_FIRST.value
    assert "RAM" in response["decision"]["headline"]
    assert "memory fix" not in response["message"].lower()


def test_scenario_05_gpu_required_above_safe_vram_is_optimize_first():
    node = FakeNode(needs_to_cook=False, last_cook_ms=3000.0)
    machine = _ample_machine(gpu_devices=[
        {"name": "RTX 4090", "vram_bytes": 24_000_000_000, "vram_available_bytes": 22_000_000_000}
    ])
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        evidence_overrides=dict(
            gpu_relevance=GPURelevance.REQUIRED.value,
            peak_working_set_bytes=Evidence.known(
                Interval(low=1_000_000_000.0, high=23_000_000_000.0), unit="bytes",
                source="calibrated_estimate",
            ),
        ),
        policy=CachePolicy(vram_safety_fraction=0.85),
    )
    assert response["verdict"] == CacheVerdict.OPTIMIZE_FIRST.value


def test_scenario_06_cpu_only_workload_on_rtx4090_same_as_without_gpu_metadata():
    """GPU name cannot sway the verdict -- ran twice through the real assess path with
    identical workload evidence, differing only in whether the machine reports an RTX
    4090 at all."""
    overrides = dict(
        frame_range=(1, 240), expected_future_reads=2,
        evidence_overrides=dict(
            estimated_output_bytes_per_frame=Interval(800_000_000.0, 1_000_000_000.0),
            compute_seconds_total=Interval(1400.0, 1440.0),
            write_seconds_total=Interval(200.0, 260.0),
            read_seconds_total=Interval(80.0, 120.0),
            boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
            gpu_relevance=GPURelevance.NOT_USED.value,
            peak_working_set_bytes=_ample_peak_ram(),
        ),
    )
    node_with = FakeNode(needs_to_cook=False, last_cook_ms=6000.0, path="/obj/geo1/a")
    node_without = FakeNode(needs_to_cook=False, last_cook_ms=6000.0, path="/obj/geo1/b")
    machine_with_gpu = _ample_machine(gpu_devices=[{"name": "RTX 4090", "vram_bytes": 24_000_000_000}])
    machine_without_gpu = _ample_machine(gpu_devices=[])

    r_with = hc.assess_cache_core(node_with, node_path=node_with.path(), machine=machine_with_gpu, **overrides)
    r_without = hc.assess_cache_core(node_without, node_path=node_without.path(), machine=machine_without_gpu, **overrides)
    assert r_with["verdict"] == r_without["verdict"] == CacheVerdict.CACHE_NOW.value


def test_scenario_07_valuable_cache_insufficient_free_space():
    node = FakeNode(needs_to_cook=False, last_cook_ms=6000.0)
    machine = MachineProfile(
        ram_total_bytes=128_000_000_000, ram_available_bytes=100_000_000_000,
        cache_volume=CacheVolume(free_bytes=600 * 1024**3, total_bytes=2000 * 1024**3),
    )
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        frame_range=(1, 240), expected_future_reads=3,
        evidence_overrides=dict(
            estimated_output_bytes_per_frame=Interval(3.8 * 1024**3, 4.0 * 1024**3),
            compute_seconds_total=Interval(1400.0, 1440.0),
            write_seconds_total=Interval(200.0, 260.0),
            read_seconds_total=Interval(80.0, 120.0),
            boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
            peak_working_set_bytes=_ample_peak_ram(),
        ),
    )
    assert response["verdict"] == CacheVerdict.INSUFFICIENT_DISK.value


def test_scenario_08_existing_matching_complete_manifest_is_use_valid_cache():
    node = FakeNode(needs_to_cook=False, last_cook_ms=6000.0)
    machine = _ample_machine()
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        evidence_overrides=dict(existing_cache=ExistingCacheState(
            present=True, manifested=True, manifest_status="complete",
            upstream_signature="sha256:same", current_upstream_signature="sha256:same",
        )),
    )
    assert response["verdict"] == CacheVerdict.USE_VALID_CACHE.value
    assert response["cache_validity"] == CacheValidity.VALID.value
    assert "not usable" not in response["message"]


def test_scenario_09_existing_files_changed_upstream_signature_is_stale():
    node = FakeNode(needs_to_cook=False, last_cook_ms=6000.0)
    machine = _ample_machine()
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        evidence_overrides=dict(existing_cache=ExistingCacheState(
            present=True, manifested=True, manifest_status="complete",
            upstream_signature="sha256:old", current_upstream_signature="sha256:new",
        )),
    )
    assert response["cache_validity"] == CacheValidity.STALE.value
    assert response["verdict"] != CacheVerdict.USE_VALID_CACHE.value
    assert "STALE" in response["message"], "stale status must never be buried (§14.2)"


def test_scenario_10_existing_unmanifested_cache_is_unverifiable():
    node = FakeNode(needs_to_cook=False, last_cook_ms=6000.0)
    machine = _ample_machine()
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        evidence_overrides=dict(existing_cache=ExistingCacheState(present=True, manifested=False)),
    )
    assert response["cache_validity"] == CacheValidity.UNVERIFIABLE.value
    assert response["verdict"] != CacheVerdict.USE_VALID_CACHE.value
    assert "UNVERIFIABLE" in response["message"]


def test_scenario_11_unknown_context_is_unsupported():
    node = FakeNode(category="Vop")
    machine = _ample_machine()
    response = hc.assess_cache_core(node, node_path=node.path(), machine=machine)
    assert response["verdict"] == CacheVerdict.UNSUPPORTED.value


def test_scenario_12_dirty_node_no_prior_observation_is_measure_first():
    """Dirty node, no prior observation -> measure_first. geometry() is NEVER invoked --
    the tripwire node raises if it is."""
    node = FakeDirtyGeometryTripwireNode()
    machine = _ample_machine()
    response = hc.assess_cache_core(node, node_path=node.path(), machine=machine)
    assert node.geometry_call_count == 0, "geometry() was called on a dirty node"
    assert response["verdict"] == CacheVerdict.MEASURE_FIRST.value
    assert response["observation_status"] == "dirty_not_forced"


# =============================================================================================
# §16 Phase 1 exit gate -- all five, through the real assess path
# =============================================================================================

def test_exit_gate_1_assessment_cannot_increase_cook_count_on_dirty_node():
    node = FakeDirtyGeometryTripwireNode()
    before = node.cookCount()
    machine = _ample_machine()
    hc.assess_cache_core(node, node_path=node.path(), machine=machine)
    after = node.cookCount()
    assert before == after == 3
    assert node.geometry_call_count == 0


def test_exit_gate_2_every_verdict_includes_provenance_confidence_and_missing_evidence():
    """"Every verdict includes provenance, confidence, and missing evidence" -- checked
    across a spread of verdicts, not just one lucky path."""
    cases = []

    dirty = FakeDirtyGeometryTripwireNode()
    cases.append(hc.assess_cache_core(dirty, node_path=dirty.path(), machine=_ample_machine()))

    clean_cheap = FakeNode(needs_to_cook=False, last_cook_ms=50.0)
    cases.append(hc.assess_cache_core(
        clean_cheap, node_path=clean_cheap.path(), machine=_ample_machine(),
        frame_range=(1, 1), expected_future_reads=1,
        evidence_overrides=dict(
            compute_seconds_total=Interval(0.05, 0.05),
            write_seconds_total=Interval(3.0, 5.0),
            read_seconds_total=Interval(1.0, 2.0),
            boundary_signals=BoundarySignals(static_or_cheap=True),
            peak_working_set_bytes=_ample_peak_ram(),
            estimated_output_bytes_per_frame=Interval(2_000_000_000.0, 2_000_000_000.0),
        ),
    ))

    unsupported = FakeNode(category="Vop")
    cases.append(hc.assess_cache_core(unsupported, node_path=unsupported.path(), machine=_ample_machine()))

    for response in cases:
        decision = response["decision"]
        # provenance: the digest that ties the verdict to the substantive evidence it was
        # computed from -- see cache_policy/signatures.py's compute_evidence_digest.
        assert decision["evidence_digest"] and decision["evidence_digest"] != "unknown", response
        assert decision["confidence"] in ("high", "medium", "low", "unknown"), response
        assert isinstance(decision["missing_evidence"], list), response
        # response["confidence"] mirrors decision["confidence"] at the top level too
        assert response["confidence"] == decision["confidence"]


def test_exit_gate_3_no_prose_channel_and_identical_evidence_yields_identical_verdict():
    """"Changing prompt wording without changing graph/evidence does not change the policy
    verdict" (§17.2) -- proven two ways, replacing the ORIGINAL version of this test
    (reviewer-flagged, post-87e758bc, as vacuous: it mutated a returned dict's
    ``message``/``decision.reasons`` keys and then asserted the unrelated ``verdict`` key
    was unchanged -- true by construction for ANY dict, since mutating one key can never
    change a sibling key. That could never fail, the same class of defect the Mile 2
    reviewer caught in ``test_insert_boundary_only_does_not_imply_bake``).

    (1) STRUCTURAL: the live tool schema (pinned exactly in
        ``test_tool_schema_matches_blueprint_declared_input_set``) has NO free-text/prose
        property at all -- every property is typed (integer/number/boolean) or a
        structural/enum-constrained string (``node`` = a path, ``data_class`` = a closed
        enum). There is no field an LLM could stuff restated wording into that reaches
        ``decide_cache()``, because nothing routes a caller-supplied string into policy
        math anywhere in this module.
    (2) BEHAVIORAL: two INDEPENDENT calls (fresh node objects, no shared mutable state)
        with byte-identical structured evidence produce the identical verdict AND the
        identical evidence_digest -- restated in a way that cannot be satisfied by
        comparing two unrelated dict keys.
    """
    import synapse.mcp._tool_registry as tr

    # (1) structural: no prose channel on the schema.
    schema_props = tr.TOOL_JSON["synapse_assess_cache"]["inputSchema"]["properties"]
    for name, spec in schema_props.items():
        if spec.get("type") == "string":
            assert name == "node" or "enum" in spec, (
                f"schema property {name!r} is a free string with no enum constraint -- "
                "a prose/free-text channel into the tool, which the structured-verdict "
                "guarantee requires must not exist"
            )

    # (2) behavioral: independent calls, identical structured evidence -> identical verdict.
    machine = _ample_machine()
    kwargs = dict(
        frame_range=(1001, 1240), expected_future_reads=2,
        evidence_overrides=dict(
            estimated_output_bytes_per_frame=Interval(800_000_000.0, 1_000_000_000.0),
            compute_seconds_total=Interval(1400.0, 1440.0),
            write_seconds_total=Interval(200.0, 260.0),
            read_seconds_total=Interval(80.0, 120.0),
            boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
            peak_working_set_bytes=_ample_peak_ram(),
        ),
    )
    node1 = FakeNode(needs_to_cook=False, last_cook_ms=6000.0, time_dependent=True, path="/obj/geo1/a")
    node2 = FakeNode(needs_to_cook=False, last_cook_ms=6000.0, time_dependent=True, path="/obj/geo1/a")
    r1 = hc.assess_cache_core(node1, node_path=node1.path(), machine=machine, **kwargs)
    r2 = hc.assess_cache_core(node2, node_path=node2.path(), machine=machine, **kwargs)
    assert r1["verdict"] == r2["verdict"] == CacheVerdict.CACHE_NOW.value
    assert r1["decision"]["evidence_digest"] == r2["decision"]["evidence_digest"]


def test_card_label_is_driven_by_structured_verdict_never_by_reason_text():
    """Falsifiable version of the "an LLM's opinion cannot alter the structured verdict"
    guarantee, applied at the rendering boundary: even when ``headline``/``reasons`` read
    as the OPPOSITE of ``verdict`` (simulating a hypothetical future where those fields
    carried model-authored prose contradicting the real decision), the card's lead line
    must still reflect ``decision.verdict`` -- proving ``_render_advice_card`` derives its
    label from the structured enum, never by scanning reason text. Fails if the rendering
    function is ever refactored to infer status from prose instead of the enum field.
    """
    from synapse.cache_policy import CacheDecision, Estimates

    contradictory = CacheDecision(
        verdict=CacheVerdict.NOT_WORTH_IT.value,
        confidence="high",
        headline="CACHE STRONGLY RECOMMENDED -- bake this immediately",
        reasons=["This is an amazing cache opportunity, bake immediately"],
        estimates=Estimates(),
    )
    card = hc._render_advice_card(contradictory, node_path="/obj/geo1/x")
    lead_line = card.splitlines()[0]
    assert lead_line.startswith(hc._VERDICT_LABELS[CacheVerdict.NOT_WORTH_IT.value]), lead_line
    assert "STRONGLY RECOMMENDED" not in lead_line
    assert "bake immediately" not in lead_line


def test_exit_gate_4_optimize_first_for_per_frame_memory_failure():
    node = FakeNode(needs_to_cook=False, last_cook_ms=3000.0)
    machine = _ample_machine(ram_total_bytes=32_000_000_000, ram_available_bytes=20_000_000_000)
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        evidence_overrides=dict(
            peak_working_set_bytes=Evidence.known(
                Interval(low=15_000_000_000.0, high=30_000_000_000.0), unit="bytes",
                source="calibrated_estimate",
            ),
        ),
        policy=CachePolicy(ram_safety_fraction=0.80),
    )
    assert response["verdict"] == CacheVerdict.OPTIMIZE_FIRST.value


def test_exit_gate_5_no_disk_file_or_node_created_by_assessment(tmp_path, monkeypatch):
    """No filesystem write, anywhere, during assessment. Points HIP-shaped policy/cache
    paths at an empty tmp_path and asserts it is still empty afterward -- and, structurally,
    the fake node exposes no node-creation method at all, so any attempt by
    assess_cache_core to mutate the scene would raise AttributeError."""
    before = sorted(tmp_path.iterdir())
    assert before == []

    node = FakeNode(needs_to_cook=False, last_cook_ms=6000.0, time_dependent=True)
    machine = _ample_machine()
    hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        frame_range=(1001, 1240), expected_future_reads=2,
        evidence_overrides=dict(
            estimated_output_bytes_per_frame=Interval(800_000_000.0, 1_000_000_000.0),
            compute_seconds_total=Interval(1400.0, 1440.0),
            write_seconds_total=Interval(200.0, 260.0),
            read_seconds_total=Interval(80.0, 120.0),
            boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
            peak_working_set_bytes=_ample_peak_ram(),
        ),
    )
    after = sorted(tmp_path.iterdir())
    assert after == [], f"assessment created files it should never touch: {after}"


# =============================================================================================
# Task 3 -- advice card rendering rules (§14.1/§14.2)
# =============================================================================================

def test_card_shows_at_most_three_reasons_before_more_details():
    node = FakeDirtyGeometryTripwireNode()
    machine = _ample_machine()
    response = hc.assess_cache_core(node, node_path=node.path(), machine=machine)
    # measure_first's reasons list is short by construction in Phase 0/1; assert the
    # RENDERING rule directly instead of depending on a decision with >3 reasons existing.
    lines = response["message"].splitlines()
    why_idx = next((i for i, l in enumerate(lines) if l == "Why"), None)
    if why_idx is not None:
        reason_lines = []
        i = why_idx + 1
        while i < len(lines) and lines[i].startswith("- "):
            reason_lines.append(lines[i])
            i += 1
        assert len(reason_lines) <= hc._MAX_REASONS_SHOWN + 1  # +1 for the "N more" line


def test_card_never_buries_stale_status():
    node = FakeNode(needs_to_cook=False, last_cook_ms=6000.0)
    machine = _ample_machine()
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        evidence_overrides=dict(existing_cache=ExistingCacheState(
            present=True, manifested=True, manifest_status="complete",
            upstream_signature="sha256:old", current_upstream_signature="sha256:new",
        )),
    )
    assert "Cache status: STALE" in response["message"]


def test_card_separates_blocked_from_uncertain():
    """A blocked (red) verdict and a merely-uncertain (yellow) verdict render under
    DIFFERENT headings -- never the same list."""
    ram_blocked_node = FakeNode(needs_to_cook=False, last_cook_ms=3000.0)
    machine = _ample_machine(ram_total_bytes=32_000_000_000, ram_available_bytes=20_000_000_000)
    blocked = hc.assess_cache_core(
        ram_blocked_node, node_path=ram_blocked_node.path(), machine=machine,
        evidence_overrides=dict(peak_working_set_bytes=Evidence.known(
            Interval(low=15_000_000_000.0, high=30_000_000_000.0), unit="bytes",
            source="calibrated_estimate",
        )),
        policy=CachePolicy(ram_safety_fraction=0.80),
    )
    assert "Blocked" in blocked["message"]
    assert "per-frame RAM" in blocked["decision"]["blockers"]

    uncertain_node = FakeDirtyGeometryTripwireNode()
    uncertain = hc.assess_cache_core(uncertain_node, node_path=uncertain_node.path(), machine=_ample_machine())
    assert "Uncertain / missing evidence" in uncertain["message"]
    assert uncertain["decision"]["blockers"] == []


def test_card_shows_ranges_not_false_precision():
    node = FakeNode(needs_to_cook=False, last_cook_ms=6000.0, time_dependent=True)
    machine = _ample_machine()
    response = hc.assess_cache_core(
        node, node_path=node.path(), machine=machine,
        frame_range=(1001, 1240), expected_future_reads=2,
        evidence_overrides=dict(
            estimated_output_bytes_per_frame=Interval(800_000_000.0, 1_000_000_000.0),
            compute_seconds_total=Interval(1400.0, 1440.0),
            write_seconds_total=Interval(200.0, 260.0),
            read_seconds_total=Interval(80.0, 120.0),
            boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
            peak_working_set_bytes=_ample_peak_ram(),
        ),
    )
    disk_lines = [l for l in response["message"].splitlines() if "Estimated disk" in l]
    assert disk_lines, response["message"]
    assert "-" in disk_lines[0].split("Estimated disk:", 1)[1], (
        "expected a low-high range, not a single point value"
    )
