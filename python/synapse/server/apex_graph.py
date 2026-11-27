"""APEX graph geometry reader -- observation only.

Houdini stores an APEX graph as geometry, and a rigged character as a
geometry of packed folders. This module reads both and returns plain dicts.

Layout, measured on Houdini 22.0.466 (OVOID rig, 2026-11-27):

  graph geometry
    one point per graph node    name:String  callback:String  tags:String[]
                                parms:Dict   properties:Dict
    one primitive per wire      two vertices; vertex 0 is the source (an
                                output port), vertex 1 the destination (an
                                input port)
    one vertex per port end     portname:String  portindex:Int  portalias:String
    graph inputs                wires that leave the ``__parms__`` node
    graph outputs               wires that enter the ``__output__`` node
    rig controls                nodes whose ``tags`` contain ``control``

  character geometry
    packed folders named ``Base.rig`` (the graph), ``Base.shp`` (the mesh)
    and ``Base.skel`` (the skeleton). A scene nests the character one folder
    deeper: ``ovoid.char/Base.rig``.

Direction was checked on all 490 wires of that rig: nothing enters
``__parms__``, nothing leaves ``__output__``, and a topological sort consumes
every node.

Three rules the callers rely on:

* Never cooks on its own. ``summarize`` takes geometry that is already
  cooked, and ``find_graphs`` reads a node only through the reader its caller
  supplies, so the caller's cook gate decides every read.
* Never walks a mesh. A geometry is opened only through O(1) counts, and a
  folder geometry is walked only when it holds few primitives.
* Type-strict. A count must be a real int and a column a real sequence of
  str, so a stand-in object (a test double, a mock) can never read as a graph.

The module imports neither ``hou`` nor ``apex``: every read is duck-typed on
the geometry it is given, so it runs and tests outside Houdini.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# The primitive type a packed folder reports from hou.Prim.type().name().
PACKED_TYPE = "PackedGeometry"

# Graph vocabulary.
CONTROL_TAG = "control"
GRAPH_INPUT_CALLBACK = "__parms__"
GRAPH_OUTPUT_CALLBACK = "__output__"

# Ceilings. Past each one the read stops and says so; it never returns a
# partial result as if it were complete.
FOLDER_SCAN_CAP = 256        # most primitives a folder geometry may hold and still be walked
FOLDER_DEPTH_CAP = 3         # scene > character > rig is depth 2
FOLDER_VISIT_CAP = 512       # folders opened in one read, across all depths
FOLDER_REPORT_CAP = 32       # folder rows returned in a summary
GRAPH_NODE_CAP = 20_000      # graph nodes read from one graph
GRAPH_WIRE_CAP = 100_000     # wires read from one graph
UPSTREAM_DEPTH_CAP = 5       # input levels searched when a node's own output has no graph
UPSTREAM_NODE_CAP = 12       # input nodes examined in that search
NAME_LIST_CAP = 120          # names returned per list in a summary
CALLBACK_KIND_CAP = 40       # callback kinds returned in a summary


# ---------------------------------------------------------------------------
# Strict low-level reads
# ---------------------------------------------------------------------------

def _count(geo: Any, name: str) -> Optional[int]:
    """An element count from ``intrinsicValue``, or None.

    Only a real non-negative int counts. A bool is not a count, and a stand-in
    object's attribute must not pass as one.
    """
    reader = getattr(geo, "intrinsicValue", None)
    if not callable(reader):
        return None
    try:
        value = reader(name)
    except Exception:
        logger.debug("intrinsic %s unreadable", name, exc_info=True)
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _has_attrib(geo: Any, finder_name: str, attrib_name: str) -> bool:
    finder = getattr(geo, finder_name, None)
    if not callable(finder):
        return False
    try:
        return finder(attrib_name) is not None
    except Exception:
        logger.debug("%s(%r) failed", finder_name, attrib_name, exc_info=True)
        return False


def _string_column(geo: Any, reader_name: str, attrib_name: str,
                   expected: int) -> Optional[Tuple[str, ...]]:
    """One str per element, read in bulk, or None when it is not exactly that."""
    reader = getattr(geo, reader_name, None)
    if not callable(reader):
        return None
    try:
        values = reader(attrib_name)
    except Exception:
        logger.debug("%s(%r) failed", reader_name, attrib_name, exc_info=True)
        return None
    if not isinstance(values, (tuple, list)) or len(values) != expected:
        return None
    if not all(isinstance(v, str) for v in values):
        return None
    return tuple(values)


def _string_list(value: Any) -> List[str]:
    """A string-array attribute value as a list of str (a lone str is one item)."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (tuple, list)):
        return [v for v in value if isinstance(v, str)]
    return []


def _capped(names: Sequence[str]) -> Tuple[List[str], int]:
    """The first NAME_LIST_CAP names and how many were left out."""
    kept = list(names[:NAME_LIST_CAP])
    return kept, len(names) - len(kept)


def _unique(names: Sequence[str]) -> List[str]:
    seen = set()
    out = []
    for name in names:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


# ---------------------------------------------------------------------------
# Graph geometry
# ---------------------------------------------------------------------------

def is_graph_geometry(geo: Any) -> bool:
    """True when *geo* is APEX graph geometry: one ``callback`` str per point.

    Cheap. It reads two O(1) facts and never touches a primitive, so a
    792,113-point mesh answers False at once.
    """
    if geo is None or not _has_attrib(geo, "findPointAttrib", "callback"):
        return False
    count = _count(geo, "pointcount")
    return count is not None and count > 0


def read_graph(geo: Any, *, include_nodes: bool = False,
               include_wires: bool = False) -> Optional[Dict[str, Any]]:
    """Read one APEX graph from its geometry, or None when *geo* is not one.

    The result always carries the counts, the callback histogram, the control
    names and the graph's inputs and outputs. ``include_nodes`` adds one row
    per node and ``include_wires`` one row per wire; both are off by default
    so a summary stays small.

    Anything left out is stamped under ``omitted``. A graph past
    GRAPH_NODE_CAP is reported by its counts with ``read: False``.
    """
    if not is_graph_geometry(geo):
        return None
    node_count = _count(geo, "pointcount")
    wire_count = _count(geo, "primitivecount")
    if node_count is None:
        return None
    if node_count > GRAPH_NODE_CAP:
        return {
            "read": False,
            "reason": "graph has %d nodes, past the %d-node read ceiling"
                      % (node_count, GRAPH_NODE_CAP),
            "node_count": node_count,
            "wire_count": wire_count,
        }

    callbacks = _string_column(geo, "pointStringAttribValues", "callback", node_count)
    if callbacks is None:
        # A ``callback`` attribute that is not one str per point is not a graph.
        return None
    names = None
    if _has_attrib(geo, "findPointAttrib", "name"):
        names = _string_column(geo, "pointStringAttribValues", "name", node_count)
    if names is None:
        names = tuple("node_%d" % i for i in range(node_count))
    else:
        names = tuple(n if n else "node_%d" % i for i, n in enumerate(names))

    tags = _read_tags(geo, node_count)
    controls = [names[i] for i in range(node_count) if CONTROL_TAG in tags[i]]

    histogram: Dict[str, int] = {}
    for cb in callbacks:
        histogram[cb] = histogram.get(cb, 0) + 1
    ranked = sorted(histogram.items(), key=lambda kv: (-kv[1], kv[0]))

    wires, wires_unread, wires_status = _read_wires(geo, node_count, wire_count)
    graph_inputs = _unique([w[1] for w in wires
                            if callbacks[w[0]] == GRAPH_INPUT_CALLBACK and w[1]])
    graph_outputs = _unique([w[3] for w in wires
                             if callbacks[w[2]] == GRAPH_OUTPUT_CALLBACK and w[3]])

    omitted: Dict[str, int] = {}
    kept_controls, left = _capped(controls)
    if left:
        omitted["controls"] = left
    kept_inputs, left = _capped(graph_inputs)
    if left:
        omitted["graph_inputs"] = left
    kept_outputs, left = _capped(graph_outputs)
    if left:
        omitted["graph_outputs"] = left
    if len(ranked) > CALLBACK_KIND_CAP:
        omitted["callback_kinds"] = len(ranked) - CALLBACK_KIND_CAP
    if wires_unread:
        omitted["wires_unread"] = wires_unread

    result: Dict[str, Any] = {
        "read": True,
        "node_count": node_count,
        "wire_count": wire_count,
        "control_count": len(controls),
        "controls": kept_controls,
        "callbacks": dict(ranked[:CALLBACK_KIND_CAP]),
        "graph_input_count": len(graph_inputs),
        "graph_inputs": kept_inputs,
        "graph_output_count": len(graph_outputs),
        "graph_outputs": kept_outputs,
        "wires_status": wires_status,
    }
    if omitted:
        result["omitted"] = omitted
    if include_nodes:
        result["nodes"] = [
            {"name": names[i], "callback": callbacks[i], "tags": tags[i]}
            for i in range(node_count)
        ]
    if include_wires:
        result["wires"] = [
            {"source": names[a], "source_port": sp,
             "destination": names[b], "destination_port": dp}
            for a, sp, b, dp in wires
        ]
    return result


def _read_tags(geo: Any, node_count: int) -> List[List[str]]:
    """Per-node tag lists. ``tags`` is a string array, which has no bulk reader
    (``pointStringAttribValues('tags')`` raises on 22.0.466), so it is read
    one point at a time over a count already held under GRAPH_NODE_CAP."""
    tags: List[List[str]] = [[] for _ in range(node_count)]
    if not _has_attrib(geo, "findPointAttrib", "tags"):
        return tags
    source = None
    for accessor in ("iterPoints", "points"):
        getter = getattr(geo, accessor, None)
        if callable(getter):
            try:
                source = getter()
                break
            except Exception:
                logger.debug("%s() failed", accessor, exc_info=True)
    if source is None:
        return tags
    try:
        for index, point in enumerate(source):
            if index >= node_count:
                break
            try:
                tags[index] = _string_list(point.attribValue("tags"))
            except Exception:
                logger.debug("tags unreadable on point %d", index, exc_info=True)
    except Exception:
        logger.debug("point walk for tags failed", exc_info=True)
    return tags


def _read_wires(geo: Any, node_count: int, wire_count: Optional[int],
                ) -> Tuple[List[Tuple[int, str, int, str]], int, str]:
    """Wires as (source index, source port, destination index, destination port).

    Returns (wires, unread count, status). A primitive that is not a clean
    two-vertex wire between two known nodes is counted as unread, never guessed.
    """
    if wire_count is None:
        return [], 0, "not read (wire count unavailable)"
    if wire_count > GRAPH_WIRE_CAP:
        return [], wire_count, ("not read (%d wires, past the %d-wire ceiling)"
                                % (wire_count, GRAPH_WIRE_CAP))
    has_ports = _has_attrib(geo, "findVertexAttrib", "portname")
    source = None
    for accessor in ("iterPrims", "prims"):
        getter = getattr(geo, accessor, None)
        if callable(getter):
            try:
                source = getter()
                break
            except Exception:
                logger.debug("%s() failed", accessor, exc_info=True)
    if source is None:
        return [], wire_count, "not read (primitives unavailable)"

    wires: List[Tuple[int, str, int, str]] = []
    unread = 0
    try:
        for prim in source:
            try:
                # hou.Prim.vertices() hands back a generator on 22.0.466, not
                # a tuple, so it is materialised before it is measured.
                ends = tuple(prim.vertices())
                if len(ends) != 2:
                    unread += 1
                    continue
                a = ends[0].point().number()
                b = ends[1].point().number()
                if (isinstance(a, bool) or isinstance(b, bool)
                        or not isinstance(a, int) or not isinstance(b, int)
                        or not 0 <= a < node_count or not 0 <= b < node_count):
                    unread += 1
                    continue
                sp = _port_name(ends[0]) if has_ports else ""
                dp = _port_name(ends[1]) if has_ports else ""
                wires.append((a, sp, b, dp))
            except Exception:
                logger.debug("wire unreadable", exc_info=True)
                unread += 1
    except Exception:
        logger.debug("wire walk failed", exc_info=True)
        return wires, max(0, wire_count - len(wires)), "partly read (wire walk failed)"
    status = "read" if not unread else "partly read"
    return wires, unread, status


def _port_name(vertex: Any) -> str:
    try:
        value = vertex.attribValue("portname")
    except Exception:
        logger.debug("portname unreadable", exc_info=True)
        return ""
    return value if isinstance(value, str) else ""


# ---------------------------------------------------------------------------
# Packed folders
# ---------------------------------------------------------------------------

def _packed_count(geo: Any) -> Optional[int]:
    """How many packed folders *geo* holds, in O(1), or None if unknowable."""
    counter = getattr(geo, "countPrimType", None)
    if not callable(counter):
        return None
    try:
        value = counter(PACKED_TYPE)
    except Exception:
        logger.debug("countPrimType(%r) failed", PACKED_TYPE, exc_info=True)
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def iter_folders(geo: Any) -> Iterator[Tuple[str, Any, int]]:
    """Yield (label, embedded geometry, depth) for the packed folders in *geo*.

    Nested folders follow their parent with a ``parent/child`` label, down to
    FOLDER_DEPTH_CAP. A geometry is walked only when its packed count is known
    and non-zero and it holds at most FOLDER_SCAN_CAP primitives, so a mesh is
    answered by two O(1) reads and never iterated.
    """
    budget = [FOLDER_VISIT_CAP]
    yield from _walk_folders(geo, "", 0, budget)


def _walk_folders(geo: Any, prefix: str, depth: int,
                  budget: List[int]) -> Iterator[Tuple[str, Any, int]]:
    if geo is None or depth > FOLDER_DEPTH_CAP or budget[0] <= 0:
        return
    packed = _packed_count(geo)
    if not packed:
        return
    total = _count(geo, "primitivecount")
    if total is None or total > FOLDER_SCAN_CAP:
        return
    names = None
    if _has_attrib(geo, "findPrimAttrib", "name"):
        names = _string_column(geo, "primStringAttribValues", "name", total)
    getter = getattr(geo, "prims", None)
    if not callable(getter):
        return
    try:
        prims = getter()
    except Exception:
        logger.debug("prims() failed", exc_info=True)
        return
    if not isinstance(prims, (tuple, list)):
        return
    for index, prim in enumerate(prims):
        if budget[0] <= 0:
            return
        try:
            type_name = prim.type().name()
        except Exception:
            logger.debug("prim type unreadable", exc_info=True)
            continue
        if type_name != PACKED_TYPE:
            continue
        opener = getattr(prim, "getEmbeddedGeometry", None)
        if not callable(opener):
            continue
        try:
            embedded = opener()
        except Exception:
            logger.debug("getEmbeddedGeometry() failed", exc_info=True)
            continue
        if embedded is None:
            continue
        label = names[index] if names is not None and names[index] else "prim_%d" % index
        budget[0] -= 1
        yield prefix + label, embedded, depth
        yield from _walk_folders(embedded, prefix + label + "/", depth + 1, budget)


def _folder_kind(geo: Any) -> str:
    if is_graph_geometry(geo):
        return "graph"
    if _packed_count(geo):
        return "folder"
    if (_has_attrib(geo, "findPointAttrib", "name")
            and _has_attrib(geo, "findPointAttrib", "transform")):
        return "skeleton"
    return "geometry"


# ---------------------------------------------------------------------------
# One call for the inspect tools
# ---------------------------------------------------------------------------

def summarize(geo: Any, *, include_nodes: bool = False,
              include_wires: bool = False) -> Optional[Dict[str, Any]]:
    """Describe the APEX graphs carried by *geo*, or None when it carries none.

    *geo* may be a graph itself, a character (packed folders) or a scene (a
    character one folder deeper). The result is bounded: counts, a callback
    histogram, capped name lists and one row per folder.

    Returns None for any geometry without a graph, including ordinary packed
    geometry, so a caller can add the result as an optional block.
    """
    if geo is None:
        return None
    direct = read_graph(geo, include_nodes=include_nodes, include_wires=include_wires)
    if direct is not None:
        direct["folder"] = ""
        return {"graphs": [direct], "folders": []}

    graphs: List[Dict[str, Any]] = []
    folders: List[Dict[str, Any]] = []
    folder_total = 0
    for label, embedded, depth in iter_folders(geo):
        folder_total += 1
        kind = _folder_kind(embedded)
        if len(folders) < FOLDER_REPORT_CAP:
            folders.append({
                "name": label,
                "kind": kind,
                "points": _count(embedded, "pointcount"),
                "prims": _count(embedded, "primitivecount"),
            })
        if kind == "graph":
            graph = read_graph(embedded, include_nodes=include_nodes,
                               include_wires=include_wires)
            if graph is not None:
                graph["folder"] = label
                graphs.append(graph)
    if not graphs:
        return None
    result: Dict[str, Any] = {"graphs": graphs, "folders": folders}
    if folder_total > len(folders):
        result["folders_omitted"] = folder_total - len(folders)
    return result


# ---------------------------------------------------------------------------
# Node-level search
# ---------------------------------------------------------------------------

def _path_of(node: Any) -> Optional[str]:
    try:
        path = node.path()
    except Exception:
        logger.debug("node path unavailable", exc_info=True)
        return None
    return path if isinstance(path, str) else None


def find_graphs(node: Any, read_geometry: Callable[[Any], Any], *,
                search_upstream: bool = True, include_nodes: bool = False,
                include_wires: bool = False) -> Dict[str, Any]:
    """Find the APEX graphs *node* carries: its own output, else upstream.

    *read_geometry* is the caller's reader. It takes a node and returns that
    node's geometry, or None when the caller will not read it (a dirty node
    behind a cook gate, say). This function never calls ``geometry()`` itself.

    A node whose own output holds no graph (Scene Invoke outputs the posed
    mesh) is answered from the nearest input that holds one, breadth first,
    within UPSTREAM_DEPTH_CAP levels and UPSTREAM_NODE_CAP nodes.

    Returns a dict:
      summary    the ``summarize`` result, or None when no graph was found
      source     path of the node the graph was read from, or None
      distance   0 for the node itself, n for n inputs upstream
      examined   upstream nodes looked at
      unread     paths of upstream nodes the reader declined to read
    """
    result: Dict[str, Any] = {
        "summary": None, "source": None, "distance": 0,
        "examined": 0, "unread": [],
    }

    def _summarize(candidate: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
        try:
            geo = read_geometry(candidate)
        except Exception:
            logger.debug("geometry reader failed", exc_info=True)
            return False, None
        if geo is None:
            return False, None
        return True, summarize(geo, include_nodes=include_nodes,
                               include_wires=include_wires)

    was_read, summary = _summarize(node)
    if summary is not None:
        result["summary"] = summary
        result["source"] = _path_of(node)
        return result
    if not search_upstream:
        return result

    seen = set()
    frontier: List[Tuple[Any, int]] = [(node, 0)]
    while frontier and result["examined"] < UPSTREAM_NODE_CAP:
        current, distance = frontier.pop(0)
        if distance >= UPSTREAM_DEPTH_CAP:
            continue
        try:
            inputs = current.inputs()
        except Exception:
            logger.debug("inputs unavailable", exc_info=True)
            continue
        if not isinstance(inputs, (tuple, list)):
            continue
        for upstream in inputs:
            if upstream is None or result["examined"] >= UPSTREAM_NODE_CAP:
                continue
            path = _path_of(upstream)
            if path is None or path in seen:
                continue
            seen.add(path)
            result["examined"] += 1
            was_read, summary = _summarize(upstream)
            if summary is not None:
                result["summary"] = summary
                result["source"] = path
                result["distance"] = distance + 1
                return result
            if not was_read:
                result["unread"].append(path)
            frontier.append((upstream, distance + 1))
    return result
