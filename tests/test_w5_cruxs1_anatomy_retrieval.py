"""W5-CRUXS1 — the CTO-bound Solaris compound-node anatomy doc is retrievable via scout.

Pins the REFUTATION of finding F-CRUX-1. F-CRUX-1 claimed
``solaris_compound_node_anatomy.md`` has a ``rag/semantic_index`` embedding row but
"NO rag/corpus/ backing entry, so scout's defensive skip-id-without-corpus-entry
logic drops it" and the doc is unreachable via ``synapse_scout``.

Direct reproduction (harness/notes/receipts/W5-CRUXS1.json) shows the opposite in
the REAL path: the corpus is MATERIALIZED by ``scout_ingest.activate()`` from the
repo ``rag/`` tree — ``KnowledgeIndex`` reads *every* ``skills/houdini21-reference/*.md``
into a ``{id, type, source, searchable_text}`` entry, keyed by the file stem — so the
anatomy doc DOES get a corpus entry and scout surfaces it (rank 1-4 hybrid,
rank 1-2 lexical-only) with its H22 ``alternative`` output + the three island paths
in the retrievable text. F-CRUX-1's symptom is reachable ONLY when scout runs
against the *un-materialized* raw ``rag/`` root (no ``activate()``); production
activates first (``mcp_server.py::_get_scout_dispatcher``), so the doc is
live-retrievable.

These tests guard that retrieval-coverage so it cannot silently regress. Three tiers:

* Lexical tier (always runs; no torch): after a lexical-only corpus build the anatomy
  doc surfaces for the componentgeometry / component-builder queries F-CRUX-1 named,
  it has a corpus entry, and its H22 facts are in the retrievable text.
* Real-corpus tier (always runs; no torch): the REAL anatomy doc, in the REAL shipped
  corpus (node datasheets + all prose + sidefxlabs), still surfaces for those queries.
* Hybrid tier (skipped without sentence-transformers): the production mode — the prose
  dense index carries the embedding row AND the materialized corpus backs it.
"""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from synapse.cognitive.tools import scout, scout_ingest

ANATOMY_ID = "solaris_compound_node_anatomy"

# The CTO-bound H22 specifics F-CRUX-1 said could not surface: the 'alternative'
# 4th output, the user-editable islands, the locked-HDA flag, and the
# karmamaterial* phantom warning. Load-bearing + stable across doc edits.
_H22_FACTS = ["alternative", "sopnet/geo", "isInsideLockedHDA", "karmamaterial"]

# Queries F-CRUX-1 reported as failing. Measured lexical ranks against the shipped
# corpus: componentgeometry -> 2, "component builder internals" -> 1.
_QUERIES = ["componentgeometry", "component builder internals"]

_HAS_ST = importlib.util.find_spec("sentence_transformers") is not None


# --------------------------------------------------------------------------- #
#  Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def scout_state():
    """Snapshot + restore scout module globals so pointing it at a tmp store never
    leaks into other tests (mirrors test_scout_node_dense's _point discipline)."""
    saved = (scout.RAG_ROOT, scout.VEX_ROOT, scout.EXPECTED_HOUDINI_VERSION)

    def _clear():
        for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
            c.clear()

    _clear()
    yield
    scout.RAG_ROOT, scout.VEX_ROOT, scout.EXPECTED_HOUDINI_VERSION = saved
    _clear()


def _point(store_root: Path):
    scout.RAG_ROOT = Path(store_root)
    scout.VEX_ROOT = Path(store_root)
    for c in (scout._CORPUS, scout._FTS, scout._DENSE, scout._SYMS, scout._TABLE_CACHE):
        c.clear()


def _real_anatomy_md() -> Path:
    return scout_ingest.rag_source() / "skills" / "houdini21-reference" / (ANATOMY_ID + ".md")


def _build_lexical_only(rag_root: Path, out_root: Path, monkeypatch):
    """Build the corpus on the dense-less path: skip the (torch-heavy) node-dense
    derivation and remove any copied semantic index, so scout reports
    mode="lexical_only" deterministically regardless of whether sentence-transformers
    is installed. The lexical path is dependency-free by design, so this tier is the
    CI-robust guard."""
    monkeypatch.setattr(scout_ingest, "_build_node_semantic_index", lambda *a, **k: None)
    scout_ingest.build_corpus(rag_root=str(rag_root), out_root=str(out_root))
    shutil.rmtree(out_root / "semantic_index", ignore_errors=True)
    shutil.rmtree(out_root / scout_ingest.NODE_INDEX_DIRNAME, ignore_errors=True)


def _make_rag_with_anatomy(root: Path) -> Path:
    """A hermetic rag/ carrying the REAL anatomy .md content next to a competing
    componentgeometry node datasheet — the exact F-CRUX-1 scenario (does the prose
    doc surface ALONGSIDE the node the query names)."""
    anatomy = _real_anatomy_md()
    if not anatomy.is_file():
        pytest.skip(f"anatomy source doc absent: {anatomy}")

    ref = root / "skills" / "houdini21-reference"
    ref.mkdir(parents=True)
    # the REAL doc content — pins the shipped text's retrievability, not a paraphrase
    (ref / (ANATOMY_ID + ".md")).write_text(anatomy.read_text(encoding="utf-8"), encoding="utf-8")
    # a distractor prose doc so BM25 has real competition
    (ref / "solaris_variants.md").write_text(
        "# Solaris Variants\ncomponent variants geo variant material variant explore.",
        encoding="utf-8")

    meta = root / "documentation" / "_metadata"
    meta.mkdir(parents=True)
    (meta / "semantic_index.json").write_text("{}", encoding="utf-8")

    corpus = root / "corpus"
    corpus.mkdir()
    node = {
        "id": "h22:lop/componentgeometry", "type": "componentgeometry", "context": "lop",
        "searchable_text": "Component Geometry (componentgeometry)\ncomponentgeometry node "
                           "- lop context\nAuthors SOP geometry for a USD component.",
    }
    (corpus / "nodes.json").write_text(
        json.dumps({"schema": "h22_node_corpus/v1", "build": "22.0.400", "entries": [node]}),
        encoding="utf-8")
    return root


def _assert_facts_in_backing(store):
    _, by_id = scout._load_corpus(store)
    # Directly refutes F-CRUX-1's "NO rag/corpus/ backing entry".
    assert ANATOMY_ID in by_id, "anatomy .md must materialize a corpus entry (F-CRUX-1 refutation)"
    text = by_id[ANATOMY_ID]["searchable_text"]
    for fact in _H22_FACTS:
        assert fact in text, f"H22 fact {fact!r} missing from retrievable anatomy text"
    return by_id


# --------------------------------------------------------------------------- #
#  Lexical tier — always runs                                                  #
# --------------------------------------------------------------------------- #
def test_anatomy_has_corpus_backing_and_h22_facts(tmp_path, monkeypatch, scout_state):
    rag = _make_rag_with_anatomy(tmp_path / "rag")
    _build_lexical_only(rag, tmp_path / "store", monkeypatch)
    _point(tmp_path / "store")
    _assert_facts_in_backing(scout._stores()[0])


def test_anatomy_surfaces_lexical(tmp_path, monkeypatch, scout_state):
    rag = _make_rag_with_anatomy(tmp_path / "rag")
    _build_lexical_only(rag, tmp_path / "store", monkeypatch)
    _point(tmp_path / "store")
    for q in _QUERIES:
        out = scout.synapse_scout(q, k=6)
        assert out["mode"] == "lexical_only"          # proves the torch-free path
        ids = [h["id"] for h in out["hits"]]
        assert ANATOMY_ID in ids, f"anatomy absent from scout({q!r}) hits: {ids}"


# --------------------------------------------------------------------------- #
#  Real-corpus tier — always runs (lexical, so no torch needed)               #
# --------------------------------------------------------------------------- #
def test_anatomy_surfaces_in_real_shipped_corpus(tmp_path, monkeypatch, scout_state):
    """The strongest guard: the REAL anatomy doc, competing inside the REAL shipped
    corpus (node datasheets + all 104 prose docs + sidefxlabs), surfaces for the
    real queries. This is the retrieval-coverage the wave certified."""
    rag = scout_ingest.rag_source()
    if not _real_anatomy_md().is_file():
        pytest.skip("real rag/ anatomy doc absent")
    _build_lexical_only(rag, tmp_path / "store", monkeypatch)
    _point(tmp_path / "store")
    _assert_facts_in_backing(scout._stores()[0])
    for q in _QUERIES:
        out = scout.synapse_scout(q, k=6)
        ids = [h["id"] for h in out["hits"]]
        assert ANATOMY_ID in ids, f"anatomy absent from real-corpus scout({q!r}): {ids}"


# --------------------------------------------------------------------------- #
#  Hybrid tier — production mode; skipped without sentence-transformers        #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _HAS_ST, reason="sentence-transformers absent -> lexical-only path")
def test_anatomy_surfaces_hybrid_real_corpus(tmp_path, monkeypatch, scout_state):
    """The live production mode: the copied prose dense index carries the anatomy
    embedding row AND the materialized corpus backs it, so the fused hit renders
    (it is NOT skipped as an orphan). Node-dense derivation is stubbed out for speed;
    the prose semantic index is kept so the dense path is real."""
    rag = scout_ingest.rag_source()
    if not _real_anatomy_md().is_file():
        pytest.skip("real rag/ anatomy doc absent")
    monkeypatch.setattr(scout_ingest, "_build_node_semantic_index", lambda *a, **k: None)
    scout_ingest.build_corpus(rag_root=str(rag), out_root=str(tmp_path / "store"))
    _point(tmp_path / "store")

    store = scout._stores()[0]
    loaded = scout._dense(store)
    if loaded is None:
        pytest.skip("embedder not constructible here -> no dense path to assert")
    _index, ids, _emb = loaded
    assert ANATOMY_ID in ids, "prose dense index must carry the anatomy embedding row"

    out = scout.synapse_scout("componentgeometry", k=6)
    assert out["mode"] in ("hybrid", "semantic_only")
    hit_ids = [h["id"] for h in out["hits"]]
    assert ANATOMY_ID in hit_ids, f"anatomy absent from hybrid scout: {hit_ids}"
