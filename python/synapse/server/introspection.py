"""
Synapse Scene Introspection

Shared infrastructure for the three inspect tools:
  - inspect_selection  (Phase 1.1)
  - inspect_scene      (Phase 1.2)
  - inspect_node_detail (Phase 1.3)

Runs inside Houdini — assumes ``hou`` is importable.
"""

from typing import Any, Dict, List, Optional

try:
    import hou
except ImportError:
    hou = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _node_basic(node) -> Dict[str, Any]:
    """Path, type, name, and network category for a node."""
    return {
        "path": node.path(),
        "name": node.name(),
        "type": node.type().name(),
        "category": node.type().category().name(),
    }


def _modified_parms(node) -> Dict[str, Any]:
    """Return parms whose current value differs from the default.

    Compares the read value against ``parm.parmTemplate().defaultValue()``.
    Tuple parms (e.g. translate) are returned as lists.
    """
    changed: Dict[str, Any] = {}
    for parm in node.parms():
        try:
            tmpl = parm.parmTemplate()
            defaults = tmpl.defaultValue()
            # hou.Parm read — NOT Python's eval()
            val = parm.eval()  # noqa: S307

            # defaultValue() returns a tuple for scalars too — unwrap
            if isinstance(defaults, tuple) and len(defaults) == 1:
                default = defaults[0]
            else:
                default = defaults

            if val != default:
                changed[parm.name()] = val
        except Exception:
            # Skip unreadable / locked / expression-only parms
            pass
    return changed


def _connections(node) -> Dict[str, list]:
    """Input and output connections with node paths and indices."""
    inputs = []
    for i, inp in enumerate(node.inputs()):
        if inp is not None:
            inputs.append({"path": inp.path(), "index": i})

    outputs = []
    for conn in node.outputConnections():
        outputs.append({
            "path": conn.outputNode().path(),
            "input_index": conn.inputIndex(),
            "output_index": conn.outputIndex(),
        })
    return {"inputs": inputs, "outputs": outputs}


def _geometry_summary(node, max_samples: int = 5) -> Optional[Dict[str, Any]]:
    """Point/prim/vertex counts and attribute overview.

    Returns ``None`` when geometry isn't accessible (e.g. OBJ-level nodes).
    Attribute values are sampled up to *max_samples* with total count appended.
    """
    try:
        geo = node.geometry()
    except Exception:
        return None
    if geo is None:
        return None

    def _attr_info(attrs, elem_count):
        result = []
        for attr in attrs:
            info = {
                "name": attr.name(),
                "type": str(attr.dataType()),
                "size": attr.size(),
                "count": elem_count,
            }
            # Sample a few values
            try:
                limit = min(max_samples, elem_count)
                samples = []
                dtype = str(attr.dataType())
                if "String" in dtype:
                    raw = attr.strings()
                    samples = list(raw[:limit])
                else:
                    raw = attr.floatListData()
                    if raw:
                        samples = list(raw[:limit])
            except Exception:
                samples = []
            info["samples"] = samples
            result.append(info)
        return result

    pt_count = len(geo.points())
    prim_count = len(geo.prims())

    return {
        "points": pt_count,
        "prims": prim_count,
        "vertices": len(geo.vertices()) if hasattr(geo, "vertices") else 0,
        "point_attributes": _attr_info(geo.pointAttribs(), pt_count),
        "prim_attributes": _attr_info(geo.primAttribs(), prim_count),
        "detail_attributes": _attr_info(geo.globalAttribs(), 1),
    }


def _node_issues(node) -> Dict[str, list]:
    """Warnings and errors from the node's cook state."""
    warnings: List[str] = []
    errors: List[str] = []
    try:
        warnings = list(node.warnings())
    except Exception:
        pass
    try:
        errors = list(node.errors())
    except Exception:
        pass
    return {"warnings": warnings, "errors": errors}


def _node_code(node) -> Optional[str]:
    """Extract VEX/Python code from wrangle or script nodes."""
    for parm_name in ("snippet", "python", "code"):
        try:
            p = node.parm(parm_name)
            if p is not None:
                # hou.Parm read — NOT Python's eval()
                val = p.eval()  # noqa: S307
                if val and isinstance(val, str) and val.strip():
                    return val
        except Exception:
            pass
    return None


def _recurse_inputs(node, depth: int, current: int = 0) -> List[Dict[str, Any]]:
    """Walk the input graph to *depth* levels, collecting basic node info."""
    if current >= depth:
        return []
    result = []
    for inp in node.inputs():
        if inp is None:
            continue
        info = _node_basic(inp)
        info["modified_parms"] = _modified_parms(inp)
        if current + 1 < depth:
            info["inputs"] = _recurse_inputs(inp, depth, current + 1)
        result.append(info)
    return result


# ---------------------------------------------------------------------------
# Public API — called by handlers
# ---------------------------------------------------------------------------

def inspect_selection(depth: int = 1) -> Dict[str, Any]:
    """Inspect currently selected nodes with input-graph traversal.

    Args:
        depth: How many levels of input nodes to recurse (0 = none).

    Returns:
        ``{"count": N, "nodes": [...], "topology": [...]}``
    """
    selected = hou.selectedNodes()
    nodes = []
    topology = []

    for node in selected[:50]:  # cap at 50
        info = _node_basic(node)
        info["modified_parms"] = _modified_parms(node)
        info["connections"] = _connections(node)
        info["issues"] = _node_issues(node)
        info["geometry"] = _geometry_summary(node)
        if depth > 0:
            info["input_graph"] = _recurse_inputs(node, depth)

        nodes.append(info)

        # Build topology edges: (source_name, target_name, input_index)
        for inp in node.inputs():
            if inp is not None:
                topology.append([inp.name(), node.name(), 0])

    return {"count": len(nodes), "nodes": nodes, "topology": topology}


def inspect_scene(
    root: str = "/",
    max_depth: int = 3,
    context_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Hierarchical scene overview from *root* down to *max_depth*.

    Args:
        root: Starting node path (default ``"/"``).
        max_depth: Maximum recursion depth.
        context_filter: If set, only include nodes of this category (e.g. ``"Sop"``).

    Returns:
        ``{"overview": {...}, "network_tree": [...], "issues": [...], "artist_notes": [...]}``
    """
    root_node = hou.node(root)
    if root_node is None:
        raise ValueError(
            f"Couldn't find a node at {root} \u2014 "
            "double-check the path exists"
        )

    node_count = 0
    contexts: Dict[str, int] = {}
    issues: List[Dict[str, Any]] = []
    notes: List[Dict[str, Any]] = []

    def _walk(node, current_depth):
        nonlocal node_count
        if current_depth > max_depth:
            return None

        cat = node.type().category().name()
        if context_filter and cat != context_filter:
            # Still recurse children — filter only excludes leaf reporting
            children = []
            for child in node.children():
                c = _walk(child, current_depth + 1)
                if c is not None:
                    children.append(c)
            return {"path": node.path(), "children": children} if children else None

        node_count += 1
        contexts[cat] = contexts.get(cat, 0) + 1

        # Collect issues
        node_issues = _node_issues(node)
        if node_issues["warnings"] or node_issues["errors"]:
            issues.append({"path": node.path(), **node_issues})

        # Collect sticky notes
        try:
            for item in node.stickyNotes():
                notes.append({
                    "type": "sticky",
                    "path": node.path(),
                    "text": item.text()[:200],
                })
        except Exception:
            pass

        entry: Dict[str, Any] = {
            "path": node.path(),
            "name": node.name(),
            "type": node.type().name(),
            "category": cat,
        }

        children = []
        for child in node.children():
            c = _walk(child, current_depth + 1)
            if c is not None:
                children.append(c)
        if children:
            entry["children"] = children

        return entry

    tree = _walk(root_node, 0)

    return {
        "overview": {
            "node_count": node_count,
            "contexts": contexts,
        },
        "network_tree": [tree] if tree else [],
        "issues": issues,
        "artist_notes": notes,
    }


def inspect_node_detail(
    node_path: str,
    include_code: bool = True,
    include_geometry: bool = True,
    include_expressions: bool = True,
) -> Dict[str, Any]:
    """Deep single-node inspection.

    Returns ALL parameters (grouped by folder), expressions, keyframe
    status, VEX/Python code, geometry with value ranges, spare parms,
    and HDA info.
    """
    node = hou.node(node_path)
    if node is None:
        raise ValueError(
            f"Couldn't find a node at {node_path} \u2014 "
            "double-check the path exists"
        )

    info = _node_basic(node)
    info["connections"] = _connections(node)
    info["issues"] = _node_issues(node)

    # ── All parms grouped by folder ──
    parm_groups: Dict[str, list] = {}
    expressions: List[Dict[str, Any]] = []
    keyframed: List[Dict[str, Any]] = []
    spare_parms: List[str] = []

    for parm in node.parms():
        try:
            tmpl = parm.parmTemplate()
            # containingFolders() lives on the parm, not the template
            folder = parm.containingFolders()
            folder_name = " > ".join(folder) if folder else "Root"

            parm_info: Dict[str, Any] = {
                "name": parm.name(),
                "label": tmpl.label(),
                # hou.Parm read — NOT Python's eval()
                "value": parm.eval(),  # noqa: S307
            }

            # Expression detection
            if include_expressions:
                try:
                    expr = parm.expression()
                    if expr:
                        parm_info["expression"] = expr
                        parm_info["expression_language"] = str(parm.expressionLanguage())
                        expressions.append({
                            "parm": parm.name(),
                            "expression": expr,
                        })
                except Exception:
                    pass

            # Keyframe detection
            try:
                kfs = parm.keyframes()
                if kfs:
                    parm_info["keyframed"] = True
                    parm_info["keyframe_count"] = len(kfs)
                    keyframed.append({
                        "parm": parm.name(),
                        "count": len(kfs),
                    })
            except Exception:
                pass

            # Spare parm detection (isSpare lives on parm, not template)
            try:
                if parm.isSpare():
                    spare_parms.append(parm.name())
                    parm_info["spare"] = True
            except Exception:
                pass

            parm_groups.setdefault(folder_name, []).append(parm_info)
        except Exception:
            pass

    info["parameters"] = parm_groups
    info["expressions"] = expressions
    info["keyframed_parms"] = keyframed
    info["spare_parms"] = spare_parms

    # ── Code extraction ──
    if include_code:
        code = _node_code(node)
        if code is not None:
            info["code"] = code

    # ── Geometry ──
    if include_geometry:
        geo = _geometry_summary(node)
        if geo is not None:
            info["geometry"] = geo

    # ── HDA info ──
    try:
        definition = node.type().definition()
        if definition is not None:
            info["hda"] = {
                "library": definition.libraryFilePath(),
                "label": definition.description(),
                "version": definition.version() if hasattr(definition, "version") else None,
                "sections": [s for s in definition.sections().keys()],
            }
    except Exception:
        pass

    return info
