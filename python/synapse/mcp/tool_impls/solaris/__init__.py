"""
SYNAPSE Solaris MCP Tool Schemas -- RELAY-SOLARIS Phase 2

Tool mapping from NodeFlow pattern corpus to MCP tool interfaces.
Schema definitions only -- no implementation bodies.

Pattern -> Tool Mapping:
  P1 (Canonical LOP Chain)  -> EXTEND synapse_solaris_assemble_chain + synapse_solaris_scene_template (NEW)
  P2 (Component Builder)    -> synapse_solaris_component_builder (NEW)
  P3 (Purpose System)       -> synapse_solaris_set_purpose (NEW)
  P4 (Hierarchy Discipline) -> EXTEND synapse_solaris_scene_template (hierarchy params)
  P5 (Variants)             -> synapse_solaris_create_variants (NEW)
  P6 (Megascans Import)     -> synapse_solaris_import_megascans (NEW)
  P7 (Asset Gallery + TOPs) -> COVERED by existing TOPs tools (low priority)
  P8 (Layout + Physics)     -> COVERED by existing Layout LOP (low priority)
"""

from . import (
    component_builder,
    create_variants,
    import_megascans,
    scene_template,
    set_purpose,
)

__all__ = [
    "component_builder",
    "create_variants",
    "import_megascans",
    "scene_template",
    "set_purpose",
]
