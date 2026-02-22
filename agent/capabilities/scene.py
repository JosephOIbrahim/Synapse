"""
Agent capabilities -- scene inspection wrappers.

Provides async functions for scene inspection using SynapseClient.
These are read-only operations that never modify the Houdini scene.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add the agent/ directory to sys.path so we can import synapse_ws
_AGENT_DIR = str(Path(__file__).resolve().parents[1])
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

from synapse_ws import SynapseClient


async def get_scene_summary(client: SynapseClient) -> Dict[str, Any]:
    """Get a combined scene summary: metadata + node hierarchy.

    Runs scene_info() and inspect_scene() concurrently and merges the
    results into a single dict.

    Args:
        client: Connected SynapseClient instance.

    Returns:
        Dict with keys from both scene_info (hip path, frame range, FPS)
        and inspect_scene (node tree), plus a top-level ``summary`` key
        with quick-reference counts.
    """
    info_result, tree_result = await asyncio.gather(
        client.scene_info(),
        client.inspect_scene(root="/", max_depth=3),
    )

    # Build a quick-reference summary
    node_count = tree_result.get("node_count", 0)
    summary = {
        "hip_file": info_result.get("hip_file", ""),
        "frame_range": (
            info_result.get("frame_start", 1),
            info_result.get("frame_end", 240),
        ),
        "fps": info_result.get("fps", 24),
        "node_count": node_count,
    }

    return {
        "scene_info": info_result,
        "scene_tree": tree_result,
        "summary": summary,
    }


async def find_nodes_by_type(
    client: SynapseClient,
    node_type: str,
    root: str = "/",
) -> List[Dict[str, Any]]:
    """Find all nodes matching a given type in the scene hierarchy.

    Inspects the scene tree from root down to depth 10 and filters for
    nodes whose type matches the query (case-insensitive substring match).

    Args:
        client: Connected SynapseClient instance.
        node_type: Node type to search for, e.g. "karma", "merge",
            "distantlight". Matches as a case-insensitive substring.
        root: Root path to start searching from.

    Returns:
        List of dicts, each with ``path``, ``type``, and ``name`` keys
        for matching nodes.
    """
    tree = await client.inspect_scene(root=root, max_depth=10)
    matches: List[Dict[str, Any]] = []
    needle = node_type.lower()

    def _walk(nodes: Any) -> None:
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, dict):
                    ntype = str(node.get("type", "")).lower()
                    if needle in ntype:
                        matches.append({
                            "path": node.get("path", ""),
                            "type": node.get("type", ""),
                            "name": node.get("name", ""),
                        })
                    # Recurse into children
                    children = node.get("children", [])
                    if children:
                        _walk(children)
        elif isinstance(nodes, dict):
            # Top-level might be a dict with a "nodes" or "children" key
            for key in ("nodes", "children", "tree"):
                if key in nodes:
                    _walk(nodes[key])

    _walk(tree)
    return matches


async def validate_connections(
    client: SynapseClient,
    node_path: str,
) -> Dict[str, Any]:
    """Check a node's input/output connections.

    Inspects the node and extracts its connection state -- useful for
    verifying that a newly created node is wired correctly.

    Args:
        client: Connected SynapseClient instance.
        node_path: Full Houdini path to the node, e.g. "/stage/merge1".

    Returns:
        Dict with ``connected`` (bool -- True if any connections exist),
        ``inputs`` (list of connected input paths), and ``outputs``
        (list of connected output paths).
    """
    node_info = await client.inspect_node(node_path)

    inputs: List[str] = []
    outputs: List[str] = []

    # Extract input connections
    raw_inputs = node_info.get("inputs", [])
    if isinstance(raw_inputs, list):
        for inp in raw_inputs:
            if isinstance(inp, dict):
                src = inp.get("source", "") or inp.get("path", "")
                if src:
                    inputs.append(src)
            elif isinstance(inp, str) and inp:
                inputs.append(inp)

    # Extract output connections
    raw_outputs = node_info.get("outputs", [])
    if isinstance(raw_outputs, list):
        for out in raw_outputs:
            if isinstance(out, dict):
                dst = out.get("target", "") or out.get("path", "")
                if dst:
                    outputs.append(dst)
            elif isinstance(out, str) and out:
                outputs.append(out)

    return {
        "connected": len(inputs) > 0 or len(outputs) > 0,
        "inputs": inputs,
        "outputs": outputs,
    }
