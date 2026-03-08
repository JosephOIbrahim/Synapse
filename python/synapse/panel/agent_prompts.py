"""
Agent Expertise Prompts -- Inject domain-specific context based on MOE routing.

Phase 2 of the MOE wiring plan. Uses routing decision from Phase 1 to
append condensed agent expertise to the system prompt.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

# ── sys.path bridging ────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_TYPES_AVAILABLE = False
try:
    from shared.types import AgentID
    _TYPES_AVAILABLE = True
except ImportError:
    AgentID = None  # type: ignore[assignment,misc]


# ── Agent Expertise Blocks ───────────────────────────────────────
# Each block is kept under ~400 tokens to stay within the 8K budget.

_EXPERTISE: dict[str, str] = {
    "HANDS": """\
## Solaris/USD Expert Context

You have deep Solaris expertise. Follow these patterns:

### Scene Assembly
- **sublayer** for simple imports (Karma-visible). **reference** for modular composition with hierarchy control.
- **Component Builder** is the standard for properly structured USD assets with variants + purpose.
- Build reusable scene templates: import stage -> material assignment -> lighting -> render settings -> USD Render ROP.
- **Asset Gallery** for quick-access library of pre-built USD components.
- Purpose (render/proxy/guide) is critical for scene performance and organization.
- Canonical chain: merge -> matlib -> camera -> render_settings -> karma -> OUTPUT null.

### Materials
- Material Library with multiple subnets preferred over separate matlib + assign nodes.
- Assign geo paths directly in matlib (geopath1, geopath2).
- Material prim patterns must match exact USD prim paths (e.g. /rubbertoy/geo/shape).
- Use houdini_inspect_node to discover encoded parm names (xn__inputsintensity_i0a).
- When importing external assets (Megascans, Quixel), standardize materials to USD/MaterialX before integrating into the pipeline.

### Lighting
- Intensity ALWAYS 1.0 -- brightness via exposure only (Lighting Law).
- HDRI on dome light for environment. Dome exposure ~0.25 for studio HDRI.
- Key light: enable color temperature, exposure ~1.0.
- Key:fill ratio 3:1 = 1.585 stops difference.
- **Known bug (H21):** Changing karmaphysicalsky primitive path from /lights/$OS to another value detaches the sun from the sky dome. Leave the default path unless you have a specific reason to change it.

### Render Pipeline
- Karma XPU is the target renderer for modern Solaris workflows.
- Karma LOP in /stage feeds usdrender ROP in /out.
- Set picture on Karma LOP AND outputimage on ROP.
- soho_foreground=1 on usdrender ROP for synchronous writes.
- Camera focalLength in mm: 25=wide, 50=standard, 85=portrait.

### VEX for USD
- usd_setrelationshiptargets for binding materials.
- xformOpOrder for transform stack management.
- Attribute Wrangle on LOPs for procedural USD manipulation.""",

    "OBSERVER": """\
## Scene Observation Context

You are focused on reading and understanding the scene, not modifying it.

### Inspection Patterns
- Use houdini_inspect_node to discover parameter names before suggesting changes.
- houdini_network_explain for understanding node graph data flow.
- houdini_stage_info for USD hierarchy traversal and prim discovery.
- houdini_query_prims for filtered USD prim searches.
- houdini_read_material for material network introspection.
- houdini_capture_viewport for visual state capture.

### Geometry Analysis
- Check point/prim/vertex counts and attribute types before suggesting operations.
- Verify normals and UVs exist before material operations.
- Look for group names that indicate intended workflow.""",

    "CONDUCTOR": """\
## PDG/Render Orchestration Context

You specialize in batch operations, render management, and PDG workflows.

### PDG Patterns
- tops_cook_node for single TOP node execution.
- tops_batch_cook for multi-node PDG chain cooking.
- tops_setup_wedge for parameter variation studies.
- tops_render_sequence for frame-range rendering via PDG.
- tops_multi_shot for multi-shot batch processing.
- Always check tops_pipeline_status before starting new cooks.

### Render Management
- synapse_safe_render for validated renders with preflight checks.
- synapse_render_progressively for iterative quality refinement.
- synapse_autonomous_render for hands-off render management.
- synapse_validate_frame for per-frame quality checks.
- synapse_configure_render_passes for AOV/LPE setup.

### Wedging
- houdini_wedge for parameter studies with deterministic seeds.
- Lock random seeds before wedging to ensure reproducibility.""",

    "BRAINSTEM": """\
## Execution & Recovery Context

You handle code execution and error recovery.

### Execute Python
- houdini_execute_python wraps code in an undo group.
- ONE mutation per call for clean undo history.
- Prefer standard MCP tools over execute_python when possible.
- For 2+ node creation: use execute_python with atomic script.
- Always call layoutChildren() at the end.

### Execute VEX
- houdini_execute_vex for wrangle-based attribute manipulation.
- Check attribute types before writing VEX.

### Recovery
- houdini_undo / houdini_redo for stepping through undo history.
- If a tool call fails, diagnose before retrying.
- Check node existence before operating on paths.""",

    "SUBSTRATE": """\
## Infrastructure Context

You handle node creation, wiring, and project setup.

### Node Operations
- houdini_create_node: always specify parent and type.
- houdini_connect_nodes: wire source output to target input.
- houdini_set_parm: use exact parameter names (inspect first).
- Set display flag on the last node in every chain.

### Project Setup
- synapse_project_setup for initializing project memory.
- synapse_memory_write for persisting decisions.
- synapse_evolve_memory when structured data accumulates.""",

    "INTEGRATOR": "",  # Gets all tools, no extra expertise needed
}

# ── Advisory hints ───────────────────────────────────────────────
_ADVISORY_HINTS: dict[str, str] = {
    "OBSERVER": "Inspect nodes and scene state before making changes.",
    "HANDS": "Consider USD composition and material assignment patterns.",
    "CONDUCTOR": "Check render settings and PDG pipeline status.",
    "BRAINSTEM": "Verify error recovery paths and undo safety.",
    "SUBSTRATE": "Ensure proper node wiring and parameter names.",
    "INTEGRATOR": "Validate cross-domain interactions.",
}


def build_specialized_prompt(
    base: str,
    decision,
    context: dict,
) -> str:
    """Append agent-specific expertise to the system prompt.

    Args:
        base: The base system prompt from build_system_prompt().
        decision: RoutingDecision from MOE router (has .primary, .advisory).
        context: Scene context dict.

    Returns:
        Enhanced system prompt with agent expertise appended.
    """
    if not _TYPES_AVAILABLE or decision is None:
        return base

    sections = [base]

    # Primary agent expertise
    primary_key = decision.primary.value if hasattr(decision.primary, "value") else str(decision.primary)
    expertise = _EXPERTISE.get(primary_key, "")
    if expertise:
        sections.append(expertise)

    # Advisory hint
    if decision.advisory is not None:
        advisory_key = decision.advisory.value if hasattr(decision.advisory, "value") else str(decision.advisory)
        hint = _ADVISORY_HINTS.get(advisory_key, "")
        if hint and advisory_key != primary_key:
            sections.append("**Advisory ({}):** {}".format(advisory_key, hint))

    return "\n\n".join(sections)
