"""
SYNAPSE APEX Graph Trace -- Introspection for APEX graphs in Houdini 21.

Reads an APEX Invoke SOP, extracts the graph structure from packed
geometry primitives, determines execution order via topological sort,
and presents the result as HTML (for the panel) or plain text (for Claude).

APEX graphs are programs stored as geometry (packed prims).  The internal
structure is not fully documented, so this module uses best-effort
introspection: it reads whatever attributes are available on the packed
content and falls back gracefully when data is missing.

All hou access is individually guarded so failures never break the trace.
Outside Houdini the module imports cleanly and trace_apex_graph() returns
an empty trace immediately.
"""

from __future__ import annotations

import html
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Houdini import guard
# ---------------------------------------------------------------------------
_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]


# ============================================================================
# Data classes
# ============================================================================

@dataclass
class ApexGraphNode:
    """One node within an APEX graph."""

    name: str               # node name within the graph
    node_type: str          # operation type (e.g. "TransformObject", "GetAttribute")
    category: str           # "transform", "attribute", "math", "control", "solver", "other"
    inputs: list            # input connection names
    outputs: list           # output connection names
    description: str        # brief description of what this operation does


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
    ],
    "control": [
        "Switch", "Branch", "Loop", "ForEach", "If", "While",
        "Compare", "And", "Or", "Not", "Select",
    ],
    "solver": [
        "FKSolver", "IKSolver", "FBIK", "FBIKSolver",
        "SpringSolver", "RBDSolver", "MotionClip",
        "SolveFK", "SolveIK", "SolveFBIK",
    ],
    "constraint": [
        "ParentConstraint", "AimConstraint", "PointConstraint",
        "OrientConstraint", "ScaleConstraint", "PoleVectorConstraint",
        "BlendConstraint", "TwoBoneIK",
    ],
    "io": [
        "Input", "Output", "Pack", "Unpack",
        "Import", "Export", "Fetch", "Store",
        "GraphInput", "GraphOutput", "SubGraphInput", "SubGraphOutput",
    ],
}

# Build reverse lookup: operation_name -> category
_OP_TO_CATEGORY: Dict[str, str] = {}
for _cat, _ops in _CATEGORY_MAP.items():
    for _op in _ops:
        _OP_TO_CATEGORY[_op] = _cat


def categorize_apex_operation(type_name: str) -> str:
    """Map an APEX operation type name to a category string.

    Returns one of: "transform", "attribute", "math", "control",
    "solver", "constraint", "io", or "other".
    """
    if type_name in _OP_TO_CATEGORY:
        return _OP_TO_CATEGORY[type_name]

    # Try case-insensitive substring matching for partial hits
    lower = type_name.lower()
    for cat, ops in _CATEGORY_MAP.items():
        for op in ops:
            if op.lower() in lower or lower in op.lower():
                return cat

    # Heuristic fallback on common suffixes/prefixes
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
}


def _describe_operation(type_name: str) -> str:
    """Return a brief human-readable description for an APEX operation."""
    if type_name in _OP_DESCRIPTIONS:
        return _OP_DESCRIPTIONS[type_name]
    cat = categorize_apex_operation(type_name)
    if cat != "other":
        return f"{cat.capitalize()} operation"
    return "APEX graph operation"


# ============================================================================
# Graph extraction helpers
# ============================================================================

def _safe_attrib_value(prim: Any, attrib_name: str, default: Any = "") -> Any:
    """Read an attribute value from a prim, returning *default* on failure."""
    try:
        val = prim.attribValue(attrib_name)
        return val if val is not None else default
    except Exception:
        return default


def _safe_string_list(prim: Any, attrib_name: str) -> List[str]:
    """Read a string array attribute, returning [] on failure."""
    try:
        val = prim.attribValue(attrib_name)
        if isinstance(val, (list, tuple)):
            return [str(v) for v in val]
        if isinstance(val, str) and val:
            return [val]
        return []
    except Exception:
        return []


def _extract_graph_nodes_from_geo(
    geo: Any,
) -> Tuple[List[ApexGraphNode], List[Tuple[str, str, str]]]:
    """Extract APEX graph nodes and connections from geometry.

    APEX graphs store nodes as primitives with attributes describing the
    graph structure.  The exact attribute names vary, so we probe several
    known patterns.

    Returns (nodes_list, connections_list).
    """
    nodes: List[ApexGraphNode] = []
    connections: List[Tuple[str, str, str]] = []
    seen_names: Set[str] = set()

    if geo is None:
        return nodes, connections

    # Discover available prim-level string attributes
    available_attribs: Set[str] = set()
    try:
        for attrib in geo.primAttribs():
            available_attribs.add(attrib.name())
    except Exception:
        pass

    # Candidate attribute names for node name, type, inputs, outputs
    name_candidates = ["name", "nodename", "node_name", "label"]
    type_candidates = ["type", "nodetype", "node_type", "callback", "op"]
    input_candidates = ["inputnames", "input_names", "inputs", "inputconnections"]
    output_candidates = ["outputnames", "output_names", "outputs", "outputconnections"]

    def _pick(candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in available_attribs:
                return c
        return None

    name_attr = _pick(name_candidates)
    type_attr = _pick(type_candidates)
    input_attr = _pick(input_candidates)
    output_attr = _pick(output_candidates)

    try:
        prims = geo.prims()
    except Exception:
        return nodes, connections

    for prim in prims:
        try:
            node_name = _safe_attrib_value(prim, name_attr, "") if name_attr else ""
            if not node_name:
                # Fallback: use prim number
                try:
                    node_name = f"node_{prim.number()}"
                except Exception:
                    node_name = f"node_{len(nodes)}"

            node_type = _safe_attrib_value(prim, type_attr, "unknown") if type_attr else "unknown"

            inputs = _safe_string_list(prim, input_attr) if input_attr else []
            outputs = _safe_string_list(prim, output_attr) if output_attr else []

            category = categorize_apex_operation(str(node_type))
            description = _describe_operation(str(node_type))

            # Deduplicate names
            base_name = str(node_name)
            if base_name in seen_names:
                suffix = 1
                while f"{base_name}_{suffix}" in seen_names:
                    suffix += 1
                base_name = f"{base_name}_{suffix}"
            seen_names.add(base_name)

            nodes.append(ApexGraphNode(
                name=base_name,
                node_type=str(node_type),
                category=category,
                inputs=inputs,
                outputs=outputs,
                description=description,
            ))
        except Exception:
            continue

    # Try to extract explicit connections from geometry-level attributes
    # APEX may store connections as detail attributes or in a separate
    # connectivity structure
    try:
        conn_attribs = {"connections", "edges", "wires", "graph_edges"}
        for attr_name in conn_attribs & available_attribs:
            val = geo.attribValue(attr_name)
            if isinstance(val, (list, tuple)):
                for item in val:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        src = str(item[0])
                        dst = str(item[1])
                        port = str(item[2]) if len(item) > 2 else ""
                        connections.append((src, dst, port))
    except Exception:
        pass

    return nodes, connections


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

    # Look for packed primitives (APEX graphs are stored as packed geo)
    all_nodes: List[ApexGraphNode] = []
    all_connections: List[Tuple[str, str, str]] = []
    packed_count = 0

    try:
        for prim in geo.prims():
            try:
                prim_type = prim.type()
                is_packed = (
                    prim_type == hou.primType.PackedPrim
                    or "packed" in str(prim_type).lower()
                )
            except Exception:
                is_packed = False

            if not is_packed:
                continue

            packed_count += 1

            # Try to get the packed geometry content
            try:
                packed_geo = prim.getEmbeddedGeometry()
            except Exception:
                packed_geo = None

            if packed_geo is None:
                # Try alternative access methods
                try:
                    packed_geo = prim.unpackedGeo()
                except Exception:
                    packed_geo = None

            if packed_geo is not None:
                nodes_found, conns_found = _extract_graph_nodes_from_geo(packed_geo)
                all_nodes.extend(nodes_found)
                all_connections.extend(conns_found)
    except Exception:
        pass

    # If we found no packed prims, try the geometry directly
    if not all_nodes and packed_count == 0:
        all_nodes, all_connections = _extract_graph_nodes_from_geo(geo)

    # If still no nodes, provide a fallback report
    if not all_nodes:
        fallback_parts = []
        if packed_count > 0:
            fallback_parts.append(f"{packed_count} packed prim(s) found")
            fallback_parts.append(
                "but graph internals could not be read"
            )
        else:
            try:
                prim_count = geo.intrinsicValue("primitivecount")
                point_count = geo.intrinsicValue("pointcount")
                fallback_parts.append(
                    f"Geometry has {prim_count} prims, {point_count} points"
                )
            except Exception:
                fallback_parts.append("Could not read geometry stats")
            fallback_parts.append("no APEX packed primitives detected")

        fallback_parts.append(
            "Try inspecting with the APEX Network Editor for full graph details"
        )

        return ApexGraphTrace(
            invoke_path=invoke_path,
            graph_name=graph_name,
            summary="; ".join(fallback_parts),
        )

    # Sort nodes into execution order
    sorted_nodes = _topological_sort(all_nodes, all_connections)

    # Find critical path
    critical_path = _find_critical_path(sorted_nodes, all_connections)

    # Build summary
    category_counts: Dict[str, int] = {}
    for n in sorted_nodes:
        category_counts[n.category] = category_counts.get(n.category, 0) + 1

    dominant_categories = sorted(
        category_counts.items(), key=lambda x: x[1], reverse=True
    )
    cat_desc = ", ".join(f"{count} {cat}" for cat, count in dominant_categories[:3])

    summary = f"APEX graph: {len(sorted_nodes)} nodes ({cat_desc})"
    if len(critical_path) > 1:
        summary += f", critical path: {len(critical_path)} nodes"

    return ApexGraphTrace(
        invoke_path=invoke_path,
        graph_name=graph_name,
        node_count=len(sorted_nodes),
        nodes=sorted_nodes,
        data_flow=all_connections,
        summary=summary,
        critical_path=critical_path,
    )


# ============================================================================
# HTML formatter
# ============================================================================

_CATEGORY_COLORS: Dict[str, str] = {
    "transform": "#6ABF69",   # green
    "attribute": "#7AB4CC",   # blue
    "math": "#B9B06A",        # yellow
    "control": "#E8922E",     # orange
    "solver": "#CC6A9E",      # pink
    "constraint": "#9E7ACC",  # purple
    "io": "#888888",          # gray
    "other": "#AAAAAA",       # light gray
}


def format_apex_trace_html(trace: ApexGraphTrace) -> str:
    """Format an ApexGraphTrace as HTML for the panel's QTextEdit."""
    if not trace.nodes:
        return (
            f"<p style='color:#888;'>APEX Trace: "
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
        f"<p style='color:#AAA; margin:2px 0;'>"
        f"Source: {html.escape(trace.invoke_path)} | "
        f"{trace.node_count} nodes</p>"
    )

    # Node list in execution order
    lines.append("<h4 style='margin:8px 0 4px 0;'>Execution Order</h4>")

    for idx, node in enumerate(trace.nodes, start=1):
        cat_color = _CATEGORY_COLORS.get(node.category, "#AAAAAA")
        is_critical = node.name in critical_set

        border_color = "#E8922E" if is_critical else "#555555"
        bg = "background:#2A2520;" if is_critical else ""

        lines.append(
            f"<div style='border-left:3px solid {border_color}; "
            f"padding:4px 8px; margin:3px 0; {bg}'>"
        )

        # Node header
        lines.append(
            f"<b>{idx}.</b> "
            f"<b>{html.escape(node.name)}</b> "
            f"<span style='color:{cat_color};'>[{html.escape(node.node_type)}]</span> "
            f"<span style='color:#666;'>({html.escape(node.category)})</span>"
        )

        # Description
        if node.description:
            lines.append(
                f"<br/><span style='color:#AAA;'>"
                f"{html.escape(node.description)}</span>"
            )

        # Inputs/outputs
        if node.inputs:
            inp_str = ", ".join(html.escape(str(i)) for i in node.inputs)
            lines.append(
                f"<br/><span style='color:#7AB;'>Inputs: {inp_str}</span>"
            )
        if node.outputs:
            out_str = ", ".join(html.escape(str(o)) for o in node.outputs)
            lines.append(
                f"<br/><span style='color:#B9B;'>Outputs: {out_str}</span>"
            )

        if is_critical:
            lines.append(
                "<br/><span style='color:#E8922E;'>** critical path **</span>"
            )

        lines.append("</div>")

    # Connection diagram (text flow)
    if trace.data_flow:
        lines.append("<h4 style='margin:8px 0 4px 0;'>Data Flow</h4>")
        lines.append("<div style='padding:4px 8px; color:#AAA; font-family:monospace;'>")
        for src, dst, port in trace.data_flow:
            port_label = f" ({html.escape(port)})" if port else ""
            lines.append(
                f"{html.escape(src)} -> {html.escape(dst)}{port_label}<br/>"
            )
        lines.append("</div>")
    elif trace.critical_path and len(trace.critical_path) > 1:
        # Show critical path as a flow diagram
        lines.append("<h4 style='margin:8px 0 4px 0;'>Critical Path</h4>")
        flow = " -> ".join(html.escape(n) for n in trace.critical_path)
        lines.append(
            f"<div style='padding:4px 8px; color:#E8922E; "
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
    lines.append(f"Source: {trace.invoke_path}")
    lines.append(f"Nodes: {trace.node_count}")
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
        for src, dst, port in trace.data_flow:
            port_label = f" ({port})" if port else ""
            lines.append(f"  {src} -> {dst}{port_label}")
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
        "You are analyzing an APEX graph from Houdini 21. The graph was "
        "extracted from an Invoke SOP. Explain what this graph does as a "
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
