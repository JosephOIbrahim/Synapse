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
