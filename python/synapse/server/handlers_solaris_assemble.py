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
from .handler_helpers import _HOUDINI_UNAVAILABLE, _layout_vertical_chain


# Canonical Solaris chain ordering.  Lower number = earlier in chain.
_SOLARIS_NODE_ORDER: Dict[str, int] = {
    # --- Stage defaults ---
    "stagemanager": 5,              # HIP-level stage defaults (kitchen-sink config)
    # --- Scene hierarchy (Pattern 4: Hierarchy Discipline) ---
    "primitive": 10,                # Xform hierarchy root (Kind=Group)
    # --- Geometry import & references (Pattern 1: chain sequentially) ---
    # FIX 4: a 'reference' usually BRINGS GEOMETRY, so it sorts in the
    # geometry tier (BEFORE materiallibrary/assignmaterial) — referenced
    # content must exist on the stage before any material library or
    # assignment sequences against the prims it targets. (Was 250, which
    # placed it AFTER assignmaterial:220 → material assign ran upstream of
    # the prims it targeted.)
    "sopcreate": 100,
    "sopimport": 100,
    "reference": 102,               # USD reference (usually brings geometry)
    "sceneimport": 105,             # Import full scene from external file
    # --- Component Builder internals (Pattern 2) ---
    "componentgeometry": 110,       # SOPs inside: geo → default/proxy/simproxy
    "componentgeometryvariants": 115,  # Pattern 5: merge geometry variants
    "componentmaterial": 120,       # Auto-assigns materials to geometry
    "componentoutput": 130,         # Export: name, path, thumbnail
    # --- Layer composition ---
    "sublayer": 150,                # USD sublayer composition
    "payload": 155,                 # Deferred USD payload loading
    # --- Materials ---
    "materiallibrary": 200,
    "assignmaterial": 220,
    # --- Collections & pruning ---
    "collection": 280,              # USD collection for light linking / grouping
    "prune": 290,                   # Prune prims from stage (deactivate)
    # --- Instancing ---
    "pointinstancer": 300,          # USD native point instancing
    "instancer": 310,               # Legacy instancer
    # --- Cameras ---
    "camera": 400,
    # --- Lighting ---
    # FIX 1: per-shape light LOPs (rectlight/spherelight/disklight/
    # cylinderlight) are PHANTOM on H21.0.671 — they fold into the generic
    # 'light' node, with the shape chosen via a parm. Only domelight and
    # distantlight remain distinct LOP types. Referencing the phantom types
    # made createNode fail at assemble time.
    "light": 500,                   # Generic area/point/spot light (shape via parm)
    "distantlight": 500,            # Sun / directional light
    "domelight": 600,               # Environment / HDRI dome
    "karmaphysicalsky": 610,        # Pattern 1: physical sky lighting
    "lightmixer": 620,              # Aggregate / edit multiple lights
    # --- Layout + Physics (Pattern 8) ---
    "layout": 650,                  # Instanceable Reference mode for physics
    "edit": 660,                    # Add Physics + Use Physics
    # --- Variants (Pattern 5) ---
    "explorevariants": 670,         # Preview variants interactively
    "setvariant": 675,              # Commit variant selection
    # --- Render (Pattern 1: Canonical LOP Chain) ---
    "karmarendersettings": 700,
    "karmarenderproperties": 700,
    "rendergeometrysettings": 710,  # Per-prim render settings
    "rendersettings": 720,          # USD RenderSettings prim
    "usdrender_rop": 800,           # Final render output
    # --- Output ---
    "null": 900,
    "output": 900,                  # Named output node
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


def _reconstruct_chain(tail) -> List:
    """Walk backwards from a chain tail along input 0, returning the existing
    linear chain in root → ... → tail order.

    Used by FIX 3: to insert new targets at their CANONICAL position we need
    the full existing chain, not just its tail anchor.
    """
    chain: List = []
    seen = set()
    cursor = tail
    while cursor is not None and id(cursor) not in seen:
        chain.append(cursor)
        seen.add(id(cursor))
        inps = cursor.inputs()
        cursor = inps[0] if inps else None
    chain.reverse()
    return chain


def _merge_chain_order(existing_chain: List, targets: List, sort_key) -> List:
    """Insert each new target into the existing chain at its canonical slot,
    WITHOUT reordering existing-vs-existing nodes.

    FIX 3 (v2 -- never silently reorder an intentional spine): the existing
    chain order is preserved EXACTLY; only the new targets move. Each target
    is placed before the first EXISTING node whose sort key is strictly
    greater (so a low-order light:500 lands upstream of a high-order
    usdrender_rop:800 tail), else appended. Targets keep canonical order among
    themselves. A deliberately non-canonical existing chain (e.g.
    materiallibrary -> sublayer authored for USD strength) is never reordered.
    For a fully-canonical chain with targets at/after the tail the result is
    identical to the old append.
    """
    result = list(existing_chain)
    existing_ids = {id(n) for n in existing_chain}
    for target in sorted(targets, key=sort_key):
        tk = sort_key(target)
        insert_at = len(result)
        for i, node in enumerate(result):
            if id(node) in existing_ids and sort_key(node) > tk:
                insert_at = i
                break
        result.insert(insert_at, target)
    return result


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
        aov_passes = payload.get("aov_passes", None)

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
            # Build the final ordered chain.
            #
            # FIX 3: in mode 'all' we must NOT blindly append targets after
            # the chain tail. The tail anchor may be a high-order node
            # (usdrender_rop:800); a low-order target (light:500) belongs
            # UPSTREAM of it. Reconstruct the existing chain and merge the
            # targets in by canonical sort key so each lands at its correct
            # position. For 'after'/'nodes' the caller gave an explicit anchor
            # (or none), so we honour the simple append — no silent reorder.
            # -----------------------------------------------------------
            target_ids = {id(t) for t in targets}

            if mode == "all" and anchor is not None:
                existing_chain = _reconstruct_chain(anchor)
                ordered = _merge_chain_order(
                    existing_chain, targets, _get_sort_key
                )
            else:
                ordered = ([anchor] if anchor is not None else []) + list(targets)

            # -----------------------------------------------------------
            # Wire the chain
            # -----------------------------------------------------------
            prev = None
            chain_paths: List[str] = []

            for node in ordered:
                if prev is not None:
                    current_inputs = node.inputs()
                    if current_inputs and current_inputs[0] == prev:
                        # Already wired correctly. Only report it as a skipped
                        # target — pre-existing internal chain links stay quiet.
                        if id(node) in target_ids:
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

            # Layout: position all chain nodes in a clean vertical column.
            # Professional VFX artists wire Solaris networks top-to-bottom
            # in a single column — this replaces layoutChildren() which
            # produces unpredictable arrangements.
            if not dry_run and wired:
                # Collect ordered chain nodes for positioning
                chain_hou_nodes = []
                for path in chain_paths:
                    n = hou.node(path)
                    if n is not None:
                        chain_hou_nodes.append(n)
                # Anchor position: if we have an anchor node, start from
                # its position. Otherwise start at origin.
                if anchor is not None:
                    anchor_pos = anchor.position()
                    start_x = anchor_pos[0]
                    start_y = anchor_pos[1]
                else:
                    start_x = 0.0
                    start_y = 0.0
                _layout_vertical_chain(chain_hou_nodes, start_x, start_y)

            result = {
                "wired": wired,
                "skipped": skipped,
                "chain": chain_paths,
                "dry_run": dry_run,
            }

            # Auto-configure render passes if requested
            if aov_passes and not dry_run:
                configure_handler = getattr(
                    self, "_handle_configure_render_passes", None
                )
                if configure_handler is not None:
                    # Find the render settings node in the chain to wire after
                    render_node = None
                    for path in reversed(chain_paths):
                        n = hou.node(path)
                        if n and n.type().name() in (
                            "karmarendersettings", "karmarenderproperties",
                        ):
                            render_node = n
                            break
                    try:
                        aov_payload = {"passes": aov_passes}
                        if render_node:
                            aov_payload["node"] = render_node.path()
                        aov_result = configure_handler(aov_payload)
                        result["aov_passes"] = aov_result
                    except Exception as exc:
                        result["aov_warning"] = (
                            f"AOV setup skipped: {exc}"
                        )

            return result

        # Karma AOV / render-ready assembly routinely exceeds the 10s default;
        # match build_graph's 30s so a timeout doesn't ghost-callback into the
        # duplicate-node spiral (parity with handlers_solaris_graph).
        return run_on_main(_on_main, timeout=30.0)
