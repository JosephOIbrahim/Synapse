"""
Synapse Node Handler Mixin

Extracted from handlers.py -- contains node creation, deletion, connection,
and network explanation handlers for the SynapseHandler class.
"""

import os
from collections import deque
from typing import Any, Dict, List, Set, Tuple

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.errors import NodeNotFoundError, HoudiniUnavailableError
from .handler_helpers import _HOUDINI_UNAVAILABLE


def _suggest_children(parent_path: str) -> str:
    """List children of a parent path for error enrichment."""
    try:
        parent = hou.node(parent_path)
        if parent and parent.children():
            names = [c.name() for c in parent.children()[:10]]
            return " Children at that path: " + ", ".join(names)
    except Exception:
        pass
    return ""


class NodeHandlerMixin:
    """Mixin providing node creation, deletion, and connection handlers."""

    def _handle_create_node(self, payload: Dict) -> Dict:
        """Handle create_node command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        parent = resolve_param(payload, "parent")
        node_type = resolve_param(payload, "type")
        name = resolve_param(payload, "name", required=False)

        from .main_thread import run_on_main

        def _on_main():
            parent_node = hou.node(parent)
            if parent_node is None:
                hint = _suggest_children(os.path.dirname(parent))
                raise NodeNotFoundError(parent, suggestion=hint.strip() if hint else "")

            if name:
                new_node = parent_node.createNode(node_type, name)
            else:
                new_node = parent_node.createNode(node_type)

            new_node.moveToGoodPosition()

            # Track node in session (logging handled by generic executor in handle())
            bridge = self._get_bridge()  # type: ignore[attr-defined]
            if bridge and self._session_id:  # type: ignore[attr-defined]
                session = bridge.get_session(self._session_id)  # type: ignore[attr-defined]
                if session:
                    session.nodes_created.append(new_node.path())

            return {
                "path": new_node.path(),
                "type": node_type,
                "name": new_node.name(),
            }

        return run_on_main(_on_main)

    def _handle_delete_node(self, payload: Dict) -> Dict:
        """Handle delete_node command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        node_path = resolve_param(payload, "node")

        from .main_thread import run_on_main

        def _on_main():
            node = hou.node(node_path)
            if node is None:
                raise NodeNotFoundError(node_path)

            node_name = node.name()
            node.destroy()

            return {"deleted": node_path, "name": node_name}

        return run_on_main(_on_main)

    def _handle_connect_nodes(self, payload: Dict) -> Dict:
        """Handle connect_nodes command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        source_path = resolve_param(payload, "source")
        target_path = resolve_param(payload, "target")
        source_output = resolve_param_with_default(payload, "source_output", 0)
        target_input = resolve_param_with_default(payload, "target_input", 0)

        from .main_thread import run_on_main

        def _on_main():
            source_node = hou.node(source_path)
            target_node = hou.node(target_path)

            if source_node is None:
                raise NodeNotFoundError(source_path)
            if target_node is None:
                raise NodeNotFoundError(target_path)

            target_node.setInput(int(target_input), source_node, int(source_output))

            return {
                "source": source_path,
                "target": target_path,
                "source_output": source_output,
                "target_input": target_input,
            }

        return run_on_main(_on_main)

    def _handle_network_explain(self, payload: Dict) -> Dict:
        """Walk a Houdini node network and produce a structured explanation.

        Traverses children in data-flow order, detects common workflow
        patterns, identifies non-default parameters, and optionally suggests
        parameters to promote for HDA interfaces.
        """
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        root_path = resolve_param(payload, "node")
        depth = resolve_param_with_default(payload, "depth", 2)
        depth = min(int(depth), 5)
        detail_level = resolve_param_with_default(payload, "detail_level", "standard")
        include_parameters = resolve_param_with_default(payload, "include_parameters", True)
        include_expressions = resolve_param_with_default(payload, "include_expressions", False)
        output_format = resolve_param_with_default(payload, "format", "structured")

        from .main_thread import run_on_main

        def _on_main():
            root = hou.node(root_path)
            if root is None:
                raise NodeNotFoundError(root_path)

            # Collect all nodes with depth-limited traversal
            all_nodes = _collect_nodes(root, depth)

            if not all_nodes:
                return {
                    "status": "ok",
                    "overview": f"Network at {root_path} is empty -- no child nodes found.",
                    "node_count": 0,
                    "data_flow": [],
                    "patterns_detected": [],
                    "complexity": "simple",
                    "suggested_hda_interface": [],
                }

            # Build adjacency and topological sort
            sorted_nodes = _topo_sort(all_nodes)

            # Build per-node info
            data_flow: List[Dict[str, Any]] = []
            type_names: Set[str] = set()
            hda_suggestions: List[Dict[str, Any]] = []

            for n in sorted_nodes:
                type_name = n.type().name()
                type_label = n.type().description()
                type_names.add(type_name)

                inputs_from: List[str] = []
                for inp in n.inputs():
                    if inp is not None:
                        inputs_from.append(inp.name())
                outputs_to: List[str] = []
                for out in n.outputs():
                    if out is not None:
                        outputs_to.append(out.name())

                entry: Dict[str, Any] = {
                    "node": n.name(),
                    "path": n.path(),
                    "type": type_name,
                    "type_label": type_label,
                    "role": _infer_role(type_name, type_label),
                    "inputs_from": sorted(inputs_from),
                    "outputs_to": sorted(outputs_to),
                }

                if include_parameters and detail_level != "summary":
                    key_params, expressions = _get_non_default_params(
                        n, include_expressions
                    )
                    entry["key_params"] = key_params
                    if include_expressions and expressions:
                        entry["expressions"] = expressions

                    # Suggest interesting parms for HDA interface
                    for parm_name, parm_val in sorted(key_params.items()):
                        hda_suggestions.append({
                            "node": n.name(),
                            "parm": parm_name,
                            "label": parm_name.replace("_", " ").title(),
                            "reason": f"Non-default value ({parm_val})",
                        })

                if detail_level == "detailed":
                    entry["input_count"] = len(inputs_from)
                    entry["output_count"] = len(outputs_to)
                    # Check for subnets
                    try:
                        children = n.children()
                        if children:
                            entry["has_children"] = True
                            entry["child_count"] = len(children)
                    except Exception:
                        pass

                data_flow.append(entry)

            # Pattern detection
            patterns = _detect_patterns(type_names)

            # Complexity rating
            node_count = len(all_nodes)
            has_subnets = any(
                e.get("has_children") for e in data_flow
            )
            if node_count <= 5 and not has_subnets:
                complexity = "simple"
            elif node_count <= 15:
                complexity = "moderate"
            else:
                complexity = "complex"

            # Generate overview text
            overview = _generate_overview(
                root_path, data_flow, patterns, node_count
            )

            result: Dict[str, Any] = {
                "status": "ok",
                "overview": overview,
                "node_count": node_count,
                "data_flow": data_flow,
                "patterns_detected": sorted(patterns),
                "complexity": complexity,
                "suggested_hda_interface": hda_suggestions,
            }

            # Format conversion
            if output_format == "prose":
                return _format_prose(result)
            elif output_format == "help_card":
                return _format_help_card(result)

            return result

        return run_on_main(_on_main)


# =============================================================================
# Network Explain Helpers
# =============================================================================

# Workflow pattern signatures — lightweight matching on node type names
_NETWORK_PATTERNS: Dict[str, Dict[str, Any]] = {
    "scatter_workflow": {
        "signature": {"scatter", "copytopoints"},
        "description": "Distributes copies of geometry across a surface",
    },
    "simulation_setup": {
        "signature": {"dopnet", "solver"},
        "description": "Dynamic simulation network",
    },
    "terrain_generation": {
        "signature": {"heightfield_noise", "heightfield_erode"},
        "description": "Procedural terrain with erosion",
    },
    "usd_stage_assembly": {
        "signature": {"sublayer", "merge"},
        "description": "USD/Solaris stage construction",
    },
    "deformation_chain": {
        "signature": {"mountain", "bend", "twist"},
        "description": "Geometry deformation pipeline",
    },
    "material_assignment": {
        "signature": {"materiallibrary", "assignmaterial"},
        "description": "Material creation and assignment",
    },
    "vdb_workflow": {
        "signature": {"vdbfrompolygons", "vdbsmooth"},
        "description": "Volume/VDB processing pipeline",
    },
    "particle_system": {
        "signature": {"popnet", "popsolver"},
        "description": "Particle simulation system",
    },
}


def _collect_nodes(root, max_depth: int) -> list:
    """Collect child nodes up to max_depth levels deep."""
    result: list = []
    queue: deque = deque()
    # (node, current_depth)
    for child in root.children():
        queue.append((child, 1))
    while queue:
        node, d = queue.popleft()
        result.append(node)
        if d < max_depth:
            try:
                for child in node.children():
                    queue.append((child, d + 1))
            except Exception:
                pass
    return result


def _topo_sort(nodes: list) -> list:
    """Topological sort of nodes by input connections.

    Nodes with no inputs come first (sources), then downstream consumers.
    Falls back to name-sorted order for nodes at the same depth.
    """
    node_set = set(id(n) for n in nodes)
    # Map id -> node for quick lookup
    id_to_node: Dict[int, Any] = {id(n): n for n in nodes}
    # in-degree per node (only counting edges within our node set)
    in_degree: Dict[int, int] = {id(n): 0 for n in nodes}
    # adjacency: id -> list of downstream ids
    adj: Dict[int, List[int]] = {id(n): [] for n in nodes}

    for n in nodes:
        for inp in n.inputs():
            if inp is not None and id(inp) in node_set:
                in_degree[id(n)] += 1
                adj[id(inp)].append(id(n))

    # Kahn's algorithm with deterministic tie-breaking by name
    queue: list = sorted(
        [n for n in nodes if in_degree[id(n)] == 0],
        key=lambda n: n.name(),
    )
    result: list = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for nid in sorted(adj[id(node)], key=lambda x: id_to_node[x].name()):
            in_degree[nid] -= 1
            if in_degree[nid] == 0:
                queue.append(id_to_node[nid])
        # Keep queue sorted for determinism
        queue.sort(key=lambda n: n.name())

    # Append any remaining nodes (cycles) sorted by name
    remaining = [n for n in nodes if n not in result]
    remaining.sort(key=lambda n: n.name())
    result.extend(remaining)

    return result


def _get_non_default_params(
    node, include_expressions: bool
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Return (non_default_params, expressions) for a node.

    Compares each parameter's current value to its template default.
    """
    key_params: Dict[str, Any] = {}
    expressions: Dict[str, str] = {}

    try:
        parms = node.parms()
    except Exception:
        return key_params, expressions

    for parm in parms:
        try:
            template = parm.parmTemplate()
            # Skip invisible/folder parms
            parm_type_name = template.type().name() if hasattr(template.type(), 'name') else str(template.type())
            if "Folder" in parm_type_name or "Separator" in parm_type_name:
                continue

            current = parm.eval()
            defaults = template.defaultValue()

            # defaultValue() returns a tuple for most types
            if isinstance(defaults, tuple) and len(defaults) > 0:
                default_val = defaults[0]
            else:
                default_val = defaults

            if current != default_val:
                key_params[parm.name()] = current

            if include_expressions:
                try:
                    expr = parm.expression()
                    if expr:
                        expressions[parm.name()] = expr
                except Exception:
                    pass
        except Exception:
            continue

    return key_params, expressions


def _infer_role(type_name: str, type_label: str) -> str:
    """Generate a brief role description from node type info."""
    # Use the human-readable label as a base
    if type_label:
        return f"Creates {type_label.lower()} output"
    return f"Processes data ({type_name})"


def _detect_patterns(type_names: Set[str]) -> List[str]:
    """Detect workflow patterns from the set of node type names."""
    detected: List[str] = []
    lower_names = {t.lower() for t in type_names}
    for pattern_name, info in sorted(_NETWORK_PATTERNS.items()):
        sig = info["signature"]
        if sig.issubset(lower_names):
            detected.append(pattern_name)
    return detected


def _generate_overview(
    root_path: str,
    data_flow: List[Dict[str, Any]],
    patterns: List[str],
    node_count: int,
) -> str:
    """Generate a human-readable overview of the network."""
    parts: List[str] = []
    parts.append(f"Network at {root_path} contains {node_count} node(s).")

    if patterns:
        descs = []
        for p in patterns:
            info = _NETWORK_PATTERNS.get(p)
            if info:
                descs.append(info["description"].lower())
        if descs:
            parts.append("Detected patterns: " + ", ".join(descs) + ".")

    # Describe data flow briefly
    if data_flow:
        sources = [e["node"] for e in data_flow if not e.get("inputs_from")]
        sinks = [e["node"] for e in data_flow if not e.get("outputs_to")]
        if sources:
            parts.append("Sources: " + ", ".join(sources) + ".")
        if sinks:
            parts.append("Outputs: " + ", ".join(sinks) + ".")

    return " ".join(parts)


def _format_prose(result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert structured result to prose format."""
    lines: List[str] = [result["overview"], ""]

    for entry in result["data_flow"]:
        line = f"{entry['node']} ({entry['type_label']})"
        if entry.get("inputs_from"):
            line += f" takes input from {', '.join(entry['inputs_from'])}"
        if entry.get("outputs_to"):
            line += f" and feeds into {', '.join(entry['outputs_to'])}"
        line += "."
        if entry.get("key_params"):
            params_str = ", ".join(
                f"{k}={v}" for k, v in sorted(entry["key_params"].items())
            )
            line += f" Key settings: {params_str}."
        lines.append(line)

    if result["patterns_detected"]:
        lines.append("")
        lines.append(
            "This network uses: "
            + ", ".join(result["patterns_detected"])
            + "."
        )

    return {
        "status": "ok",
        "format": "prose",
        "text": "\n".join(lines),
        "node_count": result["node_count"],
        "patterns_detected": result["patterns_detected"],
        "complexity": result["complexity"],
    }


def _format_help_card(result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert structured result to Houdini wiki markup for HDA help."""
    lines: List[str] = [
        "= Network Overview =",
        "",
        result["overview"],
        "",
        "== Data Flow ==",
        "",
    ]

    for entry in result["data_flow"]:
        lines.append(f"::{entry['node']}:")
        lines.append(f"    Type: {entry['type_label']} (`{entry['type']}`)")
        if entry.get("inputs_from"):
            lines.append(f"    Inputs: {', '.join(entry['inputs_from'])}")
        if entry.get("outputs_to"):
            lines.append(f"    Outputs: {', '.join(entry['outputs_to'])}")
        if entry.get("key_params"):
            for k, v in sorted(entry["key_params"].items()):
                lines.append(f"    - `{k}`: {v}")
        lines.append("")

    if result["patterns_detected"]:
        lines.append("== Detected Patterns ==")
        lines.append("")
        for p in result["patterns_detected"]:
            info = _NETWORK_PATTERNS.get(p, {})
            lines.append(f"* *{p}*: {info.get('description', '')}")
        lines.append("")

    if result["suggested_hda_interface"]:
        lines.append("== Suggested HDA Parameters ==")
        lines.append("")
        for s in result["suggested_hda_interface"]:
            lines.append(f"* `{s['node']}/{s['parm']}` -- {s['reason']}")
        lines.append("")

    return {
        "status": "ok",
        "format": "help_card",
        "text": "\n".join(lines),
        "node_count": result["node_count"],
        "patterns_detected": result["patterns_detected"],
        "complexity": result["complexity"],
    }
