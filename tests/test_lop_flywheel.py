"""U.5 utility-flywheel pins — LOP/Solaris knowledge truth.

Pins the SCAFFOLD deliverables of harness/notes/spec-U5-lop-solaris-flywheel.md:

  1. the packaged LOP knowledge catalog is deterministic + byte-identical to the
     harness artifact (a drifted/hand-edited catalog fails loud),
  2. load_lop_catalog verifies blake2b over `content` and FAILS LOUD otherwise,
  3. GraphValidator's additive LOP phase, with a PERMISSIVE oracle (so any verdict
     provably comes from the corpus catalog): a `grid`/`plane` LOP is a HARD ERROR
     (phantom type), while a missing material source upstream of assignmaterial is
     an ADVISORY (a common-pattern heuristic — materials also arrive via
     reference/sublayer or a pre-composed stage, so it must not hard-reject).

Pure Python — no hou, no Houdini. The catalog under test is the committed packaged
copy, corpus-authored + probe-cross-checked by scripts/mine_lop_knowledge.py.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from synapse.cognitive.graph_proposal import (
    GraphProposal,
    NodeKind,
    ProposedEdge,
    ProposedNode,
    ValidationStatus,
)
from synapse.cognitive.graph_validator import GraphValidator
from synapse.core.lop_knowledge import (
    LopKnowledgeError,
    known_absent,
    load_lop_catalog,
    ordering_rules,
)

_REPO = Path(__file__).resolve().parents[1]
PKG = _REPO / "python/synapse/cognitive/tools/data/lop_solaris_knowledge_21.json"
HARNESS = _REPO / "harness/notes/verified_lop_solaris_knowledge_21.0.671.json"


# ---------------------------------------------------------------------------
# 1. Catalog determinism + integrity
# ---------------------------------------------------------------------------

class TestCatalogDeterminism:
    def test_packaged_catalog_loads_and_verifies(self):
        cat = load_lop_catalog()
        assert cat["schema"] == "lop_solaris_knowledge/v1"
        assert "assignmaterial" in cat["content"]["entries"]

    def test_blake2b_recomputes_over_content(self):
        raw = json.loads(PKG.read_text(encoding="utf-8"))
        digest = hashlib.blake2b(
            json.dumps(raw["content"], sort_keys=True,
                       ensure_ascii=False).encode("utf-8"),
            digest_size=16,
        ).hexdigest()
        assert digest == raw["blake2b"]

    def test_packaged_byte_identical_to_harness_artifact(self):
        assert PKG.read_bytes() == HARNESS.read_bytes(), (
            "packaged lop_solaris_knowledge_21.json drifted from the harness probe "
            "artifact — re-run scripts/mine_lop_knowledge.py")

    def test_hand_edit_fails_loud(self, tmp_path):
        raw = json.loads(PKG.read_text(encoding="utf-8"))
        raw["content"]["entries"]["assignmaterial"]["role"] = "TAMPERED"
        p = tmp_path / "tampered.json"
        p.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(LopKnowledgeError, match="checksum mismatch"):
            load_lop_catalog(p, strict=True)

    def test_ordering_and_known_absent_present(self):
        cat = load_lop_catalog()
        assert any(r["on_type"] == "assignmaterial" for r in ordering_rules(cat))
        assert "grid" in known_absent(cat)


# ---------------------------------------------------------------------------
# 2. Behavior-change golden through GraphValidator's LOP phase
#    Permissive oracles -> any rejection provably comes from the LOP catalog.
# ---------------------------------------------------------------------------

class _AllExist:
    def node_type_exists(self, node_type, category):
        return True

    def parameter_exists(self, node_type, category, parm):
        return True


class _MockConn:
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
        return ("geo", "Object")


def _node(nid, ntype, name):
    return ProposedNode(nid, NodeKind.NEW, "Lop", node_type=ntype, friendly_name=name)


def _proposal(nodes, edges):
    return GraphProposal(
        proposal_id="u5-golden",
        network_type="SOLARIS",
        parent_path="/stage",
        nodes=nodes,
        edges=edges,
        natural_language_intent="U.5 golden LOP fixture",
        model_id="fixture",
        houdini_version_stamp="21.0.671",
    )


def _validate(p):
    return GraphValidator(_AllExist(), _MockConn()).validate(p)


_GEO = _node("geo", "sphere", "geo_sphere")
_MATLIB = _node("matlib", "materiallibrary", "matlib")
_ASSIGN = _node("assign", "assignmaterial", "assign_material")
_REF = _node("ref", "reference", "materials_usd")
_SUB = _node("sub", "sublayer", "base_layer")


def _ordering_advisories(report):
    return [i for i in report.advisories if "material source upstream" in i.message]


def _lop_errors(report):
    return [i for i in report.errors if "LOP knowledge" in i.message]


class TestLopOrdering:
    # --- (b) ordering is an ADVISORY, never a hard error ------------------------
    def test_missing_material_source_is_advisory_not_error(self):
        # geo -> assign, no material source anywhere: an ADVISORY (guidance), not a
        # hard reject — the graph is not provably wrong.
        p = _proposal([_GEO, _ASSIGN], [ProposedEdge("geo", 0, "assign", 0)])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]
        assert not _lop_errors(report), [e.message for e in report.errors]
        adv = _ordering_advisories(report)
        assert adv and "materiallibrary" in adv[0].message, (
            [a.message for a in report.advisories])

    def test_materiallibrary_upstream_satisfies(self):
        # geo -> matlib -> assign: satisfied by materiallibrary; no advisory.
        p = _proposal([_GEO, _MATLIB, _ASSIGN], [
            ProposedEdge("geo", 0, "matlib", 0),
            ProposedEdge("matlib", 0, "assign", 0),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]
        assert not _ordering_advisories(report), [a.message for a in report.advisories]

    def test_reference_upstream_satisfies(self):
        # reference(materials.usd) -> assign: a composition arc authors the material
        # prims (no materiallibrary LOP needed). satisfied_by => no advisory.
        # This is the high-severity false-positive the review caught.
        p = _proposal([_REF, _ASSIGN], [ProposedEdge("ref", 0, "assign", 0)])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]
        assert not _ordering_advisories(report), [a.message for a in report.advisories]

    def test_sublayer_upstream_satisfies(self):
        p = _proposal([_SUB, _ASSIGN], [ProposedEdge("sub", 0, "assign", 0)])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]
        assert not _ordering_advisories(report), [a.message for a in report.advisories]

    def test_multi_hop_all_new_without_source_advises(self):
        # geo -> edit -> assign, all NEW, no material source: advisory (VALID), the
        # deeper walk still detects the missing source on a fully-authored chain.
        edit = _node("edit", "edit", "edit1")
        p = _proposal([_GEO, edit, _ASSIGN], [
            ProposedEdge("geo", 0, "edit", 0),
            ProposedEdge("edit", 0, "assign", 0),
        ])
        report = _validate(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]
        assert _ordering_advisories(report), [a.message for a in report.advisories]

    def test_existing_upstream_under_advises(self):
        # MERGE into a live stage: assign sits downstream of an EXISTING node — a
        # boundary into the pre-composed stage whose content we don't model. We
        # under-advise (stay silent) rather than emit a spurious advisory.
        existing = ProposedNode("stage", NodeKind.EXISTING, "Lop",
                                node_type="reference", scene_path="/stage/ref1")
        p = _proposal([existing, _ASSIGN], [ProposedEdge("stage", 0, "assign", 0)])
        report = _validate(p)
        assert not _ordering_advisories(report), [a.message for a in report.advisories]

    # --- (a) known-absent is a HARD ERROR --------------------------------------
    def test_grid_lop_hard_error_with_remediation(self):
        p = _proposal([_node("g", "grid", "ground")], [])
        report = _validate(p)
        assert report.status == ValidationStatus.INVALID
        assert any("not a real LOP" in i.message and "cube with sy=0.01" in i.message
                   for i in report.errors), [e.message for e in report.errors]

    def test_capitalized_grid_still_flagged(self):
        # 'Grid' (capitalized) must still get the corpus remediation — the
        # known-absent match is case-insensitive.
        p = _proposal([_node("g", "Grid", "ground")], [])
        report = _validate(p)
        assert any("not a real LOP" in i.message and "cube with sy=0.01" in i.message
                   for i in report.errors), [e.message for e in report.errors]

    def test_existing_grid_node_not_flagged(self):
        # An EXISTING node's node_type is advisory-only per the contract and a live
        # node cannot be an absent type — part (a) must skip it.
        g = ProposedNode("g", NodeKind.EXISTING, "Lop",
                         node_type="grid", scene_path="/stage/g")
        p = _proposal([g], [])
        report = _validate(p)
        assert not any("not a real LOP" in i.message for i in report.errors), (
            [e.message for e in report.errors])

    # --- robustness + scope -----------------------------------------------------
    def test_malformed_injected_catalog_degrades_to_skip(self):
        # The load path is checksum-gated, but the lop_catalog= injection point is
        # not — a malformed injected catalog of ANY shape must skip, never raise.
        # A proposal exercising BOTH halves (a grid node + assign with a bare
        # upstream) so part (a) and part (b) both run against each bad shape.
        prop = _proposal([_node("g", "grid", "x"), _GEO, _ASSIGN],
                         [ProposedEdge("geo", 0, "assign", 0)])
        bad_catalogs = (
            {"content": None},                                        # content None
            {"content": ["x"]},                                       # content not a dict
            {"content": {"known_absent": ["grid"], "ordering_rules": []}},   # known_absent a list
            {"content": {"known_absent": "grid", "ordering_rules": []}},     # known_absent a str
            {"content": {"known_absent": {"grid": "oops"}, "ordering_rules": []}},  # entry not a dict
            {"content": {"known_absent": {5: {"remediation": "x"}}, "ordering_rules": []}},  # non-str key
            {"content": {"known_absent": {}, "ordering_rules": 5}},          # ordering_rules an int
            {"content": {"known_absent": {}, "ordering_rules": [
                {"relation": "upstream", "on_type": "assignmaterial",
                 "satisfied_by": "reference"}]}},                     # satisfied_by a str
        )
        for bad in bad_catalogs:
            v = GraphValidator(_AllExist(), _MockConn(), lop_catalog=bad)
            report = v.validate(prop)                # must not raise
            assert not _lop_errors(report), bad      # no spurious LOP hard-error

    def test_non_solaris_graph_untouched(self):
        # A SOP graph with an 'assignmaterial'-named node must NOT trip the LOP rule.
        sop = ProposedNode("a", NodeKind.NEW, "Sop", node_type="assignmaterial",
                            friendly_name="x")
        p = GraphProposal(
            proposal_id="x", network_type="SOP", parent_path="/obj/geo1",
            nodes=[sop], edges=[], natural_language_intent="", model_id="f")
        report = GraphValidator(_AllExist(), _MockConn()).validate(p)
        assert not _ordering_advisories(report)
        assert not _lop_errors(report)
