"""
CTO-RELAY-01 L2 — tests for the Solaris wiring verifiers.

These tests are EVIDENCE, not repair. Several of them assert that a verifier
correctly REPORTS a defect in the Solaris tool tree. That is deliberate: the L2
gate condition is "write verifiers, deposit findings, do not fix source". A
test that pins a known defect keeps the defect visible and fails loudly the day
someone fixes it -- at which point the pin is updated alongside the fix.

Pure Python: no ``hou``, no Houdini. The live tier (stage composition, prim
counts) runs under hython via ``harness/notes/l2_live_verify.py``; its recorded
verdicts live in ``harness/notes/l2_wiring_findings.md``.
"""

import importlib

import pytest

common = importlib.import_module("synapse.validation.solaris.verify_wiring_common")
v_scene = importlib.import_module("synapse.validation.solaris.verify_scene_template")
v_mega = importlib.import_module("synapse.validation.solaris.verify_import_megascans")
v_var = importlib.import_module("synapse.validation.solaris.verify_create_variants")
v_purpose = importlib.import_module("synapse.validation.solaris.verify_set_purpose")
v_audit = importlib.import_module("synapse.validation.solaris.verify_tool_audit")

ALL_RESULTS = [
    v_scene.verify_static,
    v_mega.verify_static,
    v_mega.verify_sop_chain,
    v_var.verify_static_geometry,
    v_var.verify_static_material,
    v_var.verify_static_explore,
    v_purpose.verify_static,
    v_purpose.verify_purpose_map,
    v_audit.verify_structure,
    v_audit.verify_registration,
]


# ---------------------------------------------------------------- harness ---

def test_catalog_is_the_pinned_live_build():
    cat = common.load_catalog()
    assert len(cat) == 218, "live LOP catalogue should carry 218 probed types"
    assert cat["componentmaterial"]["min_inputs"] == 1
    assert cat["componentgeometryvariants"]["max_inputs"] == 99


def test_componentbuilder_is_absent_from_the_live_catalogue():
    """component_builder's native path is a phantom on 22.0.368 (F10)."""
    assert "componentbuilder" not in common.load_catalog()


@pytest.mark.parametrize("fn", ALL_RESULTS, ids=lambda f: f.__qualname__)
def test_every_verifier_honours_the_result_contract(fn):
    res = fn()
    assert res["contract"] == common.CONTRACT_VERSION
    assert res["build"] == common.PINNED_BUILD
    assert res["status"] in ("PASS", "FAIL")
    assert isinstance(res["checks"], list) and res["checks"]
    assert res["status"] == ("FAIL" if res["failures"] else "PASS")
    for check in res["checks"]:
        assert set(check) == {"name", "ok", "detail"}


def test_check_connected_names_each_dead_end():
    topo = [
        {"name": "a", "type": "componentgeometry", "inputs": []},
        {"name": "b", "type": "componentmaterial", "inputs": ["a"]},
        {"name": "out", "type": "componentoutput", "inputs": ["b"]},
        {"name": "loose", "type": "reference", "inputs": []},
    ]
    checks = {c.name: c for c in common.check_connected(topo)}
    assert checks["single_terminal"].ok is False
    assert checks["dead_end[loose]"].ok is False
    assert checks["no_orphans"].ok is False
    assert "loose" in checks["no_orphans"].detail


def test_check_connected_passes_a_clean_chain():
    topo = [
        {"name": "a", "type": "componentgeometry", "inputs": []},
        {"name": "out", "type": "componentoutput", "inputs": ["a"]},
    ]
    assert all(c.ok for c in common.check_connected(topo))
    assert common.terminal_of(topo) == "out"


def test_arity_violation_is_reported_against_the_live_catalogue():
    topo = [{"name": "lonely", "type": "componentmaterial", "inputs": []}]
    checks = {c.name: c for c in common.check_topology(topo)}
    assert checks["lonely:min_inputs"].ok is False
    assert checks["lonely:type_exists"].ok is True


def test_unknown_type_fails_but_non_lop_types_are_exempt():
    bogus = [{"name": "x", "type": "definitely_not_a_lop", "inputs": []}]
    assert common.check_topology(bogus)[0].ok is False
    sop = [{"name": "x", "type": "usdimport", "inputs": []}]
    assert common.check_topology(sop)[0].ok is True


# ------------------------------------------------------- scene_template ----

def test_scene_template_topology_is_fully_wired():
    """The one tool of the five whose emitted chain is correct end to end."""
    res = v_scene.verify_static()
    assert res["status"] == "PASS", res["failures"]
    assert common.terminal_of(v_scene.EXPECTED_TOPOLOGY) == "render"


def test_scene_template_emits_no_deprecated_types():
    cat = common.load_catalog()
    for node in v_scene.EXPECTED_TOPOLOGY:
        assert cat[node["type"]]["deprecated"] is False, node


# ------------------------------------------------------ import_megascans ---

def test_megascans_material_reference_is_orphaned():
    """FINDING F3: the material reference LOP is created and never wired."""
    check = v_mega.material_orphan_check()
    assert check.ok is False, "F3 appears fixed -- update this pin and the finding"
    res = v_mega.verify_static()
    assert res["status"] == "FAIL"
    names = {f["name"] for f in res["failures"]}
    assert "dead_end[mtl_ref_asset]" in names
    assert "no_orphans" in names


def test_megascans_sop_chain_is_connected():
    res = v_mega.verify_sop_chain()
    assert res["status"] == "PASS", res["failures"]


# ------------------------------------------------------- create_variants ---

def test_variant_materials_are_wired_statically():
    """FINDING F4, repaired in SR1 M4 -- pin flipped by the SR1 seam pass.

    The catalog literal it reads was captured pre-F4 and never updated, so it
    asserted a defect the source no longer had: a check that could not fail
    correctly (Law 1). It now declares the post-F4 topology (live-confirmed by
    `harness/notes/sr1_seam_probe.py` LEG-2) and still fails if the base-input
    replay at `create_variants.py:168-170` is reverted.
    """
    assert v_var.unwired_variant_materials() == []
    res = v_var.verify_static_material()
    names = {f["name"] for f in res["failures"]}
    assert not {"mat_red:min_inputs", "mat_blue:min_inputs"} & names, res["failures"]
    # RESIDUAL, recorded not fixed: nothing consumes the variant materials.
    assert res["status"] == "FAIL"
    assert {"dead_end[mat_red]", "dead_end[mat_blue]"} <= names


def test_variant_set_reaches_the_terminal():
    """FINDING F5, repaired in SR1 M4 -- pin flipped by the SR1 seam pass.

    Same stale-literal story as F4 above. Post-fix the geometry branch is one
    connected graph with a single terminal; the assertion still fails if the
    consumer-steal at `create_variants.py:204-219` is reverted.
    """
    res = v_var.verify_static_geometry()
    assert res["status"] == "PASS", res["failures"]
    assert common.terminal_of(v_var.EXPECTED_TOPOLOGY_GEOMETRY) == "output_base"


def test_explore_variants_branch_is_correctly_wired():
    res = v_var.verify_static_explore()
    assert res["status"] == "PASS", res["failures"]


# ----------------------------------------------------------- set_purpose ---

def test_set_purpose_host_chain_is_valid():
    res = v_purpose.verify_static()
    assert res["status"] == "PASS", res["failures"]


def test_set_purpose_map_matches_the_tool():
    res = v_purpose.verify_purpose_map()
    assert res["status"] == "PASS", res["failures"]
    assert set(v_purpose.EXPECTED_PURPOSE_MAP) == {"render", "proxy", "simproxy"}


def test_set_purpose_distinguishes_applied_from_skipped():
    """FINDING F7, repaired in SR1 M4 -- pin flipped per this test's own
    instruction ("F7 appears fixed -- update this pin and the finding").

    This used to assert the defect: two return paths both said status="set",
    so applied and not-applied were indistinguishable. M4 removed the dead
    `componentgeometry.parm("purpose")` branch (REFUTED-LIVE on 22.0.368) and
    authors through the `configureprimitive` LOP instead; the path that cannot
    resolve a target prim now returns "noop". One "set" path remains, and it
    is proven live by
    `tests/solaris/test_live_wiring.py::test_f7_set_purpose_authors_a_real_usd_purpose_live`
    via a UsdGeom readback off the cooked stage.
    """
    check = v_purpose.silent_fallback_check()
    assert check.ok is True, check.detail


# ------------------------------------------------------------ tool_audit ---

def test_tool_audit_is_a_document_not_a_tool():
    """FINDING F2."""
    res = v_audit.verify_structure()
    assert res["status"] == "PASS", res["failures"]
    assert v_audit.HAS_IMPLEMENTATION is False


def test_every_tool_the_audit_claims_is_accounted_for():
    """FINDING F1, repaired in SR1 M1.

    This test used to pin the defect -- "all five are unreachable". A test that
    asserts a defect passes for as long as the defect survives and fails the
    moment it is fixed, so it is rewritten to pin the BEHAVIOUR that matters
    (CTO Ruling 9's pattern): every claimed tool is either dispatchable or
    gated with a reason on record. Nothing is silently missing.

    FAILS IF: a claimed tool is dropped from both the active registry and the
    pending list, or a pending entry loses its stated reason.
    """
    assert v_audit.unregistered_tools() == [], (
        "audit claims a tool that no MCP path can reach and no gate explains"
    )
    accounted = sorted(v_audit.gated_tools()
                       + [n for n in v_audit.claimed_new_tools()
                          if n not in v_audit.gated_tools()])
    assert accounted == v_audit.claimed_new_tools()
    assert len(v_audit.claimed_new_tools()) == 5
    res = v_audit.verify_registration()
    assert res["status"] == "PASS", res["failures"]


def test_import_megascans_is_dispatchable_and_nothing_is_gated():
    """SR1 M5 -- CTO Ruling 13 discharged. F9 (locked componentgeometry HDA)
    and F3 (orphaned material Reference LOP) are repaired and proven by live
    22.0.368 oracles, so the tool is now reachable.

    FAILS IF: import_megascans falls back out of the active registry, or any
    audit-claimed tool becomes gated without this test being revisited.
    """
    assert v_audit.gated_tools() == []
    assert "synapse_solaris_import_megascans" in set(
        __import__("synapse.mcp._tool_registry", fromlist=["x"]).TOOL_NAMES
    )
