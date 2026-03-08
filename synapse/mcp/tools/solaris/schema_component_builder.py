"""
Schema: synapse_solaris_component_builder

Maps to: Pattern 2 (Component Builder)
Status: NEW TOOL
Priority: HIGH — hardest branch (subnet creation with internal wiring)

Creates a complete Component Builder setup for a USD asset:
  Component Geometry (SOPs: geo → default, PolyReduce → proxy/simproxy)
  → Material Library (Karma Material Builders)
  → Component Material (auto-assigns)
  → Component Output (name, path, thumbnail, export)

CRITICAL BLOCKER (BL from sprint plan):
  The "componentbuilder" node type may not exist as a single createable node
  in Houdini 21. If it doesn't exist, this tool must be redesigned as manual
  subnet assembly. See verify_component_builder.py for the check script.

  Fallback strategy: Create a subnet and wire componentgeometry,
  componentmaterial, componentoutput nodes manually inside it.
"""

from typing import Dict, List, Optional


# --- MCP Tool Registration Schema ---

TOOL_NAME = "synapse_solaris_component_builder"

TOOL_DESCRIPTION = (
    "Create a complete USD Component Builder for a production asset. "
    "Sets up Component Geometry with render/proxy/simproxy purpose outputs, "
    "Material Library with Karma Material Builders, Component Material for "
    "auto-assignment, and Component Output for export. Supports the full "
    "export → reference round-trip workflow."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "asset_name": {
            "type": "string",
            "description": "Name for the asset (e.g., 'hero_chair'). Used for node naming and export.",
        },
        "geometry_source": {
            "type": "string",
            "description": (
                "SOP path or file path for the geometry source. "
                "If a SOP path (e.g., '/obj/geo1'), imports from the SOP network. "
                "If a file path, creates a File SOP inside Component Geometry."
            ),
        },
        "proxy_reduction": {
            "type": "number",
            "description": "PolyReduce percentage for proxy geometry (0.0-1.0, default: 0.05 = 5%).",
            "default": 0.05,
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "materials": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Material name (e.g., 'wood', 'red')"},
                    "type": {
                        "type": "string",
                        "enum": ["principled", "standard_surface", "karma_material_builder"],
                        "description": "Material shader type (default: karma_material_builder)",
                        "default": "karma_material_builder",
                    },
                    "params": {
                        "type": "object",
                        "description": "Shader parameter overrides (e.g., {'basecolor': [0.8, 0.2, 0.1]})",
                    },
                },
                "required": ["name"],
            },
            "description": "Materials to create inside the Material Library.",
        },
        "export_path": {
            "type": "string",
            "description": "File path for the exported .usd asset. If omitted, sets up the node but doesn't export.",
        },
        "generate_thumbnail": {
            "type": "boolean",
            "description": "Generate a thumbnail image for the asset (default: true).",
            "default": True,
        },
        "purposes": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["render", "proxy", "simproxy"],
            },
            "description": "Which purpose outputs to create (default: ['render', 'proxy']).",
            "default": ["render", "proxy"],
        },
        "parent": {
            "type": "string",
            "description": "LOP network path (default: '/stage').",
            "default": "/stage",
        },
    },
    "required": ["asset_name"],
}

TOOL_RETURN = {
    "type": "object",
    "properties": {
        "component_path": {
            "type": "string",
            "description": "Path to the Component Builder subnet node.",
        },
        "internal_nodes": {
            "type": "object",
            "description": "Paths to internal nodes (componentgeometry, componentmaterial, componentoutput).",
        },
        "export_path": {
            "type": "string",
            "description": "Path where the .usd was exported (if export_path was provided).",
        },
        "status": {
            "type": "string",
            "enum": ["created", "already_exists"],
        },
    },
}

# Internal node sequence within the Component Builder subnet
NODE_SEQUENCE = [
    "componentgeometry",    # SOPs inside: geo → default, PolyReduce → proxy/simproxy
    "componentmaterial",    # Auto-assigns materials to geometry
    "componentoutput",      # Name, file path, thumbnail, export
]

# SOP sequence inside Component Geometry
SOP_INTERNAL_SEQUENCE = [
    "file",                 # or import — loads geometry
    "polyreduce",           # proxy generation (5% default)
    "output",               # ensures correct export from SOP context
]
