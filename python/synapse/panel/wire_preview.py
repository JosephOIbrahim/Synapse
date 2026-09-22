"""Pure, read-only insertion proposals from bounded inspection facts.

There is intentionally no apply operation here. A proposal records the scene,
identities and topology it came from, but does not establish that an operation
would be valid after another edit or through an unobserved external path.
"""
from __future__ import annotations

import copy
import re


_EDGE_FIELDS = ("source", "source_output", "target", "target_input")


def _edge_key(edge):
    return tuple(edge.get(key) for key in _EDGE_FIELDS)


def _edge(source, output, target, input_):
    return dict(zip(_EDGE_FIELDS, (source, output, target, input_)))


def _check_port(node, index, field):
    capacity = node.get(field + "_capacity")
    if type(capacity) is not int or capacity < 1:
        raise ValueError("The " + field + " port capacity is unknown or empty. Inspect a supported node first.")
    if type(index) is not int or not 0 <= index < capacity:
        raise ValueError("The " + field + " port is outside the observed capacity for " + node["path"] + ".")


def _reaches(edges, start, end):
    adjacency = {}
    for item in edges:
        adjacency.setdefault(item["source"], set()).add(item["target"])
    pending, seen = [start], set()
    while pending:
        current = pending.pop()
        if current == end:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(adjacency.get(current, ()))
    return False


def build_insertion_preview(snapshot, wire, via_path, *, input_index=0, output_index=0):
    """Return a detached two-edge proposal, or an actionable ``ValueError``.

    Only direct wires between three observed nodes in one network/context are
    supported. Missing ports, incomplete scans, overwritten inputs and observed
    cycles refuse the proposal. Unobserved cycles and operator semantics remain
    explicitly unknown. Port indices are zero-based, as in Houdini.
    """
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "synapse-selection-v1":
        raise ValueError("Refresh the selection to obtain a supported snapshot.")
    if (snapshot.get("truncated") is not False or snapshot.get("warnings")
            or snapshot.get("complete") is not True or snapshot.get("can_pin") is not True):
        raise ValueError("A complete wire scan is needed for an insertion proposal. Narrow the selection and refresh.")
    topology_hash = snapshot.get("topology_hash")
    if (not isinstance(topology_hash, str) or re.fullmatch(r"[0-9a-f]{64}", topology_hash) is None
            or not isinstance(snapshot.get("scene"), dict)):
        raise ValueError("Refresh the selection to obtain snapshot preconditions.")
    if any(not isinstance(snapshot["scene"].get(key), str) or not snapshot["scene"][key]
           for key in ("session_token", "hip_path")):
        raise ValueError("Refresh the selection to obtain scene snapshot preconditions.")
    if not isinstance(wire, dict):
        raise ValueError("Choose an observed wire first.")
    try:
        wires = snapshot["wires"]
        observed = [item for group in ("internal", "entering", "leaving") for item in wires[group]]
        original = next(item for item in observed if _edge_key(item) == _edge_key(wire))
    except (KeyError, TypeError, StopIteration):
        raise ValueError("That wire was not observed in this scan. Refresh the selection.") from None
    for side in ("source", "target"):
        item = original.get(side + "_item")
        if item is not None and item != original[side]:
            raise ValueError("Choose a direct node-to-node wire; indirect inputs and network dots need separate inspection.")
    paths = (original["source"], original["target"], via_path)
    if len(set(paths)) != 3:
        raise ValueError("Choose an intermediate node different from both wire endpoints.")
    nodes = {node["path"]: node for node in snapshot.get("nodes", ())}
    if any(path not in nodes for path in paths):
        raise ValueError("Select both wire endpoints and the intermediate node, then refresh.")
    source, target, middle = (nodes[path] for path in paths)
    parents = {node.get("parent") for node in (source, target, middle)}
    if len(parents) != 1 or not next(iter(parents)):
        raise ValueError("All three nodes must belong to the same observed network.")
    categories = {node.get("category") for node in (source, target, middle)}
    if len(categories) != 1 or not next(iter(categories)):
        raise ValueError("All three nodes must use the same observed node context.")
    identities = snapshot.get("identities", ())
    known_ids = {item.get("path"): item.get("session_id") for item in identities}
    if any(type(known_ids.get(path)) is not int or known_ids[path] != nodes[path].get("session_id") for path in paths):
        raise ValueError("A node identity is missing. Refresh before preparing a proposal.")
    _check_port(source, original["source_output"], "output")
    _check_port(target, original["target_input"], "input")
    _check_port(middle, input_index, "input")
    _check_port(middle, output_index, "output")
    if any(item["target"] == via_path and item["target_input"] == input_index for item in observed):
        raise ValueError("That intermediate input is occupied. Choose an unused input port.")
    after = [_edge(source["path"], original["source_output"], via_path, input_index),
             _edge(via_path, output_index, target["path"], original["target_input"])]
    remaining = [item for item in observed if _edge_key(item) != _edge_key(original)]
    for added in after:
        if _reaches(remaining, added["target"], added["source"]):
            raise ValueError("The proposed insertion creates a cycle in the observed wiring.")
        remaining.append(added)
    return {
        "status": "proposal", "can_apply": False,
        "before": _edge(*_edge_key(original)), "after": after,
        "preconditions": {
            "expected_scene": copy.deepcopy(snapshot["scene"]),
            "expected_identities": copy.deepcopy(identities),
            "expected_topology_hash": snapshot["topology_hash"],
        },
        "observed_checks": ["Original source and destination ports preserved",
                            "Intermediate input unoccupied", "One network and node context",
                            "No cycle introduced within the observed wires"],
        "limitations": ["Paths outside this selection may contain unobserved cycles.",
                        "Operator semantics and data-type compatibility have not been verified.",
                        "Refresh and revalidate identities, scene, and ports before any edit."],
    }


def format_insertion_preview(proposal):
    """Plain-text output for the local preview view; never executable code."""
    def line(item):
        return (f"{item['source']} [out {item['source_output']}] → "
                f"{item['target']} [in {item['target_input']}]")
    return "\n".join([
        "Insertion proposal · ports are zero-based",
        "No connections have been changed.", "", "Before", line(proposal["before"]),
        "", "After", *(line(item) for item in proposal["after"]),
        "", *proposal["limitations"],
    ])
