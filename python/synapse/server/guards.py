"""
guards.py — Synapse Idempotent Operation Guards

Check-before-mutate helpers auto-injected into execute_python namespace.
Every function is safe to re-run — if desired state exists, it no-ops.

Usage (from any Synapse-executed script — no import needed):
    node = ensure_node('/stage', 'distantlight', 'rim_light')
    ensure_connection('/stage/rim_light', '/stage/scene_merge')
    ensure_parm('/stage/rim_light', 'xn__inputsintensity_i0a', 5.0)
"""

import hou
from typing import Optional, Union


# ─── Node Operations ─────────────────────────────────────────

def ensure_node(parent_path: str, node_type: str, node_name: str) -> "hou.Node":
    """Create node only if it doesn't already exist. Returns the node."""
    full_path = f"{parent_path}/{node_name}"
    existing = hou.node(full_path)
    if existing is not None:
        return existing
    parent = hou.node(parent_path)
    if parent is None:
        raise ValueError(
            f"Couldn't find the parent node at {parent_path} \u2014 "
            "verify this path exists in your scene"
        )
    return parent.createNode(node_type, node_name)


def ensure_node_deleted(node_path: str) -> bool:
    """Delete node only if it exists. Returns True if deleted or already gone."""
    node = hou.node(node_path)
    if node is None:
        return True
    node.destroy()
    return True


def node_exists(path: str) -> bool:
    """Check if a node exists at the given path."""
    return hou.node(path) is not None


# ─── Connection Operations ────────────────────────────────────

def ensure_connection(
    source_path: str,
    target_path: str,
    source_output: int = 0,
    target_input: Optional[int] = None,
) -> bool:
    """
    Connect source->target only if not already connected.

    If target_input is None, appends to next available input.
    Returns True if connection exists (new or pre-existing).
    """
    source = hou.node(source_path)
    target = hou.node(target_path)
    if not source or not target:
        missing = source_path if not source else target_path
        raise ValueError(
            f"Couldn't find a node at {missing} \u2014 "
            "make sure both source and target exist before connecting"
        )

    for inp in target.inputs():
        if inp and inp.path() == source.path():
            return True

    if target_input is not None:
        target.setInput(target_input, source, source_output)
    else:
        target.setInput(len(target.inputs()), source, source_output)
    return True


def ensure_disconnected(target_path: str, source_path: str) -> bool:
    """Disconnect source from target. Safe if already disconnected."""
    target = hou.node(target_path)
    if not target:
        return True
    inputs = target.inputs()
    for idx in range(len(inputs) - 1, -1, -1):
        inp = inputs[idx]
        if inp and inp.path() == source_path:
            target.setInput(idx, None)
    return True


def deduplicate_inputs(merge_path: str) -> dict:
    """Remove duplicate connections on a merge node."""
    merge = hou.node(merge_path)
    if not merge:
        raise ValueError(
            f"Couldn't find a node at {merge_path} \u2014 "
            "double-check the merge node path"
        )
    seen = set()
    to_disconnect = []
    for idx, inp in enumerate(merge.inputs()):
        if inp is None:
            continue
        if inp.path() in seen:
            to_disconnect.append(idx)
        else:
            seen.add(inp.path())
    for idx in reversed(to_disconnect):
        merge.setInput(idx, None)
    return {"removed": len(to_disconnect), "remaining": list(seen)}


# ─── Parameter Operations ────────────────────────────────────

def ensure_parm(
    node_path: str,
    parm_name: str,
    value: Union[float, int, str],
) -> bool:
    """Set parameter only if current value differs."""
    node = hou.node(node_path)
    if not node:
        raise ValueError(
            f"Couldn't find a node at {node_path} \u2014 "
            "double-check the path exists"
        )
    parm = node.parm(parm_name)
    if not parm:
        raise ValueError(
            f"Couldn't find parameter '{parm_name}' on {node_path} \u2014 "
            "check the parameter name spelling"
        )
    current = parm.eval()  # noqa: S307 — hou.Parm.eval(), not Python eval()
    if isinstance(value, float) and abs(current - value) < 1e-7:
        return True
    if current == value:
        return True
    parm.set(value)
    return True


def ensure_parm_tuple(
    node_path: str,
    parm_names: list,
    values: list,
) -> bool:
    """Set multiple related parameters. Only writes if any differ."""
    node = hou.node(node_path)
    if not node:
        raise ValueError(
            f"Couldn't find a node at {node_path} \u2014 "
            "double-check the path exists"
        )
    needs_update = False
    for parm_name, value in zip(parm_names, values):
        parm = node.parm(parm_name)
        if not parm:
            continue
        current = parm.eval()  # noqa: S307 — hou.Parm.eval()
        if isinstance(value, float) and abs(current - value) > 1e-7:
            needs_update = True
            break
        elif current != value:
            needs_update = True
            break
    if not needs_update:
        return True
    for parm_name, value in zip(parm_names, values):
        parm = node.parm(parm_name)
        if parm:
            parm.set(value)
    return True


# ─── Inspection ───────────────────────────────────────────────

def describe_inputs(node_path: str) -> list:
    """Return list of input connection paths for a node."""
    node = hou.node(node_path)
    if not node:
        return []
    return [inp.path() if inp else None for inp in node.inputs()]


def describe_node(node_path: str) -> dict:
    """Return basic info about a node."""
    node = hou.node(node_path)
    if not node:
        return {"exists": False}
    return {
        "exists": True,
        "path": node.path(),
        "type": node.type().name(),
        "inputs": len([i for i in node.inputs() if i]),
        "outputs": len(node.outputs()),
    }


# All guard functions for namespace injection
GUARD_FUNCTIONS = {
    "ensure_node": ensure_node,
    "ensure_node_deleted": ensure_node_deleted,
    "node_exists": node_exists,
    "ensure_connection": ensure_connection,
    "ensure_disconnected": ensure_disconnected,
    "deduplicate_inputs": deduplicate_inputs,
    "ensure_parm": ensure_parm,
    "ensure_parm_tuple": ensure_parm_tuple,
    "describe_inputs": describe_inputs,
    "describe_node": describe_node,
}
