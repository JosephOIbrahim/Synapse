"""
SYNAPSE APEX Graph Trace -- Introspection for APEX graphs in Houdini.

Reads the APEX graph a node carries, determines execution order via
topological sort, and presents the result as HTML (for the panel) or plain
text (for Claude).

An APEX graph is a program stored as geometry: one point per graph node and
one two-vertex primitive per wire. A rigged character holds its graph in a
packed folder (``Base.rig``), and a scene nests the character one folder
deeper. The geometry reads live in ``synapse.server.apex_graph`` (layout
measured on Houdini 22.0.466); this module turns that read into a trace.

A node whose own output holds no graph (Scene Invoke outputs the posed mesh)
is traced from the nearest input upstream that does.

All hou access is individually guarded so failures never break the trace.
Outside Houdini the module imports cleanly and trace_apex_graph() returns
an empty trace immediately.
"""

from __future__ import annotations

from synapse.panel.designsystem import tokens as _ds

import html
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Houdini import guard
# ---------------------------------------------------------------------------
_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Graph geometry reader guard
# ---------------------------------------------------------------------------
APEX_GRAPH_AVAILABLE = False
try:
    from synapse.server import apex_graph as _apex_graph
    APEX_GRAPH_AVAILABLE = True
except ImportError:
    _apex_graph = None  # type: ignore[assignment]

# Past this many nodes the longest-chain search is skipped (it is the one
# step here that is not linear in the graph).
_CRITICAL_PATH_NODE_CAP = 2000

# Wires printed by the formatters before the rest are counted, not listed.
_FLOW_LINES_CAP = 200


# ============================================================================
# Data classes
# ============================================================================

@dataclass
class ApexGraphNode:
    """One node within an APEX graph."""

    name: str               # node name within the graph
    node_type: str          # operation type (e.g. "TransformObject", "GetAttribute")
    category: str           # "transform", "attribute", "math", "logic", "solver", "deform", "other"
    inputs: list            # input connection names
    outputs: list           # output connection names
    description: str        # brief description of what this operation does
    tags: list = field(default_factory=list)   # graph tags, e.g. ["control"]


@dataclass
class ApexGraphTrace:
    """Result of tracing an APEX graph from an Invoke SOP."""

    invoke_path: str        # path to the Invoke SOP
    graph_name: str         # name/label of the APEX graph
    node_count: int = 0
    nodes: list = field(default_factory=list)       # List[ApexGraphNode] in execution order
    data_flow: list = field(default_factory=list)   # [(src_name, dst_name, port), ...]
    summary: str = ""
    critical_path: list = field(default_factory=list)  # names on longest eval chain
    wire_count: int = 0
    controls: list = field(default_factory=list)       # names of nodes tagged "control"
    graph_folder: str = ""  # packed folder the graph was read from, e.g. "Base.rig"
    graph_source: str = ""  # node the graph was read from (may be upstream of invoke_path)
    graph_inputs: list = field(default_factory=list)   # names promoted on __parms__
    graph_outputs: list = field(default_factory=list)  # names promoted on __output__


# ============================================================================
# Operation categorization
# ============================================================================

_CATEGORY_MAP: Dict[str, List[str]] = {
    "transform": [
        "TransformObject", "SetTransform", "GetTransform", "BlendTransform",
        "ComposeTransform", "InvertTransform", "DecomposeTransform",
        "TransformPoint", "TransformVector", "TransformNormal",
        "Translate", "Rotate", "Scale", "LookAt",
    ],
    "attribute": [
        "GetAttribute", "SetAttribute", "AttributeMap", "PromoteAttribute",
        "CopyAttribute", "RenameAttribute", "DeleteAttribute",
        "GetPointAttribute", "SetPointAttribute",
        "GetPrimAttribute", "SetPrimAttribute",
        "GetDetailAttribute", "SetDetailAttribute",
    ],
    "math": [
        "Add", "Subtract", "Multiply", "Divide", "Negate",
        "Lerp", "Clamp", "Fit", "Remap", "Abs", "Floor", "Ceil",
        "Sin", "Cos", "Sqrt", "Pow", "Dot", "Cross", "Normalize",
        "Length", "Distance", "Min", "Max", "Mod",
        "MatrixMultiply", "QuaternionMultiply", "QuaternionToMatrix",
        "SetComponent", "GetComponent",
    ],
    # Flow control. Named "logic" so it can never be read as rig controls,
    # which are the nodes tagged ``control``.
    "logic": [
        "Switch", "TwoWaySwitch", "Branch", "Loop", "ForEach", "If", "While",
        "Compare", "And", "Or", "Not", "Select",
    ],
    "solver": [
        "FKSolver", "IKSolver", "FBIK", "FBIKSolver",
        "SpringSolver", "RBDSolver", "MotionClip",
        "SolveFK", "SolveIK", "SolveFBIK", "TwoBoneIK",
    ],
    "constraint": [
        "ParentConstraint", "AimConstraint", "PointConstraint",
        "OrientConstraint", "ScaleConstraint", "PoleVectorConstraint",
        "BlendConstraint",
    ],
    "io": [
        "Input", "Output", "Pack", "Unpack",
        "Import", "Export", "Fetch", "Store",
        "GraphInput", "GraphOutput", "SubGraphInput", "SubGraphOutput",
        "__parms__", "__output__",
    ],
}

# Callbacks whose namespace decides the category. ``geo::Transform`` moves
# geometry; without its namespace it would read as a rig transform.
_FULL_NAME_CATEGORY: Dict[str, str] = {
    "geo::Transform": "deform",
    "sop::bonedeform": "deform",
    "skel::SetPointTransforms": "deform",
}

# Build reverse lookup: operation_name -> category
_OP_TO_CATEGORY: Dict[str, str] = {}
for _cat, _ops in _CATEGORY_MAP.items():
    for _op in _ops:
        _OP_TO_CATEGORY[_op] = _cat


def _base_callback(type_name: str) -> str:
    """A callback's bare name: ``rig::TwoBoneIK`` -> ``TwoBoneIK``,
    ``Multiply<Matrix4>`` -> ``Multiply``."""
    return type_name.rsplit("::", 1)[-1].split("<", 1)[0]


def categorize_apex_operation(type_name: str) -> str:
    """Map an APEX callback name to a category string.

    Returns one of: "transform", "attribute", "math", "logic", "solver",
    "constraint", "deform", "io", or "other".

    The full name is matched first, then the bare name with its namespace and
    ``<Type>`` suffix removed. Both are exact matches: a substring match would
    file ``geo::Transform`` and ``SetComponent<Vector3>`` under the two-letter
    op ``Or``.
    """
    if type_name in _FULL_NAME_CATEGORY:
        return _FULL_NAME_CATEGORY[type_name]
    if type_name in _OP_TO_CATEGORY:
        return _OP_TO_CATEGORY[type_name]
    base = _base_callback(type_name)
    if base in _OP_TO_CATEGORY:
        return _OP_TO_CATEGORY[base]

    # Heuristic fallback on the bare name
    lower = base.lower()
    if lower.endswith("switch"):
        return "logic"
    if "deform" in lower:
        return "deform"
    if "transform" in lower or "xform" in lower:
        return "transform"
    if "attrib" in lower:
        return "attribute"
    if "solver" in lower or "solve" in lower:
        return "solver"
    if "constraint" in lower:
        return "constraint"
    if "input" in lower or "output" in lower:
        return "io"

    return "other"


# ============================================================================
# Description helper
# ============================================================================

_OP_DESCRIPTIONS: Dict[str, str] = {
    "TransformObject": "Applies a transform to an object",
    "SetTransform": "Sets the transform matrix directly",
    "GetTransform": "Reads the current transform matrix",
    "BlendTransform": "Blends between two transforms",
    "GetAttribute": "Reads an attribute value",
    "SetAttribute": "Writes an attribute value",
    "Add": "Adds two values",
    "Multiply": "Multiplies two values",
    "Lerp": "Linear interpolation between two values",
    "Clamp": "Clamps a value to a range",
    "FKSolver": "Forward kinematics solver",
    "IKSolver": "Inverse kinematics solver",
    "FBIK": "Full-body inverse kinematics",
    "FBIKSolver": "Full-body IK solver",
    "SpringSolver": "Spring-based dynamics solver",
    "ParentConstraint": "Constrains to a parent transform",
    "AimConstraint": "Constrains orientation to aim at a target",
    "PointConstraint": "Constrains position to a target point",
    "Input": "Graph input port",
    "Output": "Graph output port",
    "GraphInput": "Subgraph input boundary",
    "GraphOutput": "Subgraph output boundary",
    "Switch": "Selects between inputs based on a condition",
    "Branch": "Conditional execution branch",
    "Loop": "Iterative loop over elements",
    "Pack": "Packs geometry into a packed primitive",
    "Unpack": "Unpacks a packed primitive",
    "Normalize": "Normalizes a vector to unit length",
    "Dot": "Dot product of two vectors",
    "Cross": "Cross product of two vectors",
    "LookAt": "Computes a look-at rotation matrix",
    "TwoBoneIK": "Two-bone IK chain solver",
    "TwoWaySwitch": "Chooses between two inputs",
    "Value": "Holds a constant value",
    "SetComponent": "Sets one component of a vector",
    "__parms__": "Graph inputs: the values the rig is driven by",
    "__output__": "Graph outputs: what the rig hands back",
    "geo::Transform": "Moves a group of the shape by a matrix (rigid deform)",
    "sop::bonedeform": "Runs Bone Deform on the shape, inside the graph",
    "skel::SetPointTransforms": "Writes transforms onto the skeleton's joints",
}


def _describe_operation(type_name: str) -> str:
    """Return a brief human-readable description for an APEX operation."""
    if type_name in _OP_DESCRIPTIONS:
        return _OP_DESCRIPTIONS[type_name]
    base = _base_callback(type_name)
    if base in _OP_DESCRIPTIONS:
        return _OP_DESCRIPTIONS[base]
    cat = categorize_apex_operation(type_name)
    if cat != "other":
        return f"{cat.capitalize()} operation"
    return "APEX graph operation"


# ============================================================================
# Graph extraction helpers
# ============================================================================

def _nodes_from_graph(
    graph: Dict[str, Any],
) -> Tuple[List[ApexGraphNode], List[Tuple[str, str, str]]]:
    """Turn one graph read (``apex_graph.read_graph`` with nodes and wires)
    into trace nodes and ``(source, destination, port)`` connections.

    The port label reads ``source_port -> destination_port``.
    """
    nodes: List[ApexGraphNode] = []
    connections: List[Tuple[str, str, str]] = []
    in_ports: Dict[str, List[str]] = {}
    out_ports: Dict[str, List[str]] = {}

    for wire in graph.get("wires", []):
        src = wire.get("source", "")
        dst = wire.get("destination", "")
        sp = wire.get("source_port", "")
        dp = wire.get("destination_port", "")
        if not src or not dst:
            continue
        label = f"{sp} -> {dp}" if (sp or dp) else ""
        connections.append((src, dst, label))
        if sp and sp not in out_ports.setdefault(src, []):
            out_ports[src].append(sp)
        if dp and dp not in in_ports.setdefault(dst, []):
            in_ports[dst].append(dp)

    for row in graph.get("nodes", []):
        name = str(row.get("name", ""))
        callback = str(row.get("callback", "unknown"))
        nodes.append(ApexGraphNode(
            name=name,
            node_type=callback,
            category=categorize_apex_operation(callback),
            inputs=in_ports.get(name, []),
            outputs=out_ports.get(name, []),
            description=_describe_operation(callback),
            tags=list(row.get("tags", [])),
        ))
    return nodes, connections


def _extract_graph_nodes_from_geo(
    geo: Any,
) -> Tuple[List[ApexGraphNode], List[Tuple[str, str, str]]]:
    """Extract APEX graph nodes and connections from graph geometry.

    Points are the graph's nodes and two-vertex primitives are its wires.
    Geometry that is not a graph (a mesh, a skeleton) returns two empty
    lists without being walked.

    Returns (nodes_list, connections_list).
    """
    if geo is None or not APEX_GRAPH_AVAILABLE:
        return [], []
    graph = _apex_graph.read_graph(geo, include_nodes=True, include_wires=True)
    if graph is None or not graph.get("read"):
        return [], []
    return _nodes_from_graph(graph)


def _read_node_geometry(node: Any) -> Any:
    """Geometry reader for an explicit trace: the artist asked for this node,
    so it may cook, exactly as ``trace_apex_graph`` always has."""
    try:
        return node.geometry()
    except Exception:
        logger.debug("geometry unavailable", exc_info=True)
        return None


def _find_graphs(node: Any) -> Tuple[Optional[Dict[str, Any]], str, int]:
    """(read, source node path, distance) for the graph *node* carries.

    The node's own output first; if it holds no graph, the nearest input
    upstream that does. ``read`` is None when no graph was found.
    """
    found = _apex_graph.find_graphs(
        node, _read_node_geometry, include_nodes=True, include_wires=True)
    return found["summary"], found["source"] or "", found["distance"]


def _topological_sort(
    nodes: List[ApexGraphNode],
    connections: List[Tuple[str, str, str]],
) -> List[ApexGraphNode]:
    """Sort nodes in execution order using topological sort.

    Falls back to the original order if sorting is not possible
    (e.g. no connection data, cycles).
    """
    if not connections or not nodes:
        # Without connections, put io:input first, io:output last,
        # keep everything else in original order
        inputs = [n for n in nodes if n.category == "io" and "input" in n.node_type.lower()]
        outputs = [n for n in nodes if n.category == "io" and "output" in n.node_type.lower()]
        middle = [n for n in nodes if n not in inputs and n not in outputs]
        return inputs + middle + outputs

    name_to_node: Dict[str, ApexGraphNode] = {n.name: n for n in nodes}
    in_degree: Dict[str, int] = {n.name: 0 for n in nodes}
    adjacency: Dict[str, List[str]] = {n.name: [] for n in nodes}

    for src, dst, _ in connections:
        if src in adjacency and dst in in_degree:
            adjacency[src].append(dst)
            in_degree[dst] += 1

    # Kahn's algorithm
    queue: deque = deque()
    for name, deg in in_degree.items():
        if deg == 0:
            queue.append(name)

    sorted_names: List[str] = []
    while queue:
        name = queue.popleft()
        sorted_names.append(name)
        for neighbor in adjacency.get(name, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # If sort is incomplete (cycle or missing nodes), append remainder
    sorted_set = set(sorted_names)
    for n in nodes:
        if n.name not in sorted_set:
            sorted_names.append(n.name)

    return [name_to_node[n] for n in sorted_names if n in name_to_node]


def _find_critical_path(
    nodes: List[ApexGraphNode],
    connections: List[Tuple[str, str, str]],
) -> List[str]:
    """Find the longest chain from any source to any sink.

    Returns list of node names on the critical path.
    """
    if not connections or not nodes:
        return [n.name for n in nodes]

    name_set = {n.name for n in nodes}
    adjacency: Dict[str, List[str]] = {n.name: [] for n in nodes}
    predecessors: Dict[str, List[str]] = {n.name: [] for n in nodes}

    for src, dst, _ in connections:
        if src in name_set and dst in name_set:
            adjacency[src].append(dst)
            predecessors[dst].append(src)

    # Find sources (no predecessors with actual connections)
    sources = [n.name for n in nodes if not predecessors.get(n.name)]
    if not sources:
        sources = [nodes[0].name]

    # BFS/DFS for longest path from any source
    best_path: List[str] = []

    for source in sources:
        # BFS tracking path lengths
        dist: Dict[str, int] = {source: 0}
        parent: Dict[str, Optional[str]] = {source: None}
        queue: deque = deque([source])

        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, []):
                new_dist = dist[current] + 1
                if neighbor not in dist or new_dist > dist[neighbor]:
                    dist[neighbor] = new_dist
                    parent[neighbor] = current
                    queue.append(neighbor)

        if not dist:
            continue

        # Find the farthest node
        farthest = max(dist, key=lambda n: dist[n])
        if dist[farthest] + 1 <= len(best_path):
            continue

        # Reconstruct path
        path: List[str] = []
        cur: Optional[str] = farthest
        while cur is not None:
            path.append(cur)
            cur = parent.get(cur)
        path.reverse()
        if len(path) > len(best_path):
            best_path = path

    return best_path if best_path else [n.name for n in nodes[:1]]


# ============================================================================
# Primary trace function
# ============================================================================

def trace_apex_graph(invoke_path: str) -> ApexGraphTrace:
    """Trace an APEX graph from an Invoke SOP.

    Given the path to an APEX Invoke SOP, extracts the graph structure
    from packed geometry primitives and returns an ApexGraphTrace with
    nodes in execution order.

    Returns an empty trace with a descriptive summary if Houdini is
    unavailable or the graph cannot be read.
    """
    if not _HOU_AVAILABLE:
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name="(unavailable)",
            summary="Houdini not available -- cannot trace APEX graph",
        )

    # Resolve the node
    try:
        node = hou.node(invoke_path)
    except Exception as exc:
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name="(error)",
            summary=f"Error resolving node: {exc}",
        )

    if node is None:
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name="(not found)",
            summary=f"Node not found: {invoke_path}",
        )

    # Read graph name from the Invoke node parameters
    graph_name = "(unnamed)"
    try:
        # APEX Invoke SOPs typically have a "graphfile" or "graph" parm
        for parm_name in ("graphfile", "graph", "graphname", "name", "label"):
            try:
                parm = node.parm(parm_name)
                if parm is not None:
                    val = parm.evalAsString()
                    if val:
                        graph_name = val
                        break
            except Exception:
                continue
        # Fallback: node name
        if graph_name == "(unnamed)":
            graph_name = node.name()
    except Exception:
        graph_name = node.name() if node else "(unknown)"

    # Get geometry from the node
    try:
        geo = node.geometry()
    except Exception as exc:
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name=graph_name,
            summary=f"Cannot read geometry: {exc}",
        )

    if geo is None:
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name=graph_name,
            summary="No geometry on node -- is it cooked?",
        )

    if not APEX_GRAPH_AVAILABLE:
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name=graph_name,
            summary="Graph reader unavailable -- cannot trace APEX graph",
        )

    # Read the graph: this node's own output, else the nearest input upstream.
    try:
        found, source_path, distance = _find_graphs(node)
    except Exception as exc:
        logger.debug("graph search failed", exc_info=True)
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name=graph_name,
            summary=f"Cannot read graph: {exc}",
        )

    if found is None:
        fallback_parts = []
        try:
            prim_count = geo.intrinsicValue("primitivecount")
            point_count = geo.intrinsicValue("pointcount")
            fallback_parts.append(
                f"Geometry has {prim_count} prims, {point_count} points"
            )
        except Exception:
            logger.debug("geometry stats unavailable", exc_info=True)
            fallback_parts.append("Could not read geometry stats")
        fallback_parts.append(
            "no APEX graph in this node's output or its inputs upstream"
        )
        fallback_parts.append(
            "Try inspecting with the APEX Network Editor for full graph details"
        )
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name=graph_name,
            summary="; ".join(fallback_parts),
        )

    graphs = found.get("graphs", [])
    graph = graphs[0]
    folder = str(graph.get("folder", ""))
    if folder:
        graph_name = folder.rsplit("/", 1)[-1]

    if not graph.get("read"):
        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name=graph_name,
            node_count=int(graph.get("node_count") or 0),
            wire_count=int(graph.get("wire_count") or 0),
            graph_folder=folder,
            graph_source=source_path,
            summary=f"APEX graph {graph_name}: {graph.get('reason', 'not read')}",
        )

    all_nodes, all_connections = _nodes_from_graph(graph)

    # Sort nodes into execution order
    sorted_nodes = _topological_sort(all_nodes, all_connections)

    # Find critical path (skipped on very large graphs; see the cap)
    if len(sorted_nodes) <= _CRITICAL_PATH_NODE_CAP:
        critical_path = _find_critical_path(sorted_nodes, all_connections)
    else:
        critical_path = []

    # Build summary
    category_counts: Dict[str, int] = {}
    for n in sorted_nodes:
        category_counts[n.category] = category_counts.get(n.category, 0) + 1

    dominant_categories = sorted(
        category_counts.items(), key=lambda x: x[1], reverse=True
    )
    cat_desc = ", ".join(f"{count} {cat}" for cat, count in dominant_categories[:4])

    controls = list(graph.get("controls", []))
    control_count = int(graph.get("control_count") or 0)
    wire_count = int(graph.get("wire_count") or len(all_connections))

    summary = (
        f"APEX graph {graph_name}: {len(sorted_nodes)} nodes, "
        f"{wire_count} wires, {control_count} controls ({cat_desc})"
    )
    if len(critical_path) > 1:
        summary += f", critical path: {len(critical_path)} nodes"
    if distance:
        summary += (
            f". Read from {source_path}, {distance} input(s) upstream: "
            "this node's own output holds no graph"
        )
    if len(graphs) > 1:
        others = ", ".join(str(g.get("folder", "")) for g in graphs[1:4])
        summary += f". {len(graphs) - 1} more graph(s) not traced: {others}"

    return ApexGraphTrace(
        invoke_path=invoke_path,
        graph_name=graph_name,
        node_count=len(sorted_nodes),
        nodes=sorted_nodes,
        data_flow=all_connections,
        summary=summary,
        critical_path=critical_path,
        wire_count=wire_count,
        controls=controls,
        graph_folder=folder,
        graph_source=source_path,
        graph_inputs=list(graph.get("graph_inputs", [])),
        graph_outputs=list(graph.get("graph_outputs", [])),
    )


# ============================================================================
# HTML formatter
# ============================================================================

_CATEGORY_COLORS: Dict[str, str] = {
    "transform": _ds.TEXT_SECONDARY,
    "attribute": _ds.TEXT_SECONDARY,
    "math": _ds.TEXT_SECONDARY,
    "logic": _ds.TEXT_SECONDARY,
    "deform": _ds.TEXT_SECONDARY,
    "solver": _ds.TEXT_SECONDARY,
    "constraint": _ds.TEXT_SECONDARY,
    "io": _ds.TEXT_TERTIARY,
    "other": _ds.TEXT_SECONDARY,
}


def format_apex_trace_html(trace: ApexGraphTrace) -> str:
    """Format an ApexGraphTrace as HTML for the panel's QTextEdit."""
    if not trace.nodes:
        return (
            f"<p style='color:{_ds.TEXT_TERTIARY};'>APEX Trace: "
            f"<b>{html.escape(trace.invoke_path)}</b><br/>"
            f"{html.escape(trace.summary)}</p>"
        )

    critical_set = set(trace.critical_path)
    lines: List[str] = []

    # Header
    lines.append(
        f"<h3 style='margin:4px 0;'>APEX Graph: "
        f"{html.escape(trace.graph_name)}</h3>"
    )
    lines.append(
        f"<p style='color:{_ds.TEXT_SECONDARY}; margin:2px 0;'>"
        f"Source: {html.escape(trace.graph_source or trace.invoke_path)} | "
        f"{trace.node_count} nodes | {trace.wire_count} wires | "
        f"{len(trace.controls)} controls</p>"
    )
    if trace.controls:
        control_str = ", ".join(html.escape(str(c)) for c in trace.controls)
        lines.append("<h4 style='margin:8px 0 4px 0;'>Controls</h4>")
        lines.append(
            f"<div style='padding:4px 8px; color:{_ds.TEXT_SECONDARY};'>"
            f"{control_str}</div>"
        )

    # Node list in execution order
    lines.append("<h4 style='margin:8px 0 4px 0;'>Execution Order</h4>")

    for idx, node in enumerate(trace.nodes, start=1):
        cat_color = _CATEGORY_COLORS.get(node.category, _ds.TEXT_SECONDARY)
        is_critical = node.name in critical_set

        border_color = _ds.SIGNAL if is_critical else _ds.BORDER
        bg = f"background:{_ds.SIGNAL_TINT};" if is_critical else ""

        lines.append(
            f"<div style='border-left:3px solid {border_color}; "
            f"padding:4px 8px; margin:3px 0; {bg}'>"
        )

        # Node header
        lines.append(
            f"<b>{idx}.</b> "
            f"<b>{html.escape(node.name)}</b> "
            f"<span style='color:{cat_color};'>[{html.escape(node.node_type)}]</span> "
            f"<span style='color:{_ds.TEXT_TERTIARY};'>({html.escape(node.category)})</span>"
        )

        # Description
        if node.description:
            lines.append(
                f"<br/><span style='color:{_ds.TEXT_SECONDARY};'>"
                f"{html.escape(node.description)}</span>"
            )

        # Inputs/outputs
        if node.inputs:
            inp_str = ", ".join(html.escape(str(i)) for i in node.inputs)
            lines.append(
                f"<br/><span style='color:{_ds.TEXT_SECONDARY};'>Inputs: {inp_str}</span>"
            )
        if node.outputs:
            out_str = ", ".join(html.escape(str(o)) for o in node.outputs)
            lines.append(
                f"<br/><span style='color:{_ds.TEXT_SECONDARY};'>Outputs: {out_str}</span>"
            )

        if is_critical:
            lines.append(
                f"<br/><span style='color:{_ds.SIGNAL};'>** critical path **</span>"
            )

        lines.append("</div>")

    # Connection diagram (text flow)
    if trace.data_flow:
        lines.append("<h4 style='margin:8px 0 4px 0;'>Data Flow</h4>")
        lines.append(f"<div style='padding:4px 8px; color:{_ds.TEXT_SECONDARY}; font-family:monospace;'>")
        for src, dst, port in trace.data_flow[:_FLOW_LINES_CAP]:
            port_label = f" ({html.escape(port)})" if port else ""
            lines.append(
                f"{html.escape(src)} -> {html.escape(dst)}{port_label}<br/>"
            )
        if len(trace.data_flow) > _FLOW_LINES_CAP:
            lines.append(
                f"... and {len(trace.data_flow) - _FLOW_LINES_CAP} more wires<br/>"
            )
        lines.append("</div>")
    elif trace.critical_path and len(trace.critical_path) > 1:
        # Show critical path as a flow diagram
        lines.append("<h4 style='margin:8px 0 4px 0;'>Critical Path</h4>")
        flow = " -> ".join(html.escape(n) for n in trace.critical_path)
        lines.append(
            f"<div style='padding:4px 8px; color:{_ds.SIGNAL}; "
            f"font-family:monospace;'>{flow}</div>"
        )

    # Summary
    lines.append("<hr/>")
    lines.append(f"<p><b>Summary:</b> {html.escape(trace.summary)}</p>")

    return "\n".join(lines)


# ============================================================================
# Plain text formatter
# ============================================================================

def format_apex_trace_text(trace: ApexGraphTrace) -> str:
    """Format an ApexGraphTrace as plain text for sending to Claude."""
    if not trace.nodes:
        return f"APEX Trace: {trace.invoke_path}\n{trace.summary}"

    critical_set = set(trace.critical_path)
    lines: List[str] = []

    lines.append(f"APEX Graph Trace: {trace.graph_name}")
    lines.append(f"Source: {trace.graph_source or trace.invoke_path}")
    lines.append(f"Nodes: {trace.node_count}")
    lines.append(f"Wires: {trace.wire_count}")
    lines.append(f"Controls: {len(trace.controls)}")
    lines.append("")

    if trace.controls:
        lines.append("== Controls ==")
        lines.append("  " + ", ".join(str(c) for c in trace.controls))
        lines.append("")

    lines.append("== Execution Order ==")
    for idx, node in enumerate(trace.nodes, start=1):
        crit_marker = " [CRITICAL PATH]" if node.name in critical_set else ""
        lines.append(
            f"{idx}. {node.name} ({node.node_type}) [{node.category}]{crit_marker}"
        )
        lines.append(f"   {node.description}")
        if node.inputs:
            lines.append(f"   inputs: {', '.join(str(i) for i in node.inputs)}")
        if node.outputs:
            lines.append(f"   outputs: {', '.join(str(o) for o in node.outputs)}")

    lines.append("")

    if trace.data_flow:
        lines.append("== Data Flow ==")
        for src, dst, port in trace.data_flow[:_FLOW_LINES_CAP]:
            port_label = f" ({port})" if port else ""
            lines.append(f"  {src} -> {dst}{port_label}")
        if len(trace.data_flow) > _FLOW_LINES_CAP:
            lines.append(
                f"  ... and {len(trace.data_flow) - _FLOW_LINES_CAP} more wires"
            )
        lines.append("")

    if trace.critical_path and len(trace.critical_path) > 1:
        lines.append("== Critical Path ==")
        lines.append("  " + " -> ".join(trace.critical_path))
        lines.append("")

    lines.append(f"Summary: {trace.summary}")
    return "\n".join(lines)


# ============================================================================
# Claude prompt/message builders
# ============================================================================

def build_apex_trace_prompt(trace: ApexGraphTrace) -> str:
    """System prompt for Claude to interpret the APEX graph."""
    return (
        "You are analyzing an APEX graph from Houdini. The graph was read "
        "from the geometry of an APEX node. Explain what this graph does as a "
        "complete rigging operation. Describe the data flow from inputs to "
        "outputs. Identify the core operations (transforms, constraints, "
        "solvers) and explain how they work together.\n\n"
        "If the graph data is incomplete or could not be fully extracted, "
        "explain what is available and suggest how the artist can inspect "
        "the graph further using Houdini's APEX Network Editor.\n\n"
        "Keep your explanation concise and practical -- focus on what the "
        "graph DOES, not on restating the raw data."
    )


def build_apex_trace_messages(trace: ApexGraphTrace) -> list:
    """Build messages list for the Claude API with the trace data."""
    trace_text = format_apex_trace_text(trace)

    messages = [
        {
            "role": "user",
            "content": (
                f"Analyze this APEX graph and explain what it does:\n\n"
                f"{trace_text}"
            ),
        }
    ]
    return messages
