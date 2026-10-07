"""SC-02: the doctor names a missing or unreadable SideFX help library.

The SideFX library (``cognitive/tools/sidefx_library.py``) is configured by
``$SYNAPSE_SIDEFX_CORPUS_ROOT`` or ``<repo>/.synapse/sidefx_library.json``. On
this seat the root is ``G:/HOUDINI22/_CORPUS``. When that drive is absent,
Scout quietly falls back to the repo ``rag/`` corpus and Identify finds no node
help pages; until this check, ``synapse_doctor`` said nothing about it.

States pinned here:
  not configured        -> skipped (a legitimate setup, named as such)
  configured, root gone -> fail, naming the root and what is disabled
  configured, broken    -> fail, carrying the library's own reason
  configured, ready     -> ok, with the generation actually opened
"""

from contextlib import closing
import json
import sqlite3
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
# Plant-or-enrich, never a skeleton (tests/test_m3_logs_doctor.py convention).
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "text"):
    _h.text = MagicMock()
    _h.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.cognitive.tools import sidefx_library as library  # noqa: E402
from synapse.server import doctor  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Never read the checkout's real .synapse/sidefx_library.json."""
    monkeypatch.delenv(library.ROOT_ENV, raising=False)
    monkeypatch.setattr(library, "CONFIG_PATH",
                        tmp_path / ".synapse" / "sidefx_library.json")


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _configure(root):
    _json(library.CONFIG_PATH, {"schema": library.CONFIG_SCHEMA, "root": str(root)})


def _publish(root, generation="gen-one"):
    """A minimal real published library: pointer + read-only-openable sqlite."""
    database = root / "indexes" / f"{generation}.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    coverage = {"indexed_chunks": 1, "source_errors": 0}
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.executescript("""
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE chunks(id TEXT PRIMARY KEY, source_url TEXT, title TEXT,
                                body TEXT, metadata TEXT, domain TEXT);
            CREATE VIRTUAL TABLE chunks_fts USING fts5(id UNINDEXED, body);
        """)
        connection.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("schema", json.dumps(library.DATABASE_SCHEMA)),
            ("generation", json.dumps(generation)),
            ("coverage", json.dumps(coverage, sort_keys=True)),
        ])
    _json(root / "current.json", {
        "schema": library.POINTER_SCHEMA, "generation": generation,
        "database": f"indexes/{generation}.sqlite3", "coverage": coverage,
    })
    _configure(root)
    return database


def test_not_configured_is_skipped_and_named():
    check = doctor._check_sidefx_library()
    assert check["name"] == "sidefx_library"
    assert check["status"] == "skipped"
    assert "not configured" in check["detail"]
    assert library.ROOT_ENV in check["detail"]


def test_configured_root_missing_fails_and_names_the_root(tmp_path):
    # The SC-02 case: the configured drive/folder is not there.
    missing = tmp_path / "G_drive_not_mounted" / "_CORPUS"
    _configure(missing)
    check = doctor._check_sidefx_library()
    assert check["status"] == "fail"
    assert str(missing) in check["detail"]
    assert "does not exist" in check["detail"]
    # The consequence is stated, not left for the artist to infer.
    assert "grounded" in check["detail"].lower()
    assert check["result"]["root"] == str(missing)
    assert check["result"]["config_source"] == str(library.CONFIG_PATH)


def test_env_root_missing_names_the_env_var(tmp_path, monkeypatch):
    missing = tmp_path / "absent"
    monkeypatch.setenv(library.ROOT_ENV, str(missing))
    check = doctor._check_sidefx_library()
    assert check["status"] == "fail"
    assert f"${library.ROOT_ENV}" in check["detail"]
    assert check["result"]["config_source"] == f"${library.ROOT_ENV}"


def test_root_present_but_database_missing_fails_with_reason(tmp_path):
    root = tmp_path / "corpus"
    database = _publish(root)
    database.unlink()
    check = doctor._check_sidefx_library()
    assert check["status"] == "fail"
    assert check["result"]["reason"]
    assert check["result"]["reason"] in check["detail"]


def test_root_present_but_pointer_missing_fails(tmp_path):
    root = tmp_path / "corpus"
    _publish(root)
    (root / "current.json").unlink()
    check = doctor._check_sidefx_library()
    assert check["status"] == "fail"
    assert "current.json" in check["detail"]


def test_bad_config_schema_fails():
    _json(library.CONFIG_PATH, {"schema": "something/else", "root": "C:/x"})
    check = doctor._check_sidefx_library()
    assert check["status"] == "fail"
    assert "unsupported library configuration schema" in check["detail"]


def test_ready_library_is_ok_with_generation(tmp_path):
    root = tmp_path / "corpus"
    _publish(root, generation="gen-42")
    check = doctor._check_sidefx_library()
    assert check["status"] == "ok", check
    assert "gen-42" in check["detail"]
    assert check["result"]["generation"] == "gen-42"
    assert check["result"]["status"] == "ready"


def test_run_doctor_carries_the_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _configure(tmp_path / "gone")
    result = doctor.run_doctor({}, home=tmp_path)
    by_name = {c["name"]: c for c in result["checks"]}
    assert by_name["sidefx_library"]["status"] == "fail"
    assert sum(result["summary"].values()) == len(result["checks"])
