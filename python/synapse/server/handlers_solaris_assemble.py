"""
Synapse Solaris Assemble Handler Mixin

Auto-wires unwired LOP nodes in /stage into the canonical Solaris chain.
Three modes: "all" (scan for unwired), "nodes" (specific paths), "after" (append).
"""

from typing import Dict, List, Optional, Tuple

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.errors import NodeNotFoundError, HoudiniUnavailableError
from .handler_helpers import _HOUDINI_UNAVAILABLE


# Canonical Solaris chain ordering.  Lower number = earlier in chain.
_SOLARIS_NODE_ORDER: Dict[str, int] = {
    # --- Scene hierarchy (Pattern 4: Hierarchy Discipline) ---
    "primitive": 10,                # Xform hierarchy root (Kind=Group)
    # --- Geometry import (Pattern 1: chain sequentially, NEVER merge) ---
    "sopcreate": 100,
    "sopimport": 100,
    # --- Component Builder internals (Pattern 2) ---
    "componentgeometry": 110,       # SOPs inside: geo → default/proxy/simproxy
    "componentmaterial": 120,       # Auto-assigns materials to geometry
    "componentoutput": 130,         # Export: name, path, thumbnail
    "componentgeometryvariants": 115,  # Pattern 5: merge geometry variants
    # --- Materials ---
    "materiallibrary": 200,
    "assignmaterial": 220,
    # --- References (Pattern 6: Megascans material import trick) ---
    "reference": 250,               # /materials/* wildcard for material import
    # --- Cameras ---
    "camera": 400,
    # --- Lighting ---
    "rectlight": 500,
    "distantlight": 500,
    "domelight": 600,
    "karmaphysicalsky": 610,        # Pattern 1: physical sky lighting
    # --- Layout + Physics (Pattern 8) ---
    "layout": 650,                  # Instanceable Reference mode for physics
    "edit": 660,                    # Add Physics + Use Physics
    # --- Variants (Pattern 5) ---
    "explorevariants": 670,         # Preview variants interactively
    "setvariant": 675,              # Commit variant selection
    # --- Render (Pattern 1: Canonical LOP Chain) ---
    "karmarendersettings": 700,
    "karmarenderproperties": 700,
    "usdrender_rop": 800,           # Final render output
    "null": 900,
}

# Named chain templates for multi-node tool creation (RELAY-SOLARIS Phase 2)
_SOLARIS_CHAIN_TEMPLATES: Dict[str, List[str]] = {
    # Pattern 1: Full scene skeleton
    "scene_template": [
        "primitive",
        "sopimport",
        "camera",
        "materiallibrary",
        "karmaphysicalsky",
        "karmarendersettings",
        "usdrender_rop",
    ],
    # Pattern 2: Component Builder internals
    "component_builder": [
        "componentgeometry",
        "componentmaterial",
        "componentoutput",
    ],
    # Pattern 6: Megascans SOP pipeline (inside Component Geometry)
    "megascans_sop_import": [
        "usdimport",
        "xform",
        "matchsize",
        "polyreduce",
        "output",
    ],
}


def _get_sort_key(node) -> int:
    """Return canonical sort key for a LOP node type."""
    type_name = node.type().name().split("::")[0].lower()
    return _SOLARIS_NODE_ORDER.get(type_name, 800)


def _is_unwired(node) -> bool:
    """True if node has no input connections AND no output connections."""
    return len(node.inputs()) == 0 and len(node.outputs()) == 0


def _is_chain_end(node) -> bool:
    """True if node has input(s) but no outputs -- i.e. the tail of a chain."""
    return len(node.inputs()) > 0 and len(node.outputs()) == 0


class SolarisAssembleMixin:
    """Mixin providing the solaris_assemble_chain handler."""

    def _handle_solaris_assemble_chain(self, payload: Dict) -> Dict:
        """Wire unwired LOP nodes into the canonical Solaris chain.

        Modes:
            "all"   - Scan /stage (or parent) for unwired nodes, sort by
                      canonical order, wire them into a linear chain. If an
                      existing chain tail is found, append after it.
            "nodes" - Wire the specific node paths given in `nodes` list,
                      in the order provided (or sorted if `sort` is true).
            "after" - Append `nodes` after a specific `after` node path.

        Args:
            payload: Dict with keys:
                - mode: "all" | "nodes" | "after" (default: "all")
                - parent: LOP network path (default: "/stage")
                - nodes: list of node paths (required for "nodes" and "after")
                - after: node path to append after (required for "after" mode)
                - sort: bool, sort nodes by canonical order (default: true)
                - dry_run: bool, report what would happen without wiring
                           (default: false)

        Returns:
            {
                "wired": [{"from": path, "to": path}, ...],
                "skipped": [{"node": path, "reason": str}, ...],
                "chain": [path, ...],  # final linear order
                "dry_run": bool
            }
        """
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        mode = resolve_param_with_default(payload, "mode", "all")
        parent_path = resolve_param_with_default(payload, "parent", "/stage")
        node_paths = payload.get("nodes", [])
        after_path = payload.get("after", None)
        sort_nodes = payload.get("sort", True)
        dry_run = payload.get("dry_run", False)

        from .main_thread import run_on_main

        def _on_main():
            parent_node = hou.node(parent_path)
            if parent_node is None:
                raise NodeNotFoundError(
                    parent_path,
                    suggestion="Check that /stage exists in this scene",
                )

            wired: List[Dict[str, str]] = []
            skipped: List[Dict[str, str]] = []

            # -----------------------------------------------------------
            # Collect target nodes depending on mode
            # -----------------------------------------------------------
            targets: List = []

            if mode == "all":
                # Gather all unwired children
                for child in parent_node.children():
                    if _is_unwired(child):
                        targets.append(child)
                if sort_nodes:
                    targets.sort(key=_get_sort_key)

            elif mode == "nodes":
                if not node_paths:
                    raise ValueError(
                        "Mode 'nodes' requires a 'nodes' list -- "
                        "pass the node paths you want wired"
                    )
                for np in node_paths:
                    n = hou.node(np)
                    if n is None:
                        skipped.append({"node": np, "reason": "not found"})
                    else:
                        targets.append(n)
                if sort_nodes:
                    targets.sort(key=_get_sort_key)

            elif mode == "after":
                if not after_path:
                    raise ValueError(
                        "Mode 'after' requires an 'after' node path -- "
                        "pass the node to append after"
                    )
                if not node_paths:
                    raise ValueError(
                        "Mode 'after' requires a 'nodes' list -- "
                        "pass the node paths to append"
                    )
                for np in node_paths:
                    n = hou.node(np)
                    if n is None:
                        skipped.append({"node": np, "reason": "not found"})
                    else:
                        targets.append(n)
                if sort_nodes:
                    targets.sort(key=_get_sort_key)

            else:
                raise ValueError(
                    f"Unknown mode '{mode}' -- use 'all', 'nodes', or 'after'"
                )

            if not targets:
                return {
                    "wired": wired,
                    "skipped": skipped,
                    "chain": [],
                    "dry_run": dry_run,
                }

            # -----------------------------------------------------------
            # Find the anchor (tail of existing chain) to start from
            # -----------------------------------------------------------
            anchor: Optional = None

            if mode == "after":
                anchor = hou.node(after_path)
                if anchor is None:
                    raise NodeNotFoundError(
                        after_path,
                        suggestion="Check the 'after' node path exists",
                    )
            elif mode == "all":
                # Find existing chain tail in the parent network
                for child in parent_node.children():
                    if child not in targets and _is_chain_end(child):
                        # Prefer the node with the highest sort key
                        # (closest to OUTPUT end of chain)
                        if anchor is None or _get_sort_key(child) > _get_sort_key(anchor):
                            anchor = child

            # -----------------------------------------------------------
            # Wire the chain
            # -----------------------------------------------------------
            prev = anchor
            chain_paths: List[str] = []

            if prev is not None:
                chain_paths.append(prev.path())

            for node in targets:
                if prev is not None:
                    # Skip if already wired to this input
                    current_inputs = node.inputs()
                    if current_inputs and current_inputs[0] == prev:
                        skipped.append({
                            "node": node.path(),
                            "reason": "already wired to predecessor",
                        })
                        chain_paths.append(node.path())
                        prev = node
                        continue

                    if not dry_run:
                        node.setInput(0, prev)
                    wired.append({
                        "from": prev.path(),
                        "to": node.path(),
                    })

                chain_paths.append(node.path())
                prev = node

            # Layout for readability
            if not dry_run and wired:
                parent_node.layoutChildren()

            return {
                "wired": wired,
                "skipped": skipped,
                "chain": chain_paths,
                "dry_run": dry_run,
            }

        return run_on_main(_on_main)
