"""U.1 utility-flywheel pins — network-wiring truth.

Pins the three SCAFFOLD deliverables of harness/notes/spec-U1-wiring-flywheel.md:

  1. the packaged connectivity catalog is deterministic + byte-identical to the
     probe artifact (a drifted/hand-edited catalog fails loud),
  2. wire_by_label resolves labels from the catalog and FAILS LOUD on anything
     else (index fallback only behind the explicit allow_index gate),
  3. GraphValidator P3e REJECTS the three golden miswires (the exact bug class
     fixed on the release train) while the corrected forms pass.

Pure Python — no hou, no Houdini. The catalog under test is the committed
packaged copy (python/synapse/cognitive/tools/data/connectivity_21.json),
probe-generated on live 21.0.671 by host/introspect_connectivity.py.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from conftest import HOUDINI_BUILD
from synapse.cognitive.graph_proposal import (
    GraphProposal,
    NodeKind,
    ProposedEdge,
    ProposedNode,
    ValidationStatus,
)
from synapse.cognitive.graph_validator import GraphValidator
from synapse.core.wiring import (
    WiringError,
    load_connectivity_catalog,
    resolve_catalog_entry,
    resolve_input_index,
    wire_by_label,
)

_REPO = Path(__file__).resolve().parents[1]
PKG_CATALOG = _REPO / "python/synapse/cognitive/tools/data/connectivity_21.json"
HARNESS_CATALOG = _REPO / "harness/notes/verified_connectivity_21.0.671.json"


# ---------------------------------------------------------------------------
# 1. Catalog determinism pin
# ---------------------------------------------------------------------------

class TestCatalogDeterminism:
    def test_packaged_catalog_loads_and_verifies(self):
        cat = load_connectivity_catalog()
        assert cat["schema"] == "verified_connectivity/v2"
        assert cat["houdini_version"] == HOUDINI_BUILD

    def test_blake2b_recomputes_over_sorted_entries(self):
        # The determinism contract: the stamp is a pure function of the sorted
        # entries — any drift (hand edit, non-deterministic probe) fails here.
        raw = json.loads(PKG_CATALOG.read_text(encoding="utf-8"))
        digest = hashlib.blake2b(
            json.dumps(raw["entries"], sort_keys=True,
                       ensure_ascii=False).encode("utf-8"),
            digest_size=16,
        ).hexdigest()
        assert digest == raw["blake2b"]

    def test_packaged_copy_byte_identical_to_probe_artifact(self):
        assert PKG_CATALOG.read_bytes() == HARNESS_CATALOG.read_bytes(), (
            "packaged connectivity_21.json drifted from the harness probe "
            "artifact — re-run host/introspect_connectivity.py and re-copy"
        )

    def test_v1_payload_preserved_with_provenance(self):
        # EXPLORE must extend v1, not discard it: the dir()-membership facts and
        # the phantom list survive the v2 fold, provenance-marked.
        raw = json.loads(PKG_CATALOG.read_text(encoding="utf-8"))
        v1 = raw["v1_preserved"]
        assert "NOT re-derived" in v1["_provenance"]
        assert v1["symbols_present"]["hou.Node.inputLabels"] is True
        assert "hou.NodeType.inputLabels" in v1["symbols_PHANTOM_do_not_use"]

    def test_regression_seed_labels_are_probe_truth(self):
        # The two known-true seeds this whole cycle grew from.
        cat = load_connectivity_catalog()
        vs = cat["entries"]["Sop/vellumsolver"]
        assert vs["input_labels"] == [
            "Vellum Geometry", "Constraint Geometry", "Collision Geometry"]
        rbd = cat["entries"]["Sop/rbdbulletsolver"]
        assert rbd["input_labels"][0] == "Geometry"
        assert rbd["input_labels"][1] == "Constraint Geometry"


# ---------------------------------------------------------------------------
# 2. wire_by_label unit matrix
# ---------------------------------------------------------------------------

class _FakeCategory:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _FakeType:
    def __init__(self, name, category):
        self._name, self._category = name, _FakeCategory(category)

    def name(self):
        return self._name

    def category(self):
        return self._category


class _FakeNode:
    def __init__(self, type_name, category="Sop"):
        self._type = _FakeType(type_name, category)
        self.wired = []

    def type(self):
        return self._type

    def setInput(self, index, source, source_output=0):
        self.wired.append((index, source, source_output))


class TestWireByLabel:
    def test_known_label_resolves_to_catalog_index(self):
        solver, cloth = _FakeNode("vellumsolver"), object()
        idx = wire_by_label(solver, "Constraint Geometry", cloth, source_output=1)
        assert idx == 1
        assert solver.wired == [(1, cloth, 1)]

    def test_case_variance_still_resolves(self):
        solver, src = _FakeNode("vellumsolver"), object()
        assert wire_by_label(solver, "collision geometry", src) == 2
        assert wire_by_label(solver, "  VELLUM GEOMETRY ", src) == 0

    def test_unknown_label_fails_loud(self):
        solver = _FakeNode("vellumsolver")
        with pytest.raises(WiringError, match="no input labeled"):
            wire_by_label(solver, "Constraint Geoemtry", object())
        assert solver.wired == []            # nothing was wired on the failure

    def test_unknown_type_fails_loud(self):
        with pytest.raises(WiringError, match="not in the connectivity catalog"):
            wire_by_label(_FakeNode("totally_phantom_solver"), "Geometry", object())

    def test_index_fallback_requires_explicit_allow_index(self):
        node = _FakeNode("totally_phantom_solver")
        # index alone is NOT an escape hatch...
        with pytest.raises(WiringError):
            wire_by_label(node, "Geometry", object(), index=1)
        # ...allow_index without an index isn't either...
        with pytest.raises(WiringError):
            wire_by_label(node, "Geometry", object(), allow_index=True)
        # ...only the explicit pair wires.
        src = object()
        assert wire_by_label(node, "Geometry", src, index=1, allow_index=True) == 1
        assert node.wired == [(1, src, 0)]

    def test_rbdbulletsolver_constraint_is_input_1(self):
        # The second regression seed, end to end through the public API.
        solver, props = _FakeNode("rbdbulletsolver"), object()
        assert wire_by_label(solver, "Constraint Geometry", props) == 1

    def test_resolve_helpers_handle_versioned_and_bare_names(self):
        cat = load_connectivity_catalog()
        # exact spelling wins outright ('Lop/light' is a real plain key)...
        entry = resolve_catalog_entry(cat, "Lop", "light")
        assert entry is not None and entry["type_name"] == "light"
        # ...and a versioned spelling resolves its own exact entry.
        entry = resolve_catalog_entry(cat, "Lop", "light::2.0")
        assert entry is not None and entry["type_name"] == "light::2.0"
        with pytest.raises(WiringError):
            resolve_input_index(cat, "Sop", "vellumsolver", "Nope")


# ---------------------------------------------------------------------------
# 3. Golden miswire fixtures through GraphValidator P3e
# ---------------------------------------------------------------------------

class _AllExist:
    def node_type_exists(self, node_type, category):
        return True

    def parameter_exists(self, node_type, category, parm):
        return True


class _MockConn:
    """Permissive IConnectivityOracle: generous arity/outputs so the ORACLE
    phases pass and any rejection provably comes from the catalog (P3e)."""

    def __init__(self, existing=None):
        self._existing = existing or {}

    def input_arity(self, node_type, category):
        return (0, 9999)

    def input_labels(self, node_type, category):
        return []

    def output_count(self, node_type, category):
        return 9999

    def is_typed_category(self, category):
        return False

    def types_compatible(self, *a):
        return True

    def input_is_occupied(self, scene_path, input_index):
        return False

    def resolve_node_type(self, scene_path):
        return self._existing[scene_path]


def _proposal(nodes, edges):
    return GraphProposal(
        proposal_id="u1-golden",
        network_type="SOP",
        parent_path="/obj/geo1",
        nodes=nodes,
        edges=edges,
        natural_language_intent="U.1 golden miswire fixture",
        model_id="fixture",
        houdini_version_stamp=HOUDINI_BUILD,
    )


def _validate(p):
    conn = _MockConn(existing={"/obj/geo1": ("geo", "Object")})
    return GraphValidator(_AllExist(), conn).validate(p)


_VELLUM_NODES = [
    ProposedNode("cloth", NodeKind.NEW, "Sop", node_type="vellumconstraints",
                 friendly_name="vellum_cloth"),
    ProposedNode("solver", NodeKind.NEW, "Sop", node_type="vellumsolver",
                 friendly_name="vellum_solver"),
    ProposedNode("collider", NodeKind.NEW, "Sop", node_type="null",
                 friendly_name="collision_geo"),
]

_RBD_NODES = [
    ProposedNode("asm", NodeKind.NEW, "Sop", node_type="assemble",
                 friendly_name="assemble1"),
    ProposedNode("props", NodeKind.NEW, "Sop", node_type="rbdconstraintproperties",
                 friendly_name="glue_props"),
    ProposedNode("solver", NodeKind.NEW, "Sop", node_type="rbdbulletsolver",
                 friendly_name="rbd_solver"),
]


class TestGoldenMiswires:
    def test_golden_1_vellum_constraint_collision_swap_rejected(self):
        # THE historical miswire: constraints wired to input 2, collision to 1.
        p = _proposal(_VELLUM_NODES, [
            ProposedEdge("cloth", 0, "solver", 0, target_input_label="Vellum Geometry"),
            ProposedEdge("cloth", 1, "solver", 2, target_input_label="Constraint Geometry"),
            ProposedEdge("collider", 0, "solver", 1, target_input_label="Collision Geometry"),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.INVALID
        mismatches = [i for i in report.errors if "label-mismatched slot" in i.message]
        assert len(mismatches) == 2
        assert all(HOUDINI_BUILD in i.message for i in report.errors)

    def test_golden_1_corrected_form_passes(self):
        p = _proposal(_VELLUM_NODES, [
            ProposedEdge("cloth", 0, "solver", 0, target_input_label="Vellum Geometry"),
            ProposedEdge("cloth", 1, "solver", 1, target_input_label="Constraint Geometry"),
            ProposedEdge("collider", 0, "solver", 2, target_input_label="Collision Geometry"),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]

    def test_golden_2_rbd_constraint_to_input_2_rejected(self):
        p = _proposal(_RBD_NODES, [
            ProposedEdge("asm", 0, "solver", 0, target_input_label="Geometry"),
            ProposedEdge("props", 0, "solver", 2, target_input_label="Constraint Geometry"),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.INVALID
        assert any("label-mismatched slot" in i.message
                   and "index 1" in i.message for i in report.errors)

    def test_golden_2_corrected_form_passes(self):
        p = _proposal(_RBD_NODES, [
            ProposedEdge("asm", 0, "solver", 0, target_input_label="Geometry"),
            ProposedEdge("props", 0, "solver", 1, target_input_label="Constraint Geometry"),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]

    def test_golden_3_out_of_range_index_rejected_by_catalog_not_oracle(self):
        # The oracle mock allows 9999 inputs — the rejection can ONLY come from
        # the probe-verified catalog arity (vellumsolver max_inputs=3).
        p = _proposal(_VELLUM_NODES, [
            ProposedEdge("cloth", 0, "solver", 5),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.INVALID
        assert any("probe-verified arity" in i.message for i in report.errors)

    def test_golden_3_corrected_form_passes(self):
        p = _proposal(_VELLUM_NODES, [
            ProposedEdge("cloth", 0, "solver", 0),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]

    def test_unknown_label_rejected(self):
        p = _proposal(_VELLUM_NODES, [
            ProposedEdge("cloth", 0, "solver", 0, target_input_label="Constraint Geoemtry"),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.INVALID
        assert any("no such input" in i.message for i in report.errors)

    def test_catalog_check_is_additive_unknown_types_skip(self):
        # A type the catalog does not carry: P3e stays silent (no false reject);
        # the oracle-backed phases still govern.
        nodes = [
            ProposedNode("a", NodeKind.NEW, "Sop", node_type="not_in_catalog_a",
                         friendly_name="a1"),
            ProposedNode("b", NodeKind.NEW, "Sop", node_type="not_in_catalog_b",
                         friendly_name="b1"),
        ]
        p = _proposal(nodes, [ProposedEdge("a", 0, "b", 7)])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID


# ---------------------------------------------------------------------------
# 4. Planner adoption pin — the live sites emit wire_by_label, not raw indices
# ---------------------------------------------------------------------------

class TestPlannerAdoption:
    def setup_method(self):
        from synapse.routing.planner import WorkflowPlanner
        self.planner = WorkflowPlanner()

    def test_cloth_core_step_wires_by_label(self):
        plan = self.planner.plan("set up cloth sim")
        code = plan.steps[0].payload["code"]
        assert "wire_by_label(solver, 'Vellum Geometry', cloth, source_output=0)" in code
        assert "wire_by_label(solver, 'Constraint Geometry', cloth, source_output=1)" in code
        assert "solver.setInput(" not in code

    def test_cloth_collision_step_wires_by_label(self):
        plan = self.planner.plan("set up cloth simulation with collision")
        collision_code = plan.steps[1].payload["code"]
        assert "wire_by_label(solver, 'Collision Geometry', collider)" in collision_code
        assert "solver.setInput(" not in collision_code

    def test_destruction_core_step_wires_by_label(self):
        plan = self.planner.plan("setup destruction pipeline")
        code = plan.steps[0].payload["code"]
        assert "wire_by_label(solver, 'Geometry', asm)" in code
        assert "wire_by_label(solver, 'Constraint Geometry', props)" in code
        assert "solver.setInput(" not in code
