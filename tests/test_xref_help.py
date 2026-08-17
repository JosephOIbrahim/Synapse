"""Pure-Python tests for the C3 help-cache cross-reference referee.

No ``hou``, no live cache, no hython. Fixture cache entries are built inline in
the exact shape of the real Houdini parsed-help cache (verified against
``OneDrive/.../houdini22.0/config/Help/cache/nodes`` on 2026-08-17). Runs under
stock pytest.

The suite pins the parser AND the honesty discipline that makes this a referee
rather than a rumour mill:
  * cache absence == no-evidence, never product-absence
  * a quarantine candidate requires the runtime to have been ACTUALLY consumed
  * every mismatch / quarantine finding carries BOTH anchors
  * zero unclassified rows
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# --- bootstrap: xref_help lives under harness/autoresearch, not the package ---
_REPO_ROOT = Path(__file__).resolve().parent.parent
_AR = _REPO_ROOT / "harness" / "autoresearch"
if str(_AR) not in sys.path:
    sys.path.insert(0, str(_AR))

import xref_help as X  # noqa: E402


# ===========================================================================
# Fixture cache entries — real shapes
# ===========================================================================

def _curveik() -> dict:
    """Deprecated apex-context callback with typed ports + successor link."""
    return {
        "type": "root",
        "attrs": {
            "type": "node", "context": "apex", "namespace": "apex",
            "internal": "rig::CurveIK", "icon": "APEX/rig-CurveIK",
            "since": "20.0", "status": "deprecated", "version": None,
        },
        "body": [
            {"type": "title", "text": ["rig::CurveIK"]},
            {"type": "summary", "text": ["Drives a joint chain with a curve."]},
            {"type": "warning_group", "role": "item_group", "body": [
                {"type": "warning", "text": ["Deprecated"], "body": [
                    {"type": "para", "text": [
                        "This node is deprecated. Use ",
                        {"scheme": "Node",
                         "value": "/nodes/apex/rig--SampleSplineTransforms",
                         "type": "link", "text": "",
                         "fullpath": "/nodes/apex/rig--SampleSplineTransforms.html"},
                        " instead."]},
                ]},
            ]},
            {"type": "inputs_section", "id": "inputs", "text": "Inputs", "body": [
                {"type": "inputs_item_group", "body": [
                    {"type": "inputs_item", "text": ["curve"], "attrs": {"type": "Geometry"}},
                    {"type": "inputs_item", "text": ["curvexform"], "attrs": {"type": "Matrix4"}},
                    {"type": "inputs_item", "text": ["restlocal"],
                     "attrs": {"type": "VariadicArg<Matrix4>"}},
                ]},
            ]},
            {"type": "outputs_section", "id": "outputs", "text": "Outputs", "body": [
                {"type": "outputs_item_group", "body": [
                    {"type": "outputs_item", "text": ["outlocal"],
                     "attrs": {"type": "VariadicArg<Matrix4>"}},
                ]},
            ]},
        ],
        "summary": ["Drives a joint chain with a curve."],
    }


def _sample_v2() -> dict:
    """Current apex-context callback, version 2.0 (the CurveIK successor)."""
    return {
        "type": "root",
        "attrs": {
            "type": "node", "context": "apex", "namespace": "apex",
            "internal": "rig::SampleSplineTransforms",
            "icon": "APEX/rig-SampleSplineTransforms-2.0",
            "version": "2.0", "since": "20.5",
        },
        "body": [
            {"type": "title", "text": ["rig::SampleSplineTransforms"]},
            {"type": "inputs_section", "id": "inputs", "body": [
                {"type": "inputs_item", "text": ["spline"], "attrs": {"type": "Geometry"}},
            ]},
            {"type": "outputs_section", "id": "outputs", "body": [
                {"type": "outputs_item", "text": ["transforms"],
                 "attrs": {"type": "VariadicArg<Matrix4>"}},
            ]},
        ],
        "summary": ["Sample transforms along a spline."],
    }


def _toarray_v2_embedded() -> dict:
    """The live cache's inconsistent shape: attrs.internal ALREADY carries the
    ::2.0 suffix while attrs.version is also '2.0'
    (rig--SplineInterpolateTransformsToArray-2.0.json). Verified live 2026-08-17.
    Most v2.0 siblings do NOT embed the version — the parser must normalise."""
    return {
        "type": "root",
        "attrs": {
            "type": "node", "context": "apex", "namespace": "apex",
            "internal": "rig::SplineInterpolateTransformsToArray::2.0",
            "version": "2.0", "since": "20.5",
        },
        "body": [{"type": "title", "text": ["rig::SplineInterpolateTransformsToArray"]}],
    }


def _mapped_constraints() -> dict:
    """A stub page: no inputs/outputs section at all (ports NOT present)."""
    return {
        "type": "root",
        "attrs": {
            "type": "node", "context": "apex", "namespace": "apex",
            "internal": "component::MappedConstraints",
            "icon": "APEX/component-MappedConstraints", "since": "21.0", "version": "",
        },
        "body": [{"type": "title", "text": ["component::MappedConstraints"]}],
        "title": ["component::MappedConstraints"],
    }


def _sceneinvoke() -> dict:
    """SOP-context node: type == namespace::internal == apex::sceneinvoke."""
    return {
        "type": "root",
        "attrs": {
            "type": "node", "context": "sop", "namespace": "apex",
            "internal": "sceneinvoke", "icon": "SOP/apex-sceneinvoke",
            "since": "20.0", "version": "",
        },
        "body": [{"type": "title", "text": ["Apex Scene Invoke"]}],
        "summary": ["Invoke an APEX scene."],
    }


def _rigbuilder_lop() -> dict:
    """LOP-context node: bare internal (namespace null) == apexsoprigbuilder."""
    return {
        "type": "root",
        "attrs": {
            "type": "node", "context": "lop", "internal": "apexsoprigbuilder",
            "icon": "LOP/apexsoprigbuilder", "since": "22.0",
            "version": None, "namespace": None,
        },
        "body": [{"type": "title", "text": ["APEX SOP Rig Builder"]}],
    }


def _include_fragment() -> dict:
    """A non-node include page (_transform_shared / _wip) — must parse to None."""
    return {"type": "root", "attrs": {"type": "include"}, "body": []}


# ===========================================================================
# 1. Parser — per-context identity, ports, deprecation, successor
# ===========================================================================

def test_parse_apex_callback_deprecated_with_successor_and_ports():
    c = X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json")
    assert c is not None
    assert c.surface == "apex_callback"
    assert c.node == "rig::CurveIK"
    assert c.type_name == "rig::CurveIK"        # base version -> unfolded
    assert c.namespace == "rig"                 # true namespace from internal prefix
    assert c.context == "apex"
    assert c.since == "20.0"
    assert c.status == "deprecated"
    assert c.successor == "rig::SampleSplineTransforms"
    assert c.successor_link and "SampleSplineTransforms" in c.successor_link
    # typed ports, in order
    assert c.ports_present is True
    assert {"name": "curve", "type": "Geometry"} in c.inputs
    assert {"name": "curvexform", "type": "Matrix4"} in c.inputs
    assert {"name": "restlocal", "type": "VariadicArg<Matrix4>"} in c.inputs
    assert c.outputs == [{"name": "outlocal", "type": "VariadicArg<Matrix4>"}]


def test_parse_versioned_callback_folds_version_into_type_name():
    c = X.parse_cache_entry(_sample_v2(), "nodes/apex/rig--SampleSplineTransforms-2.0.json")
    assert c.node == "rig::SampleSplineTransforms"
    assert c.type_name == "rig::SampleSplineTransforms::2.0"   # Houdini-canonical fold
    assert c.version == "2.0"
    assert c.status == "current"
    assert c.successor is None


def test_parse_embedded_version_internal_does_not_double_fold():
    """Regression: the one live cache entry whose attrs.internal already ends in
    ::2.0 must fold to a SINGLE ::2.0, never ::2.0::2.0 (crucible major, live-
    confirmed 2026-08-17). Otherwise the alignment key can never match runtime."""
    c = X.parse_cache_entry(
        _toarray_v2_embedded(),
        "nodes/apex/rig--SplineInterpolateTransformsToArray-2.0.json")
    # node identity version-stripped -> consistent with base-version siblings
    assert c.node == "rig::SplineInterpolateTransformsToArray"
    assert c.version == "2.0"
    assert c.namespace == "rig"
    # alignment key carries the version EXACTLY ONCE
    assert c.type_name == "rig::SplineInterpolateTransformsToArray::2.0"
    assert "::2.0::2.0" not in c.type_name


def test_fold_version_is_idempotent():
    assert X._fold_version("rig::X", "2.0") == "rig::X::2.0"
    assert X._fold_version("rig::X::2.0", "2.0") == "rig::X::2.0"   # no double
    assert X._fold_version("rig::X", "") == "rig::X"
    assert X._fold_version("rig::X", "1.0") == "rig::X"
    assert X._strip_embedded_version("rig::X::2.0", "2.0") == "rig::X"
    assert X._strip_embedded_version("rig::X", "2.0") == "rig::X"


def test_parse_stub_has_no_ports_evidence():
    c = X.parse_cache_entry(_mapped_constraints(), "nodes/apex/component--MappedConstraints-.json")
    assert c.node == "component::MappedConstraints"
    assert c.ports_present is False              # honesty: no section == no-evidence
    assert c.inputs == [] and c.outputs == []
    assert c.status == "current"


def test_parse_sop_context_builds_namespaced_type():
    c = X.parse_cache_entry(_sceneinvoke(), "nodes/sop/apex--sceneinvoke-.json")
    assert c.surface == "sop_type"
    assert c.node == "apex::sceneinvoke"
    assert c.type_name == "apex::sceneinvoke"
    assert c.namespace == "apex"
    assert c.context == "sop"


def test_parse_lop_context_bare_internal():
    c = X.parse_cache_entry(_rigbuilder_lop(), "nodes/lop/apexsoprigbuilder.json")
    assert c.surface == "lop_type"
    assert c.node == "apexsoprigbuilder"
    assert c.type_name == "apexsoprigbuilder"
    assert c.since == "22.0"


def test_parse_include_fragment_is_not_a_node():
    assert X.parse_cache_entry(_include_fragment(), "nodes/apex/_transform_shared.json") is None


# ===========================================================================
# 2. Filename / link decode
# ===========================================================================

def test_decode_help_filename():
    assert X.decode_help_filename("rig--CurveIK") == ("rig", "CurveIK", None)
    assert X.decode_help_filename("rig--SampleSplineTransforms-") == ("rig", "SampleSplineTransforms", "")
    assert X.decode_help_filename("rig--SampleSplineTransforms-2.0") == ("rig", "SampleSplineTransforms", "2.0")
    assert X.decode_help_filename("apex--sceneinvoke-") == ("apex", "sceneinvoke", "")
    assert X.decode_help_filename("apexsoprigbuilder") == (None, "apexsoprigbuilder", None)


def test_link_target_to_node():
    assert X._link_target_to_node("/nodes/apex/rig--SampleSplineTransforms") == "rig::SampleSplineTransforms"
    assert X._link_target_to_node("/nodes/apex/rig--SampleSplineTransforms.html") == "rig::SampleSplineTransforms"
    assert X._link_target_to_node("") is None


# ===========================================================================
# 3. parse_help_cache — directory walk over apex/ + sop/apex--* + lop
# ===========================================================================

def _write_cache(root: Path):
    (root / "nodes" / "apex").mkdir(parents=True)
    (root / "nodes" / "sop").mkdir(parents=True)
    (root / "nodes" / "lop").mkdir(parents=True)
    (root / "nodes" / "apex" / "rig--CurveIK.json").write_text(json.dumps(_curveik()))
    (root / "nodes" / "apex" / "rig--SampleSplineTransforms-2.0.json").write_text(json.dumps(_sample_v2()))
    (root / "nodes" / "apex" / "rig--SplineInterpolateTransformsToArray-2.0.json").write_text(
        json.dumps(_toarray_v2_embedded()))
    (root / "nodes" / "apex" / "component--MappedConstraints-.json").write_text(json.dumps(_mapped_constraints()))
    (root / "nodes" / "apex" / "_transform_shared.json").write_text(json.dumps(_include_fragment()))
    (root / "nodes" / "sop" / "apex--sceneinvoke-.json").write_text(json.dumps(_sceneinvoke()))
    (root / "nodes" / "sop" / "someother.json").write_text(json.dumps(_sceneinvoke()))  # not apex--
    (root / "nodes" / "lop" / "apexsoprigbuilder.json").write_text(json.dumps(_rigbuilder_lop()))


def test_parse_help_cache_walks_the_three_globs(tmp_path):
    _write_cache(tmp_path)
    claims = X.parse_help_cache(tmp_path)
    nodes = {c.node for c in claims}
    # apex/, sop/apex--, lop/apexsoprigbuilder included
    assert "rig::CurveIK" in nodes
    assert "rig::SampleSplineTransforms" in nodes
    assert "apex::sceneinvoke" in nodes
    assert "apexsoprigbuilder" in nodes
    assert "component::MappedConstraints" in nodes
    # the embedded-version entry normalises to its base identity, folded once
    assert "rig::SplineInterpolateTransformsToArray" in nodes
    assert all("::2.0::2.0" not in c.type_name for c in claims)
    # include fragment skipped; non-apex-- sop file NOT matched by the glob
    assert all(c.context != "unknown" for c in claims)
    assert len(claims) == 6


def test_missing_cache_is_no_evidence_not_crash(tmp_path):
    assert X.parse_help_cache(tmp_path / "does_not_exist") == []
    assert X.parse_help_cache(None) == []


def test_malformed_cache_file_is_skipped(tmp_path):
    (tmp_path / "nodes" / "apex").mkdir(parents=True)
    (tmp_path / "nodes" / "apex" / "rig--Good.json").write_text(json.dumps(_curveik()))
    (tmp_path / "nodes" / "apex" / "rig--Bad.json").write_text("{not valid json")
    claims = X.parse_help_cache(tmp_path)
    assert len(claims) == 1  # torn write skipped, good one survives


# ===========================================================================
# 4. Recipes scan — AST, read-only, with anchors
# ===========================================================================

_RECIPES_SRC = '''
APEX_RECIPES = {
    "fk_chain": {
        "title": "FK Chain",
        "nodes": [
            {"type": "bonegenerator", "name": "s1", "parms": {}},
            {"type": "apex::buildfkgraph", "name": "fk1", "parms": {}},
        ],
    },
    "ik_chain": {
        "title": "IK Chain",
        "nodes": [
            {"type": "kinefx::twoboneik", "name": "ik1", "parms": {}},
        ],
    },
}
'''


def test_scan_recipe_names_extracts_types_with_anchors(tmp_path):
    p = tmp_path / "apex_recipes.py"
    p.write_text(_RECIPES_SRC)
    names = X.scan_recipe_names(p)
    by_type = {n.type_name: n for n in names}
    assert set(by_type) == {"bonegenerator", "apex::buildfkgraph", "kinefx::twoboneik"}
    # anchors are real line numbers, recipe attribution resolved
    assert by_type["apex::buildfkgraph"].recipe == "fk_chain"
    assert by_type["kinefx::twoboneik"].recipe == "ik_chain"
    assert by_type["apex::buildfkgraph"].lineno > 0


def test_scan_recipe_names_reads_the_real_module():
    # read-only scan of the actual apex_recipes.py; the migration already put
    # real catalog names in place, so no apex::rig::/apex::sop:: phantoms.
    names = X.scan_recipe_names()
    assert names, "expected recipe node types from the real module"
    types = {n.type_name for n in names}
    assert "apex::buildfkgraph" in types
    # the phantom namespacing the wave exists to kill must be absent
    assert not any(t.startswith("apex::rig::") or t.startswith("apex::sop::") for t in types)


# ===========================================================================
# 5. Runtime catalog — states, tolerance, and the not-consumed default
# ===========================================================================

def _truth_artifact(entries, build="22.0.400") -> dict:
    return {"meta": {"build": build, "mission": "apex_basic"}, "entries": entries}


def test_runtime_not_consumed_is_all_unknown():
    rt = X.load_runtime_catalog(None)
    assert rt.consumed is False
    assert rt.lookup("sop_type", "apex::sceneinvoke")["state"] == X.UNKNOWN


def test_runtime_missing_artifact_is_not_consumed(tmp_path):
    rt = X.load_runtime_catalog(str(tmp_path / "nope.json"))
    assert rt.consumed is False


def test_runtime_consumes_membership(tmp_path):
    art = _truth_artifact([
        {"claim": "type_existence:apex::sceneinvoke", "value": {"exists": True},
         "probe": "type_existence", "build": "22.0.400"},
        {"claim": "type_existence:rig::CurveIK", "value": {"exists": False},
         "probe": "callback_discovery", "build": "22.0.400"},
    ])
    p = tmp_path / "apex_truth_22.0.400.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    assert rt.consumed is True
    assert rt.build == "22.0.400"
    assert rt.lookup("sop_type", "apex::sceneinvoke")["state"] == X.PRESENT
    # rig:: is a callback namespace -> apex_callback surface
    assert rt.lookup("apex_callback", "rig::CurveIK")["state"] == X.ABSENT
    # a type never probed -> UNKNOWN, not ABSENT (silence != absence)
    assert rt.lookup("sop_type", "apex::neverprobed")["state"] == X.UNKNOWN


def test_runtime_value_tolerance():
    assert X._classify_runtime_value(True) == X.PRESENT
    assert X._classify_runtime_value(False) == X.ABSENT
    assert X._classify_runtime_value("UNKNOWN") == X.UNKNOWN
    assert X._classify_runtime_value("true") == X.PRESENT
    assert X._classify_runtime_value({"exists": True}) == X.PRESENT
    assert X._classify_runtime_value({"present": False}) == X.ABSENT
    assert X._classify_runtime_value({"state": "UNKNOWN"}) == X.UNKNOWN
    assert X._classify_runtime_value({"exists": None}) == X.UNKNOWN
    assert X._classify_runtime_value(42) == X.UNKNOWN  # unrecognised -> never a fake PRESENT
    # Honesty gate: junk under a membership key is UNKNOWN, NEVER truthiness-
    # coerced (crucible honesty-gate major, 2026-08-17). 0 must not become ABSENT,
    # 42/[..] must not become PRESENT.
    assert X._classify_runtime_value({"exists": 0}) == X.UNKNOWN
    assert X._classify_runtime_value({"exists": 42}) == X.UNKNOWN
    assert X._classify_runtime_value({"found": [1, 2]}) == X.UNKNOWN
    assert X._classify_runtime_value({"present": 0.5}) == X.UNKNOWN


def test_junk_membership_does_not_flip_consumed_or_quarantine(tmp_path):
    """The full honesty chain: a junk 'exists' value must not flip the catalog to
    consumed, and a docs-present node must NOT be quarantined against it."""
    art = _truth_artifact([{"claim": "callback:rig::CurveIK", "value": {"exists": 0}}])
    p = tmp_path / "apex_truth.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    assert rt.consumed is False                      # junk != membership
    rows = X.three_way_diff(
        [X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json")], rt, [])
    assert rows[0].verdict == X.V_RUNTIME_UNKNOWN     # not quarantined on junk
    assert X.quarantine_candidates(rows) == []


def test_runtime_only_unparseable_entries_is_not_consumed(tmp_path):
    art = _truth_artifact([{"noise": 1}, {"claim": "", "value": None}])
    p = tmp_path / "apex_truth_x.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    assert rt.consumed is False


# ---- WA1-TRUTH's REAL apex_basic schema (verified live 2026-08-17) -----------

def _real_truth_artifact() -> dict:
    """apex_basic shape: apex_callback_catalog:<ns> (enumerated names, '*' has a
    matching count => complete), apex_port_signature:<cb> (exists + null-typed
    port arity), type_exists[*]:<type> (SOP/LOP existence + deprecated)."""
    callback_names = [
        "rig::CurveIK", "rig::SampleSplineTransforms", "rig::SampleSplineTransforms::2.0",
        "transform::LookAt", "geo::Lattice",
    ]
    return {
        "meta": {"build": "22.0.400", "mission": "apex_basic"},
        "entries": [
            {"claim": "apex_callback_catalog:*", "probe": "apex_callback_discovery",
             "value": {"namespace": "*", "count": len(callback_names), "names": callback_names}},
            {"claim": "apex_port_signature:rig::CurveIK", "probe": "apex_port_signature",
             "value": {"exists": True, "callback": "rig::CurveIK", "is_hidden": True,
                       "input_count": 3, "output_count": 1,
                       "inputs": [{"name": None, "type": None}] * 3,
                       "outputs": [{"name": None, "type": None}]}},
            {"claim": "type_exists[*]:apex::sceneinvoke", "probe": "type_existence",
             "value": {"exists": True, "deprecated": False, "found_in_categories": ["Sop"]}},
            {"claim": "type_exists[*]:apex::rigpose", "probe": "type_existence",
             "value": {"exists": True, "deprecated": False, "found_in_categories": ["Sop"]}},
            {"claim": "type_exists[*]:apexsoprigbuilder", "probe": "type_existence",
             "value": {"exists": True, "deprecated": False, "found_in_categories": ["Lop"]}},
            {"claim": "invoke_geo_hash:apex_invoke_smoke", "probe": "chain_hash",
             "value": {"hashes": ["abc", "abc"]}},  # not a membership entry
        ],
    }


def _write_real_truth(tmp_path) -> str:
    p = tmp_path / "apex_truth_22.0.400.json"
    p.write_text(json.dumps(_real_truth_artifact()))
    return str(p)


def test_real_callback_catalog_complete_membership(tmp_path):
    rt = X.load_runtime_catalog(_write_real_truth(tmp_path))
    assert rt.consumed is True
    assert rt.build == "22.0.400"
    assert rt._callback_complete is True
    # enumerated present
    assert rt.lookup("apex_callback", "rig::CurveIK")["state"] == X.PRESENT
    assert rt.lookup("apex_callback", "rig::SampleSplineTransforms::2.0")["state"] == X.PRESENT
    # absent from a COMPLETE enumeration -> KNOWN-ABSENT, with the catalog anchor
    a = rt.lookup("apex_callback", "component::MappedConstraints")
    assert a["state"] == X.ABSENT
    assert a["entry_ref"] and "apex_callback_catalog:*" in a["entry_ref"]


def test_real_type_exists_routes_sop_and_lop(tmp_path):
    rt = X.load_runtime_catalog(_write_real_truth(tmp_path))
    assert rt.lookup("sop_type", "apex::sceneinvoke")["state"] == X.PRESENT
    assert rt.lookup("sop_type", "apex::rigpose")["state"] == X.PRESENT
    assert rt.lookup("lop_type", "apexsoprigbuilder")["state"] == X.PRESENT
    # a SOP type never probed -> UNKNOWN (probed subset, not a complete enum)
    assert rt.lookup("sop_type", "apex::neverprobed")["state"] == X.UNKNOWN


def test_incomplete_callback_catalog_does_not_license_absent(tmp_path):
    # count mismatch => not complete => absence is UNKNOWN, never ABSENT
    art = {"meta": {"build": "x"}, "entries": [
        {"claim": "apex_callback_catalog:*", "probe": "apex_callback_discovery",
         "value": {"count": 999, "names": ["rig::CurveIK"]}}]}
    p = tmp_path / "a.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    assert rt._callback_complete is False
    assert rt.lookup("apex_callback", "rig::CurveIK")["state"] == X.PRESENT
    assert rt.lookup("apex_callback", "rig::Ghost")["state"] == X.UNKNOWN  # not ABSENT


def test_non_membership_entries_do_not_pollute_or_overwrite(tmp_path):
    """invoke_geo_hash / chain_hash are non-membership diagnostics. They must NOT
    enter the membership surface, and a variant keyed by a real type must NOT
    overwrite that type's PRESENT record (crucible realformat-fidelity, 2026-08-17)."""
    art = {"meta": {"build": "x"}, "entries": [
        {"claim": "type_exists[*]:apex::sceneinvoke", "probe": "type_existence",
         "value": {"exists": True, "found_in_categories": ["Sop"]}},
        # smoke keyed by the very type it invokes — the dangerous overwrite case
        {"claim": "invoke_geo_hash:apex::sceneinvoke", "probe": "chain_hash",
         "value": {"hashes": ["a", "a"], "chain": []}},
        {"claim": "invoke_geo_hash:apex_invoke_smoke", "probe": "chain_hash",
         "value": {"hashes": ["a"]}},
    ]}
    p = tmp_path / "a.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    # the real type_exists membership survives, un-demoted
    assert rt.lookup("sop_type", "apex::sceneinvoke")["state"] == X.PRESENT
    # the smoke-only key never becomes a membership record
    assert "apex_invoke_smoke" not in rt._by_surface.get("sop_type", {})
    assert rt.lookup("sop_type", "apex_invoke_smoke")["state"] == X.UNKNOWN


def test_real_diff_confirmed_and_noncallback_quarantine(tmp_path):
    rt = X.load_runtime_catalog(_write_real_truth(tmp_path))
    claims = [
        X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json"),
        X.parse_cache_entry(_mapped_constraints(), "nodes/apex/component--MappedConstraints-.json"),
    ]
    rows = {r.type_name: r for r in X.three_way_diff(claims, rt, [])}
    # CurveIK present in the complete catalog (even though docs mark deprecated)
    # -> confirmed, NOT quarantined. Runtime truth > docs referee.
    assert rows["rig::CurveIK"].verdict == X.V_CONFIRMED
    # MappedConstraints absent from the complete registry -> quarantine, flagged
    # as a likely NON-callback concept (component ns has no callbacks).
    q = rows["component::MappedConstraints"]
    assert q.verdict == X.V_QUARANTINE
    assert q.runtime == X.ABSENT
    assert q.docs_anchor and q.runtime_anchor
    assert any("non-callback concept" in n for n in q.notes)
    cands = X.quarantine_candidates(rows.values())
    assert [c["symbol"] for c in cands] == ["component::MappedConstraints"]


def test_real_port_signature_null_types_no_false_mismatch(tmp_path):
    rt = X.load_runtime_catalog(_write_real_truth(tmp_path))
    rows = {r.type_name: r for r in X.three_way_diff(
        [X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json")], rt, [])}
    # runtime exposes arity but null port types -> no type-mismatch measurable
    assert rows["rig::CurveIK"].verdict == X.V_CONFIRMED
    assert rows["rig::CurveIK"].port_mismatches == []


def test_report_flags_port_types_unmeasurable(tmp_path):
    rt = X.load_runtime_catalog(_write_real_truth(tmp_path))
    claims = [X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json")]
    rows = X.three_way_diff(claims, rt, [])
    report = X.build_report(rows, claims, rt, [], None)
    assert report["meta"]["runtime_callback_catalog_complete"] is True
    assert report["meta"]["runtime_callback_catalog_size"] == 5
    assert report["meta"]["runtime_port_types_measurable"] is False


# ===========================================================================
# 6. Three-way diff verdicts
# ===========================================================================

def _claims():
    return [
        X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json"),
        X.parse_cache_entry(_sceneinvoke(), "nodes/sop/apex--sceneinvoke-.json"),
    ]


def test_verdict_runtime_unknown_when_truth_not_published():
    """The core honesty gate: docs present + runtime NOT consumed => every doc
    row is runtime-unknown, and ZERO quarantine candidates are raised."""
    rows = X.three_way_diff(_claims(), X.load_runtime_catalog(None), [])
    verdicts = {r.type_name: r.verdict for r in rows}
    assert verdicts["rig::CurveIK"] == X.V_RUNTIME_UNKNOWN
    assert verdicts["apex::sceneinvoke"] == X.V_RUNTIME_UNKNOWN
    for r in rows:
        assert r.runtime == X.UNKNOWN
    assert X.quarantine_candidates(rows) == []


def test_verdict_confirmed_and_quarantine_when_consumed(tmp_path):
    art = _truth_artifact([
        {"claim": "type_existence:apex::sceneinvoke", "value": {"exists": True}},
        {"claim": "callback:rig::CurveIK", "value": {"exists": False}},
    ])
    p = tmp_path / "apex_truth_22.0.400.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    rows = {r.type_name: r for r in X.three_way_diff(_claims(), rt, [])}
    assert rows["apex::sceneinvoke"].verdict == X.V_CONFIRMED
    # deprecated + runtime-absent => quarantine candidate
    q = rows["rig::CurveIK"]
    assert q.verdict == X.V_QUARANTINE
    assert q.status == "deprecated"
    # BOTH anchors present
    assert q.docs_anchor == "nodes/apex/rig--CurveIK.json"
    assert q.runtime_anchor and "CurveIK" in q.runtime_anchor
    cands = X.quarantine_candidates(rows.values())
    assert len(cands) == 1
    assert cands[0]["symbol"] == "rig::CurveIK"
    assert cands[0]["docs_anchor"] and cands[0]["runtime_anchor"]


def test_verdict_undocumented_when_runtime_present_docs_absent(tmp_path):
    art = _truth_artifact([
        {"claim": "type_existence:apex::brandnewnode", "value": {"exists": True}},
    ])
    p = tmp_path / "apex_truth.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    rows = {r.type_name: r for r in X.three_way_diff([], rt, [])}
    assert rows["apex::brandnewnode"].verdict == X.V_UNDOCUMENTED
    assert rows["apex::brandnewnode"].docs == "absent"


def test_verdict_type_mismatch_carries_both_anchors(tmp_path):
    # runtime disagrees on the 'curve' port type (Geometry in docs, Matrix4 rt)
    art = _truth_artifact([
        {"claim": "callback:rig::CurveIK",
         "value": {"exists": True,
                   "inputs": [{"name": "curve", "type": "Matrix4"}]}},
    ])
    p = tmp_path / "apex_truth.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    rows = {r.type_name: r for r in X.three_way_diff(
        [X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json")], rt, [])}
    r = rows["rig::CurveIK"]
    assert r.verdict == X.V_TYPE_MISMATCH
    assert r.port_mismatches
    mm = r.port_mismatches[0]
    assert mm["port"] == "curve" and mm["docs_type"] == "Geometry" and mm["runtime_type"] == "Matrix4"
    assert r.docs_anchor and r.runtime_anchor  # both anchors


def test_partial_ports_do_not_false_mismatch(tmp_path):
    # runtime lists a DIFFERENT port only; overlapping 'curve' agrees implicitly
    # by being absent from rt -> no mismatch (partial signature discipline).
    art = _truth_artifact([
        {"claim": "callback:rig::CurveIK",
         "value": {"exists": True, "inputs": [{"name": "otherport", "type": "Float"}]}},
    ])
    p = tmp_path / "apex_truth.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    rows = {r.type_name: r for r in X.three_way_diff(
        [X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json")], rt, [])}
    assert rows["rig::CurveIK"].verdict == X.V_CONFIRMED
    assert rows["rig::CurveIK"].port_mismatches == []


def test_recipes_column_and_anchors(tmp_path):
    recipes = tmp_path / "apex_recipes.py"
    recipes.write_text(
        'APEX_RECIPES = {"r": {"nodes": [{"type": "apex::sceneinvoke", "name": "a"}]}}\n')
    rec_names = X.scan_recipe_names(recipes)
    rows = {r.type_name: r for r in X.three_way_diff(
        [X.parse_cache_entry(_sceneinvoke(), "nodes/sop/apex--sceneinvoke-.json")],
        X.load_runtime_catalog(None), rec_names)}
    r = rows["apex::sceneinvoke"]
    assert r.recipes == "present"
    assert r.recipes_anchors and r.recipes_anchors[0].endswith(":1")


# ===========================================================================
# 7. Invariants: zero unclassified rows, report envelope, markdown
# ===========================================================================

def test_zero_unclassified_rows_both_modes(tmp_path):
    # unconsumed
    rows = X.three_way_diff(_claims(), X.load_runtime_catalog(None), [])
    assert rows and all(r.verdict in X._ALL_VERDICTS for r in rows)
    # consumed
    art = _truth_artifact([{"claim": "type_existence:apex::sceneinvoke",
                            "value": {"exists": True}}])
    p = tmp_path / "t.json"
    p.write_text(json.dumps(art))
    rows2 = X.three_way_diff(_claims(), X.load_runtime_catalog(str(p)), [])
    assert rows2 and all(r.verdict in X._ALL_VERDICTS for r in rows2)


def test_unclassified_counter_is_real_not_tautological():
    """The 'unclassified' summary counter must be able to go non-zero, else the
    zero it reports on the real run proves nothing (crucible minor, 2026-08-17).
    Inject an off-taxonomy verdict and confirm build_report counts it."""
    claims = _claims()
    rt = X.load_runtime_catalog(None)
    rows = X.three_way_diff(claims, rt, [])
    rows[0].verdict = "BOGUS_NOT_IN_TAXONOMY"
    report = X.build_report(rows, claims, rt, [], None)
    assert report["summary"]["unclassified"] == 1


def test_quarantine_requires_both_anchors_in_code():
    """The 'one anchor -> not filed' contract is enforced in code, not merely by
    observation (crucible anchor-completeness hardening, 2026-08-17)."""
    r = X.XrefRow(
        surface="apex_callback", type_name="rig::Ghost", verdict=X.V_QUARANTINE,
        docs="present", runtime=X.ABSENT, recipes="absent",
        docs_anchor="nodes/apex/rig--Ghost.json", runtime_anchor=None)
    assert X.quarantine_candidates([r]) == []          # missing runtime anchor -> dropped
    r.runtime_anchor = "apex_truth.json#entries[0]:callback:rig::Ghost"
    filed = X.quarantine_candidates([r])
    assert len(filed) == 1
    assert filed[0]["docs_anchor"] and filed[0]["runtime_anchor"]


def test_quarantine_candidate_carries_phantoms_filing_fields(tmp_path):
    """A3: a filed candidate carries every field a harness/phantoms/ entry needs,
    both anchors non-null. The ledger location itself is human-gated by design
    (phantoms SPEC: 'never auto-written'); this pins the filing PAYLOAD."""
    art = _truth_artifact([{"claim": "callback:rig::CurveIK", "value": {"exists": False}}])
    p = tmp_path / "apex_truth.json"
    p.write_text(json.dumps(art))
    rt = X.load_runtime_catalog(str(p))
    rows = X.three_way_diff(
        [X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json")], rt, [])
    cands = X.quarantine_candidates(rows)
    assert len(cands) == 1
    for k in ("symbol", "surface", "docs_anchor", "runtime_anchor"):
        assert cands[0].get(k), f"phantoms filing needs {k}"


def test_report_envelope_and_markdown_unconsumed():
    claims = _claims()
    rt = X.load_runtime_catalog(None)
    rows = X.three_way_diff(claims, rt, [])
    report = X.build_report(rows, claims, rt, [], Path("C:/x/houdini22.0/config/Help/cache"),
                            timestamp="2026-08-17T00:00:00+00:00")
    assert report["meta"]["runtime_consumed"] is False
    assert report["meta"]["runtime_build"] == "UNKNOWN"
    assert report["meta"]["cache_config_version"] == "22.0"
    assert report["summary"]["unclassified"] == 0
    assert report["summary"]["quarantine_candidates"] == 0
    md = X.render_markdown(report)
    assert "LOW-RECALL" in md or "low-recall" in md
    assert "UNKNOWN" in md
    assert "rig::CurveIK" in md


def test_report_quarantine_section_when_consumed(tmp_path):
    art = _truth_artifact([{"claim": "callback:rig::CurveIK", "value": {"exists": False}}])
    p = tmp_path / "apex_truth_22.0.400.json"
    p.write_text(json.dumps(art))
    claims = [X.parse_cache_entry(_curveik(), "nodes/apex/rig--CurveIK.json")]
    rt = X.load_runtime_catalog(str(p))
    rows = X.three_way_diff(claims, rt, [])
    report = X.build_report(rows, claims, rt, [], None)
    assert report["summary"]["quarantine_candidates"] == 1
    assert report["meta"]["runtime_build"] == "22.0.400"
    md = X.render_markdown(report)
    assert "Quarantine candidates" in md
    assert "rig::CurveIK" in md


def test_full_run_against_fixture_cache(tmp_path):
    _write_cache(tmp_path)
    report = X.run_xref(tmp_path, None)  # no runtime -> unconsumed
    assert report["summary"]["rows_total"] >= 4
    assert report["summary"]["unclassified"] == 0
    # every doc row is runtime-unknown (no truth consumed), zero quarantine
    assert report["summary"]["quarantine_candidates"] == 0
    assert report["meta"]["runtime_consumed"] is False


def test_cache_config_version_parse():
    assert X.cache_config_version(Path("C:/Users/u/OneDrive/Documents/houdini22.0/config/Help/cache")) == "22.0"
    assert X.cache_config_version(Path("/tmp/nohoudinihere")) is None
