"""
FORGE Pattern Clusterer — Groups extracted topologies into reusable patterns.

Reads raw_topologies.json (output of the extraction phase) and produces
pattern_clusters.json with:
  - Exact signature clusters (identical node-type sequences)
  - Common fragments (shared subsequences across different topologies)
  - Functional role classification per cluster

ZERO dependency on hou module. Runs outside Houdini as a pure data transform.

Input:  forge/extraction_data/raw_topologies.json
Output: forge/extraction_data/pattern_clusters.json
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# =============================================================================
# Paths
# =============================================================================

_DATA_DIR = Path(__file__).resolve().parent.parent / "extraction_data"
RAW_TOPOLOGIES_PATH = _DATA_DIR / "raw_topologies.json"
PATTERN_CLUSTERS_PATH = _DATA_DIR / "pattern_clusters.json"


# =============================================================================
# Role Classification Keywords
# =============================================================================

# Maps functional role names to keyword sets matched against node types.
# Order matters: first match wins.
ROLE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("render_setup", ["karma", "render", "usdrender", "rop_", "ifd"]),
    ("lighting", ["light", "envlight", "domelight", "distant", "rectlight"]),
    ("shading", [
        "material", "mtlx", "materialx", "shader", "principled", "matlib",
        "assign",
    ]),
    ("camera", ["camera", "cam", "lens", "dof"]),
    ("instancing", [
        "instance", "copytopoints", "copy_to_points", "scatter",
    ]),
    ("simulation", [
        "dop", "flip", "pyro", "vellum", "rbd", "bullet", "solver",
        "sop_solver", "pop",
    ]),
    ("deformation", [
        "deform", "lattice", "bend", "twist", "mountain", "noise",
        "smooth", "sculpt",
    ]),
    ("geometry_generation", [
        "grid", "sphere", "box", "tube", "torus", "circle", "line",
        "platonic", "font",
    ]),
    ("composition", [
        "sublayer", "reference", "payload", "variant", "flatten",
        "graft", "merge", "collect",
    ]),
    ("constraint", [
        "constraint", "lookat", "follow", "parent", "orient",
    ]),
    ("import_export", [
        "file", "filecache", "rop_geometry", "alembic", "usdimport",
        "usdexport", "sopimport",
    ]),
    ("attribute", [
        "attrib", "attribute", "wrangle", "vex", "promote", "rename",
    ]),
    ("grouping", ["group", "partition", "blast", "delete"]),
    ("transform", ["xform", "transform", "null", "object_merge"]),
    ("pdg", ["topnet", "top_", "wedge", "ropfetch", "waitforall"]),
]


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class RawTopology:
    """A single extracted node-graph topology from a HIP file or HDA."""

    source: str  # HIP path or HDA name
    network_path: str  # e.g. /obj/geo1, /stage
    node_types: list[str]  # Ordered list of node type names
    connections: list[list[int]]  # Adjacency list (index-based)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def signature(self) -> str:
        """Deterministic hash of the node-type sequence + connection topology."""
        sig_data = json.dumps(
            {"types": self.node_types, "connections": self.connections},
            sort_keys=True,
        )
        return hashlib.sha256(sig_data.encode("utf-8")).hexdigest()[:16]

    @property
    def type_sequence(self) -> tuple[str, ...]:
        return tuple(self.node_types)


@dataclass
class PatternCluster:
    """A group of topologies sharing the same exact signature."""

    cluster_id: str
    signature: str
    role: str  # Functional role inferred from node types
    node_types: list[str]
    connections: list[list[int]]
    sources: list[str]  # Which HIP/HDA files contained this pattern
    network_paths: list[str]
    count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommonFragment:
    """A shared node-type subsequence found across multiple clusters."""

    fragment_id: str
    node_types: list[str]
    length: int
    found_in_clusters: list[str]  # Cluster IDs
    occurrence_count: int
    role: str  # Functional role of this fragment


@dataclass
class ClusterResult:
    """Full output of the pattern clustering phase."""

    clusters: list[PatternCluster]
    fragments: list[CommonFragment]
    stats: dict[str, Any]


# =============================================================================
# Role Inference
# =============================================================================


def _infer_role(node_types: list[str]) -> str:
    """Classify the functional role of a node-type sequence.

    Scans node types against ROLE_KEYWORDS. The role whose keywords match
    the most nodes wins. Ties broken by declaration order (earlier = higher
    priority).

    Returns "general" if no keywords match.
    """
    if not node_types:
        return "general"

    lower_types = [t.lower() for t in node_types]
    role_scores: Counter[str] = Counter()

    for role, keywords in ROLE_KEYWORDS:
        for node_type in lower_types:
            for kw in keywords:
                if kw in node_type:
                    role_scores[role] += 1
                    break  # One match per node per role is enough

    if not role_scores:
        return "general"

    # Highest score wins. On tie, ROLE_KEYWORDS declaration order breaks it
    # (Counter.most_common is stable for equal counts).
    max_score = role_scores.most_common(1)[0][1]
    role_order = [r for r, _ in ROLE_KEYWORDS]
    for role in role_order:
        if role_scores.get(role, 0) == max_score:
            return role

    return "general"


# =============================================================================
# Common Fragment Discovery
# =============================================================================


def _find_common_fragments(
    clusters: list[PatternCluster],
    min_length: int = 2,
    min_occurrences: int = 2,
) -> list[CommonFragment]:
    """Discover shared node-type subsequences across clusters.

    Uses a sliding-window approach: for each cluster's node_types, extract
    all contiguous subsequences of length >= min_length. Subsequences that
    appear in >= min_occurrences distinct clusters are reported as fragments.

    This is intentionally simple (O(n * k^2) where k = max chain length).
    Topology sizes in Houdini networks rarely exceed ~50 nodes, so brute
    force is fine.
    """
    # Map subsequence (as tuple) -> set of cluster IDs that contain it
    subseq_to_clusters: dict[tuple[str, ...], set[str]] = defaultdict(set)

    for cluster in clusters:
        types = cluster.node_types
        n = len(types)
        seen_in_cluster: set[tuple[str, ...]] = set()

        for length in range(min_length, n + 1):
            for start in range(n - length + 1):
                subseq = tuple(types[start : start + length])
                if subseq not in seen_in_cluster:
                    seen_in_cluster.add(subseq)
                    subseq_to_clusters[subseq].add(cluster.cluster_id)

    # Filter to subsequences found in enough clusters
    candidates: list[tuple[tuple[str, ...], set[str]]] = [
        (subseq, cids)
        for subseq, cids in subseq_to_clusters.items()
        if len(cids) >= min_occurrences
    ]

    # Remove subsequences that are fully contained within a longer one
    # sharing the same cluster set (keep the longest).
    candidates.sort(key=lambda x: len(x[0]), reverse=True)
    kept: list[tuple[tuple[str, ...], set[str]]] = []

    for subseq, cids in candidates:
        # Check if a longer kept fragment already covers this one
        # in the same or superset of clusters.
        is_redundant = False
        for longer_subseq, longer_cids in kept:
            if len(longer_subseq) > len(subseq) and cids <= longer_cids:
                # Check if subseq is a contiguous sub-tuple of longer_subseq
                if _is_contiguous_subtuple(subseq, longer_subseq):
                    is_redundant = True
                    break
        if not is_redundant:
            kept.append((subseq, cids))

    # Build fragment objects
    fragments: list[CommonFragment] = []
    for i, (subseq, cids) in enumerate(kept):
        types_list = list(subseq)
        fragments.append(
            CommonFragment(
                fragment_id=f"frag-{i:04d}",
                node_types=types_list,
                length=len(types_list),
                found_in_clusters=sorted(cids),
                occurrence_count=len(cids),
                role=_infer_role(types_list),
            )
        )

    # Sort: longest first, then by occurrence count descending
    fragments.sort(key=lambda f: (-f.length, -f.occurrence_count))
    return fragments


def _is_contiguous_subtuple(
    short: tuple[str, ...], long: tuple[str, ...]
) -> bool:
    """Check if short is a contiguous sub-tuple of long."""
    slen = len(short)
    for start in range(len(long) - slen + 1):
        if long[start : start + slen] == short:
            return True
    return False


# =============================================================================
# Clustering
# =============================================================================


def cluster_topologies(
    topologies: list[RawTopology],
) -> list[PatternCluster]:
    """Group topologies by exact signature match.

    Each unique (node_types + connections) combination becomes one cluster.
    """
    sig_groups: dict[str, list[RawTopology]] = defaultdict(list)
    for topo in topologies:
        sig_groups[topo.signature].append(topo)

    clusters: list[PatternCluster] = []
    for i, (sig, group) in enumerate(sorted(sig_groups.items())):
        representative = group[0]
        clusters.append(
            PatternCluster(
                cluster_id=f"cluster-{i:04d}",
                signature=sig,
                role=_infer_role(representative.node_types),
                node_types=representative.node_types,
                connections=representative.connections,
                sources=sorted({t.source for t in group}),
                network_paths=sorted({t.network_path for t in group}),
                count=len(group),
                metadata={
                    "avg_node_count": sum(len(t.node_types) for t in group) / len(group),
                },
            )
        )

    # Sort by frequency descending (most common patterns first)
    clusters.sort(key=lambda c: -c.count)
    return clusters


# =============================================================================
# Pipeline Entry Point
# =============================================================================


def run(
    input_path: Path | None = None,
    output_path: Path | None = None,
    min_fragment_length: int = 2,
    min_fragment_occurrences: int = 2,
) -> ClusterResult:
    """Run the full pattern clustering pipeline.

    1. Load raw topologies from JSON
    2. Cluster by exact signature
    3. Extract common fragments across clusters
    4. Infer functional roles
    5. Write results to JSON

    Returns the ClusterResult for programmatic use.
    """
    src = input_path or RAW_TOPOLOGIES_PATH
    dst = output_path or PATTERN_CLUSTERS_PATH

    # Load
    raw_data = json.loads(src.read_text(encoding="utf-8"))
    topologies = [RawTopology(**entry) for entry in raw_data]

    # Cluster
    clusters = cluster_topologies(topologies)

    # Fragment discovery
    fragments = _find_common_fragments(
        clusters,
        min_length=min_fragment_length,
        min_occurrences=min_fragment_occurrences,
    )

    # Role distribution stats
    role_dist: Counter[str] = Counter()
    for c in clusters:
        role_dist[c.role] += c.count

    result = ClusterResult(
        clusters=clusters,
        fragments=fragments,
        stats={
            "total_topologies": len(topologies),
            "unique_clusters": len(clusters),
            "common_fragments": len(fragments),
            "role_distribution": dict(role_dist.most_common()),
            "largest_cluster_count": clusters[0].count if clusters else 0,
            "singleton_clusters": sum(1 for c in clusters if c.count == 1),
        },
    )

    # Write
    dst.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "clusters": [asdict(c) for c in result.clusters],
        "fragments": [asdict(f) for f in result.fragments],
        "stats": result.stats,
    }
    dst.write_text(
        json.dumps(output, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return result


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys

    result = run()
    print(
        f"Clustered {result.stats['total_topologies']} topologies "
        f"into {result.stats['unique_clusters']} clusters, "
        f"{result.stats['common_fragments']} common fragments."
    )
    # Role breakdown
    for role, count in result.stats["role_distribution"].items():
        print(f"  {role}: {count}")
    sys.exit(0)
