"""
SYNAPSE Explain Mode -- Contextual node/network interpretation for artists.

Artists select a node and type /explain to get a plain-English explanation
of what that specific node is actually doing in their scene.  This is NOT
documentation -- it is contextual interpretation of the node's current state,
parameter values, connections, and data flow.

Outside Houdini the module still imports cleanly -- gather functions return
minimal dicts immediately.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Houdini import guard
# ---------------------------------------------------------------------------
_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]

# Maximum nodes to trace when walking a data flow chain.
_MAX_CHAIN_LENGTH = 50


# ============================================================================
# Internal helpers
# ============================================================================

def _get_cook_time(node) -> float:
    """Return cook time in milliseconds for *node*.

    Uses ``hou.perfMon`` when available.  Returns 0.0 on any failure --
    cook time is informational, never worth crashing over.
    """
    try:
        profile = hou.perfMon.activeProfile()
        if profile is not None:
            stats = profile.stats(node)
            if stats is not None:
                return stats.cookTime() * 1000.0  # seconds -> ms
    except Exception:
        pass
    # Fallback: try the node's intrinsic cook time if exposed
    try:
        return node.cookTime() * 1000.0
    except Exception:
        pass
    return 0.0


def _format_geo_summary(node) -> Optional[Dict[str, Any]]:
    """Compact geometry stats for *node*.

    Returns ``None`` when the node has no geometry or geometry cannot be read
    (e.g. OBJ-level nodes, errored cooks).
    """
    try:
        geo = node.geometry()
    except Exception:
        return None
    if geo is None:
        return None

    try:
        point_count = len(geo.points())
        prim_count = len(geo.prims())
    except Exception:
        return None

    # Attributes grouped by class
    attribs: Dict[str, List[str]] = {}
    for label, accessor in (
        ("point", "pointAttribs"),
        ("prim", "primAttribs"),
        ("vertex", "vertexAttribs"),
        ("detail", "globalAttribs"),
    ):
        try:
            attr_list = getattr(geo, accessor)()
            names = [a.name() for a in attr_list]
            if names:
                attribs[label] = names
        except Exception:
            pass

    # Bounding box
    bounds = None
    try:
        bb = geo.boundingBox()
        bounds = {
            "min": [bb.minvec()[0], bb.minvec()[1], bb.minvec()[2]],
            "max": [bb.maxvec()[0], bb.maxvec()[1], bb.maxvec()[2]],
        }
    except Exception:
        pass

    return {
        "point_count": point_count,
        "prim_count": prim_count,
        "attribs": attribs,
        "bounds": bounds,
    }


def _brief_geo_summary(node) -> str:
    """One-line geometry summary for use in connection listings."""
    info = _format_geo_summary(node)
    if info is None:
        return "no geometry"
    # Flatten attribute names across all classes
    all_attr_names: List[str] = []
    for names in info.get("attribs", {}).values():
        for n in names:
            if n not in all_attr_names:
                all_attr_names.append(n)
    attr_str = ", ".join(all_attr_names[:8])
    if len(all_attr_names) > 8:
        attr_str += f" (+{len(all_attr_names) - 8} more)"
    return f"{info['point_count']} pts, {info['prim_count']} prims, attribs: {attr_str}"


def _trace_data_flow(display_node) -> list:
    """Walk backwards from *display_node* through input[0] connections.

    Returns a list of nodes in top-to-bottom (data flow) order.
    Follows the primary (input 0) path only.  Stops at *_MAX_CHAIN_LENGTH*
    nodes to prevent runaway on huge networks.
    """
    chain: list = []
    visited: set = set()
    current = display_node

    while current is not None and len(chain) < _MAX_CHAIN_LENGTH:
        node_path = current.path()
        if node_path in visited:
            break  # cycle guard
        visited.add(node_path)
        chain.append(current)

        inputs = current.inputs()
        if inputs and inputs[0] is not None:
            current = inputs[0]
        else:
            current = None

    chain.reverse()
    return chain


def _position_in_chain(node) -> str:
    """Determine where *node* sits in its local network chain."""
    has_inputs = any(inp is not None for inp in node.inputs())
    has_outputs = bool(node.outputConnections())

    if has_inputs and has_outputs:
        return "middle"
    elif has_inputs and not has_outputs:
        return "last"
    elif not has_inputs and has_outputs:
        return "first"
    else:
        return "only"


def _parm_type_label(parm) -> str:
    """Human-readable parameter type string."""
    try:
        tmpl = parm.parmTemplate()
        return tmpl.type().name()
    except Exception:
        return "unknown"


def _get_non_default_parms(node) -> List[Dict[str, Any]]:
    """Return parameters whose current value differs from default."""
    result: List[Dict[str, Any]] = []
    for parm in node.parms():
        try:
            tmpl = parm.parmTemplate()
            defaults = tmpl.defaultValue()
            # hou.Parm read -- NOT Python's eval()
            val = parm.eval()  # noqa: S307

            # defaultValue() returns a tuple for scalars -- unwrap
            if isinstance(defaults, tuple) and len(defaults) == 1:
                default = defaults[0]
            else:
                default = defaults

            if val != default:
                result.append({
                    "name": parm.name(),
                    "label": tmpl.label(),
                    "value": val,
                    "default": default,
                    "type": _parm_type_label(parm),
                })
        except Exception:
            pass
    return result


# ============================================================================
# Public API -- context gathering
# ============================================================================

def gather_node_context(node_path: str) -> Dict[str, Any]:
    """Gather everything about a single node for Claude to explain.

    Returns a structured dict with the node's type, parameters, connections,
    geometry, cook state, and position in the network.  If ``hou`` is
    unavailable, returns a minimal dict with just the path.
    """
    if not _HOU_AVAILABLE:
        return {"node_path": node_path, "error": "hou module not available"}

    node = hou.node(node_path)
    if node is None:
        return {"node_path": node_path, "error": f"Node not found: {node_path}"}

    node_type = node.type()

    # -- Input connections with brief geo summaries --
    input_connections: List[Dict[str, Any]] = []
    for i, inp in enumerate(node.inputs()):
        if inp is not None:
            input_connections.append({
                "index": i,
                "node_path": inp.path(),
                "node_type": inp.type().name(),
                "geo_summary": _brief_geo_summary(inp),
            })

    # -- Output connections --
    output_connections: List[Dict[str, Any]] = []
    for conn in node.outputConnections():
        output_connections.append({
            "index": conn.inputIndex(),
            "node_path": conn.outputNode().path(),
            "node_type": conn.outputNode().type().name(),
        })

    # -- Errors and warnings --
    errors: List[str] = []
    warnings: List[str] = []
    try:
        errors = list(node.errors())
    except Exception:
        pass
    try:
        warnings = list(node.warnings())
    except Exception:
        pass

    # -- Flags --
    has_display = False
    has_render = False
    try:
        has_display = node.isDisplayFlagSet()
    except Exception:
        pass
    try:
        has_render = node.isRenderFlagSet()
    except Exception:
        pass

    # -- User comment --
    user_comment = ""
    try:
        user_comment = node.comment() or ""
    except Exception:
        pass

    return {
        "node_path": node_path,
        "node_type": node_type.name(),
        "type_label": node_type.description(),
        "type_description": node_type.description(),
        "category": node_type.category().name(),
        "non_default_parms": _get_non_default_parms(node),
        "input_connections": input_connections,
        "output_connections": output_connections,
        "geometry": _format_geo_summary(node),
        "cook_time_ms": _get_cook_time(node),
        "errors": errors,
        "warnings": warnings,
        "has_display_flag": has_display,
        "has_render_flag": has_render,
        "user_comment": user_comment,
        "position_in_chain": _position_in_chain(node),
    }


def gather_network_context(network_path: str) -> Dict[str, Any]:
    """Gather info about an entire network for data-flow explanation.

    Traces the primary data path from the first node (no upstream inputs
    within this network) to the display node, collecting geometry deltas,
    cook times, and key parameters at each step.
    """
    if not _HOU_AVAILABLE:
        return {"network_path": network_path, "error": "hou module not available"}

    network = hou.node(network_path)
    if network is None:
        return {"network_path": network_path, "error": f"Network not found: {network_path}"}

    children = network.children()
    node_count = len(children)

    # Find display node
    display_node = None
    try:
        display_node = network.displayNode()
    except Exception:
        pass

    # Trace the data flow
    flow_nodes = _trace_data_flow(display_node) if display_node else []

    # Build flow entries with geometry deltas
    flow: List[Dict[str, Any]] = []
    prev_pt_count: Optional[int] = None
    prev_prim_count: Optional[int] = None
    total_cook_time = 0.0
    max_cook_time = 0.0
    bottleneck: Optional[str] = None

    for fn in flow_nodes:
        cook_ms = _get_cook_time(fn)
        total_cook_time += cook_ms
        if cook_ms > max_cook_time:
            max_cook_time = cook_ms
            bottleneck = fn.path()

        # Geometry delta
        geo_info = _format_geo_summary(fn)
        if geo_info is not None:
            cur_pts = geo_info["point_count"]
            cur_prims = geo_info["prim_count"]
            if prev_pt_count is not None:
                if cur_pts == prev_pt_count and cur_prims == prev_prim_count:
                    geo_delta = "no change"
                else:
                    geo_delta = f"{prev_pt_count} pts -> {cur_pts} pts, {prev_prim_count} prims -> {cur_prims} prims"
            else:
                geo_delta = f"{cur_pts} pts, {cur_prims} prims"
            prev_pt_count = cur_pts
            prev_prim_count = cur_prims
        else:
            geo_delta = "no geometry"

        # Top 3 non-default parms
        non_defaults = _get_non_default_parms(fn)
        key_parms = [{"name": p["name"], "value": p["value"]} for p in non_defaults[:3]]

        # Errors
        node_errors: List[str] = []
        try:
            node_errors = list(fn.errors())
        except Exception:
            pass

        flow.append({
            "node_path": fn.path(),
            "node_type": fn.type().name(),
            "label": fn.type().description(),
            "key_parms": key_parms,
            "geo_delta": geo_delta,
            "cook_time_ms": cook_ms,
            "errors": node_errors,
        })

    # If bottleneck has zero cook time, there is no meaningful bottleneck
    if max_cook_time == 0.0:
        bottleneck = None

    return {
        "network_path": network_path,
        "network_type": network.type().category().name() if hasattr(network.type(), "category") else "unknown",
        "node_count": node_count,
        "flow": flow,
        "display_node": display_node.path() if display_node else None,
        "total_cook_time_ms": total_cook_time,
        "bottleneck": bottleneck,
    }


# ============================================================================
# Public API -- prompt building
# ============================================================================

def build_explain_prompt(context: Dict[str, Any], mode: str = "node") -> str:
    """Build a system prompt addendum for Claude to explain the node or network.

    Args:
        context: Output of ``gather_node_context`` or ``gather_network_context``.
        mode: ``"node"`` for single-node explanation, ``"network"`` for full flow.

    Returns:
        A system prompt string with guidance for contextual explanation.
    """
    if mode == "node":
        return (
            "You are explaining a single Houdini node to an artist. Be specific about "
            "what THIS node is doing with its CURRENT settings. Don't recite documentation. "
            "Explain like a senior artist walking a junior through the scene.\n\n"
            "Start with what the node does in one sentence, then detail the key parameters "
            "and what they're set to, then how it connects to the rest of the network. "
            "Use the artist's language, not API terms.\n\n"
            "If the node has errors or warnings, explain what they mean and suggest fixes. "
            "If parameters are at non-default values, explain why those values matter -- "
            "what would change if they were at default.\n\n"
            "Keep it conversational. No bullet-point walls unless the node is complex."
        )
    elif mode == "network":
        return (
            "You are walking through a Houdini network, explaining the data flow from "
            "start to finish. For each node, explain what transformation it applies and "
            "how the data changes. Mention point/prim counts at each step. Highlight the "
            "bottleneck if one exists. Be concise but thorough.\n\n"
            "Frame it as a story: 'First we start with X, then Y transforms it into Z...' "
            "The artist should understand the whole pipeline after reading your explanation.\n\n"
            "If there are errors in the chain, flag them clearly and explain the impact "
            "on downstream nodes."
        )
    else:
        return f"Explain the following Houdini {mode} context to an artist."


def build_explain_messages(context: Dict[str, Any], mode: str = "node") -> List[Dict[str, str]]:
    """Build the messages list for a Claude API call.

    Args:
        context: Output of ``gather_node_context`` or ``gather_network_context``.
        mode: ``"node"`` for single-node explanation, ``"network"`` for full flow.

    Returns:
        A list of message dicts with ``role`` and ``content`` keys.
    """
    system_prompt = build_explain_prompt(context, mode)

    if mode == "node":
        user_content = _format_node_context(context)
    else:
        user_content = _format_network_context(context)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


# ============================================================================
# Context formatting -- structured text, not raw JSON
# ============================================================================

def _format_node_context(ctx: Dict[str, Any]) -> str:
    """Format node context as readable structured text for the user message."""
    lines: List[str] = []
    lines.append(f"Explain this node:")
    lines.append(f"")
    lines.append(f"Node: {ctx.get('node_path', 'unknown')}")
    lines.append(f"Type: {ctx.get('type_label', ctx.get('node_type', 'unknown'))} ({ctx.get('node_type', '')})")
    lines.append(f"Category: {ctx.get('category', 'unknown')}")
    lines.append(f"Position in chain: {ctx.get('position_in_chain', 'unknown')}")

    if ctx.get("user_comment"):
        lines.append(f"Artist comment: {ctx['user_comment']}")

    # Flags
    flags = []
    if ctx.get("has_display_flag"):
        flags.append("display")
    if ctx.get("has_render_flag"):
        flags.append("render")
    if flags:
        lines.append(f"Flags: {', '.join(flags)}")

    # Non-default parameters
    parms = ctx.get("non_default_parms", [])
    if parms:
        lines.append(f"")
        lines.append(f"Parameters changed from default ({len(parms)}):")
        for p in parms:
            lines.append(f"  {p['label']} ({p['name']}): {p['value']}  [default: {p['default']}]")
    else:
        lines.append(f"")
        lines.append(f"All parameters at default values.")

    # Input connections
    inputs = ctx.get("input_connections", [])
    if inputs:
        lines.append(f"")
        lines.append(f"Inputs:")
        for inp in inputs:
            lines.append(f"  [{inp['index']}] {inp['node_path']} ({inp['node_type']}) -- {inp.get('geo_summary', '')}")

    # Output connections
    outputs = ctx.get("output_connections", [])
    if outputs:
        lines.append(f"")
        lines.append(f"Outputs:")
        for out in outputs:
            lines.append(f"  -> {out['node_path']} ({out['node_type']})")

    # Geometry
    geo = ctx.get("geometry")
    if geo:
        lines.append(f"")
        lines.append(f"Geometry: {geo['point_count']} points, {geo['prim_count']} primitives")
        attribs = geo.get("attribs", {})
        for cls, names in attribs.items():
            lines.append(f"  {cls} attribs: {', '.join(names)}")
        if geo.get("bounds"):
            b = geo["bounds"]
            lines.append(f"  Bounds: min({b['min'][0]:.2f}, {b['min'][1]:.2f}, {b['min'][2]:.2f}) "
                         f"max({b['max'][0]:.2f}, {b['max'][1]:.2f}, {b['max'][2]:.2f})")

    # Cook time
    cook_ms = ctx.get("cook_time_ms", 0.0)
    if cook_ms > 0:
        lines.append(f"")
        lines.append(f"Cook time: {cook_ms:.1f} ms")

    # Errors / warnings
    errors = ctx.get("errors", [])
    warnings = ctx.get("warnings", [])
    if errors:
        lines.append(f"")
        lines.append(f"ERRORS:")
        for e in errors:
            lines.append(f"  {e}")
    if warnings:
        lines.append(f"")
        lines.append(f"Warnings:")
        for w in warnings:
            lines.append(f"  {w}")

    return "\n".join(lines)


def _format_network_context(ctx: Dict[str, Any]) -> str:
    """Format network context as readable structured text for the user message."""
    lines: List[str] = []
    lines.append(f"Explain this network's data flow:")
    lines.append(f"")
    lines.append(f"Network: {ctx.get('network_path', 'unknown')}")
    lines.append(f"Type: {ctx.get('network_type', 'unknown')}")
    lines.append(f"Total nodes: {ctx.get('node_count', 0)}")

    display = ctx.get("display_node")
    if display:
        lines.append(f"Display node: {display}")

    total_cook = ctx.get("total_cook_time_ms", 0.0)
    if total_cook > 0:
        lines.append(f"Total cook time: {total_cook:.1f} ms")

    bottleneck = ctx.get("bottleneck")
    if bottleneck:
        lines.append(f"Bottleneck: {bottleneck}")

    flow = ctx.get("flow", [])
    if flow:
        lines.append(f"")
        lines.append(f"Data flow ({len(flow)} nodes):")
        lines.append(f"{'=' * 60}")
        for i, entry in enumerate(flow):
            lines.append(f"")
            lines.append(f"Step {i + 1}: {entry.get('label', '')} ({entry.get('node_type', '')})")
            lines.append(f"  Path: {entry.get('node_path', '')}")
            lines.append(f"  Geometry: {entry.get('geo_delta', 'unknown')}")

            key_parms = entry.get("key_parms", [])
            if key_parms:
                parm_strs = [f"{p['name']}={p['value']}" for p in key_parms]
                lines.append(f"  Key settings: {', '.join(parm_strs)}")

            cook_ms = entry.get("cook_time_ms", 0.0)
            if cook_ms > 0:
                lines.append(f"  Cook: {cook_ms:.1f} ms")

            errors = entry.get("errors", [])
            if errors:
                for e in errors:
                    lines.append(f"  ERROR: {e}")
    else:
        lines.append(f"")
        lines.append(f"No data flow traced (no display node or empty network).")

    return "\n".join(lines)
