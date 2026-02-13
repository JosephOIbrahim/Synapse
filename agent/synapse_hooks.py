"""
synapse_hooks.py — Safety and verification hooks for the Synapse Agent.

These hooks fire during the agent loop:
- validate_before_execute: Checks code follows atomic convention + guard usage
- enrich_result: Adds coaching-tone messages after tool calls
- enrich_error: Enriches error messages with suggestions

The hooks complement the server-side safety (undo groups, guards.py) with
agent-side intelligence.
"""

import json
import logging
import re
from typing import Any, Optional

from synapse_tone import enrich_error_message, format_success_message

logger = logging.getLogger("synapse.hooks")


# ─────────────────────────────────────────────────────────────
# PRE-EXECUTION VALIDATION
# ─────────────────────────────────────────────────────────────


def validate_atomic_convention(code: str) -> tuple[bool, str]:
    """
    Check if a code block follows the atomic convention (one mutation per call).

    Heuristic: count mutation keywords. If >1 distinct mutation type, flag it.
    This is advisory — doesn't block execution, but warns the agent.
    """
    mutation_patterns = [
        (r"\.createNode\(", "node creation"),
        (r"\.setInput\(", "connection"),
        (r"\.set\(", "parameter set"),
        (r"\.destroy\(", "node deletion"),
        (r"\.move\(", "node move"),
    ]

    found_mutations = set()
    for pattern, label in mutation_patterns:
        if re.search(pattern, code):
            found_mutations.add(label)

    if len(found_mutations) > 1:
        return False, (
            f"This script has multiple mutation types ({', '.join(sorted(found_mutations))}). "
            "For safety, split into separate calls — one mutation per execute. "
            "Read operations can stay combined."
        )

    return True, "Looks good — single mutation type."


def validate_guard_usage(code: str) -> tuple[bool, str]:
    """
    Check if mutations use guard functions for idempotency.
    Advisory — encourages but doesn't block.
    """
    has_raw_create = bool(re.search(r"\.createNode\(", code))
    has_guard_create = bool(re.search(r"ensure_node\(", code))

    has_raw_connect = bool(re.search(r"\.setInput\(", code))
    has_guard_connect = bool(re.search(r"ensure_connection\(", code))

    warnings = []
    if has_raw_create and not has_guard_create:
        warnings.append(
            "Using raw createNode() — consider ensure_node() to prevent duplicates on retry."
        )
    if has_raw_connect and not has_guard_connect:
        warnings.append(
            "Using raw setInput() — consider ensure_connection() to prevent duplicate wiring."
        )

    if warnings:
        return False, " ".join(warnings)
    return True, "Guard functions used appropriately."


def validate_execute_code(code: str) -> Optional[str]:
    """
    Pre-validate code before sending to Synapse.
    Returns a warning string if issues found, None otherwise.
    """
    is_atomic, atomic_msg = validate_atomic_convention(code)
    if not is_atomic:
        logger.warning("Atomic convention violation: %s", atomic_msg)
        return f"Safety note: {atomic_msg}"

    uses_guards, guard_msg = validate_guard_usage(code)
    if not uses_guards:
        logger.info("Guard suggestion: %s", guard_msg)
        # Don't block, just log

    return None


def validate_tops_cook(tool_input: dict) -> Optional[str]:
    """Advisory check for TOPS cook calls.

    Returns a warning string if potential issues detected, None otherwise.
    """
    max_retries = tool_input.get("max_retries", 0)
    if max_retries > 5:
        return "max_retries > 5 may cause long waits -- consider a lower value"
    return None


def enrich_tool_result(tool_name: str, tool_input: dict, result: Any) -> Optional[str]:
    """
    Post-process a tool result with coaching-tone enrichment.
    Returns enriched message or None.
    """
    if tool_name == "synapse_execute":
        try:
            result_data = json.loads(result) if isinstance(result, str) else result
            if isinstance(result_data, dict):
                if result_data.get("executed"):
                    return format_success_message(
                        tool_input.get("description", "operation"), result_data
                    )
                elif result_data.get("error"):
                    return enrich_error_message(
                        result_data.get("error", ""), tool_input.get("code", "")
                    )
        except (json.JSONDecodeError, AttributeError):
            pass

    return None
