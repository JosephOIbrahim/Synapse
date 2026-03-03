"""
FORGE Corpus Ingester — Promote clustered patterns into FORGE corpus entries.

Reads pattern_clusters.json (output of the clustering phase) and ingests
high-frequency patterns into the FORGE corpus using the Pokémon evolution
model:
  - freq >= 5  →  RULE   (crystallized knowledge)
  - freq >= 3  →  PATTERN (validated recurring behavior)
  - freq >= 1  →  OBSERVATION (raw finding)

All entries created with AgentRole.RESEARCHER as the creator, since this
is automated extraction (discovery work).

ZERO dependency on hou module. Runs outside Houdini as a pure data transform.

Input:  forge/extraction_data/pattern_clusters.json
Output: forge/corpus/{observations,patterns,rules}/*.json  (via CorpusManager)
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from forge.engine.schemas import (
    AgentRole,
    CorpusEntry,
    CorpusStage,
    ScenarioDomain,
    ScenarioResult,
)
from forge.engine.corpus_manager import CorpusManager


# =============================================================================
# Paths
# =============================================================================

_DATA_DIR = Path(__file__).resolve().parent.parent / "extraction_data"
PATTERN_CLUSTERS_PATH = _DATA_DIR / "pattern_clusters.json"
CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"


# =============================================================================
# Domain Mapping
# =============================================================================

# Map cluster roles (from pattern_clusterer) to FORGE ScenarioDomain.
_ROLE_TO_DOMAIN: dict[str, ScenarioDomain] = {
    "render_setup": ScenarioDomain.RENDER,
    "lighting": ScenarioDomain.LIGHTING,
    "shading": ScenarioDomain.LOOKDEV,
    "camera": ScenarioDomain.LAYOUT,
    "instancing": ScenarioDomain.FX,
    "simulation": ScenarioDomain.FX,
    "deformation": ScenarioDomain.FX,
    "geometry_generation": ScenarioDomain.GENERAL,
    "composition": ScenarioDomain.PIPELINE,
    "constraint": ScenarioDomain.LAYOUT,
    "import_export": ScenarioDomain.PIPELINE,
    "attribute": ScenarioDomain.GENERAL,
    "grouping": ScenarioDomain.GENERAL,
    "transform": ScenarioDomain.GENERAL,
    "pdg": ScenarioDomain.PIPELINE,
    "general": ScenarioDomain.GENERAL,
}


# =============================================================================
# Ingestion Logic
# =============================================================================


def _determine_stage(count: int) -> CorpusStage:
    """Determine corpus stage based on cluster frequency."""
    if count >= 5:
        return CorpusStage.RULE
    if count >= 3:
        return CorpusStage.PATTERN
    return CorpusStage.OBSERVATION


def _confidence_from_count(count: int) -> float:
    """Map occurrence count to confidence score (diminishing returns)."""
    if count >= 10:
        return 0.9
    if count >= 5:
        return 0.7 + (count - 5) * 0.04  # 0.7 → 0.9
    if count >= 3:
        return 0.3 + (count - 3) * 0.2  # 0.3 → 0.7
    return 0.1 + (count - 1) * 0.1  # 0.1 → 0.2


def _build_pattern_text(cluster: dict[str, Any]) -> str:
    """Build a human-readable pattern description from cluster data."""
    node_types = cluster.get("node_types", [])
    role = cluster.get("role", "general")
    count = cluster.get("count", 1)
    chain = " → ".join(node_types)
    return f"Solaris {role} chain ({count}x): {chain}"


def _build_context_text(cluster: dict[str, Any]) -> str:
    """Build context string describing where/when this pattern applies."""
    sources = cluster.get("sources", [])
    network_paths = cluster.get("network_paths", [])
    parts = []
    if sources:
        parts.append(f"Found in {len(sources)} example file(s)")
    if network_paths:
        parts.append(f"Network(s): {', '.join(network_paths[:3])}")
    return ". ".join(parts) if parts else "Extracted from Houdini example files"


def ingest_clusters(
    clusters_path: Path | None = None,
    corpus_dir: Path | None = None,
) -> dict[str, Any]:
    """Ingest pattern clusters into the FORGE corpus.

    Reads pattern_clusters.json, creates CorpusEntry objects for each cluster
    and each common fragment, and writes them via CorpusManager.

    Args:
        clusters_path: Path to pattern_clusters.json. Defaults to standard location.
        corpus_dir: Path to corpus directory. Defaults to forge/corpus/.

    Returns:
        Summary dict with counts by stage, total ingested, and skipped (dedup).
    """
    src = clusters_path or PATTERN_CLUSTERS_PATH
    dst = corpus_dir or CORPUS_DIR

    data = json.loads(src.read_text(encoding="utf-8"))
    clusters = data.get("clusters", [])
    fragments = data.get("fragments", [])

    manager = CorpusManager(dst)

    stats: dict[str, int] = {
        "clusters_processed": 0,
        "fragments_processed": 0,
        "entries_created": 0,
        "entries_deduplicated": 0,
        "observations": 0,
        "patterns": 0,
        "rules": 0,
    }

    print(f"Ingesting {len(clusters)} clusters + {len(fragments)} fragments")

    # --- Ingest clusters ---
    for cluster in clusters:
        count = cluster.get("count", 1)
        stage = _determine_stage(count)
        role = cluster.get("role", "general")
        domain = _ROLE_TO_DOMAIN.get(role, ScenarioDomain.GENERAL)

        pattern_text = _build_pattern_text(cluster)
        context_text = _build_context_text(cluster)

        # Build a synthetic ScenarioResult to use CorpusManager's dedup
        synthetic_result = ScenarioResult(
            cycle=0,
            agent=AgentRole.RESEARCHER,
            scenario_id=f"extraction:{cluster.get('cluster_id', 'unknown')}",
        )

        entry = manager.add_observation(
            result=synthetic_result,
            pattern=pattern_text,
            context=context_text,
        )

        # Override stage and confidence based on frequency
        # (add_observation creates OBSERVATION by default)
        entry.stage = stage
        entry.confidence = _confidence_from_count(count)
        entry.recurrence_count = count
        entry.domain = domain
        entry.category = role

        # Save with updated stage (moves to correct directory)
        manager._save_entry(entry)
        manager._update_manifest(entry)

        stage_key = stage.value + "s"
        stats[stage_key] = stats.get(stage_key, 0) + 1
        stats["entries_created"] += 1
        stats["clusters_processed"] += 1

    # --- Ingest common fragments ---
    for fragment in fragments:
        occ = fragment.get("occurrence_count", 1)
        stage = _determine_stage(occ)
        role = fragment.get("role", "general")
        domain = _ROLE_TO_DOMAIN.get(role, ScenarioDomain.GENERAL)

        node_types = fragment.get("node_types", [])
        chain = " → ".join(node_types)
        pattern_text = f"Common Solaris fragment ({occ}x across clusters): {chain}"
        context_text = (
            f"Shared subsequence found in {occ} distinct topology clusters. "
            f"Fragment length: {fragment.get('length', len(node_types))} nodes."
        )

        synthetic_result = ScenarioResult(
            cycle=0,
            agent=AgentRole.RESEARCHER,
            scenario_id=f"extraction:{fragment.get('fragment_id', 'unknown')}",
        )

        entry = manager.add_observation(
            result=synthetic_result,
            pattern=pattern_text,
            context=context_text,
        )

        entry.stage = stage
        entry.confidence = _confidence_from_count(occ)
        entry.recurrence_count = occ
        entry.domain = domain
        entry.category = f"fragment:{role}"

        manager._save_entry(entry)
        manager._update_manifest(entry)

        stage_key = stage.value + "s"
        stats[stage_key] = stats.get(stage_key, 0) + 1
        stats["entries_created"] += 1
        stats["fragments_processed"] += 1

    # Summary
    print(f"\nIngestion complete:")
    print(f"  Clusters processed: {stats['clusters_processed']}")
    print(f"  Fragments processed: {stats['fragments_processed']}")
    print(f"  Entries created: {stats['entries_created']}")
    print(f"  By stage: {stats['rules']} rules, {stats['patterns']} patterns, {stats['observations']} observations")

    return stats


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys

    stats = ingest_clusters()
    total = stats["entries_created"]
    print(f"\nIngested {total} corpus entries from extraction pipeline.")
    sys.exit(0)
