"""Fixture-table tests for the H22 API-delta diff engine (task 0.2, deliverable C).

``python/synapse/cognitive/tools/api_delta.py`` is the hou-free core of
``scripts/h22_api_delta.py`` — these tests exercise every diff path on stock
Python with fixture tables, no Houdini. The live-probed ground truth
(``harness/notes/verified_usdlux_encodings_21.0.671.json``) doubles as the
decoder conformance corpus: every alias/encoding pair must round-trip.

Also pins the LOCKSTEP rule: ``host/introspect_nodetypes.py`` carries
zero-synapse copies of the decoder + alias rule (the host layer never imports
the package); if either side drifts, these tests fail loud.

NO Houdini import -- pure fixture checks.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# --- Bootstrap: package root is <repo>/python -------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from synapse.cognitive.tools import api_delta  # noqa: E402

_VERIFIED_JSON = _PROJECT_ROOT / "harness" / "notes" / "verified_usdlux_encodings_21.0.671.json"

_spec = importlib.util.spec_from_file_location(
    "introspect_nodetypes", _PROJECT_ROOT / "host" / "introspect_nodetypes.py"
)
introspect_nodetypes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(introspect_nodetypes)


def _verified_flat() -> dict:
    return api_delta.flatten_verified_encodings(
        json.loads(_VERIFIED_JSON.read_text(encoding="utf-8"))
    )


# ===========================================================================
# 1. Punycode decoding — the 27 live-probed pairs are the conformance corpus
# ===========================================================================

def test_every_verified_pair_round_trips():
    flat = _verified_flat()
    assert len(flat) >= 20, "verified corpus shrank — wrong file?"
    for alias, encoded in flat.items():
        raw = api_delta.decode_parm_name(encoded)
        assert api_delta.alias_from_raw(raw) == alias, (
            f"{encoded} -> {raw!r} -> alias mismatch (expected {alias!r})"
        )


def test_decode_known_pairs_exactly():
    assert api_delta.decode_parm_name("xn__inputsintensity_i0a") == "inputs:intensity"
    assert (api_delta.decode_parm_name("xn__inputscolorTemperature_wcb")
            == "inputs:colorTemperature")
    assert (api_delta.decode_parm_name("xn__inputsshapingconeangle_wcbhe")
            == "inputs:shaping:cone:angle")


def test_non_xn_names_pass_through():
    assert api_delta.decode_parm_name("intensity") == "intensity"
    assert api_delta.decode_parm_name("focalLength") == "focalLength"


def test_malformed_extension_raises():
    with pytest.raises(ValueError):
        api_delta.decode_parm_name("xn__inputsintensity_!!")


def test_alias_rule():
    assert api_delta.alias_from_raw("inputs:colorTemperature_control") == "color_temperature_control"
    assert api_delta.alias_from_raw("inputs:shaping:cone:angle") == "shaping_cone_angle"
    assert api_delta.alias_from_raw("inputs:enableColorTemperature") == "enable_color_temperature"


def test_raw_for_alias_resolves_through_attr_names():
    names = {"intensity": "inputs:intensity"}
    assert api_delta.raw_for_alias("intensity", names) == "inputs:intensity"
    assert api_delta.raw_for_alias("intensity_control", names) == "inputs:intensity_control"
    assert api_delta.raw_for_alias("unknown", names) is None


# ===========================================================================
# 2. Lockstep: host/introspect_nodetypes.py duplicates the decoder + alias
#    rule (zero-synapse host layer) — they must agree on every verified pair
# ===========================================================================

def test_host_decoder_lockstep_with_engine():
    for alias, encoded in _verified_flat().items():
        assert (introspect_nodetypes.decode_parm_name(encoded)
                == api_delta.decode_parm_name(encoded)), f"decoder drift on {encoded}"
    raw = "inputs:colorTemperature_control"
    assert (introspect_nodetypes.alias_from_raw(raw)
            == api_delta.alias_from_raw(raw))


def test_host_flatten_lockstep_with_engine():
    verified = json.loads(_VERIFIED_JSON.read_text(encoding="utf-8"))
    assert (introspect_nodetypes._flatten_verified(verified)
            == api_delta.flatten_verified_encodings(verified))


# ===========================================================================
# 3. Call-site index
# ===========================================================================

def test_callsite_index_and_usage(tmp_path):
    (tmp_path / "a.py").write_text(
        "import hou\nhou.LopNode.dependents\npdg.EventType.CookComplete\n",
        encoding="utf-8",
    )
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("x = hou.LopNode\n", encoding="utf-8")
    index = api_delta.build_callsite_index(tmp_path)
    assert index["hou.LopNode"] == ["sub/b.py"]
    assert index["hou.LopNode.dependents"] == ["a.py"]
    # deeper chains count as usage of the parent symbol
    assert api_delta.symbol_usage("hou.LopNode", index) == ["a.py", "sub/b.py"]
    assert api_delta.symbol_usage("pdg.EventType", index) == ["a.py"]
    assert api_delta.symbol_usage("hou.SopNode", index) == []


# ===========================================================================
# 4. Symbol diff
# ===========================================================================

def test_diff_symbols_identity_is_empty():
    table = ["hou", "hou.Node", "pdg.EventType"]
    d = api_delta.diff_symbols(table, list(table))
    assert d["added"] == [] and d["removed"] == [] and d["moved_candidates"] == []


def test_diff_symbols_ranks_used_removals_first():
    index = {"hou.updateGraphTick": ["server/handlers.py"]}
    d = api_delta.diff_symbols(
        ["hou.updateGraphTick", "hou.aaaUnused", "hou.Node"],
        ["hou.Node"],
        callsite_index=index,
    )
    assert d["removed_count"] == 2
    assert d["removed"][0]["symbol"] == "hou.updateGraphTick"
    assert d["removed"][0]["used_in"] == ["server/handlers.py"]
    assert d["removed"][1]["used_in"] == []


def test_diff_symbols_moved_candidates_by_leaf():
    d = api_delta.diff_symbols(
        ["hou.qt.mainWindow"], ["hou.ui.mainWindow"], callsite_index={}
    )
    assert d["moved_candidates"] == [
        {"removed": "hou.qt.mainWindow", "candidates": ["hou.ui.mainWindow"]}
    ]


# ===========================================================================
# 5. Node-type catalog diff
# ===========================================================================

def _catalog(entries):
    return {"schema": "verified_nodetype_catalog/v1", "entries": entries}


def _entry(name, exists=True, resolved=None, sources=("x.py",)):
    return {"type_name": name, "exists": exists,
            "source_files": list(sources), "resolved": resolved or []}


def _match(cat, full, parms):
    return {"category": cat, "full_name": full, "parms": parms}


def test_diff_node_catalogs_identity_is_empty():
    cat = _catalog([
        _entry("sopimport", resolved=[_match("Lop", "sopimport", [["primpath", "String", "''"]])]),
        _entry("halftone", exists=False),  # pre-existing phantom: never "goes missing"
    ])
    d = api_delta.diff_node_catalogs(cat, json.loads(json.dumps(cat)))
    assert d == {"missing_types": [], "parm_changes": [], "new_types": []}


def test_diff_node_catalogs_missing_type():
    base = _catalog([_entry("layout", resolved=[_match("Lop", "layout", [])])])
    live = _catalog([_entry("layout", exists=False)])
    d = api_delta.diff_node_catalogs(base, live)
    assert d["missing_types"] == [{"type_name": "layout", "source_files": ["x.py"]}]


def test_diff_node_catalogs_parm_level_changes():
    base = _catalog([_entry("domelight", resolved=[_match(
        "Lop", "domelight::3.0",
        [["a", "Float", "1.0"], ["b", "Float", "0.5"], ["gone", "Int", "0"]],
    )])])
    live = _catalog([_entry("domelight", resolved=[_match(
        "Lop", "domelight::3.0",
        [["a", "Float", "2.0"], ["b", "String", "0.5"], ["new", "Int", "0"]],
    )])])
    changes = api_delta.diff_node_catalogs(base, live)["parm_changes"]
    kinds = {(c["change"], c["parm"]) for c in changes}
    assert kinds == {
        ("parm_removed", "gone"), ("parm_added", "new"),
        ("parm_default_changed", "a"), ("parm_template_type_changed", "b"),
    }


def test_diff_node_catalogs_resolution_moved_and_new():
    base = _catalog([_entry("light", resolved=[_match("Lop", "light::2.0", [])])])
    live = _catalog([
        _entry("light", resolved=[_match("Lop", "light::3.0", [])]),
        _entry("newtype", resolved=[_match("Lop", "newtype", [])]),
    ])
    d = api_delta.diff_node_catalogs(base, live)
    assert d["missing_types"] == []
    assert d["parm_changes"] == [{
        "type_name": "light", "match": "Lop/light::2.0",
        "change": "resolution_moved", "now_resolves": ["Lop/light::3.0"],
    }]
    assert d["new_types"] == ["newtype"]


# ===========================================================================
# 6. Punycode diff
# ===========================================================================

_ENC_I = "xn__inputsintensity_i0a"
_ATTRS = {"intensity": "inputs:intensity"}


def test_diff_punycode_identity():
    d = api_delta.diff_punycode(
        pinned={"intensity": _ENC_I, "focal_length": "xn__bogus_camera"},
        live_raw_map={"inputs:intensity": _ENC_I},
        baseline_verified={"intensity": _ENC_I},
        usd_attr_names=_ATTRS,
    )
    assert d["matches"] == 1
    assert d["changed"] == [] and d["vanished"] == []
    # never-verified camera alias not seen live -> informational, NOT unpatched
    assert d["unverified_unprobed"] == ["focal_length"]


def test_diff_punycode_changed_and_vanished():
    d = api_delta.diff_punycode(
        pinned={"intensity": _ENC_I, "exposure": "xn__inputsexposure_vya"},
        live_raw_map={"inputs:intensity": "xn__inputsintensity_DRIFTED"},
        baseline_verified={"intensity": _ENC_I, "exposure": "xn__inputsexposure_vya"},
        usd_attr_names={**_ATTRS, "exposure": "inputs:exposure"},
    )
    assert d["changed"] == [{
        "alias": "intensity", "raw": "inputs:intensity",
        "pinned": _ENC_I, "live": "xn__inputsintensity_DRIFTED",
    }]
    assert d["vanished"] == [{"alias": "exposure", "pinned": "xn__inputsexposure_vya"}]


def test_diff_punycode_new_live_properties_are_informational():
    d = api_delta.diff_punycode(
        pinned={"intensity": _ENC_I},
        live_raw_map={"inputs:intensity": _ENC_I, "inputs:brandNew": "xn__inputsbrandNew_x"},
        baseline_verified={}, usd_attr_names=_ATTRS,
    )
    assert d["new"] == ["inputs:brandNew"]
    assert d["changed"] == [] and d["vanished"] == []


def test_flatten_verified_encodings_committed_file():
    flat = _verified_flat()
    assert flat["intensity"] == "xn__inputsintensity_i0a"
    assert flat["color"] == "xn__inputscolor_zta"  # tuple contributes its base
    assert "_provenance" not in flat


# ===========================================================================
# 7. Report assembly — the check_probe_clean contract
# ===========================================================================

def _identity_report():
    symbols = api_delta.diff_symbols(["hou.Node"], ["hou.Node"])
    cat = _catalog([_entry("sopimport", resolved=[_match("Lop", "sopimport", [])])])
    node_types = api_delta.diff_node_catalogs(cat, cat)
    punycode = api_delta.diff_punycode(
        {"intensity": _ENC_I}, {"inputs:intensity": _ENC_I},
        {"intensity": _ENC_I}, _ATTRS,
    )
    return api_delta.build_delta("21.0.671", "21.0.671", symbols, node_types, punycode)


def test_identity_report_is_clean_and_schema_stamped():
    report = _identity_report()
    assert report["schema"] == "h22_probe_delta/v1"
    assert report["baseline_build"] == report["live_build"] == "21.0.671"
    assert report["unpatched"] == []


def test_report_satisfies_check_probe_clean_shape():
    # harness/verify/checks.py::check_probe_clean counts len(delta["unpatched"])
    report = json.loads(json.dumps(_identity_report()))
    assert len(report.get("unpatched", [])) == 0


def test_unpatched_flattens_real_drift():
    symbols = api_delta.diff_symbols(
        ["hou.updateGraphTick"], [], callsite_index={"hou.updateGraphTick": ["a.py"]}
    )
    base = _catalog([_entry("layout", resolved=[_match("Lop", "layout", [])])])
    live = _catalog([_entry("layout", exists=False)])
    node_types = api_delta.diff_node_catalogs(base, live)
    punycode = api_delta.diff_punycode(
        {"intensity": _ENC_I}, {"inputs:intensity": "xn__DRIFTED_x"},
        {"intensity": _ENC_I}, _ATTRS,
    )
    unpatched = api_delta.flatten_unpatched(symbols, node_types, punycode)
    kinds = [u["kind"] for u in unpatched]
    assert kinds == ["symbol_removed_used", "node_type_missing", "punycode_changed"]


def test_unused_symbol_removal_is_not_unpatched():
    symbols = api_delta.diff_symbols(["hou.neverUsed"], [], callsite_index={})
    unpatched = api_delta.flatten_unpatched(
        symbols, {"missing_types": [], "parm_changes": []}, {}
    )
    assert unpatched == []


# ===========================================================================
# 8. Human triage doc + proposed block
# ===========================================================================

def test_render_markdown_identity():
    text = api_delta.render_markdown(_identity_report())
    assert "identity-clean" in text
    assert "## Consumer: scout symbol table" in text
    assert "## Consumer: usd_punycode" in text
    assert "## Consumer: recipes / handlers" in text
    assert "## Consumer: rag corpus" in text


def test_proposed_punycode_block():
    block = api_delta.proposed_punycode_block(
        pinned={"intensity": _ENC_I, "focal_length": "xn__bogus"},
        live_raw_map={"inputs:intensity": _ENC_I,
                      "inputs:brandNew": "xn__inputsbrandNew_x"},
        usd_attr_names=_ATTRS,
    )
    assert '"intensity": "xn__inputsintensity_i0a",' in block
    assert '# UNRESOLVED by live probe: "focal_length"' in block
    assert '"brand_new": "xn__inputsbrandNew_x",' in block
