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

import json
from pathlib import Path
from typing import Optional


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


def build_corpus(rag_root: Optional[str] = None, out_root: Optional[str] = None) -> dict:
    """Materialize the scout corpus from rag_root → out_root/corpus/entries.jsonl.

    Returns ``{entries, path, store_root}``. Raises if rag_root yields no entries
    (fail-loud — a silently-empty corpus is the bug this whole tool exists to avoid)."""
    src = Path(rag_root) if rag_root else rag_source()
    out = Path(out_root) if out_root else corpus_root()

    entries = _entries_from_knowledge(src)
    if not entries:
        raise RuntimeError(
            f"[scout_ingest] no entries from {src} — expected "
            f"{src / 'skills' / 'houdini21-reference'}/*.md (KnowledgeIndex source). "
            "Is the canonical rag/ tree present?"
        )

    corpus_dir = out / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (out / "semantic_index").mkdir(parents=True, exist_ok=True)  # empty → lexical_only

    out_fp = corpus_dir / "entries.jsonl"
    out_fp.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
        encoding="utf-8",
    )
    return {"entries": len(entries), "path": str(out_fp), "store_root": str(out)}


def ensure_corpus(rag_root: Optional[str] = None, out_root: Optional[str] = None) -> dict:
    """Build the corpus iff it is absent/empty (idempotent). The live wiring calls
    this before dispatch so scout never goes live empty."""
    out = Path(out_root) if out_root else corpus_root()
    fp = out / "corpus" / "entries.jsonl"
    if fp.is_file() and fp.stat().st_size > 0:
        return {"entries": -1, "path": str(fp), "store_root": str(out), "cached": True}
    return build_corpus(rag_root, out_root)


if __name__ == "__main__":             # pragma: no cover
    import sys
    res = build_corpus()
    sys.stdout.write(f"built {res['entries']} entries -> {res['path']}\n")
