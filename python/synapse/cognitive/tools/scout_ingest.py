"""
synapse.cognitive.tools.scout_ingest
=====================================

Build scout's lexical corpus from the CANONICAL repo ``rag/`` tree — the source
``routing.knowledge.KnowledgeIndex`` already defaults to (NOT G:, which the
knowledge-scaffold review found thin/stale).

Reuses KnowledgeIndex's reader (no second markdown parser): its
``_reference_files`` (the ``skills/houdini21-reference/*.md`` — raw content, so
``hou.*``/``pdg.*``/``pxr.*`` tokens and VEX signatures survive VERBATIM) plus
``_semantic_index`` (keyword/summary enrichment so keyword queries hit). Maps each
reference file to scout's ``{id, type, source, searchable_text}`` and writes
``corpus/*.jsonl`` at a fresh, gitignored store.

LEXICAL + phantom-grounding ONLY. The semantic path is out of scope (blocked on the
embedder manifest — the ``semantic_index`` probe). The store has an empty
``semantic_index/`` so scout reports ``mode="lexical_only"`` honestly.

Contract: pure Python, ZERO ``hou`` (passes tests/test_cognitive_boundary.py).
``KnowledgeIndex`` is host-agnostic (file + keyword logic, no hou).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

# Store-root corpus manifest — records the BLAKE2b digest of the rag/ source the
# corpus was built from, so scout can detect drift at load (Spike 1). This is a
# DIFFERENT file from semantic_index/manifest.json (which declares the embedder,
# Spike 3); they never collide because they live in different dirs.
CORPUS_MANIFEST_NAME = "manifest.json"
MANIFEST_SCHEMA = "scout_corpus_manifest/v1"


def _repo_root() -> Path:
    # .../python/synapse/cognitive/tools/scout_ingest.py
    #   parents: [0]=tools [1]=cognitive [2]=synapse [3]=python [4]=repo-root
    return Path(__file__).resolve().parents[4]


def rag_source() -> Path:
    """The canonical repo rag/ tree (KnowledgeIndex's default source)."""
    return _repo_root() / "rag"


def corpus_root() -> Path:
    """Fresh, gitignored store (sibling of .synapse/ledger) — never overwrites G:'s
    corpus/ nor the rag/ source markdown."""
    return _repo_root() / ".synapse" / "scout_corpus"


def source_files(rag_root: Path) -> list[Path]:
    """Exactly the rag/ inputs that determine corpus content — what
    ``_entries_from_knowledge`` + ``_entries_from_corpus_dir`` consume: the
    reference .md tree, the semantic_index enrichment metadata, and any
    pre-built corpus/*.json|*.jsonl entry files (K.3 — e.g. migrated
    SideFXLabs param-schema entries). Digesting these *and only these* means
    mutating a real source file drifts the corpus, while touching an unrelated
    file under rag/ never raises a false-stale."""
    files: list[Path] = []
    ref_dir = rag_root / "skills" / "houdini21-reference"
    if ref_dir.is_dir():
        files.extend(sorted(ref_dir.glob("*.md")))
    sem = rag_root / "documentation" / "_metadata" / "semantic_index.json"
    if sem.is_file():
        files.append(sem)
    corpus_dir = rag_root / "corpus"
    if corpus_dir.is_dir():
        files.extend(sorted(corpus_dir.glob("*.json")))
        files.extend(sorted(corpus_dir.glob("*.jsonl")))
    return files


def source_digest(rag_root: Path) -> str:
    """BLAKE2b over (relative-path | size | mtime) of every source file —
    stable across process restarts (unlike PYTHONHASHSEED-salted ``hash()``).
    Relative paths keep it stable across checkout locations. A vanished file
    folds its absence into the digest, so deleting a source drifts too."""
    h = hashlib.blake2b(digest_size=16)
    for p in source_files(rag_root):
        try:
            st = p.stat()
            rel = p.relative_to(rag_root).as_posix()
            h.update(f"{rel}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8"))
        except OSError:
            h.update(f"{p}|missing".encode("utf-8"))
    return h.hexdigest()


def _entries_from_knowledge(rag_root: Path) -> list[dict]:
    """Map KnowledgeIndex's loaded reference files (+ topic enrichment) to scout
    entries. One entry per reference .md; searchable_text is the RAW content (+
    the keywords/summary of any topic that references it) so symbols stay verbatim."""
    from synapse.routing.knowledge import KnowledgeIndex
    idx = KnowledgeIndex(rag_root=str(rag_root))

    # reference-file stem -> enrichment text from topics that point at it.
    enrich: dict[str, list[str]] = {}
    for topic, data in (idx._semantic_index or {}).items():
        if not isinstance(data, dict):
            continue
        ref = str(data.get("reference_file") or "").rsplit(".md", 1)[0].strip()
        if not ref:
            continue
        summ = str(data.get("summary", "") or data.get("description", ""))
        kw = " ".join(data.get("keywords", []) or [])
        enrich.setdefault(ref, []).append(f"{topic} {summ} {kw}".strip())

    entries: list[dict] = []
    for stem, content in (idx._reference_files or {}).items():
        extra = " ".join(enrich.get(stem, []))
        body = content + ("\n" + extra if extra else "")
        entries.append({
            "id": stem,
            "type": "vex_reference" if "vex" in stem.lower() else "houdini21-reference",
            "source": f"{stem}.md",
            "searchable_text": body,
        })
    return entries


def _entries_from_corpus_dir(rag_root: Path) -> list[dict]:
    """Read any pre-built corpus/*.json|*.jsonl entry files under rag_root (K.3 —
    e.g. the migrated SideFXLabs param-schema entries, previously orphaned at
    G:\\HOUDINI21_RAG_SYSTEM\\semantic_index\\ where scout's loader never looked).

    Parses the same way scout.py's own _load_corpus does (list, or dict with an
    "entries" key) so a file written for one is readable by the other. Entries
    missing 'id' or 'searchable_text' are skipped, not fatal — a malformed extra
    corpus file must not take down the whole build (mirrors the malformed-
    semantic_index tolerance in build_corpus)."""
    corpus_dir = rag_root / "corpus"
    if not corpus_dir.is_dir():
        return []

    entries: list[dict] = []
    for fp in sorted(corpus_dir.glob("*.jsonl")) + sorted(corpus_dir.glob("*.json")):
        try:
            if fp.suffix == ".jsonl":
                raw = [json.loads(line) for line in fp.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                obj = json.loads(fp.read_text(encoding="utf-8"))
                raw = obj if isinstance(obj, list) else obj.get("entries", [])
        except (json.JSONDecodeError, OSError):
            continue
        for e in raw:
            if isinstance(e, dict) and e.get("id") and e.get("searchable_text"):
                entries.append(e)
    return entries


def _copy_semantic_index(rag_root: Path, sem_dir: Path) -> None:
    """Copy a pre-built semantic index (manifest.json + meta.jsonl + embeddings.npy
    and/or *.faiss) from ``rag_root/semantic_index/`` into the ephemeral store, if
    present. Built offline by ``scripts/build_semantic_index.py`` and committed to
    the repo — end users never need sentence-transformers installed just to GET a
    hybrid-mode corpus, only to query one that's already built. Absent source ->
    no-op, sem_dir stays empty, scout reports mode="lexical_only" (unchanged prior
    behavior; this function adds capability, it never removes the fallback)."""
    src = rag_root / "semantic_index"
    manifest = src / "manifest.json"
    if not manifest.is_file():
        return
    import shutil
    for name in ("manifest.json", "meta.jsonl"):
        fp = src / name
        if fp.is_file():
            shutil.copy2(fp, sem_dir / name)
    for fp in src.glob("*.faiss"):
        shutil.copy2(fp, sem_dir / fp.name)
    npy = src / "embeddings.npy"
    if npy.is_file():
        shutil.copy2(npy, sem_dir / "embeddings.npy")


def build_corpus(rag_root: Optional[str] = None, out_root: Optional[str] = None) -> dict:
    """Materialize the scout corpus from rag_root → out_root/corpus/entries.jsonl.

    Returns ``{entries, path, store_root}``. Raises if rag_root yields no entries
    (fail-loud — a silently-empty corpus is the bug this whole tool exists to avoid)."""
    src = Path(rag_root) if rag_root else rag_source()
    out = Path(out_root) if out_root else corpus_root()

    entries = _entries_from_knowledge(src) + _entries_from_corpus_dir(src)
    if not entries:
        raise RuntimeError(
            f"[scout_ingest] no entries from {src} — expected "
            f"{src / 'skills' / 'houdini21-reference'}/*.md (KnowledgeIndex source). "
            "Is the canonical rag/ tree present?"
        )

    corpus_dir = out / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    sem_dir = out / "semantic_index"
    sem_dir.mkdir(parents=True, exist_ok=True)  # empty → lexical_only unless populated below
    _copy_semantic_index(src, sem_dir)

    out_fp = corpus_dir / "entries.jsonl"
    out_fp.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
        encoding="utf-8",
    )

    # Freshness manifest (Spike 1): the BLAKE2b digest of the rag/ source this
    # corpus was built from. scout recomputes + compares at load to catch drift.
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "source_root": str(src),
        "source_digest": source_digest(src),
        "source_file_count": len(source_files(src)),
        "entries": len(entries),
    }
    (out / CORPUS_MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"entries": len(entries), "path": str(out_fp), "store_root": str(out)}


def _manifest_is_fresh(manifest_fp: Path, rag_root: Optional[str]) -> bool:
    """True iff the cached corpus manifest's recorded ``source_digest`` still
    matches the live digest of its rag/ source.

    A drifted source (e.g. an H21→H22 edit to the reference markdown) makes the
    cached corpus STALE. Serving it would trip scout's fail-closed drift gate
    (``DRIFT_POLICY=refuse`` raises; the default) and break retrieval on the
    headless/MCP path — so ``ensure_corpus`` must rebuild rather than return the
    stale store as ``cached``. Any read/parse error reads as NOT fresh (rebuild —
    fail toward a correct store, never silently serve unverifiable provenance)."""
    try:
        manifest = json.loads(manifest_fp.read_text(encoding="utf-8"))
        recorded = manifest["source_digest"]
        src = Path(rag_root) if rag_root else Path(manifest.get("source_root") or rag_source())
        return source_digest(src) == recorded
    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        return False


def ensure_corpus(rag_root: Optional[str] = None, out_root: Optional[str] = None) -> dict:
    """Build the corpus iff it is absent/empty/STALE (idempotent). The live wiring
    calls this before dispatch so scout never goes live empty — and never serves a
    corpus that has drifted from its rag/ source (which the refuse-policy gate would
    reject, degrading the headless/MCP path)."""
    out = Path(out_root) if out_root else corpus_root()
    fp = out / "corpus" / "entries.jsonl"
    # Rebuild if the corpus is absent/empty, predates the freshness manifest
    # (a manifest-less corpus has unverifiable provenance — scout would flag it
    # stale forever; rebuilding self-heals a pre-Spike-1 store on first use), OR
    # has drifted from its rag/ source (a stale store the drift gate would refuse).
    manifest_fp = out / CORPUS_MANIFEST_NAME
    if (fp.is_file() and fp.stat().st_size > 0 and manifest_fp.is_file()
            and _manifest_is_fresh(manifest_fp, rag_root)):
        return {"entries": -1, "path": str(fp), "store_root": str(out), "cached": True}
    return build_corpus(rag_root, out_root)


def activate(rag_root: Optional[str] = None, out_root: Optional[str] = None) -> dict:
    """Materialize the canonical repo ``rag/`` corpus (build-if-absent) and point
    the live ``scout`` module at it — the SAME sequence the MCP server runs at
    init (ensure_corpus → set roots → clear caches), factored here so the panel's
    "Corpus" button shares it verbatim and the two can't drift. Pure Python, zero
    ``hou``. Returns ``{loaded, store_root, entries, cached}``.

    NB: activates the canonical repo ``rag/`` (which carries the H21 Solaris docs
    in scout's ``searchable_text`` schema), NOT raw ``G:\\HOUDINI21_RAG_SYSTEM`` —
    G:'s ``corpus/`` has no ``searchable_text`` and would load hollow."""
    from synapse.cognitive.tools import scout as _scout
    info = ensure_corpus(rag_root, out_root)
    store_root = info["store_root"]
    _scout.RAG_ROOT = Path(store_root)
    _scout.VEX_ROOT = Path(store_root)
    for cache in (_scout._CORPUS, _scout._FTS, _scout._DENSE,
                  _scout._SYMS, _scout._TABLE_CACHE):
        cache.clear()
    return {"loaded": True, "store_root": store_root,
            "entries": info.get("entries", -1), "cached": info.get("cached", False)}


if __name__ == "__main__":             # pragma: no cover
    import sys
    res = build_corpus()
    sys.stdout.write(f"built {res['entries']} entries -> {res['path']}\n")
