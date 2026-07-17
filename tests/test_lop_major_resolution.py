"""C-U5 fold pins — major-aware LOP/Solaris CONTEXT catalog resolution.

The twin of the U.1-H22 wiring fold (tests/test_wiring_major_resolution.py),
for CONTEXT truth: ``synapse.core.lop_knowledge`` resolves the packaged
knowledge catalog PER RUNNING MAJOR (the ``connectivity_<major>.json``
selection pattern):

  * ``hou`` importable -> ``lop_solaris_knowledge_<major>.json``
  * ``hou`` absent     -> the H21 default (the test-world truth, unchanged)
  * missing major file -> ``LopKnowledgeError`` naming the expected file —
                          NEVER a silent cross-major fallback (wrong-major
                          CONTEXT truth is the stale-advice class C-U5 kills)
  * explicit ``path``  -> honored verbatim, untouched by resolution

Plus the 22.0.368 catalog content pins (probe truth, authored by
scripts/author_lop_knowledge_22.py from the banked hython probe): the renamed
instancer family is IN, the per-shape lights are OUT (known_absent, superseded
by the consolidated light LOP), plane is REAL now (was H21 known_absent), and
GraphValidator's additive LOP phase advises from the _22 catalog on an H22
host.

Pure Python — no Houdini. ``hou`` presence is simulated through scoped
``monkeypatch.setitem(sys.modules, ...)`` (``None`` forces ``import hou`` to
raise, deterministically simulating absence even when another test module
leaked a resident fake) — the ratified U.1-H22 pattern, never a module-level
plant.
"""
from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from synapse.cognitive.graph_proposal import (
    GraphProposal,
    NodeKind,
    ProposedEdge,
    ProposedNode,
    ValidationStatus,
)
from synapse.cognitive.graph_validator import GraphValidator
from synapse.core import lop_knowledge
from synapse.core.lop_knowledge import (
    LopKnowledgeError,
    known_absent,
    load_lop_catalog,
    ordering_rules,
)

_REPO = Path(__file__).resolve().parents[1]
_DATA = _REPO / "python/synapse/cognitive/tools/data"
PKG_21 = _DATA / "lop_solaris_knowledge_21.json"
PKG_22 = _DATA / "lop_solaris_knowledge_22.json"
HARNESS_22 = _REPO / "harness/notes/verified_lop_solaris_knowledge_22.0.368.json"

_H22_INSTANCERS = (
    "copytopoints", "extractinstances", "mergepointinstancers",
    "modifypointinstances", "paintinstances", "pointinstancer",
    "retimeinstances", "scatterinstances", "splitpointinstancers",
)
_H22_DEAD_LIGHTS = ("cylinderlight", "disklight", "rectlight", "spherelight")


def _fake_hou(major):
    mod = types.ModuleType("hou")
    mod.applicationVersion = lambda: (major, 0, 368)
    return mod


# ---------------------------------------------------------------------------
# 1. Resolver rules (a)-(d) — the wiring.py mirror
# ---------------------------------------------------------------------------

class TestMajorResolution:
    def test_no_hou_defaults_to_h21(self, monkeypatch):
        # sys.modules["hou"] = None makes `import hou` raise ImportError —
        # deterministic absence, immune to resident fakes from other modules.
        monkeypatch.setitem(sys.modules, "hou", None)
        assert lop_knowledge._pkg_catalog_path() == PKG_21
        cat = load_lop_catalog()
        assert cat["houdini_version"] == "21.0.671"

    def test_h22_major_resolves_h22_catalog(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(22))
        assert lop_knowledge._pkg_catalog_path() == PKG_22
        cat = load_lop_catalog()
        assert cat["houdini_version"] == "22.0.368"

    def test_missing_major_fails_loud_never_cross_major(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(99))
        with pytest.raises(LopKnowledgeError, match=r"lop_solaris_knowledge_99\.json"):
            load_lop_catalog(strict=True)
        # Validator posture: honest skip (None) — still no cross-major fallback.
        assert load_lop_catalog(strict=False) is None

    def test_non_int_major_reads_unknown_default_21(self, monkeypatch):
        # The residency-leak shape: a MagicMock hou whose applicationVersion()
        # yields a MagicMock, not an int. Must read UNKNOWN -> H21 default,
        # never a garbage-named catalog.
        monkeypatch.setitem(sys.modules, "hou", MagicMock())
        assert lop_knowledge._pkg_catalog_path() == PKG_21

    def test_explicit_path_honored_over_resolution(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(22))
        cat = load_lop_catalog(PKG_21)
        assert cat["houdini_version"] == "21.0.671"


# ---------------------------------------------------------------------------
# 2. H22 catalog determinism + content pins (probe truth, never hand-edited)
# ---------------------------------------------------------------------------

class TestH22CatalogTruth:
    def _cat(self):
        return load_lop_catalog(PKG_22)

    def test_packaged_copy_byte_identical_to_harness_artifact(self):
        assert PKG_22.read_bytes() == HARNESS_22.read_bytes(), (
            "packaged lop_solaris_knowledge_22.json drifted from the harness "
            "artifact — re-run scripts/author_lop_knowledge_22.py"
        )

    def test_blake2b_recomputes_over_sorted_content(self):
        raw = json.loads(PKG_22.read_text(encoding="utf-8"))
        digest = hashlib.blake2b(
            json.dumps(raw["content"], sort_keys=True,
                       ensure_ascii=False).encode("utf-8"),
            digest_size=16,
        ).hexdigest()
        assert digest == raw["blake2b"]
        assert raw["schema"] == "lop_solaris_knowledge/v1"
        assert raw["houdini_version"] == "22.0.368"

    def test_h22_instancer_family_present(self):
        # The W.3 rename class: ALL nine instancers resolve on 22.0.368 as
        # unversioned Lop types (probe truth) and are catalog entries.
        entries = self._cat()["content"]["entries"]
        for name in _H22_INSTANCERS:
            assert name in entries, f"instancer '{name}' missing from the _22 catalog"
        assert entries["pointinstancer"]["usd_type"] == "PointInstancer"

    def test_per_shape_lights_dropped_and_known_absent(self):
        # USDLux-punycode class: creation FAILS live for all four — they are
        # OUT of entries and IN known_absent, remediation naming the
        # consolidated light LOP.
        cat = self._cat()
        entries = cat["content"]["entries"]
        absent = known_absent(cat)
        for name in _H22_DEAD_LIGHTS:
            assert name not in entries, f"stale per-shape light '{name}' still an entry"
            assert name in absent, f"'{name}' missing from known_absent"
            assert "light" in absent[name]["remediation"]
        # The survivors stay distinct types (probe: domelight::3.0 / distantlight::2.0).
        assert "domelight" in entries and "distantlight" in entries
        assert "light" in entries
        assert "lighttype" in entries["light"]["key_parms"]

    def test_plane_is_real_now_grid_still_absent(self):
        # The exact stale-advice kill: H21 marked plane known_absent; on
        # 22.0.368 the probe proves it is a real LOP type.
        cat = self._cat()
        entries = cat["content"]["entries"]
        absent = known_absent(cat)
        assert "plane" in entries and "plane" not in absent
        assert "grid" not in entries and "grid" in absent

    def test_instancer_opalias_flagged_known_absent(self):
        # DECISION-POINT pin (W.3 "canonical spelling, never the opalias"):
        # 'instancer' is gone from the type table but createNode() silently
        # aliases to copytopoints — known_absent remediation states both facts.
        absent = known_absent(self._cat())
        assert "instancer" in absent
        assert "copytopoints" in absent["instancer"]["remediation"]

    def test_render_successor_and_deprecation(self):
        entries = self._cat()["content"]["entries"]
        assert "karmarendersettings" in entries
        assert any("karmarendersettings" in g
                   for g in entries["karmarenderproperties"]["gotchas"])

    def test_ordering_rule_carried_and_grounded(self):
        cat = self._cat()
        rules = ordering_rules(cat)
        assert any(r["on_type"] == "assignmaterial" for r in rules)
        entries = cat["content"]["entries"]
        for name in ("assignmaterial", "materiallibrary", "reference", "sublayer"):
            assert name in entries

    def test_probe_confirmed_types_in_connectivity_lop_set(self):
        # Advisory cross-check: every probe_confirmed name is in the SAME-major
        # connectivity catalog's Lop set (never the H21 one).
        conn = json.loads((_DATA / "connectivity_22.json").read_text(encoding="utf-8"))
        lop = {e.get("type_name", "").split("::")[0]
               for e in conn.get("entries", {}).values()
               if e.get("category") == "Lop"}
        confirmed = self._cat()["probe_confirmed_types"]
        assert confirmed, "no probe-confirmed types"
        for name in confirmed:
            assert name in lop, f"'{name}' claimed probe-confirmed but not in connectivity_22"


# ---------------------------------------------------------------------------
# 3. GraphValidator's LOP phase against the _22 catalog
#    Permissive oracles -> any verdict provably comes from the knowledge catalog.
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
        proposal_id="c-u5-golden",
        network_type="SOLARIS",
        parent_path="/stage",
        nodes=nodes,
        edges=edges,
        natural_language_intent="C-U5 golden H22 LOP fixture",
        model_id="fixture",
        houdini_version_stamp="22.0.368",
    )


def _validate_22(p):
    return GraphValidator(_AllExist(), _MockConn(),
                          lop_catalog=load_lop_catalog(PKG_22)).validate(p)


def _lop_errors(report):
    return [i for i in report.errors if "LOP knowledge" in i.message]


def _ordering_advisories(report):
    return [i for i in report.advisories if "material source upstream" in i.message]


class TestValidatorAgainstH22Catalog:
    def test_spherelight_hard_error_names_successor(self):
        report = _validate_22(_proposal([_node("l", "spherelight", "key")], []))
        assert report.status == ValidationStatus.INVALID
        assert any("not a real LOP" in i.message and "light" in i.message
                   for i in report.errors), [e.message for e in report.errors]

    def test_instancer_hard_error_names_copytopoints(self):
        report = _validate_22(_proposal([_node("i", "instancer", "scatter")], []))
        assert report.status == ValidationStatus.INVALID
        assert any("copytopoints" in i.message for i in report.errors), (
            [e.message for e in report.errors])

    def test_plane_no_longer_flagged(self):
        # Pre-fold, the H21 catalog hard-errored plane on an H22 host — the
        # stale-advice class this fold kills.
        report = _validate_22(_proposal([_node("p", "plane", "ground")], []))
        assert not _lop_errors(report), [e.message for e in report.errors]

    def test_grid_still_flagged(self):
        report = _validate_22(_proposal([_node("g", "grid", "ground")], []))
        assert any("not a real LOP" in i.message for i in report.errors), (
            [e.message for e in report.errors])

    def test_ordering_advisory_intact_on_h22(self):
        geo = _node("geo", "sphere", "geo_sphere")
        assign = _node("assign", "assignmaterial", "assign_material")
        p = _proposal([geo, assign], [ProposedEdge("geo", 0, "assign", 0)])
        report = _validate_22(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]
        assert _ordering_advisories(report), [a.message for a in report.advisories]

    def test_materiallibrary_upstream_satisfies_on_h22(self):
        geo = _node("geo", "sphere", "geo_sphere")
        matlib = _node("matlib", "materiallibrary", "matlib")
        assign = _node("assign", "assignmaterial", "assign_material")
        p = _proposal([geo, matlib, assign], [
            ProposedEdge("geo", 0, "matlib", 0),
            ProposedEdge("matlib", 0, "assign", 0),
        ])
        report = _validate_22(p)
        assert report.status == ValidationStatus.VALID, [e.message for e in report.errors]
        assert not _ordering_advisories(report), [a.message for a in report.advisories]

    def test_default_construction_resolves_h22_catalog_under_h22_host(self, monkeypatch):
        # End to end: a default-constructed validator on a (faked) H22 host
        # loads the _22 catalog via the major-aware resolver — no injection.
        monkeypatch.setitem(sys.modules, "hou", _fake_hou(22))
        v = GraphValidator(_AllExist(), _MockConn())
        assert v._lop_catalog is not None
        assert v._lop_catalog["houdini_version"] == "22.0.368"
        report = v.validate(_proposal([_node("l", "rectlight", "key")], []))
        assert report.status == ValidationStatus.INVALID
