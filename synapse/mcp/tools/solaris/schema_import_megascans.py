"""
Schema: synapse_solaris_import_megascans

Maps to: Pattern 6 (External Asset Import — Megascans/Fab)
Status: NEW TOOL
Priority: HIGH — SOP↔LOP bridge with material trick

Full Megascans/Fab .usdc import pipeline:
  Inside Component Geometry (SOPs):
    USD Import (unpack=ON) → Transform (0.01) → Match Size (Y min) → PolyReduce (5%)
  Separate Reference LOP for materials:
    Same .usdc → /materials/* wildcard → save to asset/mtl/
  Then: Component Material → Component Output → export

Key trick: Materials and geometry live in the same .usdc but must be imported
separately. Geometry via USD Import in SOPs, materials via Reference LOP with
/materials/* wildcard targeting.
"""

from typing import Dict, Optional


# --- MCP Tool Registration Schema ---

TOOL_NAME = "synapse_solaris_import_megascans"

TOOL_DESCRIPTION = (
    "Import a Megascans/Fab .usdc asset into a Component Builder with proper "
    "unit scaling, grounding, proxy generation, and material extraction. "
    "Handles the material import trick: Reference LOP with /materials/* wildcard "
    "imports materials separately from geometry. Scale 0.01 converts Unreal "
    "centimeters to Houdini meters."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "usdc_path": {
            "type": "string",
            "description": "Path to the downloaded .usdc file from Fab/Megascans.",
        },
        "asset_name": {
            "type": "string",
            "description": "Name for the imported asset (e.g., 'book_01', 'rock_large').",
        },
        "scale_factor": {
            "type": "number",
            "description": "Uniform scale factor (default: 0.01 — Unreal centimeters to Houdini meters).",
            "default": 0.01,
        },
        "ground_asset": {
            "type": "boolean",
            "description": "Apply Match Size with Justify Y: Minimum to ground the asset (default: true).",
            "default": True,
        },
        "rotation_correction": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 3,
            "maxItems": 3,
            "description": "Optional rotation correction [rx, ry, rz] in degrees. Applied after scale.",
        },
        "proxy_reduction": {
            "type": "number",
            "description": "PolyReduce percentage for proxy/simproxy (0.0-1.0, default: 0.05 = 5%).",
            "default": 0.05,
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "import_materials": {
            "type": "boolean",
            "description": "Import materials via Reference LOP /materials/* trick (default: true).",
            "default": True,
        },
        "export_path": {
            "type": "string",
            "description": "File path for the exported .usd asset. If omitted, sets up but doesn't export.",
        },
        "parent": {
            "type": "string",
            "description": "LOP network path (default: '/stage').",
            "default": "/stage",
        },
    },
    "required": ["usdc_path", "asset_name"],
}

TOOL_RETURN = {
    "type": "object",
    "properties": {
        "component_path": {
            "type": "string",
            "description": "Path to the created Component Builder subnet.",
        },
        "geometry_nodes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Paths to SOP nodes inside Component Geometry (import, transform, matchsize, polyreduce).",
        },
        "material_reference": {
            "type": "string",
            "description": "Path to the Reference LOP importing materials (if import_materials=true).",
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

# SOP sequence inside Component Geometry for Megascans
SOP_SEQUENCE = [
    {"type": "usdimport", "params": {"unpack_to_polygons": True}},
    {"type": "xform", "params": {"uniform_scale": 0.01}},
    {"type": "matchsize", "params": {"justify_y": "Minimum"}},
    {"type": "xform", "params": {}, "optional": True, "note": "rotation correction"},
    {"type": "polyreduce", "params": {"percentage": 0.05}},
    {"type": "output", "params": {}},
]

# Material import via Reference LOP
MATERIAL_IMPORT = {
    "node_type": "reference",
    "filepath": "<same .usdc as geometry>",
    "primpath": "/materials/*",
    "destpath": "asset/mtl/",
    "note": "Use Paste Relative Reference for path consistency",
}
