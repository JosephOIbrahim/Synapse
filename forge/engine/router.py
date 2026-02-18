"""
FORGE MoE Router — Sparse scenario-to-agent assignment.

Routes scenarios to top-k agents (k=2-3) based on feature extraction.
Mirrors DeepSeek-V3.2 sparse routing: not every agent sees every scenario.
"""

from __future__ import annotations

from .schemas import (
    AgentAssignment,
    AgentRole,
    CorpusEntry,
    ScenarioComplexity,
    ScenarioDefinition,
    ScenarioDomain,
    ScenarioFocus,
)

# =============================================================================
# Routing Tables
# =============================================================================

# Primary agent by focus area
FOCUS_PRIMARY: dict[ScenarioFocus, AgentRole] = {
    ScenarioFocus.QUALITY: AgentRole.SUPERVISOR,
    ScenarioFocus.COVERAGE: AgentRole.RESEARCHER,
    ScenarioFocus.ARCHITECTURE: AgentRole.ARCHITECT,
    ScenarioFocus.RELIABILITY: AgentRole.ENGINEER,
    ScenarioFocus.PERFORMANCE: AgentRole.PRODUCER,
}

# Secondary agent routing rules
FOCUS_SECONDARY: dict[ScenarioFocus, AgentRole] = {
    ScenarioFocus.QUALITY: AgentRole.PRODUCER,  # Time the quality check
    ScenarioFocus.COVERAGE: AgentRole.SUPERVISOR,  # Evaluate discoveries
    ScenarioFocus.ARCHITECTURE: AgentRole.SUPERVISOR,  # Quality gate
    ScenarioFocus.RELIABILITY: AgentRole.PRODUCER,  # Measure degradation
    ScenarioFocus.PERFORMANCE: AgentRole.ENGINEER,  # Stress baseline
}

# Domain expertise mapping (which agents know this domain best)
DOMAIN_EXPERTS: dict[ScenarioDomain, list[AgentRole]] = {
    ScenarioDomain.LIGHTING: [AgentRole.SUPERVISOR, AgentRole.RESEARCHER],
    ScenarioDomain.FX: [AgentRole.RESEARCHER, AgentRole.ENGINEER],
    ScenarioDomain.LOOKDEV: [AgentRole.SUPERVISOR, AgentRole.RESEARCHER],
    ScenarioDomain.LAYOUT: [AgentRole.ARCHITECT, AgentRole.SUPERVISOR],
    ScenarioDomain.PIPELINE: [AgentRole.ARCHITECT, AgentRole.ENGINEER],
    ScenarioDomain.RENDER: [AgentRole.SUPERVISOR, AgentRole.PRODUCER],
    ScenarioDomain.GENERAL: [AgentRole.RESEARCHER, AgentRole.ENGINEER],
}

# Complexity escalation (higher complexity → more agents)
COMPLEXITY_AGENT_COUNT: dict[ScenarioComplexity, int] = {
    ScenarioComplexity.SINGLE_TOOL: 2,
    ScenarioComplexity.WORKFLOW: 2,
    ScenarioComplexity.CROSS_DEPARTMENT: 3,
    ScenarioComplexity.PRODUCTION: 5,  # All agents
}


# =============================================================================
# Router
# =============================================================================


def route_scenario(
    scenario: ScenarioDefinition,
    corpus: list[CorpusEntry] | None = None,
    agent_filter: list[AgentRole] | None = None,
) -> list[AgentAssignment]:
    """Route a scenario to the optimal agent team.
    
    Args:
        scenario: The scenario to route.
        corpus: Available corpus entries for context injection.
        agent_filter: If provided, only assign from these agents.
        
    Returns:
        Ordered list of AgentAssignments (primary first).
    """
    corpus = corpus or []
    k = COMPLEXITY_AGENT_COUNT.get(scenario.complexity, 2)

    # Feature extraction
    primary = FOCUS_PRIMARY.get(scenario.focus, AgentRole.RESEARCHER)
    secondary = FOCUS_SECONDARY.get(scenario.focus, AgentRole.ENGINEER)
    domain_experts = DOMAIN_EXPERTS.get(scenario.domain, [AgentRole.RESEARCHER])

    # Build ranked candidate list (no duplicates)
    candidates: list[AgentRole] = []
    seen: set[AgentRole] = set()

    for agent in [primary, secondary] + domain_experts:
        if agent not in seen:
            candidates.append(agent)
            seen.add(agent)

    # Production complexity gets everyone
    if scenario.complexity == ScenarioComplexity.PRODUCTION:
        for role in AgentRole:
            if role not in seen:
                candidates.append(role)
                seen.add(role)

    # Apply filter if specified
    if agent_filter:
        candidates = [c for c in candidates if c in agent_filter]

    # Take top-k
    selected = candidates[:k]

    # Filter corpus entries relevant to this scenario's domain
    relevant_corpus = [
        entry
        for entry in corpus
        if entry.domain == scenario.domain or entry.domain == ScenarioDomain.GENERAL
    ]

    # Build assignments
    assignments = []
    for i, agent in enumerate(selected):
        role = "primary" if i == 0 else "secondary" if i == 1 else "observer"
        assignments.append(
            AgentAssignment(
                agent=agent,
                scenario=scenario,
                role_in_scenario=role,
                corpus_context=relevant_corpus[:10],  # Cap context size
                notes=f"Routed via focus={scenario.focus.value}, domain={scenario.domain.value}",
            )
        )

    return assignments


def route_batch(
    scenarios: list[ScenarioDefinition],
    corpus: list[CorpusEntry] | None = None,
    agent_filter: list[AgentRole] | None = None,
) -> dict[AgentRole, list[AgentAssignment]]:
    """Route a batch of scenarios, grouped by agent.
    
    Returns:
        Dict mapping each agent to their assignments.
    """
    agent_work: dict[AgentRole, list[AgentAssignment]] = {
        role: [] for role in AgentRole
    }

    for scenario in scenarios:
        assignments = route_scenario(scenario, corpus, agent_filter)
        for assignment in assignments:
            agent_work[assignment.agent].append(assignment)

    # Remove agents with no work
    return {k: v for k, v in agent_work.items() if v}


def explain_routing(scenario: ScenarioDefinition) -> str:
    """Human-readable explanation of why a scenario was routed as it was."""
    assignments = route_scenario(scenario)
    lines = [f"Scenario: {scenario.title}"]
    lines.append(f"  Domain: {scenario.domain.value}")
    lines.append(f"  Focus: {scenario.focus.value}")
    lines.append(f"  Complexity: {scenario.complexity.value}")
    lines.append(f"  Agent count: {len(assignments)}")
    for a in assignments:
        lines.append(f"  → {a.agent.value} ({a.role_in_scenario}): {a.notes}")
    return "\n".join(lines)
