"""
synapse.cognitive.tools.scout
==============================

A federated, hybrid retrieval tool that scouts the Houdini 21.0.671
documentation RAG *and* the VEX corpus, returning real H21 reference
material the model can ground on BEFORE it writes code.

Placement:  python/synapse/cognitive/tools/scout.py
Contract:   pure Python, ZERO `hou` imports  (passes tests/test_cognitive_boundary.py)

Why this exists
---------------
SYNAPSE's #1 failure class is phantom APIs (`hou.pdg.*`, `hou.secure`,
`hou.lopNetworks()`). The model's priors for H21.0.671 are frequently wrong.
This tool is the runtime enforcement of the "`dir()` is a hard gate" rule:
the agent verifies an unfamiliar symbol against the *real* corpus instead of
emitting it and letting CRUCIBLE catch it after the fact.

Errors
------
``synapse_scout`` raises :class:`ScoutError` (a plain ``RuntimeError`` subclass).
The cognitive ``Dispatcher`` CATCHES tool exceptions and wraps them into a
JSON-serializable ``AgentToolError`` *value* (which is a frozen dataclass — it is
never raised). So a cognitive tool must RAISE a normal exception, not the
``AgentToolError`` value type; the dispatcher does the conversion.

Retrieval contract (no fabrication)
-----------------------------------
* LEXICAL path always works. It builds a BM25/FTS5 index straight from the
  corpus `searchable_text` using stdlib sqlite3 — no embedder, no heavy deps,
  identical behaviour in graphical H21.0.671 and headless hython 21.0.631
  (their site-packages differ; the lexical path is dependency-free on purpose).
* SEMANTIC path auto-enables IFF `<index_dir>/manifest.json` declares the
  embedder that built the index. The query is embedded with the SAME embedder
  (the cardinal RAG rule — mismatch = silent garbage). If no manifest is found,
  the tool reports `mode="lexical_only"` rather than guessing a vector space.
* When both are available they are fused with Reciprocal Rank Fusion (RRF).

Config seams (override via env, no code edit)
---------------------------------------------
* SYNAPSE_RAG_ROOT   default: G:\\HOUDINI21_RAG_SYSTEM   (corpus\\ + semantic_index\\)
* SYNAPSE_VEX_ROOT   default: == RAG_ROOT  -> VEX is the same store, distinguished
                     by entry `type` (e.g. "vex*"). Point it at a separate folder
                     if your VEX corpus is a distinct store.

NOTE (2026-06-08): the SYNAPSE knowledge-scaffold review found that
``G:\\HOUDINI21_RAG_SYSTEM`` is the thin SideFXLabs-only store and the CANONICAL
H21 corpus is the repo ``rag/`` tree (which ``routing/knowledge.py::KnowledgeIndex``
already defaults to). Set ``SYNAPSE_RAG_ROOT`` to the repo ``rag`` dir to scout the
canonical corpus; the default is left at G:\\ per the original contract.
"""

from __future__ import annotations

import os
import re
import json
import sqlite3
import hashlib
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable

# --------------------------------------------------------------------------- #
#  Optional dependency guards  (mirrors the _HOU_AVAILABLE / _PXR_AVAILABLE    #
#  idiom in bridge.py — never assume runtime pip, never hard-fail on absence)  #
# --------------------------------------------------------------------------- #
try:
    import numpy as np
    _NUMPY = True
except Exception:                       # pragma: no cover
    np = None                           # type: ignore
    _NUMPY = False

try:
    import faiss                        # type: ignore
    _FAISS = True
except Exception:                       # pragma: no cover
    faiss = None                        # type: ignore
    _FAISS = False


class ScoutError(RuntimeError):
    """Raised by :func:`synapse_scout` on any unrecoverable retrieval problem.

    A plain exception ON PURPOSE: the cognitive ``Dispatcher`` catches it and
    wraps it into an ``AgentToolError`` value (the dataclass return-type, which
    is never raised). Raising the dataclass directly would ``TypeError``."""


# --------------------------------------------------------------------------- #
#  Config                                                                      #
# --------------------------------------------------------------------------- #
RAG_ROOT = Path(os.environ.get("SYNAPSE_RAG_ROOT", r"G:\HOUDINI21_RAG_SYSTEM"))
VEX_ROOT = Path(os.environ.get("SYNAPSE_VEX_ROOT", str(RAG_ROOT)))

# Drift policy (Spike 1): a corpus is a CACHE derived from rag/ — caches drift,
# and a drifted grounding corpus produces FALSE phantoms (flags a now-real API as
# fake), which is worse than no gate. At load scout recomputes the rag/ digest and
# compares it to the corpus manifest. The default is FAIL-CLOSED: when an H22
# build makes the symbol table / corpus stale the phantom-API gate REFUSES
# (raises) rather than silently disarm — a disarmed gate is the #1 failure class.
#   "refuse" (default) — raise ScoutError on drift (fail-closed phantom gate).
#   "warn"             — surface stale:true + a warning line; still return hits
#                        (explicit opt-in to graceful degradation, e.g. mid-upgrade).
# A missing/corrupt manifest reads as STALE, never silently fresh (invariant 1).
DRIFT_POLICY = os.environ.get("SYNAPSE_SCOUT_DRIFT_POLICY", "refuse").lower().strip()
CORPUS_MANIFEST_NAME = "manifest.json"   # store-root manifest (NOT semantic_index/manifest.json)

# Symbol-table membership authority (Spike 2.5). EXISTENCE is a `dir()` question
# against the live H21.0.671 runtime — NOT a substring-in-prose question. The
# introspected table (host/introspect_runtime.py) is the SOLE membership verdict;
# corpus presence is demoted to a `documented` retrieval hint.
SYMBOL_TABLE_NAME = "symbol_table.json"  # optional store-root override
# Committed package authority — travels to CI / headless / hython 631 where `hou`
# and the gitignored .synapse store are both absent.
_PKG_SYMBOL_TABLE = Path(__file__).resolve().parent / "data" / "h21_symbol_table.json"
# Host-injected running Houdini version (mcp_server sets it when hou is importable).
# When set, a table whose stamp != this version reads STALE (never silent-valid).
EXPECTED_HOUDINI_VERSION: Optional[str] = None

TEXT_FIELD = "searchable_text"          # per corpus entry schema: id, type, source, searchable_text
RRF_K = 60                              # standard RRF damping constant
DEFAULT_K = 6
DEFAULT_MAX_CHARS = 480

# Dotted Python API symbols — exactly the phantom-API class SYNAPSE cares about.
_DOTTED_RE = re.compile(r"\b(?:hou|pdg|hdefereval|pxr(?:\.\w+)?)\.[A-Za-z_][\w.]*")


@dataclass(frozen=True)
class Store:
    """A physical corpus + index pair. `fixed_domain=None` means one store holds
    both docs and VEX, distinguished by entry `type`."""
    corpus_dir: Path
    index_dir: Path
    fixed_domain: Optional[str]         # "docs" | "vex" | None


def _stores() -> list[Store]:
    if VEX_ROOT.resolve() == RAG_ROOT.resolve():
        # Single store holds everything; classify by entry type at result time.
        return [Store(RAG_ROOT / "corpus", RAG_ROOT / "semantic_index", None)]
    return [
        Store(RAG_ROOT / "corpus", RAG_ROOT / "semantic_index", "docs"),
        Store(VEX_ROOT / "corpus", VEX_ROOT / "semantic_index", "vex"),
    ]


def _classify(entry: dict, store: Store) -> str:
    if store.fixed_domain:
        return store.fixed_domain
    return "vex" if "vex" in str(entry.get("type", "")).lower() else "docs"


# --------------------------------------------------------------------------- #
#  Embedder seam  (resolved from the index manifest; never hardcoded)          #
# --------------------------------------------------------------------------- #
@runtime_checkable
class Embedder(Protocol):
    dim: int
    def encode(self, text: str) -> "list[float]": ...


class SentenceTransformerEmbedder:
    """Reference local embedder. Only loaded if the manifest names it AND the
    dependency is importable in this interpreter."""
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # guarded: optional
        self._m = SentenceTransformer(model_name)
        self.dim = int(self._m.get_sentence_embedding_dimension())

    def encode(self, text: str) -> list[float]:
        v = self._m.encode([text], normalize_embeddings=True)[0]
        return [float(x) for x in v]


# Map manifest "embedder" name -> factory. Add API/Voyage/Cohere adapters here
# if your index was built with a hosted embedder (they'd need network + key env).
EMBEDDERS: dict[str, Callable[[dict], Embedder]] = {
    "sentence-transformers": lambda cfg: SentenceTransformerEmbedder(cfg["model"]),
}


def _load_embedder(index_dir: Path) -> Optional[Embedder]:
    """Return the embedder that BUILT this index, per its manifest. None means
    'no semantic path' -> the tool degrades to lexical_only and says so."""
    manifest = index_dir / "manifest.json"
    if not manifest.is_file():
        return None
    cfg = json.loads(manifest.read_text(encoding="utf-8"))
    name = cfg.get("embedder")
    if name not in EMBEDDERS:
        # Manifest exists but names an embedder we can't construct — surface it
        # rather than silently dropping to lexical and pretending all is well.
        raise ScoutError(
            f"[scout] index manifest names embedder '{name}' which is not registered "
            f"in EMBEDDERS. Add an adapter or fix the manifest at {manifest}."
        )
    try:
        return EMBEDDERS[name](cfg)
    except ImportError as e:             # dep not in THIS interpreter's site-packages
        # Common + expected (e.g. torch absent in hython). Degrade loudly.
        _WARN.append(f"semantic path disabled: {name} dependency unavailable ({e}).")
        return None


# --------------------------------------------------------------------------- #
#  Caches  (load corpus / build FTS / load vectors ONCE per store)             #
# --------------------------------------------------------------------------- #
_CORPUS: dict[str, tuple[list[dict], dict[str, dict]]] = {}
_FTS: dict[str, sqlite3.Connection] = {}
_DENSE: dict[str, tuple[Any, list[str], Embedder]] = {}
_SYMS: dict[str, set[str]] = {}
_TABLE_CACHE: dict[str, dict] = {}       # path -> read-once {symbols|None, meta, stale, reason}
_WARN: list[str] = []                    # per-call warnings; reset at entry


def _stable_key(paths: list[Path]) -> str:
    """BLAKE2b over file (size, mtime) — stable across process restarts, unlike
    builtin hash() which is PYTHONHASHSEED-salted."""
    h = hashlib.blake2b(digest_size=12)
    for p in sorted(paths):
        try:
            st = p.stat()
            h.update(f"{p}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8"))
        except OSError:
            h.update(f"{p}|missing".encode("utf-8"))
    return h.hexdigest()


def _load_corpus(store: Store) -> tuple[list[dict], dict[str, dict]]:
    key = str(store.corpus_dir)
    if key in _CORPUS:
        return _CORPUS[key]
    if not store.corpus_dir.is_dir():
        raise ScoutError(f"[scout] corpus dir not found: {store.corpus_dir}")

    entries: list[dict] = []
    for fp in sorted(store.corpus_dir.rglob("*")):
        if fp.suffix.lower() == ".jsonl":
            for line in fp.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        elif fp.suffix.lower() == ".json":
            obj = json.loads(fp.read_text(encoding="utf-8"))
            entries.extend(obj if isinstance(obj, list) else obj.get("entries", []))

    if not entries:
        raise ScoutError(
            f"[scout] no corpus entries under {store.corpus_dir} "
            f"(expected *.json / *.jsonl with a '{TEXT_FIELD}' field)."
        )
    # Synthesize ids if absent so RRF + dedup have a stable key.
    by_id: dict[str, dict] = {}
    for i, e in enumerate(entries):
        eid = str(e.get("id") or f"{store.corpus_dir.name}:{i}")
        e["id"] = eid
        by_id[eid] = e
    _CORPUS[key] = (entries, by_id)
    return _CORPUS[key]


def _fts(store: Store) -> sqlite3.Connection:
    """BM25/FTS5 index built from corpus searchable_text. Cached on disk so the
    build cost is paid once."""
    key = str(store.corpus_dir)
    if key in _FTS:
        return _FTS[key]
    entries, _ = _load_corpus(store)

    cache_dir = Path(tempfile.gettempdir()) / "synapse_scout"
    cache_dir.mkdir(exist_ok=True)
    db_path = cache_dir / f"fts_{_stable_key(list(store.corpus_dir.rglob('*')))}.db"

    con = sqlite3.connect(str(db_path))
    have = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'"
    ).fetchone()
    if not have:
        con.execute(
            "CREATE VIRTUAL TABLE chunks USING fts5("
            "id UNINDEXED, type UNINDEXED, source UNINDEXED, body, "
            "tokenize='porter unicode61')"
        )
        con.executemany(
            "INSERT INTO chunks(id, type, source, body) VALUES (?,?,?,?)",
            [(e["id"], str(e.get("type", "")), str(e.get("source", "")),
              str(e.get(TEXT_FIELD, ""))) for e in entries],
        )
        con.commit()
    _FTS[key] = con
    return con


def _lexical_ids(store: Store, query: str, k: int) -> list[str]:
    """Ranked entry ids from BM25. FTS5 bm25() is lower=better -> ORDER BY asc."""
    con = _fts(store)
    match = _fts5_query(query)
    if not match:
        return []
    try:
        rows = con.execute(
            "SELECT id FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ?",
            (match, k),
        ).fetchall()
    except sqlite3.OperationalError:
        return []                        # malformed match expr -> no lexical hits
    return [r[0] for r in rows]


def _fts5_query(query: str) -> str:
    """Turn free text into a safe FTS5 OR-query of bare tokens."""
    toks = re.findall(r"[A-Za-z0-9_]+", query)
    toks = [t for t in toks if len(t) > 1][:24]
    return " OR ".join(toks)


def _dense(store: Store) -> Optional[tuple[Any, list[str], Embedder]]:
    """Load the semantic index + its embedder. None -> no semantic path.
    Supports FAISS (index.faiss + meta.jsonl) and a numpy matrix
    (embeddings.npy + meta.jsonl). Override paths via the manifest if yours
    differ."""
    key = str(store.index_dir)
    if key in _DENSE:
        return _DENSE[key]
    if not store.index_dir.is_dir():
        return None
    embedder = _load_embedder(store.index_dir)
    if embedder is None:
        return None

    meta_fp = store.index_dir / "meta.jsonl"
    if not meta_fp.is_file():
        _WARN.append(f"semantic path disabled: no meta.jsonl in {store.index_dir}.")
        return None
    ids = [json.loads(l)["id"] for l in meta_fp.read_text(encoding="utf-8").splitlines() if l.strip()]

    faiss_fp = next(iter(store.index_dir.glob("*.faiss")), None)
    npy_fp = store.index_dir / "embeddings.npy"

    if faiss_fp and _FAISS:
        index = faiss.read_index(str(faiss_fp))
    elif npy_fp.is_file() and _NUMPY:
        index = np.load(str(npy_fp)).astype("float32")   # (N, dim)
    else:
        _WARN.append("semantic path disabled: no usable vector store (need faiss+*.faiss or numpy+embeddings.npy).")
        return None

    if len(ids) and hasattr(index, "shape") and index.shape[0] != len(ids):
        raise ScoutError(
            f"[scout] index/meta length mismatch in {store.index_dir}: "
            f"{index.shape[0]} vectors vs {len(ids)} ids."
        )
    _DENSE[key] = (index, ids, embedder)
    return _DENSE[key]


def _dense_ids(store: Store, query: str, k: int) -> Optional[list[str]]:
    loaded = _dense(store)
    if loaded is None:
        return None
    index, ids, embedder = loaded
    q = embedder.encode(query)
    if len(q) != embedder.dim:           # query-side embedding sanity guard
        raise ScoutError(
            f"[scout] query embedding dim {len(q)} != index dim {embedder.dim}."
        )
    if _FAISS and isinstance(index, faiss.Index):
        import numpy as _np
        D, I = index.search(_np.array([q], dtype="float32"), k)
        return [ids[i] for i in I[0] if 0 <= i < len(ids)]
    # numpy brute-force cosine (vectors assumed L2-normalized at build time)
    qv = np.array(q, dtype="float32")
    sims = index @ qv
    top = np.argsort(-sims)[:k]
    return [ids[i] for i in top]


# --------------------------------------------------------------------------- #
#  Fusion + symbol grounding                                                   #
# --------------------------------------------------------------------------- #
def _rrf(ranked_lists: list[list[str]], k: int = RRF_K) -> list[str]:
    score: dict[str, float] = {}
    for rl in ranked_lists:
        for rank, _id in enumerate(rl, start=1):
            score[_id] = score.get(_id, 0.0) + 1.0 / (k + rank)
    return sorted(score, key=lambda i: score[i], reverse=True)


def _corpus_symbols(store: Store) -> set[str]:
    key = str(store.corpus_dir)
    if key in _SYMS:
        return _SYMS[key]
    entries, _ = _load_corpus(store)
    syms: set[str] = set()
    for e in entries:
        syms.update(_DOTTED_RE.findall(str(e.get(TEXT_FIELD, ""))))
    _SYMS[key] = syms
    return syms


def _symbol_table_path() -> Path:
    """Store-root override (spec: 'in the canonical store, alongside the corpus')
    wins; else the committed package authority."""
    override = RAG_ROOT / SYMBOL_TABLE_NAME
    return override if override.is_file() else _PKG_SYMBOL_TABLE


def _read_symbol_table(path: Path) -> dict:
    """Read + integrity-check the table file. Missing/corrupt reads STALE with
    symbols=None — never a silent-valid empty table (invariant: 'fails loud')."""
    if not path.is_file():
        return {"symbols": None, "meta": {}, "stale": True,
                "reason": f"no symbol table at {path}"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        symbols = raw["symbols"]
        recorded = raw["blake2b"]
    except (json.JSONDecodeError, OSError, KeyError, TypeError) as e:
        return {"symbols": None, "meta": {}, "stale": True,
                "reason": f"symbol table unreadable/malformed: {e}"}
    digest = hashlib.blake2b("\n".join(sorted(symbols)).encode("utf-8"),
                             digest_size=16).hexdigest()
    if digest != recorded:
        return {"symbols": None, "meta": raw, "stale": True,
                "reason": "symbol table checksum mismatch (corrupt)"}
    return {"symbols": set(symbols), "meta": raw, "stale": False, "reason": None}


def _load_symbol_table() -> tuple[Optional[set[str]], dict]:
    """Return (symbols | None, status). The file read is cached; the host version
    match is recomputed each call (EXPECTED_HOUDINI_VERSION is live host state).
    A version-mismatched table is NOT trusted as authority (symbols -> None)."""
    path = _symbol_table_path()
    key = str(path)
    if key not in _TABLE_CACHE:
        _TABLE_CACHE[key] = _read_symbol_table(path)
    rec = _TABLE_CACHE[key]
    syms, meta = rec["symbols"], rec["meta"]
    status = {"loaded": syms is not None, "path": key,
              "houdini_version": meta.get("houdini_version"),
              "stale": rec["stale"], "reason": rec["reason"]}
    if syms is not None and EXPECTED_HOUDINI_VERSION and \
            meta.get("houdini_version") != EXPECTED_HOUDINI_VERSION:
        status.update(stale=True, loaded=False,
                      reason=(f"table stamp {meta.get('houdini_version')} != running "
                              f"{EXPECTED_HOUDINI_VERSION}"))
        return None, status
    return syms, status


def _ground_symbols(query: str, stores: list[Store],
                    table_syms: Optional[set[str]],
                    table_reason: Optional[str] = None) -> list[dict]:
    """For each dotted API symbol in the query report:
      exists_in_runtime — the MEMBERSHIP VERDICT from the introspected table
                          (True/False; None when no trustworthy table is loaded).
      documented        — secondary hint: does it appear verbatim in the corpus?
    Existence is the table's call, not the corpus's — that demotion IS the fix."""
    wanted = sorted(set(_DOTTED_RE.findall(query)))
    if not wanted:
        return []
    universe: set[str] = set()
    for s in stores:
        try:
            universe |= _corpus_symbols(s)
        except ScoutError:
            # A missing/empty store can't supply the documented hint; skip it
            # rather than fail the whole scout (the hits path surfaced it).
            continue
    out = []
    for sym in wanted:
        entry = {"symbol": sym,
                 "exists_in_runtime": (sym in table_syms) if table_syms is not None else None,
                 "documented": sym in universe}
        if table_syms is None:
            # A None verdict must say WHY at point of use (truth contract)
            entry["unverified_reason"] = table_reason or "no trustworthy symbol table loaded"
        out.append(entry)
    return out


# --------------------------------------------------------------------------- #
#  Corpus freshness  (Spike 1 — the Floor: the map must match the building)    #
# --------------------------------------------------------------------------- #
def _freshness_for(store_root: Path) -> Optional[dict]:
    """Verify the corpus at ``store_root`` still matches its rag/ source.

    Returns None when no corpus is present at this root (nothing to verify here).
    Otherwise ``{"stale": bool, "reason": str|None}``. A missing/corrupt manifest,
    or a source that can no longer be digested, reads as STALE — never silently
    fresh (invariant 1). Recomputed every call (never cached) so a mid-process
    mutation of rag/ is caught live.
    """
    corpus_fp = store_root / "corpus" / "entries.jsonl"
    if not corpus_fp.is_file():
        return None                       # no corpus here — the hits path will surface that

    manifest_fp = store_root / CORPUS_MANIFEST_NAME
    if not manifest_fp.is_file():
        return {"stale": True, "reason": f"no corpus manifest at {manifest_fp} "
                                         "(unverifiable provenance)"}
    try:
        manifest = json.loads(manifest_fp.read_text(encoding="utf-8"))
        recorded = manifest["source_digest"]
        source_root = Path(manifest["source_root"])
    except (json.JSONDecodeError, OSError, KeyError, TypeError) as e:
        return {"stale": True, "reason": f"corpus manifest unreadable/malformed: {e}"}

    if not source_root.exists():
        return {"stale": True, "reason": f"rag/ source {source_root} is gone "
                                         "(cannot confirm freshness)"}

    from synapse.cognitive.tools import scout_ingest   # lazy: avoid import cycle
    current = scout_ingest.source_digest(source_root)
    if current != recorded:
        return {"stale": True, "reason": f"rag/ source changed since ingest "
                                         f"(manifest {recorded[:12]}… != live {current[:12]}…)"}
    return {"stale": False, "reason": None}


def _check_freshness(stores: list[Store]) -> bool:
    """Check every unique store root; surface staleness per DRIFT_POLICY.
    Returns True if ANY checked store is stale. In 'refuse' mode, raises on the
    first stale store instead of returning."""
    stale = False
    for root in sorted({s.corpus_dir.parent for s in stores}):
        verdict = _freshness_for(root)
        if verdict is None or not verdict["stale"]:
            continue
        stale = True
        msg = f"[scout] corpus STALE: {verdict['reason']}"
        if DRIFT_POLICY == "refuse":
            raise ScoutError(msg + " — SYNAPSE_SCOUT_DRIFT_POLICY=refuse")
        _WARN.append(msg)
    return stale


# --------------------------------------------------------------------------- #
#  The tool                                                                    #
# --------------------------------------------------------------------------- #
def synapse_scout(
    query: str,
    domain: str = "both",
    k: int = DEFAULT_K,
    max_chars: int = DEFAULT_MAX_CHARS,
    where: Optional[dict] = None,
) -> dict:
    """Scout the H21 docs RAG and the VEX corpus for grounding material.

    Args:
        query:      natural-language need OR an API/VEX signature to verify.
        domain:     "docs" | "vex" | "both"  (default "both").
        k:          max hits to return.
        max_chars:  snippet truncation per hit (token economy).
        where:      optional post-filter, e.g. {"type": "vex_function",
                    "source_contains": "sidefxlabs"}.

    Returns a JSON-serializable dict:
        {
          "query", "mode" ("hybrid" | "semantic_only" | "lexical_only"),
          "domain", "stale" (corpus drifted from its rag/ source — Spike 1),
          "table": {loaded, houdini_version, stale, reason},  # membership authority
          "hits": [{id, domain, type, source, score, snippet}],
          "symbols": [{symbol, exists_in_runtime, documented}],   # membership + doc hint
          "warnings": [...]
        }
    """
    _WARN.clear()
    domain = domain.lower().strip()
    if domain not in ("docs", "vex", "both"):
        raise ScoutError(f"[scout] domain must be docs|vex|both, got '{domain}'.")
    if not query or not query.strip():
        raise ScoutError("[scout] query is empty.")

    stores = _stores()
    stale = _check_freshness(stores)     # Floor: surface corpus drift before grounding (Spike 1)

    # Membership authority (Spike 2.5): load the introspected symbol table. A
    # missing/corrupt/version-mismatched table fails loud — never silent-valid.
    table_syms, table_status = _load_symbol_table()
    if table_status["stale"]:
        msg = f"[scout] symbol table unavailable: {table_status['reason']} — membership unverified"
        if DRIFT_POLICY == "refuse":
            raise ScoutError(msg + " — SYNAPSE_SCOUT_DRIFT_POLICY=refuse")
        _WARN.append(msg)

    fanout = max(k * 4, 20)              # retrieve wide, fuse, then trim to k
    per_retriever: list[list[str]] = []
    id_meta: dict[str, tuple[Store, dict]] = {}
    used_dense = False
    used_lexical = False

    for store in stores:
        _, by_id = _load_corpus(store)

        lex = _lexical_ids(store, query, fanout)
        if lex:
            used_lexical = True
            per_retriever.append(lex)

        den = _dense_ids(store, query, fanout)
        if den is not None:
            used_dense = True
            per_retriever.append(den)

        for _id in set(lex) | set(den or []):
            if _id in by_id:
                id_meta[_id] = (store, by_id[_id])

    fused = _rrf(per_retriever) if per_retriever else []

    hits: list[dict] = []
    for rank, _id in enumerate(fused):
        store, entry = id_meta[_id]
        dom = _classify(entry, store)
        if domain != "both" and dom != domain:
            continue
        if where and not _passes(entry, where):
            continue
        hits.append({
            "id": _id,
            "domain": dom,
            "type": entry.get("type", ""),
            "source": entry.get("source", ""),
            "score": round(1.0 / (rank + 1), 4),   # fused rank -> [0,1]
            "snippet": str(entry.get(TEXT_FIELD, ""))[:max_chars].strip(),
        })
        if len(hits) >= k:
            break

    mode = ("hybrid" if used_dense and used_lexical
            else "semantic_only" if used_dense
            else "lexical_only")
    if mode == "lexical_only":
        _WARN.append("No embedder declared — add semantic_index/manifest.json "
                     "to enable semantic retrieval.")

    return {
        "query": query,
        "mode": mode,
        "domain": domain,
        "stale": stale,                  # Spike 1: corpus drifted from its rag/ source
        "gate_armed": table_syms is not None,  # Spike 2.5 membership authority loaded+trusted (NOT the corpus 'stale' axis)
        "table": table_status,           # Spike 2.5: symbol-table membership authority status
        "hits": hits,
        "symbols": _ground_symbols(query, stores, table_syms, table_status.get("reason")),
        "warnings": list(_WARN),
    }


def _passes(entry: dict, where: dict) -> bool:
    if "type" in where and str(entry.get("type", "")) != where["type"]:
        return False
    if "source_contains" in where and where["source_contains"] not in str(entry.get("source", "")):
        return False
    return True


# --------------------------------------------------------------------------- #
#  Registration  (your documented 3-step port pattern)                         #
# --------------------------------------------------------------------------- #
SYNAPSE_SCOUT_SCHEMA: dict = {
    "name": "synapse_scout",
    "description": (
        "Scout the Houdini 21.0.671 documentation RAG and the VEX corpus for real "
        "reference material. CALL THIS BEFORE writing any unfamiliar hou.* / pdg.* / "
        "pxr.* call or VEX function — it returns grounding snippets AND, for each API "
        "symbol in your query, whether it exists in the live H21.0.671 runtime "
        "(checked against an introspected dir() symbol table, the membership authority). "
        "A symbol with exists_in_runtime=false does NOT exist in H21.0.671 and must not "
        "be used; exists_in_runtime=true is real even if undocumented. The 'documented' "
        "flag is a secondary hint (does the corpus mention it). "
        "Prefer the returned snippets over your own recall of the Houdini API. "
        "If exists_in_runtime is null the gate is DOWN (missing/corrupt/build-"
        "mismatched symbol table -- result.table.reason and each symbol's "
        "unverified_reason say why, gate_armed=false): treat the symbol as "
        "UNVERIFIED, do not emit it on memory alone, and regenerate the table "
        "per docs/studio/UPGRADE.md."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string",
                      "description": "Natural-language need, or an API/VEX signature to verify."},
            "domain": {"type": "string", "enum": ["docs", "vex", "both"], "default": "both"},
            "k": {"type": "integer", "default": DEFAULT_K, "minimum": 1, "maximum": 25},
            "max_chars": {"type": "integer", "default": DEFAULT_MAX_CHARS},
            "where": {"type": "object",
                      "description": "Optional filter: {type, source_contains}."},
        },
        "required": ["query"],
    },
}


def register(register_fn: Callable[..., Any]) -> None:
    """Step 2 of the port: register fn + schema with the cognitive Dispatcher.

    ``Dispatcher.register`` takes ``schema`` as a KEYWORD-ONLY arg
    (``register(tool_name, fn, *, schema=None)``), so pass it by keyword. Step 3
    is the mcp_server.py branch:  ``dispatcher.execute('synapse_scout', kwargs)``."""
    register_fn(SYNAPSE_SCOUT_SCHEMA["name"], synapse_scout, schema=SYNAPSE_SCOUT_SCHEMA)


# --------------------------------------------------------------------------- #
#  Standalone smoke test  (runs in CI / outside Houdini)                       #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":             # pragma: no cover
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "create a pyro burst with sparse pyro"
    # sys.stdout.write, not print() — the project bans bare print() in synapse/
    # source (tests/test_v5_features.py::test_no_print_in_source).
    try:
        out = synapse_scout(q, domain="both", k=5)
    except ScoutError as e:
        sys.stdout.write(f"SCOUT ERROR: {e}\n")
        sys.exit(1)
    sys.stdout.write(f"mode={out['mode']}  hits={len(out['hits'])}  warnings={out['warnings']}\n")
    for h in out["hits"]:
        sys.stdout.write(f"  [{h['domain']}/{h['type']}] {h['source']}  ({h['score']})\n")
        sys.stdout.write(f"    {h['snippet'][:120]}...\n")
    if out["symbols"]:
        sys.stdout.write("symbol grounding:\n")
        for s in out["symbols"]:
            _v = s["exists_in_runtime"]
            flag = "OK " if _v else ("UNVERIFIED" if _v is None else "PHANTOM?")
            doc = "doc" if s["documented"] else "undoc"
            sys.stdout.write(f"  {flag} [{doc}] {s['symbol']}\n")
