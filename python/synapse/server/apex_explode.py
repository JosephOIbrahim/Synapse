"""Planning for ``synapse_add_explode_control``: what the tool decides before
it touches a scene, and the code of the one node it writes.

Pure. This module imports neither ``hou`` nor ``apex``. Every node and
geometry it is handed is read through plain method calls, so the whole plan is
testable with stand-ins and no Houdini.

What the tool does, in one line: it adds one control, ``explode``, to an
existing APEX rig, carried by one Python SOP placed after the node that packs
the character. It builds no rig. The exception to boundary rule D-H22-3 that
allows this one tool is recorded in docs/SYNAPSE_H22_BOUNDARY.md, section 6.

Where the explode directions come from: the asset. Each point of the rest
shape carries its own move at full explode in a vector attribute,
``explode_offset``, in the shape's rest space. The tool reads that attribute
and refuses an asset that has none. It does not invent directions.

What it never does:

  * force a cook to find the character. A node is read only through the
    caller's reader, which declines a node that would have to cook;
  * take code, node names or coordinates from the caller. The node's code is
    generated here from the rig's own names and from measured numbers;
  * edit the rig in place. The packed rig upstream is left as it was, and the
    new node hands on an edited copy.
"""
from __future__ import annotations

import inspect
import logging
import math
import textwrap
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.errors import SynapseUserError
from . import apex_explode_edit as _edit
from . import apex_graph

try:
    import numpy as _np

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover -- numpy ships with Houdini and with the test seat
    _np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

#: The control's name in the rig, and the slider's name on the node.
CONTROL = "explode"
SLIDER = "explode"
#: Per-point vector attribute on the rest shape: each point's move at full explode.
OFFSET_ATTRIBUTE = "explode_offset"
#: The node SYNAPSE writes, and how it is told from an artist's own node.
CARRIER_NAME = "SYNAPSE_explode_control"
MARKER_KEY = "synapse_tool"
MARKER_VALUE = "add_explode_control"
#: One undo step, named in words. The bridge adds the "SYNAPSE: " prefix back.
UNDO_LABEL = "SYNAPSE: Add explode control"
#: What the edit adds to the graph: one control and four working nodes.
ADDED_NODES = ("explode", "EXPLODE_height", "EXPLODE_travel", "EXPLODE_limits",
               "EXPLODE_move")
ADDED_INPUTS = ("explode_t",)
ADDED_OUTPUTS = ("explode", "explode_amount")

#: Defaults measured from the asset: the handle travels a quarter of the
#: asset's height, and rests an eighth of its height above its top.
TRAVEL_FRACTION = 0.25
HANDLE_CLEARANCE_FRACTION = 0.125

#: Bounds on the walk upstream to the node that packs the character.
UPSTREAM_DEPTH_CAP = 8
UPSTREAM_NODE_CAP = 24
CLIMB_CAP = 32

RIG_SUFFIX = ".rig"
SHAPE_SUFFIX = ".shp"
_TEXT_CAP = 200


# ---------------------------------------------------------------------------
# The character a node holds
# ---------------------------------------------------------------------------

def characters_in(geo: Any) -> List[Dict[str, Any]]:
    """The characters packed at the top level of *geo*.

    A character here is a ``<name>.rig`` folder that holds an APEX graph with
    a ``<name>.shp`` folder beside it. A scene's nested characters are one
    level down and are not listed: the tool edits the character where it is
    first packed, not inside a scene.
    """
    rigs: Dict[str, Any] = {}
    shapes: Dict[str, Any] = {}
    for label, embedded, depth in apex_graph.iter_folders(geo):
        if depth != 0 or not isinstance(label, str):
            continue
        if label.endswith(RIG_SUFFIX) and apex_graph.is_graph_geometry(embedded):
            rigs.setdefault(label[:-len(RIG_SUFFIX)], embedded)
        elif label.endswith(SHAPE_SUFFIX):
            shapes.setdefault(label[:-len(SHAPE_SUFFIX)], embedded)
    return [
        {"name": name, "rig_folder": name + RIG_SUFFIX, "shape_folder": name + SHAPE_SUFFIX,
         "rig": rigs[name], "shape": shapes[name]}
        for name in sorted(set(rigs) & set(shapes))
    ]


def _path_of(node: Any) -> Optional[str]:
    try:
        path = node.path()
    except Exception:
        logger.debug("node path unavailable", exc_info=True)
        return None
    return path if isinstance(path, str) else None


def _inputs_of(node: Any) -> List[Any]:
    try:
        inputs = node.inputs()
    except Exception:
        logger.debug("inputs unavailable", exc_info=True)
        return []
    if not isinstance(inputs, (tuple, list)):
        return []
    return [n for n in inputs if n is not None]


def find_packer(node: Any, read_geometry: Callable[[Any], Any]) -> Dict[str, Any]:
    """The node that first packs the character *node* shows or is fed by.

    Two steps. The nearest node at or above *node* whose output holds a
    character at its top level is found breadth first. From there the walk
    climbs while an input still holds the same character, so a Rig Pose, or
    this tool's own node from an earlier call, leads back to the node the
    character starts at. Every consumer of that node then gets the control.

    *read_geometry* takes a node and returns its geometry, or None when the
    caller will not read it (a node that would have to cook). This function
    never calls ``geometry()`` itself.

    Returns ``{"node", "characters", "examined", "unread"}``. ``node`` is None
    when no character was found.
    """
    examined = 0
    unread: List[str] = []

    def look(candidate: Any) -> List[Dict[str, Any]]:
        nonlocal examined
        examined += 1
        try:
            geo = read_geometry(candidate)
        except Exception:
            logger.debug("geometry reader failed", exc_info=True)
            geo = None
        if geo is None:
            path = _path_of(candidate)
            if path is not None and path not in unread:
                unread.append(path)
            return []
        return characters_in(geo)

    found: Optional[Tuple[Any, List[Dict[str, Any]]]] = None
    seen = {_path_of(node)}
    frontier: List[Tuple[Any, int]] = [(node, 0)]
    while frontier and examined < UPSTREAM_NODE_CAP:
        current, distance = frontier.pop(0)
        characters = look(current)
        if characters:
            found = (current, characters)
            break
        if distance >= UPSTREAM_DEPTH_CAP:
            continue
        for upstream in _inputs_of(current):
            path = _path_of(upstream)
            if path is None or path in seen:
                continue
            seen.add(path)
            frontier.append((upstream, distance + 1))
    if found is None:
        return {"node": None, "characters": [], "examined": examined, "unread": unread}

    current, characters = found
    names = [c["name"] for c in characters]
    for _ in range(CLIMB_CAP):
        higher = None
        for upstream in _inputs_of(current):
            above = look(upstream)
            if above and [c["name"] for c in above] == names:
                higher = (upstream, above)
                break
        if higher is None:
            break
        current, characters = higher
    return {"node": current, "characters": characters, "examined": examined,
            "unread": unread}


# ---------------------------------------------------------------------------
# The plan for one rig
# ---------------------------------------------------------------------------

def plan_edit(graph: Optional[Dict[str, Any]], shape_port: str) -> Dict[str, Any]:
    """Check one rig can take the control, and choose what the handle follows.

    *graph* is ``apex_graph.read_graph(rig, include_nodes=True,
    include_wires=True)``. Raises ``SynapseUserError`` with the reason when
    the rig is not one the edit can be made to. Returns ``{"parent",
    "parent_note", "shape_readers", "before"}``.
    """
    if not graph or not graph.get("read"):
        raise SynapseUserError(
            "No control added: the rig's graph could not be read (%s)."
            % ((graph or {}).get("reason") or "it is not an APEX graph"))
    if graph.get("wires_status") != "read":
        raise SynapseUserError(
            "No control added: the rig's wires were %s, and the edit needs all of them."
            % graph.get("wires_status"))
    nodes = graph.get("nodes") or []
    wires = graph.get("wires") or []
    names = [n["name"] for n in nodes]
    if len(set(names)) != len(names):
        raise SynapseUserError(
            "No control added: two nodes in the rig share a name, so a wire "
            "cannot be placed by name.")

    def named(callback: str) -> List[str]:
        return [n["name"] for n in nodes if n["callback"] == callback]

    inputs = named(apex_graph.GRAPH_INPUT_CALLBACK)
    outputs = named(apex_graph.GRAPH_OUTPUT_CALLBACK)
    if len(inputs) != 1 or len(outputs) != 1:
        raise SynapseUserError(
            "No control added: the rig needs one input node and one output node, "
            "and has %d and %d." % (len(inputs), len(outputs)))
    # Read from the wires, not from the summary's input and output lists:
    # those are capped at a length a large rig can pass.
    published_in = {w["source_port"] for w in wires if w["source"] == inputs[0]}
    published_out = {w["destination_port"] for w in wires if w["destination"] == outputs[0]}
    taken = [name for name in ADDED_NODES if name in names]
    taken += [p for p in ADDED_INPUTS if p in published_in]
    taken += [p for p in ADDED_OUTPUTS if p in published_out]
    if taken:
        raise SynapseUserError(
            "No control added: the rig already has %s." % ", ".join(sorted(set(taken))),
            suggestion="It may already carry an explode control. "
                       "synapse_inspect_node lists the rig's controls.")
    readers = [w for w in wires
               if w["source"] == inputs[0] and w["source_port"] == shape_port]
    if not readers:
        raise SynapseUserError(
            "No control added: nothing in the rig reads its shape from a graph "
            "input named %s, which is where the explode has to go in." % shape_port)

    # The handle follows the rig's root control when there is exactly one:
    # a control that is a TransformObject with nothing wired to its parent.
    parented = {w["destination"] for w in wires if w["destination_port"] == "parent"}
    roots = [n["name"] for n in nodes
             if n["callback"] == "TransformObject"
             and apex_graph.CONTROL_TAG in (n.get("tags") or [])
             and n["name"] not in parented]
    if len(roots) == 1:
        parent: Optional[str] = roots[0]
        note = "The handle follows the rig's root control, %s." % roots[0]
    elif not roots:
        parent = None
        note = ("The rig has no root control to follow, so the handle sits in "
                "world space.")
    else:
        parent = None
        note = ("The rig has %d root controls (%s), so the handle follows none "
                "of them and sits in world space."
                % (len(roots), ", ".join(roots[:4]) + (", ..." if len(roots) > 4 else "")))
    return {
        "parent": parent,
        "parent_note": note,
        "shape_readers": len(readers),
        "before": {key: graph.get(key) for key in
                   ("node_count", "wire_count", "control_count",
                    "graph_input_count", "graph_output_count")},
    }


def shape_facts(shape: Any, attribute: str = OFFSET_ATTRIBUTE) -> Dict[str, Any]:
    """What the edit needs to know about the rest shape, or the reason it stops.

    Checks the offsets are there to read: a point attribute, float, three
    wide, finite, and not all zero. Returns the point count, how many points
    move, the largest move, the shape's height and where its top is.
    """
    try:
        found = shape.findPointAttrib(attribute)
    except Exception:
        logger.debug("findPointAttrib(%r) failed", attribute, exc_info=True)
        found = None
    if found is None:
        raise SynapseUserError(
            "No control added: the shape has no point attribute named %s." % attribute,
            suggestion="The explode directions come from the asset. Each point "
                       "needs its move at full explode, as a vector attribute "
                       "named %s, before the node that packs the character." % attribute)
    try:
        kind = found.dataType().name()
        size = found.size()
    except Exception:
        logger.debug("attribute type unreadable", exc_info=True)
        kind, size = None, None
    if kind != "Float" or size != 3:
        raise SynapseUserError(
            "No control added: %s has to be a float attribute three wide, and is "
            "%s, %s wide." % (attribute, kind, size))
    try:
        box = shape.boundingBox()
        low = [float(v) for v in box.minvec()]
        high = [float(v) for v in box.maxvec()]
    except Exception:
        logger.debug("bounding box unreadable", exc_info=True)
        raise SynapseUserError("No control added: the shape's bounds could not be read.")
    height = high[1] - low[1]
    if not (len(low) == 3 and len(high) == 3 and math.isfinite(height) and height > 0.0):
        raise SynapseUserError(
            "No control added: the shape has no height to size the control from.")

    points: Optional[int] = None
    moving: Optional[int] = None
    largest: Optional[float] = None
    if NUMPY_AVAILABLE:
        try:
            raw = shape.pointFloatAttribValuesAsString(attribute)
            offsets = _np.frombuffer(raw, dtype=_np.float32).reshape(-1, 3)
        except Exception:
            logger.debug("offsets unreadable", exc_info=True)
            offsets = None
        if offsets is not None:
            if not bool(_np.isfinite(offsets).all()):
                raise SynapseUserError(
                    "No control added: %s holds a value that is not a finite number."
                    % attribute)
            lengths = _np.sqrt((offsets.astype(_np.float64) ** 2).sum(axis=1))
            points = int(len(offsets))
            moving = int((lengths > 0.0).sum())
            largest = float(lengths.max()) if points else 0.0
            if not moving:
                raise SynapseUserError(
                    "No control added: every %s is zero, so the control would "
                    "move nothing." % attribute)
    return {
        "points": points,
        "points_that_move": moving,
        "largest_move": None if largest is None else round(largest, 6),
        "height": round(height, 6),
        "top": round(high[1], 6),
        "centre": [round((low[0] + high[0]) / 2.0, 6), round((low[2] + high[2]) / 2.0, 6)],
    }


def sizes(facts: Dict[str, Any], travel: Any = None) -> Tuple[float, Tuple[float, float, float]]:
    """(travel, handle) for one asset.

    Unless the caller gives a travel, the handle goes up a quarter of the
    asset's height for a full explode. It rests an eighth of that height above
    the asset's top, over its centre.
    """
    height = float(facts["height"])
    if travel is None:
        travel = round(height * TRAVEL_FRACTION, 4)
    else:
        if isinstance(travel, bool) or not isinstance(travel, (int, float)):
            raise SynapseUserError("travel must be a number, in scene units")
        travel = float(travel)
    if not (math.isfinite(travel) and travel > 0.0):
        raise SynapseUserError("travel must be above zero, in scene units")
    centre = facts["centre"]
    handle = (round(float(centre[0]), 4),
              round(float(facts["top"]) + height * HANDLE_CLEARANCE_FRACTION, 4),
              round(float(centre[1]), 4))
    return travel, handle


# ---------------------------------------------------------------------------
# The node's code
# ---------------------------------------------------------------------------

#: Houdini expands a Python SOP's code as a string parameter before Python
#: sees it. A doubled backslash arrives single (probe, 22.0.466), a dollar
#: sign starts a variable and a backtick starts an expression. Generated code
#: holds none of the three, so what is written is what runs.
EXPANDED_BY_HOUDINI = ("\\", "$", "`")


def _text(value: Any, what: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > _TEXT_CAP
            or not value.isprintable()
            or any(mark in value for mark in EXPANDED_BY_HOUDINI)):
        raise ValueError("%s must be a short printable name with no backslash, "
                         "dollar sign or backtick, not %r" % (what, value))
    return value


def node_code(*, rig_folder: str, shape_port: str, parent: Optional[str],
              travel: float, handle: Tuple[float, float, float],
              attribute: str = OFFSET_ATTRIBUTE, slider: str = SLIDER) -> str:
    """Python SOP code that hands on the character with the explode control added.

    The host generates this and writes it into the node. Houdini runs it, so
    its inputs are checked: every name is a short printable string written as
    a Python literal, and every number is finite. The two functions in it are
    the source of ``apex_explode_edit``, copied whole; the node needs no
    SYNAPSE to cook.
    """
    rig_folder = _text(rig_folder, "the rig folder")
    shape_port = _text(shape_port, "the shape input")
    attribute = _text(attribute, "the offset attribute")
    slider = _text(slider, "the slider")
    if parent is not None:
        parent = _text(parent, "the parent control")
    travel = float(travel)
    handle = tuple(float(v) for v in handle)
    if not (math.isfinite(travel) and travel > 0.0):
        raise ValueError("travel must be a finite number above zero")
    if len(handle) != 3 or not all(math.isfinite(v) for v in handle):
        raise ValueError("the handle must be three finite numbers")
    try:
        functions = [textwrap.dedent(inspect.getsource(fn)).rstrip()
                     for fn in (_edit.add_explode_control, _edit.carry_explode_control)]
    except (OSError, TypeError) as exc:
        raise RuntimeError("the explode control's source could not be read: %s" % exc)
    lines = [
        "# SYNAPSE: explode control. Written by SYNAPSE's add_explode_control tool,",
        "# not by the model. It hands on a copy of the rig with one control added;",
        "# nothing upstream is changed. The slider on this node sets where the",
        "# control rests: 0 is closed, 1 is open.",
        "import apex",
        "import hou",
        "",
        "RIG_FOLDER = %r" % rig_folder,
        "SHAPE_PORT = %r" % shape_port,
        "PARENT = %r" % (parent,),
        "TRAVEL = %r" % travel,
        "HANDLE = %r" % (handle,),
        "ATTRIBUTE = %r" % attribute,
        "SLIDER = %r" % slider,
        "",
        "",
        functions[0],
        "",
        "",
        functions[1],
        "",
        "",
        "node = hou.pwd()",
        "try:",
        "    carry_explode_control(",
        "        node.geometry(), apex, hou, rig_folder=RIG_FOLDER, shape_port=SHAPE_PORT,",
        "        parent=PARENT, travel=TRAVEL, handle=HANDLE, attribute=ATTRIBUTE,",
        "        rest_value=node.evalParm(SLIDER))",
        "except ValueError as problem:",
        "    raise hou.NodeError('SYNAPSE explode control: %s' % problem)",
        "",
    ]
    code = "\n".join(lines)
    for mark in EXPANDED_BY_HOUDINI:
        if mark in code:
            raise RuntimeError(
                "the explode control's code holds %r, which Houdini would expand "
                "before Python runs it" % mark)
    return code


def outcome_line(*, control: str, node_path: str, packer_path: str, rig_folder: str,
                 facts: Dict[str, Any], travel: float, parent_note: str,
                 rewired: int, status: str) -> str:
    """The sentence the tool relays: what it did, in the scene's own names."""
    if status == "unchanged":
        return ("%s already carries the %s control for %s, so nothing was changed."
                % (node_path, control, rig_folder))
    moving = facts.get("points_that_move")
    points = facts.get("points")
    if moving is None or points is None:
        moves = "The asset's own %s attribute sets each point's move" % OFFSET_ATTRIBUTE
    else:
        moves = ("%s of the shape's %s points move, each by the asset's own %s"
                 % (format(moving, ","), format(points, ","), OFFSET_ATTRIBUTE))
    return ("Added the %s control to %s in one new node, %s, after %s (%d "
            "connection%s rewired). %s. Raising the control %s units opens it fully; "
            "the %s slider on the node sets where it rests. %s"
            % (control, rig_folder, node_path, packer_path, rewired,
               "" if rewired == 1 else "s", moves, format(travel, "g"),
               SLIDER, parent_note))
