"""
RELAY-SOLARIS Phase 2: Tool Audit & Mapping Summary

Complete mapping of 8 NodeFlow patterns to SYNAPSE MCP tools.
This file is the Phase 2 reference — consumed by AGENT-ENG in Phase 3.
"""

# Pattern → Tool mapping with action and rationale
TOOL_AUDIT = {
    "P1_CANONICAL_LOP_CHAIN": {
        "existing_tool": "synapse_solaris_assemble_chain",
        "existing_workflow": "solaris_scene_pipeline (planner.py)",
        "action": "EXTEND + NEW",
        "new_tool": "synapse_solaris_scene_template",
        "rationale": (
            "assemble_chain handles wiring but not creation. "
            "solaris_scene_pipeline creates nodes but lacks Primitive LOP hierarchy, "
            "karmaphysicalsky, usdrender_rop, and canonical /shot paths. "
            "New scene_template tool creates the full skeleton; assemble_chain "
            "gets extended _SOLARIS_NODE_ORDER entries for the new node types."
        ),
    },
    "P2_COMPONENT_BUILDER": {
        "existing_tool": None,
        "action": "NEW",
        "new_tool": "synapse_solaris_component_builder",
        "rationale": (
            "No existing tool covers Component Builder subnet creation. "
            "This is the hardest branch — subnet with internal wiring. "
            "BLOCKER: verify 'componentbuilder' node type exists in H21."
        ),
        "blocker": "verify_component_builder.py must run before Phase 3",
    },
    "P3_PURPOSE_SYSTEM": {
        "existing_tool": None,
        "action": "NEW",
        "new_tool": "synapse_solaris_set_purpose",
        "rationale": (
            "Purpose is a parameter on Component Geometry outputs, "
            "but no existing tool exposes it. Simple single-param tool."
        ),
    },
    "P4_HIERARCHY_DISCIPLINE": {
        "existing_tool": "solaris_scene_pipeline (planner.py)",
        "action": "EXTEND (via scene_template)",
        "new_tool": None,
        "rationale": (
            "Hierarchy is the Primitive LOP with Xform/Group + canonical paths. "
            "Folded into scene_template tool — not a separate tool."
        ),
    },
    "P5_VARIANTS": {
        "existing_tool": None,
        "action": "NEW",
        "new_tool": "synapse_solaris_create_variants",
        "rationale": (
            "No existing variant management. Creates material and geometry "
            "variants inside Component Builder with auto variant set creation."
        ),
    },
    "P6_MEGASCANS_IMPORT": {
        "existing_tool": None,
        "action": "NEW",
        "new_tool": "synapse_solaris_import_megascans",
        "rationale": (
            "Full Megascans pipeline: SOP↔LOP bridge with material Reference trick. "
            "Scale 0.01, Match Size, PolyReduce, /materials/* wildcard."
        ),
    },
    "P7_ASSET_GALLERY_TOPS": {
        "existing_tool": "existing TOPs infrastructure",
        "action": "COVERED (low priority)",
        "new_tool": None,
        "rationale": (
            "Asset Gallery population is mostly UI-driven (pane, gear icon, etc.). "
            "The TOPs 'USD Assets to Gallery' node is a built-in H21 TOP. "
            "No custom MCP tool needed — existing tops_cook_node can drive it. "
            "The workflow is more of a recipe/guide than an automatable tool."
        ),
    },
    "P8_LAYOUT_PHYSICS": {
        "existing_tool": "existing Layout LOP + Edit LOP",
        "action": "COVERED (low priority)",
        "new_tool": None,
        "rationale": (
            "Layout and physics use built-in H21 LOP nodes with specific parameter "
            "settings. The key knowledge is: use 'Instanceable Reference' not "
            "'Point Instancer' for physics. This is a parameter hint, not a tool. "
            "Existing houdini_create_node + houdini_set_parm can handle this. "
            "Better served as a FORGE recipe than a dedicated MCP tool."
        ),
    },
}

# Summary counts
TOOLS_NEW = 5       # scene_template, component_builder, set_purpose, create_variants, import_megascans
TOOLS_EXTENDED = 2  # assemble_chain (_SOLARIS_NODE_ORDER), solaris_scene_pipeline (hierarchy)
TOOLS_COVERED = 2   # asset_gallery (TOPs), layout_physics (existing LOPs)
