"""W5-DENSE — node corpus entries enter the dense semantic index (P@1 reaches the bar).

Pins the leg's behaviour hermetically. Two tiers:

* No-embedder tier (always runs): the intent classifier, the deterministic
  exact-type retriever, the lexical-path-untouched guarantee, the ingest no-op
  when there are no node entries, the dirname-match pin, and the scout_eval dedup
  instruments. None of these need torch.
* Embedder tier (skipped when sentence-transformers is absent, e.g. torch-less CI):
  the node-dense index is derived at ingest, node intent fuses it, and a
  delete-and-rebuild reproduces a byte-identical index + identical retrieval
  (the derived-data proof, acceptance predicate 3).

The LIVE shipped-corpus numbers (hybrid P@1 1.0 / floor 1.0, lexical 0.9453 /
0.9962 unchanged, conceptual 0.8333 preserved) are recorded in the receipt and
harness/notes/W5-DENSE_eval.md as `check` evidence; these tests guard the
mechanism those numbers rest on.
"""

import json
from pathlib import Path

import pytest

from synapse.cognitive.tools import scout, scout_ingest, scout_eval


# --------------------------------------------------------------------------- #
#  Fixtures                                                                    #
# --------------------------------------------------------------------------- #
_PROSE = {
    "materialx_shaders.md": "# MaterialX Shaders in Solaris\nlayered shader network "
                            "mtlxstandard_surface hero asset lookdev material graph.",
    "flip_simulation.md": "# FLIP\nwater pouring splashing fluid simulation flip solver.",
}

# A node corpus with the exact hazards the leg must resolve:
#   * 'blur' spans cop+lop (disambiguation) and also appears as a non-h22 labs
#     entry of the same type (h22-preference must win P@1),
#   * 'blur::2.0' is a versioned sibling of 'blur' (must beat the base on its query),
#   * 'attribute' is a generic word a labs/intent entry competes for lexically.
_NODES = [
    {"id": "h22:cop/blur", "type": "blur", "context": "cop",
     "searchable_text": "Blur (blur)\nblur node - cop context\nBlurs the image."},
    {"id": "h22:lop/blur", "type": "blur", "context": "lop",
     "searchable_text": "Blur (blur)\nblur node - lop context\nBlurs a USD attribute."},
    {"id": "h22:cop/blur::2.0", "type": "blur::2.0", "context": "cop",
     "searchable_text": "Blur (blur::2.0)\nblur::2.0 node - cop context\nNewer blur."},
    {"id": "h22:cop/attribute", "type": "attribute", "context": "cop",
     "searchable_text": "Attribute (attribute)\nattribute node - cop context\nReads an attribute."},
    {"id": "labs_blur_9f", "type": "blur", "context": "sop",
     "searchable_text": "Labs Blur (blur)\nblur node - sop context\nSideFXLabs blur HDA."},
    {"id": "labs_intent_ab", "type": "intent_mapping", "context": "",
     "searchable_text": "attribute wrangle vex point attribute intent sticky note."},
    {"id": "h22:cop/chromakey", "type": "chromakey", "context": "cop",
     "searchable_text": "Chroma Key (chromakey)\nchromakey node - cop context\nKeys a color."},
]


def _make_rag(root: Path) -> Path:
    ref = root / "skills" / "houdini21-reference"
    ref.mkdir(parents=True)
    for name, body in _PROSE.items():
        (ref / name).write_text(body, encoding="utf-8")
    meta = root / "documentation" / "_metadata"
    meta.mkdir(parents=True)
    (meta / "semantic_index.json").write_text("{}", encoding="utf-8")
    corpus = root / "corpus"
    corpus.mkdir()
    (corpus / "nodes.json").write_text(
        json.dumps({"schema": "h22_node_corpus/v1", "build": "22.0.368",
                    "entries": _NODES}), encoding="utf-8")
    return root


def _point(store_root: Path):
    scout.RAG_ROOT = Path(store_root)
    scout.VEX_ROOT = Path(store_root)
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
        c.clear()


# --------------------------------------------------------------------------- #
#  No-embedder tier                                                            #
# --------------------------------------------------------------------------- #
def test_node_index_dirname_matches_reader():
    # The writer (scout_ingest) and reader (scout) must name the derived index
    # identically or the dense path silently never loads.
    assert scout_ingest.NODE_INDEX_DIRNAME == scout._NODE_INDEX_DIRNAME


def test_has_node_intent_mirrors_knowledge_rules():
    """scout._has_node_intent must follow the same rules as
    KnowledgeIndex._has_node_intent (bare type / 'node' marker / context+interrogative;
    a keyword-bag sentence that merely contains a type does NOT fire)."""
    nt = {"blur", "chromakey", "attribute"}
    assert scout._has_node_intent("blur", nt) is True                 # bare type
    assert scout._has_node_intent("cop blur", nt) is True             # <=2 tokens
    assert scout._has_node_intent("how does the blur node work", nt) is True    # 'node'
    assert scout._has_node_intent("what blur does in cop", nt) is True          # ctx+interrog
    assert scout._has_node_intent("build a layered shader network for a hero asset", nt) is False
    assert scout._has_node_intent("attribute wrangle vex point sweep", nt) is False  # bag w/ type
    assert scout._has_node_intent("blur", set()) is False             # no corpus types


def test_exact_type_retriever_ordering(tmp_path):
    """exact-type: h22 datasheets first, then current-context-first; a version
    suffix matches only its own type."""
    rag = _make_rag(tmp_path / "rag")
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    _point(tmp_path / "store")
    nt = scout._node_type_universe(scout._stores())
    # 'blur' -> h22 cop/lop before the labs sop entry
    ids = scout._exact_type_ids(scout._stores(), "blur", nt)
    assert ids, "exact-type should match the 'blur' type"
    assert ids[0].startswith("h22:")                    # h22 preferred over labs_blur_9f
    assert "labs_blur_9f" in ids and ids.index("labs_blur_9f") == len(ids) - 1
    # versioned type resolves to its own entry only
    v = scout._exact_type_ids(scout._stores(), "blur::2.0", nt)
    assert v == ["h22:cop/blur::2.0"]
    # a conceptual sentence with no whole-type match and no type token -> nothing
    assert scout._exact_type_ids(scout._stores(), "make a nice picture", nt) == []


def test_bare_type_top1_via_exact_type_lexical_only(tmp_path):
    """Even with NO embedder (lexical_only), the exact-type retriever makes a bare
    type query, a versioned query, and a generic-word query return the right h22
    type at top-1 — the precision that resolves the F1 misses without touching BM25."""
    rag = _make_rag(tmp_path / "rag")
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    # remove any derived indexes so this is provably the dense-less path
    import shutil
    shutil.rmtree(tmp_path / "store" / "semantic_index", ignore_errors=True)
    shutil.rmtree(tmp_path / "store" / "semantic_index_nodes", ignore_errors=True)
    _point(tmp_path / "store")

    def top1_type(q):
        o = scout.synapse_scout(q, k=1)
        assert o["mode"] == "lexical_only"              # no dense in play
        h = o["hits"][0]
        return scout_eval._parse_h22_id(h["id"])

    assert top1_type("blur::2.0") == ("cop", "blur::2.0")   # version beats base
    assert top1_type("attribute") == ("cop", "attribute")  # beats labs_intent lexical hit
    assert top1_type("chromakey") == ("cop", "chromakey")
    assert top1_type("blur")[1] == "blur"                  # spans contexts; type matches


def test_lexical_path_untouched(tmp_path):
    """The BM25 retriever is unchanged: a non-node query still returns lexical
    hits and reports lexical_only (no node intent, no dense)."""
    rag = _make_rag(tmp_path / "rag")
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    import shutil
    shutil.rmtree(tmp_path / "store" / "semantic_index", ignore_errors=True)
    shutil.rmtree(tmp_path / "store" / "semantic_index_nodes", ignore_errors=True)
    _point(tmp_path / "store")
    out = scout.synapse_scout("water pouring splashing fluid", k=3)
    assert out["mode"] == "lexical_only" and out["hits"]
    # _lexical_ids itself still returns the prose doc for a conceptual lexical query
    st = scout._stores()[0]
    assert "flip_simulation" in scout._lexical_ids(st, "water splashing fluid simulation", 10)


def test_build_node_index_noop_without_node_entries(tmp_path):
    """A prose-only rag/ (no corpus node entries) derives no node index and records
    node_index: null — build must not require an embedder in that case."""
    ref = tmp_path / "rag" / "skills" / "houdini21-reference"
    ref.mkdir(parents=True)
    (ref / "a.md").write_text("hou.Node prose only", encoding="utf-8")
    meta = tmp_path / "rag" / "documentation" / "_metadata"
    meta.mkdir(parents=True)
    (meta / "semantic_index.json").write_text("{}", encoding="utf-8")
    store = tmp_path / "store"
    scout_ingest.build_corpus(rag_root=str(tmp_path / "rag"), out_root=str(store))
    assert not (store / scout_ingest.NODE_INDEX_DIRNAME).exists()
    m = json.loads((store / scout_ingest.CORPUS_MANIFEST_NAME).read_text(encoding="utf-8"))
    assert "node_index" in m and m["node_index"] is None


def test_fused_id_without_corpus_entry_is_skipped_not_crash(tmp_path, monkeypatch):
    """A retriever that surfaces an id absent from the corpus (a semantic index
    drifted from entries.jsonl) must be skipped, not KeyError-crash the fusion.
    Pins the W5-DELTA-reported pre-existing scout.py bug fixed by this leg."""
    rag = _make_rag(tmp_path / "rag")
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    import shutil
    shutil.rmtree(tmp_path / "store" / "semantic_index", ignore_errors=True)
    shutil.rmtree(tmp_path / "store" / "semantic_index_nodes", ignore_errors=True)
    _point(tmp_path / "store")
    real = scout._lexical_ids
    monkeypatch.setattr(scout, "_lexical_ids",
                        lambda st, q, k: ["__ghost_not_in_corpus__"] + real(st, q, k))
    out = scout.synapse_scout("water splashing fluid", k=3)          # must not raise
    assert out["hits"]                                               # real hits still returned
    assert all(h["id"] != "__ghost_not_in_corpus__" for h in out["hits"])


def test_dedup_instruments():
    """scout_eval dedup census + probe report the same-(context,type) duplicates
    (the '+9 collapse' contract) — measured, not asserted from prose."""
    dup_nodes = _NODES + [
        {"id": "h22:cop/chromakey#2", "type": "chromakey", "context": "cop",
         "searchable_text": "Chroma Key (chromakey) duplicate twin"}]
    summ = scout_eval.dedup_summary(corpus_entries=dup_nodes)
    assert summ["dup_groups"] == 1
    assert "cop/chromakey" in summ["dup_detail"]
    assert set(summ["dup_detail"]["cop/chromakey"]) == {"h22:cop/chromakey", "h22:cop/chromakey#2"}
    # probe surfaces both twins for the type query via an injected perfect retriever
    def fake(query, k=6, **kw):
        hits = [{"id": e["id"]} for e in dup_nodes if e.get("type", "").lower() == query.lower()]
        return {"hits": hits[:k]}
    probe = scout_eval.run_dedup_probe(scout_fn=fake, corpus_entries=dup_nodes, k=6)
    surfaced = probe["per_group"]["cop/chromakey"]["surfaced_in_topk"]
    assert set(surfaced) == {"h22:cop/chromakey", "h22:cop/chromakey#2"}


# --------------------------------------------------------------------------- #
#  Embedder tier (skipped without sentence-transformers)                       #
# --------------------------------------------------------------------------- #
def _require_embedder():
    pytest.importorskip("sentence_transformers")
    pytest.importorskip("numpy")


def test_node_index_derived_at_ingest(tmp_path):
    _require_embedder()
    rag = _make_rag(tmp_path / "rag")
    store = tmp_path / "store"
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(store))
    nd = store / scout_ingest.NODE_INDEX_DIRNAME
    assert (nd / "manifest.json").is_file()
    assert (nd / "meta.jsonl").is_file()
    assert (nd / "embeddings.npy").is_file()
    m = json.loads((nd / "manifest.json").read_text(encoding="utf-8"))
    # derived data, stamped against the corpus build (Target 1 + 4)
    assert m["derived"] is True and m["embedder"] == "sentence-transformers"
    assert m["content_digest"] and m["source_digest"]
    # context-bearing entries only (labs_intent, context="", is excluded)
    n_ctx = len([e for e in _NODES if e.get("context")])
    assert m["entries"] == n_ctx
    ids = [json.loads(l)["id"] for l in (nd / "meta.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "labs_intent_ab" not in ids


def test_node_dense_fires_hybrid_and_conceptual_uses_prose(tmp_path):
    _require_embedder()
    rag = _make_rag(tmp_path / "rag")
    store = tmp_path / "store"
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(store))
    _point(store)
    # a bare type query engages the dense path -> hybrid mode, node entry top-1
    o = scout.synapse_scout("chromakey", k=3)
    assert o["mode"] == "hybrid"
    assert scout_eval._parse_h22_id(o["hits"][0]["id"]) == ("cop", "chromakey")
    # a conceptual query does NOT fire node intent (prose-dense path, unchanged)
    nt = scout._node_type_universe(scout._stores())
    assert scout._has_node_intent("build a layered shader network for a hero asset", nt) is False


def test_delete_rebuild_identical(tmp_path):
    """Acceptance predicate 3 — the derived-data proof: deleting the index and
    rebuilding from the corpus reproduces a byte-identical index AND identical
    retrieval results."""
    _require_embedder()
    rag = _make_rag(tmp_path / "rag")
    store = tmp_path / "store"

    # Score P@1 over the h22 datasheets only (the campaign corpus). The fixture's
    # non-h22 labs_intent entry is deliberately present to prove node-dense
    # exclusion; it is not an h22 datasheet, so it is not a P@1 subject.
    h22_only = [e for e in _NODES if e["id"].startswith("h22:")]

    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(store))
    nd = store / scout_ingest.NODE_INDEX_DIRNAME
    npy_a = (nd / "embeddings.npy").read_bytes()
    meta_a = (nd / "meta.jsonl").read_bytes()
    digest_a = json.loads((nd / "manifest.json").read_text(encoding="utf-8"))["content_digest"]
    _point(store)
    card_a = scout_eval.run_type_name_eval(corpus_entries=h22_only,
                                           knowledge_index=None, live_types={}).to_dict()

    import shutil
    shutil.rmtree(store)                               # delete the whole derived store
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(store))
    npy_b = (nd / "embeddings.npy").read_bytes()
    meta_b = (nd / "meta.jsonl").read_bytes()
    digest_b = json.loads((nd / "manifest.json").read_text(encoding="utf-8"))["content_digest"]
    _point(store)
    card_b = scout_eval.run_type_name_eval(corpus_entries=h22_only,
                                           knowledge_index=None, live_types={}).to_dict()

    assert digest_a == digest_b                        # deterministic content digest
    assert npy_a == npy_b                              # byte-identical embeddings (CPU build)
    assert meta_a == meta_b
    assert card_a == card_b                            # identical retrieval scorecard
    assert card_a["p_at_1"] == 1.0                     # exact-type precision holds on rebuild
