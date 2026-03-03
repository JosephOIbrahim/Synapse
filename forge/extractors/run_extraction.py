"""
FORGE Extraction Runner — Master pipeline that runs all 5 extraction phases.

Phases:
  1. Hip Crawler     — Scan $HFS examples for Solaris .hip files
  2. Topology Extract — Extract network wiring from each .hip
  3. Pattern Cluster  — Group topologies into reusable pattern clusters
  4. Corpus Ingest    — Promote high-frequency patterns into FORGE corpus
  5. RAG Generate     — Produce markdown RAG document from corpus + clusters

Phases 1-2 require Houdini (hou module). Phases 3-5 are pure Python.

Run from Houdini Python shell or hython for the full pipeline.
Run with --skip-houdini to execute phases 3-5 only (offline analysis).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any


# =============================================================================
# Paths
# =============================================================================

_FORGE_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _FORGE_ROOT / "extraction_data"
HIP_MANIFEST_PATH = _DATA_DIR / "hip_manifest.json"
RAW_TOPOLOGIES_PATH = _DATA_DIR / "raw_topologies.json"
PATTERN_CLUSTERS_PATH = _DATA_DIR / "pattern_clusters.json"


# =============================================================================
# Phase Runner
# =============================================================================


def _print_phase(number: int, name: str, status: str = "RUNNING") -> None:
    """Print a phase status line."""
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  Phase {number}/5: {name}  [{status}]")
    print(bar)


def _print_summary(results: dict[str, Any]) -> None:
    """Print final pipeline summary."""
    bar = "=" * 60
    print(f"\n{bar}")
    print("  FORGE EXTRACTION PIPELINE — COMPLETE")
    print(bar)

    for phase, data in results.items():
        status = data.get("status", "unknown")
        elapsed = data.get("elapsed_s", 0)
        icon = "OK" if status == "success" else "SKIP" if status == "skipped" else "FAIL"
        print(f"  [{icon}] {phase} ({elapsed:.1f}s)")
        for key, val in data.items():
            if key not in ("status", "elapsed_s"):
                print(f"        {key}: {val}")

    total_time = sum(d.get("elapsed_s", 0) for d in results.values())
    print(f"\n  Total time: {total_time:.1f}s")
    print(bar)


def run_pipeline(
    skip_houdini: bool = False,
    examples_subdir: str = "houdini/help/examples",
    include_non_solaris: bool = False,
) -> dict[str, Any]:
    """Run the full extraction pipeline.

    Args:
        skip_houdini: If True, skip phases 1-2 (requires existing data files).
        examples_subdir: Subdirectory under $HFS to scan in phase 1.
        include_non_solaris: Include non-Solaris .hip files in phase 1.

    Returns:
        Dict of phase results with status, timing, and key metrics.
    """
    results: dict[str, Any] = {}

    # ── Phase 1: Hip Crawler ──────────────────────────────────────────────
    if skip_houdini:
        _print_phase(1, "Hip Crawler", "SKIPPED (--skip-houdini)")
        results["phase_1_crawl"] = {"status": "skipped", "elapsed_s": 0}

        if not HIP_MANIFEST_PATH.exists():
            print("  ERROR: hip_manifest.json not found. Run phase 1 in Houdini first.")
            results["phase_1_crawl"]["status"] = "error"
            return results
    else:
        _print_phase(1, "Hip Crawler")
        t0 = time.time()
        try:
            from forge.extractors.hip_crawler import crawl_examples
            manifest = crawl_examples(
                output_path=str(HIP_MANIFEST_PATH),
                examples_subdir=examples_subdir,
                include_non_solaris=include_non_solaris,
            )
            results["phase_1_crawl"] = {
                "status": "success",
                "elapsed_s": time.time() - t0,
                "files_scanned": manifest.total_scanned,
                "solaris_found": manifest.solaris_count,
            }
        except ImportError:
            print("  ERROR: hou module not available. Use --skip-houdini or run in Houdini.")
            results["phase_1_crawl"] = {"status": "error", "elapsed_s": time.time() - t0}
            return results
        except Exception as e:
            print(f"  ERROR: {e}")
            results["phase_1_crawl"] = {"status": "error", "elapsed_s": time.time() - t0}
            return results

    # ── Phase 2: Topology Extraction ──────────────────────────────────────
    if skip_houdini:
        _print_phase(2, "Topology Extraction", "SKIPPED (--skip-houdini)")
        results["phase_2_extract"] = {"status": "skipped", "elapsed_s": 0}

        if not RAW_TOPOLOGIES_PATH.exists():
            print("  ERROR: raw_topologies.json not found. Run phase 2 in Houdini first.")
            results["phase_2_extract"]["status"] = "error"
            return results
    else:
        _print_phase(2, "Topology Extraction")
        t0 = time.time()
        try:
            from forge.extractors.topology_extractor import extract_all
            collection = extract_all(
                manifest_path=str(HIP_MANIFEST_PATH),
                output_path=str(RAW_TOPOLOGIES_PATH),
            )
            results["phase_2_extract"] = {
                "status": "success",
                "elapsed_s": time.time() - t0,
                "topologies_extracted": collection.total_extracted,
                "errors": collection.errors,
            }
        except Exception as e:
            print(f"  ERROR: {e}")
            results["phase_2_extract"] = {"status": "error", "elapsed_s": time.time() - t0}
            return results

    # ── Phase 3: Pattern Clustering ───────────────────────────────────────
    _print_phase(3, "Pattern Clustering")
    t0 = time.time()
    try:
        from forge.extractors.pattern_clusterer import run as run_clusterer
        cluster_result = run_clusterer(
            input_path=RAW_TOPOLOGIES_PATH,
            output_path=PATTERN_CLUSTERS_PATH,
        )
        results["phase_3_cluster"] = {
            "status": "success",
            "elapsed_s": time.time() - t0,
            "unique_clusters": cluster_result.stats.get("unique_clusters", 0),
            "common_fragments": cluster_result.stats.get("common_fragments", 0),
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        results["phase_3_cluster"] = {"status": "error", "elapsed_s": time.time() - t0}
        return results

    # ── Phase 4: Corpus Ingestion ─────────────────────────────────────────
    _print_phase(4, "Corpus Ingestion")
    t0 = time.time()
    try:
        from forge.extractors.corpus_ingester import ingest_clusters
        ingest_stats = ingest_clusters(
            clusters_path=PATTERN_CLUSTERS_PATH,
        )
        results["phase_4_ingest"] = {
            "status": "success",
            "elapsed_s": time.time() - t0,
            "entries_created": ingest_stats.get("entries_created", 0),
            "rules": ingest_stats.get("rules", 0),
            "patterns": ingest_stats.get("patterns", 0),
            "observations": ingest_stats.get("observations", 0),
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        results["phase_4_ingest"] = {"status": "error", "elapsed_s": time.time() - t0}
        return results

    # ── Phase 5: RAG Generation ───────────────────────────────────────────
    _print_phase(5, "RAG Generation")
    t0 = time.time()
    try:
        from forge.extractors.rag_generator import generate_rag
        rag_path = generate_rag(
            clusters_path=PATTERN_CLUSTERS_PATH,
        )
        results["phase_5_rag"] = {
            "status": "success",
            "elapsed_s": time.time() - t0,
            "output": str(rag_path),
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        results["phase_5_rag"] = {"status": "error", "elapsed_s": time.time() - t0}
        return results

    # ── Summary ───────────────────────────────────────────────────────────
    _print_summary(results)
    return results


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    skip = "--skip-houdini" in sys.argv
    run_pipeline(skip_houdini=skip)
