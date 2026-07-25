"""
Schema: synapse_solaris_create_variants

Maps to: Pattern 5 (Variants)
Status: NEW TOOL
Priority: MEDIUM — variant set API is well-documented in USD

Creates material and/or geometry variants on a Component Builder asset.

Material variants: Duplicate Component Material nodes with different KMBs.
Geometry variants: Duplicate Component Geometry + Component Geometry Variants node.
Nested: geometry × material variant sets are orthogonal and independently selectable.

Preview: Explore Variants node (interactive, non-committing).
Commit: Set Variant node (right-click asset → choose variant).
"""

from typing import Dict, List, Optional


# --- MCP Tool Registration Schema ---

TOOL_NAME = "synapse_solaris_create_variants"

TOOL_DESCRIPTION = (
    "Create material and/or geometry variants on a USD Component Builder asset. "
    "Material variants duplicate Component Material nodes with different Karma "
    "Material Builders. Geometry variants duplicate Component Geometry and merge "
    "via Component Geometry Variants node. Supports nested variant sets "
    "(geo × material). Use Explore Variants to preview, Set Variant to commit."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "component_path": {
            "type": "string",
            "description": "Path to the Component Builder subnet.",
        },
        "variant_type": {
            "type": "string",
            "enum": ["material", "geometry"],
            "description": "Type of variant to create.",
        },
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Variant name (e.g., 'red', 'blue', 'big_hands').",
                    },
                    "material": {
                        "type": "object",
                        "description": (
                            "Material parameters for material variants. "
                            "Keys are KMB parameter names, values are settings. "
                            "Only used when variant_type='material'."
                        ),
                    },
                    "geometry_source": {
                        "type": "string",
                        "description": (
                            "SOP path or file path for geometry variants. "
                            "Only used when variant_type='geometry'."
                        ),
                    },
                },
                "required": ["name"],
            },
            "description": "List of variants to create.",
        },
        "add_explore_node": {
            "type": "boolean",
            "description": "Add an Explore Variants node after the component for interactive preview (default: true).",
            "default": True,
        },
    },
    "required": ["component_path", "variant_type", "variants"],
}

TOOL_RETURN = {
    "type": "object",
    "properties": {
        "variant_set_name": {
            "type": "string",
            "description": "Name of the created variant set.",
        },
        "variants_created": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of variant names created.",
        },
        "explore_node": {
            "type": "string",
            "description": "Path to the Explore Variants node (if add_explore_node=true).",
        },
        "status": {
            "type": "string",
            "enum": ["created", "extended", "already_exists"],
        },
    },
}

# Workflow steps per variant type
MATERIAL_VARIANT_WORKFLOW = [
    "Duplicate Component Material nodes inside Component Builder",
    "Each gets a different Karma Material Builder with different settings",
    "Component Builder auto-creates material variant set",
    "Preview: Explore Variants node",
    "Commit: Set Variant (right-click asset → choose variant)",
]

GEOMETRY_VARIANT_WORKFLOW = [
    "Duplicate Component Geometry nodes inside Component Builder",
    "Modify each geometry variant",
    "Use Component Geometry Variants node to merge geometry variants",
    "Each geometry variant can have independent material variants",
    "Preview: Explore Variants node (geo and material sets switch independently)",
]
