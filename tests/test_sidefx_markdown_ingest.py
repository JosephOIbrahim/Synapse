"""Bounded offline snapshots reach the real Scout path without acquiring authority."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rag" / "ingest"))
import sidefx_markdown as sm
from synapse.cognitive.tools import scout, scout_ingest


def _record(path, text, **extra):
    path.write_text(text, encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), **extra}


def _snapshot(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    index = _record(inputs / "llms.txt", "# Houdini 22.0\n| HOUDINI help | 22.0.452 |\n")
    page = _record(inputs / "sopimport.md",
                   '# SOP Import\nReference only.\n\n## <a id="splats"></a>Splatbridge\n'
                   'Amber splats and `hou.sidefxPhantomProbe`.\n```python\n## not a heading\n```\n',
                   source_url="https://www.sidefx.com/docs/houdini/nodes/lop/sopimport.md")
    manifest = {"schema": sm.INPUT_SCHEMA, "docs_build": "22.0.452",
                "runtime_build": "22.0.400", "fetched_at": "2026-09-24T17:00:00+00:00",
                "index": index, "pages": [page]}
    path = inputs / "manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    output = tmp_path / "rag" / "corpus" / "sidefx_docs.json"
    return path, output, manifest


def _save(path, manifest):
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_snapshot_preserves_literal_text_hashes_and_only_real_anchors(tmp_path):
    path, output, manifest = _snapshot(tmp_path)
    result = sm.import_snapshot(path, output)
    rows = json.loads(output.read_text(encoding="utf-8"))["entries"]
    assert result["pages"] == 1 and result["entries"] == 2
    assert rows[0]["source_anchor"] is None and "#" not in rows[0]["source"]
    assert rows[1]["source"].endswith("sopimport.md#splats")
    assert '## not a heading' in rows[1]["searchable_text"]
    assert rows[1]["source_sha256"] == manifest["pages"][0]["sha256"]
    assert rows[1]["content_sha256"] == hashlib.sha256(rows[1]["searchable_text"].encode()).hexdigest()
    assert rows[1]["evidence_level"] == "document_only"
    assert rows[1]["build_relation_at_import"] == "ahead_of_runtime"
    assert not any("context" in row or "exists_in_runtime" in row for row in rows)


@pytest.mark.parametrize("fault", ["hash", "build", "apex", "foreign", "traversal",
                                  "empty", "too_many", "duplicate", "oversize", "missing"])
def test_invalid_refresh_keeps_last_complete_snapshot(tmp_path, fault):
    path, output, manifest = _snapshot(tmp_path)
    sm.import_snapshot(path, output)
    previous = output.read_bytes()
    page = manifest["pages"][0]
    if fault == "hash":
        page["sha256"] = "0" * 64
    elif fault == "build":
        manifest["docs_build"] = "22.0.999"
    elif fault == "apex":
        page["source_url"] = "https://www.sidefx.com/docs/houdini/nodes/apex/Abs.md"
    elif fault == "foreign":
        page["source_url"] = "https://example.com/docs/houdini/page.md"
    elif fault == "traversal":
        page["path"] = "../private.md"
    elif fault in ("empty", "oversize"):
        text = "" if fault == "empty" else "# Page\n" + "x" * sm.MAX_PAGE_BYTES
        manifest["pages"] = [_record(path.parent / "sopimport.md", text, source_url=page["source_url"])]
    elif fault == "too_many":
        manifest["pages"] *= sm.MAX_PAGES + 1
    elif fault == "duplicate":
        manifest["pages"] *= 2
    elif fault == "missing":
        manifest["pages"].append({**page, "path": "missing.md",
                                  "source_url": "https://www.sidefx.com/docs/houdini/nodes/lop/other.md"})
    _save(path, manifest)
    with pytest.raises((ValueError, OSError)):
        sm.import_snapshot(path, output)
    assert output.read_bytes() == previous


def test_failed_atomic_publication_keeps_previous_file(tmp_path, monkeypatch):
    path, output, _ = _snapshot(tmp_path)
    sm.import_snapshot(path, output)
    previous = output.read_bytes()
    def denied(*args):
        raise PermissionError("fixture: output busy")
    monkeypatch.setattr(sm.os, "replace", denied)
    with pytest.raises(PermissionError):
        sm.import_snapshot(path, output)
    assert output.read_bytes() == previous
    assert not list(output.parent.glob(".sidefx-*.tmp"))


def test_same_build_same_length_refresh_rebuilds_existing_scout_store(tmp_path):
    path, output, manifest = _snapshot(tmp_path)
    sm.import_snapshot(path, output)
    # Derive a same-second comparison with distinct subsecond times rather than
    # relying on how quickly this machine happens to execute the test.
    timestamp = 1700000000000000000
    os.utime(output, ns=(timestamp, timestamp))
    rag, store = output.parent.parent, tmp_path / "store"
    scout_ingest.build_corpus(str(rag), str(store))
    before = scout_ingest.source_digest(rag)
    previous = json.loads(output.read_text(encoding="utf-8"))
    previous_size = output.stat().st_size
    page = path.parent / "sopimport.md"
    manifest["pages"][0] = _record(page, page.read_text().replace("Amber", "Azure"),
                                   source_url=manifest["pages"][0]["source_url"])
    _save(path, manifest)
    sm.import_snapshot(path, output)
    os.utime(output, ns=(timestamp + 1000000, timestamp + 1000000))
    current = json.loads(output.read_text(encoding="utf-8"))
    assert output.stat().st_size == previous_size
    assert current["docs_build"] == previous["docs_build"]
    assert current["snapshot_id"] != previous["snapshot_id"]
    assert scout_ingest.source_digest(rag) != before
    rebuilt = scout_ingest.ensure_corpus(str(rag), str(store))
    assert not rebuilt.get("cached")
    assert "Azure" in Path(rebuilt["path"]).read_text(encoding="utf-8")


def test_real_scout_hit_keeps_provenance_and_runtime_gate_independent(tmp_path, monkeypatch):
    path, output, _ = _snapshot(tmp_path)
    sm.import_snapshot(path, output)
    store = tmp_path / "store"
    scout_ingest.build_corpus(str(output.parent.parent), str(store))
    monkeypatch.setattr(scout, "RAG_ROOT", store)
    monkeypatch.setattr(scout, "VEX_ROOT", store)
    monkeypatch.setattr(scout, "EXPECTED_HOUDINI_VERSION", "22.0.400")
    for cache in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
        cache.clear()
    result = scout.synapse_scout("Splatbridge hou.sidefxPhantomProbe", domain="docs")
    hit = result["hits"][0]
    assert {"id", "domain", "type", "source", "score", "snippet"} <= hit.keys()
    assert hit["docs_build"] == "22.0.452" and hit["runtime_build"] == "22.0.400"
    assert hit["build_relation"] == "ahead_of_runtime"
    assert hit["source_anchor"] == "splats" and len(hit["source_sha256"]) == 64
    assert hit["evidence_level"] == "document_only"
    phantom = next(s for s in result["symbols"] if s["symbol"] == "hou.sidefxPhantomProbe")
    assert phantom["exists_in_runtime"] is False and phantom["documented"] is True
    # A future host switch updates the comparison even with the same cached rows.
    monkeypatch.setattr(scout, "EXPECTED_HOUDINI_VERSION", "22.0.452")
    with pytest.raises(scout.ScoutError, match="symbol table unavailable"):
        scout.synapse_scout("Splatbridge", domain="docs")
    # The existing explicit warn mode allows document retrieval with an unarmed
    # table; the importer does not bypass the default refusal above.
    monkeypatch.setattr(scout, "DRIFT_POLICY", "warn")
    same = scout.synapse_scout("Splatbridge", domain="docs")["hits"][0]
    assert same["build_relation"] == "same_build"
    assert same["build_relation_at_import"] == "ahead_of_runtime"
    monkeypatch.setattr(scout, "EXPECTED_HOUDINI_VERSION", None)
    monkeypatch.delenv("HOUDINI_VERSION", raising=False)
    external = scout.synapse_scout("Splatbridge", domain="docs")["hits"][0]
    assert external["runtime_build"] is None and external["build_relation"] == "unknown"


def test_legacy_hit_projection_remains_empty():
    assert scout._hit_provenance({"id": "old", "source": "legacy.md"}) == {}
