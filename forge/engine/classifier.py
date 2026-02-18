"""
FORGE Classifier — Maps scenario failures to actionable categories.

Each category routes to a specific fix generator. The classifier uses
keyword matching and heuristics, graduating to pattern matching as
the corpus grows.
"""

from __future__ import annotations

from .schemas import (
    CorpusEntry,
    FailureCategory,
    ScenarioResult,
    BacklogItem,
)


# =============================================================================
# Classification Rules
# =============================================================================

# Keyword → category mapping (first match wins within priority tiers)
CLASSIFICATION_RULES: list[tuple[list[str], FailureCategory, int]] = [
    # Priority 0: Safety (check first)
    (
        ["undo failed", "scene corrupt", "cannot rollback", "dirty state"],
        FailureCategory.MISSING_GUARDRAIL,
        0,
    ),
    (
        ["partial", "midway", "half-completed", "incomplete mutation"],
        FailureCategory.PARTIAL_EXECUTION,
        0,
    ),
    # Priority 1: API/Knowledge
    (
        ["attributeerror", "no attribute", "no such method", "not callable",
         "does not exist", "unknown function", "hou."],
        FailureCategory.HALLUCINATED_API,
        1,
    ),
    (
        ["wrong file", "deployed", "~/.synapse", "wrong path", "source vs"],
        FailureCategory.WRONG_TARGET,
        1,
    ),
    # Priority 2: Conventions
    (
        ["convention", "wiring", "pattern", "standard", "how to", "dop network",
         "material prim", "binding"],
        FailureCategory.MISSING_CONVENTION,
        2,
    ),
    (
        ["order", "ordering", "sequence", "before", "after", "livrps",
         "composition order", "evaluation order"],
        FailureCategory.WRONG_ORDERING,
        2,
    ),
    (
        ["composition", "arc", "reference", "sublayer", "payload",
         "orphan prim", "broken reference"],
        FailureCategory.COMPOSITION_ERROR,
        2,
    ),
    # Priority 3: UX/Efficiency
    (
        ["parameter name", "ui label", "encoded", "api name", "mismatch"],
        FailureCategory.PARAMETER_CONFUSION,
        3,
    ),
    (
        ["no tool", "missing tool", "needed a tool", "doesn't exist",
         "not available", "no mcp"],
        FailureCategory.TOOL_GAP,
        3,
    ),
    (
        ["too many", "steps", "calls", "friction", "roundtrip", "inefficient"],
        FailureCategory.WORKFLOW_FRICTION,
        3,
    ),
    # Priority 4: Performance
    (
        ["slow", "timeout", "took too long", "performance", "elapsed"],
        FailureCategory.SLOW_OPERATION,
        4,
    ),
    (
        ["memory", "oom", "out of memory", "ram", "swap"],
        FailureCategory.MEMORY_PRESSURE,
        4,
    ),
]


# =============================================================================
# Classifier
# =============================================================================


def classify_failure(result: ScenarioResult) -> FailureCategory:
    """Classify a failed scenario result into a FailureCategory.
    
    Uses keyword matching against error messages, friction notes,
    and agent report content. Returns the highest-priority match.
    """
    if result.success:
        # Successful scenarios can still have friction
        return _classify_friction(result)

    # Build searchable text from all relevant fields
    search_text = _build_search_text(result).lower()

    # If agent already classified it, trust the agent
    if result.failure_category is not None:
        return result.failure_category

    # Keyword matching, priority-ordered
    best_match: FailureCategory | None = None
    best_priority = 999

    for keywords, category, priority in CLASSIFICATION_RULES:
        if priority > best_priority:
            continue
        for keyword in keywords:
            if keyword.lower() in search_text:
                best_match = category
                best_priority = priority
                break

    if best_match is not None:
        return best_match

    # Fallback: if we can't classify, it's missing knowledge
    return FailureCategory.MISSING_KNOWLEDGE


def _classify_friction(result: ScenarioResult) -> FailureCategory:
    """Classify friction in a successful scenario."""
    if result.friction_ratio > 2.0:
        return FailureCategory.WORKFLOW_FRICTION
    if result.missing_tools:
        return FailureCategory.TOOL_GAP
    # Check friction notes for parameter confusion signals
    friction_text = " ".join(result.friction_notes).lower()
    if any(kw in friction_text for kw in ["parameter", "name", "label", "encoded"]):
        return FailureCategory.PARAMETER_CONFUSION
    return FailureCategory.WORKFLOW_FRICTION


def _build_search_text(result: ScenarioResult) -> str:
    """Concatenate all searchable fields from a result."""
    parts = [
        result.error_message or "",
        result.failure_point or "",
        result.workaround_description or "",
        result.corpus_contribution,
        " ".join(result.friction_notes),
        " ".join(result.missing_tools),
    ]
    # Include agent report text
    if result.agent_report:
        parts.append(str(result.agent_report))
    # Include tool call errors
    for tc in result.tool_calls:
        if tc.error_message:
            parts.append(tc.error_message)
        parts.append(tc.notes)
    return " ".join(parts)


def classify_batch(
    results: list[ScenarioResult],
) -> dict[FailureCategory, list[ScenarioResult]]:
    """Classify a batch of results, grouped by category."""
    grouped: dict[FailureCategory, list[ScenarioResult]] = {}
    for result in results:
        if not result.success or result.friction_notes or result.missing_tools:
            category = classify_failure(result)
            result.failure_category = category
            grouped.setdefault(category, []).append(result)
    return grouped


def should_escalate_to_human(
    category: FailureCategory,
    recurrence_count: int = 1,
    corpus_entries: list[CorpusEntry] | None = None,
) -> bool:
    """Determine if a failure should be escalated to human review.
    
    Even automated categories escalate if:
    - The same failure recurs > 3 times despite fixes
    - The fix destination says human_review
    """
    if category.fix_destination == "human_review":
        return True
    if recurrence_count > 3:
        return True  # Automated fix isn't working
    return False


def generate_backlog_item(
    result: ScenarioResult,
    category: FailureCategory,
    cycle: int,
) -> BacklogItem:
    """Create a human-review backlog item from a classified failure."""
    return BacklogItem(
        id=f"BL-{cycle:04d}-{result.scenario_id}",
        created_cycle=cycle,
        category=category.value,
        title=f"[{category.value}] {result.scenario_id}",
        description=(
            f"Agent {result.agent.value} encountered {category.value} "
            f"during scenario {result.scenario_id}.\n"
            f"Error: {result.error_message or 'N/A'}\n"
            f"Failure point: {result.failure_point or 'N/A'}\n"
            f"Friction notes: {'; '.join(result.friction_notes) or 'None'}"
        ),
        evidence=[result.scenario_id],
        proposed_fix=result.workaround_description or "No automated fix available",
        priority=_priority_from_category(category),
    )


def _priority_from_category(category: FailureCategory) -> str:
    """Map category to backlog priority."""
    critical = {FailureCategory.MISSING_GUARDRAIL, FailureCategory.PARTIAL_EXECUTION}
    high = {FailureCategory.TOOL_GAP, FailureCategory.COMPOSITION_ERROR}
    low = {FailureCategory.SLOW_OPERATION, FailureCategory.MEMORY_PRESSURE}
    if category in critical:
        return "critical"
    if category in high:
        return "high"
    if category in low:
        return "low"
    return "medium"
