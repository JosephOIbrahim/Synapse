"""Resolve a Solaris graph and its ports before any scene mutation.

Called only on Houdini's main thread. The same plan feeds preview and execution.
Connection identity follows host.graph_builder: source node and output index.
"""
import json
from functools import lru_cache
from pathlib import Path

from ..core.errors import SynapseUserError


@lru_cache(maxsize=2)
def _ordered_inputs_catalog(version):
    """Measured boundaries, only when the bundled catalog matches this build."""
    try:
        path = Path(__file__).resolve().parents[1] / "cognitive/tools/data" / ("connectivity_" + version.split(".")[0] + ".json")
        catalog = json.loads(path.read_text(encoding="utf-8"))
        return catalog["entries"] if catalog.get("houdini_version") == version else {}
    except (OSError, ValueError, KeyError):
        return {}


def _check_unordered_gaps(bindings, node_types, occupied, hou):
    for nid, slots in occupied.items():
        if not slots or not node_types[nid].hasUnorderedInputs():
            continue
        maximum = max(slots)
        if set(slots) == set(range(maximum + 1)):
            continue
        node = bindings[nid]
        if node is not None:
            boundary = node.numOrderedInputs()
        else:
            key = node_types[nid].category().name() + "/" + node_types[nid].name()
            boundary = _ordered_inputs_catalog(hou.applicationVersionString()).get(key, {}).get("num_ordered_inputs")
        if type(boundary) is not int:
            raise SynapseUserError("Cannot verify input gaps for %s on this Houdini build" % nid,
                                   suggestion="Use contiguous inputs or refresh the live connectivity catalog. Nothing was changed.")
        if {index for index in slots if index >= boundary} != set(range(boundary, maximum + 1)):
            raise SynapseUserError("Unordered inputs on %s cannot contain gaps" % nid,
                                   suggestion="Houdini compacts these ports. Use consecutive input indices. Nothing was changed.")


def _reject_live_cycles(bindings, paths, planned, hou):
    """Include live, unrequested edges when checking the final dependency graph."""
    nodes = {paths[nid]: node for nid, node in bindings.items()}
    final_inputs = {}
    for link in planned:
        target = link["to"]
        if target not in final_inputs:
            node = nodes[target]
            final_inputs[target] = observed_inputs(node) if node is not None else {}
        final_inputs[target][link["input"]] = (link["from"], link["output"])

    def upstream(path):
        if path not in final_inputs:
            node = nodes.get(path) if path in nodes else hou.node(path)
            final_inputs[path] = observed_inputs(node) if node is not None else {}
        return [source for source, _output in final_inputs[path].values()]

    for link in planned:
        pending, visited = [link["from"]], set()
        while pending:
            path = pending.pop()
            if path == link["to"]:
                raise SynapseUserError("Requested connection would create a cycle through %s" % path,
                                       suggestion="Inspect the existing upstream chain. Nothing was changed.")
            if path not in visited:
                visited.add(path)
                pending.extend(upstream(path))


def observed_inputs(node):
    """Read occupied input slots; an unavailable source is not an empty slot."""
    result = {}
    for connection in node.inputConnections():
        source = connection.inputNode()
        if source is None:
            # A subnet input is a real occupied boundary, not a missing wire.
            source = connection.subnetIndirectInput()
        if source is None:
            raise SynapseUserError(
                "Cannot resolve an existing input on %s" % node.path(),
                suggestion="Inspect the indirect connection before changing this network.")
        result[connection.inputIndex()] = (source.path(), connection.outputIndex())
    return result


def resolve_plan(parent, node_map, sorted_ids, connections, hou, resolve_existing):
    """Return resolved bindings, paths, and an ordered, unambiguous wire plan."""
    bindings, paths, node_types = {}, {}, {}
    claimed_paths = set()
    for nid in sorted_ids:
        spec = node_map[nid]
        name = spec.get("name") or nid
        node = (resolve_existing(parent, spec) if spec.get("existing") else parent.node(name))
        if node is not None:
            if node.parent() != parent:
                raise SynapseUserError("Node %s is outside %s" % (node.path(), parent.path()),
                                       suggestion="Build connections within one network.")
            node_type = node.type()
            if not spec.get("existing"):
                wanted = hou.preferredNodeType(parent.childTypeCategory().name() + "/" + spec["type"], parent)
                if node_type != wanted:
                    raise SynapseUserError("Node %s already has a different type" % node.path(),
                                           suggestion="Choose a distinct node name. Nothing was changed.")
            path = node.path()
        else:
            node_type = hou.preferredNodeType(parent.childTypeCategory().name() + "/" + spec["type"], parent)
            path = parent.path().rstrip("/") + "/" + name
        if path in claimed_paths:
            raise SynapseUserError("Multiple graph IDs resolve to %s" % path,
                                   suggestion="Use one graph ID per node. Nothing was changed.")
        claimed_paths.add(path)
        bindings[nid], paths[nid], node_types[nid] = node, path, node_type

    occupied, reserved = {}, {}
    for conn in connections:
        target = conn["to"]
        if target not in occupied:
            node = bindings[target]
            occupied[target] = observed_inputs(node) if node is not None else {}
        if "input" in conn or not node_map[target].get("existing"):
            reserved.setdefault(target, set()).add(conn.get("input", 0))

    planned, claimed = [], set()
    for conn in connections:
        source, target = conn["from"], conn["to"]
        output = conn.get("output", 0)
        desired = (paths[source], output)
        slots = occupied[target]
        protected = bool(node_map[target].get("existing"))
        if protected and "input" not in conn:
            # Reserve explicit slots first, so input order in the JSON cannot
            # make an implicit append steal a later explicit destination.
            matching = [index for index, value in slots.items() if value == desired]
            if matching:
                index = min(matching)
            else:
                index = 0
                while index in slots or index in reserved.get(target, set()):
                    index += 1
        else:
            index = conn.get("input", 0)
        if index >= node_types[target].maxNumInputs() or output >= node_types[source].maxNumOutputs():
            raise SynapseUserError("Connection %s[%d] -> %s[%d] exceeds the live node's port count"
                                   % (paths[source], output, paths[target], index),
                                   suggestion="Inspect the node's available ports. Nothing was changed.")
        key = (target, index)
        if key in claimed:
            raise SynapseUserError("Multiple connections claim %s input %d" % (paths[target], index),
                                   suggestion="Give each requested wire a distinct input. Nothing was changed.")
        prior = slots.get(index)
        if prior is not None and (prior[0] != desired[0] or (protected and prior != desired)):
            raise SynapseUserError("Input %d of %s is already connected to %s output %d"
                                   % (index, paths[target], prior[0], prior[1]),
                                   suggestion="Choose an unused input or omit input to append to an existing node. Nothing was changed.")
        claimed.add(key)
        slots[index] = desired
        planned.append({"from_id": source, "to_id": target, "from": paths[source],
                        "to": paths[target], "input": index, "output": output,
                        "changed": prior != desired})
    _check_unordered_gaps(bindings, node_types, occupied, hou)
    _reject_live_cycles(bindings, paths, planned, hou)
    return {"bindings": bindings, "paths": paths, "connections": planned}


def observed_display(parent):
    """Report the actual display flag, or unknown if the host cannot read it."""
    try:
        nodes = parent.children()
        readable = [node for node in nodes if callable(getattr(node, "isDisplayFlagSet", None))]
        if nodes and not readable:
            return None, False
        return next((node.path() for node in readable if node.isDisplayFlagSet()), None), True
    except Exception:
        return None, False
