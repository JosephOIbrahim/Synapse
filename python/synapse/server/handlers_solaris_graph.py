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
from .handler_helpers import (
    _layout_dag_vertical, _layout_vertical_chain, _free_origin,
    _apply_section_boxes,
)
# Rank table is the single source of truth for both wiring order (assemble) and
# the M10 section bands here -- imported, never duplicated. Sibling data import,
# no cycle (assemble -> handler_helpers, graph -> handler_helpers + assemble).
from .handlers_solaris_assemble import (
    _SOLARIS_NODE_ORDER, _UNRANKED_RANK, _next_free_input,
)

logger = logging.getLogger(__name__)


# ── Recognition (B5) ─────────────────────────────────────────────────────
# The live creation path performed ZERO node-type validation: every recognition
# authority SYNAPSE owns was unreachable from the code an artist actually hits
# (grep known_absent|lop_knowledge|node_type_exists over server/ was empty).
# A single bad type therefore surfaced as a bare hou.OperationFailed raised
# mid-build, rolling back every other node in the graph -- while the catalog
# already held the exact remediation for it.


def _absent_type_remediation(type_name: str) -> Optional[str]:
    """The catalog's fix-it string for a known-absent LOP type, if any.

    Never raises: a missing/corrupt catalog degrades to None and the caller
    still rejects the type, just without the extra guidance.
    """
    try:
        from ..core.lop_knowledge import load_lop_catalog
        catalog = load_lop_catalog(strict=False)
        if not isinstance(catalog, dict):
            return None
        content = catalog.get("content")
        if not isinstance(content, dict):
            return None
        entry = (content.get("known_absent") or {}).get(type_name)
        if isinstance(entry, dict):
            return entry.get("remediation")
    except Exception:  # noqa: BLE001 -- guidance is best-effort, never fatal
        return None
    return None


def _validate_node_types(parent_node, node_map: Dict[str, Dict]) -> None:
    """Reject unknown node types BEFORE the undo group opens.

    Collects every bad type in one pass so the caller sees all of them at once
    rather than discovering them one failed build at a time -- the same posture
    GraphValidator's symbol phase already takes on the /mcp path.
    """
    try:
        category = parent_node.childTypeCategory()
    except Exception:  # noqa: BLE001 -- unknown container: skip, never false-reject
        return

    bad: List[str] = []
    for spec in node_map.values():
        if spec.get("existing"):
            continue  # resolved live, not created -- no type to validate
        type_name = spec.get("type")
        if not type_name or not isinstance(type_name, str):
            continue
        try:
            exists = hou.nodeType(category, type_name) is not None
        except Exception:  # noqa: BLE001
            continue
        if exists:
            continue
        remediation = _absent_type_remediation(type_name)
        bad.append("'%s'%s" % (type_name,
                               (" -- " + remediation) if remediation else ""))

    if bad:
        raise SynapseUserError(
            "unknown %s node type(s): %s"
            % (category.name(), "; ".join(sorted(set(bad)))),
            suggestion=("Nothing was created. Fix the node type(s) and re-run "
                        "-- synapse_scout will confirm what exists on this build."),
        )


def _set_parm(node, parm_name: str, value) -> Tuple[bool, bool]:
    """Set ``parm_name`` on ``node``, resolving USD punycode + tuples.

    Returns ``(landed, changed)``. ``landed`` is True if the value actually
    landed; ``changed`` is True only if the post-set value DIFFERED from the
    parm's prior value. Comparing the post-set eval to the prior eval (rather
    than the raw incoming value) is coercion-proof: an int written to a float
    parm reports changed only when it genuinely moved the parm. The literal
    name is tried first so an exact match always wins; only then the punycode
    encoding, then the tuple form. Anything still unset is the caller's to
    report -- never silently dropped (M4). ``changed`` only matters for a
    reused node -- it is what turns a full-reuse rebuild from 'unchanged' into
    'updated' when a parm value actually moved.
    """
    for candidate in (parm_name, _punycode_encoded(parm_name)):
        if not candidate:
            continue
        p = node.parm(candidate)
        if p is not None:
            try:
                prior = p.eval()
                p.set(value)
                return True, (p.eval() != prior)
            except Exception:  # noqa: BLE001 -- wrong type/shape: report it
                return False, False
        tup = node.parmTuple(candidate)
        if tup is not None:
            try:
                prior = tuple(tup.eval())
                tup.set(value)
                return True, (tuple(tup.eval()) != prior)
            except Exception:  # noqa: BLE001
                return False, False
    return False, False


def _punycode_encoded(alias: str) -> Optional[str]:
    """The punycode-encoded LOP parm name for a friendly USD alias, or None."""
    try:
        from ..core.usd_punycode import encoded
        return encoded(alias)
    except Exception:  # noqa: BLE001 -- resolution is best-effort
        return None


def _ensure_node(parent_node, node_type: str, node_name: str) -> Tuple[Any, bool]:
    """Create ``node_name`` under ``parent_node``, or reuse it if it already
    matches. Returns ``(node, created)``.

    B4: this was a raw ``createNode``. Houdini auto-uniquifies a colliding name,
    so running an identical build twice produced a SECOND complete network drawn
    on top of the first (OUTPUT -> OUTPUT1) and moved the display flag to it,
    reporting status='created' with no warnings. Build -> look -> rebuild is the
    core artist loop, which made the tool unsafe to point at a populated shot.

    Reuse requires the TYPE to match as well as the name -- guards.ensure_node
    matches on name alone, which would silently hand back a `null` when a
    `merge` was asked for. A name collision across types is a real conflict and
    is raised rather than papered over.
    """
    existing = parent_node.node(node_name)
    if existing is None:
        return parent_node.createNode(node_type, node_name), True

    existing_base = existing.type().name().split("::")[0]
    wanted_base = node_type.split("::")[0]
    if existing_base == wanted_base:
        return existing, False

    raise SynapseUserError(
        "'%s' already exists at %s as a '%s', but the graph asks for a '%s'"
        % (node_name, existing.path(), existing_base, wanted_base),
        suggestion=("Rename the node in the graph, or delete the existing one "
                    "first. Nothing was created."),
    )


def _resolve_existing_node(parent_node, spec: Dict) -> Any:
    """Resolve a node marked ``existing: true`` to the live node it names.

    An existing spec references a node the artist already built -- build_graph
    wires INTO it (e.g. append an asset to a merge) but never creates, moves,
    stamps, or sections it. Resolution is by ``path`` (absolute, or relative to
    ``parent_node``) or by ``name`` (a child of ``parent_node``). Absence is a
    hard, clear failure -- wiring a graph against a node that is not there is
    never what the artist meant.
    """
    path = spec.get("path")
    name = spec.get("name")
    node = None
    if path:
        node = (hou.node(path) if str(path).startswith("/")
                else parent_node.node(path))
    elif name:
        node = parent_node.node(name)
    if node is None:
        ref = path or name or spec.get("id")
        raise SynapseUserError(
            "existing node '%s' was not found under %s"
            % (ref, parent_node.path()),
            suggestion=("Mark a node 'existing' only if it is already in the "
                        "network. Check the name/path, or drop 'existing' to "
                        "create it. Nothing was changed."),
        )
    return node


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

    # Existing-node specs must name the live node they reference. Caught here
    # (pure, before any hou) so a typo fails loud instead of at wiring time.
    for n in nodes:
        if n.get("existing") and not (n.get("name") or n.get("path")):
            errors.append(
                f"Existing node '{n['id']}' must give a 'name' or 'path' to "
                "resolve the live node"
            )

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


# Base LOP types where the input INDEX determines USD opinion/layer strength.
# Mirrors handlers_usd._ORDER_DEPENDENT_TYPES — kept local (not imported) to
# avoid pulling the heavy USD handler module into the graph builder's import
# chain. ``switch``/``null``/``output`` are explicitly order-INDEPENDENT.
_ORDER_DEPENDENT_BASE = frozenset({"merge", "sublayer", "graft", "layerbreak"})
_ORDER_INDEPENDENT_BASE = frozenset({"switch", "switchif", "null", "output"})


def detect_order_ambiguities(
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Surface (never silently reorder) order-dependent merge/sublayer targets.

    FIX 2 / CLAUDE.md §11.12 "never trust LLM boundary flags": for order-
    dependent LOPs (merge / sublayer / graft / layerbreak) the input INDEX
    decides USD opinion strength — and on the Solaris merge & sublayer LOPs the
    HIGHER input index is the STRONGER opinion (the opposite of raw USD
    subLayerPaths). build_graph wires ``conn['input']`` verbatim from the
    caller/LLM, so a flipped index silently inverts which layer wins.

    We can't know the artist's intended strength, so we must NOT auto-correct
    (a forced reorder can be just as wrong). Instead we DETECT every multi-input
    order-dependent node and SURFACE it for review.

    Returns a deterministic ``list[dict]`` with the same shape as
    ``solaris_validate_ordering`` issues: ``node`` (id), ``node_type``,
    ``input_count``, ``current_order`` (source ids ordered by input index),
    ``suggested_fix``.
    """
    type_by_id = {n["id"]: str(n.get("type", "")) for n in nodes}
    inbound: Dict[str, List[Tuple[int, str]]] = defaultdict(list)
    for conn in connections:
        inbound[conn["to"]].append((conn.get("input", 0), conn["from"]))

    findings: List[Dict[str, Any]] = []
    for to_id, pairs in inbound.items():
        if len(pairs) < 2:
            continue
        base = type_by_id.get(to_id, "").split("::")[0].lower()
        if base in _ORDER_INDEPENDENT_BASE:
            continue
        is_order_dependent = (
            base in _ORDER_DEPENDENT_BASE
            or base.startswith("merge")
            or base.startswith("sublayer")
        )
        if not is_order_dependent:
            continue

        current_order = [fid for _idx, fid in sorted(pairs, key=lambda p: p[0])]
        if "sublayer" in base:
            fix = (
                "Verify sublayer order matches intended opinion strength -- on "
                "the Solaris sublayer LOP the HIGHER input index is the STRONGER "
                "opinion (opposite of raw USD subLayerPaths)"
            )
        else:
            fix = (
                "Verify merge order matches intended layer strength -- on the "
                "Solaris merge LOP the HIGHER input index wins; check geometry, "
                "materials and lights are in the expected order"
            )
        findings.append({
            "node": to_id,
            "node_type": type_by_id.get(to_id, ""),
            "input_count": len(pairs),
            "current_order": current_order,
            "suggested_fix": fix,
        })

    findings.sort(key=lambda f: f["node"])
    return findings


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

        # ── FIX 2: detect-and-surface order-dependent input ambiguities ──
        # We honour the caller's explicit input indices (forcing a reorder can
        # be just as wrong as trusting one), but we refuse to accept them
        # silently for merge/sublayer-style LOPs where index = opinion
        # strength. Surface every such node so the caller reviews the order.
        ambiguous_merges = detect_order_ambiguities(raw_nodes, raw_connections)
        for f in ambiguous_merges:
            warnings.append(
                f"Order-dependent merge target '{f['node']}' "
                f"({f['node_type']}) has {f['input_count']} inputs in order "
                f"{f['current_order']} -- {f['suggested_fix']}"
            )

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
                "ambiguous_merges": ambiguous_merges,
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
            existing_nids: set = set()   # ids resolved live, never mutated
            nodes_created = []
            nodes_reused = []
            parms_missed = []
            parms_changed = False
            connections_changed = False   # did any wire actually move this build?
            connections_made = []

            # B5: reject unknown types BEFORE opening the undo group, so a bad
            # type costs nothing instead of rolling back a whole graph.
            _validate_node_types(parent_node, node_map)

            try:
                with hou.undos.group("SYNAPSE: build_graph"):
                    # 1. Create all nodes in topo order
                    for nid in sorted_ids:
                        spec = node_map[nid]
                        if spec.get("existing"):
                            # Resolve the artist's live node -- never create,
                            # and exclude it from stamp/layout/section below.
                            node = _resolve_existing_node(parent_node, spec)
                            id_to_hou[nid] = node
                            existing_nids.add(nid)
                            continue
                        node_type = spec["type"]
                        node_name = spec.get("name", nid) or nid
                        node, created = _ensure_node(
                            parent_node, node_type, node_name)
                        id_to_hou[nid] = node
                        entry = {"id": nid, "path": node.path()}
                        if created:
                            nodes_created.append(entry)
                        else:
                            nodes_reused.append(entry)

                    # 2. Set parameters (new nodes only -- an existing node's
                    # parms are the artist's; build_graph never touches them).
                    for nid in sorted_ids:
                        if nid in existing_nids:
                            continue
                        spec = node_map[nid]
                        parms = spec.get("parms", {})
                        node = id_to_hou[nid]
                        for parm_name, parm_value in parms.items():
                            # M4: this was a bare `if p is not None` -- an
                            # unresolvable name was dropped and success still
                            # returned, so a light rig reported as dialed in
                            # sat at its defaults. USD light parms carry
                            # punycode-encoded names on the LOP interface
                            # (`intensity` -> `xn__inputsintensity_i0a`), which
                            # is exactly the case that silently vanished.
                            # Resolve, then parmTuple, then REPORT the miss.
                            landed, changed = _set_parm(node, parm_name, parm_value)
                            if landed:
                                if changed:
                                    parms_changed = True
                                continue
                            parms_missed.append({
                                "node": node.path(),
                                "parm": parm_name,
                                "value": repr(parm_value)[:80],
                            })

                    # 3. Wire connections
                    #
                    # B4 seam: reuse-by-name is safe for a true rebuild (the
                    # reused node's inputs already match the spec, so setInput is
                    # a no-op), but it must NOT silently clobber a DIFFERENT
                    # existing connection. Two independent networks in one /stage
                    # that happen to share a node name (every template has an
                    # "OUTPUT" null) would otherwise cross-wire: building the
                    # second silently rewired the first. Refuse on a real
                    # conflict -- the undo group rolls this build back, leaving
                    # the existing network intact.
                    reused_ids = {e["id"] for e in nodes_reused}
                    for conn in raw_connections:
                        source = id_to_hou[conn["from"]]
                        target = id_to_hou[conn["to"]]
                        to_id = conn["to"]
                        output_idx = conn.get("output", 0)
                        explicit_input = conn.get("input")   # None if omitted

                        # Wiring a NEW source into a node the artist already owns
                        # must APPEND to the next free input, never clobber
                        # input 0. Reuse assemble's _next_free_input. An EXPLICIT
                        # index is honoured verbatim and guarded just below.
                        # Live-verified on 22.0.368: merge[a,b] + asset_c at the
                        # next free index 2 -> [a,b,c], first two untouched.
                        if to_id in existing_nids and explicit_input is None:
                            # IDEMPOTENT APPEND (seam fix): if this source already
                            # feeds the target, do NOT re-append it on a rebuild.
                            # Without this, build->look->rebuild grows the merge
                            # unboundedly ([a,b,c] -> [a,b,c,c] -> ...), corrupting
                            # the artist's network -- the exact loop item 2 exists
                            # to make safe. _next_free_input always returns a fresh
                            # index, so the guard must live here.
                            if source in target.inputs():
                                connections_made.append({
                                    "from": source.path(),
                                    "to": target.path(),
                                    "input": list(target.inputs()).index(source),
                                })
                                continue                 # already wired -- no-op
                            input_idx = _next_free_input(target)
                        else:
                            input_idx = (explicit_input
                                         if explicit_input is not None else 0)

                        if to_id in reused_ids:
                            cur = target.inputs()
                            occupied = (cur[input_idx]
                                        if input_idx < len(cur) else None)
                            if occupied is not None and occupied != source:
                                raise SynapseUserError(
                                    "'%s' already exists wired to '%s' on input "
                                    "%d, but this build wires it to '%s' -- a "
                                    "name collision with a different network."
                                    % (target.name(), occupied.name(),
                                       input_idx, source.name()),
                                    suggestion=(
                                        "Nothing was changed. Rename the node in "
                                        "your graph, or build into a fresh LOP "
                                        "network -- build_graph reuses a node of "
                                        "the same name+type, so two networks in "
                                        "one /stage must not share node names."),
                                )

                        # An EXPLICIT index into an artist-owned existing node
                        # that would overwrite a DIFFERENT source is refused
                        # (append never trips this -- _next_free_input returns an
                        # unoccupied index; same-source is an idempotent no-op).
                        if to_id in existing_nids and explicit_input is not None:
                            cur = target.inputs()
                            occupied = (cur[input_idx]
                                        if input_idx < len(cur) else None)
                            if occupied is not None and occupied != source:
                                raise SynapseUserError(
                                    "existing node '%s' already has '%s' on input "
                                    "%d, but this build wires '%s' there -- "
                                    "refusing to overwrite the artist's wiring."
                                    % (target.name(), occupied.name(),
                                       input_idx, source.name()),
                                    suggestion=(
                                        "Nothing was changed. Drop the explicit "
                                        "'input' to append to the next free "
                                        "input, or choose an unused index."),
                                )
                        # A wire is only a CHANGE if the slot did not already
                        # hold this exact source -- so a true rebuild (re-setting
                        # identical connections) stays 'unchanged', while an added
                        # or rewired input flips status to 'updated' (seam fix:
                        # status must not report 'unchanged' after a topology
                        # change).
                        cur = target.inputs()
                        prior = cur[input_idx] if input_idx < len(cur) else None
                        # `!=`, not `is not`: two hou.Node wrappers for the SAME
                        # node fail identity but compare equal, so an identical
                        # rebuild (re-setting the same connection) must read as
                        # NO change -- otherwise it falsely reports 'updated'.
                        if prior != source:
                            connections_changed = True
                        target.setInput(input_idx, source, output_idx)
                        connections_made.append({
                            "from": source.path(),
                            "to": target.path(),
                            "input": input_idx,
                        })

                    # 4. Stamp provenance -- new nodes only; an existing node is
                    # the artist's and must not be re-commented or re-flagged.
                    for nid, node in id_to_hou.items():
                        if nid in existing_nids:
                            continue
                        node.setComment("SYNAPSE: build_graph")
                        node.setGenericFlag(hou.nodeFlag.DisplayComment, True)

                    # 5. Layout BEFORE display flag — position nodes in clean
                    # vertical columns instead of Houdini's black-box
                    # layoutChildren(). Professional VFX artists use top-to-
                    # bottom vertical chains. This also avoids the GPU context
                    # init race condition that layoutChildren() can trigger
                    # with Karma nodes (CUDA double-init → segfault).
                    # M7: origin below existing content so a build into a
                    # populated stage reads as its own column instead of landing
                    # on top of what's already there. New nodes are excluded so
                    # only pre-existing children move the origin.
                    # Existing (artist-owned) nodes are resolved for wiring
                    # only: never moved, and never counted as this build's
                    # content. Everything below operates on the NEW nodes.
                    new_id_to_hou = {nid: n for nid, n in id_to_hou.items()
                                     if nid not in existing_nids}
                    new_sorted_ids = [nid for nid in sorted_ids
                                      if nid not in existing_nids]
                    new_paths = {n.path() for n in new_id_to_hou.values()}
                    ox, oy = _free_origin(parent_node, new_paths)
                    if topology == "linear":
                        # Simple vertical column for linear chains
                        ordered_nodes = [new_id_to_hou[nid]
                                         for nid in new_sorted_ids]
                        _layout_vertical_chain(ordered_nodes, ox, oy)
                    else:
                        # Layered vertical DAG for merge/fan-out topologies.
                        # raw_connections may reference existing ids; the DAG
                        # layout only positions ids present in new_id_to_hou, so
                        # an edge into an existing node leaves that node untouched
                        # (_compute_dag_positions filters parents not in depth).
                        _layout_dag_vertical(
                            new_sorted_ids, raw_connections, new_id_to_hou,
                            start_x=ox, start_y=oy,
                        )

                    # 5b. Section boxes (M10) — after layout so fitAroundContents
                    # reads final positions; idempotent so a rebuild refreshes
                    # rather than stacks. Cosmetic + best-effort: never fails the
                    # build. Ranks come from the same table assemble_chain wires by.
                    # New nodes only. node_map has no 'type' for existing specs,
                    # so keying ranks off new_id_to_hou also avoids a KeyError,
                    # and an existing node keeps whatever box the artist gave it.
                    # Namespace the boxes by the build's display-node name so a
                    # second network into the same /stage keeps its own boxes
                    # (per-network identity; M10 fast-follow).
                    node_ranks = {
                        nid: _SOLARIS_NODE_ORDER.get(
                            str(node_map[nid]["type"]).split("::")[0].lower(),
                            _UNRANKED_RANK)
                        for nid in new_id_to_hou
                    }
                    sections = _apply_section_boxes(
                        parent_node, new_id_to_hou, node_ranks,
                        namespace=id_to_hou[display_node_id].name())

                    # 6. Display flag AFTER layout — now the cook triggered
                    # by setDisplayFlag runs on a fully-laid-out, wired
                    # network with no concurrent layout evaluation.
                    display_hou = id_to_hou[display_node_id]
                    # Never move the display flag onto an existing (artist-owned)
                    # node -- it may already sit upstream of its own downstream
                    # chain (merge -> rendersettings -> rop), and stealing the
                    # flag would blank the viewport/export the artist set up.
                    if (display_node_id not in existing_nids
                            and hasattr(display_hou, "setDisplayFlag")):
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

            # B4: a rebuild that reused everything is not a "created" -- saying
            # so is the same lie the duplicate network told, pointed the other
            # way. The status names what actually happened.
            # 'created' when new nodes were made; 'updated' when only pre-existing
            # nodes (reused-by-name or artist-owned 'existing') were touched but
            # a parm or a wire actually moved; 'unchanged' when a rebuild was a
            # genuine no-op. A build that only references existing nodes (an
            # extend that appends nothing new) must never read 'created'.
            _touched = parms_changed or connections_changed
            if nodes_created:
                status = "updated" if nodes_reused else "created"
            elif nodes_reused or existing_nids:
                status = "updated" if _touched else "unchanged"
            else:
                status = "created"
            # Mutate rather than rebind: `warnings` is the enclosing function's
            # list (bound at validate_graph), and rebinding it here would make
            # it local to _on_main and break every earlier read.
            if nodes_reused:
                warnings.append(
                    "reused %d existing node(s) by name+type instead of "
                    "duplicating them" % len(nodes_reused))
            if parms_missed:
                warnings.append(
                    "%d parameter(s) could not be set and were NOT applied -- "
                    "see parms_missed" % len(parms_missed))

            return {
                "status": status,
                "nodes_created": nodes_created,
                "nodes_reused": nodes_reused,
                "existing_nodes": [
                    {"id": nid, "path": id_to_hou[nid].path()}
                    for nid in sorted(existing_nids)
                ],
                "sections": sections,
                "parms_missed": parms_missed,
                "connections_made": connections_made,
                "display_node": display_hou.path(),
                "topology": topology,
                "merge_points": [id_to_hou[mid].path() for mid in merge_ids],
                "ambiguous_merges": ambiguous_merges,
                "warnings": warnings,
                "dry_run": False,
            }

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT)
