"""
Synapse Parameter Aliasing

Centralized parameter aliasing system to accept multiple naming conventions.
Allows clients to use different naming conventions (camelCase, snake_case, etc.)
"""

from typing import Dict, List, Any


# =============================================================================
# PARAMETER ALIASES
# =============================================================================

PARAM_ALIASES: Dict[str, List[str]] = {
    # Node references
    "source": ["source", "from_node", "from", "src", "input_node"],
    "target": ["target", "to_node", "to", "dst", "output_node", "dest"],
    "node": ["node", "path", "node_path"],
    "parent": ["parent", "parent_path", "parent_node"],

    # Input/output indices
    "source_output": ["source_output", "from_output", "output_index", "out_idx"],
    "target_input": ["target_input", "to_input", "input_index", "in_idx"],

    # Parameters
    "parm": ["parm", "parameter", "param", "attr", "attribute"],
    "value": ["value", "val", "v"],

    # Node creation
    "type": ["type", "node_type", "nodeType"],
    "name": ["name", "node_name", "nodeName"],

    # USD
    "prim_path": ["prim_path", "path", "primPath"],
    "prim_type": ["prim_type", "type", "primType"],

    # Memory operations
    "query": ["query", "q", "search", "text"],
    "content": ["content", "text", "message", "body"],
    "memory_type": ["memory_type", "type", "memoryType"],
    "tags": ["tags", "labels", "categories"],
    "keywords": ["keywords", "keys", "concepts"],
    "limit": ["limit", "max", "count"],
    "decision": ["decision", "what", "choice"],
    "reasoning": ["reasoning", "why", "rationale", "reason"],
    "alternatives": ["alternatives", "options", "other_options", "otherOptions"],
}


def resolve_param(payload: Dict, canonical: str, required: bool = True) -> Any:
    """
    Resolve a parameter from payload using aliasing.

    Args:
        payload: The command payload dictionary
        canonical: The canonical parameter name
        required: Whether the parameter is required

    Returns:
        The parameter value, or None if not found and not required

    Raises:
        ValueError: If required parameter is not found
    """
    aliases = PARAM_ALIASES.get(canonical, [canonical])

    for alias in aliases:
        if alias in payload:
            return payload[alias]

    if required:
        alias_list = ", ".join(f"'{a}'" for a in aliases)
        raise ValueError(
            f"Missing required parameter. Expected one of: {alias_list}\n"
            f"HINT: Common names are '{canonical}' or '{aliases[1] if len(aliases) > 1 else canonical}'"
        )

    return None


def resolve_param_with_default(payload: Dict, canonical: str, default: Any) -> Any:
    """Resolve parameter with a default value if not found."""
    result = resolve_param(payload, canonical, required=False)
    return result if result is not None else default


def get_all_aliases(canonical: str) -> List[str]:
    """Get all aliases for a canonical parameter name."""
    return PARAM_ALIASES.get(canonical, [canonical])


def add_alias(canonical: str, alias: str):
    """Add a new alias for a canonical parameter name."""
    if canonical not in PARAM_ALIASES:
        PARAM_ALIASES[canonical] = [canonical]
    if alias not in PARAM_ALIASES[canonical]:
        PARAM_ALIASES[canonical].append(alias)
