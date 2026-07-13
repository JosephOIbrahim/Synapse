#!/usr/bin/env python3
"""Build the offline semantic (embedding) index for scout's dense-retrieval path.

Run this once, or after a meaningful rag/ content change, on a machine that has
sentence-transformers installed. The output is committed to rag/semantic_index/
so end users never need the embedding model installed just to GET hybrid-mode
retrieval — scout_ingest.build_corpus() copies these files into its ephemeral
store on every corpus rebuild, and scout.py's dense path picks them up
automatically. Absent/unreadable output -> scout silently stays lexical_only,
exactly today's behavior (no new fail-open surface).

Embeds the same {id, searchable_text} entries scout_ingest already derives from
KnowledgeIndex (python/synapse/routing/knowledge.py) — the SAME text the lexical
BM25 path indexes, and the SAME ids the lexical corpus uses, so dense and lexical
hits fuse against one consistent id space (scout.py's RRF fusion).

Known MVP limitation: one embedding per reference file (whole-file granularity,
truncated at the model's max sequence length for very long files), not
sub-file chunking. Good enough to catch paraphrased artist queries; a follow-up
can move to section-level chunking without changing this file's contract.

Usage:
    python scripts/build_semantic_index.py [--model all-MiniLM-L6-v2] [--rag-root rag]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "python"))


def embed_source_digest(rag_root: Path) -> str:
    """Content digest of everything that determines the embedded text: the
    reference .md tree + semantic_index.json (whose topic enrichment is folded
    into each entry's searchable_text by _entries_from_knowledge). Content-based
    (not mtime) so it is stable across checkouts and meaningful across edits.

    K.5 freshness invariant: build_semantic_index stamps this into manifest.json,
    and harness/verify/checks.py::check_semantic_index_fresh recomputes it with the
    IDENTICAL formula (pure file reads, no synapse/torch import) to detect a corpus
    that drifted from its committed vectors. If you change this formula, change the
    check in lockstep — a mismatch makes the gate read stale-forever or fresh-blind."""
    parts = []
    md_dir = rag_root / "skills" / "houdini21-reference"
    if md_dir.is_dir():
        for p in sorted(md_dir.glob("*.md"), key=lambda p: p.name):
            parts.append((p.name, hashlib.blake2b(p.read_bytes(), digest_size=16).hexdigest()))
    sem = rag_root / "documentation" / "_metadata" / "semantic_index.json"
    if sem.is_file():
        parts.append(("semantic_index.json",
                      hashlib.blake2b(sem.read_bytes(), digest_size=16).hexdigest()))
    blob = "\n".join(f"{name}:{h}" for name, h in parts)
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=16).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="all-MiniLM-L6-v2",
                         help="sentence-transformers model name (default: all-MiniLM-L6-v2)")
    parser.add_argument("--rag-root", default=str(REPO_ROOT / "rag"),
                         help="rag/ tree to embed (default: repo rag/)")
    args = parser.parse_args()

    rag_root = Path(args.rag_root)

    from synapse.cognitive.tools.scout_ingest import _entries_from_knowledge
    entries = _entries_from_knowledge(rag_root)
    if not entries:
        print(f"[build_semantic_index] no entries under {rag_root} — nothing to embed.",
              file=sys.stderr)
        return 1

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError as e:
        print(f"[build_semantic_index] missing dependency: {e}\n"
              f"  pip install -e .[semantic]", file=sys.stderr)
        return 1

    print(f"[build_semantic_index] loading {args.model}...")
    model = SentenceTransformer(args.model)
    dim = int(model.get_sentence_embedding_dimension())

    texts = [e["searchable_text"] for e in entries]
    print(f"[build_semantic_index] embedding {len(texts)} entries (dim={dim})...")
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    vectors = np.asarray(vectors, dtype="float32")
    assert vectors.shape == (len(entries), dim), (
        f"shape mismatch: got {vectors.shape}, expected ({len(entries)}, {dim})"
    )

    out_dir = rag_root / "semantic_index"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "manifest.json").write_text(
        json.dumps({
            "embedder": "sentence-transformers",
            "model": args.model,
            "dim": dim,
            "entries": len(entries),
            "normalized": True,
            # K.5: content digest of the embedded source — the freshness anchor.
            "content_digest": embed_source_digest(rag_root),
        }, indent=2),
        encoding="utf-8",
    )
    with open(out_dir / "meta.jsonl", "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps({"id": e["id"]}, ensure_ascii=False) + "\n")
    np.save(out_dir / "embeddings.npy", vectors)

    print(f"[build_semantic_index] wrote {len(entries)} embeddings -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
