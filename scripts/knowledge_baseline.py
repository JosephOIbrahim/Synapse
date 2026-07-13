#!/usr/bin/env python3
"""K.0 — snapshot current knowledge-corpus stats to harness/notes/knowledge_baseline.json.

Read-only probe: no dependency on hython or a running Houdini. Re-run any time to
refresh the baseline (each run overwrites with a freshly-computed digest — there
is no drift concept here, unlike the corpus's own BLAKE2b freshness gate against
rag/ source files; this is a point-in-time stats snapshot for the K-track's
check_knowledge_baseline_fresh gate).

Usage:
    python scripts/knowledge_baseline.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "python"))


def main() -> int:
    rag_root = REPO_ROOT / "rag"

    from synapse.cognitive.tools import scout_ingest

    ref_files = sorted((rag_root / "skills" / "houdini21-reference").glob("*.md"))
    md_entries = scout_ingest._entries_from_knowledge(rag_root)
    corpus_entries = scout_ingest._entries_from_corpus_dir(rag_root)

    sem_manifest_fp = rag_root / "semantic_index" / "manifest.json"
    semantic_built = sem_manifest_fp.is_file()
    semantic_model = None
    if semantic_built:
        try:
            semantic_model = json.loads(sem_manifest_fp.read_text(encoding="utf-8")).get("model")
        except (json.JSONDecodeError, OSError):
            semantic_built = False

    topic_map_fp = rag_root / "documentation" / "_metadata" / "semantic_index.json"
    lexical_topics = 0
    if topic_map_fp.is_file():
        try:
            raw = json.loads(topic_map_fp.read_text(encoding="utf-8"))
            topics = raw.get("semantic_index", {}).get("topics", raw) if isinstance(raw, dict) else {}
            lexical_topics = len(topics) if isinstance(topics, dict) else 0
        except (json.JSONDecodeError, OSError):
            pass

    scout_fp = REPO_ROOT / "python" / "synapse" / "cognitive" / "tools" / "scout.py"
    scout_src = scout_fp.read_text(encoding="utf-8")
    m = re.search(r'^RAG_ROOT\s*=\s*Path\(os\.environ\.get\("SYNAPSE_RAG_ROOT",\s*(.+?)\)\)',
                  scout_src, re.MULTILINE)
    root_canonical = bool(m) and "HOUDINI21_RAG_SYSTEM" not in m.group(1)

    stats = {
        "reference_files": len(ref_files),
        "corpus_entries_from_markdown": len(md_entries),
        "corpus_entries_from_extra_sources": len(corpus_entries),
        "corpus_entries": len(md_entries) + len(corpus_entries),
        "lexical_topic_map_size": lexical_topics,
        "semantic_index_built": semantic_built,
        "semantic_index_model": semantic_model,
        "retrieval_mode": "hybrid" if semantic_built else "lexical_only",
        "rag_root_default_canonical": root_canonical,
    }
    digest = hashlib.blake2b(
        json.dumps(stats, sort_keys=True, ensure_ascii=False).encode("utf-8"),
        digest_size=16,
    ).hexdigest()

    out = {
        "schema": "knowledge_baseline/v1",
        "stats": stats,
        "blake2b": digest,
    }
    out_fp = REPO_ROOT / "harness" / "notes" / "knowledge_baseline.json"
    out_fp.parent.mkdir(parents=True, exist_ok=True)
    out_fp.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[knowledge_baseline] wrote {out_fp}")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
