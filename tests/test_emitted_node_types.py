"""Pin the emitted-node-types extraction (task 0.2, deliverable A).

``scripts/extract_emitted_node_types.py`` statically derives every node-type
string SYNAPSE emits and writes the committed
``python/synapse/cognitive/tools/data/emitted_node_types.json`` that the
drop-day probe (``host/introspect_nodetypes.py``) resolves against the live
catalog. These tests pin:

* determinism — the same tree state renders byte-identical output;
* coverage — every catalog-verified spelling already pinned by
  ``tests/test_apex_recipe_names.py`` (the ``APEX_SEED`` nodetype list) and
  ``tests/test_setdressing_recipe.py`` (``VERIFIED_NODE_TYPES``) is present
  in the committed artifact;
* hygiene — no template placeholders, schema stamped, sources real files.

NO Houdini -- pure data checks on stock Python.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# --- Bootstrap: package root is <repo>/python -------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PKG = _PROJECT_ROOT / "python"
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

_SCRIPT = _PROJECT_ROOT / "scripts" / "extract_emitted_node_types.py"
_DATA = _PKG / "synapse" / "cognitive" / "tools" / "data" / "emitted_node_types.json"

_spec = importlib.util.spec_from_file_location("extract_emitted_node_types", _SCRIPT)
extractor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extractor)


def _committed() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _committed_type_names() -> set:
    return {e["type_name"] for e in _committed()["entries"]}


# ===========================================================================
# 1. Determinism — same tree, identical bytes
# ===========================================================================

def test_extraction_is_deterministic():
    first = extractor.render(extractor.build_payload(commit="TEST"))
    second = extractor.render(extractor.build_payload(commit="TEST"))
    assert first == second


def test_entries_sorted_by_type_name():
    names = [e["type_name"] for e in _committed()["entries"]]
    assert names == sorted(names)


# ===========================================================================
# 2. Coverage of the verified-spelling lists the suite already pins
# ===========================================================================

def test_every_apex_seed_nodetype_present():
    from synapse.science.apex_probes import APEX_SEED

    seed = {
        s.surface.removeprefix("nodetypes.")
        for s in APEX_SEED
        if s.kind == "nodetype"
    }
    assert seed, "APEX_SEED nodetype list is empty — authority moved?"
    missing = seed - _committed_type_names()
    assert not missing, f"apex-seed spellings missing from the artifact: {sorted(missing)}"


def test_every_setdressing_verified_type_present():
    verified = extractor.setdressing_nodetypes()
    assert verified, "VERIFIED_NODE_TYPES read back empty — test file moved?"
    missing = verified - _committed_type_names()
    assert not missing, f"set-dressing spellings missing from the artifact: {sorted(missing)}"


# ===========================================================================
# 3. Artifact hygiene
# ===========================================================================

def test_schema_and_shape():
    data = _committed()
    assert data["schema"] == "emitted_node_types/v1"
    assert data["generated_from_commit"]
    assert data["entries"], "artifact has no entries"
    for entry in data["entries"]:
        assert set(entry) == {"category", "type_name", "source_files"}
        assert entry["source_files"], f"{entry['type_name']}: no source files"


def test_no_template_placeholders_in_type_names():
    for name in _committed_type_names():
        assert "{" not in name and "}" not in name, (
            f"template placeholder leaked into the artifact: {name!r}"
        )
        assert extractor._CREATE_NODE.pattern  # the char class is the guard
        assert all(c.isalnum() or c in "_:." for c in name), (
            f"non-node-type character in {name!r}"
        )


def test_source_files_exist():
    for entry in _committed()["entries"]:
        for rel in entry["source_files"]:
            assert (_PROJECT_ROOT / rel).is_file(), (
                f"{entry['type_name']}: source file {rel} does not exist"
            )


# ===========================================================================
# 4. Catalog audit (CTO B6) — no phantom / deprecated emitted node types
# ===========================================================================
#
# ``rag/catalog/h22.0.400/`` is the authority. ``karma`` is a deprecated LOP
# there (live only as the /out ROP in Driver.json); ``grade`` is in no
# category at all. Both were emitted by live recipes until B6.

_CATALOG_DIR = _PROJECT_ROOT / "rag" / "catalog" / "h22.0.400"


def _index() -> dict:
    index = extractor.load_catalog_index(_CATALOG_DIR)
    assert index, f"catalog index empty — {_CATALOG_DIR} missing?"
    return index


def test_recipe_payload_types_are_harvested():
    payload = extractor.scan_recipe_payload_types()
    assert "colorcorrect" in payload, "recipe payload harvest lost the COP color_correction_setup step"
    assert "usdrender_rop" in payload, "recipe payload harvest lost the planner render step"
    # The TOPs wedge attribute dict carries a data type, not a node type.
    assert "float" not in payload


def test_recipe_payload_types_land_in_committed_artifact():
    entries = {e["type_name"]: e for e in _committed()["entries"]}
    for type_name in extractor.scan_recipe_payload_types():
        assert type_name in entries, f"recipe payload type {type_name!r} missing from the artifact"
        assert "recipe_payload" in entries[type_name]["category"].split("+")


def test_live_tree_emits_no_phantom_or_deprecated_node_types():
    violations = extractor.audit_tree(catalog_dir=_CATALOG_DIR)
    assert violations == [], "\n".join(
        f"{v['verdict']}: {v['type_name']} {v.get('categories') or 'absent'} <- {v['source_files']}"
        for v in violations
    )


def test_committed_artifact_emits_no_phantom_or_deprecated_node_types():
    """The artifact the drop-day probe reads must carry the same verdict."""
    type_files = {e["type_name"]: e["source_files"] for e in _committed()["entries"]}
    lop = extractor.scan_lop_createnode_literals(_PKG / "synapse")
    violations = extractor.catalog_audit(type_files, lop, _index())
    assert violations == [], [(v["verdict"], v["type_name"]) for v in violations]


def test_lop_receiver_scan_is_a_subset_of_the_raw_scan():
    raw = extractor.scan_createnode_literals(_PKG / "synapse")
    lop = extractor.scan_lop_createnode_literals(_PKG / "synapse")
    assert lop, "no stage.createNode literals found — recipes moved off the /stage handle?"
    assert set(lop) <= set(raw)


def test_known_phantom_allowlist_is_still_absent_from_catalog():
    """A stale allowlist entry is a lie about the catalog — fail loud."""
    index = _index()
    for type_name in extractor.KNOWN_PHANTOMS:
        assert type_name not in index, (
            f"{type_name!r} is now in the catalog ({index[type_name]}) — drop it from KNOWN_PHANTOMS"
        )


def test_audit_flags_phantom_and_deprecated_verdicts():
    """The auditor itself can fail: synthetic phantom, LOP-deprecated, all-deprecated."""
    index = {
        "karma": {"Lop": True, "Driver": False},
        "karmarenderproperties": {"Lop": True},
        "duplicate": {"Lop": False, "Sop": True},
        "null": {"Lop": False, "Sop": False},
    }
    type_files = {
        "grade": ["x.py"],                  # phantom
        "karma": ["x.py"],                  # live in Driver -> not flagged by the global rule
        "karmarenderproperties": ["x.py"],  # deprecated everywhere
        "duplicate": ["x.py"],              # mixed, receiver unknown -> not flagged
        "null": ["x.py"],
    }
    lop_files = {"karma": ["x.py"]}         # stage.createNode('karma') -> Lop verdict
    verdicts = {(v["verdict"], v["type_name"], v.get("receiver"))
                for v in extractor.catalog_audit(type_files, lop_files, index, allow={})}
    assert verdicts == {
        ("phantom", "grade", None),
        ("deprecated", "karmarenderproperties", None),
        ("deprecated", "karma", "stage"),
    }
    # The allowlist exempts phantoms only, never a deprecated verdict.
    allowed = {(v["verdict"], v["type_name"])
               for v in extractor.catalog_audit(type_files, lop_files, index,
                                                allow={"grade": "r", "karma": "r"})}
    assert ("phantom", "grade") not in allowed
    assert ("deprecated", "karma") in allowed
