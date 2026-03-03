"""
FORGE Topology Extractor -- Extract network wiring from Solaris scenes.

For each .hip in the manifest, loads the scene, walks the /stage network,
and records the full topology: node types, connections, ordering, and
parameter states.

Leverages the existing network_explain handler patterns but runs
directly (no MCP round-trip) for speed.

Run inside Houdini's Python shell or via hython.

Data structures:
    NodeRecord: Extracted information about a single LOP node, including its
        name, type, position, input/output connections, display/render flags,
        USD prim path if set, and non-default parameter values.

    TopologyRecord: Complete topology of a single /stage network. Contains all
        NodeRecords in topological order, a chain_signature hash for clustering,
        connection pairs, linearity analysis, branch count, and detected
        Solaris workflow patterns (e.g., "material_assignment", "karma_render").

    TopologyCollection: All extracted topologies from a crawl run, with
        metadata (timestamp, counts, errors). Serializes to
        forge/extraction_data/raw_topologies.json via .to_dict().
"""

from __future__ import annotations

import hashlib
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
    key_params: Dict[str, Any]  # Non-default parameter values


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
        json.dump(collection.to_dict(), f, indent=2, sort_keys=False)

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

        # Topological sort (Kahn's algorithm -- same as handlers_node.py)
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
