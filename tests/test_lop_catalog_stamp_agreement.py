"""G5a: a packaged LOP knowledge catalog stamped on a build the runtime has
moved past must be detected.

``core/lop_knowledge.py:_pkg_catalog_path()`` resolves the packaged catalog by
MAJOR only, and the loader validates ``schema`` plus a blake2b over ``content``
without ever reading ``houdini_version`` — so a within-major point-release drift
passes in silence. These pin the detector for that gap. The detector reports;
it changes nothing about what the loader or the validator DOES on mismatch.
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "harness/verify/version_agreement.py"
_spec = importlib.util.spec_from_file_location("g5a_version_agreement", VERIFIER)
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)

DATA = "python/synapse/cognitive/tools/data"


def _write(root, relative, payload):
    target = Path(root) / DATA / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _catalog(build):
    return {"schema": "lop_solaris_knowledge/v1", "houdini_version": build,
            "blake2b": "0" * 32, "content": {}}


def _symbol_table(build):
    return {"schema": "scout_symbol_table/v1", "houdini_version": build,
            "symbols": []}


@pytest.fixture
def tree(tmp_path):
    """A minimal repo root carrying one per-major catalog + symbol table."""
    def build(catalog_build, table_build, major="22"):
        if catalog_build is not None:
            _write(tmp_path, "lop_solaris_knowledge_%s.json" % major,
                   _catalog(catalog_build))
        if table_build is not None:
            _write(tmp_path, "h%s_symbol_table.json" % major,
                   _symbol_table(table_build))
        return tmp_path
    return build


def test_point_release_drift_is_a_failure(tree):
    root = tree("22.0.368", "22.0.400")
    result = verifier.lop_catalog_agreement(repo_root=root)
    assert result["status"] == "FAIL", result
    assert result["ok"] is False
    assert "22.0.368" in result["reason"] and "22.0.400" in result["reason"]
    assert result["catalogs"]["22"]["catalog_build"] == "22.0.368"
    assert result["catalogs"]["22"]["reference_build"] == "22.0.400"


def test_agreeing_stamps_pass(tree):
    root = tree("22.0.400", "22.0.400")
    result = verifier.lop_catalog_agreement(repo_root=root)
    assert result["status"] == "PASS", result
    assert result["ok"] is True


def test_missing_reference_is_unknown_never_pass(tree):
    root = tree("22.0.400", None)
    result = verifier.lop_catalog_agreement(repo_root=root)
    assert result["status"] == "UNKNOWN", result
    assert result["ok"] is False


def test_unstamped_catalog_is_unknown(tmp_path):
    _write(tmp_path, "lop_solaris_knowledge_22.json",
           {"schema": "lop_solaris_knowledge/v1", "content": {}})
    _write(tmp_path, "h22_symbol_table.json", _symbol_table("22.0.400"))
    result = verifier.lop_catalog_agreement(repo_root=tmp_path)
    assert result["status"] == "UNKNOWN", result
    assert result["ok"] is False


def test_stamp_major_must_match_the_filename_major(tree):
    root = tree("21.0.671", "22.0.400")
    result = verifier.lop_catalog_agreement(repo_root=root)
    assert result["status"] == "FAIL", result
    assert "major" in result["reason"]


def test_no_catalog_at_all_is_unknown(tmp_path):
    result = verifier.lop_catalog_agreement(repo_root=tmp_path)
    assert result["status"] == "UNKNOWN", result
    assert result["ok"] is False


def test_supplied_runtime_build_is_compared(tree):
    root = tree("22.0.368", "22.0.368")
    agreeing = verifier.lop_catalog_agreement(repo_root=root)
    assert agreeing["status"] == "PASS", agreeing
    drifted = verifier.lop_catalog_agreement(runtime_build="22.0.400",
                                             repo_root=root)
    assert drifted["status"] == "FAIL", drifted
    assert drifted["runtime_comparison"]["status"] == "FAIL"


def test_offline_check_does_not_invent_a_live_runtime(tree):
    root = tree("22.0.400", "22.0.400")
    result = verifier.lop_catalog_agreement(repo_root=root)
    assert result["runtime_comparison"] == {"status": "UNKNOWN", "build": None}


def test_shipped_h22_catalog_is_in_observed_drift():
    """The hazard on this tree, read from the files themselves.

    LAW 6: when the 22.x catalog is re-harvested on the running build this test
    gets REWRITTEN to assert PASS — never deleted, never skipped.
    """
    data = ROOT / DATA
    catalog = json.loads((data / "lop_solaris_knowledge_22.json").read_text(
        encoding="utf-8"))["houdini_version"]
    table = json.loads((data / "h22_symbol_table.json").read_text(
        encoding="utf-8"))["houdini_version"]
    assert catalog != table, (catalog, table)
    result = verifier.lop_catalog_agreement(repo_root=ROOT)
    assert result["status"] == "FAIL", result
    assert result["catalogs"]["22"]["catalog_build"] == catalog
    assert result["catalogs"]["22"]["reference_build"] == table
    # The 21 pair is the control: both artifacts stamped on the same build.
    assert result["catalogs"]["21"]["status"] == "PASS", result
