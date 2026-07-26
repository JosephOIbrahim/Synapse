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
            "description": "The purpose that was assigned.",
        },
        "status": {
            "type": "string",
            # R33, 2026-07-26. Was ["set", "already_set", "not_found"].
            # `already_set` has never been returned by execute(); the three
            # authoring outcomes are distinguished as set/updated/unchanged
            # (Law 3 -- three distinct things happened, three distinct words),
            # and `noop` is the honest report when no target prim resolves.
            # Derived from set_purpose.py:278 (not_found), :288 (noop) and
            # :360-361 (the set/updated/unchanged ternary).
            "enum": ["set", "updated", "unchanged", "noop", "not_found"],
            "description": (
                "'set' = purpose newly authored. 'updated' = this tool's "
                "existing configureprimitive was retargeted to a new value. "
                "'unchanged' = it already carried this exact purpose, so "
                "nothing moved. 'noop' = no target prim could be resolved, so "
                "nothing was authored. 'not_found' = the component holds no "
                "componentgeometry node."
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
