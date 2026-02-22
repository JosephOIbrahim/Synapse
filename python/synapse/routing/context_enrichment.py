"""
Context Enrichment for LLM Routing Tiers

Builds enriched context strings by combining:
- Tier 1 knowledge lookup results (RAG)
- Project memory search results
- Tool group domain knowledge preambles

Extracted from inline enrichment in router.py for reuse
across Tier 2 (Haiku) and Tier 3 (Agent) routing.
"""

import logging
from typing import Dict, List, Optional, Any

try:
    from .knowledge import KnowledgeLookupResult
except ImportError:
    # Standalone import (e.g. from tests via spec_from_file_location)
    KnowledgeLookupResult = None  # type: ignore[misc, assignment]

logger = logging.getLogger(__name__)

# Tool group knowledge preambles — populated by register_group_knowledge()
_GROUP_KNOWLEDGE: Dict[str, str] = {}


def register_group_knowledge(groups: Dict[str, str]) -> None:
    """Register tool group knowledge preambles.

    Called once at startup with {group_name: knowledge_text} mapping.
    Typically populated from mcp_tools_*.GROUP_KNOWLEDGE constants.
    """
    _GROUP_KNOWLEDGE.update(groups)


def enrich_context(
    message: str,
    tier1_hint: Optional[KnowledgeLookupResult] = None,
    memory: Optional[Any] = None,
    tool_group: Optional[str] = None,
    memory_limit: int = 3,
) -> str:
    """Build enriched context string for LLM routing tiers.

    Assembles context from multiple sources in priority order:
    1. Tool group domain knowledge (if tool_group specified)
    2. Tier 1 RAG knowledge (if tier1_hint.found)
    3. Project memory search results (if memory available)
    4. The original message

    Args:
        message: The user's input query.
        tier1_hint: Optional Tier 1 knowledge lookup result.
        memory: Optional SynapseMemory instance for context search.
        tool_group: Optional tool group name to inject domain knowledge.
        memory_limit: Max memory results to include (default 3).

    Returns:
        Enriched context string with XML-tagged sections.
    """
    parts: List[str] = []

    # 1. Tool group domain knowledge
    if tool_group and tool_group in _GROUP_KNOWLEDGE:
        knowledge = _GROUP_KNOWLEDGE[tool_group]
        parts.append(
            f'<context source="tool_group" group="{tool_group}">\n'
            f"{knowledge}\n</context>\n"
        )

    # 2. Tier 1 RAG knowledge
    if tier1_hint and tier1_hint.found:
        parts.append(
            f'<context source="tier1" confidence="{tier1_hint.confidence:.2f}">\n'
            f"{tier1_hint.answer}\n</context>\n"
        )

    # 3. Project memory
    if memory is not None:
        try:
            recent = memory.search(query=message, limit=memory_limit)
            if recent:
                mem_lines = [
                    f"- {r.memory.summary or r.memory.content[:100]}"
                    for r in recent
                ]
                parts.append(
                    "<memory>\n" + "\n".join(mem_lines) + "\n</memory>\n"
                )
        except Exception:
            logger.debug("Memory search failed during context enrichment")

    # 4. Original message
    parts.append(message)

    return "\n".join(parts)


def get_group_for_tool(tool_name: str) -> Optional[str]:
    """Resolve which tool group a tool belongs to.

    Returns the group name (e.g. 'render', 'usd') or None if unknown.
    Uses prefix heuristics — no import of tool group modules required.
    """
    _PREFIX_MAP = {
        "tops_": "tops",
        "houdini_render": "render",
        "houdini_capture": "render",
        "houdini_set_keyframe": "render",
        "houdini_render_settings": "render",
        "houdini_stage_info": "usd",
        "houdini_get_usd": "usd",
        "houdini_set_usd": "usd",
        "houdini_create_usd": "usd",
        "houdini_modify_usd": "usd",
        "houdini_reference_usd": "usd",
        "houdini_query_prims": "usd",
        "houdini_manage_variant": "usd",
        "houdini_manage_collection": "usd",
        "houdini_configure_light": "usd",
        "houdini_create_material": "usd",
        "houdini_create_textured": "usd",
        "houdini_assign_material": "usd",
        "houdini_read_material": "usd",
        "houdini_hda_": "memory",
        "synapse_knowledge": "memory",
        "synapse_context": "memory",
        "synapse_search": "memory",
        "synapse_recall": "memory",
        "synapse_decide": "memory",
        "synapse_add_memory": "memory",
        "synapse_project_setup": "memory",
        "synapse_memory_": "memory",
        "synapse_evolve_memory": "memory",
        "synapse_metrics": "memory",
        "synapse_router_stats": "memory",
        "synapse_list_recipes": "memory",
        "synapse_live_metrics": "memory",
        "synapse_validate_frame": "render",
        "synapse_configure_render": "render",
        "synapse_render_": "render",
        "synapse_autonomous_render": "render",
        "synapse_validate_ordering": "render",
    }

    # Check exact matches first, then prefix matches
    for prefix, group in sorted(_PREFIX_MAP.items(), key=lambda x: -len(x[0])):
        if tool_name.startswith(prefix):
            return group

    # Default: scene group for houdini_* and synapse_* tools not matched above
    if tool_name.startswith(("houdini_", "synapse_")):
        return "scene"

    return None
