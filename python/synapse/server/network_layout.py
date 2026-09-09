"""Pure planning for visual organization of existing nodes; no native mutation."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math
import re
import textwrap

from .handler_helpers import _compute_dag_positions

METADATA_KEY = "synapse.network_layout.v1"
MAX_NODES = 256
_COLORS = ((0.32, 0.38, 0.43), (0.40, 0.35, 0.32), (0.35, 0.40, 0.35))
_SHARED = "Shared assembly and output"


def _text(value, name, limit=120):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 for c in value)):
        raise ValueError(f"{name} must be readable text of 1 to {limit} characters")
    return value.strip()


def validate_request(payload):
    """Validate direct callers too: transport schemas are not the authority."""
    allowed = {"parent", "nodes", "style", "orientation", "groups", "labels",
               "spacing", "replace_boxes", "dry_run"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError("Only declared network layout fields are accepted")
    parent = payload.get("parent", "/stage")
    if (not isinstance(parent, str) or not parent.startswith("/")
            or ".." in parent.split("/") or "//" in parent):
        raise ValueError("parent must be an absolute network path")
    parent = parent.rstrip("/") or "/"
    paths = payload.get("nodes")
    if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_NODES:
        raise ValueError(f"nodes must name 1 to {MAX_NODES} existing direct children")
    for path in paths:
        if (not isinstance(path, str) or path.rsplit("/", 1)[0] != parent
                or not re.fullmatch(r"[^/\s.]+", path.rsplit("/", 1)[-1])):
            raise ValueError("Each node must be an absolute direct child of parent")
    if len(set(paths)) != len(paths):
        raise ValueError("nodes must not contain duplicates")
    style = payload.get("style", "plain")
    orientation = payload.get("orientation", "vertical")
    if style not in ("plain", "focus", "assets"):
        raise ValueError("style must be plain, focus, or assets")
    if orientation not in ("vertical", "horizontal"):
        raise ValueError("orientation must be vertical or horizontal")
    spacing = payload.get("spacing", 1.0)
    if (isinstance(spacing, bool) or not isinstance(spacing, (int, float))
            or not math.isfinite(spacing) or not 1 <= spacing <= 4):
        raise ValueError("spacing must be a finite multiplier between 1 and 4")
    groups = payload.get("groups", [])
    if not isinstance(groups, list) or len(groups) > 32:
        raise ValueError("groups must contain at most 32 named sections")
    if style == "assets" and not groups:
        raise ValueError("Asset organization requires explicit groups; inspect the nodes first")
    if style == "plain" and groups:
        raise ValueError("Use focus or assets style to create groups")
    selected, assigned, names, clean_groups = set(paths), set(), set(), []
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"label", "nodes"}:
            raise ValueError("Each group needs only label and nodes")
        label = _text(group["label"], "group label", 64)
        members = group["nodes"]
        if label in names or label == _SHARED:
            raise ValueError("Group labels must be unique; the shared section is automatic")
        if (not isinstance(members, list) or not members
                or any(not isinstance(p, str) or p not in selected for p in members)
                or len(set(members)) != len(members) or assigned.intersection(members)):
            raise ValueError("Each selected node may belong to only one declared group")
        assigned.update(members)
        names.add(label)
        clean_groups.append({"label": label, "nodes": list(members)})
    labels = payload.get("labels", {})
    if not isinstance(labels, dict) or set(labels) - selected:
        raise ValueError("labels may only name selected nodes")
    labels = {p: _text(value, "node label") for p, value in labels.items()}
    replace = payload.get("replace_boxes", [])
    if (not isinstance(replace, list) or len(replace) > 64
            or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9_]+", n) for n in replace)
            or len(set(replace)) != len(replace)):
        raise ValueError("replace_boxes must be unique existing box names in this network")
    dry_run = payload.get("dry_run", False)
    if not isinstance(dry_run, bool):
        raise ValueError("dry_run must be a boolean")
    return {"parent": parent, "nodes": list(paths), "style": style,
            "orientation": orientation, "spacing": float(spacing),
            "groups": clean_groups, "labels": labels,
            "replace_boxes": replace, "dry_run": dry_run}


def _ordered(paths, connections):
    indegree = dict.fromkeys(paths, 0)
    children = defaultdict(list)
    for edge in connections:
        source, target = edge["from"], edge["to"]
        if source in indegree and target in indegree:
            children[source].append(target)
            indegree[target] += 1
    pending = sorted(p for p, degree in indegree.items() if degree == 0)
    result = []
    while pending:
        path = pending.pop(0)
        result.append(path)
        for child in children[path]:
            indegree[child] -= 1
            if indegree[child] == 0:
                pending.append(child)
                pending.sort()
    if len(result) != len(paths):
        raise ValueError("The selected network contains a cycle; no layout was changed")
    return result


def _section(node):
    kind = node["type"].split("::")[0].lower()
    if any(token in kind for token in ("light", "camera", "sky")):
        return "Camera and lighting"
    if any(token in kind for token in ("material", "shader")):
        return "Materials"
    if kind in ("null", "merge", "sublayer", "usd_rop", "karmarenderproperties"):
        return _SHARED
    return "Geometry" if kind.startswith(("sop", "component")) else "Processing"


def layout_summary(payload):
    style = payload.get("style", "plain") if isinstance(payload, dict) else "plain"
    return {"focus": "Focus layout", "assets": "Organize network by asset"}.get(style, "Layout change")


def plan_layout(settings, nodes, connections, origin=(0.0, 0.0)):
    """Return bounded positions, comments, colors and explicit box membership."""
    by_path = {node["path"]: node for node in nodes}
    order = _ordered(settings["nodes"], connections)
    styled = settings["style"] != "plain"
    sections = [dict(group, nodes=list(group["nodes"])) for group in settings["groups"]]
    if not sections and styled:
        by_label = {}
        for path in order:
            by_label.setdefault(_section(by_path[path]), []).append(path)
        sections = [{"label": label, "nodes": paths} for label, paths in by_label.items()]
    elif sections:
        assigned = {p for section in sections for p in section["nodes"]}
        remaining = [p for p in order if p not in assigned]
        if remaining:
            sections.append({"label": _SHARED, "nodes": remaining})
    units = sections or [{"label": "", "nodes": order}]
    positions, cursor = {}, 0.0
    vspace, hspace = ((3.0, 6.0) if styled else (1.6, 4.0))
    spacing = settings["spacing"]
    for index, section in enumerate(units):
        members = set(section["nodes"])
        edges = [edge for edge in connections if edge["from"] in members and edge["to"] in members]
        local = _compute_dag_positions([p for p in order if p in members], edges,
                                      v_spacing=vspace * spacing, h_spacing=hspace * spacing,
                                      orientation=settings["orientation"])
        left, top = min(x for x, y in local.values()), max(y for x, y in local.values())
        horizontal = settings["orientation"] == "horizontal"
        for path, (x, y) in local.items():
            positions[path] = (origin[0] + x - left + (cursor if horizontal else 0),
                               origin[1] + y - top - (0 if horizontal else cursor))
        extent = (max(x for x, y in local.values()) - left if horizontal
                  else top - min(y for x, y in local.values()))
        cursor += extent + (hspace if horizontal else vspace) * spacing + 3.0
        if styled:
            token = "\n".join([section["label"], *sorted(section["nodes"])])
            section["box_name"] = "synapse_layout_" + hashlib.sha256(token.encode()).hexdigest()[:16]
            section["color"] = _COLORS[index % len(_COLORS)]
    labels = ({path: settings["labels"].get(path) or by_path[path]["description"] for path in order}
              if styled else dict(settings["labels"]))
    labels = {path: "\n".join(textwrap.wrap(label, width=34, break_long_words=True))
              for path, label in labels.items()}
    return {"positions": positions, "sections": sections, "labels": labels,
            "style": settings["style"], "orientation": settings["orientation"]}
