"""
Synapse Solaris Graph Builder Handler Mixin

Builds arbitrary DAG topologies in Solaris LOP networks — merge nodes,
sublayer stacks, parallel streams. Complements assemble_chain (linear only).
"""

import contextlib
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Tuple
import logging
import re

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.errors import NodeNotFoundError, HoudiniUnavailableError, SynapseUserError
from .solaris_graph_templates import expand_template, TEMPLATES
from .handler_helpers import (
    _compute_dag_positions, _free_origin,
    _apply_section_boxes,
)
from .solaris_graph_plan import resolve_plan, observed_inputs, observed_display
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
    catalog = None
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
        if not remediation:
            # TYPEHINT (10/1): name the closest real types, so one failed
            # guess becomes one correct retry instead of a run of guesses.
            try:
                from ..core.type_suggest import live_catalog, suggest
                if catalog is None:
                    catalog = live_catalog(category)
                near = suggest(type_name, catalog)
                if near:
                    remediation = "closest real types: " + ", ".join(near)
            except Exception as exc:  # noqa: BLE001 -- guidance is best-effort
                logger.debug("build_graph: type hint unavailable: %s", exc)
        bad.append("'%s'%s" % (type_name,
                               (" -- " + remediation) if remediation else ""))

    if bad:
        raise SynapseUserError(
            "unknown %s node type(s): %s"
            % (category.name(), "; ".join(sorted(set(bad)))),
            # The panel worker may not call synapse_scout (fail-closed allowlist);
            # pointing there sent the 10/1 bench into denied calls.
            suggestion=("Nothing was created. Use one of the closest real types "
                        "exactly, or look up the artist's words with "
                        "synapse_knowledge_lookup, then re-run."),
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


# ── On-camera polish (G1 badge check, G2 framing) ────────────────────────
# A build that "succeeds" with a red error badge on one of its new nodes reads
# as a failure on camera, and nothing in the build path looked: node.errors()
# only reports the LAST cook, and inside the update-mode sandwich (or hython)
# the new nodes have not cooked yet. So the check cooks first, then reads.


def _cook_and_collect_badges(nodes) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Cook ``nodes`` (sinks first) and return ``(errors, warnings)``.

    Each entry is ``(node_path, message)``. Only LOP nodes are cooked -- a
    ``usdrender_rop`` under /stage is a RopNode, and cooking a ROP RENDERS, so
    ROPs (and any non-LOP) are read without cooking. ``hou.OperationFailed``
    from ``cook()`` is the expected error signal, not a failure of the check;
    the message is read back from ``errors()``. Never raises.
    """
    errors: List[Tuple[str, str]] = []
    warnings: List[Tuple[str, str]] = []
    lop_cls = getattr(hou, "LopNode", None)
    for node in nodes:
        if lop_cls is not None and isinstance(node, lop_cls):
            try:
                node.cook(force=False)
            except Exception as exc:  # noqa: BLE001 -- OperationFailed == the node errored
                logger.debug("build_graph: badge cook raised (read back below): %s", exc)
    for node in nodes:
        try:
            path = node.path()
            node_errors = tuple(node.errors() or ())
            node_warnings = tuple(node.warnings() or ())
        except Exception as exc:  # noqa: BLE001 -- a node we cannot read cannot be badged
            logger.debug("build_graph: badge read skipped: %s", exc)
            continue
        errors.extend((path, str(msg)) for msg in node_errors)
        warnings.extend((path, str(msg)) for msg in node_warnings)
    return errors, warnings


def _inherited_error_nodes(created_nodes, created_paths) -> Dict[str, str]:
    """Created nodes whose error comes from an erroring EXISTING upstream node.

    ``created_nodes`` in topological order. A LOP under an erroring input
    reports its own "Invalid source ..." error (probed on 22.0.400), so
    without this a new light wired under a broken pythonscript LOP would be
    rolled back and blamed. Returns ``{created_path: external_source_path}``.
    A node downstream of a created node with its OWN error is not excused.
    """
    inherited: Dict[str, str] = {}
    for node in created_nodes:
        try:
            if not node.errors():
                continue
            path = node.path()
            for source in node.inputs():
                if source is None or not source.errors():
                    continue
                src = source.path()
                if src not in created_paths:
                    inherited[path] = src
                    break
                if src in inherited:
                    inherited[path] = inherited[src]
                    break
        except Exception as exc:  # noqa: BLE001 -- unknown stays fatal
            logger.debug("build_graph: inherited-error check skipped: %s", exc)
    return inherited


class _BadgeFailure(SynapseUserError):
    """New nodes showed an error badge. Raised inside the build's undo group;
    the handler's ``except`` words the error, because only there is it known
    whether the build was really taken back out (see ``_badge_failure_error``)."""


def _badge_failure_error(detail: str, rolled_back: bool, undo_enabled: bool) -> SynapseUserError:
    """The error for a build whose new nodes showed an error badge.

    It says "rolled back" only when the undo actually ran. Under another open
    undo group this build's own group never reaches the undo stack, so nothing
    can be undone here (``performUndo`` raises inside a group on 22.0.400) and
    the nodes are still in the network: the panel's execution bridge wraps
    every mutating tool that way. Before 10/1 the text claimed a rollback on
    every path. Probed on 22.0.400: without an outer group the build is rolled
    back; under one, the node stays and one Ctrl+Z removes it."""
    retry = ("fix the parameter/input named above and re-run, or pass badge_check:false "
             "to keep the nodes despite the error.")
    if rolled_back:
        return SynapseUserError("build rolled back -- " + detail,
                                suggestion="Nothing was left in the network. F" + retry[1:])
    if undo_enabled:
        where = ("Its nodes are still in the network: the build ran inside another undo "
                 "step, so one Ctrl+Z (or REVERT) removes them")
    else:
        where = "Its nodes are still in the network, and undo is off, so remove them by hand"
    return SynapseUserError("build failed and was NOT rolled back -- " + detail,
                            suggestion="%s. Then %s" % (where, retry))


_FRAME_PAD = (0.8, 0.6)      # network units around the framed context
_FRAME_TRANSITION = 0.25     # seconds; a short animated move reads calmer on camera


def _context_bounds(nodes):
    """hou.BoundingRect around ``nodes`` plus their immediate upstream and
    downstream neighbours, padded; None when nothing can be measured."""
    try:
        seen, items = set(), []
        for node in list(nodes) + [n for node in nodes
                                   for n in tuple(node.inputs()) + tuple(node.outputs())]:
            if node is None or node.path() in seen:
                continue
            seen.add(node.path())
            items.append(node)
        xs0, ys0, xs1, ys1 = [], [], [], []
        for node in items:
            pos, size = node.position(), node.size()
            xs0.append(pos[0])
            ys0.append(pos[1])
            xs1.append(pos[0] + size[0])
            ys1.append(pos[1] + size[1])
        if not items:
            return None
        rect = hou.BoundingRect(min(xs0), min(ys0), max(xs1), max(ys1))
        rect.expand(_FRAME_PAD)
        return rect
    except Exception as exc:  # noqa: BLE001 -- fall back to homeToSelection
        logger.debug("build_graph: context bounds unavailable: %s", exc)
        return None


def _frame_new_nodes(parent_node, nodes, current) -> bool:
    """Best-effort: select ``nodes`` in every Network Editor showing
    ``parent_node``, make ``current`` the current node, and frame them.

    Returns True only when at least one editor was framed. A no-op returning
    False when there is no UI (hython), no ``hou.ui``, no editor on this
    network, or anything at all raises -- framing is cosmetic and must never
    fail or roll back a build.
    """
    try:
        if not nodes or not hou.isUIAvailable():
            return False
        ui = getattr(hou, "ui", None)
        if ui is None:
            return False
        parent_path = parent_node.path()
        editors = []
        for tab in ui.paneTabs():
            if not isinstance(tab, hou.NetworkEditor):
                continue
            try:
                pwd = tab.pwd()
            except Exception as exc:  # noqa: BLE001
                logger.debug("build_graph: editor pwd unreadable: %s", exc)
                continue
            if pwd is not None and pwd.path() == parent_path:
                editors.append(tab)
        if not editors:
            return False
        # R1: HOM setSelected pushes its own "Change Selection" undo entry
        # (probed on 22.0.400). Framing must not leave one on top of the
        # build -- Ctrl+Z would hit the selection first and the panel's REVERT
        # would refuse. Selection is cosmetic, so it is made outside undo.
        undos = getattr(hou, "undos", None)
        disabler = getattr(undos, "disabler", None)
        with (disabler() if callable(disabler) else contextlib.nullcontext()):
            for index, node in enumerate(nodes):
                node.setSelected(True, clear_all_selected=(index == 0))
            if current is not None:
                current.setCurrent(True, clear_all_selected=False)
        # P4: frame the new nodes TOGETHER WITH their immediate upstream and
        # downstream neighbours, so the chain reads in context (homeToSelection
        # alone was too tight on camera). setVisibleBounds keeps the editor's
        # aspect and animates the move; homeToSelection is the fallback.
        bounds = _context_bounds(nodes)
        framed = False
        for editor in editors:
            try:
                if bounds is not None:
                    editor.setVisibleBounds(bounds, transition_time=_FRAME_TRANSITION)
                else:
                    editor.homeToSelection()
                framed = True
            except Exception as exc:  # noqa: BLE001
                logger.debug("build_graph: framing an editor failed: %s", exc)
                continue
        return framed
    except Exception as exc:  # noqa: BLE001 -- cosmetic, never fatal
        logger.debug("build_graph: framing skipped: %s", exc)
        return False


_SPLICE_SIDE_GAP = 3.0   # network units right of the column beside the splice
_SPLICE_ROW = 1.0        # first inserted node sits one row below the displaced one


def _splice_origin(anchor_pos, local_positions, others) -> Tuple[float, float]:
    """Layout origin placing a spliced-in block in a side column next to the
    displaced node ``anchor_pos``: its top row one row below the anchor, its
    left edge ``_SPLICE_SIDE_GAP`` right of every other node that shares those
    rows. Pure (positions in, offset out); ``others`` excludes the new nodes.
    """
    xs = [p[0] for p in local_positions.values()]
    ys = [p[1] for p in local_positions.values()]
    top_y = anchor_pos[1] - _SPLICE_ROW
    bottom_y = top_y - (max(ys) - min(ys))
    band = [p[0] for p in others if bottom_y - _SPLICE_ROW <= p[1] <= anchor_pos[1] + _SPLICE_ROW]
    left_x = max(band + [anchor_pos[0]]) + _SPLICE_SIDE_GAP
    return left_x - min(xs), top_y - max(ys)


_INLINE_BAND = 1.75      # half-width of "the same column" (HORIZONTAL_SPACING / 2)
_INLINE_ROW = 1.2        # row pitch when A -> B gives none to copy (VERTICAL_SPACING)


def _downstream_positions(target, exclude_paths) -> Dict[str, Tuple[float, float]]:
    """``target`` and every node reachable downstream from it (live outputs),
    excluding ``exclude_paths`` (this build's new nodes). Path -> position."""
    found: Dict[str, Tuple[float, float]] = {}
    pending = [target]
    while pending:
        node = pending.pop()
        try:
            path = node.path()
            if path in found or path in exclude_paths:
                continue
            pos = node.position()
            found[path] = (pos[0], pos[1])
            pending.extend(n for n in node.outputs() if n is not None)
        except Exception as exc:  # noqa: BLE001 -- unreadable node: leave it where it is
            logger.debug("build_graph: downstream walk skipped a node: %s", exc)
    return found


# R2 (10/1 12:22 take): at the artist's 0.894 row pitch the inserted lights'
# labels overlapped, and dusk_key's sat under look_fade_10's three-line
# comment. Text is NOT measured through hou; a conservative, tested rule adds
# room below any node that draws text under its tile:
#   * a displayed comment (DisplayComment flag set) counts its lines, each
#     source line wrapped at _LABEL_WRAP characters (look_fade_10's 107-char
#     comment -> 3 lines, the 3 it drew on camera);
#   * a node with a `primpath` parm (lights, cameras) draws its prim path as
#     one more line.
# Each line adds _LABEL_LINE network units (about one node tile height, 0.28).
_LABEL_LINE = 0.28
_LABEL_WRAP = 40


def _label_lines(comment, shows_comment, has_primpath) -> int:
    """Text lines a node draws below its tile, by the rule above. Pure."""
    lines = 0
    if shows_comment and comment:
        for part in str(comment).splitlines() or [""]:
            lines += max(1, -(-len(part) // _LABEL_WRAP))
    if has_primpath:
        lines += 1
    return lines


def _node_label_lines(node) -> int:
    """_label_lines for a live hou node; 0 when anything is unreadable."""
    try:
        return _label_lines(node.comment(),
                            node.isGenericFlagSet(hou.nodeFlag.DisplayComment),
                            node.parm("primpath") is not None)
    except Exception as exc:  # noqa: BLE001 -- spacing degrades to the plain pitch
        logger.debug("build_graph: label lines unreadable: %s", exc)
        return 0


def _inline_splice_layout(anchor_pos, target_pos, local_positions, downstream,
                          anchor_lines=0, node_lines=None):
    """P3 inline splice: place the new rows in A's column directly below A and
    push only B's downstream chain (same column band, below A) down by the
    room they need. Pure. Returns ``(positions, shifts)`` -- ``positions``
    {nid: (x, y)}, ``shifts`` [(path, dx, dy)] -- or None when A -> B is not a
    vertical step (the caller then falls back to the side column).

    The row pitch copies the artist's own A -> B spacing so the column keeps its
    rhythm; a B that already sits low enough is not moved at all. R2: the gap
    below A grows by ``anchor_lines`` label lines, and the gap below each new
    row by the most label lines any node in that row draws (``node_lines``).
    """
    gap = anchor_pos[1] - target_pos[1]
    if gap <= 0.3 or abs(target_pos[0] - anchor_pos[0]) > _INLINE_BAND:
        return None
    node_lines = node_lines or {}
    pitch = gap if gap <= 1.5 * _INLINE_ROW else _INLINE_ROW
    rows = sorted({round(p[1], 6) for p in local_positions.values()}, reverse=True)
    row_lines = [max([node_lines.get(nid, 0) for nid, p in local_positions.items()
                      if round(p[1], 6) == y] + [0]) for y in rows]
    row_y, y = [], anchor_pos[1] - (pitch + _LABEL_LINE * anchor_lines)
    for lines in row_lines:
        row_y.append(y)
        y -= pitch + _LABEL_LINE * lines
    row_of = {ry: index for index, ry in enumerate(rows)}
    top_row_xs = [p[0] for p in local_positions.values() if round(p[1], 6) == rows[0]]
    base_x = min(top_row_xs)
    positions = {
        nid: (anchor_pos[0] + (x - base_x), row_y[row_of[round(py, 6)]])
        for nid, (x, py) in local_positions.items()}
    need_y = y   # one labelled row below the last new row
    dy = min(0.0, need_y - target_pos[1])
    shifts = []
    if dy < 0.0:
        for path, (x, y) in sorted(downstream.items()):
            if abs(x - anchor_pos[0]) <= _INLINE_BAND and y < anchor_pos[1]:
                shifts.append((path, 0.0, dy))
    return positions, shifts


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

    if not isinstance(nodes, list) or not isinstance(connections, list):
        return False, ["nodes and connections must be lists"], warnings
    if not nodes:
        return (not connections), (["Connections require graph nodes"] if connections else []), warnings
    names = set()
    for spec in nodes:
        if not isinstance(spec, dict) or not isinstance(spec.get("id"), str) or not spec["id"]:
            errors.append("Every node needs a nonempty string id")
            continue
        if "existing" in spec and not isinstance(spec["existing"], bool):
            errors.append("Node '%s': existing must be a boolean" % spec["id"])
        if not spec.get("existing"):
            if not isinstance(spec.get("type"), str) or not spec["type"]:
                errors.append("Node '%s' needs a node type" % spec["id"])
            name = spec.get("name") or spec["id"]
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                errors.append("Node '%s' needs a Houdini name using letters, numbers, and underscores" % spec["id"])
            elif name in names:
                errors.append("Duplicate node name: '%s'" % name)
            names.add(name if isinstance(name, str) else spec["id"])
    if errors:
        return False, errors, warnings

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
    claimed_slots = set()
    existing_ids = {n["id"] for n in nodes if n.get("existing")}
    for conn in connections:
        if not isinstance(conn, dict):
            errors.append("Each connection must be an object")
            continue
        from_id = conn.get("from", "")
        to_id = conn.get("to", "")
        if not isinstance(from_id, str) or not isinstance(to_id, str):
            errors.append("Connection source and target IDs must be strings")
            continue
        if from_id not in node_id_set:
            errors.append(f"Connection references unknown source id: '{from_id}'")
        if to_id not in node_id_set:
            errors.append(f"Connection references unknown target id: '{to_id}'")
        if from_id == to_id and from_id:
            errors.append(f"Self-loop on node '{from_id}'")
        for field in ("input", "output"):
            if field in conn and (type(conn[field]) is not int or conn[field] < 0):
                errors.append("Connection %s must be a nonnegative integer" % field)
        if "insert" in conn and not isinstance(conn["insert"], bool):
            errors.append("Connection insert must be a boolean")
        if type(conn.get("input", 0)) is int and ("input" in conn or to_id not in existing_ids):
            slot = (to_id, conn.get("input", 0))
            if slot in claimed_slots:
                errors.append("Multiple connections claim '%s' input %d" % slot)
            claimed_slots.add(slot)

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
                - badge_check: cook the built nodes and roll the whole build
                  back if a NEW node shows an error badge (default: true);
                  warnings are reported, never rolled back
                - frame: select + center the Network Editor on the new nodes
                  when a UI is present (default: true); never fails a build

        Returns:
            {
                "status": "created" | "preview",
                "nodes_created": [{id, path}, ...],
                "connections_made": [{from, to, input}, ...],
                "display_node": path,
                "topology": "dag" | "linear" | "single",
                "merge_points": [path, ...],
                "badges": {enabled, checked, warnings, errors_on_reused},
                "framed": bool,
                "warnings": [str, ...],
                "dry_run": bool
            }
        """
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        if payload.get("template") == "copernicus_lookdev":
            from .solaris_lookdev import validate_request, build_lookdev
            from .main_thread import run_on_main, _SLOW_TIMEOUT
            try:
                settings = validate_request(payload)
            except ValueError as error:
                raise SynapseUserError(str(error)) from error
            return run_on_main(lambda: build_lookdev(hou, settings), timeout=_SLOW_TIMEOUT,
                               label="solaris_graph:copernicus_lookdev")

        parent_path = resolve_param_with_default(payload, "parent", "/stage")
        raw_nodes = payload.get("nodes", [])
        raw_connections = payload.get("connections", [])
        display_node_id = payload.get("display_node", None)
        template_name = payload.get("template", None)
        template_params = payload.get("template_params", {})
        dry_run = payload.get("dry_run", False)
        orientation = payload.get("layout", "vertical")
        relayout = payload.get("relayout", False)
        if orientation not in ("vertical", "horizontal"):
            raise SynapseUserError("layout must be 'vertical' or 'horizontal'")
        if not isinstance(relayout, bool):
            raise SynapseUserError("relayout must be a boolean")
        badge_check = payload.get("badge_check", True)
        frame = payload.get("frame", True)
        if not isinstance(badge_check, bool):
            raise SynapseUserError("badge_check must be a boolean")
        if not isinstance(frame, bool):
            raise SynapseUserError("frame must be a boolean")
        splice_layout = payload.get("splice_layout", "inline")
        if splice_layout not in ("inline", "side"):
            raise SynapseUserError("splice_layout must be 'inline' or 'side'")

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
            plan = resolve_plan(parent_node, node_map, sorted_ids, raw_connections,
                                hou, _resolve_existing_node)
            display_before, display_known = observed_display(parent_node)
            planned_links = [{key: link[key] for key in ("from", "to", "input", "output")}
                             for link in plan["connections"]]
            if dry_run:
                return {
                    "status": "preview", "dry_run": True,
                    "nodes_created": [{"id": nid, "path": plan["paths"][nid]} for nid in sorted_ids
                                      if plan["bindings"][nid] is None],
                    "nodes_reused": [{"id": nid, "path": plan["paths"][nid]} for nid in sorted_ids
                                     if plan["bindings"][nid] is not None],
                    "connections_made": planned_links, "planned_connections": planned_links,
                    "display_node": display_before,
                    "display_observed": display_known,
                    "requested_display_node": plan["paths"][display_node_id],
                    "topology": topology, "merge_points": [plan["paths"][nid] for nid in merge_ids],
                    "ambiguous_merges": ambiguous_merges, "warnings": warnings,
                    "layout": {"requested": orientation, "applied": False, "relayout": relayout},
                }
            moved = []
            shifted = []   # existing nodes an inline splice moved, with offsets
            splice_applied = None   # "inline" | "side" when a splice was placed
            badge_report = {"enabled": badge_check, "checked": False,
                            "warnings": [], "errors_on_reused": [], "inherited_errors": []}
            undo_enabled, labels_before = False, ()
            try:
                undo_enabled = bool(hou.undos.areEnabled())
                labels_before = tuple(hou.undos.undoLabels())
            except Exception:
                pass

            try:
                with hou.undos.group("SYNAPSE: build_graph"):
                    # F1 freeze-relief: update-mode sandwich INSIDE the
                    # undo group (the probed nesting) — collapses the
                    # per-create/per-parm auto-cook flood across create,
                    # parm-set, wiring, layout, and display-flag phases.
                    # Flag-off/headless = identical behavior to today.
                    from .update_mode import cook_sandwich
                    with cook_sandwich(
                            label="solaris_build_graph") as _sandwich:
                        # Heuristic collapsed-cook estimate for the A/B
                        # histogram: one auto-cook per spec node plus the
                        # display-flag cook. A stated upper bound, not a
                        # measured count.
                        _sandwich.note_estimate(len(node_map) + 1)

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

                        # 3. Apply the resolved plan, then read every wire back.
                        # Unordered ports compact gaps as they are wired. Fill
                        # lower slots first, independent of request-list order.
                        for link in sorted(plan["connections"], key=lambda link: (link["to"], link["input"])):
                            source = id_to_hou[link["from_id"]]
                            target = id_to_hou[link["to_id"]]
                            desired = (source.path(), link["output"])
                            prior = observed_inputs(target).get(link["input"])
                            if prior != desired:
                                target.setInput(link["input"], source, link["output"])
                                connections_changed = True
                        for link in plan["connections"]:
                            target = id_to_hou[link["to_id"]]
                            actual = observed_inputs(target).get(link["input"])
                            desired = (id_to_hou[link["from_id"]].path(), link["output"])
                            if actual != desired:
                                raise SynapseUserError(
                                    "Connection readback did not match %s input %d" % (target.path(), link["input"]),
                                    suggestion="Inspect the network; no verified connection is claimed.")
                            connections_made.append({"from": actual[0], "to": target.path(),
                                                     "input": link["input"], "output": actual[1]})

                        # Preserve the artist's comments and positions on reused nodes.
                        created_ids = {entry["id"] for entry in nodes_created}
                        managed = {nid: node for nid, node in id_to_hou.items() if nid not in existing_nids}
                        for nid in created_ids:
                            node = id_to_hou[nid]
                            node.setComment("SYNAPSE: build_graph")
                            node.setGenericFlag(hou.nodeFlag.DisplayComment, True)

                        # 5. New nodes get a free area. Explicit relayout anchors to
                        # this graph's first reused node, never to another network.
                        movable = managed if relayout else {nid: managed[nid] for nid in created_ids}
                        moving_ids = [nid for nid in sorted_ids if nid in movable]
                        layout_links = [{"from": link["from_id"], "to": link["to_id"], "input": link["input"]}
                                        for link in plan["connections"]]
                        local_positions = _compute_dag_positions(moving_ids, layout_links,
                                                                 orientation=orientation)
                        anchors = [nid for nid in moving_ids if nid not in created_ids]
                        splice_link = next((link for link in plan["connections"]
                                            if link.get("displaced")), None)
                        splice_anchor = hou.node(splice_link["displaced"]) if splice_link else None
                        explicit = None   # nid -> (x, y) when a layout places nodes itself
                        if (not anchors and splice_anchor is not None and local_positions
                                and splice_layout == "inline" and orientation == "vertical"):
                            # P3 inline: the new nodes go in A's column directly
                            # below A; only B's downstream chain (same column
                            # band) moves down to make room. Nothing else moves.
                            splice_target = hou.node(splice_link["to"])
                            new_paths = {node.path() for node in movable.values()}
                            downstream = _downstream_positions(splice_target, new_paths)
                            # R2: room for the text drawn under A and under each
                            # new node (comments + prim path), by _label_lines.
                            inline = _inline_splice_layout(
                                splice_anchor.position(), splice_target.position(),
                                local_positions, downstream,
                                anchor_lines=_node_label_lines(splice_anchor),
                                node_lines={nid: _node_label_lines(movable[nid])
                                            for nid in local_positions})
                            if inline is not None:
                                explicit, shift_plan = inline
                                for path, dx, dy in shift_plan:
                                    node = hou.node(path)
                                    pos = node.position()
                                    node.setPosition(hou.Vector2(pos[0] + dx, pos[1] + dy))
                                    shifted.append({"node": path, "dx": round(dx, 6), "dy": round(dy, 6)})
                        if explicit is not None:
                            ox, oy = 0.0, 0.0
                            splice_applied = "inline"
                        elif anchors:
                            anchor = anchors[0]
                            current, desired = movable[anchor].position(), local_positions[anchor]
                            ox, oy = current[0] - desired[0], current[1] - desired[1]
                        elif splice_anchor is not None and local_positions:
                            # Inserted between existing A -> B: a side column
                            # beside A, not the bottom of the network (whose
                            # wires would run back up behind the whole chain).
                            new_paths = {node.path() for node in movable.values()}
                            others = [child.position() for child in parent_node.children()
                                      if child.path() not in new_paths]
                            ox, oy = _splice_origin(splice_anchor.position(), local_positions, others)
                            splice_applied = "side"
                        else:
                            ox, oy = _free_origin(parent_node, {node.path() for node in movable.values()})
                            # Horizontal roots can extend above the origin; keep
                            # their entire bounding range below existing content.
                            if local_positions:
                                oy -= max(position[1] for position in local_positions.values())
                        for nid, (x, y) in local_positions.items():
                            node = movable[nid]
                            before = node.position()
                            desired = explicit[nid] if explicit is not None else (ox + x, oy + y)
                            if any(abs(before[i] - desired[i]) > 1e-7 for i in (0, 1)):
                                node.setPosition(hou.Vector2(*desired))
                                moved.append(node.path())

                        # Cosmetic sections follow the actual flow axis. A no-op
                        # preserves existing boxes, including the artist's sizing.
                        sections = []
                        if created_ids or moved:
                            node_ranks = {nid: _SOLARIS_NODE_ORDER.get(
                                str(node_map[nid]["type"]).split("::")[0].lower(), _UNRANKED_RANK)
                                for nid in managed}
                            sections = _apply_section_boxes(parent_node, managed, node_ranks,
                                namespace=id_to_hou[display_node_id].name(), orientation=orientation)
                        elif managed:
                            try:
                                members = set(managed.values())
                                sections = [box.name() for box in parent_node.networkBoxes()
                                            if box.name().startswith("synapse_sec_")
                                            and any(node in members for node in box.nodes())]
                            except Exception:
                                pass

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

                    # 7. G1 badge check -- AFTER the sandwich has restored the
                    # artist's update mode, still INSIDE the undo group, so an
                    # error raised here takes the same performUndo rollback as
                    # any other build failure. Errors on nodes this build
                    # CREATED roll the whole build back; warnings (and anything
                    # on reused nodes, whose state predates this build) are
                    # reported, never rolled back. Existing:true nodes are the
                    # artist's and are not inspected.
                    if badge_check:
                        created_set = {entry["id"] for entry in nodes_created}
                        check_ids = [nid for nid in reversed(sorted_ids)
                                     if nid not in existing_nids]
                        badge_errors, badge_warnings = _cook_and_collect_badges(
                            [id_to_hou[nid] for nid in check_ids])
                        created_paths = {id_to_hou[nid].path() for nid in created_set}
                        # An error inherited from an erroring EXISTING upstream
                        # node is the artist's, not this build's: keep the build
                        # and say where the error comes from.
                        inherited = _inherited_error_nodes(
                            [id_to_hou[nid] for nid in sorted_ids if nid in created_set],
                            created_paths)
                        for p, src in sorted(inherited.items()):
                            badge_report["inherited_errors"].append({"node": p, "from": src})
                            warnings.append("%s inherits an upstream error from %s; build kept"
                                            % (p, src))
                        fatal = [(p, m) for p, m in badge_errors
                                 if p in created_paths and p not in inherited]
                        for p, m in badge_errors:
                            if p not in created_paths:
                                badge_report["errors_on_reused"].append(
                                    {"node": p, "message": m})
                                warnings.append("reused node %s has an error: %s" % (p, m))
                        for p, m in badge_warnings:
                            badge_report["warnings"].append({"node": p, "message": m})
                            warnings.append("%s: %s" % (p, m))
                        if fatal:
                            raise _BadgeFailure(
                                "%d new node(s) showed an error badge after cooking: %s"
                                % (len({p for p, _ in fatal}),
                                   "; ".join("%s: %s" % (p, m) for p, m in fatal)))
                        badge_report["checked"] = True

            except Exception as build_exc:
                # Safe undo fallback — the C++ undo layer for LOP nodes
                # with USD stage data can throw during __exit__ if GPU
                # resources are being deallocated. Catch and explicitly
                # undo to prevent undo stack corruption.
                rolled_back = False
                try:
                    if undo_enabled and tuple(hou.undos.undoLabels()) != labels_before:
                        hou.undos.performUndo()
                        rolled_back = True
                except Exception as undo_exc:
                    logger.warning("build_graph: undo rollback also failed: %s", undo_exc)
                if isinstance(build_exc, _BadgeFailure):
                    # Only now is it known whether the build was taken back out.
                    raise _badge_failure_error(str(build_exc), rolled_back, undo_enabled) from None
                raise

            # B4: a rebuild that reused everything is not a "created" -- saying
            # so is the same lie the duplicate network told, pointed the other
            # way. The status names what actually happened.
            # 'created' when new nodes were made; 'updated' when only pre-existing
            # nodes (reused-by-name or artist-owned 'existing') were touched but
            # a parm or a wire actually moved; 'unchanged' when a rebuild was a
            # genuine no-op. A build that only references existing nodes (an
            # extend that appends nothing new) must never read 'created'.
            display_after, display_after_known = observed_display(parent_node)
            display_changed = (display_before != display_after) if display_known and display_after_known else False
            _touched = (parms_changed or connections_changed or bool(moved) or bool(shifted)
                        or display_changed)
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

            # G2: frame the network editor on what this build made. After the
            # undo group has closed (selection is not undoable, and a framing
            # failure must never roll back a good build). No-op in hython.
            framed = False
            if frame and (nodes_created or moved):
                frame_ids = [nid for nid in sorted_ids if nid not in existing_nids
                             and (nid in created_ids or id_to_hou[nid].path() in moved)]
                current = (display_hou if display_node_id not in existing_nids
                           else (id_to_hou[frame_ids[-1]] if frame_ids else None))
                framed = _frame_new_nodes(parent_node,
                                          [id_to_hou[nid] for nid in frame_ids], current)

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
                "display_node": display_after,
                "display_observed": display_after_known,
                "requested_display_node": display_hou.path(),
                "layout": {"requested": orientation, "applied": bool(movable), "moved": moved,
                           # existing nodes an inline splice moved, with exact offsets
                           "splice_layout": splice_applied,
                           "shifted": shifted,
                           "preserved": [node.path() for nid, node in id_to_hou.items()
                                         if nid not in movable
                                         and node.path() not in {s["node"] for s in shifted}]},
                "verification": {"connections": "verified", "parameters": "partial" if parms_missed else "applied"},
                "topology": topology,
                "merge_points": [id_to_hou[mid].path() for mid in merge_ids],
                "ambiguous_merges": ambiguous_merges,
                "badges": badge_report,
                "framed": framed,
                "warnings": warnings,
                "dry_run": False,
            }

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT, label="solaris_graph:_handle_solaris_build_graph")
