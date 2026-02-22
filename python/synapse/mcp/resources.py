"""
MCP Resource Registry

Maps URI patterns to existing SYNAPSE handlers for resources/list
and resources/read. Resources provide read-only browseable data
about the Houdini scene, USD stage, and TOPS networks.

He2025: get_resources() returns resources sorted by URI.
"""

import re
from typing import Any


# =========================================================================
# Resource definitions
# =========================================================================

# Static resources (no URI parameters)
_STATIC_RESOURCES: list[dict] = [
    {
        "uri": "houdini://scene/info",
        "name": "Scene Info",
        "description": "HIP file path, current frame, FPS, frame range, and statistics.",
        "mimeType": "application/json",
        "_handler": "get_scene_info",
        "_payload": {},
    },
    {
        "uri": "houdini://scene/tree",
        "name": "Scene Tree",
        "description": "Full node hierarchy of the Houdini scene.",
        "mimeType": "application/json",
        "_handler": "inspect_scene",
        "_payload": {},
    },
    {
        "uri": "houdini://stage/info",
        "name": "USD Stage Info",
        "description": "USD stage summary: prim list and types.",
        "mimeType": "application/json",
        "_handler": "get_stage_info",
        "_payload": {},
    },
    {
        "uri": "synapse://project/context",
        "name": "Project Context",
        "description": (
            "Project memory, scene memory, agent state, and evolution stage. "
            "Auto-loaded on session start. Read this to understand the artist's "
            "project history, previous decisions, and current scene context."
        ),
        "mimeType": "application/json",
        "_handler": "project_setup",
        "_payload": {},
    },
]

# Resource templates (URI contains {parameters})
_RESOURCE_TEMPLATES: list[dict] = [
    {
        "uriTemplate": "houdini://node/{path}/parameters",
        "name": "Node Parameters",
        "description": "All parameter values for a Houdini node.",
        "mimeType": "application/json",
        "_handler": "inspect_node",
        "_payload_fn": lambda path: {"node": "/" + path, "include_geometry": False},
    },
    {
        "uriTemplate": "houdini://node/{path}/attributes",
        "name": "Node Attributes",
        "description": "Geometry attribute metadata and samples for a Houdini node.",
        "mimeType": "application/json",
        "_handler": "inspect_node",
        "_payload_fn": lambda path: {"node": "/" + path, "include_code": False},
    },
    {
        "uriTemplate": "houdini://node/{path}/cook-stats",
        "name": "Node Cook Stats",
        "description": "Cook time, memory usage, and dependencies for a node.",
        "mimeType": "application/json",
        "_handler": "get_metrics",
        "_payload_fn": lambda path: {"node": "/" + path},
    },
    {
        "uriTemplate": "houdini://tops/{topnet_path}/graph",
        "name": "TOPS Dependency Graph",
        "description": "TOP network dependency graph: nodes, types, edges, work item counts.",
        "mimeType": "application/json",
        "_handler": "tops_get_dependency_graph",
        "_payload_fn": lambda topnet_path: {"topnet_path": "/" + topnet_path},
    },
    {
        "uriTemplate": "houdini://tops/{topnet_path}/scheduler",
        "name": "TOPS Scheduler",
        "description": "Scheduler configuration for a TOP network.",
        "mimeType": "application/json",
        "_handler": "tops_configure_scheduler",
        "_payload_fn": lambda topnet_path: {"topnet_path": "/" + topnet_path},
    },
    {
        "uriTemplate": "houdini://tops/{node_path}/items",
        "name": "TOPS Work Items",
        "description": "Work items from a TOP node with state and attributes.",
        "mimeType": "application/json",
        "_handler": "tops_get_work_items",
        "_payload_fn": lambda node_path: {"node": "/" + node_path},
    },
    {
        "uriTemplate": "houdini://tops/{node_path}/cook-log",
        "name": "TOPS Cook Stats",
        "description": "Cook statistics for a TOP node or network.",
        "mimeType": "application/json",
        "_handler": "tops_get_cook_stats",
        "_payload_fn": lambda node_path: {"node": "/" + node_path},
    },
    {
        "uriTemplate": "houdini://tops/{topnet_path}/status",
        "name": "TOPS Pipeline Status",
        "description": "Full health check for a TOP network: per-node status, issues, suggestions.",
        "mimeType": "application/json",
        "_handler": "tops_pipeline_status",
        "_payload_fn": lambda topnet_path: {"topnet_path": "/" + topnet_path},
    },
    {
        "uriTemplate": "houdini://tops/{node_path}/diagnosis",
        "name": "TOPS Diagnosis",
        "description": "Failure analysis for a TOP node: failed items, scheduler, upstream deps.",
        "mimeType": "application/json",
        "_handler": "tops_diagnose",
        "_payload_fn": lambda node_path: {"node": "/" + node_path},
    },
]


# =========================================================================
# Public API
# =========================================================================

def get_resources() -> list[dict]:
    """Return all static MCP resource definitions for resources/list.

    He2025: sorted by URI for deterministic output.
    """
    resources = []
    for r in _STATIC_RESOURCES:
        resources.append({
            "uri": r["uri"],
            "name": r["name"],
            "description": r["description"],
            "mimeType": r["mimeType"],
        })
    return sorted(resources, key=lambda r: r["uri"])


def get_resource_templates() -> list[dict]:
    """Return all resource templates for resources/templates/list.

    He2025: sorted by uriTemplate for deterministic output.
    """
    templates = []
    for t in _RESOURCE_TEMPLATES:
        templates.append({
            "uriTemplate": t["uriTemplate"],
            "name": t["name"],
            "description": t["description"],
            "mimeType": t["mimeType"],
        })
    return sorted(templates, key=lambda t: t["uriTemplate"])


def resolve_resource(uri: str) -> tuple[str, dict] | None:
    """Resolve a URI to (handler_name, payload) or None if not found.

    Checks static resources first, then matches against templates.
    """
    # Static resources — exact match
    for r in _STATIC_RESOURCES:
        if r["uri"] == uri:
            return r["_handler"], dict(r["_payload"])

    # Resource templates — pattern match
    for t in _RESOURCE_TEMPLATES:
        pattern = t["uriTemplate"]
        # Convert {param} to regex groups
        regex = re.sub(r"\{(\w+)\}", r"(?P<\1>.+?)", pattern)
        regex = "^" + regex + "$"
        m = re.match(regex, uri)
        if m:
            # Extract the first captured group value
            param_value = list(m.groups())[0]
            payload = t["_payload_fn"](param_value)
            return t["_handler"], payload

    return None
