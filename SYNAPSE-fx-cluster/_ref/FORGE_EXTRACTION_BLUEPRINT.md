# FORGE Solaris Pattern Extraction Pipeline
## Learn Wiring Patterns from Houdini 21's Own Examples

> **Mission:** Crawl Houdini 21's built-in example .hip files, extract every 
> Solaris/LOP network topology, cluster them into canonical wiring patterns, 
> feed them into the FORGE corpus as observations, and auto-generate RAG 
> documents from crystallized rules.
>
> **D1 metaphor:** We're filming the relay team's form — studying how SideFX 
> themselves wire Solaris networks — then teaching SYNAPSE to replicate 
> those handoffs.

---

## Why This Works

Houdini ships with ~200 example .hip files under `$HFS/houdini/help/examples/`.
The LOP/Solaris examples show SideFX's own canonical wiring patterns — these 
are ground truth for how Solaris networks should be assembled. We already have 
`network_explain` which extracts topology from any network. The missing piece 
is connecting these two systems through FORGE.

---

## Architecture

```
Phase 1: CRAWL
  $HFS/houdini/help/examples/ → find all .hip/.hipnc with /stage networks
  Output: hip_manifest.json (paths + metadata)

Phase 2: EXTRACT  
  For each .hip: load → run network_explain on /stage → capture topology
  Output: raw_topologies.json (node types, connections, ordering)

Phase 3: CLUSTER
  Group topologies by pattern signature (type sequence hash)
  Identify: canonical chains, common fragments, frequency counts
  Output: pattern_clusters.json

Phase 4: CORPUS INGEST
  Feed clusters into FORGE corpus as OBSERVATIONS
  Clusters seen 3+ times auto-promote to PATTERNS
  Patterns with 5+ recurrences promote to RULES
  Output: forge/corpus/observations/EX-*.json

Phase 5: RAG GENERATE
  Crystallized RULES → auto-generate RAG markdown documents
  Output: rag/skills/houdini21-reference/solaris_patterns_extracted.md

Phase 6: VERIFY (FORGE cycle)
  Run FORGE scenarios that test wiring against extracted patterns
  Measure: does SYNAPSE wire like SideFX's examples?
```

---

## File Structure (New Files)

```
forge/
├── extractors/
│   ├── __init__.py
│   ├── hip_crawler.py          # Phase 1: Find example .hip files
│   ├── topology_extractor.py   # Phase 2: Extract network topology
│   ├── pattern_clusterer.py    # Phase 3: Cluster into canonical patterns
│   ├── corpus_ingester.py      # Phase 4: Feed into FORGE corpus
│   └── rag_generator.py        # Phase 5: Generate RAG documents
├── extraction_data/
│   ├── hip_manifest.json       # Discovered .hip files
│   ├── raw_topologies.json     # Extracted network topologies
│   └── pattern_clusters.json   # Clustered patterns
```

---

## Phase 1: Hip Crawler

### File: `forge/extractors/hip_crawler.py`

```python
"""
FORGE Hip Crawler — Discover Houdini example files containing Solaris networks.

Scans $HFS/houdini/help/examples/ for .hip/.hipnc files,
opens each one, checks if /stage exists with children,
and builds a manifest of extraction targets.

Run inside Houdini's Python shell or via hython.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class HipEntry:
    """Metadata for a discovered .hip file."""
    path: str
    filename: str
    category: str          # Parent folder name (e.g., "lop", "sop", "dop")
    has_stage: bool        # Does /stage exist?
    stage_child_count: int # Number of children in /stage
    lop_node_types: List[str]  # Types of LOP nodes found
    file_size_kb: int
    error: Optional[str] = None


@dataclass
class HipManifest:
    """Collection of discovered .hip files."""
    scan_time: str
    hfs_path: str
    total_scanned: int = 0
    solaris_count: int = 0
    entries: List[HipEntry] = field(default_factory=list)

    def to_dict(self):
        return {
            "scan_time": self.scan_time,
            "hfs_path": self.hfs_path,
            "total_scanned": self.total_scanned,
            "solaris_count": self.solaris_count,
            "entries": [asdict(e) for e in self.entries],
        }


def crawl_examples(
    output_path: str = "forge/extraction_data/hip_manifest.json",
    examples_subdir: str = "houdini/help/examples",
    include_non_solaris: bool = False,
) -> HipManifest:
    """Crawl Houdini example directory for .hip files with Solaris content.

    Must be run inside Houdini (needs hou module).

    Args:
        output_path: Where to write the manifest JSON.
        examples_subdir: Subdirectory under $HFS to scan.
        include_non_solaris: If True, include .hip files without /stage.

    Returns:
        HipManifest with discovered files.
    """
    import hou

    hfs = hou.expandString("$HFS")
    examples_root = os.path.join(hfs, examples_subdir)

    manifest = HipManifest(
        scan_time=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        hfs_path=hfs,
    )

    if not os.path.isdir(examples_root):
        # Also check alternative locations
        alt_paths = [
            os.path.join(hfs, "houdini", "help", "examples"),
            os.path.join(hfs, "help", "examples"),
            os.path.join(hfs, "houdini", "examples"),
        ]
        for alt in alt_paths:
            if os.path.isdir(alt):
                examples_root = alt
                break
        else:
            print(f"ERROR: No examples directory found under {hfs}")
            return manifest

    print(f"Scanning: {examples_root}")

    # Find all .hip and .hipnc files
    hip_files = []
    for root, dirs, files in os.walk(examples_root):
        for f in files:
            if f.endswith((".hip", ".hipnc")):
                hip_files.append(os.path.join(root, f))

    print(f"Found {len(hip_files)} .hip files to scan")

    for i, hip_path in enumerate(hip_files):
        if (i + 1) % 10 == 0:
            print(f"  Scanning {i+1}/{len(hip_files)}...")

        entry = _scan_hip_file(hip_path, examples_root)
        manifest.total_scanned += 1

        if entry.has_stage and entry.stage_child_count > 0:
            manifest.solaris_count += 1
            manifest.entries.append(entry)
        elif include_non_solaris:
            manifest.entries.append(entry)

    # Sort by category then filename
    manifest.entries.sort(key=lambda e: (e.category, e.filename))

    # Save manifest
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)

    print(f"\nCrawl complete:")
    print(f"  Scanned: {manifest.total_scanned}")
    print(f"  With Solaris: {manifest.solaris_count}")
    print(f"  Manifest: {output_path}")

    return manifest


def _scan_hip_file(hip_path: str, examples_root: str) -> HipEntry:
    """Open a .hip file and check for Solaris content."""
    import hou

    filename = os.path.basename(hip_path)
    rel_path = os.path.relpath(hip_path, examples_root)
    category = rel_path.split(os.sep)[0] if os.sep in rel_path else "root"

    try:
        hou.hipFile.load(hip_path, suppress_save_prompt=True, ignore_load_warnings=True)

        stage = hou.node("/stage")
        if stage is None:
            # Check for lopnet anywhere in the scene
            for child in hou.node("/").children():
                if child.type().name() == "lopnet":
                    stage = child
                    break

        has_stage = stage is not None
        children = stage.children() if stage else []
        lop_types = sorted(set(c.type().name() for c in children))

        return HipEntry(
            path=hip_path,
            filename=filename,
            category=category,
            has_stage=has_stage,
            stage_child_count=len(children),
            lop_node_types=lop_types,
            file_size_kb=os.path.getsize(hip_path) // 1024,
        )

    except Exception as e:
        return HipEntry(
            path=hip_path,
            filename=filename,
            category=category,
            has_stage=False,
            stage_child_count=0,
            lop_node_types=[],
            file_size_kb=os.path.getsize(hip_path) // 1024,
            error=str(e)[:200],
        )
```

---

## Phase 2: Topology Extractor

### File: `forge/extractors/topology_extractor.py`

```python
"""
FORGE Topology Extractor — Extract network wiring from Solaris scenes.

For each .hip in the manifest, loads the scene, walks the /stage network,
and records the full topology: node types, connections, ordering, and
parameter states.

Leverages the existing network_explain handler patterns but runs 
directly (no MCP round-trip) for speed.

Run inside Houdini's Python shell or via hython.
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class NodeRecord:
    """Extracted information about a single LOP node."""
    name: str
    type_name: str
    type_label: str
    position_y: float           # Vertical position (proxy for chain order)
    inputs_from: List[str]      # Names of input nodes
    outputs_to: List[str]       # Names of output nodes
    input_count: int
    output_count: int
    is_display_flag: bool
    is_render_flag: bool
    has_primpath: bool           # Does it set a USD prim path?
    primpath_value: str          # The actual primpath if set
    key_params: Dict[str, Any]   # Non-default parameter values


@dataclass 
class TopologyRecord:
    """Complete topology of a single /stage network."""
    source_hip: str
    category: str
    node_count: int
    nodes: List[NodeRecord]
    chain_signature: str          # Hash of type sequence for clustering
    chain_types: List[str]        # Ordered list of type names (topological)
    connections: List[Tuple[str, str]]  # (source_name, target_name) pairs
    has_linear_chain: bool        # True if all nodes form a single chain
    branch_count: int             # Number of parallel branches
    display_flag_node: str        # Which node has display flag
    patterns_detected: List[str]  # e.g., "three_point_lighting", "material_assign"
    extraction_error: Optional[str] = None


@dataclass
class TopologyCollection:
    """All extracted topologies."""
    extraction_time: str
    total_extracted: int = 0
    errors: int = 0
    topologies: List[TopologyRecord] = field(default_factory=list)

    def to_dict(self):
        return {
            "extraction_time": self.extraction_time,
            "total_extracted": self.total_extracted,
            "errors": self.errors,
            "topologies": [asdict(t) for t in self.topologies],
        }


# Known Solaris patterns to detect
_PATTERN_SIGNATURES: Dict[str, Set[str]] = {
    "material_assignment": {"materiallibrary", "assignmaterial"},
    "three_point_lighting": {"rectlight"},  # 3+ rectlights
    "dome_environment": {"domelight"},
    "camera_setup": {"camera"},
    "karma_render": {"karmarenderproperties"},
    "sop_import": {"sopimport"},
    "sop_create": {"sopcreate"},
    "usd_reference": {"reference"},
    "usd_sublayer": {"sublayer"},
    "scene_assembly": {"sopcreate", "materiallibrary", "assignmaterial", "camera"},
}


def extract_all(
    manifest_path: str = "forge/extraction_data/hip_manifest.json",
    output_path: str = "forge/extraction_data/raw_topologies.json",
) -> TopologyCollection:
    """Extract topologies from all .hip files in the manifest.

    Must be run inside Houdini.

    Args:
        manifest_path: Path to hip_manifest.json from Phase 1.
        output_path: Where to write raw_topologies.json.

    Returns:
        TopologyCollection with all extracted networks.
    """
    import hou

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    collection = TopologyCollection(
        extraction_time=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    entries = manifest.get("entries", [])
    print(f"Extracting topologies from {len(entries)} .hip files")

    for i, entry in enumerate(entries):
        if (i + 1) % 5 == 0:
            print(f"  Extracting {i+1}/{len(entries)}: {entry['filename']}")

        topo = _extract_topology(entry["path"], entry["category"])
        collection.total_extracted += 1

        if topo.extraction_error:
            collection.errors += 1
        else:
            collection.topologies.append(topo)

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(collection.to_dict(), f, indent=2)

    print(f"\nExtraction complete:")
    print(f"  Extracted: {collection.total_extracted}")
    print(f"  Errors: {collection.errors}")
    print(f"  Valid topologies: {len(collection.topologies)}")
    print(f"  Output: {output_path}")

    return collection


def _extract_topology(hip_path: str, category: str) -> TopologyRecord:
    """Extract topology from a single .hip file."""
    import hou

    try:
        hou.hipFile.load(hip_path, suppress_save_prompt=True, ignore_load_warnings=True)

        stage = hou.node("/stage")
        if stage is None:
            for child in hou.node("/").children():
                if child.type().name() == "lopnet":
                    stage = child
                    break

        if stage is None or not stage.children():
            return TopologyRecord(
                source_hip=hip_path,
                category=category,
                node_count=0,
                nodes=[],
                chain_signature="empty",
                chain_types=[],
                connections=[],
                has_linear_chain=False,
                branch_count=0,
                display_flag_node="",
                patterns_detected=[],
                extraction_error="No /stage or empty network",
            )

        children = stage.children()

        # Topological sort (Kahn's algorithm — same as handlers_node.py)
        sorted_nodes = _topo_sort(children)

        # Extract node records
        nodes = []
        connections = []
        display_node = ""
        type_set = set()

        for n in sorted_nodes:
            type_name = n.type().name()
            type_set.add(type_name)

            inputs_from = [inp.name() for inp in n.inputs() if inp]
            outputs_to = [out.name() for out in n.outputs() if out]

            for inp in n.inputs():
                if inp:
                    connections.append((inp.name(), n.name()))

            # Check for primpath parameter
            has_primpath = False
            primpath_value = ""
            try:
                pp = n.parm("primpath")
                if pp:
                    has_primpath = True
                    primpath_value = pp.eval()
            except Exception:
                pass

            # Get non-default params (lightweight version)
            key_params = _get_key_params(n)

            is_display = False
            is_render = False
            try:
                is_display = n.isDisplayFlagSet()
                is_render = n.isRenderFlagSet() if hasattr(n, "isRenderFlagSet") else False
            except Exception:
                pass

            if is_display:
                display_node = n.name()

            nodes.append(NodeRecord(
                name=n.name(),
                type_name=type_name,
                type_label=n.type().description(),
                position_y=n.position()[1],
                inputs_from=inputs_from,
                outputs_to=outputs_to,
                input_count=len(inputs_from),
                output_count=len(outputs_to),
                is_display_flag=is_display,
                is_render_flag=is_render,
                has_primpath=has_primpath,
                primpath_value=primpath_value,
                key_params=key_params,
            ))

        # Chain analysis
        chain_types = [n.type_name for n in nodes]
        chain_sig = _compute_signature(chain_types)

        # Detect linear vs branching
        max_inputs = max((n.input_count for n in nodes), default=0)
        root_count = sum(1 for n in nodes if n.input_count == 0)
        has_linear = max_inputs <= 1 and root_count <= 1
        branch_count = max(1, root_count)

        # Detect known patterns
        patterns = _detect_patterns(type_set, nodes)

        return TopologyRecord(
            source_hip=hip_path,
            category=category,
            node_count=len(nodes),
            nodes=nodes,
            chain_signature=chain_sig,
            chain_types=chain_types,
            connections=connections,
            has_linear_chain=has_linear,
            branch_count=branch_count,
            display_flag_node=display_node,
            patterns_detected=patterns,
        )

    except Exception as e:
        return TopologyRecord(
            source_hip=hip_path,
            category=category,
            node_count=0,
            nodes=[],
            chain_signature="error",
            chain_types=[],
            connections=[],
            has_linear_chain=False,
            branch_count=0,
            display_flag_node="",
            patterns_detected=[],
            extraction_error=str(e)[:300],
        )


def _topo_sort(nodes) -> list:
    """Topological sort by input dependencies. Deterministic (name tie-break)."""
    node_set = {id(n) for n in nodes}
    id_map = {id(n): n for n in nodes}
    in_deg = {id(n): 0 for n in nodes}
    adj = {id(n): [] for n in nodes}

    for n in nodes:
        for inp in n.inputs():
            if inp and id(inp) in node_set:
                in_deg[id(n)] += 1
                adj[id(inp)].append(id(n))

    queue = sorted([n for n in nodes if in_deg[id(n)] == 0], key=lambda n: n.name())
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for nid in sorted(adj[id(node)], key=lambda x: id_map[x].name()):
            in_deg[nid] -= 1
            if in_deg[nid] == 0:
                queue.append(id_map[nid])
        queue.sort(key=lambda n: n.name())

    remaining = sorted([n for n in nodes if n not in result], key=lambda n: n.name())
    result.extend(remaining)
    return result


def _get_key_params(node, max_params: int = 10) -> Dict[str, Any]:
    """Get non-default params, limited to max_params for storage efficiency."""
    params = {}
    try:
        for parm in node.parms():
            if len(params) >= max_params:
                break
            try:
                template = parm.parmTemplate()
                type_name = template.type().name() if hasattr(template.type(), "name") else ""
                if "Folder" in type_name or "Separator" in type_name:
                    continue
                current = parm.eval()
                defaults = template.defaultValue()
                default_val = defaults[0] if isinstance(defaults, tuple) and defaults else defaults
                if current != default_val:
                    params[parm.name()] = current
            except Exception:
                continue
    except Exception:
        pass
    return params


def _compute_signature(type_list: List[str]) -> str:
    """Compute a hash signature from a sequence of type names."""
    import hashlib
    content = "|".join(type_list)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _detect_patterns(type_set: Set[str], nodes: list) -> List[str]:
    """Detect known Solaris workflow patterns."""
    detected = []
    for pattern_name, required_types in sorted(_PATTERN_SIGNATURES.items()):
        if required_types.issubset(type_set):
            # Special case: three_point needs 3+ rectlights
            if pattern_name == "three_point_lighting":
                rect_count = sum(1 for n in nodes if n.type_name == "rectlight")
                if rect_count >= 3:
                    detected.append(pattern_name)
            else:
                detected.append(pattern_name)
    return detected
```

---

## Phase 3: Pattern Clusterer

### File: `forge/extractors/pattern_clusterer.py`

```python
"""
FORGE Pattern Clusterer — Group extracted topologies into canonical patterns.

Takes raw topologies from Phase 2, clusters them by:
  1. Exact chain signature (identical type sequences)
  2. Subsequence similarity (shared fragments)
  3. Functional role clustering (lighting chains, material chains, etc.)

Outputs canonical patterns with frequency counts, which become
the training data for SYNAPSE's wiring knowledge.

Runs outside Houdini (pure Python, no hou dependency).
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class CanonicalPattern:
    """A validated wiring pattern discovered from examples."""
    pattern_id: str
    name: str                        # Human-readable name
    description: str
    chain_types: List[str]           # Canonical type sequence
    frequency: int                   # How many examples use this pattern
    source_hips: List[str]           # Which .hip files contain it
    is_linear: bool                  # Single chain or branching
    functional_role: str             # "lighting", "material", "render", etc.
    connection_rules: List[Dict]     # [{source_type, target_type, input_idx}]
    display_flag_type: str           # Which type typically gets display flag
    common_params: Dict[str, Any]    # Most common non-default param values
    confidence: float                # frequency / total_examples


@dataclass
class PatternClusterResult:
    """Output of the clustering phase."""
    cluster_time: str
    total_topologies: int
    unique_signatures: int
    canonical_patterns: List[CanonicalPattern] = field(default_factory=list)
    # Fragments: common subsequences found across multiple patterns
    common_fragments: List[Dict[str, Any]] = field(default_factory=list)
    # Type frequency: how often each node type appears across all examples
    type_frequency: Dict[str, int] = field(default_factory=dict)
    # Connection frequency: how often each connection type appears
    connection_frequency: Dict[str, int] = field(default_factory=dict)

    def to_dict(self):
        return {
            "cluster_time": self.cluster_time,
            "total_topologies": self.total_topologies,
            "unique_signatures": self.unique_signatures,
            "canonical_patterns": [asdict(p) for p in self.canonical_patterns],
            "common_fragments": self.common_fragments,
            "type_frequency": dict(sorted(
                self.type_frequency.items(), key=lambda x: -x[1]
            )),
            "connection_frequency": dict(sorted(
                self.connection_frequency.items(), key=lambda x: -x[1]
            )),
        }


def cluster_patterns(
    topologies_path: str = "forge/extraction_data/raw_topologies.json",
    output_path: str = "forge/extraction_data/pattern_clusters.json",
    min_frequency: int = 2,
) -> PatternClusterResult:
    """Cluster extracted topologies into canonical patterns.

    Args:
        topologies_path: Input from Phase 2.
        output_path: Where to write pattern_clusters.json.
        min_frequency: Minimum occurrences to be considered a pattern.

    Returns:
        PatternClusterResult with discovered patterns.
    """
    with open(topologies_path, encoding="utf-8") as f:
        data = json.load(f)

    topologies = data.get("topologies", [])
    total = len(topologies)

    result = PatternClusterResult(
        cluster_time=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        total_topologies=total,
    )

    if not topologies:
        return result

    # ── Step 1: Exact signature clustering ──
    sig_groups: Dict[str, List[Dict]] = defaultdict(list)
    for topo in topologies:
        sig_groups[topo["chain_signature"]].append(topo)

    result.unique_signatures = len(sig_groups)

    # ── Step 2: Build canonical patterns from frequent signatures ──
    pattern_id = 0
    for sig, group in sorted(sig_groups.items(), key=lambda x: -len(x[1])):
        if len(group) < min_frequency:
            continue

        pattern_id += 1
        representative = group[0]  # Use first as template
        chain_types = representative["chain_types"]

        # Determine functional role from node types
        role = _infer_role(set(chain_types))

        # Extract connection rules from the representative
        conn_rules = []
        for conn in representative.get("connections", []):
            src_name, tgt_name = conn
            # Find types from nodes list
            src_type = _find_type(representative["nodes"], src_name)
            tgt_type = _find_type(representative["nodes"], tgt_name)
            if src_type and tgt_type:
                conn_rules.append({
                    "source_type": src_type,
                    "target_type": tgt_type,
                    "input_index": 0,
                })

        # Aggregate common params across the group
        common_params = _aggregate_params(group)

        # Display flag consensus
        display_types = Counter(
            _find_type(t["nodes"], t.get("display_flag_node", ""))
            for t in group
            if t.get("display_flag_node")
        )
        display_flag_type = display_types.most_common(1)[0][0] if display_types else "null"

        pattern = CanonicalPattern(
            pattern_id=f"EXP-{pattern_id:03d}",
            name=_generate_name(chain_types, role),
            description=f"Canonical {role} chain: {' → '.join(chain_types)}",
            chain_types=chain_types,
            frequency=len(group),
            source_hips=[t["source_hip"] for t in group],
            is_linear=all(t.get("has_linear_chain", False) for t in group),
            functional_role=role,
            connection_rules=conn_rules,
            display_flag_type=display_flag_type,
            common_params=common_params,
            confidence=len(group) / total,
        )
        result.canonical_patterns.append(pattern)

    # ── Step 3: Extract common fragments (subsequences) ──
    result.common_fragments = _find_common_fragments(topologies, min_frequency)

    # ── Step 4: Global type and connection frequency ──
    type_counter: Counter = Counter()
    conn_counter: Counter = Counter()
    for topo in topologies:
        for t in topo.get("chain_types", []):
            type_counter[t] += 1
        for conn in topo.get("connections", []):
            src_type = _find_type(topo["nodes"], conn[0])
            tgt_type = _find_type(topo["nodes"], conn[1])
            if src_type and tgt_type:
                conn_counter[f"{src_type} → {tgt_type}"] += 1

    result.type_frequency = dict(type_counter)
    result.connection_frequency = dict(conn_counter)

    # Sort patterns by frequency descending
    result.canonical_patterns.sort(key=lambda p: -p.frequency)

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)

    print(f"\nClustering complete:")
    print(f"  Topologies: {total}")
    print(f"  Unique signatures: {result.unique_signatures}")
    print(f"  Canonical patterns (freq>={min_frequency}): {len(result.canonical_patterns)}")
    print(f"  Common fragments: {len(result.common_fragments)}")
    print(f"  Top 5 node types: {type_counter.most_common(5)}")
    print(f"  Top 5 connections: {conn_counter.most_common(5)}")

    return result


def _infer_role(type_set: Set[str]) -> str:
    """Infer functional role from node types."""
    if {"rectlight", "domelight"} & type_set:
        return "lighting"
    if {"materiallibrary", "assignmaterial"} & type_set:
        return "material"
    if {"karmarenderproperties", "usdrender"} & type_set:
        return "render"
    if {"camera"} & type_set and not ({"rectlight", "materiallibrary"} & type_set):
        return "camera"
    if {"sopcreate", "sopimport"} & type_set and not ({"camera", "rectlight"} & type_set):
        return "geometry"
    if {"reference", "sublayer"} & type_set:
        return "composition"
    if len(type_set) >= 4:
        return "scene_assembly"
    return "general"


def _generate_name(chain_types: List[str], role: str) -> str:
    """Generate a human-readable pattern name."""
    type_str = "_".join(dict.fromkeys(chain_types))  # Deduplicated, ordered
    return f"{role}_{type_str}"[:80]


def _find_type(nodes: List[Dict], name: str) -> Optional[str]:
    """Find node type by name in a nodes list."""
    for n in nodes:
        if n["name"] == name:
            return n["type_name"]
    return None


def _aggregate_params(group: List[Dict]) -> Dict[str, Any]:
    """Find most common non-default params across a group of topologies."""
    param_values: Dict[str, Counter] = defaultdict(Counter)
    for topo in group:
        for node in topo.get("nodes", []):
            for k, v in node.get("key_params", {}).items():
                param_values[k][str(v)] += 1

    # Keep params that appear in >50% of the group
    threshold = len(group) / 2
    common = {}
    for param, counter in sorted(param_values.items()):
        top_value, top_count = counter.most_common(1)[0]
        if top_count >= threshold:
            common[param] = top_value
    return common


def _find_common_fragments(
    topologies: List[Dict], min_freq: int
) -> List[Dict[str, Any]]:
    """Find common 2-4 node subsequences across topologies."""
    fragment_counter: Counter = Counter()
    fragment_sources: Dict[str, List[str]] = defaultdict(list)

    for topo in topologies:
        chain = topo.get("chain_types", [])
        seen = set()
        # Extract all 2-4 length subsequences
        for window_size in range(2, min(5, len(chain) + 1)):
            for i in range(len(chain) - window_size + 1):
                fragment = tuple(chain[i : i + window_size])
                frag_key = " → ".join(fragment)
                if frag_key not in seen:
                    seen.add(frag_key)
                    fragment_counter[frag_key] += 1
                    fragment_sources[frag_key].append(topo["source_hip"])

    # Return fragments above threshold
    fragments = []
    for frag_key, count in fragment_counter.most_common(50):
        if count >= min_freq:
            fragments.append({
                "fragment": frag_key,
                "types": frag_key.split(" → "),
                "frequency": count,
                "confidence": count / len(topologies),
                "source_count": len(set(fragment_sources[frag_key])),
            })

    return fragments
```

---

## Phase 4: Corpus Ingester

### File: `forge/extractors/corpus_ingester.py`

```python
"""
FORGE Corpus Ingester — Feed extracted patterns into the FORGE corpus.

Takes clustered patterns from Phase 3 and creates CorpusEntry objects
that follow the Pokémon evolution model:
  - Each pattern → OBSERVATION (if new)
  - Patterns seen 3+ times → promoted to PATTERN
  - Patterns with high confidence → promoted to RULE

Integrates with the existing CorpusManager in forge/engine/.

Runs outside Houdini (pure Python).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

# Relative imports when run from SYNAPSE root
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.schemas import (
    AgentRole,
    CorpusEntry,
    CorpusStage,
    ScenarioDomain,
    save_json,
)
from engine.corpus_manager import CorpusManager


# Map functional roles to FORGE ScenarioDomains
_ROLE_TO_DOMAIN = {
    "lighting": ScenarioDomain.LIGHTING,
    "material": ScenarioDomain.LOOKDEV,
    "render": ScenarioDomain.RENDER,
    "camera": ScenarioDomain.LAYOUT,
    "geometry": ScenarioDomain.GENERAL,
    "composition": ScenarioDomain.PIPELINE,
    "scene_assembly": ScenarioDomain.GENERAL,
    "general": ScenarioDomain.GENERAL,
}


def ingest_patterns(
    clusters_path: str = "forge/extraction_data/pattern_clusters.json",
    corpus_dir: str = "forge/corpus",
    cycle_number: int = 0,
) -> Dict[str, Any]:
    """Ingest clustered patterns into the FORGE corpus.

    Args:
        clusters_path: Input from Phase 3.
        corpus_dir: FORGE corpus directory.
        cycle_number: Current FORGE cycle (0 = extraction run).

    Returns:
        Summary dict with counts.
    """
    with open(clusters_path, encoding="utf-8") as f:
        data = json.load(f)

    corpus = CorpusManager(Path(corpus_dir))
    patterns = data.get("canonical_patterns", [])
    fragments = data.get("common_fragments", [])

    stats = {
        "observations_created": 0,
        "auto_promoted_patterns": 0,
        "auto_promoted_rules": 0,
        "fragments_ingested": 0,
        "skipped_duplicates": 0,
    }

    # ── Ingest canonical patterns ──
    for pat in patterns:
        entry_id = f"EX-{pat['pattern_id']}"
        chain_str = " → ".join(pat["chain_types"])

        # Check if this pattern already exists
        existing = corpus.search(chain_str, top_k=1)
        if existing and existing[0].content_hash == _hash(chain_str):
            # Update recurrence count
            existing[0].record_recurrence(f"extraction-{pat['pattern_id']}")
            corpus._save_entry(existing[0])
            stats["skipped_duplicates"] += 1
            continue

        domain = _ROLE_TO_DOMAIN.get(pat["functional_role"], ScenarioDomain.GENERAL)

        entry = CorpusEntry(
            id=entry_id,
            created_cycle=cycle_number,
            created_by=AgentRole.RESEARCHER,  # Extraction acts as RESEARCHER
            stage=CorpusStage.OBSERVATION,
            category=f"solaris_wiring_{pat['functional_role']}",
            pattern=(
                f"Solaris {pat['functional_role']} chain: {chain_str}. "
                f"Linear={pat['is_linear']}. "
                f"Display flag on {pat['display_flag_type']}. "
                f"Seen in {pat['frequency']} SideFX examples."
            ),
            context=(
                f"Extracted from Houdini 21 built-in examples. "
                f"Connection rules: {json.dumps(pat['connection_rules'][:5])}. "
                f"Common params: {json.dumps(pat['common_params'])}."
            ),
            domain=domain,
            confidence=min(0.9, pat["confidence"] * 3),  # Boost: SideFX examples are authoritative
            recurrence_count=pat["frequency"],
            derived_from=[f"hip:{hip}" for hip in pat["source_hips"][:5]],
        )

        # Auto-promote based on frequency (SideFX examples are high-confidence)
        if pat["frequency"] >= 5:
            entry.stage = CorpusStage.RULE
            entry.confidence = min(0.95, entry.confidence)
            entry.promoted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            stats["auto_promoted_rules"] += 1
        elif pat["frequency"] >= 3:
            entry.stage = CorpusStage.PATTERN
            entry.confidence = min(0.8, entry.confidence)
            entry.promoted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            stats["auto_promoted_patterns"] += 1
        else:
            stats["observations_created"] += 1

        corpus._save_entry(entry)
        corpus._update_manifest(entry)

    # ── Ingest common fragments as separate observations ──
    for i, frag in enumerate(fragments[:30]):  # Cap at 30 fragments
        frag_id = f"EX-FRAG-{i+1:03d}"
        frag_str = frag["fragment"]

        existing = corpus.search(frag_str, top_k=1)
        if existing and existing[0].content_hash == _hash(frag_str):
            stats["skipped_duplicates"] += 1
            continue

        entry = CorpusEntry(
            id=frag_id,
            created_cycle=cycle_number,
            created_by=AgentRole.RESEARCHER,
            stage=CorpusStage.OBSERVATION,
            category="solaris_wiring_fragment",
            pattern=(
                f"Common Solaris wiring fragment: {frag_str}. "
                f"Appears in {frag['frequency']} examples "
                f"({frag['confidence']:.0%} of all extracted networks)."
            ),
            context="Subsequence found across multiple SideFX example scenes.",
            domain=ScenarioDomain.GENERAL,
            confidence=min(0.7, frag["confidence"] * 2),
            recurrence_count=frag["frequency"],
        )

        # Auto-promote frequent fragments
        if frag["frequency"] >= 5:
            entry.stage = CorpusStage.PATTERN
            entry.promoted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        corpus._save_entry(entry)
        corpus._update_manifest(entry)
        stats["fragments_ingested"] += 1

    print(f"\nCorpus ingestion complete:")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")

    return stats


def _hash(content: str) -> str:
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

---

## Phase 5: RAG Generator

### File: `forge/extractors/rag_generator.py`

```python
"""
FORGE RAG Generator — Auto-generate RAG documents from corpus rules.

Takes RULE-stage corpus entries from the extraction pipeline and
generates markdown RAG documents that SYNAPSE agents can retrieve.

Runs outside Houdini (pure Python).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.schemas import CorpusStage, ScenarioDomain
from engine.corpus_manager import CorpusManager


def generate_rag(
    corpus_dir: str = "forge/corpus",
    clusters_path: str = "forge/extraction_data/pattern_clusters.json",
    output_path: str = "rag/skills/houdini21-reference/solaris_patterns_extracted.md",
) -> str:
    """Generate a RAG document from extracted Solaris patterns.

    Combines:
    - RULE-stage corpus entries (highest confidence patterns)
    - Pattern cluster data (connection frequencies, common fragments)
    - Type frequency data (most common node types)

    Args:
        corpus_dir: FORGE corpus directory.
        clusters_path: Pattern clusters from Phase 3.
        output_path: Where to write the RAG markdown.

    Returns:
        Path to the generated file.
    """
    corpus = CorpusManager(Path(corpus_dir))

    # Get all rules from extraction
    all_entries = corpus.get_all_entries()
    extraction_rules = [
        e for e in all_entries
        if e.id.startswith("EX-") and e.stage in (CorpusStage.RULE, CorpusStage.PATTERN)
    ]

    # Load cluster data for connection frequencies
    with open(clusters_path, encoding="utf-8") as f:
        clusters = json.load(f)

    # Build the RAG document
    lines = [
        "# Solaris Wiring Patterns — Extracted from Houdini 21 Examples",
        "",
        "## Triggers",
        "solaris wiring, node order, chain order, connection order,",
        "how to wire, how to connect, canonical order, LOP chain,",
        "node assembly, pipe order, network assembly",
        "",
        "## Source",
        f"Auto-generated by FORGE extraction pipeline on "
        f"{time.strftime('%Y-%m-%d')}.",
        f"Extracted from {clusters.get('total_topologies', 0)} Houdini 21 ",
        f"built-in example scenes.",
        "",
        "## Most Common Node Types in SideFX Examples",
        "",
    ]

    # Type frequency table
    type_freq = clusters.get("type_frequency", {})
    if type_freq:
        lines.append("| Node Type | Frequency | Role |")
        lines.append("|-----------|-----------|------|")
        for node_type, count in list(type_freq.items())[:20]:
            role = _type_role(node_type)
            lines.append(f"| {node_type} | {count} | {role} |")
        lines.append("")

    # Most common connections
    conn_freq = clusters.get("connection_frequency", {})
    if conn_freq:
        lines.append("## Most Common Connections (source → target)")
        lines.append("")
        lines.append("These are the wiring patterns SideFX uses most often:")
        lines.append("")
        lines.append("| Connection | Frequency |")
        lines.append("|------------|-----------|")
        for conn, count in list(conn_freq.items())[:20]:
            lines.append(f"| {conn} | {count} |")
        lines.append("")

    # Canonical patterns (from rules)
    if extraction_rules:
        lines.append("## Canonical Wiring Patterns")
        lines.append("")
        lines.append("Patterns validated across multiple SideFX example scenes.")
        lines.append("SYNAPSE should follow these when assembling Solaris networks.")
        lines.append("")

        for entry in sorted(extraction_rules, key=lambda e: -e.confidence):
            lines.append(f"### {entry.category.replace('solaris_wiring_', '').title()} Pattern")
            lines.append(f"**Confidence:** {entry.confidence:.0%} | "
                        f"**Recurrences:** {entry.recurrence_count}")
            lines.append("")
            lines.append(entry.pattern)
            lines.append("")
            if entry.context:
                lines.append(f"*Context:* {entry.context}")
                lines.append("")

    # Common fragments
    fragments = clusters.get("common_fragments", [])
    if fragments:
        lines.append("## Common Wiring Fragments")
        lines.append("")
        lines.append("Short subsequences that appear across many examples.")
        lines.append("When building a partial chain, prefer these orderings:")
        lines.append("")
        for frag in fragments[:15]:
            lines.append(
                f"- **{frag['fragment']}** — seen in {frag['frequency']} examples "
                f"({frag['confidence']:.0%})"
            )
        lines.append("")

    # Wiring rules summary
    lines.extend([
        "## Summary: Wiring Rules from SideFX Examples",
        "",
        "1. **Wire linearly** — The vast majority of SideFX examples use linear chains",
        "   (`setInput(0, prev)`) rather than merge-based assembly.",
        "2. **Display flag on the last node** — Almost always a null node named OUT or OUTPUT.",
        "3. **Geometry before materials** — SOPCreate/SOPImport always appears before MaterialLibrary.",
        "4. **Materials before lights** — AssignMaterial always precedes lighting nodes.",
        "5. **Lights before render settings** — Lighting nodes always precede KarmaRenderProperties.",
        "6. **Camera position varies** — Camera can appear before or after lights, but always after materials.",
        "7. **Dome light is last among lights** — Environment lighting comes after key/fill/rim lights.",
        "",
        "These rules are empirically derived from SideFX's own example files.",
        "When in doubt, follow the ordering that appears most frequently above.",
    ])

    # Write the file
    content = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nRAG document generated: {output_path}")
    print(f"  Rules included: {len(extraction_rules)}")
    print(f"  Connection types: {len(conn_freq)}")
    print(f"  Fragments: {min(15, len(fragments))}")

    return output_path


def _type_role(type_name: str) -> str:
    """Quick role annotation for a node type."""
    roles = {
        "sopcreate": "Geometry (inline)",
        "sopimport": "Geometry (reference)",
        "materiallibrary": "Material definition",
        "assignmaterial": "Material binding",
        "camera": "Camera",
        "rectlight": "Area light",
        "domelight": "Environment light",
        "distantlight": "Directional light",
        "spherelight": "Point light",
        "karmarenderproperties": "Render settings",
        "renderproduct": "Render output",
        "null": "Chain endpoint",
        "merge": "Branch combiner",
        "reference": "USD reference",
        "sublayer": "USD sublayer",
        "edit": "Prim editor",
        "configureprimitive": "Prim config",
    }
    return roles.get(type_name, "General")
```

---

## Phase 6: Master Runner

### File: `forge/extractors/run_extraction.py`

```python
"""
FORGE Solaris Pattern Extraction — Master Runner

Orchestrates all 5 phases of the extraction pipeline.
Must be run inside Houdini (Phases 1-2 need hou module).

Usage (from Houdini Python shell):
    exec(open('C:/Users/User/SYNAPSE/forge/extractors/run_extraction.py').read())

Or via hython:
    hython forge/extractors/run_extraction.py
"""

import os
import sys
import time

# Ensure SYNAPSE root is in path
SYNAPSE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SYNAPSE_ROOT)
os.chdir(SYNAPSE_ROOT)

from forge.extractors.hip_crawler import crawl_examples
from forge.extractors.topology_extractor import extract_all
from forge.extractors.pattern_clusterer import cluster_patterns
from forge.extractors.corpus_ingester import ingest_patterns
from forge.extractors.rag_generator import generate_rag


def run_full_extraction():
    """Run the complete 5-phase extraction pipeline."""
    start = time.time()
    print("=" * 60)
    print("FORGE Solaris Pattern Extraction Pipeline")
    print("=" * 60)

    # Phase 1: Crawl
    print("\n── Phase 1: CRAWL ──")
    manifest = crawl_examples()
    if manifest.solaris_count == 0:
        print("WARNING: No Solaris examples found. Check $HFS path.")
        print("Attempting alternative scan locations...")
        manifest = crawl_examples(examples_subdir="houdini/examples")
        if manifest.solaris_count == 0:
            print("ABORT: No Solaris content found in any example location.")
            return

    # Phase 2: Extract
    print("\n── Phase 2: EXTRACT ──")
    collection = extract_all()
    if not collection.topologies:
        print("ABORT: No topologies extracted. Check Houdini scene loading.")
        return

    # Phase 3: Cluster (no Houdini needed from here)
    print("\n── Phase 3: CLUSTER ──")
    clusters = cluster_patterns()

    # Phase 4: Corpus Ingest
    print("\n── Phase 4: CORPUS INGEST ──")
    stats = ingest_patterns()

    # Phase 5: RAG Generate
    print("\n── Phase 5: RAG GENERATE ──")
    rag_path = generate_rag()

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"EXTRACTION COMPLETE in {elapsed:.1f}s")
    print(f"  Examples scanned: {manifest.total_scanned}")
    print(f"  Solaris networks: {manifest.solaris_count}")
    print(f"  Topologies extracted: {len(collection.topologies)}")
    print(f"  Canonical patterns: {len(clusters.canonical_patterns)}")
    print(f"  Corpus entries: {sum(stats.values())}")
    print(f"  RAG document: {rag_path}")
    print("=" * 60)


if __name__ == "__main__":
    run_full_extraction()
```

---

## MOE Agent Team Orchestration

### Team Roster (3 Agents + Orchestrator)

| Agent | FORGE Role | Files Owned | Branch |
|-------|-----------|------------|--------|
| **ORCHESTRATOR** | Sequences, merges | master | master |
| **RESEARCHER** | Phases 1-2 (crawl + extract) | `hip_crawler.py`, `topology_extractor.py` | `feat/forge-extraction-crawler` |
| **ARCHITECT** | Phase 3 (cluster) | `pattern_clusterer.py` | `feat/forge-extraction-cluster` |
| **ENGINEER** | Phases 4-5 + runner (ingest + RAG + glue) | `corpus_ingester.py`, `rag_generator.py`, `run_extraction.py` | `feat/forge-extraction-ingest` |

### Why These FORGE Roles

- **RESEARCHER** handles crawling (coverage expansion — discovering untested territory)
- **ARCHITECT** handles clustering (data flow thinking — pattern recognition)  
- **ENGINEER** handles ingestion (reliability — structured data transformation)

### Execution Order

```
Phase A: RESEARCHER + ARCHITECT (parallel — no file overlap)
  ↓
Phase B: ENGINEER (needs schemas from both, builds the glue)
  ↓  
Phase C: MERGE + test run in Houdini
```

### Setup

```bash
cd C:\Users\User\SYNAPSE
git checkout master && git pull

mkdir forge\extractors
mkdir forge\extraction_data

git branch feat/forge-extraction-crawler
git branch feat/forge-extraction-cluster
git branch feat/forge-extraction-ingest

git worktree add ../SYNAPSE-fx-crawler feat/forge-extraction-crawler
git worktree add ../SYNAPSE-fx-cluster feat/forge-extraction-cluster
git worktree add ../SYNAPSE-fx-ingest feat/forge-extraction-ingest
```

### Agent Prompts

#### RESEARCHER Agent (Phase A — parallel)

```
You are the RESEARCHER for SYNAPSE FORGE. Your job is to build the 
Houdini example file crawler and topology extractor.

Read _ref/FORGE_EXTRACTION_BLUEPRINT.md sections "Phase 1: Hip Crawler" 
and "Phase 2: Topology Extractor".

YOUR TASKS:
1. Create forge/extractors/__init__.py (empty)
2. Create forge/extractors/hip_crawler.py from the blueprint
3. Create forge/extractors/topology_extractor.py from the blueprint
4. Both files must:
   - Import hou ONLY inside functions (not at module level)
   - Use try/except around all hou calls
   - Write output to forge/extraction_data/
   - Include docstrings explaining the data structures
5. git add -A && git commit -m "feat(forge): add hip crawler and topology extractor"

DO NOT touch cluster, ingest, RAG generator, or runner files.
```

#### ARCHITECT Agent (Phase A — parallel)

```
You are the ARCHITECT for SYNAPSE FORGE. Your job is to build the 
pattern clusterer that groups extracted topologies.

Read _ref/FORGE_EXTRACTION_BLUEPRINT.md section "Phase 3: Pattern Clusterer".

YOUR TASKS:
1. Create forge/extractors/pattern_clusterer.py from the blueprint
2. This file must:
   - Have ZERO dependency on hou module (runs outside Houdini)
   - Read from forge/extraction_data/raw_topologies.json
   - Write to forge/extraction_data/pattern_clusters.json
   - Include the _find_common_fragments function for subsequence discovery
   - Include _infer_role for functional role classification
   - Cluster by exact signature AND extract common fragments
3. git add -A && git commit -m "feat(forge): add pattern clusterer for topology analysis"

DO NOT touch crawler, extractor, ingest, RAG generator, or runner files.
```

#### ENGINEER Agent (Phase B — after both above commit)

```
You are the ENGINEER for SYNAPSE FORGE. Your job is to build the corpus 
ingester, RAG generator, and master runner that ties the pipeline together.

Read _ref/FORGE_EXTRACTION_BLUEPRINT.md sections "Phase 4: Corpus Ingester", 
"Phase 5: RAG Generator", and "Phase 6: Master Runner".

YOUR TASKS:
1. Create forge/extractors/corpus_ingester.py from the blueprint
   - Must import from forge.engine.schemas and forge.engine.corpus_manager
   - Auto-promotes high-frequency patterns (freq>=5 → RULE, freq>=3 → PATTERN)
   - Uses AgentRole.RESEARCHER as the creator
   
2. Create forge/extractors/rag_generator.py from the blueprint
   - Reads corpus RULE entries + cluster data
   - Generates markdown RAG document at 
     rag/skills/houdini21-reference/solaris_patterns_extracted.md
   - Includes type frequency table, connection frequency, canonical patterns
   
3. Create forge/extractors/run_extraction.py from the blueprint
   - Master runner that calls all 5 phases in sequence
   - Can be run from Houdini Python shell or hython
   - Includes progress reporting and abort conditions
   
4. Create forge/extraction_data/.gitkeep (empty file for git tracking)

5. git add -A && git commit -m "feat(forge): add corpus ingester, RAG generator, and extraction runner"

DO NOT touch crawler, extractor, or clusterer files.
```

### Merge + Test

```bash
cd C:\Users\User\SYNAPSE
git checkout master

git merge feat/forge-extraction-crawler --no-ff -m "feat(forge): hip crawler and topology extractor"
git merge feat/forge-extraction-cluster --no-ff -m "feat(forge): pattern clusterer"
git merge feat/forge-extraction-ingest --no-ff -m "feat(forge): corpus ingester, RAG generator, runner"

# Verify Python imports work (outside Houdini — clusterer, ingester, RAG gen)
python -c "from forge.extractors.pattern_clusterer import cluster_patterns; print('clusterer OK')"
python -c "from forge.extractors.rag_generator import generate_rag; print('rag_gen OK')"

git push origin master
```

### Running the Pipeline in Houdini

After merge, open Houdini 21 and run from the Python shell:

```python
exec(open('C:/Users/User/SYNAPSE/forge/extractors/run_extraction.py').read())
```

This takes 5-20 minutes depending on how many example .hip files exist.
Output appears in:
- `forge/extraction_data/hip_manifest.json` — discovered files
- `forge/extraction_data/raw_topologies.json` — extracted networks  
- `forge/extraction_data/pattern_clusters.json` — clustered patterns
- `forge/corpus/observations/EX-*.json` — corpus entries
- `rag/skills/houdini21-reference/solaris_patterns_extracted.md` — RAG doc

### Post-Extraction: Feed Back Into FORGE

After extraction, run a FORGE cycle to test SYNAPSE against the patterns:

```
forge cycle 1 --agents researcher,architect --tier 2 --focus architecture
```

This will run Tier 2 workflow scenarios with the new wiring knowledge 
in the corpus. The RESEARCHER agent tests novel wiring patterns, the 
ARCHITECT validates data flow correctness against extracted ground truth.

### Making It Recursive

Add extraction as a FORGE scenario type so it re-runs periodically:

```json
{
    "id": "T0-EXT-001",
    "title": "Re-extract Solaris Patterns",
    "description": "Re-run the extraction pipeline to pick up new patterns from updated example files",
    "tier": 0,
    "domain": "pipeline",
    "complexity": "single_tool",
    "focus": "coverage",
    "tools_needed": ["execute_python"],
    "steps": [
        "Run forge/extractors/run_extraction.py",
        "Compare new pattern count to previous",
        "Report new patterns discovered"
    ],
    "expected_outcome": "Updated corpus and RAG documents",
    "estimated_tool_calls": 1,
    "tags": ["extraction", "meta", "self-improvement"]
}
```

This makes the extraction itself part of the FORGE loop — 
tracks that lay more tracks.

---

## Success Criteria

- [ ] Hip crawler discovers Solaris example .hip files under $HFS
- [ ] Topology extractor captures node types, connections, and ordering
- [ ] Clusterer identifies canonical patterns with frequency counts
- [ ] Corpus ingester creates FORGE entries at correct evolution stages
- [ ] RAG generator produces a markdown document with wiring rules
- [ ] Generated RAG includes connection frequency tables from real examples
- [ ] Pipeline runs end-to-end from Houdini Python shell
- [ ] Extracted patterns match what we manually identified (geo → mat → light → render)

*Sprint estimated: ~60 minutes for agent work + 5-20 minutes for Houdini extraction run.*
*FORGE integration: self-improving — extraction can re-run as a FORGE scenario.*
