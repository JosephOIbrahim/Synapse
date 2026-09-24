"""Real disk FTS controls for Scout's optional, query-only SideFX library."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from synapse.cognitive.tools import scout, sidefx_library as library


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.delenv(library.ROOT_ENV, raising=False)
    monkeypatch.setattr(library, "CONFIG_PATH", tmp_path / ".synapse" / "sidefx_library.json")


def _row(identity, body, *, domain="docs", kind="sidefx_markdown", build="22.0.452"):
    url = f"https://www.sidefx.com/docs/houdini/{identity}.html"
    installed = kind == "sidefx_installed_help"
    return (identity, url, identity.title(), body, json.dumps({
        "type": kind, "docs_build": build,
        "docs_build_basis": "installed_build" if installed else "navigation_index",
        "source_sha256": "a" * 64, "content_sha256": "b" * 64,
        "scope": "sidefx_docs", "raw_source_path": f"raw/{identity}.md",
        "evidence_level": "document_only",
        "source_format": "sidefx_wiki_unexpanded" if installed else "markdown",
        "source_url_basis": "derived_from_installed_path" if installed else "fetched_official_url",
    }, sort_keys=True), domain)


def _publish(root, rows, generation="one"):
    database = root / "indexes" / f"{generation}.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    coverage = {"indexed_chunks": len(rows), "source_errors": 0}
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.executescript("""
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE chunks(id TEXT PRIMARY KEY, source_url TEXT, title TEXT,
                                body TEXT, metadata TEXT, domain TEXT);
            CREATE VIRTUAL TABLE chunks_fts USING fts5(id UNINDEXED, body,
                                                     tokenize='porter unicode61');
        """)
        connection.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("schema", json.dumps(library.DATABASE_SCHEMA)),
            ("generation", json.dumps(generation)),
            ("coverage", json.dumps(coverage, sort_keys=True)),
        ])
        connection.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)", rows)
        connection.executemany("INSERT INTO chunks_fts VALUES (?, ?)",
                               [(row[0], row[3]) for row in rows])
    pointer = {"schema": library.POINTER_SCHEMA, "generation": generation,
               "database": f"indexes/{generation}.sqlite3", "coverage": coverage}
    _json(root / "current.json", pointer)
    _json(library.CONFIG_PATH, {"schema": library.CONFIG_SCHEMA, "root": str(root)})
    return database, pointer


def _wire_legacy(tmp_path, monkeypatch):
    root = tmp_path / "legacy"
    (root / "corpus").mkdir(parents=True)
    _json(root / "corpus" / "entry.json", [{
        "id": "legacy", "type": "reference", "source": "local.md",
        "searchable_text": "quasar existing local reference",
    }])
    for name in ("RAG_ROOT", "VEX_ROOT"):
        monkeypatch.setattr(scout, name, root)
    monkeypatch.setattr(scout, "DRIFT_POLICY", "warn")
    monkeypatch.setattr(scout, "EXPECTED_HOUDINI_VERSION", "22.0.400")
    monkeypatch.setattr(scout, "_load_symbol_table", lambda: (
        {"hou.Node"}, {"stale": False, "loaded": True, "reason": None}))
    monkeypatch.setattr(scout, "_dense_ids", lambda *args: None)
    monkeypatch.setattr(scout, "_node_dense_ids", lambda *args: None)
    for cache in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS):
        cache.clear()
    return root


def test_missing_config_leaves_existing_scout_shape_and_hits_unchanged(tmp_path, monkeypatch):
    _wire_legacy(tmp_path, monkeypatch)
    assert library.query_library("quasar") is None
    result = scout.synapse_scout("quasar")
    assert [hit["id"] for hit in result["hits"]] == ["legacy"]
    assert "source_status" not in result
    assert not any("SideFX library" in warning for warning in result["warnings"])


@pytest.mark.parametrize("fault", ["missing_pointer", "broken_json", "bad_schema", "missing_database",
                                  "corrupt_database", "generation_mismatch", "coverage_mismatch",
                                  "missing_generation", "missing_coverage"])
def test_configured_failure_is_explicit_and_keeps_narrow_fallback(tmp_path, monkeypatch, fault):
    _wire_legacy(tmp_path, monkeypatch)
    root = tmp_path / "external"
    database, pointer = _publish(root, [_row("remote", "quasar")])
    if fault == "missing_pointer":
        (root / "current.json").unlink()
    elif fault == "broken_json":
        (root / "current.json").write_text("{", encoding="utf-8")
    elif fault == "bad_schema":
        pointer["schema"] = "unknown"
        _json(root / "current.json", pointer)
    elif fault == "missing_database":
        database.unlink()
    elif fault == "corrupt_database":
        database.write_bytes(b"not a SQLite database")
    elif fault.startswith("missing_"):
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("DELETE FROM meta WHERE key = ?", (fault[8:],))
    else:
        pointer["generation" if fault == "generation_mismatch" else "coverage"] = (
            "wrong" if fault == "generation_mismatch" else {"indexed_chunks": 999})
        _json(root / "current.json", pointer)
    result = scout.synapse_scout("quasar")
    assert [hit["id"] for hit in result["hits"]] == ["legacy"]
    status = result["source_status"]["sidefx_library"]
    assert status["status"] == "unavailable" and status["reason"]
    assert any("using existing Scout sources only" in warning for warning in result["warnings"])
    if fault == "missing_database":
        assert not database.exists()  # mode=ro must never create an empty database.


@pytest.mark.parametrize("unsafe", ["../outside.sqlite3", "/outside.sqlite3", "C:/outside.sqlite3",
                                   "indexes/../../outside.sqlite3", "indexes\\one.sqlite3",
                                   "//server/share/outside.sqlite3"])
def test_pointer_cannot_escape_library_root(tmp_path, monkeypatch, unsafe):
    root = tmp_path / "external"
    _, pointer = _publish(root, [_row("remote", "quasar")])
    pointer["database"] = unsafe
    _json(root / "current.json", pointer)
    monkeypatch.setattr(library.sqlite3, "connect", lambda *args, **kwargs: pytest.fail(
        "unsafe pointer reached SQLite"))
    result = library.query_library("quasar")
    assert result["source_status"]["status"] == "unavailable"
    assert "unsafe" in result["source_status"]["reason"]


def test_resolved_symlink_escape_rejected(tmp_path):
    root = tmp_path / "external"
    database, _ = _publish(root, [_row("remote", "quasar")])
    outside = tmp_path / "outside.sqlite3"
    database.replace(outside)
    try:
        database.symlink_to(outside)
    except OSError:
        pytest.skip("symlink privilege unavailable on this host")
    result = library.query_library("quasar")
    assert result["source_status"]["status"] == "unavailable"
    assert "escapes" in result["source_status"]["reason"]


def test_environment_override_wins_without_reading_bad_config(tmp_path, monkeypatch):
    root = tmp_path / "external"
    _publish(root, [_row("remote", "quasar")])
    library.CONFIG_PATH.write_text("{bad", encoding="utf-8")
    monkeypatch.setenv(library.ROOT_ENV, str(root))
    assert library.query_library("quasar")["source_status"]["status"] == "ready"


def test_real_bm25_ranking_and_only_shortlist_metadata_loaded(tmp_path):
    # Equal document lengths make term frequency decide the independently
    # expected order. Invalid metadata in a losing row catches whole-table load.
    rows = [_row("best", "quasar quasar quasar"), _row("second", "quasar filler filler"),
            ("unrelated", "https://www.sidefx.com/docs/houdini/other.html", "Other",
             "unrelated filler filler", "{invalid", "docs")]
    _publish(tmp_path / "external", rows)
    result = library.query_library("quasar", k=1)
    assert [entry["id"] for entry in result["entries"]] == ["sidefx_library:best"]
    assert result["source_status"]["coverage"] == {"indexed_chunks": 3, "source_errors": 0}
    assert result["source_status"]["coverage_basis"] == "published_database_metadata"


def test_domain_and_where_filters_apply_before_shortlist_limit(tmp_path):
    rows = [_row("docs", "quasar " * 5), _row("vex/noise", "quasar", domain="vex"),
            _row("apex/callback", "quasar " * 20, domain="apex")]
    _publish(tmp_path / "external", rows)
    assert [entry["domain"] for entry in library.query_library("quasar", domain="vex", k=1)["entries"]] == ["vex"]
    docs = library.query_library("quasar", domain="docs", k=1)["entries"]
    assert [entry["id"] for entry in docs] == ["sidefx_library:docs"]
    filtered = library.query_library("quasar", k=1, where={
        "type": "sidefx_markdown", "source_contains": "vex/noise"})["entries"]
    assert [entry["id"] for entry in filtered] == ["sidefx_library:vex/noise"]
    assert library.query_library("quasar", where={"source_contains": "%"})["entries"] == []
    assert library.query_library("quasar", where={"type": "different"})["entries"] == []
    assert {entry["domain"] for entry in library.query_library("quasar")["entries"]} == {"docs", "vex"}


def test_generation_swap_is_visible_without_cache_clear(tmp_path):
    root = tmp_path / "external"
    _publish(root, [_row("old", "quasar")], generation="old")
    first = library.query_library("quasar")
    _publish(root, [_row("new", "quasar")], generation="new")
    second = library.query_library("quasar")
    assert first["source_status"]["generation"] == "old"
    assert second["source_status"]["generation"] == "new"
    assert [entry["id"] for entry in second["entries"]] == ["sidefx_library:new"]


def test_connection_is_read_only_closed_and_not_shared_across_threads(tmp_path, monkeypatch):
    database, _ = _publish(tmp_path / "external", [_row("remote", "quasar")])
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    connect = sqlite3.connect
    connections = []

    def track(*args, **kwargs):
        assert kwargs.get("uri") is True and args[0].endswith("?mode=ro")
        connection = connect(*args, **kwargs)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM chunks")
        connection.rollback()
        connections.append(connection)
        return connection

    monkeypatch.setattr(library.sqlite3, "connect", track)
    with ThreadPoolExecutor(max_workers=3) as workers:
        results = list(workers.map(library.query_library, ["quasar"] * 6))
    assert len(connections) == 6 and len({id(connection) for connection in connections}) == 6
    assert all(result["source_status"]["status"] == "ready" for result in results)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == digest
    # A main-thread call verifies close independently of SQLite's thread fence.
    library.query_library("quasar")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[-1].execute("SELECT 1")


def test_scout_fuses_library_without_documentation_granting_runtime_membership(tmp_path, monkeypatch):
    _wire_legacy(tmp_path, monkeypatch)
    root = tmp_path / "external"
    _publish(root, [_row("new_api", "quasar hou.FutureOnly", build="22.0.452"),
                    _row("installed_api", "quasar hou.Node", kind="sidefx_installed_help", build="22.0.400")])
    result = scout.synapse_scout("quasar hou.FutureOnly hou.Node", k=8)
    assert {hit["id"] for hit in result["hits"]} == {
        "legacy", "sidefx_library:new_api", "sidefx_library:installed_api"}
    symbols = {symbol["symbol"]: symbol for symbol in result["symbols"]}
    assert symbols["hou.FutureOnly"]["documented"] is True
    assert symbols["hou.FutureOnly"]["exists_in_runtime"] is False
    assert symbols["hou.Node"]["exists_in_runtime"] is True
    hits = {hit["id"]: hit for hit in result["hits"]}
    web = hits["sidefx_library:new_api"]
    assert web["build_relation"] == "ahead_of_runtime"
    assert web["docs_build_basis"] == "navigation_index"
    assert web["source_format"] == "markdown" and web["source_url_basis"] == "fetched_official_url"
    assert web["evidence_level"] == "document_only"
    assert web["source"] == web["source_url"] == "https://www.sidefx.com/docs/houdini/new_api.html"
    assert web["raw_source_path"] == "raw/new_api.md" and web["library_generation"] == "one"
    assert "exists_in_runtime" not in web
    assert hits["sidefx_library:installed_api"]["build_relation"] == "same_build"
    assert hits["sidefx_library:installed_api"]["source_format"] == "sidefx_wiki_unexpanded"
    assert hits["sidefx_library:installed_api"]["source_url_basis"] == "derived_from_installed_path"


def test_scout_respects_library_domain_and_filters(tmp_path, monkeypatch):
    _wire_legacy(tmp_path, monkeypatch)
    _publish(tmp_path / "external", [_row("docs", "quasar"),
                                     _row("vex/noise", "quasar", domain="vex")])
    result = scout.synapse_scout("quasar", domain="vex")
    assert [(hit["id"], hit["domain"]) for hit in result["hits"]] == [
        ("sidefx_library:vex/noise", "vex")]
    result = scout.synapse_scout("quasar", where={
        "type": "sidefx_markdown", "source_contains": "vex/noise"})
    assert [hit["id"] for hit in result["hits"]] == ["sidefx_library:vex/noise"]


def test_anchor_source_origin_and_namespaced_id_roundtrip(tmp_path, monkeypatch):
    _wire_legacy(tmp_path, monkeypatch)
    row = list(_row("guide", "quasar"))
    row[0] = "sidefx_library:guide-chunk"
    metadata = json.loads(row[4])
    metadata.update(source=row[1] + "#render-settings", source_anchor="render-settings",
                    source_origin="web")
    row[4] = json.dumps(metadata, sort_keys=True)
    spoof = list(_row("different", "quasar quasar quasar"))
    metadata = json.loads(spoof[4])
    metadata["source"] = "https://unrelated.invalid/#render-settings"
    spoof[4] = json.dumps(metadata, sort_keys=True)
    _publish(tmp_path / "external", [tuple(row), tuple(spoof)])
    result = scout.synapse_scout("quasar", k=1, where={"source_contains": "#render-settings"})
    assert len(result["hits"]) == 1
    hit = result["hits"][0]
    assert hit["id"] == "sidefx_library:guide-chunk"
    assert hit["source"] == row[1] + "#render-settings" and hit["source_url"] == row[1]
    assert hit["source_anchor"] == "render-settings" and hit["source_origin"] == "web"
    unfiltered = library.query_library("quasar")["entries"]
    rejected = next(entry for entry in unfiltered if entry["id"] == "sidefx_library:different")
    assert rejected["source"] == spoof[1]


def test_library_does_not_disarm_missing_runtime_gate(tmp_path, monkeypatch):
    _wire_legacy(tmp_path, monkeypatch)
    _publish(tmp_path / "external", [_row("fake", "hou.FutureOnly")])
    monkeypatch.setattr(scout, "_load_symbol_table", lambda: (
        None, {"stale": True, "loaded": False, "reason": "table absent"}))
    result = scout.synapse_scout("hou.FutureOnly")
    assert result["gate_armed"] is False
    assert result["symbols"][0]["exists_in_runtime"] is None
    assert result["symbols"][0]["documented"] is True
    assert result["symbols"][0]["unverified_reason"] == "table absent"
    monkeypatch.setattr(scout, "DRIFT_POLICY", "refuse")
    with pytest.raises(scout.ScoutError, match="table absent"):
        scout.synapse_scout("hou.FutureOnly")


def test_scout_apex_route_does_not_consult_local_library(tmp_path, monkeypatch):
    monkeypatch.setattr(scout, "_scout_apex", lambda *args: {"domain": "apex"})
    monkeypatch.setattr(library, "query_library", lambda *args, **kwargs: pytest.fail(
        "APEX must remain on its explicitly federated route"))
    assert scout.synapse_scout("callback", domain="apex") == {"domain": "apex"}
