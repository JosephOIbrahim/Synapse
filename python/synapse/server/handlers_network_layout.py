"""Main-thread, undo-grouped visual changes to explicitly named existing nodes.

No createNode, setName, parm writes, wiring or output flag mutations. H22 API
and undo behavior are exercised by scripts/probe_network_layout.py.
"""
from __future__ import annotations

import json

try:
    import hou
except ImportError:
    hou = None

from ..core.errors import HoudiniUnavailableError, NodeNotFoundError, SynapseUserError
from .main_thread import run_on_main, _SLOW_TIMEOUT
from .network_layout import METADATA_KEY, layout_summary, plan_layout, validate_request


def _read_metadata(parent):
    raw = parent.userData(METADATA_KEY)
    if not raw:
        return {"boxes": {}, "labels": {}}
    try:
        data = json.loads(raw)
        if (not isinstance(data, dict) or set(data) != {"boxes", "labels"}
                or any(not isinstance(data[k], dict) for k in data)
                or any(not isinstance(v, str) for values in data.values() for v in values.values())):
            raise ValueError("invalid metadata shape")
        return data
    except (TypeError, ValueError) as error:
        raise SynapseUserError("Network layout ownership metadata is invalid; no nodes were changed") from error


def _with_label(comment, previous, label):
    # Remove only the exact annotation we previously added. Artist text, even
    # text edited after the last layout, is retained.
    if previous and (comment == previous or comment.endswith("\n\n" + previous)):
        comment = comment[:-len(previous)].removesuffix("\n\n")
    annotation = "SYNAPSE · " + label
    return (comment + "\n\n" if comment else "") + annotation, annotation


def _same_color(observed, requested):
    # Houdini stores node/box colors as floats (e.g. 0.32 -> 0.3199999928).
    # Exact Python-double comparison otherwise writes every color on a retry.
    return all(abs(a - b) <= 1e-6 for a, b in zip(observed, requested))


def apply_layout(native, settings):
    """Called only on the host main thread (or an isolated native probe)."""
    parent = native.node(settings["parent"])
    if parent is None:
        raise NodeNotFoundError(settings["parent"])
    if not parent.isNetwork() or not parent.isEditable():
        raise SynapseUserError("The target network is not editable")
    nodes = {}
    for path in settings["nodes"]:
        node = native.node(path)
        if node is None:
            raise NodeNotFoundError(path)
        if node.parent() != parent:
            raise SynapseUserError("Each selected node must be a direct child of the target network")
        nodes[path] = node
    metadata = _read_metadata(parent)
    boxes = {box.name(): box for box in parent.networkBoxes()}
    owned = {name for name, comment in metadata["boxes"].items()
             if name in boxes and boxes[name].comment() == comment}
    replace = set(settings["replace_boxes"])
    for name in replace:
        if name not in boxes:
            raise SynapseUserError(f"Network box '{name}' was not found")
        if any(item not in nodes.values() for item in boxes[name].items()):
            raise SynapseUserError(f"Box '{name}' includes items outside the selected nodes; it cannot be replaced")
    descriptors = [{"path": p, "type": n.type().name(), "description": n.type().description()}
                   for p, n in nodes.items()]
    connections = []
    for path, node in nodes.items():
        for connection in node.inputConnections():
            source = connection.inputNode()
            if source is not None and source.path() in nodes:
                connections.append({"from": source.path(), "to": path,
                                    "input": connection.inputIndex()})
    origin = (min(n.position()[0] for n in nodes.values()), max(n.position()[1] for n in nodes.values()))
    plan = plan_layout(settings, descriptors, connections, origin)
    for section in plan["sections"]:
        name = section["box_name"]
        if name in boxes and name not in owned and name not in replace:
            raise SynapseUserError(f"Box '{name}' is not owned by this layout tool; it was preserved")
        if name in boxes and any(item not in nodes.values() for item in boxes[name].items()):
            raise SynapseUserError(f"Box '{name}' now contains unselected items; include them before regrouping")
    affected = {box.name(): box for node in nodes.values()
                if (box := node.parentNetworkBox()) is not None}
    if plan["sections"]:
        for name, box in affected.items():
            if name not in owned and any(item not in nodes.values() for item in box.items()):
                raise SynapseUserError(
                    f"Artist box '{name}' includes unselected items. Select its full contents before regrouping")
    result = {"status": "planned", "parent": parent.path(), **plan,
              "nodes": list(nodes), "dry_run": settings["dry_run"],
              "undo_label": "SYNAPSE: " + layout_summary(settings),
              "retained_boxes": sorted(set(affected) - owned - replace),
              "mutation_scope": ["position", "color", "comment", "display_comment", "network_box", "layout_metadata"]}
    if settings["dry_run"]:
        return result
    if not native.undos.areEnabled():
        raise SynapseUserError("Undo is disabled; reversible network organization is unavailable")
    changed_nodes, changed_boxes, metadata_changed = set(), set(), False
    with native.undos.group(result["undo_label"]):
        for name in replace:
            boxes[name].destroy(destroy_contents=False)
            changed_boxes.add(name)
            boxes.pop(name)
            affected.pop(name, None)
            metadata["boxes"].pop(name, None)
        for path, position in plan["positions"].items():
            node = nodes[path]
            if tuple(node.position()) != tuple(position):
                node.setPosition(native.Vector2(position))
                changed_nodes.add(path)
        for path, label in plan["labels"].items():
            node = nodes[path]
            comment, annotation = _with_label(node.comment(), metadata["labels"].get(path), label)
            if node.comment() != comment:
                node.setComment(comment)
                changed_nodes.add(path)
            if not node.isGenericFlagSet(native.nodeFlag.DisplayComment):
                node.setGenericFlag(native.nodeFlag.DisplayComment, True)
                changed_nodes.add(path)
            metadata["labels"][path] = annotation
        for section in plan["sections"]:
            name = section["box_name"]
            box = boxes.get(name)
            if box is None:
                box = parent.createNetworkBox(name)
                boxes[name] = box
                changed_boxes.add(name)
            comment = section["label"]
            if box.comment() != comment:
                box.setComment(comment)
                changed_boxes.add(name)
            color = tuple(section["color"])
            if not _same_color(box.color().rgb(), color):
                box.setColor(native.Color(color))
                changed_boxes.add(name)
            for path in section["nodes"]:
                node = nodes[path]
                if node.parentNetworkBox() != box:
                    box.addItem(node)
                    changed_boxes.add(name)
                if not _same_color(node.color().rgb(), color):
                    node.setColor(native.Color(color))
                    changed_nodes.add(path)
            metadata["boxes"][name] = comment
            affected[name] = box
        for name, box in affected.items():
            if name in owned and not box.items():
                box.destroy(destroy_contents=False)
                metadata["boxes"].pop(name, None)
                changed_boxes.add(name)
            elif box.items() and (changed_nodes or changed_boxes):
                before = (tuple(box.position()), tuple(box.size()))
                box.fitAroundContents()
                if (tuple(box.position()), tuple(box.size())) != before:
                    changed_boxes.add(name)
        encoded = json.dumps(metadata, sort_keys=True)
        if (plan["labels"] or plan["sections"] or replace) and parent.userData(METADATA_KEY) != encoded:
            parent.setUserData(METADATA_KEY, encoded)
            metadata_changed = True
    result.update(status="updated" if changed_nodes or changed_boxes or metadata_changed else "unchanged",
                  changed_nodes=sorted(changed_nodes), changed_boxes=sorted(changed_boxes),
                  metadata_changed=metadata_changed)
    return result


class NetworkLayoutMixin:
    def _handle_layout_network(self, payload):
        if hou is None:
            raise HoudiniUnavailableError()
        try:
            settings = validate_request(payload)
        except ValueError as error:
            raise SynapseUserError(str(error)) from error
        return run_on_main(lambda: apply_layout(hou, settings), timeout=_SLOW_TIMEOUT,
                           label="network_layout:apply")
