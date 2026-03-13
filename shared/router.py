"""
SYNAPSE Agent Team -- MOE (Mixture of Experts) Router
Sparse routing: extract 4 features -> top-K agents -> dispatch.

Elegant Revision R5: Precise lexical boundary routing
  - re.search(r'\\b...\\b') replaces substring matching
  - 'usd' no longer matches 'paused', 'cop' no longer matches 'scope'
  - Urgency extraction uses word boundaries for accurate intent detection
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
from datetime import datetime
from shared.types import (
    AgentID, TaskType, Complexity, Urgency, DomainSignal,
    RoutingFeatures, TaskSpec, TaskStatus
)
from shared.constants import (
    ADVISORY_SCORE_THRESHOLD,
    BLOCKING_URGENCY_BOOST,
    COMPLEX_DOMAIN_LIMIT,
    COMPLEX_SCORE_MULTIPLIER,
    DOMAIN_AFFINITY,
    DOMAIN_KEYWORDS,
    FAST_PATHS,
    MODERATE_DOMAIN_LIMIT,
    MODERATE_WORD_LIMIT,
    RESEARCH_INTEGRATOR_FLOOR,
    ROUTER_CALIBRATION_PERIOD,
    TASK_TYPE_BOOST,
    TASK_TYPE_KEYWORDS,
    TRIVIAL_DOMAIN_LIMIT,
    TRIVIAL_WORD_LIMIT,
    URGENCY_BLOCKING_PATTERN,
    URGENCY_EXPLORATORY_PATTERN,
)


# ── Router ───────────────────────────────────────────────────────

@dataclass
class RoutingDecision:
    primary: AgentID
    advisory: AgentID | None
    scores: dict[AgentID, float]
    method: str
    features: RoutingFeatures


class MOERouter:
    """Sparse Mixture-of-Experts router for agent dispatch."""

    def __init__(self, k: int = 2):
        self.k = k
        self._call_count = 0
        self._dense_threshold = ROUTER_CALIBRATION_PERIOD
        self._session_fast_paths: dict[str, tuple[AgentID, AgentID | None]] = {}

    def route(self, features: RoutingFeatures) -> RoutingDecision:
        self._call_count += 1
        fingerprint = features.fingerprint()

        # Fast paths after calibration
        if self._call_count > self._dense_threshold:
            if fingerprint in FAST_PATHS:
                primary, advisory = FAST_PATHS[fingerprint]
                return RoutingDecision(
                    primary=primary, advisory=advisory,
                    scores={primary: 1.0, **(({advisory: 0.8} if advisory else {}))},
                    method="fast_path", features=features
                )
            if fingerprint in self._session_fast_paths:
                primary, advisory = self._session_fast_paths[fingerprint]
                return RoutingDecision(
                    primary=primary, advisory=advisory,
                    scores={primary: 1.0, **(({advisory: 0.8} if advisory else {}))},
                    method="session_fast_path", features=features
                )

        # Full scoring
        scores = self._score_all_agents(features)
        sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        primary = sorted_agents[0][0]
        advisory = sorted_agents[1][0] if len(sorted_agents) > 1 and sorted_agents[1][1] > ADVISORY_SCORE_THRESHOLD else None

        return RoutingDecision(
            primary=primary, advisory=advisory,
            scores=scores, method="scored", features=features
        )

    def _score_all_agents(self, features: RoutingFeatures) -> dict[AgentID, float]:
        scores: dict[AgentID, float] = {agent: 0.0 for agent in AgentID}

        for signal in features.domain_signals:
            affinities = DOMAIN_AFFINITY.get(signal, {})
            for agent, affinity in affinities.items():
                scores[agent] += affinity

        boosts = TASK_TYPE_BOOST.get(features.task_type, {})
        for agent, boost in boosts.items():
            scores[agent] += boost

        if features.complexity == Complexity.COMPLEX:
            max_agent = max(scores, key=scores.get)
            scores[max_agent] *= COMPLEX_SCORE_MULTIPLIER
        elif features.complexity == Complexity.RESEARCH:
            scores[AgentID.INTEGRATOR] = max(scores[AgentID.INTEGRATOR], RESEARCH_INTEGRATOR_FLOOR)

        if features.urgency == Urgency.BLOCKING:
            scores[AgentID.BRAINSTEM] += BLOCKING_URGENCY_BOOST

        return scores

    def learn_fast_path(self, fingerprint: str, primary: AgentID,
                         advisory: AgentID | None):
        self._session_fast_paths[fingerprint] = (primary, advisory)


# ── R5: Feature Extraction with Word Boundaries ─────────────────

def extract_features(task_description: str) -> RoutingFeatures:
    """
    R5: Extract routing features using precise lexical boundaries.
    \\b ensures exact word matching: 'usd' won't match 'paused',
    'cop' won't match 'scope', 'fix' won't match 'prefix'.
    """
    text = task_description.lower()

    # Domain signals -- word boundary matching
    domain_signals = set()
    for keyword, signal in DOMAIN_KEYWORDS.items():
        if re.search(rf'\b{re.escape(keyword)}\b', text):
            domain_signals.add(signal)

    # Task type -- first word-boundary match wins
    task_type = TaskType.GENERATION
    for keyword, tt in TASK_TYPE_KEYWORDS.items():
        if re.search(rf'\b{re.escape(keyword)}\b', text):
            task_type = tt
            break

    # Complexity heuristic (unchanged -- works on counts)
    words = text.split()
    word_count = len(words)
    domain_count = len(domain_signals)
    if word_count < TRIVIAL_WORD_LIMIT and domain_count <= TRIVIAL_DOMAIN_LIMIT:
        complexity = Complexity.TRIVIAL
    elif word_count < MODERATE_WORD_LIMIT and domain_count <= MODERATE_DOMAIN_LIMIT:
        complexity = Complexity.MODERATE
    elif domain_count <= COMPLEX_DOMAIN_LIMIT:
        complexity = Complexity.COMPLEX
    else:
        complexity = Complexity.RESEARCH

    # Urgency -- word boundary matching with expanded vocabulary
    urgency = Urgency.NORMAL
    if re.search(URGENCY_BLOCKING_PATTERN, text):
        urgency = Urgency.BLOCKING
    elif re.search(URGENCY_EXPLORATORY_PATTERN, text):
        urgency = Urgency.EXPLORATORY

    return RoutingFeatures(
        task_type=task_type,
        complexity=complexity,
        domain_signals=tuple(domain_signals) if domain_signals else (DomainSignal.GEOMETRY,),
        urgency=urgency
    )


# ── Convenience ──────────────────────────────────────────────────

def route_task(description: str) -> RoutingDecision:
    """One-shot: extract features and route."""
    features = extract_features(description)
    router = MOERouter()
    return router.route(features)
