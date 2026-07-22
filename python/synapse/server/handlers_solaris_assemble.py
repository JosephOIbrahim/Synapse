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
from .handler_helpers import (
    _HOUDINI_UNAVAILABLE, _layout_vertical_chain, VERTICAL_SPACING,
)


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
    # --- Scene content (B1): these were UNRANKED and therefore defaulted into
    # the render tier. `plane` and `shadowcatcher` are the exact pair the recon
    # predicted would land downstream of usdrender_rop and render nothing.
    # All verified present on 22.0.368 (h22_lop_catalog_live_22.0.368.json).
    "cube": 106, "sphere": 106, "cylinder": 106, "cone": 106,
    "capsule": 106, "basiscurves": 106,
    "backgroundplate": 107,         # Background plate card
    "plane": 108,                   # Ground plane (NOT `grid` -- absent on H22)
    "shadowcatcher": 109,           # Shadow catcher surface
    "sopmodify": 101,               # Round-trip stage geometry through SOPs
    "assetreference": 103,          # Reference a published asset
    # --- Layer composition ---
    # `payload` REMOVED: phantom on 22.0.368 -- verified absent from the live
    # catalog. It had rank 155 since H21 and could never have matched a node.
    "graftstages": 140,             # Graft branches onto the stage
    "merge": 145,                   # Combine branches (input index == strength)
    "sublayer": 150,                # USD sublayer composition
    "layerbreak": 158,              # Discard everything authored upstream
    "configurelayer": 160,
    "configurestage": 162,
    "configureprimitive": 165,
    "configureproperty": 166,
    # --- Materials ---
    "materiallibrary": 200,
    "editmaterial": 210,
    "assignmaterial": 220,
    "materialvariation": 230,
    # --- Collections, transforms & pruning ---
    "collection": 280,              # USD collection for light linking / grouping
    "duplicate": 270,
    "xform": 275,                   # Transform prims
    "prune": 290,                   # Prune prims from stage (deactivate)
    "cache": 295,                   # Stage cache point
    # --- Instancing ---
    "pointinstancer": 300,          # USD native point instancing (new H22 create+edit node)
    # W.3 (H22): `instancer` was renamed `copytopoints` (whats-new 22/solaris.txt
    # L143). Canonical spelling only — never the opalias. Dropped parms vs H21:
    # allowmissingprototypes / protooptionsgroup (successor: handlemissingprototypes);
    # nothing in SYNAPSE ever set them.
    "copytopoints": 310,            # Copy to Points (formerly `instancer`)
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
    # W.3 (H22): `layout` was renamed `paintinstances` (whats-new 22/solaris.txt
    # L137). Canonical spelling only — never the opalias. Sole dropped parm vs
    # H21: `method`; nothing in SYNAPSE ever set it.
    "paintinstances": 650,          # Paint Instances (formerly `layout`); Instanceable Reference mode
    "edit": 660,                    # Add Physics + Use Physics
    # --- Variants (Pattern 5) ---
    "explorevariants": 670,         # Preview variants interactively
    "setvariant": 675,              # Commit variant selection
    # --- Render (Pattern 1: Canonical LOP Chain) ---
    "karmarendersettings": 700,
    "karmarenderproperties": 700,   # DEPRECATED on 22.0.368 -- see B9
    "rendervar": 705,               # USD RenderVar (AOV) prim
    "rendergeometrysettings": 710,  # Per-prim render settings
    "rendersettings": 720,          # USD RenderSettings prim
    "usdrender_rop": 800,           # Final render output
    # --- Output ---
    "null": 900,
    "output": 900,                  # Named output node
}

# B1 -- the rank an unlisted type receives.
#
# This was 800, byte-identical to `usdrender_rop`. Because _merge_chain_order
# only inserts before an existing node whose key is STRICTLY greater, an
# unranked node tied with the ROP and was therefore appended AFTER it: wired
# downstream of the render output, reported as `wired`, laid out cleanly, and
# contributing nothing to the render. 184 of the build's 218 LOP types hit this
# path, including `plane` and `shadowcatcher`.
#
# 690 places an unknown type at the end of the scene-content region and
# strictly upstream of the whole render tier (karmarendersettings:700 onward),
# which is the safe direction to be wrong in: a node that should have been
# later still renders, whereas a node placed after the ROP never can.
# Unranked placements are also REPORTED (result["unranked"]), because a guess
# the artist cannot see is indistinguishable from a decision.
_UNRANKED_RANK = 690

# Types whose maxNumInputs is variadic on 22.0.368 (verified:
# h22_lop_catalog_live_22.0.368.json -- 8 of 218). For these the input INDEX
# carries USD opinion strength (higher index == stronger; SideFX lop/merge.txt),
# so overwriting input 0 silently changes which opinion wins. The wiring loop
# appends to the next free input on these instead of clobbering.
_UNBOUNDED_INPUT_TYPES = frozenset({
    "addvariant", "graftstages", "merge", "reference",
    "shotswitch", "sublayer", "switch",
})

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


def _base_type_name(node) -> str:
    """Version-stripped, lowercased type name.

    Houdini resolves a bare name to the NEWEST version at creation, so a node
    asked for as `domelight` reports `domelight::3.0`. Every lookup keyed on the
    requested spelling must strip the version or it silently misses.
    """
    return node.type().name().split("::")[0].lower()


def _get_sort_key(node) -> int:
    """Return canonical sort key for a LOP node type.

    Unlisted types receive _UNRANKED_RANK (upstream of the render tier), not the
    render ROP's own rank -- see the _UNRANKED_RANK note.
    """
    return _SOLARIS_NODE_ORDER.get(_base_type_name(node), _UNRANKED_RANK)


def _is_unranked(node) -> bool:
    """True if this node's placement was a fallback guess rather than a rule."""
    return _base_type_name(node) not in _SOLARIS_NODE_ORDER


def _takes_unbounded_inputs(node) -> bool:
    """True if input INDEX carries USD opinion strength on this node."""
    if _base_type_name(node) in _UNBOUNDED_INPUT_TYPES:
        return True
    try:                                    # live truth beats the static set
        return node.type().maxNumInputs() > 4
    except Exception:                       # noqa: BLE001
        return False


def _next_free_input(node) -> int:
    """Lowest unoccupied input index on ``node`` (variadic-safe)."""
    inputs = node.inputs()
    for i, connected in enumerate(inputs):
        if connected is None:
            return i
    return len(inputs)


def _is_unwired(node) -> bool:
    """True if node has no input connections AND no output connections."""
    return len(node.inputs()) == 0 and len(node.outputs()) == 0


def _is_chain_end(node) -> bool:
    """True if node has input(s) but no outputs -- i.e. the tail of a chain."""
    return len(node.inputs()) > 0 and len(node.outputs()) == 0


def _reconstruct_chain(tail) -> Tuple[List, List]:
    """Walk backwards from a chain tail, returning ``(spine, branch_roots)``.

    ``spine`` is the input-0 walk in root → ... → tail order -- the linear
    backbone the canonical ordering is expressed against.

    ``branch_roots`` (B3) is every node feeding a spine node through an input
    OTHER than 0. Following input 0 alone silently flattened a merge DAG into a
    line, so a three-asset merge looked like a one-asset chain and the other two
    branches became invisible: eligible to be "re-wired" over, and absent from
    every report. Merge input index IS USD opinion strength, so losing a branch
    is not cosmetic -- it changes which opinion wins.

    The spine stays the ordering axis (linear ordering of a DAG is not
    meaningful), but callers can now see what the spine does not cover and must
    not disturb.
    """
    spine: List = []
    branch_roots: List = []
    seen = set()
    cursor = tail
    while cursor is not None and id(cursor) not in seen:
        spine.append(cursor)
        seen.add(id(cursor))
        inputs = cursor.inputs()
        for extra in inputs[1:]:
            if extra is not None and id(extra) not in seen:
                branch_roots.append(extra)
        cursor = inputs[0] if inputs else None
    spine.reverse()
    return spine, branch_roots


def _upstream_closure(node, limit: int = 512) -> set:
    """ids of every node reachable upstream through ANY input.

    Guards the wiring loop against treating a node that already feeds the chain
    through a non-zero input as a free target (M15/B3).
    """
    out: set = set()
    stack = [node]
    while stack and len(out) < limit:
        cur = stack.pop()
        for upstream in cur.inputs():
            if upstream is not None and id(upstream) not in out:
                out.add(id(upstream))
                stack.append(upstream)
    return out


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

            wired: List[Dict] = []
            skipped: List[Dict[str, str]] = []
            overwritten: List[Dict] = []      # B3 -- links this call replaced
            branch_paths: List[str] = []      # B3 -- non-input-0 feeders seen

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
                    elif not _is_unwired(n):
                        # M15: mode 'all' has always screened with _is_unwired;
                        # 'nodes'/'after' did not, so naming an already-wired
                        # node yanked it out of its chain, left its former
                        # upstream dangling, and reported the theft under
                        # `wired` as a clean addition. This tool wires unwired
                        # nodes -- rewiring a live node is a different, explicit
                        # operation.
                        skipped.append({
                            "node": np,
                            "reason": ("already wired (%d in, %d out) -- "
                                       "assemble_chain only wires unwired "
                                       "nodes; disconnect it first to move it"
                                       % (len([i for i in n.inputs() if i]),
                                          len(n.outputs()))),
                        })
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
                    elif not _is_unwired(n):
                        # M15: mode 'all' has always screened with _is_unwired;
                        # 'nodes'/'after' did not, so naming an already-wired
                        # node yanked it out of its chain, left its former
                        # upstream dangling, and reported the theft under
                        # `wired` as a clean addition. This tool wires unwired
                        # nodes -- rewiring a live node is a different, explicit
                        # operation.
                        skipped.append({
                            "node": np,
                            "reason": ("already wired (%d in, %d out) -- "
                                       "assemble_chain only wires unwired "
                                       "nodes; disconnect it first to move it"
                                       % (len([i for i in n.inputs() if i]),
                                          len(n.outputs()))),
                        })
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
                existing_chain, branch_roots = _reconstruct_chain(anchor)
                # B3: branches feeding the spine through a non-zero input are
                # part of the network but not part of the ordering axis. Record
                # them so a merge with three assets stops looking like a
                # one-asset chain in the response.
                branch_paths = [b.path() for b in branch_roots]
                protected = _upstream_closure(anchor)
                reclaimed = [t for t in targets if id(t) in protected]
                if reclaimed:
                    for t in reclaimed:
                        skipped.append({
                            "node": t.path(),
                            "reason": ("already feeds this chain through a "
                                       "non-zero input -- rewiring it would "
                                       "change USD opinion strength"),
                        })
                    targets = [t for t in targets if id(t) not in protected]
                    target_ids = {id(t) for t in targets}
                ordered = _merge_chain_order(
                    existing_chain, targets, _get_sort_key
                )
            else:
                ordered = ([anchor] if anchor is not None else []) + list(targets)

            # -----------------------------------------------------------
            # Wire the chain
            # -----------------------------------------------------------
            chain_paths: List[str] = []

            def _wire_and_layout() -> None:
                prev = None
                for node in ordered:
                    if prev is not None:
                        current_inputs = node.inputs()
                        if current_inputs and current_inputs[0] == prev:
                            # Already wired correctly. Only report it as a
                            # skipped target — pre-existing internal chain
                            # links stay quiet.
                            if id(node) in target_ids:
                                skipped.append({
                                    "node": node.path(),
                                    "reason": "already wired to predecessor",
                                })
                            chain_paths.append(node.path())
                            prev = node
                            continue

                        # B3: decide the input index BEFORE mutating, and never
                        # clobber an existing connection silently.
                        #
                        # On a variadic node (merge/sublayer/switch/...) the
                        # input index IS the USD opinion strength, so
                        # overwriting input 0 rewrites which layer wins while
                        # reporting nothing but a tidy new connection. Append to
                        # the next free input there instead. Anywhere else an
                        # occupied input 0 is still someone's deliberate wiring,
                        # so the displaced link is recorded rather than lost.
                        target_index = 0
                        displaced = (
                            current_inputs[0]
                            if current_inputs and current_inputs[0] is not None
                            else None
                        )
                        if displaced is not None and _takes_unbounded_inputs(node):
                            target_index = _next_free_input(node)
                            displaced = None      # nothing is being replaced

                        if not dry_run:
                            node.setInput(target_index, prev)

                        link = {
                            "from": prev.path(),
                            "to": node.path(),
                            "input": target_index,
                        }
                        if displaced is not None:
                            link["replaced"] = displaced.path()
                            overwritten.append({
                                "node": node.path(),
                                "input": target_index,
                                "was": displaced.path(),
                                "now": prev.path(),
                                "reason": (
                                    "input 0 was already connected; this node "
                                    "type's input index does not carry USD "
                                    "opinion strength, so it was replaced"),
                            })
                        wired.append(link)

                    chain_paths.append(node.path())
                    prev = node

                # Layout: one clean vertical column, top to bottom.
                #
                # M18: start_y must be chosen so the ANCHOR keeps the position
                # it already has. Passing the anchor's own y put the chain ROOT
                # there instead, sliding the artist's entire existing chain down
                # by (anchor index x spacing) every time this ran.
                if dry_run or not wired:
                    return
                chain_hou_nodes = []
                for path in chain_paths:
                    n = hou.node(path)
                    if n is not None:
                        chain_hou_nodes.append(n)
                if not chain_hou_nodes:
                    return
                start_x, start_y = 0.0, 0.0
                if anchor is not None:
                    anchor_pos = anchor.position()
                    anchor_index = 0
                    for i, n in enumerate(chain_hou_nodes):
                        if n == anchor:
                            anchor_index = i
                            break
                    start_x = anchor_pos[0]
                    start_y = anchor_pos[1] + anchor_index * VERTICAL_SPACING
                _layout_vertical_chain(chain_hou_nodes, start_x, start_y)

            # B2: assemble_chain rewires nodes the artist already owns, and did
            # it with NO undo group at all (grep -c undos -> 0). A failure
            # part-way through the loop left a half-rewired network with no
            # single Ctrl+Z and no record of which links had changed — strictly
            # worse than build_graph, which at least only creates.
            #
            # M14: performUndo() must not fire unless there is evidence a group
            # actually opened, or it pops the artist's OWN last action. Both
            # hou.undos.areEnabled and hou.undos.undoLabels verified present on
            # 22.0.368 by live probe (the symbol table omits the hou.undos
            # submodule entirely, so its silence is not evidence of absence).
            if dry_run:
                _wire_and_layout()
            else:
                undo_enabled = False
                labels_before: Tuple = ()
                try:
                    undo_enabled = bool(hou.undos.areEnabled())
                    labels_before = tuple(hou.undos.undoLabels())
                except Exception:  # noqa: BLE001 — evidence is best-effort
                    undo_enabled = False
                try:
                    with hou.undos.group("SYNAPSE: assemble_chain"):
                        _wire_and_layout()
                except Exception:
                    # The C++ undo layer for LOP nodes carrying USD stage data
                    # can itself throw on __exit__, so roll back explicitly —
                    # but only with evidence that something was recorded.
                    if undo_enabled:
                        try:
                            if tuple(hou.undos.undoLabels()) != labels_before:
                                hou.undos.performUndo()
                        except Exception as undo_exc:  # noqa: BLE001
                            import logging
                            logging.getLogger(__name__).warning(
                                "assemble_chain: undo rollback failed: %s",
                                undo_exc)
                    raise

            result = {
                "wired": wired,
                "skipped": skipped,
                "chain": chain_paths,
                "dry_run": dry_run,
            }

            # B1: surface every node whose position was a fallback guess rather
            # than a canonical rule, so "SYNAPSE placed this" is distinguishable
            # from "SYNAPSE knows where this goes".
            unranked = sorted({
                _base_type_name(n) for n in ordered if _is_unranked(n)
            })
            if unranked:
                result["unranked"] = unranked
                result["unranked_note"] = (
                    "no canonical rank for these types; placed upstream of the "
                    "render tier (rank %d) as a safe default -- verify their "
                    "position" % _UNRANKED_RANK
                )
            # B3: what this call replaced, and what it deliberately left alone.
            if overwritten:
                result["overwritten"] = overwritten
            if branch_paths:
                result["branches"] = branch_paths
                result["branches_note"] = (
                    "these feed the chain through a non-zero input; they are "
                    "part of the network but not of the linear ordering axis"
                )

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
