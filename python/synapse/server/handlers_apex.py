"""python/synapse/server/handlers_apex.py -- ``synapse_add_explode_control``.

One build. SYNAPSE adds one control, ``explode``, to an existing APEX rig:
it writes one Python SOP after the node that packs the character, wires that
node's consumers to the new one, and reads the result back. One undo step.

Scope. This is the one tool that reaches into a rig, by a recorded exception
to boundary rule D-H22-3 (docs/SYNAPSE_H22_BOUNDARY.md, section 6: Joe
Ibrahim, 2026-11-27). It adds a control to a rig that already exists. It
builds no rig, no skeleton and no skinning, and it does not edit the packed
rig upstream: the new node hands on an edited copy.

What the caller may pass: the node, and how far the handle travels. No code,
no node names and no directions. The directions are the asset's own (a
per-point ``explode_offset`` attribute on the rest shape), and the tool
refuses an asset that has none.

Two layers, split so the build is testable with no Houdini present
(tests/test_apex_explode_tool.py), the same way ``handlers_cache`` is:

  * ``add_explode_control_core`` -- the build. Takes an already-resolved node
    (a real ``hou.OpNode`` or a stand-in) and the three things only Houdini
    can supply: a geometry reader that will not force a cook, a function that
    adds the slider, and an undo-group factory. Imports no ``hou``.
  * ``ApexHandlerMixin._handle_add_explode_control`` -- resolves the node from
    the payload and runs the core in one main-thread visit.

Take-back. Everything the build changes sits in one undo group. A build that
does not end with the control readable in the new node's output is taken back
out by hand before the error is raised: the consumers are wired to the packer
again and the node is destroyed. ``performUndo`` is not relied on, because
under the panel bridge's outer group this group has not reached the undo
stack yet (the same reason ``handlers_spatial`` withdraws its trail by hand).

Symbol provenance: every ``hou`` member used here and in the generated code
(``OpNode.createNode``/``setInput``/``outputConnections``/``addSpareParmTuple``/
``setUserData``/``userData``/``needsToCook``/``destroy``, ``FloatParmTemplate``,
``PackedGeometry.setEmbeddedGeometry``, ``NodeError``, ``hmath.buildTranslate``,
``undos.group``) is on the committed h22_symbol_table.json (22.0.400), and the
whole path was run on hython 22.0.466.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import hou  # type: ignore

    HOU_AVAILABLE = True
except ImportError:  # pragma: no cover -- exercised in the no-hou test environment
    hou = None  # type: ignore[assignment]
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param
from ..core.errors import HoudiniUnavailableError, NodeNotFoundError, SynapseUserError
from . import apex_explode as _plan
from . import apex_graph
from .handler_helpers import undo_receipt

logger = logging.getLogger(__name__)

UNDO_LABEL = _plan.UNDO_LABEL
_NAME_TRIES = 64


def _carrier_downstream(packer: Any) -> Optional[Any]:
    """This tool's own node among *packer*'s consumers, if an earlier call made one."""
    try:
        connections = list(packer.outputConnections())
    except Exception:
        logger.debug("output connections unavailable", exc_info=True)
        return None
    for connection in connections:
        try:
            consumer = connection.outputNode()
            if consumer.userData(_plan.MARKER_KEY) == _plan.MARKER_VALUE:
                return consumer
        except Exception:
            logger.debug("consumer unreadable", exc_info=True)
    return None


def _free_name(parent: Any, base: str) -> str:
    name, n = base, 1
    while parent.node(name) is not None:
        n += 1
        if n > _NAME_TRIES:
            raise SynapseUserError(
                "No control added: %s already holds %d nodes named like %s."
                % (parent.path(), _NAME_TRIES, base))
        name = "%s%d" % (base, n)
    return name


def _rig_read(geo: Any, rig_folder: str) -> Optional[Dict[str, Any]]:
    """The named rig as *geo* holds it, read with ``apex_graph``, or None."""
    if geo is None:
        return None
    for character in _plan.characters_in(geo):
        if character["rig_folder"] == rig_folder:
            return apex_graph.read_graph(character["rig"])
    return None


def _counts(graph: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not graph:
        return None
    return {key: graph.get(key) for key in
            ("node_count", "wire_count", "control_count",
             "graph_input_count", "graph_output_count")}


def add_explode_control_core(
    node: Any,
    *,
    read_geometry: Callable[[Any], Any],
    add_slider: Callable[[Any], None],
    undo_context_factory: Callable[[], Any],
    travel: Any = None,
) -> Dict[str, Any]:
    """Add the explode control to the rig *node* shows or is fed by.

    node                  the rig's node, or any node downstream of it
    read_geometry         node -> its geometry, or None when it would have to cook
    add_slider            adds the 0-to-1 ``explode`` parameter to the new node
    undo_context_factory  () -> a context manager that groups the build's undo
    travel                how far up the handle goes for a full explode, in
                          scene units; None sizes it from the asset

    Returns a plain-JSON result. Raises ``SynapseUserError`` with the reason,
    having changed nothing, when the rig is not one it can add the control to.
    """
    start_path = node.path()
    found = _plan.find_packer(node, read_geometry)
    packer = found["node"]
    if packer is None:
        if found["unread"]:
            raise SynapseUserError(
                "No control added: no APEX character was read at or above %s, and "
                "%d node(s) there are not cooked (%s). SYNAPSE does not force a cook."
                % (start_path, len(found["unread"]), ", ".join(found["unread"][:3])),
                suggestion="Display the rig's node so it cooks, then ask again.")
        raise SynapseUserError(
            "No control added: no APEX character at or above %s. The tool needs a "
            "packed character: a .rig folder with an APEX graph and a .shp folder "
            "beside it." % start_path,
            suggestion="Pass the node that packs the character, or a node below it.")
    characters = found["characters"]
    if len(characters) != 1:
        raise SynapseUserError(
            "No control added: %s packs %d characters (%s), and the tool adds the "
            "control to one." % (packer.path(), len(characters),
                                 ", ".join(c["name"] for c in characters[:4])))
    character = characters[0]
    rig_folder, shape_folder = character["rig_folder"], character["shape_folder"]
    packer_path = packer.path()

    existing = _carrier_downstream(packer)
    if existing is not None:
        graph = _rig_read(read_geometry(existing), rig_folder)
        result: Dict[str, Any] = {
            "status": "unchanged",
            "node": existing.path(),
            "character_node": packer_path,
            "rig": rig_folder,
            "control": _plan.CONTROL,
            "slider": existing.path() + "/" + _plan.SLIDER,
            "after": _counts(graph),
            "control_listed": (_plan.CONTROL in graph["controls"]) if graph else None,
        }
        result["outcome"] = _plan.outcome_line(
            control=_plan.CONTROL, node_path=existing.path(), packer_path=packer_path,
            rig_folder=rig_folder, facts={}, travel=0.0, parent_note="", rewired=0,
            status="unchanged")
        return result

    graph = apex_graph.read_graph(character["rig"], include_nodes=True, include_wires=True)
    plan = _plan.plan_edit(graph, shape_folder)
    facts = _plan.shape_facts(character["shape"])
    travel, handle = _plan.sizes(facts, travel)
    code = _plan.node_code(rig_folder=rig_folder, shape_port=shape_folder,
                           parent=plan["parent"], travel=travel, handle=handle)

    # Who reads the packer's first output now: each is handed the new node instead.
    consumers: List[Tuple[Any, int]] = []
    for connection in packer.outputConnections():
        if connection.outputIndex() != 0:
            continue
        consumers.append((connection.outputNode(), connection.inputIndex()))
    parent = packer.parent()
    name = _free_name(parent, _plan.CARRIER_NAME)

    def withdraw(carrier: Any) -> None:
        """Put the wires back and take the node out. Never raises: the caller is
        about to raise the error that matters."""
        try:
            for consumer, index in consumers:
                consumer.setInput(index, packer, 0)
            if carrier is not None:
                carrier.destroy()
        except Exception as exc:  # noqa: BLE001 -- the original error is the one to report
            logger.warning("add_explode_control: could not take %s back out of %s: %s",
                           name, parent.path(), exc)

    with undo_context_factory():
        carrier = None
        try:
            carrier = parent.createNode("python", name)
            add_slider(carrier)
            carrier.parm("python").set(code)
            carrier.setUserData(_plan.MARKER_KEY, _plan.MARKER_VALUE)
            carrier.setComment("SYNAPSE: explode control")
            carrier.setInput(0, packer, 0)
            for consumer, index in consumers:
                consumer.setInput(index, carrier, 0)
            carrier.moveToGoodPosition()

            # Read it back. The packer is cooked, so this cooks the new node alone.
            try:
                built = carrier.geometry()
            except Exception:
                logger.debug("the new node's geometry could not be read", exc_info=True)
                built = None
            after = _rig_read(built, rig_folder)
            errors = [str(e) for e in carrier.errors()]
            problem = None
            if errors:
                problem = "%s reported an error: %s" % (carrier.path(), "; ".join(errors[:2]))
            elif after is None or not after.get("read"):
                problem = "%s is not readable in %s's output" % (rig_folder, carrier.path())
            elif _plan.CONTROL not in after["controls"]:
                problem = "the %s control is not in the rig %s hands on" % (
                    _plan.CONTROL, carrier.path())
            elif after["node_count"] != plan["before"]["node_count"] + len(_plan.ADDED_NODES):
                problem = ("the rig has %d nodes where %d were expected"
                           % (after["node_count"],
                              plan["before"]["node_count"] + len(_plan.ADDED_NODES)))
            if problem:
                raise SynapseUserError(
                    "The control was not added: " + problem,
                    suggestion="The network was left as it was.")
            carrier_path = carrier.path()
        except SynapseUserError:
            withdraw(carrier)
            raise
        except Exception as exc:
            withdraw(carrier)
            raise SynapseUserError(
                "The control was not added: %s" % exc,
                suggestion="The network was left as it was.")

    result = {
        "status": "created",
        "node": carrier_path,
        "character_node": packer_path,
        "asked_at": start_path,
        "rig": rig_folder,
        "control": _plan.CONTROL,
        "control_follows": plan["parent"],
        "slider": carrier_path + "/" + _plan.SLIDER,
        "travel": travel,
        "handle": list(handle),
        "offset_attribute": _plan.OFFSET_ATTRIBUTE,
        "points": facts["points"],
        "points_that_move": facts["points_that_move"],
        "largest_move": facts["largest_move"],
        "rewired": [{"node": consumer.path(), "input": index} for consumer, index in consumers],
        "before": plan["before"],
        "after": _counts(after),
        "added_nodes": list(_plan.ADDED_NODES),
        "decision": "add_explode_control",
        "reasoning": (
            "The control goes in after %s because that is where the character is "
            "first packed, so every node reading it gets the control. The packed "
            "rig upstream is unchanged; the new node hands on an edited copy. "
            "Each point's direction and distance come from the asset's own %s "
            "attribute, not from SYNAPSE."
            % (packer_path, _plan.OFFSET_ATTRIBUTE)),
    }
    result["outcome"] = _plan.outcome_line(
        control=_plan.CONTROL, node_path=carrier_path, packer_path=packer_path,
        rig_folder=rig_folder, facts=facts, travel=travel,
        parent_note=plan["parent_note"], rewired=len(consumers), status="created")
    # A build that fails is taken back out above, so the receipt says so.
    result.update(undo_receipt(UNDO_LABEL, rolls_back_on_failure=True))
    return result


class ApexHandlerMixin:
    """add_explode_control (one build)."""

    def _handle_add_explode_control(self, payload: Dict) -> Dict:
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        node_path = resolve_param(payload, "node")
        travel = payload.get("travel")

        from .introspection import _clean_geometry
        from .main_thread import run_on_main, _SLOW_TIMEOUT

        def _add_slider(carrier):
            carrier.addSpareParmTuple(hou.FloatParmTemplate(  # type: ignore[union-attr]
                _plan.SLIDER, "Explode", 1, default_value=(0.0,), min=0.0, max=1.0,
                min_is_strict=True, max_is_strict=True))

        # One main-thread visit: find the character, build, read back.
        def _on_main():
            node = hou.node(node_path)  # type: ignore[union-attr]
            if node is None:
                raise NodeNotFoundError(str(node_path))
            return add_explode_control_core(
                node,
                read_geometry=lambda n: _clean_geometry(n)[0],
                add_slider=_add_slider,
                undo_context_factory=lambda: hou.undos.group(UNDO_LABEL),  # type: ignore[union-attr]
                travel=travel,
            )

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT,
                           label="apex:add_explode_control")
