"""
Schema: synapse_solaris_set_purpose

Maps to: Pattern 3 (Purpose System)
Status: NEW TOOL
Priority: EASY — single parameter set on Component Geometry outputs

Sets the USD purpose on geometry within a Component Builder.
Purpose controls what gets shown where:
  - render:   full-res geometry shown at render time
  - proxy:    low-poly version shown in viewport (Preview mode)
  - simproxy: low-poly for physics/collision tools

Viewport toggle: Glasses icon → "Preview" (proxy) vs "Final Render" (render).
"""

from typing import Dict, Optional


# --- MCP Tool Registration Schema ---

TOOL_NAME = "synapse_solaris_set_purpose"

TOOL_DESCRIPTION = (
    "Set the USD purpose on geometry within a Component Builder. "
    "Purpose controls visibility: 'render' for full-res at render time, "
    "'proxy' for low-poly in viewport, 'simproxy' for physics/collision. "
    "Toggle viewport between proxy and render via the Glasses icon."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "component_path": {
            "type": "string",
            "description": "Path to the Component Builder subnet or Component Geometry node.",
        },
        "geometry_name": {
            "type": "string",
            "description": (
                "Which geometry output to configure. "
                "Maps to Component Geometry output names: 'default' (render), "
                "'proxy', 'simproxy'."
            ),
        },
        "purpose": {
            "type": "string",
            "enum": ["render", "proxy", "simproxy"],
            "description": (
                "USD purpose to assign. "
                "'render' = full-res at render time (Component Geometry 'default' output). "
                "'proxy' = low-poly in viewport Preview mode. "
                "'simproxy' = low-poly for physics/collision tools."
            ),
        },
    },
    "required": ["component_path", "purpose"],
}

TOOL_RETURN = {
    "type": "object",
    "properties": {
        "geometry_path": {
            "type": "string",
            "description": "USD prim path of the geometry with purpose set.",
        },
        "purpose": {
            "type": "string",
            # R33 (2026-07-26): was "The purpose that was assigned", which is
            # false on the `noop` path -- execute() echoes the REQUESTED
            # purpose there while authoring nothing.
            "description": (
                "The purpose that was requested. On every status except "
                "'noop' this is also what was authored; on 'noop' nothing "
                "was authored -- read `status`, not this field."
            ),
        },
        "status": {
            "type": "string",
            # R33 (2026-07-26): reconciled against set_purpose.execute().
            # The prior enum [set, already_set, not_found] declared
            # `already_set`, which this tool has never returned, and hid
            # `updated`, `unchanged` and `noop`, which it does return. That is
            # not stale documentation: it is what the MODEL is told it will
            # get back, so the model had no branch for three real outcomes and
            # a branch for one that never arrives. Pinned by
            # tests/test_solaris_schema_return_contract.py.
            "enum": ["set", "updated", "unchanged", "noop", "not_found"],
            "description": (
                "'set' = a new configureprimitive was created and wired in. "
                "'updated' = this tool's existing node was re-pointed to a "
                "different purpose. "
                "'unchanged' = that node already carried this exact purpose; "
                "nothing moved. "
                "'noop' = the target prim path could not be resolved, so NO "
                "purpose was authored -- pass `prim_path` explicitly. "
                "'not_found' = no componentgeometry node exists under "
                "`component_path`."
            ),
        },
    },
}

# Purpose → Component Geometry output mapping
PURPOSE_OUTPUT_MAP = {
    "render": "default",
    "proxy": "proxy",
    "simproxy": "sim proxy",
}
