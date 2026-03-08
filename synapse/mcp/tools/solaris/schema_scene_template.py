"""
Schema: synapse_solaris_scene_template

Maps to: Pattern 1 (Canonical LOP Chain) + Pattern 4 (Hierarchy Discipline)
Status: NEW TOOL (extends existing solaris_scene_pipeline in planner.py)
Priority: MEDIUM — extends existing chain builder with proper hierarchy

Creates the full canonical Solaris scene skeleton from NodeFlow Pattern 1:
  Primitive (Xform/Group) → SOP Import(s) → Camera → Material Library
  → Karma Physical Sky → Karma Render Settings → USD Render ROP

Key difference from existing solaris_scene_pipeline:
  - Adds Primitive LOP with Xform Kind=Group hierarchy (Pattern 4)
  - Uses canonical /shot/{geo,LGT,MTL,cam}/$OS path convention
  - Creates karmaphysicalsky instead of generic light
  - Creates usdrender_rop for final output
  - Supports multiple SOP imports chained sequentially (never merged)
"""

from typing import Dict, List, Optional, Tuple


# --- MCP Tool Registration Schema ---

TOOL_NAME = "synapse_solaris_scene_template"

TOOL_DESCRIPTION = (
    "Create a full canonical Solaris scene skeleton with proper USD hierarchy. "
    "Builds the complete chain: Primitive (Xform/Group hierarchy) → SOP imports "
    "(chained, never merged) → Camera → Material Library → Karma Physical Sky → "
    "Karma Render Settings (XPU) → USD Render ROP. Follows the NodeFlow "
    "canonical LOP chain pattern with /shot/{geo,LGT,MTL,cam}/$OS path conventions."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_name": {
            "type": "string",
            "description": "Root primitive name (default: 'shot'). Becomes /shot in the hierarchy.",
            "default": "shot",
        },
        "hierarchy": {
            "type": "object",
            "description": (
                "Scene hierarchy categories. Keys are category names (geo, LGT, MTL, cam), "
                "values are lists of asset/light/material names to create under each category. "
                "Default creates empty categories for manual population."
            ),
            "default": {"geo": [], "LGT": [], "MTL": [], "cam": []},
        },
        "sop_paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "SOP geometry paths to import. Each creates a chained SOP Import node "
                "(sequential, never merged). Primitive path: /shot/geo/$OS."
            ),
        },
        "render_engine": {
            "type": "string",
            "enum": ["karma_xpu", "karma_cpu"],
            "description": "Karma rendering engine (default: karma_xpu for GPU rendering).",
            "default": "karma_xpu",
        },
        "resolution": {
            "type": "array",
            "items": {"type": "integer"},
            "minItems": 2,
            "maxItems": 2,
            "description": "Render resolution [width, height] (default: [1920, 1080]).",
            "default": [1920, 1080],
        },
        "output_path": {
            "type": "string",
            "description": "Render output path (default: '$HIP/render/$HIPNAME.png').",
            "default": "$HIP/render/$HIPNAME.png",
        },
        "parent": {
            "type": "string",
            "description": "LOP network path (default: '/stage').",
            "default": "/stage",
        },
    },
    "required": [],
}

TOOL_RETURN = {
    "type": "object",
    "properties": {
        "chain": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ordered list of created node paths from Primitive to USD Render ROP.",
        },
        "hierarchy_root": {
            "type": "string",
            "description": "USD primitive path of the scene root (e.g., '/shot').",
        },
        "render_rop": {
            "type": "string",
            "description": "Path to the USD Render ROP node.",
        },
        "status": {
            "type": "string",
            "enum": ["created", "already_exists"],
        },
    },
}

# Node sequence for _SOLARIS_NODE_ORDER extension
NODE_SEQUENCE = [
    "primitive",            # Xform hierarchy (Kind=Group)
    "sopimport",            # Geometry (chain sequentially, NEVER merge)
    "camera",               # Camera
    "materiallibrary",      # Materials (Karma Material Builders inside)
    "karmaphysicalsky",     # Physical sky lighting
    "karmarendersettings",  # Render configuration (engine + resolution)
    "usdrender_rop",        # Final render output
]

# Primitive path conventions (Pattern 4)
PRIMITIVE_PATHS = {
    "root": "/{scene_name}",
    "geometry": "/{scene_name}/geo/$OS",
    "lighting": "/{scene_name}/LGT/$OS",
    "materials": "/{scene_name}/MTL/$OS",
    "cameras": "/{scene_name}/cam/$OS",
}
