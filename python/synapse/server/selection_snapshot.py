"""Bounded, read-only selection topology observations.

Call on Houdini's main thread. No geometry, stage, cook, parameter or code
reads occur unless an explicit detail callback is supplied. A pin is an
inspection precondition, never a mutation sandbox or a scene revision lock.
"""

from collections import deque
import hashlib
import json
import os
import re
import sys
from types import ModuleType
import uuid


_ANCHOR = "_synapse_selection_process_identity"


def _session_token():
    # Keep identity outside this module: panel/server reloads must not invalidate
    # a pin. This is process identity, not a claim that the HIP has not changed.
    anchor = sys.modules.setdefault(_ANCHOR, ModuleType(_ANCHOR))
    if getattr(anchor, "pid", None) != os.getpid():
        anchor.pid = os.getpid()
        anchor.token = uuid.uuid4().hex
    return anchor.token


def _read(value, method):
    try:
        fn = getattr(value, method, None)
        return fn() if callable(fn) else None
    except Exception:
        return None


def _text(value):
    return value if isinstance(value, str) and value else None


def _integer(value):
    return value if type(value) is int and value >= 0 else None


def _path(item):
    return _text(_read(item, "path"))


def _sid(item):
    return _integer(_read(item, "sessionId"))


def _invalid(message):
    raise ValueError("SELECTION_INVALID: " + message)


def _stale(message):
    raise ValueError("SELECTION_STALE: " + message)


def _validate(depth, max_nodes, max_edges, include_parameters, include_geometry,
              node_paths, expected_identities, expected_scene, expected_topology_hash):
    for label, value, lo, hi in (("depth", depth, 0, 5),
                                 ("max_nodes", max_nodes, 1, 500),
                                 ("max_edges", max_edges, 1, 5000)):
        if type(value) is not int or not lo <= value <= hi:
            _invalid("%s must be an integer from %d to %d" % (label, lo, hi))
    for label, value in (("include_parameters", include_parameters),
                         ("include_geometry", include_geometry)):
        if type(value) is not bool:
            _invalid(label + " must be a boolean")
    if node_paths is not None:
        if not isinstance(node_paths, list) or len(node_paths) > 500:
            _invalid("node_paths must be a list of at most 500 absolute node paths")
        for path in node_paths:
            if (not isinstance(path, str) or not path.startswith("/") or len(path) > 2048
                    or any(ord(ch) < 32 for ch in path)
                    or any(part in ("", ".", "..") for part in path.split("/")[1:])):
                _invalid("node_paths must contain canonical absolute node paths")
        if len(set(node_paths)) != len(node_paths):
            _invalid("node_paths must not contain duplicates")
    if expected_identities is not None:
        if node_paths is None or not isinstance(expected_identities, list):
            _invalid("expected_identities requires explicit node_paths and a list of identities")
        expected_paths = []
        for identity in expected_identities:
            if (not isinstance(identity, dict) or not isinstance(identity.get("path"), str)
                    or _integer(identity.get("session_id")) is None):
                _invalid("each expected identity needs a path and integer session_id")
            expected_paths.append(identity["path"])
        if len(set(expected_paths)) != len(expected_paths) or set(expected_paths) != set(node_paths):
            _invalid("expected_identities must match node_paths exactly")
    if expected_scene is not None:
        if (node_paths is None or not isinstance(expected_scene, dict)
                or not _text(expected_scene.get("session_token"))
                or not _text(expected_scene.get("hip_path"))):
            _invalid("expected_scene requires explicit paths, session_token and hip_path")
    if expected_topology_hash is not None:
        if (not isinstance(expected_topology_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_topology_hash)
                or node_paths is None or expected_identities is None or expected_scene is None):
            _invalid("expected_topology_hash requires a SHA-256 hash and pinned paths, identities and scene")


class _Scan:
    def __init__(self, max_nodes, max_edges, detail_callbacks):
        self.max_nodes, self.max_edges = max_nodes, max_edges
        # Both duplicate connection observations and dot traversal consume a
        # finite budget. HOM returns connection tuples; their native allocation
        # is outside this Python budget, but we never walk an unbounded tuple.
        self.max_observations = 4 * max_edges + 2 * max_nodes
        self.observations = 0
        self.edges = {}
        self.item_edges = {}
        self.destinations = {}
        self.rows = {}
        self.objects = {}
        self.incoming = {}
        self.outgoing = {}
        self.callbacks = detail_callbacks
        self.warnings = []
        self.complete = True
        self.truncated = False

    def issue(self, message, truncated=False):
        if message not in self.warnings:
            self.warnings.append(message)
        self.complete = False
        self.truncated = self.truncated or truncated

    def identity(self, item):
        path, sid = _path(item), _sid(item)
        if path is None or sid is None:
            self.issue("A connection or node has an unavailable item identity.")
        return path, sid

    def metadata(self, node):
        path, sid = self.identity(node)
        if path in self.rows:
            return self.rows[path]
        typ = _read(node, "type")
        category = _read(typ, "category")
        ports = {"min_inputs": _integer(_read(typ, "minNumInputs")),
                 "max_inputs": _integer(_read(typ, "maxNumInputs")),
                 "max_outputs": _integer(_read(typ, "maxNumOutputs"))}
        for key, method in (("input_names", "inputNames"), ("output_names", "outputNames"),
                            ("input_data_types", "inputDataTypes"), ("output_data_types", "outputDataTypes")):
            value = _read(node, method)
            ports[key] = list(value) if isinstance(value, (tuple, list)) and all(isinstance(v, str) for v in value) else None
        # Names are advertised labels, not a count of available ports: H22 LOP
        # subnets advertise one output name while their type allows ten outputs.
        row = {"path": path, "session_id": sid, "name": _text(_read(node, "name")),
               "type": _text(_read(typ, "name")), "category": _text(_read(category, "name")),
               "parent": _path(_read(node, "parent")), "ports": ports,
               "input_capacity": ports["max_inputs"], "output_capacity": ports["max_outputs"],
               "connections": {"inputs": [], "outputs": []}}
        for name, callback in self.callbacks.items():
            row[name] = callback(node)
        self.rows[path], self.objects[path] = row, node
        return row

    def connections(self, item, direction):
        cache = self.incoming if direction == "input" else self.outgoing
        key = (_path(item), _sid(item))
        if key in cache:
            return cache[key]
        try:
            rows = getattr(item, direction + "Connections")()
            if not isinstance(rows, (tuple, list)):
                raise TypeError("connections are not a sequence")
        except Exception:
            self.issue("Could not observe %s connections for %s." % (direction, key[0] or "an item"))
            rows = ()
        remaining = max(0, self.max_observations - self.observations)
        if len(rows) > remaining:
            self.issue("Connection observation limit reached; remaining wires are unknown.", True)
        rows = rows[:remaining]
        self.observations += len(rows)
        cache[key] = rows
        return rows

    def edge(self, conn):
        source_node = _read(conn, "inputNode")
        target = _read(conn, "outputNode")
        source_item = _read(conn, "inputItem")
        target_item = _read(conn, "outputItem")
        indirect = _read(conn, "subnetIndirectInput")
        if source_node is None:
            source = indirect if indirect is not None else source_item
            kind = "subnet_input" if indirect is not None else "item"
        else:
            source, kind = source_node, "node"
        # Direct wire endpoints fall back only to observed node objects. A dot
        # is never silently replaced with an invented node/port.
        source_item = source_item if source_item is not None else source
        target_item = target_item if target_item is not None else target
        source_path, source_sid = self.identity(source)
        target_path, target_sid = self.identity(target if target is not None else target_item)
        item_path, item_sid = self.identity(source_item)
        target_item_path, target_item_sid = self.identity(target_item)
        output = _integer(_read(conn, "outputIndex"))
        input_index = _integer(_read(conn, "inputIndex"))
        item_output = _integer(_read(conn, "inputItemOutputIndex"))
        if output is None or input_index is None or item_output is None:
            self.issue("A wire has an unavailable port index.")
        edge = {"source": source_path, "source_session_id": source_sid,
                "source_output": output, "source_kind": kind,
                "source_item": item_path, "source_item_session_id": item_sid,
                "source_item_output": item_output,
                "target": target_path, "target_session_id": target_sid,
                "target_input": input_index, "target_item": target_item_path,
                "target_item_session_id": target_item_sid}
        if (item_path, item_sid) != (source_path, source_sid) or source_node is None or target is None:
            physical = {key: edge[key] for key in (
                "source_item", "source_item_session_id", "source_item_output",
                "target_item", "target_item_session_id", "target_input")}
            physical_key = json.dumps(physical, sort_keys=True)
            if physical_key not in self.item_edges:
                if len(self.item_edges) >= self.max_edges:
                    self.issue("Physical wire item limit reached; intermediate items are unknown.", True)
                else:
                    self.item_edges[physical_key] = physical
        return edge, source_node, target

    def retain(self, edge):
        key = (edge["source"], edge["source_session_id"], edge["source_output"],
               edge["target"], edge["target_session_id"], edge["target_input"],
               edge["source_item"], edge["source_item_session_id"], edge["source_item_output"])
        destination = (edge["target"], edge["target_session_id"], edge["target_input"])
        previous = self.destinations.setdefault(destination, key)
        if previous != key:
            self.issue("Connection observations disagree for one destination input; refresh before pinning.")
        if key not in self.edges:
            if len(self.edges) >= self.max_edges:
                self.issue("Wire limit reached; remaining wires are unknown.", True)
                return
            self.edges[key] = edge

    def scan_node(self, node):
        upstream = []
        for conn in self.connections(node, "input"):
            edge, source, _ = self.edge(conn)
            self.retain(edge)
            if source is not None:
                upstream.append(source)
        # A node -> dot connection has outputNode() == None. Follow the dot's
        # outputConnections() to terminal nodes, retaining the terminal wire's
        # physical source item and its logical source output index.
        pending = deque(self.connections(node, "output"))
        visited_items = set()
        while pending:
            conn = pending.popleft()
            edge, _, _ = self.edge(conn)
            target = _read(conn, "outputNode")
            item = _read(conn, "outputItem")
            if target is None and item is not None:
                key = self.identity(item)
                if key in visited_items:
                    self.issue("Repeated non-node wire item; downstream completeness is unknown.")
                    continue
                visited_items.add(key)
                following = self.connections(item, "output")
                if following:
                    pending.extend(following)
                else:
                    self.issue("A wire ends at a non-node item; it is retained as an incomplete boundary.")
                    self.retain(edge)
            else:
                self.retain(edge)
        return upstream


def capture_selection(native, *, depth=0, max_nodes=200, max_edges=2000,
                      include_parameters=False, include_geometry=False,
                      node_paths=None, expected_identities=None, expected_scene=None,
                      expected_topology_hash=None, parameter_reader=None, geometry_reader=None):
    """Capture selection or explicit pinned paths, refusing stale preconditions."""
    _validate(depth, max_nodes, max_edges, include_parameters, include_geometry,
              node_paths, expected_identities, expected_scene, expected_topology_hash)
    if native is None:
        raise ValueError("SELECTION_UNAVAILABLE: Houdini is unavailable")
    scene = {"session_token": _session_token(),
             "hip_path": _text(_read(getattr(native, "hipFile", None), "path")),
             "houdini_version": _text(_read(native, "applicationVersionString"))}
    if expected_scene is not None and any(expected_scene[key] != scene[key] for key in ("session_token", "hip_path")):
        _stale("the Houdini session or HIP path changed; capture the selection again")
    expected = {row["path"]: row["session_id"] for row in expected_identities or []}
    if node_paths is not None:
        selected = []
        for path in node_paths:
            try:
                node = native.node(path)
            except Exception:
                node = None
            if node is None or _path(node) != path:
                _stale("a pinned node is missing or renamed: " + path)
            if path in expected and _sid(node) != expected[path]:
                _stale("a pinned node was replaced: " + path)
            selected.append(node)
    else:
        try:
            selected = native.selectedNodes()
            if not isinstance(selected, (tuple, list)):
                raise TypeError("selection is not a sequence")
        except Exception:
            raise ValueError("SELECTION_UNAVAILABLE: could not observe the current node selection") from None
    callbacks = {}
    if include_parameters:
        callbacks["modified_parms"] = parameter_reader
    if include_geometry:
        callbacks["geometry"] = geometry_reader
    scan = _Scan(max_nodes, max_edges, callbacks)
    selected_count = len(selected)
    chosen = selected[:max_nodes]
    if selected_count > len(chosen):
        scan.issue("Selection node limit reached; omitted selected nodes were not inspected.", True)
    if scene["hip_path"] is None:
        scan.issue("HIP path is unavailable; scene freshness cannot be verified.")
    nodes = [scan.metadata(node) for node in chosen]
    selected_paths = {row["path"] for row in nodes}
    pending = deque()
    for node in chosen:
        upstream = scan.scan_node(node)
        if depth:
            pending.extend((source, 1) for source in upstream)
    traversed = []
    traversal_truncated = False
    traversal_omitted = set()
    processed = set(selected_paths)
    while pending:
        node, level = pending.popleft()
        path = _path(node)
        if path in processed:
            continue
        processed.add(path)
        if len(scan.rows) >= max_nodes:
            traversal_truncated = True
            traversal_omitted.add(path)
            scan.issue("Traversal node limit reached; additional upstream nodes were not inspected.", True)
            continue
        row = scan.metadata(node)
        row["depth"] = level
        traversed.append(row)
        upstream = scan.scan_node(node)
        if level < depth:
            pending.extend((source, level + 1) for source in upstream)
    edges = sorted(scan.edges.values(), key=lambda edge: json.dumps(edge, sort_keys=True))
    wires = {"internal": [], "entering": [], "leaving": []}
    traversal_wires = []
    topology = []
    for edge in edges:
        source, target = edge["source"], edge["target"]
        source_in, target_in = source in selected_paths, target in selected_paths
        if source_in or target_in:
            category = "internal" if source_in and target_in else "entering" if target_in else "leaving"
            wires[category].append(edge)
        else:
            traversal_wires.append(edge)
        if target_in:
            topology.append([source.rsplit("/", 1)[-1] if source else None,
                             target.rsplit("/", 1)[-1], edge["target_input"]])
        if target in scan.rows:
            scan.rows[target]["connections"]["inputs"].append({
                "path": source, "index": edge["target_input"], "output_index": edge["source_output"],
                "source_item": edge["source_item"]})
        if source in scan.rows:
            scan.rows[source]["connections"]["outputs"].append({
                "path": target, "input_index": edge["target_input"], "output_index": edge["source_output"],
                "source_item": edge["source_item"]})
    if depth:
        # Legacy field remains a shallow list. The deduplicated, bounded graph
        # lives in traversal.nodes/wires rather than recursively repeating DAGs.
        for row in nodes:
            paths = {edge["source"] for edge in edges if edge["target"] == row["path"]}
            row["input_graph"] = [dict(path=path, session_id=scan.rows[path]["session_id"],
                                        name=scan.rows[path]["name"], type=scan.rows[path]["type"],
                                        category=scan.rows[path]["category"])
                                  for path in sorted(paths - {None}) if path in scan.rows]
    identities = [{"path": row["path"], "session_id": row["session_id"]} for row in nodes]
    # Optional parameter evaluation can run user expressions. Verify the
    # captured identities after all observations too, without retargeting a
    # replaced node or returning a mixture as a fresh pinned snapshot.
    final_scene = {"session_token": _session_token(),
                   "hip_path": _text(_read(getattr(native, "hipFile", None), "path"))}
    scene_changed = any(final_scene[key] != scene[key] for key in final_scene)
    identity_changed = any(_path(scan.objects[row["path"]]) != row["path"] or
                           _sid(scan.objects[row["path"]]) != row["session_id"]
                           for row in nodes + traversed)
    if expected:
        for path, sid in expected.items():
            try:
                current = native.node(path)
            except Exception:
                current = None
            identity_changed = identity_changed or _path(current) != path or _sid(current) != sid
    if scene_changed or identity_changed:
        if node_paths is not None:
            _stale("node identities or scene changed during inspection; capture the scope again")
        scan.issue("Node identities or scene changed during inspection; capture the selection again.")
    item_wires = [scan.item_edges[key] for key in sorted(scan.item_edges)]
    # Params/geometry and live selection order are deliberately outside the
    # topology precondition. Boundary item identity and exact ports are inside.
    hash_payload = {"scene": scene, "depth": depth,
                    "nodes": sorted([{"path": row["path"], "session_id": row["session_id"],
                                      "parent": row["parent"], "type": row["type"], "category": row["category"],
                                      "ports": row["ports"]}
                                     for row in nodes + traversed], key=lambda row: row["path"] or ""),
                    "selected": sorted(selected_paths - {None}), "wires": edges, "item_wires": item_wires}
    topology_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if expected_topology_hash is not None and (not scan.complete or topology_hash != expected_topology_hash):
        _stale("wiring changed or could not be fully observed; refresh the pinned selection before preparing an action")
    return {"schema": "synapse-selection-v1", "selection_source": "pinned" if node_paths is not None else "live",
            "count": len(nodes), "nodes": nodes, "topology": topology,
            "selected_count": selected_count, "observed_count": len(nodes),
            "omitted_count": selected_count - len(nodes), "truncated": scan.truncated,
            "complete": scan.complete, "can_pin": bool(nodes) and scan.complete,
            "identities": identities, "scene": scene, "topology_hash": topology_hash,
            "wires": wires, "wire_scope": "observed_selection",
            "item_wires": item_wires, "item_wire_count": len(item_wires),
            "edge_count": len(edges), "omitted_edge_count": None if not scan.complete else 0,
            "traversal": {"depth": depth, "nodes": traversed, "wires": traversal_wires,
                          "observed_count": len(traversed), "truncated": traversal_truncated,
                          "omitted_count": None if depth and not scan.complete else 0,
                          "known_omitted_count": len(traversal_omitted)},
            "limits": {"max_nodes": max_nodes, "max_edges": max_edges, "depth": depth,
                       "node_ceiling": 500, "edge_ceiling": 5000, "depth_ceiling": 5,
                       "max_connection_observations": scan.max_observations,
                       "max_item_wires": max_edges},
            "connection_observation_count": scan.observations,
            "details": {"parameters": include_parameters, "geometry": include_geometry},
            "warnings": scan.warnings}
