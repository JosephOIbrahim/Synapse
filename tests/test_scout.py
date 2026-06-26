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
    # This manifest-less fixture is intentionally STALE; pin warn so it exercises
    # graceful degradation (the module default is now fail-closed "refuse").
    monkeypatch.setattr(scout, "DRIFT_POLICY", "warn")
    for cache in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
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
    # Membership comes from the introspected table (package fallback here), NOT
    # the corpus — that demotion is the Spike 2.5 fix.
    out = scout.synapse_scout("how do I use hou.LopNode and hou.lopNetworks together")
    syms = {s["symbol"]: s["exists_in_runtime"] for s in out["symbols"]}
    assert syms.get("hou.LopNode") is True       # real in H21.0.671
    assert syms.get("hou.lopNetworks") is False  # phantom — absent from runtime
    # 'documented' is the secondary corpus hint: hou.LopNode is in d1's text, the phantom is not.
    docd = {s["symbol"]: s["documented"] for s in out["symbols"]}
    assert docd.get("hou.LopNode") is True
    assert docd.get("hou.lopNetworks") is False


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
    for cache in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
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


# ── Spike 1: corpus freshness / drift gate ───────────────────────────────────

from synapse.cognitive.tools import scout_ingest


def _build_store(tmp_path):
    """A real rag/ fixture + a build_corpus store (with freshness manifest)."""
    rag = tmp_path / "rag"
    ref = rag / "skills" / "houdini21-reference"; ref.mkdir(parents=True)
    (ref / "lop.md").write_text("hou.LopNode editableStage usd karma render stage", encoding="utf-8")
    meta = rag / "documentation" / "_metadata"; meta.mkdir(parents=True)
    (meta / "semantic_index.json").write_text("{}", encoding="utf-8")
    store = tmp_path / "store"
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(store))
    return rag, store


def _wire(monkeypatch, store, policy="warn"):
    monkeypatch.setattr(scout, "RAG_ROOT", store)
    monkeypatch.setattr(scout, "VEX_ROOT", store)
    monkeypatch.setattr(scout, "DRIFT_POLICY", policy)
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
        c.clear()


def test_fresh_corpus_not_stale(tmp_path, monkeypatch):
    _, store = _build_store(tmp_path)
    _wire(monkeypatch, store)
    out = scout.synapse_scout("hou.LopNode usd stage", k=3)
    assert out["stale"] is False
    assert not any("stale" in w.lower() for w in out["warnings"])


def test_mutated_rag_flags_stale_loud(tmp_path, monkeypatch):
    rag, store = _build_store(tmp_path)
    _wire(monkeypatch, store)
    # Mutate the rag/ source AFTER ingest → digest diverges from the manifest.
    (rag / "skills" / "houdini21-reference" / "lop.md").write_text(
        "hou.LopNode editableStage usd karma render stage MUTATED", encoding="utf-8")
    out = scout.synapse_scout("hou.LopNode usd stage", k=3)
    assert out["stale"] is True
    assert any("stale" in w.lower() for w in out["warnings"])
    assert out["hits"]                       # warn-mode still serves hits


def test_missing_manifest_reads_stale_not_fresh(tmp_path, monkeypatch):
    _, store = _build_store(tmp_path)
    (store / scout_ingest.CORPUS_MANIFEST_NAME).unlink()    # corpus present, manifest gone
    _wire(monkeypatch, store)
    out = scout.synapse_scout("hou.LopNode usd stage", k=3)
    assert out["stale"] is True              # NOT silently fresh (invariant 1)


def test_corrupt_manifest_reads_stale(tmp_path, monkeypatch):
    _, store = _build_store(tmp_path)
    (store / scout_ingest.CORPUS_MANIFEST_NAME).write_text("{ not json", encoding="utf-8")
    _wire(monkeypatch, store)
    out = scout.synapse_scout("hou.LopNode usd stage", k=3)
    assert out["stale"] is True


def test_refuse_policy_raises_on_drift(tmp_path, monkeypatch):
    rag, store = _build_store(tmp_path)
    _wire(monkeypatch, store, policy="refuse")
    (rag / "skills" / "houdini21-reference" / "lop.md").write_text("MUTATED", encoding="utf-8")
    with pytest.raises(scout.ScoutError):
        scout.synapse_scout("hou.LopNode usd stage", k=3)


def test_refuse_policy_passes_when_fresh(tmp_path, monkeypatch):
    _, store = _build_store(tmp_path)
    _wire(monkeypatch, store, policy="refuse")
    out = scout.synapse_scout("hou.LopNode usd stage", k=3)   # fresh → no raise
    assert out["stale"] is False


def test_default_drift_policy_is_refuse(monkeypatch):
    """Env var unset → the phantom-API gate is fail-closed by default (H22 hardening)."""
    import importlib
    monkeypatch.delenv("SYNAPSE_SCOUT_DRIFT_POLICY", raising=False)
    try:
        reloaded = importlib.reload(scout)
        assert reloaded.DRIFT_POLICY == "refuse"
    finally:
        importlib.reload(scout)   # restore module to ambient-env state


# ── Spike 2.5: introspected symbol table = membership authority ──────────────

import hashlib


def _write_table(path, symbols, version="21.0.671", corrupt=False):
    syms = sorted(symbols)
    digest = hashlib.blake2b("\n".join(syms).encode("utf-8"), digest_size=16).hexdigest()
    if corrupt:
        digest = "deadbeef" * 4          # wrong checksum → reads corrupt
    path.write_text(json.dumps({
        "schema": "scout_symbol_table/v1", "houdini_version": version,
        "blake2b": digest, "symbol_count": len(syms), "symbols": syms,
    }), encoding="utf-8")


def _table_store(tmp_path, monkeypatch, entries, *, table_symbols=None,
                 table_version="21.0.671", corrupt=False, expected_version=None,
                 policy="warn"):
    """A store wired into scout with the package table NEUTRALIZED, so membership
    comes ONLY from the store table (or its absence) — hermetic and deterministic."""
    cdir = tmp_path / "corpus"; cdir.mkdir()
    (cdir / "entries.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    (tmp_path / "semantic_index").mkdir()
    if table_symbols is not None:
        _write_table(tmp_path / scout.SYMBOL_TABLE_NAME, table_symbols, table_version, corrupt)
    monkeypatch.setattr(scout, "RAG_ROOT", tmp_path)
    monkeypatch.setattr(scout, "VEX_ROOT", tmp_path)
    monkeypatch.setattr(scout, "DRIFT_POLICY", policy)
    monkeypatch.setattr(scout, "EXPECTED_HOUDINI_VERSION", expected_version)
    monkeypatch.setattr(scout, "_PKG_SYMBOL_TABLE", tmp_path / "no_pkg_table.json")  # neutralize fallback
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
        c.clear()


def test_real_but_undocumented_resolves_true(tmp_path, monkeypatch):
    # THE case that was broken: real API, absent from corpus prose. Table says real.
    _table_store(tmp_path, monkeypatch,
                 entries=[{"id": "d", "type": "ref", "source": "d.md",
                           "searchable_text": "general solaris notes, no class tokens here"}],
                 table_symbols={"hou.LopNode"})
    out = scout.synapse_scout("can I use hou.LopNode", k=3)
    s = {x["symbol"]: x for x in out["symbols"]}["hou.LopNode"]
    assert s["exists_in_runtime"] is True        # membership authority = the table
    assert s["documented"] is False              # corpus never mentions it (the old false phantom)


def test_documented_but_fake_flags_absent(tmp_path, monkeypatch):
    # Adversarial: a fake token written into corpus prose must NOT resurrect it.
    _table_store(tmp_path, monkeypatch,
                 entries=[{"id": "d", "type": "ref", "source": "d.md",
                           "searchable_text": "a blog wrongly mentions hou.lopNetworks here"}],
                 table_symbols={"hou.LopNode"})   # table excludes the fake
    out = scout.synapse_scout("use hou.lopNetworks", k=3)
    s = {x["symbol"]: x for x in out["symbols"]}["hou.lopNetworks"]
    assert s["exists_in_runtime"] is False       # table is authority, corpus is not
    assert s["documented"] is True               # it IS in the prose — and still flagged absent


def test_missing_table_membership_unknown_not_silent(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch,
                 entries=[{"id": "d", "type": "ref", "source": "d.md", "searchable_text": "x"}],
                 table_symbols=None)              # no store table + package neutralized
    out = scout.synapse_scout("use hou.LopNode", k=3)
    assert out["table"]["loaded"] is False and out["table"]["stale"] is True
    s = {x["symbol"]: x for x in out["symbols"]}["hou.LopNode"]
    assert s["exists_in_runtime"] is None         # unknown, never a silent verdict
    assert any("symbol table" in w.lower() for w in out["warnings"])


def test_corrupt_table_reads_stale(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch,
                 entries=[{"id": "d", "type": "ref", "source": "d.md", "searchable_text": "x"}],
                 table_symbols={"hou.LopNode"}, corrupt=True)
    out = scout.synapse_scout("use hou.LopNode", k=3)
    assert out["table"]["loaded"] is False and out["table"]["stale"] is True
    assert {x["symbol"]: x for x in out["symbols"]}["hou.LopNode"]["exists_in_runtime"] is None


def test_version_mismatch_reads_stale(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch,
                 entries=[{"id": "d", "type": "ref", "source": "d.md", "searchable_text": "x"}],
                 table_symbols={"hou.LopNode"}, table_version="21.0.512",
                 expected_version="21.0.671")
    out = scout.synapse_scout("use hou.LopNode", k=3)
    assert out["table"]["loaded"] is False and out["table"]["stale"] is True
    assert "21.0.512" in out["table"]["reason"] and "21.0.671" in out["table"]["reason"]


def test_version_match_trusts_table(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch,
                 entries=[{"id": "d", "type": "ref", "source": "d.md", "searchable_text": "x"}],
                 table_symbols={"hou.LopNode"}, table_version="21.0.671",
                 expected_version="21.0.671")
    out = scout.synapse_scout("use hou.LopNode", k=3)
    assert out["table"]["loaded"] is True and out["table"]["stale"] is False


def test_refuse_policy_raises_on_missing_table(tmp_path, monkeypatch):
    _table_store(tmp_path, monkeypatch,
                 entries=[{"id": "d", "type": "ref", "source": "d.md", "searchable_text": "x"}],
                 table_symbols=None, policy="refuse")
    with pytest.raises(scout.ScoutError):
        scout.synapse_scout("use hou.LopNode", k=3)
