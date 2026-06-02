"""Seed Moneta with a compact, recall-triggering VEX-corpus pointer index.

Mile 4 of the VEX-corpus goal. The recall->RAG seam (Mile 3) already makes the
full corpus *retrievable* via synapse_recall/search. This script adds the
*first-class Moneta object* the artist asked for: one compact REFERENCE /
SHOW-tier entry per VEX topic -- summary + dense tags/keywords + a path into
rag/ -- NOT the full example text. So:

  * recall triggers on vex / wrangle / @attrib via Moneta's tag+keyword scoring
    (a second trigger path that complements RAG's lexical match),
  * SHOW tier => protected_floor > 0 => survives Moneta sleep/decay passes,
  * zero bulk duplication of the ~2000-example corpus (pointers, not copies).

It also seeds the genuinely-missing pipeline knowledge the audit found unstored:
the materiallinker>assignmaterial preference and the Karma-CPU production preset.
(The AMD library path is intentionally NOT seeded -- it was not found anywhere on
disk and is pending the artist.)

Standalone -- no ``hou`` required. Usage:
    python -m synapse.memory.seed_corpus [--dir DIR] [--dry-run] [--force]

Default DIR is <repo>/.synapse/corpus -- a dedicated project dir, so the
single-owner Moneta URI lock never collides with a live Houdini session.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Allow running as a plain file (python path/to/seed_corpus.py) as well as -m.
_REPO_PYTHON = Path(__file__).resolve().parents[2]
if str(_REPO_PYTHON) not in sys.path:
    sys.path.insert(0, str(_REPO_PYTHON))

from synapse.memory.models import Memory, MemoryType, MemoryTier  # noqa: E402

# Deterministic timestamp => deterministic Memory ids => stable across re-runs.
_SEED_TS = "2026-06-02T00:00:00"
_SEED_TAG = "vex_corpus_seed"
_MAX_KEYWORDS = 12

_REPO_ROOT = _REPO_PYTHON.parent
_RAG_REF_DIR = "rag/skills/houdini21-reference"
_SEMANTIC_INDEX = _REPO_ROOT / "rag" / "documentation" / "_metadata" / "semantic_index.json"


def _short_topic(key: str) -> str:
    """Human tag from an index key: vex_corpus_noise_patterns -> noise_patterns."""
    for prefix in ("vex_corpus_", "joy_of_vex_", "rag_"):
        if key.startswith(prefix):
            return key[len(prefix):]
    return key


def _corpus_pointers(index: Dict) -> List[Memory]:
    """One compact REFERENCE/SHOW pointer Memory per VEX-related index topic."""
    out: List[Memory] = []
    for key, entry in sorted(index.items()):
        if "vex" not in key.lower():
            continue
        summary = (entry.get("summary") or "").strip()
        description = (entry.get("description") or "").strip()
        ref = entry.get("reference_file") or key
        kws = [k for k in (entry.get("keywords") or []) if isinstance(k, str)]
        topic = _short_topic(key)

        content = (
            f"VEX corpus topic: {topic.replace('_', ' ')}.\n"
            f"{summary}\n\n{description}\n\n"
            f"Full examples: {_RAG_REF_DIR}/{ref}.md "
            f"(also reachable via synapse_knowledge_lookup / recall)."
        ).strip()

        # Dense, deduped trigger surface. Order-stable, capped.
        seen = set()
        keywords: List[str] = []
        for k in ["vex", "wrangle"] + kws + [topic]:
            kl = k.strip()
            if kl and kl.lower() not in seen:
                seen.add(kl.lower())
                keywords.append(kl)
            if len(keywords) >= _MAX_KEYWORDS:
                break

        out.append(Memory(
            created_at=_SEED_TS,
            content=content,
            memory_type=MemoryType.REFERENCE,
            tier=MemoryTier.SHOW,
            summary=f"VEX: {topic.replace('_', ' ')}",
            tags=["vex", "wrangle", "corpus", _SEED_TAG, topic],
            keywords=keywords,
            source="user",
        ))
    return out


def _missing_item_entries() -> List[Memory]:
    """The genuinely-unstored pipeline knowledge the audit surfaced."""
    entries: List[Memory] = []

    # materiallinker > assignmaterial -- a recorded preference (DECISION so it
    # also surfaces through recall's decision search; SHOW so it is protected).
    entries.append(Memory(
        created_at=_SEED_TS,
        content=(
            "Pipeline preference: bind materials in Solaris with the "
            "`materiallinker` LOP, NOT `assignmaterial`. materiallinker drives "
            "collection-based binding and is the preferred path; assignmaterial "
            "(documented in rag/skills/houdini21-reference/solaris_nodes.md) "
            "stays available but is not the default."
        ),
        memory_type=MemoryType.DECISION,
        tier=MemoryTier.SHOW,
        summary="Prefer materiallinker over assignmaterial in Solaris",
        tags=["solaris", "material", "pipeline", "preference", _SEED_TAG],
        keywords=["materiallinker", "assignmaterial", "material", "bind",
                  "collection", "lop", "solaris"],
        source="user",
    ))

    # Karma-CPU production preset -- generalized from the rubber_toy summary.
    entries.append(Memory(
        created_at=_SEED_TS,
        content=(
            "Karma CPU production preset (diffuse-dominant hero, derived from "
            "docs/karma_cpu_settings_summary.md): Bucket image mode, bucket size "
            "64, 256 pixel samples, 512 path-traced samples, light-tree sampling "
            "at quality 1.5, indirect guiding ON (128 training samples, "
            "diffuse+sss), variance AA threshold 0.005, blackman-harris 1.5 "
            "pixel filter, diffuse limit 3 / reflect 2 / refract 0. Start here "
            "for matte/diffuse surfaces on CPU; full table in "
            "docs/karma_cpu_settings_summary.md."
        ),
        memory_type=MemoryType.REFERENCE,
        tier=MemoryTier.SHOW,
        summary="Karma CPU production preset (diffuse-dominant)",
        tags=["karma", "render", "cpu", "pipeline", "config", _SEED_TAG],
        keywords=["karma", "cpu", "render", "pixel samples", "bucket",
                  "guiding", "render settings", "preset"],
        source="user",
    ))
    return entries


def build_entries() -> List[Memory]:
    if not _SEMANTIC_INDEX.exists():
        raise FileNotFoundError(f"semantic index not found: {_SEMANTIC_INDEX}")
    index = json.loads(_SEMANTIC_INDEX.read_text(encoding="utf-8"))
    return _corpus_pointers(index) + _missing_item_entries()


def seed(target_dir: str, dry_run: bool = False, force: bool = False) -> Dict:
    entries = build_entries()
    if dry_run:
        return {
            "dry_run": True,
            "would_write": len(entries),
            "samples": [e.summary for e in entries[:8]],
        }

    from synapse.memory.moneta_store import MonetaBackedStore

    os.makedirs(target_dir, exist_ok=True)
    store = MonetaBackedStore.from_storage_dir(target_dir)
    try:
        existing = store.count()
        if existing > 0 and not force:
            return {
                "skipped": True,
                "reason": f"target already has {existing} entries; use --force",
                "dir": target_dir,
            }
        written = [store.add(m) for m in entries]
        store.save()
        return {
            "written": len(written),
            "total_after": store.count(),
            "dir": target_dir,
        }
    finally:
        store.close()


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Seed Moneta with the VEX-corpus pointer index.")
    ap.add_argument("--dir", default=str(_REPO_ROOT / ".synapse" / "corpus"),
                    help="Moneta project dir (default: <repo>/.synapse/corpus)")
    ap.add_argument("--dry-run", action="store_true", help="preview without writing")
    ap.add_argument("--force", action="store_true", help="seed even if dir is non-empty")
    args = ap.parse_args(argv)

    result = seed(args.dir, dry_run=args.dry_run, force=args.force)
    # sys.stdout.write (not print) keeps this CLI within the repo's
    # "no print() in source" rule (tests/test_v5_features.py).
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
