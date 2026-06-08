"""Tests for synapse.cognitive.tools.scout — the federated hybrid retrieval tool.

Deterministic: builds a tiny fixture corpus (no dependency on the real
G:\\HOUDINI21_RAG_SYSTEM or the repo rag/ content), points the tool at it via the
module globals, and exercises the lexical path, RRF, symbol grounding (the
phantom-API check), filters, modes, error paths, and the dispatcher registration.
"""

import json

import pytest

from synapse.cognitive.tools import scout


_ENTRIES = [
    {"id": "d1", "type": "node_reference", "source": "lop-solaris.md",
     "searchable_text": "hou.LopNode editableStage authoring USD stage composition LIVRPS sublayer"},
    {"id": "d2", "type": "karma_reference", "source": "karma.md",
     "searchable_text": "Karma render settings engine XPU CPU pixel samples hou.RopNode render"},
    {"id": "v1", "type": "vex_function", "source": "sidefxlabs",
     "searchable_text": "vex noise fractal turbulence sparse pyro density temperature"},
    {"id": "v2", "type": "vex_function", "source": "sidefxlabs",
     "searchable_text": "vex point cloud pcopen pciterate nearest neighbour"},
]


@pytest.fixture()
def corpus(tmp_path, monkeypatch):
    """A fixture RAG store at tmp_path, wired into scout's module globals; caches
    cleared so each test is isolated."""
    cdir = tmp_path / "corpus"
    cdir.mkdir()
    (cdir / "entries.jsonl").write_text(
        "\n".join(json.dumps(e) for e in _ENTRIES), encoding="utf-8")
    (tmp_path / "semantic_index").mkdir()   # no manifest.json → lexical_only
    monkeypatch.setattr(scout, "RAG_ROOT", tmp_path)
    monkeypatch.setattr(scout, "VEX_ROOT", tmp_path)
    for cache in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS):
        cache.clear()
    return tmp_path


# ── lexical retrieval ────────────────────────────────────────────────────────

def test_lexical_retrieval_finds_relevant(corpus):
    out = scout.synapse_scout("karma render pixel samples XPU", domain="both", k=3)
    assert out["mode"] == "lexical_only"
    assert out["hits"], "expected at least one lexical hit"
    assert out["hits"][0]["id"] == "d2"          # the karma doc ranks first
    assert out["hits"][0]["domain"] == "docs"
    assert 0 < out["hits"][0]["score"] <= 1.0


def test_lexical_only_mode_warns_no_embedder(corpus):
    out = scout.synapse_scout("pyro", k=5)
    assert out["mode"] == "lexical_only"
    assert any("embedder" in w.lower() for w in out["warnings"])


def test_k_limits_hits(corpus):
    out = scout.synapse_scout("vex hou render usd noise", k=2)
    assert len(out["hits"]) <= 2


# ── domain classification + filters ──────────────────────────────────────────

def test_domain_vex_filters_to_vex_entries(corpus):
    out = scout.synapse_scout("noise pyro point cloud", domain="vex", k=5)
    assert out["hits"] and all(h["domain"] == "vex" for h in out["hits"])
    assert {h["id"] for h in out["hits"]} <= {"v1", "v2"}


def test_domain_docs_filters_to_docs(corpus):
    out = scout.synapse_scout("hou usd karma noise", domain="docs", k=5)
    assert all(h["domain"] == "docs" for h in out["hits"])


def test_where_source_contains_filter(corpus):
    out = scout.synapse_scout("vex noise pyro", domain="both", k=5,
                              where={"source_contains": "sidefxlabs"})
    assert out["hits"] and all("sidefxlabs" in h["source"] for h in out["hits"])


def test_where_type_filter(corpus):
    out = scout.synapse_scout("vex noise pyro point", k=5, where={"type": "vex_function"})
    assert all(h["type"] == "vex_function" for h in out["hits"])


# ── symbol grounding (the phantom-API check) ─────────────────────────────────

def test_symbol_grounding_flags_phantom(corpus):
    out = scout.synapse_scout("how do I use hou.LopNode and hou.lopNetworks together")
    syms = {s["symbol"]: s["found_in_corpus"] for s in out["symbols"]}
    assert syms.get("hou.LopNode") is True       # real — present in d1
    assert syms.get("hou.lopNetworks") is False  # phantom — absent from corpus


def test_no_symbols_when_query_has_none(corpus):
    out = scout.synapse_scout("how to render a karma image")
    assert out["symbols"] == []


# ── error paths (raise ScoutError → dispatcher wraps it) ─────────────────────

def test_empty_query_raises(corpus):
    with pytest.raises(scout.ScoutError):
        scout.synapse_scout("   ")


def test_bad_domain_raises(corpus):
    with pytest.raises(scout.ScoutError):
        scout.synapse_scout("karma", domain="everything")


def test_missing_corpus_dir_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(scout, "RAG_ROOT", tmp_path)      # no corpus/ subdir
    monkeypatch.setattr(scout, "VEX_ROOT", tmp_path)
    for cache in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS):
        cache.clear()
    with pytest.raises(scout.ScoutError):
        scout.synapse_scout("anything")


# ── registration matches the dispatcher's keyword-only schema ────────────────

def test_register_passes_schema_by_keyword():
    captured = {}

    def fake_register(name, fn, *, schema=None):   # mirrors Dispatcher.register
        captured.update(name=name, fn=fn, schema=schema)

    scout.register(fake_register)
    assert captured["name"] == "synapse_scout"
    assert captured["fn"] is scout.synapse_scout
    assert captured["schema"] is scout.SYNAPSE_SCOUT_SCHEMA


def test_register_into_real_dispatcher():
    from synapse.cognitive.dispatcher import Dispatcher
    d = Dispatcher(is_testing=True)
    scout.register(d.register)
    assert d.is_registered("synapse_scout")
