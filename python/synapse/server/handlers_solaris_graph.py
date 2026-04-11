"""
Synapse Solaris Graph Builder Handler Mixin

Builds arbitrary DAG topologies in Solaris LOP networks — merge nodes,
sublayer stacks, parallel streams. Complements assemble_chain (linear only).
"""

from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Tuple
import logging

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.errors import NodeNotFoundError, HoudiniUnavailableError, SynapseUserError
from .solaris_graph_templates import expand_template, TEMPLATES
from .handler_helpers import _layout_dag_vertical, _layout_vertical_chain

logger = logging.getLogger(__name__)


# ── Validation (pure Python, no hou) ─────────────────────────────────────


def validate_graph(
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
    display_node: Optional[str] = None,
) -> Tuple[bool, List[str], List[str]]:
    """Validate a graph specification.

    Returns:
        (valid, errors, warnings) — valid is True if no errors.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not nodes:
        return True, errors, warnings  # Empty graph is valid (no-op)

    # Check duplicate IDs
    node_ids = [n["id"] for n in nodes]
    seen = set()
    for nid in node_ids:
        if nid in seen:
            errors.append(f"Duplicate node id: '{nid}'")
        seen.add(nid)

    node_id_set = set(node_ids)

    # Check connection references
    for conn in connections:
        from_id = conn.get("from", "")
        to_id = conn.get("to", "")
        if from_id not in node_id_set:
            errors.append(f"Connection references unknown source id: '{from_id}'")
        if to_id not in node_id_set:
            errors.append(f"Connection references unknown target id: '{to_id}'")
        if from_id == to_id and from_id:
            errors.append(f"Self-loop on node '{from_id}'")

    # Check display_node reference
    if display_node is not None and display_node not in node_id_set:
        errors.append(f"display_node '{display_node}' not found in node ids")

    # Check for cycles (Kahn's algorithm)
    if not errors:
        cycle_error = _detect_cycle(node_id_set, connections)
        if cycle_error:
            errors.append(cycle_error)

    # Check for merge input gaps
    if not errors:
        gap_warnings = _check_merge_input_gaps(connections)
        warnings.extend(gap_warnings)

    return len(errors) == 0, errors, warnings


def _detect_cycle(node_ids: set, connections: List[Dict[str, Any]]) -> Optional[str]:
    """Detect cycles using Kahn's topological sort. Returns error string or None."""
    in_degree = defaultdict(int)
    adjacency = defaultdict(list)

    for nid in node_ids:
        in_degree[nid] = 0

    for conn in connections:
        from_id = conn["from"]
        to_id = conn["to"]
        adjacency[from_id].append(to_id)
        in_degree[to_id] += 1

    queue = deque(nid for nid in node_ids if in_degree[nid] == 0)
    visited = 0

    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(node_ids):
        return "Graph contains a cycle — Solaris DAGs must be acyclic"
    return None


def _check_merge_input_gaps(connections: List[Dict[str, Any]]) -> List[str]:
    """Warn if a target node has input indices with gaps (e.g. 0 and 2 but not 1)."""
    warnings = []
    target_inputs: Dict[str, List[int]] = defaultdict(list)

    for conn in connections:
        to_id = conn["to"]
        input_idx = conn.get("input", 0)
        target_inputs[to_id].append(input_idx)

    for nid, inputs in target_inputs.items():
        if len(inputs) > 1:
            sorted_inputs = sorted(inputs)
            expected = list(range(sorted_inputs[0], sorted_inputs[-1] + 1))
            if sorted_inputs != expected:
                warnings.append(
                    f"Node '{nid}' has input gap: indices {sorted_inputs} "
                    f"(expected contiguous {expected})"
                )

    return warnings


def topo_sort(
    node_ids: set,
    connections: List[Dict[str, Any]],
) -> List[str]:
    """Topological sort via Kahn's algorithm. Returns ordered node IDs.

    Deterministic: ties broken alphabetically.
    """
    in_degree = {nid: 0 for nid in node_ids}
    adjacency = defaultdict(list)

    for conn in connections:
        adjacency[conn["from"]].append(conn["to"])
        in_degree[conn["to"]] += 1

    # Use sorted() for deterministic ordering among equal in-degree nodes
    queue = sorted([nid for nid in node_ids if in_degree[nid] == 0])
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        neighbors = sorted(adjacency[node])
        for neighbor in neighbors:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                # Insert in sorted position
                queue.append(neighbor)
        queue.sort()

    return result


def _find_terminal_nodes(
    node_ids: set,
    connections: List[Dict[str, Any]],
) -> List[str]:
    """Find nodes with no outgoing connections (sink nodes)."""
    has_outgoing = {conn["from"] for conn in connections}
    return sorted(nid for nid in node_ids if nid not in has_outgoing)


# ── Handler Mixin ────────────────────────────────────────────────────────


class SolarisGraphMixin:
    """Mixin providing the solaris_build_graph handler."""

    def _handle_solaris_build_graph(self, payload: Dict) -> Dict:
        """Build a Solaris LOP network with arbitrary DAG topology.

        Supports merge nodes, sublayer stacks, parallel streams,
        and pre-built templates.

        Args:
            payload: Dict with keys:
                - parent: LOP network path (default: "/stage")
                - nodes: list of {id, type, name?, parms?}
                - connections: list of {from, to, input?, output?}
                - display_node: node id for display flag (auto-detects if omitted)
                - template: template name (optional)
                - template_params: params for template expansion (optional)
                - dry_run: preview without creating (default: false)

        Returns:
            {
                "status": "created" | "preview",
                "nodes_created": [{id, path}, ...],
                "connections_made": [{from, to, input}, ...],
                "display_node": path,
                "topology": "dag" | "linear" | "single",
                "merge_points": [path, ...],
                "warnings": [str, ...],
                "dry_run": bool
            }
        """
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        parent_path = resolve_param_with_default(payload, "parent", "/stage")
        raw_nodes = payload.get("nodes", [])
        raw_connections = payload.get("connections", [])
        display_node_id = payload.get("display_node", None)
        template_name = payload.get("template", None)
        template_params = payload.get("template_params", {})
        dry_run = payload.get("dry_run", False)

        # ── Template expansion ──
        if template_name:
            template_result = expand_template(
                template_name,
                params=template_params,
                overlay_nodes=raw_nodes if raw_nodes else None,
                overlay_connections=raw_connections if raw_connections else None,
            )
            raw_nodes = template_result["nodes"]
            raw_connections = template_result["connections"]
            if display_node_id is None:
                display_node_id = template_result.get("display_node")

        # ── Validation ──
        valid, errors, warnings = validate_graph(raw_nodes, raw_connections, display_node_id)
        if not valid:
            raise SynapseUserError(
                f"Invalid graph: {'; '.join(errors)}",
                suggestion="Check node IDs and connection references for typos or cycles",
            )

        if not raw_nodes:
            return {
                "status": "preview" if dry_run else "created",
                "nodes_created": [],
                "connections_made": [],
                "display_node": None,
                "topology": "single",
                "merge_points": [],
                "warnings": warnings,
                "dry_run": dry_run,
            }

        # ── Topo sort ──
        node_id_set = {n["id"] for n in raw_nodes}
        sorted_ids = topo_sort(node_id_set, raw_connections)
        node_map = {n["id"]: n for n in raw_nodes}

        # ── Auto-detect display node ──
        if display_node_id is None:
            terminals = _find_terminal_nodes(node_id_set, raw_connections)
            display_node_id = terminals[0] if terminals else sorted_ids[-1]

        # ── Classify topology ──
        if len(raw_nodes) == 1:
            topology = "single"
        elif any(conn.get("input", 0) > 0 for conn in raw_connections):
            topology = "dag"
        else:
            # Check fan-out
            from_counts = defaultdict(int)
            for conn in raw_connections:
                from_counts[conn["from"]] += 1
            topology = "dag" if any(c > 1 for c in from_counts.values()) else "linear"

        # ── Identify merge points (nodes with multiple inputs) ──
        input_counts = defaultdict(int)
        for conn in raw_connections:
            input_counts[conn["to"]] += 1
        merge_ids = [nid for nid, count in input_counts.items() if count > 1]

        if dry_run:
            return {
                "status": "preview",
                "nodes_created": [
                    {"id": nid, "path": f"{parent_path}/{node_map[nid].get('name', nid)}"}
                    for nid in sorted_ids
                ],
                "connections_made": [
                    {
                        "from": f"{parent_path}/{node_map[c['from']].get('name', c['from'])}",
                        "to": f"{parent_path}/{node_map[c['to']].get('name', c['to'])}",
                        "input": c.get("input", 0),
                    }
                    for c in raw_connections
                ],
                "display_node": f"{parent_path}/{node_map[display_node_id].get('name', display_node_id)}",
                "topology": topology,
                "merge_points": [
                    f"{parent_path}/{node_map[mid].get('name', mid)}"
                    for mid in merge_ids
                ],
                "warnings": warnings,
                "dry_run": True,
            }

        # ── Execute on main thread ──
        # Use _SLOW_TIMEOUT: Solaris network builds with Karma nodes
        # involve GPU context init and USD stage authoring that routinely
        # exceed the default 10s timeout, triggering the stall-detection
        # death spiral (timeout → ghost callback → duplicate nodes → crash).
        from .main_thread import run_on_main, _SLOW_TIMEOUT

        def _on_main():
            parent_node = hou.node(parent_path)
            if parent_node is None:
                raise NodeNotFoundError(
                    parent_path,
                    suggestion="Check that the LOP network path exists",
                )

            id_to_hou = {}
            nodes_created = []
            connections_made = []

            try:
                with hou.undos.group("SYNAPSE: build_graph"):
                    # 1. Create all nodes in topo order
                    for nid in sorted_ids:
                        spec = node_map[nid]
                        node_type = spec["type"]
                        node_name = spec.get("name", nid) or nid
                        node = parent_node.createNode(node_type, node_name)
                        id_to_hou[nid] = node
                        nodes_created.append({"id": nid, "path": node.path()})

                    # 2. Set parameters
                    for nid in sorted_ids:
                        spec = node_map[nid]
                        parms = spec.get("parms", {})
                        node = id_to_hou[nid]
                        for parm_name, parm_value in parms.items():
                            p = node.parm(parm_name)
                            if p is not None:
                                p.set(parm_value)

                    # 3. Wire connections
                    for conn in raw_connections:
                        source = id_to_hou[conn["from"]]
                        target = id_to_hou[conn["to"]]
                        input_idx = conn.get("input", 0)
                        output_idx = conn.get("output", 0)
                        target.setInput(input_idx, source, output_idx)
                        connections_made.append({
                            "from": source.path(),
                            "to": target.path(),
                            "input": input_idx,
                        })

                    # 4. Stamp provenance
                    for node in id_to_hou.values():
                        node.setComment("SYNAPSE: build_graph")
                        node.setGenericFlag(hou.nodeFlag.DisplayComment, True)

                    # 5. Layout BEFORE display flag — position nodes in clean
                    # vertical columns instead of Houdini's black-box
                    # layoutChildren(). Professional VFX artists use top-to-
                    # bottom vertical chains. This also avoids the GPU context
                    # init race condition that layoutChildren() can trigger
                    # with Karma nodes (CUDA double-init → segfault).
                    if topology == "linear":
                        # Simple vertical column for linear chains
                        ordered_nodes = [id_to_hou[nid] for nid in sorted_ids]
                        _layout_vertical_chain(ordered_nodes)
                    else:
                        # Layered vertical DAG for merge/fan-out topologies
                        _layout_dag_vertical(
                            sorted_ids, raw_connections, id_to_hou
                        )

                    # 6. Display flag AFTER layout — now the cook triggered
                    # by setDisplayFlag runs on a fully-laid-out, wired
                    # network with no concurrent layout evaluation.
                    display_hou = id_to_hou[display_node_id]
                    if hasattr(display_hou, "setDisplayFlag"):
                        try:
                            display_hou.setDisplayFlag(True)
                        except AttributeError:
                            pass  # RopNode — no display flag

            except Exception:
                # Safe undo fallback — the C++ undo layer for LOP nodes
                # with USD stage data can throw during __exit__ if GPU
                # resources are being deallocated. Catch and explicitly
                # undo to prevent undo stack corruption.
                try:
                    hou.undos.performUndo()
                except Exception as undo_exc:
                    logger.warning(
                        "build_graph: undo rollback also failed: %s", undo_exc
                    )
                raise

            return {
                "status": "created",
                "nodes_created": nodes_created,
                "connections_made": connections_made,
                "display_node": display_hou.path(),
                "topology": topology,
                "merge_points": [id_to_hou[mid].path() for mid in merge_ids],
                "warnings": warnings,
                "dry_run": False,
            }

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT)
