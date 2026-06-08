"""Tests for synapse.cognitive.tools.scout_ingest — canonical rag/ → scout corpus.

FORGE basic (entries produced, body non-empty, ids unique) + CRUCIBLE hostile
(empty/malformed markdown, no body, dup ids, and the LOAD-BEARING symbol-
preservation regression) + ensure-idempotence + scout-reads-the-materialized-store.
All deterministic against fixture rag/ trees (no dependency on the real rag/ content).
"""

import json
from pathlib import Path

import pytest

from synapse.cognitive.tools import scout_ingest, scout


def _make_rag(rag_root: Path, md_files: dict, topics: dict | None = None) -> Path:
    """A fixture rag/ tree KnowledgeIndex can read (skills/ + documentation/_metadata)."""
    ref = rag_root / "skills" / "houdini21-reference"
    ref.mkdir(parents=True)
    for name, content in md_files.items():
        (ref / name).write_text(content, encoding="utf-8")
    meta = rag_root / "documentation" / "_metadata"
    meta.mkdir(parents=True)
    (meta / "semantic_index.json").write_text(json.dumps(topics or {}), encoding="utf-8")
    return rag_root


def _rows(out: dict) -> list:
    return [json.loads(l) for l in Path(out["path"]).read_text(encoding="utf-8").splitlines() if l.strip()]


# ── FORGE basic ──────────────────────────────────────────────────────────────

def test_build_produces_entries(tmp_path):
    rag = _make_rag(tmp_path / "rag", {
        "lop-solaris.md": "# Solaris\nhou.LopNode editableStage USD composition.",
        "karma.md": "# Karma\nKarma render engine XPU pixel samples.",
    })
    out = scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    assert out["entries"] == 2
    rows = _rows(out)
    assert all(r["searchable_text"].strip() for r in rows)          # body non-empty
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))                                # ids unique
    assert all(set(r) >= {"id", "type", "source", "searchable_text"} for r in rows)


def test_enrichment_from_topics(tmp_path):
    rag = _make_rag(tmp_path / "rag",
                    {"karma.md": "# Karma\nrender engine."},
                    topics={"karma_rendering": {"reference_file": "karma.md",
                                                "keywords": ["xpu", "denoise"],
                                                "summary": "Karma render"}})
    out = scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    st = _rows(out)[0]["searchable_text"]
    assert "xpu" in st and "denoise" in st     # topic keywords enrich the entry


# ── CRUCIBLE hostile ─────────────────────────────────────────────────────────

def test_empty_rag_fails_loud(tmp_path):
    rag = _make_rag(tmp_path / "rag", {})       # no .md files
    with pytest.raises(RuntimeError):
        scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))


def test_malformed_semantic_index_tolerated(tmp_path):
    rag = tmp_path / "rag"
    ref = rag / "skills" / "houdini21-reference"; ref.mkdir(parents=True)
    (ref / "x.md").write_text("# X\nhou.Node content", encoding="utf-8")
    meta = rag / "documentation" / "_metadata"; meta.mkdir(parents=True)
    (meta / "semantic_index.json").write_text("{ not valid json", encoding="utf-8")
    out = scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    assert out["entries"] == 1                  # bad index tolerated; .md still ingests


def test_empty_markdown_no_crash(tmp_path):
    rag = _make_rag(tmp_path / "rag", {"empty.md": "", "real.md": "hou.Node x"})
    out = scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    assert out["entries"] == 2                  # the empty file still yields an entry, no crash


def test_ids_unique(tmp_path):
    rag = _make_rag(tmp_path / "rag", {"a.md": "x", "b.md": "y", "c.md": "z"})
    out = scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    ids = [r["id"] for r in _rows(out)]
    assert len(ids) == len(set(ids))


def test_symbol_preservation_verbatim(tmp_path):
    # LOAD-BEARING: a hou.pdg-style token AND a VEX signature must survive VERBATIM
    # into searchable_text — else scout's _ground_symbols + lexical path go blind.
    md = ("# Recipe\n"
          "Use hou.pdg.workItem in the callback.\n"
          "VEX: vector @P; float n = noise(@P * 2.0);\n")
    rag = _make_rag(tmp_path / "rag", {"vex_pyro.md": md})
    out = scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    st = _rows(out)[0]["searchable_text"]
    assert "hou.pdg.workItem" in st             # dotted API token verbatim
    assert "float n = noise(@P * 2.0)" in st    # VEX signature verbatim
    assert _rows(out)[0]["type"] == "vex_reference"   # 'vex' in stem → vex domain


# ── ensure idempotence + scout reads the materialized store ──────────────────

def test_ensure_idempotent_and_scout_reads(tmp_path, monkeypatch):
    rag = _make_rag(tmp_path / "rag",
                    {"lop.md": "hou.LopNode editableStage USD karma render stage composition"})
    store = tmp_path / "store"
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(store))
    r2 = scout_ingest.ensure_corpus(rag_root=str(rag), out_root=str(store))
    assert r2.get("cached") is True             # second call does NOT rebuild

    monkeypatch.setattr(scout, "RAG_ROOT", store)
    monkeypatch.setattr(scout, "VEX_ROOT", store)
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
        c.clear()
    out = scout.synapse_scout("karma render usd stage hou.LopNode", k=3)
    assert out["mode"] == "lexical_only" and out["hits"]   # non-zero hits off the store
    # Membership now comes from the introspected table (package fallback), not the corpus.
    syms = {s["symbol"]: s["exists_in_runtime"] for s in out["symbols"]}
    assert syms.get("hou.LopNode") is True


# ── Spike 1: freshness digest + manifest ─────────────────────────────────────

def test_build_writes_freshness_manifest(tmp_path):
    rag = _make_rag(tmp_path / "rag", {"a.md": "hou.Node x", "b.md": "hou.Geometry y"})
    store = tmp_path / "store"
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(store))
    mfp = store / scout_ingest.CORPUS_MANIFEST_NAME
    assert mfp.is_file()
    m = json.loads(mfp.read_text(encoding="utf-8"))
    assert m["schema"] == scout_ingest.MANIFEST_SCHEMA
    assert m["source_root"] == str(rag)
    assert m["source_digest"] == scout_ingest.source_digest(rag)   # matches a fresh recompute
    assert m["source_file_count"] == 3                              # 2 .md + semantic_index.json (_make_rag writes it)


def test_source_digest_stable_and_sensitive(tmp_path):
    rag = _make_rag(tmp_path / "rag", {"a.md": "hou.Node x"})
    d1 = scout_ingest.source_digest(rag)
    assert d1 == scout_ingest.source_digest(rag)                    # stable: same inputs → same digest
    # Mutating a source file (size changes) drifts the digest.
    (rag / "skills" / "houdini21-reference" / "a.md").write_text("hou.Node x EXTENDED", encoding="utf-8")
    assert scout_ingest.source_digest(rag) != d1


def test_source_digest_ignores_unrelated_files(tmp_path):
    rag = _make_rag(tmp_path / "rag", {"a.md": "hou.Node x"})
    d1 = scout_ingest.source_digest(rag)
    # A file outside the ingested source set must NOT raise a false-stale.
    (rag / "skills" / "houdini21-reference" / "notes.txt").write_text("scratch", encoding="utf-8")
    (rag / "README.md").write_text("repo readme", encoding="utf-8")
    assert scout_ingest.source_digest(rag) == d1


def test_ensure_rebuilds_manifestless_corpus(tmp_path):
    """A pre-Spike-1 store (entries but no manifest) self-heals on ensure_corpus."""
    rag = _make_rag(tmp_path / "rag", {"a.md": "hou.Node x"})
    store = tmp_path / "store"
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(store))
    (store / scout_ingest.CORPUS_MANIFEST_NAME).unlink()            # simulate old store
    r = scout_ingest.ensure_corpus(rag_root=str(rag), out_root=str(store))
    assert r.get("cached") is not True                              # rebuilt, not served stale
    assert (store / scout_ingest.CORPUS_MANIFEST_NAME).is_file()    # manifest restored
